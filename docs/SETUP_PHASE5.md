# SETUP_PHASE5.md — Call Intelligence Suite Setup

**Time required:** ~15 minutes  
**When to do this:** After Phase 5 code is deployed to Railway

---

## What Phase 5 does

1. **Pre-call brief** — Scout automatically sends you a research brief 10 minutes before any Zoom call, then saves it as a Google Doc
2. **Post-call summary** — When Fireflies finishes transcribing your call, Scout automatically extracts all key sales data and sends it to Telegram
3. **Recap email** — Auto-drafted to Gmail Drafts after every call
4. **Salesforce block** — Pre-formatted copy-paste block ready for your CRM

---

## Step 1: Set up Fireflies.ai (10 min)

### 1a. Create account
- Go to [app.fireflies.ai](https://app.fireflies.ai) and sign up (free)
- Free plan: 800 transcription minutes/month (~13 hours of calls)

### 1b. Connect Zoom
- Settings → Integrations → Zoom → Connect
- Fireflies will auto-join your Zoom calls as "Notetaker"

### 1c. Get your API key
- Top-right menu → Settings → API
- Copy your API key

### 1d. Set up the webhook
- Settings → Webhooks → Add Webhook
- URL: `https://[your-railway-app-url]/fireflies-webhook`
  - Find your Railway URL: go to railway.app → your project → Settings → Domains
  - It looks like: `https://firstcocoagent-production-xxxx.up.railway.app`
- Webhook secret: create any random string (e.g., `scout_ff_secret_2026`)
  - You'll add this same string to Railway in Step 2
- Events to subscribe: check **"Transcription completed"**
- Save

---

## Step 2: Add Railway environment variables (2 min)

Go to railway.app → your project → Variables tab → add:

| Variable | Where to get it | Example |
|----------|----------------|---------|
| `FIREFLIES_API_KEY` | Fireflies Settings → API | `abc123xyz...` |
| `FIREFLIES_WEBHOOK_SECRET` | Whatever you set in Step 1d | `scout_ff_secret_2026` |
| `PRECALL_BRIEF_FOLDER_ID` | Google Drive folder URL — see Step 3 | `1aBcD2eFgH...` |

---

## Step 3: Create the "Scout Pre-Call Briefs" Google Drive folder (2 min)

1. Open [Google Drive](https://drive.google.com) in your **work account** (`steven@codecombat.com`)
2. Click **New → Folder** → name it `Scout Pre-Call Briefs`
3. Open the folder
4. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/[THIS_IS_THE_FOLDER_ID]
   ```
5. Add it to Railway as `PRECALL_BRIEF_FOLDER_ID`

---

## Step 4: Update Code.gs (3 min)

Phase 5 adds a `createGoogleDoc` action to your Google Apps Script bridge.

1. Go to [script.google.com](https://script.google.com) → Scout Bridge project
2. Use `/push_code gas/Code.gs` in Scout to fetch the current file and have Scout add the Phase 5 changes
   - OR: manually replace `Code.gs` with the Phase 5 version from GitHub
3. Deploy → **New deployment** (not "Edit existing")
   - Type: Web app
   - Execute as: Me
   - Who has access: Anyone
4. Copy the new deployment URL
5. Update `GAS_WEBHOOK_URL` in Railway with the new URL

> ⚠️ **Remember:** Replace the `SECRET_TOKEN` placeholder in Code.gs with your actual token before deploying!

---

## Step 5: Verify everything works

After Railway deploys (~30 seconds after code push):

1. **Test webhook server health:**
   ```
   curl https://[your-railway-url]/health
   ```
   Should return: `Scout is alive`

2. **Test Fireflies connection:**
   Send `/recent_calls` in Telegram
   - If you have any calls in Fireflies, they'll appear
   - If you get an error, check `FIREFLIES_API_KEY` in Railway

3. **Test pre-call brief manually:**
   - Create a test calendar event with "zoom.us" in the description
   - Send `/brief [meeting name]` in Telegram

4. **Test post-call processing manually:**
   After any real call is transcribed by Fireflies:
   - Send `/recent_calls` to see the transcript ID
   - Send `/call [transcript_id]` to manually trigger processing

---

## Phase 5 commands

| Command | What it does |
|---------|-------------|
| `/brief [meeting name]` | Manually trigger pre-call brief for a specific meeting (or next Zoom if no name given) |
| `/recent_calls` | List 5 most recent Fireflies transcripts |
| `/call [transcript_id]` | Manually process a specific transcript |

**Automatic triggers (no commands needed):**
- Pre-call brief fires automatically 10 minutes before any Zoom on your calendar
- Post-call summary fires automatically when Fireflies finishes transcribing

---

## Troubleshooting

**Webhook not firing:**
- Verify Railway URL is correct in Fireflies webhook settings
- Check that `PORT` is set in Railway (it should be auto-set, but verify)
- Look at Railway logs for `[Webhook]` entries

**Pre-call brief not triggering:**
- Verify the calendar event has `zoom.us` in the Location or Description field
- Check Railway logs for `[PreCallBrief]` entries
- Make sure `GAS_WEBHOOK_URL` is current (re-deploy Code.gs if needed)

**Google Doc not being created:**
- Verify `PRECALL_BRIEF_FOLDER_ID` is set correctly in Railway
- Make sure the folder is in your **work Google Drive** (steven@codecombat.com)
- The GAS bridge runs as your work account, so it can only access your work Drive

**Fireflies not joining calls:**
- Make sure Zoom is connected in Fireflies Settings → Integrations
- Check that you're using the same Google/Zoom account that Fireflies is connected to
