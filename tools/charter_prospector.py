"""
tools/charter_prospector.py

F6 Charter School CMO Prospector.

Loads memory/charter_cmos.json, filters by territory state, and queues CMOs
into the Prospecting Queue via district_prospector.add_district with strategy
tag "charter_cmo".

MODULE not class. Flat functions imported at top of main.py.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _seed_path() -> str:
    """Resolve the charter CMO seed file path."""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "memory", "charter_cmos.json"
    )


def load_charter_cmos() -> list[dict]:
    """
    Load the charter CMO seed list. Returns the list of cmo dicts (without the
    _meta key). Empty list on any error.
    """
    path = _seed_path()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        cmos = data.get("cmos", [])
        if not isinstance(cmos, list):
            logger.warning(f"charter_cmos.json 'cmos' is not a list: {type(cmos)}")
            return []
        return cmos
    except FileNotFoundError:
        logger.warning(f"charter_cmos.json not found at {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"charter_cmos.json parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load charter_cmos.json: {e}")
        return []


def filter_cmos_by_state(cmos: list[dict], state: Optional[str] = None) -> list[dict]:
    """
    Filter CMOs by territory state. If state is None, returns all CMOs (caller
    is responsible for territory filtering upstream).
    Matches case-insensitively on 2-letter state code.
    """
    if not state:
        return cmos
    s = state.strip().upper()
    return [c for c in cmos if (c.get("state") or "").strip().upper() == s]


def queue_charter_cmos(state: Optional[str] = None) -> dict:
    """
    Queue charter CMOs as prospects with strategy="charter_cmo".

    Args:
        state: optional 2-letter state filter. None = all territory CMOs.

    Returns: {
        "found": int,           # total CMOs matching the filter
        "queued": list[dict],   # successfully added to queue
        "skipped": list[dict],  # already in queue or active customer
        "errors": list[str],
    }
    """
    # Lazy import to avoid circular
    import tools.district_prospector as district_prospector

    cmos = load_charter_cmos()
    if not cmos:
        return {
            "found": 0,
            "queued": [],
            "skipped": [],
            "errors": ["charter_cmos.json empty or unreadable"],
        }

    if state:
        cmos = filter_cmos_by_state(cmos, state)

    queued = []
    skipped = []
    errors = []

    for cmo in cmos:
        name = (cmo.get("cmo_name") or "").strip()
        state_code = (cmo.get("state") or "").strip().upper()
        if not name or not state_code:
            errors.append(f"Missing name or state: {cmo}")
            continue

        school_count = cmo.get("school_count") or 0
        est_enrollment = cmo.get("est_enrollment") or 0
        website = cmo.get("website") or ""
        hq_city = cmo.get("hq_city") or ""
        grade_levels = cmo.get("grade_levels") or ""
        cmo_notes = cmo.get("notes") or ""
        parent_network = cmo.get("parent_network") or ""

        # Pack rich metadata into the notes field so it lands in the queue sheet
        notes_parts = [
            f"Charter CMO",
            f"{school_count} schools" if school_count else "",
            f"~{est_enrollment:,} students" if est_enrollment else "",
            f"Grades {grade_levels}" if grade_levels else "",
            f"HQ: {hq_city}" if hq_city else "",
            f"Parent: {parent_network}" if parent_network else "",
            f"Web: {website}" if website else "",
        ]
        full_notes = ". ".join(p for p in notes_parts if p)
        if cmo_notes:
            full_notes += f". {cmo_notes}"

        try:
            from tools.signal_processor import build_csta_enrichment
            full_notes, priority_bonus = build_csta_enrichment(name, state_code, full_notes)
            result = district_prospector.add_district(
                name=name,
                state=state_code,
                notes=full_notes,
                strategy="charter_cmo",
                source="manual",
                school_count=school_count,
                est_enrollment=est_enrollment,
                priority_bonus=priority_bonus,
            )
            if result.get("success"):
                queued.append({
                    "name": name,
                    "state": state_code,
                    "schools": school_count,
                    "enrollment": est_enrollment,
                })
            else:
                skipped.append({
                    "name": name,
                    "state": state_code,
                    "reason": result.get("error", "unknown"),
                })
        except Exception as e:
            errors.append(f"{name}: {e}")

    logger.info(
        f"Charter CMO prospector: {len(cmos)} found, "
        f"{len(queued)} queued, {len(skipped)} skipped, {len(errors)} errors"
    )
    return {
        "found": len(cmos),
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
    }


def format_queue_result_for_telegram(result: dict) -> str:
    """Format queue_charter_cmos result for Telegram notification."""
    found = result.get("found", 0)
    queued = result.get("queued", [])
    skipped = result.get("skipped", [])
    errors = result.get("errors", [])

    lines = [f"🏫 *Charter CMO Prospector* — {found} CMOs found"]
    lines.append("")

    if queued:
        lines.append(f"✅ Queued {len(queued)}:")
        for q in queued[:20]:
            schools = q.get("schools", 0)
            enroll = q.get("enrollment", 0)
            lines.append(
                f"  • {q['name'][:45]} ({q['state']}) "
                f"— {schools} schools, ~{enroll:,} students"
            )
        if len(queued) > 20:
            lines.append(f"  ...and {len(queued) - 20} more")
        lines.append("")

    if skipped:
        lines.append(f"⏭ Skipped {len(skipped)} (already in queue or active):")
        for s in skipped[:10]:
            lines.append(f"  • {s['name'][:45]} — {s.get('reason', '')[:40]}")
        if len(skipped) > 10:
            lines.append(f"  ...and {len(skipped) - 10} more")
        lines.append("")

    if errors:
        lines.append(f"⚠️ {len(errors)} errors — check Railway logs")
        lines.append("")

    lines.append(
        "Review with `/prospect_all` then approve batches with "
        "`/prospect_approve 1,3,5`."
    )
    return "\n".join(lines)


def list_charter_cmos_for_telegram(state: Optional[str] = None) -> str:
    """
    Show the seed list for a state (or all) in Telegram format — read-only,
    does not queue anything.
    """
    cmos = load_charter_cmos()
    if state:
        cmos = filter_cmos_by_state(cmos, state)

    if not cmos:
        return f"🏫 No CMOs found{' in ' + state.upper() if state else ''}."

    header = f"🏫 *Charter CMOs{' in ' + state.upper() if state else ' (all territory)'}* — {len(cmos)} total"
    lines = [header, ""]

    for c in cmos:
        name = (c.get("cmo_name") or "?")[:50]
        st = c.get("state", "?")
        schools = c.get("school_count", 0)
        enroll = c.get("est_enrollment", 0)
        city = c.get("hq_city", "")
        lines.append(
            f"• *{name}* ({st}) — {schools} schools, ~{enroll:,} students"
        )
        if city:
            lines.append(f"   HQ: {city}")

    lines.append("")
    lines.append("Use `/prospect_charter_cmos [state]` to queue these as prospects.")
    return "\n".join(lines)
