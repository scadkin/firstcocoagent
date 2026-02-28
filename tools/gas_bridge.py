"""
tools/gas_bridge.py
Scout's Google connector — talks to the Google Apps Script Web App.
Replaces direct OAuth2 Google API calls with GAS bridge requests.

Single class handles: Gmail, Calendar, Slides — all routed through
the GAS web app running as steven@codecombat.com inside Google.

Phase 4.5: get_sent_emails now accepts page_start for pagination.
           Each email dict now includes is_reply (bool) and
           incoming_context (str) — bundled by GAS, no extra round-trips.
"""

import json
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class GASBridge:
    """
    HTTP client for the Scout Google Apps Script bridge.
    All requests are POST to the GAS web app URL with a secret token.
    """

    def __init__(self, webhook_url: str, secret_token: str):
        self.webhook_url = webhook_url
        self.secret_token = secret_token
        self._session = requests.Session()

    def _call(self, action: str, params: dict = None) -> dict:
        """
        Makes a POST request to the GAS bridge.
        Returns the parsed JSON response.
        Raises GASBridgeError on failure.
        """
        payload = {
            "token": self.secret_token,
            "action": action,
            "params": params or {},
        }

        try:
            response = self._session.post(
                self.webhook_url,
                json=payload,
                timeout=60,  # GAS can be slow on cold start
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            raise GASBridgeError(f"GAS bridge timed out on action '{action}'. It may be cold-starting — try again.")
        except requests.exceptions.RequestException as e:
            raise GASBridgeError(f"GAS bridge request failed: {e}")
        except json.JSONDecodeError:
            raise GASBridgeError(f"GAS bridge returned non-JSON: {response.text[:200]}")

        if not data.get("success"):
            error = data.get("error", "Unknown error from GAS bridge")
            if "Unauthorized" in error:
                raise GASBridgeError("GAS bridge auth failed. Check GAS_SECRET_TOKEN matches the token in Code.gs.")
            raise GASBridgeError(f"GAS bridge error on '{action}': {error}")

        return data

    # ── Health ────────────────────────────────────────────────────

    def ping(self) -> dict:
        """Tests connectivity to the GAS bridge. Returns user email if working."""
        return self._call("ping")

    # ── Gmail ─────────────────────────────────────────────────────

    def get_sent_emails(
        self,
        months_back: int = 6,
        max_results: int = 200,
        page_start: int = 0,
        page_size: int = 200,
    ) -> list[dict]:
        """
        Fetches Steven's sent emails for voice training.

        Phase 4.5 additions:
          - page_start: offset into the sent-mail search results (for pagination)
          - page_size:  how many threads to fetch this page (GAS caps at 200)
          - max_results is kept for backward compatibility but ignored when page_size is set

        Each returned dict has:
          subject, to, date, body,
          is_reply (bool)         — True if Steven was replying to someone
          incoming_context (str)  — the message Steven received (empty string for cold emails)

        Caller checks data["has_more"] to decide whether to fetch the next page.
        """
        data = self._call("get_sent_emails", {
            "months_back": months_back,
            "page_size":   page_size,
            "page_start":  page_start,
        })
        emails = data.get("emails", [])
        logger.info(
            f"GAS bridge returned {len(emails)} sent emails "
            f"(page_start={page_start}, has_more={data.get('has_more', False)})"
        )
        return emails
