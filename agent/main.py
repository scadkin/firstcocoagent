"""
main.py — Scout entry point.
Starts the Telegram bot, scheduler, and keeps everything running 24/7 on Railway.

To run locally:  python agent/main.py
To deploy:       git push (Railway auto-deploys)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import config
from agent.claude_brain import ScoutBrain
from agent.scheduler import ScoutScheduler
from tools.telegram_bot import ScoutBot, send_message

# ─── LOGGING ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ─── STARTUP ─────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 50)
    logger.info("  SCOUT — CodeCombat Sales Agent")
    logger.info("  Starting up...")
    logger.info("=" * 50)

    # 1. Validate all required config is present
    try:
        config.validate()
    except EnvironmentError as e:
        logger.error(f"[Startup] Config error: {e}")
        sys.exit(1)

    # 2. Initialize Claude brain
    brain = ScoutBrain()
    logger.info("[Startup] Claude brain initialized.")

    # 3. Start scheduler in background (morning brief, EOD report)
    scheduler = ScoutScheduler(brain)
    scheduler.run_in_background()
    logger.info("[Startup] Scheduler running in background.")

    # 4. Create the Telegram bot with Claude as its handler
    async def handle_message(user_message: str) -> str:
        """Bridge between Telegram and Claude."""
        return await brain.chat(user_message)

    bot = ScoutBot(claude_handler=handle_message)

    # 5. Notify Steven that Scout is online
    async def send_startup_message():
        await send_message(
            f"Scout is online and ready.\n\n"
            f"Morning brief: {config.MORNING_BRIEF_TIME}\n"
            f"EOD report: {config.EOD_REPORT_TIME}\n"
            f"Timezone: {config.TIMEZONE}\n\n"
            f"Send me a task or type /help to see what I can do."
        )

    asyncio.get_event_loop().run_until_complete(send_startup_message())
    logger.info("[Startup] Startup notification sent to Telegram.")

    # 6. Run the bot (this blocks — bot stays alive until Railway restarts it)
    logger.info("[Startup] Bot running. Listening for messages...")
    bot.run()


if __name__ == "__main__":
    main()

