#!/usr/bin/env python3
"""
Session 54 Phase 1 — Ground-truth the memory's description of the
Lackland row scramble.

Reads the Prospecting Queue tab directly via the service account and
dumps the raw 20 cells (A-T) for:
  1. All rows where Account Name contains "Lackland"
  2. All rows where Date Added starts with "2026-04-10 00:5" (the F2 run
     window 00:51 UTC per memory)
  3. A canonical control row (Pittsburgh Public Schools) for comparison

Output for each matching row:
  - Absolute sheet row number
  - Every cell value with its column letter + canonical header label
  - A per-row fingerprint diagnosis: which cells look "canonical" vs drifted

Read-only. Safe to run multiple times.

Usage: python3 scripts/phase1_ground_truth_lackland.py
Requires: GOOGLE_SHEETS_ID + GOOGLE_SERVICE_ACCOUNT_JSON in .env
"""

import json
import os
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

CANONICAL_HEADERS = [
    "State", "Account Name", "Email", "First Name", "Last Name",
    "Deal Level", "Parent District", "Name Key", "Strategy", "Source",
    "Status", "Priority", "Date Added", "Date Approved", "Sequence Doc URL",
    "Est. Enrollment", "School Count", "Total Licenses", "Signal ID", "Notes",
]

TAB = "Prospecting Queue"


def get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not creds_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON not set in .env", file=sys.stderr)
        sys.exit(1)
    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return build("sheets", "v4", credentials=creds)


def col_letter(idx: int) -> str:
    # 0-indexed → A, B, C...
    return chr(ord("A") + idx)


def dump_row(abs_row_num: int, row: list):
    padded = row + [""] * max(0, 20 - len(row))
    print(f"\n━━━ Row {abs_row_num} (len={len(row)}) ━━━")
    for i, label in enumerate(CANONICAL_HEADERS):
        val = padded[i] if i < len(padded) else ""
        display = (val[:60] + "…") if len(str(val)) > 60 else val
        print(f"  {col_letter(i):>2} ({i+1:>2}) {label:<16} │ {display!r}")

    # Diagnosis: where does "strategy-looking" text live?
    STRATEGY_HINTS = {
        "upward", "cold", "winback", "cold_license_request", "trigger",
        "competitor_displacement", "csta_partnership", "charter_cmo",
        "cte_center", "private_school_network", "compliance_gap",
        "intra_district", "cs_funding_recipient", "homeschool_coop",
        "proximity", "esa_cluster", "sequence_reengagement",
        "webinar_attendee", "webinar_missed",
    }
    STATUS_HINTS = {"pending", "approved", "researching", "draft", "complete", "skipped"}
    SOURCE_HINTS = {
        "web_search", "manual", "upward_auto", "pipeline_closed", "outreach",
        "signal", "proximity_auto", "expansion_auto", "compliance_scan",
    }

    found_strategy_idx = [i for i, v in enumerate(padded[:20]) if str(v).strip() in STRATEGY_HINTS]
    found_status_idx = [i for i, v in enumerate(padded[:20]) if str(v).strip() in STATUS_HINTS]
    found_source_idx = [i for i, v in enumerate(padded[:20]) if str(v).strip() in SOURCE_HINTS]
    non_empty_idx = [i for i, v in enumerate(padded[:20]) if str(v).strip()]

    print(f"  FINGERPRINT:")
    print(f"    strategy at: {found_strategy_idx} (canonical=8)")
    print(f"    status   at: {found_status_idx} (canonical=10)")
    print(f"    source   at: {found_source_idx} (canonical=9)")
    print(f"    non-empty:   {non_empty_idx}")
    print(f"    row length:  {len(row)}")


def main():
    svc = get_service()
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEETS_ID not set", file=sys.stderr)
        sys.exit(1)

    print(f"Reading '{TAB}'!A:T from sheet {sheet_id[:12]}…")
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB}'!A:T",
    ).execute()
    rows = result.get("values", [])
    print(f"Got {len(rows)} total rows (including header)")

    if len(rows) < 2:
        print("ERROR: no data rows")
        sys.exit(1)

    header = rows[0]
    print(f"\nHEADER (len={len(header)}): {header}")
    if header != CANONICAL_HEADERS:
        print(f"WARNING: header does not match canonical schema!")
        print(f"  Expected: {CANONICAL_HEADERS}")
        print(f"  Got:      {header}")

    data_rows = rows[1:]
    print(f"\n============================================================")
    print(f"SEARCH 1: rows with Account Name containing 'Lackland'")
    print(f"============================================================")
    lackland_hits = []
    for i, row in enumerate(data_rows):
        # Column B (index 1) is Account Name canonically, but we want to be
        # flexible since we're investigating a scramble. Check both col B and
        # col B if it's an old layout — actually just check every cell.
        for val in row:
            if "lackland" in str(val).lower():
                lackland_hits.append((i + 2, row))  # +2 = 1-indexed + skip header
                break
    print(f"Matched {len(lackland_hits)} Lackland rows")
    for abs_num, row in lackland_hits:
        dump_row(abs_num, row)

    print(f"\n============================================================")
    print(f"SEARCH 2: rows with Date Added in the 2026-04-10 00:5x window")
    print(f"(this is the F2 scan window per memory)")
    print(f"============================================================")
    time_window_hits = []
    for i, row in enumerate(data_rows):
        for val in row:
            if isinstance(val, str) and val.startswith("2026-04-10 00:5"):
                time_window_hits.append((i + 2, row))
                break
    print(f"Matched {len(time_window_hits)} rows in 00:5x window")
    # Dedup against Lackland hits
    seen = {t[0] for t in lackland_hits}
    new_hits = [(n, r) for n, r in time_window_hits if n not in seen]
    print(f"  {len(new_hits)} NOT already shown as Lackland hits")
    for abs_num, row in new_hits:
        dump_row(abs_num, row)

    print(f"\n============================================================")
    print(f"SEARCH 3: Pittsburgh Public Schools (canonical control)")
    print(f"============================================================")
    pitt_hits = []
    for i, row in enumerate(data_rows):
        for val in row:
            if "pittsburgh public" in str(val).lower():
                pitt_hits.append((i + 2, row))
                break
    print(f"Matched {len(pitt_hits)} Pittsburgh rows")
    for abs_num, row in pitt_hits:
        dump_row(abs_num, row)

    print(f"\n============================================================")
    print(f"SEARCH 4: Archdiocese of Chicago (canonical control)")
    print(f"============================================================")
    arch_hits = []
    for i, row in enumerate(data_rows):
        for val in row:
            if "archdiocese" in str(val).lower() and "chicago" in str(val).lower():
                arch_hits.append((i + 2, row))
                break
    print(f"Matched {len(arch_hits)} Archdiocese rows")
    for abs_num, row in arch_hits:
        dump_row(abs_num, row)


if __name__ == "__main__":
    main()
