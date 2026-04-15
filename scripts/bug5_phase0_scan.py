#!/usr/bin/env python3
"""Phase 0 scan: inventory Leads from Research + pull Archdiocese snapshot.
Temporary diagnostic script — not committed."""
import os, json
from pathlib import Path

# Manual .env load (dotenv.find_dotenv breaks with stdin)
for line in Path(__file__).resolve().parent.parent.joinpath(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
)
svc = build('sheets', 'v4', credentials=creds)
sheet_id = os.environ['GOOGLE_SHEETS_ID']

resp = svc.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="'Leads from Research'!A1:Z5000"
).execute()
values = resp.get('values', [])
headers = values[0] if values else []
print(f"Header cols ({len(headers)}): {headers}")
print(f"Total data rows: {len(values) - 1 if values else 0}")

dn_idx = headers.index("District Name") if "District Name" in headers else -1
email_idx = headers.index("Email") if "Email" in headers else -1
src_idx = headers.index("Source URL") if "Source URL" in headers else -1

# HIGH-13 (S70) fail-fast: Python allows negative indexing, so a `-1` sentinel
# would pass the downstream `*_idx < len(row)` guards and silently read the
# LAST column of every row as if it were District Name / Email / Source URL.
# Crash loudly instead, naming the missing column(s) so schema drift is obvious.
_missing = [
    name for name, idx in (("District Name", dn_idx),
                           ("Email", email_idx),
                           ("Source URL", src_idx)) if idx < 0
]
if _missing:
    raise SystemExit(
        f"Header missing required columns: {_missing}. Got headers={headers}. "
        f"Refusing to run — fix the 'Leads from Research' tab schema first."
    )

# Archdiocese snapshot
archdiocese = []
for i, row in enumerate(values[1:], start=2):
    dn = row[dn_idx] if dn_idx < len(row) else ""
    if "archdiocese" in dn.lower() and "chicago" in dn.lower():
        d = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}
        d["__row__"] = i
        d["expected"] = "keep"  # default
        archdiocese.append(d)

print(f"\nArchdiocese rows: {len(archdiocese)}")

# Mark the known-bad rows
for r in archdiocese:
    email = r.get("Email", "").lower()
    src = r.get("Source URL", "").lower()
    if "rowva" in email or "rowva" in src:
        r["expected"] = "drop"
        r["known_bad_reason"] = "ROWVA CUSD 208 — unrelated public district in IL"
    elif "chsd218" in email or "chsd218" in src:
        r["expected"] = "drop"
        r["known_bad_reason"] = "Community High School District 218 — unrelated public district in IL"

known_bad = [r for r in archdiocese if r.get("expected") == "drop"]
print(f"Known-bad rows marked: {len(known_bad)}")
for r in known_bad:
    print(f"  row {r['__row__']}: {r.get('First Name','')} {r.get('Last Name','')} | {r.get('Email','')} | {r.get('Source URL','')[:70]}")

# Write snapshot
out_dir = Path(__file__).resolve().parent
(out_dir / "bug5_oracle_archdiocese.json").write_text(json.dumps(archdiocese, indent=2))
print(f"\nWrote {out_dir}/bug5_oracle_archdiocese.json ({len(archdiocese)} rows)")

# Clean sample: rows where email domain contains a hint derived from District Name
from collections import Counter
dn_counts = Counter(row[dn_idx] for row in values[1:] if dn_idx < len(row) and row[dn_idx])
print(f"\nUnique District Name values in tab: {len(dn_counts)}")
print("Top 15:")
for name, count in dn_counts.most_common(15):
    print(f"  {count:>4}  {name}")

# Build a simple hint function (same logic as the plan helpers)
def hint(name: str) -> str:
    h = name.lower()
    for suf in [" isd", " unified school district", " school district", " public schools",
                " city schools", " county schools", " academy", " catholic schools", " schools"]:
        if h.endswith(suf):
            h = h[:-len(suf)]
            break
    for pre in ["archdiocese of ", "diocese of "]:
        if h.startswith(pre):
            h = h[len(pre):]
    return h.replace(" ", "").strip()

# Find 20 clean-sample rows: email domain contains hint, source host contains hint
clean_candidates = []
for i, row in enumerate(values[1:], start=2):
    dn = row[dn_idx] if dn_idx < len(row) else ""
    email = (row[email_idx] if email_idx < len(row) else "").lower()
    src = (row[src_idx] if src_idx < len(row) else "").lower()
    if not dn or not email or "@" not in email:
        continue
    h = hint(dn)
    if len(h) < 5:
        continue
    email_dom = email.split("@", 1)[1]
    from urllib.parse import urlparse
    src_host = urlparse(src).netloc.lower().replace("www.", "")
    if h in email_dom and h in src_host:
        d = {k: (row[j] if j < len(row) else "") for j, k in enumerate(headers)}
        d["__row__"] = i
        d["expected"] = "keep"
        d["hint"] = h
        clean_candidates.append(d)

# Pick 20: first pass takes one per district for diversity, second pass fills.
seen_districts = set()
clean_sample = []
for c in clean_candidates:
    dn = c.get("District Name", "")
    if dn not in seen_districts:
        seen_districts.add(dn)
        clean_sample.append(c)
    if len(clean_sample) >= 20: break
# Second pass: fill remaining slots with non-first-seen rows
for c in clean_candidates:
    if len(clean_sample) >= 20: break
    if c not in clean_sample:
        clean_sample.append(c)

print(f"\nClean-sample candidates (hint in both email+source): {len(clean_candidates)}")
print(f"Diversified clean sample (≤1 per district): {len(clean_sample)}")
for c in clean_sample[:25]:
    print(f"  row {c['__row__']}: {c.get('District Name','')[:40]!r:<42} | hint={c['hint']!r:<20} | {c.get('Email','')[:40]}")

(out_dir / "bug5_oracle_clean_sample.json").write_text(json.dumps(clean_sample, indent=2))
print(f"\nWrote {out_dir}/bug5_oracle_clean_sample.json ({len(clean_sample)} rows)")
