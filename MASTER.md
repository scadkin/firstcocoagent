# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-27
**Status:** Phase 1 ✅ | Phase 1.5 ✅ | Phase 2 ✅ | Phase 3 ✅ | Phase 4 ⬜ Next

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phase 3 is verified working — Scout is live. Start Phase 4."**

---

## CURRENT STATUS — WHERE WE LEFT OFF

**Phase 3 is complete and verified.** Scout is running cleanly on Railway. It came online and sent Steven a Telegram message confirming it was live.

### Phase 4 is next — first task: `/push_code`
Give Scout the ability to commit files directly to GitHub using the `GITHUB_TOKEN` already in Railway env vars. This eliminates the manual GitHub upload step that caused so much friction during Phase 3 debugging. Steven has approved this approach.

### Phase 3 GAS bridge setup status
- `GAS_WEBHOOK_URL` — ⬜ Not yet set (Steven still needs to deploy Code.gs first)
- `GAS_SECRET_TOKEN` — ⬜ Not yet set
- GAS features (voice training, email drafting, calendar, slides) will not work until GAS is deployed
- See `docs/SETUP_PHASE3.md` for step-by-step instructions
- All other Phase 3 code is deployed and running

### CRITICAL RULE FOR ALL FUTURE CODING SESSIONS
**Before writing any code that calls an existing module, read that module first.**
Every Phase 3 crash was caused by calling methods that don't exist — hallucinated class names, wrong argument signatures, missing methods. The fix: always upload and read the actual source file before writing calls to it. This is non-negotiable going forward.

Specifically: if `main.py` will call `memory.something()`, read `memory_manager.py` first. If new code calls `research_queue.something()`, read `research_engine.py` first. Etc.

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
- **Drafts emails in Steven's voice via GAS bridge** (Phase 3 ✅ — pending GAS deploy)
- **Logs calls + creates pitch decks** (Phase 3 ✅ — pending GAS deploy)
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
| Google Apps Script | Bridge to work Gmail/Calendar/Slides — no IT approval needed | Free | ⬜ Code deployed, Railway vars not yet set |
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
| 3 | Gmail Voice Training + Email Drafting + Calendar + Slides (GAS bridge) | ✅ Complete |
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
│   ├── main.py                      ← Entry point. Scheduler poll loop. All tool dispatch.
│   ├── config.py                    ← All env vars. Includes GAS_WEBHOOK_URL, GAS_SECRET_TOKEN.
│   ├── claude_brain.py              ← Claude API + tool use + memory injection. 10 tools total.
│   ├── memory_manager.py            ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py                 ← CST-aware Scheduler class with check() method
│   ├── keywords.py                  ← Full title/keyword/role list (Phase 2)
│   └── voice_trainer.py             ← Analyzes sent emails via GAS → builds voice profile (Phase 3)
├── tools/
│   ├── __init__.py
│   ├── telegram_bot.py
│   ├── research_engine.py           ← Classes: ResearchJob, ResearchQueue. Singleton: research_queue.
│   ├── contact_extractor.py         ← Claude-powered contact extraction (Phase 2)
│   ├── sheets_writer.py             ← Module of functions (no class). write_contacts(), count_leads(), etc.
│   └── gas_bridge.py                ← GASBridge class: Gmail/Calendar/Slides (Phase 3)
├── gas/
│   └── Code.gs                      ← Google Apps Script — paste into script.google.com, deploy as Web App
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── email_draft.md               ← Email drafting prompt with voice profile injection
├── memory/
│   ├── preferences.md               ← Learned preferences. GitHub-committed on every write.
│   ├── context_summary.md           ← Daily compressed summaries. Never deleted.
│   └── voice_profile.md             ← Steven's writing style (populated by /train_voice)
└── docs/
    ├── SETUP.md
    ├── SETUP_PHASE2.md
    ├── SETUP_PHASE3.md
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
| GAS_WEBHOOK_URL | Web App URL from script.google.com deployment | ⬜ Set after GAS deploy |
| GAS_SECRET_TOKEN | Token you choose — must match Code.gs | ⬜ Set after GAS deploy |

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

### MemoryManager — actual method signatures
```python
memory_manager.load_preferences() -> str
memory_manager.load_recent_summary() -> str
memory_manager.build_memory_context() -> str
memory_manager.save_preference(entry: str)
memory_manager.append_to_summary(text: str)      # called at EOD with the report text
memory_manager.clear_preferences()
memory_manager._commit_to_github(filepath: str, content: str, message: str)
memory_manager.extract_memory_update(response: str) -> tuple  # static method
```
**No `.load()` method. No `.compress_history()` method.**

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

### Critical API notes
- `research_engine.py` has two classes: `ResearchJob` and `ResearchQueue`
- Never instantiate `ResearchJob` directly — `ResearchQueue` manages it internally
- Use the **singleton**: `from tools.research_engine import research_queue`
- `await research_queue.enqueue(district_name, state, progress_callback, completion_callback)`
- Properties (no parentheses): `research_queue.current_job`, `research_queue.queue_size`

### sheets_writer.py — it's a MODULE, not a class
```python
# CORRECT:
import tools.sheets_writer as sheets_writer
sheets_writer.write_contacts(contacts, state="")    # returns {leads_added, no_email_added, duplicates_skipped}
sheets_writer.count_leads()                          # returns {leads, no_email, total}
sheets_writer.get_master_sheet_url()                 # returns string URL
sheets_writer.log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)
sheets_writer.ensure_sheet_tabs_exist()

# WRONG (class doesn't exist):
from tools.sheets_writer import SheetsWriter        # ← will crash
```

### Google Sheets structure
- `Leads` tab — contacts with email (Outreach.io import format)
- `No Email` tab — contacts found but missing email
- `Research Log` tab — every job with date and counts

---

## 11. PHASE 3 — GMAIL + EMAIL DRAFTING + CALENDAR + SLIDES (✅ Complete)

### Why GAS bridge (not OAuth2)
Steven's work Google account (`steven@codecombat.com`) is on company-managed Google Workspace. IT would need to approve any third-party OAuth app — so Scout connects through a **Google Apps Script Web App** that runs inside Google as Steven, no IT approval required.

Personal account (Google Sheets) continues using the existing service account.

### Architecture
```
Scout (Railway) → HTTPS POST + secret token → GAS Web App → Gmail / Calendar / Slides
```

### How email drafting works end-to-end
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

### Scheduler — actual API
```python
# Scheduler takes NO arguments
scheduler = Scheduler()

# Only method: check() — returns a string event name or None
event = scheduler.check()  # returns "morning_brief", "eod_report", "checkin", or None

# WRONG — these don't exist:
Scheduler(morning_brief_fn=..., eod_report_fn=..., checkin_fn=...)  # ← will crash
scheduler.run(stop_event)  # ← will crash
```

The correct run loop (already in main.py) polls `check()` every 30 seconds:
```python
while not stop_event.is_set():
    event = scheduler.check()
    if event == "morning_brief":
        asyncio.create_task(send_morning_brief())
    elif event == "eod_report":
        asyncio.create_task(send_eod_report())
    elif event == "checkin":
        asyncio.create_task(send_checkin())
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=30)
    except asyncio.TimeoutError:
        pass
```

### GASBridge — actual method signatures
```python
gas = GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)
gas.ping() -> dict
gas.get_sent_emails(months_back=6, max_results=200) -> list[dict]
gas.create_draft(to, subject, body) -> dict
gas.get_calendar_events(days_ahead=7) -> list[dict]
gas.log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps) -> dict
gas.create_district_deck(district_name, state, contact_name, contact_title, student_count, key_pain_points, products_to_highlight, case_study) -> dict
```

### VoiceTrainer — actual method signatures
```python
trainer = VoiceTrainer(gas_bridge=gas, memory_manager=memory)
trainer.train(months_back=6, progress_callback=None) -> str
trainer.load_profile() -> Optional[str]
trainer.update_profile_from_feedback(feedback: str) -> bool
```

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

### GAS setup (still needed)
1. Go to script.google.com logged in as steven@codecombat.com
2. New project → paste `gas/Code.gs` → set SECRET_TOKEN to a string you make up
3. Deploy → New deployment → Web app → Execute as: Me → Anyone → Deploy → authorize → copy URL
4. Set `GAS_WEBHOOK_URL` + `GAS_SECRET_TOKEN` in Railway
5. In Telegram: `/ping_gas` → should return "GAS Bridge connected!"
6. `/train_voice` → 2-3 min → voice profile built
7. Test: "Draft a cold email to the CS Director at Austin ISD"

---

## 12. PHASE 4 — SCOUT PUSHES CODE TO GITHUB (⬜ Next)

### Goal
Give Scout a `/push_code` command (or natural language equivalent) so it can commit updated files directly to GitHub. This eliminates the manual upload step for every code change — the biggest workflow bottleneck in Phase 3 debugging.

### How it will work
- `GITHUB_TOKEN` is already in Railway env vars with `contents:write` scope
- New `push_code` Claude tool: accepts `filepath` + `content` + optional `commit_message`
- Calls GitHub Contents API (same approach already used by `memory_manager._commit_to_github()`)
- Claude can then write a fix and immediately commit it without Steven touching GitHub

### What to upload at the start of Phase 4
Before writing Phase 4 code, upload and read:
- `agent/main.py` (current version)
- `agent/config.py`
- `agent/claude_brain.py`
- `tools/` — any files Phase 4 will touch

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
| Scout pushes code in Phase 4 | Eliminates manual GitHub uploads after every code change |
| Read modules before writing code | All Phase 3 crashes were hallucinated method names — prevention requires reading source first |

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
| SyntaxError: global _pending_draft | global declaration appeared after assignment in same function scope | Moved global declaration to top of execute_tool() | ✅ Fixed |
| ImportError: ResearchEngine | Class doesn't exist — hallucinated name. Actual: ResearchJob, ResearchQueue | Rewrote to use research_queue singleton with correct enqueue() API | ✅ Fixed |
| ImportError: SheetsWriter | SheetsWriter class never existed — sheets_writer.py is a module of functions | Changed to `import tools.sheets_writer as sheets_writer`, replaced all class instantiations | ✅ Fixed |
| AttributeError: memory.load() | MemoryManager has no load() — __init__ handles setup automatically | Removed the call | ✅ Fixed |
| AttributeError: memory.compress_history() | Method doesn't exist — real method is append_to_summary(text) | Replaced with memory.append_to_summary(text) | ✅ Fixed |
| TypeError: Scheduler.__init__() unexpected kwargs | Scheduler() takes no arguments | Changed to Scheduler() | ✅ Fixed |
| AttributeError: scheduler.run() | Scheduler has no run() method, only check() | Rewrote run loop to poll scheduler.check() every 30s | ✅ Fixed |
| AttributeError: memory.commit_file() in voice_trainer | Method doesn't exist — real method is _commit_to_github(path, content, msg) | Fixed both calls in voice_trainer.py | ✅ Fixed |

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
| 2026-02-27 | SETUP_PHASE3.md written | Phase 3 |
| 2026-02-27 | 6 Phase 3 deployment crashes debugged and fixed (SheetsWriter, memory.load, compress_history, Scheduler args, scheduler.run, voice_trainer.commit_file) | Phase 3 |
| 2026-02-27 | Phase 3 verified — Scout online, Telegram message received | Phase 3 ✅ |
