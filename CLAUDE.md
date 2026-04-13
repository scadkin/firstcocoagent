# SCOUT — Claude Code Reference
*Last updated: 2026-04-13 — End of Session 59 (diocesan value extraction + tool hardening: 6 diocesan sequences live in Outreach with correct state, `validate_sequence_inputs` + `verify_sequence` helpers shipped, Steven's 5 schedule IDs fully mapped, 3 process rules + 4 preflight checklists added)*

---

## CURRENT STATE — update this after each session

**What's live after Session 59:**

- **6 diocesan sequences in Outreach**, all verified clean via `verify_sequence`:
  - 2008 Archdiocese of Philadelphia Schools
  - 2009 Archdiocese of Cincinnati Schools
  - 2010 Archdiocese of Detroit Schools
  - 2011 Diocese of Cleveland Schools
  - 2012 Archdiocese of Boston Catholic Schools
  - 2013 Archdiocese of Chicago Schools

  All sequences: `owner=11` (Steven), `schedule=52` (Admin Mon-Thurs Multi-Window), 5 steps with graduated cadence (5 min / 5d / 6d / 7d / 8d — total ~26 day timeline), clean descriptions with zero automation language, meeting link (`https://hello.codecombat.com/c/steven/t/130`) hyperlinked in required steps, `codecombat.com/schools` hyperlinked in ≥2 steps per sequence, zero em dashes, zero banned phrases in any body. Ready for Steven to activate in Outreach UI.

- **Tool hardening** (`tools/outreach_client.py`, commit `1f22991`):
  - `validate_sequence_inputs(...)` — standalone pre-write validator, 12 checks, zero API calls, unit-testable
  - `verify_sequence(seq_id, expected=...)` — standalone post-write / audit fetch + validation with network error handling
  - `create_sequence` refactored to auto-call both (input validation blocks writes; post-write verify catches drift)
  - Schedule allowlist via `OUTREACH_ALLOWED_SCHEDULE_IDS` env var → default `{1, 48, 50, 52, 53}`
  - Banned-phrase body scan (16 phrases + em/en dash detection)
  - Required `codecombat.com/schools` in ≥2 step bodies (opt-in via `require_cc_schools_link`, default True)
  - Meeting link (if provided) required in ≥1 step body
  - Repetition policy: `one pager` / `one-pager` max 1x across all bodies
  - Min step interval sanity check: default 432000s (5 days cold), override for hot-lead/license-request flows
  - `verify_after_create=True` default, set False for bulk creation to avoid rate limiting
  - **Live-tested:** all 6 diocesan sequences verified. Philadelphia + Cincinnati initially failed on "15 minutes" in step 3 bodies (validator caught real violations rounds 1-3 had missed); PATCHed templates 43923 and 43928 in place; re-verified clean.
  - **Unit tests:** `scripts/test_outreach_validator.py` — 14 cases, all pass in <1s, zero API calls.

- **Steven's 5 delivery schedule IDs confirmed** (stored in `memory/feedback_outreach_schedule_id_map.md`):
  - `1` = Hot Lead Mon-Fri (confirmed via AI Webinar seq)
  - `48` = SA Workdays (confirmed via ACTE '25 Seq)
  - `50` = C4 Tue-Thu Morning (confirmed via C4 License Re-Engage cluster)
  - `52` = Admin Mon-Thurs Multi-Window (confirmed after Steven attached it to Chicago seq)
  - `53` = Teacher Tue-Thu Multi-Window (confirmed via FETC 2025 seq)

- **3 new process rules** appended to `docs/SCOUT_RULES.md` Section 1:
  - Write the audit question in plain English BEFORE running code
  - Never cite cost/time/count/percentage numbers without labeling provenance (`measurement / sample / extrapolation / estimate / unknown`)
  - Never present a guess as a fact

- **4 new preflight checklists** added to this file's Preflight section below — Outreach work, Sequence content, Sheet audit, Cost/time estimate. Must be loaded at the start of any task matching those categories.

- **11 memory files banked** in `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/`:
  - `feedback_category_error_audit_the_question.md` — the F1 category error post-mortem
  - `feedback_never_cite_made_up_numbers.md` — fabricated $200-800 / 30hr post-mortem
  - `feedback_verify_units_at_layer_boundaries.md` — the 4 "I should have"s from the interval bug
  - `feedback_outreach_interval_is_seconds.md` — interval unit bug
  - `feedback_outreach_no_automation_language.md` — auto-generated description post-mortem
  - `feedback_outreach_delivery_schedule_required.md` — schedule always required
  - `feedback_outreach_schedule_id_map.md` — all 5 schedules mapped
  - `feedback_outreach_sequence_owner_required.md` — Session 59 round 2 owner fix
  - `feedback_never_manual_outreach_upload.md` — Scout automates, never tells Steven to copy/paste
  - `user_meeting_link_pattern.md` — hello.codecombat.com link per campaign
  - `feedback_f1_intra_district_is_important.md` — F1 stays, horizontal prospecting is valid
  - `feedback_scout_data_mostly_untested.md` — most Scout sheet data is from test runs, not active use
  - `project_research_engine_needs_cost_redesign.md` — cost/time redesign required before backlog drain
  - `project_bug5_shared_city_gap.md` — Detroit contamination post-mortem

- **F1 intra_district scanner stays active.** Session 59 original Option C (retire F1 + bulk-skip 384 rows) was withdrawn after Steven pushed back on the flawed audit. Horizontal prospecting to sibling schools in active-customer districts is a valid sales motion; the scanner is not redundant; F1 data mostly needs re-running once the research engine is cheap/fast enough, not deletion. 384 rows stay `pending`.

- **Scout data is mostly from test runs** (per Steven Session 59). Only the conference/webinar follow-up sequences and manual prospecting have been used actively. Treat Prospecting Queue, Signals, Leads from Research, and other derived tabs as scaffold-data until the pipelines are rerun with trusted economics. Active Accounts / Pipeline / Closed Lost / Activities are Salesforce-sourced and trustworthy.

- **Research engine honest numbers** (measured from Research Log, 27 recent jobs): avg 7.3 min/job, range 3.5-11.6 min, ~45 queries/job. Per-job cost estimated $0.35-0.95 (Serper + Exa + Brave + Claude extractions). For 384 intra_district rows serial: ~47 hours wall clock, ~$135-365 total. **This is too expensive and too slow for bulk use. Research engine bulk-mode optimization is a blocker for any backlog drain** — separate plan-mode session required.

- **Session 58 carryover still stands:** CSTA roster 77/41 matchable, CSTA enrichment wired to F1/F2/F4/F6/F7/F8, F4/F6/F7 kill switches, BUG 4 diocesan playbook, BUG 5 two-stage filter, F9 handler (scanner quality still weak), Telethon bridge, Railway log API, `/prospect_approve all` + `/prospect_skip all` working.

- **Silent failure spot-check** (5 recent non-diocesan Steven-owned sequences, loose expectations): findings documented — all 5 have at least one banned-phrase or dash failure. Not fixed without Steven's sign-off (legacy sequences are Steven's own work). Notable: seq 1999 "2026 License Request Seq (April)" uses `schedule=51` which is NOT in Steven's 5 named schedules — flag for Steven attention. Validator's en-dash (U+2013) detection is producing false positives on legitimate date ranges; future iteration should make en dash a warning not a failure.

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 59:** Diocesan value extraction + tool hardening. Rounds 1-3 shipped 12 user-visible failures (missing meeting link, "one pager" CTA repetition, em dashes, auto-gen descriptions, rogue schedule 19, 60x-too-short intervals, F1 audit category error, fabricated cost numbers, "F3 retired" fabrication, etc.) — every one caught by Steven in the Outreach UI or sheet audit, not self-caught. Root cause was shipping on API 2xx + memory not loaded, not reasoning quality per se. Round 4 installed tool hardening: `validate_sequence_inputs` + `verify_sequence` in `tools/outreach_client.py` make 8 of 12 failure modes structurally impossible at the code boundary, plus 14 unit tests. All 6 diocesan sequences 2008-2013 verified clean in Outreach with correct schedule/owner/intervals/bodies. Added 3 process rules to `docs/SCOUT_RULES.md` + 4 preflight checklists to this file. 14 memory files banked. F1 stays active after Steven pushback on flawed audit. Research engine bulk-mode optimization deferred to Session 60 as a blocker for backlog drain. Commits: `042f146`, `4051f53`, `7c162b6`, `eff3786`, `880d77b`, `1f22991`. Plan: `~/.claude/plans/lexical-swinging-pelican.md` (v3 after 2 pressure-test passes).
- **Session 58:** Priorities 1–4 comprehensive knockdown. Stage 6/7/8 (F6/F7/F9/F1), diocesan drip started (6 of 16 approved), CSTA enrichment wired to F4/F6/F7/F8 via helper, CSTA roster 39/14 → 77/41, `/prospect_approve all` bug fixed, CLAUDE.md doc trim. 7 commits (`185a3f2`, `c947681`, `e52ce25`, `3ea1be1`, `69a3e9c`, `529a919`, end-of-session). Plans: `~/.claude/plans/mellow-bouncing-lemur.md` (CLAUDE.md trim).
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits. Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits.
- **Session 53:** Fire drill audit. F2 max_tokens fix. 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.

### What still needs to be done (Session 60 — execute + decisions)

1. **STEVEN ACTION — activate the 6 diocesan sequences** (IDs 2008-2013) in Outreach UI. All verified clean via `verify_sequence`. Open each, click Activate, toggle all 5 templates active, add prospects from `Leads from Research` tab. Philadelphia (20 verified central-office contacts on `@archphila.org`) and Cincinnati (23 contacts on `@catholicaoc.org`) are the gold targets — start there.
2. **STEVEN DECISION — schedule 51 on seq 1999.** "2026 License Request Seq (April)" uses schedule 51, NOT in Steven's 5 named schedules. Either a legacy schedule that should be migrated to schedule 1 (Hot Lead Mon-Fri), or a 6th schedule Steven has that isn't in the allowlist. Flag was raised by Session 59 Section 3 spot-check.
3. **SESSION 60 PRIMARY: research engine bulk-mode optimization** — plan-mode session. Measure per-layer hit rates from recent Research Log, add parallelism with rate-limit budget, add entity-level caching, introduce early termination on confidence threshold, and use the territory master list as L0 to skip re-discovery. Target: 10x cost reduction + 6-8x speed up. **Blocker for any backlog drain** (intra_district 384, charter_cmo 15, cte_center 34, private_school_network 16, cs_funding 7, cold_license_request 1,245, winback 247).
4. **SESSION 60 — BUG 5 code fix** in `tools/research_engine.py:_target_match_params`. Shared-city gap (Detroit/Pittsburgh/OKC/Fort Worth/Houston/Lincoln/Omaha/Nashville dioceses all share city tokens with public districts). Test harness, same shape as BUG 1 Session 57. Runtime `public_district_email_blocklist.json` is current patch.
5. **SESSION 60 — 9 pending dioceses review** with per-diocese blocklist-gated cleanup after each research job completes. Pittsburgh/OKC/Omaha first. Only after BUG 5 fix ships OR blocklist enforcement is wired into the research engine.
6. **OPTIONAL — F9 compliance scanner query redesign.** Separate plan-mode session. Empirical Serper PDF probes first, then query iteration. Exit criterion ≥60% HIGH validation rate.
7. **OPTIONAL — LA archdiocese research restart.** Hand-seed with `lacatholicschools.org` and rerun; regenerate sequence if yield improves.
8. **OPTIONAL — IN/OK/TN CSTA hand-curation.** +15 matchable entries. ~15-30 min manual Google/LinkedIn work.
9. **DEFERRED — cold_license_request 1,245 + winback 247 stale March backlogs.** Dedicated plan-mode session to decide purge vs cherry-pick vs retire. Blocked on research engine redesign.
10. **FUTURE — wire `create_sequence` into `_on_prospect_research_complete` handler.** Tool hardening is in place so the wiring is safe when it ships. Every future auto-approved diocesan/charter/cte prospect will auto-generate a live Outreach sequence with full validation.

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

## PREFLIGHT CHECKLISTS (load these before starting any task in the triggered category)

Session 59 shipped 12 failures across 3 rounds because memory files weren't loaded before touching the topics they covered. These checklists are MANDATORY reads at the start of any task matching the trigger. They live in CLAUDE.md (not a separate file) so they're always in session context.

**PREFLIGHT: Outreach work** — triggers on any task creating/modifying Outreach sequences, templates, prospects, or schedules.
- Confirm `tools/outreach_client.py::validate_sequence_inputs` is callable and knows the current allowlist (env `OUTREACH_ALLOWED_SCHEDULE_IDS` or default `{1, 48, 50, 52, 53}`)
- Ask Steven for the campaign-specific meeting link BEFORE building (if the sequence is cold — see `user_meeting_link_pattern.md`)
- After creation, check `validation_failures` in the return dict. If non-empty, PATCH before declaring done. If the result has `validation_errors`, the post-write fetch failed — retry or investigate.
- Never bypass the validator. Never recommend manual Outreach copy/paste when `create_sequence` exists (see `feedback_never_manual_outreach_upload.md`).

**PREFLIGHT: Sequence content** — triggers on any task writing sequence bodies, subjects, or `extra_context` for `sequence_builder.build_sequence`.
- Load: `memory/feedback_sequence_copy_rules.md`, `memory/feedback_sequence_iteration_learnings.md`, `memory/feedback_bond_trigger_outreach_tone.md`, `memory/feedback_email_drafting.md`
- Verify the planned structure: Step 1 ≤80 words, 5-day minimum cadence (cold), distinct angle per step, breakup ≤60 words, meeting link in ≥1 step, `codecombat.com/schools` in ≥2 steps, 3 distinct CTA phrasings (no "one pager" repetition), merge fields `{{first_name}}`/`{{company}}`/`{{state}}` present
- Call `validate_sequence_inputs` on the built output before writing any Google Doc or pushing to Outreach. Fail fast.

**PREFLIGHT: Sheet audit** — triggers on any task aggregating, filtering, or recommending action on rows in the master sheet.
- Write the question in 1-3 plain-English sentences. Map every concept in the question to a literal column in a literal tab.
- Dump row 1 (header) of every tab being read. If a concept has no backing column, STOP — you're reading the wrong tab. (The Session 59 F1 category error happened because "Active Accounts" was read as if it had contact data. It has zero contact columns.)
- Spot-check 3 raw rows before writing any aggregation. Distrust clean 100%/0% numbers — real sales data is rarely that clean.

**PREFLIGHT: Cost/time estimate** — triggers whenever quoting a cost, time, count, or percentage range in a recommendation.
- Grep telemetry first: `Research Log` for research jobs, `Activities` for actions, provider billing dashboards for API cost.
- Pull 5-10 real rows and aggregate. Label the result explicitly: `measurement / sample / extrapolation / estimate / unknown`.
- If unknown and the number matters, say "unknown — here's how to find out." Do NOT fill in a plausible range. (Session 59 fabricated "$200-800 cost / 30 hours" for 384 research jobs — real numbers were $135-365 and 47 hours, both directions wrong.)

---

## CRITICAL RULES (top 15 — full rule set in `docs/SCOUT_RULES.md`)

1. **Always enter plan mode** before non-trivial builds. New scanners, strategies, schema changes, multi-file refactors — all require `EnterPlanMode` + Steven's sign-off. Session 51 shipped 7 features without plan mode; 3 had BLOCKER bugs. Established Session 52.
2. **Always push code from Claude Code via git**, never `/push_code` in Telegram (4096 char truncation). `git add`, `git commit`, `git push` directly from Claude Code terminal. Hard rule since Session 19.
3. **Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs in `agent/CLAUDE.md` + `tools/CLAUDE.md`.
4. **Every plan is one-shot; pressure-test hard BEFORE presenting.** Don't write a plan expecting refinement rounds. Steven rejected plans that pushed rigor onto him. See `memory/feedback_plans_are_one_shot.md`.
5. **Verify foundational assumptions empirically BEFORE writing plans.** Walk the pipeline end-to-end and probe the load-bearing assumptions (Serper queries, httpx fetches, grep verification). BUG 1 + BUG 2 both had silent rev-1s that only surfaced via live probing.
6. **Execute the task-triggered preflight checklists in the Preflight section above** before starting any work in the triggered categories (Outreach work, Sequence content, Sheet audit, Cost/time estimate). Session 59 shipped 12 failures across 3 rounds because memory files weren't loaded before touching the topics they covered. Memory files only help if loaded; preflight checklists force the load. Session 59 lesson.
7. **New scanners ship with kill switches.** `ENABLE_X_SCAN = True` constant near top of `tools/signal_processor.py`. Scanner short-circuits at function entry when disabled. One-line disable in production without removing code.
8. **Multi-feature sessions → one commit per feature.** Don't bundle features into one big commit at session end. Separate commits enable surgical `git revert`.
9. **Signal vs Prospect routing for new lead-gen scanners.** HIGH confidence → auto-queue via `district_prospector.add_district()` as `pending`. MEDIUM/LOW → Signals tab only via `write_signals()`. Active customer match → `customer_intel` log only (don't sell, don't discard). All queue writes are `pending` — Steven manually approves.
10. **`handle_message()` and async tasks must call `get_gas_bridge()` locally** — never reference `gas` as a free variable. Python treats `gas` as local throughout the function (it's assigned later for `/call_list`), so any earlier reference raises `UnboundLocalError`. Same for `_run_*_scan()` tasks spawned via `asyncio.create_task()`. Two latent bugs shipped in Session 49 from this pattern.
11. **Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Synchronous versions freeze the event loop. Synchronous blocking code called from async context must use `run_in_executor`.
12. **`global` declarations go at the TOP of `handle_message()`**, not in elif blocks. Python SyntaxError if `global` appears after first use of the variable. One line at top: `global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _pending_csv_intent, _last_proximity_result`.
13. **`tool_result` always follows `tool_use`.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing `tool_result` → 400 on next API call.
14. **Explicit slash commands bypass Claude and call `execute_tool()` directly.** `/brief`, `/call`, `/recent_calls`, `/progress`, `/sync_activities`, `/call_list`, `/pipeline`, `/pipeline_import`, `/import_*`, `/enrich_leads`, all `/prospect_*`. Direct dispatch is the only reliable pattern — when conversation history is long, Claude responds with descriptive text instead of calling tools.
15. **NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement. **ALL sequences are drafts** — always Google Doc + Telegram link for Steven's approval. Never auto-finalize.
16. **Never design workflows requiring large-text paste through Telegram.** 4,096 char limit. Use fetch-first: Scout reads from GitHub, asks for changes in plain English.

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
