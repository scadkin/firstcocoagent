# SCOUT — Claude Code Reference
*Last updated: 2026-03-02 — Session 5*

---

## CURRENT STATE — update this after each session

**Phase 6A fully verified ✅. Ready to build Phase 6B.**

### What was built/fixed this session
- GAS redeploy completed: `createGoogleDoc` try/catch for DriveApp folder-move is now live
- `/build_sequence` verified end-to-end: questions → build → Telegram preview → Google Doc link → doc lands in "Scout Built Sequences" folder
- **Bug fix:** Duplicate "Got it — building the sequence now." message after sequence output. Root cause: `text_response` (Claude's preamble text sent alongside a tool_use block) was being sent to Telegram AFTER `execute_tool` had already sent the sequence directly. Fix: `if text_response and not tool_calls:` at line 707 of `agent/main.py`. Suppresses Claude's pre-tool chatter whenever a tool is being called.

### Current status
- `/recent_calls` ✅
- `/call [id]` ✅
- `/brief` (manual) ✅
- Auto pre-call brief (10-min trigger) ✅
- Fireflies webhook (auto on call end) ⏳ configured, pending first real external call
- `/build_sequence` ✅ fully verified — questions, sequence, Google Doc, correct folder, clean output

### Next step
**Phase 6B — Research Engine Expansion.** Full plan in `/Users/stevenadkins/.claude/plans/glistening-jumping-teacup.md`.
- 4 new search layers in `tools/research_engine.py` (L11: school staff, L12: board agendas, L13: state DOE, L14: conference presenters)
- `enqueue_batch()` on `ResearchQueue` + `research_batch` tool wired into `claude_brain.py` + `main.py`
- Configurable `SERPER_REQUESTS_PER_JOB` env var (default 22, up from hardcoded 15)

### Phase 6 plan
- **6A** — Campaign Engine ✅ done
- **6B** — Research Engine Expansion ← next
- **6C** — Activity Tracking + Analytics (activity_tracker.py, data-driven morning brief/EOD)
- **6D** — Automation + Learning Loops (campaign_manager.py, Outreach CSV import, weekly review)

---

## CRITICAL RULES

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names.

**Always produce complete replacement files.** Never give partial snippets or "find line X and replace." Steven uploads full files directly.

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result causes 400 on the next API call.

**GAS bridge: every Code.gs edit needs a new deployment.** Save → Deploy → Manage deployments → Edit → New version → Deploy → copy URL → update `GAS_WEBHOOK_URL` in Railway.

**Never design workflows that require pasting large text through Telegram.** Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

**Explicit commands must bypass Claude and call execute_tool() directly.** `/brief`, `/call`, `/recent_calls` all call execute_tool() directly and return — never route through Claude's tool dispatch. When conversation history is long, Claude responds with text describing what the tool would do instead of calling it. Direct dispatch is the only reliable pattern for explicit slash commands.

**`/build_sequence` is a hybrid — questions via Claude, output direct.** The slash command routes through Claude so it can ask clarifying questions. But `execute_tool("build_sequence")` sends the final result via `await send_message()` directly and returns `"✅ Sequence built and sent above."` — a short string that prevents Claude from rewriting the sequence output.

**`execute_tool` can send directly to Telegram for long outputs.** For tools that return content Claude tends to rewrite (sequences, docs), use `await send_message(full_output)` inside `execute_tool` and return a short ack string. This is the pattern for `build_sequence` and should be used for any future tools with rich structured output.

**GAS deployment URL does NOT change when bumping version.** When you edit an existing deployment and increment the version, the Web App URL stays the same. Only Railway update needed is if you create a brand-new deployment (not an edit).

**Suppress `text_response` when tool_calls are present.** In `handle_message`, use `if text_response and not tool_calls:` before sending Claude's text response. When Claude calls a tool, its preamble text ("Got it — building...") is noise — the tool output IS the response. This prevents duplicate/out-of-order messages for any tool that sends output directly to Telegram.

---

## WHAT SCOUT IS

Always-on AI assistant running 24/7 on Railway.app. Communicates via Telegram (@coco_scout_bot).
- Morning brief: 9:15am CST | EOD report: 4:30pm CST | Hourly check-in: 10am–4pm CST
- Persistent memory via GitHub (never cleared)
- Operator: Steven — steven@codecombat.com — CST timezone

**Architecture:**
```
Telegram → agent/main.py (asyncio poll loop)
                ↓
         claude_brain.py (Claude API + tools)
                ↓
    tools/ + GAS bridge + GitHub memory
```

**GAS bridge:** Scout (Railway) → HTTPS POST + secret token → Google Apps Script Web App → Gmail/Calendar/Slides/Docs
Reason: work Google Workspace blocks third-party OAuth; GAS runs inside Google as Steven, no IT approval needed.

---

## REPO STRUCTURE

```
firstcocoagent/
├── CLAUDE.md
├── SCOUT_HISTORY.md            ← Bug log + changelog (not loaded each session)
├── Procfile                    ← "web: python -m agent.main"
├── requirements.txt
├── agent/
│   ├── main.py                 ← Entry point. Scheduler poll loop. All tool dispatch. _parse_guests().
│   ├── config.py               ← Env vars (GAS_WEBHOOK_URL, GAS_SECRET_TOKEN, etc.)
│   ├── claude_brain.py         ← Claude API + tool definitions + memory injection. 18 tools.
│   ├── memory_manager.py       ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py            ← CST-aware Scheduler class, check() only
│   ├── keywords.py             ← Lead research title/keyword list
│   ├── voice_trainer.py        ← Paginated email fetch + paired context analysis
│   ├── call_processor.py       ← Phase 5: transcript → summary → Google Doc
│   └── webhook_server.py       ← Phase 5: aiohttp server for Fireflies webhook
├── tools/
│   ├── telegram_bot.py
│   ├── research_engine.py      ← ResearchJob, ResearchQueue classes. Singleton: research_queue.
│   ├── contact_extractor.py
│   ├── sheets_writer.py        ← MODULE (not class). write_contacts(), count_leads(), etc.
│   ├── gas_bridge.py           ← GASBridge class
│   ├── github_pusher.py        ← push_file(), list_repo_files(), get_file_content()
│   ├── sequence_builder.py     ← Phase 6A. build_sequence(), write_sequence_to_doc(), format_for_telegram()
│   └── fireflies.py            ← FirefliesClient, FirefliesError
├── gas/
│   └── Code.gs                 ← Deployed at script.google.com as "Scout Bridge"
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   ├── email_draft.md
│   └── sequence_templates.md   ← Phase 6A. 17 archetypes: 6 role-based + 11 scenario-based
└── memory/
    ├── preferences.md          ← Corrections/preferences. GitHub-committed on every write.
    ├── context_summary.md      ← EOD summaries. Never deleted.
    └── voice_profile.md        ← Built from 273 paired emails.
```

---

## RAILWAY ENVIRONMENT VARIABLES

| Variable | Notes |
|----------|-------|
| ANTHROPIC_API_KEY | Claude API |
| TELEGRAM_BOT_TOKEN | Bot token |
| TELEGRAM_CHAT_ID | 8677984089 |
| MORNING_BRIEF_TIME | 09:15 |
| EOD_REPORT_TIME | 16:30 |
| TIMEZONE | America/Chicago |
| AGENT_NAME | Scout |
| GITHUB_TOKEN | Fine-grained PAT, contents:write |
| GITHUB_REPO | scadkin/firstcocoagent |
| CHECKIN_START_HOUR | 10 |
| CHECKIN_END_HOUR | 16 |
| SERPER_API_KEY | serper.dev |
| GOOGLE_SHEETS_ID | From Sheet URL |
| GOOGLE_SERVICE_ACCOUNT_JSON | Full JSON string, personal account |
| GAS_WEBHOOK_URL | **Update every time Code.gs is redeployed** |
| GAS_SECRET_TOKEN | Must match Code.gs |
| FIREFLIES_API_KEY | app.fireflies.ai → Account → API |
| FIREFLIES_WEBHOOK_SECRET | Must match Fireflies webhook config |
| PRECALL_BRIEF_FOLDER_ID | Google Drive folder ID — confirmed set |
| SEQUENCES_FOLDER_ID | Phase 6A. Google Drive folder ID for sequence docs. Paste full browser URL — query params stripped automatically. Set to "Scout Built Sequences" folder. |

**Note:** Phase 5+ env vars (`FIREFLIES_API_KEY`, `FIREFLIES_WEBHOOK_SECRET`, `PRECALL_BRIEF_FOLDER_ID`, `SEQUENCES_FOLDER_ID`) are read via `os.environ.get()` directly in the files that need them — they are NOT in `config.py`.

---

## MODULE API REFERENCE

### MemoryManager (`agent/memory_manager.py`)
```python
memory_manager.load_preferences() -> str
memory_manager.load_recent_summary() -> str
memory_manager.build_memory_context() -> str
memory_manager.save_preference(entry: str)
memory_manager.append_to_summary(text: str)
memory_manager.clear_preferences()
memory_manager._commit_to_github(filepath, content, message)
memory_manager.extract_memory_update(response) -> tuple  # static
# NO .load() — NO .compress_history()
```

### Scheduler (`agent/scheduler.py`)
```python
scheduler = Scheduler()  # NO arguments
event = scheduler.check()  # returns "morning_brief" | "eod_report" | "checkin" | None
# NO .run() method
```

### GASBridge (`tools/gas_bridge.py`)
```python
gas = GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)
gas.ping() -> dict
gas.get_sent_emails(months_back=6, max_results=200, page_start=0, page_size=200) -> list[dict]
gas.get_sent_emails_page(months_back=6, page_size=200, page_start=0) -> dict  # has_more field
gas.create_draft(to, subject, body) -> dict
gas.search_inbox(query, max_results=10) -> list[dict]
gas.get_calendar_events(days_ahead=7) -> list[dict]
gas.log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps) -> dict
gas.create_district_deck(district_name, state, contact_name, contact_title, student_count, key_pain_points, products_to_highlight, case_study) -> dict
gas.create_google_doc(title, content, folder_id) -> dict  # {success, doc_id, url, title}
```
**GAS returns calendar `guests` as plain email strings, NOT dicts. Use `_parse_guests()` in main.py to normalize.**

### ResearchQueue (`tools/research_engine.py`)
```python
from tools.research_engine import research_queue  # use the singleton
await research_queue.enqueue(district_name, state, progress_callback, completion_callback)
research_queue.current_job   # property, no ()
research_queue.queue_size    # property, no ()
# NEVER instantiate ResearchJob directly
```

### sheets_writer (`tools/sheets_writer.py`) — MODULE, NOT A CLASS
```python
import tools.sheets_writer as sheets_writer
sheets_writer.write_contacts(contacts, state="")
sheets_writer.count_leads()
sheets_writer.get_master_sheet_url()
sheets_writer.log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)
sheets_writer.ensure_sheet_tabs_exist()
# from tools.sheets_writer import SheetsWriter  ← CRASHES — class does not exist
```

### VoiceTrainer (`agent/voice_trainer.py`)
```python
trainer = VoiceTrainer(gas_bridge=gas, memory_manager=memory)
trainer.train(months_back=24, progress_callback=None) -> str
trainer.load_profile() -> Optional[str]
trainer.update_profile_from_feedback(feedback: str) -> bool
```

### github_pusher (`tools/github_pusher.py`) — lazy import only
```python
import tools.github_pusher as github_pusher
github_pusher.push_file(filepath, content, commit_message=None) -> dict  # {success, url, message}
github_pusher.list_repo_files(path="") -> list[str]
github_pusher.get_file_content(filepath) -> str | None
```

### sequence_builder (`tools/sequence_builder.py`) — lazy import only
```python
import tools.sequence_builder as sequence_builder
sequence_builder.build_sequence(campaign_name, target_role, focus_product="CodeCombat AI Suite", num_steps=5, voice_profile=None, additional_context="", ab_variants=True) -> dict
# {success, steps: [{step, day, label, subject, body, variant_b_subject, variant_b_body}], raw, error}
# Uses prompts/sequence_templates.md for 17 archetypes. Calls claude-sonnet-4-6.
sequence_builder.write_sequence_to_doc(campaign_name, steps, gas_bridge, folder_id=None) -> dict
# {success, url, error} — creates Google Doc via GAS bridge. folder_id defaults to SEQUENCES_FOLDER_ID env var.
sequence_builder.format_for_telegram(campaign_name, steps) -> str
# Compact preview: subject + first ~150 chars of body per step. A/B variant subject shown inline.
# SEQUENCES_FOLDER_ID env var: strip ?query params automatically — safe to paste full browser URL
```

### FirefliesClient (`tools/fireflies.py`) — lazy import only
```python
from tools.fireflies import FirefliesClient, FirefliesError
client = FirefliesClient(api_key=FIREFLIES_API_KEY)
client.get_transcript(transcript_id) -> dict
# {id, title, date, duration, attendees: [{name, email}], transcript, summary, action_items, keywords}
client.get_recent_transcripts(limit=5, filter_internal=True) -> list[dict]
# Fetches 4x limit, filters internal, sorts most-recent-first
client.format_recent_for_telegram(transcripts) -> str
```
**Fireflies schema is camelCase:** `dateString`, `speakerName`, `meeting_attendees` (for email filtering), `participants` (name strings only).
**Internal filter:** skip if ALL `meeting_attendees` emails are @codecombat.com. Keep if ANY external email present.

### CallProcessor (`agent/call_processor.py`) — lazy import only
```python
from agent.call_processor import CallProcessor
processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=None)
# Reads PRECALL_BRIEF_FOLDER_ID from os.environ directly
await processor.build_pre_call_brief(event, attendees, progress_callback=None) -> str
await processor.process_transcript(transcript_id, progress_callback=None) -> dict
# {telegram_summary, recap_email, salesforce_block, outreach_row, draft_url, error}
```
`_create_brief_doc` returns: `"https://docs.google.com/..."` | `"ERROR:<msg>"` | `""` (folder ID not set)

---

## CLAUDE TOOLS (18 total, all in claude_brain.py + handled in main.py)

`research_district`, `get_sheet_status`, `get_research_queue_status`, `train_voice`, `draft_email`, `save_draft_to_gmail`, `get_calendar`, `log_call`, `create_district_deck`, `push_code`, `list_repo_files`, `get_file_content`, `build_sequence`, `ping_gas_bridge`, `grade_draft`, `add_template`, `process_call_transcript`, `get_pre_call_brief`

---

## SHORTHAND COMMANDS (`handle_message` in main.py)

| Command | Action |
|---------|--------|
| `/ping_gas`, `ping gas`, `test gas` | ping GAS bridge |
| `/train_voice`, `train voice`, `learn my style` | train voice from Gmail (24 months) |
| `/grade_draft`, `grade draft`, `rate that draft` | feedback on last draft → updates voice_profile.md |
| `/add_template [content]` | add template to voice profile |
| `/list_files`, `/ls`, `list files` | list repo files |
| `/push_code [filepath]` | fetch-first: read file, ask for changes, edit + push |
| `/build_sequence [campaign name]` | Routes through Claude to ask 4 clarifying questions, then builds. execute_tool sends result directly to Telegram. |
| `looks good`, `save it`, `approved`, `use this` | save pending draft to Gmail |
| `add email: addr@domain.org` | set recipient on pending draft |
| `/brief [meeting name]` | manual pre-call brief (Phase 5) |
| `/recent_calls [num]` | recent external calls, optional count 1–20 |
| `/call [transcript_id or url]` | manual post-call processing (Phase 5) |

---

## GAS DEPLOYMENT CHECKLIST

Every time `Code.gs` changes:
1. script.google.com → Scout Bridge → Code.gs → edit + save
2. Deploy → Manage deployments → pencil icon → Version: New version → Deploy
3. Copy new URL
4. Railway dashboard → Variables → update `GAS_WEBHOOK_URL`
5. Railway redeploys automatically
6. Run `/ping_gas` to verify

**Gotchas:**
- `SECRET_TOKEN` placeholder in Code.gs must be replaced with actual token before deploying
- `Session.getActiveUser().getEmail()` returns `""` for anonymous callers — hardcode `"steven@codecombat.com"` in ping handler
- Never use `Session.getEffectiveUser()` — throws permission error
- Bumping version on an existing deployment keeps the same URL — no Railway update needed
- DriveApp `getFolderById` throws "Unexpected error" if DriveApp is not authorized OR if called during a deployment that hasn't re-authed. Wrap in try/catch so doc creation never fails due to folder move.
- `SEQUENCES_FOLDER_ID` (and any Drive folder ID env var) may be pasted as full browser URL with `?ths=true`. Strip with `.split("?")[0]` before use.
