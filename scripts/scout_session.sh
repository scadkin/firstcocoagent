#!/bin/bash
#
# Scout Session Launcher
# Automatically captures the full terminal session and cleans it up when done.
#
# Usage: scout [session_number]
#   e.g., scout 36
#   If no number given, auto-increments from the last session file.
#
# What it does:
#   1. Starts invisible terminal recording
#   2. Launches Claude Code in the Scout project directory
#   3. When you /exit Claude Code, auto-cleans the transcript
#   4. Saves a readable markdown file to docs/sessions/
#
# The end-of-session routine inside Claude Code handles the git commit
# of the transcript (along with CLAUDE.md, SCOUT_PLAN.md, etc.)
# This script just ensures the raw capture and cleanup happen.
#

SCOUT_DIR="/Users/stevenadkins/Code/Scout"
SESSIONS_DIR="$SCOUT_DIR/docs/sessions"
SCRIPTS_DIR="$SCOUT_DIR/scripts"
RAW_DIR="$SESSIONS_DIR/.raw"

# Create dirs if needed
mkdir -p "$SESSIONS_DIR" "$RAW_DIR"

# Determine session number
if [ -n "$1" ]; then
    SESSION_NUM="$1"
else
    # Auto-detect: find highest existing session number and increment
    LAST=$(ls "$SESSIONS_DIR"/session_*.md 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
    if [ -n "$LAST" ]; then
        SESSION_NUM=$((LAST + 1))
    else
        SESSION_NUM=36
    fi
fi

# Safety check: warn if transcript already exists (prevents accidental overwrite)
if [ -f "$SESSIONS_DIR/session_${SESSION_NUM}.md" ]; then
    echo "WARNING: session_${SESSION_NUM}.md already exists!"
    echo ""
    # Auto-bump to next available number
    while [ -f "$SESSIONS_DIR/session_${SESSION_NUM}.md" ]; do
        SESSION_NUM=$((SESSION_NUM + 1))
    done
    echo "Auto-corrected to Session $SESSION_NUM"
    echo ""
fi

RAW_FILE="$RAW_DIR/session_${SESSION_NUM}_raw.txt"
CLEAN_FILE="$SESSIONS_DIR/session_${SESSION_NUM}.md"

# Export paths so Claude Code can find them during end-of-session
export SCOUT_SESSION_NUM="$SESSION_NUM"
export SCOUT_RAW_TRANSCRIPT="$RAW_FILE"
export SCOUT_CLEAN_TRANSCRIPT="$CLEAN_FILE"

echo "========================================="
echo "  Scout Session $SESSION_NUM"
echo "  Transcript: docs/sessions/session_${SESSION_NUM}.md"
echo "========================================="
echo ""

# Use script to capture everything, running claude in the Scout directory
# -q = quiet (no "Script started" message in terminal)
# When claude exits, script exits, then we clean up
script -q "$RAW_FILE" /bin/zsh -c "cd '$SCOUT_DIR' && SCOUT_SESSION_NUM=$SESSION_NUM SCOUT_RAW_TRANSCRIPT='$RAW_FILE' SCOUT_CLEAN_TRANSCRIPT='$CLEAN_FILE' claude"

echo ""
echo "Cleaning transcript..."

# Clean the raw output into readable markdown
python3 "$SCRIPTS_DIR/clean_transcript.py" "$RAW_FILE" "$CLEAN_FILE"

echo ""
echo "Session $SESSION_NUM transcript saved: $CLEAN_FILE"
echo ""

# Check if Claude already committed the transcript (during end-of-session routine)
cd "$SCOUT_DIR"
if git status --porcelain "$CLEAN_FILE" 2>/dev/null | grep -q .; then
    # Transcript exists but wasn't committed (session ended abruptly or skipped end-of-session)
    echo "Note: Transcript wasn't committed during the session."
    echo "Auto-committing now..."
    git add "$CLEAN_FILE"
    git commit -m "Add Session $SESSION_NUM transcript (auto-saved on exit)"
    echo "Done."
else
    echo "Transcript already committed during end-of-session routine."
fi
