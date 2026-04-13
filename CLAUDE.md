# SCOUT — Claude Code Reference
*Last updated: 2026-04-13 — End of Session 59 (diocesan value extraction: sequence_builder diocesan branch shipped, 6 diocesan sequence docs regenerated clean, 1 contamination row deleted, intra_district 384-row audit produced retire-F1 recommendation)*

---

## CURRENT STATE — update this after each session

**What's working after Session 59:**
- **Sequence builder has a diocesan branch** (commit `042f146`). `agent/main.py:_on_prospect_research_complete` now has a `private_school_network` branch that detects diocesan targets via "archdiocese"/"diocese" token match, sets target_role to "Superintendent of Catholic Schools", and inlines the full tone rules (no dollar figures, no peer names, CS/safe-AI framing, 3-CTA pattern, banned-phrase list, structure constraints). Non-diocesan private_school_network rows get a network-level branch. Additive change — no regression risk on existing strategies.
- **6 diocesan sequence docs regenerated and linked in the queue.** Session 58 Session 56 + Session 58 shipped 7 draft docs all built through the broken cold fallback (52-73 em dashes each, AI leading in subject lines, banned phrases, zero match on diocesan framing elements). Session 59 Section 5 regenerated Philadelphia, Cincinnati, Detroit, Cleveland, Boston, Chicago through the new branch — 5 clean, 1 (Cincinnati) with minor Step 1 length nit. Prospecting Queue `Sequence Doc URL` column updated. LA abandoned (only 2 leads from 1 parochial school). Review details: `docs/SESSION_59_DIOCESAN_REVIEW.md`.
- **Public-district email blocklist shipped** (`memory/public_district_email_blocklist.json`). 10 exact domains + 8 regex patterns + per-diocese exclusions for all 16 Catholic dioceses + whitelist of 23 known-good archdiocesan/parochial domains from Session 58 research. Used in Section 3 cleanup, available as runtime contamination guard for future diocesan approvals.
- **1 cross-contamination row deleted.** `nicole.cummings@detroitk12.org` was written into Archdiocese of Detroit rows (Detroit Public Schools leak). Detroit row count 9 → 8, total diocesan rows 71 → 70. BUG 5 shared-city gap documented in `memory/project_bug5_shared_city_gap.md`.
- **intra_district backlog decision made.** 100% of all 384 pending rows have ≥1 active contact at parent district — F1 is structurally redundant (finds sibling schools inside already-active districts). **Recommendation: Option C = retire F1 + bulk-skip all 384.** Full audit in `docs/SESSION_59_INTRA_DISTRICT_AUDIT.md`. Awaiting Steven's confirm/override.
- **Prospecting Queue backup tab deleted.** Was `Prospecting Queue BACKUP 2026-04-10 0010` (38,837 rows). Live queue intact at 38,932 rows.
- **Session 58 carryover still stands:** CSTA roster at 77/41 matchable, CSTA enrichment wired to all 6 scanners (F1/F2/F4/F6/F7/F8), F4/F6/F7 kill switches still `True`, Telethon bridge + Railway log API functional.
- **Diocesan research yield is dramatically better than CLAUDE.md Session 58 predicted.** Session 58 expected "central-office NAMES without verified emails"; Session 59 audit found **72 verified emails across 6 archdioceses (67% rate)**, with Philadelphia 87% and Cincinnati 88% delivering gold central-office Superintendent contacts. **Apollo/RocketReach decision deferred** — the existing L16/L17/L20 research stack is doing the job.

**What's still in-progress / unresolved (carryover for Session 60):**
- **Steven's decision owed on intra_district 384 rows.** Session 59 audit recommends Option C (retire F1 + bulk-skip). See `docs/SESSION_59_INTRA_DISTRICT_AUDIT.md`. Execute by running a one-off bulk-skip script OR `/prospect_skip all` via Telethon pagination. Also consider adding `ENABLE_F1_INTRA_DISTRICT = False` kill switch near top of `tools/district_prospector.py` to stop the backlog from rebuilding.
- **Steven's review owed on 6 regenerated diocesan sequence docs.** URLs in `docs/SESSION_59_DIOCESAN_REVIEW.md` — Philadelphia + Cincinnati are the highest-value (gold central-office contacts). Each is ~5 steps, 2-3 minutes to read. If approved, manual Outreach setup (no API-side creation for diocesan sequences). If iteration needed, I can regen with specific edit notes in ~30 sec + ~$0.05 per regen.
- **Archdiocese of LA central office still not cracked.** Research yielded only 2 leads from 1 parochial high school. Regeneration abandoned. Session 60 candidate: hand-seed research with `lacatholicschools.org` and rerun.
- **BUG 5 shared-city contamination gap persists as a code-level issue.** Runtime blocklist (`memory/public_district_email_blocklist.json`) is the Session 59 patch. A proper fix in `tools/research_engine.py:_target_match_params` needs a separate plan-mode session. Tracked in `memory/project_bug5_shared_city_gap.md`.
- **9 pending dioceses unchanged this session** (Pittsburgh, OKC, Tulsa, Nashville, Memphis, Fort Worth, Galveston-Houston, Lincoln, Omaha). Per Session 59 plan, bounded to 3-diocese stretch approval if time allowed. Default: pick up in Session 60 with per-diocese blocklist-gated approval.
- **Session 58 backlog still pending** (minus diocesan updates + the 1 deleted contamination row): cs_funding_recipient 7, charter_cmo 15, cte_center 34, competitor_displacement 24, trigger 12, proximity 5, csta_partnership 1, other private_school_network 7 = 105 rows still awaiting approval across non-intra_district strategies. `cold_license_request` 1,245 and `winback` 247 remain out of scope.
- **F9 compliance scanner query redesign** — handler fine, scanner still surfaces wrong PDFs. Future BUG-1-shape plan-mode session.
- **IN/OK/TN CSTA hand-curation** — +15 matchable entries available via manual Google/LinkedIn work. Lower priority than diocesan work.
- **`.DS_Store`** still in git status — macOS noise, safe to ignore.

**Session 58 carryover still in effect** (details in SCOUT_HISTORY.md): CSTA roster 77/41, CSTA enrichment wired to all 6 scanners, `build_csta_enrichment` helper pattern in `tools/signal_processor.py`, F4/F6/F7 kill switches, BUG 4 diocesan playbook, BUG 5 two-stage filter, F9 handler, Telethon bridge, Railway log API, `/prospect_approve all` + `/prospect_skip all` working.

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 59:** Diocesan value extraction. Discovered sequence_builder had no `private_school_network` branch — every diocesan approval since Session 56 produced broken cold-framed drafts (50-73 em dashes, AI in subject lines, banned phrases, 0/9 tone match). Shipped diocesan branch (commit `042f146`), regenerated 6 of 7 existing docs clean (5 fully pass, 1 minor Step 1 length nit), abandoned LA. Confirmed diocesan research yield is actually excellent — 72 verified emails / 107 found (67%), Philadelphia 87% / Cincinnati 88% central-office gold. Shipped `public_district_email_blocklist.json` (16 dioceses + 10 domains + 8 patterns). Cleaned 1 Detroit contamination row (detroitk12.org leak). intra_district audit: 100% of 384 rows redundant against Active Accounts → recommend retire F1. Deleted backup tab. 2 commits. Plan: `~/.claude/plans/lexical-swinging-pelican.md` (rewritten v2 after pressure test).
- **Session 58:** Priorities 1–4 comprehensive knockdown. Stage 6/7/8 (F6/F7/F9/F1), diocesan drip started (6 of 16 approved), CSTA enrichment wired to F4/F6/F7/F8 via helper, CSTA roster 39/14 → 77/41, `/prospect_approve all` bug fixed, CLAUDE.md doc trim. 7 commits (`185a3f2`, `c947681`, `e52ce25`, `3ea1be1`, `69a3e9c`, `529a919`, end-of-session). Plans: `~/.claude/plans/mellow-bouncing-lemur.md` (CLAUDE.md trim).
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits. Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits.
- **Session 53:** Fire drill audit. F2 max_tokens fix. 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.

### What still needs to be done (Session 60 — execute decisions + optional sprint)

1. **STEVEN DECISION — intra_district 384 rows.** Confirm Option C from `docs/SESSION_59_INTRA_DISTRICT_AUDIT.md` (retire F1, bulk-skip) or override. If confirmed: run bulk-skip on all 384 + add kill switch to `tools/district_prospector.py`.
2. **STEVEN REVIEW — 6 regenerated diocesan sequence docs.** URLs in `docs/SESSION_59_DIOCESAN_REVIEW.md`. Philadelphia + Cincinnati are the highest-leverage — 20+ verified central-office contacts each, ready to ship to Outreach manually. Boston/Cleveland are school-level (parochial principals) usable for school-by-school campaigns. Detroit + Chicago are clean archdiocesan central targets.
3. **APPROVE remaining 9 pending dioceses** with per-diocese blocklist-gated cleanup. Pittsburgh/OKC/Omaha first (Steven's strongest territories). 7 of 9 are BUG 5 shared-city risks — run `memory/public_district_email_blocklist.json` cleanup after each research job completes.
4. **APPROVE Session 58 non-diocesan backlog:** 7 cs_funding + 15 charter_cmo + 34 cte_center + 7 other private_school_network = 63 rows across 4 strategies. Smallest-to-largest order (cs_funding first).
5. **OPTIONAL — BUG 5 code fix** (`tools/research_engine.py:_target_match_params` shared-city gap). Plan-mode session, test harness, same shape as BUG 1 Session 57.
6. **OPTIONAL — hand-curate IN/OK/TN CSTA board members.** +15 matchable entries. ~15-30 min manual work.
7. **OPTIONAL — F9 compliance scanner query redesign.** Separate plan-mode session. Empirical Serper PDF probes first, then query iteration. Exit criterion ≥60% HIGH validation rate.
8. **OPTIONAL — LA archdiocese research restart.** Hand-seed with `lacatholicschools.org` and rerun; regenerate sequence if yield improves.
9. **DEFERRED — cold_license_request 1,245 + winback 247 stale March backlogs.** Dedicated plan-mode session to decide purge vs cherry-pick vs retire.

### Session 59 lessons (most recent, still load-bearing)
- **Empirical probing before plan mode catches frame errors, not just detail errors.** Session 59's v1 plan focused on backlog drain. 15 minutes of pre-plan probing (pulling Research Log row counts, checking `_on_prospect_research_complete` elif chain, counting queue rows, verifying `ResearchQueue` singleton behavior) revealed that the real bottleneck wasn't queue or cost but (a) the sequence builder had no diocesan branch, and (b) Steven's review bandwidth was saturated, not his queue capacity. Completely reframed the session. The pressure-test pass caught what the first plan missed by holding the full pipeline in head instead of reacting to CLAUDE.md's stated priorities.
- **Stale-by-design backlogs are always worth auditing before approving.** The 384 intra_district rows had been sitting pending since March. 100% of them are redundant against Active Accounts. F1's entire premise (find sibling schools inside active-district customers) is structurally redundant-by-design: every parent is already an Active Account, so research on the sibling mostly rediscovers the parent's known contacts. Audit first, approve second.
- **Google Docs/Drive APIs are often disabled per service-account project, but public `/export?format=txt` URL works without auth.** When the service account couldn't read the Sheets project's Docs/Drive APIs (both disabled), a direct `httpx.get('https://docs.google.com/document/d/<id>/export?format=txt', follow_redirects=True)` pulled clean plain text from any doc accessible to anyone with the link. Useful fallback when auth is stuck.
- **The `Sequence Doc URL` column in Prospecting Queue is col 14 (O in A1 notation).** Not col 15. Off-by-one noted.
- **Inline tone rules in `extra_context` beat externalized prompt files for iteration velocity.** When the tone rules live in one place in `agent/main.py`, iteration after a Steven review is one edit. If split across multiple prompt files, iteration requires cross-file coordination. Ship inline unless extracting becomes necessary.

### Session 58 lessons (still load-bearing)
- **Haiku saturates on large mixed-topic corpora.** A 610K-char corpus of 101 URLs silently dropped state chapter content; a focused 22K-char corpus extracted the same entries perfectly. Split by topic bucket + run per-bucket extraction. Saved as `memory/feedback_haiku_saturation_large_corpus.md`.
- **Haiku is nondeterministic across runs even at `temperature=0.0`.** Three consecutive identical calls produced different subsets. Data scripts that persist extractions must merge-with-previous, never overwrite. Saved as `memory/feedback_haiku_nondeterminism_merge_previous.md`.
- **Explicit state chapter URLs must be DNS-verified before seeding.** `california.csteachers.org`, `pennsylvania.csteachers.org`, `texas.csteachers.org` all DNS-fail — those states use regional chapter subdomains only (goldengate, pittsburgh, dallasfortworth). `httpx.head()` probe is the fastest check.
- **Scout's `/prospect_approve all` was always broken despite its own output telling users to use it.** Latent bug since Session 49 — handlers parsed `int(x)` on `"all"` and fell through to `Usage:` error. Lesson: when a command help message promises a syntax, actually test that syntax.
- **`build_csta_enrichment(district, state, base_notes) -> (enriched_notes, priority_bonus)`** lives in `tools/signal_processor.py`. F4 uses it in-file; F6/F7/F8 use lazy imports to avoid circulars. F1/F2 kept inline (predate helper). If you add a 3rd non-helper call site, refactor everything to use the helper (Rule of Three).

### Session 57 lessons (still load-bearing, full prose in `docs/SCOUT_RULES.md` Appendix A)
- Static finite directories are **lookups, not scanners** (CSTA, dioceses, CTE, charters → `memory/*.json` + enrichment helper, not daily scan).
- Haiku extractions in validation harnesses need `temperature=0.0` or the gate flip-flops between runs.
- **Empirical Serper/httpx probes BEFORE plan mode** — both BUG 1 and BUG 2 had silent rev-1s that only surfaced via live probing. Session 58 Priority 4 reinforced this same lesson (CSTA fetcher saturation found only via focused corpus probe).
- Browser User-Agent is OK for one-shot local scripts (not Scout's global UA).
- **Eager-load lookup indexes at module import time** — lazy patterns are overkill for read-only JSON.
- Pressure-test only catches silent bugs if you HOLD THE FULL PLAN IN HEAD before reacting.

---

## CRITICAL RULES (top 15 — full rule set in `docs/SCOUT_RULES.md`)

1. **Always enter plan mode** before non-trivial builds. New scanners, strategies, schema changes, multi-file refactors — all require `EnterPlanMode` + Steven's sign-off. Session 51 shipped 7 features without plan mode; 3 had BLOCKER bugs. Established Session 52.
2. **Always push code from Claude Code via git**, never `/push_code` in Telegram (4096 char truncation). `git add`, `git commit`, `git push` directly from Claude Code terminal. Hard rule since Session 19.
3. **Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs in `agent/CLAUDE.md` + `tools/CLAUDE.md`.
4. **Every plan is one-shot; pressure-test hard BEFORE presenting.** Don't write a plan expecting refinement rounds. Steven rejected plans that pushed rigor onto him. See `memory/feedback_plans_are_one_shot.md`.
5. **Verify foundational assumptions empirically BEFORE writing plans.** Walk the pipeline end-to-end and probe the load-bearing assumptions (Serper queries, httpx fetches, grep verification). BUG 1 + BUG 2 both had silent rev-1s that only surfaced via live probing.
6. **New scanners ship with kill switches.** `ENABLE_X_SCAN = True` constant near top of `tools/signal_processor.py`. Scanner short-circuits at function entry when disabled. One-line disable in production without removing code.
7. **Multi-feature sessions → one commit per feature.** Don't bundle features into one big commit at session end. Separate commits enable surgical `git revert`.
8. **Signal vs Prospect routing for new lead-gen scanners.** HIGH confidence → auto-queue via `district_prospector.add_district()` as `pending`. MEDIUM/LOW → Signals tab only via `write_signals()`. Active customer match → `customer_intel` log only (don't sell, don't discard). All queue writes are `pending` — Steven manually approves.
9. **`handle_message()` and async tasks must call `get_gas_bridge()` locally** — never reference `gas` as a free variable. Python treats `gas` as local throughout the function (it's assigned later for `/call_list`), so any earlier reference raises `UnboundLocalError`. Same for `_run_*_scan()` tasks spawned via `asyncio.create_task()`. Two latent bugs shipped in Session 49 from this pattern.
10. **Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Synchronous versions freeze the event loop. Synchronous blocking code called from async context must use `run_in_executor`.
11. **`global` declarations go at the TOP of `handle_message()`**, not in elif blocks. Python SyntaxError if `global` appears after first use of the variable. One line at top: `global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _pending_csv_intent, _last_proximity_result`.
12. **`tool_result` always follows `tool_use`.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing `tool_result` → 400 on next API call.
13. **Explicit slash commands bypass Claude and call `execute_tool()` directly.** `/brief`, `/call`, `/recent_calls`, `/progress`, `/sync_activities`, `/call_list`, `/pipeline`, `/pipeline_import`, `/import_*`, `/enrich_leads`, all `/prospect_*`. Direct dispatch is the only reliable pattern — when conversation history is long, Claude responds with descriptive text instead of calling tools.
14. **NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement. **ALL sequences are drafts** — always Google Doc + Telegram link for Steven's approval. Never auto-finalize.
15. **Never design workflows requiring large-text paste through Telegram.** 4,096 char limit. Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

> **Full rule set** (GAS bridge, CSV import, research engine, signal processor internals, priority scoring tables, Outreach API gotchas, data model invariants, deployment ops, Session 55/56/57 post-mortems): **`docs/SCOUT_RULES.md`** — read by section or grep by keyword.

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

## REFERENCE MATERIAL

CLAUDE.md stays lean. On-demand reference lives in peer files:

- **`docs/SCOUT_RULES.md`** — full rule set (GAS bridge, CSV import, research engine, signal processor, priority scoring tables, Outreach API, data model invariants, ops, Session 55–57 post-mortems). Read by section or grep by keyword.
- **`docs/SCOUT_REFERENCE.md`** — repo tree, full Railway env var table, Claude tool registry (25 tools), Telegram shorthand command list (~80 commands), session-workflow `scout` wrapper notes.
- **`SCOUT_PLAN.md`** — active plan + completed feature notes (A3 / B2 / C1 / C3 / C4 / C5 / Email Drafter / Signal System / etc.)
- **`SCOUT_HISTORY.md`** — bug log + per-session changelog
- **`agent/CLAUDE.md`** + **`tools/CLAUDE.md`** — module-scoped API signatures
- **`gas/CLAUDE.md`** — GAS deployment checklist
- **`memory/*.md`** — behavioral feedback, auto-loaded at session start

CLAUDE.md was crossing the 40K char performance ceiling — Session 53 extracted `docs/SCOUT_REFERENCE.md` and Session 58 extracted `docs/SCOUT_RULES.md` + retired duplicated sections that already lived in `SCOUT_PLAN.md` and `memory/*.md`.
