# EOD Report Prompt

Generate Steven's end-of-day report. Be factual and specific.

CRITICAL RULES:
- The REAL ACTIVITY DATA block above this prompt contains actual numbers from Google Sheets. Use those numbers exactly — do not invent or estimate.
- Only report work that is confirmed in the REAL ACTIVITY DATA or today's conversation history.
- If no research ran today, do not mention leads — do not invent numbers.
- If no emails were drafted, say so.
- "Nothing to report" is a valid and honest answer for any section.
- Report final KPI progress honestly, including misses — don't soften.

Format:

📊 EOD Report — [DATE]

**ACCOMPLISHED TODAY:**
[Only real completed work from REAL ACTIVITY DATA or today's conversation. If nothing: "No tasks completed today — ready to start fresh tomorrow."]

**KPI RESULTS:**
[From the REAL ACTIVITY DATA block. Format each goal as "Calls: X/10 ✅" or "Districts: X/2 ❌ (missed)". Only include if goal data is present.]

**LEADS FOUND:**
[Only if districts_researched > 0 in REAL ACTIVITY DATA. Include district names from conversation context if available. If no research: omit this section.]

**EMAILS DRAFTED:**
[Only if emails_drafted or emails_saved > 0. Count and brief description. If none: omit.]

**PANDADOC / DIALPAD ACTIVITY:**
[Only if pandadoc_event or dialpad_call > 0. What happened. If none: omit.]

**PROSPECTING:**
[If any districts were discovered, approved, researched, or had sequences built today, mention them. If nothing: omit this section.]

**PIPELINE ALERTS:**
[If PIPELINE ALERT DATA is provided above, list stale opps and past-due close dates. If no pipeline data or no alerts: omit this section entirely.]

**PENDING / TOMORROW:**
[Unfinished tasks or queued items carrying over. Include approved districts awaiting research. If none: "Clean slate for tomorrow."]

**ONE OBSERVATION:**
[A brief coaching note or strategic observation based on what actually happened today, or a suggestion for tomorrow.]

Keep the entire report under 250 words.
