# SCOUT — Claude Code Reference
*Last updated: 2026-04-13 — End of Session 58 (Priorities 1–4 all knocked down — Stage 6-8 carryover shipped, diocesan drip started, CSTA enrichment wired to all 6 scanners, CSTA roster tripled)*

---

## CURRENT STATE — update this after each session

**What's working after Session 58:**
- **F1 intra_district CSTA enrichment wired and live** (commit `e52ce25`). Per-parent-district lookup, inline `_calculate_priority(...) + csta_bonus`, lazy import to avoid circular. 384 existing pending intra_district rows are NOT retroactively enriched (drip is Steven's manual approval cadence).
- **F4/F6/F7/F8 CSTA enrichment wired via `build_csta_enrichment` helper** (commit `3ea1be1`) in `tools/signal_processor.py` next to `enrich_with_csta`. Returns `(enriched_notes, priority_bonus)`, `(base_notes, 0)` on miss. F4 uses it in-file, F6/F7/F8 via lazy import. F1/F2 kept inline (pre-helper).
- **CSTA roster at 77 entries / 41 matchable** (commit `529a919`, up from 39/14 baseline = +193%). Territory coverage: CA=9, CT=1, IL=2, MA=6, MI=2, NE=7, NV=3, OH=3, PA=2, TX=2. Still zero: IN/OK/TN (hand-curation work, see `memory/project_csta_roster_hand_curation_gaps.md`). Refresh: `python3 scripts/fetch_csta_roster.py` — **rerun 2-3 times to let merge-with-previous saturate** (Haiku is nondeterministic across runs even at temp=0). Cost ~$0.40/run.
- **F6 Stage 6 complete** — 26 charter CMOs queued (KIPP Texas 57 schools, KIPP SoCal/TN/MA/PA, IDEA 135 schools, Harmony 60 schools, Aspire, Uplift, ResponsiveEd, etc.).
- **F7 Stage 6 complete** — 41 CTE centers queued (OK tech centers dominant: Autry, Caddo Kiowa, Canadian Valley, Central, Chisholm Trail, Eastern OK County, etc.).
- **F9 `/signal_compliance <state>` handler live** (commit `c947681`). Dispatch path works end-to-end — ran CA pilot, 4 PDFs processed, 0 signals written this run. Handler is fine; scanner quality (Serper PDF discovery surfacing "Faculty Qualifications" style docs instead of district compliance rosters) is a **pre-existing issue, future bug with BUG 1 shape**.
- **`/prospect_approve all` + `/prospect_skip all` now work** (commit `69a3e9c`). Latent bug since Session 49 — Scout's own output told users to type `all` but handlers only parsed integer indices. Fixed by expanding `all` to `range(1, len(_last_prospect_batch)+1)`.
- **6 top-territory archdioceses approved for research via BUG 4 playbook:** Archdiocese of Boston (MA), Philadelphia (PA), Cincinnati (OH), Los Angeles (CA), Cleveland (OH), Detroit (MI). Research running at session end — validate yield in Leads from Research tab at Session 59 start (~15-30 min post-session for all 6 to complete). Remaining 10 dioceses still `pending` in queue.
- **F4 CS funding scanner still live** (`ENABLE_FUNDING_SCAN=True`). 8 HIGH auto-queued prospects from Session 57 run still pending in queue.
- **F2 CSTA enrichment still live.** Competitor displacement scanner augments queue rows on CSTA hit.
- **BUG 4 diocesan research playbook live** (`ENABLE_DIOCESAN_PLAYBOOK=True`).
- **BUG 5 two-stage cross-district filter live** (`ENABLE_RESEARCH_CONTAM_FILTER=True`).
- **Telethon bridge + screencapture + Railway log API** all functional.
- **Leads from Research tab is clean** (Session 56). 482 rows, zero real cross-contamination.
- **CLAUDE.md is lean** — trimmed 41.8K → 12.5K chars this session. Full rule set now at `docs/SCOUT_RULES.md` (13 topic sections + Session 55/57 lesson appendices).

**What's still in-progress / unresolved (carryover for Session 59):**
- **`Prospecting Queue BACKUP 2026-04-10 0010` tab** still in the sheet. Safe to delete.
- **Prospecting Queue is deeply backlogged with pending prospects** — roughly 475+ total across all strategies. Priority tiers (highest first): charter_cmo 780-899 (26 from Stage 6), cs_funding_recipient 800-899 (8 from Session 57), cte_center 760-879 (41 from Stage 6), intra_district 750-849 (384 pending), private_school_network 740-839 (10 dioceses remaining), plus smaller backlogs. Steven's manual approval cadence via `/prospect_approve all` on displayed batches is the "drip."
- **Diocesan email verification ceiling still unresolved.** BUG 4 playbook finds central-office names, not verified emails. Apollo/RocketReach/Hunter is future decision.
- **Sequence builder diocesan branch still not written.** Any approved diocese gets a cold-framed sequence needing manual rewrite.
- **F9 scanner quality (not handler)** — 0 signals produced on CA pilot run. Serper PDF discovery surfaces wrong doc types. Needs BUG 1-shape plan-mode session: empirical Serper probes first, then query redesign.
- **IN/OK/TN CSTA roster still at zero.** Chapter subdomains exist but fetched HTML doesn't list boards. Hand-curation is future work for +15 matchable.
- **`scripts/scout_session.sh` `--effort high` flag** committed in session wrap (commit `1525a7c`). Takes effect on next `scout` session to work around Opus 4.6 medium-effort regression.
- **`.DS_Store` showing up in git status** — macOS noise, safe to ignore.

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 58:** Priorities 1–4 comprehensive knockdown. Stage 6/7/8 (F6/F7/F9/F1), diocesan drip started (6 of 16 approved), CSTA enrichment wired to F4/F6/F7/F8 via helper, CSTA roster 39/14 → 77/41, `/prospect_approve all` bug fixed, CLAUDE.md doc trim. 7 commits (`185a3f2`, `c947681`, `e52ce25`, `3ea1be1`, `69a3e9c`, `529a919`, end-of-session). Plans: `~/.claude/plans/mellow-bouncing-lemur.md` (CLAUDE.md trim).
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits. Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits.
- **Session 53:** Fire drill audit. F2 max_tokens fix. 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.

### What still needs to be done (Session 59 — cleanup + optional sprint)

1. **CLEANUP — drip-approve the queue backlog.** ~475 pending prospects across charter_cmo/cs_funding/cte_center/intra_district/private_school_network strategies. Use `/prospect` + `/prospect_approve all` cadence at Steven's preferred pace. The 384 intra_district rows are the largest bucket — they'll need the most approval rounds. Consider `/prospect_skip all` on low-value strategies if too many.
2. **CLEANUP — delete `Prospecting Queue BACKUP 2026-04-10 0010` tab.** Safe operation, one Telegram instruction.
3. **CLEANUP — validate BUG 4 diocesan playbook yield.** 6 archdioceses are in research at session end. Check `Leads from Research` tab at session start — expect central-office NAMES without verified emails. If yield is poor, Apollo/RocketReach decision becomes urgent.
4. **OPTIONAL — hand-curate IN/OK/TN CSTA board members.** See `memory/project_csta_roster_hand_curation_gaps.md`. Expected +15 matchable entries if done. ~15-30 min manual Google+LinkedIn work.
5. **OPTIONAL — F9 compliance scanner query redesign.** Separate plan-mode session. Same shape as BUG 1 Session 57: empirical Serper PDF probes first (what does `site:ca.gov filetype:pdf "computer science" compliance` actually return vs intended target like district compliance rosters), then iterate query templates. Exit criterion from Session 52 is ≥60% HIGH-confidence validation rate — can't measure until queries return actual district compliance data.
6. **OPTIONAL — approve remaining 10 dioceses** from Session 56 batch if Session 58's first 6 produced useful yield.
7. **OPTIONAL — diocesan email verification upgrade decision** (Apollo/RocketReach/Hunter paid tools, or L8 pattern inference seeding).

### Session 58 lessons (most recent, still load-bearing)
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
