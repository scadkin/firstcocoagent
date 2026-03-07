# SCOUT — Claude Code Reference
*Last updated: 2026-03-07 — Session 15*

---

## CURRENT STATE — update this after each session

**Phase 6E deployed to Railway. "Scout is online — Phase 6E active" confirmed. End-to-end testing NOT yet done.**

### What still needs to be done (Session 16)
- Test all 7 prospect commands in order:
  1. `/prospect_discover TX` — verify Serper finds districts, dedupes against Active Accounts, adds to Prospecting Queue tab
  2. `/prospect_upward` — verify it finds districts from Active Accounts with school foothold
  3. `/prospect` — verify it shows pending queue with numbered items
  4. `/prospect_approve 1` — verify it marks approved, queues research, and auto-builds sequence on completion
  5. `/prospect_skip 2` — verify it marks skipped
  6. `/prospect_add Austin ISD, TX` — verify manual add
  7. `/prospect_all` — verify grouped status view
- Verify auto-pipeline end-to-end: approve → research runs → `_on_prospect_research_complete` fires → sequence auto-builds → Google Doc created → prospect marked complete in queue
- Verify morning brief shows pending prospects
- Verify hourly check-in suggests idle research targets
- If any bugs found, fix and redeploy

### Current status
- Phases 1–5: ✅ all verified
- Phase 6A (Campaign Engine): ✅
- Phase 6B (Research Engine — 15 layers): ✅
- Phase 6C (Activity Tracking + KPI + CSV Import + Gmail Intel): ✅
- Phase 6D (Daily Call List): ✅
- Phase 6E (District Prospecting Queue): ✅ deployed — awaiting end-to-end verification

### Phase 6 roadmap
- **6E** — District Prospecting Queue ✅ (deployed, testing next)
- **6F** — Pipeline Snapshot (Salesforce opp CSV → lightweight CRM in Sheets, stale follow-up alerts)

---

## CRITICAL RULES

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs are documented in `agent/CLAUDE.md` and `tools/CLAUDE.md`.

**Always produce complete replacement files.** Never give partial snippets or "find line X and replace." Steven uploads full files via GitHub web interface.

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**Top-level imports for flat tool modules.** `activity_tracker`, `csv_importer`, `daily_call_list`, `district_prospector` are imported at the top of main.py like sheets_writer.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result → 400 on next API call.

**Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Both synchronous versions freeze the asyncio event loop.

**Synchronous code called from async context must use `run_in_executor`.** Wrap blocking I/O in `await loop.run_in_executor(None, fn, args...)`. Never call blocking functions directly from async methods.

**Explicit slash commands bypass Claude and call execute_tool() directly.** `/brief`, `/call`, `/recent_calls`, `/progress`, `/sync_activities`, `/call_list`, and all `/prospect_*` commands call execute_tool() directly and return. Direct dispatch is the only reliable pattern — when conversation history is long, Claude responds with descriptive text instead of calling tools.

**`/build_sequence` is a hybrid.** Routes through Claude for clarifying questions. But `execute_tool("build_sequence")` sends output via `await send_message()` directly and returns a short ack string to prevent Claude from rewriting.

**`execute_tool` can send directly to Telegram for long outputs.** For tools that return content Claude tends to rewrite, use `await send_message(full_output)` inside `execute_tool` and return a short ack string.

**Suppress `text_response` when tool_calls are present.** Use `if text_response and not tool_calls:` before sending Claude's text. Tool preamble text is noise.

**Never design workflows that require pasting large text through Telegram.** 4,096 char limit. Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

**GAS bridge: new Code.gs edits need a new deployment version.** See `gas/CLAUDE.md` for the full checklist.

**GAS deployment URL does NOT change when bumping version.** Only need to update Railway env var if creating a brand-new deployment (not editing an existing one).

**Salesforce CSV: Parent Account = always the district.** Account Name can be district/school/library/company. Parent Account filled → sub-unit under that district. Empty → standalone or top-level. One level deep: district → schools.

**Active accounts CSV importer clears and rewrites — not additive.** Each Salesforce export is the full current state.

**CSV uploads decode with utf-8-sig.** Strips BOM from Salesforce/Excel exports.

**Active Accounts "Account Type" column: district | school | library | company.** Old boolean "Is District" column is gone. Do not reintroduce TRUE/FALSE logic.

**Sheet dedup uses email as primary key.** Falls back to `first|last` name for no-email contacts. Don't use name+district — Claude varies district_name spelling.

**Research completion always calls `log_research_job`.** Failure to log is silent.

**`classify_account()` checks district patterns BEFORE school keywords.** "Austin Independent School District" must not match "school" first.

**Name ends in "school" (singular) → school. "schools" (plural) → district.** Explicit rule from Steven.

**District/school names: normalize aggressively, ask when ambiguous.** `normalize_name()` handles abbreviation expansion + suffix stripping. Always normalize both sides before comparing across sources.

**call_processor.py must use claude-sonnet-4-6.** claude-opus-4-5 hangs indefinitely. Anthropic client timeout=90.0.

**Validate email before calling gas.create_draft().** GAS throws on malformed emails.

**`/call_list` must be guarded in the `/call` handler.** `startswith("/call")` matches both. Use `startswith("/call") and not startswith("/call_list")`.

**Call list per-district cap (_MAX_PER_DISTRICT = 2) applies to BOTH priority matches AND backfill.**

**NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement.

**Sequence building rules are in `memory/sequence_building_rules.md`.** Load as context when auto-building sequences.

**`global` declarations go at the TOP of `handle_message()`, not in elif blocks.** Python SyntaxError if `global` appears after first use of the variable. All globals in one line: `global conversation_history, _pending_draft, _last_prospect_batch`.

**`_on_prospect_research_complete` is the auto-pipeline callback.** Runs `_on_research_complete` first (standard flow), then auto-builds a strategy-aware sequence, writes Google Doc, marks prospect complete. Uses `sequence_builder` (lazy import inside the callback). If sequence fails, prospect is still marked complete.

**Two prospecting strategies — upward and cold.** Upward = districts with active school accounts, no district deal. Cold = no CodeCombat presence. Strategy column tracks this. Sequences differ by strategy.

**Prospecting priority tiers (8 levels).** Tier 1 (900+): upward 3+ schools. Tier 2 (800+): upward highest licenses. Tier 3 (700+): cold small/medium. Tier 4 (600+): upward 1 school large district. Tiers 5-7: deferred. Tier 8 (300+): cold large. Small/medium always above large in same tier.

**No Salesforce or Outreach API access.** All data enters Scout via CSV export or Gmail notification parsing. Never design features assuming API access to Salesforce, Outreach, PandaDoc, or Dialpad.

**Outreach handoff pattern for cold sequences.** Scout builds content → Google Doc → Steven copy-pastes into Outreach.io. Do NOT try to replace Outreach with Gmail for cold sequences.

**Fireflies Gmail polling uses startup seeding.** First scan adds all existing emails to set without processing. Only post-startup emails trigger workflows.

**`_ensure_tab()` always overwrites the header row.** Column schema changes must propagate immediately.

**Telegram file upload handler is separate.** `handle_document()` uses `filters.Document.ALL`. Never merge into `handle_message`.

**Railway build cache can serve stale code.** If behavior doesn't match, add a logger.info line and check logs after redeploy. If value doesn't appear, trigger manual redeploy.

**After Railway redeploy, wait for "Scout is online" in Telegram before testing.** 409 Conflict errors during ~30s overlap are normal.

---

## WHAT SCOUT IS

Scout is Steven's always-on AI sales partner — a force multiplier that learns his voice, territory, customers, and patterns. Handles operational/analytical heavy lifting so Steven focuses on relationships and closing.

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

**GAS bridge:** Scout (Railway) → HTTPS POST + secret token → Google Apps Script Web App → Gmail/Calendar/Slides/Docs. Work Google Workspace blocks third-party OAuth; GAS runs inside Google as Steven.

---

## REPO STRUCTURE

```
firstcocoagent/
├── CLAUDE.md                   ← This file (project-wide rules)
├── SCOUT_HISTORY.md            ← Bug log + changelog (not loaded each session)
├── Procfile                    ← "web: python -m agent.main"
├── requirements.txt
├── agent/
│   ├── CLAUDE.md               ← Module APIs for agent/ files
│   ├── main.py                 ← Entry point. Scheduler poll loop. All tool dispatch.
│   ├── config.py               ← Env vars
│   ├── claude_brain.py         ← Claude API + tool definitions + memory injection
│   ├── memory_manager.py       ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py            ← CST-aware Scheduler class, check() only
│   ├── keywords.py             ← Lead research title/keyword list
│   ├── voice_trainer.py        ← Paginated email fetch + paired context analysis
│   ├── call_processor.py       ← Transcript → summary → Google Doc
│   └── webhook_server.py       ← aiohttp server for Fireflies webhook
├── tools/
│   ├── CLAUDE.md               ← Module APIs for tools/ files
│   ├── telegram_bot.py
│   ├── research_engine.py      ← ResearchJob, ResearchQueue (singleton: research_queue)
│   ├── contact_extractor.py
│   ├── sheets_writer.py        ← MODULE not class. write_contacts(), count_leads(), etc.
│   ├── gas_bridge.py           ← GASBridge class
│   ├── github_pusher.py        ← push_file(), list_repo_files(), get_file_content()
│   ├── sequence_builder.py     ← build_sequence(), write_sequence_to_doc()
│   ├── activity_tracker.py     ← MODULE not class. log_activity(), sync_gmail_activities()
│   ├── csv_importer.py         ← MODULE not class. import_accounts(), classify_account()
│   ├── daily_call_list.py      ← MODULE not class. build_daily_call_list()
│   ├── district_prospector.py  ← MODULE not class. discover_districts(), suggest_upward_targets()
│   └── fireflies.py            ← FirefliesClient, FirefliesError
├── gas/
│   ├── CLAUDE.md               ← GAS deployment checklist and gotchas
│   └── Code.gs                 ← Deployed at script.google.com as "Scout Bridge"
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── sequence_templates.md   ← 18 archetypes
├── memory/
│   ├── preferences.md
│   ├── context_summary.md
│   ├── voice_profile.md
│   └── sequence_building_rules.md
└── docs/
    ├── CHANGELOG.md
    ├── DECISIONS.md
    ├── SETUP.md
    └── SETUP_PHASE5.md
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
| GAS_WEBHOOK_URL | **Update every time Code.gs gets new deployment** |
| GAS_SECRET_TOKEN | Must match Code.gs |
| FIREFLIES_API_KEY | app.fireflies.ai → Account → API |
| FIREFLIES_WEBHOOK_SECRET | Must match Fireflies webhook config |
| PRECALL_BRIEF_FOLDER_ID | Google Drive folder ID |
| SEQUENCES_FOLDER_ID | Google Drive folder ID. Paste full browser URL — query params stripped automatically. |

**Note:** Phase 5+ env vars (`FIREFLIES_API_KEY`, `FIREFLIES_WEBHOOK_SECRET`, `PRECALL_BRIEF_FOLDER_ID`, `SEQUENCES_FOLDER_ID`) are read via `os.environ.get()` directly — NOT in `config.py`.

---

## CLAUDE TOOLS (24 total, defined in claude_brain.py, handled in main.py)

`research_district`, `get_sheet_status`, `get_research_queue_status`, `train_voice`, `draft_email`, `save_draft_to_gmail`, `get_calendar`, `log_call`, `create_district_deck`, `push_code`, `list_repo_files`, `get_file_content`, `build_sequence`, `ping_gas_bridge`, `grade_draft`, `add_template`, `process_call_transcript`, `get_pre_call_brief`, `get_activity_summary`, `get_accounts_status`, `set_goal`, `sync_gmail_activities`, `generate_call_list`, `discover_prospects`

---

## SHORTHAND COMMANDS (handle_message in main.py)

| Command | Action |
|---------|--------|
| `/ping_gas`, `ping gas`, `test gas` | ping GAS bridge |
| `/train_voice`, `train voice` | train voice from Gmail (24 months) |
| `/grade_draft`, `grade draft` | feedback on last draft → updates voice_profile.md |
| `/add_template [content]` | add template to voice profile |
| `/list_files`, `/ls` | list repo files |
| `/push_code [filepath]` | fetch-first: read file, ask for changes, edit + push |
| `/build_sequence [name]` | hybrid: Claude asks questions, then builds + sends directly |
| `looks good`, `save it`, `approved` | save pending draft to Gmail |
| `add email: addr@domain.org` | set recipient on pending draft |
| `/brief [meeting name]` | manual pre-call brief |
| `/recent_calls [num]` | recent external calls (1–20) |
| `/call [id] [email]` | post-call processing. Optional email override. |
| `/progress` or `/kpi` | today's activity vs KPI goals |
| `/sync_activities` | scan Gmail for PandaDoc + Dialpad events |
| `/set_goal [type] [target]` | update KPI target |
| `/call_list` | generate daily call list (10 contacts) |
| `/prospect_discover [state]` | cold district search via Serper |
| `/prospect_upward` | upward targets from active accounts |
| `/prospect` | show next 5 pending districts |
| `/prospect_all` | full queue grouped by status |
| `/prospect_add [name], [state]` | manually add district to queue |
| `/prospect_approve 1,3,5` | approve from last batch, auto-queue research |
| `/prospect_skip 2,4` | skip from last batch |
| send a `.csv` file | Salesforce active accounts import |
