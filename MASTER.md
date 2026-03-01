# SCOUT — MASTER REFERENCE DOCUMENT
*Last updated: 2026-03-01 — End of Phase 5 debugging session*

---

## ⚡ RESUME POINT — START HERE IN NEXT CHAT

**Where we left off:** Phase 5 is live and mostly working. One outstanding issue remains.

### What's working ✅
- `/recent_calls` — fetches most recent external calls (filters internal @codecombat.com meetings), one clean message, supports `/recent_calls 10` for custom count
- `/brief` — generates pre-call brief, sends to Telegram. Content works. **Google Doc creation is failing silently.**
- `/call [id]` — manual post-call transcript processing
- Immediate ack system — Scout responds within 5 seconds for all commands

### One outstanding fix — upload this file before continuing
**File to upload:** `agent/call_processor.py` (already generated, ready to download from this chat)
**Upload to:** GitHub → `agent/call_processor.py`
**What it fixes:** Google Doc creation was silently failing and showing a misleading "PRECALL_BRIEF_FOLDER_ID not set" message even though the variable IS set. The fix surfaces the real error from GAS bridge so we can see exactly what's wrong.

**After uploading and Railway redeploys:** Run `/brief` again. The bottom of the message will now show either:
- `📄 [Open Google Doc](url)` → it's working, we're done
- `⚠️ Google Doc creation failed: [actual error message]` → bring that error message into the new chat

### Most likely cause of Google Doc failure
The `createGoogleDoc` action in `Code.gs` either:
1. Was never saved/deployed after being added, OR
2. Was added but a **new deployment** was not created after saving (every Code.gs change needs a new deployment + Railway URL update)

Check script.google.com → Scout Bridge → Code.gs and confirm the `createGoogleDoc` case exists. If it does, create a new deployment and update `GAS_WEBHOOK_URL` in Railway.

### Files to share with new chat
Yes — upload these files at the start of the new chat so Claude can read them before writing anything:
1. `agent/main.py`
2. `agent/call_processor.py`
3. `tools/fireflies.py`
4. `gas/Code.gs`

These are the four files most likely to be touched next. Claude will read them before writing any code.

---

## 0. CRITICAL RULES FOR CLAUDE

**Before writing any code that calls an existing module:**
Read that module first using the file tools. Every crash in this project has been caused by hallucinated method names or wrong signatures. There are no exceptions to this rule.

**Always produce complete replacement files.**
Steven is a beginner — never give partial snippets or "find line X and replace" instructions. Always generate the full file so he can upload it directly.

**Lazy imports only for Phase 4+ modules.**
`github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`. Scout must boot cleanly even if those files are temporarily missing.

**Tool results MUST always be appended to conversation history.**
Every `tool_use` block must be immediately followed by a `tool_result` block in the next user message. Wrap every `execute_tool()` call in try/except so a result is always appended even if the tool throws. Without this, the next Claude API call will 400.

**GAS bridge — every Code.gs edit needs a new deployment.**
Editing Code.gs and saving is not enough. Must: Deploy → Manage deployments → Edit → New version → Deploy → Copy new URL → Update `GAS_WEBHOOK_URL` in Railway.

**Telegram character limit awareness.**
Never design workflows that require Steven to paste large amounts of text through Telegram. Use fetch-first patterns (Scout reads from GitHub, asks for changes in plain English).

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
- **Call Intelligence Suite** (Phase 5 ✅ — live, Google Doc creation pending fix)

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
| Fireflies.ai | Zoom transcription + webhook | Free (800 min/mo) | ✅ Live — notetaker joins via Google Calendar sync |
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
| 5 | Call Intelligence Suite (Fireflies + Pre-call Brief + Post-call Summary + Recap Email) | ✅ Live — Google Doc pending fix |
| 6 | At-Scale Research + Campaign Engine | ⬜ Next |
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
│   ├── claude_brain.py              ← Claude API + tool use + memory injection. 17 tools total.
│   ├── memory_manager.py            ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py                 ← CST-aware Scheduler class with check() method
│   ├── keywords.py                  ← Full title/keyword/role list (Phase 2)
│   ├── voice_trainer.py             ← Paginated email fetch + paired context analysis (Phase 4.5)
│   ├── call_processor.py            ← Phase 5: transcript → structured notes → summary → outputs
│   └── webhook_server.py            ← Phase 5: aiohttp server to receive Fireflies webhook POST
├── tools/
│   ├── __init__.py
│   ├── telegram_bot.py
│   ├── research_engine.py           ← Classes: ResearchJob, ResearchQueue. Singleton: research_queue.
│   ├── contact_extractor.py         ← Claude-powered contact extraction (Phase 2)
│   ├── sheets_writer.py             ← Module of functions (no class). write_contacts(), count_leads(), etc.
│   ├── gas_bridge.py                ← GASBridge class: Gmail/Calendar/Slides/Docs (Phase 5 updated)
│   ├── github_pusher.py             ← push_file(), list_repo_files(), get_file_content() (Phase 4)
│   ├── sequence_builder.py          ← build_sequence(), write_sequence_to_sheets(), format_for_telegram() (Phase 4)
│   └── fireflies.py                 ← Phase 5: Fireflies GraphQL API client
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
    ├── SETUP_PHASE5.md
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
| GAS_WEBHOOK_URL | (update every time Code.gs is redeployed) | ✅ Set |
| GAS_SECRET_TOKEN | (matches Code.gs) | ✅ Set |
| FIREFLIES_API_KEY | (from app.fireflies.ai → Account → API) | ✅ Set |
| FIREFLIES_WEBHOOK_SECRET | (set in Fireflies webhook config, must match Railway) | ✅ Set |
| PRECALL_BRIEF_FOLDER_ID | (Google Drive folder ID — confirmed set correctly) | ✅ Set |

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
gas.create_google_doc(title, content, folder_id) -> dict   # Phase 5 — returns {success, doc_id, url, title}
```

**Important: GAS bridge returns calendar event `guests` as plain email strings, NOT dicts.**
Use `_parse_guests()` helper in `main.py` to normalize to `[{name, email}]` before using.

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
Phase 4+ modules (`github_pusher`, `sequence_builder`, `fireflies`, `call_processor`) are imported **inside** `execute_tool()`, not at the top of `main.py`. Scout boots cleanly even if files are temporarily missing. Never move them to top-level imports.

### IMPORTANT: /push_code fetch-first workflow
`/push_code filepath` → Scout fetches file from GitHub, summarizes it, asks what changes Steven wants, makes edits, pushes. Steven never pastes file content through Telegram. Note: `/push_code` has never worked reliably — always generate full replacement files for Steven to upload manually instead.

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

## 14. PHASE 5 — CALL INTELLIGENCE SUITE (✅ Live — Google Doc pending fix)

### Status
- `tools/fireflies.py` — deployed, working
- `agent/call_processor.py` — deployed. **New version ready to upload** (surfaces Google Doc errors)
- `agent/webhook_server.py` — deployed
- `/recent_calls` — working ✅
- `/brief` — working ✅ (Google Doc creation failing silently — fix pending)
- `/call [id]` — working ✅
- Auto-trigger (10-min pre-call brief) — code live, not yet tested

### Fireflies notes (hard-won)
- Steven's Zoom integration was blocked by IT — using **Google Calendar sync** instead (Fireflies notetaker joins via calendar)
- Fireflies GraphQL schema uses camelCase: `dateString` not `date`, `speakerName` not `speaker_name`
- `participants` field = flat list of name strings (no emails)
- `meeting_attendees` field = list of `{displayName, email}` objects — use this for email-based filtering
- Internal meeting filter: if ALL `meeting_attendees` emails are @codecombat.com → skip
- If even ONE external email present → keep the call
- Fireflies only transcribes calls where the notetaker bot was present — recent calls missing from `/recent_calls` means the bot wasn't connected yet for those calls

### FirefliesClient — actual method signatures
```python
from tools.fireflies import FirefliesClient, FirefliesError

client = FirefliesClient(api_key=FIREFLIES_API_KEY)
client.get_transcript(transcript_id: str) -> dict
# Returns: {id, title, date, duration, attendees: [{name, email}], transcript: str, summary: str, action_items: str, keywords: list}

client.get_recent_transcripts(limit: int = 5, filter_internal: bool = True) -> list[dict]
# Fetches 4x limit then filters, sorts most-recent-first

client.format_recent_for_telegram(transcripts: list[dict]) -> str
```

### CallProcessor — actual method signatures
```python
from agent.call_processor import CallProcessor

processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=None)
# IMPORTANT: reads PRECALL_BRIEF_FOLDER_ID from os.environ directly (not config.py)

await processor.build_pre_call_brief(event: dict, attendees: list[dict], progress_callback=None) -> str
await processor.process_transcript(transcript_id: str, progress_callback=None) -> dict
# Returns: {telegram_summary, recap_email, salesforce_block, outreach_row, draft_url, error}
```

### _create_brief_doc return values (updated)
```python
# Returns one of:
"https://docs.google.com/..."   # success — use as link
"ERROR:<message>"               # GAS bridge failed — surface the message
""                              # folder ID not configured
```

### _parse_guests() helper in main.py
```python
# GAS bridge returns guests as plain email strings OR dicts — this normalises both
def _parse_guests(raw_guests: list) -> list:
    # Returns [{name, email}] with @codecombat.com filtered out
```

### What /brief does (use case)
Manual command: send `/brief` 30-60 minutes before a prospect call to get a research brief.
Auto-trigger: Scout watches calendar every 30s and fires automatically 10 minutes before any Zoom with external attendees. The auto-trigger is the main value — you don't have to remember to ask.

### /recent_calls command
- `/recent_calls` — fetch 5 most recent external calls
- `/recent_calls 10` — fetch 10 (any number 1-20)
- Filters out internal meetings (all-codecombat.com attendees)
- Sorted most-recent-first
- Note: only shows calls where Fireflies notetaker was present

---

## 15. ALL CLAUDE TOOLS (17 total)

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
| `get_file_content` | 4 | ✅ |
| `build_sequence` | 4 | ✅ |
| `ping_gas_bridge` | 3 | ✅ |
| `grade_draft` | 4.5 | ✅ (via /grade_draft shorthand) |
| `add_template` | 4.5 | ✅ (via /add_template shorthand) |
| `process_call_transcript` | 5 | ✅ |
| `get_pre_call_brief` | 5 | ✅ |

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
| `/recent_calls [num]` | list recent external Fireflies transcripts, optional count 1-20 |
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
| Google Calendar sync for Fireflies | IT blocked Zoom integration; calendar sync achieves same result |
| Always generate full replacement files | Steven is a beginner — never give partial snippets or line-by-line instructions |
| Immediate ack within 5 seconds | Steven needs signal that Scout heard the command before long tasks run |
| _parse_guests() normalises GAS guests | GAS returns guests as plain strings, not dicts — normalize at entry point |
| tool_use always gets tool_result | Wrap every execute_tool() in try/except — history corruption causes 400 on next message |

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
| ImportError: FIREFLIES_API_KEY from agent.config | Phase 5 vars added to main.py import but config.py never updated | Read from os.environ directly in main.py | ✅ Fixed |
| ModuleNotFoundError: aiohttp | aiohttp used by webhook_server.py but not in requirements.txt | Added aiohttp to requirements.txt | ✅ Fixed |
| Unknown tool: get_file_content | Handler existed in plan but was never added to execute_tool() | Added full get_file_content handler to main.py | ✅ Fixed |
| /push_code fetched file but didn't ack or summarize | Prompt told Claude to fetch but didn't specify next steps clearly enough | Added immediate ack send_message + step-by-step PUSH_CODE WORKFLOW prompt | ✅ Fixed |
| Scout ending messages with "On it." | Claude's default response pattern — memory can't override hardcoded behavior | Added _clean() function that strips "On it." and "Let me know if..." before every send_message | ✅ Fixed |
| Behavioral corrections not saving to memory | Claude didn't always tag corrections with [MEMORY_UPDATE] | Added correction_signals detector that appends memory save hint to user message | ✅ Fixed |
| main.py corrupted from repeated patch attempts | Multiple incremental sed/replace operations left stray quote chars and broken f-strings | Rebuilt from original uploaded file with all changes in single clean pass | ✅ Fixed |
| Fireflies 400 Bad Request on /recent_calls | Field name mismatches: date→dateString, attendees→participants, speaker_name→speakerName | Rewrote fireflies.py GraphQL queries with correct schema | ✅ Fixed |
| /recent_calls sent two messages | Old container briefly responded during Railway redeploy | Moved to direct send_message flow with single return path | ✅ Fixed |
| /recent_calls showing random old dates | Fireflies returns calls in arbitrary order | Added sort by dateString descending before returning | ✅ Fixed |
| /brief completely silent after tool error | CallProcessor crash uncaught — tool_result never appended to history | Wrapped all execute_tool() calls in try/except; always append result | ✅ Fixed |
| /brief 400 on follow-up message | tool_use block in history had no matching tool_result (history corrupted) | try/except guarantees tool_result always written; history auto-clears on 400 | ✅ Fixed |
| /brief "str object has no attribute get" | GAS bridge returns guests as plain email strings, not dicts | Added _parse_guests() helper that handles both string and dict formats | ✅ Fixed |
| ImportError: PRECALL_BRIEF_FOLDER_ID in call_processor | Imported from config.py which didn't have it | Changed to os.environ.get() directly | ✅ Fixed |
| Google Doc silently skipped despite PRECALL_BRIEF_FOLDER_ID being set | Exception swallowed silently, fallback message blamed missing env var | _create_brief_doc now returns "ERROR:<msg>" string; build_pre_call_brief surfaces it | ⏳ Fix ready — upload call_processor.py |
| internal meeting filter used hostEmail | hostEmail = codecombat.com on all calls; need to check if ANY attendee is external | Changed to check meeting_attendees[].email — skip only if ALL emails are @codecombat.com | ✅ Fixed |

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
| 2026-02-28 | Phase 5 fully designed: Call Intelligence Suite architecture, all decisions documented | Phase 5 design ✅ |
| 2026-02-28 | Phase 5 built: tools/fireflies.py, agent/call_processor.py, agent/webhook_server.py | Phase 5 |
| 2026-02-28 | Phase 5: Code.gs updated with createGoogleDoc action | Phase 5 |
| 2026-02-28 | Phase 5: gas_bridge.py create_google_doc(), claude_brain.py 2 new tools, main.py asyncio.gather | Phase 5 |
| 2026-02-28 | Phase 5: SETUP_PHASE5.md written, MASTER.md updated | Phase 5 |
| 2026-02-28 | Bug fixes: aiohttp missing, FIREFLIES_API_KEY ImportError, get_file_content handler missing | Phase 5 |
| 2026-02-28 | Phase 5 code fully deployed — Fireflies account setup + verification pending | Phase 5 |
| 2026-03-01 | Phase 5 debugging: Fireflies GraphQL schema fixed (dateString, participants, meeting_attendees) | Phase 5 |
| 2026-03-01 | /recent_calls: single clean message, sort by date, internal meeting filter by attendee email | Phase 5 |
| 2026-03-01 | /recent_calls: optional count argument (/recent_calls 10), capped 1-20 | Phase 5 |
| 2026-03-01 | /brief: immediate ack within 5 seconds for all long-running commands | Phase 5 |
| 2026-03-01 | /brief: fixed silent crash — PRECALL_BRIEF_FOLDER_ID read from os.environ not config.py | Phase 5 |
| 2026-03-01 | /brief: fixed 400 on follow-up — try/except wraps all tool calls, tool_result always appended | Phase 5 |
| 2026-03-01 | /brief: fixed "str has no attribute get" — _parse_guests() handles string and dict guest formats | Phase 5 |
| 2026-03-01 | /brief working end-to-end — Google Doc creation still failing silently (fix generated, pending upload) | Phase 5 |
| 2026-03-01 | call_processor.py updated: _create_brief_doc surfaces real error instead of generic fallback message | Phase 5 ⏳ |

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
