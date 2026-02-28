# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-28
**Status:** Phase 1 ✅ | Phase 1.5 ✅ | Phase 2 ✅ | Phase 3 ✅ | Phase 4 ✅ | Phase 4.5 ⬜ Next

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phase 4 is verified working — Scout is live. Start Phase 4.5."**

---

## CURRENT STATUS — WHERE WE LEFT OFF

**Phase 4 is complete and verified.** Scout is running on Railway with all Phase 4 files uploaded:
- `agent/main.py` — updated (tool_result history bug fixed, lazy imports, Phase 4 handlers)
- `agent/claude_brain.py` — updated (3 new Phase 4 tools: push_code, list_repo_files, build_sequence)
- `tools/github_pusher.py` — new (GitHub Contents API wrapper)
- `tools/sequence_builder.py` — new (multi-step Outreach.io sequence generator)

**Phase 3 GAS bridge is NOW fully live:**
- `GAS_WEBHOOK_URL` — ✅ Set (new deployment URL after redeploy)
- `GAS_SECRET_TOKEN` — ✅ Set
- `/ping_gas` → `✅ GAS Bridge connected! Running as: steven@codecombat.com`
- `/train_voice` → ✅ Ran successfully — voice profile built from 40 emails

### Phase 4.5 is next — Voice Trainer Upgrade
The `/train_voice` command currently pulls 173 emails but only analyzes 40 (hard cap in `voice_trainer.py`). Steven wants **1,000–2,000 emails with full thread context** (the incoming email + Steven's reply together). This is the most impactful quality improvement available — the richer the voice profile, the better every future email draft.

See Section 12 for full Phase 4.5 spec.

### CRITICAL RULE FOR ALL FUTURE CODING SESSIONS
**Before writing any code that calls an existing module, read that module first.**
Every crash in this project has been caused by hallucinated class names, wrong argument signatures, or missing methods. The fix: always upload and read the actual source file before writing calls to it.

Specifically:
- If code calls `memory.something()` → read `memory_manager.py` first
- If code calls `research_queue.something()` → read `research_engine.py` first
- If code calls `gas.something()` → read `gas_bridge.py` first
- If code calls `trainer.something()` → read `voice_trainer.py` first
- If code touches `main.py` → upload and read it before writing

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
- **Drafts emails in Steven's voice via GAS bridge** (Phase 3 ✅)
- **Logs calls + creates pitch decks** (Phase 3 ✅)
- **Pushes code to GitHub directly** (Phase 4 ✅)
- **Builds multi-step Outreach.io sequences** (Phase 4 ✅)
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
| GitHub (memory persistence) | Persistent memory + code storage | Free | ✅ Active |
| Serper API | Google search for lead research | ~$10/mo | ✅ Active |
| Google Sheets API | Lead list storage (personal account, service account) | Free | ✅ Active |
| Google Apps Script ("Scout Bridge") | Bridge to work Gmail/Calendar/Slides — no IT approval needed | Free | ✅ Live |
| Fireflies.ai | Zoom transcription | Free (800 min/mo) | ⬜ Phase 5 |
| Outreach.io | Email sequences | Existing plan | ✅ Active |
| Salesforce | CRM | Existing plan | ✅ Active |

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
| 4.5 | Voice Trainer Upgrade (1000-2000 emails with thread context) | ⬜ Next |
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
│   ├── claude_brain.py              ← Claude API + tool use + memory injection. 13 tools total.
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
│   ├── gas_bridge.py                ← GASBridge class: Gmail/Calendar/Slides (Phase 3)
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
| GAS_WEBHOOK_URL | ✅ Set (new URL from latest Scout Bridge deployment) | ✅ Set |
| GAS_SECRET_TOKEN | ✅ Set (matches Code.gs) | ✅ Set |

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
Scout (Railway) → HTTPS POST + secret token → GAS Web App → Gmail / Calendar / Slides
```

### GAS deployment notes (hard-won)
- Project name: **"Scout Bridge"** at script.google.com
- Must deploy as: Execute as **Me**, Who has access **Anyone**
- Every code change requires a **New deployment** (not editing existing) → new URL → update `GAS_WEBHOOK_URL` in Railway
- `Session.getActiveUser().getEmail()` returns empty string for anonymous callers → use hardcoded `"steven@codecombat.com"` in ping handler
- `Session.getEffectiveUser().getEmail()` throws permission error — don't use it

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

### Phase 3 tools (all in claude_brain.py TOOLS list)
| Tool | Trigger |
|------|---------|
| `ping_gas_bridge` | `/ping_gas` — test connection |
| `train_voice` | `/train_voice` — analyze sent emails, build voice profile |
| `draft_email` | "draft a [type] email to [person] at [district]" |
| `save_draft_to_gmail` | "looks good" — saves pending draft to Gmail Drafts |
| `get_calendar` | "what's on my calendar" |
| `log_call` | "log a call with [name] at [district]" |
| `create_district_deck` | "make a deck for [district]" |

---

## 12. PHASE 4 — SCOUT PUSHES CODE + EMAIL SEQUENCES (✅ Complete)

### github_pusher.py — method signatures
```python
import tools.github_pusher as github_pusher

github_pusher.push_file(filepath: str, content: str, commit_message: str = None) -> dict
# Returns: {success: bool, url: str, message: str}
# - Creates file if new, updates if exists (handles SHA automatically)
# - filepath is repo-relative: e.g. "agent/main.py", "tools/github_pusher.py"

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
# Default day offsets: [0, 3, 7, 14]

sequence_builder.write_sequence_to_sheets(campaign_name: str, steps: list[dict]) -> bool
# Appends to "Sequences" tab in Google Sheet. Returns True on success.

sequence_builder.format_for_telegram(campaign_name: str, steps: list[dict]) -> str
# Returns formatted string for Telegram display
```

### Phase 4 tools
| Tool | Trigger |
|------|---------|
| `push_code` | "push this to GitHub", "commit this fix", `/push_code filepath` |
| `list_repo_files` | "list files in the repo", "show me what's in tools/", `/list_files` |
| `build_sequence` | "build a sequence for [role]", "create a campaign for [audience]", `/build_sequence` |

### IMPORTANT: Lazy imports
Phase 4 modules (`github_pusher`, `sequence_builder`) are imported **inside** `execute_tool()`, not at the top of `main.py`. This means Scout boots cleanly even if these files are temporarily missing from the repo. Don't move them to top-level imports.

---

## 13. PHASE 4.5 — VOICE TRAINER UPGRADE (⬜ Next)

### Problem
Current `voice_trainer.py`:
- GAS bridge fetches up to 200 sent emails (`max_results=200`)
- `voice_trainer.py` hard-caps analysis at 40 emails
- Emails are analyzed in isolation — no context of the incoming message that Steven was replying to
- Result: voice profile built from 40 one-sided emails = shallow style capture

### Goal
- Fetch **1,000–2,000 sent emails** (may require pagination in Code.gs)
- For each sent email that is a **reply**, fetch the **thread** (incoming message + Steven's reply together)
- Feed Claude **paired context**: "Here is the email Steven received, here is how he replied"
- This teaches tone matching, not just writing style — the single biggest quality improvement available

### What to upload at start of Phase 4.5
Before writing any code, upload and read:
- `agent/voice_trainer.py` (current version)
- `tools/gas_bridge.py` (current version — specifically `get_sent_emails` signature)
- `gas/Code.gs` (current version — need to see what GAS already fetches)

### Changes needed
1. **`gas/Code.gs`** — add `get_email_thread(threadId)` action + pagination support to `get_sent_emails`
2. **`tools/gas_bridge.py`** — add `get_email_thread(thread_id)` method + update `get_sent_emails` to accept `page_token`
3. **`agent/voice_trainer.py`** — rewrite training loop: fetch in batches, resolve threads for replies, build richer prompt
4. **No changes needed** to `main.py`, `claude_brain.py`, or `config.py`

---

## 14. ALL CLAUDE TOOLS (13 total in claude_brain.py)

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

---

## 15. SHORTHAND COMMANDS (handle_message in main.py)

| Command | Expands to |
|---------|-----------|
| `/ping_gas`, `ping gas`, `test gas` | ping the GAS bridge |
| `/train_voice`, `train voice`, `learn my style` | train your voice model from my Gmail history |
| `/list_files`, `/ls`, `list files` | list all files in the repo root |
| `/push_code [filepath]` | I want to push code to GitHub. File path: [filepath]. Ask me for the file content. |
| `/build_sequence [args]` | Build an email sequence for [args]. Ask me for any details you need. |
| `looks good`, `save it`, `approved`, `use this` | (when pending draft exists) → triggers save_draft_to_gmail |
| `add email: addr@district.org` | (when pending draft exists) → sets recipient |

---

## 16. KEY DECISIONS

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
| Lazy imports for Phase 4 modules | Scout boots cleanly even if new tool files not yet uploaded |
| tool_result appended to history | Claude API 400 error if tool_use has no matching tool_result in next message |
| Hardcode user email in GAS ping | Session.getActiveUser() returns empty for anonymous callers; getEffectiveUser() throws permission error |
| Read modules before writing code | All crashes were hallucinated method names — prevention requires reading source first |
| 1000-2000 emails with thread context | 40 isolated emails produces shallow voice profile; paired incoming+reply context teaches tone matching |

---

## 17. BUG FIX LOG

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

---

## 18. CHANGELOG

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
| 2026-02-28 | Phase 4.5 planned: voice trainer upgrade to 1000-2000 emails with thread context | Phase 4.5 ⬜ |

---

## 19. FULL TARGET TITLE & KEYWORD LIST

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
