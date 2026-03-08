"""
tools/csv_importer.py — Scout Phase 6C Salesforce CSV import.

Parses Salesforce "Active Accounts" CSV exports into the "Active Accounts"
tab of the Master Google Sheet.

Triggered by:
  - Steven sending a .csv file in Telegram
  - Claude tool: import_accounts

Salesforce CSV columns (12):
  Billing State/Province | Account Name | Parent Account | Open Renewal |
  # of Opportunities | # of Active Licenses | 2025 Revenue | Lifetime Revenue |
  Last Activity | Last Modified Date | Type | Billing State/Province (text)

Classification (Account Type column):
  Uses Salesforce Type field first, then name-based heuristics.
  Values: district | school | library | company

  district  — name ends in ISD, USD, CISD, SD, "District", "Public Schools", or
              a number suffix (e.g. "CUSD 300"); or SF Type contains "district"
  school    — has a parent account; or name contains Elementary/Academy/High School/
              etc.; or name matches "School Name (District Abbrev)" pattern
  library   — name or SF Type contains "library"
  company   — anything else (businesses, nonprofits, universities, etc.)

Usage (module-level, not a class):
  import tools.csv_importer as csv_importer
  result = csv_importer.import_accounts(csv_text)
"""

import csv
import io
import json
import logging
import os
import re
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_ACTIVE_ACCOUNTS = "Active Accounts"

ACTIVE_ACCOUNTS_COLUMNS = [
    "Name Key",           # normalized lowercase — used for matching
    "Display Name",       # original Salesforce Account Name
    "Parent Account",     # district name if this is a school; blank if district/top-level
    "SF Type",            # raw Salesforce Type field
    "Account Type",       # classified: district | school | library | company
    "Open Renewal",       # dollar amount or blank
    "Opportunities",      # count
    "Active Licenses",    # count
    "2025 Revenue",
    "Lifetime Revenue",
    "Last Activity",
    "Last Modified",
    "State",
]

# Salesforce CSV column name aliases (Salesforce exports vary slightly)
_SF_COL_MAP = {
    "billing state/province":  "state",
    "account name":            "account_name",
    "parent account":          "parent_account",
    "open renewal":            "open_renewal",
    "# of opportunities":      "opportunities",
    "# of active licenses":    "active_licenses",
    "2025 revenue":            "revenue_2025",
    "lifetime revenue":        "lifetime_revenue",
    "last activity":           "last_activity",
    "last modified date":      "last_modified",
    "type":                    "type",
}


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _get_sheet_id():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID not set")
    return sheet_id


def _ensure_tab(headers: list[str] | None = None):
    """Create Active Accounts tab if missing. Write header row.
    If headers is None, uses ACTIVE_ACCOUNTS_COLUMNS (base columns only).
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_ACTIVE_ACCOUNTS not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_ACTIVE_ACCOUNTS}}}]}
        ).execute()

    header_row = headers if headers else ACTIVE_ACCOUNTS_COLUMNS
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1",
        valueInputOption="RAW",
        body={"values": [header_row]}
    ).execute()

    return service, sheet_id


def _parse_csv(csv_text: str) -> tuple[list[dict], list[str]]:
    """
    Parse Salesforce CSV text into normalized dicts.
    Known columns get mapped keys via _SF_COL_MAP; unknown columns keep
    their original CSV header name so they pass through to the sheet.

    Returns (records, extra_col_names) where extra_col_names are CSV headers
    not in _SF_COL_MAP (preserved for dynamic sheet columns).
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    csv_headers = [h.strip() for h in (reader.fieldnames or [])]
    mapped_lower = set(_SF_COL_MAP.keys())
    extra_cols = [h for h in csv_headers if h and h.strip().lower() not in mapped_lower]

    records = []
    for raw_row in reader:
        row = {}
        for col, val in raw_row.items():
            col_clean = col.strip()
            mapped = _SF_COL_MAP.get(col_clean.lower())
            if mapped:
                row[mapped] = (val or "").strip()
            elif col_clean:
                row[col_clean] = (val or "").strip()
        if row.get("account_name"):
            records.append(row)
    return records, extra_cols


def _build_row_for_headers(headers: list[str], rec: dict, name_key: str, acct_type: str) -> list:
    """Build a sheet row matching the given headers from a parsed CSV record."""
    base_map = {
        "Name Key": name_key,
        "Display Name": rec.get("account_name", ""),
        "Parent Account": rec.get("parent_account", ""),
        "SF Type": rec.get("type", ""),
        "Account Type": acct_type,
        "Open Renewal": rec.get("open_renewal", ""),
        "Opportunities": rec.get("opportunities", ""),
        "Active Licenses": rec.get("active_licenses", ""),
        "2025 Revenue": rec.get("revenue_2025", ""),
        "Lifetime Revenue": rec.get("lifetime_revenue", ""),
        "Last Activity": rec.get("last_activity", ""),
        "Last Modified": rec.get("last_modified", ""),
        "State": rec.get("state", ""),
    }
    row = []
    for h in headers:
        if h in base_map:
            row.append(base_map[h])
        else:
            # Extra column — value stored under original CSV header name
            row.append(rec.get(h, ""))
    return row


# ─────────────────────────────────────────────
# NAME NORMALIZATION
# ─────────────────────────────────────────────

# Suffixes to strip for clean matching against research engine results
_SUFFIX_PATTERNS = [
    r"\bindependent school district\b",
    r"\bunified school district\b",
    r"\bschool district\b",
    r"\bpublic schools\b",
    r"\bpublic school\b",
    r"\bcommunity school district\b",
    r"\bcommunity unit school district\b",
    r"\bcommunity schools\b",
    r"\bschools\b",
    r"\bdistrict\b",
    r"\bunified\b",  # "Los Angeles Unified" → "los angeles"
    r"\bisd\b",
    r"\busd\b",
    r"\bcusd\b",
    r"\bcisd\b",
    r"\bgisd\b",
    r"\bnisd\b",
    r"\brsd\b",
    r"\bccsd\b",
    r"\bcsd\b",
    r"\bmusd\b",
    r"\bpusd\b",
    r"\bsusd\b",
    r"\bdisd\b",
    r"\s+\d+\s*$",   # trailing number e.g. "CUSD 300"
]

# Known district abbreviations → canonical expanded name (lowercase).
# Used by normalize_name so "LAUSD" and "Los Angeles Unified School District"
# both normalize to the same key ("los angeles").
_KNOWN_ABBREVIATIONS: dict[str, str] = {
    "lausd":  "los angeles unified school district",
    "lausd":  "los angeles unified school district",
    "hisd":   "houston independent school district",
    "aisd":   "austin independent school district",
    "disd":   "dallas independent school district",
    "pisd":   "plano independent school district",
    "fisd":   "frisco independent school district",
    "lisd":   "lewisville independent school district",
    "cfbisd": "cypress fairbanks independent school district",
    "neisd":  "north east independent school district",
    "nwisd":  "northwest independent school district",
    "misd":   "midland independent school district",
    "episd":  "el paso independent school district",
    "saisd":  "san antonio independent school district",
    "fwisd":  "fort worth independent school district",
    "bisd":   "beaumont independent school district",
    "sdusd":  "san diego unified school district",
    "sfusd":  "san francisco unified school district",
    "ousd":   "oakland unified school district",
    "fusd":   "fresno unified school district",
    "rusd":   "riverside unified school district",
    "sbusd":  "santa barbara unified school district",
    "vusd":   "ventura unified school district",
    "cusd":   "capistrano unified school district",
    "iusd":   "irvine unified school district",
    "svusd":  "saddleback valley unified school district",
    "pvusd":  "pajaro valley unified school district",
    "cps":    "chicago public schools",
    "nycdoe": "new york city department of education",
    "dcps":   "district of columbia public schools",
}

# Regex to detect "School Name (District Abbrev)" format
_PAREN_DISTRICT_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")


def normalize_name(name: str) -> str:
    """
    Return a normalized lowercase key for matching.
    Strips common school district suffixes, parenthetical district tags,
    punctuation, and extra whitespace. Expands known abbreviations first
    so e.g. "LAUSD" and "Los Angeles Unified School District" produce the
    same key ("los angeles").

    Examples:
      "Medina Valley ISD"                        → "medina valley"
      "AUSTIN INDEPENDENT SCHOOL DISTRICT"       → "austin"
      "Elk Grove Unified School District"        → "elk grove"
      "Los Angeles Unified"                      → "los angeles"
      "LAUSD"                                    → "los angeles"
      "Jefferson Elementary (Medina Valley ISD)" → "jefferson elementary"
    """
    key = name.strip()
    # Strip parenthetical district tag before normalizing
    m = _PAREN_DISTRICT_RE.match(key)
    if m:
        key = m.group(1).strip()
    key = key.lower()
    # Expand known abbreviations (e.g. "lausd" → full name, then strip suffixes)
    key_clean = re.sub(r"[^\w\s]", "", key).strip()
    if key_clean in _KNOWN_ABBREVIATIONS:
        key = _KNOWN_ABBREVIATIONS[key_clean]
    for pattern in _SUFFIX_PATTERNS:
        key = re.sub(pattern, "", key, flags=re.IGNORECASE)
    # Remove punctuation except spaces
    key = re.sub(r"[^\w\s]", "", key)
    # Collapse whitespace
    key = re.sub(r"\s+", " ", key).strip()
    return key


# ─────────────────────────────────────────────
# ACCOUNT CLASSIFICATION
# ─────────────────────────────────────────────

# Salesforce Type values that map to each category
_SF_TYPE_DISTRICT = {"school district"}
_SF_TYPE_SCHOOL   = {"k-12 school", "charter school", "private school", "public school",
                     "elementary school", "middle school", "high school", "school"}
_SF_TYPE_LIBRARY  = {"library", "public library"}

# Name-pattern lists (applied to lowercased name)
_DISTRICT_NAME_RE = re.compile(
    r"""
    \b(
        independent\s+school\s+district |
        unified\s+school\s+district     |
        community\s+(unit\s+)?school\s+district |
        school\s+district               |
        public\s+schools                |   # "Chicago Public Schools"
        isd | usd | cisd | gisd | nisd  |
        cusd | rsd | ccsd | csd         |
        musd | pusd | susd | disd       |
        \w+usd | \w+isd                 |   # LAUSD, CFBISD, etc.
        district
    )\b
    | \b\d+\s*$                             # trailing number "CUSD 300"
    | \bschools\s*$                         # ends in "schools" (plural) → district
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SCHOOL_NAME_RE = re.compile(
    r"\b(elementary|middle\s+school|high\s+school|junior\s+high|"
    r"academy|charter|magnet|preparatory|prep\s+school|primary\s+school|k-12|"
    r"school|sch)\b",    # "school" anywhere; "sch" abbreviation (e.g. "Sch of Excellence")
    re.IGNORECASE,
)

_LIBRARY_NAME_RE = re.compile(r"\blibrar(y|ies)\b", re.IGNORECASE)

_COMPANY_NAME_RE = re.compile(
    r"\b(inc\.?|llc\.?|corp\.?|ltd\.?|foundation|association|university|college)\b",
    re.IGNORECASE,
)


def classify_account(account_name: str, parent_account: str, sf_type: str) -> str:
    """
    Classify an account as 'district', 'school', 'library', or 'company'.

    Priority:
      1. Salesforce Type field (if recognized)
      2. Has a parent account → school
      3. Name contains library keywords → library
      4. Name is a company/org → company
      5. Name matches "School Name (District Abbrev)" pattern → school
      6. Name contains district keywords → district  ← before school to avoid
         "Austin Independent School District" matching "school" first
      7. Name contains school keywords → school
         (ends in "school"; contains "school" or "sch")
      8. Default → company (unknown, treated as non-district to be safe)
    """
    name   = (account_name or "").strip()
    parent = (parent_account or "").strip()
    sft    = (sf_type or "").strip().lower()

    # 1. Salesforce Type takes priority when it's specific
    if sft in _SF_TYPE_DISTRICT or "district" in sft:
        return "district"
    if sft in _SF_TYPE_SCHOOL:
        return "school"
    if sft in _SF_TYPE_LIBRARY or "library" in sft:
        return "library"

    # 2. Has a parent account → it's a sub-unit (almost always a school)
    if parent:
        return "school"

    # 3. Library by name
    if _LIBRARY_NAME_RE.search(name):
        return "library"

    # 4. Company/org by name
    if _COMPANY_NAME_RE.search(name):
        return "company"

    # 5. "School Name (District Abbrev)" pattern → school
    #    Must come before district check so ISD/USD inside parens doesn't win
    m = _PAREN_DISTRICT_RE.match(name)
    if m:
        return "school"

    # 6. District keywords — checked before school keywords so names like
    #    "Austin Independent School District" aren't caught by "school" first
    if _DISTRICT_NAME_RE.search(name):
        return "district"

    # 7. School keywords: ends in "school", contains "school" or "sch"
    if _SCHOOL_NAME_RE.search(name):
        return "school"

    # 8. Default: unknown → company (safe — won't pollute district reports)
    return "company"


# ─────────────────────────────────────────────
# IMPORT — CLEAR + REWRITE
# ─────────────────────────────────────────────

def import_accounts(csv_text: str) -> dict:
    """
    Parse Salesforce active accounts CSV and write to the "Active Accounts" tab.
    Clears the tab first (except header), then writes fresh.
    Preserves ALL CSV columns — base columns first, then extras.

    Returns:
      {imported: N, districts: N, schools: N, libraries: N, companies: N,
       skipped: N, errors: list[str]}
    """
    errors = []
    imported = 0
    type_counts: dict[str, int] = {"district": 0, "school": 0, "library": 0, "company": 0}
    skipped = 0

    try:
        records, extra_cols = _parse_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    full_headers = ACTIVE_ACCOUNTS_COLUMNS + [c for c in extra_cols if c not in ACTIVE_ACCOUNTS_COLUMNS]

    rows_to_write = []
    for rec in records:
        account_name = rec.get("account_name", "").strip()
        if not account_name:
            skipped += 1
            continue

        parent   = rec.get("parent_account", "").strip()
        sf_type  = rec.get("type", "").strip()
        acct_type = classify_account(account_name, parent, sf_type)
        name_key  = normalize_name(account_name)

        row = _build_row_for_headers(full_headers, rec, name_key, acct_type)
        rows_to_write.append(row)
        imported += 1
        type_counts[acct_type] = type_counts.get(acct_type, 0) + 1

    try:
        service, sheet_id = _ensure_tab(full_headers)

        # Clear existing data (keep header)
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A2:ZZ",
        ).execute()

        # Write new data
        if rows_to_write:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{TAB_ACTIVE_ACCOUNTS}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows_to_write}
            ).execute()

        logger.info(
            f"Imported {imported} accounts — "
            + ", ".join(f"{v} {k}s" for k, v in type_counts.items() if v)
        )

    except Exception as e:
        errors.append(f"Sheet write failed: {e}")
        logger.error(f"import_accounts sheet write error: {e}")

    return {
        "imported":   imported,
        "districts":  type_counts.get("district", 0),
        "schools":    type_counts.get("school", 0),
        "libraries":  type_counts.get("library", 0),
        "companies":  type_counts.get("company", 0),
        "skipped":    skipped,
        "errors":     errors,
    }


# ─────────────────────────────────────────────
# IMPORT — MERGE (add new / update existing)
# ─────────────────────────────────────────────

def merge_accounts(csv_text: str) -> dict:
    """
    Parse Salesforce CSV and merge into Active Accounts tab.
    - Existing rows matched by Name Key are updated in place.
    - New rows are appended.
    - Rows not in the CSV are left untouched.
    - New CSV columns not already in the sheet are appended as extra columns.

    Returns same shape as import_accounts() plus updated/added counts.
    """
    errors = []
    type_counts: dict[str, int] = {"district": 0, "school": 0, "library": 0, "company": 0}
    skipped = 0
    updated = 0
    added = 0

    try:
        records, extra_cols = _parse_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "updated": 0, "added": 0,
                "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "updated": 0, "added": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Load existing sheet (all columns)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1:ZZ"
        ).execute()
        existing_rows = result.get("values", [])
        existing_headers = existing_rows[0] if existing_rows else ACTIVE_ACCOUNTS_COLUMNS
        data_rows = existing_rows[1:] if len(existing_rows) > 1 else []

        # Compute full headers: existing + any new extras not already present
        full_headers = list(existing_headers)
        for col in extra_cols:
            if col not in full_headers:
                full_headers.append(col)

        # Pad existing data rows to match full_headers length
        for i, row in enumerate(data_rows):
            data_rows[i] = row + [""] * (len(full_headers) - len(row))

        # Build index of existing rows by Name Key (column 0)
        existing_by_key: dict[str, int] = {}
        for i, row in enumerate(data_rows):
            if row and row[0]:
                existing_by_key[row[0]] = i

        # Build new rows from CSV
        new_rows_by_key: dict[str, list] = {}
        for rec in records:
            account_name = rec.get("account_name", "").strip()
            if not account_name:
                skipped += 1
                continue

            parent   = rec.get("parent_account", "").strip()
            sf_type  = rec.get("type", "").strip()
            acct_type = classify_account(account_name, parent, sf_type)
            name_key  = normalize_name(account_name)

            row = _build_row_for_headers(full_headers, rec, name_key, acct_type)
            new_rows_by_key[name_key] = row
            type_counts[acct_type] = type_counts.get(acct_type, 0) + 1

        # Update existing, collect new
        append_rows = []
        for name_key, new_row in new_rows_by_key.items():
            if name_key in existing_by_key:
                idx = existing_by_key[name_key]
                data_rows[idx] = new_row
                updated += 1
            else:
                append_rows.append(new_row)
                added += 1

        # Write back everything (headers + updated rows + new rows)
        all_rows = [full_headers] + data_rows + append_rows
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1",
            valueInputOption="RAW",
            body={"values": all_rows}
        ).execute()

        # Clear any leftover rows below
        total_written = len(all_rows)
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A{total_written + 1}:ZZ",
        ).execute()

        logger.info(
            f"Merged {updated + added} accounts ({updated} updated, {added} new) — "
            + ", ".join(f"{v} {k}s" for k, v in type_counts.items() if v)
        )

    except Exception as e:
        errors.append(f"Sheet write failed: {e}")
        logger.error(f"merge_accounts sheet write error: {e}")

    return {
        "imported":   updated + added,
        "districts":  type_counts.get("district", 0),
        "schools":    type_counts.get("school", 0),
        "libraries":  type_counts.get("library", 0),
        "companies":  type_counts.get("company", 0),
        "skipped":    skipped,
        "updated":    updated,
        "added":      added,
        "errors":     errors,
    }


# ─────────────────────────────────────────────
# IMPORT — REPLACE BY STATE
# ─────────────────────────────────────────────

def replace_accounts_by_state(csv_text: str, state_code: str) -> dict:
    """
    Replace all accounts for a given state with data from the CSV.
    - Removes all existing rows where State == state_code (case-insensitive).
    - Inserts all rows from the CSV (which should already be filtered to that state).
    - Accounts from all other states are left completely untouched.
    - New CSV columns not already in the sheet are appended as extra columns.

    Returns same shape as merge_accounts() plus replaced count.
    """
    state_upper = state_code.strip().upper()
    errors = []
    type_counts: dict[str, int] = {"district": 0, "school": 0, "library": 0, "company": 0}
    skipped = 0
    replaced = 0
    added = 0

    try:
        records, extra_cols = _parse_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "replaced": 0, "added": 0,
                "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "replaced": 0, "added": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Load existing sheet (all columns)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1:ZZ"
        ).execute()
        existing_rows = result.get("values", [])
        existing_headers = existing_rows[0] if existing_rows else ACTIVE_ACCOUNTS_COLUMNS
        data_rows = existing_rows[1:] if len(existing_rows) > 1 else []

        # Find State column index in existing sheet
        state_col_idx = existing_headers.index("State") if "State" in existing_headers else -1

        # Keep rows that are NOT the target state
        kept_rows = []
        for row in data_rows:
            padded = row + [""] * (len(existing_headers) - len(row))
            row_state = padded[state_col_idx].strip().upper() if state_col_idx >= 0 else ""
            if row_state != state_upper:
                kept_rows.append(padded)
            else:
                replaced += 1

        # Extend headers with any new columns from the CSV
        full_headers = list(existing_headers)
        for col in extra_cols:
            if col not in full_headers:
                full_headers.append(col)

        # Pad kept rows to new header length
        for i, row in enumerate(kept_rows):
            kept_rows[i] = row + [""] * (len(full_headers) - len(row))

        # Build new rows from CSV
        new_rows = []
        for rec in records:
            account_name = rec.get("account_name", "").strip()
            if not account_name:
                skipped += 1
                continue
            parent   = rec.get("parent_account", "").strip()
            sf_type  = rec.get("type", "").strip()
            acct_type = classify_account(account_name, parent, sf_type)
            name_key  = normalize_name(account_name)
            row = _build_row_for_headers(full_headers, rec, name_key, acct_type)
            new_rows.append(row)
            added += 1
            type_counts[acct_type] = type_counts.get(acct_type, 0) + 1

        # Write back: header + kept rows (other states) + new rows (this state)
        all_rows = [full_headers] + kept_rows + new_rows
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1",
            valueInputOption="RAW",
            body={"values": all_rows}
        ).execute()

        # Clear any leftover rows below
        total_written = len(all_rows)
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A{total_written + 1}:ZZ",
        ).execute()

        logger.info(
            f"State-replace {state_upper}: removed {replaced} old rows, "
            f"added {added} new — "
            + ", ".join(f"{v} {k}s" for k, v in type_counts.items() if v)
        )

    except Exception as e:
        errors.append(f"Sheet write failed: {e}")
        logger.error(f"replace_accounts_by_state error: {e}")

    return {
        "imported":   added,
        "districts":  type_counts.get("district", 0),
        "schools":    type_counts.get("school", 0),
        "libraries":  type_counts.get("library", 0),
        "companies":  type_counts.get("company", 0),
        "skipped":    skipped,
        "replaced":   replaced,
        "added":      added,
        "errors":     errors,
    }


# ─────────────────────────────────────────────
# DEDUP
# ─────────────────────────────────────────────

def dedup_accounts() -> dict:
    """
    Remove duplicate rows from Active Accounts tab.
    Groups by Name Key (column 0). When duplicates exist, keeps the row
    with the most non-empty cells. Returns diagnostic info.

    Returns:
      {total_before, total_after, duplicates_removed, duplicate_names, errors}
    """
    errors = []
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1:ZZ"
        ).execute()
        existing_rows = result.get("values", [])
        if len(existing_rows) < 2:
            return {"total_before": 0, "total_after": 0,
                    "duplicates_removed": 0, "duplicate_names": [], "errors": []}

        headers = existing_rows[0]
        data_rows = existing_rows[1:]
        total_before = len(data_rows)

        # Find State column index so we can use Name Key + State as composite key
        state_col_idx = headers.index("State") if "State" in headers else -1

        # Group rows by composite key: Name Key (col 0) + "|" + State
        seen: dict[str, list[int]] = {}
        for i, row in enumerate(data_rows):
            name_key = row[0].strip().lower() if row and row[0] else f"__blank_{i}"
            state_val = row[state_col_idx].strip().upper() if state_col_idx >= 0 and len(row) > state_col_idx else ""
            composite_key = f"{name_key}|{state_val}"
            if composite_key not in seen:
                seen[composite_key] = []
            seen[composite_key].append(i)

        # For each group, pick the row with the most non-empty cells
        keep_indices: set[int] = set()
        duplicate_names: list[str] = []
        for name_key, indices in seen.items():
            if len(indices) == 1:
                keep_indices.add(indices[0])
            else:
                # Pick best row (most non-empty cells)
                best_idx = max(indices, key=lambda i: sum(1 for c in data_rows[i] if c.strip()))
                keep_indices.add(best_idx)
                # Get display name from the best row for reporting
                best_row = data_rows[best_idx]
                display = best_row[1] if len(best_row) > 1 and best_row[1] else name_key
                duplicate_names.append(f"{display} ({len(indices)} copies)")

        # Build deduped output preserving order
        deduped = [data_rows[i] for i in sorted(keep_indices)]
        total_after = len(deduped)
        removed = total_before - total_after

        if removed > 0:
            all_rows = [headers] + deduped
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1",
                valueInputOption="RAW",
                body={"values": all_rows}
            ).execute()
            # Clear leftover rows
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range=f"'{TAB_ACTIVE_ACCOUNTS}'!A{len(all_rows) + 1}:ZZ",
            ).execute()
            logger.info(f"Dedup: removed {removed} duplicates ({total_before} → {total_after})")

        return {
            "total_before": total_before,
            "total_after": total_after,
            "duplicates_removed": removed,
            "duplicate_names": duplicate_names,
            "errors": errors,
        }

    except Exception as e:
        errors.append(str(e))
        logger.error(f"dedup_accounts error: {e}")
        return {"total_before": 0, "total_after": 0,
                "duplicates_removed": 0, "duplicate_names": [], "errors": errors}


# ─────────────────────────────────────────────
# QUERIES
# ─────────────────────────────────────────────

def _load_all_accounts() -> list[dict]:
    """Load all rows from Active Accounts tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1:ZZ"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        accounts = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            accounts.append(dict(zip(headers, padded)))
        return accounts
    except Exception as e:
        logger.error(f"_load_all_accounts error: {e}")
        return []


def get_active_accounts(state_filter: str = "") -> list[dict]:
    """
    Return all active accounts, optionally filtered by state abbreviation.
    Each dict has keys matching ACTIVE_ACCOUNTS_COLUMNS.
    """
    accounts = _load_all_accounts()
    if not state_filter:
        return accounts
    sf = state_filter.strip().upper()
    return [a for a in accounts if a.get("State", "").upper() == sf]


def get_districts_with_schools() -> list[dict]:
    """
    Return parent districts that have active CodeCombat school accounts.
    These are the targeting signals for Phase 6D: we already have a foothold
    in the district via schools, so we pitch a district-wide deal.

    Logic:
      - Start from school accounts (Account Type == "school")
      - Group by their Parent Account (the district)
      - Exclude parent districts that already have a district-level deal
        (Account Type == "district" in Active Accounts — already owned)
      - Sort by school count descending — more active schools = higher priority

    Returns list of dicts:
      {display_name, name_key, state, school_count,
       schools: [{display_name, active_licenses}]}
    """
    accounts = _load_all_accounts()

    # Collect districts we already have deals with — exclude from targeting
    existing_district_keys: set[str] = set()
    for acct in accounts:
        if acct.get("Account Type", "").lower() == "district":
            existing_district_keys.add(normalize_name(acct.get("Display Name", "")))

    # Group school accounts by their Parent Account (the target district)
    schools_by_parent: dict[str, list[dict]] = {}
    for acct in accounts:
        if acct.get("Account Type", "").lower() != "school":
            continue
        parent = acct.get("Parent Account", "").strip()
        if not parent:
            continue
        if parent not in schools_by_parent:
            schools_by_parent[parent] = []
        schools_by_parent[parent].append({
            "display_name":    acct.get("Display Name", ""),
            "active_licenses": acct.get("Active Licenses", ""),
            "state":           acct.get("State", ""),
        })

    # Build targeting list — one entry per parent district, excluding existing deals
    result = []
    for parent_name, children in schools_by_parent.items():
        name_key = normalize_name(parent_name)
        if name_key in existing_district_keys:
            continue  # already have district-level deal — not a target
        state = next((s.get("state", "") for s in children if s.get("state")), "")
        result.append({
            "display_name": parent_name,
            "name_key":     name_key,
            "state":        state,
            "school_count": len(children),
            "schools":      children,
        })

    # Sort by school count descending — most active schools = best pitch
    result.sort(key=lambda x: x["school_count"], reverse=True)
    return result


def get_import_summary() -> str:
    """Return a one-line summary of what's in the Active Accounts tab."""
    try:
        accounts = _load_all_accounts()
        if not accounts:
            return "Active Accounts tab is empty — send a Salesforce CSV to import."
        counts: dict[str, int] = {}
        for a in accounts:
            t = a.get("Account Type", "company").lower()
            counts[t] = counts.get(t, 0) + 1
        parts = ", ".join(f"{v} {k}s" for k, v in sorted(counts.items()) if v)
        districts_with_schools = len(get_districts_with_schools())
        return (
            f"{len(accounts)} total accounts: {parts}. "
            f"{districts_with_schools} districts have active CodeCombat schools."
        )
    except Exception as e:
        return f"Could not read Active Accounts tab: {e}"
