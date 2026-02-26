# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-26
**Status:** Phase 1 — Deploy in progress (Telegram bot crash-fixing)
**GitHub Repo:** https://github.com/[YOUR_USERNAME]/firstcocoagent (private)

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. We are fixing a Railway deploy crash for Phase 1. Read the current status in Section 11 and continue from there."**

---

## 1. WHO THIS IS FOR

**Operator:** Steven (Senior Sales Rep, CodeCombat)
**Goal:** $3M in sales this year
**Email:** steven@codecombat.com
**Company:** CodeCombat

---

## 2. WHAT THIS AGENT IS

Always-on AI sales assistant named **Scout** that:
- Runs 24/7 on Railway.app (~$5/mo)
- Communicates via **Telegram** (@coco_scout_bot)
- Sends **morning brief** at 9:15am CT daily
- Sends **EOD report** at 4:30pm CT daily
- Sends **hourly check-in** every hour at :00 asking for tasks
- Researches K-12 leads at scale
- Drafts emails in Steven's voice
- Processes Zoom call transcripts

---

## 3. THE PRODUCT BEING SOLD

**CodeCombat K-12 CS + AI Suite** — 8 products:
1. CodeCombat Classroom — game-based CS (Python, JS, Lua), Grades 6-12
2. Ozaria — narrative RPG CS for middle school
3. CodeCombat Junior — block-based coding K-5
4. AI HackStack — hands-on AI literacy curriculum
5. AI Junior — AI curriculum K-8
6. CodeCombat AI League — Esports coding tournaments
7. CodeCombat Worlds on Roblox — CS learning in Roblox
8. AP CSP Course — full College Board AP CS Principles course

Standards: CSTA, ISTE, California CS Standards, NGSS. Turn-key teacher resources included.

---

## 4. TARGET PROSPECTS

**Tier 1 — Decision Makers:** CS/Tech/STEM/CTE Directors, Curriculum Directors, CAOs, Directors of EdTech, Superintendents, Principals

**Tier 2 — Influencers:** CS/Coding Teachers, AP CSP Teachers, STEM/Robotics/Esports Teachers, Instructional Technology Coaches, TOSA

**Tier 3 — High Value:** State DOE CS contacts, Regional ESC contacts, State CSTA leaders, Librarians with CS programs

**Other Markets:** After-school, libraries, homeschool co-ops, community ed, government youth programs

---

## 5. TECH STACK

| Tool | Purpose | Cost | Status |
|------|---------|------|--------|
| Claude API (claude-opus-4-5) | Agent brain | ~$15-25/mo | ✅ Key obtained |
| Railway.app | Always-on server | ~$5/mo | ✅ Account + repo connected |
| Telegram Bot (@coco_scout_bot) | Command channel | Free | ✅ Bot created, token obtained |
| Gmail API | Read style, write drafts | Free | ⬜ Phase 3 |
| Google Sheets API | Lead list storage | Free | ⬜ Phase 2 |
| Fireflies.ai | Zoom transcription | Free (800 min/mo) | ⬜ Phase 5 |
| Outreach.io | Email sequences | Existing plan | ✅ Active |
| Salesforce | CRM | Existing plan | ✅ Active |

**Steven's Telegram Chat ID:** 8677984089
**Bot username:** @coco_scout_bot

---

## 6. BUILD PHASES

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Brain + Command Channel (Railway + Telegram + Claude API) | 🔄 Deploying — fixing crash |
| 2 | Lead Research + Google Sheets | ⬜ Not started |
| 3 | Gmail Voice Training + Email Drafting | ⬜ Not started |
| 4 | Email Sequences + Outreach.io | ⬜ Not started |
| 5 | Zoom Call Intelligence (Fireflies) | ⬜ Not started |
| 6 | At-Scale Research + Campaign Engine | ⬜ Not started |
| 7 | Video Clips + Social Content (Descript) | ⬜ Optional |

---

## 7. REPO STRUCTURE (firstcocoagent)

```
firstcocoagent/
├── MASTER.md                  ← This file. Always read first.
├── agent/
│   ├── __init__.py            ← Required for Python imports
│   ├── main.py                ← Entry point. asyncio.run(main())
│   ├── config.py              ← Loads all env vars
│   ├── claude_brain.py        ← All Claude API calls, conversation history
│   └── scheduler.py           ← Morning brief + EOD report scheduling
├── tools/
│   ├── __init__.py            ← Required for Python imports
│   └── telegram_bot.py        ← Telegram send/receive, uses asyncio.Event to stay alive
├── prompts/
│   ├── system.md              ← Scout's full identity and instructions
│   ├── morning_brief.md       ← 7:30am brief template
│   └── eod_report.md          ← 5:30pm report template
├── docs/
│   ├── SETUP.md
│   ├── CHANGELOG.md
│   └── DECISIONS.md
├── requirements.txt
├── Procfile                   ← "worker: python -u agent/main.py"
└── .env.example
```

---

## 8. RAILWAY ENVIRONMENT VARIABLES

All set in Railway → service → Variables tab:

| Variable | Value |
|----------|-------|
| ANTHROPIC_API_KEY | (Claude API key — keep secret) |
| TELEGRAM_BOT_TOKEN | (Bot token from @BotFather — keep secret) |
| TELEGRAM_CHAT_ID | 8677984089 |
| MORNING_BRIEF_TIME | 09:15 |
| EOD_REPORT_TIME | 16:30 |
| TIMEZONE | America/Chicago |
| AGENT_NAME | Scout |

---

## 9. KEY DECISIONS

| Decision | Why |
|----------|-----|
| Telegram over SMS | Free, rich formatting, works on iPhone + laptop |
| Railway.app | $5/mo, git push to deploy, persistent 24/7 |
| Python | Best library support for all tools |
| Gmail Drafts only | Nothing sends without Steven reviewing |
| Outreach.io manual import | Company controls admin |
| GitHub as source of truth | Chats expire, code is permanent |
| asyncio.Event() to keep bot alive | updater.idle() doesn't exist in this PTB version |

---

## 10. CRASH HISTORY (what we fixed and why)

| Crash | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Missing env vars | Variables not added to Railway | Added all 7 variables in Railway dashboard |
| Chat not found | Bot can't message first — must receive message first | Removed startup message; user messages bot first |
| This event loop is already running | `run_polling()` creates its own loop, conflicting with `asyncio.run()` | Replaced with manual `initialize/start/start_polling` |
| 'Updater' has no attribute 'idle' | `idle()` doesn't exist in installed PTB version | Replaced with `asyncio.Event()` — never-resolving await |

---

## 11. CURRENT STATUS & NEXT STEP

**Where we are:** The bot connects to Telegram successfully (logs show `Application started` and `Bot polling. Waiting for messages...`) but then crashes immediately on `await self.app.updater.idle()` because that method doesn't exist.

**Fix applied:** Replaced `idle()` with `asyncio.Event()` in `telegram_bot.py`. This creates an event that never fires, keeping the coroutine alive forever without calling any nonexistent methods.

**What needs to happen:**
1. Upload new `tools/telegram_bot.py` to GitHub (one file change)
2. Railway auto-redeploys
3. Logs should end with `Bot polling. Waiting for messages...` and STAY THERE
4. Open Telegram, message @coco_scout_bot, get a response = Phase 1 complete

**The single line that changed:**
- OLD: `await self.app.updater.idle()`
- NEW: `stop_event = asyncio.Event()` then `await stop_event.wait()`

---

## 12. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | GitHub repo created: firstcocoagent | Phase 1 |
| 2026-02-26 | All Phase 1 code written: main.py, config.py, claude_brain.py, scheduler.py, telegram_bot.py, all prompts | Phase 1 |
| 2026-02-26 | Fixed missing __init__.py files, Procfile changed to worker | Phase 1 |
| 2026-02-26 | Fixed asyncio event loop conflict — replaced run_polling() with manual async start | Phase 1 |
| 2026-02-26 | Fixed updater.idle() — replaced with asyncio.Event() | Phase 1 |
| 2026-02-26 | Phase 1 complete. Scout live and responding on Telegram. | Phase 1 |
| 2026-02-26 | Changed brief times: 9:15am + 4:30pm CT. Added hourly check-in. | Phase 1 |
