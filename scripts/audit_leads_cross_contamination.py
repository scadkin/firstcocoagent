#!/usr/bin/env python3
"""BUG 5 Phase 4 — historical audit of Leads from Research.

Fingerprints every row in the tab using the SAME helpers that the Stage 1
page filter, Stage 2 contact filter, and strengthened L10 use in production.
No per-job target_domain lookup (we don't have it for historical rows) —
instead derives target_hint from the District Name column.

Gated by:
  1. Known-bad oracle: loads scripts/bug5_oracle_archdiocese.json and
     verifies the 2 ROWVA + CHSD218 rows fingerprint as source_mismatch
     or both_mismatch. If not, the rule has regressed — exits nonzero.
  2. Clean spot-check: loads scripts/bug5_oracle_clean_sample.json and
     verifies all 20 sample rows fingerprint as clean_*. If not, false
     positive detected — exits nonzero.

Output: grouped counts + top contaminated districts + per-bucket samples,
written to stdout AND a Google Doc via gas_bridge.create_google_doc().
"""
import os, json, sys
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter, defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from tools.research_engine import ResearchJob, _GENERIC_EMAIL_ROOTS

_GENERIC_HOSTS = frozenset({
    "linkedin.com", "www.linkedin.com",
    "facebook.com", "www.facebook.com",
    "twitter.com", "x.com", "www.twitter.com",
    "goffinstrategygroup.com", "tips-usa.com",
})


def fingerprint(row: dict) -> tuple[str, str]:
    """Classify a row into (code, reason). Mutually exclusive, checked in order."""
    email = (row.get("Email") or "").strip().lower()
    source_url = (row.get("Source URL") or "").strip()
    district = (row.get("District Name") or "").strip()

    if not email and not source_url:
        return ("no_data", "both Email and Source URL are empty")

    target_hint = ResearchJob._district_name_hint(district)
    if len(target_hint) < 5:
        return ("ambiguous", f"target_hint too short: {target_hint!r}")

    source_host = urlparse(source_url).netloc.lower().replace("www.", "") if source_url else ""
    email_domain = email.rsplit("@", 1)[1] if "@" in email else ""
    email_local_root = email_domain.split(".")[0] if email_domain else ""

    source_matches = target_hint in source_host if source_host else False
    email_matches = target_hint in email_domain if email_domain else False
    source_is_school = ResearchJob._is_school_host(source_host) if source_host else False
    email_is_school = ResearchJob._is_school_host(email_domain) if email_domain else False

    is_generic_email = email_local_root in _GENERIC_EMAIL_ROOTS or email_domain in _GENERIC_HOSTS
    is_generic_source = source_host in _GENERIC_HOSTS or not source_is_school

    # Clean paths
    if source_matches and email_matches:
        return ("clean_both", "source host and email domain both match target hint")
    if source_matches:
        return ("clean_source", "source host matches; email generic/unknown")
    if email_matches:
        return ("clean_email", "email domain matches; source generic/unknown")

    # Mismatch paths
    source_mismatch = source_is_school and not source_matches
    email_mismatch = email_is_school and not email_matches and not is_generic_email

    if source_mismatch and email_mismatch:
        return ("both_mismatch", f"source={source_host} email={email_domain} target_hint={target_hint}")
    if source_mismatch:
        return ("source_mismatch", f"school-like source {source_host} doesn't contain {target_hint}")
    if email_mismatch:
        return ("email_mismatch", f"school-like email {email_domain} doesn't contain {target_hint}")

    if is_generic_email:
        return ("generic", f"personal-generic email domain {email_domain}")

    return ("ambiguous", f"neither clean nor clearly mismatched — source={source_host} email={email_domain}")


def run_oracle_gates():
    """Hard gates: re-validate the helpers against the Phase 0 oracles."""
    archdiocese_path = ROOT / "scripts" / "bug5_oracle_archdiocese.json"
    clean_path = ROOT / "scripts" / "bug5_oracle_clean_sample.json"

    if not archdiocese_path.exists() or not clean_path.exists():
        sys.exit("ORACLE FILES MISSING. Run scripts/bug5_phase0_scan.py first.")

    archdiocese = json.loads(archdiocese_path.read_text())
    clean_sample = json.loads(clean_path.read_text())

    # Known-bad gate: the 2 ROWVA + CHSD rows must fingerprint as source_mismatch or both_mismatch
    for row in archdiocese:
        if row.get("expected") != "drop":
            continue
        code, reason = fingerprint(row)
        if code not in ("source_mismatch", "email_mismatch", "both_mismatch"):
            sys.exit(
                f"KNOWN-BAD GATE FAILED: row {row.get('__row__')} "
                f"({row.get('First Name')} {row.get('Last Name')} / {row.get('Email')}) "
                f"fingerprinted as {code!r} — expected mismatch. Reason: {reason}"
            )

    # Clean spot-check gate: all 20 clean sample rows must fingerprint as clean_*
    for row in clean_sample:
        code, reason = fingerprint(row)
        if not code.startswith("clean_"):
            sys.exit(
                f"CLEAN SPOT-CHECK GATE FAILED: row {row.get('__row__')} "
                f"({row.get('Email')}) fingerprinted as {code!r} — expected clean_*. "
                f"Reason: {reason}"
            )

    print(f"✅ Oracle gates passed: {len(archdiocese)} archdiocese + {len(clean_sample)} clean")


def main():
    run_oracle_gates()

    creds = Credentials.from_service_account_info(
        json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
    )
    svc = build('sheets', 'v4', credentials=creds)
    sheet_id = os.environ['GOOGLE_SHEETS_ID']

    resp = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="'Leads from Research'!A1:K5000"
    ).execute()
    values = resp.get('values', [])
    headers = values[0]
    print(f"\nTotal rows in Leads from Research: {len(values) - 1}\n")

    rows = []
    for i, row in enumerate(values[1:], start=2):
        d = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}
        d["__row__"] = i
        rows.append(d)

    # Fingerprint every row
    results = []
    for row in rows:
        code, reason = fingerprint(row)
        results.append({"row": row, "code": code, "reason": reason})

    # Grouped counts
    counts = Counter(r["code"] for r in results)
    print("=" * 70)
    print("GROUPED COUNTS")
    print("=" * 70)
    for code in ("clean_both", "clean_source", "clean_email", "generic",
                 "no_data", "ambiguous", "source_mismatch", "email_mismatch",
                 "both_mismatch"):
        n = counts.get(code, 0)
        marker = "⚠️ " if "mismatch" in code else "  "
        print(f"  {marker}{code:<20} {n:>5}")
    print()

    # Per-district contamination breakdown
    district_contam = defaultdict(lambda: {"total": 0, "mismatch": 0})
    for r in results:
        dn = r["row"].get("District Name", "")
        district_contam[dn]["total"] += 1
        if "mismatch" in r["code"]:
            district_contam[dn]["mismatch"] += 1

    sorted_d = sorted(
        district_contam.items(),
        key=lambda kv: (-kv[1]["mismatch"], -kv[1]["total"]),
    )
    print("=" * 70)
    print("TOP DISTRICTS BY CONTAMINATION COUNT")
    print("=" * 70)
    for dn, stats in sorted_d[:15]:
        if stats["mismatch"] > 0 or stats["total"] > 20:
            print(f"  {stats['mismatch']:>3} / {stats['total']:<4}  {dn}")
    print()

    # Sample rows per mismatch bucket
    print("=" * 70)
    print("SAMPLE MISMATCH ROWS (first 5 per bucket)")
    print("=" * 70)
    for code in ("source_mismatch", "email_mismatch", "both_mismatch"):
        samples = [r for r in results if r["code"] == code][:5]
        if not samples:
            continue
        print(f"\n--- {code} ({counts[code]} total) ---")
        for s in samples:
            row = s["row"]
            print(f"  row {row['__row__']}: {row.get('First Name','')} {row.get('Last Name','')}")
            print(f"    District Name: {row.get('District Name','')}")
            print(f"    Email: {row.get('Email','')}")
            print(f"    Source URL: {row.get('Source URL','')[:80]}")
            print(f"    Reason: {s['reason']}")

    print()

    # Optionally write to Google Doc via GAS bridge
    try:
        from tools.gas_bridge import GASBridge
        webhook = os.environ.get("GAS_WEBHOOK_URL")
        secret = os.environ.get("GAS_SECRET_TOKEN")
        if webhook and secret:
            gas = GASBridge(webhook_url=webhook, secret_token=secret)
            # Assemble full report
            lines = [
                f"Research Contamination Audit — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"",
                f"Total rows: {len(rows)}",
                f"",
                f"=== GROUPED COUNTS ===",
            ]
            for code in ("clean_both", "clean_source", "clean_email", "generic",
                         "no_data", "ambiguous", "source_mismatch",
                         "email_mismatch", "both_mismatch"):
                n = counts.get(code, 0)
                marker = "⚠️ " if "mismatch" in code else ""
                lines.append(f"  {marker}{code}: {n}")
            lines.append("")
            lines.append("=== TOP CONTAMINATED DISTRICTS ===")
            for dn, stats in sorted_d[:15]:
                if stats["mismatch"] > 0 or stats["total"] > 20:
                    lines.append(f"  {stats['mismatch']} / {stats['total']}  {dn}")
            lines.append("")
            lines.append("=== SAMPLE MISMATCH ROWS ===")
            for code in ("source_mismatch", "email_mismatch", "both_mismatch"):
                samples = [r for r in results if r["code"] == code][:5]
                if samples:
                    lines.append(f"\n--- {code} ({counts[code]} total) ---")
                    for s in samples:
                        row = s["row"]
                        lines.append(f"  row {row['__row__']}: {row.get('First Name','')} {row.get('Last Name','')}")
                        lines.append(f"    District Name: {row.get('District Name','')}")
                        lines.append(f"    Email: {row.get('Email','')}")
                        lines.append(f"    Source URL: {row.get('Source URL','')[:100]}")
                        lines.append(f"    Reason: {s['reason']}")
            doc_content = "\n".join(lines)
            doc_result = gas.create_google_doc(
                title=f"Research Contamination Audit — {datetime.now().strftime('%Y-%m-%d %H%M')}",
                content=doc_content,
                folder_id="",
            )
            if doc_result.get("success"):
                print(f"📄 Google Doc: {doc_result.get('url')}")
            else:
                print(f"Google Doc creation failed: {doc_result}")
        else:
            print("GAS webhook not configured — skipping Google Doc creation")
    except Exception as e:
        print(f"Google Doc creation error: {e}")

    print("\n✅ Audit complete")


if __name__ == "__main__":
    main()
