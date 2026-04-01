#!/usr/bin/env python3
"""
eval_research_tools.py — Head-to-head evaluation of web research tools for Scout's C2 engine.

Tests 7 tools against real K-12 districts, measuring contact yield, speed, cost,
content quality, and token efficiency.

Usage:
    python scripts/eval_research_tools.py --tool all --district all
    python scripts/eval_research_tools.py --tool baseline --district "Houston ISD"
    python scripts/eval_research_tools.py --tool all --skip-claude
    python scripts/eval_research_tools.py --summary-only
    python scripts/eval_research_tools.py --list
    python scripts/eval_research_tools.py --phase1               # Houston ISD + Guthrie only
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from eval_config import (
    TEST_DISTRICTS,
    PHASE1_DISTRICTS,
    AVAILABLE_TOOLS,
    TOOL_API_KEYS,
    COST_PER_QUERY,
    build_search_queries,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "eval_results"
RESULTS_FILE = RESULTS_DIR / "results.json"
SUMMARY_FILE = RESULTS_DIR / "summary.txt"
CONTENT_DIR = RESULTS_DIR / "content_samples"

# ─────────────────────────────────────────────
# RESULT SCHEMA
# ─────────────────────────────────────────────

def empty_result(tool: str, district: str, state: str) -> dict:
    return {
        "tool": tool,
        "district": district,
        "state": state,
        "timestamp": datetime.now().isoformat(),
        "timings": {
            "search_seconds": 0.0,
            "scrape_seconds": 0.0,
            "extract_seconds": 0.0,
            "total_seconds": 0.0,
        },
        "costs": {
            "search_cost": 0.0,
            "scrape_cost": 0.0,
            "extract_cost": 0.0,
            "total_cost": 0.0,
        },
        "content": {
            "pages_fetched": 0,
            "total_chars": 0,
            "total_tokens_est": 0,
            "content_type": "text",  # text | markdown | structured
        },
        "contacts": {
            "total": 0,
            "with_email": 0,
            "verified": 0,
            "likely": 0,
            "inferred": 0,
            "unknown": 0,
            "names": [],
            "emails": [],
        },
        "errors": [],
    }


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

async def serper_search(queries: list[str]) -> list[dict]:
    """Run Serper queries, return list of result dicts."""
    import httpx
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY not set")

    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for query in queries:
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 10},
                )
                resp.raise_for_status()
                results.append(resp.json())
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Serper query failed: {query[:60]}... — {e}")
                results.append({})
    return results


def extract_urls_from_serper(results: list[dict], max_urls: int = 10) -> list[str]:
    """Pull unique URLs from Serper organic results."""
    seen = set()
    urls = []
    skip_domains = {
        "linkedin.com", "twitter.com", "facebook.com", "wikipedia.org",
        "niche.com", "greatschools.org", "schooldigger.com", "youtube.com",
        "indeed.com", "glassdoor.com",
    }
    for result in results:
        for item in result.get("organic", []):
            url = item.get("link", "")
            if not url or url in seen:
                continue
            domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
            if any(skip in domain for skip in skip_domains):
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= max_urls:
                return urls
    return urls


def extract_snippets_from_serper(results: list[dict]) -> list[tuple[str, str]]:
    """Pull (url, snippet_content) from Serper results."""
    pages = []
    for result in results:
        for item in result.get("organic", []):
            url = item.get("link", "")
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            if url and snippet:
                pages.append((url, f"Title: {title}\nURL: {url}\n{snippet}"))
    return pages


async def scrape_with_httpx(urls: list[str]) -> list[tuple[str, str]]:
    """Scrape URLs with httpx + BeautifulSoup. Returns (url, text) pairs."""
    from bs4 import BeautifulSoup
    import httpx

    pages = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ScoutBot/2.0; K12 Education Research)"}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)[:15000]
                pages.append((url, text))
            except Exception as e:
                logger.debug(f"Scrape failed: {url} — {e}")
            await asyncio.sleep(0.5)
    return pages


def _extract_district_domain_hint(district_name: str) -> str:
    """Derive likely email domain fragment from district name for validation."""
    # "Houston ISD" → "houstonisd", "Guthrie Public Schools" → "guthrie"
    name = district_name.lower()
    # Strip common suffixes
    for suffix in [" isd", " unified school district", " school district",
                   " public schools", " city schools", " county superintendent of schools",
                   " county schools"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace(" ", "")


def _validate_email(email: str, first_name: str, last_name: str, district_hint: str) -> str:
    """Validate email quality. Returns confidence adjustment or empty string to reject."""
    if not email or "@" not in email:
        return ""

    local, domain = email.rsplit("@", 1)

    # Reject obviously malformed emails
    if email.startswith(".") or " " in email or email.count("@") != 1:
        return "REJECT"

    # Reject emails that are clearly from a different district
    # e.g., @aisd.net when researching Houston ISD, @jarrellisd.org for Leander ISD
    # Allow generic domains (gmail, yahoo, etc.) and .edu/.gov
    generic_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com"}
    if domain in generic_domains:
        return ""  # keep but don't boost

    # Check if domain plausibly matches the target district
    # District hint "houston" should match "houstonisd.org" but not "aisd.net"
    if district_hint and len(district_hint) > 3:
        domain_lower = domain.lower()
        # Allow .edu, .gov, and state education domains (tea.texas.gov, etc.)
        if not any(x in domain_lower for x in [district_hint, ".edu", ".gov"]):
            return "CROSS_DISTRICT"

    # Check name↔email alignment: local part should contain first or last name
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    local_lower = local.lower()
    if fn and ln and len(fn) > 1 and len(ln) > 1 and local_lower:
        # Check if the local part plausibly matches the person's name
        # Patterns we accept: first.last, flast, firstl, first_last, first, last
        fn_in_local = fn in local_lower
        ln_in_local = ln in local_lower
        # First initial + last name (e.g., "jeverett" for Jamie Everett)
        fi_ln = fn[0] + ln in local_lower if len(fn) > 0 else False
        # First name + last initial (e.g., "jamies" for Jamie Spradling)
        fn_li = fn + ln[0] in local_lower if len(ln) > 0 else False
        # Last name starts the local part (e.g., "scastil2" doesn't match "Rene Sanchez")
        ln_starts = local_lower.startswith(ln[:3]) if len(ln) >= 3 else False

        if not (fn_in_local or ln_in_local or fi_ln or fn_li or ln_starts):
            return "NAME_MISMATCH"

    return ""


def run_claude_extraction(pages: list[tuple[str, str]], district_name: str) -> tuple[list[dict], dict]:
    """
    Run Claude extraction on pages. Returns (contacts, usage_info).
    Includes post-extraction validation for cross-district and name↔email issues.
    """
    from anthropic import Anthropic

    EXTRACT_SYSTEM = f"""You are a precise data extraction assistant for a K-12 education sales team.

Your job: extract CS/STEM/CTE contact information from raw text or HTML for the district "{district_name}".

Return ONLY a valid JSON array. No explanation, no markdown, no preamble.

Each contact object must have these exact keys:
{{
  "first_name": "",
  "last_name": "",
  "title": "",
  "email": "",
  "work_phone": "",
  "account": "",
  "district_name": "",
  "source_url": "",
  "email_confidence": "",
  "notes": ""
}}

CRITICAL RULES FOR ACCURACY:
1. Each contact's email MUST belong to that specific person. In staff directory tables,
   carefully match each row's name to that SAME row's email. Do NOT shift or misalign
   rows. If a table has columns [Name | Title | Email], read each row independently.
2. Only extract contacts who work at {district_name}. If the page contains staff from
   a different school district, SKIP those contacts entirely.
3. email_confidence must be one of: VERIFIED, LIKELY, INFERRED, or UNKNOWN
   - VERIFIED: email explicitly shown on the SAME LINE or SAME ROW as the person's name
   - LIKELY: email follows a confirmed pattern (e.g., first.last@domain) AND name matches
   - INFERRED: email constructed from pattern but name alignment is uncertain
   - UNKNOWN: no email found for this person
4. If you see a phone number or extension but no email, set email to "" — do NOT put
   a phone number in the email field.
5. If a table row is truncated or ambiguous, set email_confidence to UNKNOWN rather than
   guessing which email belongs to which person.
6. account: school name if school-level contact, district name if district-level
7. Only include contacts whose title relates to: Computer Science, CS, Coding, Programming,
   STEM, STEAM, CTE, Career & Technical Education, Educational Technology, Curriculum,
   Instructional Technology, Digital Learning, Innovation, AP CSP, AP CS, Robotics, Esports,
   Game Design, Makerspace, After-School, TOSA, Librarian, Superintendent, Principal, Title I
8. Do NOT include general admin staff, secretaries, HR, finance unless directly related to above
9. If no valid contacts found, return empty array: []
"""

    client = Anthropic()
    all_contacts = []
    seen = set()
    total_input_tokens = 0
    total_output_tokens = 0
    district_hint = _extract_district_domain_hint(district_name)
    rejected = {"cross_district": 0, "name_mismatch": 0, "malformed": 0}

    for url, content in pages:
        if not content or len(content.strip()) < 50:
            continue

        chunk = content[:12000]
        prompt = f"""District: {district_name}
Source URL: {url}

IMPORTANT: Only extract contacts who work at {district_name}. If this page contains
staff from a different district, skip them. Match each person's name to their own email
— do not mix up rows in tables or lists.

Raw content to extract contacts from:
---
{chunk}
---

Extract all CS/STEM/CTE/EdTech contacts from {district_name} only. Return JSON array only."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            raw = response.content[0].text.strip()
            # Strip JSON preamble/postamble
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"^```\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            # Strip text before first [ and after last ]
            bracket_start = raw.find("[")
            bracket_end = raw.rfind("]")
            if bracket_start >= 0 and bracket_end > bracket_start:
                raw = raw[bracket_start : bracket_end + 1]

            contacts = json.loads(raw)
            if not isinstance(contacts, list):
                continue

            for c in contacts:
                fn = str(c.get("first_name", "")).strip()
                ln = str(c.get("last_name", "")).strip()
                if not fn and not ln:
                    continue

                email = str(c.get("email", "")).strip().lower()
                confidence = str(c.get("email_confidence", "UNKNOWN")).strip().upper()

                # Post-extraction validation
                if email:
                    validation = _validate_email(email, fn, ln, district_hint)
                    if validation == "REJECT":
                        email = ""
                        confidence = "UNKNOWN"
                        rejected["malformed"] += 1
                    elif validation == "CROSS_DISTRICT":
                        logger.debug(f"  Cross-district email rejected: {fn} {ln} → {email}")
                        email = ""
                        confidence = "UNKNOWN"
                        rejected["cross_district"] += 1
                    elif validation == "NAME_MISMATCH":
                        logger.debug(f"  Name↔email mismatch: {fn} {ln} → {email}")
                        email = ""
                        confidence = "UNKNOWN"
                        rejected["name_mismatch"] += 1

                key = f"{fn.lower()}|{ln.lower()}|{district_name.lower()}"
                if key not in seen:
                    seen.add(key)
                    all_contacts.append({
                        "first_name": fn,
                        "last_name": ln,
                        "title": str(c.get("title", "")).strip(),
                        "email": email,
                        "email_confidence": confidence,
                    })

        except json.JSONDecodeError:
            logger.debug(f"JSON parse error for {url}")
        except Exception as e:
            logger.warning(f"Claude extraction error for {url}: {e}")

    if any(v > 0 for v in rejected.values()):
        logger.info(f"    Validation: rejected {rejected['cross_district']} cross-district, "
                     f"{rejected['name_mismatch']} name-mismatch, {rejected['malformed']} malformed")

    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "est_cost": (total_input_tokens * 3.0 / 1_000_000) + (total_output_tokens * 15.0 / 1_000_000),
    }
    return all_contacts, usage


def save_content_sample(tool: str, district: str, pages: list[tuple[str, str]]):
    """Save sample content for manual review."""
    safe_name = district.lower().replace(" ", "_")
    sample_dir = CONTENT_DIR / safe_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    ext = "md" if tool in ("crawl4ai", "firecrawl", "jina") else "txt"
    sample_file = sample_dir / f"{tool}.{ext}"

    with open(sample_file, "w") as f:
        for url, content in pages[:3]:  # save first 3 pages as sample
            f.write(f"--- URL: {url} ---\n\n")
            f.write(content[:5000])
            f.write("\n\n")

    logger.info(f"  Saved content sample: {sample_file}")


# ─────────────────────────────────────────────
# PAGE PRE-FILTERING
# ─────────────────────────────────────────────

# Domains that never contain useful K-12 contact data
SKIP_DOMAINS = {
    "linkedin.com", "twitter.com", "facebook.com", "wikipedia.org",
    "niche.com", "greatschools.org", "schooldigger.com", "youtube.com",
    "indeed.com", "glassdoor.com", "instagram.com", "contactout.com",
    "rocketreach.co", "zoominfo.com", "signalhire.com", "lusha.com",
    "tiktok.com", "pinterest.com", "reddit.com",
}


def filter_pages_for_district(
    pages: list[tuple[str, str]], district_name: str, state: str
) -> list[tuple[str, str]]:
    """Pre-filter pages to remove cross-district content and noise.

    Removes:
    - Pages from skip-listed domains (social media, people-search sites)
    - Pages that clearly belong to a different school district
    - Pages with too little content to extract from
    """
    district_hint = _extract_district_domain_hint(district_name)
    district_words = set(district_name.lower().split())
    # Remove generic words that appear in many district names
    district_words -= {"public", "schools", "school", "district", "unified",
                       "county", "city", "of", "the", "superintendent"}

    filtered = []
    skipped_reasons = {}

    for url, content in pages:
        # Skip empty/tiny content
        if not content or len(content.strip()) < 100:
            skipped_reasons[url] = "too_short"
            continue

        # Skip social media and people-search sites
        try:
            domain = url.split("/")[2].lower()
        except (IndexError, AttributeError):
            domain = ""

        if any(skip in domain for skip in SKIP_DOMAINS):
            skipped_reasons[url] = "skip_domain"
            continue

        # Check if URL belongs to a different district's domain
        # e.g., "aisd.net" when searching for Houston ISD, "jarrellisd.org" for Leander ISD
        # Only flag if URL contains another district abbreviation that conflicts
        if domain and district_hint:
            # Extract the subdomain root (e.g., "houstonisd" from "www.houstonisd.org")
            domain_parts = domain.replace("www.", "").split(".")
            domain_root = domain_parts[0] if domain_parts else ""

            # If domain root looks like a district domain and doesn't match our target
            district_domain_patterns = ["isd", "usd", "k12", "schools", "ps"]
            looks_like_district_domain = any(p in domain_root for p in district_domain_patterns)

            if looks_like_district_domain and district_hint not in domain_root:
                # It's another district's domain — check if any of our district words match
                # to avoid false positives (e.g., "houstonisd.org" subdomains like "deady.houstonisd.org")
                if not any(w in domain_root for w in district_words if len(w) > 3):
                    skipped_reasons[url] = f"other_district_domain:{domain_root}"
                    continue

        filtered.append((url, content))

    if skipped_reasons:
        reasons_summary = {}
        for reason in skipped_reasons.values():
            key = reason.split(":")[0]
            reasons_summary[key] = reasons_summary.get(key, 0) + 1
        logger.info(f"    Pre-filter: kept {len(filtered)}/{len(pages)} pages "
                     f"(dropped: {dict(reasons_summary)})")

    return filtered


# ─────────────────────────────────────────────
# TOOL ADAPTERS
# ─────────────────────────────────────────────

async def run_baseline(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Baseline: Serper search + httpx/BS4 scrape. Returns (pages, cost_info)."""
    queries = build_search_queries(district, state)

    t0 = time.time()
    results = await serper_search(queries)
    search_time = time.time() - t0

    urls = extract_urls_from_serper(results, max_urls=5)
    snippets = extract_snippets_from_serper(results)

    t0 = time.time()
    scraped = await scrape_with_httpx(urls)
    scrape_time = time.time() - t0

    # Combine snippets + scraped pages
    all_pages = snippets + scraped

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["serper"],
        "scrape_cost": 0.0,
        "search_seconds": search_time,
        "scrape_seconds": scrape_time,
        "queries_used": len(queries),
    }
    return all_pages, costs


async def run_jina(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Jina: s.jina.ai search + r.jina.ai scrape. Returns (pages, cost_info)."""
    import httpx

    api_key = os.environ.get("JINA_API_KEY", "")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    pages = []
    search_queries = [
        f'"{district}" computer science STEM CTE staff directory contact email',
        f'"{district}" {state} curriculum director technology coordinator',
    ]

    t0 = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        # Search via s.jina.ai
        for query in search_queries:
            try:
                resp = await client.get(
                    f"https://s.jina.ai/",
                    params={"q": query},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("data", []):
                    url = item.get("url", "")
                    content = item.get("content", "") or item.get("description", "")
                    if url and content:
                        pages.append((url, content))
                await asyncio.sleep(3.0)  # respect 20 RPM limit
            except Exception as e:
                logger.warning(f"Jina search failed: {e}")

        # Also scrape top URLs via r.jina.ai for full content
        urls_to_scrape = list(dict.fromkeys(url for url, _ in pages))[:5]
        for url in urls_to_scrape:
            try:
                scrape_headers = {"Accept": "text/markdown"}
                if api_key:
                    scrape_headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(
                    f"https://r.jina.ai/{url}",
                    headers=scrape_headers,
                )
                resp.raise_for_status()
                pages.append((url, resp.text[:15000]))
                await asyncio.sleep(3.0)
            except Exception as e:
                logger.debug(f"Jina scrape failed for {url}: {e}")

    search_time = time.time() - t0

    costs = {
        "search_cost": 0.0,  # free tier
        "scrape_cost": 0.0,
        "search_seconds": search_time,
        "scrape_seconds": 0.0,  # included in search_time
        "queries_used": len(search_queries) + len(urls_to_scrape),
    }
    return pages, costs


async def run_tavily(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Tavily: search with full raw_content. Returns (pages, cost_info)."""
    try:
        from tavily import TavilyClient
    except ImportError:
        raise RuntimeError("tavily not installed. Run: pip install tavily-python")

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")

    client = TavilyClient(api_key=api_key)
    pages = []

    queries = [
        f'"{district}" computer science STEM CTE staff directory contact email',
        f'"{district}" {state} curriculum director technology coordinator',
    ]

    t0 = time.time()
    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                include_raw_content=True,
                max_results=10,
            )
            for item in response.get("results", []):
                url = item.get("url", "")
                content = item.get("raw_content", "") or item.get("content", "")
                if url and content:
                    pages.append((url, content[:15000]))
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")
    search_time = time.time() - t0

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["tavily_advanced"],
        "scrape_cost": 0.0,  # included in search
        "search_seconds": search_time,
        "scrape_seconds": 0.0,
        "queries_used": len(queries),
    }
    return pages, costs


async def run_exa(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Exa: semantic search + contents. Returns (pages, cost_info)."""
    try:
        from exa_py import Exa
    except ImportError:
        raise RuntimeError("exa not installed. Run: pip install exa-py")

    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        raise RuntimeError("EXA_API_KEY not set")

    exa = Exa(api_key=api_key)
    pages = []

    queries = [
        f"{district} {state} computer science STEM staff directory",
        f"{district} CTE curriculum technology coordinator contact email",
    ]

    t0 = time.time()
    for query in queries:
        try:
            results = exa.search_and_contents(
                query=query,
                type="auto",
                num_results=10,
                text=True,
            )
            for r in results.results:
                url = r.url or ""
                content = r.text or ""
                if url and content:
                    pages.append((url, content[:15000]))
        except Exception as e:
            logger.warning(f"Exa search failed: {e}")
    search_time = time.time() - t0

    num_results = len(pages)
    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["exa_search"] + num_results * COST_PER_QUERY["exa_content"],
        "scrape_cost": 0.0,
        "search_seconds": search_time,
        "scrape_seconds": 0.0,
        "queries_used": len(queries),
    }
    return pages, costs


async def run_firecrawl(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Firecrawl: Serper search + Firecrawl scrape for full markdown. Returns (pages, cost_info)."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        raise RuntimeError("firecrawl not installed. Run: pip install firecrawl-py")

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")

    app = FirecrawlApp(api_key=api_key)

    # Use Serper for search (cheaper), Firecrawl for scraping (better quality)
    queries = build_search_queries(district, state)

    t0 = time.time()
    results = await serper_search(queries)
    search_time = time.time() - t0

    urls = extract_urls_from_serper(results, max_urls=5)
    snippets = extract_snippets_from_serper(results)

    # Scrape top URLs with Firecrawl for full markdown content
    pages = list(snippets)
    scrape_credits = 0
    t0 = time.time()
    for url in urls:
        try:
            doc = app.scrape(url, formats=["markdown"])
            markdown = getattr(doc, 'markdown', '') or ''
            if isinstance(doc, dict):
                markdown = doc.get('markdown', '')
            if markdown:
                pages.append((url, str(markdown)[:15000]))
                scrape_credits += 1
        except Exception as e:
            logger.debug(f"Firecrawl scrape failed for {url}: {e}")
    scrape_time = time.time() - t0

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["serper"],
        "scrape_cost": scrape_credits * COST_PER_QUERY["firecrawl_scrape"],
        "search_seconds": search_time,
        "scrape_seconds": scrape_time,
        "queries_used": len(queries) + scrape_credits,
    }
    return pages, costs


async def run_exa_firecrawl(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Hybrid: Exa semantic search for broad content + Firecrawl scrape for district site pages."""
    try:
        from exa_py import Exa
    except ImportError:
        raise RuntimeError("exa not installed. Run: pip install exa-py")
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        raise RuntimeError("firecrawl not installed. Run: pip install firecrawl-py")

    exa_key = os.environ.get("EXA_API_KEY", "")
    fc_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not exa_key:
        raise RuntimeError("EXA_API_KEY not set")
    if not fc_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")

    exa = Exa(api_key=exa_key)
    fc = FirecrawlApp(api_key=fc_key)

    pages = []

    # Step 1: Exa broad semantic search (same as run_exa)
    queries = [
        f"{district} {state} computer science STEM staff directory",
        f"{district} CTE curriculum technology coordinator contact email",
    ]

    t0 = time.time()
    for query in queries:
        try:
            results = exa.search_and_contents(
                query=query,
                type="auto",
                num_results=10,
                text=True,
            )
            for r in results.results:
                url = r.url or ""
                content = r.text or ""
                if url and content:
                    pages.append((url, content[:15000]))
        except Exception as e:
            logger.warning(f"Exa search failed: {e}")
    exa_time = time.time() - t0
    exa_results = len(pages)

    # Step 2: Firecrawl targeted scrape of district domain pages
    # Use Firecrawl search to find district-specific pages, then scrape them
    t0 = time.time()
    fc_credits = 0
    try:
        fc_results = fc.search(
            f"{district} staff directory contact email",
            limit=5,
        )
        fc_urls = []
        if hasattr(fc_results, 'web') and fc_results.web:
            for r in fc_results.web:
                url = r.url if hasattr(r, 'url') else ''
                if url:
                    fc_urls.append(url)
        fc_credits += 1  # search costs 1 credit

        # Scrape district-domain URLs found by Firecrawl (skip social/generic)
        seen_urls = {u for u, _ in pages}
        for url in fc_urls[:3]:
            if url in seen_urls:
                continue
            try:
                doc = fc.scrape(url, formats=["markdown"])
                markdown = getattr(doc, 'markdown', '') or ''
                if markdown and len(markdown) > 100:
                    pages.append((url, str(markdown)[:15000]))
                    fc_credits += 1
            except Exception as e:
                logger.debug(f"Firecrawl scrape failed for {url}: {e}")
    except Exception as e:
        logger.warning(f"Firecrawl search failed: {e}")
    fc_time = time.time() - t0

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["exa_search"] + exa_results * COST_PER_QUERY["exa_content"],
        "scrape_cost": fc_credits * COST_PER_QUERY["firecrawl_scrape"],
        "search_seconds": exa_time,
        "scrape_seconds": fc_time,
        "queries_used": len(queries) + fc_credits,
    }
    return pages, costs


async def run_crawl4ai(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Crawl4AI: Serper for search + Crawl4AI for scraping (markdown output). Returns (pages, cost_info)."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        raise RuntimeError("crawl4ai not installed. Run: pip install crawl4ai && crawl4ai-setup")

    # Use Serper for search (same as baseline)
    queries = build_search_queries(district, state)

    t0 = time.time()
    results = await serper_search(queries)
    search_time = time.time() - t0

    urls = extract_urls_from_serper(results, max_urls=5)
    snippets = extract_snippets_from_serper(results)

    # Scrape with Crawl4AI (returns markdown)
    pages = list(snippets)  # start with snippets from Serper
    t0 = time.time()
    try:
        async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
            for url in urls:
                try:
                    result = await crawler.arun(url=url, config=CrawlerRunConfig())
                    if result and result.markdown:
                        pages.append((url, result.markdown[:15000]))
                except Exception as e:
                    logger.debug(f"Crawl4AI scrape failed: {url} — {e}")
    except Exception as e:
        logger.warning(f"Crawl4AI browser failed: {e}")
    scrape_time = time.time() - t0

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["serper"],
        "scrape_cost": 0.0,  # free, self-hosted
        "search_seconds": search_time,
        "scrape_seconds": scrape_time,
        "queries_used": len(queries),
    }
    return pages, costs


async def run_parsebot(district: str, state: str) -> tuple[list[tuple[str, str]], dict]:
    """Parse.bot: dispatch → poll → execute structured extraction. Returns (pages, cost_info)."""
    import httpx

    api_key = os.environ.get("PARSEBOT_API_KEY", "")
    if not api_key:
        raise RuntimeError("PARSEBOT_API_KEY not set")

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    # First, use Serper to find the district's staff directory URL
    queries = [f'"{district}" staff directory', f'"{district}" {state} contact administration']

    t0 = time.time()
    results = await serper_search(queries)
    urls = extract_urls_from_serper(results, max_urls=2)

    pages = []
    async with httpx.AsyncClient(timeout=60) as client:
        for url in urls:
            try:
                # Step 1: Dispatch — ask Parse.bot to build/match an API for this URL
                resp = await client.post(
                    "https://api.parse.bot/dispatch",
                    headers=headers,
                    json={
                        "url": url,
                        "task": "Extract all staff names, job titles, email addresses, and phone numbers",
                        "force_new": False,
                    },
                )
                resp.raise_for_status()
                dispatch = resp.json()
                task_id = dispatch.get("task_id", "")

                if not task_id:
                    logger.warning(f"Parse.bot no task_id for {url}: {dispatch}")
                    continue

                # Step 2: Poll until complete (max 30s)
                scraper_id = None
                for _ in range(15):
                    await asyncio.sleep(2)
                    poll_resp = await client.get(
                        f"https://api.parse.bot/dispatch/tasks/{task_id}",
                        headers=headers,
                    )
                    poll_resp.raise_for_status()
                    task = poll_resp.json()
                    status = task.get("status", "")

                    if status == "completed":
                        scraper_id = task.get("result_scraper_id", "")
                        break
                    elif status == "failed":
                        logger.warning(f"Parse.bot task failed for {url}: {task.get('error', 'unknown')}")
                        break
                    elif status == "needs_input":
                        logger.warning(f"Parse.bot needs input for {url} — skipping")
                        break

                if not scraper_id:
                    continue

                # Step 3: Execute the generated scraper
                exec_resp = await client.get(
                    f"https://api.parse.bot/scraper/{scraper_id}",
                    headers=headers,
                )
                exec_resp.raise_for_status()
                data = exec_resp.json()
                content = json.dumps(data, indent=2)
                if content and len(content) > 10:
                    pages.append((url, content[:15000]))

            except Exception as e:
                logger.warning(f"Parse.bot failed for {url}: {e}")
    search_time = time.time() - t0

    costs = {
        "search_cost": len(queries) * COST_PER_QUERY["serper"],
        "scrape_cost": len(pages) * COST_PER_QUERY["parsebot"],
        "search_seconds": search_time,
        "scrape_seconds": 0.0,
        "queries_used": len(queries) + len(pages),
    }
    return pages, costs


# Tool dispatcher
TOOL_RUNNERS = {
    "baseline": run_baseline,
    "crawl4ai": run_crawl4ai,
    "firecrawl": run_firecrawl,
    "jina": run_jina,
    "tavily": run_tavily,
    "exa": run_exa,
    "parsebot": run_parsebot,
    "exa_firecrawl": run_exa_firecrawl,
}


# ─────────────────────────────────────────────
# MAIN EVALUATION LOGIC
# ─────────────────────────────────────────────

async def evaluate_tool(tool: str, district_info: dict, skip_claude: bool = False) -> dict:
    """Run a single tool against a single district. Returns result dict."""
    district = district_info["name"]
    state = district_info["state"]
    result = empty_result(tool, district, state)

    runner = TOOL_RUNNERS.get(tool)
    if not runner:
        result["errors"].append(f"Unknown tool: {tool}")
        return result

    # Check API key
    env_key = TOOL_API_KEYS.get(tool, "")
    if env_key and not os.environ.get(env_key, ""):
        # Jina works without API key on free tier
        if tool != "jina":
            result["errors"].append(f"Missing {env_key}")
            return result

    print(f"\n  Running {tool} on {district} ({state})...")

    try:
        t_total = time.time()
        pages, cost_info = await runner(district, state)
        total_time = time.time() - t_total

        # Pre-filter pages to remove cross-district and noise
        pages = filter_pages_for_district(pages, district, state)

        result["timings"]["search_seconds"] = cost_info.get("search_seconds", 0)
        result["timings"]["scrape_seconds"] = cost_info.get("scrape_seconds", 0)
        result["timings"]["total_seconds"] = total_time
        result["costs"]["search_cost"] = cost_info.get("search_cost", 0)
        result["costs"]["scrape_cost"] = cost_info.get("scrape_cost", 0)

        # Content stats
        result["content"]["pages_fetched"] = len(pages)
        total_chars = sum(len(c) for _, c in pages)
        result["content"]["total_chars"] = total_chars
        result["content"]["total_tokens_est"] = total_chars // 4
        if tool in ("crawl4ai", "firecrawl", "jina", "exa_firecrawl"):
            result["content"]["content_type"] = "markdown"
        elif tool == "parsebot":
            result["content"]["content_type"] = "structured"

        # Save content samples
        save_content_sample(tool, district, pages)

        # Claude extraction (optional)
        if not skip_claude and pages:
            print(f"    Extracting contacts with Claude...")
            t_extract = time.time()
            contacts, usage = run_claude_extraction(pages, district)
            extract_time = time.time() - t_extract

            result["timings"]["extract_seconds"] = extract_time
            result["timings"]["total_seconds"] = total_time + extract_time
            result["costs"]["extract_cost"] = usage["est_cost"]
            result["costs"]["total_cost"] = (
                result["costs"]["search_cost"]
                + result["costs"]["scrape_cost"]
                + result["costs"]["extract_cost"]
            )
            result["content"]["total_tokens_est"] = usage["input_tokens"]

            result["contacts"]["total"] = len(contacts)
            result["contacts"]["with_email"] = sum(1 for c in contacts if c.get("email"))
            result["contacts"]["verified"] = sum(1 for c in contacts if c.get("email_confidence") == "VERIFIED")
            result["contacts"]["likely"] = sum(1 for c in contacts if c.get("email_confidence") == "LIKELY")
            result["contacts"]["inferred"] = sum(1 for c in contacts if c.get("email_confidence") == "INFERRED")
            result["contacts"]["unknown"] = sum(1 for c in contacts if c.get("email_confidence") == "UNKNOWN")
            result["contacts"]["names"] = [
                f"{c['first_name']} {c['last_name']}" for c in contacts
            ]
            # Store emails as parallel array (empty string for contacts without email)
            # so names[i] always corresponds to emails[i]
            result["contacts"]["emails"] = [c.get("email", "") for c in contacts]
        else:
            result["costs"]["total_cost"] = result["costs"]["search_cost"] + result["costs"]["scrape_cost"]

        print(f"    Done: {result['content']['pages_fetched']} pages, "
              f"{result['content']['total_chars']:,} chars, "
              f"{result['timings']['total_seconds']:.1f}s, "
              f"${result['costs']['total_cost']:.4f}")
        if not skip_claude:
            print(f"    Contacts: {result['contacts']['total']} "
                  f"({result['contacts']['with_email']} with email, "
                  f"{result['contacts']['verified']} verified)")

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"  Error running {tool} on {district}: {e}")

    return result


# ─────────────────────────────────────────────
# RESULTS I/O
# ─────────────────────────────────────────────

def load_results() -> list[dict]:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return []


def save_results(results: list[dict]):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2))


def upsert_result(all_results: list[dict], new_result: dict) -> list[dict]:
    """Replace existing result for same tool+district, or append."""
    key = (new_result["tool"], new_result["district"])
    updated = [r for r in all_results if (r["tool"], r["district"]) != key]
    updated.append(new_result)
    return updated


# ─────────────────────────────────────────────
# SUMMARY / COMPARISON OUTPUT
# ─────────────────────────────────────────────

def print_summary(results: list[dict]):
    """Print comparison tables from results."""
    if not results:
        print("\nNo results found. Run an evaluation first.")
        return

    # Group by district
    districts = sorted(set(r["district"] for r in results))
    tools = sorted(set(r["tool"] for r in results))

    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append(f"RESEARCH TOOL EVALUATION — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output_lines.append("=" * 70)

    for district in districts:
        d_results = {r["tool"]: r for r in results if r["district"] == district}
        if not d_results:
            continue

        state = next(iter(d_results.values()))["state"]
        output_lines.append(f"\nDistrict: {district} ({state})")
        output_lines.append("-" * 70)

        # Header
        tool_names = [t for t in tools if t in d_results]
        header = f"{'':18s}" + "".join(f"{t:>12s}" for t in tool_names)
        output_lines.append(header)

        # Rows
        def row(label, fn):
            vals = "".join(f"{fn(d_results[t]):>12s}" for t in tool_names)
            return f"{label:18s}{vals}"

        output_lines.append(row("Pages fetched", lambda r: str(r["content"]["pages_fetched"])))
        output_lines.append(row("Content chars", lambda r: f"{r['content']['total_chars']:,}"))
        output_lines.append(row("Est. tokens", lambda r: f"{r['content']['total_tokens_est']:,}"))
        output_lines.append(row("Content type", lambda r: r["content"]["content_type"]))

        has_contacts = any(r["contacts"]["total"] > 0 for r in d_results.values())
        if has_contacts:
            output_lines.append(row("Contacts", lambda r: str(r["contacts"]["total"])))
            output_lines.append(row("With email", lambda r: str(r["contacts"]["with_email"])))
            output_lines.append(row("VERIFIED", lambda r: str(r["contacts"]["verified"])))

        output_lines.append(row("Time (sec)", lambda r: f"{r['timings']['total_seconds']:.1f}"))
        output_lines.append(row("Cost ($)", lambda r: f"${r['costs']['total_cost']:.4f}"))

        # Errors
        for t in tool_names:
            if d_results[t]["errors"]:
                output_lines.append(f"  {t} errors: {', '.join(d_results[t]['errors'])}")

    # Aggregate summary
    if len(districts) > 1:
        output_lines.append("\n" + "=" * 70)
        output_lines.append("AGGREGATE SUMMARY")
        output_lines.append("=" * 70)

        header = f"{'':18s}" + "".join(f"{t:>12s}" for t in tools)
        output_lines.append(header)

        for metric_label, metric_fn in [
            ("Avg pages", lambda r: r["content"]["pages_fetched"]),
            ("Avg chars", lambda r: r["content"]["total_chars"]),
            ("Avg contacts", lambda r: r["contacts"]["total"]),
            ("Avg w/ email", lambda r: r["contacts"]["with_email"]),
            ("Avg time (s)", lambda r: r["timings"]["total_seconds"]),
            ("Avg cost ($)", lambda r: r["costs"]["total_cost"]),
        ]:
            vals = ""
            for t in tools:
                t_results = [r for r in results if r["tool"] == t and not r["errors"]]
                if t_results:
                    avg = sum(metric_fn(r) for r in t_results) / len(t_results)
                    if "cost" in metric_label:
                        vals += f"${avg:>11.4f}"
                    elif "time" in metric_label:
                        vals += f"{avg:>12.1f}"
                    elif "chars" in metric_label:
                        vals += f"{avg:>12,.0f}"
                    else:
                        vals += f"{avg:>12.1f}"
                else:
                    vals += f"{'N/A':>12s}"
            output_lines.append(f"{metric_label:18s}{vals}")

    summary = "\n".join(output_lines)
    print(summary)

    # Save to file
    SUMMARY_FILE.write_text(summary)
    print(f"\nSummary saved to: {SUMMARY_FILE}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="C2 Research Tool Evaluation")
    parser.add_argument("--tool", default="all", help="Tool to test (or 'all')")
    parser.add_argument("--district", default="all", help="District to test (or 'all')")
    parser.add_argument("--skip-claude", action="store_true", help="Skip Claude extraction (content comparison only)")
    parser.add_argument("--summary-only", action="store_true", help="Print summary from existing results")
    parser.add_argument("--list", action="store_true", help="List available tools and districts")
    parser.add_argument("--phase1", action="store_true", help="Run Phase 1 districts only (Houston + Guthrie)")
    args = parser.parse_args()

    if args.list:
        print("Available tools:", ", ".join(AVAILABLE_TOOLS))
        print("\nTest districts:")
        for d in TEST_DISTRICTS:
            phase1 = " [PHASE 1]" if d["name"] in PHASE1_DISTRICTS else ""
            print(f"  {d['name']} ({d['state']}) — {d['size']}, {d['notes']}{phase1}")
        return

    if args.summary_only:
        results = load_results()
        print_summary(results)
        return

    # Determine which tools to run
    if args.tool == "all":
        tools_to_run = AVAILABLE_TOOLS
    else:
        tools_to_run = [t.strip() for t in args.tool.split(",")]
        for t in tools_to_run:
            if t not in AVAILABLE_TOOLS:
                print(f"Unknown tool: {t}. Available: {', '.join(AVAILABLE_TOOLS)}")
                return

    # Determine which districts to run
    if args.phase1:
        districts_to_run = [d for d in TEST_DISTRICTS if d["name"] in PHASE1_DISTRICTS]
    elif args.district == "all":
        districts_to_run = TEST_DISTRICTS
    else:
        districts_to_run = [d for d in TEST_DISTRICTS if d["name"] == args.district]
        if not districts_to_run:
            print(f"Unknown district: {args.district}")
            print("Available:", ", ".join(d["name"] for d in TEST_DISTRICTS))
            return

    # Run evaluations
    all_results = load_results()
    total_combos = len(tools_to_run) * len(districts_to_run)
    print(f"\nRunning {total_combos} evaluations ({len(tools_to_run)} tools x {len(districts_to_run)} districts)")
    if args.skip_claude:
        print("  (skipping Claude extraction — content comparison only)")

    async def run_all():
        nonlocal all_results
        for district_info in districts_to_run:
            print(f"\n{'='*50}")
            print(f"District: {district_info['name']} ({district_info['state']})")
            print(f"{'='*50}")

            for tool in tools_to_run:
                result = await evaluate_tool(tool, district_info, skip_claude=args.skip_claude)
                all_results = upsert_result(all_results, result)
                save_results(all_results)

    asyncio.run(run_all())

    # Print summary
    print_summary(all_results)


if __name__ == "__main__":
    main()
