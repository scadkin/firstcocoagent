"""
role_classifier.py — Haiku-backed contact role bucketing.

Classifies a contact (primarily by job title) into one of:
    admin | curriculum | it | teacher | coach | other

Used by scripts/load_campaign.py to route contacts to the right
role-variant sequence in a multi-variant Outreach campaign.

Design:
  - Pre-filter: agent.target_roles.is_relevant_role filters out CTE
    trades + IT infrastructure. Failing contacts route to "other"
    without a Claude call (saves cost).
  - Claude Haiku at temp=0 for the actual bucketing. Deterministic per
    title — same title → same bucket.
  - sha1(normalized title)-keyed cache at data/role_classifier_cache.json
    so re-runs + large batches don't re-call Claude for repeat titles.
  - Kill switch: ROLE_CLASSIFIER_MODE = "haiku" | "pass_through". Set to
    "pass_through" to route every contact to "other" — breakglass if
    Haiku is down.
  - Testable: classify_contact_role accepts an optional client kwarg so
    tests can inject a mock Claude client without env/API deps.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agent.target_roles import is_relevant_role

logger = logging.getLogger(__name__)

# ── Kill switch ──────────────────────────────────────────────────────────
# "haiku" = call Claude Haiku for classification
# "pass_through" = every contact returns "other" (breakglass mode)
ROLE_CLASSIFIER_MODE = os.environ.get("ROLE_CLASSIFIER_MODE", "haiku")

VALID_ROLES = ("admin", "curriculum", "it", "teacher", "coach", "other")

_DEFAULT_CACHE_PATH = Path("data/role_classifier_cache.json")
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_HAIKU_MAX_TOKENS = 20
_HAIKU_TIMEOUT = 30.0

_CLASSIFIER_PROMPT = """You classify a K-12 education job title into exactly one role bucket for sales outreach targeting.

Buckets (pick ONE):
- admin: Superintendents, Assistant Superintendents, Principals, Assistant/Vice Principals, Executive Directors, Heads of School, District Office senior leadership. Anyone who runs a school building or district.
- curriculum: Curriculum Directors, C&I leads, Academic Coaches, Instructional Coaches, Assessment Coordinators, CS Curriculum Leads, Content Area Coordinators. Anyone focused on curriculum design or instruction support.
- it: Directors of Technology, CIOs, CTOs, EdTech Coordinators, Instructional Technology Coordinators, EdTech Directors. Technology leadership with an education focus. NOT help desk, sysadmin, or network ops (those are "other").
- teacher: CS Teachers, Math Teachers, Algebra Teachers, STEM Teachers, Robotics Teachers, classroom-level teaching roles. Includes subject-area teachers.
- coach: Athletic Coaches, Esports Coaches, Robotics Coaches, Game Design Coaches. ONLY actual coach-of-a-team roles — "Instructional Coach" is curriculum, not coach.
- other: Anything that doesn't fit cleanly, trades roles, or ambiguous titles.

Job title: {title}

Respond with exactly one word — the bucket name, lowercase. Nothing else."""


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.strip().lower()
    title = re.sub(r"\s+", " ", title)
    return title


def _cache_key(title: str) -> str:
    return hashlib.sha1(_normalize_title(title).encode("utf-8")).hexdigest()


def _read_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning(f"role classifier cache read failed at {path}: {e}")
        return {}


def _write_cache_atomic(path: Path, data: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".rc-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _build_default_client():
    """Lazy-instantiate an Anthropic client. Returns None if SDK missing."""
    try:
        import anthropic

        return anthropic.Anthropic(timeout=_HAIKU_TIMEOUT)
    except Exception as e:
        logger.warning(f"anthropic SDK unavailable: {e}")
        return None


def _classify_with_haiku(title: str, client) -> str:
    """Call Haiku at temp=0 and map the response to a valid bucket."""
    prompt = _CLASSIFIER_PROMPT.format(title=title)
    try:
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=_HAIKU_MAX_TOKENS,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip().lower()
    except Exception as e:
        logger.warning(f"Haiku classification failed for title {title!r}: {e}")
        return "other"

    token = re.sub(r"[^a-z]", "", raw.split()[0] if raw else "")
    if token in VALID_ROLES:
        return token
    for bucket in VALID_ROLES:
        if bucket in raw:
            return bucket
    logger.warning(f"Haiku returned unrecognized bucket {raw!r} for title {title!r}")
    return "other"


def classify_contact_role(
    contact: dict,
    *,
    client: Any = None,
    cache_path: Optional[Path] = None,
) -> str:
    """
    Classify a contact dict into one of VALID_ROLES. Never raises.

    Args:
        contact: dict with at minimum a 'title' key. Other keys ignored.
        client: optional Anthropic client. If None, a default client is
            built lazily. Tests inject a mock client to avoid live calls.
        cache_path: optional Path to the cache JSON. Defaults to
            data/role_classifier_cache.json. Pass a temp path in tests.

    Returns:
        One of: admin | curriculum | it | teacher | coach | other.
    """
    title = (contact.get("title") or "").strip()
    if not title:
        return "other"

    if ROLE_CLASSIFIER_MODE == "pass_through":
        return "other"

    if not is_relevant_role(title):
        return "other"

    path = cache_path or _DEFAULT_CACHE_PATH
    cache = _read_cache(path)
    key = _cache_key(title)
    cached = cache.get(key)
    if cached and cached.get("bucket") in VALID_ROLES:
        return cached["bucket"]

    if client is None:
        client = _build_default_client()
    if client is None:
        return "other"

    bucket = _classify_with_haiku(title, client)

    cache[key] = {
        "bucket": bucket,
        "title": title,
        "classified_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        _write_cache_atomic(path, cache)
    except Exception as e:
        logger.warning(f"role classifier cache write failed: {e}")

    return bucket
