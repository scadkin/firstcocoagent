# Agent Module APIs

Reference for all modules in `agent/`. Read this before editing any file that imports from agent/.

---

## MemoryManager (`agent/memory_manager.py`)
```python
memory_manager.load_preferences() -> str
memory_manager.load_recent_summary() -> str
memory_manager.build_memory_context() -> str
memory_manager.save_preference(entry: str)
memory_manager.append_to_summary(text: str)
memory_manager.clear_preferences()
memory_manager._commit_to_github(filepath, content, message)
memory_manager.extract_memory_update(response) -> tuple  # static
# NO .load() — NO .compress_history()
```

## Scheduler (`agent/scheduler.py`)
```python
scheduler = Scheduler()  # NO arguments
event = scheduler.check()  # returns "morning_brief" | "eod_report" | "checkin" | "weekend_greeting" | "leadership_scan" | "rfp_scan" | "legislative_scan" | None
scheduler.mark_user_active_today()  # suppresses weekend greeting if Steven messages first
# Weekdays: signal_scan 7:45am, leadership_scan Mon 8:00am, rfp_scan Mon 8:15am, legislative_scan 1st Mon 8:30am, morning_brief 9:15am, eod_report 4:30pm
# Saturday: weekend_greeting at 11am (if not already active)
# Sunday: weekend_greeting at 1pm (if not already active)
# NO .run() method
```

## VoiceTrainer (`agent/voice_trainer.py`)
```python
trainer = VoiceTrainer(gas_bridge=gas, memory_manager=memory)
trainer.train(months_back=24, progress_callback=None) -> str
trainer.load_profile() -> Optional[str]
trainer.update_profile_from_feedback(feedback: str) -> bool
```

## CallProcessor (`agent/call_processor.py`) — lazy import only
```python
from agent.call_processor import CallProcessor
processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=None)
# Reads PRECALL_BRIEF_FOLDER_ID from os.environ directly
await processor.build_pre_call_brief(event, attendees, progress_callback=None) -> str
await processor.process_transcript(transcript_id, progress_callback=None, email_override="") -> dict
# {telegram_summary, recap_email, salesforce_block, outreach_row, draft_url, error}
# email_override: skips Fireflies attendee lookup and extracted contact_email
```
`_create_brief_doc` returns: `"https://docs.google.com/..."` | `"ERROR:<msg>"` | `""` (folder ID not set)

**IMPORTANT:** Uses claude-sonnet-4-6 with timeout=90.0. Do NOT use claude-opus-4-5 (hangs indefinitely).

## claude_brain.py
- 24 tool definitions (see root CLAUDE.md for full list)
- Memory injection via memory_manager.build_memory_context()
- All tool calls dispatched to execute_tool() in main.py
