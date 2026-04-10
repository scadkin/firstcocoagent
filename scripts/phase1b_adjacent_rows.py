#!/usr/bin/env python3
"""
Session 54 Phase 1b — Inspect rows adjacent to the F2 scramble block.

Reads rows 1940-1960 to see what layout the immediately-surrounding rows
have. If rows 1944-1945 (just before F2) are scrambled too, maybe the
scramble is position-dependent. If they're canonical, the ghost writer
is definitely per-row.

Read-only.
"""
import json
import os
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

CANONICAL = [
    "State", "Account Name", "Email", "First Name", "Last Name",
    "Deal Level", "Parent District", "Name Key", "Strategy", "Source",
    "Status", "Priority", "Date Added", "Date Approved", "Sequence Doc URL",
    "Est. Enrollment", "School Count", "Total Licenses", "Signal ID", "Notes",
]

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds)
sheet_id = os.environ["GOOGLE_SHEETS_ID"]

r = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range="'Prospecting Queue'!A1940:T1960",
).execute()
rows = r.get("values", [])

def fp(row):
    padded = row + [""] * max(0, 20 - len(row))
    STRATS = {"upward", "cold", "winback", "cold_license_request", "trigger",
              "competitor_displacement", "csta_partnership", "charter_cmo",
              "cte_center", "private_school_network", "compliance_gap",
              "intra_district", "cs_funding_recipient", "homeschool_coop",
              "proximity", "esa_cluster", "sequence_reengagement",
              "webinar_attendee", "webinar_missed"}
    s_idx = [i for i, v in enumerate(padded[:20]) if str(v).strip() in STRATS]
    non_empty = [i for i, v in enumerate(padded[:20]) if str(v).strip()]
    return s_idx, non_empty

print(f"Rows 1940-1960 (got {len(rows)}):")
print()
for i, row in enumerate(rows):
    abs_num = 1940 + i
    name = (row[1] if len(row) > 1 else "").strip() or "(empty name)"
    state = (row[0] if len(row) > 0 else "").strip() or "?"
    s_idx, non_empty = fp(row)
    fingerprint = "CANONICAL" if s_idx == [8] else f"SCRAMBLED (strategy at {s_idx})"
    print(f"  row {abs_num}: {state:>2} │ {name[:40]:<40} │ {fingerprint} │ filled={non_empty}")
