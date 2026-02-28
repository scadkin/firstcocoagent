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

**REPLY emails** (marked [REPLY]) show you both:
  1. The email Steven RECEIVED
  2. The email Steven SENT back
  This is the richest data — it shows how his tone adapts to what he's responding to.

**COLD / STANDALONE emails** (marked [COLD]) are outbound emails with no incoming context.

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

    def train(self, months_back: int = MONTHS_BACK, progress_callback=None) -> str:
        """
        Full training run. Returns the voice profile text on success,
        or an error string starting with "❌" on failure.
        """
        if progress_callback:
            progress_callback(
                f"📬 Fetching up to {MAX_EMAILS_TO_FETCH} sent emails "
                f"from the last {months_back} months..."
            )

        all_emails = self._fetch_all_emails(months_back, progress_callback)

        if not all_emails:
            return (
                "❌ No sent emails found. "
                "Make sure the GAS bridge is connected and you have sent emails "
                f"in the last {months_back} months."
            )

        reply_count = sum(1 for e in all_emails if e.get("is_reply"))
        cold_count  = len(all_emails) - reply_count

        if progress_callback:
            progress_callback(
                f"📊 Fetched {len(all_emails)} emails "
                f"({reply_count} replies with context, {cold_count} cold/standalone). "
                f"Selecting {SAMPLE_SIZE}-email sample..."
            )

        sample = self._select_sample(all_emails, count=SAMPLE_SIZE)

        if progress_callback:
            sample_replies = sum(1 for e in sample if e.get("is_reply"))
            progress_callback(
                f"🧠 Analyzing {len(sample)} emails "
                f"({sample_replies} paired reply+context) with Claude..."
            )

        profile = self._analyze_with_claude(sample)

        if not profile:
            return "❌ Claude analysis failed. Check logs."

        self._save_profile(profile)

        try:
            self.memory._commit_to_github(
                VOICE_PROFILE_PATH,
                profile,
                "[Phase 4.5] Voice profile updated — paginated fetch with thread context",
            )
        except Exception as e:
            logger.warning(f"GitHub commit failed (file still saved locally): {e}")

        sample_replies = sum(1 for e in sample if e.get("is_reply"))
        if progress_callback:
            progress_callback(
                f"✅ Voice profile built from {len(sample)} emails "
                f"({sample_replies} with reply context) and saved!"
            )

        return profile

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
        updated   = profile + f"\n\n---\n## Style Correction ({timestamp})\n{feedback}\n"
        self._save_profile(updated)

        try:
            self.memory._commit_to_github(
                VOICE_PROFILE_PATH,
                updated,
                "[Phase 4.5] Voice profile: style correction",
            )
        except Exception as e:
            logger.warning(f"GitHub commit of voice update failed: {e}")

        return True

    # ── Internal helpers ─────────────────────────────────────────

    def _fetch_all_emails(self, months_back: int, progress_callback=None) -> list[dict]:
        """
        Paginates through GAS get_sent_emails until MAX_EMAILS_TO_FETCH is reached
        or GAS says has_more=False.
        """
        all_emails = []
        page_start = 0

        while len(all_emails) < MAX_EMAILS_TO_FETCH:
            try:
                data = self.gas.get_sent_emails_page(
                    months_back=months_back,
                    page_size=PAGE_SIZE,
                    page_start=page_start,
                )
            except Exception as e:
                logger.error(f"GAS fetch failed at page_start={page_start}: {e}")
                break

            batch = data.get("emails", [])
            if not batch:
                break

            all_emails.extend(batch)

            if progress_callback and len(all_emails) % 400 == 0:
                progress_callback(f"  ↳ {len(all_emails)} emails fetched so far...")

            if not data.get("has_more", False):
                break  # GAS says we've hit the end

            page_start += PAGE_SIZE

        logger.info(f"Total emails fetched: {len(all_emails)}")
        return all_emails

    def _select_sample(self, emails: list, count: int) -> list:
        """
        Filters noise, then selects a representative sample that:
        - Prioritizes reply emails (they carry paired context — richer signal)
        - Fills remaining slots with cold emails
        - Spreads temporally across the full dataset
        """
        skip_keywords = [
            "unsubscribe", "calendar invite", "zoom.us/j/",
            "auto-reply", "out of office", "notification",
            "noreply", "no-reply", "donotreply",
        ]

        replies = []
        cold    = []

        for email in emails:
            combined = (email.get("body", "") + email.get("subject", "")).lower()
            if any(kw in combined for kw in skip_keywords):
                continue
            if len(email.get("body", "")) < 80:
                continue

            if email.get("is_reply") and email.get("incoming_context", "").strip():
                replies.append(email)
            else:
                cold.append(email)

        total_available = len(replies) + len(cold)

        # If we have fewer emails than the sample target, just use everything — no sampling needed
        if total_available <= count:
            logger.info(
                f"Pool ({total_available}) ≤ sample target ({count}) — using all emails. "
                f"({len(replies)} replies, {len(cold)} cold)"
            )
            return replies + cold

        # Target: 60% replies (richer signal), 40% cold
        reply_quota = min(int(count * 0.6), len(replies))
        cold_quota  = min(count - reply_quota, len(cold))

        # If we don't have enough of one type, fill from the other
        if reply_quota < int(count * 0.6):
            cold_quota = min(count - reply_quota, len(cold))
        if cold_quota < count - reply_quota:
            reply_quota = min(count - cold_quota, len(replies))

        # Spread evenly across each pool
        def spread_sample(pool, n):
            if len(pool) <= n:
                return pool
            step = len(pool) / n
            return [pool[int(i * step)] for i in range(n)]

        sampled = spread_sample(replies, reply_quota) + spread_sample(cold, cold_quota)
        logger.info(
            f"Sample: {len(sampled)} total "
            f"({reply_quota} replies, {cold_quota} cold) "
            f"from {len(replies)} replies + {len(cold)} cold available"
        )
        return sampled

    def _analyze_with_claude(self, emails: list) -> Optional[str]:
        """Builds the prompt and calls Claude for voice analysis."""
        email_blocks = []

        for i, email in enumerate(emails, 1):
            is_reply        = email.get("is_reply", False)
            incoming_context = email.get("incoming_context", "").strip()

            if is_reply and incoming_context:
                block = f"""--- EMAIL {i} [REPLY] ---
Subject: {email.get('subject', '(no subject)')}
To:      {email.get('to', 'unknown')}
Date:    {email.get('date', '')}

▶ INCOMING MESSAGE (what Steven received):
{incoming_context}

▶ STEVEN'S REPLY:
{email.get('body', '')}
"""
            else:
                block = f"""--- EMAIL {i} [COLD] ---
Subject: {email.get('subject', '(no subject)')}
To:      {email.get('to', 'unknown')}
Date:    {email.get('date', '')}

{email.get('body', '')}
"""
            email_blocks.append(block)

        emails_text = "\n\n".join(email_blocks)

        # Truncate if over limit (keep the most informative front portion)
        if len(emails_text) > PROMPT_CHAR_LIMIT:
            emails_text = emails_text[:PROMPT_CHAR_LIMIT] + "\n\n[... truncated to fit context window ...]"

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
