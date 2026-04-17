from __future__ import annotations

"""
tools/outreach_client.py — Outreach.io API client.

OAuth2 Authorization Code flow. Tokens stored in environment + refreshed
automatically. Write access scoped to sequence creation only (Session 38).

Usage:
  import tools.outreach_client as outreach_client
  outreach_client.get_sequences()
  outreach_client.get_sequence_states(sequence_id)
  outreach_client.get_prospect(prospect_id)
  outreach_client.create_sequence(name, steps=[{subject, body_html, interval_minutes}])
"""

import json
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

API_BASE = "https://api.outreach.io/api/v2"
TOKEN_URL = "https://api.outreach.io/oauth/token"
AUTH_URL = "https://api.outreach.io/oauth/authorize"

# Read from env (set in Railway)
_CLIENT_ID = os.environ.get("OUTREACH_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("OUTREACH_CLIENT_SECRET", "")
_REDIRECT_URI = os.environ.get("OUTREACH_REDIRECT_URI", "")

# In-memory token storage (persisted to env/file for Railway restarts)
_access_token: str = os.environ.get("OUTREACH_ACCESS_TOKEN", "")
_refresh_token: str = os.environ.get("OUTREACH_REFRESH_TOKEN", "")
_token_expires_at: float = 0.0
_user_id: str = ""  # Outreach user ID for the authenticated user (Steven)


def is_configured() -> bool:
    """Check if Outreach OAuth credentials are set."""
    return bool(_CLIENT_ID and _CLIENT_SECRET and _REDIRECT_URI)


def is_authenticated() -> bool:
    """Check if we have a valid (or refreshable) token."""
    return bool(_access_token or _refresh_token)


def get_auth_url() -> str:
    """Build the OAuth authorization URL for the user to visit in their browser."""
    scopes = "+".join([
        # Read scopes
        "accounts.read",
        "prospects.read",
        "sequences.read",
        "sequenceStates.read",
        "sequenceSteps.read",
        "sequenceTemplates.read",
        "templates.read",
        "mailings.read",
        "calls.read",
        "events.read",
        "users.read",
        # Write scopes
        "sequences.write",
        "sequenceSteps.write",
        "sequenceTemplates.write",
        "sequenceStates.write",
        "sequenceStates.delete",
        "templates.write",
        "prospects.write",
    ])
    return (
        f"{AUTH_URL}?client_id={_CLIENT_ID}"
        f"&redirect_uri={_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scopes}"
    )


# ─────────────────────────────────────────────
# TOKEN MANAGEMENT
# ─────────────────────────────────────────────

def exchange_code_for_tokens(auth_code: str) -> dict:
    """
    Exchange an authorization code for access + refresh tokens.
    Called once after the user approves the OAuth flow.
    Returns {success, error}.
    """
    global _access_token, _refresh_token, _token_expires_at

    try:
        logger.info(f"Outreach OAuth: exchanging code (client_id length={len(_CLIENT_ID)}, "
                     f"secret length={len(_CLIENT_SECRET)}, redirect_uri={_REDIRECT_URI})")
        resp = httpx.post(TOKEN_URL, data={
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "redirect_uri": _REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": auth_code,
        }, timeout=30.0)

        if resp.status_code != 200:
            body = resp.text[:500]
            logger.error(f"Outreach OAuth token exchange HTTP {resp.status_code}: {body}")
            return {"success": False, "error": f"HTTP {resp.status_code}: {body}"}

        data = resp.json()

        _access_token = data.get("access_token", "")
        _refresh_token = data.get("refresh_token", "")
        expires_in = data.get("expires_in", 7200)
        _token_expires_at = time.time() + expires_in - 60  # 60s buffer

        _persist_tokens()
        logger.info("Outreach OAuth: tokens obtained successfully")

        # Look up the authenticated user's ID so we can filter to only their data
        _lookup_current_user()

        return {"success": True, "error": ""}

    except Exception as e:
        logger.error(f"Outreach OAuth token exchange failed: {e}")
        return {"success": False, "error": str(e)}


def _refresh_access_token() -> bool:
    """Refresh the access token using the refresh token. Returns True on success."""
    global _access_token, _refresh_token, _token_expires_at

    if not _refresh_token:
        logger.error("Outreach: no refresh token available")
        return False

    try:
        resp = httpx.post(TOKEN_URL, data={
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": _refresh_token,
        }, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        _access_token = data.get("access_token", "")
        _refresh_token = data.get("refresh_token", _refresh_token)
        expires_in = data.get("expires_in", 7200)
        _token_expires_at = time.time() + expires_in - 60

        _persist_tokens()
        logger.info("Outreach OAuth: token refreshed successfully")
        return True

    except Exception as e:
        logger.error(f"Outreach OAuth token refresh failed: {e}")
        return False


def _persist_tokens():
    """Save tokens to GitHub (survives Railway deploys) and /tmp (fast local access)."""
    token_data = {
        "access_token": _access_token,
        "refresh_token": _refresh_token,
        "expires_at": _token_expires_at,
        "user_id": _user_id,
    }
    # Local cache for fast reads during this deploy
    try:
        with open("/tmp/outreach_tokens.json", "w") as f:
            json.dump(token_data, f)
    except Exception:
        pass

    # Persist to GitHub for survival across deploys
    try:
        import tools.github_pusher as github_pusher
        github_pusher.push_file(
            "memory/outreach_tokens.json",
            json.dumps(token_data, indent=2),
            "Outreach OAuth tokens update",
        )
        logger.info("Outreach tokens persisted to GitHub")
    except Exception as e:
        logger.warning(f"Could not persist Outreach tokens to GitHub: {e}")


def _load_persisted_tokens():
    """Load tokens from /tmp first (fast), fall back to GitHub."""
    global _access_token, _refresh_token, _token_expires_at, _user_id

    # Try local cache first
    try:
        with open("/tmp/outreach_tokens.json", "r") as f:
            data = json.load(f)
        _access_token = data.get("access_token", "")
        _refresh_token = data.get("refresh_token", "")
        _token_expires_at = data.get("expires_at", 0.0)
        _user_id = data.get("user_id", "")
        if _refresh_token:
            logger.info(f"Outreach tokens loaded from local cache (user_id={_user_id})")
            return
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Fall back to GitHub
    try:
        import tools.github_pusher as github_pusher
        content = github_pusher.get_file_content("memory/outreach_tokens.json")
        if content:
            data = json.loads(content)
            _access_token = data.get("access_token", "")
            _refresh_token = data.get("refresh_token", "")
            _token_expires_at = data.get("expires_at", 0.0)
            _user_id = data.get("user_id", "")
            # Write to local cache for fast subsequent reads
            try:
                with open("/tmp/outreach_tokens.json", "w") as f:
                    json.dump(data, f)
            except Exception:
                pass
            logger.info(f"Outreach tokens loaded from GitHub (user_id={_user_id})")
            return
    except Exception as e:
        logger.warning(f"Could not load Outreach tokens from GitHub: {e}")

    logger.info("No Outreach tokens found — use /connect_outreach to authorize")


def _lookup_current_user():
    """Look up the authenticated user's Outreach ID and name."""
    global _user_id
    try:
        headers = _get_headers()

        # Try /users/me first (some Outreach API versions support this)
        resp = httpx.get(f"{API_BASE}/users/me", headers=headers, timeout=30.0)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            _user_id = str(data.get("id", ""))
            attrs = data.get("attributes", {})
            name = f"{attrs.get('firstName', '')} {attrs.get('lastName', '')}".strip()
            logger.info(f"Outreach user identified via /users/me: {name} (ID: {_user_id})")
            _persist_tokens()
            return

        logger.info(f"Outreach /users/me returned HTTP {resp.status_code}, trying search by email")

        # Fallback: search users by email (Steven's email)
        resp2 = httpx.get(
            f"{API_BASE}/users",
            headers=headers,
            params={"filter[email]": "steven@codecombat.com"},
            timeout=30.0,
        )
        if resp2.status_code == 200:
            users = resp2.json().get("data", [])
            if users:
                data = users[0]
                _user_id = str(data.get("id", ""))
                attrs = data.get("attributes", {})
                name = f"{attrs.get('firstName', '')} {attrs.get('lastName', '')}".strip()
                logger.info(f"Outreach user identified via email search: {name} (ID: {_user_id})")
                _persist_tokens()
                return

        logger.info(f"Outreach email search returned HTTP {resp2.status_code}, trying list all users")

        # Fallback 2: list all users, find Steven Adkins
        resp3 = httpx.get(
            f"{API_BASE}/users",
            headers=headers,
            params={"page[size]": "200"},
            timeout=30.0,
        )
        if resp3.status_code == 200:
            users = resp3.json().get("data", [])
            for u in users:
                attrs = u.get("attributes", {})
                first = attrs.get("firstName", "").lower()
                last = attrs.get("lastName", "").lower()
                email = attrs.get("email", "").lower()
                if "steven" in first or "adkins" in last or "steven@codecombat" in email:
                    _user_id = str(u.get("id", ""))
                    name = f"{attrs.get('firstName', '')} {attrs.get('lastName', '')}".strip()
                    logger.info(f"Outreach user identified via user list: {name} (ID: {_user_id})")
                    _persist_tokens()
                    return
            # Log all users found for debugging
            user_names = [f"{u.get('attributes',{}).get('firstName','')} {u.get('attributes',{}).get('lastName','')}" for u in users[:10]]
            logger.warning(f"Outreach: could not find Steven in {len(users)} users. First 10: {user_names}")
        else:
            logger.warning(f"Outreach user list returned HTTP {resp3.status_code}: {resp3.text[:200]}")

    except Exception as e:
        logger.warning(f"Outreach user lookup failed: {e}")


def get_user_id() -> str:
    """Return the authenticated user's Outreach ID."""
    return _user_id


# Load on module import
_load_persisted_tokens()


def _get_headers() -> dict:
    """Get auth headers, refreshing token if needed."""
    global _access_token
    if time.time() >= _token_expires_at and _refresh_token:
        _refresh_access_token()
    return {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/vnd.api+json",
    }


# ─────────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────────

def _api_get(path: str, params: dict | None = None) -> dict:
    """
    Make a GET request to the Outreach API. Handles pagination cursor.
    Returns the JSON response or raises on error.
    """
    url = f"{API_BASE}{path}"
    headers = _get_headers()

    resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
    if resp.status_code == 401:
        # Try refresh once
        if _refresh_access_token():
            headers = _get_headers()
            resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, payload: dict) -> dict:
    """
    Make a POST request to the Outreach API (JSON:API format).
    Returns the JSON response or raises on error.
    """
    url = f"{API_BASE}{path}"
    headers = _get_headers()

    resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    if resp.status_code == 401:
        if _refresh_access_token():
            headers = _get_headers()
            resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)

    if resp.status_code not in (200, 201):
        body = resp.text[:500]
        logger.error(f"Outreach POST {path} HTTP {resp.status_code}: {body}")
        raise Exception(f"Outreach API error {resp.status_code}: {body}")

    return resp.json()


def _api_patch(path: str, payload: dict) -> dict:
    """Make a PATCH request to the Outreach API (JSON:API format)."""
    url = f"{API_BASE}{path}"
    headers = _get_headers()

    resp = httpx.patch(url, headers=headers, json=payload, timeout=30.0)
    if resp.status_code == 401:
        if _refresh_access_token():
            headers = _get_headers()
            resp = httpx.patch(url, headers=headers, json=payload, timeout=30.0)

    if resp.status_code not in (200, 201):
        body = resp.text[:500]
        logger.error(f"Outreach PATCH {path} HTTP {resp.status_code}: {body}")
        raise Exception(f"Outreach API error {resp.status_code}: {body}")

    return resp.json()


def _api_get_all(path: str, params: dict | None = None, max_pages: int = 50) -> list:
    """
    Paginate through all results for a GET endpoint.
    Returns a list of all data objects across pages.
    """
    if params is None:
        params = {}
    params.setdefault("page[size]", "50")

    all_data = []
    pages = 0

    while pages < max_pages:
        result = _api_get(path, params)
        data = result.get("data", [])
        all_data.extend(data)
        pages += 1

        # Check for next page
        next_link = result.get("links", {}).get("next")
        if not next_link or not data:
            break

        # Extract cursor from next link
        import urllib.parse
        parsed = urllib.parse.urlparse(next_link)
        next_params = dict(urllib.parse.parse_qsl(parsed.query))
        params.update(next_params)

    return all_data


# ─────────────────────────────────────────────
# READ-ONLY API METHODS
# ─────────────────────────────────────────────

def get_sequences() -> list[dict]:
    """
    List sequences owned by the authenticated user only.
    Returns simplified list of sequence dicts.
    Each dict: {id, name, enabled, reply_count, bounce_count, deliver_count,
                open_count, num_contacted, num_replied, created_at, last_used_at}
    """
    params = {}
    if _user_id:
        params["filter[owner][id]"] = _user_id
    raw = _api_get_all("/sequences", params)
    sequences = []
    for item in raw:
        attrs = item.get("attributes", {})
        sequences.append({
            "id": item.get("id"),
            "name": attrs.get("name", ""),
            "enabled": attrs.get("enabled", False),
            "reply_count": attrs.get("replyCount", 0),
            "bounce_count": attrs.get("bounceCount", 0),
            "deliver_count": attrs.get("deliverCount", 0),
            "open_count": attrs.get("openCount", 0),
            "num_contacted": attrs.get("numContactedProspects", 0),
            "num_replied": attrs.get("numRepliedProspects", 0),
            "created_at": attrs.get("createdAt", ""),
            "last_used_at": attrs.get("lastUsedAt", ""),
            "tags": attrs.get("tags", []),
        })
    return sequences


def get_sequence_states(sequence_id: int | str, include_prospect: bool = True) -> list[dict]:
    """
    Get all prospect states for a sequence (who's in it, their engagement).
    Returns list of dicts with engagement data + prospect info.
    """
    params = {
        "filter[sequence][id]": str(sequence_id),
    }
    if include_prospect:
        params["include"] = "prospect"

    raw_result = []
    all_data = []
    included_map = {}

    # Manual pagination to capture 'included' sideloads
    params["page[size]"] = "50"
    max_pages = 100
    pages = 0

    while pages < max_pages:
        result = _api_get(f"/sequenceStates", params)
        data = result.get("data", [])
        all_data.extend(data)

        # Build map of included resources (prospects)
        for inc in result.get("included", []):
            key = f"{inc['type']}:{inc['id']}"
            included_map[key] = inc

        pages += 1
        next_link = result.get("links", {}).get("next")
        if not next_link or not data:
            break
        import urllib.parse
        parsed = urllib.parse.urlparse(next_link)
        next_params = dict(urllib.parse.parse_qsl(parsed.query))
        params.update(next_params)

    # Build simplified output
    states = []
    for item in all_data:
        attrs = item.get("attributes", {})
        prospect_ref = item.get("relationships", {}).get("prospect", {}).get("data", {})
        prospect_id = prospect_ref.get("id") if prospect_ref else None

        state = {
            "id": item.get("id"),
            "state": attrs.get("state", ""),
            "open_count": attrs.get("openCount", 0),
            "click_count": attrs.get("clickCount", 0),
            "reply_count": attrs.get("replyCount", 0),
            "bounce_count": attrs.get("bounceCount", 0),
            "deliver_count": attrs.get("deliverCount", 0),
            "replied_at": attrs.get("repliedAt"),
            "call_completed_at": attrs.get("callCompletedAt"),
            "meeting_booked_at": attrs.get("meetingBookedAt"),
            "active_at": attrs.get("activeAt"),
            "created_at": attrs.get("createdAt"),
            "state_changed_at": attrs.get("stateChangedAt"),
            "error_reason": attrs.get("errorReason"),
            "prospect_id": prospect_id,
        }

        # Attach prospect details if sideloaded
        if prospect_id:
            prospect_data = included_map.get(f"prospect:{prospect_id}")
            if prospect_data:
                p_attrs = prospect_data.get("attributes", {})
                state["prospect"] = {
                    "id": prospect_id,
                    "first_name": p_attrs.get("firstName", ""),
                    "last_name": p_attrs.get("lastName", ""),
                    "emails": p_attrs.get("emails", []),
                    "title": p_attrs.get("title", ""),
                    "company": p_attrs.get("company", ""),
                    "tags": p_attrs.get("tags", []),
                }

        states.append(state)

    return states


def get_prospect(prospect_id: int | str) -> dict | None:
    """Get a single prospect by ID."""
    try:
        result = _api_get(f"/prospects/{prospect_id}")
        data = result.get("data", {})
        attrs = data.get("attributes", {})
        return {
            "id": data.get("id"),
            "first_name": attrs.get("firstName", ""),
            "last_name": attrs.get("lastName", ""),
            "emails": attrs.get("emails", []),
            "title": attrs.get("title", ""),
            "company": attrs.get("company", ""),
            "tags": attrs.get("tags", []),
            "created_at": attrs.get("createdAt", ""),
        }
    except Exception as e:
        logger.error(f"get_prospect({prospect_id}) error: {e}")
        return None


def get_mailings_for_prospect(prospect_id: int | str, sequence_id: int | str = None) -> list[dict]:
    """
    Get all email sends (mailings) for a prospect. Optionally filter by sequence.
    Returns list of mailing dicts with engagement data + email content.
    """
    params = {
        "filter[prospect][id]": str(prospect_id),
        "sort": "-createdAt",
    }
    if sequence_id:
        params["filter[sequence][id]"] = str(sequence_id)

    raw = _api_get_all("/mailings", params)
    mailings = []
    for item in raw:
        attrs = item.get("attributes", {})
        mailings.append({
            "id": item.get("id"),
            "subject": attrs.get("subject", ""),
            "body_text": attrs.get("bodyText", ""),
            "body_html": attrs.get("bodyHtml", ""),
            "state": attrs.get("state", ""),
            "delivered_at": attrs.get("deliveredAt"),
            "opened_at": attrs.get("openedAt"),
            "clicked_at": attrs.get("clickedAt"),
            "replied_at": attrs.get("repliedAt"),
            "bounced_at": attrs.get("bouncedAt"),
            "open_count": attrs.get("openCount", 0),
            "click_count": attrs.get("clickCount", 0),
            "created_at": attrs.get("createdAt", ""),
        })
    return mailings


def get_pricing_prospect_ids(sequence_ids: list[int | str]) -> set[str]:
    """
    Bulk scan: pull ALL mailings for the given sequences and find prospect IDs
    where pricing was sent. Returns set of prospect ID strings.

    Much faster than checking mailings per-prospect (3 bulk queries vs 1600+ individual).
    """
    pricing_prospect_ids = set()
    total_mailings = 0

    pricing_signals_subject = ["codecombat licensing and pricing guide"]
    pricing_phrases = [
        "here is the link to your digital quote for",
        "you can edit these quotes yourself",
        "standard tiered pricing", "site license (unlimited)",
        "$70/license", "$49/license", "$38/license",
        "up to 99 students", "100 to 171 students", "multi-site & districts",
    ]

    for seq_id in sequence_ids:
        logger.info(f"Outreach: bulk scanning mailings for sequence {seq_id}")
        params = {
            "filter[sequence][id]": str(seq_id),
            "page[size]": "100",
        }
        pages = 0
        max_pages = 200  # safety limit

        while pages < max_pages:
            try:
                result = _api_get("/mailings", params)
            except Exception as e:
                logger.warning(f"Outreach: mailing bulk scan error on page {pages}: {e}")
                break

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                total_mailings += 1
                attrs = item.get("attributes", {})
                subject = (attrs.get("subject") or "").lower()
                body_text = (attrs.get("bodyText") or "").lower()
                body_html = (attrs.get("bodyHtml") or "").lower()
                body = body_text + body_html

                is_pricing = False

                # Signal 1: PandaDoc quote link
                if "pandadoc.com/d/" in body:
                    is_pricing = True
                # Signal 2: Pricing subject line
                elif any(s in subject for s in pricing_signals_subject):
                    is_pricing = True
                # Signal 3: Quote template content
                else:
                    has_quote = "here is the link to your digital quote for" in body
                    has_edit = "you can edit these quotes yourself" in body
                    has_tier = any(p in body for p in pricing_phrases[2:])  # tier indicators
                    if has_quote and (has_edit or has_tier):
                        is_pricing = True
                    elif has_edit and has_tier:
                        is_pricing = True

                if is_pricing:
                    # Extract prospect ID from relationship
                    prospect_ref = item.get("relationships", {}).get("prospect", {}).get("data", {})
                    pid = prospect_ref.get("id") if prospect_ref else None
                    if pid:
                        pricing_prospect_ids.add(str(pid))

            pages += 1
            next_link = result.get("links", {}).get("next")
            if not next_link:
                break
            import urllib.parse
            parsed = urllib.parse.urlparse(next_link)
            next_params = dict(urllib.parse.parse_qsl(parsed.query))
            params.update(next_params)

        logger.info(f"Outreach: sequence {seq_id} — scanned {total_mailings} mailings so far, {len(pricing_prospect_ids)} pricing found")

    logger.info(f"Outreach: bulk mailing scan complete — {total_mailings} total mailings, {len(pricing_prospect_ids)} prospects with pricing")
    return pricing_prospect_ids


def get_sequence_steps(sequence_id: int | str) -> list[dict]:
    """Get the steps for a sequence (email, call, task)."""
    params = {"filter[sequence][id]": str(sequence_id)}
    raw = _api_get_all("/sequenceSteps", params)
    steps = []
    for item in raw:
        attrs = item.get("attributes", {})
        steps.append({
            "id": item.get("id"),
            "step_type": attrs.get("stepType", ""),
            "order": attrs.get("order", 0),
            "interval": attrs.get("interval", 0),
            "name": attrs.get("name", ""),
        })
    return sorted(steps, key=lambda s: s.get("order", 0))


# ─────────────────────────────────────────────
# VALIDATION — Session 59 hardening
# ─────────────────────────────────────────────
#
# validate_sequence_inputs(...) is a standalone, zero-API helper that any
# code path can call BEFORE writing Outreach state. Catches the failures
# from Session 59 rounds 1-3 at the point where fixing them is cheapest.
#
# verify_sequence(seq_id, expected=...) is the post-write / audit
# counterpart. Hits the API to fetch live state and validate against
# expected values. Called automatically from create_sequence after write,
# callable standalone for auditing existing sequences.
#
# See ~/.claude/projects/.../memory/feedback_outreach_* for the full
# rationale behind each guard.


# Unconditional banned phrases in email body text. Phrases that are
# context-dependent (e.g. "Are you the right person?" allowed in breakup
# steps) are NOT in this list. If a phrase ever needs an exception, add
# a per-step override rather than removing it from the list.
_BANNED_BODY_PHRASES = [
    # classic sales cliches
    "just checking in", "circling back", "touch base",
    "i'd love to", "hop on a call", "quick call",
    "jump on a call", "let's connect", "15 minutes",
    "i wanted to reach out", "i dropped the ball",
    "i hope this email finds you well", "i hope this finds you well",
    # sign-off / identity cliches (signature handles identity)
    "i'm steven",
    # formulaic lead-ins
    "the #1 thing teachers tell me",
    # Session 59 specific
    "schools school by school",
]

# Unicode dash characters banned unconditionally in bodies.
# U+2014 em dash, U+2013 en dash, and the " — " 3-char pattern.
_BANNED_BODY_CHARS = ["\u2014", "\u2013", " — "]

# Automation/AI language banned in sequence name + description.
# Outreach's sequence name and description are visible to Steven's manager
# and sales team.
_BANNED_META_PHRASES = [
    "auto-generated", "auto generated", "autogenerated",
    "ai-generated", "ai generated", "ai-built", "ai built",
    "claude", "anthropic",
    "scout", "sequence_builder", "sequence builder",
    "automated", "bot-built",
]

# Steven's 5 named delivery schedules (verified in S60 from Outreach UI
# dropdown screenshots — S59 map had schedule 1 incorrectly labeled as
# "Hot Lead Mon-Fri"; the real "Hot Lead Mon-Fri" is schedule 51).
#   48 = SA Workdays
#   50 = C4 Tue-Thu Morning
#   51 = Hot Lead Mon-Fri
#   52 = Admin Mon-Thurs Multi-Window
#   53 = Teacher Tue-Thu Multi-Window
# Schedule 1 "Weekday Business Hours" is a legacy default (131 of Steven's
# sequences are on it) but is NOT one of the 5 targeted schedules Scout
# should use for new sequences.
# Overridable via OUTREACH_ALLOWED_SCHEDULE_IDS env var (comma-separated).
_DEFAULT_ALLOWED_SCHEDULE_IDS = {48, 50, 51, 52, 53}


def _get_allowed_schedule_ids() -> set[int]:
    """Resolve the allowlist: env var first, fall back to hardcoded default."""
    raw = os.environ.get("OUTREACH_ALLOWED_SCHEDULE_IDS", "")
    if raw.strip():
        try:
            return {int(x.strip()) for x in raw.split(",") if x.strip()}
        except ValueError:
            logger.warning(
                f"OUTREACH_ALLOWED_SCHEDULE_IDS env var is malformed: {raw!r}. "
                f"Falling back to default allowlist."
            )
    return set(_DEFAULT_ALLOWED_SCHEDULE_IDS)


def _get_step_bodies(steps: list[dict]) -> list[str]:
    """Extract body_html from each step for content checks."""
    return [str(s.get("body_html", "") or "") for s in steps]


def _scan_banned_phrases(text: str, phrases: list[str]) -> list[str]:
    """Return the list of banned phrases found in text (case-insensitive)."""
    if not text:
        return []
    lower = text.lower()
    return [p for p in phrases if p.lower() in lower]


def _scan_banned_chars(text: str, chars: list[str]) -> list[str]:
    """Return banned characters/patterns found in text (literal match)."""
    if not text:
        return []
    return [c for c in chars if c in text]


def _resolve_step_interval_seconds(step: dict, fallback: int) -> int:
    """Resolve a step's interval in seconds.
    Prefers explicit interval_seconds; falls back to legacy interval_minutes
    (multiplied by 60); otherwise uses the given fallback.
    """
    if "interval_seconds" in step:
        return int(step["interval_seconds"])
    if "interval_minutes" in step:
        return int(step["interval_minutes"]) * 60
    return fallback


def validate_sequence_inputs(
    name: str,
    steps: list[dict],
    description: str = "",
    schedule_id: int | None = None,
    *,
    allowed_schedule_ids: set[int] | None = None,
    meeting_link: str | None = None,
    require_cc_schools_link: bool = True,
    min_interval_seconds: int = 432000,   # 5 days — cold default
    max_interval_seconds: int = 2592000,  # 30 days — sanity cap
    first_step_max_seconds: int = 600,    # step 1 ≤10 min after add
    allow_no_schedule: bool = False,
    max_repetition: dict[str, int] | None = None,
) -> dict:
    """
    Pre-write validation for an Outreach sequence. Zero API calls.

    Designed to be called from create_sequence, from scripts, from
    _on_prospect_research_complete, from any code path that writes Outreach
    state. Returns {"passed", "failures", "warnings"}.

    Failures block the write. Warnings are informational.

    Defaults target cold outreach (5+ day cadence, codecombat.com/schools
    link required, owned schedule required). Non-cold callers (hot lead,
    license request, conference followup) override the relevant kwargs:
        validate_sequence_inputs(
            ..., require_cc_schools_link=False, min_interval_seconds=3600,
        )
    """
    failures: list[str] = []
    warnings: list[str] = []

    # ── 1. Name + description: automation language ────────────────────
    for field_name, field_value in [("name", name), ("description", description)]:
        hits = _scan_banned_phrases(field_value, _BANNED_META_PHRASES)
        if hits:
            failures.append(
                f"{field_name} contains banned automation language {hits!r}. "
                f"Outreach fields are visible to Steven's manager and team."
            )

    # ── 2. Schedule required unless overridden ────────────────────────
    if schedule_id is None and not allow_no_schedule:
        failures.append(
            "schedule_id is required. Pass schedule_id=<N> where N is one of "
            "Steven's 5 named schedules (see feedback_outreach_schedule_id_map.md), "
            "or pass allow_no_schedule=True for hot-lead override."
        )

    # ── 3. Schedule ID in allowlist ───────────────────────────────────
    if schedule_id is not None:
        allowlist = allowed_schedule_ids if allowed_schedule_ids is not None else _get_allowed_schedule_ids()
        if int(schedule_id) not in allowlist:
            failures.append(
                f"schedule_id={schedule_id} is not in the allowed schedule IDs {sorted(allowlist)}. "
                f"Session 59 round 2 shipped with a rogue schedule 19 recommendation; this guard "
                f"prevents that. See feedback_outreach_schedule_id_map.md for the current ID list."
            )

    # ── 4. Step count ≥1 ──────────────────────────────────────────────
    if not steps or len(steps) < 1:
        failures.append(f"steps must contain at least 1 entry (got {len(steps) if steps else 0}).")
        # Short-circuit further per-step checks if empty
        return {"passed": not failures, "failures": failures, "warnings": warnings}

    # ── 5, 6. Per-step interval sanity ────────────────────────────────
    for i, step in enumerate(steps):
        interval = _resolve_step_interval_seconds(
            step, fallback=(300 if i == 0 else min_interval_seconds)
        )
        if i == 0:
            if interval < 1 or interval > first_step_max_seconds:
                failures.append(
                    f"step 1 interval={interval}s is outside the allowed first-step range "
                    f"[1, {first_step_max_seconds}] (typical: 300s = 5 min)."
                )
        else:
            if interval < min_interval_seconds:
                failures.append(
                    f"step {i+1} interval={interval}s is below minimum {min_interval_seconds}s "
                    f"({min_interval_seconds//86400} days). Session 59 round 2 shipped intervals "
                    f"60x too short because the wrapper accepted minute values as seconds. "
                    f"Override via min_interval_seconds=<N> for non-cold cadences."
                )
            if interval > max_interval_seconds:
                warnings.append(
                    f"step {i+1} interval={interval}s exceeds max {max_interval_seconds}s "
                    f"({max_interval_seconds//86400} days). Unusual but not blocked."
                )

    # ── 7. Body banned-phrase scan ────────────────────────────────────
    bodies = _get_step_bodies(steps)
    for i, body in enumerate(bodies):
        hits = _scan_banned_phrases(body, _BANNED_BODY_PHRASES)
        if hits:
            failures.append(f"step {i+1} body contains banned phrases {hits!r}.")

    # ── 8. Em/en dash detection in bodies ─────────────────────────────
    for i, body in enumerate(bodies):
        dash_hits = _scan_banned_chars(body, _BANNED_BODY_CHARS)
        if dash_hits:
            failures.append(
                f"step {i+1} body contains banned dash characters {dash_hits!r}. "
                f"Use commas or periods instead."
            )

    # ── 9. codecombat.com/schools required in ≥2 steps ────────────────
    if require_cc_schools_link:
        cc_hits = sum(1 for b in bodies if "codecombat.com/schools" in b.lower())
        if cc_hits < 2:
            failures.append(
                f"codecombat.com/schools appears in {cc_hits} step bodies; "
                f"feedback_sequence_copy_rules.md requires it hyperlinked in ≥2 steps. "
                f"Override with require_cc_schools_link=False for non-cold sequences."
            )

    # ── 10. Meeting link required in ≥1 step if provided ──────────────
    if meeting_link:
        link_hits = sum(1 for b in bodies if meeting_link in b)
        if link_hits < 1:
            failures.append(
                f"meeting_link={meeting_link!r} was provided but does not appear in any step body. "
                f"Required in ≥1 step (typically the booking CTA step)."
            )

    # ── 11. Repetition policy ─────────────────────────────────────────
    rep_policy = max_repetition if max_repetition is not None else {"one pager": 1, "one-pager": 1}
    combined_lower = " ".join(bodies).lower()
    for phrase, limit in rep_policy.items():
        count = combined_lower.count(phrase.lower())
        if count > limit:
            failures.append(
                f"phrase {phrase!r} appears {count}x across all step bodies; "
                f"policy limit is {limit}. Vary CTA language across steps."
            )

    # ── 12. Merge field presence (warning only) ───────────────────────
    merge_fields = ["{{first_name}}", "{{company}}", "{{state}}"]
    has_any_merge = any(any(mf in b for mf in merge_fields) for b in bodies)
    if not has_any_merge:
        warnings.append(
            "no Outreach merge fields ({{first_name}}, {{company}}, {{state}}) "
            "found in any step body. Cold sequences typically use at least one."
        )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }


def verify_sequence(
    seq_id: int | str,
    expected: dict | None = None,
) -> dict:
    """
    Post-write / audit verification for an Outreach sequence.

    Fetches live state (sequence + steps + templates) and validates against
    expected values. Called automatically by create_sequence after write,
    or standalone for audits.

    expected keys (all optional):
      - owner_id: int (default 11)
      - schedule_id: int (if set, must match)
      - allow_no_schedule: bool (default False)
      - step_count: int
      - step_interval_ranges: list[tuple[int, int]]  # [(min, max), ...] per step in order
      - meeting_link: str  # must appear in ≥1 step body
      - require_cc_schools_link: bool (default True)

    Returns:
        {
            "passed": bool | None,   # None = couldn't verify (network error)
            "failures": list[str],
            "warnings": list[str],
            "errors": list[str],     # fetch errors, distinct from failures
            "fetched": {             # cached for callers that want the data
                "sequence": dict,
                "steps": list,
                "templates": list,
            },
        }
    """
    import time

    expected = expected or {}
    failures: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    fetched: dict = {"sequence": None, "steps": [], "templates": []}

    def _try_fetch(path: str, params: dict | None = None):
        """Fetch with one retry + 2s backoff on transient errors."""
        for attempt in range(2):
            try:
                return _api_get(path, params=params) if params else _api_get(path)
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                    continue
                errors.append(f"fetch {path} failed: {type(e).__name__}: {e}")
                return None
        return None

    # ── Fetch sequence ────────────────────────────────────────────────
    seq_resp = _try_fetch(f"/sequences/{seq_id}")
    if seq_resp is None:
        return {
            "passed": None,
            "failures": failures,
            "warnings": warnings,
            "errors": errors,
            "fetched": fetched,
        }

    seq_data = seq_resp.get("data", {})
    seq_attrs = seq_data.get("attributes", {})
    seq_rels = seq_data.get("relationships", {})
    fetched["sequence"] = seq_data

    # ── 1. Owner ──────────────────────────────────────────────────────
    owner_rel = seq_rels.get("owner", {}).get("data")
    expected_owner = expected.get("owner_id", 11)
    if not owner_rel:
        failures.append(f"owner not set (expected user id {expected_owner})")
    elif int(owner_rel.get("id", 0)) != int(expected_owner):
        failures.append(
            f"owner user id={owner_rel.get('id')} does not match expected {expected_owner}"
        )

    # ── 2. Schedule ───────────────────────────────────────────────────
    sched_rel = seq_rels.get("schedule", {}).get("data")
    allow_no_schedule = bool(expected.get("allow_no_schedule", False))
    if not sched_rel:
        if not allow_no_schedule:
            failures.append("schedule not attached (use allow_no_schedule=True for hot-lead override)")
    else:
        sched_id = int(sched_rel.get("id", 0))
        expected_sched = expected.get("schedule_id")
        if expected_sched is not None and sched_id != int(expected_sched):
            failures.append(f"schedule id={sched_id} does not match expected {expected_sched}")
        # Always enforce allowlist (unless explicitly allowed)
        allowlist = _get_allowed_schedule_ids()
        if sched_id not in allowlist:
            failures.append(
                f"schedule id={sched_id} is not in the allowed schedule IDs {sorted(allowlist)}."
            )

    # ── 3. Name + description banned language ────────────────────────
    name = seq_attrs.get("name", "") or ""
    description = seq_attrs.get("description", "") or ""
    for field_name, field_value in [("name", name), ("description", description)]:
        hits = _scan_banned_phrases(field_value, _BANNED_META_PHRASES)
        if hits:
            failures.append(f"{field_name} contains banned automation language {hits!r}")

    # ── 4. Fetch steps ────────────────────────────────────────────────
    steps_resp = _try_fetch("/sequenceSteps", params={"filter[sequence][id]": str(seq_id)})
    if steps_resp is None:
        return {
            "passed": None,
            "failures": failures,
            "warnings": warnings,
            "errors": errors,
            "fetched": fetched,
        }

    raw_steps = steps_resp.get("data", [])
    # Sort by order
    raw_steps = sorted(raw_steps, key=lambda s: s.get("attributes", {}).get("order", 0))
    fetched["steps"] = raw_steps

    # ── 5. Step count ─────────────────────────────────────────────────
    expected_count = expected.get("step_count")
    if expected_count is not None and len(raw_steps) != int(expected_count):
        failures.append(
            f"step count={len(raw_steps)} does not match expected {expected_count}"
        )

    # ── 6. Step interval ranges ───────────────────────────────────────
    expected_ranges = expected.get("step_interval_ranges")
    if expected_ranges:
        for i, step in enumerate(raw_steps):
            if i >= len(expected_ranges):
                break
            interval = int(step.get("attributes", {}).get("interval", 0))
            lo, hi = expected_ranges[i]
            if interval < lo or interval > hi:
                failures.append(
                    f"step {i+1} (id={step.get('id')}) interval={interval}s outside expected range [{lo}, {hi}]"
                )

    # ── 7. Fetch templates for each step and scan bodies ─────────────
    # GET /sequenceTemplates?filter[sequenceStep][id]=<id> → /templates/<id>
    step_bodies: list[str] = []
    for i, step in enumerate(raw_steps):
        step_id = step.get("id")
        st_resp = _try_fetch("/sequenceTemplates", params={"filter[sequenceStep][id]": str(step_id)})
        if st_resp is None:
            warnings.append(f"could not fetch sequenceTemplates for step {step_id}; skipping body scan")
            continue
        st_data = st_resp.get("data", [])
        if not st_data:
            failures.append(f"step {i+1} (id={step_id}) has no linked template — malformed sequence")
            continue
        template_rel = st_data[0].get("relationships", {}).get("template", {}).get("data")
        if not template_rel:
            failures.append(f"step {i+1} sequenceTemplate has no template relationship — malformed")
            continue
        template_id = template_rel.get("id")
        tmpl_resp = _try_fetch(f"/templates/{template_id}")
        if tmpl_resp is None:
            warnings.append(f"could not fetch template {template_id} for step {step_id}")
            continue
        tmpl_attrs = tmpl_resp.get("data", {}).get("attributes", {})
        body_html = tmpl_attrs.get("bodyHtml", "") or ""
        fetched["templates"].append({
            "step_id": step_id,
            "template_id": template_id,
            "subject": tmpl_attrs.get("subject", ""),
            "body_html": body_html,
        })
        if not body_html:
            failures.append(f"step {i+1} template body is empty — malformed")
            continue
        step_bodies.append(body_html)

        # Banned phrases in body
        banned_hits = _scan_banned_phrases(body_html, _BANNED_BODY_PHRASES)
        if banned_hits:
            failures.append(f"step {i+1} body contains banned phrases {banned_hits!r}")

        # Banned dash characters
        dash_hits = _scan_banned_chars(body_html, _BANNED_BODY_CHARS)
        if dash_hits:
            failures.append(f"step {i+1} body contains banned dash characters {dash_hits!r}")

    # ── 8. Aggregate body checks (links + meeting_link) ──────────────
    if expected.get("require_cc_schools_link", True):
        cc_hits = sum(1 for b in step_bodies if "codecombat.com/schools" in b.lower())
        if cc_hits < 2:
            failures.append(
                f"codecombat.com/schools appears in {cc_hits} step bodies; expected ≥2"
            )

    meeting_link = expected.get("meeting_link")
    if meeting_link:
        link_hits = sum(1 for b in step_bodies if meeting_link in b)
        if link_hits < 1:
            failures.append(
                f"meeting_link {meeting_link!r} not found in any step body"
            )

    return {
        "passed": len(failures) == 0 and not errors,
        "failures": failures,
        "warnings": warnings,
        "errors": errors,
        "fetched": fetched,
    }


# ─────────────────────────────────────────────
# WRITE METHODS — Sequence Creation (Session 38+)
# ─────────────────────────────────────────────

def get_mailboxes() -> list[dict]:
    """Get available mailboxes for sending sequences."""
    raw = _api_get_all("/mailboxes")
    mailboxes = []
    for item in raw:
        attrs = item.get("attributes", {})
        mailboxes.append({
            "id": item.get("id"),
            "email": attrs.get("email", ""),
            "username": attrs.get("username", ""),
        })
    return mailboxes


def create_sequence(
    name: str,
    steps: list[dict],
    description: str = "",
    tags: list[str] | None = None,
    schedule_id: int | None = None,
    *,
    allow_no_schedule: bool = False,
    meeting_link: str | None = None,
    require_cc_schools_link: bool = True,
    min_interval_seconds: int = 432000,  # 5 days — cold default
    verify_after_create: bool = True,
    max_repetition: dict[str, int] | None = None,
) -> dict:
    """
    Create a complete sequence in Outreach with email steps.

    Session 59 hardening: this function now calls `validate_sequence_inputs`
    BEFORE any write and `verify_sequence` AFTER the write (unless disabled
    via `verify_after_create=False` for bulk creation).

    If input validation fails, returns {"error": ..., "validation_failures": [...]}
    with no API calls made. If post-write verification fails, returns the
    sequence_id plus a `validation_failures` field so the caller knows the
    write landed but the state is malformed.

    Args:
        name: Sequence name (shown in Outreach UI). No automation language.
        steps: List of step dicts, each with subject, body_html, interval_seconds
            (legacy interval_minutes accepted and converted).
        description: Optional sequence description. No automation language.
        tags: Optional list of tags.
        schedule_id: REQUIRED unless allow_no_schedule=True. Must be in the
            allowlist (env var OUTREACH_ALLOWED_SCHEDULE_IDS or default
            {48, 50, 51, 52, 53} — Steven's 5 named schedules, see
            feedback_outreach_schedule_id_map.md).
        allow_no_schedule: Override for hot-lead flows where no schedule is
            intentional. Default False.
        meeting_link: Campaign-specific booking URL. If provided, must appear
            in ≥1 step body.
        require_cc_schools_link: If True (default), codecombat.com/schools
            must appear in ≥2 step bodies. Set False for non-cold sequences.
        min_interval_seconds: Minimum interval between subsequent steps.
            Default 432000 (5 days, cold). Override for hot lead / license
            request (e.g. 3600 for 1 hour).
        verify_after_create: If True (default), call verify_sequence after
            write. Disable for bulk creation to avoid rate limiting;
            callers batch-verify at the end.
        max_repetition: Optional repetition policy. Default:
            {"one pager": 1, "one-pager": 1}.

    Returns:
        {
            "sequence_id": str,
            "name": str,
            "steps": [...],
            "errors": [...],                  # per-step API errors during create
            "validation_failures": [...],     # pre or post-write validation
            "validation_warnings": [...],
        }
    """
    # ── Pre-write input validation ────────────────────────────────────
    validation = validate_sequence_inputs(
        name=name,
        steps=steps,
        description=description,
        schedule_id=schedule_id,
        meeting_link=meeting_link,
        require_cc_schools_link=require_cc_schools_link,
        min_interval_seconds=min_interval_seconds,
        allow_no_schedule=allow_no_schedule,
        max_repetition=max_repetition,
    )
    if not validation["passed"]:
        logger.error(
            f"create_sequence refusing to write: validation failed with "
            f"{len(validation['failures'])} failure(s): {validation['failures']}"
        )
        return {
            "error": "Pre-write validation failed. See validation_failures for details.",
            "validation_failures": validation["failures"],
            "validation_warnings": validation["warnings"],
        }
    if validation["warnings"]:
        logger.warning(f"create_sequence proceeding with warnings: {validation['warnings']}")

    logger.info(f"Creating Outreach sequence: {name} ({len(steps)} steps)")

    # Step 1: Create the sequence
    # Owner is REQUIRED for Steven to see the sequence in his "My Sequences"
    # view and be able to activate it. The POST /sequences endpoint defaults
    # owner to null if not explicitly set — even when creator=authenticated
    # user. Always set owner to the authenticated user's ID (Steven = 11).
    seq_attrs = {
        "name": name,
        "sequenceType": "interval",
    }
    if description:
        seq_attrs["description"] = description
    if tags:
        seq_attrs["tags"] = tags

    # Resolve owner ID: explicit env var first, then cached _user_id, then fall
    # back to 11 (Steven) as the hard default for single-operator Scout.
    owner_user_id = os.environ.get("OUTREACH_OWNER_USER_ID") or _user_id or "11"
    try:
        owner_user_id_int = int(owner_user_id)
    except (TypeError, ValueError):
        owner_user_id_int = 11

    seq_relationships = {
        "owner": {
            "data": {"type": "user", "id": owner_user_id_int}
        }
    }
    if schedule_id is not None:
        seq_relationships["schedule"] = {
            "data": {"type": "schedule", "id": int(schedule_id)}
        }

    seq_payload = {
        "data": {
            "type": "sequence",
            "attributes": seq_attrs,
            "relationships": seq_relationships,
        }
    }

    try:
        seq_result = _api_post("/sequences", seq_payload)
    except Exception as e:
        return {"error": f"Failed to create sequence: {e}"}

    seq_id = seq_result.get("data", {}).get("id")
    if not seq_id:
        return {"error": f"No sequence ID returned: {seq_result}"}

    logger.info(f"  Created sequence ID: {seq_id} (owner user_id={owner_user_id_int}, schedule_id={schedule_id})")

    created_steps = []

    for i, step in enumerate(steps):
        subject = step.get("subject", f"Step {i+1}")
        body_html = step.get("body_html", "")
        # Outreach sequenceStep.interval is in SECONDS.
        # Prefer explicit interval_seconds; fall back to legacy interval_minutes
        # (multiplied by 60) for backward compat with any older caller.
        # Default: step 1 = 300s (5 min), subsequent steps = 432000s (5 days,
        # the minimum Steven-approved cold cadence).
        if "interval_seconds" in step:
            interval = int(step["interval_seconds"])
        elif "interval_minutes" in step:
            interval = int(step["interval_minutes"]) * 60
        else:
            interval = 300 if i == 0 else 432000

        # Template resolution: if the step carries an existing `template_id`,
        # reuse that template directly (no POST /templates). Pattern promoted
        # from scripts/create_c4_sequences.py (S43) per Rule 18. Used by DRE
        # (S73) to reuse info-dump template 43784 across 13 sequences without
        # creating 13 duplicates.
        reused_template_id = step.get("template_id")
        if reused_template_id:
            template_id = int(reused_template_id)
            logger.info(f"  Step {i+1}: reusing existing template {template_id}")
        else:
            # Step 2a: Create template
            template_payload = {
                "data": {
                    "type": "template",
                    "attributes": {
                        "subject": subject,
                        "bodyHtml": body_html,
                    },
                }
            }

            try:
                template_result = _api_post("/templates", template_payload)
                template_id = template_result.get("data", {}).get("id")
            except Exception as e:
                logger.error(f"  Failed to create template for step {i+1}: {e}")
                created_steps.append({"step": i+1, "error": str(e)})
                continue

        # Step 2b: Create sequence step
        step_payload = {
            "data": {
                "type": "sequenceStep",
                "attributes": {
                    "stepType": "auto_email",
                    "interval": interval,
                    "order": i + 1,
                },
                "relationships": {
                    "sequence": {
                        "data": {
                            "type": "sequence",
                            "id": int(seq_id),
                        }
                    }
                },
            }
        }

        try:
            step_result = _api_post("/sequenceSteps", step_payload)
            step_id = step_result.get("data", {}).get("id")
        except Exception as e:
            logger.error(f"  Failed to create step {i+1}: {e}")
            created_steps.append({"step": i+1, "template_id": template_id, "error": str(e)})
            continue

        # Step 2c: Link template to step
        link_payload = {
            "data": {
                "type": "sequenceTemplate",
                "relationships": {
                    "sequenceStep": {
                        "data": {
                            "type": "sequenceStep",
                            "id": int(step_id),
                        }
                    },
                    "template": {
                        "data": {
                            "type": "template",
                            "id": int(template_id),
                        }
                    },
                },
            }
        }

        try:
            _api_post("/sequenceTemplates", link_payload)
        except Exception as e:
            logger.error(f"  Failed to link template to step {i+1}: {e}")
            created_steps.append({
                "step": i+1, "step_id": step_id,
                "template_id": template_id, "error": f"Link failed: {e}",
            })
            continue

        created_steps.append({
            "step": i+1,
            "step_id": step_id,
            "template_id": template_id,
            "subject": subject,
            "interval_seconds": interval,
        })
        logger.info(f"  Step {i+1}: template={template_id}, step={step_id}, interval={interval}s, subject={subject[:50]}")

    result = {
        "sequence_id": seq_id,
        "name": name,
        "steps": created_steps,
        "errors": [s for s in created_steps if "error" in s],
        "validation_warnings": validation["warnings"],  # from pre-write validator
    }

    if result["errors"]:
        logger.warning(f"  Sequence created with {len(result['errors'])} errors")
    else:
        logger.info(f"  Sequence '{name}' created successfully with {len(created_steps)} steps")

    # ── Post-write verification (Session 59 hardening) ──────────────
    # Auto-invoke verify_sequence to catch drift between intended state and
    # what Outreach actually wrote. Disabled for bulk creation via
    # verify_after_create=False — bulk callers batch-verify at the end.
    if verify_after_create and seq_id:
        # Build expected state from the parameters we actually passed
        step_interval_ranges = []
        for i, s in enumerate(steps):
            iv = _resolve_step_interval_seconds(s, fallback=(300 if i == 0 else min_interval_seconds))
            step_interval_ranges.append((iv, iv))  # exact match expected
        expected = {
            "schedule_id": schedule_id,
            "allow_no_schedule": allow_no_schedule,
            "step_count": len(steps),
            "step_interval_ranges": step_interval_ranges,
            "meeting_link": meeting_link,
            "require_cc_schools_link": require_cc_schools_link,
        }
        post_result = verify_sequence(seq_id, expected=expected)
        if post_result["passed"] is False:
            logger.error(
                f"  POST-WRITE verification FAILED for seq {seq_id}: "
                f"{post_result['failures']}"
            )
            result["validation_failures"] = post_result["failures"]
        elif post_result["passed"] is None:
            logger.warning(
                f"  POST-WRITE verification could not fetch live state for seq {seq_id}: "
                f"{post_result['errors']}"
            )
            result["validation_errors"] = post_result["errors"]
        else:
            logger.info(f"  POST-WRITE verification PASSED for seq {seq_id}")

    return result


# ─────────────────────────────────────────────
# PROSPECT WRITE METHODS (Session 61 — promoted from Sessions 38/43 ephemeral scripts)
# ─────────────────────────────────────────────
#
# These four functions commit the POST /prospects + POST /sequenceStates patterns
# that Sessions 38 and 43 used as one-shot inline scripts. The library-level
# capture satisfies Rule 18 (never re-derive prospect-add code; use the committed
# functions) and Rule 17 (every prospect create requires a populated IANA
# timezone, enforced by validate_prospect_inputs at the code boundary).
#
# Design mirrors the S59 sequence hardening pattern:
#   - validate_prospect_inputs is a standalone, zero-API-call validator
#   - create_prospect calls it first and refuses to POST on failure
#   - find_prospect_by_email lets the caller dedup before create
#   - add_prospect_to_sequence is a thin POST /sequenceStates wrapper

# Placeholder/reserved email prefixes that always produce hard bounces.
_PLACEHOLDER_EMAIL_PREFIXES = (
    "[email",      # literal template leaks like "[email protected]"
    "test@",
    "example@",
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "postmaster@",
    "mailer-daemon@",
    "abuse@",
)

# Generic free-mail domains that indicate the contact is a personal address
# rather than a legitimate work address. Blocked unless explicitly allow-listed
# (caller passes allow_generic_email=True for cases where a personal email is
# intentional, e.g., a sole-proprietor LLC).
_GENERIC_FREE_MAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "ymail.com",
    "hotmail.com", "hotmail.co.uk",
    "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "protonmail.com", "proton.me",
})

# Regex for validating the local-part of an email. Rejects apostrophes
# (the O'Brien bug from S61 diocesan drip — apostrophe local-parts technically
# parse under RFC 5322 quoted-strings but most SMTP servers reject them on send),
# whitespace, and obvious garbage. Intentionally strict.
_EMAIL_LOCAL_RE = re.compile(r"^[A-Za-z0-9._+\-]+$") if False else None
# Import re lazily to match the existing pattern in validate_sequence_inputs
import re as _re  # noqa: E402 — placed after helpers to avoid reorder churn

_EMAIL_LOCAL_PART_RE = _re.compile(r"^[A-Za-z0-9._+\-]+$")


def validate_prospect_inputs(
    first_name: str,
    last_name: str,
    email: str,
    *,
    title: str = "",
    company: str = "",
    state: str = "",
    timezone: str = "",
    tags: list[str] | None = None,
    allow_generic_email: bool = False,
) -> dict:
    """
    Pre-write validation for an Outreach prospect. Zero API calls.

    Returns {"passed": bool, "failures": list[str], "warnings": list[str]}.
    Never raises. All failures are collected so the caller can log or display
    the full list rather than fix-fail-fix-fail.

    Hard checks (Session 61 Rule 17 — timezone is code-enforced, not process):
      - first_name non-empty
      - last_name non-empty
      - email local@domain shape, no apostrophe in local-part, no whitespace
      - email prefix not a placeholder ("[email...", "test@", "noreply@", ...)
      - email domain not in generic free-mail set (unless allow_generic_email=True)
      - timezone non-empty AND parses via zoneinfo.ZoneInfo without raising
      - title/company do not contain automation language (reuses S59 scanner)
    """
    from tools.timezone_lookup import is_valid_iana_timezone

    failures: list[str] = []
    warnings: list[str] = []

    # ── 1. Name fields non-empty ──────────────────────────────────────
    if not (first_name or "").strip():
        failures.append("first_name is empty. Every prospect must have a first name.")
    if not (last_name or "").strip():
        failures.append("last_name is empty. Every prospect must have a last name.")

    # ── 2. Email shape + placeholder + domain checks ──────────────────
    email_clean = (email or "").strip().lower()
    if not email_clean:
        failures.append("email is empty. Every prospect must have an email address.")
    else:
        # Placeholder prefix check runs BEFORE the '@' count check because
        # Cloudflare email-obfuscation masks like '[email protected]' have
        # ZERO '@' signs and should be caught by the placeholder rule, not the
        # shape rule. Also catches fully-malformed strings that happen to start
        # with a known placeholder substring.
        hit_placeholder = False
        for prefix in _PLACEHOLDER_EMAIL_PREFIXES:
            if email_clean.startswith(prefix):
                failures.append(
                    f"email {email!r} starts with placeholder prefix {prefix!r}. "
                    f"This is a template/obfuscation artifact (e.g. Cloudflare email "
                    f"protection masks real addresses with '[email" " " "protected]'). "
                    f"The row needs a real email before it can ship."
                )
                hit_placeholder = True
                break

        if not hit_placeholder:
            if email_clean.count("@") != 1:
                failures.append(
                    f"email {email!r} does not have exactly one '@' character. "
                    f"Likely an obfuscated or truncated string."
                )
            else:
                local, domain = email_clean.split("@", 1)

                # Local-part shape (catches O'Brien apostrophe bug + whitespace)
                if not _EMAIL_LOCAL_PART_RE.match(local):
                    failures.append(
                        f"email local-part {local!r} contains disallowed characters. "
                        f"Allowed: A-Z a-z 0-9 . _ + - . Apostrophes, whitespace, and "
                        f"other special chars cause SMTP-side rejections even if RFC "
                        f"5322 technically permits them under quoted-string rules."
                    )

                # Domain shape
                if "." not in domain or domain.startswith(".") or domain.endswith("."):
                    failures.append(f"email domain {domain!r} is malformed.")

                # Generic free-mail block (unless allow-listed)
                if not allow_generic_email and domain in _GENERIC_FREE_MAIL_DOMAINS:
                    failures.append(
                        f"email domain {domain!r} is a generic free-mail provider. "
                        f"Cold outreach to personal addresses damages sender "
                        f"reputation. Pass allow_generic_email=True only for "
                        f"legitimate sole-proprietor cases."
                    )

    # ── 3. Timezone REQUIRED + IANA-valid (Rule 17) ───────────────────
    if not (timezone or "").strip():
        failures.append(
            "timezone is empty. Rule 17 (Session 61): every Outreach prospect "
            "create requires a populated IANA timezone string. Derive from state "
            "via tools.timezone_lookup.state_to_timezone(state). Never fall back."
        )
    elif not is_valid_iana_timezone(timezone):
        failures.append(
            f"timezone {timezone!r} is not a valid IANA identifier. "
            f"Must parse via zoneinfo.ZoneInfo(tz) without raising. "
            f"Examples: 'America/New_York', 'America/Chicago', 'America/Los_Angeles'."
        )

    # ── 4. Automation language in title / company ────────────────────
    for field_name, field_value in [("title", title), ("company", company)]:
        if field_value:
            hits = _scan_banned_phrases(field_value, _BANNED_META_PHRASES)
            if hits:
                failures.append(
                    f"{field_name} contains banned automation language {hits!r}. "
                    f"Outreach prospect fields are visible in the UI."
                )

    # ── 5. Tag sanity (warning only) ──────────────────────────────────
    if tags is not None:
        if not isinstance(tags, list):
            failures.append(f"tags must be a list, got {type(tags).__name__}.")
        elif not all(isinstance(t, str) and t for t in tags):
            failures.append("tags must be a list of non-empty strings.")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }


def create_prospect(
    first_name: str,
    last_name: str,
    email: str,
    *,
    title: str = "",
    company: str = "",
    state: str = "",
    timezone: str = "",
    tags: list[str] | None = None,
    owner_id: int = 11,
    verify_inputs: bool = True,
    allow_generic_email: bool = False,
) -> dict:
    """
    Create an Outreach prospect via POST /prospects.

    Rule 17 + S59 hardening pattern: calls validate_prospect_inputs FIRST and
    refuses to fire the HTTP request on any validation failure. If validation
    fails, returns {"error": ..., "validation_failures": [...]} with NO API call
    made. On success, returns {"prospect_id": str, "email": str}.

    Owner defaults to Steven's user ID (11). Mailbox is NOT set at prospect
    create time — it's bound at sequenceState create via add_prospect_to_sequence.

    Session 38 lesson (feedback_outreach_torecipients.md): this path does NOT
    touch toRecipients or templates. Only the prospect resource itself.
    """
    if verify_inputs:
        validation = validate_prospect_inputs(
            first_name=first_name,
            last_name=last_name,
            email=email,
            title=title,
            company=company,
            state=state,
            timezone=timezone,
            tags=tags,
            allow_generic_email=allow_generic_email,
        )
        if not validation["passed"]:
            return {
                "error": "prospect_validation_failed",
                "validation_failures": validation["failures"],
                "email": email,
            }

    email_clean = (email or "").strip().lower()

    attributes: dict = {
        "firstName": first_name.strip(),
        "lastName": last_name.strip(),
        "emails": [email_clean],
    }
    if title:
        attributes["title"] = title.strip()
        attributes["occupation"] = title.strip()
    if company:
        attributes["company"] = company.strip()
    if state:
        attributes["addressState"] = state.strip().upper()
    if timezone:
        attributes["timeZone"] = timezone.strip()
    if tags:
        attributes["tags"] = list(tags)

    payload = {
        "data": {
            "type": "prospect",
            "attributes": attributes,
            "relationships": {
                "owner": {
                    "data": {"type": "user", "id": str(owner_id)},
                },
            },
        }
    }

    try:
        response = _api_post("/prospects", payload)
    except Exception as e:
        return {
            "error": f"outreach_api_error: {e}",
            "email": email_clean,
        }

    prospect_id = response.get("data", {}).get("id")
    if not prospect_id:
        return {
            "error": "outreach_response_missing_prospect_id",
            "raw": response,
            "email": email_clean,
        }

    logger.info(f"  created prospect {prospect_id} for {email_clean}")
    return {
        "prospect_id": prospect_id,
        "email": email_clean,
    }


def find_prospect_by_email(email: str) -> dict | None:
    """
    Look up an existing Outreach prospect by email.

    Returns a dict with {"prospect_id", "email", "owner_id", "sequence_count"}
    for the first match, or None if no match.

    Used by prospect_loader for dedup: before create_prospect, check if the
    contact already exists in Outreach. If yes, reuse the existing ID and
    proceed directly to add_prospect_to_sequence.
    """
    email_clean = (email or "").strip().lower()
    if not email_clean:
        return None
    try:
        # Outreach v2 API: filter[emails] accepts a single email value
        result = _api_get("/prospects", {"filter[emails]": email_clean, "page[size]": "1"})
    except Exception as e:
        logger.warning(f"  find_prospect_by_email({email_clean}) error: {e}")
        return None

    data = result.get("data", [])
    if not data:
        return None

    item = data[0]
    attrs = item.get("attributes", {})
    owner_rel = (item.get("relationships", {}).get("owner", {}) or {}).get("data") or {}

    return {
        "prospect_id": item.get("id"),
        "email": email_clean,
        "owner_id": owner_rel.get("id"),
        "first_name": attrs.get("firstName", ""),
        "last_name": attrs.get("lastName", ""),
        "title": attrs.get("title", ""),
        "sequence_count": attrs.get("sequenceCount", 0),
    }


def add_prospect_to_sequence(
    prospect_id: str,
    sequence_id: int | str,
    *,
    mailbox_id: int = 11,
) -> dict:
    """
    Create a sequenceState linking a prospect to a sequence on a mailbox.

    POST /sequenceStates with the JSON:API relationships payload. Mailbox 11 is
    Steven's default (confirmed S61 by reading existing sequenceStates on
    sequences 1999, 1939, 1857 — all use mailbox_id=11).

    Returns {"sequence_state_id": str, "prospect_id": str, "sequence_id": str}
    on success, or {"error": ..., "prospect_id": str, "sequence_id": str}
    on failure.

    Session 38 lesson (feedback_outreach_sequence_order.md): the target sequence
    MUST be activated in the Outreach UI before this call. If the sequence is
    paused, the resulting sequenceState will go in as `paused`, not `active`.
    This function does NOT verify activation — callers should use
    prospect_loader.execute_load_plan which includes the pre-flight check.
    """
    payload = {
        "data": {
            "type": "sequenceState",
            "relationships": {
                "prospect": {
                    "data": {"type": "prospect", "id": str(prospect_id)},
                },
                "sequence": {
                    "data": {"type": "sequence", "id": str(sequence_id)},
                },
                "mailbox": {
                    "data": {"type": "mailbox", "id": str(mailbox_id)},
                },
            },
        }
    }

    try:
        response = _api_post("/sequenceStates", payload)
    except Exception as e:
        return {
            "error": f"outreach_api_error: {e}",
            "prospect_id": str(prospect_id),
            "sequence_id": str(sequence_id),
        }

    state_id = response.get("data", {}).get("id")
    if not state_id:
        return {
            "error": "outreach_response_missing_sequence_state_id",
            "raw": response,
            "prospect_id": str(prospect_id),
            "sequence_id": str(sequence_id),
        }

    logger.info(
        f"  added prospect {prospect_id} to sequence {sequence_id} "
        f"(mailbox {mailbox_id}) -> sequenceState {state_id}"
    )
    return {
        "sequence_state_id": state_id,
        "prospect_id": str(prospect_id),
        "sequence_id": str(sequence_id),
    }


# ─────────────────────────────────────────────
# SEQUENCE EXPORT
# ─────────────────────────────────────────────

def export_sequence(sequence_id: int | str) -> dict:
    """
    Export a full sequence with all settings, steps, and email content.
    Returns a dict with everything needed to recreate or rework the sequence.
    """
    # 1. Get sequence metadata
    resp = _api_get(f"/sequences/{sequence_id}")
    seq_data = resp.get("data", {})
    seq_attrs = seq_data.get("attributes", {})

    seq_info = {
        "id": seq_data.get("id"),
        "name": seq_attrs.get("name", ""),
        "description": seq_attrs.get("description", ""),
        "enabled": seq_attrs.get("enabled", False),
        "sequence_type": seq_attrs.get("sequenceType", ""),
        "sharing": seq_attrs.get("sharing", ""),
        "tags": seq_attrs.get("tags", []),
        "max_activations": seq_attrs.get("maxActivations", 0),
        "throttle_max_adds_per_day": seq_attrs.get("throttleMaxAddsPerDay", 0),
        "throttle_capacity": seq_attrs.get("throttleCapacity", 0),
        "num_contacted": seq_attrs.get("numContactedProspects", 0),
        "num_replied": seq_attrs.get("numRepliedProspects", 0),
        "open_count": seq_attrs.get("openCount", 0),
        "click_count": seq_attrs.get("clickCount", 0),
        "reply_count": seq_attrs.get("replyCount", 0),
        "bounce_count": seq_attrs.get("bounceCount", 0),
        "deliver_count": seq_attrs.get("deliverCount", 0),
        "created_at": seq_attrs.get("createdAt", ""),
        "updated_at": seq_attrs.get("updatedAt", ""),
    }

    # Get schedule relationship
    schedule_rel = seq_data.get("relationships", {}).get("schedule", {}).get("data")
    if schedule_rel:
        seq_info["schedule_id"] = schedule_rel.get("id")

    # 2. Get sequence steps
    steps_raw = _api_get_all("/sequenceSteps", {
        "filter[sequence][id]": str(sequence_id),
    })
    steps = []
    for step in sorted(steps_raw, key=lambda s: s.get("attributes", {}).get("order", 0)):
        s_attrs = step.get("attributes", {})
        steps.append({
            "id": step.get("id"),
            "step_type": s_attrs.get("stepType", ""),
            "order": s_attrs.get("order", 0),
            "interval": s_attrs.get("interval", 0),
            "name": s_attrs.get("name", ""),
            "task_note": s_attrs.get("taskNote", ""),
        })

    # 3. Get sequenceTemplates to find template IDs for each step.
    # Outreach's JSON:API does NOT support filter[sequence][id] on
    # /sequenceTemplates (returns 400). The working pattern is
    # filter[sequenceStep][id]=<step_id> one call per step — same as
    # validate_sequence_inputs at line 1115.
    step_to_template = {}
    for step in steps:
        step_id = step.get("id")
        if not step_id:
            continue
        try:
            st_resp = _api_get(
                "/sequenceTemplates",
                {"filter[sequenceStep][id]": str(step_id)},
            )
        except Exception as e:
            logger.warning(f"  sequenceTemplates fetch failed for step {step_id}: {e}")
            continue
        for st in st_resp.get("data", []) or []:
            rels = st.get("relationships", {})
            tmpl_rel = rels.get("template", {}).get("data", {})
            if tmpl_rel:
                step_to_template[str(step_id)] = str(tmpl_rel.get("id"))
                break

    # 4. Fetch each template's content
    for step in steps:
        template_id = step_to_template.get(str(step["id"]))
        if template_id:
            try:
                tmpl_resp = _api_get(f"/templates/{template_id}")
                tmpl_data = tmpl_resp.get("data", {})
                tmpl_attrs = tmpl_data.get("attributes", {})
                step["template_id"] = template_id
                step["subject"] = tmpl_attrs.get("subject", "")
                step["body_html"] = tmpl_attrs.get("bodyHtml", "")
                step["body_text"] = tmpl_attrs.get("bodyText", "")
                step["to_recipients"] = tmpl_attrs.get("toRecipients", [])
                step["cc_recipients"] = tmpl_attrs.get("ccRecipients", [])
                step["open_count"] = tmpl_attrs.get("openCount", 0)
                step["reply_count"] = tmpl_attrs.get("replyCount", 0)
            except Exception as e:
                step["template_error"] = str(e)

    seq_info["steps"] = steps
    return seq_info


def format_sequence_export(seq_info: dict) -> str:
    """Format an exported sequence as a readable markdown document."""
    lines = []
    lines.append(f"# Sequence Export: {seq_info['name']}")
    lines.append(f"*Exported from Outreach.io — ID: {seq_info['id']}*\n")

    lines.append("## Settings")
    lines.append(f"- **Type:** {seq_info.get('sequence_type', '')}")
    lines.append(f"- **Enabled:** {seq_info.get('enabled', False)}")
    lines.append(f"- **Sharing:** {seq_info.get('sharing', '')}")
    lines.append(f"- **Max Activations:** {seq_info.get('max_activations', '')}")
    lines.append(f"- **Throttle Max Adds/Day:** {seq_info.get('throttle_max_adds_per_day', '')}")
    lines.append(f"- **Tags:** {', '.join(seq_info.get('tags', [])) or 'none'}")
    if seq_info.get("schedule_id"):
        lines.append(f"- **Schedule ID:** {seq_info['schedule_id']}")
    if seq_info.get("description"):
        lines.append(f"- **Description:** {seq_info['description']}")
    lines.append(f"- **Created:** {seq_info.get('created_at', '')}")
    lines.append(f"- **Last Updated:** {seq_info.get('updated_at', '')}")

    lines.append("\n## Performance")
    lines.append(f"- Contacted: {seq_info.get('num_contacted', 0)}")
    lines.append(f"- Replied: {seq_info.get('num_replied', 0)}")
    lines.append(f"- Opens: {seq_info.get('open_count', 0)}")
    lines.append(f"- Clicks: {seq_info.get('click_count', 0)}")
    lines.append(f"- Bounced: {seq_info.get('bounce_count', 0)}")
    lines.append(f"- Delivered: {seq_info.get('deliver_count', 0)}")

    lines.append(f"\n## Steps ({len(seq_info.get('steps', []))} total)\n")

    for step in seq_info.get("steps", []):
        order = step.get("order", "?")
        step_type = step.get("step_type", "email")
        interval_sec = step.get("interval", 0)

        # Convert interval to readable format
        if interval_sec >= 86400:
            interval_str = f"{interval_sec // 86400} days"
        elif interval_sec >= 3600:
            interval_str = f"{interval_sec // 3600} hours"
        elif interval_sec >= 60:
            interval_str = f"{interval_sec // 60} minutes"
        else:
            interval_str = f"{interval_sec} seconds"

        lines.append(f"### Step {order} — {step_type.title()}")
        lines.append(f"- **Interval:** {interval_str} after previous step")
        if step.get("name"):
            lines.append(f"- **Name:** {step['name']}")
        if step.get("template_id"):
            lines.append(f"- **Template ID:** {step['template_id']}")
        if step.get("open_count") or step.get("reply_count"):
            lines.append(f"- **Opens:** {step.get('open_count', 0)} | **Replies:** {step.get('reply_count', 0)}")

        subject = step.get("subject", "")
        if subject:
            lines.append(f"\n**Subject:** {subject}")

        body_html = step.get("body_html", "")
        if body_html:
            lines.append(f"\n**Email Body (HTML):**\n```html\n{body_html}\n```")

        body_text = step.get("body_text", "")
        if body_text:
            lines.append(f"\n**Email Body (Plain Text):**\n```\n{body_text}\n```")

        if step.get("task_note"):
            lines.append(f"\n**Task Note:** {step['task_note']}")

        if step.get("template_error"):
            lines.append(f"\n⚠️ **Template fetch error:** {step['template_error']}")

        lines.append("")  # blank line between steps

    return "\n".join(lines)


def _slugify(name: str) -> str:
    """Lowercase + replace non-alphanumerics with _ + collapse repeats."""
    if not name:
        return ""
    import re as _re

    lowered = name.lower()
    cleaned = _re.sub(r"[^a-z0-9]+", "_", lowered)
    return cleaned.strip("_")


def _html_to_markdown(html: str) -> str:
    """
    Best-effort HTML -> markdown converter for Outreach step bodies.

    Keeps things simple and deterministic:
      - <br>, <br/>, <br /> -> newline
      - <p>...</p> -> paragraph with blank line separator
      - <a href="URL">TEXT</a> -> [TEXT](URL)
      - <strong>/<b>/<em>/<i> -> dropped (text kept)
      - HTML entities decoded via html.unescape

    Not a full HTML parser — just good enough that a claude.ai starter
    pasted back into campaigns/<slug>.md is legible and editable.
    Round-trip is one-way: markdown output is not re-rendered to HTML
    on import; load_campaign.py passes step.body through as-is to
    create_sequence, so claude.ai output can be plain text or HTML.
    """
    if not html:
        return ""
    import html as _html
    import re as _re

    text = html
    text = _re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=_re.IGNORECASE)
    text = _re.sub(r"<\s*/\s*p\s*>", "\n\n", text, flags=_re.IGNORECASE)
    text = _re.sub(r"<\s*p\s*[^>]*>", "", text, flags=_re.IGNORECASE)
    text = _re.sub(
        r'<\s*a\s+[^>]*href\s*=\s*"([^"]*)"[^>]*>(.*?)<\s*/\s*a\s*>',
        r"[\2](\1)",
        text,
        flags=_re.IGNORECASE | _re.DOTALL,
    )
    text = _re.sub(
        r"<\s*/?(strong|b|em|i|span|div)\b[^>]*>",
        "",
        text,
        flags=_re.IGNORECASE,
    )
    text = _html.unescape(text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def export_sequence_for_editing(
    sequence_id: int | str,
    *,
    role: str = "other",
    target_role_label: str = "",
    slug_override: str = "",
) -> str:
    """
    Fetch an existing Outreach sequence and render it as a
    campaigns/<slug>.md starter — same markdown schema as
    tools/campaign_file.py parses.

    Purpose: Steven pipes this output to a file, opens it in claude.ai,
    iterates on the copy as a starter for a new campaign, then saves the
    result back into campaigns/ for load_campaign.py to ingest.

    v1 caveats:
      - Only produces a single-variant campaign. Steven can add more
        `## variant: <role>` sections manually after pasting into claude.ai.
      - Step bodies are copied as-is (typically HTML from Outreach). The
        parser stores them opaquely, so round-trip is lossless; claude.ai
        can rewrite the HTML if Steven wants a cleaner starter.
      - drip_days defaults to a single placeholder (today). Steven sets
        the real dates when finalizing the new campaign file.
    """
    from datetime import date as _date

    # Local import to avoid a hard dep at module import time.
    from tools.campaign_file import (
        Campaign,
        CampaignStep,
        CampaignVariant,
        SECONDS_PER_DAY,
        VALID_ROLES,
        dump_campaign,
    )

    role = (role or "other").lower()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")

    seq_info = export_sequence(sequence_id)

    name = seq_info.get("name") or f"Exported Sequence {sequence_id}"
    if slug_override:
        slug = slug_override
    else:
        slug = _slugify(name) or f"sequence_{sequence_id}"

    schedule_id_raw = seq_info.get("schedule_id")
    schedule_id = int(schedule_id_raw) if schedule_id_raw else 0

    raw_steps = seq_info.get("steps") or []
    campaign_steps: list[CampaignStep] = []
    for i, s in enumerate(raw_steps, start=1):
        subject = (s.get("subject") or s.get("name") or f"Step {i}").strip()
        raw_body = s.get("body_html") or s.get("body_text") or ""
        body = _html_to_markdown(raw_body)
        interval_seconds = int(s.get("interval") or 0)
        campaign_steps.append(
            CampaignStep(
                step_number=i,
                subject=subject,
                body=body,
                interval_seconds=interval_seconds,
            )
        )

    if not campaign_steps:
        raise ValueError(
            f"sequence {sequence_id} has no steps with fetched template content"
        )

    step_intervals_days = [
        max(0, round(s.interval_seconds / SECONDS_PER_DAY)) for s in campaign_steps
    ]

    variant = CampaignVariant(
        role=role,
        target_role_label=target_role_label or "TBD — fill in when editing",
        num_steps=len(campaign_steps),
        steps=campaign_steps,
    )

    campaign = Campaign(
        name=name,
        slug=slug,
        schedule_id=schedule_id,
        drip_days=[_date.today()],
        tag_template=f"{slug}-{{role}}",
        sleep_seconds=(60, 180),
        step_intervals_days=step_intervals_days,
        variants={role: variant},
    )

    return dump_campaign(campaign)
