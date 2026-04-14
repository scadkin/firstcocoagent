"""
Unit tests for scripts/load_campaign.py helpers + command flows.

Mocks tools.role_classifier.classify_contact_role and
tools.outreach_client.create_sequence / validate_sequence_inputs so
tests run offline. Does NOT cover execute_load_plan integration —
that's tested at the prospect_loader boundary.

Run from repo root:
    .venv/bin/python scripts/test_load_campaign.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import the CLI module as `load_campaign`
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "load_campaign", REPO_ROOT / "scripts" / "load_campaign.py"
)
load_campaign = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_campaign)

from tools.campaign_file import parse_campaign  # noqa: E402
from tools.prospect_loader import Contact  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────

CAMPAIGN_TEXT = """---
campaign_name: "Test Load"
campaign_slug: "test_load"
schedule_id: 50
drip_days:
  - 2026-04-21
  - 2026-04-22
tag_template: "test-load-{role}"
sleep_seconds_min: 60
sleep_seconds_max: 180
---

## variant: admin
target_role_label: "Principal"
num_steps: 2

### Step 1 — Subject: Hi admin
Body A. See <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

### Step 2 — Subject: Follow up
Body B. See <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

## variant: teacher
target_role_label: "Teacher"
num_steps: 2

### Step 1 — Subject: Hi teacher
Body C. See <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

### Step 2 — Subject: Follow up
Body D. See <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.
"""


VALID_CSV = """first_name,last_name,email,title,company,state
Alice,Reynolds,alice@isd.example,Superintendent,Test ISD,TX
Bob,Park,bob@isd.example,CS Teacher,Test ISD,TX
Carol,Chen,carol@isd.example,Director of Technology,Test ISD,CA
"""


def _check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def _tmp_path(suffix: str = "") -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return p


# ── Contact hydration ───────────────────────────────────────────────────

def test_read_contacts_csv_rejects_missing_columns() -> None:
    bad = "first_name,last_name,email\nA,B,a@b.com\n"
    try:
        load_campaign._read_contacts_csv(bad)
    except ValueError as e:
        _check("error mentions missing columns", "missing required columns" in str(e))
        return
    raise AssertionError("expected ValueError for missing columns")


def test_read_contacts_csv_accepts_extra_columns() -> None:
    rows = load_campaign._read_contacts_csv(
        "first_name,last_name,email,title,company,state,notes,extra\n"
        "A,B,a@b.com,Principal,ISD,TX,,junk\n"
    )
    _check("row parsed", len(rows) == 1)
    _check("extra column preserved", rows[0].get("extra") == "junk")


def test_hydrate_contact_success() -> None:
    contact, reason = load_campaign._hydrate_contact(
        {
            "first_name": "Alice",
            "last_name": "Reynolds",
            "email": "Alice@ISD.Example",
            "title": "Superintendent",
            "company": "Test ISD",
            "state": "tx",
        }
    )
    _check("no skip reason", reason is None, f"got {reason}")
    _check("email lowercased", contact.email == "alice@isd.example")
    _check("state uppercased", contact.state == "TX")
    _check("diocese_or_group = company", contact.diocese_or_group == "Test ISD")


def test_hydrate_contact_skips_missing_email() -> None:
    contact, reason = load_campaign._hydrate_contact(
        {
            "first_name": "A",
            "last_name": "B",
            "email": "",
            "title": "T",
            "company": "C",
            "state": "TX",
        }
    )
    _check("contact is None", contact is None)
    _check("reason mentions email", "email" in (reason or ""))


def test_hydrate_contact_skips_missing_state() -> None:
    contact, reason = load_campaign._hydrate_contact(
        {
            "first_name": "A",
            "last_name": "B",
            "email": "a@b.com",
            "title": "T",
            "company": "C",
            "state": "",
        }
    )
    _check("contact is None", contact is None)
    _check("reason mentions state", "state" in (reason or ""))


def test_hydrate_contact_skips_non_us_state() -> None:
    contact, reason = load_campaign._hydrate_contact(
        {
            "first_name": "A",
            "last_name": "B",
            "email": "a@b.com",
            "title": "T",
            "company": "C",
            "state": "ZZ",
        }
    )
    _check("contact is None", contact is None)
    _check("reason mentions timezone", "timezone" in (reason or ""))


def test_hydrate_contact_skips_missing_name() -> None:
    contact, reason = load_campaign._hydrate_contact(
        {
            "first_name": "",
            "last_name": "B",
            "email": "a@b.com",
            "title": "T",
            "company": "C",
            "state": "TX",
        }
    )
    _check("contact is None", contact is None)
    _check("reason mentions first_name", "first_name" in (reason or ""))


# ── Sidecar state I/O ───────────────────────────────────────────────────

def test_state_write_read_round_trip() -> None:
    path = _tmp_path(".json")
    try:
        data = {
            "slug": "x",
            "sequences": {"admin": {"id": "1234", "name": "X — admin"}},
            "load_runs": [],
        }
        load_campaign._write_state_atomic(path, data)
        read = load_campaign._read_state(path)
        _check("round-trip slug", read["slug"] == "x")
        _check("round-trip sequences", read["sequences"]["admin"]["id"] == "1234")
    finally:
        path.unlink(missing_ok=True)


def test_read_state_returns_empty_on_missing() -> None:
    path = _tmp_path(".json")
    result = load_campaign._read_state(path)
    _check("missing file → empty dict", result == {})


def test_sha1_of_file_is_stable() -> None:
    path = _tmp_path(".md")
    try:
        path.write_text("hello world", encoding="utf-8")
        h1 = load_campaign._sha1_of_file(path)
        h2 = load_campaign._sha1_of_file(path)
        _check("sha1 stable", h1 == h2)
        _check("sha1 nonempty", len(h1) == 40)
    finally:
        path.unlink(missing_ok=True)


# ── Drift detection ─────────────────────────────────────────────────────

def test_drift_check_matches_sha1() -> None:
    path = _tmp_path(".md")
    try:
        path.write_text("content", encoding="utf-8")
        state = {"campaign_file_sha1": load_campaign._sha1_of_file(path)}
        campaign = parse_campaign(CAMPAIGN_TEXT)
        ok = load_campaign._drift_check(campaign, path, state, force=False)
        _check("matching sha1 passes drift check", ok is True)
    finally:
        path.unlink(missing_ok=True)


def test_drift_check_rejects_mismatch_without_force() -> None:
    path = _tmp_path(".md")
    try:
        path.write_text("original", encoding="utf-8")
        state = {"campaign_file_sha1": load_campaign._sha1_of_file(path)}
        path.write_text("modified", encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)
        ok = load_campaign._drift_check(campaign, path, state, force=False)
        _check("drift detected", ok is False)
    finally:
        path.unlink(missing_ok=True)


def test_drift_check_passes_mismatch_with_force() -> None:
    path = _tmp_path(".md")
    try:
        path.write_text("original", encoding="utf-8")
        state = {"campaign_file_sha1": load_campaign._sha1_of_file(path)}
        path.write_text("modified", encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)
        ok = load_campaign._drift_check(campaign, path, state, force=True)
        _check("force bypass", ok is True)
    finally:
        path.unlink(missing_ok=True)


def test_drift_check_no_sha1_in_state() -> None:
    path = _tmp_path(".md")
    try:
        path.write_text("content", encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)
        ok = load_campaign._drift_check(campaign, path, {}, force=False)
        _check("no sha1 in state → no drift", ok is True)
    finally:
        path.unlink(missing_ok=True)


# ── Plan building ───────────────────────────────────────────────────────

def test_build_plans_routes_by_role() -> None:
    campaign = parse_campaign(CAMPAIGN_TEXT)
    contacts = [
        Contact(
            first_name="A",
            last_name="B",
            email="a@isd.example",
            title="Principal",
            company="Test ISD",
            state="TX",
            email_confidence="VERIFIED",
            diocese_or_group="Test ISD",
        ),
        Contact(
            first_name="C",
            last_name="D",
            email="c@isd.example",
            title="CS Teacher",
            company="Test ISD",
            state="TX",
            email_confidence="VERIFIED",
            diocese_or_group="Test ISD",
        ),
    ]
    role_map = {"a@isd.example": "admin", "c@isd.example": "teacher"}
    state = {
        "sequences": {
            "admin": {"id": "1001", "name": "Test Load — admin"},
            "teacher": {"id": "1002", "name": "Test Load — teacher"},
        }
    }

    plans, warnings = load_campaign._build_plans(campaign, contacts, role_map, state)
    _check("two plans built", len(plans) == 2)
    _check("no warnings", warnings == [])

    by_email = {p.contact.email: p for p in plans}
    _check(
        "admin routes to 1001",
        by_email["a@isd.example"].sequence_id == 1001,
    )
    _check(
        "teacher routes to 1002",
        by_email["c@isd.example"].sequence_id == 1002,
    )


def test_build_plans_warns_on_missing_variant_sequence() -> None:
    campaign = parse_campaign(CAMPAIGN_TEXT)
    contacts = [
        Contact(
            first_name="A",
            last_name="B",
            email="a@isd.example",
            title="Director of Technology",
            company="Test ISD",
            state="TX",
            email_confidence="VERIFIED",
            diocese_or_group="Test ISD",
        ),
    ]
    role_map = {"a@isd.example": "it"}  # 'it' variant not in state
    state = {"sequences": {"admin": {"id": "1001"}}}

    plans, warnings = load_campaign._build_plans(campaign, contacts, role_map, state)
    _check("no plans built", len(plans) == 0)
    _check("warning emitted", len(warnings) == 1)
    _check("warning mentions 'it' role", "'it'" in warnings[0] or "it" in warnings[0])


# ── Create command flow ─────────────────────────────────────────────────

def test_cmd_create_dry_run_no_state_file() -> None:
    """--create --dry-run runs preflight but does NOT write state file."""
    import tools.outreach_client as oc

    md_path = _tmp_path(".md")
    state_path = _tmp_path(".json")
    state_path.unlink(missing_ok=True)

    fake_validation = lambda **kw: {"passed": True, "failures": [], "warnings": []}

    try:
        md_path.write_text(CAMPAIGN_TEXT, encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)

        with patch.object(oc, "validate_sequence_inputs", side_effect=fake_validation), \
             patch.object(load_campaign, "state_path", return_value=state_path):
            rc = load_campaign.cmd_create(campaign, md_path, dry_run=True)

        _check("dry-run returns 0", rc == 0)
        _check(
            "dry-run does not write state file",
            not state_path.exists(),
            f"state file unexpectedly exists at {state_path}",
        )
    finally:
        md_path.unlink(missing_ok=True)
        state_path.unlink(missing_ok=True)


def test_cmd_create_idempotent_skips_existing_variants() -> None:
    """Running --create with a pre-populated state should skip created variants."""
    import tools.outreach_client as oc

    md_path = _tmp_path(".md")
    state_file = _tmp_path(".json")

    fake_validation = lambda **kw: {"passed": True, "failures": [], "warnings": []}
    create_calls: list[str] = []

    def fake_create(**kw):
        create_calls.append(kw["name"])
        return {"sequence_id": "9999", "name": kw["name"]}

    try:
        md_path.write_text(CAMPAIGN_TEXT, encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)

        # Pre-populate state: admin already created, teacher not yet
        preexisting = {
            "slug": "test_load",
            "sequences": {
                "admin": {"id": "1111", "name": "Test Load — admin"},
            },
            "load_runs": [],
        }
        state_file.write_text(json.dumps(preexisting))

        with patch.object(oc, "validate_sequence_inputs", side_effect=fake_validation), \
             patch.object(oc, "create_sequence", side_effect=fake_create), \
             patch.object(load_campaign, "state_path", return_value=state_file):
            rc = load_campaign.cmd_create(campaign, md_path, dry_run=False)

        _check("returns 0", rc == 0)
        _check(
            "only teacher created",
            len(create_calls) == 1 and "teacher" in create_calls[0],
            f"got {create_calls}",
        )

        after = json.loads(state_file.read_text())
        _check("admin still present", "admin" in after["sequences"])
        _check("teacher now present", "teacher" in after["sequences"])
        _check(
            "admin id preserved",
            after["sequences"]["admin"]["id"] == "1111",
        )
    finally:
        md_path.unlink(missing_ok=True)
        state_file.unlink(missing_ok=True)


def test_cmd_create_fails_on_preflight_failure() -> None:
    """cmd_create exits non-zero without writing state if any variant fails preflight."""
    import tools.outreach_client as oc

    md_path = _tmp_path(".md")
    state_file = _tmp_path(".json")
    state_file.unlink(missing_ok=True)

    call_count = {"n": 0}

    def fake_validation(**kw):
        call_count["n"] += 1
        if "admin" in kw.get("name", ""):
            return {"passed": False, "failures": ["admin fake failure"], "warnings": []}
        return {"passed": True, "failures": [], "warnings": []}

    create_calls: list[str] = []

    def fake_create(**kw):
        create_calls.append(kw["name"])
        return {"sequence_id": "9999", "name": kw["name"]}

    try:
        md_path.write_text(CAMPAIGN_TEXT, encoding="utf-8")
        campaign = parse_campaign(CAMPAIGN_TEXT)

        with patch.object(oc, "validate_sequence_inputs", side_effect=fake_validation), \
             patch.object(oc, "create_sequence", side_effect=fake_create), \
             patch.object(load_campaign, "state_path", return_value=state_file):
            rc = load_campaign.cmd_create(campaign, md_path, dry_run=False)

        _check("returns non-zero", rc != 0)
        _check("create_sequence never called", len(create_calls) == 0)
        _check("state file not written", not state_file.exists())
    finally:
        md_path.unlink(missing_ok=True)
        state_file.unlink(missing_ok=True)


# ── Test registration ───────────────────────────────────────────────────

TESTS = [
    test_read_contacts_csv_rejects_missing_columns,
    test_read_contacts_csv_accepts_extra_columns,
    test_hydrate_contact_success,
    test_hydrate_contact_skips_missing_email,
    test_hydrate_contact_skips_missing_state,
    test_hydrate_contact_skips_non_us_state,
    test_hydrate_contact_skips_missing_name,
    test_state_write_read_round_trip,
    test_read_state_returns_empty_on_missing,
    test_sha1_of_file_is_stable,
    test_drift_check_matches_sha1,
    test_drift_check_rejects_mismatch_without_force,
    test_drift_check_passes_mismatch_with_force,
    test_drift_check_no_sha1_in_state,
    test_build_plans_routes_by_role,
    test_build_plans_warns_on_missing_variant_sequence,
    test_cmd_create_dry_run_no_state_file,
    test_cmd_create_idempotent_skips_existing_variants,
    test_cmd_create_fails_on_preflight_failure,
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
