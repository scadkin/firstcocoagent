# SCOUT — Claude Code Reference
*Last updated: 2026-04-14 — End of Session 61 (two bodies of work: Research Engine Round 1 shipped but Level 3 Waverly gate failed and flags are parked default-OFF; diocesan drip library + amnesia fix shipped including SessionStart hook that auto-loads docs/SCOUT_CAPABILITIES.md; 63 diocesan contacts assigned across Mon-Thu, canary verified clean, Batch 1-4 live writes start Tue Apr 14 morning via `scripts/diocesan_drip.py --execute`. 9 commits on main.)*

---

## CURRENT STATE — update this after each session

**Session 61 had two distinct bodies of work.** First half: Research Engine Round 1 code shipped across 4 commits but Level 3 Waverly A/B failed the verified quality gate — flags are parked default-OFF, Round 1.1 planning needed. Second half: diocesan drip library shipped (promoted S38/S43 ephemeral prospect-add patterns into canonical tools/outreach_client.py + tools/prospect_loader.py), 63 diocesan contacts assigned across Mon-Thu buckets, throwaway canary verified clean in the Chicago diocesan sequence. Amnesia root-cause fix also shipped: new docs/SCOUT_CAPABILITIES.md inventory auto-injected into every session via a SessionStart hook in ~/.claude/settings.json. **Next session's first action:** `.venv/bin/python scripts/diocesan_drip.py --execute` to run Tuesday's live batch (17 contacts, ~2.7 hours).

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

### Session 61 second half — diocesan drip library + amnesia root-cause fix

After parking the research engine, Steven asked me to add the diocesan prospects to sequences 2008-2013 (which he'd already activated) with day + time stagger. My first draft plan framed it as "net new capability" — that framing was WRONG and Steven caught it. Sessions 38 and 43 had already done POST /prospects + POST /sequenceStates work, but always as ephemeral inline Python that never got committed, so every subsequent session I opened `tools/outreach_client.py`, saw no `create_prospect` function, and concluded the capability didn't exist. Same amnesia had hit Session 59 earlier. The corrected plan (`~/.claude/plans/rosy-jumping-teacup.md` rev 2) treats the amnesia itself as Problem B and fixes it structurally alongside the drip.

**5 commits on main this half of the session:**

| commit | scope |
|---|---|
| `fdf6920` | Promote prospect-add pattern to library: 4 new functions in `tools/outreach_client.py` (`validate_prospect_inputs`, `create_prospect`, `find_prospect_by_email`, `add_prospect_to_sequence`) + new `tools/timezone_lookup.py` (50 states → IANA) + new `tools/prospect_loader.py` (reusable bulk loader with resumable state file + jittered sleep + pre-flight sequence-enabled check + Contact/LoadPlan dataclasses + `build_load_plan` round-robin) + new `scripts/diocesan_drip.py` thin CLI (5 subcommands: `--assign`, `--dry-run`, `--canary`, `--canary-cleanup`, `--execute`, `--verify`) + new `scripts/test_diocesan_drip.py` (15 unit tests). 29 unit tests green total. |
| `fcd1417` | Amnesia root-cause fix. New `docs/SCOUT_CAPABILITIES.md` (~360 line inventory of every committed Scout capability with file:line pointers, organized by module) + new CLAUDE.md PREFLIGHT: Prospect add to sequence block + Rule 17 (timezone required via `validate_prospect_inputs` code boundary) + Rule 18 (no ephemeral prospect scripts — grep library and git log before writing new one-shots). New memory file `feedback_timezone_required_before_sequence.md`. |
| `fb941a1` | Rule 19 (never show Outreach backend IDs in chat). Memory file `feedback_no_outreach_ids_in_chat.md` with the full translation table (prospect_id → name+email, sequence_id → diocesan name, mailbox_id → "your mailbox", sequenceState IDs → omit entirely). |
| `4d8ec58` | Documented two scope gaps discovered via 403s during canary cleanup: `prospects.delete` (we have `prospects.write` but not delete) and `mailboxes.read` (confirmed via `get_mailboxes()` 403). Both gaps need to be added on next OAuth re-auth. |

**Not in the repo but persistent on the local machine (user-level config):**
- `~/.claude/settings.json` — added `SessionStart` hook block that runs `cat /Users/stevenadkins/Code/Scout/docs/SCOUT_CAPABILITIES.md` on every session start. The content becomes injected session context exactly like the Vercel plugin's knowledge-update banner. **Next session will automatically see the capabilities inventory before Claude proposes any work.**
- `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/` — 3 new memory files banked (listed below). MEMORY.md index updated.

**Diocesan drip state (live-writes start Tuesday):**

- `data/diocesan_drip_state.json` holds 63 contacts assigned round-robin across 4 business days, VERIFIED first within each diocese. Per-day totals: Mon 17, Tue 17, Wed 15, Thu 14.
- **Expected 65 dropped to 63** because 2 leads had empty first-name fields in the Leads tab and the validator refused to create them: (a) the single Chicago contact (last name "Allen", `tallen@archchicago.org`) → Chicago diocesan sequence ships empty, (b) one Philadelphia contact (last name "Ricci", `mricci@smspa.org`). Both skipped per Steven's explicit decision; he can hand-fix first names in the sheet and re-run `--assign` later to reclaim them.
- Exclusion list: 3 broken emails — `[email` obfuscation placeholder for Michael Kennedy (Cincinnati), both O'Brien apostrophe-local-part variants (Cincinnati).
- Mailbox = your mailbox (confirmed by reading existing sequenceStates on 1999/1939/1857). Owner = you (user 11, but per Rule 19 never surface the ID). Tags on every prospect: `diocesan-drip-2026-04` + `diocesan-drip-<diocese-slug>`.

**Canary verification — PASSED.** A throwaway "Scout Canary" prospect at `scout-canary-<ts>@codecombat.test` (IANA-reserved `.test` TLD → unresolvable, no real mail delivered) was created and added to the Chicago diocesan sequence. Steven screenshot-confirmed it landed on Step 1 (Auto email) with the right sequencer, sending in 6h. Cleaned up: sequenceState DELETE succeeded cleanly (204). Prospect DELETE returned 403 — `prospects.delete` scope not granted. Steven then manually deleted the orphaned prospect from Outreach UI.

**Session 61 second-half lessons (load-bearing):**

- **The ephemeral-script pattern IS the amnesia.** Sessions 38 and 43 each built `POST /prospects` + `POST /sequenceStates` inline in a heredoc or /tmp/ script that ran once and vanished. Every subsequent session I open `tools/outreach_client.py`, see no `create_prospect` function, and conclude the capability doesn't exist. Rule 18 now requires grepping library code AND `git log --since=120days` AND `docs/SCOUT_CAPABILITIES.md` before writing any new one-shot prospect-add code. The fix is structural: `docs/SCOUT_CAPABILITIES.md` + SessionStart hook force the inventory into every session's context.
- **CLAUDE.md trim moves institutional memory out of the auto-loaded window.** Session 53 extracted `docs/SCOUT_REFERENCE.md`, Session 58 extracted `docs/SCOUT_RULES.md`. Both files are load-bearing but NOT auto-loaded — CLAUDE.md just says "read by section or grep by keyword" with no forcing function. The SessionStart hook fix is the forcing function for the NEW capabilities index. If you want the FULL SCOUT_RULES.md / SCOUT_REFERENCE.md content in auto-loaded context too, that's a trivial extension of the hook — just add them to the `cat` command.
- **Code enforcement beats process rules wherever possible.** The timezone rule (Rule 17) is enforced by `validate_prospect_inputs` refusing to fire on empty/invalid IANA — NOT by "remember to populate the field." Same meta-principle as `feedback_code_enforcement_beats_process_rules.md`. The prospect-add amnesia fix is a hybrid: structural (library code + capability inventory + SessionStart hook) for what can be automated, process rule (Rule 18) for the judgment call before writing new code.
- **Never show Outreach backend numeric IDs to Steven.** He reads `prospect_id=669325, sequence 2013, mailbox 11` as pure noise — meaningless strings that make the assistant feel like a log terminal. Rule 19 requires translating at the presentation boundary: prospect_id → "First Last (email@domain)", sequence_id → diocesan name, mailbox → "your mailbox", sequenceState → omit entirely. Raw IDs stay in function return dicts for downstream API calls but never leak into chat/stdout/Telegram summaries. Full translation table in `memory/feedback_no_outreach_ids_in_chat.md`.
- **`raw_pages` in research_engine is an extraction-REQUEST list, not a page list.** Multiple entries per URL are intentional: Serper adds per-query snippets with different highlighting, direct scrape / Firecrawl / Exa add full-page markdown. Any URL-based dedup loses information. Round 1 URL dedup flag is lossy and stays OFF. `memory/feedback_raw_pages_is_extraction_requests.md`.

**Memory files banked in Session 61 second half:**

- `feedback_timezone_required_before_sequence.md` — Rule 17, code-enforced timezone
- `feedback_no_outreach_ids_in_chat.md` — Rule 19, translation table
- `feedback_raw_pages_is_extraction_requests.md` — research engine lesson (first half)

**Uncommitted state at end of Session 61:**

- `.DS_Store` — harmless macOS noise, ignore.
- `data/diocesan_drip_state.json` — gitignored, holds the 63-contact assignment plan.
- `data/diocesan_drip_audit.jsonl` — will be created on first `--execute` run (gitignored).
- `/tmp/scout_*.py` test probes — ephemeral, not committed.

**Exact next step (start of Session 62):**

```bash
cd /Users/stevenadkins/Code/Scout
.venv/bin/python scripts/diocesan_drip.py --execute
```

This runs Tuesday's batch (17 contacts) with 5-15 min jittered sleeps between POSTs. Total wall clock ~2.5-3 hours. The script reads `data/diocesan_drip_state.json`, picks up the day bucket for today's date via `datetime.now(ZoneInfo('America/Chicago')).date()`, filters to pending contacts, verifies each target sequence is still enabled, dedups via `find_prospect_by_email`, creates prospects, adds them to sequences, updates state file atomically after every POST, writes one line per contact to `data/diocesan_drip_audit.jsonl`.

If Steven wants Monday's batch caught up (it was skipped because he called EOD on Apr 13 night), add `--force-day 2026-04-13` and run once for Monday before running the Tuesday batch. Or run twice back-to-back. Both are resumable via the state file.

After Tuesday's batch completes, `scripts/diocesan_drip.py --verify` will read the state file and compare against live Outreach sequenceStates for all 6 sequences.

Wednesday's Session 63 and Thursday's Session 64 each run `--execute` once more. After Thursday, run `--verify` for the final audit.

---

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

### Recent session narratives (full detail in `SCOUT_HISTORY.md`)

- **Session 61:** Research Engine Round 1 feature-flag implementation + Level 3 Waverly A/B failure + Round 1.1 deferred + diocesan drip library + SCOUT_CAPABILITIES inventory + SessionStart hook + Rules 17/18/19. 9 commits. Plans: `~/.claude/plans/spicy-sleeping-gadget.md` (research engine, implementation failed verified_quality_gate), `~/.claude/plans/rosy-jumping-teacup.md` (diocesan drip rev 2, implementation shipped).
- **Session 60:** Schedule ID map correction + research engine Round 1 plan approved. Plan: `~/.claude/plans/spicy-sleeping-gadget.md`.
- **Session 59:** Diocesan value extraction + Session 59 round 4 tool hardening (`validate_sequence_inputs` + `verify_sequence` + allowlist). Plan: `~/.claude/plans/lexical-swinging-pelican.md`.
- **Sessions 52-58:** see `SCOUT_HISTORY.md` for bug fixes, tool additions, and lessons banked.

### Session 62 carryover (non-diocesan work, not blocking Tue drip)

1. **BUG 5 code fix** in `tools/research_engine.py::_target_match_params`. Shared-city gap. Plan-mode session required.
2. **Round 1.1 research engine plan.** Per-URL content MERGE (not dedup) as the most promising cost lever. L15 Step 5 threshold rethink. L9 batch-mode Claude calls. All flags currently default OFF; measurement instrument (`log_claude_usage`) works and should be reused.
3. **9 pending dioceses review** — Pittsburgh/OKC/Omaha contamination risk. Blocked on BUG 5.
4. **OPTIONAL:** F9 compliance scanner query redesign, LA archdiocese research restart, IN/OK/TN CSTA hand-curation.
5. **DEFERRED:** 1,245 cold_license_request + 247 winback March backlogs. Dedicated plan-mode session.
6. **FUTURE:** wire `prospect_loader.execute_load_plan` into `_on_prospect_research_complete` so research-complete callbacks auto-load prospects into their campaign sequences without manual script runs.

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
19. **Never show Outreach backend numeric IDs to Steven.** `prospect_id`, `sequence_state_id`, `sequence_id`, `mailbox_id`, `owner_id`, `template_id`, `schedule_id` — all meaningless to him, all get translated to human names at the presentation boundary. Prospect ID → "First Last (email@domain)". Sequence ID → the sequence name from `feedback_outreach_schedule_id_map.md` / `get_sequences()` (diocesan 2008-2013 → "Philadelphia/Cincinnati/Detroit/Cleveland/Boston/Chicago diocesan"). Mailbox 11 → "your mailbox". Owner 11 → "you" / "Steven". SequenceState IDs are internal bookkeeping — omit entirely and say "the add to <sequence name>". Raw IDs stay in function return dicts for downstream API calls, but never leak into chat/stdout/Telegram/summary text. Full rule in `memory/feedback_no_outreach_ids_in_chat.md`. Session 61 lesson.

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
