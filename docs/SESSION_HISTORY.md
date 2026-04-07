# SCOUT — Detailed Session History & Feature Reference

*This file preserves detailed implementation notes, decisions, and context for every feature built. CLAUDE.md stays lean for performance; this file is the full reference.*

*Read this file when you need: detailed implementation context, why decisions were made, how features evolved, or the full roadmap history.*

---

## Session 36 (2026-03-25) — Session Transcript Capture + Plan View Format

### Session Summary
Infrastructure session — no changes to Scout bot code. Built session transcript auto-capture system so Steven can go back and search/scroll through any past session verbatim. Locked in the exact plan view format after multiple rounds of feedback. C4 spot-check still pending — Steven decided to start fresh in Session 37 with the `scout` wrapper active so the transcript is captured.

### What was built
- **`scripts/scout_session.sh`** — Shell wrapper that replaces `claude` command. Runs macOS `script` to capture full terminal I/O, then auto-cleans and saves readable markdown to `docs/sessions/session_N.md`. Auto-detects session number (increments from last file). Safety check prevents overwriting existing transcripts. Fallback auto-commit if end-of-session routine is skipped.
- **`scripts/clean_transcript.py`** — Strips ANSI escape codes, control characters, terminal artifacts, spinner lines from raw `script` output. Produces clean, searchable markdown.
- **`docs/sessions/`** — Directory for clean transcripts. `.raw/` subdirectory (gitignored) holds raw terminal captures.
- **`.gitignore`** — Created to exclude `docs/sessions/.raw/`.
- **`~/.zshrc` alias** — `scout` → `scout_session.sh` so Steven just types `scout` to start.

### Key Decisions
- Use `/exit` not `/clear` between sessions — `scout` wrapper needs Claude Code to exit to finalize transcript
- Session transcript cleanup + commit happens during end-of-session routine (env vars: `SCOUT_RAW_TRANSCRIPT`, `SCOUT_CLEAN_TRANSCRIPT`)
- Plan view format locked in: no tables, emoji markers, ➕ additions nested under parent features, moderate detail level

### Feedback Captured
- Plan view format: dialed in over multiple iterations. Exact template saved to `memory/feedback_plan_view_format.md`.
- Session transcripts: Steven wants full verbatim transcripts saved and searchable, not summaries.
- Use `/exit` between sessions so each `scout` run = one clean transcript.

### Files Changed
- `scripts/scout_session.sh` (new)
- `scripts/clean_transcript.py` (new)
- `.gitignore` (new)
- `~/.zshrc` (added `scout` alias)
- `CLAUDE.md` (updated current state, added transcript capture section)
- `SCOUT_PLAN.md` (updated Session 36 additions, key decisions)
- `docs/SESSION_HISTORY.md` (this entry)
- Memory files: `feedback_plan_view_format.md`, `feedback_session_transcript.md`, `feedback_exit_not_clear.md` (all new)

---

## Session 35 (2026-03-23/25) — C4 Spot-Check Fixes + State Extraction + Plan Infrastructure

### Session Summary
Fixed all 5 C4 spot-check issues from Session 34 (email domain priority, SoCal detection, student exclusion, Claude prompt, lead-level columns). Built comprehensive state extraction from email domains (k12, .gov, state suffixes, city names). Built SF data-driven domain→state lookup from real SF Leads/Contacts emails. Added Prospecting Queue column migration (16→19 cols), /fix_queue, /cleanup_queue commands. Trimmed CLAUDE.md from 43.6k→28.9k for performance. Created SCOUT_PLAN.md as living master plan and docs/SESSION_HISTORY.md as detailed history. Paused mid-spot-check — latest /c4 run produced 1,452 targets, Steven needs to review accuracy.

### Key Decisions
- Email domain always ranks higher than company name for location (email_priority=True)
- Build domain→state mapping from real SF data rather than hardcoded lists
- Don't exclude unknown-state prospects yet — keep in queue for review until confident
- SCOUT_PLAN.md maintained as detailed living plan, brief view shown in terminal
- CLAUDE.md kept lean (under 40k combined), SESSION_HISTORY.md has full details

### Feedback Captured
- Always ask for Steven's input before implementing fixes
- Always give exact next steps (no dev jargon)
- Always acknowledge Steven's points before jumping to action
- Never tell Steven to push/deploy — always do it yourself
- Plan brief view should be moderately detailed, not too short
- Keep comprehensive records — Steven should never have to remember what he told Claude

---

### Detailed Implementation Notes (Session 35)

### C4 Issues Found During Spot-Check
1. **Email domain must rank higher than company name** — Salesforce company names are unreliable (educators pick wrong school when signing up). Example: `mstewart2@udallas.edu` with "Corsica High School" → should be TX not SD.
2. **Known SoCal domains excluded incorrectly** — `lausd.net`, `sandi.net`, `ucsd.edu`, `aesd.net` are SoCal but excluded as "CA - not in SoCal territory". Must check email domain against territory districts before excluding CA.
3. **Claude prompt needs email domain emphasis** — Tell Claude: "email domain is the MOST reliable signal."
4. **Student emails must be excluded** — `students.` subdomain = student, not educator. Also `waltonstudent.org`, `cusdstudent.com` etc.
5. **Need lead-level columns** — C4 prospects need email, first name, last name visible (not buried in Notes).

### Fixes Applied
- `match_record()` gets `email_priority=True` param — email domain matching runs BEFORE name matching
- `_match_by_email_domain()` extracted as reusable helper
- Claude inference prompt explicitly states email domain is MOST reliable signal with examples
- `is_student_email()`: detects "student" anywhere in domain (not just prefix)
- Email, First Name, Last Name columns added to Prospecting Queue (19 columns total)
- Prospecting Queue column migration from 16→19 columns (`migrate_prospect_columns()`)
- `/fix_queue` and `/cleanup_queue` commands added

### Comprehensive State Extraction (extract_state_from_email)
Patterns checked in order:
1. k12.STATE.us or k12.STATE.gov (any length, handles DC)
2. *.STATE.us with edu markers
3. State abbreviation as suffix of domain root (harmonytx → TX)
4. State abbreviation after separator (acs-nj → NJ)
5. State name in domain (hawaii.edu → HI)
6. Known city in domain (schools.nyc.gov → NY, udallas.edu → TX via dallas)

Ambiguous suffixes excluded from suffix matching: sd, id, in, me, or, al

### Known SoCal Domain Roots (KNOWN_SOCAL_DOMAIN_ROOTS)
90+ hardcoded SoCal district abbreviations that can't be derived from NCES names:
lausd, sandi, sausd, ggusd, abcusd, myabcusd, iusd, tustin, capousd, svusd, fjuhsd, auhsd, pylusd, bousd, hbuhsd, lbusd, musd, cnusd, cjusd, mvusd, psusd, rusd, ausd, jusd, alvord, hemet, menifee, beaumont, banning, perris, rialto, fontana, colton, redlands, yucaipa, sbcusd, and many more.

### Bug Fixes
- `extract_domain_root()`: fixed `parts[-2]` → `parts[-1]` for k12 TLD detection
- `extract_domain_root()`: fixed multi-level handler `parts[:-2]` → `parts[:-1]` (was missing lausd in staff.lausd.net)
- `generate_domain_roots()`: added acronym+sd/usd variants (lausd, ggusd, sdusd)
- C4 row building: `first_name`/`last_name` were not in `filtered_candidates` tuple — caused crash
- Timing message updated from "15-20 min" to "~10 min"

### Still In Progress
- Building domain→state mapping from real SF Leads/Contacts/Territory data
- Many prospects still have empty states — need data-driven approach

---

## Session 34 (2026-03-20) — C3 Verified, Outreach Connected, C4 Built

### C3 Closed-Lost Winback — FULLY VERIFIED
All 5 tests passed: import, scan, spot-check, approve+research, sequence draft.
- Date window logic: dual-edge `buffer_months=6` + `lookback_months=18`
- `/prospect_winback all` disables both. Custom params: `buffer=N lookback=N`

### Outreach.io API Integration
- OAuth app: "AI Coco Automation" (Development mode), shared with CodeCombat team
- Steven's Outreach user ID: **11** — all queries filter by this owner ID
- Tokens persist via GitHub (`memory/outreach_tokens.json`) — survives Railway deploys
- `/connect_outreach [force]` — OAuth flow, sends auth link in Telegram
- `/outreach_status` — shows connection status + user ID
- `/outreach_sequences` — lists Steven's sequences with engagement stats
- Read-only scopes: accounts, prospects, sequences, sequenceStates, sequenceSteps, sequenceTemplates, templates, mailings, calls, events, users, callDispositions
- **NEVER write to Outreach** — read-only. Don't add write operations without Steven's explicit approval.

### C4 Cold License Request Scan — Built End-to-End
- Pulls prospects from 3 US license request sequences (507, 1768, 1860)
- Bulk mailing scan for pricing detection (PandaDoc + subject + body content)
- Territory matcher (5-tier fuzzy matching against NCES data)
- Claude Sonnet batch inference for unresolved locations
- International TLD exclusion
- Cross-check against Active Accounts, Pipeline, Closed Lost
- Strategy: "cold_license_request", Source: "outreach"
- Scan takes ~10 min (bulk mailing + Claude inference)
- Initial results: 1,290 targets from 2,118 prospects (after all filters)

### territory_matcher.py Created
- Core utility for matching messy school/district names against NCES Territory Master List
- 5-tier matching: exact name, suffix-stripped, email domain, city+token overlap, containment
- In-memory cache with 1-hour TTL (~48K records from Territory Schools + Districts tabs)
- `match_record(name, email=, city=, state=, email_priority=)` → MatchResult or None
- `match_records(records, ...)` → batch matching with email_priority support
- `infer_locations_with_claude(unknowns)` → Claude batch inference for unresolved
- `extract_domain_root(email)` and `generate_domain_roots(name)` — domain utilities
- `extract_state_from_email(email)` — comprehensive state extraction
- `is_student_email(email)` — student detection
- `is_socal_domain(email)` — SoCal district domain detection

### Prospecting Queue Redesigned
New column order (19 columns):
State | Account Name | Email | First Name | Last Name | Deal Level | Parent District | Name Key | Strategy | Source | Status | Priority | Date Added | Date Approved | Sequence Doc URL | Est. Enrollment | School Count | Total Licenses | Notes (always last)

### New Commands
`/connect_outreach [force]`, `/outreach_status`, `/outreach_sequences`, `/c4` (also `/prospect_cold_requests`, `/cold_requests`), `/c4_clear`, `/fix_queue`, `/cleanup_queue`

### Speed Optimization
- Bulk mailing scan (3 API calls vs 1,600+)
- Background task execution for C4 scan

---

## Session 33 (2026-03-19) — C3 Closed-Lost Winback Built

### C3 Design Decisions
- **Data source:** Separate Salesforce "Closed Lost Opportunities" report CSV — NOT from Pipeline tab
- **Closed-lost opps are not in Steven's pipeline data.** He must run a dedicated report in Salesforce, export CSV, upload to Scout
- `/import_closed_lost` — sets next CSV upload to route to the "Closed Lost" tab (dedicated, separate from Pipeline)
- Natural language: "closed lost" / "winback" in caption or pre-message also routes to Closed Lost tab
- `get_closed_lost_opps()` reads from Closed Lost tab first, falls back to Pipeline tab
- Filter: Date window with dual edges — `buffer_months=6` (exclude too-recent) + `lookback_months=18` (how far back from buffer edge). Default: ~24mo ago to ~6mo ago. `lookback_months=0` = no oldest cutoff.
- Groups by district: uses Parent Account if available, else Account Name
- Priority 550-749: higher deal amounts score higher. Between upward (600-999) and cold (300-700)
- Notes field captures: opp count, total value, last close date, opp names

### Winback Sequence Requirements
- 5 steps, Outreach.io variables ({{first_name}}, {{state}}, {{company}})
- At least one "reply" email
- Highlight what's new/improved
- Include incentivization
- Breakup email last

### Why Deals Close Lost (Actual Data)
- 61% Unresponsive (teacher went dark after admin pushback)
- 19% Budget (admin said no)
- 5% Not using/didn't start
- 4% Teacher turnover
- 2% Competitor
- Teachers get discouraged asking admins

---

## Sessions 31-32 — C1 Territory Master List

### Implementation Details
- Data source: Urban Institute Education Data API (`educationdata.urban.org`), wrapping NCES CCD 2023
- No auth required, JSON responses, filter by FIPS state code
- 13 states: IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE, TX + CA (SoCal counties only)
- CA filtered by `county_code` to 10 SoCal counties — **API returns county_code as strings** (e.g., `"6037"`), not integers
- Separate Google Sheet: `GOOGLE_SHEETS_TERRITORY_ID` env var (falls back to main sheet)
- Two tabs: `Territory Districts` (17 columns) and `Territory Schools` (18 columns)
- API responses cached in `/tmp/territory_{kind}_{state}.json` with 7-day TTL (cleared on Railway redeploy)
- Sync clears existing rows for each state before writing (idempotent re-sync)
- Chunked writes at 2,000 rows with 3-attempt retry
- **Full territory size:** 8,133 districts, 40,317 schools, 20.6M students across all states

### Gap Analysis Coverage Rules
- District-level Active Account deal = "covered"
- School account in a district = "upward opportunity" (NOT coverage)
- Coverage % = district deals / total NCES districts
- Unmatched schools (private/charter not in NCES) shown separately with warning

---

## Sessions 24-28 — B2 SF Leads & Contacts Import

### Design
- Two new tabs: **SF Leads** (from Salesforce Leads report) and **SF Contacts** (from Salesforce Contacts report)
- SEPARATE from the existing Leads tab (which is research-generated contacts)
- `/import_leads` — next CSV goes to SF Leads tab; `/import_contacts` — next CSV goes to SF Contacts tab
- Auto-detect: lead CSV has 2+ of {Lead Source, Lead Status, Company}; contact CSV has 2+ of {Account Name, Department, Contact Owner} + name columns
- Auto-detect priority: pipeline > sf_leads > sf_contacts > accounts
- Natural language: "salesforce leads" / "my leads" routes to SF Leads; "contacts" / "sf contacts" routes to SF Contacts

### Cross-Check Implementation
- Cross-checks each record against Active Accounts by email domain, account/company name, and district name
- Enrichment columns: Verified School, Verified District, Verified State, Verified County (CA only), Active Account Match, Enrichment Status, Enrichment Notes, Last Enriched, Date Imported
- **Exact Match - School**: lead's company = same school as active account → match
- **Exact Match - District**: lead's company = same district as active account → match
- **District is Active Account**: active account is a district-level deal, lead is at any school or the district itself → match
- **NOT a match**: active account is just a school, lead is at a DIFFERENT school or the district → Steven can freely prospect
- Key rule: school-level active accounts only block the SAME school. District-level active accounts block the whole district.

### Domain Matching
- Pre-built lookup structures: `_build_account_lookups()` runs once per import
- `_generate_domain_roots()` creates plausible roots from account names (e.g., "Austin ISD" → {"austinisd", "austin", "aisd"})
- Includes acronym-based roots: "Los Angeles Unified School District" → "lausd"
- `_extract_domain_root()` handles k12-style domains and multi-level domains
- State filtering: matches require same state (or either side blank)
- **Step 2 (District Name) validation**: Salesforce District Name field is unreliable — if lead has non-generic institutional email, domain root must match the matched district's generated roots.

### Tab Structure
- Two extra tabs: **Leads Assoc Active Accounts** and **Contacts Assoc Active Accounts**
- Four math filter tabs: **SF Leads - Math**, **Leads Assoc Active - Math**, **SF Contacts - Math**, **Contacts Assoc Active - Math**
- **Mutually exclusive routing** — each record goes to exactly ONE tab
- Separate Google Sheet: `GOOGLE_SHEETS_SF_ID` env var

### Technical Details
- Large CSV imports chunked at 2,000 rows per batch with 3-attempt retry + 2s/4s backoff
- Append range uses tight `A:{last_col}` based on header count (NOT `A:AZ`) — prevents 10M cell limit hits
- `clear_tab()` uses `values().clear()` + `updateSheetProperties` grid resize (NOT `deleteDimension` which fails on frozen rows)
- Tab formatting: column widths sized to header text (~7px/char), alternating row banding, frozen row 1
- Column order: State/Province first, then name/title/company/email, then Active Account Match right after Email
- "Leads from Research" — renamed from "Leads". `TAB_LEADS` constant in sheets_writer.py

---

## Sessions 25-26 — SoCal Lead/Contact Filtering (Offline Scripts)

### Scripts (in `scripts/` — NOT Scout feature code)
- `scripts/socal_filter.py` — Pass 1: CDE public school/district name matching + zip + city + email domain
- `scripts/socal_filter_pass2.py` — Pass 2: Parent account matching, city names embedded in school names, deeper email domain
- `scripts/socal_filter_pass3.py` — Pass 3: CDE + NCES private school database matching
- `scripts/socal_filter_pass4.py` — Pass 4: Serper web search on uncertain school-keyword records
- `scripts/socal_filter_pass5.py` — Pass 5: Free lookups (email domain→district→county, phone area codes, city/District Name fields)
- `scripts/socal_rebuild_leads.py` — Utility: replays passes 1-4 from original source

### Data Sources
- CDE public schools: `https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt`
- CDE districts: `rid=dl2`
- CDE private: `https://www.cde.ca.gov/ds/si/ps/documents/privateschooldata2425.xlsx`
- NCES private: `https://nces.ed.gov/surveys/pss/zip/pss2122_pu_csv.zip`
- Cached in `/tmp/`

### Results
- Input: 20,737 SoCal leads + 8,040 SoCal contacts
- Output: 10,677 confirmed leads, 4,170 confirmed contacts, 1,128 uncertain leads, 69 uncertain contacts
- SoCal counties: Los Angeles, San Diego, Orange, Riverside, San Bernardino, Kern, Ventura, Santa Barbara, San Luis Obispo, Imperial
- Salesforce CSV files use latin-1 encoding
- Pass order: 1→2→3→5→4 (pass 5 before 4 saves Serper credits)
- Serper credits used: ~819 total

### Merged Files (Session 27)
- `~/Downloads/My merged leads list - Including SoCal - as of 3-7-26.csv` — 86,993 leads
- `~/Downloads/My merged contacts list - Including SoCal - as of 3-7-26.csv` — 19,775 contacts

---

## Session 23 — Enhancements A1-A3 + B1

### Weekend Scheduler (B1)
- Saturday: greeting at 11:00am CST, Sunday: greeting at 1:00pm CST
- No auto check-ins or auto EOD on weekends
- `/eod` command triggers EOD report manually (works any day)
- `scheduler.mark_user_active_today()` called from `handle_message()` on weekends — suppresses auto-greeting if Steven messages first
- `_is_user_active_today()` resets daily (compares against current date)

### Lead Row Coloring (A3)
- `_color_leads_by_confidence()` auto-runs after `write_contacts()` appends to Leads tab
- `/color_leads` command recolors all existing rows (one-time cleanup)
- Colors: VERIFIED/HIGH = light green, LIKELY/MEDIUM = yellowish-green, INFERRED/LOW = light yellow, UNKNOWN = light grey
- Batches in chunks of 500 requests for Sheets API safety

---

## Full Roadmap (approved Session 22)

See `memory/roadmap_full.md` for the complete approved roadmap (A1-A3, B1-B2, C1-C5).

### Status Overview
- Phases 1–5: ✅ all verified
- Phase 6A-6F: ✅ all verified
- Enhancements A1-A3 + B1: ✅ implemented (Session 23)
- Enhancement B2 (SF Leads/Contacts): ✅ fully verified (Session 30)
- Enhancement C1 (Territory Master List): ✅ fully verified (Session 32)
- Enhancement C3 (Closed-Lost Winback): ✅ fully verified (Session 34)
- Enhancement C4 (Cold License Requests): 🔧 in progress (Session 35)
- Enhancement C2 (Research Engine): next after C4
- Enhancement C5 (Proximity): deferred

---

## Session 37 (2026-03-25 to 2026-03-26) — C4 Cold License Requests: SIGNED OFF

### What changed
- **C4 fully verified and signed off.** Final: 1,274 targets, 113 empty states (11 institutional), 100% parent district coverage, $1.38/run.
- **State extraction:** Added education keyword stripping (kyschools→KY), expanded city/county→state map (30+ entries), improved Claude prompt with domain decoding examples.
- **SoCal verification:** Added `is_socal_by_name()` — checks company name + Claude city/district for SoCal city names. Fixed gmail CA prospects being falsely excluded.
- **Serper web search pipeline:** Searches school name + full email address (per-prospect), plus domain-only (deduped). Parallel via ThreadPoolExecutor (20 concurrent). Generic emails searched by school name.
- **Parent district enrichment:** NCES re-matching with known state + Serper extraction. 100% coverage (1 missing of 1,161).
- **Deterministic international detection:** TLDs (.pa, .name), foreign edu domains (.edu.pa, .ac.uk, .bc.ca), company name keywords (école, liceo, colegio, escuela), search content signals (british columbia, .bc.ca/).
- **Claude JSON preamble fix:** Claude Sonnet sometimes writes "I'll analyze each record carefully..." before JSON. Fix: strip text before `[` and after `]`.
- **API cost tracking:** `_track_claude_usage()` accumulates tokens, shows est. cost in `/c4` completion message.
- **Local dev setup:** `.env` with GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_JSON, SERPER_API_KEY (gitignored). `scripts/spot_check_c4.py` for direct sheet reading.
- **Railway CLI:** Installed, authenticated, linked. `railway logs --lines N --since Xm` for live debugging.
- **NCES cache:** Added city_to_states and district_name_to_states indexes. `lookup_state_from_nces()` function exists but NOT used in C4 (partial state data gives false positives).
- **SOCAL_CITIES, SOCAL_KEYWORDS, SOCAL_COUNTIES** constants added to territory_matcher.py.

### Key decisions
- **Serper web search is primary resolution tool** — direct domain scraping was slower and less accurate.
- **Search school name + full email** — `"Corpus Christi School jonathan.sam@cchristi.org"` returns exact person's school page. Domain-only search returns wrong results for ambiguous names.
- **Do NOT use NCES city lookup for state extraction** — 13-state partial data makes "unique" matches wrong (charlottesville→IN because VA not in data).
- **International detection must be deterministic** — Claude's `is_us` flag varies across runs. Use TLDs, domain patterns, and company name keywords instead.
- **Do NOT use substring matching for geographic signals** — "india" matches "Indiana", "england" matches "New England", "ontario" matches "Ontario, CA". Only use unambiguous multi-word signals.

### Bugs found and fixed
1. NCES city lookup false positives (partial state data)
2. Python `not x == y` precedence (confirmed NOT a bug — was correct)
3. `results` dict NameError (used before initialization)
4. Claude text preamble before JSON (strip before `[`)
5. Silent `except Exception: pass` hiding errors
6. International content filter matching US states ("india"→"Indiana")
7. Serper rate limits from too many concurrent connections
8. Separate district Serper pass burning double API credits

### Files modified
- `tools/territory_matcher.py` — extract_state_from_email patterns, SOCAL constants, is_socal_by_name(), infer_locations_with_claude prompt + JSON preamble fix, lookup_state_from_nces (unused)
- `tools/district_prospector.py` — _scrape_resolve_locations (Serper search), international detection, cost tracking, parent district enrichment, SoCal company name check
- `agent/main.py` — cost display in /c4 completion message
- `scripts/spot_check_c4.py` — new local spot-check script
- `.gitignore` — added .env
- `.env` — local credentials (gitignored)

### New feature request captured
- **Todo List Feature** — Replace Scout's hourly check-ins with todo list management. Steven wants Scout to keep him on task, accept status updates, add/complete items via Telegram. Captured in memory/project_todo_feature.md.

---

## Session 38 (2026-03-26 to 2026-03-31) — Todo List, CUE Enrichment, Outreach Sequences

### Todo List Feature
- `tools/todo_manager.py` — flat module, top-level import in main.py
- Google Sheet "Todo List" tab: ID, Task, Priority (high/medium/low), Status (open/done), Created, Completed, Due Date
- Telegram commands: `add:`, `todo:`, `done:`, `/todos`, `/todo_clear`, `/todo_remove`
- Claude tool: `manage_todos` with actions: add, complete, list, remove, clear_completed, update_priority
- Hourly check-ins rewritten to reference open todos (top 3 shown, overdue flagged)
- Priority parsing: `add: call Jennifer !high` or `(high)`

### CUE 2026 Lead Enrichment
- `scripts/enrich_cue_leads.py` — offline enrichment script for conference leads
- 1,472 raw → 1,298 deduped unique leads
- 5-layer resolution pipeline: (1) email domain patterns, (2) SF domain→state lookup from existing sheets (859 roots), (3) Serper web search (parallel, deduped by domain), (4) Claude extraction from search results, (5) Claude inference for remaining + company name fill
- Final NorCal/SoCal resolution pass with Serper + Claude for CA county identification
- NCES name normalization against 8,038 districts + 36,145 schools from Territory sheet
- Abbreviation-to-full-name mapping for 40+ common abbreviations (LAUSD, SBCUSD, etc.)
- Rep routing: Steven (SoCal + 12 states), Tom (NorCal + 21 states), Liz (17 states), Shan (non-Americas intl), CUE-CALIE (excluded)
- Output: Google Sheet with Enriched tab + per-rep tabs + CSV
- CA domain overrides for typo domains (lawndalesd.n.et, beaumontusd.k12.ca)
- Full-domain overrides for ambiguous roots (pusd.org=Pomona, pusd.us=Pasadena)

### Outreach Sequence Creation
- Added `_api_post()`, `create_sequence()`, `get_mailboxes()` to `outreach_client.py`
- Added `from __future__ import annotations` for Python 3.9 compat
- Fixed webhook callback that was blocking OAuth re-authorization ("Already authenticated" guard removed)
- Created 12 sequences total:
  - 6 CUE booth: Universal, Elementary K-5, Middle School, High School, Admin/Ed Tech Lead, Pomona USD (4 steps each)
  - 5 CUE opt-in: Teacher Universal (590), Admin/District (225), Teacher High School (46), Teacher Elementary (28), Teacher Middle School (16) (3 steps each)
  - 1 Booth Apology (1 step)
- 58 booth prospects + 883 opt-in prospects loaded
- **CRITICAL BUG:** Outreach sequenceStep interval is in SECONDS, not minutes. Research said minutes. Used 8640 (intended 6 days), actually = 2h24m. All 4 booth emails sent within hours. Fixed all intervals. Apology sent.
- **API limitations discovered:** `enabled` is private (can't activate via API), `sequenceStates` can't be PATCHed (can't resume paused prospects), need delete scope for step removal
- **Template formatting:** Must use `<br><br>` not `<p>` tags — Outreach renders `<p>` with no spacing
- Default settings for all sequences: owner=Steven (ID 11), sharing=private, throttle 150/day, capacity 200

### Other
- Session transcript numbering fix in `scout_session.sh`
- GitHub fine-grained PAT regenerated (was expired)
- Local .env: added ANTHROPIC_API_KEY, GOOGLE_SHEETS_TERRITORY_ID, Outreach vars, GITHUB_TOKEN
- Steven's territory saved to memory: TX, CA-SoCal, IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE

### Key Decisions
- Outreach write access lifted for sequences (was read-only since Session 34)
- Outreach interval is in SECONDS — hard rule, never use minutes
- Creation order: create sequence → Steven activates in UI → add prospects
- Steven's territory must be known by heart (13 states + SoCal)

---

## Session 39 (2026-04-01) — Session Numbering Fix + C2 Parallelization Analysis

### Session Summary
Short session. Fixed the session transcript numbering system that was broken since Session 36 — sessions 37+38 ran without the `scout` wrapper, so auto-detect fell behind. Analyzed the full research engine for C2 parallelization and got the plan approved, but didn't code it yet.

### What was built
- **`scripts/scout_session.sh` fix** — Auto-detect now parses CLAUDE.md header (`*Last updated: ... — Session N*`) as the primary source of truth for session number. Previously only checked transcript files on disk. Exit cross-check regex also updated from `"Session N: ... SIGNED OFF"` (which never matched) to the actual CLAUDE.md format. Takes the highest of: CLAUDE.md number, clean transcript files, raw transcript files.

### C2 Research Engine Analysis
Read all 973 lines of `tools/research_engine.py`. Mapped the dependency graph for all 15 layers:
- **Independent (no deps):** L1, L2, L3, L5, L13, L14 — all pure Serper searches
- **Finds district_domain:** L4 — also a Serper search, but output needed by later layers
- **Needs district_domain:** L6→L7→L8 (sequential website crawl chain), L11, L12
- **Needs all raw_pages:** L9 (Claude extraction from all collected content)
- **Sequential tail:** L10 (dedup) → L15 (email verify) → L10 (re-score)

Proposed parallel groups:
- **Group A:** L1, L2, L3, L4, L5, L13, L14 via `asyncio.gather` — all concurrent
- **Group B:** After L4 completes — L6→L7→L8 chain + L11/L12 in parallel alongside
- **Group C:** L9 Claude extraction (blocked on A+B)
- **Group D:** L10→L15→L10 unchanged

Additional fixes needed: asyncio.Lock for shared `_serper_count` (race condition in concurrent layers), shared httpx.AsyncClient instead of per-query client creation.

Estimated speedup: 40-60% wall-time reduction. Steven approved the approach.

### Key Decisions
- CLAUDE.md is the authoritative source of truth for session numbering
- C2 parallelization plan: 4 groups, serper lock, shared client — approved and ready to code

---

## Session 40 (2026-04-01/02)

### What Changed
- **C2 Research Engine upgrade complete.** Tested 7 web research tools (Serper, Exa, Tavily, Firecrawl, Jina, Crawl4AI, Parse.bot) across 8 test districts. Built evaluation framework (`scripts/eval_research_tools.py`, `scripts/eval_config.py`) and deep research prototype (`scripts/eval_deep_research.py`).
- **Production engine upgraded from 15 to 20 layers.** Added L16 (Exa broad search), L17 (Exa domain-scoped search), L18 (Firecrawl extract — deferred/budget), L19 (Firecrawl site map — deferred/budget), L20 (Brave Search).
- **Parallelized into 5 phases** using asyncio.gather. Phase A runs 6 searches across 3 indices simultaneously. Phase C runs 8 domain-dependent tasks simultaneously. ~40% speed improvement.
- **Quality validation added.** Cross-district pre-filter (drops pages from wrong district domains). Name↔email validation (catches mismatched table rows from Claude). Two-pass extraction filter (skips non-contact pages, saves ~50% Claude cost).
- **Lead targeting tightened.** Created `agent/target_roles.py` from Steven's "ROLES and KEYWORDS" doc. CTE filter excludes culinary/automotive/business/art/IT-infra. Includes algebra (AI Algebra product) and cybersecurity (fall 2026 product).
- **Contact extractor upgraded.** Prompt now has explicit include/exclude rules, table alignment instructions, CTE post-extraction filter, JSON preamble strip, max_tokens 2000→4000.
- **API keys deployed.** EXA_API_KEY + BRAVE_API_KEY added to Railway. Firecrawl deferred (budget).
- **Live A/B tests.** Austin ISD: 77→124 contacts (+61%), 12→48 verified emails (+300%). Kern HSSD: 35→115 contacts (+229%), 1→34 verified (+3300%).
- **24 prospecting strategies documented** in memory. Covers expansion, cold, trigger-based, event-driven, product-specific campaigns.
- **Permissions allowlist cleaned up.** 94 accumulated one-off entries → 70 organized broad patterns.

### Key Decisions
- Firecrawl paid plan deferred due to budget ($19/mo). L18/L19 skip gracefully. Was the #1 tool — circle back when budget allows.
- Exa is the primary new search tool (neural index, domain-scoped search, best content quality).
- Brave Search added as independent index (not Google wrapper) — different results = more coverage.
- CTE roles only relevant if related to CS/Tech/Cyber/Engineering/Algebra. Generic trades excluded.
- IT infrastructure roles (network ops, sysadmin, help desk) excluded unless title has education qualifier.
- Parse.bot backend DNS issues — MCP configured but unusable. Revisit later.
- Contact extractor prompt updated to mention CodeCombat specifically and list explicit include/exclude criteria.

### New Files
- `scripts/eval_research_tools.py` — 8-tool evaluation framework with quality validation
- `scripts/eval_config.py` — Test districts, tool registry, search queries
- `scripts/eval_deep_research.py` — 8-stage deep research prototype (domain discovery → extract → search → Claude → pattern inference → Brave → agent → agentic followup)
- `agent/target_roles.py` — Authoritative lead targeting: titles, keywords, CTE filter, IT infra filter

---

## Session 42 (2026-04-04)

### C2 Research Engine — Live Verification
- Tested 4 districts on Railway via Telegram (using new natural language dispatch)
- Houston ISD: 8→82 contacts, 2→44 verified (+2,100%). Exa L16 = 39 contacts (MVP layer)
- Columbus City Schools: 29→90 contacts, 0→18 verified. Exa L16 = 58 contacts
- Guthrie Public Schools: 1→52 contacts, 0→26 verified. Exa L16 = 25 contacts
- Leander ISD: 11→31 contacts, 3→14 verified. Exa L16 = 3 (JS-heavy site, Serper+L15 compensated)
- L4-L14 (scraping layers) mostly zeros — JS-heavy school sites block crawling
- Brave L20 marginal — contributed on Houston only
- No errors or crashes — parallelization stable

### C5: Proximity + Regional Service Centers — Built + Verified
- **New module:** `tools/proximity_engine.py`
- **Targeted proximity:** `proximity Liberty Hill ISD` finds districts + schools near one active account
  - Default 15mi radius, adjustable: `proximity Liberty Hill ISD 30`
  - Shows nearby districts (with enrollment, distance) and schools (grouped by district)
  - Adaptive suggestions: too few → widen, too many → narrow
- **Add to queue:** `add nearby 4,8,13` picks from last proximity results → Prospecting Queue
  - Uses `_last_proximity_result` global (in-memory only, like `_last_prospect_batch`)
- **State sweep:** `proximity Texas all` — bulk mode for all accounts in a state
- **ESA mapping:** `esa Texas` — maps districts to nearest ESC using NCES Agency Type 4 data
  - County-code match first, haversine fallback
  - Shows which ESAs have Steven's active accounts + uncovered districts
  - TX: 20 ESCs, OH: 51 ESCs + 49 career-tech, OK: graceful "no ESA system"
- **ESC vs career-tech split:** Agency Type 4 includes both true ESCs (0 schools, 0 enrollment) and career-tech centers (JVSDs with enrolled students). Classified separately. Career-tech shown as own prospecting targets.
- **ESA_PATTERNS expanded:** 11 → 78 entity name patterns from Steven's ROLES and KEYWORDS doc
- **Priority scoring:** proximity strategy (400-699, closer=higher), esa_cluster (450-599)
- **All direct dispatch:** Natural language matching in handle_message(), bypasses Claude routing

### Natural Language Research Dispatch
- Added pattern matching for `research [district] in [state]` — routes directly to execute_tool("research_district")
- `/research_district` was NOT a shorthand command — went through Claude, which sometimes picked wrong tool
- Fixed after Claude called `get_research_queue_status` instead of `research_district`

### Other Session 42 Items
- **Parse.bot:** Server-side DNS failure on scraper workers after migration. list_apis works, create_api fails on all URLs (even example.com). Emailed + DM'd founder Alex Forman (alex@parse.bot, @alexscraping). Parked.
- **GitGuardian alert:** False positive — flagged "X-API-Key" HTTP header name in eval_research_tools.py (Parse.bot integration). Not an actual secret. No action needed.
- **YouTube transcript MCP:** Added `@fabriqa.ai/youtube-transcript-mcp` as user-scope MCP. Also installed `yt-dlp` as fallback. Tools: get-transcript, get-transcript-languages.
- **Session numbering:** CLAUDE.md said Session 40, scout wrapper said 42. Gap from Session 41 that didn't update CLAUDE.md. Fixed.

### New Files
- `tools/proximity_engine.py` — C5 proximity + ESA module (haversine, find_nearby_one, map_districts_to_esa, etc.)

### Key Decisions
- Targeted proximity is the default (one account), state sweep is opt-in ("all" suffix)
- Proximity results are display-only — Steven picks which to add via "add nearby"
- ESCs and career-tech centers are both Agency Type 4 but shown separately
- Career-tech centers are prospecting targets (have CS/CTE decision-makers)
- Steven prefers natural language over slash commands — all new features should have NL dispatch

---

## Session 44 (2026-04-05) — Signal Intelligence System + Enrichment + Alert Overhaul

### Session Summary
Built Scout's complete signal intelligence system from scratch. Processes Gmail emails (Google Alerts, Burbio newsletters, DOE newsletters) plus Indeed job postings into a Signals Database. Added enrichment layer that does web research + Claude analysis to score each signal for CodeCombat relevance before recommending action. Overhauled Google Alerts from 28 redundant alerts to 18 buying-signal focused alerts. Subscribed to DOE newsletters for all 13 territory states. Quality pass reduced noise from 150 to 40 actionable signals.

### What was built
- **`tools/signal_processor.py`** (~1,000 lines) — Core module. 3-tier pipeline: Tier 1 regex parsing ($0, Google Alerts), Tier 2 Claude Haiku extraction ($0.30 for 500+ emails, Burbio/DOE), Tier 3 enrichment ($0.002/signal, Serper + Claude relevance scoring).
- **Signals Database tab** — 17 columns: ID, Date, Source, Source Detail, Signal Type, Scope, District, State, Headline, Dollar Amount, Tier, Heat Score, Urgency, Status, Customer Status, Source URL, Message ID.
- **Signal enrichment** — `enrich_signal()` does Serper web search for spending details + Claude Haiku analysis for CodeCombat relevance (strong/moderate/weak/none). Returns: spending breakdown, CS/CTE relevance, key contacts, timeline, talking points, recommended action.
- **Job posting scanner** — `scan_job_postings()` uses python-jobspy to scrape Indeed for CS/CTE/STEM teacher hiring. Filters to K-12 entities + CS-relevant roles.
- **Google Alert parser** — `parse_google_alert()` regex-parses weekly digest emails into individual stories. Handles `\r\n` from GAS `getPlainBody()`. Extracts keyword, title, source, snippet, real URL (unwrapped from Google redirect).
- **NCES district→state lookup** — Loads 8,133 districts from Territory Districts tab. Maps district names to states. Fixes the "Dallas ISD doesn't contain Texas" problem.
- **Heat scoring** — Base score from signal type weights × territory bonus × customer modifier × cluster bonus × recency. Decay applied on read. Urgency-aware: time_sensitive/urgent signals use minimal decay (0.97/week).
- **10 Telegram commands** — `/signals`, `/signals all|[state]|new`, `/signal_info N`, `/signal_enrich N`, `/signal_act N`, `/signal_dismiss N`, `/signal_scan`, `/signal_jobs`, `/signal_stats`. All direct-dispatch.
- **Daily scanner** — Scheduler event at 7:45 AM CST. Auto-enriches Tier 1 signals. Retry-once on failure.
- **Morning brief integration** — MARKET SIGNALS section injected via `build_signal_brief_block()`. Signal-of-the-day highlight.

### Batch processing results
- 380 Google Alert digests → 18,065 stories (regex parsed, $0)
- 41 Burbio newsletters → 201 signals (Claude Haiku, ~$0.20)
- 36 DOE newsletters → 135 signals (Claude Haiku, ~$0.10)
- Total: 18,401 signals, 272 territory-relevant, 68 Tier 1, 46 clusters
- Total cost: $0.30

### Signal enrichment results (12 queued districts)
- 🟢 STRONG (4): Tulsa PS (OK) — $200M CTE/STEM labs, vote Apr 7, Robert F. Burton; Richardson ISD (TX) — $86M CTE center, CTE District of Distinction; Acton-Boxborough (MA) — hiring STEAM Coordinator + Robotics; Norwalk PS (CT) — CTE + tech board discussion, 3 signals
- 🟡 MODERATE (6): Dallas ISD (TX) — $145M tech but devices/infrastructure only; Sand Springs PS (OK); Lamar ISD (TX); North East ISD (TX); Tuloso-Midway ISD (TX); Somers PS (CT)
- 🔴 WEAK/NONE (2): Ingham ISD (MI) — special ed bond; Seward PS (NE) — facilities only
- Key insight: $6.2B Dallas ISD headline = MODERATE (devices), while no-dollar Acton-Boxborough = STRONG (STEAM hire). Enrichment completely reorders priority.

### Quality pass
- Expired 161 market_intel noise signals (stories mentioning a district name in passing)
- Expired 5 rejected/non-tech bonds (locker rooms, tennis courts, rejected measures)
- Restored 1 false positive (Lamar ISD caught by "facilities" regex — valid $1.9B bond)
- Territory signals: 150→40 actionable

### Signal sources expanded
- DOE newsletters: GovDelivery (TX, OH, MI, IN, OK), CDE listservs (CA ×3), state portals (MA, NE, NV, IL), listserv (CT), PENN*LINK (PA)
- Google Alerts: 28→18. Removed 22 redundant. Added 12 buying-signal focused.
- Free newsletters: K-12 Dive, EdWeek Market Brief, eSchool News, District Administration, CSTA
- Gmail filter: `*SIGNALS` label, skip inbox

### Key decisions
- Google Alerts stay as weekly digests (not daily) — parser knows the format, buying windows are 30-90 days
- Default `/signals` is territory-only — out-of-territory signals are noise for Steven
- Signal enrichment is mandatory before action ��� never queue a district on headline alone
- market_intel scope="district" signals get expired — a story mentioning a district in passing is not a signal
- Bond/leadership/RFP urgency = "time_sensitive" with minimal decay — the opportunity window matters, not email age
- python-jobspy added to requirements.txt — imports gracefully (try/except) if not installed

### Architectural patterns
- signal_processor follows existing flat module pattern (like todo_manager, district_prospector)
- `_last_signal_batch` is in-memory, same pattern as `_last_prospect_batch`
- Cost tracking uses same `_track_usage()` / `_get_cost()` pattern as district_prospector
- Enrichment uses Serper for web search (same as C4) + Claude Haiku (not Sonnet — structured extraction doesn't need it)
- GAS bridge `search_inbox_full` with `body_limit=65000` for alerts, `15000` for Burbio/DOE

---

## Session 45 (2026-04-06) — Signal System Expansion + Outreach Sequences + Sequence Rules

### Signal sources added (3 new, 7 total)
- **RSS feeds:** `feedparser` library added to requirements. 3 feeds: K-12 Dive (`k12dive.com/feeds/news/`), eSchool News (`eschoolnews.com/feed/`), CSTA (`csteachers.org/feed/`). EdWeek has no RSS (says "future feature"), District Admin returns 403. `process_rss_feeds()` function with `since_date` filtering. Source type: `rss_feed`. `/signal_rss` command.
- **BoardDocs scraper:** 25 territory districts hardcoded in `BOARDDOCS_DISTRICTS` list. HTTP POST to `BD-GetMeetingsList?open` and `PRINT-AgendaDetailed`. Auto-discovers committee_id from public page. `_BOARD_TECH_KEYWORDS` regex for CS/CTE/STEM + `_BOARD_BOND_KEYWORDS` for bond/budget. Capped at 3 tech + 1 bond signal per meeting to reduce noise. HTML entity stripping. Headlines use keyword + trailing context. Source type: `boarddocs`. `/signal_board` command.
- **Ballotpedia bond tracking:** Scrapes `ballotpedia.org/Local_school_bonds_on_the_ballot`. Parses `<li>` items with `re.DOTALL`. Filters to 12 territory states (CA excluded — thousands of results). 2025-2026 only. Detects passed/failed from `<img alt="">` icons. Deduplicates within batch. Source type: `ballotpedia`. `/signal_bonds` command.

### Signal-to-deal attribution
- Added "Pipeline Link" column to Signals tab (18th column, `NUM_COLS` = 18)
- Added "Signal ID" column to Prospecting Queue (19th column, before Notes which moves to 20th)
- `add_district()` now accepts `source` and `signal_id` params
- `/signal_act` passes signal ID through and calls `link_signal_to_prospect()` to write Pipeline Link
- `migrate_prospect_columns()` updated for 19→20 column migration
- `_load_all_prospects()` range updated from `A:S` to `A:T`

### Signal infrastructure fixes
- **Dedup fix:** `get_processed_message_ids()` was only reading Message ID column. `write_signals` constructs `msg_id|url` composite keys. Now reads both Source URL + Message ID columns (adjacent: P and Q) to build matching composite keys.
- **Daily scan protection:** BoardDocs, Ballotpedia, and RSS all wrapped in try/except in both `process_all_signals()` and `process_new_signals()`. One source failing can't crash the daily scan. Morning scan was failing before this fix.
- **Disabled scheduler events:** Hourly check-ins removed from `scheduler.py`. Weekend greetings replaced with early `return None` for `weekday >= 5`.

### Outreach sequences created
- **!!!2026 License Request Seq (April)** — ID 1999, 7 steps. Step 3 uses existing template 43784. Based on prompt Steven crafted with claude.ai using exported version of old sequence (ID 1860).
- **Algebra Webinar Seq (April 2026) Attendees** — ID 2000, 4 steps. Recording, resources doc, PD certificate links. Step 3 = existing template 43784.
- **Algebra Webinar Seq (April 2026) Non-attendees** — ID 2001, 4 steps. Same structure, different messaging (missed-it angle).
- All 14 webinar leads loaded (4 attended, 10 no-show). 2 initially failed (active in other sequence, opted out) — retried successfully.

### Outreach API improvements
- Added `_api_patch()` method to `outreach_client.py`
- Added `export_sequence()` — pulls sequence metadata, steps, sequenceTemplates, and full template content (subject + bodyHtml)
- Added `format_sequence_export()` — formats as readable markdown
- Added `/export_sequence [name]` Telegram command
- **CRITICAL BUG FOUND:** Setting `toRecipients: ["{{toRecipient}}"]` on templates causes ALL emails to fail with "Invalid recipients." Must be `[]`. Failed states cannot be retried/deleted via API — manual UI clicks required. Fixed all 12 templates across 3 sequences.
- Re-authorized OAuth with `sequenceStates.delete` scope added
- Schedule scopes (`schedules.read`/`schedules.write`) confirmed non-existent in Outreach API

### Send schedules (created in Outreach UI)
- **"Teacher Tue-Thu Multi-Window"** — Tue/Wed/Thu, 3 slots: 6:30-8 AM, 12-1 PM, 3:30-4:30 PM
- **"Admin Mon-Thurs Multi-Window"** — Mon/Tue/Wed/Thu, 3 slots: 6:30-8 AM, 10-11 AM, 3-5 PM
- **"Hot Lead Mon-Fri"** — Mon-Fri, 7 AM-4 PM
- Based on cross-referencing Claude.ai, Grok, Gemini, ChatGPT research on K-12 email timing (EdWeek survey, K-12 marketing data)

### Sequence copy rules overhaul
- Zero AI-written traces rule added
- Framing as pattern is Steven's preference over case studies
- Default variables: `{{first_name}}`, `{{company}}`, `{{state}}` (license requests = first_name only exception)
- Value props expanded: vertical alignment K-12, 10-product suite, implementation support, PCEP certification
- All URLs must be hyperlinked (not just codecombat.com/schools)
- Full seasonal calendar: Budget Season (Feb-Jun), Buying Season (Jul-Sep), Pre-Pilot (Oct-Dec), Pilot (Jan-Jun), Summer PD, Conference Season
- Minimum 5 days between ALL steps (license request Steps 1-3 are exceptions)

### CLAUDE.md maintenance
- Trimmed from 43,169 to 36,548 chars (under 40k limit). Condensed session history, collapsed completed status items, trimmed C4 implementation details.

### Key decisions
- CA excluded from Ballotpedia (thousands of results would swamp the signal database)
- Hourly check-ins and weekend greetings disabled (not useful currently)
- Outreach app settings page: `https://developers.outreach.io/apps/ai-coco-automation/edit?section=api`
- Schedule scopes don't exist — schedules are Outreach UI only, forever

### Architectural patterns
- All new signal sources (RSS, BoardDocs, Ballotpedia) follow same pattern: `scan_*()` function returns list of signal dicts → `write_signals()` handles dedup → wired into both orchestrators with try/except
- BoardDocs uses `urllib.request` (not httpx) since signal_processor already imports it
- RSS uses `feedparser` library (new dependency)
- Ballotpedia parses raw HTML with regex (no API available)

---

## Session 46 (2026-04-06)

### What was built
1. **Leadership change monitoring** — `scan_leadership_changes()` in signal_processor.py. Serper web search across 12 territory states for superintendent hires/resignations/retirements/searches. Claude Haiku extracts structured data. 8 changes found on first run (OH: Wilmington, Twinsburg, Sebring, Middletown, Poland; MI: Grosse Pointe, Okemos, Whitefish). Weekly Monday 8 AM CST via scheduler. `/signal_leadership` command. BoardDocs `_BOARD_LEADERSHIP_KEYWORDS` regex added for superintendent search/resignation/appointment agenda items. Display-layer risk flagging: active customer leadership changes show "⚠️ ACCOUNT RISK" in format_hot_signals and format_signal_detail.
2. **RFP monitoring** — `scan_rfp_opportunities()` in signal_processor.py. Serper + Claude Haiku with aggressive CodeCombat-relevance filtering. Prompt has explicit include list (CS/STEM/CTE curriculum, game-based learning, math, cybersecurity) and hard-exclude list (construction, devices, food, LMS, assessment). 0 results on first run (expected — RFPs are procurement postings, not news articles). Weekly Monday 8:15 AM CST. `/signal_rfp` command.
3. **Legislative signal scanner** — `scan_legislative_signals()` in signal_processor.py. State CS/STEM/CTE education mandates, bills, and policy changes. 2 signals found: TX HB 1481 tech mandate, IL CS education mandate. Monthly 1st Monday 8:30 AM CST (legislation moves slowly). `/signal_legislation` command. Urgency: enacted/signed = urgent, passed committee = time_sensitive. Heat score override: territory legislation gets minimum 30, enacted gets +15 bonus.
4. **Territory map visualization** — `tools/territory_map.py` (new file). Interactive Folium HTML map with 5 layers: Active Accounts (green, 18), Pipeline (orange, 12), Prospects (blue, 108), ESAs (purple, 0), All Districts (gray clustered, 7978). Clickable popups. Layer toggles. CartoDB positron tiles. Sent as Telegram file attachment (10.3 MB). `/territory_map [state]` command. `folium>=0.17.0` added to requirements.txt.
5. **BoardDocs noise filtering** — `_BOARD_FALSE_POSITIVE` regex in signal_processor.py. Rejects tech keyword matches when nearby context contains false positive words (wheelchair, food service, janitorial, expo, fair, family night, athletic, playground). Checks 50 chars before + 150 after each match.
6. **Permissions fix** — Global `Bash(*)` in `~/.claude/settings.json` and project `.claude/settings.local.json`. Replaced 50+ individual Bash command rules with single wildcard. Deny list still blocks rm -rf, dd, mkfs.

### Key decisions
- url="" for all Serper-based scanners (leadership, RFP, legislative). Same RFP/change gets indexed by multiple sources → different URLs → different composite dedup keys → duplicates. Empty url makes dedup key fall back to msg_id only. Full URL preserved in source_detail field.
- RFP urgency: all "time_sensitive" regardless of deadline. Deadline data from search snippets is unreliable. Deadline included in headline when Claude finds one.
- Legislative scan uses TERRITORY_STATES_WITH_CA (not just TERRITORY_STATES). A CS mandate in any territory state creates opportunity.
- Territory map sent as Telegram file (not GAS bridge). Folium HTML is 10+ MB — too large for GAS bridge POST, and Google Docs can't render interactive HTML anyway.
- BoardDocs false positive filter uses context window (50 chars before + 150 after) to catch phrases like "wheelchair accessible RFP" or "STEM Expo sponsorship" without blocking legitimate STEM/RFP signals.

### Bugs fixed during session
- territory_map: `gas` variable not in scope → created local GASBridge instance → then switched to Telegram file attachment entirely
- territory_map: `config.TELEGRAM_BOT_TOKEN` → should be direct import `TELEGRAM_BOT_TOKEN`

### Architectural patterns
- All three new scanners (leadership, RFP, legislative) follow identical pattern: Serper queries → URL dedup → single Claude Haiku batch call → JSON parse with fence stripping → post-process with NCES/customer status lookups → in-scan dedup → return signal list with url=""
- Scheduler now has 3 weekly/monthly events staggered by 15 min: leadership 8:00, RFP 8:15, legislative 8:30 (1st Monday only)
- territory_map.py is a lazy import (folium is heavy), only loaded when /territory_map command is used

---

## Session 47 (2026-04-07) — 15 Features Shipped + All Live-Tested

### Session Summary
Massive build session: 22 of 24 prospecting strategies now built. Signal system expanded from 10→19 sources, 16→31 commands. All features live-tested on Railway with Steven via Telegram. Core prospecting infrastructure is now COMPLETE — shifting to operating mode.

### Features Built (Phase 1 — before plan)
1. **Territory map enriched popups** — Active Accounts show licenses, revenue, enrollment, school count. Pipeline shows opp name, close date. Prospects show enrollment, priority. Districts show city.
2. **Signal heat overlay** — HeatMap layer on territory map showing signal density by district. Togglable.
3. **Grant-funded prospecting (#20)** — `scan_grant_opportunities()`. Monthly 1st Mon 8:45 AM. `/signal_grants`. ~$0.03/scan.
4. **Budget cycle targeting (#21)** — `scan_budget_cycle_signals()`. Monthly 1st Mon 9:00 AM. `/signal_budget`. ~$0.03/scan.
5. **AI Algebra campaign (#23)** — `scan_algebra_targets()`. On-demand. `/signal_algebra`. ~$0.03/scan.
6. **Cybersecurity pre-launch (#24)** — `scan_cybersecurity_targets()`. On-demand. `/signal_cyber`. ~$0.03/scan.
7. **Cohort/lookalike prospecting (#22)** — `find_lookalike_districts()`. $0. `/prospect_lookalike`.
8. **Fuzzy name matching** — `fuzzy_match_name()` with token subset + Jaccard. Applied to territory gap analysis + map.
9. **District Administration RSS** — only verified working feed of 6 tested.

### Features Built (Phase 2 — from plan v3)
10. **Role/title-based prospecting (#7)** — `scan_role_targets()`. Serper for rare titles only (CS/CTE/STEM directors, specialized teachers). ~$2.50/scan. On-demand. `/signal_roles [state]`.
11. **CSTA chapter prospecting (#8)** — `scan_csta_chapters()`. ~$1.20/scan. On-demand. `/signal_csta`.
12. **Sequence re-engagement (#11)** — `get_sequence_reengagement_overview()` + `scan_sequence_for_reengagement()`. Report-then-act: Mode 1 shows sequence list, Mode 2 scans one sequence by segment. `/prospect_reengagement`.
13. **Dormant lead detection (#12)** — `get_dormant_accounts()`. Requires >= 1 prior activity. `/dormant [days]`.
14. **Webinar campaign tags (#14)** — `_parse_csv_intent()` recognizes webinar keywords. Routes to Prospecting Queue.
15. **Pilot sequence template (#15)** — 4-step, 12-day pilot offer archetype in sequence_templates.md.

### Bugs Fixed During Live Testing
- **Lookalike Agency Type mismatch** — NCES stores full text ("Regular local school district") not numeric codes ("1"). Filter matched both.
- **Dormant name dedup** — "Los Angeles Unified School District" and "Los Angeles Unified" merged via normalize_name().
- **Reengagement territory filter** — was only checking .k12. domains, missing 95% of prospects. Added NCES district lookup + international TLD exclusion + territory-only filter.
- **Budget scanner false positive** — Cincinnati Health/PE curriculum adoption slipped through. Added exclusions for non-CS subjects.
- **CSTA territory filter** — Miami (FL) was showing up. Added territory state check before dedup.

### Key Decisions
- **Role/title scanning: Serper for rare titles only.** Common titles (Principal, Teacher, Math Teacher) are NOT searchable via Serper — too noisy, too expensive ($550/scan for one common title). Found through existing research engine + job scanner instead.
- **Sequence re-engagement: report-then-act, not auto-queue.** Different sequences have different contexts (CUE booth vs license request vs webinar). Auto-queuing into one bucket lost that context.
- **RSS feeds: only 1 of 6 tested works.** District Administration is valid. EdWeek, THE Journal, GovTech, EdSurge, SmartBrief all return malformed XML.
- **Cut from plan:** State procurement portal scrapers (fragile, marginal over Serper), Ballotpedia superintendent snapshots (marginal over existing leadership scan), Active Accounts column rename (zero user value), sequence copy audit (Steven's manual task).

### Architectural Patterns
- All new scanners follow same pattern: Serper queries → URL dedup → Claude Haiku extraction → NCES validation → customer status check → heat scoring → write signals
- Scheduler now has 5 monthly 1st Monday events: legislation 8:30, grants 8:45, budget 9:00 (+ weekly leadership 8:00, RFP 8:15)
- `fuzzy_match_name()` uses token subset (2+ token containment = 0.95 score) + Jaccard similarity with 0.7 threshold
- Reengagement overview uses single `get_sequences()` API call (no per-prospect scanning) for fast display
- `_last_reengagement_sequences` global caches overview for Mode 2 index lookup
