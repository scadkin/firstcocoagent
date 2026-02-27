"""
claude_brain.py — Claude API integration for Scout.
Phase 2 additions:
  - Tool use for research intent detection
  - Research job triggering and status reporting
  - Memory injection unchanged from Phase 1.5
"""

import re
import logging
from anthropic import Anthropic
from agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

client = Anthropic()

# ─────────────────────────────────────────────
# TOOL DEFINITIONS (Phase 2)
# Claude uses these to signal research intent
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "research_district",
        "description": (
            "Use this tool when the user wants Scout to research contacts at a specific K-12 school district. "
            "Triggers the 10-layer research engine. "
            "Examples: 'Research CS contacts in Austin ISD', 'Find STEM leads at Denver Public Schools', "
            "'Look up computer science people at Chicago Public Schools'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_name": {
                    "type": "string",
                    "description": "Full official name of the school district (e.g. 'Austin Independent School District' or 'Denver Public Schools')"
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state abbreviation (e.g. 'TX', 'CO', 'CA')"
                },
            },
            "required": ["district_name", "state"]
        }
    },
    {
        "name": "get_sheet_status",
        "description": "Check the current count of leads in the Master Google Sheet.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_research_queue_status",
        "description": "Check if a research job is currently running and how many are queued.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ─────────────────────────────────────────────
# BRAIN CLASS
# ─────────────────────────────────────────────

class ClaudeBrain:
    def __init__(self, memory_manager: MemoryManager, research_queue=None):
        self.memory = memory_manager
        self.research_queue = research_queue  # ResearchQueue instance
        self.conversation_history = []

    def _build_system_prompt(self) -> str:
        """Load system prompt from file and inject current memory."""
        try:
            with open("prompts/system.md", "r") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            base_prompt = "You are Scout, an AI sales assistant for CodeCombat."

        # Inject memory
        preferences = self.memory.load_preferences()
        context = self.memory.load_context_summary()

        memory_section = ""
        if preferences.strip():
            memory_section += f"\n\n## Steven's Preferences & Corrections\n{preferences}"
        if context.strip():
            memory_section += f"\n\n## Recent Context Summary\n{context}"

        if memory_section:
            base_prompt += f"\n\n---\n# MEMORY (from past conversations){memory_section}"

        return base_prompt

    def _detect_memory_update(self, response_text: str) -> str | None:
        """Extract [MEMORY_UPDATE: ...] tag from response."""
        match = re.search(r'\[MEMORY_UPDATE:\s*(.+?)\]', response_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _strip_memory_tag(self, response_text: str) -> str:
        """Remove [MEMORY_UPDATE: ...] tag from response before sending to user."""
        return re.sub(r'\[MEMORY_UPDATE:\s*.+?\]', '', response_text, flags=re.IGNORECASE).strip()

    async def process_message(self, user_message: str) -> tuple[str, dict | None]:
        """
        Process a user message through Claude.
        Returns (response_text, tool_call_or_None).

        If Claude calls a tool (e.g., research_district), the tool_call dict is returned
        so the caller can execute it.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        system = self._build_system_prompt()

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=self.conversation_history
        )

        # Check if Claude wants to use a tool
        tool_call = None
        response_text = ""

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    tool_call = {
                        "name": block.name,
                        "input": block.input,
                        "tool_use_id": block.id,
                    }
                elif hasattr(block, "text"):
                    response_text += block.text

            # Add Claude's tool-use response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })

        else:
            # Normal text response
            for block in response.content:
                if hasattr(block, "text"):
                    response_text += block.text

            # Check for memory update tag
            memory_update = self._detect_memory_update(response_text)
            if memory_update:
                self.memory.save_preference(memory_update)
                response_text = self._strip_memory_tag(response_text)

            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })

        # Trim history to avoid context bloat (keep last 40 turns)
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        return response_text, tool_call

    async def inject_tool_result(self, tool_use_id: str, tool_name: str, result: str) -> str:
        """
        After executing a tool, send the result back to Claude for a natural response.
        Returns Claude's follow-up text.
        """
        self.conversation_history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result,
                }
            ]
        })

        system = self._build_system_prompt()

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=self.conversation_history
        )

        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text += block.text

        # Check for memory update
        memory_update = self._detect_memory_update(response_text)
        if memory_update:
            self.memory.save_preference(memory_update)
            response_text = self._strip_memory_tag(response_text)

        self.conversation_history.append({
            "role": "assistant",
            "content": response_text
        })

        return response_text

    def clear_history(self):
        """Clear conversation history (used at EOD before compression)."""
        self.conversation_history = []

    def get_history_for_compression(self) -> list[dict]:
        """Return history for EOD compression."""
        return self.conversation_history.copy()

    async def compress_to_memory(self):
        """
        Compress today's conversation history to context_summary.md.
        Called at EOD.
        """
        if not self.conversation_history:
            return

        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content'] if isinstance(msg['content'], str) else '[tool interaction]'}"
            for msg in self.conversation_history
        ])

        summary_prompt = f"""Compress today's conversation into 3-5 sentences for memory.
Focus on: what Steven worked on, what was researched, decisions made, and any corrections/preferences.
Do NOT include greetings or small talk. Be concrete and specific.

Conversation:
{history_text[:8000]}

Write the summary only. No preamble."""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": summary_prompt}]
        )

        summary = response.content[0].text.strip()
        self.memory.append_context_summary(summary)
        self.clear_history()
