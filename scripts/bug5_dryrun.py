#!/usr/bin/env python3
"""BUG 5 Phase 1 dry-run harness.

Validates the cross-district matching helpers + filter decision rules against
the Archdiocese oracle (2 known-bad + 1 known-good) and the 20-row clean
sample. Hard gate: Phase 2 ships only if every oracle row lands on its
expected side of the filter.

Runs in two modes:
  (a) Simulated filters (default) — reimplements the page-filter and contact-
      filter decision rules inline using the helpers from research_engine.
      This is what runs DURING Phase 1 before the real filter methods exist.
  (b) Live filters (--live) — imports the real ResearchJob methods once
      Commits B/C have landed and re-runs the same oracle.

Both modes MUST produce the same results. If they diverge, Commit B or C
introduced a regression vs the Phase 1 rule.
"""
import argparse, json, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.research_engine import (
    ResearchJob,
    ENABLE_RESEARCH_CONTAM_FILTER,
    _GENERIC_EMAIL_ROOTS,
)

# Treat Archdiocese of Chicago as having target_host = archchicago.org for the
# dry-run. In a real research run, L4 discovers this. We hardcode it here
# because we don't want to hit Serper just to validate the decision rule.
TARGETS = {
    "Archdiocese of Chicago Schools": "archchicago.org",
}


def target_host_for(district_name: str, row: dict) -> str:
    """Pick a target_host for a given row. For the Archdiocese oracle it's
    hardcoded. For the clean sample we infer it from the row's own email
    domain (since the clean sample was picked BECAUSE email+source both
    already matched the hint — which means the row is authoritative about
    its own target)."""
    if district_name in TARGETS:
        return TARGETS[district_name]
    email = row.get("Email", "")
    if "@" in email:
        return email.rsplit("@", 1)[1].lower()
    return ""


def simulated_page_filter(
    host: str, target_host: str, target_hint: str
) -> bool:
    """Return True if the page should be DROPPED.

    Inline simulation of the Stage 1 rule from the plan:
      - host matches target → keep
      - host is school-like and doesn't match → DROP
      - otherwise (generic host) → keep
    """
    if not ENABLE_RESEARCH_CONTAM_FILTER:
        return False
    if not target_host and not target_hint:
        return False
    if ResearchJob._host_matches_target(host, target_host, target_hint):
        return False
    if ResearchJob._is_school_host(host):
        return True
    return False


def simulated_contact_filter(
    row: dict, target_host: str, target_hint: str
) -> tuple[bool, str]:
    """Return (should_drop, reason). Inline simulation of Stage 2."""
    if not ENABLE_RESEARCH_CONTAM_FILTER:
        return (False, "filter_off")
    if not target_host and not target_hint:
        return (False, "no_target")

    email = row.get("Email", "")
    source_url = row.get("Source URL", "")
    host = urlparse(source_url).netloc.lower().replace("www.", "")
    email_domain = email.rsplit("@", 1)[1].lower() if "@" in email else ""

    source_matches = ResearchJob._host_matches_target(host, target_host, target_hint)
    email_matches = ResearchJob._email_domain_matches_target(email, target_host, target_hint)

    if source_matches and email_matches:
        return (False, "both_match")
    if source_matches and email and not email_matches and ResearchJob._is_school_host(email_domain):
        # Legit target page, email links to a different school — caller
        # clears the email. We don't drop.
        return (False, "source_match_email_cleared")
    if source_matches:
        return (False, "source_match")
    if email_matches:
        return (False, "email_match")
    if ResearchJob._is_school_host(host) and not source_matches:
        return (True, "wrong_school_host")
    # Generic host
    if email and ResearchJob._is_school_host(email_domain) and not email_matches:
        return (True, "generic_host_wrong_email_school")
    return (False, "generic_host_keep")


def run_live_mode():
    """Test the real ResearchJob filter methods against the oracle.

    Constructs a fake ResearchJob, manually sets district_domain (skip L4),
    populates raw_pages + all_contacts from the oracle rows, calls the real
    filter methods, and asserts the expected drop/keep pattern.
    """
    archdiocese = json.loads((ROOT / "scripts" / "bug5_oracle_archdiocese.json").read_text())
    clean = json.loads((ROOT / "scripts" / "bug5_oracle_clean_sample.json").read_text())

    # Run Archdiocese oracle through real filters
    job = ResearchJob("Archdiocese of Chicago Schools", "IL")
    job.district_domain = "archchicago.org"

    # Populate raw_pages from archdiocese source URLs (with dummy content)
    job.raw_pages = [(row.get("Source URL", ""), "dummy content") for row in archdiocese]
    before_pages = len(job.raw_pages)
    job._filter_raw_pages_by_domain()
    after_pages = len(job.raw_pages)
    print(f"Stage 1 page filter: {before_pages - after_pages}/{before_pages} pages dropped")

    # Populate all_contacts from archdiocese rows
    job.all_contacts = [
        {
            "first_name": row.get("First Name", ""),
            "last_name": row.get("Last Name", ""),
            "email": row.get("Email", ""),
            "source_url": row.get("Source URL", ""),
            "email_confidence": row.get("Email Confidence", "UNKNOWN"),
            "account": row.get("Account", ""),
            "district_name": row.get("District Name", ""),
        }
        for row in archdiocese
    ]
    before_contacts = len(job.all_contacts)
    job._filter_contacts_by_domain()
    after_contacts = len(job.all_contacts)
    print(f"Stage 2 contact filter: {before_contacts - after_contacts}/{before_contacts} contacts dropped")
    print(f"Counters: pages_filtered={job._contam_pages_filtered} contacts_filtered={job._contam_contacts_filtered}")

    # Check that the known-bad rows are dropped, known-good are kept
    surviving_emails = {c.get("email", "") for c in job.all_contacts}
    expected_surviving = {row.get("Email", "") for row in archdiocese if row.get("expected", "keep") == "keep"}
    expected_dropped = {row.get("Email", "") for row in archdiocese if row.get("expected") == "drop"}

    missing_good = expected_surviving - surviving_emails
    surviving_bad = expected_dropped & surviving_emails

    if missing_good:
        print(f"FAIL: known-good contacts dropped: {missing_good}")
    if surviving_bad:
        print(f"FAIL: known-bad contacts survived: {surviving_bad}")
    if not missing_good and not surviving_bad:
        print("PASS: Archdiocese oracle — known-bad dropped, known-good kept")

    # Clean sample — run each through a fresh job per district since district_domain varies
    clean_fails = []
    for row in clean:
        district = row.get("District Name", "")
        email = row.get("Email", "")
        # Infer target_host from the row's own email domain (clean sample was
        # selected because email domain already contains the district hint)
        target_host = email.rsplit("@", 1)[1].lower() if "@" in email else ""
        job2 = ResearchJob(district, row.get("State", ""))
        job2.district_domain = target_host
        job2.all_contacts = [{
            "first_name": row.get("First Name", ""),
            "last_name": row.get("Last Name", ""),
            "email": email,
            "source_url": row.get("Source URL", ""),
            "email_confidence": row.get("Email Confidence", "UNKNOWN"),
        }]
        job2._filter_contacts_by_domain()
        if len(job2.all_contacts) != 1:
            clean_fails.append(row)

    if clean_fails:
        print(f"\nFAIL: {len(clean_fails)}/{len(clean)} clean sample rows were dropped:")
        for r in clean_fails:
            print(f"  row {r['__row__']}: {r.get('Email','')} host={r.get('Source URL','')[:60]}")
        sys.exit(1)
    print(f"PASS: all {len(clean)} clean sample rows kept")

    if missing_good or surviving_bad or clean_fails:
        sys.exit("LIVE MODE HARD GATE FAILED")
    print("\nLIVE MODE HARD GATE PASSED — real filter methods match Phase 1 simulation.")


def run_oracle(rows: list[dict], oracle_name: str) -> list[dict]:
    """Run every row through both the simulated page filter and simulated
    contact filter. Record what happens and whether it matches `expected`.
    """
    results = []
    for row in rows:
        district = row.get("District Name", "")
        target_host = target_host_for(district, row)
        target_hint = ResearchJob._district_name_hint(district)
        source_url = row.get("Source URL", "")
        host = urlparse(source_url).netloc.lower().replace("www.", "")

        page_dropped = simulated_page_filter(host, target_host, target_hint)
        contact_dropped, contact_reason = simulated_contact_filter(row, target_host, target_hint)

        any_dropped = page_dropped or contact_dropped
        expected = row.get("expected", "keep")
        ok = (any_dropped and expected == "drop") or (not any_dropped and expected == "keep")

        results.append({
            "oracle": oracle_name,
            "__row__": row.get("__row__"),
            "first_name": row.get("First Name", ""),
            "last_name": row.get("Last Name", ""),
            "email": row.get("Email", ""),
            "source_host": host,
            "district": district,
            "target_host": target_host,
            "target_hint": target_hint,
            "page_dropped": page_dropped,
            "contact_dropped": contact_dropped,
            "contact_reason": contact_reason,
            "final_action": "drop" if any_dropped else "keep",
            "expected": expected,
            "ok": ok,
        })
    return results


def print_results(results: list[dict]):
    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    print(f"\n{'=' * 70}")
    print(f"Oracle pass/fail: {len(oks)}/{len(results)} OK, {len(fails)} failures")
    print(f"{'=' * 70}")
    for r in results:
        mark = "OK" if r["ok"] else "FAIL"
        action = r["final_action"]
        expected = r["expected"]
        print(
            f"  [{mark:4}] row {r['__row__']:<4} "
            f"exp={expected:<4} act={action:<4}  "
            f"{r['first_name']} {r['last_name']} | {r['email']:<40} | "
            f"host={r['source_host'][:30]:<30} "
            f"page={'D' if r['page_dropped'] else '.'} "
            f"contact={'D' if r['contact_dropped'] else '.'}"
            f"  ({r['contact_reason']})"
        )
    if fails:
        print(f"\n{len(fails)} failures:")
        for f in fails:
            print(json.dumps(f, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="Use real ResearchJob filter methods (post Commits B/C)")
    args = ap.parse_args()
    if args.live:
        print("=== LIVE MODE: testing real ResearchJob filter methods ===\n")
        run_live_mode()
        return

    # Load oracles
    archdiocese_path = ROOT / "scripts" / "bug5_oracle_archdiocese.json"
    clean_path = ROOT / "scripts" / "bug5_oracle_clean_sample.json"
    if not archdiocese_path.exists() or not clean_path.exists():
        sys.exit(f"Oracle files missing. Run scripts/bug5_phase0_scan.py first.")

    archdiocese = json.loads(archdiocese_path.read_text())
    clean = json.loads(clean_path.read_text())
    print(f"Loaded {len(archdiocese)} Archdiocese rows + {len(clean)} clean-sample rows")

    # Quick helper sanity checks
    print("\n--- Helper unit tests ---")
    tests = [
        # (district_name, expected_hint)
        ("Austin ISD", "austin"),
        ("Pittsburgh Public Schools", "pittsburgh"),
        ("Archdiocese of Chicago Schools", "chicago"),
        ("Park Ridge", "parkridge"),  # 9 chars — passes min length
        ("Park ISD", ""),              # "park" after stripping — 4 chars, too short
        ("Columbus City Schools", "columbus"),
        ("Coppell ISD", "coppell"),
        ("Kern High School District", "kernhigh"),
        ("Epic Charter School", "epiccharterschool"),  # no strip rule applies — "school" not " schools"
        ("", ""),
    ]
    hint_fails = 0
    for name, expected in tests:
        actual = ResearchJob._district_name_hint(name)
        ok = actual == expected
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark:4}] _district_name_hint({name!r}) → {actual!r} (expected {expected!r})")
        if not ok: hint_fails += 1

    school_host_tests = [
        ("rowva.k12.il.us", True),
        ("chsd218.org", True),                # chsd pattern
        ("austinisd.org", True),              # isd pattern
        ("archchicago.org", False),           # diocesan central office, not school — OK (email match handles archchicago contacts)
        ("goffinstrategygroup.com", False),
        ("linkedin.com", False),
        ("nces.ed.gov", False),               # federal, not school
        ("cde.ca.gov", False),                # state DOE, not school
        ("epiccharterschools.org", True),     # charter + schools
        ("cvusd.org", True),                  # cvusd → matches "cusd" substring, accepted
    ]
    print("\n--- _is_school_host tests ---")
    for host, expected in school_host_tests:
        actual = ResearchJob._is_school_host(host)
        ok = actual == expected
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark:4}] _is_school_host({host!r}) → {actual} (expected {expected})")

    print()
    # Run oracles
    arch_results = run_oracle(archdiocese, "archdiocese")
    clean_results = run_oracle(clean, "clean")
    print_results(arch_results + clean_results)

    arch_fails = [r for r in arch_results if not r["ok"]]
    clean_fails = [r for r in clean_results if not r["ok"]]
    total_fails = len(arch_fails) + len(clean_fails)

    print(f"\n{'=' * 70}")
    print(f"FINAL: Archdiocese {len(archdiocese) - len(arch_fails)}/{len(archdiocese)} OK, "
          f"Clean {len(clean) - len(clean_fails)}/{len(clean)} OK")
    print(f"{'=' * 70}")

    if total_fails or hint_fails:
        sys.exit(f"\nHARD GATE FAILED: {total_fails} oracle failures + {hint_fails} helper failures")
    print("\nHARD GATE PASSED — Phase 2 may begin.")


if __name__ == "__main__":
    main()
