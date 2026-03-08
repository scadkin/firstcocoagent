"""
tools/pipeline_tracker.py — Scout Phase 6F Pipeline Snapshot.

Imports Salesforce opportunity CSV exports into a "Pipeline" tab in the
Master Google Sheet. Provides pipeline summary, stale follow-up alerts,
and EOD report injection.

Triggered by:
  - Steven sending an opp CSV in Telegram (auto-detected or /pipeline_import)
  - /pipeline command for summary view

Import mode is always REPLACE ALL — pipeline is a point-in-time snapshot.

Usage (module-level, not a class):
  import tools.pipeline_tracker as pipeline_tracker
  result = pipeline_tracker.import_pipeline(csv_text)
"""

import csv
import io
import json
import logging
import os
import re
from datetime import datetime, date

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ─────────────────────────────────────────────
# TAB + COLUMN DEFINITIONS
# ─────────────────────────────────────────────

TAB_PIPELINE = "Pipeline"

PIPELINE_COLUMNS = [
    "Opportunity Name",
    "Account Name",
    "Parent Account",
    "Stage",
    "Amount",
    "Close Date",
    "Next Step",
    "Age (days)",
    "Last Activity",
    "State",
    "Created Date",
    "Date Imported",
]

# Salesforce opp CSV headers → internal keys (case-insensitive match)
_OPP_COL_MAP = {
    "opportunity name":        "opp_name",
    "account name":            "account_name",
    "parent account":          "parent_account",
    "stage":                   "stage",
    "amount":                  "amount",
    "close date":              "close_date",
    "next step":               "next_step",
    "last activity":           "last_activity",
    "created date":            "created_date",
    "billing state/province":  "state",
    "age":                     "age",
}

# Stages considered closed — these opps are not "open"
_CLOSED_STAGES = {"closed won", "closed lost", "closed - lost", "closed - won"}

# Default stale threshold (days since last activity)
PIPELINE_STALE_DAYS = int(os.environ.get("PIPELINE_STALE_DAYS", "14"))


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
    """Create Pipeline tab if missing. Always overwrite header row."""
    service = _get_service()
    sheet_id = _get_sheet_id()

    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if TAB_PIPELINE not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_PIPELINE}}}]}
        ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{TAB_PIPELINE}'!A1",
        valueInputOption="RAW",
        body={"values": [PIPELINE_COLUMNS]}
    ).execute()

    return service, sheet_id


def _parse_date(date_str: str):
    """Parse common Salesforce date formats. Returns date or None."""
    if not date_str or not date_str.strip():
        return None
    ds = date_str.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(ds, fmt).date()
        except ValueError:
            continue
    return None


def _clean_amount(val: str) -> str:
    """Strip $ and commas from amount, return clean number string."""
    if not val:
        return ""
    cleaned = val.strip().replace("$", "").replace(",", "")
    try:
        float(cleaned)
        return cleaned
    except ValueError:
        return val.strip()


def _parse_amount_float(val: str) -> float:
    """Parse an amount string to float. Returns 0.0 on failure."""
    if not val:
        return 0.0
    cleaned = str(val).strip().replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────
# CSV PARSING
# ─────────────────────────────────────────────

def _parse_opp_csv(csv_text: str) -> list[dict]:
    """
    Parse Salesforce opp CSV into normalized dicts.
    Computes Age from Created Date if not already present.
    Cleans Amount field.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return []

    records = []
    today = date.today()

    for raw_row in reader:
        row = {}
        for col, val in raw_row.items():
            col_clean = col.strip()
            mapped = _OPP_COL_MAP.get(col_clean.lower())
            if mapped:
                row[mapped] = (val or "").strip()
            elif col_clean:
                row[col_clean] = (val or "").strip()

        # Must have at least an opp name or account name
        if not row.get("opp_name") and not row.get("account_name"):
            continue

        # Clean amount
        row["amount"] = _clean_amount(row.get("amount", ""))

        # Compute age if not provided
        if not row.get("age"):
            created = _parse_date(row.get("created_date", ""))
            if created:
                row["age"] = str((today - created).days)
            else:
                row["age"] = ""

        records.append(row)

    return records


def is_opp_csv(csv_text: str) -> bool:
    """
    Check if a CSV looks like an opportunity export (not accounts).
    Returns True if the header row contains 2+ of {stage, close date, opportunity name}.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            return False
        headers_lower = {h.strip().lower() for h in reader.fieldnames}
        opp_signals = {"stage", "close date", "opportunity name"}
        matches = opp_signals & headers_lower
        return len(matches) >= 2
    except Exception:
        return False


# ─────────────────────────────────────────────
# IMPORT — REPLACE ALL
# ─────────────────────────────────────────────

def import_pipeline(csv_text: str) -> dict:
    """
    Parse Salesforce opp CSV and write to the "Pipeline" tab.
    Always clears and rewrites (point-in-time snapshot).

    Returns:
      {imported, open, closed, total_value, skipped, errors}
    """
    errors = []
    imported = 0
    open_count = 0
    closed_count = 0
    total_value = 0.0
    skipped = 0

    try:
        records = _parse_opp_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "open": 0, "closed": 0, "total_value": 0,
                "skipped": 0, "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "open": 0, "closed": 0, "total_value": 0,
                "skipped": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    today_str = date.today().strftime("%m/%d/%Y")
    rows_to_write = []

    for rec in records:
        opp_name = rec.get("opp_name", "").strip()
        if not opp_name:
            skipped += 1
            continue

        stage = rec.get("stage", "")
        amount = rec.get("amount", "")
        is_closed = stage.lower().strip() in _CLOSED_STAGES

        if is_closed:
            closed_count += 1
        else:
            open_count += 1
            total_value += _parse_amount_float(amount)

        row = [
            opp_name,
            rec.get("account_name", ""),
            rec.get("parent_account", ""),
            stage,
            amount,
            rec.get("close_date", ""),
            rec.get("next_step", ""),
            rec.get("age", ""),
            rec.get("last_activity", ""),
            rec.get("state", ""),
            rec.get("created_date", ""),
            today_str,
        ]
        rows_to_write.append(row)
        imported += 1

    try:
        service, sheet_id = _ensure_tab()

        # Clear existing data (keep header)
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PIPELINE}'!A2:ZZ",
        ).execute()

        # Write new data
        if rows_to_write:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{TAB_PIPELINE}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows_to_write}
            ).execute()

        logger.info(f"Pipeline import: {imported} opps ({open_count} open, {closed_count} closed, ${total_value:,.0f} pipeline value)")

    except Exception as e:
        errors.append(f"Sheet write failed: {e}")
        logger.error(f"import_pipeline sheet write error: {e}")

    return {
        "imported": imported,
        "open": open_count,
        "closed": closed_count,
        "total_value": total_value,
        "skipped": skipped,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# QUERIES
# ─────────────────────────────────────────────

def _load_all_opps() -> list[dict]:
    """Load all rows from Pipeline tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PIPELINE}'!A1:ZZ"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        opps = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            opps.append(dict(zip(headers, padded)))
        return opps
    except Exception as e:
        logger.error(f"_load_all_opps error: {e}")
        return []


def get_open_opps() -> list[dict]:
    """Return opps where stage is not in _CLOSED_STAGES."""
    opps = _load_all_opps()
    return [o for o in opps if o.get("Stage", "").lower().strip() not in _CLOSED_STAGES]


def get_stale_opps(stale_days: int = None) -> list[dict]:
    """
    Return open opps that are stale:
    - Last Activity > stale_days ago, OR
    - Close Date is in the past.
    Adds a 'stale_reason' field to each.
    """
    if stale_days is None:
        stale_days = PIPELINE_STALE_DAYS

    today = date.today()
    open_opps = get_open_opps()
    stale = []

    for opp in open_opps:
        reasons = []

        # Check last activity staleness
        last_activity = _parse_date(opp.get("Last Activity", ""))
        if last_activity:
            days_since = (today - last_activity).days
            if days_since > stale_days:
                reasons.append(f"No activity in {days_since} days")
        elif not opp.get("Last Activity", "").strip():
            reasons.append("No last activity date")

        # Check past-due close date
        close_date = _parse_date(opp.get("Close Date", ""))
        if close_date and close_date < today:
            days_past = (today - close_date).days
            reasons.append(f"Close date {days_past} days past due")

        if reasons:
            opp["stale_reason"] = "; ".join(reasons)
            stale.append(opp)

    # Sort by most stale first
    def staleness_key(o):
        la = _parse_date(o.get("Last Activity", ""))
        return (today - la).days if la else 9999
    stale.sort(key=staleness_key, reverse=True)

    return stale


def get_pipeline_summary() -> dict:
    """
    Build a summary of the current pipeline.
    Returns:
      {total_open, total_value, by_stage: {stage: {count, value}},
       stale_count, stale_opps, total_closed}
    """
    open_opps = get_open_opps()
    all_opps = _load_all_opps()
    stale = get_stale_opps()

    total_value = 0.0
    by_stage: dict[str, dict] = {}

    for opp in open_opps:
        stage = opp.get("Stage", "Unknown").strip() or "Unknown"
        amount = _parse_amount_float(opp.get("Amount", ""))
        total_value += amount

        if stage not in by_stage:
            by_stage[stage] = {"count": 0, "value": 0.0}
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += amount

    closed_count = len(all_opps) - len(open_opps)

    return {
        "total_open": len(open_opps),
        "total_value": total_value,
        "by_stage": by_stage,
        "stale_count": len(stale),
        "stale_opps": stale,
        "total_closed": closed_count,
    }


# ─────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────

def format_pipeline_for_telegram(summary: dict) -> str:
    """Format pipeline summary for Telegram message."""
    total_open = summary.get("total_open", 0)
    total_value = summary.get("total_value", 0)
    by_stage = summary.get("by_stage", {})
    stale_count = summary.get("stale_count", 0)
    stale_opps = summary.get("stale_opps", [])
    total_closed = summary.get("total_closed", 0)

    if total_open == 0 and total_closed == 0:
        return "📊 *Pipeline*\n\nNo opportunities found. Upload a Salesforce opp CSV to get started."

    if total_open == 0:
        return f"📊 *Pipeline*\n\nNo open opportunities ({total_closed} closed).\nUpload a fresh Salesforce opp CSV to update."

    lines = [
        f"📊 *Pipeline Summary*",
        f"",
        f"*{total_open} open opps* | ${total_value:,.0f} total value",
    ]

    if total_closed:
        lines.append(f"({total_closed} closed opps not shown)")
    lines.append("")

    # Stage breakdown — sort by value descending
    lines.append("*By Stage:*")
    for stage, data in sorted(by_stage.items(), key=lambda x: x[1]["value"], reverse=True):
        lines.append(f"  • {stage}: {data['count']} opp{'s' if data['count'] != 1 else ''} (${data['value']:,.0f})")

    # Stale alerts
    if stale_count > 0:
        lines.append("")
        lines.append(f"⚠️ *{stale_count} stale opp{'s' if stale_count != 1 else ''}:*")
        for opp in stale_opps[:5]:
            name = opp.get("Opportunity Name", "?")
            acct = opp.get("Account Name", "")
            reason = opp.get("stale_reason", "")
            label = f"{name}"
            if acct:
                label += f" ({acct})"
            lines.append(f"  • {label} — {reason}")
        if stale_count > 5:
            lines.append(f"  ... and {stale_count - 5} more")

    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if sheet_id:
        lines.append(f"\n📋 [Full Pipeline Sheet](https://docs.google.com/spreadsheets/d/{sheet_id})")

    return "\n".join(lines)


def build_pipeline_alerts() -> str:
    """
    Build pipeline alert text for EOD report injection.
    Returns empty string if no alerts (so EOD prompt omits the section).
    """
    try:
        stale = get_stale_opps()
        if not stale:
            return ""

        lines = ["PIPELINE ALERT DATA:"]
        lines.append(f"{len(stale)} stale/past-due opportunities:")
        for opp in stale[:10]:
            name = opp.get("Opportunity Name", "?")
            acct = opp.get("Account Name", "")
            stage = opp.get("Stage", "")
            amount = opp.get("Amount", "")
            reason = opp.get("stale_reason", "")
            parts = [name]
            if acct:
                parts.append(f"Account: {acct}")
            if stage:
                parts.append(f"Stage: {stage}")
            if amount:
                parts.append(f"${amount}")
            parts.append(reason)
            lines.append(f"  - {' | '.join(parts)}")
        if len(stale) > 10:
            lines.append(f"  ... and {len(stale) - 10} more")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"build_pipeline_alerts error: {e}")
        return ""
