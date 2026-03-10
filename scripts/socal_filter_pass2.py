"""
SoCal Filter — Pass 2: Resolve uncertain records with deeper matching.

Strategies:
  1. Parent Account → CDE district → county
  2. City names embedded in company/account name → county
  3. Deeper email domain matching (k12, .edu, org with district roots)
  4. California city name extraction from any text field
  5. Cross-reference all available fields together
"""

import csv
import io
import os
import re
from collections import defaultdict

SOCAL_COUNTIES = {
    "los angeles", "san diego", "orange", "riverside", "san bernardino",
    "kern", "ventura", "santa barbara", "san luis obispo", "imperial",
}

CDE_SCHOOLS_FILE = "/tmp/cde_schools.txt"
CDE_DISTRICTS_FILE = "/tmp/cde_districts.txt"


def _normalize(name: str) -> str:
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def build_lookups():
    """Build all lookup tables from CDE data."""
    school_to_county = {}
    district_to_county = {}
    zip_to_county = {}
    city_to_county_counts = defaultdict(lambda: defaultdict(int))
    school_to_district = {}

    with open(CDE_SCHOOLS_FILE, encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            status = row.get("StatusType", "").strip()
            if status not in ("Active", "Pending"):
                continue
            county = row.get("County", "").strip()
            school = row.get("School", "").strip()
            district = row.get("District", "").strip()
            city = row.get("City", "").strip()
            zipcode = row.get("Zip", "").strip()
            if not county:
                continue
            if school and school != "No Data":
                key = _normalize(school)
                if key:
                    school_to_county[key] = county
                    school_to_district[key] = district
            if district:
                key = _normalize(district)
                if key:
                    district_to_county[key] = county
            if zipcode:
                z5 = zipcode.split("-")[0].strip()
                if len(z5) == 5 and z5.isdigit():
                    zip_to_county[z5] = county
            if city:
                city_to_county_counts[city.lower().strip()][county] += 1

    with open(CDE_DISTRICTS_FILE, encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            status = row.get("StatusType", "").strip()
            if status not in ("Active", "Pending"):
                continue
            county = row.get("County", "").strip()
            district = row.get("District", "").strip()
            city = row.get("City", "").strip()
            zipcode = row.get("Zip", "").strip()
            if county and district:
                key = _normalize(district)
                if key:
                    district_to_county[key] = county
            if zipcode:
                z5 = zipcode.split("-")[0].strip()
                if len(z5) == 5 and z5.isdigit():
                    zip_to_county[z5] = county
            if city and county:
                city_to_county_counts[city.lower().strip()][county] += 1

    city_to_county = {}
    for city, counties in city_to_county_counts.items():
        city_to_county[city] = max(counties, key=counties.get)

    return school_to_county, district_to_county, zip_to_county, city_to_county, school_to_district


def build_ca_city_list(city_to_county):
    """
    Build a comprehensive CA city list for extracting city names from text.
    Sort by length descending so longer city names match first (e.g., "San Luis Obispo" before "San").
    """
    # Add well-known CA cities/communities not in CDE data (private school areas)
    extra_cities = {
        # SoCal
        "aliso viejo": "Orange", "anaheim": "Orange", "brea": "Orange",
        "buena park": "Orange", "costa mesa": "Orange", "cypress": "Orange",
        "dana point": "Orange", "fountain valley": "Orange", "fullerton": "Orange",
        "garden grove": "Orange", "huntington beach": "Orange", "irvine": "Orange",
        "la habra": "Orange", "laguna beach": "Orange", "laguna hills": "Orange",
        "laguna niguel": "Orange", "laguna woods": "Orange",
        "lake forest": "Orange", "los alamitos": "Orange", "mission viejo": "Orange",
        "newport beach": "Orange", "orange": "Orange", "placentia": "Orange",
        "rancho santa margarita": "Orange", "san clemente": "Orange",
        "san juan capistrano": "Orange", "santa ana": "Orange", "seal beach": "Orange",
        "stanton": "Orange", "tustin": "Orange", "villa park": "Orange",
        "westminster": "Orange", "yorba linda": "Orange",

        "alhambra": "Los Angeles", "arcadia": "Los Angeles", "azusa": "Los Angeles",
        "baldwin park": "Los Angeles", "bell gardens": "Los Angeles", "bellflower": "Los Angeles",
        "beverly hills": "Los Angeles", "burbank": "Los Angeles", "calabasas": "Los Angeles",
        "carson": "Los Angeles", "cerritos": "Los Angeles", "claremont": "Los Angeles",
        "compton": "Los Angeles", "covina": "Los Angeles", "culver city": "Los Angeles",
        "diamond bar": "Los Angeles", "downey": "Los Angeles", "duarte": "Los Angeles",
        "el monte": "Los Angeles", "el segundo": "Los Angeles", "encino": "Los Angeles",
        "gardena": "Los Angeles", "glendale": "Los Angeles", "glendora": "Los Angeles",
        "hawthorne": "Los Angeles", "hermosa beach": "Los Angeles",
        "hollywood": "Los Angeles", "inglewood": "Los Angeles", "la canada": "Los Angeles",
        "la mirada": "Los Angeles", "la verne": "Los Angeles", "lakewood": "Los Angeles",
        "lancaster": "Los Angeles", "lawndale": "Los Angeles",
        "long beach": "Los Angeles", "los angeles": "Los Angeles",
        "malibu": "Los Angeles", "manhattan beach": "Los Angeles", "monrovia": "Los Angeles",
        "montebello": "Los Angeles", "monterey park": "Los Angeles",
        "north hollywood": "Los Angeles", "northridge": "Los Angeles",
        "norwalk": "Los Angeles", "palmdale": "Los Angeles", "palos verdes": "Los Angeles",
        "rancho palos verdes": "Los Angeles",
        "pasadena": "Los Angeles", "pico rivera": "Los Angeles", "pomona": "Los Angeles",
        "redondo beach": "Los Angeles", "rosemead": "Los Angeles",
        "san dimas": "Los Angeles", "san fernando": "Los Angeles",
        "san pedro": "Los Angeles", "santa clarita": "Los Angeles",
        "santa monica": "Los Angeles", "sherman oaks": "Los Angeles",
        "south gate": "Los Angeles", "south pasadena": "Los Angeles",
        "studio city": "Los Angeles", "sylmar": "Los Angeles",
        "tarzana": "Los Angeles", "temple city": "Los Angeles",
        "torrance": "Los Angeles", "valencia": "Los Angeles", "van nuys": "Los Angeles",
        "west covina": "Los Angeles", "west hills": "Los Angeles",
        "west hollywood": "Los Angeles", "westlake village": "Los Angeles",
        "whittier": "Los Angeles", "wilmington": "Los Angeles", "woodland hills": "Los Angeles",
        "watts": "Los Angeles", "chatsworth": "Los Angeles", "reseda": "Los Angeles",
        "canoga park": "Los Angeles", "panorama city": "Los Angeles",
        "sun valley": "Los Angeles", "tujunga": "Los Angeles",

        "carlsbad": "San Diego", "chula vista": "San Diego", "coronado": "San Diego",
        "del mar": "San Diego", "el cajon": "San Diego", "encinitas": "San Diego",
        "escondido": "San Diego", "la jolla": "San Diego", "la mesa": "San Diego",
        "national city": "San Diego", "oceanside": "San Diego", "poway": "San Diego",
        "ramona": "San Diego", "san marcos": "San Diego", "santee": "San Diego",
        "solana beach": "San Diego", "vista": "San Diego",

        "beaumont": "Riverside", "cathedral city": "Riverside", "coachella": "Riverside",
        "corona": "Riverside", "hemet": "Riverside", "indio": "Riverside",
        "jurupa valley": "Riverside", "lake elsinore": "Riverside",
        "menifee": "Riverside", "moreno valley": "Riverside", "murrieta": "Riverside",
        "norco": "Riverside", "palm desert": "Riverside", "palm springs": "Riverside",
        "perris": "Riverside", "temecula": "Riverside", "wildomar": "Riverside",

        "apple valley": "San Bernardino", "barstow": "San Bernardino",
        "big bear": "San Bernardino", "chino": "San Bernardino",
        "chino hills": "San Bernardino", "colton": "San Bernardino",
        "fontana": "San Bernardino", "hesperia": "San Bernardino",
        "highland": "San Bernardino", "loma linda": "San Bernardino",
        "montclair": "San Bernardino", "ontario": "San Bernardino",
        "rancho cucamonga": "San Bernardino", "redlands": "San Bernardino",
        "rialto": "San Bernardino", "san bernardino": "San Bernardino",
        "upland": "San Bernardino", "victorville": "San Bernardino",
        "yucaipa": "San Bernardino",

        "bakersfield": "Kern", "delano": "Kern", "ridgecrest": "Kern",
        "tehachapi": "Kern", "arvin": "Kern", "wasco": "Kern", "shafter": "Kern",

        "camarillo": "Ventura", "fillmore": "Ventura", "moorpark": "Ventura",
        "newbury park": "Ventura", "ojai": "Ventura", "oxnard": "Ventura",
        "port hueneme": "Ventura", "santa paula": "Ventura",
        "simi valley": "Ventura", "thousand oaks": "Ventura",
        "ventura": "Ventura", "westlake": "Ventura",

        "goleta": "Santa Barbara", "lompoc": "Santa Barbara",
        "santa barbara": "Santa Barbara", "santa maria": "Santa Barbara",
        "solvang": "Santa Barbara", "carpinteria": "Santa Barbara",

        "arroyo grande": "San Luis Obispo", "atascadero": "San Luis Obispo",
        "grover beach": "San Luis Obispo", "morro bay": "San Luis Obispo",
        "paso robles": "San Luis Obispo", "pismo beach": "San Luis Obispo",
        "san luis obispo": "San Luis Obispo",

        "brawley": "Imperial", "calexico": "Imperial", "el centro": "Imperial",
        "holtville": "Imperial", "imperial": "Imperial",

        # Major NorCal cities
        "san francisco": "San Francisco", "oakland": "Alameda",
        "berkeley": "Alameda", "fremont": "Alameda", "hayward": "Alameda",
        "san jose": "Santa Clara", "sunnyvale": "Santa Clara",
        "mountain view": "Santa Clara", "palo alto": "Santa Clara",
        "cupertino": "Santa Clara", "santa clara": "Santa Clara",
        "sacramento": "Sacramento", "elk grove": "Sacramento",
        "fresno": "Fresno", "modesto": "Stanislaus",
        "stockton": "San Joaquin", "turlock": "Stanislaus",
        "san mateo": "San Mateo", "redwood city": "San Mateo",
        "daly city": "San Mateo", "south san francisco": "San Mateo",
        "walnut creek": "Contra Costa", "concord": "Contra Costa",
        "richmond": "Contra Costa", "antioch": "Contra Costa",
        "santa rosa": "Sonoma", "petaluma": "Sonoma",
        "napa": "Napa", "vallejo": "Solano",
        "san rafael": "Marin", "novato": "Marin",
        "santa cruz": "Santa Cruz", "salinas": "Monterey",
        "visalia": "Tulare", "porterville": "Tulare",
        "merced": "Merced", "chico": "Butte", "redding": "Shasta",
        "eureka": "Humboldt", "davis": "Yolo",
        "roseville": "Placer", "folsom": "Sacramento",
        "vacaville": "Solano", "fairfield": "Solano",
        "pleasanton": "Alameda", "livermore": "Alameda",
        "dublin": "Alameda", "milpitas": "Santa Clara",
        "gilroy": "Santa Clara", "morgan hill": "Santa Clara",
        "campbell": "Santa Clara", "los gatos": "Santa Clara",
        "saratoga": "Santa Clara",
    }

    # Merge CDE cities + extra cities
    all_cities = dict(city_to_county)
    all_cities.update(extra_cities)

    # Sort by name length descending (match longer names first)
    sorted_cities = sorted(all_cities.items(), key=lambda x: len(x[0]), reverse=True)
    # Filter out very short city names that cause false matches
    sorted_cities = [(c, county) for c, county in sorted_cities if len(c) >= 4]

    return sorted_cities


def extract_city_from_text(text, sorted_cities):
    """Try to find a city name embedded in text."""
    if not text:
        return None, None
    text_lower = text.lower()
    # Normalize punctuation for matching
    text_clean = re.sub(r"[^\w\s]", " ", text_lower)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    for city_name, county in sorted_cities:
        # Check if city name appears as a word boundary match in the text
        # Use word boundary to avoid partial matches like "orange" in "orangewood"
        pattern = r'\b' + re.escape(city_name) + r'\b'
        if re.search(pattern, text_clean):
            return county, city_name
    return None, None


def match_parent_account(parent_account, district_to_county):
    """Match Parent Account field against CDE districts."""
    if not parent_account:
        return None, None
    normalized = _normalize(parent_account)
    if not normalized:
        return None, None

    # Exact match
    if normalized in district_to_county:
        return district_to_county[normalized], f"parent account exact match '{parent_account}'"

    # Strip suffixes and try again
    suffixes = [
        "unified school district", "unified", "school district",
        "union school district", "elementary school district",
        "high school district", "union high school district",
        "joint union high school district", "joint unified school district",
    ]
    stripped = normalized
    for s in sorted(suffixes, key=len, reverse=True):
        if stripped.endswith(s):
            stripped = stripped[:-len(s)].strip()
            break

    if stripped:
        for dist, county in district_to_county.items():
            dist_stripped = dist
            for s in sorted(suffixes, key=len, reverse=True):
                if dist_stripped.endswith(s):
                    dist_stripped = dist_stripped[:-len(s)].strip()
                    break
            if stripped == dist_stripped:
                return county, f"parent account stripped match '{parent_account}'"

    return None, None


def deeper_email_match(email, district_to_county, sorted_cities):
    """
    Deeper email domain matching:
    - .k12.ca.us domains
    - .edu domains with CA institution names
    - Domain roots containing city names
    - Domain roots matching district abbreviations
    """
    if not email or "@" not in email:
        return None, None

    domain = email.split("@")[1].lower().strip()
    generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
               "aol.com", "icloud.com", "me.com", "live.com", "msn.com",
               "comcast.net", "sbcglobal.net", "att.net", "verizon.net",
               "charter.net", "cox.net"}
    if domain in generic:
        return None, None

    domain_root = domain.split(".")[0]

    # k12.ca.us pattern: subdomain.k12.ca.us
    if domain.endswith(".k12.ca.us"):
        subdomain = domain.replace(".k12.ca.us", "")
        # Try matching subdomain against districts more loosely
        for dist, county in district_to_county.items():
            # Build possible abbreviation from district name
            words = dist.split()
            sig_words = [w for w in words if w not in ("of", "the", "and", "county", "office", "education",
                                                       "unified", "school", "district", "elementary",
                                                       "high", "union", "joint")]
            if sig_words:
                abbrev = "".join(w[0] for w in sig_words)
                if subdomain == abbrev:
                    return county, f"k12 abbreviation '{subdomain}' = '{dist}'"
                # Also try first word
                if subdomain == sig_words[0]:
                    return county, f"k12 root '{subdomain}' = '{dist}'"
                # Try concatenation of first two words
                if len(sig_words) >= 2 and subdomain == sig_words[0] + sig_words[1]:
                    return county, f"k12 concat '{subdomain}' = '{dist}'"

    # Check for city name in domain
    for city_name, county in sorted_cities:
        if len(city_name) >= 5:  # only longer city names to avoid false matches
            city_nodash = city_name.replace(" ", "")
            if city_nodash in domain_root or domain_root in city_nodash:
                if len(domain_root) >= 4 and len(city_nodash) >= 5:
                    return county, f"city in domain '{domain}' ~ '{city_name}'"

    # Check for location hints in domain parts
    # e.g., stodiliaschool-la.org → "la" at end
    parts = re.split(r"[-_.]", domain)
    location_abbrevs = {
        "la": "Los Angeles", "sd": "San Diego", "oc": "Orange",
        "sb": "San Bernardino", "rv": "Riverside", "slo": "San Luis Obispo",
    }
    # Only check if abbrev is a distinct part (not embedded)
    for part in parts:
        if part in location_abbrevs:
            return location_abbrevs[part], f"domain location abbrev '{part}' in '{domain}'"

    return None, None


def process_uncertain(input_path, output_path, file_type,
                      school_to_county, district_to_county, zip_to_county,
                      city_to_county, school_to_district, sorted_cities):
    """Re-process uncertain records with deeper matching."""

    if file_type == "leads":
        company_col = "Company / Account"
        district_col = "District Name"
        city_col = "City"
        zip_col = "Zip/Postal Code"
        email_col = "Email"
        parent_col = None
    else:
        company_col = "Account Name"
        district_col = "District Name"
        city_col = "Mailing City"
        zip_col = "Mailing Zip/Postal Code"
        email_col = "Email"
        parent_col = "Parent Account"

    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        all_rows = list(reader)

    # Separate already-resolved from uncertain
    resolved = [r for r in all_rows if r.get("SoCal") != "Uncertain"]
    uncertain = [r for r in all_rows if r.get("SoCal") == "Uncertain"]

    print(f"\n{'='*60}")
    print(f"Pass 2: {file_type.upper()} — {len(uncertain)} uncertain records")
    print(f"{'='*60}")

    tier_counts = {"parent_acct": 0, "city_in_name": 0, "deeper_email": 0,
                   "city_in_domain": 0, "still_uncertain": 0}
    newly_socal = 0
    newly_norcal = 0

    for row in uncertain:
        company = row.get(company_col, "").strip()
        district = row.get(district_col, "").strip()
        city = row.get(city_col, "").strip()
        zipcode = row.get(zip_col, "").strip()
        email = row.get(email_col, "").strip()
        parent = row.get(parent_col, "").strip() if parent_col else ""

        county = None
        method = None

        # Strategy 1: Parent Account → CDE district
        if not county and parent:
            county, method = match_parent_account(parent, district_to_county)
            if county:
                tier_counts["parent_acct"] += 1

        # Strategy 2: Extract city name from company/account name
        if not county:
            county, city_found = extract_city_from_text(company, sorted_cities)
            if county:
                method = f"city '{city_found}' in company name"
                tier_counts["city_in_name"] += 1

        # Strategy 2b: Extract city name from district name
        if not county and district:
            county, city_found = extract_city_from_text(district, sorted_cities)
            if county:
                method = f"city '{city_found}' in district name"
                tier_counts["city_in_name"] += 1

        # Strategy 2c: Extract city name from parent account
        if not county and parent:
            county, city_found = extract_city_from_text(parent, sorted_cities)
            if county:
                method = f"city '{city_found}' in parent account"
                tier_counts["city_in_name"] += 1

        # Strategy 3: Deeper email domain matching
        if not county and email:
            county, method = deeper_email_match(email, district_to_county, sorted_cities)
            if county:
                tier_counts["deeper_email"] += 1

        # Strategy 4: Extract city from email domain name
        if not county and email and "@" in email:
            domain = email.split("@")[1].lower()
            domain_root = domain.split(".")[0]
            # Try domain root as potential org name against company
            # e.g., @bishopamat.org — check if "amat" relates to a location
            # This is too loose, skip for now

        if county:
            row["County"] = county
            row["County_Method"] = f"pass2: {method}"
            if county.lower() in SOCAL_COUNTIES:
                row["SoCal"] = "Yes"
                newly_socal += 1
            else:
                row["SoCal"] = "No"
                newly_norcal += 1
        else:
            tier_counts["still_uncertain"] += 1

    # Combine resolved + updated uncertain
    all_updated = resolved + uncertain

    # Write output: keep SoCal + Uncertain, remove NorCal
    kept = [r for r in all_updated if r["SoCal"] != "No"]
    removed = [r for r in all_updated if r["SoCal"] == "No"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    norcal_path = output_path.replace(".csv", "_NORCAL_REMOVED.csv")
    with open(norcal_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(removed)

    still_uncertain = tier_counts["still_uncertain"]
    print(f"\n  Pass 2 resolution:")
    print(f"    Parent account match:  {tier_counts['parent_acct']:>5}")
    print(f"    City in name:          {tier_counts['city_in_name']:>5}")
    print(f"    Deeper email match:    {tier_counts['deeper_email']:>5}")
    print(f"    Still uncertain:       {still_uncertain:>5}")
    print(f"\n  Pass 2 results:")
    print(f"    Newly confirmed SoCal: {newly_socal:>5}")
    print(f"    Newly confirmed NorCal:{newly_norcal:>5}")
    print(f"    Still uncertain:       {still_uncertain:>5}")
    print(f"\n  Final output:")
    socal_total = sum(1 for r in kept if r["SoCal"] == "Yes")
    uncertain_total = sum(1 for r in kept if r["SoCal"] == "Uncertain")
    print(f"    SoCal:     {socal_total:>6,}")
    print(f"    Uncertain: {uncertain_total:>6,}")
    print(f"    Total kept:{len(kept):>6,} → {output_path}")
    print(f"    Removed:   {len(removed):>6,} → {norcal_path}")

    return {
        "total": len(all_updated),
        "socal": socal_total,
        "norcal": len(removed),
        "uncertain": uncertain_total,
        "kept": len(kept),
        "newly_resolved": newly_socal + newly_norcal,
    }


def main():
    print("=" * 60)
    print("SoCal Filter — Pass 2 (Deeper Matching)")
    print("=" * 60)

    # Build lookups
    school_to_county, district_to_county, zip_to_county, city_to_county, school_to_district = build_lookups()
    sorted_cities = build_ca_city_list(city_to_county)
    print(f"City lookup: {len(sorted_cities)} cities/communities")

    # Process Leads
    leads_result = process_uncertain(
        input_path="/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv",
        output_path="/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv",
        file_type="leads",
        school_to_county=school_to_county,
        district_to_county=district_to_county,
        zip_to_county=zip_to_county,
        city_to_county=city_to_county,
        school_to_district=school_to_district,
        sorted_cities=sorted_cities,
    )

    # Process Contacts
    contacts_result = process_uncertain(
        input_path="/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv",
        output_path="/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv",
        file_type="contacts",
        school_to_county=school_to_county,
        district_to_county=district_to_county,
        zip_to_county=zip_to_county,
        city_to_county=city_to_county,
        school_to_district=school_to_district,
        sorted_cities=sorted_cities,
    )

    # Final summary
    print("\n" + "=" * 60)
    print("PASS 2 FINAL SUMMARY")
    print("=" * 60)
    print(f"\nLeads:    {leads_result['socal']:,} SoCal + {leads_result['uncertain']:,} uncertain = {leads_result['kept']:,} kept | {leads_result['norcal']:,} NorCal removed")
    print(f"Contacts: {contacts_result['socal']:,} SoCal + {contacts_result['uncertain']:,} uncertain = {contacts_result['kept']:,} kept | {contacts_result['norcal']:,} NorCal removed")
    print(f"\nNewly resolved: {leads_result['newly_resolved'] + contacts_result['newly_resolved']} records")


if __name__ == "__main__":
    main()
