"""
scheduler.py — Scout's scheduled daily jobs.

FIXES FROM PHASE 1:
  - BUG FIX: Railway runs UTC. Old code scheduled in UTC so "09:15" fired at 3:15am CST.
    Fixed by checking current CST time every minute rather than relying on schedule library's
    wall-clock time. This works correctly regardless of server timezone.
  - BUG FIX: Hourly check-ins fired 24/7. Now restricted to CHECKIN_START_HOUR–CHECKIN_END_HOUR
    CST (default 10am–4pm).
  - BUG FIX: Morning brief hallucinated activity. Prompt rewritten to only report real data.
  - IMPROVEMENT: EOD report now compresses conversation into memory instead of wiping history.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime

import pytz

from agent import config
from tools.telegram_bot import send_message

logger = logging.getLogger(__name__)


class ScoutScheduler:

    def __init__(self, brain, memory_manager):
        self.brain = brain
        self.memory = memory_manager
        self.timezone = pytz.timezone(config.TIMEZONE)
        self._last_fired = {}   # Tracks which jobs have fired today to prevent double-firing

    def _load_prompt(self, filename: str) -> str:
        from pathlib import Path
        path = Path(__file__).parent.parent / "prompts" / filename
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _now_cst(self) -> datetime:
        return datetime.now(self.timezone)

    def _today_key(self, job_name: str) -> str:
        """Unique key per job per day — prevents double-firing."""
        return f"{job_name}_{self._now_cst().strftime('%Y-%m-%d')}"

    def _already_fired(self, job_name: str) -> bool:
        return self._today_key(job_name) in self._last_fired

    def _mark_fired(self, job_name: str):
        self._last_fired[self._today_key(job_name)] = True

    # ─── JOBS ────────────────────────────────────────────────────────────────

    async def _run_morning_brief(self):
        logger.info("[Scheduler] Running morning brief...")
        today = self._now_cst().strftime("%A, %B %d")
        prompt = self._load_prompt("morning_brief.md")
        try:
            brief = await self.brain.one_shot(prompt, f"Today is {today}.")
            await send_message(f"☀️ Good morning Steven.\n\n{brief}")
            logger.info("[Scheduler] Morning brief sent.")
        except Exception as e:
            logger.error(f"[Scheduler] Morning brief failed: {e}")
            await send_message(f"Morning brief failed: {str(e)}")

    async def _run_eod_report(self):
        """
        EOD report — replaces clear_history() with memory compression.
        Conversation history is summarized and saved, not deleted.
        """
        logger.info("[Scheduler] Running EOD report...")
        today = self._now_cst().strftime("%A, %B %d")
        prompt = self._load_prompt("eod_report.md")
        try:
            report = await self.brain.one_shot(prompt, f"Today is {today}.")
            await send_message(f"📊 EOD Report — {today}\n\n{report}")

            # Compress and save today's conversation to memory instead of wiping it
            await self._compress_history_to_memory(today)

            logger.info("[Scheduler] EOD report sent. History compressed to memory.")
        except Exception as e:
            logger.error(f"[Scheduler] EOD report failed: {e}")
            await send_message(f"EOD report failed: {str(e)}")

    async def _compress_history_to_memory(self, date_label: str):
        """
        Summarize today's conversation history into a compact memory entry.
        Saves to context_summary.md and commits to GitHub.
        Then trims the in-memory history to the last 4 exchanges.
        """
        history = self.brain.conversation_history
        if not history or len(history) < 2:
            return

        # Build a readable transcript of today's conversation
        transcript_lines = []
        for msg in history:
            role = "Steven" if msg["role"] == "user" else "Scout"
            content = msg["content"][:300]  # Truncate long messages for compression
            transcript_lines.append(f"{role}: {content}")
        transcript = "\n".join(transcript_lines)

        compression_prompt = (
            "You are summarizing today's conversation between Steven and Scout for long-term memory. "
            "Write a compact summary (max 200 words) covering:\n"
            "- Key tasks requested and whether they were completed\n"
            "- Any leads found or research done (district names, contact counts)\n"
            "- Any corrections or preferences Steven expressed\n"
            "- Decisions made\n"
            "- What is pending or carries over to tomorrow\n\n"
            "Be factual. Do not invent anything not in the transcript.\n\n"
            f"TRANSCRIPT:\n{transcript}"
        )

        try:
            summary = await self.brain.one_shot(compression_prompt)
            self.memory.append_to_summary(summary)
            # Trim live history to last 4 exchanges (keeps some immediate context)
            self.brain.conversation_history = self.brain.conversation_history[-8:]
            logger.info("[Scheduler] History compressed and saved to memory.")
        except Exception as e:
            logger.error(f"[Scheduler] History compression failed: {e}")

    async def _run_hourly_checkin(self):
        now = self._now_cst()
        hour = now.strftime("%I:%M %p").lstrip("0")
        hour_24 = now.hour

        # ── WINDOW GUARD: only fire between CHECKIN_START_HOUR and CHECKIN_END_HOUR ──
        if hour_24 < config.CHECKIN_START_HOUR or hour_24 > config.CHECKIN_END_HOUR:
            logger.debug(f"[Scheduler] Skipping check-in at {hour} — outside window.")
            return

        # Skip if it coincides with morning brief or EOD windows
        hhmm = now.strftime("%H:%M")
        if hhmm in (config.MORNING_BRIEF_TIME, config.EOD_REPORT_TIME):
            logger.info("[Scheduler] Skipping check-in — brief/report time.")
            return

        logger.info(f"[Scheduler] Running hourly check-in ({hour})...")

        prompt = (
            f"It is {hour} CST. Send Steven a brief hourly check-in.\n\n"
            f"Format exactly:\n"
            f"🕐 {hour} check-in\n\n"
            f"WORKING ON: [1-2 sentences — be specific about what is actually in progress "
            f"from this conversation. If nothing has been assigned, say so honestly. "
            f"Do not invent or assume tasks.]\n\n"
            f"ANY TASKS FOR ME? Reply with anything you want me to work on, "
            f"or reply SKIP to skip this hour.\n\n"
            f"Keep it under 60 words total."
        )
        try:
            checkin = await self.brain.one_shot(prompt)
            await send_message(checkin)
            logger.info("[Scheduler] Hourly check-in sent.")
        except Exception as e:
            logger.error(f"[Scheduler] Hourly check-in failed: {e}")

    # ─── TICK-BASED SCHEDULER ────────────────────────────────────────────────

    def _should_fire(self, job_name: str, target_hhmm: str) -> bool:
        """
        Check if a job should fire right now.
        Compares current CST time to target. Fires once per day.
        Works correctly regardless of Railway server timezone (UTC).
        """
        if self._already_fired(job_name):
            return False
        now_hhmm = self._now_cst().strftime("%H:%M")
        return now_hhmm == target_hhmm

    def _tick(self):
        """Called every 60 seconds. Checks whether any jobs are due."""
        now = self._now_cst()

        # Morning brief
        if self._should_fire("morning_brief", config.MORNING_BRIEF_TIME):
            self._mark_fired("morning_brief")
            asyncio.run(self._run_morning_brief())

        # EOD report
        if self._should_fire("eod_report", config.EOD_REPORT_TIME):
            self._mark_fired("eod_report")
            asyncio.run(self._run_eod_report())

        # Hourly check-in — fires at the top of each hour (:00)
        if now.minute == 0:
            checkin_key = f"checkin_{now.strftime('%Y-%m-%d_%H')}"
            if checkin_key not in self._last_fired:
                self._last_fired[checkin_key] = True
                asyncio.run(self._run_hourly_checkin())

    def run_in_background(self):
        """Start the scheduler loop in a daemon thread."""
        def loop():
            logger.info("[Scheduler] Background loop started.")
            while True:
                try:
                    self._tick()
                except Exception as e:
                    logger.error(f"[Scheduler] Tick error: {e}")
                time.sleep(60)  # Check every minute

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()

        now = self._now_cst()
        logger.info(f"[Scheduler] Running. Current CST: {now.strftime('%H:%M')}")
        logger.info(f"[Scheduler] Morning brief: {config.MORNING_BRIEF_TIME} CST")
        logger.info(f"[Scheduler] EOD report: {config.EOD_REPORT_TIME} CST")
        logger.info(f"[Scheduler] Check-ins: {config.CHECKIN_START_HOUR}:00–{config.CHECKIN_END_HOUR}:00 CST")
