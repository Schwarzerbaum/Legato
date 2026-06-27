"""
LEGATUM Bank Engine API — FastAPI router for L2 L3 L6.
Mount at: /api/bank-engine
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Literal

router = APIRouter(tags=["bank-engine"])


# ── Request models ─────────────────────────────────────────────────────────────

class NGOSearchRequest(BaseModel):
    sdgs: list[int] = []
    min_score: float = Field(0.0, ge=0.0, le=1.0)


class CredibilityRequest(BaseModel):
    donor_id: str = "donor-demo"
    ngo_id: str   = "NGO-001"
    commitment_eur: float = Field(50_000.0, gt=0)
    sdg_alignment: float        = Field(0.8, ge=0.0, le=1.0)
    historical_compliance: float = Field(0.9, ge=0.0, le=1.0)
    ngo_transparency: float     = Field(0.85, ge=0.0, le=1.0)
    ngo_count: int = Field(1, ge=1)


class KGNodeRequest(BaseModel):
    id: str
    node_type: Literal["donor", "ngo", "sdg", "foundation", "advisor"]
    label: str
    metadata: dict = {}


class KGEdgeRequest(BaseModel):
    from_id: str
    to_id: str
    relation: Literal["funds", "aligns_with", "founded_by", "targets_sdg", "advised_by", "co_funds"]
    weight: float = Field(1.0, ge=0.0, le=1.0)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/l2/ngo/search")
async def search_ngos(req: NGOSearchRequest):
    """L2 — Search vetted NGO registry by SDG focus and minimum impact score."""
    from legatum_bank_engine import search_ngos as _search, ngo_result_to_dict
    results = _search(req.sdgs or None, req.min_score)
    return {
        "count": len(results),
        "ngos": [ngo_result_to_dict(r) for r in results],
    }


@router.get("/l2/ngo/{ngo_id}")
async def get_ngo(ngo_id: str):
    """L2 — Get a single NGO record by ID."""
    from legatum_bank_engine import search_ngos as _search, ngo_result_to_dict
    all_ngos = _search()
    match = next((r for r in all_ngos if r.ngo.ngo_id == ngo_id), None)
    if match is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"NGO {ngo_id} not found")
    return ngo_result_to_dict(match)


@router.post("/l3/credibility")
async def score_credibility(req: CredibilityRequest):
    """L3 — BlackSwanX risk-adjusted credibility score for a donor × NGO pair."""
    from legatum_bank_engine import calc_credibility, credibility_to_dict, CredibilityInput
    inp = CredibilityInput(
        donor_id=req.donor_id,
        ngo_id=req.ngo_id,
        commitment_eur=req.commitment_eur,
        sdg_alignment=req.sdg_alignment,
        historical_compliance=req.historical_compliance,
        ngo_transparency=req.ngo_transparency,
        ngo_count=req.ngo_count,
    )
    score = calc_credibility(inp)
    return credibility_to_dict(score)


@router.post("/l6/kg/node")
async def add_kg_node(req: KGNodeRequest):
    """L6 — Add or upsert a node to the Knowledge Graph."""
    from legatum_bank_engine import add_node, KGNode
    node = add_node(KGNode(req.id, req.node_type, req.label, req.metadata))  # type: ignore[arg-type]
    return {"status": "upserted", "id": node.id}


@router.post("/l6/kg/edge")
async def add_kg_edge(req: KGEdgeRequest):
    """L6 — Add a directed edge to the Knowledge Graph."""
    from legatum_bank_engine import add_edge, KGEdge
    edge = add_edge(KGEdge(req.from_id, req.to_id, req.relation, req.weight))  # type: ignore[arg-type]
    return {"status": "added", "from": edge.from_id, "to": edge.to_id, "relation": edge.relation}


@router.get("/l6/kg/graph")
async def get_kg_graph():
    """L6 — Return full Knowledge Graph for D3 visualisation."""
    from legatum_bank_engine import get_graph
    return get_graph()


@router.get("/l6/kg/neighbours/{node_id}")
async def get_neighbours(node_id: str):
    """L6 — Return all nodes adjacent to a given node."""
    from legatum_bank_engine import query_neighbours
    return {"node_id": node_id, "neighbours": query_neighbours(node_id)}


@router.get("/l6/kg/stats")
async def kg_stats():
    """L6 — Knowledge Graph statistics."""
    from legatum_bank_engine import get_stats
    return get_stats()


@router.post("/l6/kg/seed")
async def seed_demo():
    """L6 — Seed the Knowledge Graph with demo data."""
    from legatum_bank_engine import seed_demo_graph
    stats = seed_demo_graph()
    return {"status": "seeded", **stats}
