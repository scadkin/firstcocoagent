#!/usr/bin/env python3
"""
Clean raw `script` terminal output into a readable markdown transcript.

Usage:
  python3 clean_transcript.py <raw_file> <output_file>              # full cleaned transcript
  python3 clean_transcript.py <raw_file> <output_file> --convo      # conversation only (no tools/code)

Modes:
  Default:  Strips ANSI, spinners, progress bars, UI chrome. Keeps tool calls and code output.
  --convo:  Just your words and Claude's responses. No tool calls, code blocks, file reads,
            or internal noise. Like reading a chat log.
"""

import re
import sys
from pathlib import Path


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences, replacing them with a space
    to prevent words from smooshing together."""
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', ' ', text)
    text = re.sub(r'\x1b\[\?[0-9;]*[a-zA-Z]', ' ', text)
    text = re.sub(r'\x1b\].*?(?:\x07|\x1b\\)', ' ', text, flags=re.DOTALL)
    text = re.sub(r'\x1b[()][A-Z0-9]', '', text)
    text = re.sub(r'\x1b[>=<]', '', text)
    text = re.sub(r'\x1b[78]', '', text)
    text = re.sub(r'\x1bP.*?\x1b\\', '', text, flags=re.DOTALL)
    text = re.sub(r'\x1b', '', text)
    text = re.sub(r' {2,}', ' ', text)
    return text


def strip_control_chars(text: str) -> str:
    """Remove control characters except newline and tab."""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


SPINNER_CHARS = r'[✻✶✳✢·*⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◑◒◓⣾⣽⣻⢿⡿⣟⣯⣷]'


def is_ui_junk(stripped: str) -> bool:
    """Return True if a line is terminal UI noise (spinners, progress, chrome)."""
    # Empty
    if not stripped:
        return False

    # Spinner/thinking animation — Claude uses random words (Mulling, Gallivanting, etc.)
    stripped_nospace = re.sub(r'\s+', '', stripped)
    if re.match(rf'^{SPINNER_CHARS}?[A-Z][a-zéè]+(?:ing|ed)\b', stripped_nospace):
        return True
    if re.match(rf'^{SPINNER_CHARS}?\s*[A-Z]\s*[a-zéè]+\s*(?:ing|ed)\b', stripped) and len(stripped) < 80:
        return True
    if re.match(rf'^{SPINNER_CHARS}\s+[A-Z][a-z]+\w*[….]', stripped):
        return True

    # Spinner chars alone
    if re.match(r'^[✻✶✳✢·*⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◑◒◓⏺]+$', stripped):
        return True

    # Character-by-character animation fragments
    if len(stripped) <= 20:
        no_spaces = stripped.replace(' ', '')
        if len(no_spaces) <= 12 and not re.search(r'[a-z]{4,}', no_spaces):
            if re.match(r'^[✻✶✳✢·*⏺]?\s*[A-Za-z\d…↓↑]+$', no_spaces):
                return True

    # Partial word buildup: "· Mul ling…", "✢ l g"
    if re.match(rf'^{SPINNER_CHARS}?\s+\w{{1,3}}(\s+\w{{1,3}}){{1,5}}\s*…?$', stripped):
        return True

    # Bare symbols from animation
    if re.match(r'^…\s*\d*$', stripped):
        return True
    if stripped in ('↓', '↑', '❯'):
        return True

    # Progress bars
    if re.match(r'^[\[▓░█▒]*\s*\d*%?\s*$', stripped):
        return True
    if '░░░░' in stripped or '▓▓' in stripped:
        return True

    # Status bar (model info)
    if re.match(r'^\[?Opus\s*4', stripped):
        return True
    if re.match(r'.*\(1M\s*context\).*[░▓%]', stripped):
        return True

    # "accept edits" UI
    if 'accept' in stripped and 'edit' in stripped and ('shift+tab' in stripped or 'cycle' in stripped):
        return True
    if stripped.startswith('⏵⏵'):
        return True

    # Horizontal rules
    if re.match(r'^[─━]{20,}$', stripped):
        return True

    # Claude Code chrome
    if re.match(r'^[▐▛▜▝▘█]+', stripped):
        return True
    if 'ClaudeCode' in stripped.replace(' ', '') and ('v2.' in stripped or 'v1.' in stripped):
        return True

    # UI hints
    if re.match(r'^\(ctrl\+[a-z] to (expand|run in background)\)$', stripped):
        return True

    # Pasted text indicators
    if re.match(r'^(\[?Pasting text|Pasted\s*text|\[Pastedtext|\[Pasted text).*$', stripped, re.IGNORECASE):
        return True

    # Recalling memory
    if re.match(r'^,?\s*recalling \d+ memor', stripped):
        return True

    # Timing stats
    if re.match(r'^\([\d.]+[sm]\s*·\s*[↑↓][\d.]+k tokens?\)$', stripped):
        return True
    if re.match(r'^·?\s*\w+…?\s*\([\d.]+[sm]\s*·\s*[↑↓]', stripped):
        return True

    # Bare numbers
    if re.match(r'^\d{1,3}$', stripped):
        return True

    # Config display
    if re.match(r'^.*medium.*·.*/effort.*$', stripped):
        return True

    # Terminal mode remnants
    if re.match(r'^\[>[0-9;]*[a-zA-Z]', stripped):
        return True

    # Tool animation artifacts
    if re.match(r'^(Read|Srch|Search|Grep|Glob|Write|Edit|Bash)\(', stripped) and len(stripped) < 100:
        if '⎿' not in stripped:
            no_spaces = stripped.replace(' ', '')
            if ')' in no_spaces and no_spaces.endswith(')'):
                return True

    # Repeated tool file paths
    if re.match(r'^(tools|agent|scripts)/\S+\)$', stripped):
        return True

    # "+N more" lines
    if re.match(r'^\+\d+ more.*\(ctrl\+', stripped):
        return True

    return False


def is_tool_or_code(stripped: str) -> bool:
    """Return True if a line is tool call output, code, or internal Claude noise.
    Used only in --convo mode."""
    # Tool call headers: "⏺ Read(...)", "⏺ Write(...)", "⏺ Bash(...)", etc.
    if re.match(r'^⏺\s*(Read|Write|Edit|Bash|Grep|Glob|Explore|Agent|Search|Searched|Recalled)\b', stripped):
        return True

    # Tool output markers
    if re.match(r'^\s*⎿', stripped):
        return True

    # "Read N file(s)" / "Searched for N pattern(s)" / "wrote N memories" summary lines
    if re.match(r'^(Read|Searched|Wrote|Updated|Created|Recalled|Deleted)\s+\d+', stripped):
        return True
    if re.match(r'^Read \d+ files?', stripped):
        return True
    if re.match(r'^Searched for \d+ pattern', stripped):
        return True

    # Tool status lines
    if re.match(r'^⏺\s*(Reading|Searching|Writing|Running|Updating|Creating)\s', stripped):
        return True
    if re.match(r'^Running\s*…', stripped):
        return True

    # "Done (N tool uses · Nk tokens · Ns)" lines
    if re.match(r'^Done\s*\(\d+ ', stripped):
        return True

    # File path lines (from tool output)
    if re.match(r'^\s+\d+[→│]\s', stripped):  # Line-numbered code output
        return True

    # Git output
    if re.match(r'^\s*(Saved working directory|HEAD is now|Switched to)', stripped):
        return True

    # Code fences
    if re.match(r'^```', stripped):
        return True

    # Indented code blocks (4+ spaces or tab, common in tool output)
    # Be careful not to strip indented conversation text (like numbered lists)
    if re.match(r'^\s{6,}\S', stripped) and not re.match(r'^\s+\d+\.?\s', stripped):
        return True

    # Agent spawning
    if re.match(r'^⏺\s*(claude-code-guide|general-purpose|Explore|Plan)\(', stripped):
        return True

    # "ctrl+o to expand" with context
    if 'ctrl+o to expand' in stripped:
        return True

    # Warnings / Python tracebacks
    if re.match(r'^\s*(WARNING|warnings\.warn|Traceback|File "|/Users/)', stripped):
        return True
    if re.match(r'^\s+\w+Error:', stripped):
        return True

    # "Wrote N lines to file" tool confirmations
    if re.match(r'^\s*Wrote \d+ lines to ', stripped):
        return True

    # Diff-style lines (from Edit tool)
    if re.match(r'^\s*(Added|Removed|Changed) \d+ lines?', stripped):
        return True

    # "(thinking)" and "(thought for Ns)" lines
    if re.match(r'^[✻✶✳✢·*]?\s*\(think', stripped):
        return True
    if re.match(r'^\(thought for ', stripped):
        return True

    # Permission prompt UI ("Esc to cancel · Tab to amend · ctrl+e to explain")
    if 'Esc to cancel' in stripped or 'Tab to amend' in stripped:
        return True

    # "Bash command" / "Command contains" labels from permission prompts
    if re.match(r'^(Bash command|Command contains|Allow once|Allow always)', stripped):
        return True

    # Tip lines
    if re.match(r'^Tip:', stripped):
        return True

    # "ctrl+s to stash" and similar hints
    if re.match(r'^ctrl\+', stripped):
        return True

    # Bare "?" from prompt UI
    if stripped == '?':
        return True

    # Short debris fragments (1-3 chars that aren't real words)
    if len(stripped) <= 4 and not re.match(r'^(OK|No|Yes|Hi)\b', stripped, re.IGNORECASE):
        if re.match(r'^[a-z\s]+$', stripped):
            return True

    # "Bash" / "Read" / etc. on their own (command type labels)
    if stripped in ('Bash', 'Read', 'Write', 'Edit', 'Grep', 'Glob', 'Search'):
        return True

    # Search/grep pattern lines leaking from tool calls
    if re.match(r'^(S\s*r\s*ch|R\s*d)\s*\(', stripped):
        return True
    if re.match(r'^[a-zA-Z_|]+",?\s*p\s*[ta]\s*h:', stripped):
        return True
    # Tool call patterns with spaces from ANSI stripping: "Write ( scripts/..." , "Read ( file )"
    if re.match(r'^(Write|Read|Edit|Bash|Grep|Glob|Search)\s*\(', stripped):
        return True

    # File paths (tool output)
    if re.match(r'^(tools|agent|scripts|src|lib|tests?|docs|config)/\S', stripped):
        return True

    # Shell command echoes (from Bash tool)
    if re.match(r'^(echo |cat |grep |ls |cd |git |python3? |pip |npm |chmod |mkdir |curl )', stripped):
        return True

    # Error/warning output
    if re.match(r'^Error: Exit code', stripped):
        return True
    if re.match(r'^ERROR:', stripped):
        return True
    if 'bug fixes on a best-effort basis' in stripped:
        return True
    if 'Please upgrade your Python version' in stripped:
        return True

    # Token/timing stats leaking through
    if re.match(r'^\d+[sm]\s*·\s*[↑↓]', stripped):
        return True
    if re.match(r'^\d+\s*0s\s*·\s*[↑↓]', stripped):
        return True

    # Code lines (import, def, class, etc.)
    if re.match(r'^\d+\s+(import |from |def |class |#|""")', stripped):
        return True
    if re.match(r'^import ', stripped):
        return True

    # Spaced-out debris from ANSI stripping (short nonsense like "an fe", "tc in 1", "ch ng", "buidlin")
    if len(stripped) <= 20:
        words = stripped.split()
        if all(len(w) <= 4 for w in words) and len(words) >= 2:
            if not re.match(r'^(I |OK |No |Oh |So |Do |If |We |It |My |Go |On )', stripped):
                return True
        # Single nonsense fragment
        if len(stripped) <= 10 and re.match(r'^[a-z]+$', stripped) and not stripped in (
            'ok', 'no', 'yes', 'hi', 'hey', 'sure', 'done', 'good', 'fine', 'cool', 'nice', 'right', 'wait',
            'what', 'why', 'how', 'when', 'where', 'which', 'that', 'this', 'here', 'there',
        ):
            return True

    # Lines that are just a file/path with no context
    if re.match(r'^\.?(env|gitignore|git|node_modules|__pycache__)(\s.*)?$', stripped):
        return True

    # Grep/search query patterns leaking: "pattern: ..." or "C4|Audit|..."
    if re.match(r'^[A-Z_|]+",?\s*(pa|p)\s*[th]', stripped):
        return True
    if re.match(r'^[a-zA-Z_]+\|[a-zA-Z_]+', stripped) and len(stripped) < 60:
        return True

    # Mangled search patterns with spaces: 'C4|Audit|TAB_C4 AUDIT", pa h: "tools")'
    if re.match(r'.*",\s*pa?\s*[th].*:\s*"', stripped) and len(stripped) < 80:
        return True

    # "Check if env vars" and similar Claude internal short narration
    if re.match(r'^Check if ', stripped):
        return True

    # Code comment/docstring lines leaking
    if re.match(r'^\d+\s+', stripped) and len(stripped) < 80:
        # Numbered code lines like "3 Quick spot-check...", "7 Requires:..."
        if re.match(r'^\d+\s+[A-Z#"\']', stripped):
            return True

    # Orphan parens, brackets from code output
    if stripped in (')', '(', '{', '}', '];', '};'):
        return True

    # Single period or dot
    if stripped == '.':
        return True

    return False


def clean_lines(text: str, convo_mode: bool = False) -> str:
    """Line-by-line cleaning. In convo mode, also strips tools and code."""
    lines = text.split('\n')
    cleaned = []
    in_code_block = False
    skip_indented = False  # For skipping tool output blocks

    for line in lines:
        stripped = line.strip()

        # Always skip UI junk
        if stripped and is_ui_junk(stripped):
            continue

        if not stripped:
            if not in_code_block:
                skip_indented = False  # Reset on blank line
            cleaned.append('')
            continue

        if convo_mode:
            # Track code fences
            if re.match(r'^```', stripped):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Skip tool/code lines
            if is_tool_or_code(stripped):
                skip_indented = True  # Following indented lines are likely tool output
                continue

            # If we're in a tool output block, skip indented continuation lines
            if skip_indented and line.startswith('  '):
                continue

            # A non-indented, non-tool line resets the skip
            if not line.startswith('  '):
                skip_indented = False

        # Clean up trailing whitespace
        line = line.rstrip()
        cleaned.append(line)

    return '\n'.join(cleaned)


def collapse_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive blank lines into 1."""
    return re.sub(r'\n{3,}', '\n\n', text)


def remove_script_wrapper(text: str) -> str:
    """Remove the 'Script started...' and 'Script done...' lines."""
    text = re.sub(r'^Script started.*\n', '', text)
    text = re.sub(r'\nScript done.*$', '', text)
    return text


def fix_smooshed_text(text: str) -> str:
    """Fix text that lost spaces due to terminal escape code stripping."""
    lines = text.split('\n')
    fixed = []
    for line in lines:
        if re.search(r'[a-z][A-Z][a-z].*[a-z][A-Z]', line):
            line = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', line)
            line = re.sub(r'(\w)—(\w)', r'\1 — \2', line)
            line = re.sub(r'(\w)➕(\w)', r'\1 ➕ \2', line)
        fixed.append(line)
    return '\n'.join(fixed)


def deduplicate_lines(text: str) -> str:
    """Remove consecutive duplicate lines (from terminal redraws)."""
    lines = text.split('\n')
    deduped = []
    prev = None
    repeat_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == prev and stripped:
            repeat_count += 1
            if repeat_count >= 2:
                continue  # Skip 3rd+ consecutive duplicate
        else:
            repeat_count = 0
        prev = stripped
        deduped.append(line)
    return '\n'.join(deduped)


def final_cleanup(text: str) -> str:
    """Final pass to catch remaining artifacts."""
    # Short random char debris
    text = re.sub(r'^\s*[a-z]{1,3}\s*$', '', text, flags=re.MULTILINE)

    # Orphaned tool markers
    text = re.sub(r'^\s*⎿\s*$', '', text, flags=re.MULTILINE)

    # "Reading N file(s)…" status
    text = re.sub(r'^\s*⏺?\s*Reading \d+ files?….*$', '', text, flags=re.MULTILINE)

    # Recalling memory status
    text = re.sub(r'^,?\s*recalling \d+ memor.*$', '', text, flags=re.MULTILINE)

    # Fix smooshed text
    text = fix_smooshed_text(text)

    # Deduplicate repeated lines
    text = deduplicate_lines(text)

    # Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def format_conversation(text: str) -> str:
    """In convo mode, add clear markers for who's speaking."""
    lines = text.split('\n')
    formatted = []
    for line in lines:
        stripped = line.strip()
        # User prompts start with ❯
        if stripped.startswith('❯'):
            formatted.append('')
            formatted.append('---')
            formatted.append('')
            formatted.append(f'**You:** {stripped[1:].strip()}')
        # Claude responses start with ⏺
        elif stripped.startswith('⏺'):
            formatted.append('')
            formatted.append(f'**Claude:** {stripped[1:].strip()}')
        else:
            formatted.append(line)
    return '\n'.join(formatted)


def clean_transcript(raw_path: str, output_path: str, convo_mode: bool = False) -> None:
    """Read raw script output, clean it, write markdown."""
    raw = Path(raw_path).read_text(errors='replace')

    # Apply cleaning pipeline
    text = remove_script_wrapper(raw)
    text = strip_ansi(text)
    text = strip_control_chars(text)
    text = clean_lines(text, convo_mode=convo_mode)
    text = collapse_blank_lines(text)
    text = final_cleanup(text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    if convo_mode:
        text = format_conversation(text)
        text = re.sub(r'\n{3,}', '\n\n', text)

    text = text.strip()

    # Header
    fname = Path(output_path).stem
    mode_label = " (Conversation)" if convo_mode else ""
    header = f"# Scout Session Transcript{mode_label} — {fname}\n\n"

    Path(output_path).write_text(header + text + "\n")

    raw_lines = raw.count('\n')
    clean_lines_count = text.count('\n')
    print(f"Cleaned transcript saved to {output_path}")
    print(f"  Raw:   {raw_lines:,} lines / {len(raw):,} chars")
    print(f"  Clean: {clean_lines_count:,} lines / {len(text):,} chars")
    print(f"  Removed {raw_lines - clean_lines_count:,} lines ({100 * (raw_lines - clean_lines_count) // max(raw_lines, 1)}%)")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 clean_transcript.py <raw_file> <output_file> [--convo]")
        sys.exit(1)

    convo = '--convo' in sys.argv
    clean_transcript(sys.argv[1], sys.argv[2], convo_mode=convo)
