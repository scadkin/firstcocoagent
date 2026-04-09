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
import tools.pipeline_tracker as pipeline_tracker
import tools.sheets_writer as sheets_writer
import tools.territory_data as territory_data

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

# Cost tracking for C4 scans — Sonnet pricing: $3/MTok input, $15/MTok output
_c4_cost_tracker = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

def _reset_cost_tracker():
    _c4_cost_tracker["input_tokens"] = 0
    _c4_cost_tracker["output_tokens"] = 0
    _c4_cost_tracker["api_calls"] = 0

def _track_claude_usage(response):
    """Extract and accumulate token usage from a Claude API response."""
    usage = getattr(response, "usage", None)
    if usage:
        _c4_cost_tracker["input_tokens"] += getattr(usage, "input_tokens", 0)
        _c4_cost_tracker["output_tokens"] += getattr(usage, "output_tokens", 0)
        _c4_cost_tracker["api_calls"] += 1

def _get_estimated_cost() -> float:
    """Estimate cost in USD. Sonnet: $3/MTok in, $15/MTok out."""
    return (_c4_cost_tracker["input_tokens"] * 3.0 / 1_000_000 +
            _c4_cost_tracker["output_tokens"] * 15.0 / 1_000_000)

TAB_PROSPECT_QUEUE = "Prospecting Queue"

PROSPECT_COLUMNS = [
    "State",
    "Account Name",     # the actual deal target (school name or district name)
    "Email",            # contact email (populated by C4, blank for other strategies)
    "First Name",       # contact first name (populated by C4)
    "Last Name",        # contact last name (populated by C4)
    "Deal Level",       # "school" | "district" — was the deal at a school or district?
    "Parent District",  # for school-level deals: the parent district name. Empty for district-level.
    "Name Key",         # normalized via csv_importer.normalize_name()
    "Strategy",         # "upward" | "cold" | "winback" | "cold_license_request" | "trigger"
    "Source",           # "web_search" | "manual" | "upward_auto" | "pipeline_closed" | "outreach" | "signal"
    "Status",           # "pending" | "approved" | "researching" | "draft" | "complete" | "skipped"
    "Priority",         # numeric score (higher = more important)
    "Date Added",
    "Date Approved",
    "Sequence Doc URL",
    "Est. Enrollment",
    "School Count",
    "Total Licenses",
    "Signal ID",        # SIG-XXX from Signals tab (for attribution tracking)
    "Notes",            # always last
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

    # Clear entire header row first (removes stale columns from old schema — 19 cols now)
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A1:Z1",
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A1",
        valueInputOption="RAW",
        body={"values": [PROSPECT_COLUMNS]}
    ).execute()

    return service, sheet_id


def migrate_prospect_columns() -> dict:
    """
    Migrate Prospecting Queue rows to current column layout (20 columns).
    Handles 16→19 (adds Email/First/Last) and 19→20 (adds Signal ID before Notes).

    Safe to run multiple times — detects which rows need migration.
    Returns {migrated, total, already_correct, errors}.
    """
    _KNOWN_STRATEGIES = {"upward", "cold", "winback", "cold_license_request", "trigger", "sequence_reengagement", "webinar_attendee", "webinar_missed"}
    num_cols = len(PROSPECT_COLUMNS)  # 20

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A:Z"
        ).execute()
        all_rows = result.get("values", [])

        if len(all_rows) < 2:
            return {"migrated": 0, "total": 0, "already_correct": 0, "errors": ""}

        data_rows = all_rows[1:]  # skip header
        migrated_count = 0
        already_correct = 0
        new_data = []

        for row in data_rows:
            padded = list(row) + [""] * max(0, num_cols - len(row))

            val_at_5 = padded[5] if len(padded) > 5 else ""
            val_at_8 = padded[8] if len(padded) > 8 else ""

            if val_at_8 in _KNOWN_STRATEGIES and len(row) >= 20:
                # Already in 20-column format
                new_data.append(padded[:num_cols])
                already_correct += 1
            elif val_at_8 in _KNOWN_STRATEGIES and len(row) <= 19:
                # 19-column format — insert empty Signal ID before Notes (last col)
                migrated_row = padded[:18] + [""] + [padded[18]]
                new_data.append(migrated_row[:num_cols])
                migrated_count += 1
            elif val_at_5 in _KNOWN_STRATEGIES:
                # Old 16-column format — insert 3 empty cols after Account Name + Signal ID
                migrated_row = padded[:2] + ["", "", ""] + padded[2:]
                migrated_row = migrated_row[:18] + [""] + [migrated_row[18] if len(migrated_row) > 18 else ""]
                new_data.append(migrated_row[:num_cols])
                migrated_count += 1
            else:
                new_data.append(padded[:num_cols])
                logger.warning(f"migrate_prospect_columns: unknown row format, keeping as-is: {padded[:6]}")

        # Clear all data and rewrite with correct header + migrated data
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A1:Z9999",
        ).execute()

        all_output = [PROSPECT_COLUMNS] + new_data
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A1",
            valueInputOption="RAW",
            body={"values": all_output}
        ).execute()

        logger.info(
            f"migrate_prospect_columns: {migrated_count} migrated, "
            f"{already_correct} already correct, {len(new_data)} total rows"
        )

        return {
            "migrated": migrated_count,
            "total": len(new_data),
            "already_correct": already_correct,
            "errors": "",
        }

    except Exception as e:
        logger.error(f"migrate_prospect_columns error: {e}")
        return {"migrated": 0, "total": 0, "already_correct": 0, "errors": str(e)}


def _load_all_prospects() -> list[dict]:
    """Load all rows from Prospecting Queue tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A:T"
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
        range=f"'{TAB_PROSPECT_QUEUE}'!A2:Z9999",
    ).execute()
    logger.info("Prospecting Queue cleared")


def clear_by_strategy(strategy: str) -> dict:
    """Delete only rows matching a specific strategy (e.g., 'cold_license_request').
    Keeps all other rows intact. Returns {cleared, total_before, total_after}."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A:S"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return {"cleared": 0, "total_before": 0, "total_after": 0}

    headers = rows[0]
    strategy_idx = headers.index("Strategy") if "Strategy" in headers else 5
    total_before = len(rows) - 1

    # Keep header + rows that don't match the strategy
    kept_rows = [headers]
    cleared = 0
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        if padded[strategy_idx] == strategy:
            cleared += 1
        else:
            kept_rows.append(row)

    # Clear and rewrite
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PROSPECT_QUEUE}'!A1:Z9999",
    ).execute()

    if kept_rows:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A1",
            valueInputOption="RAW",
            body={"values": kept_rows}
        ).execute()

    logger.info(f"Cleared {cleared} '{strategy}' entries from Prospecting Queue")
    return {"cleared": cleared, "total_before": total_before, "total_after": len(kept_rows) - 1}


_KNOWN_STRATEGIES = {"upward", "cold", "winback", "cold_license_request", "sequence_reengagement", "webinar_attendee", "webinar_missed"}


def cleanup_prospect_queue() -> dict:
    """Remove rows with invalid/empty Strategy and deduplicate by Name Key (keep last).

    Returns {total_before, total_after, removed_invalid, removed_duplicate, errors}.
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A:T"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return {"total_before": 0, "total_after": 0,
                    "removed_invalid": 0, "removed_duplicate": 0, "errors": []}

        headers = rows[0]
        strategy_idx = headers.index("Strategy") if "Strategy" in headers else 8
        name_key_idx = headers.index("Name Key") if "Name Key" in headers else 7

        total_before = len(rows) - 1

        # Step 1: filter out rows with invalid or empty strategy
        valid_rows = []
        removed_invalid = 0
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            strategy = padded[strategy_idx].strip().lower()
            if strategy in _KNOWN_STRATEGIES:
                valid_rows.append(row)
            else:
                removed_invalid += 1

        # Step 2: deduplicate by Name Key (keep last occurrence)
        seen = {}
        for i, row in enumerate(valid_rows):
            padded = row + [""] * (len(headers) - len(row))
            nk = padded[name_key_idx].strip().lower()
            if nk:
                seen[nk] = i  # overwrite — keeps last
            else:
                # No name key — keep the row (don't drop unknowns)
                seen[f"__no_key_{i}"] = i

        deduped_indices = sorted(seen.values())
        deduped_rows = [valid_rows[i] for i in deduped_indices]
        removed_duplicate = len(valid_rows) - len(deduped_rows)

        total_after = len(deduped_rows)

        # Rewrite sheet: clear all then write header + clean rows
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A1:Z9999",
        ).execute()

        write_data = [headers] + deduped_rows
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A1",
            valueInputOption="RAW",
            body={"values": write_data}
        ).execute()

        logger.info(
            f"Prospecting Queue cleanup: {total_before} → {total_after} "
            f"(removed {removed_invalid} invalid, {removed_duplicate} dupes)"
        )
        return {
            "total_before": total_before,
            "total_after": total_after,
            "removed_invalid": removed_invalid,
            "removed_duplicate": removed_duplicate,
            "errors": [],
        }
    except Exception as e:
        logger.error(f"cleanup_prospect_queue error: {e}")
        return {
            "total_before": 0, "total_after": 0,
            "removed_invalid": 0, "removed_duplicate": 0,
            "errors": [str(e)],
        }


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
        range=f"'{TAB_PROSPECT_QUEUE}'!A:S"
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
                        est_enrollment: int, **kwargs) -> int:
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
    elif strategy == "winback":
        # Winback: between upward and cold (550-749)
        # Higher amount = higher priority
        amount = kwargs.get("amount", 0.0)
        if amount >= 10000:
            return 700 + min(int(amount // 1000), 49)
        elif amount >= 1000:
            return 650 + min(int(amount // 200), 49)
        else:
            return 550 + min(int(amount), 99)
    elif strategy == "proximity":
        # Tier 6-7 (400-699): closer = higher priority
        distance = kwargs.get("distance_miles", 50)
        if distance <= 10:
            base = 600
        elif distance <= 25:
            base = 500
        else:
            base = 400
        enrollment_bonus = min(int(est_enrollment / 300), 99) if est_enrollment > 0 else 0
        return base + enrollment_bonus
    elif strategy == "esa_cluster":
        # Between proximity and cold (450-599)
        # More active accounts in the ESA region = higher priority
        active_in_esa = kwargs.get("active_in_esa", 0)
        base = 450 + min(active_in_esa * 30, 100)
        enrollment_bonus = min(int(est_enrollment / 500), 49) if est_enrollment > 0 else 0
        return base + enrollment_bonus
    elif strategy == "intra_district":
        # F1 Second Buyer Expansion: sibling schools in covered districts.
        # Highest-warm leads — same district as existing customer.
        # Tier 1.5 (750-849): higher than upward tier 4, lower than upward tier 1-2.
        return 750 + min(int(est_enrollment / 100), 99)
    elif strategy == "cs_funding_recipient":
        # F4 State CS Funding: district just received CS-specific funding.
        # Pre-qualified — they have budget allocated.
        # Tier 1.2 (800-899): very high. Above winback, below upward tier 1.
        return 800 + min(int(est_enrollment / 200), 99)
    elif strategy == "competitor_displacement":
        # F2 Competitor Displacement: district uses a competitor.
        # Pre-sold on CS, may be approaching renewal.
        # Tier 2.5 (650-749): moderate-warm. Similar to winback range.
        return 650 + min(int(est_enrollment / 250), 99)
    elif strategy == "csta_partnership":
        # F5 CSTA Chapter Partnership: CSTA chapter leader with district affiliation.
        # Warm entry point — partner with the chapter, build goodwill, get intro to
        # district decision-makers via the chapter leader relationship.
        # Tier 2.7 (620-719): just below competitor_displacement. Individual teacher
        # relationships are warm but not deal-ready the way funding or displacement is.
        return 620 + min(int(est_enrollment / 300), 99)
    elif strategy == "homeschool_coop":
        # F10 Homeschool Co-op: parent-organized groups, 20-200 students.
        # Small deal sizes but short sales cycles and no procurement red tape.
        # Tier 3.5 (500-599): below cold small/medium (which enjoys enrollment
        # lookups) but above cold with unknown enrollment.
        return 500 + min(int(est_enrollment / 20), 99)
    elif strategy == "charter_cmo":
        # F6 Charter School CMO: multi-school network. One contract = many
        # schools. Highest per-deal leverage in the territory.
        # Tier 1.3 (780-899): below upward tier 1 (active customer expansion)
        # but above intra_district and cs_funding_recipient. Scale by school
        # count because more schools = bigger deal.
        school_count = kwargs.get("school_count", 0)
        base = 780 + min(school_count * 2, 99)
        return base
    elif strategy == "cte_center":
        # F7 CTE Center: regional career/technical center serving multiple
        # sending districts. Similar leverage to charter CMO — one adoption
        # pulls 5-50 sending district relationships with it.
        # Tier 1.4 (760-879): just below charter_cmo. Scale by sending
        # district count because more sending districts = broader reach.
        sending_districts = kwargs.get("sending_districts", 0)
        base = 760 + min(sending_districts * 3, 119)
        return base
    elif strategy == "private_school_network":
        # F8 Private School Network: diocesan system or multi-school chain.
        # Highest per-relationship leverage (one diocese = 100+ schools) but
        # longer sales cycles because private schools have distributed
        # purchasing and slower adoption cycles than districts.
        # Tier 1.5 (740-839): below cte_center, above intra_district.
        schools = kwargs.get("schools", 0)
        base = 740 + min(schools * 1, 99)
        return base
    elif strategy == "compliance_gap":
        # F9 CS Graduation Compliance Gap: district is legally obligated to
        # offer CS but doesn't yet. Forced-buyer pattern — the law is the
        # sales pitch. Highest urgency after cs_funding_recipient because
        # the timing is driven by state compliance deadlines.
        # Tier 1.1 (850-939): just below cs_funding_recipient (which has
        # actual money already allocated).
        return 850 + min(int(est_enrollment / 200), 89)
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


def _fetch_domain_page(domain: str) -> str:
    """Fetch a domain homepage and extract text content. Returns page text or empty string."""
    from bs4 import BeautifulSoup
    _HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScoutBot/2.0; K12 Education Research)"}
    for scheme in ["https", "http"]:
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True, verify=False) as http:
                resp = http.get(f"{scheme}://{domain}", headers=_HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    title = soup.title.string.strip() if soup.title and soup.title.string else ""
                    meta_desc = ""
                    meta_tag = soup.find("meta", attrs={"name": "description"})
                    if meta_tag:
                        meta_desc = meta_tag.get("content", "")[:200]
                    for tag in soup(["script", "style", "nav"]):
                        tag.decompose()
                    body_text = soup.get_text(separator=" ", strip=True)[:1500]
                    footer = soup.find("footer")
                    footer_text = footer.get_text(separator=" ", strip=True)[:300] if footer else ""
                    page_text = f"Title: {title}\nMeta: {meta_desc}\nBody: {body_text}"
                    if footer_text:
                        page_text += f"\nFooter: {footer_text}"
                    return page_text
        except Exception:
            continue
    return ""


def _scrape_resolve_locations(unknowns: list[dict], claude_batch_size: int = 25) -> dict:
    """
    Fetch school/district homepages in parallel and use Claude to extract
    state, district, and city. FREE — no search API needed.

    Fetches up to 20 domains concurrently via ThreadPoolExecutor.
    Deduplicates domains (multiple prospects from same district share one fetch).

    Returns dict keyed by email → {state, district, city}
    """
    import anthropic
    import json as _json
    from concurrent.futures import ThreadPoolExecutor, as_completed

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    _GENERIC_EMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
        "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
        "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
        "earthlink.net", "me.com", "live.com", "ymail.com",
    }

    # ── Step 1: Deduplicate domains and search in parallel via Serper ──
    domain_to_prospects = {}  # domain → list of unknowns
    generic_prospects = []
    for u in unknowns:
        email = u.get("email", "")
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if not domain or domain in _GENERIC_EMAIL_DOMAINS:
            generic_prospects.append(u)
        else:
            domain_to_prospects.setdefault(domain, []).append(u)

    unique_domains = list(domain_to_prospects.keys())
    logger.info(f"C4 resolve: {len(unique_domains)} unique domains to search "
                f"({len(unknowns)} prospects, {len(generic_prospects)} generic skipped)")

    # Parallel Serper searches — 20 concurrent
    serper_headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    domain_content = {}  # domain → search result text
    prospect_extra = {}  # email → additional per-prospect search results
    generic_content = {}  # company → search results for generic email prospects

    # Build domain → school name mapping for second search query
    domain_to_company = {}
    for domain, prospects_list in domain_to_prospects.items():
        for u in prospects_list:
            company = u.get("company", "")
            if company and company != "Unknown" and "@" not in company and len(company) > 3:
                domain_to_company[domain] = company
                break

    _serper_hdrs = dict(serper_headers)  # copy for thread safety

    def _serper_search(query):
        """Run a single Serper search. Returns snippet text."""
        try:
            with httpx.Client(timeout=10.0) as http:
                resp = http.post(SERPER_URL, headers=_serper_hdrs,
                                 json={"q": query, "num": 3})
                if resp.status_code != 200:
                    logger.warning(f"C4 Serper: HTTP {resp.status_code} for query: {query[:50]}")
                    return ""
                data = resp.json()
                parts = []
                for item in data.get("organic", [])[:3]:
                    parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                kg = data.get("knowledgeGraph", {})
                if kg:
                    attrs = kg.get("attributes", {})
                    addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                    parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.warning(f"C4 Serper search error for '{query[:50]}': {e}")
        return ""

    if SERPER_API_KEY:
        # Search strategy (like Steven does manually):
        # 1. Search "school name + full email" — most specific, finds exact person + school
        # 2. Search just the domain — catches district homepages
        # Deduplicate domains for search 2, but search 1 is per-prospect

        # Search 1: domain-level search (deduped — one per unique domain)
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_domain = {executor.submit(_serper_search, d): d for d in unique_domains}
            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    domain_content[domain] = future.result()
                except Exception:
                    domain_content[domain] = ""

        # Search 2: per-prospect "school name + email" search (more specific)
        # Only for institutional emails — adds results ON TOP of domain search
        prospect_extra = {}  # email → additional search results
        institutional_unknowns = [
            u for u in unknowns
            if "@" in u.get("email", "")
            and u.get("email", "").split("@")[-1].lower() not in _GENERIC_EMAIL_DOMAINS
            and u.get("company", "") and u["company"] != "Unknown" and "@" not in u["company"]
        ]
        if institutional_unknowns:
            def _search_with_email(u):
                return _serper_search(f"{u['company']} {u['email']}")

            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_email = {executor.submit(_search_with_email, u): u["email"] for u in institutional_unknowns}
                for future in as_completed(future_to_email):
                    email = future_to_email[future]
                    try:
                        prospect_extra[email] = future.result()
                    except Exception:
                        prospect_extra[email] = ""
    else:
        # Fallback: direct scraping if no Serper key
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_domain = {executor.submit(_fetch_domain_page, d): d for d in unique_domains}
            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    domain_content[domain] = future.result()
                except Exception:
                    domain_content[domain] = ""

    fetched_count = sum(1 for v in domain_content.values() if v)
    logger.info(f"C4 resolve: got results for {fetched_count} of {len(unique_domains)} domains")

    # ── Step 1b: Search generic-email prospects by school name ──
    if SERPER_API_KEY and generic_prospects:
        def _search_company(company):
            try:
                with httpx.Client(timeout=10.0) as http:
                    resp = http.post(SERPER_URL, headers=serper_headers,
                                     json={"q": f'"{company}" school', "num": 3})
                    if resp.status_code == 200:
                        data = resp.json()
                        parts = []
                        for item in data.get("organic", [])[:3]:
                            parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                        kg = data.get("knowledgeGraph", {})
                        if kg:
                            attrs = kg.get("attributes", {})
                            addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                            parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                        return "\n".join(parts) if parts else ""
            except Exception:
                pass
            return ""

        # Only search prospects with real school names (skip junk like "Unknown", email-as-name, etc.)
        searchable_generic = [
            u for u in generic_prospects
            if u.get("company", "") and u["company"] != "Unknown"
            and "@" not in u["company"] and len(u["company"]) > 3
        ]
        generic_content = {}  # company → search results
        if searchable_generic:
            logger.info(f"C4 resolve: searching {len(searchable_generic)} generic-email prospects by school name")
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_company = {executor.submit(_search_company, u["company"]): u["company"]
                                     for u in searchable_generic}
                for future in as_completed(future_to_company):
                    company = future_to_company[future]
                    try:
                        generic_content[company] = future.result()
                    except Exception:
                        generic_content[company] = ""

    # ── Step 2: Build context for all prospects ──
    # Combine domain search + per-prospect email search + generic company search
    page_context = []
    for u in unknowns:
        company = u.get("company", "")
        email = u.get("email", "")
        domain = email.split("@")[-1].lower() if "@" in email else ""
        parts = []
        # Domain search results
        if domain and domain_content.get(domain):
            parts.append(domain_content[domain])
        # Per-prospect "school name + email" search results (more specific)
        if email and prospect_extra.get(email):
            parts.append(prospect_extra[email])
        # For generic emails, use company name search results
        if not parts and company:
            gc = generic_content.get(company, "")
            if gc:
                parts.append(gc)
        content = "\n".join(parts)
        page_context.append({"company": company, "email": email, "content": content})

    results = {}  # email/company → {state, district, city}

    # ── Step 2b: Deterministic international detection from search results ──
    # Catch Canadian/international schools that have .org/.com domains
    # by checking search result content for UNAMBIGUOUS signals only.
    # IMPORTANT: avoid signals that match US places:
    #   "india" matches "Indiana", "ontario" matches "Ontario, CA",
    #   "england" matches "New England" — DO NOT use these.
    _INTL_SIGNALS_IN_CONTENT = [
        # Canadian domain patterns in URLs (unambiguous)
        ".bc.ca/", ".on.ca/", ".ab.ca/", ".qc.ca/", ".ns.ca/", ".nb.ca/",
        ".bc.ca ", ".on.ca ", ".ab.ca ", ".qc.ca ",
        # Canadian provinces (full, unambiguous)
        "british columbia", "salt spring island", "gulf islands",
        # Specific enough international signals
        "australia nsw", "australia vic", "new south wales",
        "united kingdom", "south africa",
        "são paulo", "sao paulo", "buenos aires",
        "méxico, d.f", "bogotá, colombia", "bogota, colombia",
    ]

    for pc in page_context:
        if not pc["content"]:
            continue
        content_lower = pc["content"].lower()
        for signal in _INTL_SIGNALS_IN_CONTENT:
            if signal in content_lower:
                entry = {"state": "__INTL__", "district": "", "city": ""}
                if pc["email"]:
                    results[pc["email"]] = entry
                if pc["company"]:
                    results[pc["company"]] = entry
                break

    # ── Step 3: Send to Claude in batches for extraction ──
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

    # Only send non-international records to Claude
    with_content = [pc for pc in page_context if pc["content"]]
    intl_flagged = [pc for pc in with_content
                    if results.get(pc["email"], {}).get("state") == "__INTL__"
                    or results.get(pc["company"], {}).get("state") == "__INTL__"]
    records_with_content = [pc for pc in with_content if pc not in intl_flagged]
    logger.info(f"C4 scrape: {len(page_context)} total, {len(with_content)} have content, "
                f"{len(intl_flagged)} flagged intl, {len(records_with_content)} to Claude")
    if not records_with_content:
        return results

    for batch_start in range(0, len(records_with_content), claude_batch_size):
        batch = records_with_content[batch_start:batch_start + claude_batch_size]

        records_text = ""
        for idx, pc in enumerate(batch, 1):
            domain = pc["email"].split("@")[-1] if "@" in pc["email"] else ""
            records_text += f"{idx}. Domain: {domain} | School: {pc['company']} | Email: {pc['email']}\n"
            records_text += f"   Search results:\n{pc['content'][:800]}\n\n"

        prompt = f"""I searched for these school/district email domains. Based on the results, determine the US state, city, and parent school district for each.

Look for:
- Address or location in search results or knowledge graph
- District name in page titles or URLs
- State abbreviations in URLs or snippets
- If the domain IS a school district (e.g., neisd.net = North East ISD), use that as the parent district

RECORDS:
{records_text}

Respond with ONLY a JSON array, no other text. Each element:
{{"idx": 1, "state": "TX", "district": "North East Independent School District", "city": "San Antonio"}}

Use "" for state only if the page gives NO location clue at all.
Always return a district — use the school name itself if no parent district is apparent.
"""
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
            )
            _track_claude_usage(response)
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            # Strip text preamble before JSON array
            if "[" in text:
                text = text[text.index("["):]
            if "]" in text:
                text = text[:text.rindex("]") + 1]

            parsed = _json.loads(text)
            for item in parsed:
                idx = item.get("idx", 0)
                if 1 <= idx <= len(batch):
                    pc = batch[idx - 1]
                    state = (item.get("state") or "").strip().upper()
                    district = (item.get("district") or "").strip()
                    entry = {
                        "state": state if state and len(state) == 2 else "",
                        "district": district,
                        "city": item.get("city", ""),
                    }
                    if entry["state"] or entry["district"]:
                        if pc["email"]:
                            results[pc["email"]] = entry
                        if pc["company"]:
                            results[pc["company"]] = entry

            resolved_count = len([i for i in parsed if (i.get("state") or "").strip()])
            logger.info(f"C4 scrape: resolved {resolved_count}/{len(batch)} "
                        f"(batch {batch_start // claude_batch_size + 1})")
        except Exception as e:
            logger.error(f"C4 scrape: Claude extraction failed: {e}")

    return results


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
                d["state"],          # State
                d["name"],           # Account Name
                "",                  # Email
                "",                  # First Name
                "",                  # Last Name
                "district",          # Deal Level
                "",                  # Parent District
                name_key,            # Name Key
                "cold",              # Strategy
                "web_search",        # Source
                "pending",           # Status
                str(priority),       # Priority
                now,                 # Date Added
                "",                  # Date Approved
                "",                  # Sequence Doc URL
                str(d.get("est_enrollment", "")),  # Est. Enrollment
                "",                  # School Count
                "",                  # Total Licenses
                territory_warning,   # Notes (always last)
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
            "districts": [r[1] for r in new_rows],
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
                dist.get("state", ""),     # State
                dist["display_name"],      # Account Name
                "",                        # Email
                "",                        # First Name
                "",                        # Last Name
                "district",                # Deal Level
                "",                        # Parent District
                name_key,                  # Name Key
                "upward",                  # Strategy
                "upward_auto",             # Source
                "pending",                 # Status
                str(priority),             # Priority
                now,                       # Date Added
                "",                        # Date Approved
                "",                        # Sequence Doc URL
                "",                        # Est. Enrollment
                str(school_count),         # School Count
                str(total_licenses),       # Total Licenses
                f"Schools: {', '.join(school_names)}",  # Notes (always last)
            ]
            new_rows.append(row)
            prospect_keys.add(name_key)

        if new_rows:
            _write_rows(new_rows)

        return {
            "success": True,
            "new_added": len(new_rows),
            "already_known": already_known,
            "districts": [r[1] for r in new_rows],
            "error": "",
        }

    except Exception as e:
        logger.error(f"suggest_upward_targets error: {e}")
        return {
            "success": False, "new_added": 0, "already_known": 0,
            "districts": [], "error": str(e),
        }


def _is_recent_activity(date_str: str, days: int = 180) -> bool:
    """
    Returns True if a Salesforce date string is within the last N days.
    Empty/unparseable dates → False (treat as inactive).
    """
    if not date_str or not date_str.strip():
        return False
    try:
        from dateutil import parser as date_parser
        activity_dt = date_parser.parse(date_str.strip())
        if activity_dt.tzinfo is None:
            from datetime import timezone
            activity_dt = activity_dt.replace(tzinfo=timezone.utc)
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return activity_dt >= cutoff
    except Exception:
        return False


def suggest_intra_district_expansion(max_per_district: int = 5) -> dict:
    """
    F1 Second Buyer Expansion: queue sibling schools within districts where
    CodeCombat already has at least one healthy school account.

    Logic:
      1. Load Active Accounts. Build coverage maps:
         - district_account_keys: districts that ARE accounts (skip — already covered)
         - covered_school_keys_by_district: schools already on CodeCombat per district
         - district_health: parent district -> bool (any healthy school account)
      2. For each parent district with >=1 school account:
         a. Skip if district itself is an Active Account (full coverage already)
         b. Skip if all school accounts in that district are dead (>180d inactive)
         c. Load Territory Schools for that state, filter to this district
         d. Exclude already-covered schools and already-queued schools
         e. Sort by enrollment desc, take top max_per_district
         f. Append rows with strategy=intra_district, source=expansion_auto

    Returns: {success, eligible_districts, queued, skipped_district_covered,
              skipped_dead, skipped_already_queued, error}
    """
    try:
        accounts = csv_importer.get_active_accounts()
        if not accounts:
            return {
                "success": True, "eligible_districts": 0, "queued": 0,
                "skipped_district_covered": 0, "skipped_dead": 0,
                "skipped_already_queued": 0, "districts": [], "error": "",
            }

        # Build coverage maps from active accounts
        district_account_keys: set[str] = set()
        covered_school_keys_by_district: dict[str, set[str]] = {}

        for acct in accounts:
            atype = acct.get("Account Type", "").lower()
            display_name = (
                acct.get("Active Account Name", "")
                or acct.get("Display Name", "")
            )
            if not display_name:
                continue

            if atype == "district":
                district_account_keys.add(csv_importer.normalize_name(display_name))
                continue

            if atype == "school":
                parent = acct.get("Parent Account", "").strip()
                if not parent:
                    continue
                school_key = csv_importer.normalize_name(display_name).lower()
                covered_school_keys_by_district.setdefault(parent, set()).add(school_key)

        # Load existing queue for dedup
        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects}

        # Use existing helper to enumerate districts with at least one school account
        districts_with_schools = csv_importer.get_districts_with_schools()

        new_rows = []
        eligible_count = 0
        skipped_district_covered = 0
        skipped_dead = 0
        skipped_already_queued = 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        for dist in districts_with_schools:
            parent_display = dist["display_name"]
            parent_key = dist["name_key"]
            state = dist.get("state", "")

            # Defense in depth — get_districts_with_schools already filters
            # district-level deals, but check anyway
            if parent_key in district_account_keys:
                skipped_district_covered += 1
                continue

            eligible_count += 1

            # Load territory schools for this state and filter to this district
            try:
                territory_schools = territory_data._load_territory_schools(state)
            except Exception as e:
                logger.warning(f"intra_district: territory load failed for {state}: {e}")
                continue

            if not territory_schools:
                continue

            parent_key_norm = parent_key.lower() if parent_key else ""
            sibling_schools = []
            for ts in territory_schools:
                ts_district = ts.get("District Name", "").strip()
                if not ts_district:
                    continue
                ts_district_key = csv_importer.normalize_name(ts_district).lower()
                if ts_district_key == parent_key_norm:
                    sibling_schools.append(ts)

            # Fuzzy fallback if exact match returns nothing
            if not sibling_schools and parent_key_norm:
                ts_keys = {
                    csv_importer.normalize_name(t.get("District Name", "")).lower(): t
                    for t in territory_schools
                    if t.get("District Name", "").strip()
                }
                fuzzy_key = csv_importer.fuzzy_match_name(
                    parent_key_norm, ts_keys, threshold=0.7
                )
                if fuzzy_key:
                    # Pull every territory school whose normalized district key matches
                    fuzzy_district_name = ts_keys[fuzzy_key].get("District Name", "")
                    sibling_schools = [
                        t for t in territory_schools
                        if csv_importer.normalize_name(
                            t.get("District Name", "")
                        ).lower() == fuzzy_key
                    ]

            if not sibling_schools:
                continue

            covered_keys_here = covered_school_keys_by_district.get(parent_display, set())

            # Filter out covered + already-queued, sort by enrollment desc
            candidates = []
            for ts in sibling_schools:
                school_name = ts.get("School Name", "").strip()
                if not school_name:
                    continue
                school_key = csv_importer.normalize_name(school_name).lower()
                if school_key in covered_keys_here:
                    continue
                if school_key in prospect_keys:
                    skipped_already_queued += 1
                    continue
                try:
                    enrollment = int(ts.get("Enrollment", 0) or 0)
                except (ValueError, TypeError):
                    enrollment = 0
                candidates.append({
                    "name": school_name,
                    "key": school_key,
                    "state": ts.get("State", state),
                    "enrollment": enrollment,
                })

            candidates.sort(key=lambda c: c["enrollment"], reverse=True)
            candidates = candidates[:max_per_district]

            # Pick a representative covered school for the note
            covered_sample = ""
            for s in dist.get("schools", []):
                covered_sample = s.get("display_name", "")
                if covered_sample:
                    break

            for cand in candidates:
                priority = _calculate_priority(
                    "intra_district", 0, 0, cand["enrollment"]
                )
                note = (
                    f"Sibling-school expansion. Parent district: {parent_display}. "
                    f"District has {dist['school_count']} active CodeCombat school(s)"
                    + (f" (e.g., {covered_sample})." if covered_sample else ".")
                )
                row = [
                    cand["state"],          # State
                    cand["name"],           # Account Name
                    "",                     # Email
                    "",                     # First Name
                    "",                     # Last Name
                    "school",               # Deal Level
                    parent_display,         # Parent District
                    cand["key"],            # Name Key
                    "intra_district",       # Strategy
                    "expansion_auto",       # Source
                    "pending",              # Status
                    str(priority),          # Priority
                    now,                    # Date Added
                    "",                     # Date Approved
                    "",                     # Sequence Doc URL
                    str(cand["enrollment"]),# Est. Enrollment
                    "",                     # School Count
                    "",                     # Total Licenses
                    "",                     # Signal ID
                    note,                   # Notes (always last)
                ]
                new_rows.append(row)
                prospect_keys.add(cand["key"])

        if new_rows:
            _write_rows(new_rows)

        logger.info(
            f"suggest_intra_district_expansion: {eligible_count} districts eligible, "
            f"{len(new_rows)} schools queued, "
            f"{skipped_district_covered} skipped (district covered), "
            f"{skipped_already_queued} skipped (already queued)"
        )

        return {
            "success": True,
            "eligible_districts": eligible_count,
            "queued": len(new_rows),
            "skipped_district_covered": skipped_district_covered,
            "skipped_dead": 0,  # filter removed in v1
            "skipped_already_queued": skipped_already_queued,
            "districts": list({r[6] for r in new_rows}),  # unique parent districts
            "error": "",
        }

    except Exception as e:
        logger.error(f"suggest_intra_district_expansion error: {e}")
        return {
            "success": False, "eligible_districts": 0, "queued": 0,
            "skipped_district_covered": 0, "skipped_dead": 0,
            "skipped_already_queued": 0, "districts": [], "error": str(e),
        }


def suggest_closed_lost_targets(buffer_months: int = 6, lookback_months: int = 18) -> dict:
    """
    Pull closed-lost opps from Closed Lost tab (within date window).
    Group by district (Account Name / Parent Account), dedup against
    Active Accounts and existing queue, add to queue with strategy="winback".

    Window: opps closed between (today - buffer - lookback) and (today - buffer).
    Default: 6-month buffer, 18-month lookback → ~24 months ago to ~6 months ago.
    Set lookback_months=0 to include all history (no oldest cutoff).

    Returns:
      {success, new_added, already_known, already_active, districts, error}
    """
    try:
        closed_lost = pipeline_tracker.get_closed_lost_opps(buffer_months, lookback_months)
        if not closed_lost:
            return {
                "success": True, "new_added": 0, "already_known": 0,
                "already_active": 0, "districts": [],
                "error": "No closed-lost opps found in the date window. Upload a closed-lost CSV first (`/import_closed_lost`).",
            }

        # Build territory school→district lookup for enriching parent district info
        # Used to fill in missing Parent Account data from NCES (Salesforce data is often wrong)
        try:
            territory_schools = territory_data._load_territory_schools()
            territory_school_to_district = {}
            for ts in territory_schools:
                s_key = ts.get("Name Key", "").strip().lower()
                d_name = ts.get("District Name", "").strip()
                if s_key and d_name:
                    territory_school_to_district[s_key] = d_name
            logger.info(f"Winback: loaded {len(territory_school_to_district)} territory school→district mappings")
        except Exception as e:
            logger.warning(f"Winback: could not load territory schools for cross-check: {e}")
            territory_school_to_district = {}

        # Group by Account Name (the actual deal target), NOT by Parent Account.
        # School-level deals stay as school-level targets. District-level deals stay as district targets.
        # Parent Account is stored as context, not used for grouping.
        account_opps: dict[str, list[dict]] = {}
        territory_resolved = 0
        territory_fuzzy_resolved = 0
        for opp in closed_lost:
            account = opp.get("Account Name", "").strip()
            if not account:
                continue

            # Enrich: if no Parent Account, try to find it via territory data
            parent = opp.get("Parent Account", "").strip()
            if not parent and territory_school_to_district:
                acct_key = csv_importer.normalize_name(account).lower()
                matched_district = territory_school_to_district.get(acct_key)
                if not matched_district:
                    fuzzy_key = csv_importer.fuzzy_match_name(
                        acct_key, territory_school_to_district, threshold=0.7
                    )
                    if fuzzy_key:
                        matched_district = territory_school_to_district[fuzzy_key]
                        territory_fuzzy_resolved += 1
                if matched_district:
                    opp["_resolved_parent"] = matched_district
                    territory_resolved += 1

            account_opps.setdefault(account, []).append(opp)

        if territory_resolved:
            logger.info(
                f"Winback: resolved {territory_resolved} school opps → parent district "
                f"via territory data ({territory_fuzzy_resolved} via fuzzy match)"
            )

        # Load existing data for dedup
        active_accounts = csv_importer.get_active_accounts()
        active_keys = {
            csv_importer.normalize_name(
                a.get("Active Account Name", "") or a.get("Display Name", "")
            )
            for a in active_accounts
        }

        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects}

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_rows = []
        already_known = 0
        already_active = 0

        for account_name, opps in account_opps.items():
            name_key = csv_importer.normalize_name(account_name)
            if not name_key or len(name_key) < 3:
                continue

            if name_key in active_keys:
                already_active += 1
                continue

            if name_key in prospect_keys:
                already_known += 1
                continue

            # Determine deal level: school-level vs district-level
            # If any opp has a Parent Account (or territory-resolved parent), it's a school under a district
            parent_districts = set()
            for opp in opps:
                p = opp.get("Parent Account", "").strip()
                if p:
                    parent_districts.add(p)
                rp = opp.get("_resolved_parent", "")
                if rp:
                    parent_districts.add(rp)

            is_school_deal = len(parent_districts) > 0
            parent_info = ", ".join(sorted(parent_districts)) if parent_districts else ""

            # Summarize the closed-lost opps for this account
            total_amount = 0.0
            opp_names = []
            latest_close = ""
            state = ""
            lost_reasons = set()
            contact_emails = set()
            for opp in opps:
                amt_str = opp.get("Amount", "")
                if amt_str:
                    try:
                        total_amount += float(str(amt_str).replace("$", "").replace(",", ""))
                    except ValueError:
                        pass
                opp_names.append(opp.get("Opportunity Name", "?"))
                if not state:
                    state = opp.get("State", "")
                close_str = opp.get("Close Date", "")
                if close_str and (not latest_close or close_str > latest_close):
                    latest_close = close_str
                lr = opp.get("Lost Reason", "").strip()
                if lr:
                    lost_reasons.add(lr)
                ce = opp.get("Contact Email", "").strip()
                if ce:
                    contact_emails.add(ce)

            priority = _calculate_priority(
                "winback", 0, 0, 0, amount=total_amount
            )

            deal_level = "school" if is_school_deal else "district"

            # Build notes — deal level is now a separate column, no need to repeat in notes
            notes_parts = []
            if len(opps) > 1:
                notes_parts.append(f"{len(opps)} closed-lost opps")
            if total_amount > 0:
                notes_parts.append(f"${total_amount:,.0f} total value")
            if latest_close:
                notes_parts.append(f"last closed {latest_close}")
            if lost_reasons:
                notes_parts.append(f"Lost: {', '.join(sorted(lost_reasons))}")
            if contact_emails:
                notes_parts.append(f"Contacts: {', '.join(sorted(contact_emails)[:3])}")
            if opp_names:
                notes_parts.append(f"Opps: {', '.join(opp_names[:3])}")

            row = [
                state,               # State
                account_name,        # Account Name (school name or district name — the actual deal)
                "",                  # Email
                "",                  # First Name
                "",                  # Last Name
                deal_level,          # Deal Level — "school" or "district"
                parent_info,         # Parent District — for school deals, the district name
                name_key,            # Name Key
                "winback",           # Strategy
                "pipeline_closed",   # Source
                "pending",           # Status
                str(priority),       # Priority
                now,                 # Date Added
                "",                  # Date Approved
                "",                  # Sequence Doc URL
                "",                  # Est. Enrollment
                "",                  # School Count
                "",                  # Total Licenses
                " | ".join(notes_parts),  # Notes (always last)
            ]
            new_rows.append(row)
            prospect_keys.add(name_key)  # prevent within-batch dupes

        if new_rows:
            _write_rows(new_rows)

        # Deal Level is column index 5 (after State, Account Name, Email, First Name, Last Name)
        school_deal_count = sum(1 for r in new_rows if r[5] == "school")
        district_deal_count = sum(1 for r in new_rows if r[5] == "district")
        return {
            "success": True,
            "new_added": len(new_rows),
            "already_known": already_known,
            "already_active": already_active,
            "territory_resolved": territory_resolved,
            "school_deals": school_deal_count,
            "district_deals": district_deal_count,
            "districts": [r[1] for r in new_rows],
            "error": "",
        }

    except Exception as e:
        logger.error(f"suggest_closed_lost_targets error: {e}")
        return {
            "success": False, "new_added": 0, "already_known": 0,
            "already_active": 0, "districts": [], "error": str(e),
        }


def suggest_cold_license_requests(sequence_ids: list[int] = None, progress_callback=None) -> dict:
    """
    C4: Scan Outreach license request sequences for cold prospects.
    A prospect is "cold" if: no Salesforce opp exists AND no pricing was sent.

    Pricing detection: PandaDoc link in email body (pandadoc.com/d/).

    Returns:
      {success, new_added, already_known, already_active, pricing_sent,
       has_opp, total_scanned, prospects, error}
    """
    import tools.outreach_client as outreach_client

    _reset_cost_tracker()

    if not outreach_client.is_authenticated():
        return {"success": False, "new_added": 0, "error": "Outreach not connected. Use /connect_outreach."}

    # Default to Steven's 3 US license request sequences
    if sequence_ids is None:
        sequence_ids = [507, 1768, 1860]

    try:
        # ── Step 1: Pull all prospects from the target sequences ──
        all_prospects = {}  # prospect_id → {prospect_data, engagement, sequences}
        total_states = 0

        for seq_id in sequence_ids:
            if progress_callback:
                progress_callback(f"Scanning sequence {seq_id}...")
            logger.info(f"C4: scanning sequence {seq_id}")

            states = outreach_client.get_sequence_states(seq_id, include_prospect=True)
            total_states += len(states)

            for state in states:
                pid = state.get("prospect_id")
                if not pid:
                    continue

                prospect_info = state.get("prospect", {})
                if not prospect_info:
                    continue

                if pid not in all_prospects:
                    all_prospects[pid] = {
                        "prospect": prospect_info,
                        "reply_count": 0,
                        "deliver_count": 0,
                        "open_count": 0,
                        "sequences": [],
                    }
                # Aggregate engagement across sequences
                all_prospects[pid]["reply_count"] += state.get("reply_count", 0)
                all_prospects[pid]["deliver_count"] += state.get("deliver_count", 0)
                all_prospects[pid]["open_count"] += state.get("open_count", 0)
                all_prospects[pid]["sequences"].append(seq_id)

        logger.info(f"C4: found {len(all_prospects)} unique prospects across {total_states} sequence states")

        # ── Step 1b: Bulk pricing detection — scan all mailings at once ──
        logger.info("C4: bulk scanning mailings for pricing signals...")
        pricing_prospect_ids = outreach_client.get_pricing_prospect_ids(sequence_ids)
        logger.info(f"C4: {len(pricing_prospect_ids)} prospects had pricing sent (bulk scan)")

        # ── Step 2: Build opp lookup from Pipeline + Closed Lost ──
        # If an opp exists for this company/account, it's not C4
        opp_account_keys = set()
        try:
            open_opps = pipeline_tracker.get_open_opps()
            for opp in open_opps:
                acct = opp.get("Account Name", "").strip()
                parent = opp.get("Parent Account", "").strip()
                if acct:
                    opp_account_keys.add(csv_importer.normalize_name(acct))
                if parent:
                    opp_account_keys.add(csv_importer.normalize_name(parent))
        except Exception:
            pass

        try:
            closed_lost = pipeline_tracker.get_closed_lost_opps(buffer_months=0, lookback_months=0)
            for opp in closed_lost:
                acct = opp.get("Account Name", "").strip()
                parent = opp.get("Parent Account", "").strip()
                if acct:
                    opp_account_keys.add(csv_importer.normalize_name(acct))
                if parent:
                    opp_account_keys.add(csv_importer.normalize_name(parent))
        except Exception:
            pass

        logger.info(f"C4: {len(opp_account_keys)} account keys with existing opps")

        # ── Step 3: Load Active Accounts + existing queue for dedup ──
        active_accounts = csv_importer.get_active_accounts()
        active_keys = {
            csv_importer.normalize_name(
                a.get("Active Account Name", "") or a.get("Display Name", "")
            )
            for a in active_accounts
        }

        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects}

        # ── Step 3b: Load territory matcher for name resolution + filtering ──
        import tools.territory_matcher as territory_matcher
        try:
            territory_matcher.ensure_cache(force_reload=True)
            logger.info(f"C4: territory matcher cache loaded — {territory_matcher.get_cache_stats()}")
        except Exception as e:
            logger.warning(f"C4: could not load territory matcher: {e}")

        # Build domain→state lookup from real SF Leads/Contacts emails
        try:
            sf_lookup = territory_matcher.build_domain_state_lookup(force_reload=True)
            logger.info(f"C4: SF domain→state lookup built — {len(sf_lookup)} domain roots")
        except Exception as e:
            logger.warning(f"C4: could not build SF domain lookup: {e}")

        # Steven's territory states
        territory_states = {
            "IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE", "TX", "CA",
        }

        # Known international email TLDs to exclude
        intl_tlds = {
            ".ca", ".uk", ".au", ".nz", ".in", ".za", ".ng", ".ke", ".gh",
            ".ph", ".sg", ".my", ".hk", ".jp", ".kr", ".tw", ".br", ".mx",
            ".co", ".cl", ".ar", ".de", ".fr", ".es", ".it", ".nl", ".se",
            ".no", ".dk", ".fi", ".ie", ".be", ".at", ".ch", ".pt", ".pl",
            ".cz", ".hu", ".ro", ".bg", ".hr", ".rs", ".ae", ".sa", ".qa",
            ".eg", ".pk", ".bd", ".lk", ".th", ".vn", ".id",
            ".pa", ".gt", ".sv", ".hn", ".ni", ".cr", ".bo", ".py", ".uy",
            ".pe", ".ec", ".ve", ".do", ".cu", ".tt", ".jm",
            ".name",
        }
        # International domain patterns (edu.XX = foreign education system)
        intl_domain_patterns = (
            ".edu.pa", ".edu.mx", ".edu.br", ".edu.ar", ".edu.co", ".edu.pe",
            ".edu.cl", ".edu.au", ".edu.uk", ".edu.sg", ".edu.hk", ".edu.ph",
            ".edu.my", ".edu.in", ".edu.pk", ".edu.ng", ".edu.za",
            ".ac.uk", ".ac.nz", ".ac.jp", ".ac.kr", ".ac.in", ".ac.za",
            ".gc.ca", ".on.ca", ".bc.ca", ".ab.ca", ".qc.ca",
        )
        # International keywords in company names (deterministic, not Claude-dependent)
        intl_company_keywords = (
            "école", "ecole", "lycée", "lycee", "colegio", "liceo", "escuela",
            "instituto", "técnica", "tecnica", "buen pastor", "scolaire",
            "collège", "komisyon", "schule", "grundschule",
            "gymnasium", "scuola", "escola",
        )

        # ── Step 4: First pass — quick filters + territory matching + pricing ──
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_rows = []
        already_known = 0
        already_active = 0
        pricing_sent_count = 0
        has_opp_count = 0
        out_of_territory = 0
        international_count = 0
        student_email_count = 0
        claude_inferred_count = 0
        audit_pricing_sent = []
        audit_has_opp = []
        audit_active = []
        audit_no_company = 0
        audit_out_of_territory = []
        audit_international = []
        audit_student_emails = []

        # Collect candidates that pass quick filters but need location resolution
        candidates = []  # list of (pid, pdata, company, company_key, email_str, full_name, title, territory_match)

        for pid, pdata in all_prospects.items():
            prospect = pdata["prospect"]
            company = (prospect.get("company") or "").strip()
            first_name = (prospect.get("first_name") or "")
            last_name = (prospect.get("last_name") or "")
            emails = prospect.get("emails") or []
            title = (prospect.get("title") or "")
            full_name = f"{first_name} {last_name}".strip()

            if not company:
                audit_no_company += 1
                continue
            company_key = csv_importer.normalize_name(company)
            if not company_key or len(company_key) < 3:
                audit_no_company += 1
                continue
            email_str = emails[0] if emails else ""

            # Quick filter 0: Student email? ("student" anywhere in domain)
            if email_str:
                try:
                    if territory_matcher.is_student_email(email_str):
                        student_email_count += 1
                        audit_student_emails.append([company, full_name, email_str, title, "Student email"])
                        continue
                except Exception:
                    # Fallback: simple check
                    domain_lower = email_str.lower().split("@")[-1] if "@" in email_str else ""
                    if "student" in domain_lower:
                        student_email_count += 1
                        audit_student_emails.append([company, full_name, email_str, title, "Student email"])
                        continue

            # Quick filter 1: Already an active customer?
            if company_key in active_keys:
                already_active += 1
                audit_active.append([company, full_name, email_str, title, "Active Customer"])
                continue
            # Quick filter 2: Already in Prospecting Queue?
            if company_key in prospect_keys:
                already_known += 1
                continue
            # Quick filter 3: Does an opp exist?
            if company_key in opp_account_keys:
                has_opp_count += 1
                audit_has_opp.append([company, full_name, email_str, title, "Has Opp"])
                continue
            # Quick filter 4: International email/company?
            is_intl = False
            intl_reason = ""
            if email_str:
                email_lower = email_str.lower()
                domain = email_lower.split("@")[-1] if "@" in email_lower else ""
                # Check country-code TLDs
                for tld in intl_tlds:
                    if domain.endswith(tld):
                        is_intl = True
                        intl_reason = f"International TLD ({domain})"
                        break
                # Check foreign education domain patterns (edu.pa, ac.uk, etc.)
                if not is_intl:
                    for pattern in intl_domain_patterns:
                        if domain.endswith(pattern):
                            is_intl = True
                            intl_reason = f"International edu domain ({domain})"
                            break
            # Check company name for non-US school keywords
            if not is_intl and company:
                company_lower = company.lower()
                for kw in intl_company_keywords:
                    if kw in company_lower:
                        is_intl = True
                        intl_reason = f"International name ({kw} in '{company}')"
                        break
            if is_intl:
                international_count += 1
                audit_international.append([company, full_name, email_str, title, intl_reason])
                continue

            # Quick filter 5: Extract state from email domain
            # Priority: k12/gov domain → SF data lookup → territory matching
            # NOTE: NCES city lookup NOT used here — our NCES data only covers 13 states,
            # so "unique" city matches are false positives (e.g., "charlottesville" maps to
            # IN because VA isn't in our data). Will revisit when we have full US coverage.
            email_state = ""
            if email_str:
                try:
                    # First try k12/gov/suffix/city patterns
                    email_state = territory_matcher.extract_state_from_email(email_str)
                    # If that didn't work, try SF data-driven lookup
                    if not email_state:
                        email_state = territory_matcher.lookup_domain_state(email_str)
                except Exception:
                    email_state = ""
            if email_state and email_state not in territory_states:
                out_of_territory += 1
                audit_out_of_territory.append([
                    company, full_name, email_str, title,
                    f"State: {email_state} (k12 email domain)"
                ])
                continue

            # Territory matching (email_priority=True: email domain ranks above company name)
            # Pass the k12-extracted state to constrain matching
            territory_match = territory_matcher.match_record(
                company, email=email_str, email_priority=True,
                state=email_state,  # constrain to k12 state if available
            )
            if territory_match and territory_match.state not in territory_states:
                out_of_territory += 1
                audit_out_of_territory.append([
                    company, full_name, email_str, title,
                    f"State: {territory_match.state} ({territory_match.match_method})"
                ])
                continue

            # If k12 domain gave us a state but territory matcher didn't find a match,
            # still use that state (it's reliable)
            if email_state and not territory_match:
                # Create a lightweight result — we know the state from the email
                from tools.territory_matcher import MatchResult as _MR
                territory_match = _MR(
                    canonical_name=company,
                    name_key=company_key,
                    entity_type="school",
                    parent_district="",
                    state=email_state,
                    city="",
                    enrollment=0,
                    nces_id="",
                    confidence="high",
                    match_method="k12_email_state",
                )

            candidates.append((pid, pdata, company, company_key, email_str, full_name, title, territory_match))

        logger.info(f"C4: {len(candidates)} candidates after quick filters + territory matching")

        # ── Step 4b: Claude inference for unresolved candidates ──
        # Collect prospects with no territory match for Claude batch inference
        unresolved = []
        unresolved_indices = []  # track which candidates need Claude results
        for i, (pid, pdata, company, company_key, email_str, full_name, title, territory_match) in enumerate(candidates):
            if not territory_match:
                unresolved.append({
                    "company": company,
                    "email": email_str,
                    "name": full_name,
                    "title": title,
                })
                unresolved_indices.append(i)

        claude_results = {}
        if unresolved:
            logger.info(f"C4: running Claude inference on {len(unresolved)} unresolved prospects")
            try:
                claude_results = territory_matcher.infer_locations_with_claude(
                    unresolved, usage_callback=_track_claude_usage
                )
                claude_inferred_count = len(claude_results)
                logger.info(f"C4: Claude inferred {claude_inferred_count} locations")
            except Exception as e:
                logger.error(f"C4: Claude inference failed: {e}")

        # Apply Claude results — filter out non-territory and international
        filtered_candidates = []
        for i, (pid, pdata, company, company_key, email_str, full_name, title, territory_match) in enumerate(candidates):
            if territory_match:
                # Already resolved — keep
                filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                            territory_match.state, territory_match.parent_district,
                                            territory_match.canonical_name, territory_match.entity_type))
            else:
                # Check Claude results
                claude_info = claude_results.get(company, {})
                if claude_info:
                    if not claude_info.get("is_us", True):
                        international_count += 1
                        audit_international.append([company, full_name, email_str, title, "International (Claude)"])
                        continue
                    c_state = claude_info.get("state", "")
                    if c_state and c_state not in territory_states:
                        out_of_territory += 1
                        audit_out_of_territory.append([
                            company, full_name, email_str, title,
                            f"State: {c_state} (Claude inferred)"
                        ])
                        continue
                    # CA check — if Claude says CA, check SoCal via domain match OR known SoCal domains OR company name
                    if c_state == "CA":
                        is_socal = False
                        # Check 1: email domain matches SoCal territory district
                        email_domain_match = territory_matcher._match_by_email_domain(
                            email_str, csv_importer.normalize_name(company).lower(), "CA"
                        ) if email_str else None
                        if email_domain_match:
                            is_socal = True
                            filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                        "CA", email_domain_match.parent_district or email_domain_match.canonical_name,
                                                        email_domain_match.canonical_name, email_domain_match.entity_type))
                        # Check 2: known SoCal domain abbreviation
                        if not is_socal and email_str:
                            try:
                                if territory_matcher.is_socal_domain(email_str):
                                    is_socal = True
                                    filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                                "CA", claude_info.get("district", ""),
                                                                company, claude_info.get("entity_type", "school")))
                            except Exception:
                                pass
                        # Check 3: company name or Claude city/district contains SoCal signals
                        if not is_socal:
                            try:
                                if territory_matcher.is_socal_by_name(
                                    company,
                                    city=claude_info.get("city", ""),
                                    district=claude_info.get("district", ""),
                                ):
                                    is_socal = True
                                    filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                                "CA", claude_info.get("district", ""),
                                                                company, claude_info.get("entity_type", "school")))
                            except Exception:
                                pass
                        if is_socal:
                            continue
                        # No SoCal match — likely NorCal, exclude
                        out_of_territory += 1
                        audit_out_of_territory.append([
                            company, full_name, email_str, title,
                            "CA - not in SoCal territory (Claude: CA)"
                        ])
                        continue
                    filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                c_state, claude_info.get("district", ""),
                                                company, claude_info.get("entity_type", "school")))
                else:
                    # No Claude result — try email state extraction + SF lookup as last resort
                    last_resort_state = ""
                    try:
                        if email_str:
                            last_resort_state = territory_matcher.extract_state_from_email(email_str)
                        if not last_resort_state and email_str:
                            last_resort_state = territory_matcher.lookup_domain_state(email_str)
                    except Exception:
                        pass
                    if last_resort_state:
                        if last_resort_state not in territory_states:
                            out_of_territory += 1
                            audit_out_of_territory.append([
                                company, full_name, email_str, title,
                                f"State: {last_resort_state} (email extraction, no Claude result)"
                            ])
                            continue
                        filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                    last_resort_state, "", company, "school"))
                    else:
                        # Unknown state — keep in queue for review (don't exclude yet)
                        filtered_candidates.append((pid, pdata, company, company_key, email_str, full_name, title,
                                                    "", "", company, "school"))

        logger.info(f"C4: {len(filtered_candidates)} candidates after Claude inference filtering")

        # ── Step 4c: Serper web search for unknowns (state OR district) ──
        # Search web for prospects that are missing state OR missing parent district.
        # One search per prospect resolves both — cuts API calls vs separate passes.
        still_unknown = []
        still_unknown_indices = []
        still_unknown_needs = []  # track what each needs: "state", "district", or "both"
        for i, fc in enumerate(filtered_candidates):
            resolved_state = fc[7]
            resolved_district = fc[8]
            if not resolved_state:
                still_unknown.append({"company": fc[2], "email": fc[4]})
                still_unknown_indices.append(i)
                still_unknown_needs.append("state")
            elif not resolved_district:
                still_unknown.append({"company": fc[2], "email": fc[4]})
                still_unknown_indices.append(i)
                still_unknown_needs.append("district")

        if still_unknown and SERPER_API_KEY:
            logger.info(f"C4: running Serper web search for {len(still_unknown)} still-unknown prospects")
            if progress_callback:
                progress_callback(f"Fetching {len(still_unknown)} school websites for location data...")
            try:
                serper_results = _scrape_resolve_locations(still_unknown)
                logger.info(f"C4: scrape returned {len(serper_results)} results for {len(still_unknown)} unknowns")
                serper_resolved = 0
                serper_districts = 0
                for idx, u, need in zip(still_unknown_indices, still_unknown, still_unknown_needs):
                    # Look up by email first (unique), then company name
                    search_result = serper_results.get(u["email"]) or serper_results.get(u["company"])
                    if not search_result:
                        continue

                    # Check for international marker from deterministic detection
                    if search_result.get("state") == "__INTL__":
                        fc = filtered_candidates[idx]
                        international_count += 1
                        audit_international.append([
                            fc[2], fc[5], fc[4], "",
                            "International (web search content)"
                        ])
                        filtered_candidates[idx] = (*fc[:7], "__OOT__", *fc[8:])
                        continue

                    fc = filtered_candidates[idx]

                    # District-only lookup: already has state, just needs district
                    if need == "district":
                        s_district = search_result.get("district", "")
                        if s_district:
                            filtered_candidates[idx] = (*fc[:8], s_district, fc[9], fc[10])
                            serper_districts += 1
                        continue

                    # State lookup (need == "state")
                    s_state = search_result.get("state", "")
                    if not s_state:
                        continue
                    if s_state not in territory_states:
                        out_of_territory += 1
                        audit_out_of_territory.append([
                            fc[2], fc[5], fc[4], "",
                            f"State: {s_state} (Serper web search)"
                        ])
                        # Mark for removal by setting state to a sentinel
                        filtered_candidates[idx] = (*fc[:7], "__OOT__", *fc[8:])
                    else:
                        # CA SoCal check
                        if s_state == "CA":
                            is_socal = False
                            try:
                                if fc[4] and territory_matcher.is_socal_domain(fc[4]):
                                    is_socal = True
                                if not is_socal and territory_matcher.is_socal_by_name(
                                    fc[2], city=search_result.get("city", ""),
                                    district=search_result.get("district", "")
                                ):
                                    is_socal = True
                            except Exception:
                                pass
                            if not is_socal:
                                out_of_territory += 1
                                audit_out_of_territory.append([
                                    fc[2], fc[5], fc[4], "",
                                    "CA - not in SoCal territory (Serper)"
                                ])
                                filtered_candidates[idx] = (*fc[:7], "__OOT__", *fc[8:])
                                continue
                        filtered_candidates[idx] = (*fc[:7], s_state, search_result.get("district", fc[8]),
                                                    fc[9], fc[10])
                        serper_resolved += 1

                # Remove OOT-marked candidates
                filtered_candidates = [fc for fc in filtered_candidates if fc[7] != "__OOT__"]
                logger.info(f"C4: scrape resolved {serper_resolved} states + {serper_districts} districts")
            except Exception as e:
                import traceback
                logger.error(f"C4: scrape location resolution failed: {e}\n{traceback.format_exc()}")

        # ── Step 4d: Enrich parent districts for prospects with state but no district ──
        # Now that states are resolved (via Claude, Serper, patterns), re-run territory
        # matching WITH the known state to find parent districts. Also use Claude's
        # district field and Serper results where available.
        enriched_district_count = 0
        for i, fc in enumerate(filtered_candidates):
            resolved_state = fc[7]
            resolved_district = fc[8]
            if resolved_state and not resolved_district:
                company_fc = fc[2]
                email_fc = fc[4]
                # Try territory matching with the now-known state
                try:
                    match = territory_matcher.match_record(
                        company_fc, email=email_fc, state=resolved_state, email_priority=True
                    )
                    if match and match.parent_district:
                        filtered_candidates[i] = (*fc[:8], match.parent_district, match.canonical_name, match.entity_type)
                        enriched_district_count += 1
                    elif match and match.entity_type == "district":
                        filtered_candidates[i] = (*fc[:8], match.canonical_name, match.canonical_name, "district")
                        enriched_district_count += 1
                except Exception:
                    pass
        if enriched_district_count:
            logger.info(f"C4: enriched {enriched_district_count} parent districts via territory re-matching")

        # ── Step 5: Check pricing for remaining candidates ──
        for (pid, pdata, company, company_key, email_str, full_name, title,
             resolved_state, resolved_district, resolved_name, resolved_type) in filtered_candidates:

            prospect = pdata["prospect"]
            emails = prospect.get("emails") or []
            p_first = (prospect.get("first_name") or "")
            p_last = (prospect.get("last_name") or "")

            # Check pricing — fast set lookup from bulk scan (Step 1b)
            if str(pid) in pricing_prospect_ids:
                pricing_sent_count += 1
                audit_pricing_sent.append([company, full_name, email_str, title, "Pricing detected (bulk scan)"])
                continue

            # ── This prospect is a C4 target ──
            notes_parts = []
            if pdata["deliver_count"] > 0:
                notes_parts.append(f"{pdata['deliver_count']} emails delivered")
            if pdata["open_count"] > 0:
                notes_parts.append(f"{pdata['open_count']} opens")
            if pdata["reply_count"] > 0:
                notes_parts.append(f"{pdata['reply_count']} replies (no pricing sent)")
            else:
                notes_parts.append("no reply")
            if title:
                notes_parts.append(f"Title: {title}")
            notes_parts.append(f"Seqs: {','.join(str(s) for s in pdata['sequences'])}")

            engagement_score = min(pdata["open_count"] * 5 + pdata["reply_count"] * 20, 99)
            priority = 750 + engagement_score

            row = [
                resolved_state,      # State (from territory match or Claude inference)
                resolved_name,       # Account Name (canonical NCES name or original)
                email_str,           # Email
                p_first,             # First Name
                p_last,              # Last Name
                resolved_type,       # Deal Level
                resolved_district,   # Parent District
                company_key,         # Name Key
                "cold_license_request",  # Strategy
                "outreach",          # Source
                "pending",           # Status
                str(priority),       # Priority (750-849)
                now,                 # Date Added
                "",                  # Date Approved
                "",                  # Sequence Doc URL
                "",                  # Est. Enrollment
                "",                  # School Count
                "",                  # Total Licenses
                " | ".join(notes_parts),  # Notes (always last)
            ]
            new_rows.append(row)
            prospect_keys.add(company_key)

        if new_rows:
            _write_rows(new_rows)

        # ── Write audit tab for spot-checking ──
        try:
            _write_c4_audit(
                audit_pricing_sent, audit_has_opp, audit_active,
                audit_no_company, audit_out_of_territory, audit_international,
                audit_student_emails,
            )
        except Exception as e:
            logger.warning(f"C4: could not write audit tab: {e}")

        logger.info(
            f"C4: {len(new_rows)} cold license requests added. "
            f"Scanned {len(all_prospects)} prospects, "
            f"{len(pricing_prospect_ids)} pricing (bulk), {pricing_sent_count} pricing (applied), "
            f"{has_opp_count} opps, {already_active} active, {already_known} queued, "
            f"{out_of_territory} out of territory, {international_count} international, "
            f"{student_email_count} student emails, "
            f"{claude_inferred_count} Claude inferred, {audit_no_company} no company."
        )

        return {
            "success": True,
            "new_added": len(new_rows),
            "already_known": already_known,
            "already_active": already_active,
            "pricing_sent": pricing_sent_count,
            "pricing_bulk_detected": len(pricing_prospect_ids),
            "has_opp": has_opp_count,
            "total_scanned": len(all_prospects),
            "no_company": audit_no_company,
            "claude_inferred": claude_inferred_count,
            "out_of_territory": out_of_territory,
            "international": international_count,
            "student_emails": student_email_count,
            "prospects": [r[1] for r in new_rows[:20]],
            "estimated_cost": round(_get_estimated_cost(), 2),
            "api_calls": _c4_cost_tracker["api_calls"],
            "error": "",
        }

    except Exception as e:
        logger.error(f"suggest_cold_license_requests error: {e}")
        return {
            "success": False, "new_added": 0, "already_known": 0,
            "already_active": 0, "pricing_sent": 0, "has_opp": 0,
            "total_scanned": 0, "mailings_checked": 0, "prospects": [],
            "out_of_territory": 0, "international": 0,
            "error": str(e),
        }


def _write_c4_audit(pricing_sent: list, has_opp: list, active: list,
                    no_company: int, out_of_territory: list = None,
                    international: list = None, student_emails: list = None):
    """Write C4 exclusion audit data to a 'C4 Audit' tab for spot-checking."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    tab_name = "C4 Audit"
    out_of_territory = out_of_territory or []
    international = international or []
    student_emails = student_emails or []

    # Ensure tab exists
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if tab_name not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        ).execute()

    # Clear and rewrite
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1:Z9999",
    ).execute()

    rows = [["Company", "Contact Name", "Email", "Title", "Exclusion Reason"]]

    if pricing_sent:
        rows.append(["", "", "", "", ""])
        rows.append(["=== PRICING SENT ===", f"{len(pricing_sent)} prospects", "", "", ""])
        rows.extend(pricing_sent)

    if has_opp:
        rows.append(["", "", "", "", ""])
        rows.append(["=== HAS EXISTING OPP ===", f"{len(has_opp)} prospects", "", "", ""])
        rows.extend(has_opp)

    if active:
        rows.append(["", "", "", "", ""])
        rows.append(["=== ACTIVE CUSTOMER ===", f"{len(active)} prospects", "", "", ""])
        rows.extend(active)

    if international:
        rows.append(["", "", "", "", ""])
        rows.append(["=== INTERNATIONAL ===", f"{len(international)} prospects", "", "", ""])
        rows.extend(international)

    if student_emails:
        rows.append(["", "", "", "", ""])
        rows.append(["=== STUDENT EMAILS ===", f"{len(student_emails)} prospects", "", "", ""])
        rows.extend(student_emails)

    if out_of_territory:
        rows.append(["", "", "", "", ""])
        rows.append(["=== OUT OF TERRITORY ===", f"{len(out_of_territory)} prospects", "", "", ""])
        rows.extend(out_of_territory)

    if no_company:
        rows.append(["", "", "", "", ""])
        rows.append(["=== NO COMPANY NAME ===", f"{no_company} prospects skipped", "", "", ""])

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": rows}
    ).execute()

    logger.info(
        f"C4 Audit tab written: {len(pricing_sent)} pricing, {len(has_opp)} opps, "
        f"{len(active)} active, {len(international)} intl, {len(student_emails)} students, "
        f"{len(out_of_territory)} out of territory, {no_company} no company"
    )


def add_district(name: str, state: str, notes: str = "", strategy: str = "cold",
                  source: str = "manual", signal_id: str = "") -> dict:
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
            state_abbr,     # State
            name,           # Account Name
            "",             # Email
            "",             # First Name
            "",             # Last Name
            "",             # Deal Level
            "",             # Parent District
            name_key,       # Name Key
            strategy,       # Strategy
            source,         # Source
            "pending",      # Status
            str(priority),  # Priority
            now,            # Date Added
            "",             # Date Approved
            "",             # Sequence Doc URL
            "",             # Est. Enrollment
            "",             # School Count
            "",             # Total Licenses
            signal_id,      # Signal ID
            notes,          # Notes (always last)
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
        tag = {"upward": "REF", "winback": "WINBACK", "cold_license_request": "LIC REQ"}.get(strategy, "COLD")
        name = d.get("Account Name", d.get("District Name", "?"))
        state = d.get("State", "")
        priority = d.get("Priority", "")
        school_count = d.get("School Count", "")
        enrollment = d.get("Est. Enrollment", "")

        deal_level = d.get("Deal Level", "")
        parent_district = d.get("Parent District", "")

        line = f"{i}. [{tag}] *{name}* ({state})"
        details = []
        if strategy == "winback" and deal_level == "school" and parent_district:
            details.append(f"🏫 under {parent_district}")
        elif strategy == "winback" and deal_level == "district":
            details.append("🏛️ district deal")
        if school_count and str(school_count) != "0":
            details.append(f"{school_count} active schools")
        if enrollment and str(enrollment) != "0" and str(enrollment) != "":
            details.append(f"~{enrollment} students")
        # Show contact info for C4 (cold_license_request)
        contact_name = f"{d.get('First Name', '')} {d.get('Last Name', '')}".strip()
        if strategy == "cold_license_request" and contact_name:
            details.append(contact_name)
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

    status_order = ["pending", "approved", "researching", "draft", "complete", "skipped"]
    status_emoji = {
        "pending": "⏳", "approved": "✅", "researching": "🔍",
        "draft": "📝", "complete": "📄", "skipped": "⏭",
    }

    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        emoji = status_emoji.get(status, "•")
        lines.append(f"{emoji} *{status.upper()}* ({len(group)})")
        for d in group[:10]:  # cap at 10 per status to keep message manageable
            strategy = d.get("Strategy", "cold")
            tag = {"upward": "REF", "winback": "WINBACK", "cold_license_request": "LIC REQ"}.get(strategy, "COLD")
            name = d.get("Account Name", d.get("District Name", "?"))
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


# ─────────────────────────────────────────────
# COHORT / LOOKALIKE PROSPECTING (#22)
# ─────────────────────────────────────────────

def find_lookalike_districts(state: str = "", max_results: int = 25,
                             min_enrollment: int = 500) -> dict:
    """
    Find districts demographically similar to Steven's best active customers.

    Algorithm:
    1. Profile active accounts: enrollment distribution, median/mean school count
    2. Filter NCES districts to same enrollment bracket
    3. Exclude existing customers, pipeline, and prospects
    4. Score by similarity to customer profile
    5. Return top N matches sorted by similarity score

    Args:
        state: Optional state filter (2-letter code). Empty = all territory states.
        max_results: Max districts to return. Default 25.
        min_enrollment: Minimum district enrollment. Default 500.

    Returns:
        {success, lookalikes: [{name, state, enrollment, school_count, similarity, reason}],
         profile: {enrollment_range, median_enrollment, median_schools, account_count},
         total_candidates}
    """
    try:
        # Step 1: Profile active customers
        active_accounts = csv_importer.get_active_accounts()
        if not active_accounts:
            return {"success": False, "error": "No active accounts found."}

        # Load NCES districts to get enrollment data for active accounts
        all_districts = territory_data._load_territory_districts()
        nces_by_key = {}
        for d in all_districts:
            key = d.get("Name Key", "")
            if key:
                nces_by_key[key] = d

        # Build profile from district-level active accounts
        customer_enrollments = []
        customer_schools = []
        customer_licenses = []
        for acc in active_accounts:
            acc_type = (acc.get("Account Type") or "").lower()
            if acc_type != "district":
                continue
            name_key = acc.get("Name Key", "") or csv_importer.normalize_name(
                acc.get("Active Account Name", "") or acc.get("Display Name", ""))
            nces = nces_by_key.get(name_key, {})
            try:
                enroll = int(nces.get("Enrollment") or 0)
                if enroll > 0:
                    customer_enrollments.append(enroll)
            except (ValueError, TypeError):
                pass
            try:
                schools = int(nces.get("School Count") or 0)
                if schools > 0:
                    customer_schools.append(schools)
            except (ValueError, TypeError):
                pass
            try:
                lic = int(acc.get("Active Licenses") or 0)
                if lic > 0:
                    customer_licenses.append(lic)
            except (ValueError, TypeError):
                pass

        if not customer_enrollments:
            return {"success": False, "error": "No district-level active accounts with NCES enrollment data."}

        # Compute profile stats
        customer_enrollments.sort()
        customer_schools.sort()
        n = len(customer_enrollments)
        median_enrollment = customer_enrollments[n // 2]
        mean_enrollment = sum(customer_enrollments) // n
        p25_enrollment = customer_enrollments[max(0, n // 4)]
        p75_enrollment = customer_enrollments[min(n - 1, 3 * n // 4)]
        # Expand the bracket for matching — ±50% of the 25-75th percentile range
        bracket_low = max(min_enrollment, int(p25_enrollment * 0.5))
        bracket_high = int(p75_enrollment * 1.5)

        median_schools = customer_schools[len(customer_schools) // 2] if customer_schools else 0

        profile = {
            "account_count": n,
            "enrollment_range": f"{bracket_low:,}–{bracket_high:,}",
            "median_enrollment": median_enrollment,
            "mean_enrollment": mean_enrollment,
            "p25_enrollment": p25_enrollment,
            "p75_enrollment": p75_enrollment,
            "median_schools": median_schools,
        }

        # Step 2: Build exclusion sets
        active_keys = set()
        for acc in active_accounts:
            key = acc.get("Name Key", "") or csv_importer.normalize_name(
                acc.get("Active Account Name", "") or acc.get("Display Name", ""))
            if key:
                active_keys.add(key)

        pipeline_keys = set()
        try:
            opps = pipeline_tracker.get_open_opps()
            for o in opps:
                key = csv_importer.normalize_name(o.get("Account Name", ""))
                if key:
                    pipeline_keys.add(key)
        except Exception:
            pass

        prospect_keys = set()
        try:
            prospects = _load_all_prospects()
            for p in prospects:
                key = p.get("Name Key", "")
                if key:
                    prospect_keys.add(key)
        except Exception:
            pass

        excluded = active_keys | pipeline_keys | prospect_keys

        # Step 3: Filter NCES districts
        if state:
            districts = territory_data._load_territory_districts(state.upper())
        else:
            districts = all_districts

        candidates = []
        total_candidates = 0
        # Agency Type can be stored as numeric code ("1") or full text ("Regular local school district")
        _VALID_AGENCY_TYPES = {
            "1", "2", "7", "9",
            "Regular local school district",
            "Local school district (component of supervisory union)",
            "Charter school agency",
            "Specialized public school district",
        }
        for d in districts:
            agency_type = str(d.get("Agency Type", ""))
            if agency_type not in _VALID_AGENCY_TYPES:
                continue

            name_key = d.get("Name Key", "")
            if not name_key or name_key in excluded:
                continue

            try:
                enrollment = int(d.get("Enrollment") or 0)
            except (ValueError, TypeError):
                continue
            if enrollment < min_enrollment or enrollment < bracket_low or enrollment > bracket_high:
                continue

            try:
                school_count = int(d.get("School Count") or 0)
            except (ValueError, TypeError):
                school_count = 0

            total_candidates += 1

            # Step 4: Score by similarity to customer profile
            # Enrollment similarity (closer to median = higher score)
            enroll_diff = abs(enrollment - median_enrollment) / max(median_enrollment, 1)
            enroll_score = max(0, 100 - int(enroll_diff * 100))

            # School count similarity
            if median_schools > 0 and school_count > 0:
                school_diff = abs(school_count - median_schools) / max(median_schools, 1)
                school_score = max(0, 100 - int(school_diff * 100))
            else:
                school_score = 50  # Neutral if no data

            # In-territory bonus
            d_state = d.get("State", "").upper()
            territory_bonus = 20 if d_state in _TERRITORY_STATES else 0

            similarity = int(enroll_score * 0.5 + school_score * 0.3 + territory_bonus)

            candidates.append({
                "name": d.get("District Name", "Unknown"),
                "state": d_state,
                "enrollment": enrollment,
                "school_count": school_count,
                "similarity": similarity,
                "name_key": name_key,
                "city": d.get("City", ""),
                "lat": d.get("Lat", ""),
                "lon": d.get("Lon", ""),
            })

        # Step 5: Sort by similarity, return top N
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        lookalikes = candidates[:max_results]

        # Generate reason text
        for la in lookalikes:
            parts = []
            e = la["enrollment"]
            if p25_enrollment <= e <= p75_enrollment:
                parts.append(f"enrollment ({e:,}) in customer sweet spot")
            else:
                parts.append(f"enrollment ({e:,}) near customer median ({median_enrollment:,})")
            if la["school_count"] and median_schools:
                parts.append(f"{la['school_count']} schools (customer median: {median_schools})")
            la["reason"] = "; ".join(parts)

        return {
            "success": True,
            "lookalikes": lookalikes,
            "profile": profile,
            "total_candidates": total_candidates,
        }

    except Exception as e:
        logger.error(f"Lookalike search failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def format_lookalikes_for_telegram(result: dict) -> str:
    """Format lookalike results for Telegram display."""
    if not result.get("success"):
        return f"Lookalike search failed: {result.get('error', 'Unknown error')}"

    profile = result["profile"]
    lookalikes = result["lookalikes"]
    total = result["total_candidates"]

    lines = [
        "🔍 *Lookalike District Analysis*\n",
        f"*Customer Profile* ({profile['account_count']} district accounts):",
        f"  Enrollment bracket: {profile['enrollment_range']}",
        f"  Median enrollment: {profile['median_enrollment']:,}",
        f"  Median schools: {profile['median_schools']}",
        f"\n*Top {len(lookalikes)} Lookalikes* ({total:,} total candidates)\n",
    ]

    for i, la in enumerate(lookalikes, 1):
        lines.append(
            f"  {i}. *{la['name']}* ({la['state']})\n"
            f"     Enrollment: {la['enrollment']:,} | Schools: {la['school_count']}"
            f" | Score: {la['similarity']}"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────
# STRATEGY #11: SEQUENCE RE-ENGAGEMENT (report-then-act)
# ─────────────────────────────────────────────

_C4_SEQUENCE_IDS = {1995, 1996, 1997, 1998}


def get_sequence_reengagement_overview(exclude_sequence_ids=None) -> dict:
    """
    Fast overview: list all sequences with approximate no-reply counts.
    Uses only get_sequences() — ONE API call, no per-prospect scanning.

    Returns {success, sequences: [{id, name, num_contacted, num_replied, est_no_reply, reply_rate_pct}]}
    """
    try:
        import tools.outreach_client as outreach_client
        if not outreach_client.is_authenticated():
            return {"success": False, "error": "Outreach not authenticated.", "sequences": []}

        exclude = _C4_SEQUENCE_IDS.copy()
        if exclude_sequence_ids:
            exclude.update(exclude_sequence_ids)

        sequences = outreach_client.get_sequences()
        if not sequences:
            return {"success": False, "error": "No sequences found.", "sequences": []}

        result_seqs = []
        for s in sequences:
            seq_id = int(s.get("id", 0))
            if seq_id in exclude:
                continue
            contacted = int(s.get("num_contacted", 0) or 0)
            if contacted == 0:
                continue
            replied = int(s.get("num_replied", 0) or 0)
            est_no_reply = max(0, contacted - replied)
            reply_rate = round(replied / contacted * 100) if contacted > 0 else 0

            result_seqs.append({
                "id": seq_id,
                "name": s.get("name", f"Sequence {seq_id}"),
                "num_contacted": contacted,
                "num_replied": replied,
                "est_no_reply": est_no_reply,
                "reply_rate_pct": reply_rate,
            })

        result_seqs.sort(key=lambda x: x["est_no_reply"], reverse=True)
        return {"success": True, "sequences": result_seqs}

    except Exception as e:
        logger.error(f"Reengagement overview failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "sequences": []}


def scan_sequence_for_reengagement(sequence_id, segment="engaged",
                                   progress_callback=None) -> dict:
    """
    Scan ONE sequence for finished/no-reply prospects. Filters by territory,
    active customers, existing prospects. Returns candidates for the requested
    segment WITHOUT writing to Prospecting Queue.

    Args:
        sequence_id: Outreach sequence ID
        segment: "engaged" (default), "lurker", "ghost", or "all"

    Returns {success, sequence_name, total_no_reply, segment_counts, candidates: [dicts]}
    """
    try:
        import tools.outreach_client as outreach_client
        if not outreach_client.is_authenticated():
            return {"success": False, "error": "Outreach not authenticated."}

        if progress_callback:
            progress_callback(f"Scanning sequence {sequence_id}...")

        states = outreach_client.get_sequence_states(sequence_id, include_prospect=True)

        # Get sequence name
        sequences = outreach_client.get_sequences()
        seq_name = f"Sequence {sequence_id}"
        for s in sequences:
            if int(s.get("id", 0)) == int(sequence_id):
                seq_name = s.get("name", seq_name)
                break

        # Build exclusion sets
        active_accounts = csv_importer.get_active_accounts()
        active_keys = {
            acc.get("Name Key", "") or csv_importer.normalize_name(
                acc.get("Active Account Name", "") or acc.get("Display Name", ""))
            for acc in active_accounts
        }
        active_keys.discard("")

        existing_prospects = _load_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in existing_prospects if p.get("Name Key")}

        try:
            pipeline_keys = set()
            for o in pipeline_tracker.get_open_opps():
                key = csv_importer.normalize_name(o.get("Account Name", ""))
                if key:
                    pipeline_keys.add(key)
        except Exception:
            pipeline_keys = set()

        excluded_keys = active_keys | prospect_keys | pipeline_keys

        # International TLDs to exclude
        _INTL_TLDS = (
            ".ca", ".uk", ".au", ".nz", ".in", ".za", ".ng", ".ke", ".gh",
            ".ph", ".sg", ".my", ".hk", ".jp", ".kr", ".tw", ".br", ".mx",
            ".co", ".cl", ".ar", ".de", ".fr", ".es", ".it", ".nl", ".se",
            ".no", ".dk", ".fi", ".ie", ".be", ".at", ".ch", ".pt", ".pl",
            ".cz", ".hu", ".ro", ".bg", ".hr", ".rs", ".ae", ".sa", ".qa",
            ".eg", ".pk", ".bd", ".lk", ".th", ".vn", ".id",
        )
        _INTL_EDU_TLDS = (
            ".edu.cl", ".edu.au", ".edu.uk", ".edu.sg", ".edu.hk", ".edu.ph",
            ".edu.my", ".edu.in", ".edu.pk", ".edu.ng", ".edu.za",
            ".ac.uk", ".ac.nz", ".ac.jp", ".ac.kr", ".ac.in", ".ac.za",
            ".gc.ca", ".on.ca", ".bc.ca", ".ab.ca", ".qc.ca",
        )

        # NCES district→state lookup for territory filtering
        import tools.signal_processor as signal_processor

        # Process prospects
        all_candidates = []
        segment_counts = {"engaged": 0, "lurker": 0, "ghost": 0}

        for entry in states:
            if entry.get("state") != "finished":
                continue
            if int(entry.get("reply_count", 0) or 0) > 0:
                continue

            prospect = entry.get("prospect", {})
            if not prospect:
                continue

            emails = prospect.get("emails", [])
            email = emails[0] if emails else ""
            company = (prospect.get("company") or "").strip()
            first_name = (prospect.get("first_name") or "").strip()
            last_name = (prospect.get("last_name") or "").strip()

            if not company and not email:
                continue

            # Exclude international emails
            if email and "@" in email:
                domain = email.split("@")[1].lower()
                if any(domain.endswith(tld) for tld in _INTL_EDU_TLDS):
                    continue
                if any(domain.endswith(tld) for tld in _INTL_TLDS):
                    continue

            name_key = csv_importer.normalize_name(company) if company else ""

            # Skip known
            if name_key and name_key in excluded_keys:
                continue

            # Territory check: NCES lookup on company name, then email domain patterns
            state_code = ""
            if company:
                state_code = signal_processor.lookup_district_state(company)

            if not state_code and email and "@" in email:
                domain = email.split("@")[1].lower()
                # k12.STATE.us pattern
                if ".k12." in domain:
                    parts = domain.split(".")
                    for i, p in enumerate(parts):
                        if p == "k12" and i + 1 < len(parts):
                            st = parts[i + 1].upper()
                            if len(st) == 2:
                                state_code = st
                                break
                # .gov state domains
                elif ".gov" in domain:
                    parts = domain.split(".")
                    for p in parts:
                        if len(p) == 2 and p.upper() in _TERRITORY_STATES:
                            state_code = p.upper()
                            break

            # Must be in territory — skip if unknown or out-of-territory
            if not state_code or state_code not in _TERRITORY_STATES:
                continue

            # Segment
            open_count = int(entry.get("open_count", 0) or 0)
            click_count = int(entry.get("click_count", 0) or 0)

            if open_count >= 3 or click_count > 0:
                seg = "engaged"
                priority = 750
            elif open_count > 0:
                seg = "lurker"
                priority = 700
            else:
                seg = "ghost"
                priority = 600

            segment_counts[seg] += 1

            cand = {
                "State": state_code,
                "Account Name": company,
                "Email": email,
                "First Name": first_name,
                "Last Name": last_name,
                "Name Key": name_key,
                "segment": seg,
                "priority": priority,
                "seq_name": seq_name,
                "open_count": open_count,
                "click_count": click_count,
                "Strategy": "sequence_reengagement",
                "Source": "outreach",
            }
            all_candidates.append(cand)

        # Filter to requested segment
        if segment == "all":
            filtered = all_candidates
        else:
            filtered = [c for c in all_candidates if c["segment"] == segment]

        # Sort: highest engagement first
        filtered.sort(key=lambda x: (x["open_count"] + x["click_count"] * 3), reverse=True)

        total_no_reply = sum(segment_counts.values())
        logger.info(f"Reengagement scan {seq_name}: {total_no_reply} no-reply, "
                    f"showing {len(filtered)} ({segment})")

        return {
            "success": True,
            "sequence_name": seq_name,
            "sequence_id": sequence_id,
            "total_no_reply": total_no_reply,
            "segment_counts": segment_counts,
            "segment_shown": segment,
            "candidates": filtered,
        }

    except Exception as e:
        logger.error(f"Reengagement scan failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def format_reengagement_overview(result: dict, min_no_reply: int = 20,
                                  max_display: int = 15) -> str:
    """Format sequence overview for Telegram. Only shows sequences with meaningful volume."""
    if not result.get("success"):
        return f"Reengagement overview failed: {result.get('error', 'Unknown error')}"

    all_seqs = result.get("sequences", [])
    if not all_seqs:
        return "No sequences with contacted prospects found."

    # Filter to sequences worth scanning
    seqs = [s for s in all_seqs if s["est_no_reply"] >= min_no_reply]
    hidden = len(all_seqs) - len(seqs)

    if not seqs:
        return (f"No sequences with {min_no_reply}+ unresponsive prospects.\n"
                f"({len(all_seqs)} sequences checked, all below threshold)")

    lines = [f"🔄 *Sequences with {min_no_reply}+ unresponsive prospects*\n"]
    for i, s in enumerate(seqs[:max_display], 1):
        lines.append(
            f"  {i}. *{s['name']}*\n"
            f"     Contacted: {s['num_contacted']:,} | Est. no-reply: ~{s['est_no_reply']:,}"
        )
    if len(seqs) > max_display:
        lines.append(f"\n  ... and {len(seqs) - max_display} more above threshold")
    if hidden:
        lines.append(f"  ({hidden} sequences with <{min_no_reply} no-reply hidden)")

    lines.append(f"\nScan one: `/prospect_reengagement 2`")
    lines.append(f"With segment: `/prospect_reengagement 2 lurker`")
    return "\n".join(lines)


def format_reengagement_scan(result: dict) -> str:
    """Format single-sequence scan results for Telegram."""
    if not result.get("success"):
        return f"Scan failed: {result.get('error', 'Unknown error')}"

    seg_counts = result.get("segment_counts", {})
    seg_shown = result.get("segment_shown", "engaged")
    candidates = result.get("candidates", [])
    seq_name = result.get("sequence_name", "Unknown")

    lines = [
        f"🔄 *{seq_name}*",
        f"Total no-reply: {result.get('total_no_reply', 0)}",
        f"  🟢 Engaged: {seg_counts.get('engaged', 0)}"
        f" | 🟡 Lurkers: {seg_counts.get('lurker', 0)}"
        f" | ⚪ Ghosts: {seg_counts.get('ghost', 0)}\n",
    ]

    if not candidates:
        lines.append(f"No *{seg_shown}* prospects in this sequence.")
        lines.append(f"Try: `/prospect_reengagement {result.get('sequence_id', '')} all`")
        return "\n".join(lines)

    lines.append(f"Showing *{seg_shown}* ({len(candidates)}):\n")
    for i, c in enumerate(candidates[:10], 1):
        name = f"{c.get('First Name', '')} {c.get('Last Name', '')}".strip() or "Unknown"
        email = c.get("Email", "")
        company = c.get("Account Name", "")
        state = c.get("State", "")
        opens = c.get("open_count", 0)
        clicks = c.get("click_count", 0)
        loc = f"{company}, {state}" if state else company
        lines.append(f"  {i}. *{name}* ({email})\n     {loc} | Opens: {opens}, Clicks: {clicks}")

    if len(candidates) > 10:
        lines.append(f"\n  ... and {len(candidates) - 10} more")

    lines.append(f"\n`/prospect_approve 1,3,5` to queue selected")
    lines.append(f"`/prospect_approve all` to queue all {len(candidates)}")
    return "\n".join(lines)
