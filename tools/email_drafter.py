"""
tools/email_drafter.py
Auto-drafts Gmail replies in Steven's voice.

Polls unread inbox, classifies emails (DRAFT/FLAG/SKIP),
drafts replies using Claude with voice profile + response playbook,
creates threaded HTML drafts via GAS bridge.

MODULE not class. Flat functions imported at top of main.py.
"""

import json
import logging
import os
import re
import time
from datetime import datetime

from anthropic import Anthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Track processed message IDs to avoid re-drafting
_processed_message_ids: set[str] = set()
_seeded: bool = False

# Daily stats
_daily_stats: dict = {"date": "", "drafted": 0, "flagged": 0, "skipped": 0, "errors": 0}

# Gmail search query — same as prompts/reply_draft.md
_INBOX_QUERY = (
    "is:unread in:inbox "
    "-category:promotions -category:social "
    "-from:noreply -from:no-reply -from:notifications -from:mailer-daemon"
)

# Skip patterns — emails that never need replies
_SKIP_FROM_PATTERNS = [
    "noreply", "no-reply", "notifications", "mailer-daemon",
    "donotreply", "do-not-reply", "autonotify", "automated",
    "postmaster", "bounce", "support@outreach", "salesforce.com",
    "pandadoc.com", "dialpad.com", "fireflies.ai", "calendar-notification",
    "ionwave", "accounts@", "billing@",
]

_SKIP_SUBJECT_PATTERNS = [
    "automatic reply", "out of office", "auto-reply", "autoreply",
    "undeliverable", "delivery status", "mailer-daemon",
]


def _reset_daily_stats():
    """Reset stats at start of new day."""
    global _daily_stats
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_stats["date"] != today:
        _daily_stats = {"date": today, "drafted": 0, "flagged": 0, "skipped": 0, "errors": 0}


def _should_skip_fast(email: dict) -> bool:
    """Quick pre-filter before sending to Claude for classification."""
    from_addr = email.get("from", "").lower()
    subject = email.get("subject", "").lower()

    for pattern in _SKIP_FROM_PATTERNS:
        if pattern in from_addr:
            return True
    for pattern in _SKIP_SUBJECT_PATTERNS:
        if pattern in subject:
            return True
    return False


def _extract_sender_email(from_field: str) -> str:
    """Extract email address from 'Name <email>' format."""
    match = re.search(r'<([^>]+)>', from_field)
    if match:
        return match.group(1)
    # Maybe it's just an email address
    if "@" in from_field:
        return from_field.strip()
    return ""


def _extract_sender_name(from_field: str) -> str:
    """Extract display name from 'Name <email>' format."""
    match = re.match(r'^"?([^"<]+)"?\s*<', from_field)
    if match:
        return match.group(1).strip()
    return from_field.split("@")[0] if "@" in from_field else from_field


def _load_context_files() -> tuple[str, str]:
    """Load voice profile and response playbook from memory/ files."""
    voice_profile = ""
    playbook = ""

    # Try local files first (Claude Code), then GitHub (Railway)
    voice_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "voice_profile.md")
    playbook_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "response_playbook.md")

    try:
        with open(voice_path, "r") as f:
            voice_profile = f.read()
    except FileNotFoundError:
        logger.warning("voice_profile.md not found locally, will use GitHub")
        try:
            import tools.github_pusher as github_pusher
            voice_profile = github_pusher.get_file_content("memory/voice_profile.md") or ""
        except Exception as e:
            logger.error(f"Failed to load voice_profile.md: {e}")

    try:
        with open(playbook_path, "r") as f:
            playbook = f.read()
    except FileNotFoundError:
        logger.warning("response_playbook.md not found locally, will use GitHub")
        try:
            import tools.github_pusher as github_pusher
            playbook = github_pusher.get_file_content("memory/response_playbook.md") or ""
        except Exception as e:
            logger.error(f"Failed to load response_playbook.md: {e}")

    return voice_profile, playbook


def _classify_email(client: Anthropic, email: dict) -> str:
    """Classify email as DRAFT, FLAG, or SKIP using Claude Haiku."""
    from_addr = email.get("from", "")
    subject = email.get("subject", "")
    body = email.get("body", "")[:3000]  # Limit body size for classification
    labels = email.get("labels", [])

    prompt = f"""Classify this email into one of three categories:

DRAFT — Standard email Steven can reply to with product/sales knowledge.
Examples: pricing questions, scheduling, follow-ups, acknowledgments, product questions, budget constraints, free trial requests, partner inquiries.

FLAG — Needs specific info only Steven has, or requires a judgment call.
Examples: "What's your availability next week?", custom enterprise pricing, contract negotiations, complaints needing investigation, internal team questions.

SKIP — No reply needed or out of scope.
- Auto-replies, OOO responses
- Automated notifications (Outreach, Salesforce, PandaDoc, Dialpad, calendar)
- Newsletters, marketing, promotions
- CC-only threads where Steven isn't directly addressed
- Sales outreach or recruiting emails TO Steven
- Internal company-wide announcements
- Support ticket auto-responses
- Bid/procurement system notifications
- Emails already replied to
- Thread updates that are FYI only

Email:
From: {from_addr}
Subject: {subject}
Labels: {', '.join(labels) if labels else 'none'}
Body:
{body}

Respond with ONLY one word: DRAFT, FLAG, or SKIP"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text.strip().upper()
        if result in ("DRAFT", "FLAG", "SKIP"):
            return result
        return "SKIP"
    except Exception as e:
        logger.error(f"Classification failed for '{subject}': {e}")
        return "SKIP"


def _draft_reply(client: Anthropic, email: dict, voice_profile: str, playbook: str, is_flag: bool = False) -> str:
    """Draft a reply using Claude Sonnet with voice profile + playbook."""
    from_addr = email.get("from", "")
    sender_name = _extract_sender_name(from_addr)
    subject = email.get("subject", "")
    body = email.get("body", "")[:8000]

    flag_instruction = ""
    if is_flag:
        flag_instruction = (
            "\n\nThis email was classified as FLAG — it likely needs specific info only Steven has. "
            "Draft what you can and mark gaps inline with [STEVEN: insert specific info needed]. "
            "For example: [STEVEN: insert your availability next week] or [STEVEN: custom quote needed]."
        )

    prompt = f"""You are drafting an email reply AS Steven Adkins (steven@codecombat.com), CodeCombat Senior Partnership Manager.

VOICE PROFILE (follow these rules exactly — especially the Anti-AI-Tell Checklist):
{voice_profile}

RESPONSE PLAYBOOK (match to the closest category):
{playbook}

RULES:
- Body only — no subject line (Gmail handles Re:), no signature (auto-appended by Gmail)
- Start with greeting (usually "Hey {sender_name}," or "Hi {sender_name},")
- End naturally — Steven often just stops after the last point, no formal sign-off needed
- Match inbound energy: short incoming → short reply, casual → casual, formal → structured but warm
- NEVER use phrases from the Anti-AI-Tell Checklist
- NEVER fabricate product features or pricing you're not sure about
- Use HTML formatting: <br><br> between paragraphs, <b>bold</b> for emphasis, <ul><li> for lists
- Make links clickable: <a href="URL">text</a>
- Calendar link: https://codecombat.orumbriel.com/c/steven{flag_instruction}

EMAIL TO REPLY TO:
From: {from_addr}
Subject: {subject}
Body:
{body}

Write ONLY the reply body (HTML). No subject line, no signature, no explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Draft generation failed for '{subject}': {e}")
        return ""


def clear_processed_cache() -> int:
    """
    Force-clear the in-memory processed message ID set and re-enable seeding.
    Returns the count of IDs that were cleared.
    Used by /draft force to re-scan emails that were seeded-out or previously skipped.
    """
    global _processed_message_ids, _seeded
    count = len(_processed_message_ids)
    _processed_message_ids = set()
    _seeded = True  # keep seeded=True so process_new_emails doesn't re-seed on this call
    logger.info(f"[Email Drafter] Force-cleared processed cache ({count} IDs)")
    return count


def seed_processed_emails(gas) -> int:
    """
    On first run after startup, mark all existing unread emails as already-seen
    so Scout doesn't draft replies for the entire inbox.
    Returns count of seeded emails.
    """
    global _processed_message_ids, _seeded
    if _seeded:
        return 0

    try:
        data = gas.search_inbox_full(
            query=_INBOX_QUERY,
            max_results=50,
            body_limit=500,
        )
        results = data.get("results", [])
        for email in results:
            msg_id = email.get("message_id", "")
            if msg_id:
                _processed_message_ids.add(msg_id)
        _seeded = True
        logger.info(f"[Email Drafter] Seeded {len(results)} existing emails — watching for new ones.")
        return len(results)
    except Exception as e:
        logger.error(f"[Email Drafter] Seeding failed: {e}")
        _seeded = True  # Don't retry forever
        return 0


def process_new_emails(gas) -> dict:
    """
    Main entry point. Fetches unread inbox, classifies, drafts replies.
    Returns {drafted: [{to, subject, category, flag}], skipped: int, errors: int}
    """
    global _processed_message_ids
    _reset_daily_stats()

    if not _seeded:
        seed_processed_emails(gas)
        return {"drafted": [], "skipped": 0, "errors": 0, "message": "Seeded inbox — will draft on next cycle."}

    if not ANTHROPIC_API_KEY:
        return {"drafted": [], "skipped": 0, "errors": 1, "message": "ANTHROPIC_API_KEY not set"}

    client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=90.0)

    # Fetch unread emails
    try:
        data = gas.search_inbox_full(
            query=_INBOX_QUERY,
            max_results=20,
            body_limit=8000,
        )
        results = data.get("results", [])
    except Exception as e:
        logger.error(f"[Email Drafter] Inbox fetch failed: {e}")
        _daily_stats["errors"] += 1
        return {"drafted": [], "skipped": 0, "errors": 1, "message": f"Inbox fetch failed: {e}"}

    # Filter to only new emails
    new_emails = []
    for email in results:
        msg_id = email.get("message_id", "")
        if msg_id and msg_id not in _processed_message_ids:
            new_emails.append(email)

    if not new_emails:
        return {"drafted": [], "skipped": 0, "errors": 0, "message": "No new emails."}

    logger.info(f"[Email Drafter] Processing {len(new_emails)} new email(s)")

    # Load voice context
    voice_profile, playbook = _load_context_files()
    if not voice_profile:
        logger.warning("[Email Drafter] Voice profile empty — drafts may lack Steven's voice")

    drafted = []
    skipped = 0
    errors = 0

    for email in new_emails:
        msg_id = email.get("message_id", "")
        thread_id = email.get("thread_id", "")
        from_addr = email.get("from", "")
        subject = email.get("subject", "")
        sender_email = _extract_sender_email(from_addr)
        sender_name = _extract_sender_name(from_addr)

        # Mark as processed regardless of outcome
        if msg_id:
            _processed_message_ids.add(msg_id)

        # Fast pre-filter
        if _should_skip_fast(email):
            skipped += 1
            _daily_stats["skipped"] += 1
            logger.debug(f"[Email Drafter] SKIP (fast): {subject}")
            continue

        # Classify with Claude Haiku
        classification = _classify_email(client, email)

        if classification == "SKIP":
            skipped += 1
            _daily_stats["skipped"] += 1
            logger.debug(f"[Email Drafter] SKIP: {subject}")
            continue

        is_flag = classification == "FLAG"

        # Draft reply
        draft_body = _draft_reply(client, email, voice_profile, playbook, is_flag=is_flag)
        if not draft_body:
            errors += 1
            _daily_stats["errors"] += 1
            logger.error(f"[Email Drafter] Empty draft for: {subject}")
            continue

        # Validate sender email
        if not sender_email or "@" not in sender_email:
            errors += 1
            _daily_stats["errors"] += 1
            logger.error(f"[Email Drafter] Invalid sender email: {from_addr}")
            continue

        # Create threaded draft via GAS bridge (skip_if_draft_exists=True by default)
        try:
            result = gas.create_draft(
                to=sender_email,
                subject=f"Re: {subject}" if not subject.lower().startswith("re:") else subject,
                body=draft_body,
                thread_id=thread_id,
                content_type="text/html",
            )
            if result.get("success"):
                entry = {
                    "to": sender_email,
                    "name": sender_name,
                    "subject": subject,
                    "flag": is_flag,
                    "draft_id": result.get("draft_id", ""),
                }
                drafted.append(entry)
                if is_flag:
                    _daily_stats["flagged"] += 1
                else:
                    _daily_stats["drafted"] += 1
                logger.info(f"[Email Drafter] {'FLAG' if is_flag else 'DRAFT'}: {sender_name} — {subject}")
            elif result.get("already_drafted"):
                # Thread already has a draft — treat as skipped, not error
                skipped += 1
                _daily_stats["skipped"] += 1
                logger.info(f"[Email Drafter] SKIP (already drafted): {sender_name} — {subject}")
            else:
                errors += 1
                _daily_stats["errors"] += 1
                logger.error(f"[Email Drafter] GAS draft creation failed: {result}")
        except Exception as e:
            # Treat "already has a draft" errors as soft-skip, not error
            if "already has a draft" in str(e).lower() or "already_drafted" in str(e).lower():
                skipped += 1
                _daily_stats["skipped"] += 1
                logger.info(f"[Email Drafter] SKIP (already drafted, via exception path): {sender_name} — {subject}")
            else:
                errors += 1
                _daily_stats["errors"] += 1
                logger.error(f"[Email Drafter] Draft creation error for '{subject}': {e}")

    return {
        "drafted": drafted,
        "skipped": skipped,
        "errors": errors,
    }


def format_draft_summary(result: dict) -> str:
    """Format process_new_emails result for Telegram notification."""
    drafted = result.get("drafted", [])
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)
    message = result.get("message", "")

    if message and not drafted:
        return ""  # Don't notify for "no new emails" or seeding

    if not drafted and not errors:
        return ""  # Nothing to report

    lines = []
    if drafted:
        lines.append(f"✉️ **Auto-drafted {len(drafted)} repl{'y' if len(drafted) == 1 else 'ies'}:**")
        for i, d in enumerate(drafted, 1):
            flag_marker = " ⚠️ FLAG" if d.get("flag") else ""
            lines.append(f"{i}. {d['name']} — {d['subject'][:50]}{flag_marker}")
    if errors:
        lines.append(f"\n⚠️ {errors} error(s) — check logs")

    return "\n".join(lines)


def get_daily_summary() -> str:
    """Get daily stats for EOD report."""
    _reset_daily_stats()
    d = _daily_stats
    total = d["drafted"] + d["flagged"] + d["skipped"]
    if total == 0:
        return ""
    return (
        f"📧 **Email Drafting:** {d['drafted']} drafted, {d['flagged']} flagged, "
        f"{d['skipped']} skipped"
        + (f", {d['errors']} errors" if d["errors"] else "")
    )
