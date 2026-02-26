"""
config.py — Central configuration for Scout.
All values load from environment variables. Never hardcode keys here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── CLAUDE ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-opus-4-5"  # Upgrade to opus for better reasoning if budget allows
CLAUDE_MAX_TOKENS = 2048

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

# ─── GOOGLE ──────────────────────────────────────────────────────────────────
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

# ─── FIREFLIES ────────────────────────────────────────────────────────────────
FIREFLIES_API_KEY = os.getenv("FIREFLIES_API_KEY")

# ─── SCHEDULE ────────────────────────────────────────────────────────────────
MORNING_BRIEF_TIME = os.getenv("MORNING_BRIEF_TIME", "07:30")
EOD_REPORT_TIME = os.getenv("EOD_REPORT_TIME", "17:30")
TIMEZONE = os.getenv("TIMEZONE", "America/Chicago")

# ─── AGENT IDENTITY ──────────────────────────────────────────────────────────
AGENT_NAME = os.getenv("AGENT_NAME", "Scout")

# ─── VALIDATION ──────────────────────────────────────────────────────────────
def validate():
    """Call at startup to catch missing config early."""
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in your values."
        )
    print(f"[Config] All required variables present. Agent: {AGENT_NAME}")
