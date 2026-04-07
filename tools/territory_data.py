"""
tools/territory_data.py — Master Territory List from NCES CCD data.

Downloads district and school data from the Urban Institute Education Data API
(wraps NCES Common Core of Data) and writes to a dedicated Google Sheet.

Cross-references against Active Accounts + Prospecting Queue to identify
coverage gaps.

Usage (module-level, not a class):
  import tools.territory_data as territory_data
  result = territory_data.sync_territory(states=["NV"])
  stats = territory_data.get_territory_stats(state_filter="NV")
  gaps = territory_data.get_territory_gaps("NV")
"""

import json
import logging
import os
import time
from datetime import datetime

import httpx

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import tools.csv_importer as csv_importer
import tools.district_prospector as district_prospector

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

URBAN_API_BASE = "https://educationdata.urban.org/api/v1"
NCES_YEAR = 2023

# Steven's territory states
TERRITORY_STATES = {"IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE", "TX"}

STATE_TO_FIPS = {
    "AL": 1, "AK": 2, "AZ": 4, "AR": 5, "CA": 6, "CO": 8, "CT": 9, "DE": 10,
    "DC": 11, "FL": 12, "GA": 13, "HI": 15, "ID": 16, "IL": 17, "IN": 18,
    "IA": 19, "KS": 20, "KY": 21, "LA": 22, "ME": 23, "MD": 24, "MA": 25,
    "MI": 26, "MN": 27, "MS": 28, "MO": 29, "MT": 30, "NE": 31, "NV": 32,
    "NH": 33, "NJ": 34, "NM": 35, "NY": 36, "NC": 37, "ND": 38, "OH": 39,
    "OK": 40, "OR": 41, "PA": 42, "RI": 44, "SC": 45, "SD": 46, "TN": 47,
    "TX": 48, "UT": 49, "VT": 50, "VA": 51, "WA": 53, "WV": 54, "WI": 55,
    "WY": 56,
}

STATE_NAME_TO_ABBR = {
    "illinois": "IL", "pennsylvania": "PA", "ohio": "OH", "michigan": "MI",
    "connecticut": "CT", "oklahoma": "OK", "massachusetts": "MA", "indiana": "IN",
    "nevada": "NV", "tennessee": "TN", "nebraska": "NE", "texas": "TX",
    "california": "CA",
}

# SoCal FIPS county codes (API returns these as strings)
SOCAL_COUNTY_CODES = {
    "6037",  # Los Angeles
    "6073",  # San Diego
    "6059",  # Orange
    "6065",  # Riverside
    "6071",  # San Bernardino
    "6029",  # Kern
    "6111",  # Ventura
    "6083",  # Santa Barbara
    "6079",  # San Luis Obispo
    "6025",  # Imperial
}

SOCAL_COUNTY_NAMES = {
    "6037": "Los Angeles", "6073": "San Diego", "6059": "Orange",
    "6065": "Riverside", "6071": "San Bernardino", "6029": "Kern",
    "6111": "Ventura", "6083": "Santa Barbara", "6079": "San Luis Obispo",
    "6025": "Imperial",
}

# Tab names
TAB_TERRITORY_DISTRICTS = "Territory Districts"
TAB_TERRITORY_SCHOOLS = "Territory Schools"

# Sheet column schemas
DISTRICT_COLUMNS = [
    "State", "District Name", "LEAID", "City", "Street", "Zip",
    "Phone", "County", "County Code", "Enrollment", "School Count",
    "Grade Span", "Agency Type", "Lat", "Lon", "Date Synced", "Name Key",
]

SCHOOL_COLUMNS = [
    "State", "School Name", "District Name", "NCESSCH", "LEAID",
    "City", "Street", "Zip", "Phone", "County Code", "Enrollment",
    "Grade Span", "School Type", "Charter", "Lat", "Lon", "Date Synced",
    "Name Key",
]

# Agency types from NCES CCD (numeric codes)
_AGENCY_TYPE_MAP = {
    1: "Regular local school district",
    2: "Local school district (component of supervisory union)",
    3: "Supervisory union",
    4: "Regional education service agency",
    5: "State-operated agency",
    6: "Federally-operated agency",
    7: "Charter school agency",
    8: "Other education agency",
    9: "Specialized public school district",
}

# School types
_SCHOOL_TYPE_MAP = {
    1: "Regular school",
    2: "Special education school",
    3: "Vocational school",
    4: "Alternative/other school",
}

# Cache TTL: 7 days in seconds
_CACHE_TTL = 7 * 24 * 3600


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _get_territory_sheet_id():
    """Get the separate Google Sheet ID for territory data.
    Falls back to main sheet if GOOGLE_SHEETS_TERRITORY_ID not set."""
    sheet_id = os.environ.get("GOOGLE_SHEETS_TERRITORY_ID") or os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_TERRITORY_ID or GOOGLE_SHEETS_ID not set")
    return sheet_id


def _col_to_letter(col_idx: int) -> str:
    """Convert 0-based column index to spreadsheet letter."""
    result = ""
    idx = col_idx
    while idx >= 0:
        result = chr(idx % 26 + ord("A")) + result
        idx = idx // 26 - 1
    return result


def _ensure_tab(tab_name: str, columns: list[str]):
    """Create tab if missing, overwrite header row + freeze row 1.
    Returns (service, sheet_id, tab_id)."""
    service = _get_service()
    sheet_id = _get_territory_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {}
    for s in meta.get("sheets", []):
        existing[s["properties"]["title"]] = s["properties"]["sheetId"]

    if tab_name not in existing:
        resp = service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        ).execute()
        tab_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
        logger.info(f"Created tab: {tab_name}")
    else:
        tab_id = existing[tab_name]

    # Always overwrite headers
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": [columns]}
    ).execute()

    # Freeze row 1
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }]}
    ).execute()

    return service, sheet_id, tab_id


def _format_tab(service, sheet_id: str, tab_name: str, headers: list[str]):
    """Apply formatting: column widths sized to header text, alternating row banding."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        tab_id = None
        has_banding = False
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == tab_name:
                tab_id = s["properties"]["sheetId"]
                has_banding = bool(s.get("bandedRanges"))
                break
        if tab_id is None:
            return

        requests = []

        for i, header in enumerate(headers):
            px = max(len(header) * 7 + 16, 50)
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": tab_id,
                        "dimension": "COLUMNS",
                        "startIndex": i,
                        "endIndex": i + 1,
                    },
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            })

        if not has_banding:
            header_color = {"red": 0.22, "green": 0.46, "blue": 0.69, "alpha": 1.0}
            first_band = {"red": 1.0, "green": 1.0, "blue": 1.0, "alpha": 1.0}
            second_band = {"red": 0.93, "green": 0.95, "blue": 0.97, "alpha": 1.0}
            requests.append({
                "addBanding": {
                    "bandedRange": {
                        "range": {
                            "sheetId": tab_id,
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
            logger.info(f"Formatted {tab_name}: {len(headers)} columns + banding")
    except Exception as e:
        logger.warning(f"Format failed for {tab_name}: {e}")


def _append_in_chunks(service, sheet_id: str, tab_name: str, rows: list, errors: list,
                      chunk_size: int = 2000, num_cols: int = 0):
    """Append rows to a Sheets tab in chunks with retry."""
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


def _normalize_state(state_input: str) -> str:
    """Normalize state input to 2-letter abbreviation. Returns '' if unrecognized."""
    s = state_input.strip()
    if len(s) == 2:
        return s.upper()
    key = s.lower()
    return STATE_NAME_TO_ABBR.get(key, "")


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


def _cache_path(kind: str, state: str) -> str:
    """Return /tmp cache file path for a given kind+state."""
    return f"/tmp/territory_{kind}_{state}.json"


def _read_cache(path: str) -> list | None:
    """Read cached API response if fresh enough."""
    try:
        if not os.path.exists(path):
            return None
        age = time.time() - os.path.getmtime(path)
        if age > _CACHE_TTL:
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(path: str, data: list):
    """Write API response to cache."""
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to write cache {path}: {e}")


# ─────────────────────────────────────────────
# API FETCH
# ─────────────────────────────────────────────

def _fetch_districts_for_state(state_abbr: str) -> list[dict]:
    """Fetch district data from Urban API for one state. Uses /tmp cache with 7-day TTL."""
    fips = STATE_TO_FIPS.get(state_abbr)
    if not fips:
        raise ValueError(f"Unknown state: {state_abbr}")

    cache = _cache_path("districts", state_abbr)
    cached = _read_cache(cache)
    if cached is not None:
        logger.info(f"Using cached districts for {state_abbr} ({len(cached)} records)")
        return cached

    url = f"{URBAN_API_BASE}/school-districts/ccd/directory/{NCES_YEAR}/?fips={fips}"
    logger.info(f"Fetching districts for {state_abbr} from Urban API...")

    all_results = []
    with httpx.Client(timeout=120.0) as client:
        # API may paginate — follow next links
        page_url = url
        while page_url:
            resp = client.get(page_url)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            page_url = data.get("next")

    # Filter CA to SoCal only
    if state_abbr == "CA":
        before = len(all_results)
        all_results = [d for d in all_results if d.get("county_code") in SOCAL_COUNTY_CODES]
        logger.info(f"CA districts: {before} total → {len(all_results)} SoCal only")

    _write_cache(cache, all_results)
    logger.info(f"Fetched {len(all_results)} districts for {state_abbr}")
    return all_results


def _fetch_schools_for_state(state_abbr: str) -> list[dict]:
    """Fetch school data from Urban API for one state. Uses /tmp cache with 7-day TTL."""
    fips = STATE_TO_FIPS.get(state_abbr)
    if not fips:
        raise ValueError(f"Unknown state: {state_abbr}")

    cache = _cache_path("schools", state_abbr)
    cached = _read_cache(cache)
    if cached is not None:
        logger.info(f"Using cached schools for {state_abbr} ({len(cached)} records)")
        return cached

    url = f"{URBAN_API_BASE}/schools/ccd/directory/{NCES_YEAR}/?fips={fips}"
    logger.info(f"Fetching schools for {state_abbr} from Urban API...")

    all_results = []
    with httpx.Client(timeout=120.0) as client:
        page_url = url
        while page_url:
            resp = client.get(page_url)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            page_url = data.get("next")

    # Filter CA to SoCal only
    if state_abbr == "CA":
        before = len(all_results)
        all_results = [s for s in all_results if s.get("county_code") in SOCAL_COUNTY_CODES]
        logger.info(f"CA schools: {before} total → {len(all_results)} SoCal only")

    _write_cache(cache, all_results)
    logger.info(f"Fetched {len(all_results)} schools for {state_abbr}")
    return all_results


# ─────────────────────────────────────────────
# ROW BUILDERS
# ─────────────────────────────────────────────

def _build_district_row(record: dict, state_abbr: str) -> list:
    """Convert API district record to sheet row matching DISTRICT_COLUMNS."""
    name = _to_title_case(record.get("lea_name", "") or "")
    name_key = csv_importer.normalize_name(name)

    enrollment = record.get("enrollment")
    school_count = record.get("number_of_schools") or ""

    lowest = record.get("lowest_grade_offered") or ""
    highest = record.get("highest_grade_offered") or ""
    grade_span = f"{lowest}-{highest}" if lowest and highest else ""

    agency_type_code = record.get("agency_type")
    agency_type = _AGENCY_TYPE_MAP.get(agency_type_code, str(agency_type_code) if agency_type_code else "")

    county_code = record.get("county_code") or ""
    county_name = SOCAL_COUNTY_NAMES.get(county_code, "") if state_abbr == "CA" else ""

    return [
        state_abbr,
        name,
        str(record.get("leaid", "")),
        _to_title_case(record.get("city_location", "") or ""),
        _to_title_case(record.get("street_location", "") or ""),
        record.get("zip_location", "") or "",
        record.get("phone", "") or "",
        county_name,
        str(county_code),
        enrollment if enrollment is not None else "",
        school_count,
        grade_span,
        agency_type,
        record.get("latitude") or "",
        record.get("longitude") or "",
        datetime.now().strftime("%Y-%m-%d"),
        name_key,
    ]


def _build_school_row(record: dict, state_abbr: str) -> list:
    """Convert API school record to sheet row matching SCHOOL_COLUMNS."""
    name = _to_title_case(record.get("school_name", "") or "")
    name_key = csv_importer.normalize_name(name)
    district_name = _to_title_case(record.get("lea_name", "") or "")

    enrollment = record.get("enrollment")

    lowest = record.get("lowest_grade_offered") or ""
    highest = record.get("highest_grade_offered") or ""
    grade_span = f"{lowest}-{highest}" if lowest and highest else ""

    school_type_code = record.get("school_type")
    school_type = _SCHOOL_TYPE_MAP.get(school_type_code, str(school_type_code) if school_type_code else "")

    charter = record.get("charter")
    charter_str = "Yes" if charter == 1 else "No" if charter == 0 else ""

    return [
        state_abbr,
        name,
        district_name,
        str(record.get("ncessch", "")),
        str(record.get("leaid", "")),
        _to_title_case(record.get("city_location", "") or ""),
        _to_title_case(record.get("street_location", "") or ""),
        record.get("zip_location", "") or "",
        record.get("phone", "") or "",
        str(record.get("county_code") or ""),
        enrollment if enrollment is not None else "",
        grade_span,
        school_type,
        charter_str,
        record.get("latitude") or "",
        record.get("longitude") or "",
        datetime.now().strftime("%Y-%m-%d"),
        name_key,
    ]


# ─────────────────────────────────────────────
# SHEET READ
# ─────────────────────────────────────────────

def _load_tab_rows(tab_name: str, columns: list[str]) -> list[dict]:
    """Read all rows from a territory tab, return as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_territory_sheet_id()
        last_col = _col_to_letter(len(columns) - 1)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A2:{last_col}",
        ).execute()
        rows = result.get("values", [])
        records = []
        for row in rows:
            rec = {}
            for i, col in enumerate(columns):
                rec[col] = row[i] if i < len(row) else ""
            records.append(rec)
        return records
    except Exception as e:
        logger.warning(f"Failed to load {tab_name}: {e}")
        return []


def _load_territory_districts(state_filter: str = "") -> list[dict]:
    """Load districts from the Territory Districts tab."""
    rows = _load_tab_rows(TAB_TERRITORY_DISTRICTS, DISTRICT_COLUMNS)
    if state_filter:
        sf = state_filter.strip().upper()
        rows = [r for r in rows if r.get("State", "").upper() == sf]
    return rows


def _load_territory_schools(state_filter: str = "") -> list[dict]:
    """Load schools from the Territory Schools tab."""
    rows = _load_tab_rows(TAB_TERRITORY_SCHOOLS, SCHOOL_COLUMNS)
    if state_filter:
        sf = state_filter.strip().upper()
        rows = [r for r in rows if r.get("State", "").upper() == sf]
    return rows


def _clear_state_rows(service, sheet_id: str, tab_name: str, columns: list[str], state: str):
    """Delete all rows for a given state from a tab. Returns count deleted."""
    last_col = _col_to_letter(len(columns) - 1)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A2:{last_col}",
    ).execute()
    rows = result.get("values", [])

    state_col_idx = columns.index("State")
    keep_rows = []
    deleted = 0
    for row in rows:
        row_state = row[state_col_idx] if state_col_idx < len(row) else ""
        if row_state.upper() == state.upper():
            deleted += 1
        else:
            keep_rows.append(row)

    if deleted == 0:
        return 0

    # Clear data area and rewrite kept rows
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A2:{last_col}",
    ).execute()

    if keep_rows:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A2",
            valueInputOption="RAW",
            body={"values": keep_rows}
        ).execute()

    return deleted


# ─────────────────────────────────────────────
# PUBLIC FUNCTIONS
# ─────────────────────────────────────────────

def clear_territory() -> dict:
    """Clear all data rows from both territory tabs. Keeps headers."""
    cleared = {"districts": 0, "schools": 0, "errors": []}
    try:
        service = _get_service()
        sheet_id = _get_territory_sheet_id()
        for tab_name, columns in [(TAB_TERRITORY_DISTRICTS, DISTRICT_COLUMNS),
                                   (TAB_TERRITORY_SCHOOLS, SCHOOL_COLUMNS)]:
            try:
                last_col = _col_to_letter(len(columns) - 1)
                result = service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=f"'{tab_name}'!A2:{last_col}",
                ).execute()
                row_count = len(result.get("values", []))
                service.spreadsheets().values().clear(
                    spreadsheetId=sheet_id,
                    range=f"'{tab_name}'!A2:{last_col}",
                ).execute()
                if tab_name == TAB_TERRITORY_DISTRICTS:
                    cleared["districts"] = row_count
                else:
                    cleared["schools"] = row_count
            except Exception as e:
                cleared["errors"].append(f"{tab_name}: {e}")
    except Exception as e:
        cleared["errors"].append(str(e))
    cleared["success"] = True
    return cleared


def sync_territory(states: list[str] | None = None) -> dict:
    """Download NCES data and write to Territory sheet.

    Args:
        states: list of state abbreviations. None = all territory states + CA.

    Returns dict with keys: success, districts_synced, schools_synced,
    states_completed, errors.
    """
    if states is None:
        states = sorted(TERRITORY_STATES | {"CA"})
    else:
        # Normalize state inputs
        normalized = []
        for s in states:
            abbr = _normalize_state(s)
            if abbr:
                normalized.append(abbr)
            else:
                logger.warning(f"Unrecognized state: {s}")
        states = normalized

    if not states:
        return {"success": False, "error": "No valid states provided"}

    errors = []
    total_districts = 0
    total_schools = 0
    states_done = []

    # Ensure tabs exist
    d_service, d_sheet_id, _ = _ensure_tab(TAB_TERRITORY_DISTRICTS, DISTRICT_COLUMNS)
    _ensure_tab(TAB_TERRITORY_SCHOOLS, SCHOOL_COLUMNS)

    for state in states:
        logger.info(f"Syncing territory data for {state}...")
        try:
            # Fetch from API (with caching)
            districts = _fetch_districts_for_state(state)
            schools = _fetch_schools_for_state(state)

            # Build rows
            district_rows = [_build_district_row(d, state) for d in districts]
            school_rows = [_build_school_row(s, state) for s in schools]

            # Clear existing rows for this state before writing new ones
            service = _get_service()
            sheet_id = _get_territory_sheet_id()
            _clear_state_rows(service, sheet_id, TAB_TERRITORY_DISTRICTS, DISTRICT_COLUMNS, state)
            _clear_state_rows(service, sheet_id, TAB_TERRITORY_SCHOOLS, SCHOOL_COLUMNS, state)

            # Append new rows
            if district_rows:
                _append_in_chunks(service, sheet_id, TAB_TERRITORY_DISTRICTS,
                                  district_rows, errors, num_cols=len(DISTRICT_COLUMNS))
                total_districts += len(district_rows)

            if school_rows:
                _append_in_chunks(service, sheet_id, TAB_TERRITORY_SCHOOLS,
                                  school_rows, errors, num_cols=len(SCHOOL_COLUMNS))
                total_schools += len(school_rows)

            states_done.append(state)
            logger.info(f"{state}: {len(district_rows)} districts, {len(school_rows)} schools synced")

        except Exception as e:
            err_msg = f"{state}: {e}"
            logger.error(f"Sync failed for {state}: {e}")
            errors.append(err_msg)

    # Format tabs
    try:
        service = _get_service()
        sheet_id = _get_territory_sheet_id()
        _format_tab(service, sheet_id, TAB_TERRITORY_DISTRICTS, DISTRICT_COLUMNS)
        _format_tab(service, sheet_id, TAB_TERRITORY_SCHOOLS, SCHOOL_COLUMNS)
    except Exception as e:
        logger.warning(f"Tab formatting failed: {e}")

    return {
        "success": len(states_done) > 0,
        "districts_synced": total_districts,
        "schools_synced": total_schools,
        "states_completed": states_done,
        "errors": errors,
    }


def get_territory_stats(state_filter: str = "") -> dict:
    """Get territory summary statistics.

    Returns dict with: success, total_districts, total_schools, total_enrollment,
    by_state (list of dicts with state, districts, schools, enrollment).
    """
    try:
        districts = _load_territory_districts(state_filter)
        schools = _load_territory_schools(state_filter)

        # Group by state
        by_state = {}
        for d in districts:
            st = d.get("State", "?")
            if st not in by_state:
                by_state[st] = {"state": st, "districts": 0, "schools": 0, "enrollment": 0}
            by_state[st]["districts"] += 1
            try:
                by_state[st]["enrollment"] += int(d.get("Enrollment") or 0)
            except (ValueError, TypeError):
                pass

        for s in schools:
            st = s.get("State", "?")
            if st not in by_state:
                by_state[st] = {"state": st, "districts": 0, "schools": 0, "enrollment": 0}
            by_state[st]["schools"] += 1

        state_list = sorted(by_state.values(), key=lambda x: x["enrollment"], reverse=True)

        total_enrollment = sum(s["enrollment"] for s in state_list)

        return {
            "success": True,
            "total_districts": len(districts),
            "total_schools": len(schools),
            "total_enrollment": total_enrollment,
            "by_state": state_list,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_territory_gaps(state: str) -> dict:
    """Cross-reference territory districts against Active Accounts + Prospecting Queue.

    Returns dict with: success, state, total_districts, covered_count,
    prospecting_count, uncovered_count, coverage_pct, top_uncovered (list sorted by enrollment).
    """
    state_abbr = _normalize_state(state) if len(state) > 2 else state.upper()
    if not state_abbr:
        return {"success": False, "error": f"Unrecognized state: {state}"}

    try:
        # Load territory districts for this state
        districts = _load_territory_districts(state_abbr)
        if not districts:
            return {"success": False, "error": f"No territory data for {state_abbr}. Run /territory_sync {state_abbr} first."}

        # Load Active Accounts
        active_accounts = csv_importer.get_active_accounts(state_abbr)
        all_active = csv_importer.get_active_accounts()
        use_accounts = active_accounts if active_accounts else all_active

        # Build normalized name sets for active accounts
        active_district_keys = set()
        active_school_keys = set()
        school_parent_keys = set()  # normalized parent account names
        active_account_names = set()  # all account names for fuzzy matching

        for acc in use_accounts:
            name_key = csv_importer.normalize_name(
                acc.get("Active Account Name", "") or acc.get("Display Name", "")
            )
            acct_type = (acc.get("Account Type") or "").lower()
            parent = acc.get("Parent Account", "")
            acc_state = (acc.get("State") or "").upper()

            # Only consider accounts in this state (or with no state)
            if acc_state and acc_state != state_abbr:
                continue

            active_account_names.add(name_key)

            if acct_type == "district":
                active_district_keys.add(name_key)
            else:
                # school, library, company, or blank type
                active_school_keys.add(name_key)
                if parent:
                    school_parent_keys.add(csv_importer.normalize_name(parent))

        # Build school→district lookup from territory schools tab
        # so we can map active school accounts to their NCES district
        territory_schools = _load_territory_schools(state_abbr)
        school_to_district_key = {}
        for ts in territory_schools:
            s_key = ts.get("Name Key", "").lower()
            d_name = ts.get("District Name", "")
            if s_key and d_name:
                school_to_district_key[s_key] = csv_importer.normalize_name(d_name)

        # Districts with active school accounts (through territory school lookup)
        # Use fuzzy matching to handle NCES vs Salesforce naming differences
        districts_with_active_schools = set()
        matched_schools = []
        unmatched_schools = []
        for school_key in active_school_keys:
            district_key = school_to_district_key.get(school_key.lower())
            if district_key:
                districts_with_active_schools.add(district_key)
                matched_schools.append(school_key)
            else:
                # Fuzzy match: try token overlap against NCES school names
                fuzzy_key = csv_importer.fuzzy_match_name(
                    school_key.lower(), school_to_district_key, threshold=0.7)
                if fuzzy_key:
                    districts_with_active_schools.add(school_to_district_key[fuzzy_key])
                    matched_schools.append(school_key)
                else:
                    unmatched_schools.append(school_key)
        # Also add districts from Parent Account field
        districts_with_active_schools.update(school_parent_keys)

        # Load Prospecting Queue
        all_prospects = district_prospector.get_all_prospects()
        prospect_keys = set()
        for p in all_prospects:
            if p.get("State", "").upper() == state_abbr:
                prospect_keys.add(p.get("Name Key", "").lower())

        # Classify each territory district
        # "covered" = district-level active deal only
        # "has_schools" = school-level deals in this district (upward opportunity, NOT coverage)
        covered = []
        has_schools = []
        prospecting = []
        uncovered = []

        for d in districts:
            d_name_key = d.get("Name Key", "").lower()
            d_name = d.get("District Name", "")
            enrollment = 0
            try:
                enrollment = int(d.get("Enrollment") or 0)
            except (ValueError, TypeError):
                pass

            entry = {
                "name": d_name,
                "name_key": d_name_key,
                "enrollment": enrollment,
                "city": d.get("City", ""),
                "school_count": d.get("School Count", ""),
                "grade_span": d.get("Grade Span", ""),
            }

            if d_name_key in active_district_keys:
                entry["status"] = "active customer (district deal)"
                covered.append(entry)
            elif d_name_key in districts_with_active_schools:
                entry["status"] = "has active school(s) — upward opportunity"
                has_schools.append(entry)
            elif d_name_key in prospect_keys:
                entry["status"] = "in prospecting"
                prospecting.append(entry)
            else:
                entry["status"] = "uncovered"
                uncovered.append(entry)

        # Sort uncovered by enrollment descending
        uncovered.sort(key=lambda x: x["enrollment"], reverse=True)

        total = len(districts)
        covered_count = len(covered)
        has_schools_count = len(has_schools)
        prospecting_count = len(prospecting)
        uncovered_count = len(uncovered)
        # Coverage % = district-level deals only (schools in a district ≠ coverage)
        coverage_pct = round((covered_count / total) * 100, 1) if total > 0 else 0

        return {
            "success": True,
            "state": state_abbr,
            "total_districts": total,
            "covered_count": covered_count,
            "has_schools_count": has_schools_count,
            "active_schools_count": len(active_school_keys),
            "unmatched_schools": unmatched_schools,
            "prospecting_count": prospecting_count,
            "uncovered_count": uncovered_count,
            "coverage_pct": coverage_pct,
            "covered": covered,
            "has_schools": has_schools,
            "prospecting": prospecting,
            "top_uncovered": uncovered,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────
# TELEGRAM FORMATTERS
# ─────────────────────────────────────────────

def format_stats_for_telegram(stats: dict) -> str:
    """Format territory stats for Telegram."""
    if not stats.get("success"):
        return f"❌ {stats.get('error', 'Unknown error')}"

    lines = [
        f"📊 *Territory Overview*",
        f"Districts: {stats['total_districts']:,}",
        f"Schools: {stats['total_schools']:,}",
        f"Total Enrollment: {stats['total_enrollment']:,}",
        "",
        "*By State:*",
    ]

    for s in stats["by_state"]:
        lines.append(
            f"  {s['state']}: {s['districts']} districts, "
            f"{s['schools']} schools, {s['enrollment']:,} enrolled"
        )

    return "\n".join(lines)


def format_gaps_for_telegram(gaps: dict, max_show: int = 20) -> str:
    """Format gap analysis for Telegram."""
    if not gaps.get("success"):
        return f"❌ {gaps.get('error', 'Unknown error')}"

    has_schools_count = gaps.get("has_schools_count", 0)
    active_schools_count = gaps.get("active_schools_count", 0)
    lines = [
        f"🗺️ *Territory Gaps — {gaps['state']}*",
        f"Total NCES districts: {gaps['total_districts']}",
        f"Active school accounts: {active_schools_count}",
        f"✅ District deals: {gaps['covered_count']}",
        f"🏫 Districts w/ school account(s): {has_schools_count}",
        f"🔄 In prospecting: {gaps['prospecting_count']}",
        f"⬜ Uncovered: {gaps['uncovered_count']}",
        f"District coverage: {gaps['coverage_pct']}%",
    ]

    # Show unmatched schools (not found in NCES data — likely private/charter)
    unmatched = gaps.get("unmatched_schools", [])
    if unmatched:
        lines.append("")
        lines.append("*School accounts not matched to an NCES district:*")
        for s in unmatched:
            lines.append(f"  ⚠️ {s}")

    # Show districts with school-level deals (upward opportunities)
    has_schools = gaps.get("has_schools", [])
    if has_schools:
        lines.append("")
        lines.append("*Upward opportunities (school deals, no district deal):*")
        for d in sorted(has_schools, key=lambda x: x["enrollment"], reverse=True):
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            lines.append(f"  📈 {d['name']} — {enrollment_str} students")

    top = gaps.get("top_uncovered", [])
    if top:
        lines.append("")
        shown = min(len(top), max_show)
        lines.append(f"*Top {shown} Uncovered (by enrollment):*")
        for i, d in enumerate(top[:max_show]):
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            lines.append(
                f"  {i+1}. {d['name']} — {enrollment_str} students"
                f"{', ' + d['city'] if d['city'] else ''}"
            )
        if len(top) > max_show:
            lines.append(f"  ... and {len(top) - max_show} more")

    return "\n".join(lines)


def write_gaps_to_doc(gaps: dict, gas_bridge) -> dict:
    """Write full gap analysis to a Google Doc for large results.

    Args:
        gaps: result from get_territory_gaps()
        gas_bridge: GASBridge instance for creating Google Docs

    Returns: {success, url, error}
    """
    if not gaps.get("success"):
        return {"success": False, "error": gaps.get("error", "No gap data")}

    state = gaps["state"]
    title = f"Territory Gaps — {state} — {datetime.now().strftime('%Y-%m-%d')}"

    has_schools_count = gaps.get("has_schools_count", 0)
    lines = [
        f"Territory Gap Analysis: {state}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Total NCES Districts: {gaps['total_districts']}",
        f"District Deals: {gaps['covered_count']}",
        f"Has School Account(s): {has_schools_count}",
        f"In Prospecting: {gaps['prospecting_count']}",
        f"Uncovered: {gaps['uncovered_count']}",
        f"District Coverage: {gaps['coverage_pct']}%",
        "",
        "=" * 60,
    ]

    # District deals
    if gaps.get("covered"):
        lines.append("")
        lines.append(f"DISTRICT DEALS ({len(gaps['covered'])})")
        lines.append("-" * 40)
        for d in sorted(gaps["covered"], key=lambda x: x["enrollment"], reverse=True):
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            lines.append(f"  {d['name']} — {enrollment_str} students — {d['status']}")

    # Upward opportunities
    if gaps.get("has_schools"):
        lines.append("")
        lines.append(f"UPWARD OPPORTUNITIES — school deals, no district deal ({len(gaps['has_schools'])})")
        lines.append("-" * 40)
        for d in sorted(gaps["has_schools"], key=lambda x: x["enrollment"], reverse=True):
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            lines.append(f"  {d['name']} — {enrollment_str} students — {d['status']}")

    # Prospecting
    if gaps.get("prospecting"):
        lines.append("")
        lines.append(f"IN PROSPECTING ({len(gaps['prospecting'])})")
        lines.append("-" * 40)
        for d in sorted(gaps["prospecting"], key=lambda x: x["enrollment"], reverse=True):
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            lines.append(f"  {d['name']} — {enrollment_str} students")

    # Uncovered
    if gaps.get("top_uncovered"):
        lines.append("")
        lines.append(f"UNCOVERED ({len(gaps['top_uncovered'])})")
        lines.append("-" * 40)
        for d in gaps["top_uncovered"]:
            enrollment_str = f"{d['enrollment']:,}" if d['enrollment'] else "?"
            city = f", {d['city']}" if d['city'] else ""
            lines.append(f"  {d['name']} — {enrollment_str} students{city}")

    content = "\n".join(lines)

    try:
        folder_id = os.environ.get("SEQUENCES_FOLDER_ID", "")
        if folder_id and "?" in folder_id:
            folder_id = folder_id.split("?")[0]
        result = gas_bridge.create_google_doc(title, content, folder_id)
        if result.get("success"):
            return {"success": True, "url": result.get("url", "")}
        else:
            return {"success": False, "error": result.get("error", "Doc creation failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}
