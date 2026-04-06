# SCOUT MASTER PLAN
*Last updated: 2026-04-06 — Session 45*

---

## YOU ARE HERE → Signal system expanded: RSS feeds (3), BoardDocs (25 districts), Ballotpedia bond tracking, signal-to-deal attribution all built and verified. 7 signal sources total. 3 Outreach sequences created (License Request 2026, Algebra Webinar Attendees/Non-Attendees). Sequence copy rules + send schedules fully documented. Next: leadership change monitoring, RFP monitoring, then verify Google Alert parser on ~April 9.

---

## COMPLETED: Signal Intelligence System — Phase 1 (Session 44)

### What was built
- `tools/signal_processor.py` — 3-tier processing pipeline (regex → Claude Haiku → clustering)
- 17-column Signals Database tab with heat scoring, time decay, urgency classification
- NCES district→state lookup (8,133 districts) for territory filtering
- Cross-reference against Active Accounts, Pipeline, Prospecting Queue, Closed-Lost
- 8 Telegram commands: `/signals`, `/signal_act`, `/signal_info`, `/signal_dismiss`, `/signal_scan`, `/signal_stats`
- Daily automated scan at 7:45 AM CST with retry logic
- Morning brief MARKET SIGNALS section with signal-of-the-day

### Batch results
- 380 Google Alert digests → 18,065 stories (all programmatic, $0)
- 41 Burbio newsletters → 201 signals (Claude Haiku extraction)
- 36 DOE newsletters → 135 signals (two-pass triage + Claude Haiku)
- **Total: 18,401 signals, 272 territory-relevant, 68 Tier 1, 46 clusters**
- **Cost: $0.30**
- 12 districts added to Prospecting Queue (Dallas ISD $6.2B, Richardson ISD $1.4B, Lamar ISD $1.9B, etc.)

### Signal sources expanded
- **DOE newsletters:** Subscribed to all 13 territory states (was OK + TN only). GovDelivery (TX, OH, MI, IN), CDE listservs (CA), state portals (MA, NE, NV, IL), listserv (CT), PENN*LINK request (PA).
- **Google Alerts overhauled:** 28→18 alerts. Removed 22 redundant (grade-level splits, esports, duplicate variants). Kept 6 core market awareness. Added 12 buying-signal alerts (3 bond, 3 leadership, 2 AI policy, 1 CTE, 1 tech, 2 territory).
- **Free newsletters:** K-12 Dive, EdWeek Market Brief, eSchool News, District Administration, CSTA.
- **Gmail filter:** `*SIGNALS` label auto-applied, skip inbox for all signal sources.

### Enrichment + Phase 2 additions (later in Session 44)
- **Signal enrichment layer:** `enrich_signal()` does Serper web search + Claude Haiku analysis for each Tier 1 signal. Returns: spending breakdown, CS/CTE relevance (strong/moderate/weak/none), key contacts, timeline, talking points, recommended action. Cost: $0.002/signal. Auto-runs on Tier 1 during daily scans.
- **Job posting scanner:** `scan_job_postings()` uses python-jobspy to scrape Indeed for CS/CTE/STEM teacher hiring across all 13 territory states. Filters to K-12 entities + CS-relevant roles only. Integrated into full scan + `/signal_jobs` standalone command.
- **Quality pass:** Expired 161 market_intel noise signals + 5 rejected/non-tech bonds. Signals went from 150→40 actionable territory signals.
- **Territory filtering fix:** `/signals` now defaults to territory-only (was showing NC, MD, etc.)
- **Urgency-aware decay:** Bond/leadership/RFP signals use minimal decay (0.97/week) so heat scores don't drop just because the email is old.
- **Google Alerts overhauled:** 28→18 alerts. Removed 22 redundant. Added 12 buying-signal alerts (bonds, leadership, AI policy, CTE, territory-specific).
- **Enrichment results for 12 queued districts:** 4 STRONG (Tulsa PS, Richardson ISD, Acton-Boxborough, Norwalk PS), 6 MODERATE, 2 WEAK.

### Next session starts with:
1. Check Tulsa PS bond vote result (April 7) — if passed, act immediately (Robert F. Burton, Exec Dir IT)
2. Act on 4 STRONG enriched signals — research contacts + draft outreach for Tulsa, Richardson, Acton-Boxborough, Norwalk
3. First new Google Alert digest arrives ~April 9 — verify parser handles new bond/leadership keyword sections
4. RSS feed ingestion for K-12 Dive, EdWeek Market Brief, eSchool News
5. BoardDocs board meeting agenda scraping (Phase 3 — complex, per-district setup)

---

## COMPLETED: C2 Research Engine Improvements

### What C4 is
Cold license requests are inbound prospects who requested a CodeCombat license through Outreach sequences but Steven never connected with them — no opportunity was created, no pricing was sent. These are warm leads that went cold. Strategy label: `cold_license_request`.

### Why we're doing it
These are the lowest-hanging fruit for re-engagement. They already showed interest by requesting a license. Steven just needs to reach back out.

### How it works
The `/c4` command scans 3 Outreach license request sequences (IDs 507, 1768, 1860), pulls all prospects, then filters through multiple layers:
1. Student email exclusion ("student" in domain)
2. Active customer check (already in Active Accounts)
3. Existing queue check (already in Prospecting Queue)
4. Existing opp check (Pipeline or Closed Lost)
5. International email TLD exclusion
6. State extraction from email domain (k12, .gov, state abbreviations, city names)
7. SF data-driven domain→state lookup (built from real SF Leads/Contacts emails)
8. Territory matching against NCES data (email_priority=True)
9. Claude Sonnet batch inference for remaining unknowns
10. SoCal domain check for CA prospects (KNOWN_SOCAL_DOMAIN_ROOTS)
11. Pricing detection via bulk mailing scan (PandaDoc links, subject lines)

Surviving prospects are added to the Prospecting Queue with email, first name, last name visible.

### C4 Sub-tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Build C4 scan end-to-end | ✅ Done (Session 34) | Outreach API → territory matching → Claude inference → Prospecting Queue |
| 2 | Connect Outreach API | ✅ Done (Session 34) | OAuth2, read-only, user ID 11 |
| 3 | Bulk mailing pricing detection | ✅ Done (Session 34) | 3 API calls vs 1,600+ |
| 4 | territory_matcher.py core utility | ✅ Done (Session 34) | 5-tier matching + Claude inference |
| 5 | Fix: Email domain priority over company name | ✅ Done (Session 35) | `email_priority=True` param |
| 6 | Fix: SoCal domain check before CA exclusion | ✅ Done (Session 35) | `is_socal_domain()` + KNOWN_SOCAL_DOMAIN_ROOTS |
| 7 | Fix: Student email detection (broad) | ✅ Done (Session 35) | "student" anywhere in domain |
| 8 | Fix: Claude prompt email domain emphasis | ✅ Done (Session 35) | Explicit instruction + examples |
| 9 | Fix: Lead-level columns in Prospecting Queue | ✅ Done (Session 35) | Email, First Name, Last Name (19 columns total) |
| 10 | Fix: k12.STATE.us/gov state extraction | ✅ Done (Session 35) | Handles 3+ part domains, .gov TLD, DC |
| 11 | Comprehensive state extraction from email | ✅ Done (Session 35) | k12, .gov, state suffixes, separators, state names, city names |
| 12 | SF data-driven domain→state lookup | ✅ Done (Session 35) | Reads real emails from SF Leads/Contacts tabs |
| 13 | Known SoCal domain abbreviation list | ✅ Done (Session 35) | 90+ hardcoded + containment matching |
| 14 | Column migration (16→19 cols) | ✅ Done (Session 35) | `/fix_queue`, `/cleanup_queue` commands |
| 15 | Spot-check accuracy of states | ✅ Done (Session 37) | Multiple rounds of spot-checking + fixes. Empty states: 301→113. |
| 16 | Spot-check SoCal exclusions | ✅ Done (Session 37) | SoCal false exclusions: 11→3. Company name verification added. |
| 17 | Serper web search (school name + email) | ✅ Done (Session 37) | Searches like Steven does manually. Parallel, deduped. |
| 18 | Parent district enrichment | ✅ Done (Session 37) | NCES re-matching + Serper extraction. 100% coverage. |
| 19 | Deterministic international detection | ✅ Done (Session 37) | TLDs, edu domains, school name keywords, search content signals. |
| 20 | API cost tracking | ✅ Done (Session 37) | Shows est. cost in /c4 completion message. |
| 21 | Final verification + sign-off | ✅ Done (Session 37) | Steven verified: 1,274 targets, 113 empty, 100% district coverage. |

### Mid-flight additions to C4 (things that came up during implementation)
- **Prospecting Queue column redesign** — added Email, First Name, Last Name columns so contact info isn't buried in Notes. Required migrating all existing rows from 16→19 columns.
- **`/fix_queue` and `/cleanup_queue` commands** — needed to fix data after column migration issues.
- **Comprehensive state extraction** — original plan was just territory matching + Claude. Spot-checking revealed email domains like `k12.va.us`, `harmonytx.org`, `schools.nyc.gov` weren't being parsed for state info. Built a multi-pattern extractor.
- **SF data-driven domain lookup** — hardcoded abbreviation lists weren't enough. Built a system that reads real email→state pairs from SF Leads/Contacts to learn domain mappings automatically.
- **Known SoCal domain list** — territory matcher's generated roots missed creative abbreviations like `sandi` (San Diego), `ggusd` (Garden Grove), `myabcusd` (ABC USD). Added 90+ known roots.
- **CLAUDE.md trimming** — file grew past 40k char limit (impacts Claude Code performance). Trimmed to 29k, moved detailed history to `docs/SESSION_HISTORY.md`.

---

## FULL ROADMAP

### Part A: Quick Wins — ALL DONE (Session 23)

| # | Enhancement | What it does | Status |
|---|------------|-------------|--------|
| A1 | `/call_list [N]` custom count | Parse optional number, clamp 1-50, default 10 | ✅ Done |
| A2 | Command cheat sheet in morning brief | `_COMMAND_CHEAT_SHEET` appended to morning brief | ✅ Done |
| A3 | Color-code lead rows by confidence | Auto-colors after research. VERIFIED=green, LIKELY=yellow-green, INFERRED=yellow, UNKNOWN=grey | ✅ Done |

### Part B: Medium Features — ALL DONE (Sessions 23-30)

| # | Enhancement | What it does | Status |
|---|------------|-------------|--------|
| B1 | Weekend scheduler | Sat 11am, Sun 1pm greeting. No auto check-ins. `/eod` for manual EOD. | ✅ Done |
| B2 | SF Leads/Contacts import + enrichment | Import Salesforce lead/contact CSVs. Cross-check against Active Accounts. Math filter tabs. Serper enrichment. Separate Google Sheet. | ✅ Done (verified Session 30, 8/8 tests) |

**B2 mid-flight additions:**
- Sessions 25-26: SoCal CSV filtering scripts (5 passes, offline, needed for real data testing)
- Session 27: Merged territory CSV files (86k leads + 20k contacts)
- Sessions 27-28: Cross-check rule refinement (school vs district matching rules clarified by Steven)

### Part C: Large Projects

| # | Enhancement | What it does | Status |
|---|------------|-------------|--------|
| C1 | Territory Master List | NCES CCD data for 13 states + SoCal. 8,133 districts, 40,317 schools. Gap analysis. | ✅ Done (Sessions 31-32) |
| C3 | Closed-Lost Winback | Scan closed-lost opps, add to Prospecting Queue. Date window filtering. Draft sequences. | ✅ Done (Sessions 33-34, verified) |
| C4 | Cold License Requests | Scan Outreach sequences for cold inbound requests. Full pipeline: pattern extraction → SF lookup → NCES matching → Claude inference → Serper web search → district enrichment. 1,274 targets, 113 empty states, 100% district coverage. | ✅ Done (Sessions 34-37, verified) |
| C2 | Research Engine Improvements | Multi-tool pipeline (Exa+Brave+Serper), parallelized, quality validation, tighter targeting. 2-3x more contacts, 4-34x more verified emails. | ✅ Done (Sessions 39-40) |
| C5 | Proximity + Regional Service Centers | Targeted proximity search near active accounts. ESA/ESC mapping using NCES Agency Type 4 data. `proximity [account]`, `esa [state]`, `add nearby`. | ✅ Done (Session 42) |

**Note:** C4 was originally described as "Unresponsive leads strategy" in the roadmap but evolved during implementation into "Cold License Requests" — specifically targeting inbound license requests from Outreach sequences that went cold (no opp, no pricing). This is a more focused and actionable definition than generic "unresponsive leads." The original C4 concept of tracking outbound attempts + non-response may still be built later as a separate feature.

### Unplanned Work (things that came up between roadmap items)

| When | What | Why |
|------|------|-----|
| Sessions 25-26 | SoCal CSV filtering (5-pass offline scripts) | Needed to filter 20k+ SoCal leads/contacts before B2 could use real data |
| Session 27 | Merged territory CSV creation | Combined SoCal + non-SoCal lead/contact files for complete dataset |
| Session 34 | Prospecting Queue column redesign | C4 needed email/name columns visible, not buried in Notes |
| Session 35 | CLAUDE.md trimming + SESSION_HISTORY.md | Performance warning at 41.9k chars. Moved detailed history to separate file. |
| Session 35 | `/fix_queue`, `/cleanup_queue` commands | Column migration from 16→19 created data alignment issues |
| Session 36 | Session transcript auto-capture | `scout` command wraps Claude Code with `script`, auto-cleans + commits transcripts to `docs/sessions/` |
| Session 36 | Plan view format locked in | Dialed in exact format for plan brief view — saved to memory as template for all future sessions |
| Session 38 | Todo List Feature | Replace hourly check-ins with todo list management. Google Sheet tab, Telegram commands, Claude tool. |
| Session 38 | CUE 2026 lead enrichment | 1,298 conference leads enriched via 5-layer pipeline. State, district/school, county, NorCal/SoCal. Rep routing tabs (Steven/Tom/Liz/Shan). `scripts/enrich_cue_leads.py` |
| Session 38 | Outreach write access | OAuth re-authorized with write scopes for sequences, steps, templates, prospects. Ready to build sequence creation. |
| Session 38 | Session transcript numbering fix | `scout_session.sh` checks .raw/ files + CLAUDE.md cross-check |
| Session 38 | GitHub token regenerated | Fine-grained PAT expired, regenerated |
| Session 38 | Outreach sequence creation | Built create_sequence() API. 11 CUE sequences + 940 prospects loaded. Interval bug discovered (seconds not minutes). |
| Session 38 | CUE booth apology sequence | Sent apology for 4-email spam caused by interval bug |
| Session 39 | Session numbering fix | `scout_session.sh` auto-detect now uses CLAUDE.md as source of truth, not just transcript files. Fixes drift when sessions run without `scout` wrapper. |

---

## UP NEXT

### Outreach Sequence Creation — DONE (Session 38)
**What:** Create email sequences directly in Outreach.io via API.
- `create_sequence()` in `outreach_client.py` — creates sequence + steps + templates + links
- 6 CUE booth sequences (4 steps: custom + existing template) + 5 CUE opt-in sequences (3 steps) + 1 apology sequence
- 58 booth + 883 opt-in prospects loaded
- **CRITICAL LESSON:** Outreach interval is in SECONDS not minutes. Caused all booth emails to fire in hours. Fixed + apology sent.
- **Creation order:** create → Steven activates in UI → toggle templates → then add prospects via API

### C2: Research Engine Improvements — IN PROGRESS
**What:** Make the district research engine faster and more accurate.

**Session 39 analysis complete — parallelization plan approved:**
- **Group A (parallel):** L1, L2, L3, L4, L5, L13, L14 — all independent Serper searches, run concurrently
- **Group B (after L4):** L6→L7→L8 chain + L11, L12 in parallel — all need district_domain from L4
- **Group C:** L9 Claude extraction (needs all raw_pages from A+B)
- **Group D:** L10→L15→L10 sequential (unchanged)
- Also: add asyncio.Lock for serper counter race condition, shared httpx client

**Sub-tasks:**
- ✅ Layer dependency analysis + parallelization plan (Session 39)
- ✅ Tool landscape research — 7 tools evaluated (Session 40)
- ✅ Evaluation framework built — `scripts/eval_research_tools.py` (Session 40)
- ✅ Phase 1 content comparison — Tavily (160K chars, 12s) + Exa (133K chars, 3s) = 3-4x more content than baseline (Session 40)
  - ➕ Python 3.13 venv + all deps installed
  - ➕ API keys: Jina, Tavily, Exa, Firecrawl, Parse.bot (all free tiers)
  - ➕ Parse.bot MCP configured in `.mcp.json`
- ✅ Test Parse.bot MCP (backend DNS down, deferred)
- ✅ Firecrawl tested — extract with schema is breakthrough tool (deferred: paid plan needed, budget)
- ✅ Run Claude extraction on top tools — Exa wins for email yield
- ✅ Scale evaluation to all 8 test districts — 188 contacts, 163 w/email across 8 districts
- ✅ Build deep research engine v4 — 8-stage multi-tool pipeline (`scripts/eval_deep_research.py`)
- ✅ Integrate into production — L16 (Exa broad), L17 (Exa domain-scoped), L18 (Firecrawl extract), L19 (Firecrawl site map), L20 (Brave Search) added to `tools/research_engine.py`
- ✅ Implement parallel groups — Phase A (6 layers parallel), Phase B (domain), Phase C (8 layers parallel)
- ✅ Better Claude extraction prompts — district-specific, table alignment rules, CTE filtering
- ✅ Quality validation — cross-district filter, name↔email validation, two-pass extraction filter
- ✅ Lead targeting tightened — `agent/target_roles.py` from Steven's roles/keywords doc
- ✅ Live A/B test — Austin ISD: 77→124 contacts (+61%), 12→48 verified (+300%). Kern: 35→115 (+229%), 1→34 verified (+3300%)
- ✅ API keys deployed — EXA_API_KEY + BRAVE_API_KEY on Railway
- ✅ Permissions allowlist cleaned up for Claude Code
  - ➕ Brave Search API signed up + integrated
  - ➕ `agent/target_roles.py` — authoritative role/keyword/CTE filter from Steven's doc
  - ➕ `contact_extractor.py` max_tokens 2000→4000 (truncation fix)
  - ➕ 24 prospecting strategies documented in memory
- 🔧 **Firecrawl paid plan deferred** — budget constraint. L18/L19 skip gracefully. Circle back later.
- ✅ Live verification on Railway (Session 42) — Houston 8→82/2→44, Columbus 29→90/0→18, Guthrie 1→52/0→26, Leander 11→31/3→14
  - ➕ Natural language research dispatch (bypasses Claude routing)
- 🔧 **Firecrawl paid plan deferred** — budget constraint. L18/L19 skip gracefully. Circle back later.
- 🔧 **Parse.bot deferred** — server-side DNS failure after migration. Emailed founder.
- ⬜ Claude tool_use for interactive, adaptive extraction
- ⬜ Monthly improvement cadence (check-up on new tools/models)

### C5: Proximity + Regional Service Centers — DONE (Session 42)
**What:** Two related prospecting strategies:
1. **Proximity:** Find districts/schools near a specific active account. Adjustable radius. Name-drop for FOMO.
2. **ESA mapping:** Map districts to their ESC/BOCES/IU using NCES Agency Type 4 data. Shows which ESAs serve regions where Steven has active accounts.

**Sub-tasks:**
- ✅ `tools/proximity_engine.py` — haversine distance, targeted proximity, ESA mapping
- ✅ Targeted mode: `proximity Liberty Hill ISD` — districts + schools near one account, 15mi default
- ✅ Adjustable radius: `proximity Liberty Hill ISD 30` — wider/narrower search
- ✅ Add to queue: `add nearby 4,8,13` — pick which districts to queue from results
- ✅ State sweep: `proximity Texas all` — bulk mode for all accounts in a state
- ✅ ESA mapping: `esa Texas` — 20 ESCs found, active accounts mapped, uncovered districts shown
- ✅ ESA patterns expanded: 11 → 78 entity names from Steven's ROLES and KEYWORDS doc
- ✅ Priority scoring: proximity strategy (400-699), esa_cluster strategy (450-599)
- ✅ Graceful handling: OK returns "no ESA system", OH found 100 Agency Type 4 entities
- ✅ All commands bypass Claude — direct dispatch via natural language matching

---

## COMPLETED: C4 Sequence Automation (Session 43)

### What was done
- Enriched 1,274 C4 prospects: 2-pass enrichment (title, state, parent district, international detection)
- Wrote 4 email sequences through 7 iterations with Steven's feedback
- Created "C4 Tue-Thu Morning" Outreach schedule (ID 50): Tue/Wed/Thu 8-10 AM prospect local time
- Created 4 sequences in Outreach via API (IDs 1995-1998)
- Loaded 1,119 prospects (150 correctly rejected: opted out or already in another sequence)
- Updated 135 prospect timezones in Outreach from state data
- Fixed 11 CUE sequences that had "No schedule" delivery setting

### Sequences
| ID | Name | Prospects | Steps |
|----|------|-----------|-------|
| 1995 | C4 License Re-Engage — Teachers | 422 | 6 |
| 1996 | C4 License Re-Engage — District/Admin | 184 | 5 |
| 1997 | C4 License Re-Engage — School (General) | 403 | 6 |
| 1998 | C4 License Re-Engage — District (General) | 110 | 5 |

### Key learnings saved to memory
- `feedback_sequence_copy_rules.md`: Steven's detailed rules for writing sequences
- `feedback_sequence_iteration_learnings.md`: What was rejected/approved through 7 iterations (no sales cliches, lead with engagement not AI, specific subject lines, budget angles, etc.)

---

## COMPLETED: Signal System Expansion + Outreach Sequences (Session 45)

### Signal sources added
- **RSS feeds:** K-12 Dive, eSchool News, CSTA. feedparser library. Classified through existing regex pipeline ($0). `/signal_rss` command. 220 articles ingested on first run.
- **BoardDocs scraper:** 25 territory districts (TX 5, OH 4, IL 5, PA 3, CT 3, MI 4, IN 1). Auto-discovers committee IDs. Scans recent meeting agendas for tech/CS/CTE/bond keywords. 17 signals on verified run. `/signal_board` command.
- **Ballotpedia bond tracking:** Scrapes ballotpedia.org for K-12 bond measures in 12 territory states (CA excluded — too many). Tracks upcoming votes + passed/failed results. 37 territory measures found including Tulsa PS 4 propositions. `/signal_bonds` command.
- **Signal-to-deal attribution:** Pipeline Link column on Signals tab + Signal ID column on Prospecting Queue (19→20 columns). `/signal_act` now passes signal ID through and writes Pipeline Link back.

### Infrastructure fixes
- Signal dedup fix: `get_processed_message_ids()` now reads both Message ID + Source URL columns to build composite keys matching `write_signals` logic.
- BoardDocs/Ballotpedia/RSS wrapped in try/except in both orchestrators — one source failing can't crash the daily scan.
- Disabled hourly check-ins and weekend greetings (not useful currently).

### Outreach sequences created
| ID | Name | Steps | Type |
|----|------|-------|------|
| 1999 | !!!2026 License Request Seq (April) | 7 | Inbound license request |
| 2000 | Algebra Webinar Seq (April 2026) Attendees | 4 | Webinar follow-up |
| 2001 | Algebra Webinar Seq (April 2026) Non-attendees | 4 | Webinar follow-up |

### Outreach API improvements
- Added `_api_patch()` method to outreach_client.py
- Added `export_sequence()` + `format_sequence_export()` for pulling full sequence content
- Added `/export_sequence` Telegram command
- **CRITICAL FIX:** `toRecipients` must be `[]` (empty) on all templates. Setting to `["{{toRecipient}}"]` causes all emails to fail with "Invalid recipients" — and failed states can't be retried via API.
- Re-authorized OAuth with `sequenceStates.delete` scope
- Schedule scopes confirmed non-existent — schedules are UI-only

### Send schedules created (Outreach UI)
- "Teacher Tue-Thu Multi-Window" — Tue/Wed/Thu, 3 slots: 6:30-8 AM, 12-1 PM, 3:30-4:30 PM
- "Admin Mon-Thurs Multi-Window" — Mon/Tue/Wed/Thu, 3 slots: 6:30-8 AM, 10-11 AM, 3-5 PM
- "Hot Lead Mon-Fri" — Mon-Fri, 7 AM-4 PM

### Sequence copy rules fully updated
- Zero AI-written traces, stand out from pack
- Framing as pattern is Steven's preference over case studies
- Default variables: {{first_name}}, {{company}}, {{state}} (license requests = first_name only)
- Value props expanded (vertical alignment, 10-product suite, implementation support)
- All URLs must be hyperlinked
- Full seasonal calendar: Budget Season (Feb-Jun), Buying Season (Jul-Sep), Pre-Pilot (Oct-Dec), Pilot (Jan-Jun), Summer PD, Conference Season

---

## IN PROGRESS: Trigger-Based Prospecting Aggregator

### Research complete (Session 43)
- K-12 buying signals ranked by conversion (bonds > leadership changes > board meetings > RFPs > job postings > grants)
- Burbio deep dive: ~$4,500/yr, can replicate 60-70% for free
- AI aggregator architecture patterns (auto-news GitHub, RSS+LLM pipeline)
- MCP inventory: Apify, Tavily, JobSpy, RSS MCP, Twitter MCP, Puppeteer MCP
- Full research saved to `docs/trigger_aggregator_research.md`

### Infrastructure ready
- GAS bridge enhanced with `search_inbox_full` (full email bodies + pagination)
- Railway API token configured for local env var access
- Gmail scanning verified: can read full content of all 500+ emails

### Gmail signal sources discovered
- 29 Google Alerts (359 weekly digests since mid-2025)
- 41 Burbio newsletters from Dennis Roche (weekly since Mar 2025)
- 118 DOE/newsletter emails (OK State Dept of Ed, TN STEM Innovation, OKEdTech, OKLibraries)
- Only subscribed to OK + TN newsletters (11 states missing)

### Territory-specific signals found in Burbio (need action)
- Dallas ISD, TX: $6.2B bond with $144M tech upgrades
- Tulsa Public Schools, OK: $200M+ bond (STEM labs, CTE, software)
- Marquette Area Public Schools, MI: $60M bond (science labs, CTE)
- Somers Public Schools, CT: Establishing K-12 AI Committees
- Acton-Boxborough Regional, MA: Creating K-8 STEAM Coordinator + Robotics/Engineering position
- Seward Public Schools, NE: $25M bond

### Phase plan
- **Phase 1:** ✅ DONE (Session 44) — Process Gmail emails, subscribe DOE newsletters, enhance Google Alerts
- **Phase 2:** ✅ DONE (Session 45) — RSS feeds (3), BoardDocs (25 districts), Ballotpedia bond tracking, signal-to-deal attribution
- **Phase 3 (in progress):** Leadership change monitoring, RFP monitoring (state procurement portals). Signal clustering + auto-scoring already exists.
- **Phase 4 (future):** BoardDocs noise filtering improvements, additional RSS/signal sources

---

## UP NEXT (after aggregator)

### Territory Map Visualization
- Digital map of Steven's territory with pins for active accounts, pipeline, prospects, ESAs
- All data already exists (lat/lon, addresses, enrollment, status)
- Saved in memory for future implementation

---

## PARKED FOR LATER (Steven asked to revisit at a future time)

### Sequence Copy Improvements
- Outreach.io variables not being used — sequences have hardcoded names instead of `{{first_name}}`, `{{company}}`, `{{state}}` etc.
- Product accuracy in sequences: **AI Junior = still in beta (NOT released)**, AI Algebra = launched (reference as new offering), CyberSecurity course = planned fall 2026 (can say "coming soon")
- Inaccurate product claims in sequences damage credibility
- **When:** After C4 is done, when we next build/edit sequences

### Fuzzy Matching for Territory Cross-Check
- Territory school→district lookup currently uses exact normalized name matching
- Only 17 out of ~93 schools matched their parent district (very low hit rate)
- NCES and Salesforce spell school names differently (e.g., "Huntington Beach High School" vs "Huntington Beach Senior High School")
- **Fix needed:** Levenshtein distance, token overlap, or substring matching. Could also try city+state+school-type as secondary lookup.
- Would improve Parent District values for winback and C4 targets
- **When:** Future enhancement, could be folded into C2 research engine improvements

### Active Accounts Column Rename
- "Display Name" → "Active Account Name" in the Google Sheet header
- Will happen automatically on next account CSV import (csv_importer rewrites header)
- Until then, all code reading Active Accounts must check BOTH column names
- **When:** Automatic on next CSV import — no action needed

### ~~Automate Sequence Creation for C4 Prospects~~ — DONE (Session 43)
- Completed: 4 sequences created in Outreach, 1,119 prospects loaded

### Original C4 Concept: Track Outbound Non-Response
- The original roadmap described C4 as "unresponsive leads" — tracking outbound contact attempts + detecting non-response
- We redefined C4 to focus on cold license requests (more specific and actionable)
- The broader "contacted 30+ days ago, no reply detected" concept could still be built as a separate feature
- Would need activity tracking to distinguish sent vs replied
- **When:** TBD, after current C4 and C2 are done

---

## KEY DECISIONS LOG

| Date | Decision | Why | Impact |
|------|---------|-----|--------|
| 2026-03-08 | Approved roadmap A1-C5 in order | Steven reviewed full system, identified priorities | Authoritative plan — don't deviate without approval |
| 2026-03-19 | C3 winback: all sequences are DRAFTS | Steven must review before sending | Applies to ALL strategies, not just winback |
| 2026-03-20 | C4 redefined as cold license requests | Original "unresponsive leads" too broad. Cold license requests = specific, actionable | Changed strategy from "re-engage" to "cold_license_request" |
| 2026-03-20 | Outreach API: read-only ONLY | Steven's explicit instruction. Never add write operations. | ~~Hard rule~~ **SUPERSEDED Session 38** |
| 2026-03-29 | Outreach API: write access for sequences only | Steven wants to create sequences programmatically instead of manual copy/paste | Write scopes: sequences, sequenceSteps, sequenceStates, sequenceTemplates, templates, prospects. Do NOT write to other resources without approval. |
| 2026-03-29 | Steven's territory: TX, CA-SoCal, IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE | These are the 13 states from C1 Territory Master List | Must know this by heart — never ask again |
| 2026-03-23 | Email domain > company name for location | Salesforce company names are self-reported, often wrong | `email_priority=True` in territory matching for C4 |
| 2026-04-04 | C4 sequences: 4 buckets by role + entity type | Teachers, District/Admin, School(general), District(general). Enrichment got 53% title coverage. | 1,119 prospects loaded across 4 Outreach sequences |
| 2026-04-04 | Outreach send schedule: Tue/Wed/Thu 8-10 AM | Research showed Tue-Thu morning optimal for educators. Prospect timezones set from state data. | C4 Tue-Thu Morning schedule (ID 50) |
| 2026-04-05 | Build DIY Burbio alternative | Burbio costs ~$4,500/yr. Can replicate 60-70% free via BoardDocs scraping, Ballotpedia, job monitoring | 3-phase aggregator plan in docs/trigger_aggregator_research.md |
| 2026-03-23 | Build domain→state from real SF data | Hardcoded lists can't capture all creative abbreviations | SF Leads/Contacts emails used as training data |
| 2026-03-24 | Don't exclude unknown-state prospects yet | Need to verify state extraction works well first | Keep in queue for review, exclude later once confident |
| 2026-03-24 | SCOUT_PLAN.md as living detailed plan | Steven needs visibility into where we are, what changed, and why | Updated every session, brief view in terminal/Telegram |
| 2026-03-25 | Session transcript auto-capture via `scout` command | Steven needs to search/scroll past sessions verbatim | `scout` wraps `claude` with `script`, auto-cleans + commits to docs/sessions/ |
| 2026-03-25 | Plan view format locked in | Spent time dialing in — saved exact template to memory | No tables, emoji markers, ➕ nested additions, consistent structure |
| 2026-03-25 | Use `/exit` not `/clear` between sessions | `scout` wrapper needs Claude Code to exit to finalize transcript | Each `scout` run = one clean transcript file |
