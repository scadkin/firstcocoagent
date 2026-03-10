"""Pass 4: Serper web search on uncertain records with school/academy keywords.

Searches each school name + "California county" to determine location.
Updates the filtered CSVs in ~/Downloads/.

Usage:
    SERPER_API_KEY=xxx python3 scripts/socal_filter_pass4.py
"""
import csv
import json
import os
import re
import sys
import time
import httpx

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

SOCAL_COUNTIES = {
    'los angeles', 'san diego', 'orange', 'riverside', 'san bernardino',
    'kern', 'ventura', 'santa barbara', 'san luis obispo', 'imperial',
}

ALL_CA_COUNTIES = {
    'alameda', 'alpine', 'amador', 'butte', 'calaveras', 'colusa',
    'contra costa', 'del norte', 'el dorado', 'fresno', 'glenn',
    'humboldt', 'imperial', 'inyo', 'kern', 'kings', 'lake', 'lassen',
    'los angeles', 'madera', 'marin', 'mariposa', 'mendocino', 'merced',
    'modoc', 'mono', 'monterey', 'napa', 'nevada', 'orange', 'placer',
    'plumas', 'riverside', 'sacramento', 'san benito', 'san bernardino',
    'san diego', 'san francisco', 'san joaquin', 'san luis obispo',
    'san mateo', 'santa barbara', 'santa clara', 'santa cruz', 'shasta',
    'sierra', 'siskiyou', 'solano', 'sonoma', 'stanislaus', 'sutter',
    'tehama', 'trinity', 'tulare', 'tuolumne', 'ventura', 'yolo', 'yuba',
}

# Keywords that indicate a school/education record
SCHOOL_KEYWORDS = [
    'school', 'academy', 'acad', 'collegiate', 'preparatory', 'prep',
    'charter', 'montessori', 'learning', 'education', 'elementary',
    'middle', 'high school', 'christian', 'catholic', 'lutheran',
    'hebrew', 'jewish', 'baptist', 'adventist', 'episcopal', 'waldorf',
]


def has_school_keyword(name):
    name_lower = name.lower()
    return any(kw in name_lower for kw in SCHOOL_KEYWORDS)


def extract_county_from_serper(results):
    """Parse Serper results to find a California county mention."""
    text_blocks = []

    # Collect text from organic results
    for item in results.get('organic', [])[:5]:
        text_blocks.append(item.get('title', ''))
        text_blocks.append(item.get('snippet', ''))

    # Knowledge graph
    kg = results.get('knowledgeGraph', {})
    if kg:
        text_blocks.append(kg.get('title', ''))
        text_blocks.append(kg.get('description', ''))
        for attr_key, attr_val in kg.get('attributes', {}).items():
            text_blocks.append(f"{attr_key}: {attr_val}")

    # Answer box
    ab = results.get('answerBox', {})
    if ab:
        text_blocks.append(ab.get('answer', ''))
        text_blocks.append(ab.get('snippet', ''))

    combined = ' '.join(text_blocks).lower()

    # Look for "X County, California" or "X County, CA" patterns
    county_patterns = [
        r'(\w[\w\s]*?)\s+county\s*,\s*(?:california|ca)\b',
        r'(?:located in|county of|in)\s+(\w[\w\s]*?)\s+county',
        r'(\w[\w\s]*?)\s+county\s+(?:office|superintendent|department)',
    ]

    for pattern in county_patterns:
        matches = re.findall(pattern, combined)
        for match in matches:
            candidate = match.strip().lower()
            if candidate in ALL_CA_COUNTIES:
                return candidate.title()

    # Direct county name mention near "california" or "CA"
    for county in ALL_CA_COUNTIES:
        # Look for county name near California context
        county_re = re.escape(county)
        if re.search(rf'\b{county_re}\b', combined):
            # Verify it's in a California context (not e.g. Orange, NJ)
            if 'california' in combined or ', ca' in combined or 'ca ' in combined[:200]:
                return county.title()

    return None


def extract_state_from_serper(results):
    """Check if the result clearly indicates a non-CA state."""
    text_blocks = []
    for item in results.get('organic', [])[:3]:
        text_blocks.append(item.get('title', ''))
        text_blocks.append(item.get('snippet', ''))
    kg = results.get('knowledgeGraph', {})
    if kg:
        text_blocks.append(kg.get('description', ''))
        for attr_val in kg.get('attributes', {}).values():
            text_blocks.append(str(attr_val))

    combined = ' '.join(text_blocks)

    # Check for non-CA states explicitly mentioned
    non_ca_states = [
        'New York', 'New Jersey', 'Texas', 'Florida', 'Illinois',
        'Pennsylvania', 'Ohio', 'Michigan', 'Georgia', 'North Carolina',
        'Virginia', 'Washington', 'Arizona', 'Massachusetts', 'Tennessee',
        'Indiana', 'Missouri', 'Maryland', 'Wisconsin', 'Colorado',
        'Minnesota', 'South Carolina', 'Alabama', 'Louisiana', 'Kentucky',
        'Oregon', 'Oklahoma', 'Connecticut', 'Utah', 'Iowa',
        'Nevada', 'Arkansas', 'Mississippi', 'Kansas', 'New Mexico',
        'Nebraska', 'Idaho', 'West Virginia', 'Hawaii', 'New Hampshire',
        'Maine', 'Montana', 'Rhode Island', 'Delaware', 'South Dakota',
        'North Dakota', 'Alaska', 'Vermont', 'Wyoming',
    ]
    for state in non_ca_states:
        if state in combined and 'California' not in combined:
            return state

    return None


def search_serper(query):
    """Run a single Serper search. Returns parsed JSON or None."""
    try:
        resp = httpx.post(
            SERPER_URL,
            json={"q": query, "num": 5},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  Serper error {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  Serper exception: {e}")
        return None


def process_file(path, company_col, label):
    """Search uncertain school-keyword records via Serper."""
    with open(path, encoding='latin-1') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames)
        all_rows = list(reader)

    uncertain = [r for r in all_rows if r.get('SoCal') == 'Uncertain']
    resolved = [r for r in all_rows if r.get('SoCal') != 'Uncertain']

    # Filter to school-keyword records only
    school_uncertain = [r for r in uncertain if has_school_keyword(r.get(company_col, ''))]
    non_school_uncertain = [r for r in uncertain if not has_school_keyword(r.get(company_col, ''))]

    print(f"\n{'='*60}")
    print(f"{label}: {len(school_uncertain)} school-keyword uncertain records to search")
    print(f"  ({len(non_school_uncertain)} non-school uncertain will be kept as-is)")
    print(f"{'='*60}")

    matched_socal = 0
    matched_norcal = 0
    matched_non_ca = 0
    no_match = 0
    errors = 0

    for i, row in enumerate(school_uncertain):
        company = row.get(company_col, '').strip()
        if not company or company.startswith('@') or '@' in company:
            # Skip email-as-company entries
            no_match += 1
            continue

        query = f'"{company}" California county school'
        print(f"  [{i+1}/{len(school_uncertain)}] {company}")

        results = search_serper(query)
        if not results:
            errors += 1
            time.sleep(0.5)
            continue

        county = extract_county_from_serper(results)
        if county:
            row['County'] = county
            row['County_Method'] = f'pass4: serper "{company}"'
            if county.lower() in SOCAL_COUNTIES:
                row['SoCal'] = 'Yes'
                matched_socal += 1
                print(f"    → SoCal ({county})")
            else:
                row['SoCal'] = 'No'
                matched_norcal += 1
                print(f"    → NorCal/Central ({county})")
        else:
            # Check if it's clearly non-CA
            non_ca_state = extract_state_from_serper(results)
            if non_ca_state:
                row['SoCal'] = 'No'
                row['County_Method'] = f'pass4: serper non-CA ({non_ca_state})'
                matched_non_ca += 1
                print(f"    → Not California ({non_ca_state})")
            else:
                no_match += 1
                print(f"    → No match")

        # Rate limit: ~2 requests/second
        time.sleep(0.5)

    # Recombine
    all_updated = resolved + school_uncertain + non_school_uncertain
    kept = [r for r in all_updated if r['SoCal'] != 'No']
    removed = [r for r in all_updated if r['SoCal'] == 'No']

    # Write kept records
    with open(path, 'w', encoding='latin-1', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(kept)

    # Append newly removed to NorCal file
    norcal_path = path.replace('.csv', '_NORCAL_REMOVED.csv')
    newly_removed = [r for r in removed if 'pass4' in r.get('County_Method', '')]
    if newly_removed:
        with open(norcal_path, 'a', encoding='latin-1', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writerows(newly_removed)

    still_uncertain = sum(1 for r in kept if r['SoCal'] == 'Uncertain')
    socal_confirmed = sum(1 for r in kept if r['SoCal'] == 'Yes')

    print(f"\n{label} RESULTS:")
    print(f"  Serper searches: {len(school_uncertain)}")
    print(f"  Resolved → SoCal: {matched_socal}")
    print(f"  Resolved → NorCal/Central CA: {matched_norcal}")
    print(f"  Resolved → Non-California: {matched_non_ca}")
    print(f"  No match (still uncertain): {no_match}")
    print(f"  Errors: {errors}")
    print(f"  File: {socal_confirmed} confirmed SoCal + {still_uncertain} uncertain = {len(kept)} kept")

    return len(school_uncertain)


def main():
    if not SERPER_API_KEY:
        print("ERROR: Set SERPER_API_KEY environment variable")
        print("Usage: SERPER_API_KEY=xxx python3 scripts/socal_filter_pass4.py")
        sys.exit(1)

    print("Pass 4: Serper web search for uncertain school-keyword records")
    print(f"API key: {SERPER_API_KEY[:8]}...")

    total_searches = 0
    total_searches += process_file(
        '/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv',
        'Company / Account',
        'LEADS',
    )
    total_searches += process_file(
        '/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv',
        'Account Name',
        'CONTACTS',
    )

    print(f"\n{'='*60}")
    print(f"TOTAL Serper credits used: ~{total_searches}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
