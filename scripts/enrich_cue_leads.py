#!/usr/bin/env python3
"""
Enrich CUE 2026 conference leads:
  1. Clean: split names, strip title commas, dedup by email
  2. Flag CUE/CALIE staff
  3. Enrich: state, district/school classification, school name, district name,
     county (CA), NorCal/SoCal (CA), country
  4. Route: US by state, CA by NorCal/SoCal, Americas non-US round-robin 1/2/3,
     rest of world to Portugal rep
  5. Write enriched data to Google Sheet

Usage:
  python3 scripts/enrich_cue_leads.py
"""

import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# Python 3.9 compat: extract needed code from territory_matcher without importing
# the full module chain (which uses 3.10+ type hints). Railway runs 3.11+ so this
# only matters for local development.
def _load_territory_matcher_standalone():
    """Execute territory_matcher.py source with __future__ annotations in an isolated namespace."""
    import types as _types

    # Create minimal stub modules so territory_matcher's top-level imports don't fail
    for stub_name in ["tools", "tools.sheets_writer", "tools.csv_importer",
                       "tools.territory_data", "tools.district_prospector",
                       "tools.pipeline_tracker", "tools.lead_importer"]:
        if stub_name not in sys.modules:
            m = _types.ModuleType(stub_name)
            if stub_name == "tools":
                m.__path__ = [str(Path(__file__).resolve().parent.parent / "tools")]
            m.__package__ = stub_name.rsplit(".", 1)[0] if "." in stub_name else stub_name
            # Add dummy functions that territory_matcher might call at module level
            m.get_active_accounts = lambda **kw: []
            m.normalize_name = lambda n: n.lower().strip() if isinstance(n, str) else ""
            sys.modules[stub_name] = m

    tm_path = Path(__file__).resolve().parent.parent / "tools" / "territory_matcher.py"
    source = tm_path.read_text()
    code = compile("from __future__ import annotations\n" + source, str(tm_path), "exec")

    # Create as a proper module so dataclasses can find it via sys.modules
    mod = _types.ModuleType("tools.territory_matcher")
    mod.__file__ = str(tm_path)
    mod.__package__ = "tools"
    sys.modules["tools.territory_matcher"] = mod
    exec(code, mod.__dict__)
    return mod.__dict__

_tm = _load_territory_matcher_standalone()
extract_state_from_email = _tm["extract_state_from_email"]
extract_domain_root = _tm["extract_domain_root"]
KNOWN_SOCAL_DOMAIN_ROOTS = _tm["KNOWN_SOCAL_DOMAIN_ROOTS"]
SOCAL_COUNTIES = _tm["SOCAL_COUNTIES"]
SOCAL_CITIES = _tm["SOCAL_CITIES"]
_GENERIC_DOMAINS = _tm["_GENERIC_DOMAINS"]

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

CSV_PATH = (
    Path.home() / "Downloads"
    / "Unsorted, unfiltered Spring CUE 2026 Opt-In Attendee List - Sheet1"
    " - Unsorted, unfiltered Spring CUE 2026 Opt-In Attendee List - Sheet1.csv.csv"
)

SHEET_ID = "1lZOMTsg-W9fQvJyUuaY0GFJGo6fwy3A7PZXQ6ZVY-es"

# CUE/CALIE detection
CUE_CALIE_EMAIL_SIGNALS = ["cue.org", "capcue.org", "sgvcue.org", "calie"]
CUE_CALIE_COMPANY_SIGNALS = ["cue", "calie"]

# NorCal counties (everything in CA not in SOCAL_COUNTIES)
NORCAL_COUNTIES = {
    "alameda", "alpine", "amador", "butte", "calaveras", "colusa", "contra costa",
    "del norte", "el dorado", "fresno", "glenn", "humboldt", "inyo", "kings",
    "lake", "lassen", "madera", "marin", "mariposa", "mendocino", "merced",
    "modoc", "mono", "monterey", "napa", "nevada", "placer", "plumas",
    "sacramento", "san benito", "san francisco", "san joaquin", "san mateo",
    "santa clara", "santa cruz", "shasta", "sierra", "siskiyou", "solano",
    "sonoma", "stanislaus", "sutter", "tehama", "trinity", "tulare",
    "tuolumne", "yolo", "yuba",
}

# Non-US TLDs
INTERNATIONAL_TLDS = {
    "uk", "au", "nz", "ca", "mx", "br", "ar", "cl", "co", "pe", "ec",
    "uy", "py", "ve", "bo", "gt", "hn", "sv", "ni", "cr", "pa", "do",
    "cu", "jm", "tt", "bs", "gy", "sr", "bz", "pr", "de", "fr", "es",
    "it", "pt", "nl", "be", "ch", "at", "se", "no", "dk", "fi", "pl",
    "cz", "sk", "hu", "ro", "bg", "hr", "si", "rs", "ua", "ru",
    "jp", "kr", "cn", "tw", "hk", "sg", "th", "vn", "ph", "my", "id",
    "in", "pk", "bd", "lk", "il", "ae", "sa", "qa", "ke", "ng", "za",
    "eg", "ma", "tn", "et", "gh",
}

# Americas countries (for round robin vs Portugal rep)
AMERICAS_TLDS = {
    "ca", "mx", "br", "ar", "cl", "co", "pe", "ec", "uy", "py", "ve",
    "bo", "gt", "hn", "sv", "ni", "cr", "pa", "do", "cu", "jm", "tt",
    "bs", "gy", "sr", "bz", "pr",
}

# Foreign .edu domains
FOREIGN_EDU_DOMAINS = {".edu.sg", ".edu.au", ".edu.mx", ".edu.co", ".edu.pe",
                       ".edu.ar", ".edu.br", ".edu.pa", ".edu.hk", ".edu.tw",
                       ".ac.uk", ".ac.nz", ".ac.jp", ".ac.kr", ".ac.za",
                       ".bc.ca", ".ab.ca", ".on.ca", ".qc.ca"}

# Known CA district domain → county mapping (built from common patterns)
# We'll also use NCES data to fill this in
# Known CA domains that get mis-extracted as other states by extract_state_from_email
# These override the generic state extraction
CA_DOMAIN_OVERRIDES = {
    "oside.us": "CA",       # Oceanside USD → gets "DE" from domain parsing
    "valverde.edu": "CA",   # Val Verde USD → gets "DE"
    "alsd.org": "CA",       # Alta Loma SD → gets "AL"
    "lausd.net": "CA",      # LAUSD → gets "LA" (Louisiana)
    "wvusd.org": "CA",      # Walnut Valley USD → gets "WV"
    "romoland.net": "CA",   # Romoland → gets "ND"
    "nvside.org": "CA",     # NVSIDE
    "cvcharter.org": "CA",  # Crescent Valley Public Charter
    "lawndalesd.n.et": "CA",  # Typo in source data (.n.et instead of .net)
    "beaumontusd.k12.ca": "CA",  # Typo in source data (missing .us)
    "monet.k12.ca.us": "CA",  # Modesto City Schools
    "alvordschools.org": "CA",  # Alvord USD
    "sweetwaterschools.org": "CA",  # Sweetwater UHSD
    "riversideunified.org": "CA",  # Riverside USD
    "egusd.net": "CA",  # Elk Grove USD
    "richgrove.org": "CA",  # Richgrove SD
    "sanchezcharter.org": "CA",  # Ambassador Sanchez Charter
    "palmdalesd.org": "CA",  # Palmdale SD
    "pusd.us": "CA",  # Pasadena USD
    "apps.pusd.org": "CA",  # Pomona USD
    "srvusd.net": "CA",  # San Ramon Valley USD
    "mvla.net": "CA",  # Mountain View-Los Altos HSD
    "bhuhsd.k12.ca.us": "CA",  # Bret Harte UHSD
    "auesd.org": "CA",  # Armona Union ESD
    "janesvilleschool.org": "CA",  # Janesville Elementary
    "nlmusd.org": "CA",  # Norwalk-La Mirada USD
    "mdusd.org": "CA",  # Mt. Diablo USD
    "ycjusd.us": "CA",  # Yucaipa-Calimesa JUSD
    "muhsd.org": "CA",  # Merced UHSD
    "mercedcsd.org": "CA",  # Merced City SD
    "palihigh.org": "CA",  # Palisades Charter HS
    "gabri.org": "CA",  # Gabrielino HS
    "salinascityesd.org": "CA",  # Salinas City ESD
}

CA_DOMAIN_TO_COUNTY = {
    "lausd": "los angeles", "lacoe": "los angeles", "lbusd": "los angeles",
    "ggusd": "orange", "sausd": "orange", "iusd": "orange", "tustin": "orange",
    "capousd": "orange", "fjuhsd": "orange", "bousd": "orange", "pylusd": "orange",
    "hbuhsd": "orange", "hbcsd": "orange", "orangeusd": "orange", "ocde": "orange",
    "svusd": "orange",
    "sandi": "san diego", "sdusd": "san diego", "oceanside": "san diego",
    "carlsbad": "san diego", "escondido": "san diego", "poway": "san diego",
    "cajon": "san diego", "sweetwater": "san diego", "cvesd": "san diego",
    "nmusd": "san diego", "fallbrook": "san diego", "ramona": "san diego",
    "coronado": "san diego", "santee": "san diego", "lakeside": "san diego",
    "smusd": "san diego",
    "sbcusd": "san bernardino", "rialto": "san bernardino", "fontana": "san bernardino",
    "colton": "san bernardino", "redlands": "san bernardino", "yucaipa": "san bernardino",
    "sbcss": "san bernardino", "cuca": "san bernardino", "alsd": "san bernardino",
    "busdk12": "san bernardino", "castaicusd": "san bernardino",
    "rusd": "riverside", "cnusd": "riverside", "cjusd": "riverside",
    "mvusd": "riverside", "psusd": "riverside", "alvord": "riverside",
    "hemet": "riverside", "menifee": "riverside", "beaumont": "riverside",
    "banning": "riverside", "perris": "riverside", "rcoe": "riverside",
    "temecula": "riverside", "murrieta": "riverside", "desertsands": "riverside",
    "beaumontusd": "riverside",
    "abcusd": "los angeles", "myabcusd": "los angeles", "auhsd": "orange",
    "pusd": "los angeles",  # Pomona USD (LA county) — most common at CUE
    "bpusd": "los angeles", "ausd": "los angeles", "erusd": "los angeles",
    "wcusd": "los angeles", "lawndale": "los angeles", "centinela": "los angeles",
    "hawthorne": "los angeles", "inglewood": "los angeles", "compton": "los angeles",
    "lynwood": "los angeles", "paramount": "los angeles", "bellflower": "los angeles",
    "downey": "los angeles", "montebello": "los angeles", "burbank": "los angeles",
    "glendale": "los angeles", "pasadena": "los angeles", "arcadia": "los angeles",
    "monrovia": "los angeles", "azusa": "los angeles", "covina": "los angeles",
    "westcovina": "los angeles", "pomona": "los angeles", "claremont": "los angeles",
    "hlpusd": "los angeles", "lvusd": "los angeles", "wvusd": "los angeles",
    "bassett": "los angeles", "hacienda": "los angeles", "elrancho": "los angeles",
    "whittier": "los angeles", "sanchezcharter": "los angeles",
    "oxnard": "ventura", "oxnardsd": "ventura", "simivalleyusd": "ventura",
    "sangerusd": "fresno", "kesd": "kings", "kcusd": "kings",
    "morongousd": "san bernardino", "morongo": "san bernardino",
    "bcsd": "kern", "pbvusd": "kern",
    "sfusd": "san francisco", "suesd": "santa cruz",
    "oside": "san diego",
    "tarbut": "orange", "loomisk8": "placer", "rocklin": "placer",
    "rocklinusd": "placer",
    "tusd": "san joaquin",  # Tracy USD
    "omsd": "san bernardino",  # Ontario-Montclair
    "lancsd": "los angeles",  # Lancaster
    "parlierunified": "fresno",
    "cvcharter": "los angeles",
    "perrisesd": "riverside",
    "newarkunified": "alameda",
    "mcusd": "merced",  # Merced City USD
    "plusd": "yuba",  # Plumas Lake
    "eduhsd": "el dorado",
    "lompoc": "santa barbara", "lusd": "santa barbara",
    "ttusd": "placer",  # Tahoe Truckee actually Nevada county but close
    "njuhsd": "nevada",  # Nevada Joint Union HSD
    "glendora": "los angeles",
    "scotiaschool": "humboldt",
    "vcschools": "san joaquin",
    "cusdk12": "orange",  # Capistrano USD
    "coldspringschool": "santa barbara",
    "castaicusd": "los angeles",
    "cardiffschools": "san diego",
    "rsd": "riverside",  # Rialto/Riverside area
    "oside": "san diego",     # Oceanside USD
    "valverde": "riverside",  # Val Verde USD
    "alsd": "san bernardino", # Alta Loma SD
    "romoland": "riverside",  # Romoland
    "nvside": "san bernardino",
    "lawndalesd.n": "los angeles",  # Typo domain
    "monet": "stanislaus",  # Modesto City Schools
    "palmdalesd": "los angeles",
    "compton": "los angeles",
    "egusd": "sacramento",  # Elk Grove USD
    "richgrove": "tulare",
    "kernhigh": "kern", "khsd": "kern",
    "mdusd": "contra costa",  # Mt. Diablo USD
    "nlmusd": "los angeles",  # Norwalk-La Mirada
    "salinascityesd": "monterey", "salinascity": "monterey",
    "srvusd": "contra costa",  # San Ramon Valley USD
    "bhuhsd": "calaveras",  # Bret Harte UHSD
    "auesd": "kings",  # Armona Union ESD
    "mvla": "santa clara",  # Mountain View-Los Altos HSD
    "alvordschools": "riverside",
    "sweetwaterschools": "san diego",
    "riversideunified": "riverside",
    "pomona": "los angeles",
    "ycjusd": "san bernardino",
    "muhsd": "merced",
    "mercedcsd": "merced",
    "palihigh": "los angeles",
    "gabri": "los angeles",
    "wascohsd": "kern",
    "hightechhigh": "san diego",
    "fusd": "fresno",
    "edcoe": "el dorado",
}

# District classification keywords
DISTRICT_KEYWORDS = [
    "unified school district", "unified", "usd", "school district", "elem",
    "elementary school district", "high school district", "union school district",
    "joint union", "county office of education", "county superintendent",
    "county office", "coe", "office of education",
]
SCHOOL_KEYWORDS = [
    "elementary school", "middle school", "high school", "junior high",
    "charter school", "academy", "preparatory", "magnet", "montessori",
    "christian school", "catholic school", "day school", "episcopal school",
    "charter", "school",  # "school" singular last — most generic
]


def clean_title(title: str) -> str:
    """Remove commas and clean up title text."""
    if not title:
        return ""
    # Remove leading/trailing commas and whitespace
    t = title.strip().strip(",").strip()
    # Remove "Please select" junk
    if t.lower().startswith("please select"):
        t = t[len("please select"):].strip().strip(",").strip()
    # Remove remaining commas
    t = t.replace(",", " ").strip()
    # Collapse multiple spaces
    t = re.sub(r"\s+", " ", t)
    return t


def split_name(full_name: str) -> tuple[str, str]:
    """Split 'Lastname, Firstname' into (first, last). Handles edge cases."""
    if not full_name:
        return "", ""
    name = full_name.strip()
    if "," in name:
        parts = name.split(",", 1)
        last = parts[0].strip()
        first = parts[1].strip()
    else:
        # No comma — split by space
        parts = name.split()
        if len(parts) >= 2:
            first = parts[0]
            last = " ".join(parts[1:])
        else:
            first = name
            last = ""
    # Title case
    first = first.title() if first == first.upper() or first == first.lower() else first
    last = last.title() if last == last.upper() or last == last.lower() else last
    return first, last


def is_cue_calie(email: str, company: str) -> bool:
    """Detect CUE or CALIE staff/affiliates."""
    email_lower = email.lower()
    company_lower = company.lower()

    for signal in CUE_CALIE_EMAIL_SIGNALS:
        if signal in email_lower:
            return True

    # Company name: check for CUE/CALIE as standalone words
    # "OCCUE" = OC CUE, "CALIE" standalone, but not "excuse" or "rescued"
    for signal in CUE_CALIE_COMPANY_SIGNALS:
        # Match as standalone word or at end of another word (OCCUE, SGVCUE)
        if re.search(rf'\b{signal}\b', company_lower):
            return True
        if company_lower.endswith(signal):
            return True
        # Also match "OC CUE", "SG VCUE" etc
        if signal in company_lower.split():
            return True

    return False


def classify_org(company: str) -> tuple[str, str, str]:
    """Classify company name as district or school.
    Returns (org_type, school_name, district_name).
    """
    if not company:
        return "", "", ""

    name = company.strip()
    name_lower = name.lower()

    # Check for compound: "School Name - District Name" or "School (District)"
    # e.g. "Simons Middle School - Pomona USD"
    # e.g. "Vineyard School (Ontario-Montclair School District)"
    district_name = ""
    school_name = ""

    # Pattern: "X - Y" or "X / Y"
    for sep in [" - ", " / ", " – "]:
        if sep in name:
            parts = name.split(sep, 1)
            left, right = parts[0].strip(), parts[1].strip()
            left_lower, right_lower = left.lower(), right.lower()
            # Check which side is the district
            if any(kw in right_lower for kw in ["unified", "usd", "district", "county"]):
                school_name = left
                district_name = right
                return "school", school_name, district_name
            elif any(kw in left_lower for kw in ["unified", "usd", "district", "county"]):
                district_name = left
                school_name = right
                return "school", school_name, district_name

    # Pattern: "School Name (District Name)"
    paren_match = re.match(r'^(.+?)\s*\((.+?)\)\s*$', name)
    if paren_match:
        inner = paren_match.group(2).strip()
        outer = paren_match.group(1).strip()
        if any(kw in inner.lower() for kw in ["unified", "usd", "district", "county"]):
            return "school", outer, inner
        if any(kw in outer.lower() for kw in ["unified", "usd", "district", "county"]):
            return "school", inner, outer

    # Single entity — classify it
    # Check district keywords first (order matters per CLAUDE.md)
    for kw in DISTRICT_KEYWORDS:
        if kw in name_lower:
            return "district", "", name

    # School keywords
    for kw in SCHOOL_KEYWORDS:
        if kw in name_lower:
            return "school", name, ""

    # If it ends in common abbreviations
    if re.search(r'\b(USD|UHSD|ESD|HSD|JUHSD)\b', name, re.IGNORECASE):
        return "district", "", name

    # Default — can't tell
    return "", "", ""


def detect_country(email: str, company: str) -> tuple[str, str]:
    """Detect non-US country from email domain.
    Returns (country_code, region) where region is 'americas' or 'other'.
    """
    if not email or "@" not in email:
        return "", ""

    domain = email.lower().split("@")[-1]
    tld = domain.split(".")[-1]

    # Check foreign .edu domains first
    for fed in FOREIGN_EDU_DOMAINS:
        if domain.endswith(fed):
            # Determine country from the foreign edu domain
            country_tld = fed.split(".")[-1]
            region = "americas" if country_tld in AMERICAS_TLDS else "other"
            return country_tld.upper(), region

    # Check .ca specifically — could be Canada
    if tld == "ca":
        # If domain has .bc.ca, .ab.ca etc. it's definitely Canada
        if any(domain.endswith(f".{prov}.ca") for prov in ["bc", "ab", "on", "qc", "mb", "sk", "ns", "nb", "pe", "nl"]):
            return "CA_INTL", "americas"
        # Just .ca TLD — likely Canada
        return "CA_INTL", "americas"

    # Known international TLD
    if tld in INTERNATIONAL_TLDS:
        region = "americas" if tld in AMERICAS_TLDS else "other"
        return tld.upper(), region

    # Company name signals for international
    company_lower = company.lower()
    intl_company_keywords = {
        "japan": ("JP", "other"), "canada": ("CA_INTL", "americas"),
        "singapore": ("SG", "other"), "australia": ("AU", "other"),
        "mexico": ("MX", "americas"), "brazil": ("BR", "americas"),
    }
    for kw, (code, region) in intl_company_keywords.items():
        if kw in company_lower:
            return code, region

    return "", ""


def get_county_from_domain(email: str) -> str:
    """Try to get CA county from email domain using known mappings."""
    if not email or "@" not in email:
        return ""
    domain_root = extract_domain_root(email)
    if not domain_root:
        return ""

    # Direct lookup
    county = CA_DOMAIN_TO_COUNTY.get(domain_root, "")
    if county:
        return county

    # Check if domain root contains a known root
    for known, cty in CA_DOMAIN_TO_COUNTY.items():
        if known in domain_root or domain_root in known:
            return cty

    # k12.ca.us domains — extract the district abbreviation
    domain = email.lower().split("@")[-1]
    if ".k12.ca" in domain:
        parts = domain.split(".")
        # The district abbreviation is the first part or the part before k12
        k12_idx = parts.index("k12")
        if k12_idx > 0:
            dist_root = parts[k12_idx - 1]
            county = CA_DOMAIN_TO_COUNTY.get(dist_root, "")
            if county:
                return county

    return ""


def norcal_or_socal(county: str) -> str:
    """Given a CA county name, return NorCal or SoCal."""
    if not county:
        return ""
    county_lower = county.lower()
    if county_lower in SOCAL_COUNTIES:
        return "SoCal"
    if county_lower in NORCAL_COUNTIES:
        return "NorCal"
    return ""


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def load_and_clean(csv_path: str) -> list[dict]:
    """Load CSV, clean names/titles, dedup by email."""
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw = list(reader)

    logger.info(f"Raw rows: {len(raw)}")

    # Dedup by email — keep row with most non-empty fields
    by_email = {}
    for row in raw:
        email = row.get("Email Address", "").strip().lower()
        if not email:
            continue
        company = row.get("Company Name", "").strip()
        title = row.get("Title", "").strip()
        # Score: prefer rows with company name and non-trivial title
        score = 0
        if company:
            score += 2
        if title and title not in ['","', ",", ""]:
            score += 1
        if email not in by_email or score > by_email[email]["_score"]:
            row["_score"] = score
            by_email[email] = row

    logger.info(f"After dedup: {len(by_email)} unique emails")

    leads = []
    for email, row in by_email.items():
        full_name = row.get("Full Name", "").strip()
        first, last = split_name(full_name)
        company = row.get("Company Name", "").strip()
        title = clean_title(row.get("Title", ""))

        # Normalize ALL CAPS names
        if company == company.upper() and len(company) > 4:
            # Title case but preserve known acronyms
            company = re.sub(
                r'\b([A-Z]{2,})\b',
                lambda m: m.group(0) if len(m.group(0)) <= 5 else m.group(0).title(),
                company.title()
            )

        leads.append({
            "First Name": first,
            "Last Name": last,
            "Email": email,
            "Company Name": company,
            "Title": title,
            "State": "",
            "Org Type": "",
            "School Name": "",
            "District Name": "",
            "County": "",
            "NorCal/SoCal": "",
            "Country": "",
            "Round Robin": "",
            "CUE/CALIE Flag": "",
        })

    return leads


# Domain root → full district name (for filling in Company Name when missing)
DOMAIN_TO_DISTRICT_NAME = {
    "lausd": "Los Angeles Unified School District",
    "sandi": "San Diego Unified School District",
    "iusd": "Irvine Unified School District",
    "ggusd": "Garden Grove Unified School District",
    "sausd": "Santa Ana Unified School District",
    "orangeusd": "Orange Unified School District",
    "capousd": "Capistrano Unified School District",
    "fjuhsd": "Fullerton Joint Union High School District",
    "bousd": "Brea Olinda Unified School District",
    "pylusd": "Placentia-Yorba Linda Unified School District",
    "hbuhsd": "Huntington Beach Union High School District",
    "hbcsd": "Huntington Beach City School District",
    "svusd": "Saddleback Valley Unified School District",
    "tustin": "Tustin Unified School District",
    "auhsd": "Anaheim Union High School District",
    "sbcusd": "San Bernardino City Unified School District",
    "cnusd": "Corona-Norco Unified School District",
    "cjusd": "Colton Joint Unified School District",
    "mvusd": "Moreno Valley Unified School District",
    "psusd": "Palm Springs Unified School District",
    "rusd": "Riverside Unified School District",
    "alvord": "Alvord Unified School District",
    "hemet": "Hemet Unified School District",
    "beaumontusd": "Beaumont Unified School District",
    "perris": "Perris Union High School District",
    "perrisesd": "Perris Elementary School District",
    "rcoe": "Riverside County Office of Education",
    "desertsands": "Desert Sands Unified School District",
    "smusd": "San Marcos Unified School District",
    "lbusd": "Laguna Beach Unified School District",
    "oside": "Oceanside Unified School District",
    "pusd": "Pomona Unified School District",
    "bpusd": "Baldwin Park Unified School District",
    "erusd": "El Rancho Unified School District",
    "wcusd": "West Covina Unified School District",
    "abcusd": "ABC Unified School District",
    "wvusd": "Walnut Valley Unified School District",
    "alsd": "Alta Loma School District",
    "sfusd": "San Francisco Unified School District",
    "bcsd": "Bakersfield City School District",
    "pbvusd": "Panama-Buena Vista Union School District",
    "kesd": "Kingsburg Elementary School District",
    "omsd": "Ontario-Montclair School District",
    "lancsd": "Lancaster School District",
    "lacoe": "Los Angeles County Office of Education",
    "sbcss": "San Bernardino County Superintendent of Schools",
    "ocde": "Orange County Department of Education",
    "cuca": "Cucamonga School District",
    "morongousd": "Morongo Unified School District",
    "romoland": "Romoland Elementary School District",
    "parlierunified": "Parlier Unified School District",
    "sangerusd": "Sanger Unified School District",
    "rocklinusd": "Rocklin Unified School District",
    "lawndale": "Lawndale Elementary School District",
    "lawndalesd": "Lawndale Elementary School District",
    "euhsd": "Escondido Union High School District",
    "tvusd": "Temecula Valley Unified School District",
    "powayusd": "Poway Unified School District",
    "rbusd": "Redondo Beach Unified School District",
    "lvusd": "Las Virgenes Unified School District",
    "hlpusd": "Hacienda La Puente Unified School District",
    "glendora": "Glendora Unified School District",
    "fontana": "Fontana Unified School District",
    "rialto": "Rialto Unified School District",
    "colton": "Colton Joint Unified School District",
    "redlands": "Redlands Unified School District",
    "oxnardsd": "Oxnard School District",
    "simivalleyusd": "Simi Valley Unified School District",
    "newarkunified": "Newark Unified School District",
    "mcusd": "Merced City School District",
    "ttusd": "Tahoe Truckee Unified School District",
    "njuhsd": "Nevada Joint Union High School District",
    "castaicusd": "Castaic Union School District",
    "plusd": "Plumas Lake Elementary School District",
    "eduhsd": "El Dorado Union High School District",
    "cardiffschools": "Cardiff School District",
    "coldspringschool": "Cold Spring School District",
    "loomisk8": "Loomis Union School District",
    "vvuhsd": "Victor Valley Union High School District",
    "busdk12": "Barstow Unified School District",
    "suesd": "Soquel Union Elementary School District",
    "cusdk12": "Capistrano Unified School District",
    "ausd": "Alhambra Unified School District",
    "tusd": "Tracy Unified School District",
    # Additional districts from spot-checking
    "monet": "Modesto City Schools",
    "palmdalesd": "Palmdale School District",
    "compton": "Compton Unified School District",
    "egusd": "Elk Grove Unified School District",
    "richgrove": "Richgrove School District",
    "kernhigh": "Kern High School District",
    "khsd": "Kern High School District",
    "slane": "South Lane School District",
    "mdusd": "Mt. Diablo Unified School District",
    "nlmusd": "Norwalk-La Mirada Unified School District",
    "nvside": "Nevada Society of Innovators and Digital Educators",
    "pcoe": "Placer County Office of Education",
    "salinascityesd": "Salinas City Elementary School District",
    "salinascity": "Salinas City Elementary School District",
    "sdusd": "San Diego Unified School District",
    "sjusd": "San Jose Unified School District",
    "srvusd": "San Ramon Valley Unified School District",
    "bhuhsd": "Bret Harte Union High School District",
    "auesd": "Armona Union Elementary School District",
    "janesvilleschool": "Janesville Elementary School",
    "mvla": "Mountain View-Los Altos High School District",
    "pomona": "Pomona Unified School District",
    "riversideunified": "Riverside Unified School District",
    "alvordschools": "Alvord Unified School District",
    "sweetwaterschools": "Sweetwater Union High School District",
    "wascohsd": "Wasco Union High School District",
    "hightechhigh": "High Tech High",
    "sanchezcharter": "Ambassador Phillip V. Sanchez II Public Charter School",
    "pps": "Portland Public Schools",
    "coupeville": "Coupeville School District",
    "muhsd": "Merced Union High School District",
    "mercedcsd": "Merced City School District",
    "gabri": "Gabrielino High School",
    "ycjusd": "Yucaipa-Calimesa Joint Unified School District",
    "dishchiibikoh": "Dishchii'bikoh Community School",
    "fusd": "Fresno Unified School District",
    "edcoe": "El Dorado County Office of Education",
    "palihigh": "Palisades Charter High School",
    "visitationschool": "Visitation School",
    "iciacadmey": "ICI Academy",
    "vvuhsd": "Victor Valley Union High School District",
}

# Full-domain overrides for ambiguous domain roots (same root, different districts)
DOMAIN_FULL_TO_DISTRICT = {
    "pusd.org": "Pomona Unified School District",
    "pusd.us": "Pasadena Unified School District",
    "apps.pusd.org": "Pomona Unified School District",
    "cusd.com": "Claremont Unified School District",
    "cusdk12.org": "Calexico Unified School District",
}


def enrich_leads(leads: list[dict]) -> list[dict]:
    """Enrich leads with state, district/school, county, country, routing."""

    # Pre-pass: fill in Company Name from known domain mappings for leads missing it
    filled_from_domain = 0
    for lead in leads:
        if not lead["Company Name"]:
            domain = lead["Email"].split("@")[-1].lower() if "@" in lead["Email"] else ""
            # Check full domain first, then root
            name = DOMAIN_FULL_TO_DISTRICT.get(domain, "")
            if not name:
                root = extract_domain_root(lead["Email"])
                name = DOMAIN_TO_DISTRICT_NAME.get(root, "") if root else ""
            if name:
                lead["Company Name"] = name
                filled_from_domain += 1
    if filled_from_domain:
        logger.info(f"  Pre-fill: {filled_from_domain} leads got Company Name from known email domains")

    round_robin_counter = 0

    for lead in leads:
        email = lead["Email"]
        company = lead["Company Name"]

        # ── Flag CUE/CALIE ──
        if is_cue_calie(email, company):
            lead["CUE/CALIE Flag"] = "CUE/CALIE"

        # ── Check CA domain overrides BEFORE country detection ──
        # Catches typo domains like lawndalesd.n.et, beaumontusd.k12.ca
        domain = email.split("@")[-1].lower() if "@" in email else ""
        is_ca_override = False
        for override_domain, override_state in CA_DOMAIN_OVERRIDES.items():
            if domain == override_domain or domain.endswith("." + override_domain):
                is_ca_override = True
                break

        # ── Country detection (skip if CA override matched) ──
        if not is_ca_override:
            country_code, region = detect_country(email, company)
            if country_code:
                lead["Country"] = country_code
                # Round robin for Americas non-US
                if region == "americas":
                    round_robin_counter += 1
                    lead["Round Robin"] = str(((round_robin_counter - 1) % 3) + 1)
                elif region == "other":
                    lead["Round Robin"] = "Portugal"
                continue  # Skip US-specific enrichment

        # ── US lead: extract state ──
        lead["Country"] = "US"

        state = ""
        if is_ca_override:
            state = "CA"

        if not state:
            state = extract_state_from_email(email)

        # If no state from email, try to infer CA from known SoCal domains
        if not state:
            domain_root = extract_domain_root(email)
            if domain_root and domain_root in KNOWN_SOCAL_DOMAIN_ROOTS:
                state = "CA"

        # If still no state, check if domain root is in our CA county map
        if not state:
            if not domain_root:
                domain_root = extract_domain_root(email)
            if domain_root and domain_root in CA_DOMAIN_TO_COUNTY:
                state = "CA"

        # Many CUE leads will be CA even without clear domain signal
        # We'll mark those as needing review later

        lead["State"] = state

        # ── Classify org ──
        org_type, school_name, district_name = classify_org(company)
        lead["Org Type"] = org_type
        lead["School Name"] = school_name
        lead["District Name"] = district_name

        # ── CA-specific: county + NorCal/SoCal ──
        if state == "CA":
            county = get_county_from_domain(email)

            # Also try company name for county clues
            if not county and company:
                company_lower = company.lower()
                for city, _ in sorted(SOCAL_CITIES, key=len, reverse=True) if isinstance(SOCAL_CITIES, dict) else [(c, None) for c in sorted(SOCAL_CITIES, key=len, reverse=True)]:
                    if city in company_lower:
                        # Map city to county
                        for domain, cty in CA_DOMAIN_TO_COUNTY.items():
                            if city.replace(" ", "") in domain:
                                county = cty
                                break
                        break

            lead["County"] = county.title() if county else ""
            lead["NorCal/SoCal"] = norcal_or_socal(county)

    return leads


def resolve_unknowns_with_data(leads: list[dict]) -> list[dict]:
    """
    Multi-layered resolution using ALL available data sources (C4-style pipeline):
      Layer 1: SF domain→state lookup (cross-ref existing sheet data)
      Layer 2: Serper web search (domain search + company name search)
      Layer 3: Claude extraction from search results (not guessing — reading real web data)
      Layer 4: Claude inference for remaining (company name only, no web data)
    """
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import httpx
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    serper_key = os.environ.get("SERPER_API_KEY", "")

    # ── Layer 1: SF domain→state lookup ──
    logger.info("Layer 1: Cross-referencing SF Leads/Contacts for domain→state mappings...")
    domain_state_lookup = _build_domain_state_lookup()
    if domain_state_lookup:
        resolved_l1 = 0
        for lead in leads:
            if lead["State"] or lead["Country"] != "US":
                continue
            root = extract_domain_root(lead["Email"])
            if root and root in domain_state_lookup:
                lead["State"] = domain_state_lookup[root]["state"]
                resolved_l1 += 1
        logger.info(f"  Layer 1 resolved: {resolved_l1} leads from SF domain lookup")

    # Count remaining unknowns
    unknowns = [lead for lead in leads if not lead["State"] and lead["Country"] == "US"]
    logger.info(f"  Remaining unknowns after L1: {len(unknowns)}")

    # ── Layer 2: Serper web search ──
    if serper_key and unknowns:
        logger.info(f"Layer 2: Serper web search for {len(unknowns)} unknowns...")

        # Group by domain for deduplication
        domain_to_leads = {}
        generic_leads = []
        for lead in unknowns:
            email = lead["Email"]
            domain = email.split("@")[-1].lower() if "@" in email else ""
            if not domain or domain in _GENERIC_DOMAINS:
                generic_leads.append(lead)
            else:
                domain_to_leads.setdefault(domain, []).append(lead)

        unique_domains = list(domain_to_leads.keys())
        logger.info(f"  {len(unique_domains)} unique domains + {len(generic_leads)} generic emails")

        def _serper_search(query):
            try:
                with httpx.Client(timeout=10.0) as http:
                    resp = http.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                        json={"q": query, "num": 3},
                    )
                    if resp.status_code != 200:
                        return ""
                    data = resp.json()
                    parts = []
                    for item in data.get("organic", [])[:3]:
                        parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                    kg = data.get("knowledgeGraph", {})
                    if kg:
                        attrs = kg.get("attributes", {})
                        addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                        parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                    return "\n".join(parts) if parts else ""
            except Exception:
                return ""

        # Search 1: domain-level (deduped)
        domain_content = {}
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_map = {executor.submit(_serper_search, d): d for d in unique_domains}
            for future in as_completed(future_map):
                domain_content[future_map[future]] = future.result() or ""

        # Search 2: company name + email for leads WITH company names
        prospect_content = {}
        searchable = [l for l in unknowns if l["Company Name"] and len(l["Company Name"]) > 3]
        if searchable:
            logger.info(f"  Searching {len(searchable)} by company name + email...")
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_map = {}
                for lead in searchable:
                    query = f"{lead['Company Name']} {lead['Email']}"
                    future_map[executor.submit(_serper_search, query)] = lead["Email"]
                for future in as_completed(future_map):
                    prospect_content[future_map[future]] = future.result() or ""

        # Search 3: domain-only search for leads WITHOUT company names
        # These are the low-hanging fruit — institutional emails with no org listed
        no_company = [l for l in unknowns
                      if not l["Company Name"]
                      and l["Email"].split("@")[-1].lower() not in _GENERIC_DOMAINS]
        if no_company:
            logger.info(f"  Searching {len(no_company)} no-company leads by email domain...")
            # Dedupe — many share the same domain
            domain_to_no_company = {}
            for lead in no_company:
                domain = lead["Email"].split("@")[-1].lower()
                domain_to_no_company.setdefault(domain, []).append(lead)
            # Only search domains we haven't already searched
            new_domains = [d for d in domain_to_no_company if d not in domain_content or not domain_content[d]]
            if new_domains:
                with ThreadPoolExecutor(max_workers=20) as executor:
                    future_map = {executor.submit(_serper_search, d): d for d in new_domains}
                    for future in as_completed(future_map):
                        domain_content[future_map[future]] = future.result() or ""

        fetched = sum(1 for v in domain_content.values() if v) + sum(1 for v in prospect_content.values() if v)
        logger.info(f"  Got search results for {fetched} lookups")

        # ── Layer 3: Claude extraction from search results ──
        if api_key:
            logger.info("Layer 3: Claude extraction from search results...")
            client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

            # Build context for ALL unknowns (including those without company names)
            context_items = []
            for lead in unknowns:
                email = lead["Email"]
                domain = email.split("@")[-1].lower() if "@" in email else ""
                parts = []
                if domain and domain_content.get(domain):
                    parts.append(domain_content[domain])
                if prospect_content.get(email):
                    parts.append(prospect_content[email])
                content = "\n".join(parts)
                if content:
                    context_items.append({"lead": lead, "content": content})

            logger.info(f"  {len(context_items)} leads have search results to analyze")

            # Process in batches
            batch_size = 30
            resolved_l3 = 0
            for batch_start in range(0, len(context_items), batch_size):
                batch = context_items[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                total_batches = (len(context_items) + batch_size - 1) // batch_size

                prompt_lines = []
                for idx, item in enumerate(batch):
                    prompt_lines.append(
                        f"{idx+1}. email: {item['lead']['Email']} | company: {item['lead']['Company Name']}\n"
                        f"   Search results:\n   {item['content'][:500]}"
                    )

                prompt = f"""Analyze these education leads and their Google search results. Extract location and organization info.

IMPORTANT: Many leads have no company name listed but their email domain clearly identifies the school/district. Use the search results to determine the organization name.

For each lead, return a JSON array with objects:
- "num": line number (1-indexed)
- "state": 2-letter US state code (or "" if international/unclear)
- "county": county name (lowercase, especially for CA leads)
- "org_type": "school" or "district" or ""
- "org_name": the organization name (school or district) — fill this in even if company was blank
- "school_name": school name if the org is a school
- "district_name": parent district name
- "is_us": true/false
- "is_intl": true only if clearly international (not US)

Return ONLY the JSON array.

Leads:
{chr(10).join(prompt_lines)}"""

                try:
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()
                    bracket_start = text.find("[")
                    bracket_end = text.rfind("]")
                    if bracket_start >= 0 and bracket_end > bracket_start:
                        text = text[bracket_start:bracket_end + 1]

                    results = json.loads(text)
                    for result in results:
                        num = result.get("num", 0) - 1
                        if 0 <= num < len(batch):
                            lead = batch[num]["lead"]
                            if result.get("is_intl"):
                                lead["Country"] = "INTL"
                                resolved_l3 += 1
                                continue
                            state = result.get("state", "")
                            if state and not lead["State"]:
                                lead["State"] = state
                                resolved_l3 += 1
                            if result.get("org_type") and not lead["Org Type"]:
                                lead["Org Type"] = result["org_type"]
                            # Fill in org name as Company Name if missing
                            org_name = result.get("org_name", "")
                            if org_name and not lead["Company Name"]:
                                lead["Company Name"] = org_name
                            if result.get("school_name") and not lead["School Name"]:
                                lead["School Name"] = result["school_name"]
                            if result.get("district_name") and not lead["District Name"]:
                                lead["District Name"] = result["district_name"]
                            county = result.get("county", "")
                            if county and lead["State"] == "CA" and not lead["County"]:
                                lead["County"] = county.title()
                                lead["NorCal/SoCal"] = norcal_or_socal(county)
                except Exception as e:
                    logger.error(f"  L3 Claude error: {e}")

            logger.info(f"  Layer 3 resolved: {resolved_l3} leads from search results")

    # ── Layer 4: Claude inference for remaining (no web data, just company name) ──
    remaining = [(i, l) for i, l in enumerate(leads)
                 if not l["State"] and l["Country"] == "US" and l["Company Name"]]
    if remaining and api_key:
        logger.info(f"Layer 4: Claude inference for {len(remaining)} remaining unknowns...")
        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

        batch_size = 50
        resolved_l4 = 0
        for batch_start in range(0, len(remaining), batch_size):
            batch = remaining[batch_start:batch_start + batch_size]

            prompt_lines = []
            for idx, (i, lead) in enumerate(batch):
                prompt_lines.append(f"{idx+1}. email: {lead['Email']} | company: {lead['Company Name']}")

            prompt = f"""Analyze these education leads. Most are from a California CUE conference.
Determine US state. Mark is_us=false ONLY if clearly international.

Return JSON array: "num", "state" (2-letter), "county" (lowercase, for CA), "org_type", "school_name", "district_name", "is_us".
ONLY the JSON array, no other text.

{chr(10).join(prompt_lines)}"""

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                bracket_start = text.find("[")
                bracket_end = text.rfind("]")
                if bracket_start >= 0 and bracket_end > bracket_start:
                    text = text[bracket_start:bracket_end + 1]
                results = json.loads(text)
                for result in results:
                    num = result.get("num", 0) - 1
                    if 0 <= num < len(batch):
                        lead = batch[num][1]
                        if not result.get("is_us", True):
                            lead["Country"] = "INTL"
                            resolved_l4 += 1
                            continue
                        state = result.get("state", "")
                        if state and not lead["State"]:
                            lead["State"] = state
                            resolved_l4 += 1
                        if result.get("org_type") and not lead["Org Type"]:
                            lead["Org Type"] = result["org_type"]
                        if result.get("school_name") and not lead["School Name"]:
                            lead["School Name"] = result["school_name"]
                        if result.get("district_name") and not lead["District Name"]:
                            lead["District Name"] = result["district_name"]
                        county = result.get("county", "")
                        if county and lead["State"] == "CA" and not lead["County"]:
                            lead["County"] = county.title()
                            lead["NorCal/SoCal"] = norcal_or_socal(county)
            except Exception as e:
                logger.error(f"  L4 Claude error: {e}")

        logger.info(f"  Layer 4 resolved: {resolved_l4} leads")

    # ── Layer 5: Fill missing Company Name for institutional email domains ──
    # This catches leads where state IS set but Company Name is empty
    missing_company = [l for l in leads if not l["Company Name"]
                       and l["Email"].split("@")[-1].lower() not in _GENERIC_DOMAINS
                       and "@" in l["Email"]]
    if missing_company and serper_key:
        logger.info(f"Layer 5: Filling Company Name for {len(missing_company)} institutional-email leads...")

        # Group by domain — one search per domain, results shared across all leads
        domain_groups = {}
        for lead in missing_company:
            domain = lead["Email"].split("@")[-1].lower()
            domain_groups.setdefault(domain, []).append(lead)

        logger.info(f"  {len(domain_groups)} unique domains to search")

        # Serper search each domain
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import httpx

        def _serper_search_l5(query):
            try:
                with httpx.Client(timeout=10.0) as http:
                    resp = http.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                        json={"q": query, "num": 3},
                    )
                    if resp.status_code != 200:
                        return ""
                    data = resp.json()
                    parts = []
                    for item in data.get("organic", [])[:3]:
                        parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                    kg = data.get("knowledgeGraph", {})
                    if kg:
                        attrs = kg.get("attributes", {})
                        addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                        parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                    return "\n".join(parts) if parts else ""
            except Exception:
                return ""

        domain_results = {}
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_map = {executor.submit(_serper_search_l5, d): d for d in domain_groups}
            for future in as_completed(future_map):
                domain_results[future_map[future]] = future.result() or ""

        got_results = sum(1 for v in domain_results.values() if v)
        logger.info(f"  Got search results for {got_results}/{len(domain_groups)} domains")

        # Claude extraction — batch by domain, apply to all leads sharing that domain
        if api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

            domains_with_results = [(d, r) for d, r in domain_results.items() if r]
            batch_size = 40
            filled_l5 = 0

            for batch_start in range(0, len(domains_with_results), batch_size):
                batch = domains_with_results[batch_start:batch_start + batch_size]

                prompt_lines = []
                for idx, (domain, content) in enumerate(batch):
                    prompt_lines.append(f"{idx+1}. domain: {domain}\n   Search results: {content[:400]}")

                prompt = f"""For each email domain, identify the organization (school district, school, or company).

Return a JSON array with objects:
- "num": line number (1-indexed)
- "org_name": full organization name (e.g. "Compton Unified School District")
- "org_type": "district" or "school" or ""
- "district_name": parent district name (if org is a school)
- "state": 2-letter US state code (or "" if international)
- "county": county name lowercase (especially for CA)

Return ONLY the JSON array.

Domains:
{chr(10).join(prompt_lines)}"""

                try:
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()
                    bs = text.find("[")
                    be = text.rfind("]")
                    if bs >= 0 and be > bs:
                        text = text[bs:be + 1]
                    results = json.loads(text)

                    for result in results:
                        num = result.get("num", 0) - 1
                        if 0 <= num < len(batch):
                            domain = batch[num][0]
                            org_name = result.get("org_name", "")
                            org_type = result.get("org_type", "")
                            district_name = result.get("district_name", "")
                            state = result.get("state", "")
                            county = result.get("county", "")

                            # Apply to ALL leads sharing this domain
                            for lead in domain_groups[domain]:
                                if org_name and not lead["Company Name"]:
                                    lead["Company Name"] = org_name
                                    filled_l5 += 1
                                if org_type and not lead["Org Type"]:
                                    lead["Org Type"] = org_type
                                if district_name and not lead["District Name"]:
                                    lead["District Name"] = district_name
                                if org_type == "district" and org_name and not lead["District Name"]:
                                    lead["District Name"] = org_name
                                if org_type == "school" and org_name and not lead["School Name"]:
                                    lead["School Name"] = org_name
                                if state and not lead["State"]:
                                    lead["State"] = state
                                if county and lead.get("State") == "CA" and not lead["County"]:
                                    lead["County"] = county.title()
                                    lead["NorCal/SoCal"] = norcal_or_socal(county)
                except Exception as e:
                    logger.error(f"  L5 Claude error: {e}")

            logger.info(f"  Layer 5 filled: {filled_l5} leads got Company Name from domain search")

    # ── Final pass: resolve CA NorCal/SoCal for any that are still missing ──
    ca_unknowns = [(i, l) for i, l in enumerate(leads)
                   if l["State"] == "CA" and not l["NorCal/SoCal"] and l["Company Name"]]
    if ca_unknowns and api_key:
        logger.info(f"Final pass: resolving {len(ca_unknowns)} CA NorCal/SoCal unknowns...")
        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        batch_size = 50
        for batch_start in range(0, len(ca_unknowns), batch_size):
            batch = ca_unknowns[batch_start:batch_start + batch_size]
            prompt_lines = [f"{idx+1}. email: {l['Email']} | company: {l['Company Name']}"
                            for idx, (_, l) in enumerate(batch)]
            prompt = f"""These are California education leads. Determine the county for each.
Return JSON array: "num" (1-indexed), "county" (lowercase).

{chr(10).join(prompt_lines)}"""
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                bracket_start = text.find("[")
                bracket_end = text.rfind("]")
                if bracket_start >= 0 and bracket_end > bracket_start:
                    text = text[bracket_start:bracket_end + 1]
                results = json.loads(text)
                for result in results:
                    num = result.get("num", 0) - 1
                    if 0 <= num < len(batch):
                        lead = batch[num][1]
                        county = result.get("county", "")
                        if county and not lead["County"]:
                            lead["County"] = county.title()
                            lead["NorCal/SoCal"] = norcal_or_socal(county)
            except Exception as e:
                logger.error(f"  CA county error: {e}")

    return leads


def _fill_missing_columns(leads: list[dict]):
    """Fill School Name, District Name, Org Type from data we already have.

    For every lead:
    - If Org Type=school and School Name empty → copy from Company Name
    - If no Org Type but has Company Name → classify it
    - If Org Type=school and District Name empty → look up in NCES, or use Claude
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # Load NCES school→district mapping
    _, nces_school_to_district, _ = _load_nces_names()

    def _normalize_key(name):
        return re.sub(r'[^a-z0-9]', '', name.lower())

    filled_school = 0
    filled_org = 0

    for lead in leads:
        company = lead.get("Company Name", "")
        if not company:
            continue

        # Classify if missing
        if not lead["Org Type"]:
            org_type, school_name, district_name = classify_org(company)
            if org_type:
                lead["Org Type"] = org_type
                filled_org += 1
            if school_name and not lead["School Name"]:
                lead["School Name"] = school_name
            if district_name and not lead["District Name"]:
                lead["District Name"] = district_name

        # If school but no School Name → copy from Company
        if lead["Org Type"] == "school" and not lead["School Name"]:
            lead["School Name"] = company
            filled_school += 1

        # If school but no District Name → NCES lookup
        if lead["Org Type"] == "school" and not lead["District Name"]:
            key = _normalize_key(company)
            if key in nces_school_to_district:
                lead["District Name"] = nces_school_to_district[key]

    logger.info(f"  Filled {filled_school} School Names, classified {filled_org} Org Types from Company Name")

    # For remaining schools without district, use Claude with the info we have
    still_no_district = [l for l in leads
                         if l.get("Org Type") == "school" and not l.get("District Name")
                         and l.get("Company Name")]
    if still_no_district and api_key:
        logger.info(f"  Looking up parent district for {len(still_no_district)} schools via Claude...")
        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

        batch_size = 40
        resolved = 0
        for batch_start in range(0, len(still_no_district), batch_size):
            batch = still_no_district[batch_start:batch_start + batch_size]
            prompt_lines = []
            for idx, lead in enumerate(batch):
                state = lead.get("State", "")
                county = lead.get("County", "")
                prompt_lines.append(
                    f"{idx+1}. school: {lead['Company Name']} | state: {state} | county: {county}"
                )

            prompt = f"""For each school, identify its parent school district.

Return JSON array: "num" (1-indexed), "district_name" (full official district name).

{chr(10).join(prompt_lines)}"""

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                bs = text.find("[")
                be = text.rfind("]")
                if bs >= 0 and be > bs:
                    text = text[bs:be + 1]
                results = json.loads(text)
                for result in results:
                    num = result.get("num", 0) - 1
                    if 0 <= num < len(batch):
                        district = result.get("district_name", "")
                        if district and district.lower() != "unknown":
                            batch[num]["District Name"] = district
                            resolved += 1
            except Exception as e:
                logger.error(f"  District lookup error: {e}")

        logger.info(f"  Resolved {resolved} parent districts")


def _resolve_remaining_states(leads: list[dict]):
    """Final pass: resolve ALL remaining US leads without a state using Serper + Claude."""
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import httpx

    serper_key = os.environ.get("SERPER_API_KEY", "")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not serper_key or not api_key:
        logger.warning("  Missing SERPER_API_KEY or ANTHROPIC_API_KEY — skipping")
        return

    no_state = [l for l in leads if l.get("Country") == "US" and not l.get("State")]
    if not no_state:
        logger.info("  No remaining US leads without state")
        return

    logger.info(f"  {len(no_state)} US leads still without state")

    def _serper_search(query):
        try:
            with httpx.Client(timeout=10.0) as http:
                resp = http.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 3},
                )
                if resp.status_code != 200:
                    return ""
                data = resp.json()
                parts = []
                for item in data.get("organic", [])[:3]:
                    parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                kg = data.get("knowledgeGraph", {})
                if kg:
                    attrs = kg.get("attributes", {})
                    addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                    parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                return "\n".join(parts) if parts else ""
        except Exception:
            return ""

    # Build search queries for each lead
    queries = {}  # lead index → query
    for i, lead in enumerate(no_state):
        email = lead["Email"]
        domain = email.split("@")[-1].lower() if "@" in email else ""
        company = lead.get("Company Name", "")
        name = f"{lead.get('First Name','')} {lead.get('Last Name','')}".strip()
        title = lead.get("Title", "")

        is_generic = domain in _GENERIC_DOMAINS

        if not is_generic:
            # Institutional: search domain + company name if available
            if company:
                queries[i] = f"{company} {domain}"
            else:
                queries[i] = domain
        elif company:
            # Generic email + company: search company + name
            queries[i] = f'"{company}" {name}'
        elif name and title:
            # Generic email, no company: search name + title + educator
            queries[i] = f'"{name}" {title} educator school'
        elif name:
            queries[i] = f'"{name}" educator school district'

    logger.info(f"  Searching {len(queries)} leads...")

    # Parallel Serper search
    search_results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(_serper_search, q): i for i, q in queries.items()}
        for future in as_completed(future_map):
            idx = future_map[future]
            search_results[idx] = future.result() or ""

    got = sum(1 for v in search_results.values() if v)
    logger.info(f"  Got results for {got}/{len(queries)} searches")

    # Claude extraction in batches
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    items_with_results = [(i, no_state[i], search_results.get(i, ""))
                          for i in range(len(no_state)) if search_results.get(i)]

    batch_size = 30
    resolved = 0
    for batch_start in range(0, len(items_with_results), batch_size):
        batch = items_with_results[batch_start:batch_start + batch_size]

        prompt_lines = []
        for idx, (i, lead, content) in enumerate(batch):
            prompt_lines.append(
                f"{idx+1}. email: {lead['Email']} | company: {lead.get('Company Name','')} | "
                f"name: {lead.get('First Name','')} {lead.get('Last Name','')}\n"
                f"   Search results: {content[:500]}"
            )

        prompt = f"""Determine the US state for each lead based on search results.
Many are educators from a California CUE conference.

Return JSON array: "num" (1-indexed), "state" (2-letter US state or "" if truly unknown/international),
"county" (lowercase, for CA), "org_name" (organization name if identifiable), "org_type" ("school"/"district"/""),
"district_name", "is_intl" (true only if clearly not US).

ONLY the JSON array.

{chr(10).join(prompt_lines)}"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            bs = text.find("[")
            be = text.rfind("]")
            if bs >= 0 and be > bs:
                text = text[bs:be + 1]
            results = json.loads(text)

            for result in results:
                num = result.get("num", 0) - 1
                if 0 <= num < len(batch):
                    lead = batch[num][1]
                    if result.get("is_intl"):
                        lead["Country"] = "INTL"
                        resolved += 1
                        continue
                    state = result.get("state", "")
                    if state and state.lower() != "unknown" and len(state) == 2:
                        lead["State"] = state.upper()
                        resolved += 1
                    org_name = result.get("org_name", "")
                    if org_name and not lead["Company Name"]:
                        lead["Company Name"] = org_name
                    if result.get("org_type") and not lead["Org Type"]:
                        lead["Org Type"] = result["org_type"]
                    if result.get("district_name") and not lead["District Name"]:
                        lead["District Name"] = result["district_name"]
                    county = result.get("county", "")
                    if county and lead.get("State") == "CA" and not lead["County"]:
                        lead["County"] = county.title()
                        lead["NorCal/SoCal"] = norcal_or_socal(county)
        except Exception as e:
            logger.error(f"  Final resolve Claude error: {e}")

    logger.info(f"  Final pass resolved: {resolved} leads")


def _resolve_norcal_socal(ca_leads: list[dict]):
    """Resolve NorCal/SoCal for CA leads missing county info using Serper + Claude."""
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import httpx

    serper_key = os.environ.get("SERPER_API_KEY", "")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not serper_key or not api_key:
        return

    # First try: fill from known domain→county map
    filled = 0
    for lead in ca_leads:
        if lead.get("NorCal/SoCal"):
            continue
        root = extract_domain_root(lead["Email"])
        county = CA_DOMAIN_TO_COUNTY.get(root, "")
        if county:
            lead["County"] = county.title()
            lead["NorCal/SoCal"] = norcal_or_socal(county)
            filled += 1
    if filled:
        logger.info(f"  Filled {filled} from domain→county map")

    # Remaining
    still_unknown = [l for l in ca_leads if not l.get("NorCal/SoCal")]
    if not still_unknown:
        return

    logger.info(f"  {len(still_unknown)} still need NorCal/SoCal — searching...")

    def _serper_search(query):
        try:
            with httpx.Client(timeout=10.0) as http:
                resp = http.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    json={"q": query + " California county location", "num": 3},
                )
                if resp.status_code != 200:
                    return ""
                data = resp.json()
                parts = []
                for item in data.get("organic", [])[:3]:
                    parts.append(f"{item.get('title','')} | {item.get('snippet','')} | {item.get('link','')}")
                kg = data.get("knowledgeGraph", {})
                if kg:
                    attrs = kg.get("attributes", {})
                    addr = attrs.get("Address", "") or attrs.get("Headquarters", "")
                    parts.append(f"[KG] {kg.get('title','')} | {kg.get('description','')} | {addr}")
                return "\n".join(parts) if parts else ""
        except Exception:
            return ""

    # Build queries — use company name or email domain
    search_results = {}
    queries = {}
    for i, lead in enumerate(still_unknown):
        company = lead.get("Company Name", "")
        domain = lead["Email"].split("@")[-1].lower()
        if company:
            queries[i] = company
        elif domain not in _GENERIC_DOMAINS:
            queries[i] = domain

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(_serper_search, q): i for i, q in queries.items()}
        for future in as_completed(future_map):
            search_results[future_map[future]] = future.result() or ""

    # Claude batch for county extraction
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    items = [(i, still_unknown[i], search_results.get(i, ""))
             for i in range(len(still_unknown)) if search_results.get(i)]

    batch_size = 40
    resolved = 0
    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start:batch_start + batch_size]
        prompt_lines = []
        for idx, (i, lead, content) in enumerate(batch):
            prompt_lines.append(
                f"{idx+1}. company: {lead.get('Company Name','')} | email domain: {lead['Email'].split('@')[-1]}\n"
                f"   Search: {content[:400]}"
            )

        prompt = f"""These are California education organizations. Determine the COUNTY for each.

Return JSON array: "num" (1-indexed), "county" (lowercase California county name).

{chr(10).join(prompt_lines)}"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            bs = text.find("[")
            be = text.rfind("]")
            if bs >= 0 and be > bs:
                text = text[bs:be + 1]
            results = json.loads(text)
            for result in results:
                num = result.get("num", 0) - 1
                if 0 <= num < len(batch):
                    lead = batch[num][1]
                    county = result.get("county", "")
                    if county and county.lower() != "unknown":
                        lead["County"] = county.title()
                        lead["NorCal/SoCal"] = norcal_or_socal(county)
                        if lead["NorCal/SoCal"]:
                            resolved += 1
        except Exception as e:
            logger.error(f"  NorCal/SoCal Claude error: {e}")

    logger.info(f"  NorCal/SoCal resolved: {resolved} leads")


def _build_domain_state_lookup() -> dict:
    """Build domain_root → state lookup from SF Leads + SF Contacts + Active Accounts + Prospecting Queue."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build as gapi_build

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        return {}

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = gapi_build("sheets", "v4", credentials=creds)

    domain_state_counts = {}

    def _process_rows(rows, email_col, state_col, source):
        if len(rows) < 2:
            return
        headers = rows[0]
        try:
            email_idx = headers.index(email_col)
            state_idx = headers.index(state_col)
        except ValueError:
            return
        for row in rows[1:]:
            if len(row) <= max(email_idx, state_idx):
                continue
            email = (row[email_idx] or "").strip()
            state = (row[state_idx] or "").strip().upper()
            if not email or not state or len(state) != 2 or "@" not in email:
                continue
            root = extract_domain_root(email)
            if not root or len(root) < 3:
                continue
            domain_state_counts.setdefault(root, {})
            domain_state_counts[root][state] = domain_state_counts[root].get(state, 0) + 1

    # Read from multiple sheets
    main_sheet = os.environ.get("GOOGLE_SHEETS_ID", "")
    sf_sheet = os.environ.get("GOOGLE_SHEETS_SF_ID", main_sheet)

    tabs_to_read = [
        (sf_sheet, "'SF Leads'!A1:ZZ", "Email", "State/Province"),
        (sf_sheet, "'SF Contacts'!A1:ZZ", "Email", "Mailing State/Province"),
        (main_sheet, "'Active Accounts'!A1:ZZ", "Email", "State"),
        (main_sheet, "'Prospecting Queue'!A1:ZZ", "Email", "State"),
    ]

    for sheet_id, range_str, email_col, state_col in tabs_to_read:
        if not sheet_id:
            continue
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=range_str
            ).execute()
            rows = result.get("values", [])
            _process_rows(rows, email_col, state_col, range_str)
        except Exception:
            pass  # Tab might not exist

    # Build final lookup — pick most common state per domain
    lookup = {}
    for root, state_counts in domain_state_counts.items():
        if not state_counts:
            continue
        best_state = max(state_counts, key=state_counts.get)
        total = sum(state_counts.values())
        if total >= 1:
            lookup[root] = {"state": best_state, "count": state_counts[best_state], "total": total}

    logger.info(f"  Built domain→state lookup: {len(lookup)} domain roots from {sum(v['total'] for v in lookup.values())} records")
    return lookup


def _load_nces_names() -> tuple:
    """Load canonical district and school names from NCES territory data.
    Returns (district_names: dict[name_key → canonical_name],
             school_to_district: dict[school_name_key → district_name],
             district_set: set[canonical_name])
    """
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build as gapi_build

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    territory_id = os.environ.get("GOOGLE_SHEETS_TERRITORY_ID")
    if not creds_json or not territory_id:
        return {}, {}, set()

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = gapi_build("sheets", "v4", credentials=creds)

    district_names = {}  # normalized key → canonical name
    district_set = set()
    school_to_district = {}  # normalized school key → canonical district name

    # Load districts
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=territory_id, range="'Territory Districts'!A:B"
        ).execute()
        for row in result.get("values", [])[1:]:
            if len(row) >= 2:
                name = row[1].strip()
                key = re.sub(r'[^a-z0-9]', '', name.lower())
                district_names[key] = name
                district_set.add(name)
    except Exception:
        pass

    # Load schools with their parent districts
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=territory_id, range="'Territory Schools'!A:C"
        ).execute()
        for row in result.get("values", [])[1:]:
            if len(row) >= 3:
                school = row[1].strip()
                district = row[2].strip()
                key = re.sub(r'[^a-z0-9]', '', school.lower())
                school_to_district[key] = district
    except Exception:
        pass

    return district_names, school_to_district, district_set


def normalize_names(leads: list[dict]) -> list[dict]:
    """Normalize Company Name, District Name, School Name across all leads.

    Strategy:
    1. Load NCES canonical names as ground truth
    2. Group leads by email domain
    3. For each domain group, determine the canonical district name:
       a. Match against NCES district names
       b. Match against DOMAIN_TO_DISTRICT_NAME map
       c. Pick the most complete/common name among leads in the group
    4. For school-level leads, set School Name = company, District Name = canonical district
    5. For district-level leads, set Company Name = District Name = canonical district
    """
    logger.info("  Loading NCES territory data for name normalization...")
    nces_districts, nces_school_to_district, nces_district_set = _load_nces_names()
    logger.info(f"  NCES: {len(nces_districts)} districts, {len(nces_school_to_district)} schools")

    def _normalize_key(name):
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def _find_nces_district(name):
        """Try to match a name against NCES district data. Conservative — no substring matching."""
        if not name:
            return ""
        key = _normalize_key(name)
        # Exact match
        if key in nces_districts:
            return nces_districts[key]
        # Try with common suffixes/prefixes stripped for exact base match
        for suffix in ["elementaryschooldistrict", "schooldistrict", "unifiedschooldistrict",
                       "unionhighschooldistrict", "jointunionhighschooldistrict",
                       "unionschooldistrict", "highschooldistrict", "cityschooldistrict",
                       "countyofficeofeducation", "unified", "usd", "esd", "hsd"]:
            if key.endswith(suffix):
                base = key[:-len(suffix)]
                if len(base) >= 5:  # Need substantial base to avoid false matches
                    # Only match if NCES key STARTS with the same base AND has a district suffix
                    for nk, nv in nces_districts.items():
                        if nk.startswith(base) and len(nk) > len(base):
                            return nv
        return ""

    def _find_nces_school(name):
        """Try to match a name against NCES school data, return parent district."""
        if not name:
            return ""
        key = _normalize_key(name)
        if key in nces_school_to_district:
            return nces_school_to_district[key]
        # Partial match
        if len(key) >= 8:
            for sk, district in nces_school_to_district.items():
                if key in sk or sk in key:
                    return district
        return ""

    def _is_school_name(name):
        """Check if a name refers to an individual school (not a district)."""
        nl = name.lower()
        # Individual school indicators
        school_indicators = [
            "elementary school", "middle school", "high school", "junior high",
            "charter school", "academy", "preparatory", "magnet",
            "montessori", "k-8", "k8", "tk-8", "tk8",
            "intermediate", "preschool", "day school",
        ]
        # District indicators take priority
        district_indicators = [
            "unified", "school district", "district", "county office",
            "superintendent", "office of education",
        ]
        for d in district_indicators:
            if d in nl:
                return False
        for s in school_indicators:
            if s in nl:
                return True
        # "X Elementary" without "District"
        if re.search(r'\b(elementary|middle|high|junior)\b', nl) and "district" not in nl:
            return True
        return False

    # Group leads by email domain
    domain_groups = {}
    for lead in leads:
        if "@" not in lead["Email"]:
            continue
        domain = lead["Email"].split("@")[-1].lower()
        if domain in _GENERIC_DOMAINS:
            continue
        domain_groups.setdefault(domain, []).append(lead)

    normalized_count = 0

    for domain, group in domain_groups.items():
        # Collect all company names in this domain group
        names = [l["Company Name"] for l in group if l["Company Name"]]
        if not names:
            continue

        # Step 0: Try full-domain override first (handles pusd.org vs pusd.us etc.)
        canonical_district = DOMAIN_FULL_TO_DISTRICT.get(domain, "")

        # Step 1: Try DOMAIN_TO_DISTRICT_NAME map by domain root
        root = extract_domain_root(group[0]["Email"])
        if not canonical_district:
            canonical_district = DOMAIN_TO_DISTRICT_NAME.get(root, "")

        # Step 2: Try NCES match on each company name
        if not canonical_district:
            for name in names:
                match = _find_nces_district(name)
                if match:
                    canonical_district = match
                    break

        # Step 3: Try NCES match on the domain root — ONLY if root is 6+ chars
        # to avoid false matches like "monet" → something wrong
        if not canonical_district and root and len(root) >= 6:
            # Only match if the NCES key starts with root AND root is most of the key
            for nk, nv in nces_districts.items():
                if nk.startswith(root) and len(root) >= len(nk) * 0.6:
                    canonical_district = nv
                    break

        # Step 4: Pick the longest/most complete name among leads
        if not canonical_district:
            # Filter to district-like names (not individual schools)
            district_names_in_group = [n for n in names if not _is_school_name(n)]
            if district_names_in_group:
                canonical_district = max(district_names_in_group, key=len)
            elif names:
                canonical_district = max(names, key=len)

        if not canonical_district:
            continue

        # Apply canonical district to all leads in this domain group
        for lead in group:
            company = lead["Company Name"]

            if _is_school_name(company):
                # This lead is at a specific school — keep school name, set district
                if not lead["School Name"]:
                    lead["School Name"] = company
                # ALWAYS set District Name to canonical (overwrite inconsistent Claude output)
                lead["District Name"] = canonical_district
                lead["Company Name"] = company  # keep the school name as company
                if not lead["Org Type"]:
                    lead["Org Type"] = "school"
            else:
                # District-level or unknown — normalize to canonical district name
                if company != canonical_district:
                    lead["Company Name"] = canonical_district
                    normalized_count += 1
                # ALWAYS set District Name to canonical
                lead["District Name"] = canonical_district
                if not lead["Org Type"]:
                    lead["Org Type"] = "district"

    logger.info(f"  Normalized {normalized_count} company names to canonical district names")

    # Second pass: normalize known abbreviation-only company names (for generic email leads)
    ABBREV_TO_FULL = {
        "abcusd": "ABC Unified School District",
        "auhsd": "Anaheim Union High School District",
        "avuhsd": "Antelope Valley Union High School District",
        "bpusd": "Baldwin Park Unified School District",
        "ccsd": "Clark County School District",
        "clovis usd": "Clovis Unified School District",
        "cusd 300": "Community Unit School District 300",
        "evsc": "Evansville Vanderburgh School Corporation",
        "ewcsd": "East Whittier City School District",
        "gfusd": "Greenfield Union School District",
        "glendale sd": "Glendale Unified School District",
        "kecsd": "Kern County Superintendent of Schools",
        "kern high": "Kern High School District",
        "lacoe": "Los Angeles County Office of Education",
        "lausd": "Los Angeles Unified School District",
        "leusd": "Lake Elsinore Unified School District",
        "mdusd": "Mt. Diablo Unified School District",
        "msd of pike township": "Metropolitan School District of Pike Township",
        "nlmusd": "Norwalk-La Mirada Unified School District",
        "nvside": "Nevada Society of Innovators and Digital Educators",
        "occue": "OC CUE",
        "oc cue": "OC CUE",
        "pbvusd": "Panama-Buena Vista Union School District",
        "pcoe": "Placer County Office of Education",
        "rcoe": "Riverside County Office of Education",
        "sbcss": "San Bernardino County Superintendent of Schools",
        "sbcusd": "San Bernardino City Unified School District",
        "sdusd": "San Diego Unified School District",
        "sjusd": "San Jose Unified School District",
        "slocoe": "San Luis Obispo County Office of Education",
        "ttusd": "Tahoe Truckee Unified School District",
        "tusd": "Tracy Unified School District",
        "tvusd": "Temecula Valley Unified School District",
        "tvusd - les": "Temecula Valley Unified School District",
        "vvuhsd": "Victor Valley Union High School District",
        "walker/auhsd": "Anaheim Union High School District",
        "ycusd": "Yuba City Unified School District",
        "mercedes isd": "Mercedes Independent School District",
        "cesa 9": "Cooperative Educational Service Agency 9",
        "arvin union": "Arvin Union School District",
        "laverne": "University of La Verne",
        "icia": "ICI Academy",
    }

    abbrev_fixed = 0
    for lead in leads:
        company_key = lead["Company Name"].strip().lower()
        if company_key in ABBREV_TO_FULL:
            new_name = ABBREV_TO_FULL[company_key]
            if lead["Company Name"] != new_name:
                lead["Company Name"] = new_name
                if not lead["District Name"] or lead["District Name"].strip().lower() == company_key:
                    lead["District Name"] = new_name
                abbrev_fixed += 1

    if abbrev_fixed:
        logger.info(f"  Fixed {abbrev_fixed} abbreviation-only company names")

    return leads


def print_summary(leads: list[dict]):
    """Print enrichment summary."""
    total = len(leads)
    us = [l for l in leads if l["Country"] == "US"]
    intl = [l for l in leads if l["Country"] and l["Country"] != "US"]
    no_country = [l for l in leads if not l["Country"]]

    ca = [l for l in us if l["State"] == "CA"]
    other_states = [l for l in us if l["State"] and l["State"] != "CA"]
    no_state = [l for l in us if not l["State"]]

    socal = [l for l in ca if l["NorCal/SoCal"] == "SoCal"]
    norcal = [l for l in ca if l["NorCal/SoCal"] == "NorCal"]
    ca_unknown = [l for l in ca if not l["NorCal/SoCal"]]

    cue_calie = [l for l in leads if l["CUE/CALIE Flag"]]

    americas = [l for l in intl if l["Round Robin"] in ["1", "2", "3"]]
    portugal = [l for l in intl if l["Round Robin"] == "Portugal"]

    districts = [l for l in leads if l["Org Type"] == "district"]
    schools = [l for l in leads if l["Org Type"] == "school"]

    logger.info(f"\n{'='*50}")
    logger.info(f"ENRICHMENT SUMMARY")
    logger.info(f"{'='*50}")
    logger.info(f"Total unique leads: {total}")
    logger.info(f"CUE/CALIE flagged:  {len(cue_calie)}")
    logger.info(f"")
    logger.info(f"US leads:           {len(us)}")
    logger.info(f"  California:       {len(ca)}")
    logger.info(f"    SoCal:          {len(socal)}")
    logger.info(f"    NorCal:         {len(norcal)}")
    logger.info(f"    Unknown region: {len(ca_unknown)}")
    logger.info(f"  Other states:     {len(other_states)}")
    logger.info(f"  No state:         {len(no_state)}")
    logger.info(f"")
    logger.info(f"International:      {len(intl)}")
    logger.info(f"  Americas (RR):    {len(americas)}")
    logger.info(f"  Other (Portugal): {len(portugal)}")
    logger.info(f"No country:         {len(no_country)}")
    logger.info(f"")
    logger.info(f"Classified as district: {len(districts)}")
    logger.info(f"Classified as school:   {len(schools)}")
    logger.info(f"{'='*50}")

    # Show state distribution
    state_counts = {}
    for l in us:
        s = l["State"] or "(unknown)"
        state_counts[s] = state_counts.get(s, 0) + 1
    logger.info(f"\nUS State Distribution:")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {state}: {count}")


def write_to_csv(leads: list[dict], output_path):
    """Write enriched leads to CSV file."""
    headers = [
        "First Name", "Last Name", "Email", "Company Name", "Title",
        "State", "Country", "Org Type", "School Name", "District Name",
        "County", "NorCal/SoCal", "Round Robin", "CUE/CALIE Flag",
    ]

    # Sort same as sheet output
    def sort_key(l):
        return (
            0 if l["CUE/CALIE Flag"] else 1,
            l.get("Country", "") != "US",
            l.get("State", "") != "CA",
            {"SoCal": 0, "NorCal": 1}.get(l.get("NorCal/SoCal", ""), 2),
            l.get("State", "ZZZ"),
            l.get("Last Name", ""),
        )
    leads_sorted = sorted(leads, key=sort_key)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads_sorted)

    logger.info(f"CSV written: {output_path} ({len(leads_sorted)} rows)")


def write_to_sheet(leads: list[dict]):
    """Write enriched leads to Google Sheet."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        logger.error("GOOGLE_SERVICE_ACCOUNT_JSON not set — can't write to sheet")
        return

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)

    # Output columns
    headers = [
        "First Name", "Last Name", "Email", "Company Name", "Title",
        "State", "Country", "Org Type", "School Name", "District Name",
        "County", "NorCal/SoCal", "Round Robin", "CUE/CALIE Flag",
    ]

    # Sort: CUE/CALIE first, then by state, then by NorCal/SoCal
    def sort_key(l):
        return (
            0 if l["CUE/CALIE Flag"] else 1,
            l.get("Country", "") != "US",  # US first
            l.get("State", "") != "CA",    # CA first within US
            {"SoCal": 0, "NorCal": 1}.get(l.get("NorCal/SoCal", ""), 2),
            l.get("State", "ZZZ"),
            l.get("Last Name", ""),
        )
    leads.sort(key=sort_key)

    rows = [headers]
    for lead in leads:
        rows.append([lead.get(h, "") for h in headers])

    tab_name = "Enriched"

    # Create or clear the Enriched tab
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                for s in meta.get("sheets", [])}

    if tab_name not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        ).execute()
        logger.info(f"Created tab: {tab_name}")
    else:
        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A:Z",
        ).execute()

    # Write data
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    logger.info(f"\nWrote {len(rows)-1} leads to '{tab_name}' tab in Google Sheet")
    logger.info(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


# ─────────────────────────────────────────────
# REP ROUTING + TAB CREATION
# ─────────────────────────────────────────────

STEVEN_STATES = {"TX", "IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE"}
TOM_STATES = {"NY", "VA", "NJ", "WA", "WI", "WY", "IA", "MN", "HI", "WV", "MT", "RI",
              "ID", "SD", "NH", "DE", "ND", "ME", "AK", "DC", "VT"}
LIZ_STATES = {"FL", "NC", "CO", "GA", "SC", "UT", "AR", "AL", "LA", "KY", "MO", "MS",
              "MD", "NM", "KS", "OR", "AZ"}


def route_leads(leads: list[dict]) -> dict:
    """Route leads to rep tabs. Returns dict of rep_name → list of leads."""
    steven, tom, liz, shan, cue_calie = [], [], [], [], []
    unknown_pool = []  # for 50/50 split
    americas_pool = []  # for round-robin 3-way split

    for lead in leads:
        # CUE/CALIE excluded from all rep tabs
        if lead.get("CUE/CALIE Flag"):
            cue_calie.append(lead)
            continue

        country = lead.get("Country", "US")
        state = lead.get("State", "")
        region = lead.get("NorCal/SoCal", "")

        # Non-Americas international → Shan
        if country not in ("US", "") and lead.get("Round Robin") == "Portugal":
            shan.append(lead)
            continue

        # Americas international → pool for 3-way split
        if country not in ("US", "") and lead.get("Round Robin") in ("1", "2", "3"):
            americas_pool.append(lead)
            continue

        # US with no state → pool for 50/50 Steven/Tom
        if not state:
            unknown_pool.append(lead)
            continue

        # CA → split by NorCal/SoCal
        if state == "CA":
            if region == "SoCal":
                steven.append(lead)
            elif region == "NorCal":
                tom.append(lead)
            else:
                # Unknown region — split 50/50
                unknown_pool.append(lead)
            continue

        # Other US states
        if state in STEVEN_STATES:
            steven.append(lead)
        elif state in TOM_STATES:
            tom.append(lead)
        elif state in LIZ_STATES:
            liz.append(lead)
        else:
            # Unlisted state — goes to Steven as catch-all
            steven.append(lead)

    # Split unknown pool 50/50 between Steven and Tom
    for i, lead in enumerate(unknown_pool):
        if i % 2 == 0:
            steven.append(lead)
        else:
            tom.append(lead)

    # Split Americas international round-robin between Steven, Tom, Liz
    for i, lead in enumerate(americas_pool):
        if i % 3 == 0:
            steven.append(lead)
        elif i % 3 == 1:
            tom.append(lead)
        else:
            liz.append(lead)

    return {
        "Steven": steven,
        "Tom": tom,
        "Liz": liz,
        "Shan": shan,
        "CUE-CALIE": cue_calie,
    }


def write_rep_tabs(leads: list[dict]):
    """Route leads and write each rep's tab to Google Sheet."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        logger.error("GOOGLE_SERVICE_ACCOUNT_JSON not set")
        return

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)

    routed = route_leads(leads)

    headers = [
        "First Name", "Last Name", "Email", "Company Name", "Title",
        "State", "Country", "Org Type", "School Name", "District Name",
        "County", "NorCal/SoCal", "CUE/CALIE Flag",
    ]

    def sort_key(l):
        return (
            l.get("State", "ZZZ"),
            {"SoCal": 0, "NorCal": 1}.get(l.get("NorCal/SoCal", ""), 2),
            l.get("District Name", ""),
            l.get("Last Name", ""),
        )

    # Get existing tabs
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                for s in meta.get("sheets", [])}

    for rep_name, rep_leads in routed.items():
        tab_name = rep_name
        rep_leads.sort(key=sort_key)

        # Create tab if needed
        if tab_name not in existing:
            resp = service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
            ).execute()
            tab_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
            existing[tab_name] = tab_id
            logger.info(f"  Created tab: {tab_name}")
        else:
            tab_id = existing[tab_name]
            service.spreadsheets().values().clear(
                spreadsheetId=SHEET_ID,
                range=f"'{tab_name}'!A:Z",
            ).execute()

        # Write data
        rows = [headers]
        for lead in rep_leads:
            rows.append([lead.get(h, "") for h in headers])

        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        logger.info(f"  {tab_name}: {len(rep_leads)} leads")

        # Highlight CUE/CALIE rows in red on the CUE-CALIE tab
        if rep_name == "CUE-CALIE" and rep_leads:
            requests = [{
                "repeatCell": {
                    "range": {
                        "sheetId": tab_id,
                        "startRowIndex": 1,
                        "endRowIndex": len(rep_leads) + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers),
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {
                                "red": 1.0,
                                "green": 0.8,
                                "blue": 0.8,
                            }
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }]
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": requests},
            ).execute()

        # Freeze header row
        service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": tab_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }]},
        ).execute()

    logger.info(f"\nRep tabs written to: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


def main():
    logger.info("Loading and cleaning CUE leads...")
    leads = load_and_clean(str(CSV_PATH))

    logger.info("Enriching leads...")
    leads = enrich_leads(leads)

    logger.info("Resolving unknowns (C4-style multi-layer pipeline)...")
    resolve_unknowns_with_data(leads)

    # Re-run routing for newly resolved international leads
    round_robin_counter = sum(1 for l in leads if l["Round Robin"] in ["1", "2", "3"])
    for lead in leads:
        if lead["Country"] == "INTL" and not lead["Round Robin"]:
            round_robin_counter += 1
            lead["Round Robin"] = str(((round_robin_counter - 1) % 3) + 1)

    # ── Final state resolution: catch ALL remaining no-state leads ──
    logger.info("Final state resolution pass...")
    _resolve_remaining_states(leads)

    # ── NorCal/SoCal resolution for remaining CA unknowns ──
    ca_no_region = [l for l in leads if l.get("State") == "CA" and not l.get("NorCal/SoCal")]
    if ca_no_region:
        logger.info(f"Resolving NorCal/SoCal for {len(ca_no_region)} CA leads...")
        _resolve_norcal_socal(ca_no_region)

    # ── Normalize company names across leads sharing the same domain ──
    logger.info("Normalizing company/district/school names...")
    leads = normalize_names(leads)

    # ── Final completeness pass: fill School Name, District Name, Org Type from existing data ──
    logger.info("Final completeness pass...")
    _fill_missing_columns(leads)

    # Clean up: Claude sometimes returns "unknown" or "Unknown" as state
    for lead in leads:
        if lead["State"] and lead["State"].lower() == "unknown":
            lead["State"] = ""
        if lead["Country"] and lead["Country"].lower() == "unknown":
            lead["Country"] = "US"

    print_summary(leads)

    # Write to CSV first (always works), then try sheet
    csv_out = Path.home() / "Downloads" / "CUE_2026_Enriched.csv"
    write_to_csv(leads, csv_out)

    logger.info("\nWriting to Google Sheet...")
    try:
        write_to_sheet(leads)
    except Exception as e:
        logger.error(f"Sheet write failed: {e}")
        logger.info(f"CSV output saved to: {csv_out}")

    logger.info("\nCreating rep tabs...")
    try:
        write_rep_tabs(leads)
    except Exception as e:
        logger.error(f"Rep tab write failed: {e}")


if __name__ == "__main__":
    main()
