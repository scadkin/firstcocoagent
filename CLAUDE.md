# SCOUT — Claude Code Reference
*Last updated: 2026-04-06 — Session 46*

---

## CURRENT STATE — update this after each session

**Session 46: 5 features shipped. Leadership change monitoring (8 superintendent turnovers found). RFP monitoring (CodeCombat-relevant filtering). Legislative signal scanner (2 CS mandates: TX HB 1481, IL CS mandate). Territory map visualization (interactive Folium HTML, 10.3MB, sent via Telegram). BoardDocs noise filtering (false positive rejection). Next: verify Google Alert parser ~April 9, check Tulsa PS bond vote result, enhance territory map detail, continue with unbuilt prospecting strategies.**

### What was done (Session 46)
- **Leadership change monitoring:** `scan_leadership_changes()` — Serper + Claude Haiku across 12 territory states. 8 superintendent changes found on first run (OH, MI). Weekly Monday 8 AM CST. `/signal_leadership` command. BoardDocs keyword expansion for superintendent search/resignation/appointment agenda items. Display-layer risk flagging: active customer leadership changes show "⚠️ ACCOUNT RISK" prefix.
- **RFP monitoring:** `scan_rfp_opportunities()` — Serper + Claude Haiku with aggressive CodeCombat-relevance filtering (CS/STEM/CTE curriculum only, hard-excludes construction/food/devices). 0 results on first run (expected — RFPs are procurement postings, not news). Weekly Monday 8:15 AM CST. `/signal_rfp` command.
- **Legislative signal scanner:** `scan_legislative_signals()` — state CS/STEM/CTE education mandates and policy changes. 2 signals found: TX HB 1481 tech mandate, IL CS education mandate. Monthly 1st Monday 8:30 AM CST. `/signal_legislation` command. Urgency: enacted/signed = urgent, passed committee = time_sensitive.
- **Territory map visualization:** `tools/territory_map.py` — interactive Folium HTML with 5 layers: Active Accounts (green, 18), Pipeline (orange, 12), Prospects (blue, 108), ESAs (purple, 0), All Districts (gray clustered, 7978). Clickable popups. Layer toggles. Sent as Telegram file attachment (10.3 MB). `/territory_map [state]` command. `folium>=0.17.0` added.
- **BoardDocs noise filtering:** `_BOARD_FALSE_POSITIVE` regex rejects tech matches near wheelchair, food service, janitorial, expo, fair, family night, athletic, playground. Checks 50 chars before + 150 chars after each keyword match.
- **Permissions fix:** Global `Bash(*)` in `~/.claude/settings.json` and project `.claude/settings.local.json`. Deny list still blocks rm -rf, dd, mkfs. No more babysitting permission prompts.

### What was done (Session 45)
- Signal system expanded: RSS (3 feeds), BoardDocs (25 districts), Ballotpedia bonds, signal-to-deal attribution. 3 Outreach sequences. Sequence copy rules + send schedules.

### What was done (Session 44)
- Signal Intelligence System: 18,401 signals ($0.30), enrichment ($0.002/signal), job scanner, 10 commands, daily scan, quality pass (150→40). Google Alerts 28→18. DOE newsletters 13 states.

### What still needs to be done
- **Verify Google Alert parser ~April 9** — First new digest with bond/leadership/AI policy keywords. Run `/signal_scan`.
- **Tulsa PS bond vote result** — April 7. Check result, then decide whether to act.
- **Enhance territory map** — More detail in popups (enrollment, school count, licenses). Possibly add signal heat overlay.
- **Unbuilt prospecting strategies** — AI Algebra launch campaign (#23), Cybersecurity pre-launch (#24), grant-funded prospecting (#20), budget cycle targeting (#21).
- **Phase 2 deeper sources** — Ballotpedia superintendent snapshots, state procurement portal scraping for RFPs.
- **Firecrawl paid plan** — Deferred (budget).
- **Parse.bot integration** — Deferred (DNS).
- See `SCOUT_PLAN.md` for full roadmap

### Current status
- All prior phases + enhancements: ✅
- Signal Intelligence System: ✅ (Session 44-47) — 14 sources (Google Alerts, Burbio, DOE, RSS, BoardDocs, Ballotpedia, Job postings, Leadership scan, RFP scan, Legislative scan, Grant scan, Budget scan, Algebra scan, Cybersecurity scan). 22 Telegram commands. Daily 7:45 AM scan + weekly Monday (leadership 8 AM, RFP 8:15 AM) + monthly 1st Monday (legislation 8:30 AM, grants 8:45 AM, budget 9:00 AM). Signal-to-deal attribution wired.
- Outreach sequences: ✅ — IDs 1995-2001 (C4 x4, License Request, Webinar x2). 3 send schedules.
- Sequence copy rules: ✅ — Comprehensive rules in memory. Seasonal calendar. Send schedules.

### Other completed features
- **Lead row coloring (A3):** Auto-colors by confidence after research. `/color_leads` for manual recolor.

### SF Leads & Contacts import (B2, Sessions 24-28) — VERIFIED
- Tabs: SF Leads, SF Contacts (separate from research Leads). Separate sheet: `GOOGLE_SHEETS_SF_ID` env var.
- `/import_leads`, `/import_contacts`, `/enrich_leads`, `/clear_leads`, `/clear_contacts`
- Cross-checks against Active Accounts (email domain, name, district). Math filter tabs for math-related titles.
- Mutually exclusive routing: math+active → math active, math only → math, active only → assoc active, neither → main.
- `lead_importer` is a flat module imported at top of main.py (NOT lazy). Chunked at 2,000 rows.
- Cross-check rules: school-level active accounts only block SAME school. District-level blocks whole district.
- `clear_tab()` uses `values().clear()` + `updateSheetProperties` grid resize (NOT `deleteDimension`).
- "Leads from Research" = renamed research Leads tab. `TAB_LEADS` constant.

### C1 Territory Master List (Sessions 31-32) — VERIFIED
- NCES CCD 2023 data via Urban Institute API. 13 states + CA (SoCal counties only). 8,133 districts, 40,317 schools.
- Separate sheet: `GOOGLE_SHEETS_TERRITORY_ID`. Tabs: Territory Districts, Territory Schools.
- `/territory_sync`, `/territory_stats`, `/territory_gaps`. Cached in `/tmp/` with 7-day TTL.
- **API returns county_code as strings** (e.g., `"6037"`), not integers.
- Gap coverage: only district-level deals = "covered". School account = "upward opportunity".

### C3 Closed-Lost Winback (Session 33) — VERIFIED
- Separate "Closed Lost" tab (NOT Pipeline). `/import_closed_lost`, `/prospect_winback`.
- Date window: `buffer_months=6` + `lookback_months=18`. Strategy: "winback", Source: "pipeline_closed".
- **Why deals close lost:** 61% Unresponsive, 19% Budget, 5% Not using, 4% Turnover, 2% Competitor.
- All sequences are DRAFTS → Google Doc → Steven reviews. Status includes "draft".

### SoCal CSV Filtering (Sessions 25-27) — COMPLETE
- Offline scripts in `scripts/socal_filter*.py`. SoCal counties: LA, SD, Orange, Riverside, San Bernardino, Kern, Ventura, Santa Barbara, SLO, Imperial.

### Outreach.io API (Sessions 34, 38, 43)
- Steven's user ID: **11**. OAuth app: "AI Coco Automation" (Development mode).
- **Write access enabled (Session 38)** for: sequences, sequenceSteps, sequenceStates, sequenceTemplates, templates, prospects. Scoped to sequence creation — do not write to other resources without Steven's approval.
- Tokens persist via GitHub (`memory/outreach_tokens.json`). Railway env vars: `OUTREACH_CLIENT_ID`, `OUTREACH_CLIENT_SECRET`, `OUTREACH_REDIRECT_URI`.
- JSON:API format required. Content-Type: `application/vnd.api+json`.
- **Sequence step interval is in SECONDS** (not minutes). 5 min=300, 4 days=345600, 6 days=518400.
- **Outreach template `toRecipients` MUST be `[]` (empty).** Never set to `["{{toRecipient}}"]` — causes ALL emails to fail with "Invalid recipients." Failed states cannot be retried via API. Steven has to manually click "Try again" on every prospect in the UI.
- Sequence creation flow: create sequence → create steps → create templates → link via sequenceTemplates → Steven activates in UI → Steven toggles templates active → THEN add prospects.
- `enabled` is a private attribute — cannot activate sequences via API. Steven must toggle in UI.
- `sequenceStates` cannot be PATCHed (no resume via API). `sequenceSteps` need delete scope to remove.
- Use `<br><br>` between paragraphs in bodyHtml, NOT `<p>` tags (Outreach renders `<p>` with no spacing).
- Default settings for all sequences: owner=Steven (ID 11), sharing=private, throttleMaxAddsPerDay=150, throttleCapacity=200, maxActivations=200.
- **Can PATCH sequences to change schedule** (Session 43). Set `relationships.schedule.data` to `{type: "schedule", id: <int>}`.
- **Prospect timezone field is `timeZone`** (camelCase), not `timezone`. Can be PATCHed.
- **Cannot read/write schedules via API** (scopes don't exist). Steven creates/edits schedules in the Outreach UI. Three standard schedules: "Teacher Tue-Thu Multi-Window" (teachers), "Admin Mon-Thurs Multi-Window" (admins/district), "Hot Lead Mon-Fri" (inbound/speed). Always assign one to every sequence.
- **C4 sequences:** IDs 1995 (Teachers, 6 steps), 1996 (District/Admin, 5 steps), 1997 (School General, 6 steps), 1998 (District General, 5 steps). Schedule: "C4 Tue-Thu Morning" (ID 50).
- **Steven's info dump template:** ID 43784 ("New referral/info dump email 2026 DRAFT"). Reuse via existing template ID when creating sequence steps.
- **Steven's mailbox for sending:** steven@codecombat.com (ID 11).

### C4 Cold License Requests (Sessions 34-37) — VERIFIED
- Strategy: "cold_license_request" — inbound license requests that went cold. 1,274 targets, $1.38/run.
- `/c4`, `/c4_clear`, `/cleanup_queue`, `/fix_queue`. C4 Audit tab for spot-checking.
- **Email domain ranks higher than company name** (`email_priority=True`). Student emails excluded.
- **Deterministic international detection:** TLDs, foreign edu domains, company name keywords. Do NOT use ambiguous signals ("india" matches "Indiana").
- **Claude JSON preamble fix:** Strip text before `[` and after `]` before json.loads().

---

### Session transcript capture
- Steven starts sessions with `scout` in terminal (not `claude`). This wraps Claude Code with `script` to capture full transcripts.
- Transcripts save to `docs/sessions/session_N.md`. Raw captures in `docs/sessions/.raw/` (gitignored).
- During end-of-session routine: run `python3 scripts/clean_transcript.py "$SCOUT_RAW_TRANSCRIPT" "$SCOUT_CLEAN_TRANSCRIPT"`, then include the clean file in the commit.
- Env vars available: `SCOUT_SESSION_NUM`, `SCOUT_RAW_TRANSCRIPT`, `SCOUT_CLEAN_TRANSCRIPT`.
- Steven uses `/exit` between sessions (not `/clear`) so each `scout` run = one transcript file.
- Wrapper script auto-commits as fallback if end-of-session routine is skipped.
- **Session numbering source of truth is CLAUDE.md header** (`Session N`). The `scout_session.sh` script parses this, transcript files on disk, and raw files — uses the highest. This prevents drift when sessions run without the `scout` wrapper.

---

## CRITICAL RULES

**Always push code changes from Claude Code via git — never tell Steven to use `/push_code` in Telegram.** Scout's `/push_code` dumps entire file contents into Telegram (4,096-char limit) causing truncation and confusion. Always `git add`, `git commit`, `git push` directly from the Claude Code terminal. This is a hard rule established Session 19.

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs are documented in `agent/CLAUDE.md` and `tools/CLAUDE.md`.

**Always produce complete replacement files.** Never give partial snippets or "find line X and replace." Steven uploads full files via GitHub web interface.

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**Top-level imports for flat tool modules.** `activity_tracker`, `csv_importer`, `daily_call_list`, `district_prospector`, `pipeline_tracker`, `lead_importer` are imported at the top of main.py like sheets_writer.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result → 400 on next API call.

**Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Both synchronous versions freeze the asyncio event loop.

**Synchronous code called from async context must use `run_in_executor`.** Wrap blocking I/O in `await loop.run_in_executor(None, fn, args...)`. Never call blocking functions directly from async methods.

**Explicit slash commands bypass Claude and call execute_tool() directly.** `/brief`, `/call`, `/recent_calls`, `/progress`, `/sync_activities`, `/call_list`, `/pipeline`, `/pipeline_import`, `/import_closed_lost`, `/import_leads`, `/import_contacts`, `/enrich_leads`, and all `/prospect_*` commands call execute_tool() directly and return. Direct dispatch is the only reliable pattern — when conversation history is long, Claude responds with descriptive text instead of calling tools.

**`/build_sequence` is a hybrid.** Routes through Claude for clarifying questions. But `execute_tool("build_sequence")` sends output via `await send_message()` directly and returns a short ack string to prevent Claude from rewriting.

**`execute_tool` can send directly to Telegram for long outputs.** For tools that return content Claude tends to rewrite, use `await send_message(full_output)` inside `execute_tool` and return a short ack string.

**Suppress `text_response` when tool_calls are present.** Use `if text_response and not tool_calls:` before sending Claude's text. Tool preamble text is noise.

**Never design workflows that require pasting large text through Telegram.** 4,096 char limit. Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

**GAS bridge: new Code.gs edits need a new deployment version.** See `gas/CLAUDE.md` for the full checklist.

**GAS deployment URL does NOT change when bumping version.** Only need to update Railway env var if creating a brand-new deployment (not editing an existing one).

**Active Accounts "Display Name" column is the account name.** Sheet header currently says "Display Name". Steven wants it renamed to "Active Account Name" — this will happen automatically on next account CSV import (csv_importer rewrites header). Until then, any code reading active accounts must check BOTH column names: `acc.get("Active Account Name", "") or acc.get("Display Name", "")`. The `territory_data.py` gap analysis already has this fallback.

**Urban Institute Education Data API returns county_code as strings, not integers.** `"6037"` not `6037`. All county code comparisons must use string keys.

**Territory gap coverage: school accounts ≠ district coverage.** Only district-level Active Account deals count as "covered." A school account inside a district is an "upward opportunity," not coverage. Coverage % = district deals / total NCES districts.

**Salesforce CSV: Parent Account = always the district.** Account Name can be district/school/library/company. Parent Account filled → sub-unit under that district. Empty → standalone or top-level. One level deep: district → schools.

**CSV import default mode is MERGE (non-destructive).** Matches by Name Key: updates existing rows, appends new ones, leaves unmatched rows untouched. `/import_clear` switches to clear-and-rewrite mode for the next upload only — but still respects auto-detect routing (accounts vs pipeline). `/import_merge` switches back explicitly. `/import_replace_state CA` replaces only rows matching that state — all other states untouched (always routes to Active Accounts).

**`/dedup_accounts` uses Name Key + State as composite key (fixed Session 18).** Safe to use — will not merge same-named schools from different states.

**`merge_accounts()` auto-deduplicates existing rows before merging.** If multiple rows share the same Name Key, keeps only the last one. Prevents duplicate buildup from repeated uploads (fixed Session 21).

**`cleanup_and_format_sheets()` runs on startup.** Deletes unused tabs (Sheet1, Salesforce Import), applies alternating row banding (white/light gray-blue) to all tabs. Safe to call repeatedly — skips already-banded tabs.

**`get_districts_with_schools()` state key is `"State"` (capital S).** Active Accounts sheet rows use capital-S key. Using `s.get("state")` returns empty string — always use `s.get("State")`. Fixed Session 19.

**CSV importer preserves ALL columns from the Salesforce export.** Known columns are mapped to internal keys via `_SF_COL_MAP`. Unknown columns pass through with their original CSV header name. The sheet header row extends dynamically.

**Always normalize Salesforce/Outreach names to sentence case.** Account names, opp names, contact names, and parent accounts often come in ALL CAPS. Convert to natural title case ("ARLINGTON ISD" → "Arlington ISD") while preserving known acronyms (ISD, HS, STEM, etc.). Applies to any import, display, or use in sequences/emails.

**CSV uploads decode with utf-8-sig.** Strips BOM from Salesforce/Excel exports.

**Pipeline tab uses REPLACE ALL on import — not merge.** Pipeline is a point-in-time snapshot. Every opp CSV upload clears and rewrites the entire Pipeline tab.

**Pipeline importer preserves ALL CSV columns.** Known columns mapped via `_OPP_COL_MAP`, unknown columns pass through with original header name. Same dynamic header pattern as csv_importer.

**Auto-detect CSV routing by headers.** Priority: pipeline > sf_leads > sf_contacts > accounts. Pipeline: 2+ of {Stage, Close Date, Opportunity Name} without account-only columns. SF Leads: 2+ of {Lead Source, Lead Status, Company} without account-only columns. SF Contacts: 2+ of {Account Name, Department, Contact Owner} + name columns without account-only columns. Everything else → Active Accounts. `/import_replace_state` overrides auto-detect and forces account import. `/import_clear` sets clear mode but still respects auto-detect routing. `/import_leads` and `/import_contacts` force SF Leads/Contacts routing.

**Natural language CSV description overrides auto-detect.** Steven can describe what a CSV is before uploading (or as a caption on the file). `_parse_csv_intent()` detects keywords: pipeline/opportunity → Pipeline tab; lead/salesforce lead → SF Leads tab; contact/salesforce contact → SF Contacts tab; account/customer → Active Accounts; prospect → Active Accounts. Priority: slash commands > caption > pre-message description > auto-detect.

**Pipeline uses 3-tier stale alerts.** 🟠 Needs Update (14+ days), 🟡 Needs Check-In / Going Stale (30+ days), 🔴 Risk Going Cold! (45+ days). Past-due Close Date also triggers. Empty Last Activity is NOT flagged (no data ≠ stale). Thresholds are constants in pipeline_tracker.py (TIER_NEEDS_UPDATE, TIER_GOING_STALE, TIER_GOING_COLD).

**Active Accounts "Account Type" column: district | school | library | company.** Old boolean "Is District" column is gone. Do not reintroduce TRUE/FALSE logic.

**Sheet dedup uses email as primary key.** Falls back to `first|last` name for no-email contacts. Don't use name+district — Claude varies district_name spelling.

**Research completion always calls `log_research_job`.** Failure to log is silent.

**`classify_account()` checks district patterns BEFORE school keywords.** "Austin Independent School District" must not match "school" first.

**Name ends in "school" (singular) → school. "schools" (plural) → district.** Explicit rule from Steven.

**District/school names: normalize aggressively, ask when ambiguous.** `normalize_name()` handles abbreviation expansion + suffix stripping. Always normalize both sides before comparing across sources.

**call_processor.py must use claude-sonnet-4-6.** claude-opus-4-5 hangs indefinitely. Anthropic client timeout=90.0.

**`agent/target_roles.py` is the authoritative lead targeting filter.** Contains TIER1/TIER2 titles, CTE relevant/exclude keywords, IT infra exclusions, and `is_relevant_role()` function. Used by `contact_extractor.py` post-extraction. Source: Steven's "ROLES and KEYWORDS" doc.

**Research engine has 20 layers in 5 parallel phases.** Phase A (parallel): L1,L2,L3,L5,L16,L20. Phase B: L4 (domain discovery). Phase C (parallel): L6,L11-L14,L17-L19. Phase D: L7,L8. Phase E: L9→L10→L15→L10. New layers: L16 (Exa broad), L17 (Exa domain-scoped), L18 (Firecrawl extract — needs paid plan), L19 (Firecrawl site map — needs paid plan), L20 (Brave Search).

**Firecrawl paid plan deferred (budget).** L18/L19 skip gracefully when FIRECRAWL_API_KEY has no credits. Was the #1 tool discovery — schema-based extraction pulled 10-20 verified contacts per district. Circle back when budget allows.

**Contact extractor max_tokens is 4000 (not 2000).** School directory pages with 15+ contacts were causing JSON truncation. Fixed Session 40.

**`proximity_engine.py` is a flat module imported at top of main.py.** Two modes: targeted (`proximity Leander ISD` — near one account) and state sweep (`proximity Texas all` — all accounts). `add nearby 1,4,8` queues from last results. ESA mapping via `esa Texas`. All direct dispatch, no Claude routing.

**ESA mapping uses NCES Agency Type 4 data.** True ESCs have 0 schools + 0 enrollment (administrative entities). Career-tech centers have enrolled students (JVSDs, career campuses). Both are Agency Type 4 but classified separately. ESCs used for regional mapping; career-tech shown as separate prospecting targets.

**`_last_proximity_result` is in-memory only — lost on bot restart.** Run `proximity [account]` before `add nearby` in a new session.

**ESA_PATTERNS in target_roles.py has 78 entity name variations.** From Steven's ROLES and KEYWORDS doc. Covers ESC, BOCES, IU, COE, ROE, ISC, ESU, AEA, CESA, SELPA, JPA, SSA, and dozens more.

**`signal_processor.py` is a flat module imported at top of main.py.** 14 signal sources: Google Alerts (regex), Burbio (Claude), DOE (Claude), RSS (feedparser), BoardDocs (HTTP scraping), Ballotpedia (HTTP scraping), Job postings (JobSpy), Leadership scan (Serper + Claude), RFP scan (Serper + Claude), Legislative scan (Serper + Claude), Grant scan (Serper + Claude), Budget scan (Serper + Claude), Algebra scan (Serper + Claude), Cybersecurity scan (Serper + Claude). Signals Database tab (18 columns including Pipeline Link). 22 Telegram commands, all direct-dispatch. Daily scan at 7:45 AM CST. Weekly Monday: leadership 8 AM + RFP 8:15 AM. Monthly 1st Monday: legislation 8:30 AM + grants 8:45 AM + budget 9:00 AM. Algebra/cybersecurity scans are on-demand only (`/signal_algebra`, `/signal_cyber`). All ~$0.03/scan each. BoardDocs/Ballotpedia/RSS wrapped in try/except (non-fatal). `_last_signal_batch` is in-memory — run `/signals` before `/signal_act` or `/signal_info` in a new session.

**Signal enrichment must run before acting on signals.** Never queue a district based on a headline alone. `enrich_signal()` does Serper web search + Claude Haiku analysis for CodeCombat relevance (strong/moderate/weak/none). A $6.2B bond can be WEAK if it's all devices. A no-dollar STEAM coordinator hire can be STRONG. Auto-runs on Tier 1 during daily scans; manual via `/signal_enrich N`.

**Google Alerts are weekly digests with all keywords bundled into one email.** Format: `=== News - N new results for [KEYWORD] ===` sections. Parser normalizes `\r\n` to `\n`. `body_limit=65000` required (digests are ~56K chars). ~80 stories per digest.

**`/signals` defaults to territory-only.** `format_hot_signals(territory_only=True)` filters to 13 states + SoCal. Pass state_filter for single-state view. `_last_signal_batch` is also territory-filtered.

**Bond/leadership/RFP signals use urgency="time_sensitive" with minimal decay.** Standard Tier 1 decay is 0.93/week. Time-sensitive signals use 0.97/week because the opportunity window matters more than email age.

**Validate email before calling gas.create_draft().** GAS throws on malformed emails.

**`/call_list` must be guarded in the `/call` handler.** `startswith("/call")` matches both. Use `startswith("/call") and not startswith("/call_list")`.

**Call list per-district cap (_MAX_PER_DISTRICT = 2) applies to BOTH priority matches AND backfill.**

**NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement.

**ALL sequences are drafts — always show for Steven's approval.** Write to Google Doc, share link in Telegram, mark prospect as "draft" status. Never auto-finalize or auto-mark "complete". Steven reviews and either approves or gives feedback on changes. This applies to ALL strategies (upward, cold, winback), not just winback.

**Sequence building rules are in `memory/sequence_building_rules.md`.** Load as context when auto-building sequences.

**`scheduler` is a module-level global in main.py.** It must be instantiated at module scope (alongside `memory` and `conversation_history`), not inside `_run_telegram_and_scheduler()`. If it's local to that function, `handle_message()` can't access it and all message handling silently dies. Fixed Session 23.

**`global` declarations go at the TOP of `handle_message()`, not in elif blocks.** Python SyntaxError if `global` appears after first use of the variable. All globals in one line: `global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _pending_csv_intent, _last_proximity_result`.

**`_on_prospect_research_complete` is the auto-pipeline callback.** Runs `_on_research_complete` first (standard flow), then auto-builds a strategy-aware sequence, writes Google Doc, marks prospect complete. Uses `sequence_builder` (lazy import inside the callback). If sequence fails, prospect is still marked complete.

**`sequence_builder.build_sequence()` uses max_tokens=6000 and retries once on JSON parse failure.** First attempt uses A/B variants. If JSON parse fails, retries with `ab_variants=False` (simpler, smaller response). Large districts (LAUSD etc.) can produce malformed JSON on first attempt due to long email bodies.

**`/prospect_approve` checks Active Accounts before queuing research.** If any approved district is already an active customer (Account Type == "district"), Scout warns and asks yes/no. `_pending_approve_force` global holds flagged districts awaiting confirmation. Replying "yes"/"confirm"/"proceed" queues them anyway; "no"/"skip"/"cancel" clears them. Clean districts (not active customers) are queued immediately without interruption.

**`_last_prospect_batch` is in-memory only — lost on bot restart.** Always run `/prospect` before `/prospect_approve` or `/prospect_skip` in a new session or after any Railway redeploy. The batch is not persisted to disk or Sheets.

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
│   ├── lead_importer.py        ← MODULE not class. import_leads(), import_contacts(), enrich
│   ├── proximity_engine.py     ← MODULE not class. C5: proximity search, ESA mapping
│   ├── signal_processor.py     ← MODULE not class. Signal intelligence: Gmail parsing, classification, scoring
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
