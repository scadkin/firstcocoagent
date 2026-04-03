"""
tools/proximity_engine.py — C5: Proximity + Regional Service Center (ESA) prospecting.

Finds districts near Steven's active accounts (name-drop/FOMO) and maps districts
to their ESA (ESC/BOCES/IU/COE) for regional relationship leverage.

Uses NCES territory data (lat/lon, Agency Type 4 = ESAs) — no external geocoding needed.
"""

import logging
import math
from datetime import datetime

import tools.csv_importer as csv_importer
import tools.territory_data as territory_data
import tools.district_prospector as district_prospector

logger = logging.getLogger(__name__)

# Agency types to prospect (regular districts only)
_PROSPECTABLE_AGENCY_TYPES = {
    "Regular local school district",
    "Local school district (component of supervisory union)",
    "Charter school agency",
    "Specialized public school district",
}

_ESA_AGENCY_TYPE = "Regional education service agency"


# ─────────────────────────────────────────────
# HAVERSINE
# ─────────────────────────────────────────────

def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in miles."""
    R = 3958.8  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _parse_float(val) -> float | None:
    """Parse a float from a string or number, returning None on failure."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _normalize_state(state_input: str) -> str:
    """Normalize state input to 2-letter abbreviation using territory_data's normalizer."""
    return territory_data._normalize_state(state_input)


def _get_active_account_locations(state: str) -> list[dict]:
    """
    Get lat/lon for active accounts by matching against NCES territory data.

    Returns list of {name, name_key, lat, lon, account_type}.
    Unmatched accounts are logged and skipped.
    """
    accounts = csv_importer.get_active_accounts(state)
    if not accounts:
        return []

    # Load territory districts + schools for matching
    districts = territory_data._load_territory_districts(state)
    schools = territory_data._load_territory_schools(state)

    # Build lookup dicts by Name Key
    district_geo = {}
    for d in districts:
        nk = d.get("Name Key", "")
        lat = _parse_float(d.get("Lat"))
        lon = _parse_float(d.get("Lon"))
        if nk and lat is not None and lon is not None:
            district_geo[nk] = (lat, lon)

    school_geo = {}
    for s in schools:
        nk = s.get("Name Key", "")
        lat = _parse_float(s.get("Lat"))
        lon = _parse_float(s.get("Lon"))
        if nk and lat is not None and lon is not None:
            school_geo[nk] = (lat, lon)

    locations = []
    unmatched = []
    for acc in accounts:
        display = acc.get("Active Account Name", "") or acc.get("Display Name", "")
        name_key = acc.get("Name Key", "") or csv_importer.normalize_name(display)
        acc_type = acc.get("Account Type", "")

        # Try district match first, then school
        geo = district_geo.get(name_key) or school_geo.get(name_key)
        if geo:
            locations.append({
                "name": display,
                "name_key": name_key,
                "lat": geo[0],
                "lon": geo[1],
                "account_type": acc_type,
            })
        else:
            unmatched.append(display)

    if unmatched:
        logger.info(f"Proximity: {len(unmatched)} active accounts unmatched to NCES data: {unmatched[:10]}")

    return locations


# ─────────────────────────────────────────────
# PROXIMITY: FIND NEARBY DISTRICTS
# ─────────────────────────────────────────────

def find_nearby_districts(state: str, radius_miles: float = 30,
                          min_enrollment: int = 500) -> dict:
    """
    Find NCES districts within radius of Steven's active accounts.

    Returns {success, state, radius_miles, total_found, matched_accounts, unmatched_accounts,
             nearby_districts: [{name, name_key, enrollment, city, county, agency_type,
                                 nearest_account, distance_miles, score}],
             error}
    """
    state = _normalize_state(state)
    if not state:
        return {"success": False, "error": "Unknown state. Use abbreviation or full name."}

    # Get active account locations
    account_locs = _get_active_account_locations(state)
    if not account_locs:
        return {
            "success": False,
            "error": f"No active accounts found in {state}, or none matched NCES data.",
        }

    # Load territory districts
    all_districts = territory_data._load_territory_districts(state)

    # Build sets for exclusion
    active_keys = {a.get("Name Key", "") or csv_importer.normalize_name(
        a.get("Active Account Name", "") or a.get("Display Name", ""))
        for a in csv_importer.get_active_accounts(state)}
    prospect_keys = {p.get("Name Key", "") for p in district_prospector.get_all_prospects()}

    nearby = []
    for dist in all_districts:
        # Only prospect regular districts
        agency_type = dist.get("Agency Type", "")
        if agency_type not in _PROSPECTABLE_AGENCY_TYPES:
            continue

        name_key = dist.get("Name Key", "")
        if not name_key:
            continue

        # Skip if already active or in queue
        if name_key in active_keys or name_key in prospect_keys:
            continue

        # Check enrollment minimum
        enrollment = 0
        try:
            enrollment = int(dist.get("Enrollment", 0) or 0)
        except (ValueError, TypeError):
            pass
        if enrollment < min_enrollment:
            continue

        # Get lat/lon
        lat = _parse_float(dist.get("Lat"))
        lon = _parse_float(dist.get("Lon"))
        if lat is None or lon is None:
            continue

        # Find nearest active account
        min_dist = float("inf")
        nearest_name = ""
        for acc in account_locs:
            d = haversine_miles(lat, lon, acc["lat"], acc["lon"])
            if d < min_dist:
                min_dist = d
                nearest_name = acc["name"]

        if min_dist <= radius_miles:
            # Composite score: closer + bigger enrollment = higher
            # Distance component: 100 for 0 mi, 0 for radius_miles
            dist_score = max(0, 100 * (1 - min_dist / radius_miles))
            # Enrollment component: capped at 100
            enroll_score = min(100, enrollment / 250)
            score = dist_score * 0.6 + enroll_score * 0.4

            nearby.append({
                "name": dist.get("District Name", ""),
                "name_key": name_key,
                "enrollment": enrollment,
                "city": dist.get("City", ""),
                "county": dist.get("County", ""),
                "agency_type": agency_type,
                "nearest_account": nearest_name,
                "distance_miles": round(min_dist, 1),
                "score": round(score, 1),
            })

    # Sort by score descending
    nearby.sort(key=lambda x: x["score"], reverse=True)

    return {
        "success": True,
        "state": state,
        "radius_miles": radius_miles,
        "total_found": len(nearby),
        "matched_accounts": len(account_locs),
        "nearby_districts": nearby,
    }


def add_proximity_prospects(state: str, radius_miles: float = 30,
                            max_add: int = 25, min_enrollment: int = 500) -> dict:
    """
    Find nearby districts and add top ones to the Prospecting Queue.

    Returns {success, state, radius_miles, new_added, already_known,
             districts: [{name, nearest_account, distance_miles}], error}
    """
    result = find_nearby_districts(state, radius_miles, min_enrollment)
    if not result["success"]:
        return result

    nearby = result["nearby_districts"][:max_add]
    if not nearby:
        return {
            "success": True,
            "state": state,
            "radius_miles": radius_miles,
            "new_added": 0,
            "already_known": 0,
            "districts": [],
            "error": f"No uncovered districts found within {radius_miles} mi of active accounts in {state}.",
        }

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    added_districts = []

    for d in nearby:
        priority = district_prospector._calculate_priority(
            "proximity", 0, 0, d["enrollment"],
            distance_miles=d["distance_miles"],
        )
        note = f"Near {d['nearest_account']} ({d['distance_miles']} mi)"
        if d.get("city"):
            note += f" — {d['city']}"

        row = [
            state,                    # State
            d["name"],                # Account Name
            "",                       # Email
            "",                       # First Name
            "",                       # Last Name
            "district",               # Deal Level
            "",                       # Parent District
            d["name_key"],            # Name Key
            "proximity",              # Strategy
            "proximity_auto",         # Source
            "pending",                # Status
            str(priority),            # Priority
            now,                      # Date Added
            "",                       # Date Approved
            "",                       # Sequence Doc URL
            str(d["enrollment"]),     # Est. Enrollment
            "",                       # School Count
            "",                       # Total Licenses
            note,                     # Notes
        ]
        rows.append(row)
        added_districts.append({
            "name": d["name"],
            "nearest_account": d["nearest_account"],
            "distance_miles": d["distance_miles"],
            "enrollment": d["enrollment"],
            "city": d.get("city", ""),
        })

    district_prospector._write_rows(rows)
    logger.info(f"Proximity: added {len(rows)} districts to Prospecting Queue for {state}")

    return {
        "success": True,
        "state": state,
        "radius_miles": radius_miles,
        "new_added": len(rows),
        "already_known": result["total_found"] - len(nearby),
        "total_nearby": result["total_found"],
        "matched_accounts": result["matched_accounts"],
        "districts": added_districts,
    }


# ─────────────────────────────────────────────
# ESA: REGIONAL SERVICE CENTER MAPPING
# ─────────────────────────────────────────────

def get_esa_districts(state: str) -> list[dict]:
    """
    Return all Agency Type 4 (Regional education service agency) entries for a state.
    These are the ESCs/BOCES/IUs/COEs themselves.
    """
    state = _normalize_state(state)
    if not state:
        return []

    all_districts = territory_data._load_territory_districts(state)
    esas = []
    for d in all_districts:
        if d.get("Agency Type", "") == _ESA_AGENCY_TYPE:
            lat = _parse_float(d.get("Lat"))
            lon = _parse_float(d.get("Lon"))
            esas.append({
                "name": d.get("District Name", ""),
                "name_key": d.get("Name Key", ""),
                "leaid": d.get("LEAID", ""),
                "county_code": d.get("County Code", ""),
                "county": d.get("County", ""),
                "city": d.get("City", ""),
                "lat": lat,
                "lon": lon,
                "state": state,
            })
    return esas


def map_districts_to_esa(state: str) -> dict:
    """
    Map each regular district to its nearest ESA.

    Algorithm: county_code match first, then haversine fallback.

    Returns {success, state, esa_count, district_count,
             esa_map: {esa_name: {leaid, county_code, county, city, lat, lon,
                                   districts: [{name, enrollment, distance_miles, city}],
                                   total_enrollment, district_count}},
             unmapped_count, error}
    """
    state = _normalize_state(state)
    if not state:
        return {"success": False, "error": "Unknown state."}

    from agent.target_roles import REGIONAL_ENTITIES
    entity_info = REGIONAL_ENTITIES.get(state)
    if entity_info and entity_info[0] is None:
        return {
            "success": True,
            "state": state,
            "esa_count": 0,
            "district_count": 0,
            "esa_map": {},
            "unmapped_count": 0,
            "no_esa_system": True,
            "error": f"No ESA system established by law in {state}.",
        }

    esas = get_esa_districts(state)
    all_districts = territory_data._load_territory_districts(state)

    # Separate regular districts
    regular = [d for d in all_districts if d.get("Agency Type", "") in _PROSPECTABLE_AGENCY_TYPES]

    if not esas:
        return {
            "success": True,
            "state": state,
            "esa_count": 0,
            "district_count": len(regular),
            "esa_map": {},
            "unmapped_count": len(regular),
            "error": f"No Agency Type 4 entries found in NCES data for {state}.",
        }

    # Build ESA map
    esa_map = {}
    for esa in esas:
        esa_map[esa["name"]] = {
            "leaid": esa["leaid"],
            "county_code": esa["county_code"],
            "county": esa.get("county", ""),
            "city": esa.get("city", ""),
            "lat": esa["lat"],
            "lon": esa["lon"],
            "districts": [],
            "total_enrollment": 0,
            "district_count": 0,
        }

    # Build county_code → ESA lookup
    county_to_esa = {}
    for esa in esas:
        cc = esa.get("county_code", "")
        if cc:
            county_to_esa[cc] = esa["name"]

    unmapped = 0
    for dist in regular:
        name = dist.get("District Name", "")
        enrollment = 0
        try:
            enrollment = int(dist.get("Enrollment", 0) or 0)
        except (ValueError, TypeError):
            pass

        lat = _parse_float(dist.get("Lat"))
        lon = _parse_float(dist.get("Lon"))
        cc = dist.get("County Code", "")
        city = dist.get("City", "")

        # Try county_code match first
        assigned_esa = county_to_esa.get(cc)

        # Fallback: nearest ESA by distance
        if not assigned_esa and lat is not None and lon is not None:
            min_d = float("inf")
            for esa in esas:
                if esa["lat"] is not None and esa["lon"] is not None:
                    d = haversine_miles(lat, lon, esa["lat"], esa["lon"])
                    if d < min_d:
                        min_d = d
                        assigned_esa = esa["name"]

        if assigned_esa and assigned_esa in esa_map:
            distance = 0.0
            if lat is not None and lon is not None:
                esa_info = esa_map[assigned_esa]
                if esa_info["lat"] is not None and esa_info["lon"] is not None:
                    distance = haversine_miles(lat, lon, esa_info["lat"], esa_info["lon"])

            esa_map[assigned_esa]["districts"].append({
                "name": name,
                "enrollment": enrollment,
                "distance_miles": round(distance, 1),
                "city": city,
            })
            esa_map[assigned_esa]["total_enrollment"] += enrollment
            esa_map[assigned_esa]["district_count"] += 1
        else:
            unmapped += 1

    return {
        "success": True,
        "state": state,
        "esa_count": len(esas),
        "district_count": len(regular),
        "esa_map": esa_map,
        "unmapped_count": unmapped,
    }


def find_esa_opportunities(state: str) -> dict:
    """
    Find ESAs where Steven has active accounts — regional relationship leverage.

    Returns {success, state, esa_opportunities: [{esa_name, city, county,
             active_account_count, active_accounts: [str],
             uncovered_count, uncovered_enrollment,
             top_targets: [{name, enrollment, city}]}],
             total_esa, no_esa_system, error}
    """
    mapping = map_districts_to_esa(state)
    if not mapping["success"]:
        return mapping
    if mapping.get("no_esa_system"):
        return mapping

    state_norm = mapping["state"]
    esa_map = mapping["esa_map"]

    if not esa_map:
        return {
            "success": True,
            "state": state_norm,
            "esa_opportunities": [],
            "total_esa": 0,
            "error": f"No ESAs found in NCES data for {state_norm}.",
        }

    # Get active account keys
    active_accounts = csv_importer.get_active_accounts(state_norm)
    active_keys = {}
    for a in active_accounts:
        display = a.get("Active Account Name", "") or a.get("Display Name", "")
        nk = a.get("Name Key", "") or csv_importer.normalize_name(display)
        active_keys[nk] = display

    # Get prospect queue keys
    prospect_keys = {p.get("Name Key", "") for p in district_prospector.get_all_prospects()}

    opportunities = []
    for esa_name, esa_info in esa_map.items():
        # Check which districts in this ESA region are active accounts
        active_in_region = []
        uncovered = []

        for d in esa_info["districts"]:
            dk = csv_importer.normalize_name(d["name"])
            if dk in active_keys:
                active_in_region.append(active_keys[dk])
            elif dk not in prospect_keys:
                uncovered.append(d)

        # Sort uncovered by enrollment desc
        uncovered.sort(key=lambda x: x.get("enrollment", 0), reverse=True)

        uncovered_enrollment = sum(d.get("enrollment", 0) for d in uncovered)

        opportunities.append({
            "esa_name": esa_name,
            "city": esa_info.get("city", ""),
            "county": esa_info.get("county", ""),
            "total_districts": esa_info["district_count"],
            "active_account_count": len(active_in_region),
            "active_accounts": active_in_region,
            "uncovered_count": len(uncovered),
            "uncovered_enrollment": uncovered_enrollment,
            "top_targets": uncovered[:5],
        })

    # Sort: ESAs with active accounts first, then by uncovered enrollment
    opportunities.sort(
        key=lambda x: (x["active_account_count"] > 0, x["active_account_count"],
                       x["uncovered_enrollment"]),
        reverse=True,
    )

    return {
        "success": True,
        "state": state_norm,
        "esa_opportunities": opportunities,
        "total_esa": len(opportunities),
    }


# ─────────────────────────────────────────────
# TELEGRAM FORMATTING
# ─────────────────────────────────────────────

def format_proximity_for_telegram(result: dict, max_show: int = 15) -> str:
    """Format proximity results for Telegram."""
    if not result.get("success"):
        return f"❌ {result.get('error', 'Unknown error')}"

    state = result["state"]
    total = result.get("total_nearby", result.get("total_found", 0))
    added = result.get("new_added", 0)
    matched = result.get("matched_accounts", 0)
    radius = result.get("radius_miles", 30)
    districts = result.get("districts", [])

    lines = [
        f"📍 *Proximity Search: {state}*",
        f"Radius: {radius} mi | Active accounts matched: {matched}",
        f"Found: {total} nearby districts | Added to queue: {added}",
        "",
    ]

    if not districts:
        lines.append("No new districts found within range.")
        return "\n".join(lines)

    for i, d in enumerate(districts[:max_show], 1):
        enrollment_str = f"{d['enrollment']:,}" if d.get("enrollment") else "?"
        city_str = f" ({d['city']})" if d.get("city") else ""
        lines.append(
            f"{i}. *{d['name']}*{city_str}\n"
            f"   📏 {d['distance_miles']} mi from {d['nearest_account']} | "
            f"🎓 {enrollment_str} students"
        )

    if total > max_show:
        lines.append(f"\n_{total - max_show} more in Prospecting Queue_")

    return "\n".join(lines)


def format_esa_for_telegram(result: dict, max_show: int = 10) -> str:
    """Format ESA opportunity results for Telegram."""
    if not result.get("success"):
        return f"❌ {result.get('error', 'Unknown error')}"
    if result.get("no_esa_system"):
        return f"ℹ️ {result['state']}: {result.get('error', 'No ESA system.')}"

    state = result["state"]
    opps = result.get("esa_opportunities", [])
    total_esa = result.get("total_esa", 0)

    lines = [
        f"🏛️ *ESA Opportunities: {state}*",
        f"Total ESAs: {total_esa}",
        "",
    ]

    if not opps:
        lines.append("No ESA data found.")
        return "\n".join(lines)

    # Show ESAs with active accounts first
    has_active = [o for o in opps if o["active_account_count"] > 0]
    no_active = [o for o in opps if o["active_account_count"] == 0]

    if has_active:
        lines.append("*🟢 ESAs with your active accounts:*")
        for o in has_active[:max_show]:
            city_str = f" ({o['city']})" if o.get("city") else ""
            lines.append(
                f"  *{o['esa_name']}*{city_str}\n"
                f"    ✅ {o['active_account_count']} active: {', '.join(o['active_accounts'][:3])}"
            )
            if len(o["active_accounts"]) > 3:
                lines[-1] += f" +{len(o['active_accounts']) - 3} more"
            lines.append(
                f"    🎯 {o['uncovered_count']} uncovered districts "
                f"({o['uncovered_enrollment']:,} students)"
            )
            if o["top_targets"]:
                targets = [f"{t['name']}" for t in o["top_targets"][:3]]
                lines.append(f"    Top targets: {', '.join(targets)}")
        lines.append("")

    if no_active:
        lines.append(f"*⚪ {len(no_active)} ESAs with no active accounts*")
        # Show top 3 by uncovered enrollment
        top_cold = sorted(no_active, key=lambda x: x["uncovered_enrollment"], reverse=True)[:3]
        for o in top_cold:
            city_str = f" ({o['city']})" if o.get("city") else ""
            lines.append(
                f"  {o['esa_name']}{city_str} — "
                f"{o['uncovered_count']} districts, "
                f"{o['uncovered_enrollment']:,} students"
            )

    return "\n".join(lines)
