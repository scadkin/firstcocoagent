#!/usr/bin/env python3
"""
C4 Enrichment Pass 2 — Comprehensive multi-source enrichment.

Enriches: state, title, parent district, international detection.

Data sources (in priority order):
  1. Email domain analysis (k12, edu, district domains → state)
  2. Leads from Research tab (email match → title, state)
  3. Active Accounts tab (domain match → state, district)
  4. NCES Territory Districts (name match → state, district info)
  5. NCES Territory Schools (name match → parent district, state)
  6. Serper web search (school/district website staff pages, NOT LinkedIn)
  7. Claude classification (from search results)

Usage: python3 scripts/enrich_c4_pass2.py
"""

import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Audit theme #4 (S70): shared .env loader. Replaces local if-exists
# branch that silently no-op'd on missing .env, and also fixes missing
# quote-stripping on parsed values.
sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ for _env
from _env import load_env_or_die  # noqa: E402
load_env_or_die(required=[
    "SERPER_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SHEETS_ID",
])

SERPER_API_KEY = os.environ["SERPER_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheets_service():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def read_tab(service, sheet_id, tab_range):
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=tab_range
    ).execute()
    return result.get("values", [])


def rows_to_dicts(rows):
    if len(rows) < 2:
        return []
    headers = rows[0]
    return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows[1:]]


# ─────────────────────────────────────────────
# EMAIL DOMAIN ANALYSIS
# ─────────────────────────────────────────────

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "protonmail.com", "msn.com", "live.com", "mail.com",
    "comcast.net", "sbcglobal.net", "att.net", "verizon.net", "cox.net",
    "charter.net", "earthlink.net", "me.com", "ymail.com", "rocketmail.com",
}

# State from k12 domain patterns
K12_STATE_PATTERN = re.compile(r"\.k12\.([a-z]{2})\.us$", re.IGNORECASE)
GOV_STATE_PATTERN = re.compile(r"\.([a-z]{2})\.us$", re.IGNORECASE)

US_STATE_ABBREVS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

INTL_TLDS = {
    ".ca", ".uk", ".au", ".nz", ".in", ".za", ".ng", ".ke", ".gh",
    ".ph", ".sg", ".my", ".hk", ".jp", ".kr", ".tw", ".br", ".mx",
    ".co", ".cl", ".ar", ".de", ".fr", ".es", ".it", ".nl", ".se",
    ".no", ".dk", ".fi", ".ie", ".be", ".at", ".ch", ".pt", ".pl",
    ".cz", ".hu", ".ro", ".bg", ".hr", ".rs", ".ae", ".sa", ".qa",
    ".eg", ".pk", ".bd", ".lk", ".th", ".vn", ".id", ".pa",
}
INTL_EDU_PATTERNS = (
    ".edu.pa", ".edu.mx", ".edu.br", ".edu.ar", ".edu.co", ".edu.pe",
    ".edu.cl", ".edu.au", ".edu.uk", ".edu.sg", ".edu.hk", ".edu.ph",
    ".edu.my", ".edu.in", ".edu.pk", ".edu.ng", ".edu.za",
    ".ac.uk", ".ac.nz", ".ac.jp", ".ac.kr", ".ac.in", ".ac.za",
    ".gc.ca", ".on.ca", ".bc.ca", ".ab.ca", ".qc.ca",
)
INTL_COMPANY_KEYWORDS = (
    "école", "ecole", "lycée", "lycee", "colegio", "liceo", "escuela",
    "instituto", "técnica", "tecnica", "buen pastor", "scolaire",
    "collège", "komisyon", "schule", "grundschule", "gymnasium",
    "scuola", "escola",
)


def _col_letter(idx: int) -> str:
    """Convert 0-indexed column number to A1 letter (A, B, ..., Z, AA, AB, ...).

    HIGH theme #3 (S70): replaces bare `chr(65 + col)` which wraps past Z
    silently — chr(65+26) = '[', breaking any write to a column at index ≥ 26.
    """
    if idx < 0:
        raise ValueError(f"negative column index: {idx}")
    result = ""
    while True:
        result = chr(65 + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


def extract_state_from_domain(email):
    """Try to extract US state from email domain. Returns state abbrev or None."""
    if not email or "@" not in email:
        return None
    domain = email.split("@")[1].lower()

    if domain in GENERIC_DOMAINS:
        return None

    # k12.XX.us pattern
    m = K12_STATE_PATTERN.search(domain)
    if m:
        st = m.group(1).upper()
        if st in US_STATE_ABBREVS:
            return st

    # .XX.us gov pattern
    m = GOV_STATE_PATTERN.search(domain)
    if m:
        st = m.group(1).upper()
        if st in US_STATE_ABBREVS:
            return st

    # State abbreviation in domain parts
    parts = domain.replace(".", " ").replace("-", " ").split()
    for part in parts:
        if part.upper() in US_STATE_ABBREVS and len(part) == 2:
            # Only if it's a clear state suffix like "schooltx" → TX
            pass  # Too ambiguous on its own

    return None


def detect_international(email, company):
    """Detect if prospect is international. Returns country hint or None."""
    if not email:
        return None
    domain = email.split("@")[1].lower() if "@" in email else ""
    company_lower = (company or "").lower()

    # International TLD
    for tld in INTL_TLDS:
        if domain.endswith(tld):
            return tld.strip(".")

    # International edu patterns
    for pat in INTL_EDU_PATTERNS:
        if domain.endswith(pat):
            return pat.split(".")[-1]

    # International company keywords
    for kw in INTL_COMPANY_KEYWORDS:
        if kw in company_lower:
            return f"intl_keyword:{kw}"

    return None


# ─────────────────────────────────────────────
# SERPER
# ─────────────────────────────────────────────

def serper_search(query, num_results=5):
    if not SERPER_API_KEY:
        return []
    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=15.0,
        )
        resp.raise_for_status()
        return [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "link": r.get("link", "")}
            for r in resp.json().get("organic", [])
        ]
    except Exception as e:
        logger.warning(f"Serper error: {e}")
        return []


# ─────────────────────────────────────────────
# CLAUDE
# ─────────────────────────────────────────────

def claude_enrich_batch(batch, task_type="all"):
    """
    Use Claude to enrich a batch of prospects.
    task_type: 'state' (find state/country), 'title' (find role), 'all' (everything)
    """
    if not ANTHROPIC_API_KEY or not batch:
        return []

    items_text = []
    for i, item in enumerate(batch):
        search_text = ""
        for r in item.get("search_results", [])[:4]:
            search_text += f"    - [{r.get('link', '')}] {r['title']}: {r['snippet']}\n"

        items_text.append(
            f"{i+1}. Name: {item.get('name', '')}\n"
            f"   Email: {item.get('email', '')}\n"
            f"   Company: {item.get('company', '')}\n"
            f"   Entity type: {item.get('entity_type', '')}\n"
            f"   Current state: {item.get('current_state', '(unknown)')}\n"
            f"   Current title: {item.get('current_title', '(unknown)')}\n"
            f"   Current parent district: {item.get('current_parent', '(unknown)')}\n"
            f"   Web results:\n{search_text or '    (none)'}"
        )

    if task_type == "state":
        instruction = """For each person, determine:
1. state: US state abbreviation (e.g., "TX", "CA") if US-based, or "INTL:[country]" if international (e.g., "INTL:India", "INTL:Canada")
2. confidence: "high", "medium", or "low"
3. reasoning: one sentence explaining how you determined location

Use ALL clues: email domain, company/school name, web search results, city names in snippets.
If the email domain contains a state pattern (e.g., .k12.tx.us), that's high confidence.
If web results mention a specific city/state, use that.
Homeschool families, private tutors, and hobbyists with gmail addresses — check web results for location clues.
If truly cannot determine, use state: "UNKNOWN".

Return ONLY a JSON array: [{"idx": 1, "state": "TX", "confidence": "high", "reasoning": "..."}]"""

    elif task_type == "title":
        instruction = """For each person, determine their job title/role based on web search results.

Rules:
- Search for them on school/district websites, staff directories, board pages — NOT LinkedIn (often outdated).
- Look for clues in search snippets: "teaches", "department chair", "principal at", "director of", etc.
- Use the company name as context: if it's a school, likely a teacher/admin; if a district, likely a coordinator/director.
- Be specific: "Computer Science Teacher" is better than "Teacher". "Curriculum Director" is better than "Director".
- Role bucket must be one of: teacher, admin, district_contact, library_contact, unknown
  - teacher = classroom teachers, coaches, instructional tech coaches, TOSAs, educators
  - admin = principals, assistant principals, deans, heads of school
  - district_contact = directors, coordinators, superintendents, specialists, technology leads
  - library_contact = librarians, media specialists
  - unknown = genuinely can't determine

Return ONLY a JSON array: [{"idx": 1, "title": "Computer Science Teacher", "role": "teacher", "confidence": "high"}]"""

    else:  # all
        instruction = """For each person, determine AS MANY of these as possible:
1. state: US state abbreviation or "INTL:[country]" or "UNKNOWN"
2. title: their job title (be specific)
3. role: one of teacher, admin, district_contact, library_contact, unknown
4. parent_district: the school district they belong to (if school-level entity)
5. is_international: true/false
6. country: if international, which country

Use ALL available clues: email domain patterns, company name, web search snippets, URLs.
School/district websites are the best source for titles — more reliable than LinkedIn.

Return ONLY a JSON array: [{"idx": 1, "state": "TX", "title": "CS Teacher", "role": "teacher", "parent_district": "Austin ISD", "is_international": false, "country": ""}]"""

    prompt = f"""{instruction}

People to analyze:
{chr(10).join(items_text)}"""

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90.0,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()

        # Parse JSON
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        bracket_idx = raw.find("[")
        if bracket_idx > 0:
            raw = raw[bracket_idx:]
        end_idx = raw.rfind("]")
        if end_idx > 0:
            raw = raw[:end_idx + 1]

        return json.loads(raw)
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return []


# ─────────────────────────────────────────────
# ROLE CLASSIFICATION
# ─────────────────────────────────────────────

TEACHER_KW = [
    "teacher", "instructor", "coach", "tosa", "facilitator", "educator",
    "professor", "tutor", "teaching",
]
ADMIN_KW = ["principal", "vice principal", "head of school", "dean", "headmaster"]
DISTRICT_KW = [
    "superintendent", "director", "coordinator", "specialist",
    "curriculum", "cto", "cio", "chief", "administrator",
    "manager", "supervisor", "technology", "innovation",
]
LIBRARY_KW = ["librarian", "library", "media specialist"]


def _classify_role_c4(title):
    t = (title or "").lower().strip()
    if not t:
        return "unknown"
    for kw in LIBRARY_KW:
        if kw in t:
            return "library_contact"
    for kw in ADMIN_KW:
        if kw in t:
            return "admin"
    for kw in DISTRICT_KW:
        if kw in t:
            return "district_contact"
    for kw in TEACHER_KW:
        if kw in t:
            return "teacher"
    return "unknown"


def extract_title_from_notes(notes):
    if not notes:
        return ""
    for part in notes.split("|"):
        part = part.strip()
        if part.startswith("Title:"):
            return part[6:].strip().replace("(enriched)", "").strip()
    return ""


def normalize_name(name):
    """Simple name normalization for matching."""
    return re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    service = get_sheets_service()
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]
    territory_id = os.environ.get("GOOGLE_SHEETS_TERRITORY_ID", "")

    # ══════════════════════════════════════════
    # LOAD ALL DATA SOURCES
    # ══════════════════════════════════════════

    logger.info("Loading all data sources...")

    # Prospecting Queue
    pq_rows = read_tab(service, sheet_id, "'Prospecting Queue'!A:S")
    pq_headers = pq_rows[0]
    all_prospects = []
    for row in pq_rows[1:]:
        padded = row + [""] * (len(pq_headers) - len(row))
        all_prospects.append(dict(zip(pq_headers, padded)))

    c4 = [p for p in all_prospects if p.get("Strategy") == "cold_license_request"]
    logger.info(f"C4 prospects: {len(c4)}")

    # Leads from Research (email → title, state, district)
    research_leads = rows_to_dicts(read_tab(service, sheet_id, "'Leads from Research'!A:K"))
    research_by_email = {}
    research_by_name = {}
    for lead in research_leads:
        em = lead.get("Email", "").strip().lower()
        if em:
            research_by_email[em] = lead
        name_key = normalize_name(f"{lead.get('First Name', '')} {lead.get('Last Name', '')}")
        if name_key and len(name_key) > 4:
            research_by_name[name_key] = lead
    logger.info(f"Leads from Research: {len(research_leads)} rows, {len(research_by_email)} emails")

    # Active Accounts (domain → state, district info)
    active_accounts = rows_to_dicts(read_tab(service, sheet_id, "'Active Accounts'!A:Z"))
    # Build domain → account mapping
    active_by_domain = {}
    active_by_name_key = {}
    for acc in active_accounts:
        name = acc.get("Display Name", "") or acc.get("Active Account Name", "")
        state = acc.get("State", "").strip()
        nk = normalize_name(name)
        if nk:
            active_by_name_key[nk] = {"name": name, "state": state, "type": acc.get("Account Type", "")}
    logger.info(f"Active Accounts: {len(active_accounts)} rows")

    # Territory Districts (name_key → state, district info)
    territory_districts = []
    district_by_name_key = {}
    district_by_leaid = {}
    if territory_id:
        territory_districts = rows_to_dicts(read_tab(service, territory_id, "'Territory Districts'!A:Q"))
        for d in territory_districts:
            nk = d.get("Name Key", "").strip() or normalize_name(d.get("District Name", ""))
            if nk:
                district_by_name_key[nk] = d
            leaid = d.get("LEAID", "").strip()
            if leaid:
                district_by_leaid[leaid] = d
        logger.info(f"Territory Districts: {len(territory_districts)} rows")

    # Territory Schools (name_key → parent district, state)
    territory_schools = []
    school_by_name_key = {}
    school_by_name_state = {}  # (normalized_name, state) → school
    if territory_id:
        territory_schools = rows_to_dicts(read_tab(service, territory_id, "'Territory Schools'!A:R"))
        for s in territory_schools:
            nk = s.get("Name Key", "").strip() or normalize_name(s.get("School Name", ""))
            state = s.get("State", "").strip()
            if nk:
                school_by_name_key[nk] = s
                if state:
                    school_by_name_state[(nk, state)] = s
        logger.info(f"Territory Schools: {len(territory_schools)} rows")

    # Build email domain → state lookup from ALL known data
    domain_state_lookup = {}
    # From territory districts
    for d in territory_districts:
        # Can't easily get domains from NCES, but state is there
        pass
    # From research leads (email domain → state)
    for lead in research_leads:
        em = lead.get("Email", "").strip().lower()
        state = lead.get("State", "").strip().upper()
        if em and state and "@" in em:
            domain = em.split("@")[1]
            if domain not in GENERIC_DOMAINS:
                domain_state_lookup[domain] = state
    # From active accounts we'd need email data, but we don't have emails on accounts
    logger.info(f"Domain → state lookup: {len(domain_state_lookup)} domains")

    # ══════════════════════════════════════════
    # ENRICHMENT PASS
    # ══════════════════════════════════════════

    # Track all updates: row_index → {field: new_value}
    # Row indices are 2-based (1-indexed, skip header)
    updates = {}  # row_idx → dict of updates

    def get_row_idx(prospect):
        """Find the 1-indexed row number in the sheet for this prospect."""
        email = prospect.get("Email", "").strip().lower()
        name_key = prospect.get("Name Key", "").strip()
        for i, row in enumerate(pq_rows[1:], start=2):
            padded = row + [""] * (len(pq_headers) - len(row))
            p = dict(zip(pq_headers, padded))
            if p.get("Strategy") != "cold_license_request":
                continue
            if email and p.get("Email", "").strip().lower() == email:
                return i
            if name_key and p.get("Name Key", "").strip() == name_key:
                return i
        return None

    # Pre-build row index for C4 prospects
    c4_row_indices = {}
    for i, row in enumerate(pq_rows[1:], start=2):
        padded = row + [""] * (len(pq_headers) - len(row))
        p = dict(zip(pq_headers, padded))
        if p.get("Strategy") == "cold_license_request":
            email = p.get("Email", "").strip().lower()
            if email:
                c4_row_indices[email] = i

    # ── TASK 1: Empty state prospects ──
    logger.info("\n" + "=" * 60)
    logger.info("TASK 1: Enriching 113 empty-state prospects")
    logger.info("=" * 60)

    empty_state = [p for p in c4 if not p.get("State", "").strip()]
    logger.info(f"Empty state count: {len(empty_state)}")

    state_enriched = 0
    international_found = 0
    need_serper_state = []

    for p in empty_state:
        email = p.get("Email", "").strip().lower()
        company = p.get("Account Name", "").strip()
        row_idx = c4_row_indices.get(email)
        if not row_idx:
            continue

        # Layer 1a: International detection
        intl = detect_international(email, company)
        if intl:
            if row_idx not in updates:
                updates[row_idx] = {}
            updates[row_idx]["international"] = intl
            international_found += 1
            logger.info(f"  INTL: {email} → {intl} ({company})")
            continue

        # Layer 1b: Email domain → state
        if email and "@" in email:
            domain = email.split("@")[1]
            # Direct k12/gov extraction
            st = extract_state_from_domain(email)
            if st:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["State"] = st
                state_enriched += 1
                logger.info(f"  Domain→State: {email} → {st}")
                continue

            # Known domain lookup
            if domain in domain_state_lookup:
                st = domain_state_lookup[domain]
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["State"] = st
                state_enriched += 1
                logger.info(f"  Known domain→State: {email} ({domain}) → {st}")
                continue

        # Layer 1c: Company name match against NCES
        comp_key = normalize_name(company)
        if comp_key and comp_key in district_by_name_key:
            d = district_by_name_key[comp_key]
            st = d.get("State", "").strip()
            if st:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["State"] = st
                updates[row_idx]["Parent District"] = d.get("District Name", "")
                state_enriched += 1
                logger.info(f"  NCES district match: {company} → {st}")
                continue

        if comp_key and comp_key in school_by_name_key:
            s = school_by_name_key[comp_key]
            st = s.get("State", "").strip()
            if st:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["State"] = st
                if s.get("District Name"):
                    updates[row_idx]["Parent District"] = s.get("District Name", "")
                state_enriched += 1
                logger.info(f"  NCES school match: {company} → {st}")
                continue

        # Layer 1d: Research leads cross-ref
        if email in research_by_email:
            lead = research_by_email[email]
            st = lead.get("State", "").strip().upper()
            if st:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["State"] = st
                if lead.get("District Name"):
                    updates[row_idx]["Parent District"] = lead.get("District Name", "")
                state_enriched += 1
                logger.info(f"  Research lead match: {email} → {st}")
                continue

        # Queue for Serper
        need_serper_state.append(p)

    logger.info(f"  Quick enrichment: {state_enriched} states found, {international_found} international")
    logger.info(f"  Need Serper search: {len(need_serper_state)}")

    # Serper search for remaining empty-state prospects
    if need_serper_state:
        logger.info("  Running Serper searches for empty-state prospects...")
        serper_state_items = []
        for p in need_serper_state:
            name = f"{p.get('First Name', '')} {p.get('Last Name', '')}".strip()
            company = p.get("Account Name", "").strip()
            email = p.get("Email", "").strip()
            # Search for school/person to find location
            if company and company != email:
                query = f'"{company}" location address'
            elif name:
                query = f'"{name}" teacher school district'
            else:
                continue
            serper_state_items.append({
                "email": email.lower(),
                "name": name,
                "company": company,
                "entity_type": p.get("Deal Level", ""),
                "query": query,
            })

        search_results = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for item in serper_state_items:
                f = executor.submit(serper_search, item["query"], 5)
                futures[f] = item
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results = future.result()
                    search_results[item["email"]] = {"results": results, "item": item}
                except Exception as e:
                    logger.warning(f"  Search error: {e}")

        logger.info(f"  Serper returned results for {len(search_results)} prospects")

        # Claude batch classification for state
        claude_state_batch = []
        for email, data in search_results.items():
            item = data["item"]
            item["search_results"] = data["results"]
            item["current_state"] = "(unknown)"
            item["current_title"] = extract_title_from_notes(
                next((p.get("Notes", "") for p in empty_state if p.get("Email", "").strip().lower() == email), "")
            ) or "(unknown)"
            item["current_parent"] = "(unknown)"
            claude_state_batch.append(item)

        claude_state_found = 0
        for batch_start in range(0, len(claude_state_batch), 20):
            batch = claude_state_batch[batch_start:batch_start + 20]
            results = claude_enrich_batch(batch, task_type="all")
            for r in results:
                idx = r.get("idx", 0) - 1
                if 0 <= idx < len(batch):
                    item = batch[idx]
                    email = item["email"]
                    row_idx = c4_row_indices.get(email)
                    if not row_idx:
                        continue
                    if row_idx not in updates:
                        updates[row_idx] = {}

                    st = r.get("state", "")
                    if st and st != "UNKNOWN":
                        if st.startswith("INTL:"):
                            updates[row_idx]["international"] = st
                            international_found += 1
                            logger.info(f"  Claude INTL: {email} → {st}")
                        elif st.upper() in US_STATE_ABBREVS:
                            updates[row_idx]["State"] = st.upper()
                            state_enriched += 1
                            logger.info(f"  Claude state: {email} → {st}")
                        claude_state_found += 1

                    title = r.get("title", "")
                    role = r.get("role", "")
                    if title and role != "unknown":
                        updates[row_idx]["title"] = title
                        updates[row_idx]["role"] = role

                    parent = r.get("parent_district", "")
                    if parent:
                        updates[row_idx]["Parent District"] = parent

            done = min(batch_start + 20, len(claude_state_batch))
            logger.info(f"  Claude state: processed {done}/{len(claude_state_batch)} ({claude_state_found} found)")

    logger.info(f"TASK 1 TOTAL: {state_enriched} states, {international_found} international")

    # ── TASK 2: Schools missing parent district ──
    logger.info("\n" + "=" * 60)
    logger.info("TASK 2: Schools missing parent district")
    logger.info("=" * 60)

    schools_no_parent = [
        p for p in c4
        if p.get("Deal Level", "").strip() == "school"
        and not p.get("Parent District", "").strip()
    ]
    logger.info(f"Schools without parent: {len(schools_no_parent)}")

    parent_enriched = 0
    for p in schools_no_parent:
        email = p.get("Email", "").strip().lower()
        company = p.get("Account Name", "").strip()
        state = p.get("State", "").strip()
        row_idx = c4_row_indices.get(email)
        if not row_idx:
            continue

        # Check if we already have an update from Task 1
        if row_idx in updates and updates[row_idx].get("Parent District"):
            parent_enriched += 1
            continue

        comp_key = normalize_name(company)

        # Try NCES school match with state
        if state and (comp_key, state) in school_by_name_state:
            s = school_by_name_state[(comp_key, state)]
            district = s.get("District Name", "").strip()
            if district:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["Parent District"] = district
                parent_enriched += 1
                logger.info(f"  NCES school+state: {company} ({state}) → {district}")
                continue

        # Try NCES school match without state
        if comp_key in school_by_name_key:
            s = school_by_name_key[comp_key]
            district = s.get("District Name", "").strip()
            if district:
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["Parent District"] = district
                # Also fill state if missing
                if not state and s.get("State", "").strip():
                    updates[row_idx]["State"] = s.get("State", "").strip()
                parent_enriched += 1
                logger.info(f"  NCES school: {company} → {district}")
                continue

        # Try fuzzy: strip common suffixes and try again
        stripped = comp_key
        for suffix in ["elementary", "middle", "high", "school", "academy", "charter",
                        "preparatory", "prep", "magnet", "center", "campus"]:
            stripped = stripped.replace(suffix, "").strip()
        stripped = re.sub(r"\s+", " ", stripped).strip()

        if stripped and stripped != comp_key:
            # Search all schools for substring match
            for sk, s_data in school_by_name_key.items():
                if stripped in sk or sk in stripped:
                    if not state or s_data.get("State", "") == state:
                        district = s_data.get("District Name", "").strip()
                        if district:
                            if row_idx not in updates:
                                updates[row_idx] = {}
                            updates[row_idx]["Parent District"] = district
                            parent_enriched += 1
                            logger.info(f"  Fuzzy NCES: {company} → {district}")
                            break

        # Try email domain match against NCES
        if email and "@" in email:
            domain = email.split("@")[1].lower()
            if domain not in GENERIC_DOMAINS:
                # Extract root from domain
                domain_root = domain.split(".")[0]
                # Search districts for domain root match
                for dk, d_data in district_by_name_key.items():
                    if domain_root in dk and len(domain_root) >= 4:
                        if not state or d_data.get("State", "") == state:
                            if row_idx not in updates:
                                updates[row_idx] = {}
                            updates[row_idx]["Parent District"] = d_data.get("District Name", "")
                            parent_enriched += 1
                            logger.info(f"  Domain→District: {domain} → {d_data.get('District Name', '')}")
                            break

    logger.info(f"TASK 2 TOTAL: {parent_enriched} parent districts found")

    # ── TASK 3: Missing titles ──
    logger.info("\n" + "=" * 60)
    logger.info("TASK 3: Enriching missing titles")
    logger.info("=" * 60)

    no_title = [
        p for p in c4
        if not extract_title_from_notes(p.get("Notes", ""))
        or _classify_role_c4(extract_title_from_notes(p.get("Notes", ""))) == "unknown"
    ]
    # Exclude ones where we already got a title from Task 1
    no_title_remaining = []
    for p in no_title:
        email = p.get("Email", "").strip().lower()
        row_idx = c4_row_indices.get(email)
        if row_idx and row_idx in updates and updates[row_idx].get("title"):
            continue
        no_title_remaining.append(p)

    logger.info(f"Missing usable title: {len(no_title_remaining)}")

    # Layer 3a: Research leads cross-ref by email
    title_from_research = 0
    still_need_title = []
    for p in no_title_remaining:
        email = p.get("Email", "").strip().lower()
        row_idx = c4_row_indices.get(email)
        if not row_idx:
            still_need_title.append(p)
            continue

        # Email match in research leads
        if email in research_by_email:
            lead = research_by_email[email]
            title = lead.get("Title", "").strip()
            if title and _classify_role_c4(title) != "unknown":
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["title"] = title
                updates[row_idx]["role"] = _classify_role_c4(title)
                title_from_research += 1
                continue

        # Name match in research leads
        name_key = normalize_name(f"{p.get('First Name', '')} {p.get('Last Name', '')}")
        if name_key and name_key in research_by_name:
            lead = research_by_name[name_key]
            title = lead.get("Title", "").strip()
            if title and _classify_role_c4(title) != "unknown":
                if row_idx not in updates:
                    updates[row_idx] = {}
                updates[row_idx]["title"] = title
                updates[row_idx]["role"] = _classify_role_c4(title)
                title_from_research += 1
                continue

        still_need_title.append(p)

    logger.info(f"  Research leads cross-ref: {title_from_research} titles found")
    logger.info(f"  Still need title: {len(still_need_title)}")

    # Layer 3b: Serper search — target school/district websites, staff directories
    logger.info("  Running Serper searches for titles (school/district websites)...")

    serper_title_items = []
    for p in still_need_title:
        name = f"{p.get('First Name', '')} {p.get('Last Name', '')}".strip()
        company = p.get("Account Name", "").strip()
        email = p.get("Email", "").strip()
        state = p.get("State", "").strip()

        if not name:
            continue

        # Build search query targeting school/district websites
        domain = ""
        if email and "@" in email:
            d = email.split("@")[1].lower()
            if d not in GENERIC_DOMAINS:
                domain = d

        if domain:
            # Best case: search on their own domain
            query = f'"{name}" site:{domain}'
        elif company and company != email:
            # Search school/district site for staff page
            query = f'"{name}" "{company}" staff directory OR teacher OR principal OR director'
            if state:
                query += f" {state}"
        else:
            continue

        serper_title_items.append({
            "email": email.lower(),
            "name": name,
            "company": company,
            "entity_type": p.get("Deal Level", ""),
            "current_state": state or "(unknown)",
            "current_title": "(unknown)",
            "current_parent": p.get("Parent District", "") or "(unknown)",
            "query": query,
        })

    # Parallel search
    title_search_results = {}
    batch_size = 50
    for batch_start in range(0, len(serper_title_items), batch_size):
        batch = serper_title_items[batch_start:batch_start + batch_size]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for item in batch:
                f = executor.submit(serper_search, item["query"], 3)
                futures[f] = item
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results = future.result()
                    if results:
                        title_search_results[item["email"]] = {"results": results, "item": item}
                except Exception:
                    pass

        done = min(batch_start + batch_size, len(serper_title_items))
        logger.info(f"  Searched {done}/{len(serper_title_items)} ({len(title_search_results)} with results)")

    logger.info(f"  Serper returned results for {len(title_search_results)} prospects")

    # Claude classification for titles
    claude_title_batch = []
    for email, data in title_search_results.items():
        item = data["item"]
        item["search_results"] = data["results"]
        claude_title_batch.append(item)

    claude_title_found = 0
    for batch_start in range(0, len(claude_title_batch), 20):
        batch = claude_title_batch[batch_start:batch_start + 20]
        results = claude_enrich_batch(batch, task_type="title")
        for r in results:
            idx = r.get("idx", 0) - 1
            if 0 <= idx < len(batch):
                item = batch[idx]
                email = item["email"]
                row_idx = c4_row_indices.get(email)
                if not row_idx:
                    continue

                title = r.get("title", "")
                role = r.get("role", "unknown")
                confidence = r.get("confidence", "low")

                if title and role != "unknown":
                    if row_idx not in updates:
                        updates[row_idx] = {}
                    updates[row_idx]["title"] = title
                    updates[row_idx]["role"] = role
                    claude_title_found += 1

        done = min(batch_start + 20, len(claude_title_batch))
        logger.info(f"  Claude title: processed {done}/{len(claude_title_batch)} ({claude_title_found} found)")

    logger.info(f"TASK 3 TOTAL: {title_from_research + claude_title_found} titles enriched")

    # ══════════════════════════════════════════
    # WRITE UPDATES TO SHEET
    # ══════════════════════════════════════════

    logger.info("\n" + "=" * 60)
    logger.info("TASK 4: Writing updates to Prospecting Queue")
    logger.info("=" * 60)

    # Column mapping: State=A(1), Account Name=B(2), ..., Parent District=G(7), Notes=S(19)
    col_map = {h: i for i, h in enumerate(pq_headers)}
    state_col = col_map.get("State", 0)       # A
    parent_col = col_map.get("Parent District", 6)  # G
    notes_col = col_map.get("Notes", 18)       # S

    sheet_updates = []
    intl_flagged = []

    for row_idx, upd in updates.items():
        # State update
        if "State" in upd:
            col_letter = _col_letter(state_col)  # A
            sheet_updates.append({
                "range": f"'Prospecting Queue'!{col_letter}{row_idx}",
                "values": [[upd["State"]]],
            })

        # Parent District update
        if "Parent District" in upd:
            col_letter = _col_letter(parent_col)  # G
            sheet_updates.append({
                "range": f"'Prospecting Queue'!{col_letter}{row_idx}",
                "values": [[upd["Parent District"]]],
            })

        # Title update → append to Notes
        if "title" in upd:
            # Read current notes
            current_row = pq_rows[row_idx - 1] if row_idx - 1 < len(pq_rows) else []
            current_notes = current_row[notes_col] if len(current_row) > notes_col else ""

            # Check if already has a title
            existing_title = extract_title_from_notes(current_notes)
            new_title = upd["title"]

            if existing_title:
                # Replace existing title
                new_notes = re.sub(
                    r"Title:\s*[^|]+(\s*\(enriched\))?",
                    f"Title: {new_title} (enriched-v2)",
                    current_notes,
                )
            else:
                if current_notes:
                    new_notes = current_notes + f" | Title: {new_title} (enriched-v2)"
                else:
                    new_notes = f"Title: {new_title} (enriched-v2)"

            col_letter = _col_letter(notes_col)  # S
            sheet_updates.append({
                "range": f"'Prospecting Queue'!{col_letter}{row_idx}",
                "values": [[new_notes]],
            })

        # International flag → append to Notes
        if "international" in upd:
            current_row = pq_rows[row_idx - 1] if row_idx - 1 < len(pq_rows) else []
            current_notes = current_row[notes_col] if len(current_row) > notes_col else ""
            new_notes = current_notes + f" | INTL: {upd['international']}"
            col_letter = _col_letter(notes_col)
            sheet_updates.append({
                "range": f"'Prospecting Queue'!{col_letter}{row_idx}",
                "values": [[new_notes]],
            })
            # Also get the email for reporting
            current_email = current_row[2] if len(current_row) > 2 else ""
            current_company = current_row[1] if len(current_row) > 1 else ""
            intl_flagged.append(f"{current_email} | {current_company} | {upd['international']}")

    logger.info(f"Total sheet updates to write: {len(sheet_updates)}")

    # Batch write
    for chunk_start in range(0, len(sheet_updates), 100):
        chunk = sheet_updates[chunk_start:chunk_start + 100]
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": chunk},
        ).execute()
        done = min(chunk_start + 100, len(sheet_updates))
        logger.info(f"  Written {done}/{len(sheet_updates)}")

    # ══════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════

    logger.info("\n" + "=" * 60)
    logger.info("FINAL ENRICHMENT SUMMARY")
    logger.info("=" * 60)

    # Count what changed
    states_added = sum(1 for u in updates.values() if "State" in u)
    parents_added = sum(1 for u in updates.values() if "Parent District" in u)
    titles_added = sum(1 for u in updates.values() if "title" in u)
    intl_count = sum(1 for u in updates.values() if "international" in u)

    logger.info(f"States resolved:     {states_added}")
    logger.info(f"Parents resolved:    {parents_added}")
    logger.info(f"Titles resolved:     {titles_added}")
    logger.info(f"International found: {intl_count}")
    logger.info(f"Total rows updated:  {len(updates)}")

    if intl_flagged:
        logger.info(f"\nInternational prospects flagged ({len(intl_flagged)}):")
        for item in intl_flagged:
            logger.info(f"  {item}")

    # Save detailed results
    output = {
        "states_added": states_added,
        "parents_added": parents_added,
        "titles_added": titles_added,
        "international": intl_count,
        "total_updated": len(updates),
        "international_list": intl_flagged,
        "updates": {
            str(row_idx): upd for row_idx, upd in updates.items()
        },
    }
    output_path = Path(__file__).resolve().parent / "c4_enrichment_pass2.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"\nDetailed results: {output_path}")


if __name__ == "__main__":
    main()
