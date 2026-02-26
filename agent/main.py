"""
main.py — Scout entry point. Python 3.13 compatible async entry.

CHANGES FROM PHASE 1:
  - MemoryManager initialized first and injected into both Brain and Scheduler
  - Memory is loaded at startup so Scout wakes up with full context
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
    from agent.config import (
        validate, MORNING_BRIEF_TIME, EOD_REPORT_TIME,
        TIMEZONE, CLAUDE_MODEL, CHECKIN_START_HOUR, CHECKIN_END_HOUR
    )
    try:
        validate()
    except EnvironmentError as e:
        logger.error(f"CONFIG ERROR: {e}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("  SCOUT — CodeCombat Sales Agent")
    logger.info(f"  Model: {CLAUDE_MODEL}")
    logger.info(f"  Brief: {MORNING_BRIEF_TIME} | EOD: {EOD_REPORT_TIME} | TZ: {TIMEZONE}")
    logger.info(f"  Check-ins: {CHECKIN_START_HOUR}:00–{CHECKIN_END_HOUR}:00 CST")
    logger.info("=" * 50)

    try:
        from agent.memory_manager import MemoryManager
        from agent.claude_brain import ScoutBrain
        from agent.scheduler import ScoutScheduler
        from tools.telegram_bot import ScoutBot
    except ImportError as e:
        logger.error(f"IMPORT ERROR: {e}")
        sys.exit(1)

    # Memory loads first — brain and scheduler both need it
    memory = MemoryManager()
    logger.info("[Main] Memory manager ready.")

    brain = ScoutBrain(memory_manager=memory)
    logger.info("[Main] Claude brain ready.")

    scheduler = ScoutScheduler(brain=brain, memory_manager=memory)
    scheduler.run_in_background()
    logger.info("[Main] Scheduler running.")

    async def handle_message(user_message: str) -> str:
        return await brain.chat(user_message)

    logger.info("[Main] Starting bot. Message @coco_scout_bot to begin.")
    bot = ScoutBot(claude_handler=handle_message)
    await bot.run_async()


if __name__ == "__main__":
    asyncio.run(main())
