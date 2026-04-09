"""
tools/compliance_gap_scanner.py

F9 CS Graduation Compliance Gap Scanner (PDF pilot).

Some states have laws requiring computer science offerings for graduation
(CA AB 1251, IL HB 3449, MA CS framework). Districts that fail to meet
those requirements are forced-buyer leads: legally obligated to offer CS
but haven't yet.

Approach:
1. Serper `filetype:pdf` queries against state DOE domains for compliance
   reports, annual CS offering reports, and state report cards.
2. Download the PDFs (httpx).
3. Send each PDF to Claude Sonnet 4.6 via the document input API for
   structured extraction of compliant vs. non-compliant districts.
4. Queue non-compliant districts as prospects with
   strategy="compliance_gap".

Pilot scope: CA, IL, MA only.

Exit criterion (manual, not enforced by code): at least 60% of the
extracted "non-compliant" districts should be independently verifiable.
If the first run produces garbage, dial back or pivot.

Cost per state: ~$0.50-$2.00 depending on PDF size. Claude PDF pricing
is by page count in the rendered document.
"""

import base64
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

# Kill switch
ENABLE_COMPLIANCE_SCAN = True

# Pilot states with known CS graduation / offering requirements
PILOT_STATES = {"CA", "IL", "MA"}

# Per-state query strategy. Targeting official state DOE and legislature
# PDF reports that list district-level CS offerings or compliance.
_STATE_QUERIES = {
    "CA": [
        '"AB 1251" OR "computer science" report district "California" filetype:pdf',
        'site:cde.ca.gov "computer science" enrollment district report filetype:pdf',
        '"California Department of Education" "computer science" offerings filetype:pdf',
    ],
    "IL": [
        '"HB 3449" OR "PA 102" "computer science" Illinois report filetype:pdf',
        'site:isbe.net "computer science" district filetype:pdf',
        '"Illinois State Board of Education" computer science graduation district filetype:pdf',
    ],
    "MA": [
        'site:doe.mass.edu "computer science" district report filetype:pdf',
        '"Massachusetts DESE" "computer science" enrollment filetype:pdf',
        '"computer science" Massachusetts district accountability filetype:pdf',
    ],
}

_PROMPT_TEMPLATE = """You are analyzing a state-level computer science compliance document to identify K-12 school districts that are NOT meeting CS graduation or offering requirements.

STATE: {state_name}
CONTEXT: {state_context}

Extract structured data about districts mentioned in this document with respect to their CS program status.

Return ONLY a JSON array of objects with this shape:
[
  {{
    "district": "Exact district name",
    "status": "non_compliant | compliant | partial | unknown",
    "evidence_quote": "Direct quote from the document (<= 200 chars) supporting the status",
    "page_hint": "approximate page number or section",
    "confidence": "HIGH | MEDIUM | LOW"
  }}
]

RULES:
- Only include K-12 school districts (no universities, no individual schools except as district-level summaries).
- A district is "non_compliant" if the document explicitly says it does not offer CS, has no CS teacher, has no CS course, or fails a CS requirement.
- A district is "compliant" if the document says it meets requirements.
- A district is "partial" if it offers some but not all required CS content.
- If the document doesn't speak to a specific district, do not include it.
- HIGH confidence only when the evidence quote is unambiguous.
- Return [] if the document has no district-level compliance data.
- Return ONLY the JSON array. No commentary, no markdown code fences.
"""

_STATE_CONTEXT = {
    "CA": (
        "California AB 1251 (signed 2023) requires every high school to offer at "
        "least one computer science course by the 2028-29 school year, with "
        "phased compliance. Districts without a CS teacher or CS course are "
        "non-compliant with the requirement."
    ),
    "IL": (
        "Illinois PA 102-0763 (HB 3449) requires every public high school to "
        "offer at least one computer science course by the 2023-24 school year. "
        "Districts without such a course are non-compliant with state law."
    ),
    "MA": (
        "Massachusetts DESE has a Digital Literacy and Computer Science (DLCS) "
        "curriculum framework. Districts without an implemented DLCS program "
        "at the high school level are considered gaps in the state standard."
    ),
}


def _serper_pdf_urls(state: str, max_per_query: int = 8) -> list[dict]:
    """Run the state-specific query set and collect candidate PDF URLs."""
    queries = _STATE_QUERIES.get(state.upper(), [])
    if not queries:
        return []

    import httpx

    hits = []
    seen = set()
    for q in queries:
        try:
            resp = httpx.post(
                SERPER_URL,
                headers={"X-API-Key": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": q, "num": max_per_query},
                timeout=15.0,
            )
            data = resp.json()
            for item in data.get("organic", [])[:max_per_query]:
                url = item.get("link", "")
                if not url or url in seen:
                    continue
                if not url.lower().endswith(".pdf"):
                    continue
                seen.add(url)
                hits.append({
                    "url": url,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Serper compliance query failed for {state}: {e}")
    return hits


def _download_pdf(url: str, max_bytes: int = 10_000_000) -> Optional[bytes]:
    """Download a PDF, with a 10 MB cap. Returns None on failure or size exceeded."""
    import httpx
    try:
        with httpx.stream("GET", url, timeout=30.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 Scout/1.0"}) as r:
            if r.status_code != 200:
                logger.info(f"PDF download {r.status_code}: {url[:80]}")
                return None
            ct = r.headers.get("content-type", "")
            if "pdf" not in ct.lower() and not url.lower().endswith(".pdf"):
                logger.info(f"Not a PDF (ct={ct}): {url[:80]}")
                return None
            chunks = []
            total = 0
            for chunk in r.iter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    logger.info(f"PDF exceeds {max_bytes} bytes: {url[:80]}")
                    return None
            return b"".join(chunks)
    except Exception as e:
        logger.info(f"PDF download error for {url[:80]}: {e}")
        return None


def _extract_districts_from_pdf(pdf_bytes: bytes, state: str) -> list[dict]:
    """Call Claude Sonnet with the PDF and extraction prompt."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — cannot extract compliance data")
        return []

    import anthropic

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=180.0)
        prompt = _PROMPT_TEMPLATE.format(
            state_name={"CA": "California", "IL": "Illinois", "MA": "Massachusetts"}.get(state, state),
            state_context=_STATE_CONTEXT.get(state, ""),
        )
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Claude PDF extraction failed for {state}: {e}")
        return []

    # Parse JSON array — strip fences if present
    try:
        clean = raw_text
        if "```" in clean:
            parts = clean.split("```")
            if len(parts) >= 2:
                clean = parts[1]
                if clean.startswith("json"):
                    clean = clean[4:]
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            return []
        items = json.loads(clean[start:end + 1])
        if not isinstance(items, list):
            return []
        return items
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Compliance JSON parse failed for {state}: {e}")
        return []


def scan_compliance_gaps(state: str, max_pdfs: int = 5) -> dict:
    """
    F9: Run the compliance gap scanner for a single pilot state.

    Returns {
        state,
        pdf_count,
        district_extractions: [{url, title, districts: [...]}],
        non_compliant_total,
        queued: [district_names],
        errors: [],
    }
    """
    if not ENABLE_COMPLIANCE_SCAN:
        return {"state": state, "error": "compliance scan disabled via ENABLE_COMPLIANCE_SCAN"}

    state_upper = state.strip().upper()
    if state_upper not in PILOT_STATES:
        return {
            "state": state_upper,
            "error": f"{state_upper} not in pilot scope (CA, IL, MA)",
        }

    if not SERPER_API_KEY:
        return {"state": state_upper, "error": "SERPER_API_KEY not set"}
    if not ANTHROPIC_API_KEY:
        return {"state": state_upper, "error": "ANTHROPIC_API_KEY not set"}

    # Step 1: find candidate PDFs
    pdf_hits = _serper_pdf_urls(state_upper)
    logger.info(f"F9 {state_upper}: {len(pdf_hits)} candidate PDFs")
    if not pdf_hits:
        return {
            "state": state_upper,
            "pdf_count": 0,
            "district_extractions": [],
            "non_compliant_total": 0,
            "queued": [],
            "errors": ["No PDFs found from Serper"],
        }

    # Step 2: process up to max_pdfs
    extractions = []
    errors = []
    for hit in pdf_hits[:max_pdfs]:
        url = hit["url"]
        pdf_bytes = _download_pdf(url)
        if not pdf_bytes:
            errors.append(f"download_failed: {url[:80]}")
            continue
        districts = _extract_districts_from_pdf(pdf_bytes, state_upper)
        extractions.append({
            "url": url,
            "title": hit["title"],
            "districts": districts,
        })
        time.sleep(1.0)

    # Step 3: tally non-compliant districts and queue them
    import tools.district_prospector as district_prospector
    import tools.csv_importer as csv_importer

    all_non_compliant = {}  # district name → best evidence
    for ext in extractions:
        for d in ext.get("districts", []):
            status = (d.get("status") or "").strip().lower()
            confidence = (d.get("confidence") or "LOW").strip().upper()
            if status not in ("non_compliant", "partial"):
                continue
            if confidence != "HIGH":
                continue
            name = (d.get("district") or "").strip()
            if not name:
                continue
            evidence = (d.get("evidence_quote") or "").strip()[:200]
            norm = csv_importer.normalize_name(name)
            # Keep first hit per district (dedup across PDFs)
            if norm not in all_non_compliant:
                all_non_compliant[norm] = {
                    "name": name,
                    "status": status,
                    "evidence": evidence,
                    "source_url": ext["url"],
                    "source_title": ext["title"],
                }

    queued = []
    for norm_key, d in all_non_compliant.items():
        notes = (
            f"CS compliance gap ({d['status']}). "
            f"Evidence: {d['evidence']}. "
            f"Source: {d['source_title'][:80]}. "
            f"URL: {d['source_url']}"
        )
        try:
            result = district_prospector.add_district(
                name=d["name"],
                state=state_upper,
                notes=notes[:900],
                strategy="compliance_gap",
                source="signal",
            )
            if result.get("success"):
                queued.append(d["name"])
        except Exception as e:
            errors.append(f"queue_failed {d['name']}: {e}")

    return {
        "state": state_upper,
        "pdf_count": len(extractions),
        "district_extractions": extractions,
        "non_compliant_total": len(all_non_compliant),
        "queued": queued,
        "errors": errors,
    }


def format_scan_result_for_telegram(result: dict) -> str:
    """Format scan_compliance_gaps output for Telegram."""
    if result.get("error"):
        return f"❌ Compliance gap scan: {result['error']}"

    state = result.get("state", "?")
    pdf_count = result.get("pdf_count", 0)
    non_compliant = result.get("non_compliant_total", 0)
    queued = result.get("queued", [])
    errors = result.get("errors", [])
    extractions = result.get("district_extractions", [])

    lines = [f"📑 *F9 Compliance Gap Scan — {state}*"]
    lines.append("")
    lines.append(f"PDFs processed: {pdf_count}")
    lines.append(f"Non-compliant districts extracted: {non_compliant}")
    lines.append(f"Auto-queued (HIGH confidence): {len(queued)}")
    lines.append("")

    if queued:
        lines.append("Queued districts:")
        for q in queued[:15]:
            lines.append(f"  • {q}")
        if len(queued) > 15:
            lines.append(f"  ...and {len(queued) - 15} more")
        lines.append("")

    if extractions:
        lines.append("Source PDFs processed:")
        for e in extractions[:5]:
            title = (e.get("title") or "")[:60]
            url = (e.get("url") or "")[:100]
            dist_count = len(e.get("districts", []))
            lines.append(f"  • {title}")
            lines.append(f"    {url}")
            lines.append(f"    ({dist_count} districts extracted)")
        lines.append("")

    if errors:
        lines.append(f"⚠️ {len(errors)} errors:")
        for e in errors[:5]:
            lines.append(f"  • {e[:100]}")
        lines.append("")

    lines.append("Review queued prospects with `/prospect_all`.")
    lines.append("PILOT: verify 60% of queued districts are truly non-compliant before scaling.")
    return "\n".join(lines)
