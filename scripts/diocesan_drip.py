"""
diocesan_drip.py — thin CLI for the diocesan drip load.

Pulls diocesan central-office contacts from the Leads tab, filters to the
6 target dioceses (sequences 2008-2013), excludes 3 known-broken rows,
timezone-enriches via state_to_timezone, and calls tools.prospect_loader
to round-robin assign + execute.

All heavy lifting lives in tools/prospect_loader.py — this file is just a
CLI wrapper with 5 subcommands: --assign, --dry-run, --canary,
--canary-cleanup, --execute, --verify.

Usage examples:
    .venv/bin/python scripts/diocesan_drip.py --assign
    .venv/bin/python scripts/diocesan_drip.py --dry-run
    .venv/bin/python scripts/diocesan_drip.py --canary
    .venv/bin/python scripts/diocesan_drip.py --canary-cleanup 123456 789012
    .venv/bin/python scripts/diocesan_drip.py --execute
    .venv/bin/python scripts/diocesan_drip.py --execute --force-day 2026-04-14
    .venv/bin/python scripts/diocesan_drip.py --verify
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import tools.sheets_writer as sheets_writer  # noqa: E402
from tools.outreach_client import (  # noqa: E402
    create_prospect,
    add_prospect_to_sequence,
    get_sequence_states,
    _api_post,
    _api_get,
)
from tools.prospect_loader import (  # noqa: E402
    Contact,
    LoadPlan,
    build_load_plan,
    execute_load_plan,
    read_state,
    write_state_atomic,
)
from tools.timezone_lookup import state_to_timezone  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("diocesan_drip")

# ─────────────────────────────────────────────
# Diocesan targets
# ─────────────────────────────────────────────

DIOCESE_TO_SEQUENCE: dict[str, int] = {
    "Archdiocese of Philadelphia": 2008,
    "Archdiocese of Cincinnati":   2009,
    "Archdiocese of Detroit":      2010,
    "Diocese of Cleveland":        2011,
    "Archdiocese of Boston":       2012,
    "Archdiocese of Chicago":      2013,
}

# Excluded rows — known-broken email addresses that will hard-bounce.
# Stored as lowercased emails for exact-match filtering.
EXCLUDED_EMAILS: set[str] = {
    "[email protected]",  # literal template placeholder in the sheet
    "co'brien@catholicaoc.org",  # apostrophe local-part — SMTP reject
    "do'brien@catholicaoc.org",  # duplicate O'Brien with different pattern
}

# Drip schedule: 4 consecutive business days starting today
DRIP_DAYS: list[str] = [
    "2026-04-13",  # Mon — Batch 1
    "2026-04-14",  # Tue — Batch 2
    "2026-04-15",  # Wed — Batch 3
    "2026-04-16",  # Thu — Batch 4
]

STATE_PATH = os.path.join(os.path.dirname(_HERE), "data", "diocesan_drip_state.json")
AUDIT_PATH = os.path.join(os.path.dirname(_HERE), "data", "diocesan_drip_audit.jsonl")

MAILBOX_ID = 11


# ─────────────────────────────────────────────
# Lead loading + filtering
# ─────────────────────────────────────────────

def _match_diocese(district_name: str) -> str | None:
    """Return the canonical diocese key if this district name matches one of
    our 6 targets, else None."""
    if not district_name:
        return None
    lower = district_name.lower()
    for canonical in DIOCESE_TO_SEQUENCE.keys():
        if canonical.lower() in lower:
            return canonical
    return None


def _lead_to_contact(lead: dict, diocese: str) -> Contact | None:
    """Convert a Leads-tab dict to a Contact. Returns None if the contact
    is missing required fields or is in the exclusion list."""
    email = (lead.get("Email") or "").strip().lower()
    if not email:
        return None
    if email in EXCLUDED_EMAILS:
        logger.info(f"  excluded (broken email): {email}")
        return None
    first = (lead.get("First Name") or "").strip()
    last = (lead.get("Last Name") or "").strip()
    if not first or not last:
        return None
    title = (lead.get("Title") or "").strip()
    company = (lead.get("Account") or diocese).strip()
    state = (lead.get("State") or "").strip().upper()
    conf = (lead.get("Email Confidence") or "UNKNOWN").strip().upper()
    return Contact(
        first_name=first,
        last_name=last,
        email=email,
        title=title,
        company=company,
        state=state,
        email_confidence=conf,
        diocese_or_group=diocese,
    )


def load_diocesan_contacts() -> list[Contact]:
    """Pull Leads → filter to 6 dioceses → exclude broken rows → return Contact list."""
    leads = sheets_writer.get_leads()
    logger.info(f"  pulled {len(leads)} leads from sheet")
    contacts: list[Contact] = []
    for lead in leads:
        diocese = _match_diocese(lead.get("District Name") or "")
        if not diocese:
            continue
        contact = _lead_to_contact(lead, diocese)
        if contact is None:
            continue
        contacts.append(contact)
    logger.info(f"  {len(contacts)} diocesan contacts after filtering + exclusion")
    return contacts


# ─────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────

def cmd_assign() -> int:
    """Build the load plan from scratch and write the state file."""
    contacts = load_diocesan_contacts()
    if not contacts:
        logger.error("no diocesan contacts found — aborting assign")
        return 1

    def sequence_id_for(c: Contact) -> int:
        return DIOCESE_TO_SEQUENCE[c.diocese_or_group]

    def tags_for(c: Contact) -> list[str]:
        slug = c.diocese_or_group.lower().replace(" ", "-").replace("archdiocese-of-", "").replace("diocese-of-", "")
        return [
            "diocesan-drip-2026-04",
            f"diocesan-drip-{slug}",
        ]

    plans = build_load_plan(
        contacts,
        sequence_id_for=sequence_id_for,
        days=DRIP_DAYS,
        mailbox_id=MAILBOX_ID,
        tags_for=tags_for,
    )

    write_state_atomic(STATE_PATH, plans)

    # Summary
    per_day: dict[str, dict[str, int]] = {}
    for p in plans:
        bucket = per_day.setdefault(p.day_bucket, {})
        bucket[p.contact.diocese_or_group] = bucket.get(p.contact.diocese_or_group, 0) + 1

    print(f"\nAssigned {len(plans)} contacts across {len(DRIP_DAYS)} days\n")
    print(f"{'Date':<12}{'Total':>6}  Breakdown")
    print("-" * 60)
    for day in DRIP_DAYS:
        day_plans = [p for p in plans if p.day_bucket == day]
        breakdown = ", ".join(
            f"{k.split(' of ')[-1]}={v}" for k, v in sorted(per_day.get(day, {}).items())
        )
        print(f"{day:<12}{len(day_plans):>6}  {breakdown}")
    print(f"\nState file: {STATE_PATH}")
    return 0


def cmd_dry_run(target_day: str | None) -> int:
    """Print the plan for `target_day` (today by default) without posting."""
    plans = read_state(STATE_PATH)
    if not plans:
        logger.error(f"no state file at {STATE_PATH} — run --assign first")
        return 1

    day = target_day or datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    day_plans = [p for p in plans if p.day_bucket == day]
    pending = [p for p in day_plans if p.status == "pending"]

    print(f"\n=== Dry run for {day} ===\n")
    print(f"Total for day: {len(day_plans)}")
    print(f"Pending:       {len(pending)}")
    print(f"Already done:  {len(day_plans) - len(pending)}\n")

    if not pending:
        print("Nothing to do.")
        return 0

    print(f"{'#':>3}  {'Diocese':<32s} {'Name':<30s} {'Conf':<8s} {'Email'}")
    print("-" * 100)
    for i, p in enumerate(pending, 1):
        c = p.contact
        print(
            f"{i:>3}  {c.diocese_or_group:<32s} "
            f"{(c.first_name + ' ' + c.last_name)[:30]:<30s} "
            f"{c.email_confidence:<8s} {c.email}"
        )
    print()
    print(f"Tags on each: {pending[0].tags}")
    print(f"Mailbox: {MAILBOX_ID}")
    print(f"Target sequences: {sorted({p.sequence_id for p in pending})}")
    return 0


def cmd_canary() -> int:
    """One-shot: create throwaway prospect, add to Chicago seq 2013, print IDs."""
    ts = int(time.time())
    email = f"scout-canary-{ts}@codecombat.test"
    tags = ["scout-canary", "DELETE_ME"]

    print(f"\n=== Canary ===\n")
    print(f"Creating prospect {email}...")
    create_result = create_prospect(
        first_name="Scout",
        last_name="Canary",
        email=email,
        title="TEST — delete if seen",
        company="CodeCombat Test Fixture",
        state="IL",
        timezone="America/Chicago",
        tags=tags,
        owner_id=11,
    )
    if "error" in create_result:
        print(f"FAILED: {create_result}")
        return 1
    prospect_id = create_result["prospect_id"]
    print(f"  prospect_id = {prospect_id}")

    print(f"Adding to sequence 2013 (Chicago)...")
    add_result = add_prospect_to_sequence(
        prospect_id=prospect_id,
        sequence_id=2013,
        mailbox_id=MAILBOX_ID,
    )
    if "error" in add_result:
        print(f"FAILED: {add_result}")
        print(f"Prospect {prospect_id} was created. Run:")
        print(f"  .venv/bin/python scripts/diocesan_drip.py --canary-cleanup {prospect_id} 0")
        return 1
    ssid = add_result["sequence_state_id"]
    print(f"  sequence_state_id = {ssid}")

    print(f"\nCanary OK.")
    print(f"Verify in Outreach UI:")
    print(f"  - prospect {prospect_id} shows up with owner=11")
    print(f"  - tags include 'scout-canary' and 'DELETE_ME'")
    print(f"  - sequence 2013 has the new sequenceState {ssid}")
    print(f"\nWhen done, clean up with:")
    print(f"  .venv/bin/python scripts/diocesan_drip.py --canary-cleanup {prospect_id} {ssid}")
    return 0


def cmd_canary_cleanup(prospect_id: str, sequence_state_id: str) -> int:
    """Delete the canary sequenceState + prospect. Graceful on 403 (scope gap)."""
    print(f"\n=== Canary cleanup ===\n")

    # Try DELETE /sequenceStates/<id> first
    if sequence_state_id and sequence_state_id != "0":
        print(f"DELETE /sequenceStates/{sequence_state_id}...")
        try:
            import httpx
            from tools.outreach_client import _get_headers, API_BASE
            resp = httpx.delete(
                f"{API_BASE}/sequenceStates/{sequence_state_id}",
                headers=_get_headers(),
                timeout=30.0,
            )
            if resp.status_code in (200, 204):
                print(f"  deleted sequenceState {sequence_state_id}")
            elif resp.status_code == 403:
                print(f"  403 Forbidden — delete scope not granted. Remove manually in UI.")
            else:
                print(f"  {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  error: {e}")

    # Try DELETE /prospects/<id>
    if prospect_id:
        print(f"DELETE /prospects/{prospect_id}...")
        try:
            import httpx
            from tools.outreach_client import _get_headers, API_BASE
            resp = httpx.delete(
                f"{API_BASE}/prospects/{prospect_id}",
                headers=_get_headers(),
                timeout=30.0,
            )
            if resp.status_code in (200, 204):
                print(f"  deleted prospect {prospect_id}")
            elif resp.status_code == 403:
                print(f"  403 Forbidden — delete scope not granted. Remove manually in UI.")
            else:
                print(f"  {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  error: {e}")

    return 0


def cmd_execute(target_day: str | None) -> int:
    """Run the drip for today's (or --force-day) batch. Live Outreach writes."""
    plans = read_state(STATE_PATH)
    if not plans:
        logger.error(f"no state file at {STATE_PATH} — run --assign first")
        return 1

    day = target_day or datetime.now(ZoneInfo("America/Chicago")).date().isoformat()

    summary = execute_load_plan(
        plans,
        state_path=STATE_PATH,
        audit_path=AUDIT_PATH,
        target_day=day,
        sleep_seconds=(300, 900),  # 5-15 min uniform
        verify_sequence_active=True,
        dry_run=False,
    )

    print(f"\n=== Execute summary ({day}) ===")
    for k, v in summary.items():
        print(f"  {k:<30s}: {v}")
    print(f"\nState: {STATE_PATH}")
    print(f"Audit: {AUDIT_PATH}")
    return 0


def cmd_verify() -> int:
    """Read state file + audit against live Outreach sequenceStates."""
    plans = read_state(STATE_PATH)
    if not plans:
        logger.error(f"no state file at {STATE_PATH}")
        return 1

    # Per-sequence expected counts (only plans with status=done)
    expected: dict[int, int] = {}
    for p in plans:
        if p.status == "done":
            expected[p.sequence_id] = expected.get(p.sequence_id, 0) + 1

    print(f"\n=== Verify ===\n")
    print(f"Total plans: {len(plans)}")
    print(f"  done:    {sum(1 for p in plans if p.status == 'done')}")
    print(f"  pending: {sum(1 for p in plans if p.status == 'pending')}")
    print(f"  skipped: {sum(1 for p in plans if p.status == 'skipped')}")
    print(f"  failed:  {sum(1 for p in plans if p.status == 'failed')}")
    print()

    print(f"{'Sequence':<10s}{'Expected':>10s}{'Live':>8s}{'Match':>8s}")
    print("-" * 36)
    all_match = True
    for sid in sorted(DIOCESE_TO_SEQUENCE.values()):
        try:
            live_states = get_sequence_states(sid, include_prospect=False)
            live_count = len(live_states)
        except Exception as e:
            live_count = -1
            logger.warning(f"seq {sid} live count error: {e}")
        exp = expected.get(sid, 0)
        match = (live_count >= exp)
        all_match = all_match and match
        print(f"{sid:<10d}{exp:>10d}{live_count:>8d}{'OK' if match else 'MISMATCH':>8s}")

    return 0 if all_match else 1


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Diocesan drip CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--assign", action="store_true", help="Build state file from Leads")
    group.add_argument("--dry-run", action="store_true", help="Print today's plan without posting")
    group.add_argument("--canary", action="store_true", help="Create a throwaway test prospect + add to seq 2013")
    group.add_argument("--canary-cleanup", nargs=2, metavar=("PROSPECT_ID", "SEQSTATE_ID"),
                       help="Delete canary prospect + sequenceState. Pass '0' to skip sequenceState.")
    group.add_argument("--execute", action="store_true", help="Run today's batch (live writes)")
    group.add_argument("--verify", action="store_true", help="Compare state file to live Outreach counts")
    parser.add_argument("--force-day", default=None, metavar="YYYY-MM-DD",
                        help="Override today's date for --dry-run / --execute")
    args = parser.parse_args()

    if args.assign:
        return cmd_assign()
    if args.dry_run:
        return cmd_dry_run(args.force_day)
    if args.canary:
        return cmd_canary()
    if args.canary_cleanup:
        return cmd_canary_cleanup(args.canary_cleanup[0], args.canary_cleanup[1])
    if args.execute:
        return cmd_execute(args.force_day)
    if args.verify:
        return cmd_verify()
    return 2


if __name__ == "__main__":
    sys.exit(main())
