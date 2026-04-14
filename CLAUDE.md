# SCOUT — Claude Code Reference
*Last updated: 2026-04-13 — End of Session 61 (Research Engine Round 1 code shipped across 4 commits; Level 3 Waverly A/B failed verified_quality_gate; root cause documented; flags default OFF preserves v1 production behavior; Round 1.1 planning needed before the flags can flip on.)*

---

## CURRENT STATE — update this after each session

**Session 61 shipped Research Engine Round 1 code across 4 commits. Level 3 Waverly A/B failed the verified_quality gate; Level 3 halted at target 1 per plan's "stop on first failure" rule. Flags default OFF so production is unchanged — v1 behavior is byte-for-byte preserved.**

### Session 61 commits (all on main)

| commit | scope |
|---|---|
| `978499b` | Part 0: shared dedup fix (upgrade-on-collision helper in contact_extractor, rewire extract_from_multiple + ResearchJob._merge_contacts). Level 2 Waverly check: 37/37 contacts preserved, zero regression. 7 unit tests green. |
| `bd7a562` | Part 1: three feature flags on ResearchJob.__init__ (enable_url_dedup, l15_step5_skip_threshold, log_claude_usage). All default OFF. Module-level Claude usage capture in contact_extractor.py is safe across run_in_executor thread boundaries because CPython GIL + serial ResearchQueue guarantee. 20 unit tests green. |
| `21d9b3b` | Part 2: A/B harness (scripts/ab_research_engine.py + ab_analyze.py). Measurement-grade cost from response.usage token counts. --max-cost-usd ceiling. 3 numerical gates. |
| `e62f4be` | Round 1.1 patch: URL dedup keeps longest content per URL (first-occurrence rule lost full-page content to short Serper snippets). 21 unit tests green. |

### Level 3 Waverly A/B — FAIL, stopped at target 1

Two runs against "Waverly School District 145" NE:

| metric | v1 baseline | v2 flags-on (first-wins) | v2 flags-on (longest-wins) |
|---|---|---|---|
| contacts total | 34 / 36 | 20 | 23 |
| contacts verified | **30 / 30** | **19** | **22** |
| claude calls | 134 / 137 | 65 | 69 |
| wall clock (s) | 334 / 329 | 171 | 179 |
| cost usd (measurement) | $0.80 / $0.81 | $0.41 | $0.44 |
| verified_quality_gate (≥95%) | — | **FAIL** (63%) | **FAIL** (73%) |
| cost_reduction_gate (≤90%) | — | PASS | PASS |
| wall_clock_gate (≤105%) | — | PASS | PASS |

**Root cause of verified loss** (13 unique contacts in v1 that v2 missed):

- **URL dedup is lossy for Serper snippets.** Each `_add_raw_from_serper` call appends per-query with different snippet text — the same URL gets 2-4 distinct snippet entries where each snippet highlights sentences matching that query. Dedup by URL (either first-wins OR longest-wins) collapses those to one entry and loses the distinct per-query highlighting. Longest-wins recovered ~3 contacts vs first-wins, but ~8 contacts remain lost.
- **L15 Step 5 skip at threshold=15** drops discovery search contacts. Waverly had >15 VERIFIED before L15 step 5, so the flag triggered and skipped 5 Serper discovery queries + 1 Claude extraction. Estimated 3-5 of the lost 13 contacts came from there.

Both losses are legitimate — neither path can be recovered by a small patch to the existing flags. Round 1 in its current shape is incompatible with the 95% verified quality floor.

**Round 1.1 options (require fresh planning, did NOT ship in S61):**

1. **Per-URL content merge:** instead of dedup, concatenate all distinct contents for a URL into one Claude call. Preserves all snippet text + full page content with one call instead of N. Requires careful token budgeting (20k char cap per extract_contacts call). Most promising, biggest scope change.
2. **Raise L15 Step 5 threshold to 30+:** at threshold 30, Waverly's 30 verified wouldn't trigger the skip. But Conejo Valley / Cincinnati / Cypress-Fairbanks probably also land at 30-40 verified, making the skip almost never fire — savings vanish.
3. **Ship only usage logging, abandon URL dedup + L15 skip:** gives measurement-grade cost data for Round 2 planning but zero cost savings in Round 1. Honest minimum.
4. **Different cost lever entirely:** batch L9 claude calls (5-10 pages per call instead of 1 per page). Round 2 scope but might be bringable forward.

**Round 1 code state: ship as-is.** The flags default OFF so `agent/main.py`'s 4 call sites still produce byte-for-byte v1 behavior. The module-level usage capture is gated on `log_claude_usage=True` — it's off unless the harness explicitly flips it. Test suite is 21/21 green. No production risk. The flags are available as lab instruments for Round 1.1 experimentation.

**Budget burned in Session 61 A/B runs: ~$4.00** (Level 2 Waverly pre-merge check ~$1.50, A/B run 1 ~$1.21, A/B run 2 ~$1.25). Well under the $5 harness ceiling. Level 3 targets 2-5 (Lake Zurich, Conejo Valley, Cincinnati, Cypress-Fairbanks) NOT executed — stopped on first failure per plan rule, saved ~$8.

### Session 61 lessons (most recent, load-bearing)

- **`raw_pages` is not a page list — it's an extraction-request list.** Multiple entries per URL are intentional: different Serper queries produce distinct snippet highlighting for the same URL, and direct-scrape / Firecrawl / Exa layers add full-page versions of the same URL. Any dedup that collapses them to one entry loses information. This wasn't in the Round 1 plan's assumption set because I looked at the dedup target without tracing the population pattern.
- **"Pure cost win with zero quality loss" is a claim that must be verified against real data, not asserted at plan time.** The Round 1 plan assumed URL dedup was lossless. It wasn't. The A/B harness caught this on the very first target — which is exactly what the harness is for — but the plan's estimated impact was wrong by a meaningful margin.
- **95% is a strict floor, not a soft target.** The plan set verified_quality_gate at `v2 ≥ v1 × 0.95` (CLAUDE.md quality bar). Under that rule, losing 8 of 30 verified is a 27% loss — 5.4x the allowed tolerance. No amount of cost savings compensates for that loss under Steven's "no sacrifice" quality rule.
- **Stop-on-first-failure is the right rule.** I saved ~$8 and ~60 min by not running Cincinnati / Conejo / Lake Zurich / Cypress-Fairbanks. The failure pattern is mechanical (Serper snippet loss + L15 Step 5 skip), same root cause on every target. More data points would have confirmed the same finding, not revealed new ones.
- **Level 2 pre-merge checks catch pure regressions; Level 3 A/B checks catch design failures.** Level 2 (stash → run → unstash → diff) proved Part 0 was safe. Level 3 (two engines side-by-side with real targets) proved Part 1 flags were unsafe as designed. Both matter — one is not a substitute for the other.
- **Ship with flags OFF by default. Failed flags stay dark.** The three Round 1 flags exist in `ResearchJob.__init__` but default to values that preserve v1 behavior. Production is unchanged. The next session can iterate on flag behavior without having to revert and re-ship anything.

---

## SESSION 60 HISTORY (kept for continuity)

**Session 60 ended mid-execution at context limit.** Two distinct pieces of work:

### 1. Schedule ID map correction — SHIPPED (commit `846aaed`)

- S59 memory had schedule 1 incorrectly labeled as "Hot Lead Mon-Fri" based on sequence-name clustering (no UI verification)
- S60 verified from Outreach UI screenshots: schedule **1** = "Weekday Business Hours" (legacy default, 131 seqs), schedule **51** = actual "Hot Lead Mon-Fri" (only seq 1999 uses it)
- `tools/outreach_client.py::_DEFAULT_ALLOWED_SCHEDULE_IDS` corrected from `{1, 48, 50, 52, 53}` → `{48, 50, 51, 52, 53}`
- 14/14 outreach_validator unit tests still pass (tests never referenced schedule 1 directly)
- Seq 1999 "!!!2026 License Request Seq (April)" is correctly configured on its real schedule — no migration needed
- `feedback_outreach_schedule_id_map.md` rewritten with UI-verified 5 schedules + legacy/teammate/do-not-use IDs
- `feedback_outreach_delivery_schedule_required.md` rewritten (stale per-type default table replaced)
- New meta-lesson: `feedback_schedule_map_wrong_in_s59.md` — never confirm an ID→name map from sequence-name clustering, only from UI or Steven
- Files committed: `CLAUDE.md`, `tools/outreach_client.py`, `scripts/s60_schedule_lookup.py`

### 2. Research engine Round 1 plan — APPROVED (implementation pending)

**Plan file:** `~/.claude/plans/spicy-sleeping-gadget.md`

Session 60 dedicated the back half to deep exploration of `tools/research_engine.py` (1,795 lines) + `tools/contact_extractor.py`, real per-layer yield measurement from Research Log (N=20 public district jobs), and a pressure-test rebuild of the Round 1 plan. Steven explicitly approved the plan after the pressure-test pass. **Implementation has NOT started.** Next session begins at Commit 1.

**Anchoring data (measurement from 20 real public district jobs):**
- L2 title-variations is the workhorse: 90% hit rate, mean 12.6 contacts, max 30
- L1 direct-title: 75% hit rate, mean 10.4
- L3 linkedin: 75% hit rate, mean 7.7
- L14 conference: 70% hit rate, mean 3.8
- **L16 Exa broad: 25% hit rate but mean 28.6 when it hits, max 58 — variance bomb. When it fires, 10-20 extra pages feed into L9 Claude extraction, amplifying cost by $0.40-1.20/job indirect**
- L4/L5/L11/L12/L13/L20: all low hit rate (10-35%) + low mean yield (1-5 contacts). Candidates for conditional execution in Round 2.

**Two silent quality bugs confirmed by code read:**
- `ResearchJob._merge_contacts` at `tools/research_engine.py:1635-1649` — dedupes by (first, last), silently drops newer contact on name collision
- `extract_from_multiple` at `tools/contact_extractor.py:214-235` — identical bug
- Impact: if page 1 returns "John Smith no email" and page 2 returns "John Smith + VERIFIED email", the page-2 version is silently dropped and the email is lost. Happens today in every research job.

**Round 1 scope (3 parts, 3 commits, zero `agent/main.py` changes):**

- **Part 0 — Shared dedup fix:** extract `_merge_contact_upgrade(existing, new)` helper into `contact_extractor.py`, call from both `_merge_contacts` and `extract_from_multiple`. Upgrade-on-collision: fill email if missing, upgrade confidence VERIFIED > LIKELY > INFERRED > UNKNOWN, fill empty title. Never drop, never downgrade.

- **Part 1 — Three feature flags on `ResearchJob.__init__`**, all defaulting to byte-for-byte v1 behavior:
  - `enable_url_dedup: bool = False` — dedupes `raw_pages` by `url.rstrip("/").lower()` before L9 Claude extraction
  - `l15_step5_skip_threshold: int | None = None` — when set (Round 1 uses 15), skips L15 Step 5 discovery if VERIFIED contact count ≥ threshold. Steps 1-4 still run (verification + enrichment). Only "find more" is skipped.
  - `log_claude_usage: bool = False` — captures `response.usage.input_tokens/output_tokens` via module-level `_capture_usage_enabled` + `_captured_usage` buffer in `contact_extractor.py`. Safe across `run_in_executor` thread boundaries because module globals are shared under CPython GIL + `ResearchQueue` is explicitly serial. `try/finally` in `ResearchJob.run()` ensures balanced start/stop. Attaches `claude_usage` key to result dict.

- **Part 2 — A/B harness** (`scripts/ab_research_engine.py`, new): instantiates two `ResearchJob` objects (flags off vs flags on), runs serially with 30s delay, captures real per-run cost from `response.usage` token counts, computes diff + numerical pass/fail gates (verified_quality ≥ 95% of v1, cost ≤ 90% of v1, wall_clock ≤ 105% of v1), writes JSONL to `/tmp/scout_ab_results.jsonl`, enforces `--max-cost-usd` default $5 ceiling, handles exceptions gracefully. Companion `scripts/ab_analyze.py` aggregates the JSONL.

**Architecture decision:** feature flags in v1 `ResearchJob`, NOT a `research_engine_v2.py` subclass. Rationale: subclass would require copying 200+ lines of `_layer15_email_verification` to change one if-statement. Full rationale in `feedback_feature_flags_not_subclass.md` and the plan file.

**Expected impact:** 10-25% cost reduction `(estimate)`. Round 1 blended is ~$45/week at saturation vs the $25/week hard ceiling — **Round 1 does NOT solve the budget problem alone**, it's the foundation for Round 2 (entity cache, Claude batching, Haiku fallback) and Round 3 (parallelism, territory L0 shortcut) which close the gap.

**5 locked test targets (confirmed in `territory_data`, all cold/no-Active-Account):**

| # | District | State | Enrollment | Tier |
|---|---|---|---|---|
| 1 | Cypress-Fairbanks ISD | TX | 118,470 | Large |
| 2 | Cincinnati Public Schools | OH | 34,860 | Medium |
| 3 | Conejo Valley USD | CA | 15,999 | Medium |
| 4 | Lake Zurich CUSD 95 | IL | 5,703 | Small |
| 5 | Waverly School District 145 | NE | 2,134 | Small |

**Next step (exact, start of next session):** execute Commit 1. Write `scripts/test_round1_unit.py` with 7 failing Part 0 tests (TDD), implement `_merge_contact_upgrade` helper in `contact_extractor.py`, rewrite both dedup functions to use it, run unit tests (must be 7/7 green), run Level 2 pre-merge integration check on Waverly (stash → baseline run → unstash → post-fix run → diff, expected ~14 min wall clock + ~$1.50 API cost), commit as `fix(research): upgrade-on-collision in shared dedup logic`.

### Uncommitted files in working tree

- `scripts/s60_test_target_lookup.py` — untracked. Used to verify 5 test targets against Active Accounts + pull Research Log per-layer yields. Keep for reference; commit alongside Round 1 work or as a standalone measurement-script commit.
- `scripts/s60_verify_test_targets.py` — untracked. Verified 5 candidates against `territory_data.lookup_district_enrollment` enrollment. Caught Park Ridge-Niles CCSD 64 → Lake Zurich CUSD 95 swap (Park Ridge wasn't in the NCES territory master under that name). Keep for reference.
- `.DS_Store` — harmless macOS noise, ignore.

### Session 60 memory files banked (4 new, 2 rewritten)

- NEW `feedback_schedule_map_wrong_in_s59.md` — meta-lesson on ID→name confirmation discipline
- NEW `feedback_scout_primary_target_is_public_districts.md` — hard rule against drifting to diocesan/charter/CTE defaults
- NEW `feedback_dont_default_to_diocese_examples.md` — self-check for "diocese" before sending messages
- NEW `feedback_research_budget_25_per_week.md` — $25/week hard ceiling, not invented numbers
- NEW `feedback_outreach_sending_cap_5k_weekly.md` — Outreach 5k/week user-level cap + Gmail 2k/24hr comparison + spillover analysis
- NEW `feedback_job_definition_user_request.md` — "job" = user-facing request, not atomic entity
- NEW `feedback_feature_flags_not_subclass.md` — architecture lesson from the S60 pressure test
- REWRITTEN `feedback_outreach_schedule_id_map.md` — UI-verified 5 schedules + legacy table
- REWRITTEN `feedback_outreach_delivery_schedule_required.md` — correct per-type defaults

### Session 60 lessons (most recent, load-bearing)

- **Don't default to diocese/charter/CTE examples.** Public school districts in territory states are Scout's primary lane. S58-S60 drift happened because diocesan data was the freshest thing in memory and I reached for it reflexively. Hard self-check for the word "diocese" before sending drafts on non-diocesan topics.
- **Feature flags beat subclass for shipping variant behavior on large classes.** Subclass requires copying 200+ line methods to override one if-statement. Flags defaulting to current behavior preserve byte-for-byte production state with zero risk.
- **Real token counts via `response.usage` replace formula-based cost estimation.** The Anthropic SDK returns exact input/output tokens on every call — we just weren't logging them. Module-level capture buffer is safe across `run_in_executor` thread boundaries because (a) CPython GIL makes `list.append` atomic, (b) `ResearchQueue` is explicitly serial one-job-at-a-time.
- **`threading.local()` does NOT survive `run_in_executor`.** Initial design used thread-local for usage capture; caught during pressure-test that `extract_from_multiple` runs in the executor thread pool while `ResearchJob.run()` runs in the main asyncio thread — thread-local entries don't cross thread boundaries. Module globals do.
- **Steven's budget is $25/week maximum, lower is better.** Not the $50-150/week I guessed earlier in S60. Derived from Outreach 5k/week cap → ~100 atomic jobs/week saturation → $0.25/job max. Do not quote higher numbers as "the target."
- **Outreach 5k/rolling-7-days is user-level, not mailbox-level.** Adding mailboxes doesn't help. Gmail spillover breaks tracking. Second Outreach seat is the only clean escape valve.
- **`territory_data.lookup_district_enrollment` fails on historical Research Log rows** because old writer truncated state field to "Te"/"Oh"/"Ok". Fresh rows use correct 2-letter abbreviations. Historical data quality issue, not a current bug. Blocks enrollment-based tier routing in Round 1 — deferred to Round 3.
- **L16 Exa broad is the variance bomb.** 25% hit rate but mean 28.6 contacts when it hits, max 58 (Columbus City Schools). When fires, 10-20 extra pages feed into L9 Claude extraction, indirectly amplifying L9 cost by $0.40-1.20/job. Round 2 candidate for conditional execution only when L9 first pass finds <15 VERIFIED.

---

## WHAT SHIPPED BEFORE SESSION 60 (still load-bearing)

**From Session 59:**

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
  - Schedule allowlist via `OUTREACH_ALLOWED_SCHEDULE_IDS` env var → default `{48, 50, 51, 52, 53}` (corrected in S60 — S59 had schedule 1 incorrectly labeled as "Hot Lead Mon-Fri"; the real "Hot Lead Mon-Fri" is schedule 51)
  - Banned-phrase body scan (16 phrases + em/en dash detection)
  - Required `codecombat.com/schools` in ≥2 step bodies (opt-in via `require_cc_schools_link`, default True)
  - Meeting link (if provided) required in ≥1 step body
  - Repetition policy: `one pager` / `one-pager` max 1x across all bodies
  - Min step interval sanity check: default 432000s (5 days cold), override for hot-lead/license-request flows
  - `verify_after_create=True` default, set False for bulk creation to avoid rate limiting
  - **Live-tested:** all 6 diocesan sequences verified. Philadelphia + Cincinnati initially failed on "15 minutes" in step 3 bodies (validator caught real violations rounds 1-3 had missed); PATCHed templates 43923 and 43928 in place; re-verified clean.
  - **Unit tests:** `scripts/test_outreach_validator.py` — 14 cases, all pass in <1s, zero API calls.

- **Steven's 5 delivery schedule IDs — verified S60 against Outreach UI dropdown screenshots** (stored in `memory/feedback_outreach_schedule_id_map.md`):
  - `48` = SA Workdays (seq 1939 "ACTE '25 Seq")
  - `50` = C4 Tue-Thu Morning (seq 1995 "C4 License Re-Engage — Teachers" cluster)
  - `51` = **Hot Lead Mon-Fri** (seq 1999 "!!!2026 License Request Seq (April)") — **S59 had schedule 1 wrongly labeled as "Hot Lead Mon-Fri"; corrected in S60 after Steven read the UI dropdown**
  - `52` = Admin Mon-Thurs Multi-Window (the 6 diocesan sequences 2008–2013)
  - `53` = Teacher Tue-Thu Multi-Window (seq 1857 "FETC 2025")
  - Schedule 1 is **"Weekday Business Hours"** — a legacy default with 131 sequences on it, but NOT one of the 5 targeted schedules. Out of the allowlist.

- **3 new process rules** appended to `docs/SCOUT_RULES.md` Section 1:
  - Write the audit question in plain English BEFORE running code
  - Never cite cost/time/count/percentage numbers without labeling provenance (`measurement / sample / extrapolation / estimate / unknown`)
  - Never present a guess as a fact

- **4 new preflight checklists** added to this file's Preflight section below — Outreach work, Sequence content, Sheet audit, Cost/time estimate. Must be loaded at the start of any task matching those categories.

- **16 memory files banked** in `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/`:
  - `feedback_schedule_map_wrong_in_s59.md` — S60 meta-lesson: never cite an ID→name map as confirmed without reading the name from the UI
  - `feedback_code_enforcement_beats_process_rules.md` — the meta-lesson: tool guards > doc rules wherever code can enforce
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
- **Session 60:** Two bodies of work. (1) Schedule ID map correction — shipped (commit `846aaed`). S59 memory had schedule 1 labeled as "Hot Lead Mon-Fri" from sequence-name clustering; S60 verified from Outreach UI that schedule 1 is "Weekday Business Hours" (legacy default, 131 seqs) and the real "Hot Lead Mon-Fri" is schedule 51. Default allowlist corrected to `{48, 50, 51, 52, 53}`. Seq 1999 is correctly configured on its real schedule — no migration needed. (2) Research engine Round 1 plan — approved after pressure-test pass (plan file: `~/.claude/plans/spicy-sleeping-gadget.md`). Feature-flag architecture (not subclass), 3 flags on `ResearchJob.__init__`, A/B harness with real token logging via `response.usage`, numerical pass/fail gates, 5 locked test targets. **Implementation not yet started — next session starts at Commit 1 (Part 0 shared dedup fix + 7 unit tests + Level 2 Waverly integration check).** 4 new memory files banked (anti-drift, budget, sending cap, feature flags) + 2 rewritten (schedule map, delivery schedule required). 20 total memory files banked across S60. 1 commit: `846aaed`. Plan file: `~/.claude/plans/spicy-sleeping-gadget.md`.
- **Session 59:** Diocesan value extraction + tool hardening. Rounds 1-3 shipped 12 user-visible failures (missing meeting link, "one pager" CTA repetition, em dashes, auto-gen descriptions, rogue schedule 19, 60x-too-short intervals, F1 audit category error, fabricated cost numbers, "F3 retired" fabrication, etc.) — every one caught by Steven in the Outreach UI or sheet audit, not self-caught. Root cause was shipping on API 2xx + memory not loaded, not reasoning quality per se. Round 4 installed tool hardening: `validate_sequence_inputs` + `verify_sequence` in `tools/outreach_client.py` make 8 of 12 failure modes structurally impossible at the code boundary, plus 14 unit tests. All 6 diocesan sequences 2008-2013 verified clean in Outreach with correct schedule/owner/intervals/bodies. Added 3 process rules to `docs/SCOUT_RULES.md` + 4 preflight checklists to this file. 15 memory files banked. F1 stays active after Steven pushback on flawed audit. Research engine bulk-mode optimization deferred to Session 60 as a blocker for backlog drain. Commits: `042f146`, `4051f53`, `7c162b6`, `eff3786`, `880d77b`, `1f22991`, `08c8f98` (+ wrap commit). Plan: `~/.claude/plans/lexical-swinging-pelican.md` (v3 after 2 pressure-test passes).
- **Session 58:** Priorities 1–4 comprehensive knockdown. Stage 6/7/8 (F6/F7/F9/F1), diocesan drip started (6 of 16 approved), CSTA enrichment wired to F4/F6/F7/F8 via helper, CSTA roster 39/14 → 77/41, `/prospect_approve all` bug fixed, CLAUDE.md doc trim. 7 commits (`185a3f2`, `c947681`, `e52ce25`, `3ea1be1`, `69a3e9c`, `529a919`, end-of-session). Plans: `~/.claude/plans/mellow-bouncing-lemur.md` (CLAUDE.md trim).
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits. Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits.
- **Session 53:** Fire drill audit. F2 max_tokens fix. 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.

### What still needs to be done (Session 61 — execute Round 1 + carryover decisions)

**PRIMARY — execute the approved research engine Round 1 plan** (`~/.claude/plans/spicy-sleeping-gadget.md`):

1. **Commit 1 — Part 0 shared dedup fix** (~2 hours including integration check):
   - Write `scripts/test_round1_unit.py` with 7 failing TDD tests for `_merge_contact_upgrade`
   - Implement helper in `tools/contact_extractor.py`
   - Rewrite `extract_from_multiple` (lines 214-235) and `ResearchJob._merge_contacts` (`tools/research_engine.py:1635-1649`) to use the helper
   - Run unit tests — must be 7/7 green
   - Level 2 pre-merge integration check against Waverly (stash → baseline run → unstash → post-fix run → diff). Two real research jobs, ~14 min wall clock, ~$1.50 real API cost. Expected: `post.contacts_verified >= pre.contacts_verified`.
   - Commit as `fix(research): upgrade-on-collision in shared dedup logic (recovers silently-lost VERIFIED emails)`
2. **Commit 2 — Part 1 feature flags** (~2 hours):
   - Add 13 more unit tests (5 URL dedup + 4 L15 Step 5 skip + 4 usage logging)
   - Add 3 flags to `ResearchJob.__init__` defaulting to v1 behavior
   - URL dedup block at top of `_layer9_claude_extraction` gated on `enable_url_dedup`
   - L15 Step 5 skip check gated on `l15_step5_skip_threshold`
   - Module-level `_capture_usage_enabled` + `_captured_usage` + helpers in `contact_extractor.py`
   - `start_usage_capture`/`stop_usage_capture` in `ResearchJob.run()` via `try/finally` gated on `log_claude_usage`
   - `claude_usage` key added to result dict when logging enabled
   - Run all 20 unit tests — must be 20/20 green
   - Commit as `feat(research): add round 1 feature flags (url_dedup, l15_step5_skip, claude_usage_log)`
3. **Commit 3 — Part 2 A/B harness** (~2 hours):
   - Create `scripts/ab_research_engine.py` (~250 lines)
   - Create `scripts/ab_analyze.py` (~50 lines)
   - Add `*.jsonl` to `.gitignore`
   - Smoke test against Waverly with `--max-cost-usd 2`
   - Commit as `feat(ab): research engine v1-vs-v1-with-flags A/B harness with real token logging`
4. **Level 3 full A/B validation run** (~45 min wall clock, ~$5-10 real API cost):
   - Run harness against all 5 locked targets (Waverly → Lake Zurich → Conejo Valley → Cincinnati → Cypress-Fairbanks)
   - Aggregate via `ab_analyze.py`
   - All 5 targets must pass 3 numerical gates (verified ≥ 95%, cost ≤ 90%, wall clock ≤ 105%)
   - If all pass → Round 1 is validated, Round 2 planning unlocks
   - If any fail → investigate, iterate, re-run

**CARRYOVER FROM SESSION 59 (still pending, not Round 1 scope):**

5. **STEVEN ACTION — activate the 6 diocesan sequences** (IDs 2008-2013) in Outreach UI. All verified clean via `verify_sequence`. Philadelphia + Cincinnati are the gold targets (20+ verified central-office contacts each).
6. **BUG 5 code fix** in `tools/research_engine.py:_target_match_params`. Shared-city gap (Pittsburgh/OKC/Omaha etc dioceses share city tokens with public districts). Runtime `public_district_email_blocklist.json` is current patch. Separate plan-mode session.
7. **9 pending dioceses review** with per-diocese blocklist-gated cleanup. Pittsburgh/OKC/Omaha first. Blocked on BUG 5 fix or blocklist enforcement wired into engine.
8. **OPTIONAL — F9 compliance scanner query redesign.** Separate plan-mode session. Empirical Serper PDF probes first. Exit criterion ≥60% HIGH validation rate.
9. **OPTIONAL — LA archdiocese research restart.** Hand-seed with `lacatholicschools.org` and rerun.
10. **OPTIONAL — IN/OK/TN CSTA hand-curation.** +15 matchable entries. ~15-30 min manual work.
11. **DEFERRED — cold_license_request 1,245 + winback 247 stale March backlogs.** Dedicated plan-mode session to decide purge vs cherry-pick vs retire. Blocked on research engine Round 2/3 completion.
12. **FUTURE — wire `create_sequence` into `_on_prospect_research_complete` handler.** Tool hardening is in place so the wiring is safe when it ships.

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

### Session 57 lessons
*Archived to `docs/SCOUT_RULES.md` Appendix A (full prose) — no longer duplicated here.*

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
