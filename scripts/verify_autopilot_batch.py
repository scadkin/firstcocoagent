"""
verify_autopilot_batch.py — S75 first-live-run pre-flight verifier.

Read-only. No Outreach POST/PATCH. No pool mutation. No sheet writes.

Walks the first N candidates of a strategy/cohort in the same order the
autopilot would pick them (pool insertion order) and runs three layers of
checks:

  Layer 1 — ROUTING CORRECTNESS (hard-abort if any miss)
    Looks up the SF-Leads row by email, confirms Lead Source ∈ the cohort's
    authoritative source whitelist. A miss implies the classifier wrote the
    wrong cohort bucket and Phase B MUST NOT proceed.

  Layer 2 — HARD-SKIP (what autopilot would skip on a live run)
    - not_in_outreach         → find_prospect_by_email returns None
    - touched_within_90d      → prospects/<id>.attributes.touchedAt < 90d
    - already_in_dre_cohort   → /sequenceStates include=sequence carries
                                 a dre-2026-spring tag

  Layer 3 — SOFT-FLAG (review signal; does not auto-skip)
    - email_malformed         → fails basic regex
    - email_typo_tld          → ends in .con/.cpm/.nte/.orge/.ocm
    - encoding_issue          → ? in name or codepoint > 0x017F
    - company_is_email        → @ in company string
    - active_district_match   → fuzzy match ≥0.8 to an active *district*
                                 account (BUG 5 surface)

Usage:
  .venv/bin/python scripts/verify_autopilot_batch.py \\
      --strategy dre --cohort LQD-Universal --n 80 [--verbose]

Exits:
  0 — clean (or clean-with-flags under decision thresholds)
  1 — systematic regression / Layer 1 failure / operational error
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env_or_die  # noqa: E402

load_env_or_die(required=[])

from tools.campaign_autopilot import (  # noqa: E402
    _get_prospect_touched_at,
    _is_recent_activity,
    _prospect_has_active_dre_cohort_state,
)
from tools.campaign_pool import load_pool  # noqa: E402
from tools.lead_filters import (  # noqa: E402
    INT_SOURCES,
    LQD_SOURCES,
    TC_SOURCES,
    read_sf_leads_rows,
)
from tools.outreach_client import find_prospect_by_email  # noqa: E402
from tools.csv_importer import (  # noqa: E402
    get_active_accounts,
    normalize_name,
    fuzzy_match_name,
)

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
TYPO_TLDS = (".con", ".cpm", ".nte", ".orge", ".ocm")

COHORT_SOURCES: dict[str, frozenset[str]] = {
    "LQD-Universal": LQD_SOURCES,
    "INT-Universal": INT_SOURCES,
    "INT-Teacher": INT_SOURCES,
    # TC-* cohorts share TC_SOURCES; add as needed when those cohorts open.
    "TC-Universal-Residual": TC_SOURCES,
    "TC-MS": TC_SOURCES,
    "TC-HS": TC_SOURCES,
    "TC-Elem": TC_SOURCES,
    "TC-Virtual": TC_SOURCES,
    "TC-District": TC_SOURCES,
    "TC-All-Grades": TC_SOURCES,
    "TC-Teacher": TC_SOURCES,
    # LIB + IT-ReEngage route by title, not source — skip Layer 1 for them.
}


@dataclass
class CandidateResult:
    email: str
    first_name: str
    last_name: str
    company: str
    state: str
    # Layer 1
    sf_row_found: bool = False
    lead_source_raw: str = ""
    layer1_pass: bool = False
    # Layer 2
    prospect_id: Optional[str] = None
    not_in_outreach: bool = False
    touched_at: Optional[str] = None
    touched_within_90d: bool = False
    already_in_dre_cohort: bool = False
    # Layer 3
    soft_flags: list[str] = field(default_factory=list)
    soft_details: dict[str, str] = field(default_factory=dict)

    @property
    def hard_skip_reason(self) -> Optional[str]:
        if self.not_in_outreach:
            return "not_in_outreach"
        if self.touched_within_90d:
            return "touched_within_90d"
        if self.already_in_dre_cohort:
            return "already_in_dre_cohort"
        return None

    @property
    def clean(self) -> bool:
        return self.layer1_pass and self.hard_skip_reason is None


# ── Layer 3 checks ─────────────────────────────────────────────────────

def _soft_check_email(email: str) -> list[tuple[str, str]]:
    flags: list[tuple[str, str]] = []
    low = (email or "").strip().lower()
    if not low or not EMAIL_RE.match(low):
        flags.append(("email_malformed", low))
    for tld in TYPO_TLDS:
        if low.endswith(tld):
            flags.append(("email_typo_tld", f"endswith {tld}"))
            break
    return flags


def _soft_check_name(first: str, last: str) -> list[tuple[str, str]]:
    combo = f"{first} {last}"
    if "?" in combo:
        return [("encoding_issue", f"'?' in name: {combo!r}")]
    for ch in combo:
        if ord(ch) > 0x017F:
            return [("encoding_issue", f"high codepoint U+{ord(ch):04X} in name: {combo!r}")]
    return []


def _soft_check_company(company: str) -> list[tuple[str, str]]:
    if "@" in (company or ""):
        return [("company_is_email", company)]
    return []


def _build_active_account_index() -> tuple[dict, dict]:
    """Return (name_key_to_account_dict, name_key_set_for_fuzzy).

    fuzzy_match_name expects a dict of candidate keys → value; we keep the
    account dict as the value so we can reach Account Type after matching.
    """
    accounts = get_active_accounts()
    idx: dict[str, dict] = {}
    for acct in accounts:
        display = (acct.get("Display Name") or "").strip()
        if not display:
            continue
        key = normalize_name(display)
        if not key:
            continue
        # First writer wins; dupes are rare enough to ignore
        idx.setdefault(key, acct)
    return idx, {k: True for k in idx}


def _soft_check_active_account(
    company: str, account_idx: dict[str, dict], fuzzy_pool: dict
) -> list[tuple[str, str]]:
    if not company:
        return []
    q = normalize_name(company)
    if not q:
        return []
    match_key = fuzzy_match_name(q, fuzzy_pool, threshold=0.8)
    if not match_key:
        return []
    acct = account_idx.get(match_key) or {}
    acct_type = (acct.get("Account Type") or "").strip().lower()
    display = acct.get("Display Name") or match_key
    if acct_type == "district":
        return [("active_district_match",
                 f'matched account={display!r} (district)')]
    # School-level customers are not a CSM issue — record but don't trigger
    # the decision-rule pause threshold.
    return [("active_account_match",
             f'matched account={display!r} (Account Type={acct_type or "unknown"})')]


# ── Main walker ────────────────────────────────────────────────────────

def verify(
    strategy_key: str, cohort: str, n: int, verbose: bool = False
) -> tuple[list[CandidateResult], dict]:
    meta: dict = {"strategy_key": strategy_key, "cohort": cohort, "n_requested": n}

    t0 = time.time()
    logger.info("Loading pool for strategy=%s", strategy_key)
    pool = load_pool(strategy_key)
    meta["pool_built_at"] = pool.built_at
    meta["cohort_sizes"] = pool.cohort_sizes()
    bucket = pool.buckets.get(cohort) or []
    if not bucket:
        raise SystemExit(f"pool has no leads in cohort {cohort!r}")
    if len(bucket) < n:
        logger.warning(
            "Cohort %s has only %d leads (requested %d) — will verify all available",
            cohort, len(bucket), n,
        )
    selected = bucket[:n]
    meta["n_selected"] = len(selected)

    # Build SF Leads index
    logger.info("Reading SF Leads into email→row dict")
    from tools.sheets_writer import _get_service
    svc = _get_service()
    rows = read_sf_leads_rows(svc)
    sf_by_email: dict[str, dict] = {}
    for r in rows:
        em = (r.get("email") or "").strip().lower()
        if em:
            sf_by_email.setdefault(em, r)
    meta["sf_leads_rows"] = len(rows)

    # Build active-account fuzzy pool
    logger.info("Building active-account index")
    account_idx, fuzzy_pool = _build_active_account_index()
    meta["active_accounts"] = len(account_idx)

    source_whitelist = COHORT_SOURCES.get(cohort)
    if source_whitelist is None:
        logger.warning(
            "Cohort %s has no Lead Source whitelist mapping — Layer 1 will be skipped",
            cohort,
        )

    results: list[CandidateResult] = []
    for i, lead in enumerate(selected, 1):
        cr = CandidateResult(
            email=lead.email,
            first_name=lead.first_name,
            last_name=lead.last_name,
            company=lead.company,
            state=lead.state,
        )

        # Layer 1 — Routing
        em_key = (lead.email or "").strip().lower()
        sf_row = sf_by_email.get(em_key)
        if sf_row is not None:
            cr.sf_row_found = True
            cr.lead_source_raw = (sf_row.get("lead_source") or "").strip()
            if source_whitelist is None:
                cr.layer1_pass = True
            else:
                low = cr.lead_source_raw.lower()
                cr.layer1_pass = low in source_whitelist
        else:
            cr.layer1_pass = False  # can't verify — treat as routing failure

        # Layer 2 — Outreach state
        prospect = find_prospect_by_email(lead.email)
        if prospect is None:
            cr.not_in_outreach = True
        else:
            cr.prospect_id = prospect.get("prospect_id")
            touched = _get_prospect_touched_at(cr.prospect_id)
            cr.touched_at = touched
            if _is_recent_activity(touched):
                cr.touched_within_90d = True
            elif _prospect_has_active_dre_cohort_state(cr.prospect_id):
                cr.already_in_dre_cohort = True

        # Layer 3 — Soft flags
        for flag, detail in _soft_check_email(lead.email):
            cr.soft_flags.append(flag)
            cr.soft_details[flag] = detail
        for flag, detail in _soft_check_name(lead.first_name, lead.last_name):
            cr.soft_flags.append(flag)
            cr.soft_details[flag] = detail
        for flag, detail in _soft_check_company(lead.company):
            cr.soft_flags.append(flag)
            cr.soft_details[flag] = detail
        for flag, detail in _soft_check_active_account(
            lead.company, account_idx, fuzzy_pool
        ):
            cr.soft_flags.append(flag)
            cr.soft_details[flag] = detail

        results.append(cr)

        if verbose:
            tag = "CLEAN" if cr.clean else (
                cr.hard_skip_reason or ("L1_FAIL" if not cr.layer1_pass else "FLAG")
            )
            print(f"  [{i:>3}] {tag:<24} {lead.email}")

    meta["elapsed_sec"] = round(time.time() - t0, 1)
    return results, meta


# ── Report ─────────────────────────────────────────────────────────────

def _report(results: list[CandidateResult], meta: dict, cohort: str) -> tuple[str, int]:
    """Build the stdout report and return (text, exit_code)."""
    n = len(results)
    l1_pass = sum(1 for r in results if r.layer1_pass)
    l1_fail = n - l1_pass

    hard_counts: dict[str, int] = {
        "not_in_outreach": 0,
        "touched_within_90d": 0,
        "already_in_dre_cohort": 0,
    }
    soft_counts: dict[str, int] = {}
    clean_rows: list[CandidateResult] = []
    hard_rows: list[CandidateResult] = []
    soft_rows: list[CandidateResult] = []

    for r in results:
        hr = r.hard_skip_reason
        if hr:
            hard_counts[hr] += 1
            hard_rows.append(r)
        for f in r.soft_flags:
            soft_counts[f] = soft_counts.get(f, 0) + 1
        # A row can be both hard-skip and soft-flagged; we display it in
        # both sections because Steven may want to eyeball the overlap.
        if r.soft_flags and not hr:
            soft_rows.append(r)
        if r.clean and not r.soft_flags:
            clean_rows.append(r)

    total_hard = sum(hard_counts.values())
    total_soft = sum(1 for r in results if r.soft_flags)
    total_clean = sum(1 for r in results if r.clean and not r.soft_flags)

    lines: list[str] = []
    lines.append(f"PRE-FLIGHT — {meta['strategy_key'].upper()} / {cohort} / first {n} candidates")
    lines.append("─" * 72)
    lines.append(f"Pool built_at: {meta['pool_built_at']}")
    lines.append(
        f"SF Leads rows: {meta['sf_leads_rows']}  Active accounts: {meta['active_accounts']}  "
        f"Elapsed: {meta['elapsed_sec']}s"
    )
    lines.append("")

    # Layer 1
    banner = "✓" if l1_fail == 0 else "✗  HALT"
    src_list = ""
    wl = COHORT_SOURCES.get(cohort)
    if wl:
        src_list = f"  (whitelist has {len(wl)} sources)"
    lines.append(f"LAYER 1 ROUTING:   {l1_pass}/{n} in cohort whitelist  {banner}{src_list}")
    if l1_fail:
        lines.append("  Layer 1 mismatches (routing bug — investigate classifier):")
        for r in results:
            if r.layer1_pass:
                continue
            if not r.sf_row_found:
                lines.append(f"    {r.email}  (NOT FOUND in SF Leads)")
            else:
                lines.append(f"    {r.email}  source={r.lead_source_raw!r}")

    # Layer 2
    lines.append(f"LAYER 2 OUTREACH:  {n}/{n} lookups completed  ✓")
    lines.append("")

    # Counts
    lines.append("COUNTS:")
    lines.append(f"  CLEAN (ready):                  {total_clean}")
    lines.append(f"  HARD-SKIP:                      {total_hard}")
    lines.append(f"    ├─ not_in_outreach:             {hard_counts['not_in_outreach']}")
    lines.append(f"    ├─ touched_within_90d:          {hard_counts['touched_within_90d']}")
    lines.append(f"    └─ already_in_dre_cohort:       {hard_counts['already_in_dre_cohort']}")
    lines.append(f"  SOFT-FLAG rows (review):        {total_soft}")
    for flag in sorted(soft_counts):
        lines.append(f"    ├─ {flag}:{' ' * (28 - len(flag))}{soft_counts[flag]}")
    lines.append("")

    # First 5 clean
    if clean_rows:
        lines.append("First 5 CLEAN:")
        for r in clean_rows[:5]:
            full = f"{r.first_name} {r.last_name}".strip() or "(no name)"
            touched = r.touched_at or "no_touchedAt"
            lines.append(
                f"  {r.email}  ·  {full}  ·  {r.company!r}  ·  "
                f"{r.state}  ·  prospect {r.prospect_id}  ·  touched {touched}"
            )
        lines.append("")

    # All soft-flag details
    flagged_all = [r for r in results if r.soft_flags]
    if flagged_all:
        lines.append(f"All SOFT-FLAG rows ({len(flagged_all)}):")
        for r in flagged_all:
            hard = f" [HARD-SKIP: {r.hard_skip_reason}]" if r.hard_skip_reason else ""
            for f in r.soft_flags:
                lines.append(f"  {r.email}  ·  flag={f}  ·  {r.soft_details.get(f, '')}{hard}")
        lines.append("")

    # Decision
    exit_code, decision = _apply_decision_rules(
        l1_fail, total_clean, total_soft, soft_counts, n
    )
    lines.append("DECISION:")
    lines.append(f"  {decision}")

    return "\n".join(lines), exit_code


def _apply_decision_rules(
    l1_fail: int, clean: int, total_soft: int, soft_counts: dict[str, int], n: int
) -> tuple[int, str]:
    if l1_fail > 0:
        return 1, "HALT — Layer 1 routing failure(s). Do NOT proceed to Phase B."

    max_soft_reason = max(soft_counts.values()) if soft_counts else 0
    active_dm = soft_counts.get("active_district_match", 0)
    pct = lambda c: (c / n * 100.0) if n else 0.0

    warnings: list[str] = []
    if active_dm >= 3:
        warnings.append(
            f"active_district_match={active_dm} ≥ 3 — list for Steven's eyeball (BUG 5 surface)"
        )
    for flag, c in soft_counts.items():
        if pct(c) > 10.0:
            warnings.append(f"{flag} at {c}/{n} ({pct(c):.1f}%) >10% — systematic, investigate")

    if clean < 53:
        return 1, (
            f"CLEAN={clean} < 53 — insufficient. "
            "Rerun at --n 120; if still short, investigate cohort decay."
        )

    if warnings:
        return 1, "PAUSE — " + "; ".join(warnings)

    if total_soft > 5:
        return 0, (
            f"READY (with soft flags to eyeball) — CLEAN={clean} ≥ 53, SOFT={total_soft} >5. "
            "Inspect the SOFT list above; proceed to Phase B only if Steven greenlits."
        )

    return 0, (
        f"READY — CLEAN={clean} ≥ 53, SOFT={total_soft} ≤ 5, no single SOFT reason ≥ 3. "
        "Awaiting Steven's approval before Phase B."
    )


# ── CLI ────────────────────────────────────────────────────────────────

def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strategy", default="dre")
    ap.add_argument("--cohort", default="LQD-Universal")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    results, meta = verify(args.strategy, args.cohort, args.n, verbose=args.verbose)
    text, code = _report(results, meta, args.cohort)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(_main())
