"""
lead_filters.py — SF-Leads → DRE-cohort classification.

Promotes the S72 one-shot classifiers (`/tmp/sf_leads_dre_segmentation.py`
+ `/tmp/sf_leads_dre_pass5.py`) into a library the S74 campaign autopilot
consumes when building the DRE prospect pool.

Two layers:

1. **Pure classification logic** (`classify_rows`) — given a list of SF-Leads
   row dicts and a pre-built `TerritoryIndex`, routes every row to one of
   the 13 DRE cohorts (or tags it excluded/parked). Fully testable with
   fixture data; no I/O.

2. **Sheets-backed driver** (`classify_sf_leads_to_dre_buckets`) — reads
   the `SF Leads` tab + the `Territory Schools` tab, builds the territory
   index, calls `classify_rows`. Single I/O entry point; wrapped by
   `tools.campaign_pool`.

Routing order (first match wins) from
`memory/project_dre_family_framework.md`:

  0. Universal exclusions (Code Ninjas corp deal, individual homeschool).
  1. Librarian title → LIB (beats substrategy).
  2. TC substrategy (Lead Source ∈ TC_SOURCES): empty-title → TC-Universal
     family via pass5 grade rules; teacher → TC-Teacher; IT → IT-ReEngage;
     other populated title → TC-Universal-Residual (catchall).
  3. LQD substrategy → LQD-Universal.
  4. INT substrategy (22-source whitelist): empty-title → INT-Universal;
     teacher → INT-Teacher; IT → IT-ReEngage; other populated title →
     parked (no INT catchall per S72 data-driven collapse).
  5. No substrategy match → parked (future cold-outreach session).
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Literal, NamedTuple, Optional

from tools.grade_level_detector import (
    detect_grade,
    homeschool_subsplit,
    is_code_ninjas,
    is_homeschool,
    is_virtual,
    map_grade_span,
    normalize_name,
)

logger = logging.getLogger(__name__)

# ── Authoritative DRE cohort names (must match Outreach sequence display names) ──

CohortName = Literal[
    "INT-Universal",
    "TC-Universal-Residual",
    "TC-MS",
    "TC-HS",
    "TC-Elem",
    "TC-Virtual",
    "TC-District",
    "TC-All-Grades",
    "LIB",
    "LQD-Universal",
    "INT-Teacher",
    "TC-Teacher",
    "IT-ReEngage",
]

ALL_DRE_COHORTS: tuple[CohortName, ...] = (
    "INT-Universal", "TC-Universal-Residual", "TC-MS", "TC-HS", "TC-Elem",
    "TC-Virtual", "TC-District", "TC-All-Grades", "LIB", "LQD-Universal",
    "INT-Teacher", "TC-Teacher", "IT-ReEngage",
)

# ── Lead Source whitelists (case-insensitive exact match) ──────────────

TC_SOURCES: frozenset[str] = frozenset({
    "teacher created account",
    "converted teacher account",
})

LQD_SOURCES: frozenset[str] = frozenset({
    "license request",
    "request a quote/demo",
    "request a quote/ demo",
})

# The 22-source INT whitelist from memory/project_uni_lead_source_whitelist.md
INT_SOURCES: frozenset[str] = frozenset({
    "webinar 11/17/20", "tcea 2020", "iste 2019", "intercom",
    "hour of code 2019", "hoc demo day 2022", "fetc 2020", "drift",
    "demo day/webinar", "cue spring 2019", "cue 2023", "cue 2019 spring",
    "cue 2019 fall", "csta 2020", "csta 2022", "csta 2019", "csedcon 2019",
    "covid-19 email", "conference", "apcsp landing", "ai league demo day",
    "acte 2022",
})

# ── Role detection (lifted from segmentation.py) ───────────────────────

_LIB_KWS = ("librarian", "library", "media specialist", "media center")
_TEACHER_KWS = ("teacher", "instructor", "faculty")
_IT_KWS = (
    "edtech", "cto", "cio", "chief information", "chief technology",
    "information systems", "it director", "tech integration",
    "it coordinator", "director of tech", "technology",
)

Role = Literal["empty", "library", "teacher", "it", "other"]


def detect_role(title: str | None) -> Role:
    """Classify a job title into role buckets used by DRE routing."""
    t = (title or "").strip().lower()
    if not t:
        return "empty"
    if any(k in t for k in _LIB_KWS):
        return "library"
    if any(k in t for k in _TEACHER_KWS):
        return "teacher"
    if any(k in t for k in _IT_KWS):
        return "it"
    # admin-school, admin-district, curriculum, and genuinely-other titles
    # all collapse to "other" under S72 data-driven merge.
    return "other"


# ── Territory Schools index (lifted from pass5 — state-aware) ──────────

class TerritoryIndex(NamedTuple):
    """7-way index over the Territory Schools tab.

    Keys:
      exact_by_state  : {(STATE, lowername): [span, ...]}
      norm_by_state   : {(STATE, normkey): [span, ...]}
      exact_all       : {lowername: [(span, state), ...]}
      norm_all        : {normkey: [(span, state), ...]}
      district_by_state : {(STATE, lowdistrict): [span, ...]}
      district_all    : {lowdistrict: [(span, state), ...]}
      norm_keys_by_state : {STATE: set[normkey]}
    """
    exact_by_state: dict
    norm_by_state: dict
    exact_all: dict
    norm_all: dict
    district_by_state: dict
    district_all: dict
    norm_keys_by_state: dict


TERRITORY_SHEET_ID = "1CWYpnw4vmK9anrGKjs_357azU47v8auiSCTNFHIDd9c"
TERRITORY_TAB = "Territory Schools"

SF_LEADS_SHEET_ID = "15pSmpfdSlgoaBFxbwquUjtO9xYSnK-4yA69mkw_lWLk"
SF_LEADS_TAB = "SF Leads"


def build_territory_index_stateaware(svc) -> TerritoryIndex:
    """Read Territory Schools columns A/B/C/L and build the 7-way state-aware index.

    Columns: A=State, B=School Name, C=District Name, L=Grade Span.
    """
    ranges = [
        f"'{TERRITORY_TAB}'!A2:A",
        f"'{TERRITORY_TAB}'!B2:B",
        f"'{TERRITORY_TAB}'!C2:C",
        f"'{TERRITORY_TAB}'!L2:L",
    ]
    resp = svc.spreadsheets().values().batchGet(
        spreadsheetId=TERRITORY_SHEET_ID,
        ranges=ranges,
        majorDimension="COLUMNS",
    ).execute()
    cols = [
        vr.get("values", [[]])[0] if vr.get("values") else []
        for vr in resp["valueRanges"]
    ]
    states, names, districts, spans = cols
    n = max(len(states), len(names), len(districts), len(spans))

    def pad(xs: list[str]) -> list[str]:
        return xs + [""] * (n - len(xs))

    states, names, districts, spans = pad(states), pad(names), pad(districts), pad(spans)

    exact_by_state: dict = defaultdict(list)
    norm_by_state: dict = defaultdict(list)
    exact_all: dict = defaultdict(list)
    norm_all: dict = defaultdict(list)
    district_by_state: dict = defaultdict(list)
    district_all: dict = defaultdict(list)
    norm_keys_by_state: dict = defaultdict(set)

    for name, span, state, district in zip(names, spans, states, districts):
        span_s = (span or "").strip()
        state_s = (state or "").strip().upper()
        if name:
            low = name.strip().lower()
            exact_all[low].append((span_s, state_s))
            if state_s:
                exact_by_state[(state_s, low)].append(span_s)
            nk = normalize_name(name)
            if nk:
                norm_all[nk].append((span_s, state_s))
                if state_s:
                    norm_by_state[(state_s, nk)].append(span_s)
                    norm_keys_by_state[state_s].add(nk)
        if district:
            dlow = district.strip().lower()
            district_all[dlow].append((span_s, state_s))
            if state_s:
                district_by_state[(state_s, dlow)].append(span_s)

    return TerritoryIndex(
        exact_by_state=exact_by_state,
        norm_by_state=norm_by_state,
        exact_all=exact_all,
        norm_all=norm_all,
        district_by_state=district_by_state,
        district_all=district_all,
        norm_keys_by_state=norm_keys_by_state,
    )


def _resolve_spans_to_bucket(spans: Iterable[str]) -> Optional[str]:
    """Return unanimous span bucket, else None. Filters out unmapped spans."""
    buckets = {map_grade_span(sp) for sp in spans}
    buckets.discard(None)
    if len(buckets) == 1:
        return buckets.pop()
    return None


def fuzzy_match_v5(
    company: str | None,
    lead_state: str | None,
    idx: TerritoryIndex,
) -> Optional[str]:
    """State-primary fuzzy match. Returns 'Elem'|'MS'|'HS'|'AllGrades' or None.

    Mirrors `/tmp/sf_leads_dre_pass5.py::fuzzy_match_v5` including the
    state-first path, district fallback, substring scan, and global-fallback
    unanimous-bucket rescue.
    """
    if not company:
        return None
    low = company.strip().lower()
    ls = (lead_state or "").strip().upper()

    # State-primary path (preferred)
    if ls:
        key = (ls, low)
        if key in idx.exact_by_state:
            b = _resolve_spans_to_bucket(idx.exact_by_state[key])
            if b:
                return b

        if key in idx.district_by_state:
            b = _resolve_spans_to_bucket(idx.district_by_state[key])
            if b:
                return b

        nk = normalize_name(company)
        if nk:
            nkey = (ls, nk)
            if nkey in idx.norm_by_state:
                b = _resolve_spans_to_bucket(idx.norm_by_state[nkey])
                if b:
                    return b

            tokens = [t for t in nk.split() if len(t) >= 3]
            if len(tokens) >= 3:
                state_keys = idx.norm_keys_by_state.get(ls, set())
                hits: list[str] = []
                checked = 0
                for key2 in state_keys:
                    checked += 1
                    if checked > 1500:
                        break
                    if nk in key2 or key2 in nk:
                        hits.extend(idx.norm_by_state[(ls, key2)])
                        if len(hits) > 50:
                            break
                if hits:
                    b = _resolve_spans_to_bucket(hits)
                    if b:
                        return b

    # Global fallback — only if unanimous across all candidates
    if low in idx.exact_all:
        spans = [sp for sp, _ in idx.exact_all[low]]
        b = _resolve_spans_to_bucket(spans)
        if b:
            return b

    if low in idx.district_all:
        spans = [sp for sp, _ in idx.district_all[low]]
        b = _resolve_spans_to_bucket(spans)
        if b:
            return b

    nk = normalize_name(company)
    if nk and nk in idx.norm_all:
        spans = [sp for sp, _ in idx.norm_all[nk]]
        b = _resolve_spans_to_bucket(spans)
        if b:
            return b

    return None


# ── Row-level classification ───────────────────────────────────────────

def _classify_tc_empty_title(
    company: str | None,
    verified_school: str | None,
    state: str | None,
    idx: TerritoryIndex,
) -> CohortName:
    """TC substrategy + empty title: apply pass5 grade rules with fuzzy fallback."""
    if is_virtual(company, verified_school):
        return "TC-Virtual"
    g = detect_grade(company, verified_school)
    if g == "District":
        return "TC-District"
    if g == "All-Grades":
        return "TC-All-Grades"
    if g == "MS":
        return "TC-MS"
    if g == "HS":
        return "TC-HS"
    if g == "Elem":
        return "TC-Elem"
    # Unknown → Territory-Schools fuzzy match
    span_bucket = fuzzy_match_v5(company, state, idx)
    if span_bucket == "Elem":
        return "TC-Elem"
    if span_bucket == "MS":
        return "TC-MS"
    if span_bucket == "HS":
        return "TC-HS"
    if span_bucket == "AllGrades":
        return "TC-All-Grades"
    return "TC-Universal-Residual"


def classify_row(
    row: dict,
    idx: TerritoryIndex,
) -> tuple[Optional[CohortName], str]:
    """Route one SF-Leads row to a cohort (or tag it excluded/parked).

    Expects keys: ``state``, ``title``, ``company``, ``lead_source``,
    ``verified_school``. Missing keys treated as empty.

    Returns ``(cohort_name, "match")`` on success, or ``(None, reason)``
    where reason is one of:
      excluded_code_ninjas
      excluded_homeschool_network
      excluded_homeschool_individual
      parked_no_source_match
      parked_int_other_role
    """
    company = row.get("company") or ""
    title = row.get("title") or ""
    source = row.get("lead_source") or ""
    verified = row.get("verified_school") or ""
    state = row.get("state") or ""

    # 0. Universal exclusions
    if is_code_ninjas(company):
        return None, "excluded_code_ninjas"
    if is_homeschool(company):
        sub = homeschool_subsplit(company)
        if sub == "TC-Homeschool-Network":
            # Networks/co-ops are legitimate customers but not DRE targets —
            # they're a distinct future cohort. Park for now.
            return None, "excluded_homeschool_network"
        return None, "excluded_homeschool_individual"

    # 1. Librarian title beats substrategy
    role = detect_role(title)
    if role == "library":
        return "LIB", "match"

    # 2. Substrategy by Lead Source
    src_low = source.strip().lower()

    if src_low in TC_SOURCES:
        if role == "empty":
            return _classify_tc_empty_title(company, verified, state, idx), "match"
        if role == "teacher":
            return "TC-Teacher", "match"
        if role == "it":
            return "IT-ReEngage", "match"
        # admin / curriculum / other — fold to TC-Universal-Residual catchall
        return "TC-Universal-Residual", "match"

    if src_low in LQD_SOURCES:
        # S72 data-driven collapse: all LQD roles/grades → single cohort
        return "LQD-Universal", "match"

    if src_low in INT_SOURCES:
        if role == "empty":
            return "INT-Universal", "match"
        if role == "teacher":
            return "INT-Teacher", "match"
        if role == "it":
            return "IT-ReEngage", "match"
        # No INT catchall — admin/curriculum/other parked
        return None, "parked_int_other_role"

    # 3. No substrategy match
    return None, "parked_no_source_match"


# ── Result dataclass + bulk driver ─────────────────────────────────────

@dataclass
class DrePoolResult:
    """Outcome of a full SF-Leads → DRE-cohort classification pass."""
    buckets: dict[str, list[dict]] = field(default_factory=dict)
    excluded: Counter = field(default_factory=Counter)
    total_rows_scanned: int = 0
    total_matched: int = 0

    def cohort_sizes(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.buckets.items()}


def classify_rows(
    rows: Iterable[dict],
    idx: TerritoryIndex,
) -> DrePoolResult:
    """Pure classification: rows + territory index → DrePoolResult."""
    result = DrePoolResult()
    # Pre-init all 13 bucket keys so empty buckets appear in the output
    for c in ALL_DRE_COHORTS:
        result.buckets[c] = []

    for row in rows:
        result.total_rows_scanned += 1
        cohort, reason = classify_row(row, idx)
        if cohort is None:
            result.excluded[reason] += 1
            continue
        result.buckets[cohort].append(row)
        result.total_matched += 1

    return result


# ── Sheet I/O driver ───────────────────────────────────────────────────

def _col_letter(idx: int) -> str:
    """0-based column index → spreadsheet letter (A, B, ..., Z, AA, ...)."""
    s = ""
    n = idx
    while True:
        s = chr(ord("A") + (n % 26)) + s
        n = n // 26 - 1
        if n < 0:
            break
    return s


def _fetch_col(svc, sheet_id: str, rng: str) -> list[str]:
    resp = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng, majorDimension="COLUMNS",
    ).execute()
    vals = resp.get("values", [])
    return vals[0] if vals else []


def read_sf_leads_rows(svc) -> list[dict]:
    """Read the 5 columns we need from SF Leads into row dicts.

    Columns discovered by header name (not hard-coded index) so sheet
    column reorders don't silently break the classifier.
    """
    header_resp = svc.spreadsheets().values().get(
        spreadsheetId=SF_LEADS_SHEET_ID, range=f"'{SF_LEADS_TAB}'!1:1",
    ).execute()
    header = header_resp.get("values", [[]])[0]

    wanted = {
        "state/province": None,
        "title": None,
        "company": None,
        "lead source": None,
        "verified school": None,
        "email": None,
        "first name": None,
        "last name": None,
    }
    for i, h in enumerate(header):
        key = (h or "").strip().lower()
        if key in wanted and wanted[key] is None:
            wanted[key] = (i, _col_letter(i), h)

    required = ("state/province", "title", "company", "lead source", "email")
    missing = [k for k in required if wanted[k] is None]
    if missing:
        raise RuntimeError(f"SF Leads header missing required columns: {missing}")

    def col(k: str) -> Optional[str]:
        v = wanted.get(k)
        return v[1] if v else None

    s_col = col("state/province")
    t_col = col("title")
    c_col = col("company")
    ls_col = col("lead source")
    vs_col = col("verified school")
    e_col = col("email")
    fn_col = col("first name")
    ln_col = col("last name")

    states = _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{s_col}2:{s_col}")
    titles = _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{t_col}2:{t_col}")
    companies = _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{c_col}2:{c_col}")
    sources = _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{ls_col}2:{ls_col}")
    verifieds = (
        _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{vs_col}2:{vs_col}")
        if vs_col else []
    )
    emails = _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{e_col}2:{e_col}")
    firsts = (
        _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{fn_col}2:{fn_col}")
        if fn_col else []
    )
    lasts = (
        _fetch_col(svc, SF_LEADS_SHEET_ID, f"'{SF_LEADS_TAB}'!{ln_col}2:{ln_col}")
        if ln_col else []
    )

    n = max(len(states), len(titles), len(companies), len(sources),
            len(emails))

    def pad(xs: list[str]) -> list[str]:
        return xs + [""] * (n - len(xs))

    states = pad(states); titles = pad(titles); companies = pad(companies)
    sources = pad(sources); emails = pad(emails)
    verifieds = pad(verifieds) if vs_col else [""] * n
    firsts = pad(firsts) if fn_col else [""] * n
    lasts = pad(lasts) if ln_col else [""] * n

    rows: list[dict] = []
    for st, ti, co, sr, ve, em, fn, ln in zip(
        states, titles, companies, sources, verifieds, emails, firsts, lasts
    ):
        rows.append({
            "state": st,
            "title": ti,
            "company": co,
            "lead_source": sr,
            "verified_school": ve,
            "email": em,
            "first_name": fn,
            "last_name": ln,
        })
    return rows


def classify_sf_leads_to_dre_buckets(svc=None) -> DrePoolResult:
    """Read SF Leads + Territory Schools, classify every row to a DRE cohort.

    If ``svc`` is None, lazily constructs one via ``sheets_writer._get_service``.
    """
    if svc is None:
        from tools.sheets_writer import _get_service
        svc = _get_service()

    logger.info("Reading SF Leads + Territory Schools for DRE classification")
    rows = read_sf_leads_rows(svc)
    idx = build_territory_index_stateaware(svc)
    logger.info("SF Leads rows: %d; territory exact keys: %d",
                len(rows), len(idx.exact_all))
    return classify_rows(rows, idx)
