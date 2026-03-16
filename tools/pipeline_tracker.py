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
TAB_CLOSED_LOST = "Closed Lost"

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
    "Type",
    "Primary Contact",
    "Probability (%)",
    "Description",
    "Opportunity Owner",
]

# Extra columns for Closed Lost tab (appended after PIPELINE_COLUMNS)
CLOSED_LOST_EXTRA_COLUMNS = [
    "Lost Reason",
    "Contact Email",
    "Fiscal Period",
    "Lead Source",
]

# Salesforce opp CSV headers → internal keys (case-insensitive match)
_OPP_COL_MAP = {
    "opportunity name":        "opp_name",
    "account name":            "account_name",
    "parent account":          "parent_account",
    "stage":                   "stage",
    "amount":                  "amount",
    "close date":              "close_date",
    "close date (2)":          "close_date",
    "next step":               "next_step",
    "last activity":           "last_activity",
    "created date":            "created_date",
    "billing state/province":  "state",
    "age":                     "age",
    "primary contact":         "primary_contact",
    "probability (%)":         "probability",
    "description":             "description",
    "type":                    "opp_type",
    "opportunity owner":       "owner",
    "lost reason":             "lost_reason",
    "contact: email":          "contact_email",
    "fiscal period":           "fiscal_period",
    "lead source":             "lead_source",
}

# Stages considered closed — these opps are not "open"
_CLOSED_STAGES = {"closed won", "closed lost", "closed - lost", "closed - won"}

# Stale tiers (days since last activity)
TIER_NEEDS_UPDATE = 14    # "Needs Update"
TIER_GOING_STALE = 30     # "Needs Check-In / Going Stale"
TIER_GOING_COLD = 45      # "Risk Going Cold!"


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


# Words that should stay uppercase when converting from ALL CAPS
_UPPERCASE_WORDS = {
    "hs", "ms", "es", "isd", "usd", "cisd", "cusd", "gisd", "nisd",
    "sd", "rsd", "csd", "ccsd", "musd", "pusd", "susd", "disd",
    "ii", "iii", "iv", "stem", "pk", "jh",
    "ilt", "lausd", "hisd", "aisd", "episd", "saisd", "fwisd",
}

# Words that should stay lowercase (articles, prepositions, conjunctions)
_LOWERCASE_WORDS = {"of", "the", "and", "in", "at", "for", "to", "a", "an", "on"}


def _smart_title_case(name: str) -> str:
    """
    Convert ALL CAPS names to natural sentence case for use in emails/sequences.
    - Preserves known acronyms (ISD, HS, STEM, etc.)
    - Preserves parenthetical acronyms like (ILT)
    - Lowercases articles/prepositions mid-name
    - Only converts if the name appears to be ALL CAPS (len > 3)
    """
    if not name or not name.strip():
        return name
    stripped = name.strip()
    # Only convert if it looks ALL CAPS (ignore short strings like "CA")
    if stripped != stripped.upper() or len(stripped) <= 3:
        return stripped

    words = stripped.split()
    result = []
    for i, word in enumerate(words):
        # Handle parenthetical like "(ILT)"
        if word.startswith("(") and word.endswith(")"):
            inner = word[1:-1]
            if inner.lower() in _UPPERCASE_WORDS or len(inner) <= 4:
                result.append(word)  # keep as-is
            else:
                result.append("(" + inner.capitalize() + ")")
            continue

        word_lower = word.lower()
        # Known acronyms stay uppercase
        if word_lower in _UPPERCASE_WORDS:
            result.append(word.upper())
        # Articles/prepositions lowercase (unless first word)
        elif i > 0 and word_lower in _LOWERCASE_WORDS:
            result.append(word_lower)
        else:
            result.append(word.capitalize())

    return " ".join(result)


# Map from internal keys back to Pipeline column headers
_KEY_TO_COLUMN = {
    "opp_name":        "Opportunity Name",
    "account_name":    "Account Name",
    "parent_account":  "Parent Account",
    "stage":           "Stage",
    "amount":          "Amount",
    "close_date":      "Close Date",
    "next_step":       "Next Step",
    "age":             "Age (days)",
    "last_activity":   "Last Activity",
    "state":           "State",
    "created_date":    "Created Date",
    "opp_type":        "Type",
    "primary_contact": "Primary Contact",
    "probability":     "Probability (%)",
    "description":     "Description",
    "owner":           "Opportunity Owner",
    "lost_reason":     "Lost Reason",
    "contact_email":   "Contact Email",
    "fiscal_period":   "Fiscal Period",
    "lead_source":     "Lead Source",
}


def _build_pipeline_row(headers: list[str], rec: dict, date_imported: str) -> list:
    """Build a sheet row matching the given headers from a parsed opp record."""
    row = []
    for h in headers:
        if h == "Date Imported":
            row.append(date_imported)
            continue
        # Find internal key for this header
        internal_key = None
        for k, v in _KEY_TO_COLUMN.items():
            if v == h:
                internal_key = k
                break
        if internal_key and internal_key in rec:
            row.append(rec[internal_key])
        elif h in rec:
            # Extra column — stored under original CSV header name
            row.append(rec[h])
        else:
            row.append("")
    return row


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

def _parse_opp_csv(csv_text: str) -> tuple[list[dict], list[str]]:
    """
    Parse Salesforce opp CSV into normalized dicts.
    Computes Age from Created Date if not already present.
    Cleans Amount field.
    Returns (records, extra_cols) — extra_cols are CSV columns not in _OPP_COL_MAP.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return [], []

    # Identify extra columns not covered by _OPP_COL_MAP
    extra_cols = []
    for h in reader.fieldnames:
        h_clean = h.strip()
        if h_clean and h_clean.lower() not in _OPP_COL_MAP:
            extra_cols.append(h_clean)

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

        # Normalize ALL CAPS names to sentence case
        for key in ("opp_name", "account_name", "parent_account", "primary_contact"):
            if row.get(key):
                row[key] = _smart_title_case(row[key])

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

    return records, extra_cols


def is_opp_csv(csv_text: str) -> bool:
    """
    Check if a CSV looks like an opportunity export (not accounts).
    Returns True if the header row contains 2+ of {stage, close date, opportunity name}
    AND does NOT contain account-specific columns (# of Active Licenses, # of Opportunities).

    Steven's "active accounts" Salesforce report includes opp columns (Stage, Close Date,
    Opportunity Name) because it's a joined report. Account-specific columns like
    "# of Active Licenses" and "# of Opportunities" distinguish it from a pure opp export.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            return False
        headers_lower = {h.strip().lower() for h in reader.fieldnames}

        # Account-specific columns — if present, this is an account CSV, not opps
        account_signals = {"# of active licenses", "# of opportunities"}
        if account_signals & headers_lower:
            return False

        opp_signals = {"stage", "close date", "close date (2)", "opportunity name"}
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
        records, extra_cols = _parse_opp_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "open": 0, "closed": 0, "total_value": 0,
                "skipped": 0, "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "open": 0, "closed": 0, "total_value": 0,
                "skipped": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    # Build full headers: base columns + any extra CSV columns
    full_headers = list(PIPELINE_COLUMNS)
    for col in extra_cols:
        if col not in full_headers:
            full_headers.append(col)

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

        row = _build_pipeline_row(full_headers, rec, today_str)
        rows_to_write.append(row)
        imported += 1

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Ensure tab exists
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if TAB_PIPELINE not in existing:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": TAB_PIPELINE}}}]}
            ).execute()

        # Clear entire tab and rewrite with headers + data
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PIPELINE}'!A1:ZZ",
        ).execute()

        all_rows = [full_headers] + rows_to_write
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_PIPELINE}'!A1",
            valueInputOption="RAW",
            body={"values": all_rows}
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


def import_closed_lost(csv_text: str) -> dict:
    """
    Parse Salesforce closed-lost opp CSV and write to the "Closed Lost" tab.
    Always clears and rewrites (point-in-time snapshot).
    Same CSV format as pipeline opps.

    Returns:
      {imported, total_value, skipped, errors}
    """
    errors = []
    imported = 0
    total_value = 0.0
    skipped = 0

    try:
        records, extra_cols = _parse_opp_csv(csv_text)
    except Exception as e:
        return {"imported": 0, "total_value": 0, "skipped": 0,
                "errors": [f"CSV parse failed: {e}"]}

    if not records:
        return {"imported": 0, "total_value": 0, "skipped": 0,
                "errors": ["No valid rows found in CSV. Check column headers."]}

    # Build full headers: base pipeline columns + closed-lost extras + any remaining CSV extras
    full_headers = list(PIPELINE_COLUMNS)
    for col in CLOSED_LOST_EXTRA_COLUMNS:
        if col not in full_headers:
            full_headers.append(col)
    for col in extra_cols:
        if col not in full_headers:
            full_headers.append(col)

    today_str = date.today().strftime("%m/%d/%Y")
    rows_to_write = []

    for rec in records:
        opp_name = rec.get("opp_name", "").strip()
        if not opp_name:
            skipped += 1
            continue

        amount = rec.get("amount", "")
        total_value += _parse_amount_float(amount)
        row = _build_pipeline_row(full_headers, rec, today_str)
        rows_to_write.append(row)
        imported += 1

    try:
        service = _get_service()
        sheet_id = _get_sheet_id()

        # Ensure tab exists
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if TAB_CLOSED_LOST not in existing:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": TAB_CLOSED_LOST}}}]}
            ).execute()

        # Clear entire tab and rewrite with headers + data
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{TAB_CLOSED_LOST}'!A1:ZZ",
        ).execute()

        all_rows = [full_headers] + rows_to_write
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{TAB_CLOSED_LOST}'!A1",
            valueInputOption="RAW",
            body={"values": all_rows}
        ).execute()

        logger.info(f"Closed Lost import: {imported} opps, ${total_value:,.0f} total value")

    except Exception as e:
        errors.append(f"Sheet write failed: {e}")
        logger.error(f"import_closed_lost sheet write error: {e}")

    return {
        "imported": imported,
        "total_value": total_value,
        "skipped": skipped,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# QUERIES
# ─────────────────────────────────────────────

def _load_closed_lost_opps() -> list[dict]:
    """Load all rows from Closed Lost tab as list of dicts."""
    try:
        service = _get_service()
        sheet_id = _get_sheet_id()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{TAB_CLOSED_LOST}'!A1:ZZ"
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
        logger.error(f"_load_closed_lost_opps error: {e}")
        return []


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


def get_closed_lost_opps(buffer_months: int = 6, lookback_months: int = 18) -> list[dict]:
    """
    Return closed-lost opps from the Closed Lost tab, filtered to a date
    window. Falls back to Pipeline tab if Closed Lost tab is empty.

    Window logic:
      recent_cutoff = today - buffer_months   (exclude too-fresh opps)
      oldest_cutoff = recent_cutoff - lookback_months  (don't go too far back)

    Example (today = 2026-03-15, buffer=6, lookback=18):
      recent_cutoff = 2025-09-15
      oldest_cutoff = 2024-03-15
      → includes opps closed between 2024-03-15 and 2025-09-15

    Set lookback_months=0 to skip the oldest cutoff (include all history).
    """
    from datetime import timedelta
    today = date.today()
    recent_cutoff = today - timedelta(days=buffer_months * 30)
    oldest_cutoff = (recent_cutoff - timedelta(days=lookback_months * 30)) if lookback_months > 0 else None

    # Primary source: dedicated Closed Lost tab
    opps = _load_closed_lost_opps()

    # Fallback: scan Pipeline tab for closed-lost stages
    if not opps:
        all_opps = _load_all_opps()
        _closed_lost_stages = {"closed lost", "closed - lost"}
        opps = [o for o in all_opps if o.get("Stage", "").lower().strip() in _closed_lost_stages]

    closed_lost = []
    for opp in opps:
        close_date = _parse_date(opp.get("Close Date", ""))
        if close_date:
            # Must be before recent_cutoff (not too fresh)
            if close_date > recent_cutoff:
                continue
            # Must be after oldest_cutoff (not too old) — skip check if no oldest_cutoff
            if oldest_cutoff and close_date < oldest_cutoff:
                continue
            opp["_close_date_parsed"] = close_date
            closed_lost.append(opp)
        else:
            # Include opps without a close date (data may be missing)
            closed_lost.append(opp)

    # Sort by most recent close date first
    closed_lost.sort(key=lambda o: o.get("_close_date_parsed", today), reverse=True)
    return closed_lost


def get_stale_opps() -> list[dict]:
    """
    Return open opps that need attention, grouped by tier:
    - 14+ days: "Needs Update"
    - 30+ days: "Needs Check-In / Going Stale"
    - 45+ days: "Risk Going Cold!"
    - Close Date in the past also flagged.
    Adds 'stale_tier', 'stale_reason', and 'days_since_activity' fields.
    """
    today = date.today()
    open_opps = get_open_opps()
    stale = []

    for opp in open_opps:
        reasons = []
        tier = None
        days_since = 0

        # Check last activity staleness (skip if field is empty — no data ≠ stale)
        last_activity = _parse_date(opp.get("Last Activity", ""))
        if last_activity:
            days_since = (today - last_activity).days
            if days_since >= TIER_GOING_COLD:
                tier = "Risk Going Cold!"
                reasons.append(f"No activity in {days_since} days")
            elif days_since >= TIER_GOING_STALE:
                tier = "Needs Check-In / Going Stale"
                reasons.append(f"No activity in {days_since} days")
            elif days_since >= TIER_NEEDS_UPDATE:
                tier = "Needs Update"
                reasons.append(f"No activity in {days_since} days")

        # Check past-due close date
        close_date = _parse_date(opp.get("Close Date", ""))
        if close_date and close_date < today:
            days_past = (today - close_date).days
            reasons.append(f"Close date {days_past} days past due")
            # Escalate tier if close date is past due
            if not tier:
                tier = "Needs Update"

        if reasons and tier:
            opp["stale_tier"] = tier
            opp["stale_reason"] = "; ".join(reasons)
            opp["days_since_activity"] = days_since
            stale.append(opp)

    # Sort by most stale first
    stale.sort(key=lambda o: o.get("days_since_activity", 0), reverse=True)

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

    # Group stale opps by tier
    tier_counts = {}
    for opp in stale:
        t = opp.get("stale_tier", "Unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    return {
        "total_open": len(open_opps),
        "total_value": total_value,
        "by_stage": by_stage,
        "stale_count": len(stale),
        "stale_opps": stale,
        "tier_counts": tier_counts,
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

    # Stale alerts by tier
    tier_counts = summary.get("tier_counts", {})
    if stale_count > 0:
        lines.append("")
        lines.append(f"⚠️ *{stale_count} opps need attention:*")

        # Show tiers in order of severity (worst first)
        tier_order = ["Risk Going Cold!", "Needs Check-In / Going Stale", "Needs Update"]
        for tier_name in tier_order:
            tier_opps = [o for o in stale_opps if o.get("stale_tier") == tier_name]
            if not tier_opps:
                continue

            if tier_name == "Risk Going Cold!":
                emoji = "🔴"
            elif tier_name == "Needs Check-In / Going Stale":
                emoji = "🟡"
            else:
                emoji = "🟠"

            lines.append(f"\n{emoji} *{tier_name}* ({len(tier_opps)}):")
            for opp in tier_opps[:5]:
                name = opp.get("Opportunity Name", "?")
                acct = opp.get("Account Name", "")
                days = opp.get("days_since_activity", 0)
                label = f"{name}"
                if acct and acct.lower() != name.lower():
                    label += f" ({acct})"
                lines.append(f"  • {label} — {days}d")
            if len(tier_opps) > 5:
                lines.append(f"  ... and {len(tier_opps) - 5} more")

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
        lines.append(f"{len(stale)} opportunities need attention:")

        tier_order = ["Risk Going Cold!", "Needs Check-In / Going Stale", "Needs Update"]
        for tier_name in tier_order:
            tier_opps = [o for o in stale if o.get("stale_tier") == tier_name]
            if not tier_opps:
                continue
            lines.append(f"\n{tier_name} ({len(tier_opps)}):")
            for opp in tier_opps[:5]:
                name = opp.get("Opportunity Name", "?")
                stage = opp.get("Stage", "")
                amount = opp.get("Amount", "")
                reason = opp.get("stale_reason", "")
                parts = [name]
                if stage:
                    parts.append(f"Stage: {stage}")
                if amount:
                    parts.append(f"${amount}")
                parts.append(reason)
                lines.append(f"  - {' | '.join(parts)}")
            if len(tier_opps) > 5:
                lines.append(f"  ... and {len(tier_opps) - 5} more")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"build_pipeline_alerts error: {e}")
        return ""
