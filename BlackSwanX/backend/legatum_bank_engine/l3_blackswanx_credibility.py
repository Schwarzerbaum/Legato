"""
L3 — BlackSwanX Credibility AI
Risk-adjusted philanthropic credibility scoring for donor × NGO pairs.
Applies the BlackSwanX signal-decay model to philanthropy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

CredibilityGrade = Literal["A", "B", "C", "D", "F"]
BlackSwanRisk    = Literal["low", "medium", "high", "critical"]

# Signal weights (must sum to 1.0)
_WEIGHTS = {
    "sdg_alignment":         0.30,
    "historical_compliance": 0.30,
    "ngo_transparency":      0.20,
    "commitment_size":       0.10,
    "diversification":       0.10,
}

_GRADE_THRESHOLDS = [
    (85, "A"), (70, "B"), (55, "C"), (40, "D"),
]

_RISK_THRESHOLDS = [
    (70, "low"), (45, "medium"), (25, "high"),
]


@dataclass
class CredibilityInput:
    donor_id: str
    ngo_id: str
    commitment_eur: float
    sdg_alignment: float        # 0–1: overlap between donor SDG prefs and NGO SDGs
    historical_compliance: float  # 0–1: past disbursement compliance rate
    ngo_transparency: float     # 0–1: from DZI / annual report grade
    ngo_count: int = 1          # number of NGOs in portfolio (diversification)


@dataclass
class CredibilityScore:
    donor_id: str
    ngo_id: str
    score: float                # 0–100
    grade: CredibilityGrade
    black_swan_risk: BlackSwanRisk
    breakdown: dict[str, float]
    flags: list[str]
    recommendation: str


def calc_credibility(inp: CredibilityInput) -> CredibilityScore:
    # Normalise commitment (caps at €1M)
    commitment_norm = min(inp.commitment_eur / 1_000_000, 1.0)
    # Diversification bonus (max 5 NGOs)
    diversification_norm = min((inp.ngo_count - 1) / 4, 1.0)

    raw_scores = {
        "sdg_alignment":         inp.sdg_alignment         * 100,
        "historical_compliance": inp.historical_compliance * 100,
        "ngo_transparency":      inp.ngo_transparency      * 100,
        "commitment_size":       commitment_norm           * 100,
        "diversification":       diversification_norm      * 100,
    }

    weighted = sum(_WEIGHTS[k] * v for k, v in raw_scores.items())
    score = round(weighted, 1)

    grade: CredibilityGrade = "F"
    for threshold, g in _GRADE_THRESHOLDS:
        if score >= threshold:
            grade = g  # type: ignore[assignment]
            break

    risk: BlackSwanRisk = "critical"
    for threshold, r in _RISK_THRESHOLDS:
        if score >= threshold:
            risk = r  # type: ignore[assignment]
            break

    flags: list[str] = []
    if inp.sdg_alignment < 0.3:
        flags.append("Low SDG alignment between donor and NGO")
    if inp.historical_compliance < 0.5:
        flags.append("Poor historical disbursement compliance")
    if inp.ngo_transparency < 0.5:
        flags.append("NGO transparency below acceptable threshold")
    if inp.commitment_eur < 1_000:
        flags.append("Commitment below €1,000 — limited impact signal")

    recommendation = (
        "APPROVE"          if score >= 80 else
        "APPROVE_WITH_KYC" if score >= 65 else
        "ENHANCED_DD"      if score >= 45 else
        "HOLD"             if score >= 30 else
        "REJECT"
    )

    return CredibilityScore(
        donor_id=inp.donor_id,
        ngo_id=inp.ngo_id,
        score=score,
        grade=grade,
        black_swan_risk=risk,
        breakdown={k: round(_WEIGHTS[k] * v, 2) for k, v in raw_scores.items()},
        flags=flags,
        recommendation=recommendation,
    )


def credibility_to_dict(c: CredibilityScore) -> dict:
    return {
        "donor_id": c.donor_id,
        "ngo_id": c.ngo_id,
        "score": c.score,
        "grade": c.grade,
        "black_swan_risk": c.black_swan_risk,
        "breakdown": c.breakdown,
        "flags": c.flags,
        "recommendation": c.recommendation,
    }
