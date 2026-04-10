#!/usr/bin/env python3
"""
Session 54 Phase 1c — Walk the queue from row 1900 upward to find where
the scramble block starts AND read each row's actual strategy + date.
"""
import json, os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds)
sheet_id = os.environ["GOOGLE_SHEETS_ID"]

r = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range="'Prospecting Queue'!A1:T2000",
).execute()
rows = r.get("values", [])

# For scrambled rows, strategy is at idx 2, date at idx 14
# For canonical rows, strategy is at idx 8, date at idx 12
STRATS = {"upward", "cold", "winback", "cold_license_request", "trigger",
          "competitor_displacement", "csta_partnership", "charter_cmo",
          "cte_center", "private_school_network", "compliance_gap",
          "intra_district", "cs_funding_recipient", "homeschool_coop",
          "proximity", "esa_cluster", "sequence_reengagement",
          "webinar_attendee", "webinar_missed"}

def classify(row):
    padded = row + [""] * max(0, 20 - len(row))
    if str(padded[8]).strip() in STRATS:
        return "CANONICAL", padded[8], padded[12]
    if str(padded[2]).strip() in STRATS:
        return "SCRAMBLED", padded[2], padded[14]
    if str(padded[5]).strip() in STRATS:
        return "LEGACY16", padded[5], padded[12]
    return "UNKNOWN", "", ""

# Summary counts
from collections import Counter
fp_counter = Counter()
strat_by_fp = {}
for i, row in enumerate(rows[1:], start=2):
    fp, strat, date = classify(row)
    fp_counter[fp] += 1
    strat_by_fp.setdefault(fp, Counter())[strat] += 1

print("OVERALL FINGERPRINT COUNTS:")
for fp, c in fp_counter.most_common():
    print(f"  {fp}: {c}")

print("\nSTRATEGIES BY FINGERPRINT:")
for fp, strats in strat_by_fp.items():
    print(f"  {fp}:")
    for s, c in strats.most_common(15):
        print(f"    {s or '(empty)':<25} {c}")

print("\nTRANSITIONS from row 1930 to 1960 (show fingerprint flip points):")
for i in range(1930, min(1960, len(rows))):
    if i < 1 or i >= len(rows):
        continue
    row = rows[i]
    fp, strat, date = classify(row)
    name = (row[1] if len(row) > 1 else "")[:35]
    print(f"  row {i+1:>4}: {fp:<10} │ strat={strat:<25} │ date={date:<20} │ {name}")

# Find the FIRST scrambled row (earliest scramble in the sheet)
first_scrambled = None
last_canonical_before = None
for i, row in enumerate(rows[1:], start=2):
    fp, _, _ = classify(row)
    if fp == "SCRAMBLED" and first_scrambled is None:
        first_scrambled = i
    if fp == "CANONICAL" and first_scrambled is None:
        last_canonical_before = i
print(f"\nFIRST scrambled row: {first_scrambled}")
print(f"Last canonical row before first scramble: {last_canonical_before}")
