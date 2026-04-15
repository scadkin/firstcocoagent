"""Shared .env loader for scripts/ — replaces the raw-KeyError / FileNotFoundError
pattern that every standalone script hand-coded.

Usage inside a sibling script:

    from _env import load_env_or_die  # scripts/ is on sys.path when running
    load_env_or_die(required=["SERPER_API_KEY", "ANTHROPIC_API_KEY"])

On failure (missing file, parse error, missing required var) this raises
SystemExit with a human-readable message naming the exact problem. Never
returns a partial success.

The audit theme this closes: "scripts/*.py crash on missing .env with raw
KeyError / FileNotFoundError and no helpful message". Each buggy script
either (a) did `Path(".env").read_text()` which raises FileNotFoundError
with a stack trace, or (b) wrapped `load_dotenv()` in `try/except: pass`
and silently proceeded to a KeyError on the first `os.environ["KEY"]`.
Both are operator-hostile — the fix makes the operator see exactly what's
missing and where to look.

Not using python-dotenv's load_dotenv because repo/.env line 7 has a
value containing a literal single quote that confuses python-dotenv's
shell-heuristic parser in some environments (see memory/
reference_env_var_quoting_gotcha.md). Manual parse matches the style
already used by f4_serper_replay.py and fetch_csta_roster.py so every
script converges on one pattern.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Sequence

# Repo root = scripts/../
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = REPO_ROOT / ".env"


def _die(msg: str) -> None:
    """Print to stderr and SystemExit with code 2. Never returns."""
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_env_or_die(
    required: Optional[Sequence[str]] = None,
    env_path: Optional[Path] = None,
) -> None:
    """Load .env into os.environ; die with a helpful message on any failure.

    Args:
        required: optional list of env var names that MUST be set and
            non-empty after loading. If any are missing, dies with a
            specific list of what's missing.
        env_path: optional override for the .env file location. Defaults
            to <repo root>/.env.

    Never returns a partial success — either everything loads or
    SystemExit(2) fires with a message naming the exact problem.
    """
    path = env_path or DEFAULT_ENV_PATH

    if not path.exists():
        _die(
            f"{path} not found.\n"
            f"  This script needs the Scout repo-root .env file with Google, "
            f"Serper, Anthropic, and/or Outreach credentials.\n"
            f"  Fix: run the script from the Scout repo root, OR copy the "
            f"relevant secrets into {path}."
        )

    try:
        lines = path.read_text().splitlines()
    except Exception as e:
        _die(f"failed to read {path}: {e}")

    parsed = 0
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, _, v = ln.partition("=")
        k = k.strip()
        # Strip surrounding single OR double quotes from value. Matches the
        # pattern already used by f4_serper_replay.py / fetch_csta_roster.py.
        v = v.strip().strip("'\"")
        os.environ.setdefault(k, v)
        parsed += 1

    if parsed == 0:
        _die(f"{path} exists but contained zero KEY=value lines after parsing.")

    if required:
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            _die(
                f"required env vars not set: {missing}\n"
                f"  Check {path} and make sure these keys are present AND "
                f"non-empty.\n"
                f"  Reminder: this helper uses os.environ.setdefault(), so "
                f"values already in the shell environment take precedence "
                f"over the .env file."
            )
