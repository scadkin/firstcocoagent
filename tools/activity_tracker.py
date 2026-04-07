"""
tools/activity_tracker.py — Scout Phase 6C activity logging.

Logs all Scout-driven actions to the "Activities" tab in the Master Google Sheet.
Manages KPI goals in the "Goals" tab.
Scans Gmail for PandaDoc quote events and Dialpad call summary emails.

Tabs:
  - Activities : one row per logged action
  - Goals      : one row per KPI goal type

Usage (module-level, not a class):
  import tools.activity_tracker as activity_tracker
  activity_tracker.log_activity("research_job", district="Austin ISD", ...)
"""

import logging
import os
import json
import re
from datetime import datetime, date
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_ACTIVITIES = "Activities"
TAB_GOALS = "Goals"

ACTIVITY_COLUMNS = [
    "Date",
    "Time",
    "Type",
    "District/Account",
    "Contact",
    "Notes",
    "Source",
    "Message ID",
]

GOALS_COLUMNS = [
    "Goal Type",
    "Daily Target",
    "Description",
]

# Valid activity types
ACTIVITY_TYPES = {
    "research_job":    "District researched",
    "sequence_built":  "Email sequence built",
    "email_drafted":   "Email drafted",
    "email_saved":     "Email saved to Gmail",
    "call_logged":     "Call logged",
    "pandadoc_event":  "PandaDoc quote event",
    "dialpad_call":    "Dialpad call summary",
    "call_list_generated": "Daily call list generated",
}

# Default daily goals seeded on first run
DEFAULT_GOALS = [
    ("calls_made",           10, "Outreach calls per day"),
    ("districts_researched",  2, "Districts fully researched"),
    ("emails_drafted",        5, "Emails drafted or saved"),
]


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _get_sheet_id():
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID not set")
    return sheet_id


def _ensure_tabs():
    """Create Activities and Goals tabs + headers if missing. Seeds default goals."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    to_create = []
    for tab in [TAB_ACTIVITIES, TAB_GOALS]:
        if tab not in existing:
            to_create.append({"addSheet": {"properties": {"title": tab}}})

    if to_create:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": to_create}
        ).execute()

    # Write headers if tab is empty
    _ensure_headers(service, sheet_id, TAB_ACTIVITIES, ACTIVITY_COLUMNS)
    _ensure_headers(service, sheet_id, TAB_GOALS, GOALS_COLUMNS)

    # Seed default goals if Goals tab was just created or is empty
    _seed_default_goals(service, sheet_id)


def _ensure_headers(service, sheet_id, tab, columns):
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A1:Z1"
    ).execute()
    values = result.get("values", [])
    if not values or not values[0]:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab}'!A1",
            valueInputOption="RAW",
            body={"values": [columns]}
        ).execute()


def _seed_default_goals(service, sheet_id):
    """Write default goals if the Goals tab only has a header row (or is empty)."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_GOALS}'!A:C"
    ).execute()
    rows = result.get("values", [])
    # rows[0] = header, rows[1:] = data
    if len(rows) <= 1:
        rows_to_write = [[gt, tgt, desc] for gt, tgt, desc in DEFAULT_GOALS]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{TAB_GOALS}'!A:C",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows_to_write}
        ).execute()
        logger.info("Seeded default KPI goals")


def _load_message_ids(service, sheet_id) -> set:
    """Return set of all Message IDs already in Activities tab (for dedup)."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_ACTIVITIES}'!A:H"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return set()
    headers = rows[0]
    try:
        mid_idx = headers.index("Message ID")
    except ValueError:
        return set()
    ids = set()
    for row in rows[1:]:
        if mid_idx < len(row) and row[mid_idx]:
            ids.add(row[mid_idx].strip())
    return ids


# ─────────────────────────────────────────────
# ACTIVITY LOGGING
# ─────────────────────────────────────────────

def log_activity(
    activity_type: str,
    district: str = "",
    contact: str = "",
    notes: str = "",
    source: str = "scout",
    message_id: str = "",
):
    """
    Append one activity row to the Activities tab.

    activity_type: one of ACTIVITY_TYPES keys
    district:      district or account name
    contact:       contact name or email
    notes:         free-text notes
    source:        "scout" | "gmail_scan" | "manual"
    message_id:    Gmail message ID (for dedup of inbox scans)
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        _ensure_tabs()

        now = datetime.now()
        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M"),
            activity_type,
            district,
            contact,
            notes,
            source,
            message_id,
        ]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVITIES}'!A:H",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
        logger.info(f"Activity logged: {activity_type} | {district}")
    except Exception as e:
        logger.error(f"log_activity failed: {e}")


def is_activity_logged(message_id: str) -> bool:
    """Return True if this Gmail Message ID is already in Activities tab."""
    if not message_id:
        return False
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        existing = _load_message_ids(service, sheet_id)
        return message_id in existing
    except Exception as e:
        logger.error(f"is_activity_logged error: {e}")
        return False


# ─────────────────────────────────────────────
# ACTIVITY QUERIES
# ─────────────────────────────────────────────

def _load_activity_rows(date_str: str = None) -> list[dict]:
    """Load all activity rows, optionally filtered to a specific date (YYYY-MM-DD)."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_ACTIVITIES}'!A:H"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        activities = []
        for row in rows[1:]:
            # Pad row to header length
            padded = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded))
            if date_str and record.get("Date", "") != date_str:
                continue
            activities.append(record)
        return activities
    except Exception as e:
        logger.error(f"_load_activity_rows error: {e}")
        return []


def get_today_activities(date_str: str = None) -> list[dict]:
    """Return all activity rows for today (or a specified date YYYY-MM-DD)."""
    target = date_str or date.today().strftime("%Y-%m-%d")
    return _load_activity_rows(date_str=target)


def get_activity_summary(date_str: str = None) -> dict:
    """
    Return counts by activity type for the given date (default: today).
    Also returns a human-readable summary string.
    """
    target = date_str or date.today().strftime("%Y-%m-%d")
    rows = _load_activity_rows(date_str=target)

    counts = {k: 0 for k in ACTIVITY_TYPES}
    for row in rows:
        atype = row.get("Type", "")
        if atype in counts:
            counts[atype] += 1

    # Build readable summary
    lines = []
    label_map = {
        "research_job":   "Districts researched",
        "sequence_built": "Sequences built",
        "email_drafted":  "Emails drafted",
        "email_saved":    "Emails saved to Gmail",
        "call_logged":    "Calls logged",
        "pandadoc_event": "PandaDoc events",
        "dialpad_call":   "Dialpad call summaries",
        "call_list_generated": "Call lists generated",
    }
    for key, label in label_map.items():
        if counts[key]:
            lines.append(f"  {label}: {counts[key]}")

    summary_str = "\n".join(lines) if lines else "  No activities logged yet."
    return {**counts, "date": target, "summary_text": summary_str}


# ─────────────────────────────────────────────
# KPI GOALS
# ─────────────────────────────────────────────

def get_goals() -> list[dict]:
    """Return all goals as list of dicts: {goal_type, daily_target, description}."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_GOALS}'!A:C"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        goals = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded))
            goals.append({
                "goal_type":    record.get("Goal Type", ""),
                "daily_target": int(record.get("Daily Target", 0) or 0),
                "description":  record.get("Description", ""),
            })
        return goals
    except Exception as e:
        logger.error(f"get_goals error: {e}")
        return []


def set_goal(goal_type: str, daily_target: int, description: str = ""):
    """
    Update or insert a KPI goal.
    If goal_type already exists, update its target. Otherwise append new row.
    """
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        _ensure_tabs()

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_GOALS}'!A:C"
        ).execute()
        rows = result.get("values", [])
        headers = rows[0] if rows else GOALS_COLUMNS

        # Find existing row index
        existing_row_idx = None
        for i, row in enumerate(rows[1:], start=2):  # 1-indexed, row 1 = header
            if row and row[0] == goal_type:
                existing_row_idx = i
                break

        desc = description or next(
            (d for gt, _, d in DEFAULT_GOALS if gt == goal_type), ""
        )

        if existing_row_idx:
            # Update in place
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{TAB_GOALS}'!A{existing_row_idx}:C{existing_row_idx}",
                valueInputOption="RAW",
                body={"values": [[goal_type, daily_target, desc]]}
            ).execute()
        else:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{TAB_GOALS}'!A:C",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[goal_type, daily_target, desc]]}
            ).execute()
        logger.info(f"Goal set: {goal_type} = {daily_target}")
    except Exception as e:
        logger.error(f"set_goal error: {e}")


def get_daily_progress(date_str: str = None) -> dict:
    """
    Compare today's actual activity counts against KPI goals.

    Returns dict keyed by goal_type:
      { "calls_made": {"target": 10, "actual": 3, "pct": 30, "description": "..."}, ... }

    Also returns "progress_text" — a formatted string for Telegram.
    """
    target_date = date_str or date.today().strftime("%Y-%m-%d")
    summary = get_activity_summary(date_str=target_date)
    goals = get_goals()

    # Map activity types to goal types
    # calls_made counts both call_logged + dialpad_call
    # emails_drafted counts email_drafted + email_saved
    # districts_researched counts research_job
    actuals = {
        "calls_made":           summary.get("call_logged", 0) + summary.get("dialpad_call", 0),
        "districts_researched": summary.get("research_job", 0),
        "emails_drafted":       summary.get("email_drafted", 0) + summary.get("email_saved", 0),
    }

    progress = {}
    for goal in goals:
        gt = goal["goal_type"]
        target = goal["daily_target"]
        actual = actuals.get(gt, 0)
        pct = round((actual / target * 100) if target > 0 else 0)
        progress[gt] = {
            "target":      target,
            "actual":      actual,
            "pct":         pct,
            "description": goal["description"],
        }

    # Build Telegram-ready progress text
    lines = [f"📊 *KPI Progress — {target_date}*\n"]
    emoji_map = {
        "calls_made":           "📞",
        "districts_researched": "🔍",
        "emails_drafted":       "✉️",
    }
    for gt, data in progress.items():
        bar = _progress_bar(data["pct"])
        emoji = emoji_map.get(gt, "•")
        lines.append(
            f"{emoji} {data['description']}: {data['actual']}/{data['target']} "
            f"({data['pct']}%)\n{bar}"
        )

    progress["progress_text"] = "\n".join(lines)
    progress["date"] = target_date
    return progress


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = min(width, round(pct / 100 * width))
    return "  [" + "█" * filled + "░" * (width - filled) + f"] {pct}%"


# ─────────────────────────────────────────────
# GMAIL INTELLIGENCE — PandaDoc + Dialpad
# ─────────────────────────────────────────────

def scan_pandadoc_notifications(gas_bridge) -> list[dict]:
    """
    Search Gmail inbox for PandaDoc quote notification emails.
    Returns list of activity dicts (not yet logged — caller decides whether to log).

    Parses: opened / signed / rejected events.
    Subject lines look like:
      "[PandaDoc] Quote Opened: Austin ISD - CodeCombat Proposal"
      "[PandaDoc] Document Signed: ..."
    """
    activities = []
    try:
        results = gas_bridge.search_inbox(
            query='from:notifications@pandadoc.com subject:("opened" OR "signed" OR "rejected" OR "viewed")',
            max_results=20
        )
        for email in results:
            msg_id = email.get("id", "") or email.get("messageId", "")
            subject = email.get("subject", "")
            date_str = email.get("date", "")

            # Parse event type from subject
            event = "viewed"
            for keyword in ["signed", "rejected", "opened", "viewed"]:
                if keyword in subject.lower():
                    event = keyword
                    break

            # Try to extract document/district name from subject
            # Pattern: "Quote Opened: <name>" or "Document Signed: <name>"
            doc_name = ""
            match = re.search(r":\s*(.+)$", subject)
            if match:
                doc_name = match.group(1).strip()

            activities.append({
                "activity_type": "pandadoc_event",
                "district":      doc_name,
                "contact":       "",
                "notes":         f"PandaDoc {event}: {subject}",
                "source":        "gmail_scan",
                "message_id":    msg_id,
            })
    except Exception as e:
        logger.error(f"scan_pandadoc_notifications error: {e}")
    return activities


def scan_dialpad_summaries(gas_bridge) -> list[dict]:
    """
    Search Gmail inbox for Dialpad call summary emails.
    Returns list of activity dicts (not yet logged).

    Dialpad sends emails like:
      Subject: "Call Summary with John Smith"
      Body: duration, notes, etc.
    Steven must enable in Dialpad → Settings → Notifications → Call Summary.
    """
    activities = []
    try:
        results = gas_bridge.search_inbox(
            query='subject:"Call Summary" (from:no-reply@dialpad.com OR from:dialpad.com)',
            max_results=20
        )
        for email in results:
            msg_id = email.get("id", "") or email.get("messageId", "")
            subject = email.get("subject", "")
            snippet = email.get("snippet", "")

            # Parse contact name from subject: "Call Summary with John Smith"
            contact = ""
            match = re.search(r"Call Summary with (.+)", subject, re.IGNORECASE)
            if match:
                contact = match.group(1).strip()

            activities.append({
                "activity_type": "dialpad_call",
                "district":      "",
                "contact":       contact,
                "notes":         f"Dialpad call summary: {snippet[:100]}",
                "source":        "gmail_scan",
                "message_id":    msg_id,
            })
    except Exception as e:
        logger.error(f"scan_dialpad_summaries error: {e}")
    return activities


def sync_gmail_activities(gas_bridge) -> dict:
    """
    Run both PandaDoc and Dialpad inbox scans.
    Deduplicates against existing Activities tab rows.
    Logs only new events.

    Returns: {pandadoc_logged: N, dialpad_logged: N, already_seen: N}
    """
    pandadoc_logged = 0
    dialpad_logged = 0
    already_seen = 0

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        _ensure_tabs()
        existing_ids = _load_message_ids(service, sheet_id)

        all_activities = (
            scan_pandadoc_notifications(gas_bridge)
            + scan_dialpad_summaries(gas_bridge)
        )

        for act in all_activities:
            mid = act.get("message_id", "")
            if mid and mid in existing_ids:
                already_seen += 1
                continue

            log_activity(
                activity_type=act["activity_type"],
                district=act["district"],
                contact=act["contact"],
                notes=act["notes"],
                source=act["source"],
                message_id=mid,
            )
            if mid:
                existing_ids.add(mid)

            if act["activity_type"] == "pandadoc_event":
                pandadoc_logged += 1
            elif act["activity_type"] == "dialpad_call":
                dialpad_logged += 1

    except Exception as e:
        logger.error(f"sync_gmail_activities error: {e}")

    return {
        "pandadoc_logged": pandadoc_logged,
        "dialpad_logged":  dialpad_logged,
        "already_seen":    already_seen,
    }


# ─────────────────────────────────────────────
# FORMATTED SUMMARY FOR PROMPTS
# ─────────────────────────────────────────────

def build_brief_data_block(date_str: str = None) -> str:
    """
    Build a plain-text data block for injection into morning_brief.md / eod_report.md.
    Claude uses this as ground truth — no inventing numbers.
    """
    target = date_str or date.today().strftime("%Y-%m-%d")
    summary = get_activity_summary(date_str=target)
    progress = get_daily_progress(date_str=target)

    lines = [
        f"REAL ACTIVITY DATA for {target} (from Google Sheets — use these numbers, do not invent):",
        f"  Districts researched: {summary.get('research_job', 0)}",
        f"  Sequences built: {summary.get('sequence_built', 0)}",
        f"  Emails drafted: {summary.get('email_drafted', 0)}",
        f"  Emails saved to Gmail: {summary.get('email_saved', 0)}",
        f"  Calls logged: {summary.get('call_logged', 0)}",
        f"  PandaDoc events: {summary.get('pandadoc_event', 0)}",
        f"  Dialpad calls parsed: {summary.get('dialpad_call', 0)}",
        "",
        "KPI GOALS vs ACTUALS (daily targets):",
    ]
    goal_labels = {
        "calls_made":           "Calls",
        "districts_researched": "Districts researched",
        "emails_drafted":       "Emails drafted/saved",
    }
    for gt, label in goal_labels.items():
        if gt in progress and isinstance(progress[gt], dict):
            d = progress[gt]
            lines.append(f"  {label}: {d['actual']}/{d['target']} ({d['pct']}%)")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# DORMANT LEAD DETECTION (#12)
# ─────────────────────────────────────────────

def get_dormant_accounts(days: int = 90) -> list[dict]:
    """
    Find accounts with Scout-tracked activity that went silent.
    Only returns accounts that HAVE had activity (at least 1 logged event)
    but whose most recent activity is >= `days` ago.
    Excludes current active customers.

    Returns list of dicts sorted by days_dormant descending:
    [{account, last_date, last_type, days_dormant, activity_count}]
    """
    from datetime import datetime as dt

    try:
        all_rows = _load_activity_rows()  # No date filter — all history
        if not all_rows:
            return []

        # Group by account
        by_account = {}
        for row in all_rows:
            account = (row.get("District/Account") or "").strip()
            if not account:
                continue
            date_str = row.get("Date", "")
            act_type = row.get("Type", "")
            if account not in by_account:
                by_account[account] = {"dates": [], "types": [], "count": 0}
            by_account[account]["dates"].append(date_str)
            by_account[account]["types"].append(act_type)
            by_account[account]["count"] += 1

        # Build exclusion set from active customers
        try:
            import tools.csv_importer as csv_importer
            active_accounts = csv_importer.get_active_accounts()
            active_keys = set()
            for acc in active_accounts:
                name = (acc.get("Active Account Name", "") or acc.get("Display Name", "")).strip()
                if name:
                    active_keys.add(name.lower())
                    active_keys.add(csv_importer.normalize_name(name))
        except Exception:
            active_keys = set()

        today = dt.now().date()
        dormant = []

        for account, data in by_account.items():
            # Skip active customers
            if account.lower() in active_keys or csv_importer.normalize_name(account) in active_keys:
                continue

            # Find most recent activity date
            latest_date = None
            latest_type = ""
            for i, d in enumerate(data["dates"]):
                try:
                    parsed = dt.strptime(d, "%Y-%m-%d").date()
                    if latest_date is None or parsed > latest_date:
                        latest_date = parsed
                        latest_type = data["types"][i]
                except (ValueError, TypeError):
                    continue

            if latest_date is None:
                continue

            days_dormant = (today - latest_date).days
            if days_dormant >= days:
                dormant.append({
                    "account": account,
                    "last_date": latest_date.strftime("%Y-%m-%d"),
                    "last_type": latest_type,
                    "days_dormant": days_dormant,
                    "activity_count": data["count"],
                })

        dormant.sort(key=lambda x: x["days_dormant"], reverse=True)
        return dormant

    except Exception as e:
        logger.error(f"get_dormant_accounts error: {e}", exc_info=True)
        return []


def format_dormant_for_telegram(dormant: list, limit: int = 20) -> str:
    """Format dormant accounts for Telegram display."""
    if not dormant:
        return "No dormant accounts found."

    lines = [f"💤 *Dormant Accounts* ({len(dormant)} total)\n"]
    for i, d in enumerate(dormant[:limit], 1):
        lines.append(
            f"  {i}. *{d['account']}*\n"
            f"     Last: {d['last_date']} ({d['days_dormant']}d ago) — {d['last_type']}"
            f" | {d['activity_count']} total activities"
        )
    if len(dormant) > limit:
        lines.append(f"\n  ... and {len(dormant) - limit} more")
    return "\n".join(lines)
