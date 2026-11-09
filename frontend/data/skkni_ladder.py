"""
Illustrative SKKNI career ladder for the onboarding "Choose Your Path" step
(pages/onboarding.py) - Digital Product Development functional group,
levels 2-9 (Kepmenaker No. 282/2016; BPSDM Komdigi's PON TIK 2025
occupational map, 68 occupations across these levels). Role names per
level come from that reference's Table 2.1; the illustrative single-branch
path (Programmer Staff -> ... -> Chief Technology Officer) comes from its
Figure 2.3.

Static/hardcoded, not modeled in Neo4j or Postgres - see the onboarding
design spec's engineering notes. Only ACTIVE_LEVEL/ACTIVE_ROLE has real
content built today: the 6 SKKNI units under Assistant Web Developer,
served from Neo4j (see utils/materials_api.py::get_all_units).
"""

ACTIVE_LEVEL = 4
ACTIVE_ROLE = "Assistant Web Developer"

# {level: [role names]} - level 4's only entry IS the active track
# (ACTIVE_ROLE); every role at every other level is a locked preview, not
# real, gated content.
LADDER = {
    2: ["Programmer Staff", "Multimedia Librarian Staff"],
    3: ["Junior Front-End Programmer", "Junior Back-End Programmer", "Junior Technical Support"],
    4: [ACTIVE_ROLE],
    5: ["Associate Application Programmer", "Associate Mobile Programmer", "Associate Programmer"],
    6: ["Frontend Developer", "Backend Developer", "Web Developer"],
    7: ["Software Engineer Manager", "Full Stack Developer", "Requirements Engineer"],
    8: ["Lead Programmer"],
    9: ["Chief Technology Officer", "Chief Business Applications Officer"],
}

LEVELS = sorted(LADDER.keys())


def get_roles_for_level(level: int) -> list:
    """Role names available at a given SKKNI level (empty list if unknown)."""
    return LADDER.get(level, [])
