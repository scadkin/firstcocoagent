"""Pass 5: Free lookups — email domain→district→county, phone area code, city, District Name field.

No Serper credits used. Resolves uncertain records using data already in the CSV.

Usage:
    python3 scripts/socal_filter_pass5.py
"""
import csv
import re

SOCAL_COUNTIES = {
    'los angeles', 'san diego', 'orange', 'riverside', 'san bernardino',
    'kern', 'ventura', 'santa barbara', 'san luis obispo', 'imperial',
}

# ── Email domain → (county, district name) mapping ──
# CA school district domains mapped to their county
DOMAIN_TO_COUNTY = {
    # SoCal
    'lausd.net': ('Los Angeles', 'Los Angeles USD'),
    'mymail.lausd.net': ('Los Angeles', 'Los Angeles USD'),
    'laalliance.org': ('Los Angeles', 'Alliance College-Ready Public Schools'),
    'bpusd.net': ('Los Angeles', 'Baldwin Park USD'),
    'ggusd.net': ('Orange', 'Garden Grove USD'),
    'ggusd.us': ('Orange', 'Garden Grove USD'),
    'capousd.org': ('Orange', 'Capistrano USD'),
    'iusd.org': ('Orange', 'Irvine USD'),
    'svusd.org': ('Orange', 'Saddleback Valley USD'),
    'cnusd.k12.ca.us': ('Riverside', 'Corona-Norco USD'),
    'tvusd.us': ('Riverside', 'Temecula Valley USD'),
    'mytusd.org': ('Riverside', 'Temecula Valley USD'),
    'sbcusd.k12.ca.us': ('San Bernardino', 'San Bernardino City USD'),
    'my.cjusd.net': ('San Bernardino', 'Colton Joint USD'),
    'hcsd.k12.ca.us': ('San Mateo', 'Hillsborough City SD'),
    'cvesd.org': ('San Diego', 'Chula Vista ESD'),
    'my.sduhsd.net': ('San Diego', 'San Dieguito Union HSD'),
    'stu.powayusd.com': ('San Diego', 'Poway USD'),
    'esusd.k12.ca.us': ('San Diego', 'El Cajon USD'),  # close enough
    'smusd.org': ('San Diego', 'San Marcos USD'),
    'pvpusd.net': ('Los Angeles', 'Palos Verdes Peninsula USD'),
    'myabcusd.org': ('Los Angeles', 'ABC USD'),
    'auhsd.net': ('Orange', 'Anaheim Union HSD'),
    'auhsd.us': ('Orange', 'Anaheim Union HSD'),
    'g.mvusd.net': ('Riverside', 'Moreno Valley USD'),
    'husd.k12.ca.us': ('Riverside', 'Hemet USD'),
    'lmusd.org': ('San Luis Obispo', 'Lucia Mar USD'),
    'hbcsd.k12.ca.us': ('Orange', 'Huntington Beach City SD'),
    'mydusd.org': ('Los Angeles', 'Downey USD'),
    'gusd.net': ('Los Angeles', 'Glendale USD'),
    'gusd.com': ('Los Angeles', 'Glendale USD'),
    'rbgusd.org': ('Kern', 'Rio Bravo-Greeley USD'),  # need to verify
    'stu.wvusd.org': ('Los Angeles', 'Walnut Valley USD'),
    'ouhsd.k12.ca.us': ('Ventura', 'Oxnard Union HSD'),
    'kvusd.org': ('Kern', 'Kern Valley USD'),
    'opusd.us': ('Orange', 'Ocean View/Orange?'),
    'materdei.org': ('Orange', 'Mater Dei HS'),
    'brains-and-motion.com': ('Orange', 'Brains & Motion Education'),  # OC based

    # NorCal / Central
    'egusd.net': ('Sacramento', 'Elk Grove USD'),
    'scusd.edu': ('Sacramento', 'Sacramento City USD'),
    'twinriversusd.org': ('Sacramento', 'Twin Rivers USD'),
    'fortuneschool.us': ('Sacramento', 'Fortune School'),
    'sjusd.org': ('Santa Clara', 'San Jose USD'),
    'fusdk12.net': ('Alameda', 'Fremont USD'),
    'pausd.us': ('Santa Clara', 'Palo Alto USD'),
    'mdusd.net': ('Contra Costa', 'Mt. Diablo USD'),
    'wccusd.net': ('Contra Costa', 'West Contra Costa USD'),
    'oakgrovesd.net': ('Santa Clara', 'Oak Grove SD'),
    'sfusd.edu': ('San Francisco', 'San Francisco USD'),
    's.sfusd.edu': ('San Francisco', 'San Francisco USD'),
    'gvusd.org': ('Nevada', 'Grass Valley USD'),
    'gvusd.k12.ca.us': ('Nevada', 'Grass Valley USD'),
    'nvusd.org': ('Solano', 'Napa Valley USD'),  # actually Napa
    'wpusd.org': ('Yolo', 'Woodland USD'),  # could be West Park
    'mcusd.org': ('Merced', 'Merced City USD'),  # could be other
    'eesd.org': ('Santa Clara', 'Evergreen ESD'),
    'centralusd.k12.ca.us': ('Fresno', 'Central USD'),
    'fusd.net': ('Fresno', 'Fresno USD'),
    'dusd.net': ('Alameda', 'Dublin USD'),
    'vcusd.org': ('Solano', 'Vacaville USD'),  # could be Vallejo
    'ycusd.org': ('Sutter', 'Yuba City USD'),
    'luhsd.k12.ca.us': ('Humboldt', 'Loleta Union HSD'),  # or Lemoore
    'pjusd.com': ('Placer', 'Placer Joint USD'),
    'ttusd.org': ('Nevada', 'Tahoe-Truckee USD'),
    'frjusd.org': ('Shasta', 'Fall River Joint USD'),
    'mtnview.k12.ca.us': ('Santa Clara', 'Mountain View'),
    'rbhsd.org': ('San Mateo', 'RB High School?'),
    'pgusd.org': ('Monterey', 'Pacific Grove USD'),
    'ssusdschools.org': ('Sonoma', 'Sonoma?'),
    'llesd.org': ('Santa Clara', 'Luther Burbank?'),
    'wrightesd.org': ('Stanislaus', 'Wright ESD'),
    'acusd.org': ('San Luis Obispo', 'Atascadero CSD'),
    'auesd.org': ('Sacramento', 'Arcohe/Arden?'),
    'bantaesd.net': ('San Joaquin', 'Banta ESD'),
    'cusdk8.org': ('Santa Clara', 'Cupertino USD'),
    'missionbit.org': ('San Francisco', 'Mission Bit'),

    # Non-California
    'dallasisd.org': ('NON-CA', 'Dallas ISD, TX'),
    'hermitage.k12.mo.us': ('NON-CA', 'Hermitage, MO'),
    'phm.k12.in.us': ('NON-CA', 'Penn-Harris-Madison, IN'),
    'silsbeeisd.org': ('NON-CA', 'Silsbee ISD, TX'),
}

# ── Phone area code → region mapping ──
SOCAL_AREA_CODES = {
    '213', '310', '323', '424', '442', '619', '626', '657', '661',
    '714', '747', '760', '805', '818', '858', '909', '949', '951',
}
NORCAL_AREA_CODES = {
    '209', '279', '341', '408', '415', '510', '530', '559', '650',
    '669', '707', '831', '916', '925', '934',
}

# ── City → county (for the few records with city data) ──
CA_CITY_TO_COUNTY = {
    'los angeles': 'Los Angeles', 'la': 'Los Angeles', 'hollywood': 'Los Angeles',
    'burbank': 'Los Angeles', 'pasadena': 'Los Angeles', 'glendale': 'Los Angeles',
    'long beach': 'Los Angeles', 'torrance': 'Los Angeles', 'pomona': 'Los Angeles',
    'santa monica': 'Los Angeles', 'west hollywood': 'Los Angeles',
    'san diego': 'San Diego', 'chula vista': 'San Diego', 'oceanside': 'San Diego',
    'carlsbad': 'San Diego', 'escondido': 'San Diego', 'la mesa': 'San Diego',
    'anaheim': 'Orange', 'irvine': 'Orange', 'santa ana': 'Orange',
    'huntington beach': 'Orange', 'costa mesa': 'Orange', 'fullerton': 'Orange',
    'riverside': 'Riverside', 'corona': 'Riverside', 'temecula': 'Riverside',
    'murrieta': 'Riverside', 'moreno valley': 'Riverside',
    'san bernardino': 'San Bernardino', 'ontario': 'San Bernardino',
    'rancho cucamonga': 'San Bernardino', 'fontana': 'San Bernardino',
    'bakersfield': 'Kern', 'oxnard': 'Ventura', 'ventura': 'Ventura',
    'thousand oaks': 'Ventura', 'simi valley': 'Ventura', 'camarillo': 'Ventura',
    'santa barbara': 'Santa Barbara',
    'san francisco': 'San Francisco', 'sf': 'San Francisco',
    'oakland': 'Alameda', 'berkeley': 'Alameda', 'fremont': 'Alameda',
    'san jose': 'Santa Clara', 'sunnyvale': 'Santa Clara', 'cupertino': 'Santa Clara',
    'palo alto': 'Santa Clara', 'mountain view': 'Santa Clara',
    'sacramento': 'Sacramento', 'fresno': 'Fresno',
    'stockton': 'San Joaquin', 'modesto': 'Stanislaus',
}

# Non-CA cities (junk data in the City field)
NON_CA_CITIES = {
    'dallas', 'raleigh', 'conyers', 'palm beach gardens', 'miami', 'mastic',
    'hendon', 'texarkana', 'atlanta', 'rockville', 'boquete', 'regina',
    'oxford', 'edgewater',
}

# Junk city values
JUNK_CITIES = {'city', 'test', 'california', 'caliornia', 'virgina', 'sdfg', 'vbb', 'n/a', ''}

EMAIL_COL_LEADS = 'ï»¿Email'  # BOM-mangled column name in latin-1


def get_area_code(phone):
    """Extract 3-digit area code from phone number."""
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) >= 10:
        # Handle +1 prefix
        if len(digits) == 11 and digits[0] == '1':
            return digits[1:4]
        return digits[:3]
    return None


def process_file(path, company_col, email_col, city_col, district_col, label):
    with open(path, encoding='latin-1') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames)
        all_rows = list(reader)

    uncertain = [r for r in all_rows if r.get('SoCal') == 'Uncertain']
    resolved = [r for r in all_rows if r.get('SoCal') != 'Uncertain']

    print(f"\n{'='*60}")
    print(f"{label}: {len(uncertain)} uncertain records")
    print(f"{'='*60}")

    by_domain = 0
    by_area_code = 0
    by_city = 0
    by_district = 0
    by_junk = 0
    newly_socal = 0
    newly_norcal = 0
    newly_nonca = 0

    for row in uncertain:
        email = row.get(email_col, '')
        phone = row.get('Phone', '').strip()
        city = row.get(city_col, '').strip().lower() if city_col else ''
        district = row.get(district_col, '').strip() if district_col else ''
        company = row.get(company_col, '').strip()

        county = None
        method = None

        # ── Strategy 1: Email domain → district → county ──
        if email and '@' in email:
            domain = email.split('@')[-1].lower().strip()
            if domain in DOMAIN_TO_COUNTY:
                county_name, district_name = DOMAIN_TO_COUNTY[domain]
                if county_name == 'NON-CA':
                    row['SoCal'] = 'No'
                    row['County_Method'] = f'pass5: email domain non-CA ({domain} → {district_name})'
                    newly_nonca += 1
                    by_domain += 1
                    continue
                county = county_name
                method = f'pass5: email domain ({domain} → {district_name})'
                by_domain += 1

        # ── Strategy 2: District Name field (for non-CA districts) ──
        if not county and district:
            district_lower = district.lower()
            # Non-CA indicators
            non_ca_indicators = ['elmhurst', 'oneida', 'montgomery county', 'clarkston',
                                 'bentley community', 'penn-harris', 'dallas']
            if any(ind in district_lower for ind in non_ca_indicators):
                row['SoCal'] = 'No'
                row['County_Method'] = f'pass5: District Name non-CA ({district})'
                newly_nonca += 1
                by_district += 1
                continue

        # ── Strategy 3: City field ──
        if not county and city and city not in JUNK_CITIES:
            if city in NON_CA_CITIES:
                row['SoCal'] = 'No'
                row['County_Method'] = f'pass5: city non-CA ({city})'
                newly_nonca += 1
                by_city += 1
                continue
            if city in CA_CITY_TO_COUNTY:
                county = CA_CITY_TO_COUNTY[city]
                method = f'pass5: city field ({city})'
                by_city += 1

        # ── Strategy 4: Phone area code ──
        if not county and phone:
            ac = get_area_code(phone)
            if ac:
                if ac in SOCAL_AREA_CODES:
                    county = 'SoCal (by area code)'
                    method = f'pass5: area code {ac} (SoCal)'
                    by_area_code += 1
                elif ac in NORCAL_AREA_CODES:
                    county = 'NorCal (by area code)'
                    method = f'pass5: area code {ac} (NorCal)'
                    by_area_code += 1

        # ── Strategy 5: Junk/garbage company names ──
        if not county:
            company_lower = company.lower().strip()
            junk_indicators = ['n/a', 'test', 'unknown', 'fake', 'none', 'asdf', 'poopy',
                               'goblin', 'kitkat', 'fahgufugsh', 'ikmacoolboy', 'aschool',
                               'codecombat online']
            if any(company_lower.startswith(j) or company_lower == j for j in junk_indicators):
                # Check if they have any CA indicators
                if phone:
                    ac = get_area_code(phone)
                    if ac and ac not in SOCAL_AREA_CODES and ac not in NORCAL_AREA_CODES:
                        row['SoCal'] = 'No'
                        row['County_Method'] = f'pass5: junk name + non-CA area code {ac}'
                        newly_nonca += 1
                        by_junk += 1
                        continue

        # Apply county result
        if county:
            row['County'] = county
            row['County_Method'] = method
            if county.lower() in SOCAL_COUNTIES or 'SoCal' in county:
                row['SoCal'] = 'Yes'
                newly_socal += 1
            else:
                row['SoCal'] = 'No'
                newly_norcal += 1

    # Recombine
    all_updated = resolved + uncertain
    kept = [r for r in all_updated if r['SoCal'] != 'No']
    removed = [r for r in all_updated if r['SoCal'] == 'No']

    # Write kept
    with open(path, 'w', encoding='latin-1', newline='', errors='replace') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(kept)

    # Append newly removed to NorCal file
    norcal_path = path.replace('.csv', '_NORCAL_REMOVED.csv')
    newly_removed = [r for r in removed if 'pass5' in r.get('County_Method', '')]
    if newly_removed:
        with open(norcal_path, 'a', encoding='latin-1', newline='', errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writerows(newly_removed)

    still_uncertain = sum(1 for r in kept if r['SoCal'] == 'Uncertain')
    socal_confirmed = sum(1 for r in kept if r['SoCal'] == 'Yes')

    print(f"\n{label} RESULTS:")
    print(f"  By email domain: {by_domain}")
    print(f"  By phone area code: {by_area_code}")
    print(f"  By city field: {by_city}")
    print(f"  By District Name: {by_district}")
    print(f"  By junk cleanup: {by_junk}")
    print(f"  ─────────────────")
    print(f"  Resolved → SoCal: {newly_socal}")
    print(f"  Resolved → NorCal/Central: {newly_norcal}")
    print(f"  Resolved → Non-California: {newly_nonca}")
    print(f"  Still uncertain: {still_uncertain}")
    print(f"  File: {socal_confirmed} confirmed SoCal + {still_uncertain} uncertain = {len(kept)} kept")


def main():
    print("Pass 5: Free lookups (email domain, phone area code, city, District Name)")
    print("No Serper credits used.\n")

    process_file(
        '/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv',
        company_col='Company / Account',
        email_col=EMAIL_COL_LEADS,
        city_col='City',
        district_col='District Name',
        label='LEADS',
    )
    process_file(
        '/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv',
        company_col='Account Name',
        email_col=EMAIL_COL_LEADS,  # same BOM issue
        city_col='Mailing City',
        district_col='District Name',
        label='CONTACTS',
    )


if __name__ == '__main__':
    main()
