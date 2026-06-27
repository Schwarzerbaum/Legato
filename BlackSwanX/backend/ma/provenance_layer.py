"""
provenance_layer.py — W3C PROV-O compliant provenance tracking for BlackSwanX
Wraps all KG entity/edge writes with semantica.provenance.ProvenanceManager.
Every entity and relationship written to the knowledge graph gets a full audit trail:
  - source document
  - page / section
  - agent that detected it
  - confidence score
  - timestamp
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from semantica.provenance import ProvenanceManager, ProvenanceEntry, SQLiteStorage

# ── storage path ────────────────────────────────────────────────────────────
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "blackswanx_provenance.db",
)

_storage = SQLiteStorage(_DB_PATH)
_manager = ProvenanceManager(storage=_storage)


# ── public helpers ────────────────────────────────────────────────────────────

def track_entity(
    entity_id: str,
    entity_type: str,
    source_document: str,
    agent_id: str = "knowledge_graph",
    confidence: float = 1.0,
    section: str | None = None,
    quote: str | None = None,
    page: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record provenance for a KG entity."""
    entry = ProvenanceEntry(
        entity_id=str(entity_id),
        entity_type=entity_type,
        activity_id=f"extract_{entity_type.lower()}",
        agent_id=agent_id,
        source_document=source_document,
        source_location=section,
        source_quote=(quote[:200] if quote else None),
        confidence=confidence,
        metadata=metadata or {},
    )
    try:
        _manager.track_entity(str(entity_id), entry)
    except Exception:
        pass  # provenance is best-effort — never break the main pipeline


def track_relationship(
    source_id: str,
    target_id: str,
    relationship_type: str,
    agent_id: str = "knowledge_graph",
    confidence: float = 1.0,
    source_document: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record provenance for a KG edge."""
    rel_id = f"{source_id}__{relationship_type}__{target_id}"
    try:
        _manager.track_relationship(
            source_id=str(source_id),
            target_id=str(target_id),
            relationship_type=relationship_type,
            agent_id=agent_id,
            metadata={
                "source_document": source_document,
                "confidence": confidence,
                **(metadata or {}),
            },
        )
    except Exception:
        pass


def track_agent_finding(
    entity_id: str,
    entity_type: str,
    agent_id: str,
    source_document: str,
    confidence: float = 1.0,
    quote: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record provenance when an agent (Leukocyte, War Room, etc.) flags something."""
    track_entity(
        entity_id=entity_id,
        entity_type=entity_type,
        source_document=source_document,
        agent_id=agent_id,
        confidence=confidence,
        quote=quote,
        metadata=metadata,
    )


def get_lineage(entity_id: str) -> dict[str, Any]:
    """Return the full provenance trail for an entity."""
    try:
        return _manager.get_lineage(str(entity_id)) or {}
    except Exception:
        return {}


def get_provenance(entity_id: str) -> dict[str, Any] | None:
    """Return the provenance entry for a single entity."""
    try:
        entry = _manager.get_provenance(str(entity_id))
        if entry is None:
            return None
        return {
            "entity_id": entry.entity_id,
            "entity_type": entry.entity_type,
            "agent_id": entry.agent_id,
            "source_document": entry.source_document,
            "source_location": entry.source_location,
            "source_quote": entry.source_quote,
            "confidence": entry.confidence,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
        }
    except Exception:
        return None


def get_statistics() -> dict[str, Any]:
    """Return aggregate provenance statistics."""
    try:
        return _manager.get_statistics() or {}
    except Exception:
        return {}


def get_all_sources() -> list[dict[str, Any]]:
    """Return all unique source documents tracked."""
    try:
        return _manager.get_all_sources() or []
    except Exception:
        return []
