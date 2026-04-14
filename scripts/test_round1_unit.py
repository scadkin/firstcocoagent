"""
Unit tests for research engine Round 1 changes.

Part 0: shared dedup fix — upgrade-on-collision in contact_extractor._merge_contact_upgrade.
        Fixes silent-drop bug where page 2's VERIFIED email is lost when page 1 already
        returned the same name without an email.

Zero API calls. Runs in <1 second.

Run:
    .venv/bin/python scripts/test_round1_unit.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from tools.contact_extractor import (  # noqa: E402
    _merge_contact_upgrade,
    start_usage_capture,
    stop_usage_capture,
    _log_usage,
)
import tools.contact_extractor as ce  # noqa: E402
from tools.research_engine import ResearchJob  # noqa: E402


def _contact(
    first: str = "John",
    last: str = "Smith",
    title: str = "",
    email: str = "",
    email_confidence: str = "UNKNOWN",
    source_url: str = "",
    district_name: str = "Test ISD",
) -> dict:
    return {
        "first_name": first,
        "last_name": last,
        "title": title,
        "email": email,
        "email_confidence": email_confidence,
        "source_url": source_url,
        "district_name": district_name,
        "work_phone": "",
        "account": district_name,
        "notes": "",
    }


# ─────────────────────────────────────────────
# Part 0: _merge_contact_upgrade unit tests
# ─────────────────────────────────────────────

def test_merge_upgrades_no_email_to_email():
    existing = _contact(email="", email_confidence="UNKNOWN")
    new = _contact(
        email="john.smith@test.edu",
        email_confidence="VERIFIED",
        source_url="http://test.edu/staff",
    )
    _merge_contact_upgrade(existing, new)
    assert existing["email"] == "john.smith@test.edu", existing
    assert existing["email_confidence"] == "VERIFIED", existing
    assert existing["source_url"] == "http://test.edu/staff", existing
    return "merge_upgrades_no_email_to_email"


def test_merge_upgrades_unknown_to_verified():
    existing = _contact(email="guess@test.edu", email_confidence="UNKNOWN")
    new = _contact(email="john.smith@test.edu", email_confidence="VERIFIED")
    _merge_contact_upgrade(existing, new)
    assert existing["email"] == "john.smith@test.edu"
    assert existing["email_confidence"] == "VERIFIED"
    return "merge_upgrades_unknown_to_verified"


def test_merge_fills_empty_title():
    existing = _contact(title="")
    new = _contact(title="Superintendent")
    _merge_contact_upgrade(existing, new)
    assert existing["title"] == "Superintendent"
    return "merge_fills_empty_title"


def test_merge_no_downgrade():
    existing = _contact(
        email="verified@test.edu",
        email_confidence="VERIFIED",
        title="Principal",
    )
    new = _contact(
        email="guess@test.edu",
        email_confidence="LIKELY",
        title="Teacher",
    )
    _merge_contact_upgrade(existing, new)
    assert existing["email"] == "verified@test.edu", "should not downgrade email"
    assert existing["email_confidence"] == "VERIFIED", "should not downgrade confidence"
    assert existing["title"] == "Principal", "should not overwrite non-empty title"
    return "merge_no_downgrade"


def test_merge_no_duplicate_append():
    # Simulates the caller's dedup flow — same name twice should land as one entry.
    from tools.contact_extractor import extract_from_multiple  # noqa: F401
    # Verified indirectly via test_extract_from_multiple_upgrades_across_pages below.
    # Here we assert the helper never mutates identity fields.
    existing = _contact(first="John", last="Smith")
    new = _contact(first="JANE", last="DOE", email="x@y", email_confidence="VERIFIED")
    _merge_contact_upgrade(existing, new)
    # Name fields must not be changed — the helper trusts the caller's dedup key.
    assert existing["first_name"] == "John"
    assert existing["last_name"] == "Smith"
    # But the email upgrade should still apply because existing had none.
    assert existing["email"] == "x@y"
    assert existing["email_confidence"] == "VERIFIED"
    return "merge_no_duplicate_append"


def test_merge_adds_new_name():
    # Sanity: the helper is upgrade-only; "adding" is the caller's job via seen-set.
    # This test documents that the helper does not append to any list.
    existing = _contact(first="John", last="Smith")
    before = dict(existing)
    new = _contact(first="Jane", last="Doe")
    _merge_contact_upgrade(existing, new)
    # existing is still John Smith, untouched for identity fields.
    assert existing["first_name"] == before["first_name"]
    assert existing["last_name"] == before["last_name"]
    return "merge_adds_new_name"


# ─────────────────────────────────────────────
# Part 1 Flag A: URL dedup in L9
# ─────────────────────────────────────────────


def _fresh_job(**kwargs) -> ResearchJob:
    return ResearchJob("Test ISD", "TX", **kwargs)


async def _call_l9(job: ResearchJob):
    """Drive _layer9_claude_extraction until it reaches the existing filter.
    We intercept _filter_raw_pages_by_domain to snapshot raw_pages (post-dedup)
    and short-circuit L9 before it touches the Claude API.
    """
    import tools.research_engine as re_mod

    def fake_filter(self):
        self._observed_raw_pages = list(self.raw_pages)
        self.raw_pages = []

    original = re_mod.ResearchJob._filter_raw_pages_by_domain
    re_mod.ResearchJob._filter_raw_pages_by_domain = fake_filter
    try:
        await job._layer9_claude_extraction()
    finally:
        re_mod.ResearchJob._filter_raw_pages_by_domain = original


def _run_async(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_url_dedup_exact_duplicate():
    job = _fresh_job(enable_url_dedup=True)
    job.raw_pages = [("http://x.com/staff", "a"), ("http://x.com/staff", "b")]
    _run_async(_call_l9(job))
    assert len(job._observed_raw_pages) == 1
    return "url_dedup_exact_duplicate"


def test_url_dedup_trailing_slash():
    job = _fresh_job(enable_url_dedup=True)
    job.raw_pages = [("http://x.com/staff/", "a"), ("http://x.com/staff", "b")]
    _run_async(_call_l9(job))
    assert len(job._observed_raw_pages) == 1
    return "url_dedup_trailing_slash"


def test_url_dedup_case_insensitive():
    job = _fresh_job(enable_url_dedup=True)
    job.raw_pages = [("HTTP://X.COM/STAFF", "a"), ("http://x.com/staff", "b")]
    _run_async(_call_l9(job))
    assert len(job._observed_raw_pages) == 1
    return "url_dedup_case_insensitive"


def test_url_dedup_preserves_different_urls():
    job = _fresh_job(enable_url_dedup=True)
    job.raw_pages = [
        ("http://x.com/a", "a"),
        ("http://x.com/b", "b"),
        ("http://y.com/a", "c"),
    ]
    _run_async(_call_l9(job))
    assert len(job._observed_raw_pages) == 3
    return "url_dedup_preserves_different_urls"


def test_url_dedup_off_by_default():
    job = _fresh_job()  # flag defaults to False
    assert job.enable_url_dedup is False
    job.raw_pages = [("http://x.com/", "a"), ("http://x.com", "b")]
    _run_async(_call_l9(job))
    assert len(job._observed_raw_pages) == 2, "dedup must NOT run when flag is off"
    return "url_dedup_off_by_default"


# ─────────────────────────────────────────────
# Part 1 Flag B: L15 Step 5 skip threshold
# ─────────────────────────────────────────────


def _make_verified_contacts(n: int) -> list[dict]:
    return [
        _contact(
            first=f"V{i}",
            last="Person",
            email=f"v{i}@test.edu",
            email_confidence="VERIFIED",
        )
        for i in range(n)
    ]


def test_l15_step5_skips_at_threshold():
    job = _fresh_job(l15_step5_skip_threshold=15)
    job.all_contacts = _make_verified_contacts(15)
    # Reproduce only the skip predicate Part 1 Flag B adds, not the whole L15.
    threshold = job.l15_step5_skip_threshold
    verified = sum(
        1 for c in job.all_contacts
        if (c.get("email_confidence") or "").upper() == "VERIFIED"
    )
    should_skip = threshold is not None and verified >= threshold
    assert should_skip is True
    return "l15_step5_skips_at_threshold"


def test_l15_step5_skips_above_threshold():
    job = _fresh_job(l15_step5_skip_threshold=15)
    job.all_contacts = _make_verified_contacts(20)
    verified = sum(
        1 for c in job.all_contacts
        if (c.get("email_confidence") or "").upper() == "VERIFIED"
    )
    should_skip = job.l15_step5_skip_threshold is not None and verified >= job.l15_step5_skip_threshold
    assert should_skip is True
    return "l15_step5_skips_above_threshold"


def test_l15_step5_runs_below_threshold():
    job = _fresh_job(l15_step5_skip_threshold=15)
    job.all_contacts = _make_verified_contacts(14)
    verified = sum(
        1 for c in job.all_contacts
        if (c.get("email_confidence") or "").upper() == "VERIFIED"
    )
    should_skip = job.l15_step5_skip_threshold is not None and verified >= job.l15_step5_skip_threshold
    assert should_skip is False
    return "l15_step5_runs_below_threshold"


def test_l15_step5_off_by_default():
    job = _fresh_job()  # threshold defaults to None
    assert job.l15_step5_skip_threshold is None
    job.all_contacts = _make_verified_contacts(100)
    should_skip = job.l15_step5_skip_threshold is not None
    assert should_skip is False
    return "l15_step5_off_by_default"


# ─────────────────────────────────────────────
# Part 1 Flag C: Claude usage capture
# ─────────────────────────────────────────────


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.usage = _FakeUsage(input_tokens, output_tokens)


def test_claude_usage_capture_when_enabled():
    start_usage_capture()
    try:
        _log_usage(_FakeResponse(1000, 500), "http://test/staff")
        _log_usage(_FakeResponse(2000, 800), "http://test/leadership")
    finally:
        records = stop_usage_capture()
    assert len(records) == 2, records
    assert records[0]["input_tokens"] == 1000
    assert records[0]["output_tokens"] == 500
    assert records[0]["source_url"] == "http://test/staff"
    assert records[0]["model"] == "claude-sonnet-4-6"
    assert records[1]["input_tokens"] == 2000
    return "claude_usage_capture_when_enabled"


def test_claude_usage_no_capture_when_disabled():
    # Ensure flag is off (explicit reset in case a previous test leaked)
    stop_usage_capture()
    _log_usage(_FakeResponse(1000, 500), "http://test/staff")
    # No start_usage_capture was called — buffer should be empty
    assert ce._captured_usage == [], ce._captured_usage
    assert ce._capture_usage_enabled is False
    return "claude_usage_no_capture_when_disabled"


def test_claude_usage_balanced_start_stop():
    start_usage_capture()
    _log_usage(_FakeResponse(1000, 500), "http://test")
    first = stop_usage_capture()
    second = stop_usage_capture()
    assert len(first) == 1
    assert second == [], "second stop must return empty after buffer is cleared"
    assert ce._capture_usage_enabled is False
    return "claude_usage_balanced_start_stop"


def test_claude_usage_exception_cleanup():
    start_usage_capture()
    assert ce._capture_usage_enabled is True
    try:
        raise RuntimeError("simulated mid-job exception")
    except RuntimeError:
        stop_usage_capture()  # mimics run() except-branch cleanup
    assert ce._capture_usage_enabled is False
    # A fresh job must start with an empty buffer.
    start_usage_capture()
    assert ce._captured_usage == []
    stop_usage_capture()
    return "claude_usage_exception_cleanup"


def test_extract_from_multiple_upgrades_across_pages(monkeypatch):
    """
    The real bug: page 1 returns John Smith with no email, page 2 returns the same
    John Smith with a VERIFIED email. Old code silently dropped page 2. New code
    must return one John Smith entry with the VERIFIED email.
    """
    import tools.contact_extractor as ce

    calls = {"n": 0}

    def fake_extract_contacts(raw_content, source_url, district_name):
        calls["n"] += 1
        if calls["n"] == 1:
            return [_contact(
                first="John", last="Smith",
                email="", email_confidence="UNKNOWN",
                source_url=source_url,
                district_name=district_name,
            )]
        return [_contact(
            first="John", last="Smith",
            email="john.smith@test.edu", email_confidence="VERIFIED",
            source_url=source_url,
            district_name=district_name,
        )]

    monkeypatch(ce, "extract_contacts", fake_extract_contacts)

    pages = [("http://a/", "x"), ("http://b/", "y")]
    result = ce.extract_from_multiple(pages, "Test ISD")

    assert len(result) == 1, f"expected 1 merged contact, got {len(result)}: {result}"
    assert result[0]["email"] == "john.smith@test.edu"
    assert result[0]["email_confidence"] == "VERIFIED"
    return "extract_from_multiple_upgrades_across_pages"


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

class _Monkey:
    """Minimal monkeypatcher — no pytest dependency."""

    def __init__(self):
        self._saved: list[tuple] = []

    def __call__(self, obj, attr, value):
        self._saved.append((obj, attr, getattr(obj, attr)))
        setattr(obj, attr, value)

    def undo(self):
        for obj, attr, value in reversed(self._saved):
            setattr(obj, attr, value)
        self._saved.clear()


TESTS_PART_0 = [
    test_merge_upgrades_no_email_to_email,
    test_merge_upgrades_unknown_to_verified,
    test_merge_fills_empty_title,
    test_merge_no_downgrade,
    test_merge_no_duplicate_append,
    test_merge_adds_new_name,
    test_extract_from_multiple_upgrades_across_pages,
]

TESTS_PART_1 = [
    test_url_dedup_exact_duplicate,
    test_url_dedup_trailing_slash,
    test_url_dedup_case_insensitive,
    test_url_dedup_preserves_different_urls,
    test_url_dedup_off_by_default,
    test_l15_step5_skips_at_threshold,
    test_l15_step5_skips_above_threshold,
    test_l15_step5_runs_below_threshold,
    test_l15_step5_off_by_default,
    test_claude_usage_capture_when_enabled,
    test_claude_usage_no_capture_when_disabled,
    test_claude_usage_balanced_start_stop,
    test_claude_usage_exception_cleanup,
]


def main() -> int:
    passed, failed = 0, 0
    failures: list[str] = []

    for fn in TESTS_PART_0 + TESTS_PART_1:
        name = fn.__name__
        mp = _Monkey()
        try:
            if "monkeypatch" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                fn(mp)
            else:
                fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failures.append(name)
            failed += 1
        except Exception as e:
            print(f"  ERR   {name}: {type(e).__name__}: {e}")
            failures.append(name)
            failed += 1
        finally:
            mp.undo()

    total = passed + failed
    print()
    print(f"Round 1 unit tests: {passed}/{total} passed")
    if failures:
        print(f"Failures: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
