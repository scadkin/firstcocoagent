"""
config.py — Central configuration for Scout.
All values load from environment variables. Never hardcode keys here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── CLAUDE ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-5")
CLAUDE_MAX_TOKENS = 2048

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

# ─── GOOGLE ──────────────────────────────────────────────────────────────────
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

# ─── GITHUB (memory persistence) ─────────────────────────────────────────────
# Fine-grained personal access token with contents:write on firstcocoagent
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "scadkin/firstcocoagent")

# ─── RESEARCH (Phase 2) ───────────────────────────────────────────────────────
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# ─── FIREFLIES ────────────────────────────────────────────────────────────────
FIREFLIES_API_KEY = os.getenv("FIREFLIES_API_KEY")

# ─── SCHEDULE ────────────────────────────────────────────────────────────────
MORNING_BRIEF_TIME = os.getenv("MORNING_BRIEF_TIME", "09:15")
EOD_REPORT_TIME = os.getenv("EOD_REPORT_TIME", "16:30")
TIMEZONE = os.getenv("TIMEZONE", "America/Chicago")

# Hourly check-in window (CST). No check-ins outside these hours.
CHECKIN_START_HOUR = int(os.getenv("CHECKIN_START_HOUR", "10"))   # 10am CST
CHECKIN_END_HOUR = int(os.getenv("CHECKIN_END_HOUR", "16"))       # 4pm CST (last at 4:00pm)

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

    # Warn about optional but important vars
    warnings = []
    if not GITHUB_TOKEN:
        warnings.append("GITHUB_TOKEN not set — memory will not persist across Railway restarts")
    if not SERPER_API_KEY:
        warnings.append("SERPER_API_KEY not set — Phase 2 research will be limited")

    for w in warnings:
        print(f"[Config] WARNING: {w}")

    print(f"[Config] All required variables present. Agent: {AGENT_NAME}")
