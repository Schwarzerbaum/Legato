"""
Legatum Intelligence — Master Orchestrator

Sequence (annotated in orchestration_trace for frontend):
  [1] Resolve user identity from Vector DB (cosine lookup by user_id)
  [2] Enrich intent with persona context (SDGs, narrative, geography)
  [3] Semantic search NGO profiles in Vector DB
  [4] Parallel credibility gate: filter by risk_score + greenwash flags
  [5] Mirror qualified NGOs into Knowledge Graph (L6)
  [6] Foundation Intelligence: map NGOs → financial products
  [7] Trigger engine: idle capital / tax-deadline / rebalance alerts
  [8] Package + return OrchestrateResponse
"""
from __future__ import annotations

import asyncio
import time
from uuid import UUID, uuid4

from legatum_intelligence.schemas import (
    BankInteractionTrigger, FoundationIntelligenceResult,
    GiverIdentityProfile, NGOCredibilityProfile,
    OrchestrateRequest, OrchestrateResponse,
)
from legatum_intelligence.vector_store import vector_store
from legatum_bank_engine.foundation_intelligence import recommend
from legatum_bank_engine.l6_knowledge_graph import add_node, add_edge, KGNode, KGEdge


# ── Credibility gate ──────────────────────────────────────────────────────────

_MAX_RISK_SCORE   = 0.4    # NGOs above this are excluded
_MIN_CREDIBILITY  = 45.0   # Minimum composite credibility score


def _credibility_gate(ngos: list[tuple[float, NGOCredibilityProfile]]) -> list[NGOCredibilityProfile]:
    return [
        profile for _, profile in ngos
        if profile.risk_score <= _MAX_RISK_SCORE
        and profile.credibility_score >= _MIN_CREDIBILITY
        and not any(
            f.severity.value == "critical" for f in profile.greenwash_flags
        )
    ]


# ── Knowledge Graph sync ──────────────────────────────────────────────────────

def _sync_to_kg(user_id: UUID, ngos: list[NGOCredibilityProfile]) -> None:
    """Mirror user → NGO → SDG edges into the persistent KG (L6)."""
    donor_node_id = f"donor-{str(user_id)[:8]}"
    add_node(KGNode(id=donor_node_id, node_type="donor", label=str(user_id)))

    for ngo in ngos:
        ngo_node_id = f"ngo-{str(ngo.ngo_id)[:8]}"
        add_node(KGNode(id=ngo_node_id, node_type="ngo", label=ngo.name))
        add_edge(KGEdge(
            from_id=donor_node_id, to_id=ngo_node_id,
            relation="funds", weight=round(ngo.credibility_score / 100, 2),
        ))
        for sdg in ngo.sdgs[:3]:
            sdg_node_id = f"sdg-{sdg}"
            add_node(KGNode(id=sdg_node_id, node_type="sdg", label=f"SDG {sdg}"))
            add_edge(KGEdge(
                from_id=ngo_node_id, to_id=sdg_node_id,
                relation="targets_sdg", weight=1.0,
            ))


# ── Main orchestration pipeline ───────────────────────────────────────────────

async def orchestrate(req: OrchestrateRequest) -> OrchestrateResponse:
    t0    = time.monotonic()
    trace: list[str] = []

    # ── Step 1: Resolve user identity ─────────────────────────────────────────
    trace.append("[1/8] Resolving user identity from Vector DB …")
    identity = vector_store.get_giver(req.user_id)

    if identity is None:
        # Graceful degradation: proceed with request params only
        trace.append("      ⚠ Identity not found — proceeding with request params only")
        sdgs       = req.sdg_filter or [13, 4]
        geography  = req.geography_filter or ["DE"]
        narrative  = req.intent
        financial  = None
        archetype  = None
    else:
        trace.append(f"      ✓ Identity resolved: {identity.archetype.value} | {identity.giver_narrative[:60]}…")
        sdgs      = req.sdg_filter or identity.preferred_sdgs
        geography = req.geography_filter or identity.geography
        narrative = f"{req.intent}. Persona: {identity.giver_narrative}"
        financial = identity.financial
        archetype = identity.archetype

    # ── Step 2: Semantic NGO search in Vector DB ──────────────────────────────
    trace.append(f"[2/8] Semantic NGO search | SDGs={sdgs} | query='{req.intent[:50]}…'")
    ngo_hits = vector_store.search_ngos(
        query_text=narrative,
        sdg_filter=sdgs,
        geography=geography,
        min_credibility=_MIN_CREDIBILITY,
        top_k=req.top_k_ngos * 2,  # fetch extra; gate will trim
    )
    trace.append(f"      ✓ {len(ngo_hits)} NGO candidates retrieved")

    # ── Step 3: Credibility gate ──────────────────────────────────────────────
    trace.append("[3/8] Running credibility gate (risk + greenwash filter) …")
    qualified = _credibility_gate(ngo_hits)[: req.top_k_ngos]
    trace.append(
        f"      ✓ {len(qualified)}/{len(ngo_hits)} NGOs passed "
        f"(risk ≤ {_MAX_RISK_SCORE}, credibility ≥ {_MIN_CREDIBILITY})"
    )

    # ── Step 4: Mirror to Knowledge Graph ────────────────────────────────────
    trace.append("[4/8] Syncing qualified NGOs to Knowledge Graph (L6) …")
    _sync_to_kg(req.user_id, qualified)
    trace.append(f"      ✓ {len(qualified)} nodes + edges written to KG")

    # ── Step 5: Foundation Intelligence ──────────────────────────────────────
    trace.append("[5/8] Foundation Intelligence: mapping NGOs → financial products …")
    if financial:
        fin_result = recommend(
            financial=financial,
            matched_ngos=qualified,
            archetype=archetype,
            budget_override_eur=req.max_allocation_eur,
        )
    else:
        # Minimal result without full financial profile
        from legatum_intelligence.schemas import FoundationIntelligenceResult
        fin_result = FoundationIntelligenceResult(
            recommended_allocations=[],
            interaction_triggers=[],
            total_tax_saving_eur=0.0,
            effective_giving_pct=0.0,
            compliance_note="Full financial plan requires completed onboarding.",
        )
    trace.append(
        f"      ✓ {len(fin_result.recommended_allocations)} products allocated | "
        f"tax saving: €{fin_result.total_tax_saving_eur:,.0f}"
    )

    # ── Step 6: Collect triggers ──────────────────────────────────────────────
    trace.append("[6/8] Collecting bank-user interaction triggers …")
    triggers = fin_result.interaction_triggers
    trace.append(f"      ✓ {len(triggers)} trigger(s) generated")

    # ── Step 7: Package response ──────────────────────────────────────────────
    trace.append("[7/8] Packaging final response payload …")
    latency = round((time.monotonic() - t0) * 1000, 1)
    trace.append(f"[8/8] Done in {latency} ms")

    return OrchestrateResponse(
        request_id=uuid4(),
        user_id=req.user_id,
        matched_ngos=qualified,
        financial_plan=fin_result,
        triggers=triggers,
        latency_ms=latency,
        orchestration_trace=trace,
    )
