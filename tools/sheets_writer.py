"""
sheets_writer.py — Google Sheets integration for Scout's lead management.
Handles read/write/dedup against the Master Lead Sheet.

Tabs:
  - Leads        : contacts with at least one email
  - No Email     : contacts found but missing email
  - Research Log : one row per research job

Column headers (exact Outreach.io import format):
  First Name | Last Name | Title | Email | State | Account | Work Phone |
  District Name | Source URL | Email Confidence | Date Found
"""

import logging
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

LEAD_COLUMNS = [
    "First Name",
    "Last Name",
    "Title",
    "Email",
    "State",
    "Account",
    "Work Phone",
    "District Name",
    "Source URL",
    "Email Confidence",
    "Date Found",
]

# Internal key → Sheet column name mapping
CONTACT_KEY_MAP = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "title": "Title",
    "email": "Email",
    "state": "State",
    "account": "Account",
    "work_phone": "Work Phone",
    "district_name": "District Name",
    "source_url": "Source URL",
    "email_confidence": "Email Confidence",
    "date_found": "Date Found",
}

LOG_COLUMNS = [
    "Date",
    "District",
    "State",
    "Layers Used",
    "Total Found",
    "With Email",
    "No Email",
    "Notes",
]

TAB_LEADS = "Leads"
TAB_NO_EMAIL = "No Email"
TAB_LOG = "Research Log"


# ─────────────────────────────────────────────
# CLIENT INITIALIZATION
# ─────────────────────────────────────────────

def _get_service():
    """Build and return authenticated Google Sheets service."""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    return service


def _get_sheet_id():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID environment variable not set")
    return sheet_id


# ─────────────────────────────────────────────
# SHEET SETUP
# ─────────────────────────────────────────────

def ensure_sheet_tabs_exist():
    """
    Ensure Leads, No Email, and Research Log tabs exist with correct headers.
    Safe to call on every startup — only creates what's missing.
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    # Get existing sheets
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing_tabs = {s["properties"]["title"] for s in meta.get("sheets", [])}

    requests = []
    for tab_name in [TAB_LEADS, TAB_NO_EMAIL, TAB_LOG]:
        if tab_name not in existing_tabs:
            requests.append({
                "addSheet": {
                    "properties": {"title": tab_name}
                }
            })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests}
        ).execute()
        logger.info(f"Created missing tabs: {[r['addSheet']['properties']['title'] for r in requests]}")

    # Write headers to each tab if row 1 is empty
    _ensure_headers(service, sheet_id, TAB_LEADS, LEAD_COLUMNS)
    _ensure_headers(service, sheet_id, TAB_NO_EMAIL, LEAD_COLUMNS)
    _ensure_headers(service, sheet_id, TAB_LOG, LOG_COLUMNS)


def _ensure_headers(service, sheet_id: str, tab: str, columns: list[str]):
    """Write header row if tab is empty."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A1:Z1"
    ).execute()

    values = result.get("values", [])
    if not values or not values[0]:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab}'!A1",
            valueInputOption="RAW",
            body={"values": [columns]}
        ).execute()
        logger.info(f"Wrote headers to tab: {tab}")


# ─────────────────────────────────────────────
# DEDUP CHECK
# ─────────────────────────────────────────────

def _load_existing_keys(service, sheet_id: str, tab: str) -> set[str]:
    """
    Load all existing (first_name, last_name, district_name) keys from a tab.
    Used for dedup before writing.
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A:Z"
    ).execute()

    rows = result.get("values", [])
    if len(rows) < 2:
        return set()

    headers = rows[0]
    try:
        fn_idx = headers.index("First Name")
        ln_idx = headers.index("Last Name")
        dist_idx = headers.index("District Name")
    except ValueError:
        return set()

    keys = set()
    for row in rows[1:]:
        fn = row[fn_idx].lower().strip() if fn_idx < len(row) else ""
        ln = row[ln_idx].lower().strip() if ln_idx < len(row) else ""
        dist = row[dist_idx].lower().strip() if dist_idx < len(row) else ""
        if fn or ln:
            keys.add(f"{fn}|{ln}|{dist}")

    return keys


# ─────────────────────────────────────────────
# WRITE CONTACTS
# ─────────────────────────────────────────────

def write_contacts(contacts: list[dict], state: str = "") -> dict:
    """
    Write a list of contact dicts to the Master Sheet.
    Automatically routes to Leads or No Email tab.
    Deduplicates against existing data.

    Returns summary dict: {leads_added, no_email_added, duplicates_skipped}
    """
    if not contacts:
        return {"leads_added": 0, "no_email_added": 0, "duplicates_skipped": 0}

    service = _get_service()
    sheet_id = _get_sheet_id()

    ensure_sheet_tabs_exist()

    # Load existing keys from both tabs
    leads_keys = _load_existing_keys(service, sheet_id, TAB_LEADS)
    no_email_keys = _load_existing_keys(service, sheet_id, TAB_NO_EMAIL)
    all_existing = leads_keys | no_email_keys

    leads_rows = []
    no_email_rows = []
    duplicates = 0

    for c in contacts:
        fn = c.get("first_name", "").lower().strip()
        ln = c.get("last_name", "").lower().strip()
        dist = c.get("district_name", "").lower().strip()
        key = f"{fn}|{ln}|{dist}"

        if key in all_existing:
            duplicates += 1
            continue

        # Build row in column order
        row = [
            c.get("first_name", ""),
            c.get("last_name", ""),
            c.get("title", ""),
            c.get("email", ""),
            state or c.get("state", ""),
            c.get("account", ""),
            c.get("work_phone", ""),
            c.get("district_name", ""),
            c.get("source_url", ""),
            c.get("email_confidence", "UNKNOWN"),
            c.get("date_found", datetime.now().strftime("%Y-%m-%d")),
        ]

        all_existing.add(key)  # prevent duplicates within this batch

        if c.get("email"):
            leads_rows.append(row)
        else:
            no_email_rows.append(row)

    # Append to Leads tab
    if leads_rows:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{TAB_LEADS}'!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": leads_rows}
        ).execute()
        logger.info(f"Appended {len(leads_rows)} rows to Leads tab")

    # Append to No Email tab
    if no_email_rows:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{TAB_NO_EMAIL}'!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": no_email_rows}
        ).execute()
        logger.info(f"Appended {len(no_email_rows)} rows to No Email tab")

    return {
        "leads_added": len(leads_rows),
        "no_email_added": len(no_email_rows),
        "duplicates_skipped": duplicates,
    }


# ─────────────────────────────────────────────
# LOG RESEARCH JOB
# ─────────────────────────────────────────────

def log_research_job(
    district: str,
    state: str,
    layers_used: str,
    total_found: int,
    with_email: int,
    no_email: int,
    notes: str = ""
):
    """Append one row to the Research Log tab."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    ensure_sheet_tabs_exist()

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        district,
        state,
        layers_used,
        total_found,
        with_email,
        no_email,
        notes,
    ]

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"'{TAB_LOG}'!A:H",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()


# ─────────────────────────────────────────────
# CREATE ON-DEMAND SHEET
# ─────────────────────────────────────────────

def create_export_sheet(contacts: list[dict], title: str, state: str = "") -> str:
    """
    Create a brand-new Google Sheet with the given contacts.
    Returns the URL of the new sheet.
    Used for on-demand exports (e.g. 'give me a fresh sheet for Denver PS contacts').
    """
    service = _get_service()

    # Create new spreadsheet
    spreadsheet = service.spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [{"properties": {"title": "Leads"}}]
        }
    ).execute()

    new_id = spreadsheet["spreadsheetId"]
    url = f"https://docs.google.com/spreadsheets/d/{new_id}"

    # Write headers
    service.spreadsheets().values().update(
        spreadsheetId=new_id,
        range="'Leads'!A1",
        valueInputOption="RAW",
        body={"values": [LEAD_COLUMNS]}
    ).execute()

    # Write contacts
    if contacts:
        rows = []
        for c in contacts:
            rows.append([
                c.get("first_name", ""),
                c.get("last_name", ""),
                c.get("title", ""),
                c.get("email", ""),
                state or c.get("state", ""),
                c.get("account", ""),
                c.get("work_phone", ""),
                c.get("district_name", ""),
                c.get("source_url", ""),
                c.get("email_confidence", "UNKNOWN"),
                c.get("date_found", datetime.now().strftime("%Y-%m-%d")),
            ])

        service.spreadsheets().values().append(
            spreadsheetId=new_id,
            range="'Leads'!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows}
        ).execute()

    logger.info(f"Created export sheet: {title} — {url}")
    return url


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def get_master_sheet_url() -> str:
    sheet_id = _get_sheet_id()
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def count_leads() -> dict:
    """Return counts from Leads and No Email tabs."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        for tab, key in [(TAB_LEADS, "leads"), (TAB_NO_EMAIL, "no_email")]:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=f"'{tab}'!A:A"
            ).execute()
            rows = result.get("values", [])
            counts = {
                "leads": max(0, len(rows) - 1),  # subtract header
            }

        result_no = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_NO_EMAIL}'!A:A"
        ).execute()
        result_leads = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_LEADS}'!A:A"
        ).execute()

        return {
            "leads": max(0, len(result_leads.get("values", [])) - 1),
            "no_email": max(0, len(result_no.get("values", [])) - 1),
            "total": max(0, len(result_leads.get("values", [])) - 1) + max(0, len(result_no.get("values", [])) - 1),
        }
    except Exception as e:
        logger.error(f"count_leads error: {e}")
        return {"leads": 0, "no_email": 0, "total": 0}
