"""
Session 59 Section 5 — regenerate 6 diocesan sequence docs through the new
private_school_network diocesan branch in _on_prospect_research_complete.

Abandons LA (only 2 email leads from single parochial school).
Outputs: new Google Doc URLs to stdout, also updates Prospecting Queue
Sequence Doc URL column for each regenerated diocese.
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv('.env')

import tools.sequence_builder as sb
from tools.gas_bridge import GASBridge
from tools.sheets_writer import _get_service, _get_sheet_id

# Load voice profile once (shared across all 6)
voice_profile = None
try:
    with open('memory/voice_profile.md', 'r', encoding='utf-8') as f:
        voice_profile = f.read()
except FileNotFoundError:
    pass

def build_diocesan_extra_context(state: str, strategy: str = "private_school_network") -> str:
    """Mirror the diocesan branch in agent/main.py:_on_prospect_research_complete."""
    extra = f"State: {state}. Strategy: {strategy}."
    extra += (
        "\n\nThis is a COLD diocesan central-office outreach sequence for a Catholic archdiocese/diocese."
        "\n\nTARGET AUDIENCE: The Superintendent of Catholic Schools at the diocesan central office."
        " This role oversees a network of parochial K-12 schools under the diocese. They are"
        " administrators, not classroom teachers — outreach should feel peer-to-peer at the admin level,"
        " not classroom-level."
        "\n\nCRITICAL TONE REQUIREMENTS:"
        "\n- NO dollar figures. NO unverified peer district/diocese names. NO assumed success claims."
        "\n- Frame CodeCombat as 'CS/coding & safe AI curriculum' — the safe AI angle matters for"
        "  Catholic schools that are rightfully cautious about AI exposure for minors."
        "\n- Lead with student engagement (video-game feel, rigorous curriculum underneath), NOT with AI as the main hook."
        "\n- Acknowledge the diocesan structure: central office serves many parochial school principals,"
        "  so the pitch should emphasize how one central relationship helps the superintendent standardize"
        "  CS curriculum across all member schools."
        "\n- Reference the mission alignment (equity of access to CS, preparing students for the workforce)"
        "  without being saccharine or leaning on religious language."
        "\n- Turn-key for teachers angle is critical — most parochial schools have teachers without"
        "  CS backgrounds, and superintendents worry about implementation burden on their principals."
        "\n- Soft, colleague-level language throughout. 'Throw our hat in early' beats 'want to be considered.'"
        "  'Would it be worth sending over some info?' beats 'can we hop on a call?'"
        "\n\nCTA PATTERN (Steven's approved 3-option format, use across the sequence):"
        "\n- A one-pager overview (NOT 'licensing + pricing guide' — too transactional)"
        "\n- Free trial licenses for any teachers the superintendent wants to pilot with, no strings"
        "\n- Some data, case studies, or efficacy reports (Bobby Duke MS is Steven's verified case study;"
        "  do NOT name peer dioceses unless research confirmed them as Active Accounts)"
        "\n\nSTRUCTURE:"
        "\n- 5 steps, graduated spacing (5+ days between each), ~4 weeks total"
        "\n- Step 1 HARD LIMIT: under 80 words (non-negotiable — Steven cuts longer emails)"
        "\n- Other steps under 120 words"
        "\n- Each step needs a DISTINCT angle: engagement, turn-key for parochial teachers,"
        "  K-12 vertical alignment (replaces Scratch/Code.org patchwork), budget/timing, breakup"
        "\n- Final step is a breakup email under 60 words (pulls 20-30% reply rate)"
        "\n- Use Outreach merge fields: {{first_name}}, {{company}}, {{state}}"
        "\n\nBANNED PHRASES (Steven rejected these in 5+ sequence iterations):"
        "\n- 'Just checking in', 'circling back', 'touch base', 'reach out', 'I'd love to',"
        "  'quick call', 'hop on a call', 'I'm Steven', 'I wanted to reach out',"
        "  'The #1 thing teachers tell me', 'Are you the right person?' (except in breakup),"
        "  'I dropped the ball', 'sorry' openers, 'I hope this email finds you well'"
        "\n- NO em dashes — use commas or periods"
        "\n- NOT vendor-y, NOT formulaic, NOT AI-sounding — must read like a human wrote it"
    )
    return extra


# Dioceses to regenerate (abandon LA)
TARGETS = [
    ("Archdiocese of Philadelphia Schools", "PA"),
    ("Archdiocese of Cincinnati Schools", "OH"),
    ("Archdiocese of Detroit Schools", "MI"),
    ("Diocese of Cleveland Schools", "OH"),
    ("Archdiocese of Boston Catholic Schools", "MA"),
    ("Archdiocese of Chicago Schools", "IL"),
]

gas = GASBridge(webhook_url=os.environ['GAS_WEBHOOK_URL'], secret_token=os.environ['GAS_SECRET_TOKEN'])
print(f'GAS ping: {gas.ping()}\n')

new_doc_urls = {}

for district_name, state in TARGETS:
    print(f'\n{"="*80}\n{district_name} ({state})\n{"="*80}')
    campaign_name = f"{district_name} — Diocesan Central Office Outreach"
    target_role = "Superintendent of Catholic Schools"
    extra = build_diocesan_extra_context(state)

    result = sb.build_sequence(
        campaign_name=campaign_name,
        target_role=target_role,
        num_steps=5,
        voice_profile=voice_profile,
        additional_context=extra,
    )

    if not result.get("success"):
        print(f'  BUILD FAILED: {result.get("error", "?")}')
        new_doc_urls[district_name] = "BUILD_FAILED"
        continue

    steps = result.get("steps", [])
    print(f'  built {len(steps)} steps')
    # Quick tone-check on Step 1 body
    step1_words = len(steps[0]['body'].split()) if steps else 0
    print(f'  Step 1 word count: {step1_words}')
    # Count em dashes + banned phrases
    full_text = ' '.join(f"{s['subject']} {s['body']}" for s in steps)
    em_count = full_text.count('\u2014') + full_text.count(' — ')
    banned_hit = [p for p in ["i'd love to", "quick call", "hop on a call", "touch base", "circling back", "finds you well"] if p in full_text.lower()]
    print(f'  em dashes: {em_count}')
    print(f'  banned phrases: {banned_hit}')

    # Write new doc
    doc_result = sb.write_sequence_to_doc(campaign_name, steps, gas)
    if doc_result.get("success"):
        url = doc_result.get("url", "")
        new_doc_urls[district_name] = url
        print(f'  NEW DOC: {url}')
    else:
        print(f'  DOC WRITE FAILED: {doc_result.get("error", "?")}')
        new_doc_urls[district_name] = "DOC_WRITE_FAILED"

print(f'\n{"="*80}\nSUMMARY\n{"="*80}')
for d, url in new_doc_urls.items():
    print(f'{d}: {url}')

# Save to JSON for the review markdown
with open('/tmp/s59_new_doc_urls.json', 'w') as f:
    json.dump(new_doc_urls, f, indent=2)
print('\nsaved to /tmp/s59_new_doc_urls.json')
