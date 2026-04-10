#!/usr/bin/env python3
"""
Session 54 Phase 1d — Local sentinel test.

Reproduce the Session 53 claim: calling dp.add_district() from this checkout
produces a CANONICAL row. If memory is right, this should land correctly.
If memory is WRONG (or the bug is somehow environmental), this will land
scrambled and we'll have a reproducer.

CRITICAL: This writes to the LIVE Prospecting Queue, so we use a sentinel
name and delete the row immediately after inspection.

WRITES to live sheet. Run once, inspect, clean up.
"""
import json, os, sys
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# Import the actual Scout module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import district_prospector as dp

SENTINEL_NAME = "ZZZ_SENTINEL_SESSION54_DELETE_ME_phase1d"

print(f"Calling dp.add_district with sentinel name: {SENTINEL_NAME}")
result = dp.add_district(
    name=SENTINEL_NAME,
    state="TX",
    notes="Session 54 Phase 1d sentinel row — SAFE TO DELETE",
    strategy="competitor_displacement",
    source="signal",
    signal_id="sentinel_session54_phase1d",
    est_enrollment=1234,
)
print(f"\nResult: {result}")

# Now read the row back and inspect
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds)
sheet_id = os.environ["GOOGLE_SHEETS_ID"]

r = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range="'Prospecting Queue'!A:T",
).execute()
rows = r.get("values", [])

sentinel_row_num = None
sentinel_row = None
for i, row in enumerate(rows):
    if any(SENTINEL_NAME in str(v) for v in row):
        sentinel_row_num = i + 1  # 1-indexed
        sentinel_row = row
        break

if sentinel_row is None:
    print("\nERROR: sentinel row not found in sheet after add_district")
    sys.exit(1)

print(f"\nSentinel row found at sheet row {sentinel_row_num} (len={len(sentinel_row)}):")
CANONICAL = [
    "State", "Account Name", "Email", "First Name", "Last Name",
    "Deal Level", "Parent District", "Name Key", "Strategy", "Source",
    "Status", "Priority", "Date Added", "Date Approved", "Sequence Doc URL",
    "Est. Enrollment", "School Count", "Total Licenses", "Signal ID", "Notes",
]
padded = sentinel_row + [""] * max(0, 20 - len(sentinel_row))
for i, label in enumerate(CANONICAL):
    val = padded[i] if i < len(padded) else ""
    marker = ""
    if label == "Strategy" and val == "competitor_displacement":
        marker = " ✓ CANONICAL"
    elif i == 2 and val == "competitor_displacement":
        marker = " ✗ SCRAMBLED (strategy at col 3)"
    print(f"  {chr(ord('A')+i):>2} ({i+1:>2}) {label:<16} │ {val!r}{marker}")

# Fingerprint diagnosis
if padded[8] == "competitor_displacement":
    print("\n==> LOCAL TEST RESULT: CANONICAL (strategy correctly at col 9/idx 8)")
    print("    This means add_district produces canonical rows when called from local Python.")
    print("    The production bug must be environmental (Railway-specific) or async-related.")
elif padded[2] == "competitor_displacement":
    print("\n==> LOCAL TEST RESULT: SCRAMBLED (strategy at col 3/idx 2)")
    print("    This means add_district ALSO produces scrambled rows locally — memory was wrong.")
    print("    The bug is in the current code itself, not environmental.")
else:
    print(f"\n==> LOCAL TEST RESULT: UNKNOWN (strategy not found at expected positions)")
    print(f"    padded[2]={padded[2]!r}, padded[8]={padded[8]!r}")

print(f"\nSentinel row number: {sentinel_row_num}")
print(f"Clean up: run `python3 scripts/phase1d_cleanup.py {sentinel_row_num}` (script below)")
