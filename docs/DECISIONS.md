# DECISIONS.md

Key architectural decisions and the reasoning behind them.
This file exists so future Claude sessions (and future you) understand *why* things were built the way they were.

---

## 2026-02-25

**Decision: Telegram over SMS**
SMS via Twilio costs money per message and only supports plain text. Telegram is free, supports rich formatting (bold, tables, inline buttons), works identically on iPhone and laptop, and has a first-class bot API. Tap-to-approve buttons for plan approvals are a Telegram feature that doesn't exist in SMS.

**Decision: Railway.app for hosting**
Originally considered Make.com scheduled triggers as the "always-on" solution. This was wrong — Make.com runs jobs on a schedule but isn't a persistent server. Railway.app at $5/mo gives a real always-on Python process that can respond to messages in real-time, run overnight jobs, and maintain state between calls. One git push deploys. No DevOps knowledge required.

**Decision: Python for all agent code**
Best library ecosystem for this stack: python-telegram-bot, anthropic, google-api-python-client, gspread. All mature, well-documented, and actively maintained.

**Decision: Gmail Drafts only (no auto-send)**
Trust is built incrementally. Starting with agent writing drafts that Steven reviews lets Steven build confidence in the agent's voice before enabling any autonomous sending. This can be changed later once the writing quality is proven.

**Decision: Outreach.io manual import (no API)**
Steven's company controls the Outreach.io admin account. Rather than fight this, agent drafts sequences in a formatted document that can be copy-pasted directly into Outreach.io. Functionally equivalent for the use case.

**Decision: Two-speed research (bulk + deep)**
Bulk enrichment (500–2,000+/night) builds pipeline volume fast. Deep personalization (50–100/batch) reserves quality research for the highest-value targets. Trying to deep-research thousands of contacts would be too slow and too expensive. The two-speed model gives both scale and quality where it matters.

**Decision: GitHub as source of truth**
Claude chats have context limits and don't persist. The repo is permanent. Every file we build gets committed. When a chat fills up, a new chat reads the repo and picks up where we left off. MASTER.md is the "memory file" that gives any new Claude session full context in seconds.
