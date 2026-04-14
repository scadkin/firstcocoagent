"""
Unit tests for tools/campaign_file.py.

Run from repo root:
    .venv/bin/python scripts/test_campaign_file.py
"""
from __future__ import annotations

import sys
import traceback
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.campaign_file import (  # noqa: E402
    Campaign,
    CampaignFileError,
    CampaignStep,
    CampaignVariant,
    DEFAULT_STEP_INTERVALS_DAYS,
    SECONDS_PER_DAY,
    dump_campaign,
    load_campaign,
    parse_campaign,
)


MINIMAL_FIXTURE = """---
campaign_name: "Test"
campaign_slug: "test_min"
schedule_id: 50
drip_days:
  - 2026-04-21
tag_template: "test-{role}"
sleep_seconds_min: 30
sleep_seconds_max: 90
---

## variant: admin
target_role_label: "Superintendent"
num_steps: 2

### Step 1 — Subject: Hello
Body one.

### Step 2 — Subject: Hello again
Body two.
"""


def _check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def test_parses_canary_fixture() -> None:
    path = REPO_ROOT / "campaigns" / "canary_test.md"
    campaign = load_campaign(path)
    _check("canary name", campaign.name == "Canary Test Campaign")
    _check("canary slug", campaign.slug == "canary_test")
    _check("canary schedule", campaign.schedule_id == 50)
    _check("canary drip_days length", len(campaign.drip_days) == 3)
    _check("canary drip_days[0] type", isinstance(campaign.drip_days[0], date))
    _check("canary variant count", len(campaign.variants) == 3)
    _check("canary variants keys", set(campaign.variants.keys()) == {"admin", "teacher", "it"})
    admin = campaign.variants["admin"]
    _check("admin step count", len(admin.steps) == 5)
    _check("admin step 1 number", admin.steps[0].step_number == 1)
    _check("admin step 1 subject present", bool(admin.steps[0].subject))
    _check("admin step 1 interval", admin.steps[0].interval_seconds == 0)
    _check(
        "admin step 2 interval == 5 days",
        admin.steps[1].interval_seconds == 5 * SECONDS_PER_DAY,
    )


def test_round_trip_parse_dump_parse() -> None:
    path = REPO_ROOT / "campaigns" / "canary_test.md"
    original = load_campaign(path)
    dumped = dump_campaign(original)
    reparsed = parse_campaign(dumped)

    _check("round-trip name", reparsed.name == original.name)
    _check("round-trip slug", reparsed.slug == original.slug)
    _check("round-trip schedule_id", reparsed.schedule_id == original.schedule_id)
    _check("round-trip drip_days", reparsed.drip_days == original.drip_days)
    _check("round-trip tag_template", reparsed.tag_template == original.tag_template)
    _check("round-trip sleep_seconds", reparsed.sleep_seconds == original.sleep_seconds)
    _check(
        "round-trip step_intervals_days",
        reparsed.step_intervals_days == original.step_intervals_days,
    )
    _check(
        "round-trip variant roles",
        set(reparsed.variants.keys()) == set(original.variants.keys()),
    )
    for role, variant in original.variants.items():
        reparsed_variant = reparsed.variants[role]
        _check(
            f"round-trip {role} target_role_label",
            reparsed_variant.target_role_label == variant.target_role_label,
        )
        _check(
            f"round-trip {role} num_steps",
            reparsed_variant.num_steps == variant.num_steps,
        )
        _check(
            f"round-trip {role} step count",
            len(reparsed_variant.steps) == len(variant.steps),
        )
        for i, orig_step in enumerate(variant.steps):
            rp_step = reparsed_variant.steps[i]
            _check(
                f"round-trip {role} step {i+1} subject",
                rp_step.subject == orig_step.subject,
            )
            _check(
                f"round-trip {role} step {i+1} body",
                rp_step.body == orig_step.body,
            )
            _check(
                f"round-trip {role} step {i+1} interval_seconds",
                rp_step.interval_seconds == orig_step.interval_seconds,
            )


def test_parses_minimal_fixture() -> None:
    campaign = parse_campaign(MINIMAL_FIXTURE)
    _check("minimal slug", campaign.slug == "test_min")
    _check("minimal variants", set(campaign.variants.keys()) == {"admin"})
    _check("minimal step count", len(campaign.variants["admin"].steps) == 2)
    _check(
        "minimal default intervals",
        campaign.step_intervals_days == DEFAULT_STEP_INTERVALS_DAYS,
    )


def test_permissive_heading_variations() -> None:
    variant_text = """---
campaign_name: "P"
campaign_slug: "p"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "p-{role}"
sleep_seconds_min: 10
sleep_seconds_max: 20
---

## variant: teacher
target_role_label: "Teacher"
num_steps: 3

## Step 1 - Subject: H2 heading with hyphen
Body A

#### Step 2: H4 heading with colon only
Body B

### Step 3 — Subject: H3 heading with em-dash
Body C
"""
    campaign = parse_campaign(variant_text)
    steps = campaign.variants["teacher"].steps
    _check("permissive step count", len(steps) == 3)
    _check("permissive step 1 subject", "H2 heading" in steps[0].subject)
    _check("permissive step 2 subject", "H4 heading" in steps[1].subject)
    _check("permissive step 3 subject", "H3 heading" in steps[2].subject)


def test_rejects_missing_frontmatter_key() -> None:
    bad = """---
campaign_name: "X"
campaign_slug: "x"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "x-{role}"
---

## variant: admin
target_role_label: "A"
num_steps: 1

### Step 1 — Subject: S
B
"""
    try:
        parse_campaign(bad)
    except CampaignFileError as e:
        _check("error mentions missing keys", "sleep_seconds_min" in str(e))
        return
    raise AssertionError("expected CampaignFileError for missing sleep_seconds_min")


def test_rejects_duplicate_variant_role() -> None:
    bad = """---
campaign_name: "X"
campaign_slug: "x"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "x-{role}"
sleep_seconds_min: 10
sleep_seconds_max: 20
---

## variant: admin
target_role_label: "A"
num_steps: 1

### Step 1 — Subject: S
B

## variant: admin
target_role_label: "A2"
num_steps: 1

### Step 1 — Subject: S2
B2
"""
    try:
        parse_campaign(bad)
    except CampaignFileError as e:
        _check("duplicate error mentions admin", "admin" in str(e))
        return
    raise AssertionError("expected CampaignFileError for duplicate variant")


def test_rejects_unknown_role() -> None:
    bad = """---
campaign_name: "X"
campaign_slug: "x"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "x-{role}"
sleep_seconds_min: 10
sleep_seconds_max: 20
---

## variant: janitor
target_role_label: "J"
num_steps: 1

### Step 1 — Subject: S
B
"""
    try:
        parse_campaign(bad)
    except CampaignFileError as e:
        _check("unknown role error", "janitor" in str(e))
        return
    raise AssertionError("expected CampaignFileError for unknown role")


def test_rejects_empty_variant_section() -> None:
    bad = """---
campaign_name: "X"
campaign_slug: "x"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "x-{role}"
sleep_seconds_min: 10
sleep_seconds_max: 20
---

## variant: admin
target_role_label: "A"
num_steps: 1
"""
    try:
        parse_campaign(bad)
    except CampaignFileError as e:
        _check("empty variant error", "no steps" in str(e))
        return
    raise AssertionError("expected CampaignFileError for variant with no steps")


def test_rejects_no_frontmatter() -> None:
    bad = "## variant: admin\ntarget_role_label: A\nnum_steps: 1\n### Step 1 — Subject: S\nB\n"
    try:
        parse_campaign(bad)
    except CampaignFileError:
        return
    raise AssertionError("expected CampaignFileError for missing frontmatter")


def test_custom_step_intervals_days() -> None:
    text = """---
campaign_name: "X"
campaign_slug: "x"
schedule_id: 50
drip_days: ["2026-04-21"]
tag_template: "x-{role}"
sleep_seconds_min: 10
sleep_seconds_max: 20
step_intervals_days: [0, 3, 4]
---

## variant: admin
target_role_label: "A"
num_steps: 3

### Step 1 — Subject: S1
B1

### Step 2 — Subject: S2
B2

### Step 3 — Subject: S3
B3
"""
    campaign = parse_campaign(text)
    steps = campaign.variants["admin"].steps
    _check("custom step 1 interval", steps[0].interval_seconds == 0)
    _check("custom step 2 interval", steps[1].interval_seconds == 3 * SECONDS_PER_DAY)
    _check("custom step 3 interval", steps[2].interval_seconds == 4 * SECONDS_PER_DAY)


TESTS = [
    test_parses_canary_fixture,
    test_round_trip_parse_dump_parse,
    test_parses_minimal_fixture,
    test_permissive_heading_variations,
    test_rejects_missing_frontmatter_key,
    test_rejects_duplicate_variant_role,
    test_rejects_unknown_role,
    test_rejects_empty_variant_section,
    test_rejects_no_frontmatter,
    test_custom_step_intervals_days,
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
