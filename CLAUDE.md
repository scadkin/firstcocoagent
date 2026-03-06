# SCOUT — Claude Code Reference
*Last updated: 2026-03-06 — Session 12*

---

## CURRENT STATE — update this after each session

**Phase 6D verification in progress. SoCal CSV uploaded. Ready for Step 2 (research a district).**

### What was built/fixed this session (Session 12)
- **Layer 15: Email Verification & Discovery** added to `research_engine.py`:
  - Runs after L10 (dedup+scoring) on the cleaned contact list
  - Step 1: identifies contacts with INFERRED/UNKNOWN confidence or missing email
  - Step 2+3: generates candidate emails from L8 pattern, searches quoted email in Serper → VERIFIED if email+name both in snippet, LIKELY if email only
  - Step 4: enrichment search (`"Name" "District" CS OR STEM OR CTE`) for high-priority contacts → extracts new contacts from snippets
  - Step 5: discovery searches (`"@domain.org" computer science coordinator`) → finds contacts missed by earlier layers
  - Hard cap: 30 queries per district; respects global 100-query Serper cap
  - After L15, L10 runs a second time to dedup/sort any new contacts
  - Hyphenated last name variants generated automatically
  - Student email pattern filter (strips `students.`, `stu.`, graduation year patterns)
- **`contact_extractor.py`** — model updated from `claude-opus-4-5` → `claude-sonnet-4-6`
- **`csv_importer.get_districts_with_schools()`** — targeting logic corrected (critical fix):
  - Old: started from `Account Type == "district"` entries → missed most targets
  - New: starts from school accounts → groups by `Parent Account` → excludes parent districts that already appear as `Account Type == "district"` (already have a deal)
  - Result: surfaces all parent districts where we have a school foothold but no district deal — sorted by school count descending
- **`agent/main.py`** — `L15:email-verify` added to layer breakdown order in research completion report
- **CLAUDE.md** — business model rules added: CodeCombat customer types, multi-site deals, district deal progression, Scout mission expanded, active district account guidance, Leads tab freshness note

### Key design decisions (Session 12)
- **Targeting logic: start from schools, not districts.** Active school accounts = foothold signal. Active district accounts = already closed, skip for new business. Parent districts with most active schools = highest priority call list targets.
- **CodeCombat deal progression:** individual school → multi-site deal → full district contract. "District deal" almost always means multi-site (e.g. all middle schools), not fully district-wide. Full district = rare goal.
- **Scout's mission is force multiplication**, not just assistance. The platform is designed to be taught and trained — every session makes it smarter and more capable across research, sequences, call processing, prioritization, and strategic analysis.
- **The Leads tab has existing data.** Never assume it is empty. Future feature: periodic freshness check.
- **Railway 409 Conflict on redeploy is normal.** Old container takes ~30s to die after new one starts. Both briefly poll Telegram simultaneously → Telegram rejects with 409. Resolves automatically once old container stops. Not a bug.

### Current status
- `/recent_calls` ✅
- `/call [id]` ✅ (+ email override: `/call [id] email@domain.com`)
- `/brief` (manual) ✅
- Auto pre-call brief (10-min trigger) ✅
- Fireflies webhook ✅ configured (backup trigger)
- Fireflies Gmail polling ✅ live — auto-processes calls within 60s of recap email
- `/build_sequence` ✅
- Phase 6B ✅ verified
- Phase 6C ✅ verified (all 5 steps passed)
- Account classifier ✅ fixed — district/school/library/company
- Research engine ✅ 15 layers — L15 email verification added
- Phase 6D: Daily Call List ✅ built + targeting logic fixed + deployed — **verification in progress**
- SoCal Active Accounts CSV ✅ uploaded (55 accounts: 2 districts, 46 schools, 7 other)

### Next step
**Resume Phase 6D verification at Step 2** — research a parent district from the SoCal CSV

Verification checklist (resume here):
1. ✅ Upload Salesforce CSV (done — 55 accounts imported)
2. ⬅ **Research ≥1 parent district** — open Active Accounts tab, find school with highest Parent Account count, research that district in Telegram: `Research [District Name] CA`
3. Run `/call_list` in Telegram
4. Check: Telegram preview shows ≤10 contacts with name/title/district/school count/email
5. Check: Google Doc link in message → open it → confirm full call cards + talking points
6. Check: `/progress` shows `call_list_generated` activity logged
7. Edge case: `/call_list` with no leads → confirm "No leads found" message (code-verified, may skip live test)

After verification:
- 6E: Scout suggests districts from territory, Steven approves, auto-research + sequence doc for Outreach

### Phase 6 plan (expanded)
- **6A** — Campaign Engine ✅ verified
- **6B** — Research Engine Expansion ✅ verified
- **6C** — Activity Tracking + KPI Goals + Salesforce CSV import + Gmail intelligence ✅ verified
- **6D** — Daily Call List ✅ built + targeting fixed + deployed — **verification in progress (step 2)**
- **6E** — District Prospecting Queue (Scout suggests districts from territory, Steven approves, auto-research + sequence doc for Outreach)
- **6F** — Pipeline Snapshot (Salesforce opp CSV → lightweight CRM in Sheets, stale follow-up alerts in EOD)

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

**Never use `requests` or `time.sleep()` inside async functions.** Both are synchronous and freeze the entire asyncio event loop — blocking all Telegram processing, heartbeats, and scheduled tasks. Always use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays.

**Synchronous code called from async context must use `run_in_executor`.** If a module uses synchronous I/O (e.g. `anthropic.Anthropic().messages.create()` in `contact_extractor.py`), wrap calls in `await loop.run_in_executor(None, fn, args...)`. Never call blocking functions directly from an async method — they freeze the event loop even if wrapped in `asyncio.create_task()`.

**Sheet dedup uses email as primary key.** `sheets_writer.write_contacts()` deduplicates by email first (district-agnostic), then falls back to `first|last` name for no-email contacts. Claude's extractor varies district_name spelling across runs so name+district keying caused duplicates.

**Research completion always calls `log_research_job`.** `_on_research_complete` in `main.py` must call `sheets_writer.log_research_job()` after every successful job. Failure to log is silent — no error is thrown.

**Salesforce CSV: Parent Account = always the district.** Account Name can be a district, a school, a library, or any business. When Parent Account is filled, that account is a school (or sub-unit) under that district. When Parent Account is empty, the account is either a standalone entity or a top-level district account. The hierarchy is one level deep: district → schools.

**Active accounts CSV importer must normalize names.** Salesforce has inconsistent casing (e.g. "Medina Valley Isd" vs "MEDINA VALLEY ISD"). Store a normalized lowercase key alongside the display name for matching against research engine results.

**Telegram file upload handler is a separate MessageHandler.** `handle_document()` is registered with `filters.Document.ALL` — a distinct handler from `handle_message()` (which only handles TEXT). Never merge file handling into `handle_message`. Registration order: text handler, command handler, document handler.

**activity_tracker, csv_importer, and daily_call_list are NOT lazy imports.** They are imported at the top of main.py like sheets_writer. Only Phase 4/5 modules are lazy: `github_pusher`, `sequence_builder`, `fireflies`, `call_processor`. Adding a new flat tool module? Import it at the top.

**sync_gmail_activities() is synchronous — always use run_in_executor.** `activity_tracker.sync_gmail_activities(gas)` makes blocking HTTP calls via gas_bridge. Always call it from async context as: `await loop.run_in_executor(None, activity_tracker.sync_gmail_activities, gas)`. Same rule applies to any blocking sheets/network call inside activity_tracker or csv_importer.

**CSV file upload decodes with utf-8-sig.** Salesforce (and Excel) exports often include a BOM at the start of the file. Use `file_bytes.decode("utf-8-sig")` — not `"utf-8"` — to silently strip it. Using plain `"utf-8"` causes the first column header to have a garbage prefix.

**import_accounts() clears and rewrites — it is not additive.** `csv_importer.import_accounts()` clears the "Active Accounts" tab (A2:Z) before writing fresh rows. This is intentional — each Salesforce export is the full current state. Do not add an "append" mode unless explicitly asked.

**Gmail intelligence hub pattern.** PandaDoc and Dialpad both email Steven when events occur. Use `gas.search_inbox()` with targeted queries to parse these notifications for activity logging — no API permissions needed. Dialpad call summary emails must be enabled by Steven in Dialpad → Settings → Notifications → Call Summary.

**Outreach handoff pattern for cold sequences.** Scout builds sequence content and formats it into a Google Doc for easy copy-paste into Outreach.io. Outreach.io handles actual sending, open/click tracking, and call logging. Do NOT try to replace Outreach with Gmail for cold prospecting sequences — Outreach is Steven's tool for that workflow.

**No Salesforce or Outreach API access.** Steven cannot obtain integration permissions for Salesforce, Outreach.io, PandaDoc, or Dialpad. All data from these tools enters Scout via CSV export (Salesforce, Outreach) or Gmail notification parsing (PandaDoc, Dialpad). Never design a feature that assumes API access to these tools.

**Fireflies Gmail polling uses startup seeding.** `_check_fireflies_gmail()` sets `_fireflies_gmail_seeded = True` on the first scan, adding all existing emails to `_fireflies_email_triggers` without processing any. Only emails that arrive after startup trigger the workflow. Apply this pattern to any future Gmail poller that auto-triggers actions.

**`classify_account()` checks district patterns BEFORE school keywords.** Reversed order is intentional — "Austin Independent School District" must not match "school" before reaching the district check. Parenthetical check `"Name (District)"` runs before district check so "(Medina Valley ISD)" doesn't trigger district classification.

**`_ensure_tab()` always overwrites the header row.** Never use `if not values` to skip the header write. Column schema changes in code must propagate to the sheet immediately on the next import — not just on first use.

**Active Accounts "Account Type" column values: district | school | library | company.** The old boolean `Is District` column is gone. `get_import_summary` filters on `Account Type == "district"`. Do not reintroduce TRUE/FALSE logic.

**`get_districts_with_schools()` targeting logic — DO NOT REVERT.** Active school accounts signal which parent districts to target (we have a foothold → pitch a district-wide deal). Active district accounts = we already have some form of district deal → generally NOT a prospecting target for new business (though they can be expansion targets case by case, and are excellent for referrals/references). The function starts from school accounts, groups by Parent Account, and excludes parent districts that appear as `Account Type == "district"` in Active Accounts. Schools with no Parent Account set are a Salesforce data quality gap and won't appear in call list matching. Sort order: most active schools first (e.g. a district with 10 active schools outranks one with 1).

**CodeCombat's customer types — DO NOT oversimplify.** CodeCombat sells to: school districts, individual schools, libraries, after-school programs, and any organization or individual that wants to teach or learn CS, AI, or coding. "District deals" are not always fully district-wide. The most common structure is a multi-site deal: buying for all middle schools, a subset of high schools, a few elementaries, etc. Fully district-wide contracts are the ultimate goal but relatively rare. Always think in terms of: individual school → multi-site deal → full district contract as the progression.

**Active district accounts: not a primary prospecting target, but not off-limits.** They already have some form of deal. There may be room to expand (e.g. they bought for 7th/8th grade; 9th–12th is untouched). These are case-by-case. Their primary value is as referral sources and references — not cold outreach targets. Scout should not auto-include them in call lists but should surface them as referral/reference candidates when relevant.

**The Leads tab has existing data and must be kept current.** Do not assume the Leads tab is empty. Scout should periodically re-scan and refresh leads data as new research completes. Future feature: scheduled Leads tab freshness check.

**Name ends in "school" (singular) → school. Name ends in "schools" (plural) → district.** "Springfield School" is a school. "Chicago Public Schools" is a district. "sch" as a standalone word (e.g. "Sch of Excellence") → school. These are explicit rules from Steven — do not override with other heuristics.

**call_processor.py must use claude-sonnet-4-6.** `claude-opus-4-5` is deprecated — calling it hangs indefinitely (Anthropic SDK default timeout is 10 minutes). All three `messages.create()` calls in call_processor.py use `claude-sonnet-4-6`. Anthropic client is initialized with `timeout=90.0`. Do not revert this.

**Validate email before calling gas.create_draft().** GAS throws "Invalid argument: Invalid To header" on malformed emails. Always run `_is_valid_email()` before `create_draft()`. If invalid, surface the bad email in the Telegram summary so Steven can correct it with `/call [id] corrected@email.com`.

**`/call` supports optional email override.** Usage: `/call [transcript_id] email@domain.com`. The second token is treated as an email override if it contains `@`. Passed via `tool_input["email_override"]` through execute_tool → `process_transcript(email_override=...)`. Takes priority over Fireflies attendees AND Claude-extracted contact_email. Both the `/call` direct dispatch handler and the `process_call_transcript` execute_tool handler pass it through.

**Post-call summary section is "Key Insights", not "Scout's Take".** Updated in `_format_telegram_summary` in call_processor.py. Do not revert the label.

---

## WHAT SCOUT IS

Scout is Steven's always-on AI sales partner — not just a helper, but a force multiplier. Scout learns Steven's voice, territory, customers, and patterns over time and uses that knowledge to proactively multiply his efforts: researching prospects, building sequences, processing calls, generating daily priorities, surfacing pipeline insights, drafting custom outreach, and executing workflows that would otherwise take hours. The goal is for Scout to handle the operational and analytical heavy lifting so Steven can focus on relationships and closing. Scout is designed to be taught, trained, and expanded — every session makes it smarter and more capable.

Communicates via Telegram (@coco_scout_bot). Runs 24/7 on Railway.app.
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
│   ├── daily_call_list.py      ← Phase 6D. build_daily_call_list(), write_call_list_to_doc(), format_for_telegram()
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
sheets_writer.get_leads(state_filter="") -> list[dict]  # Phase 6D: all leads from Leads tab
sheets_writer.get_master_sheet_url()
sheets_writer.log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)
sheets_writer.ensure_sheet_tabs_exist()
# Tabs created: Leads, No Email, Research Log, Activities, Active Accounts, Goals, Salesforce Import
# from tools.sheets_writer import SheetsWriter  ← CRASHES — class does not exist
```

### activity_tracker (`tools/activity_tracker.py`) — MODULE, NOT A CLASS (Phase 6C)
```python
import tools.activity_tracker as activity_tracker
activity_tracker.log_activity(activity_type, district="", contact="", notes="", source="scout", message_id="")
# activity_type: "research_job" | "sequence_built" | "email_drafted" | "email_saved" | "call_logged" | "pandadoc_event" | "dialpad_call" | "call_list_generated"
activity_tracker.get_today_activities(date_str=None) -> list[dict]
activity_tracker.get_activity_summary(date_str=None) -> dict  # {research_job: N, ..., summary_text: str}
activity_tracker.get_goals() -> list[dict]
activity_tracker.set_goal(goal_type, daily_target, description="")
activity_tracker.get_daily_progress(date_str=None) -> dict  # {calls_made: {target, actual, pct}, ..., progress_text: str}
activity_tracker.is_activity_logged(message_id) -> bool
activity_tracker.scan_pandadoc_notifications(gas_bridge) -> list[dict]
activity_tracker.scan_dialpad_summaries(gas_bridge) -> list[dict]
activity_tracker.sync_gmail_activities(gas_bridge) -> dict  # {pandadoc_logged, dialpad_logged, already_seen}
activity_tracker.build_brief_data_block(date_str=None) -> str  # injected into morning/EOD prompts
# SYNC function — call via run_in_executor from async context
```

### csv_importer (`tools/csv_importer.py`) — MODULE, NOT A CLASS (Phase 6C)
```python
import tools.csv_importer as csv_importer
csv_importer.import_accounts(csv_text: str) -> dict
# {imported, districts, schools, libraries, companies, skipped, errors}
# Clears Active Accounts tab, rewrites fresh from CSV string
# Column schema: Name Key | Display Name | Parent Account | SF Type | Account Type |
#                Open Renewal | Opportunities | Active Licenses | 2025 Revenue |
#                Lifetime Revenue | Last Activity | Last Modified | State
# Account Type values: district | school | library | company

csv_importer.classify_account(account_name, parent_account, sf_type) -> str
# Returns "district" | "school" | "library" | "company"

csv_importer.get_active_accounts(state_filter="") -> list[dict]
csv_importer.get_districts_with_schools() -> list[dict]  # Phase 6D: parent districts with ≥1 active school account
# Starts from school accounts → groups by Parent Account → excludes districts already in Active Accounts as "district" type
# Sorted by school count descending. DO NOT revert to filtering on Account Type == "district".
csv_importer.normalize_name(name: str) -> str  # strips ISD/USD/etc + parenthetical tags
csv_importer.get_import_summary() -> str  # one-line status: N accounts by type, N districts with schools
```

### daily_call_list (`tools/daily_call_list.py`) — MODULE, NOT A CLASS (Phase 6D)
```python
import tools.daily_call_list as daily_call_list
daily_call_list.build_daily_call_list(max_contacts=10) -> dict
# {success, cards: list[dict], district_count, total_matched, error}
# Synchronous — call via run_in_executor from async context

daily_call_list.write_call_list_to_doc(cards, gas_bridge, folder_id=None) -> dict
# {success, url, error} — creates Google Doc via GAS bridge
# Uses CALL_LIST_FOLDER_ID env var, falls back to SEQUENCES_FOLDER_ID

daily_call_list.format_for_telegram(cards, doc_url="") -> str
# Compact preview: name, title, district, school count, email

# Card dict keys:
# contact_name, title, email, phone, district, state,
# school_count, schools: list[str], talking_point, is_backfill
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
await processor.process_transcript(transcript_id, progress_callback=None, email_override="") -> dict
# {telegram_summary, recap_email, salesforce_block, outreach_row, draft_url, error}
# email_override: if set, skips Fireflies attendee lookup and extracted contact_email — use for malformed emails
```
`_create_brief_doc` returns: `"https://docs.google.com/..."` | `"ERROR:<msg>"` | `""` (folder ID not set)

---

## CLAUDE TOOLS (23 total, all in claude_brain.py + handled in main.py)

`research_district`, `get_sheet_status`, `get_research_queue_status`, `train_voice`, `draft_email`, `save_draft_to_gmail`, `get_calendar`, `log_call`, `create_district_deck`, `push_code`, `list_repo_files`, `get_file_content`, `build_sequence`, `ping_gas_bridge`, `grade_draft`, `add_template`, `process_call_transcript`, `get_pre_call_brief`, `get_activity_summary`, `get_accounts_status`, `set_goal`, `sync_gmail_activities`, `generate_call_list`

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
| `/call [transcript_id or url]` | manual post-call processing (Phase 5). Optional email override: `/call [id] correct@email.com` |
| `/progress` or `/kpi` | show today's activity counts vs KPI goals (direct dispatch) |
| `/sync_activities` | scan Gmail for PandaDoc + Dialpad events, log new ones (direct dispatch) |
| `/set_goal [type] [target]` | update KPI daily target e.g. `/set_goal calls_made 15` (direct dispatch) |
| `/call_list` or `call list` or `who should i call` | generate daily call list — 10 prioritized contacts (direct dispatch) |
| send a `.csv` file | triggers Salesforce active accounts import via `handle_document()` |

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
