"""Session 60 — check 5 candidate test targets against Active Accounts + pull public district yield from Research Log."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import tools.csv_importer as csv_importer

CANDIDATES = [
    ("Cypress-Fairbanks ISD", "TX", "large"),
    ("Cincinnati Public Schools", "OH", "medium"),
    ("Conejo Valley USD", "CA", "medium"),
    ("Park Ridge-Niles CCSD 64", "IL", "small"),
    ("Waverly School District 145", "NE", "small"),
]

print("=" * 70)
print("ACTIVE ACCOUNTS LOOKUP (5 candidate test targets)")
print("=" * 70)

all_accounts = csv_importer.get_active_accounts()
print(f"Total Active Accounts loaded: {len(all_accounts)}")

# Per-candidate: exact + fuzzy match at district level, then look for any account
# containing the candidate's state + partial name (schools underneath)
for name, state, tier in CANDIDATES:
    print(f"\n--- {name} ({state}, {tier}) ---")
    target_key = csv_importer.normalize_name(name)

    # Filter to same-state
    state_accounts = [a for a in all_accounts if a.get("State", "").upper() == state.upper()]
    print(f"  {len(state_accounts)} active accounts in {state}")

    # District-level exact match
    district_hits = []
    for a in state_accounts:
        a_key = a.get("Name Key") or csv_importer.normalize_name(a.get("Account Name", ""))
        if a_key == target_key:
            district_hits.append(a)

    # District-level fuzzy match
    if not district_hits:
        keys = [a.get("Name Key") or csv_importer.normalize_name(a.get("Account Name", "")) for a in state_accounts]
        matched_key = csv_importer.fuzzy_match_name(target_key, [k for k in keys if k], threshold=0.7)
        if matched_key:
            for a in state_accounts:
                a_key = a.get("Name Key") or csv_importer.normalize_name(a.get("Account Name", ""))
                if a_key == matched_key:
                    district_hits.append(a)

    if district_hits:
        print(f"  DISTRICT-LEVEL MATCH: {len(district_hits)} account(s)")
        for a in district_hits[:3]:
            print(f"    - {a.get('Account Name', '?')} | type={a.get('SF Type', '?')} | classification={a.get('Classification', '?')}")
    else:
        print(f"  no district-level match")

    # School-level lookup: find accounts where Parent District matches OR Account Name contains candidate tokens
    target_tokens = set(t for t in target_key.split() if len(t) > 3)
    if not target_tokens:
        continue
    school_hits = []
    for a in state_accounts:
        parent = (a.get("Parent District") or "").lower()
        acct_name = (a.get("Account Name") or "").lower()
        parent_key = csv_importer.normalize_name(parent) if parent else ""
        # Match if parent district == target or contains all target tokens
        if parent_key == target_key:
            school_hits.append(a)
        elif all(t in acct_name for t in target_tokens) and a not in district_hits:
            school_hits.append(a)
        elif parent_key and target_tokens.issubset(set(parent_key.split())):
            if a not in school_hits:
                school_hits.append(a)

    if school_hits:
        print(f"  SCHOOL-LEVEL ACCOUNTS UNDER THIS DISTRICT: {len(school_hits)}")
        for a in school_hits[:5]:
            print(f"    - {a.get('Account Name', '?')} | parent={a.get('Parent District', '?')} | type={a.get('SF Type', '?')}")
        if len(school_hits) > 5:
            print(f"    ... and {len(school_hits) - 5} more")
    else:
        print(f"  no school-level accounts under this district")

print()
print("=" * 70)
print("RESEARCH LOG YIELD — public district jobs only")
print("=" * 70)

# Pull Research Log directly
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import json as _json

creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
creds_dict = _json.loads(creds_json)
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds)
sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
result = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Research Log'!A2:I"
).execute()
rows = result.get("values", [])
print(f"Total Research Log rows: {len(rows)}")

# Exclude anything that looks diocesan / charter / CTE / private school network
def is_public_district(name: str) -> bool:
    n = (name or "").lower()
    bad_tokens = [
        "archdiocese", "diocese", "catholic", "parochial", "cte center",
        "career technology", "career technical center", "tech center",
        "kipp", "idea public schools", "harmony public", "aspire public",
        "uplift education", "responsiveed", "great hearts", "cristo rey",
        "charter school", "charter academy", "charter network",
        "academy of", "prep academy", " prep ", "archbishop",
    ]
    return not any(tok in n for tok in bad_tokens)

public_rows = [r for r in rows if len(r) > 4 and is_public_district(r[1])]
print(f"Public district rows (excluding diocesan/charter/CTE/private networks): {len(public_rows)}")

# Compute yield distribution
yields = []
with_email_yields = []
for r in public_rows:
    try:
        total = int(r[4]) if len(r) > 4 and r[4] else 0
        with_em = int(r[5]) if len(r) > 5 and r[5] else 0
        yields.append(total)
        with_email_yields.append(with_em)
    except (ValueError, IndexError):
        continue

if yields:
    yields_sorted = sorted(yields)
    n = len(yields)
    print(f"\nContacts-found distribution over {n} public district research jobs:")
    print(f"  min: {yields_sorted[0]}")
    print(f"  p25: {yields_sorted[n // 4]}")
    print(f"  median: {yields_sorted[n // 2]}")
    print(f"  p75: {yields_sorted[(3 * n) // 4]}")
    print(f"  p90: {yields_sorted[min(n - 1, (9 * n) // 10)]}")
    print(f"  max: {yields_sorted[-1]}")
    print(f"  mean: {sum(yields) / n:.1f}")
    print(f"  zero-yield jobs: {sum(1 for y in yields if y == 0)} ({100 * sum(1 for y in yields if y == 0) / n:.0f}%)")

    em_sorted = sorted(with_email_yields)
    print(f"\nContacts-with-email distribution:")
    print(f"  median: {em_sorted[n // 2]}")
    print(f"  mean: {sum(with_email_yields) / n:.1f}")
    print(f"  zero-email jobs: {sum(1 for y in with_email_yields if y == 0)} ({100 * sum(1 for y in with_email_yields if y == 0) / n:.0f}%)")
else:
    print("No public district jobs in Research Log")

# Top 10 and bottom 10 for sanity
if public_rows:
    print(f"\nSample public district rows (first 5):")
    for r in public_rows[:5]:
        total = r[4] if len(r) > 4 else "?"
        with_em = r[5] if len(r) > 5 else "?"
        print(f"  {r[0]} | {r[1]} ({r[2] if len(r) > 2 else '?'}) | total={total} with_email={with_em}")
    print(f"\nSample public district rows (last 5):")
    for r in public_rows[-5:]:
        total = r[4] if len(r) > 4 else "?"
        with_em = r[5] if len(r) > 5 else "?"
        print(f"  {r[0]} | {r[1]} ({r[2] if len(r) > 2 else '?'}) | total={total} with_email={with_em}")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
