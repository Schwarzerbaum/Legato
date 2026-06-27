"""
LEGATUM User Engine API — FastAPI router for L1 L4 L5 L7 L8 L9.
Mount at: /api/user-engine
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Literal

router = APIRouter(tags=["user-engine"])


# ── Request models ─────────────────────────────────────────────────────────────

class PersonaRequest(BaseModel):
    scores: dict[str, float] = Field(
        default={"systemic": 3, "depth": 1, "identity": 2, "engagement": 1},
        description="Raw quiz dimension scores",
    )


class AdvisorRequest(BaseModel):
    archetype: str = "Gestalter"
    preferred_sdgs: list[int] = []


class ImpactRequest(BaseModel):
    total_eur: float = Field(100.0, description="Monthly contribution in EUR")
    sdg_weights: dict[int, float] = Field(
        default={13: 0.4, 4: 0.3, 2: 0.3},
        description="SDG number → relative weight",
    )
    horizon_years: int = Field(5, ge=1, le=30)


class FoundationArcRequest(BaseModel):
    project_id: str = "FND-DEMO"
    completed_gate_ids: list[str] = []


class PassportRequest(BaseModel):
    donor_id: str = "donor-demo"
    total_committed_eur: float = 0.0
    completed_gates: int = 0
    ngo_count: int = 0


class StrategyRequest(BaseModel):
    archetype: str = "Gestalter"
    total_wealth_eur: float = 1_000_000.0
    sdg_affinity: list[int] = [4, 13, 1]
    risk_tolerance: Literal["low", "medium", "high"] = "medium"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/l1/persona")
async def derive_persona(req: PersonaRequest):
    """L1 — Derive philanthropic archetype from quiz scores."""
    from legatum_user_engine import calc_persona, persona_to_dict
    result = calc_persona(req.scores)
    return persona_to_dict(result)


@router.post("/l4/advisor")
async def match_advisor(req: AdvisorRequest):
    """L4 — Match donor persona to best-fit LBBW advisor."""
    from legatum_user_engine import match_advisor as _match, advisor_to_dict
    match = _match(req.archetype, req.preferred_sdgs)
    return advisor_to_dict(match)


@router.post("/l5/impact")
async def calc_impact(req: ImpactRequest):
    """L5 — Build SDG allocation snapshot + lives-touched estimate."""
    from legatum_user_engine import build_impact_snapshot, snapshot_to_dict
    snap = build_impact_snapshot(req.total_eur, req.sdg_weights, req.horizon_years)
    return snapshot_to_dict(snap)


@router.post("/l7/foundation-arc")
async def foundation_arc(req: FoundationArcRequest):
    """L7 — Evaluate German Stiftung structuring gates."""
    from legatum_user_engine import build_foundation_arc, arc_to_dict
    arc = build_foundation_arc(req.project_id, req.completed_gate_ids)
    return arc_to_dict(arc)


@router.post("/l8/passport")
async def build_passport(req: PassportRequest):
    """L8 — Generate LegatumPassport with badges + credibility score."""
    from legatum_user_engine import build_passport as _passport, passport_to_dict
    passport = _passport(
        req.donor_id, req.total_committed_eur,
        req.completed_gates, req.ngo_count,
    )
    return passport_to_dict(passport)


@router.post("/l9/strategy")
async def giving_strategy(req: StrategyRequest):
    """L9 — Generate AI-driven philanthropic giving strategy."""
    from legatum_user_engine import generate_strategy, strategy_to_dict
    strategy = generate_strategy(
        req.archetype, req.total_wealth_eur,
        req.sdg_affinity, req.risk_tolerance,
    )
    return strategy_to_dict(strategy)
