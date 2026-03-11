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
                      chunk_size: int = 2000):
    """Append rows to a Sheets tab in chunks with retry."""
    import time
    appended = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        chunk_num = i // chunk_size + 1
        for attempt in range(3):
            try:
                service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range=f"'{tab_name}'!A:AZ",
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

def _cross_check_record(record: dict, active_accounts: list[dict], tab_type: str) -> str:
    """
    Check a single record against Active Accounts.
    Returns match description string or empty string.

    Matching by:
    1. Email domain → account with matching domain in any field
    2. Company/Account name → normalized name match
    3. District name inference from company name
    """
    matches = []

    # Get the company/account name from the record
    if tab_type == "leads":
        company = record.get("company", "")
    else:
        company = record.get("account_name", "")

    email = record.get("email", "")

    # 1. Email domain matching
    if email and "@" in email:
        domain = email.split("@")[1].lower().strip()
        # Skip generic domains
        generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                   "aol.com", "icloud.com", "me.com", "live.com", "msn.com"}
        if domain not in generic:
            for acct in active_accounts:
                acct_name = acct.get("Display Name", "").lower()
                # Check if domain appears in account name (e.g. "austinisd.org" ↔ "Austin ISD")
                domain_root = domain.split(".")[0]  # "austinisd" from "austinisd.org"
                name_clean = re.sub(r"[^\w]", "", acct_name)
                if domain_root and len(domain_root) > 3 and domain_root in name_clean:
                    matches.append(f"Email domain match: {acct.get('Display Name', '')}")
                    break

    # 2. Company/account name matching
    if company:
        from tools.csv_importer import normalize_name
        company_key = normalize_name(company)
        if company_key:
            for acct in active_accounts:
                acct_key = acct.get("Name Key", "").lower().strip()
                if acct_key and (company_key == acct_key or company_key in acct_key or acct_key in company_key):
                    matches.append(f"Account name match: {acct.get('Display Name', '')}")
                    break

    # 3. Check parent account (district) matching
    if company:
        from tools.csv_importer import normalize_name
        company_key = normalize_name(company)
        for acct in active_accounts:
            parent = acct.get("Parent Account", "").strip()
            if parent:
                parent_key = normalize_name(parent)
                if parent_key and (company_key == parent_key or company_key in parent_key or parent_key in company_key):
                    matches.append(f"District match: {acct.get('Display Name', '')} (under {parent})")
                    break

    return "; ".join(matches) if matches else ""


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
        if active_accounts:
            account_match = _cross_check_record(rec, active_accounts, "leads")
            if account_match:
                cross_checked += 1

        # Build row matching headers
        row = _build_lead_row(headers, rec, account_match, today)
        rows_to_append.append(row)
        if account_match:
            active_rows.append(row)

    # Append in chunks to avoid Sheets API payload limits
    appended = _append_in_chunks(service, sheet_id, TAB_SF_LEADS, rows_to_append, errors)

    # Write cross-checked rows to separate tab
    if active_rows:
        try:
            _ensure_tab(TAB_LEADS_ACTIVE, headers)
            _append_in_chunks(service, sheet_id, TAB_LEADS_ACTIVE, active_rows, errors)
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
        if active_accounts:
            account_match = _cross_check_record(rec, active_accounts, "contacts")
            if account_match:
                cross_checked += 1

        # Build row matching headers
        row = _build_contact_row(headers, rec, account_match, today)
        rows_to_append.append(row)
        if account_match:
            active_rows.append(row)

    # Append in chunks to avoid Sheets API payload limits
    appended = _append_in_chunks(service, sheet_id, TAB_SF_CONTACTS, rows_to_append, errors)

    # Write cross-checked rows to separate tab
    if active_rows:
        try:
            _ensure_tab(TAB_CONTACTS_ACTIVE, headers)
            _append_in_chunks(service, sheet_id, TAB_CONTACTS_ACTIVE, active_rows, errors)
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
