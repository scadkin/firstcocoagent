#!/usr/bin/env python3
"""Build memory/csta_roster.json — CSTA chapter leader roster with per-state
extraction + district resolver pass.

Session 58 rewrite — fixes the saturation problem where a single Haiku call
on the full 610K-char corpus silently drops state chapter members in favor
of the louder national CSTA content. Splits extraction by state bucket.
Then resolves missing K-12 employer districts via Serper + Haiku reverse
lookup for territory-state entries.

Pipeline:
  Phase 1 (Discovery): Serper queries find CSTA chapter pages on csteachers.org
    subdomains + LinkedIn snippets for each territory state.
  Phase 2 (Fetch): httpx + BeautifulSoup fetch each csteachers.org URL with a
    browser User-Agent. Bucket URLs by state subdomain prefix.
  Phase 3 (Per-state extraction): Haiku extraction, one call per state bucket
    plus one call for the national bucket. Per-state prompts inject the state
    code so Haiku correctly tags employer state by default.
  Phase 4 (District resolver): For territory-state entries still missing a
    district, run Serper `"{name}" "computer science" teacher {state_name}`
    and feed snippets to Haiku for a reverse-lookup employer extraction.
  Phase 5 (Dedup + write).

Run: python3 scripts/fetch_csta_roster.py
Output: memory/csta_roster.json
Cost: ~$0.40 one-time (Serper + Haiku, up from ~$0.10 for the v1 single-call
      version).
Refresh: manually, quarterly or when CSTA announces new chapter boards.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ for _env

# Audit theme #4 (S70): shared .env loader replaces raw FileNotFoundError
# on missing .env and raw KeyError on missing vars.
from _env import load_env_or_die  # noqa: E402
load_env_or_die(required=["SERPER_API_KEY", "ANTHROPIC_API_KEY"])

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from tools.signal_processor import TERRITORY_STATES_WITH_CA, ABBR_TO_STATE_NAME, SERPER_URL  # noqa: E402
from tools import csv_importer  # noqa: E402

SERPER_KEY = os.environ["SERPER_API_KEY"]  # guaranteed by load_env_or_die above

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

NATIONAL_SEEDS = [
    "https://csteachers.org/board-of-directors/",
    "https://csteachers.org/team/",
]

OUTPUT_PATH = ROOT / "memory" / "csta_roster.json"

# Subdomain → state code map for URL-based bucketing
STATE_SUBDOMAIN_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "newhampshire": "NH", "newjersey": "NJ", "newmexico": "NM", "newyork": "NY",
    "northcarolina": "NC", "northdakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhodeisland": "RI", "southcarolina": "SC",
    "southdakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "westvirginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

# Regional CSTA subchapters that live on csteachers.org subdomains but don't
# match a single state name. Map them to their parent state explicitly.
REGIONAL_SUBDOMAIN_TO_STATE = {
    # California regional chapters
    "goldengate": "CA",
    "greaterlosangeles": "CA",
    "siliconvalley": "CA",
    "sanmateocounty": "CA",
    "sanmateo": "CA",
    "sacramento": "CA",
    "sandiego": "CA",
    "orange": "CA",
    "orangecounty": "CA",
    "ca-socal": "CA",
    "ca-southbay": "CA",
    "pasadena": "CA",
    "castanislaus": "CA",
    "centralvalley": "CA",
    "far-north": "CA",
    "inland-empire": "CA",
    # Pennsylvania regional chapters
    "pittsburgh": "PA",
    "philly": "PA",
    "philadelphia": "PA",
    "susquehannavalley": "PA",
    "susquehanna": "PA",
    # Texas regional chapters
    "dallasfortworth": "TX",
    "dallas": "TX",
    "houston": "TX",
    "austin": "TX",
    "sanantonio": "TX",
    # Massachusetts regional
    "greaterboston": "MA",
    "boston": "MA",
    # Illinois regional
    "chicagosuburban": "IL",
    "chicago": "IL",
    # NJ regional (non-territory but catch for accuracy)
    "cstanj": "NJ",
}

# Additional explicit state chapter URLs to probe directly (bypass Serper)
# for territory states. Ensures discovery even when Serper ranking drops them.
# IMPORTANT: CA/PA/TX state-level subdomains DO NOT RESOLVE (DNS error) — those
# states use regional chapter subdomains only. Use regional URLs instead.
EXPLICIT_STATE_CHAPTER_URLS = {
    "CA": [
        "https://goldengate.csteachers.org/",
        "https://greaterlosangeles.csteachers.org/",
        "https://siliconvalley.csteachers.org/",
        "https://sacramento.csteachers.org/",
        "https://sandiego.csteachers.org/",
        "https://orange.csteachers.org/",
        "https://farnorthca.csteachers.org/",
    ],
    "IL": ["https://illinois.csteachers.org/"],
    "PA": [
        "https://pittsburgh.csteachers.org/",
        "https://philly.csteachers.org/",
        "https://susquehanna.csteachers.org/",
    ],
    "OH": ["https://ohio.csteachers.org/"],
    "MI": ["https://michigan.csteachers.org/"],
    "CT": ["https://connecticut.csteachers.org/"],
    "OK": ["https://oklahoma.csteachers.org/"],
    "MA": ["https://massachusetts.csteachers.org/"],
    "IN": ["https://indiana.csteachers.org/"],
    "NV": [
        "https://nevada.csteachers.org/",
        "https://community.csteachers.org/cstanevadasilverstate/home",
    ],
    "TN": ["https://tennessee.csteachers.org/"],
    "NE": ["https://nebraska.csteachers.org/"],
    "TX": [
        "https://dallasfortworth.csteachers.org/",
        "https://houston.csteachers.org/",
        "https://austin.csteachers.org/",
    ],
}

# High-value community forum seed threads. The CSTA community digest thread
# below has ~30 state chapter leader posts from multiple states in one page
# — the Session 57 baseline roster sourced most of its non-CA entries from
# this thread. Must be fetched and extracted via the national bucket.
COMMUNITY_SEED_URLS = [
    "https://community.csteachers.org/communities/community-home/digestviewer/viewthread?GroupId=121&MessageKey=1675f53d-3da1-49d2-bbb7-687c03b42080&CommunityKey=3fe0a7c8-7160-491f-905f-390b7dbc0e92&hlmlt=VT",
]

# National URL whitelist — only these path patterns go into the national
# bucket. Filters out PD articles, event calendars, and other noise that
# caused Haiku to return empty on the previous run.
NATIONAL_URL_WHITELIST_PATTERNS = (
    "/team/",
    "/board-of-directors",
    "/chapters/",
    "/csta-board-corner",
    "/csta-volunteer-spotlight",
    "/meet-",
    "/award-winners",
    "/communities/community-home/digestviewer",
    "/volunteer",
)


# ──────────────────────────────────────────────────────────
# Phase 1 — Discovery
# ──────────────────────────────────────────────────────────


def serper_search(query: str, num: int = 10) -> list[dict]:
    r = httpx.post(
        SERPER_URL,
        headers={"X-API-Key": SERPER_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=20.0,
    )
    return r.json().get("organic", [])


def discover_csteachers_urls_and_linkedin_snippets() -> tuple[set[str], list[dict]]:
    """Returns (csteachers_urls, linkedin_snippets).
    LinkedIn snippets are extracted from Serper directly (no fetch, LinkedIn
    403s anonymous bots)."""
    cst_urls: set[str] = set()
    linkedin_snippets: list[dict] = []

    for state_abbr in sorted(TERRITORY_STATES_WITH_CA):
        state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr).title()
        queries = [
            f'site:csteachers.org "{state_name}" chapter',
            f'site:linkedin.com "CSTA {state_name}" president OR officer OR board',
        ]
        for q in queries:
            try:
                orgs = serper_search(q, num=10)
                for item in orgs:
                    link = item.get("link", "")
                    if "csteachers.org" in link:
                        cst_urls.add(link)
                    elif "linkedin.com" in link:
                        snippet = item.get("snippet", "")
                        title = item.get("title", "")
                        if snippet or title:
                            linkedin_snippets.append(
                                {
                                    "title": title,
                                    "snippet": snippet,
                                    "url": link,
                                    "state_hint": state_abbr,
                                }
                            )
                time.sleep(0.5)
            except Exception as e:
                print(f"  [warn] Serper failed for {state_abbr} / {q[:40]}: {e}", file=sys.stderr)

    # Always include national seeds
    for url in NATIONAL_SEEDS:
        cst_urls.add(url)

    # Community forum digest threads — source of ~30 baseline entries
    for url in COMMUNITY_SEED_URLS:
        cst_urls.add(url)

    # Always include explicit state chapter URLs for territory states —
    # guarantees discovery even if Serper didn't surface them this run.
    for state_code, urls in EXPLICIT_STATE_CHAPTER_URLS.items():
        if state_code in TERRITORY_STATES_WITH_CA:
            for u in urls:
                cst_urls.add(u)

    return cst_urls, linkedin_snippets


def is_national_signal_url(url: str) -> bool:
    """Return True if the URL should survive into the national bucket.
    Filters out noise (PD articles, event calendars, jobs, schoolsofed, etc.)."""
    # Skip jobs subdomain, conference subdomain, landscape subdomain
    lower = url.lower()
    if any(x in lower for x in ("jobs.csteachers.org", "conference.csteachers.org",
                                  "landscape.csteachers.org", "my.csteachers.org")):
        return False
    # Keep if any whitelist pattern matches
    return any(p in url for p in NATIONAL_URL_WHITELIST_PATTERNS)


# ──────────────────────────────────────────────────────────
# Phase 2 — Fetch
# ──────────────────────────────────────────────────────────


def fetch_page_text(url: str) -> str:
    """Fetch a URL with browser UA and return extracted text. Empty on error."""
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": BROWSER_UA},
            timeout=20.0,
            follow_redirects=True,
        )
        if r.status_code >= 400:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000]
    except Exception as e:
        print(f"  [warn] fetch failed for {url}: {e}", file=sys.stderr)
        return ""


def url_to_state_code(url: str) -> str:
    """Extract state code from URL subdomain pattern like 'https://michigan.csteachers.org/...'.
    Returns '' if URL doesn't match a state subdomain (e.g. bare csteachers.org)."""
    m = re.match(r"https?://([a-z-]+)\.csteachers\.org", url.lower())
    if m:
        sub = m.group(1)
        # Try state-name match first
        if sub in STATE_SUBDOMAIN_TO_CODE:
            return STATE_SUBDOMAIN_TO_CODE[sub]
        # Then regional chapter match
        if sub in REGIONAL_SUBDOMAIN_TO_STATE:
            return REGIONAL_SUBDOMAIN_TO_STATE[sub]
        return ""
    # community.csteachers.org/csta{state}/... or /csta{state}silverstate/...
    m2 = re.search(r"community\.csteachers\.org/csta([a-z]+?)silverstate", url.lower())
    if m2:
        sub = m2.group(1)
        return STATE_SUBDOMAIN_TO_CODE.get(sub, "")
    m3 = re.search(r"community\.csteachers\.org/csta([a-z-]+)/", url.lower())
    if m3:
        sub = m3.group(1)
        if sub in STATE_SUBDOMAIN_TO_CODE:
            return STATE_SUBDOMAIN_TO_CODE[sub]
        if sub in REGIONAL_SUBDOMAIN_TO_STATE:
            return REGIONAL_SUBDOMAIN_TO_STATE[sub]
    return ""


def bucket_urls_by_state(urls: set[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Partition URLs into state buckets + a national bucket (whitelisted).
    Returns (state_buckets, national_list). Non-signal national URLs are
    dropped entirely — the national bucket gets only team/volunteer/award/
    digestviewer pages."""
    state_buckets: dict[str, list[str]] = {}
    national: list[str] = []
    dropped = 0
    for u in sorted(urls):
        code = url_to_state_code(u)
        if code:
            state_buckets.setdefault(code, []).append(u)
            continue
        if is_national_signal_url(u):
            national.append(u)
        else:
            dropped += 1
    if dropped:
        print(f"  [note] Filtered {dropped} non-signal national URLs (PD articles, calendars, jobs)")
    return state_buckets, national


# ──────────────────────────────────────────────────────────
# Phase 3 — Per-state Haiku extraction
# ──────────────────────────────────────────────────────────


PER_STATE_PROMPT_TEMPLATE = """Extract CSTA (Computer Science Teachers Association) chapter board members and officers from these pages.

CONTEXT: These pages are specifically for the CSTA {state_name} chapter (state code: {state_code}). Default `state` to "{state_code}" for every person unless the page EXPLICITLY says the person teaches in a different state.

For each person, return JSON:
{{
  "name": "Full name",
  "role": "Chapter role — e.g. 'President', 'Vice President', 'Secretary', 'K-12 Board Member', 'Treasurer', 'Chapter Leader'",
  "chapter": "CSTA chapter name — e.g. 'CSTA {state_name}', 'CSTA Pittsburgh'",
  "state": "2-letter state code — MUST default to '{state_code}' unless page says otherwise",
  "district": "Exact K-12 school district name where this person works. Empty string '' if the page does not explicitly name a district — do NOT guess, do NOT use the chapter city as a district, do NOT fabricate.",
  "source_url": "Copy one of the '===== URL:' lines from the input that mentions this person. Do not fabricate."
}}

STRICT RULES:
- SKIP university professors and college advisors — K-12 only.
- SKIP general CSTA national HQ staff unless they ALSO hold this state chapter role.
- SKIP conference speakers unless explicitly listed as chapter officers.
- `state` MUST be a 2-letter uppercase code. Default to "{state_code}".
- `district` must be a named K-12 LEA. Return "" if the page just says "computer science teacher" without naming a district.
- Return ONLY a valid JSON array. Empty array [] if nothing qualifies.

Pages:
{corpus}"""


NATIONAL_PROMPT = """Extract every CSTA (Computer Science Teachers Association) STATE or REGIONAL chapter member, officer, or board member mentioned anywhere in these pages. Be INCLUSIVE — articles, event recaps, volunteer spotlights, award winners, and team bios are all valid sources if they mention someone's state chapter role.

For each person, return JSON:
{
  "name": "Full name",
  "role": "Chapter role or volunteer position. Use 'Volunteer' if no specific title.",
  "chapter": "CSTA chapter name (e.g. 'CSTA Pittsburgh', 'CSTA Dallas Fort Worth', 'CSTA Greater Boston')",
  "state": "2-letter state code of their K-12 SCHOOL EMPLOYER",
  "district": "Exact K-12 school district name. Empty '' if not explicit.",
  "source_url": "Copy one of the '===== URL:' lines from the input that mentions this person."
}

INCLUDE:
- State/regional chapter presidents, officers, board members, volunteer leads
- Chapter spotlight subjects named as chapter members/volunteers
- People described as working with or leading a specific CSTA state/regional chapter
- Team members of national CSTA who ALSO hold or previously held a state chapter role

SKIP:
- Pure national CSTA Board of Directors entries (no state chapter tie)
- University professors and higher-ed (K-12 only)
- Conference speakers with NO chapter affiliation mentioned

RULES:
- `state` MUST be a 2-letter uppercase code. Do not return full state names.
- `district` must be a named K-12 LEA. Return "" if not explicit — the district resolver will pick it up later.
- Return ONLY a valid JSON array. Empty array [] if nothing qualifies.

Pages:
"""


def haiku_extract(prompt: str, label: str = "") -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(timeout=120.0)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=6000,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    clean = raw
    if "```" in clean:
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    start, end = clean.find("["), clean.rfind("]")
    if start == -1 or end == -1:
        print(f"  [warn] Haiku returned no JSON array for {label}", file=sys.stderr)
        print(f"  raw: {raw[:400]}", file=sys.stderr)
        return []
    try:
        return json.loads(clean[start : end + 1])
    except json.JSONDecodeError as e:
        print(f"  [warn] JSON parse failed for {label}: {e}", file=sys.stderr)
        return []


def build_state_corpus(state_code: str, urls: list[str], linkedin_snippets: list[dict]) -> str:
    """Build a focused corpus for one state bucket."""
    blocks = []
    for url in urls:
        print(f"    fetching {url}")
        text = fetch_page_text(url)
        if not text:
            continue
        blocks.append(f"\n===== URL: {url}\n{text}\n")

    # Add LinkedIn snippets for this state
    state_snippets = [ls for ls in linkedin_snippets if ls.get("state_hint") == state_code]
    if state_snippets:
        blocks.append("\n===== LinkedIn snippets =====")
        for ls in state_snippets:
            blocks.append(
                f"\n-- [{ls.get('state_hint','')}] {ls.get('title','')}\n"
                f"URL: {ls.get('url','')}\n"
                f"{ls.get('snippet','')}\n"
            )
    return "".join(blocks)


def build_national_corpus(urls: list[str]) -> str:
    """Build the national bucket corpus."""
    blocks = []
    for url in urls:
        print(f"    fetching {url}")
        text = fetch_page_text(url)
        if not text:
            continue
        blocks.append(f"\n===== URL: {url}\n{text}\n")
    return "".join(blocks)


def extract_per_state(
    state_buckets: dict[str, list[str]],
    national_urls: list[str],
    linkedin_snippets: list[dict],
) -> list[dict]:
    """Run Haiku once per state bucket + once for national. Merge results."""
    all_items: list[dict] = []

    # Per-state calls
    for state_code in sorted(state_buckets.keys()):
        state_name = ABBR_TO_STATE_NAME.get(state_code, state_code).title()
        urls = state_buckets[state_code]
        print(f"\n  === State bucket: {state_code} ({state_name}) — {len(urls)} URLs ===")
        corpus = build_state_corpus(state_code, urls, linkedin_snippets)
        if not corpus.strip():
            print(f"    (empty corpus, skipping)")
            continue
        prompt = PER_STATE_PROMPT_TEMPLATE.format(
            state_name=state_name,
            state_code=state_code,
            corpus=corpus[:500000],
        )
        items = haiku_extract(prompt, label=state_code)
        print(f"    → Haiku returned {len(items)} items for {state_code}")
        all_items.extend(items)

    # National bucket — cap at 150K chars to avoid Haiku saturation
    print(f"\n  === National bucket — {len(national_urls)} URLs ===")
    national_corpus = build_national_corpus(national_urls)
    if national_corpus.strip():
        capped = national_corpus[:150000]
        if len(national_corpus) > 150000:
            print(f"    (capped corpus at 150K chars, dropped {len(national_corpus)-150000:,})")
        prompt = NATIONAL_PROMPT + capped
        items = haiku_extract(prompt, label="national")
        print(f"    → Haiku returned {len(items)} items for national")
        all_items.extend(items)

    return all_items


# ──────────────────────────────────────────────────────────
# Phase 4 — District resolver (for entries with empty district)
# ──────────────────────────────────────────────────────────


def resolve_district(name: str, state_code: str) -> tuple[str, str]:
    """Reverse-lookup employer district for a CSTA chapter leader.
    Returns (district_name, confidence) where confidence is high|medium|low|none.
    Only called for territory-state entries with empty district."""
    state_name = ABBR_TO_STATE_NAME.get(state_code, state_code).title()
    queries = [
        f'"{name}" "computer science" teacher {state_name}',
        f'"{name}" CSTA {state_name} school district',
    ]
    all_snippets = []
    for q in queries:
        try:
            orgs = serper_search(q, num=5)
            for o in orgs[:5]:
                title = o.get("title", "")
                snippet = o.get("snippet", "")
                link = o.get("link", "")
                if snippet or title:
                    all_snippets.append(f"- [{title[:80]}] {snippet[:200]} (source: {link[:80]})")
            time.sleep(0.4)
        except Exception as e:
            print(f"      [warn] resolver Serper failed for {name}: {e}", file=sys.stderr)

    if not all_snippets:
        return "", "none"

    snippets_text = "\n".join(all_snippets[:12])
    prompt = f"""Based ONLY on these search results, what K-12 school district does {name} currently work at in {state_name}?

Rules:
- Return exactly: `district_name|confidence` where confidence is high, medium, low, or none.
- Return `|none` if no district is clearly named in the snippets.
- Do NOT guess. Do NOT fabricate. Prefer LinkedIn/school-directory hits.
- `district_name` must be a real K-12 LEA or charter school.
- Example outputs:
    Vallejo City Unified School District|high
    Stoneham Public Schools|medium
    |none

Search results:
{snippets_text}

Your answer (district_name|confidence):"""

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=60.0)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = resp.content[0].text.strip()
        # Strip code fences if any
        answer = answer.replace("`", "").strip()
        if "|" in answer:
            district, confidence = answer.split("|", 1)
            return district.strip(), confidence.strip().lower()
    except Exception as e:
        print(f"      [warn] resolver Haiku failed for {name}: {e}", file=sys.stderr)
    return "", "none"


def run_district_resolver(entries: list[dict]) -> tuple[int, int]:
    """For each territory-state entry with empty district, try to resolve one.
    Mutates entries in place. Returns (attempted, resolved)."""
    territory = TERRITORY_STATES_WITH_CA
    attempted = 0
    resolved = 0
    for e in entries:
        state = (e.get("state") or "").strip().upper()
        district = (e.get("district") or "").strip()
        name = (e.get("name") or "").strip()
        if district:
            continue
        if state not in territory:
            continue
        if not name:
            continue
        attempted += 1
        print(f"    resolving {name} ({state})...")
        d, conf = resolve_district(name, state)
        if d and conf in ("high", "medium"):
            e["district"] = d
            e["district_resolver_confidence"] = conf
            resolved += 1
            print(f"      ✓ {d} ({conf})")
        elif d:
            print(f"      ~ {d} ({conf}) — low confidence, skipped")
    return attempted, resolved


# ──────────────────────────────────────────────────────────
# Phase 5 — Dedup + write
# ──────────────────────────────────────────────────────────


def load_previous_roster() -> list[dict]:
    """Load the existing roster to merge with. Returns [] if none exists."""
    if not OUTPUT_PATH.exists():
        return []
    try:
        data = json.loads(OUTPUT_PATH.read_text())
        return data.get("entries", []) or []
    except Exception as e:
        print(f"  [warn] could not load previous roster: {e}", file=sys.stderr)
        return []


def normalize_and_dedup(items: list[dict], previous: list[dict] | None = None) -> list[dict]:
    """Dedup by normalized person name across current items + previous roster.

    Precedence for each person:
      1. Prefer the entry with a non-empty district (current run preferred over
         previous only if it has a district and previous doesn't).
      2. Otherwise keep whichever has the most complete fields.

    Additive: people only in `previous` are kept — Haiku is nondeterministic
    and each run can drop entries that were valid finds in prior runs.
    """
    by_person: dict[str, dict] = {}
    dropped_invalid_state = 0

    # Seed with previous roster so nothing is lost
    for it in (previous or []):
        name = (it.get("name") or "").strip()
        if not name:
            continue
        key = csv_importer.normalize_name(name)
        state = (it.get("state") or "").strip().upper()
        if state and len(state) != 2:
            continue
        by_person[key] = dict(it)
        by_person[key]["state"] = state

    # Now layer current run on top, preferring fresh entries with districts
    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        key = csv_importer.normalize_name(name)
        state = (it.get("state") or "").strip().upper()
        district = (it.get("district") or "").strip()
        if state and len(state) != 2:
            dropped_invalid_state += 1
            continue

        existing = by_person.get(key)
        if existing is None:
            by_person[key] = dict(it)
            by_person[key]["state"] = state
            by_person[key]["district"] = district
            continue

        existing_district = (existing.get("district") or "").strip()
        existing_state = (existing.get("state") or "").strip()

        # Prefer new entry only if it strictly improves on existing:
        # (a) existing has no district and new does
        # (b) existing has no state and new does
        should_replace = False
        if district and not existing_district:
            should_replace = True
        if state and not existing_state:
            should_replace = True

        if should_replace:
            merged = dict(existing)
            if district:
                merged["district"] = district
            if state:
                merged["state"] = state
            # Preserve new role/chapter/source_url if existing was sparse
            for k in ("role", "chapter", "source_url"):
                if not existing.get(k) and it.get(k):
                    merged[k] = it[k]
            by_person[key] = merged

    if dropped_invalid_state:
        print(f"  [note] Dropped {dropped_invalid_state} entries with invalid state codes", file=sys.stderr)

    merged_list = list(by_person.values())
    for e in merged_list:
        district = (e.get("district") or "").strip()
        e["district_normalized"] = csv_importer.normalize_name(district) if district else ""
    return merged_list


def main() -> None:
    print("=== Phase 1: Discovery ===")
    cst_urls, linkedin_snippets = discover_csteachers_urls_and_linkedin_snippets()
    print(f"Discovered {len(cst_urls)} csteachers.org URLs + {len(linkedin_snippets)} LinkedIn snippets")

    print("\n=== Phase 2: Bucket URLs by state ===")
    state_buckets, national_urls = bucket_urls_by_state(cst_urls)
    print(f"State buckets: {len(state_buckets)} (total {sum(len(v) for v in state_buckets.values())} URLs)")
    for sc in sorted(state_buckets.keys()):
        print(f"  {sc}: {len(state_buckets[sc])} URLs")
    print(f"National bucket: {len(national_urls)} URLs")

    print("\n=== Phase 3: Per-state Haiku extraction ===")
    all_items = extract_per_state(state_buckets, national_urls, linkedin_snippets)
    print(f"\n  Total raw items: {len(all_items)}")

    print("\n=== Phase 4a: Initial dedup (merge with previous roster) ===")
    previous = load_previous_roster()
    print(f"  Loaded {len(previous)} entries from previous roster")
    entries = normalize_and_dedup(all_items, previous=previous)
    with_district = [e for e in entries if e.get("district")]
    print(f"  After dedup: {len(entries)} unique people, {len(with_district)} with district")

    print("\n=== Phase 4b: District resolver (territory states, empty district) ===")
    attempted, resolved = run_district_resolver(entries)
    print(f"  Resolver: attempted {attempted}, resolved {resolved}")

    # Recompute district_normalized after resolver pass
    for e in entries:
        district = (e.get("district") or "").strip()
        e["district_normalized"] = csv_importer.normalize_name(district) if district else ""

    with_district = [e for e in entries if e.get("district")]
    print(f"\n  Final: {len(entries)} unique people, {len(with_district)} with district")

    output = {
        "_comment": (
            "CSTA state/regional chapter roster — enrichment source for F1/F2/F4/F6/F7/F8 "
            "(via signal_processor.build_csta_enrichment). Built by "
            "scripts/fetch_csta_roster.py with per-state Haiku extraction + "
            "district resolver pass. Refresh manually quarterly or when CSTA "
            "announces new chapter boards. Each entry's `state` is the person's "
            "K-12 EMPLOYER state, NOT their chapter's state. Entries with empty "
            "`district` are kept for /signal_csta display but ignored during "
            "enrich_with_csta matching."
        ),
        "fetched_at": datetime.now().strftime("%Y-%m-%d"),
        "source": (
            "csteachers.org per-state fetch + Serper LinkedIn snippets + "
            "Haiku extraction + district resolver (Session 58 rewrite)"
        ),
        "entries": entries,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"   {len(entries)} entries, {len(with_district)} with district")

    # Territory coverage summary
    print("\n=== Territory coverage ===")
    by_state: dict[str, list[dict]] = {}
    for e in entries:
        by_state.setdefault(e.get("state", "?") or "?", []).append(e)
    for sc in sorted(TERRITORY_STATES_WITH_CA):
        ents = by_state.get(sc, [])
        matchable = [e for e in ents if e.get("district")]
        print(f"  {sc}: {len(ents)} entries, {len(matchable)} matchable")


if __name__ == "__main__":
    main()
