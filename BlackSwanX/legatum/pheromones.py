"""
Construction Signal Pheromone System
======================================
Ports BlackSwanX's stigmergic pheromone system to the construction domain.

Instead of rigid graph traversal, nodes EMIT typed signals that propagate
through semantic proximity. A NACHTRAG_RISK signal from a delay automatically
PULLS related clauses, subcontractors, and DIN standards — without explicit edges.

Construction signal types:
    NACHTRAG_RISK       — Nachtrag claim risk detected
    BEHINDERUNG         — Behinderungsanzeige trigger
    MANGEL_FLAG         — Defect documented
    TERMIN_DRIFT        — Schedule date shifted from contract
    FEHLENDE_UNTERLAGE  — Missing required document
    VERTRAGSSTRAFE_RISK — Penalty clause may be triggered
    AUDIT_BEACON        — Mandatory human review required

Signal propagation:
    - Source node emits signal with strength 0-1
    - Signal pulls semantically similar nodes (cosine similarity via embeddings or keyword overlap)
    - Decay: strength × 0.85 per hop
    - Threshold: 0.55 cosine similarity to pull a node
    - When 3+ signals hit same node: intensities compound × 1.3 (compound pheromone)
"""

from __future__ import annotations

import re
import json
import math
import hashlib
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# ── Signal types ──────────────────────────────────────────────────────────────

SignalType = Literal[
    "NACHTRAG_RISK",
    "BEHINDERUNG",
    "MANGEL_FLAG",
    "TERMIN_DRIFT",
    "FEHLENDE_UNTERLAGE",
    "VERTRAGSSTRAFE_RISK",
    "AUDIT_BEACON",
]

SIGNAL_DECAY = 0.85
SIGNAL_MIN = 0.05
SEMANTIC_THRESHOLD = 0.15  # min similarity to pull a node — lower for short construction docs
COMPOUND_MULTIPLIER = 1.3  # when 3+ signals hit same node

# ── Signal trigger patterns (deterministic, no LLM) ──────────────────────────

SIGNAL_TRIGGERS = [
    {
        "signal_type": "NACHTRAG_RISK",
        "keywords": ["nachtrag", "mehrvergütung", "zusatzleistung", "change order",
                     "leistungsänderung", "mehrbetrag", "nachtragsangebot"],
        "strength": 0.9,
        "description": "Nachtrag claim risk detected in document",
    },
    {
        "signal_type": "BEHINDERUNG",
        "keywords": ["behinderung", "behinderungsanzeige", "unterbrechung",
                     "verzögerung durch ag", "hindrance", "bauablaufstörung"],
        "strength": 0.85,
        "description": "Behinderungsanzeige trigger — VOB/B §6 rights may apply",
    },
    {
        "signal_type": "MANGEL_FLAG",
        "keywords": ["mangel", "mängel", "defekt", "nachbesserung", "abnahmemangel",
                     "gewährleistungsmangel", "werkmangel", "defect"],
        "strength": 0.8,
        "description": "Defect documented — VOB/B §13 Gewährleistung triggered",
    },
    {
        "signal_type": "TERMIN_DRIFT",
        "keywords": ["terminverschiebung", "verzögerung", "verschoben",
                     "nicht rechtzeitig", "fristüberschreitung", "bauzeitverlängerung"],
        "strength": 0.8,
        "description": "Schedule drift detected — contract deadline at risk",
    },
    {
        "signal_type": "FEHLENDE_UNTERLAGE",
        "keywords": ["fehlt", "nicht vorhanden", "nicht eingereicht", "missing",
                     "ausstehend", "kein aufmaß", "keine abnahme", "nicht unterschrieben"],
        "strength": 0.75,
        "description": "Required document or approval is missing",
    },
    {
        "signal_type": "VERTRAGSSTRAFE_RISK",
        "keywords": ["vertragsstrafe", "pönale", "penalty", "verzugsschaden",
                     "verzugszinsen", "schadensersatz", "schadenersatz"],
        "strength": 0.85,
        "description": "Contractual penalty clause may be triggered",
    },
    {
        "signal_type": "AUDIT_BEACON",
        "keywords": ["rechtsstreit", "klage", "schiedsgericht", "arbitration",
                     "litigation", "anwalt", "baurechtlich", "gerichtsverfahren"],
        "strength": 1.0,
        "description": "Legal dispute — mandatory human review required",
    },
]

# ── Database ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db_path = Path(__file__).parent.parent / "backend" / "blackswanx.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_pheromone_tables() -> None:
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ms_signals (
            signal_id       TEXT PRIMARY KEY,
            signal_type     TEXT NOT NULL,
            source_entity   TEXT NOT NULL,
            source_doc_id   INTEGER,
            strength        REAL DEFAULT 1.0,
            description     TEXT DEFAULT '',
            payload         TEXT DEFAULT '{}',
            hops            INTEGER DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_signal_pulls (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id       TEXT NOT NULL,
            pulled_entity   TEXT NOT NULL,
            pulled_doc_id   INTEGER,
            pull_strength   REAL DEFAULT 0.0,
            similarity      REAL DEFAULT 0.0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_pheromone_nodes (
            entity          TEXT PRIMARY KEY,
            doc_id          INTEGER,
            total_intensity REAL DEFAULT 0.0,
            signal_count    INTEGER DEFAULT 0,
            compound        INTEGER DEFAULT 0,
            dominant_signal TEXT,
            last_signal_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class PheromoneSignal:
    signal_id: str
    signal_type: SignalType
    source_entity: str
    source_doc_id: int
    strength: float
    description: str = ""
    hops: int = 0
    pulled_nodes: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PheromoneField:
    """Current state of all active signals in the system."""
    hot_nodes: list[dict]       # nodes with highest intensity (sorted desc)
    signal_count: int
    compound_nodes: list[dict]  # nodes hit by 3+ signals
    dominant_signals: dict[str, int]  # signal_type → count


# ── Core functions ────────────────────────────────────────────────────────────

def _keyword_similarity(text_a: str, text_b: str) -> float:
    """Fast keyword-based similarity (no embeddings needed for basic pheromone propagation)."""
    words_a = set(re.findall(r'\w{4,}', text_a.lower()))
    words_b = set(re.findall(r'\w{4,}', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def scan_for_signals(doc_id: int, text: str, entity_name: str) -> list[PheromoneSignal]:
    """
    Scan document text and emit signals for detected construction risk patterns.
    Deterministic — no LLM needed.
    """
    init_pheromone_tables()
    text_lower = text.lower()
    signals = []

    for trigger in SIGNAL_TRIGGERS:
        hits = sum(1 for kw in trigger["keywords"] if kw in text_lower)
        if hits == 0:
            continue

        # Strength scales with how many keywords hit
        strength = min(1.0, trigger["strength"] * (1 + (hits - 1) * 0.1))
        signal_id = hashlib.md5(
            f"{trigger['signal_type']}:{doc_id}:{entity_name}:{int(time.time())}".encode()
        ).hexdigest()[:16]

        sig = PheromoneSignal(
            signal_id=signal_id,
            signal_type=trigger["signal_type"],
            source_entity=entity_name,
            source_doc_id=doc_id,
            strength=strength,
            description=trigger["description"],
        )
        signals.append(sig)

        # Persist signal + deposit pheromone on the SOURCE entity itself
        conn = _get_db()
        conn.execute(
            """INSERT OR REPLACE INTO ms_signals
               (signal_id, signal_type, source_entity, source_doc_id, strength, description)
               VALUES (?,?,?,?,?,?)""",
            (signal_id, trigger["signal_type"], entity_name, doc_id, strength, trigger["description"])
        )
        # Source node gets full signal strength deposited on itself
        existing = conn.execute(
            "SELECT * FROM ms_pheromone_nodes WHERE entity=?", (entity_name,)
        ).fetchone()
        if existing:
            new_intensity = existing["total_intensity"] + strength
            new_count = existing["signal_count"] + 1
            compound = int(new_count >= 3)
            if compound:
                new_intensity *= COMPOUND_MULTIPLIER
            conn.execute(
                """UPDATE ms_pheromone_nodes
                   SET total_intensity=?, signal_count=?, compound=?,
                       dominant_signal=?, last_signal_at=datetime('now')
                   WHERE entity=?""",
                (new_intensity, new_count, compound, trigger["signal_type"], entity_name)
            )
        else:
            conn.execute(
                """INSERT INTO ms_pheromone_nodes
                   (entity, doc_id, total_intensity, signal_count, compound, dominant_signal)
                   VALUES (?,?,?,1,0,?)""",
                (entity_name, doc_id, strength, trigger["signal_type"])
            )
        conn.commit()
        conn.close()

    return signals


def propagate_signal(
    signal: PheromoneSignal,
    corpus: list[dict],  # [{"entity": str, "doc_id": int, "text": str}]
    max_hops: int = 3,
) -> list[dict]:
    """
    Propagate a signal through the corpus via keyword similarity.
    Returns list of pulled nodes with their pull strength.

    For each hop:
        new_strength = current_strength × similarity × DECAY
        if new_strength >= SIGNAL_MIN and similarity >= SEMANTIC_THRESHOLD: pull node
    """
    init_pheromone_tables()
    pulled = []
    visited = {signal.source_entity}
    queue = [(signal.source_entity, signal.strength, 0, signal.description)]

    while queue:
        current_entity, current_strength, hop, source_text = queue.pop(0)
        if hop >= max_hops or current_strength < SIGNAL_MIN:
            continue

        for item in corpus:
            if item["entity"] in visited:
                continue

            sim = _keyword_similarity(source_text + " " + current_entity, item["text"])
            if sim < SEMANTIC_THRESHOLD:
                continue

            pull_strength = current_strength * sim * (SIGNAL_DECAY ** hop)
            if pull_strength < SIGNAL_MIN:
                continue

            visited.add(item["entity"])
            pulled.append({
                "entity": item["entity"],
                "doc_id": item["doc_id"],
                "pull_strength": round(pull_strength, 3),
                "similarity": round(sim, 3),
                "signal_type": signal.signal_type,
                "hop": hop + 1,
            })

            # Update pheromone node intensity
            conn = _get_db()
            existing = conn.execute(
                "SELECT * FROM ms_pheromone_nodes WHERE entity=?", (item["entity"],)
            ).fetchone()

            if existing:
                new_intensity = existing["total_intensity"] + pull_strength
                new_count = existing["signal_count"] + 1
                compound = int(new_intensity >= COMPOUND_MULTIPLIER or new_count >= 3)
                if compound and new_count >= 3:
                    new_intensity *= COMPOUND_MULTIPLIER  # compound boost
                conn.execute(
                    """UPDATE ms_pheromone_nodes
                       SET total_intensity=?, signal_count=?, compound=?,
                           dominant_signal=?, last_signal_at=datetime('now')
                       WHERE entity=?""",
                    (new_intensity, new_count, compound, signal.signal_type, item["entity"])
                )
            else:
                conn.execute(
                    """INSERT INTO ms_pheromone_nodes
                       (entity, doc_id, total_intensity, signal_count, compound, dominant_signal)
                       VALUES (?,?,?,1,0,?)""",
                    (item["entity"], item["doc_id"], pull_strength, signal.signal_type)
                )

            conn.commit()
            conn.close()

            queue.append((item["entity"], pull_strength, hop + 1, item["text"]))

    # Persist pulls
    if pulled:
        conn = _get_db()
        for p in pulled:
            conn.execute(
                """INSERT INTO ms_signal_pulls
                   (signal_id, pulled_entity, pulled_doc_id, pull_strength, similarity)
                   VALUES (?,?,?,?,?)""",
                (signal.signal_id, p["entity"], p["doc_id"], p["pull_strength"], p["similarity"])
            )
        conn.commit()
        conn.close()

    signal.pulled_nodes = pulled
    return pulled


def get_pheromone_field() -> PheromoneField:
    """Return current state of all pheromone nodes — the 'heat map'."""
    init_pheromone_tables()
    conn = _get_db()
    nodes = [dict(n) for n in conn.execute(
        "SELECT * FROM ms_pheromone_nodes ORDER BY total_intensity DESC"
    ).fetchall()]
    signals = [dict(s) for s in conn.execute(
        "SELECT signal_type, COUNT(*) as cnt FROM ms_signals GROUP BY signal_type"
    ).fetchall()]
    conn.close()

    hot = [n for n in nodes if n["total_intensity"] >= 0.5]
    compound = [n for n in nodes if n["compound"]]
    dominant = {s["signal_type"]: s["cnt"] for s in signals}

    return PheromoneField(
        hot_nodes=hot[:20],
        signal_count=len(nodes),
        compound_nodes=compound,
        dominant_signals=dominant,
    )


def analyse_documents(
    documents: list[dict],  # [{"doc_id": int, "filename": str, "text": str}]
) -> dict:
    """
    Full pheromone analysis pipeline:
    1. Scan each document for risk signals
    2. Propagate signals through the corpus
    3. Return heat map of highest-intensity nodes

    This is the construction equivalent of BlackSwanX's
    full adversarial analysis with pheromone deposits.
    """
    init_pheromone_tables()

    # Clear previous run
    conn = _get_db()
    conn.execute("DELETE FROM ms_signals")
    conn.execute("DELETE FROM ms_signal_pulls")
    conn.execute("DELETE FROM ms_pheromone_nodes")
    conn.commit()
    conn.close()

    all_signals = []
    corpus = [
        {"entity": doc["filename"], "doc_id": doc["doc_id"], "text": doc["text"]}
        for doc in documents
    ]

    for doc in documents:
        signals = scan_for_signals(doc["doc_id"], doc["text"], doc["filename"])
        all_signals.extend(signals)
        for sig in signals:
            propagate_signal(sig, corpus)

    field = get_pheromone_field()

    return {
        "signals_emitted": len(all_signals),
        "signal_types": list({s.signal_type for s in all_signals}),
        "hot_nodes": field.hot_nodes,
        "compound_nodes": field.compound_nodes,
        "dominant_signals": field.dominant_signals,
        "heat_map": [
            {
                "entity": n["entity"],
                "intensity": round(n["total_intensity"], 3),
                "signal_count": n["signal_count"],
                "compound": bool(n["compound"]),
                "dominant_signal": n["dominant_signal"],
            }
            for n in field.hot_nodes
        ],
    }
