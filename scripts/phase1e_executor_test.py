#!/usr/bin/env python3
"""
Session 54 Phase 1e — Test add_district via loop.run_in_executor
exactly like production does. If this produces scrambled, the executor
is the vector. If canonical, we've ruled out asyncio+executor.
"""
import asyncio, json, os, sys
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import district_prospector as dp

SENTINEL_NAME = "ZZZ_SENTINEL_SESSION54_PHASE1E_EXECUTOR"

async def main():
    loop = asyncio.get_event_loop()
    # Exactly like main.py:3276
    result = await loop.run_in_executor(
        None,
        lambda: dp.add_district(
            name=SENTINEL_NAME,
            state="TX",
            notes="Session 54 Phase 1e sentinel — via executor",
            strategy="competitor_displacement",
            source="signal",
            signal_id="sentinel_phase1e_executor",
            est_enrollment=9999,
        )
    )
    print(f"Executor result: {result}")

asyncio.run(main())

# Now read back
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
for i, row in enumerate(rows):
    if any(SENTINEL_NAME in str(v) for v in row):
        padded = row + [""] * max(0, 20-len(row))
        print(f"\nSentinel found at row {i+1}")
        if padded[8] == "competitor_displacement":
            print("==> CANONICAL (strategy at col 9)")
        elif padded[2] == "competitor_displacement":
            print("==> SCRAMBLED (strategy at col 3)")
        else:
            print(f"==> UNKNOWN: padded[2]={padded[2]!r}, padded[8]={padded[8]!r}")
        for j, v in enumerate(padded):
            print(f"  col {j+1}: {v!r}")
        break
