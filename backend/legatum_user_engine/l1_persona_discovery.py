"""
L1 — Persona Discovery
Onboarding quiz scoring → philanthropic archetype.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

PersonaArchetype = Literal["Visionär", "Bewahrer", "Gestalter", "Brückenbauer", "Pionier"]

ARCHETYPE_SDG_AFFINITY: dict[str, list[int]] = {
    "Visionär":      [13, 17, 9, 11],
    "Bewahrer":      [15, 14, 6, 3],
    "Gestalter":     [4, 8, 10, 16],
    "Brückenbauer":  [1, 2, 5, 10],
    "Pionier":       [7, 9, 12, 13],
}

ARCHETYPE_THRESHOLDS: dict[str, str] = {
    "systemic":   "Visionär",
    "depth":      "Bewahrer",
    "identity":   "Gestalter",
    "engagement": "Brückenbauer",
}


@dataclass
class PersonaResult:
    archetype: PersonaArchetype
    scores: dict[str, float]
    sdg_affinity: list[int]
    confidence: float


def calc_persona(scores: dict[str, float]) -> PersonaResult:
    """Derive PersonaResult from raw quiz dimension scores."""
    if not scores:
        return PersonaResult(
            archetype="Gestalter", scores=scores,
            sdg_affinity=ARCHETYPE_SDG_AFFINITY["Gestalter"], confidence=0.0,
        )

    dominant_dim = max(scores, key=lambda k: scores[k])
    total = sum(scores.values()) or 1
    top_score = scores[dominant_dim]

    archetype: PersonaArchetype = ARCHETYPE_THRESHOLDS.get(dominant_dim, "Pionier")  # type: ignore[assignment]
    confidence = round(top_score / total, 3)

    return PersonaResult(
        archetype=archetype,
        scores=scores,
        sdg_affinity=ARCHETYPE_SDG_AFFINITY[archetype],
        confidence=confidence,
    )


def persona_to_dict(result: PersonaResult) -> dict:
    return {
        "archetype": result.archetype,
        "scores": result.scores,
        "sdg_affinity": result.sdg_affinity,
        "confidence": result.confidence,
    }
