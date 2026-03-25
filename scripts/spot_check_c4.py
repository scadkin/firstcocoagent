#!/usr/bin/env python3
"""
Quick spot-check script for C4 Cold License Requests.
Reads Prospecting Queue and C4 Audit tab directly from Google Sheets.

Usage: python3 scripts/spot_check_c4.py
Requires: GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON env vars
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Load .env if present
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not creds_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON not set")
        sys.exit(1)
    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return build("sheets", "v4", credentials=creds)


def read_tab(service, sheet_id, tab_range):
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=tab_range)
        .execute()
    )
    return result.get("values", [])


def main():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEETS_ID not set")
        sys.exit(1)

    service = get_service()

    # ── 1. Prospecting Queue: state distribution ──
    print("=" * 60)
    print("PROSPECTING QUEUE — State Distribution")
    print("=" * 60)

    rows = read_tab(service, sheet_id, "'Prospecting Queue'!A:S")
    if not rows:
        print("No data in Prospecting Queue!")
        return

    headers = rows[0]
    prospects = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        prospects.append(dict(zip(headers, padded)))

    # Filter to cold_license_request strategy only
    c4_prospects = [p for p in prospects if p.get("Strategy") == "cold_license_request"]
    all_prospects = prospects

    print(f"\nTotal rows: {len(all_prospects)}")
    print(f"C4 (cold_license_request) rows: {len(c4_prospects)}")

    # State distribution for C4
    states = Counter(p.get("State", "").strip() for p in c4_prospects)
    print(f"\nC4 State distribution ({len(states)} unique states):")
    for state, count in states.most_common():
        label = state if state else "<<EMPTY>>"
        print(f"  {label:20s} {count:5d}")

    # Empty states
    empty_state = [p for p in c4_prospects if not p.get("State", "").strip()]
    if empty_state:
        print(f"\n⚠️  {len(empty_state)} C4 prospects with EMPTY state:")
        for p in empty_state[:20]:
            email = p.get("Email", "???")
            name = p.get("Account Name", "???")
            print(f"  {email:40s}  {name}")
        if len(empty_state) > 20:
            print(f"  ... and {len(empty_state) - 20} more")
    else:
        print("\n✅ No empty states in C4 prospects!")

    # ── 2. Sample of CA prospects (SoCal should be included) ──
    ca_prospects = [p for p in c4_prospects if p.get("State", "").strip() == "CA"]
    print(f"\n{'=' * 60}")
    print(f"CA PROSPECTS IN QUEUE ({len(ca_prospects)} total)")
    print("=" * 60)
    for p in ca_prospects[:30]:
        email = p.get("Email", "")
        name = p.get("Account Name", "")
        district = p.get("Parent District", "")
        print(f"  {email:40s}  {name[:30]:30s}  {district[:30]}")
    if len(ca_prospects) > 30:
        print(f"  ... and {len(ca_prospects) - 30} more")

    # ── 3. C4 Audit: OUT OF TERRITORY section ──
    print(f"\n{'=' * 60}")
    print("C4 AUDIT — OUT OF TERRITORY")
    print("=" * 60)

    audit_rows = read_tab(service, sheet_id, "'C4 Audit'!A:E")
    if not audit_rows:
        print("No data in C4 Audit tab!")
        return

    # Find OUT OF TERRITORY section
    out_of_terr = []
    in_section = False
    for row in audit_rows:
        row_text = " ".join(str(c) for c in row) if row else ""
        if "OUT OF TERRITORY" in row_text:
            in_section = True
            print(f"  Section header: {row_text}")
            continue
        if in_section:
            if row and str(row[0]).startswith("==="):
                break
            if row and len(row) >= 3:
                out_of_terr.append(row)

    print(f"\n  {len(out_of_terr)} prospects excluded as OUT OF TERRITORY:")
    # Show all with email domains for SoCal check
    for row in out_of_terr:
        company = row[0] if len(row) > 0 else ""
        contact = row[1] if len(row) > 1 else ""
        email = row[2] if len(row) > 2 else ""
        title = row[3] if len(row) > 3 else ""
        reason = row[4] if len(row) > 4 else ""
        print(f"  {email:40s}  {company[:30]:30s}  {reason}")

    # Check for known SoCal domains in OUT OF TERRITORY (potential false exclusions)
    SOCAL_KEYWORDS = [
        "lausd", "sandi", "sausd", "ggusd", "abcusd", "myabcusd", "iusd",
        "tustin", "capousd", "svusd", "fjuhsd", "auhsd", "pylusd", "bousd",
        "hbuhsd", "lbusd", "musd", "ouhsd", "ocde", "lacoe", "rialto",
        "sbcusd", "colton", "fontana", "jurupa", "alvord", "hemet",
        "temecula", "murrieta", "menifee", "perris", "beaumont", "banning",
        "palmsprings", "desertsands", "psusd", "cvusd", "cnusd", "dusd",
        "eusd", "fusd", "husd", "kusd", "nusd", "pusd", "rusd", "susd",
        "tusd", "vusd", "wusd", "sbusd", "oxnard", "ventura", "camarillo",
        "moorpark", "simivalley", "thousandoaks", "santabarbara",
        "sanluisobispo", "bakersfield", "kern", "imperial",
        "sandiego", "losangeles", "riverside", "sanbernardino", "orange",
    ]

    suspect = []
    for row in out_of_terr:
        email = (row[2] if len(row) > 2 else "").lower()
        domain = email.split("@")[-1] if "@" in email else ""
        for kw in SOCAL_KEYWORDS:
            if kw in domain:
                suspect.append((email, row[0] if row else "", kw))
                break

    if suspect:
        print(f"\n⚠️  {len(suspect)} OUT OF TERRITORY entries with SoCal-looking domains:")
        for email, company, matched_kw in suspect:
            print(f"  {email:40s}  {company[:30]:30s}  (matched: {matched_kw})")
    else:
        print(f"\n✅ No SoCal-looking domains found in OUT OF TERRITORY!")

    # ── 4. C4 Audit: all section counts ──
    print(f"\n{'=' * 60}")
    print("C4 AUDIT — Section Counts")
    print("=" * 60)

    current_section = None
    section_counts = {}
    for row in audit_rows:
        row_text = " ".join(str(c) for c in row) if row else ""
        if row_text.strip().startswith("==="):
            current_section = row_text.strip()
            section_counts[current_section] = 0
        elif current_section and row and row[0]:
            # Skip header-like rows
            if row[0] not in ("Company", ""):
                section_counts[current_section] = section_counts.get(current_section, 0) + 1

    for section, count in section_counts.items():
        print(f"  {section:45s} {count:5d}")


if __name__ == "__main__":
    main()
