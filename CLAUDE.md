# SCOUT — Claude Code Reference
*Last updated: 2026-04-14 — End of Session 64. Generalized campaign loader shipped (plan rebuilt from scratch after pressure-test), OAuth + pre-existing export filter bug fixed, scripts/env.sh shim shipped, priority queue locked by Steven, BUG 5 prep note committed for next session. Ten commits on main this session, all pushed.*

---

## CURRENT STATE — update this after each session

**Session-narrative history lives in `SCOUT_HISTORY.md`. Active plan detail lives in `SCOUT_PLAN.md §YOU ARE HERE`. This section stays ≤35 lines.**

**Where we are right now (end of Session 64):**
- **Session 64 shipped the generalized campaign loader + OAuth fix bundle (10 commits, all pushed).** Plan `~/.claude/plans/luminous-honking-cook.md` rev 2 after a full pressure-test rebuild. New in-repo: `tools/campaign_file.py` (single-file markdown schema + permissive parser), `tools/role_classifier.py` (Haiku temp=0 per-contact bucketing with pre-filter + sha1 cache), `scripts/load_campaign.py` (CLI with `--preview` / `--create` / `--execute` / `--dry-run` / `--force` + CSV/stdin contact input + sidecar state with sha1 drift detection + Rule 19 name translation), `outreach_client.export_sequence_for_editing` (fetch existing sequence as claude.ai starter markdown), `scripts/env.sh` (bash shim for python-dotenv env loading), `campaigns/canary_test.md` + `campaigns/canary_test_contacts.csv` fixtures, 47 unit tests total (10 parser + 7 export + 11 classifier + 19 CLI). Live smoke: 14/14 real K-12 titles classified correctly; `--create --dry-run` 3/3 variants pass preflight; full Chicago diocesan export + round-trip verified against the live API.
- **The plan rebuilt from scratch mid-session after a Steven senior-reviewer pressure-test.** v1 had three structural problems: multi-file `campaigns/<slug>/config.yaml + variants/` layout that would have forced Steven to translate claude.ai output into a new schema on every round trip; rule-based role classifier that caps at 75-85% (estimate) accuracy and needs 150-300 lines (estimate) of regex; a diocesan_drip refactor mid-week with live production drip running the next two days. v2 fixed all three: single markdown file per campaign, Haiku classifier in ~50 lines, diocesan refactor dropped entirely. Plus preflight-runs-all-variants-before-any-POST, sidecar state with drift detection, stdin contact input. **Plan-mode pressure-test was the highest-value meta-lesson of the session.**
- **Reframe #1 (the big one)**: I started on the S63 prep note's handler-wiring path. Steven said "haven't we got these features built already?" and described his real workflow: drafts in claude.ai, role segmentation, multi-variant sequences, staggered loads. That killed the handler-wiring direction entirely. Handler stays unchanged (`agent/main.py:319-528` still writes Google Doc drafts only — Steven confirmed he uses the auto-draft "almost always" as a claude.ai starter). `docs/session_64_prep_prospect_loader_wiring.md` is now historical — do not execute it.
- **OAuth fix + pre-existing filter bug**. `tools/outreach_client.export_sequence` had a latent bug calling `/sequenceTemplates?filter[sequence][id]=<N>` which Outreach rejects with 400. The working pattern (per `validate_sequence_inputs:1115`) is `filter[sequenceStep][id]=<step_id>` one call per step — rewrote accordingly. Also: `.venv/bin/python scripts/load_campaign.py` now calls `load_dotenv()` at import time per Scout convention; `campaign_file.dump_campaign` uses `allow_unicode=True` so em-dashes render natively. Local token cache refreshed (`/tmp/outreach_tokens.json` has ~2h headroom).
- **`bash source .env` is permanently broken — use `scripts/env.sh` instead.** Empirical proof: the `OUTREACH_CLIENT_SECRET` value contains both a literal `'` and a literal `$`, and no quoting scheme represents both characters the same way in bash and python-dotenv. Tested 4 schemes, zero universal winners. Shim uses python-dotenv internally then emits shlex-quoted `export` lines for bash. Full analysis in `memory/reference_env_var_quoting_gotcha.md`.
- **Steven locked a priority queue for end-of-S64 through the rest of the roadmap.** Do items in order, nothing else without explicit redirection. See "Locked priority queue" section below + `memory/project_s64_priority_queue.md` (auto-loaded).
- **Research Engine Round 1 flags still parked default-OFF.** Production `agent/main.py` is byte-for-byte v1. Round 1.1 is NOT in the priority queue — treat as "after item 8" unless reprioritized.
- **Wrap-ups are not rushed, ever** (S63 rule still in force). The 40%/45%/50% context thresholds (measured — from user CLAUDE.md) are for stopping NEW builds, not for rushing the session wrap. This wrap crossed into that zone deliberately.
- **Structural enforcement (Rule 19 + Rule 20 scanner) still live** and still catching ghost-matches on stale violation log entries. Known issue, documented in S63 memory files. Not a blocker.
- **Repo state:** all S64 commits pushed to `origin/main`. Working tree clean except `.DS_Store`.

**LOCKED PRIORITY QUEUE (Steven 2026-04-14 end-of-S64, do in order, nothing else):**

Full rationale + per-item background lives in `memory/project_s64_priority_queue.md` (auto-loaded each session). Order is load-bearing.

1. **HARD DEADLINE: Thursday diocesan drip** — `.venv/bin/python scripts/diocesan_drip.py --execute` on Thu 2026-04-16 (do NOT `--force-day`). 14 contacts, roughly 6 min wall clock (sample). Then `--verify` to confirm all 63 diocesan contacts landed. This is the ONE item that can preempt the priority queue because of its fixed date.
2. **BUG 5 permanent fix** in `tools/research_engine.py::_target_match_params`. **Plan-mode session required (Rule 1).** **READ `docs/session_65_prep_bug5_target_match_params.md` FIRST** — code paths mapped, seven open questions pre-identified, five candidate fix approaches. Current band-aid is `memory/public_district_email_blocklist.json` runtime guard. Blocks the 9 pending dioceses review.
3. **LA archdiocese research restart** — blocked on F8 diocesan research playbook gap. Plan-mode session. Background: `memory/project_f8_diocesan_research_playbook.md`.
4. **IN/OK/TN CSTA LinkedIn-snippet extraction** — iterate `scripts/fetch_csta_roster.py` for higher yield than hand-curation. Background: `memory/project_csta_roster_hand_curation_gaps.md`.
5. **F2 column layout corruption** — 1,912 pre-existing scrambled rows + something bypassing the canonical writer. Highest-priority unknown. Background: `memory/project_f2_column_layout_corruption.md`.
6. **Research cross-contamination audit** — post-extraction domain validation layer. Not F8-specific. Background: `memory/project_research_cross_contamination.md`.
7. **Prospecting Queue / Signals / Leads cleanup** — scaffold data from test runs. One-time sweep. Background: `memory/feedback_scout_data_mostly_untested.md`.
8. **Known debt / housekeeping** — refresh `SCOUT_PLAN.md` YOU ARE HERE (stale since end of S63), optionally rotate `OUTREACH_CLIENT_SECRET` to remove the embedded `'` + `$` combo.

**Explicitly NOT in this queue (do not start until drained):**
- First live campaign via `load_campaign.py` — cross-session validation, opportunistic when a real campaign is on the plate.
- Research Engine Round 1.1 — cost-ceiling blocker but not on Steven's explicit priority list. Treat as "after #8 unless Steven reprioritizes."
- Handler wiring `_on_prospect_research_complete → execute_load_plan` — reframed during S64 plan mode, replaced by `scripts/load_campaign.py`. `docs/session_64_prep_prospect_loader_wiring.md` is now historical.
- 1,245 cold_license_request + 247 winback March backlogs — deferred.

**For Session 62 + 63 narratives:** `SCOUT_HISTORY.md §Session 62` / `§Session 63`.
**For the rule scanner plan reference:** `~/.claude/plans/playful-weaving-nygaard.md` + `~/.claude/plans/flickering-nibbling-breeze.md`.

**Session 63+ carryover (non-drip, load by demand):** see `SCOUT_PLAN.md §YOU ARE HERE` — 9 pending dioceses review blocked on BUG 5, optional F9/LA/OK-CSTA/IN-TN-script items, deferred 1,245 cold_license_request + 247 winback March backlogs (plan-mode triage session).

**Active kill switches:**
- Rule scanner hooks: `touch ~/.claude/state/scout-hooks-disabled` (both hooks short-circuit at top)
- Research Engine Round 1 flags: default OFF in `ResearchJob.__init__`; do NOT enable without a fresh plan

---

## LOAD-BEARING REFERENCES

The following institutional knowledge is still current at end of Session 61. Full context is in the named files; this section is a pointer map, not a duplicate.

- **6 diocesan sequences activated** (Archdiocese of Philadelphia/Cincinnati/Detroit, Diocese of Cleveland, Archdiocese of Boston, Archdiocese of Chicago). Owner = you, schedule = "Admin Mon-Thurs Multi-Window", 5 steps cadence 5 min / 5d / 6d / 7d / 8d, clean descriptions, hyperlinked meeting link + `codecombat.com/schools`. All verified clean via `verify_sequence` in Session 59 rounds 1-4 + re-verified at Session 61 second half. Diocesan drip is actively loading contacts into these starting Tue Apr 14.
- **Outreach tool hardening (Session 59 round 4)** lives in `tools/outreach_client.py` — `validate_sequence_inputs`, `verify_sequence`, and `create_sequence` refactored to call both automatically. Schedule allowlist default `{48, 50, 51, 52, 53}`. 14 unit tests in `scripts/test_outreach_validator.py`. Full Session 59 narrative in `SCOUT_HISTORY.md`.
- **Outreach prospect write-path (Session 61)** lives in `tools/outreach_client.py` — `validate_prospect_inputs`, `create_prospect`, `find_prospect_by_email`, `add_prospect_to_sequence`. Wrapped by `tools/prospect_loader.py` (reusable bulk loader) and called from `scripts/diocesan_drip.py`. 15 unit tests in `scripts/test_diocesan_drip.py`. Full inventory in `docs/SCOUT_CAPABILITIES.md`.
- **Steven's 5 named delivery schedule IDs** are in `memory/feedback_outreach_schedule_id_map.md`. Do NOT cite them to Steven by number (Rule 19); use the name.
- **F1 intra_district scanner stays active** (384 pending rows). Horizontal prospecting is valid. Session 59 pushback in `memory/feedback_f1_intra_district_is_important.md`.
- **Scout data quality caveat** (Session 59): most Prospecting Queue / Signals / Leads from Research rows are scaffold-data from test runs. Active Accounts / Pipeline / Closed Lost / Activities are Salesforce-sourced and trustworthy. `memory/feedback_scout_data_mostly_untested.md`.
- **Research engine cost target**: **$25/week hard ceiling**, lower is better. Round 1 A/B run at ~$0.80/job blended → ~$80/week at saturation, which is 3x over. Round 1.1+ must close the gap. `memory/feedback_research_budget_25_per_week.md`.
- **Outreach sending cap**: 5,000 emails/rolling-7-days per USER (user-level, not mailbox-level). Gmail spillover breaks tracking. `memory/feedback_outreach_sending_cap_5k_weekly.md`.
- **BUG 5 shared-city gap** — runtime blocklist at `memory/public_district_email_blocklist.json` patches the contamination; the permanent code fix in `tools/research_engine.py::_target_match_params` is pending a dedicated plan-mode session. `memory/project_bug5_shared_city_gap.md`.

### Per-session narratives
Session 61 (research engine R1 + diocesan drip + amnesia fix), Session 60 (schedule ID correction + R1 plan), Session 59 (diocesan value extraction + tool hardening), and earlier sessions live in `SCOUT_HISTORY.md`. Grep by `^## Session N` for a specific entry. Active plans: `~/.claude/plans/spicy-sleeping-gadget.md` (research R1 — failed), `~/.claude/plans/rosy-jumping-teacup.md` (diocesan drip rev 2 — shipped).

### Session 58/59 lessons (still load-bearing — full text in memory files)

- **Empirical probing before plan mode catches frame errors, not just detail errors** — `memory/feedback_plans_are_one_shot.md` + Session 59 narrative.
- **Stale-by-design backlogs are always worth auditing before approving** — Session 59 intra_district audit lesson.
- **Haiku saturates on large mixed-topic corpora** — `memory/feedback_haiku_saturation_large_corpus.md`.
- **Haiku is nondeterministic across runs even at temp=0** — `memory/feedback_haiku_nondeterminism_merge_previous.md`.
- **`build_csta_enrichment` helper** lives in `tools/signal_processor.py` (Rule of Three applies: F4 inline, F6/F7/F8 lazy import).
- **Session 57 lessons** archived to `docs/SCOUT_RULES.md` Appendix A.

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
- Every contact MUST have a populated IANA timezone derived from state via `tools.timezone_lookup.state_to_timezone`. Missing tz = skip the contact, never fall back (Rule 17).
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

---

## CRITICAL RULES (top 19 — full rule set in `docs/SCOUT_RULES.md`)

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
17. **Timezone is a hard requirement on every Outreach prospect create.** `tools.outreach_client.validate_prospect_inputs` enforces it at the code boundary — missing or invalid IANA timezone causes the validator to return `passed=False` and `create_prospect` refuses to fire the HTTP request. Derive from state via `tools.timezone_lookup.state_to_timezone`. Never fall back to a default tz; skip the contact and fix the source data. Session 61 diocesan drip lesson.
18. **Never write a new one-shot Outreach prospect loader.** Before writing any prospect-add code, (a) grep `tools/outreach_client.py` for the target function name, (b) check `docs/SCOUT_CAPABILITIES.md`, (c) grep `git log --since=120days` for `prospect` + `load` + `sequence` commits. If the work has been done before but isn't in library code, promote the pattern to `tools/outreach_client.py` + `tools/prospect_loader.py` BEFORE writing a new one-shot. Ephemeral inline Python scripts (S38 CUE loader, S43 C4 1,119-prospect loader) are the root cause of the "did I build this already?" amnesia Steven called out in Sessions 59 and 61. The canonical path is `create_prospect` / `find_prospect_by_email` / `add_prospect_to_sequence` / `prospect_loader.execute_load_plan`.
19. **Never show Outreach backend numeric IDs to Steven — structurally enforced.** `prospect_id`, `sequence_state_id`, `sequence_id`, `mailbox_id`, `owner_id`, `template_id`, `schedule_id` — all meaningless to him, all get translated to human names at the presentation boundary. Prospect ID → "First Last (email@domain)". Sequence ID → the sequence name from `feedback_outreach_schedule_id_map.md` / `get_sequences()` (diocesan 2008-2013 → "Philadelphia/Cincinnati/Detroit/Cleveland/Boston/Chicago diocesan"). Mailbox 11 → "your mailbox". Owner 11 → "you" / "Steven". SequenceState IDs are internal bookkeeping — omit entirely and say "the add to <sequence name>". Raw IDs stay in function return dicts for downstream API calls, but never leak into chat/stdout/Telegram/summary text. Full rule in `memory/feedback_no_outreach_ids_in_chat.md`. Session 61 lesson. **Session 62 structural upgrade:** enforced by `scripts/rule_scanner.py` R19 rule. Scanner regexes: `prospect_id`, `sequenceState`, `mailbox`, `owner`, `template_id`, `schedule_id` followed by digits, plus `sequence 2008–2013` (diocesan numeric). Violations are caught on Stop, logged, and trigger a mandatory correction on the next turn. `label_roots: []` means no qualification can save you — these IDs must not appear in chat at all.
20. **Every number labeled, structurally enforced.** Every numerical claim in any response — percentages, dollar amounts, token counts — must be followed within 100 characters by a label root word: `measured`, `sample`, `estimat`, `extrapolat`, `unknown`, `approximat`, `rough`, `guess`. The label can be in parens `(measured)`, in natural language `— based on measurement`, or as a substring `estimated from the file`. Unlabeled numbers are forbidden even in single-sentence replies, status updates, and casual answers. Violation is caught by the post-turn scanner at `scripts/rule_scanner.py` (run tests via `.venv/bin/python scripts/test_rule_scanner.py`). When the Stop-hook + UserPromptSubmit-injector wrappers at `~/.claude/hooks/scout-stop-scan.sh` + `~/.claude/hooks/scout-violation-inject.sh` are wired, violations log to `~/.claude/state/scout-violations.log` and force a mandatory correction directive on the next user turn. Kill switch: `touch ~/.claude/state/scout-hooks-disabled`. Session 62 incident: Claude quoted three different context-window percentages (9%, 21%, 15%) in 30 minutes without labeling any; Steven installed a full-context hook based on the bad number and had to revoke it. Text rule alone fails because the preflight trigger was too narrow ("recommendation-only"). This rule says "every number, always."

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
