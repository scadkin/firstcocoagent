#!/usr/bin/env python3
"""
Session 54 Phase 2 — Full fingerprint audit of Prospecting Queue.

Classifies every row by the TUPLE of its non-empty positions, so we can
see whether scrambled rows share one pattern or multiple.

Read-only.
"""
import json, os
from collections import Counter, defaultdict
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
sheet_id = os.environ["GOOGLE_SHEETS_ID"]

r = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range="'Prospecting Queue'!A:T",
).execute()
rows = r.get("values", [])

STRATEGIES = {
    "upward", "cold", "winback", "cold_license_request", "trigger",
    "competitor_displacement", "csta_partnership", "charter_cmo",
    "cte_center", "private_school_network", "compliance_gap",
    "intra_district", "cs_funding_recipient", "homeschool_coop",
    "proximity", "esa_cluster", "sequence_reengagement",
    "webinar_attendee", "webinar_missed",
}
STATUSES = {"pending", "approved", "researching", "draft", "complete", "skipped"}
SOURCES = {
    "web_search", "manual", "upward_auto", "pipeline_closed", "outreach",
    "signal", "proximity_auto", "expansion_auto", "compliance_scan",
}


def fingerprint(row):
    """Return tuple of (filled_positions, strategy_index) for a row."""
    padded = row + [""] * max(0, 20 - len(row))
    filled = tuple(i for i, v in enumerate(padded[:20]) if str(v).strip() != "")
    strat_idx = next((i for i, v in enumerate(padded[:20]) if str(v).strip() in STRATEGIES), -1)
    status_idx = next((i for i, v in enumerate(padded[:20]) if str(v).strip() in STATUSES), -1)
    source_idx = next((i for i, v in enumerate(padded[:20]) if str(v).strip() in SOURCES), -1)
    return filled, strat_idx, status_idx, source_idx


# Scan all rows
by_filled = Counter()
by_strat_idx = Counter()
# Group rows by (strat_idx, status_idx, source_idx) signature
sig_groups = defaultdict(list)
# Break down each strategy across signatures
strat_by_sig = defaultdict(lambda: Counter())
# By date range
oldest_by_sig = {}
newest_by_sig = {}

header = rows[0]
data_rows = rows[1:]
print(f"Header ({len(header)} cols): {header}")
print(f"Data rows: {len(data_rows)}\n")

for i, row in enumerate(data_rows):
    filled, strat_idx, status_idx, source_idx = fingerprint(row)
    by_filled[filled] += 1
    by_strat_idx[strat_idx] += 1
    sig = (strat_idx, status_idx, source_idx)
    sig_groups[sig].append(i + 2)  # sheet row number

    padded = row + [""] * max(0, 20 - len(row))
    strat_val = padded[strat_idx] if strat_idx >= 0 else ""
    strat_by_sig[sig][strat_val] += 1

    # Try to find the date cell — it's col M (idx 12) in canonical, col O (idx 14) in Lackland scramble
    date_str = ""
    for idx in (12, 14, 13):
        if idx < len(padded) and padded[idx].startswith("2026-"):
            date_str = padded[idx][:10]
            break
    if date_str:
        if sig not in oldest_by_sig or date_str < oldest_by_sig[sig]:
            oldest_by_sig[sig] = date_str
        if sig not in newest_by_sig or date_str > newest_by_sig[sig]:
            newest_by_sig[sig] = date_str


print("━" * 70)
print("SIGNATURE GROUPS (strategy_idx, status_idx, source_idx):")
print("━" * 70)
for sig, row_nums in sorted(sig_groups.items(), key=lambda x: -len(x[1])):
    strat_idx, status_idx, source_idx = sig
    print(f"\n  Signature: strategy@{strat_idx} status@{status_idx} source@{source_idx} "
          f"── {len(row_nums)} rows")
    print(f"    Date range: {oldest_by_sig.get(sig, '?')} → {newest_by_sig.get(sig, '?')}")
    print(f"    Sample rows: {row_nums[:3]} ... {row_nums[-3:]}")
    print(f"    Strategy distribution (top 10):")
    for s, c in strat_by_sig[sig].most_common(10):
        print(f"      {s or '(none)':<28} {c}")

print("\n" + "━" * 70)
print("UNIQUE FILLED-POSITION TUPLES (top 10):")
print("━" * 70)
for tup, c in by_filled.most_common(10):
    print(f"  {c:>5} rows │ filled={list(tup)}")
