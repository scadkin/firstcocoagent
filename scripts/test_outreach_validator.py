"""
Unit tests for tools.outreach_client.validate_sequence_inputs.

Zero API calls. Zero fixtures. Runs in <1 second.

Covers every Session 59 failure mode that's now code-enforceable, plus a
positive "clean cold sequence" case and a "hot lead override" case.

Run:
    cd /Users/stevenadkins/Code/Scout && python3 scripts/test_outreach_validator.py
"""
import sys
import os

# Ensure repo root is on path so we import from tools/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from tools.outreach_client import validate_sequence_inputs  # noqa: E402


# ─────────────────────────────────────────────
# Clean baseline cold sequence — reused by negative tests with overrides
# ─────────────────────────────────────────────

MEETING_LINK = "https://hello.codecombat.com/c/steven/t/130"
SCHOOLS_URL = "https://www.codecombat.com/schools"


def _clean_steps() -> list[dict]:
    """A clean 5-step cold diocesan sequence that passes all guards."""
    return [
        {
            "subject": "CS curriculum across your schools",
            "body_html": (
                f"{{{{first_name}}}}, a quick note about "
                f'<a href="{SCHOOLS_URL}">codecombat.com/schools</a>. '
                "Worth sending over a quick overview?"
            ),
            "interval_seconds": 300,
        },
        {
            "subject": "No CS background needed",
            "body_html": (
                f"{{{{first_name}}}}, CodeCombat is turn-key so teachers without a coding "
                f'background can run it day one. More at <a href="{SCHOOLS_URL}">codecombat.com/schools</a>.'
            ),
            "interval_seconds": 432000,
        },
        {
            "subject": "Grab 15 min",
            "body_html": (
                f"{{{{first_name}}}}, if you want to see this in action, "
                f'<a href="{MEETING_LINK}">grab time here</a>.'
            ),
            "interval_seconds": 518400,
        },
        {
            "subject": "Bobby Duke Middle School data",
            "body_html": (
                "{{first_name}}, happy to share efficacy data from Bobby Duke Middle School, "
                "one of our strongest case studies."
            ),
            "interval_seconds": 604800,
        },
        {
            "subject": "Leaving this with you",
            "body_html": (
                "{{first_name}}, last note. If CS ever becomes a priority, "
                f'<a href="{MEETING_LINK}">I am easy to find</a>.'
            ),
            "interval_seconds": 691200,
        },
    ]


def _clean_kwargs() -> dict:
    return dict(
        name="Archdiocese of Philadelphia — Diocesan Central Office Outreach",
        description="Cold outreach to the central office of Archdiocese of Philadelphia. 5-step graduated cadence.",
        schedule_id=52,
        meeting_link=MEETING_LINK,
        steps=_clean_steps(),
    )


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

def test_accepts_clean_cold_sequence():
    r = validate_sequence_inputs(**_clean_kwargs())
    assert r["passed"], f"clean sequence should pass, got failures: {r['failures']}"
    assert r["failures"] == []
    return "accepts_clean_cold_sequence"


def test_rejects_auto_generated_in_description():
    kw = _clean_kwargs()
    kw["description"] = "Auto-generated via Scout sequence_builder diocesan branch. Campaign link: " + MEETING_LINK
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("banned automation language" in f for f in r["failures"])
    return "rejects_auto_generated_in_description"


def test_rejects_schedule_19_not_in_allowlist():
    kw = _clean_kwargs()
    kw["schedule_id"] = 19
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("not in the allowed schedule IDs" in f for f in r["failures"])
    return "rejects_schedule_19_not_in_allowlist"


def test_rejects_missing_schedule_without_override():
    kw = _clean_kwargs()
    kw["schedule_id"] = None
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("schedule_id is required" in f for f in r["failures"])
    return "rejects_missing_schedule_without_override"


def test_accepts_missing_schedule_with_override():
    kw = _clean_kwargs()
    kw["schedule_id"] = None
    kw["allow_no_schedule"] = True
    r = validate_sequence_inputs(**kw)
    assert r["passed"], f"override should pass, got: {r['failures']}"
    return "accepts_missing_schedule_with_override"


def test_rejects_step3_interval_8640_seconds():
    """The exact Session 59 round 2 bug: 8640 seconds = 2h 24m, not 6 days."""
    kw = _clean_kwargs()
    kw["steps"][2]["interval_seconds"] = 8640
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("below minimum" in f and "8640" in f for f in r["failures"])
    return "rejects_step3_interval_8640_seconds"


def test_rejects_body_with_i_would_love_to():
    kw = _clean_kwargs()
    kw["steps"][0]["body_html"] = kw["steps"][0]["body_html"] + " I'd love to connect."
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("i'd love to" in f.lower() for f in r["failures"])
    return "rejects_body_with_i_would_love_to"


def test_rejects_body_with_em_dash():
    kw = _clean_kwargs()
    kw["steps"][1]["body_html"] = kw["steps"][1]["body_html"] + " \u2014 important note"
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("dash characters" in f for f in r["failures"])
    return "rejects_body_with_em_dash"


def test_rejects_schools_school_by_school():
    kw = _clean_kwargs()
    kw["steps"][0]["body_html"] = "Most diocesan offices are piecing together CS across their schools school by school."
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("schools school by school" in f for f in r["failures"])
    return "rejects_schools_school_by_school"


def test_rejects_one_pager_repeated_in_multiple_steps():
    kw = _clean_kwargs()
    # Clean steps don't mention "one pager" — inject it into multiple steps
    kw["steps"][0]["body_html"] = kw["steps"][0]["body_html"] + " Happy to send a one pager."
    kw["steps"][1]["body_html"] = kw["steps"][1]["body_html"] + " I can send another one pager."
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("'one pager'" in f and "2x" in f for f in r["failures"])
    return "rejects_one_pager_repeated_in_multiple_steps"


def _strip_schools_substring(body: str) -> str:
    """Remove BOTH the URL and the anchor-text occurrence of codecombat.com/schools."""
    return body.replace(SCHOOLS_URL, "https://example.com/other").replace("codecombat.com/schools", "example.com/other")


def test_requires_cc_schools_link_when_flag_set():
    kw = _clean_kwargs()
    # Remove both schools links AND the anchor text
    for step in kw["steps"]:
        step["body_html"] = _strip_schools_substring(step["body_html"])
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("codecombat.com/schools" in f for f in r["failures"]), f"expected codecombat link failure, got: {r['failures']}"
    return "requires_cc_schools_link_when_flag_set"


def test_skips_cc_schools_link_when_flag_disabled():
    kw = _clean_kwargs()
    for step in kw["steps"]:
        step["body_html"] = _strip_schools_substring(step["body_html"])
    kw["require_cc_schools_link"] = False
    r = validate_sequence_inputs(**kw)
    assert r["passed"], f"override should pass, got: {r['failures']}"
    return "skips_cc_schools_link_when_flag_disabled"


def test_requires_meeting_link_when_provided():
    kw = _clean_kwargs()
    # Remove the meeting link from all bodies
    for step in kw["steps"]:
        step["body_html"] = step["body_html"].replace(MEETING_LINK, "https://example.com/cal")
    r = validate_sequence_inputs(**kw)
    assert not r["passed"]
    assert any("meeting_link" in f and "does not appear" in f for f in r["failures"])
    return "requires_meeting_link_when_provided"


def test_hot_lead_override_allows_1_hour_interval():
    """Hot lead sequences legitimately need sub-day intervals."""
    kw = _clean_kwargs()
    kw["min_interval_seconds"] = 3600  # 1 hour
    kw["require_cc_schools_link"] = False
    kw["meeting_link"] = None
    # Remove schools/meeting links + rebuild steps with tight intervals
    kw["steps"] = [
        {"subject": "License request received", "body_html": "{{first_name}}, got your request.", "interval_seconds": 60},
        {"subject": "Confirmed", "body_html": "{{first_name}}, confirming now.", "interval_seconds": 3600},
        {"subject": "Next steps", "body_html": "{{first_name}}, here is what happens next.", "interval_seconds": 7200},
    ]
    r = validate_sequence_inputs(**kw)
    assert r["passed"], f"hot lead override should pass, got: {r['failures']}"
    return "hot_lead_override_allows_1_hour_interval"


# ─────────────────────────────────────────────
# Template reuse tests (S73 — create_sequence supports template_id on a step
# dict to reuse existing Outreach templates instead of creating duplicates.
# Validator must not spuriously fail a template_id-only step that carries
# no subject/body for Scout to inspect.)
# ─────────────────────────────────────────────

def test_accepts_template_id_only_step_in_mixed_sequence():
    """DRE Step 2 is `{template_id: 43784}` only — no body for validator to
    inspect. Validator must accept it without tripping banned-phrase / em-dash
    / body-empty checks."""
    kw = _clean_kwargs()
    # Replace step 2 with a template_id-only step (reuses external template).
    # Clean fixture had cc-schools in step 2 body, so dropping it to a
    # template_id removes one cc-schools hit; add it back on step 3 body so
    # the ≥2-step rule still passes on the own-bodied steps.
    kw["steps"][1] = {"template_id": 43784, "interval_seconds": 432000}
    kw["steps"][2]["body_html"] = kw["steps"][2]["body_html"] + (
        f' More at <a href="{SCHOOLS_URL}">codecombat.com/schools</a>.'
    )
    r = validate_sequence_inputs(**kw)
    assert r["passed"], f"template_id-only step should pass, got failures: {r['failures']}"
    return "accepts_template_id_only_step_in_mixed_sequence"


def test_template_id_step_does_not_count_toward_cc_schools_tally():
    """A template_id-only step's content is invisible to the validator. It
    cannot contribute cc-schools hits even if the external template has the
    link. Enforces the caller-side contract that require_cc_schools_link
    should be set False when reusing templates that host the link."""
    kw = _clean_kwargs()
    # Strip cc-schools from all own-bodied steps + add a template_id-only step.
    for s in kw["steps"]:
        s["body_html"] = s["body_html"].replace(SCHOOLS_URL, "https://www.codecombat.com/")
        s["body_html"] = s["body_html"].replace("codecombat.com/schools", "codecombat.com/")
    kw["steps"][1] = {"template_id": 43784, "interval_seconds": 432000}
    r = validate_sequence_inputs(**kw)
    assert not r["passed"], "should still fail because own-bodied steps have 0 cc-schools hits"
    assert any("codecombat.com/schools" in f for f in r["failures"])
    # Now set require_cc_schools_link=False and confirm pass.
    kw["require_cc_schools_link"] = False
    r2 = validate_sequence_inputs(**kw)
    assert r2["passed"], f"with override should pass, got: {r2['failures']}"
    return "template_id_step_does_not_count_toward_cc_schools_tally"


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

TESTS = [
    test_accepts_clean_cold_sequence,
    test_rejects_auto_generated_in_description,
    test_rejects_schedule_19_not_in_allowlist,
    test_rejects_missing_schedule_without_override,
    test_accepts_missing_schedule_with_override,
    test_rejects_step3_interval_8640_seconds,
    test_rejects_body_with_i_would_love_to,
    test_rejects_body_with_em_dash,
    test_rejects_schools_school_by_school,
    test_rejects_one_pager_repeated_in_multiple_steps,
    test_requires_cc_schools_link_when_flag_set,
    test_skips_cc_schools_link_when_flag_disabled,
    test_requires_meeting_link_when_provided,
    test_hot_lead_override_allows_1_hour_interval,
    test_accepts_template_id_only_step_in_mixed_sequence,
    test_template_id_step_does_not_count_toward_cc_schools_tally,
]


def main() -> int:
    passed = 0
    failed = 0
    for test in TESTS:
        try:
            name = test()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print()
    print(f"{passed} passed, {failed} failed out of {len(TESTS)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
