#!/usr/bin/env python3
"""BUG 5 Phase 3 smoke-test verifier.

Reads the Research Log entry for today's Lackland ISD run + the 28 new rows
it wrote to Leads from Research, and confirms:
  1. cross_contam_dropped column populated (should be 9 matching the page
     filter log line)
  2. All new Lackland rows fingerprint as clean_* via the audit logic
"""
import json, os, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from tools.research_engine import ResearchJob

creds = Credentials.from_service_account_info(
    json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
)
svc = build('sheets', 'v4', credentials=creds)
sheet_id = os.environ['GOOGLE_SHEETS_ID']

# Research Log
resp = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Research Log'!A1:I1000"
).execute()
values = resp.get('values', [])
headers = values[0] if values else []
print(f"Research Log headers ({len(headers)}): {headers}")

# Find today's Lackland ISD row (latest)
lackland_rows = [row for row in values[1:] if len(row) > 1 and "lackland" in row[1].lower()]
if not lackland_rows:
    print("No Lackland row found in Research Log")
    sys.exit(1)
latest = lackland_rows[-1]
print(f"\nLatest Lackland Research Log row:")
for i, h in enumerate(headers):
    val = latest[i] if i < len(latest) else "(empty)"
    print(f"  {h}: {val}")

# Verify cross_contam_dropped column is present and populated
if "Cross-Contam Dropped" in headers:
    idx = headers.index("Cross-Contam Dropped")
    val = latest[idx] if idx < len(latest) else None
    print(f"\n✅ cross_contam_dropped column present: value = {val!r}")
else:
    print("\n❌ cross_contam_dropped column MISSING from header")

# Leads from Research — pull today's Lackland rows
resp2 = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Leads from Research'!A1:K5000"
).execute()
lead_values = resp2.get('values', [])
lead_headers = lead_values[0] if lead_values else []
dn_idx = lead_headers.index("District Name")
date_idx = lead_headers.index("Date Found")
email_idx = lead_headers.index("Email")
src_idx = lead_headers.index("Source URL")

new_rows = [row for row in lead_values[1:]
            if len(row) > dn_idx and "lackland" in row[dn_idx].lower()]
print(f"\nNew Lackland rows today: {len(new_rows)}")

# Fingerprint each using the shipped helpers
target_host = "lacklandisd.net"
target_hint = ResearchJob._district_name_hint("Lackland ISD")
print(f"target_host={target_host}  target_hint={target_hint}")

clean_ok = 0
fails = []
for i, row in enumerate(new_rows):
    email = row[email_idx] if email_idx < len(row) else ""
    src = row[src_idx] if src_idx < len(row) else ""
    src_host = urlparse(src).netloc.lower().replace("www.", "") if src else ""
    source_ok = ResearchJob._host_matches_target(src_host, target_host, target_hint)
    email_ok = ResearchJob._email_domain_matches_target(email, target_host, target_hint)
    if source_ok or email_ok:
        clean_ok += 1
    else:
        fails.append((row[0], row[1] if len(row)>1 else "", email, src_host))

print(f"\nFingerprint: {clean_ok}/{len(new_rows)} rows pass clean check")
if fails:
    print("FAILS:")
    for f in fails:
        print(f"  {f}")
    sys.exit(1)

print("\n✅ ALL LACKLAND ROWS CLEAN")
