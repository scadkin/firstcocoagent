"""
campaign_config.py — strategy-agnostic config layer for Scout campaign automation.

Single source of truth for the ``STRATEGIES`` dict consumed by:
- ``scripts/campaign_budget_status.py`` (read-only budget reporter)
- ``tools/campaign_autopilot.py`` (S74 daily prospect-adder)
- ``tools/campaign_pool.py`` (builds per-strategy candidate pools)

Plain Python module, not YAML — with 3 real strategies today, YAML adds a
loader and schema validation for zero clarity payoff. Promote to a file
format when heterogeneous profile shapes force the issue (~15+ strategies).

Adding a new strategy is a config-only change: append an entry here. Fields
outside the ``StrategyConfig`` TypedDict are ignored by readers.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Optional, TypedDict

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_SIDECAR_DRE = REPO_ROOT / "data" / "dre_2026_spring.state.json"


class StrategyConfig(TypedDict, total=False):
    """Shape of one STRATEGIES entry.

    Required:
      number         : canonical strategy number (1..24) from the S66 plan
      display        : human label used in Telegram / CLI output
      tier           : 1..6 per S66 prioritization plan
      weekly_budget  : sends / rolling-7-days allocation for this strategy

    Sequence resolution (exactly one of these two):
      sequence_ids         : static list of Outreach sequence IDs
      sequence_ids_loader  : callable that returns the list at runtime
                             (e.g. reads a state sidecar written by the
                             orchestrator that created the sequences)

    Autopilot-specific (optional, None-valued when autopilot isn't wired):
      pool_source            : tag selecting which pool-builder dispatches
                               on in tools.campaign_pool.build_pool
      bucket_to_sequence_name: map from classifier-bucket → Outreach seq
                               display name. Populated when the strategy
                               ships multiple cohort sequences
      throttle_profile_name  : named profile in
                               scripts/create_dre_sequences.py::THROTTLE_PROFILES
                               (or equivalent). Informational only; autopilot
                               never auto-switches profiles
      priority_order         : cohort-name list. Autopilot priority-fills
                               the strategy's daily budget in this order,
                               draining the top sequence before moving on
    """
    number: int
    display: str
    tier: int
    weekly_budget: int
    sequence_ids: list[int]
    sequence_ids_loader: Callable[[], list[int]]
    pool_source: Optional[str]
    bucket_to_sequence_name: Optional[dict[str, str]]
    throttle_profile_name: Optional[str]
    priority_order: Optional[list[str]]


# ── Sequence-ID loaders ────────────────────────────────────────────────

def _load_dre_sequence_ids() -> list[int]:
    """Pull DRE sequence IDs from the orchestrator's state sidecar."""
    if not STATE_SIDECAR_DRE.exists():
        return []
    try:
        state = json.loads(STATE_SIDECAR_DRE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("could not read %s: %s", STATE_SIDECAR_DRE, e)
        return []
    return [int(info["sequence_id"]) for info in state.get("created", {}).values()]


# ── Strategies ─────────────────────────────────────────────────────────
#
# Per-strategy weekly budget derives from the S66 plan
# (memory/project_prioritization_plan_s66.md):
#   Tier 1 warm re-engage: 1,063/week split 4 ways → 266/week each for
#     #9 (C3 winback), #10 (C4 cold license), #11 (C4 unresponsive), #12 (DRE).
#   Tiers 2-6 TBD per S66 plan table.

STRATEGIES: dict[str, StrategyConfig] = {
    # #12 DRE (Dormant Re-Engage) — Tier 1, first to get autopilot
    "dre": {
        "number": 12,
        "display": "DRE (Dormant Re-Engage)",
        "tier": 1,
        "weekly_budget": 266,
        "sequence_ids_loader": _load_dre_sequence_ids,
        "pool_source": "sf_leads_dre",
        # Cohort-name → Outreach sequence display-name mapping. The actual
        # sequences (2030-2042) are named "DRE 2026 Spring — <cohort>" by
        # scripts/create_dre_sequences.py. Declared explicitly so autopilot
        # never assumes "cohort == seq name" for strategies where they differ.
        "bucket_to_sequence_name": {
            "INT-Universal":          "DRE 2026 Spring — INT-Universal",
            "TC-Universal-Residual":  "DRE 2026 Spring — TC-Universal-Residual",
            "TC-MS":                  "DRE 2026 Spring — TC-MS",
            "TC-HS":                  "DRE 2026 Spring — TC-HS",
            "TC-Elem":                "DRE 2026 Spring — TC-Elem",
            "TC-Virtual":             "DRE 2026 Spring — TC-Virtual",
            "TC-District":            "DRE 2026 Spring — TC-District",
            "TC-All-Grades":          "DRE 2026 Spring — TC-All-Grades",
            "LIB":                    "DRE 2026 Spring — LIB",
            "LQD-Universal":          "DRE 2026 Spring — LQD-Universal",
            "INT-Teacher":            "DRE 2026 Spring — INT-Teacher",
            "TC-Teacher":             "DRE 2026 Spring — TC-Teacher",
            "IT-ReEngage":            "DRE 2026 Spring — IT-ReEngage",
        },
        "throttle_profile_name": "phase-a",
        # Priority-fill order. Autopilot drains LQD-Universal (warmest, 407
        # measured cohort) before spilling into larger TC cohorts. When LQD
        # pool empties the next-day run flows into TC-Universal-Residual,
        # then the TC grade splits (biggest first), then the smaller cohorts.
        "priority_order": [
            "LQD-Universal",           # 407 warmest — ask/quote/demo leads
            "TC-Universal-Residual",   # 7k biggest catch-all
            "TC-MS", "TC-HS", "TC-Elem",   # grade cohorts, largest first
            "INT-Universal", "LIB",
            "TC-Virtual", "TC-District",
            "INT-Teacher", "TC-Teacher", "IT-ReEngage", "TC-All-Grades",
        ],
    },
    # #9 C3 Closed-lost winback — Tier 1, sequences not yet built
    "c3_winback": {
        "number": 9,
        "display": "C3 Closed-lost winback",
        "tier": 1,
        "weekly_budget": 266,
        "sequence_ids": [],
        "pool_source": None,
        "bucket_to_sequence_name": None,
        "throttle_profile_name": None,
    },
    # #10 C4 Cold license request — Tier 1, existing sequences 1995-1998
    "c4_cold_license": {
        "number": 10,
        "display": "C4 Cold license request",
        "tier": 1,
        "weekly_budget": 266,
        "sequence_ids": [1995, 1996, 1997, 1998],
        "pool_source": None,   # autopilot pool not wired yet
        "bucket_to_sequence_name": None,
        "throttle_profile_name": None,
    },
    # #11 C4 Unresponsive seq re-engage — Tier 1, sequences not yet built
    "c4_unresponsive": {
        "number": 11,
        "display": "C4 Unresponsive seq re-engage",
        "tier": 1,
        "weekly_budget": 266,
        "sequence_ids": [],
        "pool_source": None,
        "bucket_to_sequence_name": None,
        "throttle_profile_name": None,
    },
}


def resolve_sequence_ids(strategy: StrategyConfig) -> list[int]:
    """Resolve a strategy's sequence IDs — static list or runtime loader."""
    loader = strategy.get("sequence_ids_loader")
    if loader:
        return loader()
    return list(strategy.get("sequence_ids", []))
