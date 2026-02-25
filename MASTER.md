# MASTER.md — CodeCombat Sales Agent
**Last Updated:** 2026-02-25
**Status:** Pre-build — architecture finalized, repo initialized

---

## 1. WHO THIS IS FOR

**Operator:** Steven (Senior Sales Rep, CodeCombat)
**Goal:** $3M in sales this year. Needs to generate thousands of K-12 leads/month.
**Email:** steven@codecombat.com
**Company:** CodeCombat

---

## 2. WHAT THIS AGENT IS

An always-on AI sales assistant that:
- Runs 24/7 on Railway.app (cloud server, ~$5/mo)
- Communicates with Steven via **Telegram** (iPhone + laptop)
- Sends a **morning brief** each day with plans, tasks, questions for approval
- Sends an **EOD report** each evening with what was accomplished
- Researches K-12 leads at scale (bulk: 500–2,000+/night; deep: 50–100/batch)
- Drafts emails and sequences in Steven's voice
- Processes Zoom call transcripts into summaries, tasks, follow-up drafts
- Learns and improves continuously based on feedback and results

---

## 3. THE PRODUCT BEING SOLD

**CodeCombat K-12 CS + AI Suite** — 8 products:
1. CodeCombat Classroom — game-based CS curriculum (Python, JS, Lua)
2. Ozaria — narrative RPG CS curriculum for middle school
3. CodeCombat Junior — block-based coding for K-5
4. AI HackStack — AI literacy and hands-on AI curriculum
5. AI Junior — AI curriculum for younger students
6. CodeCombat AI League — Esports tournaments and leagues
7. CodeCombat Worlds on Roblox — CS learning inside Roblox
8. AP CSP Course — full AP Computer Science Principles course

Standards-aligned: CSTA, ISTE, California CS Standards, NGSS.
Turn-key teacher resources: lesson plans, slides, quizzes, unplugged activities, outcomes reports.

---

## 4. TARGET PROSPECTS

### Primary Decision Makers
- CS / Technology / STEM / STEAM / CTE Directors, Coordinators, Department Heads
- Curriculum Directors, Instructional Coordinators, Chief Academic Officers
- Directors of Technology / EdTech / Instructional Technology
- Superintendents (especially smaller districts)
- Principals (school-level buys)

### Teachers & Influencers
- CS, Coding, Programming Teachers
- AP CSP / AP CSA Teachers
- STEM / STEAM / Robotics / Esports Teachers
- Game Design, Web Dev, Digital Media Teachers
- Technology Teachers, Instructional Technology Coaches
- TOSA (Teacher on Special Assignment)

### Other High-Value
- State DOE CS contacts
- Regional / Educational Service Center CS contacts
- State CSTA Chapter leaders
- Librarians / Media Specialists with CS programs
- Girls Who Code chapter leads

### Markets Beyond K-12 Schools
- After-school centers
- Libraries
- Homeschool co-ops
- Community ed programs
- Government youth programs

---

## 5. TECH STACK

| Tool | Purpose | Cost | Status |
|------|---------|------|--------|
| Claude API (claude-sonnet) | Agent brain | ~$15–25/mo | Not yet set up |
| Railway.app | Always-on cloud server | ~$5/mo | Not yet set up |
| Telegram Bot | Command channel (iPhone + laptop) | Free | Not yet set up |
| Make.com | Automation glue | Free tier | Not yet set up |
| Gmail API | Read style, write drafts | Free | Not yet set up |
| Google Sheets API | Lead list storage | Free | Not yet set up |
| Fireflies.ai | Zoom transcription | Free (800 min/mo) | Not yet set up |
| Outreach.io | Email sequences (manual import) | Existing plan | Active |
| Salesforce | CRM | Existing plan | Active |
| Descript | Video clips (optional Phase 7) | $24/mo | Not yet — optional |

**Estimated monthly cost (Phases 1–6):** $20–39/mo
**With Descript:** $44–63/mo

---

## 6. BUILD PHASES

| Phase | Title | Status | Cost Added |
|-------|-------|--------|-----------|
| 1 | Brain + Command Channel (Railway + Telegram + Claude API) | ⬜ Not started | $20–30/mo |
| 2 | Lead Research + Google Sheets | ⬜ Not started | $0 |
| 3 | Gmail Voice Training + Email Drafting | ⬜ Not started | $0 |
| 4 | Email Sequences + Outreach.io | ⬜ Not started | $0 |
| 5 | Zoom Call Intelligence (Fireflies) | ⬜ Not started | $0 |
| 6 | At-Scale Research + Campaign Engine | ⬜ Not started | $0 |
| 7 | Video Clips + Social Content (Descript) | ⬜ Optional | $24/mo |

---

## 7. REPO STRUCTURE

```
codecombat-agent/
│
├── MASTER.md                  ← This file. Always read first.
│
├── agent/
│   ├── main.py                ← Entry point. Starts Telegram bot, schedules jobs.
│   └── config.py              ← API keys, settings, feature flags (loaded from env)
│
├── prompts/
│   ├── system.md              ← Master system prompt (Steven's context, products, targets)
│   ├── morning_brief.md       ← Prompt for daily morning brief generation
│   ├── eod_report.md          ← Prompt for end-of-day report generation
│   ├── email_drafter.md       ← Prompt for drafting emails in Steven's voice
│   ├── sequence_writer.md     ← Prompt for writing Outreach.io sequences
│   ├── lead_researcher.md     ← Prompt for bulk and deep lead research
│   └── call_debrief.md        ← Prompt for processing Zoom transcripts
│
├── jobs/
│   ├── morning_brief.py       ← Scheduled job: runs at 7:30am daily
│   ├── eod_report.py          ← Scheduled job: runs at 5:30pm daily
│   ├── lead_research.py       ← On-demand + overnight bulk research job
│   ├── call_processor.py      ← Triggered by Fireflies webhook after each call
│   └── email_queue.py         ← Manages Gmail draft queue and send approvals
│
├── tools/
│   ├── telegram_bot.py        ← Telegram send/receive, approval flows
│   ├── gmail_tool.py          ← Gmail read (style learning) + write drafts
│   ├── sheets_tool.py         ← Google Sheets read/write for lead lists
│   ├── web_search.py          ← Web research wrapper
│   └── fireflies_tool.py      ← Fireflies API: fetch transcripts
│
├── data/
│   ├── style_guide.md         ← Auto-generated: Steven's writing style (from Gmail analysis)
│   ├── sequences/             ← Saved email sequences per avatar/scenario
│   ├── leads/                 ← Local cache of lead research outputs
│   └── call_notes/            ← Saved call debriefs
│
├── docs/
│   ├── SETUP.md               ← Step-by-step setup instructions for every tool
│   ├── CHANGELOG.md           ← Log of every change made to the agent
│   └── DECISIONS.md           ← Why we made key architectural decisions
│
├── requirements.txt           ← Python dependencies
├── Procfile                   ← Railway deployment config
├── .env.example               ← Template for environment variables (never commit .env)
└── .gitignore                 ← Excludes .env, __pycache__, data caches
```

---

## 8. KEY DECISIONS & RATIONALE

| Decision | Why |
|----------|-----|
| Telegram over SMS | Free, rich formatting, tap-to-approve buttons, works on iPhone + laptop |
| Railway.app for hosting | $5/mo, one git push to deploy, persistent 24/7, supports scheduled jobs |
| Python for agent code | Best library support for Telegram bots, Claude API, Gmail, Sheets |
| Gmail Drafts (not auto-send) | Nothing sends without Steven reviewing — safety first, trust built over time |
| Outreach.io manual import | Company controls admin — agent drafts, Steven pastes in |
| Bulk + Deep research modes | Bulk for pipeline volume, deep for personalization on hottest targets |
| GitHub as source of truth | Repo is the memory. Claude chats come and go. Code is permanent. |

---

## 9. LIMITATIONS (HONEST)

| Limitation | Workaround |
|-----------|------------|
| LinkedIn automation banned | Research-only. Agent finds info, Steven does outreach manually |
| Outreach.io no API access | Agent drafts sequences, Steven pastes into Outreach.io |
| Fireflies bot visible on calls | Named "Notes" — or manually upload recordings after call |
| Bulk enrichment data gaps | Agent flags confidence level (verified vs. inferred) on every contact |

---

## 10. HOW TO RESUME IN A NEW CLAUDE CHAT

When this chat hits its limit or you start a new session:

1. Open a new chat in this Claude Project
2. Say: **"Read MASTER.md and all project files, then let's continue building the CodeCombat Sales Agent. We left off at [PHASE / TASK]."**
3. Claude will read the full context from the project files and pick up exactly where you left off.

**Always update MASTER.md when:**
- A phase is completed (update the status table in Section 6)
- A new decision is made (add to Section 8)
- A new file is created (add to Section 7)
- Something important changes (update wherever relevant)

---

## 11. WHAT'S NEXT

**Immediate next step:** Build Phase 1
- [ ] Create GitHub repo and push this structure
- [ ] Set up Railway.app account
- [ ] Create Telegram bot via @BotFather
- [ ] Get Claude API key from console.anthropic.com
- [ ] Write `agent/main.py` — the entry point
- [ ] Write `prompts/system.md` — Steven's full context as the master system prompt
- [ ] Deploy to Railway and confirm Telegram connection works
- [ ] Test: send a message, get a response

---

## 12. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, MASTER.md created, architecture finalized | Pre-build |
