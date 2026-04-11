# SCOUT — Claude Code Reference
*Last updated: 2026-04-11 — End of Session 57 (BUG 1 + BUG 2 closed — zero Fire Drill Audit bugs remain)*

---

## CURRENT STATE — update this after each session

**Session 57 closed the last two bugs from the Session 53 Fire Drill Audit.** BUG 1 (F4 CS funding scanner) shipped across 3 commits: query redesign + `STATE_DOE_NAMES` constant (13 territory states mapped to actual grant-issuing agency proper names, not the broken generic "<State> State Board of Education" template) + shrunk `STATE_CS_PROGRAMS` to verified-3 (IL "Computer Science Equity Grant", PA "PAsmart", OH "Computer Science Promise") + per-state chunked Haiku extraction (temperature=0) + `scripts/f4_serper_replay.py` diagnostic harness + hand-verified `scripts/f4_oracle.json` (14 rows) + oracle gate pass at **84.2% HIGH precision (16/19 real)** + kill switch flip. Live Railway run via `/signal_funding`: **43 signals written + 8 HIGH auto-queued prospects** (Midland ISD $674K, Berwick Area SD, Northwest Local SD, Sto-Rox $75K, Philadelphia SD $450K, DuBois Area SD $450K, Riverside USD $5.5M, Tippecanoe SC) — from the 0-extractions baseline F4 had since Session 49. BUG 2 (F5 CSTA) shipped as a single commit: F5 daily scanner retired permanently + `scripts/fetch_csta_roster.py` two-phase fetcher (Serper discovery + browser-UA httpx + BeautifulSoup + Haiku extraction) → `memory/csta_roster.json` (39 entries, 14 matchable across CA/PA/OH/TX) + `signal_processor.enrich_with_csta(district, state)` lookup helper (exact → token-subset-with-multi-candidate-disambiguation → fuzzy at 0.7 threshold) + `district_prospector.add_district(priority_bonus=N)` kwarg + F2 auto-queue integration (on CSTA hit: notes prepended with `CSTA chapter match: NAME (ROLE, CHAPTER). Source: URL` and priority +50) + `/signal_csta` handler repurposed from scan-trigger to roster-display grouped by state. Live smoke tests: `/signal_csta` returned grouped roster without exception; `/signal_competitors` completed cleanly with 1 HIGH auto-queue (North Ridgeville OH, no CSTA enrichment hit — expected with a 14-entry roster × 1-HIGH scan). **Zero bugs remain.**

**What's working after Session 57:**
- **F4 CS funding scanner live** (`ENABLE_FUNDING_SCAN=True`). Queries = Type A natural-language "awarded" + unquoted-state + quoted-"school district" + Type C state DOE proper name (quoted) + Type F "STEM grant" + Type G `site:.gov` + Type B verified program name (when available). 6-7 queries per state × 13 states = 71 queries per scan at ~$0.09/scan total. Downstream routing loop (HIGH→queue, MED/LOW→signals, active→intel) unchanged from Session 52 — only the Serper + Haiku legs were rewritten. 14 K-12 LEA grants currently in `memory/../scripts/f4_oracle.json` as the ground-truth reference.
- **F2 CSTA enrichment wired and live.** F2's HIGH-confidence auto-queue block now calls `enrich_with_csta(district, state)` and augments the queue row when a match exists. Scanner is F2 only this session; F1/F4/F9/F6/F7/F8 wiring is a mechanical follow-up once the pattern is proven.
- **CSTA roster is static reference data** at `memory/csta_roster.json`. Refresh manually via `python3 scripts/fetch_csta_roster.py`. Committed to git. 39 entries total, 14 with parseable K-12 district affiliation across CA (heaviest — 10 districts including Vallejo City USD, Sweetwater Union HSD, Reedley, etc.), PA (Warwick, Plum Borough SD), OH (Paula Caso @ North Olmsted HS), TX (1 private — filtered at enrichment match time).
- **`district_prospector.add_district` accepts `priority_bonus: int = 0`** kwarg — popped before forwarding to `_calculate_priority` and added after. Default 0 preserves every existing call site. Any enrichment source can use this; CSTA is the first caller.
- **`ENABLE_CSTA_SCAN=False` permanently.** `scan_csta_chapters` function is still in `signal_processor.py` as dead code for rollback safety — short-circuits via the kill switch. `/signal_csta` no longer triggers it; old scan path is dead.
- **BUG 4 diocesan research playbook** (from Session 56) still live. `ENABLE_DIOCESAN_PLAYBOOK=True`. 16 Catholic dioceses pending in the Prospecting Queue — approval drip is Priority 4 carryover.
- **BUG 5 two-stage cross-district filter** (from Session 55) still live. `ENABLE_RESEARCH_CONTAM_FILTER=True`.
- **Telethon bridge + screencapture + Railway log API** still functional for Claude Code → Scout end-to-end orchestration.
- **Leads from Research tab is clean** (from Session 56). 482 rows, zero real cross-contamination.

**What's still in-progress / unresolved (carryover for Session 58):**
- **`Prospecting Queue BACKUP 2026-04-10 0010` tab** still in the sheet. Safe to delete.
- **Sequence builder diocesan branch not written.** Any of the 16 pending Catholic dioceses that get approved will produce cold-framed sequence docs needing manual rewrites.
- **Diocesan email verification ceiling.** Playbook finds central-office names but can't produce VERIFIED emails without paid tools (Apollo/RocketReach/Hunter) or L8 pattern inference.
- **CSTA enrichment only wired to F2.** F1/F4/F9/F6/F7/F8 integrations pending. One-line add per scanner.
- **Session 52 Stages 6-8 carryover still untouched.** Charter CMOs + CTE centers, F9 CA pilot, F1 backlog drip (384 pending `intra_district` rows).

**Zero bugs remain from the Session 53 Fire Drill Audit.** All 5 silent-failure bugs are closed: BUG 3 (Session 55), BUG 5 (Session 55), BUG 4 (Session 56), BUG 1 (Session 57), BUG 2 (Session 57).

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits (`54e7fed`, `2c8ebfb`, `a2d43ea`, `69ec3b8`). Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits. Plan: `~/.claude/plans/sunny-riding-aurora.md`
- **Session 53:** Fire drill audit. F2 max_tokens fix (commit `7c345a07`). 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.
- **Session 51:** Tier B+C Lead Gen (F5/F6/F7/F8/F9/F10 shipped), F4+F2 URL bug fix, F2 complete rewrite.

### What still needs to be done (Session 58 — post-bug-sprint)

1. **PRIORITY 1 — Session 52 Stages 6-8 carryover.** Charter CMOs + CTE centers (Stage 6), F9 compliance CA pilot (Stage 7, Signals-only validation), F1 backlog drip (Stage 8 — 384 pending `intra_district` rows). These have been parked since Session 52 behind the bug-fix sprint. Now unblocked.
2. **PRIORITY 2 — Diocesan approval drip.** 16 Catholic dioceses pending in the Prospecting Queue since Session 56. Approve in batches via `/prospect_approve` — playbook activates automatically. Expect name-only yield (diocesan sites don't publish emails). Write sequence_builder diocesan branch BEFORE approving OR accept cold-framed fallback + manual rewrites.
3. **PRIORITY 3 — Extend CSTA enrichment to other scanners.** Wire `enrich_with_csta` into F1/F4/F9 auto-queue blocks (one-line call each, same pattern as F2). F6/F7/F8 seed-queuers get it too.
4. **PRIORITY 4 — Grow the CSTA roster.** Current fetcher surfaced 14 matchable entries. Options: (a) hand-curate known board members for sparse states (IL, TX, MA, NE, etc.); (b) iterate fetcher queries for non-csteachers.org sources (state CSTA social, LinkedIn directory); (c) accept current yield and let it grow organically on quarterly refresh.
5. **Cleanup items:**
   - Delete `Prospecting Queue BACKUP 2026-04-10 0010` tab once comfortable
   - Approve 8 F4 auto-queued prospects from Session 57's live run (Midland ISD, Berwick, Northwest Local, Sto-Rox, Philadelphia, DuBois, Riverside, Tippecanoe) — Tippecanoe is a borderline Indiana DOE robotics grant, consider skipping
   - Consider pursuing diocesan email verification upgrade (paid Apollo/RocketReach/Hunter, or L8 pattern inference seeding)

### Session 57 lessons (bank these)
- **Static finite directories are lookups, not scanners.** CSTA chapters, Catholic dioceses, charter CMOs, CTE centers — any data source that's bounded and changes less than weekly should be fetched once into `memory/*.json` and exposed as an enrichment helper, not scheduled as a daily Serper+Haiku scanner. Saved as `memory/feedback_static_directories_are_lookups.md`. Generalizes the BUG 4 diocesan lesson + retires F5 + codifies the pattern for future sources.
- **Haiku extractions in validation harnesses need `temperature=0.0`.** Without it the gate flip-flops between runs — same snapshot, different HIGH/MEDIUM splits, oracle labeling breaks. BUG 1 harness was non-deterministic until I pinned temperature. Saved as `memory/feedback_haiku_temperature_zero_for_gates.md`.
- **Empirical Serper probes BEFORE plan mode.** Both BUG 1 and BUG 2 plans had silent-bug rev-1s that only surfaced when I ran actual Serper queries against the proposed query templates. BUG 1 rev-1 used `"<State>"` quoted which killed yield to 0; rev-2 used unquoted state and yield jumped to 10+. BUG 2 rev-1 was snippet-only which would have yielded 0 because snippets are 200 chars; rev-2 added httpx + BeautifulSoup direct fetch and yield jumped to 14. Rule: don't write a plan on query design without running the queries first.
- **Browser User-Agent is OK for one-shot local scripts.** Session 56 rule was "don't change Scout's global UA because it touches every public district run." That rule still holds. But a per-script fetcher that runs manually (`scripts/fetch_csta_roster.py`) can use `Mozilla/5.0 …` safely because it's not in the production path. BUG 2 fetcher uses this and succeeds on all csteachers.org subdomains.
- **Eager-load lookup indexes at module import time.** `signal_processor.py`'s `_load_csta_roster()` runs at import via `_load_csta_roster()` call at module bottom. No lazy-init race. Scout imports are module-level, one import per process. Lazy patterns are overkill for read-only JSON lookups.
- **Pressure-test catches silent bugs that would have shipped.** BUG 1 rev-1 had `"<State> State Board of Education"` as a generic template — broken for TX (TEA), CA (CDE), OH (ODE). BUG 2 rev-1 had snippet-only extraction + wrong dedup key + unquoted-state bug. Both rev-1s would have shipped and produced near-zero yield with no obvious signal. The 7-step pressure test turned both into working rev-2s on the first pass. Rule: when Steven asks for the pressure test, actually HOLD THE FULL PLAN IN HEAD before reacting — surface all the silent bugs in one pass, rewrite from scratch with everything baked in.

### Session 56 lessons (bank these)
- **Every plan is a one-shot.** Don't write a plan expecting Steven to do refining rounds. Self-pressure-test hard; ship the best possible plan first time. Saved as `memory/feedback_plans_are_one_shot.md`. Steven explicitly rejected v1 of the BUG 4 plan that ended with "ready for your 7-step pressure test" — he considered that lazy framing that pushed rigor onto him.
- **Before writing any plan, verify the foundational assumption empirically.** For BUG 4, v1 and v2 assumed L6 direct scrape would contribute to diocesan yield. Ten minutes of `curl` + BeautifulSoup revealed that Archdiocese of Chicago runs on Liferay + React and BeautifulSoup sees zero text. v3 dropped `DIOCESAN_CENTRAL_PATHS` entirely and refocused the playbook on search-layer query tuning. Rule: walk the pipeline in your head end-to-end and ask "what has to be true for this to work?" then go verify each load-bearing assumption.
- **Serper snippets flow into `raw_pages` via `_add_raw_from_serper`.** For JS-rendered sites, search-index layers (L1/L2/L4/L11/L16/L17/L20) are where contact yield comes from. Don't waste time on L6 seed URLs for React/Liferay/Drupal SPAs. Saved as `memory/reference_serper_snippets_as_raw_pages.md`.
- **When activating a feature via district name lookup, canonicalize both sides.** `_canonical_diocesan_key` lowercases and strips "schools"/"catholic schools" suffix. Both map keys (at build time) and lookup input (at runtime) go through the same helper — so "Archdiocese of Chicago Schools", "archdiocese of chicago", and "Archdiocese of Chicago Catholic Schools" all resolve. Rule: never trust that users/bots will type the district name the way the seed has it stored.
- **Single source of truth helpers prevent filter leaks.** Commit C of BUG 4 collapsed 4 inline `target_host/target_hint` computations into a single `_target_match_params()` call. The diocesan override is in one place; non-diocesan behavior is preserved exactly. Post-commit grep gate (`grep 'self\._district_name_hint(self\.district_name)' | count == 1`) confirms no stale sites remain. Rule: when a matching rule needs a per-context override, refactor all call sites behind a single helper FIRST, then add the override.
- **L6 direct scrape is architecturally blind to modern school CMS platforms.** Liferay, Drupal SPA, WordPress-React, Next.js SPA — BeautifulSoup sees JS shell with zero text. 4 of 16 diocesan domains also WAF-block Scout's `ScoutBot/2.0` user agent outright (Boston, Pittsburgh, OKC, Galveston-Houston). Upgrading Scout's global UA is risky — it touches every public district run. Accept L6 as dead weight on diocesan and rely on Serper for yield.
- **Queue operation slash command naming is inconsistent.** `/prospect_private_networks` (not `/queue_private_school_networks`) is the actual command for `queue_private_school_networks()`. The command registry in `main.py` line ~3508 uses `prospect_` prefixes for seed-queueing functions. Session 56 wasted a command round-trip guessing. Reference the agent/main.py handler block before firing slash commands that aren't in the Scout reference.

### Session 55 lessons (bank these)
- **Filter at the earliest boundary that has the signal, not at the output.** BUG 5 plan v2 filtered after Claude extraction (wasted tokens). v3 filters at `raw_pages` boundary before Claude sees the pages. Saved as `memory/feedback_filter_upstream_not_downstream.md`. Walk the pipeline backwards in plan mode and find the earliest stage where the needed signal first becomes available.
- **Don't ask permission on verified capabilities.** Steven: "you dont need to ask to do that you should have just done it" (re: testing screencapture). Asking on safe reversible known-working actions burns latency. Saved as `memory/feedback_take_initiative_on_verified_capabilities.md`. Still ask on destructive ops, ambiguous decisions, or money-spending.
- **Shared helpers as single source of truth.** BUG 5 has 4 callers of the same matching logic (Stage 1, Stage 2, strengthened L10, audit script). One helper, four callers. DRY prevents the "4 places with subtly different rules" failure mode.
- **Known-bad oracle is necessary but not sufficient.** 2-row oracle passes trivially for almost any rule. Add a 20-row "must be kept" clean spot-check as a second gate. Both gates block the audit script from producing a report until they pass.
- **L15 additions bypass anything that runs in L9.** Any post-L9 validation must ALSO run on L15's `_merge_contacts` sites (two of them). The second L10 pass is a weaker gate than a Stage 2 call.
- **`sheets_writer._ensure_headers` was NOT the auto-migrating function I assumed from root CLAUDE.md.** Root CLAUDE.md's "`_ensure_tab` always overwrites" refers to a different function in `district_prospector.py`. Now fixed: `_ensure_headers` auto-migrates when current header is a prefix of expected.
- **Railway log API queries need DateTime scalar type** (not String). `startDate: DateTime` / `endDate: DateTime`. 5000-line limit per query — narrow the window if near the cap.
- **Scout bot research task can occasionally hang silently for 1 request then recover.** Session 55 second smoke test hung for 20+ min with zero progress logs, then a third attempt completed in 7 minutes. Possibly a 409 Conflict overlap during rolling deploy. If research seems stuck, wait 2-3 min and retry; don't assume a code bug first.

### Current status
- All prior phases + enhancements: ✅
- Signal Intelligence System: ✅ — **22 sources**. **40+ Telegram commands**. Session 52 added `/reprioritize_pending` (one-shot migration). F9 compliance scanner is now Signals-only pilot (not auto-queue). Daily 7:45 AM + weekly Monday + monthly 1st Monday schedule unchanged.
- Prospecting strategies: ✅ All Tier A + B + C strategies built AND priority-scoring is working end-to-end after Session 52 Commit 1. Seven strategies now scale with size kwargs (`intra_district`, `cs_funding_recipient`, `competitor_displacement`, `csta_partnership`, `charter_cmo`, `cte_center`, `private_school_network`, `compliance_gap`). Only #2 usage-based (blocked on CodeCombat data) remains unbuilt.
- Outreach sequences: ✅ — IDs 1995-2001 (C4 x4, License Request, Webinar x2). 3 send schedules.
- Email auto-drafter: ✅ — runs every 5 min during business hours, **thread-aware** (GAS `getThreadsBulk` batch fetch, STEVEN/PROSPECT attribution in prompt). Dedup via `threadHasDraft`. Manual triggers: `/draft_emails`, `/draft force`, `/draft [name]` (targeted, bypasses classification). Restart seeding notifies Telegram with `/draft force` hint.
- Sequence copy rules: ✅ — Comprehensive rules in memory. Seasonal calendar. Send schedules.

### Completed features (details in SCOUT_PLAN.md)
- **A3 Lead row coloring**, **B2 SF Leads/Contacts import**, **C1 Territory Master List**, **C3 Closed-Lost Winback**, **C4 Cold License Requests**, **C5 Proximity + ESA**, **SoCal CSV Filtering** — all verified and documented in SCOUT_PLAN.md.
- `lead_importer` is a flat module imported at top of main.py (NOT lazy). `clear_tab()` uses `values().clear()` + `updateSheetProperties` grid resize (NOT `deleteDimension`).
- "Leads from Research" = renamed research Leads tab. `TAB_LEADS` constant.
- Cross-check rules: school-level active accounts only block SAME school. District-level blocks whole district.

### Outreach.io API (key gotchas — full details in SCOUT_PLAN.md + memory)
- Steven's user ID: **11**. Write access for sequences/steps/templates/prospects only.
- **Interval is in SECONDS** (not minutes). 5 min=300, 4 days=345600, 6 days=518400.
- **`toRecipients` MUST be `[]` (empty).** Never `["{{toRecipient}}"]` — causes all emails to fail.
- Creation flow: create sequence → steps → templates → link → Steven activates in UI → THEN add prospects.
- Use `<br><br>` between paragraphs in bodyHtml, NOT `<p>` tags.
- Schedules: UI-only (no API scopes). Three standard: "Teacher Tue-Thu Multi-Window", "Admin Mon-Thurs Multi-Window", "Hot Lead Mon-Fri".
- C4 sequences: IDs 1995-1998. Schedule: "C4 Tue-Thu Morning" (ID 50). Steven's template: ID 43784.

### Email Reply Drafting (auto + manual)
**Auto-drafting (Railway):** `tools/email_drafter.py` polls unread inbox every 5 min during business hours (7 AM - 6 PM CST, weekdays). Classifies via Claude Haiku (DRAFT/FLAG/SKIP), drafts via Claude Sonnet with voice profile + playbook + **full thread history** (via `gas.get_threads_bulk`), creates threaded HTML drafts via GAS bridge. Notifies Steven in Telegram. Manual triggers: `/draft_emails`, `/draft force`, `/draft [name]` (targeted — bypasses classification).
**Claude Code workflow:** When Steven says "draft my emails" in Claude Code, load and follow `prompts/reply_draft.md`.
Voice rules in `memory/voice_profile.md`. Response patterns in `memory/response_playbook.md`.
Draft log in `memory/draft_log.md`. Known issue: Outreach browser extension strips draft body for contacts in Outreach.

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

**Always enter plan mode before building anything non-trivial.** New scanners, new strategies, new tools, schema changes, multi-file refactors — all require `EnterPlanMode` + Steven's sign-off BEFORE code gets written. Session 51 shipped 7 features without plan mode and 3 of them had BLOCKER-level bugs that Session 52 had to fix. Exception: typos, one-line config tweaks, documentation edits. When in doubt, plan. Rule established Session 52.

**Always push code changes from Claude Code via git — never tell Steven to use `/push_code` in Telegram.** Scout's `/push_code` dumps entire file contents into Telegram (4,096-char limit) causing truncation and confusion. Always `git add`, `git commit`, `git push` directly from the Claude Code terminal. This is a hard rule established Session 19.

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs are documented in `agent/CLAUDE.md` and `tools/CLAUDE.md`.

**Always produce complete replacement files.** Never give partial snippets or "find line X and replace." Steven uploads full files via GitHub web interface.

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**Top-level imports for flat tool modules.** `activity_tracker`, `csv_importer`, `daily_call_list`, `district_prospector`, `pipeline_tracker`, `lead_importer` are imported at the top of main.py like sheets_writer.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result → 400 on next API call.

**Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Both synchronous versions freeze the asyncio event loop.

**Synchronous code called from async context must use `run_in_executor`.** Wrap blocking I/O in `await loop.run_in_executor(None, fn, args...)`. Never call blocking functions directly from async methods.

**`handle_message()` and async tasks must call `get_gas_bridge()` locally — never reference `gas` as a free variable.** `handle_message()` assigns `gas = get_gas_bridge()` later in the function (line ~1687 for `/call_list`). Python treats `gas` as local throughout the entire function — so any earlier reference raises `UnboundLocalError`. Same applies to `_run_*_scan()` functions spawned via `asyncio.create_task()` from the scheduler — they don't inherit the outer `gas` local. ALWAYS call `get_gas_bridge()` into a local variable like `draft_gas` or `scan_gas` at the top of any new branch or scheduled function. Two latent bugs from this pattern shipped in Session 49.

**New scanners ship with kill switches.** Add an `ENABLE_X_SCAN = True` constant near the top of `tools/signal_processor.py` (next to `SERPER_API_KEY`). Scanner checks the flag at function entry and returns empty if disabled. One-line commit to disable in production without removing code. Examples: `ENABLE_FUNDING_SCAN`, `ENABLE_COMPETITOR_SCAN`.

**Multi-feature sessions ship one commit per feature.** Don't bundle features into one big commit at session end. Separate commits enable surgical `git revert` if a feature causes production issues. Session 49 shipped F3 → F1 → F4 → F2 as separate commits + small fix commits.

**Signal vs. Prospect routing for new lead-gen scanners.** HIGH confidence → auto-queue via `district_prospector.add_district()` as `pending`. MEDIUM/LOW → Signals tab only via `write_signals()`. Active customer match → `customer_intel` log only (don't sell, don't discard). Pattern established in F4 + F2 scanners (Session 49). All queue writes are `pending` — Steven manually approves via `/prospect_approve`. No auto-elevation logic.

**GAS `createDraft` always passes `skip_if_draft_exists=True`.** This prevents duplicate drafts on threads that already have one. GAS-side check via `threadHasDraft(threadId)` iterates `GmailApp.getDrafts()`. Returns `{success: false, already_drafted: true}` which `gas_bridge._call()` passes through (does NOT raise). Email drafter treats `already_drafted` as a soft-skip, not an error.

**`_calculate_priority()` strategies as of Session 52:** `upward` (600-999), `winback` (550-749), `proximity` (400-699), `esa_cluster` (450-599), `intra_district` (750-849), `cs_funding_recipient` (800-899), `competitor_displacement` (650-749), `csta_partnership` (620-719), `charter_cmo` (780-899 scaled by school_count), `cte_center` (760-879 scaled by sending_districts), `private_school_network` (740-839 scaled by schools), `compliance_gap` (850-939 scaled by est_enrollment — applies only on manual `/signal_act` promotion since F9 is Signals-only pilot), `homeschool_coop` (500-599), and falls through to `cold` (300-799 by enrollment) for anything unknown. Add new branches for new strategies — falling through to cold gives wrong sort order for warm leads. **After Session 52:** `add_district(**kwargs)` forwards `school_count`, `total_licenses`, `est_enrollment` positionally and the rest via kwargs — pass the size metadata or priority scoring collapses to tier base.

**`add_district(**kwargs)` and size metadata:** As of Session 52 Commit 1, `add_district()` accepts `**kwargs` and forwards them to `_calculate_priority`. Callers should pass `est_enrollment`, `school_count`, `sending_districts`, or `schools` depending on strategy — these both affect priority scoring and populate queue row columns 15-17 (`Est. Enrollment`, `School Count`, `Total Licenses`). If you add a new strategy and don't pass the right kwargs, it'll score at tier base and look broken. The existing `_calculate_priority` signature has `school_count` and `total_licenses` as named positionals; `add_district` pops them out of kwargs before forwarding to avoid collision. Use `functools.partial` when calling via `loop.run_in_executor(None, fn, *args)` — that API can't pass kwargs directly.

**`/signal_act` uses `_SIGNAL_TYPE_TO_STRATEGY` dict for strategy mapping.** Added Session 52 Commit 2 in `agent/main.py`. Currently only maps `"compliance" → "compliance_gap"`. Anything else defaults to `"trigger"` which falls through to the cold branch (same as the pre-Session-52 behavior for back-compat). Session 53+ follow-up: add `bond → bond_trigger`, `leadership → leadership_change`, `rfp → rfp_trigger`, etc. after those strategies are built. When you add a new signal-promoted strategy, you MUST also add its branch in `_calculate_priority` AND its entry in `_SIGNAL_TYPE_TO_STRATEGY`.

**F9 compliance_gap_scanner is Signals-only pilot mode.** Session 52 Commit 2 rewrote the queue path — scanner writes extracts to the Signals tab via `signal_processor.write_signals` with `signal_type="compliance"`, `source="compliance_scan"`, `source_detail="F9_pilot_{state}"`, and stable `message_id = f"compliance_{state}_{sha1(url+district)[:12]}"` for dedup across re-scans. Auto-queue mode is disabled until ≥60% validation rate is proven over 15+ extractions. Promotion happens via `/signal_act N` which uses the strategy mapping above. Per-state 24h rate limit enforced via module-level `_LAST_SCAN` dict (Commit 5) — override by waiting 24h or restarting Railway.

**`_extract_districts_from_pdf` returns `(items, error_msg_or_none)` tuple** (Session 52 Commit 2). Allows `scan_compliance_gaps` to distinguish "parse failed" from "no districts found in document" — both return empty lists in the first element but the second element is `None` vs an error string. The return dict now surfaces a `parse_errors` list for operator visibility.

**New territory_data helper: `lookup_district_enrollment(name, state) -> int`** (Session 52 Commit 1, refined in Commit 4). Matches on pre-computed `Name Key` column first, then falls back to re-normalizing `District Name`, then a token-subset pre-check (if target tokens are a strict subset of candidate tokens or vice versa), then `csv_importer.fuzzy_match_name` with threshold 0.7. Returns 0 on miss. The token-subset pre-check exists because `csv_importer.fuzzy_match_name` has a gap for 1-token-subset-of-multi-token cases (e.g., "carlinville" ⊂ "carlinville 1") — see `memory/feedback_fuzzy_match_limits.md`.

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

**CSV import default mode is MERGE (non-destructive).** `/import_clear` switches to clear-and-rewrite for next upload only. `/import_replace_state CA` replaces only that state's rows. `/dedup_accounts` uses Name Key + State composite key.

**`get_districts_with_schools()` state key is `"State"` (capital S).** Active Accounts use capital-S. `s.get("state")` returns empty — always use `s.get("State")`.

**CSV importer preserves ALL columns.** Known columns mapped via `_SF_COL_MAP`/`_OPP_COL_MAP`, unknown pass through. Pipeline uses REPLACE ALL (point-in-time snapshot). Always normalize names to sentence case preserving acronyms (ISD, HS, STEM). CSV uploads decode with utf-8-sig.

**Auto-detect CSV routing by headers.** Priority: pipeline > sf_leads > sf_contacts > accounts. Natural language description or caption overrides auto-detect. Slash commands override everything.

**Pipeline uses 3-tier stale alerts.** 🟠 14+ days, 🟡 30+ days, 🔴 45+ days. Empty Last Activity is NOT flagged.

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

**`proximity_engine.py` is a flat module imported at top of main.py.** Targeted + state sweep modes. `add nearby` queues from last results. ESA mapping via `esa [state]`. All direct dispatch. `_last_proximity_result` is in-memory only — lost on bot restart.

**`signal_processor.py` is a flat module imported at top of main.py.** 19 signal sources, 31 Telegram commands, all direct-dispatch. Daily 7:45 AM CST. Weekly Monday: leadership + RFP. Monthly 1st Monday: legislation + grants + budget. On-demand: algebra, cyber, roles, CSTA. BoardDocs/Ballotpedia/RSS wrapped in try/except (non-fatal). `_last_signal_batch` is in-memory — run `/signals` before `/signal_act` or `/signal_info`.

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

**`_on_prospect_research_complete` is the auto-pipeline callback.** Standard flow → strategy-aware sequence → Google Doc → mark complete. `sequence_builder` lazy imported.

**`/prospect_approve` checks Active Accounts before queuing.** Warns on existing district customers. `_pending_approve_force` + `_last_prospect_batch` are in-memory only — lost on restart.

**Two prospecting strategies — upward and cold.** Upward = school accounts, no district deal. Cold = no presence. 8 priority tiers (900+ to 300+). Small/medium above large in same tier.

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

## REFERENCE MATERIAL → docs/SCOUT_REFERENCE.md

The repo tree, full Railway env var table, the Claude tool registry (25 tools), and the complete Telegram shorthand command list (~80 commands) all live in **`docs/SCOUT_REFERENCE.md`**. Read it on demand — it's gitted, greppable, and not loaded into every session. CLAUDE.md was hitting the 40k char performance ceiling so this static reference material was extracted in Session 53.

Quick pointers:
- Module API details: `agent/CLAUDE.md` and `tools/CLAUDE.md`
- GAS deployment checklist: `gas/CLAUDE.md`
- Bug log + per-session changelog: `SCOUT_HISTORY.md`
- Active plan + completed feature notes: `SCOUT_PLAN.md`
