# SETUP.md — Step-by-Step Setup Guide

Follow these steps in order. Each section is one tool.
Estimated total setup time: 2–3 hours (mostly waiting for APIs to provision).

---

## STEP 1: GitHub Repo

1. Go to github.com and create a new repo named `codecombat-agent`
2. Set it to **Private**
3. Clone it locally: `git clone https://github.com/YOUR_USERNAME/codecombat-agent.git`
4. Copy all files from this repo into it
5. Commit and push: `git add . && git commit -m "Initial structure" && git push`

---

## STEP 2: Claude API Key

1. Go to console.anthropic.com
2. Create an account or log in
3. Go to **API Keys** → **Create Key**
4. Copy the key and save it — you only see it once
5. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

**Estimated cost:** $15–25/mo at your usage level

---

## STEP 3: Telegram Bot

1. Open Telegram on your phone
2. Search for **@BotFather** and start a chat
3. Send: `/newbot`
4. Name it: `Scout` (or whatever you prefer)
5. Username: `codecombat_scout_bot` (must be unique, add numbers if taken)
6. BotFather will give you a **token** — copy it
7. Add to `.env`: `TELEGRAM_BOT_TOKEN=...`

**Get your personal Chat ID:**
1. Search for **@userinfobot** on Telegram
2. Start it — it will reply with your Chat ID
3. Add to `.env`: `TELEGRAM_CHAT_ID=...`

---

## STEP 4: Railway.app (Always-On Server)

1. Go to railway.app and sign up with your GitHub account
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `codecombat-agent` repo
4. Railway will auto-detect it as a Python app
5. Go to **Variables** and add all your `.env` values here
6. Railway will deploy automatically — your agent is now live 24/7

**To redeploy after changes:** `git push` — Railway auto-deploys on every push

**Cost:** ~$5/mo (first $5 is free credit)

---

## STEP 5: Gmail API

1. Go to console.cloud.google.com
2. Create a new project: `codecombat-agent`
3. Go to **APIs & Services** → **Enable APIs**
4. Enable: **Gmail API** and **Google Sheets API**
5. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
6. Application type: **Desktop App**
7. Download the credentials JSON
8. Run the auth script once locally to get your refresh token:
   ```
   python tools/gmail_auth.py
   ```
9. Add the resulting tokens to `.env`

---

## STEP 6: Google Sheets

1. Go to sheets.google.com
2. Create a new sheet: `CodeCombat Leads Master`
3. Copy the Sheet ID from the URL (the long string between /d/ and /edit)
4. Add to `.env`: `GOOGLE_SHEETS_ID=...`
5. Share the sheet with your Gmail address (already have access)

---

## STEP 7: Fireflies.ai (Zoom Transcription)

1. Go to fireflies.ai and sign up with your Google account
2. Go to **Integrations** → connect your Zoom account
3. Go to **Settings** → rename the bot to `Notes`
4. Go to **API** → copy your API key
5. Add to `.env`: `FIREFLIES_API_KEY=...`
6. In Make.com, create a webhook that triggers when Fireflies sends a transcript complete notification

**Free tier:** 800 minutes/month transcription

---

## STEP 8: Make.com (Automation Glue)

1. Go to make.com and create a free account
2. You will create scenarios here to connect tools — detailed instructions in each phase's build doc
3. The free tier gives 1,000 operations/month which is enough to start

---

## VERIFICATION CHECKLIST

After setup, confirm each of these works:

- [ ] Send a message to your Telegram bot and get a response
- [ ] Agent sends a test morning brief
- [ ] Agent can write to your Google Sheet
- [ ] Agent can create a Gmail draft
- [ ] Railway shows the app as active with no errors
- [ ] Fireflies joins a test Zoom call and sends a transcript

---

## TROUBLESHOOTING

**Agent not responding on Telegram:** Check Railway logs for errors. Most common issue is a missing or wrong API key in Railway variables.

**Gmail auth failing:** OAuth tokens expire. Re-run `python tools/gmail_auth.py` to refresh.

**Railway deploy failing:** Check that `requirements.txt` is complete and `Procfile` points to the right file.
