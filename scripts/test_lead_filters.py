"""
Unit tests for tools/lead_filters.py.

Runs as a script (no pytest):
    .venv/bin/python scripts/test_lead_filters.py

Pure-logic tests only. The sheets-I/O driver (classify_sf_leads_to_dre_buckets)
is exercised by the separate live parity script scripts/verify_lead_filters_live.py.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.lead_filters import (  # noqa: E402
    ALL_DRE_COHORTS,
    INT_SOURCES,
    LQD_SOURCES,
    TC_SOURCES,
    TerritoryIndex,
    classify_row,
    classify_rows,
    detect_role,
    fuzzy_match_v5,
)

_passed = 0
_failed: list[str] = []


def check(label: str, got, expected) -> None:
    global _passed
    if got == expected:
        _passed += 1
    else:
        _failed.append(f"FAIL {label}: got {got!r}, expected {expected!r}")


# ── detect_role ────────────────────────────────────────────────────────
check("role empty", detect_role(""), "empty")
check("role None", detect_role(None), "empty")
check("role librarian", detect_role("School Librarian"), "library")
check("role media specialist", detect_role("Media Specialist"), "library")
check("role teacher", detect_role("5th Grade Teacher"), "teacher")
check("role instructor", detect_role("Math Instructor"), "teacher")
check("role faculty", detect_role("Faculty"), "teacher")
check("role it cto", detect_role("CTO"), "it")
check("role it director of tech", detect_role("Director of Technology Services"), "it")
check("role other principal", detect_role("Assistant Principal"), "other")
check("role other superintendent", detect_role("Superintendent"), "other")


# ── Whitelist sanity ───────────────────────────────────────────────────
check("TC_SOURCES size", len(TC_SOURCES), 2)
check("LQD_SOURCES size", len(LQD_SOURCES), 3)
check("INT_SOURCES size", len(INT_SOURCES), 22)
check("TC_SOURCES lowercase", "teacher created account" in TC_SOURCES, True)
check("INT_SOURCES lowercase", "cue 2023" in INT_SOURCES, True)


# ── Empty TerritoryIndex (for tests that don't hit the fuzzy path) ─────
EMPTY_IDX = TerritoryIndex(
    exact_by_state=defaultdict(list),
    norm_by_state=defaultdict(list),
    exact_all=defaultdict(list),
    norm_all=defaultdict(list),
    district_by_state=defaultdict(list),
    district_all=defaultdict(list),
    norm_keys_by_state=defaultdict(set),
)


def row(**kw) -> dict:
    base = {"state": "", "title": "", "company": "", "lead_source": "",
            "verified_school": "", "email": "x@y.com",
            "first_name": "A", "last_name": "B"}
    base.update(kw)
    return base


# ── Universal exclusions ───────────────────────────────────────────────
c, r = classify_row(row(company="Code Ninjas Plano"), EMPTY_IDX)
check("excluded code ninjas cohort", c, None)
check("excluded code ninjas reason", r, "excluded_code_ninjas")

c, r = classify_row(row(company="Jane Smith Homeschool"), EMPTY_IDX)
check("excluded homeschool individual", c, None)
check("excluded homeschool individual reason", r, "excluded_homeschool_individual")

c, r = classify_row(row(company="Austin Homeschool Co-op"), EMPTY_IDX)
check("excluded homeschool network", c, None)
check("excluded homeschool network reason", r, "excluded_homeschool_network")


# ── Librarian title beats substrategy ──────────────────────────────────
c, r = classify_row(row(title="School Librarian", lead_source="ZenProspect"), EMPTY_IDX)
check("lib beats parked", c, "LIB")
check("lib match reason", r, "match")

c, r = classify_row(row(title="Media Specialist", lead_source="Teacher Created Account"), EMPTY_IDX)
check("lib beats TC", c, "LIB")


# ── TC substrategy ─────────────────────────────────────────────────────
c, r = classify_row(
    row(title="", lead_source="Teacher Created Account",
        company="Westfield High School"),
    EMPTY_IDX,
)
check("TC empty → TC-HS", c, "TC-HS")

c, r = classify_row(
    row(title="", lead_source="Converted Teacher Account",
        company="Plano ISD"),
    EMPTY_IDX,
)
check("TC empty → TC-District", c, "TC-District")

c, r = classify_row(
    row(title="", lead_source="Teacher Created Account",
        company="Texas Virtual Academy"),
    EMPTY_IDX,
)
check("TC empty → TC-Virtual", c, "TC-Virtual")

c, r = classify_row(
    row(title="", lead_source="Teacher Created Account",
        company="Some Weirdly Named Thing"),
    EMPTY_IDX,
)
check("TC empty unparseable → TC-Universal-Residual", c, "TC-Universal-Residual")

c, r = classify_row(
    row(title="3rd Grade Teacher", lead_source="Teacher Created Account",
        company="Willow Elementary"),
    EMPTY_IDX,
)
check("TC teacher title → TC-Teacher", c, "TC-Teacher")

c, r = classify_row(
    row(title="CTO", lead_source="Teacher Created Account",
        company="Plano ISD"),
    EMPTY_IDX,
)
check("TC IT title → IT-ReEngage", c, "IT-ReEngage")

c, r = classify_row(
    row(title="Superintendent", lead_source="Teacher Created Account",
        company="Plano ISD"),
    EMPTY_IDX,
)
check("TC other title → TC-Universal-Residual", c, "TC-Universal-Residual")


# ── LQD substrategy ────────────────────────────────────────────────────
for src in ("License Request", "Request a Quote/Demo", "Request a Quote/ Demo"):
    c, r = classify_row(row(lead_source=src), EMPTY_IDX)
    check(f"LQD {src!r} → LQD-Universal", c, "LQD-Universal")

# LQD with populated title still lands in LQD-Universal
c, _ = classify_row(
    row(title="Superintendent", lead_source="License Request"),
    EMPTY_IDX,
)
check("LQD keeps any-title → LQD-Universal", c, "LQD-Universal")


# ── INT substrategy ────────────────────────────────────────────────────
c, _ = classify_row(row(lead_source="CUE 2023"), EMPTY_IDX)
check("INT empty → INT-Universal", c, "INT-Universal")

c, _ = classify_row(
    row(title="5th Grade Teacher", lead_source="CSTA 2022"),
    EMPTY_IDX,
)
check("INT teacher → INT-Teacher", c, "INT-Teacher")

c, _ = classify_row(
    row(title="CTO", lead_source="Drift"),
    EMPTY_IDX,
)
check("INT IT → IT-ReEngage", c, "IT-ReEngage")

c, r = classify_row(
    row(title="Superintendent", lead_source="CUE 2023"),
    EMPTY_IDX,
)
check("INT other title → parked", c, None)
check("INT other title reason", r, "parked_int_other_role")

# Case-insensitive INT match
c, _ = classify_row(row(lead_source="cue 2023"), EMPTY_IDX)
check("INT ci lowercase", c, "INT-Universal")

c, _ = classify_row(row(lead_source="CUE 2023  "), EMPTY_IDX)
check("INT trailing whitespace", c, "INT-Universal")


# ── Parked (no substrategy match) ──────────────────────────────────────
c, r = classify_row(row(lead_source="ZenProspect"), EMPTY_IDX)
check("parked ZenProspect cohort", c, None)
check("parked ZenProspect reason", r, "parked_no_source_match")


# ── fuzzy_match_v5 ─────────────────────────────────────────────────────
# Build a small hand-curated index: 2 schools in TX, 1 in CA
mini_idx = TerritoryIndex(
    exact_by_state={
        ("TX", "acme middle"): ["6-8"],
        ("TX", "crossroads school"): ["K-12"],
        ("CA", "acme middle"): ["9-12"],  # same name, different grade
    },
    norm_by_state={("TX", "acme"): ["6-8"], ("CA", "acme"): ["9-12"]},
    exact_all={
        "acme middle": [("6-8", "TX"), ("9-12", "CA")],
        "crossroads school": [("K-12", "TX")],
    },
    norm_all={"acme": [("6-8", "TX"), ("9-12", "CA")]},
    district_by_state={},
    district_all={},
    norm_keys_by_state={"TX": {"acme"}, "CA": {"acme"}},
)
check("fuzzy state-disambig TX", fuzzy_match_v5("Acme Middle", "TX", mini_idx), "MS")
check("fuzzy state-disambig CA", fuzzy_match_v5("Acme Middle", "CA", mini_idx), "HS")
check("fuzzy global unanimous", fuzzy_match_v5("Crossroads School", "NV", mini_idx), "AllGrades")
check("fuzzy global ambiguous", fuzzy_match_v5("Acme Middle", "", mini_idx), None)
check("fuzzy empty", fuzzy_match_v5("", "TX", mini_idx), None)
check("fuzzy no match", fuzzy_match_v5("Nowhere School", "TX", mini_idx), None)


# ── classify_rows end-to-end ───────────────────────────────────────────
fixtures = [
    row(title="", lead_source="Teacher Created Account", company="Plano HS"),
    row(title="", lead_source="Teacher Created Account", company="Riverdale Middle"),
    row(title="", lead_source="Teacher Created Account", company="Sunset Elementary"),
    row(title="", lead_source="Teacher Created Account", company="Plano ISD"),
    row(title="", lead_source="Teacher Created Account", company="Texas Virtual Academy"),
    row(title="", lead_source="Teacher Created Account", company="Crossroads K-12"),
    row(title="", lead_source="Teacher Created Account", company="No Obvious Name"),
    row(title="CTO", lead_source="Teacher Created Account", company="Plano ISD"),
    row(title="Teacher", lead_source="Teacher Created Account", company="Acme ES"),
    row(title="Librarian", lead_source="Teacher Created Account", company="Acme HS"),
    row(lead_source="License Request"),
    row(title="", lead_source="CUE 2023"),
    row(title="Teacher", lead_source="Drift"),
    row(title="Superintendent", lead_source="CUE 2023"),
    row(lead_source="ZenProspect"),
    row(company="Code Ninjas X"),
    row(company="Smith Homeschool"),
]

result = classify_rows(fixtures, EMPTY_IDX)
check("rows total scanned", result.total_rows_scanned, 17)
check("rows total matched", result.total_matched, 13)
check("rows excluded code_ninjas", result.excluded["excluded_code_ninjas"], 1)
check("rows excluded homeschool", result.excluded["excluded_homeschool_individual"], 1)
check("rows parked no_source", result.excluded["parked_no_source_match"], 1)
check("rows parked INT other", result.excluded["parked_int_other_role"], 1)

sizes = result.cohort_sizes()
check("bucket TC-HS", sizes["TC-HS"], 1)
check("bucket TC-MS", sizes["TC-MS"], 1)
check("bucket TC-Elem", sizes["TC-Elem"], 1)
check("bucket TC-District", sizes["TC-District"], 1)
check("bucket TC-Virtual", sizes["TC-Virtual"], 1)
check("bucket TC-All-Grades", sizes["TC-All-Grades"], 1)
check("bucket TC-Universal-Residual", sizes["TC-Universal-Residual"], 1)
check("bucket TC-Teacher", sizes["TC-Teacher"], 1)
check("bucket LIB", sizes["LIB"], 1)
check("bucket IT-ReEngage", sizes["IT-ReEngage"], 1)
check("bucket LQD-Universal", sizes["LQD-Universal"], 1)
check("bucket INT-Universal", sizes["INT-Universal"], 1)
check("bucket INT-Teacher", sizes["INT-Teacher"], 1)
check("all 13 cohort keys present", set(sizes) == set(ALL_DRE_COHORTS), True)


# ── Report ─────────────────────────────────────────────────────────────
print(f"Passed: {_passed}")
if _failed:
    for line in _failed:
        print(line)
    print(f"Failed: {len(_failed)}")
    sys.exit(1)
print("All tests passed.")
