"""
agent/voice_trainer.py
Analyzes Steven's sent Gmail history (via GAS bridge) → builds a voice profile.

Phase 4.5 upgrade:
  - Fetches up to 2,000 sent emails via paginated GAS calls (10 × 200)
  - Each email now carries incoming_context — the message Steven was replying to
  - Prompt feeds Claude PAIRED context: [incoming email → Steven's reply]
  - Cold emails are still included but labeled separately
  - Sample size raised from 40 to 80; Claude token budget raised to 120K chars
  - Voice profile saved to memory/voice_profile.md and committed to GitHub
"""

import os
import logging
from typing import Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Tuning knobs ────────────────────────────────────────────────────────────
MAX_EMAILS_TO_FETCH  = 2000   # Upper bound across all pages
PAGE_SIZE            = 200    # Threads per GAS call (GAS caps at 200)
SAMPLE_SIZE          = 80     # How many emails Claude actually reads
PROMPT_CHAR_LIMIT    = 120_000  # Claude opus-4-5 supports 200K tokens; 120K chars is safe
MONTHS_BACK          = 12     # How far back to pull history (increased from 6)
# ────────────────────────────────────────────────────────────────────────────

VOICE_PROFILE_PATH = "memory/voice_profile.md"


VOICE_ANALYSIS_PROMPT = """You are analyzing a sales rep's email writing style to build a precise, actionable voice profile.

The rep is Steven — Senior Sales Rep at CodeCombat, selling K-12 CS curriculum to school districts.

Below are {count} emails. They come in two formats:

REPLY emails (marked [REPLY]) show you both:
  1. The email Steven RECEIVED
  2. The email Steven SENT back
  This is the richest data — it shows how his tone adapts to what he's responding to.

COLD / STANDALONE emails (marked [COLD]) are outbound emails with no incoming context.

Study both carefully. Produce a detailed, actionable voice profile:

---

# Steven's Email Voice Profile

## Tone & Personality
(How does he come across? Warm, direct, casual, formal? What's the overall vibe?)

## Tone Matching in Replies
(How does his tone shift based on what he receives? Formal reply → formal Steven? Casual → casual? Does he mirror or lead?)

## Sentence Structure
(Short sentences? Long? Mix? Fragments? How does pacing feel?)

## Opening Style
(How does he typically start emails — both cold and replies? Quote examples.)

## Closing / CTA Style
(How does he end emails? What CTAs does he use? How assertive vs. soft?)

## Sign-off
(Exact sign-off lines he uses — e.g., "Best," "Talk soon," "Thanks,")

## Punctuation & Formatting Habits
(Bullet points? Em dashes? Ellipses? Bold? How sparingly or liberally?)

## Subject Line Style
(Short? Question? Action-oriented? Quote real examples where possible.)

## What He Avoids
(Patterns notably absent — e.g., no fluff, no jargon, no walls of text)

## Key Phrases He Uses
(5-10 specific phrases or constructions that feel distinctly "him")

## Length & Structure
(Typical email length? Paragraphs vs. lists? White space? Cold vs. reply differences?)

## Cold vs. Reply vs. Follow-up Differences
(How does his approach differ across email types? Be specific — quote examples.)

---

Be specific. Quote actual phrases when useful. This profile will be used to generate emails that sound exactly like Steven.

---

EMAILS TO ANALYZE:

{emails}
"""


class VoiceTrainer:
    """
    Reads Steven's sent emails via GAS bridge (paginated),
    builds a paired-context training set, analyzes with Claude,
    and saves the voice profile to memory/voice_profile.md.
    """

    def __init__(self, gas_bridge, memory_manager):
        self.gas    = gas_bridge
        self.memory = memory_manager
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── Public API ────────────────────────────────────────────────
