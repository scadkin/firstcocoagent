#!/usr/bin/env python3
"""
Audit C4 Cold License Request prospects in the Prospecting Queue.
Breaks down by state, role bucket, entity type, and engagement.

Usage: python3 scripts/audit_c4_prospects.py
Requires: GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON env vars
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
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


# Role classification
TEACHER_KEYWORDS = [
    "teacher", "instructor", "coach", "tosa", "facilitator",
    "coding", "stem teacher", "cs teacher", "computer science teacher",
    "esports", "robotics", "game design", "web design", "engineering teacher",
    "makerspace", "digital learning coach", "instructional technology coach",
]
ADMIN_KEYWORDS = [
    "principal", "assistant principal", "vice principal", "head of school",
    "dean", "headmaster", "headmistress",
]
DISTRICT_KEYWORDS = [
    "superintendent", "director", "coordinator", "specialist",
    "curriculum", "cto", "cio", "ceo", "cao", "chief",
    "administrator", "manager", "supervisor",
    "technology", "innovation", "academic", "instruction",
    "stem director", "cs director", "cte director",
]
LIBRARY_KEYWORDS = [
    "librarian", "library", "media specialist", "media center",
]


def _classify_role_c4(title: str) -> str:
    """Classify a title into a role bucket."""
    t = title.lower().strip()
    if not t:
        return "unknown"
    # Library first (specific)
    for kw in LIBRARY_KEYWORDS:
        if kw in t:
            return "library_contact"
    # Admin (principals)
    for kw in ADMIN_KEYWORDS:
        if kw in t:
            return "admin"
    # District-level contacts
    for kw in DISTRICT_KEYWORDS:
        if kw in t:
            return "district_contact"
    # Teachers
    for kw in TEACHER_KEYWORDS:
        if kw in t:
            return "teacher"
    return "other"


def extract_title_from_notes(notes: str) -> str:
    """Extract title from Notes column (format: 'Title: ...' in pipe-separated notes)."""
    if not notes:
        return ""
    for part in notes.split("|"):
        part = part.strip()
        if part.startswith("Title:"):
            return part[6:].strip()
    return ""


def main():
    service = get_service()
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEETS_ID not set")
        sys.exit(1)

    print("Reading Prospecting Queue...")
    rows = read_tab(service, sheet_id, "'Prospecting Queue'!A:S")
    if len(rows) < 2:
        print("No data found")
        return

    headers = rows[0]
    print(f"Headers: {headers}")
    print(f"Total rows (incl header): {len(rows)}")

    # Parse into dicts
    prospects = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        prospects.append(dict(zip(headers, padded)))

    # Filter to C4 only
    c4 = [p for p in prospects if p.get("Strategy") == "cold_license_request"]
    print(f"\n{'='*60}")
    print(f"C4 Cold License Request prospects: {len(c4)}")
    print(f"Other prospects in queue: {len(prospects) - len(c4)}")
    print(f"{'='*60}")

    # --- State breakdown ---
    state_counts = Counter(p.get("State", "").strip() or "(empty)" for p in c4)
    print(f"\n--- STATE BREAKDOWN ({len(state_counts)} states) ---")
    for state, count in state_counts.most_common():
        print(f"  {state:6s}: {count}")

    # --- Entity type (Deal Level) breakdown ---
    entity_counts = Counter(p.get("Deal Level", "").strip() or "(empty)" for p in c4)
    print(f"\n--- ENTITY TYPE (Deal Level) ---")
    for entity, count in entity_counts.most_common():
        print(f"  {entity:20s}: {count}")

    # --- Role breakdown from titles in Notes ---
    titles = []
    role_counts = Counter()
    title_examples = defaultdict(list)

    for p in c4:
        title = extract_title_from_notes(p.get("Notes", ""))
        titles.append(title)
        role = _classify_role_c4(title)
        role_counts[role] += 1
        if len(title_examples[role]) < 5:
            title_examples[role].append(title or "(no title)")

    print(f"\n--- ROLE BREAKDOWN ---")
    for role, count in role_counts.most_common():
        pct = count / len(c4) * 100
        print(f"  {role:20s}: {count:5d} ({pct:.1f}%)")
        for ex in title_examples[role]:
            print(f"    ex: {ex}")

    # --- Title frequency (raw) ---
    title_counts = Counter(t.lower().strip() for t in titles if t)
    print(f"\n--- TOP 30 RAW TITLES ---")
    for title, count in title_counts.most_common(30):
        print(f"  {count:4d}x  {title}")

    # --- Status breakdown ---
    status_counts = Counter(p.get("Status", "").strip() or "(empty)" for p in c4)
    print(f"\n--- STATUS ---")
    for status, count in status_counts.most_common():
        print(f"  {status:15s}: {count}")

    # --- Cross-tab: Role x Entity ---
    print(f"\n--- ROLE x ENTITY TYPE ---")
    cross = defaultdict(Counter)
    for p in c4:
        title = extract_title_from_notes(p.get("Notes", ""))
        role = _classify_role_c4(title)
        entity = p.get("Deal Level", "").strip() or "(empty)"
        cross[role][entity] += 1

    # Print as a table
    entities = sorted(set(e for c in cross.values() for e in c))
    header_line = f"  {'Role':20s}" + "".join(f"{e:>12s}" for e in entities) + f"{'Total':>8s}"
    print(header_line)
    for role, ecounts in sorted(cross.items(), key=lambda x: -sum(x[1].values())):
        line = f"  {role:20s}"
        total = 0
        for e in entities:
            c = ecounts.get(e, 0)
            total += c
            line += f"{c:>12d}"
        line += f"{total:>8d}"
        print(line)

    # --- Cross-tab: Role x State (top states only) ---
    top_states = [s for s, _ in state_counts.most_common(8)]
    print(f"\n--- ROLE x STATE (top 8) ---")
    cross_state = defaultdict(Counter)
    for p in c4:
        title = extract_title_from_notes(p.get("Notes", ""))
        role = _classify_role_c4(title)
        state = p.get("State", "").strip() or "(empty)"
        cross_state[role][state] += 1

    header_line = f"  {'Role':20s}" + "".join(f"{s:>8s}" for s in top_states) + f"{'Other':>8s}{'Total':>8s}"
    print(header_line)
    for role, scounts in sorted(cross_state.items(), key=lambda x: -sum(x[1].values())):
        line = f"  {role:20s}"
        total = sum(scounts.values())
        other = total
        for s in top_states:
            c = scounts.get(s, 0)
            other -= c
            line += f"{c:>8d}"
        line += f"{other:>8d}{total:>8d}"
        print(line)

    # --- Engagement data from Notes ---
    print(f"\n--- ENGAGEMENT SIGNALS ---")
    has_opens = 0
    has_replies = 0
    has_email = 0
    for p in c4:
        notes = p.get("Notes", "")
        if "opens" in notes:
            has_opens += 1
        if "replies" in notes and "no reply" not in notes:
            has_replies += 1
        if p.get("Email", "").strip():
            has_email += 1

    print(f"  With email address: {has_email} / {len(c4)}")
    print(f"  Had opens:          {has_opens} / {len(c4)}")
    print(f"  Had replies:        {has_replies} / {len(c4)}")

    # --- Sample rows ---
    print(f"\n--- SAMPLE ROWS (first 5) ---")
    for p in c4[:5]:
        print(f"  {p.get('State','?'):5s} | {p.get('Account Name','?')[:30]:30s} | "
              f"{p.get('Deal Level','?'):10s} | {p.get('Email','')[:30]:30s} | "
              f"{p.get('First Name',''):10s} {p.get('Last Name',''):15s} | "
              f"Notes: {p.get('Notes','')[:80]}")


if __name__ == "__main__":
    main()
