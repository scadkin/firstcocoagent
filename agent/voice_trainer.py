"""
agent/voice_trainer.py
Analyzes Steven's sent Gmail history (via GAS bridge) → builds a voice profile.
Voice profile saved to memory/voice_profile.md and committed to GitHub.
"""

import os
import logging
from typing import Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMAILS_FOR_ANALYSIS = 40
VOICE_PROFILE_PATH = "memory/voice_profile.md"


VOICE_ANALYSIS_PROMPT = """You are analyzing a sales rep's email writing style to build a precise voice profile.

The rep is Steven — a Senior Sales Rep at CodeCombat, selling K-12 CS curriculum to school districts.

Below are {count} of his actual sent emails. Analyze them carefully and produce a detailed, actionable voice profile with these exact sections:

---

# Steven's Email Voice Profile

## Tone & Personality
(How does he come across? Warm, direct, casual, formal? What's his vibe?)

## Sentence Structure
(Short sentences? Long? Mix? Does he use fragments? How does pacing feel?)

## Opening Style
(How does he typically start emails? Examples from the sample.)

## Closing / CTA Style
(How does he end emails? What CTAs does he use? How assertive vs soft?)

## Sign-off
(Exact sign-off line(s) he uses — e.g., "Best," "Talk soon," "Thanks,")

## Punctuation & Formatting Habits
(Does he use bullet points? Em dashes? Ellipses? Bold? How sparingly or freely?)

## Subject Line Style
(How does he write subject lines? Short? Question? Action-oriented?)

## What He Avoids
(Patterns notably absent — e.g., no fluff, no jargon, no long paragraphs)

## Key Phrases He Uses
(3-8 specific phrases or constructions that feel distinctly "him")

## Length & Structure
(Typical email length? Paragraphs or lists? How much white space?)

## Cold vs Warm Email Differences
(If detectable: how does tone shift for cold outreach vs replies vs follow-ups?)

---

Be specific. Quote actual phrases from his emails where useful. This profile will be used to generate emails that sound exactly like him.

---

EMAILS TO ANALYZE:

{emails}
"""


class VoiceTrainer:
    """
    Reads Steven's sent emails via GAS bridge, analyzes with Claude,
    saves voice profile to memory/voice_profile.md.
    """

    def __init__(self, gas_bridge, memory_manager):
        self.gas = gas_bridge
        self.memory = memory_manager
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)

    def train(self, months_back: int = 6, progress_callback=None) -> str:
        if progress_callback:
            progress_callback("📬 Fetching your sent emails from Gmail...")

        emails = self.gas.get_sent_emails(months_back=months_back, max_results=200)

        if not emails:
            return "❌ No sent emails found. Make sure the GAS bridge is connected and you have sent emails in the last 6 months."

        if progress_callback:
            progress_callback(f"📊 Found {len(emails)} sent emails. Selecting sample for analysis...")

        sample = self._select_sample(emails, count=EMAILS_FOR_ANALYSIS)

        if progress_callback:
            progress_callback(f"🧠 Analyzing {len(sample)} emails with Claude to build your voice profile...")

        profile = self._analyze_with_claude(sample)

        if not profile:
            return "❌ Claude analysis failed. Check logs."

        self._save_profile(profile)

        try:
            self.memory._commit_to_github(
                VOICE_PROFILE_PATH,
                profile,
                "[Phase 3] Voice profile updated from Gmail analysis",
            )
        except Exception as e:
            logger.warning(f"GitHub commit failed (file still saved locally): {e}")

        if progress_callback:
            progress_callback(f"✅ Voice profile built from {len(sample)} emails and saved!")

        return profile

    def _select_sample(self, emails: list, count: int) -> list:
        skip_keywords = [
            "unsubscribe", "calendar invite", "zoom.us/j/",
            "auto-reply", "out of office", "notification",
            "noreply", "no-reply", "donotreply",
        ]
        filtered = []
        for email in emails:
            combined = (email.get("body", "") + email.get("subject", "")).lower()
            if any(kw in combined for kw in skip_keywords):
                continue
            if len(email.get("body", "")) < 80:
                continue
            filtered.append(email)

        if len(filtered) <= count:
            return filtered
        step = len(filtered) // count
        return [filtered[i] for i in range(0, len(filtered), step)][:count]

    def _analyze_with_claude(self, emails: list) -> Optional[str]:
        email_blocks = []
        for i, email in enumerate(emails, 1):
            block = f"""--- EMAIL {i} ---
To: {email.get('to', 'unknown')}
Subject: {email.get('subject', '(no subject)')}
Date: {email.get('date', '')}

{email.get('body', '')}
"""
            email_blocks.append(block)

        emails_text = "\n\n".join(email_blocks)
        if len(emails_text) > 80000:
            emails_text = emails_text[:80000] + "\n\n[... truncated ...]"

        prompt = VOICE_ANALYSIS_PROMPT.format(count=len(emails), emails=emails_text)

        try:
            response = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude voice analysis failed: {e}")
            return None

    def _save_profile(self, profile: str):
        os.makedirs("memory", exist_ok=True)
        with open(VOICE_PROFILE_PATH, "w", encoding="utf-8") as f:
            f.write(profile)
        logger.info(f"Voice profile saved to {VOICE_PROFILE_PATH}")

    def load_profile(self) -> Optional[str]:
        if not os.path.exists(VOICE_PROFILE_PATH):
            return None
        with open(VOICE_PROFILE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def update_profile_from_feedback(self, feedback: str) -> bool:
        profile = self.load_profile()
        if not profile:
            return False

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        updated = profile + f"\n\n---\n## Style Correction ({timestamp})\n{feedback}\n"
        self._save_profile(updated)

        try:
            self.memory._commit_to_github(
                VOICE_PROFILE_PATH,
                updated,
                "[Phase 3] Voice profile: style correction",
            )
        except Exception as e:
            logger.warning(f"GitHub commit of voice update failed: {e}")

        return True
