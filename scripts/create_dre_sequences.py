#!/usr/bin/env python3
"""
create_dre_sequences.py — S73 DRE 13-sequence Outreach upload.

Reads `docs/DRE_13_Sequences_Final_Copy_S72.md` (Steven's locked copy),
builds 13 sequence specs matching the DRE family framework, and creates
them in Outreach via `tools.outreach_client.create_sequence`. All 13
sequences are created DISABLED (Rule 15) — Steven activates manually.

Key behaviors:
- Step 2 of every sequence reuses existing template 43784 ("CodeCombat's
  Comprehensive K-12 Suite" info dump) via the S73-promoted template_id
  feature in create_sequence. No duplicate templates are created.
- Steps 1 / 3 / 4 / 5 / 6 get new templates whose bodies are built from
  the copy file with three transformations:
    1. Em-dash replace: `—` -> `, `  (26 occurrences cleaned per S73 decision)
    2. cc-schools line appended to Step 6 only
    3. Plain-text paragraphs + raw URLs -> HTML (`<br><br>` joins,
       `<a href>` wraps)
- Per-sequence schedule mapping: 53 Teacher Tue-Thu (9), 52 Admin Mon-Thu
  (3), 51 Hot Lead Mon-Fri (1 — LQD-Universal).
- Per-sequence tags: ["dre-2026-spring", "dre-<substrategy>"].
- Validator: require_cc_schools_link=False (template 43784 hosts the
  canonical mention; Steven's copy adds a second via Step 6 append).
- State sidecar at data/dre_2026_spring.state.json supports --resume.

CLI modes:
    --dry-run       Parse + transform + validate. No API POSTs.
    --create        Full run (validate + create in Outreach).
    --only <N>      Run only build-order index N (1..13).
    --resume        Skip sequences already in the state sidecar.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _env import load_env_or_die  # noqa: E402

load_env_or_die(required=[
    "OUTREACH_CLIENT_ID",
    "OUTREACH_CLIENT_SECRET",
    "OUTREACH_REDIRECT_URI",
])

from tools.outreach_client import (  # noqa: E402
    create_sequence,
    delete_sequence,
    validate_sequence_inputs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("create_dre")

# ── Constants ────────────────────────────────────────────────────────────

COPY_FILE = REPO_ROOT / "docs" / "DRE_13_Sequences_Final_Copy_S72.md"
STATE_FILE = REPO_ROOT / "data" / "dre_2026_spring.state.json"

TEMPLATE_ID_STEP_2 = 43784
MEETING_LINK = "https://hello.codecombat.com/c/steven/t/131"
SCHOOLS_URL = "https://www.codecombat.com/schools"
STEP_1_INTERVAL_SEC = 300  # validator requires [1, 600]

# Per-step intervals: 0 / 5 / 6 / 7 / 6 / 5 days with hour+minute variance
# so contacts added together don't compound to the same fire time, and so
# fire-time-of-day drifts across the sequence (schedule still picks the next
# available window; variance breaks batching). All are ≥5-day validator min.
#   Step 2 = 5d + 3h 17m  = 443820
#   Step 3 = 6d + 2h 23m  = 526980
#   Step 4 = 7d + 5h 41m  = 625260
#   Step 5 = 6d + 1h 19m  = 523140
#   Step 6 = 5d + 4h 37m  = 448620
STEP_INTERVALS_SEC = [
    STEP_1_INTERVAL_SEC,
    5 * 86_400 + 3 * 3600 + 17 * 60,
    6 * 86_400 + 2 * 3600 + 23 * 60,
    7 * 86_400 + 5 * 3600 + 41 * 60,
    6 * 86_400 + 1 * 3600 + 19 * 60,
    5 * 86_400 + 4 * 3600 + 37 * 60,
]

# Build order: INT-Universal first as safety net, then biggest TC, then grade
# splits, specialty, non-TC. Source: DRE framework + copy file line 13-27.
# Each entry: (build_index, display_name, slug_for_tags, cohort_size,
#               schedule_id, copy_heading_regex).
BUILD_ORDER: list[tuple[int, str, str, int, int, str]] = [
    (1,  "INT-Universal",         "int-universal",        867,   52, r"^# 5\. INT-Universal"),
    (2,  "TC-Universal-Residual", "tc-universal",         6957,  53, r"^# 1\. TC-Universal-Residual"),
    (3,  "TC-MS",                 "tc-ms",                5452,  53, r"^# 2\. TC-MS"),
    (4,  "TC-HS",                 "tc-hs",                4892,  53, r"^# 3\. TC-HS"),
    (5,  "TC-Elem",               "tc-elem",              4941,  53, r"^# 4\. TC-Elem"),
    (6,  "TC-Virtual",            "tc-virtual",           441,   53, r"^# 8\. TC-Virtual"),
    (7,  "TC-District",           "tc-district",          442,   52, r"^# 7\. TC-District"),
    (8,  "TC-All-Grades",         "tc-all-grades",        126,   53, r"^# 9\. TC-All-Grades"),
    (9,  "LIB",                   "lib",                  633,   53, r"^# 6\. LIB"),
    (10, "LQD-Universal",         "lqd-universal",        407,   51, r"^# 10\. LQD-Universal"),
    (11, "INT-Teacher",           "int-teacher",          404,   53, r"^# 11\. INT-Teacher"),
    (12, "TC-Teacher",            "tc-teacher",           393,   53, r"^# 12\. TC-Teacher"),
    (13, "IT-ReEngage",           "it-reengage",          182,   52, r"^# 13\. IT-ReEngage"),
]

SCHEDULE_NAMES = {51: "Hot Lead Mon-Fri", 52: "Admin Mon-Thurs", 53: "Teacher Tue-Thu"}


# ── Body text → HTML conversion ──────────────────────────────────────────

# Match http(s) URLs not already inside an anchor tag. Greedy match, then
# strip trailing sentence-end punctuation in the substitution callback.
_URL_RE = re.compile(r"(?<!href=\")(?<!>)https?://[^\s<>\"]+")
_URL_TRAILING_PUNCT = ".,;:!?)"


def _wrap_url(match: re.Match) -> str:
    url = match.group(0)
    trailing = ""
    while url and url[-1] in _URL_TRAILING_PUNCT:
        trailing = url[-1] + trailing
        url = url[:-1]
    return f'<a href="{url}">{url}</a>{trailing}'


def body_text_to_html(text: str, preserve_em_dashes: bool = False) -> str:
    """
    Convert a plain-text email body to Outreach-ready HTML.

    - Em dashes -> ", " (comma + space), UNLESS preserve_em_dashes=True.
      S73 rev1 mechanically replaced all em dashes; S73 rev2 preserves them
      in Step 6 after Steven flagged that some replacements broke sentences.
    - Raw URLs -> <a href="url">url</a> (click-tracked in Outreach).
    - Blank-line paragraph separators -> <br><br>.
    - Single newlines inside a paragraph -> space (collapse).
    """
    if not preserve_em_dashes:
        text = text.replace(" \u2014 ", ", ")
        text = text.replace("\u2014 ", ", ")
        text = text.replace(" \u2014", ", ")
        text = text.replace("\u2014", ", ")
        text = text.replace("\u2013", "-")

    # Split on one-or-more blank lines (paragraph breaks).
    paragraphs = re.split(r"\n\s*\n", text.strip())
    html_paragraphs = []
    for p in paragraphs:
        # Collapse intra-paragraph newlines to single spaces.
        flat = re.sub(r"\s*\n\s*", " ", p).strip()
        if not flat:
            continue
        # Wrap URLs as anchor tags. Must happen AFTER flattening so we
        # don't split a URL across a newline boundary.
        flat = _URL_RE.sub(_wrap_url, flat)
        html_paragraphs.append(flat)

    return "<br><br>".join(html_paragraphs)


# Self-test for body_text_to_html. Runs at script entry (cheap, catches
# regressions before any API calls).
def _inline_html_tests() -> None:
    # Em dash replace (surrounded by spaces — common pattern).
    assert body_text_to_html("a — b") == "a, b", body_text_to_html("a — b")
    # Em dash with no surrounding spaces.
    assert body_text_to_html("a—b") == "a, b", body_text_to_html("a—b")
    # URL wrap.
    out = body_text_to_html("See https://codecombat.com/schools for more.")
    assert '<a href="https://codecombat.com/schools">https://codecombat.com/schools</a>' in out, out
    # URL with trailing period must not include the period.
    out = body_text_to_html("See https://codecombat.com/schools.")
    assert '<a href="https://codecombat.com/schools">https://codecombat.com/schools</a>' in out, out
    assert out.endswith("</a>.") or out.endswith(".</a>") or out.endswith("</a>") or out.endswith("</a>.")
    # Paragraph split.
    out = body_text_to_html("first line\n\nsecond line")
    assert out == "first line<br><br>second line", out
    # Intra-paragraph newline collapse.
    out = body_text_to_html("first\nline\n\nsecond")
    assert out == "first line<br><br>second", out
    # Already-anchored URL not re-wrapped (defensive — no anchors exist in
    # our copy but future edits might add them).
    out = body_text_to_html('Link: <a href="https://x.com">x</a> end')
    assert out.count("<a href") == 1, out


# ── Copy file parsing ────────────────────────────────────────────────────

_STEP_BLOCK_RE = re.compile(
    r"^##\s+Step\s+(\d+)\s*[—\-]\s*Interval\s+\d+\s*$(.*?)(?=^##\s+Step\s+\d+|^#\s+\d+\.|^---\s*$)",
    re.MULTILINE | re.DOTALL,
)


def _parse_step_block(block: str) -> dict:
    """Parse a single `## Step N — Interval X` block.

    Returns:
        {"subject": str, "body": str}                for normal steps
        {"template_id": int}                          for `**Template:** ID` steps
    """
    # Template reference step.
    m = re.search(r"^\*\*Template:\*\*\s*(\d+)", block, re.MULTILINE)
    if m:
        return {"template_id": int(m.group(1))}

    # Subject + body step.
    m = re.search(r"^\*\*Subject:\*\*\s*(.+?)$", block, re.MULTILINE)
    if not m:
        raise ValueError(f"step block has no **Subject:** and no **Template:**. Block head: {block[:200]!r}")
    subject = m.group(1).strip()

    # Body = everything after the Subject line, minus trailing whitespace.
    body_start = m.end()
    body = block[body_start:].strip()
    return {"subject": subject, "body": body}


def parse_copy_file() -> dict[str, list[dict]]:
    """
    Parse docs/DRE_13_Sequences_Final_Copy_S72.md into
    {display_name: [step_dict, ...]}.
    """
    text = COPY_FILE.read_text(encoding="utf-8")

    # Split into per-sequence sections keyed by the heading regex.
    sequences: dict[str, list[dict]] = {}
    for _idx, display_name, _slug, _size, _sched, heading_regex in BUILD_ORDER:
        m = re.search(heading_regex, text, re.MULTILINE)
        if not m:
            raise ValueError(f"copy file: heading for {display_name!r} not found via {heading_regex!r}")
        section_start = m.end()
        # Section ends at next `# ` heading at column 0 or at end of file.
        next_section = re.search(r"^#\s+\d+\.\s|^## Pre-activation", text[section_start:], re.MULTILINE)
        section_end = section_start + next_section.start() if next_section else len(text)
        section = text[section_start:section_end]

        # Parse all step blocks in this section.
        step_blocks = list(_STEP_BLOCK_RE.finditer(section))
        if len(step_blocks) != 6:
            raise ValueError(
                f"{display_name!r}: expected 6 step blocks, found {len(step_blocks)}. "
                f"Matched step numbers: {[int(b.group(1)) for b in step_blocks]}"
            )

        steps = []
        for b in step_blocks:
            step_num = int(b.group(1))
            parsed = _parse_step_block(b.group(2))
            parsed["_step_num"] = step_num
            steps.append(parsed)

        # Sort defensively by step number (regex already order-preserving
        # but parse errors can reorder).
        steps.sort(key=lambda s: s["_step_num"])
        sequences[display_name] = steps

    return sequences


# ── Build step dicts for create_sequence ────────────────────────────────

_CC_SCHOOLS_APPEND = (
    "\n\nMore at https://www.codecombat.com/schools."
)

# S73 rev2: Step 6's role-disqualifier paragraph ("If CS and AI aren't on
# the {{company}} roadmap..." / "If CodeCombat isn't the right fit..." /
# etc.) gets swapped for a simple role-check. The regex below finds any
# paragraph containing "take it from there" and swaps the entire paragraph.
# Matches the pattern used across all 13 Step 6 closings in the copy file.
_STEP_6_CLOSING_PARAGRAPH_RE = re.compile(
    r"\n\n[^\n]*?take it from there\.[^\n]*",
    re.MULTILINE,
)
_STEP_6_NEW_CLOSING = (
    "\n\nIf you aren't the right person to speak to, or you've changed roles, "
    "would you connect me with the right contact?"
)


def _rewrite_step_6_closing(body_text: str) -> str:
    """Replace the multi-sentence company-roadmap disqualifier with a
    single-line role-check per S73 rev2."""
    if "take it from there" not in body_text:
        # No known disqualifier pattern — append the role-check instead.
        return body_text + _STEP_6_NEW_CLOSING
    return _STEP_6_CLOSING_PARAGRAPH_RE.sub(_STEP_6_NEW_CLOSING, body_text, count=1)


def build_step_dicts(display_name: str, parsed_steps: list[dict]) -> list[dict]:
    """
    Transform parsed copy steps into the shape create_sequence expects.

    Per-step shape:
      Step 1 -> {subject, body_html, interval=300s}
      Step 2 -> {template_id: 43784, interval=STEP_INTERVALS_SEC[1]}
      Step 3 -> {subject, body_html, interval=STEP_INTERVALS_SEC[2]}
      Step 4 -> {subject, body_html+cc-schools line, interval=STEP_INTERVALS_SEC[3]}
      Step 5 -> {subject, body_html, interval=STEP_INTERVALS_SEC[4]}
      Step 6 -> {subject, body_html (em dashes preserved + closing swapped
                  for role-check per S73 rev2), interval=STEP_INTERVALS_SEC[5]}
    """
    out = []
    for s in parsed_steps:
        step_num = s["_step_num"]
        interval = STEP_INTERVALS_SEC[step_num - 1]

        if "template_id" in s:
            if step_num != 2:
                raise ValueError(f"{display_name}: template_id on non-step-2 ({step_num})")
            out.append({"template_id": s["template_id"], "interval_seconds": interval})
            continue

        body_text = s["body"]
        # cc-schools now on Step 4 (S73 rev2, moved from Step 6).
        if step_num == 4:
            body_text = body_text + _CC_SCHOOLS_APPEND
        # Step 6: swap role-disqualifier paragraph for the role-check,
        # and preserve em dashes in the remaining sequence-specific content
        # (S73 rev2 — Steven flagged broken sentences from rev1's mechanical
        # em-dash-to-comma replace).
        if step_num == 6:
            body_text = _rewrite_step_6_closing(body_text)
            body_html = body_text_to_html(body_text, preserve_em_dashes=True)
        else:
            body_html = body_text_to_html(body_text)

        out.append({
            "subject": s["subject"],
            "body_html": body_html,
            "interval_seconds": interval,
        })
    return out


# ── State sidecar ────────────────────────────────────────────────────────

def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {"created": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"state file {STATE_FILE} unreadable: {e}; starting fresh")
        return {"created": {}}


def _write_state_atomic(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=str(STATE_FILE.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_FILE)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── Main ────────────────────────────────────────────────────────────────

def _dry_run_one(display_name: str, slug: str, cohort_size: int, schedule_id: int,
                  steps: list[dict]) -> tuple[bool, list[str], list[str]]:
    """Run validator on assembled step dicts. Returns (passed, failures, warnings)."""
    name = f"DRE 2026 Spring — {display_name}"
    description = (
        f"Dormant Re-Engage 2026 Spring. Cohort: {display_name}, "
        f"{cohort_size} eligible leads. See project_dre_family_framework.md."
    )
    r = validate_sequence_inputs(
        name=name,
        steps=steps,
        description=description,
        schedule_id=schedule_id,
        meeting_link=MEETING_LINK,
        require_cc_schools_link=False,  # template 43784 hosts canonical mention
        allow_phrases=["15 minutes"],   # calendar-booking CTA, not the "got 15 min?" cliche
        forbid_body_dashes=False,       # S73 rev2: em dashes preserved in Step 6 per Steven
    )
    return r["passed"], r["failures"], r["warnings"]


def _create_one(display_name: str, slug: str, cohort_size: int, schedule_id: int,
                 steps: list[dict]) -> dict:
    """Call create_sequence for one DRE sequence. Returns the result dict."""
    name = f"DRE 2026 Spring — {display_name}"
    description = (
        f"Dormant Re-Engage 2026 Spring. Cohort: {display_name}, "
        f"{cohort_size} eligible leads. See project_dre_family_framework.md."
    )
    tags = ["dre-2026-spring", f"dre-{slug}"]
    result = create_sequence(
        name=name,
        steps=steps,
        description=description,
        tags=tags,
        schedule_id=schedule_id,
        meeting_link=MEETING_LINK,
        require_cc_schools_link=False,
        verify_after_create=True,
        allow_phrases=["15 minutes"],
        forbid_body_dashes=False,
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true", help="Parse + validate only, no API calls")
    grp.add_argument("--create", action="store_true", help="Create all 13 in Outreach")
    grp.add_argument("--delete-all", action="store_true",
                     help="DELETE every sequence ID currently in the state sidecar. "
                          "Clears sidecar afterward. Use before a full --create re-run.")
    ap.add_argument("--only", type=int, default=None, metavar="N",
                    help="Build-order index 1..13; restricts action to that sequence")
    ap.add_argument("--resume", action="store_true",
                    help="Skip sequences already recorded in state sidecar")
    args = ap.parse_args()

    _inline_html_tests()

    if args.only is not None and not (1 <= args.only <= len(BUILD_ORDER)):
        logger.error(f"--only must be 1..{len(BUILD_ORDER)}, got {args.only}")
        return 1

    logger.info(f"Parsing copy file: {COPY_FILE}")
    parsed = parse_copy_file()
    logger.info(f"  Parsed {len(parsed)} sequences")

    state = _read_state()
    already_created = set(state.get("created", {}).keys())

    targets = BUILD_ORDER
    if args.only is not None:
        targets = [t for t in BUILD_ORDER if t[0] == args.only]

    # ── DELETE-ALL ───────────────────────────────────────────
    if args.delete_all:
        created = state.get("created", {})
        if not created:
            logger.info("Nothing to delete — state sidecar is empty.")
            return 0
        for name, info in created.items():
            seq_id = info.get("sequence_id")
            if not seq_id:
                continue
            try:
                delete_sequence(seq_id)
                logger.info(f"  deleted: {name} (was id {seq_id})")
            except Exception as e:
                logger.error(f"  FAILED delete for {name} (id {seq_id}): {e}")
                return 1
            time.sleep(1)
        # Clear sidecar.
        state["created"] = {}
        _write_state_atomic(state)
        logger.info(f"Deleted {len(created)} sequences; cleared state sidecar.")
        return 0

    # ── DRY-RUN ──────────────────────────────────────────────
    if args.dry_run:
        all_passed = True
        for (idx, display_name, slug, cohort, sched, _heading) in targets:
            parsed_steps = parsed[display_name]
            step_dicts = build_step_dicts(display_name, parsed_steps)
            passed, fails, warns = _dry_run_one(display_name, slug, cohort, sched, step_dicts)

            status = "PASS" if passed else "FAIL"
            print(f"[{idx:2d}] {status}  {display_name:<24} cohort={cohort:>5}  "
                  f"schedule={SCHEDULE_NAMES.get(sched, sched)}  "
                  f"steps={len(step_dicts)} (step-2=template-{TEMPLATE_ID_STEP_2})")

            if fails:
                all_passed = False
                for f in fails:
                    print(f"       FAIL: {f}")
            for w in warns:
                print(f"       WARN: {w}")

        return 0 if all_passed else 1

    # ── CREATE ────────────────────────────────────────────────
    if args.create:
        results = []
        for (idx, display_name, slug, cohort, sched, _heading) in targets:
            if args.resume and display_name in already_created:
                logger.info(f"[{idx}] SKIP (already created): {display_name} "
                             f"-> {state['created'][display_name].get('url')}")
                continue

            parsed_steps = parsed[display_name]
            step_dicts = build_step_dicts(display_name, parsed_steps)

            logger.info(f"[{idx}] Creating: {display_name} "
                         f"(cohort={cohort}, schedule={SCHEDULE_NAMES.get(sched, sched)})")
            result = _create_one(display_name, slug, cohort, sched, step_dicts)

            seq_id = result.get("sequence_id")
            if result.get("error") or not seq_id:
                logger.error(f"[{idx}] FAILED: {display_name}: {result.get('error')}")
                if result.get("validation_failures"):
                    for vf in result["validation_failures"]:
                        logger.error(f"    {vf}")
                results.append({"idx": idx, "name": display_name, "error": result.get("error"),
                                 "validation_failures": result.get("validation_failures")})
                # Persist partial state before aborting.
                _write_state_atomic(state)
                return 1

            url = f"https://app.outreach.io/sequences/{seq_id}"
            state["created"][display_name] = {
                "sequence_id": seq_id,
                "url": url,
                "schedule_id": sched,
                "cohort_size": cohort,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "validation_failures": result.get("validation_failures", []),
                "validation_warnings": result.get("validation_warnings", []),
            }
            _write_state_atomic(state)

            logger.info(f"[{idx}] OK: {display_name} -> {url}")
            results.append({"idx": idx, "name": display_name, "url": url,
                             "validation_failures": result.get("validation_failures", []),
                             "validation_warnings": result.get("validation_warnings", [])})

            # Small courtesy sleep between sequences to avoid rate-limit
            # spikes on high-fanout create runs.
            time.sleep(2)

        # Summary table.
        print()
        print("=" * 80)
        print("DRE 2026 Spring — 13-sequence upload summary")
        print("=" * 80)
        for r in results:
            marker = "OK " if "error" not in r else "ERR"
            url = r.get("url") or r.get("error", "")
            vf = len(r.get("validation_failures") or [])
            vw = len(r.get("validation_warnings") or [])
            extra = ""
            if vf:
                extra += f" [VALIDATION_FAILURES={vf}]"
            if vw:
                extra += f" [warnings={vw}]"
            print(f"  [{r['idx']:2d}] {marker}  {r['name']:<24}  {url}{extra}")
        print()
        print(f"State sidecar: {STATE_FILE}")
        print()
        print("All 13 sequences are DISABLED by design (Rule 15). Activate each in the Outreach UI.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
