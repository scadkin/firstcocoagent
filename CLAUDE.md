# SCOUT — Claude Code Reference
*Last updated: 2026-03-12 — Session 33*

---

## CURRENT STATE — update this after each session

**Session 33: C3 Closed-Lost Winback Strategy fully implemented. Separate "Closed Lost" tab + `/import_closed_lost` for CSV upload. `/prospect_winback` scans for targets. ALL sequences (not just winback) are now drafts for Steven's review. Needs closed-lost CSV from Salesforce to test end-to-end.**

### What was done (Session 33)
- **C3 Closed-Lost Winback** — full implementation:
  - Separate "Closed Lost" tab (not Pipeline tab) — Steven's closed-lost opps aren't in his pipeline data
  - `/import_closed_lost` command + natural language routing ("closed lost" / "winback" in caption)
  - `import_closed_lost()` in `pipeline_tracker.py` — REPLACE ALL, same CSV format as pipeline
  - `get_closed_lost_opps()` reads from Closed Lost tab first, falls back to Pipeline
  - `suggest_closed_lost_targets()` in `district_prospector.py` — groups by district, dedupes, adds with strategy="winback"
  - `/prospect_winback` (also `/winback`) — scans for targets, adds to Prospecting Queue
  - Priority scoring 550-749 (between upward and cold), scaled by deal amount
  - Rich winback context: Outreach.io variables, reply emails, incentivization, breakup email, loss-reason context (85% budget, 15% competitor)
- **ALL sequences are now drafts** — not just winback. Every auto-built sequence (upward, cold, winback) writes to Google Doc, shares link, marks status="draft". Steven reviews before finalizing. Never auto-complete.
- **New "draft" status** in Prospecting Queue (between researching and complete)

### What still needs to be done (Session 34+)
- **Steven needs to export Closed Lost Opportunities report from Salesforce** and upload CSV to Scout (use `/import_closed_lost` first) — this is required to test `/prospect_winback` end-to-end
- **C4: Unresponsive leads strategy** (next up per roadmap)
- **Active Accounts column rename:** "Display Name" → "Active Account Name" — will take effect on Steven's next account CSV import. All code already has fallback for both names.
- Enrichment logic improvement

### Current status
- Phases 1–5: ✅ all verified
- Phase 6A (Campaign Engine): ✅
- Phase 6B (Research Engine — 15 layers): ✅
- Phase 6C (Activity Tracking + KPI + CSV Import + Gmail Intel): ✅
- Phase 6D (Daily Call List): ✅
- Phase 6E (District Prospecting Queue): ✅ fully verified (Session 19)
- Phase 6F (Pipeline Snapshot): ✅ fully verified (Session 22)
- Enhancements A1-A3 + B1: ✅ implemented (Session 23)
- Enhancement B2: ✅ fully verified (Session 30) — all 8 tests passed
- Enhancement C1 (Territory Master List): ✅ fully verified (Session 32)
- Enhancement C3 (Closed-Lost Winback): ✅ implemented (Session 33) — needs closed-lost CSV to verify
- SoCal CSV filtering: ✅ 5 passes complete (Session 26)

### Phase 6 roadmap
- **6E** — District Prospecting Queue ✅ complete
- **6F** — Pipeline Snapshot ✅ complete (Session 22)

### Weekend scheduler (B1, Session 23)
- Saturday: greeting at 11:00am CST, Sunday: greeting at 1:00pm CST
- No auto check-ins or auto EOD on weekends
- `/eod` command triggers EOD report manually (works any day)
- `scheduler.mark_user_active_today()` called from `handle_message()` on weekends — suppresses auto-greeting if Steven messages first
- `_is_user_active_today()` resets daily (compares against current date)

### Lead row coloring (A3, Session 23)
- `_color_leads_by_confidence()` auto-runs after `write_contacts()` appends to Leads tab
- `/color_leads` command recolors all existing rows (one-time cleanup)
- Colors: VERIFIED/HIGH = light green, LIKELY/MEDIUM = yellowish-green, INFERRED/LOW = light yellow, UNKNOWN = light grey
- Batches in chunks of 500 requests for Sheets API safety

### SF Leads & Contacts import (B2, Session 24)
- Two new tabs: **SF Leads** (from Salesforce Leads report) and **SF Contacts** (from Salesforce Contacts report)
- SEPARATE from the existing Leads tab (which is research-generated contacts)
- `/import_leads` — next CSV goes to SF Leads tab; `/import_contacts` — next CSV goes to SF Contacts tab
- Auto-detect: lead CSV has 2+ of {Lead Source, Lead Status, Company}; contact CSV has 2+ of {Account Name, Department, Contact Owner} + name columns
- Auto-detect priority: pipeline > sf_leads > sf_contacts > accounts
- Natural language: "salesforce leads" / "my leads" routes to SF Leads; "contacts" / "sf contacts" routes to SF Contacts
- Cross-checks each record against Active Accounts by email domain, account/company name, and district name
- Enrichment columns: Verified School, Verified District, Verified State, Verified County (CA only), Active Account Match, Enrichment Status, Enrichment Notes, Last Enriched, Date Imported
- `/enrich_leads` runs Serper web search on unenriched records (up to 20 at a time); `/enrich_leads contacts` for SF Contacts tab
- `_leads_import_mode` global: None | "leads" | "contacts" — resets after use (same pattern as `_pipeline_import_mode`)
- `lead_importer` is a flat module imported at top of main.py (NOT lazy)
- Large CSV imports chunked at 2,000 rows per batch with 3-attempt retry + 2s/4s backoff
- Append range uses tight `A:{last_col}` based on header count (NOT `A:AZ`) — prevents 10M cell limit hits
- Two extra tabs: **Leads Assoc Active Accounts** and **Contacts Assoc Active Accounts** — populated during import with cross-checked records only
- Four math filter tabs: **SF Leads - Math**, **Leads Assoc Active - Math**, **SF Contacts - Math**, **Contacts Assoc Active - Math** — leads/contacts with math/algebra/mathematics/calculus/geometry in Title auto-routed here
- **Mutually exclusive routing** — each record goes to exactly ONE tab: (1) math + active → math active, (2) math only → math, (3) active only → assoc active, (4) neither → main. No duplicates across tabs.
- `/clear_leads` — clears all 4 SF Leads tabs (main + active + math + math active) data rows + shrinks grid
- `/clear_contacts` — clears all 4 SF Contacts tabs (main + active + math + math active) data rows + shrinks grid
- `clear_tab()` uses `values().clear()` + `updateSheetProperties` grid resize (NOT `deleteDimension` which fails on frozen rows)
- **Separate Google Sheet for SF imports** — `GOOGLE_SHEETS_SF_ID` env var. `_get_sf_sheet_id()` reads it (falls back to main sheet). All SF lead/contact operations use this. Cross-check still reads Active Accounts from main sheet via `csv_importer`.
- **Tab formatting** — `_format_tab()` runs after every import: column widths sized to header text (~7px/char), alternating row banding (blue header, white/light gray-blue), frozen row 1. Replaced `_auto_resize_columns()`.
- **Column order** — State/Province first, then name/title/company/email, then Active Account Match right after Email, then Last Enriched right after that, then remaining columns.
- **State column first** — State/Province is column A in both SF Leads and SF Contacts schemas
- **"Leads from Research"** — the research-generated Leads tab was renamed from "Leads". `TAB_LEADS` constant in sheets_writer.py. Auto-migration renames on startup via `cleanup_and_format_sheets()`.

### Cross-check rules (B2, Sessions 27-28)
- **Exact Match - School**: lead's company = same school as active account → match
- **Exact Match - District**: lead's company = same district as active account → match
- **District is Active Account**: active account is a district-level deal, lead is at any school or the district itself → match
- **NOT a match**: active account is just a school, lead is at a DIFFERENT school or the district → Steven can freely prospect
- Key rule: school-level active accounts only block the SAME school. District-level active accounts block the whole district.
- Pre-built lookup structures: `_build_account_lookups()` runs once per import, creates by_name, districts_by_name, schools_by_parent, domain_to_accounts dicts
- Email domain matching: `_generate_domain_roots()` creates plausible roots from account names (e.g., "Austin ISD" → {"austinisd", "austin", "aisd"})
- `_generate_domain_roots()` now includes **acronym-based roots**: first letters of all words → "Los Angeles Unified School District" → "lausd"; also acronym + suffixes → "Cypress-Fairbanks ISD" → "cfisd"
- `_extract_domain_root()` handles k12-style domains (spring.k12.tx.us → "spring") and multi-level domains (staff.austinisd.org → "austinisd")
- State filtering: matches require same state (or either side blank)
- **Step 2 (District Name) validation**: Salesforce District Name field is unreliable — leads can be tagged to wrong district. If lead has non-generic institutional email, domain root must match the matched district's generated roots. Generic emails (gmail etc.) still trust SF data. `_domain_matches_account()` handles this check.
- Uses lead's District Name and Parent Account fields for district detection (Step 2)
- `_classify_lead_company()` uses `csv_importer.classify_account()` to determine if lead's company is a school vs district

### C1 Territory Master List (Sessions 31-32)
- Data source: Urban Institute Education Data API (`educationdata.urban.org`), wrapping NCES CCD 2023
- No auth required, JSON responses, filter by FIPS state code
- 13 states: IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE, TX + CA (SoCal counties only)
- CA filtered by `county_code` to 10 SoCal counties — **API returns county_code as strings** (e.g., `"6037"`), not integers
- Separate Google Sheet: `GOOGLE_SHEETS_TERRITORY_ID` env var (falls back to main sheet)
- Two tabs: `Territory Districts` (17 columns) and `Territory Schools` (18 columns)
- `/territory_sync [state]` — downloads + writes to sheet; processes one state at a time
- `/territory_stats [state]` — coverage summary by state
- `/territory_gaps <state>` — cross-refs against Active Accounts + Prospecting Queue; creates Google Doc for 20+ uncovered
- API responses cached in `/tmp/territory_{kind}_{state}.json` with 7-day TTL (cleared on Railway redeploy)
- Sync clears existing rows for each state before writing (idempotent re-sync)
- Chunked writes at 2,000 rows with 3-attempt retry
- `territory_data` is a flat module imported at top of main.py
- **Gap analysis coverage rules:** district-level Active Account deal = "covered". School account in a district = "upward opportunity" (NOT coverage). Coverage % only counts district deals. Unmatched schools (private/charter not in NCES) shown separately with ⚠️.
- **Full territory size:** 8,133 districts, 40,317 schools, 20.6M students across all states

### C3 Closed-Lost Winback (Session 33)
- **Data source:** Separate Salesforce "Closed Lost Opportunities" report CSV — NOT from Pipeline tab
- **Closed-lost opps are not in Steven's pipeline data.** He must run a dedicated report in Salesforce, export CSV, upload to Scout
- `/import_closed_lost` — sets next CSV upload to route to the "Closed Lost" tab (dedicated, separate from Pipeline)
- Natural language: "closed lost" / "winback" in caption or pre-message also routes to Closed Lost tab
- `get_closed_lost_opps()` reads from Closed Lost tab first, falls back to Pipeline tab
- Filter: Close Date within last 12 months (configurable via `months_back` param)
- Groups by district: uses Parent Account if available, else Account Name
- `/prospect_winback` (also `/winback`) — scans Closed Lost tab, adds to Prospecting Queue
- Strategy label: `"winback"`, Source: `"pipeline_closed"`
- Priority 550-749: higher deal amounts score higher. Between upward (600-999) and cold (300-700)
- Dedupes against Active Accounts (skips — they're already customers) and existing Prospecting Queue
- Notes field captures: opp count, total value, last close date, opp names
- **Winback sequences are DRAFTS** — written to Google Doc, link shared in Telegram, Steven reviews before finalizing. Status set to "draft" (not "complete") until approved.
- **Sequence requirements:** 5 steps, Outreach.io variables ({{first_name}}, {{state}}, {{company}}), at least one "reply" email, highlight what's new/improved, include incentivization, breakup email last
- **Why deals close lost:** ~85% budget/cost rejection (teachers go unresponsive after admin says no), ~15% competitor chosen (don't understand full offering). Teachers get discouraged asking admins.
- Status values now include "draft" between "researching" and "complete"

### Merged territory CSV files (Session 27)
- `~/Downloads/My merged leads list - Including SoCal - as of 3-7-26.csv` — 86,993 leads (all territory states + SoCal)
- `~/Downloads/My merged contacts list - Including SoCal - as of 3-7-26.csv` — 19,775 contacts (all territory states + SoCal)
- Non-SoCal files use latin-1 encoding; merged output is utf-8-sig
- SoCal rows have County/SoCal/County_Method columns filled; non-SoCal rows have those columns blank

### SoCal Lead/Contact Filtering (Sessions 25-26)
- **Offline data cleaning scripts** in `scripts/` — NOT Scout feature code
- `scripts/socal_filter.py` — Pass 1: CDE public school/district name matching + zip + city + email domain
- `scripts/socal_filter_pass2.py` — Pass 2: Parent account matching, city names embedded in school names, deeper email domain
- `scripts/socal_filter_pass3.py` — Pass 3: CDE + NCES private school database matching
- `scripts/socal_filter_pass4.py` — Pass 4: Serper web search on uncertain school-keyword records
- `scripts/socal_filter_pass5.py` — Pass 5: Free lookups (email domain→district→county, phone area codes, city/District Name fields)
- `scripts/socal_rebuild_leads.py` — Utility: replays passes 1-4 from original source (used for recovery)
- Data sources cached in `/tmp/`: `cde_schools.txt` (CDE public schools), `cde_districts.txt` (CDE districts), `cde_private_schools.xlsx` (CDE private), `nces_private/pss2122_pu.csv` (NCES private)
- Download URLs: CDE public = `https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt`, CDE districts = `rid=dl2`, CDE private = `https://www.cde.ca.gov/ds/si/ps/documents/privateschooldata2425.xlsx`, NCES = `https://nces.ed.gov/surveys/pss/zip/pss2122_pu_csv.zip`
- Input: `~/Downloads/My Leads - SoCal Only.csv` (20,737 records) and `~/Downloads/My Contacts - SoCal Only.csv` (8,040 records)
- Final output (4 files):
  - `~/Downloads/Leads_SoCal_Filtered.csv` — 10,677 confirmed SoCal leads
  - `~/Downloads/Contacts_SoCal_Filtered.csv` — 4,170 confirmed SoCal contacts
  - `~/Downloads/Leads_SoCal_Uncertain.csv` — 1,128 uncertain leads (separate)
  - `~/Downloads/Contacts_SoCal_Uncertain.csv` — 69 uncertain contacts (separate)
  - `*_NORCAL_REMOVED.csv` — NorCal/non-CA records removed (for audit)
- Each output has 3 added columns: County, SoCal (Yes/No/Uncertain), County_Method
- SoCal counties: Los Angeles, San Diego, Orange, Riverside, San Bernardino, Kern, Ventura, Santa Barbara, San Luis Obispo, Imperial
- Salesforce CSV files use latin-1 encoding (not utf-8)
- Pass order matters: run 1→2→3→5→4 (pass 5 before 4 saves Serper credits)
- Serper credits used: ~819 total. Steven has ~1,140 remaining.

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

**Validate email before calling gas.create_draft().** GAS throws on malformed emails.

**`/call_list` must be guarded in the `/call` handler.** `startswith("/call")` matches both. Use `startswith("/call") and not startswith("/call_list")`.

**Call list per-district cap (_MAX_PER_DISTRICT = 2) applies to BOTH priority matches AND backfill.**

**NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement.

**ALL sequences are drafts — always show for Steven's approval.** Write to Google Doc, share link in Telegram, mark prospect as "draft" status. Never auto-finalize or auto-mark "complete". Steven reviews and either approves or gives feedback on changes. This applies to ALL strategies (upward, cold, winback), not just winback.

**Sequence building rules are in `memory/sequence_building_rules.md`.** Load as context when auto-building sequences.

**`scheduler` is a module-level global in main.py.** It must be instantiated at module scope (alongside `memory` and `conversation_history`), not inside `_run_telegram_and_scheduler()`. If it's local to that function, `handle_message()` can't access it and all message handling silently dies. Fixed Session 23.

**`global` declarations go at the TOP of `handle_message()`, not in elif blocks.** Python SyntaxError if `global` appears after first use of the variable. All globals in one line: `global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _pending_csv_intent`.

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
| `/pipeline` | show open pipeline summary with stale alerts |
| `/pipeline_import` | next CSV upload imports as opportunities (Pipeline tab) |
| `/import_closed_lost` | next CSV upload imports as closed-lost opps (Closed Lost tab) |
| send a `.csv` file | Auto-detects opp vs lead vs contact vs account CSV; or Salesforce active accounts import (merge by default) |
| describe CSV before upload | "these are my salesforce leads" / "contacts from salesforce" / "pipeline opps" — sets routing for next CSV upload |
| caption on CSV upload | Same as above — type description as caption when sending the file |
