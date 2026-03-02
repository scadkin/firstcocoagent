# SCOUT — Claude Code Reference
*Last updated: 2026-03-01*

---

## CURRENT STATE — update this after each session

**Phase 5 live.** One outstanding issue:

**Google Doc creation in `/brief` is failing silently.**
- Fix is in `agent/call_processor.py` — `_create_brief_doc` now returns `"ERROR:<msg>"` instead of swallowing exceptions
- Upload that file to GitHub, let Railway redeploy, run `/brief` again
- Most likely cause: `createGoogleDoc` case in `Code.gs` was added but a **new deployment** was never created
- Check script.google.com → Scout Bridge → Code.gs → confirm `createGoogleDoc` case exists → new deployment → update `GAS_WEBHOOK_URL` in Railway

**What's working:**
- `/recent_calls` ✅ — filters internal meetings, optional count, sorted most-recent-first
- `/brief` ✅ — content works, Google Doc creation pending fix above
- `/call [id]` ✅ — manual post-call processing
- Immediate ack ✅ — all commands respond within 5 seconds

**Next phase:** Phase 6 — At-Scale Research + Campaign Engine

---

## CRITICAL RULES

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names.

**Always produce complete replacement files.** Never give partial snippets or "find line X and replace." Steven uploads full files directly.

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result causes 400 on the next API call.

**GAS bridge: every Code.gs edit needs a new deployment.** Save → Deploy → Manage deployments → Edit → New version → Deploy → copy URL → update `GAS_WEBHOOK_URL` in Railway.

**Never design workflows that require pasting large text through Telegram.** Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

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
│   ├── sequence_builder.py     ← build_sequence(), write_sequence_to_sheets(), format_for_telegram()
│   └── fireflies.py            ← FirefliesClient, FirefliesError
├── gas/
│   └── Code.gs                 ← Deployed at script.google.com as "Scout Bridge"
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── email_draft.md
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

**Note:** Phase 5 env vars (`FIREFLIES_API_KEY`, `FIREFLIES_WEBHOOK_SECRET`, `PRECALL_BRIEF_FOLDER_ID`) are read via `os.environ.get()` directly in the files that need them — they are NOT in `config.py`.

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
sequence_builder.build_sequence(campaign_name, target_role, focus_product="CodeCombat AI Suite", num_steps=4, voice_profile=None, additional_context="") -> dict
# {success, steps: [{step, day, label, subject, body}], raw, error}
sequence_builder.write_sequence_to_sheets(campaign_name, steps) -> bool
sequence_builder.format_for_telegram(campaign_name, steps) -> str
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
| `/build_sequence [args]` | build Outreach.io sequence |
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
