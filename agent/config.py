"""
agent/config.py
Centralized environment variable access for Scout.
"""

import os

# Core
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
AGENT_NAME = os.environ.get("AGENT_NAME", "Scout")
TIMEZONE = os.environ.get("TIMEZONE", "America/Chicago")

# Schedule times (HH:MM in CST)
MORNING_BRIEF_TIME = os.environ.get("MORNING_BRIEF_TIME", "09:15")
EOD_REPORT_TIME = os.environ.get("EOD_REPORT_TIME", "16:30")
CHECKIN_START_HOUR = int(os.environ.get("CHECKIN_START_HOUR", 10))
CHECKIN_END_HOUR = int(os.environ.get("CHECKIN_END_HOUR", 16))

# Memory / GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

# Research (Phase 2)
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Google Apps Script Bridge (Phase 3)
# GAS_WEBHOOK_URL: the Web App URL from your Apps Script deployment
# GAS_SECRET_TOKEN: the token you set in Code.gs (must match exactly)
GAS_WEBHOOK_URL = os.environ.get("GAS_WEBHOOK_URL", "")
GAS_SECRET_TOKEN = os.environ.get("GAS_SECRET_TOKEN", "")

def gas_bridge_configured() -> bool:
    """Returns True if GAS bridge variables are set."""
    return bool(GAS_WEBHOOK_URL and GAS_SECRET_TOKEN)
