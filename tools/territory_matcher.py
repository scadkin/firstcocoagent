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

# Known SoCal school district domain roots (creative abbreviations not derivable from NCES names)
# Used as fallback when generate_domain_roots doesn't produce the right match
KNOWN_SOCAL_DOMAIN_ROOTS = {
    "lausd", "sandi", "sausd", "ggusd", "abcusd", "myabcusd", "iusd", "tustin",
    "capousd", "svusd", "fjuhsd", "auhsd", "pylusd", "bousd", "hbuhsd",
    "lbusd", "musd", "cnusd", "cjusd", "mvusd", "psusd", "rusd", "ausd",
    "jusd", "alvord", "hemet", "menifee", "beaumont", "banning", "perris",
    "rialto", "fontana", "colton", "redlands", "yucaipa", "sbcusd",
    "aesd", "dusd", "eusd", "fusd", "gusd", "husd", "kusd", "nusd",
    "ousd", "pusd", "tusd", "vusd", "wusd", "busd", "cusd",
    "smusd", "smmusd", "lvusd", "wvusd", "hlpusd", "bassett", "hacienda",
    "keppel", "rosemead", "elrancho", "whittier", "lawndale", "centinela",
    "hawthorne", "inglewood", "compton", "lynwood", "paramount", "bellflower",
    "downey", "montebello", "lacrescenta", "burbank", "glendale", "pasadena",
    "arcadia", "monrovia", "azusa", "covina", "westcovina", "pomona", "claremont",
    "oceanside", "carlsbad", "escondido", "fallbrook", "poway", "ramona",
    "cajon", "santee", "lakeside", "coronado", "sweetwater", "cvesd", "nmusd",
    "olphriverside", "stodiliaschool",
}

_GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
    "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
    "earthlink.net", "me.com", "live.com", "ymail.com",
}


_US_STATE_ABBRS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}

_STATE_NAME_TO_ABBR = {
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

# Known US cities/regions → state mapping (major cities that appear in email domains)
_CITY_TO_STATE = {
    "nyc": "NY", "newyork": "NY", "brooklyn": "NY", "bronx": "NY", "queens": "NY",
    "manhattan": "NY", "statenisland": "NY", "buffalo": "NY",
    "chicago": "IL", "springfield": "IL",
    "houston": "TX", "dallas": "TX", "sanantonio": "TX", "austin": "TX",
    "fortworth": "TX", "elpaso": "TX", "wichitafalls": "TX",
    "losangeles": "CA", "sandiego": "CA", "sanfrancisco": "CA", "sacramento": "CA",
    "sanjose": "CA", "riverside": "CA", "longbeach": "CA", "oakland": "CA",
    "philadelphia": "PA", "pittsburgh": "PA",
    "detroit": "MI", "grandrapids": "MI",
    "columbus": "OH", "cleveland": "OH", "cincinnati": "OH",
    "indianapolis": "IN",
    "nashville": "TN", "memphis": "TN", "knoxville": "TN",
    "oklahomacity": "OK", "tulsa": "OK",
    "omaha": "NE", "lincoln": "NE",
    "lasvegas": "NV", "reno": "NV",
    "boston": "MA", "cambridge": "MA", "worcester": "MA",
    "hartford": "CT", "newhaven": "CT", "bridgeport": "CT", "stamford": "CT",
    "dc": "DC", "washington": "DC",
}


def extract_state_from_email(email: str) -> str:
    """
    Extract 2-letter US state code from email domain using multiple patterns.

    Patterns checked (in order):
      1. k12.STATE.us or *.k12.STATE.us (any length, .us or .gov TLD)
      2. State abbreviation as last 2 chars of domain root (harmonytx → TX)
      3. State abbreviation after separator (acs-nj → NJ)
      4. State name in domain (hawaii.edu → HI)
      5. Known city in domain (schools.nyc.gov → NY, udallas.edu → TX)

    Returns 2-letter state code or empty string.
    """
    if not email or "@" not in email:
        return ""
    domain = email.lower().split("@")[-1].strip()
    if domain in _GENERIC_DOMAINS:
        return ""
    parts = domain.split(".")

    # ── Pattern 1: k12/edu marker + state code in domain structure ──
    # Handles: spring.k12.tx.us, k12.wv.us, k12.dc.gov, avsd.k12.pa.us
    if "k12" in parts:
        k12_idx = parts.index("k12")
        # State code is typically right after k12 or between k12 and TLD
        for candidate in parts[k12_idx + 1:]:
            if len(candidate) == 2 and candidate.isalpha() and candidate in _US_STATE_ABBRS:
                return candidate.upper()

    # ── Pattern 2: *.STATE.us with edu markers ──
    if len(parts) >= 3 and parts[-1] == "us":
        state_candidate = parts[-2]
        if len(state_candidate) == 2 and state_candidate in _US_STATE_ABBRS:
            return state_candidate.upper()

    # ── Pattern 3: State abbreviation embedded in domain name ──
    # Get the meaningful part of the domain (first non-prefix, non-TLD part)
    domain_root = extract_domain_root(email)
    if domain_root:
        # 3a: State abbr as suffix of domain root (harmonytx → TX)
        # Exclude ambiguous suffixes that commonly appear in school district acronyms
        _AMBIGUOUS_SUFFIXES = {"sd", "id", "in", "me", "or", "al"}  # SD=school district, ID/IN/ME/OR/AL=common word parts
        if len(domain_root) > 3:
            suffix2 = domain_root[-2:]
            if suffix2 in _US_STATE_ABBRS and suffix2 not in _AMBIGUOUS_SUFFIXES:
                # Only match if the preceding part is 3+ chars
                prefix = domain_root[:-2]
                if len(prefix) >= 3:
                    return suffix2.upper()

        # 3b: State abbr after hyphen or underscore in full domain
        full_no_tld = ".".join(parts[:-1])
        for sep in ["-", "_", "."]:
            if sep in full_no_tld:
                segments = full_no_tld.split(sep)
                for seg in segments:
                    if len(seg) == 2 and seg in _US_STATE_ABBRS:
                        return seg.upper()

    # ── Pattern 4: State name in domain ──
    domain_joined = "".join(parts[:-1])  # everything except TLD
    for state_name, abbr in _STATE_NAME_TO_ABBR.items():
        if state_name in domain_joined:
            return abbr

    # ── Pattern 5: Known city/region in domain ──
    for city, state in _CITY_TO_STATE.items():
        if city in domain_joined:
            return state

    return ""


def is_socal_domain(email: str) -> bool:
    """Check if email domain matches a known SoCal school district."""
    if not email or "@" not in email:
        return False
    domain_root = extract_domain_root(email)
    if not domain_root:
        return False
    # Check exact match in known SoCal domains
    if domain_root in KNOWN_SOCAL_DOMAIN_ROOTS:
        return True
    # Check if domain contains a known SoCal root (e.g., "myabcusd" contains "abcusd")
    for socal_root in KNOWN_SOCAL_DOMAIN_ROOTS:
        if len(socal_root) >= 4 and socal_root in domain_root:
            return True
    # Check if "-la" or "la" suffix (Los Angeles area)
    domain = email.lower().split("@")[-1]
    if "-la." in domain or domain.startswith("la") or "losangeles" in domain:
        return True
    return False


def is_student_email(email: str) -> bool:
    """
    Check if an email belongs to a student (not an educator).
    Detects: students.kleinisd.net, student.district.org,
             waltonstudent.org, cusdstudent.com, wusdstudent.us
    """
    if not email or "@" not in email:
        return False
    domain = email.lower().split("@")[-1].strip()
    # Check for "student" anywhere in the domain (covers all patterns)
    return "student" in domain


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
    if len(parts) >= 4 and parts[-1] == "us":
        # state.us domain (fixed: was parts[-2], now parts[-1])
        for p in parts:
            if p not in ("k12", "us", "pvt", "tec", "cc", "lib", "state",
                         "org", "net", "edu", "com", "gov") and len(p) > 1:
                if len(p) <= 2:
                    continue  # state code
                return p

    # Handle multi-level: staff.austinisd.org → "austinisd"
    if len(parts) >= 3:
        # Skip common prefixes (including student-related)
        prefixes = {"staff", "mail", "email", "webmail", "my", "students", "student",
                    "stu", "apps", "portal", "admin"}
        for p in parts[:-1]:  # skip only TLD, check all other parts
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
         "Los Angeles Unified" → {"losangeles", "los", "lau", "lausd"}
         "Garden Grove Unified" → {"gardengrove", "gg", "ggu", "ggusd"}
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
            # Acronym + "sd" — many districts use acronym+SD in domains
            # "Los Angeles Unified" → "lau" + "sd" → "lausd"
            # "Garden Grove Unified" → "ggu" + "sd" → "ggusd"
            if len(acronym) >= 2:
                roots.add(acronym + "sd")
                roots.add(acronym + "usd")
        # Content word acronym
        if len(content_words) >= 2:
            c_acronym = "".join(w[0] for w in content_words)
            if len(c_acronym) >= 2:
                roots.add(c_acronym)
                roots.add(c_acronym + "sd")
                roots.add(c_acronym + "usd")

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


def _match_by_email_domain(email: str, name_key: str, state: str) -> MatchResult | None:
    """Try to match by email domain root against territory districts."""
    domain_root = extract_domain_root(email)
    if not domain_root:
        return None
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
        # Fall back to first match
        if matches:
            return _record_to_result(matches[0], "district", "medium", "email_domain_ambiguous")
    return None


def match_record(
    name: str,
    *,
    email: str = "",
    city: str = "",
    state: str = "",
    email_priority: bool = False,
) -> MatchResult | None:
    """
    Match a school/district name against the Territory Master List.

    Uses tiered matching (first match wins):
      Default order: 1.Exact name → 2.Suffix-stripped → 3.Email domain → 4.City+token → 5.Containment
      email_priority=True: 1.Email domain → 2.Exact name → 3.Suffix-stripped → 4.City+token → 5.Containment

    email_priority=True is recommended when company names are self-reported and
    unreliable (e.g., Outreach/Salesforce prospects). Email domains from institutional
    accounts (.edu, .k12) are more reliable indicators of location.

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

    # When email_priority=True, try email domain FIRST (before name matching)
    if email_priority and email:
        result = _match_by_email_domain(email, name_key, state)
        if result:
            return result

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

    # ── Tier 3: Email domain match (skipped if already tried via email_priority) ──
    if email and not email_priority:
        result = _match_by_email_domain(email, name_key, state)
        if result:
            return result

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
    email_priority: bool = False,
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
        match = match_record(name, email=email, city=city_val, state=state_val,
                             email_priority=email_priority)
        results.append((rec, match))
    return results


# ─────────────────────────────────────────────
# TIER 6: CLAUDE BATCH INFERENCE
# ─────────────────────────────────────────────

def infer_locations_with_claude(
    unknowns: list[dict],
    batch_size: int = 40,
) -> dict[str, dict]:
    """
    Use Claude (Sonnet) to infer school/district state and details for
    prospects that couldn't be matched via territory data.

    Each unknown dict should have: company, email, title, name (contact name)

    Returns dict mapping company → {state, district, city, confidence, entity_type}
    Uses Scout's existing ANTHROPIC_API_KEY (same key Scout uses for everything).
    """
    import anthropic
    import json as _json
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("territory_matcher: no ANTHROPIC_API_KEY for Claude inference")
        return {}

    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    results = {}

    # Process in batches
    for i in range(0, len(unknowns), batch_size):
        batch = unknowns[i:i + batch_size]
        if not batch:
            continue

        # Build the prompt
        records_text = ""
        for idx, u in enumerate(batch, 1):
            company = u.get("company", "")
            email = u.get("email", "")
            title = u.get("title", "")
            contact = u.get("name", "")
            records_text += f"{idx}. Company: {company} | Email: {email} | Contact: {contact} | Title: {title}\n"

        prompt = f"""I need you to identify the US state and school district for each of these schools/organizations. These are K-12 education institutions.

For each record, use the company name, email domain, contact name, and title to determine:
- state: 2-letter US state code (e.g., "TX", "CA"). Use "" if truly unknown or international.
- district: the parent school district name. Use the company name itself if it IS a district.
- city: the city if you can determine it. Use "" if unknown.
- entity_type: "school" or "district"
- is_us: true if this is a US institution, false if international or non-education

CRITICAL: The email domain is the MOST reliable signal for determining location. Company names in Salesforce are self-reported and often WRONG — educators frequently pick the wrong school when signing up. Always prioritize the email domain over the company name when they conflict.

Examples of unreliable company names:
- "Corsica High School" with email @udallas.edu → this is University of Dallas in TEXAS, not Corsica HS in SD
- "wfisd.net" → Wichita Falls ISD in TEXAS regardless of what the company name says

Use your knowledge of US school districts, email domain patterns (.k12.xx.us, district-specific domains), and school naming conventions. Most US public schools have email domains that indicate their district and state.

RECORDS:
{records_text}

Respond with ONLY a JSON array, no other text. Each element:
{{"idx": 1, "state": "TX", "district": "Austin ISD", "city": "Austin", "entity_type": "school", "is_us": true}}

If you cannot determine the state at all, use "state": "" and "is_us": true (assume US unless clearly international).
For international institutions (non-.edu, non-US domains, non-US school names), use "is_us": false.
"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Parse JSON — handle markdown code blocks
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            parsed = _json.loads(text)
            for item in parsed:
                idx = item.get("idx", 0)
                if 1 <= idx <= len(batch):
                    company = batch[idx - 1].get("company", "")
                    results[company] = {
                        "state": (item.get("state") or "").strip().upper(),
                        "district": item.get("district", ""),
                        "city": item.get("city", ""),
                        "entity_type": item.get("entity_type", "school"),
                        "is_us": item.get("is_us", True),
                        "confidence": "claude_inferred",
                    }

            logger.info(f"territory_matcher: Claude inferred {len(parsed)} of {len(batch)} records (batch {i // batch_size + 1})")

        except Exception as e:
            logger.error(f"territory_matcher: Claude inference failed for batch {i // batch_size + 1}: {e}")

        # Small pause between batches
        import time as _time
        _time.sleep(1.0)

    return results
