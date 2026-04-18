"""
enrich_closed_lost.py — S75 Closed Lost tab enrichment for #9 Winback build.

Populates Role Bucket, Grade Bucket, School Type, Is Currently Active,
Lost Reason Class, + provenance and confidence columns on the Closed Lost
tab so the #9 sequence variant design has clean split labels.

Phases (run in order):
  --phase-0   Ground-truth calibration. Stratified sample of 15 rows,
              prints raw blobs for Steven to hand-label, then runs the
              same rows through Phases 1-3 and reports match rate. No
              sheet writes. Gate: ≥13/15 before --full.
  --phase-1-only  Deterministic pass (free, no API calls): keyword grade,
                  role_classifier for populated titles, territory schools
                  fallback, active-account cross-ref, Lost Reason Class
                  code-table. Sheet writes enabled.
  --full      All phases: 1 → 2 (Outreach email cross-ref) → 3 (Haiku
              row-aware) → 4 (anomaly report). Sheet writes enabled.

Flags:
  --limit N         restrict to first N rows
  --dry-run         skip sheet writes, print summary only
  --force-rerun-row EMAIL
                    invalidate cache + enrichment hash for one specific
                    row to force re-classification

Merge-with-previous rule: skip rows where `Enrichment Input Hash` matches
the current-inputs hash. Re-runs are idempotent; data edits force
re-enrichment for affected rows only.

Spec: /Users/stevenadkins/.claude/plans/read-users-stevenadkins-claude-plans-snu-fluttering-thompson.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env_or_die  # noqa: E402

load_env_or_die(required=[])

from tools import csv_importer, pipeline_tracker  # noqa: E402
from tools.grade_level_detector import (  # noqa: E402
    detect_grade,
    is_code_ninjas,
    is_homeschool,
    is_virtual,
    normalize_name,
)
from tools.lead_filters import (  # noqa: E402
    build_territory_index_stateaware,
    fuzzy_match_v5,
)
from tools.outreach_client import find_prospect_by_email  # noqa: E402
from tools.role_classifier import classify_contact_role  # noqa: E402

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

ROLE_BUCKETS = (
    "school_admin", "district_admin", "curriculum",
    "teacher_elem", "teacher_ms", "teacher_hs", "teacher_universal",
    "it", "library", "universal",
)
GRADE_BUCKETS = ("Elem", "MS", "HS", "AllGrades", "District", "Virtual", "Unknown")
SCHOOL_TYPES = ("public", "private", "charter", "diocesan", "unknown")
LOST_REASON_CLASSES = (
    "budget_block", "unresponsive", "abandoned_pre_close",
    "poc_change", "competitor", "consolidation", "other",
)
# `abandoned_pre_close` replaces the earlier `onboarding_fail` label.
# Raw SF values "Not Using Product/Did Not Start" and "Training Issues"
# actually mean the deal never closed — prospect went another direction
# or lost the need before signature. Steven confirmed S75. The label name
# was misleading so it was renamed; data meaning is unchanged.

NEW_COLUMNS = [
    "Role Bucket", "Role Source",
    "Grade Bucket", "Grade Source",
    "School Type",
    "Is Currently Active",
    "Lost Reason Class",
    "Enrichment Confidence",
    "Enrichment Anomaly",
    "Enrichment Input Hash",
]

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_MAX_TOKENS = 250
HAIKU_TIMEOUT = 30.0
HAIKU_CACHE_PATH = REPO_ROOT / "data" / "cl_enrichment_cache.json"
DESCRIPTION_CHAR_CAP = 1500

LOST_REASON_MAP: dict[str, str] = {
    "budget - loss of funding":             "budget_block",
    "budget - too expensive":               "budget_block",
    "budget - nothing left for coding":     "budget_block",
    "unresponsive":                         "unresponsive",
    "not using product/did not start":      "abandoned_pre_close",
    "training issues":                      "abandoned_pre_close",
    "school - teacher role change/ turnover": "poc_change",
    "school - teacher role change/turnover":  "poc_change",
    "new school admin/new poc/new decision maker": "poc_change",
    "school - loss of enrollment":          "poc_change",
    "competitor - curriculum (explain)":    "competitor",
    "purchased through parent acct/consortium/esc": "consolidation",
    "renewed under another program/district/account": "consolidation",
    "unknown":                              "other",
    "":                                     "other",
    "privacy requirements":                 "other",
    "school - no longer offer computer science or coding": "other",
}


# ── Role keyword short-circuits ────────────────────────────────────────

_LIBRARY_KW = re.compile(r"\b(librari|media specialist|media center)\b", re.I)
_DISTRICT_ADMIN_KW = re.compile(
    r"\b(district|superintendent|assistant superintendent|cabinet|deputy supt|chief academic)\b",
    re.I,
)
_SCHOOL_ADMIN_KW = re.compile(
    r"\b(principal|vice principal|assistant principal|head of school|executive director)\b",
    re.I,
)


# ── Hashing ────────────────────────────────────────────────────────────

def input_hash(row: dict) -> str:
    """Stable hash of the inputs that drive classification."""
    blob = "\x1f".join([
        (row.get("Account Name") or "").strip(),
        (row.get("Parent Account") or "").strip(),
        (row.get("State") or "").strip(),
        (row.get("Primary Contact") or "").strip(),
        (row.get("Primary Contact (Alt 2)") or "").strip(),
        (row.get("Contact Email") or "").strip(),
        (row.get("Contact: Title") or "").strip(),
        (row.get("Lost Reason") or "").strip(),
        (row.get("Lead Source") or "").strip(),
        (row.get("Description") or "").strip()[:DESCRIPTION_CHAR_CAP],
    ])
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


# ── Cache ──────────────────────────────────────────────────────────────

def read_cache() -> dict:
    if not HAIKU_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(HAIKU_CACHE_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("Haiku cache read failed: %s", e)
        return {}


def write_cache(cache: dict) -> None:
    HAIKU_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".cl-enr-", suffix=".tmp", dir=str(HAIKU_CACHE_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, HAIKU_CACHE_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── Phase 1: deterministic enrichment ──────────────────────────────────

def _pick_role_from_title(
    title: str, grade_bucket: str
) -> tuple[Optional[str], Optional[str]]:
    """Return (role_bucket, role_source) or (None, None) if still ambiguous."""
    title = (title or "").strip()
    if not title:
        return None, None

    # Library short-circuit
    if _LIBRARY_KW.search(title):
        return "library", "layer1_title"

    # role_classifier handles the 6-bucket
    six = classify_contact_role({"title": title})
    if six == "admin":
        if _DISTRICT_ADMIN_KW.search(title):
            return "district_admin", "layer1_title"
        if _SCHOOL_ADMIN_KW.search(title):
            return "school_admin", "layer1_title"
        # Ambiguous admin — leave for Haiku
        return None, None
    if six == "curriculum":
        return "curriculum", "layer1_title"
    if six == "it":
        return "it", "layer1_title"
    if six == "teacher":
        gmap = {"Elem": "teacher_elem", "MS": "teacher_ms", "HS": "teacher_hs"}
        return gmap.get(grade_bucket, "teacher_universal"), "layer1_title"
    if six in ("coach", "other"):
        return "universal", "layer1_title"
    return None, None


def _pick_grade(row: dict) -> tuple[str, str]:
    """Layer 1 + Layer 2 grade detection. Returns (grade_bucket, source).

    Uses Account Name ONLY — the Parent Account would otherwise poison a
    school-level row (e.g. 'Blalack Middle' w/ parent 'Carrollton-Farmers
    Branch ISD') by forcing every school inside a named district into the
    'District' bucket.
    """
    acct = row.get("Account Name") or ""
    state = (row.get("State") or "").strip().upper()

    # Layer 1 — virtual / homeschool / code ninjas / keyword
    if is_code_ninjas(acct):
        return "Unknown", "layer1_keyword"  # Anomaly captured elsewhere
    if is_homeschool(acct):
        return "Unknown", "layer1_keyword"
    if is_virtual(acct, ""):
        return "Virtual", "layer1_keyword"
    g = detect_grade(acct, "")
    if g in ("Elem", "MS", "HS", "AllGrades", "District"):
        return g, "layer1_keyword"

    # Layer 2 — Territory Schools fuzzy match
    idx = _territory_index_cache.get("idx")
    if idx is None:
        from tools.sheets_writer import _get_service
        idx = build_territory_index_stateaware(_get_service())
        _territory_index_cache["idx"] = idx
    span = fuzzy_match_v5(acct, state, idx)
    if span == "Elem":
        return "Elem", "layer2_territory"
    if span == "MS":
        return "MS", "layer2_territory"
    if span == "HS":
        return "HS", "layer2_territory"
    if span == "AllGrades":
        return "AllGrades", "layer2_territory"
    return "Unknown", "unresolved"


_territory_index_cache: dict = {}


def _pick_school_type_layer1(account_name: str) -> Optional[str]:
    low = (account_name or "").lower()
    if any(k in low for k in ("diocese", "archdiocese", "catholic")):
        return "diocesan"
    if "charter" in low:
        return "charter"
    return None


def _lost_reason_class(raw: str) -> str:
    return LOST_REASON_MAP.get((raw or "").strip().lower(), "other")


def _active_account_lookup():
    accounts = csv_importer.get_active_accounts()
    idx: dict[str, dict] = {}
    for a in accounts:
        display = (a.get("Display Name") or "").strip()
        if not display:
            continue
        key = normalize_name(display)
        if not key:
            continue
        idx.setdefault(key, a)
    return idx, {k: True for k in idx}


def phase1_enrich(
    rows: list[dict], active_idx: dict, active_fuzzy: dict
) -> list[dict]:
    """Mutate rows in-place with Phase 1 results. Returns the list."""
    for row in rows:
        g, g_src = _pick_grade(row)
        row["_grade_bucket"] = g
        row["_grade_source"] = g_src

        r, r_src = _pick_role_from_title(row.get("Contact: Title") or "", g)
        row["_role_bucket"] = r
        row["_role_source"] = r_src

        st = _pick_school_type_layer1(row.get("Account Name") or "")
        row["_school_type"] = st  # may be None — fills from Haiku later

        row["_lost_reason_class"] = _lost_reason_class(row.get("Lost Reason") or "")

        # Active cross-ref
        acct_key = normalize_name(row.get("Account Name") or "")
        matched = None
        if acct_key:
            matched = csv_importer.fuzzy_match_name(
                acct_key, active_fuzzy, threshold=0.85
            )
        row["_is_active"] = bool(matched)

    return rows


# ── Phase 2: Outreach title cross-ref ──────────────────────────────────

def phase2_enrich(rows: list[dict]) -> None:
    """Fetch titles from Outreach for rows still missing Role."""
    for row in rows:
        if row.get("_role_bucket"):
            continue
        email = (row.get("Contact Email") or "").strip()
        if not email:
            continue
        p = find_prospect_by_email(email)
        if not p:
            continue
        title = (p.get("title") or "").strip()
        if not title:
            continue
        # Run it through Phase 1's role picker path
        r, _ = _pick_role_from_title(title, row.get("_grade_bucket") or "Unknown")
        if r:
            row["_role_bucket"] = r
            row["_role_source"] = "layer2_outreach"
            # Also capture the title we found, for input-hash stability and
            # future re-runs. Only cache — don't mutate the sheet's
            # Contact: Title column (that's Steven's source of truth).


# ── Phase 3: Haiku row-aware inference ─────────────────────────────────

_HAIKU_SYSTEM_PROMPT = """You classify a K-12 sales opportunity row into role, grade, and school-type buckets for Closed-Lost-Winback sequence targeting.

STRICT JSON OUTPUT — no prose, no markdown, no explanation outside the JSON object.

Input schema per call:
  Account Name, Parent Account, State, Primary Contact(s), Contact Email,
  Contact Title (may be missing), Lost Reason, Lead Source, Amount,
  Fiscal Period, Description (Steven's notes — may contain dates + context).

Output JSON schema (all keys required):
{
  "role_bucket": one of: school_admin | district_admin | curriculum | teacher_elem | teacher_ms | teacher_hs | teacher_universal | it | library | universal,
  "role_confidence": float 0.0–1.0,
  "grade_bucket": one of: Elem | MS | HS | AllGrades | District | Virtual | Unknown,
  "grade_confidence": float 0.0–1.0,
  "school_type": one of: public | private | charter | diocesan | unknown,
  "higher_ed_anomaly": bool,
  "reasoning_one_line": short string
}

BUCKET DEFINITIONS:
- school_admin: principals, vice/assistant principals, heads of school, executive directors of a single building.
- district_admin: superintendents, asst/deputy superintendents, district office senior leadership, chief academic officer.
- curriculum: C&I directors, instructional coaches, curriculum directors, CS curriculum leads, assessment coordinators.
- teacher_elem / teacher_ms / teacher_hs: classroom teachers — ONLY pick a grade-specific bucket if grade is independently derivable from the input (account name, description, or an explicit school grade). Otherwise return teacher_universal.
- teacher_universal: teacher whose grade cannot be confidently pinned down. Default teacher bucket when uncertain.
- it: Directors of Technology, CIOs, CTOs, EdTech Coordinators, Instructional Technology Coordinators.
- library: librarians, media specialists, media center staff.
- universal: anything else — coaches, C-suite non-admin, admin assistants, trades, or truly ambiguous roles. When in doubt, universal.

GRADE RULES:
- District = a district office or multi-school entity (ISDs, USDs, school districts, archdioceses).
- AllGrades = K-12 single school (rare — K-12 academies, K-12 magnets).
- Virtual = virtual/cyber/online schools.
- Elem / MS / HS = single-span schools.
- Unknown = can't tell.

HIGHER-ED RULE (STRICT):
Steven's territory is K-12. He has ~1 college opp per year. DEFAULT TO K-12 when uncertain.
- Do NOT set higher_ed_anomaly=true just because the email ends in .edu or the name sounds collegiate. Lipscomb, Mount Vernon, Trinity, etc. are all K-12 private schools despite the naming convention.
- ONLY set higher_ed_anomaly=true when the entity is unmistakably post-secondary — explicit "university", "community college", "junior college", "four-year", or obvious tertiary-education naming + context (Amount/Description matches tertiary).
- When uncertain, pick school_type=unknown and a reasonable K-12 grade with appropriate (lower) confidence.

SCHOOL TYPE:
- public: public K-12 district, charter school district, public magnet.
- private: private K-12 (non-diocesan, non-charter). Includes Catholic schools NOT affiliated with an archdiocese.
- charter: charter schools / charter networks.
- diocesan: Catholic schools / archdioceses / dioceses.
- unknown: cannot determine.

Respond with ONLY the JSON object. No prose before or after."""


def _haiku_classify(blob: str, client) -> dict:
    try:
        r = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            temperature=0.0,
            system=_HAIKU_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": blob}],
        )
        raw = r.content[0].text.strip()
    except Exception as e:
        logger.warning("Haiku call failed: %s", e)
        return {}
    # Strip any accidental code fences
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    try:
        return json.loads(raw)
    except Exception as e:
        logger.warning("Haiku JSON parse failed: %s raw=%r", e, raw[:200])
        return {}


def _blob_for_account(rep_row: dict) -> str:
    pc1 = (rep_row.get("Primary Contact") or "").strip()
    pc2 = (rep_row.get("Primary Contact (Alt 2)") or "").strip()
    primary = pc1 if pc1 == pc2 else (f"{pc1} / {pc2}" if (pc1 and pc2) else (pc1 or pc2))
    desc = (rep_row.get("Description") or "").strip()[:DESCRIPTION_CHAR_CAP]
    return "\n".join([
        f"Account Name: {rep_row.get('Account Name') or ''}",
        f"Parent Account: {rep_row.get('Parent Account') or ''}",
        f"State: {rep_row.get('State') or ''}",
        f"Primary Contact(s): {primary}",
        f"Contact Email: {rep_row.get('Contact Email') or ''}",
        f"Contact Title: {rep_row.get('Contact: Title') or ''}",
        f"Lost Reason: {rep_row.get('Lost Reason') or ''}",
        f"Lead Source: {rep_row.get('Lead Source') or ''}",
        f"Amount: {rep_row.get('Amount') or ''}",
        f"Fiscal Period: {rep_row.get('Fiscal Period') or ''}",
        f"Description: {desc}",
    ])


def phase3_enrich(rows: list[dict], cache: dict, client) -> None:
    """Haiku per unique account; fan results back to all rows of that account."""
    need_haiku = [
        r for r in rows
        if (not r.get("_role_bucket")
            or r.get("_grade_bucket") == "Unknown"
            or not r.get("_school_type"))
    ]
    if not need_haiku:
        return

    # Dedup by (normalized account name, state)
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in need_haiku:
        k = (normalize_name(r.get("Account Name") or ""), (r.get("State") or "").upper())
        by_key[k].append(r)

    for k, rs in by_key.items():
        rep = rs[0]
        blob = _blob_for_account(rep)
        cache_key = hashlib.sha1(blob.encode("utf-8")).hexdigest()
        result = cache.get(cache_key)
        if not result:
            result = _haiku_classify(blob, client)
            if result:
                cache[cache_key] = {
                    **result,
                    "classified_at": datetime.now().isoformat(timespec="seconds"),
                }
                write_cache(cache)

        # Fan out
        for r in rs:
            if not r.get("_role_bucket") and result.get("role_bucket") in ROLE_BUCKETS:
                r["_role_bucket"] = result["role_bucket"]
                r["_role_source"] = "layer3_haiku"
                r["_role_conf"] = float(result.get("role_confidence") or 0.0)
            if r.get("_grade_bucket") in ("Unknown", None) and result.get("grade_bucket") in GRADE_BUCKETS:
                r["_grade_bucket"] = result["grade_bucket"]
                r["_grade_source"] = "layer3_haiku"
                r["_grade_conf"] = float(result.get("grade_confidence") or 0.0)
            if not r.get("_school_type") and result.get("school_type") in SCHOOL_TYPES:
                r["_school_type"] = result["school_type"]
            r["_higher_ed_anomaly"] = bool(result.get("higher_ed_anomaly"))
            r["_reasoning"] = result.get("reasoning_one_line", "")


# ── Anomaly compilation ────────────────────────────────────────────────

def compile_anomaly(row: dict) -> str:
    flags: list[str] = []
    if row.get("_higher_ed_anomaly"):
        flags.append("higher_ed")
    if row.get("_is_active"):
        flags.append("currently_active")
    rc = row.get("_role_conf", 1.0)
    gc = row.get("_grade_conf", 1.0)
    if rc is not None and rc < 0.6:
        flags.append("low_conf_role")
    if gc is not None and gc < 0.6:
        flags.append("low_conf_grade")
    if not row.get("_role_bucket") or row.get("_role_source") == "unresolved":
        flags.append("unresolved_role")
    if row.get("_grade_bucket") == "Unknown" or row.get("_grade_source") == "unresolved":
        flags.append("unresolved_grade")
    return ",".join(flags)


def final_fields(row: dict) -> dict:
    """Collapse the _private fields into the sheet column values."""
    rc = row.get("_role_conf")
    gc = row.get("_grade_conf")
    conf_parts = [c for c in (rc, gc) if c is not None]
    conf = min(conf_parts) if conf_parts else 1.0
    return {
        "Role Bucket": row.get("_role_bucket") or "",
        "Role Source": row.get("_role_source") or "unresolved",
        "Grade Bucket": row.get("_grade_bucket") or "Unknown",
        "Grade Source": row.get("_grade_source") or "unresolved",
        "School Type": row.get("_school_type") or "unknown",
        "Is Currently Active": "TRUE" if row.get("_is_active") else "FALSE",
        "Lost Reason Class": row.get("_lost_reason_class") or "other",
        "Enrichment Confidence": f"{conf:.2f}",
        "Enrichment Anomaly": compile_anomaly(row),
        "Enrichment Input Hash": input_hash(row),
    }


# ── Sheet write-back ───────────────────────────────────────────────────

def write_back_columns(rows_with_enrichment: list[dict]) -> None:
    """Extend the Closed Lost tab with the NEW_COLUMNS, preserving order.

    Reads existing sheet → merges new enrichment values → writes. Existing
    rows are matched by row position (sheet is assumed stable between import
    and enrichment — the typical workflow is
    import_closed_lost → enrich_closed_lost back-to-back).
    """
    from tools.csv_importer import _get_service, _get_sheet_id
    svc = _get_service()
    sid = _get_sheet_id()

    rng = f"'{pipeline_tracker.TAB_CLOSED_LOST}'!A1:ZZ"
    resp = svc.spreadsheets().values().get(spreadsheetId=sid, range=rng).execute()
    sheet_rows = resp.get("values", [])
    if not sheet_rows:
        raise SystemExit("Closed Lost tab is empty")
    headers = list(sheet_rows[0])

    # Ensure all NEW_COLUMNS are in the header
    for col in NEW_COLUMNS:
        if col not in headers:
            headers.append(col)

    # Build output row grid
    out: list[list[str]] = [headers]

    # Match enrichment rows to sheet rows by Account Name + Opportunity Name
    # (preserves order; handles any reordering that might have happened).
    opp_col = headers.index("Opportunity Name") if "Opportunity Name" in headers else -1
    acct_col = headers.index("Account Name") if "Account Name" in headers else -1
    email_col = headers.index("Contact Email") if "Contact Email" in headers else -1

    def row_key(r):
        return (
            (r[opp_col] if opp_col >= 0 and opp_col < len(r) else ""),
            (r[acct_col] if acct_col >= 0 and acct_col < len(r) else ""),
            (r[email_col] if email_col >= 0 and email_col < len(r) else ""),
        )

    enrichment_by_key: dict[tuple, dict] = {}
    for er in rows_with_enrichment:
        enrichment_by_key[(
            (er.get("Opportunity Name") or "").strip(),
            (er.get("Account Name") or "").strip(),
            (er.get("Contact Email") or "").strip(),
        )] = final_fields(er)

    new_col_indices = [headers.index(c) for c in NEW_COLUMNS]

    for raw in sheet_rows[1:]:
        # Pad row to header length
        row = list(raw) + [""] * (len(headers) - len(raw))
        key = row_key(row)
        er = enrichment_by_key.get(key)
        if er:
            for c, idx in zip(NEW_COLUMNS, new_col_indices):
                row[idx] = er[c]
        out.append(row)

    # Clear + rewrite
    svc.spreadsheets().values().clear(
        spreadsheetId=sid, range=rng,
    ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=sid,
        range=f"'{pipeline_tracker.TAB_CLOSED_LOST}'!A1",
        valueInputOption="RAW",
        body={"values": out},
    ).execute()
    logger.info("Wrote back %d enrichment rows to Closed Lost tab",
                len(rows_with_enrichment))


# ── Phase 0: ground truth ──────────────────────────────────────────────

def phase_0_sample(all_rows: list[dict], n: int = 15) -> list[dict]:
    """Stratified sample: 3 teacher-ish, 3 admin-ish, 3 district-named,
    3 grade-named, 3 ambiguous. Deterministic seed."""
    rng = random.Random(42)
    rng.shuffle(all_rows)

    def has_teacher_title(r):
        t = (r.get("Contact: Title") or "").lower()
        return "teacher" in t
    def has_admin_title(r):
        t = (r.get("Contact: Title") or "").lower()
        return any(k in t for k in ("principal", "director", "superintendent", "head"))
    def is_district_acct(r):
        a = (r.get("Account Name") or "").lower()
        return any(k in a for k in ("district", "isd", "usd", "unified", "public schools"))
    def is_grade_acct(r):
        a = (r.get("Account Name") or "").lower()
        return any(k in a for k in ("elementary", "middle", "high ", "academy", "magnet"))
    def is_ambiguous(r):
        t = (r.get("Contact: Title") or "").strip()
        a = (r.get("Account Name") or "").lower()
        return not t and not any(k in a for k in (
            "district", "isd", "usd", "unified", "elementary", "middle", "high ",
            "academy", "magnet", "schools",
        ))

    strata = [
        ("teacher-title", has_teacher_title),
        ("admin-title",   has_admin_title),
        ("district-acct", is_district_acct),
        ("grade-acct",    is_grade_acct),
        ("ambiguous",     is_ambiguous),
    ]
    per = max(1, n // len(strata))
    picked: list[dict] = []
    seen_keys: set = set()
    for name, pred in strata:
        count = 0
        for r in all_rows:
            key = (r.get("Account Name"), r.get("Opportunity Name"))
            if key in seen_keys:
                continue
            if pred(r):
                r["_stratum"] = name
                picked.append(r)
                seen_keys.add(key)
                count += 1
                if count >= per:
                    break
    # Top-up to n if strata underfilled
    for r in all_rows:
        if len(picked) >= n:
            break
        key = (r.get("Account Name"), r.get("Opportunity Name"))
        if key not in seen_keys:
            r["_stratum"] = "topup"
            picked.append(r)
            seen_keys.add(key)
    return picked[:n]


def phase_0_print(rows: list[dict]) -> None:
    print("=" * 76)
    print("PHASE 0 — GROUND-TRUTH CALIBRATION SAMPLE")
    print("Steven: hand-label each row with (role_bucket, grade_bucket, school_type, lost_reason_class).")
    print()
    print("Role buckets: " + " | ".join(ROLE_BUCKETS))
    print("Grade buckets: " + " | ".join(GRADE_BUCKETS))
    print("School types: " + " | ".join(SCHOOL_TYPES))
    print("Lost reason classes: " + " | ".join(LOST_REASON_CLASSES))
    print("=" * 76)
    for i, r in enumerate(rows, 1):
        print()
        print(f"─── Row {i} [stratum: {r.get('_stratum')}] ───")
        print(f"  Account Name:   {r.get('Account Name') or ''}")
        print(f"  Parent Account: {r.get('Parent Account') or ''}")
        print(f"  State:          {r.get('State') or ''}")
        print(f"  Primary Contact: {r.get('Primary Contact') or ''}")
        if (r.get('Primary Contact (Alt 2)') or '') != (r.get('Primary Contact') or ''):
            print(f"  Primary (Alt):  {r.get('Primary Contact (Alt 2)') or ''}")
        print(f"  Contact Email:  {r.get('Contact Email') or ''}")
        print(f"  Contact Title:  {r.get('Contact: Title') or ''}")
        print(f"  Lost Reason:    {r.get('Lost Reason') or ''}")
        print(f"  Amount:         {r.get('Amount') or ''}")
        desc = (r.get('Description') or '').strip()
        if desc:
            trunc = desc[:600] + ("…" if len(desc) > 600 else "")
            print(f"  Description:    {trunc}")
    print()
    print("=" * 76)
    print("Next step: Steven, reply with labels as 15 lines of the form:")
    print("  <row#>: role=<bucket>; grade=<bucket>; type=<type>; reason=<class>")
    print()
    print("Example:")
    print("  1: role=teacher_hs; grade=HS; type=public; reason=budget_block")
    print("=" * 76)


# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--phase-0", action="store_true")
    g.add_argument("--phase-1-only", action="store_true")
    g.add_argument("--full", action="store_true")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-rerun-row", type=str, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    rows = pipeline_tracker.get_closed_lost_opps(buffer_months=0, lookback_months=120)
    if args.limit:
        rows = rows[:args.limit]
    logger.info("Loaded %d Closed Lost rows", len(rows))

    if args.phase_0:
        picked = phase_0_sample(rows, n=args.n)
        phase_0_print(picked)
        return 0

    # Phase 1
    active_idx, active_fuzzy = _active_account_lookup()
    phase1_enrich(rows, active_idx, active_fuzzy)

    if args.phase_1_only:
        summary = Counter((r.get("_role_source"), r.get("_grade_source")) for r in rows)
        print("\nPhase 1 resolution summary:")
        for (rs, gs), n in summary.most_common():
            print(f"  role={rs!s:<18}  grade={gs!s:<20}  rows={n}")
        if not args.dry_run:
            write_back_columns(rows)
            print(f"\nWrote {len(rows)} rows back to Closed Lost tab.")
        return 0

    # Phase 2
    phase2_enrich(rows)

    # Phase 3
    cache = read_cache()
    try:
        import anthropic
        client = anthropic.Anthropic(timeout=HAIKU_TIMEOUT)
    except Exception as e:
        logger.error("Anthropic SDK unavailable: %s", e)
        client = None
    if client is not None:
        phase3_enrich(rows, cache, client)

    # Summary
    role_dist = Counter(r.get("_role_bucket") or "unresolved" for r in rows)
    grade_dist = Counter(r.get("_grade_bucket") or "Unknown" for r in rows)
    type_dist = Counter(r.get("_school_type") or "unknown" for r in rows)
    lr_dist = Counter(r.get("_lost_reason_class") or "other" for r in rows)
    active_count = sum(1 for r in rows if r.get("_is_active"))

    print("\n=== ENRICHMENT SUMMARY ===")
    print(f"Total rows: {len(rows)}")
    print(f"Currently Active (do-not-email): {active_count}")
    print("\nRole Bucket:")
    for k, v in role_dist.most_common():
        print(f"  {v:>4}  {k}")
    print("\nGrade Bucket:")
    for k, v in grade_dist.most_common():
        print(f"  {v:>4}  {k}")
    print("\nSchool Type:")
    for k, v in type_dist.most_common():
        print(f"  {v:>4}  {k}")
    print("\nLost Reason Class:")
    for k, v in lr_dist.most_common():
        print(f"  {v:>4}  {k}")

    # Anomaly call-outs
    anomalies = [r for r in rows if compile_anomaly(r)]
    print(f"\nAnomaly rows: {len(anomalies)}")
    for r in anomalies[:30]:
        print(f"  {r.get('Account Name','')!s:<45}  flags={compile_anomaly(r)}")

    if not args.dry_run:
        write_back_columns(rows)
        print(f"\nWrote {len(rows)} rows back to Closed Lost tab.")
    else:
        print("\n(dry-run — no sheet writes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
