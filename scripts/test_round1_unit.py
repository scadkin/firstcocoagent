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

from tools.contact_extractor import _merge_contact_upgrade  # noqa: E402


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


def main() -> int:
    passed, failed = 0, 0
    failures: list[str] = []

    for fn in TESTS_PART_0:
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
    print(f"Part 0: {passed}/{total} passed")
    if failures:
        print(f"Failures: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
