"""
tools/github_pusher.py
Push files directly to GitHub using the Contents API.
Phase 4: Scout can commit code without Steven touching GitHub.

Uses GITHUB_TOKEN + GITHUB_REPO already in Railway env vars.
Same auth pattern as memory_manager._commit_to_github().
"""

import base64
import logging
import requests
from agent.config import GITHUB_TOKEN, GITHUB_REPO

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _get_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get_file_sha(filepath: str) -> str | None:
    """Get the current SHA of a file (required for updates). Returns None if file doesn't exist."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filepath}"
    resp = requests.get(url, headers=_get_headers(), timeout=10)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def push_file(filepath: str, content: str, commit_message: str = None) -> dict:
    """
    Push a file to GitHub. Creates if new, updates if exists.

    Args:
        filepath: Repo-relative path, e.g. 'agent/main.py'
        content: Full file content as a string
        commit_message: Commit message (auto-generated if None)

    Returns:
        dict with keys: success (bool), url (str), message (str)
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {
            "success": False,
            "url": "",
            "message": "❌ GITHUB_TOKEN or GITHUB_REPO not set in Railway env vars.",
        }

    if not commit_message:
        commit_message = f"Scout: update {filepath}"

    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    sha = _get_file_sha(filepath)

    payload = {
        "message": commit_message,
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha  # Required for updates; omit for new files

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filepath}"
    resp = requests.put(url, headers=_get_headers(), json=payload, timeout=15)

    if resp.status_code in (200, 201):
        data = resp.json()
        html_url = data.get("content", {}).get("html_url", "")
        action = "updated" if sha else "created"
        logger.info(f"GitHub push success: {filepath} ({action})")
        return {
            "success": True,
            "url": html_url,
            "message": f"✅ `{filepath}` {action} on GitHub.",
        }
    else:
        err = resp.json().get("message", resp.text)
        logger.error(f"GitHub push failed: {filepath} — {err}")
        return {
            "success": False,
            "url": "",
            "message": f"❌ GitHub push failed: {err}",
        }


def list_repo_files(path: str = "") -> list[str]:
    """
    List files in a repo directory. Useful for Scout to know what files exist.

    Args:
        path: Subdirectory to list (e.g. 'agent', 'tools'). Empty = root.

    Returns:
        List of file paths (strings).
    """
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    resp = requests.get(url, headers=_get_headers(), timeout=10)
    if resp.status_code != 200:
        logger.error(f"list_repo_files failed: {resp.text}")
        return []

    items = resp.json()
    if not isinstance(items, list):
        return []

    files = []
    for item in items:
        if item.get("type") == "file":
            files.append(item.get("path", ""))
        elif item.get("type") == "dir":
            files.append(item.get("path", "") + "/")
    return sorted(files)


def get_file_content(filepath: str) -> str | None:
    """
    Fetch the current content of a file from GitHub.
    Returns decoded string, or None if not found.
    """
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filepath}"
    resp = requests.get(url, headers=_get_headers(), timeout=10)
    if resp.status_code != 200:
        return None
    encoded = resp.json().get("content", "")
    try:
        return base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return None
