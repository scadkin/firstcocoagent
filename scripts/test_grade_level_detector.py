"""
Unit tests for tools/grade_level_detector.py — pure-function classifier.

Runs as a script (no pytest dependency):
    .venv/bin/python scripts/test_grade_level_detector.py

Fixtures are hand-picked real-world names lifted from Session 72's
classification passes. Any regression in the lifted rules will flip
one of these assertions.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.grade_level_detector import (  # noqa: E402
    detect_grade,
    homeschool_subsplit,
    is_code_ninjas,
    is_homeschool,
    is_virtual,
    map_grade_span,
    normalize_name,
)

_passed = 0
_failed: list[str] = []


def check(label: str, got, expected) -> None:
    global _passed
    if got == expected:
        _passed += 1
    else:
        _failed.append(f"FAIL {label}: got {got!r}, expected {expected!r}")


# ── Code Ninjas ─────────────────────────────────────────────────────────
check("code-ninjas lower", is_code_ninjas("code ninjas tulsa"), True)
check("code-ninjas mixed", is_code_ninjas("Code Ninjas Plano West"), True)
check("code-ninjas negative", is_code_ninjas("Plano ISD"), False)
check("code-ninjas empty", is_code_ninjas(""), False)
check("code-ninjas None", is_code_ninjas(None), False)

# ── Homeschool ──────────────────────────────────────────────────────────
check("homeschool word", is_homeschool("Homeschool"), True)
check("homeschool standalone home", is_homeschool("Home"), True)
check("homeschool compound", is_homeschool("Smith Family Homeschooling"), True)
check("homeschool with dash", is_homeschool("Home-School Group"), True)
check("homeschool negative", is_homeschool("Home Depot"), False)
check("homeschool empty", is_homeschool(""), False)

check("subsplit network co-op", homeschool_subsplit("Austin Homeschool Co-op"), "TC-Homeschool-Network")
check("subsplit network classical", homeschool_subsplit("Classical Conversations Home School"), "TC-Homeschool-Network")
check("subsplit network academy", homeschool_subsplit("Legacy Home School Academy"), "TC-Homeschool-Network")
check("subsplit excluded lone", homeschool_subsplit("Smith Homeschool"), "TC-Homeschool-Excluded")

# ── Virtual ─────────────────────────────────────────────────────────────
check("virtual academy", is_virtual("Texas Virtual Academy", ""), True)
check("virtual cyber", is_virtual("Pennsylvania Cyber Charter School"), True)
check("virtual ecot", is_virtual("ECOT Columbus", ""), True)
check("virtual verified col", is_virtual("Something Name", "K12 Inc. Program"), True)
check("virtual fallback regex", is_virtual("My Virtual Learning Initiative", ""), True)
check("virtual negative", is_virtual("Plano ISD", ""), False)

# ── detect_grade ────────────────────────────────────────────────────────
# District
check("grade district isd", detect_grade("Plano ISD"), "District")
check("grade district archdiocese", detect_grade("Archdiocese of Chicago"), "District")
check("grade district unified", detect_grade("Los Angeles Unified"), "District")
check("grade district boces", detect_grade("Orleans Niagara BOCES"), "District")
check("grade district public schools", detect_grade("Boston Public Schools"), "District")

# MS
check("grade MS full", detect_grade("Mountain View Middle School"), "MS")
check("grade MS jhs", detect_grade("Lincoln JHS"), "MS")
check("grade MS trailing", detect_grade("Jefferson M.S."), "MS")
check("grade MS range", detect_grade("Acme Academy 6-8"), "MS")
check("grade MS isolated abbrev", detect_grade("Washington MS"), "MS")

# HS
check("grade HS full", detect_grade("Westfield High School"), "HS")
check("grade HS trailing hs", detect_grade("Jefferson HS"), "HS")
check("grade HS range", detect_grade("Acme School 9-12"), "HS")
check("grade HS prep", detect_grade("St Mark's Preparatory Academy"), "HS")
check("grade HS vocational", detect_grade("Tulsa Technical High School"), "HS")

# Elem
check("grade Elem full", detect_grade("Willow Elementary"), "Elem")
check("grade Elem k-5", detect_grade("Acme School K-5"), "Elem")
check("grade Elem primary", detect_grade("Sunshine Primary School"), "Elem")
check("grade Elem kindergarten", detect_grade("Tiny Kindergarten"), "Elem")

# All-Grades
check("grade All k-12", detect_grade("Crossroads K-12 Academy"), "All-Grades")
check("grade All pk-12", detect_grade("Sunset PK-12 School"), "All-Grades")

# Unknown
check("grade Unknown generic", detect_grade("Acme Educational Services"), "Unknown")
check("grade Unknown empty", detect_grade(""), "Unknown")

# District takes precedence over grade keywords
check("grade precedence district > HS", detect_grade("Plano ISD High Office"), "District")

# ── map_grade_span ──────────────────────────────────────────────────────
check("span k-5", map_grade_span("K-5"), "Elem")
check("span PK-5 whitespace", map_grade_span(" PK-5 "), "Elem")
check("span 6-8", map_grade_span("6-8"), "MS")
check("span 9-12", map_grade_span("9-12"), "HS")
check("span K-12 all", map_grade_span("K-12"), "AllGrades")
check("span PK-12 normalize", map_grade_span("-1-12"), "AllGrades")
check("span 0-5 normalize", map_grade_span("0-5"), "Elem")
check("span PK-8 route elem", map_grade_span("PK-8"), "Elem")
check("span unknown", map_grade_span("13-20"), None)
check("span empty", map_grade_span(""), None)
check("span None", map_grade_span(None), None)

# ── normalize_name ──────────────────────────────────────────────────────
check("norm strip school", normalize_name("Willow Elementary School"), "willow")
check("norm strip punctuation", normalize_name("St. Mark's Preparatory Academy"), "st mark s")
check("norm empty", normalize_name(""), "")
check("norm lowercase", normalize_name("ACME MIDDLE"), "acme")


# ── Report ──────────────────────────────────────────────────────────────
print(f"Passed: {_passed}")
if _failed:
    for line in _failed:
        print(line)
    print(f"Failed: {len(_failed)}")
    sys.exit(1)
print("All tests passed.")
