#!/usr/bin/env python3
"""Sample 2-3 rows from each of the top fingerprint groups so we can
see actual values and design a content-based repair."""
import json, os
from collections import defaultdict
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds)
r = svc.spreadsheets().values().get(
    spreadsheetId=os.environ["GOOGLE_SHEETS_ID"],
    range="'Prospecting Queue'!A:T",
).execute()
rows = r.get("values", [])

def filled_tup(row):
    padded = row + [""] * max(0, 20-len(row))
    return tuple(i for i, v in enumerate(padded[:20]) if str(v).strip() != "")

by_tup = defaultdict(list)
for i, row in enumerate(rows[1:], start=2):
    by_tup[filled_tup(row)].append((i, row))

# Top 8 fingerprints
top = sorted(by_tup.items(), key=lambda x: -len(x[1]))[:8]
for tup, row_list in top:
    print(f"\n{'━'*70}")
    print(f"FINGERPRINT {list(tup)} — {len(row_list)} rows")
    print(f"{'━'*70}")
    for abs_num, row in row_list[:2]:
        padded = row + [""] * max(0, 20-len(row))
        print(f"\n  row {abs_num}:")
        for i in range(20):
            if i in tup:
                v = str(padded[i])
                print(f"    col {chr(ord('A')+i)} ({i+1:>2}): {v[:80]!r}")
