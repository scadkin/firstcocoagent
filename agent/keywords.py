"""
keywords.py — Full title, keyword, and role constants for Scout's research engine.
All variations needed to find CS/STEM/CTE decision makers and influencers in K-12 districts.
"""

# ─────────────────────────────────────────────
# TIER 1 — DECISION MAKERS (highest priority)
# ─────────────────────────────────────────────

TIER1_TITLES = [
    # Superintendent-level
    "Superintendent",
    "Assistant Superintendent",
    "Deputy Superintendent",

    # Computer Science leadership
    "Computer Science Director",
    "CS Director",
    "Director of Computer Science",
    "Director of CS",
    "Computer Science Coordinator",
    "CS Coordinator",
    "Computer Science Department Head",
    "Executive Director of Computer Science",

    # CTE leadership
    "CTE Director",
    "Director of CTE",
    "Career and Technical Education Director",
    "Director of Career and Technical Education",
    "CTE Coordinator",
    "Career Technical Education Coordinator",
    "Executive Director of CTE",

    # STEM/STEAM leadership
    "STEM Director",
    "Director of STEM",
    "STEAM Director",
    "Director of STEAM",
    "STEM Coordinator",
    "STEAM Coordinator",
    "Executive Director of STEM",
    "STEM Program Director",

    # Curriculum & Instruction
    "Curriculum Director",
    "Director of Curriculum",
    "Director of Curriculum and Instruction",
    "Curriculum and Instruction Director",
    "Curriculum Coordinator",
    "Instructional Coordinator",
    "Chief Academic Officer",
    "CAO",
    "Director of Instruction",
    "Director of Academic Programs",
    "Curriculum Specialist",
    "Curriculum Developer",

    # Technology leadership
    "Director of Technology",
    "Educational Technology Director",
    "EdTech Director",
    "Director of Educational Technology",
    "Director of Instructional Technology",
    "Instructional Technology Director",
    "Learning Technology Director",
    "Director of Digital Learning",
    "Director of Blended Learning",
    "Chief Technology Officer",
    "CTO",
    "Director of Innovation",
    "Chief Innovation Officer",
    "Director of Digital Innovation",

    # Principal-level
    "Principal",
    "Assistant Principal",
    "Vice Principal",

    # Federal programs / grants
    "Title I Director",
    "Director of Title I",
    "Director of Federal Programs",
    "Federal Programs Director",
    "Grant Manager",
    "Grants Manager",
    "Grant Writer",
    "Grants Writer",
    "Grant Administrator",

    # Program management
    "K-12 CS Program Manager",
    "CS Program Manager",
    "STEM Program Manager",
    "Technology Program Manager",
]

# ─────────────────────────────────────────────
# TIER 2 — INFLUENCERS (teachers + coaches)
# ─────────────────────────────────────────────

TIER2_TITLES = [
    # CS / Coding teachers
    "Computer Science Teacher",
    "CS Teacher",
    "Coding Teacher",
    "Programming Teacher",
    "Computer Science Instructor",
    "CS Instructor",
    "Coding Instructor",
    "Programming Instructor",

    # AP CS teachers
    "AP Computer Science Teacher",
    "AP CS Teacher",
    "AP CSP Teacher",
    "AP CSA Teacher",
    "AP CompSci Teacher",
    "AP Computer Science Principles Teacher",
    "AP Computer Science A Teacher",
    "AP CS Principles Instructor",
    "AP CS A Instructor",

    # STEM / specialty teachers
    "STEM Teacher",
    "STEAM Teacher",
    "Robotics Teacher",
    "Robotics Coach",
    "Robotics Instructor",
    "Esports Teacher",
    "Esports Coach",
    "Game Design Teacher",
    "Game Development Teacher",
    "Game Dev Teacher",
    "Web Design Teacher",
    "Web Development Teacher",
    "Web Dev Teacher",
    "Engineering Teacher",
    "Technology Teacher",
    "Computer Teacher",
    "Digital Media Teacher",
    "Digital Literacy Teacher",

    # Instructional tech
    "Instructional Technology Coach",
    "Instructional Technology Coordinator",
    "Instructional Technology Specialist",
    "EdTech Coach",
    "Educational Technology Coach",
    "Educational Technology Specialist",
    "Digital Learning Coach",
    "Technology Integration Coach",
    "Technology Integration Specialist",
    "TOSA",
    "Teacher on Special Assignment",
    "Instructional Coach",
    "Innovation Coach",
    "Instructional Innovation Specialist",
    "Instructional Designer",

    # Makerspace / Lab
    "Makerspace Coordinator",
    "Makerspace Facilitator",
    "Maker Space Coordinator",
    "STEM Lab Coordinator",
    "STEAM Lab Coordinator",
    "Makerspace Director",

    # Library / Media
    "Librarian",
    "Media Specialist",
    "Library Media Specialist",
    "School Librarian",

    # After-school
    "After School Program Director",
    "After-School Program Director",
    "After School Director",
    "Extended Learning Director",
    "Out of School Time Director",

    # Department chair
    "CS Department Chair",
    "Computer Science Department Chair",
    "Technology Department Chair",
    "STEM Department Chair",
    "CTE Department Chair",
]

# ─────────────────────────────────────────────
# TIER 3 — HIGH-VALUE NETWORK (connectors)
# ─────────────────────────────────────────────

TIER3_TITLES = [
    "State CS Coordinator",
    "State Computer Science Coordinator",
    "Regional CS Consultant",
    "CSTA Chapter Leader",
    "CSforAll Lead",
    "CS4All Lead",
    "Girls Who Code Chapter Lead",
    "Girls Who Code Facilitator",
    "CS Program Manager",
    "Regional STEM Consultant",
    "ESC STEM Consultant",
    "Education Service Center CS Consultant",
]

# ─────────────────────────────────────────────
# ALL TITLES COMBINED (flat list, deduped)
# ─────────────────────────────────────────────

ALL_TITLES = list(dict.fromkeys(TIER1_TITLES + TIER2_TITLES + TIER3_TITLES))

# ─────────────────────────────────────────────
# SEARCH KEYWORDS (for Serper + site searches)
# ─────────────────────────────────────────────

CS_KEYWORDS = [
    "computer science",
    "CS",
    "coding",
    "programming",
    "computer programming",
    "computational thinking",
    "software development",
    "software engineering",
]

STEM_KEYWORDS = [
    "STEM",
    "STEAM",
    "S.T.E.M.",
    "S.T.E.A.M.",
    "science technology engineering math",
    "science technology engineering arts math",
]

TECH_KEYWORDS = [
    "educational technology",
    "EdTech",
    "instructional technology",
    "digital learning",
    "technology integration",
    "blended learning",
]

LANGUAGE_KEYWORDS = [
    "Python",
    "JavaScript",
    "Java",
    "Lua",
    "C++",
    "HTML",
    "CSS",
    "CoffeeScript",
]

SPECIALTY_KEYWORDS = [
    "AP CSP",
    "APCSP",
    "AP CS Principles",
    "AP Computer Science Principles",
    "AP CSA",
    "APCSA",
    "AP Computer Science A",
    "AP CompSci",
    "robotics",
    "esports",
    "game design",
    "game development",
    "web design",
    "web development",
    "makerspace",
    "maker space",
    "cybersecurity",
    "digital media",
    "digital literacy",
    "Girls Who Code",
]

CTE_KEYWORDS = [
    "CTE",
    "career and technical education",
    "career technical education",
    "vocational",
    "college and career readiness",
    "college career readiness",
]

ALL_KEYWORDS = (
    CS_KEYWORDS
    + STEM_KEYWORDS
    + TECH_KEYWORDS
    + LANGUAGE_KEYWORDS
    + SPECIALTY_KEYWORDS
    + CTE_KEYWORDS
)

# ─────────────────────────────────────────────
# DEPARTMENT NAMES (for site crawl targeting)
# ─────────────────────────────────────────────

TARGET_DEPARTMENTS = [
    "computer science",
    "CS department",
    "STEM",
    "STEAM",
    "CTE",
    "career and technical education",
    "curriculum and instruction",
    "educational technology",
    "instructional technology",
    "digital learning",
    "college and career readiness",
    "advanced academics",
    "educational services",
    "instructional services",
    "curriculum",
    "academic programs",
    "innovation",
    "technology",
]

# ─────────────────────────────────────────────
# COMMON DISTRICT EMAIL PATTERNS
# (used in Layer 8: email pattern inference)
# ─────────────────────────────────────────────

EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "{last}.{first}@{domain}",
    "{first}_{last}@{domain}",
    "{f}.{last}@{domain}",
    "{last}{f}@{domain}",
    "{first}@{domain}",
]

# ─────────────────────────────────────────────
# SHORT TITLE ALIASES (for Serper query building)
# Most effective short-form titles for search queries
# ─────────────────────────────────────────────

SERPER_PRIORITY_TITLES = [
    "Computer Science Director",
    "CS Director",
    "CTE Director",
    "STEM Director",
    "Computer Science Coordinator",
    "CS Coordinator",
    "Curriculum Director",
    "Director of Technology",
    "EdTech Director",
    "Instructional Technology Director",
    "CS Teacher",
    "Computer Science Teacher",
    "Coding Teacher",
    "AP CSP Teacher",
    "Robotics Teacher",
    "STEM Coordinator",
    "Director of Curriculum",
    "Chief Academic Officer",
    "Principal",
    "Superintendent",
    "Title I Director",
    "TOSA",
    "Instructional Technology Coach",
    "Director of Innovation",
    "After School Program Director",
    "Makerspace Coordinator",
]
