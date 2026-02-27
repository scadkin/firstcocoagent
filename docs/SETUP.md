# SETUP_PHASE3.md — Gmail + Calendar + Slides via Google Apps Script Bridge

## Why GAS Bridge?

Scout connects to your work Google account (steven@codecombat.com) through a
Google Apps Script Web App rather than direct OAuth2. This approach:

- Requires ZERO IT approval — GAS runs inside Google, not as a third-party app
- Accesses Gmail, Calendar, and Slides with your full permissions
- Protected by a secret token only you and Scout know
- Free, no extra accounts or services needed

Architecture:
  Scout (Railway) → HTTPS POST → Google Apps Script Web App → Gmail / Calendar / Slides

---

## Step 1: Create the Apps Script Project

1. Go to script.google.com
2. Make sure you're logged in as steven@codecombat.com
3. Click + New project
4. Name it "Scout Bridge"
5. Delete all existing code in the editor
6. Paste the entire contents of gas/Code.gs from this repo

---

## Step 2: Set Your Secret Token

In the pasted code, find this line near the top:

  var SECRET_TOKEN = "REPLACE_WITH_YOUR_SECRET_TOKEN_HERE";

Replace the placeholder with any long random string you make up.
Example: scout_k12_2026_xK9mP3qR7vN2

Write this token down — you'll need it for Railway.

---

## Step 3: Deploy as a Web App

1. Click Deploy (top right) → New deployment
2. Click the gear icon next to "Type" → select Web app
3. Configure:
   - Execute as: Me (steven@codecombat.com)
   - Who has access: Anyone
4. Click Deploy
5. If prompted to authorize, click Authorize access → select your work account → Allow
6. Copy the Web App URL (looks like: https://script.google.com/macros/s/AKfycb.../exec)

---

## Step 4: Set Railway Environment Variables

In your Railway project → Variables, add:

  GAS_WEBHOOK_URL  =  (the Web App URL from Step 3)
  GAS_SECRET_TOKEN =  (the token you set in Step 2)

Railway will auto-redeploy.

---

## Step 5: Test the Connection

In Telegram, send:
  /ping_gas

Expected response:
  GAS Bridge connected! Running as: steven@codecombat.com

---

## Step 6: Train Voice Profile

In Telegram, send:
  /train_voice

Scout fetches 6 months of sent emails, selects 40 representative ones,
sends them to Claude for analysis, and saves your voice profile.
Takes 2-3 minutes with progress updates.

---

## Step 7: Test Each Feature

Email draft:
  Draft a cold email to the CS Director at Austin ISD

Calendar:
  What's on my calendar this week?

Log a call:
  Log a call with Maria Rodriguez, CTE Director at Denver Public Schools,
  30 minutes, discussed AI HackStack, she wants a demo next week

Create a deck:
  Make a pitch deck for Houston ISD — contact is James Park, Director of CS

---

## New Railway Variables

  GAS_WEBHOOK_URL    — GAS Web App URL (required)
  GAS_SECRET_TOKEN   — Auth token, must match Code.gs (required)

No other new variables needed.

---

## New Telegram Commands

  /ping_gas                          — Test GAS bridge connection
  /train_voice                       — Build voice profile from sent emails
  draft a [type] email to [person]   — Draft email in your voice
  looks good                         — Save pending draft to Gmail Drafts
  add email: addr@district.org       — Set recipient on pending draft
  what's on my calendar              — Show upcoming calendar events
  log a call with [name]             — Log call as structured calendar event
  make a deck for [district]         — Create Google Slides pitch deck

---

## Troubleshooting

  "GAS bridge not configured"  →  Set GAS_WEBHOOK_URL and GAS_SECRET_TOKEN in Railway
  "Unauthorized"               →  Token mismatch — check Railway var matches Code.gs exactly
  Ping timeout                 →  GAS cold-starts slowly — wait 10 seconds and try again
  "No sent emails found"       →  Verify GAS is deployed as steven@codecombat.com
  Calendar shows wrong account →  Verify GAS deployed as work account, not personal

## Updating the GAS Script Later

1. Go to script.google.com → open Scout Bridge
2. Edit Code.gs
3. Deploy → Manage deployments → pencil icon → New version → Deploy
The URL stays the same, no Railway changes needed.
