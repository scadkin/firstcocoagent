"""
build_campaign_pool.py — one-shot pool rebuild CLI.

Wraps tools.campaign_pool.build_pool for manual refreshes outside the
autopilot's Monday scheduled rebuild. Safe to re-run — replaces the
existing on-disk pool atomically.

Usage:
    .venv/bin/python scripts/build_campaign_pool.py --strategy dre
    .venv/bin/python scripts/build_campaign_pool.py --strategy dre --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _env import load_env_or_die  # noqa: E402

load_env_or_die(required=[])

from tools.campaign_config import STRATEGIES  # noqa: E402
from tools.campaign_pool import build_pool, pool_age_days  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--strategy",
        required=True,
        choices=[k for k, s in STRATEGIES.items() if s.get("pool_source")],
        help="Strategy key to rebuild (only strategies with a pool_source listed)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify + count, but do not write JSONL to disk",
    )
    args = ap.parse_args()

    if args.dry_run:
        print("Dry run: classifying without persisting.")
        from tools.lead_filters import classify_sf_leads_to_dre_buckets
        classification = classify_sf_leads_to_dre_buckets()
        print(f"Scanned: {classification.total_rows_scanned}")
        print(f"Matched: {classification.total_matched}")
        print("Cohort sizes:")
        for c, rows in sorted(classification.buckets.items(), key=lambda kv: -len(kv[1])):
            print(f"  {c:<26} {len(rows):>6}")
        print("Excluded:")
        for reason, n in sorted(classification.excluded.items(), key=lambda kv: -kv[1]):
            print(f"  {reason:<38} {n:>6}")
        return 0

    age = pool_age_days(args.strategy)
    if age is not None:
        print(f"Existing pool age: {age:.1f} days — will overwrite.")
    pool = build_pool(args.strategy)

    print(f"Built pool for {args.strategy} at {pool.built_at}")
    print(f"Scanned: {pool.total_rows_scanned}, Eligible: {pool.total_eligible}")
    print("Cohort sizes:")
    for c, n in sorted(pool.cohort_sizes().items(), key=lambda kv: -kv[1]):
        print(f"  {c:<26} {n:>6}")
    print("Excluded:")
    for reason, n in sorted(pool.excluded.items(), key=lambda kv: -kv[1]):
        print(f"  {reason:<38} {n:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
