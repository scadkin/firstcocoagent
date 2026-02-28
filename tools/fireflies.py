"""
tools/fireflies.py
Fireflies.ai GraphQL API client for Scout.
Phase 5: Call Intelligence Suite

FirefliesClient fetches transcripts and recent call history.
Used by call_processor.py and the webhook flow in main.py.
"""

import logging
import re
import requests

logger = logging.getLogger(__name__)

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


class FirefliesClient:
    """HTTP client for the Fireflies.ai GraphQL API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _query(self, query: str, variables: dict = None) -> dict:
        """
        Execute a GraphQL query against Fireflies.
        Returns data dict or raises FirefliesError.
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            r = self._session.post(FIREFLIES_API_URL, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.Timeout:
            raise FirefliesError("Fireflies API timed out (>30s). Try again.")
        except requests.exceptions.RequestException as e:
            raise FirefliesError(f"Fireflies API request failed: {e}")

        if "errors" in data:
            msg = data["errors"][0].get("message", str(data["errors"]))
            raise FirefliesError(f"Fireflies GraphQL error: {msg}")

        return data.get("data", {})

    # ── Public methods ────────────────────────────────────────────────────────

    def get_transcript(self, transcript_id: str) -> dict:
        """
        Fetch a single transcript by ID.
        Returns: {
            id, title, date, duration,
            attendees: [{name, email}],
            transcript: str   (speaker-labeled full text),
            summary: str,
            action_items: str,
            keywords: list[str],
        }
        """
        query = """
        query GetTranscript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                duration
                attendees {
                    name
                    email
                }
                sentences {
                    speaker_name
                    text
                }
                summary {
                    overview
                    action_items
                    keywords
                }
            }
        }
        """
        data = self._query(query, {"id": transcript_id})
        t = data.get("transcript")
        if not t:
            raise FirefliesError(f"Transcript '{transcript_id}' not found or not yet ready.")

        # Flatten sentences into a single readable transcript string
        sentences = t.get("sentences") or []
        transcript_text = "\n".join(
            f"{s.get('speaker_name', 'Speaker')}: {s.get('text', '')}"
            for s in sentences
            if s.get("text", "").strip()
        )

        summary = t.get("summary") or {}

        return {
            "id": t.get("id", transcript_id),
            "title": t.get("title", ""),
            "date": t.get("date", ""),
            "duration": t.get("duration", 0),
            "attendees": t.get("attendees") or [],
            "transcript": transcript_text,
            "summary": summary.get("overview", ""),
            "action_items": summary.get("action_items", ""),
            "keywords": summary.get("keywords") or [],
        }

    def get_recent_transcripts(self, limit: int = 5) -> list[dict]:
        """
        Fetch the most recent call transcripts.
        Returns list of {id, title, date, duration, attendees}.
        """
        query = """
        query GetRecent($limit: Int) {
            transcripts(limit: $limit) {
                id
                title
                date
                duration
                attendees {
                    name
                    email
                }
            }
        }
        """
        data = self._query(query, {"limit": limit})
        return data.get("transcripts") or []

    def format_recent_for_telegram(self, transcripts: list[dict]) -> str:
        """Format recent transcript list for a Telegram message."""
        if not transcripts:
            return "📞 No recent Fireflies transcripts found."

        lines = [f"📞 *Recent calls ({len(transcripts)}):*\n"]
        for t in transcripts:
            attendees = [a.get("name", a.get("email", "?")) for a in (t.get("attendees") or [])]
            attendee_str = ", ".join(attendees[:3]) or "unknown attendees"
            duration_min = round((t.get("duration") or 0) / 60)
            lines.append(
                f"• *{t.get('title', 'Untitled')}*\n"
                f"  `{t.get('id', '?')}`\n"
                f"  {t.get('date', '')[:10]} · {duration_min}min · {attendee_str}"
            )
        lines.append("\nUse `/call [id]` to process any of these.")
        return "\n".join(lines)


class FirefliesError(Exception):
    """Raised when Fireflies API returns an error or is unreachable."""
    pass
