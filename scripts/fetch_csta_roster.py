#!/usr/bin/env python3
"""Build memory/csta_roster.json — one-shot CSTA chapter leader roster.

Two-phase pipeline:
  Phase 1 (Discovery): Serper queries find CSTA chapter pages on
    csteachers.org subdomains + LinkedIn snippets for each territory state.
  Phase 2 (Extraction): httpx + BeautifulSoup fetch each csteachers.org URL
    with a browser User-Agent, combine text with national seed pages and
    LinkedIn snippets, feed to Claude Haiku for structured extraction.

Why this shape: CSTA rosters are essentially static directory data. Daily
scanning is architecturally wrong (see project_f5_csta_scanner_low_yield.md
and BUG 2 plan). Fetch once, cache to JSON, enrich F2 (and future scanners)
inline via signal_processor.enrich_with_csta.

Run: python3 scripts/fetch_csta_roster.py
Output: memory/csta_roster.json
Cost: ~$0.10 one-time (Serper + Haiku).
Refresh: manually, quarterly or when CSTA announces new chapter boards.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
for ln in (ROOT / ".env").read_text().splitlines():
    if "=" in ln and not ln.startswith("#"):
        k, _, v = ln.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from tools.signal_processor import TERRITORY_STATES_WITH_CA, ABBR_TO_STATE_NAME, SERPER_URL  # noqa: E402
from tools import csv_importer  # noqa: E402

SERPER_KEY = os.environ.get("SERPER_API_KEY", "")
if not SERPER_KEY:
    sys.exit("SERPER_API_KEY not set")

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

NATIONAL_SEEDS = [
    "https://csteachers.org/board-of-directors/",
    "https://csteachers.org/team/",
]

OUTPUT_PATH = ROOT / "memory" / "csta_roster.json"


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

    return cst_urls, linkedin_snippets


# ──────────────────────────────────────────────────────────
# Phase 2 — Extraction
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


def build_haiku_corpus(cst_urls: set[str], linkedin_snippets: list[dict]) -> str:
    """Fetch each csteachers.org URL + combine with LinkedIn snippets into a
    single corpus for Haiku extraction."""
    blocks = []

    for url in sorted(cst_urls):
        print(f"  fetching {url}")
        text = fetch_page_text(url)
        if not text:
            continue
        blocks.append(f"\n===== URL: {url}\n{text}\n")

    if linkedin_snippets:
        blocks.append("\n===== LinkedIn snippets =====")
        for ls in linkedin_snippets:
            blocks.append(
                f"\n-- [{ls.get('state_hint','')}] {ls.get('title','')}\n"
                f"URL: {ls.get('url','')}\n"
                f"{ls.get('snippet','')}\n"
            )

    combined = "".join(blocks)
    print(f"\n  Corpus: {len(combined):,} chars from {len(cst_urls)} URLs + {len(linkedin_snippets)} LinkedIn snippets")
    # Cap at 500K chars (~165K tokens) to stay comfortable in Haiku's 200K
    # context while capturing the full high-value corpus.
    return combined[:500000]


HAIKU_PROMPT_TEMPLATE = """Extract CSTA (Computer Science Teachers Association) state and regional CHAPTER board members and officers from these pages.

For each person, return JSON:
{{
  "name": "Full name",
  "role": "Chapter role — e.g. 'President', 'Vice President', 'Secretary', 'K-12 Board Member', 'Treasurer'",
  "chapter": "CSTA chapter name — e.g. 'CSTA Pittsburgh', 'CSTA Longwood', 'CSTA Arizona'",
  "state": "2-letter state code of their K-12 SCHOOL EMPLOYER, NOT their chapter's state (usually the same, but not always)",
  "district": "Exact K-12 school district name where this person works. Empty string '' if the page does not explicitly name a district — do NOT guess, do NOT use the chapter city as a district, do NOT fabricate.",
  "source_url": "Copy one of the '===== URL:' lines from the input that mentions this person. Do not fabricate."
}}

STRICT RULES:
- Only STATE or REGIONAL chapter officers/board members. SKIP the national
  CSTA Board of Directors (they are too disconnected from any single district).
- SKIP university professors and college advisors — K-12 only.
- SKIP general CSTA staff / HQ employees unless they also hold a state/regional
  chapter role.
- SKIP conference speakers unless explicitly listed as chapter officers.
- `state` is the employer state. A person on the CSTA Chicago chapter whose
  teaching job is in Gary, Indiana gets state="IN".
- `district` must be a real named K-12 LEA. If the page says "high school
  computer science teacher" without naming the district, return `district: ""`.
- `source_url` must be exactly one of the URL lines shown in the input.

Return ONLY a valid JSON array. Empty array [] if nothing qualifies.

Pages:
{corpus}"""


def haiku_extract(corpus: str) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(timeout=120.0)
    prompt = HAIKU_PROMPT_TEMPLATE.format(corpus=corpus)
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
        print("  [warn] Haiku returned no JSON array", file=sys.stderr)
        print(f"  raw: {raw[:400]}", file=sys.stderr)
        return []
    try:
        return json.loads(clean[start : end + 1])
    except json.JSONDecodeError as e:
        print(f"  [warn] JSON parse failed: {e}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────────────────
# Merge + dedup + write
# ──────────────────────────────────────────────────────────


def normalize_and_dedup(items: list[dict]) -> list[dict]:
    """Dedup by normalized person name only (not (name, state)) — chapter state
    and employer state can diverge. Keep the entry with the longest district
    string on collision."""
    by_person: dict[str, dict] = {}
    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        key = csv_importer.normalize_name(name)
        state = (it.get("state") or "").strip().upper()
        district = (it.get("district") or "").strip()
        if state and len(state) != 2:
            continue

        existing = by_person.get(key)
        if existing is None:
            by_person[key] = dict(it)
            by_person[key]["state"] = state
            by_person[key]["district"] = district
            continue

        # Keep the row with a district if one exists, else longer name
        if district and not (existing.get("district") or "").strip():
            by_person[key] = dict(it)
            by_person[key]["state"] = state
            by_person[key]["district"] = district

    merged = list(by_person.values())
    # Pre-compute district_normalized for fast lookup
    for e in merged:
        district = (e.get("district") or "").strip()
        e["district_normalized"] = csv_importer.normalize_name(district) if district else ""
    return merged


def main() -> None:
    print("=== Phase 1: Discovery ===")
    cst_urls, linkedin_snippets = discover_csteachers_urls_and_linkedin_snippets()
    print(f"Discovered {len(cst_urls)} csteachers.org URLs + {len(linkedin_snippets)} LinkedIn snippets")

    print("\n=== Phase 2: Fetch + extract ===")
    corpus = build_haiku_corpus(cst_urls, linkedin_snippets)
    if not corpus.strip():
        print("Empty corpus — nothing to extract. Abort.")
        sys.exit(1)

    print("\n=== Phase 3: Haiku extraction ===")
    items = haiku_extract(corpus)
    print(f"Haiku returned {len(items)} items")

    print("\n=== Phase 4: Dedup + normalize ===")
    entries = normalize_and_dedup(items)
    with_district = [e for e in entries if e.get("district")]
    print(f"After dedup: {len(entries)} unique people, {len(with_district)} with parseable district")

    output = {
        "_comment": (
            "CSTA state/regional chapter roster — enrichment source for F2 "
            "(and extensible to other scanners). Built by "
            "scripts/fetch_csta_roster.py. Refresh manually quarterly or "
            "when CSTA announces new chapter boards. Each entry's `state` "
            "is the person's K-12 EMPLOYER state, NOT their chapter's state. "
            "Entries with empty `district` are kept for /signal_csta display "
            "but ignored during enrich_with_csta matching."
        ),
        "fetched_at": datetime.now().strftime("%Y-%m-%d"),
        "source": "csteachers.org direct fetch + Serper LinkedIn snippets via Claude Haiku",
        "entries": entries,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"   {len(entries)} entries, {len(with_district)} with district")

    # Spot-print first 10 entries
    print("\n=== Sample entries ===")
    for e in entries[:15]:
        d = e.get("district") or "(no district)"
        print(f"  {e.get('state','??'):<2} {e.get('name',''):<35} {e.get('role','')[:25]:<25} {d[:40]}")


if __name__ == "__main__":
    main()
