#!/usr/bin/env python3
"""
Enrich C4 Cold License Request prospects with title/role data.

Layers (cheapest first):
  1. Re-query Outreach API for current titles
  2. Cross-reference SF Leads + SF Contacts tabs (email match)
  3. Serper web search (name + school/district)
  4. Claude classification from search results

Usage: python3 scripts/enrich_c4_titles.py
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

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheets_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def read_tab(service, sheet_id, tab_range):
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=tab_range)
        .execute()
    )
    return result.get("values", [])


# ─────────────────────────────────────────────
# OUTREACH API
# ─────────────────────────────────────────────

OUTREACH_API_BASE = "https://api.outreach.io/api/v2"
OUTREACH_TOKEN_URL = "https://api.outreach.io/oauth/token"

_outreach_access_token = ""
_outreach_refresh_token = ""
_outreach_expires_at = 0.0


def load_outreach_tokens():
    """Load Outreach OAuth tokens from GitHub."""
    global _outreach_access_token, _outreach_refresh_token, _outreach_expires_at

    gh_token = os.environ.get("GITHUB_TOKEN", "")
    resp = httpx.get(
        "https://api.github.com/repos/scadkin/firstcocoagent/contents/memory/outreach_tokens.json",
        headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3.raw"},
        timeout=15.0,
    )
    if resp.status_code == 200:
        data = json.loads(resp.text)
        _outreach_access_token = data.get("access_token", "")
        _outreach_refresh_token = data.get("refresh_token", "")
        _outreach_expires_at = data.get("expires_at", 0.0)
        logger.info(f"Outreach tokens loaded (user_id={data.get('user_id')})")
    else:
        logger.error(f"Could not load Outreach tokens: HTTP {resp.status_code}")
        sys.exit(1)


def refresh_outreach_token():
    """Refresh the Outreach access token."""
    global _outreach_access_token, _outreach_refresh_token, _outreach_expires_at

    resp = httpx.post(OUTREACH_TOKEN_URL, data={
        "client_id": os.environ.get("OUTREACH_CLIENT_ID", ""),
        "client_secret": os.environ.get("OUTREACH_CLIENT_SECRET", ""),
        "grant_type": "refresh_token",
        "refresh_token": _outreach_refresh_token,
    }, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    _outreach_access_token = data.get("access_token", "")
    _outreach_refresh_token = data.get("refresh_token", _outreach_refresh_token)
    _outreach_expires_at = time.time() + data.get("expires_in", 7200) - 60
    logger.info("Outreach token refreshed")


def outreach_get(path, params=None):
    """GET from Outreach API with auto-refresh."""
    global _outreach_access_token
    if time.time() >= _outreach_expires_at:
        refresh_outreach_token()

    headers = {
        "Authorization": f"Bearer {_outreach_access_token}",
        "Content-Type": "application/vnd.api+json",
    }
    resp = httpx.get(f"{OUTREACH_API_BASE}{path}", headers=headers, params=params, timeout=30.0)
    if resp.status_code == 401:
        refresh_outreach_token()
        headers["Authorization"] = f"Bearer {_outreach_access_token}"
        resp = httpx.get(f"{OUTREACH_API_BASE}{path}", headers=headers, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def outreach_get_all(path, params=None, max_pages=100):
    """Paginate through all results."""
    if params is None:
        params = {}
    params.setdefault("page[size]", "50")

    all_data = []
    pages = 0
    while pages < max_pages:
        result = outreach_get(path, params)
        data = result.get("data", [])
        all_data.extend(data)
        pages += 1
        next_link = result.get("links", {}).get("next")
        if not next_link or not data:
            break
        import urllib.parse
        parsed = urllib.parse.urlparse(next_link)
        next_params = dict(urllib.parse.parse_qsl(parsed.query))
        params.update(next_params)

    return all_data


# ─────────────────────────────────────────────
# SERPER API
# ─────────────────────────────────────────────

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")


def serper_search(query, num_results=5):
    """Search via Serper.dev. Returns list of {title, snippet, link}."""
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
        results = resp.json().get("organic", [])
        return [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "link": r.get("link", "")} for r in results]
    except Exception as e:
        logger.warning(f"Serper error for '{query[:50]}': {e}")
        return []


# ─────────────────────────────────────────────
# CLAUDE API
# ─────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def claude_classify_roles(batch):
    """
    Classify roles for a batch of prospects using Claude.
    batch: list of {name, company, email, search_results}
    Returns: list of {name, company, title, role_bucket}
    """
    if not ANTHROPIC_API_KEY:
        return []

    prompt_items = []
    for i, item in enumerate(batch):
        search_text = ""
        for r in item.get("search_results", [])[:3]:
            search_text += f"  - {r['title']}: {r['snippet']}\n"
        prompt_items.append(
            f"{i+1}. Name: {item['name']}\n"
            f"   Company: {item['company']}\n"
            f"   Email: {item['email']}\n"
            f"   Web results:\n{search_text or '   (none)'}"
        )

    prompt = f"""Classify each person's job title and role bucket based on their name, company (school/district), email, and web search results.

For each person, determine:
1. Their most likely job title (be specific: "CS Teacher", "Principal", "Curriculum Director", etc.)
2. Their role bucket: one of: teacher, admin, district_contact, library_contact, other

Rules:
- "teacher" = classroom teachers, coaches, instructional tech coaches, TOSAs
- "admin" = principals, assistant principals, deans, heads of school
- "district_contact" = directors, coordinators, superintendents, specialists, curriculum leads, CTOs, technology directors
- "library_contact" = librarians, media specialists
- "other" = can't determine from available data
- If the company name contains "school" (singular) and not "district", default to teacher/admin context
- If the company name contains "district" or "ISD" or "USD" etc, default to district_contact context
- Use email domain clues: k12 domains suggest education, specific school domains suggest school-level
- Be conservative — only assign a specific title if you have real evidence. "other" is fine.

Return ONLY a JSON array. No markdown, no explanation.
Each object: {{"idx": <1-based>, "title": "<specific title>", "role": "<bucket>"}}

People to classify:
{chr(10).join(prompt_items)}"""

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
            timeout=60.0,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

        # Strip preamble text before JSON
        bracket_idx = raw.find("[")
        if bracket_idx > 0:
            raw = raw[bracket_idx:]
        end_idx = raw.rfind("]")
        if end_idx > 0:
            raw = raw[:end_idx + 1]

        results = json.loads(raw)
        return results
    except Exception as e:
        logger.error(f"Claude classification error: {e}")
        return []


# ─────────────────────────────────────────────
# ROLE CLASSIFICATION
# ─────────────────────────────────────────────

TEACHER_KEYWORDS = [
    "teacher", "instructor", "coach", "tosa", "facilitator",
    "coding teacher", "stem teacher", "cs teacher", "computer science teacher",
    "esports", "robotics teacher", "game design", "web design", "engineering teacher",
    "makerspace", "digital learning coach", "instructional technology coach",
    "educator", "professor",
]
ADMIN_KEYWORDS = [
    "principal", "assistant principal", "vice principal", "head of school",
    "dean", "headmaster", "headmistress",
]
DISTRICT_KEYWORDS = [
    "superintendent", "director", "coordinator", "specialist",
    "curriculum", "cto", "cio", "ceo", "cao", "chief",
    "administrator", "manager", "supervisor",
    "technology", "innovation", "academic", "instruction",
]
LIBRARY_KEYWORDS = [
    "librarian", "library", "media specialist", "media center",
]


def classify_role(title):
    """Classify a title into a role bucket."""
    t = title.lower().strip()
    if not t:
        return "unknown"
    for kw in LIBRARY_KEYWORDS:
        if kw in t:
            return "library_contact"
    for kw in ADMIN_KEYWORDS:
        if kw in t:
            return "admin"
    for kw in DISTRICT_KEYWORDS:
        if kw in t:
            return "district_contact"
    for kw in TEACHER_KEYWORDS:
        if kw in t:
            return "teacher"
    return "other"


def extract_title_from_notes(notes):
    """Extract title from Notes column."""
    if not notes:
        return ""
    for part in notes.split("|"):
        part = part.strip()
        if part.startswith("Title:"):
            return part[6:].strip()
    return ""


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    sf_sheet_id = os.environ.get("GOOGLE_SHEETS_SF_ID", sheet_id)

    # ── Load Prospecting Queue ──
    logger.info("Loading Prospecting Queue...")
    service = get_sheets_service()
    rows = read_tab(service, sheet_id, "'Prospecting Queue'!A:S")
    headers = rows[0]
    prospects = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        prospects.append(dict(zip(headers, padded)))

    c4 = [p for p in prospects if p.get("Strategy") == "cold_license_request"]
    logger.info(f"C4 prospects: {len(c4)}")

    # Identify unknowns (no title in Notes)
    unknowns = []
    already_have_title = []
    for p in c4:
        title = extract_title_from_notes(p.get("Notes", ""))
        if title and classify_role(title) != "unknown":
            already_have_title.append(p)
        else:
            unknowns.append(p)

    logger.info(f"Already have title: {len(already_have_title)}")
    logger.info(f"Need enrichment: {len(unknowns)}")

    # Track enrichment results
    enriched = {}  # email -> {title, role, source}

    # ── Layer 1: Re-query Outreach API ──
    logger.info("\n=== LAYER 1: Outreach API re-query ===")
    load_outreach_tokens()

    # Build email → prospect mapping for unknowns
    email_to_prospect = {}
    for p in unknowns:
        email = p.get("Email", "").strip().lower()
        if email:
            email_to_prospect[email] = p

    # Pull prospects from the 3 license request sequences
    sequence_ids = [507, 1768, 1860]
    outreach_titles_found = 0

    for seq_id in sequence_ids:
        logger.info(f"  Scanning sequence {seq_id}...")
        try:
            states = outreach_get_all(
                "/sequenceStates",
                {"filter[sequence][id]": str(seq_id), "include": "prospect"}
            )
        except Exception as e:
            logger.warning(f"  Error scanning sequence {seq_id}: {e}")
            continue

        # Parse included prospects
        for item in states:
            # The included data might be in a different structure
            # When using get_all with pagination, we need the full response
            pass

    # Actually, let's query prospects directly by email for better efficiency
    # The sequence_states approach is slow. Let's batch lookup prospects.
    logger.info("  Batch querying Outreach prospects by email...")

    # Outreach doesn't support bulk email lookup easily.
    # Instead, pull all prospects from the 3 sequences and match.
    all_outreach_prospects = {}

    for seq_id in sequence_ids:
        logger.info(f"  Pulling sequence {seq_id} prospects...")
        page = 0
        params = {
            "filter[sequence][id]": str(seq_id),
            "include": "prospect",
            "page[size]": "50",
        }

        while page < 100:
            try:
                result = outreach_get("/sequenceStates", params)
            except Exception as e:
                logger.warning(f"  Error on page {page}: {e}")
                break

            data = result.get("data", [])
            included = result.get("included", [])

            # Build prospect map from included
            for inc in included:
                if inc.get("type") == "prospect":
                    pid = inc.get("id")
                    attrs = inc.get("attributes", {})
                    emails = [e.lower() for e in (attrs.get("emails") or [])]
                    title = (attrs.get("title") or "").strip()
                    if title and emails:
                        for em in emails:
                            if em not in all_outreach_prospects:
                                all_outreach_prospects[em] = title

            page += 1
            next_link = result.get("links", {}).get("next")
            if not next_link or not data:
                break
            import urllib.parse
            parsed = urllib.parse.urlparse(next_link)
            next_params = dict(urllib.parse.parse_qsl(parsed.query))
            params.update(next_params)

    logger.info(f"  Found {len(all_outreach_prospects)} Outreach prospects with titles")

    # Match against unknowns
    for email, prospect in email_to_prospect.items():
        if email in all_outreach_prospects:
            title = all_outreach_prospects[email]
            role = classify_role(title)
            if role != "unknown":
                enriched[email] = {"title": title, "role": role, "source": "outreach_api"}
                outreach_titles_found += 1

    logger.info(f"  Layer 1 result: {outreach_titles_found} titles found from Outreach")

    # ── Layer 2: SF Leads/Contacts cross-reference ──
    logger.info("\n=== LAYER 2: SF Leads/Contacts cross-reference ===")

    remaining = {e: p for e, p in email_to_prospect.items() if e not in enriched}
    logger.info(f"  Remaining unknowns: {len(remaining)}")

    sf_titles = {}  # email -> title

    # Read SF Leads tab
    try:
        sf_rows = read_tab(service, sf_sheet_id, "'SF Leads'!A:Z")
        if len(sf_rows) > 1:
            sf_headers = sf_rows[0]
            email_col = None
            title_col = None
            for i, h in enumerate(sf_headers):
                hl = h.lower().strip()
                if hl in ("email", "email address"):
                    email_col = i
                if hl in ("title", "job title"):
                    title_col = i
            if email_col is not None and title_col is not None:
                for row in sf_rows[1:]:
                    if len(row) > max(email_col, title_col):
                        em = row[email_col].strip().lower()
                        title = row[title_col].strip()
                        if em and title:
                            sf_titles[em] = title
                logger.info(f"  SF Leads: {len(sf_titles)} email→title pairs")
            else:
                logger.info(f"  SF Leads: email_col={email_col}, title_col={title_col}")
        else:
            logger.info("  SF Leads: no data")
    except Exception as e:
        logger.warning(f"  SF Leads read error: {e}")

    # Read SF Contacts tab
    try:
        sf_contact_rows = read_tab(service, sf_sheet_id, "'SF Contacts'!A:Z")
        if len(sf_contact_rows) > 1:
            sf_c_headers = sf_contact_rows[0]
            email_col = None
            title_col = None
            for i, h in enumerate(sf_c_headers):
                hl = h.lower().strip()
                if hl in ("email", "email address"):
                    email_col = i
                if hl in ("title", "job title"):
                    title_col = i
            if email_col is not None and title_col is not None:
                sf_contacts_count = 0
                for row in sf_contact_rows[1:]:
                    if len(row) > max(email_col, title_col):
                        em = row[email_col].strip().lower()
                        title = row[title_col].strip()
                        if em and title and em not in sf_titles:
                            sf_titles[em] = title
                            sf_contacts_count += 1
                logger.info(f"  SF Contacts: added {sf_contacts_count} more email→title pairs")
            else:
                logger.info(f"  SF Contacts: email_col={email_col}, title_col={title_col}")
        else:
            logger.info("  SF Contacts: no data")
    except Exception as e:
        logger.warning(f"  SF Contacts read error: {e}")

    # Also read the main "Leads from Research" tab
    try:
        leads_rows = read_tab(service, sheet_id, "'Leads from Research'!A:Z")
        if len(leads_rows) > 1:
            l_headers = leads_rows[0]
            email_col = None
            title_col = None
            for i, h in enumerate(l_headers):
                hl = h.lower().strip()
                if hl in ("email", "email address"):
                    email_col = i
                if hl in ("title", "role", "job title"):
                    title_col = i
            if email_col is not None and title_col is not None:
                research_count = 0
                for row in leads_rows[1:]:
                    if len(row) > max(email_col, title_col):
                        em = row[email_col].strip().lower()
                        title = row[title_col].strip()
                        if em and title and em not in sf_titles:
                            sf_titles[em] = title
                            research_count += 1
                logger.info(f"  Leads from Research: added {research_count} more")
    except Exception as e:
        logger.warning(f"  Leads from Research read error: {e}")

    logger.info(f"  Total SF/Research email→title pairs: {len(sf_titles)}")

    sf_found = 0
    for email in remaining:
        if email in sf_titles:
            title = sf_titles[email]
            role = classify_role(title)
            if role != "unknown":
                enriched[email] = {"title": title, "role": role, "source": "sf_crossref"}
                sf_found += 1

    logger.info(f"  Layer 2 result: {sf_found} titles found from SF/Research data")

    # ── Layer 3: Serper web search ──
    logger.info("\n=== LAYER 3: Serper web search ===")

    remaining = {e: p for e, p in email_to_prospect.items() if e not in enriched}
    logger.info(f"  Remaining unknowns: {len(remaining)}")

    # Build search queries
    search_items = []
    for email, p in remaining.items():
        first = p.get("First Name", "").strip()
        last = p.get("Last Name", "").strip()
        company = p.get("Account Name", "").strip()
        name = f"{first} {last}".strip()
        if name and company:
            search_items.append({
                "email": email,
                "name": name,
                "company": company,
                "query": f'"{name}" "{company}" site:linkedin.com OR site:.k12 OR site:.edu',
            })
        elif name and email and "@" in email:
            domain = email.split("@")[1]
            search_items.append({
                "email": email,
                "name": name,
                "company": company or domain,
                "query": f'"{name}" "{domain}" teacher OR director OR principal OR coordinator',
            })

    logger.info(f"  Searching for {len(search_items)} prospects...")

    # Parallel Serper searches (max 10 concurrent)
    search_results = {}  # email -> [results]
    serper_cost = 0

    def do_search(item):
        results = serper_search(item["query"], num_results=3)
        return item["email"], results

    batch_size = 50  # Process in batches to show progress
    for batch_start in range(0, len(search_items), batch_size):
        batch = search_items[batch_start:batch_start + batch_size]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(do_search, item): item for item in batch}
            for future in as_completed(futures):
                try:
                    email, results = future.result()
                    search_results[email] = results
                    serper_cost += 1
                except Exception as e:
                    logger.warning(f"  Search error: {e}")

        done = min(batch_start + batch_size, len(search_items))
        logger.info(f"  Searched {done}/{len(search_items)} ({len(search_results)} with results)")

    # Quick extraction from search results (look for title in snippets)
    title_patterns = [
        r"(?:^|\W)(teacher|principal|superintendent|director|coordinator|librarian|specialist|coach|instructor|administrator|dean)(?:\W|$)",
    ]
    serper_direct_found = 0
    need_claude = []

    for email in remaining:
        if email in enriched:
            continue
        results = search_results.get(email, [])
        if not results:
            continue

        # Try direct extraction from snippets
        combined_text = " ".join(r.get("snippet", "") + " " + r.get("title", "") for r in results).lower()

        found_title = None
        # Look for LinkedIn-style titles
        linkedin_match = re.search(r"[-–—]\s*([^-–—|]+?)(?:\s*[-–—|]|\s*at\s)", combined_text)
        if linkedin_match:
            candidate = linkedin_match.group(1).strip()
            if len(candidate) > 3 and classify_role(candidate) != "unknown":
                found_title = candidate

        if found_title:
            role = classify_role(found_title)
            enriched[email] = {"title": found_title.title(), "role": role, "source": "serper_direct"}
            serper_direct_found += 1
        else:
            # Queue for Claude classification
            p = remaining[email]
            need_claude.append({
                "email": email,
                "name": f"{p.get('First Name', '')} {p.get('Last Name', '')}".strip(),
                "company": p.get("Account Name", ""),
                "search_results": results,
            })

    logger.info(f"  Layer 3 direct extraction: {serper_direct_found} found")
    logger.info(f"  Need Claude classification: {len(need_claude)}")

    # ── Layer 4: Claude batch classification ──
    logger.info("\n=== LAYER 4: Claude classification ===")

    claude_found = 0
    claude_batch_size = 25  # 25 at a time

    for batch_start in range(0, len(need_claude), claude_batch_size):
        batch = need_claude[batch_start:batch_start + claude_batch_size]
        results = claude_classify_roles(batch)

        for r in results:
            idx = r.get("idx", 0) - 1  # 1-based to 0-based
            if 0 <= idx < len(batch):
                item = batch[idx]
                title = r.get("title", "")
                role = r.get("role", "other")
                if title and role != "other":
                    enriched[item["email"]] = {"title": title, "role": role, "source": "claude"}
                    claude_found += 1
                elif title:
                    # Even "other" with a title is useful
                    enriched[item["email"]] = {"title": title, "role": role, "source": "claude"}
                    claude_found += 1

        done = min(batch_start + claude_batch_size, len(need_claude))
        logger.info(f"  Classified {done}/{len(need_claude)} ({claude_found} found so far)")

    logger.info(f"  Layer 4 result: {claude_found} classified by Claude")

    # ── SUMMARY ──
    logger.info("\n" + "=" * 60)
    logger.info("ENRICHMENT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Started with {len(unknowns)} unknowns")
    logger.info(f"Total enriched: {len(enriched)}")

    by_source = Counter(v["source"] for v in enriched.values())
    for source, count in by_source.most_common():
        logger.info(f"  {source}: {count}")

    still_unknown = len(unknowns) - len(enriched)
    logger.info(f"Still unknown: {still_unknown}")

    # Combine already_have_title + enriched for full role breakdown
    all_roles = Counter()
    for p in already_have_title:
        title = extract_title_from_notes(p.get("Notes", ""))
        all_roles[classify_role(title)] += 1
    for v in enriched.values():
        all_roles[v["role"]] += 1
    all_roles["unknown"] = still_unknown

    logger.info(f"\nFINAL ROLE BREAKDOWN (all {len(c4)} C4 prospects):")
    for role, count in all_roles.most_common():
        pct = count / len(c4) * 100
        logger.info(f"  {role:20s}: {count:5d} ({pct:.1f}%)")

    # ── Write enrichment results to a JSON file for next step ──
    output = {
        "total_c4": len(c4),
        "enriched_count": len(enriched),
        "still_unknown": still_unknown,
        "already_had_title": len(already_have_title),
        "by_source": dict(by_source),
        "role_breakdown": dict(all_roles),
        "serper_queries": serper_cost,
        "enrichments": {
            email: {
                "title": v["title"],
                "role": v["role"],
                "source": v["source"],
                "name": email_to_prospect[email].get("First Name", "") + " " + email_to_prospect[email].get("Last Name", ""),
                "company": email_to_prospect[email].get("Account Name", ""),
                "state": email_to_prospect[email].get("State", ""),
            }
            for email, v in enriched.items()
        },
    }

    output_path = Path(__file__).resolve().parent.parent / "scripts" / "c4_enrichment_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"\nResults written to {output_path}")

    # ── Also update the Prospecting Queue Notes with enriched titles ──
    logger.info("\n=== Updating Prospecting Queue with enriched titles ===")
    updates = []
    for i, row in enumerate(rows[1:], start=2):  # 1-indexed, skip header
        padded = row + [""] * (len(headers) - len(row))
        p = dict(zip(headers, padded))
        if p.get("Strategy") != "cold_license_request":
            continue
        email = p.get("Email", "").strip().lower()
        if email in enriched:
            existing_notes = p.get("Notes", "")
            existing_title = extract_title_from_notes(existing_notes)
            if not existing_title:
                # Add title to notes
                new_title = enriched[email]["title"]
                if existing_notes:
                    new_notes = existing_notes + f" | Title: {new_title} (enriched)"
                else:
                    new_notes = f"Title: {new_title} (enriched)"
                # Notes is column S (index 19 = column 19 = S)
                updates.append({
                    "range": f"'Prospecting Queue'!S{i}",
                    "values": [[new_notes]],
                })

    if updates:
        # Batch update in chunks of 100
        for chunk_start in range(0, len(updates), 100):
            chunk = updates[chunk_start:chunk_start + 100]
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={"valueInputOption": "RAW", "data": chunk},
            ).execute()
            logger.info(f"  Updated {min(chunk_start + 100, len(updates))}/{len(updates)} rows")

    logger.info(f"  Total rows updated in sheet: {len(updates)}")
    logger.info("\nDone!")


if __name__ == "__main__":
    main()
