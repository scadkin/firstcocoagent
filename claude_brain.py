"""
claude_brain.py — All Claude API interactions for Scout.
Maintains conversation history, loads prompts, calls the API.
"""

import logging
import os
from pathlib import Path
import anthropic
from agent import config

logger = logging.getLogger(__name__)

# Load system prompt from file at startup
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts directory."""
    path = PROMPTS_DIR / filename
    if not path.exists():
        logger.warning(f"[Brain] Prompt file not found: {filename}")
        return ""
    return path.read_text(encoding="utf-8")


class ScoutBrain:
    """
    Manages conversation with Claude.
    Keeps a rolling history so Scout remembers context within a session.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.system_prompt = load_prompt("system.md")
        self.conversation_history = []  # Rolling message history
        self.max_history_turns = 20     # Keep last 20 exchanges to manage token cost
        logger.info("[Brain] Scout initialized. System prompt loaded.")

    async def chat(self, user_message: str) -> str:
        """
        Send a message to Claude and get Scout's response.
        Maintains conversation history for context.
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Trim history if too long (keep most recent turns)
        if len(self.conversation_history) > self.max_history_turns * 2:
            # Always keep first exchange for context, trim middle
            self.conversation_history = self.conversation_history[-self.max_history_turns * 2:]

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                messages=self.conversation_history
            )

            assistant_message = response.content[0].text

            # Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            logger.info(f"[Brain] Response generated ({len(assistant_message)} chars)")
            return assistant_message

        except anthropic.APIError as e:
            logger.error(f"[Brain] Claude API error: {e}")
            return f"API error: {str(e)}. Check Railway logs."
        except Exception as e:
            logger.error(f"[Brain] Unexpected error: {e}")
            return f"Unexpected error: {str(e)}. Check Railway logs."

    async def one_shot(self, prompt: str, context: str = "") -> str:
        """
        Single-turn call to Claude. Used for scheduled jobs (morning brief, EOD report)
        where we do not want to pollute the conversation history.
        """
        messages = [{"role": "user", "content": f"{context}\n\n{prompt}".strip()}]
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[Brain] One-shot error: {e}")
            return f"Error generating response: {str(e)}"

    def clear_history(self):
        """Reset conversation history. Call at start of each new day."""
        self.conversation_history = []
        logger.info("[Brain] Conversation history cleared.")

    def inject_context(self, context: str):
        """
        Inject important context into the conversation without requiring a response.
        Used to feed in call transcripts, lead data, etc.
        """
        self.conversation_history.append({
            "role": "user",
            "content": f"[CONTEXT UPDATE — no response needed]\n{context}"
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": "Context received and noted."
        })
