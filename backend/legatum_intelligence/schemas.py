"""
Legatum Intelligence — Canonical Pydantic schemas.

All vector shapes are declared explicitly so Qdrant / pgvector
collection definitions can be derived directly from these models.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ───────────────────────────────────────────────────────────────

class RiskTolerance(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"

class PersonaArchetype(str, Enum):
    VISIONAER      = "Visionär"
    BEWAHRER       = "Bewahrer"
    GESTALTER      = "Gestalter"
    BRUECKENBAUER  = "Brückenbauer"
    PIONIER        = "Pionier"

class GreenwashSeverity(str, Enum):
    CLEAN    = "clean"
    ADVISORY = "advisory"
    WARNING  = "warning"
    CRITICAL = "critical"

class ProductType(str, Enum):
    GREEN_BOND          = "green_bond"
    DAF                 = "donor_advised_fund"
    STIFTUNG            = "stiftung"
    IMPACT_FUND         = "impact_fund"
    MICROFINANCE        = "microfinance_participation"
    SDG_ETF             = "sdg_etf"


# ── Vector Metadata ────────────────────────────────────────────────────────────

class VectorMeta(BaseModel):
    """Tracks embedding provenance — required for re-indexing & drift detection."""
    model:      str   = "sentence-transformers/all-MiniLM-L6-v2"
    dimensions: int   = 384
    indexed_at: datetime = Field(default_factory=datetime.utcnow)
    version:    str   = "1.0"


# ══════════════════════════════════════════════════════════════════════════════
# USER IDENTITY  —  Hybrid Vector / Hard-Metadata Model
# Stored as a Qdrant Point:
#   point.id      = user_id (UUID)
#   point.vector  = giver_embedding  (384-dim)
#   point.payload = GiverIdentityPayload (all fields below)
# ══════════════════════════════════════════════════════════════════════════════

class FinancialProfile(BaseModel):
    available_capital_eur:    float = Field(..., gt=0, description="Total allocatable wealth (EUR)")
    annual_giving_budget_eur: float = Field(..., gt=0, description="Yearly philanthropic budget (EUR)")
    idle_dividends_eur:       float = Field(0.0,  description="Undeployed dividend income this quarter")
    tax_domicile:             str   = "DE"
    tax_optimization_goal:    bool  = True
    paragraph_10b_eligible:   bool  = True   # § 10b EStG charitable deduction


class GiverIdentityProfile(BaseModel):
    """
    Hybrid Entity Vector storage model.

    Hard metadata fields are filterable payload fields in Qdrant.
    `giver_embedding` is stored as the point vector (384-dim float32).

    Qdrant collection spec:
        vectors_config = VectorParams(size=384, distance=Distance.COSINE)
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    user_id:   UUID            = Field(default_factory=uuid4)
    full_name: str
    email:     str
    archetype: PersonaArchetype
    created_at: datetime       = Field(default_factory=datetime.utcnow)

    # ── Hard metadata (Qdrant payload — filterable) ───────────────────────────
    preferred_sdgs:    list[int]  = Field(..., description="UN SDG numbers 1-17")
    geography:         list[str]  = Field(..., description="ISO-3166-1 alpha-2 or region names")
    risk_tolerance:    RiskTolerance
    financial:         FinancialProfile

    # ── Soft semantic (the Giver Narrative) ──────────────────────────────────
    giver_narrative: str = Field(
        ...,
        description=(
            "Free-text first-person identity statement. "
            "Example: 'Founder passionate about ocean plastics and regional "
            "tech education in Baden-Württemberg.' "
            "This string is embedded into giver_embedding."
        ),
        min_length=20,
        max_length=1000,
    )

    # ── Vector (populated by embedding service, NOT from client) ─────────────
    giver_embedding: list[float] = Field(
        default=[],
        description="384-dim cosine-normalised sentence embedding of giver_narrative",
    )
    vector_meta: VectorMeta = Field(default_factory=VectorMeta)

    @field_validator("preferred_sdgs")
    @classmethod
    def sdgs_in_range(cls, v: list[int]) -> list[int]:
        for sdg in v:
            if not 1 <= sdg <= 17:
                raise ValueError(f"SDG {sdg} out of range 1-17")
        return sorted(set(v))

    @field_validator("giver_embedding")
    @classmethod
    def correct_dimensions(cls, v: list[float]) -> list[float]:
        if v and len(v) != 384:
            raise ValueError(f"Embedding must be 384-dim, got {len(v)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Lena Fischer",
                "email": "lena@example.de",
                "archetype": "Pionier",
                "preferred_sdgs": [13, 14, 4],
                "geography": ["DE-BW", "DE"],
                "risk_tolerance": "high",
                "giver_narrative": (
                    "Post-exit founder passionate about ocean plastics and "
                    "regional tech education in Baden-Württemberg."
                ),
                "financial": {
                    "available_capital_eur": 2_500_000,
                    "annual_giving_budget_eur": 125_000,
                    "idle_dividends_eur": 48_000,
                    "tax_optimization_goal": True,
                    "paragraph_10b_eligible": True,
                },
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# NGO CREDIBILITY PROFILE  —  Vector-Graph Storage Model
# Stored as a Qdrant Point:
#   point.id      = ngo_id (UUID)
#   point.vector  = mission_embedding  (384-dim)
#   point.payload = NGOCredibilityProfile (all fields below)
# KG edges stored separately in legatum_bank_engine.l6_knowledge_graph
# ══════════════════════════════════════════════════════════════════════════════

class GreenwashFlag(BaseModel):
    flag_id:    str
    severity:   GreenwashSeverity
    source:     str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    description: str


class SentimentWindow(BaseModel):
    """Rolling 30-day sentiment from news/web feeds."""
    score:      float   = Field(..., ge=-1.0, le=1.0, description="-1 negative → +1 positive")
    article_count: int  = 0
    top_sources: list[str] = []
    updated_at:  datetime  = Field(default_factory=datetime.utcnow)


class ComplianceRecord(BaseModel):
    dzi_seal:                 bool  = False
    dzi_seal_year:            int | None = None
    stifterverband_certified: bool  = False
    transparency_grade:       str   = "N/A"   # A+, A, B+, B, C, D, F
    annual_report_verified:   bool  = False
    annual_report_url:        str   = ""
    registration_number:      str   = ""      # Vereinsregisternummer
    tax_exempt_status:        bool  = False
    last_audit_date:          datetime | None = None


class NGOCredibilityProfile(BaseModel):
    """
    Vector-Graph NGO profile.

    Stored in Qdrant with mission_embedding as point vector.
    Entity relationships (funders, beneficiaries, SDG links) are
    mirrored as edges in l6_knowledge_graph (SQLite → D3 export).

    Qdrant collection spec:
        vectors_config = VectorParams(size=384, distance=Distance.COSINE)
        payload_schema = {
            "sdgs": PayloadSchemaType.INTEGER,
            "country": PayloadSchemaType.KEYWORD,
            "risk_score": PayloadSchemaType.FLOAT,
            "dzi_seal": PayloadSchemaType.BOOL,
        }
    """
    ngo_id:   UUID = Field(default_factory=uuid4)
    name:     str
    country:  str = "DE"
    sdgs:     list[int]
    website:  str = ""

    # ── Compliance ────────────────────────────────────────────────────────────
    compliance:  ComplianceRecord = Field(default_factory=ComplianceRecord)

    # ── Risk metrics ──────────────────────────────────────────────────────────
    risk_score:       float = Field(0.0, ge=0.0, le=1.0, description="0 = no risk, 1 = critical")
    greenwash_flags:  list[GreenwashFlag] = []
    sentiment:        SentimentWindow    = Field(default_factory=SentimentWindow)

    # ── Soft semantic (mission statement) ────────────────────────────────────
    mission_statement: str = Field(
        ...,
        description="Canonical mission text — embedded into mission_embedding.",
    )

    # ── Vector (384-dim cosine) ───────────────────────────────────────────────
    mission_embedding: list[float] = Field(
        default=[],
        description="384-dim cosine-normalised embedding of mission_statement",
    )
    vector_meta: VectorMeta = Field(default_factory=VectorMeta)

    # ── KG anchor ────────────────────────────────────────────────────────────
    kg_node_id: str = ""   # references l6_knowledge_graph node id

    # ── Derived score ─────────────────────────────────────────────────────────
    credibility_score: float = Field(
        0.0, ge=0.0, le=100.0,
        description="Weighted composite: compliance 40% + sentiment 30% + risk 30%",
    )

    def compute_credibility(self) -> float:
        compliance_pts  = (
            (20 if self.compliance.dzi_seal else 0) +
            (10 if self.compliance.stifterverband_certified else 0) +
            (10 if self.compliance.annual_report_verified else 0)
        )
        grade_map = {"A+": 10, "A": 8, "B+": 6, "B": 4, "C": 2, "D": 1, "F": 0, "N/A": 0}
        compliance_pts += grade_map.get(self.compliance.transparency_grade, 0)

        sentiment_pts   = max(0.0, (self.sentiment.score + 1) / 2 * 30)
        risk_pts        = (1 - self.risk_score) * 30

        self.credibility_score = round(
            min(compliance_pts, 40) + sentiment_pts + risk_pts, 1
        )
        return self.credibility_score


# ══════════════════════════════════════════════════════════════════════════════
# FOUNDATION INTELLIGENCE  —  Financial Product Recommendation
# ══════════════════════════════════════════════════════════════════════════════

class CapitalAllocation(BaseModel):
    product_type:     ProductType
    product_name:     str
    issuer:           str
    allocation_eur:   float
    expected_return:  float | None = None
    sdg_alignment:    list[int]
    tax_benefit:      str          = ""   # e.g. "§10b EStG — up to 20% of Gesamtbetrag der Einkünfte"
    lbbw_product_id:  str          = ""
    rationale:        str          = ""


class BankInteractionTrigger(BaseModel):
    """Proactive push notification to the LBBW advisor or donor portal."""
    trigger_id:    str = Field(default_factory=lambda: str(uuid4()))
    trigger_type:  Literal["idle_capital", "tax_deadline", "sdg_match", "rebalance"]
    headline:      str
    body:          str
    urgency:       Literal["low", "medium", "high"]
    amount_eur:    float | None = None
    action_url:    str          = ""


class FoundationIntelligenceResult(BaseModel):
    recommended_allocations:  list[CapitalAllocation]
    interaction_triggers:     list[BankInteractionTrigger]
    total_tax_saving_eur:     float
    effective_giving_pct:     float   # % of capital deployed after tax benefit
    compliance_note:          str     = "Reviewed against §10b EStG and §55-68 AO"


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR  —  Request / Response Contracts
# ══════════════════════════════════════════════════════════════════════════════

class OrchestrateRequest(BaseModel):
    user_id:         UUID
    intent:          str  = Field(
        ...,
        description="Natural language intent from the frontend.",
        examples=["Find ocean conservation NGOs in Baden-Württemberg under €50k"],
    )
    sdg_filter:      list[int]  = []
    geography_filter: list[str] = []
    max_allocation_eur: float | None = None
    top_k_ngos:      int = Field(5, ge=1, le=20)


class OrchestrateResponse(BaseModel):
    request_id:     UUID = Field(default_factory=uuid4)
    user_id:        UUID
    matched_ngos:   list[NGOCredibilityProfile]
    financial_plan: FoundationIntelligenceResult
    triggers:       list[BankInteractionTrigger]
    latency_ms:     float
    orchestration_trace: list[str] = []   # step-by-step log for the frontend
