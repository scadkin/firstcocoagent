#!/usr/bin/env python3
"""
eval_deep_research.py — Multi-stage deep research engine prototype.

Unlike single-tool adapters that do: search → scrape → extract,
this orchestrates multiple tools in an intelligent pipeline:

  Stage 1: Domain Discovery — Find the district's actual website
  Stage 2: Site Mapping — Crawl district domain for staff/contact pages
  Stage 3: Broad Search — Exa + Serper for third-party mentions
  Stage 4: Claude Extraction — Extract contacts from all sources
  Stage 5: Email Pattern Inference — From known emails, generate INFERRED emails
  Stage 6: Targeted Follow-up — Search for specific people still missing emails

Usage:
    .venv/bin/python scripts/eval_deep_research.py "Houston ISD" Texas
    .venv/bin/python scripts/eval_deep_research.py "Guthrie Public Schools" Oklahoma
    .venv/bin/python scripts/eval_deep_research.py --all
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_config import TEST_DISTRICTS, PRIORITY_TITLES, COST_PER_QUERY
from eval_research_tools import (
    serper_search,
    extract_urls_from_serper,
    scrape_with_httpx,
    filter_pages_for_district,
    _extract_district_domain_hint,
    _validate_email,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "eval_results"


# ─────────────────────────────────────────────
# STAGE 1: Domain Discovery
# ─────────────────────────────────────────────

async def discover_domain(district: str, state: str) -> str:
    """Find the district's primary website domain."""
    results = await serper_search([f'"{district}" {state} official website'])
    if not results or not results[0].get("organic"):
        return ""

    # Look for .org, .k12, or .us domains that match the district
    hint = _extract_district_domain_hint(district)
    for item in results[0]["organic"][:5]:
        url = item.get("link", "")
        try:
            domain = url.split("/")[2].replace("www.", "")
        except IndexError:
            continue
        # District domains are usually .org, .k12.STATE.us, or .net
        if any(tld in domain for tld in [".org", ".k12.", ".us", ".net", ".edu"]):
            if hint in domain.replace(".", "").replace("-", ""):
                return domain

    # Fallback: first .org result
    for item in results[0]["organic"][:5]:
        url = item.get("link", "")
        try:
            domain = url.split("/")[2].replace("www.", "")
        except IndexError:
            continue
        if ".org" in domain:
            return domain

    return ""


# ─────────────────────────────────────────────
# STAGE 2A: Firecrawl Extract (schema-based, replaces Claude for district sites)
# ─────────────────────────────────────────────

async def firecrawl_extract_contacts(domain: str, district: str) -> tuple[list[dict], float]:
    """Use Firecrawl /extract to pull structured contacts directly from district site.
    This is the most powerful tool — it crawls the site AND extracts in one call.
    Returns (contacts, cost)."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        return [], 0.0

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        return [], 0.0

    fc = FirecrawlApp(api_key=api_key)
    contacts = []

    try:
        logger.info(f"  [Stage 2A] Firecrawl extract on {domain}/*...")
        result = fc.extract(
            urls=[f"https://{domain}/*"],
            prompt=(
                f"Find all staff members at {district} whose role relates to: "
                "Computer Science, STEM, CTE, Career & Technical Education, "
                "Educational Technology, Curriculum, Technology, Innovation, "
                "Digital Learning, Robotics, or school leadership (Principal, "
                "Superintendent). Extract their full names, job titles, email "
                "addresses, phone numbers, and department/school."
            ),
            schema={
                "type": "object",
                "properties": {
                    "contacts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                                "title": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "department": {"type": "string"},
                            }
                        }
                    }
                }
            },
            enable_web_search=True,
            timeout=120,
        )

        # Parse result
        data = None
        if hasattr(result, 'data'):
            data = result.data
        elif isinstance(result, dict):
            data = result

        if data and isinstance(data, dict):
            raw_contacts = data.get("contacts", [])
            for c in raw_contacts:
                fn = str(c.get("first_name", "")).strip()
                ln = str(c.get("last_name", "")).strip()
                email = str(c.get("email", "")).strip()
                if not fn and not ln:
                    continue
                # Clean masked emails (Firecrawl sometimes returns a***@domain)
                if email and "***" in email:
                    email = ""
                contacts.append({
                    "first_name": fn,
                    "last_name": ln,
                    "title": str(c.get("title", "")).strip(),
                    "email": email.lower() if email else "",
                    "work_phone": str(c.get("phone", "")).strip(),
                    "account": str(c.get("department", "")).strip(),
                    "source_url": f"https://{domain}",
                    "email_confidence": "VERIFIED" if email and "***" not in email else "UNKNOWN",
                })

            logger.info(f"    Firecrawl extract: {len(contacts)} contacts, "
                        f"{sum(1 for c in contacts if c['email'])} with email")

    except Exception as e:
        logger.warning(f"  [Stage 2A] Firecrawl extract failed: {e}")

    # Rough cost: extract uses ~5-10 credits
    cost = 0.16  # estimate: 10 credits at $0.016/credit
    return contacts, cost


# ─────────────────────────────────────────────
# STAGE 2B: Site Mapping (Firecrawl map + targeted scrape)
# ─────────────────────────────────────────────

async def map_and_scrape_district_site(domain: str, district: str) -> tuple[list[tuple[str, str]], int]:
    """Use Firecrawl to map a district's site and scrape staff/contact pages.
    Returns (pages, credits_used)."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        logger.warning("Firecrawl not installed — skipping site mapping")
        return [], 0

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set — skipping site mapping")
        return [], 0

    fc = FirecrawlApp(api_key=api_key)
    pages = []
    credits = 0

    # Step 1: Map the domain to find all URLs
    try:
        logger.info(f"  [Stage 2] Mapping {domain}...")
        map_result = fc.map(f"https://{domain}")
        credits += 1

        # map_result can be a MapData object, dict, or list
        if hasattr(map_result, 'links'):
            raw_links = map_result.links or []
        elif isinstance(map_result, dict):
            raw_links = map_result.get("links", [])
        elif isinstance(map_result, list):
            raw_links = map_result
        else:
            raw_links = []

        # Normalize links — may be strings or LinkResult objects
        all_urls = []
        for link in raw_links:
            if isinstance(link, str):
                all_urls.append(link)
            elif hasattr(link, 'url'):
                all_urls.append(str(link.url))
            elif hasattr(link, '__str__'):
                all_urls.append(str(link))

        logger.info(f"    Found {len(all_urls)} URLs on {domain}")

        # Step 2: Filter for staff/contact/directory pages
        contact_keywords = [
            "staff", "directory", "contact", "team", "about", "leadership",
            "administration", "department", "curriculum", "technology",
            "cte", "stem", "cs", "computer-science", "personnel",
        ]
        staff_urls = []
        for url in all_urls:
            url_lower = url.lower()
            if any(kw in url_lower for kw in contact_keywords):
                staff_urls.append(url)

        logger.info(f"    Filtered to {len(staff_urls)} staff/contact pages")

        # Step 3: Scrape the most promising pages (limit to save credits)
        for url in staff_urls[:8]:
            try:
                doc = fc.scrape(url, formats=["markdown"])
                markdown = getattr(doc, 'markdown', '') or ''
                if markdown and len(markdown) > 200:
                    pages.append((url, str(markdown)[:15000]))
                    credits += 1
            except Exception as e:
                logger.debug(f"    Firecrawl scrape failed: {url} — {e}")

        logger.info(f"    Scraped {len(pages)} pages ({credits} credits used)")

    except Exception as e:
        logger.warning(f"  [Stage 2] Firecrawl map failed for {domain}: {e}")

    return pages, credits


# ─────────────────────────────────────────────
# STAGE 3: Broad Search (Exa + Serper combined)
# ─────────────────────────────────────────────

async def broad_search(district: str, state: str, domain: str = "") -> tuple[list[tuple[str, str]], dict]:
    """Run Exa semantic search (broad + domain-scoped) + Serper targeted search."""
    pages = []
    costs = {"exa_cost": 0.0, "serper_cost": 0.0}

    # 3A: Exa semantic search — two strategies
    try:
        from exa_py import Exa
        exa_key = os.environ.get("EXA_API_KEY", "")
        if exa_key:
            exa = Exa(api_key=exa_key)

            # Strategy 1: Broad semantic search (finds conferences, news, third-party mentions)
            exa_queries = [
                f"{district} {state} computer science STEM staff directory",
                f"{district} CTE curriculum technology coordinator contact email",
            ]
            for query in exa_queries:
                try:
                    results = exa.search_and_contents(
                        query=query, type="auto", num_results=10, text=True,
                    )
                    for r in results.results:
                        if r.url and r.text:
                            pages.append((r.url, r.text[:15000]))
                except Exception as e:
                    logger.debug(f"Exa broad search failed: {e}")

            broad_count = len(pages)
            logger.info(f"  [Stage 3a] Exa broad: {broad_count} pages")

            # Strategy 2: Domain-scoped search (finds specific staff/dept pages on district site)
            if domain:
                domain_queries = [
                    "staff directory faculty contact email",
                    "computer science technology CTE department",
                ]
                for query in domain_queries:
                    try:
                        results = exa.search_and_contents(
                            query=query, type="auto", num_results=10, text=True,
                            include_domains=[domain],
                        )
                        for r in results.results:
                            if r.url and r.text:
                                pages.append((r.url, r.text[:15000]))
                    except Exception as e:
                        logger.debug(f"Exa domain search failed: {e}")

                scoped_count = len(pages) - broad_count
                logger.info(f"  [Stage 3a] Exa domain-scoped ({domain}): {scoped_count} pages")
                exa_queries.extend(domain_queries)

            costs["exa_cost"] = len(exa_queries) * COST_PER_QUERY["exa_search"] + \
                                len(pages) * COST_PER_QUERY["exa_content"]
    except ImportError:
        logger.warning("exa-py not installed — skipping Exa search")

    # 3B: Serper targeted search (different query patterns than Exa)
    exa_page_count = len(pages)
    serper_queries = [
        # Organization/conference angle
        f'"{district}" CSTA OR ISTE OR "Code.org" computer science teacher',
        # Job posting angle (reveals positions and sometimes incumbents)
        f'"{district}" "computer science" OR "CTE" position OR hire OR coordinator',
        # Board meeting / news angle
        f'"{district}" "computer science" OR "STEM program" director OR coordinator announcement',
        # State education directory angle
        f'site:tea.texas.gov OR site:cde.ca.gov OR site:isbe.net "{district}" staff'
        if state in ("Texas", "California", "Illinois") else
        f'"{district}" {state} education directory staff',
    ]
    serper_results = await serper_search(serper_queries)
    urls = extract_urls_from_serper(serper_results, max_urls=8)
    snippets = []
    for result in serper_results:
        for item in result.get("organic", []):
            url = item.get("link", "")
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            if url and snippet:
                snippets.append((url, f"Title: {title}\nURL: {url}\n{snippet}"))
    pages.extend(snippets)

    # Scrape top unique URLs not already in Exa results
    exa_urls = {u for u, _ in pages[:exa_page_count]}
    new_urls = [u for u in urls if u not in exa_urls][:5]
    scraped = await scrape_with_httpx(new_urls)
    pages.extend(scraped)

    costs["serper_cost"] = len(serper_queries) * COST_PER_QUERY["serper"]
    logger.info(f"  [Stage 3b] Serper: {len(snippets)} snippets + {len(scraped)} scraped pages")

    return pages, costs


# ─────────────────────────────────────────────
# STAGE 4: Claude Extraction (same as eval, with quality fixes)
# ─────────────────────────────────────────────

def extract_contacts(pages: list[tuple[str, str]], district_name: str) -> tuple[list[dict], dict]:
    """Extract contacts from pages with Claude. Returns (contacts, usage_info)."""
    from anthropic import Anthropic

    SYSTEM = f"""You are a precise data extraction assistant for K-12 education sales.

Extract CS/STEM/CTE contacts from the content below for "{district_name}" ONLY.

Return ONLY a valid JSON array. Each object:
{{
  "first_name": "", "last_name": "", "title": "", "email": "",
  "work_phone": "", "account": "", "source_url": "", "email_confidence": "", "notes": ""
}}

CRITICAL:
1. Each email MUST belong to that specific person. Match rows independently in tables.
2. ONLY extract contacts from {district_name}. Skip people from other districts.
3. email_confidence: VERIFIED (shown on same line/row), LIKELY (pattern match confirmed),
   INFERRED (pattern guess), UNKNOWN (no email found).
4. Phone numbers go in work_phone, NOT email.
5. Target titles: CS, STEM, CTE, EdTech, Curriculum, Technology, Innovation, Robotics,
   Superintendent, Principal, AP CS, Makerspace, Digital Learning, Librarian, Title I.
6. If no contacts found, return [].
"""

    client = Anthropic()
    all_contacts = []
    seen = set()
    total_input = 0
    total_output = 0
    district_hint = _extract_district_domain_hint(district_name)
    pages_skipped = 0

    for url, content in pages:
        if not content or len(content.strip()) < 50:
            continue

        chunk = content[:12000]

        # TWO-PASS: Quick local classification before expensive Claude call
        # Check if page likely contains contact data (names + emails/phones/titles)
        content_lower = chunk.lower()
        contact_signals = sum([
            "@" in chunk,  # email addresses present
            any(t in content_lower for t in ["director", "coordinator", "teacher",
                "principal", "specialist", "superintendent", "staff"]),
            any(p in content_lower for p in ["phone", "email", "ext.", "extension"]),
            any(d in content_lower for d in ["department", "directory", "faculty",
                "our team", "contact us", "administration"]),
        ])
        if contact_signals < 2:
            pages_skipped += 1
            continue

        prompt = f"District: {district_name}\nSource: {url}\n\n---\n{chunk}\n---\n\nExtract contacts. JSON array only."

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=2000,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            total_input += resp.usage.input_tokens
            total_output += resp.usage.output_tokens

            raw = resp.content[0].text.strip()
            # Strip markdown/preamble
            bracket_start = raw.find("[")
            bracket_end = raw.rfind("]")
            if bracket_start >= 0 and bracket_end > bracket_start:
                raw = raw[bracket_start:bracket_end + 1]

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
                    if validation in ("REJECT", "CROSS_DISTRICT", "NAME_MISMATCH"):
                        email = ""
                        confidence = "UNKNOWN"

                key = f"{fn.lower()}|{ln.lower()}"
                if key not in seen:
                    seen.add(key)
                    all_contacts.append({
                        "first_name": fn,
                        "last_name": ln,
                        "title": str(c.get("title", "")).strip(),
                        "email": email,
                        "email_confidence": confidence,
                        "work_phone": str(c.get("work_phone", "")).strip(),
                        "account": str(c.get("account", "")).strip(),
                        "source_url": url,
                    })

        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Extraction error for {url}: {e}")

    if pages_skipped:
        logger.info(f"    Two-pass filter: skipped {pages_skipped}/{pages_skipped + len(all_contacts) + (total_input > 0)} "
                     f"pages (no contact signals) — saved ~${pages_skipped * 0.003:.3f}")

    usage = {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "est_cost": (total_input * 3.0 / 1_000_000) + (total_output * 15.0 / 1_000_000),
    }
    return all_contacts, usage


# ─────────────────────────────────────────────
# STAGE 5: Email Pattern Inference (Adaptive)
# ─────────────────────────────────────────────

def _normalize_name_for_email(name: str) -> str:
    """Normalize a name for email pattern matching.
    Removes apostrophes, periods, suffixes, and non-alpha chars."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" jr.", " jr", " sr.", " sr", " ii", " iii", " iv", " v"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    # Remove punctuation (apostrophes, periods, hyphens kept as empty)
    name = re.sub(r"[^a-z ]", "", name)
    # Take first word if multi-word (e.g., "mary ann" → "mary")
    parts = name.split()
    return parts[0] if parts else name


def _detect_pattern(local: str, fn: str, ln: str) -> str:
    """Try to match an email local part against known patterns.
    Handles name swaps (Firecrawl sometimes reverses first/last)."""

    # Try both orientations: fn/ln as given, and swapped
    for first, last in [(fn, ln), (ln, fn)]:
        if not first or not last:
            continue
        if local == f"{first}.{last}":
            return "first.last"
        if local == f"{first[0]}{last}":
            return "flast"
        if local == f"{first}{last[0]}":
            return "firstl"
        if local == f"{first}_{last}":
            return "first_last"
        if local == f"{first[0]}.{last}":
            return "f.last"
        if local == f"{last}.{first}":
            return "last.first"
        if local == f"{first[:2]}{last}":
            return "filast"

    return "unknown"


def infer_email_patterns(contacts: list[dict], domain: str) -> list[dict]:
    """Adaptive email pattern inference from verified emails.

    Smarter than naive pattern matching:
    - Normalizes names (removes apostrophes, suffixes, special chars)
    - Handles first/last name swaps (common from Firecrawl extract)
    - Detects the dominant email domain from verified emails
    - Applies pattern with confidence-based thresholds
    - Fixes swapped names when pattern match reveals the swap
    """
    if not domain:
        return contacts

    # Collect verified emails and detect patterns
    verified_emails = []
    for c in contacts:
        if c["email"] and c["email_confidence"] in ("VERIFIED", "LIKELY"):
            verified_emails.append(c)

    if not verified_emails:
        logger.info("  [Stage 5] No verified emails to learn patterns from")
        return contacts

    # Detect dominant email domain
    domain_votes = Counter()
    for c in verified_emails:
        _, dom = c["email"].rsplit("@", 1)
        domain_votes[dom] += 1
    email_domain = domain_votes.most_common(1)[0][0]

    # Detect patterns from verified emails (with name normalization)
    pattern_votes = Counter()
    for c in verified_emails:
        local, dom = c["email"].rsplit("@", 1)
        if dom != email_domain:
            continue
        fn = _normalize_name_for_email(c["first_name"])
        ln = _normalize_name_for_email(c["last_name"])
        pattern = _detect_pattern(local.lower(), fn, ln)
        pattern_votes[pattern] += 1

    # Remove unknowns and find best pattern
    known_votes = {k: v for k, v in pattern_votes.items() if k != "unknown"}
    if not known_votes:
        logger.info(f"  [Stage 5] Could not determine email pattern "
                     f"(all {pattern_votes.get('unknown', 0)} were unknown)")
        return contacts

    best_pattern, count = Counter(known_votes).most_common(1)[0]
    total_checked = sum(pattern_votes.values())
    confidence_ratio = count / total_checked if total_checked else 0

    logger.info(f"  [Stage 5] Detected pattern: {best_pattern}@{email_domain} "
                f"({count}/{total_checked} match, {confidence_ratio:.0%} confidence, "
                f"{pattern_votes.get('unknown', 0)} unknown)")

    # Lower threshold: if we have 3+ matches, even 30% confidence is enough
    # because "unknown" often means name swap or suffix, not a different pattern
    min_matches = 3
    min_confidence = 0.3
    if count < min_matches and confidence_ratio < min_confidence:
        logger.info(f"  [Stage 5] Insufficient evidence — need {min_matches}+ matches or "
                     f"{min_confidence:.0%}+ confidence")
        return contacts

    # Also try to fix contacts with swapped first/last names
    # If pattern is first.last but contact has email last.first, swap the names
    for c in contacts:
        if not c["email"]:
            continue
        local, dom = c["email"].rsplit("@", 1)
        if dom != email_domain:
            continue
        fn = _normalize_name_for_email(c["first_name"])
        ln = _normalize_name_for_email(c["last_name"])
        # Check if names are swapped
        if best_pattern == "first.last" and local.lower() == f"{ln}.{fn}":
            # Swap names to correct order
            c["first_name"], c["last_name"] = c["last_name"], c["first_name"]
            logger.debug(f"    Fixed swapped names: {c['first_name']} {c['last_name']}")

    # Apply pattern to contacts without emails
    inferred_count = 0
    for c in contacts:
        if c["email"]:
            continue
        fn = _normalize_name_for_email(c["first_name"])
        ln = _normalize_name_for_email(c["last_name"])
        if not fn or not ln:
            continue

        if best_pattern == "first.last":
            inferred = f"{fn}.{ln}@{email_domain}"
        elif best_pattern == "flast":
            inferred = f"{fn[0]}{ln}@{email_domain}"
        elif best_pattern == "firstl":
            inferred = f"{fn}{ln[0]}@{email_domain}"
        elif best_pattern == "first_last":
            inferred = f"{fn}_{ln}@{email_domain}"
        elif best_pattern == "f.last":
            inferred = f"{fn[0]}.{ln}@{email_domain}"
        elif best_pattern == "filast":
            inferred = f"{fn[:2]}{ln}@{email_domain}"
        elif best_pattern == "last.first":
            inferred = f"{ln}.{fn}@{email_domain}"
        else:
            continue

        c["email"] = inferred
        c["email_confidence"] = "INFERRED"
        c["notes"] = f"Pattern: {best_pattern} (from {count} verified examples)"
        inferred_count += 1

    logger.info(f"  [Stage 5] Inferred {inferred_count} emails using "
                f"{best_pattern}@{email_domain}")
    return contacts


# ─────────────────────────────────────────────
# STAGE 6: Brave Search (independent index = unique results)
# ─────────────────────────────────────────────

async def brave_search(district: str, state: str) -> tuple[list[tuple[str, str]], float]:
    """Search Brave's independent index for pages Google/Exa may miss.
    Brave has its own crawler — different index = different results."""
    import httpx

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.info("  [Stage 6] BRAVE_API_KEY not set — skipping")
        return [], 0.0

    pages = []
    queries = [
        f"{district} {state} computer science STEM CTE staff directory email",
        f"{district} technology coordinator curriculum director contact",
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        for query in queries:
            try:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                    params={"q": query, "count": 10},
                )
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("web", {}).get("results", []):
                    url = item.get("url", "")
                    desc = item.get("description", "")
                    title = item.get("title", "")
                    if url and desc:
                        pages.append((url, f"Title: {title}\nURL: {url}\n{desc}"))
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Brave search failed: {e}")

    if pages:
        logger.info(f"  [Stage 6] Brave: {len(pages)} results from independent index")

    # Free tier: 2,000 queries/month, $0 cost
    return pages, 0.0


# ─────────────────────────────────────────────
# STAGE 7: Firecrawl Agent (autonomous multi-step research)
# ─────────────────────────────────────────────

async def firecrawl_agent_research(domain: str, district: str) -> tuple[list[dict], float]:
    """Use Firecrawl's AI agent to autonomously research the district.
    The agent can navigate, click, search, and extract — like a human researcher."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        return [], 0.0

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key or not domain:
        return [], 0.0

    fc = FirecrawlApp(api_key=api_key)
    contacts = []

    try:
        logger.info(f"  [Stage 7] Firecrawl agent researching {district}...")

        # Use start_agent (async) with poll, more reliable than blocking agent()
        job = fc.start_agent(
            urls=[f"https://{domain}"],
            prompt=(
                f"Go to https://{domain} and find staff members who work in "
                "Computer Science, STEM, CTE, Educational Technology, Curriculum, "
                "or Technology departments. Also find school principals. "
                "Navigate to staff directory pages, department pages, and school pages. "
                "Extract: full name, job title, email address, phone number, and department."
            ),
            schema={
                "type": "object",
                "properties": {
                    "contacts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                                "title": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "school_or_department": {"type": "string"},
                            }
                        }
                    }
                }
            },
            max_credits=20,
        )

        # Poll for results
        job_id = job.id if hasattr(job, 'id') else (job.get('id') if isinstance(job, dict) else str(job))
        if job_id:
            for _ in range(30):  # max 150s
                await asyncio.sleep(5)
                status = fc.get_agent_status(job_id)
                state = getattr(status, 'status', None) or (status.get('status') if isinstance(status, dict) else None)
                if state == 'completed':
                    result = status
                    break
                elif state in ('failed', 'error'):
                    logger.warning(f"    Agent failed: {status}")
                    result = None
                    break
            else:
                logger.warning(f"    Agent timed out after 150s")
                result = None
        else:
            result = job  # Fallback if no job_id

        data = None
        if hasattr(result, 'data'):
            data = result.data
        elif isinstance(result, dict):
            data = result

        if data and isinstance(data, dict):
            for c in data.get("contacts", []):
                fn = str(c.get("first_name", "")).strip()
                ln = str(c.get("last_name", "")).strip()
                email = str(c.get("email", "")).strip()
                if not fn and not ln:
                    continue
                if email and "***" in email:
                    email = ""
                contacts.append({
                    "first_name": fn,
                    "last_name": ln,
                    "title": str(c.get("title", "")).strip(),
                    "email": email.lower() if email else "",
                    "work_phone": str(c.get("phone", "")).strip(),
                    "account": str(c.get("school_or_department", "")).strip(),
                    "source_url": f"https://{domain}",
                    "email_confidence": "VERIFIED" if email and "***" not in email else "UNKNOWN",
                })

        logger.info(f"    Firecrawl agent: {len(contacts)} contacts, "
                    f"{sum(1 for c in contacts if c['email'])} with email")

    except Exception as e:
        logger.warning(f"  [Stage 7] Firecrawl agent failed: {e}")

    cost = 0.40  # estimate: 25 credits max at $0.016/credit
    return contacts, cost


# ─────────────────────────────────────────────
# STAGE 8: Agentic Follow-up Chain (reason → search → learn → repeat)
# ─────────────────────────────────────────────

async def agentic_followup(contacts: list[dict], district: str, domain: str,
                           state: str) -> tuple[list[dict], float]:
    """Multi-step agentic reasoning that decides what to search next based on
    what it already knows. This is the 'second brain' — it thinks like a human
    researcher and fills gaps intelligently.

    Strategies:
    1. Person search — search for specific high-value people still missing emails
    2. Team expansion — found a director? Search for their team/department staff
    3. Conference mining — search CSTA/ISTE/Code.org for district mentions
    4. Org chart inference — found leadership? Search for their direct reports
    """
    cost = 0.0
    district_hint = _extract_district_domain_hint(district)
    new_contacts_found = 0

    # ── Strategy 1: Person search for high-value contacts without emails ──
    high_value_titles = {
        "director", "coordinator", "specialist", "superintendent",
        "principal", "manager", "lead", "chair",
    }
    targets = [c for c in contacts if not c.get("email")
               and any(t in c.get("title", "").lower() for t in high_value_titles)]

    if targets:
        logger.info(f"  [Stage 8a] Person search: {len(targets)} high-value contacts need emails")
        queries = []
        query_to_contact = {}
        for c in targets[:8]:
            name = f"{c['first_name']} {c['last_name']}"
            q = f'"{name}" "{district}" email'
            queries.append(q)
            query_to_contact[q] = c

        results = await serper_search(queries)
        cost += len(queries) * COST_PER_QUERY["serper"]

        found = 0
        for query, result in zip(queries, results):
            target = query_to_contact[query]
            if target.get("email"):
                continue
            for item in result.get("organic", []):
                snippet = item.get("snippet", "") + " " + item.get("title", "")
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                for email in emails:
                    validation = _validate_email(email.lower(), target["first_name"],
                                                  target["last_name"], district_hint)
                    if not validation:
                        target["email"] = email.lower()
                        target["email_confidence"] = "LIKELY"
                        target["notes"] = f"Found via person search"
                        found += 1
                        break
                if target.get("email"):
                    break
        logger.info(f"    Found {found} emails via person search")

    # ── Strategy 2: Team expansion — found leaders? Search for their departments ──
    leaders = [c for c in contacts if c.get("email") and
               any(t in c.get("title", "").lower()
                   for t in ["director", "superintendent", "coordinator", "chair"])]

    if leaders:
        dept_queries = []
        for leader in leaders[:3]:
            title = leader["title"]
            # Extract department hint from title
            for keyword in ["technology", "cs", "computer science", "cte",
                            "stem", "curriculum", "innovation", "digital"]:
                if keyword in title.lower():
                    dept_queries.append(
                        f'"{district}" "{keyword}" department staff team members')
                    break

        if dept_queries:
            logger.info(f"  [Stage 8b] Team expansion: searching {len(dept_queries)} departments")
            results = await serper_search(dept_queries)
            cost += len(dept_queries) * COST_PER_QUERY["serper"]

            # Scrape top results for new contacts
            urls = extract_urls_from_serper(results, max_urls=3)
            if urls:
                scraped = await scrape_with_httpx(urls)
                if scraped:
                    new_pages = filter_pages_for_district(scraped, district, state)
                    if new_pages:
                        new_contacts, usage = extract_contacts(new_pages, district)
                        cost += usage["est_cost"]
                        # Add new unique contacts
                        existing_keys = {f"{c['first_name'].lower()}|{c['last_name'].lower()}"
                                         for c in contacts}
                        for nc in new_contacts:
                            key = f"{nc['first_name'].lower()}|{nc['last_name'].lower()}"
                            if key not in existing_keys:
                                existing_keys.add(key)
                                contacts.append(nc)
                                new_contacts_found += 1
                        logger.info(f"    Team expansion: found {new_contacts_found} new contacts")

    # ── Strategy 3: Conference/organization mining ──
    conference_queries = [
        f'"{district}" CSTA site:csteachers.org',
        f'"{district}" site:code.org teacher OR coordinator',
        f'"{district}" ISTE OR TCEA computer science presenter',
    ]
    # Only run 1-2 of these to control cost
    conference_queries = conference_queries[:2]
    logger.info(f"  [Stage 8c] Conference mining: {len(conference_queries)} searches")
    conf_results = await serper_search(conference_queries)
    cost += len(conference_queries) * COST_PER_QUERY["serper"]

    for result in conf_results:
        for item in result.get("organic", []):
            snippet = item.get("snippet", "")
            title_text = item.get("title", "")
            # Look for emails in snippets
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
            for email in emails:
                # Try to find the associated name from context
                # Simple heuristic: look for capitalized name-like words near the email
                name_matches = re.findall(r'([A-Z][a-z]+)\s+([A-Z][a-z]+)', snippet)
                for fn, ln in name_matches:
                    validation = _validate_email(email.lower(), fn, ln, district_hint)
                    if not validation:
                        key = f"{fn.lower()}|{ln.lower()}"
                        existing_keys = {f"{c['first_name'].lower()}|{c['last_name'].lower()}"
                                         for c in contacts}
                        if key not in existing_keys:
                            contacts.append({
                                "first_name": fn,
                                "last_name": ln,
                                "title": "Found via conference/org",
                                "email": email.lower(),
                                "email_confidence": "LIKELY",
                                "work_phone": "",
                                "account": district,
                                "source_url": item.get("link", ""),
                                "notes": f"Conference mining: {title_text[:50]}",
                            })
                            new_contacts_found += 1
                            break

    logger.info(f"  [Stage 8] Agentic followup total: {new_contacts_found} new contacts, "
                f"cost=${cost:.4f}")
    return contacts, cost


# ─────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────

async def deep_research(district: str, state: str) -> dict:
    """Run the full multi-stage deep research pipeline."""
    t_start = time.time()
    result = {
        "district": district,
        "state": state,
        "stages": {},
        "contacts": [],
        "totals": {},
    }
    all_pages = []
    total_cost = 0.0

    # ── Stage 1: Domain Discovery ──
    t0 = time.time()
    domain = await discover_domain(district, state)
    stage1_time = time.time() - t0
    result["stages"]["1_domain"] = {
        "domain": domain,
        "time": stage1_time,
        "cost": COST_PER_QUERY["serper"],
    }
    total_cost += COST_PER_QUERY["serper"]
    logger.info(f"  [Stage 1] Domain: {domain or '(not found)'} ({stage1_time:.1f}s)")

    # ── Stage 2A: Firecrawl Extract (structured contacts directly from site) ──
    fc_extract_contacts = []
    if domain:
        t0 = time.time()
        fc_extract_contacts, fc_extract_cost = await firecrawl_extract_contacts(domain, district)
        stage2a_time = time.time() - t0
        result["stages"]["2a_fc_extract"] = {
            "contacts": len(fc_extract_contacts),
            "with_email": sum(1 for c in fc_extract_contacts if c["email"]),
            "time": stage2a_time,
            "cost": fc_extract_cost,
        }
        total_cost += fc_extract_cost
    else:
        result["stages"]["2a_fc_extract"] = {"contacts": 0, "time": 0, "cost": 0}

    # ── Stage 2B: Site Mapping (Firecrawl map + scrape staff pages) ──
    t0 = time.time()
    site_pages, fc_credits = await map_and_scrape_district_site(domain, district) if domain else ([], 0)
    stage2b_time = time.time() - t0
    stage2b_cost = fc_credits * COST_PER_QUERY["firecrawl_scrape"]
    result["stages"]["2b_site_map"] = {
        "pages": len(site_pages),
        "credits": fc_credits,
        "time": stage2b_time,
        "cost": stage2b_cost,
    }
    total_cost += stage2b_cost
    all_pages.extend(site_pages)

    # ── Stage 3: Broad Search (Exa broad + domain-scoped + Serper creative angles) ──
    t0 = time.time()
    search_pages, search_costs = await broad_search(district, state, domain)
    stage3_time = time.time() - t0
    stage3_cost = search_costs["exa_cost"] + search_costs["serper_cost"]
    result["stages"]["3_broad_search"] = {
        "pages": len(search_pages),
        "time": stage3_time,
        "cost": stage3_cost,
    }
    total_cost += stage3_cost
    all_pages.extend(search_pages)

    # ── Pre-filter pages ──
    pre_count = len(all_pages)
    all_pages = filter_pages_for_district(all_pages, district, state)
    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for url, content in all_pages:
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append((url, content))
    all_pages = deduped
    logger.info(f"  [Filter] {pre_count} → {len(all_pages)} pages (filtered + deduped)")

    # ── Stage 4: Claude Extraction from scraped/searched pages ──
    t0 = time.time()
    claude_contacts, usage = extract_contacts(all_pages, district)
    stage4_time = time.time() - t0
    result["stages"]["4_extraction"] = {
        "pages_processed": len(all_pages),
        "contacts_found": len(claude_contacts),
        "with_email": sum(1 for c in claude_contacts if c["email"]),
        "time": stage4_time,
        "cost": usage["est_cost"],
    }
    total_cost += usage["est_cost"]
    logger.info(f"  [Stage 4] Claude extracted {len(claude_contacts)} contacts, "
                f"{sum(1 for c in claude_contacts if c['email'])} with email ({stage4_time:.1f}s)")

    # ── Merge: Combine Firecrawl extract + Claude extract, deduplicate ──
    contacts = list(fc_extract_contacts)  # Start with Firecrawl extract (higher quality emails)
    seen_keys = set()
    for c in contacts:
        key = f"{c['first_name'].lower()}|{c['last_name'].lower()}"
        seen_keys.add(key)

    # Add Claude contacts that aren't duplicates
    for c in claude_contacts:
        key = f"{c['first_name'].lower()}|{c['last_name'].lower()}"
        if key not in seen_keys:
            seen_keys.add(key)
            contacts.append(c)
        elif not any(ec['email'] for ec in contacts if f"{ec['first_name'].lower()}|{ec['last_name'].lower()}" == key):
            # Claude found an email for someone Firecrawl didn't — merge
            for ec in contacts:
                if f"{ec['first_name'].lower()}|{ec['last_name'].lower()}" == key and not ec['email'] and c['email']:
                    ec['email'] = c['email']
                    ec['email_confidence'] = c.get('email_confidence', 'LIKELY')

    logger.info(f"  [Merge] {len(fc_extract_contacts)} from Firecrawl + {len(claude_contacts)} from Claude "
                f"→ {len(contacts)} unique contacts")

    # ── Stage 5: Email Pattern Inference ──
    t0 = time.time()
    contacts = infer_email_patterns(contacts, domain)
    stage5_time = time.time() - t0
    result["stages"]["5_inference"] = {
        "inferred": sum(1 for c in contacts if c.get("email_confidence") == "INFERRED"),
        "time": stage5_time,
    }

    # ── Stage 6: Brave Search (independent index) ──
    t0 = time.time()
    brave_pages, brave_cost = await brave_search(district, state)
    stage6_time = time.time() - t0
    if brave_pages:
        brave_pages = filter_pages_for_district(brave_pages, district, state)
        # Extract contacts from Brave results
        if brave_pages:
            brave_contacts, brave_usage = extract_contacts(brave_pages, district)
            brave_cost += brave_usage["est_cost"]
            existing_keys = {f"{c['first_name'].lower()}|{c['last_name'].lower()}" for c in contacts}
            brave_new = 0
            for bc in brave_contacts:
                key = f"{bc['first_name'].lower()}|{bc['last_name'].lower()}"
                if key not in existing_keys:
                    existing_keys.add(key)
                    contacts.append(bc)
                    brave_new += 1
            if brave_new:
                logger.info(f"    Brave added {brave_new} new contacts")
    result["stages"]["6_brave"] = {"pages": len(brave_pages), "time": stage6_time, "cost": brave_cost}
    total_cost += brave_cost

    # ── Stage 7: Firecrawl Agent (autonomous research) ──
    t0 = time.time()
    agent_contacts, agent_cost = await firecrawl_agent_research(domain, district)
    stage7_time = time.time() - t0
    if agent_contacts:
        existing_keys = {f"{c['first_name'].lower()}|{c['last_name'].lower()}" for c in contacts}
        agent_new = 0
        for ac in agent_contacts:
            key = f"{ac['first_name'].lower()}|{ac['last_name'].lower()}"
            if key not in existing_keys:
                existing_keys.add(key)
                contacts.append(ac)
                agent_new += 1
            elif ac.get("email"):
                # Agent found email for existing contact without one
                for ec in contacts:
                    if f"{ec['first_name'].lower()}|{ec['last_name'].lower()}" == key and not ec["email"]:
                        ec["email"] = ac["email"]
                        ec["email_confidence"] = ac.get("email_confidence", "LIKELY")
                        break
        if agent_new:
            logger.info(f"    Firecrawl agent added {agent_new} new contacts")
    result["stages"]["7_fc_agent"] = {
        "contacts": len(agent_contacts), "time": stage7_time, "cost": agent_cost
    }
    total_cost += agent_cost

    # ── Stage 8: Agentic Follow-up Chain ──
    t0 = time.time()
    contacts, followup_cost = await agentic_followup(contacts, district, domain, state)
    stage8_time = time.time() - t0
    result["stages"]["8_agentic"] = {"time": stage8_time, "cost": followup_cost}
    total_cost += followup_cost

    # ── Re-run pattern inference (new contacts may provide new patterns) ──
    pre_inferred = sum(1 for c in contacts if c.get("email_confidence") == "INFERRED")
    contacts = infer_email_patterns(contacts, domain)
    post_inferred = sum(1 for c in contacts if c.get("email_confidence") == "INFERRED")
    if post_inferred > pre_inferred:
        logger.info(f"  [Re-inference] {post_inferred - pre_inferred} additional emails inferred")

    # ── Final summary ──
    total_time = time.time() - t_start
    with_email = sum(1 for c in contacts if c["email"])
    verified = sum(1 for c in contacts if c.get("email_confidence") == "VERIFIED")
    likely = sum(1 for c in contacts if c.get("email_confidence") == "LIKELY")
    inferred = sum(1 for c in contacts if c.get("email_confidence") == "INFERRED")

    result["contacts"] = contacts
    result["totals"] = {
        "total_contacts": len(contacts),
        "with_email": with_email,
        "verified": verified,
        "likely": likely,
        "inferred": inferred,
        "total_time": total_time,
        "total_cost": total_cost,
    }

    return result


def print_result(result: dict):
    """Pretty-print deep research results."""
    d = result["district"]
    s = result["state"]
    t = result["totals"]

    print(f"\n{'='*80}")
    print(f"DEEP RESEARCH: {d} ({s})")
    print(f"{'='*80}")

    # Stage breakdown
    for stage_key in sorted(result["stages"]):
        stage = result["stages"][stage_key]
        parts = [f"{k}={v}" for k, v in stage.items() if k != "time"]
        print(f"  {stage_key}: {', '.join(parts)} ({stage['time']:.1f}s)")

    # Contacts
    print(f"\n  CONTACTS: {t['total_contacts']} total, {t['with_email']} with email")
    print(f"    VERIFIED: {t['verified']}  |  LIKELY: {t['likely']}  |  INFERRED: {t['inferred']}")
    print(f"    Total time: {t['total_time']:.1f}s  |  Total cost: ${t['total_cost']:.4f}")

    print(f"\n  {'Name':<35s} {'Title':<30s} {'Email':<40s} {'Conf':<10s}")
    print(f"  {'-'*115}")
    for c in result["contacts"]:
        name = f"{c['first_name']} {c['last_name']}"
        email = c["email"] or "(none)"
        conf = c.get("email_confidence", "")
        marker = {"VERIFIED": "✓", "LIKELY": "~", "INFERRED": "?"}.get(conf, " ")
        print(f"  {marker} {name:<33s} {c['title']:<30s} {email:<40s} {conf:<10s}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Multi-stage deep research engine")
    parser.add_argument("district", nargs="?", help="District name")
    parser.add_argument("state", nargs="?", help="State name")
    parser.add_argument("--all", action="store_true", help="Run all test districts")
    parser.add_argument("--phase1", action="store_true", help="Run Phase 1 districts only")
    args = parser.parse_args()

    if args.all:
        districts = TEST_DISTRICTS
    elif args.phase1:
        districts = [d for d in TEST_DISTRICTS if d["name"] in ["Houston ISD", "Guthrie Public Schools"]]
    elif args.district and args.state:
        districts = [{"name": args.district, "state": args.state}]
    else:
        parser.print_help()
        return

    all_results = []
    for d in districts:
        print(f"\n{'#'*80}")
        print(f"# {d['name']} ({d['state']})")
        print(f"{'#'*80}")
        result = asyncio.run(deep_research(d["name"], d["state"]))
        print_result(result)
        all_results.append(result)

    # Summary across all districts
    if len(all_results) > 1:
        print(f"\n{'='*80}")
        print(f"AGGREGATE DEEP RESEARCH RESULTS")
        print(f"{'='*80}")
        total_c = sum(r["totals"]["total_contacts"] for r in all_results)
        total_e = sum(r["totals"]["with_email"] for r in all_results)
        total_v = sum(r["totals"]["verified"] for r in all_results)
        total_l = sum(r["totals"]["likely"] for r in all_results)
        total_i = sum(r["totals"]["inferred"] for r in all_results)
        total_cost = sum(r["totals"]["total_cost"] for r in all_results)
        total_time = sum(r["totals"]["total_time"] for r in all_results)
        print(f"  Districts: {len(all_results)}")
        print(f"  Total contacts: {total_c}  |  With email: {total_e}")
        print(f"  VERIFIED: {total_v}  |  LIKELY: {total_l}  |  INFERRED: {total_i}")
        print(f"  Total cost: ${total_cost:.4f}  |  Total time: {total_time:.0f}s")
        print(f"  Avg per district: {total_e/len(all_results):.1f} emails, "
              f"${total_cost/len(all_results):.4f}, {total_time/len(all_results):.0f}s")

    # Save results
    results_file = RESULTS_DIR / "deep_research_results.json"
    results_file.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()
