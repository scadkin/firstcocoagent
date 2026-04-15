# SCOUT MASTER PLAN
*Last updated: 2026-04-15 — End of Session 66. Queue drained (3 stale framings caught), S55 audit re-run showed zero real contamination (measured), Scout Complete System Overview Google Doc v1/v2/v3 shipped, primary/secondary targeting correction captured across CLAUDE.md + SCOUT_PLAN.md + docs/SCOUT_RULES.md + memory, state+timezone rule expanded with both failure modes, secondary-lane scanner gaps captured as tracked todo, international territory expansion parked, 6-tier prioritization + budget plan parked for revisit, 23 of 24 strategies shipped math correction. Five commits pushed this session (`1e60d11`, `ddefd06`, `0779c3b`, `2e67680`, EOS wrap). Session 67 focus: build email sequences for the 23 active strategies.*

---

## YOU ARE HERE → Session 66 (end) drained the S65 priority queue by auditing every item and finding three stale framings (CSTA untried → tapped out S63; S55 audit blocked → audit is a re-runnable script that showed zero real contamination on current sheet; scaffold cleanup deletable → governing memory file explicitly forbids bulk delete). Built a Scout Complete System Overview Google Doc across 3 revisions to capture what Scout IS, HAS, and CAN DO — v3 corrected v2's territory-expansion mistake (kept 13 US + SoCal, parked international), expanded the secondary-lane definition beyond "charter/CTE/diocesan/private" to include libraries / after-school nonprofits+for-profits / online schools / IB / state DOE CS / regional public entities / any K-12 curriculum buyer, added secondary-lane scanner gaps as a tracked todo, expanded state+timezone rule with both failure modes (mergefield rendering + send schedule optimization), fixed the "22 of 24 strategies shipped" off-by-one to 23 of 24 (measured). Parked a full 6-tier prioritization + weekly budget allocation plan for revisit after sequence-build phase. Session 67's explicit focus is building email sequences for the 23 active strategies and their targets, starting with Tier 1 warm-re-engage strategies (9/10/11/12). Five commits pushed this session. Active queue: only Thursday 2026-04-16 diocesan drip remains.

**Three new commits on `main` this session (all pushed to `origin/main`):**

1. **`64b9511` docs(session-65): reframe priority queue after mid-session audit.** F2 and research cross-contamination both confirmed RESOLVED in S55 via memory file re-read. BUG 5 closed as WONTFIX after audit showed 1-of-71 (measured — 1.4%) contamination rate post-S55 filter — S55 two-stage filter + S63 blocklist are the complete solution, permanent code fix has negative ROI. Deleted stale `docs/session_65_prep_bug5_target_match_params.md`. Rewrote `memory/project_s64_priority_queue.md` with thin reframed queue. Updated CLAUDE.md CURRENT STATE LOCKED PRIORITY QUEUE. Rebased over `39c15d2` (Scout bot daily summary).

2. **`0b72295` feat(rule21): scanner rule for verify-before-instructing.** Motivated by S65 incident where I told Steven to delete 3 rows from `Leads from Research` based on interpreting stale audit-doc screenshots without calling `sheets_writer.get_leads()` — 2 of 3 rows didn't exist in the current sheet and the 3rd was already correctly relabeled. R21 adds a new rule type `trigger_and_missing_anchor` to `scripts/rule_scanner.py`: 9 trigger patterns (delete-row, ctrl-f-find, right-click-delete, wipe-clear-tab, modify-row, delete-row-id, sheet-delete-nav, recommend-delete), ~35 anchor patterns (live-state reader function names from `tools/`, git state commands, `.venv/bin/python`, WebFetch, WebSearch), 7 exemption patterns (past-tense, hypothetical, code-behavior present/future, method-call, questions, negations). `anchor_text_scope: "raw"` means function names in fenced code blocks count. 25 new R21 tests including S65 failed response as permanent regression fixture. Total scanner tests: **59 green**. Historical SCOUT_HISTORY.md S55-S58 prose returns zero R21 false positives (measured). Also: machine-local `~/.claude/hooks/scout-stop-scan.sh` pre-filter broadened from digit-only to also match R21 destructive keywords — not in the repo commit because hooks are machine-local, but documented in commit message and `feedback_verify_before_instructing.md`.

3. **`394869b` docs(rule21): CLAUDE.md preflight + Rule 21 text + header.** New "PREFLIGHT: Destructive instruction to Steven" entry in the preflight checklists block. New Rule 21 in CRITICAL RULES list (top-19 → top-20). Header timestamp updated. Explicit process-rule bullet for destructive instructions NOT covered by R21 (credential rotation, paste-new-secret, revoke-token — different verification shape). `.env` loading requirement documented. Memory file `feedback_verify_before_instructing.md` + `MEMORY.md` index entry written to the auto-memory dir.

**Plan architecture reminder:** the plan went through TWO full pressure-test rebuild cycles per Steven's senior-reviewer prompt. Draft 1 → draft 2 caught 6 structural issues (rotate-secret wrongly in scope, normalization conflict with code blocks, sentinel field overloading, missing exemption patterns, thin test suite, weak correction wording). Draft 2 → draft 3 caught 10 more precision issues (R20 cross-contamination in R21 test inputs, performance bug in scan(), over-loose recommend-delete regex, missing negation/future-tense exemptions, unreadable long matches in correction directive, SCOUT_HISTORY.md regression test needing jq filter, vague calibration categories, protocol gap for rotate-secret, load_dotenv() requirement unmentioned, and regex trigger precision issues). **Meta-lesson: senior-reviewer pressure-test protocol needs TWO passes for code-touching plans.** One pass surfaces structural gaps; the second pass surfaces precision/correctness bugs. Full plan at `~/.claude/plans/smooth-splashing-narwhal.md`.

**Session 65 key narrative moments:**
- **First reframe (small apples):** Started on BUG 5 pre-plan audit. Before writing the plan, Steven asked "what is the whole point of what were doing with this diocese work here? because this is so small appples we shouldnt be spending much time on diocse stuff ever." That one question killed BUG 5 as a plan-mode target and reshaped the whole queue.
- **Second reframe (stale queue):** Proposed promoting F2 to #1 in the reframed queue. Before writing files, re-read the F2 memory file — confirmed RESOLVED in S55. Then re-read research cross-contamination memory — also RESOLVED in S55. Both items had been in the queue because I copied framing from older CURRENT STATE paragraphs without re-reading the actual memory files at S64 EOS. Same default-to-shallow-reading root as the row-deletion incident that came next.
- **Third reframe (Rule 21):** Wrote row-deletion instructions from screenshot interpretation. Steven pushed back hard ("HOW CAN WE STOP THIS FROM HAPPENING? HOW ARE YOU NOT MORE RESOURCEFUL"). Pivoted to plan mode to build a structural fix. Two full pressure-test rebuild cycles. Shipped Rule 21.
- **Plan-mode discovery:** launched two parallel Explore agents during Phase 1 to map the existing scanner infrastructure AND inventory the live-state reader tools available in `tools/`. Critical findings: the scanner's `scan()` function needed a small additive change (new rule type dispatch) rather than overloading existing fields; the stop hook wrapper only sees prose not tool JSON, forcing verification to be narrated in prose or code blocks; ~30 reader functions exist that become the anchor whitelist.

**Session 65 behavioral findings:**
- **Rule 20 scanner kept firing** on ghost matches during the session (same known issue documented in `feedback_rule_scanner_hook_installed.md`). I emitted multiple correction directives throughout the session. None were blockers — the correction protocol works as intended. The ghost matches appear to come from stale violation log entries from prior smoke tests.
- **`sheets_writer.get_leads()` silently returned zero rows** on the first smoke test because `.env` wasn't loaded. Scout tools modules don't call `load_dotenv()` internally — the caller must. Fixed via `from dotenv import load_dotenv; load_dotenv()` at the top of the test script. Now documented in the R21 preflight checklist + `feedback_verify_before_instructing.md` so future sessions don't hit the same silent failure.
- **The pressure-test-twice protocol caught 16 total issues across two passes.** Single-pass senior-reviewer is insufficient for code-touching plans. The first pass catches structural issues (architecture, scope, API shape). The second pass catches precision issues (regex correctness, test assumption errors, performance, edge cases). Both are load-bearing.

### Carryover into Session 66+ — REFRAMED PRIORITY QUEUE

Lives at `memory/project_s64_priority_queue.md` (auto-loaded every session). Mirror in `CLAUDE.md` CURRENT STATE. **Do in order, nothing else without Steven's explicit redirection:**

1. **HARD DEADLINE: Thursday diocesan drip** — `.venv/bin/python scripts/diocesan_drip.py --execute` on Thu 2026-04-16 (do NOT `--force-day`). 14 contacts (measured — S66 dry-run --force-day 2026-04-16), roughly 6 min wall clock (sample). Then `--verify` to confirm all 63 diocesan contacts landed. **This is the only active queue item remaining after S66 drained/parked everything else.**
2. ~~**S55 audit re-run**~~ — **DONE S66.** Ran `scripts/audit_leads_cross_contamination.py` (commit `b809198`, 273 lines measured) against current sheet. Oracle gates passed. 551 rows total (measured), 15 flagged (measured) — ALL 15 were abbreviation false-positives (LAUSD `lausd.net`, Desert Sands `dsusd.us`, ROWVA CUSD 208 `rowva.k12.il.us`, Community HS District 218 `chsd218.org`, Friendswood ISD `fisdk12.net` — all legitimate district-owned domains). Zero real contamination in current sheet. The S55 Archdiocese → ROWVA/CHSD218 real-contamination rows have been naturally cleaned via row relabeling since S55. Fresh audit Google Doc at `https://docs.google.com/document/d/1zLtZd7w5On_kQ1T_xA_u-iXUQUuy7bV4kaHOBFtEZXM/edit`. No deletions needed. Item closed.
3. ~~**Prospecting Queue / Signals / Leads scaffold cleanup**~~ — **PARKED S66.** Third stale queue framing caught in S66: the governing memory file `feedback_scout_data_mostly_untested.md` line 12 explicitly forbids bulk-delete or retire-scanner actions on scaffold-appearing data — the right move is "rebuild the scanner / re-run with better economics" rather than throwing rows away. Since Research Engine Round 1.1 is itself parked, item #3 is blocked on upstream parked work. Row counts measured S66 via `sheets_writer`: Prospecting Queue 2,053 / Signals 18,906 / Leads from Research 551.
4. ~~**Housekeeping — OUTREACH_CLIENT_SECRET rotation**~~ — **PARKED S66 per Steven ("skip").** Purely cosmetic workaround removal. The `scripts/env.sh` shim (S64 commit `8b63d12`) works correctly; rotating the secret would just let us delete the ~30-line shim. No security or functional value. Not worth the interrupt. Shim stays.
5. **Rule 21 calibration checkpoint** — after 3-5 live sessions (S68-S70 window), read `~/.claude/state/scout-violations.log` for R21 entries, classify into correct-fire / correct-pass / false-fire / false-pass, iterate regex per calibration thresholds in `~/.claude/plans/smooth-splashing-narwhal.md`.

### Explicitly PARKED (do not start until queue drained, and even then only with explicit redirection)

- **Secondary-lane scanner gaps** (S66 todo) — Scout's F6/F7/F8/F10 scanners cover only about half of Steven's real secondary lane. No scanners exist for libraries / library networks, after-school nonprofits (Boys and Girls Clubs / YMCA / 4-H / Scouts), after-school for-profits (Code Ninjas / iCode / CodeWiz / Coder School / Mathnasium), online schools + online school networks, IB networks, state DOE CS coordinators, or regional public entities as a class. Plan-mode required before building any (Rule 1). International scanners (Canada / Mexico / Central America / Caribbean / South America) are also parked here as a separate deferred expansion — needs NCES-equivalent data sourcing plus `tools/territory_data.py::TERRITORY_STATES` expansion + non-US scanner query rewrites. Reference: `memory/project_secondary_lane_scanner_gaps.md`.
- **International territory expansion** — considered S66, parked. Steven kept the active territory at 13 US states + SoCal. Non-US prospecting only starts if Steven explicitly flags a big-fish exception, not as a scope change. Reference: `memory/user_territory.md`.
- **IN/OK/TN CSTA hand-curation + fetcher iteration** — **PARKED per S66 Steven directive.** Was S65 queue item #2. S63 hand-curation (commit `ace2abc`) already shipped IN Julie Alano + TN Becky Ashe (2 entries measured); OK skipped because only known candidate was at a nonprofit, disqualified by `feedback_scout_primary_target_is_public_districts.md`. Hand-curation ceiling hit — chapter websites have removed their public rosters. Higher-leverage path is iterating `scripts/fetch_csta_roster.py` with LinkedIn-snippet-only extraction for the 3 chapter subdomains, but that's scanner-code work → Rule 1 plan-mode required → not worth the plan-mode latency for CSTA roster-enrichment yield. Do NOT propose restarting without Steven's explicit redirection. Reference: `memory/project_csta_roster_hand_curation_gaps.md` S66 PARKED block.
- **23 pending diocesan networks expansion** (Pittsburgh/OKC/Omaha/Lincoln/Tulsa/Memphis/Nashville/Galveston-Houston/etc). Per S65 directive: diocesan work is small apples, do not expand. The 6 already-activated diocesan sequences run their course naturally.
- **LA archdiocese research restart** — blocked on F8 diocesan playbook gap. Diocesan, parked indefinitely.
- **BUG 5 permanent code fix** — **CLOSED as WONTFIX.** See `memory/project_bug5_shared_city_gap.md`. Do not re-open.
- **Research Engine Round 1.1** — cost-ceiling work. Opportunistic only, not on explicit priority list.
- **First live campaign via `load_campaign.py`** — cross-session validation, opportunistic when a real campaign is on the plate.
- **Handler wiring `_on_prospect_research_complete → execute_load_plan`** — reframed as wrong problem in S64. Permanently historical. `docs/session_64_prep_prospect_loader_wiring.md` is historical.
- **1,245 cold_license_request + 247 winback March backlogs** — deferred per prior sessions.

### Prior SESSION 64 narrative (archived below for reference)

---

## Previous YOU ARE HERE → Session 64 (end) reframed the "prospect_loader wiring" carryover from S63 as the wrong problem, pressure-test-rebuilt the plan, shipped a strategy-agnostic campaign loader with role segmentation and claude.ai round-trip, fixed a latent Outreach API filter bug, and left a BUG 5 prep note for the next session's top-priority plan-mode work.

**Ten new commits on `main` this session (all pushed to `origin/main`):**

1. **`f638168` feat(campaign_file):** single-file campaign markdown schema + permissive parser + canary fixture + 10 round-trip/edge-case tests.
2. **`a530aac` feat(outreach): export_sequence_for_editing** — thin wrapper around `export_sequence` that renders in the campaign_file schema so Steven can fetch an existing Outreach sequence as a claude.ai starter. 4 offline unit tests.
3. **`27e2243` feat(role_classifier):** Haiku temp=0 per-contact bucketing (admin/curriculum/it/teacher/coach/other) with `is_relevant_role` pre-filter + sha1-keyed cache. 11 unit tests via mock Anthropic client. **Live smoke: 14/14 real K-12 titles classified correctly.**
4. **`09668c0` feat(load_campaign):** generalized campaign loader CLI with `--preview` / `--create` / `--execute` / `--dry-run` / `--force` modes, CSV and stdin contact input, sidecar state with sha1 drift detection, Rule 19 name translation on stdout. Canary fixtures + docs (SCOUT_CAPABILITIES + CLAUDE.md PREFLIGHT: Campaign load). Canary smoke: 3/3 variants pass preflight, 5 fake contacts classify into 4 buckets.
5. **`afb8680` fix(oauth + export):** three-way bundle. (a) `load_dotenv()` added to `scripts/load_campaign.py` per Scout convention. (b) `tools/outreach_client.export_sequence` was calling `/sequenceTemplates?filter[sequence][id]=<N>` which Outreach rejects with 400 — rewrote to loop over steps and use `filter[sequenceStep][id]=<step_id>` per step, matching the working pattern at `validate_sequence_inputs:1115`. (c) `campaign_file.dump_campaign` now passes `allow_unicode=True` so em-dashes render natively instead of `\u2014`. Verified end-to-end against a live Outreach sequence fetch.
6. **`8b63d12` feat(env): scripts/env.sh shim** — proves empirically that no quoting scheme cross-parses between bash and python-dotenv for the current `OUTREACH_CLIENT_SECRET` value (contains both `'` and `$`). Shim uses python-dotenv internally and emits shlex-quoted `export` lines bash can eval cleanly. Usage: `source scripts/env.sh` instead of `source .env`.
7. **`74f4c7f` feat(export): slug cleanup + HTML→markdown** — `_slugify()` collapses runs of non-alphanumerics to single underscores; `_html_to_markdown()` converts Outreach's HTML bodies (`<br>`, `<p>`, `<a href>`, `<strong>`, `&amp;`) to clean markdown for claude.ai readability. 3 new unit tests + live Chicago diocesan export re-verified.
8. **`6ea3b29` test(load_campaign):** 19 CLI unit tests covering contact hydration (5 skip paths), sidecar state round-trip, sha1 stability, drift detection (all 4 branches), plan building (role routing + warn-on-missing-variant), and three `cmd_create` flows (dry-run no-write, idempotent re-run, preflight-failure abort). Mocks `outreach_client` for offline runs.
9. **`ea746e7` docs(session-65-prep): BUG 5 prep note + CLAUDE.md priority queue lock** — `docs/session_65_prep_bug5_target_match_params.md` with all 4 call sites of `_target_match_params` mapped, 5 candidate fix approaches, 7 open questions for the plan-mode session. CURRENT STATE "exact next actions" replaced with Steven's locked 8-item priority queue.
10. **(This EOS commit)** `docs(session-64): end-of-session wrap` — SCOUT_PLAN / CLAUDE.md / SCOUT_HISTORY updates, new reference memory for the bash-vs-dotenv quoting gotcha.

**Plan architecture reminder:** the plan went through one full pressure-test rebuild cycle (v1 → v2) per Steven's senior-reviewer prompt. v1 had three structural problems: (a) multi-file `campaigns/<slug>/config.yaml + variants/` directory layout that forced Steven to translate claude.ai output into a new schema on every round trip; (b) rule-based role classifier that caps at 75-85% accuracy (estimate) and needs 150-300 lines of regex (estimate) to get there; (c) included a diocesan_drip refactor mid-week with live production drip running the next two days (real risk, zero upside). v2 fixed all three: single-file markdown schema, Haiku temp=0 classifier in ~50 lines (estimate), diocesan refactor dropped entirely. v2 also added preflight-validator-runs-all-variants-first, sidecar state with drift detection, and stdin contact input for paste workflows. The plan pressure-test was the highest-value meta-lesson of the session — v1 would have shipped UX friction that ate every future campaign.

**Session 64 key narrative moments:**
- **First reframe**: I started by proposing the wrong plan — the S63 prep note's handler-wiring approach. Steven said "haven't we got these features built already?" and clarified his real workflow: drafts in claude.ai, role segmentation, multi-variant sequences, staggered loads. That reframe killed a whole prep-note-directed session and replaced it with what the generalized loader actually needed to be.
- **Second reframe**: my own Q2 — "does the research result contain verified contacts?" — Steven correctly pushed back that I should investigate the codebase myself rather than bring the question. I grepped `tools/research_engine.py`, found `result["contacts"]` at line 406, and answered my own question. The coaching feedback was "always try to dig into the abilities, learnings, history, etc of everything we have done before bringing me the question."
- **Third reframe**: Option B (the `.env` cleanup) turned out to be unsolvable at the quoting-scheme level. I proof-tested 4 schemes and none work for both bash and python-dotenv. Pivoted to a shim script. This was the right move but required the empirical tests to earn the right to abandon the obvious fix.
- **Fourth reframe**: while testing the Chicago diocesan export, I hit a 400 on `/sequenceTemplates` that had nothing to do with OAuth — it was a pre-existing latent bug in `export_sequence()` using the wrong filter shape. Scope-creeping the fix was the right call because it blocked the value of Commit 2. One commit bundled the OAuth `load_dotenv` fix + the filter fix + the yaml unicode cosmetic fix.

**Session 64 behavioral findings (no new memory needed, existing rules covered them):**
- The rule scanner fired ghost matches repeatedly on `40%` / `20%` / `$0.30` even when those strings were not in my prose. Cause is stale entries in the production violation log from prior smoke tests. Already documented S63 in `feedback_rule_scanner_hook_installed.md`. No new findings; just lived with the false positives this session.
- Wrap-ups-are-not-rushed rule stayed in force through this wrap. S64 crossed the 40% pause line during wrap sequence per Steven's directive, and that's the intended behavior.

### Carryover into Session 65+ — LOCKED PRIORITY QUEUE

Lives at `memory/project_s64_priority_queue.md` (auto-loaded every session). Mirror in `CLAUDE.md` CURRENT STATE. **Do in order, nothing else without Steven's explicit redirection:**

1. **HARD DEADLINE: Thursday diocesan drip** — `.venv/bin/python scripts/diocesan_drip.py --execute` on Thu 2026-04-16. Preempts the queue because of the fixed date. 14 contacts, roughly 6 min wall clock (sample).
2. **BUG 5 permanent fix** — `tools/research_engine.py::_target_match_params`. Plan-mode session required per Rule 1. **Read `docs/session_65_prep_bug5_target_match_params.md` FIRST.**
3. **LA archdiocese research restart** — blocked on F8 diocesan playbook gap.
4. **IN/OK/TN CSTA LinkedIn-snippet extraction** — iterate `scripts/fetch_csta_roster.py`.
5. **F2 column layout corruption** — 1,912 pre-existing scrambled rows + active writer bypass, root cause unknown.
6. **Research cross-contamination audit** — post-extraction domain validation layer.
7. **Prospecting Queue / Signals / Leads cleanup** — scaffold data sweep.
8. **Known debt / housekeeping** — rotate `OUTREACH_CLIENT_SECRET` to remove the `'`+`$` combo, refresh stale docs.

### Explicitly NOT in the priority queue (deferred)

- First live campaign via `load_campaign.py` — cross-session validation, opportunistic.
- Research Engine Round 1.1 per-URL content MERGE — cost ceiling blocker but not on Steven's explicit list. Treat as "after #8 unless reprioritized."
- Handler wiring `_on_prospect_research_complete → execute_load_plan` — reframed as wrong problem during S64 plan mode. Replaced by `scripts/load_campaign.py`. `docs/session_64_prep_prospect_loader_wiring.md` is now historical.
- 1,245 cold_license_request + 247 winback March backlogs.

---

## Previous YOU ARE HERE (archived to Session 63 narrative below)

**Six new commits on `main` this session:**

1. **`f479241` docs(rules): Commit 0 empirical findings.** Stop-`{decision:block}` forces in-turn continuation via a synthetic `"Stop hook feedback: ..."` user message; UserPromptSubmit `additionalContext` reaches next turn; Stop stdin field is `last_assistant_message` (plain prose only); the recursion guard on `stop_hook_active:true` is load-bearing. Tests ran via isolated `claude -p --setting-sources project --settings` — live settings.json never touched.
2. **`4f434d5` docs(session-63): mid-session state.** Bridge commit.
3. **`ace2abc` data(csta): hand-curated IN + TN roster entries.** Julie Alano (IN, Hamilton Southeastern Schools, verified match via `enrich_with_csta` on both short and long district spellings) + Becky Ashe (TN, display-only empty district). OK skipped — only lead was a Tulsa nonprofit, not a public school district. Yield is two entries vs "+15 matchable" extrapolation in the gap memory; chapter websites have restructured and the higher-yield path is iterating `scripts/fetch_csta_roster.py` with LinkedIn-snippet extraction in a future session.
4. **`c5d7753` docs(session-63): end-of-session wrap.** CLAUDE.md CURRENT STATE rewritten for final S63 outcomes; SCOUT_HISTORY.md §Session 63 appended with the full narrative.
5. **`b358819` test(hooks): scripts/test_hook_wrappers.sh.** Five smoke-test assertions for both hook wrappers, exercised via the new `SCOUT_VIOLATIONS_LOG` env override so production state is never touched. Gracefully exits 0 when wrappers aren't installed / jq is missing / kill switch engaged.
6. **`78a6595` docs(session-64-prep): prospect_loader wiring scratch note.** Reading-only exploration dump at `docs/session_64_prep_prospect_loader_wiring.md` mapping `_on_prospect_research_complete` at `agent/main.py:319-528` and `execute_load_plan` at `tools/prospect_loader.py:259-390`. Eight open questions flagged — most importantly whether auto-load-on-research is compatible with CLAUDE.md Rule 15 (all sequences are drafts, never auto-finalize).

**Two machine-local hook-wrapper edits** (not committed; documented in `memory/feedback_rule_scanner_hook_installed.md`): `scout-stop-scan.sh` now reads `.last_assistant_message` instead of `.last_message` (fix for a silent fail-open bug present since the S62 install) and both wrappers honor a `SCOUT_VIOLATIONS_LOG` env variable (`PROC` derived from `LOG` in the injector).

**Wed 2026-04-15 diocesan drip loaded on Tue per Steven's approval:** 15 of 15 processed (measured from execute summary), 14 created, 1 existing reused, 0 failed, 0 skipped. First verify run showed one sequence returning the `-1` sentinel; re-run clean, so the original mismatch was a transient one-off. 14 contacts pending for Thu 2026-04-16.

**CSTA hand-curation pivot finding:** `scan_csta_chapters` is permanently retired (`ENABLE_CSTA_SCAN = False`, F5 retired S57 BUG 2) — CSTA is now an inline enrichment lookup via `enrich_with_csta` against `memory/csta_roster.json`. The hand-curation path is to edit the roster JSON directly; the scripted path is option 4 in the gap memory file.

**Session 63 behavioral finding recorded in memory:** the rule scanner fired multiple times in-session on my own prose because I reflexively cite ctx markers and rule thresholds without inline label roots. Documented in `feedback_r20_high_risk_prose_categories.md` with preferred phrasing templates.

**Next session's FIRST action options** (Steven picks one):
- (a) Thu diocesan drip on actual Thu 2026-04-16 — 14 contacts, roughly 6 min wall clock (sample from prior batches).
- (b) Plan-mode session for `prospect_loader.execute_load_plan` wiring into `_on_prospect_research_complete` — highest-leverage carryover, **read `docs/session_64_prep_prospect_loader_wiring.md` first**, then enter plan mode per Rule 1.
- (c) Research Engine Round 1.1 plan — per-URL content merge, not dedup.
- (d) BUG 5 code fix in `tools/research_engine.py::_target_match_params`.

### Session 62 commits (6 on main)

| commit | scope |
|---|---|
| `6da2a8f` | CLAUDE.md trim — Session 60/61 narrative moved to SCOUT_HISTORY §Session 60/61, CURRENT STATE replaced with ~30 line compact pointer block (roughly 57% reduction in file size, measured). |
| `3b97046` | Diocesan drip jitter fix — `scripts/diocesan_drip.py` `sleep_seconds` changed from `(300, 900)` to `(10, 30)`. Mon+Tue batches finished in roughly 6 min (measured) each instead of the prior roughly 2.7 h (estimate) per day. |
| `94cdc0e` | Rule 20 scanner + twenty locked test cases (all green, measured) + CLAUDE.md Rule 20 text + docs/SCOUT_RULES.md mirror. Scanner is `scripts/rule_scanner.py`; tests are `scripts/test_rule_scanner.py`; run via `.venv/bin/python scripts/test_rule_scanner.py`. |
| `a4ce984` | Rule 19 extension via the scanner's extensibility contract — one new dict in `RULES`, fourteen new test cases (all green, measured), CLAUDE.md Rule 19 text updated. Zero changes to hook wrappers or settings.json. Proof the contract works. |

**Non-repo machine-local changes (not committable):**
- `~/.claude/hooks/scout-stop-scan.sh` — Stop hook bash wrapper, roughly 45 lines (measured). Reads stdin JSON, pre-filters on digits, shells out to the repo scanner, appends to violation log, emits block JSON.
- `~/.claude/hooks/scout-violation-inject.sh` — UserPromptSubmit hook, roughly 50 lines (measured). Reads violation log atomically, injects correction directive as `additionalContext`, clears log.
- `~/.claude/settings.json` — Stop now has two hooks (sound + scout-stop-scan); UserPromptSubmit now has two (inject-now-and-ctx + scout-violation-inject). Backup at `~/.claude/settings.json.bak-s62`.
- `~/.claude/state/scout-violations.log` — auto-created on first violation; truncated to last 50 entries when size exceeds 100 KB (measured from scanner config).
- `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/feedback_rule_scanner_hook_installed.md` — NEW user-level memory file documenting the system + extensibility contract + rebuild path.
- `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/feedback_claude_manages_tracking.md` — NEW user-level memory file documenting Steven's explicit "you track, not me" preference from this session.
- `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/MEMORY.md` — index updated with a new "Structural enforcement" section pointing to the two new files.

### Diocesan drip status (measured from `scripts/diocesan_drip.py --verify`)

| Diocesan sequence | Live count | Expected | Status |
|---|---|---|---|
| Philadelphia | 10 | 10 | ✅ |
| Cincinnati | 10 | 10 | ✅ |
| Detroit | 4 | 4 | ✅ |
| Cleveland | 6 | 6 | ✅ |
| Boston | 4 | 4 | ✅ |
| Chicago | 0 | 0 | ✅ (single lead skipped — empty First Name in sheet) |

**Overall:** 34 of 63 contacts loaded across Mon+Tue (measured). 29 pending (measured): 15 Wed + 14 Thu. Wall clock for both days combined was roughly 11 min (measured). Zero failures. One reused-existing prospect on each day (dedup via `find_prospect_by_email` worked).

### The Session 62 core lesson (structural, applies to all future sessions)

Text rules in CLAUDE.md and memory files are probabilistic. Compliance tops out around 95% (estimate) because even when the rule is loaded in context, the pattern-match from a real situation to the rule's trigger language does not always happen in the moment of generation. The final 5% (estimate) requires code enforcement — a Stop hook that checks Claude's output programmatically and logs violations to a state file that forces correction on the next turn.

The Session 62 incident: Claude gave Steven three different wrong percentages for the context-window cost of a SessionStart hook (9%, 21%, 15% — all unlabeled, roughly 17% was the real measured value). Rule 6 + Cost/time preflight + `feedback_never_cite_made_up_numbers.md` all existed and were in context. None fired. Steven caught it himself and asked the structural question: "what's the point of rules if you can violate them at will?"

The fix is `scripts/rule_scanner.py` with an extensible `RULES` list. Adding a new rule is a single dict append + test cases. The Stop hook + UserPromptSubmit injector pipeline catches violations in Claude's output and forces a correction directive on the next user turn before any answer can be given.

**This pattern is now the standard for any high-stakes rule whose violation has concrete cost.** Future rules become enforceable by adding to `RULES`, not by writing more memory files that won't fire.

### Session 62 carryover (exact next actions, in order)

1. **FIRST ACTION of Session 63: Commit 0 empirical hook verification.** Follow the three-test procedure in `~/.claude/plans/playful-weaving-nygaard.md` §Commit 0. Three tests, roughly five minutes each (estimate). Tests: (a) does Stop-hook `{"decision":"block"}` force in-turn correction? (b) does UserPromptSubmit `additionalContext` actually reach Claude? (c) what's in `last_message` — prose only or serialized tool-use blocks too? After running, update the "PENDING" verdicts in `scripts/rule_scanner.py`'s module docstring and `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/feedback_rule_scanner_hook_installed.md`.
2. **SECOND ACTION of Session 63: run Wednesday diocesan drip batch.** `cd /Users/stevenadkins/Code/Scout && .venv/bin/python scripts/diocesan_drip.py --execute`. 15 contacts (measured from state file), roughly 6 min (estimate) wall clock with the new jitter. Auto-picks today's date bucket from CST clock. Resumable on crash.
3. **THIRD ACTION (Thursday session): run Thursday diocesan drip batch.** Same command. 14 contacts (measured). Then `--verify` to confirm all 63 (measured) contacts landed.
4. **Passive monitoring through the week:** let Rule 20 + Rule 19 run against real traffic. If any false positive blocks a legitimate response, `touch ~/.claude/state/scout-hooks-disabled` to kill both hooks immediately, report the false positive, tune regex in `scripts/rule_scanner.py`, re-run tests, re-enable.
5. **Next plan-mode session:** Research Engine Round 1.1. Per-URL content MERGE (not dedup) as the most promising lever. All Round 1 flags currently default OFF. Plan file: `~/.claude/plans/spicy-sleeping-gadget.md` has the failed Round 1 analysis.
6. **Next plan-mode session (separate):** BUG 5 code fix in `tools/research_engine.py::_target_match_params`. Shared-city gap. Blocks the 9 pending dioceses review (Pittsburgh/OKC/Omaha contamination risk).
7. **Optional follow-ups:** F9 compliance scanner query redesign, LA archdiocese research restart, IN/OK/TN CSTA hand-curation.
8. **Deferred:** 1,245 cold_license_request + 247 winback March backlogs.

### Uncommitted state at end of Session 62

- `.DS_Store` — harmless macOS noise, as always.
- `data/diocesan_drip_state.json` — gitignored, 63-contact plan, now with 34 marked done.
- `data/diocesan_drip_audit.jsonl` — gitignored, audit log of Mon+Tue POSTs.
- No half-built code.

### Session 61 commits (9 on main)

| commit | scope |
|---|---|
| `978499b` | Research Engine Round 1 Part 0 — shared dedup fix (upgrade-on-collision helper). Level 2 Waverly check: 37/37 contacts preserved, zero regression. 7 unit tests green. |
| `bd7a562` | Research Engine Round 1 Part 1 — three feature flags (`enable_url_dedup`, `l15_step5_skip_threshold`, `log_claude_usage`). All default OFF. Module-level Claude usage capture safe across `run_in_executor`. 20 unit tests green. |
| `21d9b3b` | Research Engine Round 1 Part 2 — A/B harness (`scripts/ab_research_engine.py` + `ab_analyze.py`). Real cost from `response.usage` token counts. `--max-cost-usd` ceiling. 3 numerical gates. |
| `e62f4be` | Round 1.1 patch attempt — URL dedup keeps longest content per URL. Waverly retry still failed (22 vs 30 verified). Level 3 halted per plan's stop-on-first-failure rule. 21 unit tests green. |
| `163fc8f` | Session 61 research engine wrap doc — 9-commit summary, root-cause analysis, Round 1.1 options. |
| `fdf6920` | Diocesan drip library — 4 new functions in `tools/outreach_client.py` (`validate_prospect_inputs` + `create_prospect` + `find_prospect_by_email` + `add_prospect_to_sequence`) + new `tools/timezone_lookup.py` + new `tools/prospect_loader.py` + new `scripts/diocesan_drip.py` + new `scripts/test_diocesan_drip.py` (15 tests). 29 unit tests total green. |
| `fcd1417` | Amnesia root-cause fix — new `docs/SCOUT_CAPABILITIES.md` (~360 line inventory) + CLAUDE.md PREFLIGHT: Prospect add to sequence + Rule 17 (timezone code-enforced) + Rule 18 (no ephemeral prospect scripts) + `feedback_timezone_required_before_sequence.md`. |
| `fb941a1` | Rule 19 — never show Outreach backend IDs in chat. Translation table in `feedback_no_outreach_ids_in_chat.md`. |
| `4d8ec58` | Documented `prospects.delete` + `mailboxes.read` scope gaps in SCOUT_CAPABILITIES. |

### First half — Research Engine Round 1 (FAILED, parked)

**Plan:** `~/.claude/plans/spicy-sleeping-gadget.md` (approved Session 60).

**Level 3 Waverly A/B verdict:**

| metric | v1 baseline | v2 first-wins | v2 longest-wins |
|---|---|---|---|
| contacts total | 34 / 36 | 20 | 23 |
| contacts verified | **30 / 30** | **19** | **22** |
| cost usd | $0.80 / $0.81 | $0.41 | $0.44 |
| wall clock (s) | 334 / 329 | 171 | 179 |
| verified_quality_gate | — | **FAIL** (63%) | **FAIL** (73%) |

**Root cause:** URL dedup (either first-wins or longest-wins) collapses distinct per-query Serper snippet highlighting into one entry, losing contacts that were only visible in the lost snippets. L15 Step 5 skip at threshold=15 drops 3-5 more discovery contacts. Neither path is recoverable by a small patch. The insight: `raw_pages` is an extraction-REQUEST list, not a page list — multiple entries per URL are intentional, each carrying distinct content (snippets vs full pages). Banked as `memory/feedback_raw_pages_is_extraction_requests.md`.

**Round 1 code state:** flags default OFF. Production (the 4 `research_queue.enqueue` call sites in `agent/main.py`) unchanged. Test suite 21/21 green. Flags remain available as lab instruments for Round 1.1 experimentation without production risk.

**Round 1.1 options (fresh planning required, NOT shipped in S61):**

1. **Per-URL content MERGE** (not dedup): concatenate all distinct contents for a URL into a single Claude call. Preserves snippet text + full page. Biggest scope change. Most promising.
2. **Raise L15 Step 5 threshold to 30+**: at 30, Waverly's 30 verified still wouldn't trigger. Larger targets likely also bypass. Savings vanish.
3. **Ship only usage logging flag**: zero cost savings in Round 1, but gives measurement-grade cost data for Round 2 decisions. Honest minimum.
4. **Different cost lever entirely**: batch L9 Claude calls (5-10 pages per call instead of 1 per page). Round 2 scope but might be bringable forward.

**Session 61 A/B budget burn:** ~$4.00 of the $25/week ceiling (Level 2 Waverly ~$1.50 + two A/B runs ~$2.46). Level 3 targets 2-5 NOT executed — saved ~$8 + ~60 min by stopping on first failure.

### Second half — Diocesan drip + amnesia root-cause fix

**Plan:** `~/.claude/plans/rosy-jumping-teacup.md` (rev 2, senior-review rebuild after Steven caught a framing error in rev 1).

**Context.** The rev 1 plan framed prospect-add as "net new capability." Steven caught it: *"YOU LITERALLY HELPED ME ADD ALL THE CONTACTS TO ALL THOSE OTHER SEQUENCES YOU CREATED FOR ME THIS MONTH."* Confirmed via git log: Session 38 loaded 11 CUE sequences with prospects via inline ephemeral Python, Session 43 loaded 1,119 C4 prospects the same way. Both loads happened; the code was ephemeral and never committed. Every new session I opened `tools/outreach_client.py`, saw no `create_prospect`, and concluded "this capability doesn't exist." Same amnesia had hit Session 59 earlier with diocesan sequence copy/paste. Problem B (the amnesia itself) is a root-cause issue that required a structural fix alongside the drip.

**Library code shipped** (all in `tools/outreach_client.py`, `tools/prospect_loader.py`, `tools/timezone_lookup.py`, and `scripts/diocesan_drip.py`). The 4 new Outreach functions follow the Session 59 hardening pattern: validator + write function that calls it first + return-dict shape that never raises. Full inventory in `docs/SCOUT_CAPABILITIES.md`.

**Amnesia fix — 2 layers.** Layer 1: ephemeral scripts promoted to canonical library code (Commit `fdf6920`) with unit tests and a preflight checklist. Layer 2: `docs/SCOUT_CAPABILITIES.md` inventory + SessionStart hook in `~/.claude/settings.json` that auto-injects the file content on every Scout session start. Next session will see "here's what's already built" before Claude proposes any work.

**Diocesan drip state (pre-execution):**

- `data/diocesan_drip_state.json` holds 63 contacts assigned round-robin across 4 business days, VERIFIED first within each diocese. Per-day totals: Mon 17, Tue 17, Wed 15, Thu 14.
- **Expected 65 dropped to 63.** The 2 extras skipped: (a) the single Chicago contact (`tallen@archchicago.org`) has empty `First Name` field in the Leads tab, (b) one Philadelphia contact (last name "Ricci", `mricci@smspa.org`) has same problem. Steven's explicit call: skip both, ship 63. Both can be reclaimed later by hand-fixing first names in the sheet and re-running `--assign`.
- Exclusion list: 3 broken emails — Michael Kennedy Cincinnati Cloudflare obfuscation placeholder, both O'Brien apostrophe-local-part variants (Cincinnati).
- Mailbox = your mailbox. Owner = you. Tags on every prospect: `diocesan-drip-2026-04` + `diocesan-drip-<diocese-slug>`.

**Canary — PASSED.** Throwaway Scout Canary at `scout-canary-<ts>@codecombat.test` (IANA-reserved `.test` TLD, unresolvable) created and added to the Chicago diocesan sequence. Steven screenshot-confirmed: Step 1 (Auto email), sending in 6h, correct sequencer. Cleaned up: sequenceState DELETE succeeded (204). Prospect DELETE returned 403 — `prospects.delete` scope not granted. Steven manually deleted the orphaned prospect from Outreach UI.

**Session 61 memory files banked (3 new):**

- `feedback_raw_pages_is_extraction_requests.md` — research engine lesson (first half)
- `feedback_timezone_required_before_sequence.md` — Rule 17
- `feedback_no_outreach_ids_in_chat.md` — Rule 19 + full translation table

**Uncommitted state at end of Session 61:**

- `data/diocesan_drip_state.json` — gitignored, 63-contact plan ready for `--execute`
- `data/diocesan_drip_audit.jsonl` — will be created by first `--execute` run
- `.DS_Store` — harmless macOS noise

**Exact next step (start of Session 62):**

```bash
cd /Users/stevenadkins/Code/Scout
.venv/bin/python scripts/diocesan_drip.py --execute
```

Runs Tuesday's 17-contact batch with 5-15 min jittered sleeps. ~2.5-3 hours wall clock. State file drives which day runs via `datetime.now(ZoneInfo('America/Chicago')).date()`. Idempotent on crash (atomic state file rewrite after every POST, `find_prospect_by_email` dedup prevents double-creates). If you want Monday's caught up too, add `--force-day 2026-04-13` and run first, then run again for Tuesday.

After Tuesday's batch completes, `scripts/diocesan_drip.py --verify` reads state file and compares against live Outreach counts.

Wednesday (Session 63) and Thursday (Session 64) each run `--execute` once. After Thursday, final `--verify`.

---

### What Session 60 shipped (committed)

- **Commit `846aaed` — Schedule ID map correction.** S59 memory had schedule 1 labeled as "Hot Lead Mon-Fri" based on sequence-name clustering. S60 verified from Outreach UI screenshots that the real "Hot Lead Mon-Fri" is schedule **51**, and schedule 1 is **"Weekday Business Hours"** (legacy default, 131 of Steven's 165 sequences on it, NOT one of his 5 targeted schedules). Corrected the default allowlist in `tools/outreach_client.py::_DEFAULT_ALLOWED_SCHEDULE_IDS` from `{1, 48, 50, 52, 53}` → `{48, 50, 51, 52, 53}`. 14/14 unit tests still pass (tests only reference 52 and 19, no schedule-1 assertion). Seq 1999 "!!!2026 License Request Seq (April)" was flagged in S59 but is actually correctly configured on schedule 51 — no migration needed. Files modified: `CLAUDE.md` (Current State + Preflight + memory count), `tools/outreach_client.py`, new `scripts/s60_schedule_lookup.py`. Memory files rewritten: `feedback_outreach_schedule_id_map.md`, `feedback_outreach_delivery_schedule_required.md`. New meta-lesson memory: `feedback_schedule_map_wrong_in_s59.md`.

### What Session 60 approved (plan, implementation pending)

**Plan file:** `~/.claude/plans/spicy-sleeping-gadget.md` — Research Engine Round 1 plan, approved after 1 pressure-test pass (feature flags replacing an earlier subclass design).

**Scope of Round 1:**

- **Part 0 — Shared dedup fix.** Two silent quality bugs in `_merge_contacts` (`tools/research_engine.py:1635-1649`) and `extract_from_multiple` (`tools/contact_extractor.py:214-235`) silently drop the newer contact on name collision, losing VERIFIED emails today. Unified fix: extract shared `_merge_contact_upgrade(existing, new)` helper into `contact_extractor.py`, call from both sites. Upgrade-on-collision semantics: fill email if missing, upgrade confidence VERIFIED > LIKELY > INFERRED > UNKNOWN, fill empty title. Never drop, never downgrade.
- **Part 1 — Three feature flags on `ResearchJob.__init__`**, all defaulting to byte-for-byte v1 behavior:
  - `enable_url_dedup: bool = False` — dedupe `raw_pages` by normalized URL (lowercase + rstrip trailing slash) at the top of `_layer9_claude_extraction`, BEFORE the BUG 5 Stage 1 page filter. Catches the case where L1/L2/L11/L16/L17 all return the same staff directory URL and L9 sends it to Claude 2-3 times.
  - `l15_step5_skip_threshold: int | None = None` — when set, skip L15 Step 5 discovery when VERIFIED contact count ≥ threshold. Round 1 uses threshold=15. Steps 1-4 still run (verification + enrichment upgrades INFERRED/LIKELY → VERIFIED). Only Step 5 "find more" discovery is skipped.
  - `log_claude_usage: bool = False` — capture `response.usage.input_tokens`/`output_tokens` from every Claude call via module-level `_capture_usage_enabled` + `_captured_usage` buffer in `contact_extractor.py`. Safe across `run_in_executor` thread boundaries because module globals are shared under CPython GIL + `ResearchQueue` is explicitly serial. `try/finally` in `ResearchJob.run()` ensures `stop_usage_capture` always runs. Attaches `claude_usage` key to result dict. **This is the measurement foundation for all future round cost decisions.**
- **Part 2 — A/B test harness** (`scripts/ab_research_engine.py`, new, ~250 lines). Instantiates two `ResearchJob` objects (flags off vs flags on), runs serially with 30s delay (avoids Serper 60/min rate limit clipping), captures real per-run cost from `response.usage` token counts (not estimates), computes diff + per-target pass/fail gates (verified_quality ≥ 95%, cost ≤ 90%, wall_clock ≤ 105%), writes JSONL to `/tmp/scout_ab_results.jsonl`, enforces `--max-cost-usd` default $5 ceiling, handles exceptions without crashing. Companion `scripts/ab_analyze.py` aggregates the JSONL into a summary table.
- **Zero changes to `agent/main.py`.** The 4 existing `research_queue.enqueue` call sites (`main.py:542`, `1591`, `2480`, `2876`) stay on v1 default behavior until Round 2 after A/B validation.

**Anchoring measurement (N=20 public district jobs, real Research Log data):**
- L2 title-variations: 90% hit rate, mean 12.6 contacts, max 30 — biggest workhorse
- L1 direct-title: 75% hit rate, mean 10.4
- L3 linkedin: 75% hit rate, mean 7.7
- L14 conference: 70% hit rate, mean 3.8
- L16 Exa broad: **25% hit rate but mean 28.6 when it hits, max 58** — variance bomb
- L4, L5, L11, L12, L13, L20: all 10-35% hit rate, mean 1-5 — low-yield but kept (L4 is load-bearing for domain discovery)
- Two dedup bugs confirmed by code read: both functions drop newer contact on collision

**Architecture decision:** feature flags in v1, NOT `research_engine_v2.py` subclass. Rationale: subclass would require copying 200+ lines of `_layer15_email_verification` to change one if-statement, provides no real isolation benefit over flag gates, and makes the A/B harness harder not easier. Full rationale in the plan file and in `memory/feedback_feature_flags_not_subclass.md`.

**Expected impact:** 10-25% cost reduction `(estimate — $0.05-0.15/job URL dedup + $0.025-0.05/job L15 skip on triggered runs). Round 1 is ~$45/week at saturation vs the $25/week hard ceiling — Round 1 does NOT solve the budget problem alone, it's the foundation for Round 2 (entity cache, Claude batching, Haiku fallback) and Round 3 (parallelism, territory L0 shortcut).

**5 locked test targets (confirmed in territory_data, all cold):**
1. Cypress-Fairbanks ISD (TX, 118,470) — large
2. Cincinnati Public Schools (OH, 34,860) — medium
3. Conejo Valley USD (CA, 15,999) — medium
4. Lake Zurich CUSD 95 (IL, 5,703) — small
5. Waverly School District 145 (NE, 2,134) — small

### What Session 60 did NOT ship yet (next session work)

**Commit 1 — Part 0 dedup fix** (blocked only by context window; ready to execute):
1. Write `scripts/test_round1_unit.py` with 7 failing Part 0 tests (TDD)
2. Implement `_merge_contact_upgrade(existing: dict, new: dict) -> None` in `tools/contact_extractor.py`
3. Rewrite `extract_from_multiple` (lines 214-235) to use the helper
4. Rewrite `ResearchJob._merge_contacts` (lines 1635-1649) to import + use the helper
5. Run unit tests — must be 7/7 green
6. Level 2 integration check: stash changes, run Waverly baseline via `ResearchJob("Waverly School District 145", "NE").run()`, save result, unstash, rerun, diff. Expected: `post.contacts_verified >= pre.contacts_verified`. Two real research jobs, ~14 min wall clock, ~$1.50 real API cost.
7. Commit: `fix(research): upgrade-on-collision in shared dedup logic (recovers silently-lost VERIFIED emails)`

**Commit 2 — Part 1 feature flags** (after Commit 1 green):
1. Add 13 more unit tests to `scripts/test_round1_unit.py` (5 URL dedup, 4 L15 Step 5 skip, 4 usage logging)
2. Add 3 feature flags to `ResearchJob.__init__`
3. Add URL dedup block at top of `_layer9_claude_extraction` gated on `enable_url_dedup`
4. Add L15 Step 5 skip check gated on `l15_step5_skip_threshold`
5. Add module-level `_capture_usage_enabled` + `_captured_usage` + `start_usage_capture` / `stop_usage_capture` / `_log_usage` helpers in `contact_extractor.py`
6. Wire capture start/stop in `ResearchJob.run()` via `try/finally` gated on `log_claude_usage`
7. Add `claude_usage` key to result dict when logging enabled
8. Run all 20 unit tests — must be 20/20 green
9. Commit: `feat(research): add round 1 feature flags (url_dedup, l15_step5_skip, claude_usage_log)`

**Commit 3 — Part 2 A/B harness** (after Commit 2 green):
1. Create `scripts/ab_research_engine.py` (~250 lines)
2. Create `scripts/ab_analyze.py` (~50 lines)
3. Add `*.jsonl` to `.gitignore`
4. Smoke test against Waverly with `--max-cost-usd 2`
5. Commit: `feat(ab): research engine v1-vs-v1-with-flags A/B harness with real token logging`

**Level 3 validation run** (after Commit 3):
1. Run `.venv/bin/python scripts/ab_research_engine.py --district "<name>" --state <code>` for all 5 targets, starting with Waverly (smallest, cheapest), working up to Cypress-Fairbanks (largest)
2. Stop immediately on any gate failure
3. Aggregate via `.venv/bin/python scripts/ab_analyze.py /tmp/scout_ab_results.jsonl`
4. Expected total real-API cost for 5 A/B runs: ~$5-10
5. All 5 targets must pass all 3 gates (quality, cost, wall clock) for Round 1 to progress to Round 2 planning

### Uncommitted working state at end of S60

- `scripts/s60_test_target_lookup.py` — untracked, used to verify 5 test targets against Active Accounts + pull Research Log per-layer yields. Keep for reference, commit alongside Round 1 work.
- `scripts/s60_verify_test_targets.py` — untracked, verified 5 candidates against `territory_data` enrollment (caught Park Ridge → Lake Zurich swap). Keep for reference, commit alongside Round 1 work.
- `.DS_Store` — harmless, ignore.

### Round 2 preview (NOT Round 1 scope — deferred after Round 1 A/B validates)

1. **Entity cache** — `(normalized_district, state)` → result dict with 30-day TTL. In-memory + GitHub persistence (follows `memory/outreach_tokens.json` pattern). Biggest single cost reduction lever on repeat runs.
2. **Claude call batching in L9 (batch mode only)** — group 5-10 pages per Claude call, saves ~50% on L9 system-prompt overhead. Adds latency (batch-mode-only flag, not interactive).
3. **L15 full skip with stricter threshold** — Round 1 conservative Step 5 skip at 15. Round 2 considers full L15 skip at 25+ after data shows Steps 1-4 upgrade frequency.
4. **Haiku 4.5 fallback on high-confidence structured pages** — pages with clear staff directory table structure can extract with Haiku at ~1/3 Sonnet cost. Needs page-classifier + A/B validation.
5. **L16/L17 Exa conditional execution** — restructure phase order so L16 only fires if L9 first pass produces <15 VERIFIED. Biggest single cost amplifier today ($0.45-0.90/job indirect L9 cost when it runs).

### Round 3 preview

- Job-level parallelism (4-way concurrent `ResearchQueue` worker pool with shared token bucket)
- Territory master list L0 — persist discovered district domains so L4 becomes cache lookup on repeats
- Overnight batch scheduler (6pm-6am CST) for large-fan-out campaigns
- Tier system by enrollment (only viable after Research Log state field is fixed upstream)

### Session 60 lessons (load-bearing for next session)

- **Don't default to diocese/charter/CTE examples.** Public school districts in territory states are Scout's primary lane. S58-S60 drift happened because I reached for diocesan data reflexively — the freshest thing in memory. Banked as `feedback_scout_primary_target_is_public_districts.md` + `feedback_dont_default_to_diocese_examples.md`. Hard self-check: scan drafts for the word "diocese" before sending.
- **$25/week is the real research budget ceiling**, not the invented $50-150/week. Derived from Outreach 5k/week cap → ~100 atomic jobs/week saturation → $0.25/job max. `feedback_research_budget_25_per_week.md`.
- **Outreach 5k/week cap is user-level, not mailbox-level.** Gmail spillover breaks tracking. Recommend second Outreach seat if Steven ever exceeds. `feedback_outreach_sending_cap_5k_weekly.md`.
- **"Job" = user-facing prospecting request**, not atomic entity. One `/research all private schools in OK` command is ONE job containing 50-150 atomic entities. Progress + budget reporting happen at job level. `feedback_job_definition_user_request.md`.
- **Feature flags beat subclass for shipping variant behavior on large classes.** Subclass requires copying huge methods to override one if-statement. Flags defaulting to current behavior preserve byte-for-byte production state. `feedback_feature_flags_not_subclass.md`.
- **Steven's pressure-test ritual works.** Session 60 Round 1 plan was rebuilt from scratch after the pressure-test prompt caught: subclass architecture error, invented cost estimates, scope creep into `agent/main.py`, vague verification, floor-style success metrics. Apply the same pressure-test discipline BEFORE presenting, not after.
- **`territory_data.lookup_district_enrollment` fails on historical Research Log rows** because old writer truncated state field to "Te"/"Oh"/"Ok". Not a current bug. Blocks enrollment-based tier routing in Round 1. Fresh rows use correct abbreviations. Separate investigation, not Round 1 blocker.
- **L16 Exa broad is the variance bomb.** 25% hit rate but dominates when it hits (mean 28.6, max 58 contacts). Indirectly amplifies L9 Claude cost by 10-20 extra page extractions when it fires. Round 2 candidate for conditional execution.

---

## Session 59 archive → 4-round session: 3 rounds of broken output caught by Steven, round 4 tool hardening.

### Round-by-round narrative

**Round 1 (initial diocesan regen):** shipped the `_on_prospect_research_complete` diocesan branch in `agent/main.py` (commit `042f146`) + regenerated 6 of 7 existing diocesan sequence docs. Steven reviewed the docs and flagged 4 content problems: no campaign meeting link, "one pager" CTA repeated across every step, no `codecombat.com/schools` links, awkward phrasing ("schools school by school"). Also hard-corrected my framing: recommending manual Outreach copy/paste when Scout was built to automate that is the exact opposite of Scout's purpose.

**Round 2 (re-regen + Outreach push):** updated the diocesan branch with all 4 content fixes, regenerated all 6 sequences, pushed them to Outreach via `outreach_client.create_sequence` (commit `7c162b6`). Claimed success on HTTP 201. Steven opened the sequences in the Outreach UI and caught 3 more problems: (a) steps firing 2-3 hours apart instead of 5+ days apart — my regen script passed `interval_minutes=8640` to a wrapper that treated the value as seconds (60× too short), (b) "auto-generated via Scout sequence_builder" in the description field, visible to his manager and sales team, (c) no delivery schedule attached (sequences on "No schedule"). I had gone rogue recommending schedule 19 via name-similarity cluster inference when 19 wasn't one of Steven's 5 named schedules.

**Round 3 (patch live sequences + code fixes):** PATCHed all 6 live sequences to fix intervals, descriptions, and schedule. Refactored `tools/outreach_client.py::create_sequence` with the schedule allowlist, `interval_seconds` parameter rename, banned automation-language guards, and schedule_id required-unless-override (commits `eff3786`, `880d77b`). Started on an F1 audit and proposed retiring the intra_district scanner based on "100% REDUNDANT" findings. Steven pushed back hard: horizontal prospecting is a valid sales motion, "having a contact" ≠ "having a relationship," and my audit had conflated sibling SCHOOL ACCOUNTS with CONTACTS at the parent district — `Active Accounts` has zero contact-level columns. Category error. Also surfaced that my cost/time estimates ($200-800, ~30 hours) were fabricated — real numbers from Research Log were $135-365 and 47 hours, both directions wrong. And I had told Steven "F3 is retired" when F3 is the active RFP scanner.

**Round 4 (tool hardening — this session's biggest work):** rebuilt the prevention plan through 3 pressure-test passes. Shipped `validate_sequence_inputs` + `verify_sequence` standalone helpers in `tools/outreach_client.py` (commit `1f22991`). Refactored `create_sequence` to auto-call both. Made 8 of 12 Session 59 failure modes structurally impossible at the code boundary. 14 unit tests (`scripts/test_outreach_validator.py`) run in <1 second with zero API calls. Ran post-hardening verification on all 6 live diocesan sequences — the new verifier caught 2 real violations I had missed in rounds 1-3 ("15 minutes" in Philadelphia and Cincinnati step 3 bodies). PATCHed the two template bodies in place; re-verified clean. Ran a 5-sequence spot-check on recent Steven-owned non-diocesan sequences; all 5 have legacy findings (em/en dashes, some banned phrases, schedule 51 on seq 1999 which is NOT in the 5 named schedules) — documented but NOT fixed without Steven's sign-off.

### What's live in Outreach

| Seq ID | Diocese | Schedule | Cadence | Status |
|---|---|---|---|---|
| 2008 | Archdiocese of Philadelphia Schools | 52 (Admin Mon-Thurs Multi-Window) | 5 min / 5d / 6d / 7d / 8d | **verified clean** |
| 2009 | Archdiocese of Cincinnati Schools | 52 | 5 min / 5d / 6d / 7d / 8d | **verified clean** |
| 2010 | Archdiocese of Detroit Schools | 52 | 5 min / 5d / 6d / 7d / 8d | **verified clean** |
| 2011 | Diocese of Cleveland Schools | 52 | 5 min / 5d / 6d / 7d / 8d | **verified clean** |
| 2012 | Archdiocese of Boston Catholic Schools | 52 | 5 min / 5d / 6d / 7d / 8d | **verified clean** |
| 2013 | Archdiocese of Chicago Schools | 52 | 5 min / 5d / 6d / 7d / 8d | **verified clean** |

All 6: `owner=11` (Steven), clean description with zero automation language, meeting link (`https://hello.codecombat.com/c/steven/t/130`) hyperlinked in required steps, `codecombat.com/schools` hyperlinked in ≥2 steps, zero em dashes, zero banned phrases. Ready for Steven to activate.

### What's in the codebase

- **`tools/outreach_client.py`** — new `validate_sequence_inputs` + `verify_sequence` helpers. `create_sequence` refactored to call both automatically. Schedule allowlist via env var `OUTREACH_ALLOWED_SCHEDULE_IDS` → default `{1, 48, 50, 52, 53}`. Module constants `_BANNED_BODY_PHRASES` (16 phrases), `_BANNED_BODY_CHARS` (em/en dash + " — " pattern), `_BANNED_META_PHRASES` (14 automation terms).
- **`scripts/test_outreach_validator.py`** — 14 unit tests covering every Session 59 failure mode. Runs in <1s, zero API calls.
- **`scripts/s59_regen_diocesan_sequences.py`** — from Session 59 round 2/3, kept as reference for how to build+push a diocesan sequence via the hardened wrapper.

### What's in docs

- **`docs/SCOUT_RULES.md` Section 1 Workflow & Process** — 3 new rules: (1) Write the audit question in plain English BEFORE running code, (2) Never cite cost/time/count/percentage numbers without labeling provenance, (3) Never present a guess as a fact.
- **`CLAUDE.md`** — new Preflight section with 4 task-triggered checklists (Outreach work, Sequence content, Sheet audit, Cost/time estimate), new Rule 6 pointing at it, Current State rewritten with round 1-4 reality, Session 60 agenda.
- **`docs/SESSION_59_DIOCESAN_REVIEW.md`** — rewritten with final round 3/4 state + post-mortem. (Updated in Section 7c of this plan.)

### F1 pushback (Session 59 lesson banked)

I proposed retiring the F1 intra_district scanner based on an audit that showed "100% of all 384 pending rows have ≥1 active contact at parent district." That audit was flawed in 3 ways: (1) it conflated sibling SCHOOL ACCOUNTS with CONTACTS — Active Accounts has zero contact-level data, so "matches at parent district" counted accounts not people; (2) it ignored that "having a contact" ≠ "having a relationship" — most district-level contacts in Scout's data are stale or bought-lead quality; (3) it missed that horizontal prospecting is a valid sales motion regardless of whether Steven has parent-district contacts. Steven's exact words: "Yes, sometimes the other school websites may not have a directory or the directory may only have a search function where you have to search keywords to find old news posts where it mentions a target educator's name, email, and title, but this is the process we need to do." **F1 stays. 384 rows stay pending. The scanner is important.** Full rationale in `memory/feedback_f1_intra_district_is_important.md`.

### Research engine honest estimates (Session 59)

Real numbers from `Research Log` (27 recent jobs): avg 7.3 min/job, range 3.5-11.6 min, ~45 queries/job. Per-job cost estimated $0.35-0.95 (Serper ~$0.003/query, Exa ~$0.005/query, Brave ~$0.005/query, Claude extractions). For 384 intra_district rows serial: ~47 hours wall clock, ~$135-365 total. **This is too expensive and too slow for bulk use.** Research engine bulk-mode optimization is a Session 60 blocker for any backlog drain. Target: 10× cost reduction, 6-8× speed up via parallelism + caching + early termination + territory master list as L0. Full brief in `memory/project_research_engine_needs_cost_redesign.md`.

### Explicit Session 60 deferrals

- **Research engine bulk-mode optimization** — plan-mode session required. Blocker for all backlog drain.
- **BUG 5 shared-city filter code fix** in `tools/research_engine.py::_target_match_params` — plan-mode session.
- **9 pending dioceses approval** — blocked on BUG 5 fix or per-diocese blocklist-gated research workflow.
- **intra_district 384 rows** — stay pending. Rerun once research engine is optimized.
- **LA archdiocese research restart** with hand-seeded `lacatholicschools.org` — optional.
- **F9 compliance scanner query redesign** — optional.
- **IN/OK/TN CSTA hand-curation** — optional.
- **cold_license_request 1,245 + winback 247 stale March backlogs** — dedicated plan-mode session.

Plan file: `~/.claude/plans/lexical-swinging-pelican.md` (v3 after 2 pressure-test passes).

---

## Session 59 archive (round 1) → frame-change session, not a backlog-drain session. Planning-phase empirical probing discovered that (a) `_on_prospect_research_complete` at `agent/main.py:333-376` had `elif` branches for `upward`/`winback`/`cold`/`cold_license_request` but **no `private_school_network` branch** — every diocesan approval since Session 56 routed through the generic cold fallback and produced broken drafts (52-73 em dashes per doc, AI leading in subject lines, banned phrases, zero match on diocesan framing elements); (b) diocesan research yield was **dramatically better than CLAUDE.md Session 58 predicted** (72 verified emails across 6 archdioceses = 67% rate, with Philadelphia 87% and Cincinnati 88% delivering gold central-office Superintendents on `@archphila.org` / `@catholicaoc.org`); (c) `ResearchQueue` is explicitly single-job-at-a-time (`tools/research_engine.py:1666`) — approving 9 dioceses + 63 Tier-1 rows would take 6+ hours serial wall clock and generate 72 more unreviewed sequence docs; (d) the 384 `intra_district` pending rows are **100% redundant** against Active Accounts (every parent district already has ≥1 known contact, 7.8% have 2+). The v1 plan tried to approve all of them; v2 (after Steven's ruthless pressure test) reframed Session 59 as **value extraction** — fix the broken sequence builder, regenerate the 7 existing docs through the new branch, audit intra_district into a retire-F1 recommendation, and leave the actual backlog approvals for Session 60 once Steven has reviewed the new diocesan sequence quality.

**Next up:** Session 60 execution — (a) Steven reviews `docs/SESSION_59_DIOCESAN_REVIEW.md` to approve/iterate Philadelphia + Cincinnati as the first actually-sendable diocesan campaigns, (b) Steven decides intra_district Option C (retire F1 + bulk-skip 384), (c) approve remaining 9 pending dioceses with per-diocese blocklist-gated cleanup (7 of 9 have BUG 5 shared-city contamination risk — Pittsburgh, OKC, Tulsa, Fort Worth, Houston, Lincoln, Omaha), (d) approve the 63-row Session 58 non-diocesan Tier-1 backlog (cs_funding 7 → charter_cmo 15 → cte_center 34 → other private_school_network 7), (e) optional: BUG 5 code fix in `tools/research_engine.py:_target_match_params`, F9 query redesign, IN/OK/TN CSTA hand-curate, LA archdiocese research restart.

### Session 59 deliverables

**Priority 0 — Empirical probing in planning phase:**
- Pulled full Research Log for 6 Session 58 diocesan jobs — found 72 verified emails / 107 total leads (67% rate). Previous CLAUDE.md expected "central-office NAMES without verified emails." Completely flipped the Apollo/RocketReach decision (defer indefinitely, the existing stack is doing the job).
- Sample-inspected `Leads from Research` diocesan rows — confirmed 1 cross-contamination (`nicole.cummings@detroitk12.org` = Detroit Public Schools, not Archdiocese). BUG 5 shared-city gap. Other 70 rows are legit archdiocesan or parochial Catholic school domains.
- Verified `ResearchQueue` is explicitly single-job-at-a-time (`tools/research_engine.py:1666`): "Prevents parallel jobs from hammering Serper API." 9 dioceses × 6 min + 63 Tier-1 × 5 min = 6+ hours wall clock. Reshaped Session 59 to prioritize review bandwidth over queue throughput.
- Counted the actual queue: 1,990 pending across all strategies (not ~475 as CLAUDE.md stated). CLAUDE.md's 475 was correct for the 5 named strategies but missed 1,245 cold_license_request + 247 winback (both stale March 2026 backlogs, out of Session 59 scope).
- Read `_on_prospect_research_complete` at `agent/main.py:319-428` — discovered the missing `private_school_network` elif branch. **Highest-leverage finding of the session.** Every diocesan sequence since Session 56 had the wrong tone.

**Priority 1 — Deleted backup tab:**
- `Prospecting Queue BACKUP 2026-04-10 0010` (sheetId=793937698, 38,837 rows) deleted via `batchUpdate(deleteSheet)`. Pre-check on 3 live queue rows confirmed shape. Tab count 15 → 14. Live queue intact at 38,932 rows.

**Priority 2 — Public-district email blocklist + Detroit cleanup:**
- Resolved 9 public-district domains via Serper (Pittsburgh PS → pghschools.org, OKCPS → okcps.org, TPS → tulsaschools.org, MNPS → mnps.org, SCSK12 → scsk12.org, FWISD → fwisd.org, Houston ISD → houstonisd.org, LPS → lps.org, OPS → ops.org).
- Shipped `memory/public_district_email_blocklist.json` as a Scout runtime contamination-guard asset: 10 exact domains + 8 regex patterns (`^k12\.[a-z]{2}\.us$`, `^[a-z]+isd\.org$`, etc) + per-diocese exclusions for all 16 Catholic dioceses + whitelist of 23 known-good archdiocesan/parochial domains from Session 58 research.
- Deleted row 545 in `Leads from Research` (D. Nicole Cummings, `nicole.cummings@detroitk12.org`, Archdiocese of Detroit Schools) via `batchUpdate(deleteDimension)`. Re-verified row was the correct target before deletion. Diocesan row count 71 → 70. Zero `detroitk12.org` references remaining.
- Wrote `memory/project_bug5_shared_city_gap.md` in Claude auto-memory documenting the 7-of-9 at-risk pending dioceses and the runtime blocklist as the Session 59 patch.

**Priority 3 — Sequence builder diocesan branch (commit `042f146`):**
- Added `_is_diocesan` token match (`"archdiocese" in district_name.lower() or "diocese" in district_name.lower()`) in `_on_prospect_research_complete` around the elif chain starting at `agent/main.py:334`.
- Added `strategy_labels["private_school_network"] = "Private School Network"` and two new elif branches:
  - Diocesan: target_role → "Superintendent of Catholic Schools", campaign_name → "<diocese> — Diocesan Central Office Outreach", extra_context inlines the full tone rules (central-office audience definition, CS/safe-AI framing, 3-CTA pattern, structure/length constraints, banned-phrase list, merge-field requirements). Rules sourced from `feedback_bond_trigger_outreach_tone.md` + `feedback_sequence_copy_rules.md` + `feedback_sequence_iteration_learnings.md`.
  - Non-diocesan private_school_network: network-level framing for Cristo Rey, independent Catholic academies, etc.
- Additive change — `strategy == "private_school_network"` previously fell through with empty `extra_context`. Cannot regress any other strategy.
- **Local test against Philadelphia data passed all tone checks:** 0 banned phrases, 0 em dashes, 1 verified case study reference (Bobby Duke MS), all 3 CTA variants present, "throw our hat in early" framing, parochial / diocesan framing throughout. Step 1 was ~100 words vs the 80-word target — minor iteration target but not blocking.

**Priority 4 — Regenerated 6 of 7 existing diocesan sequence docs (Session 59 Section 5):**
- Confirmed Google Docs/Drive APIs were disabled for the service account project 878527098006 — fell back to public `/export?format=txt` URL (works for any doc accessible to anyone with the link). Pulled all 7 existing docs as plain text.
- Programmatic scoring of the 7 originals: **every one scored 0/9 on diocesan tone match**, 52-73 em dashes each, AI in subject lines, 4 docs had banned phrases ("I'd love to", "quick call"). Confirmed all 7 were unsendable as-is.
- Ran `scripts/s59_regen_diocesan_sequences.py` — regenerated Philadelphia, Cincinnati, Detroit, Cleveland, Boston, Chicago through the new branch. Per-regen quality:
  - Philadelphia: 63 words Step 1 ✓, 0 em dashes ✓, 0 banned ✓
  - Cleveland: 69 words Step 1 ✓, 0 em dashes ✓, 0 banned ✓
  - Boston: 56 words Step 1 ✓, 0 em dashes ✓, 0 banned ✓
  - Chicago: 57 words Step 1 ✓, 0 em dashes ✓, 0 banned ✓
  - Detroit: 79 words Step 1 ✓, 0 em dashes ✓ (final exported text), 0 banned ✓
  - Cincinnati: **98 words Step 1 (over 80 target)**, 0 em dashes ✓, 0 banned ✓
- Wrote 6 new Google Docs via GAS bridge `write_sequence_to_doc`, updated Prospecting Queue `Sequence Doc URL` column for all 6 rows via `batchUpdate(values)`.
- **LA abandoned** — 2 leads from 1 parochial school (`hssala.org`) is not an actionable central-office campaign. Original broken doc left in place as a placeholder. Session 60 candidate: hand-seed research with `lacatholicschools.org`.
- Wrote `docs/SESSION_59_DIOCESAN_REVIEW.md` summarizing the 7 verdicts, new Doc URLs, quality table, what to watch for in Steven's review.

**Priority 5 — intra_district 384-row desk audit:**
- Pulled all 384 `intra_district` pending rows. Stratified sample: 6 high (780-785, all), 7 mid (765-775), 6 low (750-764) = 19 rows with random seed 42.
- For each sample row: exact-matched `Parent District` against `Active Accounts` via `csv_importer.get_active_accounts()`; fuzzy-matched at threshold 0.75 on miss.
- **Sample hit rate: 19/19 (100%) REDUNDANT** — every sampled sibling school had ≥1 known contact at its parent district (LAUSD had 6, Corona-Norco 4, ABC Unified 2, etc.).
- Full-queue check across all 384: **384/384 (100%) with ≥1 active contact at parent**, 7.8% have 2+. No cohort of rows would produce net-new marketing surface.
- Root cause: F1 is designed to find sibling schools inside districts that ARE Active Accounts. By definition, every parent district has a pre-existing relationship. Research mostly rediscovers the parent's known contacts.
- Wrote `docs/SESSION_59_INTRA_DISTRICT_AUDIT.md` with the methodology, sample table, full-queue stats, and three options:
  - **A (approve all 384):** ~$400 research + 384 docs, low marginal value — NOT recommended
  - **B (approve top 50):** smaller but same structural problem — NOT recommended
  - **C (retire F1 + bulk-skip 384):** RECOMMENDED, $0, clears 20% of pending backlog, shifts sibling-school expansion to warm channels (upward_auto, signals, proximity_engine)
- Also noted a future-session alternative: replace F1 with a "referral target" talking-point generator using known parent-district contacts as warm vectors instead of cold research.

**Commits this session (expected ~2):**
1. `042f146` feat(sequences): add diocesan branch to _on_prospect_research_complete + memory/public_district_email_blocklist.json
2. (incoming) docs(session-59): SESSION_59_DIOCESAN_REVIEW + SESSION_59_INTRA_DISTRICT_AUDIT + CLAUDE.md + SCOUT_PLAN.md + SCOUT_HISTORY.md + MEMORY.md

### Session 59 v1 vs v2 plan (why it was rewritten)

The v1 plan focused on approving more prospects and cleaning the backlog — the frame CLAUDE.md Session 58 handoff set. Steven's ruthless pressure-test prompt caught the frame error. The v2 rewrite's most important changes:

1. v1 missed the `sequence_builder` diocesan branch gap entirely. v2 makes fixing it the primary work.
2. v1 tried to approve 9 dioceses + 72 Tier-1 rows. After verifying `ResearchQueue` is serial, the math showed 6+ hours of wall clock and 72+ new sequence docs for Steven to review. v2 caps diocesan approvals at 3 (stretch) and Tier-1 at 7 cs_funding rows (stretch) — bounded by review bandwidth.
3. v1 buried the 7 existing diocesan docs under a caveat. v2 made triage of those 7 docs a primary section.
4. v1's intra_district probe was a 3-row live approval probe. v2 replaced with a 20-row desk audit against Active Accounts — 30 min, not $400.
5. v1 ignored shared-city contamination risk on 7 of 9 pending dioceses. v2 built the blocklist as a reusable asset.
6. v1 was vague on cost estimates and stop conditions. v2 had dollar ranges and 2-iteration caps per section.
7. v1's verification was aspirational. v2 was specific (file paths, row counts, tab names).

Net effect: v2 shipped materially less motion (0 new approvals vs 9 + 63) but materially more value (broken pipeline gap fixed + 6 docs made sendable + reusable blocklist + clear intra_district retire recommendation).

Plan file: `~/.claude/plans/lexical-swinging-pelican.md` (v2).

---

---

## Session 58 archive → comprehensive knockdown. **Priorities 1–4 all complete** with 7 commits shipped. Stage 6: F6 charter CMOs (26 queued across KIPP/IDEA/Harmony/etc.) + F7 CTE centers (41 queued, OK tech centers dominant). Stage 7: F9 `/signal_compliance` handler wired (Telegram dispatch now works for CA/IL/MA pilot — CA scan ran end-to-end, 0 signals this time as scanner surfaced wrong PDFs; handler works, scanner query redesign is a separate future bug). Stage 8: F1 `suggest_intra_district_expansion` got per-parent-district CSTA enrichment (inline `_calculate_priority + csta_bonus`, lazy import to avoid circular). Priority 2: **6 of 16 top-territory archdioceses approved** (Boston, Philadelphia, Cincinnati, LA, Cleveland, Detroit) + research running via BUG 4 playbook — stopped at Option A (accept high-value 6 without hunting the deeper 10). Priority 3: **`build_csta_enrichment` helper** added to signal_processor.py, wired to F4/F6/F7/F8 (lazy imports for the three prospector modules). F1/F2 kept inline. Priority 4: **CSTA roster rewrite** — per-state Haiku extraction + whitelist-filtered national bucket + regional subdomain mapping (goldengate/pittsburgh/dallasfortworth/etc.) + district resolver pass (Serper + Haiku reverse-lookup with confidence gating) + merge-with-previous dedup (Haiku is nondeterministic across runs, additive merge prevents per-run regression). **Roster: 39/14 matchable → 77/41 matchable (+193%).** Territory coverage: from 4 states → 10 states. IN/OK/TN still at zero (chapter subdomains exist but pages list no board — hand-curation work for future session). Also fixed a latent bug that blocked all this drip work: `/prospect_approve` and `/prospect_skip` didn't handle `all` despite Scout's own output telling users to type it. Also docs: CLAUDE.md trimmed 41.8K → 12.5K by extracting full rules to new `docs/SCOUT_RULES.md` with grep-audit verification across 103 keywords (zero info loss). Also committed in session wrap: `scripts/scout_session.sh` updated to pass `--effort high` to the `claude` wrapper (works around Opus 4.6 medium-effort regression, takes effect on next `scout` launch).

**Next up:** Session 59 cleanup — (a) delete `Prospecting Queue BACKUP 2026-04-10 0010` tab, (b) drip-approve the backlog (8 F4 Session 57 prospects + 67 Stage 6 prospects + the remaining 10 dioceses if interested), (c) validate BUG 4 yield on the 6 approved dioceses (check Leads from Research tab in ~15-30 min after session start for research completion), (d) optional: hand-curate IN/OK/TN CSTA board members for +15 roster matches (see `memory/project_csta_roster_hand_curation_gaps.md`), (e) F9 scanner quality redesign — separate plan-mode session, same shape as BUG 1 Session 57 (Serper PDF discovery query redesign, empirical probe first).

### Session 58 deliverables

**Priority 1 — Session 52 Stages 6-8 carryover:**
- **Stage 6** — F6 `/prospect_charter_cmos` queued **26 of 43 CMOs** (KIPP Texas 57 schools, KIPP SoCal, KIPP TN/MA/PA, IDEA Public Schools 135 schools, Harmony 60 schools, Aspire, Uplift, ResponsiveEd, etc.). F7 `/prospect_cte_centers` queued **41 of 79 candidates** (OK tech centers dominant — Autry, Caddo Kiowa, Canadian Valley, Central, Chisholm Trail, Eastern OK County, etc.). Both via Telethon bridge, completed in ~80s each.
- **Stage 7** — F9 compliance scanner had no Telegram dispatch path. Added `/signal_compliance <state>` handler in `agent/main.py` (commit `c947681`) cloning F7 pattern. Pilot states surfaced via `compliance_gap_scanner.PILOT_STATES` (CA/IL/MA). Live CA pilot scan ran end-to-end — 4 PDFs processed, 0 HIGH-confidence non-compliant districts, 0 signals written. **Handler works; scanner quality (Serper PDF discovery surfacing wrong doc types like "Faculty Qualifications Minimum Standards") is a pre-existing issue, not regression. F9 query redesign is a separate future session, same shape as BUG 1 Session 57.**
- **Stage 8** — F1 `suggest_intra_district_expansion` got per-parent-district CSTA enrichment (commit `e52ce25`). F1 writes rows via `_write_rows` directly (not `add_district` like F2), so wire-in is inline: `priority = _calculate_priority("intra_district", 0, 0, cand["enrollment"]) + csta_bonus`. One CSTA lookup per parent district (not per sibling candidate), lazy import to avoid circular. 384 existing pending intra_district rows are NOT retroactively enriched — "drip" is Steven's approval cadence via `/prospect_approve all` on displayed batches, no code needed. Retrofit script is future work if wanted.

**Priority 2 — Diocesan approval drip:**
- Started paging `/prospect` batches. Discovered `/prospect_approve all` and `/prospect_skip all` didn't handle the `all` keyword despite Scout's own output at `main.py:2532` telling users to type `/prospect_approve all`. Latent bug since Session 49. Fixed both handlers (commit `69a3e9c`) — 6-line diff supporting `args.lower() == "all"` → `range(1, len(_last_prospect_batch)+1)`.
- After fix, drip loop found diocesan prospects at round 3 position 5 (mixed batches with F4 funding + F6 CMOs + F1 LIC REQ at higher priority tiers). Wrote a smart per-round parser that approves only diocesan indices and skips the rest, continuing until 4 empty rounds consecutive.
- **6 of 16 approved** (Steven chose Option A stop — accept the 6 biggest territory dioceses without hunting the deeper 10): Archdiocese of Boston Catholic Schools (MA), Archdiocese of Philadelphia Schools (PA), Archdiocese of Cincinnati Schools (OH), Archdiocese of Los Angeles Schools (CA), Diocese of Cleveland Schools (OH), Archdiocese of Detroit Schools (MI). Research is running on all 6 via BUG 4 diocesan playbook (15-30 min total). Validate output in Leads from Research tab at Session 59 start.
- Remaining 10 dioceses still in queue at `pending` status. Can be drip-approved in a future session if wanted.

**Priority 3 — Extend CSTA enrichment to F4/F6/F7/F8:**
- Added `build_csta_enrichment(district, state, base_notes) -> (enriched_notes, priority_bonus)` helper in `tools/signal_processor.py` next to `enrich_with_csta`. Returns `(base_notes, 0)` on miss — safe fallback. Prepends CSTA note, adds +50 priority bonus.
- **F4 cs_funding_recipient** wired in same file (no import needed). Previous inline F2 pattern at line 3950+ was not changed (already works).
- **F6 charter_cmo** (`tools/charter_prospector.py`) + **F7 cte_center** (`tools/cte_prospector.py`) + **F8 private_school_network** (`tools/private_schools.py`) all wired via lazy import `from tools.signal_processor import build_csta_enrichment`.
- **F1 and F2 kept inline** — F1 was wired in Session 58 Priority 1 Stage 8 before the helper existed, F2 was wired in Session 57. Both work. Refactoring to use the helper is optional Session 59+ cleanup if the pattern ever needs a 3rd change.
- Shipped as commit `3ea1be1`.

**Priority 4 — Grow CSTA roster:**
- **Baseline: 39 entries / 14 matchable across 4 territory states (CA/PA/OH/TX).**
- Empirical probes revealed two root causes:
  - **Saturation:** 610K-char mixed-topic corpus caused Haiku to silently drop minority state chapter content in favor of louder national CSTA content. Focused 22K-char corpus on MI/NE/MA home pages alone extracted 14 board members perfectly.
  - **Missing regional subdomain mapping:** CA/PA/TX don't have state-level `{state}.csteachers.org` subdomains (they DNS-fail). They use regional chapters only (`goldengate`, `greaterlosangeles`, `siliconvalley`, `pittsburgh`, `philly`, `dallasfortworth`, etc.). Current fetcher didn't map these to their parent state during bucketing.
- **Rewrite of `scripts/fetch_csta_roster.py` (commit `529a919`):**
  - Per-state Haiku extraction with state code injected into the prompt.
  - `REGIONAL_SUBDOMAIN_TO_STATE` map (18 regional subdomains → parent state).
  - National bucket URL whitelist (`/team/`, `/volunteer-spotlight`, `/csta-board-corner`, `/meet-*`, `/award-winners`, community digestviewer) — filters out PD/calendar/jobs/schoolsofed noise from 84 URLs down to 23.
  - National corpus capped at 150K chars to prevent Haiku token overflow.
  - Removed DNS-broken explicit seed URLs (`california.csteachers.org`, `pennsylvania.csteachers.org`, `texas.csteachers.org`) — replaced with regional subdomains.
  - CSTA community digest URL added as explicit seed (source of ~30 baseline entries, was being discovered intermittently via Serper).
  - **District resolver pass** — for territory-state entries with empty district after extraction, runs `"{name}" "computer science" teacher {state_name}` Serper query + Haiku reverse-lookup with confidence gating (only `high`/`medium` updates). Resolved ~50% of attempts.
  - **Merge-with-previous dedup** — loads existing roster, preserves any entries that don't appear in current run. Haiku is nondeterministic across runs (confirmed — three consecutive temp=0 runs produced different subsets). Roster is now additive: every refresh grows yield, never shrinks.
- **Ran 3 times to saturate. Final: 77 entries / 41 matchable (+193%).** Territory coverage: CA=9, CT=1, IL=2, MA=6, MI=2, NE=7, NV=3, OH=3, PA=2, TX=2. IN/OK/TN still at 0 — chapter pages exist but don't list boards; requires hand-curation (see `memory/project_csta_roster_hand_curation_gaps.md`).
- Cost per run: ~$0.40 (Serper + Haiku), up from ~$0.10 for the single-call version. Still cheap.

**Plus: docs restructure (Priority 0, done at session start):**
- CLAUDE.md was at 41,817 chars, over the 40K performance ceiling. Trimmed to **12,543 chars (70% reduction)** by extracting the full 80-rule `## CRITICAL RULES` section to new `docs/SCOUT_RULES.md` organized by 13 topic sections + Session 55/57 lesson appendices.
- Moved `### Session transcript capture` to `docs/SCOUT_REFERENCE.md` (matches its "extracted static reference" framing).
- Deleted sections duplicated in `SCOUT_PLAN.md` (Completed features, Email Reply Drafting) or `memory/*.md` (Outreach.io API, Session 55/56 lessons).
- **Zero information loss verified via grep audit** across 103 distinctive keywords — every rule and fact from the original resolves somewhere in the trimmed tree.
- Shipped as commit `185a3f2`.

**Commits this session (7 total):**
1. `185a3f2` docs: trim CLAUDE.md + extract SCOUT_RULES.md
2. `c947681` feat(f9): add /signal_compliance handler
3. `e52ce25` feat(f1): F1 CSTA enrichment wire-in
4. `3ea1be1` feat: F4/F6/F7/F8 CSTA via build_csta_enrichment helper
5. `69a3e9c` fix: support 'all' in /prospect_approve and /prospect_skip
6. `529a919` feat(csta): fetcher rewrite with per-state + resolver + merge
7. (end-of-session commit incoming with plan/history updates)
Plus uncommitted local-only: `scripts/scout_session.sh` `--effort high` flag.

---

### Session 56 deliverables

**Priority 0 — historical contamination cleanup:**
- Ran `scripts/audit_leads_cross_contamination.py` to dump all 23 flagged rows
- Verified every flagged domain via HTTP title fetch + Serper confirmation (fisdk12.net = Friendswood real domain, sbcusd.com = SBCUSD real, dsusd.us = DSUSD real, etc.)
- Identified 11 real contamination rows (4 more than Session 55's handoff list) and 12 abbreviation false positives
- Built a reassignment script: appended 10 corrected rows with the right District Name + State, then deleted the 11 originals in reverse-row order
- Post-cleanup audit: 482 rows, zero real contamination remaining (15 flagged are all known false positives + 2 new ones from my own reassignment that the audit helper's abbreviation gap can't distinguish)

**Priority 1 — BUG 4 diocesan research playbook:**
- Explored research engine integration points via Explore agent — identified L4 domain rejection, hardcoded public-district queries in L1/L2/L3/L4-site/L11, BUG 5 filter collision on shared city names, and L12 diocesan-board mismatch as four simultaneous root causes
- Verified all 16 Catholic diocesan domains via Serper top-rank + HTTP root fetch + title confirmation. Fixed 2 weak hits (OKC `archokc.org`, Galveston-Houston `archgh.org`) on re-query
- Empirically verified the L6 dead-weight hypothesis: Archdiocese of Chicago runs on Liferay + React, BeautifulSoup sees 49KB of JS module markers (`contacts-web@5.0.63`) and no text. Confirmed Serper's crawler sees the rendered content (Greg Richmond, Donna Woodard from `schools.archchicago.org/meet-our-team`) and `_add_raw_from_serper` pushes those snippets into `raw_pages` for L9 Claude extraction
- Wrote plan v1, self-critiqued, ran Steven's ruthless pressure test protocol, rewrote v3 from scratch with the foundation verification baked in — dropped `DIOCESAN_CENTRAL_PATHS` entirely (waste on React sites), added L11 diocesan queries and L12 skip that v1/v2 missed, added name canonicalization helper for robust lookup
- Shipped commits A+B+C in one push (`06f8386`):
  - `tools/private_schools.py`: domain field on 16 diocesan entries, `_canonical_diocesan_key` helper, derived `DIOCESAN_DOMAIN_MAP`
  - `tools/research_engine.py`: `ENABLE_DIOCESAN_PLAYBOOK` kill switch, `DIOCESAN_PRIORITY_TITLES` + L2/L3/L4-site/L11 query template constants, `ResearchJob.__init__` new kwargs + pre-seed, `_base_domain` static helper, `_target_match_params` instance helper (replaces 4 inline target_hint computations in Stage 1 page filter + Stage 2 contact filter + L10 email check + L10 source_url check), L1/L2/L3/L4/L11/L12 diocesan branches, `ResearchQueue.enqueue` canonicalized name lookup + kwarg forwarding to worker
  - Zero `agent/main.py` changes — all 5 existing enqueue call sites (main.py:443, 1492, 2378, 2771, enqueue_batch) auto-pick-up the playbook
- 8-check local pre-flight passed
- Live smoke test on Archdiocese of Chicago via Telethon: research completed 3m 27s, `Cross-Contam Dropped: 28`, L12 correctly absent from layers_used, L4 pre-seed log line confirmed, 0 hard contamination. Pass-criterion of ≥3 @archchicago.org emails was NOT met (still just Allen) because diocesan sites don't publish emails — but real central-office NAMES were extracted from the diocesan-tuned Serper queries
- Cleaned up 25 stale No Email tab rows from Session 53's pre-playbook run (21 confirmed cps.edu/cs4allcps Chicago Public Schools leaks + 4 uncertain LinkedIn/ICE-conference sources that matched the contamination pattern). 11 clean Archdiocese rows remain
- Queued 23 private school networks via `/prospect_private_networks` (Chicago already in queue as draft → deduped). 16 Catholic dioceses are now pending in the Prospecting Queue, will auto-activate the playbook on `/prospect_approve`

**Lessons banked (memory):**
- `feedback_plans_are_one_shot.md` — Steven explicitly rejected my v1 plan's framing that treated his pressure test as an expected refinement round. Every plan is a one-shot; self-pressure-test hard before shipping. Saved under "Critical" in MEMORY.md index.
- `reference_serper_snippets_as_raw_pages.md` — Documented the `_add_raw_from_serper` mechanism so future research-engine work on JS-rendered sites doesn't waste effort on L6 seed URLs. Saved under "Reference" in MEMORY.md index.

### Session 55 deliverables

### Session 55 deliverables

**Priority 0 — BUG 3 Phase 6 sentinel close-out:**
- Pulled Railway logs for the 12:45 UTC scheduled scan window — discovered F2 is NOT in the daily scheduled scan (only `/signal_competitors` manual trigger). Session 54's "scheduled 7:45 AM CDT" assumption was wrong.
- Built Telethon bridge: `scripts/telethon_auth.py`, `scripts/tg_send.py`, `scripts/tg_recent.py`. One-time phone auth completed. Session file at `.telethon_session` (gitignored).
- Fired `/prospect_add ZZZ_SESSION55_SENTINEL_DELETEME, TX` via Telethon through live Railway bot. Diagnostic log captured:
  ```
  [BUG3_DIAG] _write_rows row len=20 first3=['TX','ZZZ_SESSION55_SENTINEL_DELETEME',''] pos_of_strategy=[8]
  updatedRange='Prospecting Queue'!A1960:T1960 updatedRows=1 updatedCells=20
  ```
  Canonical 20-col write via normal `add_district → _write_rows` path. BUG 3 confirmed dead.
- Reverted commit `68622aa` via `9b51a67` → pushed `0061aed`.
- Deleted 5 ZZZ sentinel rows (1956-1960).
- Committed Telethon infrastructure as `746e1e7`.

**Priority 1 — BUG 5 two-stage cross-district contamination filter:**
- Entered plan mode. Wrote v1, self-pressure-tested, wrote v2, Steven ran the 7-step ruthless pressure-test prompt, wrote v3 from scratch. Biggest architectural shift across passes: filter at `raw_pages` boundary BEFORE Claude extraction, not after (cheaper AND more effective).
- **Phase 0 oracle construction:** `scripts/bug5_phase0_scan.py` built `bug5_oracle_archdiocese.json` (3 rows, 2 known-bad marked) and `bug5_oracle_clean_sample.json` (20 rows across 9 districts). Both gitignored.
- **Phase 1 dry-run hard gate:** `scripts/bug5_dryrun.py` validates matching helpers against both oracles. 23/23 rows classify correctly before any live code ships.
- **Phase 2 — 6 commits landed on main:**
  - `6ffa1b2` Commit A: `ENABLE_RESEARCH_CONTAM_FILTER` kill switch + 4 shared matching helpers (`_district_name_hint`, `_is_school_host`, `_host_matches_target`, `_email_domain_matches_target`) + 3 counters
  - `552240f` Commit B: `_filter_raw_pages_by_domain()` — Stage 1 page filter, called at start of `_layer9_claude_extraction`. Drops pages whose host is a different school BEFORE Claude extraction.
  - `148aca6` Commit C: `_filter_contacts_by_domain()` — Stage 2 contact filter, called after `_merge_contacts`. Strengthened L10 with source_url hostname branch + rewrote L10 email check to use new helpers (old `parts[0]` domain parsing missed real school domains).
  - `4bdfcfc` Commit D: `sheets_writer.log_research_job()` extended with `cross_contam_dropped` kwarg + new "Cross-Contam Dropped" column
  - `22dc28b` Commit E: `agent/main.py` `_on_research_complete` one-line wiring
  - `da46dfa` fix commit: L15 `_merge_contacts` sites now call `_filter_contacts_by_domain` so L15 additions go through Stage 2. `sheets_writer._ensure_headers` now auto-migrates headers when current is a prefix of expected (the Session 55 original assumption "`_ensure_tab` overwrites header on every call" was wrong for the log tab).
- **Phase 3 live smoke test on Lackland ISD (via Telethon):** Research completed in 7 min. Production logs confirmed `L9 page filter: 9/234 pages dropped as cross-district (target=lacklandisd.net)` + `Migrating header for tab Research Log: 8 → 9 cols`. Research Log now shows `Cross-Contam Dropped: 9`. All 25 new Lackland rows fingerprint as `clean_both` or `clean_email`. 27 total contacts vs 31 from the broken-credits run — filter caught 4 that previously leaked through.
- **Phase 4 historical audit:** `scripts/audit_leads_cross_contamination.py` fingerprinted all 483 rows, gated by both oracles. Results: 175 `clean_both` + 271 `clean_email` + 4 `clean_source` + 1 `generic` + 9 `ambiguous` + 1 `source_mismatch` + 11 `email_mismatch` + 11 `both_mismatch` = 95% clean / 4.8% flagged. Google Doc report: https://docs.google.com/document/d/1TFle1jiyEiFqU_hv-rxIxsCf-WxXXDRoRaKW2A6MEfA/edit
- Committed audit + supporting scripts as `b809198`.

**Priority 0 infrastructure wins:**
- **Telethon bridge** — Claude Code can now drive Scout Telegram end-to-end. `tg_send.py`, `tg_recent.py` documented in `memory/reference_telethon_bridge.md`.
- **Screenshot capability** — verified `screencapture -x` + Read tool image handling. Terminal permission granted. Documented in `memory/reference_screenshot_capability.md`.
- **Railway log API pattern** — dialed in, using deployment-ID scoping + DateTime filter + keyword filter.

### Historical contamination review items for Steven (Phase 4 audit)

**Real contamination worth manual deletion/correction** (11 + 11 + 1 flagged, ~half false positives from abbreviation mismatches):
- **Archdiocese of Chicago** rows 458, 459 — original Session 53 finding (ROWVA + CHSD218)
- **Epic Charter School** rows 216, 217 — staff at Collinsville + Spiro (unrelated OK districts)
- **Columbus City Schools** row 333 — cisenhour@wscloud.org from Worthington k12.oh.us
- **Irving STEAM Magnet** — 2 flagged rows, need inspection
- **Friendswood ISD** row 15 — possibly real, needs check

**False positives to ignore** (audit limitation, not live-filter behavior):
- Los Angeles Unified rows (9 flagged) — all @lausd.net, legitimately LA Unified staff. Audit can't match "losangelesunified" to "lausd" abbreviation. LIVE filter handles correctly via L4-discovered `district_domain = "lausd.net"`.
- Desert Sands Unified row 212 — @dsusd.us, same abbreviation issue.

Manual cleanup is out of scope for the automated fix per plan; Steven reviews and deletes/keeps at his discretion.

### What's still in-progress / unresolved after Session 55

- **BUG 4 (F8 diocesan research playbook)** — Priority 2 next. `memory/project_f8_diocesan_research_playbook.md`. L1-L8 have no path for multi-school central-office networks. Don't unblock the other 23 F8 networks.
- **BUG 1 (F4 funding scanner)** — Priority 3. `memory/project_f4_funding_scanner_broken.md`. Pre-existing since Session 49. Kill switch off. Needs query redesign with site filters.
- **BUG 2 (F5 CSTA scanner)** — Priority 4. `memory/project_f5_csta_scanner_low_yield.md`. Kill switch off. Strategic question first: standalone vs F2-enrichment.
- **Session 52 carryover Stages 6-8** — blocked pending bug cleanup. Charter CMOs + CTE centers (Stage 6), F9 compliance CA pilot (Stage 7, Signals-only), F1 backlog drip (Stage 8 — 384 pending intra_district rows that are now readable post-Session-54 repair).

### Session 54 deliverables (BUG 3 Fix Sprint)

**Shipped (7 commits pushed to main):**
- **Commit `7a9540f`:** Phase 0 kill switches — `ENABLE_COMPETITOR_SCAN=False`, `ENABLE_PRIVATE_SCHOOL_DISCOVERY=False` (stop-the-bleed before investigation).
- **Commit `68622aa`:** Phase 1f diagnostic — temporary `_write_rows` logging that captures row payload, strategy position, caller stack trace, and Sheets API `updatedRange` response. Still active — will capture evidence on next production write.
- **Commit `5990d8a`:** Phase 2-3 diagnostic scripts + repair script. 9 files including `scripts/repair_scrambled_queue_rows.py` (strategy-dispatch readers per scramble template, dry-run default, --apply gated).
- **Commit `a54bc8c`:** Phase 4 district_prospector.py writer fixes. 4 callers (`discover_districts`, `suggest_upward_targets`, `suggest_closed_lost_targets`, `suggest_cold_license_requests`) now write 20-element rows with the Signal ID slot. Also fixed `_update_status` range A:S → A:T (latent Notes-truncation) and extended `_KNOWN_STRATEGIES` in both the module-level constant and `migrate_prospect_columns`.
- **Commit `5ebfaea`:** Phase 4 proximity_engine.py — `add_proximity_prospects` now writes 20 elements.
- **Commit `8b59ceb`:** Phase 6 F2 re-enabled (`ENABLE_COMPETITOR_SCAN=True`).
- **Queue repair applied** via `python3 scripts/repair_scrambled_queue_rows.py --apply`. Backup: `Prospecting Queue BACKUP 2026-04-10 0010`. Post-repair audit: 1958/1958 rows canonical.

**Investigation findings (captured in updated `memory/project_f2_column_layout_corruption.md`):**
- 1952 of 1954 data rows were scrambled; only Pittsburgh PS + Archdiocese were canonical before Session 54.
- Root cause: **partially identified.** The 4 district_prospector writers + 1 proximity_engine writer all built 19-element rows (missing the Signal ID slot added by commit `33e34f6`). This explains most of the historical damage.
- **But NOT the F2 Lackland rows from 00:51 UTC.** F2 calls `add_district` which correctly builds a 20-element row. Four independent sentinel tests produced CANONICAL rows from the same checkout: (1) local Python, (2) `railway run` with Railway env vars, (3) `railway ssh` inside the container, (4) via `loop.run_in_executor`. Only the long-running Scout bot process produces scrambled rows. Diagnostic logging in `_write_rows` (commit `68622aa`) will capture evidence on the next scheduled F2 run.

**7 exit criteria verified:**
1. ✅ Zero non-canonical rows after repair (verified via fingerprint audit rerun)
2. ✅ All 8 F2 rows from 00:51 UTC visible with Status=pending
3. ⏳ Manual F2 sentinel test — waiting for next scheduled 7:45 AM CDT run
4. ✅ Backup tab exists
5. ✅ Pittsburgh PS + Archdiocese untouched
6. ✅ Repair script committed with recovery docstring
7. ✅ All writer fixes committed (one per file)

**Leftover cleanup items:**
- 4 sentinel rows (`ZZZ_SENTINEL_*`, `ZZZ_PHASE1*`) at rows 1956-1959 — canonical, harmless clutter, delete via `/cleanup_queue` or manually.
- Backup tab `Prospecting Queue BACKUP 2026-04-10 0010` — safe to keep indefinitely; delete only after confirming repaired queue looks correct.
- Phase 1f diagnostic logging in `_write_rows` — revert after next F2 run confirms outcome.

### Session 54 starts with → Session 55 starts with

**Next priority: BUG 5 — Research cross-contamination** (Priority 2 in sprint order). See `memory/project_research_cross_contamination.md`. Two steps:
1. **Audit script** — iterate "Leads from Research" tab rows, flag any where the email domain doesn't match the canonical site of `District Name`. Report scope (expected: dozens of misattributions across 20 completed research jobs).
2. **Fix** — post-extraction validation layer in `tools/research_engine.py` between L9 Claude-extract and L10 dedup-score. Drop or re-attribute contacts whose email domain doesn't match the research target's canonical domain.

**Then in order:** BUG 4 (F8 diocesan playbook) → BUG 1 (F4 query redesign) → BUG 2 (F5 strategic decision) → Session 52 Stages 6-8 carryover.

**Rules for Session 55:** Same as Session 54 — enter plan mode before any non-trivial build, ruthless pressure-test pass on the plan, verify before asking, commit one per feature, diagnostic logging should survive the fix so we catch the next ghost writer.

### Session 53 deliverables (Fire Drill Audit)

**The 1 fix that shipped:**
- **Commit `7c345a07`: F2 max_tokens 3000→8000 + codefence parser hardening.** Root cause diagnosed via local IL diagnostic (CodeHS, 30 articles → 15 HIGH board_adoption signals from real BoardDocs PDFs). Fix proven end-to-end on Railway — Telegram output went from "0 raw extracted" to "17 raw, 12 signals, 8 auto-queued". **However see BUG 3 below — the 8 auto-queued rows have their own problem.**

**The 5 silent-failure bugs discovered (all parked for Session 54):**

1. **BUG 1: F4 funding scanner queries wrong corpus** (`memory/project_f4_funding_scanner_broken.md`). Pre-existing since Session 49. Queries pull higher-ed, student scholarships, teacher awards instead of K-12 LEA recipient announcements. 456 articles → 0 extractions. Not a prompt fix — queries need site filters.
2. **BUG 2: F5 CSTA scanner low yield + strategic question** (`memory/project_f5_csta_scanner_low_yield.md`). 1.8% yield. Multiple issues including wrong query corpus, input truncation, prompt district-fallback. Plus open strategic question: standalone scanner or F2 enrichment layer?
3. **BUG 3: F2 writes rows in scrambled column layout (HIGHEST PRIORITY MYSTERY)** (`memory/project_f2_column_layout_corruption.md`). Tonight's 8 F2 rows landed at wrong column positions while F5/F8 rows from the same session window are canonical. **Also discovered 1912 pre-existing scrambled rows** in the queue — this has been happening for weeks. Some secondary writer or race condition is bypassing the canonical writer.
4. **BUG 4: F8 research playbook mismatch for diocesan networks** (`memory/project_f8_diocesan_research_playbook.md`). Archdiocese of Chicago smoke test FAILED all 3 gates. Research engine's L1-L8 all returned 0 (couldn't discover `archchicago.org`). Only 1 of 3 "verified" contacts was a real Archdiocese hit.
5. **BUG 5: Research pipeline cross-contaminates leads across districts** (`memory/project_research_cross_contamination.md`). Discovered as a side effect of BUG 4. 2 of 3 Archdiocese "verified" contacts were actually at unrelated public districts (ROWVA CUSD 208, Community HSD 218). Pattern likely affects the other 19 completed research jobs.

**Non-bug work banked tonight:**
- **CLAUDE.md trim:** 45.4k → 33.3k → 36.9k (with Session 53 current state). Extracted repo tree + env var table + command list + Claude tool registry to `docs/SCOUT_REFERENCE.md` (gitted, not loaded per-session). Cleared the 40k performance ceiling.
- **Tulsa PS Gmail draft scheduled.** Body reworked in claude.ai, rewrote as plain text via GAS bridge (3 attempts to get apostrophes right). **Scheduled to send Tuesday 8:05 AM.** Old broken drafts manually trashed.
- **2 real warm leads banked in canonical-layout queue rows** (verified via direct sheet read): Pittsburgh Public Schools (PA, csta_partnership, priority 621, via Teresa Nicholas CSTA K-12 Board member) and Archdiocese of Chicago Schools (IL, private_school_network, priority 839). Archdiocese research completed tonight — Cold Prospecting Google Doc built (note: sequence builder fell back to "cold" because it has no `private_school_network` branch — minor follow-up).
- **5 project memories + MEMORY.md index updated.**

**What was NOT done tonight (carries over to Session 54 AFTER the fix sprint):**
- Stage 6: queue charter CMOs + CTE centers — BLOCKED on BUG 3 resolution
- Stage 7: F9 compliance CA pilot — lower blocker (F9 writes to Signals tab not queue), but post-Session-53 trust level is low
- Stage 8: F1 backlog drip (384 pending intra_district rows) — BLOCKED on BUG 3 (some may already be scrambled and unreachable)

**Session 54 starts with:**
1. **Enter plan mode.** No autonomous builds. Per the Session 52 rule.
2. **Work the fix priority order from CLAUDE.md CURRENT STATE:** BUG 3 column layout → BUG 5 research cross-contamination → BUG 4 diocesan playbook → BUG 1 F4 queries → BUG 2 F5 strategic decision → Stage 6-8 Session 52 carryover.
3. **Build a local diagnostic harness** that can replay Serper results + call `add_district` without Railway redeploys.
4. **Consider flipping kill switches to False** for F4 and F5 during the sprint. F2 stays enabled (logic good, only BUG 3 writer issue). F8/F9 stay enabled.

---

### Session 52 deliverables (Checkpoint A)

**Audit findings (verified against live code, not just agent reports):**
1. **BLOCKER A — Priority scoring collapse across 7 strategies.** `add_district()` called `_calculate_priority(strategy, 0, 0, 0)` with positional zeros. Affected `intra_district`, `cs_funding_recipient`, `competitor_displacement`, `csta_partnership`, `charter_cmo`, `cte_center`, `private_school_network`, `compliance_gap`. 384 pending F1 prospects + all Session 49 auto-queued rows were at tier base.
2. **BLOCKER B — F9 auto-queued unvalidated extracts at highest system priority.** Tier 850-939 (above cs_funding_recipient 800-899 despite docstring claim), with zero validation data, violating the ≥60% validation exit criterion.
3. **BLOCKER C — `/signal_act` hardcoded `strategy="trigger"` for every signal.** Latent bug since Session 44 — every bond/leadership/RFP/AI-policy signal promoted via /signal_act has been scoring as cold tier instead of its proper strategy. "trigger" wasn't even a branch in `_calculate_priority`.

**Commits landed (6 total, 2 pushes):**
- **C1 (f4609fb) `add_district **kwargs forwarding for priority scaling`** — added **kwargs, new `territory_data.lookup_district_enrollment(name, state)` helper, updated charter/cte/private_schools/compliance + F2/F5 scanner call sites to pass size kwargs. Row columns 15-17 now populated.
- **C2 (a996b32) `F9 Signals-only + /signal_act strategy mapping`** — compliance scanner writes to Signals tab with signal_type="compliance", stable sha1 message_id, parse_errors propagation via tuple return. `_SIGNAL_TYPE_TO_STRATEGY` dict in agent/main.py maps `compliance → compliance_gap`. /signal_act now uses `functools.partial` to pass `est_enrollment=` through `run_in_executor`.
- **C3 (aff8f16) `/reprioritize_pending one-shot migration`** — recovers size metadata from seed files (charter_cmos.json, cte_centers.json, PRIVATE_SCHOOL_NETWORKS) or NCES lookup for scanner-based strategies. Explicitly skips intra_district (homogeneous) and compliance_gap (post-fix shouldn't exist).
- **C4 (f60ca7a) `token-subset matching in lookup_district_enrollment`** — fix surfaced when migration initially matched 1 of 20 rows. Added inline token-subset check between exact + fuzzy fallback (csv_importer.fuzzy_match_name has a gap for 1-token-subset-of-multi-token cases). Migration yield jumped from 1/20 → 13/20.
- **C5 (7a58cc5) `kill switches + evidence_type normalization`** — `ENABLE_CSTA_SCAN` / `ENABLE_PRIVATE_SCHOOL_DISCOVERY` / `ENABLE_HOMESCHOOL_COOP_DISCOVERY` + guards. `_normalize_enum()` helper applied to F2 scan_competitors and F5 scan_csta_chapters evidence_type comparisons. Reconciled F2 `rfp_bid` vs `rfp_replacement` prompt/code mismatch — canonicalized on `rfp_bid`, fixed prompt enum list to include `board_adoption` + `rfp_bid` (they were in the detailed rules but missing from the terse enum).
- **C6 (a846137) `F9 compliance scanner 24h rate limit`** — per-state `_LAST_SCAN` dict + 24h cooldown. Cost guardrail against typos or double-taps.

**Stage 1 side outputs (time-decaying backlog):**
- Tulsa PS Prop 3 ($104.785M tech bond) passed with 80.97% approval on April 7. Gmail draft saved for Robert F. Burton (robert.burton@tulsaschools.org) — in Drafts folder, awaits Steven's review. Draft uses the Steven-approved bond-trigger tone (saved as `feedback_bond_trigger_outreach_tone.md` memory).
- 7 stale Session 49 F2 competitor signals + 2 stale Session 44 STRONG signals (Richardson ISD RFP 198d old, Norwalk AI-policy 289d old) marked `expired` via `update_signal_status`.
- Acton-Boxborough not in active signals (already expired or different naming).
- Session 44 "4 STRONG" freshness determined on-face from age + heat decay, not per-signal research. Only Tulsa was still actionable.

**Migration run result (from Checkpoint A):**
- Total pending scanned: 20 (5 cs_funding_recipient + 15 competitor_displacement)
- Updated: 13
- Unmatched: 7 (Western Reserve ESC = 0 enrollment in NCES; others had naming variations outside the token-subset match)
- No charter_cmo / cte_center / private_school_network rows in queue yet (Stage 6 will queue them in Session 53)

**What was NOT done this session (carries over to Session 53):**
- Stage 4: rebuild signals (/signal_funding, /signal_competitors, /signal_csta) — ~30 min, ~$1.30
- Stage 5: F8 one-network smoke test (Archdiocese of Chicago) — ~20 min, ~$0.50
- Stage 6: queue charter CMOs + CTE centers (all 43 + 79) — ~20 min, $0
- Stage 7: F9 compliance pilot on CA only — ~30 min, ~$2
- Stage 8: F1 backlog drip (target 30 approvals) — ~30 min, $0
- Commit 6 (Session wrap) is being done now instead of at end of Stage 8.

**Next session starts with:**
1. Verify Railway "Scout is online" after Push #2 (a846137).
2. Run Stage 4 scanner rebuild: `/signal_funding` → spot-check → `/signal_competitors` → spot-check (3 HIGH signals against BoardDocs URLs) → `/signal_csta` → spot-check. Confirm auto-queued rows have non-zero `Est. Enrollment` column (proves C1 fix is live on Railway).
3. Stage 5/6 in parallel: queue Archdiocese of Chicago, start its research pipeline in the background, meanwhile `/prospect_charter_cmos` + `/prospect_cte_centers`. Verify charter top 10 sorts by school count (IDEA 135 should be top) and CTE top 10 sorts by sending districts.
4. Stage 7: `/scan_compliance CA` (will write to Signals tab, not queue — per C2). Manually validate first 5 extracts. If ≥3 of 5 validate, proceed to IL + MA in a later session.
5. Stage 8: approve 30 F1 intra_district prospects in batches of 5-10.
6. Review pending Tulsa PS Gmail draft from Session 52, send or revise.

---

## Session 51 deliverables (archived — all fixed or superseded in Session 52)

### Session 51 deliverables
1. **Tier A spot-check verdict**:
   - F4 Western Reserve ESC (OH): REAL — $584K Ohio Teach CS 2.0 grant for teacher PD (verified via news-herald.com URL). Scout's "ESA buys curriculum" framing is WRONG — this is PD funding. Correct play is member districts (Willoughby-Eastlake, Painesville, iSTEM), not the ESC itself.
   - F2 Carlinville/Effingham/U-46 (IL): WEAK. All three were linked to `code.org/districts/partners` — FREE partner network, not paid Code.org Express customers.
   - F2 Azusa USD (CA): VERY WEAK. Source was a CodeHS student scholarship announcement; one Azusa High student won $1,000. Not district adoption.

2. **F4+F2 URL preservation bug fix** (commit 42b6ef7): Both scanners were hardcoding `url=""` when writing signals — source URLs never made it to the Signals tab, making verification impossible. Fixed the Claude extraction schemas to include `source_url` and added http/https validation against hallucinated URLs.

3. **F2 scanner complete rewrite** (commit 4801431):
   - Dropped tertiary `site:vendor.com` query — source of 90%+ false positives.
   - New primary: BoardDocs hits (`site:go.boarddocs.com`) — real board meeting docs.
   - New secondary: general board-of-education curriculum adoption docs.
   - New tertiary: RFP / bid documents with vendor-domain exclusion.
   - Collapsed per-state query loop — territory filter moved to NCES post-process. 13× fewer Serper calls.
   - Strict evidence types: only `board_adoption`, `rfp_bid`, `job_posting`, `rfp_replacement` qualify for HIGH confidence. Case studies + press releases cap at MEDIUM.
   - URL-pattern downgrade: `/districts/partners`, `/scholars`, `/blog/announcing-*`, `/newsletter` auto-demote to LOW.
   - Local test produced 7 HIGH signals from real BoardDocs URLs: Columbus City SD (OH), Fort Worth ISD (TX), Palo Alto USD (CA), Pocono Mountain SD (PA), Northridge (OH), Chester Upland (PA). Night-and-day improvement over Session 49's 7 false positives.

4. **F5 CSTA Chapter Partnership** (commit a637487): New `csta_partnership` strategy tier 620-719. Fixed URL bug in `scan_csta_chapters`. Added confidence + evidence types. HIGH + district + chapter officer/board → auto-queue. `memory/csta_partnership_sequence.md` — 4-step peer-to-peer sequence template.

5. **F10 Homeschool Co-op Discovery** (commit 8220c83): New `/discover_coops [state]` Serper-only command. Three queries per state with noise exclusions. New `homeschool_coop` strategy tier 500-599.

6. **F6 Charter School CMO Seed List** (commit 8ae5d5a): `memory/charter_cmos.json` with 43 CMOs across 11 states — 918 schools, ~511K students total. Biggest: IDEA PS (135), National Heritage (100), ResponsiveEd (80), Harmony (60). New `tools/charter_prospector.py` module. New `charter_cmo` strategy tier 780-899.

7. **F7 CTE Center Directory** (commit ac2c4e4): `memory/cte_centers.json` with 79 CTE centers — 1,009 sending districts, ~139K students. Coverage: OK (29), OH (22), PA (11), IN (6), MA (5), MI (3), TN (3). New `tools/cte_prospector.py`. New `cte_center` strategy tier 760-879.

8. **F8 Private School discovery + networks** (commit c911b33): Pivot from Urban Institute PSS sync (blocked — Urban doesn't have PSS, NCES Locator is rate-capped). New `tools/private_schools.py` with:
   - 24 multi-school network seed (dioceses + chains) — ~1,674 schools. Biggest: Primrose (450), Archdiocese of LA (215), Archdiocese of Chicago (125).
   - Serper per-state discovery.
   - New `private_school_network` strategy tier 740-839.

9. **F9 CS Graduation Compliance Gap PDF pilot** (commit 442d7cb): New `tools/compliance_gap_scanner.py`. Pilot: CA, IL, MA. Pipeline: Serper filetype:pdf → httpx download (10 MB cap) → Claude Sonnet 4.6 document input → structured extraction → auto-queue HIGH non-compliant/partial as `compliance_gap` strategy. New tier 850-939 (just below cs_funding_recipient — the law is the sales pitch). Cost ~$0.50-$2.00/scan. Exit criterion manual: ≥60% validation rate before scaling.

**Next session starts with (Steven said no acting — this is for the session AFTER he's ready to act):**
1. Rebuild Signals tab with new URLs — run `/signal_funding`, `/signal_competitors`, `/signal_csta`. Old rows may dedup-block; clear them first if needed.
2. Test F9 compliance pilot on CA, IL, MA. Validate ≥60% of queued districts before scaling to other states.
3. Queue + approve the static seeds: `/prospect_charter_cmos`, `/prospect_cte_centers`, `/prospect_private_networks`.
4. Approve 384 F1 intra-district prospects in batches of 5-10.
5. Tulsa bond results — if Prop 3 passed, act on Robert F. Burton.
6. Verify Google Alert parser with first post-April-9 digest.

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
- **Phase 3:** ✅ DONE (Session 46) — Leadership change monitoring (Serper + Claude, 8 found), RFP monitoring (CodeCombat-relevant filtering), Legislative signal scanner (2 CS mandates)
- **Phase 4:** ✅ DONE (Session 46) — BoardDocs noise filtering (_BOARD_FALSE_POSITIVE regex)
- **Phase 5 (future):** Ballotpedia superintendent snapshots (monthly diff), state procurement portal scraping for better RFP coverage, additional RSS sources

---

## COMPLETED: Territory Map Visualization (Sessions 46-47)
- `tools/territory_map.py` — interactive Folium HTML map
- 5 layers: Active Accounts (green, 18), Pipeline (orange, 12), Prospects (blue, 108), ESAs (purple), All Districts (gray clustered, 7978)
- Clickable popups with name, state, type. Layer toggles. CartoDB positron tiles.
- Sent as Telegram file attachment (10.3 MB). `/territory_map [state]` command.
- **Session 47:** Enriched popups — Active Accounts show licenses, lifetime revenue, open renewal, NCES enrollment/school count. Pipeline shows opp name, close date, enrollment. Prospects show NCES enrollment, school count, priority score. Districts show city, formatted enrollment. ESAs show city.
- **Future enhancement:** signal heat overlay

---

## COMPLETED: Prospecting Strategy Scanners (Session 47)

### 4 new Serper + Claude Haiku scanners — ~$0.03/scan each

| Scanner | Strategy # | Command | Schedule | What it finds |
|---------|-----------|---------|----------|---------------|
| `scan_grant_opportunities()` | #20 | `/signal_grants` | Monthly 1st Mon 8:45 AM | Districts receiving Title IV-A, Perkins V, state STEM, NSF grants for CS/CTE |
| `scan_budget_cycle_signals()` | #21 | `/signal_budget` | Monthly 1st Mon 9:00 AM | Districts in procurement/adoption cycles for CS/STEM curriculum |
| `scan_algebra_targets()` | #23 | `/signal_algebra` | On-demand | Districts piloting/adopting math/algebra technology (AI Algebra targets) |
| `scan_cybersecurity_targets()` | #24 | `/signal_cyber` | On-demand | Districts with CTE cybersecurity programs (fall 2026 pre-launch pipeline) |

### Architecture
- Same pattern as leadership/RFP/legislative scanners: Serper web search → deduplicate URLs → Claude Haiku extraction with aggressive relevance filtering → NCES district validation → customer status check → heat scoring → write to Signals tab
- Grant scanner: excludes construction, hardware, E-Rate. Includes Title IV-A, Perkins V, state STEM, NSF, private foundation grants
- Budget scanner: excludes general budget news, devices, ERP/admin systems. Boosts vendor evaluation and procurement signals
- Algebra scanner: targets curriculum adoption cycles, pilots, RFPs for math technology. Wider last-month window
- Cybersecurity scanner: targets existing CTE cyber programs, hiring, certifications. Uses last-year window (pre-launch pipeline building)
- Signal system now: 14 sources, 22 Telegram commands

---

## COMPLETED: Email Reply Drafting System (Session 48)

### What was built
- **Gmail MCP workflow** — Claude Code reads unread inbox, classifies (DRAFT/FLAG/SKIP), drafts replies in Steven's voice, creates threaded Gmail drafts. Steven opens inbox, tweaks, sends.
- **Response playbook** (`memory/response_playbook.md`) — 14 categories with real snippets from 150+ sent emails: pricing, budget constraints, scheduling, pilots, support routing, procurement, grants, etc.
- **Voice profile updated** (`memory/voice_profile.md`) — added Drafting Rules, Anti-AI-Tell Checklist, and 10 Learned Corrections from live testing
- **Workflow instructions** (`prompts/reply_draft.md`) — full step-by-step for any Claude Code session
- **GAS bridge `delete_draft`** — added to Code.gs for cleaning up orphaned drafts
- **Draft log** (`memory/draft_log.md`) — for future "learn from my sends" learning loop

### Known issues
- **Outreach browser extension** strips API-created draft body for contacts in Outreach's database. Workaround: create standalone "COPY THIS" draft for copy-paste.
- Always use `contentType="text/html"` for clickable links
- Never create duplicate drafts on same thread (causes persistent "Draft" label)

### Testing results
- 5 emails drafted during testing, 3 sent successfully. Voice was accurate, content corrections captured as learnings.
- Banned phrase: "Want to hop on a quick call" — replaced with "Want to connect via Zoom this week?"
- Pricing rule: push for Zoom first, send pricing after pushback or for international leads

---

## COMPLETED: Session 49 — Massive session

### Email Auto-Drafter on Railway
- `tools/email_drafter.py` (NEW) — polls unread inbox every 5 min during business hours (7 AM-6 PM CST weekdays), classifies via Claude Haiku (DRAFT/FLAG/SKIP), drafts via Claude Sonnet 4.6 with `memory/voice_profile.md` + `memory/response_playbook.md`, creates threaded HTML drafts via GAS bridge
- `gas/Code.gs` upgraded — `createDraft()` accepts `thread_id`, `cc`, `content_type` params; new `threadHasDraft()` helper + `skip_if_draft_exists` flag prevents duplicate drafts on same thread
- `tools/gas_bridge.py` — `create_draft()` signature extended; `_call()` passes through `already_drafted: true` responses without raising
- `agent/main.py` — startup seeding, 5-min poll loop, `/draft_emails` and `/draft force` commands, EOD daily summary
- Daily summary in EOD report
- 5 emails drafted in production during session

### 5 Parked Features Shipped (from previous sessions' backlog)
- **F1 (Session 49 first batch):** Fuzzy matching for winback (`tools/district_prospector.py:suggest_closed_lost_targets`) and call list (`tools/daily_call_list.py`). Resolved 30/93 schools instead of 17/93 baseline (12 exact + 18 fuzzy)
- **F2:** Contact extractor improvements — content window 12K→20K chars, known-contacts dedup injection via module-level cache (`tools/contact_extractor.py`)
- **F3a:** Added bidnet.com + bonfirehub.com queries to RFP scanner
- **F3b:** Added EdSurge + CoSN to RSS_FEEDS list (verified working)
- **F3c:** Persistent superintendent directory in `memory/superintendent_directory.json` via github_pusher. `update_superintendent_directory()` upserts from leadership scans, detects real person-name changes, `get_superintendent()` lookup ready for personalization
- **F4:** `get_unanswered_emails()` in `tools/activity_tracker.py` — finds people Steven emailed who never replied. Comma-split recipient handling, tz-aware date parsing, 30-recipient cap. New `/unanswered [days]` command
- **F5:** Tool eval — `docs/tool_evaluation_2026_04.md` documents Serper/Exa/Firecrawl/Jina/Crawl4AI/Tavily landscape. Recommendation: Hobby plan ($16/yr or $19/mo), Jina Reader as untested cheap preprocessor, Claude PDF input as Firecrawl alternative for course catalogs

### Bug fixes
- `/draft force` UnboundLocalError — `gas` was being treated as local because `handle_message` assigns `gas = get_gas_bridge()` later in the function. Fixed by calling `get_gas_bridge()` into `draft_gas` local
- `_run_daily_signal_scan` `name 'gas' is not defined` — same scoping issue but in async task spawned from scheduler. Fixed by calling `get_gas_bridge()` into `scan_gas` local
- GAS `already_drafted` was being raised as exception by `_call()` instead of returned as dict. Fixed `_call()` to pass through known-benign responses
- F2 first run extracted 1/59 articles — Claude prompt EXCLUDE list too aggressive. Loosened to permissive extraction with confidence tiers handling filtering

### Lead Generation Expansion — Tier A Complete
**Plan:** `/Users/stevenadkins/.claude/plans/inherited-munching-sunrise.md` (after 2 ruthless pressure-test passes)

| F# | Feature | Status | Yield |
|----|---------|--------|-------|
| F3 | Curriculum Adoption Queries | ✅ Shipped | 6 new queries on existing RFP scanner — Nov-Jan committee formation primary, Feb-May secondary |
| F1 | Second Buyer Expansion (intra_district) | ✅ Shipped + Verified | **384 schools queued** from 98 eligible parent districts. 56 dedup catches. New `/prospect_expansion [max_per_district]` command. |
| F4 | State CS Funding Scanner | ✅ Shipped + Verified | 9 raw, **1 HIGH auto-queued (Educational Service Center of the Western Reserve, OH)**. ~$0.10/scan. New `/signal_funding` command. |
| F2 | Competitor Displacement Scanner | ✅ Shipped + Verified | 8 raw, **4 HIGH auto-queued (Carlinville CUSD#1 IL, Effingham CUSD 40 IL, School District U-46 IL, Azusa USD CA)** — all on Code.org Express or CodeHS. ~$0.20/scan. New `/signal_competitors` command. |

### Architecture decisions
- **Kill switches:** New scanners ship with `ENABLE_FUNDING_SCAN`/`ENABLE_COMPETITOR_SCAN` constants at top of `tools/signal_processor.py` for one-line disable
- **Confidence routing:** HIGH → auto-queue via `add_district()` as `pending`. MEDIUM/LOW → Signals tab only. Active customer match → `customer_intel` log only (don't sell, don't discard)
- **Per-feature commits:** Each feature shipped as separate commit for surgical rollback. Session 49 has 16+ commits
- **`_calculate_priority()` extended** with 3 new strategy branches: `intra_district` (750-849), `cs_funding_recipient` (800-899), `competitor_displacement` (650-749)
- **F1 healthy filter REMOVED** in v1 — was too aggressive (98 districts skipped). Salesforce CSV often has empty Last Activity field. Re-add later with verified data

### Tier B + C deferred (in plan file as one-line stubs)
- F5 CSTA Chapter Partnership — strategy tag + sequence template (~60 min)
- F6 Charter School CMO Seed List — `memory/charter_cmos.json` + prospecting module (~90 min)
- F7 CTE Center Directory — similar pattern (~90 min)
- F8 Private School Data — NCES PSS sync via Urban Institute API (~120 min)
- F9 CS Graduation Compliance Gap — Claude PDF input pilot for CA/IL/MA (~120 min). Exit criterion: ≥60% validation rate
- F10 Homeschool Co-op Discovery — lightweight Serper-only command (~45 min)

### Not built (blocked or covered)
- **F11 Usage Decline Early Warning:** Blocked on CodeCombat product usage data. Coordinate with CodeCombat team. ~2h once data available
- **F12 Teacher-to-Admin Referral Chain:** Covered by F1 + existing C5 upward prospecting

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
