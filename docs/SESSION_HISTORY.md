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
