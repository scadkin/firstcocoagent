"""
main.py — Scout entry point.
Compatible with Python 3.13. No startup message (avoids Chat not found error).
Message Scout first in Telegram, then it will respond.
"""

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    # 1. Validate config
    from agent.config import validate, MORNING_BRIEF_TIME, EOD_REPORT_TIME, TIMEZONE, CLAUDE_MODEL
    try:
        validate()
    except EnvironmentError as e:
        logger.error(f"CONFIG ERROR: {e}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("  SCOUT — CodeCombat Sales Agent")
    logger.info(f"  Model: {CLAUDE_MODEL}")
    logger.info(f"  Brief: {MORNING_BRIEF_TIME} | EOD: {EOD_REPORT_TIME} | TZ: {TIMEZONE}")
    logger.info("=" * 50)

    # 2. Import everything
    try:
        from agent.claude_brain import ScoutBrain
        from agent.scheduler import ScoutScheduler
        from tools.telegram_bot import ScoutBot
    except ImportError as e:
        logger.error(f"IMPORT ERROR: {e}")
        sys.exit(1)

    # 3. Initialize brain
    brain = ScoutBrain()
    logger.info("Claude brain ready.")

    # 4. Start scheduler
    scheduler = ScoutScheduler(brain)
    scheduler.run_in_background()
    logger.info("Scheduler running.")

    # 5. Message handler
    async def handle_message(user_message: str) -> str:
        return await brain.chat(user_message)

    # 6. Run bot — this blocks forever (that is correct)
    logger.info("Starting Telegram bot polling. Message @coco_scout_bot to begin.")
    bot = ScoutBot(claude_handler=handle_message)
    bot.run()


if __name__ == "__main__":
    asyncio.run(main())
