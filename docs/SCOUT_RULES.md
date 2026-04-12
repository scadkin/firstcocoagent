# SCOUT — Full Rules Reference
*Extracted from CLAUDE.md during Session 58 trim. Last updated: 2026-04-11.*

This file holds the full rule set. CLAUDE.md keeps the top 15 session-critical rules inline; everything else lives here. Read by section or grep by keyword — every rule's original bolded lead sentence is preserved verbatim from the original CLAUDE.md so grep on existing phrases still resolves.

**Related reference files:**
- `docs/SCOUT_REFERENCE.md` — repo tree, env vars, Claude tool registry, Telegram command list
- `CLAUDE.md` — current state, Session N priorities, top 15 rules
- `SCOUT_PLAN.md` — active plan + completed feature notes
- `SCOUT_HISTORY.md` — bug log + changelog
- `memory/*.md` — behavioral feedback, auto-loaded at session start
- `agent/CLAUDE.md` + `tools/CLAUDE.md` — module-scoped API signatures

---

## 1. Workflow & Process

**Always enter plan mode before building anything non-trivial.** New scanners, new strategies, new tools, schema changes, multi-file refactors — all require `EnterPlanMode` + Steven's sign-off BEFORE code gets written. Session 51 shipped 7 features without plan mode and 3 of them had BLOCKER-level bugs that Session 52 had to fix. Exception: typos, one-line config tweaks, documentation edits. When in doubt, plan. Rule established Session 52. *(Top-15)*

**Every plan is a one-shot.** Don't write a plan expecting Steven to do refining rounds. Self-pressure-test hard; ship the best possible plan first time. Saved as `memory/feedback_plans_are_one_shot.md`. Steven explicitly rejected v1 of the BUG 4 plan that ended with "ready for your 7-step pressure test" — he considered that lazy framing that pushed rigor onto him. *(Top-15)*

**Empirical Serper probes BEFORE plan mode.** Both BUG 1 and BUG 2 plans had silent-bug rev-1s that only surfaced when I ran actual Serper queries against the proposed query templates. BUG 1 rev-1 used `"<State>"` quoted which killed yield to 0; rev-2 used unquoted state and yield jumped to 10+. BUG 2 rev-1 was snippet-only which would have yielded 0 because snippets are 200 chars; rev-2 added httpx + BeautifulSoup direct fetch and yield jumped to 14. Rule: don't write a plan on query design without running the queries first. *(Top-15, Session 57 lesson)*

**Pressure-test catches silent bugs that would have shipped.** When Steven asks for the pressure test, actually HOLD THE FULL PLAN IN HEAD before reacting — surface all the silent bugs in one pass, rewrite from scratch with everything baked in.

**Always push code changes from Claude Code via git — never tell Steven to use `/push_code` in Telegram.** Scout's `/push_code` dumps entire file contents into Telegram (4,096-char limit) causing truncation and confusion. Always `git add`, `git commit`, `git push` directly from the Claude Code terminal. This is a hard rule established Session 19. *(Top-15)*

**Read before write.** Before touching any file that calls an existing module, read that module first. Every crash in this project has been caused by hallucinated method names. Module APIs are documented in `agent/CLAUDE.md` and `tools/CLAUDE.md`. *(Top-15)*

**Always produce complete replacement files.** [DEPRECATED — this rule applied to the pre-Edit/Write-tool workflow where Claude output file content as chat messages and Steven copy-pasted via GitHub web. Current workflow uses Edit/Write tools directly. Preserved here for historical record.]

**Multi-feature sessions ship one commit per feature.** Don't bundle features into one big commit at session end. Separate commits enable surgical `git revert` if a feature causes production issues. Session 49 shipped F3 → F1 → F4 → F2 as separate commits + small fix commits. *(Top-15)*

**New scanners ship with kill switches.** Add an `ENABLE_X_SCAN = True` constant near the top of `tools/signal_processor.py` (next to `SERPER_API_KEY`). Scanner checks the flag at function entry and returns empty if disabled. One-line commit to disable in production without removing code. Examples: `ENABLE_FUNDING_SCAN`, `ENABLE_COMPETITOR_SCAN`. *(Top-15)*

**Static finite directories are lookups, not scanners.** CSTA chapters, Catholic dioceses, charter CMOs, CTE centers — any data source that's bounded and changes less than weekly should be fetched once into `memory/*.json` and exposed as an enrichment helper, not scheduled as a daily Serper+Haiku scanner. Saved as `memory/feedback_static_directories_are_lookups.md`. Generalizes the BUG 4 diocesan lesson + retires F5 + codifies the pattern for future sources. *(Session 57 lesson)*

**Signal vs. Prospect routing for new lead-gen scanners.** HIGH confidence → auto-queue via `district_prospector.add_district()` as `pending`. MEDIUM/LOW → Signals tab only via `write_signals()`. Active customer match → `customer_intel` log only (don't sell, don't discard). Pattern established in F4 + F2 scanners (Session 49). All queue writes are `pending` — Steven manually approves via `/prospect_approve`. No auto-elevation logic. *(Top-15)*

---

## 2. Python & Async Safety

**Never use `requests` or `time.sleep()` inside async functions.** Use `httpx.AsyncClient` for HTTP and `await asyncio.sleep()` for delays. Both synchronous versions freeze the asyncio event loop. *(Top-15)*

**Synchronous code called from async context must use `run_in_executor`.** Wrap blocking I/O in `await loop.run_in_executor(None, fn, args...)`. Never call blocking functions directly from async methods.

**`handle_message()` and async tasks must call `get_gas_bridge()` locally — never reference `gas` as a free variable.** `handle_message()` assigns `gas = get_gas_bridge()` later in the function (line ~1687 for `/call_list`). Python treats `gas` as local throughout the entire function — so any earlier reference raises `UnboundLocalError`. Same applies to `_run_*_scan()` functions spawned via `asyncio.create_task()` from the scheduler — they don't inherit the outer `gas` local. ALWAYS call `get_gas_bridge()` into a local variable like `draft_gas` or `scan_gas` at the top of any new branch or scheduled function. Two latent bugs from this pattern shipped in Session 49. *(Top-15)*

**`scheduler` is a module-level global in main.py.** It must be instantiated at module scope (alongside `memory` and `conversation_history`), not inside `_run_telegram_and_scheduler()`. If it's local to that function, `handle_message()` can't access it and all message handling silently dies. Fixed Session 23.

**`global` declarations go at the TOP of `handle_message()`, not in elif blocks.** Python SyntaxError if `global` appears after first use of the variable. All globals in one line: `global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _pending_csv_intent, _last_proximity_result`. *(Top-15)*

**Eager-load lookup indexes at module import time.** `signal_processor.py`'s `_load_csta_roster()` runs at import via `_load_csta_roster()` call at module bottom. No lazy-init race. Scout imports are module-level, one import per process. Lazy patterns are overkill for read-only JSON lookups. *(Session 57 lesson)*

---

## 3. Architecture & Module Imports

**Lazy imports for Phase 4+ modules.** `github_pusher`, `sequence_builder`, `fireflies`, `call_processor` are imported INSIDE `execute_tool()`, never at the top of `main.py`.

**Top-level imports for flat tool modules.** `activity_tracker`, `csv_importer`, `daily_call_list`, `district_prospector`, `pipeline_tracker`, `lead_importer` are imported at the top of main.py like sheets_writer.

**tool_result always follows tool_use.** Wrap every `execute_tool()` call in try/except. A result must always be appended to conversation history, even on error. Missing tool_result → 400 on next API call. *(Top-15)*

**`_on_prospect_research_complete` is the auto-pipeline callback.** Standard flow → strategy-aware sequence → Google Doc → mark complete. `sequence_builder` lazy imported.

**`proximity_engine.py` is a flat module imported at top of main.py.** Targeted + state sweep modes. `add nearby` queues from last results. ESA mapping via `esa [state]`. All direct dispatch. `_last_proximity_result` is in-memory only — lost on bot restart.

**`signal_processor.py` is a flat module imported at top of main.py.** 19 signal sources, 31 Telegram commands, all direct-dispatch. Daily 7:45 AM CST. Weekly Monday: leadership + RFP. Monthly 1st Monday: legislation + grants + budget. On-demand: algebra, cyber, roles, CSTA. BoardDocs/Ballotpedia/RSS wrapped in try/except (non-fatal). `_last_signal_batch` is in-memory — run `/signals` before `/signal_act` or `/signal_info`.

---

## 4. Priority Scoring & Strategy Internals

### `_calculate_priority` strategy table (as of Session 52)

| Strategy | Priority Range | Size Kwarg | Notes |
|---|---|---|---|
| `upward` | 600–999 | — | School accounts, no district deal |
| `winback` | 550–749 | — | Closed-lost recovery |
| `proximity` | 400–699 | — | Geographic clustering |
| `esa_cluster` | 450–599 | — | ESA cohort |
| `intra_district` | 750–849 | — | F1 strategy |
| `cs_funding_recipient` | 800–899 | — | F4 strategy |
| `competitor_displacement` | 650–749 | — | F2 strategy |
| `csta_partnership` | 620–719 | — | CSTA roster enrichment |
| `charter_cmo` | 780–899 | `school_count` | F6, scales with schools |
| `cte_center` | 760–879 | `sending_districts` | F7, scales with feeder districts |
| `private_school_network` | 740–839 | `schools` | F8, scales with network size |
| `compliance_gap` | 850–939 | `est_enrollment` | F9 Signals-only pilot — applies only on manual `/signal_act` promotion |
| `homeschool_coop` | 500–599 | — | |
| `cold` (fallthrough) | 300–799 | `est_enrollment` | Any unknown strategy lands here |

Add new branches for new strategies — falling through to cold gives wrong sort order for warm leads.

**`add_district(**kwargs)` and size metadata:** As of Session 52 Commit 1, `add_district()` accepts `**kwargs` and forwards them to `_calculate_priority`. Callers should pass `est_enrollment`, `school_count`, `sending_districts`, or `schools` depending on strategy — these both affect priority scoring and populate queue row columns 15–17 (`Est. Enrollment`, `School Count`, `Total Licenses`). If you add a new strategy and don't pass the right kwargs, it'll score at tier base and look broken. The existing `_calculate_priority` signature has `school_count` and `total_licenses` as named positionals; `add_district` pops them out of kwargs before forwarding to avoid collision. Use `functools.partial` when calling via `loop.run_in_executor(None, fn, *args)` — that API can't pass kwargs directly.

**`district_prospector.add_district` accepts `priority_bonus: int = 0`** kwarg — popped before forwarding to `_calculate_priority` and added after. Default 0 preserves every existing call site. Any enrichment source can use this; CSTA is the first caller.

**`/signal_act` uses `_SIGNAL_TYPE_TO_STRATEGY` dict for strategy mapping.** Added Session 52 Commit 2 in `agent/main.py`. Currently only maps `"compliance" → "compliance_gap"`. Anything else defaults to `"trigger"` which falls through to the cold branch (same as the pre-Session-52 behavior for back-compat). Session 53+ follow-up: add `bond → bond_trigger`, `leadership → leadership_change`, `rfp → rfp_trigger`, etc. after those strategies are built. When you add a new signal-promoted strategy, you MUST also add its branch in `_calculate_priority` AND its entry in `_SIGNAL_TYPE_TO_STRATEGY`.

**F9 compliance_gap_scanner is Signals-only pilot mode.** Session 52 Commit 2 rewrote the queue path — scanner writes extracts to the Signals tab via `signal_processor.write_signals` with `signal_type="compliance"`, `source="compliance_scan"`, `source_detail="F9_pilot_{state}"`, and stable `message_id = f"compliance_{state}_{sha1(url+district)[:12]}"` for dedup across re-scans. Auto-queue mode is disabled until ≥60% validation rate is proven over 15+ extractions. Promotion happens via `/signal_act N` which uses the strategy mapping above. Per-state 24h rate limit enforced via module-level `_LAST_SCAN` dict (Commit 5) — override by waiting 24h or restarting Railway.

**`_extract_districts_from_pdf` returns `(items, error_msg_or_none)` tuple** (Session 52 Commit 2). Allows `scan_compliance_gaps` to distinguish "parse failed" from "no districts found in document" — both return empty lists in the first element but the second element is `None` vs an error string. The return dict now surfaces a `parse_errors` list for operator visibility.

**New territory_data helper: `lookup_district_enrollment(name, state) -> int`** (Session 52 Commit 1, refined in Commit 4). Matches on pre-computed `Name Key` column first, then falls back to re-normalizing `District Name`, then a token-subset pre-check (if target tokens are a strict subset of candidate tokens or vice versa), then `csv_importer.fuzzy_match_name` with threshold 0.7. Returns 0 on miss. The token-subset pre-check exists because `csv_importer.fuzzy_match_name` has a gap for 1-token-subset-of-multi-token cases (e.g., "carlinville" ⊂ "carlinville 1") — see `memory/feedback_fuzzy_match_limits.md`.

**`/prospect_approve` checks Active Accounts before queuing.** Warns on existing district customers. `_pending_approve_force` + `_last_prospect_batch` are in-memory only — lost on restart.

**Two prospecting strategies — upward and cold.** Upward = school accounts, no district deal. Cold = no presence. 8 priority tiers (900+ to 300+). Small/medium above large in same tier.

**When activating a feature via district name lookup, canonicalize both sides.** `_canonical_diocesan_key` lowercases and strips "schools"/"catholic schools" suffix. Both map keys (at build time) and lookup input (at runtime) go through the same helper — so "Archdiocese of Chicago Schools", "archdiocese of chicago", and "Archdiocese of Chicago Catholic Schools" all resolve. Rule: never trust that users/bots will type the district name the way the seed has it stored. *(Session 56 lesson)*

**Single source of truth helpers prevent filter leaks.** Commit C of BUG 4 collapsed 4 inline `target_host/target_hint` computations into a single `_target_match_params()` call. The diocesan override is in one place; non-diocesan behavior is preserved exactly. Post-commit grep gate (`grep 'self\._district_name_hint(self\.district_name)' | count == 1`) confirms no stale sites remain. Rule: when a matching rule needs a per-context override, refactor all call sites behind a single helper FIRST, then add the override. *(Session 56 lesson)*

---

## 5. Data Model, CSV Import & Sheets Schema

**Active Accounts "Display Name" column is the account name.** Sheet header currently says "Display Name". Steven wants it renamed to "Active Account Name" — this will happen automatically on next account CSV import (csv_importer rewrites header). Until then, any code reading active accounts must check BOTH column names: `acc.get("Active Account Name", "") or acc.get("Display Name", "")`. The `territory_data.py` gap analysis already has this fallback.

**Urban Institute Education Data API returns county_code as strings, not integers.** `"6037"` not `6037`. All county code comparisons must use string keys.

**Territory gap coverage: school accounts ≠ district coverage.** Only district-level Active Account deals count as "covered." A school account inside a district is an "upward opportunity," not coverage. Coverage % = district deals / total NCES districts.

**Salesforce CSV: Parent Account = always the district.** Account Name can be district/school/library/company. Parent Account filled → sub-unit under that district. Empty → standalone or top-level. One level deep: district → schools.

**CSV import default mode is MERGE (non-destructive).** `/import_clear` switches to clear-and-rewrite for next upload only. `/import_replace_state CA` replaces only that state's rows. `/dedup_accounts` uses Name Key + State composite key.

**`get_districts_with_schools()` state key is `"State"` (capital S).** Active Accounts use capital-S. `s.get("state")` returns empty — always use `s.get("State")`.

**CSV importer preserves ALL columns.** Known columns mapped via `_SF_COL_MAP`/`_OPP_COL_MAP`, unknown pass through. Pipeline uses REPLACE ALL (point-in-time snapshot). Always normalize names to sentence case preserving acronyms (ISD, HS, STEM). CSV uploads decode with utf-8-sig.

**Auto-detect CSV routing by headers.** Priority: pipeline > sf_leads > sf_contacts > accounts. Natural language description or caption overrides auto-detect. Slash commands override everything.

**Pipeline uses 3-tier stale alerts.** 🟠 14+ days, 🟡 30+ days, 🔴 45+ days. Empty Last Activity is NOT flagged.

**Active Accounts "Account Type" column: district | school | library | company.** Old boolean "Is District" column is gone. Do not reintroduce TRUE/FALSE logic.

**Sheet dedup uses email as primary key.** Falls back to `first|last` name for no-email contacts. Don't use name+district — Claude varies district_name spelling.

**`classify_account()` checks district patterns BEFORE school keywords.** "Austin Independent School District" must not match "school" first.

**Name ends in "school" (singular) → school. "schools" (plural) → district.** Explicit rule from Steven.

**District/school names: normalize aggressively, ask when ambiguous.** `normalize_name()` handles abbreviation expansion + suffix stripping. Always normalize both sides before comparing across sources.

**`_ensure_tab()` always overwrites the header row.** Column schema changes must propagate immediately.

**Telegram file upload handler is separate.** `handle_document()` uses `filters.Document.ALL`. Never merge into `handle_message`.

**`sheets_writer._ensure_headers` auto-migrates** when current header is a prefix of expected (Session 55 fix). Root CLAUDE.md's "`_ensure_tab` always overwrites" refers to a different function in `district_prospector.py` — do not conflate the two.

---

## 6. GAS Bridge

**GAS bridge: new Code.gs edits need a new deployment version.** See `gas/CLAUDE.md` for the full checklist.

**GAS deployment URL does NOT change when bumping version.** Only need to update Railway env var if creating a brand-new deployment (not editing an existing one).

**GAS `createDraft` always passes `skip_if_draft_exists=True`.** This prevents duplicate drafts on threads that already have one. GAS-side check via `threadHasDraft(threadId)` iterates `GmailApp.getDrafts()`. Returns `{success: false, already_drafted: true}` which `gas_bridge._call()` passes through (does NOT raise). Email drafter treats `already_drafted` as a soft-skip, not an error.

**Validate email before calling gas.create_draft().** GAS throws on malformed emails.

---

## 7. Research Engine & Contact Extraction

**Research engine has 20 layers in 5 parallel phases.** Phase A (parallel): L1,L2,L3,L5,L16,L20. Phase B: L4 (domain discovery). Phase C (parallel): L6,L11-L14,L17-L19. Phase D: L7,L8. Phase E: L9→L10→L15→L10. New layers: L16 (Exa broad), L17 (Exa domain-scoped), L18 (Firecrawl extract — needs paid plan), L19 (Firecrawl site map — needs paid plan), L20 (Brave Search).

**Firecrawl paid plan deferred (budget).** L18/L19 skip gracefully when FIRECRAWL_API_KEY has no credits. Was the #1 tool discovery — schema-based extraction pulled 10-20 verified contacts per district. Circle back when budget allows.

**Contact extractor max_tokens is 4000 (not 2000).** School directory pages with 15+ contacts were causing JSON truncation. Fixed Session 40.

**`agent/target_roles.py` is the authoritative lead targeting filter.** Contains TIER1/TIER2 titles, CTE relevant/exclude keywords, IT infra exclusions, and `is_relevant_role()` function. Used by `contact_extractor.py` post-extraction. Source: Steven's "ROLES and KEYWORDS" doc.

**Research completion always calls `log_research_job`.** Failure to log is silent.

**call_processor.py must use claude-sonnet-4-6.** claude-opus-4-5 hangs indefinitely. Anthropic client timeout=90.0.

**Serper snippets flow into `raw_pages` via `_add_raw_from_serper`.** For JS-rendered sites, search-index layers (L1/L2/L4/L11/L16/L17/L20) are where contact yield comes from. Don't waste time on L6 seed URLs for React/Liferay/Drupal SPAs. Saved as `memory/reference_serper_snippets_as_raw_pages.md`. *(Session 56 lesson)*

**L6 direct scrape is architecturally blind to modern school CMS platforms.** Liferay, Drupal SPA, WordPress-React, Next.js SPA — BeautifulSoup sees JS shell with zero text. 4 of 16 diocesan domains also WAF-block Scout's `ScoutBot/2.0` user agent outright (Boston, Pittsburgh, OKC, Galveston-Houston). Upgrading Scout's global UA is risky — it touches every public district run. Accept L6 as dead weight on diocesan and rely on Serper for yield. *(Session 56 lesson)*

**L15 additions bypass anything that runs in L9.** Any post-L9 validation must ALSO run on L15's `_merge_contacts` sites (two of them). The second L10 pass is a weaker gate than a Stage 2 call. *(Session 55 lesson)*

**Browser User-Agent is OK for one-shot local scripts.** Session 56 rule was "don't change Scout's global UA because it touches every public district run." That rule still holds. But a per-script fetcher that runs manually (`scripts/fetch_csta_roster.py`) can use `Mozilla/5.0 …` safely because it's not in the production path. BUG 2 fetcher uses this and succeeds on all csteachers.org subdomains. *(Session 57 lesson)*

---

## 8. Signal Processor

**Signal enrichment must run before acting on signals.** Never queue a district based on a headline alone. `enrich_signal()` does Serper web search + Claude Haiku analysis for CodeCombat relevance (strong/moderate/weak/none). A $6.2B bond can be WEAK if it's all devices. A no-dollar STEAM coordinator hire can be STRONG. Auto-runs on Tier 1 during daily scans; manual via `/signal_enrich N`.

**Google Alerts are weekly digests with all keywords bundled into one email.** Format: `=== News - N new results for [KEYWORD] ===` sections. Parser normalizes `\r\n` to `\n`. `body_limit=65000` required (digests are ~56K chars). ~80 stories per digest.

**`/signals` defaults to territory-only.** `format_hot_signals(territory_only=True)` filters to 13 states + SoCal. Pass state_filter for single-state view. `_last_signal_batch` is also territory-filtered.

**Bond/leadership/RFP signals use urgency="time_sensitive" with minimal decay.** Standard Tier 1 decay is 0.93/week. Time-sensitive signals use 0.97/week because the opportunity window matters more than email age.

---

## 9. Telegram & Command Dispatch

**Explicit slash commands bypass Claude and call execute_tool() directly.** `/brief`, `/call`, `/recent_calls`, `/progress`, `/sync_activities`, `/call_list`, `/pipeline`, `/pipeline_import`, `/import_closed_lost`, `/import_leads`, `/import_contacts`, `/enrich_leads`, and all `/prospect_*` commands call execute_tool() directly and return. Direct dispatch is the only reliable pattern — when conversation history is long, Claude responds with descriptive text instead of calling tools. *(Top-15)*

**`/build_sequence` is a hybrid.** Routes through Claude for clarifying questions. But `execute_tool("build_sequence")` sends output via `await send_message()` directly and returns a short ack string to prevent Claude from rewriting.

**`execute_tool` can send directly to Telegram for long outputs.** For tools that return content Claude tends to rewrite, use `await send_message(full_output)` inside `execute_tool` and return a short ack string.

**Suppress `text_response` when tool_calls are present.** Use `if text_response and not tool_calls:` before sending Claude's text. Tool preamble text is noise.

**Never design workflows that require pasting large text through Telegram.** 4,096 char limit. Use fetch-first: Scout reads from GitHub, asks for changes in plain English. *(Top-15)*

**`/call_list` must be guarded in the `/call` handler.** `startswith("/call")` matches both. Use `startswith("/call") and not startswith("/call_list")`.

**Call list per-district cap (_MAX_PER_DISTRICT = 2) applies to BOTH priority matches AND backfill.**

---

## 10. Sequence Building & Content Rules

**NEVER fabricate claims about active accounts in sequences.** Only cite verifiable facts: school name, license count. No assumed success/engagement. *(Top-15)*

**ALL sequences are drafts — always show for Steven's approval.** Write to Google Doc, share link in Telegram, mark prospect as "draft" status. Never auto-finalize or auto-mark "complete". Steven reviews and either approves or gives feedback on changes. This applies to ALL strategies (upward, cold, winback), not just winback. *(Top-15)*

**Sequence building rules are in `memory/sequence_building_rules.md`.** Load as context when auto-building sequences.

---

## 11. Outreach.io API Gotchas

Full details in `memory/feedback_outreach_intervals.md`, `feedback_outreach_torecipients.md`, `feedback_outreach_sequence_defaults.md`, `feedback_outreach_sequence_order.md`, and `memory/outreach_api_access.md`. Summary:

- **Steven's user ID: 11.** Write access for sequences/steps/templates/prospects only.
- **Interval is in SECONDS** (not minutes). 5 min=300, 4 days=345600, 6 days=518400.
- **`toRecipients` MUST be `[]` (empty).** Never `["{{toRecipient}}"]` — causes all emails to fail.
- **Creation flow:** create sequence → steps → templates → link → Steven activates in UI → THEN add prospects.
- Use `<br><br>` between paragraphs in bodyHtml, NOT `<p>` tags.
- **Schedules:** UI-only (no API scopes). Three standard: "Teacher Tue-Thu Multi-Window", "Admin Mon-Thurs Multi-Window", "Hot Lead Mon-Fri".
- **C4 sequences:** IDs 1995-1998. Schedule: "C4 Tue-Thu Morning" (ID 50). Steven's template: ID 43784.

---

## 12. Design Constraints

**No Salesforce or Outreach API access.** All data enters Scout via CSV export or Gmail notification parsing. Never design features assuming API access to Salesforce, Outreach, PandaDoc, or Dialpad.

**Outreach handoff pattern for cold sequences.** Scout builds content → Google Doc → Steven copy-pastes into Outreach.io. Do NOT try to replace Outreach with Gmail for cold sequences.

**Fireflies Gmail polling uses startup seeding.** First scan adds all existing emails to set without processing. Only post-startup emails trigger workflows.

---

## 13. Operations & Deployment

**Railway build cache can serve stale code.** If behavior doesn't match, add a logger.info line and check logs after redeploy. If value doesn't appear, trigger manual redeploy.

**After Railway redeploy, wait for "Scout is online" in Telegram before testing.** 409 Conflict errors during ~30s overlap are normal.

**Railway log API queries need DateTime scalar type** (not String). `startDate: DateTime` / `endDate: DateTime`. 5000-line limit per query — narrow the window if near the cap. *(Session 55 lesson)*

**Scout bot research task can occasionally hang silently for 1 request then recover.** Session 55 second smoke test hung for 20+ min with zero progress logs, then a third attempt completed in 7 minutes. Possibly a 409 Conflict overlap during rolling deploy. If research seems stuck, wait 2-3 min and retry; don't assume a code bug first. *(Session 55 lesson)*

---

## Appendix A — Session 57 Post-Mortem (full lesson prose)

### Static finite directories are lookups, not scanners
CSTA chapters, Catholic dioceses, charter CMOs, CTE centers — any data source that's bounded and changes less than weekly should be fetched once into `memory/*.json` and exposed as an enrichment helper, not scheduled as a daily Serper+Haiku scanner. Saved as `memory/feedback_static_directories_are_lookups.md`. Generalizes the BUG 4 diocesan lesson + retires F5 + codifies the pattern for future sources.

### Haiku extractions in validation harnesses need `temperature=0.0`
Without it the gate flip-flops between runs — same snapshot, different HIGH/MEDIUM splits, oracle labeling breaks. BUG 1 harness was non-deterministic until I pinned temperature. Saved as `memory/feedback_haiku_temperature_zero_for_gates.md`.

### Empirical Serper probes BEFORE plan mode
Both BUG 1 and BUG 2 plans had silent-bug rev-1s that only surfaced when I ran actual Serper queries against the proposed query templates. BUG 1 rev-1 used `"<State>"` quoted which killed yield to 0; rev-2 used unquoted state and yield jumped to 10+. BUG 2 rev-1 was snippet-only which would have yielded 0 because snippets are 200 chars; rev-2 added httpx + BeautifulSoup direct fetch and yield jumped to 14. Rule: don't write a plan on query design without running the queries first.

### Browser User-Agent is OK for one-shot local scripts
Session 56 rule was "don't change Scout's global UA because it touches every public district run." That rule still holds. But a per-script fetcher that runs manually (`scripts/fetch_csta_roster.py`) can use `Mozilla/5.0 …` safely because it's not in the production path. BUG 2 fetcher uses this and succeeds on all csteachers.org subdomains.

### Eager-load lookup indexes at module import time
`signal_processor.py`'s `_load_csta_roster()` runs at import via `_load_csta_roster()` call at module bottom. No lazy-init race. Scout imports are module-level, one import per process. Lazy patterns are overkill for read-only JSON lookups.

### Pressure-test catches silent bugs that would have shipped
BUG 1 rev-1 had `"<State> State Board of Education"` as a generic template — broken for TX (TEA), CA (CDE), OH (ODE). BUG 2 rev-1 had snippet-only extraction + wrong dedup key + unquoted-state bug. Both rev-1s would have shipped and produced near-zero yield with no obvious signal. The 7-step pressure test turned both into working rev-2s on the first pass. Rule: when Steven asks for the pressure test, actually HOLD THE FULL PLAN IN HEAD before reacting — surface all the silent bugs in one pass, rewrite from scratch with everything baked in.

---

## Appendix B — Scanner Pattern

**Scanner URL preservation.** New Claude-extraction scanners must include `source_url` in JSON schema + `http(s)` validation, never hardcode `url=""`. See `memory/feedback_scanner_url_preservation.md`.

**Vendor site queries fail for adoption evidence.** Never use `site:vendor.com` for adoption evidence — always false positives. Use BoardDocs + RFP docs instead. See `memory/feedback_vendor_site_queries_fail.md`.
