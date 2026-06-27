"""
L2 — NGO Intelligence
Vetted NGO registry with impact scoring and risk flags.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

VerificationStatus = Literal["pending", "verified", "flagged"]

# Seed registry (in production: replaces with live Bundesanzeiger / DZI scrape)
_NGO_REGISTRY: list[dict] = [
    {
        "ngo_id": "NGO-001", "name": "BUND e.V.", "country": "DE",
        "sdgs": [13, 15, 6], "impact_score": 0.88,
        "verification_status": "verified", "annual_report_url": "",
        "transparency_grade": "A",
    },
    {
        "ngo_id": "NGO-002", "name": "Welthungerhilfe", "country": "DE",
        "sdgs": [1, 2, 6], "impact_score": 0.91,
        "verification_status": "verified", "annual_report_url": "",
        "transparency_grade": "A+",
    },
    {
        "ngo_id": "NGO-003", "name": "Habitat for Humanity DE", "country": "DE",
        "sdgs": [1, 11], "impact_score": 0.79,
        "verification_status": "verified", "annual_report_url": "",
        "transparency_grade": "B+",
    },
    {
        "ngo_id": "NGO-004", "name": "SOS Kinderdörfer", "country": "DE",
        "sdgs": [1, 3, 4], "impact_score": 0.85,
        "verification_status": "verified", "annual_report_url": "",
        "transparency_grade": "A",
    },
    {
        "ngo_id": "NGO-005", "name": "GreenpeaceDE", "country": "DE",
        "sdgs": [13, 14, 15], "impact_score": 0.76,
        "verification_status": "verified", "annual_report_url": "",
        "transparency_grade": "B",
    },
]


@dataclass
class NGORecord:
    ngo_id: str
    name: str
    country: str
    sdgs: list[int]
    impact_score: float
    verification_status: VerificationStatus
    transparency_grade: str


@dataclass
class NGOIntelligenceResult:
    ngo: NGORecord
    credibility_rank: float
    risk_flags: list[str]
    recommended: bool


def score_ngo(ngo: NGORecord) -> NGOIntelligenceResult:
    flags: list[str] = []
    if ngo.verification_status == "flagged":
        flags.append("DZI verification flagged")
    if ngo.verification_status == "pending":
        flags.append("Pending verification — do not disburse")
    if ngo.impact_score < 0.5:
        flags.append("Low impact score (<50%)")
    if ngo.transparency_grade in ("C", "D", "F"):
        flags.append(f"Low transparency grade: {ngo.transparency_grade}")

    return NGOIntelligenceResult(
        ngo=ngo,
        credibility_rank=round(ngo.impact_score, 3),
        risk_flags=flags,
        recommended=len(flags) == 0 and ngo.impact_score >= 0.7,
    )


def search_ngos(sdgs: list[int] | None = None, min_score: float = 0.0) -> list[NGOIntelligenceResult]:
    results = []
    for raw in _NGO_REGISTRY:
        if sdgs and not any(s in raw["sdgs"] for s in sdgs):
            continue
        ngo = NGORecord(
            ngo_id=raw["ngo_id"], name=raw["name"], country=raw["country"],
            sdgs=raw["sdgs"], impact_score=raw["impact_score"],
            verification_status=raw["verification_status"],
            transparency_grade=raw["transparency_grade"],
        )
        if ngo.impact_score < min_score:
            continue
        results.append(score_ngo(ngo))
    results.sort(key=lambda r: -r.credibility_rank)
    return results


def ngo_result_to_dict(r: NGOIntelligenceResult) -> dict:
    return {
        "ngo_id": r.ngo.ngo_id,
        "name": r.ngo.name,
        "country": r.ngo.country,
        "sdgs": r.ngo.sdgs,
        "impact_score": r.ngo.impact_score,
        "verification_status": r.ngo.verification_status,
        "transparency_grade": r.ngo.transparency_grade,
        "credibility_rank": r.credibility_rank,
        "risk_flags": r.risk_flags,
        "recommended": r.recommended,
    }
