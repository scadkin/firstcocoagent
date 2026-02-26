"""
scheduler.py — Runs Scout's scheduled daily jobs.
Morning brief at 9:15am, EOD report at 4:30pm, hourly check-in every hour.
All times in America/Chicago (CST).
"""

import asyncio
import logging
import schedule
import time
import threading
from datetime import datetime
import pytz
from agent import config
from tools.telegram_bot import send_message

logger = logging.getLogger(__name__)


class ScoutScheduler:

    def __init__(self, brain):
        self.brain = brain
        self.timezone = pytz.timezone(config.TIMEZONE)

    def _load_prompt(self, filename: str) -> str:
        from pathlib import Path
        path = Path(__file__).parent.parent / "prompts" / filename
        return path.read_text(encoding="utf-8") if path.exists() else ""

    async def _run_morning_brief(self):
        logger.info("[Scheduler] Running morning brief...")
        today = datetime.now(self.timezone).strftime("%A, %B %d")
        prompt = self._load_prompt("morning_brief.md")
        try:
            brief = await self.brain.one_shot(prompt, f"Today is {today}.")
            await send_message(f"☀️ Good morning Steven.\n\n{brief}")
            self.brain.clear_history()
            logger.info("[Scheduler] Morning brief sent.")
        except Exception as e:
            logger.error(f"[Scheduler] Morning brief failed: {e}")
            await send_message(f"Morning brief failed: {str(e)}")

    async def _run_eod_report(self):
        logger.info("[Scheduler] Running EOD report...")
        today = datetime.now(self.timezone).strftime("%A, %B %d")
        prompt = self._load_prompt("eod_report.md")
        try:
            report = await self.brain.one_shot(prompt, f"Today is {today}.")
            await send_message(f"📊 EOD Report — {today}\n\n{report}")
            logger.info("[Scheduler] EOD report sent.")
        except Exception as e:
            logger.error(f"[Scheduler] EOD report failed: {e}")
            await send_message(f"EOD report failed: {str(e)}")

    async def _run_hourly_checkin(self):
        now = datetime.now(self.timezone)
        hour = now.strftime("%I:%M %p").lstrip("0")
        logger.info(f"[Scheduler] Running hourly check-in ({hour})...")

        # Skip if it coincides with morning brief or EOD report windows
        hour_24 = now.strftime("%H:%M")
        if hour_24 in ("09:15", "16:30"):
            logger.info("[Scheduler] Skipping check-in — brief/report time.")
            return

        prompt = (
            f"It is {hour} CST. Send Steven a brief hourly check-in. "
            f"Format:\n"
            f"🕐 {hour} check-in\n\n"
            f"WORKING ON: [1-2 sentences on what you've been doing or are ready to do — "
            f"be specific, not generic. If nothing has been assigned yet, say so honestly.]\n\n"
            f"ANY TASKS FOR ME? Reply with anything you want me to work on right now, "
            f"or reply SKIP to skip this hour.\n\n"
            f"Keep it under 60 words total."
        )
        try:
            checkin = await self.brain.one_shot(prompt)
            await send_message(checkin)
            logger.info("[Scheduler] Hourly check-in sent.")
        except Exception as e:
            logger.error(f"[Scheduler] Hourly check-in failed: {e}")

    def _schedule_jobs(self):
        morning_time = config.MORNING_BRIEF_TIME   # e.g. "09:15"
        eod_time = config.EOD_REPORT_TIME           # e.g. "16:30"

        schedule.every().day.at(morning_time).do(
            lambda: asyncio.run(self._run_morning_brief())
        )
        schedule.every().day.at(eod_time).do(
            lambda: asyncio.run(self._run_eod_report())
        )
        schedule.every().hour.at(":00").do(
            lambda: asyncio.run(self._run_hourly_checkin())
        )

        logger.info(f"[Scheduler] Morning brief: {morning_time} CT")
        logger.info(f"[Scheduler] EOD report: {eod_time} CT")
        logger.info(f"[Scheduler] Hourly check-in: every hour at :00")

    def run_in_background(self):
        self._schedule_jobs()

        def loop():
            while True:
                schedule.run_pending()
                time.sleep(30)

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info("[Scheduler] Running in background thread.")
