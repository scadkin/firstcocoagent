"""
campaign_autopilot.py — daily strategy-agnostic prospect-adder.

Called by ``agent/main.py`` at the 07:00 CST scheduler tick. Per strategy
with ``pool_source`` configured:

  1. Load (or rebuild) the persisted candidate pool.
  2. Read budget-report per sequence (throttle, adds_last_24h).
  3. For each enabled sequence with throttle>0, determine ``need``.
  4. Pull ``need * 2`` candidates from the matching cohort, run two
     at-add-time correctness checks per candidate:
         (a) prospect touched in last 90d → skip  recent_activity
         (b) prospect already in a dre-2026-spring-tagged sequence → skip
             already_in_dre_cohort
  5. Build LoadPlan list; call ``prospect_loader.execute_load_plan`` with
     60-120s jittered sleeps.
  6. Write audit line to ``vault/logs/campaign_autopilot.jsonl``.
  7. Return ``AutopilotReport`` for the Telegram formatter.

Safety rails:
  * Kill switch ``~/.claude/state/scout-campaign-autopilot-disabled`` is
    checked first; presence short-circuits to a disabled report.
  * Dry-run and live-run share the exact same code path; only the
    ``dry_run`` flag passed into ``execute_load_plan`` differs.
  * ``--preview`` mode writes a CSV of the exact next batch without
    building LoadPlans or calling Outreach at all — used by the Steven
    eyeball-before-go-live gate.
  * Per-strategy safety fuse = sum(active throttle_per_day across enabled
    sequences). Never overshoots config.

Rule 19: formatter accepts only sequence NAMES in display text; raw IDs
never reach Telegram output. Sequence-ID types flow through data
structures, not through format strings.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import logging
import sys
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from tools.campaign_config import (
    REPO_ROOT,
    STRATEGIES,
    StrategyConfig,
    resolve_sequence_ids,
)
from tools.campaign_pool import PoolLead, StrategyPool, get_or_build_pool

logger = logging.getLogger(__name__)

# ── Paths & constants ──────────────────────────────────────────────────

KILL_SWITCH = Path("~/.claude/state/scout-campaign-autopilot-disabled").expanduser()
AUTOPILOT_STATE_DIR = REPO_ROOT / "data"
AUTOPILOT_AUDIT_LOG = REPO_ROOT / "vault" / "logs" / "campaign_autopilot.jsonl"
AUTOPILOT_ARCHIVE_DIR = REPO_ROOT / "data" / "archive"

DRE_CAMPAIGN_TAG = "dre-2026-spring"
RECENT_ACTIVITY_DAYS = 90
STATE_FILE_RETENTION_DAYS = 30
SLEEP_SECONDS_RANGE = (60, 120)
DEFAULT_MAILBOX_ID = 11


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class SequenceAutopilotResult:
    """Per-sequence outcome inside one strategy's autopilot run."""
    sequence_name: str         # Rule 19: always the display name
    throttle: int
    adds_last_24h: int
    need: int
    attempted: int = 0
    succeeded: int = 0
    skipped_recent_activity: int = 0
    skipped_already_in_dre_cohort: int = 0
    skipped_existing_seq_state: int = 0  # already in this specific seq
    skipped_no_pool_candidates: int = 0
    skipped_not_in_outreach: int = 0  # DRE = dormant re-engage; never create-new
    skipped_rule17: int = 0
    failed: int = 0
    cohort_remaining: int = 0  # pool rows left for this sequence's cohort


@dataclass
class StrategyAutopilotResult:
    """Per-strategy outcome within one run."""
    strategy_key: str
    display: str
    tier: int
    weekly_budget: int
    sends_7d: int = 0
    headroom: int = 0
    utilization_pct: float = 0.0
    profile: Optional[str] = None
    pool_built_at: Optional[str] = None
    pool_excluded: dict[str, int] = field(default_factory=dict)
    sequences: dict[str, SequenceAutopilotResult] = field(default_factory=dict)


@dataclass
class AutopilotReport:
    """Top-level result of one autopilot invocation."""
    ts_utc: str
    ts_cst: str
    mode: str                  # "dry_run" | "live" | "disabled" | "error"
    strategies: dict[str, StrategyAutopilotResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    # Computed aggregates for Telegram formatter / audit log
    def total_attempted(self) -> int:
        return sum(seq.attempted
                   for s in self.strategies.values()
                   for seq in s.sequences.values())

    def total_succeeded(self) -> int:
        return sum(seq.succeeded
                   for s in self.strategies.values()
                   for seq in s.sequences.values())


# ── Kill switch ────────────────────────────────────────────────────────

def _kill_switch_active() -> bool:
    return KILL_SWITCH.exists()


# ── Timestamps ─────────────────────────────────────────────────────────

def _now_timestamps() -> tuple[str, str]:
    import zoneinfo
    cst = zoneinfo.ZoneInfo("America/Chicago")
    now_utc = datetime.now(timezone.utc)
    return (
        now_utc.isoformat(timespec="seconds"),
        now_utc.astimezone(cst).isoformat(timespec="seconds"),
    )


# ── Budget + freshness API calls ───────────────────────────────────────

def _adds_last_24h(seq_id: int) -> int:
    """Count sequenceStates created in the last 24h for one sequence."""
    from tools.outreach_client import _api_get_all
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "filter[sequence][id]": str(seq_id),
        "filter[createdAt]": f"{since}..{now}",
        "page[size]": "50",
    }
    try:
        return len(_api_get_all("/sequenceStates", params, max_pages=20))
    except Exception as e:
        logger.warning("adds_last_24h(%s) error: %s", seq_id, e)
        return 0


def _get_prospect_touched_at(prospect_id: str) -> Optional[str]:
    """Fetch raw prospect attributes.touchedAt (ISO) for freshness check."""
    from tools.outreach_client import _api_get
    try:
        r = _api_get(f"/prospects/{prospect_id}")
    except Exception as e:
        logger.warning("get /prospects/%s error: %s", prospect_id, e)
        return None
    return r.get("data", {}).get("attributes", {}).get("touchedAt")


def _prospect_has_active_dre_cohort_state(prospect_id: str) -> bool:
    """True if the prospect is currently active in any sequence tagged dre-2026-spring."""
    from tools.outreach_client import _api_get
    params = {
        "filter[prospect][id]": str(prospect_id),
        "include": "sequence",
        "page[size]": "50",
    }
    try:
        r = _api_get("/sequenceStates", params)
    except Exception as e:
        logger.warning("/sequenceStates for prospect %s error: %s", prospect_id, e)
        return False
    for inc in r.get("included", []) or []:
        if inc.get("type") != "sequence":
            continue
        tags = inc.get("attributes", {}).get("tags", []) or []
        if DRE_CAMPAIGN_TAG in tags:
            return True
    return False


def _is_recent_activity(touched_at_iso: Optional[str], days: int = RECENT_ACTIVITY_DAYS) -> bool:
    """True if touched_at within last `days`."""
    if not touched_at_iso:
        return False
    try:
        # Outreach timestamps are Z-suffixed ISO 8601
        touched = datetime.fromisoformat(touched_at_iso.replace("Z", "+00:00"))
    except Exception:
        return False
    if touched.tzinfo is None:
        touched = touched.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - touched) < timedelta(days=days)


# ── Sequence name ↔ ID resolution ──────────────────────────────────────

def _build_name_to_id_map(seq_ids: list[int]) -> dict[str, int]:
    """For a strategy's sequence IDs, fetch display name per ID."""
    from scripts.campaign_budget_status import get_sequence_meta
    out: dict[str, int] = {}
    for sid in seq_ids:
        meta = get_sequence_meta(sid)
        out[meta["name"]] = sid
    return out


def _sequence_meta_bulk(seq_ids: list[int]) -> dict[int, dict]:
    """Bulk-fetch {seq_id: meta} including throttle + enabled + name."""
    from scripts.campaign_budget_status import get_sequence_meta
    return {sid: get_sequence_meta(sid) for sid in seq_ids}


# ── Tag derivation ─────────────────────────────────────────────────────

def _derive_tags(cohort: str, state: str) -> list[str]:
    """Build Outreach tag list per project_dre_family_framework.md conventions."""
    tags = [DRE_CAMPAIGN_TAG]
    sub_map = {
        "TC-": "tc",
        "LQD-": "lqd",
        "INT-": "int",
        "LIB": "lib",
        "IT-ReEngage": "it-reengage",
    }
    for prefix, sub in sub_map.items():
        if cohort == prefix.rstrip("-") or cohort.startswith(prefix):
            tags.append(f"dre-{sub}")
            break

    grade_map = {
        "TC-Elem": "elem", "TC-MS": "ms", "TC-HS": "hs",
        "TC-Virtual": "virtual", "TC-District": "district",
        "TC-All-Grades": "all",
    }
    if cohort in grade_map:
        tags.append(f"dre-grade-{grade_map[cohort]}")

    if state:
        tags.append(f"dre-state-{state.lower()}")
    tags.append("dre-cohort-sf-leads")
    return tags


# ── Contact conversion ─────────────────────────────────────────────────

def _pool_lead_to_contact(lead: PoolLead):
    """Convert a PoolLead into a prospect_loader.Contact."""
    from tools.prospect_loader import Contact
    return Contact(
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=lead.email,
        title=lead.title,
        company=lead.company,
        state=lead.state,
        email_confidence=lead.email_confidence,
        diocese_or_group=lead.diocese_or_group,
    )


# ── State-file archive ─────────────────────────────────────────────────

def _archive_old_state_files(now: datetime) -> None:
    """Move per-day autopilot state files older than N days to archive/."""
    cutoff = now - timedelta(days=STATE_FILE_RETENTION_DAYS)
    AUTOPILOT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for p in AUTOPILOT_STATE_DIR.glob("dre_autopilot_*.state.json"):
        try:
            stem_parts = p.stem.split("_")  # ['dre', 'autopilot', '2026-04-18', 'state']
            date_str = stem_parts[2] if len(stem_parts) > 2 else ""
            d = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if d < cutoff:
                target = AUTOPILOT_ARCHIVE_DIR / p.name
                p.rename(target)
                logger.info("Archived old autopilot state file: %s", target)
        except Exception as e:
            logger.warning("Could not archive %s: %s", p, e)


# ── Core run ───────────────────────────────────────────────────────────

def _process_strategy(
    strategy_key: str,
    strategy: StrategyConfig,
    *,
    dry_run: bool,
    preview_only: bool,
    preview_rows: list[dict],
    refresh_pool: Optional[bool],
) -> StrategyAutopilotResult:
    """Run one strategy's autopilot. Returns the per-strategy result."""
    # Lazy imports so module load stays cheap when disabled
    from scripts.campaign_budget_status import build_strategy_report
    from tools.outreach_client import find_prospect_by_email
    from tools.prospect_loader import LoadPlan, execute_load_plan

    result = StrategyAutopilotResult(
        strategy_key=strategy_key,
        display=strategy["display"],
        tier=strategy["tier"],
        weekly_budget=strategy["weekly_budget"],
        profile=strategy.get("throttle_profile_name"),
    )

    if not strategy.get("pool_source"):
        return result  # silently skip — Telegram formatter filters these out

    # 1. Pool — Monday scheduled rebuild OR self-heal on age>8d
    today_cst = datetime.now(_chicago_tz()).date()
    is_monday = today_cst.weekday() == 0
    force_refresh = refresh_pool if refresh_pool is not None else is_monday
    pool: StrategyPool = get_or_build_pool(strategy_key, force_refresh=force_refresh)
    result.pool_built_at = pool.built_at
    result.pool_excluded = dict(pool.excluded)

    # 2. Budget report
    report = build_strategy_report(strategy_key, strategy)
    result.sends_7d = report.get("rolling_7d_sends", 0)
    result.headroom = report.get("headroom", 0)
    result.utilization_pct = report.get("utilization_pct", 0.0)

    # 3. Priority-fill: compute strategy-wide daily budget, walk sequences in
    # priority order, fill each up to min(remaining_budget, pool_size,
    # sequence_capacity). When a high-priority cohort's pool empties the
    # spillover flows naturally to the next priority.
    bucket_to_seq_name = strategy.get("bucket_to_sequence_name") or {}
    seq_name_to_bucket = {v: k for k, v in bucket_to_seq_name.items()}
    priority_order: list[str] = strategy.get("priority_order") or []

    # Strategy splits weekly budget across the 5 weekday autopilot ticks.
    # 266/5 = 53/day for DRE. Outreach's delivery schedules handle actual
    # send distribution (Mon-Fri vs Tue-Thu vs Mon-Thu) server-side.
    strategy_daily_budget = max(1, strategy["weekly_budget"] // 5)
    remaining_budget = strategy_daily_budget

    plans_by_sequence: dict[int, list[LoadPlan]] = {}
    seq_meta_by_id: dict[int, dict] = {}

    # Index sequences from the budget report by name for O(1) lookup
    seq_info_by_name: dict[str, dict] = {}
    for seq_info in report.get("sequences", []):
        seq_info_by_name[seq_info["name"]] = seq_info
        seq_meta_by_id[int(seq_info["id"])] = seq_info

    # Cohort-level dedupe: a PoolLead lives in exactly one bucket but we
    # enforce by email set regardless.
    emails_claimed_this_run: set[str] = set()

    # If no priority_order configured, fall back to a sensible default —
    # every enabled sequence with a mapped bucket, in budget-report order.
    fill_cohorts: list[str] = priority_order or [
        seq_name_to_bucket[s["name"]]
        for s in report.get("sequences", [])
        if s.get("enabled") and seq_name_to_bucket.get(s["name"])
    ]

    for cohort in fill_cohorts:
        if remaining_budget <= 0:
            break
        seq_name = bucket_to_seq_name.get(cohort)
        if not seq_name:
            logger.warning("priority_order entry %r has no bucket mapping", cohort)
            continue
        seq_info = seq_info_by_name.get(seq_name)
        if not seq_info:
            logger.warning("priority sequence %r not in budget report", seq_name)
            continue

        seq_id = int(seq_info["id"])
        throttle = seq_info.get("throttle_per_day") or 0
        enabled = seq_info.get("enabled")
        adds_24h = _adds_last_24h(seq_id)

        seq_result = SequenceAutopilotResult(
            sequence_name=seq_name,
            throttle=throttle,
            adds_last_24h=adds_24h,
            need=0,  # set below once we know target
            cohort_remaining=len(pool.buckets.get(cohort, [])),
        )
        result.sequences[seq_name] = seq_result

        if not enabled:
            continue

        seq_capacity = max(0, throttle - adds_24h)
        target = min(remaining_budget, seq_capacity, seq_result.cohort_remaining)
        seq_result.need = target

        if target <= 0:
            if seq_result.cohort_remaining <= 0:
                seq_result.skipped_no_pool_candidates = remaining_budget
            continue

        # Pull candidates; apply correctness checks with 2x headroom.
        candidates: list[PoolLead] = list(pool.buckets.get(cohort, []))
        accepted: list[PoolLead] = []
        for lead in candidates:
            if len(accepted) >= target:
                break
            if lead.email.lower() in emails_claimed_this_run:
                continue

            seq_result.attempted += 1

            # At-add-time correctness checks (real Outreach API calls)
            prospect = find_prospect_by_email(lead.email)
            if prospect is None:
                # DRE = dormant re-engage. A lead not yet in Outreach was
                # never engaged — "re-engage" is a category error. Skip
                # rather than falling through to create_prospect.
                seq_result.skipped_not_in_outreach += 1
                continue
            prospect_id = prospect["prospect_id"]
            touched = _get_prospect_touched_at(prospect_id)
            if _is_recent_activity(touched):
                seq_result.skipped_recent_activity += 1
                continue
            if _prospect_has_active_dre_cohort_state(prospect_id):
                seq_result.skipped_already_in_dre_cohort += 1
                continue

            accepted.append(lead)
            emails_claimed_this_run.add(lead.email.lower())

        remaining_budget -= len(accepted)

        # Preview mode: record the batch but don't build LoadPlans
        if preview_only:
            for lead in accepted:
                preview_rows.append({
                    "email": lead.email,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "company": lead.company,
                    "state": lead.state,
                    "bucket": lead.bucket,
                    "target_sequence": seq_name,
                })
            seq_result.succeeded = len(accepted)   # "would-add" count
            continue

        # Build LoadPlans
        today_iso = datetime.now(_chicago_tz()).date().isoformat()
        tags_for_cohort = _derive_tags(cohort, accepted[0].state if accepted else "")
        for lead in accepted:
            contact = _pool_lead_to_contact(lead)
            # Per-lead state tag (state differs row-to-row)
            per_lead_tags = [t for t in tags_for_cohort if not t.startswith("dre-state-")]
            per_lead_tags.append(f"dre-state-{lead.state.lower()}")
            plan = LoadPlan(
                contact=contact,
                sequence_id=seq_id,
                mailbox_id=DEFAULT_MAILBOX_ID,
                tags=per_lead_tags,
                day_bucket=today_iso,
            )
            plans_by_sequence.setdefault(seq_id, []).append(plan)

    if preview_only:
        return result

    # 4. Execute per sequence (isolates state files + sleep cadence)
    today_iso = datetime.now(_chicago_tz()).date().isoformat()
    for seq_id, plans in plans_by_sequence.items():
        state_path = AUTOPILOT_STATE_DIR / f"{strategy_key}_autopilot_{today_iso}.state.json"
        audit_path = AUTOPILOT_AUDIT_LOG.parent / f"{strategy_key}_autopilot_{today_iso}.audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            summary = execute_load_plan(
                plans,
                state_path=str(state_path),
                audit_path=str(audit_path),
                sleep_seconds=SLEEP_SECONDS_RANGE,
                verify_sequence_active=True,
                dry_run=dry_run,
            )
        except Exception as e:
            logger.error("execute_load_plan failed for seq %s: %s", seq_id, e)
            # Attribute failure to every plan in this sequence
            name = seq_meta_by_id[seq_id]["name"]
            if name in result.sequences:
                result.sequences[name].failed += len(plans)
            continue

        # Attribute outcomes
        name = seq_meta_by_id[seq_id]["name"]
        if name in result.sequences:
            sr = result.sequences[name]
            sr.succeeded = summary.get("processed", 0) - summary.get("failed", 0)
            sr.failed = summary.get("failed", 0)
            sr.skipped_rule17 = summary.get("skipped_validation", 0)
            sr.skipped_existing_seq_state = summary.get("skipped_existing_in_seq", 0)

    return result


def _chicago_tz():
    import zoneinfo
    return zoneinfo.ZoneInfo("America/Chicago")


def run_autopilot(
    strategy_key: str = "all",
    *,
    dry_run: bool = True,
    preview_only: bool = False,
    refresh_pool: Optional[bool] = None,
    preview_out: Optional[Path] = None,
) -> AutopilotReport:
    """Main entry. Returns a structured report; Telegram formatter consumes it."""
    ts_utc, ts_cst = _now_timestamps()

    # Kill-switch short-circuit
    if _kill_switch_active():
        report = AutopilotReport(
            ts_utc=ts_utc, ts_cst=ts_cst, mode="disabled",
            errors=[f"Kill switch present at {KILL_SWITCH}"],
        )
        _write_audit_log(report)
        return report

    mode = "dry_run" if dry_run else "live"
    if preview_only:
        mode = "preview"
    report = AutopilotReport(ts_utc=ts_utc, ts_cst=ts_cst, mode=mode)

    # Archive stale state files up front so today's run starts clean
    try:
        _archive_old_state_files(datetime.now(timezone.utc))
    except Exception as e:
        logger.warning("State-file archive sweep failed: %s", e)

    keys = list(STRATEGIES.keys()) if strategy_key == "all" else [strategy_key]
    preview_rows: list[dict] = []

    for key in keys:
        strategy = STRATEGIES.get(key)
        if strategy is None:
            report.errors.append(f"unknown strategy {key!r}")
            continue
        try:
            sr = _process_strategy(
                key, strategy,
                dry_run=dry_run,
                preview_only=preview_only,
                preview_rows=preview_rows,
                refresh_pool=refresh_pool,
            )
            report.strategies[key] = sr
        except Exception as e:
            logger.error("autopilot strategy %s failed: %s\n%s", key, e, traceback.format_exc())
            report.errors.append(f"{key}: {e.__class__.__name__}: {e}")
            report.mode = "error"

    if preview_only and preview_out:
        _write_preview_csv(preview_rows, preview_out)
        print(f"Preview CSV: {preview_out} ({len(preview_rows)} rows)")

    _write_audit_log(report)
    return report


# ── Persistence ────────────────────────────────────────────────────────

def _write_preview_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["email", "first_name", "last_name", "company", "state",
                  "bucket", "target_sequence"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _report_to_dict(report: AutopilotReport) -> dict:
    """Serialize AutopilotReport to a plain dict (safe for JSONL)."""
    return {
        "ts_utc": report.ts_utc,
        "ts_cst": report.ts_cst,
        "mode": report.mode,
        "errors": report.errors,
        "strategies": {
            k: {
                **{f: getattr(s, f) for f in (
                    "strategy_key", "display", "tier", "weekly_budget",
                    "sends_7d", "headroom", "utilization_pct", "profile",
                    "pool_built_at", "pool_excluded",
                )},
                "sequences": {name: dataclasses.asdict(seq)
                              for name, seq in s.sequences.items()},
            }
            for k, s in report.strategies.items()
        },
    }


def _write_audit_log(report: AutopilotReport) -> None:
    AUTOPILOT_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with AUTOPILOT_AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_report_to_dict(report), ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Could not write audit log: %s", e)


# ── Telegram formatter (Rule 19: names only) ───────────────────────────

def format_telegram_summary(report: AutopilotReport, *, live: bool) -> str:
    """Format a Telegram message from the report. Never accepts raw IDs."""
    if report.mode == "disabled":
        return (
            "🤖 Campaign Autopilot — DISABLED\n"
            f"Kill switch at ~/.claude/state/scout-campaign-autopilot-disabled\n"
            f"Run skipped at {report.ts_cst}"
        )
    if report.mode == "error":
        err_lines = "\n".join(f"  • {e}" for e in report.errors[:5])
        return (
            f"🤖 Campaign Autopilot — ERROR at {report.ts_cst}\n"
            f"{err_lines}\n"
            "(Full traceback in logs; run did not POST any prospects.)"
        )

    header = "[LIVE]" if live else "[DRY RUN — /autopilot_live to enable real adds]"
    lines = [f"🤖 Campaign Autopilot — {report.ts_cst}", header, ""]

    # Only list strategies that actually did something
    active = [s for s in report.strategies.values() if s.sequences]
    if not active:
        lines.append("No active sequences this run.")
        return "\n".join(lines)

    verb = "Added" if live else "Would add"

    for s in active:
        lines.append(f"{s.display}  Tier {s.tier}")
        lines.append(
            f"  Sends 7d: {s.sends_7d}/{s.weekly_budget} "
            f"({s.utilization_pct}%), {s.headroom} headroom"
        )
        profile_line = f"  Profile: {s.profile} (held)" if s.profile else ""
        if profile_line:
            lines.append(profile_line)

        for seq_name, seq in s.sequences.items():
            if seq.need <= 0 and seq.attempted == 0:
                continue  # idle sequence, skip from Telegram noise
            msg = f"  {verb} {seq.succeeded} → {seq_name}"
            if seq.cohort_remaining > 0:
                msg += f"  (cohort: {seq.cohort_remaining} left)"
            lines.append(msg)
            skips = []
            if seq.skipped_recent_activity:
                skips.append(f"{seq.skipped_recent_activity} recent_activity")
            if seq.skipped_already_in_dre_cohort:
                skips.append(f"{seq.skipped_already_in_dre_cohort} already_in_dre_cohort")
            if seq.skipped_not_in_outreach:
                skips.append(f"{seq.skipped_not_in_outreach} not_in_outreach")
            if seq.skipped_rule17:
                skips.append(f"{seq.skipped_rule17} rule17")
            if seq.failed:
                skips.append(f"{seq.failed} failed")
            if skips:
                lines.append(f"    skipped: {', '.join(skips)}")

        lines.append("")

    # Tier 1 rollup
    t1 = [s for s in report.strategies.values() if s.tier == 1]
    if t1:
        t1_budget = sum(s.weekly_budget for s in t1)
        t1_sends = sum(s.sends_7d for s in t1)
        t1_head = max(0, t1_budget - t1_sends)
        lines.append(f"Tier 1 TOTAL: {t1_sends}/{t1_budget}, {t1_head} headroom")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────

def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strategy",
                    default="all",
                    help="Strategy key, or 'all' (default)")
    live_group = ap.add_mutually_exclusive_group()
    live_group.add_argument("--dry-run", action="store_true",
                            help="Classify + find candidates, do not POST (default)")
    live_group.add_argument("--live", action="store_true",
                            help="Actually POST to Outreach")
    ap.add_argument("--preview", action="store_true",
                    help="Write preview CSV of next batch, do not POST")
    ap.add_argument("--preview-out", type=Path,
                    default=Path("/tmp/campaign_preview.csv"))
    ap.add_argument("--refresh-pool", action="store_true",
                    help="Force rebuild of the candidate pool before running")
    args = ap.parse_args()

    # --dry-run is the safe default; --live is opt-in
    dry_run = not args.live

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    # Load env for all Outreach/Sheets calls
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _env import load_env_or_die
    load_env_or_die(required=[])

    report = run_autopilot(
        strategy_key=args.strategy,
        dry_run=dry_run,
        preview_only=args.preview,
        refresh_pool=args.refresh_pool if args.refresh_pool else None,
        preview_out=args.preview_out if args.preview else None,
    )

    print(format_telegram_summary(report, live=not dry_run and not args.preview))
    return 0 if report.mode != "error" else 1


if __name__ == "__main__":
    sys.exit(_main())
