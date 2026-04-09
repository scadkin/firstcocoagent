"""
tools/cte_prospector.py

F7 CTE Center Prospector.

Loads memory/cte_centers.json, filters by territory state, and queues CTE
centers into the Prospecting Queue via district_prospector.add_district with
strategy tag "cte_center".

CTE centers serve multiple sending districts from one location — one CTE
adoption pulls 5-50 sending district relationships with it. Prioritize
centers with it_cs_program: true for CodeCombat fit.

MODULE not class. Flat functions imported at top of main.py.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _seed_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "memory", "cte_centers.json"
    )


def load_cte_centers() -> list[dict]:
    """Load the CTE center seed list. Empty list on any error."""
    path = _seed_path()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        centers = data.get("cte_centers", [])
        if not isinstance(centers, list):
            logger.warning(f"cte_centers.json 'cte_centers' is not a list: {type(centers)}")
            return []
        return centers
    except FileNotFoundError:
        logger.warning(f"cte_centers.json not found at {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"cte_centers.json parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load cte_centers.json: {e}")
        return []


def filter_centers_by_state(centers: list[dict], state: Optional[str] = None) -> list[dict]:
    """Case-insensitive state filter on 2-letter codes."""
    if not state:
        return centers
    s = state.strip().upper()
    return [c for c in centers if (c.get("state") or "").strip().upper() == s]


def filter_centers_cs_only(centers: list[dict]) -> list[dict]:
    """Keep only centers flagged as having an IT/CS/cyber program."""
    return [c for c in centers if c.get("it_cs_program") is True]


def queue_cte_centers(
    state: Optional[str] = None,
    cs_only: bool = True,
) -> dict:
    """
    Queue CTE centers as prospects with strategy="cte_center".

    Args:
        state: optional 2-letter state filter. None = all territory.
        cs_only: if True (default), only queue centers with an IT/CS program.

    Returns: {
        "found": int,
        "queued": list[dict],
        "skipped": list[dict],
        "errors": list[str],
    }
    """
    import tools.district_prospector as district_prospector

    centers = load_cte_centers()
    if not centers:
        return {
            "found": 0,
            "queued": [],
            "skipped": [],
            "errors": ["cte_centers.json empty or unreadable"],
        }

    if state:
        centers = filter_centers_by_state(centers, state)
    if cs_only:
        centers = filter_centers_cs_only(centers)

    queued = []
    skipped = []
    errors = []

    for center in centers:
        name = (center.get("name") or "").strip()
        state_code = (center.get("state") or "").strip().upper()
        if not name or not state_code:
            errors.append(f"Missing name or state: {center}")
            continue

        est_enrollment = center.get("est_enrollment") or 0
        sending_districts = center.get("sending_districts") or 0
        city = center.get("city") or ""
        website = center.get("website") or ""
        has_cs = center.get("it_cs_program", False)
        ctr_notes = center.get("notes") or ""

        notes_parts = [
            "CTE Center",
            f"{sending_districts} sending districts" if sending_districts else "",
            f"~{est_enrollment:,} students" if est_enrollment else "",
            f"{city}" if city else "",
            "IT/CS program" if has_cs else "",
            f"Web: {website}" if website else "",
        ]
        full_notes = ". ".join(p for p in notes_parts if p)
        if ctr_notes:
            full_notes += f". {ctr_notes}"

        try:
            result = district_prospector.add_district(
                name=name,
                state=state_code,
                notes=full_notes,
                strategy="cte_center",
                source="manual",
                sending_districts=sending_districts,
                est_enrollment=est_enrollment,
            )
            if result.get("success"):
                queued.append({
                    "name": name,
                    "state": state_code,
                    "sending": sending_districts,
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
        f"CTE prospector: {len(centers)} candidates, "
        f"{len(queued)} queued, {len(skipped)} skipped, {len(errors)} errors"
    )
    return {
        "found": len(centers),
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
    }


def format_queue_result_for_telegram(result: dict) -> str:
    """Format queue_cte_centers result for Telegram."""
    found = result.get("found", 0)
    queued = result.get("queued", [])
    skipped = result.get("skipped", [])
    errors = result.get("errors", [])

    lines = [f"🛠 *CTE Center Prospector* — {found} candidates matched"]
    lines.append("")

    if queued:
        lines.append(f"✅ Queued {len(queued)}:")
        for q in queued[:20]:
            sending = q.get("sending", 0)
            enroll = q.get("enrollment", 0)
            lines.append(
                f"  • {q['name'][:45]} ({q['state']}) "
                f"— {sending} sending, ~{enroll:,} students"
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


def list_cte_centers_for_telegram(
    state: Optional[str] = None,
    cs_only: bool = True,
) -> str:
    """Read-only view of CTE seed list."""
    centers = load_cte_centers()
    if state:
        centers = filter_centers_by_state(centers, state)
    if cs_only:
        centers = filter_centers_cs_only(centers)

    if not centers:
        return f"🛠 No CTE centers found{' in ' + state.upper() if state else ''}."

    header = (
        f"🛠 *CTE Centers{' in ' + state.upper() if state else ' (all territory)'}* "
        f"— {len(centers)} total"
    )
    lines = [header, ""]

    for c in centers:
        name = (c.get("name") or "?")[:50]
        st = c.get("state", "?")
        sending = c.get("sending_districts", 0)
        enroll = c.get("est_enrollment", 0)
        city = c.get("city", "")
        lines.append(
            f"• *{name}* ({st}) — {sending} sending districts, ~{enroll:,} students"
        )
        if city:
            lines.append(f"   {city}")

    lines.append("")
    lines.append("Use `/prospect_cte_centers [state]` to queue these as prospects.")
    return "\n".join(lines)
