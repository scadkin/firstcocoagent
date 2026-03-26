"""
tools/todo_manager.py — Scout todo list management.

Persists todos in a "Todo List" tab in the Master Google Sheet.
Steven can add, complete, and view items via Telegram commands or natural language.
Hourly check-ins reference open items instead of generic greetings.

Tabs:
  - Todo List : one row per todo item

Usage (module-level, not a class):
  import tools.todo_manager as todo_manager
  todo_manager.add_todo("Follow up with Austin ISD", priority="high")
  todo_manager.complete_todo(3)
  todo_manager.get_open_todos() -> list[dict]
  todo_manager.get_checkin_summary() -> str
"""

import logging
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_TODOS = "Todo List"

TODO_COLUMNS = [
    "ID",
    "Task",
    "Priority",      # high | medium | low
    "Status",         # open | done
    "Created",        # YYYY-MM-DD HH:MM
    "Completed",      # YYYY-MM-DD HH:MM or empty
    "Due Date",       # YYYY-MM-DD or empty
]

VALID_PRIORITIES = {"high", "medium", "low"}


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


def _ensure_tab():
    """Create Todo List tab if missing. Always overwrite header row."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_TODOS not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_TODOS}}}]}
        ).execute()
        logger.info(f"Created tab: {TAB_TODOS}")

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_TODOS}'!A1",
        valueInputOption="RAW",
        body={"values": [TODO_COLUMNS]}
    ).execute()

    return service, sheet_id


def _read_all_rows():
    """Read all data rows from the Todo List tab. Returns list of dicts."""
    service = _get_service()
    sheet_id = _get_sheet_id()
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{TAB_TODOS}'!A:G",
    ).execute()
    rows = result.get("values", [])
    if len(rows) <= 1:
        return []
    headers = rows[0]
    items = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        items.append(dict(zip(headers, padded)))
    return items


def _next_id(items: list[dict]) -> int:
    """Get the next available ID."""
    max_id = 0
    for item in items:
        try:
            max_id = max(max_id, int(item.get("ID", 0)))
        except (ValueError, TypeError):
            pass
    return max_id + 1


def _write_all_rows(items: list[dict]):
    """Overwrite all data rows (preserving header)."""
    service, sheet_id = _ensure_tab()

    # Clear existing data rows
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{TAB_TODOS}'!A2:G10000",
    ).execute()

    if not items:
        return

    rows = []
    for item in items:
        rows.append([item.get(col, "") for col in TODO_COLUMNS])

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_TODOS}'!A2",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()


def _now_str() -> str:
    """Current time as YYYY-MM-DD HH:MM in CST."""
    import pytz
    cst = pytz.timezone("America/Chicago")
    return datetime.now(cst).strftime("%Y-%m-%d %H:%M")


def _today_str() -> str:
    """Current date as YYYY-MM-DD in CST."""
    import pytz
    cst = pytz.timezone("America/Chicago")
    return datetime.now(cst).strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def add_todo(task: str, priority: str = "medium", due_date: str = "") -> dict:
    """Add a new todo item. Returns the created item."""
    priority = priority.lower().strip()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    items = _read_all_rows()
    new_id = _next_id(items)

    new_item = {
        "ID": str(new_id),
        "Task": task.strip(),
        "Priority": priority,
        "Status": "open",
        "Created": _now_str(),
        "Completed": "",
        "Due Date": due_date.strip(),
    }
    items.append(new_item)
    _write_all_rows(items)
    logger.info(f"Added todo #{new_id}: {task}")
    return new_item


def complete_todo(todo_id: int) -> dict:
    """Mark a todo as done by ID. Returns the updated item or error dict."""
    items = _read_all_rows()
    for item in items:
        if str(item.get("ID", "")) == str(todo_id):
            if item["Status"] == "done":
                return {"error": f"Todo #{todo_id} is already done."}
            item["Status"] = "done"
            item["Completed"] = _now_str()
            _write_all_rows(items)
            logger.info(f"Completed todo #{todo_id}: {item['Task']}")
            return item
    return {"error": f"Todo #{todo_id} not found."}


def complete_todo_by_match(text: str) -> dict:
    """Find and complete an open todo matching the given text.
    Tries exact substring match first, then word overlap.
    Returns the completed item or error dict.
    """
    items = _read_all_rows()
    open_items = [i for i in items if i.get("Status") == "open"]

    if not open_items:
        return {"error": "No open todos to complete."}

    text_lower = text.lower().strip()

    # Try exact substring match
    for item in open_items:
        if text_lower in item.get("Task", "").lower():
            return complete_todo(int(item["ID"]))

    # Try word overlap scoring
    text_words = set(text_lower.split())
    best_match = None
    best_score = 0
    for item in open_items:
        task_words = set(item.get("Task", "").lower().split())
        overlap = len(text_words & task_words)
        if overlap > best_score:
            best_score = overlap
            best_match = item

    if best_match and best_score >= 2:
        return complete_todo(int(best_match["ID"]))

    return {"error": f"No open todo matching \"{text}\". Use `/todos` to see your list."}


def get_open_todos() -> list[dict]:
    """Get all open todos, sorted by priority (high first) then ID."""
    items = _read_all_rows()
    open_items = [i for i in items if i.get("Status") == "open"]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    open_items.sort(key=lambda x: (priority_order.get(x.get("Priority", "medium"), 1), int(x.get("ID", 0))))
    return open_items


def get_all_todos(include_done: bool = False) -> list[dict]:
    """Get all todos. If include_done=False, only open items."""
    items = _read_all_rows()
    if not include_done:
        items = [i for i in items if i.get("Status") == "open"]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: (
        0 if x.get("Status") == "open" else 1,
        priority_order.get(x.get("Priority", "medium"), 1),
        int(x.get("ID", 0)),
    ))
    return items


def remove_todo(todo_id: int) -> dict:
    """Remove a todo entirely by ID."""
    items = _read_all_rows()
    before = len(items)
    items = [i for i in items if str(i.get("ID", "")) != str(todo_id)]
    if len(items) == before:
        return {"error": f"Todo #{todo_id} not found."}
    _write_all_rows(items)
    logger.info(f"Removed todo #{todo_id}")
    return {"success": True, "removed_id": todo_id}


def clear_completed() -> dict:
    """Remove all completed todos."""
    items = _read_all_rows()
    open_items = [i for i in items if i.get("Status") == "open"]
    removed = len(items) - len(open_items)
    _write_all_rows(open_items)
    logger.info(f"Cleared {removed} completed todos")
    return {"cleared": removed, "remaining": len(open_items)}


def update_priority(todo_id: int, priority: str) -> dict:
    """Change priority of a todo."""
    priority = priority.lower().strip()
    if priority not in VALID_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Use: high, medium, low"}
    items = _read_all_rows()
    for item in items:
        if str(item.get("ID", "")) == str(todo_id):
            item["Priority"] = priority
            _write_all_rows(items)
            return item
    return {"error": f"Todo #{todo_id} not found."}


def format_todos_for_telegram(items: list[dict], title: str = "📋 Your Todo List") -> str:
    """Format a list of todo items for Telegram display."""
    if not items:
        return f"{title}\n\nNo items! Add one with `add: [task]`"

    lines = [title, ""]
    for item in items:
        status_icon = "✅" if item.get("Status") == "done" else {
            "high": "🔴",
            "medium": "🟡",
            "low": "⚪",
        }.get(item.get("Priority", "medium"), "🟡")

        task_text = item.get("Task", "")
        if item.get("Status") == "done":
            task_text = f"~{task_text}~"

        line = f"{status_icon} *#{item.get('ID', '?')}* {task_text}"

        due = item.get("Due Date", "")
        if due:
            today = _today_str()
            if due < today and item.get("Status") == "open":
                line += f"  ⚠️ overdue ({due})"
            else:
                line += f"  📅 {due}"

        lines.append(line)

    return "\n".join(lines)


def get_checkin_summary() -> str:
    """Build the hourly check-in message referencing open todos."""
    open_items = get_open_todos()
    today = _today_str()

    if not open_items:
        return (
            "📊 Hourly check-in — your todo list is clear!\n\n"
            "Add items with `add: [task]` or tell me what you're working on."
        )

    # Count by priority
    high = [i for i in open_items if i.get("Priority") == "high"]
    overdue = [i for i in open_items if i.get("Due Date", "") and i["Due Date"] < today]

    lines = [f"📊 Hourly check-in — *{len(open_items)} open todo{'s' if len(open_items) != 1 else ''}*"]

    if overdue:
        lines.append(f"⚠️ {len(overdue)} overdue!")

    lines.append("")

    # Show top 3 items
    shown = open_items[:3]
    for item in shown:
        icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(item.get("Priority", "medium"), "🟡")
        line = f"{icon} #{item['ID']} {item['Task']}"
        due = item.get("Due Date", "")
        if due and due < today:
            line += " ⚠️"
        lines.append(line)

    remaining = len(open_items) - len(shown)
    if remaining > 0:
        lines.append(f"   +{remaining} more")

    lines.append("")
    lines.append("What are you working on? Update me or `done: [task]` to check one off.")

    return "\n".join(lines)
