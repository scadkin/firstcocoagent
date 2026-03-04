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


def _ensure_tab():
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_ACTIVE_ACCOUNTS not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_ACTIVE_ACCOUNTS}}}]}
        ).execute()

    # Always write headers so they stay in sync with ACTIVE_ACCOUNTS_COLUMNS
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_ACTIVE_ACCOUNTS}'!A1",
        valueInputOption="RAW",
        body={"values": [ACTIVE_ACCOUNTS_COLUMNS]}
    ).execute()

    return service, sheet_id


def _parse_csv(csv_text: str) -> list[dict]:
    """
    Parse Salesforce CSV text into a list of normalized dicts.
    Keys are normalized using _SF_COL_MAP.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    records = []
    for raw_row in reader:
        row = {}
        for col, val in raw_row.items():
            key = _SF_COL_MAP.get(col.strip().lower())
            if key:
                row[key] = (val or "").strip()
        if row.get("account_name"):
            records.append(row)
    return records


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

# Regex to detect "School Name (District Abbrev)" format
_PAREN_DISTRICT_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")


def normalize_name(name: str) -> str:
    """
    Return a normalized lowercase key for matching.
    Strips common school district suffixes, parenthetical district tags,
    punctuation, and extra whitespace.

    Examples:
      "Medina Valley ISD"                        → "medina valley"
      "AUSTIN INDEPENDENT SCHOOL DISTRICT"       → "austin"
      "Elk Grove Unified School District"        → "elk grove"
      "Jefferson Elementary (Medina Valley ISD)" → "jefferson elementary"
    """
    key = name.strip()
    # Strip parenthetical district tag before normalizing
    m = _PAREN_DISTRICT_RE.match(key)
    if m:
        key = m.group(1).strip()
    key = key.lower()
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
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SCHOOL_NAME_RE = re.compile(
    r"\b(elementary|middle\s+school|high\s+school|junior\s+high|"
    r"academy|charter|magnet|preparatory|prep\s+school|primary\s+school|k-12)\b",
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
      6. Name contains school keywords → school
      7. Name contains district keywords → district
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
    m = _PAREN_DISTRICT_RE.match(name)
    if m:
        return "school"

    # 6. School keywords in name (no parent → standalone school or charter)
    if _SCHOOL_NAME_RE.search(name):
        return "school"

    # 7. District keywords in name
    if _DISTRICT_NAME_RE.search(name):
        return "district"

    # 8. Default: unknown → company (safe — won't pollute district reports)
    return "company"


# ─────────────────────────────────────────────
# IMPORT — CLEAR + REWRITE
# ─────────────────────────────────────────────

def import_accounts(csv_text: str) -> dict:
    """
    Parse Salesforce active accounts CSV and write to the "Active Accounts" tab.
    Clears the tab first (except header), then writes fresh.

    Returns:
      {imported: N, districts: N, schools: N, libraries: N, companies: N,
       skipped: N, errors: list[str]}
    """
    errors = []
    imported = 0
    type_counts: dict[str, int] = {"district": 0, "school": 0, "library": 0, "company": 0}
    skipped = 0

    try:
        records = _parse_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0, "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "districts": 0, "schools": 0, "libraries": 0,
                "companies": 0, "skipped": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

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

        row = [
            name_key,
            account_name,
            parent,
            sf_type,
            acct_type,
            rec.get("open_renewal", ""),
            rec.get("opportunities", ""),
            rec.get("active_licenses", ""),
            rec.get("revenue_2025", ""),
            rec.get("lifetime_revenue", ""),
            rec.get("last_activity", ""),
            rec.get("last_modified", ""),
            rec.get("state", ""),
        ]
        rows_to_write.append(row)
        imported += 1
        type_counts[acct_type] = type_counts.get(acct_type, 0) + 1

    try:
        service, sheet_id = _ensure_tab()

        # Clear existing data (keep header)
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A2:Z",
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
# QUERIES
# ─────────────────────────────────────────────

def _load_all_accounts() -> list[dict]:
    """Load all rows from Active Accounts tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVE_ACCOUNTS}'!A:M"
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
    Return district-level accounts that have at least one school linked under them.
    This is the key input for Phase 6D call list prioritization.

    Returns list of dicts:
      {display_name, name_key, state, active_licenses, opportunities,
       school_count, schools: [{display_name, active_licenses}]}
    """
    accounts = _load_all_accounts()

    # Build parent → list of schools mapping
    schools_by_parent: dict[str, list[dict]] = {}
    for acct in accounts:
        parent = acct.get("Parent Account", "").strip()
        if parent:
            if parent not in schools_by_parent:
                schools_by_parent[parent] = []
            schools_by_parent[parent].append({
                "display_name":    acct.get("Display Name", ""),
                "active_licenses": acct.get("Active Licenses", ""),
            })

    # Build districts that appear as parent accounts
    result = []
    for acct in accounts:
        if acct.get("Account Type", "").lower() != "district":
            continue
        display = acct.get("Display Name", "")
        children = schools_by_parent.get(display, [])
        if not children:
            continue  # district exists but no linked schools
        result.append({
            "display_name":    display,
            "name_key":        acct.get("Name Key", ""),
            "state":           acct.get("State", ""),
            "active_licenses": acct.get("Active Licenses", ""),
            "opportunities":   acct.get("Opportunities", ""),
            "school_count":    len(children),
            "schools":         children,
        })

    # Sort by school count descending (most active first)
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
