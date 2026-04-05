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

TAB_LEADS = "Leads from Research"
TAB_NO_EMAIL = "No Email"
TAB_LOG = "Research Log"
TAB_ACTIVITIES = "Activities"
TAB_ACTIVE_ACCOUNTS = "Active Accounts"
TAB_GOALS = "Goals"
TAB_SF_LEADS = "SF Leads"
TAB_SF_CONTACTS = "SF Contacts"
TAB_SIGNALS = "Signals"

ACTIVITY_COLUMNS = [
    "Date", "Time", "Type", "District/Account", "Contact", "Notes", "Source", "Message ID",
]
GOALS_COLUMNS = [
    "Goal Type", "Daily Target", "Description",
]
ACTIVE_ACCOUNTS_COLUMNS = [
    "Name Key", "Display Name", "Parent Account", "Type", "Open Renewal",
    "Opportunities", "Active Licenses", "2025 Revenue", "Lifetime Revenue",
    "Last Activity", "Last Modified", "State", "Is District",
]


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
    all_tabs = [
        TAB_LEADS, TAB_NO_EMAIL, TAB_LOG,
        TAB_ACTIVITIES, TAB_ACTIVE_ACCOUNTS, TAB_GOALS,
        TAB_SF_LEADS, TAB_SF_CONTACTS, TAB_SIGNALS,
    ]
    for tab_name in all_tabs:
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
    _ensure_headers(service, sheet_id, TAB_ACTIVITIES, ACTIVITY_COLUMNS)
    _ensure_headers(service, sheet_id, TAB_ACTIVE_ACCOUNTS, ACTIVE_ACCOUNTS_COLUMNS)
    _ensure_headers(service, sheet_id, TAB_GOALS, GOALS_COLUMNS)


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


def cleanup_and_format_sheets():
    """
    One-time cleanup: remove unused tabs (Sheet1, Salesforce Import)
    and apply alternating row colors (banding) to all data tabs.
    Safe to call on every startup — skips tabs that don't exist,
    skips banding that's already applied.
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = meta.get("sheets", [])

    # Build lookup: tab name → sheet GID
    tab_gids = {}
    for s in sheets:
        props = s["properties"]
        tab_gids[props["title"]] = props["sheetId"]

    # Collect existing banded range IDs to avoid duplicates
    existing_banding_sheet_ids = set()
    for s in sheets:
        for br in s.get("bandedRanges", []):
            rng = br.get("range", {})
            existing_banding_sheet_ids.add(rng.get("sheetId"))

    requests = []

    # ── Rename migrated tabs ──
    renames = {"Leads": "Leads from Research"}
    for old_name, new_name in renames.items():
        if old_name in tab_gids and new_name not in tab_gids:
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": tab_gids[old_name],
                        "title": new_name,
                    },
                    "fields": "title",
                }
            })
            logger.info(f"Queued rename: '{old_name}' → '{new_name}'")

    # ── Delete unused tabs ──
    tabs_to_delete = ["Sheet1", "Salesforce Import"]
    for tab_name in tabs_to_delete:
        if tab_name in tab_gids:
            requests.append({
                "deleteSheet": {"sheetId": tab_gids[tab_name]}
            })
            logger.info(f"Queued deletion of unused tab: {tab_name}")

    # ── Apply alternating row colors (banding) ──
    # Light blue header, white/light gray alternating rows
    header_color = {"red": 0.22, "green": 0.46, "blue": 0.69, "alpha": 1.0}
    first_band = {"red": 1.0, "green": 1.0, "blue": 1.0, "alpha": 1.0}       # white
    second_band = {"red": 0.93, "green": 0.95, "blue": 0.97, "alpha": 1.0}    # light gray-blue

    for tab_name, gid in tab_gids.items():
        if tab_name in tabs_to_delete:
            continue  # skip tabs we're deleting
        if gid in existing_banding_sheet_ids:
            continue  # banding already applied

        requests.append({
            "addBanding": {
                "bandedRange": {
                    "range": {
                        "sheetId": gid,
                        "startRowIndex": 0,
                        "startColumnIndex": 0,
                    },
                    "rowProperties": {
                        "headerColor": header_color,
                        "firstBandColor": first_band,
                        "secondBandColor": second_band,
                    },
                }
            }
        })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests}
        ).execute()
        logger.info(f"Sheet cleanup/formatting: {len(requests)} operations applied")
    else:
        logger.info("Sheet cleanup/formatting: nothing to do")


# ─────────────────────────────────────────────
# DEDUP CHECK
# ─────────────────────────────────────────────

def _load_existing_keys(service, sheet_id: str, tab: str) -> tuple[set[str], set[str]]:
    """
    Load dedup keys from an existing tab.
    Returns (email_keys, name_keys):
      - email_keys: lowercase emails (primary dedup — district-agnostic)
      - name_keys:  "first|last" keys for no-email contacts
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A:Z"
    ).execute()

    rows = result.get("values", [])
    if len(rows) < 2:
        return set(), set()

    headers = rows[0]
    try:
        fn_idx = headers.index("First Name")
        ln_idx = headers.index("Last Name")
        email_idx = headers.index("Email")
    except ValueError:
        return set(), set()

    email_keys: set[str] = set()
    name_keys: set[str] = set()

    for row in rows[1:]:
        fn = row[fn_idx].lower().strip() if fn_idx < len(row) else ""
        ln = row[ln_idx].lower().strip() if ln_idx < len(row) else ""
        email = row[email_idx].lower().strip() if email_idx < len(row) else ""
        if email:
            email_keys.add(email)
        elif fn or ln:
            name_keys.add(f"{fn}|{ln}")

    return email_keys, name_keys


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

    # Load existing dedup keys from both tabs
    leads_emails, leads_names = _load_existing_keys(service, sheet_id, TAB_LEADS)
    no_email_emails, no_email_names = _load_existing_keys(service, sheet_id, TAB_NO_EMAIL)
    all_emails = leads_emails | no_email_emails
    all_names = leads_names | no_email_names

    leads_rows = []
    no_email_rows = []
    duplicates = 0

    for c in contacts:
        email = c.get("email", "").lower().strip()
        fn = c.get("first_name", "").lower().strip()
        ln = c.get("last_name", "").lower().strip()

        # Primary dedup: email (cross-district reliable)
        if email and email in all_emails:
            duplicates += 1
            continue
        # Secondary dedup: name match for no-email contacts
        name_key = f"{fn}|{ln}"
        if not email and name_key in all_names:
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

        # Track within this batch
        if email:
            all_emails.add(email)
        else:
            all_names.add(name_key)

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

    # Color-code newly appended lead rows by confidence
    if leads_rows:
        try:
            _color_leads_by_confidence(service, sheet_id)
        except Exception as color_err:
            logger.warning(f"Could not color lead rows: {color_err}")

    return {
        "leads_added": len(leads_rows),
        "no_email_added": len(no_email_rows),
        "duplicates_skipped": duplicates,
    }


# ─────────────────────────────────────────────
# LEAD ROW COLORING BY CONFIDENCE
# ─────────────────────────────────────────────

# Confidence → background color (RGB 0-1 floats)
_CONFIDENCE_COLORS = {
    "VERIFIED": {"red": 0.85, "green": 0.93, "blue": 0.83},  # light green
    "HIGH":     {"red": 0.85, "green": 0.93, "blue": 0.83},  # light green
    "LIKELY":   {"red": 0.91, "green": 0.95, "blue": 0.81},  # yellowish-green
    "MEDIUM":   {"red": 0.91, "green": 0.95, "blue": 0.81},  # yellowish-green
    "INFERRED": {"red": 1.0,  "green": 0.97, "blue": 0.80},  # light yellow
    "LOW":      {"red": 1.0,  "green": 0.97, "blue": 0.80},  # light yellow
    "UNKNOWN":  {"red": 0.94, "green": 0.94, "blue": 0.94},  # light grey
}


def _color_leads_by_confidence(service=None, sheet_id=None):
    """
    Apply background colors to all Leads tab rows based on Email Confidence column.
    Safe to call repeatedly — overwrites existing colors.
    """
    if service is None:
        service = _get_service()
    if sheet_id is None:
        sheet_id = _get_sheet_id()

    # Read all data from Leads tab
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_LEADS}'!A:K"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return {"colored": 0}

    headers = rows[0]
    try:
        conf_idx = headers.index("Email Confidence")
    except ValueError:
        logger.warning("Email Confidence column not found in Leads tab")
        return {"colored": 0}

    # Get the Leads tab GID
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    leads_gid = None
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == TAB_LEADS:
            leads_gid = s["properties"]["sheetId"]
            break
    if leads_gid is None:
        logger.warning("Leads tab not found for coloring")
        return {"colored": 0}

    # Build batch update requests — one per row
    requests = []
    colored = 0
    for row_idx, row in enumerate(rows[1:], start=1):  # skip header
        confidence = row[conf_idx].strip().upper() if conf_idx < len(row) else "UNKNOWN"
        color = _CONFIDENCE_COLORS.get(confidence, _CONFIDENCE_COLORS["UNKNOWN"])

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": leads_gid,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(headers),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color,
                    }
                },
                "fields": "userEnteredFormat.backgroundColor",
            }
        })
        colored += 1

    if requests:
        # Batch in chunks of 500 to avoid API limits
        for i in range(0, len(requests), 500):
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": requests[i:i+500]}
            ).execute()
        logger.info(f"Colored {colored} lead rows by confidence")

    return {"colored": colored}


def color_all_leads() -> dict:
    """
    Public function: recolor ALL existing Leads tab rows by confidence.
    Used by /color_leads command for one-time cleanup.
    """
    try:
        return _color_leads_by_confidence()
    except Exception as e:
        logger.error(f"color_all_leads error: {e}")
        return {"colored": 0, "error": str(e)}


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


def get_leads(state_filter: str = "") -> list[dict]:
    """
    Read all leads from the Leads tab as a list of dicts.
    Keys match LEAD_COLUMNS: First Name, Last Name, Title, Email, State,
    Account, Work Phone, District Name, Source URL, Email Confidence, Date Found.

    Optional state_filter narrows to a specific US state abbreviation.
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_LEADS}'!A:K"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []

        headers = rows[0]
        leads = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded))
            if state_filter:
                if record.get("State", "").strip().upper() != state_filter.strip().upper():
                    continue
            leads.append(record)
        return leads
    except Exception as e:
        logger.error(f"get_leads error: {e}")
        return []


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
