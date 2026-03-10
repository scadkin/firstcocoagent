"""
SoCal Filter — Determine county for CA leads/contacts using CDE school directory.

Tiers:
  1. Company/Account name → CDE school or district name → County
  2. Zip code → County (from CDE data)
  3. City → County (from CDE data)
  4. Email domain → District → County
  5. Mark as "Uncertain"

Outputs: filtered CSVs with County + SoCal columns added.
"""

import csv
import io
import os
import re
import sys
from collections import defaultdict

# ── SoCal counties (Steven's territory) ──
SOCAL_COUNTIES = {
    "los angeles", "san diego", "orange", "riverside", "san bernardino",
    "kern", "ventura", "santa barbara", "san luis obispo", "imperial",
}

CDE_SCHOOLS_FILE = "/tmp/cde_schools.txt"
CDE_DISTRICTS_FILE = "/tmp/cde_districts.txt"


# ─────────────────────────────────────────────
# BUILD LOOKUP TABLES FROM CDE DATA
# ─────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)  # replace punctuation with space
    name = re.sub(r"\s+", " ", name).strip()
    return name


def build_lookups():
    """Build all lookup tables from CDE data files."""
    # School name → county (active schools only)
    school_to_county = {}
    # District name → county
    district_to_county = {}
    # Zip (5-digit) → county
    zip_to_county = {}
    # City (lowercase) → county (may have conflicts — use most common)
    city_county_counts = defaultdict(lambda: defaultdict(int))
    # School name → district name (for cross-referencing)
    school_to_district = {}

    # Load schools
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

            # School name → county
            if school and school != "No Data":
                key = _normalize(school)
                if key:
                    school_to_county[key] = county
                    school_to_district[key] = district

            # District name → county
            if district:
                key = _normalize(district)
                if key:
                    district_to_county[key] = county

            # Zip → county (take first 5 digits)
            if zipcode:
                z5 = zipcode.strip().split("-")[0].strip()
                if len(z5) == 5 and z5.isdigit():
                    zip_to_county[z5] = county

            # City → county frequency
            if city:
                city_county_counts[city.lower().strip()][county] += 1

    # Load districts file too (has some districts not in schools file)
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
                z5 = zipcode.strip().split("-")[0].strip()
                if len(z5) == 5 and z5.isdigit():
                    zip_to_county[z5] = county

            if city and county:
                city_county_counts[city.lower().strip()][county] += 1

    # Resolve city → most common county
    city_to_county = {}
    for city, counties in city_county_counts.items():
        city_to_county[city] = max(counties, key=counties.get)

    print(f"Lookup tables built:")
    print(f"  Schools:   {len(school_to_county):,} names")
    print(f"  Districts: {len(district_to_county):,} names")
    print(f"  Zip codes: {len(zip_to_county):,}")
    print(f"  Cities:    {len(city_to_county):,}")

    return school_to_county, district_to_county, zip_to_county, city_to_county, school_to_district


# ─────────────────────────────────────────────
# EMAIL DOMAIN → DISTRICT MAPPING
# ─────────────────────────────────────────────

def build_domain_to_county(district_to_county):
    """
    Build email domain → county mapping from district names.
    e.g., "lausd" from @lausd.net → Los Angeles Unified → Los Angeles
    """
    domain_hints = {}
    for dist_name, county in district_to_county.items():
        # Extract likely domain root from district name
        # "los angeles unified school district" → try "lausd", "losangeles", etc.
        words = dist_name.split()

        # Try acronym (first letter of each significant word)
        sig_words = [w for w in words if w not in ("of", "the", "and", "county", "office", "education")]
        if len(sig_words) >= 2:
            acronym = "".join(w[0] for w in sig_words)
            if len(acronym) >= 3:
                domain_hints[acronym] = county

        # Try first word + "usd"/"unified" patterns
        if words:
            domain_hints[words[0]] = county
            # Join first two words
            if len(words) >= 2:
                domain_hints[words[0] + words[1]] = county

    return domain_hints


def match_email_domain(email, domain_hints, district_to_county):
    """Try to match an email domain to a county."""
    if not email or "@" not in email:
        return None, None

    domain = email.split("@")[1].lower().strip()
    # Skip generic domains
    generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
               "aol.com", "icloud.com", "me.com", "live.com", "msn.com",
               "comcast.net", "sbcglobal.net", "att.net", "verizon.net",
               "charter.net", "cox.net"}
    if domain in generic:
        return None, None

    # Extract domain root: "lausd.net" → "lausd", "srvusd.net" → "srvusd"
    domain_root = domain.split(".")[0]

    # Direct match in hints
    if domain_root in domain_hints:
        return domain_hints[domain_root], f"email domain '{domain_root}'"

    # Try matching domain root against district names
    # e.g., "abcusd" → look for district containing "abc"
    for dist_name, county in district_to_county.items():
        dist_clean = re.sub(r"\s+", "", dist_name)  # remove spaces
        if len(domain_root) >= 4 and domain_root in dist_clean:
            return county, f"email domain '{domain_root}' ~ district '{dist_name}'"
        if len(dist_clean) >= 4 and dist_clean in domain_root:
            return county, f"email domain '{domain_root}' ~ district '{dist_name}'"

    # Check if domain ends with k12.ca.us — that's a CA school domain
    # Format: districtcode.k12.ca.us — the districtcode part might match
    if domain.endswith(".k12.ca.us"):
        subdomain = domain.replace(".k12.ca.us", "")
        for dist_name, county in district_to_county.items():
            dist_clean = re.sub(r"\s+", "", dist_name)
            if subdomain in dist_clean or dist_clean in subdomain:
                return county, f"k12 domain '{subdomain}' ~ district '{dist_name}'"

    return None, None


# ─────────────────────────────────────────────
# NAME MATCHING (fuzzy-ish)
# ─────────────────────────────────────────────

# Common suffixes to strip for matching
_STRIP_SUFFIXES = [
    "school", "elementary", "middle", "high", "junior high",
    "intermediate", "academy", "charter", "preparatory", "prep",
    "magnet", "continuation", "alternative", "community",
    "learning center", "center", "campus",
    "k 8", "k 12", "k8", "k12",
    "unified school district", "unified", "school district",
    "union school district", "union elementary school district",
    "union high school district", "joint union high school district",
    "joint unified school district", "elementary school district",
    "high school district",
]

def _strip_suffixes(name: str) -> str:
    """Strip common school/district suffixes for fuzzy matching."""
    n = name
    for suffix in sorted(_STRIP_SUFFIXES, key=len, reverse=True):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def match_name(company_name, school_to_county, district_to_county, school_to_district):
    """
    Try to match a company/account name against CDE schools and districts.
    Returns (county, method_description) or (None, None).
    """
    if not company_name:
        return None, None

    normalized = _normalize(company_name)
    if not normalized:
        return None, None

    # 1. Exact match on school name
    if normalized in school_to_county:
        return school_to_county[normalized], f"exact school match"

    # 2. Exact match on district name
    if normalized in district_to_county:
        return district_to_county[normalized], f"exact district match"

    # 3. Try with suffixes stripped
    stripped = _strip_suffixes(normalized)
    if stripped and stripped != normalized:
        # Check schools
        for school, county in school_to_county.items():
            school_stripped = _strip_suffixes(school)
            if stripped == school_stripped and stripped:
                return county, f"stripped school match '{school}'"
        # Check districts
        for dist, county in district_to_county.items():
            dist_stripped = _strip_suffixes(dist)
            if stripped == dist_stripped and stripped:
                return county, f"stripped district match '{dist}'"

    # 4. Substring matching (company name contains a known school/district or vice versa)
    # Only for names with 3+ words or 12+ chars to avoid false matches
    if len(normalized) >= 12:
        # Check if company name is contained in a school name
        for school, county in school_to_county.items():
            if normalized in school and len(normalized) >= len(school) * 0.5:
                return county, f"substring school match '{school}'"
            if school in normalized and len(school) >= len(normalized) * 0.5:
                return county, f"substring school match '{school}'"

    return None, None


def match_district_name(district_name, district_to_county):
    """Match the District Name field against CDE districts."""
    if not district_name:
        return None, None

    normalized = _normalize(district_name)
    if not normalized:
        return None, None

    if normalized in district_to_county:
        return district_to_county[normalized], f"district name field match"

    stripped = _strip_suffixes(normalized)
    if stripped:
        for dist, county in district_to_county.items():
            dist_stripped = _strip_suffixes(dist)
            if stripped == dist_stripped and stripped:
                return district_to_county[dist], f"stripped district name match '{dist}'"

    return None, None


# ─────────────────────────────────────────────
# MAIN PROCESSING
# ─────────────────────────────────────────────

def process_file(input_path, output_path, company_col, district_col, city_col, zip_col, email_col,
                 school_to_county, district_to_county, zip_to_county, city_to_county,
                 school_to_district, domain_hints, label="records"):
    """Process a CSV file, add County + SoCal columns, filter NorCal."""

    with open(input_path, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)

    print(f"\nProcessing {label}: {len(rows):,} records")

    # Stats
    tier_counts = {"name": 0, "district_field": 0, "zip": 0, "city": 0, "email": 0, "uncertain": 0}
    county_counts = defaultdict(int)
    socal_count = 0
    norcal_count = 0
    uncertain_count = 0

    output_rows = []

    for row in rows:
        company = row.get(company_col, "").strip()
        district = row.get(district_col, "").strip() if district_col else ""
        city = row.get(city_col, "").strip() if city_col else ""
        zipcode = row.get(zip_col, "").strip() if zip_col else ""
        email = row.get(email_col, "").strip() if email_col else ""

        county = None
        method = None

        # Tier 1: Company/Account name → school/district → county
        county, method = match_name(company, school_to_county, district_to_county, school_to_district)
        if county:
            tier_counts["name"] += 1

        # Tier 1b: District Name field
        if not county and district:
            county, method = match_district_name(district, district_to_county)
            if county:
                tier_counts["district_field"] += 1

        # Tier 2: Zip → county
        if not county and zipcode:
            z5 = zipcode.strip().split("-")[0].strip()
            if z5 in zip_to_county:
                county = zip_to_county[z5]
                method = f"zip '{z5}'"
                tier_counts["zip"] += 1

        # Tier 3: City → county
        if not county and city:
            city_lower = city.lower().strip()
            if city_lower in city_to_county:
                county = city_to_county[city_lower]
                method = f"city '{city}'"
                tier_counts["city"] += 1

        # Tier 4: Email domain → district → county
        if not county and email:
            county, method = match_email_domain(email, domain_hints, district_to_county)
            if county:
                tier_counts["email"] += 1

        # Tier 5: Uncertain
        if not county:
            tier_counts["uncertain"] += 1
            uncertain_count += 1

        # Determine SoCal flag
        if county:
            county_lower = county.lower()
            county_counts[county] += 1
            if county_lower in SOCAL_COUNTIES:
                socal_flag = "Yes"
                socal_count += 1
            else:
                socal_flag = "No"
                norcal_count += 1
        else:
            socal_flag = "Uncertain"

        row["County"] = county or ""
        row["SoCal"] = socal_flag
        row["County_Method"] = method or ""
        output_rows.append(row)

    # Write output — only SoCal + Uncertain (remove confirmed NorCal)
    out_headers = headers + ["County", "SoCal", "County_Method"]
    kept = [r for r in output_rows if r["SoCal"] != "No"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    # Also write a NorCal-only file for review
    norcal_path = output_path.replace(".csv", "_NORCAL_REMOVED.csv")
    norcal_rows = [r for r in output_rows if r["SoCal"] == "No"]
    with open(norcal_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(norcal_rows)

    print(f"\n  Resolution by tier:")
    print(f"    Tier 1 (name match):     {tier_counts['name']:>6,}")
    print(f"    Tier 1b (district field): {tier_counts['district_field']:>6,}")
    print(f"    Tier 2 (zip):            {tier_counts['zip']:>6,}")
    print(f"    Tier 3 (city):           {tier_counts['city']:>6,}")
    print(f"    Tier 4 (email domain):   {tier_counts['email']:>6,}")
    print(f"    Tier 5 (uncertain):      {tier_counts['uncertain']:>6,}")
    print(f"\n  Results:")
    print(f"    SoCal:     {socal_count:>6,}")
    print(f"    NorCal:    {norcal_count:>6,} (removed)")
    print(f"    Uncertain: {uncertain_count:>6,} (kept for review)")
    print(f"    Output:    {len(kept):>6,} records written to {output_path}")
    print(f"    Removed:   {len(norcal_rows):>6,} records written to {norcal_path}")

    # Show top counties
    print(f"\n  Top 15 counties found:")
    for county, count in sorted(county_counts.items(), key=lambda x: -x[1])[:15]:
        flag = " ★ SoCal" if county.lower() in SOCAL_COUNTIES else ""
        print(f"    {county:>25s}: {count:>5,}{flag}")

    return {
        "total": len(rows),
        "socal": socal_count,
        "norcal": norcal_count,
        "uncertain": uncertain_count,
        "kept": len(kept),
        "tiers": tier_counts,
    }


def main():
    print("=" * 60)
    print("SoCal Filter — CDE School Directory Matching")
    print("=" * 60)

    # Build lookups
    school_to_county, district_to_county, zip_to_county, city_to_county, school_to_district = build_lookups()
    domain_hints = build_domain_to_county(district_to_county)
    print(f"  Domain hints: {len(domain_hints):,}")

    # Process Leads
    leads_result = process_file(
        input_path="/Users/stevenadkins/Downloads/My Leads - SoCal Only.csv",
        output_path="/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv",
        company_col="Company / Account",
        district_col="District Name",
        city_col="City",
        zip_col="Zip/Postal Code",
        email_col="Email",
        school_to_county=school_to_county,
        district_to_county=district_to_county,
        zip_to_county=zip_to_county,
        city_to_county=city_to_county,
        school_to_district=school_to_district,
        domain_hints=domain_hints,
        label="LEADS",
    )

    # Process Contacts
    contacts_result = process_file(
        input_path="/Users/stevenadkins/Downloads/My Contacts - SoCal Only.csv",
        output_path="/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv",
        company_col="Account Name",
        district_col="District Name",
        city_col="Mailing City",
        zip_col="Mailing Zip/Postal Code",
        email_col="Email",
        school_to_county=school_to_county,
        district_to_county=district_to_county,
        zip_to_county=zip_to_county,
        city_to_county=city_to_county,
        school_to_district=school_to_district,
        domain_hints=domain_hints,
        label="CONTACTS",
    )

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"\nLeads:    {leads_result['socal']:,} SoCal + {leads_result['uncertain']:,} uncertain = {leads_result['kept']:,} kept | {leads_result['norcal']:,} NorCal removed")
    print(f"Contacts: {contacts_result['socal']:,} SoCal + {contacts_result['uncertain']:,} uncertain = {contacts_result['kept']:,} kept | {contacts_result['norcal']:,} NorCal removed")
    print(f"\nOutput files in ~/Downloads/:")
    print(f"  Leads_SoCal_Filtered.csv")
    print(f"  Contacts_SoCal_Filtered.csv")
    print(f"  Leads_SoCal_Filtered_NORCAL_REMOVED.csv (for review)")
    print(f"  Contacts_SoCal_Filtered_NORCAL_REMOVED.csv (for review)")


if __name__ == "__main__":
    main()
