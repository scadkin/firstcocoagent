# SCOUT — Claude Code Reference
*Last updated: 2026-04-11 — End of Session 57 (BUG 1 + BUG 2 closed — zero Fire Drill Audit bugs remain)*

---

## CURRENT STATE — update this after each session

**What's working after Session 57:**
- **F4 CS funding scanner live** (`ENABLE_FUNDING_SCAN=True`). 6–7 queries × 13 states × ~$0.09/scan. Per-state chunked Haiku at `temperature=0`, `STATE_DOE_NAMES` constant mapped to actual proper agency names, `STATE_CS_PROGRAMS` shrunk to verified-3. Oracle gate (`scripts/f4_oracle.json`, 14 rows) + replay harness (`scripts/f4_serper_replay.py`). Live Railway run via `/signal_funding`: 43 signals + 8 HIGH auto-queued prospects.
- **F2 CSTA enrichment wired and live.** F2's HIGH-confidence auto-queue block calls `enrich_with_csta(district, state)` and augments the queue row on match (notes prepended, priority +50). F1/F4/F9/F6/F7/F8 wiring pending.
- **CSTA roster is static reference data** at `memory/csta_roster.json` (39 entries, 14 matchable across CA/PA/OH/TX). Refresh manually via `python3 scripts/fetch_csta_roster.py`. Committed to git.
- **`district_prospector.add_district` accepts `priority_bonus: int = 0`** kwarg — default 0 preserves every existing call site. Any enrichment source can use it.
- **`ENABLE_CSTA_SCAN=False` permanently.** Old `scan_csta_chapters` is dead code kept for rollback safety. `/signal_csta` now displays roster grouped by state.
- **BUG 4 diocesan research playbook live** (`ENABLE_DIOCESAN_PLAYBOOK=True`). 16 Catholic dioceses pending approval — Session 58 Priority 2.
- **BUG 5 two-stage cross-district filter live** (`ENABLE_RESEARCH_CONTAM_FILTER=True`).
- **Telethon bridge + screencapture + Railway log API** all functional for Claude Code → Scout end-to-end orchestration.
- **Leads from Research tab is clean** (Session 56). 482 rows, zero real cross-contamination.

**What's still in-progress / unresolved (carryover for Session 58):**
- **`Prospecting Queue BACKUP 2026-04-10 0010` tab** still in the sheet. Safe to delete.
- **Sequence builder diocesan branch not written.** 16 pending Catholic dioceses will produce cold-framed sequence docs needing manual rewrites if approved as-is.
- **Diocesan email verification ceiling.** Playbook finds central-office names but can't produce VERIFIED emails without paid tools (Apollo/RocketReach/Hunter) or L8 pattern inference.
- **CSTA enrichment only wired to F2.** F1/F4/F9/F6/F7/F8 integrations pending — one-line add per scanner.
- **Session 52 Stages 6-8 carryover still untouched.** Charter CMOs + CTE centers, F9 CA pilot, F1 backlog drip (384 pending `intra_district` rows).

### Recent sessions (details in SCOUT_PLAN.md + SCOUT_HISTORY.md)
- **Session 57:** BUG 1 (F4 query redesign + harness + oracle gate + enable flip) + BUG 2 (F5 retired, CSTA enrichment lookup built, F2 wired). 4 commits (`54e7fed`, `2c8ebfb`, `a2d43ea`, `69ec3b8`). Plans: `~/.claude/plans/purring-crafting-scroll.md` + `~/.claude/plans/bug2-csta-enrichment.md`
- **Session 56:** Historical contamination cleanup + BUG 4 diocesan research playbook shipped. 1 commit (`06f8386`). Plan: `~/.claude/plans/frolicking-swimming-sedgewick.md`
- **Session 55:** BUG 3 sentinel close-out + BUG 5 two-stage filter + Telethon bridge. 8 commits. Plan: `~/.claude/plans/abundant-finding-riddle.md`
- **Session 54:** BUG 3 repair + writer fixes. 7 commits. Plan: `~/.claude/plans/sunny-riding-aurora.md`
- **Session 53:** Fire drill audit. F2 max_tokens fix (commit `7c345a07`). 5 silent-failure bugs discovered.
- **Session 52:** Session 51 audit + 3 BLOCKER fixes. 6 commits.
- **Session 51:** Tier B+C Lead Gen (F5/F6/F7/F8/F9/F10 shipped), F4+F2 URL bug fix, F2 complete rewrite.

### What still needs to be done (Session 58 — post-bug-sprint)

1. **PRIORITY 1 — Session 52 Stages 6-8 carryover.** Charter CMOs + CTE centers (Stage 6), F9 compliance CA pilot (Stage 7, Signals-only validation toward ≥60% exit criterion), F1 backlog drip (Stage 8 — 384 pending `intra_district` rows). All parked since Session 52 behind the bug-fix sprint. Now unblocked.
2. **PRIORITY 2 — Diocesan approval drip.** 16 Catholic dioceses pending in the Prospecting Queue since Session 56. Approve in batches via `/prospect_approve` — playbook activates automatically. Expect name-only yield. Write sequence_builder diocesan branch BEFORE approving OR accept cold-framed fallback + manual rewrites.
3. **PRIORITY 3 — Extend CSTA enrichment to other scanners.** Wire `enrich_with_csta` into F1/F4/F9 auto-queue blocks (one-line call each, same pattern as F2). F6/F7/F8 seed-queuers get it too.
4. **PRIORITY 4 — Grow the CSTA roster.** Current fetcher surfaced 14 matchable entries. Options: (a) hand-curate known board members for sparse states (IL, TX, MA, NE, etc.); (b) iterate fetcher queries for non-csteachers.org sources; (c) accept current yield and let it grow organically on quarterly refresh.
5. **Cleanup items:**
   - Delete `Prospecting Queue BACKUP 2026-04-10 0010` tab
   - Approve 8 F4 auto-queued prospects from Session 57's live run (Midland ISD, Berwick, Northwest Local, Sto-Rox, Philadelphia, DuBois, Riverside, Tippecanoe — Tippecanoe is borderline Indiana DOE robotics, consider skipping)
   - Consider diocesan email verification upgrade (paid Apollo/RocketReach/Hunter, or L8 pattern inference seeding)

### Session 57 lessons (full prose in `docs/SCOUT_RULES.md` Appendix A)
- Static finite directories are **lookups, not scanners** (CSTA, dioceses, CTE, charters → `memory/*.json` + enrichment helper, not daily scan).
- Haiku extractions in validation harnesses need `temperature=0.0` or the gate flip-flops between runs.
- **Empirical Serper/httpx probes BEFORE plan mode** — both BUG 1 and BUG 2 had silent rev-1s that only surfaced via live probing.
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
