"""
agent/main.py
Scout's entry point. Phase 3: Gmail + Calendar + Slides via GAS bridge.
"""

import asyncio
import logging
import os
import re

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
from tools.telegram_bot import send_message
# Phase 4 modules imported lazily inside execute_tool() — safe to boot without them

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Global state ──────────────────────────────────────────────────────────────

memory = MemoryManager()
conversation_history = []

# Pending draft — stores last unconfirmed draft
_pending_draft = None


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


# ── Research callbacks (async, matches ResearchQueue.enqueue signature) ───────

async def _on_research_progress(message: str):
    await send_message(message)


async def _on_research_complete(result: dict):
    """Called by ResearchQueue when a job finishes. Writes to sheets + notifies."""
    try:
        contacts = result.get("contacts", [])
        sheets_writer.write_contacts(contacts, state=result.get("state", ""))

        with_email = result.get("with_email", 0)
        no_email = result.get("no_email", 0)
        total = result.get("total", 0)
        district = result.get("district_name", "")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{os.environ.get('GOOGLE_SHEETS_ID', '')}"

        await send_message(
            f"✅ *Research complete: {district}*\n"
            f"{total} contacts — {with_email} with emails, {no_email} name-only.\n"
            f"[View sheet]({sheet_url})"
        )
    except Exception as e:
        logger.error(f"Research completion handler failed: {e}")
        await send_message(f"❌ Research finished but sheet write failed: {e}")


# ── Tool execution ─────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict) -> str:
    global _pending_draft  # declared once at top of function

    # ── Phase 2: Research ──────────────────────────────────────────────────────

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
        return f"📋 Research queued for *{district}*. I'll update you when done."

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
        current = research_queue.current_job   # property, not method
        depth = research_queue.queue_size       # property, not method
        if not current:
            return "✅ No research running. Queue empty."
        return f"🔍 Currently researching: *{current}*\nJobs queued: {depth}"

    # ── Phase 3: GAS bridge connection test ───────────────────────────────────

    elif tool_name == "ping_gas_bridge":
        gas = get_gas_bridge()
        if not gas:
            return (
                "❌ GAS bridge not configured.\n"
                "Set `GAS_WEBHOOK_URL` and `GAS_SECRET_TOKEN` in Railway.\n"
                "See `docs/SETUP_PHASE3.md` for setup instructions."
            )
        try:
            result = gas.ping()
            return f"✅ *GAS Bridge connected!*\nRunning as: `{result.get('user', 'unknown')}`"
        except Exception as e:
            return f"❌ GAS bridge ping failed: {e}"

    # ── Phase 3: Voice training ────────────────────────────────────────────────

    elif tool_name == "train_voice":
        trainer = get_voice_trainer()
        if not trainer:
            return (
                "❌ GAS bridge not configured yet.\n"
                "Follow `docs/SETUP_PHASE3.md` to set up the Google Apps Script bridge first."
            )
        months_back = tool_input.get("months_back", 6)

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

    # ── Phase 3: Email drafting ────────────────────────────────────────────────

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

        _pending_draft = {
            "to": "",
            "subject": subject,
            "body": body,
            "raw": draft_text,
        }

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
            return "❌ GAS bridge not configured. Follow `docs/SETUP_PHASE3.md` to set it up."

        to = tool_input.get("to", "") or (_pending_draft or {}).get("to", "")
        subject = tool_input.get("subject", "") or (_pending_draft or {}).get("subject", "")
        body = tool_input.get("body", "") or (_pending_draft or {}).get("body", "")

        if not subject or not body:
            return "❌ No draft to save. Draft an email first."

        try:
            result = gas.create_draft(to=to, subject=subject, body=body)
            _pending_draft = None
            return (
                f"✅ *Saved to Gmail Drafts!*\n"
                f"Subject: _{subject}_\n"
                f"[Open Gmail Drafts]({result.get('link', 'https://mail.google.com/mail/u/0/#drafts')})"
            )
        except Exception as e:
            return f"❌ Could not save draft: {e}"

    # ── Phase 3: Calendar ──────────────────────────────────────────────────────

    elif tool_name == "get_calendar":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured. Follow `docs/SETUP_PHASE3.md`."

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
            return "❌ GAS bridge not configured. Follow `docs/SETUP_PHASE3.md`."
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
            return (
                f"✅ *Call logged!*\n"
                f"_{result.get('title', 'Call')}_\n"
                f"[View in Calendar]({result.get('link', 'https://calendar.google.com/calendar/r')})"
            )
        except Exception as e:
            return f"❌ Could not log call: {e}"

    # ── Phase 3: Slides ────────────────────────────────────────────────────────

    elif tool_name == "create_district_deck":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured. Follow `docs/SETUP_PHASE3.md`."

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

    # ── Phase 4: GitHub code push ─────────────────────────────────────────────

    elif tool_name == "push_code":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "❌ `tools/github_pusher.py` not found in repo. Upload it to GitHub first."

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
            return "❌ `tools/github_pusher.py` not found in repo. Upload it to GitHub first."

        path = tool_input.get("path", "")
        files = github_pusher.list_repo_files(path)
        if not files:
            return f"❌ Could not list files in `{path or 'repo root'}` — check GITHUB_TOKEN and GITHUB_REPO."
        label = f"`{path}/`" if path else "repo root"
        lines = [f"📁 *Files in {label}:*\n"] + [f"• `{f}`" for f in files]
        return "\n".join(lines)

    # ── Phase 4: Email sequences ───────────────────────────────────────────────

    elif tool_name == "build_sequence":
        try:
            import tools.sequence_builder as sequence_builder
        except ImportError:
            return "❌ `tools/sequence_builder.py` not found in repo. Upload it to GitHub first."

        campaign_name = tool_input.get("campaign_name", "")
        target_role = tool_input.get("target_role", "")
        focus_product = tool_input.get("focus_product", "CodeCombat AI Suite")
        num_steps = int(tool_input.get("num_steps", 4))
        additional_context = tool_input.get("additional_context", "")

        if not campaign_name or not target_role:
            return "❌ Need at least `campaign_name` and `target_role` to build a sequence."

        await send_message(
            f"✍️ Building {num_steps}-step sequence for *{target_role}s*...\n"
            f"Campaign: _{campaign_name}_"
        )

        # Load voice profile if available
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

        # Write to Google Sheets Sequences tab
        saved_to_sheets = sequence_builder.write_sequence_to_sheets(campaign_name, steps)
        sheets_note = "\n✅ Saved to *Sequences* tab in your sheet." if saved_to_sheets else ""

        # Format for Telegram
        tg_text = sequence_builder.format_for_telegram(campaign_name, steps)

        return f"{tg_text}{sheets_note}\n\n📋 Paste each step into Outreach.io sequence editor."


    return f"❓ Unknown tool: {tool_name}"


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

    # Shorthand commands
    if user_text.lower() in ["/ping_gas", "/test_google", "test gas", "ping gas"]:
        user_text = "ping the GAS bridge"
    elif user_text.lower() in ["/train_voice", "train voice", "train my voice", "learn my style"]:
        user_text = "train your voice model from my Gmail history"
    elif user_text.lower() in ["/list_files", "/ls", "list files", "show repo files"]:
        user_text = "list all files in the repo root"
    elif user_text.lower().startswith("/push_code"):
        # /push_code filepath
        # The actual file content will come in Claude's next turn — just set context
        args = user_text[len("/push_code"):].strip()
        user_text = f"I want to push code to GitHub. File path: {args}. Ask me for the file content." if args else "I want to push a file to GitHub. Ask me which file and what the content should be."
    elif user_text.lower().startswith("/build_sequence") or user_text.lower().startswith("/sequence"):
        args = user_text.split(" ", 1)[1].strip() if " " in user_text else ""
        user_text = f"Build an email sequence{' for ' + args if args else ''}. Ask me for any details you need."

    # Pending draft approvals
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

    # Normal processing
    text_response, conversation_history, tool_calls = process_message(
        user_message=user_text,
        history=conversation_history,
        memory=memory,
    )

    tool_results = []
    for tc in tool_calls:
        result = await execute_tool(tc["tool_name"], tc["tool_input"])
        tool_results.append(result)

    # CRITICAL: Append tool_result blocks back into history.
    # The Claude API requires every tool_use block to be immediately followed
    # by a tool_result block in the next user message. Without this, the next
    # API call fails with a 400 "tool_use ids found without tool_result" error.
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

    if text_response:
        await send_message(text_response)
    elif tool_results:
        for r in tool_results:
            await send_message(r)
    else:
        await send_message("👍")


# ── Scheduled messages ─────────────────────────────────────────────────────────

async def send_morning_brief():
    try:
        with open("prompts/morning_brief.md", "r") as f:
            prompt = f.read()
        text, _, _ = process_message(prompt, [], memory)
        await send_message(f"☀️ *Good morning, Steven!*\n\n{text}")
    except Exception as e:
        logger.error(f"Morning brief failed: {e}")


async def send_eod_report():
    try:
        with open("prompts/eod_report.md", "r") as f:
            prompt = f.read()
        text, _, _ = process_message(prompt, conversation_history, memory)
        await send_message(f"🌙 *EOD Report*\n\n{text}")
        memory.append_to_summary(text)   # persist today's summary to context_summary.md + GitHub
        conversation_history.clear()
    except Exception as e:
        logger.error(f"EOD report failed: {e}")


async def send_checkin():
    await send_message("📊 Hourly check-in — anything you need, Steven?")


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    logger.info(f"Starting {AGENT_NAME}...")
    # MemoryManager.__init__ already calls _ensure_files_exist() — no .load() needed

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))

    scheduler = Scheduler()

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    gas_status = "✅ GAS bridge configured" if gas_bridge_configured() else "⚠️ GAS bridge not yet configured (see SETUP_PHASE3.md)"
    await send_message(
        f"🤖 *{AGENT_NAME} is online — Phase 4 active.*\n"
        f"{gas_status}\n"
        f"New: `/push_code` • `/build_sequence` • `/list_files`"
    )

    stop_event = asyncio.Event()
    try:
        # Poll scheduler every 30 seconds and dispatch scheduled events
        while not stop_event.is_set():
            event = scheduler.check()
            if event == "morning_brief":
                asyncio.create_task(send_morning_brief())
            elif event == "eod_report":
                asyncio.create_task(send_eod_report())
            elif event == "checkin":
                asyncio.create_task(send_checkin())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
