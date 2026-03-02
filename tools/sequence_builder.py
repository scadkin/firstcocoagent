"""
tools/sequence_builder.py
Phase 6A: Campaign Engine — builds multi-step cold email sequences in Steven's voice.

Sequences are output as a Google Doc (via GAS bridge) that Steven copies into Outreach.io.
Each step supports an optional A/B variant for subject line / body testing.
"""

import json
import logging
import os
from datetime import datetime
import pytz
from anthropic import Anthropic

logger = logging.getLogger(__name__)

client = Anthropic()

# ── Paths ───────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_PATH = os.path.join(_HERE, "prompts", "sequence_templates.md")
# Strip any URL query params (e.g. "?ths=true") — Railway value may be pasted from browser URL
SEQUENCES_FOLDER_ID = os.environ.get("SEQUENCES_FOLDER_ID", "").split("?")[0].strip()

# ── Products reference (from system.md) ─────────────────────────────────────

PRODUCTS_REFERENCE = """
CodeCombat K-12 CS + AI Suite:
1. CodeCombat Classroom — game-based CS (Python, JS, Lua), Grades 6-12
2. Ozaria — narrative RPG CS for middle school
3. CodeCombat Junior — block-based coding K-5
4. AI HackStack — hands-on AI literacy curriculum
5. AI Junior — AI curriculum K-8
6. CodeCombat AI League — Esports coding tournaments
7. CodeCombat Worlds on Roblox — CS learning in Roblox
8. AP CSP Course — full College Board AP CS Principles course

Standards aligned: CSTA, ISTE, California CS Standards, NGSS. Turnkey teacher resources included.
"""

# ── Prompt ──────────────────────────────────────────────────────────────────

SEQUENCE_SYSTEM = """You are an expert cold email copywriter for Steven, a Senior Sales Rep at CodeCombat.

You write multi-step email sequences for Outreach.io. Your job is to write emails that:
- Sound like Steven — direct, knowledgeable, peer-to-peer, never vendor-y
- Are short and scannable (most emails under 120 words)
- Lead with value, not product features
- Use Outreach.io merge fields: {{first_name}}, {{district}}, {{title}}
- Have compelling, low-spam subject lines (under 50 chars when possible)
- Get replies and booked calls

Return ONLY a valid JSON array. No explanation, no markdown fences, no preamble.

Each step object must have these exact keys:
{
  "step": <integer, 1-based>,
  "day": <integer, send day offset from day 0>,
  "label": "<short descriptor, e.g. 'Cold intro', 'Value-add', 'Social proof', 'Break-up'>",
  "subject": "<email subject line>",
  "body": "<full email body with merge fields>",
  "variant_b_subject": "<alternative subject line, or empty string if no variant>",
  "variant_b_body": "<alternative body, or empty string if no variant>"
}

Rules:
- body and variant_b_body must be plain text (no HTML, no markdown)
- Include a PS line sparingly — only when it adds real value
- Sign-off: "Steven" or "- Steven"
- Keep subject lines out of all-caps
- Never start with "I hope this email finds you well" or similar filler
- Always end the last step with a soft close, not a hard sell
"""


def _load_templates() -> str:
    """Load sequence templates from prompts/sequence_templates.md."""
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("sequence_templates.md not found — building without templates")
        return ""


def build_sequence(
    campaign_name: str,
    target_role: str,
    focus_product: str = "CodeCombat AI Suite",
    num_steps: int = 5,
    voice_profile: str = None,
    additional_context: str = "",
    ab_variants: bool = True,
) -> dict:
    """
    Build a multi-step cold email sequence in Steven's voice.

    Returns:
        {
            success: bool,
            steps: [{step, day, label, subject, body, variant_b_subject, variant_b_body}],
            raw: str,
            error: str,
        }
    """
    templates = _load_templates()

    voice_section = ""
    if voice_profile:
        voice_section = f"\n\n## Steven's Voice Profile\n{voice_profile[:3000]}"

    ab_instruction = (
        "Generate A/B variant subject lines and opening lines for steps 1, 2, and 3 "
        "(populate variant_b_subject and variant_b_body). For all other steps, leave "
        "variant_b_subject and variant_b_body as empty strings."
        if ab_variants
        else "Leave variant_b_subject and variant_b_body as empty strings for all steps."
    )

    user_prompt = f"""Build a {num_steps}-step cold email sequence.

Campaign: {campaign_name}
Target role: {target_role}
Primary product to highlight: {focus_product}
{f'Additional context: {additional_context}' if additional_context else ''}

## CodeCombat Products
{PRODUCTS_REFERENCE}

## Sequence Templates (structural guidance)
{templates}
{voice_section}

## Instructions
- Pick the archetype from the templates that best fits "{target_role}" and follow its structure
- If {num_steps} is more than the archetype steps, extend with nurture/re-engagement steps
- {ab_instruction}
- Return exactly {num_steps} step objects in a JSON array
- Day offsets should feel natural (not every 3 days mechanically)
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SEQUENCE_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if Claude added them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

        steps = json.loads(raw)

        # Normalize: ensure all required fields exist
        normalized = []
        for s in steps:
            normalized.append({
                "step": int(s.get("step", len(normalized) + 1)),
                "day": int(s.get("day", 0)),
                "label": str(s.get("label", "")),
                "subject": str(s.get("subject", "")),
                "body": str(s.get("body", "")),
                "variant_b_subject": str(s.get("variant_b_subject", "")),
                "variant_b_body": str(s.get("variant_b_body", "")),
            })

        return {"success": True, "steps": normalized, "raw": raw, "error": ""}

    except json.JSONDecodeError as e:
        logger.error(f"sequence_builder: JSON parse error: {e}\nRaw: {raw[:500]}")
        return {"success": False, "steps": [], "raw": raw, "error": f"JSON parse error: {e}"}
    except Exception as e:
        logger.error(f"sequence_builder: build_sequence failed: {e}")
        return {"success": False, "steps": [], "raw": "", "error": str(e)}


def write_sequence_to_doc(
    campaign_name: str,
    steps: list,
    gas_bridge,
    folder_id: str = None,
) -> dict:
    """
    Write a sequence to a Google Doc via the GAS bridge.
    Steven copies the content into Outreach.io manually.

    Returns:
        {success: bool, url: str, error: str}
    """
    if not gas_bridge:
        return {"success": False, "url": "", "error": "GAS bridge not available"}

    cst = pytz.timezone("America/Chicago")
    now_cst = datetime.now(cst)
    today = now_cst.strftime("%Y-%m-%d")
    time_str = now_cst.strftime("%I:%M %p CST").lstrip("0")
    doc_title = f"Sequence — {campaign_name} — {today}"

    lines = [
        f"# {campaign_name}",
        f"Generated: {today} at {time_str}",
        f"Steps: {len(steps)}",
        "",
        "---",
        "",
        "MERGE FIELDS: {{first_name}} | {{district}} | {{title}}",
        "",
        "---",
        "",
    ]

    for step in steps:
        lines.append(f"## Step {step['step']} — Day {step['day']} — {step['label']}")
        lines.append("")
        lines.append(f"Subject: {step['subject']}")
        lines.append("")
        lines.append(step["body"])
        lines.append("")

        if step.get("variant_b_subject") or step.get("variant_b_body"):
            lines.append(f"--- Variant B ---")
            if step.get("variant_b_subject"):
                lines.append(f"Subject B: {step['variant_b_subject']}")
                lines.append("")
            if step.get("variant_b_body"):
                lines.append(step["variant_b_body"])
                lines.append("")

        lines.append("---")
        lines.append("")

    content = "\n".join(lines)

    try:
        result = gas_bridge.create_google_doc(
            title=doc_title,
            content=content,
            folder_id=SEQUENCES_FOLDER_ID,
        )
        url = result.get("url", "")
        logger.info(f"Sequence doc created: {doc_title} → {url}")
        return {"success": True, "url": url, "error": ""}
    except Exception as e:
        logger.error(f"sequence_builder: write_sequence_to_doc failed: {e}")
        return {"success": False, "url": "", "error": str(e)}


def format_for_telegram(campaign_name: str, steps: list) -> str:
    """
    Format a sequence for Telegram preview.
    Shows step number, day, label, subject, and first ~150 chars of body.
    A/B variants noted inline.
    """
    lines = [f"*{campaign_name}* — {len(steps)}-step sequence\n"]

    for step in steps:
        lines.append(
            f"*Step {step['step']} · Day {step['day']} · {step['label']}*"
        )
        lines.append(f"Subject: _{step['subject']}_")

        # Truncate body preview
        body_preview = step["body"].replace("\n", " ").strip()
        if len(body_preview) > 150:
            body_preview = body_preview[:147] + "..."
        lines.append(body_preview)

        if step.get("variant_b_subject"):
            lines.append(f"_B: {step['variant_b_subject']}_")

        lines.append("")

    return "\n".join(lines).strip()
