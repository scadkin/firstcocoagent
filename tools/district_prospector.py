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
    "Strategy",         # "upward" | "cold" | "winback" | "cold_license_request"
    "Source",           # "web_search" | "manual" | "upward_auto" | "pipeline_closed" | "outreach"
    "Status",           # "pending" | "approved" | "researching" | "draft" | "complete" | "skipped"
    "Priority",         # numeric score (higher = more important)
    "Date Added",
    "Date Approved",
    "Sequence Doc URL",
    "Est. Enrollment",
    "School Count",
    "Total Licenses",
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
    Migrate old 16-column Prospecting Queue rows to 19-column layout.
    Inserts Email, First Name, Last Name columns after Account Name.

    Old: State | Account Name | Deal Level | Parent District | Name Key | Strategy(idx5) | ...
    New: State | Account Name | Email | First Name | Last Name | Deal Level | Parent District | Name Key | Strategy(idx8) | ...

    Safe to run multiple times — detects which rows need migration.
    Returns {migrated, total, already_correct, errors}.
    """
    _KNOWN_STRATEGIES = {"upward", "cold", "winback", "cold_license_request"}

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Read ALL data including header to understand current state
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
            # Pad to at least 19 columns
            padded = list(row) + [""] * max(0, 19 - len(row))

            # Detection: check if Strategy value is at old index 5 or new index 8
            val_at_5 = padded[5] if len(padded) > 5 else ""
            val_at_8 = padded[8] if len(padded) > 8 else ""

            if val_at_8 in _KNOWN_STRATEGIES:
                # Already in new 19-column format
                new_data.append(padded[:19])
                already_correct += 1
            elif val_at_5 in _KNOWN_STRATEGIES:
                # Old 16-column format — insert 3 empty cols after Account Name
                migrated_row = padded[:2] + ["", "", ""] + padded[2:]
                new_data.append(migrated_row[:19])
                migrated_count += 1
            else:
                # Unknown format — keep as-is, pad to 19
                new_data.append(padded[:19])
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
            range=f"'{TAB_PROSPECT_QUEUE}'!A:S"
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


_KNOWN_STRATEGIES = {"upward", "cold", "winback", "cold_license_request"}


def cleanup_prospect_queue() -> dict:
    """Remove rows with invalid/empty Strategy and deduplicate by Name Key (keep last).

    Returns {total_before, total_after, removed_invalid, removed_duplicate, errors}.
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PROSPECT_QUEUE}'!A:S"
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


def _serper_resolve_locations(unknowns: list[dict], batch_size: int = 15) -> dict:
    """
    Use Serper web search + Claude to determine state for unknown prospects.
    Each unknown has: company, email.

    Strategy (like Steven does manually):
      1. For institutional emails: search the email domain directly (e.g., "kippneworleans.org")
         — first result is usually the school/district homepage showing location
      2. For generic emails: search the school/company name
      3. Feed search results to Claude to extract state, district, city

    Returns dict keyed by email → {state, district, city}
    """
    import anthropic
    import json as _json

    if not SERPER_API_KEY:
        return {}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    _GENERIC_EMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
        "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
        "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
        "earthlink.net", "me.com", "live.com", "ymail.com",
    }

    serper_headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    results = {}

    for batch_start in range(0, len(unknowns), batch_size):
        batch = unknowns[batch_start:batch_start + batch_size]
        search_context = []

        with httpx.Client(timeout=15.0) as http:
            for u in batch:
                company = u.get("company", "")
                email = u.get("email", "")
                domain = email.split("@")[-1].lower() if "@" in email else ""

                # Build search query — simple and direct, like googling the domain
                queries = []
                if domain and domain not in _GENERIC_EMAIL_DOMAINS:
                    # Search 1: just the domain (most natural — like typing it in Google)
                    queries.append(domain)
                    # Search 2: domain + school name for more context
                    if company and company != "Unknown" and company != email:
                        queries.append(f"{domain} {company}")
                elif company and company != "Unknown" and company != email:
                    # Generic email — search by school name
                    queries.append(f'"{company}" school')

                if not queries:
                    search_context.append({"company": company, "email": email, "snippets": ""})
                    continue

                all_snippets = []
                for query in queries[:2]:  # max 2 searches per prospect
                    try:
                        resp = http.post(SERPER_URL, headers=serper_headers,
                                         json={"q": query, "num": 3})
                        if resp.status_code == 200:
                            data = resp.json()
                            # Organic results — title + snippet + URL
                            for item in data.get("organic", [])[:3]:
                                title = item.get("title", "")
                                snippet = item.get("snippet", "")
                                link = item.get("link", "")
                                all_snippets.append(f"{title} | {snippet} | {link}")
                            # Knowledge graph — often has address directly
                            kg = data.get("knowledgeGraph", {})
                            if kg:
                                attrs = kg.get("attributes", {})
                                addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                                kg_desc = kg.get("description", "")
                                kg_title = kg.get("title", "")
                                all_snippets.append(f"[Knowledge Graph] {kg_title} | {kg_desc} | Address: {addr}")
                    except Exception as e:
                        logger.debug(f"C4 Serper search failed for '{query}': {e}")

                search_context.append({
                    "company": company, "email": email,
                    "snippets": "\n".join(all_snippets) if all_snippets else ""
                })

        # Send search results to Claude for state extraction
        records_with_results = [sc for sc in search_context if sc["snippets"]]
        if not records_with_results:
            continue

        records_text = ""
        for idx, sc in enumerate(records_with_results, 1):
            domain = sc["email"].split("@")[-1] if "@" in sc["email"] else ""
            records_text += f"{idx}. Domain: {domain} | School: {sc['company']} | Email: {sc['email']}\n"
            records_text += f"   Google results:\n{sc['snippets'][:600]}\n\n"

        prompt = f"""I searched Google for these school/district email domains. Based on the search results, determine the US state, city, and parent school district for each.

Look for:
- Address or location in the search results or knowledge graph
- District name in page titles or URLs (e.g., "kippneworleans.org" → KIPP New Orleans → Louisiana)
- State abbreviations in URLs or snippets

RECORDS:
{records_text}

Respond with ONLY a JSON array, no other text. Each element:
{{"idx": 1, "state": "MO", "district": "Mary Institute and Country Day School", "city": "St. Louis"}}

Use "" for state only if the search results give NO location clue at all.
"""
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parsed = _json.loads(text)
            for item in parsed:
                idx = item.get("idx", 0)
                if 1 <= idx <= len(records_with_results):
                    sc = records_with_results[idx - 1]
                    state = (item.get("state") or "").strip().upper()
                    if state and len(state) == 2:
                        entry = {
                            "state": state,
                            "district": item.get("district", ""),
                            "city": item.get("city", ""),
                        }
                        # Index by email (unique and reliable for lookup)
                        if sc["email"]:
                            results[sc["email"]] = entry
                        # Also index by company as fallback
                        if sc["company"]:
                            results[sc["company"]] = entry

            logger.info(f"C4 Serper: resolved {len([i for i in parsed if (i.get('state') or '').strip()])} "
                        f"of {len(records_with_results)} searched (batch {batch_start // batch_size + 1})")
        except Exception as e:
            logger.error(f"C4 Serper: Claude extraction failed for batch {batch_start // batch_size + 1}: {e}")

        import time as _time
        _time.sleep(0.5)

    return results


def _serper_resolve_districts(unknowns: list[dict], batch_size: int = 20) -> dict:
    """
    Use Serper web search + Claude to find parent school districts for prospects
    that already have a state but no parent district.

    Each unknown has: company (school name), email, state.

    Strategy: Google the email domain — the school's website or district site
    usually shows up first, making the parent district obvious.

    Returns dict keyed by email → {district: "District Name"}
    """
    import anthropic
    import json as _json

    if not SERPER_API_KEY:
        return {}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    _GENERIC_EMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
        "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
        "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
        "earthlink.net", "me.com", "live.com", "ymail.com",
    }

    serper_headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    results = {}

    for batch_start in range(0, len(unknowns), batch_size):
        batch = unknowns[batch_start:batch_start + batch_size]
        search_context = []

        with httpx.Client(timeout=15.0) as http:
            for u in batch:
                company = u.get("company", "")
                email = u.get("email", "")
                state = u.get("state", "")
                domain = email.split("@")[-1].lower() if "@" in email else ""

                # Search: domain directly (like Steven does), or school name + state
                query = ""
                if domain and domain not in _GENERIC_EMAIL_DOMAINS:
                    query = domain
                elif company and company != "Unknown" and company != email:
                    query = f'"{company}" {state} school district'

                if not query:
                    search_context.append({"company": company, "email": email, "state": state, "snippets": ""})
                    continue

                try:
                    resp = http.post(SERPER_URL, headers=serper_headers,
                                     json={"q": query, "num": 3})
                    all_snippets = []
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("organic", [])[:3]:
                            all_snippets.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                        kg = data.get("knowledgeGraph", {})
                        if kg:
                            attrs = kg.get("attributes", {})
                            addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                            all_snippets.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                    search_context.append({
                        "company": company, "email": email, "state": state,
                        "snippets": "\n".join(all_snippets) if all_snippets else ""
                    })
                except Exception:
                    search_context.append({"company": company, "email": email, "state": state, "snippets": ""})

        records_with_results = [sc for sc in search_context if sc["snippets"]]
        if not records_with_results:
            continue

        records_text = ""
        for idx, sc in enumerate(records_with_results, 1):
            domain = sc["email"].split("@")[-1] if "@" in sc["email"] else ""
            records_text += (f"{idx}. School: {sc['company']} | Domain: {domain} "
                            f"| State: {sc['state']} | Email: {sc['email']}\n")
            records_text += f"   Google results:\n{sc['snippets'][:500]}\n\n"

        prompt = f"""I searched Google for these school email domains. I already know the state for each one.
I need you to determine the PARENT SCHOOL DISTRICT for each school.

Rules:
- The email domain often IS the district (e.g., neisd.net = North East ISD, austinisd.org = Austin ISD)
- Look at the Google results for district names in page titles, URLs, and snippets
- If the school IS a district (ISD, USD, etc.), the parent district is itself
- For private/charter schools, use the school name as the district
- Look at the website footer or "about" info in snippets for district affiliation

RECORDS:
{records_text}

Respond with ONLY a JSON array:
{{"idx": 1, "district": "North East Independent School District"}}

Always return a district name — use the school name itself if you can't find a parent district.
"""
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parsed = _json.loads(text)
            for item in parsed:
                idx = item.get("idx", 0)
                if 1 <= idx <= len(records_with_results):
                    sc = records_with_results[idx - 1]
                    district = (item.get("district") or "").strip()
                    if district:
                        entry = {"district": district}
                        if sc["email"]:
                            results[sc["email"]] = entry
                        if sc["company"]:
                            results[sc["company"]] = entry

            logger.info(f"C4 Serper districts: found {len([i for i in parsed if (i.get('district') or '').strip()])} "
                        f"of {len(records_with_results)} (batch {batch_start // batch_size + 1})")
        except Exception as e:
            logger.error(f"C4 Serper districts: Claude extraction failed: {e}")

        import time as _time
        _time.sleep(0.5)

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
        for opp in closed_lost:
            account = opp.get("Account Name", "").strip()
            if not account:
                continue

            # Enrich: if no Parent Account, try to find it via territory data
            parent = opp.get("Parent Account", "").strip()
            if not parent and territory_school_to_district:
                acct_key = csv_importer.normalize_name(account).lower()
                matched_district = territory_school_to_district.get(acct_key)
                if matched_district:
                    opp["_resolved_parent"] = matched_district
                    territory_resolved += 1

            account_opps.setdefault(account, []).append(opp)

        if territory_resolved:
            logger.info(f"Winback: resolved {territory_resolved} school opps → parent district via territory data")

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
        }

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
            # Quick filter 4: International email?
            is_intl = False
            if email_str:
                email_lower = email_str.lower()
                domain = email_lower.split("@")[-1] if "@" in email_lower else ""
                for tld in intl_tlds:
                    if domain.endswith(tld):
                        is_intl = True
                        break
            if is_intl:
                international_count += 1
                audit_international.append([company, full_name, email_str, title, f"International ({domain})"])
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
                claude_results = territory_matcher.infer_locations_with_claude(unresolved)
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
                progress_callback(f"Web searching {len(still_unknown)} unknown locations...")
            try:
                serper_results = _serper_resolve_locations(still_unknown)
                logger.info(f"C4: Serper returned {len(serper_results)} results for {len(still_unknown)} unknowns")
                serper_resolved = 0
                serper_districts = 0
                for idx, u, need in zip(still_unknown_indices, still_unknown, still_unknown_needs):
                    # Look up by email first (unique), then company name
                    search_result = serper_results.get(u["email"]) or serper_results.get(u["company"])
                    if not search_result:
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
                logger.info(f"C4: Serper resolved {serper_resolved} states + {serper_districts} districts")
            except Exception as e:
                logger.error(f"C4: Serper location resolution failed: {e}")

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
            state_abbr,     # State
            name,           # Account Name
            "",             # Email
            "",             # First Name
            "",             # Last Name
            "",             # Deal Level
            "",             # Parent District
            name_key,       # Name Key
            strategy,       # Strategy
            "manual",       # Source
            "pending",      # Status
            str(priority),  # Priority
            now,            # Date Added
            "",             # Date Approved
            "",             # Sequence Doc URL
            "",             # Est. Enrollment
            "",             # School Count
            "",             # Total Licenses
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
