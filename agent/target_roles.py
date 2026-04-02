"""
target_roles.py — Defines the exact roles, titles, and keywords Scout targets.

Source: Steven's "ROLES and KEYWORDS for Searching and Scraping" doc (2026-04-01).

These are used by:
- contact_extractor.py: Claude extraction prompt
- research_engine.py: search queries
- eval_deep_research.py: evaluation framework

IMPORTANT: CTE roles are only relevant if they relate to CS, Technology, or Computers.
Generic CTE (culinary, automotive, health science, cosmetology, etc.) are NOT targets.
"""

# ─────────────────────────────────────────────
# TIER 1: Primary decision-makers (highest priority)
# ─────────────────────────────────────────────
TIER1_TITLES = [
    # District leadership
    "Superintendent",
    "Assistant Superintendent",
    "Chief Academic Officer",

    # CS-specific leadership
    "Director of Computer Science",
    "Computer Science Director",
    "Executive Director of Computer Science",
    "Computer Science Coordinator",
    "Computer Science Department Head",

    # CTE leadership (decision-makers for CS programs)
    "Director of CTE",
    "Executive Director of CTE",
    "CTE Director",
    "CTE Coordinator",

    # STEM/STEAM leadership
    "Director of STEM",
    "Director of STEAM",
    "Executive Director of STEM",
    "STEM Director",
    "STEAM Director",
    "STEM Coordinator",
    "STEAM Coordinator",

    # Curriculum leadership
    "Curriculum Director",
    "Director of Curriculum",
    "Director of Curriculum & Instruction",
    "Curriculum Specialist",

    # Technology leadership
    "Director of Technology",
    "Executive Director of Technology",
    "Technology Director",
    "Educational Technology Director",
    "Director of Instructional Technology",
    "EdTech Director",

    # Education level directors
    "Director of Elementary Education",
    "Director of Secondary Education",
    "Executive Director of Elementary Education",
    "Executive Director of Secondary Education",
]

# ─────────────────────────────────────────────
# TIER 2: Implementers and influencers
# ─────────────────────────────────────────────
TIER2_TITLES = [
    # School leadership
    "Principal",
    "Assistant Principal",

    # CS teachers
    "Computer Science Teacher",
    "CS Teacher",
    "Computer Science Instructor",
    "CS Instructor",
    "Computer Teacher",

    # Coding/Programming
    "Coding Teacher",
    "Programming Teacher",
    "Coding Instructor",
    "Programming Instructor",

    # AP CS
    "AP CSP Teacher",
    "AP Computer Science Principles Teacher",
    "AP CSA Teacher",
    "AP Computer Science Teacher",
    "AP CompSci Teacher",

    # STEM/STEAM teachers
    "STEM Teacher",
    "STEAM Teacher",
    "STEM Instructor",
    "STEAM Instructor",
    "STEM Coach",
    "STEAM Coach",
    "STEM Department Head",
    "STEAM Department Head",

    # Game/Web design
    "Game Design Teacher",
    "Game Development Teacher",
    "Game Dev Teacher",
    "Web Design Teacher",
    "Web Development Teacher",

    # Esports
    "Esports Teacher",
    "Esports Instructor",
    "Esports Coach",

    # Robotics
    "Robotics Teacher",
    "Robotics Instructor",
    "Robotics Coach",

    # Engineering
    "Engineering Teacher",

    # Technology
    "Technology Teacher",
    "Technology Instructor",
    "Instructional Technology Coordinator",
    "Instructional Technology Coach",
    "Instructional Technology Specialist",
    "Educational Technology Specialist",
    "Digital Learning Coach",

    # Curriculum support
    "Instructional Coordinator",
    "Curriculum Developer",
    "TOSA",
    "Teacher on Special Assignment",

    # Library/Media
    "Librarian",
    "Media Specialist",

    # CTE department heads (only CS/Tech related)
    "CTE Department Head",
]

# ─────────────────────────────────────────────
# KEYWORDS: What to search for (in content, not titles)
# ─────────────────────────────────────────────
CS_KEYWORDS = [
    "computer science", "coding", "programming", "AP CSP", "AP CSA",
    "APCSP", "APCSA", "AP CompSci", "Python", "Java", "JavaScript",
    "C++", "HTML", "CSS", "Lua", "CoffeeScript",
]

TECH_KEYWORDS = [
    "cybersecurity", "networking", "digital media", "digital literacy",
    "technology", "esports", "makerspace", "maker space",
    "STEM lab", "STEAM lab", "Girls Who Code",
]

# Keywords that indicate a CTE role IS relevant (CS/Tech related)
CTE_RELEVANT_KEYWORDS = [
    "computer", "technology", "cs", "coding", "programming", "cyber",
    "networking", "digital", "software", "web", "game", "esports",
    "information technology", "IT", "data science", "AI", "artificial intelligence",
]

# Keywords that indicate a CTE role is NOT relevant (wrong trade)
CTE_EXCLUDE_KEYWORDS = [
    "culinary", "cosmetology", "automotive", "auto body", "welding",
    "plumbing", "electrical", "hvac", "construction", "carpentry",
    "health science", "nursing", "medical", "dental", "pharmacy",
    "agriculture", "animal", "floral", "horticulture", "veterinary",
    "fashion", "interior design", "child development", "early childhood",
    "criminal justice", "law enforcement", "firefight",
    "hospitality", "tourism", "food service", "baking",
]

# ─────────────────────────────────────────────
# DEPARTMENTS worth searching for
# ─────────────────────────────────────────────
TARGET_DEPARTMENTS = [
    "Educational Services",
    "Instructional Services",
    "Curriculum & Instruction",
    "College & Career Readiness",
    "Advanced Academics",
    "Career & Technical Education",  # only CS/Tech related roles
    "Technology Department",
    "Information Technology",
]

# ─────────────────────────────────────────────
# REGIONAL SERVICE ENTITIES (ESAs)
# Steven's territory ESA types by state
# ─────────────────────────────────────────────
REGIONAL_ENTITIES = {
    "TX": ("Regional Education Service Center", 20),
    "CA": ("County Office of Education", 58),
    "IL": ("Regional Office of Education / Intermediate Service Center", 38),
    "PA": ("Intermediate Unit", 29),
    "OH": ("Educational Service Center", 51),
    "MI": ("Intermediate School District", 56),
    "CT": ("Regional Education Service Center", 6),
    "MA": ("Educational Collaborative", 25),
    "IN": ("Educational Service Center", 9),
    "NE": ("Educational Service Unit", 17),
    "TN": ("Educational Cooperative", 0),  # informal
    "OK": (None, 0),  # no ESA system
    "NV": (None, 0),  # no ESA system
}

# Generic ESA name patterns (for search queries across all states)
ESA_PATTERNS = [
    "Education Service Center",
    "Educational Service Center",
    "Regional Education Service Center",
    "County Office of Education",
    "Intermediate Unit",
    "Intermediate School District",
    "Board of Cooperative Educational Services",  # BOCES
    "Cooperative Educational Service Agency",  # CESA
    "Educational Service Unit",  # ESU
    "Area Education Agency",  # AEA
    "Educational Collaborative",
]


def is_relevant_cte_role(title: str) -> bool:
    """Check if a CTE role is relevant to CS/Technology (not culinary, automotive, etc.)."""
    title_lower = title.lower()

    # If title contains CTE/Career & Technical but no CS/Tech keyword, check exclusions
    is_cte = any(x in title_lower for x in ["cte", "career & technical", "career and technical", "cate"])
    if not is_cte:
        return True  # Not a CTE role, so no CTE filtering needed

    # CTE role — check if it's CS/Tech related
    if any(kw in title_lower for kw in CTE_RELEVANT_KEYWORDS):
        return True

    # Check if it's an excluded trade
    if any(kw in title_lower for kw in CTE_EXCLUDE_KEYWORDS):
        return False

    # Generic CTE leadership roles (Director, Coordinator) are always relevant
    if any(x in title_lower for x in ["director", "coordinator", "executive", "department head"]):
        return True

    # Unknown CTE role — include with lower confidence
    return True
