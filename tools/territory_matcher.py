"""
tools/territory_matcher.py — Territory Master List matching utility.

Matches messy school/district names from any source (Outreach, Salesforce, CSV)
against the NCES Territory Master List. Uses tiered matching with increasing
fuzziness. Returns canonical names, parent districts, states, and confidence levels.

This is a core utility used by:
  - C4 cold license request scan (district_prospector)
  - C3 winback territory cross-check (district_prospector)
  - B2 SF Leads/Contacts enrichment (lead_importer)
  - Territory gap analysis (territory_data)

Usage:
  import tools.territory_matcher as territory_matcher
  result = territory_matcher.match_record("Huntington Beach HS", email="teacher@hbuhsd.edu")
  if result:
      print(result.canonical_name, result.state, result.parent_district)
"""

import dataclasses
import logging
import re
import time

import tools.csv_importer as csv_importer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# MATCH RESULT
# ─────────────────────────────────────────────

@dataclasses.dataclass
class MatchResult:
    canonical_name: str       # NCES name (title case)
    name_key: str             # normalized key
    entity_type: str          # "school" or "district"
    parent_district: str      # district name (for schools), empty for districts
    state: str                # 2-letter state code
    city: str                 # city from NCES data
    enrollment: int           # from NCES data
    nces_id: str              # NCESSCH for schools, LEAID for districts
    confidence: str           # "exact", "high", "medium", "low"
    match_method: str         # e.g. "exact_name", "suffix_stripped", "email_domain", etc.


# ─────────────────────────────────────────────
# SCHOOL SUFFIX STRIPPING
# ─────────────────────────────────────────────

# Sorted longest-first for greedy matching
_SCHOOL_SUFFIXES = sorted([
    "high school", "middle school", "elementary school", "junior high school",
    "senior high school", "intermediate school",
    "high", "middle", "elementary", "junior high", "senior high", "intermediate",
    "academy", "charter school", "charter", "magnet school", "magnet",
    "preparatory school", "preparatory", "prep school", "prep",
    "primary school", "primary", "continuation school", "continuation",
    "alternative school", "alternative", "learning center", "center",
    "campus", "school",
], key=len, reverse=True)


def _strip_school_suffixes(name: str) -> str:
    """Strip school-type suffixes to get the core name for fuzzy matching."""
    n = name.strip().lower()
    n = re.sub(r'\s*\(.*?\)\s*', ' ', n)  # remove parentheticals
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    for suffix in _SCHOOL_SUFFIXES:
        if n.endswith(suffix):
            stripped = n[:len(n) - len(suffix)].strip()
            if len(stripped) >= 3:  # don't strip to nothing
                n = stripped
                break
    return n


# ─────────────────────────────────────────────
# DOMAIN UTILITIES
# ─────────────────────────────────────────────

_GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
    "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
    "earthlink.net", "me.com", "live.com", "ymail.com",
}


def extract_domain_root(email: str) -> str:
    """
    Extract meaningful root from an email domain.
    e.g. teacher@spring.k12.tx.us → "spring"
         admin@austinisd.org → "austinisd"
         teacher@staff.lausd.net → "lausd"
    """
    if not email or "@" not in email:
        return ""
    domain = email.lower().split("@")[-1].strip()
    if domain in _GENERIC_DOMAINS:
        return ""

    # Handle k12-style: spring.k12.tx.us → "spring"
    parts = domain.split(".")
    if len(parts) >= 4 and parts[-2] == "us":
        # state.us domain
        for p in parts:
            if p not in ("k12", "us", "pvt", "tec", "cc", "lib", "state",
                         "org", "net", "edu", "com", "gov") and len(p) > 1:
                if len(p) <= 2:
                    continue  # state code
                return p

    # Handle multi-level: staff.austinisd.org → "austinisd"
    if len(parts) >= 3:
        # Skip common prefixes
        prefixes = {"staff", "mail", "email", "webmail", "my", "students", "student",
                    "stu", "apps", "portal", "admin"}
        for p in parts[:-2]:  # skip TLD parts
            if p not in prefixes and len(p) > 2:
                return p

    # Standard: austinisd.org → "austinisd"
    if parts:
        root = parts[0]
        if len(root) > 2:
            return root

    return ""


def generate_domain_roots(name: str) -> set[str]:
    """
    Generate plausible email domain roots from a school/district name.
    e.g. "Austin Independent School District" → {"austinisd", "austin", "aisd"}
    """
    if not name:
        return set()
    words = re.sub(r'[^a-z0-9\s]', '', name.lower()).split()
    # Filter out common suffixes
    stop_words = {"school", "district", "independent", "unified", "public",
                  "schools", "elementary", "middle", "high", "junior",
                  "senior", "county", "city", "area", "regional", "community",
                  "consolidated", "central", "union", "joint", "free"}
    content_words = [w for w in words if w not in stop_words and len(w) > 1]

    roots = set()
    if content_words:
        # Full concatenation: "Austin ISD" → "austinisd"
        roots.add("".join(words[:4]))
        # Just content words: "austinisd"
        roots.add("".join(content_words[:3]))
        # First content word: "austin"
        roots.add(content_words[0])
        # Acronym: "Austin Independent School District" → "aisd"
        if len(words) >= 2:
            acronym = "".join(w[0] for w in words if w)
            if len(acronym) >= 3:
                roots.add(acronym)
        # Content word acronym
        if len(content_words) >= 2:
            c_acronym = "".join(w[0] for w in content_words)
            if len(c_acronym) >= 2:
                roots.add(c_acronym)

    return {r for r in roots if len(r) >= 3}


# ─────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────

_cache = None
_cache_loaded_at = 0.0
_CACHE_TTL = 3600  # 1 hour


def ensure_cache(force_reload: bool = False):
    """Load territory data into memory indexes if not already cached."""
    global _cache, _cache_loaded_at

    if _cache and not force_reload and (time.time() - _cache_loaded_at) < _CACHE_TTL:
        return

    import tools.territory_data as territory_data

    logger.info("territory_matcher: loading territory data into cache...")
    t0 = time.time()

    schools = territory_data._load_territory_schools()
    districts = territory_data._load_territory_districts()

    # Build indexes
    schools_by_key = {}
    schools_by_stripped = {}
    districts_by_key = {}
    districts_by_stripped = {}
    by_domain_root = {}
    by_city_state = {}

    for s in schools:
        nk = (s.get("Name Key") or "").strip().lower()
        if nk:
            schools_by_key.setdefault(nk, []).append(s)
        sn = _strip_school_suffixes(s.get("School Name") or "")
        if sn and len(sn) >= 3:
            schools_by_stripped.setdefault(sn, []).append(s)
        # City+state index
        city = (s.get("City") or "").strip().lower()
        state = (s.get("State") or "").strip().upper()
        if city and state:
            by_city_state.setdefault((city, state), []).append(s)

    for d in districts:
        nk = (d.get("Name Key") or "").strip().lower()
        if nk:
            districts_by_key.setdefault(nk, []).append(d)
        dn = _strip_school_suffixes(d.get("District Name") or "")
        if dn and len(dn) >= 3:
            districts_by_stripped.setdefault(dn, []).append(d)
        # Domain root index
        d_name = d.get("District Name") or ""
        for root in generate_domain_roots(d_name):
            by_domain_root.setdefault(root, []).append(d)
        # City+state index
        city = (d.get("City") or "").strip().lower()
        state = (d.get("State") or "").strip().upper()
        if city and state:
            by_city_state.setdefault((city, state), []).append(d)

    _cache = {
        "schools": schools,
        "districts": districts,
        "schools_by_key": schools_by_key,
        "schools_by_stripped": schools_by_stripped,
        "districts_by_key": districts_by_key,
        "districts_by_stripped": districts_by_stripped,
        "by_domain_root": by_domain_root,
        "by_city_state": by_city_state,
    }
    _cache_loaded_at = time.time()

    elapsed = time.time() - t0
    logger.info(
        f"territory_matcher: cache loaded in {elapsed:.1f}s — "
        f"{len(schools)} schools, {len(districts)} districts, "
        f"{len(schools_by_key)} school keys, {len(districts_by_key)} district keys, "
        f"{len(by_domain_root)} domain roots, {len(by_city_state)} city+state combos"
    )


def get_cache_stats() -> dict:
    """Return cache info for diagnostics."""
    if not _cache:
        return {"loaded": False}
    return {
        "loaded": True,
        "schools": len(_cache["schools"]),
        "districts": len(_cache["districts"]),
        "school_keys": len(_cache["schools_by_key"]),
        "district_keys": len(_cache["districts_by_key"]),
        "domain_roots": len(_cache["by_domain_root"]),
        "city_state_combos": len(_cache["by_city_state"]),
        "age_seconds": int(time.time() - _cache_loaded_at),
    }


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def _record_to_result(rec: dict, entity_type: str, confidence: str, method: str) -> MatchResult:
    """Convert a raw territory record to a MatchResult."""
    if entity_type == "school":
        name = rec.get("School Name", "")
        parent = rec.get("District Name", "")
        nces_id = rec.get("NCESSCH", "")
    else:
        name = rec.get("District Name", "")
        parent = ""
        nces_id = rec.get("LEAID", "")

    enrollment = 0
    try:
        enrollment = int(rec.get("Enrollment") or 0)
    except (ValueError, TypeError):
        pass

    return MatchResult(
        canonical_name=name,
        name_key=(rec.get("Name Key") or csv_importer.normalize_name(name)),
        entity_type=entity_type,
        parent_district=parent,
        state=(rec.get("State") or "").strip().upper(),
        city=(rec.get("City") or "").strip(),
        enrollment=enrollment,
        nces_id=nces_id,
        confidence=confidence,
        match_method=method,
    )


def _filter_by_state(records: list[dict], state: str) -> list[dict]:
    """Filter records to a specific state. If state is empty, return all."""
    if not state:
        return records
    return [r for r in records if (r.get("State") or "").strip().upper() == state.upper()]


def match_record(
    name: str,
    *,
    email: str = "",
    city: str = "",
    state: str = "",
) -> MatchResult | None:
    """
    Match a school/district name against the Territory Master List.

    Uses tiered matching (first match wins):
      1. Exact normalized name
      2. Suffix-stripped name
      3. Email domain → district
      4. City + token overlap
      5. Containment match

    Returns MatchResult or None if no match found.
    """
    ensure_cache()
    if not _cache or not name:
        return None

    name = name.strip()
    if not name:
        return None

    name_key = csv_importer.normalize_name(name).lower()
    stripped = _strip_school_suffixes(name)
    state = state.strip().upper() if state else ""

    # ── Tier 1: Exact normalized name match ──
    for entity_type, index in [("school", _cache["schools_by_key"]),
                                ("district", _cache["districts_by_key"])]:
        matches = index.get(name_key, [])
        if state:
            matches = _filter_by_state(matches, state)
        if matches:
            return _record_to_result(matches[0], entity_type, "exact", "exact_name")

    # ── Tier 2: Suffix-stripped name match ──
    if stripped and len(stripped) >= 3:
        for entity_type, index in [("school", _cache["schools_by_stripped"]),
                                    ("district", _cache["districts_by_stripped"])]:
            matches = index.get(stripped, [])
            if state:
                matches = _filter_by_state(matches, state)
            if len(matches) == 1:
                return _record_to_result(matches[0], entity_type, "high", "suffix_stripped")
            elif len(matches) > 1 and state:
                # Multiple matches in same state — return first (usually correct)
                return _record_to_result(matches[0], entity_type, "high", "suffix_stripped")

    # ── Tier 3: Email domain match ──
    if email:
        domain_root = extract_domain_root(email)
        if domain_root:
            matches = _cache["by_domain_root"].get(domain_root, [])
            if state:
                matches = _filter_by_state(matches, state)
            if len(matches) == 1:
                return _record_to_result(matches[0], "district", "high", "email_domain")
            elif len(matches) > 1:
                # Multiple districts match this domain — try to disambiguate with name
                for m in matches:
                    d_key = (m.get("Name Key") or "").lower()
                    if d_key and (d_key in name_key or name_key in d_key):
                        return _record_to_result(m, "district", "high", "email_domain+name")
                # Fall back to first match if state matches
                if matches:
                    return _record_to_result(matches[0], "district", "medium", "email_domain_ambiguous")

    # ── Tier 4: City + token overlap ──
    city_lower = city.strip().lower() if city else ""
    if city_lower and state:
        city_records = _cache["by_city_state"].get((city_lower, state), [])
        if city_records:
            input_tokens = set(stripped.split()) if stripped else set(name_key.split())
            best_match = None
            best_overlap = 0.0

            for rec in city_records:
                rec_name = rec.get("School Name") or rec.get("District Name") or ""
                rec_stripped = _strip_school_suffixes(rec_name)
                rec_tokens = set(rec_stripped.split())

                if not input_tokens or not rec_tokens:
                    continue

                shared = input_tokens & rec_tokens
                total = input_tokens | rec_tokens
                overlap = len(shared) / len(total) if total else 0

                if overlap > best_overlap and len(shared) >= 2 and overlap >= 0.5:
                    best_overlap = overlap
                    entity_type = "school" if "School Name" in rec else "district"
                    best_match = (rec, entity_type)

            if best_match:
                rec, entity_type = best_match
                conf = "medium" if best_overlap >= 0.7 else "low"
                return _record_to_result(rec, entity_type, conf, f"city_token_overlap({best_overlap:.0%})")

    # ── Tier 5: Containment match (state required) ──
    if state and stripped and len(stripped) >= 8:
        for entity_type, index in [("school", _cache["schools_by_stripped"]),
                                    ("district", _cache["districts_by_stripped"])]:
            for rec_stripped, recs in index.items():
                if len(rec_stripped) < 6:
                    continue
                # Check containment in both directions
                if rec_stripped in stripped or stripped in rec_stripped:
                    shorter = min(len(rec_stripped), len(stripped))
                    longer = max(len(rec_stripped), len(stripped))
                    if shorter >= 6 and shorter / longer >= 0.5:
                        state_matches = _filter_by_state(recs, state)
                        if state_matches:
                            return _record_to_result(
                                state_matches[0], entity_type, "low", "containment"
                            )

    return None


def match_records(
    records: list[dict],
    *,
    name_field: str = "company",
    email_field: str = "email",
    city_field: str = "city",
    state_field: str = "state",
) -> list[tuple[dict, MatchResult | None]]:
    """
    Match a batch of records. Loads cache once, then matches each record.
    Returns list of (original_record, match_result_or_None) tuples.
    """
    ensure_cache()
    results = []
    for rec in records:
        name = rec.get(name_field) or ""
        email = rec.get(email_field) or ""
        city_val = rec.get(city_field) or ""
        state_val = rec.get(state_field) or ""
        # Handle email as list (Outreach returns emails as list)
        if isinstance(email, list):
            email = email[0] if email else ""
        match = match_record(name, email=email, city=city_val, state=state_val)
        results.append((rec, match))
    return results
