"""
claude_brain.py — All Claude API interactions for Scout.

CHANGES FROM PHASE 1:
  - Memory injection: preferences + recent history summary prepended to every API call
  - Correction detection: Claude appends [MEMORY_UPDATE: ...] when it learns something new.
    Brain strips the tag, saves to memory, returns clean response to Steven.
  - No more clear_history() on a schedule. History is compressed by scheduler at EOD,
    not deleted. Manual clear still available if Steven requests it explicitly.
  - one_shot() unchanged — still used for scheduled jobs without polluting history.
  - inject_context() unchanged — used for feeding in transcripts, lead data, etc.
"""

import logging
from pathlib import Path

import anthropic

from agent import config

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        logger.warning(f"[Brain] Prompt file not found: {filename}")
        return ""
    return path.read_text(encoding="utf-8")


class ScoutBrain:

    def __init__(self, memory_manager=None):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._base_system_prompt = load_prompt("system.md")
        self.conversation_history = []
        self.max_history_turns = 20
        self.memory = memory_manager  # Injected from main.py
        logger.info("[Brain] Scout initialized. System prompt loaded.")

    def _build_system_prompt(self) -> str:
        """
        Build the full system prompt for this API call.
        Injects persistent memory (preferences + history summary) at the top.
        Memory context is loaded fresh each call so it always reflects latest saves.
        """
        if self.memory:
            memory_block = self.memory.build_memory_context()
        else:
            memory_block = ""
        return self._base_system_prompt + memory_block

    async def chat(self, user_message: str) -> str:
        """
        Main conversational call. Maintains rolling history.
        Detects memory updates in Claude's response and saves them automatically.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Trim history if too long (keep most recent turns)
        if len(self.conversation_history) > self.max_history_turns * 2:
            self.conversation_history = self.conversation_history[-self.max_history_turns * 2:]

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=self._build_system_prompt(),
                messages=self.conversation_history
            )
            raw_response = response.content[0].text

            # ── CORRECTION DETECTION ──────────────────────────────────────────
            # Claude appends [MEMORY_UPDATE: ...] when it detects a learned preference.
            # We extract it, save it, and strip it from what Steven sees.
            if self.memory:
                from agent.memory_manager import MemoryManager
                clean_response, memory_entry = MemoryManager.extract_memory_update(raw_response)
                if memory_entry:
                    self.memory.save_preference(memory_entry)
                    logger.info(f"[Brain] Memory updated: {memory_entry[:60]}")
            else:
                clean_response = raw_response

            # Add clean response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": clean_response
            })

            logger.info(f"[Brain] Response generated ({len(clean_response)} chars)")
            return clean_response

        except anthropic.APIError as e:
            logger.error(f"[Brain] Claude API error: {e}")
            return f"API error: {str(e)}. Check Railway logs."
        except Exception as e:
            logger.error(f"[Brain] Unexpected error: {e}")
            return f"Unexpected error: {str(e)}. Check Railway logs."

    async def one_shot(self, prompt: str, context: str = "") -> str:
        """
        Single-turn call. Used for scheduled jobs (morning brief, EOD report).
        Does NOT affect conversation history.
        Memory is injected so Scout has full context even in scheduled messages.
        """
        messages = [{"role": "user", "content": f"{context}\n\n{prompt}".strip()}]
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=self._build_system_prompt(),
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[Brain] One-shot error: {e}")
            return f"Error generating response: {str(e)}"

    def clear_history(self):
        """
        Manual clear — only called when Steven explicitly asks for it.
        NOT called automatically anymore. EOD report compresses instead.
        """
        self.conversation_history = []
        logger.info("[Brain] Conversation history cleared manually.")

    def inject_context(self, context: str):
        """
        Inject important context (transcripts, lead data, etc.)
        without requiring a response. Adds to live conversation history.
        """
        self.conversation_history.append({
            "role": "user",
            "content": f"[CONTEXT UPDATE — no response needed]\n{context}"
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": "Context received and noted."
        })
