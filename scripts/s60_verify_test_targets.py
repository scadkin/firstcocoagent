"""Verify 5 candidate A/B test targets against territory_data (NCES master list)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import tools.territory_data as territory_data
import tools.csv_importer as csv_importer

CANDIDATES = [
    ("Cypress-Fairbanks ISD", "TX", "large"),
    ("Cincinnati Public Schools", "OH", "medium"),
    ("Conejo Valley USD", "CA", "medium"),
    ("Park Ridge-Niles CCSD 64", "IL", "small"),
    ("Waverly School District 145", "NE", "small"),
]

print("=" * 70)
print("TERRITORY MASTER LIST VERIFICATION (NCES)")
print("=" * 70)

for name, state, tier in CANDIDATES:
    print(f"\n--- {name} ({state}, expected tier: {tier}) ---")
    enrollment = territory_data.lookup_district_enrollment(name, state)
    if enrollment > 0:
        # Tier classification
        if enrollment >= 50000:
            actual_tier = "LARGE (≥50k)"
        elif enrollment >= 10000:
            actual_tier = "MEDIUM (10k-50k)"
        elif enrollment >= 2000:
            actual_tier = "SMALL (2k-10k)"
        else:
            actual_tier = "TINY (<2k)"
        print(f"  ✓ found in territory: enrollment={enrollment:,} → {actual_tier}")
    else:
        print(f"  ✗ NOT FOUND in territory_data for {state}")
        # Try fuzzy across all states for a better candidate name
        print(f"    (fuzzy-searching {state} districts for closest name match...)")
        all_districts = territory_data._load_territory_districts(state)
        target_key = csv_importer.normalize_name(name)
        target_tokens = set(t for t in target_key.split() if len(t) >= 3)
        best = None
        best_score = 0
        for d in all_districts:
            d_name = d.get("District Name", "")
            d_key = csv_importer.normalize_name(d_name)
            d_tokens = set(t for t in d_key.split() if len(t) >= 3)
            if not d_tokens:
                continue
            overlap = len(target_tokens & d_tokens)
            if overlap > best_score:
                best_score = overlap
                best = d
        if best:
            enr = best.get("Enrollment", "?")
            print(f"    closest: {best.get('District Name', '?')} (enrollment={enr})")

# Also dump a sample of each state's top 5 largest public districts as
# substitute candidates in case any miss
print()
print("=" * 70)
print("FALLBACK CANDIDATES — top 5 largest public districts per state")
print("=" * 70)

from collections import defaultdict

for state in ("TX", "OH", "CA", "IL", "NE"):
    districts = territory_data._load_territory_districts(state)
    # Sort by enrollment
    sortable = []
    for d in districts:
        try:
            enr = int(d.get("Enrollment") or 0)
        except (ValueError, TypeError):
            enr = 0
        sortable.append((enr, d.get("District Name", "")))
    sortable.sort(reverse=True)
    print(f"\n{state} top 5 largest (total territory districts in state: {len(districts)}):")
    for enr, name in sortable[:5]:
        print(f"  {enr:>8,}  {name}")
    # Also show some small ones
    small_candidates = [(e, n) for e, n in sortable if 1500 <= e <= 6000]
    if small_candidates:
        print(f"{state} small-tier candidates (1.5k-6k enrollment, sample 5):")
        for enr, name in small_candidates[:5]:
            print(f"  {enr:>8,}  {name}")
