"""
campaign_pool.py — per-strategy candidate pool builder.

Given a strategy key from ``tools.campaign_config``, produces a persisted
JSONL pool of classified, Rule-17-filtered candidate leads ready for the
S74 autopilot to turn into LoadPlans.

Design:

* **PoolLead** is a strict superset of ``prospect_loader.Contact`` — every
  Contact field, plus ``bucket`` (cohort name), ``source_row_id``
  (stable audit key), and the resolved IANA ``tz``. Autopilot constructs
  Contact via ``Contact(**{k: v for k, v in asdict(lead).items() if k in
  Contact_fields})``.

* **Rule 17 at pool-build time**: rows missing a ``state`` value, or with a
  state that ``timezone_lookup.state_to_timezone`` can't resolve, are
  tagged and counted (``no_state`` / ``no_tz_for_state``) but NOT dropped
  silently. The metadata sidecar surfaces the counts.

* **Pool freshness**: ``get_or_build_pool`` reuses an on-disk pool younger
  than 8 days unless ``force_refresh=True``. Autopilot's scheduler tick
  requests refresh on Mondays; any other day that sees an expired file
  self-heals by rebuilding.

* **Atomicity**: writes to ``data/<key>_pool.jsonl.tmp`` then renames, so
  an interrupted build never leaves half a pool on disk.

Only ``pool_source="sf_leads_dre"`` is wired in S74 — new strategies slot
in by adding a dispatch case in ``build_pool``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.campaign_config import STRATEGIES, REPO_ROOT

logger = logging.getLogger(__name__)

POOL_DIR = REPO_ROOT / "data"
POOL_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = 1
POOL_MAX_AGE_DAYS = 8   # self-heal if older (covers a failed Monday run)


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class PoolLead:
    """One candidate lead ready for autopilot to POST into Outreach.

    Fields align with prospect_loader.Contact (first_name .. diocese_or_group)
    so ``Contact(**asdict(pool_lead) restricted)`` round-trips cleanly.
    Additional fields are pool-build metadata only.
    """
    # Contact-compatible fields
    first_name: str
    last_name: str
    email: str
    title: str
    company: str
    state: str
    email_confidence: str
    diocese_or_group: str   # carries the cohort bucket for audit (rename debt)

    # Pool-build metadata
    bucket: str             # DRE cohort name, e.g. "TC-MS"
    tz: str                 # IANA timezone derived from state
    source_row_id: str      # stable audit key (email, lowercased)


@dataclass
class StrategyPool:
    """Full pool build result for one strategy."""
    strategy_key: str
    built_at: str           # UTC ISO 8601
    schema_version: int = SCHEMA_VERSION
    buckets: dict[str, list[PoolLead]] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)
    total_rows_scanned: int = 0
    total_eligible: int = 0

    def cohort_sizes(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.buckets.items()}


# ── Paths ──────────────────────────────────────────────────────────────

def _pool_path(strategy_key: str) -> Path:
    return POOL_DIR / f"{strategy_key}_pool.jsonl"


def _meta_path(strategy_key: str) -> Path:
    return POOL_DIR / f"{strategy_key}_pool.meta.json"


# ── Build ──────────────────────────────────────────────────────────────

def build_pool(strategy_key: str) -> StrategyPool:
    """Build a fresh pool for ``strategy_key``. Dispatches on ``pool_source``."""
    strategy = STRATEGIES.get(strategy_key)
    if strategy is None:
        raise ValueError(f"unknown strategy: {strategy_key!r}")
    pool_source = strategy.get("pool_source")
    if pool_source is None:
        raise ValueError(
            f"strategy {strategy_key!r} has no pool_source configured; "
            "autopilot cannot build a pool for it"
        )

    if pool_source == "sf_leads_dre":
        return _build_sf_leads_dre_pool(strategy_key)

    raise ValueError(f"unknown pool_source: {pool_source!r}")


def _build_sf_leads_dre_pool(strategy_key: str) -> StrategyPool:
    """Run the DRE classifier, enrich with tz, tag Rule-17 drops, persist."""
    # Lazy imports — these modules pull in the Sheets client which is
    # heavy and only needed at pool-build time.
    from tools.lead_filters import ALL_DRE_COHORTS, classify_sf_leads_to_dre_buckets
    from tools.timezone_lookup import state_to_timezone

    logger.info("Building SF Leads DRE pool for strategy %s", strategy_key)
    classification = classify_sf_leads_to_dre_buckets()

    pool = StrategyPool(
        strategy_key=strategy_key,
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        excluded=dict(classification.excluded),
        total_rows_scanned=classification.total_rows_scanned,
    )
    for cohort in ALL_DRE_COHORTS:
        pool.buckets[cohort] = []

    for cohort_name, rows in classification.buckets.items():
        for raw in rows:
            # Rule 17 at the boundary — tag and skip rows missing state or tz.
            state = (raw.get("state") or "").strip().upper()
            if not state or len(state) != 2:
                pool.excluded["no_state"] = pool.excluded.get("no_state", 0) + 1
                continue
            try:
                tz = state_to_timezone(state)
            except Exception:
                pool.excluded["no_tz_for_state"] = \
                    pool.excluded.get("no_tz_for_state", 0) + 1
                continue

            email = (raw.get("email") or "").strip()
            if not email:
                pool.excluded["no_email"] = pool.excluded.get("no_email", 0) + 1
                continue

            lead = PoolLead(
                first_name=(raw.get("first_name") or "").strip(),
                last_name=(raw.get("last_name") or "").strip(),
                email=email,
                title=(raw.get("title") or "").strip(),
                company=(raw.get("company") or "").strip(),
                state=state,
                email_confidence="VERIFIED",   # SF Leads rows are Salesforce-sourced
                diocese_or_group=cohort_name,  # cohort tag (rename debt — Contact field)
                bucket=cohort_name,
                tz=tz,
                source_row_id=email.lower(),
            )
            pool.buckets[cohort_name].append(lead)
            pool.total_eligible += 1

    _write_pool(pool)
    return pool


# ── Persist / load ─────────────────────────────────────────────────────

def _write_pool(pool: StrategyPool) -> None:
    """Atomically write JSONL + meta sidecar for a pool."""
    jsonl_path = _pool_path(pool.strategy_key)
    meta_path = _meta_path(pool.strategy_key)

    # JSONL: one PoolLead per line
    fd, tmp_path = tempfile.mkstemp(
        dir=POOL_DIR, prefix=f".{pool.strategy_key}_pool.", suffix=".jsonl.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for leads in pool.buckets.values():
                for lead in leads:
                    f.write(json.dumps(asdict(lead), ensure_ascii=False) + "\n")
        os.replace(tmp_path, jsonl_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Meta sidecar
    meta = {
        "strategy_key": pool.strategy_key,
        "built_at": pool.built_at,
        "schema_version": pool.schema_version,
        "total_rows_scanned": pool.total_rows_scanned,
        "total_eligible": pool.total_eligible,
        "cohort_sizes": pool.cohort_sizes(),
        "excluded": pool.excluded,
    }
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    logger.info(
        "Wrote pool %s: %d eligible, %d excluded",
        pool.strategy_key, pool.total_eligible, sum(pool.excluded.values()),
    )


def load_pool(strategy_key: str) -> StrategyPool:
    """Read JSONL + meta back into a StrategyPool."""
    jsonl_path = _pool_path(strategy_key)
    meta_path = _meta_path(strategy_key)
    if not jsonl_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"pool files missing for {strategy_key}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pool = StrategyPool(
        strategy_key=meta["strategy_key"],
        built_at=meta["built_at"],
        schema_version=meta.get("schema_version", SCHEMA_VERSION),
        excluded=meta.get("excluded", {}),
        total_rows_scanned=meta.get("total_rows_scanned", 0),
        total_eligible=meta.get("total_eligible", 0),
    )
    for cohort in meta.get("cohort_sizes", {}).keys():
        pool.buckets[cohort] = []

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            lead = PoolLead(**d)
            pool.buckets.setdefault(lead.bucket, []).append(lead)
    return pool


def pool_age_days(strategy_key: str) -> Optional[float]:
    """Age of on-disk pool in days, or None if no pool exists."""
    meta_path = _meta_path(strategy_key)
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        built_at = datetime.fromisoformat(meta["built_at"])
    except Exception as e:
        logger.warning("could not parse pool meta for %s: %s", strategy_key, e)
        return None
    now = datetime.now(timezone.utc)
    if built_at.tzinfo is None:
        built_at = built_at.replace(tzinfo=timezone.utc)
    return (now - built_at).total_seconds() / 86400.0


def get_or_build_pool(
    strategy_key: str,
    *,
    force_refresh: bool = False,
) -> StrategyPool:
    """Return the pool, building it if missing or older than POOL_MAX_AGE_DAYS."""
    age = pool_age_days(strategy_key)
    if not force_refresh and age is not None and age <= POOL_MAX_AGE_DAYS:
        logger.info(
            "Loading cached pool for %s (age %.1f days)", strategy_key, age
        )
        return load_pool(strategy_key)
    logger.info(
        "Building fresh pool for %s (force=%s, cached_age_days=%s)",
        strategy_key, force_refresh, age,
    )
    return build_pool(strategy_key)
