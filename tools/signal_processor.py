"""
tools/signal_processor.py — Scout Signal Intelligence System.

Processes Gmail emails (Google Alerts, Burbio newsletters, DOE newsletters) to
extract K-12 buying signals. Three-tier pipeline: programmatic (free) → Claude
extraction → Claude judgment.

Tabs:
  - Signals : one row per buying signal (district-level or market intel)

Usage (module-level, not a class):
  import tools.signal_processor as signal_processor
  result = signal_processor.process_all_signals(gas)
  signals = signal_processor.get_active_signals()
  signal_processor.format_hot_signals(limit=5) -> str
"""

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
import urllib.request
from urllib.parse import unquote, urlencode, urlparse, parse_qs

import feedparser

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import tools.csv_importer as csv_importer
import tools.district_prospector as district_prospector
import tools.territory_data as territory_data

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_SIGNALS = "Signals"

SIGNAL_COLUMNS = [
    "ID",               # SIG-001
    "Date Detected",    # YYYY-MM-DD (from email date)
    "Source",           # google_alert / burbio / doe_newsletter / rss_feed / job_posting / boarddocs / manual
    "Source Detail",    # Alert keyword or newsletter title
    "Signal Type",      # bond / leadership / board_meeting / rfp / hiring / grant / ai_policy / technology / curriculum / enrollment / market_intel
    "Scope",            # district / state / national
    "District",         # District name (normalized) or blank
    "State",            # 2-letter code or blank
    "Headline",         # 1-2 sentence summary
    "Dollar Amount",    # $6.2B, $200M, etc. or blank
    "Tier",             # 1 / 2 / 3
    "Heat Score",       # 0-100 (base score, decay applied on read)
    "Urgency",          # routine / time_sensitive / urgent
    "Status",           # new / surfaced / acted / expired
    "Customer Status",  # active / pipeline / closed_lost / prospect / new
    "Source URL",       # Link to article
    "Message ID",       # Gmail message ID for dedup
]

NUM_COLS = len(SIGNAL_COLUMNS)

# ─────────────────────────────────────────────
# SIGNAL CLASSIFICATION
# ─────────────────────────────────────────────

# Signal type → base heat weight
SIGNAL_WEIGHTS = {
    "bond": 35, "leadership": 30, "rfp": 25, "board_meeting": 20,
    "ai_policy": 18, "hiring": 15, "grant": 15, "technology": 15,
    "curriculum": 10, "enrollment": 8, "market_intel": 3,
}

# Regex patterns for signal classification (applied to title + snippet)
SIGNAL_PATTERNS = [
    ("bond", re.compile(
        r"\bbond\b.*(?:pass|approv|measure|referendum|issue|vote|\$)"
        r"|\$\d+[\.\d]*\s*(?:billion|million|[BMbm])\b.*\b(?:bond|capital|construction|facilities)"
        r"|\b(?:capital improvement|facilities)\b.*\$",
        re.IGNORECASE)),
    ("leadership", re.compile(
        r"\b(?:superintendent|supt)\b.*\b(?:named|appointed|hired|new|resign|retire|interim|search|depart)"
        r"|\bnew\b.*\b(?:superintendent|CTO|CIO|chief technology)\b"
        r"|\b(?:superintendent|CTO|CIO)\b.*\b(?:transition|replacement|vacancy)\b",
        re.IGNORECASE)),
    ("rfp", re.compile(
        r"\bRFP\b|\brequest for proposal\b|\brequest for (?:bid|quote)\b"
        r"|\bbid\b.*\b(?:submission|deadline|solicitation)\b"
        r"|\bprocurement\b.*\b(?:technology|software|curriculum)\b",
        re.IGNORECASE)),
    ("board_meeting", re.compile(
        r"\bboard\b.*\b(?:meeting|agenda|vote|approv|discuss|adopt)\b.*\b(?:technology|curriculum|AI|computer|coding|STEM|CTE)\b"
        r"|\bschool board\b.*\b(?:technology|curriculum|AI|computer|coding|STEM|CTE)\b",
        re.IGNORECASE)),
    ("ai_policy", re.compile(
        r"\bAI\b.*\b(?:policy|committee|task force|guidelines|framework)\b.*\b(?:K-12|school|district|education)\b"
        r"|\bartificial intelligence\b.*\b(?:K-12|school|district|education)\b"
        r"|\b(?:K-12|school|district)\b.*\bAI\b.*\b(?:policy|committee|guidelines)\b",
        re.IGNORECASE)),
    ("hiring", re.compile(
        r"\b(?:hiring|position|opening|job|recruit)\b.*\b(?:CS|computer science|CTE|STEM|curriculum|coding|technology director)\b"
        r"|\b(?:CS|computer science|CTE|STEM|coding)\b.*\b(?:teacher|coordinator|specialist|director|position)\b",
        re.IGNORECASE)),
    ("grant", re.compile(
        r"\bgrant\b.*\b(?:award|fund|receive|approv)\b"
        r"|\b(?:Title IV|Perkins|E-Rate|ESSER)\b"
        r"|\bfunding\b.*\b(?:award|approv|receive|allocat)\b.*\b(?:technology|STEM|CTE|CS)\b",
        re.IGNORECASE)),
    ("technology", re.compile(
        r"\btechnology\b.*\b(?:replacement|adoption|upgrade|refresh|initiative|investment)\b"
        r"|\b1:1\b.*\bdevice\b|\bdevice\b.*\brefresh\b"
        r"|\bdigital\b.*\b(?:transformation|initiative|learning)\b.*\b(?:K-12|school|district)\b",
        re.IGNORECASE)),
    ("curriculum", re.compile(
        r"\bcurriculum\b.*\b(?:adopt|review|change|new|implement)\b.*\b(?:CS|computer science|coding|STEM)\b"
        r"|\bcomputer science\b.*\b(?:require|mandate|standard|framework|implement)\b"
        r"|\bcoding\b.*\b(?:require|mandate|curriculum)\b",
        re.IGNORECASE)),
    ("enrollment", re.compile(
        r"\benrollment\b.*\b(?:growth|decline|change|increase|decrease|surge|drop)\b"
        r"|\bstudent\b.*\b(?:population|growth|decline)\b.*\bdistrict\b",
        re.IGNORECASE)),
]

# Dollar amount extraction regex
_DOLLAR_RE = re.compile(
    r"\$\s*(\d[\d,\.]*)\s*(billion|million|B|M|b|m)\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────
# TERRITORY + STATE LOOKUP
# ─────────────────────────────────────────────

TERRITORY_STATES = {"IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE", "TX"}
TERRITORY_STATES_WITH_CA = TERRITORY_STATES | {"CA"}

STATE_NAME_TO_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

ABBR_TO_STATE_NAME = {v: k for k, v in STATE_NAME_TO_ABBR.items()}

# Reuse district regex from district_prospector
_SUFFIX_PATTERN = (
    r"(?:Independent\s+School\s+District|Unified\s+School\s+District|"
    r"Community\s+Unit\s+School\s+District|Community\s+School\s+District|"
    r"County\s+School\s+District|City\s+School\s+District|"
    r"Area\s+School\s+District|Regional\s+School\s+District|"
    r"School\s+District|Public\s+Schools|City\s+Schools|"
    r"County\s+Schools|CISD|CUSD|GISD|NISD|ISD|USD)"
)
_DISTRICT_RE = re.compile(
    r"\b((?:[\w\-\'\.]+\s+){1,5}" + _SUFFIX_PATTERN + r")\b",
    re.IGNORECASE,
)

_BAD_STARTS = {
    "high", "middle", "elementary", "schools", "school", "district", "districts",
    "in", "the", "a", "an", "of", "and", "or", "for", "from", "with", "other",
    "staff", "are", "is", "all", "best", "top", "new", "our", "their", "your",
    "this", "that", "about", "many", "some", "most", "every", "each", "any",
}

# NCES district lookup (lazy-loaded)
_nces_district_to_state = None  # {normalized_name: state_code}
_nces_city_to_states = None     # {city_lower: set of state_codes}

# ─────────────────────────────────────────────
# COST TRACKING
# ─────────────────────────────────────────────

_cost_tracker = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

def _reset_cost():
    _cost_tracker["input_tokens"] = 0
    _cost_tracker["output_tokens"] = 0
    _cost_tracker["api_calls"] = 0

def _track_usage(response):
    usage = getattr(response, "usage", None)
    if usage:
        _cost_tracker["input_tokens"] += getattr(usage, "input_tokens", 0)
        _cost_tracker["output_tokens"] += getattr(usage, "output_tokens", 0)
        _cost_tracker["api_calls"] += 1

def _get_cost() -> float:
    """Haiku: $0.80/MTok in, $4/MTok out. Sonnet: $3/MTok in, $15/MTok out."""
    # Assume Haiku for most calls
    return (_cost_tracker["input_tokens"] * 0.80 / 1_000_000 +
            _cost_tracker["output_tokens"] * 4.0 / 1_000_000)


# ─────────────────────────────────────────────
# GOOGLE SHEETS HELPERS
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
    """Create Signals tab if missing. Always overwrite header row."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_SIGNALS not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_SIGNALS}}}]}
        ).execute()
        logger.info(f"Created tab: {TAB_SIGNALS}")

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_SIGNALS}'!A1",
        valueInputOption="RAW",
        body={"values": [SIGNAL_COLUMNS]}
    ).execute()

    return service, sheet_id


def _col_letter(idx: int) -> str:
    """0-based index to column letter (A, B, ..., Z, AA, ...)."""
    result = ""
    while True:
        result = chr(65 + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


# ─────────────────────────────────────────────
# NCES DISTRICT LOOKUP (lazy-loaded)
# ──────────────────────────────────────���──────

def _load_nces_lookup():
    """Build district→state and city→states dicts from NCES territory data."""
    global _nces_district_to_state, _nces_city_to_states

    if _nces_district_to_state is not None:
        return

    _nces_district_to_state = {}
    _nces_city_to_states = defaultdict(set)

    try:
        districts = territory_data._load_territory_districts()
        for d in districts:
            name = d.get("District Name", "")
            state = d.get("State", "")
            city = d.get("City", "")
            if name and state:
                key = csv_importer.normalize_name(name)
                _nces_district_to_state[key] = state
                # Also store by shortened names (without suffix)
                short = re.sub(
                    r"\s*(independent school district|unified school district|"
                    r"school district|public schools|city schools|county schools)\s*$",
                    "", key, flags=re.IGNORECASE
                ).strip()
                if short and short != key:
                    _nces_district_to_state[short] = state
            if city and state:
                _nces_city_to_states[city.lower()].add(state)

        logger.info(f"NCES lookup loaded: {len(_nces_district_to_state)} district names, "
                    f"{len(_nces_city_to_states)} cities")
    except Exception as e:
        logger.warning(f"Failed to load NCES lookup: {e}")
        _nces_district_to_state = {}
        _nces_city_to_states = defaultdict(set)


def lookup_district_state(district_name: str) -> str:
    """Look up a district name in NCES data. Returns 2-letter state code or ''."""
    _load_nces_lookup()
    key = csv_importer.normalize_name(district_name)
    return _nces_district_to_state.get(key, "")


def lookup_city_states(city: str) -> set:
    """Look up a city name. Returns set of possible state codes."""
    _load_nces_lookup()
    return _nces_city_to_states.get(city.lower(), set())


# ─────────────────────────────────────────────
# GOOGLE ALERT PARSER (Tier 1, all programmatic)
# ─────────────────────────────────────────────

# Section header: === News - 3 new results for [K-12 Computer Science] ===
_ALERT_SECTION_RE = re.compile(
    r'^===\s+\w+\s+-\s+\d+\s+new\s+results?\s+for\s+\[(.+?)\]\s+===',
    re.MULTILINE,
)

# Google redirect URL
_GURL_RE = re.compile(r'<(https?://www\.google\.com/url\?[^>]+)>')

# Section divider
_DIVIDER_RE = re.compile(r'^-\s+-\s+-\s+-\s+-', re.MULTILINE)


def parse_google_alert(email_body: str, email_date: str = "", message_id: str = "") -> list:
    """
    Parse a Google Alert weekly digest email into individual stories.

    Returns list of dicts:
      {keyword, title, source, snippet, url, date, message_id}
    """
    stories = []
    # Normalize CRLF to LF (GAS getPlainBody returns \r\n)
    email_body = email_body.replace("\r\n", "\n")
    sections = _ALERT_SECTION_RE.split(email_body)

    # sections alternates: [pre-text, keyword1, content1, keyword2, content2, ...]
    for i in range(1, len(sections), 2):
        keyword = sections[i].strip()
        content = sections[i + 1] if i + 1 < len(sections) else ""

        # Cut at divider (unsubscribe block)
        div_match = _DIVIDER_RE.search(content)
        if div_match:
            content = content[:div_match.start()]

        # Split into story blocks (double newline between stories)
        blocks = re.split(r'\n\n+', content.strip())

        current_story = {"lines": [], "url": None}
        story_list = []

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Check if block contains a URL
            url_match = _GURL_RE.search(block)
            if url_match:
                current_story["url"] = _extract_real_url(url_match.group(1))
                # Add any text before the URL as individual lines
                text_before = block[:url_match.start()].strip()
                if text_before:
                    for line in text_before.split("\n"):
                        line = line.strip()
                        if line:
                            current_story["lines"].append(line)
                # Finish this story
                if current_story["lines"] or current_story["url"]:
                    story_list.append(current_story)
                current_story = {"lines": [], "url": None}
            else:
                # Split block into individual lines
                for line in block.split("\n"):
                    line = line.strip()
                    if line:
                        current_story["lines"].append(line)

        # Don't forget last story if no URL terminated it
        if current_story["lines"]:
            story_list.append(current_story)

        for s in story_list:
            lines = s["lines"]
            if not lines:
                continue
            title = lines[0] if lines else ""
            source_name = lines[1] if len(lines) > 1 else ""
            snippet = " ".join(lines[2:]) if len(lines) > 2 else ""

            # Skip if title is too short or looks like metadata
            if len(title) < 10 or title.startswith("Unsubscribe") or title.startswith("Sign in"):
                continue

            stories.append({
                "keyword": keyword,
                "title": title,
                "source_name": source_name,
                "snippet": snippet,
                "url": s["url"] or "",
                "date": email_date,
                "message_id": message_id,
            })

    return stories


def _extract_real_url(google_redirect_url: str) -> str:
    """Extract the real destination URL from a Google Alert redirect."""
    try:
        parsed = urlparse(google_redirect_url)
        params = parse_qs(parsed.query)
        real_urls = params.get("url", [])
        if real_urls:
            return unquote(real_urls[0])
    except Exception:
        pass
    return google_redirect_url


# ─────────────────────────────────────────────
# SIGNAL CLASSIFICATION (Tier 1, programmatic)
# ─────────────────────────────────────────────

def classify_signal(text: str) -> tuple:
    """
    Classify text into (signal_type, tier).
    Returns ("market_intel", 3) if no specific signal pattern matches.
    """
    for signal_type, pattern in SIGNAL_PATTERNS:
        if pattern.search(text):
            tier = _signal_tier(signal_type)
            return signal_type, tier
    return "market_intel", 3


def _signal_tier(signal_type: str) -> int:
    """Map signal type to tier (1=highest, 3=context)."""
    tier1 = {"bond", "leadership", "rfp", "board_meeting"}
    tier2 = {"ai_policy", "hiring", "grant", "technology"}
    if signal_type in tier1:
        return 1
    elif signal_type in tier2:
        return 2
    return 3


def extract_dollar_amount(text: str) -> str:
    """Extract the largest dollar amount from text. Returns e.g. '$6.2B' or ''."""
    matches = _DOLLAR_RE.findall(text)
    if not matches:
        return ""

    best = ""
    best_val = 0
    for num_str, unit in matches:
        num = float(num_str.replace(",", ""))
        unit_lower = unit.lower()
        if unit_lower in ("billion", "b"):
            val = num * 1_000_000_000
            formatted = f"${num}B"
        else:
            val = num * 1_000_000
            formatted = f"${num}M"
        if val > best_val:
            best_val = val
            best = formatted

    return best


def extract_district_and_state(text: str) -> tuple:
    """
    Extract (district_name, state_code) from text.
    Uses regex to find district names, then NCES lookup for state.
    Falls back to state name/abbreviation scanning.
    Returns ('', '') if nothing found.
    """
    _load_nces_lookup()

    # Try district regex first
    matches = _DISTRICT_RE.findall(text)
    for match in matches:
        match = match.strip()
        first_word = match.split()[0].lower() if match.split() else ""
        if first_word in _BAD_STARTS:
            continue

        state = lookup_district_state(match)
        if state:
            return match, state

    # Try scanning for state names/abbreviations
    text_lower = text.lower()
    for state_name, abbr in STATE_NAME_TO_ABBR.items():
        if state_name in text_lower:
            # Found a state name — look for any district in that context
            for match in matches:
                match = match.strip()
                first_word = match.split()[0].lower() if match.split() else ""
                if first_word not in _BAD_STARTS:
                    return match, abbr
            return "", abbr

    # Try 2-letter state abbreviations (more risky, need context)
    state_abbr_re = re.compile(r'\b([A-Z]{2})\b')
    for abbr_match in state_abbr_re.finditer(text):
        abbr = abbr_match.group(1)
        if abbr in TERRITORY_STATES_WITH_CA:
            return "", abbr

    return "", ""


# ─────────────────────────────────────────────
# CROSS-REFERENCE LOOKUPS
# ─────────────────────────────────────────────

_cross_ref_cache = None


def _load_cross_references() -> dict:
    """Load Active Accounts + Prospecting Queue + Pipeline for cross-referencing."""
    global _cross_ref_cache
    if _cross_ref_cache is not None:
        return _cross_ref_cache

    try:
        # Active accounts
        accounts = csv_importer.get_active_accounts()
        active_keys = set()
        for a in accounts:
            name = a.get("Active Account Name", "") or a.get("Display Name", "")
            if name:
                active_keys.add(csv_importer.normalize_name(name))

        # Prospecting queue
        prospects = district_prospector.get_all_prospects()
        prospect_keys = {p.get("Name Key", "") for p in prospects if p.get("Name Key")}

        # Pipeline
        try:
            import tools.pipeline_tracker as pipeline_tracker
            opps = pipeline_tracker.get_open_opps()
            pipeline_keys = set()
            for o in opps:
                name = o.get("Account Name", "")
                if name:
                    pipeline_keys.add(csv_importer.normalize_name(name))
        except Exception:
            pipeline_keys = set()

        # Closed-lost
        try:
            import tools.pipeline_tracker as pipeline_tracker
            cl_opps = pipeline_tracker.get_closed_lost_opps(buffer_months=0, lookback_months=24)
            closed_keys = set()
            for o in cl_opps:
                name = o.get("Account Name", "")
                if name:
                    closed_keys.add(csv_importer.normalize_name(name))
        except Exception:
            closed_keys = set()

        _cross_ref_cache = {
            "active": active_keys,
            "prospect": prospect_keys,
            "pipeline": pipeline_keys,
            "closed_lost": closed_keys,
        }
        logger.info(f"Cross-ref loaded: {len(active_keys)} active, {len(prospect_keys)} prospects, "
                    f"{len(pipeline_keys)} pipeline, {len(closed_keys)} closed-lost")
        return _cross_ref_cache

    except Exception as e:
        logger.warning(f"Failed to load cross-references: {e}")
        return {"active": set(), "prospect": set(), "pipeline": set(), "closed_lost": set()}


def check_customer_status(district: str) -> str:
    """Check if a district is an existing customer/prospect. Returns status string."""
    if not district:
        return "new"
    refs = _load_cross_references()
    key = csv_importer.normalize_name(district)
    if key in refs["active"]:
        return "active"
    if key in refs["pipeline"]:
        return "pipeline"
    if key in refs["closed_lost"]:
        return "closed_lost"
    if key in refs["prospect"]:
        return "prospect"
    return "new"


# ─────────────────────────────────────────────
# HEAT SCORING
# ─────────────────────────────────────────────

def compute_heat_score(signal_type: str, tier: int, in_territory: bool,
                       customer_status: str, cluster_count: int = 1,
                       days_old: int = 0) -> int:
    """
    Compute base heat score (0-100). Decay is applied separately on read.
    """
    base = SIGNAL_WEIGHTS.get(signal_type, 5)

    # Territory bonus
    if in_territory:
        base = int(base * 1.5)

    # Customer status modifier
    if customer_status == "active":
        base = int(base * 0.8)  # upsell, lower urgency
    elif customer_status in ("prospect", "pipeline"):
        base = int(base * 0.5)  # already being worked

    # Cluster bonus
    if cluster_count >= 3:
        base = int(base * 1.8)
    elif cluster_count >= 2:
        base = int(base * 1.4)

    # Recency bonus
    if days_old <= 14:
        base = int(base * 1.3)
    elif days_old > 60:
        base = int(base * 0.7)

    return min(base, 100)


def effective_heat(base_heat: int, days_old: int, tier: int,
                   urgency: str = "routine") -> int:
    """Apply decay to heat score based on age, tier, and urgency.
    Time-sensitive/urgent signals decay much slower — the event matters
    more than when we first heard about it."""
    if urgency in ("urgent", "time_sensitive"):
        # Minimal decay for actionable signals — the opportunity window
        # is what matters, not how old the email is
        decay_rate = 0.97  # half-life ~160 days
    elif tier == 1:
        decay_rate = 0.93  # half-life ~90 days
    elif tier == 2:
        decay_rate = 0.88  # half-life ~45 days
    else:
        decay_rate = 0.80  # half-life ~30 days

    weeks = days_old / 7.0
    decayed = base_heat * (decay_rate ** weeks)
    return max(0, int(decayed))


# ─────────────────────────────────────────────
# SIGNAL WRITING + READING
# ─────────────────────────────────────────────

def _next_signal_id(existing_ids: set) -> str:
    """Generate next SIG-NNN ID."""
    max_num = 0
    for sid in existing_ids:
        if sid.startswith("SIG-"):
            try:
                max_num = max(max_num, int(sid[4:]))
            except ValueError:
                pass
    return f"SIG-{max_num + 1:03d}"


def get_processed_message_ids() -> set:
    """Read message IDs + URLs from Signals tab for deduplication.
    Returns composite keys matching write_signals dedup logic: msg_id|url or msg_id."""
    try:
        service, sheet_id = _ensure_tab()
        msg_col_idx = SIGNAL_COLUMNS.index("Message ID")
        url_col_idx = SIGNAL_COLUMNS.index("Source URL")
        msg_letter = _col_letter(msg_col_idx)
        url_letter = _col_letter(url_col_idx)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!{url_letter}2:{msg_letter}",
        ).execute()
        rows = result.get("values", [])
        keys = set()
        for r in rows:
            if not r:
                continue
            # Columns: Source URL (idx 0), Message ID (idx 1)
            url = r[0] if len(r) > 0 else ""
            msg_id = r[1] if len(r) > 1 else ""
            if msg_id:
                dedup_key = f"{msg_id}|{url}" if url else msg_id
                keys.add(dedup_key)
        return keys
    except Exception as e:
        logger.warning(f"Failed to read message IDs: {e}")
        return set()


def get_existing_signal_ids() -> set:
    """Read all signal IDs from the Signals tab."""
    try:
        service, sheet_id = _ensure_tab()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!A2:A",
        ).execute()
        rows = result.get("values", [])
        return {r[0] for r in rows if r and r[0]}
    except Exception:
        return set()


def write_signals(signals: list) -> dict:
    """
    Write signals to the Signals tab. Deduplicates by Message ID.
    Returns {written: int, skipped: int}.
    """
    if not signals:
        return {"written": 0, "skipped": 0}

    service, sheet_id = _ensure_tab()

    # Get existing message IDs and signal IDs for dedup
    existing_msg_ids = get_processed_message_ids()
    existing_sig_ids = get_existing_signal_ids()

    rows = []
    skipped = 0
    for sig in signals:
        msg_id = sig.get("message_id", "")
        url = sig.get("url", "")
        # Dedup by message_id + url combo (same message can have multiple stories)
        dedup_key = f"{msg_id}|{url}" if url else msg_id
        if msg_id and dedup_key in existing_msg_ids:
            skipped += 1
            continue
        existing_msg_ids.add(dedup_key)

        sig_id = _next_signal_id(existing_sig_ids)
        existing_sig_ids.add(sig_id)

        row = [
            sig_id,
            sig.get("date", ""),
            sig.get("source", ""),
            sig.get("source_detail", ""),
            sig.get("signal_type", "market_intel"),
            sig.get("scope", "national"),
            sig.get("district", ""),
            sig.get("state", ""),
            sig.get("headline", ""),
            sig.get("dollar_amount", ""),
            str(sig.get("tier", 3)),
            str(sig.get("heat_score", 0)),
            sig.get("urgency", "routine"),
            "new",
            sig.get("customer_status", "new"),
            sig.get("url", ""),
            sig.get("message_id", ""),
        ]
        rows.append(row)

    if rows:
        last_col = _col_letter(NUM_COLS - 1)
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!A:{last_col}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        logger.info(f"Wrote {len(rows)} signals to Signals tab")

    return {"written": len(rows), "skipped": skipped}


def get_active_signals(state_filter: str = "", scope_filter: str = "",
                       status_filter: str = "new,surfaced") -> list:
    """
    Read active signals from the Signals tab. Applies effective heat decay.
    Returns list of dicts sorted by effective heat score descending.
    """
    try:
        service, sheet_id = _ensure_tab()
        last_col = _col_letter(NUM_COLS - 1)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!A2:{last_col}",
        ).execute()
        rows = result.get("values", [])
    except Exception as e:
        logger.warning(f"Failed to read Signals: {e}")
        return []

    signals = []
    valid_statuses = set(status_filter.split(",")) if status_filter else None

    for row in rows:
        padded = row + [""] * (NUM_COLS - len(row))
        sig = dict(zip(SIGNAL_COLUMNS, padded))

        # Apply filters
        if valid_statuses and sig["Status"] not in valid_statuses:
            continue
        if state_filter and sig["State"].upper() != state_filter.upper():
            continue
        if scope_filter and sig["Scope"] != scope_filter:
            continue

        # Compute effective heat
        try:
            date_detected = datetime.strptime(sig["Date Detected"], "%Y-%m-%d")
            days_old = (datetime.now() - date_detected).days
        except (ValueError, TypeError):
            days_old = 0

        base_heat = int(sig.get("Heat Score", 0) or 0)
        tier = int(sig.get("Tier", 3) or 3)
        urgency = sig.get("Urgency", "routine")
        sig["effective_heat"] = effective_heat(base_heat, days_old, tier, urgency)
        sig["days_old"] = days_old
        signals.append(sig)

    # Sort by effective heat descending
    signals.sort(key=lambda s: s.get("effective_heat", 0), reverse=True)
    return signals


def update_signal_status(signal_id: str, new_status: str) -> bool:
    """Update the status of a signal by ID. Returns True on success."""
    try:
        service, sheet_id = _ensure_tab()
        last_col = _col_letter(NUM_COLS - 1)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!A2:{last_col}",
        ).execute()
        rows = result.get("values", [])

        status_col_idx = SIGNAL_COLUMNS.index("Status")
        for i, row in enumerate(rows):
            if row and row[0] == signal_id:
                row_num = i + 2  # 1-indexed + header
                col_letter = _col_letter(status_col_idx)
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=f"'{TAB_SIGNALS}'!{col_letter}{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[new_status]]},
                ).execute()
                return True

        return False
    except Exception as e:
        logger.warning(f"Failed to update signal status: {e}")
        return False


# ─────────────────────────────────────────────
# BURBIO EXTRACTION (Tier 2, Claude)
# ─────────────────────────────────────────────

def extract_burbio_signals(body: str, email_date: str = "",
                           message_id: str = "") -> list:
    """
    Send a Burbio newsletter body to Claude Haiku for signal extraction.
    Returns list of signal dicts.
    """
    import anthropic

    client = anthropic.Anthropic(timeout=90.0)

    prompt = f"""Extract all K-12 buying signals from this Burbio newsletter.
For each signal found, return a JSON object with these fields:
- district: exact district name mentioned
- state: 2-letter state code
- signal_type: one of: bond, leadership, board_meeting, rfp, hiring, grant, ai_policy, technology, curriculum, enrollment
- headline: 1-2 sentence summary of the signal
- dollar_amount: dollar figure if mentioned (e.g. "$6.2B", "$200M"), or empty string
- urgency: "urgent" (deadline within 14 days), "time_sensitive" (within 30 days), or "routine"

Focus on these territory states: TX, IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE, CA (SoCal only).
Include ALL signals mentioning any US district, not just territory states.
Return ONLY a valid JSON array. No explanation, no markdown.

Newsletter content:
{body[:12000]}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        _track_usage(response)

        text = response.content[0].text.strip()
        # Strip markdown fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        # Find JSON array boundaries
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            text = text[start:end + 1]

        items = json.loads(text)
        signals = []
        for item in items:
            district = item.get("district", "")
            state = item.get("state", "")

            # Validate state via NCES if possible
            if district and not state:
                state = lookup_district_state(district)
            elif district and state:
                # Verify against NCES
                nces_state = lookup_district_state(district)
                if nces_state:
                    state = nces_state

            in_territory = state.upper() in TERRITORY_STATES_WITH_CA if state else False
            cust_status = check_customer_status(district) if district else "new"
            scope = "district" if district else ("state" if state else "national")

            heat = compute_heat_score(
                item.get("signal_type", "market_intel"),
                _signal_tier(item.get("signal_type", "market_intel")),
                in_territory, cust_status,
            )

            signals.append({
                "date": email_date,
                "source": "burbio",
                "source_detail": "Burbio School Tracker",
                "signal_type": item.get("signal_type", "market_intel"),
                "scope": scope,
                "district": district,
                "state": state,
                "headline": item.get("headline", ""),
                "dollar_amount": item.get("dollar_amount", ""),
                "tier": _signal_tier(item.get("signal_type", "market_intel")),
                "heat_score": heat,
                "urgency": item.get("urgency", "routine"),
                "customer_status": cust_status,
                "url": "",
                "message_id": message_id,
            })

        return signals

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Burbio extraction JSON: {e}")
        return []
    except Exception as e:
        logger.warning(f"Burbio extraction failed: {e}")
        return []


# ─────────────────────────────────────────────
# DOE NEWSLETTER EXTRACTION (Tier 2, Claude)
# ─────────────────────────────────────────────

# Sender → state mapping
DOE_SENDER_TO_STATE = {
    "tn.gov": "TN",
    "ok.gov": "OK",
    "sde.ok.gov": "OK",
    "oksde": "OK",
    "tsin": "TN",
}

DOE_SIGNAL_KEYWORDS = re.compile(
    r'\b(?:computer science|CS |coding|STEM|CTE|career technical|technology|'
    r'bond|grant|funding|hiring|curriculum|AI |artificial intelligence|'
    r'digital learning|EdTech|workforce|Perkins|Title IV|E-Rate)\b',
    re.IGNORECASE,
)


def _detect_doe_state(from_addr: str) -> str:
    """Detect state from DOE newsletter sender address."""
    from_lower = from_addr.lower()
    for pattern, state in DOE_SENDER_TO_STATE.items():
        if pattern in from_lower:
            return state
    return ""


def extract_doe_signals(body: str, state: str, email_date: str = "",
                        subject: str = "", message_id: str = "") -> list:
    """
    Send relevant DOE newsletter sections to Claude Haiku for extraction.
    Only called for emails that pass keyword triage.
    """
    import anthropic

    client = anthropic.Anthropic(timeout=90.0)

    prompt = f"""Extract K-12 buying signals from this {state} state education newsletter.
For each signal, return JSON: {{district, signal_type, headline, dollar_amount, urgency}}
signal_type options: bond, leadership, board_meeting, rfp, hiring, grant, ai_policy, technology, curriculum, enrollment
urgency: "urgent" (deadline ≤14 days), "time_sensitive" (≤30 days), "routine"
If a signal is state-wide (not district-specific), set district to empty string.
Return ONLY a valid JSON array.

Subject: {subject}
Content:
{body[:15000]}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        _track_usage(response)

        text = response.content[0].text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            text = text[start:end + 1]

        items = json.loads(text)
        signals = []
        for item in items:
            district = item.get("district", "")
            sig_type = item.get("signal_type", "market_intel")
            scope = "district" if district else "state"
            in_territory = state.upper() in TERRITORY_STATES_WITH_CA
            cust_status = check_customer_status(district) if district else "new"

            heat = compute_heat_score(
                sig_type, _signal_tier(sig_type),
                in_territory, cust_status,
            )

            signals.append({
                "date": email_date,
                "source": "doe_newsletter",
                "source_detail": f"{state} Dept of Ed",
                "signal_type": sig_type,
                "scope": scope,
                "district": district,
                "state": state,
                "headline": item.get("headline", ""),
                "dollar_amount": item.get("dollar_amount", ""),
                "tier": _signal_tier(sig_type),
                "heat_score": heat,
                "urgency": item.get("urgency", "routine"),
                "customer_status": cust_status,
                "url": "",
                "message_id": message_id,
            })

        return signals

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse DOE extraction JSON: {e}")
        return []
    except Exception as e:
        logger.warning(f"DOE extraction failed: {e}")
        return []


# ─────────────────────────────────────────────
# SIGNAL ENRICHMENT (Tier 3 — deep context)
# ─────────────────────────────────────────────

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"


def enrich_signal(signal: dict) -> dict:
    """
    Deep-enrich a signal with web research + Claude analysis.
    Searches for spending details, CTE/CS relevance, key contacts, timeline.
    Returns the signal dict with added enrichment fields:
      - enrichment_summary: 2-3 sentence CodeCombat-relevant analysis
      - spending_breakdown: what the money is actually for
      - cs_cte_relevance: none / weak / moderate / strong
      - key_contacts: names + titles found
      - recommended_action: specific next step
      - enriched: True
    """
    district = signal.get("district", "") or signal.get("District", "")
    state = signal.get("state", "") or signal.get("State", "")
    sig_type = signal.get("signal_type", "") or signal.get("Signal Type", "")
    headline = signal.get("headline", "") or signal.get("Headline", "")
    dollar = signal.get("dollar_amount", "") or signal.get("Dollar Amount", "")

    if not district or not state:
        signal["enriched"] = False
        signal["enrichment_summary"] = "Cannot enrich: missing district or state"
        return signal

    # Step 1: Web search for details
    search_results = _search_signal_context(district, state, sig_type, dollar)

    if not search_results:
        signal["enriched"] = False
        signal["enrichment_summary"] = "No additional context found via web search"
        return signal

    # Step 2: Claude analysis for CodeCombat relevance
    enrichment = _analyze_signal_relevance(district, state, sig_type, headline,
                                           dollar, search_results)

    signal.update(enrichment)
    signal["enriched"] = True
    return signal


def _search_signal_context(district: str, state: str, sig_type: str,
                           dollar: str) -> str:
    """Search the web for detailed context on a signal. Returns combined text."""
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot enrich signals")
        return ""

    import httpx

    # Build targeted search queries based on signal type
    queries = []
    if sig_type in ("bond", "Bond"):
        queries.append(f'"{district}" bond technology CTE STEM spending breakdown')
        queries.append(f'"{district}" bond {dollar} career technical education computer science')
    elif sig_type in ("leadership", "Leadership"):
        queries.append(f'"{district}" new superintendent priorities technology curriculum')
        queries.append(f'"{district}" superintendent CTE STEM computer science')
    elif sig_type in ("ai_policy", "AI Policy"):
        queries.append(f'"{district}" AI policy committee technology curriculum coding')
    elif sig_type in ("hiring", "Hiring"):
        queries.append(f'"{district}" CTE computer science coding teacher hiring program')
    else:
        queries.append(f'"{district}" {state} technology curriculum CTE computer science')

    combined_text = ""
    for query in queries[:2]:  # Max 2 searches per signal
        try:
            resp = httpx.post(
                SERPER_URL,
                headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=15.0,
            )
            data = resp.json()
            for item in data.get("organic", [])[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                combined_text += f"\n{title}\n{snippet}\n"
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Serper search failed for '{query}': {e}")

    return combined_text[:8000]  # Cap context size


def _analyze_signal_relevance(district: str, state: str, sig_type: str,
                              headline: str, dollar: str,
                              search_context: str) -> dict:
    """
    Use Claude to analyze whether a signal represents a real CodeCombat opportunity.
    Returns enrichment dict.
    """
    import anthropic

    client = anthropic.Anthropic(timeout=90.0)

    prompt = f"""Analyze this K-12 district signal for CodeCombat sales relevance. CodeCombat sells computer science, coding, and AI education curriculum to school districts.

SIGNAL:
- District: {district} ({state})
- Type: {sig_type}
- Headline: {headline}
- Dollar Amount: {dollar}

WEB RESEARCH CONTEXT:
{search_context}

Analyze and return a JSON object with exactly these fields:
- "spending_breakdown": Brief summary of what the money/initiative is actually for (1-2 sentences)
- "cs_cte_relevance": One of "strong", "moderate", "weak", "none"
  - "strong" = explicitly mentions CS, coding, CTE technology pathways, STEM labs, or software curriculum
  - "moderate" = CTE expansion, technology investment, or new programs that could include CS
  - "weak" = device/infrastructure refresh only, or unrelated CTE (automotive, cosmetology)
  - "none" = purely facilities, athletics, or no technology component
- "relevance_reasoning": 1-2 sentences explaining why you rated the relevance this way
- "key_contacts": Any named individuals with titles (technology directors, CTE directors, superintendents). Format: "Name - Title" separated by semicolons. Empty string if none found.
- "timeline": When spending begins or key dates (election date, construction start, etc). Empty if unknown.
- "recommended_action": One specific next step for the sales rep. Be concrete.
- "talking_points": 1-2 specific talking points that reference the signal. What should the rep say in outreach that shows they know about this initiative?

Return ONLY valid JSON. No explanation, no markdown."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        _track_usage(response)

        text = response.content[0].text.strip()
        # Strip markdown fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end + 1]

        result = json.loads(text)
        return {
            "spending_breakdown": result.get("spending_breakdown", ""),
            "cs_cte_relevance": result.get("cs_cte_relevance", "unknown"),
            "relevance_reasoning": result.get("relevance_reasoning", ""),
            "key_contacts": result.get("key_contacts", ""),
            "timeline": result.get("timeline", ""),
            "recommended_action": result.get("recommended_action", ""),
            "talking_points": result.get("talking_points", ""),
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse enrichment JSON: {e}")
        return {"cs_cte_relevance": "unknown", "enrichment_summary": "Claude parse error"}
    except Exception as e:
        logger.warning(f"Signal enrichment failed: {e}")
        return {"cs_cte_relevance": "unknown", "enrichment_summary": f"Error: {e}"}


def enrich_top_signals(signals: list, min_tier: int = 1,
                       max_enrich: int = 10,
                       progress_callback=None) -> list:
    """
    Enrich the top N signals that meet the tier threshold.
    Only enriches territory-matching, district-scoped signals.
    Returns the enriched signals.
    """
    to_enrich = [
        s for s in signals
        if (int(s.get("tier", s.get("Tier", 3))) <= min_tier
            and (s.get("scope", s.get("Scope", "")) == "district")
            and (s.get("state", s.get("State", "")).upper() in TERRITORY_STATES_WITH_CA)
            and not s.get("enriched"))
    ][:max_enrich]

    enriched = []
    for i, sig in enumerate(to_enrich):
        if progress_callback:
            district = sig.get("district", sig.get("District", ""))
            progress_callback(f"Enriching {i+1}/{len(to_enrich)}: {district}...")
        enriched_sig = enrich_signal(sig)
        enriched.append(enriched_sig)
        time.sleep(1)  # Rate limit between enrichments

    return enriched


def format_enriched_signal(sig: dict) -> str:
    """Format an enriched signal for Telegram display."""
    district = sig.get("district", sig.get("District", ""))
    state = sig.get("state", sig.get("State", ""))
    sig_type = sig.get("signal_type", sig.get("Signal Type", ""))
    headline = sig.get("headline", sig.get("Headline", ""))
    dollar = sig.get("dollar_amount", sig.get("Dollar Amount", ""))
    relevance = sig.get("cs_cte_relevance", "unknown")

    relevance_emoji = {
        "strong": "🟢 STRONG",
        "moderate": "🟡 MODERATE",
        "weak": "🔴 WEAK",
        "none": "⚫ NONE",
    }.get(relevance, "❓ UNKNOWN")

    lines = [f"📊 *{district}* ({state})\n"]
    lines.append(f"Signal: {sig_type} | {dollar}" if dollar else f"Signal: {sig_type}")
    lines.append(f"Headline: {headline}")
    lines.append(f"\n*CodeCombat Relevance: {relevance_emoji}*")

    breakdown = sig.get("spending_breakdown", "")
    if breakdown:
        lines.append(f"\n*Spending:* {breakdown}")

    reasoning = sig.get("relevance_reasoning", "")
    if reasoning:
        lines.append(f"*Why:* {reasoning}")

    contacts = sig.get("key_contacts", "")
    if contacts:
        lines.append(f"\n*Contacts:* {contacts}")

    timeline = sig.get("timeline", "")
    if timeline:
        lines.append(f"*Timeline:* {timeline}")

    action = sig.get("recommended_action", "")
    if action:
        lines.append(f"\n*Next step:* {action}")

    talking = sig.get("talking_points", "")
    if talking:
        lines.append(f"\n*Talking points:* {talking}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# JOB POSTING SCANNER (Phase 2 source)
# ─────────────────────────────────────────────

# K-12 indicators in company names
_K12_COMPANY_PATTERNS = re.compile(
    r'school district|public schools|isd\b|cisd\b|cusd\b|usd\b|'
    r'school board|board of education|county schools|city schools|'
    r'independent school|community school|area school|regional school',
    re.IGNORECASE,
)

# Job title patterns that indicate CS/CTE hiring (direct buying signal)
_CS_JOB_PATTERNS = re.compile(
    r'computer science|coding|CS teacher|CTE.*(?:tech|computer|STEM)|'
    r'STEM teacher|STEM coordinator|technology teacher|'
    r'robotics|AI teacher|artificial intelligence.*teacher|'
    r'STEAM coordinator|CTE director|technology director|'
    r'curriculum.*technology|instructional technology',
    re.IGNORECASE,
)

# Job searches to run per state
_JOB_SEARCH_QUERIES = [
    "computer science teacher school district",
    "CTE technology teacher school district",
    "STEM coding teacher school district",
]


def scan_job_postings(states: list = None, hours_old: int = 168,
                      max_per_state: int = 15,
                      progress_callback=None) -> list:
    """
    Scan Indeed for K-12 CS/CTE/STEM job postings in territory states.
    Returns list of signal dicts.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.warning("python-jobspy not installed — skipping job scan")
        return []

    if states is None:
        states = list(TERRITORY_STATES)

    # Map state abbreviations to full names for Indeed search
    abbr_to_name = {v: k.title() for k, v in STATE_NAME_TO_ABBR.items()}

    all_signals = []
    seen_companies = set()  # Dedup by company name per scan

    for state in states:
        state_name = abbr_to_name.get(state, state)
        if progress_callback:
            progress_callback(f"Scanning jobs in {state_name}...")

        for query in _JOB_SEARCH_QUERIES:
            try:
                jobs = scrape_jobs(
                    site_name=["indeed"],
                    search_term=query,
                    location=state_name,
                    results_wanted=max_per_state,
                    hours_old=hours_old,
                    country_indeed="USA",
                )
            except Exception as e:
                logger.warning(f"JobSpy failed for '{query}' in {state_name}: {e}")
                continue

            for _, job in jobs.iterrows():
                company = str(job.get("company", ""))
                title = str(job.get("title", ""))
                location = str(job.get("location", ""))

                # Filter: must be K-12 entity
                if not _K12_COMPANY_PATTERNS.search(company):
                    continue

                # Filter: must be CS/CTE/STEM role
                if not _CS_JOB_PATTERNS.search(title):
                    continue

                # Dedup by company within this scan
                company_key = csv_importer.normalize_name(company)
                if company_key in seen_companies:
                    continue
                seen_companies.add(company_key)

                # Look up district in NCES
                district_state = lookup_district_state(company)
                if not district_state:
                    district_state = state

                cust_status = check_customer_status(company)
                in_territory = district_state.upper() in TERRITORY_STATES_WITH_CA

                heat = compute_heat_score(
                    "hiring", 2, in_territory, cust_status,
                )

                all_signals.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "source": "job_posting",
                    "source_detail": f"Indeed — {state_name}",
                    "signal_type": "hiring",
                    "scope": "district",
                    "district": company,
                    "state": district_state,
                    "headline": f"Hiring: {title}",
                    "dollar_amount": "",
                    "tier": 2,
                    "heat_score": heat,
                    "urgency": "time_sensitive",
                    "customer_status": cust_status,
                    "url": str(job.get("job_url", "")),
                    "message_id": f"job_{company_key}_{datetime.now().strftime('%Y%m')}",
                })

            time.sleep(1)  # Rate limit between searches

    logger.info(f"Job scan: {len(all_signals)} K-12 CS/CTE/STEM postings found across {len(states)} states")
    return all_signals


# ─────────────────────────────────────────────
# BOARDDOCS BOARD MEETING SCRAPER
# ─────────────────────────────────────────────

# Registry of territory districts on BoardDocs.
# Format: {state}/{org_code} → {name, committee_id (auto-discovered if blank)}
BOARDDOCS_DISTRICTS = [
    # Texas
    {"state": "TX", "org_code": "tx/austinisd", "name": "Austin ISD"},
    {"state": "TX", "org_code": "tx/disd", "name": "Dallas ISD"},
    {"state": "TX", "org_code": "tx/fisd", "name": "Friendswood ISD"},
    {"state": "TX", "org_code": "tx/hisd", "name": "Humble ISD"},
    {"state": "TX", "org_code": "tx/rrisd", "name": "Round Rock ISD"},
    # Ohio
    {"state": "OH", "org_code": "oh/columbus", "name": "Columbus City Schools"},
    {"state": "OH", "org_code": "oh/cps", "name": "Cincinnati Public Schools"},
    {"state": "OH", "org_code": "oh/akron", "name": "Akron Public Schools"},
    {"state": "OH", "org_code": "oh/dublin", "name": "Dublin City Schools"},
    # Illinois
    {"state": "IL", "org_code": "il/d365u", "name": "Valley View SD 365U"},
    {"state": "IL", "org_code": "il/oswego308", "name": "Oswego CUSD 308"},
    {"state": "IL", "org_code": "il/ecusd7", "name": "Edwardsville CUSD 7"},
    {"state": "IL", "org_code": "il/d303", "name": "St. Charles CUSD 303"},
    {"state": "IL", "org_code": "il/ccsd21", "name": "CCSD 21"},
    # Pennsylvania
    {"state": "PA", "org_code": "pa/down", "name": "Downingtown Area SD"},
    {"state": "PA", "org_code": "pa/govm", "name": "Governor Mifflin SD"},
    {"state": "PA", "org_code": "pa/ojrsd", "name": "Owen J. Roberts SD"},
    # Connecticut
    {"state": "CT", "org_code": "ct/nhps", "name": "New Haven Public Schools"},
    {"state": "CT", "org_code": "ct/greenwich", "name": "Greenwich Public Schools"},
    {"state": "CT", "org_code": "ct/elsd", "name": "East Lyme SD"},
    # Michigan
    {"state": "MI", "org_code": "mi/lansing", "name": "Lansing SD"},
    {"state": "MI", "org_code": "mi/troysd", "name": "Troy SD"},
    {"state": "MI", "org_code": "mi/bsdmi", "name": "Berkley SD"},
    {"state": "MI", "org_code": "mi/washisd", "name": "Washtenaw ISD"},
    # Indiana
    {"state": "IN", "org_code": "in/sacs", "name": "South Adams Community Schools"},
    # Oklahoma — limited BoardDocs presence, most use different systems
    # Massachusetts, Nevada, Nebraska, Tennessee — search yielded no BoardDocs results
]

# Cache for committee IDs (auto-discovered)
_boarddocs_committee_cache = {}

# Keywords that indicate tech/CS/CTE buying signals in board agendas
_BOARD_TECH_KEYWORDS = re.compile(
    r"\b(?:computer science|coding|STEM|CTE|career.technical|"
    r"technology.(?:replacement|upgrade|adoption|refresh|initiative|investment|plan)|"
    r"software.(?:license|contract|purchase|renewal|platform|subscription)|"
    r"curriculum.(?:adoption|review|implement)|"
    r"1:1\s*device|device.refresh|chromebook|laptop|"
    r"artificial intelligence|AI.(?:policy|committee|guidelines)|"
    r"digital.(?:learning|transformation|literacy)|"
    r"cybersecurity|cyber.security|"
    r"e-?rate|Perkins|Title.IV|ESSER|"
    r"RFP|request.for.proposal|procurement.(?:technology|software))\b",
    re.IGNORECASE,
)

# Keywords that indicate bond/budget signals
_BOARD_BOND_KEYWORDS = re.compile(
    r"\b(?:bond.(?:measure|election|issue|referendum|authorization)|"
    r"capital.improvement|facilities.plan|"
    r"budget.(?:amendment|approval|hearing)|"
    r"technology.budget|tech.budget)\b",
    re.IGNORECASE,
)

_BOARDDOCS_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def _discover_committee_id(org_code: str) -> str:
    """Auto-discover committee_id from a BoardDocs public page."""
    if org_code in _boarddocs_committee_cache:
        return _boarddocs_committee_cache[org_code]

    url = f"https://go.boarddocs.com/{org_code}/Board.nsf/Public"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode()
            match = re.search(r'committeeid="([A-Z0-9]+)"', html)
            if match:
                cid = match.group(1)
                _boarddocs_committee_cache[org_code] = cid
                return cid
    except Exception as e:
        logger.debug(f"BoardDocs discovery failed for {org_code}: {e}")

    return ""


def _fetch_boarddocs_meetings(org_code: str, committee_id: str) -> list:
    """Fetch meeting list from BoardDocs. Returns list of meeting dicts."""
    url = f"https://go.boarddocs.com/{org_code}/Board.nsf/BD-GetMeetingsList?open"
    data = urlencode({"current_committee_id": committee_id}).encode()
    req = urllib.request.Request(url, data=data, headers=_BOARDDOCS_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode()
            if content:
                return json.loads(content)
    except Exception as e:
        logger.debug(f"BoardDocs meeting list failed for {org_code}: {e}")
    return []


def _fetch_boarddocs_agenda(org_code: str, committee_id: str,
                             meeting_id: str) -> str:
    """Fetch full agenda text from a BoardDocs meeting. Returns plain text."""
    url = f"https://go.boarddocs.com/{org_code}/Board.nsf/PRINT-AgendaDetailed"
    data = urlencode({
        "id": meeting_id,
        "current_committee_id": committee_id,
    }).encode()
    req = urllib.request.Request(url, data=data, headers=_BOARDDOCS_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode()
            # Strip HTML tags → plain text
            text = re.sub(r"<[^>]+>", " ", html)
            # Strip HTML entities
            text = text.replace("&nbsp;", " ").replace("&amp;", "&")
            text = text.replace("&lt;", "<").replace("&gt;", ">")
            text = text.replace("&quot;", '"').replace("&#39;", "'")
            text = re.sub(r"&\w+;", " ", text)  # catch remaining entities
            text = re.sub(r"\s+", " ", text).strip()
            return text
    except Exception as e:
        logger.debug(f"BoardDocs agenda fetch failed for {org_code}/{meeting_id}: {e}")
    return ""


def _extract_agenda_signals(agenda_text: str, district_name: str,
                             state: str, meeting_date: str,
                             org_code: str, meeting_id: str) -> list:
    """
    Extract buying signals from board meeting agenda text.
    Produces at most 1 signal per keyword category per meeting to avoid noise.
    """
    meeting_url = f"https://go.boarddocs.com/{org_code}/Board.nsf/goto?open=&id={meeting_id}"
    cust_status = check_customer_status(district_name)
    in_territory = state.upper() in TERRITORY_STATES_WITH_CA

    # Collect best match per signal category (tech vs bond)
    # For tech: group by the matched keyword to avoid duplicates
    tech_matches = {}  # keyword_group → best context
    for match in _BOARD_TECH_KEYWORDS.finditer(agenda_text):
        keyword = match.group(0).lower().strip()
        # Group similar keywords (e.g., all "software.*" matches → "software")
        group = keyword.split()[0] if " " in keyword else keyword
        if group not in tech_matches:
            start = max(0, match.start() - 60)
            end = min(len(agenda_text), match.end() + 100)
            context = agenda_text[start:end].strip()
            tech_matches[group] = context

    bond_found = False
    bond_context = ""
    for match in _BOARD_BOND_KEYWORDS.finditer(agenda_text):
        if not bond_found:
            start = max(0, match.start() - 60)
            end = min(len(agenda_text), match.end() + 100)
            bond_context = agenda_text[start:end].strip()
            bond_found = True

    signals = []

    # Emit up to 3 tech signals per meeting (most distinct keyword groups)
    for i, (group, context) in enumerate(tech_matches.items()):
        if i >= 3:
            break

        signal_type, tier = classify_signal(context)
        if signal_type == "market_intel":
            signal_type = "board_meeting"
            tier = 1

        dollar = extract_dollar_amount(context)
        heat = compute_heat_score(signal_type, tier, in_territory, cust_status)

        # Clean headline
        headline = f"Board agenda ({group}): {context[:120]}"

        signals.append({
            "date": meeting_date,
            "source": "boarddocs",
            "source_detail": f"BoardDocs — {district_name}",
            "signal_type": signal_type,
            "scope": "district",
            "district": district_name,
            "state": state,
            "headline": headline,
            "dollar_amount": dollar,
            "tier": tier,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": meeting_url,
            "message_id": f"bd_{org_code}_{meeting_id}_{group}",
        })

    # Emit at most 1 bond signal per meeting
    if bond_found:
        dollar = extract_dollar_amount(bond_context)
        heat = compute_heat_score("bond", 1, in_territory, cust_status)
        headline = f"Board agenda (bond): {bond_context[:120]}"

        signals.append({
            "date": meeting_date,
            "source": "boarddocs",
            "source_detail": f"BoardDocs — {district_name}",
            "signal_type": "bond",
            "scope": "district",
            "district": district_name,
            "state": state,
            "headline": headline,
            "dollar_amount": dollar,
            "tier": 1,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": meeting_url,
            "message_id": f"bd_{org_code}_{meeting_id}_bond",
        })

    return signals


def scan_board_meetings(days_back: int = 30, progress_callback=None) -> list:
    """
    Scan BoardDocs districts for recent board meeting agendas.
    Extracts tech/CS/CTE/bond buying signals from agenda text.
    Returns list of signal dicts. $0 cost (no Claude calls).
    """
    cutoff = datetime.now() - timedelta(days=days_back)
    cutoff_str = cutoff.strftime("%Y%m%d")

    all_signals = []
    districts_scanned = 0
    meetings_scanned = 0
    districts_failed = 0

    for entry in BOARDDOCS_DISTRICTS:
        district_name = entry["name"]
        state = entry["state"]
        org_code = entry["org_code"]

        try:
            # Discover committee ID
            committee_id = _discover_committee_id(org_code)
            if not committee_id:
                districts_failed += 1
                continue

            # Fetch meetings
            meetings = _fetch_boarddocs_meetings(org_code, committee_id)
            if not meetings:
                districts_failed += 1
                continue

            districts_scanned += 1

            # Filter to recent meetings (skip cancelled)
            recent = [m for m in meetings
                      if m.get("numberdate", "") >= cutoff_str
                      and "cancel" not in m.get("name", "").lower()]

            for meeting in recent[:2]:  # Cap at 2 most recent per district
                meeting_id = meeting.get("unique", "")
                meeting_date_raw = meeting.get("numberdate", "")
                if not meeting_id:
                    continue

                # Format date
                if len(meeting_date_raw) == 8:
                    meeting_date = f"{meeting_date_raw[:4]}-{meeting_date_raw[4:6]}-{meeting_date_raw[6:]}"
                else:
                    meeting_date = datetime.now().strftime("%Y-%m-%d")

                # Fetch agenda
                agenda_text = _fetch_boarddocs_agenda(org_code, committee_id, meeting_id)
                if not agenda_text or len(agenda_text) < 200:
                    continue

                meetings_scanned += 1

                # Extract signals (capped per meeting by _extract_agenda_signals)
                meeting_signals = _extract_agenda_signals(
                    agenda_text, district_name, state, meeting_date,
                    org_code, meeting_id)
                all_signals.extend(meeting_signals)

        except Exception as e:
            districts_failed += 1
            logger.warning(f"BoardDocs error for {district_name}: {e}")

        if progress_callback and districts_scanned % 5 == 0:
            progress_callback(f"BoardDocs: {districts_scanned} districts scanned, "
                            f"{len(all_signals)} signals found")

        time.sleep(0.3)  # Rate limit

    logger.info(f"BoardDocs: {districts_scanned} districts, {meetings_scanned} meetings, "
                f"{len(all_signals)} signals. {districts_failed} failed.")
    return all_signals


# ─────────────────────────────────────────────
# RSS FEED INGESTION
# ─────────────────────────────────────────────

RSS_FEEDS = [
    {
        "name": "K-12 Dive",
        "url": "https://www.k12dive.com/feeds/news/",
        "source_detail": "K-12 Dive",
    },
    {
        "name": "eSchool News",
        "url": "https://www.eschoolnews.com/feed/",
        "source_detail": "eSchool News",
    },
    {
        "name": "CSTA",
        "url": "https://csteachers.org/feed/",
        "source_detail": "CSTA",
    },
]


def process_rss_feeds(since_date: str = "", progress_callback=None) -> list:
    """
    Fetch and process RSS feeds for K-12 buying signals.
    Uses feedparser + existing classify_signal pipeline. No Claude calls ($0).
    Returns list of signal dicts.
    """
    if since_date:
        try:
            since_dt = datetime.strptime(since_date, "%Y-%m-%d")
        except ValueError:
            since_dt = datetime.now() - timedelta(days=7)
    else:
        since_dt = None

    all_signals = []
    total_articles = 0
    feeds_processed = 0

    for feed_config in RSS_FEEDS:
        feed_name = feed_config["name"]
        feed_url = feed_config["url"]
        source_detail = feed_config["source_detail"]

        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            logger.warning(f"RSS fetch failed for {feed_name}: {e}")
            continue

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse error for {feed_name}: {feed.bozo_exception}")
            continue

        feeds_processed += 1
        feed_articles = 0

        for entry in feed.entries:
            # Parse publication date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])

            # Filter by since_date
            if since_dt and pub_date and pub_date < since_dt:
                continue

            title = entry.get("title", "").strip()
            if not title or len(title) < 10:
                continue

            # Build text for classification from title + summary
            summary = entry.get("summary", "")
            # Strip HTML tags from summary
            summary_text = re.sub(r"<[^>]+>", " ", summary).strip()
            summary_text = re.sub(r"\s+", " ", summary_text)[:500]

            text = f"{title} {summary_text}"
            link = entry.get("link", "")

            # Classify
            signal_type, tier = classify_signal(text)

            # Extract district/state and dollar amounts
            district, state = extract_district_and_state(text)
            dollar = extract_dollar_amount(text)

            scope = "district" if district else "national"
            in_territory = state.upper() in TERRITORY_STATES_WITH_CA if state else False
            cust_status = check_customer_status(district)

            heat = compute_heat_score(signal_type, tier, in_territory, cust_status)

            date_str = pub_date.strftime("%Y-%m-%d") if pub_date else datetime.now().strftime("%Y-%m-%d")

            # Use feed URL + entry link as dedup key
            msg_id = f"rss_{source_detail}|{link}"

            all_signals.append({
                "date": date_str,
                "source": "rss_feed",
                "source_detail": source_detail,
                "signal_type": signal_type,
                "scope": scope,
                "district": district,
                "state": state,
                "headline": title[:200],
                "dollar_amount": dollar,
                "tier": tier,
                "heat_score": heat,
                "urgency": "routine",
                "customer_status": cust_status,
                "url": link,
                "message_id": msg_id,
            })

            feed_articles += 1
            total_articles += 1

        if progress_callback:
            progress_callback(f"RSS {feed_name}: {feed_articles} articles processed")

        logger.info(f"RSS {feed_name}: {len(feed.entries)} entries → {feed_articles} signals")

    logger.info(f"RSS feeds: {feeds_processed}/{len(RSS_FEEDS)} feeds → {total_articles} signals")
    return all_signals


# ─────────────────────────────────────────────
# FULL PROCESSING PIPELINE
# ─────────────────────────────────────────────

def process_google_alerts(gas, since_date: str = "",
                          progress_callback=None) -> list:
    """
    Fetch and process all Google Alert digests.
    Returns list of signal dicts.
    """
    query = "from:googlealerts-noreply@google.com"
    if since_date:
        query += f" after:{since_date.replace('-', '/')}"

    all_stories = []
    seen_urls = set()
    page = 0
    total_emails = 0

    while True:
        try:
            result = gas.search_inbox_full(
                query=query,
                max_results=10,
                page_start=page * 10,
                body_limit=65000,
            )
        except Exception as e:
            logger.warning(f"GAS fetch failed for Google Alerts page {page}: {e}")
            break

        emails = result.get("results", [])
        if not emails:
            break

        total_emails += len(emails)

        for email in emails:
            body = email.get("body", "")
            date_str = _parse_email_date(email.get("date", ""))
            msg_id = email.get("message_id", "")

            stories = parse_google_alert(body, date_str, msg_id)
            for story in stories:
                # URL dedup
                url = story.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                all_stories.append(story)

        if progress_callback:
            progress_callback(f"Google Alerts: {total_emails} emails parsed, {len(all_stories)} stories found")

        if not result.get("has_more", False):
            break
        page += 1
        time.sleep(1)  # Be nice to GAS

    # Classify and build signal dicts
    signals = []
    for story in all_stories:
        text = f"{story['title']} {story.get('snippet', '')}"
        signal_type, tier = classify_signal(text)
        district, state = extract_district_and_state(text)
        dollar = extract_dollar_amount(text)

        scope = "district" if district else "national"
        in_territory = state.upper() in TERRITORY_STATES_WITH_CA if state else False
        cust_status = check_customer_status(district)

        heat = compute_heat_score(signal_type, tier, in_territory, cust_status)

        signals.append({
            "date": story["date"],
            "source": "google_alert",
            "source_detail": story.get("keyword", ""),
            "signal_type": signal_type,
            "scope": scope,
            "district": district,
            "state": state,
            "headline": story["title"][:200],
            "dollar_amount": dollar,
            "tier": tier,
            "heat_score": heat,
            "urgency": "routine",
            "customer_status": cust_status,
            "url": story.get("url", ""),
            "message_id": story.get("message_id", ""),
        })

    logger.info(f"Google Alerts: {total_emails} emails → {len(all_stories)} stories → {len(signals)} signals")
    return signals


def process_burbio(gas, since_date: str = "",
                   progress_callback=None) -> list:
    """
    Fetch and process Burbio newsletters via Claude extraction.
    Returns list of signal dicts.
    """
    query = "from:myburbio.com"
    if since_date:
        query += f" after:{since_date.replace('-', '/')}"

    all_signals = []
    page = 0
    total_emails = 0
    processed = 0
    skipped_no_territory = 0

    while True:
        try:
            result = gas.search_inbox_full(
                query=query,
                max_results=20,
                page_start=page * 20,
                body_limit=15000,
            )
        except Exception as e:
            logger.warning(f"GAS fetch failed for Burbio page {page}: {e}")
            break

        emails = result.get("results", [])
        if not emails:
            break

        total_emails += len(emails)

        for email in emails:
            body = email.get("body", "")
            date_str = _parse_email_date(email.get("date", ""))
            msg_id = email.get("message_id", "")

            # Territory pre-filter: check if any territory state mentioned
            if not _has_territory_mention(body):
                skipped_no_territory += 1
                continue

            # Send to Claude for extraction
            signals = extract_burbio_signals(body, date_str, msg_id)
            all_signals.extend(signals)
            processed += 1
            time.sleep(0.5)  # Rate limiting between Claude calls

        if progress_callback:
            progress_callback(f"Burbio: {total_emails} emails, {processed} processed, "
                            f"{len(all_signals)} signals found")

        if not result.get("has_more", False):
            break
        page += 1
        time.sleep(1)

    logger.info(f"Burbio: {total_emails} emails → {processed} processed "
                f"({skipped_no_territory} skipped) → {len(all_signals)} signals")
    return all_signals


def process_doe_newsletters(gas, since_date: str = "",
                            progress_callback=None) -> list:
    """
    Fetch and process DOE newsletters. Two-pass: triage then extract.
    Returns list of signal dicts.
    """
    # Query for known DOE senders
    query = "from:(tn.gov OR ok.gov OR sde.ok.gov)"
    if since_date:
        query += f" after:{since_date.replace('-', '/')}"

    all_signals = []
    page = 0
    total_emails = 0
    flagged = 0

    while True:
        try:
            result = gas.search_inbox_full(
                query=query,
                max_results=20,
                page_start=page * 20,
                body_limit=15000,  # Pass 1: triage on first 15K
            )
        except Exception as e:
            logger.warning(f"GAS fetch failed for DOE page {page}: {e}")
            break

        emails = result.get("results", [])
        if not emails:
            break

        total_emails += len(emails)

        for email in emails:
            body = email.get("body", "")
            subject = email.get("subject", "")
            from_addr = email.get("from", "")
            date_str = _parse_email_date(email.get("date", ""))
            msg_id = email.get("message_id", "")

            state = _detect_doe_state(from_addr)
            if not state:
                continue

            # Keyword triage: does subject or first 15K of body contain signal keywords?
            text_to_check = f"{subject} {body[:15000]}"
            if not DOE_SIGNAL_KEYWORDS.search(text_to_check):
                continue

            flagged += 1
            signals = extract_doe_signals(body, state, date_str, subject, msg_id)
            all_signals.extend(signals)
            time.sleep(0.5)

        if progress_callback:
            progress_callback(f"DOE newsletters: {total_emails} emails, {flagged} flagged, "
                            f"{len(all_signals)} signals found")

        if not result.get("has_more", False):
            break
        page += 1
        time.sleep(1)

    logger.info(f"DOE: {total_emails} emails → {flagged} flagged → {len(all_signals)} signals")
    return all_signals


def _has_territory_mention(text: str) -> bool:
    """Check if text mentions any territory state name, abbreviation, or known district."""
    text_lower = text.lower()

    # Check state names
    for name in ("texas", "illinois", "pennsylvania", "ohio", "michigan",
                 "connecticut", "oklahoma", "massachusetts", "indiana",
                 "nevada", "tennessee", "nebraska", "california"):
        if name in text_lower:
            return True

    # Check common city/district mentions from territory
    territory_markers = (
        "dallas", "houston", "austin", "san antonio",  # TX
        "chicago", "springfield il",  # IL
        "philadelphia", "pittsburgh",  # PA
        "columbus", "cleveland", "cincinnati",  # OH
        "detroit", "grand rapids",  # MI
        "hartford", "new haven",  # CT
        "oklahoma city", "tulsa",  # OK
        "boston", "worcester",  # MA
        "indianapolis",  # IN
        "las vegas", "reno",  # NV
        "nashville", "memphis",  # TN
        "omaha", "lincoln ne",  # NE
        "los angeles", "san diego",  # CA SoCal
    )
    for marker in territory_markers:
        if marker in text_lower:
            return True

    # Check 2-letter state abbreviations with word boundaries
    for abbr in TERRITORY_STATES:
        if re.search(rf'\b{abbr}\b', text):
            return True

    return False


def _parse_email_date(date_str: str) -> str:
    """Parse various email date formats into YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    # Try common formats
    for fmt in (
        "%a %b %d %Y %H:%M:%S",       # Mon Apr 01 2026 09:00:00
        "%a, %d %b %Y %H:%M:%S %z",    # Mon, 01 Apr 2026 09:00:00 +0000
        "%Y-%m-%d",                      # 2026-04-01
        "%m/%d/%Y",                      # 04/01/2026
    ):
        try:
            return datetime.strptime(date_str[:30].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback: try to find a date-like pattern
    date_match = re.search(r'(\w+ \d+ \d{4})', date_str)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    return datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# CLUSTER DETECTION
# ─────────────────────────────────────────────

def detect_clusters(signals: list) -> dict:
    """
    Group signals by district and compute cluster scores.
    Returns {district_key: {district, state, signals: list, cluster_score: int}}.
    """
    by_district = defaultdict(list)
    for sig in signals:
        district = sig.get("district", "")
        if not district:
            continue
        key = csv_importer.normalize_name(district)
        by_district[key].append(sig)

    clusters = {}
    for key, sigs in by_district.items():
        if len(sigs) < 2:
            continue
        # Use the most common state
        states = [s.get("state", "") for s in sigs if s.get("state")]
        state = max(set(states), key=states.count) if states else ""

        # Recompute heat with cluster bonus
        best_heat = 0
        for sig in sigs:
            heat = compute_heat_score(
                sig.get("signal_type", "market_intel"),
                sig.get("tier", 3),
                sig.get("state", "").upper() in TERRITORY_STATES_WITH_CA,
                sig.get("customer_status", "new"),
                cluster_count=len(sigs),
            )
            best_heat = max(best_heat, heat)

        clusters[key] = {
            "district": sigs[0].get("district", ""),
            "state": state,
            "signals": sigs,
            "cluster_score": best_heat,
            "count": len(sigs),
        }

    return clusters


# ─────────────────────────────────────────────
# ORCHESTRATORS
# ─────────────────────────────────────────────

def process_all_signals(gas, progress_callback=None) -> dict:
    """
    Full batch processing: all Google Alerts + Burbio + DOE newsletters.
    Returns summary dict.
    """
    _reset_cost()
    global _cross_ref_cache
    _cross_ref_cache = None  # Force fresh load

    if progress_callback:
        progress_callback("Loading NCES district lookup + cross-reference data...")
    _load_nces_lookup()
    _load_cross_references()

    all_signals = []

    # Source 1: Google Alerts (programmatic, $0)
    if progress_callback:
        progress_callback("Scanning Google Alerts...")
    alert_signals = process_google_alerts(gas, progress_callback=progress_callback)
    all_signals.extend(alert_signals)

    # Source 2: Burbio newsletters (Claude extraction)
    if progress_callback:
        progress_callback("Scanning Burbio newsletters...")
    burbio_signals = process_burbio(gas, progress_callback=progress_callback)
    all_signals.extend(burbio_signals)

    # Source 3: DOE newsletters (two-pass)
    if progress_callback:
        progress_callback("Scanning DOE newsletters...")
    doe_signals = process_doe_newsletters(gas, progress_callback=progress_callback)
    all_signals.extend(doe_signals)

    # Source 4: Job postings (Indeed via JobSpy)
    if progress_callback:
        progress_callback("Scanning job postings...")
    job_signals = scan_job_postings(progress_callback=progress_callback)
    all_signals.extend(job_signals)

    # Source 5: RSS feeds (programmatic, $0)
    if progress_callback:
        progress_callback("Scanning RSS feeds...")
    rss_signals = process_rss_feeds(progress_callback=progress_callback)
    all_signals.extend(rss_signals)

    # Source 6: BoardDocs board meeting agendas (programmatic, $0)
    board_signals = []
    try:
        if progress_callback:
            progress_callback("Scanning BoardDocs agendas...")
        board_signals = scan_board_meetings(days_back=30,
                                             progress_callback=progress_callback)
        all_signals.extend(board_signals)
    except Exception as e:
        logger.warning(f"BoardDocs scan failed (non-fatal): {e}")

    # Detect clusters
    clusters = detect_clusters(all_signals)

    # Update heat scores for clustered signals
    for key, cluster in clusters.items():
        for sig in cluster["signals"]:
            sig["heat_score"] = compute_heat_score(
                sig.get("signal_type", "market_intel"),
                sig.get("tier", 3),
                sig.get("state", "").upper() in TERRITORY_STATES_WITH_CA,
                sig.get("customer_status", "new"),
                cluster_count=cluster["count"],
            )

    # Write to sheet
    if progress_callback:
        progress_callback("Writing signals to database...")
    write_result = write_signals(all_signals)

    # Build summary
    territory_signals = [s for s in all_signals
                         if s.get("state", "").upper() in TERRITORY_STATES_WITH_CA
                         and s.get("scope") == "district"]
    tier1 = [s for s in territory_signals if s.get("tier") == 1]

    # Auto-enrich Tier 1 territory signals
    enriched_signals = []
    if tier1 and SERPER_API_KEY:
        if progress_callback:
            progress_callback(f"Enriching {min(len(tier1), 10)} Tier 1 signals...")
        enriched_signals = enrich_top_signals(
            tier1, min_tier=1, max_enrich=10,
            progress_callback=progress_callback)

    # Separate enriched signals by relevance
    strong = [s for s in enriched_signals if s.get("cs_cte_relevance") == "strong"]
    moderate = [s for s in enriched_signals if s.get("cs_cte_relevance") == "moderate"]

    summary = {
        "total_signals": len(all_signals),
        "written": write_result["written"],
        "skipped_dedup": write_result["skipped"],
        "alert_signals": len(alert_signals),
        "burbio_signals": len(burbio_signals),
        "doe_signals": len(doe_signals),
        "job_signals": len(job_signals),
        "rss_signals": len(rss_signals),
        "board_signals": len(board_signals),
        "territory_district_signals": len(territory_signals),
        "tier1_signals": len(tier1),
        "clusters": len(clusters),
        "unique_districts": len(set(s.get("district", "") for s in all_signals if s.get("district"))),
        "cost": round(_get_cost(), 2),
        "top_signals": sorted(territory_signals, key=lambda s: s.get("heat_score", 0), reverse=True)[:10],
        "cluster_list": sorted(clusters.values(), key=lambda c: c["cluster_score"], reverse=True)[:5],
        "enriched_count": len(enriched_signals),
        "strong_signals": strong,
        "moderate_signals": moderate,
    }

    logger.info(f"Signal scan complete: {summary['total_signals']} total, "
                f"{summary['territory_district_signals']} territory, "
                f"{len(enriched_signals)} enriched ({len(strong)} strong), "
                f"${summary['cost']:.2f} cost")

    return summary


def process_new_signals(gas, since_date: str = None,
                        progress_callback=None) -> dict:
    """
    Incremental scan: only process emails since last scan date.
    Returns same summary dict as process_all_signals.
    """
    if not since_date:
        # Default: last 2 days
        since_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    _reset_cost()
    global _cross_ref_cache
    _cross_ref_cache = None

    _load_nces_lookup()
    _load_cross_references()

    all_signals = []

    alert_signals = process_google_alerts(gas, since_date=since_date,
                                          progress_callback=progress_callback)
    all_signals.extend(alert_signals)

    burbio_signals = process_burbio(gas, since_date=since_date,
                                    progress_callback=progress_callback)
    all_signals.extend(burbio_signals)

    doe_signals = process_doe_newsletters(gas, since_date=since_date,
                                          progress_callback=progress_callback)
    all_signals.extend(doe_signals)

    rss_signals = process_rss_feeds(since_date=since_date,
                                     progress_callback=progress_callback)
    all_signals.extend(rss_signals)

    board_signals = []
    try:
        board_signals = scan_board_meetings(days_back=7,
                                             progress_callback=progress_callback)
        all_signals.extend(board_signals)
    except Exception as e:
        logger.warning(f"BoardDocs scan failed (non-fatal): {e}")

    clusters = detect_clusters(all_signals)
    write_result = write_signals(all_signals)

    territory_signals = [s for s in all_signals
                         if s.get("state", "").upper() in TERRITORY_STATES_WITH_CA
                         and s.get("scope") == "district"]
    tier1 = [s for s in territory_signals if s.get("tier") == 1]

    # Auto-enrich new Tier 1 signals
    enriched_signals = []
    if tier1 and SERPER_API_KEY:
        if progress_callback:
            progress_callback(f"Enriching {min(len(tier1), 5)} Tier 1 signals...")
        enriched_signals = enrich_top_signals(
            tier1, min_tier=1, max_enrich=5,
            progress_callback=progress_callback)

    strong = [s for s in enriched_signals if s.get("cs_cte_relevance") == "strong"]

    return {
        "total_signals": len(all_signals),
        "written": write_result["written"],
        "skipped_dedup": write_result["skipped"],
        "alert_signals": len(alert_signals),
        "burbio_signals": len(burbio_signals),
        "doe_signals": len(doe_signals),
        "rss_signals": len(rss_signals),
        "board_signals": len(board_signals),
        "territory_district_signals": len(territory_signals),
        "tier1_signals": len(tier1),
        "clusters": len(clusters),
        "cost": round(_get_cost(), 2),
        "enriched_count": len(enriched_signals),
        "strong_signals": strong,
    }


# ─────────────────────────────────────────────
# TELEGRAM FORMATTING
# ─────────────────────────────────────────────

_SIGNAL_TYPE_TAGS = {
    "bond": "BOND", "leadership": "LEADER", "rfp": "RFP",
    "board_meeting": "BOARD", "ai_policy": "AI", "hiring": "HIRE",
    "grant": "GRANT", "technology": "TECH", "curriculum": "CURRIC",
    "enrollment": "ENROLL", "market_intel": "INTEL",
}


def format_hot_signals(limit: int = 5, state_filter: str = "",
                       territory_only: bool = True) -> str:
    """Format top signals for Telegram display. Territory-only by default."""
    signals = get_active_signals(state_filter=state_filter, scope_filter="district")

    # Default: filter to territory states only
    if territory_only and not state_filter:
        signals = [s for s in signals
                   if s.get("State", "").upper() in TERRITORY_STATES_WITH_CA]

    if not signals:
        return "No active district signals found."

    new_count = sum(1 for s in signals if s.get("Status") == "new")
    total = len(signals)

    lines = [f"🔥 *Hot Signals* ({total} active, {new_count} new)\n"]

    for i, sig in enumerate(signals[:limit], 1):
        tag = _SIGNAL_TYPE_TAGS.get(sig.get("Signal Type", ""), "SIG")
        district = sig.get("District", "Unknown")
        state = sig.get("State", "")
        headline = sig.get("Headline", "")[:60]
        heat = sig.get("effective_heat", 0)
        status_marker = ""

        if sig.get("Status") == "new":
            status_marker = " | 🆕 new"
        elif sig.get("days_old", 0) <= 14:
            status_marker = " | recent"

        district_display = f"{district} ({state})" if state else district
        lines.append(f"{i}. [{tag}] *{district_display}* — {headline}")
        lines.append(f"   Heat: {heat}{status_marker}")

    if total > limit:
        lines.append(f"\n... showing top {limit} of {total}. `/signals all` for full list.")

    lines.append(f"\n`/signal_act N` to research | `/signal_info N` for detail")

    return "\n".join(lines)


def format_signal_detail(signal: dict, related: list = None) -> str:
    """Format a single signal with full detail for Telegram."""
    district = signal.get("District", "Unknown")
    state = signal.get("State", "")
    heat = signal.get("effective_heat", signal.get("Heat Score", 0))
    sig_type = signal.get("Signal Type", "")
    headline = signal.get("Headline", "")
    dollar = signal.get("Dollar Amount", "")
    cust = signal.get("Customer Status", "new")
    source = signal.get("Source", "")
    date = signal.get("Date Detected", "")
    urgency = signal.get("Urgency", "routine")

    lines = [f"📊 *{district}* ({state}) — Heat Score: {heat}\n"]

    if urgency == "urgent":
        lines.append("⚡ URGENT — time-sensitive opportunity\n")
    elif urgency == "time_sensitive":
        lines.append("⏰ Time-sensitive signal\n")

    lines.append(f"Signal: {sig_type} | Tier: {signal.get('Tier', '')}")
    lines.append(f"Date: {date} | Source: {source}")
    if headline:
        lines.append(f"Detail: {headline}")
    if dollar:
        lines.append(f"Amount: {dollar}")

    # Customer status
    status_map = {
        "active": "✅ Active customer",
        "pipeline": "📋 In pipeline",
        "closed_lost": "🔄 Closed-lost (winback)",
        "prospect": "🎯 Already in prospect queue",
        "new": "🆕 New — not yet in system",
    }
    lines.append(f"\nStatus: {status_map.get(cust, cust)}")

    # Related signals (cluster)
    if related:
        lines.append(f"\n*Cluster:* {len(related) + 1} signals for this district:")
        for r in related[:5]:
            tag = _SIGNAL_TYPE_TAGS.get(r.get("Signal Type", ""), "SIG")
            lines.append(f"  [{tag}] {r.get('Headline', '')[:50]} ({r.get('Date Detected', '')})")

    url = signal.get("Source URL", "")
    if url:
        lines.append(f"\n🔗 {url}")

    return "\n".join(lines)


def format_scan_summary(summary: dict) -> str:
    """Format scan results for Telegram notification."""
    lines = ["📊 *Signal Scan Complete*\n"]
    lines.append(f"Total: {summary['total_signals']} signals found")
    lines.append(f"  📰 Google Alerts: {summary['alert_signals']}")
    lines.append(f"  📋 Burbio: {summary['burbio_signals']}")
    lines.append(f"  🏛️ DOE: {summary['doe_signals']}")
    if summary.get("job_signals"):
        lines.append(f"  💼 Job postings: {summary['job_signals']}")
    if summary.get("rss_signals"):
        lines.append(f"  📡 RSS feeds: {summary['rss_signals']}")
    if summary.get("board_signals"):
        lines.append(f"  🏛 BoardDocs: {summary['board_signals']}")

    lines.append(f"\n🎯 Territory signals: {summary['territory_district_signals']}")
    lines.append(f"  🔴 Tier 1 (act now): {summary['tier1_signals']}")

    if summary.get("clusters"):
        lines.append(f"  🔥 Clusters: {summary['clusters']} multi-signal districts")

    # Top signals
    top = summary.get("top_signals", [])
    if top:
        lines.append("\n*Top Signals:*")
        for i, sig in enumerate(top[:5], 1):
            tag = _SIGNAL_TYPE_TAGS.get(sig.get("signal_type", ""), "SIG")
            district = sig.get("district", "Unknown")
            state = sig.get("state", "")
            headline = sig.get("headline", "")[:50]
            heat = sig.get("heat_score", 0)
            lines.append(f"  {i}. [{tag}] {district} ({state}) — {headline} (heat: {heat})")

    # Enrichment results
    enriched_count = summary.get("enriched_count", 0)
    if enriched_count:
        strong = summary.get("strong_signals", [])
        lines.append(f"\n🔍 *Enriched:* {enriched_count} Tier 1 signals analyzed")
        if strong:
            lines.append(f"  🟢 *STRONG relevance ({len(strong)}):*")
            for s in strong[:3]:
                dist = s.get("district", "")
                st = s.get("state", "")
                action = s.get("recommended_action", "")[:60]
                lines.append(f"    {dist} ({st}) — {action}")
        moderate = summary.get("moderate_signals", [])
        if moderate:
            lines.append(f"  🟡 Moderate: {len(moderate)} districts")

    lines.append(f"\nWritten: {summary['written']} | Deduped: {summary['skipped_dedup']}")
    lines.append(f"Cost: ${summary['cost']:.2f}")
    lines.append(f"\nUse `/signals` to review | `/signal_enrich N` for deep analysis")

    return "\n".join(lines)


def build_signal_brief_block() -> str:
    """Build data block for morning brief injection."""
    try:
        signals = get_active_signals(scope_filter="district")
        if not signals:
            return ""

        new_signals = [s for s in signals if s.get("Status") == "new"]
        territory = [s for s in signals
                     if s.get("State", "").upper() in TERRITORY_STATES_WITH_CA]

        lines = ["SIGNAL INTELLIGENCE DATA:"]
        if new_signals:
            lines.append(f"New signals (unreviewed): {len(new_signals)}")
            for sig in new_signals[:3]:
                district = sig.get("District", "")
                state = sig.get("State", "")
                headline = sig.get("Headline", "")[:60]
                heat = sig.get("effective_heat", 0)
                lines.append(f"  - {district} ({state}): {headline} (heat: {heat})")

        # Signal of the day (highest heat)
        if territory:
            top = territory[0]
            lines.append(f"SIGNAL OF THE DAY: {top.get('District', '')} ({top.get('State', '')}) — "
                        f"{top.get('Headline', '')[:80]} (heat: {top.get('effective_heat', 0)})")

        lines.append(f"Total active territory signals: {len(territory)}")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Failed to build signal brief block: {e}")
        return ""
