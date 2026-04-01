"""
eval_config.py — Configuration for C2 research tool evaluation.

Test districts, tool registry, and shared constants.
"""

# ─────────────────────────────────────────────
# TEST DISTRICTS — All from Steven's 13 territory states + SoCal
# ─────────────────────────────────────────────

TEST_DISTRICTS = [
    {"name": "Houston ISD", "state": "Texas", "size": "large", "notes": "Complex site, deep hierarchy"},
    {"name": "Chicago Public Schools", "state": "Illinois", "size": "large", "notes": "Massive district"},
    {"name": "Rialto Unified School District", "state": "California", "size": "medium", "notes": "SoCal, previously researched"},
    {"name": "Kern County Superintendent of Schools", "state": "California", "size": "medium", "notes": "County office, SoCal edge case"},
    {"name": "Guthrie Public Schools", "state": "Oklahoma", "size": "small", "notes": "Rural, minimal web presence"},
    {"name": "Leander ISD", "state": "Texas", "size": "medium", "notes": "JS-heavy website"},
    {"name": "Columbus City Schools", "state": "Ohio", "size": "large", "notes": "Good web presence, Midwest"},
    {"name": "Beaumont ISD", "state": "Texas", "size": "small", "notes": "Steven's territory, verifiable"},
]

# Phase 1 districts (validate framework before scaling)
PHASE1_DISTRICTS = ["Houston ISD", "Guthrie Public Schools"]

# ─────────────────────────────────────────────
# SEARCH QUERIES — Same queries the baseline engine uses (L1-L5 style)
# ─────────────────────────────────────────────

PRIORITY_TITLES = [
    "Computer Science Director",
    "CS Director",
    "CTE Director",
    "STEM Director",
    "Computer Science Coordinator",
    "CS Coordinator",
    "Curriculum Director",
    "Director of Technology",
]

def build_search_queries(district_name: str, state: str) -> list[str]:
    """Build the standard search queries for a district (mirrors L1-L5)."""
    queries = []
    # L1-style: direct title search (top 5)
    for title in PRIORITY_TITLES[:5]:
        queries.append(f'"{title}" "{district_name}" email')
    # L2-style: variation sweep
    queries.extend([
        f'"{district_name}" "computer science" coordinator contact',
        f'"{district_name}" STEM director',
        f'"{district_name}" CTE director email',
        f'"{district_name}" instructional technology coordinator',
        f'"{district_name}" curriculum director',
    ])
    return queries


# ─────────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────────

AVAILABLE_TOOLS = [
    "baseline",        # Serper + httpx/BS4
    "crawl4ai",        # Serper + Crawl4AI scrape
    "firecrawl",       # Serper search + Firecrawl scrape
    "jina",            # Jina s.jina.ai + r.jina.ai
    "tavily",          # Tavily search with raw_content
    "exa",             # Exa semantic search + contents
    "parsebot",        # Parse.bot structured extraction
    "exa_firecrawl",   # Hybrid: Exa search + Firecrawl district scrape
]

# Tool-specific env var names
TOOL_API_KEYS = {
    "baseline": "SERPER_API_KEY",
    "crawl4ai": "SERPER_API_KEY",       # uses Serper for search, Crawl4AI for scrape
    "firecrawl": "FIRECRAWL_API_KEY",
    "jina": "JINA_API_KEY",             # optional for free tier
    "tavily": "TAVILY_API_KEY",
    "exa": "EXA_API_KEY",
    "parsebot": "PARSEBOT_API_KEY",
    "exa_firecrawl": "EXA_API_KEY",     # checks Exa key; Firecrawl checked inside adapter
}

# Cost per operation (for tracking)
COST_PER_QUERY = {
    "serper": 0.001,
    "firecrawl_search": 0.016,   # ~1 credit at Hobby tier
    "firecrawl_scrape": 0.016,
    "tavily_basic": 0.004,
    "tavily_advanced": 0.008,
    "exa_search": 0.005,
    "exa_content": 0.001,       # per result with content
    "jina_search": 0.0,         # free tier
    "jina_scrape": 0.0,         # free tier
    "parsebot": 0.01,           # rough estimate
}
