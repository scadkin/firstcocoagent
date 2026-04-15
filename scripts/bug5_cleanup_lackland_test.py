#!/usr/bin/env python3
"""Delete all Lackland ISD rows from today's test runs so the re-smoke-test
has a clean slate."""
import os, json
from pathlib import Path

for line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
    scopes=['https://www.googleapis.com/auth/spreadsheets'],
)
svc = build('sheets', 'v4', credentials=creds)
sheet_id = os.environ['GOOGLE_SHEETS_ID']

meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
leads_tab_id = None
log_tab_id = None
for s in meta['sheets']:
    t = s['properties']['title']
    if t == 'Leads from Research':
        leads_tab_id = s['properties']['sheetId']
    elif t == 'Research Log':
        log_tab_id = s['properties']['sheetId']

# Delete Lackland rows from Leads from Research
resp = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Leads from Research'!A1:K5000"
).execute()
values = resp.get('values', [])
headers = values[0]
dn_idx = headers.index("District Name")
lackland_rows = [i + 1 for i, row in enumerate(values[1:], start=1)
                 if dn_idx < len(row) and "lackland" in row[dn_idx].lower()]
print(f"Lackland rows in Leads from Research: {len(lackland_rows)}  (1-indexed: {lackland_rows[:5]}...)")

# Delete Lackland rows from Research Log (today only)
resp2 = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Research Log'!A1:I1000"
).execute()
log_values = resp2.get('values', [])
log_lackland = [i + 1 for i, row in enumerate(log_values[1:], start=1)
                if len(row) > 1 and "lackland" in row[1].lower()]
print(f"Lackland rows in Research Log: {len(log_lackland)}  (1-indexed: {log_lackland})")

# Build delete requests (reverse order so indices don't shift).
#
# HIGH-11 (S70) off-by-one fix: lackland_rows / log_lackland hold
# 1-indexed sheet row numbers (see the debug prints above), but the
# Sheets API deleteDimension range wants 0-indexed row positions.
# Previous code passed startIndex=r, endIndex=r+1 — which deleted the
# row immediately BELOW each Lackland row and left Lackland intact.
# Correct: startIndex=r-1, endIndex=r.
requests = []
for r in sorted(lackland_rows, reverse=True):
    requests.append({
        "deleteDimension": {
            "range": {"sheetId": leads_tab_id, "dimension": "ROWS",
                      "startIndex": r - 1, "endIndex": r}
        }
    })
for r in sorted(log_lackland, reverse=True):
    requests.append({
        "deleteDimension": {
            "range": {"sheetId": log_tab_id, "dimension": "ROWS",
                      "startIndex": r - 1, "endIndex": r}
        }
    })

if requests:
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id, body={"requests": requests}
    ).execute()
    print(f"Deleted {len(lackland_rows)} Leads + {len(log_lackland)} Log rows")
else:
    print("Nothing to delete")
