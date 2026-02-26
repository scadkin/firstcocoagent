"""
scheduler.py — Runs Scout's scheduled daily jobs.
Morning brief at 7:30am, EOD report at 5:30pm (configurable in .env).
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
    """Manages all timed/scheduled tasks for Scout."""

    def __init__(self, brain):
        """
        brain: ScoutBrain instance — used to generate scheduled reports.
        """
        self.brain = brain
        self.timezone = pytz.timezone(config.TIMEZONE)

    def _get_morning_brief_prompt(self) -> str:
        """Load and return the morning brief prompt."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "prompts" / "morning_brief.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Generate a concise morning brief for Steven covering today's priorities, pending approvals, and one tactical insight."

    def _get_eod_prompt(self) -> str:
        """Load and return the EOD report prompt."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "prompts" / "eod_report.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Generate a concise end-of-day report for Steven covering what was accomplished, pipeline stats, and priorities for tomorrow."

    async def _run_morning_brief(self):
        """Generate and send the morning brief."""
        logger.info("[Scheduler] Running morning brief...")
        today = datetime.now(self.timezone).strftime("%A, %B %d")
        context = f"Today is {today}."
        try:
            brief = await self.brain.one_shot(self._get_morning_brief_prompt(), context)
            await send_message(f"☀️ *Good morning, Steven.*\n\n{brief}")
            # Clear history at start of each day for a fresh session
            self.brain.clear_history()
            logger.info("[Scheduler] Morning brief sent.")
        except Exception as e:
            logger.error(f"[Scheduler] Morning brief failed: {e}")
            await send_message(f"Morning brief failed to generate. Error: {str(e)}")

    async def _run_eod_report(self):
        """Generate and send the EOD report."""
        logger.info("[Scheduler] Running EOD report...")
        today = datetime.now(self.timezone).strftime("%A, %B %d")
        context = f"Today is {today}. Generate the end-of-day report."
        try:
            report = await self.brain.one_shot(self._get_eod_prompt(), context)
            await send_message(f"📊 *EOD Report — {today}*\n\n{report}")
            logger.info("[Scheduler] EOD report sent.")
        except Exception as e:
            logger.error(f"[Scheduler] EOD report failed: {e}")
            await send_message(f"EOD report failed to generate. Error: {str(e)}")

    def _schedule_jobs(self):
        """Set up all scheduled jobs."""
        morning_time = config.MORNING_BRIEF_TIME  # e.g. "07:30"
        eod_time = config.EOD_REPORT_TIME          # e.g. "17:30"

        schedule.every().day.at(morning_time).do(
            lambda: asyncio.run(self._run_morning_brief())
        )
        schedule.every().day.at(eod_time).do(
            lambda: asyncio.run(self._run_eod_report())
        )

        logger.info(f"[Scheduler] Morning brief scheduled at {morning_time} {config.TIMEZONE}")
        logger.info(f"[Scheduler] EOD report scheduled at {eod_time} {config.TIMEZONE}")

    def run_in_background(self):
        """Start the scheduler in a background thread so it does not block the bot."""
        self._schedule_jobs()

        def loop():
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info("[Scheduler] Running in background thread.")
