"""
grade_level_detector.py — pure classifier primitives for school-row bucketing.

Lifted from the S72 `/tmp/sf_leads_dre_pass3.py` + `pass4.py` one-shot
classifier scripts into a library so multi-strategy campaign automation
(S74 autopilot, future strategy pool builders) can reuse them without
re-deriving the rules.

Every function here is a pure string → label mapping. Zero I/O, zero
dependencies beyond stdlib. All inputs are raw CRM/sheet strings (may be
None / empty / mixed case). Outputs are a fixed vocabulary of bucket
names or sentinel "Unknown" / None.

Classifier precedence (mirroring pass4's `classify_row_v4`):
  1. is_code_ninjas    → "EXCLUDED-Code-Ninjas"  (never routed)
  2. is_homeschool     → homeschool_subsplit(...)
  3. is_virtual        → "TC-Virtual"
  4. detect_grade      → "TC-<Elem|MS|HS|District|All-Grades>" or "Unknown"

Consumers (e.g. tools.lead_filters) wrap these with the Territory-Schools
fuzzy-match fallback used to classify the remaining "Unknown" bucket.
"""
from __future__ import annotations

import re
import string
from typing import Literal

GradeBucket = Literal["Elem", "MS", "HS", "All-Grades", "District", "Unknown"]
SpanBucket = Literal["Elem", "MS", "HS", "AllGrades"]
HomeschoolBucket = Literal["TC-Homeschool-Network", "TC-Homeschool-Excluded"]


# ── Homeschool detection ────────────────────────────────────────────────

_HOMESCHOOL_TRIGGERS = (
    "homeschool", "home school", "home-school", "home schooled",
    "home schooling", "homeschooler", "homeschoolers",
)
_HOMESCHOOL_STANDALONE = frozenset({"home"})

_NETWORK_INDICATORS = (
    "co-op", "coop", "cooperative",
    "network", "alliance", "association", "group", "consortium", "community",
    "academy", "center", "centre",
    "classical conversations", "hslda", "thsc", "texas home school coalition",
    "university model", "umbrella school",
)


def is_homeschool(company: str | None) -> bool:
    c = (company or "").strip()
    if not c:
        return False
    low = c.lower()
    if low in _HOMESCHOOL_STANDALONE:
        return True
    return any(kw in low for kw in _HOMESCHOOL_TRIGGERS)


def homeschool_subsplit(company: str | None) -> HomeschoolBucket:
    """Route homeschool rows into network vs excluded. Only call when is_homeschool(company)."""
    low = (company or "").lower()
    for ind in _NETWORK_INDICATORS:
        if ind in low:
            return "TC-Homeschool-Network"
    return "TC-Homeschool-Excluded"


# ── Virtual / online school detection ───────────────────────────────────

_VIRTUAL_TRIGGERS = (
    "virtual academy", "virtual school", "virtual charter", "virtual learning",
    "cyber school", "cyber charter", "cyber cs", "cyber academy", "cyber learning",
    "online academy", "online school", "online charter", "online learning",
    "e-learning", "elearning", "distance learning",
    "ecot", "electronic classroom of tomorrow",
    "connections academy", "commonwealth connections",
    "agora cyber", "ohio virtual", "michigan virtual", "texas virtual",
    "california virtual", "pennsylvania cyber", "pa cyber",
    "epic charter", "epic one on one", "insight school",
    "k12 inc", "stride",
)
_VIRTUAL_FALLBACK_RE = re.compile(
    r"\bvirtual\b.*?\b(academy|school|charter|learning)\b", re.IGNORECASE
)


def is_virtual(company: str | None, verified_school: str | None = "") -> bool:
    blob = f"{company or ''} {verified_school or ''}".lower()
    if any(kw in blob for kw in _VIRTUAL_TRIGGERS):
        return True
    return bool(_VIRTUAL_FALLBACK_RE.search(blob))


# ── Code Ninjas exclusion ───────────────────────────────────────────────

def is_code_ninjas(company: str | None) -> bool:
    return "code ninjas" in (company or "").lower()


# ── Grade-level detection from company + verified-school text ───────────

_DISTRICT_KWS = (
    "school district", "school dist", "sch dist",
    " isd", "-isd", "isd ",
    " cusd", "-cusd",
    " usd ", "-usd", "usd ", " usd#",
    " rsd", " rcsd",
    "public schools", "community schools", "city schools", "county schools",
    "unified school", "consolidated school",
    "board of education", " boe", "department of education", " doe ",
    " districts", "cooperative", "regional school", "regional educational",
    " iu ", "boces", " csu ",
    "archdiocese", "diocese of", "catholic schools",
    "charter network", "charter schools",
)
_UNIFIED_RE = re.compile(r"\bunified\b", re.IGNORECASE)

_ALLGRADES_KWS = ("k-12", "k12 ", " k12", "pk-12", "pre-k-12")

_MS_KWS = (
    "middle school", "middle academy", "middle-school", "middle/high", "middle and high",
    "junior high", "jr. high", "jr high", " jhs", "jhs ",
    "intermediate school", "intermediate academy",
    " 6-8", " 7-8", " 6-9", "6-8 ", "7-8 ",
)
_MS_TRAIL_RE = re.compile(r"(?:\s|^)(ms|m\.s\.)\s*$", re.IGNORECASE)
_MS_MIDDLE_RE = re.compile(r"\bms\b", re.IGNORECASE)

_HS_KWS = (
    "high school", "high-school", "highschool",
    "senior high", "senior academy",
    " 9-12", "9-12 ", "10-12", " 7-12", "7-12 ",
    " hs ", " hs,", " hs.", "hs-",
    "upper school",
    "prep school", "preparatory school", "preparatory academy",
    "career academy", "vocational", "cte center", "technical high",
    "early college",
)

_ELEM_KWS = (
    "elementary", " elem ", " elem.", "elem school", "elem. school", "elem academy",
    "primary school", "primary academy", "primary center",
    " k-5", " k5 ", " k-6", " k6 ", "k-8",
    "lower school",
    "early childhood", "pre-k", "prek ", "preschool", "kindergarten",
)


def detect_grade(
    company: str | None,
    verified_school: str | None = "",
) -> GradeBucket:
    """Return the grade bucket implied by company + verified_school text.

    Exactly reproduces pass3's `detect_grade` logic (including the two
    "tweak" paths for bare `unified` and trailing `ms`/`m.s.`).
    """
    blob_parts: list[str] = []
    if verified_school and verified_school.strip():
        blob_parts.append(verified_school)
    if company and company.strip():
        blob_parts.append(company)
    blob = " " + " ".join(blob_parts).lower() + " "

    for kw in _DISTRICT_KWS:
        if kw in blob:
            return "District"
    if _UNIFIED_RE.search(blob):
        return "District"

    stripped = blob.strip()

    # Trailing grade tokens — MS
    if (stripped.endswith(" middle") or stripped.endswith(" jr high")
            or stripped.endswith(" j h") or stripped.endswith(" jr h")
            or stripped.endswith(" int") or stripped.endswith(" intermediate")
            or " middle " in blob or " j.h." in blob or " jhs" in blob):
        return "MS"

    if _MS_TRAIL_RE.search(stripped):
        return "MS"

    # Trailing grade tokens — HS
    if (stripped.endswith(" high") or stripped.endswith(" h s")
            or stripped.endswith(" h.s.") or stripped.endswith(" hs")
            or stripped.endswith(" sr high") or stripped.endswith(" senior")
            or " h s " in blob or " h.s. " in blob):
        return "HS"

    # Trailing grade tokens — Elem
    if (stripped.endswith(" primary") or stripped.endswith(" elem")
            or stripped.endswith(" e s") or stripped.endswith(" e.s.")):
        return "Elem"

    for kw in _MS_KWS:
        if kw in blob:
            return "MS"

    # Isolated ` ms ` — pass3 accepts it as MS signal
    if _MS_MIDDLE_RE.search(stripped):
        return "MS"

    for kw in _HS_KWS:
        if kw in blob:
            return "HS"
    for kw in _ELEM_KWS:
        if kw in blob:
            return "Elem"
    for kw in _ALLGRADES_KWS:
        if kw in blob:
            return "All-Grades"
    return "Unknown"


# ── Grade-span normalization (used by Territory Schools fuzzy-match) ────

_ELEM_SPANS = frozenset({
    "PK-5", "PK-6", "KG-5", "KG-6", "K-5", "K-6", "PK-4", "PK-K", "PK-KG",
    "K-4", "1-5", "1-6", "PK-3", "K-3", "PK-2", "KG-2", "KG-3", "KG-4",
    "PK-1", "K-1", "K-2", "PK-PK", "PK-0",
    "2-5", "2-6", "3-5", "3-6", "4-5", "4-6", "1-4", "1-3", "1-2",
})
_MS_SPANS = frozenset({
    "5-8", "6-8", "7-8", "6-7", "6-9", "7-9", "4-8", "5-7", "4-7",
    "5-6", "6-6", "7-7", "8-8",
})
_HS_SPANS = frozenset({
    "9-12", "10-12", "8-12", "7-12", "11-12", "9-11", "10-11", "6-12",
})
_ALLGRADES_SPANS = frozenset({"K-12", "KG-12", "PK-12", "PRE-K-12", "P-12"})
_ELEM_MIDDLE_SPANS = frozenset({"PK-8", "K-8", "KG-8"})  # route to Elem per spec


def map_grade_span(span_raw: str | None) -> SpanBucket | None:
    """Normalize an NCES-style Grade Span string to a bucket.

    NCES convention: -1 = PreK, 0 = K. `-1-X` normalizes to `PK-X`,
    `0-X` to `K-X`. Anything outside the known span sets returns None.
    """
    if not span_raw:
        return None
    s = span_raw.strip().upper().replace(" ", "")
    m = re.match(r"^-1-(\d+)$", s)
    if m:
        s = f"PK-{m.group(1)}"
    else:
        m = re.match(r"^0-(\d+)$", s)
        if m:
            s = f"K-{m.group(1)}"
    if s in _ALLGRADES_SPANS:
        return "AllGrades"
    if s in _ELEM_MIDDLE_SPANS:
        return "Elem"
    if s in _ELEM_SPANS:
        return "Elem"
    if s in _MS_SPANS:
        return "MS"
    if s in _HS_SPANS:
        return "HS"
    return None


# ── Name normalization (used by Territory Schools fuzzy-match) ──────────

_STRIP_WORDS = frozenset({
    "the", "school", "schools", "elementary", "middle", "high", "academy",
    "center", "centre", "inc", "llc", "junior", "senior", "primary",
    "preparatory", "prep", "intermediate", "jr", "sr", "of", "at",
})
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def normalize_name(s: str | None) -> str:
    """Lowercase, strip punctuation + stopword-ish tokens. Used as a fuzzy-match key."""
    s = (s or "").lower()
    s = _PUNCT_RE.sub(" ", s)
    tokens = [t for t in s.split() if t and t not in _STRIP_WORDS]
    return " ".join(tokens)
