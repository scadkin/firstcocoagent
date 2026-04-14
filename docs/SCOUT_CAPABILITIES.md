# Scout Capabilities Index
*Last updated: 2026-04-13 (Session 61)*

**Purpose:** This file is auto-loaded at session start via a Claude Code `SessionStart` hook. Its job is to prevent "did I build this already?" amnesia by listing every committed Scout capability with file:line pointers. If you're about to write code that feels like it might already exist, search this file first.

**Maintenance:** hand-updated when a new module or public function ships. A session that adds to `tools/` must also add an entry here in the same commit. See Rule 18 in CLAUDE.md.

---

## `tools/outreach_client.py` — Outreach.io JSON:API v2 client

OAuth + refresh token auto-managed. Scopes: `accounts.read`, `prospects.read/write`, `sequences.read/write`, `sequenceStates.read/write/delete`, `sequenceSteps.read/write`, `sequenceTemplates.read/write`, `templates.read/write`, `users.read`, `mailings.read`, `calls.read`, `events.read`. Base URL: `https://api.outreach.io/api/v2`.

**⚠ Missing scopes (add on next OAuth re-auth):** `prospects.delete` (confirmed S61 via 403 on canary cleanup), `mailboxes.read` (confirmed S61 via 403 on get_mailboxes). Work around: no-op on the failure paths, note in audit log.

**Reads:**
- `get_sequences()` — all Scout-owned sequences (139 total)
- `get_sequence_states(sequence_id, include_prospect=True)` — all prospect states in a seq
- `get_prospect(prospect_id)` — single prospect fetch
- `get_mailings_for_prospect(prospect_id, sequence_id=None)` — engagement data
- `get_pricing_prospect_ids(sequence_ids)` — bulk prospect IDs across sequences
- `get_sequence_steps(sequence_id)` — all steps + templates for a seq
- `get_mailboxes()` — ⚠ **returns 403, scope not granted despite outreach_api_access.md**. Infer mailbox IDs from existing sequenceStates instead.

**Writes (sequences):**
- `validate_sequence_inputs(...)` at line 814 — 12-check pre-write validator. S59 hardening. Zero API calls. Returns `{passed, failures, warnings}`.
- `create_sequence(name, steps, description, schedule_id, ...)` at line 1198 — creates sequence + steps + templates + sequenceTemplate links. Calls validator first. Post-write verify optional.
- `verify_sequence(seq_id, expected=...)` at line 968 — post-write / audit fetch + validation.

**Writes (prospects)** — *new Session 61, promoted from S38/S43 ephemeral scripts*:
- `validate_prospect_inputs(...)` — 10-check pre-write validator. **Rule 17 enforces IANA timezone.** Placeholder block catches Cloudflare obfuscation masks with zero `@` signs. Rejects apostrophe local-parts and generic free-mail.
- `create_prospect(first_name, last_name, email, *, title, company, state, timezone, tags, owner_id=11)` — POST /prospects. Calls validator first.
- `find_prospect_by_email(email)` — GET /prospects filter, returns first match or None.
- `add_prospect_to_sequence(prospect_id, sequence_id, *, mailbox_id=11)` — POST /sequenceStates.

**Export:**
- `export_sequence(sequence_id)` / `format_sequence_export(...)` — dump sequence to Google Doc shape

**Core facts:**
- Steven's user ID: **11**
- Steven's mailbox ID: **11**
- 5 named delivery schedules: `{48, 50, 51, 52, 53}` (env `OUTREACH_ALLOWED_SCHEDULE_IDS`, default baked in)
  - 48 = SA Workdays
  - 50 = C4 Tue-Thu Morning
  - 51 = Hot Lead Mon-Fri
  - 52 = Admin Mon-Thurs Multi-Window (diocesan sequences 2008-2013)
  - 53 = Teacher Tue-Thu Multi-Window
- Interval is in **seconds**, not minutes
- toRecipients must be **`[]`** on templates (never `["{{toRecipient}}"]`)

---

## `tools/prospect_loader.py` — *new S61*

Reusable bulk-load orchestrator. First caller is `scripts/diocesan_drip.py`; future callers include C4 re-engagement, signal-to-sequence autoflows, any `/drip_*` command.

- `Contact` dataclass — required fields for validate_prospect_inputs
- `LoadPlan` dataclass — one contact assigned to one sequence on one day
- `build_load_plan(contacts, sequence_id_for, days, tags_for, group_key)` — round-robin by group, VERIFIED first, deterministic
- `execute_load_plan(plans, state_path, audit_path, target_day, sleep_seconds, verify_sequence_active, dry_run)` — resumable live loader
- `read_state(path)` / `write_state_atomic(path, plans)` / `append_audit(path, record)` — state file I/O helpers

State file format: `data/<name>_state.json` (gitignored). Audit log: `data/<name>_audit.jsonl`.

---

## `tools/campaign_file.py` — *new S64*

Single-file campaign markdown schema for multi-variant campaigns. Lives at `campaigns/<slug>.md` with YAML frontmatter + `## variant: <role>` sections. Used by `scripts/load_campaign.py` as the claude.ai round-trip surface: Steven drafts copy in claude.ai, pastes into the file, loader ingests.

- `Campaign`, `CampaignVariant`, `CampaignStep` dataclasses
- `load_campaign(path)` / `parse_campaign(text)` — permissive markdown parser (handles H2/H3/H4 step headings, `—` / `-` / `:` separators)
- `dump_campaign(campaign)` — inverse emitter, round-trip safe
- `VALID_ROLES` — `admin | curriculum | it | teacher | coach | other`
- `DEFAULT_STEP_INTERVALS_DAYS = [0, 5, 6, 7, 8]` — diocesan-matching cadence

Tests: `scripts/test_campaign_file.py` (10 cases, round-trip + edge cases).

---

## `tools/role_classifier.py` — *new S64*

Haiku-backed contact role bucketing. Classifies a K-12 contact (primarily by title) into one of six buckets via Claude Haiku at `temp=0`. Used by `scripts/load_campaign.py` to route contacts to role-variant sequences in multi-variant campaigns.

- `classify_contact_role(contact, *, client=None, cache_path=None)` — returns one of `admin | curriculum | it | teacher | coach | other`. Never raises.
- Pre-filter: `agent.target_roles.is_relevant_role` drops IT infra + irrelevant CTE trades to `other` without a Claude call.
- Cache: sha1(normalized title) → bucket, at `data/role_classifier_cache.json` (gitignored, reused across runs).
- Kill switch: `ROLE_CLASSIFIER_MODE=pass_through` env var routes every contact to `other`.

S64 live smoke test: 14/14 real K-12 titles classified correctly. Tests: `scripts/test_role_classifier.py` (11 cases using mock Anthropic client).

---

## `scripts/load_campaign.py` — *new S64*

Generalized campaign loader CLI. Strategy-agnostic replacement for the pattern hand-coded three times (S38 CUE, S43 C4, S44 webinar) before the S61 library promotion. Ingests `campaigns/<slug>.md`, classifies contacts by role, creates Outreach sequences per variant, loads contacts into the right sequence with same-district stagger.

Modes:
- `--campaign <slug> --preview --contacts-csv <path>` — build load plan, print it, no API calls
- `--campaign <slug> --create` — preflight all variants, then create sequences (writes IDs to `data/<slug>.state.json`)
- `--campaign <slug> --create --dry-run` — preflight only, no POSTs
- `--campaign <slug> --execute --contacts-csv <path>` — load contacts into already-created sequences (respects `drip_days`)
- `--campaign <slug> --execute --dry-run` — print plan without any writes
- `--campaign <slug> --execute --force` — bypass drift check (campaign file edited after `--create`)
- `--contacts-stdin` instead of `--contacts-csv` — read CSV from stdin (for paste workflows)

Sidecar state file: `data/<slug>.state.json` — tracks sequences per role, campaign file sha1 (drift detection), load-run history. Audit log: `data/<slug>.audit.jsonl`.

CSV columns required: `first_name, last_name, email, title, company, state`. Extra columns ignored. Rule 17: contacts missing state or with non-US state are skipped (never faked). Rule 19: output translates sequence IDs to variant role names; raw IDs never appear in stdout.

Canary fixture: `campaigns/canary_test.md` + `campaigns/canary_test_contacts.csv`. Verification: `.venv/bin/python scripts/load_campaign.py --campaign canary_test --create --dry-run` must preflight cleanly on all 3 variants; `.venv/bin/python scripts/load_campaign.py --campaign canary_test --preview --contacts-csv campaigns/canary_test_contacts.csv` must classify 5 contacts into 4 buckets via Haiku.

---

## `tools/outreach_client.py::export_sequence_for_editing` — *new S64*

Thin wrapper around the existing `export_sequence(sequence_id)` helper. Fetches an Outreach sequence and renders it as a `campaigns/<slug>.md` starter in the `campaign_file` schema. Supports the "old sequence as starter" workflow — Steven pipes the output to a file, opens in claude.ai, iterates the copy, saves back into `campaigns/`.

- `export_sequence_for_editing(sequence_id, *, role="other", target_role_label="", slug_override="")` → markdown string
- v1 produces a single-variant campaign; Steven can add more variants after pasting into claude.ai
- v1 keeps Outreach body_html as-is (parser stores opaquely; round-trip lossless)

Tests: `scripts/test_export_sequence_for_editing.py` (4 cases with mock `export_sequence`, offline-safe).

---

## `tools/timezone_lookup.py` — *new S61*

- `state_to_timezone(state_code)` — 2-letter US state → IANA zone. 50 states + DC + PR.
- `is_valid_iana_timezone(tz)` — parse gate via `zoneinfo.ZoneInfo`. Returns False for empty/invalid.

Edge cases documented inline: IN/TN/NE/KY/FL/ND/SD/OR/ID split between two zones; defaults pick majority-population zone.

---

## `tools/research_engine.py` — 20-layer contact research pipeline

- `ResearchJob(district, state, ...)` — builds a research result dict via Phase A (parallel L1/L2/L3/L5/L16/L20) → Phase B (L4 domain) → Phase C (parallel L6/L11/L12/L13/L14/L17/L18/L19) → Phase D (L7/L8) → Phase E (L9 Claude extract) → L10 dedup/score → L15 email verify → re-L10.
- `ResearchQueue` singleton — serial job execution via `await research_queue.enqueue(...)`

**S61 Round 1 feature flags (all default OFF after Level 3 Waverly gate failure):**
- `enable_url_dedup`: longest-content-per-URL dedup in L9. Still fails verified_quality_gate; Round 1.1 needs different approach.
- `l15_step5_skip_threshold`: skip L15 Step 5 discovery when ≥N verified already found. Contributes ~3-5 contact loss on Waverly.
- `log_claude_usage`: capture `response.usage` token counts via module-level buffer in contact_extractor. Safe across run_in_executor thread boundaries.

**Research engine is parked on Round 1.1 planning. Do not modify flags on the 4 `agent/main.py` call sites until Round 1.1 ships.**

---

## `tools/contact_extractor.py`

- `extract_contacts(raw_content, source_url, district_name)` — single-page Claude extraction
- `extract_from_multiple(pages, district_name)` — batch page extraction with S61 upgrade-on-collision dedup
- `_merge_contact_upgrade(existing, new)` — shared helper: fills missing email, upgrades confidence VERIFIED > LIKELY > INFERRED > UNKNOWN, fills empty title, never drops, never downgrades
- `start_usage_capture()` / `stop_usage_capture()` / `_log_usage(response, url)` — module-level Claude usage capture (S61 Round 1 Flag C)
- `infer_email(first, last, domain, pattern)` / `detect_email_pattern(emails, domain)`

---

## `tools/signal_processor.py` — signal aggregator + scanner runner

**Top-level:**
- `process_all_signals(gas)` / `process_new_signals(gas, since_date)` — full/incremental batch across all sources
- `write_signals(signals)` — upsert to Signals tab
- `update_signal_status(signal_id, new_status)` / `link_signal_to_prospect(signal_id, prospect_name)`

**Scanners (~$0.03-3 each):**
- `scan_board_meetings(days_back, progress_callback)` — 25 territory districts via BoardDocs
- `scan_leadership_changes(states, progress_callback)` — monthly
- `scan_rfp_opportunities(states, progress_callback)` — monthly
- `scan_legislative_signals(states, progress_callback)` — monthly
- `scan_grant_opportunities(states, progress_callback)` — monthly
- `scan_budget_cycle_signals(states, progress_callback)` — monthly
- `scan_algebra_targets(states, progress_callback)` — on-demand
- `scan_cybersecurity_targets(states, progress_callback)` — on-demand
- `scan_role_targets(states, progress_callback)` — ~$2.50/scan, on-demand
- `scan_csta_chapters(states, progress_callback)` — ~$1.20/scan, on-demand
- `scan_compliance_gaps(state, max_pdfs)` — F9 PDF pilot (CA/IL/MA only, Signals-only)

**Parsers / classifiers:**
- `parse_google_alert(email_body, email_date, message_id)`
- `classify_signal(text)` — returns `(signal_type, tier)`
- `extract_district_and_state(text)` / `extract_dollar_amount(text)`
- `detect_clusters(signals)`
- `process_rss_feeds(since_date, progress_callback)` — K-12 Dive / eSchool News / CSTA

**Formatters:**
- `format_hot_signals(limit, state_filter)` — Telegram list
- `format_signal_detail(signal, related)` / `format_scan_summary(summary)`
- `build_signal_brief_block()` — morning brief injection

**Helper:**
- `build_csta_enrichment(district, state, base_notes) -> (enriched_notes, priority_bonus)` — used by F4/F6/F7/F8 via lazy import

**Kill switches:** each scanner has `ENABLE_X_SCAN = True` constant near the top of the module.

---

## `tools/sheets_writer.py` — Google Sheets write/read

- `write_contacts(contacts, state="")` — append to Leads tab
- `count_leads()` / `get_leads(state_filter="")` — reads
- `log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)` — Research Log append
- `color_all_leads()` — sheet formatting helper

LEAD_COLUMNS: `First Name | Last Name | Title | Email | State | Account | Work Phone | District Name | Source URL | Email Confidence | Date Found`

---

## `tools/csv_importer.py` — Active Accounts CSV import

- `import_accounts(csv_text)` — clear + rewrite
- `merge_accounts(csv_text)` — update/append by Name Key (DEFAULT)
- `replace_accounts_by_state(csv_text, state_code)`
- `dedup_accounts()` — Name Key + State composite key
- `get_active_accounts(state_filter="")` / `get_districts_with_schools()`
- `classify_account(account_name, parent_account, sf_type)`
- `normalize_name(name)` / `fuzzy_match_name(query_key, candidates, threshold=0.7)`

---

## `tools/district_prospector.py` — Prospecting Queue

- `add_district(name, state, notes, strategy, source, signal_id, **kwargs)` — main writer. kwargs: `est_enrollment, school_count, sending_districts, schools, total_licenses`
- `discover_districts(state, max_results)` — Serper-based discovery
- `suggest_upward_targets()` / `suggest_closed_lost_targets(buffer_months, lookback_months)`
- `suggest_cold_license_requests(sequence_ids, progress_callback)` — C4 feeder
- `suggest_sequence_reengagement(exclude_sequence_ids, progress_callback)`
- `find_lookalike_districts(state, max_results, min_enrollment)` / `format_lookalikes_for_telegram(result)`
- `get_pending(limit)` / `get_all_prospects(status_filter)`
- `approve_districts(indices, batch)` / `skip_districts(indices, batch)`
- `clear_queue()` / `clear_by_strategy(strategy)` / `cleanup_prospect_queue()` / `migrate_prospect_columns()`

**Strategies:** `upward | cold | winback | cold_license_request | trigger | proximity | esa_cluster | charter_cmo | cte_center | private_school_network | compliance_gap`

Queue has 20 columns: `State | Account Name | Email | First Name | Last Name | Deal Level | Parent District | Name Key | Strategy | Source | Status | Priority | Date Added | Date Approved | Sequence Doc URL | Est. Enrollment | School Count | Total Licenses | Signal ID | Notes`

---

## `tools/pipeline_tracker.py` — Salesforce pipeline import

- `import_pipeline(csv_text)` / `import_closed_lost(csv_text)` — REPLACE ALL
- `is_opp_csv(csv_text)` — sniffer
- `get_open_opps()` / `get_closed_lost_opps(buffer_months, lookback_months)` / `get_pipeline_summary()`
- `format_pipeline_for_telegram(summary)` / `build_pipeline_alerts()`

---

## `tools/lead_importer.py` — Lead/Contact CSV import

- `import_leads(csv_text)` / `import_contacts(csv_text)`
- `is_lead_csv(csv_text)` / `is_contact_csv(csv_text)` — sniffers
- `clear_leads_tabs()` / `clear_contacts_tabs()`
- `enrich_record_via_serper(record, tab_type)` — single-row enrichment

---

## `tools/activity_tracker.py` — activity log + dormant detection

- `log_activity(activity_type, district, contact, notes, source, message_id)`
- `get_activity_summary(date_str)` / `get_daily_progress(date_str)`
- `sync_gmail_activities(gas_bridge)`
- `get_dormant_accounts(days=90)` / `format_dormant_for_telegram(dormant, limit)`
- **SYNC function — always call via `run_in_executor`**

---

## `tools/todo_manager.py` — Todo List tab

- `add_todo(task, priority, due_date)` / `complete_todo(todo_id)` / `complete_todo_by_match(text)`
- `get_open_todos()` / `get_all_todos(include_done)` / `get_checkin_summary()`
- `remove_todo(todo_id)` / `clear_completed()` / `update_priority(todo_id, priority)`
- `format_todos_for_telegram(items, title)`

Priorities: `high | medium | low`. Statuses: `open | done`.

---

## `tools/territory_data.py` — NCES territory master

- `sync_territory(states=None)` — SYNC, use run_in_executor
- `get_territory_stats(state_filter)` / `get_territory_gaps(state)`
- `lookup_district_enrollment(name, state)` — returns 0 on miss

---

## `tools/proximity_engine.py` — geographic clustering

- `find_nearby_districts(state, radius_miles, min_enrollment)` — SYNC
- `add_proximity_prospects(state, radius_miles, max_add, min_enrollment)` — SYNC
- `get_esa_districts(state)` / `map_districts_to_esa(state)` / `find_esa_opportunities(state)`
- `format_proximity_for_telegram(result)` / `format_esa_for_telegram(result)`
- `haversine_miles(lat1, lon1, lat2, lon2)`

Strategies: `proximity` (source `proximity_auto`) and `esa_cluster`. Agency Type 4 = ESAs.

---

## `tools/territory_map.py` — visual territory map

- `generate_territory_map(state_filter)` → HTML string
- `generate_territory_map_file(output_path, state_filter)` → file path
- Layers: Active Accounts (green), Pipeline (orange), Prospects (blue), ESAs (purple), All Districts (gray clustered)

---

## `tools/gas_bridge.py` — Google Apps Script bridge

Class `GASBridge`. Instantiate via `get_gas_bridge()` — never as a free variable inside handle_message or async tasks.
- `ping()`
- `get_sent_emails(months_back, max_results, page_start, page_size)`
- `create_draft(to, subject, body, thread_id, cc, content_type)`
- `search_inbox(query, max_results)` / `search_inbox_full(query, max_results, page_start, body_limit)`
- `get_threads_bulk(thread_ids, body_limit)` — caps 30 thread_ids × 30 msgs each
- `get_calendar_events(days_ahead)` — guests come as plain email strings, NOT dicts
- `log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps)`
- `create_google_doc(title, content, folder_id)` → `{success, doc_id, url, title}`

---

## `tools/daily_call_list.py` — morning call list

- `build_daily_call_list(max_contacts=10)` — SYNC
- `write_call_list_to_doc(cards, gas_bridge, folder_id)`
- `format_for_telegram(cards, doc_url)`

---

## `tools/email_drafter.py` — inbox auto-draft

- `seed_processed_emails(gas)` — call on startup
- `process_new_emails(gas)` — main entry; classify + draft + create Gmail drafts
- `format_draft_summary(result)` / `get_daily_summary()`

Auto-runs every 5 min during business hours (7a-6p CST weekdays). Thread-aware (S50+).

---

## `tools/sequence_builder.py` — sequence copy + Doc writer (lazy import)

- `build_sequence(campaign_name, target_role, num_steps, ...)` → `{steps, ...}`
- `write_sequence_to_doc(campaign_name, steps, gas_bridge, folder_id)`

---

## `tools/charter_prospector.py` — F6 Charter CMO seed list

- `load_charter_cmos()` — reads `memory/charter_cmos.json` (43 CMOs, 918 schools)
- `filter_cmos_by_state(cmos, state)`
- `queue_charter_cmos(state)` — via `add_district` with strategy `charter_cmo`
- `format_queue_result_for_telegram(result)` / `list_charter_cmos_for_telegram(state)`

---

## `tools/cte_prospector.py` — F7 CTE Center directory

- `load_cte_centers()` — reads `memory/cte_centers.json` (79 centers, 1009 sending districts)
- `filter_centers_by_state(centers, state)` / `filter_centers_cs_only(centers)`
- `queue_cte_centers(state, cs_only=True)` — strategy `cte_center`
- `format_queue_result_for_telegram(result)` / `list_cte_centers_for_telegram(state, cs_only)`

---

## `tools/private_schools.py` — F8 Private school network seed + discovery

- `list_private_school_networks(state)` / `PRIVATE_SCHOOL_NETWORKS` (24-network seed)
- `discover_private_schools(state, max_results)` — Serper-based
- `queue_private_school_networks(state)` — strategy `private_school_network`
- `format_discovery_for_telegram(result)` / `format_networks_queue_for_telegram(result)`

**Not comprehensive** — NCES PSS data isn't exposed via API, Urban Institute doesn't have it.

---

## `tools/compliance_gap_scanner.py` — F9 CS grad compliance PDF pilot

- `scan_compliance_gaps(state, max_pdfs)` — PDF pilot
- `format_scan_result_for_telegram(result)`
- `PILOT_STATES = {"CA", "IL", "MA"}`
- `ENABLE_COMPLIANCE_SCAN` kill switch

Signals-only. Uses Serper `filetype:pdf` + httpx download + Claude Sonnet 4.6 document input.

---

## `tools/github_pusher.py` — GitHub memory persistence (lazy import)

- `push_file(filepath, content, commit_message)`
- `list_repo_files(path)` / `get_file_content(filepath)`

---

## `tools/fireflies.py` — call transcript client (lazy import)

`FirefliesClient(api_key)`:
- `get_transcript(transcript_id)`
- `get_recent_transcripts(limit, filter_internal=True)`

Schema is camelCase. Internal filter: skip if all emails @codecombat.com.

---

## Scripts — one-shot + test harnesses

- `scripts/test_outreach_validator.py` — 14 S59 unit tests for validate_sequence_inputs
- `scripts/test_round1_unit.py` — 21 S61 unit tests for research engine Round 1 flags
- `scripts/test_diocesan_drip.py` — 15 S61 unit tests for timezone + validate_prospect_inputs + build_load_plan
- `scripts/diocesan_drip.py` — S61 CLI for diocesan load (Rule 18: use this path, not ephemeral)
- `scripts/ab_research_engine.py` + `scripts/ab_analyze.py` — S61 research engine A/B harness
- `scripts/create_c4_sequences.py` — S43 historical: created sequences 1995-1998. Actual prospect loader was ephemeral and NOT committed. See Rule 18.
- `scripts/s59_regen_diocesan_sequences.py` — S59 diocesan sequences 2008-2013 rebuild
- `scripts/enrich_c4_titles.py` — C4 title enrichment via Outreach title lookup
- `scripts/level2_integration_check.py` — S61 research engine pre-merge integration test runner

---

## Historical context (things that exist but are NOT in library code)

- **Session 38**: 11 CUE sequences created + prospects loaded via ephemeral inline Python. Loader code was not committed. The pattern is now canonical in `tools/outreach_client.create_prospect` + `tools/prospect_loader.execute_load_plan`.
- **Session 43**: 4 C4 sequences (1995-1998) created via `scripts/create_c4_sequences.py`. 1,119 prospects loaded via ephemeral inline Python. Same story — use the library functions now.
- **Research engine Round 1 (S61)**: 3 feature flags shipped but all default OFF after Level 3 Waverly verified_quality_gate failure. Round 1.1 needed.
- **Diocesan Round 1 (S59)**: 6 sequences 2008-2013 created via `scripts/s59_regen_diocesan_sequences.py`. Steven activated them S61. 65 prospects loading via `scripts/diocesan_drip.py` S61+.
