#!/usr/bin/env python3
"""Read the N most recent messages from a Telegram target."""
import os, sys, asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = str(Path(__file__).resolve().parent.parent / ".telethon_session")

async def main(target: str, n: int):
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    async for msg in c.iter_messages(target, limit=n):
        ts = msg.date.isoformat()
        who = "BOT" if msg.out is False else "ME "
        text = (msg.text or msg.message or "").replace("\n", " | ")[:500]
        print(f"{ts}  {who}  id={msg.id}  {text}")
    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5))
