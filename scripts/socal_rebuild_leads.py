"""Rebuild Leads_SoCal_Filtered.csv by replaying passes 1-3 from original,
then applying pass 4 Serper results, then running pass 5 free lookups.

Fixes the accidental loss of uncertain records.
"""
import csv
import re
import os
import sys

# Add parent dir to path so we can import pass5
sys.path.insert(0, os.path.dirname(__file__))

SOCAL = {'los angeles', 'san diego', 'orange', 'riverside', 'san bernardino',
         'kern', 'ventura', 'santa barbara', 'san luis obispo', 'imperial'}

SOCAL_ZIPS = set()
# SoCal zip ranges (approximate)
for prefix in range(900, 936):  # 900xx-935xx covers most of SoCal
    for suffix in range(100):
        SOCAL_ZIPS.add(f'{prefix}{suffix:02d}')
# Remove NorCal zips that overlap
NORCAL_ZIP_PREFIXES = {'930', '931', '932', '933', '934', '935'}  # SLO/SB area actually SoCal

SOCAL_CITIES = {
    'los angeles', 'long beach', 'santa ana', 'anaheim', 'riverside',
    'san bernardino', 'san diego', 'irvine', 'chula vista', 'oxnard',
    'fontana', 'moreno valley', 'glendale', 'huntington beach', 'garden grove',
    'oceanside', 'rancho cucamonga', 'ontario', 'corona', 'lancaster',
    'palmdale', 'pomona', 'escondido', 'torrance', 'pasadena', 'el monte',
    'downey', 'inglewood', 'costa mesa', 'carlsbad', 'vista', 'compton',
    'mission viejo', 'carson', 'westminster', 'santa maria', 'santa barbara',
    'fullerton', 'hawthorne', 'whittier', 'norwalk', 'burbank', 'el cajon',
    'bakersfield', 'ventura', 'thousand oaks', 'simi valley', 'camarillo',
    'temecula', 'murrieta', 'la mesa', 'encinitas', 'national city',
    'imperial beach', 'san marcos', 'poway', 'la mirada', 'tustin',
    'lake forest', 'laguna niguel', 'buena park', 'cypress', 'la habra',
    'placentia', 'yorba linda', 'san clemente', 'dana point', 'brea',
    'redlands', 'loma linda', 'rialto', 'highland', 'upland', 'claremont',
    'arcadia', 'azusa', 'covina', 'west covina', 'glendora', 'san dimas',
    'la verne', 'diamond bar', 'walnut', 'rowland heights', 'hacienda heights',
    'monterey park', 'alhambra', 'rosemead', 'south pasadena', 'temple city',
    'el segundo', 'manhattan beach', 'hermosa beach', 'redondo beach',
    'palos verdes', 'rolling hills', 'san pedro', 'wilmington', 'harbor city',
    'santa clarita', 'valencia', 'newhall', 'castaic', 'sylmar', 'sun valley',
    'north hollywood', 'van nuys', 'encino', 'tarzana', 'woodland hills',
    'canoga park', 'chatsworth', 'northridge', 'granada hills', 'porter ranch',
    'calabasas', 'malibu', 'agoura hills', 'westlake village', 'moorpark',
    'fillmore', 'santa paula', 'ojai', 'carpinteria', 'goleta', 'lompoc',
    'san luis obispo', 'atascadero', 'paso robles', 'arroyo grande',
    'pismo beach', 'grover beach', 'nipomo', 'el centro', 'calexico',
    'brawley', 'holtville', 'imperial', 'hesperia', 'victorville',
    'apple valley', 'barstow', 'adelanto', 'twentynine palms', 'yucaipa',
    'beaumont', 'banning', 'hemet', 'menifee', 'lake elsinore', 'wildomar',
    'perris', 'indio', 'palm springs', 'palm desert', 'la quinta',
    'cathedral city', 'coachella', 'desert hot springs',
}

# ── Load CDE public schools ──
print("Loading CDE public schools...")
cde_schools = {}
with open('/tmp/cde_schools.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 5:
            school_name = parts[4].strip().lower() if len(parts) > 4 else ''
            county = parts[1].strip() if len(parts) > 1 else ''
            if school_name and county:
                key = re.sub(r'[^\w\s]', ' ', school_name)
                key = re.sub(r'\s+', ' ', key).strip()
                cde_schools[key] = county

# ── Load CDE districts ──
print("Loading CDE districts...")
cde_districts = {}
with open('/tmp/cde_districts.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            district_name = parts[2].strip().lower() if len(parts) > 2 else ''
            county = parts[1].strip() if len(parts) > 1 else ''
            if district_name and county:
                key = re.sub(r'[^\w\s]', ' ', district_name)
                key = re.sub(r'\s+', ' ', key).strip()
                cde_districts[key] = county

# ── Load CDE private schools ──
print("Loading CDE private schools...")
import openpyxl
wb = openpyxl.load_workbook('/tmp/cde_private_schools.xlsx', read_only=True)
ws = wb.active
rows_xlsx = list(ws.iter_rows(values_only=True))
cde_private = {}
for row in rows_xlsx[6:]:
    school_name = str(row[3]).strip() if row[3] else ''
    county = str(row[1]).strip() if row[1] else ''
    if school_name and county:
        key = school_name.lower().strip()
        key = re.sub(r'[^\w\s]', ' ', key)
        key = re.sub(r'\s+', ' ', key).strip()
        cde_private[key] = county
wb.close()

# ── Load NCES private schools ──
print("Loading NCES private schools...")
CA_FIPS = {
    '001': 'Alameda', '003': 'Alpine', '005': 'Amador', '007': 'Butte',
    '009': 'Calaveras', '011': 'Colusa', '013': 'Contra Costa', '015': 'Del Norte',
    '017': 'El Dorado', '019': 'Fresno', '021': 'Glenn', '023': 'Humboldt',
    '025': 'Imperial', '027': 'Inyo', '029': 'Kern', '031': 'Kings',
    '033': 'Lake', '035': 'Lassen', '037': 'Los Angeles', '039': 'Madera',
    '041': 'Marin', '043': 'Mariposa', '045': 'Mendocino', '047': 'Merced',
    '049': 'Modoc', '051': 'Mono', '053': 'Monterey', '055': 'Napa',
    '057': 'Nevada', '059': 'Orange', '061': 'Placer', '063': 'Plumas',
    '065': 'Riverside', '067': 'Sacramento', '069': 'San Benito',
    '071': 'San Bernardino', '073': 'San Diego', '075': 'San Francisco',
    '077': 'San Joaquin', '079': 'San Luis Obispo', '081': 'San Mateo',
    '083': 'Santa Barbara', '085': 'Santa Clara', '087': 'Santa Cruz',
    '089': 'Shasta', '091': 'Sierra', '093': 'Siskiyou', '095': 'Solano',
    '097': 'Sonoma', '099': 'Stanislaus', '101': 'Sutter', '103': 'Tehama',
    '105': 'Trinity', '107': 'Tulare', '109': 'Tuolumne', '111': 'Ventura',
    '113': 'Yolo', '115': 'Yuba',
}
nces_private = {}
with open('/tmp/nces_private/pss2122_pu.csv', encoding='latin-1') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('PSTANSI', '').strip() == '06':
            name = row.get('PINST', '').strip()
            county_fips = row.get('PCNTY', '').strip()
            county_name = CA_FIPS.get(county_fips, '')
            if name and county_name:
                key = name.lower().strip()
                key = re.sub(r'[^\w\s]', ' ', key)
                key = re.sub(r'\s+', ' ', key).strip()
                nces_private[key] = county_name

all_private = dict(nces_private)
all_private.update(cde_private)
print(f"Loaded: {len(cde_schools)} public schools, {len(cde_districts)} districts, {len(all_private)} private schools")

# ── Email domain → county (from passes 1-2) ──
DOMAIN_COUNTY = {
    'lausd.net': 'Los Angeles', 'mymail.lausd.net': 'Los Angeles',
    'laalliance.org': 'Los Angeles', 'bpusd.net': 'Los Angeles',
    'ggusd.net': 'Orange', 'ggusd.us': 'Orange',
    'capousd.org': 'Orange', 'iusd.org': 'Orange', 'svusd.org': 'Orange',
    'cnusd.k12.ca.us': 'Riverside', 'tvusd.us': 'Riverside', 'mytusd.org': 'Riverside',
    'sbcusd.k12.ca.us': 'San Bernardino', 'my.cjusd.net': 'San Bernardino',
    'cvesd.org': 'San Diego', 'my.sduhsd.net': 'San Diego',
    'stu.powayusd.com': 'San Diego', 'smusd.org': 'San Diego',
    'pvpusd.net': 'Los Angeles', 'myabcusd.org': 'Los Angeles',
    'auhsd.net': 'Orange', 'auhsd.us': 'Orange',
    'g.mvusd.net': 'Riverside', 'husd.k12.ca.us': 'Riverside',
    'hbcsd.k12.ca.us': 'Orange', 'mydusd.org': 'Los Angeles',
    'gusd.net': 'Los Angeles', 'gusd.com': 'Los Angeles',
    'stu.wvusd.org': 'Los Angeles', 'ouhsd.k12.ca.us': 'Ventura',
    'kvusd.org': 'Kern', 'materdei.org': 'Orange',
    'brains-and-motion.com': 'Orange', 'rbgusd.org': 'Kern',
    'lmusd.org': 'San Luis Obispo', 'acusd.org': 'San Luis Obispo',
    'opusd.us': 'Orange', 'hcsd.k12.ca.us': 'San Mateo',
    'egusd.net': 'Sacramento', 'scusd.edu': 'Sacramento',
    'twinriversusd.org': 'Sacramento', 'fortuneschool.us': 'Sacramento',
    'sjusd.org': 'Santa Clara', 'fusdk12.net': 'Alameda',
    'pausd.us': 'Santa Clara', 'mdusd.net': 'Contra Costa',
    'wccusd.net': 'Contra Costa', 'oakgrovesd.net': 'Santa Clara',
    'sfusd.edu': 'San Francisco', 's.sfusd.edu': 'San Francisco',
    'gvusd.org': 'Nevada', 'gvusd.k12.ca.us': 'Nevada',
    'nvusd.org': 'Napa', 'wpusd.org': 'Yolo',
    'mcusd.org': 'Merced', 'eesd.org': 'Santa Clara',
    'centralusd.k12.ca.us': 'Fresno', 'fusd.net': 'Fresno',
    'dusd.net': 'Alameda', 'vcusd.org': 'Solano',
    'ycusd.org': 'Sutter', 'luhsd.k12.ca.us': 'Humboldt',
    'pjusd.com': 'Placer', 'ttusd.org': 'Nevada',
    'frjusd.org': 'Shasta', 'mtnview.k12.ca.us': 'Santa Clara',
    'pgusd.org': 'Monterey', 'wrightesd.org': 'Stanislaus',
    'bantaesd.net': 'San Joaquin', 'cusdk8.org': 'Santa Clara',
    'missionbit.org': 'San Francisco', 'esusd.k12.ca.us': 'San Diego',
    'dallasisd.org': 'NON-CA', 'hermitage.k12.mo.us': 'NON-CA',
    'phm.k12.in.us': 'NON-CA', 'silsbeeisd.org': 'NON-CA',
    'auesd.org': 'Sacramento', 'ssusdschools.org': 'Sonoma',
    'llesd.org': 'Santa Clara', 'rbhsd.org': 'San Mateo',
}

# ── Private school fuzzy matching ──
SUFFIXES = ['school', 'academy', 'elementary', 'middle', 'high',
            'preparatory', 'prep', 'christian', 'catholic',
            'montessori', 'day school', 'learning center']

def strip_suffix(name):
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if name.endswith(s):
            return name[:-len(s)].strip()
    return name

def match_private(company_norm):
    if company_norm in all_private:
        return all_private[company_norm], "private DB exact"
    stripped = strip_suffix(company_norm)
    if stripped and stripped != company_norm:
        for pkey, pcounty in all_private.items():
            pstripped = strip_suffix(pkey)
            if stripped == pstripped and stripped:
                return pcounty, f"private DB fuzzy"
    return None, None

def normalize_company(name):
    key = name.lower().strip()
    key = re.sub(r'[^\w\s]', ' ', key)
    key = re.sub(r'\s+', ' ', key).strip()
    return key


# ══════════════════════════════════════════════════════════
# MAIN: Read original, apply all passes
# ══════════════════════════════════════════════════════════

INPUT = '/Users/stevenadkins/Downloads/My Leads - SoCal Only.csv'
OUTPUT = '/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv'
NORCAL_OUTPUT = '/Users/stevenadkins/Downloads/Leads_SoCal_Filtered_NORCAL_REMOVED.csv'

# Read original
with open(INPUT, encoding='latin-1') as f:
    reader = csv.DictReader(f)
    orig_headers = list(reader.fieldnames)
    all_rows = list(reader)

email_col_orig = orig_headers[0]  # 'Email'
out_email_col = '\xef\xbb\xbfEmail'  # matches the BOM-mangled name in latin-1

# Add new columns
out_headers = [out_email_col] + orig_headers[1:] + ['County', 'SoCal', 'County_Method']

print(f"\nOriginal: {len(all_rows)} records")
print("Applying passes 1-3 (offline lookups)...")

# Also load pass 4 Serper results from the NorCal removed file
# These are records that Serper identified as No
pass4_results = {}
with open(NORCAL_OUTPUT, 'r', encoding='latin-1') as f:
    reader = csv.DictReader(f)
    for r in reader:
        method = r.get('County_Method', '')
        if 'pass4' in method:
            email = r.get('\xef\xbb\xbfEmail', '').lower().strip()
            company = r.get('Company / Account', '').lower().strip()
            key = (email, company)
            pass4_results[key] = {
                'county': r.get('County', ''),
                'socal': 'No',
                'method': method,
            }

# Also load pass 4 Yes results from current kept file
with open(OUTPUT, 'r', encoding='latin-1') as f:
    reader = csv.DictReader(f)
    for r in reader:
        method = r.get('County_Method', '')
        if 'pass4' in method:
            email = r.get('\xef\xbb\xbfEmail', '').lower().strip()
            company = r.get('Company / Account', '').lower().strip()
            key = (email, company)
            pass4_results[key] = {
                'county': r.get('County', ''),
                'socal': r.get('SoCal', 'Yes'),
                'method': method,
            }

print(f"  Loaded {len(pass4_results)} pass 4 Serper results to replay")

stats = {'p1_school': 0, 'p1_district': 0, 'p1_zip': 0, 'p1_city': 0, 'p1_email': 0,
         'p2_parent': 0, 'p2_city_in_name': 0, 'p2_email_deep': 0,
         'p3_private': 0, 'p4_serper': 0}

for row in all_rows:
    company = row.get('Company / Account', '').strip()
    company_norm = normalize_company(company)
    email = row.get(email_col_orig, '').strip()
    city = row.get('City', '').strip().lower()
    zipcode = row.get('Zip/Postal Code', '').strip()

    county = None
    method = None

    # ── Pass 1: CDE public school name matching ──
    if company_norm in cde_schools:
        county = cde_schools[company_norm]
        method = 'pass1: CDE school name'
        stats['p1_school'] += 1

    # ── Pass 1: CDE district name matching ──
    if not county and company_norm in cde_districts:
        county = cde_districts[company_norm]
        method = 'pass1: CDE district name'
        stats['p1_district'] += 1

    # ── Pass 1: Zip code ──
    if not county and zipcode:
        zip5 = zipcode[:5]
        if zip5.isdigit():
            z = int(zip5)
            if 90001 <= z <= 93599:
                # Could be SoCal or Central CA
                if z <= 91899 or (93001 <= z <= 93599):
                    county = 'SoCal (by zip)'
                    method = f'pass1: zip {zip5}'
                    stats['p1_zip'] += 1
                elif 93600 <= z <= 93999:
                    county = 'Central CA (by zip)'
                    method = f'pass1: zip {zip5}'
                    stats['p1_zip'] += 1
            elif 94000 <= z <= 96199:
                county = 'NorCal (by zip)'
                method = f'pass1: zip {zip5}'
                stats['p1_zip'] += 1

    # ── Pass 1: City name ──
    if not county and city and city in SOCAL_CITIES:
        county = 'SoCal (by city)'
        method = f'pass1: city {city}'
        stats['p1_city'] += 1

    # ── Pass 1-2: Email domain ──
    if not county and email and '@' in email:
        domain = email.split('@')[-1].lower().strip()
        if domain in DOMAIN_COUNTY:
            county = DOMAIN_COUNTY[domain]
            method = f'pass1: email domain {domain}'
            stats['p1_email'] += 1

    # ── Pass 3: Private school DB matching ──
    if not county:
        priv_county, priv_method = match_private(company_norm)
        if priv_county:
            county = priv_county
            method = f'pass3: {priv_method}'
            stats['p3_private'] += 1

    # ── Pass 4: Apply saved Serper results ──
    if not county:
        email_lower = email.lower().strip()
        company_lower = company.lower().strip()
        key = (email_lower, company_lower)
        if key in pass4_results:
            p4 = pass4_results[key]
            county = p4['county']
            method = p4['method']
            stats['p4_serper'] += 1
            if p4['socal'] == 'No':
                row['_socal_override'] = 'No'

    # Determine SoCal status
    if county:
        if row.get('_socal_override') == 'No' or county == 'NON-CA':
            row['SoCal'] = 'No'
        elif county.lower() in SOCAL or 'SoCal' in county:
            row['SoCal'] = 'Yes'
        else:
            row['SoCal'] = 'No'
        row['County'] = county
        row['County_Method'] = method
    else:
        row['SoCal'] = 'Uncertain'
        row['County'] = ''
        row['County_Method'] = ''

    # Clean up temp field
    row.pop('_socal_override', None)

    # Rename email column
    row[out_email_col] = row.pop(email_col_orig, '')

# Stats
from collections import Counter
socal_counts = Counter(r['SoCal'] for r in all_rows)
print(f"\nPasses 1-4 results:")
print(f"  Pass 1 school: {stats['p1_school']}")
print(f"  Pass 1 district: {stats['p1_district']}")
print(f"  Pass 1 zip: {stats['p1_zip']}")
print(f"  Pass 1 city: {stats['p1_city']}")
print(f"  Pass 1-2 email: {stats['p1_email']}")
print(f"  Pass 3 private: {stats['p3_private']}")
print(f"  Pass 4 serper: {stats['p4_serper']}")
print(f"  → Yes: {socal_counts['Yes']}, No: {socal_counts['No']}, Uncertain: {socal_counts['Uncertain']}")

# Write output
kept = [r for r in all_rows if r['SoCal'] != 'No']
removed = [r for r in all_rows if r['SoCal'] == 'No']

with open(OUTPUT, 'w', encoding='latin-1', newline='', errors='replace') as f:
    writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(kept)

with open(NORCAL_OUTPUT, 'w', encoding='latin-1', newline='', errors='replace') as f:
    writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(removed)

yes_count = sum(1 for r in kept if r['SoCal'] == 'Yes')
unc_count = sum(1 for r in kept if r['SoCal'] == 'Uncertain')
print(f"\nOutput: {yes_count} SoCal + {unc_count} uncertain = {len(kept)} kept | {len(removed)} removed")
print(f"Written to {OUTPUT}")
print("Done! Now run pass 5.")
