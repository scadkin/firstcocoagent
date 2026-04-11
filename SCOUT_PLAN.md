# SCOUT MASTER PLAN
*Last updated: 2026-04-11 — End of Session 56 (Priority 0 historical contamination cleanup + BUG 4 diocesan playbook shipped)*

---

## YOU ARE HERE → Session 56 closed Priority 0 (historical cross-contamination cleanup) AND shipped BUG 4 (F8 diocesan research playbook). Priority 0: verified all 23 audit-flagged rows against Serper + HTTP checks, reassigned 10 real contacts to their correct districts (4 Epic Charter → Collinsville/Spiro/Bristow, 2 Archdiocese → ROWVA/CHSD218, 2 Guthrie → Hartshorne/Wyandotte, 1 Columbus → Worthington, 1 Irving STEAM → LAUSD), dropped 1 (out-of-territory ISD 88 Foundation MN), left 12 false positives alone (LAUSD/DSUSD/SBCUSD abbreviation mismatches — all real). Priority 1: BUG 4 diocesan playbook shipped one-shot (commit `06f8386`) after full brainstorm + ruthless pressure-test + empirical foundation verification (confirmed Liferay+React diocesan CMS → L6 dead, Serper snippets via `_add_raw_from_serper` carry yield). 16 diocesan domains verified up front. Smoke test on Archdiocese of Chicago: playbook active (Cross-Contam Dropped=28, L12 skipped, L4 pre-seed engaged), zero hard contamination, 5 real Archdiocese central-office contacts found (Richmond Superintendent, Craig Deputy Superintendent, Simunovic Leadership Coach, DiCello CIO, Mannino CFO). 25 stale pre-playbook CPS-contaminated rows cleaned out of No Email tab. 23 private school networks queued via `/prospect_private_networks`. **Next up: BUG 1 (F4 funding scanner) — Priority 2.** 2 bugs remain before Session 52 Stage 6-8 carryover.

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
