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
