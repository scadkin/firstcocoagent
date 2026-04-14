"""
campaign_file.py — single-file campaign markdown schema, parser, and dumper.

A campaign lives at ``campaigns/<slug>.md``. Format:

    ---
    campaign_name: "CUE 2026"
    campaign_slug: "cue_2026"
    schedule_id: 50
    drip_days:
      - 2026-04-21
      - 2026-04-22
    tag_template: "cue-2026-{role}"
    sleep_seconds_min: 60
    sleep_seconds_max: 180
    # optional:
    step_intervals_days: [0, 5, 6, 7, 8]
    ---

    ## variant: admin
    target_role_label: "Superintendent / Principal"
    num_steps: 5

    ### Step 1 — Subject: Quick note on your CS rollout at {{company}}
    Hi {{first_name}},
    ...

    ### Step 2 — Subject: Re: Quick note on your CS rollout at {{company}}
    ...

    ## variant: teacher
    target_role_label: "CS Teacher"
    num_steps: 5

    ### Step 1 — Subject: ...

The parser is permissive on:
  - heading levels (## / ### / #### all accepted for steps)
  - subject separators (em-dash, hyphen, colon)
  - blank lines and surrounding whitespace

It is strict on:
  - YAML frontmatter must be between ``---`` delimiters at the top
  - Every variant must have ``target_role_label`` and ``num_steps``
  - Variant roles must be unique within a campaign
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


# Step 1 is immediate (0), steps 2-5 ramp up. Matches the diocesan cadence.
DEFAULT_STEP_INTERVALS_DAYS = [0, 5, 6, 7, 8]
SECONDS_PER_DAY = 86_400

VALID_ROLES = {"admin", "curriculum", "it", "teacher", "coach", "other"}


class CampaignFileError(ValueError):
    """Raised when a campaign markdown file cannot be parsed or is invalid."""


@dataclass
class CampaignStep:
    step_number: int
    subject: str
    body: str
    interval_seconds: int


@dataclass
class CampaignVariant:
    role: str
    target_role_label: str
    num_steps: int
    steps: list[CampaignStep] = field(default_factory=list)


@dataclass
class Campaign:
    name: str
    slug: str
    schedule_id: int
    drip_days: list[date]
    tag_template: str
    sleep_seconds: tuple[int, int]
    step_intervals_days: list[int]
    variants: dict[str, CampaignVariant]

    def variant_roles(self) -> list[str]:
        return sorted(self.variants.keys())


# ── Frontmatter splitting ────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise CampaignFileError("campaign file must start with YAML frontmatter delimited by '---'")
    yaml_block = match.group(1)
    try:
        data = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as e:
        raise CampaignFileError(f"frontmatter YAML parse error: {e}")
    if not isinstance(data, dict):
        raise CampaignFileError("frontmatter must be a YAML mapping, got " + type(data).__name__)
    body = text[match.end() :]
    return data, body


# ── Variant + step parsing ───────────────────────────────────────────────

_VARIANT_HEADING_RE = re.compile(
    r"^##\s+variant\s*:\s*([A-Za-z][A-Za-z0-9_\-]*)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

_STEP_HEADING_RE = re.compile(
    r"^#{2,4}\s*Step\s+(\d+)\s*[—\-:]?\s*(?:Subject\s*[—\-:])?\s*(.*?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _parse_variant_meta(block: str) -> tuple[str, int, str]:
    """
    Extract target_role_label and num_steps from the lines immediately after
    the `## variant: X` heading and before the first step heading. Returns
    (target_role_label, num_steps, remainder) where remainder starts at the
    first step heading.
    """
    first_step = _STEP_HEADING_RE.search(block)
    meta_block = block[: first_step.start()] if first_step else block
    remainder = block[first_step.start() :] if first_step else ""

    target_role_label = ""
    num_steps: int | None = None

    for raw_line in meta_block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if key == "target_role_label":
            target_role_label = value
        elif key == "num_steps":
            try:
                num_steps = int(value)
            except ValueError:
                raise CampaignFileError(f"num_steps must be an integer, got {value!r}")

    if not target_role_label:
        raise CampaignFileError("variant missing 'target_role_label'")
    if num_steps is None:
        raise CampaignFileError("variant missing 'num_steps'")

    return target_role_label, num_steps, remainder


def _parse_steps(block: str, intervals_seconds: list[int]) -> list[CampaignStep]:
    headings = list(_STEP_HEADING_RE.finditer(block))
    if not headings:
        return []

    steps: list[CampaignStep] = []
    for i, match in enumerate(headings):
        step_number = int(match.group(1))
        subject = match.group(2).strip()
        body_start = match.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(block)
        body = block[body_start:body_end].strip()

        interval_idx = step_number - 1
        if 0 <= interval_idx < len(intervals_seconds):
            interval_seconds = intervals_seconds[interval_idx]
        else:
            interval_seconds = intervals_seconds[-1] if intervals_seconds else 0

        steps.append(
            CampaignStep(
                step_number=step_number,
                subject=subject,
                body=body,
                interval_seconds=interval_seconds,
            )
        )

    steps.sort(key=lambda s: s.step_number)
    return steps


def _parse_variants(body: str, intervals_seconds: list[int]) -> dict[str, CampaignVariant]:
    headings = list(_VARIANT_HEADING_RE.finditer(body))
    if not headings:
        raise CampaignFileError("campaign has no variants — expected at least one '## variant: <role>' section")

    variants: dict[str, CampaignVariant] = {}
    for i, match in enumerate(headings):
        role = match.group(1).strip().lower()
        if role not in VALID_ROLES:
            raise CampaignFileError(
                f"unknown role '{role}' — must be one of {sorted(VALID_ROLES)}"
            )
        if role in variants:
            raise CampaignFileError(f"duplicate variant role: {role!r}")

        block_start = match.end()
        block_end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        variant_block = body[block_start:block_end]

        target_role_label, num_steps, steps_block = _parse_variant_meta(variant_block)
        steps = _parse_steps(steps_block, intervals_seconds)

        if not steps:
            raise CampaignFileError(f"variant '{role}' has no steps")

        variants[role] = CampaignVariant(
            role=role,
            target_role_label=target_role_label,
            num_steps=num_steps,
            steps=steps,
        )

    return variants


# ── Frontmatter → Campaign fields ────────────────────────────────────────

_REQUIRED_FRONTMATTER_KEYS = [
    "campaign_name",
    "campaign_slug",
    "schedule_id",
    "drip_days",
    "tag_template",
    "sleep_seconds_min",
    "sleep_seconds_max",
]


def _coerce_date(v) -> date:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError as e:
            raise CampaignFileError(f"invalid date {v!r}: {e}")
    raise CampaignFileError(f"drip_days entry must be a date or ISO string, got {type(v).__name__}")


def _hydrate_campaign(fm: dict, variants: dict[str, CampaignVariant]) -> Campaign:
    missing = [k for k in _REQUIRED_FRONTMATTER_KEYS if k not in fm]
    if missing:
        raise CampaignFileError(f"frontmatter missing required keys: {missing}")

    drip_days_raw = fm["drip_days"]
    if not isinstance(drip_days_raw, list) or not drip_days_raw:
        raise CampaignFileError("drip_days must be a non-empty list")
    drip_days = [_coerce_date(v) for v in drip_days_raw]

    sleep_min = int(fm["sleep_seconds_min"])
    sleep_max = int(fm["sleep_seconds_max"])
    if sleep_min < 0 or sleep_max < sleep_min:
        raise CampaignFileError(
            f"sleep_seconds_min ({sleep_min}) / sleep_seconds_max ({sleep_max}) are inconsistent"
        )

    intervals_days = fm.get("step_intervals_days") or DEFAULT_STEP_INTERVALS_DAYS
    if not isinstance(intervals_days, list) or not all(isinstance(x, int) for x in intervals_days):
        raise CampaignFileError("step_intervals_days must be a list of integers")

    return Campaign(
        name=str(fm["campaign_name"]),
        slug=str(fm["campaign_slug"]),
        schedule_id=int(fm["schedule_id"]),
        drip_days=drip_days,
        tag_template=str(fm["tag_template"]),
        sleep_seconds=(sleep_min, sleep_max),
        step_intervals_days=list(intervals_days),
        variants=variants,
    )


# ── Public entry points ──────────────────────────────────────────────────

def load_campaign(path: str | Path) -> Campaign:
    """Parse a campaign markdown file into a Campaign."""
    path = Path(path)
    if not path.exists():
        raise CampaignFileError(f"campaign file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_campaign(text)


def parse_campaign(text: str) -> Campaign:
    """Parse campaign markdown from a string (same contract as load_campaign)."""
    fm, body = _split_frontmatter(text)

    intervals_days = fm.get("step_intervals_days") or DEFAULT_STEP_INTERVALS_DAYS
    intervals_seconds = [d * SECONDS_PER_DAY for d in intervals_days]

    variants = _parse_variants(body, intervals_seconds)
    return _hydrate_campaign(fm, variants)


def dump_campaign(campaign: Campaign) -> str:
    """Inverse of parse_campaign — emit the canonical markdown form."""
    fm_dict = {
        "campaign_name": campaign.name,
        "campaign_slug": campaign.slug,
        "schedule_id": campaign.schedule_id,
        "drip_days": [d.isoformat() for d in campaign.drip_days],
        "tag_template": campaign.tag_template,
        "sleep_seconds_min": campaign.sleep_seconds[0],
        "sleep_seconds_max": campaign.sleep_seconds[1],
        "step_intervals_days": campaign.step_intervals_days,
    }
    fm_text = yaml.safe_dump(
        fm_dict, sort_keys=False, default_flow_style=False, allow_unicode=True
    ).strip()

    parts = ["---", fm_text, "---", ""]

    for role in sorted(campaign.variants.keys()):
        variant = campaign.variants[role]
        parts.append(f"## variant: {role}")
        parts.append(f'target_role_label: "{variant.target_role_label}"')
        parts.append(f"num_steps: {variant.num_steps}")
        parts.append("")
        for step in variant.steps:
            parts.append(f"### Step {step.step_number} — Subject: {step.subject}")
            parts.append(step.body)
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"
