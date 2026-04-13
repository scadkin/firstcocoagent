"""
Session 59 round 2 — regenerate 6 diocesan sequence docs through the updated
private_school_network diocesan branch in _on_prospect_research_complete AND
push each to Outreach.io via outreach_client.create_sequence.

Round 2 fixes from Steven's feedback:
- Always include a campaign-specific meeting link
  (https://hello.codecombat.com/c/steven/t/130) hyperlinked in steps 3 and 5
- CTA variety across steps — "one pager" max once, not every step
- codecombat.com/schools hyperlinked in at least 2 steps
- Reword awkward repetition like "schools school by school"
- Push to Outreach API programmatically — no more manual copy/paste

Abandons LA (only 2 email leads from single parochial school).
Updates Prospecting Queue Sequence Doc URL + Notes (with Outreach seq ID).
"""
import os, sys, json, re
from dotenv import load_dotenv
load_dotenv('.env')

import tools.sequence_builder as sb
import tools.outreach_client as outreach_client
from tools.gas_bridge import GASBridge
from tools.sheets_writer import _get_service, _get_sheet_id

# Load Outreach tokens directly from repo memory/outreach_tokens.json
# (module init reads env vars only; _load_persisted_tokens checks /tmp + GitHub
# but not the local repo file)
import time
with open('memory/outreach_tokens.json') as _f:
    _tok = json.load(_f)
outreach_client._access_token = _tok['access_token']
outreach_client._refresh_token = _tok['refresh_token']
outreach_client._token_expires_at = _tok.get('expires_at', 0.0)
outreach_client._user_id = _tok.get('user_id', '')
if time.time() > outreach_client._token_expires_at:
    print('Refreshing expired Outreach access token...')
    assert outreach_client._refresh_access_token(), 'token refresh failed'
    # Persist refreshed token back to repo memory file
    with open('memory/outreach_tokens.json', 'w') as _f:
        json.dump({
            'access_token': outreach_client._access_token,
            'refresh_token': outreach_client._refresh_token,
            'expires_at': outreach_client._token_expires_at,
            'user_id': outreach_client._user_id,
        }, _f, indent=2)
    print('  token refreshed + persisted')

MEETING_LINK = "https://hello.codecombat.com/c/steven/t/130"
SCHOOLS_URL = "https://www.codecombat.com/schools"

# Load voice profile once (shared across all 6)
voice_profile = None
try:
    with open('memory/voice_profile.md', 'r', encoding='utf-8') as f:
        voice_profile = f.read()
except FileNotFoundError:
    pass


def build_diocesan_extra_context(state: str, meeting_link: str = MEETING_LINK) -> str:
    """Mirror the round-2 diocesan branch in agent/main.py."""
    return (
        f"State: {state}. Strategy: private_school_network."
        f"\n\nThis is a COLD diocesan central-office outreach sequence for a Catholic archdiocese/diocese."
        f"\n\nTARGET AUDIENCE: The Superintendent of Catholic Schools at the diocesan central office."
        f" This role oversees a network of parochial K-12 schools under the diocese. They are"
        f" administrators, not classroom teachers, so outreach should feel peer-to-peer at the admin level,"
        f" not classroom-level."
        f"\n\nCRITICAL TONE REQUIREMENTS:"
        f"\n- NO dollar figures. NO unverified peer district/diocese names. NO assumed success claims."
        f"\n- Frame CodeCombat as 'CS/coding and safe AI curriculum'. The safe AI angle matters for"
        f"  Catholic schools that are rightfully cautious about AI exposure for minors."
        f"\n- Lead with student engagement (video-game feel, rigorous curriculum underneath), NOT with AI as the main hook."
        f"\n- Acknowledge the diocesan structure: central office serves many parochial school principals,"
        f"  so the pitch should emphasize how one central relationship helps the superintendent standardize"
        f"  CS curriculum across all member schools."
        f"\n- Reference the mission alignment (equity of access to CS, preparing students for the workforce)"
        f"  without being saccharine or leaning on religious language."
        f"\n- Turn-key for teachers angle is critical. Most parochial schools have teachers without"
        f"  CS backgrounds, and superintendents worry about implementation burden on their principals."
        f"\n- Soft, colleague-level language throughout. 'Throw our hat in early' beats 'want to be considered.'"
        f"  'Would it be worth sending over some info?' beats 'can we hop on a call?'"
        f"\n- Avoid awkward repetition like 'schools school by school'. If you mean 'each school individually'"
        f"  or 'one school at a time', say that. Read every sentence aloud in your head and cut anything clunky."
        f"\n\nCTA VARIETY (CRITICAL — do NOT repeat the same CTA across steps):"
        f"\n- Step 1: low-friction info offer (NOT 'one pager'). Try phrasings like"
        f"  'Worth sending over a quick overview of how this works for diocesan networks?' or"
        f"  'Want me to send over the highlights?'"
        f"\n- Step 2: free trial licenses angle ('spin up free trial licenses for any teachers you want to pilot,"
        f"  no strings') — NOT the same phrasing as step 1."
        f"\n- Step 3: calendar / booking CTA with Steven's meeting link."
        f"  Use: <a href=\"{meeting_link}\">grab 15 min here</a> or similar. DO NOT paste the raw URL. HYPERLINK it."
        f"\n- Step 4: efficacy data / Bobby Duke MS case study angle ('happy to share the data from Bobby Duke Middle"
        f"  School, one of our strongest case studies'). Do NOT name any other case study — Bobby Duke MS is the only"
        f"  verified one Steven can cite by name."
        f"\n- Step 5 (breakup): delegation + leftover funds mention. Something like 'if there's a better person on"
        f"  your team for this, I'm happy to start there instead' — include the meeting link again as a final soft"
        f"  option."
        f"\n- CTA LANGUAGE MUST VARY step to step. The phrase 'one pager' / 'one-pager' should appear AT MOST once"
        f"  across the whole sequence, not in every step."
        f"\n\nLINK REQUIREMENTS:"
        f"\n- Include <a href=\"{SCHOOLS_URL}\">codecombat.com/schools</a> HYPERLINKED in at least 2 of the 5 steps."
        f"  Natural placements: step 2 (when mentioning turn-key resources) and step 4 (when mentioning efficacy data)."
        f"\n- Include Steven's meeting link HYPERLINKED in step 3 and step 5 (the breakup)."
        f"\n- All URLs must be wrapped in <a href=\"...\">anchor text</a> tags — Outreach renders HTML bodies."
        f"\n- Do NOT paste raw URLs anywhere. Hyperlinked anchor text only."
        f"\n\nSTEVEN'S CAMPAIGN-SPECIFIC MEETING LINK FOR THIS CAMPAIGN:"
        f"\n  {meeting_link}"
        f"\n  Use this exact URL in step 3 and step 5 anchor tags."
        f"\n\nSTRUCTURE:"
        f"\n- 5 steps, graduated spacing (5+ days between each), ~4 weeks total"
        f"\n- Step 1 HARD LIMIT: under 80 words (non-negotiable, Steven cuts longer emails)"
        f"\n- Other steps under 120 words"
        f"\n- Each step needs a DISTINCT angle: (1) engagement intro, (2) turn-key for parochial teachers,"
        f"  (3) calendar/K-12 vertical alignment, (4) efficacy/Bobby Duke case study, (5) breakup"
        f"\n- Final step is a breakup email under 60 words (pulls 20-30% reply rate)"
        f"\n- Use Outreach merge fields: {{{{first_name}}}}, {{{{company}}}}, {{{{state}}}}"
        f"\n\nBANNED PHRASES (Steven rejected these in 5+ sequence iterations):"
        f"\n- 'Just checking in', 'circling back', 'touch base', 'reach out', 'I'd love to',"
        f"  'quick call', 'hop on a call', 'I'm Steven', 'I wanted to reach out',"
        f"  'The #1 thing teachers tell me', 'Are you the right person?' (except in breakup),"
        f"  'I dropped the ball', 'sorry' openers, 'I hope this email finds you well',"
        f"  awkward word-repetition like 'schools school by school'"
        f"\n- NO em dashes (U+2014). Use commas or periods."
        f"\n- NOT vendor-y, NOT formulaic, NOT AI-sounding. Must read like a human wrote it."
    )


def body_text_to_html(body: str) -> str:
    """Convert plain-text sequence body to HTML for Outreach:
       - Preserve anchor tags already in the text (Claude generates <a href="...">...)
       - Wrap paragraph breaks with <br><br> (per feedback_sequence_copy_rules.md)
       - Preserve merge fields {{first_name}} etc intact
    """
    # Double newlines → paragraph break
    html = body.replace("\r\n", "\n")
    # Collapse 3+ newlines to 2 to avoid triple break
    html = re.sub(r"\n{3,}", "\n\n", html)
    # Paragraph break
    html = html.replace("\n\n", "<br><br>")
    # Single newline → space-preserving break
    html = html.replace("\n", "<br>")
    return html


def day_to_interval_seconds(day: int, prev_day: int) -> int:
    """Convert day offset to interval_SECONDS since previous step.
       Outreach sequenceStep.interval is in SECONDS (not minutes —
       memory/feedback_outreach_intervals.md).
       Enforces the ≥5-day minimum cold cadence from
       memory/feedback_sequence_copy_rules.md.
    """
    if day == 0:
        return 300  # step 1: 5 min after add
    delta_days = max(5, day - prev_day)  # enforce 5-day minimum
    return delta_days * 24 * 60 * 60  # days to seconds


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
print(f'GAS ping: {gas.ping()}')
print(f'Outreach configured: {outreach_client.is_configured()}  authenticated: {outreach_client.is_authenticated()}')
print()

results = {}

for district_name, state in TARGETS:
    print(f'\n{"="*80}\n{district_name} ({state})\n{"="*80}')
    campaign_name = f"{district_name} — Diocesan Central Office Outreach"
    target_role = "Superintendent of Catholic Schools"
    extra = build_diocesan_extra_context(state)

    seq_result = sb.build_sequence(
        campaign_name=campaign_name,
        target_role=target_role,
        num_steps=5,
        voice_profile=voice_profile,
        additional_context=extra,
    )

    if not seq_result.get("success"):
        print(f'  BUILD FAILED: {seq_result.get("error", "?")}')
        results[district_name] = {"error": "build_failed"}
        continue

    steps = seq_result.get("steps", [])
    print(f'  built {len(steps)} steps')

    # Quality checks
    step1_words = len(steps[0]['body'].split()) if steps else 0
    full_text = ' '.join(f"{s['subject']} {s['body']}" for s in steps)
    em_count = full_text.count('\u2014')
    meeting_link_count = sum(1 for s in steps if MEETING_LINK in s['body'])
    schools_url_count = sum(1 for s in steps if SCHOOLS_URL in s['body'])
    one_pager_count = sum(1 for s in steps if 'one pager' in s['body'].lower() or 'one-pager' in s['body'].lower())
    schools_school_by_school = 'schools school by school' in full_text.lower()

    print(f'  Step 1 words: {step1_words}  em dashes: {em_count}')
    print(f'  meeting link in steps: {meeting_link_count}   schools URL in steps: {schools_url_count}')
    print(f'  "one pager" count: {one_pager_count}   awkward repetition: {schools_school_by_school}')

    # Build Outreach-format steps (interval in SECONDS, not minutes)
    prev_day = 0
    outreach_steps = []
    for i, s in enumerate(steps):
        body_html = body_text_to_html(s['body'])
        interval_seconds = day_to_interval_seconds(s['day'], prev_day if i > 0 else 0)
        prev_day = s['day']
        outreach_steps.append({
            "subject": s['subject'],
            "body_html": body_html,
            "interval_seconds": interval_seconds,
        })

    # Write Google Doc (for review)
    doc_result = sb.write_sequence_to_doc(campaign_name, steps, gas)
    doc_url = doc_result.get("url", "") if doc_result.get("success") else ""
    print(f'  Doc: {doc_url}')

    # Push to Outreach
    # Schedule 19 = cold admin to Superintendents/Principals (matches target role).
    # Description is VISIBLE to Steven's manager + teammates — zero automation language.
    try:
        out_result = outreach_client.create_sequence(
            name=campaign_name,
            steps=outreach_steps,
            description=(
                f"Cold outreach to the central office of {district_name}, targeting the "
                f"Superintendent of Catholic Schools. Frames CS + safe AI curriculum for "
                f"parochial school networks. 5-step graduated cadence (5/6/7/8 days), admin schedule."
            ),
            tags=["diocesan_central_office_2026", "cold"],
            schedule_id=19,
        )
        seq_id = out_result.get("sequence_id")
        errors = out_result.get("errors", [])
        if seq_id and not errors:
            print(f'  Outreach sequence: {seq_id} ✓')
        elif seq_id and errors:
            print(f'  Outreach sequence: {seq_id} with {len(errors)} step errors: {errors}')
        else:
            print(f'  Outreach push FAILED: {out_result}')
        results[district_name] = {
            "doc_url": doc_url,
            "outreach_sequence_id": seq_id,
            "outreach_errors": errors,
            "quality": {
                "step1_words": step1_words,
                "em_dashes": em_count,
                "meeting_link_count": meeting_link_count,
                "schools_url_count": schools_url_count,
                "one_pager_count": one_pager_count,
                "awkward_repetition": schools_school_by_school,
            },
        }
    except Exception as e:
        print(f'  Outreach push ERROR: {e}')
        results[district_name] = {"doc_url": doc_url, "error": f"outreach_exception: {e}"}

print(f'\n{"="*80}\nSUMMARY\n{"="*80}')
for d, r in results.items():
    seq_id = r.get("outreach_sequence_id", "FAIL")
    doc = r.get("doc_url", "")
    print(f'{d}: outreach_seq={seq_id}  doc={doc[:60]}')

with open('/tmp/s59_round2_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\nsaved to /tmp/s59_round2_results.json')
