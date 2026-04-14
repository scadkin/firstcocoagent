#!/usr/bin/env python3
"""
Scout rule scanner — structural enforcement of Rule 20 (every number labeled).

Reads text from stdin. If any number appears without a label root word nearby,
emits a JSON violation record to stdout and exits 0. On clean input, prints
nothing and exits 0. Shell out target for ~/.claude/hooks/scout-stop-scan.sh.

See /Users/stevenadkins/.claude/plans/playful-weaving-nygaard.md for the full
plan and rationale.

Claude Code hook API empirical findings:
    - Stop-block behavior: PENDING Commit 0 test 1
    - UserPromptSubmit injection: PENDING Commit 0 test 2
    - last_message contents: PENDING Commit 0 test 3
(Fill in verified findings once Commit 0 has been run in a throwaway session.)

Extensibility contract:
    Add a dict to RULES with number_patterns, label_roots, label_window_chars,
    and correction_template. Add test cases to test_rule_scanner.py. Run tests
    until green. No changes needed to hook wrappers or settings.json.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

RULES: list[dict[str, Any]] = [
    {
        "id": "R20",
        "name": "every-number-labeled",
        "pre_filter": r"\d",
        "number_patterns": [
            ("percent", r"\b\d+(?:\.\d+)?\s*%"),
            ("dollar",  r"\$\d+(?:\.\d+)?(?:[KMB])?\b"),
            ("tokens",  r"\b\d+(?:\.\d+)?\s*K?\s*tokens?\b"),
        ],
        "label_roots": [
            "measur",      # measured, measure, measurement
            "sample",      # sample, samples, sampled
            "estimat",     # estimate, estimated, estimating
            "extrapolat",  # extrapolation, extrapolated
            "unknown",
            "approximat",  # approximate, approximately
            "rough",       # rough, roughly
            "guess",       # guess, guessed
        ],
        "label_window_chars": 100,
        "correction_template": (
            "You violated Rule 20 (every number labeled). "
            "Unlabeled claims: {match_list}. "
            "Acknowledge by rule ID, restate each number followed by one of "
            "(measured), (sample), (estimate), (extrapolation), (unknown) in parens "
            "or use a label root word within the same sentence. "
            "Do NOT skip this acknowledgement before answering."
        ),
    },
]


def normalize(text: str) -> str:
    """Strip content that must not be scanned for rule violations."""
    # 1. Fenced code blocks — content inside ``` ``` is not Claude's prose claim
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # 2. Inline backtick spans
    text = re.sub(r"`[^`]*`", "", text)
    # 3. Markdown link targets — replace (url) with (...) so URL-encoded digits don't trigger
    text = re.sub(r"\]\([^)]*\)", "](...)", text)
    # 4. Drop any line containing the correction marker so Claude's own corrections
    #    never re-trigger the scanner
    text = re.sub(r"^.*\[RULE-SCANNER-CORRECTION\].*$", "", text, flags=re.MULTILINE)
    return text


def scan(text: str, rules: list[dict[str, Any]] = RULES) -> dict[str, Any]:
    """Scan text against every rule. Return a dict describing violations.

    Return shape:
        {
            "rule": "R20" | None,
            "violations": [{"type": str, "match": str, "position": int}, ...],
            "correction_directive": str,
        }
    """
    normalized = normalize(text)
    all_violations: list[dict[str, Any]] = []
    correction_parts: list[str] = []
    triggered_rule_id: str | None = None

    for rule in rules:
        pre_filter = rule.get("pre_filter")
        if pre_filter and not re.search(pre_filter, normalized):
            continue

        rule_violations: list[dict[str, Any]] = []
        for pattern_type, pattern in rule["number_patterns"]:
            for m in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                window_end = m.end() + rule["label_window_chars"]
                window = normalized[m.end():window_end].lower()
                label_roots = rule["label_roots"]
                labeled = any(root in window for root in label_roots) if label_roots else False
                if not labeled:
                    rule_violations.append({
                        "type": pattern_type,
                        "match": m.group(0),
                        "position": m.start(),
                    })

        if rule_violations:
            all_violations.extend(rule_violations)
            if triggered_rule_id is None:
                triggered_rule_id = rule["id"]
            match_list = ", ".join(f"'{v['match']}'" for v in rule_violations)
            correction_parts.append(rule["correction_template"].format(match_list=match_list))

    return {
        "rule": triggered_rule_id,
        "violations": all_violations,
        "correction_directive": " ".join(correction_parts) if correction_parts else "",
    }


def main() -> int:
    text = sys.stdin.read()
    result = scan(text)
    if result["violations"]:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
