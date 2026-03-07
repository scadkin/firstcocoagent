"""
tools/district_prospector.py — Scout Phase 6E District Prospecting Queue.

Two prospecting strategies:
  1. UPWARD (reference-based): districts with active school accounts but no
     district-level deal. Leverage the foothold to pitch district-wide.
  2. COLD: districts with no CodeCombat presence at all.

Manages the "Prospecting Queue" tab in the Master Google Sheet.

Usage (module-level, not a class):
  import tools.district_prospector as district_prospector
  result = district_prospector.discover_districts("Texas")
"""

import json
import logging
import os
import re
import time
from datetime import datetime

import httpx

import tools.csv_importer as csv_importer
import tools.sheets_writer as sheets_writer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

TAB_PROSPECT_QUEUE = "Prospecting Queue"

PROSPECT_COLUMNS = [
    "District Name",    # display name
    "Name Key",         # normalized via csv_importer.normalize_name()
    "State",
    "Strategy",         # "upward" | "cold"
    "Source",           # "web_search" | "manual" | "upward_auto"
    "Status",           # "pending" | "approved" | "researching" | "complete" | "skipped"
    "Priority",         # numeric score (higher = more important)
    "Date Added",
    "Date Approved",
    "Sequence Doc URL",
    "Notes",
    "Est. Enrollment",
    "School Count",
    "Total Licenses",
]

# Steven's territory
_TERRITORY_STATES = {
    "IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE", "TX",
}
_STATE_NAME_TO_ABBR = {
    "illinois": "IL", "pennsylvania": "PA", "ohio": "OH", "michigan": "MI",
    "connecticut": "CT", "oklahoma": "OK", "massachusetts": "MA", "indiana": "IN",
    "nevada": "NV", "tennessee": "TN", "nebraska": "NE", "texas": "TX",
    "california": "CA",
}

# Regex for district name extraction from search results
# Limit prefix to 1-5 words to avoid capturing entire sentences
_SUFFIX_PATTERN = (
    r"(?:Independent\s+School\s+District|Unified\s+School\s+District|"
    r"Community\s+Unit\s+School\s+District|Community\s+School\s+District|"
    r"School\s+District|Public\s+Schools|CISD|CUSD|GISD|NISD|ISD|USD)"
)
_DISTRICT_RE = re.compile(
    r"\b((?:[\w\-\'\.]+\s+){1,5}" + _SUFFIX_PATTERN + r")\b",
    re.IGNORECASE,
)

# Words that cannot start a real district name
_BAD_STARTS = {
    "high", "middle", "elementary", "schools", "school", "district", "districts",
    "in", "the", "a", "an", "of", "and", "or", "for", "from", "with", "other",
    "staff", "are", "is", "all", "best", "top", "new", "our", "their", "your",
    "this", "that", "about", "many", "some", "most", "every", "each", "any",
    "no", "more", "has", "have", "had", "was", "were", "been", "being", "its", "it",
    "tx", "ca", "oh", "pa", "il", "mi", "ct", "ok", "ma", "nv", "tn", "ne",
}

# Google Sheets credentials (shared pattern with csv_importer)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ─────────────────────────────────────────────
# INTERNAL: SHEETS HELPERS
# ─────────────────────────────────────────────

def _get_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build as gapi_build
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gapi_build("sheets", "v4", credentials=creds)


def _get_sheet_id():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID not set")
    return sheet_id


def _ensure_tab():
    """Create Prospecting Queue tab if missing. Always overwrite header row."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_PROSPECT_QUEUE not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_PROSPECT_QUEUE}}}]}
        ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A1",
        valueInputOption="RAW",
        body={"values": [PROSPECT_COLUMNS]}
    ).execute()

    return service, sheet_id


def _load_all_prospects() -> list[dict]:
    """Load all rows from Prospecting Queue tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A:N"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        prospects = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            prospects.append(dict(zip(headers, padded)))
        return prospects
    except Exception as e:
        logger.error(f"_load_all_prospects error: {e}")
        return []


def clear_queue():
    """Delete all data rows from the Prospecting Queue tab (keeps header)."""
    service, sheet_id = _ensure_tab()
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A2:N9999",
    ).execute()
    logger.info("Prospecting Queue cleared")


def _write_rows(rows: list[list]):
    """Append rows to the Prospecting Queue tab."""
    if not rows:
        return
    service, sheet_id = _ensure_tab()
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()


def _update_status(name_key: str, new_status: str, extra_updates: dict | None = None):
    """Find a row by name_key and update its Status + optional extra columns."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A:N"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return

    headers = rows[0]
    name_key_idx = headers.index("Name Key") if "Name Key" in headers else 1
    status_idx = headers.index("Status") if "Status" in headers else 5

    for row_num, row in enumerate(rows[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        if padded[name_key_idx] == name_key:
            padded[status_idx] = new_status
            if extra_updates:
                for col_name, val in extra_updates.items():
                    if col_name in headers:
                        padded[headers.index(col_name)] = val
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{TAB_PROSPECT_QUEUE}'!A{row_num}",
                valueInputOption="RAW",
                body={"values": [padded[:len(headers)]]}
            ).execute()
            return


# ─────────────────────────────────────────────
# INTERNAL: PRIORITY SCORING
# ─────────────────────────────────────────────

def _calculate_priority(strategy: str, school_count: int, total_licenses: int,
                        est_enrollment: int) -> int:
    """
    Returns a numeric priority score. Higher = more important.

    Tiers:
      1 (900-999): Upward, 3+ active schools
      2 (800-899): Upward, highest licenses/revenue
      3 (700-799): Cold, small/medium districts (<25K enrollment)
      4 (600-699): Upward, 1 active school in large district
      5 (500-599): Free usage (deferred)
      6-7 (400-499): Proximity (deferred)
      8 (300-399): Cold, large districts by est. budget
    """
    if strategy == "upward":
        if school_count >= 3:
            # Tier 1: most active schools
            return 900 + min(school_count * 10, 99)
        elif total_licenses >= 50 or school_count == 2:
            # Tier 2: high license count or 2 schools
            return 800 + min(total_licenses, 99)
        else:
            # Tier 4: 1 active school
            return 600 + min(total_licenses, 99)
    else:
        # Cold strategy
        if est_enrollment <= 0:
            # No enrollment data — default to mid-range cold
            return 500
        elif est_enrollment < 25000:
            # Tier 3: small/medium (quicker sales, less red tape)
            return 700 + max(0, 99 - (est_enrollment // 300))
        else:
            # Tier 8: large districts
            return 300 + max(0, 99 - (est_enrollment // 5000))


# ─────────────────────────────────────────────
# INTERNAL: SERPER SEARCH
# ─────────────────────────────────────────────

def _normalize_state(state_input: str) -> str:
    """Convert state name or abbreviation to 2-letter uppercase code."""
    s = state_input.strip()
    if len(s) == 2:
        return s.upper()
    return _STATE_NAME_TO_ABBR.get(s.lower(), s.upper()[:2])


def _search_districts_serper(state: str) -> list[dict]:
    """
    Run 2-3 Serper queries to discover districts in a state.
    Returns list of {name, state, est_enrollment}.
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY not set")
        return []

    queries = [
        f'"largest school districts in {state}" enrollment',
        f'"{state} school districts" list directory',
        f'"{state}" "school district" "computer science" OR "STEM"',
    ]

    all_results = []
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=15.0) as client:
        for query in queries:
            try:
                resp = client.post(
                    SERPER_URL,
                    headers=headers,
                    json={"q": query, "num": 10},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    all_results.extend(data.get("organic", []))
                else:
                    logger.warning(f"Serper query failed ({resp.status_code}): {query}")
            except Exception as e:
                logger.warning(f"Serper request error: {e}")
            time.sleep(0.3)

    return _extract_district_names(all_results, state)


def _clean_district_name(raw_name: str) -> str | None:
    """Clean an extracted district name. Returns None if it's garbage."""
    name = raw_name.strip()
    # Strip leading/trailing punctuation
    name = re.sub(r'^[\.\,\;\:\-\s]+', '', name)
    name = re.sub(r'[\.\,\;\:\-\s]+$', '', name)

    # If there's a dash/colon separator, take only the part containing the suffix
    for sep in [" - ", " — ", " – ", ": "]:
        if sep in name:
            parts = name.split(sep)
            # Keep the part that contains a district suffix keyword
            for part in parts:
                if re.search(r"(?:School District|Public Schools|ISD|USD|CISD|CUSD|GISD|NISD)\b", part, re.IGNORECASE):
                    name = part.strip()
                    break

    if len(name) < 8 or len(name) > 80:
        return None

    # Remove leading filler words (strip punctuation from each word before checking)
    words = name.split()
    while words and re.sub(r'[^a-zA-Z]', '', words[0]).lower() in _BAD_STARTS:
        words.pop(0)

    # Strip leading words that look like website names or concatenated text
    # e.g. "SATXtoday" — mixed case beyond normal title case or abbreviation
    while words:
        first_clean = re.sub(r'[^a-zA-Z]', '', words[0])
        if not first_clean:
            words.pop(0)
            continue
        if len(first_clean) > 5 and not first_clean.isupper() and not first_clean.istitle():
            words.pop(0)
            continue
        break

    if len(words) < 2:  # Need at least "Name ISD" or similar
        return None

    name = " ".join(words)

    # Reject if multiple lowercase words at start (looks like a sentence, not a name)
    name_words = name.split()
    lowercase_start = sum(1 for w in name_words[:3] if w[0].islower() and w.lower() not in ("of", "de", "la", "del"))
    if lowercase_start >= 2:
        return None

    return name


def _extract_district_names(serper_results: list[dict], state: str) -> list[dict]:
    """Extract district names from Serper organic results."""
    found: dict[str, dict] = {}  # name_key → {name, state, est_enrollment}

    for result in serper_results:
        text = (result.get("title", "") + " " + result.get("snippet", ""))

        # Find district name patterns
        matches = _DISTRICT_RE.findall(text)
        for match in matches:
            name = _clean_district_name(match)
            if not name:
                continue
            name_key = csv_importer.normalize_name(name)
            if not name_key or len(name_key) < 3:
                continue
            if name_key not in found:
                # Try to extract enrollment from nearby text
                enrollment = 0
                enroll_match = re.search(
                    r"([\d,]+)\s*(?:students|enrollment|pupils)", text, re.IGNORECASE
                )
                if enroll_match:
                    try:
                        enrollment = int(enroll_match.group(1).replace(",", ""))
                    except ValueError:
                        pass
                found[name_key] = {
                    "name": name,
                    "state": _normalize_state(state),
                    "est_enrollment": enrollment,
                }

    return list(found.values())


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def discover_districts(state: str, max_results: int = 15) -> dict:
    """
    Search for school districts in a state via Serper.
    Dedup against Active Accounts and existing queue.
    Add new districts to Prospecting Queue with Status="pending", Strategy="cold".

    Returns:
      {success, discovered, already_known, new_added, districts, error}
    """
    try:
        state_abbr = _normalize_state(state)
        territory_warning = ""
        if state_abbr not in _TERRITORY_STATES and state_abbr != "CA":
            territory_warning = f"Note: {state_abbr} is outside your primary territory."

        # Search
        raw_districts = _search_districts_serper(state)
        if not raw_districts:
            return {
                "success": True, "discovered": 0, "already_known": 0,
                "new_added": 0, "districts": [], "error": "",
                "territory_warning": territory_warning,
            }

        # Load existing data for dedup
        active_accounts = csv_importer.get_active_accounts()
        active_keys = {
            csv_importer.normalize_name(a.get("Display Name", ""))
            for a in active_accounts
        }

        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects}

        # Filter and add
        new_rows = []
        already_known = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        for d in raw_districts[:max_results]:
            name_key = csv_importer.normalize_name(d["name"])
            if name_key in active_keys or name_key in prospect_keys:
                already_known += 1
                continue

            priority = _calculate_priority("cold", 0, 0, d.get("est_enrollment", 0))
            row = [
                d["name"],           # District Name
                name_key,            # Name Key
                d["state"],          # State
                "cold",              # Strategy
                "web_search",        # Source
                "pending",           # Status
                str(priority),       # Priority
                now,                 # Date Added
                "",                  # Date Approved
                "",                  # Sequence Doc URL
                territory_warning,   # Notes
                str(d.get("est_enrollment", "")),  # Est. Enrollment
                "",                  # School Count
                "",                  # Total Licenses
            ]
            new_rows.append(row)
            prospect_keys.add(name_key)  # prevent within-batch dupes

        if new_rows:
            _write_rows(new_rows)

        return {
            "success": True,
            "discovered": len(raw_districts),
            "already_known": already_known,
            "new_added": len(new_rows),
            "districts": [r[0] for r in new_rows],
            "error": "",
            "territory_warning": territory_warning,
        }

    except Exception as e:
        logger.error(f"discover_districts error: {e}")
        return {
            "success": False, "discovered": 0, "already_known": 0,
            "new_added": 0, "districts": [], "error": str(e),
        }


def suggest_upward_targets() -> dict:
    """
    Pull districts with active school accounts (upward/reference targets).
    Filter out already-queued districts, enrich with license data, add to queue.

    Returns:
      {success, new_added, already_known, districts, error}
    """
    try:
        districts_with_schools = csv_importer.get_districts_with_schools()
        if not districts_with_schools:
            return {
                "success": True, "new_added": 0, "already_known": 0,
                "districts": [], "error": "",
            }

        # Load existing queue for dedup
        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects}

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_rows = []
        already_known = 0

        for dist in districts_with_schools:
            name_key = dist["name_key"]
            if name_key in prospect_keys:
                already_known += 1
                continue

            school_count = dist["school_count"]
            # Sum licenses across schools
            total_licenses = 0
            for school in dist.get("schools", []):
                try:
                    lic = int(school.get("active_licenses", 0) or 0)
                    total_licenses += lic
                except (ValueError, TypeError):
                    pass

            priority = _calculate_priority("upward", school_count, total_licenses, 0)
            school_names = [s["display_name"] for s in dist.get("schools", [])[:5]]

            row = [
                dist["display_name"],      # District Name
                name_key,                  # Name Key
                dist.get("state", ""),     # State
                "upward",                  # Strategy
                "upward_auto",             # Source
                "pending",                 # Status
                str(priority),             # Priority
                now,                       # Date Added
                "",                        # Date Approved
                "",                        # Sequence Doc URL
                f"Schools: {', '.join(school_names)}",  # Notes
                "",                        # Est. Enrollment
                str(school_count),         # School Count
                str(total_licenses),       # Total Licenses
            ]
            new_rows.append(row)
            prospect_keys.add(name_key)

        if new_rows:
            _write_rows(new_rows)

        return {
            "success": True,
            "new_added": len(new_rows),
            "already_known": already_known,
            "districts": [r[0] for r in new_rows],
            "error": "",
        }

    except Exception as e:
        logger.error(f"suggest_upward_targets error: {e}")
        return {
            "success": False, "new_added": 0, "already_known": 0,
            "districts": [], "error": str(e),
        }


def add_district(name: str, state: str, notes: str = "", strategy: str = "cold") -> dict:
    """
    Manually add a district to the prospecting queue.

    Returns:
      {success, message, already_exists}
    """
    try:
        name_key = csv_importer.normalize_name(name)
        state_abbr = _normalize_state(state)

        # Dedup
        active_accounts = csv_importer.get_active_accounts()
        active_keys = {
            csv_importer.normalize_name(a.get("Display Name", ""))
            for a in active_accounts
        }
        if name_key in active_keys:
            return {
                "success": False,
                "message": f"'{name}' is already in Active Accounts (existing customer).",
                "already_exists": True,
            }

        existing_prospects = _load_all_prospects()
        for p in existing_prospects:
            if p.get("Name Key", "") == name_key:
                return {
                    "success": False,
                    "message": f"'{name}' is already in the prospecting queue (status: {p.get('Status', '?')}).",
                    "already_exists": True,
                }

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        priority = _calculate_priority(strategy, 0, 0, 0)

        row = [
            name,           # District Name
            name_key,       # Name Key
            state_abbr,     # State
            strategy,       # Strategy
            "manual",       # Source
            "pending",      # Status
            str(priority),  # Priority
            now,            # Date Added
            "",             # Date Approved
            "",             # Sequence Doc URL
            notes,          # Notes
            "",             # Est. Enrollment
            "",             # School Count
            "",             # Total Licenses
        ]
        _write_rows([row])

        return {
            "success": True,
            "message": f"Added '{name}' ({state_abbr}) to prospecting queue.",
            "already_exists": False,
        }

    except Exception as e:
        return {"success": False, "message": f"Error: {e}", "already_exists": False}


def get_pending(limit: int = 5) -> list[dict]:
    """Get pending districts sorted by Priority descending."""
    prospects = _load_all_prospects()
    pending = [p for p in prospects if p.get("Status", "").lower() == "pending"]

    # Sort by Priority descending
    def sort_key(p):
        try:
            return int(p.get("Priority", 0))
        except (ValueError, TypeError):
            return 0
    pending.sort(key=sort_key, reverse=True)

    return pending[:limit]


def get_all_prospects(status_filter: str = "") -> list[dict]:
    """Get all prospects, optionally filtered by status."""
    prospects = _load_all_prospects()
    if status_filter:
        prospects = [p for p in prospects if p.get("Status", "").lower() == status_filter.lower()]
    return prospects


def approve_districts(indices: list[int], batch: list[dict]) -> list[dict]:
    """
    Mark districts as approved by 1-based index into the given batch.
    Returns list of approved district dicts.
    """
    approved = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for idx in indices:
        if 1 <= idx <= len(batch):
            district = batch[idx - 1]
            name_key = district.get("Name Key", "")
            _update_status(name_key, "approved", {"Date Approved": now})
            approved.append(district)
    return approved


def skip_districts(indices: list[int], batch: list[dict]) -> list[dict]:
    """Mark districts as skipped by 1-based index into the given batch."""
    skipped = []
    for idx in indices:
        if 1 <= idx <= len(batch):
            district = batch[idx - 1]
            name_key = district.get("Name Key", "")
            _update_status(name_key, "skipped")
            skipped.append(district)
    return skipped


def mark_researching(name_key: str):
    """Update status to 'researching'."""
    _update_status(name_key, "researching")


def mark_complete(name_key: str, sequence_doc_url: str = ""):
    """Update status to 'complete' and optionally set sequence doc URL."""
    extras = {}
    if sequence_doc_url:
        extras["Sequence Doc URL"] = sequence_doc_url
    _update_status(name_key, "complete", extras if extras else None)


# ─────────────────────────────────────────────
# TELEGRAM FORMATTING
# ─────────────────────────────────────────────

def format_batch_for_telegram(districts: list[dict], label: str = "Prospecting Suggestions") -> str:
    """Format a batch of districts for Telegram with numbered items."""
    if not districts:
        return "No pending districts in the queue."

    lines = [f"*{label}*\n"]
    for i, d in enumerate(districts, 1):
        strategy = d.get("Strategy", "cold")
        tag = "REF" if strategy == "upward" else "COLD"
        name = d.get("District Name", "?")
        state = d.get("State", "")
        priority = d.get("Priority", "")
        school_count = d.get("School Count", "")
        enrollment = d.get("Est. Enrollment", "")

        line = f"{i}. [{tag}] *{name}* ({state})"
        details = []
        if school_count and str(school_count) != "0":
            details.append(f"{school_count} active schools")
        if enrollment and str(enrollment) != "0" and str(enrollment) != "":
            details.append(f"~{enrollment} students")
        if details:
            line += f" — {', '.join(details)}"
        lines.append(line)

    lines.append("")
    lines.append("Reply `/prospect_approve 1,3` or `/prospect_skip 2,4`")
    return "\n".join(lines)


def format_all_for_telegram(districts: list[dict]) -> str:
    """Format full queue grouped by status."""
    if not districts:
        return "Prospecting queue is empty."

    by_status: dict[str, list] = {}
    for d in districts:
        status = d.get("Status", "unknown")
        by_status.setdefault(status, []).append(d)

    lines = ["*Prospecting Queue*\n"]

    status_order = ["pending", "approved", "researching", "complete", "skipped"]
    status_emoji = {
        "pending": "⏳", "approved": "✅", "researching": "🔍",
        "complete": "📄", "skipped": "⏭",
    }

    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        emoji = status_emoji.get(status, "•")
        lines.append(f"{emoji} *{status.upper()}* ({len(group)})")
        for d in group[:10]:  # cap at 10 per status to keep message manageable
            strategy = d.get("Strategy", "cold")
            tag = "REF" if strategy == "upward" else "COLD"
            name = d.get("District Name", "?")
            state = d.get("State", "")
            extra = ""
            if status == "complete" and d.get("Sequence Doc URL"):
                extra = f" — [Doc]({d['Sequence Doc URL']})"
            lines.append(f"  [{tag}] {name} ({state}){extra}")
        if len(group) > 10:
            lines.append(f"  _...and {len(group) - 10} more_")
        lines.append("")

    total = len(districts)
    lines.append(f"Total: {total} districts in queue")
    return "\n".join(lines)
