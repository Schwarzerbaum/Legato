"""
L8 — LegatumPassport
Credentialed impact badge system for Stifter.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

PassportTier = Literal["Bronze", "Silver", "Gold", "Platinum"]

_BADGE_DEFINITIONS = {
    "first_step":       {"title": "Erster Schritt",       "icon": "🌱", "threshold_eur": 0},
    "impact_starter":  {"title": "Impact Starter",        "icon": "⚡", "threshold_eur": 1_000},
    "sdg_champion":    {"title": "SDG Champion",          "icon": "🎯", "threshold_eur": 10_000},
    "foundation_ready":{"title": "Foundation Ready",      "icon": "🏛", "threshold_eur": 50_000},
    "legacy_builder":  {"title": "Legacy Builder",        "icon": "🌳", "threshold_eur": 100_000},
    "platinum_stifter":{"title": "Platinum Stifter",      "icon": "💎", "threshold_eur": 500_000},
}


@dataclass
class PassportBadge:
    id: str
    title: str
    icon: str
    earned_at: str


@dataclass
class LegatumPassport:
    donor_id: str
    total_committed_eur: float
    badges: list[PassportBadge] = field(default_factory=list)
    credibility_score: float = 0.0
    tier: PassportTier = "Bronze"


def _calc_tier(score: float) -> PassportTier:
    if score >= 90:
        return "Platinum"
    if score >= 70:
        return "Gold"
    if score >= 40:
        return "Silver"
    return "Bronze"


def build_passport(
    donor_id: str,
    total_committed_eur: float,
    completed_gates: int = 0,
    ngo_count: int = 0,
) -> LegatumPassport:
    badges: list[PassportBadge] = []
    now = datetime.utcnow().strftime("%Y-%m-%d")

    for bid, defn in _BADGE_DEFINITIONS.items():
        if total_committed_eur >= defn["threshold_eur"]:
            badges.append(PassportBadge(
                id=bid, title=defn["title"], icon=defn["icon"], earned_at=now,
            ))

    # Score: 40% commitment, 30% gates, 30% NGO diversity
    commitment_score = min(40.0, (total_committed_eur / 500_000) * 40)
    gate_score       = min(30.0, (completed_gates / 6) * 30)
    ngo_score        = min(30.0, (ngo_count / 5) * 30)
    credibility      = round(commitment_score + gate_score + ngo_score, 1)

    return LegatumPassport(
        donor_id=donor_id,
        total_committed_eur=total_committed_eur,
        badges=badges,
        credibility_score=credibility,
        tier=_calc_tier(credibility),
    )


def passport_to_dict(p: LegatumPassport) -> dict:
    return {
        "donor_id": p.donor_id,
        "total_committed_eur": p.total_committed_eur,
        "credibility_score": p.credibility_score,
        "tier": p.tier,
        "badge_count": len(p.badges),
        "badges": [
            {"id": b.id, "title": b.title, "icon": b.icon, "earned_at": b.earned_at}
            for b in p.badges
        ],
    }
