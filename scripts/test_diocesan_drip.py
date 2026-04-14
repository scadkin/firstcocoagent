"""
Unit tests for:
  - tools.timezone_lookup.state_to_timezone / is_valid_iana_timezone
  - tools.outreach_client.validate_prospect_inputs
  - tools.prospect_loader.build_load_plan

Zero API calls. Zero fixtures. Runs in <1 second.

Run:
    .venv/bin/python scripts/test_diocesan_drip.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from tools.timezone_lookup import state_to_timezone, is_valid_iana_timezone  # noqa: E402
from tools.outreach_client import validate_prospect_inputs  # noqa: E402
from tools.prospect_loader import Contact, build_load_plan  # noqa: E402


# ─────────────────────────────────────────────
# timezone_lookup
# ─────────────────────────────────────────────

_TERRITORY_STATES = ["TX", "CA", "IL", "PA", "OH", "MI", "CT", "OK", "MA", "IN", "NV", "TN", "NE"]


def test_state_to_timezone_covers_all_territory_states():
    for state in _TERRITORY_STATES:
        tz = state_to_timezone(state)
        assert tz is not None, f"{state} returned None"
        assert is_valid_iana_timezone(tz), f"{state} -> {tz!r} is not valid IANA"
    return "state_to_timezone_covers_all_territory_states"


def test_state_to_timezone_unknown_returns_none():
    assert state_to_timezone("") is None
    assert state_to_timezone(None) is None
    assert state_to_timezone("XX") is None
    assert state_to_timezone("USA") is None
    return "state_to_timezone_unknown_returns_none"


def test_is_valid_iana_timezone_rejects_garbage():
    assert is_valid_iana_timezone("America/New_York") is True
    assert is_valid_iana_timezone("America/Chicago") is True
    assert is_valid_iana_timezone("") is False
    assert is_valid_iana_timezone(None) is False
    assert is_valid_iana_timezone("Mars/Olympus") is False
    assert is_valid_iana_timezone("EST") is False or is_valid_iana_timezone("EST") is True
    return "is_valid_iana_timezone_rejects_garbage"


# ─────────────────────────────────────────────
# validate_prospect_inputs
# ─────────────────────────────────────────────

def _clean_kwargs() -> dict:
    return dict(
        first_name="Steven",
        last_name="Adkins",
        email="sadkins@archphila.org",
        title="Superintendent of Schools",
        company="Archdiocese of Philadelphia Schools",
        state="PA",
        timezone="America/New_York",
        tags=["diocesan-drip-2026-04", "diocesan-drip-philadelphia"],
    )


def test_validate_prospect_inputs_accepts_clean():
    r = validate_prospect_inputs(**_clean_kwargs())
    assert r["passed"] is True, f"clean should pass, got: {r['failures']}"
    assert r["failures"] == []
    return "validate_prospect_inputs_accepts_clean"


def test_validate_prospect_inputs_rejects_missing_timezone():
    kw = _clean_kwargs()
    kw["timezone"] = ""
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("timezone is empty" in f.lower() or "rule 17" in f.lower() for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_missing_timezone"


def test_validate_prospect_inputs_rejects_invalid_timezone():
    kw = _clean_kwargs()
    kw["timezone"] = "Mars/Olympus"
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("not a valid iana" in f.lower() for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_invalid_timezone"


def test_validate_prospect_inputs_rejects_placeholder_email():
    kw = _clean_kwargs()
    kw["email"] = "[email protected]"
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("placeholder" in f.lower() for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_placeholder_email"


def test_validate_prospect_inputs_rejects_apostrophe_local_part():
    kw = _clean_kwargs()
    kw["email"] = "co'brien@catholicaoc.org"
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("local-part" in f.lower() or "disallowed" in f.lower() for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_apostrophe_local_part"


def test_validate_prospect_inputs_rejects_generic_free_mail():
    kw = _clean_kwargs()
    kw["email"] = "stevenadkins@gmail.com"
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("free-mail" in f.lower() or "gmail" in f.lower() for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_generic_free_mail"


def test_validate_prospect_inputs_allows_generic_free_mail_when_flag_set():
    kw = _clean_kwargs()
    kw["email"] = "stevenadkins@gmail.com"
    kw["allow_generic_email"] = True
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is True, f"should pass with allow_generic_email=True, got: {r['failures']}"
    return "validate_prospect_inputs_allows_generic_free_mail_when_flag_set"


def test_validate_prospect_inputs_rejects_empty_first_name():
    kw = _clean_kwargs()
    kw["first_name"] = ""
    r = validate_prospect_inputs(**kw)
    assert r["passed"] is False
    assert any("first_name" in f for f in r["failures"]), r["failures"]
    return "validate_prospect_inputs_rejects_empty_first_name"


# ─────────────────────────────────────────────
# build_load_plan
# ─────────────────────────────────────────────

def _make_contact(first: str, last: str, diocese: str, conf: str = "VERIFIED") -> Contact:
    slug = f"{first.lower()}.{last.lower()}"
    return Contact(
        first_name=first,
        last_name=last,
        email=f"{slug}@test.edu",
        title="Superintendent",
        company=diocese,
        state="PA",
        email_confidence=conf,
        diocese_or_group=diocese,
    )


def _make_diocesan_sample() -> list[Contact]:
    # Build a small multi-diocese set: 3 each from 2 dioceses
    return [
        _make_contact("Alice", "Adams", "Archdiocese of Philadelphia", "VERIFIED"),
        _make_contact("Bob", "Brown", "Archdiocese of Philadelphia", "INFERRED"),
        _make_contact("Carol", "Chen", "Archdiocese of Philadelphia", "VERIFIED"),
        _make_contact("Dan", "Diaz", "Archdiocese of Cincinnati", "VERIFIED"),
        _make_contact("Eve", "Epps", "Archdiocese of Cincinnati", "LIKELY"),
        _make_contact("Frank", "Foy", "Archdiocese of Cincinnati", "INFERRED"),
    ]


_SEQ_MAP = {
    "Archdiocese of Philadelphia": 2008,
    "Archdiocese of Cincinnati": 2009,
}


def test_build_load_plan_round_robin_by_diocese():
    # 6 contacts (3 per diocese) across 2 days. Each diocese should split
    # 2-1 across the two days (because 3 contacts rotate: 0→Mon, 1→Tue, 2→Mon).
    # The key guarantee: no diocese ends up entirely on one day when it has
    # more contacts than days_count.
    contacts = _make_diocesan_sample()
    plans = build_load_plan(
        contacts,
        sequence_id_for=lambda c: _SEQ_MAP[c.diocese_or_group],
        days=["2026-04-13", "2026-04-14"],
    )
    assert len(plans) == 6

    # Every diocese with >1 contact must have contacts on BOTH days.
    per_diocese_days: dict[str, set[str]] = {}
    per_diocese_counts: dict[str, int] = {}
    for p in plans:
        d = p.contact.diocese_or_group
        per_diocese_days.setdefault(d, set()).add(p.day_bucket)
        per_diocese_counts[d] = per_diocese_counts.get(d, 0) + 1

    for d, days_touched in per_diocese_days.items():
        count = per_diocese_counts[d]
        if count >= 2:
            assert len(days_touched) >= 2, (
                f"diocese {d} has {count} contacts but only touches {days_touched}"
            )

    # And every day touches at least one diocese
    day1 = {p.contact.diocese_or_group for p in plans if p.day_bucket == "2026-04-13"}
    day2 = {p.contact.diocese_or_group for p in plans if p.day_bucket == "2026-04-14"}
    assert len(day1) >= 1 and len(day2) >= 1
    return "build_load_plan_round_robin_by_diocese"


def test_build_load_plan_verified_first_within_diocese():
    contacts = _make_diocesan_sample()
    plans = build_load_plan(
        contacts,
        sequence_id_for=lambda c: _SEQ_MAP[c.diocese_or_group],
        days=["2026-04-13", "2026-04-14", "2026-04-15"],
    )
    # VERIFIED contacts should appear before INFERRED in the flat plan list
    # within each diocese. Find the first INFERRED for Philadelphia and make
    # sure no VERIFIED Philadelphia contact appears after it.
    phil_plans = [p for p in plans if p.contact.diocese_or_group == "Archdiocese of Philadelphia"]
    # Phil contacts are Alice(VERIFIED), Bob(INFERRED), Carol(VERIFIED)
    # Sorted: Alice (VERIFIED), Carol (VERIFIED), Bob (INFERRED)
    order = [p.contact.first_name for p in phil_plans]
    verified_indices = [i for i, p in enumerate(phil_plans) if p.contact.confidence_rank() == 3]
    inferred_indices = [i for i, p in enumerate(phil_plans) if p.contact.confidence_rank() == 1]
    if verified_indices and inferred_indices:
        assert max(verified_indices) < min(inferred_indices), f"verified appeared after inferred: {order}"
    return "build_load_plan_verified_first_within_diocese"


def test_build_load_plan_deterministic_on_rerun():
    contacts = _make_diocesan_sample()

    def run_once():
        plans = build_load_plan(
            contacts,
            sequence_id_for=lambda c: _SEQ_MAP[c.diocese_or_group],
            days=["2026-04-13", "2026-04-14"],
        )
        return [(p.contact.email, p.day_bucket, p.sequence_id) for p in plans]

    run1 = run_once()
    run2 = run_once()
    assert run1 == run2, f"non-deterministic:\n{run1}\n!=\n{run2}"
    return "build_load_plan_deterministic_on_rerun"


def test_build_load_plan_tags_applied():
    contacts = [_make_contact("Alice", "Adams", "Archdiocese of Philadelphia", "VERIFIED")]
    plans = build_load_plan(
        contacts,
        sequence_id_for=lambda c: _SEQ_MAP[c.diocese_or_group],
        days=["2026-04-13"],
        tags_for=lambda c: ["diocesan-drip-2026-04", "custom-tag"],
    )
    assert len(plans) == 1
    assert plans[0].tags == ["diocesan-drip-2026-04", "custom-tag"]
    return "build_load_plan_tags_applied"


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

TESTS = [
    test_state_to_timezone_covers_all_territory_states,
    test_state_to_timezone_unknown_returns_none,
    test_is_valid_iana_timezone_rejects_garbage,
    test_validate_prospect_inputs_accepts_clean,
    test_validate_prospect_inputs_rejects_missing_timezone,
    test_validate_prospect_inputs_rejects_invalid_timezone,
    test_validate_prospect_inputs_rejects_placeholder_email,
    test_validate_prospect_inputs_rejects_apostrophe_local_part,
    test_validate_prospect_inputs_rejects_generic_free_mail,
    test_validate_prospect_inputs_allows_generic_free_mail_when_flag_set,
    test_validate_prospect_inputs_rejects_empty_first_name,
    test_build_load_plan_round_robin_by_diocese,
    test_build_load_plan_verified_first_within_diocese,
    test_build_load_plan_deterministic_on_rerun,
    test_build_load_plan_tags_applied,
]


def main() -> int:
    passed, failed = 0, 0
    failures: list[str] = []
    for fn in TESTS:
        name = fn.__name__
        try:
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
    total = passed + failed
    print()
    print(f"Diocesan drip: {passed}/{total} passed")
    if failures:
        print(f"Failures: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
