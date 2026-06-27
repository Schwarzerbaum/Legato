"""
L5 — Living Impact Universe
Real-time SDG allocation and lives-impacted simulation.
"""
from __future__ import annotations
from dataclasses import dataclass

SDG_LABELS = {
    1: "No Poverty", 2: "Zero Hunger", 3: "Good Health", 4: "Quality Education",
    5: "Gender Equality", 6: "Clean Water", 7: "Affordable Energy", 8: "Decent Work",
    9: "Industry & Innovation", 10: "Reduced Inequalities", 11: "Sustainable Cities",
    12: "Responsible Consumption", 13: "Climate Action", 14: "Life Below Water",
    15: "Life on Land", 16: "Peace & Justice", 17: "Partnerships",
}

# EUR per life-year of impact (rough proxy, varies by SDG)
_LIVES_PER_EUR: dict[int, float] = {
    1: 0.08, 2: 0.12, 3: 0.07, 4: 0.05, 5: 0.06, 6: 0.09,
    7: 0.04, 8: 0.03, 9: 0.02, 10: 0.04, 11: 0.03, 12: 0.02,
    13: 0.03, 14: 0.05, 15: 0.04, 16: 0.04, 17: 0.01,
}


@dataclass
class SDGAllocation:
    sdg: int
    label: str
    weight: float
    percentage: float
    euro_amount: float
    lives_touched: float


@dataclass
class ImpactSnapshot:
    total_committed_eur: float
    total_lives_touched: float
    allocations: list[SDGAllocation]
    horizon_years: int


def build_impact_snapshot(
    total_eur: float,
    sdg_weights: dict[int, float],
    horizon_years: int = 5,
) -> ImpactSnapshot:
    total_w = sum(sdg_weights.values()) or 1.0
    allocations: list[SDGAllocation] = []
    total_lives = 0.0

    for sdg, w in sdg_weights.items():
        pct = w / total_w
        eur = pct * total_eur * horizon_years * 12  # monthly → total over horizon
        lives = eur * _LIVES_PER_EUR.get(sdg, 0.04)
        total_lives += lives
        allocations.append(SDGAllocation(
            sdg=sdg,
            label=SDG_LABELS.get(sdg, f"SDG {sdg}"),
            weight=round(w, 3),
            percentage=round(pct * 100, 1),
            euro_amount=round(eur, 2),
            lives_touched=round(lives, 1),
        ))

    allocations.sort(key=lambda a: -a.euro_amount)
    return ImpactSnapshot(
        total_committed_eur=total_eur,
        total_lives_touched=round(total_lives, 1),
        allocations=allocations,
        horizon_years=horizon_years,
    )


def snapshot_to_dict(s: ImpactSnapshot) -> dict:
    return {
        "total_committed_eur": s.total_committed_eur,
        "total_lives_touched": s.total_lives_touched,
        "horizon_years": s.horizon_years,
        "allocations": [
            {
                "sdg": a.sdg, "label": a.label, "percentage": a.percentage,
                "euro_amount": a.euro_amount, "lives_touched": a.lives_touched,
            }
            for a in s.allocations
        ],
    }
