# SCOUT — Claude Code Reference
*Last updated: 2026-04-09 — End of Session 53 (Fire Drill Audit)*

---

## CURRENT STATE — update this after each session

**Session 53 (FIRE DRILL AUDIT): Started as Session 52 Stage 4-8 execution. Ended as a discovery session that uncovered 5 separate silent-failure bugs across the scanner + research pipeline. Only 1 real fix shipped (F2 max_tokens cap). Session 54 needs to be a dedicated fix sprint before any more scanning.**

**What Session 53 actually accomplished:**
- **Shipped F2 max_tokens fix (commit `7c345a07`):** Bumped `max_tokens` 3000→8000 in `scan_competitor_displacement` + hardened the codefence parser against IndexError on truncated output. Proven via local IL diagnostic (CodeHS one-competitor replay found 15 HIGH board_adoption signals incl. Naperville 203 IL). Telegram output went from "0 raw extracted" to "17 raw, 12 signals, 8 auto-queued" on rerun. **However see BUG 3 below — the 8 auto-queued rows have their own problem.**
- **Trimmed CLAUDE.md from 45.4k to 33.3k chars** to clear the 40k performance ceiling. Extracted repo tree + env var table + command list + Claude tool registry to `docs/SCOUT_REFERENCE.md` (gitted, greppable, not loaded per-session).
- **Sent the Tulsa PS Gmail draft for Robert F. Burton** — reworked the body in claude.ai, rewrote via GAS bridge (first HTML attempt had rendered `<br>`/`&#39;` literally, second shell-escaped attempt produced literal `"""` in body, third attempt via standalone Python file was clean). **Scheduled to send Tuesday 8:05 AM.** Old broken drafts manually trashed.
- **Banked 2 real warm leads in canonical-layout queue rows:** Pittsburgh Public Schools (PA, csta_partnership, priority 621 via Teresa Nicholas CSTA K-12 Board member) and Archdiocese of Chicago Schools (IL, private_school_network, priority 839 from F8 seed). These two rows are verified canonical via direct sheet read.
- **5 separate project memories created** documenting the silent-failure bugs. Index entries in `memory/MEMORY.md`.

**The 5 bugs discovered (all parked for Session 54 fix sprint):**

1. **BUG 1 — F4 funding scanner: wrong queries, not truncation** (`project_f4_funding_scanner_broken.md`). Pre-existing since Session 49. Serper pulls 456 articles across 13 states; Claude extracts 0. Local IL diagnostic proved the root cause: queries like `"CS grant awarded school district Illinois"` pull higher-ed, student scholarships, teacher awards, program descriptions — NOT K-12 LEA recipient announcements. Claude correctly extracts nothing from noise. Fix requires query redesign with site filters targeting `*.k12.*.us` domains + state DOE subdomains, NOT prompt tuning.

2. **BUG 2 — F5 CSTA scanner: multiple issues + strategic question** (`project_f5_csta_scanner_low_yield.md`). 167 articles → 3 extractions → 1 auto-queued (Pittsburgh PS is the real one). 1.8% yield. Issues: queries target wrong corpus (chapter homepages / conference promos instead of `csteachers.org` subdomains + LinkedIn rosters), 12K input truncation throws away 76% of articles, prompt lets Claude write chapter-name as district fallback (Tamar McPherson got district="CSTA PA chapter"), `max_tokens=2000` is smaller than F2's old 3000. **Strategic question:** is F5 worth keeping as a standalone scanner, or redesigned as a contact-enrichment layer on top of F2 hits?

3. **BUG 3 — F2 writes rows in scrambled column layout (HIGHEST PRIORITY MYSTERY)** (`project_f2_column_layout_corruption.md`). The F2 max_tokens fix unblocked extraction, but the 8 rows auto-queued tonight are at WRONG column positions. Lackland ISD has `competitor_displacement` at col 3 (should be col 9), priority 654 at col 4 (should be col 12), notes at col 7 (should be col 20). Status column is EMPTY, which is why `/prospect_all` doesn't see them. **SAME `add_district` call from F5 and F8 produced CANONICAL layout for Pittsburgh PS and Archdiocese in the same session window.** Local sentinel-row test via `dp.add_district(...)` also produced canonical layout. Git archaeology found NO version of `add_district` that has ever written rows with strategy at col 3. **Also discovered 1912 pre-existing scrambled rows in the queue** (1463 with status="school", 449 with status="district") — this corruption has been happening for weeks. Some secondary writer or race condition is bypassing the canonical writer and we don't know what yet. Tonight's 8 F2 rows contain real valuable data (Lackland TX, Mansfield TX, Naperville 203 IL, etc.) — they're not lost, they're unreachable until the repair script runs.

4. **BUG 4 — F8 research playbook mismatch for diocesan networks** (`project_f8_diocesan_research_playbook.md`). Archdiocese of Chicago smoke test FAILED all 3 success gates. Research engine's L1-L8 all returned 0 (couldn't discover `archchicago.org` via domain discovery). Fell through to L16 Exa broad search, produced 30 contacts, only 1 was a real Archdiocese hit (Allen in Instructional Technology, from a 2017 PDF). The 20-layer engine has no path for multi-school central-office networks. **Do NOT unblock the other 23 networks in the F8 seed** until a dedicated diocesan playbook is built.

5. **BUG 5 — Research pipeline cross-contaminates leads across districts** (`project_research_cross_contamination.md`). Discovered as a side effect of BUG 4. Two of the three "verified" email contacts for the Archdiocese research were actually employees of unrelated public districts: Michelle Erickson at ROWVA CUSD 208 and Frank LaMantia at Community HSD 218. Both written to "Leads from Research" with `District Name = "Archdiocese of Chicago Schools"` but `Account = "ROWVA CUSD 208"` etc. **This is NOT F8-specific — the same pattern likely affects the other 19 completed research jobs in the Research Log tab.** Needs an audit + a post-extraction domain-matching validation layer. Until fixed, always cross-check Email vs Account columns in any manual review of research output.

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 53:** Fire drill audit. F2 max_tokens fix shipped (commit `7c345a07`). 5 silent-failure bugs discovered. CLAUDE.md trim + `docs/SCOUT_REFERENCE.md`. Tulsa PS draft scheduled. Stages 6-8 of Session 52 carryover NOT run — stopped at Stage 5 failure. No formal plan file.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes (priority scaling, F9 Signals-only, /signal_act strategy mapping). 6 commits. Plan: `/Users/stevenadkins/.claude/plans/dreamy-floating-avalanche.md`
- **Session 51:** Tier B+C Lead Gen (F5/F6/F7/F8/F9/F10 shipped), F4+F2 URL bug fix, F2 complete rewrite.
- **Session 50:** Email drafter fixes: thread-aware drafting, restart seeding notice, `/draft [name]` targeted command.
- **Session 49:** Email auto-drafter, Lead Gen Tier A (F1-F4).
- **Session 48:** Email Reply Drafting system — Gmail MCP threaded drafts in Steven's voice.

### What still needs to be done (Session 54 — Fix Sprint)
**Session 54 is a FIX SPRINT. No new scanners, no new strategies, no new features. Fix the 5 discovered bugs in priority order.**

1. **PRIORITY 0 — Enter plan mode.** Session 53 was a discovery session; Session 54 needs a real plan before touching code. Sketch the dependency graph: BUG 3 (column layout) blocks reliable use of any scanner that calls `add_district`, so it's probably first. BUG 5 (research cross-contamination) blocks trust in any research output. BUGs 1/2/4 come after.
2. **PRIORITY 1 — BUG 3: Column layout corruption.** Audit every writer to `TAB_PROSPECT_QUEUE`. Check `signal_processor.py` vs `charter_prospector.py` vs `cte_prospector.py` vs `proximity_engine.add_proximity_prospects` (constructs rows manually) vs any auto-migration hooks. Write a sheet-state diagnostic that fingerprints every row by its column layout pattern. Write a one-shot repair script that fixes ALL scrambled rows — the 8 F2 rows from tonight AND the 1912 pre-existing status=school/district rows. Validate on local diff before running.
3. **PRIORITY 2 — BUG 5: Research cross-contamination.** Audit script that iterates "Leads from Research" and flags any row where email domain doesn't match the canonical site of its `District Name`. Report on scope. Then add a post-extraction validation layer in `research_engine.py` between L9 Claude-extract and L10 dedup-score that drops or re-attributes contacts whose email domain doesn't match the research target.
4. **PRIORITY 3 — BUG 4: F8 diocesan research playbook.** Build a dedicated diocesan central-office research path — either a new strategy branch or a preprocessing layer. Known diocesan domain patterns to try before L4 (`archchicago.org`, `archdiocese-of-X.org`), priority titles (Superintendent of Schools, Director of Schools, Director of Educational Technology), central directory paths (`/schools/leadership`, `/offices/catholic-schools`). Lower the Stage 5 success threshold to 3-5 high-confidence contacts.
5. **PRIORITY 4 — BUG 1: F4 query redesign.** Not a prompt fix. Queries need to target `*.k12.*.us` domains, state DOE subdomains, known state-program names. Build a local diagnostic harness (same pattern as tonight's F2 diag) that can replay Serper results without redeploying.
6. **PRIORITY 5 — BUG 2: F5 strategic decision.** ANSWER THE STRATEGIC QUESTION FIRST before any code fix: standalone scanner or contact-enrichment layer on top of F2? If standalone, redesign queries + prompt + truncation. If enrichment, refactor to a different entry point.
7. **PRIORITY 6 — Session 52 carryover Stages 6-8.** Once infrastructure is proven via audits, run Stage 6 (charter CMOs + CTE centers), Stage 7 (F9 compliance CA pilot — Signals-only), Stage 8 (F1 backlog drip).
8. **End-of-sprint review:** Pittsburgh PS and Archdiocese are already in the queue as canonical rows ready for manual review. Archdiocese research is complete (Cold Prospecting sequence doc built — note the sequence builder fell back to "cold" because it has no `private_school_network` branch; another minor follow-up).

### Session 53 lessons (bank these into future sessions)
- **Railway rolling deploys can cause TEMPORAL inconsistency between scanners in the same session.** F2 ran at 00:51 UTC, F5 at 01:14 UTC, same `add_district` call, different row layouts. The build cache warning in CLAUDE.md has a new dimension: two scanners in the same hour may hit different container versions.
- **Spot-check EVERY scanner output via direct sheet read, not Telegram message.** Telegram reported "F2 auto-queued 8" which sounded like a win. Direct sheet read showed 8 rows at wrong column positions, unreachable via `/prospect_all`. "Spot-check" from Session 54 onward means "read the actual sheet row via service account" not "trust the Telegram ack."
- **"Not a regression" is not the same as "not a bug".** F4 has been returning 0 since Session 49, nobody noticed. BUG 3 has been happening for weeks via the 1912 pre-existing scrambled rows. The operator-facing output looked indistinguishable from a quiet news week. Break the habituation by periodically direct-reading sheet state, not just watching Telegram.
- **Kill switches need to be used.** All 5 discovered bugs involve scanners with kill switches (`ENABLE_FUNDING_SCAN`, `ENABLE_COMPETITOR_SCAN`, `ENABLE_CSTA_SCAN`, `ENABLE_PRIVATE_SCHOOL_DISCOVERY`) currently all `True`. Session 54 may want to flip F4 + F5 to `False` until fixes land. F2 stays enabled because logic IS good (only BUG 3 writer issue). F8/F9 stay enabled (F8 seed-only, F9 Signals-only pilot).

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
