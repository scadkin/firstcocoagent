# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-28
**Status:** Phase 1 ✅ | Phase 1.5 ✅ | Phase 2 ✅ | Phase 3 ✅ | Phase 4 ✅ | Phase 4.5 ✅ | Phase 5 ⬜ Next

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phase 4.5 is verified working — Scout is live. Start Phase 5."**

**Files to upload at the start of the new chat (fetch from GitHub repo):**
- `MASTER.md` (this file)
- `agent/main.py`
- `agent/claude_brain.py`
- `tools/gas_bridge.py`
- `agent/voice_trainer.py`
- `agent/memory_manager.py`
- `agent/scheduler.py`

Uploading these ensures Claude reads actual method signatures before writing any code that calls them. This is mandatory — see CRITICAL RULE below.

---

## CURRENT STATUS — WHERE WE LEFT OFF

**Phase 4.5 is complete and deployed.** Phase 5 is fully designed (see Section 14) and ready to build.

### What was built in Phase 4.5:
- `gas/Code.gs` — rewritten: `getSentEmails` now paginates (`page_start`, `page_size`), each email returns `is_reply` (bool) + `incoming_context` (the message Steven received, stripped/capped at 1500 chars). Thread context bundled inline — no extra round-trips. `ping` handler now hardcodes `"steven@codecombat.com"`.
- `tools/gas_bridge.py` — added `get_sent_emails_page()` method for paginated batch fetching (returns full dict including `has_more`). Original `get_sent_emails()` preserved for backward compatibility.
- `agent/voice_trainer.py` — full rewrite: fetches up to 2,000 emails in batches of 200, prioritizes reply+context pairs (60% of sample), formats prompt with `[REPLY]` / `[COLD]` labels. Sample size 40→80, token budget 80K→120K chars, months_back default 6→24.
- `agent/main.py` — `/push_code` fetch-first workflow, immediate train_voice ack, `/grade_draft`, `/add_template` commands.

### Voice training results:
- `/train_voice` ran successfully: fetched 273 emails (242 replies with context, 31 cold), voice profile built and saved to `memory/voice_profile.md`
- GAS bridge is live: `/ping_gas` → `✅ GAS Bridge connected! Running as: steven@codecombat.com`

### CRITICAL RULE FOR ALL FUTURE CODING SESSIONS
**Before writing any code that calls an existing module, read that module first.**
Every crash in this project has been caused by hallucinated class names, wrong argument signatures, or missing methods.

Specifically:
- If code calls `memory.something()` → read `memory_manager.py` first
- If code calls `research_queue.something()` → read `research_engine.py` first
- If code calls `gas.something()` → read `gas_bridge.py` first
- If code calls `trainer.something()` → read `voice_trainer.py` first
- If code touches `main.py` → upload and read it before writing

### GAS deployment reminder (hard-won)
Every time Code.gs is edited, you MUST:
1. Replace the `SECRET_TOKEN` placeholder with the actual token from Railway
2. **New deployment** (Deploy → New deployment — NOT editing existing) → new URL
3. Update `GAS_WEBHOOK_URL` in Railway env vars with the new URL

### Telegram character limit — solved
`/push_code filepath` tells Scout to fetch the file from GitHub itself, ask Steven what changes to make in plain English, then make and push the edits. Steven never pastes file content through Telegram.

---

## 1. WHO THIS IS FOR

**Operator:** Steven (Senior Sales Rep, CodeCombat)
**Goal:** $3M in sales this year
**Email:** steven@codecombat.com
**CRM:** Salesforce (no API access)
**Email Sequencer:** Outreach.io (no API access — bulk CSV import only)
**Quote Tool:** PandaDoc (no API access)
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
- **Drafts emails in Steven's voice via GAS bridge** (Phase 3 ✅)
- **Logs calls + creates pitch decks** (Phase 3 ✅)
- **Pushes code to GitHub directly** (Phase 4 ✅)
- **Builds multi-step Outreach.io sequences** (Phase 4 ✅)
- **Voice profile from 273 paired emails with correction loop** (Phase 4.5 ✅)
- **Call Intelligence Suite** (Phase 5 ⬜ — fully designed, ready to build)

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
| GitHub (memory persistence) | Persistent memory + code storage | Free | ✅ Active |
| Serper API | Google search for lead research | ~$10/mo | ✅ Active |
| Google Sheets API | Lead list storage (personal account, service account) | Free | ✅ Active |
| Google Apps Script ("Scout Bridge") | Bridge to work Gmail/Calendar/Slides/Docs — no IT approval needed | Free | ✅ Live |
| Fireflies.ai | Zoom transcription + webhook | Free (800 min/mo) | ⬜ Phase 5 — not yet set up |
| Outreach.io | Email sequences | Existing plan — no API access | ✅ Active (CSV import only) |
| Salesforce | CRM | Existing plan — no API access | ✅ Active (manual only) |
| PandaDoc | Quote generation | Existing plan — no API access | ✅ Active (manual only) |

**Telegram Chat ID:** 8677984089
**Bot username:** @coco_scout_bot
**GAS Project Name:** "Scout Bridge" (at script.google.com, logged in as steven@codecombat.com)

---

## 6. BUILD PHASES

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Brain + Command Channel (Railway + Telegram + Claude API) | ✅ Complete |
| 1.5 | Bug Fixes + Persistent Memory System | ✅ Complete |
| 2 | Lead Research + Google Sheets | ✅ Complete |
| 3 | Gmail Voice Training + Email Drafting + Calendar + Slides (GAS bridge) | ✅ Complete |
| 4 | Scout Pushes Code to GitHub + Email Sequences | ✅ Complete |
| 4.5 | Voice Trainer Upgrade (pagination, paired context, correction loop) | ✅ Complete |
| 5 | Call Intelligence Suite (Fireflies + Pre-call Brief + Post-call Summary + Recap Email) | ⬜ Next — fully designed |
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
│   ├── claude_brain.py              ← Claude API + tool use + memory injection. 15 tools total.
│   ├── memory_manager.py            ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py                 ← CST-aware Scheduler class with check() method
│   ├── keywords.py                  ← Full title/keyword/role list (Phase 2)
│   └── voice_trainer.py             ← Paginated email fetch + paired context analysis (Phase 4.5)
├── tools/
│   ├── __init__.py
│   ├── telegram_bot.py
│   ├── research_engine.py           ← Classes: ResearchJob, ResearchQueue. Singleton: research_queue.
│   ├── contact_extractor.py         ← Claude-powered contact extraction (Phase 2)
│   ├── sheets_writer.py             ← Module of functions (no class). write_contacts(), count_leads(), etc.
│   ├── gas_bridge.py                ← GASBridge class: Gmail/Calendar/Slides (Phase 4.5 updated)
│   ├── github_pusher.py             ← push_file(), list_repo_files(), get_file_content() (Phase 4)
│   └── sequence_builder.py          ← build_sequence(), write_sequence_to_sheets(), format_for_telegram() (Phase 4)
├── gas/
│   └── Code.gs                      ← Google Apps Script — deployed at script.google.com as "Scout Bridge"
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── email_draft.md               ← Email drafting prompt with voice profile injection
├── memory/
│   ├── preferences.md               ← Learned preferences. GitHub-committed on every write.
│   ├── context_summary.md           ← Daily compressed summaries. Never deleted.
│   └── voice_profile.md             ← Steven's writing style — built from 273 paired emails (Phase 4.5)
└── docs/
    ├── SETUP.md
    ├── SETUP_PHASE2.md
    ├── SETUP_PHASE3.md
    ├── CHANGELOG.md
    └── DECISIONS.md
```

**Phase 5 will add:**
```
├── agent/
│   ├── call_processor.py            ← Phase 5: transcript → structured notes → summary → outputs
│   └── webhook_server.py            ← Phase 5: aiohttp server to receive Fireflies webhook POST
├── tools/
│   └── fireflies.py                 ← Phase 5: Fireflies GraphQL API client
└── docs/
    └── SETUP_PHASE5.md              ← Fireflies setup guide
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
| GAS_WEBHOOK_URL | ✅ Set (update every time Code.gs is redeployed) | ✅ Set |
| GAS_SECRET_TOKEN | ✅ Set (matches Code.gs) | ✅ Set |
| FIREFLIES_API_KEY | (from app.fireflies.ai → Account → API) | ⬜ Phase 5 |
| FIREFLIES_WEBHOOK_SECRET | (set in Fireflies webhook config, match in Railway) | ⬜ Phase 5 |

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
- `Sequences` tab — email sequence steps (added Phase 4)

---

## 11. PHASE 3 — GMAIL + EMAIL DRAFTING + CALENDAR + SLIDES (✅ Verified Live)

### Why GAS bridge (not OAuth2)
Steven's work Google account (`steven@codecombat.com`) is on company-managed Google Workspace. IT would need to approve any third-party OAuth app — so Scout connects through a **Google Apps Script Web App** that runs inside Google as Steven, no IT approval required.

Personal account (Google Sheets) continues using the existing service account.

### Architecture
```
Scout (Railway) → HTTPS POST + secret token → GAS Web App → Gmail / Calendar / Slides / Docs
```

### GAS deployment notes (hard-won)
- Project name: **"Scout Bridge"** at script.google.com
- Must deploy as: Execute as **Me**, Who has access **Anyone**
- Every code change requires a **New deployment** (not editing existing) → new URL → update `GAS_WEBHOOK_URL` in Railway
- `Session.getActiveUser().getEmail()` returns empty string for anonymous callers → hardcode `"steven@codecombat.com"` in ping handler
- `Session.getEffectiveUser().getEmail()` throws permission error — don't use it
- `SECRET_TOKEN` placeholder must be replaced with the actual token before deploying

### ping handler in Code.gs (correct version)
```javascript
case "ping":
  return jsonResponse({ success: true, message: "Scout Bridge is live", user: "steven@codecombat.com" });
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

### GASBridge — actual method signatures
```python
gas = GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)
gas.ping() -> dict
gas.get_sent_emails(months_back=6, max_results=200, page_start=0, page_size=200) -> list[dict]
gas.get_sent_emails_page(months_back=6, page_size=200, page_start=0) -> dict  # returns full response w/ has_more
gas.create_draft(to, subject, body) -> dict
gas.search_inbox(query, max_results=10) -> list[dict]
gas.get_calendar_events(days_ahead=7) -> list[dict]
gas.log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps) -> dict
gas.create_district_deck(district_name, state, contact_name, contact_title, student_count, key_pain_points, products_to_highlight, case_study) -> dict
```

**Phase 5 will add to GASBridge:**
```python
gas.create_google_doc(title, content, folder_id) -> dict   # returns {success, doc_id, url, title}
gas.search_inbox(query, max_results=10) -> list[dict]       # already exists — used for pre-call Gmail history
```

**Phase 5 will add to Code.gs:**
- `createGoogleDoc` action — creates a new Google Doc in a specified Drive folder

### VoiceTrainer — actual method signatures
```python
trainer = VoiceTrainer(gas_bridge=gas, memory_manager=memory)
trainer.train(months_back=24, progress_callback=None) -> str   # default now 24 months
trainer.load_profile() -> Optional[str]
trainer.update_profile_from_feedback(feedback: str) -> bool
```

---

## 12. PHASE 4 — SCOUT PUSHES CODE + EMAIL SEQUENCES (✅ Complete)

### github_pusher.py — method signatures
```python
import tools.github_pusher as github_pusher

github_pusher.push_file(filepath: str, content: str, commit_message: str = None) -> dict
# Returns: {success: bool, url: str, message: str}

github_pusher.list_repo_files(path: str = "") -> list[str]
# Returns sorted list of file paths in repo directory

github_pusher.get_file_content(filepath: str) -> str | None
# Returns decoded file content, or None if not found
```

### sequence_builder.py — method signatures
```python
import tools.sequence_builder as sequence_builder

sequence_builder.build_sequence(
    campaign_name: str,
    target_role: str,
    focus_product: str = "CodeCombat AI Suite",
    num_steps: int = 4,
    voice_profile: Optional[str] = None,
    additional_context: str = "",
) -> dict
# Returns: {success: bool, steps: list[dict], raw: str, error: str}
# Each step dict: {step, day, label, subject, body}

sequence_builder.write_sequence_to_sheets(campaign_name: str, steps: list[dict]) -> bool
sequence_builder.format_for_telegram(campaign_name: str, steps: list[dict]) -> str
```

### IMPORTANT: Lazy imports
Phase 4 modules (`github_pusher`, `sequence_builder`) are imported **inside** `execute_tool()`, not at the top of `main.py`. Scout boots cleanly even if files are temporarily missing. Don't move them to top-level imports. Phase 5 modules (`fireflies`, `call_processor`) must follow the same pattern.

### IMPORTANT: /push_code fetch-first workflow
`/push_code filepath` → Scout fetches file from GitHub, summarizes it, asks what changes Steven wants, makes edits, pushes. Steven never pastes file content through Telegram.

---

## 13. PHASE 4.5 — VOICE TRAINER UPGRADE (✅ Complete)

### Voice profile state
- Built from 273 emails (242 replies with paired context, 31 cold)
- Saved to `memory/voice_profile.md`, committed to GitHub
- Grows via `/grade_draft` corrections and `/add_template` additions

### New shorthand commands
| Command | What it does |
|---------|-------------|
| `/grade_draft` | Rate last draft 1-5, describe what's off. Scout updates voice_profile.md permanently. |
| `/add_template` | Paste a template/snippet/sequence. Scout analyzes + adds to voice profile "Templates" section. |

### Voice training philosophy
Correction loop > raw email volume. Priority order:
1. `/grade_draft` after every draft that sounds wrong — highest leverage
2. `/add_template` with your best actual templates — gold signal
3. `/train_voice` periodically as email history grows

---

## 14. PHASE 5 — CALL INTELLIGENCE SUITE (⬜ Next — Fully Designed)

### Overview
Phase 5 adds three integrated capabilities triggered around every Zoom call:
1. **Pre-call brief** — 10 min before the call, sent to Telegram + saved as Google Doc
2. **Post-call summary** — triggered by Fireflies webhook when call ends, sent to Telegram
3. **Recap email draft** — auto-drafted to Gmail Drafts after every call

### What Phase 5 does NOT include
- No Salesforce API integration (no access) — Salesforce updates remain manual
- No Outreach.io API integration (no access) — sequence adds remain manual via CSV
- No PandaDoc API integration (no access) — quote generation remains manual
- No general info email draft (not needed)
- No grants/funding email draft (not needed)
- No calendar event logging (the call is already on the calendar — no point logging it again)

### Pre-Call Brief — Trigger and Delivery
- **Trigger:** Scheduler checks Google Calendar every 30 seconds (already polling). When a Zoom meeting is found starting in 10 minutes, Scout fires the brief.
- **Zoom detection:** Look for "zoom.us" in calendar event location or description
- **Attendee filtering:** Exclude Steven (steven@codecombat.com) and anyone else with @codecombat.com email
- **Delivery:** Telegram message + new Google Doc created in a dedicated Drive folder

### Pre-Call Brief — Google Doc
- Created fresh for every call (never overwritten)
- Naming convention: `[Attendee Last Name(s)] - [Meeting Title] - [Date MM-DD-YYYY]`
- Saved to a dedicated Google Drive folder: "Scout Pre-Call Briefs" (create folder first, hardcode folder ID in config or env var)
- Created via new `createGoogleDoc` action in Code.gs → called via GASBridge

### Pre-Call Brief — What Scout Researches
For each non-CodeCombat attendee:
- Serper search: name + title + org + LinkedIn profile
- School/org website scrape: role confirmation, bio, background
- Any recent press mentions or social presence

For the district/org/company:
- Enrollment size, grade levels, district budget indicators
- Recent news (past 12 months): CS/STEM initiatives, grants received, technology purchases
- State DOE: relevant CS/STEM funding initiatives, requirements
- Any CodeCombat-relevant context (coding programs, makerspaces, esports, robotics)

From Gmail (via GAS bridge search_inbox):
- All email threads with attendee email addresses (past 12 months)
- Any Salesforce notification emails mentioning the contact or district

Selling potential estimate (Claude assessment):
- Based on district enrollment → estimated license count and deal size
- Based on budget signals found in research
- Based on email history: have they requested a quote? demo? pricing?
- Overall rating: Hot / Warm / Cold with reasoning

### Post-Call Summary — Trigger
- **Fireflies webhook** fires to Scout's Railway URL 2-3 minutes after call ends
- Scout receives the webhook POST, validates the secret, pulls full transcript via Fireflies API
- No manual trigger needed — fully automatic

### Webhook Server Architecture
Scout currently has no HTTP server — it's a Telegram polling loop. Phase 5 adds a lightweight **aiohttp web server** running in the same asyncio event loop alongside Telegram. Railway exposes a public port via the `PORT` environment variable.

```python
# webhook_server.py — listens on Railway's PORT
# POST /fireflies-webhook → validates secret → queues transcript processing
# GET /health → returns 200 (Railway health check)
```

The aiohttp server and Telegram polling both run under `asyncio.gather()` in `main()`.

### Post-Call Summary — What Claude Extracts from Transcript
**About the prospect/call:**
- School name(s), organization, district
- License count wanted/needed (any number mentioned)
- Grade levels they plan to use CodeCombat with
- Student devices (Chromebook, iPad, Windows, etc.)
- Implementation timeline (when they want to start)
- Budget (any number or signal, even vague)
- CodeCombat familiarity level (never heard of it / heard of it / used it / currently using it)
- Teacher coding comfort level
- Class setup (how many sections, students per class, how often they'd use it)
- Their vision for what they want to do with it
- Decision makers identified (who approves the purchase)
- Who is in charge of CS for the district

**Action items:**
- Unanswered questions (things raised but not resolved during the call)
- Clear next steps with owners and any dates mentioned
- Task list for Steven — prioritized and actionable
- Scout's suggestions — based on call content, what to emphasize next time, what to follow up on, any red flags or opportunities

### Post-Call Outputs
1. **Telegram message** — structured summary with all extracted info
2. **Recap email draft** — saved to Gmail Drafts via GAS bridge
   - Thanks them for their time
   - Brief recap of what was discussed
   - Clear next steps with expectations
   - Written in Steven's voice using voice profile
   - Subject: `Following up on our call — [District/Org Name]`
3. **Salesforce Update Block** — formatted text block sent to Telegram, ready to paste into Salesforce opportunity description/activity log (manual paste, but pre-written)
4. **Outreach.io row** — contact formatted and appended to Google Sheet (Leads or No Email tab) for bulk CSV import to Outreach.io sequences

### New Files to Build (Phase 5)

**`tools/fireflies.py`**
```python
# Fireflies GraphQL API client
class FirefliesClient:
    def __init__(self, api_key: str)
    def get_transcript(self, transcript_id: str) -> dict
    # Returns: {id, title, date, duration, attendees: [{name, email}], transcript: str, summary: str}
    def get_recent_transcripts(self, limit: int = 5) -> list[dict]
```

**`agent/call_processor.py`**
```python
# Transcript → structured notes → all outputs
class CallProcessor:
    def __init__(self, gas_bridge, memory_manager, fireflies_client)
    async def process_transcript(self, transcript_id: str, progress_callback=None) -> dict
    async def build_pre_call_brief(self, event: dict, attendees: list[dict]) -> str
    # event: calendar event dict from GASBridge.get_calendar_events()
    # attendees: filtered list (no @codecombat.com)
    # Returns: formatted brief text (also triggers Google Doc creation)
```

**`agent/webhook_server.py`**
```python
# aiohttp server for Fireflies webhook
async def handle_fireflies_webhook(request) -> web.Response
async def handle_health(request) -> web.Response
async def start_webhook_server(port: int, process_callback) -> None
```

### Updated Files (Phase 5)

**`agent/config.py`** — add:
```python
FIREFLIES_API_KEY = os.environ.get("FIREFLIES_API_KEY", "")
FIREFLIES_WEBHOOK_SECRET = os.environ.get("FIREFLIES_WEBHOOK_SECRET", "")
PRECALL_BRIEF_FOLDER_ID = os.environ.get("PRECALL_BRIEF_FOLDER_ID", "")  # Google Drive folder ID
```

**`gas/Code.gs`** — add `createGoogleDoc` action:
```javascript
case "createGoogleDoc":
  // Creates a new Google Doc in specified folder
  // params: {title, content, folder_id}
  // Returns: {success, doc_id, url, title}
```

**`agent/scheduler.py`** — add pre-call brief timing:
- On each `check()` call, also scan next 7 days of calendar events
- If a Zoom event starts in 9–11 minutes and brief hasn't been sent yet, return `"precall_brief"` event
- Track which event IDs have already had briefs sent (avoid duplicate fires)

**`agent/main.py`** — add:
- `asyncio.gather()` to run webhook server + Telegram loop together
- Handler for `"precall_brief"` scheduler event
- Execute tool handlers for `process_call_transcript` and `get_pre_call_brief`
- Lazy imports: `from tools.fireflies import FirefliesClient` and `from agent.call_processor import CallProcessor` inside execute_tool()
- `/brief [zoom_url or meeting_title]` command — manually trigger pre-call brief for a specific meeting
- `/recent_calls` command — list recent Fireflies transcripts

**`agent/claude_brain.py`** — add tools:
```python
{
    "name": "process_call_transcript",
    "description": "Process a Fireflies call transcript. Use when webhook fires or Steven sends /call.",
    "input_schema": {
        "transcript_id": str,  # Fireflies transcript ID
    }
}
{
    "name": "get_pre_call_brief",
    "description": "Generate a pre-call brief for an upcoming meeting. Use when Steven sends /brief.",
    "input_schema": {
        "meeting_title": str,   # optional — searches calendar if provided
        "attendee_emails": list  # optional — if Steven specifies
    }
}
```

### New Shorthand Commands (Phase 5)
| Command | What it does |
|---------|-------------|
| `/brief [meeting name]` | Manually trigger pre-call brief for a specific meeting |
| `/recent_calls` | List 5 most recent Fireflies transcripts |
| `/call [transcript_id or fireflies_url]` | Manually trigger post-call processing for a specific transcript |

### Fireflies Setup (Steven's steps — documented in SETUP_PHASE5.md)
1. Create free account at app.fireflies.ai
2. Connect Zoom (Settings → Integrations → Zoom)
3. Get API key: Account → API Key
4. Set up webhook: Settings → Webhooks → add Railway URL → `https://[your-railway-url]/fireflies-webhook`
5. Set webhook secret (any random string — must match `FIREFLIES_WEBHOOK_SECRET` in Railway)
6. Add `FIREFLIES_API_KEY` and `FIREFLIES_WEBHOOK_SECRET` to Railway env vars
7. Create "Scout Pre-Call Briefs" folder in Google Drive → copy folder ID → add as `PRECALL_BRIEF_FOLDER_ID` in Railway

### Railway env vars to add (Phase 5)
| Variable | Source |
|----------|--------|
| `FIREFLIES_API_KEY` | app.fireflies.ai → Account → API Key |
| `FIREFLIES_WEBHOOK_SECRET` | Your choice — set same value in Fireflies webhook config |
| `PRECALL_BRIEF_FOLDER_ID` | Google Drive folder ID from URL of "Scout Pre-Call Briefs" folder |

---

## 15. ALL CLAUDE TOOLS (15 current + 2 planned in Phase 5)

| Tool | Phase | Handler in main.py |
|------|-------|-------------------|
| `research_district` | 2 | ✅ |
| `get_sheet_status` | 2 | ✅ |
| `get_research_queue_status` | 2 | ✅ |
| `train_voice` | 3 | ✅ |
| `draft_email` | 3 | ✅ |
| `save_draft_to_gmail` | 3 | ✅ |
| `get_calendar` | 3 | ✅ |
| `log_call` | 3 | ✅ |
| `create_district_deck` | 3 | ✅ |
| `push_code` | 4 | ✅ |
| `list_repo_files` | 4 | ✅ |
| `build_sequence` | 4 | ✅ |
| `ping_gas_bridge` | 3 | ✅ |
| `grade_draft` | 4.5 | ✅ (via /grade_draft shorthand) |
| `add_template` | 4.5 | ✅ (via /add_template shorthand) |
| `process_call_transcript` | 5 | ⬜ |
| `get_pre_call_brief` | 5 | ⬜ |

---

## 16. SHORTHAND COMMANDS (handle_message in main.py)

| Command | Expands to |
|---------|-----------|
| `/ping_gas`, `ping gas`, `test gas` | ping the GAS bridge |
| `/train_voice`, `train voice`, `learn my style` | train voice model from Gmail history (24 months) |
| `/grade_draft`, `grade draft`, `rate that draft` | give feedback on last draft → updates voice profile |
| `/add_template [content]` | add template/snippet to voice profile |
| `/list_files`, `/ls`, `list files` | list all files in repo root |
| `/push_code [filepath]` | fetch file from GitHub, ask for changes, edit + push (never paste) |
| `/build_sequence [args]` | build email sequence |
| `looks good`, `save it`, `approved`, `use this` | (when pending draft exists) → save to Gmail |
| `add email: addr@district.org` | (when pending draft exists) → set recipient |
| `/brief [meeting name]` | manually trigger pre-call brief (Phase 5) |
| `/recent_calls` | list recent Fireflies transcripts (Phase 5) |
| `/call [transcript_id or url]` | manually trigger post-call processing (Phase 5) |

---

## 17. KEY DECISIONS

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
| No Salesforce/Outreach/PandaDoc API | No access available — keep those workflows manual for now |
| Fireflies webhook over polling | Automatic post-call processing, no manual trigger needed |
| aiohttp alongside Telegram loop | Scout has no HTTP server — aiohttp runs in same asyncio event loop |
| Pre-call brief as Google Doc | Steven can pull it up on second screen during the call |
| Fresh Google Doc per call | Archive of all briefs; naming = attendee(s) + date |
| No calendar event logging in Phase 5 | Call is already on the calendar — redundant and not asked for |
| Outreach.io contacts via Google Sheet | CSV row appended to existing sheet; Steven does periodic bulk import |
| Salesforce update as copy-paste block | No API, but Scout writes it pre-formatted so paste is instant |
| Lazy imports for Phase 5 modules | Same pattern as Phase 4 — Scout boots cleanly before files exist |

---

## 18. BUG FIX LOG

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
| Google Sheets 403 PERMISSION_DENIED | Sheets API not enabled in Google Cloud project | Enabled via Cloud Console | ✅ Fixed |
| SyntaxError: global _pending_draft | global declaration appeared after assignment | Moved global declaration to top of execute_tool() | ✅ Fixed |
| ImportError: ResearchEngine | Hallucinated class name. Actual: ResearchJob, ResearchQueue | Rewrote to use research_queue singleton | ✅ Fixed |
| ImportError: SheetsWriter | SheetsWriter class never existed — sheets_writer.py is functions | Changed to module import, replaced all instantiations | ✅ Fixed |
| AttributeError: memory.load() | MemoryManager has no load() | Removed the call | ✅ Fixed |
| AttributeError: memory.compress_history() | Method doesn't exist — real method is append_to_summary(text) | Replaced with correct method | ✅ Fixed |
| TypeError: Scheduler.__init__() unexpected kwargs | Scheduler() takes no arguments | Changed to Scheduler() | ✅ Fixed |
| AttributeError: scheduler.run() | Scheduler has no run() method, only check() | Rewrote run loop to poll check() every 30s | ✅ Fixed |
| AttributeError: memory.commit_file() in voice_trainer | Method doesn't exist — real method is _commit_to_github() | Fixed both calls in voice_trainer.py | ✅ Fixed |
| GAS bridge 403 on /ping_gas | Existing GAS deployment access settings not updating | Created new deployment (Deploy → New deployment) | ✅ Fixed |
| Claude API 400: tool_use ids without tool_result | Tool results not appended to conversation_history | Append tool_result content block after each tool execution | ✅ Fixed |
| Scout crash on boot: ModuleNotFoundError: tools.github_pusher | Phase 4 files imported at top-level before being uploaded | Moved Phase 4 imports inside execute_tool() as lazy imports | ✅ Fixed |
| GAS ping returns empty user string | Session.getActiveUser().getEmail() returns "" for anonymous | Hardcoded "steven@codecombat.com" in ping handler | ✅ Fixed |
| getEffectiveUser() permission error | Requires OAuth scope not available for anonymous web apps | Don't use getEffectiveUser() — hardcode email instead | ✅ Fixed |
| /train_voice no immediate response | Handler ran 3-5 min job before sending any Telegram message | Added immediate ack message before trainer.train() call | ✅ Fixed |
| /train_voice only analyzed 40 of 273 emails | Sample cap hit even when pool < target | Added check: if pool ≤ sample target, use all emails | ✅ Fixed |
| /train_voice only looked back 6 months | months_back default was 6 in main.py, overriding voice_trainer.py default | Changed default in main.py execute_tool handler to 24 | ✅ Fixed |
| /push_code fails for large files | Telegram 4,096-char limit silently truncates pasted file content | Rewrote /push_code to fetch-first: Scout reads file, asks for changes, edits + pushes | ✅ Fixed |
| Code.gs SECRET_TOKEN reverts to placeholder on paste | Steven pasted new Code.gs without replacing placeholder | Added prominent reminder in GAS deployment notes | ✅ Fixed |

---

## 19. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | Phase 1 built and deployed — Scout live on Telegram | Phase 1 |
| 2026-02-26 | Bug fixes: timezone, check-in window, hallucination prevention | Phase 1.5 |
| 2026-02-26 | Persistent memory system + GitHub commit loop built and verified | Phase 1.5 |
| 2026-02-27 | Phase 2 built: research_engine, contact_extractor, sheets_writer, keywords | Phase 2 |
| 2026-02-27 | Phase 2 verified working — research fires, contacts in sheet | Phase 2 ✅ |
| 2026-02-27 | Phase 3 designed — GAS bridge approach chosen over OAuth2 (IT restriction) | Phase 3 |
| 2026-02-27 | Phase 3 built: Code.gs, gas_bridge.py, voice_trainer.py, email_draft.md | Phase 3 |
| 2026-02-27 | 6 Phase 3 deployment crashes debugged and fixed | Phase 3 |
| 2026-02-27 | Phase 3 verified — Scout online, Telegram message received | Phase 3 ✅ |
| 2026-02-28 | Phase 4 built: github_pusher.py, sequence_builder.py, updated main.py + claude_brain.py | Phase 4 |
| 2026-02-28 | Bug fix: Claude API 400 — tool_result blocks not appended to conversation history | Phase 4 |
| 2026-02-28 | Bug fix: Scout boot crash — Phase 4 top-level imports before files uploaded → lazy imports | Phase 4 |
| 2026-02-28 | GAS bridge fully live: new deployment, fixed ping handler, /ping_gas working | Phase 3 ✅ |
| 2026-02-28 | /train_voice ran successfully — voice profile built from 40 emails | Phase 3 ✅ |
| 2026-02-28 | Phase 4 verified — Scout online, all tools registered | Phase 4 ✅ |
| 2026-02-28 | Phase 4.5 built: Code.gs pagination + inline thread context, gas_bridge.py paginated fetch, voice_trainer.py full rewrite | Phase 4.5 |
| 2026-02-28 | Bug fixes: GAS SECRET_TOKEN placeholder, /push_code Telegram truncation, /train_voice no ack, sample cap logic | Phase 4.5 |
| 2026-02-28 | Phase 4.5 verified — /train_voice fetched 273 emails with paired context, voice profile rebuilt | Phase 4.5 ✅ |
| 2026-02-28 | main.py: fetch-first /push_code, immediate train_voice ack, /grade_draft, /add_template | Phase 4.5 ✅ |
| 2026-02-28 | Phase 5 fully designed: Call Intelligence Suite architecture, all decisions documented in MASTER.md | Phase 5 design ✅ |

---

## 20. FULL TARGET TITLE & KEYWORD LIST

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
AP CSP, APCSP, AP CompSci, AP CompSci A, APCSP, AP CSA
