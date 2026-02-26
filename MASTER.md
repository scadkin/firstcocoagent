# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-26
**Status:** Phase 1 ✅ Complete | Phase 1.5 ✅ Complete | Phase 2 ⬜ Next
**GitHub Repo:** https://github.com/scadkin/firstcocoagent

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phase 1 and 1.5 are complete and verified. Let's build Phase 2: Lead Research + Google Sheets. Read the full architecture in Section 10 and begin."**

---

## 1. WHO THIS IS FOR

**Operator:** Steven (Senior Sales Rep, CodeCombat)
**Goal:** $3M in sales this year
**Email:** steven@codecombat.com
**CRM:** Salesforce
**Email Sequencer:** Outreach.io (bulk CSV import → sequences)
**Email Client:** Gmail (1:1 replies)
**Timezone:** CST (America/Chicago)

---

## 2. WHAT SCOUT IS

Always-on AI sales assistant named **Scout** that:
- Runs 24/7 on Railway.app (~$5/mo)
- Communicates via **Telegram** (@coco_scout_bot)
- Sends **morning brief** at 9:15am CST daily
- Sends **EOD report** at 4:30pm CST daily
- Sends **hourly check-in** 10am–4pm CST only
- Has **persistent memory** — learns from corrections, commits to GitHub, never forgets
- Researches K-12 leads at scale (Phase 2 — next)
- Drafts emails in Steven's voice (Phase 3)
- Processes Zoom call transcripts (Phase 5)

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

**Tier 1 — Decision Makers:**
CS/Tech/STEM/CTE Directors & Coordinators, Curriculum Directors, CAOs, Directors of EdTech/Innovation/Digital Learning/Blended Learning, Superintendents, Principals, Title I Directors, Grant Managers/Writers

**Tier 2 — Influencers:**
CS/Coding/AP CSP/AP CSA Teachers, STEM/Robotics/Esports/Game Design/Web Dev Teachers, Instructional Technology Coaches, TOSA, Makerspace Coordinators, STEM Lab Coordinators, After-School Program Directors, Instructional Designers, Innovation Coaches

**Tier 3 — High-Value Network:**
State DOE CS Coordinators, Regional ESC CS/STEM/CTE Consultants, State CSTA Chapter Leaders, K-12 CS Program Managers (large districts), CSforAll/CS4All regional leads, Librarians with CS programs, Girls Who Code chapter leads

**Other Markets:**
After-school centers, public libraries, homeschool co-ops, community education, government youth programs

---

## 5. TECH STACK

| Tool | Purpose | Cost | Status |
|------|---------|------|--------|
| Claude API (claude-opus-4-5) | Agent brain | ~$15-25/mo | ✅ Active |
| Railway.app | Always-on server | ~$5/mo | ✅ Active |
| Telegram (@coco_scout_bot) | Command channel | Free | ✅ Active |
| GitHub (memory persistence) | Persistent memory storage | Free | ✅ Active |
| Serper API | Google search for lead research | ~$10/mo | ⬜ Phase 2 |
| Google Sheets API | Lead list storage | Free | ⬜ Phase 2 |
| Gmail API | Read style, write drafts | Free | ⬜ Phase 3 |
| Fireflies.ai | Zoom transcription | Free (800 min/mo) | ⬜ Phase 5 |
| Outreach.io | Email sequences | Existing plan | ✅ Active |
| Salesforce | CRM | Existing plan | ✅ Active |

**Telegram Chat ID:** 8677984089
**Bot username:** @coco_scout_bot

---

## 6. BUILD PHASES

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Brain + Command Channel (Railway + Telegram + Claude API) | ✅ Complete |
| 1.5 | Bug Fixes + Persistent Memory System | ✅ Complete |
| 2 | Lead Research + Google Sheets | ⬜ Next — architecture fully designed |
| 3 | Gmail Voice Training + Email Drafting | ⬜ Not started |
| 4 | Email Sequences + Outreach.io | ⬜ Not started |
| 5 | Zoom Call Intelligence (Fireflies) | ⬜ Not started |
| 6 | At-Scale Research + Campaign Engine | ⬜ Not started |
| 7 | Video Clips + Social Content (Descript) | ⬜ Optional |

---

## 7. REPO STRUCTURE

```
firstcocoagent/
├── MASTER.md
├── agent/
│   ├── __init__.py
│   ├── main.py                  ← Entry point. Wires memory → brain → scheduler → bot
│   ├── config.py                ← All env vars
│   ├── claude_brain.py          ← Claude API + memory injection + correction detection
│   ├── memory_manager.py        ← Persistent memory: read/write/GitHub commit
│   └── scheduler.py             ← CST-aware tick loop. Fixed timezone + check-in window.
├── tools/
│   ├── __init__.py
│   └── telegram_bot.py
├── prompts/
│   ├── system.md                ← Scout identity + memory/learning behavior
│   ├── morning_brief.md         ← Honest brief (no hallucination)
│   └── eod_report.md            ← Honest EOD (no hallucination)
├── memory/
│   ├── preferences.md           ← Learned preferences. GitHub-committed on every write.
│   └── context_summary.md       ← Daily compressed summaries. Never deleted.
├── docs/
│   ├── SETUP.md
│   ├── CHANGELOG.md
│   └── DECISIONS.md
├── requirements.txt
├── Procfile
└── .env.example
```

---

## 8. RAILWAY ENVIRONMENT VARIABLES

| Variable | Value | Status |
|----------|-------|--------|
| ANTHROPIC_API_KEY | (Claude API key) | ✅ Set |
| TELEGRAM_BOT_TOKEN | (Bot token) | ✅ Set |
| TELEGRAM_CHAT_ID | 8677984089 | ✅ Set |
| MORNING_BRIEF_TIME | 09:15 | ✅ Set |
| EOD_REPORT_TIME | 16:30 | ✅ Set |
| TIMEZONE | America/Chicago | ✅ Set |
| AGENT_NAME | Scout | ✅ Set |
| GITHUB_TOKEN | (fine-grained PAT, contents:write) | ✅ Set |
| GITHUB_REPO | scadkin/firstcocoagent | ✅ Set |
| CHECKIN_START_HOUR | 10 | ✅ Set |
| CHECKIN_END_HOUR | 16 | ✅ Set |
| SERPER_API_KEY | (from serper.dev) | ⬜ Phase 2 |
| GOOGLE_SHEETS_ID | (from Sheet URL) | ⬜ Phase 2 |
| GOOGLE_SERVICE_ACCOUNT_JSON | (full JSON string) | ⬜ Phase 2 |

---

## 9. MEMORY SYSTEM (Phase 1.5 — Verified Working)

**Two persistent files, both GitHub-committed on every write:**

- `memory/preferences.md` — every correction and preference. Never auto-cleared. Steven clears manually if needed.
- `memory/context_summary.md` — EOD compression of each day's conversation. Grows indefinitely.

**Learning loop:**
1. Steven gives correction/feedback in Telegram
2. Scout acknowledges, asks any clarifying questions, confirms once
3. Claude appends `[MEMORY_UPDATE: one sentence]` tag to response
4. `claude_brain.py` strips tag, calls `memory_manager.save_preference()`
5. Entry appended to `preferences.md` with timestamp, committed to GitHub
6. Next session, loaded into every API call automatically

**Verified:** preferences.md GitHub commit confirmed working in smoke test.

---

## 10. PHASE 2 ARCHITECTURE — FULLY DESIGNED, READY TO BUILD

### Trigger flow
```
Steven: "Research CS contacts in Denver Public Schools"
→ Claude detects intent via tool use → triggers research job
→ Scout: "🔍 Starting research on Denver Public Schools..."
→ 10-layer research engine runs in background
→ Progress update if unusually stuck or successful
→ Contacts written to Google Sheets (Leads + No Email tabs)
→ Scout: "✅ Done. 14 contacts — 9 with emails, 5 name-only. [Sheet link]"
→ Results injected into Scout's conversation memory
```

### Job queuing
Research jobs queue — one at a time for maximum depth and quality.
Scout confirms queue and gives ETA when a second job comes in while one is running.

### Google Sheets structure

**Master Sheet** (permanent, always available):
- `Leads` tab — contacts with at least one email
- `No Email` tab — contacts found but missing email (different outreach approach)
- `Research Log` tab — every job: district, date, counts, layers used

**On-demand sheets** — Scout creates a fresh sheet and sends the link when requested.

**Column headers** (exact Outreach.io import format):
`First Name` | `Last Name` | `Title` | `Email` | `State` | `Account` | `Work Phone` | `District Name` | `Source URL` | `Email Confidence` | `Date Found`

Note: `Account` = school name for school-level contacts, district name for district-level.

### The 10-Layer Research Engine

| Layer | Method | Description |
|-------|--------|-------------|
| 1 | Serper: direct title search | `"CS Teacher" "Austin ISD" email` |
| 2 | Serper: title variation sweep | Cycles ALL title/keyword variations — different phrasings yield different results |
| 3 | Serper: LinkedIn-targeted | `site:linkedin.com "CS Director" "Austin ISD"` — no account needed |
| 4 | Serper: district site deep search | `site:austinisd.org "computer science" OR "coding" OR "STEM"` |
| 5 | Serper: news + grants search | `"Austin ISD" "computer science" grant 2025` — reveals budget/priority signals |
| 6 | Direct website scrape | BeautifulSoup fetches district site, crawls staff dirs, dept pages, contact pages |
| 7 | Keyword deep crawl | All title/keyword variations searched across every page found on district site |
| 8 | Email pattern inference | Finds district email format, constructs likely addresses — flagged INFERRED |
| 9 | Claude extraction pass | All raw content → Claude extracts structured contacts using full target title list |
| 10 | Dedup + confidence scoring | Cross-references Sheet. Tags each contact: VERIFIED / LIKELY / INFERRED |

Scout's system prompt instructs it to always be researching and adopting new tools/techniques.

### New files to create in Phase 2

```
tools/
├── research_engine.py     ← All 10 research layers
├── contact_extractor.py   ← Claude parses raw HTML into structured contact records
└── sheets_writer.py       ← Google Sheets read/write/dedup

agent/
└── keywords.py            ← Full title/keyword/role list as Python constants
```

### Setup required before building Phase 2
Two new Railway variables needed (see SETUP.md for step-by-step):
- `SERPER_API_KEY` — sign up at serper.dev (~$10/mo)
- `GOOGLE_SERVICE_ACCOUNT_JSON` + `GOOGLE_SHEETS_ID` — Google Cloud Console (free)

---

## 11. FULL TARGET TITLE & KEYWORD LIST

### Key Titles (all variations)
Superintendent, Assistant Superintendent, Principal, Assistant Principal,
Director/Executive Director/Coordinator/Department Head/Teacher/Instructor of: Computer Science, CS,
Director/Executive Director/Coordinator/Department Head/Director of: CTE, Career & Technical Education,
Director/Executive Director/Coordinator/Department Head/Instructor/Teacher/Coach of: STEM, S.T.E.M., STEAM, S.T.E.A.M.,
Director/Executive Director of Technology, Educational Technology Director, EdTech Director,
Director of Instructional Technology, Learning Technology Director,
Instructional Technology Coordinator/Coach/Specialist, Educational Technology Specialist,
Digital Learning Coach, Curriculum Director/Coordinator/Specialist/Developer,
Director of Curriculum & Instruction, Instructional Coordinator, Chief Academic Officer,
Director/Executive Director of Elementary/Secondary Education,
Director of Innovation, Chief Innovation Officer, Director of Digital Learning, Director of Blended Learning,
K-12 CS Program Manager, STEM Program Manager,
Director of Federal Programs, Title I Director, Grant Writer, Grants Manager, Instructional Designer,
Coding/Programming Teacher/Instructor, Game Design/Dev/Development Teacher/Instructor,
Web Design/Dev/Development Teacher/Instructor,
AP CSP/AP CSA/AP Computer Science/AP CompSci Teacher/Instructor (all variations),
Esports/Robotics Teacher/Instructor/Coach, Technology/Computer Teacher/Instructor,
Engineering Teacher, TOSA, Teacher on Special Assignment, Librarian, Media Specialist,
Department Chair (paired with CS/Tech/STEM keywords),
Innovation Coach, Instructional Innovation Specialist,
Makerspace Coordinator/Facilitator, STEM Lab Coordinator, After-School Program Director

### Other Important Keywords
Girls Who Code, Makerspace, Maker Space, STEAM Lab, STEM Lab,
Cybersecurity, Networking, Technology, Tech, Digital Media, Digital Literacy, Esports,
Python, Java, JavaScript, C++, CSS, Lua, CoffeeScript, HTML,
AP CSP, APCSP, AP CompSci, AP CompSci A, APCSA, AP CSA

### Other Departments to Search
Educational/Instructional Services, Curriculum & Instruction,
College & Career Readiness, Advanced Academics,
CTE (related to CS/Technology/Computers)

---

## 12. KEY DECISIONS

| Decision | Why |
|----------|-----|
| Telegram | Free, rich formatting, iPhone + laptop |
| Railway.app | $5/mo, git push deploys, persistent 24/7 |
| Python | Best library support for all planned tools |
| GitHub for memory | Free, survives Railway restarts, version-controlled, readable |
| Queue research jobs | Better quality/depth vs. simultaneous |
| CST-aware tick scheduler | Railway runs UTC — tick-based avoids timezone bugs |
| Memory compression not deletion | Steven wants permanent learning and iteration |
| `[MEMORY_UPDATE]` tag | Clean, no extra API calls, reliable extraction |
| Claude tool use for research | Claude detects intent — no fragile keyword matching |
| Gmail Drafts only | Nothing sends without Steven's review |
| Outreach.io manual CSV import | Company controls admin access |

---

## 13. BUG FIX LOG

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Check-ins all night | No time window | CHECKIN_START/END_HOUR guards | ✅ Fixed |
| Morning brief at 3:15am | Railway UTC ≠ CST | CST-aware tick loop | ✅ Fixed |
| Hallucinated activity | Prompts requested summary without real data | Rewrote prompts with honesty rules | ✅ Fixed |
| History wiped daily | clear_history() on schedule | EOD compression to memory instead | ✅ Fixed |
| updater.idle() crash | Method doesn't exist in PTB version | asyncio.Event() | ✅ Fixed (Phase 1) |

---

## 14. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | All Phase 1 code written and deployed | Phase 1 |
| 2026-02-26 | Scout live on Telegram — Phase 1 complete | Phase 1 |
| 2026-02-26 | Bug fixes: timezone, check-in window, hallucination prevention | Phase 1.5 |
| 2026-02-26 | Persistent memory system built and deployed | Phase 1.5 |
| 2026-02-26 | Memory injection + correction detection implemented | Phase 1.5 |
| 2026-02-26 | EOD compresses history to memory instead of wiping | Phase 1.5 |
| 2026-02-26 | Smoke test passed — preferences.md GitHub commit verified | Phase 1.5 |
| 2026-02-26 | Phase 2 architecture fully designed and documented | Phase 2 prep |
