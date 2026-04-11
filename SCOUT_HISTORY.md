# SCOUT — History Log
*Bug fixes and changelog extracted from MASTER.md. Not loaded into Claude context each session.*

---

## BUG FIX LOG

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Check-ins all night | No time window | CHECKIN_START/END_HOUR guards | ✅ Fixed |
| Morning brief at 3:15am | Railway UTC ≠ CST | CST-aware tick loop | ✅ Fixed |
| Hallucinated activity | Prompts requested summary without real data | Rewrote prompts with honesty rules | ✅ Fixed |
| History wiped daily | clear_history() on schedule | EOD compression to memory instead | ✅ Fixed |
| updater.idle() crash | Method doesn't exist in PTB version | asyncio.Event() | ✅ Fixed |
| ModuleNotFoundError: agent | Railway ran python agent/main.py from wrong dir | Changed to python -m agent.main | ✅ Fixed |
| ImportError: Scheduler | Phase 1 scheduler.py had no Scheduler class | Rewrote scheduler.py with Scheduler class | ✅ Fixed |
| AttributeError: load_context_summary | Method named load_recent_summary in memory_manager | Updated claude_brain.py to match | ✅ Fixed |
| Google Sheets 403 PERMISSION_DENIED | Sheets API not enabled in Google Cloud project | Enabled via Cloud Console | ✅ Fixed |
| SyntaxError: global _pending_draft | global declaration appeared after assignment | Moved global declaration to top of execute_tool() | ✅ Fixed |
| ImportError: ResearchEngine | Hallucinated class name. Actual: ResearchJob, ResearchQueue | Rewrote to use research_queue singleton | ✅ Fixed |
| ImportError: SheetsWriter | SheetsWriter class never existed — sheets_writer.py is functions | Changed to module import, replaced all instantiations | ✅ Fixed |
| AttributeError: memory.load() | MemoryManager has no load() | Removed the call | ✅ Fixed |
| AttributeError: memory.compress_history() | Method doesn't exist — real method is append_to_summary(text) | Replaced with correct method | ✅ Fixed |
| TypeError: Scheduler.__init__() unexpected kwargs | Scheduler() takes no arguments | Changed to Scheduler() | ✅ Fixed |
| AttributeError: scheduler.run() | Scheduler has no run() method, only check() | Rewrote run loop to poll check() every 30s | ✅ Fixed |
| AttributeError: memory.commit_file() in voice_trainer | Method doesn't exist — real method is _commit_to_github() | Fixed both calls in voice_trainer.py | ✅ Fixed |
| GAS bridge 403 on /ping_gas | Existing GAS deployment access settings not updating | Created new deployment (Deploy → New deployment) | ✅ Fixed |
| Claude API 400: tool_use ids without tool_result | Tool results not appended to conversation_history | Append tool_result content block after each tool execution | ✅ Fixed |
| Scout crash on boot: ModuleNotFoundError: tools.github_pusher | Phase 4 files imported at top-level before being uploaded | Moved Phase 4 imports inside execute_tool() as lazy imports | ✅ Fixed |
| GAS ping returns empty user string | Session.getActiveUser().getEmail() returns "" for anonymous | Hardcoded "steven@codecombat.com" in ping handler | ✅ Fixed |
| getEffectiveUser() permission error | Requires OAuth scope not available for anonymous web apps | Don't use getEffectiveUser() — hardcode email instead | ✅ Fixed |
| /train_voice no immediate response | Handler ran 3-5 min job before sending any Telegram message | Added immediate ack message before trainer.train() call | ✅ Fixed |
| /train_voice only analyzed 40 of 273 emails | Sample cap hit even when pool < target | Added check: if pool ≤ sample target, use all emails | ✅ Fixed |
| /train_voice only looked back 6 months | months_back default was 6 in main.py, overriding voice_trainer.py default | Changed default in main.py execute_tool handler to 24 | ✅ Fixed |
| /push_code fails for large files | Telegram 4,096-char limit silently truncates pasted file content | Rewrote /push_code to fetch-first: Scout reads file, asks for changes, edits + pushes | ✅ Fixed |
| Code.gs SECRET_TOKEN reverts to placeholder on paste | Steven pasted new Code.gs without replacing placeholder | Added prominent reminder in GAS deployment notes | ✅ Fixed |
| ImportError: FIREFLIES_API_KEY from agent.config | Phase 5 vars added to main.py import but config.py never updated | Read from os.environ directly in main.py | ✅ Fixed |
| ModuleNotFoundError: aiohttp | aiohttp used by webhook_server.py but not in requirements.txt | Added aiohttp to requirements.txt | ✅ Fixed |
| Unknown tool: get_file_content | Handler existed in plan but was never added to execute_tool() | Added full get_file_content handler to main.py | ✅ Fixed |
| /push_code fetched file but didn't ack or summarize | Prompt told Claude to fetch but didn't specify next steps clearly enough | Added immediate ack send_message + step-by-step PUSH_CODE WORKFLOW prompt | ✅ Fixed |
| Scout ending messages with "On it." | Claude's default response pattern — memory can't override hardcoded behavior | Added _clean() function that strips "On it." and "Let me know if..." before every send_message | ✅ Fixed |
| Behavioral corrections not saving to memory | Claude didn't always tag corrections with [MEMORY_UPDATE] | Added correction_signals detector that appends memory save hint to user message | ✅ Fixed |
| main.py corrupted from repeated patch attempts | Multiple incremental sed/replace operations left stray quote chars and broken f-strings | Rebuilt from original uploaded file with all changes in single clean pass | ✅ Fixed |
| Fireflies 400 Bad Request on /recent_calls | Field name mismatches: date→dateString, attendees→participants, speaker_name→speakerName | Rewrote fireflies.py GraphQL queries with correct schema | ✅ Fixed |
| /recent_calls sent two messages | Old container briefly responded during Railway redeploy | Moved to direct send_message flow with single return path | ✅ Fixed |
| /recent_calls showing random old dates | Fireflies returns calls in arbitrary order | Added sort by dateString descending before returning | ✅ Fixed |
| /brief completely silent after tool error | CallProcessor crash uncaught — tool_result never appended to history | Wrapped all execute_tool() calls in try/except; always append result | ✅ Fixed |
| /brief 400 on follow-up message | tool_use block in history had no matching tool_result (history corrupted) | try/except guarantees tool_result always written; history auto-clears on 400 | ✅ Fixed |
| /brief "str object has no attribute get" | GAS bridge returns guests as plain email strings, not dicts | Added _parse_guests() helper that handles both string and dict formats | ✅ Fixed |
| ImportError: PRECALL_BRIEF_FOLDER_ID in call_processor | Imported from config.py which didn't have it | Changed to os.environ.get() directly | ✅ Fixed |
| Google Doc silently skipped despite PRECALL_BRIEF_FOLDER_ID being set | Exception swallowed silently, fallback message blamed missing env var | _create_brief_doc now returns "ERROR:<msg>" string; build_pre_call_brief surfaces it | ✅ Fixed |
| internal meeting filter used hostEmail | hostEmail = codecombat.com on all calls; need to check if ANY attendee is external | Changed to check meeting_attendees[].email — skip only if ALL emails are @codecombat.com | ✅ Fixed |
| GAS createGoogleDoc permission error: DocumentApp.create not authorized | DocumentApp scope was never authorized — added after original GAS deployment | Added params = params \|\| {} to createGoogleDoc, ran manually in editor to trigger OAuth consent, created new GAS deployment | ✅ Fixed |
| /brief: Claude responds with text describing tool instead of calling it | Conversation history accumulates; Claude hallucinates tool execution when history is long | /brief and /call now bypass Claude entirely — call execute_tool() directly like /recent_calls | ✅ Fixed |
| /brief still failing after bypass fix | Root cause unknown — context exhausted before diagnosing | Next session: try /brief [meeting name], check Railway logs for actual exception | ⏳ Open |
| /brief: Google Doc created but not in correct folder | GAS DriveApp scope never authorized — existing OAuth token predated DriveApp code | Revoked OAuth at myaccount.google.com/permissions; added explicit oauthScopes (incl. auth/drive) to appsscript.json; fresh deployment forced re-auth | ✅ Fixed |
| /brief: Google Doc not moving to folder (DriveApp silent catch) | try/catch in createGoogleDoc swallowed DriveApp errors; only logged to GAS Logger | Removed silent catch — DriveApp errors now propagate to doPost handler and surface to Scout | ✅ Fixed |
| Auto pre-call brief (10-min trigger) never fired | GAS getCalendarEvents returned Date.toString() non-ISO string; fromisoformat() always threw; except swallowed it silently | Changed getStartTime().toString() → toISOString() in Code.gs | ✅ Fixed |
| /call [id]: 400 Bad Request with no useful message | raise_for_status() threw before response body was read; actual Fireflies error was lost | Fixed _query() to read response body on non-200 before raising FirefliesError | ✅ Fixed |
| /call [id]: Fireflies 400 — invalid field summary { keywords } | keywords is not a valid subfield of summary in Fireflies GraphQL schema | Removed keywords from summary subquery; also removed from return dict (unused downstream) | ✅ Fixed |
| /call [id]: Fireflies 400 — Cannot query field "speakerName" on type "Sentence" | Field renamed in Fireflies API — correct name is speaker_name | Renamed speakerName → speaker_name in query and transcript builder | ✅ Fixed |
| /call [id]: transcript ID string interpolation in GraphQL query | Using %s interpolation is unsafe and can break on special chars | Switched get_transcript to use GraphQL variables: query GetTranscript($id: String!) | ✅ Fixed |
| /build_sequence: tool result rewritten by Claude — truncated bodies, paraphrased output | Claude intercepts execute_tool return value and rewrites it when history is long | execute_tool now sends via await send_message() directly; returns short ack "✅ Sequence built and sent above." to Claude | ✅ Fixed |
| /build_sequence: "CS Directorss" double-s in ack | execute_tool ack appended "s" to target_role which already ended in "s" | Removed trailing "s" from ack f-string | ✅ Fixed |
| Sequence Google Doc: DriveApp getFolderById error even with empty folder_id | sequence_builder passed `folder_id or SEQUENCES_FOLDER_ID` — if env var was set, non-empty folder ID reached GAS even when caller passed "" | Always pass SEQUENCES_FOLDER_ID directly; strip ?query params from env var with .split("?")[0] | ✅ Fixed |
| Sequence Google Doc: DriveApp "Unexpected error while getting getFolderById" | DriveApp authorization not stable — throws even when called conditionally in GAS | Wrapped DriveApp folder-move block in try/catch in createGoogleDoc — doc creation succeeds regardless of folder move outcome | ✅ Fixed (pending GAS redeploy) |
| Sequence Google Doc: silent error — no error surfaced to Telegram | Doc creation failure was caught, but error msg only reached Claude which paraphrased it | Added direct await send_message() for doc errors in execute_tool, bypassing Claude | ✅ Fixed |
| Duplicate "Got it — building the sequence now." after sequence output | text_response (Claude's preamble text alongside tool_use block) sent to Telegram AFTER execute_tool already sent sequence directly — appeared out of order | Changed `if text_response:` → `if text_response and not tool_calls:` in handle_message. Suppresses Claude pre-tool chatter whenever a tool is being called. | ✅ Fixed |
| Research job froze event loop — Scout unresponsive during research, heartbeat never fired | `_serper_batch()` used `requests.post()` + `time.sleep()` (synchronous) inside async function — blocks entire asyncio event loop | Replaced with `httpx.AsyncClient` + `await asyncio.sleep(0.3)` | ✅ Fixed |
| `/dedup_accounts` destroyed data — 301 rows → 13 rows | Grouped by Name Key only; "Columbus Middle School" in NE and OH had same key → one deleted | Changed composite key to `name_key + "\|" + state`; state_col_idx found from headers at runtime | ✅ Fixed |
| `/prospect_approve` "No prospect batch to approve" immediately after `/prospect` | `_last_prospect_batch` is in-memory only; Railway redeployed between the two commands, wiping the global | Not a code bug — documented. Always run `/prospect` and `/prospect_approve` back-to-back without deploying in between | ✅ Documented |
| Sequence builder JSON parse error on large districts (LAUSD) | Claude wrote email bodies causing malformed JSON; max_tokens=4000 also gave limited headroom | Bumped max_tokens to 6000; retry once without A/B variants on JSONDecodeError | ✅ Fixed |
| Research job silent for 10+ minutes at Claude extraction pass | `extract_from_multiple()` in contact_extractor.py makes 30+ synchronous `client.messages.create()` calls — each blocks the event loop | Wrapped in `await loop.run_in_executor(None, extract_from_multiple, ...)` in `_layer9_claude_extraction()` | ✅ Fixed |
| Sheet duplicates after re-running research on same district | Dedup key was `first\|last\|district` but Claude extractor varies district_name spelling (e.g. "Austin ISD" vs "Austin Independent School District") | Changed primary dedup key to email; falls back to `first\|last` for no-email contacts | ✅ Fixed |
| Research Log tab always empty | `_on_research_complete` in main.py never called `sheets_writer.log_research_job()` | Added `log_research_job()` call with timing + layer stats in notes field | ✅ Fixed |

---

## CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | Phase 1 built and deployed — Scout live on Telegram | Phase 1 |
| 2026-02-26 | Bug fixes: timezone, check-in window, hallucination prevention | Phase 1.5 |
| 2026-02-26 | Persistent memory system + GitHub commit loop built and verified | Phase 1.5 |
| 2026-02-27 | Phase 2 built: research_engine, contact_extractor, sheets_writer, keywords | Phase 2 |
| 2026-02-27 | Phase 2 verified working — research fires, contacts in sheet | Phase 2 ✅ |
| 2026-02-27 | Phase 3 designed — GAS bridge approach chosen over OAuth2 (IT restriction) | Phase 3 |
| 2026-02-27 | Phase 3 built: Code.gs, gas_bridge.py, voice_trainer.py, email_draft.md | Phase 3 |
| 2026-02-27 | 6 Phase 3 deployment crashes debugged and fixed | Phase 3 |
| 2026-02-27 | Phase 3 verified — Scout online, Telegram message received | Phase 3 ✅ |
| 2026-02-28 | Phase 4 built: github_pusher.py, sequence_builder.py, updated main.py + claude_brain.py | Phase 4 |
| 2026-02-28 | Bug fix: Claude API 400 — tool_result blocks not appended to conversation history | Phase 4 |
| 2026-02-28 | Bug fix: Scout boot crash — Phase 4 top-level imports before files uploaded → lazy imports | Phase 4 |
| 2026-02-28 | GAS bridge fully live: new deployment, fixed ping handler, /ping_gas working | Phase 3 ✅ |
| 2026-02-28 | /train_voice ran successfully — voice profile built from 40 emails | Phase 3 ✅ |
| 2026-02-28 | Phase 4 verified — Scout online, all tools registered | Phase 4 ✅ |
| 2026-02-28 | Phase 4.5 built: Code.gs pagination + inline thread context, gas_bridge.py paginated fetch, voice_trainer.py full rewrite | Phase 4.5 |
| 2026-02-28 | Bug fixes: GAS SECRET_TOKEN placeholder, /push_code Telegram truncation, /train_voice no ack, sample cap logic | Phase 4.5 |
| 2026-02-28 | Phase 4.5 verified — /train_voice fetched 273 emails with paired context, voice profile rebuilt | Phase 4.5 ✅ |
| 2026-02-28 | main.py: fetch-first /push_code, immediate train_voice ack, /grade_draft, /add_template | Phase 4.5 ✅ |
| 2026-02-28 | Phase 5 fully designed: Call Intelligence Suite architecture, all decisions documented | Phase 5 design ✅ |
| 2026-02-28 | Phase 5 built: tools/fireflies.py, agent/call_processor.py, agent/webhook_server.py | Phase 5 |
| 2026-02-28 | Phase 5: Code.gs updated with createGoogleDoc action | Phase 5 |
| 2026-02-28 | Phase 5: gas_bridge.py create_google_doc(), claude_brain.py 2 new tools, main.py asyncio.gather | Phase 5 |
| 2026-02-28 | Phase 5: SETUP_PHASE5.md written, MASTER.md updated | Phase 5 |
| 2026-02-28 | Bug fixes: aiohttp missing, FIREFLIES_API_KEY ImportError, get_file_content handler missing | Phase 5 |
| 2026-02-28 | Phase 5 code fully deployed — Fireflies account setup + verification pending | Phase 5 |
| 2026-03-01 | Phase 5 debugging: Fireflies GraphQL schema fixed (dateString, participants, meeting_attendees) | Phase 5 |
| 2026-03-01 | /recent_calls: single clean message, sort by date, internal meeting filter by attendee email | Phase 5 |
| 2026-03-01 | /recent_calls: optional count argument (/recent_calls 10), capped 1-20 | Phase 5 |
| 2026-03-01 | /brief: immediate ack within 5 seconds for all long-running commands | Phase 5 |
| 2026-03-01 | /brief: fixed silent crash — PRECALL_BRIEF_FOLDER_ID read from os.environ not config.py | Phase 5 |
| 2026-03-01 | /brief: fixed 400 on follow-up — try/except wraps all tool calls, tool_result always appended | Phase 5 |
| 2026-03-01 | /brief: fixed "str has no attribute get" — _parse_guests() handles string and dict guest formats | Phase 5 |
| 2026-03-01 | /brief working end-to-end — Google Doc creation still failing silently (fix generated, pending upload) | Phase 5 |
| 2026-03-01 | call_processor.py updated: _create_brief_doc surfaces real error instead of generic fallback message | Phase 5 ⏳ |
| 2026-03-01 | Migrated from MASTER.md to lean CLAUDE.md + SCOUT_HISTORY.md for Claude Code CLI | Meta |
| 2026-03-01 | GAS DocumentApp OAuth: added params = params \|\| {} to createGoogleDoc, ran to trigger auth, new deployment | Phase 5 |
| 2026-03-01 | /brief: Claude was responding with text instead of calling tool when history long — fixed by bypassing Claude | Phase 5 |
| 2026-03-01 | /brief and /call now call execute_tool() directly like /recent_calls — no Claude routing for explicit commands | Phase 5 |
| 2026-03-01 | /brief still failing after bypass fix — root cause unknown, context exhausted before diagnosing | Phase 5 ⏳ |
| 2026-03-01 | Session 3: GAS DriveApp OAuth fixed — revoked old token, added explicit oauthScopes to appsscript.json, fresh deployment | Phase 5 |
| 2026-03-01 | Session 3: Code.gs toISOString() fix — auto pre-call brief trigger now fires correctly | Phase 5 |
| 2026-03-01 | Session 3: /call fixed — Fireflies schema: removed summary.keywords, speaker_name fix, GraphQL variables, better error handling | Phase 5 |
| 2026-03-01 | Session 3: Post-call output reformatted — tighter Telegram summary, Salesforce block dropped code block, extraction prompt conciseness added | Phase 5 |
| 2026-03-01 | Session 3: Outreach.io sheet write removed from post-call flow (_build_outreach_row kept for future use) | Phase 5 |
| 2026-03-01 | Session 3: Phase 5 fully verified ✅ — all features working, Fireflies webhook configured (pending first real call) | Phase 5 ✅ |
| 2026-03-02 | Phase 6A built: sequence_builder.py fully implemented, 17-archetype sequence_templates.md created | Phase 6A |
| 2026-03-02 | /build_sequence: routes through Claude for questions, execute_tool sends result directly to Telegram | Phase 6A |
| 2026-03-02 | Sequence output: Google Doc via GAS bridge, folder support, CST timestamp in doc header | Phase 6A |
| 2026-03-02 | Code.gs createGoogleDoc: DriveApp folder-move wrapped in try/catch — doc creation never fails due to folder move error | Phase 6A |
| 2026-03-02 | SEQUENCES_FOLDER_ID env var added — strips ?query params automatically | Phase 6A |
| 2026-03-02 | Phase 6A nearly verified — GAS redeploy pending to activate try/catch folder-move fix | Phase 6A ⏳ |
| 2026-03-02 | Session 5: GAS redeploy completed — createGoogleDoc try/catch now live | Phase 6A |
| 2026-03-02 | Session 5: /build_sequence fully verified end-to-end — questions, sequence, doc, correct folder | Phase 6A ✅ |
| 2026-03-02 | Session 5: Bug fix — duplicate "Got it — building..." message after sequence output. Fixed with `if text_response and not tool_calls:` in handle_message (main.py line 707) | Phase 6A ✅ |
| 2026-03-02 | Session 6: Phase 6B built — 4 new research layers (L11-L14), Serper safety cap 100 (enforced), "keep digging" command, enqueue_batch(), research_batch tool | Phase 6B |
| 2026-03-02 | Session 6: Steven's sales territory saved to memory/preferences.md and committed to GitHub | Meta |
| 2026-03-02 | Session 6: STATE_ABBREVIATIONS dict added to keywords.py for L13 state DOE searches | Phase 6B |
| 2026-03-02 | Session 6: Bug fix — requests.post() + time.sleep() in _serper_batch() blocked asyncio event loop. Replaced with httpx.AsyncClient + await asyncio.sleep() | Phase 6B |
| 2026-03-02 | Session 6: Bug fix — extract_from_multiple() makes 30+ synchronous Claude API calls — froze event loop ~10 min. Fixed with loop.run_in_executor(None, ...) in _layer9_claude_extraction() | Phase 6B |
| 2026-03-02 | Session 6: Heartbeat added — asyncio task in ResearchQueue._worker() pings Telegram every 60s with elapsed time. Works now that event loop is unblocked. | Phase 6B |
| 2026-03-02 | Session 6: Layer effectiveness tracking — _add_raw_from_serper() now takes layer_tag; url→layer dict built; layer_contact_counts included in result dict | Phase 6B |
| 2026-03-02 | Session 6: Richer completion message — time elapsed, Serper queries, verified count, new-to-sheet, dupes skipped, per-layer contact breakdown | Phase 6B |
| 2026-03-02 | Session 6: Bug fix — _on_research_complete never called log_research_job(). Research Log tab was always empty. Added call with notes field containing layer stats + timing. | Phase 6B |
| 2026-03-02 | Session 6: Bug fix — sheet dedup keyed on first\|last\|district but Claude varies district_name spelling across runs → duplicates. Switched to email as primary key. | Phase 6B |
| 2026-03-02 | Session 7: Phase 6B verified end-to-end ✅ — heartbeat, completion message, Research Log, no duplicates, batch queue all passing | Phase 6B ✅ |
| 2026-03-02 | Session 7: Full sales tech stack mapped — Salesforce (source of truth), Outreach.io (sequences + tracking), Gmail (threads + notifications), PandaDoc (quotes), Zoom/Fireflies (video calls), Dialpad (phone/texts). No API permissions for any except Gmail. | Phase 6C design |
| 2026-03-02 | Session 7: Gmail intelligence hub pattern — parse PandaDoc open/sign/reject emails + Dialpad call summary emails from Gmail inbox using gas.search_inbox(). No API needed. | Phase 6C design |
| 2026-03-02 | Session 7: Outreach handoff pattern — Scout builds sequences → Google Doc formatted for Outreach paste-in. Outreach handles actual sending + open/click tracking. | Phase 6C design |
| 2026-03-02 | Session 7: Salesforce CSV import pattern — Steven exports reports as CSV, Scout imports to Google Sheets tabs (Active Accounts, Pipeline). No API access. | Phase 6C design |
| 2026-03-02 | Session 7: Active accounts CSV format documented. 12 columns. Parent Account = always district. Account Name = school/district/library/business. Inconsistent casing in Salesforce data — normalize on import. | Phase 6C design |
| 2026-03-02 | Session 7: Dialpad call summary emails — Steven must enable in Dialpad → Settings → Notifications → Call Summary before Gmail intelligence can parse them. | Phase 6C design |
| 2026-03-02 | Session 7: Phase 6C–6F roadmap finalized. 6C=Activity Tracking+KPI+CSV import+Gmail intel, 6D=Daily Call List (10/day district expansion contacts), 6E=District Prospecting Queue, 6F=Pipeline Snapshot | Phase 6C design |
| 2026-03-02 | Session 7: Call list v1 strategy — 10 contacts/day, start with district curriculum/CS contacts for districts where CodeCombat already has ≥1 active school (from active accounts CSV). Pre-call card includes which school(s) are active. | Phase 6D design |
| 2026-03-02 | Session 8: Phase 6C built and pushed to GitHub. activity_tracker.py (Activities + Goals tabs, Gmail scan), csv_importer.py (Salesforce CSV via Telegram file upload), sheets_writer.py (4 new tabs), main.py (activity hooks + /progress + /sync_activities + /set_goal + handle_document), claude_brain.py (4 new tools, model→claude-sonnet-4-6), morning_brief.md + eod_report.md (real data injection). | Phase 6C ✅ built |
| 2026-03-02 | Session 8: CSV upload pattern decided — Steven sends .csv file directly in Telegram chat. handle_document() downloads via Telegram file API, decodes utf-8-sig (handles BOM), passes to csv_importer.import_accounts(). No GAS changes required. | Phase 6C |
| 2026-03-02 | Session 8: New critical rules added — Telegram document handler is separate from text handler; activity_tracker + csv_importer are top-level imports (not lazy); sync_gmail_activities is synchronous (use run_in_executor); decode CSV with utf-8-sig not utf-8; import_accounts clears-then-rewrites (not additive). | Meta |
| 2026-03-02 | Session 8: Phase 6C pushed to GitHub (commit a2ef953). Railway auto-deploy triggered. Verification pending next session. | Phase 6C ⏳ verify |
| 2026-03-04 | Session 9: Phase 6C verified ✅ — all 5 steps passed (/progress, CSV upload, /sync_activities, research → Activities tab, startup message) | Phase 6C ✅ |
| 2026-03-04 | Session 9: Fireflies webhook did not auto-fire after first real call (15 min passed, nothing happened). Root cause: webhook configured but may have HMAC signature format mismatch + webhook config uncertainty. | Phase 5 bug |
| 2026-03-04 | Session 9: Built Fireflies Gmail polling — polls every 60s for recap emails, triggers processing automatically. Retries 5× with Telegram updates. Eliminated webhook dependency for primary trigger. | Phase 5+ |
| 2026-03-04 | Session 9: Bug fix — on reboot, `_fireflies_email_triggers` was empty so all recent Fireflies emails appeared new → replayed last 3 meetings. Fixed with startup seeding: first scan adds all existing emails to dedup set without processing. | Phase 5+ |
| 2026-03-04 | Session 9: Bug fix — account classifier used `is_district = not bool(parent)` which was wrong. Replaced with `classify_account()` using SF Type field, parent presence, name patterns. Returns district/school/library/company. | Phase 6C |
| 2026-03-04 | Session 9: `classify_account()` — district check runs BEFORE school keyword check. Required so "Austin Independent School District" hits district before "school" keyword. Parenthetical check runs before district check so "(Medina Valley ISD)" suffix doesn't trigger district classification. | Phase 6C |
| 2026-03-04 | Session 9: Name rules added — ends in "school" → school; ends in "schools" → district; contains "school" anywhere → school; contains "sch" as word → school. | Phase 6C |
| 2026-03-04 | Session 9: Column schema change — "Is District" (TRUE/FALSE) replaced by "Account Type" (district/school/library/company) and "SF Type" (raw Salesforce field). `get_districts_with_schools()` and `get_import_summary()` updated to use Account Type. | Phase 6C |
| 2026-03-04 | Session 9: Bug fix — Active Accounts header row not updated after schema change. `_ensure_tab()` had `if not values` guard that skipped header write when tab already existed. Removed guard — always overwrites A1. | Phase 6C |
| 2026-03-04 | Session 9: `normalize_name()` now strips parenthetical district tags. "Jefferson Elementary (Medina Valley ISD)" → "jefferson elementary". | Phase 6C |
| 2026-03-04 | Session 10: Phase 6D built — Daily Call List. New module `tools/daily_call_list.py` with two-path matching, ranking, max 3 per district, backfill, template talking points, Google Doc output, Telegram preview. | Phase 6D |
| 2026-03-04 | Session 10: `sheets_writer.get_leads()` added — reads all leads from Leads tab as list[dict] with optional state_filter. | Phase 6D |
| 2026-03-04 | Session 10: `activity_tracker` — added `call_list_generated` activity type and label in get_activity_summary(). | Phase 6D |
| 2026-03-04 | Session 10: `claude_brain.py` — added `generate_call_list` tool definition (23 tools total). | Phase 6D |
| 2026-03-04 | Session 10: `main.py` — `/call_list` direct dispatch (Pattern A), `generate_call_list` execute_tool handler, Phase 6D startup message, `daily_call_list` imported at top (not lazy). | Phase 6D |
| 2026-03-04 | Session 10: Design decision — template talking points over Claude-generated. Fast, free, no API latency. Templates reference specific active school names from Active Accounts tab. | Phase 6D |
| 2026-03-04 | Session 10: Design decision — two-path matching. Lead's District Name matched against priority district name_key (path 1) OR lead's Account matched against school display_name under priority district (path 2). | Phase 6D |
| 2026-03-04 | Session 10: Design decision — max 3 contacts per district for coverage spread. Backfill with any lead that has email+title if <10 priority matches. | Phase 6D |
| 2026-03-04 | Session 10: Design decision — reuse SEQUENCES_FOLDER_ID for call list docs. Doc title "Daily Call List — {date}" distinguishes from sequences. CALL_LIST_FOLDER_ID env var supported but not required. | Phase 6D |
| 2026-03-04 | Session 11: Bug fix — call_processor.py used claude-opus-4-5 which is deprecated. API calls hung indefinitely (SDK default timeout = 10 min). Updated all 3 messages.create() calls to claude-sonnet-4-6. Added timeout=90.0 to Anthropic client. | Phase 5 |
| 2026-03-04 | Session 11: Bug fix — recap email draft silently skipped when Fireflies attendees had no email. Fixed: falls back to Claude-extracted contact_email from transcript. | Phase 5 |
| 2026-03-04 | Session 11: Bug fix — GAS create_draft threw "Invalid To header" when extracted email was malformed (e.g. rouseem@cpsboe.k12.oh.u truncated from transcript). Added _is_valid_email() check. Shows warning in Telegram summary instead of crashing. | Phase 5 |
| 2026-03-04 | Session 11: Feature — /call email override. Usage: `/call [id] correct@email.com`. Parses second token as email if it contains @. Passed through both direct dispatch handler and execute_tool → process_transcript(email_override=...). Lets Steven fix a malformed extracted email without full reprocessing. | Phase 5 |
| 2026-03-04 | Session 11: UX — renamed "Scout's Take" → "Key Insights" in _format_telegram_summary in call_processor.py. | Phase 5 |
| 2026-03-04 | Session 11: Phase 6D verification started but not completed (paused at context limit). Code review passed. Verification steps 1-7 to complete next session. | Phase 6D ⏳ | Phase 6D |
| 2026-03-06 | Session 12: Layer 15 (Email Verification & Discovery) added to research_engine.py. Runs after L10. Step 3 = Serper search of quoted email → VERIFIED/LIKELY/INFERRED heuristic. Step 4 = enrichment search for high-priority contacts via Claude extraction. Step 5 = @domain discovery searches. 30-query hard cap. L10 re-runs after L15 to dedup/sort new contacts. | Phase 6B+ |
| 2026-03-06 | Session 12: contact_extractor.py — model updated from claude-opus-4-5 → claude-sonnet-4-6. Affects L9 Claude extraction and L15 enrichment/discovery passes. | Phase 6B+ |
| 2026-03-06 | Session 12: Bug fix — csv_importer.get_districts_with_schools() had wrong targeting logic. Was filtering on Account Type == "district" → only returned 2 entries for SoCal data. Fixed: now starts from school accounts, groups by Parent Account, excludes parent districts that already appear as district-type entries. Correctly surfaces all districts with a school foothold but no district deal. | Phase 6D |
| 2026-03-06 | Session 12: Business model alignment — CodeCombat sells to districts, schools, libraries, after-school orgs, and individuals. "District deal" = usually multi-site (e.g. all middle schools), not fully district-wide. Full district-wide = rare goal. Active district accounts = already have a deal, not primary prospecting targets — best use is referrals/references. Targeting priority = parent districts with most active school accounts. | Meta |
| 2026-03-06 | Session 12: Scout mission redefined — force multiplier, not just assistant. Designed to be taught and trained, handles operational/analytical heavy lifting so Steven focuses on relationships and closing. | Meta |
| 2026-03-06 | Session 12: Railway 409 Conflict on redeploy documented as expected behavior — old container takes ~30s to stop while new one starts. Both briefly poll Telegram → 409. Self-resolves. Not a bug. | Meta |
| 2026-03-06 | Session 12: Phase 6D verification: Step 1 ✅ (SoCal CSV uploaded — 55 accounts: 2 districts, 46 schools, 7 other). Paused at Step 2 (research a parent district) due to context limit. | Phase 6D ⏳ |
| 2026-03-06 | Session 13: Bug fix — layer count message in main.py still said "14-layer run". Updated to "15-layer run". Comment in research_engine.py updated to reflect ~57 queries for 15-layer run. | Phase 6B+ |
| 2026-03-06 | Session 13: Bug fix — /call_list routed to /call handler. `startswith("/call")` matched both. Fixed: added `and not user_text.lower().startswith("/call_list")` guard to the /call elif in handle_message. | Phase 6D |
| 2026-03-06 | Session 13: Bug fix — call list backfill ignored per-district cap. Backfill loop selected 7 contacts from Austin ISD (all backfill). Fixed: backfill now uses `district_counts` dict with `_MAX_PER_DISTRICT` cap same as priority match loop. | Phase 6D |
| 2026-03-06 | Session 13: District name normalization — normalize_name() now strips standalone "unified" (previously only stripped as part of "unified school district"). "Los Angeles Unified" now → "los angeles" matching "Los Angeles Unified School District". | Phase 6D |
| 2026-03-06 | Session 13: District abbreviation expansion — added _KNOWN_ABBREVIATIONS dict to csv_importer.py (30+ entries: LAUSD, HISD, AISD, CPS, NYCDOE, etc.). normalize_name() expands abbreviations before suffix stripping so "LAUSD" and "Los Angeles Unified School District" both produce key "los angeles". | Phase 6D |
| 2026-03-06 | Session 13: Call list cap changed 3 → 2 per district (_MAX_PER_DISTRICT constant). Applies to both priority match loop and backfill loop. | Phase 6D |
| 2026-03-06 | Session 13: Call list sort order improved. Old: (has_title, school_count, confidence). New: (is_verified, title_rank, school_count, confidence). is_verified = HIGH or MEDIUM email confidence. title_rank via _get_title_rank() — CS/CTE/Curriculum Director highest, Teacher lowest, CS keyword boost (+1) within tiers. | Phase 6D |
| 2026-03-06 | Session 13: Railway build cache diagnosis pattern — if behavior doesn't match code, add logger.info(f"cap={CONSTANT}") and redeploy. Check Railway logs for that line. If expected value absent, Railway served stale cache. Trigger manual redeploy. | Meta |
| 2026-03-06 | Session 13: Documented — Railway 409 overlap window causes test commands to be processed by OLD container. Always wait for Scout's "Scout is online" startup message before testing after redeploy. | Meta |
| 2026-03-06 | Session 13: District naming rule — same district can be "LAUSD", "Los Angeles Unified", "Los Angeles USD", "Los Angeles Unified School District". normalize_name() handles it automatically. When in doubt about which district Steven means, always ask before proceeding. | Meta |
| 2026-03-06 | Session 13: Phase 6D fully verified ✅ — LAUSD research → /call_list → 10 contacts from 5 districts with correct cap + sort → Google Doc with full call cards + talking points → call_list_generated activity logged. | Phase 6D ✅ |
| 2026-03-07 | Session 14: Phase 6E planning — two-strategy prospecting queue designed (upward/reference + cold). 8-tier priority system. Detailed sequence building rules captured. | Phase 6E design |
| 2026-03-07 | Session 14: `tools/district_prospector.py` created — Serper discovery, upward target suggestion from Active Accounts, priority scoring, Prospecting Queue tab management, approve/skip/status flow, Telegram formatting. | Phase 6E |
| 2026-03-07 | Session 14: `agent/main.py` partially updated — import + global state + 7 new slash commands (discover, upward, approve, skip, add, all, prospect). Still needs: callback, scheduler hooks, startup message, claude_brain tool. | Phase 6E ⏳ |
| 2026-03-07 | Session 14: Sequence building rules saved to `memory/sequence_building_rules.md` — pacing (cold 4-5 steps/4 weeks, warm 3-4 steps/10-14 days), frameworks (3Ps, AIDA, Intent-Based), role-specific guidance, Outreach.io variables, fabrication prohibition. | Phase 6E |
| 2026-03-07 | Session 14: Prospecting priority tiers — Tier 1: upward 3+ schools (900+). Tier 2: upward highest licenses (800+). Tier 3: cold small/medium (700+). Tier 4: upward 1 school large district (600+). Tiers 5-7: deferred. Tier 8: cold large (300+). Small/medium always rank above large. | Phase 6E |
| 2026-03-07 | Session 14: Deferred features — NCES master lists (all districts+schools in territory), free usage data (Tier 5, no export available), geographic proximity (Tiers 6-7, needs geocoding). | Phase 6E |
| 2026-03-07 | Session 14: Critical rule — NEVER fabricate claims about active accounts in sequences. Only cite verifiable facts (school name, license count). No assumed success/engagement. | Meta |
| 2026-03-07 | Session 15: Bug fix — `global _last_prospect_batch` appeared in 5 separate elif blocks in handle_message(). Python SyntaxError if variable is used before `global` declaration in same scope. Moved to single `global` line at top of handle_message() alongside conversation_history and _pending_draft. | Phase 6E |
| 2026-03-07 | Session 15: `_on_prospect_research_complete(result, prospect)` callback added. Runs standard _on_research_complete first, then auto-builds strategy-aware sequence via sequence_builder (lazy import), writes Google Doc, marks prospect complete in queue, sends summary to Telegram. Upward sequences get 4 steps + fabrication warning; cold get 5 steps. | Phase 6E |
| 2026-03-07 | Session 15: `discover_prospects` tool added to claude_brain.py (24 tools total) + execute_tool() handler in main.py. Allows Claude to discover districts via natural language. | Phase 6E |
| 2026-03-07 | Session 15: Morning brief now shows 5 pending prospects after the brief text. Uses district_prospector.get_pending(5) via run_in_executor. | Phase 6E |
| 2026-03-07 | Session 15: Hourly check-in now suggests 1-2 pending districts when research queue is idle. Helps Steven remember to approve prospects. | Phase 6E |
| 2026-03-07 | Session 15: EOD report now shows approved districts waiting for research with suggestion to run overnight. | Phase 6E |
| 2026-03-07 | Session 15: Reference/Upward Prospecting archetype added to sequence_templates.md (18 archetypes total). Includes CRITICAL "DO NOT FABRICATE" rule about active accounts. 3-4 steps over 10-14 days. Tone: collegial informer, not pushy vendor. | Phase 6E |
| 2026-03-07 | Session 15: PROSPECT PIPELINE section added to morning_brief.md, PROSPECTING section added to eod_report.md. | Phase 6E |
| 2026-03-07 | Session 15: Startup message updated to Phase 6E with prospect commands listed. | Phase 6E |
| 2026-03-07 | Session 15: Phase 6E deployed to Railway. "Scout is online — Phase 6E active" confirmed. End-to-end testing deferred to Session 16. | Phase 6E ⏳ verify |
| 2026-03-07 | Session 16: Bug fix — `_DISTRICT_RE` regex too greedy: `[\w\s\-\.]+` captured entire sentences before "School District" suffix. Changed to `(?:[\w\-\'\.]+\s+){1,5}` (max 5 words). Added `_clean_district_name()` with `_BAD_STARTS` set to strip filler words (high, schools, districts, in, staff, etc.). | Phase 6E |
| 2026-03-07 | Session 16: Bug fix — "Districts." not stripped because period prevented BAD_STARTS match. Fix: `re.sub(r'[^a-zA-Z]', '', word)` before checking set. Added "district" and "districts" to _BAD_STARTS. | Phase 6E |
| 2026-03-07 | Session 16: Bug fix — "SATXtoday Southwest ISD" — website name prefix leaked through. Added check: strip leading words >5 chars that aren't title case or all-caps (not a proper noun or abbreviation). | Phase 6E |
| 2026-03-07 | Session 16: Bug fix — dash/colon separator prefixes like "STEAM - Dallas ISD". Added separator detection: splits on ` - `, ` — `, ` – `, `: ` and keeps the part containing the district suffix. | Phase 6E |
| 2026-03-07 | Session 16: `/prospect_discover TX` verified ✅ — 15 clean district names, correct dedup, added to Prospecting Queue tab. Took 3 iterations to get regex right. | Phase 6E ✅ partial |
| 2026-03-07 | Session 16: `/prospect_upward` verified ✅ — 24 upward targets found from Active Accounts. State column empty for some (Salesforce data quality — school records missing Billing State). Priority ordering correct (7-school district first). | Phase 6E ✅ partial |
| 2026-03-07 | Session 16: `/prospect_clear` command added — wipes Prospecting Queue tab data rows (keeps header). Used during testing to reset between iterations. | Phase 6E |
| 2026-03-07 | Session 16: CSV merge import — new `merge_accounts()` in csv_importer.py. Default mode for CSV uploads. Updates existing rows by Name Key, appends new, leaves unmatched untouched. `/import_clear` switches to clear-and-rewrite for one upload, then resets. | Phase 6C+ |
| 2026-03-07 | Session 16: Dynamic CSV columns — `_parse_csv()` now preserves ALL CSV columns (not just _SF_COL_MAP mapped ones). Unknown columns pass through with original header name. Sheet headers extend dynamically. `_build_row_for_headers()` handles any column list. `_load_all_accounts()` reads A1:ZZ (not A:M). | Phase 6C+ |
| 2026-03-07 | Session 16: Steven uploaded 130-account Salesforce CSV (no SoCal). 125 unique accounts merged alongside existing CA accounts. 5 "missing" = duplicates: Code Wiz x5, McKeesport Area High School x2. | Phase 6C+ |
| 2026-03-08 | Session 17: SoCal territory filtering — filtered Steven's CA Salesforce export (76 accounts) to 51 SoCal-only accounts using web search to verify county for ambiguous addresses. Removed 25 NorCal/Central Valley accounts. Added County column to filtered CSV. | Phase 6C+ |
| 2026-03-08 | Session 17: Feature — `/import_replace_state [STATE]` command. New `replace_accounts_by_state()` in csv_importer.py removes all existing rows where State matches, inserts new CSV rows, leaves other states untouched. `_csv_import_state` variable in main.py with auto-reset after use. | Phase 6C+ |
| 2026-03-08 | Session 17: Feature — `/dedup_accounts` command. `dedup_accounts()` in csv_importer.py groups by Name Key, keeps row with most non-empty cells. | Phase 6C+ |
| 2026-03-08 | Session 17: **BUG — `/dedup_accounts` destroyed data.** Grouped by Name Key only (no state). Schools with same common name across different states (e.g. "Columbus Middle School" in NE and OH) were treated as duplicates. Reduced 301 rows to 13. Fixed by restoring from Google Sheets version history. **Function exists but is BROKEN — needs Name Key + State composite key.** | Phase 6C+ BUG |
| 2026-03-08 | Session 17: Active Accounts tab rebuilt — Steven provided merged 180-account complete Salesforce CSV (all states + SoCal with County column). Used `/import_clear` then uploaded to wipe and rewrite clean. | Phase 6C+ |
| 2026-03-08 | Session 18: Bug fix — `/dedup_accounts` grouped by Name Key only (no state). Same-named schools across different states (e.g. "Columbus Middle School" in NE and OH) were treated as duplicates. Fixed: composite key is now `name_key + "\|" + state`. `state_col_idx` found from headers at runtime. | Phase 6C+ ✅ |
| 2026-03-08 | Session 18: `/prospect` verified ✅ — shows top-5 pending queue sorted by priority, sets `_last_prospect_batch` for approve/skip. State was blank for SoCal districts (data artifact — rows written before SoCal import; not a code bug). | Phase 6E ✅ partial |
| 2026-03-08 | Session 18: `/prospect_approve 1` — research pipeline verified ✅. Research ran 7m35s, 54 contacts found, wrote to Leads tab. Sequence failed with JSON parse error. | Phase 6E ⚠️ |
| 2026-03-08 | Session 18: Bug fix — sequence_builder.build_sequence() JSON parse error on large districts. Claude writes email bodies with characters that produce invalid JSON. Fix: bumped max_tokens from 4000 → 6000; added retry-without-A/B-variants on JSONDecodeError (attempt 1 uses A/B variants, attempt 2 drops them for a smaller/simpler response). | Phase 6E ✅ |
| 2026-03-08 | Session 18: Feature — `/prospect_approve` now checks each district against Active Accounts before queuing research. Districts already in Active Accounts as type "district" trigger a warning + yes/no confirmation. New global `_pending_approve_force: list[dict]`. Yes/confirm/proceed queues them; no/skip/cancel clears. Clean districts queue immediately with no interruption. | Phase 6E ✅ |
| 2026-03-08 | Session 18: Documented — `_last_prospect_batch` is in-memory only. Lost on Railway redeploy or bot restart. Always re-run `/prospect` before `/prospect_approve` in a new session. | Meta |
| 2026-03-08 | Session 19: `/prospect_approve` fully verified ✅ — research (7m4s, 38 contacts) + JSON fix confirmed working on first attempt + Google Doc created + marked complete in queue. Full pipeline end-to-end passed. | Phase 6E ✅ |
| 2026-03-08 | Session 19: `/prospect_skip` verified ✅ — marks correct district from batch as skipped. | Phase 6E ✅ |
| 2026-03-08 | Session 19: `/prospect_add` verified ✅ — correctly blocks duplicate (Austin ISD already in queue). | Phase 6E ✅ |
| 2026-03-08 | Session 19: `/prospect_all` verified ✅ — full queue grouped by status (pending/approved/researching/complete/skipped) with correct counts and Doc links. | Phase 6E ✅ |
| 2026-03-08 | Session 19: Phase 6E fully verified ✅ — all 7 commands passed across Sessions 16–19. | Phase 6E ✅ |
| 2026-03-08 | Session 19: Bug fix — `get_districts_with_schools()` in csv_importer.py used `s.get("state")` (lowercase) but Active Accounts sheet rows key state as `"State"` (capital S). All upward/REF districts showed blank state in `/prospect_all`. Fixed: `s.get("State")`. Committed and pushed from Claude Code terminal. | Phase 6E ✅ |
| 2026-03-08 | Session 19: Workflow rule established — always push code from Claude Code via git (git add / git commit / git push). Never tell Steven to use Scout's `/push_code` command. That flow fetches and dumps entire file into Telegram (4,096-char limit), causing truncation and confusion. Has been problematic throughout entire buildout. | Meta |
| 2026-03-08 | Session 19: LAUSD (stuck "approved") and Corona-Norco Unified (stuck "researching") reset to "pending" via direct Sheets edit. Stale states from Session 18 crash. Not a code bug — documented workaround for recovery. | Phase 6E |
| 2026-03-08 | Session 20: Phase 6F (Pipeline Snapshot) implemented — new `tools/pipeline_tracker.py` flat module. Imports Salesforce opp CSVs into "Pipeline" Sheets tab. `/pipeline` shows summary with stage breakdown + stale alerts. `/pipeline_import` forces next CSV to Pipeline tab. Auto-detects opp vs account CSV by header (2+ of {Stage, Close Date, Close Date (2), Opportunity Name}). Always replace-all (snapshot, not merge). EOD report injects pipeline alerts when stale opps exist. No new Claude tool — both commands are direct dispatch (Pattern A). Tool count stays at 24. | Phase 6F |
| 2026-03-08 | Session 20: Test 1 passed ✅ — uploaded 71-opp Salesforce CSV, auto-detected as opp CSV, imported to Pipeline tab. $418,628 pipeline value. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Test 2 passed ✅ — `/pipeline` shows stage breakdown (Qualified Lead 25, Quote Sent 32, Interested 11, Committed 3) + 3-tier stale alerts. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Fix — Steven's Salesforce opp CSV uses "Close Date (2)" not "Close Date". Added to `_OPP_COL_MAP` and `is_opp_csv()` detection set. Also mapped extra columns: Primary Contact, Probability, Description, Type, Opportunity Owner. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Feature — `_smart_title_case()` converts ALL CAPS Salesforce names to natural sentence case. Preserves known acronyms (ISD, HS, STEM, ILT, etc.) and parenthetical abbreviations like "(ILT)". Applied to opp_name, account_name, parent_account during pipeline CSV parse. Rule: ALL Salesforce/Outreach data must be sentence-cased on import. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Fix — removed "No last activity date" as stale reason. Empty Last Activity field ≠ stale (just missing data). Only flags opps with actual old activity dates or past-due Close Dates. Reduced false stale count from 59 to 53. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Fix — deduplicated name display in stale alerts. "Bonsall High (Bonsall High)" → "Bonsall High" when Opp Name == Account Name. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Feature — 3-tier stale pipeline alerts per Steven's request. 🟠 Needs Update (14+ days since activity), 🟡 Needs Check-In / Going Stale (30+ days), 🔴 Risk Going Cold! (45+ days). Past-due Close Date escalates to at least "Needs Update". Applies to both `/pipeline` Telegram display and EOD report injection. Steven's philosophy: every opp should be touched at least every 14 days even if just noting status. | Phase 6F ✅ |
| 2026-03-08 | Session 20: Tests 3–7 still pending — `/pipeline_import` flag, account CSV no-false-positive, `/import_clear` override, EOD stale injection, empty pipeline display. | Phase 6F ⏳ |
| 2026-03-08 | Session 21: Test 3 passed ✅ — `/pipeline_import` sets flag, CSV uploaded, routed to Pipeline tab correctly. 71 opps imported ($418,628). | Phase 6F ✅ |
| 2026-03-08 | Session 21: Test 4 initially FAILED — Steven's active accounts CSV has Stage, Close Date, and Opportunity Name columns (joined Salesforce report), causing `is_opp_csv()` to misroute 176 accounts to Pipeline tab. Fixed: `is_opp_csv()` now checks for account-specific columns (# of Active Licenses, # of Opportunities) first — if present, returns False. After fix, re-tested and Test 4 passed ✅. | Phase 6F ✅ |
| 2026-03-08 | Session 21: Feature — natural language CSV description routing. Steven can describe a CSV before uploading ("this is my active accounts CSV") or as a caption on the file. `_parse_csv_intent()` detects keywords: pipeline/opportunity → Pipeline tab; account/customer/lead/contact → Active Accounts. Priority: slash commands > caption > pre-message description > auto-detect. New global `_pending_csv_intent`. | Phase 6F ✅ |
| 2026-03-08 | Session 21: Bug fix — `merge_accounts()` didn't deduplicate existing rows. If duplicates already existed in the sheet (from prior misrouted imports), merge updated only the last duplicate and left others untouched. Fixed: auto-deduplicates existing rows by Name Key before merging. Removes all but the last row for each key. | Phase 6C+ ✅ |
| 2026-03-08 | Session 21: Feature — Pipeline tab now preserves ALL CSV columns (dynamic headers). Added Type, Primary Contact, Probability (%), Description, Opportunity Owner to base columns. Extra/unknown CSV columns pass through with original header names — same pattern as csv_importer. `_build_pipeline_row()` helper matches rows to dynamic headers. Primary Contact also gets smart title case normalization. | Phase 6F ✅ |
| 2026-03-08 | Session 21: Feature — alternating row colors (banding) on all Google Sheets tabs. `cleanup_and_format_sheets()` in sheets_writer.py runs on startup. Applies white/light gray-blue alternating rows with blue header. Safe to call repeatedly — skips already-banded tabs. Also deletes unused "Sheet1" and "Salesforce Import" tabs. Removed TAB_SF_IMPORT from `ensure_sheet_tabs_exist()`. | Phase 6F ✅ |
| 2026-03-08 | Session 21: Tests 5–7 still pending — `/import_clear` override, EOD stale injection, empty pipeline display. | Phase 6F ⏳ |
| 2026-03-08 | Session 22: Tests 5–7 passed ✅ — `/import_clear` respects auto-detect routing, EOD stale injection confirmed, empty pipeline graceful. Phase 6F fully verified. | Phase 6F ✅ |
| 2026-03-09 | Session 23: Feature — `/call_list [N]` accepts optional contact count (1-50, default 10). Handler changed from exact match to `startswith` + number parsing. | Enhancement A1 ✅ |
| 2026-03-09 | Session 23: Feature — command cheat sheet (`_COMMAND_CHEAT_SHEET` constant) appended to morning brief as separate message to avoid 4K limit. Lists all key slash commands. | Enhancement A2 ✅ |
| 2026-03-09 | Session 23: Feature — lead row coloring by email confidence. `_color_leads_by_confidence()` in sheets_writer.py auto-runs after `write_contacts()`. `/color_leads` command for one-time cleanup. Colors: VERIFIED/HIGH=green, LIKELY/MEDIUM=yellow-green, INFERRED/LOW=yellow, UNKNOWN=grey. Batched in 500-request chunks. | Enhancement A3 ✅ |
| 2026-03-09 | Session 23: Feature — weekend scheduler. Saturday greeting 11am CST, Sunday 1pm CST. No auto check-ins or EOD on weekends. `mark_user_active_today()` suppresses greeting if Steven messages first. `/eod` command for manual EOD trigger (works any day). | Enhancement B1 ✅ |
| 2026-03-09 | Session 23: Bug fix — `scheduler` was a local variable inside `_run_telegram_and_scheduler()`. `handle_message()` couldn't access it → `NameError` on `scheduler.mark_user_active_today()` silently killed ALL message handling. Fixed: moved `scheduler = Scheduler()` to module-level global alongside `memory` and `conversation_history`. | Bug ✅ |
| 2026-03-09 | Session 23: A1 verified ✅ — `/call_list 5` returned 5 contacts, `/call_list 20` returned 20 contacts (12 priority + 8 backfill). | Enhancement A1 ✅ |
| 2026-03-09 | Session 23: A3 verified ✅ — `/color_leads` colored 211 rows in Leads tab. Google Sheet confirmed correct. | Enhancement A3 ✅ |
| 2026-03-09 | Session 23: B1 `/eod` verified ✅ — manual EOD report triggered on demand, full pipeline alerts included. Weekend greeting + suppression untested (will auto-verify next weekend). | Enhancement B1 ✅ |
| 2026-03-08 | Session 24: Feature — B2 Salesforce Leads & Contacts CSV import + enrichment pipeline. New module `tools/lead_importer.py` (flat module). Two new tabs: SF Leads, SF Contacts (separate from research-generated Leads tab). `/import_leads`, `/import_contacts` explicit routing. Auto-detect: lead CSV by {Lead Source, Lead Status, Company}, contact CSV by {Account Name, Department, Contact Owner}. Cross-checks against Active Accounts by email domain, account name, district name. Enrichment columns: Verified School/District/State/County, Active Account Match, Enrichment Status/Notes. `/enrich_leads` triggers Serper-based enrichment. Dedup by email or first\|last name. `_parse_csv_intent()` updated to route "lead" → SF Leads, "contact" → SF Contacts. Auto-detect priority: pipeline > sf_leads > sf_contacts > accounts. | Enhancement B2 ⏳ (not yet verified) |
| 2026-03-08 | Session 24: Architecture — `_leads_import_mode` global added to main.py (None \| "leads" \| "contacts"). Resets after use, same pattern as `_pipeline_import_mode`. Added to handle_message global declaration and handle_document global declaration. | Architecture |
| 2026-03-08 | Session 24: Architecture — CSV routing in handle_document refactored from boolean `is_opp` to string `csv_target` with 4 values: "pipeline", "sf_leads", "sf_contacts", "accounts". All existing paths preserved. | Architecture |
| 2026-03-10 | Session 25: B2 code review — no bugs found. Implementation solid: global declarations correct, CSV routing priority chain correct, all sync functions via run_in_executor, _leads_import_mode consumed after use. Minor: _parse_csv_intent docstring stale (still says pipeline\|accounts but now returns sf_leads/sf_contacts too). | Code Review |
| 2026-03-10 | Session 25: SoCal lead/contact CSV filtering — offline data cleaning (NOT Scout feature code). Built 3-pass filtering pipeline. Pass 1: matched company/account names against CDE public school directory (18,415 schools, 1,060 districts) + zip→county + city→county + email domain→district. Resolved 89-94% of records. | Data Cleaning |
| 2026-03-10 | Session 25: Pass 2 — Parent account field → CDE district, city names embedded in school names (built 1,014-city CA lookup table), deeper email domain matching (k12.ca.us, location abbreviations in domains). Resolved 585 more records. | Data Cleaning |
| 2026-03-10 | Session 25: Pass 3 — CDE private school directory (2,781 schools) + NCES Private School Survey (2,269 CA schools via FIPS county codes). Combined 4,058 unique private schools. Resolved 256 more records. | Data Cleaning |
| 2026-03-10 | Session 25: Results — Leads: 10,478 SoCal + 1,613 uncertain (of 20,737 original). Contacts: 4,100 SoCal + 212 uncertain (of 8,040 original). Overall 93%+ resolution rate with zero web searches. Remaining ~530 school/academy records queued for Serper in next session. | Data Cleaning |
| 2026-03-10 | Session 25: Discovery — Salesforce lead/contact CSVs use latin-1 encoding (not utf-8). First attempt with utf-8-sig failed with UnicodeDecodeError on byte 0xe9. Fixed by using encoding='latin-1' for reads. Output files written with utf-8-sig for Excel compatibility. | Bug Fix |
| 2026-03-10 | Session 26: Pass 4 — Serper web search on ~504 uncertain records with school/academy keywords. Searched `"School Name" California county school`, parsed results for county patterns in snippets, knowledge graph, answer boxes. Also detected non-CA states. Resolved 165 leads (65 SoCal, 83 NorCal, 17 non-CA) + 69 contacts (46 SoCal, 21 NorCal, 2 non-CA). | Data Cleaning |
| 2026-03-10 | Session 26: Pass 5 — Free lookups: 79 CA school district email domains mapped to counties (verified 5 ambiguous via web search: rbgusd.org→Kern, hcsd.k12.ca.us→San Mateo, lmusd.org→SLO, eesd.org→Santa Clara, frjusd.org→Shasta). Phone area codes (18 SoCal + 15 NorCal codes). City/District Name fields for junk/non-CA detection. Resolved 370 leads + 118 contacts at zero Serper cost. | Data Cleaning |
| 2026-03-10 | Session 26: Bug — Pass 5 `errors='replace'` on latin-1 write caused Unicode characters in County_Method (arrow → from pass4) to be replaced, but the real issue was pass 5 found 0 uncertain leads (file had already been overwritten with Yes-only rows). Root cause: pass 4 wrote with latin-1, pass 5 read and overwrote dropping all uncertain. Fixed by replaying passes 1-3 from original source file, then running pass 5 before pass 4 (saves Serper credits too). | Bug Fix |
| 2026-03-10 | Session 26: Optimal pass order discovered: run 1→2→3→5→4. Pass 5 (free lookups) before pass 4 (Serper) reduced Serper searches from 504 to 315 (saved 189 credits / $0.19). | Optimization |
| 2026-03-10 | Session 26: Final split — separated uncertain records from confirmed SoCal into dedicated files: `Leads_SoCal_Uncertain.csv` (1,128 records) and `Contacts_SoCal_Uncertain.csv` (69 records). Confirmed SoCal files now contain only Yes records: 10,677 leads + 4,170 contacts. | Data Cleaning |
| 2026-03-10 | Session 26: Total Serper credits used: ~819 (504 first run + 315 re-run after rebuild). Steven has ~1,140 credits remaining on serper.dev. | Resource Tracking |
| 2026-03-10 | Session 27: Merged SoCal filtered CSVs with rest-of-territory CSVs. Leads: 86,993 (10,677 SoCal + 76,316 other). Contacts: 19,775 (4,170 SoCal + 15,605 other). Output: `My merged leads list - Including SoCal - as of 3-7-26.csv` and `My merged contacts list - Including SoCal - as of 3-7-26.csv`. | Data Merge |
| 2026-03-10 | Session 27: Bug — B2 auto-detect failed on Steven's actual Salesforce CSV headers. Lead CSV has "Company / Account" not "Company", "Lead Owner" not "Lead Status". Contact CSV has "Account Owner" not "Contact Owner", no "Department". Fixed by expanding signal sets and column mappings. | Bug Fix |
| 2026-03-10 | Session 27: Bug — Column letter calculation in `update_enrichment()` broke for columns beyond Z (index 26+). `chr(ord("A") + col_idx - 26)` overflows at column 52. Fixed with proper `_col_to_letter()` helper using modular arithmetic. | Bug Fix |
| 2026-03-10 | Session 27: Bug — Sheets API append range `A:Z` (26 columns) too narrow for 38+ column CSVs (Salesforce base + SoCal + enrichment columns). Widened to `A:AZ`. | Bug Fix |
| 2026-03-10 | Session 27: Bug — 86K rows in single Sheets API append caused `[Errno 32] Broken pipe`. First fix (5,000-row chunks) still failed on chunks 1-2 with SSL EOF errors. Final fix: 2,000-row chunks + 3-attempt retry with 2s/4s backoff. 86,670 leads imported successfully. | Bug Fix |
| 2026-03-10 | Session 27: Feature — Added "Leads Assoc Active Accounts" and "Contacts Assoc Active Accounts" tabs. Cross-checked records written to separate tabs during import. Extracted `_append_in_chunks()` helper to DRY up chunked writes. | Feature |
| 2026-03-10 | Session 27: Redesign — Cross-check logic completely rewritten. Old logic used substring matching (`company_key in acct_key`) causing massive false positives (e.g., Pinecrest Academy matched 3 unrelated districts). New logic: exact name match only, pre-built lookup dicts, email domain roots generated from account names, state filtering. Four match types: Exact Match - School, Exact Match - District, District is Active Account, no match. Key rule: school-level active accounts only match the SAME school; district-level accounts match the whole district. Leads at different schools/districts where only a school account exists are NOT flagged (Steven can freely prospect). | Redesign |
| 2026-03-10 | Session 27: Territory updated — CA (Southern California only) now explicitly included in Steven's territory. Full list: TX, IL, PA, OH, MI, CT, OK, MA, IN, NV, TN, NE, CA (SoCal only). Updated in memory/preferences.md and MEMORY.md. | Configuration |
| 2026-03-10 | Session 27: SF Leads import verified — 86,670 leads imported (323 dupes skipped, 8,860 cross-checked with old logic). Needs re-test with redesigned cross-check logic. Contacts import not yet tested. | Verification |
| 2026-03-11 | Session 28: Bug — Google Sheets 10M cell limit hit during SF Leads import. Append range `A:AZ` (52 columns) × 87K rows = 4.5M cells. Actual data only needs ~35 columns. Fixed: `_append_in_chunks` now accepts `num_cols` param and uses tight `A:{last_col}` range. Saves ~1.5M cells on 87K import. | Bug Fix |
| 2026-03-11 | Session 28: Bug — `clear_tab()` using `deleteDimension` failed with "cannot delete all non-frozen rows" (Google Sheets won't delete all non-frozen rows when header is frozen). Fixed: replaced with `values().clear()` + `updateSheetProperties` to resize grid to 2 rows × header columns. Properly frees cells (not just values). | Bug Fix |
| 2026-03-11 | Session 28: Feature — Added `/clear_leads` and `/clear_contacts` slash commands. `/clear_leads` clears SF Leads + Leads Assoc Active Accounts tabs (data rows + grid shrink). `/clear_contacts` does same for contacts tabs. Direct dispatch pattern. | Feature |
| 2026-03-11 | Session 28: Bug — Cross-check false positives from bad Salesforce District Name data. Example: lead at Leander ISD (email @leanderisd.org) tagged as "Alvin ISD" in SF District Name → falsely matched to Alvin ISD active account. Root cause: SF District Name field is unreliable — 55 of 89 "Alvin ISD" leads had non-Alvin emails. Fixed: Step 2 (District Name match) now validates with `_domain_matches_account()` — if lead has non-generic institutional email, domain root must match district's generated roots. Generic emails (gmail etc.) still trust SF data. | Bug Fix |
| 2026-03-11 | Session 28: Enhancement — `_generate_domain_roots()` now produces acronym-based roots. First letter of each word → "Los Angeles Unified School District" = "lausd", plus acronym+suffixes → "Cypress-Fairbanks ISD" = "cfisd", "Clark County School District" = "ccsd". Also norm-words acronym → "Fort Bend" = "fb" + "isd" = "fbisd". Fixed comma bug: `norm_joined` now uses `re.sub(r"[^a-z0-9]", "", norm)` instead of just stripping spaces. | Enhancement |
| 2026-03-11 | Session 28: SF Leads re-import verified — 86,670 leads imported (323 dupes skipped), 937 cross-checked to active accounts. Data confirmed clean — no obvious false positives from bad District Name data. Contacts import still pending. | Verification |
| 2026-03-12 | Session 29: Feature — Separated SF Leads/Contacts into dedicated Google Sheet. New env var `GOOGLE_SHEETS_SF_ID`. `_get_sf_sheet_id()` reads it, falls back to main sheet. All SF lead/contact operations updated: import, clear, enrich, summary, get_unenriched, update_enrichment. Cross-check still reads Active Accounts from main sheet via csv_importer. `get_sf_sheet_url()` public helper for success message links. | Architecture |
| 2026-03-12 | Session 29: Feature — Math/algebra lead auto-filter. `_is_math_title()` checks title for keywords: math, algebra, mathematics, calculus, geometry (word-boundary, case-insensitive). Matching leads routed to "SF Leads - Math" and "Leads Assoc Active - Math" tabs instead of main tabs. `clear_leads_tabs()` clears all 4 tabs. Import summary includes `math_filtered` count. | Feature |
| 2026-03-12 | Session 29: Feature — Renamed "Leads" tab to "Leads from Research". `TAB_LEADS` constant updated in sheets_writer.py. Auto-migration in `cleanup_and_format_sheets()`: if "Leads" exists and "Leads from Research" doesn't, renames via `updateSheetProperties`. One-time migration on startup. | Feature |
| 2026-03-12 | Session 29: Feature — State/Province column moved to first position in both `SF_LEADS_COLUMNS` and `SF_CONTACTS_COLUMNS`. Row-building logic is dict-based (order-independent), so reordering the column list just changes sheet layout. | Feature |
| 2026-03-12 | Session 29: Feature — Auto-resize columns after import. `_auto_resize_columns()` calls Sheets API `autoResizeDimensions` on all written tabs (main + active + math). Graceful failure (logs warning, doesn't crash). | Feature |
| 2026-03-12 | Session 29: SF Leads re-imported to new sheet — 86,670 imported, 937 cross-checked, math leads filtered to separate tab. Confirmed correct sheet ID in success URL. | Verification |
| 2026-03-12 | Session 30: Feature — Mutually exclusive tab routing. Each lead/contact now goes to exactly ONE tab based on priority: (1) math + active account → math active tab, (2) math only → math tab, (3) active account match only → assoc active tab, (4) neither → main tab. Previously records were duplicated across multiple tabs. | Feature |
| 2026-03-12 | Session 30: Feature — Math/algebra filter extended to contacts. Previously only applied to leads. Two new tabs: `SF Contacts - Math` and `Contacts Assoc Active - Math`. New tab constants: `TAB_SF_CONTACTS_MATH`, `TAB_CONTACTS_ACTIVE_MATH`. `/clear_contacts` updated to clear all 4 contact tabs. | Feature |
| 2026-03-12 | Session 30: Feature — Tab formatting via `_format_tab()`. Replaces `_auto_resize_columns()`. Applies: frozen row 1 (header always visible), alternating row banding (blue header, white/light gray-blue rows — same colors as main sheet via `cleanup_and_format_sheets()`), column widths sized to header text length (~7px/char + 16px padding, min 50px). Banding skipped if already applied (safe to re-run). | Feature |
| 2026-03-12 | Session 30: Feature — Column reorder. `Active Account Match` moved right after `Email` column, `Last Enriched` right after that, in both `SF_LEADS_COLUMNS` and `SF_CONTACTS_COLUMNS`. Row-building is dict-based so reordering column lists just changes sheet layout. | Feature |
| 2026-03-12 | Session 30: Feature — `_ensure_tab()` now freezes row 1 on all SF tabs. Uses `updateSheetProperties` with `frozenRowCount: 1`. Also captures tab sheetId from addSheet response for new tabs. | Feature |
| 2026-03-12 | Session 30: Bug — Natural language CSV routing failed for "these are my salesforce leads". `file_context` keyword list in `handle_message()` didn't include "these are" (only had "this is"). Also missing possessive patterns like "my leads". Fixed by adding "these are", "my lead", "my contact", "my account", "my pipeline", "my opp", "about to", "going to" to detection list. | Bug Fix |
| 2026-03-12 | Session 30: Telegram message update — Import success messages now show per-tab breakdown (X → main tab, Y → active, Z → math, W → math active, total). Both leads and contacts messages updated. Clear messages also show all 4 tab counts. | Enhancement |
| 2026-03-12 | Session 30: B2 verification COMPLETE — all 8 tests passed: (1) auto-detect leads ✅, (2) auto-detect contacts ✅, (3) /import_leads explicit ✅, (4) /import_contacts explicit ✅, (5) /enrich_leads ✅, (6) /enrich_leads contacts ✅, (7) natural language routing ✅, (8) existing account/pipeline routing not broken ✅. | Verification |
| 2026-03-12 | Session 31: C1 Master Territory List — new `tools/territory_data.py` module. Urban Institute Education Data API (NCES CCD 2023). 13 states + CA SoCal. Dedicated Google Sheet via `GOOGLE_SHEETS_TERRITORY_ID` env var. Two tabs: Territory Districts (17 cols), Territory Schools (18 cols). | Feature |
| 2026-03-12 | Session 31: 4 new slash commands — `/territory_sync [state]`, `/territory_stats [state]`, `/territory_gaps <state>`, `/territory_clear`. Pattern A direct dispatch via `run_in_executor`. `territory_data` is flat module imported at top of main.py. | Feature |
| 2026-03-12 | Session 31: `/territory_sync NV` verified ✅ — 20 districts, 772 schools written correctly. `/territory_stats NV` verified ✅ — 20 districts, 772 schools, 484,588 enrolled. | Verification |
| 2026-03-12 | Session 31: Column iterations — initial schema had Name Key first. Changed to State first, Name Key last per Steven's request. Added Street, Zip, Phone columns from API. District Name moved right after School Name in schools tab. | Feature |
| 2026-03-12 | Session 31: Bug — first sync used old column order (Name Key col A), second sync appended with new order (State col A) but didn't clear old rows because `_clear_state_rows` looked for State in col 0 and found Name Key instead. Fixed by adding `/territory_clear` command. One-time issue from schema change. | Bug Fix |
| 2026-03-12 | Session 31: Bug — `/territory_gaps` showed 0 active customers. Root cause: code used `acc.get("Account Name", "")` but Active Accounts sheet column is "Display Name". Every lookup returned empty string → zero matches. | Bug Fix |
| 2026-03-12 | Session 31: Fix attempt 1 — changed to `acc.get("Display Name", "")`. Still failed because Steven requested rename to "Active Account Name" which was pushed before the Display Name fix was verified. Sheet header wasn't updated (only updates on CSV import). | Bug Fix |
| 2026-03-12 | Session 31: Fix attempt 2 — reverted rename across all 6 files back to "Display Name". Added fallback in territory_data: `acc.get("Active Account Name", "") or acc.get("Display Name", "")`. Debug logging confirmed: 3 NV accounts found, `school_parent_keys={'churchill county'}` was populated correctly with Display Name. | Bug Fix |
| 2026-03-12 | Session 31: Railway "Failed to snapshot repository" error on deploy — infrastructure issue, not code. Fixed by manual redeploy from Railway dashboard. | Infrastructure |
| 2026-03-12 | Session 31: `/territory_gaps NV` NOT YET VERIFIED — fallback fix deployed but not re-tested before session ended. Next session must verify. | Pending |
| 2026-03-12 | Session 32: `/territory_gaps NV` VERIFIED ✅ — Display Name fallback working. 3 NV school accounts found: Churchill County HS (→ Churchill district), Pinecrest Academy (→ State Sponsored Charter), New Horizons Academy (unmatched, likely private). | Verification |
| 2026-03-12 | Session 32: Bug — `/territory_gaps` lumped school accounts with district deals in "covered" count. Having a school in a district ≠ district coverage. Coverage was 10% when it should be 0%. Fixed: 4 categories now — district deals (covered), districts with school accounts (upward opportunities), in prospecting, uncovered. Coverage % only counts district-level deals. | Bug Fix |
| 2026-03-12 | Session 32: Bug — CA SoCal filter returned 0 districts. Root cause: Urban API returns `county_code` as string `"6037"`, but `SOCAL_COUNTY_CODES` set used integers `{6037}`. String never `in` int set. Fixed: changed all county code constants to strings. Railway redeploy cleared bad `/tmp` cache. | Bug Fix |
| 2026-03-12 | Session 32: `/territory_sync TX` verified ✅ — 1,242 districts, 9,765 schools. Chunked writing (2,000 rows) works at scale. | Verification |
| 2026-03-12 | Session 32: Full territory sync verified ✅ — all 13 states + CA SoCal: 8,133 districts, 40,317 schools, 20.6M students. | Verification |
| 2026-03-12 | Session 32: `/territory_stats CA` verified ✅ — 969 districts, 5,559 schools (SoCal only). County code string fix confirmed working. | Verification |
| 2026-03-12 | Session 32: C1 Master Territory List FULLY VERIFIED — all tests passed. Marked complete in roadmap. | Milestone |
| 2026-03-12 | Session 33: C3 Closed-Lost Winback — initial implementation read from Pipeline tab. Steven clarified: closed-lost opps are NOT in pipeline data. Must run separate Salesforce report and upload CSV. | Design Fix |
| 2026-03-12 | Session 33: Added separate "Closed Lost" tab in Google Sheet + `import_closed_lost()` in `pipeline_tracker.py`. REPLACE ALL mode, same CSV format as pipeline. `get_closed_lost_opps()` reads Closed Lost tab first, falls back to Pipeline. | Feature |
| 2026-03-12 | Session 33: `/import_closed_lost` command + natural language routing — "closed lost" / "winback" in caption or pre-message auto-routes to Closed Lost tab. Also `/closed_lost_import` alias. | Feature |
| 2026-03-12 | Session 33: `suggest_closed_lost_targets()` in `district_prospector.py` — reads closed-lost opps, groups by district (Parent Account or Account Name), dedupes against Active Accounts + existing queue. Strategy="winback", Source="pipeline_closed". Priority 550-749 scaled by deal amount. | Feature |
| 2026-03-12 | Session 33: `/prospect_winback` (also `/winback`) — scans Closed Lost tab for targets, adds to Prospecting Queue, shows pending batch. | Feature |
| 2026-03-12 | Session 33: Steven clarified ALL sequences should be drafts for review, not just winback. Changed `_on_prospect_research_complete` — all strategies now write to Google Doc, share link, mark status="draft". Never auto-finalize. | Design Fix |
| 2026-03-12 | Session 33: New "draft" status added to Prospecting Queue (between researching and complete). Emoji: 📝. | Feature |
| 2026-03-12 | Session 33: Rich winback sequence context — Outreach.io variables ({{first_name}}, {{state}}, {{company}}), reply emails, incentivization, breakup email, loss-reason context (85% budget rejection, 15% competitor). 5 steps for winback/cold, 4 for upward. | Feature |
| 2026-03-12 | Session 33: Saved winback business context — 85% of closed-lost deals are budget/cost rejection (teachers go unresponsive after admin says no), ~15% competitor chosen (don't understand full offering). Teachers get discouraged asking admins. | Context |
| 2026-03-12 | Session 33: C3 Closed-Lost Winback IMPLEMENTED — needs closed-lost CSV from Salesforce to verify end-to-end. | Milestone |
| 2026-03-15 | Session 34: C3 date window rewritten — dual-edge (buffer_months + lookback_months). `/prospect_winback all` for full history. `/prospect_winback buffer=N lookback=N` for custom. | Feature |
| 2026-03-15 | Session 34: Lost Reason, Contact: Email, Fiscal Period, Lead Source mapped as proper columns in pipeline_tracker. CLOSED_LOST_EXTRA_COLUMNS added. | Feature |
| 2026-03-16 | Session 34: Winback grouping fixed — group by Account Name (actual deal target), not Parent Account. School deals stay school-level. | Design Fix |
| 2026-03-16 | Session 34: Territory cross-check for winback — 17/93 schools resolved to parent district via exact name match. Fuzzy matching needed. | Feature |
| 2026-03-18 | Session 34: Prospecting Queue column redesign — State first, Account Name, Deal Level, Parent District, then ops columns, Notes always last. 16 columns total. | Feature |
| 2026-03-18 | Session 34: clear_queue range fixed A2:N → A2:Z to cover all 16 columns. | Bug Fix |
| 2026-03-19 | Session 34: Full roadmap recovered from old session transcripts (Session 22, c102c090). Saved to memory/roadmap_full.md. | Recovery |
| 2026-03-19 | Session 34: C3 FULLY VERIFIED — all 5 tests passed (import, scan, spot-check, approve+research, sequence draft). | Milestone |
| 2026-03-20 | Session 34: Outreach.io OAuth integration — connected as Steven (user ID 11). Read-only. Tokens persist via GitHub. | Feature |
| 2026-03-20 | Session 34: `/connect_outreach`, `/outreach_status`, `/outreach_sequences` commands added. | Feature |
| 2026-03-20 | Session 34: Outreach secret regenerated — original from IT had encoding issues. Copy button on dev portal works. | Bug Fix |
| 2026-03-21 | Session 34: C4 cold license request scan built — pulls from 3 sequences (507, 1768, 1860), filters by opp/pricing/territory/international. | Feature |
| 2026-03-21 | Session 34: `/c4`, `/c4_clear` commands. Background task execution. C4 Audit tab for spot-checking. | Feature |
| 2026-03-21 | Session 34: NoneType crash fix — Outreach prospects can have null company/name/email fields. | Bug Fix |
| 2026-03-21 | Session 34: Outreach token persistence moved to GitHub (memory/outreach_tokens.json) — /tmp wiped on Railway deploys. | Bug Fix |
| 2026-03-21 | Session 34: Stale OAuth callback prevention — ignore duplicate callbacks if already authenticated. | Bug Fix |
| 2026-03-22 | Session 34: Pricing detection tightened — PandaDoc /d/ links only, subject line match, template body content (digital quote + pricing tiers). Reduced false positives. | Feature |
| 2026-03-22 | Session 34: International email TLD filter + CA/NorCal exclusion for unmatched CA prospects. | Feature |
| 2026-03-23 | Session 34: territory_matcher.py created — 5-tier fuzzy matching against NCES data. Core utility for all features. | Feature |
| 2026-03-23 | Session 34: Claude Sonnet batch inference for unresolved prospect locations (batches of 40). | Feature |
| 2026-03-23 | Session 34: Bulk mailing scan — 3 API calls instead of 1,600+. Scan time 25min → 2min. | Performance |
| 2026-03-23 | Session 34: C4 spot-check found 5 issues: email domain ranking, SoCal detection, Claude prompt, student exclusion, lead-level columns. Documented in memory. | Issues |
| 2026-03-23 | Session 34: Winback loss-reason context updated with actual data — 61% Unresponsive, 19% Budget, 5% Not using, 4% Turnover, 2% Competitor. | Context |
| 2026-03-23 | Session 34: Product status saved — AI Junior = beta (NOT released), AI Algebra = launched, CyberSecurity = fall 2026. | Context |
| 2026-04-04 | Session 43: C4 prospect enrichment — 2 passes (audit_c4_prospects.py, enrich_c4_titles.py, enrich_c4_pass2.py). 418 titles via Outreach/SF/Serper/Claude, 304 more via NCES/school websites. State, parent district, international detection. | Feature |
| 2026-04-04 | Session 43: C4 sequence copy — 7 iterations with Steven. 4 entity-based sequences (Teachers, District Admin, School General, District General). All under 80/120 word limits. | Feature |
| 2026-04-04 | Session 43: C4 Outreach sequences created — IDs 1995-1998 via create_c4_sequences.py. Schedule ID 50 "C4 Tue-Thu Morning" (Tue/Wed/Thu 8-10 AM). Template ID 43784 reused as Step 2. | Feature |
| 2026-04-04 | Session 43: 1,119 C4 prospects loaded into Outreach sequences. 135 timezones updated via state mapping. 11 CUE sequences patched with missing delivery schedules. | Feature |
| 2026-04-04 | Session 43: Outreach timeZone field is camelCase (not timezone) — bulk update initially returned 400 for all 1,166 prospects. | Bug Fix |
| 2026-04-04 | Session 43: Trigger aggregator research — K-12 buying signals ranked, Burbio deep dive, AI aggregator architecture, MCP inventory. Full doc: docs/trigger_aggregator_research.md. | Research |
| 2026-04-04 | Session 43: GAS bridge search_inbox_full added — full email bodies with pagination, labels, message/thread IDs. Code.gs + gas_bridge.py updated and deployed. | Feature |
| 2026-04-04 | Session 43: Gmail signal inventory — 29 Google Alerts (359 emails), 41 Burbio newsletters, 118 DOE/newsletter emails. Only OK + TN subscribed (11 states missing). | Discovery |
| 2026-04-04 | Session 43: Railway API access configured — team token for pulling env vars programmatically. Project/env/service IDs saved to memory. | Feature |
| 2026-04-04 | Session 43: Sequence copy rules saved to memory — Steven's detailed feedback on tone, length, CTAs, subject lines, pacing, anti-fabrication. | Context |

---

## Session 49 (2026-04-08) — Email Auto-Drafter, 5 Parked Features, Lead Gen Tier A

### Email Reply Auto-Drafter (Railway production)
- **NEW:** `tools/email_drafter.py` — polls unread inbox every 5 min during business hours (7 AM-6 PM CST weekdays). Classifies via Claude Haiku (DRAFT/FLAG/SKIP), drafts via Claude Sonnet 4.6 with `memory/voice_profile.md` + `memory/response_playbook.md`, creates threaded HTML drafts via GAS bridge. Daily summary in EOD report. Manual trigger: `/draft_emails`. Force re-scan after redeploy: `/draft force`.
- **GAS upgrade:** `Code.gs createDraft()` now accepts `thread_id`, `cc`, `content_type`. New `threadHasDraft()` helper iterates `GmailApp.getDrafts()` and returns true if any draft exists on that thread. New `skip_if_draft_exists` flag (default true from Python) prevents duplicate drafts. Returns `{success: false, already_drafted: true}` which `gas_bridge._call()` passes through without raising.
- **Startup seeding:** First run after deploy marks all existing unread emails as already-seen so Scout doesn't draft for the entire backlog. `clear_processed_cache()` resets the in-memory set for `/draft force`.

### 5 Parked Features Shipped (Tier A from inherited plan)
- **F1 Fuzzy matching for winback + call list:** Added `csv_importer.fuzzy_match_name()` fallback in `suggest_closed_lost_targets()` and `daily_call_list._match_priority_leads()` after exact key match fails. Production result: 30/93 schools resolved (12 exact + 18 fuzzy) vs 17/93 baseline.
- **F2 Contact extractor improvements:** Content window 12K→20K chars (covers longer staff directory pages), known-contacts dedup injection (loads existing leads from district, injects "DO NOT re-extract these people" into prompt). Module-level cache `_known_contacts_cache` keyed by normalized district name.
- **F3a Procurement queries in RFP scanner:** Added `site:bidnet.com` and `site:bonfirehub.com` queries to `scan_rfp_opportunities()`.
- **F3b RSS feeds expanded:** Added EdSurge (`articles_rss`) and CoSN to RSS_FEEDS list. Both tested via feedparser and verified returning entries.
- **F3c Persistent superintendent directory:** New `memory/superintendent_directory.json` in GitHub memory. `update_superintendent_directory()` upserts from leadership scan results, detects real person-name changes (logs as change events), `get_superintendent(district)` lookup ready for future email personalization. Persisted via `github_pusher.push_file()`.
- **F4 Unanswered outreach tracker:** New `get_unanswered_emails(days, gas_bridge, max_recipients)` in `tools/activity_tracker.py`. Fetches sent emails, dedups by recipient (most recent only), splits comma-separated `to` field, checks inbox for replies via `gas.search_inbox(f"from:{addr}")`, returns sorted by days_since. tz-aware date parsing via `dateutil.parser`. New `/unanswered [days]` Telegram command. 30-recipient cap.
- **F5 Tool eval:** New `docs/tool_evaluation_2026_04.md`. Documents Serper/Exa/Firecrawl/Jina/Crawl4AI/Tavily landscape. Recommendation: Hobby plan ($16/yr or ~$19/mo). Untested but worth: Jina Reader (free), Claude PDF input. Comment added to `tools/research_engine.py` line 1.

### Lead Generation Expansion — Tier A Complete
**Plan:** `/Users/stevenadkins/.claude/plans/inherited-munching-sunrise.md` (rebuilt twice via Steven's pressure-test prompt)

- **F3 Curriculum Adoption Queries (20 min):** Added 6 new queries to `scan_rfp_opportunities()`. Nov-Jan committee formation primary (RFI, "curriculum evaluation committee", "seeking computer science curriculum"), Feb-May committee meetings secondary. No new function — extends existing scanner.
- **F1 Second Buyer Expansion (60 min):** New `suggest_intra_district_expansion(max_per_district=5)` in `tools/district_prospector.py`. Logic: load Active Accounts → group by parent district → filter out district-level deals → load Territory Schools → exclude covered schools → exclude already-queued → sort by enrollment desc → cap per district. Fuzzy district matching fallback. New strategy tag `intra_district`, source `expansion_auto`. New `/prospect_expansion [max_per_district]` command. **First production run: 98 districts eligible, 384 schools queued, 56 dedups.**
- **F4 State CS Funding Scanner (75 min):** New `scan_cs_funding_awards()` in `tools/signal_processor.py`. Tier 1 generic queries always run (4 per state), Tier 2 state-specific program hints in `STATE_CS_PROGRAMS` dict (TX, IL, MA, PA, OH). 1-year Serper window (`qdr:y`). Claude Haiku extraction with HIGH/MEDIUM/LOW confidence routing: HIGH → auto-queue via `add_district()` with strategy `cs_funding_recipient`, MEDIUM/LOW → Signals tab only, active customer → `customer_intel` log only. New signal type `cs_funding_award`. New `/signal_funding` command. Kill switch: `ENABLE_FUNDING_SCAN`. **First production run: 9 raw, 1 HIGH auto-queued (Educational Service Center of the Western Reserve, OH).**
- **F2 Competitor Displacement Scanner (90 min + iteration):** New `scan_competitor_displacement()` in `tools/signal_processor.py`. `COMPETITORS` list: Tynker, CodeHS, Replit for Education, Khan Academy CS, Code.org Express, Tinkercad. Source priority: job postings (primary, "experience with X"), RFP replacement language (secondary, "replacing X"), vendor case studies (tertiary, `site:domain.com`). Same HIGH/MEDIUM/LOW routing as F4. New signal type `competitor_usage`, new strategy `competitor_displacement`. New `/signal_competitors` command. Kill switch: `ENABLE_COMPETITOR_SCAN`. **First production run: 1/59 (Claude over-filtering). Loosened extraction prompt (removed aggressive EXCLUDE list, made permissive with confidence-tier filtering). Second run: 8 raw, 4 HIGH auto-queued (Carlinville CUSD#1 IL, Effingham CUSD 40 IL, School District U-46 IL, Azusa USD CA — all Code.org Express or CodeHS).**

### `_calculate_priority()` extended with 3 new strategy branches
- `intra_district`: 750-849 (warmest non-customer leads, sibling-school expansion)
- `cs_funding_recipient`: 800-899 (pre-funded, ready to spend)
- `competitor_displacement`: 650-749 (pre-sold, may be approaching renewal)

### Bug fixes
- **F1 healthy filter killing all 98 districts:** First production run reported 0 queued, 98 skipped as "no healthy account." Root cause: Salesforce CSV exports often have empty Last Activity field, so `_is_recent_activity()` returned False for almost everything. Fix: removed the filter from v1. Even an "old" school relationship is a credible reference point. `_is_recent_activity()` helper kept for future use.
- **`/draft force` UnboundLocalError:** `handle_message()` assigns `gas = get_gas_bridge()` later in the function (line ~1687 for `/call_list`), making Python treat `gas` as local throughout. Any earlier reference raised `UnboundLocalError`. Latent bug — `/draft_emails` block had it from creation but the auto 5-min scanner uses `_check_email_drafts(gas)` which receives gas as a parameter. Steven's `/draft force` was the first Telegram invocation that hit it. Fix: call `get_gas_bridge()` into a `draft_gas` local variable.
- **`_run_daily_signal_scan` `name 'gas' is not defined`:** Same scoping issue but in async task spawned via `asyncio.create_task()` from the scheduler — function doesn't inherit the outer `gas` local. Fix: call `get_gas_bridge()` into `scan_gas` local at function entry.
- **GAS `already_drafted` raised as exception:** `gas_bridge._call()` raised `GASBridgeError` on any `success: false` response, converting the intentional `{already_drafted: true}` GAS response into an exception before `create_draft()` could inspect it. Fix: `_call()` now passes through `{success: false, already_drafted: true}` without raising. `email_drafter` also catches "already has a draft" in exception messages as defense-in-depth fallback.
- **F2 first-run extracted 1/59:** Serper returned 59 articles but Claude Haiku extracted only 1. EXCLUDE list in extraction prompt was too aggressive ("Generic vendor marketing pages without a named district" killed `site:tynker.com` results, "Mentions where district uses competitor as a complement" rejected ambiguous cases). Fix: rewrote prompt to be permissive — extract ALL plausible K-12 district mentions, let confidence tiers convey uncertainty instead of pre-excluding. Reduced EXCLUDE to only universities and out-of-state. Second run: 8 extracted from same query results.

### Architecture decisions / new patterns
- **Per-feature commits:** Each feature shipped as its own commit for surgical rollback. Session 49 has 16+ commits.
- **Kill switches for new scanners:** `ENABLE_FUNDING_SCAN` and `ENABLE_COMPETITOR_SCAN` constants near `SERPER_API_KEY` in `tools/signal_processor.py`. Each scanner checks at function entry and returns empty if disabled.
- **Signal vs Prospect routing:** HIGH confidence → Prospecting Queue as `pending`. MEDIUM/LOW → Signals tab. Active customer match → customer_intel log only (don't sell, don't discard). Established in F4 + F2 scanners as the canonical pattern.
- **All queue writes are `pending`:** No auto-elevation logic — Steven manually approves via `/prospect_approve`. Simpler than confidence-gated dual-path routing.
- **Pressure-test pattern documented:** Steven uses 7-step ruthless pressure-test prompt for plans, often runs it twice. First pass exposes weak foundations. Second pass surfaces highest-leverage rewrites. Memory saved as `feedback_pressure_test_pattern.md`.

### Tier B + C of Lead Gen Expansion deferred
Stubs in plan file:
- F5 CSTA Chapter Partnership (~60 min) — strategy tag + sequence template
- F6 Charter School CMO Seed List (~90 min) — `memory/charter_cmos.json` + prospecting module
- F7 CTE Center Directory (~90 min) — same pattern
- F8 Private School Data via NCES PSS (~120 min) — Urban Institute API
- F9 CS Graduation Compliance Gap PILOT (~120 min) — Claude PDF input approach for CA/IL/MA. Exit criterion: ≥60% validation rate
- F10 Homeschool Co-op Discovery (~45 min) — Serper-only command

### Not built (blocked or covered)
- F11 Usage Decline Early Warning: blocked on CodeCombat product usage data
- F12 Teacher-to-Admin Referral Chain: covered by F1 + existing C5 upward prospecting

### Files modified
- NEW: `tools/email_drafter.py`, `docs/tool_evaluation_2026_04.md`, `memory/superintendent_directory.json` (auto-created on first leadership scan)
- `agent/main.py` — email drafter integration, `/draft_emails`, `/draft force`, `/unanswered`, `/prospect_expansion`, `/signal_funding`, `/signal_competitors`, two scope bug fixes
- `tools/signal_processor.py` — F3 RFP queries, F3c superintendent directory, F4 funding scanner, F2 competitor scanner, kill switches, all bug fixes
- `tools/district_prospector.py` — F1 winback fuzzy, F1 second buyer expansion, `_calculate_priority` 3 new strategies, `_is_recent_activity` helper
- `tools/daily_call_list.py` — F1 fuzzy fallback (Path 1 + Path 2)
- `tools/contact_extractor.py` — content window + known-contacts dedup
- `tools/activity_tracker.py` — `get_unanswered_emails()` + `format_unanswered_for_telegram()`
- `tools/gas_bridge.py` — `create_draft()` signature extension, `_call()` already_drafted passthrough
- `tools/research_engine.py` — eval timestamp comment
- `gas/Code.gs` — `createDraft` thread/cc/HTML, `threadHasDraft` helper, `skip_if_draft_exists`
- `CLAUDE.md`, `SCOUT_PLAN.md` — updated session state and architecture rules


## Session 50 (2026-04-08) — Email Drafter Fixes + Targeted Draft Command

### What changed
- **Issue A (critical):** Second-round email drafts were repeating the first draft instead of addressing the prospect's new reply. Root cause: `searchInboxFull` in `gas/Code.gs` used `messages[0]` (oldest message in thread) instead of `messages[last]`. The drafter re-read the same original message every cycle and never saw Steven's sent reply or the prospect's new message.
- **Issue B:** First-round drafts sometimes didn't fire because `seed_processed_emails` silently marked all currently-unread emails as "seen" on Railway restart, absorbing them. No visibility into when this happened.

### Solution
- **New GAS endpoint `getThreadsBulk(thread_ids, body_limit)`** — batch-fetches structured per-message data for multiple threads in one call. Returns `{thread_id: {message_count, kept_count, messages: [{from, date, body}]}}`. Caps at 30 threads × 30 messages × 3000 chars/message.
- **`tools/email_drafter.py` enrichment pipeline:** `_enrich_with_thread_history(gas, emails)` batch-fetches after `search_inbox_full`, overwrites `email["body"]` and `email["from"]` with the latest message so classification + addressing track correctly, attaches `email["thread_messages"]` with `is_from_steven` flag per message, graceful degradation on GAS failure.
- **`_format_thread_transcript`** builds chronological STEVEN/PROSPECT transcript for Claude's prompt. 20000-char cap, truncates oldest first.
- **`_draft_reply` prompt** updated with explicit rules: "Messages marked STEVEN are replies Steven already sent — do NOT repeat points he already made. Address ONLY what is new in the prospect's last message."
- **`_skip_because_already_replied` defensive guard** for the edge case where the latest message is from Steven himself.
- **Startup restart notice** — `agent/main.py` now sends a Telegram notice when `seed_processed_emails` absorbs any unread emails on restart, with `/draft force` hint.
- **`/draft [name]` targeted command** — bypasses Haiku classification entirely for a specific sender. Searches unread inbox by name substring, forces a draft. Fixes the case where Haiku SKIPs an email Steven wants to reply to.
- **Skip-count UX fix** — `format_draft_summary` now shows "Scanned N — all skipped (already drafted or no reply needed)" instead of the misleading "No new emails to draft" when everything got dedup-blocked.

### Live test results
- **Jesse Layne / Buchanan:** PASS. Draft correctly addressed Jesse's CompTIA CyberSecurity question, acknowledged "high school" and "budget permitting" context, did not re-list product bullets.
- **Kerrie Priest / Colon Schools:** PASS. Correctly classified as SKIP (short "thank you, will check out" acknowledgment with nothing to reply to).
- **Katherine Konwinski (FLAG):** PASS. Draft addressed all 3 of Katherine's specific points (licenses in use, vendor sponsorship, Zoom scheduling) with proper `[STEVEN: ...]` FLAG placeholder.

### Key decisions
- **Batch endpoint over per-thread calls** — `_call` has ~500ms overhead per invocation and the drafter runs ~132 cycles/day minimum during business hours. One batch call per cycle beats one-plus-N calls even at N=2, and it makes error handling atomic (one try/except, not a loop).
- **Structured messages over stringly-typed transcript** — explicit `is_from_steven` beats Claude pattern-matching "On Mon, Steven wrote:". Python filters and formats deterministically.
- **Graceful degradation** (try/except around bulk fetch) — if Python ships before GAS is redeployed, drafter falls back to prior behavior rather than crashing.
- **Persistence of `_processed_message_ids` deferred** — Telegram restart notice is the minimum viable fix. Full persistence would eliminate seeding entirely but adds new failure modes (stale state, write conflicts). Revisit only if notice proves insufficient.

### Commits
- `d6a2923` Fix email drafter: second-round drafts read full thread history
- `10b72e8` Email drafter: notify Telegram when restart seeds unread emails out
- `37acfeb` Add targeted draft command: /draft [name] bypasses classification
- `61794ed` Session 50 wrap-up: update CLAUDE.md with drafter fixes

### Files modified
- NEW: (none — all changes in existing files)
- `gas/Code.gs` — new `getThreadsBulk` function + case in `doPost` switch
- `tools/gas_bridge.py` — `get_threads_bulk(thread_ids, body_limit=3000)` method with empty-list short-circuit
- `tools/email_drafter.py` — `_STEVEN_EMAIL` constant, `_MAX_TRANSCRIPT_CHARS=20000`, `_enrich_with_thread_history`, `_format_thread_transcript`, `_skip_because_already_replied` branch, `_draft_reply` prompt rewrite, `draft_for_sender` function, `format_draft_summary` skip-count handling
- `agent/main.py` — `/draft [name]` targeted handler, startup seeding Telegram notice, `import tools.email_drafter`, skip-count UX path
- `tools/CLAUDE.md` — `get_threads_bulk` documented in GASBridge section, email_drafter section updated with thread-aware drafting notes
- `CLAUDE.md` — Session 50 current state, new commands in shorthand table, email auto-drafter status with thread-aware note
- Plan: `/Users/stevenadkins/.claude/plans/sparkling-cooking-eclipse.md`


## Session 51 (2026-04-09) — Tier A Spot-Check + Full Tier B/C Build + F2 Rewrite

### What changed
Full build session, zero acting. Executed the complete Tier B + C of the Lead Generation Expansion (F5/F6/F7/F8/F9/F10), fixed a hidden bug shared by F4 and F2 that had been suppressing source URLs in signals since Session 49, and completely rewrote the F2 competitor displacement scanner after the Tier A spot-check revealed Session 49's F2 output was 100% false positives.

### Tier A spot-check verdict
- **F4 Western Reserve ESC (OH):** REAL. $584,614 Ohio Teach CS 2.0 grant, verified via news-herald.com URL. BUT characterization as "ESA buys curriculum" was wrong — this is teacher PD funding, not curriculum purchase. Correct play is member districts (Willoughby-Eastlake, Painesville, iSTEM), not the ESC itself.
- **F2 Carlinville CUSD#1, Effingham CUSD 40, School District U-46 (IL):** WEAK. All three linked to `code.org/districts/partners` — Code.org's FREE partner network page, not paid Code.org Express customers.
- **F2 Azusa USD (CA):** VERY WEAK. Source URL was a CodeHS blog post announcing the 2025 CodeHS Scholars program. One Azusa High student, Kaelyn Yang, won a $1,000 scholarship. Not district curriculum adoption.

### F4+F2 source URL preservation bug
Both `scan_cs_funding_awards` and `scan_competitor_displacement` were hardcoding `"url": ""` when writing signals to the Signals tab. Serper URLs were fed INTO Claude's prompt combined_text but never requested back in the JSON extraction schema, so Claude never returned them. Fixed by adding `source_url` field to both schemas with explicit "copy exactly, do not fabricate" instructions, plus http/https validation against hallucinated URLs. Same fix applied to F5 CSTA scanner which had the identical bug.

### F2 competitor displacement scanner — complete rewrite
Old Session 49 F2 used three queries per competitor per state (234 total Serper calls across territory):
- Primary: `"experience with {name}"` job postings
- Secondary: `"replacing {name}"` RFP replacement
- Tertiary: `site:{vendor_domain} "school district"` — this was the main source of false positives (partner listings, scholarship announcements, marketing blog posts)

New Session 51 F2 strategy:
- **Drop tertiary vendor site: queries entirely** — always produced false positives, never real customer evidence.
- **New primary:** `"{name}" site:go.boarddocs.com` — actual district board meeting documents. Highest precision.
- **New secondary:** `"{name}" "board of education" curriculum adoption school district` — general board-portal adoption records.
- **New tertiary:** `"{name}" RFP OR "request for proposal" school district -site:{vendor_domain}` — district RFP/bid documents with vendor self-site exclusion.
- **Collapsed per-state query loop** — 18 total Serper calls (6 competitors × 3 queries) instead of 234. 13× fewer calls. Territory filter moved to post-process via NCES district→state lookup.
- **Strict evidence type gate:** only `board_adoption`, `rfp_bid`, `job_posting`, or `rfp_replacement` qualify for HIGH confidence. Case studies and press releases cap at MEDIUM.
- **URL-pattern downgrade:** `/districts/partners`, `/scholars`, `/blog/announcing-*`, `/newsletter`, `/press/` auto-demote to LOW and re-tag `case_study` → `other`.
- **Prompt rewritten** to explicitly exclude partner pages, student scholarships, conference speaker bios, generic mentions.

Local test after rewrite produced 7 HIGH signals from real BoardDocs URLs: Columbus City SD (OH), Fort Worth ISD (TX), Palo Alto USD (CA), Pocono Mountain SD (PA), Northridge (OH), Chester Upland SD (PA), + more. Plus 4 MEDIUM signals. Night and day versus Session 49.

### F5 CSTA Chapter Partnership
New prospecting strategy `csta_partnership` for CSTA chapter leaders with district affiliation. Entry point is the chapter relationship, not a cold district pitch. `scan_csta_chapters` updated with:
- URL bug fix (same pattern as F4/F2)
- `confidence` + `evidence_type` fields (`chapter_officer`, `board_member`, `conference_speaker`, `active_member`)
- HIGH confidence + named district + chapter_officer/board_member → auto-queue via `district_prospector.add_district(strategy="csta_partnership")`
- Tier 1 signal upgrade for HIGH confidence (was always Tier 2)

Priority tier 620-719. Sequence template written to `memory/csta_partnership_sequence.md` — 4-step peer-to-peer framing, chapter-first entry, district decision-maker intro request in step 3, polite step-back in step 4. Hard rules: never pitch pricing in steps 1-2, never "hop on a call" language, always use the specific chapter name + role from the captured signal.

### F10 Homeschool Co-op Discovery
Lightweight Serper-only `/discover_coops [state]` command. No scheduled scan, no auto-queue. Three queries per state with noise exclusions (facebook.com, hslda.org, reddit.com). Size heuristic (small/medium/large/unknown) from snippet text. Crude city extraction. Returns structured list for Telegram display, Steven manually `/prospect_add`s the ones he wants. New `homeschool_coop` priority tier 500-599.

### F6 Charter School CMO Seed List
Static seed list of 43 Charter Management Organizations across 11 territory states. Total: 918 schools, ~511,100 students. Biggest entries: IDEA PS (TX, 135 schools), National Heritage Academies (MI, 100), ResponsiveEd (TX, 80), Harmony Public Schools (TX, 60), KIPP Texas (57). Coverage by state: TX 8, CA 8, PA 5, TN 4, IL 4, MA 3, OH 3, NV 3, CT 2, OK 2, MI 1.

`memory/charter_cmos.json` with per-entry fields: cmo_name, parent_network, state, school_count, est_enrollment, hq_city, grade_levels, website, notes. New module `tools/charter_prospector.py` with `load_charter_cmos`, `filter_cmos_by_state`, `queue_charter_cmos`, `format_queue_result_for_telegram`, `list_charter_cmos_for_telegram`. New commands `/list_charter_cmos [state]` and `/prospect_charter_cmos [state]`. New `charter_cmo` priority tier 780-899 scaling with school count (more schools = bigger deal).

### F7 CTE Center Directory
Static seed list of 79 Career Technical Education centers across 7 territory states. Total sending-district reach: 1,009 districts. ~139,500 students. Coverage: OK 29 (entire Oklahoma CareerTech system), OH 22 (major career centers), PA 11 (CTCs), IN 6 (Area Career Centers), MA 5 (regional vocational schools), MI 3 (ISD CTE centers), TN 3 (TCATs).

`memory/cte_centers.json` with per-entry fields: name, state, city, est_enrollment, sending_districts, website, it_cs_program flag, notes. All current entries flagged it_cs_program=true (prioritized CS-relevant centers for CodeCombat fit). New module `tools/cte_prospector.py` mirroring charter_prospector pattern. New commands `/list_cte_centers [state]` and `/prospect_cte_centers [state]`. New `cte_center` priority tier 760-879 scaling with sending-district count (broader reach = higher priority). `/prospect_cte_centers` defaults to cs_only=True.

### F8 Private School — pivot from Urban Institute PSS to Serper discovery + network seed
Original Session 49 plan called for Urban Institute PSS sync. Session 51 investigation found:
- Urban Institute Education Data Portal does **not** cover NCES Private School Survey. It exposes CCD, CRDC, EdFacts, and higher-ed sources — not PSS.
- NCES Private School Locator's HTML interface is rate-capped to 15 results per query with no working pagination parameters. Bulk sync is not viable.
- PSS microdata downloads from NCES require offline SAS/Stata processing. Not suitable for a live scanner.

Pivot: match F10 discovery pattern plus a static seed of multi-school networks for high-leverage targeting.

`tools/private_schools.py` with:
- `PRIVATE_SCHOOL_NETWORKS` static seed: 24 networks, ~1,674 total schools. Catholic diocesan systems (Archdiocese of LA 215, Chicago 125, Philadelphia 120, Cincinnati 110, Boston 100, Detroit 80, Galveston-Houston 55), national independent chains (Primrose 450, Stratford 28, Great Hearts TX 8, BASIS Independent 12, Challenger 4), Jewish day school networks.
- `discover_private_schools(state, max_results=25)` — Serper per-state discovery with K-12 filters, noise exclusions (facebook.com, yelp.com, niche.com, greatschools.org, -preschool, -daycare, -homeschool, -college, -university), size/city extraction heuristics.
- `queue_private_school_networks(state)` — queues static seed as `private_school_network` strategy prospects.
- Format functions for both paths.

New commands `/discover_private_schools [state]` and `/prospect_private_networks [state]`. New `private_school_network` priority tier 740-839 scaling with schools count.

### F9 CS Graduation Compliance Gap PDF Pilot
The most complex new feature this session. Uses Claude Sonnet 4.6's `document` content block for PDF input — a newer API capability.

Theory: states with CS graduation laws (CA AB 1251, IL PA 102-0763, MA DLCS framework) create forced-buyer leads. Districts legally obligated to offer CS but not yet compliant are the highest-urgency prospects because the law itself is the sales pitch.

Pipeline:
1. Per-state Serper `filetype:pdf` queries targeting state DOE domains, legislative reports, and accountability documents.
2. httpx PDF download with 10 MB cap, content-type validation, streaming (no in-memory blowup).
3. Base64-encode PDF → Claude Sonnet 4.6 document block + extraction prompt with state-specific context (cites the actual state law).
4. Structured JSON extraction: `[{district, status, evidence_quote, page_hint, confidence}]`. Statuses: non_compliant, compliant, partial, unknown.
5. Auto-queue HIGH-confidence non_compliant + partial districts via `add_district(strategy="compliance_gap")`, deduping across multiple PDFs by normalized district name.

New module `tools/compliance_gap_scanner.py` with `ENABLE_COMPLIANCE_SCAN` kill switch, `PILOT_STATES = {"CA", "IL", "MA"}`, `scan_compliance_gaps(state, max_pdfs=5)`, `format_scan_result_for_telegram`. New command `/scan_compliance [state]` pilot-guarded to CA/IL/MA.

New `compliance_gap` priority tier 850-939 — just below `cs_funding_recipient` (which has money already allocated). The law is the sales pitch.

Cost: ~$0.50-$2.00 per scan depending on PDF page counts. Sanity check on the Serper step confirmed 20+ on-topic PDF hits per pilot state (CA AIR case studies, IL legislative docs, MA DESE DLCS docs).

Exit criterion is **manual**, not enforced in code: verify ≥60% of queued districts are truly non-compliant before scaling beyond pilot states. If the first real run produces garbage, pivot or disable.

### Key decisions
- **F2 query strategy inverted from "vendor says customer" to "district says adoption"** — vendor-site queries (partner pages, case studies, customer lists, scholarship blurbs) were the main source of noise. BoardDocs and RFP documents are where districts self-report adoption decisions — high precision, low hallucination risk.
- **Territory filtering moved from query-time to post-process** for F2 — per-state queries were killing hit rate on specific phrases. Using NCES district→state lookup after extraction keeps the Serper call count low and lets the primary/secondary/tertiary queries cast a wider net.
- **F8 pivot was prompted by reality, not preference** — attempted Urban Institute endpoints (404), then scoped NCES alternatives and confirmed they're all blocked or offline-only. Static seed + Serper discovery is not the "comprehensive sync" Session 49 imagined, but it ships a working feature instead of a dead one.
- **F9 PDF input pipeline has real cost guardrails** — 10 MB download cap, max_pdfs=5 per call, kill switch, manual 60% validation gate before scaling. Claude PDF calls are priced per page; one carelessly large PDF could spike a scan to $5+.
- **Per-feature commits rule honored rigorously** — 9 commits (F2 URL fix, F2 rewrite, F5, F10, F6, F7, F8, F9, wrap-up). Anyone needs to revert any single feature can do it surgically.

### Commits
- `42b6ef7` Fix F4+F2 scanners to preserve source URLs
- `4801431` Tighten F2 competitor scanner: BoardDocs + RFP queries, strict evidence
- `a637487` F5 CSTA Chapter Partnership strategy
- `8220c83` F10 Homeschool Co-op Discovery: lightweight Serper command
- `8ae5d5a` F6 Charter School CMO Seed List + prospector
- `ac2c4e4` F7 CTE Center Directory + prospector
- `c911b33` F8 Private School discovery + network seed list
- `442d7cb` F9 CS Graduation Compliance Gap Scanner (PDF pilot)
- `2edf6df` Session 51 wrap-up: CLAUDE.md, SCOUT_PLAN.md, tools/CLAUDE.md

### Files modified
- NEW: `tools/charter_prospector.py`, `tools/cte_prospector.py`, `tools/private_schools.py`, `tools/compliance_gap_scanner.py`, `memory/charter_cmos.json`, `memory/cte_centers.json`, `memory/csta_partnership_sequence.md`
- `tools/signal_processor.py` — F4/F2/F5 URL preservation fix, F2 query strategy rewrite, F2 evidence type + confidence gating, F2 URL-pattern downgrade, F5 CSTA auto-queue logic, new `discover_homeschool_coops` + `format_homeschool_discovery` functions (F10)
- `tools/district_prospector.py` — 6 new priority tiers: `csta_partnership` (620-719), `homeschool_coop` (500-599), `charter_cmo` (780-899), `cte_center` (760-879), `private_school_network` (740-839), `compliance_gap` (850-939)
- `agent/main.py` — 8 new command handlers: `/list_charter_cmos`, `/prospect_charter_cmos`, `/list_cte_centers`, `/prospect_cte_centers`, `/discover_coops`, `/discover_private_schools`, `/prospect_private_networks`, `/scan_compliance`. New top-level imports for `charter_prospector`, `cte_prospector`, `private_schools`, `compliance_gap_scanner`.
- `CLAUDE.md` — Session 51 current state, 28-of-28 strategy count, next-session checklist restructured with acting items grouped at top, new modules in repo structure
- `SCOUT_PLAN.md` — Session 51 YOU ARE HERE with full deliverables
- `tools/CLAUDE.md` — Module API blocks added for all 4 new modules
- Memories: `feedback_build_only_mode.md`, `feedback_scanner_url_preservation.md`, `feedback_vendor_site_queries_fail.md`, `reference_urban_institute_no_pss.md`
- Plan file: none (session followed Session 49's Tier B/C stubs directly, no fresh plan file was written)


---

## Session 52 — Audit + BLOCKER fixes (Checkpoint A)

### What changed
Session 52 audited everything Session 51 shipped autonomously, surfaced three BLOCKER-level bugs by reading the code directly during planning, and shipped 6 commits across 2 Railway pushes that fixed all three. Stages 4-8 of the plan (scanner rebuild, F8 smoke test, seed queueing, F9 pilot, F1 backlog) deferred to Session 53 when context limits hit Checkpoint A. Code is ready to run — no rework needed.

### Why
Steven opened the session asking for a careful audit of the F2 rewrite + F5/F6/F7/F8/F9/F10 builds from Session 51 because they were all shipped without plan-mode discussion. Three parallel Explore agents reviewed the code and flagged issues. I verified the critical findings by reading source directly during plan mode rather than accepting agent reports on faith, and then ran the plan through Steven's "pressure-test + rewrite from scratch" prompt three iterations to land on v4 before executing.

### Audit findings (verified against live code)
- **BLOCKER A:** `add_district()` at `tools/district_prospector.py:2515` called `_calculate_priority(strategy, 0, 0, 0)` with positional zeros. Every branch added in Session 49 (`intra_district`, `cs_funding_recipient`, `competitor_displacement`) and Session 51 (`csta_partnership`, `charter_cmo`, `cte_center`, `private_school_network`, `compliance_gap`) read size metadata from `kwargs.get(...)` which was always 0. 384 pending F1 intra_district prospects + all Session 49 auto-queued rows were at tier base with no size scaling. Row columns 15-17 were 20-column aligned in the row-write but always written as empty strings — the bug had two layers, scoring AND queue display.
- **BLOCKER B:** F9 `compliance_gap_scanner.py` auto-queued HIGH-confidence extracts with `strategy="compliance_gap"` at priority tier 850-939 — the highest non-upward tier in the system, despite a docstring claim of "just below cs_funding_recipient (800-899)". Inverted numerically AND structurally wrong for a pilot requiring ≥60% validation before scaling.
- **BLOCKER C (latent since Session 44):** `/signal_act` handler at `agent/main.py:2947` hardcoded `strategy="trigger"` for every signal. `"trigger"` isn't a branch in `_calculate_priority`, so it fell through to `cold`. Every bond/leadership/RFP/AI-policy signal Steven has ever promoted has been scoring as cold tier instead of its proper strategy.

### Key decisions
- **F9 fix was NOT a retier — it was a complete behavioral pivot to Signals-only pilot mode.** Retiering would have left an unvalidated extractor auto-writing to the queue, fundamentally violating the ≥60% exit criterion. Signals-only means Steven reviews every extract manually and promotes via `/signal_act N`. Also collapsed a proposed "validation log JSON + /validate_compliance command" sub-plan because Signals tab status transitions (`new → acted` vs `new → expired`) already track validation rate implicitly.
- **BLOCKER C was framed as a sub-fix for F9 but turned out to be a load-bearing latent bug.** Without a `_SIGNAL_TYPE_TO_STRATEGY` mapping, the F9 Signals-only plan didn't work out of the box — promoted compliance signals would have become `strategy="trigger"` → cold tier instead of `compliance_gap`. Added as first-class blocker. Mapping is deliberately minimal (only `compliance → compliance_gap`) so bond/leadership/RFP keep their current "trigger" behavior until their own strategies exist.
- **`reprioritize_pending` migration explicitly skips `intra_district`.** Initially planned to cover all 7 strategies, then realized 384 F1 rows are homogeneous school-level data and sort-within-set doesn't matter for Steven's batch-approval workflow.
- **Migration surfaced a secondary bug:** first pass matched 1 of 20 rows because `csv_importer.fuzzy_match_name` has a gap for 1-token-subset-of-multi-token cases like "carlinville 1" vs "carlinville" (the "strong match" branch requires `len(shorter_tokens) >= 2`). Added an inline token-subset pre-check in `lookup_district_enrollment`. Migration yield jumped to 13/20. Saved as `feedback_fuzzy_match_limits.md` memory.
- **F2 prompt/code mismatch resolved on canonical `rfp_bid`.** The terse enum list in the F2 competitor prompt had `rfp_replacement` (no other references anywhere) and was missing `board_adoption` + `rfp_bid` entirely, while the detailed rules and `_STRONG_EVIDENCE` tuple used `rfp_bid`. Fixed the terse enum list and removed the orphan `rfp_replacement`.
- **Plan went through Steven's pressure-test prompt three iterations.** v1 → v2 (noted priority bug scope was broader than initially thought, `/signal_act` mapping discovery was deferred conditionally). v2 → v3 (discovered v2's Claude response try/except fix was redundant — already existed in code). v3 → v4 (surfaced `/signal_act` hardcoding by actually reading the code, shrank `reprioritize_pending` by skipping intra_district, added `functools.partial` gotcha callout).
- **New critical rule added to CLAUDE.md:** always enter plan mode before building anything non-trivial. Session 51 shipped 7 features without plan mode and 3 of them had BLOCKER-level bugs Session 52 had to fix. Rule is now permanent in the CRITICAL RULES block.

### Tulsa PS side quest (Stage 1)
Prop 3 tech bond ($104.785M) passed with 80.97% approval on April 7. Drafted outreach for Robert F. Burton (Exec Dir IT) via a direct GAS bridge call from Claude Code — Gmail draft created and waiting in Drafts folder for Steven's review. Steven revised the first draft: cut the "$104M" figure (too transactional), added "& safe AI" to the CodeCombat one-liner, changed CTA wording from sales-voice to colleague-voice, removed unverified peer district name-drops. Saved the approved pattern as `feedback_bond_trigger_outreach_tone.md` memory for future bond/funding-trigger outreach.

### Stale signal cleanup (Stage 1)
9 stale signals marked `expired` via `signal_processor.update_signal_status`:
- 7 Session 49 F2 competitor signals: Wylie, Carlinville, Effingham, U-46, Azusa, LAUSD, K-6 public
- Richardson ISD RFP (198 days old)
- Norwalk School District ai_policy (289 days old)
- Acton-Boxborough not in active signals

### Commits
- `f4609fb` fix: add **kwargs forwarding in add_district for priority scaling
- `a996b32` fix: F9 Signals-only pilot + /signal_act strategy mapping
- `aff8f16` fix: /reprioritize_pending one-shot migration for Session 49 + 51 queue rows
- `f60ca7a` fix: token-subset matching in lookup_district_enrollment
- `7a58cc5` fix: kill switches + evidence_type normalization for Session 51 scanners
- `a846137` fix: F9 compliance scanner per-state 24h rate limit

### Files modified
- `tools/district_prospector.py` — `add_district(**kwargs)` signature + forward, populate row columns 15-17, new `reprioritize_pending()` function, new `_col_letter_dp()` helper, compliance_gap docstring update, charter_cmo branch reads from positional school_count
- `tools/territory_data.py` — new `lookup_district_enrollment(name, state) -> int` helper with exact + token-subset + fuzzy matching
- `tools/charter_prospector.py` — passes `school_count` + `est_enrollment` to add_district
- `tools/cte_prospector.py` — passes `sending_districts` + `est_enrollment`
- `tools/private_schools.py` — passes `schools` kwarg, new `ENABLE_PRIVATE_SCHOOL_DISCOVERY` kill switch
- `tools/compliance_gap_scanner.py` — Signals-only rewrite, stable sha1 message_id, `_extract_districts_from_pdf` returns tuple with error_msg, new `_LAST_SCAN` rate limit dict, updated docstring and telegram format
- `tools/signal_processor.py` — F4/F2/F5 scanners pass `est_enrollment` via `territory_data.lookup_district_enrollment`, new `ENABLE_CSTA_SCAN` + `ENABLE_HOMESCHOOL_COOP_DISCOVERY` kill switches + guards, new `_normalize_enum` helper, F2 prompt enum list fixed, `_STRONG_EVIDENCE` tuple cleaned
- `agent/main.py` — new `_SIGNAL_TYPE_TO_STRATEGY` dict, `/signal_act` updated to use mapping + `functools.partial` for kwarg passing through run_in_executor, new `/reprioritize_pending` direct-dispatch handler, `from functools import partial` import
- `tools/CLAUDE.md` — updated `add_district` signature docstring, added `territory_data.lookup_district_enrollment` entry, rewrote `compliance_gap_scanner` block to reflect Signals-only behavior
- `CLAUDE.md` (root) — Session 52 Current State, new "Always enter plan mode before building" critical rule, expanded `_calculate_priority()` strategies list, new sections on `add_district(**kwargs)` / `_SIGNAL_TYPE_TO_STRATEGY` / F9 Signals-only / `_extract_districts_from_pdf` tuple return / `lookup_district_enrollment`
- `SCOUT_PLAN.md` — Session 52 Checkpoint A deliverables + Session 53 carryover
- `SCOUT_HISTORY.md` — this entry
- Memories (auto-memory): `feedback_always_plan_mode.md`, `feedback_bond_trigger_outreach_tone.md`, `feedback_fuzzy_match_limits.md`
- Plan file: `/Users/stevenadkins/.claude/plans/dreamy-floating-avalanche.md` (4 iterations before approval)

---

## Session 53 (2026-04-09) — Fire Drill Audit: 5 Silent-Failure Bugs Discovered

### Premise
Session 53 started as straightforward execution of the Session 52 Checkpoint A carryover: run Stages 4-8 (scanner rebuild, F8 Archdiocese smoke test, queue charter CMOs + CTE centers, F9 compliance CA pilot, F1 backlog drip). Code was supposedly ready — no rework needed.

That premise turned out to be wrong. By the end of Stage 4 we'd discovered that the scanner output had been silently corrupted for weeks, probably since Session 49. Session 53 became a fire drill audit.

### Discovery pattern
Every bug was invisible from the Telegram surface and visible in 30 seconds via direct sheet read (service account + Python). The audit pattern that worked: run a scanner, then use `_load_all_prospects()` or `service.spreadsheets().values().get(...)` to read the actual row state, then compare to what the scanner said it wrote.

### Bug 1 — F4 funding scanner queries wrong corpus (pre-existing since Session 49)
- **Symptom:** `/signal_funding` returns "0 results (raw extracted: 0)" every run.
- **Railway logs:** Serper pulls 456 articles across 13 states, Claude extracts 0 items in ~1.3s.
- **Local diagnostic (IL only):** 39 articles, 12,486 chars (fits under 14K truncation cap). Top 15 Serper results are higher-ed grants, community colleges, teacher awards, student scholarships, state program descriptions, IL statutes — ZERO K-12 LEA recipient announcements. Claude correctly extracts 1 LOW-confidence garbage ("Dot Foods STEM Grant Recipients — 23 west central Illinois schools") which is a grant program not a district. Claude isn't broken — the upstream corpus is wrong.
- **Root cause:** Queries like `"CS grant awarded school district Illinois"` don't distinguish K-12 LEAs from higher ed / student level / program level. Claude's EXCLUDE rules fire correctly but the signal content isn't there to find.
- **Fix required:** Query redesign with site filters targeting `*.k12.*.us`, state DOE subdomains (isbe.net, tea.texas.gov, cde.ca.gov etc.), known state program names. Plus chunked per-state Claude calls to eliminate the 14K truncation at 13-state scale. Plus prompt change to drop the redundant "Awards >12 months old" exclude (qdr:y already constrains to 1 year).
- **Memory:** `project_f4_funding_scanner_broken.md`
- **Status:** PARKED. ENABLE_FUNDING_SCAN flipped to False tonight (commit `3431323`) until Session 54 fix sprint.

### Bug 2 — F5 CSTA scanner low yield (1.8%) + strategic question
- **Symptom:** `/signal_csta` returned 3 leads from 167 articles across 12 states. 1 real auto-queue (Pittsburgh Public Schools via Teresa Nicholas, CSTA K-12 Board member, PA territory). 2 garbage records where Claude wrote "CSTA PA chapter" / "CSTA TN chapter" into the `district` field.
- **Railway logs:** `CSTA scan: 167 articles from 12 states` → `3 leaders/members extracted, 1 auto-queued as csta_partnership`.
- **Root causes stacked:**
  1. Queries target generic chapter homepages + conference promos, not the `csteachers.org` chapter leadership rosters or LinkedIn officer directories where real CSTA leaders live.
  2. `combined_text[:12000]` input truncation throws away ~76% of articles (167 → ~40 reach Claude).
  3. Prompt allows Claude to write chapter name ("CSTA PA chapter") into the `district` field when no real LEA is mentioned. Auto-queue gate at line 4760 only checks truthiness not LEA validity.
  4. `max_tokens=2000` is even smaller than F2's old 3000 — would bite if more content reached Claude.
  5. `split("```")[1]` IndexError lurking (same pattern F2 had).
  6. Return type is `list` not `dict`, so Telegram handler can't surface "auto-queued N" count.
- **STRATEGIC QUESTION:** Is F5 worth keeping as a standalone scanner? CSTA chapter leaders are CS advocates but they're not a strong proxy for "district about to change curriculum vendors." A redesigned F5 might be more valuable as a contact-enrichment layer ON TOP of F2 hits ("this district uses CodeHS AND has a CSTA chapter leader") rather than a standalone scanner. That's a product decision needed before any code fix.
- **Win to preserve:** Pittsburgh Public Schools row (PA, `csta_partnership`, priority 621, via Teresa Nicholas). Real warm intro, in queue in canonical layout.
- **Memory:** `project_f5_csta_scanner_low_yield.md`
- **Status:** PARKED. ENABLE_CSTA_SCAN flipped to False tonight (commit `3431323`). Fix requires strategic decision first.

### Bug 3 — F2 writes rows in scrambled column layout (HIGHEST PRIORITY MYSTERY)
- **Symptom:** After the F2 max_tokens fix shipped (commit `7c345a07`), rerunning `/signal_competitors` produced "17 raw, 12 signals, 8 auto-queued" in Telegram. Real signal visible. But `/prospect_all` showed only 2 pending rows total: Pittsburgh PS + Archdiocese, no F2 rows.
- **Direct sheet read (service account):** The F2 rows ARE in the queue. Lackland ISD is at row 1947. But the column layout is WRONG:
  ```
  col  1: TX                                   ← state (correct)
  col  2: Lackland ISD                          ← name (correct)
  col  3: competitor_displacement               ← strategy (should be col 9)
  col  4: 654                                   ← priority (should be col 12)
  col  5: signal                                ← source (should be col 10)
  col  6: 1035                                  ← enrollment (should be col 16)
  col  7: Competitor: Tynker...                 ← notes (should be col 20)
  col 8-12: EMPTY                               ← Status (col 11) is empty, which is why /prospect_all doesn't see it
  col 13: lackland                              ← name_key (should be col 8)
  col 14: pending                               ← status (should be col 11)
  col 15: 2026-04-10 00:51                      ← date_added (should be col 13)
  col 16-19: EMPTY
  col 20: competitor_lackland_tynker_2026_04    ← signal_id (should be col 19)
  ```
- **The same `add_district` call from F5 and F8 produced CANONICAL layout** for Pittsburgh PS and Archdiocese in the SAME session window. Tested by writing a sentinel row (`ZZZ_TEST_DELETE_ME_session53_diag`) via `dp.add_district(...)` from local Python — landed in canonical positions (state col 1, name col 2, name_key col 8, strategy col 9, source col 10, pending col 11, priority col 12, date col 13, enrollment col 16, signal_id col 19, notes col 20). Sentinel cleaned up after verification.
- **Git archaeology:** Searched every historical version of `district_prospector.py`. NO version of `add_district` has EVER written rows with strategy at col 3. The Session 14 original schema had strategy at col 4 and a 14-column layout. The pre-Session-52 layout had strategy at col 9 (same as current). The Lackland row layout doesn't match any version.
- **PRE-EXISTING CORRUPTION DISCOVERED:** Queue has 1954 total rows. Status distribution:
  - `status="school"`: 1463 rows
  - `status="district"`: 449 rows
  - `status=""` (empty): 40 rows
  - `status="pending"`: 2 rows (Pittsburgh PS + Archdiocese from tonight)
  The 1463 school + 449 district rows have the SAME scrambled layout as the Lackland rows — sample: Kennedy Junior High School (IL, written 2026-03-20) has strategy at col 3, status="school" at col 11 (which is actually an account type, misplaced), name_key at col 13, date at col 15. **This corruption has been happening for WEEKS, not just tonight.** Some secondary writer or race condition has been bypassing the canonical `add_district` writer for a long time.
- **Hypothesis (unconfirmed):** Railway rolling deploy overlap. The F2 max_tokens deploy (7c345a07) BUILD started 00:47:49 UTC, SUCCESS at 00:48:38 UTC. Lackland written at 00:51 UTC. Pittsburgh PS at 01:14 UTC. Archdiocese at 01:32 UTC. If Railway was still serving traffic from the old container for some period after SUCCESS, and the old container had some shadow `_write_rows` path that the new container doesn't, F2 hit the old path while F5/F8 hit the new one. But I couldn't find any code in git that would produce the Lackland layout. Hypothesis needs audit via adding log lines + redeploying.
- **Affected data:** Tonight's 8 F2 rows contain real valuable data (Lackland ISD TX, Mansfield ISD TX, Naperville Community Unit SD 203 IL, North Royalton OH, West Ottawa MI, San Juan Unified CA, San Francisco Unified CA, New Hartford) but are unreachable via `/prospect_all` because Status column is empty. Plus 1912 historical rows with scrambled layout.
- **Naperville 203 source URL ground-truthed** against my earlier local diagnostic: `https://go.boarddocs.com/il/naperville203/Board.nsf/files/DMWQGL690166/$file/2026%20Proposal.pdf` — real BoardDocs PDF, real CodeHS adoption. F2's extraction logic is genuinely good. Only the writer is broken.
- **Memory:** `project_f2_column_layout_corruption.md`
- **Status:** PARKED. F2 stays enabled (logic is proven good) — only manual runs until Session 54 repairs the writer. Session 54 PRIORITY 1.

### Bug 4 — F8 research playbook mismatch for diocesan networks
- **Symptom:** Stage 5 F8 smoke test on Archdiocese of Chicago (IL, 125 schools, priority 839). Research pipeline ran for 4m 56s using 40 Serper queries. Result: "35 total — 3 with email, 32 name-only. 3 verified emails."
- **Layer breakdown (from Research Log):** L16:exa-broad=30, L15:email-verify=4, L13:state-doe=1. **L1:direct-title, L2:title-variations, L3:linkedin, L4:district-site, L5:news-grants, L6:scrape, L7:deep-crawl, L8:email-inference, L11:school-staff, L12:board-agendas, L14:conference, L17:exa-domain all returned 0.**
- **Direct sheet read of Leads from Research tab:** The 3 "verified" contacts were:
  1. **Allen** (Instructional Technology, `tallen@archchicago.org`) — real Archdiocese hit, sourced from a 2017 PDF about early childhood leadership. 9-year-old source, employment unverified.
  2. **Michelle Erickson** (HS Business/CS, `merickson@rowva.k12.il.us`) — works at ROWVA CUSD 208, NOT Archdiocese. Cross-contamination (see Bug 5).
  3. **Frank LaMantia** (Curriculum Director CTE, `frank.lamantia@chsd218.org`) — works at Community HSD 218, NOT Archdiocese. Cross-contamination.
- **Gate assessment:**
  - Gate 1 (≥3 emails for the network): ❌ FAIL — only 1 real, 2 cross-contaminated
  - Gate 2 (network website ID'd): ❌ FAIL — `archchicago.org` never discovered via L4, only incidentally found via contact email
  - Gate 3 (≥1 named director): 🟡 PARTIAL — Allen in "Instructional Technology" is role-adjacent but not a director/C-suite title, source 9 years old
- **Root cause:** The 20-layer research engine is tuned for single-website K-12 public districts. L4 district-site discovery pattern-matches `*.k12.*.us` and common district URL structures — can't find diocesan custom domains (`archchicago.org`, `archdiocese-of-X.org`, `catholicschools.org`). When L4 returns no domain, downstream L6-L8 have no site to scrape and return 0. Engine falls through to L16 Exa broad search which pulls Chicago-area content indiscriminately.
- **Fix required:** Dedicated diocesan central-office research playbook. Known diocesan domain patterns to try before L4 (`archchicago.org`, `archdiocese-of-X.org`, `catholicschools.org`, `diocesanX.org`). Priority titles (Superintendent of Schools, Director of Schools, Chief Academic Officer, Director of Religious Education, Director of Educational Technology). Central directory paths (`/schools/leadership`, `/offices/catholic-schools`, `/education-office`). Lower success threshold to 3-5 high-confidence central office contacts.
- **Decision:** Do NOT unblock the other 23 networks in the F8 seed until the diocesan playbook is built.
- **Sequence builder side note:** Cold Prospecting Google Doc was auto-built for Archdiocese post-research. But the sequence builder wrote it as "Cold Prospecting" even though the strategy is `private_school_network` — sequence builder has no branch for that strategy and falls back to cold. Minor follow-up.
- **Memory:** `project_f8_diocesan_research_playbook.md`
- **Status:** PARKED. F8 seed-loader stays enabled (no auto-scan, manual only). Archdiocese row stays in queue as "complete/draft" for manual review. Session 54 PRIORITY 3.

### Bug 5 — Research pipeline cross-contaminates leads across districts
- **Discovered as a side effect of Bug 4.** Two of the three Archdiocese "verified" leads were not Archdiocese people at all — they work at ROWVA CUSD 208 and Community HSD 218, both unrelated public K-12 districts in Illinois. Their rows in the "Leads from Research" tab have `District Name = "Archdiocese of Chicago Schools"` (set from the research job target) but `Account = "ROWVA CUSD 208"` / `"Community High School District 218"` (set from the source page header or Claude's extraction).
- **Example row:**
  ```
  First Name: Michelle
  Last Name: Erickson
  Email: merickson@rowva.k12.il.us    ← domain proves ROWVA
  Account: ROWVA CUSD 208               ← employer
  District Name: Archdiocese of Chicago Schools   ← wrong attribution
  Source URL: https://www.rowva.k12.il.us/staff?page_no=2
  Email Confidence: VERIFIED
  ```
- **Hypothesis:** The research engine's L16 Exa broad search + L17 Exa domain-scoped search query the web with terms related to the target district. Exa returns pages mentioning those terms even if the page is ABOUT a different district. L9 Claude-extract processes the page and extracts real contacts from it — but doesn't verify that the contact's employer matches the research target. L10 dedup-score writes the contact with `District Name = <research target>` and `Account = <scraped from source page>`, creating the mismatch.
- **Scope:** Unknown but concerning. If the same contamination rate applies to the other 19 completed research jobs in the Research Log tab, we could be looking at 40+ misattributed contacts across the Leads from Research tab. NEEDS AUDIT.
- **Why this matters:** If Steven manually reviews Archdiocese research output and picks the top 3 "verified" emails, he'd send CodeCombat pitches to a ROWVA teacher and a CHSD 218 CTE director as if they were Archdiocesan contacts. Embarrassing + potentially hits real customer context for ROWVA/CHSD if they're ever in the pipeline.
- **Fix required:**
  1. Audit script: iterate all rows in "Leads from Research", flag rows where `Email` domain doesn't match the canonical site of `District Name`, report scope.
  2. Post-extraction validation layer in `research_engine.py` between L9 Claude-extract and L10 dedup-score: check each extracted contact's email domain and/or source URL host against the research target's canonical domain. If mismatch → drop the contact OR rewrite both `Account` and `District Name` to the actual employer (so the contact survives as a ROWVA lead instead of disappearing).
- **Until fixed:** When manually reviewing ANY research output, always cross-check Email column against Account column. If they don't match, treat the lead as belonging to Account, not District Name. Unscalable but protective.
- **Memory:** `project_research_cross_contamination.md`
- **Status:** PARKED. Session 54 PRIORITY 2 (after Bug 3, before Bug 4).

### Commits (Session 53)
- `7c345a07` fix: F2 max_tokens cap was truncating Claude response + harden codefence parser (THE one real fix tonight)
- `89fa279` docs: Session 53 Fire Drill Audit wrap — CLAUDE.md + SCOUT_PLAN.md + SCOUT_REFERENCE.md
- `3431323` fix: disable F4 + F5 kill switches until Session 54 fix sprint
- (this SCOUT_HISTORY entry is the 4th commit of the session)

### Files modified (Session 53)
- `tools/signal_processor.py` — F2 max_tokens 3000→8000, hardened `split("```")[1]` parser with `len(parts) >= 2` guard; ENABLE_FUNDING_SCAN flipped to False, ENABLE_CSTA_SCAN flipped to False with memory references
- `CLAUDE.md` (root) — trimmed 45.4k → 33.3k → 36.9k chars. Moved REPO STRUCTURE + RAILWAY ENV VARS + CLAUDE TOOLS + SHORTHAND COMMANDS to new `docs/SCOUT_REFERENCE.md`. Rewrote CURRENT STATE with Session 53 discoveries, 5 bugs, Session 54 fix sprint priority order. Added Session 53 lessons section (Railway temporal inconsistency, spot-check via direct sheet read, silent failure habituation, kill switch hygiene).
- `SCOUT_PLAN.md` — new YOU ARE HERE header, Session 53 deliverables section
- `SCOUT_HISTORY.md` — this entry
- `.gitignore` — replaced `scripts/__pycache__/` with generic `**/__pycache__/` to stop polluting git status
- `docs/SCOUT_REFERENCE.md` — NEW FILE, contains the static reference material trimmed from CLAUDE.md

### Side outputs (manual work during the session)
- **Tulsa PS Prop 3 Gmail draft for Robert F. Burton:** Reworked body in claude.ai, sent back to me. First draft via shell-quoted `python3 -c "..."` left literal `"""` in apostrophes ("Here's" → `Here"""s`). Second draft via standalone Python file was clean. Manually deleted the broken draft from Gmail. **Scheduled to send Tuesday 8:05 AM.** Subject: "Before the Prop 3 RFPs land on your desk".
- **Railway deployment status checks** via GraphQL API using `RAILWAY_TOKEN` from `.env` (project peaceful-delight b91479be, environment production 785d5426, service web 9534f961). Pulled deployment logs by deployment ID + filter string to diagnose each failed scanner run.
- **5 project memories created + 5 entries added to MEMORY.md index** in `~/.claude/projects/-Users-stevenadkins-Code-Scout/memory/`:
  - `project_f4_funding_scanner_broken.md`
  - `project_f5_csta_scanner_low_yield.md`
  - `project_f2_column_layout_corruption.md`
  - `project_f8_diocesan_research_playbook.md`
  - `project_research_cross_contamination.md`

### Key decisions
1. **Park F4 as pre-existing bug, not a regression.** Session 52 explicitly tracked F4 in scope but never actually ran it. Sessions 49-51 never spot-checked it. The silent zero-result output looks identical to a quiet news week. Not a Session 52 regression — a Session 49 latent bug that's been firing weekly.
2. **Quick-fix F2 via one-line max_tokens bump because local diagnostic proved the logic was sound.** Not a plan-mode violation because CLAUDE.md has an explicit exception for "one-line config tweaks". Same justification applied to tonight's kill switch flip.
3. **Do NOT quick-fix F5 despite same `max_tokens` pattern.** F5 has 6 distinct issues plus a strategic question (standalone scanner vs F2 enrichment layer). A quick fix would lock in the standalone shape before validating it's the right shape. Park instead.
4. **Do NOT attempt to repair the F2 column layout tonight.** The writer mystery isn't understood. A repair script written without knowing the writer could mangle the canonical rows alongside fixing the broken ones. Session 54 plan-mode first.
5. **Stop at Stage 5 failure rather than continue to Stages 6-8.** Stage 6 (charter CMOs + CTE centers) risked adding 122 more rows through the same potentially-broken writer path. The 50/50 odds that Stage 6 produces canonical vs scrambled rows didn't justify the audit cost.
6. **Option A at end of session: stop and wrap with brutal honesty, not Option B/C.** The responsible next session is a Fix Sprint, not more scanning. Finding more broken stuff by running more scanners just produces a longer memory list.

### What was NOT done (carried over to Session 54)
- Stage 6 (charter CMOs + CTE centers queue + approve first batch)
- Stage 7 (F9 compliance CA pilot + validation gate)
- Stage 8 (F1 backlog drip, 30 approvals from 384 pending)
- Approval of Pittsburgh Public Schools row (canonical, waiting for manual review)
- Approval of Archdiocese of Chicago row (canonical, research complete, Cold Prospecting Google Doc built, waiting for manual review)

---

## Session 54 (2026-04-10) — BUG 3 Fix Sprint: Queue Repair + Writer Fixes

**Theme:** Dedicated fix sprint for the 5 bugs discovered in Session 53's Fire Drill Audit. Full BUG 3 (queue column corruption) resolution end-to-end, 4 bugs remaining for Session 55.

**Plan file:** `/Users/stevenadkins/.claude/plans/sunny-riding-aurora.md`

### Commits pushed (7 total)

1. **`7a9540f`** — Phase 0: kill switches flipped. `ENABLE_COMPETITOR_SCAN=False`, `ENABLE_PRIVATE_SCHOOL_DISCOVERY=False`. Stop-the-bleed before investigation (next scheduled F2 was 8 hours away and would have written more scrambled rows otherwise).
2. **`68622aa`** — Phase 1f diagnostic: temporary `_write_rows` logging. Captures full row payload, strategy position, caller stack trace (8 frames), and the Sheets API `updatedRange` response on every call. TO BE REVERTED after BUG 3 is confirmed fully killed.
3. **`5990d8a`** — Phase 2-3: 9 diagnostic scripts + repair script. `scripts/repair_scrambled_queue_rows.py` is the important one — strategy-dispatch readers per scramble template, dry-run default, `--apply` opt-in, snapshot-before-write via `duplicateSheet` API.
4. **`a54bc8c`** — Phase 4 district_prospector.py: fix 4 writers (`discover_districts:1161`, `suggest_upward_targets:1263`, `suggest_closed_lost_targets:1716`, `suggest_cold_license_requests:2363`) to write 20-element rows instead of 19 (add missing `""` Signal ID slot). Also fix `_update_status` range A:S→A:T (latent Notes-column truncation) + fallback index correction (name_key: 1→7, status: 5→10). Also extend `_KNOWN_STRATEGIES` in `migrate_prospect_columns` and the module-level constant to include all Session 49+ strategies.
5. **`5ebfaea`** — Phase 4 proximity_engine.py: fix `add_proximity_prospects:415-435` to write 20 elements (same bug class as the district_prospector fixes).
6. **`8b59ceb`** — Phase 6: `ENABLE_COMPETITOR_SCAN=True`. F2 re-enabled. F4/F5/F8-discovery still disabled per their own memos.
7. (Not a commit — the queue repair was applied directly via `python3 scripts/repair_scrambled_queue_rows.py --apply` before the Phase 4 writer commits. 1952 rows rewritten, backup tab created.)

### Key decisions

- **Pivoted from root-cause hunt to repair-then-capture.** After ~2 hours of investigation with local sentinels reproducing canonical rows on every path (local Python, `railway run`, `railway ssh` inside container, `loop.run_in_executor`), decided the ghost writer was eating time better spent on the repair. Deployed diagnostic logging to catch it on the next production F2 run, then moved on to Phase 3 repair.
- **Strategy-dispatch readers over content-based heuristic recovery.** The 1952 scrambled rows had at least 8 distinct fingerprint tuples depending on which optional fields were populated. Rather than content-classify each cell, I wrote one reader per strategy template (cold_license_request, intra_district, winback, proximity, signal-strategies, plus a fallback for trigger/charter_cmo/etc.) that reads field values from the known scramble positions. Each reader was validated on sample rows before the full apply.
- **Snapshot-then-clear-then-update** pattern for the repair, reusing the same atomic-ish approach `migrate_prospect_columns` already uses. Backup via `duplicateSheet` batchUpdate call — same sheet file, new tab, zero API-level risk of losing rows mid-flight.
- **Verified 7 exit criteria before declaring done.** All pass. Only exit criterion 3 (manual F2 sentinel test) deferred to the next scheduled F2 run since we can't trigger it on-demand without Steven's Telegram hands.

### Investigation findings (captured in `memory/project_f2_column_layout_corruption.md`)

- **Ground truth:** row 1947 Lackland ISD (+ 7 other F2 rows from 00:51 UTC) confirmed scrambled. Memory description was 100% accurate. Strategy@idx2, Priority@idx3, Source@idx4, Enrollment@idx5, Notes@idx6, Name Key@idx12, Status@idx13, Date@idx14, Signal ID@idx19.
- **Scope:** 1952 of 1954 data rows were scrambled. Only Pittsburgh PS (F5 01:14 UTC) and Archdiocese of Chicago (F8 01:32 UTC) were canonical before the repair.
- **Strategy distribution of scrambled rows:** cold_license_request 1274, intra_district 384, winback 249, competitor_displacement 23, trigger 12, proximity 5, cs_funding_recipient 5.
- **Partial root cause identified:** 4 `district_prospector` writers + 1 `proximity_engine` writer built 19-element rows instead of 20, missing the Signal ID slot added by commit `33e34f6` on 2026-04-06. These 5 functions explain the bulk of the historical damage (most of the cold_license_request, intra_district, winback, proximity rows).
- **UNEXPLAINED:** the 8 F2 rows from 2026-04-10 00:51 UTC. F2 calls `add_district` which builds a correct 20-element row in the current code. Four sentinel tests on the same checkout produced canonical rows. Only the long-running Scout bot process on Railway produced scrambled F2 rows. Working hypotheses: module re-import/monkey-patching at runtime, thread-local state in the Python Sheets client, something specific to Scout's asyncio event loop after it's been running a while. Diagnostic logging will capture evidence.

### 4 bugs still remaining from Session 53 Fire Drill Audit

BUG 1 (F4 funding queries), BUG 2 (F5 strategic question), BUG 4 (F8 diocesan playbook), BUG 5 (research cross-contamination). See `memory/project_*.md` files. Priority order in CLAUDE.md CURRENT STATE. Next session starts with BUG 5 (Priority 2).

### Leftover state after Session 54

- **Queue is clean** — all 1958 rows canonical.
- **Backup tab present**: `Prospecting Queue BACKUP 2026-04-10 0010`. Safe to delete once comfortable.
- **4 sentinel rows** at queue rows 1956-1959 (`ZZZ_SENTINEL_*` + `ZZZ_PHASE1*` names). Canonical, harmless clutter. Delete via `/cleanup_queue` or manually.
- **Diagnostic logging in `_write_rows`** (commit `68622aa`) still active. Should be reverted after the next F2 run confirms whether the ghost writer was the 19-element bug or something else.
- **F2 re-enabled, scheduled for 7:45 AM CDT daily.** First run after Session 54 will be the Phase 6 sentinel test.
- **Scout still running Phase 1f diagnostic build** on Railway deployment `90072b8a-...`. Subsequent push during session created additional deployments that are now live.
- **Ghost writer investigation** is NOT complete but parked. Will resume once diagnostic logs capture the next production write.

### Archived from CLAUDE.md CURRENT STATE

The full 5-bug discovery narrative from Session 53 was trimmed from CLAUDE.md CURRENT STATE in this session because 4 of the 5 bugs already have their own detailed `memory/project_*.md` files and BUG 3 is resolved. The 5-bug narrative remains in the Session 53 entry above in this file.

---

## Session 55 (2026-04-10/11) — BUG 3 Close-Out + BUG 5 Two-Stage Filter + Telethon Bridge

**Session theme:** Priority 0 close out BUG 3 Phase 6 sentinel test from Session 54. Priority 1 plan + ship BUG 5 (research cross-contamination). Bonus: built out Claude Code's operator capabilities — Telethon Telegram bridge and screenshot capture — so future sessions can run end-to-end smoke tests without Steven manually relaying messages.

### Priority 0 — BUG 3 Phase 6 sentinel close-out

**The Session 54 assumption was wrong.** Session 54 notes said "Scheduled F2 run at 7:45 AM CDT daily — first run after Phase 6 commits will be the evidence capture." But F2 (`scan_competitor_displacement`) is NOT in the scheduled daily scan. The 7:45 AM `signal_scan` event in `agent/scheduler.py` runs Google Alerts + Burbio + DOE + RSS feeds + BoardDocs + Ballotpedia. F2 is only triggered manually via `/signal_competitors`.

I pulled Railway logs for the 12:45 UTC scheduled window — 887 lines of RSS/BoardDocs activity, zero F2, zero BUG3_DIAG. Confirmed via code read (`agent/scheduler.py:49-51` signal_scan event fires, `agent/main.py:3271-3277` F2 is only bound to `/signal_competitors`).

**Built the Telethon bridge to fire the sentinel test from Claude Code.** Steven granted Screen Recording permission to Ghostty (verified with `screencapture -x`). Created Telegram app at my.telegram.org (API_ID `37370458`, API_HASH in `.env`). Installed Telethon in `.venv`. Wrote three scripts:
- `scripts/telethon_auth.py` — one-time phone+SMS auth, session saved to `.telethon_session` (gitignored via `.telethon_session*`)
- `scripts/tg_send.py <target> <message>` — send as Steven
- `scripts/tg_recent.py <target> [N]` — read last N messages

Auth flow: Telegram sends login code inside Telegram app (not SMS). Steven pasted `42444`. Authorized as "Steven Adkins (14058355067)".

**Sentinel test via Telethon.** First attempt `/prospect_add ZZZ_SESSION55_SENTINEL_DELETEME TX` hit the bot's usage help — command requires comma syntax. Re-sent `/prospect_add ZZZ_SESSION55_SENTINEL_DELETEME, TX`. Railway logs 30s later captured the full diagnostic output:
```
[BUG3_DIAG] _write_rows row len=20 
  first3=['TX', 'ZZZ_SESSION55_SENTINEL_DELETEME', '']
  pos_of_strategy=[8]
caller stack: add_district @ line 2588 → _write_rows @ line 453
API response: updatedRange='Prospecting Queue'!A1960:T1960 
  updatedRows=1 updatedColumns=20 updatedCells=20
```

**BUG 3 confirmed dead.** Canonical 20-col write, strategy at index 8 (col 9), landed at `A1960:T1960`, via the normal `add_district → _write_rows` path inside the long-running Railway bot process. Session 54's writer-fix commits were sufficient.

**Cleanup.** Reverted commit `68622aa` (diagnostic `_write_rows` logging) via `9b51a67` → pushed `0061aed`. Wrote `scripts/delete_zzz_sentinels.py` (content-based safety — only deletes rows starting with `ZZZ_`, deletes in reverse index order). Removed 5 sentinel rows (1956-1960 including the new Session 55 one). Final fingerprint audit: **1954/1954 canonical** in Prospecting Queue.

**Committed operator tooling as `746e1e7`**: Telethon auth/send/recent + delete_zzz_sentinels scripts + `.gitignore` entry for `.telethon_session*`.

### Priority 1 — BUG 5 two-stage cross-district contamination filter

**Plan mode with three passes.** Wrote v1 (L9.5 post-extraction validation). Self-pressure-tested → v2 (trimmed fat, fixed decision table, added oracle gate). Steven ran the full 7-step ruthless pressure-test prompt → v3 with the biggest architectural shift: **filter at `raw_pages` boundary BEFORE Claude extraction, not after.** v2 validated after Claude had already tokenized contaminated pages; v3 drops them at the earliest boundary where `self.district_domain` is available.

**The matching rule** (4 helpers, single source of truth, same code in Stage 1 / Stage 2 / strengthened L10 / audit script):
- `_district_name_hint(name)` — lowercase, strip " isd"/" unified school district"/... suffixes, strip "archdiocese of "/"diocese of " prefixes, ≥5 char guard
- `_is_school_host(host)` — affirmative substring test against `_SCHOOL_HOST_PATTERNS` = `(".k12.", ".edu", "isd", "usd", "schools", ".ps.", "cusd", "cps", "chsd", "ccsd", "ccusd", "cisd", "dusd", "dvusd", "mcsd", "ecsd", "ocsd", "archdiocese", "diocese", "academy", "charter")`
- `_host_matches_target(host, target_host, target_hint)` — substring match on target_host OR hint
- `_email_domain_matches_target(email, target_host, target_hint)` — same logic applied to email domain

**Phase 0 oracle.** `scripts/bug5_phase0_scan.py` built `bug5_oracle_archdiocese.json` (3 Archdiocese rows from the live sheet, 2 marked `expected:drop` — ROWVA + CHSD218) + `bug5_oracle_clean_sample.json` (20 rows diversified across 9 districts where both source host and email domain match the district hint). Both gitignored (PII).

**Phase 1 dry-run hard gate.** `scripts/bug5_dryrun.py` validates the decision rule against both oracles. 23/23 rows classify correctly. First run failed on `chsd218.org` (wasn't in school patterns) and `nces.ed.gov` (audit test expected True, but it's federal not school). Fixed by adding `chsd/ccsd/ccusd/cisd/dusd/dvusd/mcsd/ecsd/ocsd` to `_SCHOOL_HOST_PATTERNS`. Second run: all 23 pass.

**Phase 2 — 6 commits landed:**
- **Commit A `6ffa1b2`** `feat(bug5): Session 55 Commit A — cross-contam filter kill switch + matching helpers`. Added `ENABLE_RESEARCH_CONTAM_FILTER`, `_SCHOOL_HOST_PATTERNS`, 4 helper methods on ResearchJob, 3 counters (`_contam_pages_filtered`, `_contam_contacts_filtered`, `_contam_l10_cleared`). No behavior change.
- **Commit B `552240f`** `Stage 1 page filter at raw_pages boundary`. `_filter_raw_pages_by_domain()` called as first step of `_layer9_claude_extraction`. Walks `self.raw_pages`, drops pages whose host is a school-like mismatch, removes dropped URLs from `self._url_to_layer` for bookkeeping cleanliness. Accumulates into `self._contam_pages_filtered`. Logs `L9 page filter: N/M pages dropped as cross-district (target=...)`. Fail-open when `self.district_domain` empty.
- **Commit C `148aca6`** `Stage 2 contact filter + L10 source strengthening`. `_filter_contacts_by_domain()` called after `_merge_contacts`. Per-contact decision table handles both-match / source-match-email-cleared / source-match / email-match / wrong-school-host-drop / generic-host-wrong-email-drop / keep-at-UNKNOWN. L10 strengthened with source_url hostname branch using the new helpers. `ResearchJob.run()` return dict gains `pages_filtered`, `contacts_filtered`, `l10_cleared`, `cross_contam_dropped`.
- **Commit D `4bdfcfc`** `Research Log cross_contam_dropped column`. `log_research_job` signature extended with `cross_contam_dropped: int = 0`. `LOG_COLUMNS` appended with `"Cross-Contam Dropped"`. Range updated `A:H` → `A:I`.
- **Commit E `22dc28b`** `wire cross_contam_dropped through research callback`. One-line change in `agent/main.py._on_research_complete`.
- **Fix commit `da46dfa`** `L15 additions go through Stage 2 + schema migration fix`. Three bugs caught during Phase 3 smoke test:
  1. L15's two `_merge_contacts` sites never called `_filter_contacts_by_domain`. Phil Voight (@centralislip.k12.ny.us from tips-usa.com) slipped through Stage 2 as an L15 addition. Fix: call Stage 2 after each L15 merge.
  2. `sheets_writer._ensure_headers` only wrote headers when the tab was EMPTY. The new `Cross-Contam Dropped` column never got appended. Fix: auto-migrate when current header is a prefix of expected columns (safe for append-only schema changes).
  3. Old L10 email check used `domain_root = email_domain.split(".")[0]` which misses real school domains like `centralislip.k12.ny.us` (pattern is in parts[1:], not parts[0]). Rewrote to use `_is_school_host` + `_email_domain_matches_target` on the full hostname.
  4. `_contam_contacts_filtered = dropped` → `+= dropped` so L15's second invocation doesn't overwrite the L9 count.
- **Audit commit `b809198`** — `scripts/audit_leads_cross_contamination.py` + `bug5_phase0_scan.py` + `bug5_cleanup_lackland_test.py` + `bug5_smoke_verify.py`.

**Phase 3 live smoke test.** First attempt failed with 0 contacts because Anthropic API credits were exhausted on Railway (117 credit errors in a 19-min window). Steven topped up. Second attempt hung for 20+ minutes with zero research progress logs (suspected 409 Conflict during rolling deploy overlap). Third attempt on Lackland ISD completed in 7 min.

**Production log evidence:**
```
INFO:tools.research_engine:L9 page filter: 9/234 pages dropped as cross-district (target=lacklandisd.net)
INFO:tools.sheets_writer:Migrating header for tab Research Log: 8 → 9 cols
```

**Smoke test results:** 27 total contacts (vs 31 from the broken-credits run — filter caught 4 leaks). 25 with email, 6 verified. Research Log row shows `Cross-Contam Dropped: 9`. All 25 new Lackland rows fingerprint as clean via `scripts/bug5_smoke_verify.py`.

**Phase 4 historical audit.** `scripts/audit_leads_cross_contamination.py` fingerprinted all 483 rows in Leads from Research, gated by both Phase 0 oracles (known-bad must drop + clean spot-check must pass). Results:

| Bucket | Count |
|---|---|
| clean_both | 175 |
| clean_email | 271 |
| clean_source | 4 |
| generic (personal email) | 1 |
| ambiguous | 9 |
| source_mismatch | 1 |
| email_mismatch | 11 |
| both_mismatch | 11 |

**95% clean / 4.8% flagged.** Google Doc report: https://docs.google.com/document/d/1TFle1jiyEiFqU_hv-rxIxsCf-WxXXDRoRaKW2A6MEfA/edit

**Notable audit nuance** — some flagged rows are false positives the LIVE filter wouldn't produce:
- **Los Angeles Unified** (9 flagged rows) — all @lausd.net. Audit can't match `target_hint="losangelesunified"` to `"lausd"` (abbreviation). Live filter handles correctly via L4-discovered `district_domain="lausd.net"`.
- **Desert Sands Unified** row 212 — @dsusd.us, same abbreviation issue.

**Real contamination for Steven to review manually** (manual cleanup is out of scope per plan):
- Archdiocese of Chicago rows 458, 459 (original Session 53 finding)
- Epic Charter School rows 216, 217 (Collinsville + Spiro staff)
- Columbus City Schools row 333 (Worthington staff)
- Irving STEAM Magnet (2 rows)
- Friendswood ISD row 15 (possibly real — needs check)

### Commits (chronological)

- `0061aed` `Revert "diag: Session 54 Phase 1f — temporary _write_rows logging for BUG 3 ghost writer hunt"` (BUG 3 close-out)
- `746e1e7` `feat: Session 55 operator tooling — Telethon user-API bridge + sentinel cleanup`
- `6ffa1b2` `feat(bug5): Session 55 Commit A — cross-contam filter kill switch + matching helpers`
- `552240f` `feat(bug5): Session 55 Commit B — Stage 1 page filter at raw_pages boundary`
- `148aca6` `feat(bug5): Session 55 Commit C — Stage 2 contact filter + L10 source strengthening`
- `4bdfcfc` `feat(bug5): Session 55 Commit D — Research Log cross_contam_dropped column`
- `22dc28b` `feat(bug5): Session 55 Commit E — wire cross_contam_dropped through research callback`
- `da46dfa` `fix(bug5): Session 55 — L15 additions go through Stage 2 + schema migration fix`
- `b809198` `feat(bug5): Session 55 Phase 4 — historical audit script + supporting diagnostics`

### Plan file

`/Users/stevenadkins/.claude/plans/abundant-finding-riddle.md` — v3 after Steven's ruthless pressure-test. Full decision table, sequencing, oracle gates, exit criteria, risks.

### Session 55 lessons (distilled to memory files)

- `feedback_filter_upstream_not_downstream.md` — filter at earliest boundary with the needed signal, not at the output
- `feedback_take_initiative_on_verified_capabilities.md` — don't ask permission on known-safe reversible actions
- `reference_telethon_bridge.md` — how to drive Scout Telegram end-to-end from Claude Code
- `reference_screenshot_capability.md` — `screencapture -x` + Read tool
- Updated `project_research_cross_contamination.md` with RESOLVED status + all commit SHAs
- Updated `project_f2_column_layout_corruption.md` with Session 55 live evidence capture + RESOLVED

### Still unresolved / uncommitted state after Session 55

- **3 bugs remain** from Session 53 Fire Drill Audit: BUG 4 (F8 diocesan playbook, Priority 2 next), BUG 1 (F4 query redesign, Priority 3), BUG 2 (F5 strategic decision, Priority 4).
- **Historical contamination manual cleanup** — Steven reviews the Google Doc report and decides which rows to delete.
- **`Prospecting Queue BACKUP 2026-04-10 0010` tab** safe to delete when Steven is comfortable.
- **BUG 5 oracle JSONs** live in `scripts/bug5_oracle_*.json` (gitignored) — useful if the matching rule needs iteration.
- **`sequence_builder` fallback-to-cold for `private_school_network` strategy** — minor known issue carried over from Session 53 (Archdiocese Cold Prospecting doc was built with the wrong branch).

### Archived from CLAUDE.md CURRENT STATE

Session 54's full "What's working" + "What's still in-progress" narrative was superseded by the Session 55 entry. BUG 3 Phase 6 sentinel text (including the "Scheduled F2 run at 7:45 AM CDT daily" assumption that turned out wrong), 4 ZZZ sentinel row text, and the "diagnostic logging is temporary" text all removed from CLAUDE.md CURRENT STATE since they no longer describe current state.
