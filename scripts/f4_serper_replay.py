#!/usr/bin/env python3
"""F4 CS funding scanner — Serper-replay diagnostic harness.

Lets us iterate on query design + extraction prompt without redeploying
to Railway or hitting the live Signals tab. Imports the real helpers from
tools.signal_processor so there's zero divergence path between harness and
production.

Modes:
  --snapshot <state>           Probe live Serper for one state, save snapshot
  --snapshot-all               Probe all 13 territory states
  --replay <snapshot.json>     Replay extraction offline against a snapshot
  --replay-all <snapshot_dir>  Replay every snapshot in a directory
  --gate <oracle> <snap_dir>   Run extraction across snapshots, compare HIGH
                               extractions to oracle labels, compute precision

Snapshots live in scripts/f4_snapshots/<STATE>_<YYYYMMDD>.json
Oracle lives at scripts/f4_oracle.json (committed reference artifact)

Usage:
  python3 scripts/f4_serper_replay.py --snapshot IL
  python3 scripts/f4_serper_replay.py --snapshot-all
  python3 scripts/f4_serper_replay.py --replay scripts/f4_snapshots/IL_20260411.json
  python3 scripts/f4_serper_replay.py --replay-all scripts/f4_snapshots/
  python3 scripts/f4_serper_replay.py --gate scripts/f4_oracle.json scripts/f4_snapshots/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env for SERPER_API_KEY / ANTHROPIC_API_KEY before importing signal_processor
for ln in (ROOT / ".env").read_text().splitlines():
    if "=" in ln and not ln.startswith("#"):
        k, _, v = ln.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

import httpx  # noqa: E402

from tools.signal_processor import (  # noqa: E402
    _f4_build_queries,
    _f4_extract_items,
    STATE_DOE_NAMES,
    STATE_CS_PROGRAMS,
    TERRITORY_STATES_WITH_CA,
    ABBR_TO_STATE_NAME,
    SERPER_URL,
)

SNAPSHOT_DIR = ROOT / "scripts" / "f4_snapshots"
DEFAULT_ORACLE = ROOT / "scripts" / "f4_oracle.json"

_SERPER_KEY = os.environ.get("SERPER_API_KEY", "")
if not _SERPER_KEY:
    print("ERROR: SERPER_API_KEY not set in .env", file=sys.stderr)
    sys.exit(2)


def _norm_district(name: str) -> str:
    """Lightweight normalizer — lowercase, collapse whitespace, strip trailing
    punctuation. For oracle matching only."""
    return " ".join((name or "").lower().strip().split()).rstrip(".,;:")


# ──────────────────────────────────────────────
# Snapshot mode
# ──────────────────────────────────────────────


def snapshot_state(state_abbr: str) -> dict:
    """Probe Serper for one state and return the snapshot dict."""
    state_name = ABBR_TO_STATE_NAME.get(state_abbr, state_abbr)
    queries = _f4_build_queries(state_abbr, state_name)
    print(f"[{state_abbr}] {len(queries)} queries:")
    for q in queries:
        print(f"    {q}")
    all_snippets = []
    seen_urls = set()
    for query in queries:
        try:
            resp = httpx.post(
                SERPER_URL,
                headers={"X-API-Key": _SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 10, "tbs": "qdr:y"},
                timeout=20.0,
            )
            data = resp.json()
            for item in data.get("organic", [])[:10]:
                url = item.get("link", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_snippets.append(
                        {
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "searched_state": state_abbr,
                            "query": query,
                        }
                    )
            time.sleep(0.5)
        except Exception as e:
            print(f"  [warn] Serper call failed for {state_abbr}: {e}", file=sys.stderr)
    print(f"[{state_abbr}] {len(all_snippets)} unique organic results")
    return {
        "state_abbr": state_abbr,
        "state_name": state_name,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "query_count": len(queries),
        "queries": queries,
        "snippets": all_snippets,
    }


def save_snapshot(snapshot: dict) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    path = SNAPSHOT_DIR / f"{snapshot['state_abbr']}_{date}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    print(f"  → saved to {path.relative_to(ROOT)}")
    return path


def cmd_snapshot(state_abbr: str) -> None:
    snap = snapshot_state(state_abbr)
    save_snapshot(snap)


def cmd_snapshot_all() -> None:
    states = sorted(TERRITORY_STATES_WITH_CA)
    print(f"Snapshotting {len(states)} territory states (will take ~{len(states) * 5}s)")
    for i, s in enumerate(states, 1):
        print(f"\n=== {i}/{len(states)} ===")
        snap = snapshot_state(s)
        save_snapshot(snap)


# ──────────────────────────────────────────────
# Replay mode
# ──────────────────────────────────────────────


def _client():
    import anthropic

    return anthropic.Anthropic(timeout=90.0)


def replay_snapshot(snapshot_path: Path, client=None) -> list:
    """Run _f4_extract_items against a saved snapshot. Returns extracted
    item list."""
    data = json.loads(snapshot_path.read_text())
    state_abbr = data["state_abbr"]
    snippets = data["snippets"]
    if not snippets:
        print(f"[{state_abbr}] empty snapshot — 0 extracted")
        return []
    combined_text = ""
    for s in snippets:
        combined_text += f"\n[{state_abbr}] {s['title']}\n{s['snippet']}\nURL: {s['url']}\n"
    combined_text = combined_text[:20000]
    client = client or _client()
    items = _f4_extract_items(client, combined_text, state_abbr)
    print(f"[{state_abbr}] {len(snippets)} snippets → {len(items)} extracted")
    for it in items:
        conf = (it.get("confidence") or "").strip().upper()
        print(
            f"  {conf:<6} {it.get('district','')[:45]:<45} "
            f"{it.get('state',''):<2} {it.get('amount',''):<12} "
            f"{it.get('purpose','')[:20]}"
        )
    return items


def cmd_replay(snapshot_path: str) -> None:
    replay_snapshot(Path(snapshot_path))


def cmd_replay_all(snapshot_dir: str) -> None:
    d = Path(snapshot_dir)
    files = sorted(d.glob("*.json"))
    if not files:
        print(f"No snapshots in {d}", file=sys.stderr)
        sys.exit(1)
    client = _client()
    total_items = 0
    for f in files:
        items = replay_snapshot(f, client=client)
        total_items += len(items)
    print(f"\nTotal across {len(files)} snapshots: {total_items} extracted items")


# ──────────────────────────────────────────────
# Gate mode
# ──────────────────────────────────────────────


def _load_oracle(oracle_path: Path) -> dict:
    """Oracle schema:
    {
      "rows": [
        {
          "district": "...",
          "state": "IL",
          "source_url": "...",
          "expected_confidence": "HIGH|MEDIUM|LOW",
          "is_real_lea_award": true|false|null,
          "notes": "..."
        }
      ]
    }
    Returns a dict keyed by (norm_district, state) → row. Rows with
    is_real_lea_award=null are treated as unlabeled.
    """
    data = json.loads(oracle_path.read_text())
    rows = data.get("rows", [])
    index = {}
    for r in rows:
        key = (_norm_district(r.get("district", "")), (r.get("state") or "").upper())
        index[key] = r
    return index


def cmd_gate(oracle_path: str, snapshot_dir: str, min_precision: float = 0.6) -> None:
    oracle = _load_oracle(Path(oracle_path))
    print(f"Loaded oracle: {len(oracle)} labeled rows")

    files = sorted(Path(snapshot_dir).glob("*.json"))
    if not files:
        print(f"No snapshots in {snapshot_dir}", file=sys.stderr)
        sys.exit(1)

    client = _client()
    all_high = []
    for f in files:
        items = replay_snapshot(f, client=client)
        for it in items:
            if (it.get("confidence") or "").strip().upper() == "HIGH":
                all_high.append(it)

    if not all_high:
        print("\nGATE RESULT: FAIL (no HIGH extractions at all)")
        sys.exit(1)

    labeled_true = 0
    labeled_false = 0
    unlabeled = []
    for it in all_high:
        key = (_norm_district(it.get("district", "")), (it.get("state") or "").upper())
        row = oracle.get(key)
        if row is None or row.get("is_real_lea_award") is None:
            unlabeled.append(it)
            continue
        if row["is_real_lea_award"] is True:
            labeled_true += 1
        else:
            labeled_false += 1

    total_labeled = labeled_true + labeled_false
    print(f"\nHIGH extractions: {len(all_high)}")
    print(f"  labeled real:       {labeled_true}")
    print(f"  labeled false:      {labeled_false}")
    print(f"  unlabeled:          {len(unlabeled)}")

    if unlabeled:
        print("\nUnlabeled HIGH extractions (strict mode requires labels for all):")
        for it in unlabeled:
            print(
                f"  {it.get('district',''):<45} {it.get('state',''):<2} "
                f"{it.get('amount',''):<12} {it.get('source_url','')[:70]}"
            )
        print("\nGATE RESULT: FAIL (unlabeled HIGHs — add to oracle and re-run)")
        sys.exit(1)

    if total_labeled == 0:
        print("\nGATE RESULT: FAIL (zero labeled HIGHs)")
        sys.exit(1)

    precision = labeled_true / total_labeled
    print(f"\nPrecision: {labeled_true}/{total_labeled} = {precision:.1%}")
    print(f"Threshold: {min_precision:.0%}")

    if precision >= min_precision:
        print("GATE RESULT: PASS")
        sys.exit(0)
    else:
        print("GATE RESULT: FAIL (precision below threshold)")
        sys.exit(1)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="cmd")

    p_snap = sub.add_parser("--snapshot")
    p_snap.add_argument("state", help="Two-letter state code (e.g. IL)")

    sub.add_parser("--snapshot-all")

    p_rep = sub.add_parser("--replay")
    p_rep.add_argument("snapshot_path")

    p_rall = sub.add_parser("--replay-all")
    p_rall.add_argument("snapshot_dir", nargs="?", default=str(SNAPSHOT_DIR))

    p_gate = sub.add_parser("--gate")
    p_gate.add_argument("oracle_path", nargs="?", default=str(DEFAULT_ORACLE))
    p_gate.add_argument("snapshot_dir", nargs="?", default=str(SNAPSHOT_DIR))

    # argparse doesn't love leading-dash subcommands, so parse manually instead
    args = sys.argv[1:]
    if not args:
        parser.print_help()
        sys.exit(1)

    cmd = args[0]
    rest = args[1:]
    if cmd == "--snapshot":
        if not rest:
            print("Usage: --snapshot <STATE>", file=sys.stderr)
            sys.exit(1)
        cmd_snapshot(rest[0].upper())
    elif cmd == "--snapshot-all":
        cmd_snapshot_all()
    elif cmd == "--replay":
        if not rest:
            print("Usage: --replay <snapshot.json>", file=sys.stderr)
            sys.exit(1)
        cmd_replay(rest[0])
    elif cmd == "--replay-all":
        cmd_replay_all(rest[0] if rest else str(SNAPSHOT_DIR))
    elif cmd == "--gate":
        oracle = rest[0] if rest else str(DEFAULT_ORACLE)
        snap_dir = rest[1] if len(rest) > 1 else str(SNAPSHOT_DIR)
        cmd_gate(oracle, snap_dir)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
