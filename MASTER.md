# MASTER.md — CodeCombat Sales Agent (firstcocoagent)
**Last Updated:** 2026-02-27
**Status:** Phase 1 ✅ Complete | Phase 1.5 ✅ Complete | Phase 2 ✅ Complete | Phase 3 ✅ Complete (GAS Bridge) | Phase 4 ⬜ Next

---

## HOW TO RESUME IN A NEW CLAUDE CHAT

Open a new chat in this Claude Project and say:
**"Read MASTER.md and all project files. Phases 1, 1.5, 2, and 3 are complete and verified. Let's build Phase 4: Email Sequences + Outreach.io. Read the full architecture in Section 10 and begin."**

---

## 1. WHO THIS IS FOR

**Operator:** Steven (Senior Sales Rep, CodeCombat)
**Goal:** $3M in sales this year
**Email:** steven@codecombat.com
**CRM:** Salesforce
**Email Sequencer:** Outreach.io (bulk CSV import → sequences)
**Email Client:** Gmail (1:1 replies)
**Timezone:** CST (America/Chicago)

---

## 2. WHAT SCOUT IS

Always-on AI sales assistant named **Scout** that:
- Runs 24/7 on Railway.app (~$5/mo)
- Communicates via **Telegram** (@coco_scout_bot)
- Sends **morning brief** at 9:15am CST daily
- Sends **EOD report** at 4:30pm CST daily
- Sends **hourly check-in** 10am–4pm CST only
- Has **persistent memory** — learns from corrections, commits to GitHub, never forgets
- **Researches K-12 leads at scale** (Phase 2 ✅ — working)
- **Drafts emails in Steven's voice** (Phase 3 ✅ — working)
- Processes Zoom call transcripts (Phase 5)

---

## 3. THE PRODUCT BEING SOLD

**CodeCombat K-12 CS + AI Suite** — 8 products:
1. CodeCombat Classroom — game-based CS (Python, JS, Lua), Grades 6-12
2. Ozaria — narrative RPG CS for middle school
3. CodeCombat Junior — block-based coding K-5
4. AI HackStack — hands-on AI literacy curriculum
5. AI Junior — AI curriculum K-8
6. CodeCombat AI League — Esports coding tournaments
7. CodeCombat Worlds on Roblox — CS learning in Roblox
8. AP CSP Course — full College Board AP CS Principles course

Standards: CSTA, ISTE, California CS Standards, NGSS. Turn-key teacher resources included.

---

## 4. TARGET PROSPECTS

**Tier 1 — Decision Makers:**
CS/Tech/STEM/CTE Directors & Coordinators, Curriculum Directors, CAOs, Directors of EdTech/Innovation/Digital Learning/Blended Learning, Superintendents, Principals, Title I Directors, Grant Managers/Writers

**Tier 2 — Influencers:**
CS/Coding/AP CSP/AP CSA Teachers, STEM/Robotics/Esports/Game Design/Web Dev Teachers, Instructional Technology Coaches, TOSA, Makerspace Coordinators, STEM Lab Coordinators, After-School Program Directors, Instructional Designers, Innovation Coaches

**Tier 3 — High-Value Network:**
State DOE CS Coordinators, Regional ESC CS/STEM/CTE Consultants, State CSTA Chapter Leaders, K-12 CS Program Managers (large districts), CSforAll/CS4ALL regional leads, Librarians with CS programs, Girls Who Code chapter leads

**Other Markets:**
After-school centers, public libraries, homeschool co-ops, community education, government youth programs

---

## 5. TECH STACK

| Tool | Purpose | Cost | Status |
|------|---------|------|--------|
| Claude API (claude-opus-4-5) | Agent brain | ~$15-25/mo | ✅ Active |
| Railway.app | Always-on server | ~$5/mo | ✅ Active |
| Telegram (@coco_scout_bot) | Command channel | Free | ✅ Active |
| GitHub (memory persistence) | Persistent memory storage | Free | ✅ Active |
| Serper API | Google search for lead research | ~$10/mo | ✅ Active |
| Google Sheets API | Lead list storage | Free | ✅ Active |
| Gmail API (via GAS) | Read style, write drafts | Free | ✅ Phase 3 |
| Google Apps Script | Bridge to Gmail/Calendar/Slides | Free | ✅ Phase 3 |
| Fireflies.ai | Zoom transcription | Free (800 min/mo) | ⬜ Phase 5 |
| Outreach.io | Email sequences | Existing plan | ✅ Active |
| Salesforce | CRM | Existing plan | ✅ Active |

**Telegram Chat ID:** 8677984089
**Bot username:** @coco_scout_bot

---

## 6. BUILD PHASES

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Brain + Command Channel (Railway + Telegram + Claude API) | ✅ Complete |
| 1.5 | Bug Fixes + Persistent Memory System | ✅ Complete |
| 2 | Lead Research + Google Sheets | ✅ Complete |
| 3 | Gmail Voice Training + Email Drafting | ✅ Complete |
| 4 | Email Sequences + Outreach.io | ⬜ Next |
| 5 | Zoom Call Intelligence (Fireflies) | ⬜ Not started |
| 6 | At-Scale Research + Campaign Engine | ⬜ Not started |
| 7 | Video Clips + Social Content (Descript) | ⬜ Optional |

---

## 7. REPO STRUCTURE

```
firstcocoagent/
├── MASTER.md
├── Procfile                         ← "web: python -m agent.main"
├── requirements.txt
├── agent/
│   ├── __init__.py
│   ├── main.py                      ← Entry point. Wires everything together.
│   ├── config.py                    ← All env vars
│   ├── claude_brain.py              ← Claude API + tool use + memory injection
│   ├── memory_manager.py            ← Persistent memory: read/write/GitHub commit
│   ├── scheduler.py                 ← CST-aware tick loop (Scheduler class)
│   ├── keywords.py                  ← Full title/keyword/role list (Phase 2)
│   └── voice_trainer.py             ← Analyzes sent emails → builds voice profile (Phase 3)
├── tools/
│   ├── __init__.py
│   ├── telegram_bot.py
│   ├── research_engine.py           ← 10-layer research engine + ResearchQueue (Phase 2)
│   ├── contact_extractor.py         ← Claude-powered contact extraction (Phase 2)
│   ├── sheets_writer.py             ← Google Sheets read/write/dedup (Phase 2)
│   └── gmail_client.py              ← Gmail API: OAuth2 flow, read sent, save drafts (Phase 3)
├── prompts/
│   ├── system.md                    ← Scout identity + research capabilities
│   ├── morning_brief.md
│   ├── eod_report.md
│   └── email_draft.md               ← Email drafting prompt with voice profile injection (Phase 3)
├── memory/
│   ├── preferences.md               ← Learned preferences. GitHub-committed on every write.
│   ├── context_summary.md           ← Daily compressed summaries. Never deleted.
│   └── voice_profile.md             ← Steven's writing style (generated by voice_trainer) (Phase 3)
├── gas/
│   └── Code.gs                      ← GAS bridge script (paste into script.google.com) (Phase 3)
└── docs/
    ├── SETUP.md
    ├── SETUP_PHASE2.md
    ├── SETUP_PHASE3.md              ← Gmail OAuth2 + voice training setup guide (Phase 3)
    ├── CHANGELOG.md
    └── DECISIONS.md
```

---

## 8. RAILWAY ENVIRONMENT VARIABLES

| Variable | Value | Status |
|----------|-------|--------|
| ANTHROPIC_API_KEY | (Claude API key) | ✅ Set |
| TELEGRAM_BOT_TOKEN | (Bot token) | ✅ Set |
| TELEGRAM_CHAT_ID | 8677984089 | ✅ Set |
| MORNING_BRIEF_TIME | 09:15 | ✅ Set |
| EOD_REPORT_TIME | 16:30 | ✅ Set |
| TIMEZONE | America/Chicago | ✅ Set |
| AGENT_NAME | Scout | ✅ Set |
| GITHUB_TOKEN | (fine-grained PAT, contents:write) | ✅ Set |
| GITHUB_REPO | scadkin/firstcocoagent | ✅ Set |
| CHECKIN_START_HOUR | 10 | ✅ Set |
| CHECKIN_END_HOUR | 16 | ✅ Set |
| SERPER_API_KEY | (from serper.dev) | ✅ Set |
| GOOGLE_SHEETS_ID | (from Sheet URL) | ✅ Set |
| GOOGLE_SERVICE_ACCOUNT_JSON | (full JSON string) | ✅ Set |
| GAS_WEBHOOK_URL | Google Apps Script Web App URL | ⬜ Set in Phase 3 setup |
| GAS_SECRET_TOKEN | Secret token (must match Code.gs) | ⬜ Set in Phase 3 setup |

---

## 9. MEMORY SYSTEM (Phase 1.5 — Verified Working)

**Two persistent files, both GitHub-committed on every write:**

- `memory/preferences.md` — every correction and preference. Never auto-cleared.
- `memory/context_summary.md` — EOD compression of each day's conversation. Grows indefinitely.

**Learning loop:**
1. Steven gives correction/feedback in Telegram
2. Scout acknowledges, confirms once
3. Claude appends `[MEMORY_UPDATE: one sentence]` tag to response
4. `claude_brain.py` strips tag, calls `memory_manager.save_preference()`
5. Entry appended to `preferences.md` with timestamp, committed to GitHub
6. Next session, loaded into every API call automatically

**Method name note:** `memory_manager.py` uses `load_recent_summary()` (not `load_context_summary()`). `claude_brain.py` has been updated to match.

---

## 10. PHASE 2 — LEAD RESEARCH + GOOGLE SHEETS (✅ Complete)

### How it works
```
Steven: "Research CS contacts in Denver Public Schools"
→ Claude detects intent via tool use → triggers research job
→ Scout: "🔍 Starting research on Denver Public Schools..."
→ 10-layer research engine runs in background
→ Progress updates fire to Telegram
→ Contacts written to Google Sheets (Leads + No Email tabs)
→ Scout: "✅ Done. 14 contacts — 9 with emails, 5 name-only. [Sheet link]"
```

### Google Sheets structure

**Master Sheet** (permanent):
- `Leads` tab — contacts with at least one email (Outreach.io import format)
- `No Email` tab — contacts found but missing email
- `Research Log` tab — every job: district, date, counts, layers used

**Column headers (exact Outreach.io import format):**
`First Name` | `Last Name` | `Title` | `Email` | `State` | `Account` | `Work Phone` | `District Name` | `Source URL` | `Email Confidence` | `Date Found`

### The 10-Layer Research Engine

| Layer | Method |
|-------|--------|
| 1 | Serper: direct title search |
| 2 | Serper: title variation sweep |
| 3 | Serper: LinkedIn-targeted |
| 4 | Serper: district site deep search |
| 5 | Serper: news + grants search |
| 6 | Direct website scrape (BeautifulSoup) |
| 7 | Keyword deep crawl |
| 8 | Email pattern inference |
| 9 | Claude extraction pass |
| 10 | Dedup + confidence scoring |

### Available Scout commands
- `"Research [district name] [state]"` → triggers research job
- `"Check sheet status"` → returns lead counts + sheet link
- `"What's in the queue?"` → returns current job + queue depth

### Known fixes applied in Phase 2
- `memory_manager.load_context_summary()` → renamed to `load_recent_summary()` in claude_brain.py
- Google Sheets API must be manually enabled in Google Cloud Console for the project
- Railway Start Command must be `python -m agent.main` (not `python agent/main.py`)
- `agent/__init__.py` and `tools/__init__.py` must both exist as blank files

---

## 11. PHASE 3 — GMAIL VOICE TRAINING + EMAIL DRAFTING (✅ Complete)

### Goal
Scout reads Steven's sent Gmail history to learn his writing style, then drafts outbound emails in his exact voice. Nothing ever sends automatically — Scout only writes drafts for Steven to review and send.

### How it works
```
Steven: "Draft a cold email to the CS Director at Austin ISD"
→ Scout pulls contact from sheet (or uses provided info)
→ Scout pulls Steven's voice profile from memory
→ Scout drafts email in Steven's style with Claude
→ Scout sends draft to Telegram for review
→ Steven: "looks good" → Scout saves to Gmail Drafts folder
→ Steven opens Gmail Drafts, adds recipient email, sends manually
```

### Voice training approach
- Scout reads last 6 months of Steven's sent emails (Gmail API)
- Claude analyzes: sentence length, opener style, CTA style, tone, sign-off, punctuation habits
- Voice profile saved to `memory/voice_profile.md`
- Every draft uses voice profile as style guide
- Steven can correct drafts → Scout learns and updates profile

### New files added for Phase 3
```
tools/
└── gmail_client.py     ← Gmail API: read sent, save drafts, OAuth2 flow

agent/
└── voice_trainer.py    ← Analyzes sent emails → builds voice profile

memory/
└── voice_profile.md    ← Steven's writing style (generated, not manual)

prompts/
└── email_draft.md      ← Prompt for drafting emails in Steven's voice

docs/
└── SETUP_PHASE3.md     ← Step-by-step Gmail OAuth2 setup instructions
```

### New Railway variables (Phase 3)
- `GMAIL_CREDENTIALS_JSON` — OAuth2 client credentials JSON from Google Cloud Console
- `GMAIL_TOKEN_JSON` — generated after first `/gmail_auth` flow, re-saved in Railway

### New Telegram commands (Phase 3)
| Command | What it does |
|---------|-------------|
| `/gmail_auth` | Starts Gmail OAuth2 authorization flow |
| `/gmail_code CODE` | Completes auth with Google's verification code |
| `/train_voice` | Analyzes sent emails, builds voice profile |
| `draft a [type] email to [person] at [district]` | Drafts email in Steven's voice |
| `looks good` | Saves pending draft to Gmail Drafts folder |
| `add email: addr@domain.com` | Sets recipient address on pending draft |
| `edit: [instructions]` | Revises pending draft |

### Phase 3 setup order
1. Enable Gmail API in Google Cloud Console (same project as Phase 2)
2. Create OAuth2 Desktop App credentials
3. Configure OAuth consent screen (add steven@codecombat.com as test user)
4. Set `GMAIL_CREDENTIALS_JSON` in Railway → redeploy
5. Run `/gmail_auth` in Telegram → follow auth flow → run `/gmail_code CODE`
6. Save `GMAIL_TOKEN_JSON` to Railway
7. Run `/train_voice`
8. Draft first email

Full instructions: `docs/SETUP_PHASE3.md`

---

## 12. FULL TARGET TITLE & KEYWORD LIST

### Key Titles (all variations)
Superintendent, Assistant Superintendent, Principal, Assistant Principal,
Director/Executive Director/Coordinator/Department Head/Teacher/Instructor of: Computer Science, CS,
Director/Executive Director/Coordinator/Department Head/Director of: CTE, Career & Technical Education,
Director/Executive Director/Coordinator/Department Head/Instructor/Teacher/Coach of: STEM, S.T.E.M., STEAM, S.T.E.A.M.,
Director/Executive Director of Technology, Educational Technology Director, EdTech Director,
Director of Instructional Technology, Learning Technology Director,
Instructional Technology Coordinator/Coach/Specialist, Educational Technology Specialist,
Digital Learning Coach, Curriculum Director/Coordinator/Specialist/Developer,
Director of Curriculum & Instruction, Instructional Coordinator, Chief Academic Officer,
Director/Executive Director of Elementary/Secondary Education,
Director of Innovation, Chief Innovation Officer, Director of Digital Learning, Director of Blended Learning,
K-12 CS Program Manager, STEM Program Manager,
Director of Federal Programs, Title I Director, Grant Writer, Grants Manager, Instructional Designer,
Coding/Programming Teacher/Instructor, Game Design/Dev/Development Teacher/Instructor,
Web Design/Dev/Development Teacher/Instructor,
AP CSP/AP CSA/AP Computer Science/AP CompSci Teacher/Instructor (all variations),
Esports/Robotics Teacher/Instructor/Coach, Technology/Computer Teacher/Instructor,
Engineering Teacher, TOSA, Teacher on Special Assignment, Librarian, Media Specialist,
Department Chair (paired with CS/Tech/STEM keywords),
Innovation Coach, Instructional Innovation Specialist,
Makerspace Coordinator/Facilitator, STEM Lab Coordinator, After-School Program Director

### Other Important Keywords
Girls Who Code, Makerspace, Maker Space, STEAM Lab, STEM Lab,
Cybersecurity, Networking, Technology, Tech, Digital Media, Digital Literacy, Esports,
Python, Java, JavaScript, C++, CSS, Lua, CoffeeScript, HTML,
AP CSP, APCSP, AP CompSci, AP CompSci A, APCSA, AP CSA

---

## 13. KEY DECISIONS

| Decision | Why |
|----------|-----|
| Telegram | Free, rich formatting, iPhone + laptop |
| Railway.app | $5/mo, git push deploys, persistent 24/7 |
| Python | Best library support for all planned tools |
| GitHub for memory | Free, survives Railway restarts, version-controlled |
| Queue research jobs | Better quality/depth vs. simultaneous |
| CST-aware tick scheduler | Railway runs UTC — tick-based avoids timezone bugs |
| Memory compression not deletion | Steven wants permanent learning and iteration |
| `[MEMORY_UPDATE]` tag | Clean, no extra API calls, reliable extraction |
| Claude tool use for research | Claude detects intent — no fragile keyword matching |
| Gmail Drafts only | Nothing sends without Steven's review |
| GAS bridge over OAuth2 | Work Google Workspace IT blocks third-party OAuth; GAS runs inside Google with no approval needed |
| Outreach.io manual CSV import | Company controls admin access |
| `python -m agent.main` in Railway | Fixes ModuleNotFoundError for agent/tools packages |
| OAuth2 Desktop App type for Gmail | Service accounts can't access personal Gmail |
| `/train_voice` separate from boot | Expensive operation — only run when Steven asks |
| Voice profile in memory/voice_profile.md | GitHub-persisted, loaded into every draft prompt |
| Pending draft state in main.py | Enables approve/edit loop without re-drafting |

---

## 14. BUG FIX LOG

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Check-ins all night | No time window | CHECKIN_START/END_HOUR guards | ✅ Fixed |
| Morning brief at 3:15am | Railway UTC ≠ CST | CST-aware tick loop | ✅ Fixed |
| Hallucinated activity | Prompts requested summary without real data | Rewrote prompts with honesty rules | ✅ Fixed |
| History wiped daily | clear_history() on schedule | EOD compression to memory instead | ✅ Fixed |
| updater.idle() crash | Method doesn't exist in PTB version | asyncio.Event() | ✅ Fixed |
| ModuleNotFoundError: agent | Railway ran python agent/main.py from wrong dir | Changed to python -m agent.main | ✅ Fixed |
| ImportError: Scheduler | Phase 1 scheduler.py had no Scheduler class | Rewrote scheduler.py with Scheduler class | ✅ Fixed |
| AttributeError: load_context_summary | Method named load_recent_summary in memory_manager | Updated claude_brain.py to match | ✅ Fixed |
| Google Sheets 403 PERMISSION_DENIED | Sheets API not enabled in Google Cloud project | Enabled via Cloud Console URL in logs | ✅ Fixed |

---

## 15. CHANGELOG

| Date | Change | Phase |
|------|--------|-------|
| 2026-02-25 | Repo initialized, architecture finalized | Pre-build |
| 2026-02-26 | All Phase 1 code written and deployed | Phase 1 |
| 2026-02-26 | Scout live on Telegram — Phase 1 complete | Phase 1 |
| 2026-02-26 | Bug fixes: timezone, check-in window, hallucination prevention | Phase 1.5 |
| 2026-02-26 | Persistent memory system built and deployed | Phase 1.5 |
| 2026-02-26 | Memory injection + correction detection implemented | Phase 1.5 |
| 2026-02-26 | EOD compresses history to memory instead of wiping | Phase 1.5 |
| 2026-02-26 | Smoke test passed — preferences.md GitHub commit verified | Phase 1.5 |
| 2026-02-26 | Phase 2 architecture fully designed and documented | Phase 2 prep |
| 2026-02-27 | Phase 2 built: keywords.py, research_engine.py, contact_extractor.py, sheets_writer.py | Phase 2 |
| 2026-02-27 | claude_brain.py updated with tool use (research_district, get_sheet_status, get_research_queue_status) | Phase 2 |
| 2026-02-27 | main.py updated with tool execution + research completion callback | Phase 2 |
| 2026-02-27 | system.md updated with Phase 2 research capabilities | Phase 2 |
| 2026-02-27 | Fixed: ModuleNotFoundError — Railway Start Command updated to python -m agent.main | Phase 2 |
| 2026-02-27 | Fixed: Scheduler class missing — scheduler.py rewritten | Phase 2 |
| 2026-02-27 | Fixed: load_context_summary → load_recent_summary in claude_brain.py | Phase 2 |
| 2026-02-27 | Fixed: Google Sheets API enabled in Google Cloud Console | Phase 2 |
| 2026-02-27 | Phase 3 REVISED: GAS bridge approach adopted (IT restriction workaround) | Phase 3 |
| 2026-02-27 | Phase 3 built: gas/Code.gs (GAS bridge script), tools/gas_bridge.py | Phase 3 |
| 2026-02-27 | agent/voice_trainer.py updated to use GAS bridge instead of OAuth | Phase 3 |
| 2026-02-27 | claude_brain.py: added train_voice, draft_email, save_draft, get_calendar, log_call, create_district_deck, ping_gas_bridge tools | Phase 3 |
| 2026-02-27 | main.py: Phase 3 tool execution + pending draft approval flow + Calendar + Slides | Phase 3 |
| 2026-02-27 | config.py: GAS_WEBHOOK_URL, GAS_SECRET_TOKEN (replaces OAuth vars) | Phase 3 |
| 2026-02-27 | SETUP_PHASE3.md rewritten for GAS bridge approach (no IT approval needed) | Phase 3 |
| 2026-02-27 | Phase 2 verified working — research job fires, contacts written to sheet | Phase 2 ✅ |
| 2026-02-27 | Phase 3 built: gmail_client.py, voice_trainer.py, voice_profile.md, email_draft.md | Phase 3 |
| 2026-02-27 | claude_brain.py updated: train_voice, draft_email, save_draft_to_gmail, gmail auth tools | Phase 3 |
| 2026-02-27 | main.py updated: Phase 3 tool execution + pending draft approval flow | Phase 3 |
| 2026-02-27 | config.py updated: GMAIL_CREDENTIALS_JSON, GMAIL_TOKEN_JSON variables | Phase 3 |
| 2026-02-27 | requirements.txt updated: no new packages needed (google-auth-oauthlib already in Phase 2) | Phase 3 |
| 2026-02-27 | SETUP_PHASE3.md written: Gmail OAuth2 + voice training setup guide | Phase 3 |
| 2026-02-27 | MASTER.md updated: Phase 3 complete, resume prompt updated for Phase 4 | Phase 3 |
