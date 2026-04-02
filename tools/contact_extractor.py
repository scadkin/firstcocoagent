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

EXTRACT_SYSTEM = """You are a precise data extraction assistant for a K-12 education sales team selling CodeCombat (a computer science education platform).

Your job: extract contacts who could be decision-makers or influencers for purchasing CS/coding curriculum.

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

WHO TO INCLUDE (in priority order):
1. ALWAYS include: Superintendent, Assistant Superintendent, Chief Academic Officer, Principal, Assistant Principal
2. ALWAYS include: Anyone with "Computer Science", "CS", "Coding", "Programming" in their title
3. ALWAYS include: Anyone with "STEM", "STEAM", "S.T.E.M.", "S.T.E.A.M." in their title
4. ALWAYS include: Anyone with "Technology", "EdTech", "Digital Learning", "Instructional Technology" in their title
5. ALWAYS include: Curriculum Director, Director of Curriculum, Instructional Coordinator, Curriculum Specialist
6. ALWAYS include: Esports Coach/Teacher, Robotics Coach/Teacher, Game Design/Development Teacher
7. ALWAYS include: Engineering Teacher, Web Design/Development Teacher
8. ALWAYS include: AP CSP, AP CSA, AP Computer Science teachers
9. ALWAYS include: TOSA, Teacher on Special Assignment, Librarian, Media Specialist
10. ALWAYS include: Director of Elementary/Secondary Education
11. INCLUDE CTE roles ONLY if related to: computers, technology, CS, coding, cyber, networking, digital, software, web, game, esports, data science, AI, information technology
12. INCLUDE anyone from: Educational Services, Curriculum & Instruction, College & Career Readiness, Advanced Academics departments

WHO TO EXCLUDE:
- CTE teachers in: culinary, cosmetology, automotive, welding, plumbing, HVAC, construction, health science, nursing, agriculture, animal science, fashion, criminal justice, hospitality, food service, child development
- General admin: secretaries, HR, finance, facilities, transportation, food services
- Teachers in: English, History, Social Studies, Foreign Language, Physical Education, Art, Music (unless also teaching CS/STEM)

CRITICAL RULES FOR ACCURACY:
1. Each contact's email MUST belong to that specific person. In staff directory tables,
   match each row's name to that SAME row's email. Do NOT shift or misalign rows.
2. email_confidence: VERIFIED (on same line/row), LIKELY (pattern match + name matches),
   INFERRED (pattern guess), UNKNOWN (no email found)
3. Phone numbers go in work_phone, NOT email field.
4. If a table row is truncated or ambiguous, set email_confidence to UNKNOWN.
5. account: school name if school-level, district name if district-level.
6. If no valid contacts found, return empty array: []
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
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        # Strip text before first [ and after last ] (Claude sometimes adds preamble)
        bracket_start = raw.find("[")
        bracket_end = raw.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            raw = raw[bracket_start:bracket_end + 1]

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

            # Post-extraction CTE filter: drop irrelevant trades
            try:
                from agent.target_roles import is_relevant_cte_role
                if not is_relevant_cte_role(contact["title"]):
                    logger.debug(f"Filtered irrelevant CTE: {contact['first_name']} {contact['last_name']} — {contact['title']}")
                    continue
            except ImportError:
                pass  # target_roles not available, skip filter

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
