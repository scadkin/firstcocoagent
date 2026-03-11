"""
tools/lead_importer.py — Salesforce Leads & Contacts CSV import + enrichment.

Two new tabs:
  - SF Leads    : imported from Salesforce Leads report
  - SF Contacts : imported from Salesforce Contacts report

These are SEPARATE from the existing Leads tab (research-generated contacts).

Auto-detect:
  - Lead CSV:    header contains 2+ of {Lead Source, Lead Status, Company}
  - Contact CSV: header contains 2+ of {Account Name, Department, Contact Owner}
    AND does NOT look like an account CSV (no # of Active Licenses / # of Opportunities)

Cross-check:
  - Each record checked against Active Accounts by email domain, account/company
    name, and district name matching.

Enrichment (async, background):
  - Web search to verify current role/school
  - Cross-check email domain against known domains
  - Update confidence + notes

Usage (module-level, not a class):
  import tools.lead_importer as lead_importer
  result = lead_importer.import_leads(csv_text)
  result = lead_importer.import_contacts(csv_text)
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
# HELPERS
# ─────────────────────────────────────────────

def _col_to_letter(col_idx: int) -> str:
    """Convert 0-based column index to spreadsheet letter (0=A, 25=Z, 26=AA, ...)."""
    result = ""
    idx = col_idx
    while idx >= 0:
        result = chr(idx % 26 + ord("A")) + result
        idx = idx // 26 - 1
    return result


def _append_in_chunks(service, sheet_id: str, tab_name: str, rows: list, errors: list,
                      chunk_size: int = 2000, num_cols: int = 0):
    """Append rows to a Sheets tab in chunks with retry.

    num_cols: if provided, uses a tight column range (A:{last_col}) to minimize
    cell allocation and avoid hitting the 10M cell limit.
    """
    import time
    if num_cols > 0:
        last_col = _col_to_letter(num_cols - 1)
        append_range = f"'{tab_name}'!A:{last_col}"
    else:
        append_range = f"'{tab_name}'!A:AZ"
    appended = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        chunk_num = i // chunk_size + 1
        for attempt in range(3):
            try:
                service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range=append_range,
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": chunk}
                ).execute()
                appended += len(chunk)
                logger.info(f"Appended chunk {chunk_num} ({len(chunk)} rows) to {tab_name}")
                break
            except Exception as e:
                logger.warning(f"{tab_name} chunk {chunk_num} attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    errors.append(f"{tab_name} chunk {chunk_num}: {e}")
    return appended


# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_SF_LEADS = "SF Leads"
TAB_SF_CONTACTS = "SF Contacts"
TAB_LEADS_ACTIVE = "Leads Assoc Active Accounts"
TAB_CONTACTS_ACTIVE = "Contacts Assoc Active Accounts"

# Base columns from Salesforce Leads report
SF_LEADS_COLUMNS = [
    "First Name",
    "Last Name",
    "Title",
    "Company",
    "Email",
    "Phone",
    "Lead Source",
    "Lead Status",
    "State/Province",
    "Street",
    "City",
    "Zip",
    "Description",
    "Created Date",
    # Enrichment columns (added by Scout)
    "Verified School",
    "Verified District",
    "Verified State",
    "Verified County",
    "Active Account Match",
    "Enrichment Status",
    "Enrichment Notes",
    "Last Enriched",
    "Date Imported",
]

# Base columns from Salesforce Contacts report
SF_CONTACTS_COLUMNS = [
    "First Name",
    "Last Name",
    "Title",
    "Account Name",
    "Email",
    "Phone",
    "Mailing State/Province",
    "Mailing City",
    "Department",
    "Contact Owner",
    "Created Date",
    # Enrichment columns (added by Scout)
    "Verified School",
    "Verified District",
    "Verified State",
    "Verified County",
    "Active Account Match",
    "Enrichment Status",
    "Enrichment Notes",
    "Last Enriched",
    "Date Imported",
]

# Salesforce CSV column mapping: CSV header (lowercase) → internal key
_SF_LEAD_COL_MAP = {
    "first name":           "first_name",
    "last name":            "last_name",
    "title":                "title",
    "company":              "company",
    "company / account":    "company",
    "email":                "email",
    "phone":                "phone",
    "lead source":          "lead_source",
    "lead status":          "lead_status",
    "lead owner":           "lead_owner",
    "state/province":       "state",
    "state":                "state",
    "street":               "street",
    "city":                 "city",
    "zip":                  "zip",
    "zip/postal code":      "zip",
    "description":          "description",
    "created date":         "created_date",
    "create date":          "created_date",
    "district name":        "district_name",
    "last activity":        "last_activity",
}

_SF_CONTACT_COL_MAP = {
    "first name":               "first_name",
    "last name":                "last_name",
    "title":                    "title",
    "account name":             "account_name",
    "email":                    "email",
    "secondary email":          "secondary_email",
    "phone":                    "phone",
    "mobile":                   "mobile",
    "mailing state/province":   "mailing_state",
    "mailing state/province (text only)": "mailing_state",
    "mailing state":            "mailing_state",
    "mailing city":             "mailing_city",
    "mailing street":           "mailing_street",
    "mailing zip/postal code":  "mailing_zip",
    "department":               "department",
    "contact owner":            "contact_owner",
    "account owner":            "account_owner",
    "parent account":           "parent_account",
    "district name":            "district_name",
    "created date":             "created_date",
    "last activity":            "last_activity",
    "billing state/province":   "billing_state",
}

# Headers that indicate an ACCOUNT csv (not leads/contacts)
_ACCOUNT_ONLY_HEADERS = {"# of active licenses", "# of opportunities"}


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


def _ensure_tab(tab_name: str, columns: list[str]):
    """Create tab if missing, always overwrite header row."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if tab_name not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        ).execute()
        logger.info(f"Created tab: {tab_name}")

    # Always overwrite headers (schema changes propagate immediately)
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": [columns]}
    ).execute()

    return service, sheet_id


def _to_title_case(name: str) -> str:
    """Convert ALL CAPS to Title Case, preserving known acronyms."""
    if not name or not name.isupper():
        return name
    _ACRONYMS = {"ISD", "USD", "CISD", "CUSD", "HS", "MS", "ES", "STEM", "CTE",
                 "CS", "AI", "IT", "PD", "AP", "LAUSD", "HISD", "DISD"}
    words = name.split()
    result = []
    for w in words:
        if w.upper() in _ACRONYMS:
            result.append(w.upper())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def _parse_csv_records(csv_text: str, col_map: dict) -> tuple[list[dict], list[str]]:
    """
    Parse CSV text into normalized dicts using the given column map.
    Unknown columns kept with original header name.
    Returns (records, extra_col_names).
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    csv_headers = [h.strip() for h in (reader.fieldnames or [])]
    mapped_lower = set(col_map.keys())
    extra_cols = [h for h in csv_headers if h and h.strip().lower() not in mapped_lower]

    records = []
    for raw_row in reader:
        row = {}
        for col, val in raw_row.items():
            col_clean = col.strip()
            mapped = col_map.get(col_clean.lower())
            if mapped:
                row[mapped] = (val or "").strip()
            elif col_clean:
                row[col_clean] = (val or "").strip()
        # Normalize names to title case
        for key in ("first_name", "last_name", "company", "account_name"):
            if row.get(key):
                row[key] = _to_title_case(row[key])
        if row.get("title"):
            row["title"] = _to_title_case(row["title"])
        records.append(row)
    return records, extra_cols


def _load_existing_keys(service, sheet_id: str, tab_name: str) -> tuple[set[str], set[str], list[list]]:
    """
    Load existing data from a tab.
    Returns (email_keys, name_keys, all_rows_including_header).
    email_keys: lowercase emails for dedup.
    name_keys: "first|last" for no-email dedup.
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A1:ZZ"
        ).execute()
    except Exception:
        return set(), set(), []

    rows = result.get("values", [])
    if len(rows) < 2:
        return set(), set(), rows

    headers = rows[0]
    email_keys = set()
    name_keys = set()

    try:
        fn_idx = headers.index("First Name")
        ln_idx = headers.index("Last Name")
        email_idx = headers.index("Email")
    except ValueError:
        return set(), set(), rows

    for row in rows[1:]:
        fn = row[fn_idx].lower().strip() if fn_idx < len(row) else ""
        ln = row[ln_idx].lower().strip() if ln_idx < len(row) else ""
        email = row[email_idx].lower().strip() if email_idx < len(row) else ""
        if email:
            email_keys.add(email)
        elif fn or ln:
            name_keys.add(f"{fn}|{ln}")

    return email_keys, name_keys, rows


# ─────────────────────────────────────────────
# CROSS-CHECK AGAINST ACTIVE ACCOUNTS
# ─────────────────────────────────────────────

_GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "me.com", "live.com", "msn.com", "comcast.net",
    "sbcglobal.net", "att.net", "verizon.net", "cox.net", "charter.net",
    "earthlink.net", "mac.com", "ymail.com", "protonmail.com",
}


def _extract_domain_root(email: str) -> str:
    """Extract meaningful root from an email domain.

    user@austinisd.org      → "austinisd"
    user@spring.k12.tx.us   → "spring"
    user@staff.austinisd.org → "austinisd"
    user@gmail.com           → ""
    """
    if not email or "@" not in email:
        return ""
    domain = email.split("@")[1].lower().strip()
    if domain in _GENERIC_DOMAINS:
        return ""
    # k12-style: name.k12.state.us
    parts = domain.split(".")
    if len(parts) >= 4 and parts[-1] == "us" and parts[-3] == "k12":
        return parts[0] if len(parts[0]) > 2 else ""
    # Standard: take second-level domain (handles staff.austinisd.org → austinisd)
    if len(parts) >= 3:
        return parts[-2] if len(parts[-2]) > 3 else ""
    if len(parts) >= 2:
        return parts[0] if len(parts[0]) > 3 else ""
    return ""


def _generate_domain_roots(account: dict) -> set[str]:
    """Generate plausible email domain roots from an account name.

    "Austin ISD"                              → {"austinisd", "austin", ...}
    "Elk Grove Unified School District"       → {"elkgroveusd", "elkgrove", "egusd", ...}
    "Los Angeles Unified School District"     → {"losangeles", "lausd", ...}
    "Cypress-Fairbanks ISD"                   → {"cypressfairbanksisd", "cfisd", ...}
    """
    from tools.csv_importer import normalize_name
    name = account.get("Display Name", "").lower()
    if not name:
        return set()

    # Remove punctuation, split into words
    clean = re.sub(r"[^\w\s]", "", name)
    words = clean.split()
    filler = {"the", "of", "and", "for", "in", "at"}
    words = [w for w in words if w not in filler]
    if not words:
        return set()

    roots = set()

    # Full concatenation: "austinisd"
    full = "".join(words)
    if len(full) > 3:
        roots.add(full)

    # Normalized name (suffixes stripped) concatenated: "austin"
    norm = normalize_name(name)
    norm_joined = re.sub(r"[^a-z0-9]", "", norm)  # strip commas, hyphens, spaces etc.
    if norm_joined and len(norm_joined) > 3:
        roots.add(norm_joined)

    # Normalized + common suffixes
    for suffix in ("isd", "usd", "cisd", "cusd", "schools", "k12"):
        candidate = norm_joined + suffix
        if len(candidate) > 4:
            roots.add(candidate)

    # Acronym-based roots: first letter of each word
    # "Los Angeles Unified School District" → "lausd"
    # "Cypress-Fairbanks ISD" → "cfi" + suffixes → "cfisd"
    acronym = "".join(w[0] for w in words if w)
    if len(acronym) >= 4:
        roots.add(acronym)
    # Acronym + common suffixes (handles "cfi" + "sd" → "cfisd")
    for suffix in ("sd", "isd", "usd"):
        acr_suffix = acronym + suffix
        if len(acr_suffix) >= 4 and acr_suffix != acronym:
            roots.add(acr_suffix)

    # Norm words joined with first-letter abbreviation patterns
    # "clark county" → "cc" + suffixes → "ccsd"
    norm_words = norm.split()
    if len(norm_words) >= 2:
        norm_acronym = "".join(w[0] for w in norm_words)
        for suffix in ("sd", "isd", "usd", "schools"):
            acr_suffix = norm_acronym + suffix
            if len(acr_suffix) >= 4:
                roots.add(acr_suffix)

    return roots


def _build_account_lookups(active_accounts: list[dict]) -> dict:
    """Build lookup structures from active accounts for fast cross-checking."""
    from tools.csv_importer import normalize_name

    by_name = {}          # normalized name → list of accounts
    districts_by_name = {}  # normalized name → list of district accounts
    schools_by_parent = {}  # normalized parent name → list of school accounts
    domain_to_accounts = {}  # domain root → list of accounts

    for acct in active_accounts:
        name_key = acct.get("Name Key", "").lower().strip()
        acct_type = acct.get("Account Type", "").lower().strip()
        parent = acct.get("Parent Account", "").strip()

        # Index by normalized name
        if name_key:
            by_name.setdefault(name_key, []).append(acct)
            if acct_type == "district":
                districts_by_name.setdefault(name_key, []).append(acct)

        # Index schools by parent district
        if parent and acct_type == "school":
            parent_key = normalize_name(parent)
            if parent_key:
                schools_by_parent.setdefault(parent_key, []).append(acct)

        # Generate domain roots for this account
        for root in _generate_domain_roots(acct):
            domain_to_accounts.setdefault(root, []).append(acct)

    return {
        "by_name": by_name,
        "districts_by_name": districts_by_name,
        "schools_by_parent": schools_by_parent,
        "domain_to_accounts": domain_to_accounts,
    }


def _classify_lead_company(company: str) -> str:
    """Classify a lead's company as 'district' or 'school' (or other)."""
    try:
        from tools.csv_importer import classify_account
        return classify_account(company, "", "")
    except Exception:
        return "company"


def _states_match(lead_state: str, acct_state: str) -> bool:
    """Check if states match, allowing blank on either side."""
    if not lead_state or not acct_state:
        return True  # Can't disqualify if we don't have state info
    return lead_state.upper().strip() == acct_state.upper().strip()


def _domain_matches_account(domain_root: str, acct: dict) -> bool:
    """Check if an email domain root is consistent with an account.

    Returns True if the domain root matches any of the account's generated
    domain roots. Used to validate District Name matches — if a lead has an
    institutional email pointing to a different org, the SF District Name
    is likely wrong.
    """
    if not domain_root:
        return True  # No domain to check — can't disqualify
    acct_roots = _generate_domain_roots(acct)
    if not acct_roots:
        return True  # Can't generate roots — can't disqualify
    return domain_root in acct_roots


def _cross_check_record(record: dict, lookups: dict, tab_type: str) -> str:
    """
    Check a lead/contact against Active Accounts.

    Returns one of:
      "Exact Match - School: [name]"
      "Exact Match - District: [name]"
      "District is Active Account: [name]"
      ""  (no match)

    Rules:
    - School active account → only matches if lead is at the SAME school
    - District active account → matches any school lead within that district
    - Lead at a district or different school + school-level active account → NOT a match
    """
    from tools.csv_importer import normalize_name

    # Extract lead fields
    if tab_type == "leads":
        company = record.get("company", "")
    else:
        company = record.get("account_name", "")
    email = record.get("email", "")
    lead_state = (record.get("state", "") or record.get("mailing_state", "")).strip()
    lead_district = record.get("district_name", "").strip()
    lead_parent = record.get("parent_account", "").strip()

    if not company and not email:
        return ""

    company_key = normalize_name(company) if company else ""
    company_type = _classify_lead_company(company) if company else ""

    # ── Step 1: Exact name match ──
    if company_key and company_key in lookups["by_name"]:
        for acct in lookups["by_name"][company_key]:
            if not _states_match(lead_state, acct.get("State", "")):
                continue
            acct_type = acct.get("Account Type", "").lower()
            acct_display = acct.get("Display Name", "")

            if acct_type == "district" and company_type == "district":
                return f"Exact Match - District: {acct_display}"
            if acct_type == "school" and company_type == "school":
                return f"Exact Match - School: {acct_display}"
            if acct_type == "district" and company_type != "district":
                return f"District is Active Account: {acct_display}"
            # acct_type == "school" but lead is district/other → NOT a match
            # (Steven can freely prospect the district)

    # ── Step 2: Lead is a school — check if parent district is active ──
    # Salesforce District Name field can be wrong, so validate:
    # If lead has a non-generic institutional email, its domain must be
    # consistent with the matched district. Otherwise skip (bad SF data).
    domain_root = _extract_domain_root(email)  # "" for generic/no email

    if company_type != "district":
        # Check lead's district_name field
        district_key = normalize_name(lead_district) if lead_district else ""
        if district_key and district_key in lookups["districts_by_name"]:
            for acct in lookups["districts_by_name"][district_key]:
                if not _states_match(lead_state, acct.get("State", "")):
                    continue
                # Validate: if lead has institutional email, domain must match district
                if domain_root and not _domain_matches_account(domain_root, acct):
                    continue  # institutional email points elsewhere — bad SF data
                return f"District is Active Account: {acct.get('Display Name', '')}"

        # Check lead's parent_account field (contacts CSV)
        parent_key = normalize_name(lead_parent) if lead_parent else ""
        if parent_key and parent_key != district_key and parent_key in lookups["districts_by_name"]:
            for acct in lookups["districts_by_name"][parent_key]:
                if not _states_match(lead_state, acct.get("State", "")):
                    continue
                if domain_root and not _domain_matches_account(domain_root, acct):
                    continue
                return f"District is Active Account: {acct.get('Display Name', '')}"

    # ── Step 3: Email domain matching ──
    # domain_root already computed in Step 2
    if domain_root and domain_root in lookups["domain_to_accounts"]:
        for acct in lookups["domain_to_accounts"][domain_root]:
            if not _states_match(lead_state, acct.get("State", "")):
                continue
            acct_type = acct.get("Account Type", "").lower()
            acct_display = acct.get("Display Name", "")

            if acct_type == "district":
                # Any lead with domain matching a district is under that district
                if company_type == "district":
                    # Lead's company is a district and domain matches → exact district
                    return f"Exact Match - District: {acct_display}"
                else:
                    return f"District is Active Account: {acct_display}"
            elif acct_type == "school":
                # Domain matches a school — only flag if it's the SAME school
                if company_key and company_key == acct.get("Name Key", "").lower().strip():
                    return f"Exact Match - School: {acct_display}"
                # Different school or district lead → not a match

    return ""


def _load_active_accounts() -> list[dict]:
    """Load all accounts from Active Accounts tab for cross-checking."""
    try:
        from tools.csv_importer import get_active_accounts
        return get_active_accounts()
    except Exception as e:
        logger.warning(f"Could not load active accounts for cross-check: {e}")
        return []


# ─────────────────────────────────────────────
# AUTO-DETECT CSV TYPE
# ─────────────────────────────────────────────

def is_lead_csv(csv_text: str) -> bool:
    """
    Auto-detect: True if CSV header has 2+ of {Lead Source, Lead Status, Company}
    AND does not have account-only columns.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        headers_lower = {h.strip().lower() for h in (reader.fieldnames or [])}
    except Exception:
        return False

    # Exclude account CSVs
    if headers_lower & _ACCOUNT_ONLY_HEADERS:
        return False

    lead_signals = {"lead source", "lead status", "company", "company / account", "lead owner"}
    return len(headers_lower & lead_signals) >= 2


def is_contact_csv(csv_text: str) -> bool:
    """
    Auto-detect: True if CSV header has 2+ of {Account Name, Department, Contact Owner}
    AND has First Name/Last Name (to distinguish from account CSV)
    AND does not have account-only columns.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        headers_lower = {h.strip().lower() for h in (reader.fieldnames or [])}
    except Exception:
        return False

    # Exclude account CSVs
    if headers_lower & _ACCOUNT_ONLY_HEADERS:
        return False

    contact_signals = {"account name", "department", "contact owner", "account owner", "parent account"}
    name_signals = {"first name", "last name"}
    return len(headers_lower & contact_signals) >= 2 and len(headers_lower & name_signals) >= 1


# ─────────────────────────────────────────────
# IMPORT FUNCTIONS
# ─────────────────────────────────────────────

def import_leads(csv_text: str) -> dict:
    """
    Import Salesforce Leads CSV into the SF Leads tab.
    Deduplicates by email (primary) or first|last name (secondary).
    Cross-checks against Active Accounts.

    Returns {imported, duplicates_skipped, cross_checked, errors}.
    """
    records, extra_cols = _parse_csv_records(csv_text, _SF_LEAD_COL_MAP)
    if not records:
        return {"imported": 0, "duplicates_skipped": 0, "cross_checked": 0,
                "errors": ["No records found in CSV"]}

    # Build full header list (base + extra CSV columns)
    headers = list(SF_LEADS_COLUMNS)
    for ec in extra_cols:
        if ec not in headers:
            headers.append(ec)

    service, sheet_id = _ensure_tab(TAB_SF_LEADS, headers)

    # Load existing keys for dedup
    email_keys, name_keys, _ = _load_existing_keys(service, sheet_id, TAB_SF_LEADS)

    # Load active accounts for cross-checking
    active_accounts = _load_active_accounts()
    lookups = _build_account_lookups(active_accounts) if active_accounts else {}

    rows_to_append = []
    active_rows = []  # Cross-checked rows for separate tab
    duplicates = 0
    cross_checked = 0
    errors = []
    today = datetime.now().strftime("%Y-%m-%d")

    for rec in records:
        email = rec.get("email", "").lower().strip()
        fn = rec.get("first_name", "").lower().strip()
        ln = rec.get("last_name", "").lower().strip()

        # Dedup by email
        if email and email in email_keys:
            duplicates += 1
            continue
        # Dedup by name for no-email records
        name_key = f"{fn}|{ln}"
        if not email and name_key in name_keys:
            duplicates += 1
            continue

        # Track within batch
        if email:
            email_keys.add(email)
        elif fn or ln:
            name_keys.add(name_key)

        # Cross-check against Active Accounts
        account_match = ""
        if lookups:
            account_match = _cross_check_record(rec, lookups, "leads")
            if account_match:
                cross_checked += 1

        # Build row matching headers
        row = _build_lead_row(headers, rec, account_match, today)
        rows_to_append.append(row)
        if account_match:
            active_rows.append(row)

    # Append in chunks to avoid Sheets API payload limits
    appended = _append_in_chunks(service, sheet_id, TAB_SF_LEADS, rows_to_append, errors,
                                  num_cols=len(headers))

    # Write cross-checked rows to separate tab
    if active_rows:
        try:
            _ensure_tab(TAB_LEADS_ACTIVE, headers)
            _append_in_chunks(service, sheet_id, TAB_LEADS_ACTIVE, active_rows, errors,
                              num_cols=len(headers))
            logger.info(f"Wrote {len(active_rows)} cross-checked leads to {TAB_LEADS_ACTIVE}")
        except Exception as e:
            errors.append(f"Active tab: {e}")

    return {
        "imported": appended,
        "duplicates_skipped": duplicates,
        "cross_checked": cross_checked,
        "total_in_csv": len(records),
        "errors": errors,
    }


def import_contacts(csv_text: str) -> dict:
    """
    Import Salesforce Contacts CSV into the SF Contacts tab.
    Deduplicates by email (primary) or first|last name (secondary).
    Cross-checks against Active Accounts.

    Returns {imported, duplicates_skipped, cross_checked, errors}.
    """
    records, extra_cols = _parse_csv_records(csv_text, _SF_CONTACT_COL_MAP)
    if not records:
        return {"imported": 0, "duplicates_skipped": 0, "cross_checked": 0,
                "errors": ["No records found in CSV"]}

    # Build full header list (base + extra CSV columns)
    headers = list(SF_CONTACTS_COLUMNS)
    for ec in extra_cols:
        if ec not in headers:
            headers.append(ec)

    service, sheet_id = _ensure_tab(TAB_SF_CONTACTS, headers)

    # Load existing keys for dedup
    email_keys, name_keys, _ = _load_existing_keys(service, sheet_id, TAB_SF_CONTACTS)

    # Load active accounts for cross-checking
    active_accounts = _load_active_accounts()
    lookups = _build_account_lookups(active_accounts) if active_accounts else {}

    rows_to_append = []
    active_rows = []  # Cross-checked rows for separate tab
    duplicates = 0
    cross_checked = 0
    errors = []
    today = datetime.now().strftime("%Y-%m-%d")

    for rec in records:
        email = rec.get("email", "").lower().strip()
        fn = rec.get("first_name", "").lower().strip()
        ln = rec.get("last_name", "").lower().strip()

        # Dedup by email
        if email and email in email_keys:
            duplicates += 1
            continue
        # Dedup by name for no-email records
        name_key = f"{fn}|{ln}"
        if not email and name_key in name_keys:
            duplicates += 1
            continue

        # Track within batch
        if email:
            email_keys.add(email)
        elif fn or ln:
            name_keys.add(name_key)

        # Cross-check against Active Accounts
        account_match = ""
        if lookups:
            account_match = _cross_check_record(rec, lookups, "contacts")
            if account_match:
                cross_checked += 1

        # Build row matching headers
        row = _build_contact_row(headers, rec, account_match, today)
        rows_to_append.append(row)
        if account_match:
            active_rows.append(row)

    # Append in chunks to avoid Sheets API payload limits
    appended = _append_in_chunks(service, sheet_id, TAB_SF_CONTACTS, rows_to_append, errors,
                                  num_cols=len(headers))

    # Write cross-checked rows to separate tab
    if active_rows:
        try:
            _ensure_tab(TAB_CONTACTS_ACTIVE, headers)
            _append_in_chunks(service, sheet_id, TAB_CONTACTS_ACTIVE, active_rows, errors,
                              num_cols=len(headers))
            logger.info(f"Wrote {len(active_rows)} cross-checked contacts to {TAB_CONTACTS_ACTIVE}")
        except Exception as e:
            errors.append(f"Active tab: {e}")

    return {
        "imported": appended,
        "duplicates_skipped": duplicates,
        "cross_checked": cross_checked,
        "total_in_csv": len(records),
        "errors": errors,
    }


def _build_lead_row(headers: list[str], rec: dict, account_match: str, today: str) -> list:
    """Build a sheet row for SF Leads matching the given headers."""
    base_map = {
        "First Name":           rec.get("first_name", ""),
        "Last Name":            rec.get("last_name", ""),
        "Title":                rec.get("title", ""),
        "Company":              rec.get("company", ""),
        "Email":                rec.get("email", ""),
        "Phone":                rec.get("phone", ""),
        "Lead Source":          rec.get("lead_source", ""),
        "Lead Status":          rec.get("lead_status", ""),
        "State/Province":       rec.get("state", ""),
        "Street":               rec.get("street", ""),
        "City":                 rec.get("city", ""),
        "Zip":                  rec.get("zip", ""),
        "Description":          rec.get("description", ""),
        "Created Date":         rec.get("created_date", ""),
        # Enrichment columns — blank on import
        "Verified School":      "",
        "Verified District":    "",
        "Verified State":       "",
        "Verified County":      "",
        "Active Account Match": account_match,
        "Enrichment Status":    "not_started" if not account_match else "cross_checked",
        "Enrichment Notes":     "",
        "Last Enriched":        today if account_match else "",
        "Date Imported":        today,
    }
    row = []
    for h in headers:
        if h in base_map:
            row.append(base_map[h])
        else:
            row.append(rec.get(h, ""))
    return row


def _build_contact_row(headers: list[str], rec: dict, account_match: str, today: str) -> list:
    """Build a sheet row for SF Contacts matching the given headers."""
    base_map = {
        "First Name":               rec.get("first_name", ""),
        "Last Name":                rec.get("last_name", ""),
        "Title":                    rec.get("title", ""),
        "Account Name":             rec.get("account_name", ""),
        "Email":                    rec.get("email", ""),
        "Phone":                    rec.get("phone", ""),
        "Mailing State/Province":   rec.get("mailing_state", ""),
        "Mailing City":             rec.get("mailing_city", ""),
        "Department":               rec.get("department", ""),
        "Contact Owner":            rec.get("contact_owner", ""),
        "Created Date":             rec.get("created_date", ""),
        # Enrichment columns — blank on import
        "Verified School":          "",
        "Verified District":        "",
        "Verified State":           "",
        "Verified County":          "",
        "Active Account Match":     account_match,
        "Enrichment Status":        "not_started" if not account_match else "cross_checked",
        "Enrichment Notes":         "",
        "Last Enriched":            today if account_match else "",
        "Date Imported":            today,
    }
    row = []
    for h in headers:
        if h in base_map:
            row.append(base_map[h])
        else:
            row.append(rec.get(h, ""))
    return row


# ─────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────

def get_unenriched(tab_name: str, limit: int = 20) -> list[dict]:
    """
    Get records from SF Leads or SF Contacts that haven't been enriched.
    Returns list of dicts with row_index (1-based, for sheet update) and record data.
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A1:ZZ"
        ).execute()
    except Exception as e:
        logger.error(f"get_unenriched error: {e}")
        return []

    rows = result.get("values", [])
    if len(rows) < 2:
        return []

    headers = rows[0]
    try:
        status_idx = headers.index("Enrichment Status")
    except ValueError:
        return []

    unenriched = []
    for row_idx, row in enumerate(rows[1:], start=2):  # row 2 is first data row
        padded = row + [""] * (len(headers) - len(row))
        status = padded[status_idx].strip().lower()
        if status in ("not_started", "cross_checked", ""):
            record = dict(zip(headers, padded))
            record["_row_index"] = row_idx
            unenriched.append(record)
            if len(unenriched) >= limit:
                break

    return unenriched


def update_enrichment(tab_name: str, row_index: int, enrichment: dict):
    """
    Update enrichment columns for a specific row in SF Leads or SF Contacts.

    enrichment keys: verified_school, verified_district, verified_state,
                     verified_county, enrichment_status, enrichment_notes
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    # Read headers to find column indices
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!1:1"
    ).execute()
    headers = result.get("values", [[]])[0]

    # Map enrichment fields to column letters
    field_map = {
        "Verified School":      enrichment.get("verified_school", ""),
        "Verified District":    enrichment.get("verified_district", ""),
        "Verified State":       enrichment.get("verified_state", ""),
        "Verified County":      enrichment.get("verified_county", ""),
        "Enrichment Status":    enrichment.get("enrichment_status", "enriched"),
        "Enrichment Notes":     enrichment.get("enrichment_notes", ""),
        "Last Enriched":        datetime.now().strftime("%Y-%m-%d"),
    }

    updates = []
    for col_name, value in field_map.items():
        if col_name in headers and value:
            col_idx = headers.index(col_name)
            col_letter = _col_to_letter(col_idx)
            updates.append({
                "range": f"'{tab_name}'!{col_letter}{row_index}",
                "values": [[value]],
            })

    if updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": updates}
        ).execute()
        logger.info(f"Updated enrichment for row {row_index} in {tab_name}")


def enrich_record_via_serper(record: dict, tab_type: str) -> dict:
    """
    Run a web search to verify a lead/contact's current role and school.
    Returns enrichment dict with verified fields.

    Uses SERPER_API_KEY for web search (same as research engine).
    """
    import httpx

    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        return {"enrichment_status": "error", "enrichment_notes": "No SERPER_API_KEY"}

    first = record.get("First Name", "")
    last = record.get("Last Name", "")
    company = record.get("Company", "") or record.get("Account Name", "")
    state = record.get("State/Province", "") or record.get("Mailing State/Province", "")
    email = record.get("Email", "")

    if not (first and last):
        return {"enrichment_status": "skipped", "enrichment_notes": "No name to search"}

    # Build search query
    query_parts = [first, last]
    if company:
        query_parts.append(company)
    if state:
        query_parts.append(state)
    query_parts.append("school district")
    query = " ".join(query_parts)

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"enrichment_status": "error", "enrichment_notes": f"Search failed: {e}"}

    # Parse results for verification
    results_text = []
    for item in data.get("organic", [])[:5]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        results_text.append(f"{title}: {snippet}")

    combined = " ".join(results_text).lower()
    enrichment = {"enrichment_status": "enriched", "enrichment_notes": ""}

    # Try to verify school/district from results
    notes = []
    if company and company.lower() in combined:
        enrichment["verified_school"] = company
        notes.append(f"Company '{company}' confirmed in search results")
    if state and state.lower() in combined:
        enrichment["verified_state"] = state

    # Check for California county
    if state and state.upper() in ("CA", "CALIFORNIA"):
        ca_counties = ["los angeles", "san diego", "orange", "riverside", "san bernardino",
                       "kern", "ventura", "santa barbara", "san luis obispo", "imperial"]
        for county in ca_counties:
            if county in combined:
                enrichment["verified_county"] = county.title()
                break

    if notes:
        enrichment["enrichment_notes"] = "; ".join(notes)
    else:
        enrichment["enrichment_notes"] = "Searched but no strong match found"

    return enrichment


def clear_tab(tab_name: str) -> dict:
    """Clear all data rows from a tab AND shrink grid to free cells.

    Uses updateSheetProperties to resize the grid (avoids the
    'cannot delete all non-frozen rows' error from deleteDimension).
    Keeps header row, shrinks grid to 2 rows × header columns.
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Get sheet metadata to find the sheetId and current grid size
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        tab_meta = None
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == tab_name:
                tab_meta = s
                break

        if not tab_meta:
            return {"cleared": 0, "error": f"Tab '{tab_name}' not found"}

        tab_id = tab_meta["properties"]["sheetId"]
        grid = tab_meta["properties"].get("gridProperties", {})
        current_rows = grid.get("rowCount", 1)
        current_cols = grid.get("columnCount", 26)

        # Read header to know target column count
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!1:1"
        ).execute()
        headers = result.get("values", [[]])[0]
        target_cols = max(len(headers), 1)

        data_rows = max(0, current_rows - 1)
        if data_rows == 0 and current_cols <= target_cols:
            return {"cleared": 0, "error": ""}

        # Clear all data values below header
        if data_rows > 0:
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range=f"'{tab_name}'!A2:ZZ"
            ).execute()

        # Resize grid to 2 rows × target columns (frees cells)
        # Must keep at least 2 rows (header + 1 empty) to avoid Sheets errors
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": tab_id,
                        "gridProperties": {
                            "rowCount": 2,
                            "columnCount": target_cols,
                        }
                    },
                    "fields": "gridProperties.rowCount,gridProperties.columnCount",
                }
            }]}
        ).execute()

        freed_cells = (data_rows * current_cols) - target_cols  # minus the 1 empty row kept
        logger.info(f"Cleared {data_rows} rows + resized to 2×{target_cols} in {tab_name} "
                     f"(freed ~{freed_cells} cells)")
        return {"cleared": data_rows, "error": ""}
    except Exception as e:
        return {"cleared": 0, "error": str(e)}


def clear_leads_tabs() -> dict:
    """Clear data from SF Leads + Leads Assoc Active Accounts tabs. For re-testing."""
    r1 = clear_tab(TAB_SF_LEADS)
    r2 = clear_tab(TAB_LEADS_ACTIVE)
    return {
        "sf_leads_cleared": r1["cleared"],
        "leads_active_cleared": r2["cleared"],
        "errors": [e for e in [r1["error"], r2["error"]] if e],
    }


def clear_contacts_tabs() -> dict:
    """Clear data from SF Contacts + Contacts Assoc Active Accounts tabs. For re-testing."""
    r1 = clear_tab(TAB_SF_CONTACTS)
    r2 = clear_tab(TAB_CONTACTS_ACTIVE)
    return {
        "sf_contacts_cleared": r1["cleared"],
        "contacts_active_cleared": r2["cleared"],
        "errors": [e for e in [r1["error"], r2["error"]] if e],
    }


def get_import_summary(tab_name: str) -> str:
    """Return a count summary for the given tab."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A:A"
        ).execute()
        rows = result.get("values", [])
        count = max(0, len(rows) - 1)
        return f"{tab_name}: {count} records"
    except Exception:
        return f"{tab_name}: unable to read"
