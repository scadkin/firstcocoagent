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
