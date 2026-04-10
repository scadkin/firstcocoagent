#!/usr/bin/env python3
"""
Session 54 BUG 3 repair — rebuild the Prospecting Queue canonical layout.

PROBLEM: Every row in the queue except the last 6 was written in a scrambled
column layout where Strategy sits at col C (idx 2) instead of col I (idx 8),
with additional per-strategy permutations for the optional fields. The
canonical Pittsburgh PS and Archdiocese rows (plus my sentinel rows) are the
only correct rows in the sheet. /prospect_all cannot see the scrambled rows
because Status ('pending') is at col N (idx 13) instead of col K (idx 10).

APPROACH:
  1. Snapshot the Prospecting Queue tab to a BACKUP tab (via copyTo) before
     any write. Non-negotiable recovery path.
  2. Classify each row: already canonical or scrambled.
  3. For scrambled rows, dispatch by Strategy to the correct scramble-template
     reader, extracting canonical field values from known positions.
  4. Rebuild as a 20-element canonical row.
  5. Dry-run by default (print before/after diff). --apply writes back via
     clear + update (same pattern as migrate_prospect_columns).

USAGE:
  python3 scripts/repair_scrambled_queue_rows.py            # dry run
  python3 scripts/repair_scrambled_queue_rows.py --apply    # write

RECOVERY:
  If the --apply run corrupts the queue, restore from the BACKUP tab:
    gcloud:  manually copy 'Prospecting Queue BACKUP YYYY-MM-DD' rows back
    scripted: there is no scripted recovery — snapshots are cheap,
             so make another one before any second-round repair.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ─── Canonical layout ────────────────────────────────────────────────────────
CANONICAL_HEADERS = [
    "State", "Account Name", "Email", "First Name", "Last Name",
    "Deal Level", "Parent District", "Name Key", "Strategy", "Source",
    "Status", "Priority", "Date Added", "Date Approved", "Sequence Doc URL",
    "Est. Enrollment", "School Count", "Total Licenses", "Signal ID", "Notes",
]
NUM_COLS = len(CANONICAL_HEADERS)  # 20
TAB = "Prospecting Queue"

STRATEGIES = {
    "upward", "cold", "winback", "cold_license_request", "trigger",
    "competitor_displacement", "csta_partnership", "charter_cmo",
    "cte_center", "private_school_network", "compliance_gap",
    "intra_district", "cs_funding_recipient", "homeschool_coop",
    "proximity", "esa_cluster", "sequence_reengagement",
    "webinar_attendee", "webinar_missed",
}


def get_service():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def fingerprint(row):
    """Return 'canonical' if strategy@idx8 and status@idx10 both match, else 'scrambled'."""
    padded = row + [""] * max(0, NUM_COLS - len(row))
    strat_at_8 = str(padded[8]).strip() in STRATEGIES
    status_at_10 = str(padded[10]).strip() in {"pending", "approved", "researching", "draft", "complete", "skipped"}
    if strat_at_8 and status_at_10:
        return "canonical"
    if str(padded[2]).strip() in STRATEGIES:
        return "scrambled"
    return "unknown"


# ─── Scramble readers (per strategy) ─────────────────────────────────────────
#
# All scrambled rows share the prefix:
#   idx 0: State
#   idx 1: Account Name
#   idx 2: Strategy
#   idx 3: Priority
#   idx 4: Source
#   idx 12: Name Key
#   idx 13: Status
#   idx 14: Date Added
#
# The middle (idx 5-11) and tail (idx 19) layout varies by strategy.

def _base_fields(padded):
    """Extract the always-present fields + common approved-state fields."""
    return {
        "state": padded[0],
        "name": padded[1],
        "strategy": padded[2],
        "priority": padded[3],
        "source": padded[4],
        "name_key": padded[12],
        "status": padded[13] or "pending",
        "date_added": padded[14],
        # Approved/drafted rows write date_approved and sequence_doc_url here.
        # If the row was never approved, these are empty — safe to read as ""
        "date_approved": padded[15] if len(padded) > 15 else "",
        "sequence_doc_url": padded[16] if len(padded) > 16 else "",
    }


def _read_cold_license_request(padded):
    """C4 scramble: email/first/last/deal_level/parent at 7-11, notes at 19."""
    f = _base_fields(padded)
    f.update({
        "email": padded[7],
        "first_name": padded[8],
        "last_name": padded[9],
        "deal_level": padded[10],
        "parent_district": padded[11],
        "notes": padded[19],
    })
    return f


def _read_intra_district(padded):
    """F1 scramble: enrollment@5, notes@6, deal_level@10, parent@11."""
    f = _base_fields(padded)
    f.update({
        "est_enrollment": padded[5],
        "notes": padded[6],
        "deal_level": padded[10],
        "parent_district": padded[11],
    })
    return f


def _read_winback(padded):
    """Winback scramble: deal_level@10, parent@11 (if school), notes@19."""
    f = _base_fields(padded)
    f.update({
        "deal_level": padded[10],
        "parent_district": padded[11],
        "notes": padded[19],
    })
    return f


def _read_signal_strategy(padded):
    """F2/F4/F5 scramble: enrollment@5, notes@6, signal_id@19."""
    f = _base_fields(padded)
    f.update({
        "est_enrollment": padded[5],
        "notes": padded[6],
        "signal_id": padded[19],
    })
    return f


def _read_proximity(padded):
    """Proximity scramble: deal_level@10 or 5, parent@11 or 6, notes varies."""
    f = _base_fields(padded)
    # Proximity may follow either the winback shape or the signal shape.
    # Heuristic: if idx 5 looks like a number → enrollment path; else → deal path.
    if padded[5].isdigit():
        f.update({
            "est_enrollment": padded[5],
            "notes": padded[6] or padded[19],
            "deal_level": padded[10],
            "parent_district": padded[11],
        })
    else:
        f.update({
            "deal_level": padded[10],
            "parent_district": padded[11],
            "notes": padded[19],
        })
    return f


def _read_generic_with_notes_at_19(padded):
    """
    Fallback for strategies whose scramble template matches the winback shape:
    deal_level@10, parent@11, notes@19.
    Used for: trigger, charter_cmo, cte_center, private_school_network,
    compliance_gap, homeschool_coop, sequence_reengagement, webinar_*, upward, cold.
    """
    f = _base_fields(padded)
    f.update({
        "deal_level": padded[10],
        "parent_district": padded[11],
        "notes": padded[19],
    })
    return f


STRATEGY_READERS = {
    "cold_license_request": _read_cold_license_request,
    "intra_district": _read_intra_district,
    "winback": _read_winback,
    "competitor_displacement": _read_signal_strategy,
    "cs_funding_recipient": _read_signal_strategy,
    "csta_partnership": _read_signal_strategy,
    "proximity": _read_proximity,
    "esa_cluster": _read_proximity,
    # Anything not in this map falls through to _read_generic_with_notes_at_19
}


def extract_fields_from_scrambled(row):
    """Return a dict of canonical field values recovered from a scrambled row."""
    padded = row + [""] * max(0, NUM_COLS - len(row))
    # Convert any non-string cells to string for safety
    padded = [str(v) if v is not None else "" for v in padded]
    strategy = padded[2].strip()
    reader = STRATEGY_READERS.get(strategy, _read_generic_with_notes_at_19)
    return reader(padded)


def build_canonical_row(f: dict) -> list:
    """Build a 20-element canonical row from an extracted field dict."""
    return [
        f.get("state", ""),                # 0 State
        f.get("name", ""),                 # 1 Account Name
        f.get("email", ""),                # 2 Email
        f.get("first_name", ""),           # 3 First Name
        f.get("last_name", ""),            # 4 Last Name
        f.get("deal_level", ""),           # 5 Deal Level
        f.get("parent_district", ""),      # 6 Parent District
        f.get("name_key", ""),             # 7 Name Key
        f.get("strategy", ""),             # 8 Strategy
        f.get("source", ""),               # 9 Source
        f.get("status", "pending"),        # 10 Status
        f.get("priority", ""),             # 11 Priority
        f.get("date_added", ""),           # 12 Date Added
        f.get("date_approved", ""),        # 13 Date Approved
        f.get("sequence_doc_url", ""),     # 14 Sequence Doc URL
        f.get("est_enrollment", ""),       # 15 Est. Enrollment
        f.get("school_count", ""),         # 16 School Count
        f.get("total_licenses", ""),       # 17 Total Licenses
        f.get("signal_id", ""),            # 18 Signal ID
        f.get("notes", ""),                # 19 Notes
    ]


def read_canonical_row(row):
    """For rows already canonical, pad to 20 and return."""
    padded = row + [""] * max(0, NUM_COLS - len(row))
    return [str(v) if v is not None else "" for v in padded[:NUM_COLS]]


# ─── Snapshot ────────────────────────────────────────────────────────────────

def snapshot_queue(svc, sheet_id):
    """Duplicate the Prospecting Queue tab via copyTo. Returns new tab title."""
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    source_sheet = None
    existing_titles = set()
    for s in meta.get("sheets", []):
        props = s["properties"]
        existing_titles.add(props["title"])
        if props["title"] == TAB:
            source_sheet = props
    if source_sheet is None:
        raise RuntimeError(f"Tab '{TAB}' not found")

    backup_title = f"Prospecting Queue BACKUP {datetime.now().strftime('%Y-%m-%d %H%M')}"
    # Copy within same spreadsheet via duplicateSheet
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            "requests": [{
                "duplicateSheet": {
                    "sourceSheetId": source_sheet["sheetId"],
                    "newSheetName": backup_title,
                    "insertSheetIndex": source_sheet["index"] + 1,
                }
            }]
        },
    ).execute()
    return backup_title


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Actually write the repaired rows back. Default is dry-run.")
    ap.add_argument("--skip-snapshot", action="store_true",
                    help="Skip snapshot (dangerous — only use if you already have a backup).")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only process first N data rows (dry-run diagnostic).")
    args = ap.parse_args()

    svc = get_service()
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Reading '{TAB}'...")
    r = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB}'!A:T",
    ).execute()
    rows = r.get("values", [])
    if len(rows) < 2:
        print("Queue is empty — nothing to do.")
        return

    header = rows[0]
    data_rows = rows[1:]
    if args.limit:
        data_rows = data_rows[:args.limit]
    print(f"Header length: {len(header)} (expected {NUM_COLS})")
    print(f"Data rows: {len(data_rows)}")
    if header != CANONICAL_HEADERS:
        print(f"WARNING: header doesn't match canonical. Will rewrite.")

    # Classify + extract
    new_rows = []
    counts = {"canonical": 0, "scrambled": 0, "unknown": 0}
    unknown_samples = []
    repaired_samples = []

    for abs_num, row in enumerate(data_rows, start=2):
        fp = fingerprint(row)
        counts[fp] += 1
        if fp == "canonical":
            new_rows.append(read_canonical_row(row))
        elif fp == "scrambled":
            fields = extract_fields_from_scrambled(row)
            new_row = build_canonical_row(fields)
            new_rows.append(new_row)
            if len(repaired_samples) < 5:
                repaired_samples.append((abs_num, row, new_row))
        else:
            # Keep unknown row as-is, padded to 20
            padded = row + [""] * max(0, NUM_COLS - len(row))
            new_rows.append([str(v) if v is not None else "" for v in padded[:NUM_COLS]])
            if len(unknown_samples) < 5:
                unknown_samples.append((abs_num, row))

    print(f"\nClassification:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    if repaired_samples:
        print(f"\n━━━ REPAIR SAMPLES (showing {len(repaired_samples)}) ━━━")
        for abs_num, old, new in repaired_samples:
            print(f"\n  Row {abs_num}:")
            print(f"    OLD: {old[:20]}")
            print(f"    NEW: {new}")

    if unknown_samples:
        print(f"\n━━━ UNKNOWN ROWS (showing {len(unknown_samples)}) ━━━")
        for abs_num, row in unknown_samples:
            print(f"  Row {abs_num}: {row[:10]}")

    if not args.apply:
        print(f"\n[DRY RUN] Would write {len(new_rows)} rows. Use --apply to write.")
        return

    # Apply: snapshot + clear + update
    if not args.skip_snapshot:
        print(f"\n[APPLY] Creating snapshot tab...")
        backup = snapshot_queue(svc, sheet_id)
        print(f"[APPLY] Snapshot created: '{backup}'")
    else:
        print(f"\n[APPLY] Skipping snapshot (--skip-snapshot)")

    print(f"[APPLY] Clearing '{TAB}'...")
    svc.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{TAB}'!A1:Z9999",
    ).execute()

    print(f"[APPLY] Writing {len(new_rows)} rows + header...")
    all_output = [CANONICAL_HEADERS] + new_rows
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB}'!A1",
        valueInputOption="RAW",
        body={"values": all_output},
    ).execute()

    print(f"[APPLY] Done. {counts['scrambled']} rows repaired, {counts['canonical']} rows left alone, {counts['unknown']} unknown.")


if __name__ == "__main__":
    main()
