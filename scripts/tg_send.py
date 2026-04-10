#!/usr/bin/env python3
"""Send a message to a Telegram bot/user via Telethon.
Usage: python tg_send.py <target> <message>
       python tg_send.py @coco_scout_bot "/prospect_add Foo TX"
"""
import os, sys, asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = str(Path(__file__).resolve().parent.parent / ".telethon_session")

async def main(target: str, message: str):
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        sys.exit("Not authorized — run telethon_auth.py first")
    sent = await c.send_message(target, message)
    print(f"Sent id={sent.id} to={target} at {sent.date.isoformat()}")
    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
