"""
L9 — Stifter Intelligence
AI-driven philanthropic giving strategy generation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

RiskTolerance = Literal["low", "medium", "high"]

_ARCHETYPE_PROFILES: dict[str, dict] = {
    "Visionär": {
        "strategy_name": "Systemwandel-Portfolio",
        "focus": "Großskalige SDG-Interventionen mit messbarer globaler Wirkung",
        "instruments": ["Impact Bonds", "Collective Impact Fonds", "SDG-ETF"],
        "annual_pct": 0.07,
    },
    "Bewahrer": {
        "strategy_name": "Natur & Erbe Portfolio",
        "focus": "Langfristiger Schutz von Ökosystemen und Kulturerbe",
        "instruments": ["Naturschutzfonds", "Erbschaftsstiftungen", "Community Foundations"],
        "annual_pct": 0.04,
    },
    "Gestalter": {
        "strategy_name": "Bildungs-Infrastruktur Portfolio",
        "focus": "Direkte Wirkung durch Bildungsprojekte und lokale Stiftungen",
        "instruments": ["Bildungsfonds", "lokale NGO-Grants", "Stipendienprogramme"],
        "annual_pct": 0.05,
    },
    "Brückenbauer": {
        "strategy_name": "Inklusions-Netzwerk Portfolio",
        "focus": "Verbindung von Donor-Netzwerken für multiplizierte Wirkung",
        "instruments": ["Matching-Gift-Programme", "Co-Funding-Runden", "Diaspora-Bonds"],
        "annual_pct": 0.05,
    },
    "Pionier": {
        "strategy_name": "Innovations-Katalysator Portfolio",
        "focus": "Frühphasen-Impact-Investitionen in unerprobte Lösungsansätze",
        "instruments": ["Social Venture Capital", "R&D Grants", "Prize Challenges"],
        "annual_pct": 0.08,
    },
}

_RISK_MULTIPLIER: dict[str, float] = {
    "low": 0.7, "medium": 1.0, "high": 1.3,
}


@dataclass
class GivingStrategy:
    archetype: str
    strategy_name: str
    focus: str
    instruments: list[str]
    sdg_focus: list[int]
    annual_commitment_eur: float
    five_year_total_eur: float
    risk_tolerance: RiskTolerance
    rationale: str
    suggested_ngo_count: int = 3


def generate_strategy(
    archetype: str,
    total_wealth_eur: float,
    sdg_affinity: list[int],
    risk_tolerance: RiskTolerance = "medium",
) -> GivingStrategy:
    profile = _ARCHETYPE_PROFILES.get(archetype, _ARCHETYPE_PROFILES["Gestalter"])
    base_pct = profile["annual_pct"] * _RISK_MULTIPLIER[risk_tolerance]
    annual = round(total_wealth_eur * base_pct, 2)
    five_year = round(annual * 5, 2)

    return GivingStrategy(
        archetype=archetype,
        strategy_name=profile["strategy_name"],
        focus=profile["focus"],
        instruments=profile["instruments"],
        sdg_focus=sdg_affinity[:4],
        annual_commitment_eur=annual,
        five_year_total_eur=five_year,
        risk_tolerance=risk_tolerance,
        rationale=(
            f"{archetype}-Profil mit {risk_tolerance} Risikobereitschaft: "
            f"{base_pct:.1%} des Vermögens jährlich für maximale SDG-Wirkung."
        ),
        suggested_ngo_count=3 if risk_tolerance == "low" else 5,
    )


def strategy_to_dict(s: GivingStrategy) -> dict:
    return {
        "archetype": s.archetype,
        "strategy_name": s.strategy_name,
        "focus": s.focus,
        "instruments": s.instruments,
        "sdg_focus": s.sdg_focus,
        "annual_commitment_eur": s.annual_commitment_eur,
        "five_year_total_eur": s.five_year_total_eur,
        "risk_tolerance": s.risk_tolerance,
        "rationale": s.rationale,
        "suggested_ngo_count": s.suggested_ngo_count,
    }
