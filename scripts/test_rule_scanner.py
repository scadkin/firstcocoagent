#!/usr/bin/env python3
"""Test harness for scripts/rule_scanner.py. Run from repo root.

Usage: .venv/bin/python scripts/test_rule_scanner.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rule_scanner import scan

TESTS: list[tuple[str, str, int]] = [
    # (label, input_text, expected_violation_count)
    ("bare percent",                           "17% of the window",                                                  1),
    ("labeled parens",                          "17% (measured) of the window",                                       0),
    ("labeled natural language",                "17% of the window, measured from wc output",                         0),
    ("labeled estimated roughly",               "17% (estimated roughly)",                                            0),
    ("labeled approximate",                     "17% — this is an approximate figure",                                0),
    ("multiple bare percents",                  "9%, 21%, and 15% all different",                                     3),
    ("fenced code block stripped",              "```python\nx = 17 / 100  # 17% target\n```",                         0),
    ("inline backticks stripped",               "inline `17%` in backticks",                                          0),
    ("URL target stripped, prose percent left", "See [doc](https://a.com/17%20bar) for 17%",                          1),
    ("correction prefix excluded",              "[RULE-SCANNER-CORRECTION] the value is 15% (measured)",              0),
    ("bare dollar",                             "$0.25 per job",                                                      1),
    ("labeled dollar",                          "$0.25 per job (measured)",                                           0),
    ("bare tokens count",                       "134 tokens",                                                         1),
    ("labeled K-tokens",                        "17K tokens (sample from one run)",                                   0),
    ("bare count with unlisted unit",           "17 contacts",                                                        0),
    ("labeled percent + ignored time",          "99.9% uptime, measured over 30 days",                                0),
    ("bare 100 percent",                        "100%",                                                               1),
    ("no numbers pre-filter short-circuit",     "text with no numbers at all",                                        0),
    ("two percents share one label in window",  "17% and 18%, both measured",                                         0),
    ("two percents each with distinct labels",  "17% and 18%, first measured second guessed",                         0),

    # R19 — no Outreach backend IDs
    ("R19 prospect_id equals",                   "prospect_id = 669325 needs follow-up",                               1),
    ("R19 prospect_id colon",                    "prospect_id: 669325",                                                1),
    ("R19 prospect_id no spaces",                "prospect_id=669325",                                                 1),
    ("R19 sequenceState space",                  "added to sequenceState 522355",                                      1),
    ("R19 mailbox",                              "mailbox 11 is yours",                                                1),
    ("R19 owner",                                "owner 11 is Steven",                                                 1),
    ("R19 diocesan seq by number",               "added to sequence 2013",                                             1),
    ("R19 non-diocesan seq number ignored",      "added to sequence 2015",                                             0),
    ("R19 template_id",                          "template_id = 400 changed",                                          1),
    ("R19 schedule_id",                          "schedule_id: 52",                                                    1),
    ("R19 human-name restatement is clean",      "added Rosie Carollo (rcarollo@archphila.org) to Philadelphia diocesan", 0),
    ("R19 code block strips the ID",             "```python\nprospect_id = 669325\n```",                               0),
    ("R19 inline code strips the ID",            "inline `mailbox 11` is yours",                                       0),
    ("R19 multiple IDs in one line",             "prospect_id = 669325 added to sequence 2013 in mailbox 11",          3),
]


def run() -> int:
    fails: list[tuple[str, str, int, int, list]] = []
    for label, text, expected in TESTS:
        result = scan(text)
        got = len(result["violations"])
        if got != expected:
            fails.append((label, text, expected, got, result["violations"]))

    if fails:
        print(f"FAIL: {len(fails)}/{len(TESTS)} test cases wrong")
        for label, text, expected, got, violations in fails:
            print(f"  [{label}] expected {expected}, got {got}")
            print(f"    text:       {text!r}")
            print(f"    violations: {violations}")
        return 1

    print(f"PASS: all {len(TESTS)} test cases green")
    return 0


if __name__ == "__main__":
    sys.exit(run())
