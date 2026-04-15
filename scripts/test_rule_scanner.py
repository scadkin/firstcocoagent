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

    # R21 — verify before instructing Steven to modify live state
    # Trigger-fires (no anchor, no exemption → FIRE)
    ("R21 delete row by index",                  "Delete row X from the Leads from Research tab.",                    1),
    ("R21 delete rows plural",                   "Delete the rows I flagged in the audit doc.",                        1),
    ("R21 remove record with email",             "Remove the record for melissa@collinsville.k12.ok.us.",              1),
    # Multi-match: Ctrl+F + right-click + delete row all trigger distinct patterns on the same phrase
    ("R21 Ctrl+F find-and-delete",               "Ctrl+F melissa@example.com and right-click Delete row.",             4),
    ("R21 right-click delete row",               "Right-click the row and choose Delete row.",                         3),
    ("R21 wipe backup tab",                      "Wipe the Prospecting Queue BACKUP tab once comfortable.",            1),
    ("R21 clear the Signals tab",                "Clear the Signals tab to remove test-run scaffolding.",              1),
    ("R21 modify status field",                  "Modify the status field to approved for row X.",                     1),
    ("R21 update row value",                     "Update the row value in the Priority column to a higher tier.",     1),
    ("R21 recommend deleting rows",              "I recommend deleting the contaminated rows below.",                  1),
    # Multi-match: ctrl-f-find + right-click-delete + sheet-delete-nav + delete-row all fire on the primary Delete row phrase
    ("R21 S65 incident regression",              "Ctrl+F melissa@collinsville.k12.ok.us → right-click row → Delete row. Also delete kcraig@spiro.k12.ok.us and cisenhour@wcloud.org.", 4),

    # Anchor-saves (trigger + anchor → CLEAN)
    ("R21 clean: get_leads narrated",            "I called get_leads() and found rows matching. Delete the row for melissa.", 0),
    ("R21 clean: anchor in code block",          "```python\nfrom tools.sheets_writer import get_leads\nleads = get_leads()\n```\nBased on the data returned (measured), delete the row for melissa.", 0),
    ("R21 clean: git log anchor",                "git log shows the commit history. Clear the test tab now.",         0),
    ("R21 clean: .venv/bin/python anchor",       ".venv/bin/python -c 'from tools.sheets_writer import get_leads' confirmed the row. Delete row X.", 0),
    ("R21 clean: get_sequences anchor",          "I ran get_sequences() and confirmed the sequence is active. Modify the status field to paused.", 0),
    ("R21 clean: get_active_accounts anchor",    "After calling get_active_accounts(), I see duplicates. Delete the duplicate row for Austin ISD.", 0),

    # Exemption-saves (trigger + exemption → CLEAN)
    ("R21 clean: past-tense S55",                "In Session 55 we deleted the scrambled rows via the repair script.", 0),
    ("R21 clean: hypothetical if-you",           "If you wanted to delete row X, the procedure would be Ctrl+F then right-click.", 0),
    ("R21 clean: code behavior present",         "The sheets_writer.write_contacts() function deletes duplicates automatically on merge.", 0),
    ("R21 clean: code behavior future",          "The cleanup script will delete rows flagged by the audit.",         0),
    ("R21 clean: question not instruction",      "Should we delete the test rows from the Signals tab?",              0),
    ("R21 clean: negation",                      "Do NOT delete these rows — they are active leads.",                  0),

    # Edge cases
    ("R21 clean: delete in inline backtick",     "The command `delete row` is a git alias.",                           0),
    ("R21 clean: correction prefix stripped",    "[RULE-SCANNER-CORRECTION] Delete row X violates Rule 21.",           0),
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
