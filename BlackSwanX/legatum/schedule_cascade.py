"""
Schedule-Aware Risk Cascade (Temporal Pheromone System)
=========================================================
Replaces generic cosine-similarity signal propagation with a CPM-integrated
temporal risk cascade for construction projects.

Core insight: In construction, delays and risks propagate along schedule
dependencies (the critical path), not just semantic similarity. A concrete
pouring delay doesn't just "relate to" a drywall delay — it CAUSES it, with
a quantifiable lag and cascading Nachtrag rights under VOB/B §6.

Standard pheromone decay: based on cosine similarity (text distance)
This system's decay: based on schedule proximity (time distance in CPM)

Signal strength to downstream node B:
    strength_B = strength_A
                 × text_similarity(A, B)      # document relevance
                 × schedule_proximity(A, B)   # CPM dependency weight
                 × (1 / (lag_days + 1))       # closer in time = stronger signal

Output:
    - Cascading risk alerts along the critical path
    - Estimated downstream Nachtrag exposure in EUR
    - VOB/B §6 rights triggered
    - Time window for Behinderungsanzeige submission
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Literal


# ── VOB/B §6 rules for delay rights ──────────────────────────────────────────

VOB_DELAY_RIGHTS = {
    "behinderungsanzeige_window_days": 3,   # Must notify within ~3 days of recognizing delay
    "bauzeitverlaengerung_threshold_days": 1,  # Any delay triggers right to extension
    "schadensersatz_threshold_days": 7,     # >7 days may trigger §6 Abs. 6 Schadensersatz
    "vertragsstrafe_safe_days": 0,          # Vertragsstrafe only if delay attributable to AN
}

# Trade sequence — typical construction order (simplified CPM)
DEFAULT_TRADE_SEQUENCE = [
    "erdarbeiten",
    "fundamentarbeiten",
    "rohbau",
    "betonage",
    "mauerwerk",
    "dacharbeiten",
    "fassade",
    "fenster_tueren",
    "estrich",
    "heizung_sanitaer",
    "elektroinstallation",
    "trockenbau",
    "putz_maler",
    "bodenbelag",
    "aussenanlagen",
]

# Signal types for construction
ConstructionSignalType = Literal[
    "TERMIN_DELAY",         # Schedule delay detected
    "NACHTRAG_RISK",        # Potential Nachtrag claim downstream
    "BEHINDERUNG",          # Behinderungsanzeige trigger
    "MANGEL_CASCADE",       # Defect rippling to dependent trades
    "RESSOURCE_CONFLICT",   # Resource/material bottleneck
    "KRITISCHER_PFAD",      # Critical path milestone at risk
]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ScheduleNode:
    """A task/milestone in the project schedule."""
    node_id: str
    name: str
    trade: str                          # e.g. "betonage", "trockenbau"
    planned_start: date
    planned_end: date
    actual_start: date | None = None
    actual_end: date | None = None
    predecessors: list[str] = field(default_factory=list)  # node_ids
    lag_days: int = 0                   # mandatory lag after predecessor
    contract_value_eur: float = 0.0
    subcontractor: str | None = None
    is_critical_path: bool = False


@dataclass
class CascadeSignal:
    """A risk signal propagating through the schedule."""
    signal_id: str
    signal_type: ConstructionSignalType
    source_node_id: str
    source_node_name: str
    delay_days: int
    strength: float                     # 0-1
    financial_exposure_eur: float = 0.0
    vob_rights: list[str] = field(default_factory=list)
    propagated_to: list[str] = field(default_factory=list)
    hops: int = 0
    emitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class CascadeResult:
    """Full cascade analysis result."""
    trigger_node: str
    trigger_node_name: str
    delay_days: int
    affected_nodes: list[dict] = field(default_factory=list)
    total_exposure_eur: float = 0.0
    vob_rights_triggered: list[str] = field(default_factory=list)
    behinderungsanzeige_deadline: str | None = None
    critical_path_impact: bool = False
    recommendation: str = ""
    cascade_depth: int = 0


# ── Database ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db_path = Path(__file__).parent.parent / "backend" / "blackswanx.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schedule_tables() -> None:
    """Create schedule cascade tables (idempotent)."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ms_schedule_nodes (
            node_id         TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL,
            name            TEXT NOT NULL,
            trade           TEXT NOT NULL,
            planned_start   TEXT NOT NULL,
            planned_end     TEXT NOT NULL,
            actual_start    TEXT,
            actual_end      TEXT,
            predecessors    TEXT DEFAULT '[]',
            lag_days        INTEGER DEFAULT 0,
            contract_value  REAL DEFAULT 0.0,
            subcontractor   TEXT,
            is_critical     INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_cascade_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT NOT NULL,
            trigger_node    TEXT NOT NULL,
            delay_days      INTEGER NOT NULL,
            affected_count  INTEGER DEFAULT 0,
            total_exposure  REAL DEFAULT 0.0,
            cascade_depth   INTEGER DEFAULT 0,
            vob_rights      TEXT DEFAULT '[]',
            logged_at       TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Schedule input helpers ────────────────────────────────────────────────────

def register_schedule(
    project_id: str,
    tasks: list[dict],
) -> dict:
    """
    Register project schedule tasks.

    Each task dict:
        node_id, name, trade, planned_start (ISO date), planned_end (ISO date),
        predecessors (list of node_ids), lag_days, contract_value_eur,
        subcontractor (optional), is_critical_path (bool)
    """
    init_schedule_tables()
    conn = _get_db()

    for t in tasks:
        conn.execute(
            """INSERT OR REPLACE INTO ms_schedule_nodes
               (node_id, project_id, name, trade, planned_start, planned_end,
                actual_start, actual_end, predecessors, lag_days,
                contract_value, subcontractor, is_critical)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t["node_id"], project_id, t["name"], t.get("trade", ""),
                t["planned_start"], t["planned_end"],
                t.get("actual_start"), t.get("actual_end"),
                json.dumps(t.get("predecessors", [])),
                t.get("lag_days", 0),
                t.get("contract_value_eur", 0.0),
                t.get("subcontractor"),
                int(t.get("is_critical_path", False)),
            )
        )

    conn.commit()
    conn.close()
    return {"project_id": project_id, "tasks_registered": len(tasks)}


def record_delay(
    project_id: str,
    node_id: str,
    delay_days: int,
    reason: str = "",
) -> None:
    """Record an actual delay on a schedule node."""
    init_schedule_tables()
    conn = _get_db()
    conn.execute(
        "UPDATE ms_schedule_nodes SET actual_start=? WHERE node_id=? AND project_id=?",
        (reason[:200], node_id, project_id)  # store reason in actual_start for now
    )
    conn.commit()
    conn.close()


# ── Core cascade algorithm ────────────────────────────────────────────────────

def _schedule_proximity(
    node_a: sqlite3.Row,
    node_b: sqlite3.Row,
    predecessors_b: list[str],
) -> float:
    """
    Calculate schedule proximity weight between two nodes.
    Direct predecessor = 1.0, indirect = decays by 0.7 per hop.
    """
    if node_a["node_id"] in predecessors_b:
        return 1.0  # Direct dependency

    # Check trade sequence proximity
    trade_a = node_a["trade"].lower()
    trade_b = node_b["trade"].lower()
    try:
        idx_a = next(
            i for i, t in enumerate(DEFAULT_TRADE_SEQUENCE) if t in trade_a
        )
        idx_b = next(
            i for i, t in enumerate(DEFAULT_TRADE_SEQUENCE) if t in trade_b
        )
        distance = abs(idx_b - idx_a)
        if distance == 0:
            return 0.9
        elif distance == 1:
            return 0.7
        elif distance == 2:
            return 0.5
        elif distance <= 4:
            return 0.3
        else:
            return 0.1
    except StopIteration:
        return 0.2  # Unknown trade — weak connection


def _text_similarity_simple(text_a: str, text_b: str) -> float:
    """
    Lightweight text similarity without embeddings.
    Token overlap (Jaccard on word sets).
    """
    words_a = set(re.findall(r'\w{4,}', text_a.lower()))
    words_b = set(re.findall(r'\w{4,}', text_b.lower()))
    if not words_a or not words_b:
        return 0.1
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def propagate_delay_cascade(
    project_id: str,
    trigger_node_id: str,
    delay_days: int,
    initial_strength: float = 1.0,
    max_depth: int = 6,
) -> CascadeResult:
    """
    Propagate a delay signal through the project schedule.

    For each downstream node:
        signal_strength = parent_strength
                         × schedule_proximity(trigger, node)
                         × (1 / (lag_days + 1))
                         × DECAY^hops (0.85)

    Nodes above 0.3 threshold are included in the cascade.
    VOB/B §6 rights triggered based on delay magnitude.

    Returns CascadeResult with full downstream impact analysis.
    """
    init_schedule_tables()
    DECAY = 0.85
    MIN_STRENGTH = 0.15

    conn = _get_db()
    all_nodes = conn.execute(
        "SELECT * FROM ms_schedule_nodes WHERE project_id=?",
        (project_id,)
    ).fetchall()
    conn.close()

    if not all_nodes:
        return CascadeResult(
            trigger_node=trigger_node_id,
            trigger_node_name="Unknown",
            delay_days=delay_days,
            recommendation="Kein Terminplan registriert. Bitte Terminplan zuerst einpflegen."
        )

    nodes_by_id = {n["node_id"]: n for n in all_nodes}
    trigger = nodes_by_id.get(trigger_node_id)
    if not trigger:
        return CascadeResult(
            trigger_node=trigger_node_id,
            trigger_node_name="Not found",
            delay_days=delay_days,
        )

    # BFS-style cascade propagation
    affected: list[dict] = []
    visited: set[str] = {trigger_node_id}
    queue: list[tuple[str, float, int]] = [(trigger_node_id, initial_strength, 0)]

    while queue:
        current_id, current_strength, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        current_node = nodes_by_id.get(current_id)
        if not current_node:
            continue

        # Find all downstream nodes (nodes that have current as predecessor)
        for candidate in all_nodes:
            if candidate["node_id"] in visited:
                continue

            predecessors = json.loads(candidate["predecessors"] or "[]")
            # Include if: direct predecessor match OR same trade family
            is_downstream = (
                current_id in predecessors or
                _text_similarity_simple(
                    current_node["trade"], candidate["trade"]
                ) > 0.1
            )
            if not is_downstream:
                continue

            # Calculate signal strength for this candidate
            sched_prox = _schedule_proximity(current_node, candidate, predecessors)
            is_direct_predecessor = current_id in predecessors

            # For direct schedule predecessors: use sched_prox only (no text similarity required)
            # Construction tasks in sequence share zero vocabulary ("Betonage" ≠ "Trockenbau")
            # but are causally linked — the schedule IS the connection
            if is_direct_predecessor:
                text_sim = 1.0  # direct causal link — bypass text similarity
            else:
                text_sim = max(0.1, _text_similarity_simple(
                    current_node["trade"], candidate["trade"]
                ))

            # Lag affects WHEN the impact hits, not WHETHER it cascades.
            # Use lag only to modulate downstream delay, not to kill the signal.
            # A 14-day concrete delay still cascades to drywall even if lag=4.
            lag = candidate["lag_days"] or 0

            signal_strength = current_strength * sched_prox * text_sim * DECAY

            if signal_strength < MIN_STRENGTH:
                continue

            visited.add(candidate["node_id"])

            # Calculate downstream delay (propagated delay × schedule proximity)
            downstream_delay = round(delay_days * sched_prox)

            # Calculate financial exposure
            exposure = candidate["contract_value"] * (downstream_delay / 30) * 0.15
            # Rough: 15% of monthly contract value per month of delay

            affected.append({
                "node_id": candidate["node_id"],
                "name": candidate["name"],
                "trade": candidate["trade"],
                "subcontractor": candidate["subcontractor"],
                "signal_strength": round(signal_strength, 3),
                "downstream_delay_days": downstream_delay,
                "financial_exposure_eur": round(exposure, 2),
                "is_critical_path": bool(candidate["is_critical"]),
                "planned_start": candidate["planned_start"],
                "depth": depth + 1,
                "vob_right": (
                    "VOB/B §6 Abs. 6 Schadensersatz"
                    if downstream_delay >= VOB_DELAY_RIGHTS["schadensersatz_threshold_days"]
                    else "VOB/B §6 Bauzeitverlängerung"
                ),
            })

            queue.append((candidate["node_id"], signal_strength, depth + 1))

    # Sort by signal strength
    affected.sort(key=lambda x: -x["signal_strength"])

    # Aggregate results
    total_exposure = sum(n["financial_exposure_eur"] for n in affected)
    critical_path_impact = any(n["is_critical_path"] for n in affected)
    cascade_depth = max((n["depth"] for n in affected), default=0)

    # VOB/B rights
    vob_rights = list(set(n["vob_right"] for n in affected))
    if delay_days >= VOB_DELAY_RIGHTS["schadensersatz_threshold_days"]:
        vob_rights.append("VOB/B §6 Abs. 6 — Schadensersatzanspruch prüfen")

    # Behinderungsanzeige deadline
    behinderung_deadline = (
        date.today() + timedelta(days=VOB_DELAY_RIGHTS["behinderungsanzeige_window_days"])
    ).isoformat()

    # Build recommendation
    if critical_path_impact and delay_days >= 7:
        recommendation = (
            f"🔴 KRITISCHER PFAD BETROFFEN: {delay_days} Tage Verzögerung "
            f"bei '{trigger['name']}' gefährdet {len(affected)} nachfolgende Gewerke. "
            f"Geschätzte Nachtragsexposition: EUR {total_exposure:,.0f}. "
            f"Behinderungsanzeige bis {behinderung_deadline} einreichen (VOB/B §6)."
        )
    elif len(affected) >= 3:
        recommendation = (
            f"🟡 KASKADENWIRKUNG: {len(affected)} Gewerke betroffen. "
            f"Geschätzte Exposition: EUR {total_exposure:,.0f}. "
            f"Abstimmung mit betroffenen AN empfohlen."
        )
    else:
        recommendation = (
            f"🟢 BEGRENZTE AUSWIRKUNG: {len(affected)} nachgelagerte Gewerke betroffen. "
            f"Geschätzte Exposition: EUR {total_exposure:,.0f}."
        )

    # Log the cascade
    conn2 = _get_db()
    conn2.execute(
        """INSERT INTO ms_cascade_log
           (project_id, trigger_node, delay_days, affected_count,
            total_exposure, cascade_depth, vob_rights)
           VALUES (?,?,?,?,?,?,?)""",
        (project_id, trigger_node_id, delay_days, len(affected),
         total_exposure, cascade_depth, json.dumps(vob_rights))
    )
    conn2.commit()
    conn2.close()

    return CascadeResult(
        trigger_node=trigger_node_id,
        trigger_node_name=trigger["name"],
        delay_days=delay_days,
        affected_nodes=affected,
        total_exposure_eur=round(total_exposure, 2),
        vob_rights_triggered=vob_rights,
        behinderungsanzeige_deadline=behinderung_deadline,
        critical_path_impact=critical_path_impact,
        recommendation=recommendation,
        cascade_depth=cascade_depth,
    )


def cascade_to_dict(result: CascadeResult) -> dict:
    """Serialize CascadeResult to JSON-compatible dict."""
    return {
        "trigger": {
            "node_id": result.trigger_node,
            "name": result.trigger_node_name,
            "delay_days": result.delay_days,
        },
        "cascade_summary": {
            "affected_nodes": len(result.affected_nodes),
            "cascade_depth": result.cascade_depth,
            "critical_path_impact": result.critical_path_impact,
            "total_exposure_eur": result.total_exposure_eur,
        },
        "vob_rights_triggered": result.vob_rights_triggered,
        "behinderungsanzeige_deadline": result.behinderungsanzeige_deadline,
        "recommendation": result.recommendation,
        "affected_nodes": result.affected_nodes[:10],  # top 10 by signal strength
    }


# ── Quick analysis from document text ────────────────────────────────────────

DELAY_PATTERNS = [
    (r'(\d+)\s*(?:tage?|days?)\s*(?:verzögerung|verspätung|delay)', 'delay_days'),
    (r'(?:verzögerung|verspätung|delay)\s*(?:von\s*)?(\d+)\s*(?:tage?|days?)', 'delay_days'),
    (r'(\d+)\s*(?:wochen?|weeks?)\s*(?:verzögerung|delay)', 'delay_weeks'),
]

TRADE_MENTIONS = {
    "beton": "betonage",
    "rohbau": "rohbau",
    "estrich": "estrich",
    "elektro": "elektroinstallation",
    "heizung": "heizung_sanitaer",
    "sanitär": "heizung_sanitaer",
    "trockenbau": "trockenbau",
    "putz": "putz_maler",
    "fenster": "fenster_tueren",
    "dach": "dacharbeiten",
    "fassade": "fassade",
}


def analyze_delay_from_text(text: str, project_id: str) -> dict:
    """
    Extract delay information from document text and identify affected trades.
    Lightweight — no LLM, regex-based.
    """
    text_lower = text.lower()

    # Extract delay magnitude
    delay_days = 0
    for pattern, dtype in DELAY_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            val = int(m.group(1))
            delay_days = val * 7 if dtype == "delay_weeks" else val
            break

    # Identify mentioned trades
    mentioned_trades = []
    for keyword, trade in TRADE_MENTIONS.items():
        if keyword in text_lower:
            mentioned_trades.append(trade)

    # Check for VOB/B §6 keywords
    vob6_triggered = bool(re.search(
        r'behinderung|unterbrechung|verzögerung.*schuldet|hindrance',
        text_lower
    ))

    return {
        "delay_days_detected": delay_days,
        "trades_mentioned": list(set(mentioned_trades)),
        "vob6_triggered": vob6_triggered,
        "behinderungsanzeige_required": vob6_triggered and delay_days > 0,
        "behinderungsanzeige_deadline": (
            (date.today() + timedelta(days=3)).isoformat()
            if vob6_triggered else None
        ),
    }
