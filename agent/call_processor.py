"""
agent/call_processor.py
Phase 5: Call Intelligence Suite

Two main capabilities:
  1. build_pre_call_brief() — 10 min before a Zoom, research attendees + org + Gmail
                              history, synthesize with Claude, create Google Doc
  2. process_transcript()   — After call ends (Fireflies webhook), extract structured
                              sales data, draft recap email, build Salesforce block,
                              add contact to Outreach sheet

All heavy HTTP work is run in asyncio.to_thread() so the event loop stays responsive.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Callable

import pytz
import requests
from anthropic import Anthropic

logger = logging.getLogger(__name__)
CST = pytz.timezone("America/Chicago")

SERPER_URL = "https://google.serper.dev/search"


class CallProcessor:

    def __init__(self, gas_bridge, memory_manager, fireflies_client=None):
        """
        gas_bridge:       GASBridge instance
        memory_manager:   MemoryManager instance
        fireflies_client: FirefliesClient instance (optional — required for post-call)
        """
        self.gas = gas_bridge
        self.memory = memory_manager
        self.fireflies = fireflies_client

        # Phase 5 fix: PRECALL_BRIEF_FOLDER_ID is a Railway env var, not in config.py
        from agent.config import ANTHROPIC_API_KEY, SERPER_API_KEY
        self._claude = Anthropic(api_key=ANTHROPIC_API_KEY)
        self._serper_key = SERPER_API_KEY
        self._brief_folder_id = os.environ.get("PRECALL_BRIEF_FOLDER_ID", "")

    # ── Pre-Call Brief ────────────────────────────────────────────────────────

    async def build_pre_call_brief(
        self,
        event: dict,
        attendees: list[dict],
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        Builds a comprehensive pre-call brief for an upcoming Zoom meeting.
        """
        async def progress(msg: str):
            if progress_callback:
                await progress_callback(msg)
            logger.info(f"[PreCallBrief] {msg}")

        meeting_title = event.get("title", "Meeting")
        names = [a.get("name") or a.get("email", "?") for a in attendees]
        await progress(f"🔍 *Pre-call brief: {meeting_title}*\nResearching {', '.join(names)}...")

        attendee_profiles = await asyncio.to_thread(
            self._research_all_attendees, attendees
        )

        org = self._extract_org(attendees, event)
        org_profile = await asyncio.to_thread(self._research_org, org)

        email_history = await asyncio.to_thread(self._get_email_history, attendees)

        await progress("🧠 Synthesizing brief with Claude...")
        brief_text = await asyncio.to_thread(
            self._synthesize_brief,
            event, attendees, attendee_profiles, org_profile, email_history,
        )

        await progress("📄 Creating Google Doc...")
        doc_result = await asyncio.to_thread(
            self._create_brief_doc, event, attendees, brief_text
        )

        if doc_result and not doc_result.startswith("ERROR:"):
            # Success — append clickable link
            brief_text += f"\n\n📄 [Open Google Doc]({doc_result})"
        elif doc_result and doc_result.startswith("ERROR:"):
            # Surface the actual error so we can debug it
            brief_text += f"\n\n⚠️ *Google Doc creation failed:* {doc_result[6:]}"
        else:
            # Empty string means folder ID wasn't set
            brief_text += "\n\n_(Google Doc skipped — PRECALL_BRIEF_FOLDER_ID not set in Railway)_"

        return brief_text

    def _research_all_attendees(self, attendees: list[dict]) -> list[dict]:
        profiles = []
        for a in attendees:
            name = a.get("name", "")
            email = a.get("email", "")
            profile = self._research_attendee(name, email)
            profiles.append(profile)
        return profiles

    def _research_attendee(self, name: str, email: str) -> dict:
        if not name and not email:
            return {"name": email, "bio": "", "linkedin": ""}

        results = self._serper_search(f"{name} school district educator site:linkedin.com OR title", num=5)
        snippets = " ".join(r.get("snippet", "") for r in results[:3])
        linkedin = next(
            (r["link"] for r in results if "linkedin.com/in/" in r.get("link", "")),
            ""
        )
        return {
            "name": name,
            "email": email,
            "bio": snippets[:600] if snippets else "No public bio found.",
            "linkedin": linkedin,
        }

    def _research_org(self, org: str) -> dict:
        if not org:
            return {"org": "", "info": "", "news": ""}

        info_results = self._serper_search(
            f"{org} school district enrollment technology CS STEM programs budget"
        )
        news_results = self._serper_search(
            f"{org} school district AI coding technology grant 2024 2025"
        )

        info_text = " ".join(r.get("snippet", "") for r in info_results[:4])
        news_text = " ".join(r.get("snippet", "") for r in news_results[:3])

        return {
            "org": org,
            "info": info_text[:800],
            "news": news_text[:600],
        }

    def _get_email_history(self, attendees: list[dict]) -> str:
        from tools.gas_bridge import GASBridgeError

        parts = []
        for a in attendees:
            email = a.get("email", "")
            name = a.get("name", "")
            if not email and not name:
                continue
            query = f"from:{email}" if email else f'"{name}"'
            try:
                results = self.gas.search_inbox(query=query, max_results=5)
                if results:
                    parts.append(f"\nEmails with {name or email}:")
                    for r in results[:4]:
                        parts.append(
                            f"  • [{r.get('date', '')[:10]}] {r.get('subject', '(no subject)')} — "
                            f"{r.get('snippet', '')[:140]}"
                        )
            except GASBridgeError as e:
                logger.warning(f"[CallProcessor] Gmail search failed for {email}: {e}")

        return "\n".join(parts) if parts else "No prior email threads found."

    def _synthesize_brief(
        self,
        event: dict,
        attendees: list[dict],
        attendee_profiles: list[dict],
        org_profile: dict,
        email_history: str,
    ) -> str:
        meeting_title = event.get("title", "Meeting")
        meeting_start = event.get("start", "")
        meeting_location = event.get("location", "")
        meeting_desc = event.get("description", "")

        attendee_text = "\n".join(
            f"- *{p.get('name', '?')}* ({p.get('email', '')})\n"
            f"  Bio: {p.get('bio', 'No info')}\n"
            f"  LinkedIn: {p.get('linkedin', 'Not found')}"
            for p in attendee_profiles
        )

        prompt = f"""You are Scout, an AI sales assistant for Steven at CodeCombat (K-12 CS and AI curriculum).
Steven has an upcoming Zoom call. Build him a sharp, scannable pre-call brief.

MEETING: {meeting_title}
WHEN: {meeting_start}
ZOOM/LOCATION: {meeting_location}
DESCRIPTION: {meeting_desc}

ATTENDEES:
{attendee_text}

DISTRICT/ORG INFO:
{org_profile.get("info", "No info found.")}

RECENT NEWS:
{org_profile.get("news", "No news found.")}

PRIOR EMAIL HISTORY:
{email_history}

Format the brief with these exact sections:

## 👥 Who You're Meeting
For each attendee: name, title, key background, LinkedIn if found. Keep it tight.

## 🏫 About the District/Org
Enrollment, grades served, budget signals, any CS/STEM/coding programs already in place.

## 📰 Recent News
Relevant things from the past 12 months — tech purchases, grants, AI pilots, CS requirements.

## 📧 Our History
How warm is this? Prior touchpoints, what was discussed, any quotes/promises made.

## 💰 Deal Intelligence
• Estimated deal size (based on enrollment × license rate ~$15-25/student/yr)
• Rating: 🔥 Hot / ☀️ Warm / 🧊 Cold
• Top 2-3 signals driving that rating

## 🎯 Steven's Game Plan
3-5 specific things to say, ask, or watch for on this call.
Flag any red flags or objections to get ahead of.

Rules: Be direct. Use bullets. Skip filler. Give Steven only what matters."""

        try:
            response = self._claude.messages.create(
                model="claude-opus-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[CallProcessor] Brief synthesis error: {e}")
            return f"❌ Brief synthesis failed: {e}"

    def _create_brief_doc(
        self,
        event: dict,
        attendees: list[dict],
        content: str,
    ) -> str:
        """
        Create a Google Doc for the brief.
        Returns:
          - URL string on success
          - "ERROR:<message>" string if GAS bridge call fails
          - "" if folder ID not configured
        """
        if not self._brief_folder_id:
            return ""

        last_names = []
        for a in attendees:
            name = a.get("name", "")
            if name:
                last_names.append(name.strip().split()[-1])

        meeting_title = event.get("title", "Meeting")
        date_str = ""
        start = event.get("start", "")
        if start:
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                date_str = dt.strftime("%m-%d-%Y")
            except Exception:
                date_str = start[:10]

        doc_title = f"{' '.join(last_names) or 'Pre-Call'} — {meeting_title} — {date_str}"

        try:
            result = self.gas.create_google_doc(
                title=doc_title,
                content=content,
                folder_id=self._brief_folder_id,
            )
            logger.info(f"[CallProcessor] Google Doc created: {result.get('url', '')}")
            return result.get("url", "")
        except Exception as e:
            # Return error string instead of swallowing it silently
            logger.warning(f"[CallProcessor] Google Doc creation failed: {e}")
            return f"ERROR:{e}"

    # ── Post-Call Processing ──────────────────────────────────────────────────

    async def process_transcript(
        self,
        transcript_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        """
        Full post-call processing pipeline triggered by Fireflies webhook or /call command.
        """
        async def progress(msg: str):
            if progress_callback:
                await progress_callback(msg)
            logger.info(f"[PostCall] {msg}")

        if not self.fireflies:
            return {"error": "Fireflies client not configured. Set FIREFLIES_API_KEY in Railway."}

        await progress(f"📥 Fetching Fireflies transcript `{transcript_id}`...")

        try:
            transcript_data = await asyncio.to_thread(
                self.fireflies.get_transcript, transcript_id
            )
        except Exception as e:
            return {"error": f"Could not fetch transcript: {e}"}

        title = transcript_data.get("title", "Call")
        attendees = transcript_data.get("attendees") or []
        transcript_text = transcript_data.get("transcript", "")
        call_date = transcript_data.get("date", "")

        await progress(
            f"✅ Transcript loaded: *{title}*\n"
            f"{len(transcript_text.splitlines())} lines · "
            f"{', '.join(a.get('name', a.get('email', '?')) for a in attendees)}"
        )

        await progress("🧠 Extracting sales intelligence...")
        extracted = await asyncio.to_thread(
            self._extract_call_data, transcript_text, title, attendees, call_date
        )

        await progress("✍️ Drafting recap email in your voice...")
        recap_email = await asyncio.to_thread(self._draft_recap_email, extracted)

        draft_url = ""
        draft_error = ""
        try:
            # Prefer Fireflies attendee emails; fall back to what Claude extracted from transcript
            prospect_email = self._find_prospect_email(attendees) or extracted.get("contact_email", "")
            if prospect_email and self._is_valid_email(prospect_email):
                result = self.gas.create_draft(
                    to=prospect_email,
                    subject=recap_email["subject"],
                    body=recap_email["body"],
                )
                draft_url = result.get("link", "https://mail.google.com/mail/u/0/#drafts")
                await progress("✉️ Recap email saved to Gmail Drafts")
            elif prospect_email:
                draft_error = f"email looks malformed (`{prospect_email}`) — correct it and resend `/call`"
                logger.warning(f"[PostCall] Malformed email, skipping draft: {prospect_email}")
            else:
                draft_error = "no prospect email found — draft skipped"
                logger.warning(f"[PostCall] {draft_error}")
        except Exception as e:
            draft_error = str(e)
            logger.warning(f"[PostCall] Gmail draft failed: {e}")

        salesforce_block = self._build_salesforce_block(extracted)

        telegram_summary = self._format_telegram_summary(extracted, draft_url, draft_error)

        return {
            "telegram_summary": telegram_summary,
            "recap_email": recap_email,
            "salesforce_block": salesforce_block,
            "draft_url": draft_url,
            "error": None,
        }

    def _extract_call_data(
        self,
        transcript: str,
        title: str,
        attendees: list[dict],
        call_date: str,
    ) -> dict:
        attendee_list = ", ".join(
            f"{a.get('name', '')} <{a.get('email', '')}>"
            for a in attendees
        )

        transcript_sample = transcript[:8000]
        if len(transcript) > 8000:
            transcript_sample += "\n...[truncated]"

        prompt = f"""You are Scout, a sales intelligence assistant for Steven at CodeCombat.
Analyze this sales call transcript and extract every useful detail.
CodeCombat sells K-12 CS and AI curriculum to school districts.

CALL: {title}
DATE: {call_date}
ATTENDEES: {attendee_list}

TRANSCRIPT:
{transcript_sample}

Return a JSON object with these exact keys (use null if not mentioned):
{{
  "district": "school district or org name",
  "contact_name": "primary prospect's full name",
  "contact_title": "their job title",
  "contact_email": "email if said aloud",
  "grade_levels": "e.g. 6-12, K-8, or 'not mentioned'",
  "license_count": "number of students or licenses mentioned, or 'not mentioned'",
  "device_type": "Chromebook/iPad/Windows/mixed, or 'not mentioned'",
  "implementation_timeline": "when they want to start, or 'not mentioned'",
  "budget_signal": "any budget info (even vague), or 'not mentioned'",
  "codecombat_familiarity": "never heard of it / heard of it / used it / currently using",
  "teacher_comfort": "teacher coding comfort level",
  "class_setup": "sections, class size, frequency if discussed",
  "vision": "what they want to accomplish with CS/AI curriculum",
  "decision_makers": "who approves the purchase",
  "cs_lead": "who runs CS/STEM for the district",
  "unanswered_questions": ["things raised but not resolved"],
  "next_steps": ["clear action items with owners and dates if mentioned"],
  "steven_tasks": ["prioritized to-do list for Steven"],
  "scout_suggestions": ["Scout's recommendations — what to emphasize next time, follow-up priorities, red flags"],
  "temperature": "Hot / Warm / Cold",
  "temperature_reason": "1-2 sentence reasoning"
}}

Keep all string field values concise — clean phrases under 80 characters. No parenthetical explanations inside field values. Use the cleanest version of names (e.g. "Oklahoma State University Academy" not "Oklahoma State University Academy (referenced as...)").

Return ONLY valid JSON. No preamble, no explanation, no markdown fences."""

        try:
            response = self._claude.messages.create(
                model="claude-opus-4-5",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"[PostCall] JSON parse error: {e} | Raw: {raw[:200]}")
            return {"district": title, "_parse_error": True}
        except Exception as e:
            logger.error(f"[PostCall] Extraction failed: {e}")
            return {"district": title, "_error": str(e)}

    def _draft_recap_email(self, data: dict) -> dict:
        voice_profile = ""
        try:
            with open("memory/voice_profile.md", "r", encoding="utf-8") as f:
                voice_profile = f.read()[:2000]
        except FileNotFoundError:
            voice_profile = "Warm, direct, conversational. No fluff. Short. Human."

        district = data.get("district") or "your organization"
        contact_name = data.get("contact_name") or ""
        next_steps = data.get("next_steps") or []
        vision = data.get("vision") or ""
        grade_levels = data.get("grade_levels") or ""

        next_steps_text = "\n".join(f"- {s}" for s in next_steps) if next_steps else "- Following up with more details"

        prompt = f"""Write a short post-call recap email in Steven's voice.

STEVEN'S VOICE PROFILE:
{voice_profile}

CALL CONTEXT:
Contact: {contact_name} at {district}
Grade levels discussed: {grade_levels}
Their vision: {vision}
Next steps agreed to:
{next_steps_text}

Requirements:
- Short: 4-6 sentences max
- Thanks them for their time (one sentence, genuine not sycophantic)
- 1-2 sentences recapping the key takeaway from the call
- Lists the next steps clearly
- Ends with an easy, low-pressure CTA
- Subject: Following up on our call — {district}
- Plain text only, no HTML

Return exactly this format:
Subject: [subject line]
Body:
[email body]"""

        try:
            response = self._claude.messages.create(
                model="claude-opus-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            subject_match = re.search(r"Subject:\s*(.+)", text, re.IGNORECASE)
            body_match = re.search(r"Body:\s*([\s\S]+)", text, re.IGNORECASE)
            subject = subject_match.group(1).strip() if subject_match else f"Following up on our call — {district}"
            body = body_match.group(1).strip() if body_match else text
            return {"subject": subject, "body": body}
        except Exception as e:
            logger.error(f"[PostCall] Email draft error: {e}")
            first_name = (contact_name or "").split()[0] or "there"
            return {
                "subject": f"Following up on our call — {district}",
                "body": (
                    f"Hi {first_name},\n\n"
                    f"Great talking today. I'll send over the info we discussed shortly.\n\n"
                    f"Best,\nSteven"
                )
            }

    def _build_salesforce_block(self, data: dict) -> str:
        now = datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")

        def val(key: str, max_len: int = 0) -> str:
            v = data.get(key)
            s = str(v) if v and v != "not mentioned" else "N/A"
            if max_len and len(s) > max_len:
                return s[:max_len] + "…"
            return s

        temp_icon = {"Hot": "🔥", "Warm": "☀️", "Cold": "🧊"}.get(data.get("temperature", ""), "")
        ns = data.get("next_steps") or []
        next_steps_str = "\n".join(f"• {s}" for s in ns) if ns else "• N/A"

        return (
            f"*━━━ Salesforce Log ━━━*\n"
            f"📅 {now}\n"
            f"👤 *{val('contact_name')}* — {val('contact_title', 60)}\n"
            f"📧 {val('contact_email')}\n"
            f"🏫 {val('district', 60)}\n"
            f"{temp_icon} *{val('temperature')}*\n"
            f"\n"
            f"*Key Info:*\n"
            f"• Grades: {val('grade_levels', 60)}\n"
            f"• Licenses: {val('license_count')}\n"
            f"• Timeline: {val('implementation_timeline', 60)}\n"
            f"• Budget: {val('budget_signal', 80)}\n"
            f"• Devices: {val('device_type')}\n"
            f"• CC Familiarity: {val('codecombat_familiarity', 60)}\n"
            f"\n"
            f"*Vision:* {val('vision', 150)}\n"
            f"\n"
            f"*Next Steps:*\n{next_steps_str}\n"
            f"\n"
            f"*Reasoning:* {val('temperature_reason', 150)}"
        )

    def _build_outreach_row(self, data: dict, attendees: list[dict]) -> dict:
        prospect_email = data.get("contact_email") or self._find_prospect_email(attendees)
        contact_name = data.get("contact_name") or ""

        if not prospect_email and not contact_name:
            return {}

        if not contact_name:
            for a in attendees:
                if a.get("email") == prospect_email:
                    contact_name = a.get("name", "")
                    break

        name_parts = contact_name.strip().split() if contact_name else []
        first = name_parts[0] if name_parts else ""
        last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        date_str = datetime.now(CST).strftime("%Y-%m-%d")
        temp = data.get("temperature", "")
        vision_snippet = (data.get("vision") or "")[:100]

        return {
            "First Name": first,
            "Last Name": last,
            "Title": data.get("contact_title", ""),
            "Email": prospect_email or "",
            "Organization": data.get("district", ""),
            "Notes": f"Call {date_str} | {temp} | {vision_snippet}",
        }

    def _format_telegram_summary(self, data: dict, draft_url: str, draft_error: str = "") -> str:
        def val(key: str, max_len: int = 0) -> str:
            v = data.get(key)
            s = str(v) if v and v not in (None, "not mentioned", "N/A") else "—"
            if max_len and len(s) > max_len:
                return s[:max_len] + "…"
            return s

        if data.get("_parse_error") or data.get("_error"):
            return (
                f"⚠️ *Post-call summary extracted with issues*\n"
                f"District: {val('district')}\n"
                f"Claude had trouble parsing structured data — check call_processor logs.\n"
                + (f"\n✉️ [Recap email in Gmail Drafts]({draft_url})" if draft_url else "")
            )

        temp_icon = {"Hot": "🔥", "Warm": "☀️", "Cold": "🧊"}.get(data.get("temperature", ""), "🌡️")

        lines = [f"📞 *Post-Call Summary: {val('district', 60)}*", ""]

        # Contact line — name, title, email on next line if present
        lines.append(f"👤 *{val('contact_name')}* — {val('contact_title', 60)}")
        email = data.get("contact_email")
        if email and email not in (None, "not mentioned", "N/A"):
            lines.append(f"📧 {email}")

        lines.append(f"{temp_icon} *{val('temperature')}* — {val('temperature_reason', 120)}")
        lines.append("")

        lines.append("📊 *Key Intel:*")
        for key, label in [
            ("grade_levels",             "Grades"),
            ("license_count",            "Licenses"),
            ("device_type",              "Devices"),
            ("implementation_timeline",  "Timeline"),
            ("budget_signal",            "Budget"),
            ("codecombat_familiarity",   "CC Familiarity"),
            ("teacher_comfort",          "Teacher Comfort"),
            ("decision_makers",          "Decision Maker"),
        ]:
            lines.append(f"• {label}: {val(key, 80)}")
        lines.append(f"• Vision: {val('vision', 160)}")
        lines.append("")

        next_steps = data.get("next_steps") or []
        if next_steps:
            lines.append("✅ *Next Steps:*")
            for s in next_steps[:5]:
                lines.append(f"• {str(s)[:120]}")
            lines.append("")

        tasks = data.get("steven_tasks") or []
        if tasks:
            lines.append("📋 *Your Tasks:*")
            for t in tasks[:5]:
                lines.append(f"• {str(t)[:120]}")
            lines.append("")

        suggestions = data.get("scout_suggestions") or []
        if suggestions:
            lines.append("💡 *Key Insights:*")
            for s in suggestions[:4]:
                lines.append(f"• {str(s)[:120]}")
            lines.append("")

        if draft_url:
            lines.append(f"✉️ [Recap email saved to Gmail Drafts]({draft_url})")
        elif draft_error:
            lines.append(f"⚠️ *Recap email not saved:* {draft_error}")

        return "\n".join(lines)

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _serper_search(self, query: str, num: int = 5) -> list[dict]:
        if not self._serper_key:
            return []
        try:
            r = requests.post(
                SERPER_URL,
                json={"q": query, "num": num},
                headers={"X-API-KEY": self._serper_key, "Content-Type": "application/json"},
                timeout=10,
            )
            r.raise_for_status()
            return r.json().get("organic", [])
        except Exception as e:
            logger.warning(f"[CallProcessor] Serper search failed: {e}")
            return []

    def _extract_org(self, attendees: list[dict], event: dict) -> str:
        title = event.get("title", "")
        if title:
            return title
        for a in attendees:
            email = a.get("email", "")
            if email and "@codecombat.com" not in email:
                domain = email.split("@")[-1]
                if not any(x in domain for x in ["gmail", "yahoo", "outlook", "hotmail", "icloud"]):
                    return domain
        return ""

    def _find_prospect_email(self, attendees: list[dict]) -> str:
        for a in attendees:
            email = a.get("email", "")
            if email and "@codecombat.com" not in email.lower():
                return email
        return ""

    def _is_valid_email(self, email: str) -> bool:
        """Basic sanity check: has @, domain has a dot, TLD is at least 2 chars."""
        if not email or "@" not in email:
            return False
        local, _, domain = email.partition("@")
        if not local or not domain or "." not in domain:
            return False
        tld = domain.rsplit(".", 1)[-1]
        return len(tld) >= 2
