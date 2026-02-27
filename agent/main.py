"""
main.py — Scout's entry point.
Wires: memory → brain → scheduler → telegram bot → research queue

Phase 2 additions:
  - ResearchQueue initialized and passed to brain
  - Tool call handling: research_district, get_sheet_status, get_research_queue_status
  - Progress messages and completion callbacks fire to Telegram
"""

import asyncio
import logging
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from agent.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    MORNING_BRIEF_TIME,
    EOD_REPORT_TIME,
    TIMEZONE,
    CHECKIN_START_HOUR,
    CHECKIN_END_HOUR,
    AGENT_NAME,
)
from agent.memory_manager import MemoryManager
from agent.claude_brain import ClaudeBrain
from agent.scheduler import Scheduler
from tools.research_engine import research_queue, ResearchQueue
from tools.sheets_writer import write_contacts, log_research_job, get_master_sheet_url, count_leads, ensure_sheet_tabs_exist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# GLOBALS
# ─────────────────────────────────────────────

memory = MemoryManager()
brain = ClaudeBrain(memory_manager=memory, research_queue=research_queue)
scheduler = Scheduler()
app: Application = None  # set during startup


# ─────────────────────────────────────────────
# TELEGRAM SEND HELPER
# ─────────────────────────────────────────────

async def send_message(text: str):
    """Send a message to Steven's Telegram chat."""
    if app is None:
        logger.error("App not initialized, can't send message")
        return
    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


# ─────────────────────────────────────────────
# TOOL EXECUTION (Phase 2)
# ─────────────────────────────────────────────

async def execute_tool(tool_call: dict, tool_use_id: str) -> str:
    """
    Execute a tool call returned by Claude.
    Returns a result string to inject back into Claude.
    """
    name = tool_call["name"]
    inp = tool_call.get("input", {})

    if name == "research_district":
        district = inp.get("district_name", "Unknown District")
        state = inp.get("state", "")

        queue_size = research_queue.queue_size
        is_busy = research_queue.is_busy

        if is_busy:
            current = research_queue.current_job
            eta_min = 5 + (queue_size * 5)  # rough estimate
            return (
                f"Research job queued. Currently researching: {current}. "
                f"Your job ({district}) is #{queue_size + 1} in queue. "
                f"Estimated wait: ~{eta_min} minutes."
            )

        # Start the job
        async def progress_callback(msg: str):
            await send_message(msg)

        async def completion_callback(result: dict):
            await _handle_research_complete(result)

        await research_queue.enqueue(
            district_name=district,
            state=state,
            progress_callback=progress_callback,
            completion_callback=completion_callback,
        )

        return f"Research job started for {district} ({state}). I'll update you as it progresses."

    elif name == "get_sheet_status":
        try:
            counts = count_leads()
            url = get_master_sheet_url()
            return (
                f"Master Sheet has {counts['leads']} leads with email, "
                f"{counts['no_email']} contacts without email, "
                f"{counts['total']} total. URL: {url}"
            )
        except Exception as e:
            return f"Could not fetch sheet status: {e}"

    elif name == "get_research_queue_status":
        if research_queue.is_busy:
            return (
                f"Currently researching: {research_queue.current_job}. "
                f"{research_queue.queue_size} job(s) waiting in queue."
            )
        else:
            return "No research job currently running. Queue is empty."

    else:
        return f"Unknown tool: {name}"


async def _handle_research_complete(result: dict):
    """Handle completion of a research job — write to sheets and notify Steven."""
    district = result["district_name"]
    state = result["state"]
    contacts = result["contacts"]
    total = result["total"]
    with_email = result["with_email"]
    no_email = result["no_email"]
    layers = result["layers_used"]

    # Write to Google Sheets
    try:
        write_result = write_contacts(contacts, state=state)
        log_research_job(
            district=district,
            state=state,
            layers_used=layers,
            total_found=total,
            with_email=with_email,
            no_email=no_email,
            notes=f"Added {write_result['leads_added']} leads, {write_result['duplicates_skipped']} dupes skipped"
        )
        sheet_url = get_master_sheet_url()

        msg = (
            f"✅ Research complete: **{district}**\n"
            f"📊 {total} contacts found — {with_email} with email, {no_email} name-only\n"
            f"📥 Added to sheet: {write_result['leads_added']} leads | {write_result['no_email_added']} no-email | {write_result['duplicates_skipped']} dupes skipped\n"
            f"🔗 [Open Master Sheet]({sheet_url})"
        )
    except Exception as e:
        logger.error(f"Sheet write failed for {district}: {e}")
        msg = (
            f"✅ Research complete: **{district}**\n"
            f"📊 {total} contacts found — {with_email} with email, {no_email} name-only\n"
            f"⚠️ Sheet write failed: {e}"
        )

    await send_message(msg)


# ─────────────────────────────────────────────
# MESSAGE HANDLER
# ─────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming Telegram messages from Steven."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return  # ignore unknown chats

    user_text = update.message.text.strip()
    if not user_text:
        return

    logger.info(f"Message from Steven: {user_text[:100]}")

    # Get Claude's response (may include tool call)
    response_text, tool_call = await brain.process_message(user_text)

    # If Claude wants to use a tool
    if tool_call:
        # Send any pre-tool text (e.g., "Sure, let me look that up...")
        if response_text.strip():
            await send_message(response_text)

        # Execute the tool
        tool_result = await execute_tool(tool_call, tool_call["tool_use_id"])

        # Send result back to Claude for natural follow-up
        follow_up = await brain.inject_tool_result(
            tool_use_id=tool_call["tool_use_id"],
            tool_name=tool_call["name"],
            result=tool_result
        )

        if follow_up.strip():
            await send_message(follow_up)
    else:
        if response_text.strip():
            await send_message(response_text)


# ─────────────────────────────────────────────
# SCHEDULED MESSAGES
# ─────────────────────────────────────────────

async def send_morning_brief():
    """Send the morning brief at 9:15am CST."""
    try:
        with open("prompts/morning_brief.md", "r") as f:
            prompt = f.read()
    except FileNotFoundError:
        prompt = "Send Steven a short, honest morning brief. Only mention real data you have."

    _, _ = await brain.process_message(f"[SYSTEM: MORNING BRIEF]\n{prompt}")
    history = brain.get_history_for_compression()
    if history:
        last = history[-1]
        text = last.get("content", "")
        if isinstance(text, str) and text.strip():
            await send_message(text)


async def send_eod_report():
    """Send EOD report at 4:30pm CST, then compress history to memory."""
    try:
        with open("prompts/eod_report.md", "r") as f:
            prompt = f.read()
    except FileNotFoundError:
        prompt = "Send Steven an honest EOD report. Only mention real things that happened today."

    _, _ = await brain.process_message(f"[SYSTEM: EOD REPORT]\n{prompt}")
    history = brain.get_history_for_compression()
    if history:
        last = history[-1]
        text = last.get("content", "")
        if isinstance(text, str) and text.strip():
            await send_message(text)

    # Compress to memory
    await brain.compress_to_memory()


async def send_checkin():
    """Send hourly check-in (10am–4pm CST only)."""
    _, _ = await brain.process_message(
        "[SYSTEM: HOURLY CHECK-IN] Send a brief, practical check-in. "
        "Only mention real activity. No hallucination. Keep it short."
    )
    history = brain.get_history_for_compression()
    if history:
        last = history[-1]
        text = last.get("content", "")
        if isinstance(text, str) and text.strip():
            await send_message(text)


# ─────────────────────────────────────────────
# SCHEDULER TICK
# ─────────────────────────────────────────────

async def tick():
    """Called every minute by scheduler. Fires scheduled messages at the right time."""
    action = scheduler.check()
    if action == "morning_brief":
        await send_morning_brief()
    elif action == "eod_report":
        await send_eod_report()
    elif action == "checkin":
        await send_checkin()


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

async def main():
    global app

    logger.info(f"Starting Scout (Phase 2)...")

    # Initialize Google Sheets tabs on startup (non-blocking)
    try:
        ensure_sheet_tabs_exist()
        logger.info("Google Sheets tabs verified/created")
    except Exception as e:
        logger.warning(f"Sheet init failed (will retry on first use): {e}")

    # Build Telegram app
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info(f"Scout is live. Listening on Telegram chat {TELEGRAM_CHAT_ID}")
    await send_message(f"🤖 **Scout online.** Phase 2 active — lead research ready. Say *'Research [district name]'* to start.")

    # Tick loop
    stop_event = asyncio.Event()
    try:
        while not stop_event.is_set():
            await tick()
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down Scout...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
