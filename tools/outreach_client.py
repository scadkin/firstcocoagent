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
) -> dict:
    """
    Create a complete sequence in Outreach with email steps.

    Args:
        name: Sequence name (shown in Outreach UI)
        steps: List of step dicts, each with:
            - subject: Email subject line
            - body_html: HTML email body
            - interval_minutes: Minutes after previous step (first step = 5 min)
        description: Optional sequence description
        tags: Optional list of tags

    Returns dict with sequence details + step/template IDs, or error.

    Flow:
        1. Create sequence
        2. For each step: create template → create sequenceStep → link via sequenceTemplate
    """
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

    seq_payload = {
        "data": {
            "type": "sequence",
            "attributes": seq_attrs,
            "relationships": {
                "owner": {
                    "data": {"type": "user", "id": owner_user_id_int}
                }
            },
        }
    }

    try:
        seq_result = _api_post("/sequences", seq_payload)
    except Exception as e:
        return {"error": f"Failed to create sequence: {e}"}

    seq_id = seq_result.get("data", {}).get("id")
    if not seq_id:
        return {"error": f"No sequence ID returned: {seq_result}"}

    logger.info(f"  Created sequence ID: {seq_id} (owner user_id={owner_user_id_int})")

    created_steps = []

    for i, step in enumerate(steps):
        subject = step.get("subject", f"Step {i+1}")
        body_html = step.get("body_html", "")
        interval = step.get("interval_minutes", 5 if i == 0 else 1440)

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
            "interval_minutes": interval,
        })
        logger.info(f"  Step {i+1}: template={template_id}, step={step_id}, interval={interval}min, subject={subject[:50]}")

    result = {
        "sequence_id": seq_id,
        "name": name,
        "steps": created_steps,
        "errors": [s for s in created_steps if "error" in s],
    }

    if result["errors"]:
        logger.warning(f"  Sequence created with {len(result['errors'])} errors")
    else:
        logger.info(f"  Sequence '{name}' created successfully with {len(created_steps)} steps")

    return result


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

    # 3. Get sequenceTemplates to find template IDs for each step
    seq_templates_raw = _api_get_all("/sequenceTemplates", {
        "filter[sequence][id]": str(sequence_id),
    })
    step_to_template = {}
    for st in seq_templates_raw:
        rels = st.get("relationships", {})
        step_rel = rels.get("sequenceStep", {}).get("data", {})
        tmpl_rel = rels.get("template", {}).get("data", {})
        if step_rel and tmpl_rel:
            step_to_template[str(step_rel.get("id"))] = str(tmpl_rel.get("id"))

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
