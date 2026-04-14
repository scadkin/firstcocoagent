"""
Research engine A/B harness — v1 (flags off) vs v1 (Round 1 flags on).

Runs two ResearchJob instances serially against the same target and captures:
  - real per-call Claude token usage via response.usage
  - exact Serper query count from the result dict
  - Exa / Brave query count approximated from layers_used / skipped_layers
  - wall clock elapsed
  - full contact diff (shared, v1-only, v2-only)

Writes one structured JSONL record per A/B run to /tmp/scout_ab_results.jsonl.
Enforces a --max-cost-usd ceiling so debugging runs can't burn unlimited money.

Both engines run serially with a 30-second delay between them to avoid
clipping Serper's 60/min rate limit and to minimize noise from network
variance.

Usage:
    .venv/bin/python scripts/ab_research_engine.py \\
        --district "Waverly School District 145" --state NE \\
        --max-cost-usd 5.0 --delay-seconds 30

Not a test runner — just an instrumentation script. No production writes.
"""
import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from tools.research_engine import ResearchJob  # noqa: E402


# ─────────────────────────────────────────────
# Pricing constants (2026 rates)
# ─────────────────────────────────────────────
# Claude Sonnet 4.6: $3/M input, $15/M output (standard, no caching)
_CLAUDE_INPUT_PER_TOKEN = 3.0 / 1_000_000
_CLAUDE_OUTPUT_PER_TOKEN = 15.0 / 1_000_000

# Flat-rate search APIs
_SERPER_PER_QUERY = 0.001
_EXA_PER_QUERY = 0.005
_BRAVE_PER_QUERY = 0.005

# Exa/Brave query counts aren't tracked by the engine; we infer from
# layers_used. L16 fires up to 4 broad queries when active, L17 up to 4
# domain queries, L20 fires 1 brave query. Skipped layers fire 0.
_EXA_L16_QUERIES = 4
_EXA_L17_QUERIES = 4
_BRAVE_L20_QUERIES = 1

_RESULTS_PATH = "/tmp/scout_ab_results.jsonl"


def _layer_fired(result: dict, layer_tag: str) -> bool:
    layers_used = result.get("layers_used") or ""
    skipped = set(result.get("skipped_layers") or [])
    return layer_tag in layers_used and not any(
        layer_tag.split(":")[0] in s for s in skipped
    )


def _exa_query_estimate(result: dict) -> int:
    n = 0
    if _layer_fired(result, "L16:exa-broad"):
        n += _EXA_L16_QUERIES
    if _layer_fired(result, "L17:exa-domain"):
        n += _EXA_L17_QUERIES
    return n


def _brave_query_estimate(result: dict) -> int:
    return _BRAVE_L20_QUERIES if _layer_fired(result, "L20:brave") else 0


def _compute_costs(result: dict) -> dict:
    usage_records = result.get("claude_usage") or []
    claude_input = sum(r.get("input_tokens", 0) for r in usage_records)
    claude_output = sum(r.get("output_tokens", 0) for r in usage_records)
    claude_cost = (
        claude_input * _CLAUDE_INPUT_PER_TOKEN
        + claude_output * _CLAUDE_OUTPUT_PER_TOKEN
    )

    serper_queries = result.get("queries_used", 0)
    serper_cost = serper_queries * _SERPER_PER_QUERY

    exa_queries = _exa_query_estimate(result)
    exa_cost = exa_queries * _EXA_PER_QUERY

    brave_queries = _brave_query_estimate(result)
    brave_cost = brave_queries * _BRAVE_PER_QUERY

    total = claude_cost + serper_cost + exa_cost + brave_cost

    return {
        "claude_calls": len(usage_records),
        "claude_input_tokens": claude_input,
        "claude_output_tokens": claude_output,
        "cost_claude_usd": round(claude_cost, 4),
        "cost_serper_usd": round(serper_cost, 4),
        "cost_exa_usd": round(exa_cost, 4),
        "cost_brave_usd": round(brave_cost, 4),
        "cost_total_usd": round(total, 4),
    }


def _summarize(result: dict) -> dict:
    contacts = result.get("contacts") or []
    costs = _compute_costs(result)
    return {
        "status": "success",
        "contacts_total": result.get("total", len(contacts)),
        "contacts_verified": result.get("verified", 0),
        "contacts_with_email": result.get("with_email", 0),
        "queries_used": result.get("queries_used", 0),
        "wall_clock_seconds": result.get("elapsed_seconds", 0),
        "layers_used": result.get("layers_used", ""),
        "skipped_layers": result.get("skipped_layers") or [],
        "pages_filtered": result.get("pages_filtered", 0),
        "contacts_filtered": result.get("contacts_filtered", 0),
        **costs,
    }


def _contact_key(c: dict) -> tuple[str, str]:
    return (
        (c.get("first_name") or "").strip().lower(),
        (c.get("last_name") or "").strip().lower(),
    )


def _diff_contacts(v1_result: dict, v2_result: dict) -> dict:
    v1_contacts = {_contact_key(c): c for c in v1_result.get("contacts") or []}
    v2_contacts = {_contact_key(c): c for c in v2_result.get("contacts") or []}

    shared_keys = set(v1_contacts) & set(v2_contacts)
    v1_only = sorted(set(v1_contacts) - set(v2_contacts))
    v2_only = sorted(set(v2_contacts) - set(v1_contacts))

    def _verified(contacts: dict) -> set:
        return {
            k for k, c in contacts.items()
            if (c.get("email_confidence") or "").upper() == "VERIFIED"
        }

    v1_verified = _verified(v1_contacts)
    v2_verified = _verified(v2_contacts)

    return {
        "shared_contacts": len(shared_keys),
        "v1_only_names": [" ".join(n).strip() for n in v1_only[:10]],
        "v1_only_count": len(v1_only),
        "v2_only_names": [" ".join(n).strip() for n in v2_only[:10]],
        "v2_only_count": len(v2_only),
        "shared_verified": len(v1_verified & v2_verified),
        "v1_verified_lost": len(v1_verified - v2_verified),
        "v2_verified_gained": len(v2_verified - v1_verified),
    }


def _evaluate_gates(v1: dict, v2: dict) -> dict:
    """Three numerical ship/no-ship gates — all must pass."""
    if v1["status"] != "success" or v2["status"] != "success":
        return {
            "verified_quality_gate": False,
            "cost_reduction_gate": False,
            "wall_clock_gate": False,
            "overall": False,
            "reason": "one or both runs failed",
        }

    v1_verified = v1["contacts_verified"]
    v2_verified = v2["contacts_verified"]
    verified_gate = v2_verified >= v1_verified * 0.95

    cost_gate = v2["cost_total_usd"] <= v1["cost_total_usd"] * 0.90 if v1["cost_total_usd"] > 0 else False

    v1_wc = v1["wall_clock_seconds"]
    v2_wc = v2["wall_clock_seconds"]
    wc_gate = v2_wc <= v1_wc * 1.05 if v1_wc > 0 else False

    return {
        "verified_quality_gate": verified_gate,
        "cost_reduction_gate": cost_gate,
        "wall_clock_gate": wc_gate,
        "overall": verified_gate and cost_gate and wc_gate,
    }


async def _run_engine(label: str, district: str, state: str, **flags) -> tuple[dict, dict | None]:
    """Run one engine, return (summary_dict, raw_result_dict_or_None)."""
    print(f"\n=== {label} ===", flush=True)
    print(f"  district={district} state={state} flags={flags}", flush=True)

    async def _progress(msg: str) -> None:
        print(f"  [{label}] {msg}", flush=True)

    job = ResearchJob(district, state, progress_callback=_progress, **flags)
    start = datetime.now()
    try:
        result = await job.run()
    except Exception as e:
        elapsed = int((datetime.now() - start).total_seconds())
        print(f"  [{label}] FAILED after {elapsed}s: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return (
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "wall_clock_seconds": elapsed,
                "contacts_total": 0,
                "contacts_verified": 0,
                "contacts_with_email": 0,
                "queries_used": 0,
                "cost_total_usd": 0.0,
                "cost_claude_usd": 0.0,
                "cost_serper_usd": 0.0,
                "cost_exa_usd": 0.0,
                "cost_brave_usd": 0.0,
                "claude_calls": 0,
                "claude_input_tokens": 0,
                "claude_output_tokens": 0,
                "layers_used": "",
                "skipped_layers": [],
                "pages_filtered": 0,
                "contacts_filtered": 0,
            },
            None,
        )

    summary = _summarize(result)
    print(
        f"  [{label}] done: total={summary['contacts_total']} "
        f"verified={summary['contacts_verified']} "
        f"cost=${summary['cost_total_usd']:.4f} "
        f"wall={summary['wall_clock_seconds']}s",
        flush=True,
    )
    return summary, result


def _print_comparison(v1: dict, v2: dict, diff: dict, gates: dict) -> None:
    print("\n" + "=" * 70)
    print(f"  {'metric':<28}{'v1 (baseline)':>18}{'v2 (flags on)':>18}")
    print("-" * 70)

    def _row(label: str, a, b, fmt: str = ""):
        sa = format(a, fmt) if fmt else str(a)
        sb = format(b, fmt) if fmt else str(b)
        print(f"  {label:<28}{sa:>18}{sb:>18}")

    _row("contacts total", v1["contacts_total"], v2["contacts_total"])
    _row("contacts verified", v1["contacts_verified"], v2["contacts_verified"])
    _row("contacts with email", v1["contacts_with_email"], v2["contacts_with_email"])
    _row("serper queries", v1["queries_used"], v2["queries_used"])
    _row("claude calls", v1["claude_calls"], v2["claude_calls"])
    _row("claude in tokens", v1["claude_input_tokens"], v2["claude_input_tokens"])
    _row("claude out tokens", v1["claude_output_tokens"], v2["claude_output_tokens"])
    _row("claude cost usd", v1["cost_claude_usd"], v2["cost_claude_usd"], ".4f")
    _row("serper cost usd", v1["cost_serper_usd"], v2["cost_serper_usd"], ".4f")
    _row("exa cost usd", v1["cost_exa_usd"], v2["cost_exa_usd"], ".4f")
    _row("brave cost usd", v1["cost_brave_usd"], v2["cost_brave_usd"], ".4f")
    _row("TOTAL cost usd", v1["cost_total_usd"], v2["cost_total_usd"], ".4f")
    _row("wall clock seconds", v1["wall_clock_seconds"], v2["wall_clock_seconds"])
    print("-" * 70)
    print(f"  shared contacts:       {diff['shared_contacts']}")
    print(f"  v1-only contacts:      {diff['v1_only_count']}  {diff['v1_only_names'][:5]}")
    print(f"  v2-only contacts:      {diff['v2_only_count']}  {diff['v2_only_names'][:5]}")
    print(f"  shared verified:       {diff['shared_verified']}")
    print(f"  v1 verified lost:      {diff['v1_verified_lost']}")
    print(f"  v2 verified gained:    {diff['v2_verified_gained']}")
    print("-" * 70)
    print(f"  verified_quality_gate  (v2 >= v1 * 0.95):  {'PASS' if gates['verified_quality_gate'] else 'FAIL'}")
    print(f"  cost_reduction_gate    (v2 <= v1 * 0.90):  {'PASS' if gates['cost_reduction_gate'] else 'FAIL'}")
    print(f"  wall_clock_gate        (v2 <= v1 * 1.05):  {'PASS' if gates['wall_clock_gate'] else 'FAIL'}")
    print(f"  OVERALL:                                    {'PASS' if gates['overall'] else 'FAIL'}")
    print("=" * 70 + "\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description="A/B harness for research engine v1 vs v1+flags")
    parser.add_argument("--district", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--max-cost-usd", type=float, default=5.0,
                        help="ceiling for combined v1+v2 cost; v2 skipped if v1 alone exceeds")
    parser.add_argument("--delay-seconds", type=int, default=30,
                        help="delay between v1 and v2 runs to avoid rate limit clipping")
    parser.add_argument("--l15-threshold", type=int, default=15,
                        help="l15_step5_skip_threshold for the v2 run")
    parser.add_argument("--results-path", default=_RESULTS_PATH)
    args = parser.parse_args()

    record: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "district": args.district,
        "state": args.state,
        "config": {
            "max_cost_usd": args.max_cost_usd,
            "delay_seconds": args.delay_seconds,
            "l15_threshold": args.l15_threshold,
        },
    }

    # ── v1 baseline: flags OFF, usage logging ON (so we can measure cost) ──
    v1_summary, v1_raw = await _run_engine(
        "v1",
        args.district,
        args.state,
        log_claude_usage=True,
    )
    record["v1"] = v1_summary

    if v1_summary["cost_total_usd"] > args.max_cost_usd:
        record["cost_ceiling_hit_after_v1"] = True
        record["v2"] = {"status": "skipped_cost_ceiling"}
        record["diff"] = None
        record["pass_fail"] = {
            "verified_quality_gate": False,
            "cost_reduction_gate": False,
            "wall_clock_gate": False,
            "overall": False,
            "reason": "cost ceiling exceeded after v1",
        }
        _write_record(record, args.results_path)
        print(
            f"\nABORTED: v1 cost ${v1_summary['cost_total_usd']:.4f} exceeded "
            f"ceiling ${args.max_cost_usd:.2f}. v2 skipped.",
            flush=True,
        )
        return 2

    # ── Rate-limit breather ──
    print(f"\nSleeping {args.delay_seconds}s between runs...", flush=True)
    await asyncio.sleep(args.delay_seconds)

    # ── v2 Round 1 flags on ──
    v2_summary, v2_raw = await _run_engine(
        "v2",
        args.district,
        args.state,
        enable_url_dedup=True,
        l15_step5_skip_threshold=args.l15_threshold,
        log_claude_usage=True,
    )
    record["v2"] = v2_summary

    if v1_raw is not None and v2_raw is not None:
        diff = _diff_contacts(v1_raw, v2_raw)
    else:
        diff = {
            "shared_contacts": 0, "v1_only_count": 0, "v1_only_names": [],
            "v2_only_count": 0, "v2_only_names": [],
            "shared_verified": 0, "v1_verified_lost": 0, "v2_verified_gained": 0,
        }
    record["diff"] = diff
    record["pass_fail"] = _evaluate_gates(v1_summary, v2_summary)

    combined_cost = v1_summary["cost_total_usd"] + v2_summary["cost_total_usd"]
    if combined_cost > args.max_cost_usd:
        record["cost_ceiling_exceeded_post_run"] = True
        print(
            f"\nWARNING: combined cost ${combined_cost:.4f} exceeded ceiling "
            f"${args.max_cost_usd:.2f} (both runs already completed)",
            flush=True,
        )

    _write_record(record, args.results_path)
    _print_comparison(v1_summary, v2_summary, diff, record["pass_fail"])

    return 0 if record["pass_fail"]["overall"] else 1


def _write_record(record: dict, path: str) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    print(f"Wrote JSONL record to {path}", flush=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
