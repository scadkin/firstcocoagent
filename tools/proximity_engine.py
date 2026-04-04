"""
tools/proximity_engine.py — C5: Proximity + Regional Service Center (ESA) prospecting.

Finds districts/schools near a specific active account (name-drop/FOMO) and maps
districts to their ESA (ESC/BOCES/IU/COE) for regional relationship leverage.

Uses NCES territory data (lat/lon, Agency Type 4 = ESAs) — no external geocoding needed.

Two modes:
  - Targeted (default): "proximity Leander ISD" → find what's near one account
  - State sweep: "proximity Texas all" → find nearby districts for ALL accounts in a state
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

def _parse_float(val):
    """Parse a float from a string or number, returning None on failure."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _normalize_state(state_input: str) -> str:
    """Normalize state input to 2-letter abbreviation."""
    return territory_data._normalize_state(state_input)


def _find_account_location(account_name: str):
    """
    Find lat/lon for a specific account by matching against NCES territory data.
    Searches all states since the user may not specify one.

    Returns {name, name_key, lat, lon, state, account_type, match_source} or None.
    """
    name_key = csv_importer.normalize_name(account_name)

    # First check Active Accounts to find the state
    all_accounts = csv_importer.get_active_accounts()
    matched_account = None
    for acc in all_accounts:
        display = acc.get("Active Account Name", "") or acc.get("Display Name", "")
        ak = acc.get("Name Key", "") or csv_importer.normalize_name(display)
        if ak == name_key:
            matched_account = acc
            break

    # Also try partial match if exact fails
    if not matched_account:
        for acc in all_accounts:
            display = acc.get("Active Account Name", "") or acc.get("Display Name", "")
            ak = acc.get("Name Key", "") or csv_importer.normalize_name(display)
            if name_key in ak or ak in name_key:
                matched_account = acc
                break

    if not matched_account:
        return None

    display = matched_account.get("Active Account Name", "") or matched_account.get("Display Name", "")
    state = matched_account.get("State", "").strip().upper()
    acc_type = matched_account.get("Account Type", "")
    mk = matched_account.get("Name Key", "") or csv_importer.normalize_name(display)

    if not state:
        return None

    # Find lat/lon from NCES data
    districts = territory_data._load_territory_districts(state)
    for d in districts:
        if d.get("Name Key", "") == mk:
            lat = _parse_float(d.get("Lat"))
            lon = _parse_float(d.get("Lon"))
            if lat is not None and lon is not None:
                return {
                    "name": display, "name_key": mk, "lat": lat, "lon": lon,
                    "state": state, "account_type": acc_type, "match_source": "district",
                }

    schools = territory_data._load_territory_schools(state)
    for s in schools:
        if s.get("Name Key", "") == mk:
            lat = _parse_float(s.get("Lat"))
            lon = _parse_float(s.get("Lon"))
            if lat is not None and lon is not None:
                return {
                    "name": display, "name_key": mk, "lat": lat, "lon": lon,
                    "state": state, "account_type": acc_type, "match_source": "school",
                }

    return None


def _get_active_account_locations(state: str) -> list:
    """
    Get lat/lon for ALL active accounts in a state.
    Returns list of {name, name_key, lat, lon, account_type}.
    """
    accounts = csv_importer.get_active_accounts(state)
    if not accounts:
        return []

    districts = territory_data._load_territory_districts(state)
    schools = territory_data._load_territory_schools(state)

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
    for acc in accounts:
        display = acc.get("Active Account Name", "") or acc.get("Display Name", "")
        name_key = acc.get("Name Key", "") or csv_importer.normalize_name(display)
        acc_type = acc.get("Account Type", "")
        geo = district_geo.get(name_key) or school_geo.get(name_key)
        if geo:
            locations.append({
                "name": display, "name_key": name_key,
                "lat": geo[0], "lon": geo[1], "account_type": acc_type,
            })
    return locations


def _build_exclusion_sets(state: str):
    """Build sets of Name Keys for active accounts + prospecting queue."""
    active_keys = set()
    for a in csv_importer.get_active_accounts(state):
        display = a.get("Active Account Name", "") or a.get("Display Name", "")
        nk = a.get("Name Key", "") or csv_importer.normalize_name(display)
        active_keys.add(nk)
    prospect_keys = {p.get("Name Key", "") for p in district_prospector.get_all_prospects()}
    return active_keys, prospect_keys


# ─────────────────────────────────────────────
# TARGETED PROXIMITY: NEAR ONE ACCOUNT
# ─────────────────────────────────────────────

def find_nearby_one(account_name: str, radius_miles: float = 15,
                    min_enrollment: int = 0) -> dict:
    """
    Find districts and schools near ONE specific active account.

    Default radius is 15 miles. Results are display-only (not auto-added to queue).
    If few results, suggests widening radius. If many, suggests narrowing.

    Returns {success, account_name, state, radius_miles, origin_lat, origin_lon,
             nearby_districts: [{name, name_key, enrollment, city, distance_miles, agency_type}],
             nearby_schools: [{name, name_key, district_name, enrollment, city, distance_miles}],
             suggestion, error}
    """
    loc = _find_account_location(account_name)
    if not loc:
        return {
            "success": False,
            "error": (
                f"Could not find '{account_name}' in Active Accounts, "
                f"or could not match it to NCES territory data for lat/lon."
            ),
        }

    state = loc["state"]
    origin_lat, origin_lon = loc["lat"], loc["lon"]
    active_keys, prospect_keys = _build_exclusion_sets(state)

    # Find nearby districts
    all_districts = territory_data._load_territory_districts(state)
    nearby_districts = []
    for dist in all_districts:
        agency_type = dist.get("Agency Type", "")
        if agency_type not in _PROSPECTABLE_AGENCY_TYPES:
            continue
        name_key = dist.get("Name Key", "")
        if not name_key or name_key in active_keys:
            continue

        lat = _parse_float(dist.get("Lat"))
        lon = _parse_float(dist.get("Lon"))
        if lat is None or lon is None:
            continue

        enrollment = 0
        try:
            enrollment = int(dist.get("Enrollment", 0) or 0)
        except (ValueError, TypeError):
            pass
        if enrollment < min_enrollment:
            continue

        d = haversine_miles(origin_lat, origin_lon, lat, lon)
        if d <= radius_miles:
            in_queue = name_key in prospect_keys
            nearby_districts.append({
                "name": dist.get("District Name", ""),
                "name_key": name_key,
                "enrollment": enrollment,
                "city": dist.get("City", ""),
                "distance_miles": round(d, 1),
                "agency_type": agency_type,
                "in_queue": in_queue,
            })

    nearby_districts.sort(key=lambda x: x["distance_miles"])

    # Find nearby schools (from other districts, not the origin's own schools)
    all_schools = territory_data._load_territory_schools(state)
    nearby_schools = []
    for sch in all_schools:
        nk = sch.get("Name Key", "")
        if not nk or nk in active_keys:
            continue

        lat = _parse_float(sch.get("Lat"))
        lon = _parse_float(sch.get("Lon"))
        if lat is None or lon is None:
            continue

        enrollment = 0
        try:
            enrollment = int(sch.get("Enrollment", 0) or 0)
        except (ValueError, TypeError):
            pass

        d = haversine_miles(origin_lat, origin_lon, lat, lon)
        if d <= radius_miles:
            nearby_schools.append({
                "name": sch.get("School Name", ""),
                "name_key": nk,
                "district_name": sch.get("District Name", ""),
                "enrollment": enrollment,
                "city": sch.get("City", ""),
                "distance_miles": round(d, 1),
            })

    nearby_schools.sort(key=lambda x: x["distance_miles"])

    # Adaptive radius suggestion
    total = len(nearby_districts)
    suggestion = ""
    if total == 0:
        suggestion = f"No districts found within {radius_miles} mi. Try widening: `proximity {account_name} {int(radius_miles * 2)}`"
    elif total <= 3:
        suggestion = f"Only {total} districts found. Try widening: `proximity {account_name} {int(radius_miles * 2)}`"
    elif total > 30:
        suggestion = f"{total} districts is a lot. Try narrowing: `proximity {account_name} {int(radius_miles / 2)}`"

    return {
        "success": True,
        "account_name": loc["name"],
        "state": state,
        "radius_miles": radius_miles,
        "origin_lat": origin_lat,
        "origin_lon": origin_lon,
        "nearby_districts": nearby_districts,
        "nearby_schools": nearby_schools,
        "district_count": len(nearby_districts),
        "school_count": len(nearby_schools),
        "suggestion": suggestion,
    }


# ─────────────────────────────────────────────
# STATE SWEEP: ALL ACCOUNTS IN A STATE
# ─────────────────────────────────────────────

def find_nearby_state(state: str, radius_miles: float = 30,
                      min_enrollment: int = 500) -> dict:
    """
    Find NCES districts within radius of ANY active account in a state.
    Bulk mode — for full state overview.

    Returns {success, state, radius_miles, total_found, matched_accounts,
             nearby_districts: [{name, name_key, enrollment, city, nearest_account,
                                 distance_miles, score}], error}
    """
    state = _normalize_state(state)
    if not state:
        return {"success": False, "error": "Unknown state."}

    account_locs = _get_active_account_locations(state)
    if not account_locs:
        return {"success": False, "error": f"No active accounts matched NCES data in {state}."}

    all_districts = territory_data._load_territory_districts(state)
    active_keys, prospect_keys = _build_exclusion_sets(state)

    nearby = []
    for dist in all_districts:
        agency_type = dist.get("Agency Type", "")
        if agency_type not in _PROSPECTABLE_AGENCY_TYPES:
            continue
        name_key = dist.get("Name Key", "")
        if not name_key or name_key in active_keys or name_key in prospect_keys:
            continue

        enrollment = 0
        try:
            enrollment = int(dist.get("Enrollment", 0) or 0)
        except (ValueError, TypeError):
            pass
        if enrollment < min_enrollment:
            continue

        lat = _parse_float(dist.get("Lat"))
        lon = _parse_float(dist.get("Lon"))
        if lat is None or lon is None:
            continue

        min_dist = float("inf")
        nearest_name = ""
        for acc in account_locs:
            d = haversine_miles(lat, lon, acc["lat"], acc["lon"])
            if d < min_dist:
                min_dist = d
                nearest_name = acc["name"]

        if min_dist <= radius_miles:
            dist_score = max(0, 100 * (1 - min_dist / radius_miles))
            enroll_score = min(100, enrollment / 250)
            score = dist_score * 0.6 + enroll_score * 0.4
            nearby.append({
                "name": dist.get("District Name", ""),
                "name_key": name_key,
                "enrollment": enrollment,
                "city": dist.get("City", ""),
                "nearest_account": nearest_name,
                "distance_miles": round(min_dist, 1),
                "score": round(score, 1),
            })

    nearby.sort(key=lambda x: x["score"], reverse=True)

    return {
        "success": True,
        "state": state,
        "radius_miles": radius_miles,
        "total_found": len(nearby),
        "matched_accounts": len(account_locs),
        "nearby_districts": nearby,
    }


def add_proximity_prospects(districts: list, state: str, reference_account: str = "") -> dict:
    """
    Add a list of districts to the Prospecting Queue with strategy="proximity".

    districts: list of {name, name_key, enrollment, distance_miles, city, nearest_account}
    """
    if not districts:
        return {"success": True, "new_added": 0}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for d in districts:
        nearest = d.get("nearest_account", reference_account) or reference_account
        priority = district_prospector._calculate_priority(
            "proximity", 0, 0, d.get("enrollment", 0),
            distance_miles=d.get("distance_miles", 50),
        )
        note = f"Near {nearest} ({d.get('distance_miles', '?')} mi)"
        if d.get("city"):
            note += f" — {d['city']}"

        row = [
            state,                         # State
            d.get("name", ""),             # Account Name
            "",                            # Email
            "",                            # First Name
            "",                            # Last Name
            "district",                    # Deal Level
            "",                            # Parent District
            d.get("name_key", ""),         # Name Key
            "proximity",                   # Strategy
            "proximity_auto",              # Source
            "pending",                     # Status
            str(priority),                 # Priority
            now,                           # Date Added
            "",                            # Date Approved
            "",                            # Sequence Doc URL
            str(d.get("enrollment", "")),  # Est. Enrollment
            "",                            # School Count
            "",                            # Total Licenses
            note,                          # Notes
        ]
        rows.append(row)

    district_prospector._write_rows(rows)
    logger.info(f"Proximity: added {len(rows)} districts to Prospecting Queue")

    return {"success": True, "new_added": len(rows)}


# ─────────────────────────────────────────────
# ESA: REGIONAL SERVICE CENTER MAPPING
# ─────────────────────────────────────────────

def _classify_esa_entity(district: dict) -> str:
    """
    Classify an Agency Type 4 entity as 'esc' (true service center) or 'career_tech'.

    True ESCs have 0 schools and 0 enrollment — they're administrative entities.
    Career-tech centers (JVSDs, career campuses) operate schools with enrolled students.
    """
    enrollment = 0
    school_count = 0
    try:
        enrollment = int(district.get("Enrollment", 0) or 0)
    except (ValueError, TypeError):
        pass
    try:
        school_count = int(district.get("School Count", 0) or 0)
    except (ValueError, TypeError):
        pass

    if enrollment == 0 and school_count == 0:
        return "esc"
    return "career_tech"


def get_esa_districts(state: str) -> list:
    """
    Return all Agency Type 4 entries for a state, classified as 'esc' or 'career_tech'.

    True ESCs: 0 schools, 0 enrollment (administrative service entities).
    Career-tech: operate schools with enrolled students (JVSDs, career campuses).
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
            enrollment = 0
            school_count = 0
            try:
                enrollment = int(d.get("Enrollment", 0) or 0)
            except (ValueError, TypeError):
                pass
            try:
                school_count = int(d.get("School Count", 0) or 0)
            except (ValueError, TypeError):
                pass

            esas.append({
                "name": d.get("District Name", ""),
                "name_key": d.get("Name Key", ""),
                "leaid": d.get("LEAID", ""),
                "county_code": d.get("County Code", ""),
                "county": d.get("County", ""),
                "city": d.get("City", ""),
                "lat": lat, "lon": lon, "state": state,
                "entity_type": _classify_esa_entity(d),
                "enrollment": enrollment,
                "school_count": school_count,
            })
    return esas


def map_districts_to_esa(state: str) -> dict:
    """
    Map each regular district to its nearest ESA.
    Algorithm: county_code match first, then haversine fallback.
    """
    state = _normalize_state(state)
    if not state:
        return {"success": False, "error": "Unknown state."}

    from agent.target_roles import REGIONAL_ENTITIES
    entity_info = REGIONAL_ENTITIES.get(state)
    if entity_info and entity_info[0] is None:
        return {
            "success": True, "state": state, "esa_count": 0, "district_count": 0,
            "esa_map": {}, "unmapped_count": 0, "no_esa_system": True,
            "error": f"No ESA system established by law in {state}.",
        }

    all_esas = get_esa_districts(state)
    esas = [e for e in all_esas if e["entity_type"] == "esc"]
    career_tech = [e for e in all_esas if e["entity_type"] == "career_tech"]
    all_districts = territory_data._load_territory_districts(state)
    regular = [d for d in all_districts if d.get("Agency Type", "") in _PROSPECTABLE_AGENCY_TYPES]

    if not esas:
        return {
            "success": True, "state": state, "esa_count": 0,
            "district_count": len(regular), "esa_map": {}, "unmapped_count": len(regular),
            "error": f"No Agency Type 4 entries found in NCES data for {state}.",
        }

    esa_map = {}
    for esa in esas:
        esa_map[esa["name"]] = {
            "leaid": esa["leaid"], "county_code": esa["county_code"],
            "county": esa.get("county", ""), "city": esa.get("city", ""),
            "lat": esa["lat"], "lon": esa["lon"],
            "districts": [], "total_enrollment": 0, "district_count": 0,
        }

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

        assigned_esa = county_to_esa.get(cc)
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
                ei = esa_map[assigned_esa]
                if ei["lat"] is not None and ei["lon"] is not None:
                    distance = haversine_miles(lat, lon, ei["lat"], ei["lon"])
            esa_map[assigned_esa]["districts"].append({
                "name": name, "enrollment": enrollment,
                "distance_miles": round(distance, 1), "city": city,
            })
            esa_map[assigned_esa]["total_enrollment"] += enrollment
            esa_map[assigned_esa]["district_count"] += 1
        else:
            unmapped += 1

    return {
        "success": True, "state": state, "esa_count": len(esas),
        "career_tech_count": len(career_tech), "career_tech": career_tech,
        "district_count": len(regular), "esa_map": esa_map, "unmapped_count": unmapped,
    }


def find_esa_opportunities(state: str) -> dict:
    """Find ESAs where Steven has active accounts — regional relationship leverage."""
    mapping = map_districts_to_esa(state)
    if not mapping["success"]:
        return mapping
    if mapping.get("no_esa_system"):
        return mapping

    state_norm = mapping["state"]
    esa_map = mapping["esa_map"]

    if not esa_map:
        return {
            "success": True, "state": state_norm, "esa_opportunities": [],
            "total_esa": 0, "error": f"No ESAs found in NCES data for {state_norm}.",
        }

    active_accounts = csv_importer.get_active_accounts(state_norm)
    active_keys = {}
    for a in active_accounts:
        display = a.get("Active Account Name", "") or a.get("Display Name", "")
        nk = a.get("Name Key", "") or csv_importer.normalize_name(display)
        active_keys[nk] = display

    prospect_keys = {p.get("Name Key", "") for p in district_prospector.get_all_prospects()}

    opportunities = []
    for esa_name, esa_info in esa_map.items():
        active_in_region = []
        uncovered = []
        for d in esa_info["districts"]:
            dk = csv_importer.normalize_name(d["name"])
            if dk in active_keys:
                active_in_region.append(active_keys[dk])
            elif dk not in prospect_keys:
                uncovered.append(d)

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

    opportunities.sort(
        key=lambda x: (x["active_account_count"] > 0, x["active_account_count"],
                       x["uncovered_enrollment"]),
        reverse=True,
    )

    # Career-tech centers as separate prospecting targets
    career_tech = mapping.get("career_tech", [])
    career_tech_targets = []
    for ct in career_tech:
        nk = ct.get("name_key", "")
        if nk not in active_keys and nk not in prospect_keys:
            career_tech_targets.append({
                "name": ct["name"],
                "city": ct.get("city", ""),
                "enrollment": ct.get("enrollment", 0),
                "school_count": ct.get("school_count", 0),
            })
    career_tech_targets.sort(key=lambda x: x.get("enrollment", 0), reverse=True)

    return {
        "success": True, "state": state_norm,
        "esa_opportunities": opportunities, "total_esa": len(opportunities),
        "career_tech_targets": career_tech_targets,
        "career_tech_count": len(career_tech),
    }


# ─────────────────────────────────────────────
# TELEGRAM FORMATTING
# ─────────────────────────────────────────────

def format_targeted_for_telegram(result: dict, max_districts: int = 20,
                                 max_schools: int = 10) -> str:
    """Format targeted proximity results (one account) for Telegram."""
    if not result.get("success"):
        return f"❌ {result.get('error', 'Unknown error')}"

    account = result["account_name"]
    state = result["state"]
    radius = result["radius_miles"]
    districts = result.get("nearby_districts", [])
    schools = result.get("nearby_schools", [])

    lines = [
        f"📍 *Nearby: {account}* ({state})",
        f"Radius: {radius} mi",
        "",
    ]

    # Districts
    new_districts = [d for d in districts if not d.get("in_queue")]
    queued_districts = [d for d in districts if d.get("in_queue")]

    if new_districts:
        lines.append(f"*Districts ({len(new_districts)} new, {len(queued_districts)} already queued):*")
        for i, d in enumerate(new_districts[:max_districts], 1):
            enrollment_str = f"{d['enrollment']:,}" if d.get("enrollment") else "?"
            city_str = f", {d['city']}" if d.get("city") else ""
            lines.append(
                f"  {i}. *{d['name']}*{city_str}\n"
                f"     📏 {d['distance_miles']} mi | 🎓 {enrollment_str} students"
            )
        if len(new_districts) > max_districts:
            lines.append(f"  _... +{len(new_districts) - max_districts} more_")
    elif queued_districts:
        lines.append(f"*Districts:* all {len(queued_districts)} nearby are already in the queue")
    else:
        lines.append("*Districts:* none found within range")

    lines.append("")

    # Unique nearby districts (by parent district name) for schools
    if schools:
        # Group schools by district
        by_district = {}
        for s in schools:
            dn = s.get("district_name", "Unknown")
            if dn not in by_district:
                by_district[dn] = []
            by_district[dn].append(s)

        lines.append(f"*Nearby schools ({len(schools)} across {len(by_district)} districts):*")
        shown = 0
        for dn, school_list in sorted(by_district.items(), key=lambda x: x[1][0]["distance_miles"]):
            if shown >= max_schools:
                break
            closest = school_list[0]
            lines.append(
                f"  {dn}: {len(school_list)} schools "
                f"(closest {closest['distance_miles']} mi)"
            )
            shown += 1
        if len(by_district) > max_schools:
            lines.append(f"  _... +{len(by_district) - max_schools} more districts_")

    # Suggestion
    if result.get("suggestion"):
        lines.append(f"\n💡 {result['suggestion']}")

    return "\n".join(lines)


def format_state_sweep_for_telegram(result: dict, max_show: int = 15) -> str:
    """Format state sweep proximity results for Telegram."""
    if not result.get("success"):
        return f"❌ {result.get('error', 'Unknown error')}"

    state = result["state"]
    total = result.get("total_found", 0)
    matched = result.get("matched_accounts", 0)
    radius = result.get("radius_miles", 30)
    districts = result.get("nearby_districts", [])

    lines = [
        f"📍 *Proximity Sweep: {state}*",
        f"Radius: {radius} mi | Active accounts matched: {matched}",
        f"Found: {total} nearby uncovered districts",
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
        lines.append(f"\n_{total - max_show} more found_")

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
    career_tech = result.get("career_tech_targets", [])
    career_tech_count = result.get("career_tech_count", 0)

    lines = [
        f"🏛️ *ESA Opportunities: {state}*",
        f"ESCs: {total_esa} | Career-Tech Centers: {career_tech_count}",
        "",
    ]

    if not opps and not career_tech:
        lines.append("No ESA data found.")
        return "\n".join(lines)

    # ESC section
    has_active = [o for o in opps if o["active_account_count"] > 0]
    no_active = [o for o in opps if o["active_account_count"] == 0]

    if has_active:
        lines.append("*🟢 ESCs with your active accounts:*")
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
        lines.append(f"*⚪ {len(no_active)} ESCs with no active accounts*")
        top_cold = sorted(no_active, key=lambda x: x["uncovered_enrollment"], reverse=True)[:3]
        for o in top_cold:
            city_str = f" ({o['city']})" if o.get("city") else ""
            lines.append(
                f"  {o['esa_name']}{city_str} — "
                f"{o['uncovered_count']} districts, "
                f"{o['uncovered_enrollment']:,} students"
            )
        lines.append("")

    # Career-tech section
    if career_tech:
        lines.append(f"*🔧 Career-Tech Centers ({len(career_tech)} untargeted):*")
        for ct in career_tech[:5]:
            city_str = f", {ct['city']}" if ct.get("city") else ""
            lines.append(
                f"  {ct['name']}{city_str} — "
                f"{ct.get('enrollment', 0):,} students, "
                f"{ct.get('school_count', 0)} schools"
            )
        if len(career_tech) > 5:
            lines.append(f"  _... +{len(career_tech) - 5} more_")

    return "\n".join(lines)
