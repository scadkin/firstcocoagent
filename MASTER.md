# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-27
**Status:** Phase 1 ✅ | Phase 1.5 ✅ | Phase 2 ✅ | Phase 3 ✅ | Phase 4 ⬜ Next

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phase 3 code is written but not yet verified working — Scout may still be crashing on Railway. Continue debugging and get Phase 3 stable, then we'll move to Phase 4."**

---

## CURRENT STATUS — WHERE WE LEFT OFF

Phase 3 code is fully written and committed to GitHub. Scout was crashing on Railway with two sequential bugs, both fixed. The latest `agent/main.py` has been uploaded to GitHub. We are waiting to see if Railway deploys cleanly.

### Phase 3 bugs fixed so far
| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| SyntaxError: global _pending_draft | `global` declaration appeared after assignment in same function — Python disallows this even across elif branches | Moved `global _pending_draft` to top of `execute_tool()` function | ✅ Fixed |
| ImportError: ResearchEngine | My new main.py invented a class name that doesn't exist. Actual classes are `ResearchJob` and `ResearchQueue`. The queue is used via its singleton `research_queue` and `enqueue()` method | Rewrote research tool block to import and use `research_queue` singleton with correct `enqueue()` / `current_job` / `queue_size` API | ✅ Fixed |

### What to do first in the new chat
1. Check if Scout is running on Railway (no crash loop in logs)
2. If still crashing — paste the new logs and debug
3. If running — test `/ping_gas` to verify GAS bridge connection
4. If GAS bridge works — run `/train_voice`
5. If everything passes — mark Phase 3 verified ✅ and update MASTER.md

### Phase 3 GAS bridge setup status
- `GAS_WEBHOOK_URL` — ⬜ Not yet set in Railway (Steven needs to deploy Code.gs first)
- `GAS_SECRET_TOKEN` — ⬜ Not yet set in Railway
- See `docs/SETUP_PHASE3.md` for the full step-by-step

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
- **Researches K-12 leads at scale** (Phase 2 ✅)
- **Drafts emails in Steven's voice via GAS bridge** (Phase 3 ⚠️ written, not yet verified)
- **Logs calls + creates pitch decks** (Phase 3 ⚠️ written, not yet verified)
- Processes Zoom call transcripts (Phase 5 ⬜)

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
| Serper API | Google search for lead research | ~$10/mo | ✅ Active |
| Google Sheets API | Lead list storage (personal account, service account) | Free | ✅ Active |
| Google Apps Script | Bridge to work Gmail/Calendar/Slides — no IT approval needed | Free | ⚠️ Code written, not yet deployed |
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
| 2 | Lead Research + Google Sheets | ✅ Complete |
| 3 | Gmail Voice Training + Email Drafting + Calendar + Slides (GAS bridge) | ⚠️ Written, debugging |
| 4 | Scout Pushes Code to GitHub + Email Sequences | ⬜ Next |
| 5 | Zoom Call Intelligence (Fireflies) | ⬜ Not started |
| 6 | At-Scale Research + Campaign Engine | ⬜ Not started |
| 7 | Video Clips + Social Content (Descript) | ⬜ Optional |

---

## 7. REPO STRUCTURE

```
firstcocoagent/
├── MASTER.md
├── Procfile                         ← "web: python -m agent.main"
├── requirements.txt
├── agent/
│   ├── __init__.py
│   ├── main.py                      ← Entry point. Phase 3 updated — uses research_queue singleton + GAS bridge tools.
│   ├── config.py                    ← All env vars. Phase 3 adds GAS_WEBHOOK_URL, GAS_SECRET_TOKEN.
│   ├── claude_brain.py              ← Claude API + tool use + memory injection. Phase 3 adds 7 new tools.
│   ├── memory_manager.py            ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py                 ← CST-aware tick loop (Scheduler class)
│   ├── keywords.py                  ← Full title/keyword/role list (Phase 2)
│   └── voice_trainer.py             ← Analyzes sent emails via GAS → builds voice profile (Phase 3)
├── tools/
│   ├── __init__.py
│   ├── telegram_bot.py
│   ├── research_engine.py           ← Classes: ResearchJob, ResearchQueue. Singleton: research_queue. (Phase 2)
│   ├── contact_extractor.py         ← Claude-powered contact extraction (Phase 2)
│   ├── sheets_writer.py             ← Google Sheets read/write/dedup (Phase 2)
│   └── gas_bridge.py                ← GAS bridge HTTP client: Gmail/Calendar/Slides (Phase 3)
├── gas/
│   └── Code.gs                      ← Google Apps Script — paste into script.google.com, deploy as Web App (Phase 3)
├── prompts/
│   ├── system.md                    ← Scout identity + research capabilities
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── email_draft.md               ← Email drafting prompt with voice profile injection (Phase 3)
├── memory/
│   ├── preferences.md               ← Learned preferences. GitHub-committed on every write.
│   ├── context_summary.md           ← Daily compressed summaries. Never deleted.
│   └── voice_profile.md             ← Steven's writing style — populated by /train_voice (Phase 3)
└── docs/
    ├── SETUP.md
    ├── SETUP_PHASE2.md
    ├── SETUP_PHASE3.md              ← GAS bridge setup: script.google.com → deploy → Railway vars → /ping_gas → /train_voice
    ├── CHANGELOG.md
    └── DECISIONS.md
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
| SERPER_API_KEY | (from serper.dev) | ✅ Set |
| GOOGLE_SHEETS_ID | (from Sheet URL) | ✅ Set |
| GOOGLE_SERVICE_ACCOUNT_JSON | (full JSON string, personal account) | ✅ Set |
| GAS_WEBHOOK_URL | Web App URL from script.google.com deployment | ⬜ Set after GAS setup |
| GAS_SECRET_TOKEN | Token you choose — must match Code.gs | ⬜ Set after GAS setup |

---

## 9. MEMORY SYSTEM (Phase 1.5 ✅)

**Two persistent files, both GitHub-committed on every write:**
- `memory/preferences.md` — every correction and preference. Never auto-cleared.
- `memory/context_summary.md` — EOD compression of each day's conversation. Grows indefinitely.

**Learning loop:**
1. Steven gives correction/feedback in Telegram
2. Claude appends `[MEMORY_UPDATE: one sentence]` to response
3. `claude_brain.py` strips tag, calls `memory_manager.save_preference()`
4. Entry appended to `preferences.md` with timestamp, committed to GitHub
5. Next session, loaded into every API call automatically

**Method name note:** `memory_manager.py` uses `load_recent_summary()` (not `load_context_summary()`).

---

## 10. PHASE 2 — LEAD RESEARCH + GOOGLE SHEETS (✅ Verified Working)

```
Steven: "Research CS contacts in Denver Public Schools"
→ Claude detects intent → triggers research_queue.enqueue()
→ ResearchQueue runs ResearchJob internally (10 layers)
→ Progress updates fire to Telegram
→ Contacts written to Google Sheets
→ Scout: "✅ Done. 14 contacts — 9 with emails, 5 name-only. [Sheet link]"
```

### Critical API notes (learned from bugs)
- `research_engine.py` has two classes: `ResearchJob` (the engine) and `ResearchQueue` (the manager)
- `ResearchQueue` creates `ResearchJob` instances internally — never instantiate `ResearchJob` directly from main.py
- Use the **singleton**: `from tools.research_engine import research_queue`
- Queue methods: `await research_queue.enqueue(district_name, state, progress_callback, completion_callback)`
- Queue properties (not methods — no parentheses): `research_queue.current_job`, `research_queue.queue_size`

### Google Sheets structure
- `Leads` tab — contacts with email (Outreach.io import format)
- `No Email` tab — contacts found but missing email
- `Research Log` tab — every job with date and counts

### Column headers (exact Outreach.io import format)
`First Name` | `Last Name` | `Title` | `Email` | `State` | `Account` | `Work Phone` | `District Name` | `Source URL` | `Email Confidence` | `Date Found`

### Available Scout commands
- `"Research [district name] [state]"` → triggers research job
- `"Check sheet status"` → lead counts + sheet link
- `"What's in the queue?"` → current job + queue depth

---

## 11. PHASE 3 — GMAIL VOICE TRAINING + EMAIL DRAFTING + CALENDAR + SLIDES (⚠️ Written, Not Yet Verified)

### Why GAS bridge (not OAuth2)
Steven's work Google account (`steven@codecombat.com`) is on a company-managed Google Workspace. IT would need to approve any third-party OAuth app — so instead, Scout connects through a **Google Apps Script Web App** that runs inside Google as Steven, with no IT approval required.

Personal account (Google Sheets) continues using the existing service account — that's unaffected.

### Architecture
```
Scout (Railway) → HTTPS POST + secret token → GAS Web App → Gmail / Calendar / Slides
```

### How it works end-to-end
```
Steven: "Draft a cold email to the CS Director at Austin ISD"
→ Claude fires draft_email tool
→ Scout pulls voice profile from memory/voice_profile.md
→ Scout calls Claude to write draft in Steven's style
→ Draft sent to Telegram for review
→ Steven: "looks good" → Scout calls save_draft_to_gmail tool
→ GAS bridge creates draft in Gmail Drafts folder
→ Steven opens Gmail, adds recipient email if needed, sends manually
```

### New files (Phase 3)
- `gas/Code.gs` — the GAS script, paste into script.google.com and deploy as Web App
- `tools/gas_bridge.py` — HTTP client that calls the GAS Web App
- `agent/voice_trainer.py` — fetches sent emails via GAS, analyzes with Claude, saves voice profile
- `memory/voice_profile.md` — Steven's writing style (populated by /train_voice)
- `prompts/email_draft.md` — drafting prompt with voice profile injected at runtime
- `docs/SETUP_PHASE3.md` — full setup walkthrough

### New Claude tools (Phase 3)
| Tool | Trigger |
|------|---------|
| `ping_gas_bridge` | `/ping_gas` — test connection |
| `train_voice` | `/train_voice` — analyze sent emails, build voice profile |
| `draft_email` | "draft a [type] email to [person] at [district]" |
| `save_draft_to_gmail` | "looks good" — saves pending draft to Gmail Drafts |
| `get_calendar` | "what's on my calendar" |
| `log_call` | "log a call with [name] at [district]" |
| `create_district_deck` | "make a deck for [district]" |

### GAS setup order (not yet done)
1. Go to script.google.com logged in as steven@codecombat.com
2. New project → paste `gas/Code.gs` → set SECRET_TOKEN to a string you make up
3. Deploy → New deployment → Web app → Execute as: Me → Anyone → Deploy → authorize → copy URL
4. Set `GAS_WEBHOOK_URL` + `GAS_SECRET_TOKEN` in Railway
5. In Telegram: `/ping_gas` → should return "GAS Bridge connected!"
6. `/train_voice` → 2-3 min → voice profile built
7. Test: "Draft a cold email to the CS Director at Austin ISD"

Full instructions: `docs/SETUP_PHASE3.md`

---

## 12. PHASE 4 PREVIEW — SCOUT PUSHES CODE TO GITHUB

The first item in Phase 4 is giving Scout a `/push_code` command so it can commit updated files directly to GitHub using the `GITHUB_TOKEN` already in Railway. This eliminates the manual GitHub upload step for every code change. Steven approved this approach in the current chat.

---

## 13. FULL TARGET TITLE & KEYWORD LIST

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

---

## 14. KEY DECISIONS

| Decision | Why |
|----------|-----|
| Telegram | Free, rich formatting, iPhone + laptop |
| Railway.app | $5/mo, git push deploys, persistent 24/7 |
| Python | Best library support for all planned tools |
| GitHub for memory | Free, survives Railway restarts, version-controlled |
| Queue research jobs | Better quality/depth vs. simultaneous |
| CST-aware tick scheduler | Railway runs UTC — tick-based avoids timezone bugs |
| Memory compression not deletion | Steven wants permanent learning and iteration |
| `[MEMORY_UPDATE]` tag | Clean, no extra API calls, reliable extraction |
| Claude tool use for research | Claude detects intent — no fragile keyword matching |
| Gmail Drafts only | Nothing sends without Steven's review |
| GAS bridge over OAuth2 | Work Google Workspace IT blocks third-party OAuth; GAS runs inside Google, no approval needed |
| Personal account for Sheets | Service account works fine for Sheets, no IT involvement |
| Work account for Gmail/Cal/Slides | GAS bridge runs as steven@codecombat.com with full access |
| `python -m agent.main` in Railway | Fixes ModuleNotFoundError for agent/tools packages |
| `research_queue` singleton | ResearchJob/Queue are tightly coupled; queue manages job lifecycle internally |
| `/train_voice` separate from boot | Expensive Claude API call — only run on demand |
| Voice profile in memory/ | GitHub-persisted, survives restarts, loaded into every draft prompt |
| Pending draft state in main.py | Enables approve/edit loop without re-drafting from scratch |
| Option B (Scout pushes code) planned for Phase 4 | Eliminates manual GitHub uploads after every code change |

---

## 15. BUG FIX LOG

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Check-ins all night | No time window | CHECKIN_START/END_HOUR guards | ✅ Fixed |
| Morning brief at 3:15am | Railway UTC ≠ CST | CST-aware tick loop | ✅ Fixed |
| Hallucinated activity | Prompts requested summary without real data | Rewrote prompts with honesty rules | ✅ Fixed |
| History wiped daily | clear_history() on schedule | EOD compression to memory instead | ✅ Fixed |
| updater.idle() crash | Method doesn't exist in PTB version | asyncio.Event() | ✅ Fixed |
| ModuleNotFoundError: agent | Railway ran python agent/main.py from wrong dir | Changed to python -m agent.main | ✅ Fixed |
| ImportError: Scheduler | Phase 1 scheduler.py had no Scheduler class | Rewrote scheduler.py with Scheduler class | ✅ Fixed |
| AttributeError: load_context_summary | Method named load_recent_summary in memory_manager | Updated claude_brain.py to match | ✅ Fixed |
| Google Sheets 403 PERMISSION_DENIED | Sheets API not enabled in Google Cloud project | Enabled via Cloud Console URL in logs | ✅ Fixed |
| SyntaxError: global _pending_draft | global declaration appeared after assignment in same function scope (even across elif branches) | Moved global declaration to top of execute_tool() | ✅ Fixed |
| ImportError: ResearchEngine | Class doesn't exist — Claude hallucinated the name. Actual classes: ResearchJob, ResearchQueue | Rewrote research block to use research_queue singleton with correct enqueue() API | ✅ Fixed |
| ImportError: SheetsWriter | SheetsWriter class never existed — sheets_writer.py is a module of functions | Changed to `import tools.sheets_writer as sheets_writer`, replaced all class instantiations with direct function calls | ✅ Fixed |
| AttributeError: memory.load() | MemoryManager has no load() — __init__ handles setup automatically | Removed the call | ✅ Fixed |
| AttributeError: memory.compress_history() | Method doesn't exist — real method is append_to_summary(text) | Replaced with memory.append_to_summary(text) | ✅ Fixed |
| TypeError: Scheduler.__init__() unexpected keyword args | Scheduler() takes no arguments | Changed to Scheduler() | ✅ Fixed |
| AttributeError: scheduler.run() | Scheduler has no run() method, only check() | Rewrote run loop to poll scheduler.check() every 30s via asyncio | ✅ Fixed |
| AttributeError: memory.commit_file() | Method doesn't exist — real method is _commit_to_github(path, content, msg) | Fixed both calls in voice_trainer.py | ✅ Fixed |

---

## 16. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | Phase 1 built and deployed — Scout live on Telegram | Phase 1 |
| 2026-02-26 | Bug fixes: timezone, check-in window, hallucination prevention | Phase 1.5 |
| 2026-02-26 | Persistent memory system + GitHub commit loop built and verified | Phase 1.5 |
| 2026-02-27 | Phase 2 built: research_engine, contact_extractor, sheets_writer, keywords | Phase 2 |
| 2026-02-27 | Phase 2 verified working — research fires, contacts in sheet | Phase 2 ✅ |
| 2026-02-27 | Phase 3 designed — GAS bridge approach chosen over OAuth2 (IT restriction) | Phase 3 |
| 2026-02-27 | Phase 3 built: Code.gs, gas_bridge.py, voice_trainer.py, email_draft.md, voice_profile.md | Phase 3 |
| 2026-02-27 | claude_brain.py: 7 new Phase 3 tools added | Phase 3 |
| 2026-02-27 | config.py: GAS_WEBHOOK_URL + GAS_SECRET_TOKEN added | Phase 3 |
| 2026-02-27 | SETUP_PHASE3.md written for GAS bridge approach | Phase 3 |
| 2026-02-27 | Fixed: SyntaxError — global _pending_draft moved to top of execute_tool() | Phase 3 |
| 2026-02-27 | Fixed: ImportError ResearchEngine — rewrote to use research_queue singleton correctly | Phase 3 |
| 2026-02-27 | main.py uploaded to GitHub — awaiting clean Railway deploy | Phase 3 ⚠️ |
