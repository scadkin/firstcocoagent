"""Pass 3: Match uncertain records against CDE + NCES private school databases."""
import csv
import re
import openpyxl

# ── Load CDE private schools ──
wb = openpyxl.load_workbook('/tmp/cde_private_schools.xlsx', read_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

cde_private = {}
for row in rows[6:]:
    school_name = str(row[3]).strip() if row[3] else ''
    county = str(row[1]).strip() if row[1] else ''
    if school_name and county:
        key = school_name.lower().strip()
        key = re.sub(r'[^\w\s]', ' ', key)
        key = re.sub(r'\s+', ' ', key).strip()
        cde_private[key] = county
wb.close()

# ── Load NCES private schools ──
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

# Merge (CDE takes priority)
all_private = dict(nces_private)
all_private.update(cde_private)
print(f'CDE private: {len(cde_private)}, NCES private: {len(nces_private)}, Combined unique: {len(all_private)}')

SOCAL = {'los angeles', 'san diego', 'orange', 'riverside', 'san bernardino',
         'kern', 'ventura', 'santa barbara', 'san luis obispo', 'imperial'}

SUFFIXES = ['school', 'academy', 'elementary', 'middle', 'high',
            'preparatory', 'prep', 'christian', 'catholic',
            'montessori', 'day school', 'learning center']


def strip_suffix(name):
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if name.endswith(s):
            return name[:-len(s)].strip()
    return name


def match_private(company_norm):
    """Try exact then fuzzy match against private school DBs."""
    if company_norm in all_private:
        return all_private[company_norm], "exact"

    stripped = strip_suffix(company_norm)
    if stripped and stripped != company_norm:
        for pkey, pcounty in all_private.items():
            pstripped = strip_suffix(pkey)
            if stripped == pstripped and stripped:
                return pcounty, f"fuzzy '{pkey}'"
    return None, None


def process_file(path, company_col, label):
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames)
        all_rows = list(reader)

    resolved_rows = [r for r in all_rows if r.get('SoCal') != 'Uncertain']
    uncertain = [r for r in all_rows if r.get('SoCal') == 'Uncertain']

    matched = 0
    newly_socal = 0
    newly_norcal = 0

    for row in uncertain:
        company = row.get(company_col, '').strip().lower()
        company_norm = re.sub(r'[^\w\s]', ' ', company)
        company_norm = re.sub(r'\s+', ' ', company_norm).strip()

        county, method = match_private(company_norm)

        if county:
            matched += 1
            row['County'] = county
            row['County_Method'] = f'pass3: private school DB ({method})'
            if county.lower() in SOCAL:
                row['SoCal'] = 'Yes'
                newly_socal += 1
            else:
                row['SoCal'] = 'No'
                newly_norcal += 1

    all_updated = resolved_rows + uncertain
    kept = [r for r in all_updated if r['SoCal'] != 'No']
    removed = [r for r in all_updated if r['SoCal'] == 'No']

    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(kept)

    norcal_path = path.replace('.csv', '_NORCAL_REMOVED.csv')
    with open(norcal_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(removed)

    still_uncertain = sum(1 for r in kept if r['SoCal'] == 'Uncertain')
    socal_total = sum(1 for r in kept if r['SoCal'] == 'Yes')

    print(f'\n{label}:')
    print(f'  Private school matches: {matched} ({newly_socal} SoCal, {newly_norcal} NorCal)')
    print(f'  Final: {socal_total} SoCal + {still_uncertain} uncertain = {len(kept)} kept | {len(removed)} removed')


process_file('/Users/stevenadkins/Downloads/Leads_SoCal_Filtered.csv', 'Company / Account', 'LEADS')
process_file('/Users/stevenadkins/Downloads/Contacts_SoCal_Filtered.csv', 'Account Name', 'CONTACTS')
