#!/usr/bin/env python3
"""Phase 1g — Call add_district via `railway run` (Railway env vars injected)
but fresh Python process. If this lands canonical, Railway env vars are not
the cause. If scrambled, something in env is involved."""
import json, os, sys, random
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
# Don't load .env — use whatever env we were launched with (railway run)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import district_prospector as dp

# Fresh sentinel name each run
SENTINEL = f"ZZZ_PHASE1G_RAILWAYENV_{random.randint(1000,9999)}"

r = dp.add_district(
    name=SENTINEL,
    state="TX",
    notes="Phase 1g — railway env test",
    strategy="competitor_displacement",
    source="signal",
    signal_id=f"phase1g_{random.randint(1000,9999)}",
    est_enrollment=5555,
)
print(f"add_district: {r}")

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds)
resp = svc.spreadsheets().values().get(
    spreadsheetId=os.environ["GOOGLE_SHEETS_ID"],
    range="'Prospecting Queue'!A:T",
).execute()
for i, row in enumerate(resp.get("values", [])):
    if SENTINEL in str(row):
        padded = row + [""] * max(0, 20 - len(row))
        result = "CANONICAL" if padded[8] == "competitor_displacement" else ("SCRAMBLED" if padded[2] == "competitor_displacement" else "UNKNOWN")
        print(f"\nSentinel at row {i+1}: {result}")
        for j, v in enumerate(padded[:20]):
            print(f"  col {j+1}: {v!r}")
        sys.exit(0)
print("ERROR: sentinel not found")
sys.exit(1)
