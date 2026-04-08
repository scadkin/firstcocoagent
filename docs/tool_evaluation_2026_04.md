# Research Tool Evaluation — 2026-04-08 (Session 49)

Last full evaluation was Session 40. This pass checks whether the research engine's tool mix should change.

## Current stack

- **Serper** — primary SERP source. ~$0.001/query. Used for web search, news, and all signal scanners. Reliable.
- **Exa** — neural/semantic search. L16 (broad) and L17 (domain-scoped) in research_engine.py.
- **Firecrawl** — L18 (extract) + L19 (site map). **DEFERRED** — paid plan needed, skips gracefully when credits exhausted. Was #1 finding of Session 40 eval for contact extraction via schema-based extraction (10-20 verified contacts per district).
- **Brave Search** — L20 fallback.

## Session 49 findings

No tool swap warranted right now. Reasons:

1. **Serper + Exa + contact_extractor is working.** The F2 improvements this session (20K content window, known-contacts dedup) address the pain point without needing new tools.
2. **Firecrawl is still the highest-value unlock.** When budget allows, turning it on gives schema-based extraction across staff directories that no other tool in the current mix replicates.
3. **Crawl4AI** (open source) is interesting for self-hosted extraction but would add operational burden on Railway and doesn't beat Firecrawl's hosted extract API for this use case.
4. **Jina Reader API** (`r.jina.ai/<url>`) is free and produces clean markdown from messy HTML — worth a test as a cheap preprocessor before Claude extraction. Low-risk, no signup required. **Action:** test as a fallback when a target URL returns bloated HTML.
5. **Tavily** — specialized for AI agent search. Overlaps with Serper + Exa. Not worth adding a third search API unless Serper degrades.

## Pricing watch list

- **Firecrawl:** revisit when prospecting budget expands. Schema extract API is the unlock.
- **Exa:** currently on usage pricing — monitor spend trend via research jobs log.

## Next eval trigger

- If Firecrawl budget approved → run full extraction comparison vs current stack
- If research engine hit rate drops below baseline → re-evaluate
- Default cadence: every ~8 sessions
