#!/usr/bin/env python3
"""
Clean raw `script` terminal output into a readable markdown transcript.

Usage: python3 clean_transcript.py <raw_file> <output_file>

Strips ANSI escape codes, control characters, and terminal artifacts.
Produces clean, scrollable, searchable markdown.
"""

import re
import sys
from pathlib import Path


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (colors, cursor moves, etc.)."""
    # Standard ANSI escape codes
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # OSC sequences (title setting, etc.)
    text = re.sub(r'\x1b\][^\x07]*\x07', '', text)
    text = re.sub(r'\x1b\][^\x1b]*\x1b\\', '', text)
    # Other escape sequences
    text = re.sub(r'\x1b[()][A-Z0-9]', '', text)
    text = re.sub(r'\x1b[>=<]', '', text)
    text = re.sub(r'\x1b\[\?[0-9;]*[a-zA-Z]', '', text)
    text = re.sub(r'\x1b[78]', '', text)
    # Remaining bare escapes
    text = re.sub(r'\x1b', '', text)
    return text


def strip_control_chars(text: str) -> str:
    """Remove control characters except newline and tab."""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def collapse_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive blank lines into 2."""
    return re.sub(r'\n{4,}', '\n\n\n', text)


def remove_script_wrapper(text: str) -> str:
    """Remove the 'Script started...' and 'Script done...' lines from `script` command."""
    text = re.sub(r'^Script started.*\n', '', text)
    text = re.sub(r'\nScript done.*$', '', text)
    return text


def remove_spinner_lines(text: str) -> str:
    """Remove terminal spinner/progress indicator lines (overwritten lines)."""
    # Lines that are just spinner characters or progress indicators
    text = re.sub(r'^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◑◒◓⣾⣽⣻⢿⡿⣟⣯⣷|/\\-]+ .*$', '', text, flags=re.MULTILINE)
    return text


def clean_transcript(raw_path: str, output_path: str) -> None:
    """Read raw script output, clean it, write markdown."""
    raw = Path(raw_path).read_text(errors='replace')

    # Apply cleaning pipeline
    text = remove_script_wrapper(raw)
    text = strip_ansi(text)
    text = strip_control_chars(text)
    text = remove_spinner_lines(text)
    text = collapse_blank_lines(text)
    text = text.strip()

    # Extract session number from filename if present
    fname = Path(output_path).stem
    header = f"# Scout Session Transcript — {fname}\n\n"

    Path(output_path).write_text(header + text + "\n")
    print(f"Cleaned transcript saved to {output_path}")
    print(f"  Raw size:   {len(raw):,} chars")
    print(f"  Clean size: {len(text):,} chars")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 clean_transcript.py <raw_file> <output_file>")
        sys.exit(1)
    clean_transcript(sys.argv[1], sys.argv[2])
