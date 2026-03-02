"""
tools/fireflies.py
Fireflies.ai GraphQL API client for Scout.
Phase 5: Call Intelligence Suite

FirefliesClient fetches transcripts and recent call history.
Used by call_processor.py and the webhook flow in main.py.

Phase 5 fixes:
  - date → dateString
  - attendees { name email } → participants (flat name strings) + meeting_attendees (has emails)
  - speaker_name → speakerName
  - Internal meeting filter: skips calls where ALL attendee emails are @codecombat.com
  - Results sorted by dateString descending (most recent first)
"""

import logging
import requests

logger = logging.getLogger(__name__)

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"

# Any call where every attendee email matches one of these domains = internal, skip it
INTERNAL_DOMAINS = ["codecombat.com"]


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
        except requests.exceptions.Timeout:
            raise FirefliesError("Fireflies API timed out (>30s). Try again.")
        except requests.exceptions.RequestException as e:
            raise FirefliesError(f"Fireflies API request failed: {e}")

        if not r.ok:
            try:
                error_body = r.json()
                errors = error_body.get("errors", [])
                msg = errors[0].get("message") if errors else r.text[:400]
            except Exception:
                msg = r.text[:400]
            raise FirefliesError(f"Fireflies API {r.status_code} — {msg}")

        data = r.json()

        if "errors" in data:
            msg = data["errors"][0].get("message", str(data["errors"]))
            raise FirefliesError(f"Fireflies GraphQL error: {msg}")

        return data.get("data", {})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_internal(self, meeting_attendees: list) -> bool:
        """
        Returns True if every attendee with a known email is @codecombat.com.
        A call with even ONE external email is considered external (keep it).
        If no emails are available at all, assume external (keep it).
        """
        emails = [
            (a.get("email") or "").lower().strip()
            for a in (meeting_attendees or [])
            if a.get("email")
        ]

        if not emails:
            # No email data — can't determine, so keep it
            return False

        return all(
            any(domain in email for domain in INTERNAL_DOMAINS)
            for email in emails
        )

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
                dateString
                duration
                participants
                meeting_attendees {
                    displayName
                    email
                }
                sentences {
                    speakerName
                    text
                }
                summary {
                    overview
                    action_items
                }
            }
        }
        """

        data = self._query(query, variables={"id": transcript_id})
        t = data.get("transcript")
        if not t:
            raise FirefliesError(f"Transcript '{transcript_id}' not found or not yet ready.")

        # Flatten sentences into a single readable transcript string
        sentences = t.get("sentences") or []
        transcript_text = "\n".join(
            f"{s.get('speakerName', 'Speaker')}: {s.get('text', '')}"
            for s in sentences
            if s.get("text", "").strip()
        )

        summary = t.get("summary") or {}

        # Prefer meeting_attendees (has emails) — fall back to participants (names only)
        meeting_attendees = t.get("meeting_attendees") or []
        if meeting_attendees:
            attendees = [
                {
                    "name": a.get("displayName") or a.get("email", ""),
                    "email": a.get("email", ""),
                }
                for a in meeting_attendees
            ]
        else:
            attendees = [{"name": p, "email": ""} for p in (t.get("participants") or [])]

        return {
            "id": t.get("id", transcript_id),
            "title": t.get("title", ""),
            "date": t.get("dateString", ""),
            "duration": t.get("duration", 0),
            "attendees": attendees,
            "transcript": transcript_text,
            "summary": summary.get("overview", ""),
            "action_items": summary.get("action_items", ""),
        }

    def get_recent_transcripts(self, limit: int = 5, filter_internal: bool = True) -> list[dict]:
        """
        Fetch the most recent external call transcripts.

        limit:           How many results to return after filtering.
        filter_internal: If True, skips calls where every attendee email is @codecombat.com.
                         A call with even one external email is kept.

        Fetches 4x the requested limit first so filtering doesn't leave us short,
        then sorts by dateString descending (most recent first).
        """
        fetch_limit = limit * 4 if filter_internal else limit

        query = """
        query {
            transcripts(limit: %d) {
                id
                title
                dateString
                duration
                participants
                meeting_attendees {
                    displayName
                    email
                }
            }
        }
        """ % fetch_limit

        data = self._query(query)
        transcripts = data.get("transcripts") or []

        # Sort most recent first
        transcripts.sort(key=lambda t: t.get("dateString") or "", reverse=True)

        # Filter out internal-only calls
        if filter_internal:
            transcripts = [
                t for t in transcripts
                if not self._is_internal(t.get("meeting_attendees") or [])
            ]

        return transcripts[:limit]

    def format_recent_for_telegram(self, transcripts: list[dict]) -> str:
        """Format recent transcript list as a clean, readable Telegram message."""
        if not transcripts:
            return (
                "📞 No recent external calls found in Fireflies.\n\n"
                "If you expected results, make sure the Fireflies notetaker joined your Zoom calls."
            )

        lines = [f"📞 *Recent External Calls — {len(transcripts)} most recent*\n"]

        for i, t in enumerate(transcripts, 1):
            title = t.get("title") or "Untitled"
            transcript_id = t.get("id") or "?"
            date_str = (t.get("dateString") or "")[:10]
            duration_min = round((t.get("duration") or 0) / 60)

            # Prefer meeting_attendees emails, fall back to participants names
            meeting_attendees = t.get("meeting_attendees") or []
            if meeting_attendees:
                # Show external attendee names/emails only
                external = [
                    a.get("displayName") or a.get("email", "")
                    for a in meeting_attendees
                    if not any(d in (a.get("email") or "").lower() for d in INTERNAL_DOMAINS)
                ]
                people = ", ".join(external[:3]) if external else "External attendee"
            else:
                # Fall back to raw participant names
                names = [p for p in (t.get("participants") or []) if p and p.strip()][:3]
                people = ", ".join(names) if names else "No participants listed"

            lines.append(
                f"*{i}. {title}*\n"
                f"📅 {date_str}  🕐 {duration_min} min\n"
                f"👥 {people}\n"
                f"ID: `{transcript_id}`\n"
            )

        lines.append("To process a call: `/call [ID]`")
        return "\n".join(lines)


class FirefliesError(Exception):
    """Raised when Fireflies API returns an error or is unreachable."""
    pass
