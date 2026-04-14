"""
Aggregate /tmp/scout_ab_results.jsonl into a pass/fail summary table.

Usage:
    .venv/bin/python scripts/ab_analyze.py
    .venv/bin/python scripts/ab_analyze.py /tmp/scout_ab_results.jsonl
"""
import json
import sys


def main(path: str) -> int:
    try:
        with open(path) as f:
            records = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"No results file at {path}")
        return 1

    if not records:
        print(f"Empty results file at {path}")
        return 1

    print(f"Aggregating {len(records)} A/B runs from {path}\n")

    header = (
        f"  {'district':<35} {'v1 $':>8} {'v2 $':>8} {'Δ%':>7} "
        f"{'v1 ver':>7} {'v2 ver':>7} {'v1 s':>6} {'v2 s':>6} {'gate':>5}"
    )
    print(header)
    print("-" * len(header))

    total_v1_cost = 0.0
    total_v2_cost = 0.0
    overall_pass = 0
    overall_fail = 0

    for r in records:
        v1 = r.get("v1", {}) or {}
        v2 = r.get("v2", {}) or {}
        gates = r.get("pass_fail", {}) or {}

        district = r.get("district", "?")[:35]
        v1_cost = v1.get("cost_total_usd", 0) or 0
        v2_cost = v2.get("cost_total_usd", 0) or 0
        delta_pct = ((v2_cost - v1_cost) / v1_cost * 100) if v1_cost else 0
        v1_ver = v1.get("contacts_verified", 0)
        v2_ver = v2.get("contacts_verified", 0)
        v1_wc = v1.get("wall_clock_seconds", 0)
        v2_wc = v2.get("wall_clock_seconds", 0)
        gate = "PASS" if gates.get("overall") else "FAIL"

        print(
            f"  {district:<35} "
            f"{v1_cost:>8.4f} {v2_cost:>8.4f} {delta_pct:>+6.1f}% "
            f"{v1_ver:>7} {v2_ver:>7} {v1_wc:>6} {v2_wc:>6} {gate:>5}"
        )

        total_v1_cost += v1_cost
        total_v2_cost += v2_cost
        if gates.get("overall"):
            overall_pass += 1
        else:
            overall_fail += 1

    print("-" * len(header))
    print(f"\n  totals: v1=${total_v1_cost:.4f}  v2=${total_v2_cost:.4f}  "
          f"Δ={(total_v2_cost - total_v1_cost):+.4f}  "
          f"(v2 is {(total_v2_cost/total_v1_cost*100 if total_v1_cost else 0):.1f}% of v1)")
    print(f"  gate results: {overall_pass} pass / {overall_fail} fail")
    print()

    if overall_fail == 0 and overall_pass > 0:
        print("  ROUND 1 VERDICT: all gates PASS — ready to advance to Round 2 planning")
        return 0
    elif overall_fail > 0:
        print("  ROUND 1 VERDICT: at least one gate FAILED — investigate before advancing")
        return 1
    return 1


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/scout_ab_results.jsonl"
    sys.exit(main(path))
