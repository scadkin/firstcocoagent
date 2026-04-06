"""
Territory Map Generator — interactive Folium map of Steven's territory.

Layers:
  - Active Accounts (green) — current customers
  - Pipeline (yellow) — open opportunities
  - Prospects (blue) — in prospecting queue
  - ESAs (purple) — regional service centers (Agency Type 4)
  - All Districts (gray, clustered) — full NCES territory

Usage:
  generate_territory_map() -> str  # returns HTML string
  generate_territory_map_file(output_path) -> str  # writes to file, returns path
"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def generate_territory_map(state_filter: str = "") -> str:
    """
    Generate an interactive territory map as HTML string.
    Optionally filter to a single state.
    Returns HTML string.
    """
    import folium
    from folium.plugins import MarkerCluster

    import tools.csv_importer as csv_importer
    import tools.territory_data as territory_data
    import tools.district_prospector as district_prospector
    import tools.pipeline_tracker as pipeline_tracker

    # ── Load all data sources ──
    logger.info("Loading territory data for map...")

    active_accounts = csv_importer.get_active_accounts(state_filter)
    logger.info(f"Active accounts: {len(active_accounts)}")

    try:
        pipeline_opps = pipeline_tracker.get_open_opps()
        if state_filter:
            # Pipeline doesn't have a state filter param — filter manually
            sf = state_filter.strip().upper()
            pipeline_opps = [o for o in pipeline_opps if sf in o.get("Account Name", "").upper()
                            or o.get("State", "").upper() == sf]
    except Exception:
        pipeline_opps = []
    logger.info(f"Pipeline opps: {len(pipeline_opps)}")

    try:
        prospects = district_prospector.get_all_prospects()
        if state_filter:
            sf = state_filter.strip().upper()
            prospects = [p for p in prospects if p.get("State", "").upper() == sf]
    except Exception:
        prospects = []
    logger.info(f"Prospects: {len(prospects)}")

    districts = territory_data._load_territory_districts(state_filter)
    logger.info(f"Territory districts: {len(districts)}")

    # ── Build lookup sets for classification ──
    active_keys = set()
    for acc in active_accounts:
        key = acc.get("Name Key", "") or csv_importer.normalize_name(
            acc.get("Active Account Name", "") or acc.get("Display Name", ""))
        if key:
            active_keys.add(key)

    pipeline_keys = set()
    for opp in pipeline_opps:
        key = csv_importer.normalize_name(opp.get("Account Name", ""))
        if key:
            pipeline_keys.add(key)

    prospect_keys = set()
    for p in prospects:
        key = p.get("Name Key", "") or csv_importer.normalize_name(p.get("Account Name", ""))
        if key:
            prospect_keys.add(key)

    # ── Create map centered on US ──
    if state_filter:
        # Center on first district with lat/lon in the filtered state
        center_lat, center_lon, zoom = 39.8, -98.5, 5
        for d in districts:
            try:
                lat = float(d.get("Lat", 0))
                lon = float(d.get("Lon", 0))
                if lat and lon:
                    center_lat, center_lon = lat, lon
                    zoom = 7
                    break
            except (ValueError, TypeError):
                continue
    else:
        center_lat, center_lon, zoom = 39.8, -98.5, 5

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
    )

    # ── Layer: All Districts (gray, clustered) ──
    district_cluster = MarkerCluster(name="All Districts (gray)", show=False)
    placed_districts = 0
    for d in districts:
        try:
            lat = float(d.get("Lat", 0))
            lon = float(d.get("Lon", 0))
        except (ValueError, TypeError):
            continue
        if not lat or not lon:
            continue

        name_key = d.get("Name Key", "")
        # Skip if already in active/pipeline/prospect (those get their own layer)
        if name_key in active_keys or name_key in pipeline_keys or name_key in prospect_keys:
            continue

        name = d.get("District Name", "Unknown")
        state = d.get("State", "")
        enrollment = d.get("Enrollment", "")
        agency_type = d.get("Agency Type", "")

        # ESAs get their own layer
        if str(agency_type) == "4":
            continue

        popup_html = f"<b>{name}</b><br>{state} | Enrollment: {enrollment}"
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color="#999999",
            fill=True,
            fill_color="#cccccc",
            fill_opacity=0.5,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(district_cluster)
        placed_districts += 1

    district_cluster.add_to(m)
    logger.info(f"District markers: {placed_districts}")

    # ── Layer: ESAs (purple) ──
    esa_group = folium.FeatureGroup(name="ESAs / Service Centers (purple)", show=True)
    esa_count = 0
    for d in districts:
        if str(d.get("Agency Type", "")) != "4":
            continue
        try:
            lat = float(d.get("Lat", 0))
            lon = float(d.get("Lon", 0))
        except (ValueError, TypeError):
            continue
        if not lat or not lon:
            continue

        name = d.get("District Name", "Unknown")
        state = d.get("State", "")
        popup_html = f"<b>{name}</b><br>{state} | ESA/Service Center"
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="purple", icon="info-sign"),
        ).add_to(esa_group)
        esa_count += 1
    esa_group.add_to(m)
    logger.info(f"ESA markers: {esa_count}")

    # ── Layer: Prospects (blue) ──
    prospect_group = folium.FeatureGroup(name="Prospects (blue)", show=True)
    prospect_count = 0
    for p in prospects:
        name_key = p.get("Name Key", "") or csv_importer.normalize_name(p.get("Account Name", ""))
        # Find lat/lon from NCES data
        matched = _find_district_coords(districts, name_key)
        if not matched:
            continue

        name = p.get("Account Name", "Unknown")
        state = p.get("State", "")
        strategy = p.get("Strategy", "")
        status = p.get("Status", "")
        popup_html = (f"<b>{name}</b><br>{state} | Strategy: {strategy}<br>"
                     f"Status: {status}")
        folium.Marker(
            location=[matched["lat"], matched["lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="blue", icon="search"),
        ).add_to(prospect_group)
        prospect_count += 1
    prospect_group.add_to(m)
    logger.info(f"Prospect markers: {prospect_count}")

    # ── Layer: Pipeline (yellow/orange) ──
    pipeline_group = folium.FeatureGroup(name="Pipeline (orange)", show=True)
    pipeline_count = 0
    for opp in pipeline_opps:
        name_key = csv_importer.normalize_name(opp.get("Account Name", ""))
        matched = _find_district_coords(districts, name_key)
        if not matched:
            continue

        name = opp.get("Account Name", "Unknown")
        stage = opp.get("Stage", "")
        amount = opp.get("Amount", "")
        popup_html = (f"<b>{name}</b><br>Stage: {stage}<br>"
                     f"Amount: {amount}")
        folium.Marker(
            location=[matched["lat"], matched["lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="orange", icon="briefcase"),
        ).add_to(pipeline_group)
        pipeline_count += 1
    pipeline_group.add_to(m)
    logger.info(f"Pipeline markers: {pipeline_count}")

    # ── Layer: Active Accounts (green) ──
    active_group = folium.FeatureGroup(name="Active Accounts (green)", show=True)
    active_count = 0
    for acc in active_accounts:
        name_key = acc.get("Name Key", "") or csv_importer.normalize_name(
            acc.get("Active Account Name", "") or acc.get("Display Name", ""))
        matched = _find_district_coords(districts, name_key)
        if not matched:
            continue

        name = acc.get("Active Account Name", "") or acc.get("Display Name", "Unknown")
        state = acc.get("State", "")
        acc_type = acc.get("Account Type", "")
        popup_html = f"<b>{name}</b><br>{state} | Type: {acc_type}"
        folium.Marker(
            location=[matched["lat"], matched["lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="green", icon="ok-sign"),
        ).add_to(active_group)
        active_count += 1
    active_group.add_to(m)
    logger.info(f"Active account markers: {active_count}")

    # ── Layer control ──
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Title ──
    title_html = f"""
    <div style="position: fixed; top: 10px; left: 60px; z-index: 1000;
         background-color: white; padding: 10px 15px; border-radius: 5px;
         box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-family: Arial;">
        <b>Scout Territory Map</b>
        {f' — {state_filter.upper()}' if state_filter else ''}<br>
        <span style="color:green;">&#9679;</span> Active ({active_count})
        <span style="color:orange;">&#9679;</span> Pipeline ({pipeline_count})
        <span style="color:blue;">&#9679;</span> Prospects ({prospect_count})
        <span style="color:purple;">&#9679;</span> ESAs ({esa_count})
        <span style="color:gray;">&#9679;</span> Districts ({placed_districts})
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    html = m._repr_html_()
    logger.info(f"Territory map generated: {active_count} active, {pipeline_count} pipeline, "
                f"{prospect_count} prospects, {esa_count} ESAs, {placed_districts} districts")
    return html


def generate_territory_map_file(output_path: str = "", state_filter: str = "") -> str:
    """Generate map and save to HTML file. Returns file path."""
    html = generate_territory_map(state_filter)
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(), "scout_territory_map.html")
    with open(output_path, "w") as f:
        f.write(html)
    logger.info(f"Territory map saved to {output_path}")
    return output_path


def _find_district_coords(districts: list, name_key: str) -> dict | None:
    """Find lat/lon for a district by name key. Returns {lat, lon} or None."""
    if not name_key:
        return None
    for d in districts:
        if d.get("Name Key", "") == name_key:
            try:
                lat = float(d.get("Lat", 0))
                lon = float(d.get("Lon", 0))
                if lat and lon:
                    return {"lat": lat, "lon": lon}
            except (ValueError, TypeError):
                continue
    return None
