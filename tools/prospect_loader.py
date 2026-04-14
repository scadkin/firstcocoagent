"""
prospect_loader.py — reusable bulk loader for Outreach prospects + sequences.

The canonical home for the "take a list of contacts, push them into an
Outreach sequence, stagger the POSTs, persist state so we can resume" flow.
First caller is scripts/diocesan_drip.py; future callers include C4
re-engagement, signal-to-sequence auto-flows, and any Telegram `/drip_*`
command.

Design constraints:
  - Resumable: state file written after every successful POST. Rerunning is
    idempotent — already-done contacts are skipped by status, already-existing
    Outreach prospects are reused by email.
  - Safe: pre-flight verifies target sequences are still `enabled` before
    every write (Session 38 lesson: adding to paused sequence goes in paused).
  - Honest about cost: every POST is a real Outreach API write; caller controls
    sleep cadence + dry-run mode.
  - Rule 17 enforced: timezone is populated for every contact via
    timezone_lookup.state_to_timezone. Contacts without state are skipped,
    logged, and counted — never papered over.
"""
from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from typing import Callable
from zoneinfo import ZoneInfo

from tools.outreach_client import (
    _api_get,  # read-only helper, used for sequence-enabled preflight
    validate_prospect_inputs,
    create_prospect,
    find_prospect_by_email,
    add_prospect_to_sequence,
)
from tools.timezone_lookup import state_to_timezone

logger = logging.getLogger(__name__)

# Confidence rank — higher is better. Used for VERIFIED-first ordering.
_CONFIDENCE_RANK = {
    "VERIFIED": 3,
    "LIKELY": 2,
    "INFERRED": 1,
    "UNKNOWN": 0,
    "": 0,
}


@dataclass
class Contact:
    """One prospect to load. Must carry enough fields for validate_prospect_inputs."""
    first_name: str
    last_name: str
    email: str
    title: str
    company: str
    state: str
    email_confidence: str
    diocese_or_group: str  # For logging / tagging / routing (e.g., "Philadelphia")

    def key(self) -> str:
        """Stable identity: lowercased email. Used as state-file key."""
        return self.email.strip().lower()

    def confidence_rank(self) -> int:
        return _CONFIDENCE_RANK.get((self.email_confidence or "").upper(), 0)


@dataclass
class LoadPlan:
    """One contact assigned to one sequence on one day with one tag set."""
    contact: Contact
    sequence_id: int
    mailbox_id: int
    tags: list[str]
    day_bucket: str  # ISO date string, e.g. '2026-04-13'
    status: str = "pending"  # pending | done | skipped | failed
    prospect_id: str | None = None
    sequence_state_id: str | None = None
    error: str | None = None
    updated_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["contact"] = asdict(self.contact)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LoadPlan":
        contact_data = d["contact"]
        contact = Contact(**contact_data)
        return cls(
            contact=contact,
            sequence_id=d["sequence_id"],
            mailbox_id=d["mailbox_id"],
            tags=list(d.get("tags") or []),
            day_bucket=d["day_bucket"],
            status=d.get("status", "pending"),
            prospect_id=d.get("prospect_id"),
            sequence_state_id=d.get("sequence_state_id"),
            error=d.get("error"),
            updated_at=d.get("updated_at", ""),
        )


# ─────────────────────────────────────────────
# Planning
# ─────────────────────────────────────────────

def build_load_plan(
    contacts: list[Contact],
    sequence_id_for: Callable[[Contact], int],
    *,
    days: list[str],
    mailbox_id: int = 11,
    tags_for: Callable[[Contact], list[str]] | None = None,
    group_key: Callable[[Contact], str] = lambda c: c.diocese_or_group,
) -> list[LoadPlan]:
    """
    Round-robin assign contacts across `days`, VERIFIED first within each
    group. Deterministic on re-run: same input → same assignment.

    Strategy:
      1. Bucket contacts by group_key (e.g., diocese name).
      2. Within each group, sort by (-confidence_rank, email) so VERIFIED
         lands first and ties break deterministically.
      3. Iterate groups in sorted key order. From each group, pop one contact
         at a time round-robin across days. Day index advances mod len(days).
      4. Emit LoadPlan records with contact's sequence_id and tags.

    Result: every day touches multiple groups, VERIFIED contacts land in
    earlier days, re-running with the same input produces byte-for-byte
    the same output list.
    """
    if not days:
        raise ValueError("days must be non-empty")
    if not contacts:
        return []

    if tags_for is None:
        tags_for = lambda c: []  # noqa: E731

    # Bucket by group
    groups: dict[str, list[Contact]] = {}
    for c in contacts:
        groups.setdefault(group_key(c), []).append(c)

    # Sort each group deterministically: VERIFIED first, then by email
    for key in groups:
        groups[key].sort(key=lambda c: (-c.confidence_rank(), c.email.lower()))

    # Assignment: each diocese rotates its OWN contacts through the day list,
    # so within any single day you see a mix of dioceses and within any single
    # diocese the contacts are spread across all days. Day N within a diocese
    # takes contacts [N, N+len(days), N+2*len(days), ...] from that diocese's
    # sorted list. That gives two properties at once:
    #   (a) every day touches every diocese that has enough contacts
    #   (b) VERIFIED contacts (which sort first) land in earlier days
    sorted_group_keys = sorted(groups.keys())
    plans: list[LoadPlan] = []

    for key in sorted_group_keys:
        group_contacts = groups[key]
        for i, contact in enumerate(group_contacts):
            day = days[i % len(days)]
            plans.append(LoadPlan(
                contact=contact,
                sequence_id=sequence_id_for(contact),
                mailbox_id=mailbox_id,
                tags=tags_for(contact),
                day_bucket=day,
            ))

    # Sort the final list by day so Batch 1 / Batch 2 reads cleanly in the
    # state file, then by diocese (for stable diff) and email (for determinism).
    plans.sort(key=lambda p: (p.day_bucket, p.contact.diocese_or_group, p.contact.email.lower()))

    return plans


# ─────────────────────────────────────────────
# State file I/O (atomic)
# ─────────────────────────────────────────────

def write_state_atomic(path: str, plans: list[LoadPlan]) -> None:
    """Write state file atomically: tmp + fsync + rename."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_path = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(
                {"plans": [p.to_dict() for p in plans]},
                f,
                indent=2,
                default=str,
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def read_state(path: str) -> list[LoadPlan]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return [LoadPlan.from_dict(d) for d in data.get("plans", [])]


def append_audit(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record_with_time = {"timestamp": datetime.now().isoformat(timespec="seconds"), **record}
    with open(path, "a") as f:
        f.write(json.dumps(record_with_time, default=str) + "\n")


# ─────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────

def _sequence_is_enabled(sequence_id: int | str) -> bool:
    """
    Pre-flight: GET /sequences/<id> and check attributes.enabled.
    Returns False if the sequence is paused, deleted, or unreadable.
    Session 38 lesson: adding prospects to a paused sequence makes them
    land as paused sequenceStates.
    """
    try:
        result = _api_get(f"/sequences/{sequence_id}")
    except Exception as e:
        logger.warning(f"  sequence {sequence_id} preflight read error: {e}")
        return False
    attrs = result.get("data", {}).get("attributes", {}) or {}
    return bool(attrs.get("enabled", False))


def _sleep_jittered(min_seconds: int, max_seconds: int) -> None:
    if max_seconds <= 0 or min_seconds < 0:
        return
    gap = random.randint(min_seconds, max_seconds)
    logger.info(f"  sleeping {gap}s before next POST")
    time.sleep(gap)


def execute_load_plan(
    plans: list[LoadPlan],
    *,
    state_path: str,
    audit_path: str,
    target_day: str | None = None,
    sleep_seconds: tuple[int, int] = (300, 900),  # 5-15 min uniform random
    verify_sequence_active: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Process the subset of `plans` whose day_bucket matches target_day (or all
    pending plans if target_day is None). For each plan:

      1. Check status — skip if already done/skipped/failed.
      2. Verify target sequence is enabled — skip with reason if paused.
      3. find_prospect_by_email → if exists, reuse prospect_id.
      4. Else validate_prospect_inputs (re-verify, cheap) → create_prospect.
      5. add_prospect_to_sequence.
      6. Update plan status + IDs, write state file (atomic), append audit.
      7. Sleep jittered `sleep_seconds` gap before next contact.

    Returns a summary dict with counts + per-plan outcomes.
    State file is rewritten after EVERY POST for resumability.
    """
    if target_day is None:
        target_day = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()

    today_plans = [p for p in plans if p.day_bucket == target_day]
    remaining = [p for p in today_plans if p.status == "pending"]

    summary = {
        "target_day": target_day,
        "total_for_day": len(today_plans),
        "already_done": len(today_plans) - len(remaining),
        "processed": 0,
        "created": 0,
        "existing_reused": 0,
        "skipped_sequence_paused": 0,
        "skipped_validation": 0,
        "skipped_existing_in_seq": 0,
        "failed": 0,
        "dry_run": dry_run,
    }

    if not remaining:
        logger.info(f"execute_load_plan: no pending plans for {target_day} (all {len(today_plans)} already done)")
        return summary

    logger.info(
        f"execute_load_plan: {len(remaining)} pending / {len(today_plans)} total for {target_day} "
        f"(dry_run={dry_run})"
    )

    # Cache sequence-enabled status per sequence to avoid repeat reads
    seq_enabled_cache: dict[str, bool] = {}

    for plan in remaining:
        contact = plan.contact
        plan.updated_at = datetime.now().isoformat(timespec="seconds")
        email_clean = contact.email.strip().lower()

        logger.info(
            f"[{contact.diocese_or_group}] {contact.first_name} {contact.last_name} "
            f"<{email_clean}> -> seq {plan.sequence_id}"
        )

        if dry_run:
            logger.info("  dry_run: would POST")
            summary["processed"] += 1
            continue

        # ── Preflight: sequence enabled? ─────────────────────────────
        if verify_sequence_active:
            seq_key = str(plan.sequence_id)
            if seq_key not in seq_enabled_cache:
                seq_enabled_cache[seq_key] = _sequence_is_enabled(plan.sequence_id)
            if not seq_enabled_cache[seq_key]:
                plan.status = "skipped"
                plan.error = "sequence_not_enabled"
                summary["skipped_sequence_paused"] += 1
                append_audit(audit_path, {"event": "skipped_sequence_paused", "plan": plan.to_dict()})
                write_state_atomic(state_path, plans)
                logger.warning(f"  sequence {plan.sequence_id} is not enabled — skipping contact")
                continue

        # ── Dedup: find existing prospect by email ───────────────────
        existing = find_prospect_by_email(email_clean)
        if existing and existing.get("prospect_id"):
            plan.prospect_id = existing["prospect_id"]
            logger.info(f"  reusing existing prospect {plan.prospect_id}")
            summary["existing_reused"] += 1
        else:
            # ── Create prospect (runs validator internally) ──────────
            result = create_prospect(
                first_name=contact.first_name,
                last_name=contact.last_name,
                email=email_clean,
                title=contact.title,
                company=contact.company,
                state=contact.state,
                timezone=state_to_timezone(contact.state) or "",
                tags=plan.tags,
                owner_id=11,
            )
            if "error" in result:
                plan.status = "failed" if result["error"] != "prospect_validation_failed" else "skipped"
                plan.error = result.get("error") + " " + str(result.get("validation_failures", []))
                append_audit(audit_path, {"event": "create_prospect_failed", "result": result, "plan": plan.to_dict()})
                write_state_atomic(state_path, plans)
                if result["error"] == "prospect_validation_failed":
                    summary["skipped_validation"] += 1
                else:
                    summary["failed"] += 1
                logger.warning(f"  create_prospect failed: {result.get('error')} / {result.get('validation_failures')}")
                continue
            plan.prospect_id = result["prospect_id"]
            summary["created"] += 1
            logger.info(f"  created prospect {plan.prospect_id}")

        # ── Dedup: already in this sequence? ─────────────────────────
        # Outreach will happily accept duplicate sequenceStates; we avoid
        # re-adding by checking the existing prospect's membership in the
        # target sequence via the dedicated filter call.
        already_in_seq = False
        try:
            states_check = _api_get(
                "/sequenceStates",
                {
                    "filter[sequence][id]": str(plan.sequence_id),
                    "filter[prospect][id]": str(plan.prospect_id),
                    "page[size]": "1",
                },
            )
            if states_check.get("data"):
                already_in_seq = True
        except Exception as e:
            logger.warning(f"  membership check error (continuing): {e}")

        if already_in_seq:
            plan.status = "skipped"
            plan.error = "already_in_sequence"
            summary["skipped_existing_in_seq"] += 1
            append_audit(audit_path, {"event": "skipped_already_in_sequence", "plan": plan.to_dict()})
            write_state_atomic(state_path, plans)
            logger.info(f"  already in seq {plan.sequence_id} — skipping add")
            continue

        # ── Add to sequence ──────────────────────────────────────────
        add_result = add_prospect_to_sequence(
            prospect_id=plan.prospect_id,
            sequence_id=plan.sequence_id,
            mailbox_id=plan.mailbox_id,
        )
        if "error" in add_result:
            plan.status = "failed"
            plan.error = add_result["error"]
            summary["failed"] += 1
            append_audit(audit_path, {"event": "add_to_sequence_failed", "result": add_result, "plan": plan.to_dict()})
            write_state_atomic(state_path, plans)
            logger.warning(f"  add_prospect_to_sequence failed: {add_result['error']}")
            continue

        plan.sequence_state_id = add_result["sequence_state_id"]
        plan.status = "done"
        plan.updated_at = datetime.now().isoformat(timespec="seconds")
        summary["processed"] += 1
        append_audit(audit_path, {"event": "posted", "plan": plan.to_dict()})
        write_state_atomic(state_path, plans)
        logger.info(f"  done: sequenceState {plan.sequence_state_id}")

        # ── Stagger sleep between POSTs ──────────────────────────────
        # Skip sleep after the last contact of the day (no next POST to pace)
        if plan is not remaining[-1]:
            _sleep_jittered(*sleep_seconds)

    logger.info(f"execute_load_plan summary: {summary}")
    return summary
