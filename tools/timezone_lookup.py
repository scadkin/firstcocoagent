"""
timezone_lookup.py — 2-letter US state code → IANA timezone string.

Zero dependencies beyond `zoneinfo` (stdlib since Python 3.9). Used by
tools/prospect_loader.py and tools/outreach_client.validate_prospect_inputs
to satisfy Rule 17 (every Outreach prospect create must have a populated
IANA timezone).

Edge cases (IN, TN, NE, KY, FL, ND, SD, OR, ID): states that span two
timezones. Defaults pick the zone covering the majority of the state
population. Override explicitly when shipping to a minority-zone district.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 50 states + DC + PR. Listed alphabetically for auditability.
STATE_TO_TZ: dict[str, str] = {
    "AL": "America/Chicago",
    "AK": "America/Anchorage",
    "AZ": "America/Phoenix",          # no DST
    "AR": "America/Chicago",
    "CA": "America/Los_Angeles",
    "CO": "America/Denver",
    "CT": "America/New_York",
    "DC": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",          # majority-ET; panhandle is CT
    "GA": "America/New_York",
    "HI": "Pacific/Honolulu",
    "IA": "America/Chicago",
    "ID": "America/Boise",             # majority-MT; north is PT
    "IL": "America/Chicago",
    "IN": "America/Indiana/Indianapolis",  # majority-ET; NW counties CT
    "KS": "America/Chicago",
    "KY": "America/New_York",          # majority-ET; west is CT
    "LA": "America/Chicago",
    "MA": "America/New_York",
    "MD": "America/New_York",
    "ME": "America/New_York",
    "MI": "America/Detroit",           # ET for lower peninsula
    "MN": "America/Chicago",
    "MO": "America/Chicago",
    "MS": "America/Chicago",
    "MT": "America/Denver",
    "NC": "America/New_York",
    "ND": "America/Chicago",           # majority-CT; western counties MT
    "NE": "America/Chicago",           # majority-CT; panhandle MT
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NM": "America/Denver",
    "NV": "America/Los_Angeles",
    "NY": "America/New_York",
    "OH": "America/New_York",
    "OK": "America/Chicago",
    "OR": "America/Los_Angeles",       # majority-PT; Malheur County MT
    "PA": "America/New_York",
    "PR": "America/Puerto_Rico",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "SD": "America/Chicago",           # majority-CT; western counties MT
    "TN": "America/New_York",          # majority-ET; western is CT
    "TX": "America/Chicago",           # majority-CT; El Paso MT
    "UT": "America/Denver",
    "VA": "America/New_York",
    "VT": "America/New_York",
    "WA": "America/Los_Angeles",
    "WI": "America/Chicago",
    "WV": "America/New_York",
    "WY": "America/Denver",
}


def state_to_timezone(state_code: str | None) -> str | None:
    """Return IANA timezone string for a 2-letter US state code, or None if unknown.

    Returns None for empty/None/unknown input so the caller can skip the contact
    rather than silently falling back to a default zone. Per Rule 17, a missing
    timezone must never be papered over with a guess.
    """
    if not state_code:
        return None
    return STATE_TO_TZ.get(state_code.strip().upper())


def is_valid_iana_timezone(tz: str | None) -> bool:
    """True if `tz` parses via zoneinfo.ZoneInfo without raising. Used by
    validate_prospect_inputs to confirm that an externally-provided timezone
    string is a real IANA identifier before it lands in an Outreach POST."""
    if not tz:
        return False
    try:
        ZoneInfo(tz)
        return True
    except ZoneInfoNotFoundError:
        return False
    except Exception:
        return False
