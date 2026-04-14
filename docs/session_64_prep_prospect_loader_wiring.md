# Session 64 prep — wiring `prospect_loader.execute_load_plan` into `_on_prospect_research_complete`

**Status: scratch prep note, not a plan.** Written end-of-Session-63 as a reading-only dump so Session 64's plan-mode exploration starts with the code paths already mapped. This file is the kind of intermediate note that CLAUDE.md says to prefer putting in conversation context, but the ctx-handoff argument for committing it is: Session 63 is about to end and the next session starts with a cold context, so a committed note is the load-bearing handoff mechanism.

Read this, then read the actual files it cites, then brainstorm. Do not skip straight to design from this note alone.

## The gap being closed

**Today's flow** (end of Session 63): the research engine finishes a district, `_on_prospect_research_complete` runs, which:
1. Calls `_on_research_complete(result)` — writes to Sheets, sends Telegram summary.
2. Builds a draft sequence via `sequence_builder.build_sequence` — ~5 steps, strategy-specific tone/content.
3. Writes the sequence to a Google Doc, sends the URL to Steven for review.
4. Logs a `sequence_built` activity.
5. Marks the prospect's status as `draft` in the prospecting queue.

The prospect is **NOT automatically loaded into the built sequence**. Steven has to (a) review the draft, (b) manually load contacts via a separate command or process. The diocesan drip (`scripts/diocesan_drip.py --execute`) uses `prospect_loader.execute_load_plan` to load contacts from a pre-built CSV state file — that same machinery could be called from the handler.

**The gap.** After a research job finishes, if the research produced verified contact emails (not just a district name), Scout could auto-load those contacts into the just-built sequence so the sequence starts sending without Steven's manual intervention.

## Critical files and entry points

- `agent/main.py:319` — `async def _on_prospect_research_complete(result: dict, prospect: dict)`. 209 lines of body (measured). The handler runs in the 24/7 Railway asyncio loop. Any change here is production-critical.
- `agent/main.py:2485` and `agent/main.py:2881` — the two places `_on_prospect_research_complete` is invoked. Both are inside `execute_tool` branches for research completion. Call sites pass `result` (the research engine's output dict) and `prospect` (the prospecting-queue row that was approved).
- `tools/prospect_loader.py:77` — `@dataclass class LoadPlan`. Fields: `contact` (Contact), `sequence_id`, `mailbox_id: int = 11`, `tags: list[str]`, `day_bucket: str`, `status`, `prospect_id`, `sequence_state_id`, `error`, `updated_at`.
- `tools/prospect_loader.py:117` — `def build_load_plan(contacts, sequence_id_for, *, days, mailbox_id=11, tags_for, group_key)`. Round-robin assigns contacts across days. Deterministic on re-run. Used by the diocesan drip.
- `tools/prospect_loader.py:259` — `def execute_load_plan(plans, *, state_path, audit_path, target_day=None, sleep_seconds=(300, 900), verify_sequence_active=True, dry_run=False) -> dict`. The function the handler would call.
- `tools/prospect_loader.py` — `Contact` dataclass (read the file for the exact field contract; it includes `first_name`, `last_name`, `email`, `title`, `company`, `state`, `diocese_or_group`, `confidence_rank`, and the `state` field must map via `state_to_timezone` to a populated IANA tz per CLAUDE.md Rule 17).

## What `execute_load_plan` expects

From reading lines 259–390:

1. A **list of `LoadPlan` records**, each already bound to a `sequence_id`, `mailbox_id`, `tags`, and `day_bucket`.
2. A **`state_path`** file for resumability — rewritten after every successful POST. Path must exist / be creatable.
3. An **`audit_path`** append-only JSONL file for per-POST audit entries.
4. The function loops per plan and:
   - Skips if status is not pending.
   - Preflight: checks sequence enabled via `_sequence_is_enabled` (cached per seq).
   - Dedup: `find_prospect_by_email` — reuses existing prospect if found.
   - Else: `create_prospect` (runs validator internally — requires populated IANA timezone per Rule 17).
   - Dedup: checks existing sequenceState on (prospect, sequence) — skips if already in.
   - `add_prospect_to_sequence` — creates the sequenceState.
   - Updates `plan.status`, writes state file atomically, appends audit.
   - Sleeps jittered `sleep_seconds` (default `(300, 900)` — 5–15 min per contact, far too slow for inline auto-load; drip tightened this to 10–30 sec for its own run).

## Open questions that Session 64 must resolve in plan mode

These are the ones I can name from reading alone. The actual plan-mode session will surface more.

1. **Where do the contacts come from?** `_on_prospect_research_complete` has `result: dict` (research engine output) and `prospect: dict` (queue row). Does the research result contain a verified contact list, or just a district name? If the research engine outputs contacts-with-emails, the wiring is feasible. If it only outputs a district name, Scout needs a separate contact-discovery step before load. **Read the actual research result shape before committing to an approach.**
2. **Who builds the `sequence_id_for` mapping?** `build_load_plan` expects a callable that maps a Contact to its target sequence_id. For the diocesan drip the mapping is diocese→preset sequence. For auto-load from research, the only candidate sequence is the one just built by `sequence_builder.build_sequence` — which returns a dict with a nascent sequence plus steps, but the sequence isn't created in Outreach yet by `build_sequence` alone. A separate call to `outreach_client.create_sequence` turns it into a real live sequence with an ID. Does the current handler do that create? Or is the draft-sequence-URL flow operating at a different abstraction? **Trace the build_sequence → create_sequence handoff.**
3. **Synchronous vs async.** `execute_load_plan` is a sync function that sleeps between POSTs. Calling it from the async handler without `run_in_executor` will freeze the event loop for the duration of a full batch (potentially many minutes). Must be called via `run_in_executor`, OR the function needs an async variant, OR the loader is refactored into an async generator. **Decide which at plan time.**
4. **Dry-run / draft-review flow preservation.** Today, every sequence is a draft — Steven reviews the Google Doc before anything is loaded. If auto-load fires immediately on research complete, that review step is bypassed. Rule 15 of CLAUDE.md says "ALL sequences are drafts — always Google Doc + Telegram link for Steven's approval. Never auto-finalize." So auto-load-on-research is probably wrong; the right flow is auto-load-on-Steven-approval, which needs a separate trigger (a `/approve <name_key>` command, a Telegram reply handler, or similar). **This is the biggest design question.**
5. **Timezone requirements.** Rule 17: every prospect create MUST have a populated IANA timezone derived from state via `state_to_timezone`. The research result may produce contacts with no state field or a non-US state. What happens to those contacts? Per the rule, skip them, never fall back. **Validation path needs explicit handling.**
6. **Cadence and sleep_seconds.** The default `(300, 900)` 5-15 min jitter is safe for long manual loads but too slow for an inline-after-research trigger. The diocesan drip tightened this to `(10, 30)` (10–30 sec) in `scripts/diocesan_drip.py`. Auto-load should probably use similar or tighter. **Parameterize at call site, do not touch the default.**
7. **Failure mode and partial-state recovery.** `execute_load_plan` writes the state file after every POST. For a 15-contact inline run that's fine. For a 200-contact research-driven run triggered by a single research job, a mid-run crash needs a resumable path — the state file is the resume mechanism, but the file path must be chosen per-run (a district-slug-based path, probably). **Decide the state-file-path convention.**
8. **Kill switch.** Per CLAUDE.md Rule 7, every new feature ships with a kill switch. `ENABLE_AUTO_LOAD_AFTER_RESEARCH = False` constant in `agent/main.py` near the other `ENABLE_*` flags. Default OFF. Flip only after a successful canary run in production.

## Risks that are not in the open-questions list

- **Rule 1**: this is a "non-trivial build" touching a 24/7 Railway-deployed async handler. Must enter plan mode. Cannot be a one-shot commit.
- **Rule 8**: multi-feature sessions ship one commit per feature. If Session 64's plan-mode session produces wiring + kill switch + new state-file path convention + new approval trigger, that's at least three commits.
- **Rule 11**: no `requests` / `time.sleep` in async. Wrapping `execute_load_plan` in `run_in_executor` is probably the right call — verify that `_api_get` inside the loader isn't itself using an async http client that would need a different wrapping.
- **`prospect_loader.py` uses `owner_id=11` hardcoded** at line 362 of the file (measured from the Read output). That's Steven's user ID. Not a rule violation per se, but worth noting — if Scout is ever multi-user, this breaks.

## Recommended Session 64 opener

1. Enter plan mode.
2. Read the **research engine's actual output shape** by searching for the most recent `_on_research_complete` invocation in agent/main.py and tracing what `result` actually contains. Do not assume.
3. Read the **sequence_builder → create_sequence → live-sequence-id** chain. Map where the "draft" state lives.
4. Re-read **CLAUDE.md Rule 15** (all sequences are drafts) and decide whether auto-load-on-research is even compatible with that rule. If not, the real work is designing the approval trigger, not the loader wiring.
5. Resolve open questions 1–8 above in order.
6. Write the plan, pressure-test it, ship commit per feature.

## What was NOT read during this prep

- The research engine's actual result dict shape (question 1).
- The sequence_builder → create_sequence handoff (question 2).
- The `Contact` dataclass contract in `tools/prospect_loader.py` (lines 1–76, not read in this prep).
- The `_on_research_complete` function body (called by the prospect variant).
- Any existing `ENABLE_*` flag patterns in `agent/main.py`.

All of the above are Session 64 reading targets, not blockers for this prep note.
