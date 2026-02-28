"""
agent/claude_brain.py
Claude API interface for Scout. Handles tool use, memory injection, response parsing.
Phase 3: Gmail + Calendar + Slides via GAS bridge.
"""

import json
import logging
import re
from anthropic import Anthropic
from agent.config import ANTHROPIC_API_KEY
from agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

TOOLS = [
    # Phase 2: Research
    {
        "name": "research_district",
        "description": "Research a school district to find CS/STEM/CTE contacts. Use when Steven asks to research a district.",
        "input_schema": {
            "type": "object",
            "properties": {
                "district_name": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["district_name"],
        },
    },
    {
        "name": "get_sheet_status",
        "description": "Get current lead counts and Google Sheets link.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_research_queue_status",
        "description": "Get current research job and queue depth.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Phase 3: Voice Training
    {
        "name": "train_voice",
        "description": "Train Scout's voice model by reading Steven's sent Gmail history via GAS bridge. Use when Steven says 'train your voice', 'learn my style', or '/train_voice'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "months_back": {"type": "integer", "description": "Months of history to analyze (default 6)"},
            },
            "required": [],
        },
    },
    # Phase 3: Email Drafting
    {
        "name": "draft_email",
        "description": "Draft a sales email in Steven's voice. Use when Steven asks to draft or write an email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient_name": {"type": "string"},
                "recipient_title": {"type": "string"},
                "district": {"type": "string"},
                "state": {"type": "string"},
                "email_type": {
                    "type": "string",
                    "enum": ["cold outreach", "follow-up", "reply", "referral intro"],
                },
                "additional_context": {"type": "string"},
            },
            "required": ["district"],
        },
    },
    {
        "name": "save_draft_to_gmail",
        "description": "Save an approved email draft to Gmail Drafts. Use when Steven says 'looks good', 'save it', or approves a draft.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["subject", "body"],
        },
    },
    # Phase 3: Calendar
    {
        "name": "get_calendar",
        "description": "Get Steven's upcoming calendar events. Use when he asks what's on his calendar or 'what does my week look like'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Days ahead to look (default 7)"},
            },
            "required": [],
        },
    },
    {
        "name": "log_call",
        "description": "Log a sales call as a calendar event with structured notes. Use when Steven says 'log that call' or describes a call he just had.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string"},
                "title": {"type": "string"},
                "district": {"type": "string"},
                "date_iso": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "notes": {"type": "string"},
                "outcome": {"type": "string"},
                "next_steps": {"type": "string"},
            },
            "required": ["contact_name", "district"],
        },
    },
    # Phase 3: Slides
    {
        "name": "create_district_deck",
        "description": "Create a Google Slides pitch deck for a specific district. Use when Steven asks to make a deck or presentation for a district.",
        "input_schema": {
            "type": "object",
            "properties": {
                "district_name": {"type": "string"},
                "state": {"type": "string"},
                "contact_name": {"type": "string"},
                "contact_title": {"type": "string"},
                "key_pain_points": {"type": "array", "items": {"type": "string"}},
                "products_to_highlight": {"type": "array", "items": {"type": "string"}},
                "case_study": {"type": "string"},
            },
            "required": ["district_name"],
        },
    },
    # Phase 4: GitHub Code Push
    {
        "name": "push_code",
        "description": (
            "Push a file to GitHub. Use when Steven says '/push_code', 'push this to GitHub', "
            "'commit this', 'deploy this fix', or when Steven pastes code and asks Scout to save it. "
            "Also use when Scout itself generates a code fix and should commit it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Repo-relative path, e.g. 'agent/main.py' or 'tools/github_pusher.py'",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write. Must be the complete file, not a diff.",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Git commit message. Optional — auto-generated if omitted.",
                },
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "list_repo_files",
        "description": (
            "List files in the GitHub repo. Use when Steven asks 'what files are in the repo', "
            "'show me the repo structure', or before pushing code to verify a filepath."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Subdirectory to list, e.g. 'agent' or 'tools'. Empty string = root.",
                },
            },
            "required": [],
        },
    },
    # Phase 4: Email Sequences
    {
        "name": "build_sequence",
        "description": (
            "Build a multi-step cold email sequence in Steven's voice for Outreach.io. "
            "Use when Steven says 'build a sequence', 'create a campaign', 'write a sequence for [role/district]', "
            "or 'make outreach emails for [audience]'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_name": {
                    "type": "string",
                    "description": "Name for this sequence, e.g. 'CS Directors - California Spring 2026'",
                },
                "target_role": {
                    "type": "string",
                    "description": "Job title/role being targeted, e.g. 'CS Director', 'CTE Coordinator', 'Superintendent'",
                },
                "focus_product": {
                    "type": "string",
                    "description": "CodeCombat product to highlight. Defaults to 'CodeCombat AI Suite'.",
                },
                "num_steps": {
                    "type": "integer",
                    "description": "Number of sequence steps (default 4: cold + 3 follow-ups)",
                },
                "additional_context": {
                    "type": "string",
                    "description": "Any extra context: state, budget season, specific pain points, etc.",
                },
            },
            "required": ["campaign_name", "target_role"],
        },
    },
    # Utility
    {
        "name": "ping_gas_bridge",
        "description": "Test the Google Apps Script bridge connection. Use when Steven asks if Google is connected or sends /ping_gas.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def load_system_prompt() -> str:
    try:
        with open("prompts/system.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "You are Scout, an AI sales assistant for CodeCombat."


def load_email_draft_prompt() -> str:
    try:
        with open("prompts/email_draft.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def build_system_context(memory: MemoryManager) -> str:
    system = load_system_prompt()

    preferences = memory.load_preferences()
    if preferences:
        system += f"\n\n---\n## Learned Preferences\n{preferences}"

    recent = memory.load_recent_summary()
    if recent:
        system += f"\n\n---\n## Recent Activity Context\n{recent}"

    try:
        with open("memory/voice_profile.md", "r", encoding="utf-8") as f:
            voice = f.read()
        if "Not yet generated" not in voice:
            system += f"\n\n---\n## Steven's Email Voice Profile\n{voice}"
    except FileNotFoundError:
        pass

    return system


def process_message(
    user_message: str,
    history: list,
    memory: MemoryManager,
) -> tuple:
    system = build_system_context(memory)
    history = history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=history,
        )
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return f"❌ Claude API error: {e}", history, []

    tool_calls = []
    text_parts = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({
                "tool_name": block.name,
                "tool_input": block.input,
                "tool_use_id": block.id,
            })

    text_response = "\n".join(text_parts).strip()

    if "[MEMORY_UPDATE:" in text_response:
        _extract_and_save_memory(text_response, memory)
        text_response = re.sub(r"\[MEMORY_UPDATE:.*?\]", "", text_response).strip()

    history = history + [{"role": "assistant", "content": response.content}]
    return text_response, history, tool_calls


def _extract_and_save_memory(text: str, memory: MemoryManager):
    matches = re.findall(r"\[MEMORY_UPDATE:\s*(.*?)\]", text, re.DOTALL)
    for match in matches:
        entry = match.strip()
        if entry:
            memory.save_preference(entry)
            logger.info(f"Memory saved: {entry}")


def build_draft_prompt(voice_profile, recipient_name, recipient_title, district, state, email_type, additional_context) -> str:
    template = load_email_draft_prompt()
    return template.format(
        voice_profile=voice_profile or "(Voice profile not yet trained — use a warm, direct, concise sales style)",
        recipient_name=recipient_name or "unknown",
        recipient_title=recipient_title or "unknown",
        district=district,
        state=state or "unknown",
        email_type=email_type or "cold outreach",
        additional_context=additional_context or "none provided",
    )


def draft_email_with_claude(prompt: str) -> str:
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude draft email error: {e}")
        return f"❌ Could not generate draft: {e}"
