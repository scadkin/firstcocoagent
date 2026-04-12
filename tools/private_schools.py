"""
tools/private_schools.py

F8 Private School Discovery.

Original Session 49 plan called for Urban Institute PSS sync, but Urban
Institute does NOT expose PSS data (only CCD, CRDC, EdFacts, higher ed).
NCES Private School Locator HTML is rate-capped to 15 results/query with
no pagination — unusable for bulk sync.

Pivot: Serper-based on-demand discovery (pattern matches F10 homeschool
co-ops). Steven runs it per state, reviews results, prospect_adds the
ones worth pursuing.

Also provides a small static seed of major multi-school private school
networks (diocesan systems, national independent chains) for high-leverage
targeting where one account = many schools.

MODULE not class.
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

# Kill switch — F8 private school Serper discovery
ENABLE_PRIVATE_SCHOOL_DISCOVERY = False  # DISABLED Session 54 Phase 0 — BUG 3 queue column corruption investigation. Re-enable after Phase 6.

TERRITORY_STATES = {"IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE", "TX"}
TERRITORY_STATES_WITH_CA = TERRITORY_STATES | {"CA"}

_STATE_NAMES = {
    "IL": "Illinois", "PA": "Pennsylvania", "OH": "Ohio", "MI": "Michigan",
    "CT": "Connecticut", "OK": "Oklahoma", "MA": "Massachusetts", "IN": "Indiana",
    "NV": "Nevada", "TN": "Tennessee", "NE": "Nebraska", "TX": "Texas",
    "CA": "California",
}

# Static seed of multi-school private networks with presence in territory
# states. One relationship = multiple schools. Not exhaustive.
PRIVATE_SCHOOL_NETWORKS = [
    # Catholic diocesan systems — each runs 10-100+ schools.
    # `domain` fields added Session 56 (BUG 4) for the diocesan research
    # playbook. Verified 2026-04-10 via Serper + HTTP title fetch.
    {"name": "Archdiocese of Chicago Schools", "state": "IL", "schools": 125, "domain": "schools.archchicago.org", "notes": "Largest Catholic school system in IL. ~125 schools, ~49K students."},
    {"name": "Archdiocese of Boston Catholic Schools", "state": "MA", "schools": 100, "domain": "bostoncatholic.org", "notes": "~100 Catholic schools across MA."},
    {"name": "Diocese of Pittsburgh Schools", "state": "PA", "schools": 55, "domain": "diopitt.org", "notes": "Pittsburgh-area Catholic schools."},
    {"name": "Archdiocese of Philadelphia Schools", "state": "PA", "schools": 120, "domain": "archphila.org", "notes": "Philadelphia Catholic schools, one of the largest dioceses by school count."},
    {"name": "Diocese of Cleveland Schools", "state": "OH", "schools": 90, "domain": "dioceseofcleveland.org", "notes": "NE Ohio Catholic schools."},
    {"name": "Archdiocese of Cincinnati Schools", "state": "OH", "schools": 110, "domain": "catholicaoc.org", "notes": "SW Ohio Catholic schools."},
    {"name": "Archdiocese of Detroit Schools", "state": "MI", "schools": 80, "domain": "aod.org", "notes": "SE Michigan Catholic schools."},
    {"name": "Archdiocese of Oklahoma City Schools", "state": "OK", "schools": 20, "domain": "archokc.org", "notes": "Central/western OK Catholic schools."},
    {"name": "Diocese of Tulsa Schools", "state": "OK", "schools": 10, "domain": "dioceseoftulsa.org", "notes": "Eastern OK Catholic schools."},
    {"name": "Diocese of Nashville Schools", "state": "TN", "schools": 18, "domain": "dioceseofnashville.com", "notes": "Middle TN Catholic schools."},
    {"name": "Diocese of Memphis Schools", "state": "TN", "schools": 10, "domain": "cdom.org", "notes": "Western TN Catholic schools."},
    {"name": "Diocese of Fort Worth Schools", "state": "TX", "schools": 20, "domain": "fwdioc.org", "notes": "North TX Catholic schools."},
    {"name": "Archdiocese of Galveston-Houston Schools", "state": "TX", "schools": 55, "domain": "archgh.org", "notes": "Greater Houston Catholic schools."},
    {"name": "Archdiocese of Los Angeles Schools", "state": "CA", "schools": 215, "domain": "lacatholicschools.org", "notes": "LARGEST Catholic school system in US. 215+ schools."},
    {"name": "Diocese of Lincoln Schools", "state": "NE", "schools": 28, "domain": "lincolndiocese.org", "notes": "Eastern NE Catholic schools."},
    {"name": "Archdiocese of Omaha Schools", "state": "NE", "schools": 70, "domain": "schools.archomaha.org", "notes": "Eastern NE Catholic schools."},
    # National independent school networks
    {"name": "BASIS Charter Schools (Independent branch)", "state": "TX", "schools": 12, "notes": "BASIS Independent branch — tuition private schools. TX, DC, NY, VA, CA."},
    {"name": "Great Hearts Academies", "state": "TX", "schools": 8, "notes": "Classical liberal arts. TX network (also listed under charter for public charter schools)."},
    {"name": "Challenger School", "state": "NV", "schools": 4, "notes": "Western Expansion — CA and NV campuses."},
    {"name": "Primrose Schools", "state": "TX", "schools": 450, "notes": "Early childhood + K. Nationwide franchise."},
    {"name": "Stratford School", "state": "CA", "schools": 28, "notes": "California-focused independent PK-8."},
    {"name": "Waldorf Association Schools", "state": "CA", "schools": 40, "notes": "AWSNA-affiliated Waldorf schools across CA."},
    # Jewish day school networks
    {"name": "Yeshiva University of Los Angeles (YULA)", "state": "CA", "schools": 3, "notes": "LA Jewish day school network."},
    {"name": "Solomon Schechter Day School (various)", "state": "MA", "schools": 3, "notes": "Conservative Jewish day schools in Boston/Newton."},
]


def _canonical_diocesan_key(name: str) -> str:
    """Normalize diocesan district names for robust lookup.

    Lowercases and strips trailing ' schools' / ' catholic schools' so
    variations like 'Archdiocese of Chicago', 'archdiocese of chicago schools',
    and 'Archdiocese of Chicago Catholic Schools' all resolve to the same key.
    Used on both DIOCESAN_DOMAIN_MAP keys at build time and lookup input at
    runtime in ResearchQueue.enqueue.
    """
    h = (name or "").strip().lower()
    for suf in (" catholic schools", " schools"):
        if h.endswith(suf):
            h = h[: -len(suf)]
            break
    return h


# BUG 4 Session 56 — diocesan research playbook activation map. Built from
# PRIVATE_SCHOOL_NETWORKS at import time so it can't drift from the seed.
# Keys are canonicalized (via _canonical_diocesan_key); lookup must use the
# same function on the query district name.
DIOCESAN_DOMAIN_MAP: dict[str, str] = {
    _canonical_diocesan_key(n["name"]): n["domain"]
    for n in PRIVATE_SCHOOL_NETWORKS
    if n.get("domain")
    and (n["name"].startswith("Archdiocese") or n["name"].startswith("Diocese"))
}


def list_private_school_networks(state: Optional[str] = None) -> list[dict]:
    """Return static seed list filtered by state."""
    if not state:
        return list(PRIVATE_SCHOOL_NETWORKS)
    s = state.strip().upper()
    return [n for n in PRIVATE_SCHOOL_NETWORKS if (n.get("state") or "").upper() == s]


def discover_private_schools(state: str, max_results: int = 25) -> dict:
    """
    F8: Serper-based discovery of notable private schools in a state.

    Returns {
        state, count,
        schools: [{name, city, url, snippet, estimated_size}]
    }

    Focuses on larger/multi-campus private schools and excludes daycares,
    preschools-only, homeschool co-ops, and colleges.
    """
    if not ENABLE_PRIVATE_SCHOOL_DISCOVERY:
        return {"state": state, "count": 0, "schools": [], "error": "disabled via ENABLE_PRIVATE_SCHOOL_DISCOVERY"}
    if not SERPER_API_KEY:
        return {"state": state, "count": 0, "schools": [], "error": "SERPER_API_KEY not set"}

    state_abbr = state.strip().upper()
    if state_abbr not in TERRITORY_STATES_WITH_CA:
        return {
            "state": state_abbr,
            "count": 0,
            "schools": [],
            "error": f"{state_abbr} not in territory",
        }
    state_name = _STATE_NAMES.get(state_abbr, state_abbr)

    import httpx

    exclusions = (
        "-site:facebook.com -site:yelp.com -site:niche.com -site:greatschools.org "
        "-preschool -daycare -homeschool -college -university"
    )
    queries = [
        f'"private school" "{state_name}" top OR best K-12 {exclusions}',
        f'private day school "{state_name}" independent K-12 {exclusions}',
        f'catholic school "{state_name}" diocese enrollment {exclusions}',
        f'"private school" "{state_name}" tuition grades enrollment {exclusions}',
    ]

    schools = []
    seen_urls = set()
    seen_names = set()

    for q in queries:
        try:
            resp = httpx.post(
                SERPER_URL,
                headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": q, "num": 10},
                timeout=15.0,
            )
            data = resp.json()
            for item in data.get("organic", [])[:10]:
                url = item.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = item.get("title", "").strip()
                snippet = item.get("snippet", "").strip()
                lower = (title + " " + snippet).lower()

                # Filter: must look like a specific school, not a listing
                bad_phrases = (
                    "list of", "top 10", "best private", "niche", "ranking",
                    "reviews of", "compare", "greatschools", "admissions consultant",
                    "wikipedia",
                )
                if any(b in lower for b in bad_phrases):
                    continue

                # Dedup by name token
                name_key = title.lower()[:30]
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                # Heuristic size
                size = "unknown"
                if any(n in lower for n in ("800 students", "1000 students", "1200 students", "large")):
                    size = "large"
                elif any(n in lower for n in ("400 students", "500 students", "600 students", "medium")):
                    size = "medium"
                elif any(n in lower for n in ("100 students", "200 students", "small")):
                    size = "small"

                # City extraction (crude — first comma-separated token before state)
                city = ""
                for part in snippet.replace(",", ".").split("."):
                    if state_name in part or f" {state_abbr} " in f" {part} ":
                        tokens = part.strip().split()
                        for i, t in enumerate(tokens):
                            if t == state_abbr or t == state_name:
                                if i > 0:
                                    cand = tokens[i - 1].strip(",. ")
                                    if cand[:1].isupper() and len(cand) > 2:
                                        city = cand
                                        break
                        if city:
                            break

                schools.append({
                    "name": title,
                    "city": city,
                    "url": url,
                    "snippet": snippet[:200],
                    "estimated_size": size,
                })
                if len(schools) >= max_results:
                    break
            time.sleep(0.3)
            if len(schools) >= max_results:
                break
        except Exception as e:
            logger.warning(f"Serper private school query failed: {e}")

    logger.info(f"Private school discovery ({state_abbr}): {len(schools)} schools found")
    return {
        "state": state_abbr,
        "count": len(schools),
        "schools": schools[:max_results],
    }


def queue_private_school_networks(state: Optional[str] = None) -> dict:
    """
    Queue the static seed of multi-school networks (dioceses, chains) as
    prospects with strategy="private_school_network".
    """
    import tools.district_prospector as district_prospector

    networks = list_private_school_networks(state)
    if not networks:
        return {"found": 0, "queued": [], "skipped": [], "errors": []}

    queued = []
    skipped = []
    errors = []

    for n in networks:
        name = n.get("name") or ""
        st = n.get("state") or ""
        schools = n.get("schools") or 0
        notes_extra = n.get("notes") or ""
        full_notes = f"Private school network. {schools} schools. {notes_extra}".strip()

        try:
            from tools.signal_processor import build_csta_enrichment
            full_notes, priority_bonus = build_csta_enrichment(name, st, full_notes)
            result = district_prospector.add_district(
                name=name,
                state=st,
                notes=full_notes,
                strategy="private_school_network",
                source="manual",
                schools=schools,
                priority_bonus=priority_bonus,
            )
            if result.get("success"):
                queued.append({"name": name, "state": st, "schools": schools})
            else:
                skipped.append({
                    "name": name,
                    "state": st,
                    "reason": result.get("error", "unknown"),
                })
        except Exception as e:
            errors.append(f"{name}: {e}")

    return {
        "found": len(networks),
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
    }


def format_discovery_for_telegram(result: dict) -> str:
    """Format discover_private_schools output for Telegram."""
    if result.get("error"):
        return f"❌ Private school discovery: {result['error']}"

    schools = result.get("schools", [])
    state = result.get("state", "?")

    if not schools:
        return f"🏫 No private schools found in {state}."

    lines = [f"🏫 *Private schools in {state}* — {len(schools)} found"]
    lines.append("")
    for i, s in enumerate(schools[:15], 1):
        size_marker = {"large": "🟢", "medium": "🟡", "small": "🔵", "unknown": "⚪"}.get(
            s["estimated_size"], "⚪"
        )
        name = s["name"][:55]
        city_str = f" ({s['city']})" if s["city"] else ""
        lines.append(f"{i}. {size_marker} {name}{city_str}")
        if s["snippet"]:
            lines.append(f"    _{s['snippet'][:100]}_")
        lines.append(f"    {s['url'][:100]}")
        lines.append("")

    if len(schools) > 15:
        lines.append(f"_...and {len(schools) - 15} more._")

    lines.append("")
    lines.append("Use `/prospect_add [name], [state]` to queue any for outreach.")
    lines.append("Or `/prospect_private_networks [state]` to queue diocesan/chain networks.")
    return "\n".join(lines)


def format_networks_queue_for_telegram(result: dict) -> str:
    """Format queue_private_school_networks output."""
    found = result.get("found", 0)
    queued = result.get("queued", [])
    skipped = result.get("skipped", [])
    errors = result.get("errors", [])

    lines = [f"⛪ *Private School Networks* — {found} networks matched"]
    lines.append("")

    if queued:
        lines.append(f"✅ Queued {len(queued)}:")
        for q in queued[:15]:
            lines.append(f"  • {q['name'][:50]} ({q['state']}) — {q['schools']} schools")
        if len(queued) > 15:
            lines.append(f"  ...and {len(queued) - 15} more")
        lines.append("")

    if skipped:
        lines.append(f"⏭ Skipped {len(skipped)}:")
        for s in skipped[:10]:
            lines.append(f"  • {s['name'][:45]} — {s.get('reason', '')[:30]}")
        lines.append("")

    if errors:
        lines.append(f"⚠️ {len(errors)} errors")
        lines.append("")

    lines.append("Review with `/prospect_all`.")
    return "\n".join(lines)
