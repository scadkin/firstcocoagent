"""
agent/main.py
Scout's entry point. Phase 6E: District Prospecting Queue + all previous phases.
"""

import asyncio
from datetime import datetime
from functools import partial
import logging
import os
import re
import time
import pytz
CST = pytz.timezone('America/Chicago')

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from agent.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, AGENT_NAME,
    GAS_WEBHOOK_URL, GAS_SECRET_TOKEN, gas_bridge_configured,
)
from agent.claude_brain import process_message, build_draft_prompt, draft_email_with_claude
from agent.memory_manager import MemoryManager
from agent.scheduler import Scheduler
from agent.voice_trainer import VoiceTrainer
from tools.research_engine import research_queue   # singleton queue from Phase 2
import tools.sheets_writer as sheets_writer
import tools.activity_tracker as activity_tracker
import tools.csv_importer as csv_importer
import tools.daily_call_list as daily_call_list
import tools.district_prospector as district_prospector
import tools.pipeline_tracker as pipeline_tracker
import tools.lead_importer as lead_importer
import tools.territory_data as territory_data
import tools.todo_manager as todo_manager
import tools.proximity_engine as proximity_engine
import tools.signal_processor as signal_processor
import tools.charter_prospector as charter_prospector
import tools.cte_prospector as cte_prospector
import tools.private_schools as private_schools
import tools.compliance_gap_scanner as compliance_gap_scanner
import tools.email_drafter as email_drafter
from tools.telegram_bot import send_message
# Phase 4/5 modules imported lazily inside execute_tool() — safe to boot without them

# Phase 5 vars read from env directly (no config.py change needed)
FIREFLIES_API_KEY = os.environ.get("FIREFLIES_API_KEY", "")
FIREFLIES_WEBHOOK_SECRET = os.environ.get("FIREFLIES_WEBHOOK_SECRET", "")
PRECALL_BRIEF_FOLDER_ID = os.environ.get("PRECALL_BRIEF_FOLDER_ID", "")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Global state ──────────────────────────────────────────────────────────────

memory = MemoryManager()
conversation_history = []
scheduler = Scheduler()

# Pending draft — stores last unconfirmed draft
_pending_draft = None

# Phase 5: Track which calendar event IDs have had pre-call briefs sent
_precall_briefs_sent: set = set()

# Phase 5+: Fireflies Gmail polling dedup
_fireflies_email_triggers: set = set()   # keyed by "subject[:60]|date[:16]"
_fireflies_processed_ids: set = set()    # keyed by transcript_id
_fireflies_gmail_seeded: bool = False    # True after first scan seeds existing emails

# Phase 6E: Prospecting queue — last shown batch for approve/skip indexing
_last_prospect_batch: list[dict] = []
# C5: Last proximity results for "add nearby" command
_last_proximity_result: dict = {}
# Signal type → prospecting strategy mapping for /signal_act promotion.
# Signals not in this dict default to "trigger" (falls through to cold tier).
# Session 53+ follow-up: add bond / leadership / rfp → their own strategies.
_SIGNAL_TYPE_TO_STRATEGY = {
    "compliance": "compliance_gap",
}

# Signal intelligence: last shown batch for /signal_act indexing
_last_signal_batch: list[dict] = []
_last_reengagement_sequences: list[dict] = []
# Districts flagged as existing customers during approve — awaiting confirmation to proceed
_pending_approve_force: list[dict] = []

# CSV import mode: "merge" (default) or "clear"
_csv_import_mode: str = "merge"
# CSV state-replace mode: when set (e.g. "CA"), next upload replaces only that state's rows
_csv_import_state: str = ""
# Pipeline import mode: when True, next CSV upload goes to Pipeline tab
_pipeline_import_mode: bool = False
# Natural language CSV description — set by pre-upload message or file caption
_pending_csv_intent: dict | None = None
# Closed-lost import mode: when True, next CSV upload goes to Closed Lost tab
_closed_lost_import_mode: bool = False
# SF Leads/Contacts import mode: None | "leads" | "contacts"
_leads_import_mode: str | None = None

# ── Command cheat sheet (appended to morning brief) ──────────────────────────
_COMMAND_CHEAT_SHEET = """
📋 *Quick Commands*
`/call_list [N]` — daily call list (default 10, max 50)
`/progress` — today's KPI dashboard
`/pipeline` — open pipeline + stale alerts
`/brief [meeting]` — pre-call brief
`/call [id] [email]` — process a call transcript
`/recent_calls [N]` — recent external calls
`/sync_activities` — scan Gmail for PandaDoc/Dialpad
`/set_goal [type] [target]` — update KPI target
`/prospect` — next 5 pending districts
`/prospect_discover [state]` — cold district search
`/prospect_upward` — upward targets from accounts
`/prospect_winback` — closed-lost winback targets
`/prospect_approve 1,3` — approve from last batch
`/build_sequence [name]` — build outreach sequence
`/dedup_accounts` — deduplicate Active Accounts
`/color_leads` — recolor Leads tab by confidence
`/import_leads` — next CSV imports as SF leads
`/import_contacts` — next CSV imports as SF contacts
`/import_closed_lost` — next CSV imports as closed-lost opps
`/enrich_leads` — enrich unenriched SF leads
`/territory_sync [state]` — download NCES territory data
`/territory_stats [state]` — territory coverage summary
`/territory_gaps <state>` — gap analysis vs active accounts
`proximity [state] [miles]` — districts near active accounts
`esa [state]` — ESA/service center opportunities
Send a `.csv` — import accounts, leads, or pipeline
""".strip()


def _parse_csv_intent(text: str) -> dict | None:
    """
    Parse natural language CSV description into routing intent.
    Returns {"target": "pipeline"|"accounts", "label": str} or None.
    """
    if not text:
        return None
    lower = text.lower()

    # Closed-lost signals — route to Closed Lost tab (NOT pipeline)
    closed_lost_patterns = ["closed lost", "closed-lost", "winback", "win back", "win-back"]
    if any(p in lower for p in closed_lost_patterns):
        return {"target": "closed_lost", "label": "closed-lost opportunities"}

    # Pipeline / opportunity signals
    opp_patterns = ["pipeline", "opportunit", " opp ", " opps", "open opp",
                    "closed won"]
    if any(p in f" {lower} " for p in opp_patterns):
        return {"target": "pipeline", "label": "pipeline opportunities"}

    # Account / customer signals
    acct_patterns = ["account", "customer"]
    if any(p in lower for p in acct_patterns):
        return {"target": "accounts", "label": "active accounts"}

    # Salesforce leads signals → route to SF Leads tab
    lead_patterns = ["lead", "salesforce lead", "sf lead"]
    if any(p in lower for p in lead_patterns) and "contact" not in lower:
        return {"target": "sf_leads", "label": "Salesforce leads"}

    # Salesforce contacts signals → route to SF Contacts tab
    contact_patterns = ["contact", "salesforce contact", "sf contact"]
    if any(p in lower for p in contact_patterns):
        return {"target": "sf_contacts", "label": "Salesforce contacts"}

    # Webinar signals → route to prospecting queue
    webinar_patterns = ["webinar", "attendee", "registrant"]
    if any(p in lower for p in webinar_patterns):
        if any(x in lower for x in ["didn't attend", "no show", "no-show", "missed", "non-attend"]):
            return {"target": "prospect_webinar_missed", "label": "webinar non-attendees"}
        return {"target": "prospect_webinar", "label": "webinar attendees"}

    # Prospect signals → route to accounts
    prospect_patterns = ["prospect"]
    if any(p in lower for p in prospect_patterns):
        return {"target": "accounts", "label": "accounts"}

    return None


def get_gas_bridge():
    """Lazy-init GAS bridge. Returns None if not configured."""
    if not gas_bridge_configured():
        return None
    from tools.gas_bridge import GASBridge
    return GASBridge(webhook_url=GAS_WEBHOOK_URL, secret_token=GAS_SECRET_TOKEN)


def get_voice_trainer():
    """Lazy-init voice trainer. Returns None if GAS not configured."""
    gas = get_gas_bridge()
    if not gas:
        return None
    return VoiceTrainer(gas_bridge=gas, memory_manager=memory)


def _parse_guests(raw_guests: list) -> list:
    """
    GAS bridge returns guests as either plain email strings OR dicts with {name, email}.
    This helper normalises both formats into [{name, email}] dicts.
    Filters out @codecombat.com addresses.
    """
    attendees = []
    for g in (raw_guests or []):
        if isinstance(g, dict):
            email = g.get("email", "")
            name = g.get("name", "") or email.split("@")[0]
        else:
            # Plain email string
            email = str(g)
            name = email.split("@")[0]
        if email and "@codecombat.com" not in email.lower():
            attendees.append({"email": email, "name": name})
    return attendees


# ── Research callbacks ────────────────────────────────────────────────────────

async def _on_research_progress(message: str):
    await send_message(message)


async def _on_research_complete(result: dict):
    try:
        contacts = result.get("contacts", [])
        write_summary = sheets_writer.write_contacts(contacts, state=result.get("state", ""))
        with_email = result.get("with_email", 0)
        no_email = result.get("no_email", 0)
        total = result.get("total", 0)
        verified = result.get("verified", 0)
        district = result.get("district_name", "")
        state = result.get("state", "")
        elapsed = result.get("elapsed_seconds", 0)
        queries_used = result.get("queries_used", 0)
        layer_counts = result.get("layer_contact_counts", {})
        leads_added = write_summary.get("leads_added", 0)
        no_email_added = write_summary.get("no_email_added", 0)
        dupes_skipped = write_summary.get("duplicates_skipped", 0)
        sheet_url = f"https://docs.google.com/spreadsheets/d/{os.environ.get('GOOGLE_SHEETS_ID', '')}"

        # Format elapsed time
        mins, secs = divmod(elapsed, 60)
        elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

        # Format layer breakdown (only layers that found contacts)
        layer_lines = []
        layer_order = [
            "L1:direct-title", "L2:title-variations", "L3:linkedin",
            "L4:district-site", "L5:news-grants", "L6:scrape", "L7:deep-crawl",
            "L11:school-staff", "L12:board-agendas", "L13:state-doe", "L14:conference",
            "L15:email-verify",
        ]
        for layer in layer_order:
            count = layer_counts.get(layer, 0)
            layer_lines.append(f"  {layer}: {count}")
        # Include any layers not in the order list
        for layer, count in layer_counts.items():
            if layer not in layer_order:
                layer_lines.append(f"  {layer}: {count}")

        msg = (
            f"✅ *Research complete: {district}*\n\n"
            f"⏱ Time: {elapsed_str} | 🔍 Serper queries: {queries_used}\n"
            f"📊 Found: {total} total — {with_email} with email, {no_email} name-only\n"
            f"✅ Verified emails: {verified} | 🆕 New to sheet: {leads_added + no_email_added} | ♻️ Dupes skipped: {dupes_skipped}\n\n"
            f"*Layer breakdown (contacts found per strategy):*\n"
            + "\n".join(layer_lines)
            + f"\n\n[View sheet]({sheet_url})"
        )

        # Cap-hit reporting
        if result.get("cap_hit"):
            skipped = result.get("skipped_layers", [])
            skipped_str = ", ".join(skipped) if skipped else "some layers"
            msg += (
                f"\n\n⚠️ *Hit the {queries_used}-query safety limit.* Layers skipped: _{skipped_str}_\n"
                f"There are likely more leads — say *\"keep digging on {district}\"* to continue."
            )

        await send_message(msg)

        # Log to Research Log tab
        try:
            layer_notes = " | ".join(f"{k}:{v}" for k, v in layer_counts.items() if v > 0)
            notes = f"{elapsed_str} | {queries_used} queries | {layer_notes}"
            sheets_writer.log_research_job(
                district=district,
                state=state,
                layers_used=result.get("layers_used", ""),
                total_found=total,
                with_email=with_email,
                no_email=no_email,
                notes=notes,
                cross_contam_dropped=result.get("cross_contam_dropped", 0),
            )
        except Exception as log_err:
            logger.error(f"Research log write failed: {log_err}")

        # Phase 6C: log to Activities tab
        try:
            activity_tracker.log_activity(
                activity_type="research_job",
                district=district,
                contact="",
                notes=f"{total} contacts found ({with_email} with email) | {elapsed_str}",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log failed: {act_err}")

    except Exception as e:
        logger.error(f"Research completion handler failed: {e}")
        await send_message(f"❌ Research finished but sheet write failed: {e}")


async def _on_prospect_research_complete(result: dict, prospect: dict):
    """Runs after research finishes for an approved prospect. Logs research, then auto-builds a sequence and marks complete."""
    # Run the standard research-complete flow first (writes to Sheets, sends Telegram summary)
    await _on_research_complete(result)

    district_name = prospect.get("Account Name", prospect.get("District Name", result.get("district_name", "")))
    name_key = prospect.get("Name Key", "")
    strategy = prospect.get("Strategy", "cold")
    state = prospect.get("State", result.get("state", ""))
    school_count = prospect.get("School Count", "")
    notes = prospect.get("Notes", "")

    # Auto-build a sequence for this prospect
    try:
        import tools.sequence_builder as sequence_builder
        strategy_labels = {"upward": "Upward", "winback": "Winback", "cold": "Cold", "cold_license_request": "License Request Re-engagement"}
        campaign_name = f"{district_name} — {strategy_labels.get(strategy, 'Cold')} Prospecting"
        target_role = "CS/CTE Director"

        # Build context based on strategy
        extra_context = f"State: {state}. Strategy: {strategy}."
        if strategy == "upward" and school_count:
            extra_context += (
                f" This district has {school_count} schools already using CodeCombat."
                f" CRITICAL: Do NOT fabricate claims about these accounts — do not assume"
                f" how the schools are doing, how many students use it, or what products they have."
                f" Only cite verifiable facts: school name and that they are active customers."
            )
            if notes:
                extra_context += f" {notes}"
        elif strategy == "winback":
            extra_context += (
                f" This is a RE-ENGAGEMENT / WINBACK sequence for a closed-lost deal."
                f"\n\nCRITICAL REQUIREMENTS:"
                f"\n- Use Outreach.io variables: {{{{first_name}}}}, {{{{state}}}}, {{{{company}}}}"
                f"\n- At least ONE step must be a 'reply' email (Re: subject, keeps thread context, bumps to top of inbox)"
                f"\n- Highlight what's new/improved at CodeCombat since they last evaluated (CodeCombat AI, new pricing, etc.)"
                f"\n- Include incentivization (extended trial, free pilot, flexible pricing)"
                f"\n- Final email should be a 'breakup' email (creates gentle urgency, highest reply rate)"
                f"\n- Tone: warm and empathetic, NOT pushy. These teachers WANTED the product but got blocked."
                f"\n\nCONTEXT ON WHY DEALS CLOSE LOST (from actual data):"
                f"\n- ~61% UNRESPONSIVE: teacher went dark after admin pushback or budget rejection. They wanted the product but stopped advocating."
                f"\n  For these: acknowledge they went quiet, lead with empathy, don't blame. Offer a fresh start and give them ammo to try again with admin."
                f"\n- ~19% BUDGET: admin said no due to cost/funding loss. Teacher couldn't make the case."
                f"\n  For these: acknowledge the budget challenge, lead with new pricing/flexible options, help them build an ROI case for their admin."
                f"\n- ~5% NOT USING/DIDN'T START: bought but never implemented. Teacher turnover or lack of support."
                f"\n  For these: offer hands-on onboarding, training support, implementation help."
                f"\n- ~4% TEACHER TURNOVER: champion left the school/role. Need to find the new POC."
                f"\n  For these: introduce yourself fresh, reference the prior relationship, offer a clean-slate demo."
                f"\n- ~2% COMPETITOR: chose another product. May be regretting it."
                f"\n  For these: lead with curiosity (how's it going?), highlight CodeCombat AI differentiators, offer side-by-side pilot."
                f"\n- Teachers get discouraged asking admins and getting told 'no' — they stop advocating."
                f"\n  Re-engage with empathy and give them tools/ammo to try again."
            )
            if notes:
                extra_context += f"\n\nPrior deal info: {notes}"
        elif strategy == "cold":
            extra_context += " No existing CodeCombat presence in this district."

        voice_profile = None
        try:
            with open("memory/voice_profile.md", "r", encoding="utf-8") as f:
                voice_profile = f.read()
        except FileNotFoundError:
            pass

        await send_message(f"✍️ Auto-building sequence for *{district_name}*...")
        seq_result = sequence_builder.build_sequence(
            campaign_name=campaign_name,
            target_role=target_role,
            num_steps=4 if strategy == "upward" else 5,
            voice_profile=voice_profile,
            additional_context=extra_context,
        )

        doc_url = ""
        if seq_result["success"]:
            gas = get_gas_bridge()
            if gas:
                doc_result = sequence_builder.write_sequence_to_doc(campaign_name, seq_result["steps"], gas)
                doc_url = doc_result.get("url", "")

            try:
                activity_tracker.log_activity(
                    activity_type="sequence_built",
                    district=district_name,
                    contact=target_role,
                    notes=f"Auto-built from prospecting queue | {strategy}",
                    source="scout",
                )
            except Exception:
                pass

            # All sequences are drafts — show for Steven's review before finalizing
            if doc_url:
                await send_message(
                    f"📝 *DRAFT — {campaign_name}*\n\n"
                    f"📄 [Review sequence draft]({doc_url})\n\n"
                    f"Please review and let me know any feedback or if it's good to go."
                )
            else:
                tg_text = sequence_builder.format_for_telegram(campaign_name, seq_result["steps"])
                await send_message(f"📝 *DRAFT — {campaign_name}*\n\n{tg_text}\n\nPlease review and share feedback.")
            # Mark as draft — Steven will approve or give feedback
            district_prospector._update_status(name_key, "draft", {"Sequence Doc URL": doc_url} if doc_url else None)
        else:
            await send_message(f"⚠️ Sequence generation failed for {district_name}: {seq_result.get('error', '?')}")

    except Exception as e:
        logger.error(f"Prospect auto-sequence failed for {district_name}: {e}")
        await send_message(f"⚠️ Research done for {district_name} but sequence auto-build failed: {e}")


# ── Tool execution ─────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict) -> str:
    global _pending_draft

    if tool_name == "research_district":
        district = tool_input.get("district_name", "")
        state = tool_input.get("state", "")
        if not district:
            return "❌ No district name provided."
        await send_message(f"🔍 Starting research on *{district}*{' (' + state + ')' if state else ''}...")
        await research_queue.enqueue(
            district_name=district,
            state=state,
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
        )
        return f"📋 Research queued for *{district}*. Full 15-layer run typically takes 5–10 minutes. I'll ping you every minute so you know it's still working."

    elif tool_name == "research_batch":
        targets = tool_input.get("targets", [])
        if not targets:
            return "❌ No targets provided."
        names = [t.get("district_name", "?") for t in targets]
        await send_message(f"📋 Queuing batch research for {len(targets)} districts: {', '.join(names)}")
        await research_queue.enqueue_batch(
            targets=targets,
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
        )
        return f"✅ {len(targets)} research jobs queued. I'll send updates as each completes."

    elif tool_name == "get_sheet_status":
        try:
            counts = sheets_writer.count_leads()
            sheet_url = sheets_writer.get_master_sheet_url()
            return (
                f"📊 *Sheet status:*\n"
                f"✅ {counts['leads']} contacts with emails\n"
                f"📋 {counts['no_email']} name-only (no email)\n"
                f"📈 {counts['total']} total\n"
                f"[Open sheet]({sheet_url})"
            )
        except Exception as e:
            return f"❌ Could not read sheet: {e}"

    elif tool_name == "get_research_queue_status":
        current = research_queue.current_job
        depth = research_queue.queue_size
        if not current:
            return "✅ No research running. Queue empty."
        return f"🔍 Currently researching: *{current}*\nJobs queued: {depth}"

    elif tool_name == "ping_gas_bridge":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured. Set `GAS_WEBHOOK_URL` and `GAS_SECRET_TOKEN` in Railway."
        try:
            result = gas.ping()
            return f"✅ *GAS Bridge connected!*\nRunning as: `{result.get('user', 'unknown')}`"
        except Exception as e:
            return f"❌ GAS bridge ping failed: {e}"

    elif tool_name == "train_voice":
        trainer = get_voice_trainer()
        if not trainer:
            return "❌ GAS bridge not configured yet. Follow `docs/SETUP_PHASE3.md` first."
        months_back = tool_input.get("months_back", 24)
        await send_message(
            "🔄 *Starting voice training...*\n"
            f"Fetching up to 2,000 sent emails from the last {months_back} months. "
            "This takes 3–5 minutes — I'll send updates as I go."
        )
        def on_progress(msg):
            asyncio.create_task(send_message(msg))
        try:
            profile = trainer.train(months_back=months_back, progress_callback=on_progress)
            if profile.startswith("❌"):
                return profile
            return (
                "✅ *Voice profile built!*\n\n"
                "I've analyzed your sent emails and learned your writing style. "
                "Every draft from now on will sound like you.\n\n"
                "Try: `Draft a cold email to the CS Director at Austin ISD`"
            )
        except Exception as e:
            logger.error(f"Voice training error: {e}")
            return f"❌ Voice training failed: {e}"

    elif tool_name == "draft_email":
        trainer = get_voice_trainer()
        voice_profile = trainer.load_profile() if trainer else None
        recipient_name = tool_input.get("recipient_name", "")
        recipient_title = tool_input.get("recipient_title", "")
        district = tool_input.get("district", "")
        state = tool_input.get("state", "")
        email_type = tool_input.get("email_type", "cold outreach")
        additional_context = tool_input.get("additional_context", "")
        await send_message(f"✍️ Drafting {email_type} email for *{recipient_title or 'contact'}* at *{district}*...")
        prompt = build_draft_prompt(
            voice_profile=voice_profile,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            district=district,
            state=state,
            email_type=email_type,
            additional_context=additional_context,
        )
        draft_text = draft_email_with_claude(prompt)
        if draft_text.startswith("❌"):
            return draft_text
        subject, body = _parse_draft(draft_text)
        _pending_draft = {"to": "", "subject": subject, "body": body, "raw": draft_text}

        # Phase 6C: log email draft
        try:
            activity_tracker.log_activity(
                activity_type="email_drafted",
                district=district,
                contact=f"{recipient_name} ({recipient_title})" if recipient_name else recipient_title,
                notes=f"Type: {email_type} | Subject: {subject}",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log (draft_email) failed: {act_err}")

        return (
            f"📧 *Draft ready:*\n\n"
            f"{draft_text}\n\n"
            "---\n"
            "• *looks good* → save to Gmail Drafts\n"
            "• *edit: [what to change]* → I'll revise\n"
            "• *add email: name@district.org* → set recipient"
        )

    elif tool_name == "save_draft_to_gmail":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        to = tool_input.get("to", "") or (_pending_draft or {}).get("to", "")
        subject = tool_input.get("subject", "") or (_pending_draft or {}).get("subject", "")
        body = tool_input.get("body", "") or (_pending_draft or {}).get("body", "")
        if not subject or not body:
            return "❌ No draft to save. Draft an email first."
        try:
            result = gas.create_draft(to=to, subject=subject, body=body)
            _pending_draft = None

            # Phase 6C: log email saved
            try:
                activity_tracker.log_activity(
                    activity_type="email_saved",
                    district="",
                    contact=to,
                    notes=f"Subject: {subject}",
                    source="scout",
                )
            except Exception as act_err:
                logger.error(f"Activity log (email_saved) failed: {act_err}")

            return (
                f"✅ *Saved to Gmail Drafts!*\n"
                f"Subject: _{subject}_\n"
                f"[Open Gmail Drafts]({result.get('link', 'https://mail.google.com/mail/u/0/#drafts')})"
            )
        except Exception as e:
            return f"❌ Could not save draft: {e}"

    elif tool_name == "get_calendar":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        days_ahead = tool_input.get("days_ahead", 7)
        try:
            events = gas.get_calendar_events(days_ahead=days_ahead)
            if not events:
                return f"📅 No events in the next {days_ahead} days."
            lines = [f"📅 *Next {days_ahead} days ({len(events)} events):*\n"]
            for ev in events:
                lines.append(f"• *{ev.get('title', '?')}*")
                lines.append(f"  {ev.get('start', '')}")
                if ev.get("location"):
                    lines.append(f"  📍 {ev['location']}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Could not fetch calendar: {e}"

    elif tool_name == "log_call":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        try:
            result = gas.log_call(
                contact_name=tool_input.get("contact_name", ""),
                title=tool_input.get("title", ""),
                district=tool_input.get("district", ""),
                date_iso=tool_input.get("date_iso"),
                duration_minutes=tool_input.get("duration_minutes", 30),
                notes=tool_input.get("notes", ""),
                outcome=tool_input.get("outcome", ""),
                next_steps=tool_input.get("next_steps", ""),
            )

            # Phase 6C: log call activity
            try:
                activity_tracker.log_activity(
                    activity_type="call_logged",
                    district=tool_input.get("district", ""),
                    contact=tool_input.get("contact_name", ""),
                    notes=f"Outcome: {tool_input.get('outcome', '')} | {tool_input.get('notes', '')}",
                    source="scout",
                )
            except Exception as act_err:
                logger.error(f"Activity log (log_call) failed: {act_err}")

            return (
                f"✅ *Call logged!*\n"
                f"_{result.get('title', 'Call')}_\n"
                f"[View in Calendar]({result.get('link', 'https://calendar.google.com/calendar/r')})"
            )
        except Exception as e:
            return f"❌ Could not log call: {e}"

    elif tool_name == "create_district_deck":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        district = tool_input.get("district_name", "")
        await send_message(f"📊 Building pitch deck for *{district}*...")
        try:
            result = gas.create_district_deck(
                district_name=district,
                state=tool_input.get("state", ""),
                contact_name=tool_input.get("contact_name", ""),
                contact_title=tool_input.get("contact_title", ""),
                key_pain_points=tool_input.get("key_pain_points", []),
                products_to_highlight=tool_input.get("products_to_highlight", []),
                case_study=tool_input.get("case_study", ""),
            )
            return (
                f"✅ *Pitch deck created!*\n"
                f"_{result.get('title', district)}_ — {result.get('slide_count', '?')} slides\n"
                f"[Open in Google Slides]({result.get('url', '')})"
            )
        except Exception as e:
            return f"❌ Could not create deck: {e}"

    elif tool_name == "push_code":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "❌ `tools/github_pusher.py` not found in repo."
        filepath = tool_input.get("filepath", "").strip()
        content = tool_input.get("content", "")
        commit_msg = tool_input.get("commit_message", "")
        if not filepath or not content:
            return "❌ Need both `filepath` and `content` to push."
        await send_message(f"📤 Pushing `{filepath}` to GitHub...")
        result = github_pusher.push_file(
            filepath=filepath,
            content=content,
            commit_message=commit_msg or f"Scout: update {filepath}",
        )
        if result["success"]:
            url = result.get("url", "")
            link = f"\n[View on GitHub]({url})" if url else ""
            return f"{result['message']}{link}\n\n⚡️ Railway will auto-deploy in ~30 seconds."
        else:
            return result["message"]

    elif tool_name == "list_repo_files":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "❌ `tools/github_pusher.py` not found in repo."
        path = tool_input.get("path", "")
        files = github_pusher.list_repo_files(path)
        if not files:
            return f"❌ Could not list files in `{path or 'repo root'}`."
        label = f"`{path}/`" if path else "repo root"
        lines = [f"📁 *Files in {label}:*\n"] + [f"• `{f}`" for f in files]
        return "\n".join(lines)

    elif tool_name == "get_file_content":
        try:
            import tools.github_pusher as github_pusher
        except ImportError:
            return "github_pusher.py not found — upload tools/github_pusher.py to GitHub first."
        filepath = tool_input.get("filepath", "").strip()
        if not filepath:
            return "Need a filepath. Example: agent/main.py"
        content_str = github_pusher.get_file_content(filepath)
        if content_str is None:
            return f"Could not fetch {filepath} — use list_repo_files to check available paths."
        line_count = len(content_str.splitlines())
        char_count = len(content_str)
        return (
            f"FILE: {filepath} | {line_count} lines, {char_count} chars"
            f"\n\n```\n{content_str}\n```"
        )

    elif tool_name == "build_sequence":
        try:
            import tools.sequence_builder as sequence_builder
        except ImportError:
            return "❌ `tools/sequence_builder.py` not found in repo."
        campaign_name = tool_input.get("campaign_name", "")
        target_role = tool_input.get("target_role", "")
        focus_product = tool_input.get("focus_product", "CodeCombat AI Suite")
        num_steps = int(tool_input.get("num_steps", 5))
        additional_context = tool_input.get("additional_context", "")
        if not campaign_name or not target_role:
            return "❌ Need at least `campaign_name` and `target_role` to build a sequence."
        await send_message(
            f"✍️ Building {num_steps}-step sequence for *{target_role}*...\n"
            f"Campaign: _{campaign_name}_"
        )
        voice_profile = None
        try:
            with open("memory/voice_profile.md", "r", encoding="utf-8") as f:
                voice_profile = f.read()
        except FileNotFoundError:
            pass
        result = sequence_builder.build_sequence(
            campaign_name=campaign_name,
            target_role=target_role,
            focus_product=focus_product,
            num_steps=num_steps,
            voice_profile=voice_profile,
            additional_context=additional_context,
        )
        if not result["success"]:
            return f"❌ Sequence generation failed: {result['error']}"
        steps = result["steps"]
        tg_text = sequence_builder.format_for_telegram(campaign_name, steps)
        # Write to Google Doc via GAS bridge
        gas = get_gas_bridge()
        doc_result = sequence_builder.write_sequence_to_doc(campaign_name, steps, gas)
        if doc_result["success"] and doc_result["url"]:
            full_output = f"📄 [Full sequence — {campaign_name}]({doc_result['url']})\n\n{tg_text}"
        else:
            raw_error = doc_result.get("error", "unknown error")
            logger.error(f"Sequence doc creation failed: {raw_error}")
            full_output = f"{tg_text}\n\n⚠️ Doc creation failed: `{raw_error}`\n📋 Copy steps into Outreach.io manually."
        # Send directly to Telegram — bypasses Claude so it can't rewrite the output
        await send_message(full_output)

        # Phase 6C: log sequence built
        try:
            activity_tracker.log_activity(
                activity_type="sequence_built",
                district="",
                contact=target_role,
                notes=f"Campaign: {campaign_name} | {num_steps} steps",
                source="scout",
            )
        except Exception as act_err:
            logger.error(f"Activity log (sequence_built) failed: {act_err}")

        return "✅ Sequence built and sent above."

    elif tool_name == "process_call_transcript":
        try:
            from tools.fireflies import FirefliesClient
            from agent.call_processor import CallProcessor
        except ImportError as e:
            return f"Phase 5 module not found: {e}"
        transcript_id = tool_input.get("transcript_id", "").strip()
        if not transcript_id:
            return "Need a transcript ID. Use /recent_calls to find one."
        gas = get_gas_bridge()
        if not gas:
            return "GAS bridge not configured."
        if not FIREFLIES_API_KEY:
            return "FIREFLIES_API_KEY not set in Railway."
        fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=fireflies)
        except Exception as e:
            return f"❌ Could not initialize call processor: {e}"
        await send_message(f"📞 Processing transcript `{transcript_id}`... This takes 30-60 seconds.")
        async def on_progress(msg):
            await send_message(msg)
        email_override = tool_input.get("email_override", "").strip()
        result = await processor.process_transcript(transcript_id=transcript_id, progress_callback=on_progress, email_override=email_override)
        if result.get("error"):
            return "Processing failed: " + result["error"]
        await send_message(result["telegram_summary"])
        await send_message(result["salesforce_block"])
        return ""

    elif tool_name == "get_pre_call_brief":
        try:
            from agent.call_processor import CallProcessor
        except ImportError as e:
            return f"agent/call_processor.py not found: {e}"
        gas = get_gas_bridge()
        if not gas:
            return "GAS bridge not configured."
        meeting_title = tool_input.get("meeting_title", "")
        attendee_emails = tool_input.get("attendee_emails", [])
        try:
            events = gas.get_calendar_events(days_ahead=14)
        except Exception as e:
            return f"❌ Could not fetch calendar: {e}"
        target_event = None
        if meeting_title:
            for ev in events:
                if meeting_title.lower() in ev.get("title", "").lower():
                    target_event = ev
                    break
        else:
            for ev in events:
                loc = (ev.get("location") or "") + (ev.get("description") or "")
                if "zoom.us" in loc.lower():
                    target_event = ev
                    break
        if not target_event and not attendee_emails:
            titles = ", ".join("'" + e.get("title","?") + "'" for e in events[:5]) if events else "none"
            return f"Could not find a Zoom meeting. Upcoming events: {titles}"
        if attendee_emails:
            attendees = [{"email": e, "name": e.split("@")[0]} for e in attendee_emails]
        else:
            raw_guests = (target_event or {}).get("guests", [])
            attendees = _parse_guests(raw_guests)
            if not attendees:
                attendees = [{"name": "Prospect", "email": ""}]
        mtitle = (target_event or {}).get("title", meeting_title or "your meeting")
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory)
        except Exception as e:
            return f"❌ Could not initialize call processor: {e}"
        async def on_brief_progress(msg):
            await send_message(msg)
        brief = await processor.build_pre_call_brief(
            event=target_event or {"title": meeting_title, "start": ""},
            attendees=attendees,
            progress_callback=on_brief_progress,
        )
        await send_message(brief)
        return ""

    # ── Phase 6C tools ────────────────────────────────────────────────────────

    elif tool_name == "get_activity_summary":
        try:
            date_str = tool_input.get("date", None)
            progress = activity_tracker.get_daily_progress(date_str=date_str)
            return progress.get("progress_text", "No activity data available.")
        except Exception as e:
            return f"❌ Could not load activity data: {e}"

    elif tool_name == "get_accounts_status":
        try:
            return csv_importer.get_import_summary()
        except Exception as e:
            return f"❌ Could not read Active Accounts tab: {e}"

    elif tool_name == "set_goal":
        goal_type = tool_input.get("goal_type", "")
        daily_target = tool_input.get("daily_target", 0)
        description = tool_input.get("description", "")
        if not goal_type or not daily_target:
            return "❌ Need goal_type and daily_target."
        try:
            activity_tracker.set_goal(goal_type, int(daily_target), description)
            return f"✅ Goal updated: *{goal_type}* = {daily_target}/day"
        except Exception as e:
            return f"❌ Could not update goal: {e}"

    elif tool_name == "sync_gmail_activities":
        gas = get_gas_bridge()
        if not gas:
            return "❌ GAS bridge not configured."
        try:
            await send_message("🔄 Scanning Gmail for PandaDoc and Dialpad events...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, activity_tracker.sync_gmail_activities, gas)
            pd = result.get("pandadoc_logged", 0)
            dd = result.get("dialpad_logged", 0)
            seen = result.get("already_seen", 0)
            return (
                f"✅ *Gmail scan complete*\n"
                f"📄 PandaDoc events logged: {pd}\n"
                f"📞 Dialpad calls logged: {dd}\n"
                f"♻️ Already seen (skipped): {seen}"
            )
        except Exception as e:
            return f"❌ Gmail sync failed: {e}"

    # ── Phase 6D: Daily Call List ────────────────────────────────────────────

    elif tool_name == "generate_call_list":
        max_contacts = int(tool_input.get("max_contacts", 10))
        await send_message("Building your daily call list...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, daily_call_list.build_daily_call_list, max_contacts
            )
            if not result["success"]:
                return f"Could not build call list: {result['error']}"
            cards = result["cards"]
            if not cards:
                return "No contacts matched your active accounts. Research more districts or upload a fresh Salesforce CSV."
            doc_url = ""
            gas = get_gas_bridge()
            if gas:
                doc_result = await loop.run_in_executor(
                    None, daily_call_list.write_call_list_to_doc, cards, gas
                )
                doc_url = doc_result.get("url", "")
            tg_text = daily_call_list.format_for_telegram(cards, doc_url=doc_url)
            await send_message(tg_text)
            try:
                activity_tracker.log_activity(
                    "call_list_generated",
                    notes=f"{len(cards)} contacts from {result.get('district_count', 0)} districts",
                )
            except Exception:
                pass
            return "Daily call list built and sent above."
        except Exception as e:
            return f"Call list failed: {e}"

    # ── Phase 6E: Prospect Discovery ─────────────────────────────────────────

    elif tool_name == "discover_prospects":
        state = tool_input.get("state", "")
        if not state:
            return "❌ Need a state. Example: 'discover prospects in Texas'"
        await send_message(f"🔍 Searching for school districts in *{state}*...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.discover_districts, state)
            if not result["success"]:
                return f"Discovery failed: {result['error']}"
            msg = (
                f"Found {result['discovered']} districts in {state}\n"
                f"Already known: {result['already_known']} | New added: {result['new_added']}"
            )
            if result.get("territory_warning"):
                msg += f"\n⚠️ {result['territory_warning']}"
            return msg
        except Exception as e:
            return f"Discovery error: {e}"

    elif tool_name == "find_nearby_prospects":
        account = tool_input.get("account_name", "")
        state = tool_input.get("state", "")
        radius = tool_input.get("radius_miles", 15)
        include_esa = tool_input.get("include_esa", False)

        try:
            loop = asyncio.get_event_loop()
            if account:
                # Targeted mode
                await send_message(f"📍 Finding what's near *{account}*...")
                result = await loop.run_in_executor(
                    None, proximity_engine.find_nearby_one, account, radius
                )
                msg = proximity_engine.format_targeted_for_telegram(result)
            elif state:
                # State sweep
                await send_message(f"📍 Sweeping all active accounts in *{state}*...")
                result = await loop.run_in_executor(
                    None, proximity_engine.find_nearby_state, state, radius
                )
                msg = proximity_engine.format_state_sweep_for_telegram(result)
            else:
                return "❌ Need an account name or state. Example: 'what's near Leander ISD' or 'nearby districts in Texas'"

            if include_esa and state:
                esa_result = await loop.run_in_executor(
                    None, proximity_engine.find_esa_opportunities, state
                )
                msg += "\n\n" + proximity_engine.format_esa_for_telegram(esa_result)

            await send_message(msg)
            return "Proximity results sent."
        except Exception as e:
            return f"Proximity error: {e}"

    elif tool_name == "manage_todos":
        action = tool_input.get("action", "")
        try:
            loop = asyncio.get_event_loop()
            if action == "add":
                task = tool_input.get("task", "")
                if not task:
                    return "Need a task description."
                priority = tool_input.get("priority", "medium")
                item = await loop.run_in_executor(None, todo_manager.add_todo, task, priority)
                icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(priority, "🟡")
                return f"✅ Added #{item['ID']}: {icon} {task}"
            elif action == "complete":
                todo_id = tool_input.get("todo_id")
                task = tool_input.get("task", "")
                if todo_id:
                    result = await loop.run_in_executor(None, todo_manager.complete_todo, int(todo_id))
                elif task:
                    result = await loop.run_in_executor(None, todo_manager.complete_todo_by_match, task)
                else:
                    return "Need a todo_id or task text to complete."
                if "error" in result:
                    return result["error"]
                return f"✅ Done! Checked off #{result['ID']}: {result['Task']}"
            elif action == "list":
                items = await loop.run_in_executor(None, todo_manager.get_all_todos, True)
                msg = todo_manager.format_todos_for_telegram(items)
                await send_message(msg)
                return "Todo list shown."
            elif action == "remove":
                todo_id = tool_input.get("todo_id")
                if not todo_id:
                    return "Need a todo_id to remove."
                result = await loop.run_in_executor(None, todo_manager.remove_todo, int(todo_id))
                if "error" in result:
                    return result["error"]
                return f"🗑 Removed todo #{todo_id}"
            elif action == "clear_completed":
                result = await loop.run_in_executor(None, todo_manager.clear_completed)
                return f"🗑 Cleared {result['cleared']} completed items. {result['remaining']} open."
            elif action == "update_priority":
                todo_id = tool_input.get("todo_id")
                priority = tool_input.get("priority", "medium")
                if not todo_id:
                    return "Need a todo_id to update priority."
                result = await loop.run_in_executor(None, todo_manager.update_priority, int(todo_id), priority)
                if "error" in result:
                    return result["error"]
                return f"Updated #{todo_id} priority to {priority}"
            else:
                return f"Unknown todo action: {action}"
        except Exception as e:
            return f"Todo error: {e}"

    return f"❓ Unknown tool: {tool_name}"


# ── CSV file upload handler ────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CSV file uploads from Steven. Auto-detects opp CSV vs account CSV."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return

    doc = update.message.document
    if not doc:
        return

    filename = doc.file_name or ""
    mime = doc.mime_type or ""

    # Only handle CSV files
    if not (filename.lower().endswith(".csv") or "csv" in mime.lower() or "text" in mime.lower()):
        await send_message(
            "📎 Got a file, but I can only process `.csv` files right now.\n"
            "Export from Salesforce as CSV and send that file."
        )
        return

    global _csv_import_mode, _csv_import_state, _pipeline_import_mode, _closed_lost_import_mode, _pending_csv_intent, _leads_import_mode

    try:
        tg_file = await doc.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        csv_text = file_bytes.decode("utf-8-sig")  # utf-8-sig handles BOM from Excel/Salesforce exports
    except Exception as e:
        await send_message(f"❌ Could not download file: {e}")
        return

    # ── Resolve CSV routing intent ──
    # Priority: explicit slash commands > caption > pre-message description > auto-detect
    # Targets: "pipeline" | "sf_leads" | "sf_contacts" | "accounts"
    caption = (update.message.caption or "").strip()
    caption_intent = _parse_csv_intent(caption) if caption else None
    pre_intent = _pending_csv_intent
    _pending_csv_intent = None  # consume after use

    csv_target = "accounts"  # default
    if _csv_import_state:
        # State-replace is account-specific — always route to Active Accounts
        csv_target = "accounts"
    elif _leads_import_mode == "leads":
        csv_target = "sf_leads"
        _leads_import_mode = None
    elif _leads_import_mode == "contacts":
        csv_target = "sf_contacts"
        _leads_import_mode = None
    elif _closed_lost_import_mode:
        csv_target = "closed_lost"
        _closed_lost_import_mode = False
    elif _pipeline_import_mode:
        csv_target = "pipeline"
        _pipeline_import_mode = False
    elif caption_intent:
        csv_target = caption_intent["target"]
        logger.info(f"CSV routed via caption: {caption_intent['label']}")
    elif pre_intent:
        csv_target = pre_intent["target"]
        logger.info(f"CSV routed via pre-message: {pre_intent['label']}")
    else:
        # Auto-detect: pipeline > sf_leads > sf_contacts > accounts
        if pipeline_tracker.is_opp_csv(csv_text):
            csv_target = "pipeline"
        elif lead_importer.is_lead_csv(csv_text):
            csv_target = "sf_leads"
        elif lead_importer.is_contact_csv(csv_text):
            csv_target = "sf_contacts"

    # ── SF Leads import path ──
    if csv_target == "sf_leads":
        await send_message(f"👤 Got `{filename}` — importing Salesforce leads...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lead_importer.import_leads, csv_text)
        except Exception as e:
            await send_message(f"❌ Leads import failed: {e}")
            return

        imported = result.get("imported", 0)
        active_matched = result.get("active_matched", 0)
        math_filtered = result.get("math_filtered", 0)
        math_active = result.get("math_active", 0)
        dupes = result.get("duplicates_skipped", 0)
        cross = result.get("cross_checked", 0)
        total = result.get("total_in_csv", 0)
        errors = result.get("errors", [])
        sheet_url = lead_importer.get_sf_sheet_url()

        msg = (
            f"✅ *SF Leads import complete!*\n\n"
            f"📊 {imported} leads → SF Leads tab\n"
        )
        if active_matched:
            msg += f"  • {active_matched} active account matches → Leads Assoc Active\n"
        if math_filtered:
            msg += f"  • {math_filtered} math/algebra leads → SF Leads - Math\n"
        if math_active:
            msg += f"  • {math_active} math + active → Leads Assoc Active - Math\n"
        msg += f"  • {imported + active_matched + math_filtered + math_active} total (of {total} in CSV)\n"
        if dupes:
            msg += f"  • {dupes} duplicates skipped\n"
        if errors:
            msg += f"\n⚠️ Errors: {'; '.join(errors[:3])}\n"
        msg += f"\n[View SF Leads tab]({sheet_url})"

        try:
            activity_tracker.log_activity(
                activity_type="research_job",
                district="SF Leads Import",
                notes=f"Imported {imported} leads from {filename}",
                source="manual",
            )
        except Exception:
            pass

        await send_message(msg)
        return

    # ── SF Contacts import path ──
    if csv_target == "sf_contacts":
        await send_message(f"👥 Got `{filename}` — importing Salesforce contacts...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lead_importer.import_contacts, csv_text)
        except Exception as e:
            await send_message(f"❌ Contacts import failed: {e}")
            return

        imported = result.get("imported", 0)
        active_matched = result.get("active_matched", 0)
        math_filtered = result.get("math_filtered", 0)
        math_active = result.get("math_active", 0)
        dupes = result.get("duplicates_skipped", 0)
        cross = result.get("cross_checked", 0)
        total = result.get("total_in_csv", 0)
        errors = result.get("errors", [])
        sheet_url = lead_importer.get_sf_sheet_url()

        msg = (
            f"✅ *SF Contacts import complete!*\n\n"
            f"📊 {imported} contacts → SF Contacts tab\n"
        )
        if active_matched:
            msg += f"  • {active_matched} active account matches → Contacts Assoc Active\n"
        if math_filtered:
            msg += f"  • {math_filtered} math/algebra contacts → SF Contacts - Math\n"
        if math_active:
            msg += f"  • {math_active} math + active → Contacts Assoc Active - Math\n"
        msg += f"  • {imported + active_matched + math_filtered + math_active} total (of {total} in CSV)\n"
        if dupes:
            msg += f"  • {dupes} duplicates skipped\n"
        if errors:
            msg += f"\n⚠️ Errors: {'; '.join(errors[:3])}\n"
        msg += f"\n[View SF Contacts tab]({sheet_url})"

        try:
            activity_tracker.log_activity(
                activity_type="research_job",
                district="SF Contacts Import",
                notes=f"Imported {imported} contacts from {filename}",
                source="manual",
            )
        except Exception:
            pass

        await send_message(msg)
        return

    if csv_target == "closed_lost":
        # ── Closed-Lost import path (REPLACE ALL) ──
        await send_message(f"🔄 Got `{filename}` — importing closed-lost opportunities...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, pipeline_tracker.import_closed_lost, csv_text)
        except Exception as e:
            await send_message(f"❌ Closed-lost import failed: {e}")
            return

        imported = result.get("imported", 0)
        total_value = result.get("total_value", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", [])
        sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")

        msg = (
            f"✅ *Closed-lost import complete!*\n\n"
            f"🔄 {imported} closed-lost opps imported (${total_value:,.0f} total value)\n"
        )
        if skipped:
            msg += f"  • {skipped} skipped (no opp name)\n"
        if errors:
            msg += f"\n⚠️ Errors: {'; '.join(errors)}"
        msg += f"\n\nUse `/prospect_winback` to scan these for re-engagement targets."
        if sheet_id:
            msg += f"\n📋 [Sheet](https://docs.google.com/spreadsheets/d/{sheet_id})"
        await send_message(msg)
        return

    if csv_target == "pipeline":
        # ── Pipeline import path (REPLACE ALL) ──
        _csv_import_mode = "merge"  # reset in case /import_clear was set (pipeline is always replace-all anyway)
        await send_message(f"📊 Got `{filename}` — importing pipeline opportunities...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, pipeline_tracker.import_pipeline, csv_text)
        except Exception as e:
            await send_message(f"❌ Pipeline import failed: {e}")
            return

        imported = result.get("imported", 0)
        open_count = result.get("open", 0)
        closed_count = result.get("closed", 0)
        total_value = result.get("total_value", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", [])
        sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")

        msg = (
            f"✅ *Pipeline import complete!*\n\n"
            f"📊 {imported} opportunities imported\n"
            f"  • {open_count} open (${total_value:,.0f} pipeline value)\n"
            f"  • {closed_count} closed\n"
        )
        if skipped:
            msg += f"  • {skipped} skipped (no opp name)\n"
        if errors:
            msg += f"\n⚠️ Errors: {'; '.join(errors)}"
        if sheet_id:
            msg += f"\n📋 [Pipeline Sheet](https://docs.google.com/spreadsheets/d/{sheet_id})"
        await send_message(msg)
        return

    # ── Account import path ──
    mode = _csv_import_mode
    state_replace = _csv_import_state
    if state_replace:
        mode_label = f"state-replace ({state_replace})"
    elif mode == "clear":
        mode_label = "clear & rewrite"
    else:
        mode_label = "merge"
    await send_message(f"📥 Got `{filename}` — importing Salesforce accounts ({mode_label} mode)...")

    try:
        loop = asyncio.get_event_loop()
        if state_replace:
            result = await loop.run_in_executor(
                None, csv_importer.replace_accounts_by_state, csv_text, state_replace
            )
            _csv_import_state = ""  # reset after use
        elif mode == "clear":
            result = await loop.run_in_executor(None, csv_importer.import_accounts, csv_text)
            _csv_import_mode = "merge"  # reset to merge after a clear import
        else:
            result = await loop.run_in_executor(None, csv_importer.merge_accounts, csv_text)
    except Exception as e:
        await send_message(f"❌ Import failed: {e}")
        return

    imported  = result.get("imported", 0)
    districts = result.get("districts", 0)
    schools   = result.get("schools", 0)
    libraries = result.get("libraries", 0)
    companies = result.get("companies", 0)
    skipped   = result.get("skipped", 0)
    updated   = result.get("updated", 0)
    added     = result.get("added", 0)
    replaced  = result.get("replaced", 0)
    errors    = result.get("errors", [])
    sheet_url = sheets_writer.get_master_sheet_url()

    breakdown = f"  • {districts} districts\n  • {schools} schools\n"
    if libraries:
        breakdown += f"  • {libraries} libraries\n"
    if companies:
        breakdown += f"  • {companies} other (companies/orgs)\n"

    if state_replace:
        msg = (
            f"✅ *{state_replace} accounts replaced!*\n\n"
            f"📊 Removed {replaced} old {state_replace} rows, added {added} new\n"
            f"{breakdown}"
        )
    elif mode == "merge" and (updated or added):
        msg = (
            f"✅ *Salesforce merge complete!*\n\n"
            f"📊 {imported} accounts processed ({updated} updated, {added} new)\n"
            f"{breakdown}"
        )
    else:
        msg = (
            f"✅ *Salesforce import complete!*\n\n"
            f"📊 {imported} accounts imported\n"
            f"{breakdown}"
        )
    if skipped:
        msg += f"⚠️ {skipped} rows skipped (blank account name)\n"
    if errors:
        msg += f"❌ Errors: {'; '.join(errors[:3])}\n"
    msg += f"\n[View Active Accounts tab]({sheet_url})"

    # Log the import as an activity
    try:
        activity_tracker.log_activity(
            activity_type="research_job",
            district="Salesforce Import",
            contact="",
            notes=f"Imported {imported} accounts ({districts} districts, {schools} schools) from {filename}",
            source="manual",
        )
    except Exception:
        pass

    await send_message(msg)


# ── Draft parsing ──────────────────────────────────────────────────────────────

def _parse_draft(draft_text: str) -> tuple:
    subject = ""
    body = draft_text
    match = re.search(r"\*{0,2}Subject:\*{0,2}\s*(.+)", draft_text, re.IGNORECASE)
    if match:
        subject = match.group(1).strip()
        body = draft_text[match.end():].strip()
    return subject, body


# ── Telegram message handler ───────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global conversation_history, _pending_draft, _last_prospect_batch, _pending_approve_force, _csv_import_mode, _csv_import_state, _pipeline_import_mode, _closed_lost_import_mode, _pending_csv_intent, _leads_import_mode, _last_proximity_result, _last_signal_batch, _last_reengagement_sequences

    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return

    user_text = update.message.text.strip()
    logger.info(f"Received: {user_text}")

    # On weekends, mark user as active to suppress auto-greeting
    now = datetime.now(CST)
    if now.weekday() >= 5:  # Saturday or Sunday
        scheduler.mark_user_active_today()

    _ack_sent = False

    # ── Command routing ────────────────────────────────────────────────────────

    if user_text.lower() in ["/ping_gas", "/test_google", "test gas", "ping gas"]:
        user_text = "ping the GAS bridge"

    elif user_text.lower() in ["/train_voice", "train voice", "train my voice", "learn my style"]:
        user_text = "train your voice model from my Gmail history"

    elif user_text.lower() in ["/list_files", "/ls", "list files", "show repo files"]:
        user_text = "list all files in the repo root"

    elif user_text.lower().startswith("/push_code"):
        args = user_text[len("/push_code"):].strip()
        if args:
            await send_message(f"On it — fetching `{args}` from GitHub now...")
            _ack_sent = True
            user_text = (
                f"PUSH_CODE WORKFLOW for '{args}':\n"
                f"Step 1: Call the get_file_content tool immediately to fetch '{args}' from GitHub. Do NOT skip this.\n"
                f"Step 2: Once you have the file, write a 2-3 sentence summary of what it does.\n"
                f"Step 3: Ask Steven exactly this: 'What changes would you like me to make?'\n"
                f"Step 4: Wait for Steven's answer, then make those specific changes to the fetched content and push with push_code.\n"
                f"Do not deviate from these steps."
            )
        else:
            user_text = "Ask Steven which file he wants to update. Once he answers, immediately call get_file_content to fetch it, summarize it, then ask what changes he wants."

    elif user_text.lower() in ["/grade_draft", "grade draft", "grade that draft", "rate that draft"]:
        user_text = (
            "I want to give you feedback on the last email draft you wrote. "
            "Ask me to rate it 1-5 and describe specifically what was off — "
            "tone, length, word choice, CTA, anything. "
            "Then update my voice profile permanently with what you learn."
        )

    elif user_text.lower().startswith("/add_template"):
        args = user_text[len("/add_template"):].strip()
        user_text = (
            f"I'm going to give you one of my actual email templates or snippets that I use regularly. "
            f"{'Here it is: ' + args if args else 'Ask me to paste it.'} "
            f"Analyze the writing style, structure, and tone. "
            f"Then permanently add it to my voice profile under a Templates section so you can reference it when drafting."
        )

    elif re.match(
        r"^(?:/research_district|research|look\s*up|find contacts for|find contacts at)\s+(.+)",
        user_text, re.IGNORECASE,
    ):
        m = re.match(
            r"^(?:/research_district|research|look\s*up|find contacts for|find contacts at)\s+(.+)",
            user_text, re.IGNORECASE,
        )
        raw = m.group(1).strip().rstrip(".")
        # Parse "District Name, State" or "District Name in State"
        state = ""
        for sep in [",", " in "]:
            if sep in raw:
                parts = raw.rsplit(sep, 1)
                raw = parts[0].strip()
                state = parts[1].strip()
                break
        await send_message(f"⏳ Working on it...")
        result = await execute_tool("research_district", {"district_name": raw, "state": state})
        if result:
            await send_message(result)
        return

    elif re.match(r"^(keep digging|dig deeper|keep searching|go deeper)\s+(on\s+)?(.+)", user_text, re.IGNORECASE):
        m = re.match(r"^(keep digging|dig deeper|keep searching|go deeper)\s+(on\s+)?(.+)", user_text, re.IGNORECASE)
        district = m.group(3).strip().rstrip(".")
        await send_message(f"🔍 Continuing deep search on *{district}* with extended query budget...")
        await research_queue.enqueue(
            district_name=district,
            state="",
            progress_callback=_on_research_progress,
            completion_callback=_on_research_complete,
            serper_cap_override=200,
        )
        return

    elif user_text.lower().startswith("/build_sequence") or user_text.lower().startswith("/sequence"):
        args = ""
        for prefix in ["/build_sequence", "/sequence"]:
            if user_text.lower().startswith(prefix):
                args = user_text[len(prefix):].strip()
                break
        campaign_hint = f" for '{args}'" if args else ""
        user_text = (
            f"I want to build an email sequence{campaign_hint}. "
            f"Before building, ask me all of these in one message: "
            f"(1) Exact target role/title — if already clear from the campaign name, confirm it. "
            f"(2) Number of steps — give a recommendation based on the scenario. "
            f"(3) Primary CodeCombat product to highlight — or ask if I want to cover the full suite. "
            f"(4) Any specific context: state CS requirements, budget timing, pain points, or scenario type (cold, post-demo, re-engagement, etc.). "
            f"Once you have my answers, use the build_sequence tool."
        )

    elif user_text.lower().startswith("/brief"):
        args = user_text[len("/brief"):].strip()
        await send_message(
            "🔍 *On it!* Looking up your calendar and researching attendees...\n"
            "This takes about 30-60 seconds. I'll send progress updates."
        )
        tool_input = {"meeting_title": args} if args else {}
        result = await execute_tool("get_pre_call_brief", tool_input)
        if result:
            await send_message(result)
        return

    elif user_text.lower().startswith("/recent_calls") or user_text.lower() in ["recent calls", "list calls", "show calls"]:
        num = 5
        raw = user_text.lower().replace("/recent_calls", "").strip()
        if raw.isdigit():
            num = max(1, min(int(raw), 20))
        if not FIREFLIES_API_KEY:
            await send_message("❌ FIREFLIES_API_KEY not set in Railway.")
            return
        await send_message(f"📞 Fetching your {num} most recent external calls from Fireflies...")
        try:
            from tools.fireflies import FirefliesClient
            ff_client = FirefliesClient(api_key=FIREFLIES_API_KEY)
            transcripts = ff_client.get_recent_transcripts(limit=num, filter_internal=True)
            msg = ff_client.format_recent_for_telegram(transcripts)
        except Exception as e:
            msg = f"❌ Could not fetch Fireflies transcripts: {e}"
        await send_message(msg)
        return

    elif user_text.lower().startswith("/call") and not user_text.lower().startswith("/call_list"):
        args = user_text[len("/call"):].strip()
        if "fireflies.ai" in args and "/transcript/" in args:
            args = args.split("/transcript/")[-1].split("/")[0].split("?")[0]
        # Allow optional email override: /call [id] email@domain.com
        email_override = ""
        parts = args.split()
        if len(parts) >= 2 and "@" in parts[-1]:
            email_override = parts[-1]
            args = " ".join(parts[:-1])
        if args:
            msg = f"📞 Got it — fetching transcript `{args}` from Fireflies..."
            if email_override:
                msg += f"\nUsing email override: {email_override}"
            await send_message(msg)
            tool_input = {"transcript_id": args}
            if email_override:
                tool_input["email_override"] = email_override
            result = await execute_tool("process_call_transcript", tool_input)
            if result:
                await send_message(result)
        else:
            await send_message("Give me the transcript ID, or use /recent_calls to find one.")
        return

    elif user_text.lower() in ["/eod", "eod", "end of day", "eod report"]:
        asyncio.create_task(send_eod_report())
        return

    elif user_text.lower().startswith("/draft") or user_text.lower() in ["draft my emails", "draft emails", "check my inbox", "draft replies"]:
        draft_gas = get_gas_bridge()
        if not draft_gas:
            await send_message("❌ GAS bridge not configured — can't access Gmail.")
            return

        # Check for targeted draft: /draft Allison, /draft Allison Alltucker
        draft_target = None
        if user_text.lower().startswith("/draft"):
            arg = user_text[6:].strip()
            if arg and arg.lower() not in ("force", "emails", "my emails", "replies"):
                draft_target = arg

        if draft_target:
            await send_message(f"📧 Searching for *{draft_target}* in unread inbox...")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, email_drafter.draft_for_sender, draft_gas, draft_target
                )
                if result.get("success"):
                    flag_marker = " ⚠️ FLAG" if result.get("flag") else ""
                    await send_message(
                        f"✉️ Drafted reply to *{result['name']}* — "
                        f"{result['subject'][:50]}{flag_marker}"
                    )
                else:
                    await send_message(f"❌ {result.get('error', 'Could not draft')}")
            except Exception as e:
                await send_message(f"❌ Draft failed: {e}")
            return

        force = "force" in user_text.lower()
        if force:
            cleared = email_drafter.clear_processed_cache()
            await send_message(f"🔄 Force scan — cleared {cleared} seen email(s). Rechecking inbox...")
        else:
            await send_message("📧 Checking inbox for new emails to draft...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, email_drafter.process_new_emails, draft_gas)
            summary = email_drafter.format_draft_summary(result)
            if summary:
                await send_message(summary)
            else:
                msg = result.get("message", "No new emails to draft.")
                await send_message(f"📧 {msg}")
        except Exception as e:
            await send_message(f"❌ Email drafting failed: {e}")
        return

    # ── Phase 6C commands ──────────────────────────────────────────────────────

    elif user_text.lower() in ["/progress", "/kpi", "kpi", "my progress", "how am i doing"]:
        await send_message("📊 Checking today's progress...")
        try:
            loop = asyncio.get_event_loop()
            progress = await loop.run_in_executor(None, activity_tracker.get_daily_progress)
            await send_message(progress.get("progress_text", "No activity data yet today."))
        except Exception as e:
            await send_message(f"❌ Could not load progress: {e}")
        return

    elif user_text.lower().startswith("/dormant") or user_text.lower() in ["dormant", "dormant leads", "dormant accounts"]:
        # Parse optional days: /dormant 120
        parts = user_text.strip().split()
        days = 90
        for p in parts[1:]:
            try:
                days = int(p)
                break
            except ValueError:
                pass
        await send_message(f"💤 Checking for accounts dormant {days}+ days...")
        try:
            loop = asyncio.get_event_loop()
            dormant = await loop.run_in_executor(
                None, activity_tracker.get_dormant_accounts, days)
            output = activity_tracker.format_dormant_for_telegram(dormant)
            await send_message(output)
        except Exception as e:
            await send_message(f"Dormant check failed: {e}")
        return

    elif user_text.lower().startswith("/unanswered") or user_text.lower() in ["unanswered", "unanswered emails", "no reply"]:
        # Parse optional days: /unanswered 45
        parts = user_text.strip().split()
        days = 30
        for p in parts[1:]:
            try:
                days = int(p)
                break
            except ValueError:
                pass
        await send_message(f"📭 Checking for unanswered emails in last {days} days (up to 30 recipients)...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, activity_tracker.get_unanswered_emails, days, gas, 30)
            output = activity_tracker.format_unanswered_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"Unanswered check failed: {e}")
        return

    elif user_text.lower().startswith("/sync_activities") or user_text.lower() in ["sync activities", "sync gmail"]:
        result = await execute_tool("sync_gmail_activities", {})
        if result:
            await send_message(result)
        return

    elif user_text.lower().startswith("/set_goal"):
        args = user_text[len("/set_goal"):].strip().split()
        if len(args) >= 2:
            goal_type = args[0]
            try:
                target = int(args[1])
                result = await execute_tool("set_goal", {"goal_type": goal_type, "daily_target": target})
                await send_message(result)
            except ValueError:
                await send_message("Usage: `/set_goal calls_made 15`\nGoal types: `calls_made`, `districts_researched`, `emails_drafted`")
        else:
            await send_message("Usage: `/set_goal calls_made 15`\nGoal types: `calls_made`, `districts_researched`, `emails_drafted`")
        return

    # ── Phase 6D commands ──────────────────────────────────────────────────────

    elif user_text.lower().startswith("/call_list") or user_text.lower().startswith("/daily_list") or user_text.lower() in [
                               "call list", "daily call list",
                               "who should i call today", "who should i call"]:
        # Parse optional count: /call_list 20
        max_contacts = 10  # default
        parts = user_text.strip().split()
        if len(parts) >= 2:
            try:
                max_contacts = max(1, min(50, int(parts[-1])))
            except ValueError:
                pass
        await send_message(f"Building your daily call list ({max_contacts} contacts)...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, daily_call_list.build_daily_call_list, max_contacts)
            if not result["success"]:
                await send_message(f"Could not build call list: {result['error']}")
                return
            cards = result["cards"]
            if not cards:
                await send_message("No contacts matched your active accounts. Research more districts or upload a fresh Salesforce CSV.")
                return
            doc_url = ""
            gas = get_gas_bridge()
            if gas:
                doc_result = await loop.run_in_executor(
                    None, daily_call_list.write_call_list_to_doc, cards, gas
                )
                doc_url = doc_result.get("url", "")
            tg_text = daily_call_list.format_for_telegram(cards, doc_url=doc_url)
            await send_message(tg_text)
            try:
                activity_tracker.log_activity(
                    "call_list_generated",
                    notes=f"{len(cards)} contacts from {result.get('district_count', 0)} districts",
                )
            except Exception:
                pass
        except Exception as e:
            await send_message(f"Call list failed: {e}")
        return

    elif user_text.lower() in ["/color_leads", "color leads"]:
        await send_message("Recoloring Leads tab by confidence...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, sheets_writer.color_all_leads)
            if result.get("error"):
                await send_message(f"❌ Color leads failed: {result['error']}")
            else:
                await send_message(f"✅ Colored {result.get('colored', 0)} lead rows by confidence level.")
        except Exception as e:
            await send_message(f"Color leads failed: {e}")
        return

    # ── SF Leads/Contacts import commands ─────────────────────────────────

    elif user_text.lower() == "/import_leads":
        _leads_import_mode = "leads"
        await send_message(
            "👤 Leads import mode set. Next CSV upload will import as Salesforce leads into the *SF Leads* tab.\n"
            "Send the Salesforce leads CSV now."
        )
        return

    elif user_text.lower() == "/import_contacts":
        _leads_import_mode = "contacts"
        await send_message(
            "👥 Contacts import mode set. Next CSV upload will import as Salesforce contacts into the *SF Contacts* tab.\n"
            "Send the Salesforce contacts CSV now."
        )
        return

    elif user_text.lower() == "/clear_leads":
        await send_message("🗑️ Clearing all SF Leads tabs...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lead_importer.clear_leads_tabs)
            errors = result.get("errors", [])
            msg = (
                f"✅ Cleared:\n"
                f"  • SF Leads: {result['sf_leads_cleared']} rows\n"
                f"  • Leads Assoc Active: {result['leads_active_cleared']} rows\n"
                f"  • SF Leads - Math: {result['math_leads_cleared']} rows\n"
                f"  • Leads Assoc Active - Math: {result['math_active_cleared']} rows"
            )
            if errors:
                msg += f"\n⚠️ Errors: {'; '.join(errors)}"
            await send_message(msg)
        except Exception as e:
            await send_message(f"❌ Clear failed: {e}")
        return

    elif user_text.lower() == "/clear_contacts":
        await send_message("🗑️ Clearing all SF Contacts tabs...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lead_importer.clear_contacts_tabs)
            errors = result.get("errors", [])
            msg = (
                f"✅ Cleared:\n"
                f"  • SF Contacts: {result['sf_contacts_cleared']} rows\n"
                f"  • Contacts Assoc Active: {result['contacts_active_cleared']} rows\n"
                f"  • SF Contacts - Math: {result['math_contacts_cleared']} rows\n"
                f"  • Contacts Assoc Active - Math: {result['math_active_cleared']} rows"
            )
            if errors:
                msg += f"\n⚠️ Errors: {'; '.join(errors)}"
            await send_message(msg)
        except Exception as e:
            await send_message(f"❌ Clear failed: {e}")
        return

    # ── C1: Territory commands ─────────────────────────────────────────────────

    elif user_text.lower() == "/territory_clear":
        await send_message("🗑️ Clearing all territory data...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, territory_data.clear_territory)
            await send_message(
                f"✅ Cleared {result['districts']} district rows + {result['schools']} school rows"
            )
        except Exception as e:
            await send_message(f"❌ Clear failed: {e}")
        return

    elif user_text.lower().startswith("/territory_sync"):
        args = user_text[len("/territory_sync"):].strip()
        states = [args] if args else None
        label = args.upper() if args else "all territory states"
        await send_message(f"🗺️ Syncing NCES territory data for {label}... this may take a few minutes.")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, territory_data.sync_territory, states)
            if not result["success"]:
                await send_message(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
                return
            msg = (
                f"✅ Territory sync complete\n"
                f"Districts: {result['districts_synced']:,}\n"
                f"Schools: {result['schools_synced']:,}\n"
                f"States: {', '.join(result['states_completed'])}"
            )
            if result.get("errors"):
                msg += f"\n⚠️ Errors: {'; '.join(result['errors'])}"
            await send_message(msg)
        except Exception as e:
            await send_message(f"❌ Territory sync error: {e}")
        return

    elif user_text.lower().startswith("/territory_stats"):
        args = user_text[len("/territory_stats"):].strip()
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, territory_data.get_territory_stats, args)
            await send_message(territory_data.format_stats_for_telegram(result))
        except Exception as e:
            await send_message(f"❌ Territory stats error: {e}")
        return

    elif user_text.lower().startswith("/territory_gaps"):
        args = user_text[len("/territory_gaps"):].strip()
        if not args:
            await send_message("Usage: `/territory_gaps Texas` or `/territory_gaps TX`")
            return
        await send_message(f"🔍 Analyzing territory gaps for {args}...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, territory_data.get_territory_gaps, args)
            await send_message(territory_data.format_gaps_for_telegram(result))

            # If many uncovered, also write to Google Doc
            if result.get("success") and result.get("uncovered_count", 0) > 20:
                try:
                    from tools.gas_bridge import GASBridge
                    gas = GASBridge(
                        webhook_url=os.environ.get("GAS_WEBHOOK_URL", ""),
                        secret_token=os.environ.get("GAS_SECRET_TOKEN", "")
                    )
                    doc_result = await loop.run_in_executor(
                        None, territory_data.write_gaps_to_doc, result, gas
                    )
                    if doc_result.get("success"):
                        await send_message(f"📄 Full gap report: {doc_result['url']}")
                except Exception as e:
                    logger.warning(f"Gap doc creation failed: {e}")
        except Exception as e:
            await send_message(f"❌ Territory gaps error: {e}")
        return

    elif user_text.lower().startswith("/territory_map"):
        args = user_text[len("/territory_map"):].strip()
        state_filter = args.upper() if args else ""
        label = f" for {state_filter}" if state_filter else ""
        await send_message(f"🗺 Generating territory map{label}... This may take a minute.")
        try:
            import tools.territory_map as territory_map
            import tempfile
            from telegram import Bot
            loop = asyncio.get_event_loop()
            map_path = await loop.run_in_executor(
                None, territory_map.generate_territory_map_file, "", state_filter)
            # Send HTML file via Telegram — Steven opens in browser
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            async with bot:
                with open(map_path, "rb") as f:
                    await bot.send_document(
                        chat_id=TELEGRAM_CHAT_ID,
                        document=f,
                        filename=f"scout_territory_map{'_' + state_filter if state_filter else ''}.html",
                        caption=f"🗺 Territory Map{label} — open in browser for interactive view")
        except Exception as e:
            await send_message(f"❌ Territory map error: {e}")
        return

    # ── C5: Proximity + ESA commands ──────────────────────────────────────────

    elif re.match(
        r"^(?:/proximity|/nearby|proximity|nearby districts?)\s*(.*)",
        user_text, re.IGNORECASE,
    ):
        m = re.match(
            r"^(?:/proximity|/nearby|proximity|nearby districts?)\s*(.*)",
            user_text, re.IGNORECASE,
        )
        raw = m.group(1).strip().rstrip(".")
        if not raw:
            await send_message(
                "Usage:\n"
                "  `proximity Leander ISD` — find what's near one account\n"
                "  `proximity Leander ISD 25` — custom radius (miles)\n"
                "  `proximity Texas all` — sweep all accounts in a state"
            )
            return
        # Strip "in" prefix
        raw = re.sub(r"^in\s+", "", raw, flags=re.IGNORECASE)

        # Check for state sweep mode: "Texas all" or "TX all"
        if raw.lower().endswith(" all"):
            state_str = raw[:-4].strip()
            await send_message(f"📍 Sweeping all active accounts in {state_str} (30 mi radius)...")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, proximity_engine.find_nearby_state, state_str, 30.0
                )
                await send_message(proximity_engine.format_state_sweep_for_telegram(result))
            except Exception as e:
                await send_message(f"❌ Proximity error: {e}")
            return

        # Targeted mode (default): parse optional radius at end
        # "Leander ISD 25" → account="Leander ISD", radius=25
        parts = raw.rsplit(" ", 1)
        radius = 15.0
        account_name = raw
        if len(parts) == 2:
            try:
                radius = float(parts[1])
                account_name = parts[0]
            except ValueError:
                pass  # last word isn't a number, use full string as account name

        await send_message(f"📍 Finding districts and schools near *{account_name}* ({radius} mi)...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, proximity_engine.find_nearby_one, account_name, radius
            )
            _last_proximity_result = result
            msg = proximity_engine.format_targeted_for_telegram(result)
            # If there are new districts, show add hint
            new_districts = [d for d in result.get("nearby_districts", []) if not d.get("in_queue")]
            if new_districts:
                msg += f"\n\n_To add districts to queue: `add nearby 1,4,8` (by number above)_"
            await send_message(msg)
        except Exception as e:
            await send_message(f"❌ Proximity error: {e}")
        return

    elif re.match(r"^add nearby\s+(.+)", user_text, re.IGNORECASE):
        m = re.match(r"^add nearby\s+(.+)", user_text, re.IGNORECASE)
        args = m.group(1).strip()
        if not _last_proximity_result or not _last_proximity_result.get("success"):
            await send_message("No proximity results to add from. Run `proximity [account]` first.")
            return

        new_districts = [d for d in _last_proximity_result.get("nearby_districts", [])
                         if not d.get("in_queue")]
        if not new_districts:
            await send_message("No new districts in last proximity results.")
            return

        # Parse indices: "1,4,8" or "all"
        if args.lower() == "all":
            selected = new_districts
        else:
            try:
                indices = [int(x.strip()) for x in args.split(",")]
                selected = [new_districts[i - 1] for i in indices if 0 < i <= len(new_districts)]
            except (ValueError, IndexError):
                await send_message("Usage: `add nearby 1,4,8` or `add nearby all`")
                return

        if not selected:
            await send_message("No valid selections. Use numbers from the proximity list.")
            return

        state = _last_proximity_result.get("state", "")
        ref_account = _last_proximity_result.get("account_name", "")
        try:
            loop = asyncio.get_event_loop()
            # Build the dicts add_proximity_prospects expects
            to_add = []
            for d in selected:
                to_add.append({
                    "name": d["name"],
                    "name_key": d["name_key"],
                    "enrollment": d.get("enrollment", 0),
                    "distance_miles": d.get("distance_miles", 0),
                    "city": d.get("city", ""),
                    "nearest_account": ref_account,
                })
            result = await loop.run_in_executor(
                None, proximity_engine.add_proximity_prospects, to_add, state, ref_account
            )
            names = [d["name"] for d in selected]
            await send_message(
                f"✅ Added {result['new_added']} districts to Prospecting Queue:\n"
                + "\n".join(f"  • {n}" for n in names)
            )
        except Exception as e:
            await send_message(f"❌ Add nearby error: {e}")
        return

    elif re.match(
        r"^(?:/esa|/service.?centers?|esa|service.?centers?)\s*(.*)",
        user_text, re.IGNORECASE,
    ):
        m = re.match(
            r"^(?:/esa|/service.?centers?|esa|service.?centers?)\s*(.*)",
            user_text, re.IGNORECASE,
        )
        raw = m.group(1).strip().rstrip(".")
        if not raw:
            await send_message("Usage: `esa Texas` or `service centers in Ohio`")
            return
        raw = re.sub(r"^in\s+", "", raw, flags=re.IGNORECASE)
        await send_message(f"🏛️ Mapping ESA regions for {raw}...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, proximity_engine.find_esa_opportunities, raw
            )
            await send_message(proximity_engine.format_esa_for_telegram(result))
        except Exception as e:
            await send_message(f"❌ ESA error: {e}")
        return

    elif user_text.lower().startswith("/enrich_leads"):
        args = user_text[len("/enrich_leads"):].strip()
        tab_name = lead_importer.TAB_SF_LEADS  # default to SF Leads
        if args.lower() == "contacts":
            tab_name = lead_importer.TAB_SF_CONTACTS
        await send_message(f"🔍 Checking {tab_name} for unenriched records...")
        try:
            loop = asyncio.get_event_loop()
            unenriched = await loop.run_in_executor(None, lead_importer.get_unenriched, tab_name, 20)
            if not unenriched:
                await send_message(f"✅ All records in {tab_name} are already enriched!")
                return
            await send_message(f"Found {len(unenriched)} unenriched records. Running enrichment (this may take a moment)...")
            enriched_count = 0
            errors_count = 0
            for rec in unenriched:
                row_idx = rec.get("_row_index")
                tab_type = "leads" if tab_name == lead_importer.TAB_SF_LEADS else "contacts"
                enrichment = await loop.run_in_executor(
                    None, lead_importer.enrich_record_via_serper, rec, tab_type
                )
                if enrichment.get("enrichment_status") == "error":
                    errors_count += 1
                    continue
                await loop.run_in_executor(
                    None, lead_importer.update_enrichment, tab_name, row_idx, enrichment
                )
                enriched_count += 1
            msg = f"✅ *Enrichment complete!*\n\n📊 {enriched_count} records enriched"
            if errors_count:
                msg += f"\n⚠️ {errors_count} errors"
            sheet_url = sheets_writer.get_master_sheet_url()
            msg += f"\n\n[View {tab_name} tab]({sheet_url})"
            await send_message(msg)
        except Exception as e:
            await send_message(f"❌ Enrichment failed: {e}")
        return

    # ── Pipeline commands ──────────────────────────────────────────────────

    elif user_text.lower() in ["/pipeline", "pipeline", "show pipeline"]:
        await send_message("Loading pipeline summary...")
        try:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(None, pipeline_tracker.get_pipeline_summary)
            tg_text = pipeline_tracker.format_pipeline_for_telegram(summary)
            await send_message(tg_text)
        except Exception as e:
            await send_message(f"Pipeline summary failed: {e}")
        return

    elif user_text.lower() == "/pipeline_import":
        _pipeline_import_mode = True
        await send_message(
            "📊 Pipeline import mode set. Next CSV upload will import as opportunities (replacing existing pipeline data).\n"
            "Send the Salesforce opp CSV now."
        )
        return

    elif user_text.lower() in ["/import_closed_lost", "/closed_lost_import"]:
        _closed_lost_import_mode = True
        await send_message(
            "🔄 Closed-lost import mode set. Next CSV upload will import to the *Closed Lost* tab.\n"
            "Run a Closed Lost Opportunities report in Salesforce, export as CSV, and send it here."
        )
        return

    # ── Outreach OAuth ─────────────────────────────────────────────────────
    elif user_text.lower().startswith("/connect_outreach") or user_text.lower().startswith("/outreach_connect"):
        import tools.outreach_client as outreach_client
        if not outreach_client.is_configured():
            await send_message("⚠️ Outreach OAuth credentials not configured in Railway env vars.")
            return
        force = "force" in user_text.lower() or "reconnect" in user_text.lower()
        if outreach_client.is_authenticated() and not force:
            user_id = outreach_client.get_user_id()
            await send_message(
                f"✅ Outreach is already connected (user ID: {user_id}).\n"
                f"Use `/outreach_sequences` to list your sequences.\n"
                f"To reconnect as a different user: `/connect_outreach force`"
            )
            return
        auth_url = outreach_client.get_auth_url()
        await send_message(
            f"🔗 *Connect Outreach*\n\n"
            f"Click the link below to authorize Scout to read your Outreach data (read-only):\n\n"
            f"[Authorize Outreach]({auth_url})\n\n"
            f"After approving, you'll be redirected back and Scout will confirm the connection."
        )
        return

    elif user_text.lower() in ["/outreach_status", "/outreach_info"]:
        import tools.outreach_client as outreach_client
        user_id = outreach_client.get_user_id()
        authed = outreach_client.is_authenticated()
        await send_message(
            f"🔗 *Outreach Connection Status*\n\n"
            f"Connected: {'✅' if authed else '❌'}\n"
            f"User ID: {user_id or 'not set'}\n"
            f"Configured: {'✅' if outreach_client.is_configured() else '❌'}"
        )
        return

    elif user_text.lower() in ["/outreach_sequences", "/outreach_seq"]:
        import tools.outreach_client as outreach_client
        if not outreach_client.is_authenticated():
            await send_message("⚠️ Outreach not connected. Use `/connect_outreach` to set up.")
            return
        try:
            loop = asyncio.get_event_loop()
            sequences = await loop.run_in_executor(None, outreach_client.get_sequences)
            if not sequences:
                await send_message("No sequences found in Outreach.")
                return
            lines = [f"📋 *Your Outreach Sequences* ({len(sequences)} total)\n"]
            for seq in sequences[:30]:
                status = "✅" if seq["enabled"] else "⏸"
                contacted = seq.get("num_contacted", 0)
                replied = seq.get("num_replied", 0)
                lines.append(
                    f"{status} *{seq['name']}* (ID: {seq['id']})\n"
                    f"   {contacted} contacted, {replied} replied"
                )
            if len(sequences) > 30:
                lines.append(f"\n_...and {len(sequences) - 30} more_")
            await send_message("\n".join(lines))
        except Exception as e:
            await send_message(f"Outreach error: {e}")
        return

    # ── CSV import mode commands ─────────────────────────────────────────────

    elif user_text.lower() == "/import_clear":
        _csv_import_mode = "clear"
        await send_message("🔄 Import mode set to *clear & rewrite*. Next CSV upload will wipe and replace the target tab (accounts or pipeline — auto-detected from CSV headers).\nSend `/import_merge` to switch back.")
        return

    elif user_text.lower() == "/import_merge":
        _csv_import_mode = "merge"
        _csv_import_state = ""
        await send_message("✅ Import mode set to *merge* (default). Next CSV upload will add new accounts and update existing ones without wiping.")
        return

    elif user_text.lower().startswith("/import_replace_state"):
        parts = user_text.strip().split()
        if len(parts) < 2:
            await send_message("Usage: `/import_replace_state CA` — replaces all accounts for that state, leaves all other states untouched.")
            return
        _csv_import_state = parts[1].upper()
        _csv_import_mode = "merge"  # ensure normal mode doesn't interfere
        await send_message(
            f"🔄 State-replace mode set for *{_csv_import_state}*.\n"
            f"Next CSV upload will remove all existing {_csv_import_state} accounts and replace with new data.\n"
            f"All other states will be untouched.\n"
            f"Send the CSV now, or `/import_merge` to cancel."
        )
        return

    elif user_text.lower() == "/dedup_accounts":
        await send_message("🔍 Scanning Active Accounts for duplicates...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, csv_importer.dedup_accounts)
            removed = result.get("duplicates_removed", 0)
            dupes = result.get("duplicate_names", [])
            errors = result.get("errors", [])
            if errors:
                await send_message(f"❌ Dedup error: {errors[0]}")
            elif removed == 0:
                await send_message("✅ No duplicates found — Active Accounts tab is clean.")
            else:
                dupe_list = "\n".join(f"  • {d}" for d in dupes[:20])
                await send_message(
                    f"✅ *Removed {removed} duplicate rows*\n\n"
                    f"{result['total_before']} → {result['total_after']} rows\n\n"
                    f"Duplicates found:\n{dupe_list}"
                )
        except Exception as e:
            await send_message(f"❌ Dedup failed: {e}")
        return

    # ── Phase 6E commands ──────────────────────────────────────────────────────

    elif user_text.lower().startswith("/prospect_discover"):
        args = user_text[len("/prospect_discover"):].strip()
        if not args:
            await send_message("Usage: `/prospect_discover Texas` or `/prospect_discover TX`")
            return
        await send_message(f"🔍 Searching for school districts in *{args}*...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.discover_districts, args)
            if not result["success"]:
                await send_message(f"Discovery failed: {result['error']}")
                return
            msg = (
                f"Found {result['discovered']} districts in {args}\n"
                f"Already known: {result['already_known']} | New added to queue: {result['new_added']}"
            )
            if result.get("territory_warning"):
                msg += f"\n⚠️ {result['territory_warning']}"
            await send_message(msg)
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Discovery error: {e}")
        return

    elif user_text.lower().startswith("/prospect_upward"):
        await send_message("🔍 Finding upward targets from your active school accounts...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.suggest_upward_targets)
            if not result["success"]:
                await send_message(f"Error: {result['error']}")
                return
            msg = (
                f"Found {result['new_added'] + result['already_known']} upward targets\n"
                f"New added to queue: {result['new_added']} | Already queued: {result['already_known']}"
            )
            await send_message(msg)
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Upward targets error: {e}")
        return

    elif user_text.lower().startswith("/prospect_expansion"):
        # F1: Second buyer expansion — sibling schools in covered districts
        # Optional arg: max per district (default 5)
        args = user_text[len("/prospect_expansion"):].strip()
        max_per_district = 5
        if args:
            try:
                max_per_district = max(0, int(args.split()[0]))
            except (ValueError, IndexError):
                pass
        await send_message(
            f"🏫 Finding sibling schools in your covered districts (cap: {max_per_district}/district)..."
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, district_prospector.suggest_intra_district_expansion, max_per_district
            )
            if not result["success"]:
                await send_message(f"Error: {result['error']}")
                return
            msg = (
                f"🏫 *Intra-District Expansion*\n"
                f"Eligible parent districts: {result['eligible_districts']}\n"
                f"Schools queued: {result['queued']}\n"
                f"Skipped (district fully covered): {result['skipped_district_covered']}\n"
                f"Skipped (no healthy account): {result['skipped_dead']}\n"
                f"Skipped (already in queue): {result['skipped_already_queued']}"
            )
            if result["queued"]:
                msg += "\n\n_Approve in batches of 5-10 with `/prospect_approve` so research catches up._"
            await send_message(msg)
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Expansion error: {e}")
        return

    elif user_text.lower().startswith("/prospect_approve"):
        args = user_text[len("/prospect_approve"):].strip()
        if not args or not _last_prospect_batch:
            await send_message("No prospect batch to approve. Use `/prospect` first.")
            return
        if args.lower() == "all":
            indices = list(range(1, len(_last_prospect_batch) + 1))
        else:
            try:
                indices = [int(x.strip()) for x in args.split(",")]
            except ValueError:
                await send_message("Usage: `/prospect_approve 1,3,5` or `/prospect_approve all`")
                return
        try:
            loop = asyncio.get_event_loop()
            approved = await loop.run_in_executor(
                None, district_prospector.approve_districts, indices, _last_prospect_batch
            )
            if not approved:
                await send_message("No valid indices to approve.")
                return

            # Check approved districts against Active Accounts — warn if already a customer
            active_accounts = await loop.run_in_executor(None, csv_importer.get_active_accounts)
            active_district_keys = {
                csv_importer.normalize_name(a.get("Display Name", ""))
                for a in active_accounts
                if a.get("Account Type", "").lower() == "district"
            }

            clean = []
            flagged = []
            for d in approved:
                nk = d.get("Name Key", "") or csv_importer.normalize_name(d.get("Account Name", d.get("District Name", "")))
                if nk in active_district_keys:
                    flagged.append(d)
                else:
                    clean.append(d)

            # Queue research for clean districts immediately
            if clean:
                names = [d.get("Account Name", d.get("District Name", "?")) for d in clean]
                await send_message(f"✅ Approved {len(clean)} district(s): {', '.join(names)}\nQueuing research...")
                for d in clean:
                    district_prospector.mark_researching(d.get("Name Key", ""))
                    await research_queue.enqueue(
                        district_name=d.get("Account Name", d.get("District Name", "")),
                        state=d.get("State", ""),
                        progress_callback=_on_research_progress,
                        completion_callback=lambda result, prospect=d: asyncio.ensure_future(
                            _on_prospect_research_complete(result, prospect)
                        ),
                    )

            # Warn about flagged districts and ask for confirmation
            if flagged:
                _pending_approve_force = flagged
                flag_names = "\n".join(
                    f"  • *{d.get('District Name', '?')}* — already an active customer (district-level deal)"
                    for d in flagged
                )
                await send_message(
                    f"⚠️ *Active customer conflict detected:*\n{flag_names}\n\n"
                    f"These districts already have a district-level deal in Active Accounts. "
                    f"Prospecting them is usually not the priority — expansion or referral outreach "
                    f"would be handled differently.\n\n"
                    f"Reply *yes* to approve them anyway, or *no* to skip them."
                )

        except Exception as e:
            await send_message(f"Approve error: {e}")
        return

    elif user_text.lower().startswith("/prospect_skip"):
        args = user_text[len("/prospect_skip"):].strip()
        if not args or not _last_prospect_batch:
            await send_message("No prospect batch to skip. Use `/prospect` first.")
            return
        if args.lower() == "all":
            indices = list(range(1, len(_last_prospect_batch) + 1))
        else:
            try:
                indices = [int(x.strip()) for x in args.split(",")]
            except ValueError:
                await send_message("Usage: `/prospect_skip 2,4` or `/prospect_skip all`")
                return
        try:
            loop = asyncio.get_event_loop()
            skipped = await loop.run_in_executor(
                None, district_prospector.skip_districts, indices, _last_prospect_batch
            )
            names = [d.get("Account Name", d.get("District Name", "?")) for d in skipped]
            await send_message(f"⏭ Skipped {len(skipped)} districts: {', '.join(names)}")
        except Exception as e:
            await send_message(f"Skip error: {e}")
        return

    elif user_text.lower().startswith("/prospect_add"):
        args = user_text[len("/prospect_add"):].strip()
        parts = [p.strip() for p in args.split(",")]
        if len(parts) < 2:
            await send_message("Usage: `/prospect_add Austin ISD, TX`")
            return
        name, state = parts[0], parts[1]
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, district_prospector.add_district, name, state)
            await send_message(result["message"])
        except Exception as e:
            await send_message(f"Add error: {e}")
        return

    elif user_text.lower().startswith("/prospect_winback") or user_text.lower() in ["/winback", "winback", "closed lost winback"]:
        try:
            # Parse args: /prospect_winback [all | buffer=N lookback=N]
            # Examples:
            #   /prospect_winback              → default (buffer=6, lookback=18)
            #   /prospect_winback all          → no buffer, no oldest cutoff
            #   /prospect_winback buffer=3     → 3-month buffer, 18-month lookback
            #   /prospect_winback lookback=24  → 6-month buffer, 24-month lookback
            #   /prospect_winback buffer=0 lookback=0  → same as "all"
            parts = user_text.strip().split()
            buffer_months = 6
            lookback_months = 18
            use_all = False
            for p in parts[1:]:
                pl = p.lower()
                if pl == "all":
                    use_all = True
                    buffer_months = 0
                    lookback_months = 0
                elif pl.startswith("buffer="):
                    try:
                        buffer_months = int(pl.split("=", 1)[1])
                    except ValueError:
                        pass
                elif pl.startswith("lookback="):
                    try:
                        lookback_months = int(pl.split("=", 1)[1])
                    except ValueError:
                        pass
            kwargs = {"buffer_months": buffer_months, "lookback_months": lookback_months}

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: district_prospector.suggest_closed_lost_targets(**kwargs)
            )
            if result.get("error") and result.get("new_added", 0) == 0:
                await send_message(f"⚠️ {result['error']}")
            else:
                if use_all:
                    window_label = "all history"
                elif buffer_months != 6 or lookback_months != 18:
                    window_label = f"buffer={buffer_months}mo, lookback={lookback_months}mo"
                else:
                    window_label = "last 18 months (6-month buffer)"
                lines = [f"🔄 *Closed-Lost Winback Scan* ({window_label})\n"]
                lines.append(f"Found *{result['new_added']}* new winback targets")
                if result.get("school_deals") or result.get("district_deals"):
                    lines.append(f"  🏫 {result.get('school_deals', 0)} school-level | 🏛️ {result.get('district_deals', 0)} district-level")
                if result.get("territory_resolved"):
                    lines.append(f"  ({result['territory_resolved']} schools → parent district resolved via territory data)")
                if result.get("already_known"):
                    lines.append(f"({result['already_known']} already in queue)")
                if result.get("already_active"):
                    lines.append(f"({result['already_active']} now active customers — skipped)")
                await send_message("\n".join(lines))

            # Show pending after scan
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                _last_prospect_batch = pending
                await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Winback scan error: {e}")
        return

    elif user_text.lower().startswith("/prospect_lookalike") or user_text.lower() in ["/lookalike", "lookalike", "lookalike districts", "find lookalikes"]:
        try:
            # Parse optional state filter: /prospect_lookalike TX
            parts = user_text.strip().split()
            state_filter = ""
            for p in parts[1:]:
                if len(p) == 2 and p.upper().isalpha():
                    state_filter = p.upper()
                    break
            await send_message("🔍 Analyzing customer profile and finding lookalike districts...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: district_prospector.find_lookalike_districts(state=state_filter))
            output = district_prospector.format_lookalikes_for_telegram(result)
            await send_message(output)
            if result.get("success") and result.get("lookalikes"):
                _last_prospect_batch = [
                    {"Account Name": la["name"], "State": la["state"],
                     "Name Key": la["name_key"], "Est. Enrollment": str(la["enrollment"]),
                     "School Count": str(la["school_count"]),
                     "Strategy": "cold", "Source": "lookalike"}
                    for la in result["lookalikes"][:10]
                ]
                await send_message(
                    "Use `/prospect_approve 1,3,5` to add specific districts to the queue, "
                    "or `/prospect_approve all` to add all 10."
                )
        except Exception as e:
            await send_message(f"Lookalike search error: {e}")
        return

    elif user_text.lower().startswith("/prospect_reengagement") or user_text.lower() in ["/reengagement", "reengagement", "re-engagement"]:
        try:
            parts = user_text.strip().split()
            # Parse args: optional sequence selector + optional segment
            seq_selector = None
            segment = "engaged"
            for p in parts[1:]:
                pl = p.lower()
                if pl in ("engaged", "lurker", "ghost", "all"):
                    segment = pl
                else:
                    try:
                        seq_selector = int(p)
                    except ValueError:
                        pass

            loop = asyncio.get_event_loop()

            if seq_selector is None:
                # Mode 1: Overview — list all sequences with est. no-reply counts
                await send_message("🔄 Loading Outreach sequences...")
                result = await loop.run_in_executor(
                    None, district_prospector.get_sequence_reengagement_overview)
                if not result.get("success"):
                    await send_message(f"⚠️ {result.get('error', 'Unknown error')}")
                else:
                    _last_reengagement_sequences = result.get("sequences", [])
                    output = district_prospector.format_reengagement_overview(result)
                    await send_message(output)
            else:
                # Mode 2: Scan specific sequence
                # Resolve: <=100 = index into last overview, >100 = direct sequence ID
                if seq_selector <= 100:
                    if not _last_reengagement_sequences:
                        await send_message("Run `/prospect_reengagement` first to see available sequences.")
                        return
                    idx = seq_selector - 1
                    if idx < 0 or idx >= len(_last_reengagement_sequences):
                        await send_message(f"Invalid index. Choose 1-{len(_last_reengagement_sequences)}.")
                        return
                    sequence_id = _last_reengagement_sequences[idx]["id"]
                else:
                    sequence_id = seq_selector

                await send_message(f"🔄 Scanning sequence {sequence_id} for {segment} prospects...")
                result = await loop.run_in_executor(
                    None, district_prospector.scan_sequence_for_reengagement,
                    sequence_id, segment, None)
                if not result.get("success"):
                    await send_message(f"⚠️ {result.get('error', 'Unknown error')}")
                else:
                    output = district_prospector.format_reengagement_scan(result)
                    await send_message(output)
                    # Set _last_prospect_batch for /prospect_approve
                    candidates = result.get("candidates", [])
                    if candidates:
                        _last_prospect_batch = candidates
        except Exception as e:
            await send_message(f"Re-engagement error: {e}")
        return

    elif user_text.lower() in ["/prospect_cold_requests", "/cold_requests", "/c4"]:
        async def _run_c4_scan():
            """Run C4 scan as a background task so it doesn't block the event loop."""
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, district_prospector.suggest_cold_license_requests)
                if result.get("error") and result.get("new_added", 0) == 0:
                    await send_message(f"⚠️ C4 scan error: {result['error']}")
                else:
                    lines = [f"🔍 *Cold License Request Scan Complete*\n"]
                    lines.append(f"Scanned *{result.get('total_scanned', 0)}* unique prospects across 3 sequences\n")
                    lines.append(f"✅ *{result['new_added']}* new cold license request targets added")
                    if result.get("pricing_sent"):
                        lines.append(f"💰 {result['pricing_sent']} had pricing sent (excluded)")
                    if result.get("has_opp"):
                        lines.append(f"📋 {result['has_opp']} have existing opps (excluded)")
                    if result.get("already_active"):
                        lines.append(f"🏢 {result['already_active']} are active customers (excluded)")
                    if result.get("already_known"):
                        lines.append(f"📌 {result['already_known']} already in queue (excluded)")
                    if result.get("student_emails"):
                        lines.append(f"🎓 {result['student_emails']} student emails (excluded)")
                    if result.get("international"):
                        lines.append(f"🌍 {result['international']} international (excluded)")
                    if result.get("out_of_territory"):
                        lines.append(f"🗺 {result['out_of_territory']} out of territory (excluded)")
                    if result.get("claude_inferred"):
                        lines.append(f"🤖 {result['claude_inferred']} locations inferred by Claude")
                    if result.get("pricing_bulk_detected"):
                        lines.append(f"📧 {result['pricing_bulk_detected']} pricing emails detected (bulk scan)")
                    if result.get("estimated_cost"):
                        lines.append(f"\n💲 Est. API cost: ${result['estimated_cost']:.2f} ({result.get('api_calls', 0)} Claude calls)")
                    lines.append(f"\n📋 Check the *C4 Audit* tab in your Google Sheet to spot-check exclusions.")
                    await send_message("\n".join(lines))
            except Exception as e:
                await send_message(f"C4 scan error: {e}")

        await send_message("🔍 Scanning Outreach license request sequences for cold prospects...\nThis runs in the background — I'll send results when done (~10 min).")
        asyncio.create_task(_run_c4_scan())
        return

    elif user_text.lower() in ["/fix_queue", "/migrate_queue"]:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, district_prospector.migrate_prospect_columns
            )
            if result.get("errors"):
                await send_message(f"⚠️ Migration error: {result['errors']}")
            else:
                await send_message(
                    f"✅ Prospecting Queue columns fixed.\n"
                    f"Migrated: *{result['migrated']}* rows\n"
                    f"Already correct: *{result['already_correct']}* rows\n"
                    f"Total: *{result['total']}* rows"
                )
        except Exception as e:
            await send_message(f"Migration error: {e}")
        return

    elif user_text.lower() in ["/cleanup_queue", "/clean_queue"]:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, district_prospector.cleanup_prospect_queue
            )
            if result.get("errors"):
                await send_message(f"⚠️ Cleanup error: {result['errors']}")
            else:
                await send_message(
                    f"✅ Prospecting Queue cleaned up.\n"
                    f"Before: *{result['total_before']}* rows\n"
                    f"After: *{result['total_after']}* rows\n"
                    f"Removed invalid strategy: *{result['removed_invalid']}*\n"
                    f"Removed duplicates: *{result['removed_duplicate']}*"
                )
        except Exception as e:
            await send_message(f"Cleanup error: {e}")
        return

    elif user_text.lower() in ["/c4_clear", "/clear_c4", "/clear_cold_requests"]:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, district_prospector.clear_by_strategy, "cold_license_request"
            )
            await send_message(
                f"🗑 Cleared *{result['cleared']}* cold license request entries.\n"
                f"Queue: {result['total_before']} → {result['total_after']} entries remaining."
            )
        except Exception as e:
            await send_message(f"Clear error: {e}")
        return

    elif user_text.lower() == "/prospect_clear":
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, district_prospector.clear_queue)
            _last_prospect_batch = []
            await send_message("Prospecting queue cleared.")
        except Exception as e:
            await send_message(f"Clear error: {e}")
        return

    elif user_text.lower() == "/reprioritize_pending":
        try:
            await send_message("🔧 Reprioritizing pending queue rows (Session 52 migration)...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, district_prospector.reprioritize_pending
            )
            lines = [
                "✅ *Reprioritize complete*",
                "",
                f"Scanned: {result.get('total_scanned', 0)}",
                f"Updated: {result.get('updated', 0)}",
                f"Unmatched: {result.get('unmatched', 0)}",
            ]
            bs = result.get("by_strategy", {}) or {}
            if bs:
                lines.append("")
                lines.append("*By strategy:*")
                for strat, counts in sorted(bs.items()):
                    lines.append(
                        f"  • {strat}: {counts.get('matched', 0)} matched, "
                        f"{counts.get('unmatched', 0)} unmatched"
                    )
            errs = result.get("errors", []) or []
            if errs:
                lines.append("")
                lines.append(f"⚠️ {len(errs)} errors:")
                for e in errs[:5]:
                    lines.append(f"  • {e[:120]}")
            await send_message("\n".join(lines))
        except Exception as e:
            await send_message(f"Reprioritize error: {e}")
        return

    elif user_text.lower() in ["/prospect_all", "prospect all", "show all prospects"]:
        try:
            loop = asyncio.get_event_loop()
            all_prospects = await loop.run_in_executor(None, district_prospector.get_all_prospects)
            if not all_prospects:
                await send_message("Prospecting queue is empty. Use `/prospect_discover [state]` or `/prospect_upward` to populate it.")
                return
            await send_message(district_prospector.format_all_for_telegram(all_prospects))
        except Exception as e:
            await send_message(f"Queue view error: {e}")
        return

    elif user_text.lower() in ["/prospect", "/prospects", "prospect", "show prospects",
                                "prospect queue", "prospecting queue"]:
        try:
            loop = asyncio.get_event_loop()
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if not pending:
                await send_message("No pending districts. Use `/prospect_discover [state]` or `/prospect_upward` to find some.")
                return
            _last_prospect_batch = pending
            await send_message(district_prospector.format_batch_for_telegram(pending))
        except Exception as e:
            await send_message(f"Prospect queue error: {e}")
        return

    elif _pending_approve_force and user_text.lower() in ["yes", "approve anyway", "confirm", "continue", "proceed"]:
        districts_to_force = _pending_approve_force
        _pending_approve_force = []
        try:
            names = [d.get("Account Name", d.get("District Name", "?")) for d in districts_to_force]
            await send_message(f"✅ Approved {len(districts_to_force)} district(s) anyway: {', '.join(names)}\nQueuing research...")
            for d in districts_to_force:
                district_prospector.mark_researching(d.get("Name Key", ""))
                await research_queue.enqueue(
                    district_name=d.get("Account Name", d.get("District Name", "")),
                    state=d.get("State", ""),
                    progress_callback=_on_research_progress,
                    completion_callback=lambda result, prospect=d: asyncio.ensure_future(
                        _on_prospect_research_complete(result, prospect)
                    ),
                )
        except Exception as e:
            await send_message(f"Force-approve error: {e}")
        return

    elif _pending_approve_force and user_text.lower() in ["no", "skip", "cancel"]:
        skipped_names = [d.get("Account Name", d.get("District Name", "?")) for d in _pending_approve_force]
        _pending_approve_force = []
        await send_message(f"Skipped: {', '.join(skipped_names)}. No research queued.")
        return

    elif _pending_draft and any(
        user_text.lower().startswith(t) for t in ["looks good", "save it", "save to gmail", "approved", "use this"]
    ):
        result = await execute_tool("save_draft_to_gmail", {
            "to": _pending_draft.get("to", ""),
            "subject": _pending_draft.get("subject", ""),
            "body": _pending_draft.get("body", ""),
        })
        await send_message(result)
        return

    elif _pending_draft and user_text.lower().startswith("add email:"):
        email_addr = user_text[len("add email:"):].strip()
        _pending_draft["to"] = email_addr
        await send_message(f"✅ Recipient set to `{email_addr}`. Say *looks good* to save.")
        return

    # ── Todo list commands ───────────────────────────────────────────────────

    elif user_text.lower() in ["/todos", "/todo", "todos", "todo list", "my todos", "show todos"]:
        try:
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, todo_manager.get_all_todos, True)
            await send_message(todo_manager.format_todos_for_telegram(items))
        except Exception as e:
            await send_message(f"Todo error: {e}")
        return

    elif user_text.lower().startswith("add:") or user_text.lower().startswith("todo:"):
        prefix = "add:" if user_text.lower().startswith("add:") else "todo:"
        task_text = user_text[len(prefix):].strip()
        if not task_text:
            await send_message("What do you want to add? e.g. `add: Follow up with Austin ISD`")
            return
        # Parse optional priority: "add: call Jennifer !high" or "add: call Jennifer (high)"
        priority = "medium"
        for p in ["high", "medium", "low"]:
            if f"!{p}" in task_text.lower() or f"({p})" in task_text.lower():
                priority = p
                task_text = re.sub(rf'\s*[!(]{p}[)]?\s*', '', task_text, flags=re.IGNORECASE).strip()
                break
        try:
            loop = asyncio.get_event_loop()
            item = await loop.run_in_executor(None, todo_manager.add_todo, task_text, priority)
            icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(priority, "🟡")
            await send_message(f"✅ Added #{item['ID']}: {icon} {task_text}")
        except Exception as e:
            await send_message(f"Add error: {e}")
        return

    elif user_text.lower().startswith("done:") or user_text.lower().startswith("done "):
        prefix = "done:" if user_text.lower().startswith("done:") else "done "
        done_text = user_text[len(prefix):].strip()
        if not done_text:
            await send_message("What did you finish? e.g. `done: Austin follow-up` or `done: #3`")
            return
        try:
            loop = asyncio.get_event_loop()
            # Check if it's an ID reference like "#3" or "3"
            id_match = re.match(r'^#?(\d+)$', done_text.strip())
            if id_match:
                result = await loop.run_in_executor(None, todo_manager.complete_todo, int(id_match.group(1)))
            else:
                result = await loop.run_in_executor(None, todo_manager.complete_todo_by_match, done_text)
            if "error" in result:
                await send_message(f"⚠️ {result['error']}")
            else:
                await send_message(f"✅ Done! Checked off #{result['ID']}: {result['Task']}")
        except Exception as e:
            await send_message(f"Done error: {e}")
        return

    elif user_text.lower() in ["/todo_clear", "/clear_todos", "clear todos", "clear completed todos"]:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, todo_manager.clear_completed)
            await send_message(f"🗑 Cleared {result['cleared']} completed items. {result['remaining']} open items remain.")
        except Exception as e:
            await send_message(f"Clear error: {e}")
        return

    elif user_text.lower().startswith("/todo_remove"):
        id_text = user_text[len("/todo_remove"):].strip().lstrip("#")
        if not id_text.isdigit():
            await send_message("Usage: `/todo_remove #3` or `/todo_remove 3`")
            return
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, todo_manager.remove_todo, int(id_text))
            if "error" in result:
                await send_message(f"⚠️ {result['error']}")
            else:
                await send_message(f"🗑 Removed todo #{id_text}")
        except Exception as e:
            await send_message(f"Remove error: {e}")
        return

    # ── Signal intelligence commands ─────────────────────────────────────────

    elif user_text.lower() in ["/signals", "signals", "show signals", "hot signals"]:
        try:
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, signal_processor.format_hot_signals, 5, "", True)
            all_sigs = await loop.run_in_executor(
                None, signal_processor.get_active_signals, "", "district", "new,surfaced")
            _last_signal_batch = [s for s in all_sigs
                                  if s.get("State", "").upper() in signal_processor.TERRITORY_STATES_WITH_CA]
            await send_message(output)
        except Exception as e:
            await send_message(f"Signal error: {e}")
        return

    elif user_text.lower().startswith("/signals "):
        args = user_text[len("/signals "):].strip()
        try:
            loop = asyncio.get_event_loop()
            if args.lower() == "all":
                output = await loop.run_in_executor(None, signal_processor.format_hot_signals, 20, "")
            elif args.lower() == "new":
                sigs = await loop.run_in_executor(
                    None, signal_processor.get_active_signals, "", "district", "new")
                output = signal_processor.format_hot_signals(20, "") if sigs else "No new signals."
            elif len(args) == 2 and args.upper().isalpha():
                output = await loop.run_in_executor(
                    None, signal_processor.format_hot_signals, 20, args.upper())
            else:
                output = await loop.run_in_executor(None, signal_processor.format_hot_signals, 10, "")
            _last_signal_batch = await loop.run_in_executor(
                None, signal_processor.get_active_signals, "", "district", "new,surfaced")
            await send_message(output)
        except Exception as e:
            await send_message(f"Signal error: {e}")
        return

    elif user_text.lower().startswith("/signal_info"):
        idx_text = user_text[len("/signal_info"):].strip()
        try:
            idx = int(idx_text) - 1
            if not _last_signal_batch or idx < 0 or idx >= len(_last_signal_batch):
                await send_message("Run `/signals` first to load the signal list.")
                return
            sig = _last_signal_batch[idx]
            # Find related signals for same district
            district = sig.get("District", "")
            related = [s for s in _last_signal_batch if s.get("District") == district and s.get("ID") != sig.get("ID")] if district else []
            output = signal_processor.format_signal_detail(sig, related)
            await send_message(output)
        except (ValueError, IndexError):
            await send_message("Usage: `/signal_info 1` (number from `/signals` list)")
        except Exception as e:
            await send_message(f"Signal info error: {e}")
        return

    elif user_text.lower().startswith("/signal_act"):
        idx_text = user_text[len("/signal_act"):].strip()
        try:
            idx = int(idx_text) - 1
            if not _last_signal_batch or idx < 0 or idx >= len(_last_signal_batch):
                await send_message("Run `/signals` first to load the signal list.")
                return
            sig = _last_signal_batch[idx]
            district = sig.get("District", "")
            state = sig.get("State", "")
            cust_status = sig.get("Customer Status", "new")

            if cust_status == "active":
                await send_message(
                    f"⚠️ {district} ({state}) is already an active account. "
                    f"This signal could support an upsell conversation.\n"
                    f"Want me to draft talking points? (reply 'yes' or skip)")
                return

            if cust_status == "prospect":
                await send_message(
                    f"ℹ️ {district} ({state}) is already in the Prospecting Queue. "
                    f"Adding signal context to notes.")

            # Mark signal as acted
            loop = asyncio.get_event_loop()
            signal_id = sig.get("ID", "")
            await loop.run_in_executor(None, signal_processor.update_signal_status, signal_id, "acted")

            # Update Pipeline Link on the signal
            if signal_id:
                try:
                    await loop.run_in_executor(
                        None, signal_processor.link_signal_to_prospect,
                        signal_id, district)
                except Exception:
                    pass  # Non-fatal

            # Add to Prospecting Queue with signal attribution
            headline = sig.get("Headline", "")
            dollar = sig.get("Dollar Amount", "")
            sig_type = sig.get("Signal Type", "")
            notes = f"Signal: {sig_type} — {headline}"
            if dollar:
                notes += f" ({dollar})"

            # Map signal type to a prospecting strategy (falls back to "trigger")
            strategy = _SIGNAL_TYPE_TO_STRATEGY.get(
                (sig_type or "").strip().lower(), "trigger"
            )

            # Look up district enrollment so priority scales correctly
            enrollment = territory_data.lookup_district_enrollment(district, state)

            add_fn = partial(
                district_prospector.add_district,
                district, state, notes, strategy, "signal", signal_id,
                est_enrollment=enrollment,
            )
            result = await loop.run_in_executor(None, add_fn)

            await send_message(
                f"✅ {district} ({state}) queued for research.\n"
                f"Strategy: {strategy} | Signal: {signal_id} ({sig_type})\n"
                f"I'll notify you when the sequence draft is ready.")
        except (ValueError, IndexError):
            await send_message("Usage: `/signal_act 1` (number from `/signals` list)")
        except Exception as e:
            await send_message(f"Signal act error: {e}")
        return

    elif user_text.lower().startswith("/signal_dismiss"):
        idx_text = user_text[len("/signal_dismiss"):].strip()
        try:
            idx = int(idx_text) - 1
            if not _last_signal_batch or idx < 0 or idx >= len(_last_signal_batch):
                await send_message("Run `/signals` first to load the signal list.")
                return
            sig = _last_signal_batch[idx]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, signal_processor.update_signal_status, sig.get("ID", ""), "expired")
            await send_message(f"Dismissed: {sig.get('District', 'Unknown')} ({sig.get('Signal Type', '')})")
        except (ValueError, IndexError):
            await send_message("Usage: `/signal_dismiss 1`")
        except Exception as e:
            await send_message(f"Signal dismiss error: {e}")
        return

    elif user_text.lower().startswith("/signal_enrich"):
        idx_text = user_text[len("/signal_enrich"):].strip()
        try:
            idx = int(idx_text) - 1
            if not _last_signal_batch or idx < 0 or idx >= len(_last_signal_batch):
                await send_message("Run `/signals` first to load the signal list.")
                return
            sig = _last_signal_batch[idx]
            district = sig.get("District", "Unknown")
            await send_message(f"🔍 Enriching {district}... (web research + relevance analysis)")
            loop = asyncio.get_event_loop()
            enriched = await loop.run_in_executor(None, signal_processor.enrich_signal, sig)
            output = signal_processor.format_enriched_signal(enriched)
            await send_message(output)
        except (ValueError, IndexError):
            await send_message("Usage: `/signal_enrich 1` (number from `/signals` list)")
        except Exception as e:
            await send_message(f"Enrich error: {e}")
        return

    elif user_text.lower() in ["/signal_jobs", "signal jobs", "scan jobs"]:
        await send_message("💼 Scanning job postings across territory states...")
        try:
            loop = asyncio.get_event_loop()
            job_signals = await loop.run_in_executor(
                None, signal_processor.scan_job_postings, None, 168, 15,
                lambda msg: None)  # suppress progress for Telegram
            if job_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, job_signals)
                lines = [f"💼 *Job Scan Complete* — {len(job_signals)} CS/CTE/STEM postings found\n"]
                for i, sig in enumerate(job_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:50]
                    lines.append(f"  {i}. {dist} ({state}) — {headline}")
                if len(job_signals) > 10:
                    lines.append(f"\n  ... and {len(job_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No K-12 CS/CTE/STEM job postings found this week.")
        except Exception as e:
            await send_message(f"Job scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_bonds", "signal bonds", "scan bonds", "scan ballotpedia"]:
        await send_message("🗳 Scanning Ballotpedia for bond measures...")
        try:
            loop = asyncio.get_event_loop()
            ballot_signals = await loop.run_in_executor(
                None, signal_processor.scan_ballotpedia, None)
            if ballot_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, ballot_signals)
                lines = [f"🗳 *Ballotpedia Scan Complete* — {len(ballot_signals)} territory bond measures\n"]
                for i, sig in enumerate(ballot_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:70]
                    dollar = sig.get("dollar_amount", "")
                    dollar_str = f" {dollar}" if dollar else ""
                    lines.append(f"  {i}. {dist} ({state}){dollar_str} — {headline}")
                if len(ballot_signals) > 10:
                    lines.append(f"\n  ... and {len(ballot_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No territory bond measures found on Ballotpedia.")
        except Exception as e:
            await send_message(f"Ballotpedia scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_board", "signal board", "scan board", "scan boarddocs"]:
        await send_message("🏛 Scanning BoardDocs agendas... This may take a few minutes.")
        try:
            loop = asyncio.get_event_loop()
            board_signals = await loop.run_in_executor(
                None, signal_processor.scan_board_meetings, 30, None)
            if board_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, board_signals)
                lines = [f"🏛 *BoardDocs Scan Complete* — {len(board_signals)} signals from "
                         f"{len(signal_processor.BOARDDOCS_DISTRICTS)} districts\n"]
                for i, sig in enumerate(board_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    stype = sig.get("signal_type", "")
                    headline = sig.get("headline", "")[:80]
                    dollar = sig.get("dollar_amount", "")
                    dollar_str = f" {dollar}" if dollar else ""
                    lines.append(f"  {i}. [{stype}] {dist} ({state}){dollar_str} — {headline}")
                if len(board_signals) > 10:
                    lines.append(f"\n  ... and {len(board_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No buying signals found in recent board meeting agendas.")
        except Exception as e:
            await send_message(f"BoardDocs scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_rss", "signal rss", "scan rss"]:
        await send_message("📡 Scanning RSS feeds...")
        try:
            loop = asyncio.get_event_loop()
            rss_signals = await loop.run_in_executor(
                None, signal_processor.process_rss_feeds, "", None)
            if rss_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, rss_signals)
                territory = [s for s in rss_signals
                             if s.get("state", "").upper() in signal_processor.TERRITORY_STATES_WITH_CA
                             and s.get("scope") == "district"]
                lines = [f"📡 *RSS Scan Complete* — {len(rss_signals)} articles from {len(signal_processor.RSS_FEEDS)} feeds\n"]
                if territory:
                    lines.append(f"🎯 Territory signals: {len(territory)}")
                    for i, sig in enumerate(territory[:8], 1):
                        dist = sig.get("district", "")
                        state = sig.get("state", "")
                        headline = sig.get("headline", "")[:50]
                        lines.append(f"  {i}. {dist} ({state}) — {headline}")
                non_mi = [s for s in rss_signals if s.get("signal_type") != "market_intel"]
                if non_mi and not territory:
                    lines.append(f"\nClassified signals: {len(non_mi)} (non-market-intel)")
                    for i, sig in enumerate(non_mi[:5], 1):
                        headline = sig.get("headline", "")[:60]
                        stype = sig.get("signal_type", "")
                        lines.append(f"  {i}. [{stype}] {headline}")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No articles found from RSS feeds.")
        except Exception as e:
            await send_message(f"RSS scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_leadership", "signal leadership", "scan leadership"]:
        await send_message("👔 Scanning for superintendent changes...")
        try:
            loop = asyncio.get_event_loop()
            leadership_signals = await loop.run_in_executor(
                None, signal_processor.scan_leadership_changes, None, None)
            if leadership_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, leadership_signals)
                lines = [f"👔 *Leadership Scan Complete* — {len(leadership_signals)} changes found\n"]
                for i, sig in enumerate(leadership_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    cust = sig.get("customer_status", "")
                    risk = "⚠️ " if cust == "active" else ""
                    lines.append(f"  {risk}{i}. {dist} ({state}) — {headline}")
                if len(leadership_signals) > 10:
                    lines.append(f"\n  ... and {len(leadership_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No superintendent changes found.")
        except Exception as e:
            await send_message(f"Leadership scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_rfp", "signal rfp", "scan rfp", "scan rfps"]:
        await send_message("📋 Scanning for CS/STEM RFP opportunities...")
        try:
            loop = asyncio.get_event_loop()
            rfp_signals = await loop.run_in_executor(
                None, signal_processor.scan_rfp_opportunities, None, None)
            if rfp_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, rfp_signals)
                lines = [f"📋 *RFP Scan Complete* — {len(rfp_signals)} opportunities found\n"]
                for i, sig in enumerate(rfp_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    lines.append(f"  {i}. {dist} ({state}) — {headline}")
                if len(rfp_signals) > 10:
                    lines.append(f"\n  ... and {len(rfp_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CodeCombat-relevant RFP opportunities found.")
        except Exception as e:
            await send_message(f"RFP scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_legislation", "signal legislation", "scan legislation"]:
        await send_message("📜 Scanning for CS/STEM education legislation...")
        try:
            loop = asyncio.get_event_loop()
            leg_signals = await loop.run_in_executor(
                None, signal_processor.scan_legislative_signals, None, None)
            if leg_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, leg_signals)
                lines = [f"📜 *Legislative Scan Complete* — {len(leg_signals)} signals found\n"]
                for i, sig in enumerate(leg_signals[:10], 1):
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    urgency = sig.get("urgency", "")
                    tag = "🔴" if urgency == "urgent" else "🟡" if urgency == "time_sensitive" else ""
                    lines.append(f"  {tag}{i}. ({state}) — {headline}")
                if len(leg_signals) > 10:
                    lines.append(f"\n  ... and {len(leg_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CS/STEM education legislation found.")
        except Exception as e:
            await send_message(f"Legislative scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_grants", "signal grants", "scan grants"]:
        await send_message("💰 Scanning for CS/STEM grant-funded districts...")
        try:
            loop = asyncio.get_event_loop()
            grant_signals = await loop.run_in_executor(
                None, signal_processor.scan_grant_opportunities, None, None)
            if grant_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, grant_signals)
                lines = [f"💰 *Grant Scan Complete* — {len(grant_signals)} signals found\n"]
                for i, sig in enumerate(grant_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    dollar = sig.get("dollar_amount", "")
                    amount_tag = f" {dollar}" if dollar else ""
                    lines.append(f"  {i}. {dist} ({state}){amount_tag} — {headline}")
                if len(grant_signals) > 10:
                    lines.append(f"\n  ... and {len(grant_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CS/STEM grant signals found.")
        except Exception as e:
            await send_message(f"Grant scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_competitors", "signal competitors", "scan competitors"]:
        # F2: Competitor Displacement Scanner
        await send_message("🎯 Scanning for districts using competitor platforms (Tynker, CodeHS, Replit, Khan CS, Code.org, Tinkercad)...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, signal_processor.scan_competitor_displacement, None, None)
            signals = result.get("signals", [])
            queued = result.get("queued", [])
            customer_intel = result.get("customer_intel", [])
            raw = result.get("raw_count", 0)

            if signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, signals)
            else:
                write_result = {"written": 0, "skipped": 0}

            if not signals and not queued:
                await send_message(f"🎯 Competitor scan: 0 results (raw extracted: {raw}).")
                return

            lines = [
                f"🎯 *Competitor Displacement Scan*",
                f"Raw extracted: {raw}",
                f"Signals written: {write_result['written']} (deduped: {write_result['skipped']})",
                f"Auto-queued (HIGH confidence): {len(queued)}",
            ]
            if customer_intel:
                lines.append(f"Customer intel (existing accounts): {len(customer_intel)}")
            if queued:
                lines.append("\n*Queued as displacement prospects:*")
                for i, item in enumerate(queued[:10], 1):
                    lines.append(f"  {i}. {item}")
                if len(queued) > 10:
                    lines.append(f"  ... and {len(queued) - 10} more")
                lines.append("\n_Approve in batches with `/prospect_approve` so research catches up._")
            await send_message("\n".join(lines))
        except Exception as e:
            await send_message(f"Competitor scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_funding", "signal funding", "scan funding", "/signal_cs_funding"]:
        # F4: State CS Funding Award Scanner
        await send_message("💵 Scanning state DOEs for CS funding awards...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, signal_processor.scan_cs_funding_awards, None, None)
            signals = result.get("signals", [])
            queued = result.get("queued", [])
            customer_intel = result.get("customer_intel", [])
            raw = result.get("raw_count", 0)

            if signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, signals)
            else:
                write_result = {"written": 0, "skipped": 0}

            if not signals and not queued:
                await send_message(f"💵 CS funding scan: 0 results (raw extracted: {raw}).")
                return

            lines = [
                f"💵 *CS Funding Scan*",
                f"Raw extracted: {raw}",
                f"Signals written: {write_result['written']} (deduped: {write_result['skipped']})",
                f"Auto-queued (HIGH confidence): {len(queued)}",
            ]
            if customer_intel:
                lines.append(f"Customer intel (existing accounts): {len(customer_intel)}")
            if queued:
                lines.append("\n*Queued as prospects:*")
                for i, dist in enumerate(queued[:10], 1):
                    lines.append(f"  {i}. {dist}")
                if len(queued) > 10:
                    lines.append(f"  ... and {len(queued) - 10} more")
                lines.append("\n_Approve in batches of 5-10 with `/prospect_approve` so research catches up._")
            await send_message("\n".join(lines))
        except Exception as e:
            await send_message(f"CS funding scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_budget", "signal budget", "scan budget"]:
        await send_message("📊 Scanning for CS/STEM budget and procurement signals...")
        try:
            loop = asyncio.get_event_loop()
            budget_signals = await loop.run_in_executor(
                None, signal_processor.scan_budget_cycle_signals, None, None)
            if budget_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, budget_signals)
                lines = [f"📊 *Budget Scan Complete* — {len(budget_signals)} signals found\n"]
                for i, sig in enumerate(budget_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    dollar = sig.get("dollar_amount", "")
                    amount_tag = f" {dollar}" if dollar else ""
                    lines.append(f"  {i}. {dist} ({state}){amount_tag} — {headline}")
                if len(budget_signals) > 10:
                    lines.append(f"\n  ... and {len(budget_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CS/STEM budget/procurement signals found.")
        except Exception as e:
            await send_message(f"Budget scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_algebra", "signal algebra", "scan algebra"]:
        await send_message("🔢 Scanning for math/algebra curriculum targets (AI Algebra campaign)...")
        try:
            loop = asyncio.get_event_loop()
            alg_signals = await loop.run_in_executor(
                None, signal_processor.scan_algebra_targets, None, None)
            if alg_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, alg_signals)
                lines = [f"🔢 *AI Algebra Campaign Scan* — {len(alg_signals)} targets found\n"]
                for i, sig in enumerate(alg_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    lines.append(f"  {i}. {dist} ({state}) — {headline}")
                if len(alg_signals) > 10:
                    lines.append(f"\n  ... and {len(alg_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No math/algebra curriculum targets found.")
        except Exception as e:
            await send_message(f"Algebra scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_cyber", "signal cyber", "scan cybersecurity"]:
        await send_message("🛡️ Scanning for CTE cybersecurity program targets (pre-launch pipeline)...")
        try:
            loop = asyncio.get_event_loop()
            cyber_signals = await loop.run_in_executor(
                None, signal_processor.scan_cybersecurity_targets, None, None)
            if cyber_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, cyber_signals)
                lines = [f"🛡️ *Cybersecurity Campaign Scan* — {len(cyber_signals)} targets found\n"]
                for i, sig in enumerate(cyber_signals[:10], 1):
                    dist = sig.get("district", "")
                    state = sig.get("state", "")
                    headline = sig.get("headline", "")[:80]
                    lines.append(f"  {i}. {dist} ({state}) — {headline}")
                if len(cyber_signals) > 10:
                    lines.append(f"\n  ... and {len(cyber_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CTE cybersecurity program targets found.")
        except Exception as e:
            await send_message(f"Cybersecurity scan failed: {e}")
        return

    elif user_text.lower().startswith("/signal_roles") or user_text.lower() in ["signal roles", "scan roles"]:
        parts = user_text.strip().split()
        state_arg = None
        for p in parts[1:]:
            if len(p) == 2 and p.upper().isalpha():
                state_arg = [p.upper()]
                break
        await send_message("👤 Scanning for CS/CTE/STEM leaders (~$2.50, 48 Serper queries)...")
        try:
            loop = asyncio.get_event_loop()
            role_signals = await loop.run_in_executor(
                None, signal_processor.scan_role_targets, state_arg, None)
            if role_signals:
                write_result = await loop.run_in_executor(
                    None, signal_processor.write_signals, role_signals)
                lines = [f"👤 *Role Scan Complete* — {len(role_signals)} leaders found\n"]
                for i, sig in enumerate(role_signals[:10], 1):
                    headline = sig.get("headline", "")[:80]
                    lines.append(f"  {i}. {headline}")
                if len(role_signals) > 10:
                    lines.append(f"\n  ... and {len(role_signals) - 10} more")
                lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
                await send_message("\n".join(lines))
            else:
                await send_message("No CS/CTE/STEM leaders found.")
        except Exception as e:
            await send_message(f"Role scan failed: {e}")
        return

    elif user_text.lower().startswith(("/scan_compliance", "/compliance_gap", "scan compliance")):
        # F9: CS graduation compliance gap scanner (PDF pilot)
        parts = user_text.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            await send_message(
                "📑 Usage: `/scan_compliance [state]` — pilot scope: CA, IL, MA. "
                "E.g. `/scan_compliance CA` (cost: ~$0.50-$2.00 per scan)"
            )
            return
        state_arg = parts[1].strip().upper()
        await send_message(
            f"📑 Running F9 compliance gap scan on {state_arg}... "
            f"(Serper → PDF download → Claude Sonnet extraction, ~2-5 min)"
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, compliance_gap_scanner.scan_compliance_gaps, state_arg, 5
            )
            output = compliance_gap_scanner.format_scan_result_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Compliance gap scan failed: {e}")
        return

    elif user_text.lower().startswith(("/discover_private_schools", "/discover_private", "discover private schools")):
        # F8: Serper-based private school discovery
        parts = user_text.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            await send_message(
                "🏫 Usage: `/discover_private_schools [state]` — e.g. `/discover_private_schools TX`"
            )
            return
        state_arg = parts[1].strip()
        await send_message(f"🏫 Discovering private schools in {state_arg}...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, private_schools.discover_private_schools, state_arg, 25
            )
            output = private_schools.format_discovery_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Private school discovery failed: {e}")
        return

    elif user_text.lower().startswith(("/prospect_private_networks", "/prospect_dioceses", "queue private networks")):
        # F8: queue static seed of diocesan and chain networks
        parts = user_text.strip().split(None, 1)
        state_arg = parts[1].strip() if len(parts) > 1 else None
        await send_message(
            f"⛪ Queueing private school networks{' for ' + state_arg.upper() if state_arg else ' (all territory)'}..."
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, private_schools.queue_private_school_networks, state_arg
            )
            output = private_schools.format_networks_queue_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Private school network queueing failed: {e}")
        return

    elif user_text.lower().startswith(("/list_cte_centers", "list cte centers", "show cte centers")):
        # F7: read-only CTE center list
        parts = user_text.strip().split(None, 1)
        state_arg = parts[1].strip() if len(parts) > 1 else None
        try:
            output = cte_prospector.list_cte_centers_for_telegram(state_arg)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ CTE center list failed: {e}")
        return

    elif user_text.lower().startswith(("/prospect_cte_centers", "/prospect_cte", "queue cte centers")):
        # F7: queue CTE centers as prospects
        parts = user_text.strip().split(None, 1)
        state_arg = parts[1].strip() if len(parts) > 1 else None
        await send_message(
            f"🛠 Queueing CTE centers{' for ' + state_arg.upper() if state_arg else ' (all territory)'}..."
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, cte_prospector.queue_cte_centers, state_arg
            )
            output = cte_prospector.format_queue_result_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ CTE center queueing failed: {e}")
        return

    elif user_text.lower().startswith(("/list_charter_cmos", "list charter cmos", "show charter cmos")):
        # F6: read-only seed list view
        parts = user_text.strip().split(None, 1)
        state_arg = parts[1].strip() if len(parts) > 1 else None
        try:
            output = charter_prospector.list_charter_cmos_for_telegram(state_arg)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Charter CMO list failed: {e}")
        return

    elif user_text.lower().startswith(("/prospect_charter_cmos", "/prospect_cmos", "queue charter cmos")):
        # F6: queue charter CMOs as prospects
        parts = user_text.strip().split(None, 1)
        state_arg = parts[1].strip() if len(parts) > 1 else None
        await send_message(
            f"🏫 Queueing charter CMOs{' for ' + state_arg.upper() if state_arg else ' (all territory)'}..."
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, charter_prospector.queue_charter_cmos, state_arg
            )
            output = charter_prospector.format_queue_result_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Charter CMO queueing failed: {e}")
        return

    elif user_text.lower().startswith(("/signal_compliance", "/scan_compliance", "compliance scan")):
        # F9: compliance gap scanner (Signals-only pilot — CA/IL/MA)
        # Usage: /signal_compliance CA  (required state, must be in PILOT_STATES)
        parts = user_text.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            pilot = ", ".join(sorted(compliance_gap_scanner.PILOT_STATES))
            await send_message(
                f"📋 Usage: `/signal_compliance [state]` — pilot scope: {pilot}. e.g. `/signal_compliance CA`"
            )
            return
        state_arg = parts[1].strip()
        await send_message(f"📋 Scanning {state_arg.upper()} for compliance gaps (F9 pilot, Signals-only)...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, compliance_gap_scanner.scan_compliance_gaps, state_arg
            )
            output = compliance_gap_scanner.format_scan_result_for_telegram(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Compliance scan failed: {e}")
        return

    elif user_text.lower().startswith(("/discover_coops", "/discover_homeschool", "discover homeschool")):
        # F10: on-demand homeschool co-op discovery
        # Usage: /discover_coops TX  OR  /discover_homeschool_coops Texas
        parts = user_text.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            await send_message(
                "🏠 Usage: `/discover_coops [state]` — e.g. `/discover_coops TX` or `/discover_coops California`"
            )
            return
        state_arg = parts[1].strip()
        await send_message(f"🏠 Discovering homeschool co-ops in {state_arg}...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, signal_processor.discover_homeschool_coops, state_arg, 25
            )
            output = signal_processor.format_homeschool_discovery(result)
            await send_message(output)
        except Exception as e:
            await send_message(f"❌ Homeschool discovery failed: {e}")
        return

    elif user_text.lower() in ["/signal_csta", "signal csta", "csta roster", "scan csta"]:
        # Session 57 BUG 2: F5 daily scanner retired. This command now displays
        # the cached CSTA roster used for F2 enrichment. Refresh manually:
        # python3 scripts/fetch_csta_roster.py
        try:
            import json as _json
            from pathlib import Path as _Path
            root = _Path(__file__).resolve().parent.parent
            path = root / "memory" / "csta_roster.json"
            if not path.exists():
                await send_message(
                    "📚 CSTA roster not built yet. Run "
                    "`python3 scripts/fetch_csta_roster.py` from Claude Code."
                )
                return
            data = _json.loads(path.read_text())
            entries = data.get("entries", [])
            fetched = data.get("fetched_at", "unknown")
            with_district = [e for e in entries if e.get("district")]
            lines = [
                f"🎓 *CSTA Roster* — {len(entries)} entries "
                f"({len(with_district)} with district)",
                f"_Fetched: {fetched}. F5 daily scanner retired Session 57 — "
                f"CSTA is now F2 enrichment. Refresh: "
                f"`scripts/fetch_csta_roster.py`_",
                "",
            ]
            from collections import defaultdict
            by_state = defaultdict(list)
            for e in entries:
                by_state[(e.get("state", "??") or "??").upper()].append(e)
            for st in sorted(by_state.keys()):
                lines.append(f"*{st}* ({len(by_state[st])})")
                for e in by_state[st][:8]:
                    d = e.get("district") or "_no district_"
                    lines.append(
                        f"  • {e.get('name','')} — {e.get('role','')} — {d}"
                    )
                if len(by_state[st]) > 8:
                    lines.append(f"  _…and {len(by_state[st]) - 8} more_")
            msg = "\n".join(lines)
            if len(msg) > 3900:
                msg = msg[:3900].rsplit("\n", 1)[0] + "\n…_(truncated)_"
            await send_message(msg)
        except Exception as e:
            await send_message(f"CSTA roster display failed: {e}")
        return

    elif user_text.lower() in ["/signal_scan", "signal scan", "scan signals"]:
        await send_message("📬 Starting signal scan... This may take a few minutes.")
        try:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(None, signal_processor.process_all_signals, gas)
            output = signal_processor.format_scan_summary(summary)
            await send_message(output)
        except Exception as e:
            await send_message(f"Signal scan failed: {e}")
        return

    elif user_text.lower() in ["/signal_stats", "signal stats"]:
        try:
            loop = asyncio.get_event_loop()
            signals = await loop.run_in_executor(
                None, signal_processor.get_active_signals, "", "", "new,surfaced,acted")
            total = len(signals)
            by_type = {}
            by_state = {}
            for s in signals:
                st = s.get("Signal Type", "unknown")
                by_type[st] = by_type.get(st, 0) + 1
                state = s.get("State", "")
                if state:
                    by_state[state] = by_state.get(state, 0) + 1
            lines = [f"📊 *Signal Stats* ({total} total)\n"]
            lines.append("*By type:*")
            for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")
            lines.append("\n*By state:*")
            for st, c in sorted(by_state.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {st}: {c}")
            await send_message("\n".join(lines))
        except Exception as e:
            await send_message(f"Stats error: {e}")
        return

    # ── Outreach export ─────────────────────────────────────────────────────

    elif user_text.lower().startswith("/export_sequence"):
        search_name = user_text[len("/export_sequence"):].strip()
        if not search_name:
            await send_message("Usage: `/export_sequence [name or partial name]`")
            return
        await send_message(f"📋 Searching for sequence matching \"{search_name}\"...")
        try:
            import tools.outreach_client as outreach_client
            loop = asyncio.get_event_loop()

            # Find matching sequence
            sequences = await loop.run_in_executor(None, outreach_client.get_sequences)
            match = None
            for seq in sequences:
                if search_name.lower() in seq.get("name", "").lower():
                    match = seq
                    break

            if not match:
                await send_message(f"No sequence found matching \"{search_name}\"")
                return

            await send_message(f"Found: **{match['name']}** (ID: {match['id']}). Exporting...")

            # Export full sequence with templates
            seq_info = await loop.run_in_executor(
                None, outreach_client.export_sequence, int(match["id"]))
            markdown = outreach_client.format_sequence_export(seq_info)

            # Write to Google Doc
            gas = get_gas_bridge()
            if gas:
                folder_id = os.environ.get("SEQUENCES_FOLDER_ID", "")
                doc_result = await loop.run_in_executor(
                    None, gas.create_google_doc,
                    f"Export — {match['name']}",
                    markdown,
                    folder_id)
                if doc_result.get("success"):
                    doc_url = doc_result.get("url", "")
                    await send_message(
                        f"✅ Exported **{match['name']}** ({len(seq_info.get('steps', []))} steps)\n\n"
                        f"📄 Google Doc: {doc_url}")
                else:
                    # Fallback: send markdown directly
                    await send_message(f"Doc creation failed. Sending as text...")
                    # Split if too long
                    if len(markdown) > 4000:
                        for i in range(0, len(markdown), 4000):
                            await send_message(markdown[i:i+4000])
                    else:
                        await send_message(markdown)
            else:
                # No GAS — send as text
                if len(markdown) > 4000:
                    for i in range(0, len(markdown), 4000):
                        await send_message(markdown[i:i+4000])
                else:
                    await send_message(markdown)

        except Exception as e:
            await send_message(f"Export failed: {e}")
        return

    # ── CSV upload description (pre-message before file upload) ─────────────
    # Steven can describe what a CSV is before uploading it, e.g.:
    # "this is a list of all the open opps in my pipeline"
    # "uploading my active accounts from Salesforce"
    _csv_intent_check = _parse_csv_intent(user_text)
    if _csv_intent_check:
        file_context = ["csv", "file", "upload", "report", "export", "spreadsheet",
                        "sending", "importing", "here", "this is", "these are", "list of",
                        "data", "my lead", "my contact", "my account", "my pipeline",
                        "my opp", "about to", "going to"]
        if any(fc in user_text.lower() for fc in file_context):
            _pending_csv_intent = _csv_intent_check
            label = _csv_intent_check["label"]
            await send_message(f"👍 Got it — I'll import the next CSV as *{label}*. Send the file whenever you're ready.")
            return

    # Behavioral correction detection
    correction_signals = [
        "stop ", "don't ", "do not ", "always ", "never ", "remember to ",
        "please don't", "i want you to", "from now on", "every time",
        "too long", "too short", "too formal", "too casual",
    ]
    if any(sig in user_text.lower() for sig in correction_signals):
        user_text = (
            user_text
            + "\n\n[If this is a behavioral correction or preference, append [MEMORY_UPDATE: one sentence summary] to your response so it gets saved permanently.]"
        )

    # General ack for task-style messages
    if not _ack_sent and any(
        kw in user_text.lower() for kw in [
            "draft", "research", "sequence", "deck", "train", "brief", "build",
            "create", "generate", "write", "log", "push", "fetch",
        ]
    ):
        await send_message("⏳ Working on it...")
        _ack_sent = True

    # ── Claude processing ──────────────────────────────────────────────────────

    text_response, conversation_history, tool_calls = process_message(
        user_message=user_text,
        history=conversation_history,
        memory=memory,
    )

    if text_response.startswith("❌ Claude API error"):
        if "tool_use" in text_response and "tool_result" in text_response:
            logger.warning("400 tool_use error — clearing conversation history to recover.")
            conversation_history.clear()
        await send_message(text_response)
        return

    # ── Tool execution — ALWAYS append result even if tool throws ─────────────
    tool_results = []
    for tc in tool_calls:
        try:
            result = await execute_tool(tc["tool_name"], tc["tool_input"])
        except Exception as e:
            logger.error(f"Tool '{tc['tool_name']}' raised exception: {e}")
            result = f"❌ Tool error in {tc['tool_name']}: {e}"
        tool_results.append(result)

    # CRITICAL: Every tool_use block MUST have a matching tool_result in the next message.
    if tool_calls and tool_results:
        tool_result_content = [
            {
                "type": "tool_result",
                "tool_use_id": tc["tool_use_id"],
                "content": str(result),
            }
            for tc, result in zip(tool_calls, tool_results)
        ]
        conversation_history.append({
            "role": "user",
            "content": tool_result_content,
        })

    def _clean(msg: str) -> str:
        msg = re.sub(r"\s*\bOn it[.!]*\s*$", "", msg, flags=re.IGNORECASE).strip()
        msg = re.sub(r"\s*Let me know if (you need|there's|you have).*$", "", msg, flags=re.IGNORECASE | re.DOTALL).strip()
        return msg

    if text_response and not tool_calls:
        await send_message(_clean(text_response))
    elif tool_results:
        for r in tool_results:
            if r:
                await send_message(_clean(r))
    else:
        await send_message("👍")


# ── Scheduled messages ─────────────────────────────────────────────────────────

async def send_morning_brief():
    try:
        with open("prompts/morning_brief.md", "r") as f:
            prompt_template = f.read()

        # Phase 6C: inject real activity data from yesterday
        try:
            from datetime import date, timedelta
            yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            data_block = activity_tracker.build_brief_data_block(date_str=yesterday)
            # Inject signal intelligence data
            try:
                signal_block = signal_processor.build_signal_brief_block()
                if signal_block:
                    data_block = f"{data_block}\n\n{signal_block}"
            except Exception as sig_err:
                logger.warning(f"Could not load signal data for morning brief: {sig_err}")
            prompt = f"{data_block}\n\n---\n\n{prompt_template}"
        except Exception as data_err:
            logger.warning(f"Could not load activity data for morning brief: {data_err}")
            prompt = prompt_template

        text, _, _ = process_message(prompt, [], memory)
        await send_message(f"☀️ *Good morning, Steven!*\n\n{text}")

        # Send command cheat sheet as separate message to avoid 4K limit
        await send_message(_COMMAND_CHEAT_SHEET)

        # Show pending prospects if any
        try:
            loop = asyncio.get_event_loop()
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 5)
            if pending:
                await send_message(
                    district_prospector.format_batch_for_telegram(pending, label="Pending Prospects")
                )
        except Exception as pq_err:
            logger.warning(f"Could not load prospect queue for morning brief: {pq_err}")
    except Exception as e:
        logger.error(f"Morning brief failed: {e}")


async def _run_daily_signal_scan():
    """Scheduled daily signal scan at 7:45 AM CST."""
    try:
        scan_gas = get_gas_bridge()
        if not scan_gas:
            logger.error("Daily signal scan: GAS bridge not configured")
            return
        from datetime import date, timedelta
        since = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None, signal_processor.process_new_signals, scan_gas, since)
        if summary.get("written", 0) > 0:
            output = signal_processor.format_scan_summary(summary)
            await send_message(output)
        else:
            logger.info("Daily signal scan: no new signals found")
    except Exception as e:
        logger.error(f"Daily signal scan failed: {e}")
        try:
            # Retry once after 5 minutes
            await asyncio.sleep(300)
            scan_gas = get_gas_bridge()
            if not scan_gas:
                await send_message("⚠️ Signal scan failed: GAS bridge not configured.")
                return
            from datetime import date, timedelta
            since = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None, signal_processor.process_new_signals, scan_gas, since)
            if summary.get("written", 0) > 0:
                output = signal_processor.format_scan_summary(summary)
                await send_message(output)
        except Exception as retry_err:
            logger.error(f"Daily signal scan retry failed: {retry_err}")
            await send_message("⚠️ Signal scan failed. Will retry tomorrow.")


async def _run_leadership_scan():
    """Scheduled weekly leadership scan — Mondays at 8:00 AM CST."""
    try:
        loop = asyncio.get_event_loop()
        signals = await loop.run_in_executor(
            None, signal_processor.scan_leadership_changes, None, None)
        if signals:
            write_result = await loop.run_in_executor(
                None, signal_processor.write_signals, signals)
            lines = [f"👔 *Weekly Leadership Scan* — {len(signals)} changes found\n"]
            for i, sig in enumerate(signals[:10], 1):
                dist = sig.get("district", "")
                state = sig.get("state", "")
                headline = sig.get("headline", "")[:80]
                cust = sig.get("customer_status", "")
                risk = "⚠️ " if cust == "active" else ""
                lines.append(f"  {risk}{i}. {dist} ({state}) — {headline}")
            if len(signals) > 10:
                lines.append(f"\n  ... and {len(signals) - 10} more")
            lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
            await send_message("\n".join(lines))
        else:
            logger.info("Weekly leadership scan: no changes found")
    except Exception as e:
        logger.error(f"Weekly leadership scan failed: {e}")


async def _run_rfp_scan():
    """Scheduled weekly RFP scan — Mondays at 8:15 AM CST."""
    try:
        loop = asyncio.get_event_loop()
        signals = await loop.run_in_executor(
            None, signal_processor.scan_rfp_opportunities, None, None)
        if signals:
            write_result = await loop.run_in_executor(
                None, signal_processor.write_signals, signals)
            lines = [f"📋 *Weekly RFP Scan* — {len(signals)} opportunities found\n"]
            for i, sig in enumerate(signals[:10], 1):
                dist = sig.get("district", "")
                state = sig.get("state", "")
                headline = sig.get("headline", "")[:80]
                lines.append(f"  {i}. {dist} ({state}) — {headline}")
            if len(signals) > 10:
                lines.append(f"\n  ... and {len(signals) - 10} more")
            lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
            await send_message("\n".join(lines))
        else:
            logger.info("Weekly RFP scan: no opportunities found")
    except Exception as e:
        logger.error(f"Weekly RFP scan failed: {e}")


async def _run_legislative_scan():
    """Scheduled monthly legislative scan — first Monday of month at 8:30 AM CST."""
    try:
        loop = asyncio.get_event_loop()
        signals = await loop.run_in_executor(
            None, signal_processor.scan_legislative_signals, None, None)
        if signals:
            write_result = await loop.run_in_executor(
                None, signal_processor.write_signals, signals)
            lines = [f"📜 *Monthly Legislative Scan* — {len(signals)} signals found\n"]
            for i, sig in enumerate(signals[:10], 1):
                state = sig.get("state", "")
                headline = sig.get("headline", "")[:80]
                urgency = sig.get("urgency", "")
                tag = "🔴 " if urgency == "urgent" else "🟡 " if urgency == "time_sensitive" else ""
                lines.append(f"  {tag}{i}. ({state}) — {headline}")
            lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
            await send_message("\n".join(lines))
        else:
            logger.info("Monthly legislative scan: no signals found")
    except Exception as e:
        logger.error(f"Monthly legislative scan failed: {e}")


async def _run_grant_scan():
    """Scheduled monthly grant opportunity scan — first Monday of month at 8:45 AM CST."""
    try:
        loop = asyncio.get_event_loop()
        signals = await loop.run_in_executor(
            None, signal_processor.scan_grant_opportunities, None, None)
        if signals:
            write_result = await loop.run_in_executor(
                None, signal_processor.write_signals, signals)
            lines = [f"💰 *Monthly Grant Scan* — {len(signals)} signals found\n"]
            for i, sig in enumerate(signals[:10], 1):
                dist = sig.get("district", "")
                state = sig.get("state", "")
                headline = sig.get("headline", "")[:80]
                lines.append(f"  {i}. {dist} ({state}) — {headline}")
            lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
            await send_message("\n".join(lines))
        else:
            logger.info("Monthly grant scan: no signals found")
    except Exception as e:
        logger.error(f"Monthly grant scan failed: {e}")


async def _run_budget_scan():
    """Scheduled monthly budget cycle scan — first Monday of month at 9:00 AM CST."""
    try:
        loop = asyncio.get_event_loop()
        signals = await loop.run_in_executor(
            None, signal_processor.scan_budget_cycle_signals, None, None)
        if signals:
            write_result = await loop.run_in_executor(
                None, signal_processor.write_signals, signals)
            lines = [f"📊 *Monthly Budget Scan* — {len(signals)} signals found\n"]
            for i, sig in enumerate(signals[:10], 1):
                dist = sig.get("district", "")
                state = sig.get("state", "")
                headline = sig.get("headline", "")[:80]
                lines.append(f"  {i}. {dist} ({state}) — {headline}")
            lines.append(f"\nWritten: {write_result['written']} | Deduped: {write_result['skipped']}")
            await send_message("\n".join(lines))
        else:
            logger.info("Monthly budget scan: no signals found")
    except Exception as e:
        logger.error(f"Monthly budget scan failed: {e}")


async def send_eod_report():
    try:
        with open("prompts/eod_report.md", "r") as f:
            prompt_template = f.read()

        # Phase 6C: inject real activity data from today + trigger Gmail sync first
        try:
            gas = get_gas_bridge()
            if gas:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, activity_tracker.sync_gmail_activities, gas)
        except Exception as sync_err:
            logger.warning(f"Gmail sync before EOD failed: {sync_err}")

        try:
            data_block = activity_tracker.build_brief_data_block()
            prompt = f"{data_block}\n\n---\n\n{prompt_template}"
        except Exception as data_err:
            logger.warning(f"Could not load activity data for EOD: {data_err}")
            prompt = prompt_template

        # Phase 6F: inject pipeline alerts if any stale opps exist
        try:
            pipeline_alerts = pipeline_tracker.build_pipeline_alerts()
            if pipeline_alerts:
                prompt = f"{prompt}\n\n{pipeline_alerts}"
        except Exception as pipe_err:
            logger.warning(f"Could not load pipeline alerts for EOD: {pipe_err}")

        # Email drafting daily summary
        try:
            draft_summary = email_drafter.get_daily_summary()
            if draft_summary:
                prompt = f"{prompt}\n\n{draft_summary}"
        except Exception as draft_err:
            logger.warning(f"Could not load email draft summary for EOD: {draft_err}")

        text, _, _ = process_message(prompt, conversation_history, memory)
        await send_message(f"🌙 *EOD Report*\n\n{text}")

        # Suggest approved districts for overnight research
        try:
            loop = asyncio.get_event_loop()
            approved = await loop.run_in_executor(
                None, district_prospector.get_all_prospects, "approved"
            )
            if approved:
                names = [d.get("Account Name", d.get("District Name", "?")) for d in approved[:3]]
                await send_message(
                    f"🌙 *Prospecting:* {len(approved)} approved district(s) waiting for research.\n"
                    f"Top: {', '.join(names)}\n"
                    f"I can run these overnight — just say the word."
                )
        except Exception as pq_err:
            logger.warning(f"Could not load prospect queue for EOD: {pq_err}")

        memory.append_to_summary(text)
        conversation_history.clear()
    except Exception as e:
        logger.error(f"EOD report failed: {e}")


async def send_checkin():
    # Todo-based check-in: reference open items instead of generic greeting
    try:
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(None, todo_manager.get_checkin_summary)
    except Exception:
        msg = "📊 Hourly check-in — anything you need, Steven?"
    # Also suggest pending prospects when research queue is idle
    try:
        if not research_queue.current_job:
            loop = asyncio.get_event_loop()
            pending = await loop.run_in_executor(None, district_prospector.get_pending, 2)
            if pending:
                names = [f"*{d.get('District Name', '?')}*" for d in pending]
                msg += f"\n\n💡 Ready to research: {', '.join(names)}\nApprove with `/prospect_approve` or see all with `/prospect`"
    except Exception:
        pass
    await send_message(msg)


async def send_weekend_greeting():
    """Casual weekend greeting — Saturday 11am or Sunday 1pm CST."""
    now = datetime.now(CST)
    day_name = "Saturday" if now.weekday() == 5 else "Sunday"
    await send_message(
        f"👋 Happy {day_name}, Steven! What do you want to work on today?\n\n"
        f"I'm here if you need anything — research, sequences, pipeline review, whatever.\n"
        f"No auto check-ins today. Use `/eod` if you want an end-of-day summary."
    )


# ── Phase 5: Webhook transcript callback ──────────────────────────────────────

async def _on_transcript_received(transcript_id: str):
    await send_message(f"📞 Call transcript received — processing `{transcript_id}`...")
    gas = get_gas_bridge()
    if not gas or not FIREFLIES_API_KEY:
        await send_message("❌ GAS bridge or FIREFLIES_API_KEY not configured.")
        return
    try:
        from tools.fireflies import FirefliesClient
        from agent.call_processor import CallProcessor
        fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
        try:
            processor = CallProcessor(gas_bridge=gas, memory_manager=memory, fireflies_client=fireflies)
        except Exception as e:
            await send_message(f"❌ Could not initialize call processor: {e}")
            return
        async def on_progress(msg):
            await send_message(msg)
        result = await processor.process_transcript(transcript_id=transcript_id, progress_callback=on_progress)
        if result.get("error"):
            await send_message(f"❌ Processing failed: {result['error']}")
            return
        await send_message(result["telegram_summary"])
        await send_message(result["salesforce_block"])
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        await send_message(f"❌ Error processing transcript {transcript_id}: {e}")


# ── Phase 5+: Fireflies Gmail polling ─────────────────────────────────────────

async def _check_fireflies_gmail(gas):
    """
    Scans Gmail every 60s for new Fireflies recap emails.
    On the first run after startup, seeds existing emails as already-seen so Scout
    doesn't replay old meetings on reboot. Only emails that arrive after startup
    trigger processing.
    """
    global _fireflies_email_triggers, _fireflies_gmail_seeded
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: gas.search_inbox("from:fireflies.ai", max_results=5)
        )

        if not _fireflies_gmail_seeded:
            # First run: mark all existing emails as already seen — don't process any
            for email in results:
                subj = email.get("subject", "")
                date = email.get("date", "")[:16]
                key = f"{subj[:60]}|{date}"
                _fireflies_email_triggers.add(key)
            _fireflies_gmail_seeded = True
            logger.info(f"[Fireflies Gmail] Seeded {len(results)} existing email(s) — watching for new ones.")
            return

        for email in results:
            subj = email.get("subject", "")
            date = email.get("date", "")[:16]
            key = f"{subj[:60]}|{date}"

            # Only care about recap / meeting note emails
            subj_lower = subj.lower()
            if "recap" not in subj_lower and "meeting note" not in subj_lower:
                continue

            if key in _fireflies_email_triggers:
                continue
            _fireflies_email_triggers.add(key)

            # Parse meeting name from subject
            meeting_name = subj
            for prefix in [
                "Your Fireflies.ai meeting recap:",
                "Your Fireflies meeting recap:",
                "Fireflies.ai meeting notes:",
            ]:
                if subj_lower.startswith(prefix.lower()):
                    meeting_name = subj[len(prefix):].strip()
                    break

            await send_message(
                f"📞 Fireflies recap detected: *{meeting_name}*\n"
                f"Fetching transcript... I'll update you every minute if still processing."
            )
            asyncio.create_task(_process_latest_fireflies_transcript(meeting_name))
    except Exception as e:
        logger.warning(f"[Fireflies Gmail check] {e}")


async def _check_email_drafts(gas):
    """
    Auto-draft replies for new unread emails.
    Runs every 5 min during business hours (7 AM - 6 PM CST, weekdays).
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, email_drafter.process_new_emails, gas)
        summary = email_drafter.format_draft_summary(result)
        if summary:
            await send_message(summary)
    except Exception as e:
        logger.error(f"[Email Drafter] Auto-draft check failed: {e}")


async def _process_latest_fireflies_transcript(meeting_name: str):
    """
    Polls the Fireflies API for the newest unprocessed external transcript.
    Retries up to 5 times (60s apart) with Telegram status updates.
    """
    global _fireflies_processed_ids
    if not FIREFLIES_API_KEY:
        return

    loop = asyncio.get_event_loop()

    for attempt in range(1, 6):
        try:
            from tools.fireflies import FirefliesClient
            fireflies = FirefliesClient(api_key=FIREFLIES_API_KEY)
            transcripts = await loop.run_in_executor(
                None, lambda: fireflies.get_recent_transcripts(limit=3)
            )

            new_t = next(
                (t for t in transcripts
                 if t.get("id") and t["id"] not in _fireflies_processed_ids),
                None
            )

            if not new_t:
                if attempt < 5:
                    await send_message(
                        f"⏳ Transcript not ready yet (attempt {attempt}/5) — "
                        f"checking again in 60s"
                    )
                    await asyncio.sleep(60)
                else:
                    await send_message(
                        "❌ Fireflies transcript not available after 5 attempts. "
                        "Use `/call [id]` to process manually."
                    )
                continue

            transcript_id = new_t["id"]
            _fireflies_processed_ids.add(transcript_id)
            await _on_transcript_received(transcript_id)
            return

        except Exception as e:
            if attempt < 5:
                await send_message(
                    f"⏳ Attempt {attempt}/5 failed ({e}) — retrying in 60s"
                )
                await asyncio.sleep(60)
            else:
                await send_message(
                    f"❌ Could not process transcript after 5 attempts: {e}\n"
                    f"Use `/call [id]` to process manually."
                )


# ── Phase 5: Pre-call brief auto-trigger ───────────────────────────────────────

async def _check_precall_briefs(gas):
    global _precall_briefs_sent
    try:
        from agent.call_processor import CallProcessor
        events = gas.get_calendar_events(days_ahead=1)
        now = datetime.now(CST)
        for event in events:
            event_id = (event.get("id") or "") or (event.get("title","") + "|" + event.get("start",""))
            if event_id in _precall_briefs_sent:
                continue
            loc = (event.get("location") or "").lower()
            desc = (event.get("description") or "").lower()
            if "zoom.us" not in loc and "zoom.us" not in desc:
                continue
            start_str = event.get("start", "")
            if not start_str:
                continue
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start_cst = start_dt.astimezone(CST)
                minutes_until = (start_cst - now).total_seconds() / 60
            except Exception:
                continue
            if 9 <= minutes_until <= 11:
                _precall_briefs_sent.add(event_id)
                raw_guests = event.get("guests") or []
                attendees = _parse_guests(raw_guests)
                if not attendees:
                    attendees = [{"name": "Prospect", "email": ""}]
                await send_message(f"⏰ 10-minute warning: *{event.get('title','Zoom call')}*\nBuilding pre-call brief now...")
                try:
                    processor = CallProcessor(gas_bridge=gas, memory_manager=memory)
                    async def on_brief_progress(msg):
                        await send_message(msg)
                    brief = await processor.build_pre_call_brief(
                        event=event, attendees=attendees, progress_callback=on_brief_progress
                    )
                    await send_message(brief)
                except Exception as e:
                    logger.error(f"Pre-call brief auto-trigger error: {e}")
                    await send_message(f"❌ Pre-call brief error: {e}")
    except Exception as e:
        logger.warning(f"Calendar check failed: {e}")


# ── Entry point ────────────────────────────────────────────────────────────────

async def _run_telegram_and_scheduler():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    gas = get_gas_bridge() if gas_bridge_configured() else None

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # One-time sheet cleanup: remove unused tabs + apply alternating row colors
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sheets_writer.cleanup_and_format_sheets)
    except Exception as e:
        logger.warning(f"Sheet cleanup/formatting failed (non-fatal): {e}")

    gas_status = "GAS bridge ready" if gas_bridge_configured() else "GAS bridge not configured"
    ff_status = "Fireflies ready" if FIREFLIES_API_KEY else "FIREFLIES_API_KEY not set"
    await send_message(
        f"Scout is online — Phase 6F+ active.\n"
        f"{gas_status} | {ff_status}\n"
        f"Commands: /brief | /recent_calls | /call [id] | /push_code [file]\n"
        f"/call_list [N] | /progress | /pipeline | /eod\n"
        f"/prospect | /prospect_discover [state] | /prospect_upward | send CSV to import"
    )

    fireflies_gmail_last_check: float = 0.0
    email_draft_last_check: float = 0.0

    # Seed email drafter on startup (marks existing emails as seen)
    if gas:
        try:
            loop = asyncio.get_event_loop()
            seeded_count = await loop.run_in_executor(
                None, email_drafter.seed_processed_emails, gas
            )
            if seeded_count > 0:
                plural = "" if seeded_count == 1 else "s"
                try:
                    await send_message(
                        f"🔄 *Scout restarted* — seeded {seeded_count} existing unread "
                        f"email{plural} as already-seen.\n\n"
                        f"If any of them still need auto-drafts, run `/draft force`."
                    )
                except Exception as notify_err:
                    logger.warning(f"Could not send startup seeding notice: {notify_err}")
        except Exception as e:
            logger.warning(f"Email drafter seeding failed (non-fatal): {e}")

    try:
        while True:
            sched_event = scheduler.check()
            if sched_event == "morning_brief":
                asyncio.create_task(send_morning_brief())
            elif sched_event == "eod_report":
                asyncio.create_task(send_eod_report())
            elif sched_event == "checkin":
                asyncio.create_task(send_checkin())
            elif sched_event == "weekend_greeting":
                asyncio.create_task(send_weekend_greeting())
            elif sched_event == "signal_scan":
                asyncio.create_task(_run_daily_signal_scan())
            elif sched_event == "leadership_scan":
                asyncio.create_task(_run_leadership_scan())
            elif sched_event == "rfp_scan":
                asyncio.create_task(_run_rfp_scan())
            elif sched_event == "legislative_scan":
                asyncio.create_task(_run_legislative_scan())
            elif sched_event == "grant_scan":
                asyncio.create_task(_run_grant_scan())
            elif sched_event == "budget_scan":
                asyncio.create_task(_run_budget_scan())
            if gas and FIREFLIES_API_KEY:
                asyncio.create_task(_check_precall_briefs(gas))
                now_ts = time.time()
                if now_ts - fireflies_gmail_last_check >= 60:
                    fireflies_gmail_last_check = now_ts
                    asyncio.create_task(_check_fireflies_gmail(gas))
            # Auto-draft email replies every 5 min during business hours (7 AM - 6 PM CST, weekdays)
            if gas:
                now_ts = time.time()
                now_cst = datetime.now(pytz.timezone("America/Chicago"))
                is_business_hours = (
                    now_cst.weekday() < 5
                    and 7 <= now_cst.hour < 18
                )
                if is_business_hours and now_ts - email_draft_last_check >= 300:
                    email_draft_last_check = now_ts
                    asyncio.create_task(_check_email_drafts(gas))
            await asyncio.sleep(30)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def main():
    logger.info(f"Starting {AGENT_NAME} — Phase 6E...")
    port = int(os.environ.get("PORT", 8080))
    if os.environ.get("PORT"):
        from agent.webhook_server import start_webhook_server
        logger.info(f"Webhook server starting on port {port}")
        await asyncio.gather(
            _run_telegram_and_scheduler(),
            start_webhook_server(
                port=port,
                process_callback=_on_transcript_received,
                webhook_secret=FIREFLIES_WEBHOOK_SECRET,
                send_message=send_message,
            ),
        )
    else:
        await _run_telegram_and_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
