"""
Unit tests for tools/campaign_pool.py — persistence + Rule 17 tagging.

Does not hit the live Sheets API — exercises _write_pool / load_pool
round-trip and pool_age_days on a hand-built StrategyPool.

Run: .venv/bin/python scripts/test_campaign_pool.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import tools.campaign_pool as cp  # noqa: E402
from tools.campaign_pool import PoolLead, StrategyPool  # noqa: E402

_passed = 0
_failed: list[str] = []


def check(label: str, got, expected) -> None:
    global _passed
    if got == expected:
        _passed += 1
    else:
        _failed.append(f"FAIL {label}: got {got!r}, expected {expected!r}")


def make_lead(i: int, bucket: str) -> PoolLead:
    return PoolLead(
        first_name=f"F{i}", last_name=f"L{i}", email=f"u{i}@ex.com",
        title="", company=f"School {i}",
        state="TX", email_confidence="VERIFIED",
        diocese_or_group=bucket,
        bucket=bucket, tz="America/Chicago",
        source_row_id=f"u{i}@ex.com",
    )


def test_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_dir = cp.POOL_DIR
        cp.POOL_DIR = Path(tmpdir)
        try:
            pool = StrategyPool(
                strategy_key="test",
                built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                total_rows_scanned=100,
                total_eligible=3,
                excluded={"no_state": 5, "parked_no_source_match": 92},
            )
            pool.buckets["TC-MS"] = [make_lead(1, "TC-MS"), make_lead(2, "TC-MS")]
            pool.buckets["LIB"] = [make_lead(3, "LIB")]

            cp._write_pool(pool)

            # Verify files present
            check("jsonl exists", cp._pool_path("test").exists(), True)
            check("meta exists", cp._meta_path("test").exists(), True)

            # Line count = total leads
            with cp._pool_path("test").open() as f:
                lines = [l for l in f if l.strip()]
            check("jsonl line count", len(lines), 3)

            # Load and verify
            loaded = cp.load_pool("test")
            check("loaded key", loaded.strategy_key, "test")
            check("loaded total_eligible", loaded.total_eligible, 3)
            check("loaded excluded", loaded.excluded["no_state"], 5)
            check("loaded TC-MS count", len(loaded.buckets["TC-MS"]), 2)
            check("loaded LIB count", len(loaded.buckets["LIB"]), 1)
            first = loaded.buckets["TC-MS"][0]
            check("loaded lead email", first.email, "u1@ex.com")
            check("loaded lead state", first.state, "TX")
            check("loaded lead tz", first.tz, "America/Chicago")
            check("loaded lead bucket", first.bucket, "TC-MS")
        finally:
            cp.POOL_DIR = orig_dir


def test_age() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_dir = cp.POOL_DIR
        cp.POOL_DIR = Path(tmpdir)
        try:
            # No pool yet
            check("age missing returns None", cp.pool_age_days("test"), None)

            # Fresh pool
            pool = StrategyPool(
                strategy_key="test",
                built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            pool.buckets["TC-MS"] = []
            cp._write_pool(pool)
            age = cp.pool_age_days("test")
            check("age fresh is small", age is not None and age < 0.01, True)

            # Backdate by hand
            meta_path = cp._meta_path("test")
            meta = json.loads(meta_path.read_text())
            meta["built_at"] = (
                datetime.now(timezone.utc) - timedelta(days=10)
            ).isoformat(timespec="seconds")
            meta_path.write_text(json.dumps(meta))
            age_old = cp.pool_age_days("test")
            check("age older than max", age_old is not None and age_old > cp.POOL_MAX_AGE_DAYS, True)
        finally:
            cp.POOL_DIR = orig_dir


def main() -> int:
    test_roundtrip()
    test_age()
    print(f"Passed: {_passed}")
    if _failed:
        for line in _failed:
            print(line)
        print(f"Failed: {len(_failed)}")
        return 1
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
