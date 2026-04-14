#!/bin/bash
# Automated smoke tests for the Scout rule-scanner hook wrappers.
#
# The wrappers are machine-local (not tracked in this repo):
#   ~/.claude/hooks/scout-stop-scan.sh
#   ~/.claude/hooks/scout-violation-inject.sh
#
# This script exercises them against a temp violation log via the
# SCOUT_VIOLATIONS_LOG env override shipped in Session 63, so it
# cannot poison the real production log at ~/.claude/state/scout-violations.log.
#
# Gracefully skips with exit 0 if the wrappers are not installed (e.g.
# fresh clone on a new machine). Fails loudly with exit 1 on any test
# assertion failure.
#
# Usage: bash scripts/test_hook_wrappers.sh
#
# Companion to scripts/test_rule_scanner.py (which tests the Python
# scan() function in isolation).

set -u

STOP_SCAN="$HOME/.claude/hooks/scout-stop-scan.sh"
INJECTOR="$HOME/.claude/hooks/scout-violation-inject.sh"

if [ ! -f "$STOP_SCAN" ] || [ ! -f "$INJECTOR" ]; then
    echo "SKIP: hook wrappers not installed at $STOP_SCAN or $INJECTOR"
    echo "  (expected on a fresh clone before the machine-local wrappers are recreated;"
    echo "   see memory/feedback_rule_scanner_hook_installed.md §Rebuild on a new machine)"
    exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "SKIP: jq not on PATH — hook wrappers require jq"
    exit 0
fi

# Guard against running while the kill switch is engaged — the wrappers
# short-circuit at the top of the file and every test would silently pass.
if [ -f "$HOME/.claude/state/scout-hooks-disabled" ]; then
    echo "SKIP: kill switch is engaged at ~/.claude/state/scout-hooks-disabled"
    echo "  (rm it to re-enable, then re-run this script)"
    exit 0
fi

TMP_LOG="$(mktemp -t scout-smoke-vlog.XXXXXX)"
export SCOUT_VIOLATIONS_LOG="$TMP_LOG"
rm -f "$TMP_LOG" "$TMP_LOG.processing"

fail() {
    echo "FAIL: $1"
    unset SCOUT_VIOLATIONS_LOG
    rm -f "$TMP_LOG" "$TMP_LOG.processing"
    exit 1
}

log_line_count() {
    [ -f "$TMP_LOG" ] || { echo 0; return; }
    wc -l < "$TMP_LOG" | tr -d ' '
}

# ---- Test A: bare percent triggers block + writes log ----
out_a=$(echo '{"session_id":"t","last_assistant_message":"the answer is 17%","stop_hook_active":false}' \
    | bash "$STOP_SCAN")
[ -n "$out_a" ] || fail "Test A: expected non-empty stdout, got empty"
echo "$out_a" | jq -e '.decision == "block"' >/dev/null 2>&1 \
    || fail "Test A: expected decision:block in stdout, got: $out_a"
[ "$(log_line_count)" = "1" ] || fail "Test A: expected 1 log line, got $(log_line_count)"

# ---- Test B: labeled percent is clean (empty stdout, no new log write) ----
out_b=$(echo '{"session_id":"t","last_assistant_message":"the answer is 17% (measured)","stop_hook_active":false}' \
    | bash "$STOP_SCAN")
[ -z "$out_b" ] || fail "Test B: expected empty stdout, got: $out_b"
[ "$(log_line_count)" = "1" ] || fail "Test B: expected 1 log line (unchanged), got $(log_line_count)"

# ---- Test C: recursion guard short-circuits on stop_hook_active:true ----
out_c=$(echo '{"session_id":"t","last_assistant_message":"17% bare","stop_hook_active":true}' \
    | bash "$STOP_SCAN")
[ -z "$out_c" ] || fail "Test C: expected empty stdout (recursion guard), got: $out_c"
[ "$(log_line_count)" = "1" ] || fail "Test C: expected 1 log line (unchanged), got $(log_line_count)"

# ---- Test D: injector consumes the log and emits additionalContext ----
out_d=$(echo '{}' | bash "$INJECTOR")
[ -n "$out_d" ] || fail "Test D: expected non-empty stdout from injector, got empty"
echo "$out_d" | jq -e '.hookSpecificOutput.hookEventName == "UserPromptSubmit"' >/dev/null 2>&1 \
    || fail "Test D: expected hookSpecificOutput.hookEventName UserPromptSubmit, got: $out_d"
echo "$out_d" | jq -e '.hookSpecificOutput.additionalContext | contains("17%")' >/dev/null 2>&1 \
    || fail "Test D: expected additionalContext to mention 17%, got: $out_d"
[ ! -f "$TMP_LOG" ] || fail "Test D: expected temp log to be gone after injector consume, still at $TMP_LOG"
[ ! -f "$TMP_LOG.processing" ] || fail "Test D: expected temp log.processing to be gone, still at $TMP_LOG.processing"

# ---- Test E: production log is untouched throughout ----
[ ! -f "$HOME/.claude/state/scout-violations.log" ] \
    || fail "Test E: production log at ~/.claude/state/scout-violations.log was written during the smoke test (SCOUT_VIOLATIONS_LOG override is broken or ineffective)"
[ ! -f "$HOME/.claude/state/scout-violations.log.processing" ] \
    || fail "Test E: production log.processing was created during the smoke test"

unset SCOUT_VIOLATIONS_LOG
rm -f "$TMP_LOG" "$TMP_LOG.processing"

echo "PASS: all 5 hook wrapper smoke tests green"
exit 0
