"""
memory_manager.py — Scout's persistent memory system.

Four memory layers:
  1. preferences.md     — How Steven works, corrections, approved formats. Never auto-cleared.
  2. context_summary.md — Compressed daily summaries of conversations. Grows over time.
  3. leads_log entries  — Handled by sheets_writer.py (Phase 2)
  4. Active injection   — Relevant memory loaded into every Claude API call

GitHub persistence: all writes commit back to the repo so memory survives
Railway restarts, redeploys, and container wipes.
"""

import base64
import logging
import re
from datetime import datetime
from pathlib import Path

import pytz
import requests

from agent import config

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent / "memory"
PREFERENCES_FILE = MEMORY_DIR / "preferences.md"
SUMMARY_FILE = MEMORY_DIR / "context_summary.md"

# How many lines of context_summary to inject (keeps token cost controlled)
SUMMARY_INJECT_LINES = 80


class MemoryManager:

    def __init__(self):
        MEMORY_DIR.mkdir(exist_ok=True)
        self._ensure_files_exist()
        self.github_token = config.GITHUB_TOKEN
        self.github_repo = config.GITHUB_REPO  # e.g. "scadkin/firstcocoagent"
        self.timezone = pytz.timezone(config.TIMEZONE)
        logger.info("[Memory] Memory manager initialized.")

    def _ensure_files_exist(self):
        """Create memory files if they don't exist yet."""
        if not PREFERENCES_FILE.exists():
            PREFERENCES_FILE.write_text(
                "# Scout Preferences & Learned Behavior\n"
                "# This file is written by Scout as it learns from Steven.\n"
                "# Do not delete. Clear specific entries manually if needed.\n\n",
                encoding="utf-8"
            )
        if not SUMMARY_FILE.exists():
            SUMMARY_FILE.write_text(
                "# Scout Context Summary Log\n"
                "# Daily compressed summaries of conversations and activity.\n"
                "# Oldest entries at top, newest at bottom.\n\n",
                encoding="utf-8"
            )

    # ─── LOAD ────────────────────────────────────────────────────────────────

    def load_preferences(self) -> str:
        """Return full preferences file content."""
        try:
            return PREFERENCES_FILE.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"[Memory] Failed to load preferences: {e}")
            return ""

    def load_recent_summary(self) -> str:
        """Return the most recent N lines of the context summary."""
        try:
            text = SUMMARY_FILE.read_text(encoding="utf-8")
            lines = text.splitlines()
            recent = lines[-SUMMARY_INJECT_LINES:] if len(lines) > SUMMARY_INJECT_LINES else lines
            return "\n".join(recent)
        except Exception as e:
            logger.error(f"[Memory] Failed to load summary: {e}")
            return ""

    def build_memory_context(self) -> str:
        """
        Build the memory block injected into every Claude API call.
        Loaded at the top of the system prompt so Scout always has context.
        """
        prefs = self.load_preferences().strip()
        summary = self.load_recent_summary().strip()

        parts = []
        if prefs:
            parts.append(f"## YOUR LEARNED PREFERENCES (from past interactions)\n{prefs}")
        if summary:
            parts.append(f"## RECENT HISTORY SUMMARY\n{summary}")

        if not parts:
            return ""

        return (
            "\n\n---\n## PERSISTENT MEMORY — READ THIS EVERY SESSION\n\n"
            + "\n\n".join(parts)
            + "\n\n---\n"
        )

    # ─── SAVE ────────────────────────────────────────────────────────────────

    def save_preference(self, entry: str):
        """
        Append a new learned preference or correction.
        Called when Claude detects [MEMORY_UPDATE: ...] in its response.
        """
        now = datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M")
        line = f"- [{now}] {entry.strip()}\n"

        try:
            with open(PREFERENCES_FILE, "a", encoding="utf-8") as f:
                f.write(line)
            logger.info(f"[Memory] Preference saved: {entry[:60]}")
            self._commit_to_github(
                "memory/preferences.md",
                PREFERENCES_FILE.read_text(encoding="utf-8"),
                f"Scout learned: {entry[:60]}"
            )
        except Exception as e:
            logger.error(f"[Memory] Failed to save preference: {e}")

    def append_to_summary(self, text: str):
        """
        Append a compressed summary block to context_summary.md.
        Called at end of day instead of clearing history.
        """
        now = datetime.now(self.timezone).strftime("%Y-%m-%d")
        block = f"\n### {now}\n{text.strip()}\n"

        try:
            with open(SUMMARY_FILE, "a", encoding="utf-8") as f:
                f.write(block)
            logger.info(f"[Memory] Summary appended for {now}.")
            self._commit_to_github(
                "memory/context_summary.md",
                SUMMARY_FILE.read_text(encoding="utf-8"),
                f"Scout daily summary — {now}"
            )
        except Exception as e:
            logger.error(f"[Memory] Failed to append summary: {e}")

    def clear_preferences(self):
        """Manual clear — only called when Steven explicitly requests it."""
        PREFERENCES_FILE.write_text(
            "# Scout Preferences & Learned Behavior\n"
            "# Cleared manually.\n\n",
            encoding="utf-8"
        )
        self._commit_to_github(
            "memory/preferences.md",
            PREFERENCES_FILE.read_text(encoding="utf-8"),
            "Scout preferences cleared by Steven"
        )
        logger.info("[Memory] Preferences cleared.")

    # ─── GITHUB PERSISTENCE ──────────────────────────────────────────────────

    def _commit_to_github(self, filepath: str, content: str, message: str):
        """
        Commit a file to the GitHub repo so memory survives Railway restarts.
        Uses the GitHub Contents API — no extra dependencies needed.
        """
        if not self.github_token or not self.github_repo:
            logger.warning("[Memory] GitHub token or repo not set — skipping commit.")
            return

        url = f"https://api.github.com/repos/{self.github_repo}/contents/{filepath}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Get current file SHA (required for updates)
        sha = None
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                sha = r.json().get("sha")
        except Exception as e:
            logger.warning(f"[Memory] Could not fetch file SHA: {e}")

        # Commit new content
        payload = {
            "message": f"[Scout] {message}",
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "committer": {"name": "Scout", "email": "scout@codecombat.com"}
        }
        if sha:
            payload["sha"] = sha

        try:
            r = requests.put(url, json=payload, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                logger.info(f"[Memory] Committed to GitHub: {filepath}")
            else:
                logger.error(f"[Memory] GitHub commit failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            logger.error(f"[Memory] GitHub commit error: {e}")

    # ─── CORRECTION DETECTION ────────────────────────────────────────────────

    @staticmethod
    def extract_memory_update(response: str) -> tuple[str, str | None]:
        """
        Looks for [MEMORY_UPDATE: ...] tag in Claude's response.
        Returns (clean_response, memory_entry_or_None).
        Claude appends this tag when it detects a correction or preference.
        """
        pattern = r'\[MEMORY_UPDATE:\s*(.+?)\]'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            entry = match.group(1).strip()
            clean = re.sub(pattern, '', response, flags=re.DOTALL).strip()
            return clean, entry
        return response, None
