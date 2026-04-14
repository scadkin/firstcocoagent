"""
Level 2 pre-merge integration check for research engine Round 1 Part 0.

Runs ResearchJob("Waverly School District 145", "NE") once and saves the
result dict to a JSON path passed on the command line. Used by a shell
wrapper that stashes code, runs baseline, unstashes, runs post-fix, diffs.

Not a test runner — just an instrumentation script.

Usage:
    .venv/bin/python scripts/level2_integration_check.py /tmp/waverly_pre_part0.json
"""
import asyncio
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from tools.research_engine import ResearchJob  # noqa: E402


DISTRICT = "Waverly School District 145"
STATE = "NE"


async def _progress(msg: str) -> None:
    print(f"[progress] {msg}", flush=True)


async def main(out_path: str) -> int:
    print(f"Running ResearchJob({DISTRICT!r}, {STATE!r}) -> {out_path}", flush=True)
    job = ResearchJob(DISTRICT, STATE, progress_callback=_progress)
    result = await job.run()

    contacts = result.get("contacts") or []
    condensed = {
        "district_name": result.get("district_name"),
        "state": result.get("state"),
        "total": result.get("total"),
        "with_email": result.get("with_email"),
        "no_email": result.get("no_email"),
        "verified": result.get("verified"),
        "queries_used": result.get("queries_used"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "layers_used": result.get("layers_used"),
        "layer_contact_counts": result.get("layer_contact_counts"),
        "contacts": [
            {
                "first_name": c.get("first_name", ""),
                "last_name": c.get("last_name", ""),
                "title": c.get("title", ""),
                "email": c.get("email", ""),
                "email_confidence": c.get("email_confidence", ""),
                "source_url": c.get("source_url", ""),
            }
            for c in contacts
        ],
    }

    with open(out_path, "w") as f:
        json.dump(condensed, f, indent=2)

    print(
        f"Done: total={condensed['total']} verified={condensed['verified']} "
        f"with_email={condensed['with_email']} queries={condensed['queries_used']} "
        f"elapsed={condensed['elapsed_seconds']}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: level2_integration_check.py <out_path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
