#!/usr/bin/env python3
"""Delete ZZZ_* sentinel rows from Prospecting Queue. One-shot cleanup.

Safety: only deletes rows where col B (Account Name) starts with 'ZZZ_'.
Uses deleteDimension to avoid shifting rows mid-batch — processes in reverse
index order so later deletions don't invalidate earlier row numbers.
"""
import os, json
from dotenv import load_dotenv
load_dotenv()
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
    scopes=['https://www.googleapis.com/auth/spreadsheets'],
)
svc = build('sheets', 'v4', credentials=creds)
sheet_id = os.environ['GOOGLE_SHEETS_ID']
TAB = 'Prospecting Queue'

# Find the tab's numeric sheetId
meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
tab_sheet_id = None
for s in meta['sheets']:
    if s['properties']['title'] == TAB:
        tab_sheet_id = s['properties']['sheetId']
        break
assert tab_sheet_id is not None, f'tab {TAB} not found'

# Read all rows
resp = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range=f"'{TAB}'!A1:T3000"
).execute()
values = resp.get('values', [])

# Find ZZZ rows (1-indexed row numbers)
zzz_rows = []
for i, row in enumerate(values, start=1):
    if i == 1: continue  # skip header
    name = row[1] if len(row) > 1 else ''
    if isinstance(name, str) and name.startswith('ZZZ_'):
        zzz_rows.append((i, name))

print(f'Found {len(zzz_rows)} ZZZ_* sentinel rows:')
for idx, name in zzz_rows:
    print(f'  row {idx}: {name!r}')

if not zzz_rows:
    print('Nothing to delete.')
    raise SystemExit(0)

# Build deleteDimension requests — reverse order to preserve indices
requests = []
for idx, _name in sorted(zzz_rows, reverse=True):
    # deleteDimension uses 0-indexed, end-exclusive
    requests.append({
        'deleteDimension': {
            'range': {
                'sheetId': tab_sheet_id,
                'dimension': 'ROWS',
                'startIndex': idx - 1,
                'endIndex': idx,
            }
        }
    })

svc.spreadsheets().batchUpdate(
    spreadsheetId=sheet_id, body={'requests': requests}
).execute()
print(f'Deleted {len(zzz_rows)} sentinel rows.')
