"""
contact_extractor.py — Uses Claude API to extract structured contact records
from raw HTML, text blobs, LinkedIn snippets, and search result content.
"""

import re
import json
import logging
from datetime import date
from anthropic import Anthropic

logger = logging.getLogger(__name__)

client = Anthropic()

# ─────────────────────────────────────────────
# EXTRACTION PROMPT
# ─────────────────────────────────────────────

EXTRACT_SYSTEM = """You are a precise data extraction assistant for a K-12 education sales team.

Your job: extract CS/STEM/CTE contact information from raw text or HTML.

Return ONLY a valid JSON array. No explanation, no markdown, no preamble.

Each contact object must have these exact keys:
{
  "first_name": "",
  "last_name": "",
  "title": "",
  "email": "",
  "work_phone": "",
  "account": "",
  "district_name": "",
  "source_url": "",
  "email_confidence": "",
  "notes": ""
}

Rules:
- email_confidence must be one of: VERIFIED, LIKELY, INFERRED, or UNKNOWN
  - VERIFIED: email explicitly shown in source
  - LIKELY: email pattern confirmed by district, name matches
  - INFERRED: email constructed from pattern but unconfirmed
  - UNKNOWN: no email found
- account: school name if school-level contact, district name if district-level
- If a field is unknown, use empty string ""
- Only include contacts whose title relates to: Computer Science, CS, Coding, Programming,
  STEM, STEAM, CTE, Career & Technical Education, Educational Technology, Curriculum,
  Instructional Technology, Digital Learning, Innovation, AP CSP, AP CS, Robotics, Esports,
  Game Design, Makerspace, After-School, TOSA, Librarian, Superintendent, Principal, Title I
- Do NOT include general admin staff, secretaries, HR, finance unless directly related to above
- If no valid contacts found, return empty array: []
"""

# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def extract_contacts(raw_content: str, source_url: str, district_name: str) -> list[dict]:
    """
    Send raw content to Claude for contact extraction.
    Returns list of contact dicts, ready for sheets_writer.
    """
    if not raw_content or len(raw_content.strip()) < 50:
        return []

    # Truncate to avoid token limits — 12k chars is plenty for extraction
    content_chunk = raw_content[:12000]

    prompt = f"""District: {district_name}
Source URL: {source_url}

Raw content to extract contacts from:
---
{content_chunk}
---

Extract all CS/STEM/CTE/EdTech contacts. Return JSON array only."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system=EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        contacts = json.loads(raw)

        if not isinstance(contacts, list):
            logger.warning(f"Extractor returned non-list: {type(contacts)}")
            return []

        # Normalize + stamp each contact
        today = date.today().isoformat()
        cleaned = []
        for c in contacts:
            contact = {
                "first_name": str(c.get("first_name", "")).strip(),
                "last_name": str(c.get("last_name", "")).strip(),
                "title": str(c.get("title", "")).strip(),
                "email": str(c.get("email", "")).strip().lower(),
                "work_phone": str(c.get("work_phone", "")).strip(),
                "account": str(c.get("account", district_name)).strip(),
                "district_name": district_name,
                "source_url": str(c.get("source_url", source_url)).strip(),
                "email_confidence": str(c.get("email_confidence", "UNKNOWN")).strip().upper(),
                "notes": str(c.get("notes", "")).strip(),
                "date_found": today,
            }

            # Skip contacts with no name
            if not contact["first_name"] and not contact["last_name"]:
                continue

            # Skip if email_confidence is invalid
            if contact["email_confidence"] not in ("VERIFIED", "LIKELY", "INFERRED", "UNKNOWN"):
                contact["email_confidence"] = "UNKNOWN"

            cleaned.append(contact)

        logger.info(f"Extracted {len(cleaned)} contacts from {source_url}")
        return cleaned

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error from extractor: {e}\nRaw: {raw[:500]}")
        return []
    except Exception as e:
        logger.error(f"Extraction error for {source_url}: {e}")
        return []


def extract_from_multiple(pages: list[tuple[str, str]], district_name: str) -> list[dict]:
    """
    Extract contacts from multiple (url, content) pairs.
    Deduplicates by (first_name, last_name, district_name).
    Returns merged, deduped list.
    """
    all_contacts = []
    seen = set()

    for url, content in pages:
        contacts = extract_contacts(content, url, district_name)
        for c in contacts:
            key = (
                c["first_name"].lower(),
                c["last_name"].lower(),
                c["district_name"].lower()
            )
            if key not in seen:
                seen.add(key)
                all_contacts.append(c)

    return all_contacts


def infer_email(first: str, last: str, domain: str, pattern: str) -> str:
    """
    Construct an email address from a pattern template.
    Pattern uses {first}, {last}, {f} (first initial), {domain}.
    """
    if not first or not last or not domain:
        return ""

    first = first.lower().strip()
    last = last.lower().strip()
    f = first[0] if first else ""

    try:
        email = pattern.format(
            first=first,
            last=last,
            f=f,
            domain=domain
        )
        return email
    except (KeyError, IndexError):
        return ""


def detect_email_pattern(known_emails: list[str], domain: str) -> str | None:
    """
    Given a list of known emails from a district and the domain,
    detect which pattern they use.
    Returns the pattern string or None.
    """
    from agent.keywords import EMAIL_PATTERNS

    # We need at least one confirmed email with a known first+last to detect
    # This function is called after we've already found some staff directory entries
    # Returns the most likely pattern

    # Try to match known emails against patterns
    # Since we don't always know first/last from just email, we do a structural match

    if not known_emails:
        return None

    for email in known_emails:
        if "@" not in email:
            continue
        local = email.split("@")[0].lower()

        # firstname.lastname
        if re.match(r"^[a-z]+\.[a-z]+$", local):
            return "{first}.{last}@{domain}"
        # flastname
        if re.match(r"^[a-z][a-z]{2,}$", local) and len(local) < 12:
            return "{f}{last}@{domain}"
        # firstnamelastname
        if re.match(r"^[a-z]{4,}$", local):
            return "{first}{last}@{domain}"
        # firstname_lastname
        if re.match(r"^[a-z]+_[a-z]+$", local):
            return "{first}_{last}@{domain}"
        # f.lastname
        if re.match(r"^[a-z]\.[a-z]+$", local):
            return "{f}.{last}@{domain}"

    return None
