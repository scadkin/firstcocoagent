"""
telegram_bot.py — All Telegram send/receive logic for Scout.
Handles incoming messages, sends responses, manages approval flows.
"""

import logging
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ParseMode
from agent import config

logger = logging.getLogger(__name__)


# ─── SEND HELPERS ────────────────────────────────────────────────────────────

async def send_message(text: str, parse_mode: str = None) -> None:
    """Send a message to Steven's Telegram chat."""
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    # Split long messages (Telegram limit is 4096 chars)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=chunk,
            parse_mode=parse_mode
        )


async def send_approval_request(plan_name: str, description: str, details: list,
                                 expected_outcome: str, time_estimate: str,
                                 needs_from_steven: str = "Nothing — I have what I need.") -> None:
    """Send a formatted approval request to Steven."""
    details_text = "\n".join(f"  • {d}" for d in details)
    message = (
        f"📋 *PLAN: {plan_name}*\n"
        f"{description}\n\n"
        f"*Details:*\n{details_text}\n\n"
        f"*Expected outcome:* {expected_outcome}\n"
        f"*Time to complete:* {time_estimate}\n"
        f"*What I need from you:* {needs_from_steven}\n\n"
        f"✅ Reply *YES* to approve\n"
        f"✏️ Reply *EDIT* followed by your changes\n"
        f"❌ Reply *NO* to cancel"
    )
    await send_message(message, parse_mode=ParseMode.MARKDOWN)


# ─── MESSAGE HANDLER ─────────────────────────────────────────────────────────

class ScoutBot:
    """Main bot class. Handles all incoming messages from Steven."""

    def __init__(self, claude_handler):
        """
        claude_handler: async function(user_message: str) -> str
        Called whenever Steven sends a message. Returns Scout's response.
        """
        self.claude_handler = claude_handler
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self):
        # Security: only respond to Steven's chat ID
        steven_filter = filters.Chat(chat_id=config.TELEGRAM_CHAT_ID)

        self.app.add_handler(CommandHandler("start", self._handle_start, filters=steven_filter))
        self.app.add_handler(CommandHandler("status", self._handle_status, filters=steven_filter))
        self.app.add_handler(CommandHandler("help", self._handle_help, filters=steven_filter))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & steven_filter,
            self._handle_message
        ))

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Scout online. Ready to work.\n\n"
            "Send me any task and I will get on it. "
            "Type /help to see what I can do."
        )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "All systems running.\n"
            f"Morning brief: {config.MORNING_BRIEF_TIME}\n"
            f"EOD report: {config.EOD_REPORT_TIME}\n"
            f"Timezone: {config.TIMEZONE}"
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "*Scout — What I Can Do*\n\n"
            "*Research:*\n"
            "• Find CS leads in [state or district]\n"
            "• Research [district name] for contacts\n"
            "• Find contact info for [person name]\n\n"
            "*Email:*\n"
            "• Draft a cold email to [role]\n"
            "• Write a follow-up for [scenario]\n"
            "• Build a sequence for [avatar]\n\n"
            "*Planning:*\n"
            "• Create a prospecting plan for [state]\n"
            "• What should I focus on today?\n\n"
            "*Commands:*\n"
            "/start — Wake me up\n"
            "/status — Check system status\n"
            "/help — Show this menu\n\n"
            "Or just talk to me naturally — I will figure out what you need."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route every message from Steven through Claude and reply."""
        user_message = update.message.text
        logger.info(f"[Telegram] Received: {user_message[:80]}...")

        # Show typing indicator while processing
        await context.bot.send_chat_action(
            chat_id=config.TELEGRAM_CHAT_ID,
            action="typing"
        )

        try:
            response = await self.claude_handler(user_message)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"[Telegram] Error handling message: {e}")
            await update.message.reply_text(
                "Something went wrong on my end. Check Railway logs. "
                "I am still running — try again."
            )

    def run(self):
        """Start the bot in polling mode. Blocks until stopped."""
        logger.info("[Telegram] Bot starting in polling mode...")
        self.app.run_polling(drop_pending_updates=True)
