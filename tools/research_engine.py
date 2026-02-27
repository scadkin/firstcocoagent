"""
research_engine.py — Scout's 10-layer K-12 lead research engine.

Layers:
  1. Serper: direct title search
  2. Serper: title variation sweep
  3. Serper: LinkedIn-targeted search
  4. Serper: district site deep search
  5. Serper: news + grants search (priority signals)
  6. Direct website scrape (BeautifulSoup)
  7. Keyword deep crawl across all pages found
  8. Email pattern inference
  9. Claude extraction pass (all raw content)
  10. Dedup + confidence scoring
"""

import os
import re
import time
import logging
import asyncio
import httpx
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import date

from agent.keywords import (
    SERPER_PRIORITY_TITLES,
    ALL_TITLES,
    CS_KEYWORDS,
    STEM_KEYWORDS,
    TECH_KEYWORDS,
    CTE_KEYWORDS,
    TARGET_DEPARTMENTS,
    EMAIL_PATTERNS,
)
from tools.contact_extractor import (
    extract_contacts,
    extract_from_multiple,
    infer_email,
    detect_email_pattern,
)

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScoutBot/2.0; K12 Education Research)"
}

MAX_CRAWL_PAGES = 30          # max pages to crawl on district site
CRAWL_DELAY = 0.5             # seconds between requests (be polite)
SERPER_REQUESTS_PER_JOB = 15  # stay well under rate limits


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

class ResearchJob:
    """
    Runs all 10 research layers for a given district.
    Call run() to execute. Progress callback fires at key milestones.
    """

    def __init__(self, district_name: str, state: str, progress_callback=None):
        self.district_name = district_name
        self.state = state
        self.progress_callback = progress_callback  # async func(message: str)

        self.raw_pages: list[tuple[str, str]] = []  # (url, content)
        self.all_contacts: list[dict] = []
        self.seen_keys: set[str] = set()
        self.layers_used: list[str] = []
        self.district_domain: str = ""
        self.known_emails: list[str] = []
        self.email_pattern: str = ""

    async def run(self) -> dict:
        """
        Execute all 10 layers. Returns result summary dict.
        """
        await self._progress(f"🔍 Starting research on **{self.district_name}**...")

        # Layer 1: Direct title search
        await self._layer1_direct_title_search()

        # Layer 2: Title variation sweep
        await self._layer2_title_variation_sweep()

        # Layer 3: LinkedIn-targeted
        await self._layer3_linkedin_search()

        # Layer 4: District site deep search
        await self._layer4_district_site_search()

        # Layer 5: News + grants
        await self._layer5_news_grants_search()

        await self._progress(f"🔎 Crawling district website...")

        # Layer 6: Direct scrape
        await self._layer6_direct_scrape()

        # Layer 7: Keyword deep crawl
        await self._layer7_keyword_crawl()

        # Layer 8: Email pattern inference
        await self._layer8_email_inference()

        await self._progress(f"🤖 Running Claude extraction pass...")

        # Layer 9: Claude extraction pass
        await self._layer9_claude_extraction()

        # Layer 10: Dedup + confidence scoring
        await self._layer10_dedup_and_score()

        layers_str = ", ".join(self.layers_used)
        total = len(self.all_contacts)
        with_email = sum(1 for c in self.all_contacts if c.get("email"))
        no_email = total - with_email

        return {
            "district_name": self.district_name,
            "state": self.state,
            "contacts": self.all_contacts,
            "total": total,
            "with_email": with_email,
            "no_email": no_email,
            "layers_used": layers_str,
        }

    # ─────────────────────────────────────────────
    # LAYER 1: Direct Serper title search
    # ─────────────────────────────────────────────

    async def _layer1_direct_title_search(self):
        self.layers_used.append("L1:direct-title")
        queries = [
            f'"{title}" "{self.district_name}" email'
            for title in SERPER_PRIORITY_TITLES[:8]
        ]
        results = await self._serper_batch(queries[:5])
        self._add_raw_from_serper(results)

    # ─────────────────────────────────────────────
    # LAYER 2: Title variation sweep
    # ─────────────────────────────────────────────

    async def _layer2_title_variation_sweep(self):
        self.layers_used.append("L2:title-variations")
        # Use different title phrasings — different results than Layer 1
        varied = [
            f'"{self.district_name}" "computer science" coordinator contact',
            f'"{self.district_name}" STEM director',
            f'"{self.district_name}" CTE director email',
            f'"{self.district_name}" instructional technology coordinator',
            f'"{self.district_name}" curriculum director',
        ]
        results = await self._serper_batch(varied)
        self._add_raw_from_serper(results)

    # ─────────────────────────────────────────────
    # LAYER 3: LinkedIn targeted
    # ─────────────────────────────────────────────

    async def _layer3_linkedin_search(self):
        self.layers_used.append("L3:linkedin")
        queries = [
            f'site:linkedin.com "computer science" "{self.district_name}"',
            f'site:linkedin.com "STEM" "{self.district_name}" director',
            f'site:linkedin.com "instructional technology" "{self.district_name}"',
        ]
        results = await self._serper_batch(queries[:3])
        self._add_raw_from_serper(results)

    # ─────────────────────────────────────────────
    # LAYER 4: District site deep search
    # ─────────────────────────────────────────────

    async def _layer4_district_site_search(self):
        self.layers_used.append("L4:district-site")

        # Find the district domain first
        domain_query = f'"{self.district_name}" official website {self.state}'
        results = await self._serper_batch([domain_query])

        if results:
            for item in results[0].get("organic", []):
                link = item.get("link", "")
                if link and self._looks_like_district_domain(link, self.district_name):
                    parsed = urlparse(link)
                    self.district_domain = parsed.netloc
                    break

        if self.district_domain:
            # Search within the domain
            site_queries = [
                f'site:{self.district_domain} "computer science" OR "coding" OR "STEM"',
                f'site:{self.district_domain} staff directory',
                f'site:{self.district_domain} department contact',
            ]
            results = await self._serper_batch(site_queries[:3])
            self._add_raw_from_serper(results)

    # ─────────────────────────────────────────────
    # LAYER 5: News + grants search
    # ─────────────────────────────────────────────

    async def _layer5_news_grants_search(self):
        self.layers_used.append("L5:news-grants")
        year = date.today().year
        queries = [
            f'"{self.district_name}" "computer science" grant {year}',
            f'"{self.district_name}" STEM program news {year}',
            f'"{self.district_name}" coding curriculum announcement',
        ]
        results = await self._serper_batch(queries[:2])
        self._add_raw_from_serper(results)

    # ─────────────────────────────────────────────
    # LAYER 6: Direct website scrape
    # ─────────────────────────────────────────────

    async def _layer6_direct_scrape(self):
        if not self.district_domain:
            return

        self.layers_used.append("L6:scrape")

        seed_urls = [
            f"https://{self.district_domain}",
            f"https://{self.district_domain}/departments",
            f"https://{self.district_domain}/staff",
            f"https://{self.district_domain}/contact",
            f"https://{self.district_domain}/about",
        ]

        crawled = set()
        for url in seed_urls:
            if url in crawled:
                continue
            content = await self._fetch_page(url)
            if content:
                self.raw_pages.append((url, content))
                crawled.add(url)
                # Extract links for Layer 7
                soup = BeautifulSoup(content, "html.parser")
                self._discover_links(soup, url, crawled)
            await asyncio.sleep(CRAWL_DELAY)

    # ─────────────────────────────────────────────
    # LAYER 7: Keyword deep crawl
    # ─────────────────────────────────────────────

    async def _layer7_keyword_crawl(self):
        if not self.district_domain:
            return

        self.layers_used.append("L7:deep-crawl")

        # Find pages that mention any target department or keyword
        dept_keywords = TARGET_DEPARTMENTS[:10]
        crawl_targets = []

        for url, content in self.raw_pages:
            content_lower = content.lower()
            for kw in dept_keywords:
                if kw.lower() in content_lower:
                    # Extract links from this page too
                    soup = BeautifulSoup(content, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        full_url = urljoin(url, href)
                        if self.district_domain in full_url:
                            crawl_targets.append(full_url)
                    break

        # Deduplicate and crawl up to limit
        existing_urls = {url for url, _ in self.raw_pages}
        new_targets = [u for u in dict.fromkeys(crawl_targets) if u not in existing_urls]

        for url in new_targets[:MAX_CRAWL_PAGES]:
            content = await self._fetch_page(url)
            if content:
                self.raw_pages.append((url, content))
            await asyncio.sleep(CRAWL_DELAY)

    # ─────────────────────────────────────────────
    # LAYER 8: Email pattern inference
    # ─────────────────────────────────────────────

    async def _layer8_email_inference(self):
        self.layers_used.append("L8:email-inference")

        # Collect all emails found so far from raw pages
        for url, content in self.raw_pages:
            found_emails = re.findall(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                content
            )
            if self.district_domain:
                district_emails = [
                    e for e in found_emails
                    if self.district_domain in e or self.district_domain.replace("www.", "") in e
                ]
                self.known_emails.extend(district_emails)

        self.known_emails = list(dict.fromkeys(self.known_emails))

        if self.known_emails and self.district_domain:
            domain = self.district_domain.replace("www.", "")
            self.email_pattern = detect_email_pattern(self.known_emails, domain) or EMAIL_PATTERNS[0]
            logger.info(f"Detected email pattern: {self.email_pattern} for {domain}")

    # ─────────────────────────────────────────────
    # LAYER 9: Claude extraction pass
    # ─────────────────────────────────────────────

    async def _layer9_claude_extraction(self):
        self.layers_used.append("L9:claude-extract")

        if not self.raw_pages:
            logger.warning(f"No raw pages to extract from for {self.district_name}")
            return

        # Extract from all pages (deduped internally)
        contacts = extract_from_multiple(self.raw_pages, self.district_name)

        # Apply email inference to contacts that have name but no email
        if self.email_pattern and self.district_domain:
            domain = self.district_domain.replace("www.", "")
            for c in contacts:
                if not c.get("email") and c.get("first_name") and c.get("last_name"):
                    inferred = infer_email(
                        c["first_name"],
                        c["last_name"],
                        domain,
                        self.email_pattern
                    )
                    if inferred:
                        c["email"] = inferred
                        c["email_confidence"] = "INFERRED"

        self._merge_contacts(contacts)

    # ─────────────────────────────────────────────
    # LAYER 10: Dedup + confidence scoring
    # ─────────────────────────────────────────────

    async def _layer10_dedup_and_score(self):
        self.layers_used.append("L10:dedup-score")

        final = []
        seen = set()

        for c in self.all_contacts:
            fn = c.get("first_name", "").lower().strip()
            ln = c.get("last_name", "").lower().strip()
            email = c.get("email", "").lower().strip()

            # Primary dedup key: name + district
            key = f"{fn}|{ln}|{self.district_name.lower()}"

            if key in seen:
                # If duplicate has email and current doesn't, skip (keep best)
                continue

            seen.add(key)

            # Upgrade confidence if email is in known_emails
            if email and email in [e.lower() for e in self.known_emails]:
                c["email_confidence"] = "VERIFIED"

            final.append(c)

        # Sort: VERIFIED > LIKELY > INFERRED > UNKNOWN, then by last name
        confidence_order = {"VERIFIED": 0, "LIKELY": 1, "INFERRED": 2, "UNKNOWN": 3}
        final.sort(key=lambda c: (
            confidence_order.get(c.get("email_confidence", "UNKNOWN"), 3),
            c.get("last_name", "").lower()
        ))

        self.all_contacts = final

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    async def _serper_batch(self, queries: list[str]) -> list[dict]:
        """Run a batch of Serper queries. Returns list of result dicts."""
        if not SERPER_API_KEY:
            logger.error("SERPER_API_KEY not set")
            return []

        results = []
        for query in queries:
            try:
                response = requests.post(
                    SERPER_URL,
                    headers={
                        "X-API-KEY": SERPER_API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={"q": query, "num": 10},
                    timeout=10
                )
                response.raise_for_status()
                results.append(response.json())
                time.sleep(0.3)  # rate limit courtesy
            except Exception as e:
                logger.error(f"Serper query failed: '{query}' — {e}")
                results.append({})

        return results

    def _add_raw_from_serper(self, results: list[dict]):
        """Extract snippet text from Serper results and add to raw_pages."""
        for result in results:
            for item in result.get("organic", []):
                url = item.get("link", "")
                snippet = item.get("snippet", "")
                title = item.get("title", "")
                if url and snippet:
                    content = f"Title: {title}\nURL: {url}\n{snippet}"
                    self.raw_pages.append((url, content))

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch a web page and return its text content."""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(url, headers=HEADERS)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove nav/footer/script noise
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)
                return text[:15000]  # cap per page
        except Exception as e:
            logger.debug(f"Fetch failed for {url}: {e}")
            return None

    def _discover_links(self, soup: BeautifulSoup, base_url: str, crawled: set):
        """Find same-domain links in a page and add to crawled tracking."""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(base_url, href)
            if self.district_domain and self.district_domain in full:
                crawled.discard(full)  # allow recrawl discovery — we'll dedupe elsewhere

    def _looks_like_district_domain(self, url: str, district_name: str) -> bool:
        """Heuristic: does this URL look like the official district website?"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Skip common non-district domains
        skip = [
            "linkedin.com", "twitter.com", "facebook.com", "wikipedia.org",
            "niche.com", "greatschools.org", "schooldigger.com", "usnews.com",
            "indeed.com", "glassdoor.com", "youtube.com", "instagram.com",
        ]
        for s in skip:
            if s in domain:
                return False

        # Look for district/school-style TLDs or keywords
        district_signals = [".k12.", "schools", "isd", "usd", "csd", "unified", "district", "cusd"]
        for signal in district_signals:
            if signal in domain:
                return True

        # Last resort: some words from district name in domain
        words = district_name.lower().split()
        significant = [w for w in words if len(w) > 3 and w not in ("school", "district", "unified", "public", "city", "county")]
        for word in significant[:2]:
            if word in domain:
                return True

        return False

    def _merge_contacts(self, new_contacts: list[dict]):
        """Merge new contacts into all_contacts, avoiding duplicates."""
        existing_keys = set()
        for c in self.all_contacts:
            fn = c.get("first_name", "").lower()
            ln = c.get("last_name", "").lower()
            existing_keys.add(f"{fn}|{ln}")

        for c in new_contacts:
            fn = c.get("first_name", "").lower()
            ln = c.get("last_name", "").lower()
            key = f"{fn}|{ln}"
            if key not in existing_keys:
                existing_keys.add(key)
                self.all_contacts.append(c)

    async def _progress(self, message: str):
        """Fire progress callback if set."""
        if self.progress_callback:
            try:
                await self.progress_callback(message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")


# ─────────────────────────────────────────────
# JOB QUEUE MANAGER
# ─────────────────────────────────────────────

class ResearchQueue:
    """
    Single-job-at-a-time queue for research jobs.
    Prevents parallel jobs from hammering Serper API and ensures maximum depth.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._current_job: str | None = None
        self._running = False

    @property
    def is_busy(self) -> bool:
        return self._current_job is not None

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def current_job(self) -> str | None:
        return self._current_job

    async def enqueue(
        self,
        district_name: str,
        state: str,
        progress_callback,
        completion_callback
    ):
        """
        Add a job to the queue.
        completion_callback(result: dict) is called when done.
        """
        await self._queue.put({
            "district_name": district_name,
            "state": state,
            "progress_callback": progress_callback,
            "completion_callback": completion_callback,
        })

        if not self._running:
            asyncio.create_task(self._worker())

    async def _worker(self):
        """Process jobs one at a time."""
        self._running = True
        while not self._queue.empty():
            job = await self._queue.get()
            self._current_job = job["district_name"]

            try:
                engine = ResearchJob(
                    district_name=job["district_name"],
                    state=job["state"],
                    progress_callback=job["progress_callback"]
                )
                result = await engine.run()
                await job["completion_callback"](result)
            except Exception as e:
                logger.error(f"Research job failed for {job['district_name']}: {e}")
                if job["progress_callback"]:
                    await job["progress_callback"](
                        f"❌ Research job failed for {job['district_name']}: {e}"
                    )
            finally:
                self._current_job = None
                self._queue.task_done()

        self._running = False


# Singleton queue instance
research_queue = ResearchQueue()
