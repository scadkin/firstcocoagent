"""
Offline unit test for tools.outreach_client.export_sequence_for_editing.

Monkeypatches tools.outreach_client.export_sequence to return a canned
dict, so the transform + campaign_file round-trip can be verified without
hitting Outreach OAuth.

Run from repo root:
    .venv/bin/python scripts/test_export_sequence_for_editing.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import tools.outreach_client as outreach_client  # noqa: E402
from tools.campaign_file import load_campaign, parse_campaign  # noqa: E402


FAKE_SEQ = {
    "id": "2013",
    "name": "Archdiocese of Chicago — Diocesan Central Office Outreach",
    "description": "",
    "enabled": True,
    "schedule_id": "52",
    "steps": [
        {
            "id": "s1",
            "order": 1,
            "step_type": "email",
            "interval": 0,
            "name": "Step 1",
            "subject": "Quick note on CS rollout at {{company}}",
            "body_html": "<p>Hi {{first_name}},</p><p>Body one with a <a href=\"https://www.codecombat.com/schools\">link</a>.</p>",
            "body_text": "",
        },
        {
            "id": "s2",
            "order": 2,
            "step_type": "email",
            "interval": 432000,
            "name": "Step 2",
            "subject": "Re: Quick note on CS rollout at {{company}}",
            "body_html": "<p>Following up.</p>",
            "body_text": "",
        },
        {
            "id": "s3",
            "order": 3,
            "step_type": "email",
            "interval": 518400,
            "name": "Step 3",
            "subject": "15 minutes next week?",
            "body_html": "<p>Third try.</p>",
            "body_text": "",
        },
    ],
}


def _check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def _with_monkeypatch(fake_dict):
    original = outreach_client.export_sequence
    outreach_client.export_sequence = lambda sequence_id: fake_dict

    def restore():
        outreach_client.export_sequence = original

    return restore


def test_round_trip_default_role() -> None:
    restore = _with_monkeypatch(FAKE_SEQ)
    try:
        md = outreach_client.export_sequence_for_editing(2013)
    finally:
        restore()

    _check("export contains frontmatter", md.startswith("---\n"))
    _check("export contains variant heading", "## variant: other" in md)
    _check(
        "export preserves subjects",
        "Quick note on CS rollout" in md,
    )
    _check(
        "export preserves link tag as-is",
        "codecombat.com/schools" in md,
    )

    reparsed = parse_campaign(md)
    _check("reparsed slug present", bool(reparsed.slug))
    _check(
        "reparsed has single 'other' variant",
        set(reparsed.variants.keys()) == {"other"},
    )
    variant = reparsed.variants["other"]
    _check("reparsed step count = 3", len(variant.steps) == 3)
    _check(
        "reparsed step 1 subject",
        "Quick note" in variant.steps[0].subject,
    )
    _check(
        "reparsed step 1 interval = 0",
        variant.steps[0].interval_seconds == 0,
    )
    # Step 2: 432_000 seconds = 5 days. Round-trip goes via
    # step_intervals_days which stores `round(seconds/86400)` = 5, so
    # back-to-seconds is 5 * 86400 = 432_000. Exact match expected.
    _check(
        "reparsed step 2 interval = 432000",
        variant.steps[1].interval_seconds == 432_000,
        f"got {variant.steps[1].interval_seconds}",
    )


def test_role_override_and_slug() -> None:
    restore = _with_monkeypatch(FAKE_SEQ)
    try:
        md = outreach_client.export_sequence_for_editing(
            2013,
            role="admin",
            target_role_label="Superintendent",
            slug_override="chicago_export",
        )
    finally:
        restore()

    reparsed = parse_campaign(md)
    _check("slug override honored", reparsed.slug == "chicago_export")
    _check("role override honored", "admin" in reparsed.variants)
    _check(
        "target_role_label honored",
        reparsed.variants["admin"].target_role_label == "Superintendent",
    )


def test_rejects_unknown_role() -> None:
    restore = _with_monkeypatch(FAKE_SEQ)
    try:
        try:
            outreach_client.export_sequence_for_editing(2013, role="janitor")
        except ValueError as e:
            _check("unknown role error", "janitor" in str(e))
            return
        raise AssertionError("expected ValueError for unknown role")
    finally:
        restore()


def test_rejects_empty_steps() -> None:
    fake_empty = dict(FAKE_SEQ)
    fake_empty["steps"] = []
    restore = _with_monkeypatch(fake_empty)
    try:
        try:
            outreach_client.export_sequence_for_editing(2013)
        except ValueError as e:
            _check("empty steps error", "no steps" in str(e))
            return
        raise AssertionError("expected ValueError for empty steps")
    finally:
        restore()


def test_slugify_collapses_repeats() -> None:
    from tools.outreach_client import _slugify

    _check(
        "em-dash + spaces collapse",
        _slugify("Archdiocese of Chicago Schools — Diocesan Outreach")
        == "archdiocese_of_chicago_schools_diocesan_outreach",
    )
    _check(
        "leading + trailing punct stripped",
        _slugify("!!! hello ??? world !!!") == "hello_world",
    )
    _check("empty input → empty", _slugify("") == "")
    _check("digits preserved", _slugify("CUE 2026") == "cue_2026")


def test_html_to_markdown_basics() -> None:
    from tools.outreach_client import _html_to_markdown

    _check(
        "br converts to newline",
        _html_to_markdown("Hi<br>there") == "Hi\nthere",
    )
    _check(
        "anchor converts to markdown link",
        _html_to_markdown(
            '<a href="https://www.codecombat.com/schools">codecombat.com/schools</a>'
        )
        == "[codecombat.com/schools](https://www.codecombat.com/schools)",
    )
    _check(
        "strong/em stripped",
        _html_to_markdown("<strong>bold</strong> <em>italic</em>") == "bold italic",
    )
    _check(
        "html entities decoded",
        _html_to_markdown("you &amp; me") == "you & me",
    )
    _check(
        "triple newlines collapsed to double",
        _html_to_markdown("a<br><br><br><br>b") == "a\n\nb",
    )
    _check("empty input", _html_to_markdown("") == "")


def test_export_renders_anchor_as_markdown_link() -> None:
    fake = dict(FAKE_SEQ)
    fake["steps"] = [
        {
            "id": "s1",
            "order": 1,
            "step_type": "email",
            "interval": 0,
            "subject": "Test",
            "body_html": '<p>Hi {{first_name}},</p><p>Link: <a href="https://www.codecombat.com/schools">codecombat.com/schools</a></p>',
        }
    ]
    restore = _with_monkeypatch(fake)
    try:
        md = outreach_client.export_sequence_for_editing(99)
    finally:
        restore()
    _check(
        "markdown link present in export",
        "[codecombat.com/schools](https://www.codecombat.com/schools)" in md,
    )
    _check("no br tags remaining", "<br" not in md)


TESTS = [
    test_round_trip_default_role,
    test_role_override_and_slug,
    test_rejects_unknown_role,
    test_rejects_empty_steps,
    test_slugify_collapses_repeats,
    test_html_to_markdown_basics,
    test_export_renders_anchor_as_markdown_link,
]


def main() -> int:
    failures: list[str] = []
    for fn in TESTS:
        try:
            fn()
            print(f"ok    {fn.__name__}")
        except Exception as e:
            failures.append(f"{fn.__name__}: {e}")
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()

    print()
    print(f"{len(TESTS) - len(failures)}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
