# Email Reply Drafting — Workflow Instructions

## When to run
Steven says "draft my emails", "check my inbox", "draft replies", or similar.

## Before starting
Load these files into context:
- memory/voice_profile.md (voice rules + anti-AI-tell checklist)
- memory/response_playbook.md (category patterns + real snippets)

## Step 1: Find emails needing replies
```
gmail_search_messages(q="is:unread in:inbox -category:promotions -category:social -from:noreply -from:no-reply -from:notifications -from:mailer-daemon")
```

## Step 2: Read and classify each email
For each result, read the full thread: `gmail_read_thread(threadId=...)`

Classify into one of three buckets:

**DRAFT** — Standard email Steven can reply to with voice + playbook knowledge.
Examples: pricing questions, scheduling, follow-ups, acknowledgments, product questions, budget constraints, free trial requests.

**FLAG** — Needs specific info only Steven has, or requires a judgment call.
Draft what you can and mark gaps inline: `[STEVEN: insert availability / custom quote / specific decision]`.
Examples: "What's your availability next week?", custom enterprise pricing, contract negotiations, complaints requiring investigation.

**SKIP** — No reply needed or out of scope.
- Auto-replies / OOO responses ("Automatic reply:", "Out of Office")
- Automated notifications (Outreach, Salesforce, PandaDoc, Dialpad, calendar)
- Newsletters, marketing, promotions
- CC-only threads where Steven isn't directly addressed
- Sales outreach or recruiting emails TO Steven
- Internal company-wide announcements
- Support ticket auto-responses
- Bid/procurement system notifications (ionwave, etc.)
- Emails already replied to (check if Steven's address appears in later thread messages)

## Step 3: Draft replies
For each DRAFT or FLAG email:
1. Match to the closest playbook category (response_playbook.md)
2. Write the reply body following voice_profile.md rules — especially the Anti-AI-Tell Checklist
3. Match inbound energy:
   - 1-2 sentence inbound → 1-3 sentence reply
   - Casual tone → casual reply ("Hey [Name],", tilde, emoji if fits)
   - Formal/procurement → structured but still warm
   - Frustrated/disappointed → empathetic first, then solution
4. Body only — no subject line (Gmail handles Re:), no signature (auto-appended by Gmail)
5. Start with greeting (usually "Hey [Name]," or "Hi [Name],")
6. End naturally — Steven often just stops after the last point, no formal sign-off needed
7. For FLAG emails, include `[STEVEN: ...]` inline where Steven needs to fill in info

## Step 4: Create Gmail drafts IMMEDIATELY
Do NOT show drafts in Claude Code for approval first. Create them directly in Gmail so Steven can open each email and see the draft reply waiting. Steven's workflow: open inbox → open email → see draft → tweak → send → next.

For each DRAFT or FLAG email:
```
gmail_create_draft(to=sender_email, body=draft_html, threadId=thread_id, cc=original_cc_recipients, contentType="text/html")
```

**IMPORTANT:**
- Always use `contentType="text/html"` so links are clickable.
- Only create ONE draft per thread — never recreate or you'll leave orphaned drafts that show "Draft" labels even after Steven sends.
- **Outreach extension conflict:** For contacts in Steven's Outreach system, the Outreach browser extension takes over the compose window and wipes API-created draft body text. When this happens, create a standalone draft (no threadId) with a "COPY THIS" subject line so Steven can copy-paste the body into the thread manually. After sending, delete the orphaned threaded draft via GAS bridge `delete_draft` action.
- If a draft needs to be deleted, use the GAS bridge: `{action: "delete_draft", params: {draft_id: "<id>"}}` via Python requests (curl doesn't handle GAS redirects).

**CC handling:** Include all original CC recipients from the inbound email, minus any noreply/automated addresses. If the inbound was sent to multiple people including Steven, reply-all.

After creating all drafts, show Steven a brief summary of what was drafted:
```
**Drafted 5 replies, skipped 3:**
1. Kate Grow — AI question → product info + call CTA
2. Anthony Pollina — locked out of levels → FLAG [needs: check licensing vs bug]
3. Krista Farris — "wasn't me" → pivoted to her as CS teacher
SKIPPED: Arlington ISD (bid notification), Megan Weber (OOO), PandaDoc reminder
```

## Step 6: Log for learning
Append to memory/draft_log.md with this format:

```
## YYYY-MM-DD HH:MM

### thread:<thread_id>
from: sender@email.com | subject: Re: Subject | category: <playbook category>
DRAFT:
[full draft text]
```

**Cleanup:** At the start of each drafting session, delete entries older than 14 days.

---

## "Learn from my sends" workflow
When Steven says "learn from my sends":
1. Read memory/draft_log.md for recent entries
2. For each thread_id: gmail_read_thread to check if Steven sent a reply
3. Compare draft text to what Steven actually sent
4. If substantially the same → positive signal, no action
5. If different → extract what changed, append correction to voice_profile.md under "Learned Corrections"
6. If never sent → flag as a miss, analyze what was wrong
7. Report summary to Steven
