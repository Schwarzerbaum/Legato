"""
Legatum Intelligence — FastAPI Router
Mount at: /api/v1/legatum
"""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from legatum_intelligence.orchestrator import orchestrate
from legatum_intelligence.schemas import (
    GiverIdentityProfile, NGOCredibilityProfile,
    OrchestrateRequest, OrchestrateResponse,
)
from legatum_intelligence.vector_store import vector_store
from legatum_bank_engine.credibility_engine import ingest_ngo, batch_ingest, DEMO_NGOS
from legatum_bank_engine.l6_knowledge_graph import get_graph, get_stats, seed_demo_graph

router = APIRouter(tags=["legatum-intelligence"])


# ══════════════════════════════════════════════════════════════════════════════
# PRIMARY ENDPOINT — Agentic Orchestration
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/orchestrate",
    response_model=OrchestrateResponse,
    summary="Run the full Legatum Intelligence orchestration pipeline",
    description="""
**Multi-agent workflow:**

1. Resolve user's GiverIdentityProfile from Vector DB
2. Merge user SDG affinity with request intent
3. Semantic search NGO profiles (cosine similarity over 384-dim embeddings)
4. Credibility gate (risk ≤ 0.4, credibility ≥ 45, no CRITICAL flags)
5. Mirror qualified NGOs → L6 Knowledge Graph
6. Foundation Intelligence: map to §10b EStG-compliant financial products
7. Trigger engine: idle capital / tax deadline / SDG gap alerts
8. Return structured payload + orchestration trace
    """,
    status_code=status.HTTP_200_OK,
)
async def orchestrate_endpoint(req: OrchestrateRequest) -> OrchestrateResponse:
    try:
        return await orchestrate(req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(exc), "type": type(exc).__name__},
        ) from exc


# ══════════════════════════════════════════════════════════════════════════════
# USER IDENTITY — Vector Upsert & Retrieval
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/identity",
    response_model=GiverIdentityProfile,
    summary="Upsert a GiverIdentityProfile into the Vector DB",
    status_code=status.HTTP_201_CREATED,
)
async def upsert_identity(profile: GiverIdentityProfile) -> GiverIdentityProfile:
    """
    Embeds `giver_narrative` into a 384-dim vector and stores the full
    hybrid profile in Qdrant (or in-memory fallback).
    """
    return vector_store.upsert_giver(profile)


@router.get(
    "/identity/{user_id}",
    response_model=GiverIdentityProfile,
    summary="Retrieve a GiverIdentityProfile by user_id",
)
async def get_identity(user_id: UUID) -> GiverIdentityProfile:
    profile = vector_store.get_giver(user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No identity found for user_id={user_id}",
        )
    return profile


# ══════════════════════════════════════════════════════════════════════════════
# NGO CREDIBILITY — Ingest, Score & Search
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/ngo/ingest",
    response_model=NGOCredibilityProfile,
    summary="Ingest one NGO through the full credibility pipeline",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_ngo_endpoint(
    name: str,
    mission_statement: str,
    sdgs: list[int],
    website: str = "",
    country: str = "DE",
    registration_number: str = "",
) -> NGOCredibilityProfile:
    """
    Runs: DZI scrape → news sentiment → greenwash scan → credibility score → Vector DB upsert.
    """
    profile = await ingest_ngo(
        name=name,
        mission_statement=mission_statement,
        sdgs=sdgs,
        website=website,
        country=country,
        registration_number=registration_number,
    )
    return vector_store.upsert_ngo(profile)


@router.post(
    "/ngo/search",
    summary="Semantic NGO search with hard-metadata filters",
)
async def search_ngos(
    query: str,
    sdgs: list[int] | None = None,
    geography: list[str] | None = None,
    min_credibility: float = 50.0,
    top_k: int = 5,
) -> dict:
    results = vector_store.search_ngos(
        query_text=query,
        sdg_filter=sdgs,
        geography=geography,
        min_credibility=min_credibility,
        top_k=top_k,
    )
    return {
        "count": len(results),
        "ngos": [
            {"similarity": round(score, 4), **ngo.model_dump(exclude={"mission_embedding"})}
            for score, ngo in results
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH — L6 Read Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/kg/graph", summary="Full Knowledge Graph for D3 visualisation")
async def kg_graph() -> dict:
    return get_graph()


@router.get("/kg/stats", summary="Knowledge Graph node/edge statistics")
async def kg_stats_endpoint() -> dict:
    return get_stats()


# ══════════════════════════════════════════════════════════════════════════════
# DEMO / SEED
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/demo/seed",
    summary="Seed Vector DB + KG with demo NGOs and a sample user identity",
)
async def seed_demo(background_tasks: BackgroundTasks) -> dict:
    """
    Async background seeding so the endpoint returns immediately.
    Ingests DEMO_NGOS through the full credibility pipeline.
    """

    async def _seed() -> None:
        profiles = await batch_ingest(DEMO_NGOS)
        for p in profiles:
            vector_store.upsert_ngo(p)

        # Sample user identity
        demo_user = GiverIdentityProfile(
            full_name="Lena Fischer",
            email="lena@example.de",
            archetype="Pionier",  # type: ignore[arg-type]
            preferred_sdgs=[14, 13, 4],
            geography=["DE-BW", "DE"],
            risk_tolerance="high",  # type: ignore[arg-type]
            giver_narrative=(
                "Post-exit founder passionate about ocean plastics and "
                "regional tech education in Baden-Württemberg."
            ),
            financial={  # type: ignore[arg-type]
                "available_capital_eur": 2_500_000,
                "annual_giving_budget_eur": 125_000,
                "idle_dividends_eur": 48_000,
                "tax_optimization_goal": True,
                "paragraph_10b_eligible": True,
            },
        )
        vector_store.upsert_giver(demo_user)
        seed_demo_graph()

    background_tasks.add_task(_seed)
    return {"status": "seeding", "message": "Demo data ingestion started in background"}


@router.post(
    "/demo/orchestrate",
    response_model=OrchestrateResponse,
    summary="Run a live demo orchestration with the seeded demo user",
)
async def demo_orchestrate() -> OrchestrateResponse:
    """
    Convenience endpoint for the hackathon demo —
    runs a full orchestration pass using the seeded Lena Fischer identity.
    """
    # Re-seed synchronously to guarantee data exists
    profiles = await batch_ingest(DEMO_NGOS)
    for p in profiles:
        vector_store.upsert_ngo(p)

    demo_user = GiverIdentityProfile(
        full_name="Lena Fischer",
        email="lena@example.de",
        archetype="Pionier",  # type: ignore[arg-type]
        preferred_sdgs=[14, 13, 4],
        geography=["DE-BW", "DE"],
        risk_tolerance="high",  # type: ignore[arg-type]
        giver_narrative=(
            "Post-exit founder passionate about ocean plastics and "
            "regional tech education in Baden-Württemberg."
        ),
        financial={  # type: ignore[arg-type]
            "available_capital_eur": 2_500_000,
            "annual_giving_budget_eur": 125_000,
            "idle_dividends_eur": 48_000,
            "tax_optimization_goal": True,
            "paragraph_10b_eligible": True,
        },
    )
    saved = vector_store.upsert_giver(demo_user)

    req = OrchestrateRequest(
        user_id=saved.user_id,
        intent="Find ocean conservation and climate NGOs in Baden-Württemberg",
        sdg_filter=[14, 13],
        top_k_ngos=3,
    )
    return await orchestrate(req)
