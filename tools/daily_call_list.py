"""
tools/daily_call_list.py — Scout Phase 6D Daily Call List.

Builds a prioritized daily call list of contacts from districts where
CodeCombat already has active schools. Outputs to Telegram + Google Doc.

Priority logic:
  1. Match leads to districts with active CodeCombat schools (two-path matching)
  2. Rank by email presence, title, school count, email confidence
  3. Max 3 contacts per district for coverage spread
  4. Backfill from any lead with email+title if <max_contacts from priority districts

Usage (module-level, not a class):
  import tools.daily_call_list as daily_call_list
  result = daily_call_list.build_daily_call_list()
"""

import logging
import os
from datetime import date

import tools.sheets_writer as sheets_writer
import tools.csv_importer as csv_importer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────

def build_daily_call_list(max_contacts: int = 10) -> dict:
    """
    Build today's daily call list.

    Returns:
      {success: bool, cards: list[dict], district_count: int,
       total_matched: int, error: str}
    """
    try:
        leads = sheets_writer.get_leads()
        if not leads:
            return {
                "success": False,
                "cards": [],
                "district_count": 0,
                "total_matched": 0,
                "error": "No leads found in Leads tab. Research some districts first.",
            }

        districts = csv_importer.get_districts_with_schools()
        if not districts:
            # No priority districts — backfill from all leads
            logger.info("No districts with active schools — backfilling from all leads")
            cards = _rank_and_select(
                [{"lead": l, "district_info": None} for l in leads if l.get("Email")],
                max_contacts=max_contacts,
            )
            return {
                "success": True,
                "cards": cards,
                "district_count": 0,
                "total_matched": 0,
                "error": "",
            }

        matched = _match_leads_to_districts(leads, districts)
        cards = _rank_and_select(matched, max_contacts=max_contacts, all_leads=leads)

        # Count unique districts in final cards
        district_names = set()
        for c in cards:
            if c.get("district") and not c.get("is_backfill"):
                district_names.add(c["district"])

        return {
            "success": True,
            "cards": cards,
            "district_count": len(district_names),
            "total_matched": len(matched),
            "error": "",
        }

    except Exception as e:
        logger.error(f"build_daily_call_list error: {e}")
        return {
            "success": False,
            "cards": [],
            "district_count": 0,
            "total_matched": 0,
            "error": str(e),
        }


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def _match_leads_to_districts(leads: list[dict], districts: list[dict]) -> list[dict]:
    """
    Two-path matching:
      1. Lead's District Name matches a priority district's name_key
      2. Lead's Account matches a school under a priority district

    Returns list of {lead, district_info} dicts.
    """
    # Build lookup: district name_key → district_info
    district_by_key = {}
    for d in districts:
        key = d.get("name_key", "")
        if key:
            district_by_key[key] = d

    # Build reverse lookup: school display_name (normalized) → district_info
    school_to_district = {}
    for d in districts:
        for school in d.get("schools", []):
            school_key = csv_importer.normalize_name(school.get("display_name", ""))
            if school_key:
                school_to_district[school_key] = d

    matched = []
    seen_emails = set()

    for lead in leads:
        email = (lead.get("Email") or "").strip().lower()
        if not email:
            continue
        if email in seen_emails:
            continue

        district_info = None

        # Path 1: lead's District Name matches a priority district
        lead_district = lead.get("District Name", "").strip()
        if lead_district:
            lead_district_key = csv_importer.normalize_name(lead_district)
            if lead_district_key in district_by_key:
                district_info = district_by_key[lead_district_key]

        # Path 2: lead's Account matches a school under a priority district
        if not district_info:
            lead_account = lead.get("Account", "").strip()
            if lead_account:
                account_key = csv_importer.normalize_name(lead_account)
                if account_key in school_to_district:
                    district_info = school_to_district[account_key]

        if district_info:
            seen_emails.add(email)
            matched.append({"lead": lead, "district_info": district_info})

    return matched


# ─────────────────────────────────────────────
# RANKING + SELECTION
# ─────────────────────────────────────────────

_CONFIDENCE_ORDER = {"HIGH": 4, "MEDIUM": 3, "LOW": 2, "UNKNOWN": 1, "": 0}


def _rank_and_select(
    matched: list[dict],
    max_contacts: int = 10,
    all_leads: list[dict] | None = None,
) -> list[dict]:
    """
    Rank matched leads and select top N.

    Ranking factors:
      1. Has email (required)
      2. Has title
      3. District school_count (more schools = higher priority)
      4. Email confidence (HIGH > MEDIUM > LOW > UNKNOWN)

    Max 3 contacts per district. Dedup by email.
    If <max_contacts from priority districts, backfill from any lead with email+title.
    """

    def sort_key(item):
        lead = item["lead"]
        d_info = item.get("district_info")
        has_title = 1 if lead.get("Title", "").strip() else 0
        school_count = d_info.get("school_count", 0) if d_info else 0
        confidence = _CONFIDENCE_ORDER.get(
            lead.get("Email Confidence", "").upper(), 0
        )
        return (has_title, school_count, confidence)

    # Sort best candidates first
    matched.sort(key=sort_key, reverse=True)

    selected = []
    seen_emails = set()
    district_counts = {}

    for item in matched:
        if len(selected) >= max_contacts:
            break

        lead = item["lead"]
        email = (lead.get("Email") or "").strip().lower()
        if not email or email in seen_emails:
            continue

        d_info = item.get("district_info")
        district_name = d_info.get("display_name", "") if d_info else ""

        # Max 3 per district
        if district_name:
            count = district_counts.get(district_name, 0)
            if count >= 3:
                continue
            district_counts[district_name] = count + 1

        seen_emails.add(email)
        selected.append(_build_call_card(lead, d_info))

    # Backfill if needed
    if len(selected) < max_contacts and all_leads:
        for lead in all_leads:
            if len(selected) >= max_contacts:
                break
            email = (lead.get("Email") or "").strip().lower()
            if not email or email in seen_emails:
                continue
            if not lead.get("Title", "").strip():
                continue
            seen_emails.add(email)
            selected.append(_build_call_card(lead, district_info=None))

    return selected


# ─────────────────────────────────────────────
# CARD BUILDING
# ─────────────────────────────────────────────

def _build_call_card(lead: dict, district_info: dict | None) -> dict:
    """Build a call card dict from a lead + optional district info."""
    first = lead.get("First Name", "").strip()
    last = lead.get("Last Name", "").strip()
    contact_name = f"{first} {last}".strip() or "Unknown"

    is_backfill = district_info is None

    if district_info:
        district = district_info.get("display_name", "")
        state = district_info.get("state", "") or lead.get("State", "")
        school_count = district_info.get("school_count", 0)
        schools = [s.get("display_name", "") for s in district_info.get("schools", [])]
        talking_point = _generate_talking_point(district_info)
    else:
        district = lead.get("District Name", "") or lead.get("Account", "")
        state = lead.get("State", "")
        school_count = 0
        schools = []
        talking_point = "No current CodeCombat presence — fresh opportunity."

    return {
        "contact_name": contact_name,
        "title": lead.get("Title", "").strip(),
        "email": lead.get("Email", "").strip(),
        "phone": lead.get("Work Phone", "").strip(),
        "district": district,
        "state": state,
        "school_count": school_count,
        "schools": schools[:5],  # cap display at 5 schools
        "talking_point": talking_point,
        "is_backfill": is_backfill,
    }


# ─────────────────────────────────────────────
# TALKING POINTS
# ─────────────────────────────────────────────

def _generate_talking_point(district_info: dict) -> str:
    """Template-based talking point based on school count."""
    schools = district_info.get("schools", [])
    school_count = len(schools)
    school_names = [s.get("display_name", "School") for s in schools]

    if school_count == 1:
        return (
            f"{school_names[0]} already uses CodeCombat — "
            f"ask about expanding to other schools."
        )
    elif school_count <= 3:
        names = ", ".join(school_names)
        return (
            f"{school_count} schools active ({names}) — "
            f"strong adoption, discuss district agreement."
        )
    else:
        top_names = ", ".join(school_names[:3])
        return (
            f"Major foothold with {school_count} schools ({top_names}, ...) — "
            f"ideal for district-wide contract."
        )


# ─────────────────────────────────────────────
# GOOGLE DOC OUTPUT
# ─────────────────────────────────────────────

def write_call_list_to_doc(cards: list[dict], gas_bridge, folder_id: str = None) -> dict:
    """
    Write daily call list to a Google Doc via GAS bridge.

    Returns: {success: bool, url: str, error: str}
    """
    if not gas_bridge:
        return {"success": False, "url": "", "error": "GAS bridge not available"}

    today = date.today().strftime("%Y-%m-%d")
    title = f"Daily Call List — {today}"

    # Build doc content
    lines = [
        f"DAILY CALL LIST — {today}",
        f"{len(cards)} contacts",
        "",
        "=" * 60,
        "",
    ]

    for i, card in enumerate(cards, 1):
        lines.append(f"{i}. {card['contact_name']}")
        if card.get("title"):
            lines.append(f"   Title: {card['title']}")
        lines.append(f"   Email: {card.get('email', 'N/A')}")
        if card.get("phone"):
            lines.append(f"   Phone: {card['phone']}")

        district_line = card.get("district", "")
        if card.get("state"):
            district_line += f" ({card['state']})"
        if card.get("school_count"):
            district_line += f" | {card['school_count']} active schools"
        if district_line:
            lines.append(f"   District: {district_line}")

        if card.get("schools"):
            school_names = ", ".join(card["schools"][:5])
            lines.append(f"   Active schools: {school_names}")

        if card.get("talking_point"):
            lines.append(f"   Talking point: {card['talking_point']}")

        if card.get("is_backfill"):
            lines.append("   [Backfill — no active CodeCombat presence]")

        lines.append("")
        lines.append("-" * 40)
        lines.append("")

    content = "\n".join(lines)

    # Use CALL_LIST_FOLDER_ID if set, else fall back to SEQUENCES_FOLDER_ID
    if not folder_id:
        folder_id = os.environ.get("CALL_LIST_FOLDER_ID", "")
        if not folder_id:
            folder_id = os.environ.get("SEQUENCES_FOLDER_ID", "")
        if folder_id:
            folder_id = folder_id.split("?")[0]  # strip query params

    try:
        result = gas_bridge.create_google_doc(
            title=title,
            content=content,
            folder_id=folder_id or None,
        )
        if result.get("success"):
            return {"success": True, "url": result.get("url", ""), "error": ""}
        else:
            return {"success": False, "url": "", "error": result.get("error", "Doc creation failed")}
    except Exception as e:
        logger.error(f"write_call_list_to_doc error: {e}")
        return {"success": False, "url": "", "error": str(e)}


# ─────────────────────────────────────────────
# TELEGRAM FORMAT
# ─────────────────────────────────────────────

def format_for_telegram(cards: list[dict], doc_url: str = "") -> str:
    """Format call list as a compact Telegram preview."""
    today = date.today().strftime("%Y-%m-%d")

    # Count unique districts
    districts = set()
    for c in cards:
        if c.get("district") and not c.get("is_backfill"):
            districts.add(c["district"])

    district_str = f" from {len(districts)} districts" if districts else ""
    lines = [
        f"*Daily Call List — {today}*",
        f"{len(cards)} contacts{district_str}",
        "",
    ]

    for i, card in enumerate(cards, 1):
        name = card.get("contact_name", "Unknown")
        title = card.get("title", "")
        title_str = f" — {title}" if title else ""

        district = card.get("district", "")
        state = card.get("state", "")
        district_parts = []
        if district:
            district_parts.append(district)
        if state:
            district_parts.append(f"({state})")
        if card.get("school_count"):
            district_parts.append(f"| {card['school_count']} active schools")

        email = card.get("email", "")

        lines.append(f"{i}. *{name}*{title_str}")
        if district_parts:
            lines.append(f"   {' '.join(district_parts)}")
        if email:
            lines.append(f"   {email}")
        if card.get("is_backfill"):
            lines.append("   _[new prospect — no active schools]_")
        lines.append("")

    if doc_url:
        lines.append(f"Full list with talking points: [Google Doc]({doc_url})")

    return "\n".join(lines)
