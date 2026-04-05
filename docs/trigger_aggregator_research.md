# Trigger-Based Prospecting Aggregator — Research (Session 43)

## K-12 BUYING SIGNALS (ranked by conversion strength)

### Tier 1 — Highest Conversion
1. **Bond measures passing** — $82B in bonds issued 2025. Voter-approved, locally controlled, 3-5 year spending. Source: Ballotpedia (quarterly)
2. **Leadership transitions** — New superintendent/CTO = 90-day vendor review window. Source: LinkedIn, TopSchoolJobs, state superintendent association career boards (TASA, IASA)
3. **Board meeting agenda items** — Mentions of "technology replacement," "curriculum adoption," "AI policy," "contract renewal." 30K+ board meetings/month nationwide. Source: BoardDocs sites (publicly accessible)
4. **RFP publications** — Formal buying intent, 28-45 day window. Source: RFPSchoolWatch, NationGraph, state procurement portals

### Tier 2 — Strong Indicators
5. **AI policy adoption** — Districts formalizing AI policies = 6-12 months from purchasing AI EdTech
6. **Job postings** — CS teachers, CTE directors, curriculum specialists = expanding program. Source: Indeed, SchoolSpring, K12JobSpot
7. **Grant awards** — Title IV-A, state CTE, Perkins. Earmarked funds with spending deadlines. E-Rate window: Jan-Apr ($4B/yr)
8. **Contract expirations** — Existing vendor contracts on 3-5 year cycles. Source: Sourcewell, OMNIA, TIPS

### Tier 3 — Useful Context
9. **State mandates** — CS requirements, CTE funding expansions
10. **Enrollment changes** — Growth = capacity needs, decline = optimization. Source: NCES
11. **Strategic plan releases** — "digital transformation," "computer science," "workforce readiness"
12. **Conference attendance** — ISTE, TCEA, CUE, state EdTech conferences

### Signal Clustering
Multiple simultaneous signals (bond + new CTO + board discussion) dramatically outperform any single indicator. 78% of K-12 deals take 6+ months.

### K-12 Procurement Calendar
| Window | Activity |
|--------|----------|
| Sep-Jan | Needs assessment — highest-value engagement window |
| Jan-Mar | Budget development, informal shortlisting |
| Feb-May | RFP publication, formal bids |
| May-Jun | Fiscal year-end spending surge (60-70% of decisions) |
| Jul-Aug | New fiscal year POs issued |

---

## BURBIO DEEP DIVE

### What It Tracks
- School board meeting minutes (50%+ of US K-12 population)
- District checkbook registers (actual vendor spending)
- ESSER III spending plans (7,000+ categorized)
- District budgets (CapEx and operating)
- School bonds (voting status, amounts)
- Strategic plans and RFPs
- Superintendent turnover tracking
- State funding sources with eligibility
- District contacts (new 2026)

### How It Works
Scrapes millions of public documents (board records, financial disclosures, strategic plans, budgets). "Signals Tracker" uses AI/NLP to classify mentions by topic. New "District Research Agent" (built with Domo) generates on-demand district summaries.

### Pricing: ~$3,000-6,000/year (avg $4,500)

### Competitors
- **AlchemyK12** — Similar + consulting
- **Civic IQ** — K-12 procurement intelligence, RFPs, board meetings
- **RFPSchoolWatch** — RFP aggregation from 21K+ districts
- **NationGraph** — Centralized bid/RFP database
- **SmartProcure** — FOIA-sourced purchase order data
- **BoardDocs (Diligent)** — 3,500+ districts use it. Public agendas are scrapeable.

### What We Can Replicate (60-70% of Burbio's value for $0)
1. Board meeting scraping — BoardDocs sites publicly accessible, Parse.bot/Firecrawl can extract
2. Keyword/signal alerting — Claude classifies board minutes for CS, AI, curriculum, budget mentions
3. Superintendent turnover — State career boards + LinkedIn monitoring
4. Bond measure tracking — Ballotpedia data is public

### What We CAN'T easily replicate
- Checkbook registers (requires FOIA at scale)
- 50-state comprehensive coverage (we only need 13 states)
- ESSER spending plan aggregation

---

## AI AGGREGATOR ARCHITECTURE (what developers are building)

### Best Open Source Projects
- **auto-news** (github.com/finaldie/auto-news) — 864 stars, MIT. Python + LangChain. Twitter, RSS, YouTube, Reddit, web. Outputs to Notion. Closest architectural match.
- **Horizon** (github.com/Thysrael/Horizon) — HN, RSS, Reddit, Telegram, GitHub. Claude/GPT-4 scoring.
- **Precis** (github.com/leozqin/precis) — Self-hosted RSS + LLM summarization.
- **RLLM** (github.com/DanielZhangyc/RLLM) — LLM-powered RSS reader.

### Common Architecture Pattern
```
Ingest (API poll / RSS / scrape)
    → Store (SQLite / Notion / Postgres)
    → LLM classify + summarize
    → Deliver (email / Telegram / web UI)
```
All poll-based (cron/scheduled), not webhooks. LangChain dominant orchestration.

---

## MCP SERVERS & TOOLS AVAILABLE

### What We Already Have
| Tool | Use For |
|------|---------|
| Firecrawl | Scrape BoardDocs, district sites, news |
| Parse.bot | Auto-generate scrapers for board meeting sites |
| Exa | Neural search for signals |
| Brave Search | Web search |
| Serper | Google SERP search |
| Gmail MCP | Read Burbio emails, Google Alerts, newsletters |

### MCPs To Add
| MCP | Use For | Cost |
|-----|---------|------|
| **Apify** (github.com/apify/apify-mcp-server) | 1,500+ pre-built scrapers including LinkedIn, Indeed, Twitter | $5/mo free credits |
| **Tavily** (github.com/tavily-ai/tavily-mcp) | AI-native search + extract | 1K free credits/mo |
| **Puppeteer MCP** | Browser automation for JS-heavy sites like BoardDocs | Free |
| **RSS MCP** (github.com/Lunran/rssmcp) | Monitor education news feeds, DOE RSS | Free |
| **Twitter MCP** (taazkareem/twitter-mcp-server) | Monitor EdTech chatter, policy announcements | Free (needs Twitter API) |
| **Reddit MCP** (saginawj/mcp-reddit-companion) | Monitor r/CSEducation, r/edtech | Free |

### Other Useful Tools (No MCP but scriptable)
| Tool | Use For | Cost |
|------|---------|------|
| **JobSpy** (github.com/speedyapply/JobSpy) | Scrape Indeed/LinkedIn/Glassdoor for K-12 job postings | Free, open source |
| **Jina AI Reader** | Free URL-to-markdown for board agendas | Free, 100 RPM |
| **Ballotpedia** | Bond measure tracking | Scrapeable |
| **SchoolSpring / K12JobSpot** | K-12 specific job boards | Scrapeable |

---

## PROPOSED SCOUT AGGREGATOR ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│  SIGNAL SOURCES (polled weekly by Scout on Railway)  │
├─────────────────────────────────────────────────────┤
│  Board Meetings    → Parse.bot/Firecrawl BoardDocs  │
│  Job Postings      → JobSpy (Indeed/LinkedIn)       │
│  News/Press        → Serper/Exa keyword monitoring   │
│  Burbio Emails     → Gmail MCP scan                  │
│  Google Alerts     → Gmail MCP scan                  │
│  DOE Newsletters   → Gmail MCP scan                  │
│  Bond Measures     → Ballotpedia scrape              │
│  RFPs              → State procurement portals       │
│  Leadership Change → LinkedIn/state career boards    │
│  RSS Feeds         → State DOE, EdWeek, ISTE feeds  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  CLAUDE CLASSIFICATION + SCORING                     │
│  - Relevance to CodeCombat (CS, AI, CTE, coding)    │
│  - Signal strength (Tier 1/2/3)                      │
│  - Territory filter (13 states + SoCal)              │
│  - Signal clustering (multiple signals = hot lead)   │
│  - Cross-check: already customer? already in queue?  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  OUTPUT                                              │
│  - Prospecting Queue (strategy="trigger")            │
│  - Telegram weekly digest to Steven                  │
│  - Google Sheet "Signals" tab for tracking           │
│  - Auto-queue high-confidence leads for research     │
└─────────────────────────────────────────────────────┘
```

### Phase 1 (Quick wins, low effort)
- Gmail scan: Burbio emails, Google Alerts, DOE newsletters → extract leads + signals
- Supercharge Google Alerts with better keywords
- Subscribe to DOE newsletters for all 13 states

### Phase 2 (Core aggregator)
- Board meeting scraping (top 200 priority districts via BoardDocs)
- Job posting monitoring (JobSpy for CS/CTE/curriculum roles)
- News monitoring (Serper/Exa for district + CS keyword combos)

### Phase 3 (Advanced)
- Bond measure tracking (Ballotpedia)
- Leadership change monitoring
- Signal clustering + auto-scoring
- RFP monitoring (state procurement portals)

---

Sources cited in agent research reports. Key: Civic IQ, Burbio, Salesmotion, EdWeek Market Brief, RFPSchoolWatch, auto-news GitHub, awesome-mcp-servers GitHub.
