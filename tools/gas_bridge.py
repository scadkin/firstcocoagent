"""
tools/gas_bridge.py
Scout's Google connector — talks to the Google Apps Script Web App.
Replaces direct OAuth2 Google API calls with GAS bridge requests.

Single class handles: Gmail, Calendar, Slides — all routed through
the GAS web app running as steven@codecombat.com inside Google.
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

    def get_sent_emails(self, months_back: int = 6, max_results: int = 200) -> list[dict]:
        """
        Fetches Steven's sent emails for voice training.
        Returns list of {subject, to, date, body} dicts.
        """
        data = self._call("get_sent_emails", {
            "months_back": months_back,
            "max_results": max_results,
        })
        emails = data.get("emails", [])
        logger.info(f"GAS bridge returned {len(emails)} sent emails")
        return emails

    def create_draft(self, to: str, subject: str, body: str) -> dict:
        """
        Creates a Gmail draft. Does NOT send.
        Returns {success, draft_id, to, subject, link}
        """
        result = self._call("create_draft", {
            "to": to,
            "subject": subject,
            "body": body,
        })
        logger.info(f"Draft created via GAS bridge | Subject: {subject} | To: {to}")
        return result

    def search_inbox(self, query: str, max_results: int = 10) -> list[dict]:
        """
        Searches Gmail inbox with a query string.
        Returns list of {subject, from, date, snippet} dicts.
        """
        data = self._call("search_inbox", {
            "query": query,
            "max_results": max_results,
        })
        return data.get("results", [])

    def get_draft_link(self) -> str:
        """Returns Gmail drafts folder URL."""
        return "https://mail.google.com/mail/u/0/#drafts"

    # ── Calendar ──────────────────────────────────────────────────

    def get_calendar_events(self, days_ahead: int = 7) -> list[dict]:
        """
        Gets upcoming calendar events.
        Returns list of {title, start, end, location, description, guests} dicts.
        """
        data = self._call("get_calendar_events", {
            "days_ahead": days_ahead,
        })
        events = data.get("events", [])
        logger.info(f"GAS bridge returned {len(events)} calendar events")
        return events

    def create_calendar_event(
        self,
        title: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
        guests: list[str] = None,
        location: str = "",
    ) -> dict:
        """
        Creates a calendar event.
        start_iso and end_iso should be ISO 8601 strings.
        Returns {success, event_id, title, start, link}
        """
        result = self._call("create_calendar_event", {
            "title": title,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "description": description,
            "guests": guests or [],
            "location": location,
        })
        logger.info(f"Calendar event created via GAS bridge: {title}")
        return result

    def log_call(
        self,
        contact_name: str,
        title: str,
        district: str,
        date_iso: str = None,
        duration_minutes: int = 30,
        notes: str = "",
        outcome: str = "",
        next_steps: str = "",
    ) -> dict:
        """
        Logs a sales call as a structured calendar event.
        Returns {success, event_id, title, link}
        """
        result = self._call("log_call", {
            "contact_name": contact_name,
            "title": title,
            "district": district,
            "date_iso": date_iso,
            "duration_minutes": duration_minutes,
            "notes": notes,
            "outcome": outcome,
            "next_steps": next_steps,
        })
        logger.info(f"Call logged via GAS bridge: {contact_name} @ {district}")
        return result

    # ── Slides ────────────────────────────────────────────────────

    def create_district_deck(
        self,
        district_name: str,
        state: str = "",
        contact_name: str = "",
        contact_title: str = "",
        student_count: str = "",
        key_pain_points: list[str] = None,
        products_to_highlight: list[str] = None,
        case_study: str = "",
    ) -> dict:
        """
        Creates a district pitch deck in Google Slides.
        Returns {success, presentation_id, url, title, slide_count}
        """
        result = self._call("create_district_deck", {
            "district_name": district_name,
            "state": state,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "student_count": student_count,
            "key_pain_points": key_pain_points or [],
            "products_to_highlight": products_to_highlight or ["CodeCombat Classroom", "AI HackStack"],
            "case_study": case_study,
        })
        logger.info(f"District deck created via GAS bridge: {district_name}")
        return result


class GASBridgeError(Exception):
    """Raised when the GAS bridge returns an error or is unreachable."""
    pass
