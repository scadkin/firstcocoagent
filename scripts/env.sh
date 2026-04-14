#!/usr/bin/env bash
# Source this instead of `.env` when you need env vars in a bash shell:
#
#     source scripts/env.sh
#
# Why: .env line 7 (OUTREACH_CLIENT_SECRET) contains a literal single
# quote AND a literal `$`. Those two characters together cannot be
# quoted in any way that works for both bash and python-dotenv at the
# same time — bash single-quoting can't escape inner quotes, bash
# double-quoting expands `$8` as a positional arg, python-dotenv
# doesn't interpret `\$`, and python-dotenv's single-quote parser
# accepts `\'` but bash rejects it.
#
# This shim uses python-dotenv (which is the canonical Scout env
# loader anyway — see scripts/tg_send.py, scripts/ab_research_engine.py,
# etc.) to parse .env correctly, then emits shell-safe `export` lines
# via shlex.quote which bash can eval cleanly. The result: bash sees
# exactly the same values python-dotenv sees.

set -a
eval "$(./.venv/bin/python -c '
from dotenv import dotenv_values
import shlex, sys
values = dotenv_values(".env")
for key, value in values.items():
    if value is None:
        continue
    print(f"export {key}={shlex.quote(value)}")
')"
set +a
