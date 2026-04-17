#!/usr/bin/env python3
"""
campaign_budget_status.py — strategy-agnostic rolling-7-day budget reporter.

Read-only. Computes actual rolling-7-day send count per sequence via the
Outreach /mailings endpoint, aggregates per strategy, and reports usage
against the per-strategy weekly budget from the S66 prioritization plan.

Designed to generalize to all 24 prospecting strategies as their sequences
come online. The STRATEGIES dict below is the authoritative config — add
new strategies there, not in code.

Usage:
    scripts/campaign_budget_status.py                    # all strategies
    scripts/campaign_budget_status.py --strategy dre     # just DRE
    scripts/campaign_budget_status.py --format json      # machine-readable

Scheduled runs (next session work): Scout cron at 7am or 5pm CST daily.

No writes. To act on suggestions, call the upcoming auto-rebalancer or
set throttles manually via scripts/create_dre_sequences.py
--configure-throttles.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _env import load_env_or_die  # noqa: E402

load_env_or_die(required=[
    "OUTREACH_CLIENT_ID",
    "OUTREACH_CLIENT_SECRET",
    "OUTREACH_REDIRECT_URI",
])

from tools.outreach_client import _api_get_all, _api_get  # noqa: E402
from tools.campaign_config import STRATEGIES, resolve_sequence_ids  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("budget_status")


# ── Rolling-7-day mailings count per sequence ────────────────────────────

def count_rolling_7d_mailings(seq_id: int) -> int:
    """Count mailings created in the last 7 days for a sequence.

    Uses GET /mailings?filter[sequence][id]=X&filter[createdAt]=>ISO. Only
    counts mailings with a non-null deliveredAt (actual sends; skips
    pending/failed). Adjust in one place if that definition evolves.
    """
    # Outreach JSON:API filter syntax for datetime ranges: `FROM..TO` inclusive,
    # trailing `..` means "open end" = "since FROM".
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    iso_from = seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    iso_to = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "filter[sequence][id]": str(seq_id),
        "filter[createdAt]": f"{iso_from}..{iso_to}",
        "page[size]": "100",
    }
    mailings = _api_get_all("/mailings", params, max_pages=20)
    # Count only delivered (actual sends), not pending/failed.
    return sum(1 for m in mailings if m.get("attributes", {}).get("deliveredAt"))


def get_sequence_meta(seq_id: int) -> dict:
    """Return {'name', 'enabled', 'throttle_per_day'} for a sequence."""
    try:
        r = _api_get(f"/sequences/{seq_id}")
    except Exception as e:
        logger.warning(f"  get /sequences/{seq_id} failed: {e}")
        return {"name": f"seq {seq_id}", "enabled": None, "throttle_per_day": None}
    attrs = r.get("data", {}).get("attributes", {})
    return {
        "name": attrs.get("name", f"seq {seq_id}"),
        "enabled": attrs.get("enabled"),
        "throttle_per_day": attrs.get("throttleMaxAddsPerDay"),
    }


# ── Strategy-level report ────────────────────────────────────────────────

def build_strategy_report(key: str, strategy: dict) -> dict:
    seq_ids = resolve_sequence_ids(strategy)
    report = {
        "key": key,
        "number": strategy["number"],
        "display": strategy["display"],
        "tier": strategy["tier"],
        "weekly_budget": strategy["weekly_budget"],
        "rolling_7d_sends": 0,
        "headroom": strategy["weekly_budget"],
        "utilization_pct": 0.0,
        "sequence_count": len(seq_ids),
        "sequences": [],
    }
    if not seq_ids:
        report["note"] = "no sequences configured yet"
        return report

    for seq_id in seq_ids:
        meta = get_sequence_meta(seq_id)
        sends = count_rolling_7d_mailings(seq_id)
        report["sequences"].append({
            "id": seq_id,
            "name": meta["name"],
            "enabled": meta["enabled"],
            "throttle_per_day": meta["throttle_per_day"],
            "rolling_7d_sends": sends,
        })
        report["rolling_7d_sends"] += sends

    report["headroom"] = max(0, strategy["weekly_budget"] - report["rolling_7d_sends"])
    report["utilization_pct"] = round(
        100.0 * report["rolling_7d_sends"] / strategy["weekly_budget"], 1
    )
    return report


# ── Output ───────────────────────────────────────────────────────────────

def print_text_report(reports: list[dict]) -> None:
    print(f"Campaign budget status — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print("Rolling 7-day window. Budget per S66 prioritization plan.")
    print("=" * 78)
    for r in reports:
        print()
        print(f"  [#{r['number']:>2}] {r['display']}  (Tier {r['tier']})")
        print(f"       Weekly budget:       {r['weekly_budget']:>4}")
        print(f"       Rolling 7d sends:    {r['rolling_7d_sends']:>4}  ({r['utilization_pct']}%)")
        print(f"       Headroom:            {r['headroom']:>4}")
        print(f"       Sequences:           {r['sequence_count']}")
        if r.get("note"):
            print(f"       Note: {r['note']}")
        if r.get("sequences"):
            for s in r["sequences"]:
                en = "ON " if s["enabled"] else "OFF"
                throttle = s["throttle_per_day"] if s["throttle_per_day"] is not None else "?"
                name = s["name"][:48]
                print(f"         {en}  throttle={throttle:>3}/day  sends_7d={s['rolling_7d_sends']:>3}  {name}")

    # Tier 1 summary (the governed-together set)
    tier1 = [r for r in reports if r["tier"] == 1]
    if tier1:
        t1_budget = sum(r["weekly_budget"] for r in tier1)
        t1_sends = sum(r["rolling_7d_sends"] for r in tier1)
        t1_head = max(0, t1_budget - t1_sends)
        print()
        print("=" * 78)
        print(f"  Tier 1 TOTAL: {t1_sends:>4} / {t1_budget:>4} sends "
              f"({round(100*t1_sends/t1_budget,1) if t1_budget else 0}%), "
              f"{t1_head} headroom")
        print()
        print("  Suggestions:")
        for r in tier1:
            if r["headroom"] > 50 and r.get("sequences"):
                paused = [s for s in r["sequences"] if (s["throttle_per_day"] or 0) == 0]
                if paused:
                    print(f"    #{r['number']} has {r['headroom']} headroom; "
                          f"{len(paused)} paused sequence(s) could be opened")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strategy", choices=list(STRATEGIES.keys()),
                    help="Report on a single strategy only")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    keys = [args.strategy] if args.strategy else list(STRATEGIES.keys())
    reports = [build_strategy_report(k, STRATEGIES[k]) for k in keys]

    if args.format == "json":
        print(json.dumps(reports, indent=2, default=str))
    else:
        print_text_report(reports)

    return 0


if __name__ == "__main__":
    sys.exit(main())
