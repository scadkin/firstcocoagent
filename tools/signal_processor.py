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
    "Source",           # google_alert / burbio / doe_newsletter / rss_feed / job_posting / boarddocs / ballotpedia / manual
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
    "Pipeline Link",    # Prospect name key — links signal to deal in Prospecting Queue/Pipeline
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
            "",  # Pipeline Link (populated when signal leads to deal)
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


def link_signal_to_prospect(signal_id: str, prospect_name: str) -> bool:
    """Set the Pipeline Link column on a signal to the prospect/district name."""
    try:
        service, sheet_id = _ensure_tab()
        last_col = _col_letter(NUM_COLS - 1)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_SIGNALS}'!A2:{last_col}",
        ).execute()
        rows = result.get("values", [])

        link_col_idx = SIGNAL_COLUMNS.index("Pipeline Link")
        for i, row in enumerate(rows):
            if row and row[0] == signal_id:
                row_num = i + 2
                col_letter = _col_letter(link_col_idx)
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=f"'{TAB_SIGNALS}'!{col_letter}{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[prospect_name]]},
                ).execute()
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to link signal to prospect: {e}")
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

# ─────────────────────────────────────────────
# KILL SWITCHES — flip to False to disable a scanner without deleting code
# ─────────────────────────────────────────────
ENABLE_FUNDING_SCAN = True       # F4: scan_cs_funding_awards
ENABLE_COMPETITOR_SCAN = True    # F2: scan_competitor_displacement


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

# Keywords that indicate superintendent leadership changes
_BOARD_LEADERSHIP_KEYWORDS = re.compile(
    r"\b(?:superintendent.(?:search|resignation|retirement|appointment|hire|vacancy|transition)|"
    r"interim.superintendent)\b",
    re.IGNORECASE,
)

# False positive patterns — reject BoardDocs tech matches near these words
_BOARD_FALSE_POSITIVE = re.compile(
    r"\b(?:wheelchair|accessible|ada.compliance|food.service|janitorial|custodial|"
    r"transportation|bus.route|mowing|lawn|snow.removal|roofing|hvac|plumbing|"
    r"expo|fair|night|family.night|showcase|sponsorship|donation|"
    r"athletic|stadium|scoreboard|playground|gymnasium)\b",
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
    tech_matches = {}  # keyword_group → (keyword_text, trailing_context)
    for match in _BOARD_TECH_KEYWORDS.finditer(agenda_text):
        keyword = match.group(0).strip()
        # Group similar keywords (e.g., all "software.*" matches → "software")
        group = keyword.lower().split()[0] if " " in keyword.lower() else keyword.lower()
        if group not in tech_matches:
            # Grab text AFTER the match for readable context
            trailing = agenda_text[match.end():match.end() + 150].strip()
            # Clean up: start at first word boundary
            trailing = re.sub(r"^\W+", "", trailing)
            # Reject false positives (wheelchair RFPs, STEM Expo, etc.)
            context = agenda_text[max(0, match.start() - 50):match.end() + 150]
            if _BOARD_FALSE_POSITIVE.search(context):
                continue
            tech_matches[group] = (keyword, trailing)

    bond_found = False
    bond_keyword = ""
    bond_trailing = ""
    for match in _BOARD_BOND_KEYWORDS.finditer(agenda_text):
        if not bond_found:
            bond_keyword = match.group(0).strip()
            trailing = agenda_text[match.end():match.end() + 150].strip()
            bond_trailing = re.sub(r"^\W+", "", trailing)
            bond_found = True

    signals = []

    # Emit up to 3 tech signals per meeting (most distinct keyword groups)
    for i, (group, (keyword, trailing)) in enumerate(tech_matches.items()):
        if i >= 3:
            break

        full_text = f"{keyword} {trailing}"
        signal_type, tier = classify_signal(full_text)
        if signal_type == "market_intel":
            signal_type = "board_meeting"
            tier = 1

        dollar = extract_dollar_amount(full_text)
        heat = compute_heat_score(signal_type, tier, in_territory, cust_status)

        # Clean, readable headline
        headline = f"Board: {keyword} — {trailing[:120]}"

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
        full_text = f"{bond_keyword} {bond_trailing}"
        dollar = extract_dollar_amount(full_text)
        heat = compute_heat_score("bond", 1, in_territory, cust_status)
        headline = f"Board: {bond_keyword} — {bond_trailing[:120]}"

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

    # Emit at most 1 leadership signal per meeting
    leadership_match = _BOARD_LEADERSHIP_KEYWORDS.search(agenda_text)
    if leadership_match:
        ldr_keyword = leadership_match.group(0).strip()
        ldr_trailing = agenda_text[leadership_match.end():leadership_match.end() + 150].strip()
        ldr_trailing = re.sub(r"^\W+", "", ldr_trailing)
        heat = compute_heat_score("board_meeting", 1, in_territory, cust_status)
        headline = f"Board: {ldr_keyword} — {ldr_trailing[:120]}"
        signals.append({
            "date": meeting_date,
            "source": "boarddocs",
            "source_detail": f"BoardDocs — {district_name}",
            "signal_type": "board_meeting",
            "scope": "district",
            "district": district_name,
            "state": state,
            "headline": headline,
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": meeting_url,
            "message_id": f"bd_{org_code}_{meeting_id}_leadership",
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
# BALLOTPEDIA BOND TRACKING
# ─────────────────────────────────────────────

_BALLOTPEDIA_URL = "https://ballotpedia.org/Local_school_bonds_on_the_ballot"

# Regex to parse Ballotpedia bond list entries
# Format: "District Name, State, Measure Details (Month Year)" + result icon or "On the ballot"
_BALLOT_ENTRY_RE = re.compile(
    r'<a[^>]*href="(/[^"]+)"[^>]*>([^<]+)</a>'
    r'[^<]*(?:<img[^>]*alt="([^"]*)"[^>]*/?>)?'
    r'|On the ballot',
    re.IGNORECASE,
)

# Parse district + state + date from measure title
_BALLOT_TITLE_RE = re.compile(
    r'^(.+?),\s*([A-Za-z\s]+?),\s*(.+?)\s*\((\w+\s+\d{4})\)\s*$'
)


def scan_ballotpedia(progress_callback=None) -> list:
    """
    Scrape Ballotpedia for school bond measures in territory states.
    Parses both 2025 (with results) and 2026 (upcoming) sections.
    Returns list of signal dicts. $0 cost (no Claude calls).
    """
    all_signals = []

    try:
        req = urllib.request.Request(_BALLOTPEDIA_URL, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode()
    except Exception as e:
        logger.warning(f"Ballotpedia fetch failed: {e}")
        return []

    # Parse <li> items with bond measure links (multiline HTML)
    li_pattern = re.compile(
        r'<li>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        r'\s*(?:<img[^>]*alt="([^"]*)"[^>]*/?>)?\s*'
        r'(.*?)\s*</li>',
        re.DOTALL,
    )

    for match in li_pattern.finditer(html):
        href = match.group(1).strip()
        title = match.group(2).strip()
        result_icon = (match.group(3) or "").strip()
        trailing = (match.group(4) or "").strip()

        # Parse: "District, State, Measure Details (Month Year)"
        title_match = _BALLOT_TITLE_RE.match(title)
        if not title_match:
            continue

        district = title_match.group(1).strip()
        state_name = title_match.group(2).strip().lower()
        measure_detail = title_match.group(3).strip()
        date_str = title_match.group(4).strip()

        state_abbr = STATE_NAME_TO_ABBR.get(state_name, "")
        if not state_abbr or state_abbr not in TERRITORY_STATES:
            continue  # Use TERRITORY_STATES (no CA) — CA has thousands of bonds

        # Only include recent measures (2025-2026)
        if not any(yr in date_str for yr in ("2025", "2026")):
            continue

        # Determine result from icon alt text or trailing text
        if "approved" in result_icon.lower() or "yes" in result_icon.lower():
            result = "passed"
            urgency = "urgent"
        elif "defeated" in result_icon.lower() or "no" in result_icon.lower():
            result = "failed"
            urgency = "routine"
        elif "on the ballot" in trailing.lower():
            result = "upcoming"
            urgency = "time_sensitive"
        else:
            result = "unknown"
            urgency = "time_sensitive"

        dollar = extract_dollar_amount(measure_detail + " " + title)

        if result == "passed":
            headline = f"Bond PASSED: {district} — {measure_detail}"
        elif result == "failed":
            headline = f"Bond failed: {district} — {measure_detail}"
        elif result == "upcoming":
            headline = f"Bond vote {date_str}: {district} — {measure_detail}"
        else:
            headline = f"Bond measure: {district} — {measure_detail}"

        cust_status = check_customer_status(district)
        heat = compute_heat_score("bond", 1, True, cust_status)
        if result == "passed":
            heat = min(100, heat + 15)

        msg_id = f"ballot_{state_abbr}_{district}_{date_str}".replace(" ", "_")

        all_signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "ballotpedia",
            "source_detail": f"Ballotpedia — {date_str}",
            "signal_type": "bond",
            "scope": "district",
            "district": district,
            "state": state_abbr,
            "headline": headline[:200],
            "dollar_amount": dollar,
            "tier": 1,
            "heat_score": heat,
            "urgency": urgency,
            "customer_status": cust_status,
            "url": href,
            "message_id": msg_id,
        })

    # Deduplicate within batch (Ballotpedia lists measures in multiple sections)
    seen = set()
    deduped = []
    for sig in all_signals:
        if sig["message_id"] not in seen:
            seen.add(sig["message_id"])
            deduped.append(sig)

    logger.info(f"Ballotpedia: {len(deduped)} territory bond measures "
                f"({len(all_signals) - len(deduped)} dupes removed)")
    if progress_callback:
        progress_callback(f"Ballotpedia: {len(deduped)} territory bond measures")
    return deduped


# ─────────────────────────────────────────────
# LEADERSHIP CHANGE SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# SUPERINTENDENT DIRECTORY (persistent in GitHub memory)
# ─────────────────────────────────────────────

_SUPERINTENDENT_DIR_PATH = "memory/superintendent_directory.json"
_superintendent_directory: dict | None = None


def _load_superintendent_directory() -> dict:
    """Load superintendent directory from GitHub memory. Cached in module."""
    global _superintendent_directory
    if _superintendent_directory is not None:
        return _superintendent_directory
    try:
        import tools.github_pusher as github_pusher
        raw = github_pusher.get_file_content(_SUPERINTENDENT_DIR_PATH)
        if raw:
            _superintendent_directory = json.loads(raw)
        else:
            _superintendent_directory = {}
    except Exception as e:
        logger.warning(f"Superintendent directory load failed: {e}")
        _superintendent_directory = {}
    return _superintendent_directory


def _save_superintendent_directory() -> bool:
    """Persist directory to GitHub memory."""
    global _superintendent_directory
    if _superintendent_directory is None:
        return False
    try:
        import tools.github_pusher as github_pusher
        content = json.dumps(_superintendent_directory, indent=2, sort_keys=True)
        github_pusher.push_file(
            _SUPERINTENDENT_DIR_PATH,
            content,
            commit_message="Update superintendent directory",
        )
        return True
    except Exception as e:
        logger.error(f"Superintendent directory save failed: {e}")
        return False


def get_superintendent(district_name: str) -> dict | None:
    """Lookup superintendent by district name. Returns entry dict or None."""
    if not district_name:
        return None
    directory = _load_superintendent_directory()
    key = csv_importer.normalize_name(district_name)
    return directory.get(key)


def update_superintendent_directory(items: list[dict]) -> dict:
    """
    Upsert district→superintendent entries from leadership scan results.
    Detects real person-name changes (logs a change event in returned dict).
    Returns {added, updated, changed, total}.
    """
    directory = _load_superintendent_directory()
    added = 0
    updated = 0
    changed = []
    today = datetime.now().strftime("%Y-%m-%d")

    for item in items:
        district = (item.get("district") or "").strip()
        person = (item.get("person_name") or "").strip()
        state = (item.get("state") or "").strip().upper()
        change_type = (item.get("change_type") or "").strip().lower()

        if not district or not person:
            continue

        key = csv_importer.normalize_name(district)
        existing = directory.get(key)

        if not existing:
            directory[key] = {
                "name": person,
                "state": state,
                "change_type": change_type,
                "updated": today,
                "source": "leadership_scan",
            }
            added += 1
        else:
            existing_name_norm = existing.get("name", "").strip().lower()
            if existing_name_norm and existing_name_norm != person.lower():
                changed.append({
                    "district": district,
                    "previous": existing.get("name", ""),
                    "current": person,
                })
            directory[key] = {
                "name": person,
                "state": state or existing.get("state", ""),
                "change_type": change_type or existing.get("change_type", ""),
                "updated": today,
                "source": "leadership_scan",
            }
            updated += 1

    if added or updated:
        _save_superintendent_directory()

    return {
        "added": added,
        "updated": updated,
        "changed": changed,
        "total": len(directory),
    }


def scan_leadership_changes(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 superintendent changes across territory states via Serper web search.
    Uses Claude Haiku to extract structured data from search results.
    Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan leadership changes")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)  # No CA — too noisy
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for superintendent changes...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"superintendent" ("hired" OR "appointed" OR "named" OR "resigned" OR "retired") "{state_name}" school district',
            f'"superintendent" ("search" OR "vacancy" OR "interim") "{state_name}" school district',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper leadership search failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Leadership scan: no search results found")
        if progress_callback:
            progress_callback("No superintendent changes found in search results.")
        return []

    logger.info(f"Leadership scan: {len(all_snippets)} unique articles from {len(scan_states)} states")

    # Build combined text for Claude extraction
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]  # Cap context size

    if progress_callback:
        progress_callback(f"Extracting leadership changes from {len(all_snippets)} articles...")

    # Single Claude Haiku call for all results
    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district superintendent changes from these search results.

IMPORTANT:
- Only include K-12 public school district superintendents
- EXCLUDE: police superintendents, public works superintendents, university/college leaders, state education commissioners, private school leaders
- Only include actual changes (hired, appointed, resigned, retired, interim named, search announced)
- Do NOT include routine news about sitting superintendents (statements, policy updates, etc.)

Return a JSON array. Each item:
{{
  "district": "District Name",
  "state": "XX",
  "person_name": "Dr. Jane Smith",
  "change_type": "hired|appointed|resigned|retired|interim|search",
  "headline": "One sentence describing the change"
}}

If no superintendent changes found, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude leadership extraction failed: {e}")
        return []

    # Parse JSON — strip markdown fences and preamble
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning(f"Leadership extraction: no JSON array found in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Leadership extraction JSON parse failed: {e}")
        return []

    # Post-process extracted items
    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    # Build URL lookup by (title snippet) for source_detail
    url_by_district = {}
    for s in all_snippets:
        title_lower = s["title"].lower()
        for item in items:
            dist_lower = item.get("district", "").lower()
            if dist_lower and dist_lower in title_lower:
                url_by_district[dist_lower] = s["url"]

    for item in items:
        district = item.get("district", "").strip()
        state = item.get("state", "").strip().upper()
        change_type = item.get("change_type", "").strip().lower()
        headline = item.get("headline", "").strip()

        if not district or not state or not change_type:
            continue

        # Validate state is in territory
        if state not in TERRITORY_STATES_WITH_CA:
            continue

        # NCES lookup for validation/correction
        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Dedup within scan by (district, change_type)
        norm_district = csv_importer.normalize_name(district)
        dedup_key = (norm_district, change_type)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        # Customer relationship check
        cust_status = check_customer_status(district)

        # Urgency based on relationship
        urgency = "urgent" if cust_status == "active" else "time_sensitive"

        # Heat score
        heat = compute_heat_score("leadership", 1, True, cust_status)

        # Message ID for cross-scan dedup (monthly granularity)
        msg_id = f"leadership_{norm_district}_{change_type}_{year_month}"

        # Source detail with article domain
        best_url = url_by_district.get(district.lower(), "")
        domain = urlparse(best_url).netloc if best_url else "web search"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "leadership_scan",
            "source_detail": f"Serper scan — {domain}",
            "signal_type": "leadership",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": urgency,
            "customer_status": cust_status,
            "url": "",  # Empty for correct dedup — write_signals key falls back to msg_id only
            "message_id": msg_id,
        })

    logger.info(f"Leadership scan: {len(signals)} superintendent changes extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")

    # Persist to superintendent directory (GitHub memory)
    try:
        dir_result = update_superintendent_directory(items)
        logger.info(
            f"Superintendent directory: +{dir_result['added']} added, "
            f"{dir_result['updated']} updated, {len(dir_result['changed'])} real changes, "
            f"{dir_result['total']} total"
        )
    except Exception as e:
        logger.warning(f"Superintendent directory update failed: {e}")

    if progress_callback:
        progress_callback(f"Leadership scan: {len(signals)} superintendent changes found")
    return signals


# ─────────────────────────────────────────────
# RFP OPPORTUNITY SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_rfp_opportunities(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 RFPs relevant to CodeCombat across territory states via Serper web search.
    Uses Claude Haiku to extract and filter for CodeCombat-relevant opportunities only.
    Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan RFP opportunities")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)  # No CA — too many RFPs
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CS/STEM RFPs...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"RFP" OR "request for proposal" "computer science" OR "coding" OR "programming" curriculum school "{state_name}"',
            f'"RFP" OR "request for proposal" "STEM" OR "CTE" software OR curriculum school district "{state_name}"',
            f'site:bidnet.com "computer science" OR "coding" OR "STEM" curriculum "{state_name}"',
            f'site:bonfirehub.com school district "computer science" OR "coding" "{state_name}"',
            # F3: Curriculum adoption season — Nov-Jan committee formation (primary)
            f'"request for information" OR "RFI" "computer science" OR "STEM" school district "{state_name}"',
            f'"curriculum evaluation committee" OR "CS committee" school "{state_name}"',
            f'"seeking" "computer science curriculum" school district "{state_name}"',
            # F3: Curriculum adoption season — Feb-May committee meetings (secondary)
            f'"curriculum review committee" "computer science" OR "STEM" "{state_name}"',
            f'"board agenda" "curriculum" review "computer science" OR "coding" "{state_name}"',
            f'"textbook adoption" "computer science" OR "STEM" school district "{state_name}"',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper RFP search failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("RFP scan: no search results found")
        if progress_callback:
            progress_callback("No RFP opportunities found in search results.")
        return []

    logger.info(f"RFP scan: {len(all_snippets)} unique articles from {len(scan_states)} states")

    # Build combined text for Claude extraction
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Filtering {len(all_snippets)} results for CodeCombat-relevant RFPs...")

    # Single Claude Haiku call with aggressive CodeCombat relevance filtering
    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district RFP/bid/procurement opportunities from these search results.

ONLY include RFPs where CodeCombat (a game-based computer science education platform) could be a strong candidate. CodeCombat teaches CS through game-based coding, offers AI-powered math tutoring (Algebra), and cybersecurity courses.

INCLUDE these RFP categories:
- Computer science, coding, or programming curriculum
- STEM/STEAM/CTE software platforms
- Game-based or project-based learning platforms
- Math curriculum or software (especially algebra)
- Cybersecurity education programs
- Digital curriculum adoption with CS/technology strand
- Professional development for CS/STEM teachers

HARD EXCLUDE (even if they mention "technology"):
- Construction, facilities, HVAC, roofing, furniture
- Hardware only (Chromebooks, laptops, networking, Wi-Fi)
- Food service, janitorial, transportation
- Legal, insurance, auditing, financial services
- LMS/SIS systems (Canvas, PowerSchool, Infinite Campus)
- Assessment/testing platforms (unless CS-specific)
- Generic office or admin software
- ERP, payroll, HR systems

For each relevant RFP, extract:
{{
  "district": "District Name",
  "state": "XX",
  "rfp_title": "Short title",
  "deadline": "YYYY-MM-DD or empty string if unknown",
  "what_theyre_buying": "1 sentence summary",
  "headline": "RFP: [title] — [district] ([state])"
}}

If deadline is mentioned, append " — due [date]" to headline.
If no CodeCombat-relevant RFPs found, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude RFP extraction failed: {e}")
        return []

    # Parse JSON — strip markdown fences and preamble
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("RFP extraction: no JSON array found in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"RFP extraction JSON parse failed: {e}")
        return []

    # Post-process extracted items
    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    # Build URL lookup for source_detail
    url_by_district = {}
    for s in all_snippets:
        title_lower = s["title"].lower()
        for item in items:
            dist_lower = item.get("district", "").lower()
            if dist_lower and dist_lower in title_lower:
                url_by_district[dist_lower] = s["url"]

    for item in items:
        district = item.get("district", "").strip()
        state = item.get("state", "").strip().upper()
        rfp_title = item.get("rfp_title", "").strip()
        headline = item.get("headline", "").strip()

        if not district or not state:
            continue

        # Validate state is in territory
        if state not in TERRITORY_STATES_WITH_CA:
            continue

        # NCES lookup for validation/correction
        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Dedup within scan by (district, rfp_title)
        norm_district = csv_importer.normalize_name(district)
        norm_title = rfp_title.lower().strip()[:50] if rfp_title else ""
        dedup_key = (norm_district, norm_title)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        # Customer relationship check
        cust_status = check_customer_status(district)

        # All RFPs are time_sensitive (deadline data from snippets is unreliable)
        urgency = "time_sensitive"

        # Heat score
        heat = compute_heat_score("rfp", 1, True, cust_status)

        # Message ID for cross-scan dedup (monthly granularity)
        msg_id = f"rfp_{norm_district}_{year_month}"

        # Full URL preserved in source_detail for future RFP submission tool
        best_url = url_by_district.get(district.lower(), "")

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "rfp_scan",
            "source_detail": f"Serper — {best_url}" if best_url else "Serper — web search",
            "signal_type": "rfp",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": urgency,
            "customer_status": cust_status,
            "url": "",  # Empty for correct dedup — write_signals key falls back to msg_id only
            "message_id": msg_id,
        })

    logger.info(f"RFP scan: {len(signals)} CodeCombat-relevant RFPs extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"RFP scan: {len(signals)} opportunities found")
    return signals


# ─────────────────────────────────────────────
# LEGISLATIVE SIGNAL SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_legislative_signals(states=None, progress_callback=None) -> list:
    """
    Scan for state-level CS/STEM/CTE education legislation that creates district-wide demand.
    New CS mandates = every district in that state needs curriculum.
    Returns list of signal dicts. Cost: ~$0.03/scan. Run monthly.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan legislative signals")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    # Scan ALL 50 states for legislation (not just territory — a new mandate in
    # a non-territory state could mean CodeCombat expansion opportunity)
    scan_states = states or list(TERRITORY_STATES_WITH_CA)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CS/STEM legislation...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"computer science" ("mandate" OR "requirement" OR "legislation" OR "bill") K-12 school "{state_name}" 2026',
            f'"CTE" OR "STEM" ("legislation" OR "mandate" OR "state law" OR "requirement") education "{state_name}" 2026',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper legislative search failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Legislative scan: no search results found")
        if progress_callback:
            progress_callback("No CS/STEM legislation found.")
        return []

    logger.info(f"Legislative scan: {len(all_snippets)} unique articles from {len(scan_states)} states")

    # Build combined text for Claude extraction
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting legislative signals from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 CS/STEM/CTE education legislation and policy changes from these search results.

INCLUDE:
- New state mandates requiring CS education in K-12 schools
- Bills expanding CS/CTE graduation requirements
- State funding allocations for CS/STEM curriculum
- State-level AI education policy or requirements
- Executive orders or state board decisions on CS education
- State CS standards adoption or revision

EXCLUDE:
- Federal-level legislation (unless directly affecting K-12 CS)
- General education funding not specific to CS/STEM/CTE
- University/higher-ed policy
- Opinions, editorials, or advocacy articles (not actual legislation)
- Old/expired legislation from prior years

For each legislative signal, extract:
{{
  "state": "XX",
  "bill_or_policy": "HB 1035 or State Board Decision or Executive Order",
  "status": "introduced|passed_committee|passed_house|passed_senate|signed|enacted|proposed",
  "what_it_does": "1 sentence: what this legislation requires or funds",
  "headline": "[state] [bill]: [summary]"
}}

If no CS/STEM/CTE legislation found, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude legislative extraction failed: {e}")
        return []

    # Parse JSON
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Legislative extraction: no JSON array found in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Legislative extraction JSON parse failed: {e}")
        return []

    # Post-process
    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    # URL lookup
    url_by_state = {}
    for s in all_snippets:
        state_abbr = s["searched_state"]
        if state_abbr not in url_by_state:
            url_by_state[state_abbr] = s["url"]

    for item in items:
        state = item.get("state", "").strip().upper()
        bill = item.get("bill_or_policy", "").strip()
        status = item.get("status", "").strip().lower()
        headline = item.get("headline", "").strip()

        if not state or not headline:
            continue

        # Dedup within scan by (state, bill)
        dedup_key = (state, bill.lower()[:30] if bill else headline.lower()[:30])
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        # Legislative signals are state-scope (affect all districts in the state)
        in_territory = state in TERRITORY_STATES_WITH_CA

        # Urgency based on status
        if status in ("signed", "enacted"):
            urgency = "urgent"  # Law is active — districts must comply
        elif status in ("passed_house", "passed_senate", "passed_committee"):
            urgency = "time_sensitive"  # Moving through legislature
        else:
            urgency = "routine"  # Early stage

        heat = compute_heat_score("ai_policy", 2, in_territory, "new")
        # Override: legislation is higher value than ai_policy base weight
        if in_territory:
            heat = max(heat, 30)
        if status in ("signed", "enacted"):
            heat = min(heat + 15, 100)

        msg_id = f"legislation_{state}_{year_month}"
        best_url = url_by_state.get(state, "")

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "legislative_scan",
            "source_detail": f"Serper — {best_url}" if best_url else "Serper — web search",
            "signal_type": "ai_policy",  # Closest existing type
            "scope": "state",
            "district": "",  # State-level, not district-specific
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1 if status in ("signed", "enacted") else 2,
            "heat_score": heat,
            "urgency": urgency,
            "customer_status": "new",
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Legislative scan: {len(signals)} CS/STEM legislative signals extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Legislative scan: {len(signals)} signals found")
    return signals


# ─────────────────────────────────────────────
# GRANT-FUNDED PROSPECTING SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_grant_opportunities(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 districts that received or are applying for CS/STEM/CTE grants.
    Targets: Title IV-A, Perkins V (CTE), state STEM grants, NSF awards, private foundation grants.
    Uses Serper + Claude Haiku. Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan grants")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for STEM/CS grant awards...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"grant" ("awarded" OR "received" OR "funded") ("computer science" OR "STEM" OR "CTE") school district "{state_name}"',
            f'("Title IV" OR "Perkins" OR "STEM grant" OR "CTE grant") school district "{state_name}" 2026',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper grant scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Grant scan: no results found")
        if progress_callback:
            progress_callback("Grant scan: no results found.")
        return []

    logger.info(f"Grant scan: {len(all_snippets)} articles from {len(scan_states)} states")

    # Build combined text for Claude
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting grant signals from {len(all_snippets)} articles...")

    # Claude Haiku extraction
    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district grant awards and funding relevant to CS/STEM/CTE curriculum from these search results.

INCLUDE only:
- Districts receiving grants for computer science, coding, STEM, CTE, or technology curriculum
- Title IV-A well-rounded education grants used for CS/STEM
- Perkins V CTE grants for CS/tech pathways
- State STEM/CS education grants
- NSF or private foundation grants for K-12 CS/STEM programs
- Districts announcing they will USE grant funds for CS/STEM/CTE

EXCLUDE:
- Construction/facilities grants (even if labeled "STEM building")
- Device/hardware-only grants (1:1 laptop, Chromebook)
- Generic education grants not specific to CS/STEM/CTE
- Grants to colleges or universities
- Grants for non-education entities
- E-Rate (telecom/internet infrastructure)

Return a JSON array. Each item:
{{
  "district": "Exact district name",
  "state": "2-letter state code",
  "grant_type": "Title IV-A | Perkins V | state_stem | nsf | private_foundation | other",
  "dollar_amount": "$X,XXX or empty string if unknown",
  "what_its_for": "1 sentence: what the grant funds",
  "headline": "Grant: [district] receives [amount] for [purpose]"
}}

If nothing qualifies after filtering, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude grant extraction failed: {e}")
        return []

    # Parse JSON
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Grant scan: no JSON array in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Grant scan JSON parse failed: {e}")
        return []

    # Post-process: validate, dedup, build signals
    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        # NCES validation
        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Dedup by district + grant type
        norm_district = csv_importer.normalize_name(district)
        grant_type = (item.get("grant_type") or "other").strip().lower()
        dedup_key = (norm_district, grant_type)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        in_territory = state in TERRITORY_STATES
        cust_status = check_customer_status(district)
        heat = compute_heat_score("grant", 1, in_territory, cust_status)

        headline = (item.get("headline") or f"Grant: {district} ({state})").strip()
        dollar = (item.get("dollar_amount") or "").strip()
        msg_id = f"grant_{norm_district}_{grant_type}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "grant_scan",
            "source_detail": f"Serper — {grant_type}",
            "signal_type": "grant",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": dollar,
            "tier": 1,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Grant scan: {len(signals)} CS/STEM grant signals extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Grant scan: {len(signals)} signals found")
    return signals


# ─────────────────────────────────────────────
# F4: STATE CS FUNDING AWARD SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

# Tier 2 hints: known state CS program names. Tier 1 generic queries
# always run; Tier 2 adds hints when programs are confirmed.
STATE_CS_PROGRAMS = {
    "TX": ["TEA Advancing CS"],
    "IL": ["CS Equity Grant"],
    "MA": ["Innovation Pathways CS"],
    "PA": ["PAsmart"],
    "OH": ["Computer Science Promise"],
}


def scan_cs_funding_awards(states=None, progress_callback=None) -> dict:
    """
    F4: Scan for K-12 districts that recently received state-level CS funding.
    Award recipients are pre-qualified leads — they said yes to CS and have budget.

    HIGH confidence + recent → auto-queues to Prospecting Queue as `pending`
    via add_district() with strategy=cs_funding_recipient.

    MEDIUM/LOW confidence → writes to Signals tab only for manual review.

    Returns dict: {
        signals: list,           # signals written to Signals tab (medium/low)
        queued: list,            # district names queued as prospects
        customer_intel: list,    # active accounts found in scan (don't sell)
        raw_count: int,
    }
    Cost: ~$0.10/scan.
    """
    if not ENABLE_FUNDING_SCAN:
        logger.info("CS funding scan: disabled via ENABLE_FUNDING_SCAN")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan CS funding")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES_WITH_CA)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CS funding awards...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)

        # Tier 1: generic queries (always run)
        queries = [
            f'"computer science" OR "CS" grant awarded school district "{state_name}"',
            f'"received" grant "computer science" OR "coding" school "{state_name}"',
            f'"STEM grant" awarded school district "{state_name}"',
            f'"{state_name} Department of Education" grant "computer science" OR "STEM" awarded',
        ]

        # Tier 2: state-specific program hints (only when known)
        for program_name in STATE_CS_PROGRAMS.get(state_abbr, []):
            queries.append(
                f'"{program_name}" awarded district "{state_name}"'
            )

        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:y"},  # 1-year window
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper CS funding scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("CS funding scan: no results")
        if progress_callback:
            progress_callback("No CS funding awards found.")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    logger.info(f"CS funding scan: {len(all_snippets)} articles from {len(scan_states)} states")

    # Build combined text for Claude
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:14000]

    if progress_callback:
        progress_callback(f"Extracting CS funding awards from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district CS funding awards from these search results.

For each award, return JSON:
{{
  "district": "Exact district name",
  "state": "2-letter state code",
  "program": "name of grant program",
  "amount": "$X,XXX or empty if unknown",
  "award_date": "YYYY-MM or empty if unknown",
  "purpose": "CS curriculum | teacher PD | equipment | general",
  "confidence": "HIGH | MEDIUM | LOW"
}}

CONFIDENCE RULES:
- HIGH: district named clearly, amount present, CS-specific purpose confirmed,
        K-12 context unambiguous, source date present
- MEDIUM: district + CS context clear, amount or date missing
- LOW: program-level announcement without specific recipient OR partial entity match

EXCLUDE:
- Universities, community colleges, individual schools without district context
- Private schools
- General STEM grants without clear CS component
- Construction/facilities grants
- Device/hardware-only grants (1:1 laptop, Chromebook)
- E-Rate or telecom infrastructure
- Awards >12 months old

Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude CS funding extraction failed: {e}")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    # Parse JSON
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("CS funding scan: no JSON array in response")
            return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"CS funding scan JSON parse failed: {e}")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    # Post-process: route HIGH→queue, MEDIUM/LOW→signals, customer matches→intel
    signals_to_write = []
    queued_districts = []
    customer_intel = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    # Lazy import to avoid circular dependency
    import tools.district_prospector as district_prospector

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        # NCES validation/correction
        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Dedup within scan
        norm_district = csv_importer.normalize_name(district)
        program = (item.get("program") or "unknown").strip()
        program_key = csv_importer.normalize_name(program) or "unknown"
        dedup_key = (norm_district, program_key)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        confidence = (item.get("confidence") or "LOW").strip().upper()
        amount = (item.get("amount") or "").strip()
        award_date = (item.get("award_date") or "").strip()
        purpose = (item.get("purpose") or "").strip()
        cust_status = check_customer_status(district)
        in_territory = state in TERRITORY_STATES_WITH_CA

        headline = f"{district} ({state}) — {amount or 'CS grant'} for {purpose or 'CS program'}"
        msg_id = f"funding_{norm_district}_{program_key}_{year_month}"
        notes = f"Program: {program}. Amount: {amount or 'unknown'}. Date: {award_date or 'unknown'}. Purpose: {purpose or 'CS'}. Confidence: {confidence}."

        # Active customer → log as intel only, don't sell
        if cust_status == "active":
            customer_intel.append({"district": district, "state": state, "notes": notes})
            signals_to_write.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "cs_funding_scan",
                "source_detail": f"Customer intel — {program}",
                "signal_type": "cs_funding_award",
                "scope": "district",
                "district": district,
                "state": state,
                "headline": f"[CUSTOMER] {headline}"[:200],
                "dollar_amount": amount,
                "tier": 1,
                "heat_score": compute_heat_score("grant", 1, in_territory, cust_status),
                "urgency": "time_sensitive",
                "customer_status": cust_status,
                "url": "",
                "message_id": msg_id,
            })
            continue

        # HIGH confidence → auto-queue as pending
        if confidence == "HIGH":
            try:
                queue_result = district_prospector.add_district(
                    name=district,
                    state=state,
                    notes=notes,
                    strategy="cs_funding_recipient",
                    source="signal",
                    signal_id=msg_id,
                )
                if queue_result.get("success"):
                    queued_districts.append(district)
                # If already in queue or active, add_district returns success=False
                # but we still log the signal below
            except Exception as e:
                logger.warning(f"add_district failed for {district}: {e}")

        # All confidence levels also write to Signals tab
        signals_to_write.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "cs_funding_scan",
            "source_detail": f"Serper — {program}",
            "signal_type": "cs_funding_award",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": amount,
            "tier": 1 if confidence == "HIGH" else 2,
            "heat_score": compute_heat_score("grant", 1, in_territory, cust_status),
            "urgency": "time_sensitive" if confidence == "HIGH" else "routine",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(
        f"CS funding scan: {len(items)} raw, {len(signals_to_write)} signals, "
        f"{len(queued_districts)} auto-queued, {len(customer_intel)} customer intel"
    )
    if progress_callback:
        progress_callback(
            f"CS funding scan: {len(signals_to_write)} signals, {len(queued_districts)} queued"
        )

    return {
        "signals": signals_to_write,
        "queued": queued_districts,
        "customer_intel": customer_intel,
        "raw_count": len(items),
    }


# ─────────────────────────────────────────────
# F2: COMPETITOR DISPLACEMENT SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

# Competitors to track. Job postings + RFP replacement language are
# more reliable signals than vendor case studies.
COMPETITORS = [
    {"key": "tynker", "name": "Tynker", "domain": "tynker.com"},
    {"key": "codehs", "name": "CodeHS", "domain": "codehs.com"},
    {"key": "replit", "name": "Replit for Education", "domain": "replit.com"},
    {"key": "khan_cs", "name": "Khan Academy CS", "domain": "khanacademy.org"},
    {"key": "codeorg", "name": "Code.org Express", "domain": "code.org"},
    {"key": "tinkercad", "name": "Tinkercad", "domain": "tinkercad.com"},
]


def scan_competitor_displacement(states=None, progress_callback=None) -> dict:
    """
    F2: Scan for K-12 districts currently using Tynker, CodeHS, Replit,
    Khan Academy CS, Code.org Express, or Tinkercad. These districts are
    pre-sold on CS — just need a better platform.

    Source priority:
      1. Job postings (primary) — "experience with X" implies active use
      2. RFP replacement language ("replacing X")
      3. Vendor case studies (tertiary, lower trust)

    HIGH confidence → auto-queue via add_district() with strategy=
        competitor_displacement.
    MEDIUM/LOW → Signals tab only.
    Active customer → customer_intel only (competitive positioning).

    Returns: {signals, queued, customer_intel, raw_count}
    Cost: ~$0.20/scan (heavier query count than F4).
    """
    if not ENABLE_COMPETITOR_SCAN:
        logger.info("Competitor displacement scan: disabled via ENABLE_COMPETITOR_SCAN")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan competitor displacement")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES_WITH_CA)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(
            f"Searching {len(scan_states)} states × {len(COMPETITORS)} competitors..."
        )

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)

        for comp in COMPETITORS:
            name = comp["name"]
            domain = comp["domain"]

            queries = [
                # Primary: job postings (most actionable)
                f'"experience with {name}" OR "teach {name}" school district job "{state_name}"',
                # Secondary: RFP replacement language
                f'"replacing {name}" OR "transition from {name}" school district "{state_name}"',
                # Tertiary: vendor case studies
                f'site:{domain} "school district" "{state_name}"',
            ]

            for query in queries:
                try:
                    resp = httpx.post(
                        SERPER_URL,
                        headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                        json={"q": query, "num": 10, "tbs": "qdr:y"},
                        timeout=15.0,
                    )
                    data = resp.json()
                    for item in data.get("organic", [])[:10]:
                        url = item.get("link", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_snippets.append({
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "url": url,
                                "searched_state": state_abbr,
                                "searched_competitor": comp["key"],
                            })
                    time.sleep(0.3)  # 0.3s × 234 queries ≈ 70s scan time
                except Exception as e:
                    logger.warning(
                        f"Serper competitor scan failed for {state_abbr}/{comp['key']}: {e}"
                    )

    if not all_snippets:
        logger.info("Competitor scan: no results")
        if progress_callback:
            progress_callback("No competitor mentions found.")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    logger.info(
        f"Competitor scan: {len(all_snippets)} unique articles from "
        f"{len(scan_states)} states × {len(COMPETITORS)} competitors"
    )

    # Build combined text for Claude
    combined_text = ""
    for s in all_snippets:
        combined_text += (
            f"\n[{s['searched_state']}/{s['searched_competitor']}] "
            f"{s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
        )
    combined_text = combined_text[:16000]

    if progress_callback:
        progress_callback(f"Extracting competitor mentions from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district mentions of competitor curriculum platforms from these search results.

Be PERMISSIVE in extraction. The downstream system uses confidence tiers
to filter, so include ALL plausible K-12 district mentions and let the
confidence field convey uncertainty. Do NOT pre-filter aggressively.

For each mention, return JSON:
{{
  "district": "District or school name (best guess from snippet)",
  "state": "2-letter state code",
  "competitor": "Tynker | CodeHS | Replit for Education | Khan Academy CS | Code.org Express | Tinkercad",
  "evidence_type": "job_posting | rfp_replacement | case_study | press_release | other",
  "first_mention_date": "YYYY-MM or empty",
  "confidence": "HIGH | MEDIUM | LOW",
  "headline": "one-sentence summary"
}}

INCLUDE (be generous):
- Any K-12 district, school, or school system mention paired with a competitor name
- Job postings at K-12 schools mentioning competitor experience
- Vendor case studies, customer lists, press releases naming K-12 customers
- News articles mentioning a school/district using a competitor
- Board meeting minutes referencing competitor adoption or evaluation
- If snippet says "school district" without naming one, still include with confidence=LOW

CONFIDENCE TIERS:
- HIGH: district named clearly + competitor named clearly + clear K-12 context
- MEDIUM: district OR competitor named clearly, other field inferable
- LOW: district name partial, ambiguous K-12 context, or vague snippet

EXCLUDE only:
- Universities, colleges, coding bootcamps for adults
- Out-of-territory results (state field must match the searched state)

Return ONLY a valid JSON array — no commentary. Empty array [] if truly nothing.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude competitor extraction failed: {e}")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    # Parse JSON
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Competitor scan: no JSON array in response")
            return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Competitor scan JSON parse failed: {e}")
        return {"signals": [], "queued": [], "customer_intel": [], "raw_count": 0}

    # Lookup map for competitor key from full name
    name_to_key = {c["name"]: c["key"] for c in COMPETITORS}

    signals_to_write = []
    queued_districts = []
    customer_intel = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    import tools.district_prospector as district_prospector

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        norm_district = csv_importer.normalize_name(district)
        competitor = (item.get("competitor") or "").strip()
        comp_key = name_to_key.get(competitor, csv_importer.normalize_name(competitor) or "unknown")
        dedup_key = (norm_district, comp_key)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        confidence = (item.get("confidence") or "LOW").strip().upper()
        evidence_type = (item.get("evidence_type") or "other").strip()
        first_mention = (item.get("first_mention_date") or "").strip()
        cust_status = check_customer_status(district)
        in_territory = state in TERRITORY_STATES_WITH_CA

        headline = f"{district} ({state}) — uses {competitor} ({evidence_type})"
        msg_id = f"competitor_{norm_district}_{comp_key}_{year_month}"
        notes = (
            f"Competitor: {competitor}. Evidence: {evidence_type}. "
            f"First mention: {first_mention or 'unknown'}. Confidence: {confidence}."
        )

        # Active customer → log as intel only
        if cust_status == "active":
            customer_intel.append({
                "district": district,
                "state": state,
                "competitor": competitor,
                "notes": notes,
            })
            signals_to_write.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "competitor_scan",
                "source_detail": f"Customer intel — {competitor}",
                "signal_type": "competitor_usage",
                "scope": "district",
                "district": district,
                "state": state,
                "headline": f"[CUSTOMER] {headline}"[:200],
                "dollar_amount": "",
                "tier": 2,
                "heat_score": compute_heat_score("market_intel", 2, in_territory, cust_status),
                "urgency": "routine",
                "customer_status": cust_status,
                "url": "",
                "message_id": msg_id,
            })
            continue

        # HIGH confidence → auto-queue as pending
        if confidence == "HIGH":
            try:
                queue_result = district_prospector.add_district(
                    name=district,
                    state=state,
                    notes=notes,
                    strategy="competitor_displacement",
                    source="signal",
                    signal_id=msg_id,
                )
                if queue_result.get("success"):
                    queued_districts.append(f"{district} ({competitor})")
            except Exception as e:
                logger.warning(f"add_district failed for {district}: {e}")

        # Always write to Signals tab too
        signals_to_write.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "competitor_scan",
            "source_detail": f"Serper — {evidence_type}",
            "signal_type": "competitor_usage",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1 if confidence == "HIGH" else 2,
            "heat_score": compute_heat_score("market_intel", 1 if confidence == "HIGH" else 2, in_territory, cust_status),
            "urgency": "time_sensitive" if confidence == "HIGH" else "routine",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(
        f"Competitor scan: {len(items)} raw, {len(signals_to_write)} signals, "
        f"{len(queued_districts)} auto-queued, {len(customer_intel)} customer intel"
    )
    if progress_callback:
        progress_callback(
            f"Competitor scan: {len(signals_to_write)} signals, {len(queued_districts)} queued"
        )

    return {
        "signals": signals_to_write,
        "queued": queued_districts,
        "customer_intel": customer_intel,
        "raw_count": len(items),
    }


# ─────────────────────────────────────────────
# BUDGET CYCLE TARGETING SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_budget_cycle_signals(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 districts in active budget/procurement cycles for CS/STEM/CTE.
    Targets: budget approvals, curriculum adoption cycles, technology refresh plans,
    board-approved spending for CS/STEM programs.
    Uses Serper + Claude Haiku. Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan budget cycles")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for budget/procurement signals...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"budget" ("approved" OR "adopted" OR "proposed") ("computer science" OR "STEM" OR "CTE" OR "technology") school district "{state_name}" 2026',
            f'("curriculum adoption" OR "technology plan" OR "procurement" OR "technology refresh") ("CS" OR "STEM" OR "CTE" OR "coding") school district "{state_name}"',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper budget scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Budget scan: no results found")
        if progress_callback:
            progress_callback("Budget scan: no results found.")
        return []

    logger.info(f"Budget scan: {len(all_snippets)} articles from {len(scan_states)} states")

    # Build combined text for Claude
    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting budget signals from {len(all_snippets)} articles...")

    # Claude Haiku extraction
    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district budget and procurement signals relevant to CS/STEM/CTE curriculum purchasing from these search results.

INCLUDE only:
- Districts approving budgets that include CS/STEM/CTE curriculum spending
- Districts in curriculum adoption cycles for computer science, STEM, or CTE
- Technology refresh/replacement plans that include instructional software
- Board-approved spending for CS/STEM/CTE programs or professional development
- Districts announcing they are evaluating or selecting CS/STEM curriculum vendors

EXCLUDE:
- General budget news without CS/STEM/CTE specifics
- Construction/facilities budgets (even if "STEM building")
- Device-only purchases (laptops, Chromebooks, hardware)
- ERP/payroll/admin system purchases
- Assessment platform purchases
- LMS/SIS purchases
- Budget cuts or layoffs (unless reallocating TO CS/STEM)
- Non-CS curriculum adoptions: health, physical education, social studies, English/ELA, foreign language, art, music
- Sports/athletics budgets
- Special education program budgets (unless specifically CS/STEM for special ed)

Return a JSON array. Each item:
{{
  "district": "Exact district name",
  "state": "2-letter state code",
  "budget_signal": "budget_approved | curriculum_adoption | tech_plan | procurement | vendor_evaluation",
  "dollar_amount": "$X,XXX or empty string if unknown",
  "timeline": "FY2026 | Spring 2026 | Fall 2026 | unknown",
  "what_theyre_buying": "1 sentence: what CS/STEM/CTE they are buying or planning to buy",
  "headline": "[district]: [budget signal summary]"
}}

If nothing qualifies after filtering, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude budget extraction failed: {e}")
        return []

    # Parse JSON
    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Budget scan: no JSON array in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Budget scan JSON parse failed: {e}")
        return []

    # Post-process: validate, dedup, build signals
    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        # NCES validation
        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Dedup by district
        norm_district = csv_importer.normalize_name(district)
        if norm_district in dedup_seen:
            continue
        dedup_seen.add(norm_district)

        in_territory = state in TERRITORY_STATES
        cust_status = check_customer_status(district)

        # Budget signals use "technology" weight — districts actively spending
        heat = compute_heat_score("technology", 1, in_territory, cust_status)
        # Boost for vendor evaluation (hottest signal — actively shopping)
        budget_signal = (item.get("budget_signal") or "").strip().lower()
        if budget_signal in ("vendor_evaluation", "procurement"):
            heat = min(heat + 10, 100)

        headline = (item.get("headline") or f"{district}: budget signal").strip()
        dollar = (item.get("dollar_amount") or "").strip()
        timeline = (item.get("timeline") or "").strip()
        if timeline and timeline != "unknown":
            headline = f"{headline} ({timeline})"

        msg_id = f"budget_{norm_district}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "budget_scan",
            "source_detail": f"Serper — {budget_signal or 'budget'}",
            "signal_type": "technology",  # Closest existing type for budget/procurement
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": dollar,
            "tier": 1,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Budget scan: {len(signals)} CS/STEM budget signals extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Budget scan: {len(signals)} signals found")
    return signals


# ─────────────────────────────────────────────
# AI ALGEBRA CAMPAIGN SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_algebra_targets(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 districts actively seeking math/algebra technology or curriculum.
    Targets for the AI Algebra product (launched via AI Hackstack).
    Uses Serper + Claude Haiku. Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan algebra targets")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for math/algebra curriculum signals...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'("math curriculum" OR "algebra curriculum") ("adoption" OR "pilot" OR "evaluate" OR "implement") school district "{state_name}" 2026',
            f'("math technology" OR "adaptive math" OR "game-based math" OR "math intervention") K-12 school district "{state_name}"',
            f'("algebra" OR "mathematics") ("RFP" OR "request for proposal" OR "technology pilot") school district "{state_name}"',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:m"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper algebra scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Algebra scan: no results found")
        if progress_callback:
            progress_callback("Algebra scan: no results found.")
        return []

    logger.info(f"Algebra scan: {len(all_snippets)} articles from {len(scan_states)} states")

    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting algebra campaign targets from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school districts that are actively seeking, evaluating, or implementing math/algebra technology or curriculum from these search results.

INCLUDE:
- Districts adopting or piloting math/algebra technology platforms
- Districts posting RFPs for math curriculum or technology
- Districts implementing game-based or adaptive math programs
- Districts with new math initiatives, algebra intervention programs
- Districts expanding math technology to more grades/schools
- Districts with math curriculum adoption cycles underway

EXCLUDE:
- General math education news without a specific district taking action
- College/university programs
- State-level policy without district-specific action
- Assessment-only tools (state testing, benchmarking)
- Districts just talking about math scores without taking procurement action

Return a JSON array. Each item:
{{
  "district": "Exact district name",
  "state": "2-letter state code",
  "action_type": "adoption | pilot | rfp | expansion | initiative",
  "what_theyre_doing": "1 sentence: what math/algebra action they are taking",
  "headline": "[district] ([state]): [action summary]"
}}

If nothing qualifies after filtering, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude algebra extraction failed: {e}")
        return []

    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Algebra scan: no JSON array in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Algebra scan JSON parse failed: {e}")
        return []

    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        norm_district = csv_importer.normalize_name(district)
        if norm_district in dedup_seen:
            continue
        dedup_seen.add(norm_district)

        in_territory = state in TERRITORY_STATES
        cust_status = check_customer_status(district)
        heat = compute_heat_score("curriculum", 1, in_territory, cust_status)
        # Boost: districts actively buying math curriculum are hot targets for AI Algebra
        action_type = (item.get("action_type") or "").strip().lower()
        if action_type in ("rfp", "pilot", "adoption"):
            heat = min(heat + 15, 100)

        headline = (item.get("headline") or f"{district}: math/algebra signal").strip()
        msg_id = f"algebra_{norm_district}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "algebra_scan",
            "source_detail": f"Serper — {action_type or 'math'}",
            "signal_type": "curriculum",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": "time_sensitive",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Algebra scan: {len(signals)} math/algebra campaign targets extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Algebra scan: {len(signals)} targets found")
    return signals


# ─────────────────────────────────────────────
# CYBERSECURITY PRE-LAUNCH SCANNER (Serper + Claude)
# ─────────────────────────────────────────────

def scan_cybersecurity_targets(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 districts with CTE cybersecurity programs or starting new ones.
    Pre-launch pipeline building for Cybersecurity course (fall 2026).
    Uses Serper + Claude Haiku. Returns list of signal dicts. Cost: ~$0.03/scan.
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan cybersecurity targets")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CTE cybersecurity programs...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'("cybersecurity" OR "cyber security") ("CTE" OR "career technical" OR "pathway") school district "{state_name}"',
            f'("cybersecurity" OR "networking" OR "information technology") ("teacher" OR "instructor" OR "program") K-12 school "{state_name}"',
            f'("cybersecurity curriculum" OR "cyber education" OR "cybersecurity certification") K-12 school district "{state_name}"',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:y"},  # Wider window — pre-launch research
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper cybersecurity scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Cybersecurity scan: no results found")
        if progress_callback:
            progress_callback("Cybersecurity scan: no results found.")
        return []

    logger.info(f"Cybersecurity scan: {len(all_snippets)} articles from {len(scan_states)} states")

    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting cybersecurity targets from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school districts that have CTE cybersecurity programs, are starting cybersecurity pathways, or are hiring cybersecurity/networking teachers from these search results.

INCLUDE:
- Districts with existing CTE cybersecurity pathways or programs
- Districts launching new cybersecurity/networking CTE programs
- Districts hiring cybersecurity or networking teachers/instructors
- Districts with IT/cybersecurity certification programs (CompTIA, Cisco, etc.)
- Career academies or tech high schools with cybersecurity focus
- Districts receiving grants for cybersecurity education

EXCLUDE:
- District IT security incidents (hacking, data breaches) — that's the district being attacked, not teaching cybersecurity
- College/university cybersecurity programs
- General CTE news without cybersecurity specifics
- K-12 cybersecurity policy/compliance (not curriculum)

Return a JSON array. Each item:
{{
  "district": "Exact district name",
  "state": "2-letter state code",
  "program_type": "existing_program | new_program | hiring | certification | grant",
  "what_they_have": "1 sentence: what cybersecurity program or initiative they have",
  "headline": "[district] ([state]): [cybersecurity program summary]"
}}

If nothing qualifies after filtering, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude cybersecurity extraction failed: {e}")
        return []

    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Cybersecurity scan: no JSON array in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Cybersecurity scan JSON parse failed: {e}")
        return []

    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not district or not state or len(state) != 2:
            continue

        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        norm_district = csv_importer.normalize_name(district)
        if norm_district in dedup_seen:
            continue
        dedup_seen.add(norm_district)

        in_territory = state in TERRITORY_STATES
        cust_status = check_customer_status(district)
        heat = compute_heat_score("hiring", 1, in_territory, cust_status)  # hiring weight
        # Boost: existing programs are ideal targets for new curriculum
        program_type = (item.get("program_type") or "").strip().lower()
        if program_type in ("existing_program", "certification"):
            heat = min(heat + 10, 100)

        headline = (item.get("headline") or f"{district}: cybersecurity CTE").strip()
        msg_id = f"cybersecurity_{norm_district}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "cybersecurity_scan",
            "source_detail": f"Serper — {program_type or 'cybersecurity'}",
            "signal_type": "curriculum",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": "routine",  # Pre-launch — building pipeline, not urgent
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Cybersecurity scan: {len(signals)} CTE cybersecurity targets extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Cybersecurity scan: {len(signals)} targets found")
    return signals


# ─────────────────────────────────────────────
# ROLE/TITLE-BASED PROSPECTING (#7) — Serper + Claude
# ─────────────────────────────────────────────

def scan_role_targets(states=None, progress_callback=None) -> list:
    """
    Scan for K-12 contacts with specific CS/CTE/STEM leadership titles.
    Only searches rare/specific titles — common titles (Principal, Teacher)
    are too noisy for web search and are handled by job posting scanner.
    Uses Serper + Claude Haiku. Returns list of signal dicts.
    Cost: ~$2.50/scan (48 Serper queries + 1 Claude call).
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan role targets")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CS/CTE/STEM leaders (~$2.50)...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"Director of Computer Science" OR "CS Director" OR "CTE Director" OR "Director of CTE" OR "STEM Director" OR "Director of STEM" school district "{state_name}"',
            f'"Director of Technology" OR "EdTech Director" OR "Instructional Technology Director" OR "Educational Technology Director" school district "{state_name}"',
            f'"Curriculum Director" OR "Director of Curriculum" OR "STEM Coordinator" OR "CTE Coordinator" school district "{state_name}"',
            f'"Cybersecurity Teacher" OR "Game Design Teacher" OR "Esports Coach" OR "Robotics Teacher" school district "{state_name}"',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:y"},  # Last year — roles persist
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper role scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("Role scan: no results found")
        if progress_callback:
            progress_callback("Role scan: no results found.")
        return []

    logger.info(f"Role scan: {len(all_snippets)} articles from {len(scan_states)} states")

    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:15000]  # Larger context for more results

    if progress_callback:
        progress_callback(f"Extracting role targets from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract K-12 school district staff members with CS/CTE/STEM/Technology leadership roles from these search results.

INCLUDE only people with these types of titles at K-12 public school districts:
- Directors/Coordinators of: Computer Science, CTE, STEM, STEAM, Technology, EdTech, Curriculum
- Specialized teachers: Cybersecurity, Game Design, Esports, Robotics, Computer Science
- Any CS/CTE/STEM leadership role at a school district

EXCLUDE:
- College/university staff
- State department of education employees (unless at a district)
- IT infrastructure roles (network admin, help desk, sysadmin)
- Generic "teacher" or "principal" without CS/STEM specifics
- People at non-education organizations

For each person, extract:
{{
  "person_name": "Full name (Dr./Mr./Mrs. if shown)",
  "title": "Their exact job title",
  "district": "School district name",
  "state": "2-letter state code",
  "headline": "[person_name], [title] at [district] ([state])"
}}

Return a JSON array. If nothing qualifies, return [].
Return ONLY a valid JSON array — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude role extraction failed: {e}")
        return []

    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Role scan: no JSON array in response")
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Role scan JSON parse failed: {e}")
        return []

    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        person_name = (item.get("person_name") or "").strip()
        title = (item.get("title") or "").strip()
        district = (item.get("district") or "").strip()
        state = (item.get("state") or "").strip().upper()
        if not person_name or not district or not state or len(state) != 2:
            continue

        nces_state = lookup_district_state(district)
        if nces_state:
            state = nces_state

        # Person-level dedup: same person at same district in same month
        norm_person = csv_importer.normalize_name(person_name)
        norm_district = csv_importer.normalize_name(district)
        dedup_key = (norm_person, norm_district, year_month)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        in_territory = state in TERRITORY_STATES
        cust_status = check_customer_status(district)
        heat = compute_heat_score("hiring", 1, in_territory, cust_status)

        headline = (item.get("headline") or f"{person_name}, {title} at {district}").strip()
        msg_id = f"role_{norm_person}_{norm_district}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "role_scan",
            "source_detail": f"Serper — {title[:40]}",
            "signal_type": "hiring",
            "scope": "district",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 1,
            "heat_score": heat,
            "urgency": "routine",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"Role scan: {len(signals)} CS/CTE/STEM leaders extracted "
                f"({len(items)} raw, {len(items) - len(signals)} filtered/deduped)")
    if progress_callback:
        progress_callback(f"Role scan: {len(signals)} targets found")
    return signals


# ─────────────────────────────────────────────
# CSTA CHAPTER PROSPECTING (#8) — Serper + Claude
# ─────────────────────────────────────────────

def scan_csta_chapters(states=None, progress_callback=None) -> list:
    """
    Scan for CSTA chapter leaders and active members in territory states.
    Uses Serper + Claude Haiku. Returns list of signal dicts.
    Cost: ~$1.20/scan (24 Serper queries + 1 Claude call).
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — cannot scan CSTA chapters")
        return []

    import httpx

    _load_nces_lookup()
    _load_cross_references()

    scan_states = states or list(TERRITORY_STATES)
    all_snippets = []
    seen_urls = set()

    if progress_callback:
        progress_callback(f"Searching {len(scan_states)} states for CSTA chapter leaders...")

    for state_abbr in scan_states:
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
        queries = [
            f'"CSTA" chapter "{state_name}" leader OR president OR board member school district',
            f'"computer science teachers association" "{state_name}" conference OR workshop OR event school',
        ]
        for query in queries:
            try:
                resp = httpx.post(
                    SERPER_URL,
                    headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 10, "tbs": "qdr:y"},
                    timeout=15.0,
                )
                data = resp.json()
                for item in data.get("organic", [])[:10]:
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                        })
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Serper CSTA scan failed for {state_abbr}: {e}")

    if not all_snippets:
        logger.info("CSTA scan: no results found")
        if progress_callback:
            progress_callback("CSTA scan: no results found.")
        return []

    logger.info(f"CSTA scan: {len(all_snippets)} articles from {len(scan_states)} states")

    combined_text = ""
    for s in all_snippets:
        combined_text += f"\n[{s['searched_state']}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:12000]

    if progress_callback:
        progress_callback(f"Extracting CSTA members from {len(all_snippets)} articles...")

    import anthropic
    try:
        client = anthropic.Anthropic(timeout=90.0)
        prompt = f"""Extract CSTA (Computer Science Teachers Association) chapter leaders, board members, conference speakers, and active K-12 CS educators from these search results.

INCLUDE:
- CSTA state/regional chapter presidents, vice presidents, board members
- CSTA conference speakers/presenters who work at K-12 school districts
- Active CSTA members mentioned alongside their school district

EXCLUDE:
- University/college professors
- People at non-education organizations
- Generic CSTA news without specific people
- National CSTA staff (not district-level)

For each person:
{{
  "person_name": "Full name",
  "role": "CSTA chapter role or school title",
  "district": "School district name (if mentioned)",
  "state": "2-letter state code",
  "headline": "[person_name], [role] — CSTA [state] chapter"
}}

Return a JSON array. If nothing qualifies, return [].
Return ONLY valid JSON — no commentary.

Search results:
{combined_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        _track_usage(response)
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude CSTA extraction failed: {e}")
        return []

    try:
        clean = raw_text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            return []
        items = json.loads(clean[start:end + 1])
    except json.JSONDecodeError:
        return []

    signals = []
    dedup_seen = set()
    year_month = datetime.now().strftime("%Y_%m")

    for item in items:
        person_name = (item.get("person_name") or "").strip()
        state = (item.get("state") or "").strip().upper()
        district = (item.get("district") or "").strip()
        if not person_name or not state or len(state) != 2:
            continue

        # Territory filter — skip non-territory states
        if state not in TERRITORY_STATES:
            continue

        norm_person = csv_importer.normalize_name(person_name)
        dedup_key = (norm_person, state, year_month)
        if dedup_key in dedup_seen:
            continue
        dedup_seen.add(dedup_key)

        in_territory = True  # Already filtered above
        cust_status = check_customer_status(district) if district else "new"
        heat = compute_heat_score("hiring", 2, in_territory, cust_status)

        headline = (item.get("headline") or f"{person_name}, CSTA {state}").strip()
        msg_id = f"csta_{norm_person}_{state}_{year_month}"

        signals.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "csta_scan",
            "source_detail": f"Serper — CSTA {state}",
            "signal_type": "hiring",
            "scope": "district" if district else "state",
            "district": district,
            "state": state,
            "headline": headline[:200],
            "dollar_amount": "",
            "tier": 2,
            "heat_score": heat,
            "urgency": "routine",
            "customer_status": cust_status,
            "url": "",
            "message_id": msg_id,
        })

    logger.info(f"CSTA scan: {len(signals)} chapter leaders/members extracted")
    if progress_callback:
        progress_callback(f"CSTA scan: {len(signals)} targets found")
    return signals


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
    {
        "name": "District Administration",
        "url": "https://www.districtadministration.com/feed",
        "source_detail": "District Administration",
    },
    {
        "name": "EdSurge",
        "url": "https://www.edsurge.com/articles_rss",
        "source_detail": "EdSurge",
    },
    {
        "name": "CoSN",
        "url": "https://www.cosn.org/feed/",
        "source_detail": "CoSN",
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

    # Source 7: Ballotpedia bond measures (programmatic, $0)
    ballot_signals = []
    try:
        if progress_callback:
            progress_callback("Scanning Ballotpedia bonds...")
        ballot_signals = scan_ballotpedia(progress_callback=progress_callback)
        all_signals.extend(ballot_signals)
    except Exception as e:
        logger.warning(f"Ballotpedia scan failed (non-fatal): {e}")

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
        "ballot_signals": len(ballot_signals),
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

    ballot_signals = []
    try:
        ballot_signals = scan_ballotpedia(progress_callback=progress_callback)
        all_signals.extend(ballot_signals)
    except Exception as e:
        logger.warning(f"Ballotpedia scan failed (non-fatal): {e}")

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
        "ballot_signals": len(ballot_signals),
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
        risk_prefix = ""
        if sig.get("Signal Type") == "leadership" and sig.get("Customer Status") == "active":
            risk_prefix = "⚠️ RISK "
        lines.append(f"{i}. {risk_prefix}[{tag}] *{district_display}* — {headline}")
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

    if sig_type == "leadership" and cust == "active":
        lines.append("⚠️ ACCOUNT RISK — active customer leadership change\n")

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
    if summary.get("ballot_signals"):
        lines.append(f"  🗳 Ballotpedia: {summary['ballot_signals']}")

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
