"""
telegram_bot.py — All Telegram send/receive logic for Scout.
Uses asyncio.Event to keep alive instead of updater.idle() which doesn't exist.
"""

import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from agent import config

logger = logging.getLogger(__name__)


async def send_message(text: str) -> None:
    """Send a message to Steven's Telegram chat."""
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    async with bot:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=chunk)


class ScoutBot:
    def __init__(self, claude_handler):
        self.claude_handler = claude_handler
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self):
        steven_filter = filters.Chat(chat_id=config.TELEGRAM_CHAT_ID)
        self.app.add_handler(CommandHandler("start", self._start, filters=steven_filter))
        self.app.add_handler(CommandHandler("status", self._status, filters=steven_filter))
        self.app.add_handler(CommandHandler("help", self._help, filters=steven_filter))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & steven_filter,
            self._message
        ))

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Scout online. Send me a task or type /help to see what I can do."
        )

    async def _status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"All systems running.\n"
            f"Morning brief: {config.MORNING_BRIEF_TIME}\n"
            f"EOD report: {config.EOD_REPORT_TIME}\n"
            f"Timezone: {config.TIMEZONE}"
        )

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Scout — What I Can Do\n\n"
            "Research:\n"
            "  Find CS leads in [state or district]\n"
            "  Research [district name] for contacts\n\n"
            "Email:\n"
            "  Draft a cold email to [role]\n"
            "  Write a follow-up for [scenario]\n\n"
            "Commands: /start  /status  /help\n\n"
            "Or just talk to me naturally."
        )

    async def _message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text
        logger.info(f"[Telegram] Received: {user_message[:80]}")
        await context.bot.send_chat_action(chat_id=config.TELEGRAM_CHAT_ID, action="typing")
        try:
            response = await self.claude_handler(user_message)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"[Telegram] Handler error: {e}")
            await update.message.reply_text("Something went wrong. Check Railway logs.")

    async def run_async(self):
        """Run the bot using low-level async — no event loop conflicts."""
        logger.info("[Telegram] Bot starting in async polling mode...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("[Telegram] Bot polling. Waiting for messages...")
        # Keep running forever using an asyncio Event (never set = runs until killed)
        stop_event = asyncio.Event()
        await stop_event.wait()
