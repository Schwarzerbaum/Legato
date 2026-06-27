"""
M&A Signal Pheromone System — organic entity signalling.

Instead of rigid beam search traversal, nodes EMIT signals.
When a Risk node pulses strongly, it automatically PULLS related
FinancialMetric and Contract nodes even if there's no explicit typed edge.

Biological analogy: neurotransmitter diffusion across synapses.
The signal spreads through semantic proximity, not graph edges.

Architecture:
  SignalNode     — an entity with current signal strength + decay
  SignalEmitter  — deposits signals from risk/finding/gap nodes
  SignalPropagator — follows signals across the semantic space
  SignalField    — the full current state of all active signals
"""

import json
import math
import time
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from ma.knowledge import get_db
from ma.embeddings import get_embedding, cosine_similarity


# ── Signal types (mirrors pheromone types in neural layer) ────────────────

SignalType = Literal[
    "RISK_PULSE",        # Risk node detected — pulls Financial nodes
    "ANOMALY_SCENT",     # Anomaly flagged — pulls related Claims
    "CHAIN_TRIGGER",     # Implied chain link detected
    "DRIFT_MARKER",      # Narrative drift on this entity
    "ABSENCE_FLAG",      # Missing topic signal
    "OPPORTUNITY_BLOOM", # Positive discovery
    "AUDIT_BEACON",      # Jury flagged for human review
]

SIGNAL_DECAY_RATE = 0.85    # Signal strength * decay each propagation hop
MIN_SIGNAL_STRENGTH = 0.05  # Below this, signal is too weak to propagate
SEMANTIC_PULL_THRESHOLD = 0.55  # Cosine similarity needed to pull a node


# ── Data types ────────────────────────────────────────────────────────────

@dataclass
class Signal:
    signal_id: str
    signal_type: SignalType
    source_entity: str
    source_chunk_id: int
    source_doc_id: int
    strength: float            # 0-1
    payload: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hops: int = 0
    propagated_to: list[str] = field(default_factory=list)


@dataclass
class PulledNode:
    entity_name: str
    entity_type: str
    chunk_id: int
    doc_id: int
    filename: str
    pull_strength: float       # how strongly this node was pulled
    semantic_similarity: float
    signal_type: SignalType
    source_entity: str
    excerpt: str


# ── In-memory signal field (SQLite-persisted) ─────────────────────────────

def _init_signal_tables():
    """Create signal persistence tables if not exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ma_signals (
            id TEXT PRIMARY KEY,
            signal_type TEXT NOT NULL,
            source_entity TEXT NOT NULL,
            source_chunk_id INTEGER,
            source_doc_id INTEGER,
            strength REAL DEFAULT 1.0,
            payload TEXT DEFAULT '{}',
            created_at TEXT,
            hops INTEGER DEFAULT 0,
            propagated_to TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS ma_signal_pulls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT NOT NULL,
            pulled_entity TEXT NOT NULL,
            pulled_chunk_id INTEGER,
            pulled_doc_id INTEGER,
            pull_strength REAL,
            semantic_similarity REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def emit_signal(signal_type: SignalType, source_entity: str,
                source_chunk_id: int, source_doc_id: int,
                strength: float = 1.0, payload: dict | None = None) -> Signal:
    """
    Emit a signal from a source entity node.
    Persists to SQLite and returns the Signal object.
    """
    _init_signal_tables()
    signal_id = f"{signal_type}_{source_doc_id}_{source_chunk_id}_{int(time.time())}"
    sig = Signal(
        signal_id=signal_id,
        signal_type=signal_type,
        source_entity=source_entity,
        source_chunk_id=source_chunk_id,
        source_doc_id=source_doc_id,
        strength=min(1.0, max(0.0, strength)),
        payload=payload or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO ma_signals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sig.signal_id, sig.signal_type, sig.source_entity,
         sig.source_chunk_id, sig.source_doc_id, sig.strength,
         json.dumps(sig.payload), sig.created_at, sig.hops,
         json.dumps(sig.propagated_to), 1),
    )
    conn.commit()
    conn.close()
    return sig


def propagate_signal(signal: Signal, doc_ids: list[int] | None = None) -> list[PulledNode]:
    """
    Propagate a signal through the semantic space.
    Finds chunks semantically similar to the source, weighted by signal strength.
    Returns list of pulled nodes above threshold.

    This is the "organic pull" — a Risk node pulsing pulls related
    FinancialMetric nodes from other documents without explicit edges.
    """
    _init_signal_tables()

    if signal.strength < MIN_SIGNAL_STRENGTH:
        return []

    # Get source chunk text for embedding
    conn = get_db()
    source_row = conn.execute(
        "SELECT c.text, c.doc_id FROM ma_chunks c WHERE c.id=?",
        (signal.source_chunk_id,),
    ).fetchone()

    if not source_row:
        conn.close()
        return []

    source_text = source_row["text"]

    # Get candidate chunks (from other documents)
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        candidates = conn.execute(
            f"SELECT c.id, c.doc_id, c.text, c.page, d.filename "
            f"FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id "
            f"WHERE c.doc_id IN ({placeholders}) AND c.doc_id != ? "
            f"ORDER BY c.id",
            [*doc_ids, signal.source_doc_id],
        ).fetchall()
    else:
        candidates = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id "
            "WHERE c.doc_id != ? ORDER BY c.id",
            (signal.source_doc_id,),
        ).fetchall()
    conn.close()

    if not candidates:
        return []

    # Try semantic (embedding) pull first, fall back to keyword pull
    source_emb = get_embedding(source_text[:500])
    pulled_nodes = []

    if source_emb:
        # Semantic pull via embeddings
        for cand in candidates:
            cand_emb = get_embedding(cand["text"][:500])
            if not cand_emb:
                continue
            sim = cosine_similarity(source_emb, cand_emb)
            pull_strength = sim * signal.strength
            if sim >= SEMANTIC_PULL_THRESHOLD:
                entity_type = _infer_entity_type(cand["text"])
                pulled_nodes.append(PulledNode(
                    entity_name=_extract_entity_name(cand["text"]),
                    entity_type=entity_type,
                    chunk_id=cand["id"],
                    doc_id=cand["doc_id"],
                    filename=cand["filename"],
                    pull_strength=round(pull_strength, 3),
                    semantic_similarity=round(sim, 3),
                    signal_type=signal.signal_type,
                    source_entity=signal.source_entity,
                    excerpt=cand["text"][:200],
                ))
    else:
        # Keyword-based pull fallback
        source_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', source_text.lower()))
        for cand in candidates:
            cand_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', cand["text"].lower()))
            if not source_words or not cand_words:
                continue
            overlap = len(source_words & cand_words) / max(len(source_words), len(cand_words))
            if overlap >= (SEMANTIC_PULL_THRESHOLD - 0.15):  # lower bar for BM25
                entity_type = _infer_entity_type(cand["text"])
                pulled_nodes.append(PulledNode(
                    entity_name=_extract_entity_name(cand["text"]),
                    entity_type=entity_type,
                    chunk_id=cand["id"],
                    doc_id=cand["doc_id"],
                    filename=cand["filename"],
                    pull_strength=round(overlap * signal.strength, 3),
                    semantic_similarity=round(overlap, 3),
                    signal_type=signal.signal_type,
                    source_entity=signal.source_entity,
                    excerpt=cand["text"][:200],
                ))

    # Sort by pull strength and deduplicate by chunk_id
    seen_chunks = set()
    unique_nodes = []
    for n in sorted(pulled_nodes, key=lambda x: -x.pull_strength):
        if n.chunk_id not in seen_chunks:
            seen_chunks.add(n.chunk_id)
            unique_nodes.append(n)

    # Signal ALWAYS decays after a propagation attempt — whether or not nodes were pulled.
    # (Biological analogy: neurotransmitter diffuses regardless of receptor binding)
    new_strength = signal.strength * SIGNAL_DECAY_RATE
    conn2 = get_db()
    if unique_nodes:
        for n in unique_nodes[:20]:
            conn2.execute(
                "INSERT INTO ma_signal_pulls (signal_id, pulled_entity, pulled_chunk_id, "
                "pulled_doc_id, pull_strength, semantic_similarity) VALUES (?,?,?,?,?,?)",
                (signal.signal_id, n.entity_name, n.chunk_id,
                 n.doc_id, n.pull_strength, n.semantic_similarity),
            )
    conn2.execute(
        "UPDATE ma_signals SET strength=?, hops=?, is_active=? WHERE id=?",
        (new_strength, signal.hops + 1,
         1 if new_strength >= MIN_SIGNAL_STRENGTH else 0,
         signal.signal_id),
    )
    conn2.commit()
    conn2.close()

    return unique_nodes[:15]


def get_active_signals() -> list[dict]:
    """Return all currently active signals."""
    _init_signal_tables()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ma_signals WHERE is_active=1 ORDER BY strength DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_signal_field_summary() -> dict:
    """
    Return a summary of the current signal field state —
    used for the UI signal field visualisation.
    """
    _init_signal_tables()
    conn = get_db()
    signals = conn.execute(
        "SELECT signal_type, source_entity, strength, hops, created_at "
        "FROM ma_signals WHERE is_active=1 ORDER BY strength DESC LIMIT 50"
    ).fetchall()
    pulls = conn.execute(
        "SELECT pulled_entity, pull_strength, pulled_doc_id, created_at "
        "FROM ma_signal_pulls ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()

    return {
        "active_signals": len(signals),
        "signals": [dict(s) for s in signals],
        "recent_pulls": [dict(p) for p in pulls],
        "strongest_signal": dict(signals[0]) if signals else None,
    }


def auto_emit_from_facts(doc_id: int) -> list[Signal]:
    """
    Automatically emit signals from extracted facts for a document.
    Risk facts → RISK_PULSE
    Anomaly facts → ANOMALY_SCENT
    Gap facts → ABSENCE_FLAG
    """
    _init_signal_tables()
    conn = get_db()
    facts = conn.execute(
        "SELECT f.*, c.id as chunk_id FROM ma_facts f "
        "LEFT JOIN ma_chunks c ON c.id = f.chunk_id "
        "WHERE f.doc_id=?",
        (doc_id,),
    ).fetchall()
    conn.close()

    emitted = []
    for f in facts:
        fact_type = (f["fact_type"] or "").lower()
        signal_type: SignalType = "ANOMALY_SCENT"  # default

        if "risk" in fact_type or "regulatory" in fact_type or "litigation" in fact_type:
            signal_type = "RISK_PULSE"
            strength = 0.9
        elif "gap" in fact_type or "missing" in fact_type or "absent" in fact_type:
            signal_type = "ABSENCE_FLAG"
            strength = 0.75
        elif "anomaly" in fact_type or "fraud" in fact_type or "inconsisten" in fact_type:
            signal_type = "ANOMALY_SCENT"
            strength = 0.85
        elif "financial" in fact_type or "revenue" in fact_type or "metric" in fact_type:
            signal_type = "CHAIN_TRIGGER"
            strength = 0.65
        else:
            continue  # don't emit for neutral facts

        sig = emit_signal(
            signal_type=signal_type,
            source_entity=f.get("subject", f"doc_{doc_id}") or f"doc_{doc_id}",
            source_chunk_id=f.get("chunk_id") or 0,
            source_doc_id=doc_id,
            strength=strength,
            payload={"fact_type": f["fact_type"], "value": f["value"]},
        )
        emitted.append(sig)

    return emitted


# ── Helper functions ──────────────────────────────────────────────────────

import re

_RISK_WORDS = {"risk", "regulatory", "litigation", "dispute", "contingent", "warranty"}
_FINANCIAL_WORDS = {"revenue", "ebitda", "profit", "loss", "cash", "debt", "income"}
_PERSON_PATTERN = re.compile(r'\b([A-Z][a-z]+ [A-Z][a-z]+|Dr\. [A-Z][a-z]+)\b')


def _infer_entity_type(text: str) -> str:
    words = set(text.lower().split())
    if words & _RISK_WORDS:
        return "Risk"
    if words & _FINANCIAL_WORDS:
        return "FinancialMetric"
    if _PERSON_PATTERN.search(text):
        return "Person"
    return "Claim"


def _extract_entity_name(text: str, max_len: int = 50) -> str:
    m = _PERSON_PATTERN.search(text)
    if m:
        return m.group(1)
    words = text.split()
    return " ".join(words[:6]) if words else text[:max_len]
