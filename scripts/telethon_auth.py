#!/usr/bin/env python3
"""One-time Telethon auth for Scout. Run in two phases:
  Phase 1: python telethon_auth.py send   → sends SMS code
  Phase 2: python telethon_auth.py verify <code> [2fa_password]
"""
import os, sys, asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = "+14058355067"
SESSION = str(Path(__file__).resolve().parent.parent / ".telethon_session")

async def send():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if await c.is_user_authorized():
        me = await c.get_me()
        print(f"Already authorized as {me.first_name} ({me.phone})")
        await c.disconnect()
        return
    r = await c.send_code_request(PHONE)
    print(f"Code sent. phone_code_hash={r.phone_code_hash}")
    Path(".telethon_code_hash").write_text(r.phone_code_hash)
    await c.disconnect()

async def verify(code: str, password: str | None):
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    phone_code_hash = Path(".telethon_code_hash").read_text().strip()
    try:
        await c.sign_in(PHONE, code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            print("2FA_REQUIRED")
            await c.disconnect()
            sys.exit(2)
        await c.sign_in(password=password)
    me = await c.get_me()
    print(f"Authorized as {me.first_name} {me.last_name or ''} ({me.phone})")
    Path(".telethon_code_hash").unlink(missing_ok=True)
    await c.disconnect()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "send"
    if cmd == "send":
        asyncio.run(send())
    elif cmd == "verify":
        code = sys.argv[2]
        pw = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(verify(code, pw))
    else:
        sys.exit(f"unknown cmd: {cmd}")
