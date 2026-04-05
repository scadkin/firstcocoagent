#!/usr/bin/env python3
"""
Create the 4 C4 Cold License Request sequences in Outreach.

- Schedule: C4 Tue-Thu Morning (ID 50)
- Step 1: 240s (4 min), Steps 2+: 604,800s (7 days)
- Step 2 in all sequences uses existing template ID 43784
"""

import json
import logging
import os
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# ── Auth ──

def get_access_token():
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    resp = httpx.get(
        "https://api.github.com/repos/scadkin/firstcocoagent/contents/memory/outreach_tokens.json",
        headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3.raw"},
        timeout=15.0,
    )
    tokens = json.loads(resp.text)
    resp = httpx.post("https://api.outreach.io/oauth/token", data={
        "client_id": os.environ.get("OUTREACH_CLIENT_ID", ""),
        "client_secret": os.environ.get("OUTREACH_CLIENT_SECRET", ""),
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }, timeout=30.0)
    resp.raise_for_status()
    return resp.json()["access_token"]

API_BASE = "https://api.outreach.io/api/v2"
access_token = get_access_token()
HEADERS = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/vnd.api+json",
}

SCHEDULE_ID = 50  # C4 Tue-Thu Morning
EXISTING_TEMPLATE_ID = 43784  # "New referral/info dump email 2026 DRAFT"
INTERVAL_STEP1 = 240  # 4 minutes
INTERVAL_WEEKLY = 604800  # 7 days


def api_post(path, payload):
    resp = httpx.post(f"{API_BASE}{path}", headers=HEADERS, json=payload, timeout=30.0)
    if resp.status_code not in (200, 201):
        logger.error(f"POST {path} failed: {resp.status_code} {resp.text[:300]}")
        raise Exception(f"API error {resp.status_code}")
    return resp.json()


def api_patch(path, payload):
    resp = httpx.patch(f"{API_BASE}{path}", headers=HEADERS, json=payload, timeout=30.0)
    if resp.status_code != 200:
        logger.error(f"PATCH {path} failed: {resp.status_code} {resp.text[:300]}")
        raise Exception(f"API error {resp.status_code}")
    return resp.json()


def text_to_html(text):
    """Convert plain text email to simple HTML with <br><br> between paragraphs."""
    lines = text.strip().split("\n")
    html_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            html_parts.append("<br><br>")
        else:
            html_parts.append(line)
    return " ".join(html_parts)


def create_sequence(name, description, steps, tags=None):
    """
    Create a full sequence with steps and templates.

    steps: list of dicts, each with:
        - subject: str
        - body: str (plain text, will be converted to HTML)
        - interval: int (seconds)
        - use_existing_template: int or None (template ID to reuse)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Creating sequence: {name}")
    logger.info(f"{'='*60}")

    # 1. Create the sequence
    seq_payload = {
        "data": {
            "type": "sequence",
            "attributes": {
                "name": name,
                "description": description,
                "sequenceType": "interval",
                "scheduleIntervalType": "calendar",
                "shareType": "private",
                "throttleMaxAddsPerDay": 150,
                "throttleCapacity": 200,
                "maxActivations": 200,
            },
            "relationships": {
                "owner": {"data": {"type": "user", "id": 11}},
                "schedule": {"data": {"type": "schedule", "id": SCHEDULE_ID}},
                "ruleset": {"data": {"type": "ruleset", "id": 1}},
            },
        }
    }
    if tags:
        seq_payload["data"]["attributes"]["tags"] = tags

    result = api_post("/sequences", seq_payload)
    seq_id = result["data"]["id"]
    logger.info(f"  Sequence created: ID {seq_id}")

    # 2. Create each step
    for i, step in enumerate(steps):
        order = i + 1
        interval = step["interval"]
        subject = step["subject"]
        existing_template = step.get("use_existing_template")

        if existing_template:
            # Use existing template - just create the step and link
            template_id = existing_template
            logger.info(f"  Step {order}: using existing template {template_id}")
        else:
            # Create new template
            body_html = text_to_html(step["body"])
            template_payload = {
                "data": {
                    "type": "template",
                    "attributes": {
                        "name": f"{name} - Step {order}",
                        "subject": subject,
                        "bodyHtml": body_html,
                    },
                }
            }
            template_result = api_post("/templates", template_payload)
            template_id = template_result["data"]["id"]
            logger.info(f"  Step {order}: template created (ID {template_id})")

        # Create sequence step
        step_payload = {
            "data": {
                "type": "sequenceStep",
                "attributes": {
                    "stepType": "auto_email",
                    "interval": interval,
                    "order": order,
                },
                "relationships": {
                    "sequence": {"data": {"type": "sequence", "id": int(seq_id)}},
                },
            }
        }
        step_result = api_post("/sequenceSteps", step_payload)
        step_id = step_result["data"]["id"]

        # Link template to step
        link_payload = {
            "data": {
                "type": "sequenceTemplate",
                "relationships": {
                    "sequenceStep": {"data": {"type": "sequenceStep", "id": int(step_id)}},
                    "template": {"data": {"type": "template", "id": int(template_id)}},
                },
            }
        }
        api_post("/sequenceTemplates", link_payload)
        logger.info(f"  Step {order}: linked (step={step_id}, template={template_id}, interval={interval}s)")

    logger.info(f"  Sequence '{name}' complete: {len(steps)} steps")
    return seq_id


# ══════════════════════════════════════════
# SEQUENCE DEFINITIONS
# ══════════════════════════════════════════

SEQ_A_STEPS = [
    {
        "subject": "{{first_name}}, coding at {{company}}",
        "body": """{{first_name}},

You requested a CodeCombat license a while back. Wanted to check in and see if you're still exploring CS curriculum for your students.

I work with teachers across {{state}} to build super engaging coding classes K-12. With schools planning for fall right now, the timing might work well to revisit this.

Would it be worth sending over some info on what's new?

-Steven""",
        "interval": INTERVAL_STEP1,
    },
    {
        "subject": "CodeCombat's Comprehensive K-12 Suite",
        "body": "",  # unused
        "interval": INTERVAL_WEEKLY,
        "use_existing_template": EXISTING_TEMPLATE_ID,
    },
    {
        "subject": "students who won't stop coding",
        "body": """{{first_name}},

Most CS tools get used for a unit and then collect dust. CodeCombat is the one teachers tell me students keep coming back to on their own. It looks and feels like a video game, but everything underneath is mapped to CSTA, ISTE, and state standards K-12.

The whole platform was built with new teachers in mind. Zero-prep lesson slides with teacher guidance fully built out, robust unplugged activities, multiple ways to grade and assess, and a dashboard that's easy to manage. No coding experience needed to teach it.

Worth a look: <a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "Chromebook esports?",
        "body": """{{first_name}},

CodeCombat runs the only educational coding-based esports leagues in the world. Students compete using real code they write themselves.

They're safe (zero chatting or communication between players), asynchronous, fully browser-based, and they run on Chromebooks. No special hardware needed. Schools use them to build CS culture and pull in students who never thought coding was for them.

This comes bundled with our K-12 curriculum, along with CTE certification prep through the Python Institute (PCEP).

I can set you up with a free 30-day trial. Worth trying?

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "leftover budget idea for {{company}}",
        "body": """{{first_name}},

This is the time of year when schools are submitting budgets for fall, evaluating curriculum adoptions, writing grants, and figuring out what to do with leftover funds before they expire.

If coding is something you're planning for next year, it might make sense to get a quote in hand now so you can start having those conversations. Even if you're not ready to commit, having the numbers makes the ask easier.

I can put one together for you. Here's my calendar if you want to walk through it: <a href="https://hello.codecombat.com/c/steven/t/127">Pick a time</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "closing the loop",
        "body": """{{first_name}},

Last note from me. If coding comes back up at {{company}}, I'm here. Happy to put together a quote or set up trial licenses whenever the timing works.

If there's someone else I should connect with, I'd appreciate the intro.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
]

SEQ_B_STEPS = [
    {
        "subject": "{{company}} + CodeCombat",
        "body": """{{first_name}},

Someone at {{company}} requested a CodeCombat license and I wanted to make sure the right person got connected.

CodeCombat is a K-12 coding and CS curriculum platform. One system covering elementary through AP-level, fully standards-aligned, and completely turnkey for teachers with no CS background.

Would it be worth sending over an overview?

-Steven""",
        "interval": INTERVAL_STEP1,
    },
    {
        "subject": "CodeCombat's Comprehensive K-12 Suite",
        "body": "",
        "interval": INTERVAL_WEEKLY,
        "use_existing_template": EXISTING_TEMPLATE_ID,
    },
    {
        "subject": "how {{state}} districts are solving the CS teacher problem",
        "body": """{{first_name}},

32 states now require high schools to offer CS. The challenge most districts in {{state}} are hitting isn't whether to teach it, it's finding teachers who can.

CodeCombat was built for that. Every course has zero-prep lesson slides with full teacher guidance, built-in unplugged activities, multiple grading options, and a dashboard designed for educators who have never written a line of code. The curriculum covers K-12 in one platform and it's mapped to CSTA, ISTE, and state standards.

One platform, one PO, one implementation. Plus CTE certification prep (PCEP) and the only educational coding esports leagues in the world.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "before your fall budget closes",
        "body": """{{first_name}},

With districts finalizing budgets, locking in curriculum adoptions, and allocating leftover funds, this is typically the window where CS program decisions get made for next year.

If {{company}} is evaluating options, it might make sense to get a quote together now so you have the numbers in hand. CodeCombat also offers CTE certification prep through the Python Institute (PCEP), which can help with CTE funding conversations.

I can walk through pricing and how other {{state}} districts are structuring this: <a href="https://hello.codecombat.com/c/steven/t/127">Pick a time</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "should I be talking to someone else?",
        "body": """{{first_name}},

I've reached out a few times about {{company}}'s CodeCombat request. If there's someone who handles CS or CTE curriculum, I'd appreciate the intro.

Happy to put together a quote or set up 30-day trial licenses for your teachers whenever the timing works.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
]

SEQ_C_STEPS = [
    {
        "subject": "your CodeCombat request",
        "body": """{{first_name}},

You requested a CodeCombat license a while back. Wanted to follow up and see if CS curriculum is still something you're exploring at {{company}}.

I work with schools across {{state}} to build engaging, standards-aligned coding programs K-12. With schools planning for fall, the timing might work.

Would it be worth sending over some info?

-Steven""",
        "interval": INTERVAL_STEP1,
    },
    {
        "subject": "CodeCombat's Comprehensive K-12 Suite",
        "body": "",
        "interval": INTERVAL_WEEKLY,
        "use_existing_template": EXISTING_TEMPLATE_ID,
    },
    {
        "subject": "the coding tool kids actually like",
        "body": """{{first_name}},

Quick overview if you're evaluating options for next year.

CodeCombat is the most engaging K-12 coding curriculum out there. Students see a video game. Teachers see rigorous, standards-aligned CS curriculum (CSTA, ISTE) with zero-prep lesson slides, built-in unplugged activities, multiple assessment options, and a dashboard that's simple to manage. No coding background needed to teach it.

We also run the only educational coding esports leagues in the world, and offer CTE certification prep (PCEP) through the Python Institute.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "30-day trial, no strings",
        "body": """{{first_name}},

Rather than taking my word for it, I can set you up with a free 30-day trial so you or your students can actually explore CodeCombat. It takes about 5 minutes to get started.

Teachers use the trial to get student engagement data and feedback, which makes it a lot easier to build the case internally when budget conversations come up.

If that's useful, just reply with your grade levels and I'll get it set up.

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "leftover funds + fall planning",
        "body": """{{first_name}},

This is the time of year when schools are submitting budgets, evaluating curriculum for fall, writing grants, and putting in teacher requests for next year. It's also when a lot of leftover funds need to be spent before they expire.

If CS is on the table at {{company}}, it might make sense to get a quote in hand now so you're ready when those conversations happen.

I can put one together for you: <a href="https://hello.codecombat.com/c/steven/t/127">Pick a time</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "last one from me",
        "body": """{{first_name}},

This is my last email. If CS comes back up at {{company}}, I'm here. Happy to put together a quote or set up trial licenses whenever the timing works.

If there's someone else I should connect with, I'd appreciate the intro.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
]

SEQ_D_STEPS = [
    {
        "subject": "{{company}}'s CodeCombat request",
        "body": """{{first_name}},

Someone at {{company}} requested a CodeCombat license and I wanted to make sure the right person got connected.

CodeCombat is a K-12 coding and CS curriculum platform used by districts across {{state}}. With budget season and fall planning underway, the timing might be good to revisit this.

Would it be worth sending over an overview?

-Steven""",
        "interval": INTERVAL_STEP1,
    },
    {
        "subject": "CodeCombat's Comprehensive K-12 Suite",
        "body": "",
        "interval": INTERVAL_WEEKLY,
        "use_existing_template": EXISTING_TEMPLATE_ID,
    },
    {
        "subject": "how {{state}} districts are handling the CS mandate",
        "body": """{{first_name}},

32 states now require high schools to offer CS. The biggest challenge districts in {{state}} are running into isn't the mandate itself, it's the teacher capacity piece.

CodeCombat was designed for that. Every course comes with zero-prep lesson slides, full teacher guidance, built-in unplugged activities, multiple assessment options, and a teacher dashboard built for educators with no CS background. The curriculum covers K-12 in one platform, mapped to CSTA, ISTE, and state standards.

We also offer CTE certification prep (PCEP) and the only educational coding esports leagues in the world.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "before your fall budget closes",
        "body": """{{first_name}},

With districts finalizing budgets, locking in curriculum adoptions, writing grants, and allocating leftover funds, this is typically the window where CS decisions get made for next year.

If {{company}} is evaluating options, it might make sense to get a quote together now so you have the numbers when those conversations happen. Even if you're not ready to commit, having pricing in hand makes the process faster when the time comes.

I can walk through it here: <a href="https://hello.codecombat.com/c/steven/t/127">Pick a time</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
    {
        "subject": "should I be talking to someone else?",
        "body": """{{first_name}},

I've reached out a few times about {{company}}'s CodeCombat request. If there's someone who handles CS or CTE curriculum, I'd appreciate the intro.

Happy to put together a quote or set up trial licenses whenever the timing works.

<a href="https://codecombat.com/schools">codecombat.com/schools</a>

-Steven""",
        "interval": INTERVAL_WEEKLY,
    },
]


def main():
    tags = ["C4", "cold_license_request", "2026"]

    results = {}

    # Sequence A: Teachers
    seq_a_id = create_sequence(
        name="C4 License Re-Engage — Teachers",
        description="465 cold license request prospects with teacher roles. 6 steps, weekly pacing, Tue-Thu 8-10 AM.",
        steps=SEQ_A_STEPS,
        tags=tags + ["teachers"],
    )
    results["A_Teachers"] = seq_a_id

    # Sequence B: District/Admin
    seq_b_id = create_sequence(
        name="C4 License Re-Engage — District/Admin",
        description="200 cold license request prospects with district/admin roles. 5 steps, weekly pacing, Tue-Thu 8-10 AM.",
        steps=SEQ_B_STEPS,
        tags=tags + ["district", "admin"],
    )
    results["B_District_Admin"] = seq_b_id

    # Sequence C: Unknown Role - School
    seq_c_id = create_sequence(
        name="C4 License Re-Engage — School (General)",
        description="482 cold license request prospects at school level, role unknown. 6 steps, weekly pacing, Tue-Thu 8-10 AM.",
        steps=SEQ_C_STEPS,
        tags=tags + ["school", "general"],
    )
    results["C_School_General"] = seq_c_id

    # Sequence D: Unknown Role - District
    seq_d_id = create_sequence(
        name="C4 License Re-Engage — District (General)",
        description="125 cold license request prospects at district level, role unknown. 5 steps, weekly pacing, Tue-Thu 8-10 AM.",
        steps=SEQ_D_STEPS,
        tags=tags + ["district", "general"],
    )
    results["D_District_General"] = seq_d_id

    print("\n" + "=" * 60)
    print("ALL SEQUENCES CREATED")
    print("=" * 60)
    for name, sid in results.items():
        print(f"  {name}: Sequence ID {sid}")
    print()
    print("Next steps:")
    print("  1. Steven activates each sequence in Outreach UI")
    print("  2. Steven toggles templates active in each sequence")
    print("  3. Then we add prospects via API")

    # Save results
    output_path = Path(__file__).resolve().parent / "c4_sequence_ids.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSequence IDs saved to {output_path}")


if __name__ == "__main__":
    main()
