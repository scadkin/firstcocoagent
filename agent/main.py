"""
agent/main.py
Scout's entry point. Phase 6D: Daily Call List + all previous phases.
"""

import asyncio
from datetime import datetime
import logging
import os
import re
import time
import pytz
CST = pytz.timezone('America/Chicago')

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from agent.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, AGENT_NAME,
    GAS_WEBHOOK_URL, GAS_SECRET_TOKEN, gas_bridge_configured,
)
from agent.claude_brain import process_message, build_draft_prompt, draft_email_with_claude
from agent.memory_manager import MemoryManager
from agent.scheduler import Scheduler
from agent.voice_trainer import VoiceTrainer
from tools.research_engine import research_queue   # singleton queue from Phase 2
import tools.sheets_writer as sheets_writer
import tools.activity_tracker as activity_tracker
import tools.csv_importer as csv_importer
import tools.daily_call_list as daily_call_list
import tools.district_prospector as district_prospector
from tools.telegram_bot import send_message
# Phase 4/5 modules imported lazily inside execute_tool() — safe to boot without them

# Phase 5 vars read from env directly (no config.py change needed)
FIREFLIES_API_KEY = os.environ.get("FIREFLIES_API_KEY", "")
FIREFLIES_WEBHOOK_SECRET = os.environ.get("FIREFLIES_WEBHOOK_SECRET", "")
PRECALL_BRIEF_FOLDER_ID = os.environ.get("PRECALL_BRIEF_FOLDER_ID", "")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Global state ──────────────────────────────────────────────────────────────

memory = MemoryManager()
conversation_history = []

# Pending draft — stores last unconfirmed draft
_pending_draft = None

# Phase 5: Track which calendar event IDs have had pre-call briefs sent
_precall_briefs_sent: set = set()

# Phase 5+: Fireflies Gmail polling dedup
_fireflies_email_triggers: set = set()   # keyed by "subject[:60]|date[:16]"
_fireflies_processed_ids: set = set()    # keyed by transcript_id
_fireflies_gmail_seeded: bool = False    # True after first scan seeds existing emails

# Phase 6E: Prospecting queue — last shown batch for approve/skip indexing
_last_prospect_batch: list[dict] = []


def get_gas_bridge():
    """Lazy-init GAS bridge. Returns None if not configured."""
    if not gas_bridge_configured():
        return None
    from tools.gas_bridge import GASBridge
    return GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)


def get_voice_trainer():
    """Lazy-init voice trainer. Returns None if GAS not configured."""
    gas = get_gas_bridge()
    if not gas:
        return None
    return VoiceTrainer(gas_bridge=gas, memory_manager=memory)


def _parse_guests(raw_guests: list) -> list:
    """
    GAS bridge returns guests as either plain email strings OR dicts with {name, email}.
    This helper normalises both formats into [{name, email}] dicts.
    Filters out @codecombat.com addresses.
    """
    attendees = []
    for g in (raw_guests or []):
        if isinstance(g, dict):
            email = g.get("email", "")
            name = g.get("name", "") or email.split("@")[0]
        else:
            # Plain email string
            email = str(g)
            name = email.split("@")[0]
        if email and "@codecombat.com" not in email.lower():
            attendees.append({"email": email, "name": name})
    return attendees


# ── Research callbacks ────────────────────────────────────────────────────────

async def _on_research_progress(message: str):
    await send_message(message)


async def _on_research_complete(result: dict):
    try:
        contacts = result.get("contacts", [])
        write_summary = sheets_writer.write_contacts(contacts, state=result.get("state", ""))
        with_email = result.get("with_email", 0)
        no_email = result.get("no_email", 0)
        total = result.get("total", 0)
        verified = result.get("verified", 0)
        district = result.get("district_name", "")
        state = result.get("state", "")
        elapsed = result.get("elapsed_seconds", 0)
        queries_used = result.get("queries_used", 0)
        layer_counts = result.get("layer_contact_counts", {})
        leads_added = write_summary.get("leads_added", 0)
        no_email_added = write_summary.get("no_email_added", 0)
        dupes_skipped = write_summary.get("duplicates_skipped", 0)
        sheet_url = f"https://docs.google.com/spreadsheets/d/{os.environ.get('GOOGLE_SHEETS_ID', '')}"

        # Format elapsed time
        mins, secs = divmod(elapsed, 60)
        elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

        # Format layer breakdown (only layers that found contacts)
        layer_lines = []
        layer_order = [
            "L1:direct-title", "L2:title-variations", "L3:linkedin",
            "L4:district-site", "L5:news-grants", "L6:scrape", "L7:deep-crawl",
            "L11:school-staff", "L12:board-agendas", "L13:state-doe", "L14:conference",
            "L15:email-verify",
        ]
        for layer in layer_order:
            count = layer_counts.get(layer, 0)
            layer_lines.append(f"  {layer}: {count}")
        # Include any layers not in the order list
        for layer, count in layer_counts.items():
            if layer not in layer_order:
                layer_lines.append(f"  {layer}: {count}")

        msg = (
            f"✅ *Research complete: {district}*\n\n"
            f"⏱ Time: {elapsed_str} | 🔍 Serper queries: {queries_used}\n"
            f"📊 Found: {total} total — {with_email} with email, {no_email} name-only\n"
            f"✅ Verified emails: {verified} | 🆕 New to sheet: {leads_added + no_email_added} | ♻️ Dupes skipped: {dupes_skipped}\n\n"
            f"*Layer breakdown (contacts found per strategy):*\n"
            + "\n".join(layer_lines)
            + f"\n\n[View sheet]({sheet_url})"
        )

        # Cap-hit reporting
        if result.get("cap_hit"):
            skipped = result.get("skipped_layers", [])
            skipped_str = ", ".join(skipped) if skipped else "some layers"
            msg += (
                f"\n\n⚠️ *Hit the {queries_used}-query safety limit.* Layers skipped: _{skipped_str}_\n"
                f"There are likely more leads — say *\"keep digging on {district}\"* to continue."
            )

        await send_message(msg)

        # Log to Research Log tab
        try:
            layer_notes = " | ".join(f"{k}:{v}" for k, v in layer_counts.items() if v > 0)
            notes = f"{elapsed_str} | {queries_used} queries | {layer_notes}"
            sheets_writer.log_research_job(
                district=district,
                state=state,
                layers_used=result.get("layers_used", ""),
                total_found=total,
                with_email=with_email,
                no_email=no_email,
                notes=notes,
            )
        except Exception as log_err:
            logger.error(f"Research log write failed: {log_err}")

        # Phase 6C: log to Activities tab
        try:
            activity_tracker.log_activity(
                activity_type="research_job",
                district=district,
                contact="",
                notes=f"{total} contacts found ({with_email} with email) | {elapsed_str}",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log failed: {act_err}")

    except Exception as e:
        logger.error(f"Research completion handler failed: {e}")
        await send_message(f"❌ Research finished but sheet write failed: {e}")


# ── Tool execution ─────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict) -> str:
    global _pending_draft

    if tool_name == "research_district":
        district = tool_input.get("district_name", "")
        state = tool_input.get("state", "")
        if not district:
            return "❌ No district name provided."
        await send_message(f"🔍 Starting research on *{district}*{' (' + state + ')' if state else ''}...")
        await research_queue.enqueue(
            district_name=district,
            state=state,
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
        )
        return f"📋 Research queued for *{district}*. Full 15-layer run typically takes 5–10 minutes. I'll ping you every minute so you know it's still working."

    elif tool_name == "research_batch":
        targets = tool_input.get("targets", [])
        if not targets:
            return "❌ No targets provided."
        names = [t.get("district_name", "?") for t in targets]
        await send_message(f"📋 Queuing batch research for {len(targets)} districts: {', '.join(names)}")
        await research_queue.enqueue_batch(
            targets=targets,
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
        )
        return f"✅ {len(targets)} research jobs queued. I'll send updates as each completes."

    elif tool_name == "get_sheet_status":
        try:
            counts = sheets_writer.count_leads()
            sheet_url = sheets_writer.get_master_sheet_url()
            return (
                f"📊 *Sheet status:*\n"
                f"✅ {counts['leads']} contacts with emails\n"
                f"📋 {counts['no_email']} name-only (no email)\n"
                f"📈 {counts['total']} total\n"
                f"[Open sheet]({sheet_url})"
            )
        except Exception as e:
            return f"❌ Could not read sheet: {e}"

    elif tool_name == "get_research_queue_status":
        current = research_queue.current_job
        depth = research_queue.queue_size
        if not current:
            return "✅ No research running. Queue empty."
        return f"🔍 Currently researching: *{current}*\nJobs queued: {depth}"

    elif tool_name == "ping_gas_bridge":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured. Set `GAS_WEBHOOK_URL` and `GAS_SECRET_TOKEN` in Railway."
        try:
            result = gas.ping()
            return f"✅ *GAS Bridge connected!*\nRunning as: `{result.get('user', 'unknown')}`"
        except Exception as e:
            return f"❌ GAS bridge ping failed: {e}"

    elif tool_name == "train_voice":
        trainer = get_voice_trainer()
        if not trainer:
            return "❌ GAS bridge not configured yet. Follow `docs/SETUP_PHASE3.md` first."
        months_back = tool_input.get("months_back", 24)
        await send_message(
            "🔄 *Starting voice training...*\n"
            f"Fetching up to 2,000 sent emails from the last {months_back} months. "
            "This takes 3–5 minutes — I'll send updates as I go."
        )
        def on_progress(msg):
            asyncio.create_task(send_message(msg))
        try:
            profile = trainer.train(months_back=months_back, progress_callback=on_progress)
            if profile.startswith("❌"):
                return profile
            return (
                "✅ *Voice profile built!*\n\n"
                "I've analyzed your sent emails and learned your writing style. "
                "Every draft from now on will sound like you.\n\n"
                "Try: `Draft a cold email to the CS Director at Austin ISD`"
            )
        except Exception as e:
            logger.error(f"Voice training error: {e}")
            return f"❌ Voice training failed: {e}"

    elif tool_name == "draft_email":
        trainer = get_voice_trainer()
        voice_profile = trainer.load_profile() if trainer else None
        recipient_name = tool_input.get("recipient_name", "")
        recipient_title = tool_input.get("recipient_title", "")
        district = tool_input.get("district", "")
        state = tool_input.get("state", "")
        email_type = tool_input.get("email_type", "cold outreach")
        additional_context = tool_input.get("additional_context", "")
        await send_message(f"✍️ Drafting {email_type} email for *{recipient_title or 'contact'}* at *{district}*...")
        prompt = build_draft_prompt(
            voice_profile=voice_profile,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            district=district,
            state=state,
            email_type=email_type,
            additional_context=additional_context,
        )
        draft_text = draft_email_with_claude(prompt)
        if draft_text.startswith("❌"):
            return draft_text
        subject, body = _parse_draft(draft_text)
        _pending_draft = {"to": "", "subject": subject, "body": body, "raw": draft_text}

        # Phase 6C: log email draft
        try:
            activity_tracker.log_activity(
                activity_type="email_drafted",
                district=district,
                contact=f"{recipient_name} ({recipient_title})" if recipient_name else recipient_title,
                notes=f"Type: {email_type} | Subject: {subject}",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log (draft_email) failed: {act_err}")

        return (
            f"📧 *Draft ready:*\n\n"
            f"{draft_text}\n\n"
            "---\n"
            "• *looks good* → save to Gmail Drafts\n"
            "• *edit: [what to change]* → I'll revise\n"
            "• *add email: name@district.org* → set recipient"
        )

    elif tool_name == "save_draft_to_gmail":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        to = tool_input.get("to", "") or (_pending_draft or {}).get("to", "")
        subject = tool_input.get("subject", "") or (_pending_draft or {}).get("subject", "")
        body = tool_input.get("body", "") or (_pending_draft or {}).get("body", "")
        if not subject or not body:
            return "❌ No draft to save. Draft an email first."
        try:
            result = gas.create_draft(to=to, subject=subject, body=body)
            _pending_draft = None

            # Phase 6C: log email saved
            try:
                activity_tracker.log_activity(
                    activity_type="email_saved",
                    district="",
                    contact=to,
                    notes=f"Subject: {subject}",
                    source="scout",
                )
            except Exception as act_err:
                logger.error(f"Activity log (email_saved) failed: {act_err}")

            return (
                f"✅ *Saved to Gmail Drafts!*\n"
                f"Subject: _{subject}_\n"
                f"[Open Gmail Drafts]({result.get('link', 'https://mail.google.com/mail/u/0/#drafts')})"
            )
        except Exception as e:
            return f"❌ Could not save draft: {e}"

    elif tool_name == "get_calendar":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        days_ahead = tool_input.get("days_ahead", 7)
        try:
            events = gas.get_calendar_events(days_ahead=days_ahead)
            if not events:
                return f"📅 No events in the next {days_ahead} days."
            lines = [f"📅 *Next {days_ahead} days ({len(events)} events):*\n"]
            for ev in events:
                lines.append(f"• *{ev.get('title', '?')}*")
                lines.append(f"  {ev.get('start', '')}")
                if ev.get("location"):
                    lines.append(f"  📍 {ev['location']}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Could not fetch calendar: {e}"

    elif tool_name == "log_call":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        try:
            result = gas.log_call(
                contact_name=tool_input.get("contact_name", ""),
                title=tool_input.get("title", ""),
                district=tool_input.get("district", ""),
                date_iso=tool_input.get("date_iso"),
                duration_minutes=tool_input.get("duration_minutes", 30),
                notes=tool_input.get("notes", ""),
                outcome=tool_input.get("outcome", ""),
                next_steps=tool_input.get("next_steps", ""),
            )

            # Phase 6C: log call activity
            try:
                activity_tracker.log_activity(
                    activity_type="call_logged",
                    district=tool_input.get("district", ""),
                    contact=tool_input.get("contact_name", ""),
                    notes=f"Outcome: {tool_input.get('outcome', '')} | {tool_input.get('notes', '')}",
                    source="scout",
                )
            except Exception as act_err:
                logger.error(f"Activity log (log_call) failed: {act_err}")

            return (
                f"✅ *Call logged!*\n"
                f"_{result.get('title', 'Call')}_\n"
                f"[View in Calendar]({result.get('link', 'https://calendar.google.com/calendar/r')})"
            )
        except Exception as e:
            return f"❌ Could not log call: {e}"

    elif tool_name == "create_district_deck":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        district = tool_input.get("district_name", "")
        await send_message(f"📊 Building pitch deck for *{district}*...")
        try:
            result = gas.create_district_deck(
                district_name=district,
                state=tool_input.get("state", ""),
                contact_name=tool_input.get("contact_name", ""),
                contact_title=tool_input.get("contact_title", ""),
                key_pain_points=tool_input.get("key_pain_points", []),
                products_to_highlight=tool_input.get("products_to_highlight", []),
                case_study=tool_input.get("case_study", ""),
            )
            return (
                f"✅ *Pitch deck created!*\n"
                f"_{result.get('title', district)}_ — {result.get('slide_count', '?')} slides\n"
                f"[Open in Google Slides]({result.get('url', '')})"
            )
        except Exception as e:
            return f"❌ Could not create deck: {e}"

    elif tool_name == "push_code":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "❌ `tools/github_pusher.py` not found in repo."
        filepath = tool_input.get("filepath", "").strip()
        content = tool_input.get("content", "")
        commit_msg = tool_input.get("commit_message", "")
        if not filepath or not content:
            return "❌ Need both `filepath` and `content` to push."
        await send_message(f"📤 Pushing `{filepath}` to GitHub...")
        result = github_pusher.push_file(
            filepath=filepath,
            content=content,
            commit_message=commit_msg or f"Scout: update {filepath}",
        )
        if result["success"]:
            url = result.get("url", "")
            link = f"\n[View on GitHub]({url})" if url else ""
            return f"{result['message']}{link}\n\n⚡️ Railway will auto-deploy in ~30 seconds."
        else:
            return result["message"]

    elif tool_name == "list_repo_files":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "❌ `tools/github_pusher.py` not found in repo."
        path = tool_input.get("path", "")
        files = github_pusher.list_repo_files(path)
        if not files:
            return f"❌ Could not list files in `{path or 'repo root'}`."
        label = f"`{path}/`" if path else "repo root"
        lines = [f"📁 *Files in {label}:*\n"] + [f"• `{f}`" for f in files]
        return "\n".join(lines)

    elif tool_name == "get_file_content":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "github_pusher.py not found — upload tools/github_pusher.py to GitHub first."
        filepath = tool_input.get("filepath", "").strip()
        if not filepath:
            return "Need a filepath. Example: agent/main.py"
        content_str = github_pusher.get_file_content(filepath)
        if content_str is None:
            return f"Could not fetch {filepath} — use list_repo_files to check available paths."
        line_count = len(content_str.splitlines())
        char_count = len(content_str)
        return (
            f"FILE: {filepath} | {line_count} lines, {char_count} chars"
            f"\n\n```\n{content_str}\n```"
        )

    elif tool_name == "build_sequence":
        try:
            import tools.sequence_builder as sequence_builder
        except ImportError:
            return "❌ `tools/sequence_builder.py` not found in repo."
        campaign_name = tool_input.get("campaign_name", "")
        target_role = tool_input.get("target_role", "")
        focus_product = tool_input.get("focus_product", "CodeCombat AI Suite")
        num_steps = int(tool_input.get("num_steps", 5))
        additional_context = tool_input.get("additional_context", "")
        if not campaign_name or not target_role:
            return "❌ Need at least `campaign_name` and `target_role` to build a sequence."
        await send_message(
            f"✍️ Building {num_steps}-step sequence for *{target_role}*...\n"
            f"Campaign: _{campaign_name}_"
        )
        voice_profile = None
        try:
            with open("memory/voice_profile.md", "r", encoding="utf-8") as f:
                voice_profile = f.read()
        except FileNotFoundError:
            pass
        result = sequence_builder.build_sequence(
            campaign_name=campaign_name,
            target_role=target_role,
            focus_product=focus_product,
            num_steps=num_steps,
            voice_profile=voice_profile,
            additional_context=additional_context,
        )
        if not result["success"]:
            return f"❌ Sequence generation failed: {result['error']}"
        steps = result["steps"]
        tg_text = sequence_builder.format_for_telegram(campaign_name, steps)
        # Write to Google Doc via GAS bridge
        gas = get_gas_bridge()
        doc_result = sequence_builder.write_sequence_to_doc(campaign_name, steps, gas)
        if doc_result["success"] and doc_result["url"]:
            full_output = f"📄 [Full sequence — {campaign_name}]({doc_result['url']})\n\n{tg_text}"
        else:
            raw_error = doc_result.get("error", "unknown error")
            logger.error(f"Sequence doc creation failed: {raw_error}")
            full_output = f"{tg_text}\n\n⚠️ Doc creation failed: `{raw_error}`\n📋 Copy steps into Outreach.io manually."
        # Send directly to Telegram — bypasses Claude so it can't rewrite the output
        await send_message(full_output)

        # Phase 6C: log sequence built
        try:
            activity_tracker.log_activity(
                activity_type="sequence_built",
                district="",
                contact=target_role,
                notes=f"Campaign: {campaign_name} | {num_steps} steps",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log (sequence_built) failed: {act_err}")

        return "✅ Sequence built and sent above."

    elif tool_name == "process_call_transcript":
        try:
            from tools.fireflies import FirefliesClient
            from agent.call_processor import CallProcessor
        except ImportError as e:
            return f"Phase 5 module not found: {e}"
        transcript_id = tool_input.get("transcript_id", "").strip()
        if not transcript_id:
            return "Need a transcript ID. Use /recent_calls to find one."
        gas = get_gas_bridge()
        if not gas:
            return "GAS bridge not configured."
        if not FIREFLIES_API_KEY:
            return "FIREFLIES_API_KEY not set in Railway."
        fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=fireflies)
        except Exception as e:
            return f"❌ Could not initialize call processor: {e}"
        await send_message(f"📞 Processing transcript `{transcript_id}`... This takes 30-60 seconds.")
        async def on_progress(msg):
            await send_message(msg)
        email_override = tool_input.get("email_override", "").strip()
        result = await processor.process_transcript(transcript_id=transcript_id, progress_callback=on_progress, email_override=email_override)
        if result.get("error"):
            return "Processing failed: " + result["error"]
        await send_message(result["telegram_summary"])
        await send_message(result["salesforce_block"])
        return ""

    elif tool_name == "get_pre_call_brief":
        try:
            from agent.call_processor import CallProcessor
        except ImportError as e:
            return f"agent/call_processor.py not found: {e}"
        gas = get_gas_bridge()
        if not gas:
            return "GAS bridge not configured."
        meeting_title = tool_input.get("meeting_title", "")
        attendee_emails = tool_input.get("attendee_emails", [])
        try:
            events = gas.get_calendar_events(days_ahead=14)
        except Exception as e:
            return f"❌ Could not fetch calendar: {e}"
        target_event = None
        if meeting_title:
            for ev in events:
                if meeting_title.lower() in ev.get("title", "").lower():
                    target_event = ev
                    break
        else:
            for ev in events:
                loc = (ev.get("location") or "") + (ev.get("description") or "")
                if "zoom.us" in loc.lower():
                    target_event = ev
                    break
        if not target_event and not attendee_emails:
            titles = ", ".join("'" + e.get("title","?") + "'" for e in events[:5]) if events else "none"
            return f"Could not find a Zoom meeting. Upcoming events: {titles}"
        if attendee_emails:
            attendees = [{"email": e, "name": e.split("@")[0]} for e in attendee_emails]
        else:
            raw_guests = (target_event or {}).get("guests", [])
            attendees = _parse_guests(raw_guests)
            if not attendees:
                attendees = [{"name": "Prospect", "email": ""}]
        mtitle = (target_event or {}).get("title", meeting_title or "your meeting")
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory)
        except Exception as e:
            return f"❌ Could not initialize call processor: {e}"
        async def on_brief_progress(msg):
            await send_message(msg)
        brief = await processor.build_pre_call_brief(
            event=target_event or {"title": meeting_title, "start": ""},
            attendees=attendees,
            progress_callback=on_brief_progress,
        )
        await send_message(brief)
        return ""

    # ── Phase 6C tools ────────────────────────────────────────────────────────

    elif tool_name == "get_activity_summary":
        try:
            date_str = tool_input.get("date", None)
            progress = activity_tracker.get_daily_progress(date_str=date_str)
            return progress.get("progress_text", "No activity data available.")
        except Exception as e:
            return f"❌ Could not load activity data: {e}"

    elif tool_name == "get_accounts_status":
        try:
            return csv_importer.get_import_summary()
        except Exception as e:
            return f"❌ Could not read Active Accounts tab: {e}"

    elif tool_name == "set_goal":
        goal_type = tool_input.get("goal_type", "")
        daily_target = tool_input.get("daily_target", 0)
        description = tool_input.get("description", "")
        if not goal_type or not daily_target:
            return "❌ Need goal_type and daily_target."
        try:
            activity_tracker.set_goal(goal_type, int(daily_target), description)
            return f"✅ Goal updated: *{goal_type}* = {daily_target}/day"
        except Exception as e:
            return f"❌ Could not update goal: {e}"

    elif tool_name == "sync_gmail_activities":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        try:
            await send_message("🔄 Scanning Gmail for PandaDoc and Dialpad events...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, activity_tracker.sync_gmail_activities, gas)
            pd = result.get("pandadoc_logged", 0)
            dd = result.get("dialpad_logged", 0)
            seen = result.get("already_seen", 0)
            return (
                f"✅ *Gmail scan complete*\n"
                f"📄 PandaDoc events logged: {pd}\n"
                f"📞 Dialpad calls logged: {dd}\n"
                f"♻️ Already seen (skipped): {seen}"
            )
        except Exception as e:
            return f"❌ Gmail sync failed: {e}"

    # ── Phase 6D: Daily Call List ────────────────────────────────────────────

    elif tool_name == "generate_call_list":
        max_contacts = int(tool_input.get("max_contacts", 10))
        await send_message("Building your daily call list...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, daily_call_list.build_daily_call_list, max_contacts
            )
            if not result["success"]:
                return f"Could not build call list: {result['error']}"
            cards = result["cards"]
            if not cards:
                return "No contacts matched your active accounts. Research more districts or upload a fresh Salesforce CSV."
            doc_url = ""
            gas = get_gas_bridge()
            if gas:
                doc_result = await loop.run_in_executor(
                    None, daily_call_list.write_call_list_to_doc, cards, gas
                )
                doc_url = doc_result.get("url", "")
            tg_text = daily_call_list.format_for_telegram(cards, doc_url=doc_url)
            await send_message(tg_text)
            try:
                activity_tracker.log_activity(
                    "call_list_generated",
                    notes=f"{len(cards)} contacts from {result.get('district_count', 0)} districts",
                )
            except Exception:
                pass
            return "Daily call list built and sent above."
        except Exception as e:
            return f"Call list failed: {e}"

    return f"❓ Unknown tool: {tool_name}"


# ── CSV file upload handler ────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CSV file uploads from Steven. Triggers Salesforce active accounts import."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return

    doc = update.message.document
    if not doc:
        return

    filename = doc.file_name or ""
    mime = doc.mime_type or ""

    # Only handle CSV files
    if not (filename.lower().endswith(".csv") or "csv" in mime.lower() or "text" in mime.lower()):
        await send_message(
            "📎 Got a file, but I can only process `.csv` files right now.\n"
            "Export from Salesforce as CSV and send that file."
        )
        return

    await send_message(f"📥 Got `{filename}` — importing Salesforce accounts...")

    try:
        tg_file = await doc.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        csv_text = file_bytes.decode("utf-8-sig")  # utf-8-sig handles BOM from Excel/Salesforce exports
    except Exception as e:
        await send_message(f"❌ Could not download file: {e}")
        return

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, csv_importer.import_accounts, csv_text)
    except Exception as e:
        await send_message(f"❌ Import failed: {e}")
        return

    imported  = result.get("imported", 0)
    districts = result.get("districts", 0)
    schools   = result.get("schools", 0)
    libraries = result.get("libraries", 0)
    companies = result.get("companies", 0)
    skipped   = result.get("skipped", 0)
    errors    = result.get("errors", [])
    sheet_url = sheets_writer.get_master_sheet_url()

    breakdown = f"  • {districts} districts\n  • {schools} schools\n"
    if libraries:
        breakdown += f"  • {libraries} libraries\n"
    if companies:
        breakdown += f"  • {companies} other (companies/orgs)\n"

    msg = (
        f"✅ *Salesforce import complete!*\n\n"
        f"📊 {imported} accounts imported\n"
        f"{breakdown}"
    )
    if skipped:
        msg += f"⚠️ {skipped} rows skipped (blank account name)\n"
    if errors:
        msg += f"❌ Errors: {'; '.join(errors[:3])}\n"
    msg += f"\n[View Active Accounts tab]({sheet_url})"

    # Log the import as an activity
    try:
        activity_tracker.log_activity(
            activity_type="research_job",
            district="Salesforce Import",
            contact="",
            notes=f"Imported {imported} accounts ({districts} districts, {schools} schools) from {filename}",
            source="manual",
        )
    except Exception:
        pass

    await send_message(msg)


# ── Draft parsing ──────────────────────────────────────────────────────────────

def _parse_draft(draft_text: str) -> tuple:
    subject = ""
    body = draft_text
    match = re.search(r"\*{0,2}Subject:\*{0,2}\s*(.+)", draft_text, re.IGNORECASE)
    if match:
        subject = match.group(1).strip()
        body = draft_text[match.end():].strip()
    return subject, body


# ── Telegram message handler ───────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global conversation_history, _pending_draft

    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return

    user_text = update.message.text.strip()
    logger.info(f"Received: {user_text}")

    _ack_sent = False

    # ── Command routing ────────────────────────────────────────────────────────

    if user_text.lower() in ["/ping_gas", "/test_google", "test gas", "ping gas"]:
        user_text = "ping the GAS bridge"

    elif user_text.lower() in ["/train_voice", "train voice", "train my voice", "learn my style"]:
        user_text = "train your voice model from my Gmail history"

    elif user_text.lower() in ["/list_files", "/ls", "list files", "show repo files"]:
        user_text = "list all files in the repo root"

    elif user_text.lower().startswith("/push_code"):
        args = user_text[len("/push_code"):].strip()
        if args:
            await send_message(f"On it — fetching `{args}` from GitHub now...")
            _ack_sent = True
            user_text = (
                f"PUSH_CODE WORKFLOW for '{args}':\n"
                f"Step 1: Call the get_file_content tool immediately to fetch '{args}' from GitHub. Do NOT skip this.\n"
                f"Step 2: Once you have the file, write a 2-3 sentence summary of what it does.\n"
                f"Step 3: Ask Steven exactly this: 'What changes would you like me to make?'\n"
                f"Step 4: Wait for Steven's answer, then make those specific changes to the fetched content and push with push_code.\n"
                f"Do not deviate from these steps."
            )
        else:
            user_text = "Ask Steven which file he wants to update. Once he answers, immediately call get_file_content to fetch it, summarize it, then ask what changes he wants."

    elif user_text.lower() in ["/grade_draft", "grade draft", "grade that draft", "rate that draft"]:
        user_text = (
            "I want to give you feedback on the last email draft you wrote. "
            "Ask me to rate it 1-5 and describe specifically what was off — "
            "tone, length, word choice, CTA, anything. "
            "Then update my voice profile permanently with what you learn."
        )

    elif user_text.lower().startswith("/add_template"):
        args = user_text[len("/add_template"):].strip()
        user_text = (
            f"I'm going to give you one of my actual email templates or snippets that I use regularly. "
            f"{'Here it is: ' + args if args else 'Ask me to paste it.'} "
            f"Analyze the writing style, structure, and tone. "
            f"Then permanently add it to my voice profile under a Templates section so you can reference it when drafting."
        )

    elif re.match(r"^(keep digging|dig deeper|keep searching|go deeper)\s+(on\s+)?(.+)", user_text, re.IGNORECASE):
        m = re.match(r"^(keep digging|dig deeper|keep searching|go deeper)\s+(on\s+)?(.+)", user_text, re.IGNORECASE)
        district = m.group(3).strip().rstrip(".")
        await send_message(f"🔍 Continuing deep search on *{district}* with extended query budget...")
        await research_queue.enqueue(
            district_name=district,
            state="",
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
            serper_cap_override=200,
        )
        return

    elif user_text.lower().startswith("/build_sequence") or user_text.lower().startswith("/sequence"):
        args = ""
        for prefix in ["/build_sequence", "/sequence"]:
            if user_text.lower().startswith(prefix):
                args = user_text[len(prefix):].strip()
                break
        campaign_hint = f" for '{args}'" if args else ""
        user_text = (
            f"I want to build an email sequence{campaign_hint}. "
            f"Before building, ask me all of these in one message: "
            f"(1) Exact target role/title — if already clear from the campaign name, confirm it. "
            f"(2) Number of steps — give a recommendation based on the scenario. "
            f"(3) Primary CodeCombat product to highlight — or ask if I want to cover the full suite. "
            f"(4) Any specific context: state CS requirements, budget timing, pain points, or scenario type (cold, post-demo, re-engagement, etc.). "
            f"Once you have my answers, use the build_sequence tool."
        )

    elif user_text.lower().startswith("/brief"):
        args = user_text[len("/brief"):].strip()
        await send_message(
            "🔍 *On it!* Looking up your calendar and researching attendees...\n"
            "This takes about 30-60 seconds. I'll send progress updates."
        )
        tool_input = {"meeting_title": args} if args else {}
        result = await execute_tool("get_pre_call_brief", tool_input)
        if result:
            await send_message(result)
        return

    elif user_text.lower().startswith("/recent_calls") or user_text.lower() in ["recent calls", "list calls", "show calls"]:
        num = 5
        raw = user_text.lower().replace("/recent_calls", "").strip()
        if raw.isdigit():
            num = max(1, min(int(raw), 20))
        if not FIREFLIES_API_KEY:
            await send_message("❌ FIREFLIES_API_KEY not set in Railway.")
            return
        await send_message(f"📞 Fetching your {num} most recent external calls from Fireflies...")
        try:
            from tools.fireflies import FirefliesClient
            ff_client = FirefliesClient(api_key=FIREFLIES_API_KEY)
            transcripts = ff_client.get_recent_transcripts(limit=num, filter_internal=True)
            msg = ff_client.format_recent_for_telegram(transcripts)
        except Exception as e:
            msg = f"❌ Could not fetch Fireflies transcripts: {e}"
        await send_message(msg)
        return

    elif user_text.lower().startswith("/call") and not user_text.lower().startswith("/call_list"):
        args = user_text[len("/call"):].strip()
        if "fireflies.ai" in args and "/transcript/" in args:
            args = args.split("/transcript/")[-1].split("/")[0].split("?")[0]
        # Allow optional email override: /call [id] email@domain.com
        email_override = ""
        parts = args.split()
        if len(parts) >= 2 and "@" in parts[-1]:
            email_override = parts[-1]
            args = " ".join(parts[:-1])
        if args:
            msg = f"📞 Got it — fetching transcript `{args}` from Fireflies..."
            if email_override:
                msg += f"\nUsing email override: {email_override}"
            await send_message(msg)
            tool_input = {"transcript_id": args}
            if email_override:
                tool_input["email_override"] = email_override
            result = await execute_tool("process_call_transcript", tool_input)
            if result:
                await send_message(result)
        else:
            await send_message("Give me the transcript ID, or use /recent_calls to find one.")
        return

    # ── Phase 6C commands ──────────────────────────────────────────────────────

    elif user_text.lower() in ["/progress", "/kpi", "kpi", "my progress", "how am i doing"]:
        await send_message("📊 Checking today's progress...")
        try:
            loop = asyncio.get_event_loop()
            progress = await loop.run_in_executor(None, activity_tracker.get_daily_progress)
            await send_message(progress.get("progress_text", "No activity data yet today."))
        except Exception as e:
            await send_message(f"❌ Could not load progress: {e}")
        return

    elif user_text.lower().startswith("/sync_activities") or user_text.lower() in ["sync activities", "sync gmail"]:
        result = await execute_tool("sync_gmail_activities", {})
        if result:
            await send_message(result)
        return

    elif user_text.lower().startswith("/set_goal"):
        args = user_text[len("/set_goal"):].strip().split()
        if len(args) >= 2:
            goal_type = args[0]
            try:
                target = int(args[1])
                result = await execute_tool("set_goal", {"goal_type": goal_type, "daily_target": target})
                await send_message(result)
            except ValueError:
                await send_message("Usage: `/set_goal calls_made 15`\nGoal types: `calls_made`, `districts_researched`, `emails_drafted`")
        else:
            await send_message("Usage: `/set_goal calls_made 15`\nGoal types: `calls_made`, `districts_researched`, `emails_drafted`")
        return

    # ── Phase 6D commands ──────────────────────────────────────────────────────

    elif user_text.lower() in ["/call_list", "/daily_list", "call list",
                               "daily call list", "who should i call today",
                               "who should i call"]:
        await send_message("Building your daily call list...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, daily_call_list.build_daily_call_list)
            if not result["success"]:
                await send_message(f"Could not build call list: {result['error']}")
                return
            cards = result["cards"]
            if not cards:
                await send_message("No contacts matched your active accounts. Research more districts or upload a fresh Salesforce CSV.")
                return
            doc_url = ""
            gas = get_gas_bridge()
            if gas:
                doc_result = await loop.run_in_executor(
                    None, daily_call_list.write_call_list_to_doc, cards, gas
                )
                doc_url = doc_result.get("url", "")
            tg_text = daily_call_list.format_for_telegram(cards, doc_url=doc_url)
            await send_message(tg_text)
            try:
                activity_tracker.log_activity(
                    "call_list_generated",
                    notes=f"{len(cards)} contacts from {result.get('district_count', 0)} districts",
                )
            except Exception:
                pass
        except Exception as e:
            await send_message(f"Call list failed: {e}")
        return

    # ── Phase 6E commands ──────────────────────────────────────────────────────

    elif user_text.lower().startswith("/prospect_discover"):
        global _last_prospect_batch
        args = user_text[len("/prospect_discover"):].strip()
        if not args:
            await send_message("Usage: `/prospect_discover Texas` or `/prospect_discover TX`")
            return
        await send_message(f"🔍 Searching for school districts in *{args}*...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.discover_districts, args)
            if not result["success"]:
                await send_message(f"Discovery failed: {result['error']}")
                return
            msg = (
                f"Found {result['discovered']} districts in {args}\n"
                f"Already known: {result['already_known']} | New added to queue: {result['new_added']}"
            )
            if result.get("territory_warning"):
                msg += f"\n⚠️ {result['territory_warning']}"
            await send_message(msg)
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Discovery error: {e}")
        return

    elif user_text.lower().startswith("/prospect_upward"):
        global _last_prospect_batch
        await send_message("🔍 Finding upward targets from your active school accounts...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.suggest_upward_targets)
            if not result["success"]:
                await send_message(f"Error: {result['error']}")
                return
            msg = (
                f"Found {result['new_added'] + result['already_known']} upward targets\n"
                f"New added to queue: {result['new_added']} | Already queued: {result['already_known']}"
            )
            await send_message(msg)
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Upward targets error: {e}")
        return

    elif user_text.lower().startswith("/prospect_approve"):
        global _last_prospect_batch
        args = user_text[len("/prospect_approve"):].strip()
        if not args or not _last_prospect_batch:
            await send_message("No prospect batch to approve. Use `/prospect` first.")
            return
        try:
            indices = [int(x.strip()) for x in args.split(",")]
        except ValueError:
            await send_message("Usage: `/prospect_approve 1,3,5`")
            return
        try:
            loop = asyncio.get_event_loop()
            approved = await loop.run_in_executor(
                None, district_prospector.approve_districts, indices, _last_prospect_batch
            )
            if not approved:
                await send_message("No valid indices to approve.")
                return
            names = [d.get("District Name", "?") for d in approved]
            await send_message(f"✅ Approved {len(approved)} districts: {', '.join(names)}\nQueuing research...")
            for d in approved:
                name_key = d.get("Name Key", "")
                district_prospector.mark_researching(name_key)
                await research_queue.enqueue(
                    district_name=d.get("District Name", ""),
                    state=d.get("State", ""),
                    progress_callback=_on_research_progress,
                    completion_callback=lambda result, prospect=d: asyncio.ensure_future(
                        _on_prospect_research_complete(result, prospect)
                    ),
                )
        except Exception as e:
            await send_message(f"Approve error: {e}")
        return

    elif user_text.lower().startswith("/prospect_skip"):
        global _last_prospect_batch
        args = user_text[len("/prospect_skip"):].strip()
        if not args or not _last_prospect_batch:
            await send_message("No prospect batch to skip. Use `/prospect` first.")
            return
        try:
            indices = [int(x.strip()) for x in args.split(",")]
        except ValueError:
            await send_message("Usage: `/prospect_skip 2,4`")
            return
        try:
            loop = asyncio.get_event_loop()
            skipped = await loop.run_in_executor(
                None, district_prospector.skip_districts, indices, _last_prospect_batch
            )
            names = [d.get("District Name", "?") for d in skipped]
            await send_message(f"⏭ Skipped {len(skipped)} districts: {', '.join(names)}")
        except Exception as e:
            await send_message(f"Skip error: {e}")
        return

    elif user_text.lower().startswith("/prospect_add"):
        args = user_text[len("/prospect_add"):].strip()
        parts = [p.strip() for p in args.split(",")]
        if len(parts) < 2:
            await send_message("Usage: `/prospect_add Austin ISD, TX`")
            return
        name, state = parts[0], parts[1]
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.add_district, name, state)
            await send_message(result["message"])
        except Exception as e:
            await send_message(f"Add error: {e}")
        return

    elif user_text.lower() in ["/prospect_all", "prospect all", "show all prospects"]:
        try:
            loop = asyncio.get_event_loop()
            all_prospects = await loop.run_in_executor(None, district_prospector.get_all_prospects)
            if not all_prospects:
                await send_message("Prospecting queue is empty. Use `/prospect_discover [state]` or `/prospect_upward` to populate it.")
                return
            await send_message(district_prospector.format_all_for_telegram(all_prospects))
        except Exception as e:
            await send_message(f"Queue view error: {e}")
        return

    elif user_text.lower() in ["/prospect", "/prospects", "prospect", "show prospects",
                                "prospect queue", "prospecting queue"]:
        global _last_prospect_batch
        try:
            loop = asyncio.get_event_loop()
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if not pending:
                await send_message("No pending districts. Use `/prospect_discover [state]` or `/prospect_upward` to find some.")
                return
            _last_prospect_batch = pending
            await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Prospect queue error: {e}")
        return

    elif _pending_draft and any(
        user_text.lower().startswith(t) for t in ["looks good", "save it", "save to gmail", "approved", "use this"]
    ):
        result = await execute_tool("save_draft_to_gmail", {
            "to": _pending_draft.get("to", ""),
            "subject": _pending_draft.get("subject", ""),
            "body": _pending_draft.get("body", ""),
        })
        await send_message(result)
        return

    elif _pending_draft and user_text.lower().startswith("add email:"):
        email_addr = user_text[len("add email:"):].strip()
        _pending_draft["to"] = email_addr
        await send_message(f"✅ Recipient set to `{email_addr}`. Say *looks good* to save.")
        return

    # Behavioral correction detection
    correction_signals = [
        "stop ", "don't ", "do not ", "always ", "never ", "remember to ",
        "please don't", "i want you to", "from now on", "every time",
        "too long", "too short", "too formal", "too casual",
    ]
    if any(sig in user_text.lower() for sig in correction_signals):
        user_text = (
            user_text
            + "\n\n[If this is a behavioral correction or preference, append [MEMORY_UPDATE: one sentence summary] to your response so it gets saved permanently.]"
        )

    # General ack for task-style messages
    if not _ack_sent and any(
        kw in user_text.lower() for kw in [
            "draft", "research", "sequence", "deck", "train", "brief", "build",
            "create", "generate", "write", "log", "push", "fetch",
        ]
    ):
        await send_message("⏳ Working on it...")
        _ack_sent = True

    # ── Claude processing ──────────────────────────────────────────────────────

    text_response, conversation_history, tool_calls = process_message(
        user_message=user_text,
        history=conversation_history,
        memory=memory,
    )

    if text_response.startswith("❌ Claude API error"):
        if "tool_use" in text_response and "tool_result" in text_response:
            logger.warning("400 tool_use error — clearing conversation history to recover.")
            conversation_history.clear()
        await send_message(text_response)
        return

    # ── Tool execution — ALWAYS append result even if tool throws ─────────────
    tool_results = []
    for tc in tool_calls:
        try:
            result = await execute_tool(tc["tool_name"], tc["tool_input"])
        except Exception as e:
            logger.error(f"Tool '{tc['tool_name']}' raised exception: {e}")
            result = f"❌ Tool error in {tc['tool_name']}: {e}"
        tool_results.append(result)

    # CRITICAL: Every tool_use block MUST have a matching tool_result in the next message.
    if tool_calls and tool_results:
        tool_result_content = [
            {
                "type": "tool_result",
                "tool_use_id": tc["tool_use_id"],
                "content": str(result),
            }
            for tc, result in zip(tool_calls, tool_results)
        ]
        conversation_history.append({
            "role": "user",
            "content": tool_result_content,
        })

    def _clean(msg: str) -> str:
        msg = re.sub(r"\s*\bOn it[.!]*\s*$", "", msg, flags=re.IGNORECASE).strip()
        msg = re.sub(r"\s*Let me know if (you need|there's|you have).*$", "", msg, flags=re.IGNORECASE | re.DOTALL).strip()
        return msg

    if text_response and not tool_calls:
        await send_message(_clean(text_response))
    elif tool_results:
        for r in tool_results:
            if r:
                await send_message(_clean(r))
    else:
        await send_message("👍")


# ── Scheduled messages ─────────────────────────────────────────────────────────

async def send_morning_brief():
    try:
        with open("prompts/morning_brief.md", "r") as f:
            prompt_template = f.read()

        # Phase 6C: inject real activity data from yesterday
        try:
            from datetime import date, timedelta
            yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            data_block = activity_tracker.build_brief_data_block(date_str=yesterday)
            prompt = f"{data_block}\n\n---\n\n{prompt_template}"
        except Exception as data_err:
            logger.warning(f"Could not load activity data for morning brief: {data_err}")
            prompt = prompt_template

        text, _, _ = process_message(prompt, [], memory)
        await send_message(f"☀️ *Good morning, Steven!*\n\n{text}")
    except Exception as e:
        logger.error(f"Morning brief failed: {e}")


async def send_eod_report():
    try:
        with open("prompts/eod_report.md", "r") as f:
            prompt_template = f.read()

        # Phase 6C: inject real activity data from today + trigger Gmail sync first
        try:
            gas = get_gas_bridge()
            if gas:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, activity_tracker.sync_gmail_activities, gas)
        except Exception as sync_err:
            logger.warning(f"Gmail sync before EOD failed: {sync_err}")

        try:
            data_block = activity_tracker.build_brief_data_block()
            prompt = f"{data_block}\n\n---\n\n{prompt_template}"
        except Exception as data_err:
            logger.warning(f"Could not load activity data for EOD: {data_err}")
            prompt = prompt_template

        text, _, _ = process_message(prompt, conversation_history, memory)
        await send_message(f"🌙 *EOD Report*\n\n{text}")
        memory.append_to_summary(text)
        conversation_history.clear()
    except Exception as e:
        logger.error(f"EOD report failed: {e}")


async def send_checkin():
    await send_message("📊 Hourly check-in — anything you need, Steven?")


# ── Phase 5: Webhook transcript callback ──────────────────────────────────────

async def _on_transcript_received(transcript_id: str):
    await send_message(f"📞 Call transcript received — processing `{transcript_id}`...")
    gas = get_gas_bridge()
    if not gas or not FIREFLIES_API_KEY:
        await send_message("❌ GAS bridge or FIREFLIES_API_KEY not configured.")
        return
    try:
        from tools.fireflies import FirefliesClient
        from agent.call_processor import CallProcessor
        fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=fireflies)
        except Exception as e:
            await send_message(f"❌ Could not initialize call processor: {e}")
            return
        async def on_progress(msg):
            await send_message(msg)
        result = await processor.process_transcript(transcript_id=transcript_id, progress_callback=on_progress)
        if result.get("error"):
            await send_message(f"❌ Processing failed: {result['error']}")
            return
        await send_message(result["telegram_summary"])
        await send_message(result["salesforce_block"])
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        await send_message(f"❌ Error processing transcript {transcript_id}: {e}")


# ── Phase 5+: Fireflies Gmail polling ─────────────────────────────────────────

async def _check_fireflies_gmail(gas):
    """
    Scans Gmail every 60s for new Fireflies recap emails.
    On the first run after startup, seeds existing emails as already-seen so Scout
    doesn't replay old meetings on reboot. Only emails that arrive after startup
    trigger processing.
    """
    global _fireflies_email_triggers, _fireflies_gmail_seeded
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: gas.search_inbox("from:fireflies.ai", max_results=5)
        )

        if not _fireflies_gmail_seeded:
            # First run: mark all existing emails as already seen — don't process any
            for email in results:
                subj = email.get("subject", "")
                date = email.get("date", "")[:16]
                key = f"{subj[:60]}|{date}"
                _fireflies_email_triggers.add(key)
            _fireflies_gmail_seeded = True
            logger.info(f"[Fireflies Gmail] Seeded {len(results)} existing email(s) — watching for new ones.")
            return

        for email in results:
            subj = email.get("subject", "")
            date = email.get("date", "")[:16]
            key = f"{subj[:60]}|{date}"

            # Only care about recap / meeting note emails
            subj_lower = subj.lower()
            if "recap" not in subj_lower and "meeting note" not in subj_lower:
                continue

            if key in _fireflies_email_triggers:
                continue
            _fireflies_email_triggers.add(key)

            # Parse meeting name from subject
            meeting_name = subj
            for prefix in [
                "Your Fireflies.ai meeting recap:",
                "Your Fireflies meeting recap:",
                "Fireflies.ai meeting notes:",
            ]:
                if subj_lower.startswith(prefix.lower()):
                    meeting_name = subj[len(prefix):].strip()
                    break

            await send_message(
                f"📞 Fireflies recap detected: *{meeting_name}*\n"
                f"Fetching transcript... I'll update you every minute if still processing."
            )
            asyncio.create_task(_process_latest_fireflies_transcript(meeting_name))
    except Exception as e:
        logger.warning(f"[Fireflies Gmail check] {e}")


async def _process_latest_fireflies_transcript(meeting_name: str):
    """
    Polls the Fireflies API for the newest unprocessed external transcript.
    Retries up to 5 times (60s apart) with Telegram status updates.
    """
    global _fireflies_processed_ids
    if not FIREFLIES_API_KEY:
        return

    loop = asyncio.get_event_loop()

    for attempt in range(1, 6):
        try:
            from tools.fireflies import FirefliesClient
            fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
            transcripts = await loop.run_in_executor(
                None, lambda: fireflies.get_recent_transcripts(limit=3)
            )

            new_t = next(
                (t for t in transcripts
                 if t.get("id") and t["id"] not in _fireflies_processed_ids),
                None
            )

            if not new_t:
                if attempt < 5:
                    await send_message(
                        f"⏳ Transcript not ready yet (attempt {attempt}/5) — "
                        f"checking again in 60s"
                    )
                    await asyncio.sleep(60)
                else:
                    await send_message(
                        "❌ Fireflies transcript not available after 5 attempts. "
                        "Use `/call [id]` to process manually."
                    )
                continue

            transcript_id = new_t["id"]
            _fireflies_processed_ids.add(transcript_id)
            await _on_transcript_received(transcript_id)
            return

        except Exception as e:
            if attempt < 5:
                await send_message(
                    f"⏳ Attempt {attempt}/5 failed ({e}) — retrying in 60s"
                )
                await asyncio.sleep(60)
            else:
                await send_message(
                    f"❌ Could not process transcript after 5 attempts: {e}\n"
                    f"Use `/call [id]` to process manually."
                )


# ── Phase 5: Pre-call brief auto-trigger ───────────────────────────────────────

async def _check_precall_briefs(gas):
    global _precall_briefs_sent
    try:
        from agent.call_processor import CallProcessor
        events = gas.get_calendar_events(days_ahead=1)
        now = datetime.now(CST)
        for event in events:
            event_id = (event.get("id") or "") or (event.get("title","") + "|" + event.get("start",""))
            if event_id in _precall_briefs_sent:
                continue
            loc = (event.get("location") or "").lower()
            desc = (event.get("description") or "").lower()
            if "zoom.us" not in loc and "zoom.us" not in desc:
                continue
            start_str = event.get("start", "")
            if not start_str:
                continue
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start_cst = start_dt.astimezone(CST)
                minutes_until = (start_cst - now).total_seconds() / 60
            except Exception:
                continue
            if 9 <= minutes_until <= 11:
                _precall_briefs_sent.add(event_id)
                raw_guests = event.get("guests") or []
                attendees = _parse_guests(raw_guests)
                if not attendees:
                    attendees = [{"name": "Prospect", "email": ""}]
                await send_message(f"⏰ 10-minute warning: *{event.get('title','Zoom call')}*\nBuilding pre-call brief now...")
                try:
                    processor = CallProcessor(gas_bridge=gas, memory_manager=memory)
                    async def on_brief_progress(msg):
                        await send_message(msg)
                    brief = await processor.build_pre_call_brief(
                        event=event, attendees=attendees, progress_callback=on_brief_progress
                    )
                    await send_message(brief)
                except Exception as e:
                    logger.error(f"Pre-call brief auto-trigger error: {e}")
                    await send_message(f"❌ Pre-call brief error: {e}")
    except Exception as e:
        logger.warning(f"Calendar check failed: {e}")


# ── Entry point ────────────────────────────────────────────────────────────────

async def _run_telegram_and_scheduler():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    scheduler = Scheduler()
    gas = get_gas_bridge() if gas_bridge_configured() else None

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    gas_status = "GAS bridge ready" if gas_bridge_configured() else "GAS bridge not configured"
    ff_status = "Fireflies ready" if FIREFLIES_API_KEY else "FIREFLIES_API_KEY not set"
    await send_message(
        f"Scout is online — Phase 6D active.\n"
        f"{gas_status} | {ff_status}\n"
        f"Commands: /brief | /recent_calls [num] | /call [id] | /push_code [file]\n"
        f"/call_list | /progress | /sync_activities | /set_goal [type] [target] | send CSV to import"
    )

    fireflies_gmail_last_check: float = 0.0

    try:
        while True:
            sched_event = scheduler.check()
            if sched_event == "morning_brief":
                asyncio.create_task(send_morning_brief())
            elif sched_event == "eod_report":
                asyncio.create_task(send_eod_report())
            elif sched_event == "checkin":
                asyncio.create_task(send_checkin())
            if gas and FIREFLIES_API_KEY:
                asyncio.create_task(_check_precall_briefs(gas))
                now_ts = time.time()
                if now_ts - fireflies_gmail_last_check >= 60:
                    fireflies_gmail_last_check = now_ts
                    asyncio.create_task(_check_fireflies_gmail(gas))
            await asyncio.sleep(30)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def main():
    logger.info(f"Starting {AGENT_NAME} — Phase 6D...")
    port = int(os.environ.get("PORT", 8080))
    if os.environ.get("PORT"):
        from agent.webhook_server import start_webhook_server
        logger.info(f"Webhook server starting on port {port}")
        await asyncio.gather(
            _run_telegram_and_scheduler(),
            start_webhook_server(
                port=port,
                process_callback=_on_transcript_received,
                webhook_secret=FIREFLIES_WEBHOOK_SECRET,
            ),
        )
    else:
        await _run_telegram_and_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
