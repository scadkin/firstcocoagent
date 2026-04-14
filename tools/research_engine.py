# Last tool evaluation: 2026-04-08 Session 49 — see docs/tool_evaluation_2026_04.md
"""
research_engine.py — Scout's multi-tool K-12 lead research engine.

Layers:
  1. Serper: direct title search
  2. Serper: title variation sweep
  3. Serper: LinkedIn-targeted search
  4. Serper: district site deep search (also discovers domain)
  5. Serper: news + grants search (priority signals)
  6. Direct website scrape (BeautifulSoup)
  7. Keyword deep crawl across all pages found
  8. Email pattern inference (adaptive, handles name swaps)
  11. Serper: school-level staff directories
  12. Serper: board meeting / agenda mining
  13. Serper: state DOE directory lookup
  14. Serper: conference presenter search
  16. Exa: semantic search (broad)
  17. Exa: domain-scoped search (targets district site)
  18. Firecrawl: /extract with schema (structured contacts, no Claude needed)
  19. Firecrawl: site map + targeted scrape (finds actual staff pages)
  20. Brave: independent search index
  9. Claude extraction pass (with two-pass filter to skip non-contact pages)
  10. Dedup + confidence scoring (with cross-district and name↔email validation)
  15. Email verification & discovery via search (runs after L10)

Parallelization:
  Phase A (parallel): L1, L2, L3, L5, L16, L20 — independent, multi-index
  Phase B (sequential): L4 — domain discovery
  Phase C (parallel): L6, L11-L14, L17-L19 — domain-dependent
  Phase D (sequential): L7, L8 — need Phase C pages
  Phase E: L9 → L10 → L15 → L10
"""

import os
import re
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import date, datetime

from agent.keywords import (
    SERPER_PRIORITY_TITLES,
    ALL_TITLES,
    CS_KEYWORDS,
    STEM_KEYWORDS,
    TECH_KEYWORDS,
    CTE_KEYWORDS,
    TARGET_DEPARTMENTS,
    EMAIL_PATTERNS,
    STATE_ABBREVIATIONS,
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
SERPER_REQUESTS_PER_JOB = int(os.environ.get("SERPER_REQUESTS_PER_JOB", "100"))  # safety cap; ~57 used in normal 15-layer run (L15 adds up to 30)

# BUG 5 cross-district contamination filter kill switch. Set to False to disable
# both the page-level and contact-level filters and fall back to L10's built-in
# cross-district email check only. See Session 55 plan + feedback_kill_switches.
ENABLE_RESEARCH_CONTAM_FILTER = True

# BUG 4 Session 56 — diocesan central-office research playbook.
# When True, districts whose canonicalized names hit DIOCESAN_DOMAIN_MAP
# (from tools.private_schools) activate a preprocessing path that pre-seeds
# the domain, swaps L1/L2/L3/L4-site/L11 queries to diocesan terminology,
# skips L12 (diocesan networks have no public school board), and forces the
# BUG 5 filter into strict base-domain-only mode so shared-city hints like
# "chicago" can't match cps.edu alongside archchicago.org. Set False to
# fall back to the default 20-layer flow.
ENABLE_DIOCESAN_PLAYBOOK = True

DIOCESAN_PRIORITY_TITLES = [
    "Superintendent of Schools",
    "Director of Catholic Schools",
    "Associate Superintendent",
    "Assistant Superintendent of Schools",
    "Director of Curriculum and Instruction",
    "Director of Elementary Education",
    "Director of Secondary Education",
    "Director of Educational Technology",
]

DIOCESAN_L2_QUERIES_TEMPLATE = [
    '"{district}" "superintendent of schools" email',
    '"{district}" "director of catholic schools" contact',
    '"{district}" "office of catholic schools" staff',
    '"{district}" "meet our team" OR "our staff"',
    '"{district}" director curriculum instruction',
]

DIOCESAN_L3_QUERIES_TEMPLATE = [
    'site:linkedin.com "{district}" "superintendent of schools"',
    'site:linkedin.com "{district}" "director of catholic schools"',
    'site:linkedin.com "{district}" "office of catholic schools"',
]

DIOCESAN_L4_SITE_QUERIES_TEMPLATE = [
    'site:{domain} "superintendent of schools" OR "director of schools"',
    'site:{domain} "office of catholic schools" staff OR leadership',
    'site:{domain} "meet our team" OR "our staff" OR directory',
]

DIOCESAN_L11_QUERIES_TEMPLATE = [
    'site:{domain} "meet our team" OR "office of catholic schools"',
    'site:{domain} staff OR leadership OR directory',
]

# Shared school-host pattern set for cross-district detection. Affirmative test:
# if a hostname contains any of these, treat it as a school-owned domain.
# Everything else is "generic" (news/DOE/LinkedIn/conference) and gets benefit
# of the doubt. Same set is reused by the page filter, contact filter, L10
# strengthening, and the audit script.
_SCHOOL_HOST_PATTERNS = (
    ".k12.", ".edu", "isd", "usd", "schools", ".ps.",
    "cusd", "cps", "chsd", "ccsd", "ccusd", "cisd", "dusd", "dvusd",
    "mcsd", "ecsd", "ocsd",
    "archdiocese", "diocese", "academy", "charter",
)
_GENERIC_EMAIL_ROOTS = frozenset({"gmail", "yahoo", "hotmail", "outlook", "icloud"})


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

class ResearchJob:
    """
    Runs all 10 research layers for a given district.
    Call run() to execute. Progress callback fires at key milestones.
    """

    def __init__(
        self,
        district_name: str,
        state: str,
        progress_callback=None,
        serper_cap_override: int = None,
        diocesan_domain: str = "",
        diocesan_playbook: bool = False,
        # Round 1 feature flags — default OFF preserves v1 behavior byte-for-byte.
        enable_url_dedup: bool = False,
        l15_step5_skip_threshold: int | None = None,
        log_claude_usage: bool = False,
    ):
        self.district_name = district_name
        self.state = state
        self.progress_callback = progress_callback  # async func(message: str)

        # Round 1 feature flags
        self.enable_url_dedup = enable_url_dedup
        self.l15_step5_skip_threshold = l15_step5_skip_threshold
        self.log_claude_usage = log_claude_usage

        self.raw_pages: list[tuple[str, str]] = []  # (url, content)
        self.all_contacts: list[dict] = []
        self.seen_keys: set[str] = set()
        self.layers_used: list[str] = []
        self.district_domain: str = ""
        self.known_emails: list[str] = []
        self.email_pattern: str = ""

        # Serper safety cap
        self._serper_cap = serper_cap_override if serper_cap_override is not None else SERPER_REQUESTS_PER_JOB
        self._serper_count = 0
        self._cap_hit = False
        self._skipped_layers: list[str] = []

        # Layer effectiveness tracking
        self._url_to_layer: dict[str, str] = {}  # url → layer tag
        self._start_time: datetime = datetime.now()

        # BUG 5 cross-district contamination counters (Session 55)
        self._contam_pages_filtered: int = 0
        self._contam_contacts_filtered: int = 0
        self._contam_l10_cleared: int = 0

        # BUG 4 Session 56 — diocesan central-office playbook. Pre-seeds the
        # domain (bypassing L4 discovery), swaps L1/L2/L3/L4-site/L11 queries
        # to diocesan terminology, skips L12, and forces strict base-domain
        # matching in the cross-district filter. Kill switch gated.
        self._diocesan_playbook = bool(diocesan_playbook) and ENABLE_DIOCESAN_PLAYBOOK
        self._diocesan_filter_base: str = ""
        if self._diocesan_playbook and diocesan_domain:
            self.district_domain = diocesan_domain
            self._diocesan_filter_base = self._base_domain(diocesan_domain)
            logger.info(
                f"[DIOCESAN] playbook active for {district_name!r} "
                f"domain={diocesan_domain} filter_base={self._diocesan_filter_base}"
            )

    # ─────────────────────────────────────────────
    # BUG 5 shared matching helpers (Session 55)
    # Single source of truth for cross-district filtering. Used by the stage-1
    # page filter (_filter_raw_pages_by_domain), stage-2 contact filter
    # (_filter_contacts_by_domain), strengthened L10, and the audit script.
    # ─────────────────────────────────────────────

    @staticmethod
    def _district_name_hint(name: str) -> str:
        """Derive a short distinctive token from a district name for substring
        matching against hostnames/email domains. Returns "" if the hint is
        too short (<5 chars) to be distinctive.

        Examples:
          "Austin ISD"                      → "austin"
          "Pittsburgh Public Schools"       → "pittsburgh"
          "Archdiocese of Chicago Schools"  → "chicago"
          "Park Ridge"                      → "" (too short after normalization)
        """
        if not name:
            return ""
        h = name.lower().strip()
        for suf in (
            " isd", " unified school district", " school district",
            " public schools", " city schools", " county superintendent of schools",
            " county schools", " catholic schools", " academy", " schools",
        ):
            if h.endswith(suf):
                h = h[: -len(suf)]
                break
        for pre in ("archdiocese of ", "diocese of "):
            if h.startswith(pre):
                h = h[len(pre):]
                break
        h = "".join(h.split())  # collapse whitespace
        return h if len(h) >= 5 else ""

    @staticmethod
    def _is_school_host(host: str) -> bool:
        """Affirmative test: is this hostname a school-owned domain?
        Everything else is "generic" (DOE, news, LinkedIn, conference, PDF)
        and gets benefit of the doubt (kept, not dropped).
        """
        if not host:
            return False
        h = host.lower()
        return any(p in h for p in _SCHOOL_HOST_PATTERNS)

    @staticmethod
    def _host_matches_target(host: str, target_host: str, target_hint: str) -> bool:
        """True if `host` belongs to the research target.

        Rule: exact target_host substring match OR target_hint substring match
        (when hint is ≥5 chars). Matches subdomains implicitly.
        """
        if not host:
            return False
        h = host.lower().replace("www.", "")
        if target_host:
            t = target_host.lower().replace("www.", "")
            if t and t in h:
                return True
        if target_hint and len(target_hint) >= 5 and target_hint in h:
            return True
        return False

    @staticmethod
    def _email_domain_matches_target(email: str, target_host: str, target_hint: str) -> bool:
        """Same substring test, applied to the domain of an email address."""
        if not email or "@" not in email:
            return False
        domain = email.rsplit("@", 1)[1].lower()
        return ResearchJob._host_matches_target(domain, target_host, target_hint)

    @staticmethod
    def _base_domain(host: str) -> str:
        """Return the 2-part base domain for .org/.com hosts.

        BUG 4 diocesan playbook assumption: all 16 diocesan domains use
        simple TLDs (.org / .com), so naive last-2-parts is correct. Does
        NOT handle compound TLDs like .co.uk or .k12.il.us — the diocesan
        seed is validated to contain no such domains.

        Examples:
          schools.archchicago.org → archchicago.org
          archchicago.org         → archchicago.org
          www.diopitt.org         → diopitt.org
          parish.archomaha.org    → archomaha.org
        """
        if not host:
            return ""
        h = host.lower().replace("www.", "")
        parts = h.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else h

    def _target_match_params(self) -> tuple[str, str]:
        """Return (target_host, target_hint) for BUG 5 cross-district filtering.

        Single source of truth — used by Stage 1 page filter, Stage 2 contact
        filter, and both L10 strengthening checks. Diocesan playbook runs
        force strict base-domain-only matching (empty hint) so a 'chicago'
        hint derived from 'Archdiocese of Chicago Schools' can't match both
        archchicago.org AND cps.edu (Chicago Public Schools). Non-playbook
        callers get the exact same values as the previous inline logic.
        """
        if self._diocesan_playbook and self._diocesan_filter_base:
            return (self._diocesan_filter_base, "")
        target_host = self.district_domain.lower().replace("www.", "") if self.district_domain else ""
        return (target_host, self._district_name_hint(self.district_name))

    async def run(self) -> dict:
        """
        Execute all layers with parallelization where possible.

        Dependency graph:
          Phase A (parallel): L1, L2, L3, L5, L16 — no dependencies
          Phase B (sequential): L4 — discovers district_domain (needed by later layers)
          Phase C (parallel, needs domain): L6, L11, L12, L13, L14, L17, L18, L19
          Phase D (sequential): L7, L8 — need L6 pages
          Phase E: L9 (Claude extraction on all pages)
        """
        # Round 1 Flag C: start module-level Claude usage capture. The
        # try/except below guarantees the capture flag never leaks even on
        # exception paths so the next job starts clean.
        if self.log_claude_usage:
            from tools.contact_extractor import start_usage_capture, stop_usage_capture
            start_usage_capture()
            try:
                result = await self._run_phases()
            except Exception:
                stop_usage_capture()  # discard records, clean the flag
                raise
            result["claude_usage"] = stop_usage_capture()
            return result
        return await self._run_phases()

    async def _run_phases(self) -> dict:
        # ── Phase A: Independent searches (run in parallel across 3 indices) ──
        await self._progress(f"🔎 Searching across Serper + Exa + Brave...")
        await asyncio.gather(
            self._layer1_direct_title_search(),
            self._layer2_title_variation_sweep(),
            self._layer3_linkedin_search(),
            self._layer5_news_grants_search(),
            self._layer16_exa_broad_search(),
            self._layer20_brave_search(),
        )

        # ── Phase B: Domain discovery (must complete before domain-dependent layers) ──
        await self._layer4_district_site_search()

        # ── Phase C: Domain-dependent searches + scraping (run in parallel) ──
        await self._progress(f"🔎 Deep search: district site + expanded layers...")
        await asyncio.gather(
            self._layer6_direct_scrape(),
            self._layer11_school_staff_search(),
            self._layer12_board_agenda_search(),
            self._layer13_state_doe_search(),
            self._layer14_conference_presenter_search(),
            self._layer17_exa_domain_search(),
            self._layer18_firecrawl_extract(),
            self._layer19_firecrawl_site_map(),
        )

        # ── Phase D: Sequential layers that depend on Phase C pages ──
        await self._layer7_keyword_crawl()
        await self._layer8_email_inference()

        # ── Phase E: Claude extraction (all raw pages, with two-pass filter) ──
        await self._layer9_claude_extraction()

        # Layer 10: Dedup + confidence scoring
        await self._layer10_dedup_and_score()

        # Layer 15: Email verification & discovery (operates on cleaned L10 list)
        await self._layer15_email_verification()

        # Re-run dedup + scoring to incorporate any new contacts from L15
        await self._layer10_dedup_and_score()

        layers_str = ", ".join(self.layers_used)
        total = len(self.all_contacts)
        with_email = sum(1 for c in self.all_contacts if c.get("email"))
        no_email = total - with_email
        verified = sum(1 for c in self.all_contacts if c.get("email_confidence") == "VERIFIED")
        elapsed_seconds = int((datetime.now() - self._start_time).total_seconds())

        # Count contacts per layer using source_url → layer mapping
        layer_contact_counts: dict[str, int] = {}
        for c in self.all_contacts:
            src = c.get("source_url", "")
            layer = self._url_to_layer.get(src, "unknown")
            layer_contact_counts[layer] = layer_contact_counts.get(layer, 0) + 1

        return {
            "district_name": self.district_name,
            "state": self.state,
            "contacts": self.all_contacts,
            "total": total,
            "with_email": with_email,
            "no_email": no_email,
            "verified": verified,
            "layers_used": layers_str,
            "cap_hit": self._cap_hit,
            "queries_used": self._serper_count,
            "skipped_layers": self._skipped_layers,
            "elapsed_seconds": elapsed_seconds,
            "layer_contact_counts": layer_contact_counts,
            # BUG 5 cross-district contamination stats
            "pages_filtered": self._contam_pages_filtered,
            "contacts_filtered": self._contam_contacts_filtered,
            "l10_cleared": self._contam_l10_cleared,
            "cross_contam_dropped": self._contam_pages_filtered + self._contam_contacts_filtered,
        }

    # ─────────────────────────────────────────────
    # LAYER 1: Direct Serper title search
    # ─────────────────────────────────────────────

    async def _layer1_direct_title_search(self):
        self.layers_used.append("L1:direct-title")
        titles = DIOCESAN_PRIORITY_TITLES if self._diocesan_playbook else SERPER_PRIORITY_TITLES
        queries = [
            f'"{title}" "{self.district_name}" email'
            for title in titles[:8]
        ]
        results = await self._serper_batch(queries[:5])
        self._add_raw_from_serper(results, "L1:direct-title")

    # ─────────────────────────────────────────────
    # LAYER 2: Title variation sweep
    # ─────────────────────────────────────────────

    async def _layer2_title_variation_sweep(self):
        self.layers_used.append("L2:title-variations")
        # Use different title phrasings — different results than Layer 1
        if self._diocesan_playbook:
            varied = [
                q.format(district=self.district_name)
                for q in DIOCESAN_L2_QUERIES_TEMPLATE
            ]
        else:
            varied = [
                f'"{self.district_name}" "computer science" coordinator contact',
                f'"{self.district_name}" STEM director',
                f'"{self.district_name}" CTE director email',
                f'"{self.district_name}" instructional technology coordinator',
                f'"{self.district_name}" curriculum director',
            ]
        results = await self._serper_batch(varied)
        self._add_raw_from_serper(results, "L2:title-variations")

    # ─────────────────────────────────────────────
    # LAYER 3: LinkedIn targeted
    # ─────────────────────────────────────────────

    async def _layer3_linkedin_search(self):
        self.layers_used.append("L3:linkedin")
        if self._diocesan_playbook:
            queries = [
                q.format(district=self.district_name)
                for q in DIOCESAN_L3_QUERIES_TEMPLATE
            ]
        else:
            queries = [
                f'site:linkedin.com "computer science" "{self.district_name}"',
                f'site:linkedin.com "STEM" "{self.district_name}" director',
                f'site:linkedin.com "instructional technology" "{self.district_name}"',
            ]
        results = await self._serper_batch(queries[:3])
        self._add_raw_from_serper(results, "L3:linkedin")

    # ─────────────────────────────────────────────
    # LAYER 4: District site deep search
    # ─────────────────────────────────────────────

    async def _layer4_district_site_search(self):
        self.layers_used.append("L4:district-site")

        if self._diocesan_playbook and self.district_domain:
            # Diocesan playbook pre-seeded the domain at __init__ — skip the
            # Serper "official website" discovery query entirely.
            logger.info(
                f"L4 pre-seeded diocesan domain {self.district_domain}, skipping discovery"
            )
        else:
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
            if self._diocesan_playbook:
                site_queries = [
                    q.format(domain=self.district_domain)
                    for q in DIOCESAN_L4_SITE_QUERIES_TEMPLATE
                ]
            else:
                site_queries = [
                    f'site:{self.district_domain} "computer science" OR "coding" OR "STEM"',
                    f'site:{self.district_domain} staff directory',
                    f'site:{self.district_domain} department contact',
                ]
            results = await self._serper_batch(site_queries[:3])
            self._add_raw_from_serper(results, "L4:district-site")

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
        self._add_raw_from_serper(results, "L5:news-grants")

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
                self._url_to_layer.setdefault(url, "L6:scrape")
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
                self._url_to_layer.setdefault(url, "L7:deep-crawl")
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

    def _filter_raw_pages_by_domain(self):
        """BUG 5 Stage 1: drop pages whose host is clearly a DIFFERENT school
        from the research target. Runs before Claude extraction so contaminated
        pages never cost tokens.

        Decision (per page):
          - host matches target_host or target_hint → keep
          - host is school-like AND doesn't match → DROP
          - otherwise (generic host — DOE, news, LinkedIn, PDF) → keep

        Fail-open: if self.district_domain is empty (L4 didn't discover one)
        or the kill switch is off, the filter no-ops and returns.
        """
        if not ENABLE_RESEARCH_CONTAM_FILTER:
            return
        if not self.district_domain:
            logger.info("L9 page filter skipped: no district_domain from L4")
            return

        target_host, target_hint = self._target_match_params()

        before = len(self.raw_pages)
        kept: list[tuple[str, str]] = []
        dropped_urls: list[str] = []
        for url, content in self.raw_pages:
            host = urlparse(url).netloc.lower().replace("www.", "")
            if self._host_matches_target(host, target_host, target_hint):
                kept.append((url, content))
            elif self._is_school_host(host):
                dropped_urls.append(url)
            else:
                kept.append((url, content))

        self.raw_pages = kept
        # Prune layer tracking for dropped URLs so return dict stats stay honest
        for url in dropped_urls:
            self._url_to_layer.pop(url, None)

        dropped = len(dropped_urls)
        self._contam_pages_filtered = dropped
        if dropped:
            logger.info(
                f"L9 page filter: {dropped}/{before} pages dropped as cross-district "
                f"(target={target_host})"
            )

    async def _layer9_claude_extraction(self):
        self.layers_used.append("L9:claude-extract")

        if not self.raw_pages:
            logger.warning(f"No raw pages to extract from for {self.district_name}")
            return

        # Round 1 Flag A: URL dedup with longest-content-wins.
        # Serper snippets get appended per-query with different snippet text
        # for the same URL, and direct-scrape / Firecrawl / Exa layers append
        # the same URL with full-page HTML. Naive first-occurrence dedup keeps
        # the short snippet and throws away the full page — a quality loss.
        # "Keep the longest content per normalized URL" preserves the richest
        # page while still killing the duplicate-extraction cost.
        # Normalization: lowercase + strip trailing slash. Off by default.
        if self.enable_url_dedup:
            by_url: dict[str, tuple[str, str]] = {}
            order: list[str] = []
            for url, content in self.raw_pages:
                normalized = (url or "").rstrip("/").lower()
                if not normalized:
                    continue
                existing = by_url.get(normalized)
                if existing is None:
                    by_url[normalized] = (url, content)
                    order.append(normalized)
                elif len(content or "") > len(existing[1] or ""):
                    by_url[normalized] = (url, content)
            before = len(self.raw_pages)
            self.raw_pages = [by_url[k] for k in order]
            if before > len(self.raw_pages):
                logger.info(
                    f"L9 URL dedup: {before - len(self.raw_pages)} duplicate URLs "
                    f"collapsed (longest content wins; {before} -> {len(self.raw_pages)})"
                )

        # BUG 5 Stage 1: page-host filter runs BEFORE the two-pass content
        # filter below. Contaminated pages (wrong-school hosts) never reach
        # Claude extraction.
        self._filter_raw_pages_by_domain()

        if not self.raw_pages:
            logger.warning(
                f"No pages survived cross-district page filter for {self.district_name}"
            )
            return

        # Two-pass filter: skip pages unlikely to contain contacts
        # Saves ~50% on Claude API costs
        filtered_pages = []
        skipped = 0
        for url, content in self.raw_pages:
            if not content or len(content.strip()) < 100:
                skipped += 1
                continue
            content_lower = content[:12000].lower()
            contact_signals = sum([
                "@" in content[:12000],
                any(t in content_lower for t in ["director", "coordinator", "teacher",
                    "principal", "specialist", "superintendent", "staff"]),
                any(p in content_lower for p in ["phone", "email", "ext.", "extension"]),
                any(d in content_lower for d in ["department", "directory", "faculty",
                    "our team", "contact us", "administration"]),
            ])
            if contact_signals >= 2:
                filtered_pages.append((url, content))
            else:
                skipped += 1

        if skipped:
            logger.info(f"L9 two-pass filter: {len(filtered_pages)}/{len(self.raw_pages)} pages "
                        f"have contact signals ({skipped} skipped)")

        await self._progress(f"🤖 Extracting contacts from {len(filtered_pages)} pages...")

        # Run synchronous Claude extraction in a thread pool so it doesn't block the event loop.
        # extract_from_multiple makes one blocking Claude API call per page — without run_in_executor
        # it freezes asyncio entirely, preventing heartbeats and Telegram messages from processing.
        loop = asyncio.get_event_loop()
        contacts = await loop.run_in_executor(
            None, extract_from_multiple, filtered_pages, self.district_name
        )

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

        # BUG 5 Stage 2: contact-level cross-district filter. Catches the
        # long tail of contamination that Stage 1 can't — pages from generic
        # hosts (state DOE, conference sites, PDFs) that mention the target
        # alongside other districts.
        self._filter_contacts_by_domain()

    def _filter_contacts_by_domain(self):
        """BUG 5 Stage 2: filter self.all_contacts by cross-district match.

        Runs after L9 has extracted + merged contacts. Unlike Stage 1 which
        runs on (url, content) tuples, this operates on the structured contact
        dicts from Claude extraction. Catches contamination that slipped
        through Stage 1 because the source host was generic (DOE, news, etc).

        Decision rule (per contact):
          - source_url host AND email domain both match target → keep
          - source matches target but email is from a clearly different
            school → keep the contact at UNKNOWN confidence, clear the email
            (preserve the name as a lead)
          - source matches target only (email missing/generic) → keep
          - email matches target only (source generic) → keep
          - source is a wrong-school host → drop
          - generic source + email is a wrong-school domain → drop
          - otherwise (generic source + generic/missing email) → keep at UNKNOWN

        Fail-open when district_domain is empty or kill switch is off.
        """
        if not ENABLE_RESEARCH_CONTAM_FILTER:
            return
        if not self.district_domain:
            return
        if not self.all_contacts:
            return

        target_host, target_hint = self._target_match_params()

        before = len(self.all_contacts)
        kept: list[dict] = []
        dropped = 0
        email_cleared = 0

        for c in self.all_contacts:
            source_url = c.get("source_url", "")
            email = c.get("email", "")
            host = urlparse(source_url).netloc.lower().replace("www.", "")
            email_domain = email.rsplit("@", 1)[1].lower() if "@" in email else ""

            source_matches = self._host_matches_target(host, target_host, target_hint)
            email_matches = self._email_domain_matches_target(email, target_host, target_hint)

            if source_matches and email_matches:
                kept.append(c)
                continue
            if source_matches:
                # Source page is legit target, but email may or may not match
                if email and not email_matches and self._is_school_host(email_domain):
                    # Legit-target page embedded someone else's contact info
                    logger.debug(
                        f"L9.5 source-match, email cleared: {c.get('first_name')} "
                        f"{c.get('last_name')} email={email} host={host}"
                    )
                    c["email"] = ""
                    c["email_confidence"] = "UNKNOWN"
                    email_cleared += 1
                kept.append(c)
                continue
            if email_matches:
                # Generic source, email is the authority
                kept.append(c)
                continue
            if self._is_school_host(host):
                # Wrong-school host that Stage 1 missed (shouldn't happen
                # often since Stage 1 already ran, but defense in depth)
                logger.debug(
                    f"L9.5 dropped wrong-school host: {c.get('first_name')} "
                    f"{c.get('last_name')} host={host} email={email}"
                )
                dropped += 1
                continue
            # Generic host
            if email and email_domain and self._is_school_host(email_domain) and not email_matches:
                logger.debug(
                    f"L9.5 dropped generic-host + wrong-email-school: "
                    f"{c.get('first_name')} {c.get('last_name')} email={email} host={host}"
                )
                dropped += 1
                continue
            # Can't judge — keep at UNKNOWN confidence (no change if already set)
            c["email_confidence"] = c.get("email_confidence") or "UNKNOWN"
            kept.append(c)

        self.all_contacts = kept
        self._contam_contacts_filtered += dropped
        if dropped or email_cleared:
            logger.info(
                f"L9 contact filter: {dropped}/{before} contacts dropped as cross-district, "
                f"{email_cleared} emails cleared (target={target_host})"
            )

    # ─────────────────────────────────────────────
    # LAYER 10: Dedup + confidence scoring
    # ─────────────────────────────────────────────

    async def _layer10_dedup_and_score(self):
        self.layers_used.append("L10:dedup-score")

        domain = self.district_domain.replace("www.", "") if self.district_domain else ""
        # Derive district hint for cross-district validation
        district_hint = self.district_name.lower()
        for suffix in [" isd", " unified school district", " school district",
                       " public schools", " city schools",
                       " county superintendent of schools", " county schools"]:
            if district_hint.endswith(suffix):
                district_hint = district_hint[:-len(suffix)]
                break
        district_hint = district_hint.replace(" ", "")

        final = []
        seen = set()
        rejected = {"cross_district": 0, "name_mismatch": 0}

        for c in self.all_contacts:
            fn = c.get("first_name", "").lower().strip()
            ln = c.get("last_name", "").lower().strip()
            email = c.get("email", "").lower().strip()

            # Primary dedup key: name + district
            key = f"{fn}|{ln}|{self.district_name.lower()}"

            if key in seen:
                continue
            seen.add(key)

            # Cross-district email validation.
            # BUG 5 Session 55: rewritten to use the shared helpers so the
            # whole hostname is inspected (not just parts[0]). The old
            # implementation missed emails like "@centralislip.k12.ny.us"
            # because parts[0] = "centralislip" contains no district pattern.
            if email and "@" in email and domain and ENABLE_RESEARCH_CONTAM_FILTER:
                email_domain = email.rsplit("@", 1)[1]
                target_host_l10, target_hint_l10 = self._target_match_params()
                if (
                    email_domain
                    and self._is_school_host(email_domain)
                    and not self._email_domain_matches_target(
                        email, target_host_l10, target_hint_l10
                    )
                ):
                    logger.debug(f"L10: Cross-district email dropped: {fn} {ln} → {email}")
                    c["email"] = ""
                    c["email_confidence"] = "UNKNOWN"
                    rejected["cross_district"] += 1

            # BUG 5: L10 source_url strengthening. Catches L15-added contacts
            # that bypass both filter stages. Degrades confidence to UNKNOWN;
            # does NOT drop (L10 runs twice and dropping would double-count).
            if ENABLE_RESEARCH_CONTAM_FILTER and self.district_domain:
                source_url = c.get("source_url", "")
                source_host = urlparse(source_url).netloc.lower().replace("www.", "")
                target_host_l10, target_hint_l10 = self._target_match_params()
                if (
                    source_host
                    and self._is_school_host(source_host)
                    and not self._host_matches_target(source_host, target_host_l10, target_hint_l10)
                ):
                    if c.get("email_confidence") != "UNKNOWN":
                        logger.debug(
                            f"L10: source_url cross-district: {fn} {ln} host={source_host}"
                        )
                        c["email_confidence"] = "UNKNOWN"
                        self._contam_l10_cleared += 1

            # Name↔email alignment check
            if email and "@" in email:
                local = email.split("@")[0].lower()
                if fn and ln and len(fn) > 1 and len(ln) > 1 and local:
                    fn_in = fn in local
                    ln_in = ln in local
                    fi_ln = fn[0] + ln in local
                    ln_starts = local.startswith(ln[:3]) if len(ln) >= 3 else False
                    if not (fn_in or ln_in or fi_ln or ln_starts):
                        logger.debug(f"L10: Name↔email mismatch: {fn} {ln} → {email}")
                        c["email"] = ""
                        c["email_confidence"] = "UNKNOWN"
                        rejected["name_mismatch"] += 1

            # Upgrade confidence if email is in known_emails
            if email and email in [e.lower() for e in self.known_emails]:
                c["email_confidence"] = "VERIFIED"

            final.append(c)

        if any(v > 0 for v in rejected.values()):
            logger.info(f"L10 validation: {rejected['cross_district']} cross-district, "
                         f"{rejected['name_mismatch']} name-mismatch emails cleared")

        # Sort: VERIFIED > LIKELY > INFERRED > UNKNOWN, then by last name
        confidence_order = {"VERIFIED": 0, "LIKELY": 1, "INFERRED": 2, "UNKNOWN": 3}
        final.sort(key=lambda c: (
            confidence_order.get(c.get("email_confidence", "UNKNOWN"), 3),
            c.get("last_name", "").lower()
        ))

        self.all_contacts = final

    # ─────────────────────────────────────────────
    # LAYER 11: School-level staff directories
    # ─────────────────────────────────────────────

    async def _layer11_school_staff_search(self):
        self.layers_used.append("L11:school-staff")
        if not self.district_domain:
            self._skipped_layers.append("L11:school-staff (no domain)")
            return
        if self._diocesan_playbook:
            queries = [
                q.format(domain=self.district_domain)
                for q in DIOCESAN_L11_QUERIES_TEMPLATE
            ]
        else:
            queries = [
                f'site:{self.district_domain} "staff directory" OR "staff" OR "faculty"',
                f'site:{self.district_domain} "computer science" OR "coding" teacher',
            ]
        results = await self._serper_batch(queries)
        self._add_raw_from_serper(results, "L11:school-staff")

    # ─────────────────────────────────────────────
    # LAYER 12: Board meeting / agenda mining
    # ─────────────────────────────────────────────

    async def _layer12_board_agenda_search(self):
        # BUG 4 Session 56 — diocesan networks don't have public K-12 school
        # boards. Running L12 against them returns noise (parish council
        # agendas, USCCB filings) that contaminates raw_pages. Skip entirely.
        if self._diocesan_playbook:
            self._skipped_layers.append("L12:board-agendas (diocesan — no public board)")
            return
        self.layers_used.append("L12:board-agendas")
        queries = [
            f'site:{self.district_domain} "board meeting" "computer science" OR "STEM"' if self.district_domain else f'"{self.district_name}" site:.gov "board meeting" "computer science" OR "STEM"',
            f'"{self.district_name}" "board agenda" "computer science" OR "coding"',
        ]
        results = await self._serper_batch(queries)
        self._add_raw_from_serper(results, "L12:board-agendas")

    # ─────────────────────────────────────────────
    # LAYER 13: State DOE directory lookup
    # ─────────────────────────────────────────────

    async def _layer13_state_doe_search(self):
        if not self.state:
            self._skipped_layers.append("L13:state-doe (no state provided)")
            return
        self.layers_used.append("L13:state-doe")
        # Look up 2-letter abbreviation; fall back to first 2 chars of state name
        state_abbrev = STATE_ABBREVIATIONS.get(self.state, self.state[:2]).lower()
        queries = [
            f'site:*.{state_abbrev}.us "computer science" coordinator OR director',
            f'"{self.state}" department of education "computer science"',
        ]
        results = await self._serper_batch(queries)
        self._add_raw_from_serper(results, "L13:state-doe")

    # ─────────────────────────────────────────────
    # LAYER 14: Conference presenter search
    # ─────────────────────────────────────────────

    async def _layer14_conference_presenter_search(self):
        self.layers_used.append("L14:conference")
        year = date.today().year
        queries = [
            f'"{self.district_name}" "CSTA" OR "ISTE" OR "CSforAll" presenter OR speaker',
            f'"{self.district_name}" "computer science" conference presenter {year}',
        ]
        results = await self._serper_batch(queries)
        self._add_raw_from_serper(results, "L14:conference")

    # ─────────────────────────────────────────────
    # LAYER 16: Exa semantic search (broad)
    # ─────────────────────────────────────────────

    async def _layer16_exa_broad_search(self):
        """Exa's neural search index finds pages Google often misses —
        conference mentions, org directories, news articles with contacts."""
        try:
            from exa_py import Exa
        except ImportError:
            self._skipped_layers.append("L16:exa-broad (exa-py not installed)")
            return

        exa_key = os.environ.get("EXA_API_KEY", "")
        if not exa_key:
            self._skipped_layers.append("L16:exa-broad (EXA_API_KEY not set)")
            return

        self.layers_used.append("L16:exa-broad")
        exa = Exa(api_key=exa_key)

        queries = [
            f"{self.district_name} {self.state} computer science STEM staff directory",
            f"{self.district_name} CTE curriculum technology coordinator contact email",
        ]

        for query in queries:
            try:
                results = exa.search_and_contents(
                    query=query, type="auto", num_results=10, text=True,
                )
                for r in results.results:
                    if r.url and r.text:
                        content = r.text[:15000]
                        self.raw_pages.append((r.url, content))
                        self._url_to_layer.setdefault(r.url, "L16:exa-broad")
            except Exception as e:
                logger.debug(f"Exa broad search failed: {e}")

    # ─────────────────────────────────────────────
    # LAYER 17: Exa domain-scoped search
    # ─────────────────────────────────────────────

    async def _layer17_exa_domain_search(self):
        """Search within the district's own site using Exa's index.
        Finds staff directory pages that generic search misses."""
        if not self.district_domain:
            self._skipped_layers.append("L17:exa-domain (no domain)")
            return

        try:
            from exa_py import Exa
        except ImportError:
            return

        exa_key = os.environ.get("EXA_API_KEY", "")
        if not exa_key:
            return

        self.layers_used.append("L17:exa-domain")
        exa = Exa(api_key=exa_key)
        domain = self.district_domain.replace("www.", "")

        queries = [
            "staff directory faculty contact email",
            "computer science technology CTE department",
        ]

        for query in queries:
            try:
                results = exa.search_and_contents(
                    query=query, type="auto", num_results=10, text=True,
                    include_domains=[domain],
                )
                for r in results.results:
                    if r.url and r.text:
                        content = r.text[:15000]
                        self.raw_pages.append((r.url, content))
                        self._url_to_layer.setdefault(r.url, "L17:exa-domain")
            except Exception as e:
                logger.debug(f"Exa domain search failed for {domain}: {e}")

    # ─────────────────────────────────────────────
    # LAYER 18: Firecrawl extract with schema
    # ─────────────────────────────────────────────

    async def _layer18_firecrawl_extract(self):
        """Use Firecrawl's /extract to pull structured contacts directly from
        the district site. This bypasses Claude entirely — Firecrawl's own AI
        navigates the site and extracts data based on the schema."""
        if not self.district_domain:
            self._skipped_layers.append("L18:fc-extract (no domain)")
            return

        try:
            from firecrawl import FirecrawlApp
        except ImportError:
            self._skipped_layers.append("L18:fc-extract (firecrawl not installed)")
            return

        fc_key = os.environ.get("FIRECRAWL_API_KEY", "")
        if not fc_key:
            self._skipped_layers.append("L18:fc-extract (FIRECRAWL_API_KEY not set)")
            return

        self.layers_used.append("L18:fc-extract")
        domain = self.district_domain.replace("www.", "")

        try:
            fc = FirecrawlApp(api_key=fc_key)
            loop = asyncio.get_event_loop()

            # Run synchronous Firecrawl call in executor
            def _do_extract():
                return fc.extract(
                    urls=[f"https://{domain}/*"],
                    prompt=(
                        f"Find all staff members at {self.district_name} whose role relates to: "
                        "Computer Science, STEM, CTE, Career & Technical Education, "
                        "Educational Technology, Curriculum, Technology, Innovation, "
                        "Digital Learning, Robotics, or school leadership. "
                        "Extract their full names, job titles, email addresses, and phone numbers."
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
                                    }
                                }
                            }
                        }
                    },
                    enable_web_search=True,
                    timeout=120,
                )

            result = await loop.run_in_executor(None, _do_extract)

            # Parse and merge contacts
            data = result.data if hasattr(result, 'data') else (result if isinstance(result, dict) else None)
            if data and isinstance(data, dict):
                today = date.today().isoformat()
                for c in data.get("contacts", []):
                    fn = str(c.get("first_name", "")).strip()
                    ln = str(c.get("last_name", "")).strip()
                    email = str(c.get("email", "")).strip()
                    if not fn and not ln:
                        continue
                    # Skip masked emails
                    if email and "***" in email:
                        email = ""
                    contact = {
                        "first_name": fn,
                        "last_name": ln,
                        "title": str(c.get("title", "")).strip(),
                        "email": email.lower() if email else "",
                        "work_phone": str(c.get("phone", "")).strip(),
                        "account": self.district_name,
                        "district_name": self.district_name,
                        "source_url": f"https://{domain}",
                        "email_confidence": "VERIFIED" if email and "***" not in email else "UNKNOWN",
                        "notes": "Firecrawl extract",
                        "date_found": today,
                    }
                    self._merge_contacts([contact])
                    self._url_to_layer.setdefault(f"https://{domain}", "L18:fc-extract")

                fc_contacts = len(data.get("contacts", []))
                fc_emails = sum(1 for c in data.get("contacts", []) if c.get("email") and "***" not in c.get("email", ""))
                logger.info(f"L18 Firecrawl extract: {fc_contacts} contacts, {fc_emails} with email")

        except Exception as e:
            logger.warning(f"L18 Firecrawl extract failed: {e}")

    # ─────────────────────────────────────────────
    # LAYER 19: Firecrawl site map + targeted scrape
    # ─────────────────────────────────────────────

    async def _layer19_firecrawl_site_map(self):
        """Map the district's site to find staff/contact pages, then scrape them.
        Much more effective than guessing URLs (L6) because it discovers the actual
        site structure."""
        if not self.district_domain:
            self._skipped_layers.append("L19:fc-sitemap (no domain)")
            return

        try:
            from firecrawl import FirecrawlApp
        except ImportError:
            return

        fc_key = os.environ.get("FIRECRAWL_API_KEY", "")
        if not fc_key:
            return

        self.layers_used.append("L19:fc-sitemap")
        domain = self.district_domain.replace("www.", "")

        try:
            fc = FirecrawlApp(api_key=fc_key)
            loop = asyncio.get_event_loop()

            # Map the site
            map_result = await loop.run_in_executor(None, fc.map, f"https://{domain}")

            # Normalize links
            raw_links = []
            if hasattr(map_result, 'links'):
                raw_links = map_result.links or []
            elif isinstance(map_result, list):
                raw_links = map_result

            all_urls = []
            for link in raw_links:
                if isinstance(link, str):
                    all_urls.append(link)
                elif hasattr(link, 'url'):
                    all_urls.append(str(link.url))

            # Filter for staff/contact pages
            contact_keywords = [
                "staff", "directory", "contact", "team", "leadership",
                "administration", "department", "curriculum", "technology",
                "cte", "stem", "computer-science",
            ]
            staff_urls = [u for u in all_urls if any(kw in u.lower() for kw in contact_keywords)]

            # Only scrape URLs we haven't already scraped
            existing = {url for url, _ in self.raw_pages}
            new_staff_urls = [u for u in staff_urls if u not in existing][:8]

            logger.info(f"L19 site map: {len(all_urls)} total URLs, {len(staff_urls)} staff pages, "
                        f"{len(new_staff_urls)} new to scrape")

            # Scrape with Firecrawl (handles JS)
            for url in new_staff_urls:
                try:
                    doc = await loop.run_in_executor(
                        None, lambda u=url: fc.scrape(u, formats=["markdown"])
                    )
                    markdown = getattr(doc, 'markdown', '') or ''
                    if markdown and len(markdown) > 200:
                        self.raw_pages.append((url, str(markdown)[:15000]))
                        self._url_to_layer.setdefault(url, "L19:fc-sitemap")
                except Exception as e:
                    logger.debug(f"L19 scrape failed: {url} — {e}")

        except Exception as e:
            logger.warning(f"L19 Firecrawl site map failed: {e}")

    # ─────────────────────────────────────────────
    # LAYER 20: Brave Search (independent index)
    # ─────────────────────────────────────────────

    async def _layer20_brave_search(self):
        """Search Brave's independent index for pages Google/Exa may miss."""
        brave_key = os.environ.get("BRAVE_API_KEY", "")
        if not brave_key:
            self._skipped_layers.append("L20:brave (BRAVE_API_KEY not set)")
            return

        self.layers_used.append("L20:brave")

        queries = [
            f"{self.district_name} {self.state} computer science STEM CTE staff directory email",
            f"{self.district_name} technology coordinator curriculum director contact",
        ]

        async with httpx.AsyncClient(timeout=15) as client:
            for query in queries:
                try:
                    resp = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": brave_key, "Accept": "application/json"},
                        params={"q": query, "count": 10},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for item in data.get("web", {}).get("results", []):
                        url = item.get("url", "")
                        desc = item.get("description", "")
                        title = item.get("title", "")
                        if url and desc:
                            self.raw_pages.append((url, f"Title: {title}\nURL: {url}\n{desc}"))
                            self._url_to_layer.setdefault(url, "L20:brave")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"Brave search failed: {e}")

    # ─────────────────────────────────────────────
    # LAYER 15: Email verification & discovery
    # ─────────────────────────────────────────────

    async def _layer15_email_verification(self):
        """
        Layer 15: Email Verification & Discovery via search.

        Runs after L10 on the cleaned, deduplicated contact list.

        Steps:
          1. Identify candidates: contacts with INFERRED/UNKNOWN confidence or no email
          2. Generate candidate emails from the L8-detected pattern
          3. Verify by searching the quoted email string in Serper
          4. Enrich high-priority contacts via name+district search
          5. Discovery: search @domain to find new contacts we missed
        """
        self.layers_used.append("L15:email-verify")

        _L15_MAX = 30   # hard per-layer query cap
        _l15_used = 0

        domain = self.district_domain.replace("www.", "") if self.district_domain else ""

        # ── Priority scoring ──────────────────────────────────────────────────
        _HIGH_PRI_KEYWORDS = [
            "director", "coordinator", "chief", "officer", "superintendent",
            "administrator", "specialist", "curriculum", "cte", "stem",
            "instructional technology", "computer science", "innovation", "lead",
        ]

        def _priority(contact: dict) -> int:
            title = contact.get("title", "").lower()
            for kw in _HIGH_PRI_KEYWORDS:
                if kw in title:
                    return 2
            if any(w in title for w in ("teacher", "instructor", "coach")):
                return 1
            if "principal" in title:
                return 0
            return -1

        _conf_rank = {"VERIFIED": 4, "LIKELY": 3, "INFERRED": 2, "UNKNOWN": 1, "": 0}

        def _upgrade_confidence(contact: dict, new_conf: str, url: str = ""):
            """Upgrade email_confidence if new value is higher. Never downgrade."""
            current = _conf_rank.get(contact.get("email_confidence", "").upper(), 0)
            if _conf_rank.get(new_conf.upper(), 0) > current:
                contact["email_confidence"] = new_conf
                contact["verified_by_l15"] = True
                if url:
                    contact["source_url"] = url

        # ── Step 1: Identify candidates ───────────────────────────────────────
        candidates = [
            c for c in self.all_contacts
            if c.get("first_name") and c.get("last_name")
            and (
                c.get("email_confidence", "UNKNOWN").upper() in ("INFERRED", "UNKNOWN")
                or not c.get("email")
            )
        ]
        candidates.sort(key=_priority, reverse=True)

        # ── Steps 2+3: Generate candidate emails + verify via search ──────────
        if self.email_pattern and domain:
            for contact in candidates:
                # Reserve 5 queries for discovery (Step 5)
                if _l15_used >= _L15_MAX - 5 or self._serper_count >= self._serper_cap:
                    break

                first = contact.get("first_name", "").lower().strip()
                last = contact.get("last_name", "").lower().strip()
                if not first or not last:
                    continue

                # Build candidate email variants; handle hyphenated last names
                candidate_emails = []
                primary = infer_email(first, last, domain, self.email_pattern)
                if primary:
                    candidate_emails.append(primary)
                if "-" in last:
                    for variant_last in [last.replace("-", ""), last.split("-")[0]]:
                        v = infer_email(first, variant_last, domain, self.email_pattern)
                        if v and v not in candidate_emails:
                            candidate_emails.append(v)

                # Filter student-address patterns
                candidate_emails = [
                    e for e in candidate_emails
                    if not any(s in e for s in ("students.", "stu.", "student."))
                    and not re.search(r'\d{4}@', e)
                ]
                if not candidate_emails:
                    continue

                email_to_try = candidate_emails[0]
                results = await self._serper_batch([f'"{email_to_try}"'])
                _l15_used += 1

                # Evaluate results: VERIFIED if email+name both in snippet, else LIKELY
                new_conf = None
                best_url = ""
                for result in results:
                    for item in result.get("organic", []):
                        snippet = (
                            item.get("snippet", "") + " " + item.get("title", "")
                        ).lower()
                        url = item.get("link", "")
                        email_found = email_to_try.lower() in snippet
                        name_found = first in snippet and last.split("-")[0] in snippet
                        if email_found and name_found:
                            new_conf = "VERIFIED"
                            best_url = url
                            break
                        elif email_found and not new_conf:
                            new_conf = "LIKELY"
                            best_url = url
                    if new_conf == "VERIFIED":
                        break

                # Assign email if blank, then set/upgrade confidence
                if not contact.get("email"):
                    contact["email"] = email_to_try
                    contact["email_confidence"] = new_conf or "INFERRED"
                    if best_url:
                        contact["source_url"] = best_url
                    if new_conf:
                        contact["verified_by_l15"] = True
                elif new_conf:
                    _upgrade_confidence(contact, new_conf, best_url)

                if best_url:
                    self._url_to_layer.setdefault(best_url, "L15:email-verify")

                await asyncio.sleep(1.0)  # rate limit between verification queries

        # ── Step 4: Enrichment search for high-priority contacts ──────────────
        high_pri = [c for c in self.all_contacts if _priority(c) >= 2]
        for contact in high_pri[:8]:
            if _l15_used >= _L15_MAX - 5 or self._serper_count >= self._serper_cap:
                break

            first = contact.get("first_name", "")
            last = contact.get("last_name", "")
            if not first or not last:
                continue

            query = (
                f'"{first} {last}" "{self.district_name}" '
                f'computer science OR technology OR STEM OR CTE'
            )
            results = await self._serper_batch([query])
            _l15_used += 1

            enrichment_raw = []
            for result in results:
                for item in result.get("organic", []):
                    url = item.get("link", "")
                    snippet = item.get("snippet", "")
                    title_text = item.get("title", "")
                    if url and snippet:
                        content = f"Title: {title_text}\nURL: {url}\n{snippet}"
                        enrichment_raw.append((url, content))
                        self._url_to_layer.setdefault(url, "L15:email-verify")

            if enrichment_raw:
                self.raw_pages.extend(enrichment_raw)
                loop = asyncio.get_event_loop()
                new_contacts = await loop.run_in_executor(
                    None, extract_from_multiple, enrichment_raw, self.district_name
                )
                self._merge_contacts(new_contacts)
                # BUG 5: run Stage 2 over L15 additions so they get the
                # same cross-district filtering L9 additions do
                self._filter_contacts_by_domain()

            await asyncio.sleep(1.0)

        # ── Step 5: Discovery searches using @domain pattern ─────────────────
        # Round 1 Flag B: skip Step 5 (discovery of NEW contacts) when we
        # already have enough VERIFIED contacts. Steps 1-4 above (individual
        # verification + high-priority enrichment) still run — those are pure
        # quality gains. Only the "look for more" search is skipped.
        _skip_step5 = False
        if self.l15_step5_skip_threshold is not None:
            verified_count = sum(
                1 for c in self.all_contacts
                if (c.get("email_confidence") or "").upper() == "VERIFIED"
            )
            if verified_count >= self.l15_step5_skip_threshold:
                logger.info(
                    f"L15 Step 5 skipped: {verified_count} VERIFIED contacts "
                    f"already found (threshold={self.l15_step5_skip_threshold})"
                )
                self._skipped_layers.append("L15:step5")
                _skip_step5 = True

        if not _skip_step5 and domain and _l15_used < _L15_MAX and self._serper_count < self._serper_cap:
            remaining = min(_L15_MAX - _l15_used, 5)
            discovery_queries = [
                f'"@{domain}" "computer science" coordinator OR director',
                f'"@{domain}" STEM OR CTE coordinator OR director',
                f'"@{domain}" "instructional technology"',
                f'"@{domain}" CS teacher OR "computer science teacher"',
                f'"@{domain}" curriculum OR "digital learning"',
            ][:remaining]

            results = await self._serper_batch(discovery_queries)
            _l15_used += len(discovery_queries)

            discovery_raw = []
            for result in results:
                for item in result.get("organic", []):
                    url = item.get("link", "")
                    snippet = item.get("snippet", "")
                    title_text = item.get("title", "")
                    if url and snippet:
                        content = f"Title: {title_text}\nURL: {url}\n{snippet}"
                        discovery_raw.append((url, content))
                        self._url_to_layer.setdefault(url, "L15:email-verify")

            if discovery_raw:
                self.raw_pages.extend(discovery_raw)
                loop = asyncio.get_event_loop()
                new_contacts = await loop.run_in_executor(
                    None, extract_from_multiple, discovery_raw, self.district_name
                )
                self._merge_contacts(new_contacts)
                # BUG 5: run Stage 2 over L15 discovery additions too
                self._filter_contacts_by_domain()

        logger.info(
            f"L15 complete for {self.district_name}: {_l15_used} queries used, "
            f"{sum(1 for c in self.all_contacts if c.get('verified_by_l15'))} contacts verified/updated"
        )

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    async def _serper_batch(self, queries: list[str]) -> list[dict]:
        """Run a batch of Serper queries. Returns list of result dicts. Enforces per-job safety cap."""
        if not SERPER_API_KEY:
            logger.error("SERPER_API_KEY not set")
            return []

        results = []
        for query in queries:
            # Safety cap — stop if budget exhausted
            if self._serper_count >= self._serper_cap:
                if not self._cap_hit:
                    self._cap_hit = True
                    logger.warning(f"Serper cap hit ({self._serper_cap}) for {self.district_name} — remaining queries skipped")
                results.append({})
                continue

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        SERPER_URL,
                        headers={
                            "X-API-KEY": SERPER_API_KEY,
                            "Content-Type": "application/json"
                        },
                        json={"q": query, "num": 10},
                    )
                    response.raise_for_status()
                    results.append(response.json())
                    self._serper_count += 1
                await asyncio.sleep(0.3)  # rate limit courtesy — non-blocking
            except Exception as e:
                logger.error(f"Serper query failed: '{query}' — {e}")
                results.append({})

        return results

    def _add_raw_from_serper(self, results: list[dict], layer_tag: str = ""):
        """Extract snippet text from Serper results and add to raw_pages."""
        for result in results:
            for item in result.get("organic", []):
                url = item.get("link", "")
                snippet = item.get("snippet", "")
                title = item.get("title", "")
                if url and snippet:
                    content = f"Title: {title}\nURL: {url}\n{snippet}"
                    self.raw_pages.append((url, content))
                    if layer_tag and url not in self._url_to_layer:
                        self._url_to_layer[url] = layer_tag

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
        """
        Merge new contacts into all_contacts. On name collision, upgrade the
        existing entry (fill missing email, raise confidence, fill empty title)
        instead of silently dropping the newer contact.

        Uses the shared helper in contact_extractor so the merge rule is
        consistent across every call site in the research pipeline.
        """
        from tools.contact_extractor import _merge_contact_upgrade

        index: dict[str, dict] = {}
        for c in self.all_contacts:
            fn = (c.get("first_name") or "").lower()
            ln = (c.get("last_name") or "").lower()
            index[f"{fn}|{ln}"] = c

        for c in new_contacts:
            fn = (c.get("first_name") or "").lower()
            ln = (c.get("last_name") or "").lower()
            key = f"{fn}|{ln}"
            existing = index.get(key)
            if existing is None:
                index[key] = c
                self.all_contacts.append(c)
            else:
                _merge_contact_upgrade(existing, c)

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
        completion_callback,
        serper_cap_override: int = None,
    ):
        """
        Add a job to the queue.
        completion_callback(result: dict) is called when done.
        serper_cap_override: if set, overrides SERPER_REQUESTS_PER_JOB for this job.

        BUG 4 Session 56: if district_name canonicalizes into DIOCESAN_DOMAIN_MAP,
        the job automatically activates the diocesan research playbook. Lazy
        import keeps the dependency direction one-way (research_engine does
        not appear in private_schools imports).
        """
        diocesan_domain = ""
        try:
            from tools.private_schools import DIOCESAN_DOMAIN_MAP, _canonical_diocesan_key
            diocesan_domain = DIOCESAN_DOMAIN_MAP.get(_canonical_diocesan_key(district_name), "")
        except Exception as e:
            logger.debug(f"DIOCESAN_DOMAIN_MAP lookup failed for {district_name!r}: {e}")

        await self._queue.put({
            "district_name": district_name,
            "state": state,
            "progress_callback": progress_callback,
            "completion_callback": completion_callback,
            "serper_cap_override": serper_cap_override,
            "diocesan_domain": diocesan_domain,
            "diocesan_playbook": bool(diocesan_domain),
        })

        if not self._running:
            asyncio.create_task(self._worker())

    async def _worker(self):
        """Process jobs one at a time."""
        self._running = True
        while not self._queue.empty():
            job = await self._queue.get()
            self._current_job = job["district_name"]
            start_time = asyncio.get_event_loop().time()

            # Heartbeat: send a "still working" ping every 60 seconds
            async def _heartbeat(district_name: str, progress_callback, start: float):
                try:
                    while True:
                        await asyncio.sleep(60)
                        elapsed = int((asyncio.get_event_loop().time() - start) / 60)
                        if progress_callback:
                            await progress_callback(
                                f"⏳ Still researching *{district_name}*... ({elapsed} min elapsed)"
                            )
                except asyncio.CancelledError:
                    pass

            heartbeat_task = asyncio.create_task(
                _heartbeat(job["district_name"], job["progress_callback"], start_time)
            )

            try:
                engine = ResearchJob(
                    district_name=job["district_name"],
                    state=job["state"],
                    progress_callback=job["progress_callback"],
                    serper_cap_override=job.get("serper_cap_override"),
                    diocesan_domain=job.get("diocesan_domain", ""),
                    diocesan_playbook=job.get("diocesan_playbook", False),
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
                heartbeat_task.cancel()
                self._current_job = None
                self._queue.task_done()

        self._running = False


    async def enqueue_batch(
        self,
        targets: list[dict],
        progress_callback,
        completion_callback,
    ):
        """
        Queue multiple research jobs. Each processes sequentially.
        Each target dict: {district_name, state (optional)}
        """
        for target in targets:
            await self.enqueue(
                district_name=target["district_name"],
                state=target.get("state", ""),
                progress_callback=progress_callback,
                completion_callback=completion_callback,
            )


# Singleton queue instance
research_queue = ResearchQueue()
