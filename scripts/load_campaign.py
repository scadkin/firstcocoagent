#!/usr/bin/env python3
"""
load_campaign.py — generalized campaign loader CLI.

Strategy-agnostic replacement for the pattern that was hand-coded three
times (S38 CUE, S43 C4, S44 webinar) before the S61 library promotion.

Modes:
    load_campaign.py --campaign <slug> --preview
        Build the load plan (contacts -> classified role -> routed
        sequence -> day bucket) and print it. No Outreach API calls.

    load_campaign.py --campaign <slug> --create
        Preflight every variant through validate_sequence_inputs, then
        create each variant's sequence in Outreach (unless already in
        sidecar state). Writes sequence IDs to data/<slug>.state.json.

    load_campaign.py --campaign <slug> --create --dry-run
        Run the preflight only. Refuses to continue if any variant
        fails. No Outreach POSTs.

    load_campaign.py --campaign <slug> --execute
        Load contacts into the already-created sequences. Uses
        prospect_loader.execute_load_plan under the hood. Aborts on
        drift (campaign file edited after --create); --force overrides.

    load_campaign.py --campaign <slug> --execute --dry-run
        Same but no Outreach writes; prints what would happen.

Contact input modes:
    --contacts-csv <path>   CSV at that path
    --contacts-stdin        CSV piped on stdin

CSV columns (header row required):
    first_name, last_name, email, title, company, state
    (optional: notes; extra columns ignored)

Rule compliance:
    Rule 15 - NEVER activates sequences (Steven activates in Outreach UI)
    Rule 17 - timezone enforced; contacts missing valid state are skipped
    Rule 18 - this script IS the promoted pattern
    Rule 19 - output translates sequence IDs to human names
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.campaign_file import (  # noqa: E402
    Campaign,
    CampaignFileError,
    load_campaign as load_campaign_file,
)
from tools.prospect_loader import (  # noqa: E402
    Contact,
    LoadPlan,
    build_load_plan,
    execute_load_plan,
)
from tools.role_classifier import classify_contact_role  # noqa: E402
from tools.timezone_lookup import state_to_timezone  # noqa: E402

logger = logging.getLogger("load_campaign")


# ── Paths ────────────────────────────────────────────────────────────────

def campaign_md_path(slug: str) -> Path:
    return REPO_ROOT / "campaigns" / f"{slug}.md"


def state_path(slug: str) -> Path:
    return REPO_ROOT / "data" / f"{slug}.state.json"


def audit_path(slug: str) -> Path:
    return REPO_ROOT / "data" / f"{slug}.audit.jsonl"


# ── Sidecar state ────────────────────────────────────────────────────────

def _sha1_of_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"state file {path} unreadable: {e}")
        return {}


def _write_state_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _init_state_for_slug(campaign: Campaign, md_path: Path) -> dict:
    return {
        "slug": campaign.slug,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "campaign_file_sha1": _sha1_of_file(md_path),
        "sequences": {},
        "load_runs": [],
    }


# ── Contact CSV loading ──────────────────────────────────────────────────

REQUIRED_CONTACT_COLS = ["first_name", "last_name", "email", "title", "company", "state"]


def _read_contacts_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED_CONTACT_COLS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(
            f"contact CSV missing required columns: {missing}. "
            f"Required: {REQUIRED_CONTACT_COLS}"
        )
    return list(reader)


def _load_contacts(args) -> list[dict]:
    if args.contacts_csv:
        text = Path(args.contacts_csv).read_text(encoding="utf-8")
    elif args.contacts_stdin:
        text = sys.stdin.read()
    else:
        return []
    return _read_contacts_csv(text)


def _hydrate_contact(row: dict) -> tuple[Optional[Contact], Optional[str]]:
    """
    Convert a CSV row into a Contact dataclass. Returns (contact, None) on
    success or (None, reason) on skip. Never raises.
    """
    email = (row.get("email") or "").strip().lower()
    if not email:
        return None, "missing email"

    state = (row.get("state") or "").strip().upper()
    if not state:
        return None, "missing state"
    tz = state_to_timezone(state)
    if not tz:
        return None, f"state {state!r} has no IANA timezone (non-US?)"

    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    if not first_name or not last_name:
        return None, "missing first_name or last_name"

    title = (row.get("title") or "").strip()
    company = (row.get("company") or "").strip()
    if not title or not company:
        return None, "missing title or company"

    contact = Contact(
        first_name=first_name,
        last_name=last_name,
        email=email,
        title=title,
        company=company,
        state=state,
        email_confidence=(row.get("email_confidence") or "UNKNOWN").strip().upper() or "UNKNOWN",
        diocese_or_group=company,
    )
    return contact, None


# ── Create-sequences flow ───────────────────────────────────────────────

def _variant_to_step_dicts(variant, campaign: Campaign) -> list[dict]:
    """
    Convert CampaignVariant.steps into the shape create_sequence expects.
    Coerces step 1 interval to 300s (5 min) if the campaign file sets it
    to 0 — the validator's first_step_max_seconds is 600, and the floor
    is 1, so 0 would fail even though it's semantically 'immediate'.
    """
    out = []
    for step in variant.steps:
        interval = step.interval_seconds
        if step.step_number == 1 and interval < 1:
            interval = 300
        out.append({
            "subject": step.subject,
            "body_html": step.body,
            "interval_seconds": interval,
        })
    return out


def _sequence_name_for(campaign: Campaign, role: str) -> str:
    return f"{campaign.name} — {role}"


def _run_preflight(campaign: Campaign) -> dict:
    """
    Dry-run every variant through validate_sequence_inputs. Returns
    {role: {"passed", "failures", "warnings"}}.
    """
    from tools.outreach_client import validate_sequence_inputs  # local import

    results = {}
    for role in sorted(campaign.variants.keys()):
        variant = campaign.variants[role]
        step_dicts = _variant_to_step_dicts(variant, campaign)
        result = validate_sequence_inputs(
            name=_sequence_name_for(campaign, role),
            steps=step_dicts,
            schedule_id=campaign.schedule_id,
        )
        results[role] = result
    return results


def _print_preflight_report(results: dict) -> bool:
    all_passed = True
    print()
    print("=== PREFLIGHT: validate_sequence_inputs ===")
    for role in sorted(results.keys()):
        r = results[role]
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}  variant: {role}")
        for f in r.get("failures", []):
            print(f"        - failure: {f}")
        for w in r.get("warnings", []):
            print(f"        - warning: {w}")
        if not r["passed"]:
            all_passed = False
    print()
    return all_passed


def cmd_create(campaign: Campaign, md_path: Path, *, dry_run: bool) -> int:
    from tools.outreach_client import create_sequence  # local import

    results = _run_preflight(campaign)
    passed = _print_preflight_report(results)
    if not passed:
        print("Preflight failed. Fix the validator failures above before running --create.")
        return 2

    if dry_run:
        print("--dry-run: preflight passed, skipping Outreach writes.")
        return 0

    state = _read_state(state_path(campaign.slug)) or _init_state_for_slug(campaign, md_path)
    state.setdefault("sequences", {})

    created_now: list[str] = []
    skipped_existing: list[str] = []

    for role in sorted(campaign.variants.keys()):
        if role in state["sequences"] and state["sequences"][role].get("id"):
            skipped_existing.append(role)
            continue

        variant = campaign.variants[role]
        step_dicts = _variant_to_step_dicts(variant, campaign)
        seq_name = _sequence_name_for(campaign, role)

        print(f"Creating sequence for variant '{role}': {seq_name}")
        result = create_sequence(
            name=seq_name,
            steps=step_dicts,
            schedule_id=campaign.schedule_id,
            tags=[campaign.tag_template.format(role=role)],
            verify_after_create=False,
        )
        if result.get("error"):
            print(f"  ERROR creating '{role}': {result['error']}")
            for vf in result.get("validation_failures", []):
                print(f"    - validation failure: {vf}")
            _write_state_atomic(state_path(campaign.slug), state)
            return 3

        seq_id = result.get("sequence_id")
        state["sequences"][role] = {
            "id": seq_id,
            "name": seq_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_state_atomic(state_path(campaign.slug), state)
        created_now.append(role)
        print(f"  created sequence for '{role}' (waiting for Steven to activate in Outreach UI)")

    print()
    print("=== CREATE SUMMARY ===")
    print(f"  campaign: {campaign.name}")
    if created_now:
        print(f"  created now: {sorted(created_now)}")
    if skipped_existing:
        print(f"  already created (skipped): {sorted(skipped_existing)}")
    print()
    print("Next: open Outreach UI and activate each new sequence.")
    print(f"Then run: load_campaign.py --campaign {campaign.slug} --execute")
    return 0


# ── Preview + execute flow ───────────────────────────────────────────────

def _classify_and_route(
    contacts: list[Contact],
) -> tuple[dict[str, str], Counter]:
    """Classify contacts by role. Returns (email -> role, role counter)."""
    role_map: dict[str, str] = {}
    counter: Counter = Counter()
    for contact in contacts:
        role = classify_contact_role({"title": contact.title})
        role_map[contact.email] = role
        counter[role] += 1
    return role_map, counter


def _build_plans(
    campaign: Campaign,
    contacts: list[Contact],
    role_map: dict[str, str],
    state: dict,
) -> tuple[list[LoadPlan], list[str]]:
    """
    Returns (plans, warnings). Skips contacts whose role has no matching
    sequence in the state file (not yet created, or unknown role).
    """
    warnings: list[str] = []
    sequences = state.get("sequences") or {}

    contacts_with_seq: list[Contact] = []
    for contact in contacts:
        role = role_map.get(contact.email, "other")
        seq_entry = sequences.get(role)
        if not seq_entry or not seq_entry.get("id"):
            warnings.append(
                f"skip {contact.email}: no sequence for role {role!r} yet "
                f"(run --create first or add a variant)"
            )
            continue
        contacts_with_seq.append(contact)

    def sequence_id_for(contact: Contact) -> int:
        role = role_map[contact.email]
        return int(sequences[role]["id"])

    def tags_for(contact: Contact) -> list[str]:
        role = role_map[contact.email]
        return [campaign.tag_template.format(role=role)]

    plans = build_load_plan(
        contacts_with_seq,
        sequence_id_for=sequence_id_for,
        days=[d.isoformat() for d in campaign.drip_days],
        mailbox_id=11,
        tags_for=tags_for,
        group_key=lambda c: c.company,
    )
    return plans, warnings


def _print_plan(
    campaign: Campaign,
    plans: list[LoadPlan],
    role_counter: Counter,
    skipped: list[str],
    warnings: list[str],
    state: dict,
) -> None:
    print()
    print(f"=== PLAN: {campaign.name} ({campaign.slug}) ===")
    print(f"  contacts in plan: {len(plans)}")
    print(f"  role breakdown  : {dict(role_counter)}")
    if skipped:
        print(f"  contacts skipped at hydration: {len(skipped)}")
        for reason in skipped[:10]:
            print(f"    - {reason}")
        if len(skipped) > 10:
            print(f"    ... and {len(skipped) - 10} more")
    if warnings:
        print(f"  plan warnings   : {len(warnings)}")
        for w in warnings[:10]:
            print(f"    - {w}")
        if len(warnings) > 10:
            print(f"    ... and {len(warnings) - 10} more")
    print()

    by_day: dict[str, list[LoadPlan]] = defaultdict(list)
    for plan in plans:
        by_day[plan.day_bucket].append(plan)

    sequences = state.get("sequences") or {}
    role_by_seq_id = {str(v.get("id")): role for role, v in sequences.items()}

    for day in sorted(by_day.keys()):
        print(f"  [{day}] {len(by_day[day])} contacts:")
        for plan in by_day[day]:
            seq_role = role_by_seq_id.get(str(plan.sequence_id), "?")
            print(
                f"    - {plan.contact.first_name} {plan.contact.last_name} "
                f"<{plan.contact.email}>  |  role={seq_role}  |  "
                f"company={plan.contact.company}"
            )
    print()


def _drift_check(campaign: Campaign, md_path: Path, state: dict, force: bool) -> bool:
    expected = state.get("campaign_file_sha1")
    if not expected:
        return True
    current = _sha1_of_file(md_path)
    if current == expected:
        return True
    print()
    print("=== DRIFT DETECTED ===")
    print("The campaign markdown file was edited after --create ran.")
    print(f"  expected sha1: {expected}")
    print(f"  current  sha1: {current}")
    print(
        "The sequences in Outreach no longer match the campaign file. "
        "Re-run --create to rebuild, or use --force to proceed anyway."
    )
    print()
    return force


def cmd_preview_or_execute(
    campaign: Campaign,
    md_path: Path,
    *,
    execute: bool,
    dry_run: bool,
    force: bool,
    args,
) -> int:
    rows = _load_contacts(args)
    if not rows:
        print("No contacts provided. Use --contacts-csv <path> or --contacts-stdin.")
        return 2

    contacts: list[Contact] = []
    skipped: list[str] = []
    for row in rows:
        contact, reason = _hydrate_contact(row)
        if contact is None:
            skipped.append(f"{row.get('email', '?')}: {reason}")
        else:
            contacts.append(contact)

    if not contacts:
        print(f"All {len(rows)} contacts failed hydration. First few reasons:")
        for s in skipped[:5]:
            print(f"  - {s}")
        return 2

    role_map, role_counter = _classify_and_route(contacts)

    state = _read_state(state_path(campaign.slug))
    if execute:
        if not _drift_check(campaign, md_path, state, force):
            return 2

    plans, warnings = _build_plans(campaign, contacts, role_map, state)
    _print_plan(campaign, plans, role_counter, skipped, warnings, state)

    if not execute:
        print("(preview mode — no Outreach writes)")
        return 0

    if dry_run:
        print("--dry-run: would execute the plan above. No Outreach writes.")
        return 0

    if not plans:
        print("No plans to execute (nothing routed to a created sequence).")
        return 0

    target_day = datetime.now().date().isoformat()
    summary = execute_load_plan(
        plans,
        state_path=str(state_path(campaign.slug).with_suffix(".load.json")),
        audit_path=str(audit_path(campaign.slug)),
        target_day=target_day,
        sleep_seconds=campaign.sleep_seconds,
        verify_sequence_active=True,
        dry_run=False,
    )

    state.setdefault("load_runs", []).append({
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "target_day": target_day,
        "summary": summary,
    })
    _write_state_atomic(state_path(campaign.slug), state)

    print()
    print("=== EXECUTE SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


# ── Main ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generalized campaign loader for Outreach.io",
    )
    parser.add_argument("--campaign", required=True, help="campaign slug (campaigns/<slug>.md)")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="build load plan + print, no API calls")
    mode.add_argument("--create", action="store_true", help="create Outreach sequences for each variant")
    mode.add_argument("--execute", action="store_true", help="load contacts into the already-created sequences")

    parser.add_argument("--dry-run", action="store_true", help="preflight + plan only; no Outreach writes")
    parser.add_argument("--force", action="store_true", help="bypass drift check on --execute")
    parser.add_argument("--contacts-csv", help="path to a CSV of contacts")
    parser.add_argument("--contacts-stdin", action="store_true", help="read contact CSV from stdin")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    md = campaign_md_path(args.campaign)
    if not md.exists():
        print(f"campaign file not found: {md}")
        return 2

    try:
        campaign = load_campaign_file(md)
    except CampaignFileError as e:
        print(f"campaign file parse error: {e}")
        return 2

    print(f"loaded campaign: {campaign.name} ({campaign.slug})")
    print(f"  variants: {campaign.variant_roles()}")
    print(f"  schedule_id: {campaign.schedule_id}")
    print(f"  drip_days: {[d.isoformat() for d in campaign.drip_days]}")

    if args.create:
        return cmd_create(campaign, md, dry_run=args.dry_run)

    return cmd_preview_or_execute(
        campaign,
        md,
        execute=args.execute,
        dry_run=args.dry_run,
        force=args.force,
        args=args,
    )


if __name__ == "__main__":
    raise SystemExit(main())
