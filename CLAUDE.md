# SCOUT — Claude Code Reference
*Last updated: 2026-04-17 — End of Session 74. S74 autopilot code SHIPPED (6 commits + priority-fill patch, all pushed). Not yet POSTing real prospects — `_autopilot_live_flag` defaults False. S75 plan file = first-live-run gate: pre-flight verify → PATCH throttles → flip flag → Monday 07:00 auto-fire.*

---

## CURRENT STATE — update this after each session

**Session-narrative history lives in `SCOUT_HISTORY.md §Session N`. Active plan detail lives in `SCOUT_PLAN.md §YOU ARE HERE`. Active priority queue lives in `memory/project_s64_priority_queue.md` (auto-loaded). This section stays ≤25 lines.**

**End of Session 74, 2026-04-17 16:55 CDT — Campaign Autopilot shipped in dry-run mode; S75 plan locked:**

- **6+1 S74 commits pushed to `origin/main`** (`49d9ad8` → `966e421` → `e1e42fc`): `tools/grade_level_detector.py` + `tools/lead_filters.py` (60+71 tests; promoted `/tmp/sf_leads_dre_pass3+4+5.py`), `tools/campaign_config.py` (`STRATEGIES` extracted from budget reporter; adds `pool_source` / `bucket_to_sequence_name` / `throttle_profile_name` / `priority_order`), `tools/campaign_pool.py` (`PoolLead` superset of `Contact`; JSONL + meta at `data/dre_pool.jsonl`; 15 tests), `tools/campaign_autopilot.py` (run_autopilot + priority-fill + preview CSV + kill-switch + Rule-19-clean formatter), `agent/scheduler.py` 07:00 CST weekday tick, `agent/main.py` handler + `/autopilot_live` / `/autopilot_dry` / `/autopilot_status` slash commands + persisted flag at `data/campaign_autopilot_state.json`.
- **Live verification done:** dry-run autopilot on production produced 10 LQD-Universal LoadPlans w/ 2 correctly-skipped for `recent_activity`. Pool contains **27,467 measured eligible DRE leads** (521 LQD, 7273 TC-Universal-Residual, 5772 TC-MS, 5241 TC-HS, 5051 TC-Elem, INT 932, LIB 638, TC-Virtual 451, TC-District 450, INT-Teacher 432, TC-Teacher 390, IT-ReEngage 190, TC-All-Grades 126). Delta vs S72 baseline 26,137 = +1,331 is the missing `filter_leads_against_active_accounts` pool-level filter (not wired in `campaign_pool.build_pool` — S76 debt, documented in S75 plan Risks table).
- **Budget math correction baked into memory:** Each Tier 1 strategy (#9/#10/#11/#12) has its OWN 266/week allocation — NOT a shared pool. Claude miscommunicated this multiple times in S74. Memory: `feedback_tier1_budget_is_per_strategy.md`. DRE daily budget = 266/5 = 53/day.
- **Priority-fill (commit `e1e42fc`):** autopilot walks `STRATEGIES["dre"].priority_order` (LQD → TC-U-Residual → TC-MS → TC-HS → TC-Elem → others) with a strategy-wide 53/day budget, draining the top cohort before spilling into the next. When LQD's 521 exhausts (~10 working days) adds flow automatically to TC-U-Residual etc.
- **Outreach throttle still `phase-a`:** LQD=10/day, 12 others=0. Autopilot's 53/day budget is capped at 10 until throttle is PATCHed to `autopilot-55` in S75.
- **Autopilot is LIVE in the bot but in dry-run mode.** `_autopilot_live_flag=False` default. Monday 07:00 CST scheduler will fire `_run_campaign_autopilot()` in dry-run → Telegram "[DRY RUN] Would add 10 → LQD-Universal" summary. Steven has NOT flipped live yet.
- **S75 plan approved and saved at `/Users/stevenadkins/.claude/plans/snuggly-wishing-cocke.md`.** Three-phase: (A) build+run `scripts/verify_autopilot_batch.py` pre-flight on first 80 LQD candidates (classifier audit + HARD-SKIP pre-count + SOFT-FLAG for active-account/BUG5/data-quality); (B) if clean — add `not_in_outreach` HARD-SKIP guard to autopilot (commit), extend `THROTTLE_PROFILES["autopilot-55"]` to `scripts/create_dre_sequences.py`, run `--configure-throttles autopilot-55` (PATCHes all 13 DRE seqs to 55/day), flip `_autopilot_live_flag=True`; (C) Monday 07:00 CST scheduled tick auto-fires live run → ~53 adds to LQD-Universal, Step 1 sends ship Monday's schedule-51 window. No manual CLI trigger — schedule-51 Mon-Fri means "adds tonight" and "adds Monday 07:00" produce identical send timing (`feedback_schedule_aligned_add_timing.md`).
- **Documented S76 debt:** (a) `filter_leads_against_active_accounts` not wired into `campaign_pool.build_pool` — pool is pre-filter; S75 Phase A SOFT-FLAG catches per-batch, systemic fix = S76. (b) `prospect_loader.Contact.diocese_or_group` field name is domain-specific; autopilot passes cohort bucket name through it — rename to `cohort_tag` post-S74. (c) `/apply_profile` slash command for manual throttle switches when LQD drains — defer to ~week 10.
- **Kill switches unchanged:** `touch ~/.claude/state/scout-campaign-autopilot-disabled` (autopilot), `touch ~/.claude/state/scout-hooks-disabled` (R19+R20+R21 scanner).
- **Repo state:** Clean on `main`, `.DS_Store` modified only. All S74 work pushed.

**Active kill switches:**
- Rule scanner hooks (R19+R20+R21): `touch ~/.claude/state/scout-hooks-disabled`
- Research Engine Round 1 flags: default OFF in `ResearchJob.__init__`; do NOT enable without a fresh plan

**Prior-session narratives:** `SCOUT_HISTORY.md §Session N` (S72/S71/S70 and earlier all archived there). S67–S69 narratives not yet folded into SCOUT_HISTORY.md; see `SCOUT_AUDIT_2026-04-15_0128.md` for the S69 audit output.

---

## LOAD-BEARING REFERENCES

**Primary / Secondary targeting (S66):** Primary = US public school districts in Steven's 13 territory states. Secondary = every other school / org / entity inside territory that could buy CodeCombat K-12 curriculum, MUCH broader than "charter+CTE+diocesan+private." **Never narrow the secondary lane to four categories.** Full list: `memory/feedback_scout_primary_target_is_public_districts.md` + `docs/SCOUT_RULES.md §0`. Source of truth for roles/titles/keywords at each entity type: Steven's "ROLES and KEYWORDS for Searching and Scraping (Updated 4/1/26)" Google Sheet.

**Institutional knowledge still current at end of Session 66:**

- **6 diocesan sequences activated** (Philadelphia/Cincinnati/Detroit/Cleveland/Boston/Chicago). Schedule "Admin Mon-Thurs Multi-Window", 5 steps cadence 5 min / 5d / 6d / 7d / 8d, clean descriptions, hyperlinked meeting link + `codecombat.com/schools`. Verified clean via `verify_sequence`. Drip actively loading contacts.
- **Outreach sequence tool hardening (S59 round 4)** at `tools/outreach_client.py` — `validate_sequence_inputs`, `verify_sequence`, `create_sequence` refactored to call both automatically. Schedule allowlist default `{48, 50, 51, 52, 53}`. 14 unit tests in `scripts/test_outreach_validator.py`.
- **Outreach prospect write-path (S61)** at `tools/outreach_client.py` — `validate_prospect_inputs`, `create_prospect`, `find_prospect_by_email`, `add_prospect_to_sequence`. Wrapped by `tools/prospect_loader.py` (reusable bulk loader) and called from `scripts/diocesan_drip.py`. 15 unit tests in `scripts/test_diocesan_drip.py`. Full inventory in `docs/SCOUT_CAPABILITIES.md`.
- **Generalized campaign loader (S64)** at `scripts/load_campaign.py` — reads `campaigns/<slug>.md`, role-classifies contacts via `tools/role_classifier.py`, writes variant sequences via `create_sequence`, loads contacts via `prospect_loader.execute_load_plan`. Replaces per-campaign one-shots. Use for all new campaigns going forward.
- **Steven's 5 named delivery schedule IDs** are in `memory/feedback_outreach_schedule_id_map.md`. Never cite by number (Rule 19); use the name.
- **F1 intra_district scanner stays active** (384 pending rows). Horizontal prospecting is valid. Session 59 pushback in `memory/feedback_f1_intra_district_is_important.md`.
- **Scout data quality caveat (S59):** most Prospecting Queue / Signals / Leads from Research rows are scaffold-data from test runs. Active Accounts / Pipeline / Closed Lost / Activities are Salesforce-sourced and trustworthy. `memory/feedback_scout_data_mostly_untested.md`.
- **Research engine cost target: $25/week hard ceiling**, lower is better. Round 1 A/B at ~$0.80/job blended → ~3x over. Round 1.1+ must close the gap. `memory/feedback_research_budget_25_per_week.md`.
- **Outreach sending cap:** 5,000 emails/rolling-7-days per USER (not per mailbox). Gmail spillover breaks tracking. `memory/feedback_outreach_sending_cap_5k_weekly.md`.
- **BUG 5 WONTFIX (S65):** S55 two-stage filter + S63 blocklist band-aid are the complete solution. Don't re-open. `memory/project_bug5_shared_city_gap.md`.

### Session lessons (load on demand via memory files)

- **Empirical probing before plan mode catches frame errors** — `memory/feedback_plans_are_one_shot.md`
- **Haiku saturates on large mixed-topic corpora** — `memory/feedback_haiku_saturation_large_corpus.md`
- **Haiku is nondeterministic across runs even at temp=0** — `memory/feedback_haiku_nondeterminism_merge_previous.md`
- **Static finite directories are lookups not scanners** — `memory/feedback_static_directories_are_lookups.md`
- **`build_csta_enrichment` helper** lives in `tools/signal_processor.py` (Rule of Three: F4 inline, F6/F7/F8 lazy import)
- **Session 57 lessons** archived to `docs/SCOUT_RULES.md` Appendix A

---

## PREFLIGHT CHECKLISTS (load these before starting any task in the triggered category)

Session 59 shipped 12 failures across 3 rounds because memory files weren't loaded before touching the topics they covered. These checklists are MANDATORY reads at the start of any task matching the trigger. They live in CLAUDE.md (not a separate file) so they're always in session context.

**PREFLIGHT: Outreach work** — triggers on any task creating/modifying Outreach sequences, templates, prospects, or schedules.
- Confirm `tools/outreach_client.py::validate_sequence_inputs` is callable and knows the current allowlist (env `OUTREACH_ALLOWED_SCHEDULE_IDS` or default `{48, 50, 51, 52, 53}`)
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

**PREFLIGHT: Prospect add to sequence** — triggers on any task adding prospects to an Outreach sequence, one or many, manual or automated.
- Load: `feedback_never_manual_outreach_upload.md`, `feedback_outreach_sequence_order.md`, `feedback_outreach_torecipients.md`, `feedback_outreach_intervals.md`, `feedback_timezone_required_before_sequence.md`, `outreach_api_access.md`
- Grep `tools/outreach_client.py` for `create_prospect` / `add_prospect_to_sequence` / `validate_prospect_inputs` / `find_prospect_by_email`. If missing, STOP — do not write a new one-shot. Check `docs/SCOUT_CAPABILITIES.md` and `git log --since=120days` for prior `prospect` + `load` commits first. Promote ephemeral patterns before using them (Rule 18).
- Verify target sequence is active via the `sequences[id].attributes.enabled` check in `tools/prospect_loader._sequence_is_enabled` before writing.
- **Every contact MUST have BOTH a populated `state` field AND a populated IANA timezone BEFORE `create_prospect` AND before `add_prospect_to_sequence` fires.** Two failure modes this prevents: (1) **mergefield rendering** — Scout sequences use `{{state}}` in email bodies; missing state renders as blank/error, Outreach does NOT block the send on a missing mergefield, so the broken email ships and tanks that prospect's reply rate; (2) **send schedule optimization** — multi-window schedules (52 Admin, 53 Teacher) pick per-prospect local-time windows based on timezone; missing tz either mis-schedules at 3am local or falls back to CST for all prospects. Derive timezone from state via `tools.timezone_lookup.state_to_timezone`. Missing state OR missing tz = skip the contact, never fall back (Rule 17, S66 expansion).
- Mailbox ID is 11 for all of Steven's sequences (confirmed S61 by reading existing sequenceStates on 1999/1939/1857).
- Dedup via `find_prospect_by_email` before `create_prospect`.
- Stagger POSTs: never burst >20 sequenceStates within a 60-second window.
- Never bypass `validate_prospect_inputs`.

**PREFLIGHT: Campaign load** — triggers on any task running `scripts/load_campaign.py` or creating/editing files under `campaigns/`.
- Load: `feedback_sequence_copy_rules.md`, `feedback_sequence_iteration_learnings.md`, `feedback_outreach_sending_cap_5k_weekly.md`, `feedback_outreach_schedule_id_map.md`, `feedback_timezone_required_before_sequence.md`
- Confirm the campaign markdown file parses cleanly via `.venv/bin/python -c "from tools.campaign_file import load_campaign; print(load_campaign('campaigns/<slug>.md').variant_roles())"` — any parse error = STOP.
- Confirm `schedule_id` is in the validator allowlist (env `OUTREACH_ALLOWED_SCHEDULE_IDS` default `{48, 50, 51, 52, 53}`). Refer to `feedback_outreach_schedule_id_map.md` for the ID → name map.
- Confirm every variant has a meeting link hyperlink in ≥1 step and `codecombat.com/schools` hyperlink in ≥2 steps (the validator enforces this, but catch it earlier via eyeball).
- Confirm `drip_days` are all business days, in the future, and in a reasonable range (not >30 days out).
- ALWAYS run `scripts/load_campaign.py --campaign <slug> --create --dry-run` FIRST — this runs every variant through `validate_sequence_inputs` in a single pass and prints all failures at once. Fix them all before running `--create` without `--dry-run`.
- After `--create`, open the Outreach UI and manually activate each new sequence (Rule 15 — no auto-activation). `--execute` will refuse to load contacts into disabled sequences (`verify_sequence_active=True` default).
- Before `--execute`, always run `--preview` on the contact CSV first. Verify the role-classification breakdown looks right before any real POSTs.
- Check sending cap headroom — 5,000 emails/rolling-7-days per USER (see `feedback_outreach_sending_cap_5k_weekly.md`). Large batches (>1,000 contacts in a single week) push the cap and need staggering across weeks.
- Rule 19 compliance: the CLI translates sequence IDs to role names in stdout, but if you quote the CLI output in Telegram to Steven, double-check no raw IDs leak.
- NEVER edit `campaigns/<slug>.md` after running `--create` without either (a) re-running `--create` to rebuild the sequences or (b) using `--execute --force` to explicitly bypass drift detection.

**PREFLIGHT: Destructive instruction to Steven** — triggers on any task about to instruct Steven to delete, modify, update, clear, or mutate data in a system Scout can read (master sheet tabs, Outreach API, GitHub, git state).
- Load: `memory/feedback_verify_before_instructing.md`, `memory/feedback_code_enforcement_beats_process_rules.md`
- Call a live-state reader IN THE SAME TURN before writing the instruction. Choose from `tools/sheets_writer.get_leads` / `csv_importer.get_active_accounts` / `district_prospector.get_all_prospects` / `outreach_client.get_sequences` / `github_pusher.get_file_content` / `git log` / etc. Cite the reader's function name in prose OR in a fenced code block — the Rule 21 scanner searches RAW response text for the function name, so code blocks count.
- **Loading env is required**: every verification call needs `.env` loaded. Standard pattern: `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from tools.sheets_writer import get_leads; ..."`. Scout tools modules do NOT call `load_dotenv()` internally — the caller must. Missing this produces silent `GOOGLE_SERVICE_ACCOUNT_JSON not set` failures.
- Display the queried data with specific identifiers (row index, email, account name, commit hash). Never "delete the rows I flagged" without showing WHICH specific rows.
- **For destructive instructions NOT covered by Rule 21** (credential rotation, paste-new-secret, revoke-token workflows): the verification shape is "cite the procedure source" — reference Outreach API docs, `memory/reference_outreach_app_settings.md`, or the relevant memory file. Describe the procedure step-by-step and wait for Steven's explicit "yes, execute" before he runs it. Not scanner-enforced; process rule only.
- Rule 21 scanner kill switch: `touch ~/.claude/state/scout-hooks-disabled` (covers R19+R20+R21).

---

## CRITICAL RULES (top 21 — full rule set in `docs/SCOUT_RULES.md`)

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
17. **Timezone (and state) is a hard requirement on every Outreach prospect create.** `tools.outreach_client.validate_prospect_inputs` enforces IANA timezone at the code boundary — missing/invalid tz = `passed=False` and `create_prospect` refuses. S66 expansion: `state` is also required (prevents `{{state}}` mergefield rendering failures). Derive tz from state via `tools.timezone_lookup.state_to_timezone`. Never fall back; skip the contact. Session 61 diocesan drip lesson + S66 mergefield expansion.
18. **Never write a new one-shot Outreach prospect loader.** Before writing any prospect-add code, (a) grep `tools/outreach_client.py` for the target function name, (b) check `docs/SCOUT_CAPABILITIES.md`, (c) grep `git log --since=120days` for `prospect` + `load` + `sequence` commits. If the work has been done before but isn't in library code, promote the pattern to `tools/outreach_client.py` + `tools/prospect_loader.py` BEFORE writing a new one-shot. Ephemeral inline Python scripts (S38 CUE loader, S43 C4 1,119-prospect loader) are the root cause of the amnesia Steven called out in Sessions 59 and 61. The canonical path is `create_prospect` / `find_prospect_by_email` / `add_prospect_to_sequence` / `prospect_loader.execute_load_plan`.
19. **Never show Outreach backend numeric IDs to Steven — structurally enforced.** `prospect_id`, `sequence_state_id`, `sequence_id`, `mailbox_id`, `owner_id`, `template_id`, `schedule_id` — all get translated to human names at the presentation boundary. Prospect ID → "First Last (email@domain)". Sequence ID → name from `feedback_outreach_schedule_id_map.md` / `get_sequences()`. Mailbox 11 → "your mailbox". Owner 11 → "you". SequenceState IDs → omit entirely, say "the add to <sequence name>". Raw IDs stay in function return dicts for downstream API calls but never leak to chat/Telegram/summary text. Code-enforced by `scripts/rule_scanner.py` R19 — `label_roots: []` means no qualification can save you. Kill switch: `touch ~/.claude/state/scout-hooks-disabled`. Full rule + complete ID→name translation table: `memory/feedback_no_outreach_ids_in_chat.md`. Session 61 lesson, S62 structural upgrade.
20. **Every number labeled, structurally enforced.** Every numerical claim — percentages, dollar amounts, token counts — must be followed within 100 characters by a label root: `measured`, `sample`, `estimat`, `extrapolat`, `unknown`, `approximat`, `rough`, `guess`. Label can be parenthetical, natural language, or substring. Unlabeled numbers are forbidden even in single-sentence replies and casual answers. Code-enforced by `scripts/rule_scanner.py` R20 (tests: `.venv/bin/python scripts/test_rule_scanner.py`). Violations logged to `~/.claude/state/scout-violations.log` and force a mandatory correction directive on the next turn. Kill switch: `touch ~/.claude/state/scout-hooks-disabled`. Full scanner system docs + extensibility contract + rebuild path: `memory/feedback_rule_scanner_hook_installed.md`. Session 62 incident: three different context-window percentages quoted unlabeled in 30 minutes; Steven installed a full-context hook based on the bad number and had to revoke it.
21. **Verify before instructing Steven to modify live state — structurally enforced.** Any instruction to delete / modify / update / clear / mutate data in a system Scout can read directly (sheet tabs, Outreach API, git, GitHub) must be preceded — in the SAME response turn — by a call to a live-state reader function, with the function name cited in prose OR inside a fenced code block (R21 scanner searches RAW response text for the function name, so code blocks count). Screenshots, memory files, and context-window text are NEVER authoritative — only live queries are. `.env` must be loaded for every reader call (Scout tools modules do NOT auto-load). Code-enforced by `scripts/rule_scanner.py` R21 (type `trigger_and_missing_anchor`). **Out of scope for R21:** credential rotation, paste-new-secret, revoke-token — different verification shape, handled by the "Destructive instruction to Steven" preflight process rule only. Kill switch: `touch ~/.claude/state/scout-hooks-disabled` (covers R19+R20+R21). Full rule + exemption list + S65 incident: `memory/feedback_verify_before_instructing.md`.

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

- **`docs/SCOUT_RULES.md`** — full rule set (§0 Primary/Secondary targeting, GAS bridge, CSV import, research engine, signal processor, priority scoring tables, Outreach API, data model invariants, ops, Session 55–57 post-mortems). Read by section or grep by keyword.
- **`docs/SCOUT_REFERENCE.md`** — repo tree, full Railway env var table, Claude tool registry (25 tools), Telegram shorthand command list (~80 commands), session-workflow `scout` wrapper notes.
- **`SCOUT_PLAN.md`** — active plan + completed feature notes (A3 / B2 / C1 / C3 / C4 / C5 / Email Drafter / Signal System / etc.)
- **`SCOUT_HISTORY.md`** — bug log + per-session changelog (S58-S66 narratives all archived here)
- **`agent/CLAUDE.md`** + **`tools/CLAUDE.md`** — module-scoped API signatures
- **`gas/CLAUDE.md`** — GAS deployment checklist
- **`memory/*.md`** — behavioral feedback, auto-loaded at session start. Active priority queue at `memory/project_s64_priority_queue.md`.

**Trim history:** Session 53 extracted `docs/SCOUT_REFERENCE.md`. Session 58 extracted `docs/SCOUT_RULES.md` + retired duplicated sections already in `SCOUT_PLAN.md` / `memory/*.md`. Session 67 trim moved S66/S65 CURRENT STATE narratives to `SCOUT_HISTORY.md`, moved the priority queue to `memory/project_s64_priority_queue.md`, moved the primary/secondary expansion to `docs/SCOUT_RULES.md §0`, and shortened Rules 19/20/21 by pointing to their memory files. **Session 73 trim** archived S72 narrative to `SCOUT_HISTORY.md §Session 72` and deleted CLAUDE.md's duplicate S71+S70 narratives (already in history) and the stale S66 "active kill switches (unchanged)" block (content in memory files). Only the S72 CURRENT STATE block remains — the S73 first actions inside it are the load-bearing entry point for this session.
