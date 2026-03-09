# Tools Module APIs

Reference for all modules in `tools/`. Read this before editing any file that imports from tools/.

---

## GASBridge (`tools/gas_bridge.py`)
```python
gas = GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)
gas.ping() -> dict
gas.get_sent_emails(months_back=6, max_results=200, page_start=0, page_size=200) -> list[dict]
gas.get_sent_emails_page(months_back=6, page_size=200, page_start=0) -> dict  # has_more field
gas.create_draft(to, subject, body) -> dict
gas.search_inbox(query, max_results=10) -> list[dict]
gas.get_calendar_events(days_ahead=7) -> list[dict]
gas.log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps) -> dict
gas.create_district_deck(district_name, state, contact_name, contact_title, student_count, key_pain_points, products_to_highlight, case_study) -> dict
gas.create_google_doc(title, content, folder_id) -> dict  # {success, doc_id, url, title}
```
**GAS returns calendar `guests` as plain email strings, NOT dicts. Use `_parse_guests()` in main.py to normalize.**

## ResearchQueue (`tools/research_engine.py`)
```python
from tools.research_engine import research_queue  # use the singleton
await research_queue.enqueue(district_name, state, progress_callback, completion_callback)
research_queue.current_job   # property, no ()
research_queue.queue_size    # property, no ()
# NEVER instantiate ResearchJob directly
```

## sheets_writer (`tools/sheets_writer.py`) — MODULE, NOT A CLASS
```python
import tools.sheets_writer as sheets_writer
sheets_writer.write_contacts(contacts, state="")
sheets_writer.count_leads()
sheets_writer.get_leads(state_filter="") -> list[dict]
sheets_writer.get_master_sheet_url()
sheets_writer.log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)
sheets_writer.ensure_sheet_tabs_exist()
sheets_writer.color_all_leads() -> dict  # {colored: int} — recolors all Leads rows by Email Confidence
# Tabs: Leads, No Email, Research Log, Activities, Active Accounts, Goals
# from tools.sheets_writer import SheetsWriter  ← CRASHES — class does not exist
```

## activity_tracker (`tools/activity_tracker.py`) — MODULE, NOT A CLASS
```python
import tools.activity_tracker as activity_tracker
activity_tracker.log_activity(activity_type, district="", contact="", notes="", source="scout", message_id="")
# activity_type: "research_job" | "sequence_built" | "email_drafted" | "email_saved" | "call_logged" | "pandadoc_event" | "dialpad_call" | "call_list_generated"
activity_tracker.get_today_activities(date_str=None) -> list[dict]
activity_tracker.get_activity_summary(date_str=None) -> dict  # {research_job: N, ..., summary_text: str}
activity_tracker.get_goals() -> list[dict]
activity_tracker.set_goal(goal_type, daily_target, description="")
activity_tracker.get_daily_progress(date_str=None) -> dict  # {calls_made: {target, actual, pct}, ..., progress_text: str}
activity_tracker.is_activity_logged(message_id) -> bool
activity_tracker.scan_pandadoc_notifications(gas_bridge) -> list[dict]
activity_tracker.scan_dialpad_summaries(gas_bridge) -> list[dict]
activity_tracker.sync_gmail_activities(gas_bridge) -> dict  # {pandadoc_logged, dialpad_logged, already_seen}
activity_tracker.build_brief_data_block(date_str=None) -> str
# SYNC function — always call via run_in_executor from async context
```

## csv_importer (`tools/csv_importer.py`) — MODULE, NOT A CLASS
```python
import tools.csv_importer as csv_importer
csv_importer.import_accounts(csv_text: str) -> dict
# {imported, districts, schools, libraries, companies, skipped, errors}
# CLEARS Active Accounts tab, rewrites fresh from CSV. Use /import_clear to activate.

csv_importer.merge_accounts(csv_text: str) -> dict
# {imported, districts, schools, libraries, companies, skipped, updated, added, errors}
# DEFAULT mode. Updates existing rows by Name Key, appends new ones, leaves others untouched.
# Dynamically extends sheet headers with new CSV columns not already present.
# Account Type values: district | school | library | company

# _parse_csv returns (records, extra_cols) — preserves ALL CSV columns, not just mapped ones.
# Known columns mapped via _SF_COL_MAP; unknown columns kept with original header name.
# _build_row_for_headers(headers, rec, name_key, acct_type) builds rows for any header list.

csv_importer.replace_accounts_by_state(csv_text: str, state_code: str) -> dict
# {imported, districts, schools, libraries, companies, skipped, replaced, added, errors}
# Removes ALL existing rows where State == state_code, inserts all CSV rows.
# Other states untouched. Use /import_replace_state [STATE] to activate.

csv_importer.dedup_accounts() -> dict
# {total_before, total_after, duplicates_removed, duplicate_names, errors}
# Uses Name Key + State as composite key (fixed Session 18). Safe to use.

csv_importer.classify_account(account_name, parent_account, sf_type) -> str
csv_importer.get_active_accounts(state_filter="") -> list[dict]
csv_importer.get_districts_with_schools() -> list[dict]
# Starts from school accounts → groups by Parent Account → excludes districts already active
# Sorted by school count desc. DO NOT revert to filtering on Account Type == "district"
csv_importer.normalize_name(name: str) -> str
# Strips ISD/USD/etc + "unified" + parenthetical tags; expands _KNOWN_ABBREVIATIONS
csv_importer.get_import_summary() -> str
```

## daily_call_list (`tools/daily_call_list.py`) — MODULE, NOT A CLASS
```python
import tools.daily_call_list as daily_call_list
daily_call_list.build_daily_call_list(max_contacts=10) -> dict
# {success, cards: list[dict], district_count, total_matched, error}
# Synchronous — call via run_in_executor

daily_call_list.write_call_list_to_doc(cards, gas_bridge, folder_id=None) -> dict
# {success, url, error} — uses CALL_LIST_FOLDER_ID env var, falls back to SEQUENCES_FOLDER_ID

daily_call_list.format_for_telegram(cards, doc_url="") -> str

# Card keys: contact_name, title, email, phone, district, state,
#   school_count, schools: list[str], talking_point, is_backfill
```

## district_prospector (`tools/district_prospector.py`) — MODULE, NOT A CLASS
```python
import tools.district_prospector as district_prospector
district_prospector.discover_districts(state, max_results=15) -> dict
# {success, discovered, already_known, new_added, districts, error, territory_warning}
# Synchronous — call via run_in_executor

district_prospector.suggest_upward_targets() -> dict
# {success, new_added, already_known, districts, error}

district_prospector.add_district(name, state, notes="", strategy="cold") -> dict
district_prospector.get_pending(limit=5) -> list[dict]
district_prospector.get_all_prospects(status_filter="") -> list[dict]
district_prospector.approve_districts(indices, batch) -> list[dict]
district_prospector.skip_districts(indices, batch) -> list[dict]
district_prospector.mark_researching(name_key)
district_prospector.mark_complete(name_key, sequence_doc_url="")
district_prospector.clear_queue()  # Wipes all data rows, keeps header
district_prospector.format_batch_for_telegram(districts, label="Prospecting Suggestions") -> str
district_prospector.format_all_for_telegram(districts) -> str

# Prospecting Queue tab columns:
# District Name | Name Key | State | Strategy | Source | Status | Priority |
# Date Added | Date Approved | Sequence Doc URL | Notes | Est. Enrollment |
# School Count | Total Licenses
# Strategy values: upward | cold
# Status values: pending | approved | researching | complete | skipped
```

## pipeline_tracker (`tools/pipeline_tracker.py`) — MODULE, NOT A CLASS
```python
import tools.pipeline_tracker as pipeline_tracker
pipeline_tracker.import_pipeline(csv_text: str) -> dict
# {imported, open, closed, total_value, skipped, errors}
# REPLACE ALL — clears Pipeline tab and rewrites from CSV. Point-in-time snapshot.

pipeline_tracker.is_opp_csv(csv_text: str) -> bool
# Auto-detect: True if CSV header has 2+ of {stage, close date, opportunity name}

pipeline_tracker.get_open_opps() -> list[dict]
pipeline_tracker.get_stale_opps(stale_days=14) -> list[dict]
# Open opps with Last Activity > stale_days ago OR Close Date in past. Adds stale_reason field.

pipeline_tracker.get_pipeline_summary() -> dict
# {total_open, total_value, by_stage: {stage: {count, value}}, stale_count, stale_opps, total_closed}

pipeline_tracker.format_pipeline_for_telegram(summary: dict) -> str
pipeline_tracker.build_pipeline_alerts() -> str
# EOD injection text. Empty string if no alerts.

# Pipeline tab columns (base — extra CSV columns preserved dynamically):
# Opportunity Name | Account Name | Parent Account | Stage | Amount | Close Date |
# Next Step | Age (days) | Last Activity | State | Created Date | Date Imported |
# Type | Primary Contact | Probability (%) | Description | Opportunity Owner
# Closed stages: "closed won", "closed lost", "closed - lost", "closed - won"
# Stale threshold: PIPELINE_STALE_DAYS env var (default 14)
```

## lead_importer (`tools/lead_importer.py`) — MODULE, NOT A CLASS
```python
import tools.lead_importer as lead_importer
lead_importer.import_leads(csv_text: str) -> dict
# {imported, duplicates_skipped, cross_checked, total_in_csv, errors}
# Imports Salesforce Leads CSV into SF Leads tab. Dedup by email/name. Cross-checks Active Accounts.

lead_importer.import_contacts(csv_text: str) -> dict
# {imported, duplicates_skipped, cross_checked, total_in_csv, errors}
# Imports Salesforce Contacts CSV into SF Contacts tab. Same dedup + cross-check.

lead_importer.is_lead_csv(csv_text: str) -> bool
# Auto-detect: True if CSV has 2+ of {Lead Source, Lead Status, Company}

lead_importer.is_contact_csv(csv_text: str) -> bool
# Auto-detect: True if CSV has 2+ of {Account Name, Department, Contact Owner} + name columns

lead_importer.get_unenriched(tab_name: str, limit=20) -> list[dict]
# Records with Enrichment Status = not_started/cross_checked/blank. Includes _row_index.

lead_importer.update_enrichment(tab_name: str, row_index: int, enrichment: dict)
# Update enrichment columns in-place for a specific row.

lead_importer.enrich_record_via_serper(record: dict, tab_type: str) -> dict
# Web search to verify role/school. Returns enrichment dict. Synchronous — call via run_in_executor.

lead_importer.get_import_summary(tab_name: str) -> str
# Returns count summary string.

# Tabs: SF Leads, SF Contacts (separate from existing Leads tab)
# Enrichment columns: Verified School, Verified District, Verified State, Verified County,
#   Active Account Match, Enrichment Status, Enrichment Notes, Last Enriched, Date Imported
# TAB_SF_LEADS = "SF Leads", TAB_SF_CONTACTS = "SF Contacts"
```

## github_pusher (`tools/github_pusher.py`) — lazy import only
```python
import tools.github_pusher as github_pusher
github_pusher.push_file(filepath, content, commit_message=None) -> dict  # {success, url, message}
github_pusher.list_repo_files(path="") -> list[str]
github_pusher.get_file_content(filepath) -> str | None
```

## sequence_builder (`tools/sequence_builder.py`) — lazy import only
```python
import tools.sequence_builder as sequence_builder
sequence_builder.build_sequence(campaign_name, target_role, focus_product="CodeCombat AI Suite", num_steps=5, voice_profile=None, additional_context="", ab_variants=True) -> dict
# {success, steps: [{step, day, label, subject, body, variant_b_subject, variant_b_body}], raw, error}
# Uses prompts/sequence_templates.md for 17 archetypes. Calls claude-sonnet-4-6.
sequence_builder.write_sequence_to_doc(campaign_name, steps, gas_bridge, folder_id=None) -> dict
# {success, url, error} — folder_id defaults to SEQUENCES_FOLDER_ID env var
sequence_builder.format_for_telegram(campaign_name, steps) -> str
# SEQUENCES_FOLDER_ID env var: strip ?query params automatically
```

## FirefliesClient (`tools/fireflies.py`) — lazy import only
```python
from tools.fireflies import FirefliesClient, FirefliesError
client = FirefliesClient(api_key=FIREFLIES_API_KEY)
client.get_transcript(transcript_id) -> dict
# {id, title, date, duration, attendees: [{name, email}], transcript, summary, action_items, keywords}
client.get_recent_transcripts(limit=5, filter_internal=True) -> list[dict]
client.format_recent_for_telegram(transcripts) -> str
```
**Fireflies schema is camelCase:** `dateString`, `speakerName`, `meeting_attendees` (email filtering), `participants` (name strings only).
**Internal filter:** skip if ALL emails are @codecombat.com. Keep if ANY external email present.
