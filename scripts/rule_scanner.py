#!/usr/bin/env python3
"""
Scout rule scanner — structural enforcement of Rule 20 (every number labeled).

Reads text from stdin. If any number appears without a label root word nearby,
emits a JSON violation record to stdout and exits 0. On clean input, prints
nothing and exits 0. Shell out target for ~/.claude/hooks/scout-stop-scan.sh.

See /Users/stevenadkins/.claude/plans/playful-weaving-nygaard.md for the full
plan and rationale.

Claude Code hook API empirical findings (verified 2026-04-14, Session 63):
    - Stop-block behavior: FORCES in-turn continuation. Claude Code reads
      `{"decision":"block","reason":"..."}` from a Stop hook's stdout and injects
      the reason as a synthetic user message ("Stop hook feedback: <reason>"),
      prompting Claude to produce a new assistant turn. Loops until a Stop hook
      returns clean OR Claude Code hits its internal max-turn limit.
      Recursion guard: `stop_hook_active: true` is set on recursive fires, and
      the wrapper's early-exit on that flag is what prevents infinite loops.
    - UserPromptSubmit injection: CONFIRMED. A hook emitting
      `{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"..."}}`
      reaches Claude's next turn context as extra directive text. Multiple
      UserPromptSubmit hooks run in parallel and their additionalContext
      values are both appended.
    - Stop hook stdin field: the field is `last_assistant_message` (NOT
      `last_message`). Contents are plain prose only — tool-use JSON blocks
      are NOT serialized into it, so no extra normalization step is required.
      Prior to 2026-04-14 the production wrapper read `.last_message` and
      silently fail-opened every turn since install. Fixed in S63 Commit 0.

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
    {
        "id": "R19",
        "name": "no-outreach-backend-ids",
        "pre_filter": r"\d",
        "number_patterns": [
            # prospect_id = 669325 / prospect_id: 669325 / prospect_id=669325
            ("prospect-id",    r"\bprospect_id\s*[:=]\s*\d+"),
            # sequenceState 522355
            ("sequencestate",  r"\bsequenceState\s+\d+"),
            # mailbox 11 / mailbox: 11
            ("mailbox",        r"\bmailbox\s*[:=]?\s*\d+"),
            # owner 11 / owner_id = 11 (the owner of a sequence/prospect)
            ("owner-id",       r"\bowner(?:_id)?\s*[:=]?\s*\d+"),
            # diocesan sequences 2008-2013 cited by literal ID
            ("diocesan-seq",   r"\bsequence\s+20(?:08|09|10|11|12|13)\b"),
            # template_id = 400 / schedule_id = 52
            ("template-id",    r"\btemplate_id\s*[:=]?\s*\d+"),
            ("schedule-id",    r"\bschedule_id\s*[:=]?\s*\d+"),
        ],
        "label_roots": [],  # no label can save you — these IDs must not appear
        "label_window_chars": 0,
        "correction_template": (
            "You violated Rule 19 (no Outreach backend IDs in chat). "
            "Matches: {match_list}. "
            "Restate using human names: prospect ID → 'First Last (email)', "
            "sequence ID → diocesan name (2008=Philadelphia, 2009=Cincinnati, "
            "2010=Detroit, 2011=Cleveland, 2012=Boston, 2013=Chicago), "
            "mailbox → 'your mailbox', owner → 'you' / 'Steven'. "
            "Acknowledge by rule ID before proceeding."
        ),
    },
    {
        "id": "R21",
        "type": "trigger_and_missing_anchor",
        "name": "verify-before-instructing",
        "pre_filter": r"(?i)\b(delete|remove|drop|clear|wipe|purge|truncate|modify|update|change|edit|overwrite|set|recommend|suggest|propose)\b",
        "trigger_patterns": [
            # Delete row/record/entry — present-tense imperative. Allows up to 5
            # intervening words (e.g. "delete the contaminated rows") via the
            # lazy \w+ quantifier.
            ("delete-row",         r"(?i)\b(?:delete|remove|drop)\s+(?:(?:the|this|that|these|those|all|\w+)\s+){0,5}?(?:row|rows|record|records|entry|entries|line|lines)\b"),
            # Ctrl+F find-and-delete workflow (exact S65 pattern). Uses [^\n]
            # (not [^.\n]) so email domain periods don't halt the lazy match.
            ("ctrl-f-find",        r"(?i)\b(?:Ctrl|Cmd|⌘)[\+\-\s]?F\s+[^\n]{0,80}?(?:delete|remove)"),
            # Right-click delete
            ("right-click-delete", r"(?i)right[- ]click[^\n]{0,40}?(?:delete|remove|drop)"),
            # Wipe/clear/purge a tab or sheet (up to 5 intervening words)
            ("wipe-clear-tab",     r"(?i)\b(?:wipe|clear|purge|truncate|empty|blank)\s+(?:out\s+)?(?:(?:the|this|that|\w+)\s+){0,5}?(?:tab|sheet|column|queue|list|backup)\b"),
            # Modify row/record/field/value/status (up to 5 intervening words)
            ("modify-row",         r"(?i)\b(?:modify|update|change|edit|overwrite|set)\s+(?:(?:the|this|that|\w+)\s+){0,5}?(?:row|record|entry|value|field|status|column|cell)\b"),
            # Delete row with numeric identifier
            ("delete-row-id",      r"(?i)\b(?:delete|remove|drop)\s+(?:the\s+)?(?:row|record|entry)\s+(?:\d+|[A-Z]\d+|ID\s*\d+)"),
            # Right-click or select navigation
            ("sheet-delete-nav",   r"(?i)(?:right[- ]click|select|highlight)[^\n]{0,60}?(?:delete\s+row|remove\s+row)"),
            # Soft-imperative "recommend/suggest/propose deleting X" — REQUIRES target word
            ("recommend-delete",   r"(?i)\b(?:recommend|suggest|propose)\s+(?:(?:that\s+)?(?:you|we)\s+)?(?:delet(?:e|ing)|remov(?:e|ing)|drop(?:ping)?|clear(?:ing)?|wip(?:e|ing)|modify(?:ing)?|updat(?:e|ing)|chang(?:e|ing))\s+(?:\w+\s+){0,5}?(?:row|record|entry|rows|records|entries|tab|column|field|value|status|sheet|queue)\b"),
        ],
        "anchor_patterns": [
            # Python live-state readers — any function call = verification
            r"\bget_leads\s*\(", r"\bcount_leads\s*\(",
            r"\bget_active_accounts\s*\(", r"\bget_districts_with_schools\s*\(",
            r"\bget_open_opps\s*\(", r"\bget_closed_lost_opps\s*\(", r"\bget_pipeline_summary\s*\(",
            r"\bget_pending\s*\(", r"\bget_all_prospects\s*\(",
            r"\bget_open_todos\s*\(", r"\bget_all_todos\s*\(",
            r"\bget_activity_summary\s*\(", r"\bget_daily_progress\s*\(", r"\bget_dormant_accounts\s*\(",
            r"\bget_territory_stats\s*\(", r"\bget_territory_gaps\s*\(", r"\blookup_district_enrollment\s*\(",
            r"\bget_active_signals\s*\(", r"\bget_existing_signal_ids\s*\(", r"\bget_processed_message_ids\s*\(",
            r"\bget_sequences\s*\(", r"\bget_sequence_states\s*\(", r"\bget_prospect\s*\(",
            r"\bget_mailings_for_prospect\s*\(", r"\bget_sequence_steps\s*\(",
            r"\bfind_prospect_by_email\s*\(", r"\bget_mailboxes\s*\(",
            r"\bget_file_content\s*\(", r"\blist_repo_files\s*\(",
            r"\bget_sent_emails\s*\(", r"\bsearch_inbox(?:_full)?\s*\(",
            r"\bget_threads_bulk\s*\(", r"\bget_calendar_events\s*\(",
            # Git state readers
            r"\bgit\s+(?:log|show|diff|status|blame)\b",
            # Python invocation prefix — implies live execution
            r"\.venv/bin/python\b",
            # Web readers (for non-sheet verification)
            r"\bWebFetch\b", r"\bWebSearch\b",
            # Narrated verification with function prefix
            r"(?i)\b(?:called|ran|queried|executed|invoked)\s+[`']?(?:get_|count_|lookup_|find_|list_|search_)",
        ],
        "anchor_text_scope": "raw",  # un-normalized text so code-block function calls count
        "exemption_patterns": [
            # Past-tense narrative: "In Session 55 we deleted 1,952 rows"
            r"(?i)\b(?:in\s+session\s+\d+|previously|earlier|already|before|last\s+\w+|historically|was|were)\s+[^\n]{0,100}?(?:deleted|removed|rotated|modified|updated|cleared|wiped)",
            # Hypothetical conditionals: "If you wanted to delete..."
            r"(?i)\b(?:if\s+you|if\s+we|when\s+you|suppose\s+you|imagine|would\s+(?:delete|remove|update|modify)|could\s+(?:delete|remove))",
            # Code behavior description, present-tense: "the function deletes duplicates"
            r"(?i)\b(?:the\s+)?(?:\w+\s+)?(?:function|method|script|tool|handler|scanner|writer)\s+(?:automatically\s+)?(?:deletes?|removes?|modifies|updates?|changes?|clears?|wipes?)",
            # Code behavior description, future-tense: "the script will delete rows"
            r"(?i)\b(?:the\s+)?(?:\w+\s+)?(?:function|method|script|tool|handler|scanner|writer)\s+(?:will|would|should|might|could|can)\s+(?:delete|remove|drop|clear|wipe|modify|update|change)",
            # Method-call syntax: "sheets_writer.write_contacts() modifies..."
            r"(?i)\b\w+\.\w+\s*\([^)]*\)\s+(?:deletes?|removes?|modifies|updates?|changes?)",
            # Questions, not instructions: "should we delete", "do you want to remove"
            r"(?i)\b(?:should\s+(?:we|i|you)|do\s+you\s+want|would\s+you\s+like|shall\s+(?:we|i)|can\s+you)\s+[^\n]{0,40}?(?:delet|remov|drop|modif|updat|chang|wip|clear)",
            # Negations: "do not delete", "never modify", "you should not remove"
            r"(?i)\b(?:do\s+not|don't|never|should\s+not|shouldn't|must\s+not|mustn't|won't|will\s+not)\s+(?:\w+\s+){0,3}?(?:delet|remov|drop|modif|updat|chang|wip|clear|overwrit)",
        ],
        "exemption_window_chars": 120,
        "correction_template": (
            "⚠ RULE 21 VIOLATION — DO NOT EXECUTE THE PRIOR TURN'S INSTRUCTIONS. "
            "They were issued without source verification and may reference rows that "
            "don't exist, are already correctly labeled, or target the wrong records. "
            "Triggers: {match_list}. "
            "Before telling Steven to delete, modify, or mutate live state, you MUST "
            "first query the authoritative source in the same turn (sheets_writer.get_leads, "
            "csv_importer.get_active_accounts, outreach_client.get_sequences, git log, etc.) "
            "and cite the reader call in prose or a code block. "
            "Re-issue the instructions in THIS turn with a live source query, or retract them."
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


def _truncate_match(s: str, n: int = 50) -> str:
    """Truncate long regex matches for correction-template readability.

    R21 trigger regexes can capture ~100 chars (e.g. Ctrl+F...Delete row).
    Quoted unchanged in correction directives they render as an unreadable
    wall of text. Applies to all rules; R19/R20 matches are short enough
    to pass through unchanged.
    """
    return s if len(s) <= n else s[:n - 3] + "..."


def scan(text: str, rules: list[dict[str, Any]] = RULES) -> dict[str, Any]:
    """Scan text against every rule. Return a dict describing violations.

    Return shape:
        {
            "rule": "R20" | "R19" | "R21" | None,
            "violations": [{"type": str, "match": str, "position": int}, ...],
            "correction_directive": str,
        }

    Rule dispatch by `type` field:
        - "labeled_number" (default, R19/R20): detect number/ID patterns, check
          for label root word in forward window after each match.
        - "trigger_and_missing_anchor" (R21): detect destructive-instruction
          triggers, check for verification anchor anywhere in response, check
          exemption window around each trigger. Fires when trigger present AND
          no anchor AND no exemption.
    """
    normalized = normalize(text)
    all_violations: list[dict[str, Any]] = []
    correction_parts: list[str] = []
    triggered_rule_id: str | None = None

    for rule in rules:
        pre_filter = rule.get("pre_filter")
        if pre_filter and not re.search(pre_filter, normalized, flags=re.IGNORECASE):
            continue

        rule_type = rule.get("type", "labeled_number")
        rule_violations: list[dict[str, Any]] = []

        if rule_type == "labeled_number":
            # ─── Existing R19/R20 path — unchanged semantics ───
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

        elif rule_type == "trigger_and_missing_anchor":
            # ─── R21 path ───
            # Performance: collect triggers FIRST (cheap); only pay anchor cost
            # if at least one trigger matched.
            trigger_matches: list[tuple[str, "re.Match[str]"]] = []
            for pattern_type, pattern in rule["trigger_patterns"]:
                for m in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                    trigger_matches.append((pattern_type, m))
            if not trigger_matches:
                continue  # no destructive triggers; skip anchor+exemption work

            # Anchor check — verification function name anywhere in the scoped text
            anchor_scope = rule.get("anchor_text_scope", "normalized")
            anchor_text = text if anchor_scope == "raw" else normalized
            anchor_present = any(
                re.search(p, anchor_text, flags=re.IGNORECASE)
                for p in rule["anchor_patterns"]
            )
            if anchor_present:
                continue  # verification cited; rule passes

            # Exemption check — per-trigger window
            exemption_patterns = rule.get("exemption_patterns", [])
            exemption_window = rule.get("exemption_window_chars", 120)
            for pattern_type, m in trigger_matches:
                w_start = max(0, m.start() - exemption_window)
                w_end = min(len(normalized), m.end() + exemption_window)
                window = normalized[w_start:w_end]
                exempted = any(
                    re.search(ep, window, flags=re.IGNORECASE)
                    for ep in exemption_patterns
                )
                if not exempted:
                    rule_violations.append({
                        "type": pattern_type,
                        "match": m.group(0),
                        "position": m.start(),
                    })

        if rule_violations:
            all_violations.extend(rule_violations)
            if triggered_rule_id is None:
                triggered_rule_id = rule["id"]
            match_list = ", ".join(
                f"'{_truncate_match(v['match'])}'" for v in rule_violations
            )
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
