"""
L4 — LBBW Advisor Interface
Matches a donor persona to the best-fit LBBW philanthropic advisor.
"""
from __future__ import annotations
from dataclasses import dataclass

# In production this would come from a CRM / LBBW staff directory.
_ADVISOR_POOL = [
    {
        "advisor_id": "ADV-001",
        "name": "Dr. Anna Hoffmann",
        "title": "Senior Philanthropy Advisor",
        "specialisations": ["Stiftungsgründung", "Bildung", "SDG 4"],
        "persona_fit": ["Gestalter", "Brückenbauer"],
        "languages": ["de", "en"],
    },
    {
        "advisor_id": "ADV-002",
        "name": "Markus Bauer",
        "title": "Impact Investment Specialist",
        "specialisations": ["Klimaschutz", "ESG", "SDG 13", "SDG 7"],
        "persona_fit": ["Visionär", "Pionier"],
        "languages": ["de", "en", "fr"],
    },
    {
        "advisor_id": "ADV-003",
        "name": "Julia Schneider",
        "title": "Foundation Structuring Lead",
        "specialisations": ["Vermächtnis", "Familienrecht", "SDG 1", "SDG 2"],
        "persona_fit": ["Bewahrer", "Brückenbauer"],
        "languages": ["de"],
    },
]


@dataclass
class AdvisorMatch:
    advisor_id: str
    name: str
    title: str
    specialisations: list[str]
    match_score: float
    rationale: str
    next_step: str


def match_advisor(archetype: str, preferred_sdgs: list[int] | None = None) -> AdvisorMatch:
    """Return the best-fit advisor for a given persona archetype."""
    preferred_sdgs = preferred_sdgs or []

    best = None
    best_score = -1.0

    for adv in _ADVISOR_POOL:
        score = 0.0
        if archetype in adv["persona_fit"]:
            score += 0.6
        sdg_labels = [f"SDG {s}" for s in preferred_sdgs]
        overlap = len(set(sdg_labels) & set(adv["specialisations"]))
        score += overlap * 0.2
        if score > best_score:
            best_score = score
            best = adv

    if best is None:
        best = _ADVISOR_POOL[0]
        best_score = 0.3

    return AdvisorMatch(
        advisor_id=best["advisor_id"],
        name=best["name"],
        title=best["title"],
        specialisations=best["specialisations"],
        match_score=round(best_score, 2),
        rationale=f"Best fit for {archetype} profile with focus on {', '.join(best['specialisations'][:2])}",
        next_step="Schedule 30-min intro call via LBBW Philanthropy Desk",
    )


def advisor_to_dict(match: AdvisorMatch) -> dict:
    return {
        "advisor_id": match.advisor_id,
        "name": match.name,
        "title": match.title,
        "specialisations": match.specialisations,
        "match_score": match.match_score,
        "rationale": match.rationale,
        "next_step": match.next_step,
    }
