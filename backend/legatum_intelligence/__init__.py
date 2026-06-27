"""
Legatum Intelligence — Agentic Orchestration Brain

Coordinates:
  - GiverIdentityProfile resolution (Vector DB)
  - NGO semantic search + credibility gate
  - Foundation Intelligence (§10b EStG product mapping)
  - Knowledge Graph sync (L6)
  - Bank-User interaction triggers
"""
from .orchestrator import orchestrate
from .schemas      import (
    GiverIdentityProfile, NGOCredibilityProfile,
    OrchestrateRequest, OrchestrateResponse,
    FoundationIntelligenceResult, BankInteractionTrigger,
)
from .vector_store import vector_store
from .router       import router

__all__ = [
    "orchestrate", "vector_store", "router",
    "GiverIdentityProfile", "NGOCredibilityProfile",
    "OrchestrateRequest", "OrchestrateResponse",
    "FoundationIntelligenceResult", "BankInteractionTrigger",
]
