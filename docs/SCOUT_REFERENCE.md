# SCOUT — Reference (extracted from CLAUDE.md)
*Last updated: 2026-04-09 — End of Session 52. Moved out of CLAUDE.md to keep that file under the 40k char performance limit.*

This file contains the static reference material that used to live in CLAUDE.md: repo tree, Railway env vars, Claude tool registry, and the full Telegram shorthand command list. CLAUDE.md keeps a one-line pointer to this file. Read on demand — not loaded each session.

---

## REPO STRUCTURE

```
firstcocoagent/
├── CLAUDE.md                   ← project-wide rules (kept lean)
├── SCOUT_PLAN.md               ← active plan + completed feature notes
├── SCOUT_HISTORY.md            ← bug log + changelog (not loaded each session)
├── docs/SCOUT_REFERENCE.md     ← THIS FILE: repo tree, env vars, tools, commands
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
│   ├── lead_importer.py        ← MODULE not class. import_leads(), import_contacts(), enrich
│   ├── proximity_engine.py     ← MODULE not class. C5: proximity search, ESA mapping
│   ├── signal_processor.py     ← MODULE not class. Signal intelligence: Gmail parsing, classification, scoring
│   ├── email_drafter.py        ← MODULE not class. Auto-draft Gmail replies in Steven's voice
│   ├── charter_prospector.py   ← F6 MODULE. Charter CMO seed list loader + queue functions
│   ├── cte_prospector.py       ← F7 MODULE. CTE center seed list loader + queue functions
│   ├── private_schools.py      ← F8 MODULE. Private school Serper discovery + diocesan/chain seed
│   ├── compliance_gap_scanner.py ← F9 MODULE. Serper PDF + Claude Sonnet document input (CA/IL/MA pilot)
│   └── fireflies.py            ← FirefliesClient, FirefliesError
├── gas/
│   ├── CLAUDE.md               ← GAS deployment checklist and gotchas
│   └── Code.gs                 ← Deployed at script.google.com as "Scout Bridge"
├── prompts/
│   ├── system.md
│   ├── morning_brief.md
│   ├── eod_report.md
│   ├── sequence_templates.md   ← 18 archetypes
│   └── reply_draft.md          ← Email drafting workflow instructions
├── memory/
│   ├── preferences.md
│   ├── context_summary.md
│   ├── voice_profile.md
│   ├── response_playbook.md    ← 14 reply categories from 150+ emails
│   ├── draft_log.md            ← Draft tracking for learning loop
│   └── sequence_building_rules.md
└── docs/
    ├── CHANGELOG.md
    ├── DECISIONS.md
    ├── SETUP.md
    ├── SETUP_PHASE5.md
    └── SCOUT_REFERENCE.md      ← this file
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
| GOOGLE_SHEETS_TERRITORY_ID | Separate sheet for territory data (falls back to main sheet) |
| GOOGLE_SERVICE_ACCOUNT_JSON | Full JSON string, personal account |
| GAS_WEBHOOK_URL | **Update every time Code.gs gets new deployment** |
| GAS_SECRET_TOKEN | Must match Code.gs |
| FIREFLIES_API_KEY | app.fireflies.ai → Account → API |
| FIREFLIES_WEBHOOK_SECRET | Must match Fireflies webhook config |
| PRECALL_BRIEF_FOLDER_ID | Google Drive folder ID |
| SEQUENCES_FOLDER_ID | Google Drive folder ID. Paste full browser URL — query params stripped automatically. |

**Note:** Phase 5+ env vars (`FIREFLIES_API_KEY`, `FIREFLIES_WEBHOOK_SECRET`, `PRECALL_BRIEF_FOLDER_ID`, `SEQUENCES_FOLDER_ID`) are read via `os.environ.get()` directly — NOT in `config.py`.

---

## CLAUDE TOOLS (25 total, defined in claude_brain.py, handled in main.py)

`research_district`, `get_sheet_status`, `get_research_queue_status`, `train_voice`, `draft_email`, `save_draft_to_gmail`, `get_calendar`, `log_call`, `create_district_deck`, `push_code`, `list_repo_files`, `get_file_content`, `build_sequence`, `ping_gas_bridge`, `grade_draft`, `add_template`, `process_call_transcript`, `get_pre_call_brief`, `get_activity_summary`, `get_accounts_status`, `set_goal`, `sync_gmail_activities`, `generate_call_list`, `discover_prospects`, `find_nearby_prospects`

---

## SHORTHAND COMMANDS (handle_message in main.py)

| Command | Action |
|---------|--------|
| `research [district], [state]`, `look up [district] in [state]` | direct dispatch to research_district — bypasses Claude |
| `proximity [state] [miles]`, `nearby districts in [state]` | find districts near active accounts (C5) |
| `esa [state]`, `service centers in [state]` | ESA/ESC region opportunities (C5) |
| `/signals` | top 5 district signals by heat score |
| `/signals all`, `/signals [state]`, `/signals new` | all signals, state filter, new only |
| `/signal_info N` | full detail on signal #N from last `/signals` list |
| `/signal_act N` | fast-path: mark acted → add to Prospecting Queue → auto-research |
| `/signal_dismiss N` | archive signal (hidden from default view) |
| `/signal_scan` | trigger manual signal scan of Gmail |
| `/signal_stats` | signal counts by type and state |
| `/signal_rss` | manual RSS-only scan (K-12 Dive, eSchool News, CSTA) |
| `/signal_board` | manual BoardDocs agenda scan (25 districts) |
| `/signal_bonds` | manual Ballotpedia bond measure scan |
| `/signal_leadership` | manual superintendent change scan (Serper + Claude, ~$0.03) |
| `/signal_rfp` | manual CS/STEM RFP opportunity scan (Serper + Claude, ~$0.03) |
| `/signal_legislation` | manual CS/STEM education legislation scan (Serper + Claude, ~$0.03) |
| `/signal_grants` | manual CS/STEM grant-funded district scan (Serper + Claude, ~$0.03) |
| `/signal_budget` | manual budget cycle/procurement signal scan (Serper + Claude, ~$0.03) |
| `/signal_algebra` | AI Algebra campaign: find districts adopting math/algebra curriculum (~$0.03) |
| `/signal_cyber` | Cybersecurity pre-launch: find districts with CTE cyber programs (~$0.03) |
| `/prospect_lookalike [state]` | find districts demographically similar to best customers ($0) |
| `/prospect_reengagement` | scan ALL Outreach sequences for finished/no-reply prospects |
| `/signal_roles [state]` | find CS/CTE/STEM leaders via Serper (~$2.50/scan, on-demand) |
| `/signal_csta` | find CSTA chapter leaders/members (~$1.20/scan, on-demand) |
| `/dormant [days]` | show accounts with past activity that went silent (default 90 days) |
| `/export_sequence [name]` | export Outreach sequence to Google Doc |
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
| `/call_list [N]` | generate daily call list (default 10, max 50) |
| `/color_leads` | recolor Leads tab rows by email confidence |
| `/eod` | manually trigger end-of-day report (useful on weekends) |
| `/draft_emails`, `draft my emails` | manually trigger email auto-drafting (also runs every 5 min during business hours) |
| `/draft [name]` | force-draft a specific sender's unread email, bypassing Haiku classification (e.g. `/draft Allison`) |
| `/list_charter_cmos [state]` | read-only view of the 43-CMO seed list (F6) |
| `/prospect_charter_cmos [state]` | queue charter CMOs from the seed list as `charter_cmo` strategy prospects (F6) |
| `/list_cte_centers [state]` | read-only view of the 79-CTE-center seed list (F7) |
| `/prospect_cte_centers [state]` | queue CTE centers from the seed list as `cte_center` strategy prospects (F7) |
| `/discover_coops [state]` | F10 Serper-based homeschool co-op discovery for a state |
| `/discover_private_schools [state]` | F8 Serper-based private school discovery for a state |
| `/prospect_private_networks [state]` | F8 queue the 24 diocesan/chain networks as `private_school_network` strategy |
| `/scan_compliance [state]` | F9 PDF pilot — CS graduation compliance gap scan. Pilot states: CA, IL, MA. Cost ~$0.50-$2/scan. |
| `/prospect_discover [state]` | cold district search via Serper |
| `/prospect_upward` | upward targets from active accounts |
| `/prospect` | show next 5 pending districts |
| `/prospect_all` | full queue grouped by status |
| `/prospect_winback` | scan Closed Lost tab for winback targets (last 12 months) |
| `/prospect_add [name], [state]` | manually add district to queue |
| `/prospect_approve 1,3,5` | approve from last batch, auto-queue research |
| `/prospect_skip 2,4` | skip from last batch |
| `/prospect_clear` | wipe all entries from Prospecting Queue tab |
| `/import_clear` | next CSV upload will clear & rewrite (then resets to merge) |
| `/import_merge` | switch CSV upload back to merge mode (default) |
| `/import_replace_state CA` | next CSV upload replaces only that state's rows; all other states untouched (then resets) |
| `/dedup_accounts` | Remove duplicate rows from Active Accounts tab (uses Name Key + State composite key — fixed Session 18) |
| `/import_leads` | next CSV upload imports as Salesforce leads (SF Leads tab) |
| `/import_contacts` | next CSV upload imports as Salesforce contacts (SF Contacts tab) |
| `/enrich_leads` | run Serper enrichment on unenriched SF Leads (add `contacts` arg for SF Contacts) |
| `/clear_leads` | clear SF Leads + Leads Assoc Active Accounts data rows + shrink grid |
| `/clear_contacts` | clear SF Contacts + Contacts Assoc Active Accounts data rows + shrink grid |
| `/territory_sync [state]` | download NCES territory data for one state or all |
| `/territory_stats [state]` | territory coverage summary (districts, schools, enrollment) |
| `/territory_gaps <state>` | gap analysis: cross-ref territory vs Active Accounts + Prospecting Queue |
| `/territory_map [state]` | generate interactive Folium territory map → Telegram file attachment |
| `/pipeline` | show open pipeline summary with stale alerts |
| `/pipeline_import` | next CSV upload imports as opportunities (Pipeline tab) |
| `/import_closed_lost` | next CSV upload imports as closed-lost opps (Closed Lost tab) |
| send a `.csv` file | Auto-detects opp vs lead vs contact vs account CSV; or Salesforce active accounts import (merge by default) |
| describe CSV before upload | "these are my salesforce leads" / "contacts from salesforce" / "pipeline opps" — sets routing for next CSV upload |
| caption on CSV upload | Same as above — type description as caption when sending the file |
