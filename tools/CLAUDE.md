# Tools Module APIs

Reference for all modules in `tools/`. Read this before editing any file that imports from tools/.

---

## GASBridge (`tools/gas_bridge.py`)
```python
gas = GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)
gas.ping() -> dict
gas.get_sent_emails(months_back=6, max_results=200, page_start=0, page_size=200) -> list[dict]
gas.create_draft(to, subject, body) -> dict
gas.search_inbox(query, max_results=10) -> list[dict]
gas.get_calendar_events(days_ahead=7) -> list[dict]
gas.log_call(contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps) -> dict
gas.create_google_doc(title, content, folder_id) -> dict  # {success, doc_id, url, title}
```
**GAS returns calendar `guests` as plain email strings, NOT dicts.**

## ResearchQueue (`tools/research_engine.py`)
```python
from tools.research_engine import research_queue  # singleton
await research_queue.enqueue(district_name, state, progress_callback, completion_callback)
research_queue.current_job   # property
research_queue.queue_size    # property
```

## sheets_writer — MODULE not class
```python
import tools.sheets_writer as sheets_writer
sheets_writer.write_contacts(contacts, state="")
sheets_writer.count_leads()
sheets_writer.get_leads(state_filter="") -> list[dict]
sheets_writer.log_research_job(district, state, layers_used, total_found, with_email, no_email, notes)
sheets_writer.color_all_leads() -> dict
```

## activity_tracker — MODULE not class
```python
import tools.activity_tracker as activity_tracker
activity_tracker.log_activity(activity_type, district="", contact="", notes="", source="scout", message_id="")
activity_tracker.get_activity_summary(date_str=None) -> dict
activity_tracker.get_daily_progress(date_str=None) -> dict
activity_tracker.sync_gmail_activities(gas_bridge) -> dict
# SYNC function — always call via run_in_executor
```

## csv_importer — MODULE not class
```python
import tools.csv_importer as csv_importer
csv_importer.import_accounts(csv_text) -> dict  # clear & rewrite
csv_importer.merge_accounts(csv_text) -> dict   # DEFAULT: update/append by Name Key
csv_importer.replace_accounts_by_state(csv_text, state_code) -> dict
csv_importer.dedup_accounts() -> dict  # Name Key + State composite key
csv_importer.classify_account(account_name, parent_account, sf_type) -> str
csv_importer.get_active_accounts(state_filter="") -> list[dict]
csv_importer.get_districts_with_schools() -> list[dict]
csv_importer.normalize_name(name) -> str
```

## daily_call_list — MODULE not class
```python
import tools.daily_call_list as daily_call_list
daily_call_list.build_daily_call_list(max_contacts=10) -> dict  # sync, use run_in_executor
daily_call_list.write_call_list_to_doc(cards, gas_bridge, folder_id=None) -> dict
daily_call_list.format_for_telegram(cards, doc_url="") -> str
```

## district_prospector — MODULE not class
```python
import tools.district_prospector as district_prospector
district_prospector.discover_districts(state, max_results=15) -> dict  # sync
district_prospector.suggest_upward_targets() -> dict
district_prospector.suggest_closed_lost_targets(buffer_months=6, lookback_months=18) -> dict
district_prospector.suggest_cold_license_requests(sequence_ids=None, progress_callback=None) -> dict
district_prospector.add_district(name, state, notes="", strategy="cold") -> dict
district_prospector.get_pending(limit=5) -> list[dict]
district_prospector.get_all_prospects(status_filter="") -> list[dict]
district_prospector.approve_districts(indices, batch) -> list[dict]
district_prospector.skip_districts(indices, batch) -> list[dict]
district_prospector.clear_queue()
district_prospector.clear_by_strategy(strategy) -> dict
district_prospector.cleanup_prospect_queue() -> dict
district_prospector.migrate_prospect_columns() -> dict

# Prospecting Queue: 19 columns
# State | Account Name | Email | First Name | Last Name | Deal Level | Parent District |
# Name Key | Strategy | Source | Status | Priority | Date Added | Date Approved |
# Sequence Doc URL | Est. Enrollment | School Count | Total Licenses | Notes
# Strategy: upward | cold | winback | cold_license_request
# Status: pending | approved | researching | draft | complete | skipped
```

## pipeline_tracker — MODULE not class
```python
import tools.pipeline_tracker as pipeline_tracker
pipeline_tracker.import_pipeline(csv_text) -> dict   # REPLACE ALL
pipeline_tracker.import_closed_lost(csv_text) -> dict # REPLACE ALL
pipeline_tracker.is_opp_csv(csv_text) -> bool
pipeline_tracker.get_open_opps() -> list[dict]
pipeline_tracker.get_closed_lost_opps(buffer_months=6, lookback_months=18) -> list[dict]
pipeline_tracker.get_pipeline_summary() -> dict
pipeline_tracker.format_pipeline_for_telegram(summary) -> str
pipeline_tracker.build_pipeline_alerts() -> str
```

## lead_importer — MODULE not class
```python
import tools.lead_importer as lead_importer
lead_importer.import_leads(csv_text) -> dict
lead_importer.import_contacts(csv_text) -> dict
lead_importer.is_lead_csv(csv_text) -> bool
lead_importer.is_contact_csv(csv_text) -> bool
lead_importer.clear_leads_tabs() -> dict
lead_importer.clear_contacts_tabs() -> dict
lead_importer.enrich_record_via_serper(record, tab_type) -> dict  # sync
```

## todo_manager — MODULE not class
```python
import tools.todo_manager as todo_manager
todo_manager.add_todo(task, priority="medium", due_date="") -> dict
todo_manager.complete_todo(todo_id) -> dict
todo_manager.complete_todo_by_match(text) -> dict   # fuzzy match open items by text
todo_manager.get_open_todos() -> list[dict]
todo_manager.get_all_todos(include_done=False) -> list[dict]
todo_manager.remove_todo(todo_id) -> dict
todo_manager.clear_completed() -> dict
todo_manager.update_priority(todo_id, priority) -> dict
todo_manager.format_todos_for_telegram(items, title="") -> str
todo_manager.get_checkin_summary() -> str   # used by hourly check-ins
# Todo List tab: ID | Task | Priority | Status | Created | Completed | Due Date
# Priority: high | medium | low. Status: open | done.
```

## github_pusher — lazy import
```python
import tools.github_pusher as github_pusher
github_pusher.push_file(filepath, content, commit_message=None) -> dict
github_pusher.list_repo_files(path="") -> list[str]
github_pusher.get_file_content(filepath) -> str | None
```

## sequence_builder — lazy import
```python
import tools.sequence_builder as sequence_builder
sequence_builder.build_sequence(campaign_name, target_role, ...) -> dict
sequence_builder.write_sequence_to_doc(campaign_name, steps, gas_bridge, folder_id=None) -> dict
```

## FirefliesClient — lazy import
```python
from tools.fireflies import FirefliesClient
client = FirefliesClient(api_key=FIREFLIES_API_KEY)
client.get_transcript(transcript_id) -> dict
client.get_recent_transcripts(limit=5, filter_internal=True) -> list[dict]
```
**Fireflies schema is camelCase. Internal filter: skip if ALL emails are @codecombat.com.**

## territory_data — MODULE not class
```python
import tools.territory_data as territory_data
territory_data.sync_territory(states=None) -> dict  # sync, use run_in_executor
territory_data.get_territory_stats(state_filter="") -> dict
territory_data.get_territory_gaps(state) -> dict
```

## CallProcessor — lazy import
```python
from agent.call_processor import CallProcessor
processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=None)
await processor.process_transcript(transcript_id, progress_callback=None, email_override="") -> dict
```
**Uses claude-sonnet-4-6 with timeout=90.0. Do NOT use claude-opus-4-5.**
