"""SONA — Self-Optimizing Neural Architecture (System Auditor).

SONA doesn't just remember past predictions. It:
1. AUDITS every agent after each pipeline run
2. SCORES agent quality by comparing their output to what actually happened
3. BOOSTS agents that successfully predicted edge cases
4. DEMOTES agents that missed critical risks
5. Stores PATTERNS OF SUCCESS in a ReasoningBank, not just text

Example:
- Phase 1: 20 Shadow Agents analyze a Reddit thread
- Phase 2: SONA compares their output to the BlackSwan Assassin's report
- Phase 3: If a "Cynical Redditor" agent predicted a "Liquidity Trap" that
  the "VC Agent" missed, SONA BOOSTS that Shadow Agent's weight for all
  future financial queries

The ReasoningBank stores:
- Which agent types are strong/weak per domain
- Which persona types catch risks that experts miss
- Historical accuracy scores per agent per topic type
"""
import json
import sqlite3
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resonance.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_sona_tables():
    """Create SONA tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sona_agent_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            topic_domain TEXT NOT NULL,
            quality_score REAL DEFAULT 0.0,
            accuracy_score REAL DEFAULT 0.0,
            edge_case_bonus REAL DEFAULT 0.0,
            total_weight REAL DEFAULT 1.0,
            runs INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sona_reasoning_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_description TEXT NOT NULL,
            source_agent TEXT,
            topic_domain TEXT,
            confidence REAL DEFAULT 0.5,
            times_validated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sona_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT,
            topic TEXT,
            agent_id TEXT,
            agent_type TEXT,
            score REAL,
            reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_domain
            ON sona_agent_scores(agent_id, topic_domain);
    """)
    conn.commit()
    conn.close()


# Auto-init on import
init_sona_tables()


def get_agent_weight(agent_id: str, topic_domain: str) -> float:
    """Get the SONA-adjusted weight for an agent in a specific domain.

    Returns a multiplier: >1.0 means boosted, <1.0 means demoted.
    Default is 1.0 for new agents.
    """
    conn = _get_db()
    row = conn.execute(
        "SELECT total_weight FROM sona_agent_scores WHERE agent_id=? AND topic_domain=?",
        (agent_id, topic_domain)
    ).fetchone()
    conn.close()
    return row["total_weight"] if row else 1.0


def get_agent_weights_for_domain(topic_domain: str) -> dict:
    """Get all agent weights for a domain. Used to rank agents."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT agent_id, agent_type, total_weight, runs, quality_score, edge_case_bonus "
        "FROM sona_agent_scores WHERE topic_domain=? ORDER BY total_weight DESC",
        (topic_domain,)
    ).fetchall()
    conn.close()
    return {r["agent_id"]: dict(r) for r in rows}


async def audit_pipeline(
    pipeline_id: str,
    topic: str,
    topic_domain: str,
    swarm_waves: list,
    elite_results: dict,
    kill_shot: dict,
    cognitive_dissonance: dict,
):
    """SONA audits the entire pipeline after completion.

    Compares each agent's output to the BlackSwan's Kill Shot and
    the Cognitive Dissonance Score to determine who was right.
    """
    conn = _get_db()
    kill_trigger = kill_shot.get("trigger", "")
    kill_cascade = kill_shot.get("cascade", [])
    dissonance_score = cognitive_dissonance.get("score", 50)

    # ============================================================
    # AUDIT ELITE AGENTS
    # ============================================================
    for elite_id, result in elite_results.items():
        if not isinstance(result, dict):
            continue

        # Score: Did the elite identify the kill shot risk?
        result_text = json.dumps(result, default=str).lower()
        kill_trigger_lower = kill_trigger.lower()

        # Check if elite mentioned the kill shot's trigger
        risk_awareness = 0.0
        if kill_trigger_lower and any(
            word in result_text for word in kill_trigger_lower.split()[:5]
        ):
            risk_awareness = 0.5  # Partially aware

        # Check if elite identified cascade effects
        for cascade_step in kill_cascade:
            if isinstance(cascade_step, str) and any(
                word in result_text for word in cascade_step.lower().split()[:3]
            ):
                risk_awareness += 0.2

        risk_awareness = min(risk_awareness, 1.0)

        # Quality score: how specific vs generic was the output
        specificity = min(len(result_text) / 500, 1.0)  # Longer = more specific (rough heuristic)

        quality = (risk_awareness * 0.6 + specificity * 0.4)

        _update_agent_score(conn, elite_id, "elite", topic_domain, quality, risk_awareness)
        _log_audit(conn, pipeline_id, topic, elite_id, "elite", quality,
                    f"Risk awareness: {risk_awareness:.2f}, Specificity: {specificity:.2f}")

    # ============================================================
    # AUDIT SHADOW SWARM CITIZENS
    # ============================================================
    for wave in swarm_waves:
        for citizen in wave.get("citizens", []):
            persona = citizen.get("persona", "unknown")
            citizen_id = f"citizen_{persona[:30]}"
            gut = citizen.get("gut_feeling", "").lower()
            hot_take = citizen.get("hot_take", "").lower()

            # Did this citizen catch something the elites missed?
            edge_case_bonus = 0.0

            # Check if citizen's gut feeling aligned with kill shot
            if kill_trigger_lower and any(
                word in gut + " " + hot_take
                for word in kill_trigger_lower.split()[:5]
            ):
                edge_case_bonus = 0.5  # Citizen caught the risk!

            # Check if citizen was contrarian when dissonance was high
            sentiment = citizen.get("sentiment", 0)
            swarm_direction = 1 if cognitive_dissonance.get("swarm_bull_pct", 50) > 60 else -1
            if dissonance_score > 50 and (sentiment * swarm_direction) < 0:
                # Citizen was contrarian during high dissonance — smart!
                edge_case_bonus += 0.3

            edge_case_bonus = min(edge_case_bonus, 1.0)

            if edge_case_bonus > 0:
                _update_agent_score(conn, citizen_id, "citizen", topic_domain, 0.5, edge_case_bonus)
                _log_audit(conn, pipeline_id, topic, citizen_id, "citizen", edge_case_bonus,
                           f"Edge case detected! Persona: {persona[:50]}")

    # ============================================================
    # STORE PATTERNS IN REASONING BANK
    # ============================================================
    if dissonance_score > 60:
        _store_pattern(conn, "high_dissonance",
                       f"Topic '{topic}' showed dissonance score {dissonance_score}. "
                       f"Kill shot: {kill_trigger[:100]}. Swarm was "
                       f"{'bullish' if cognitive_dissonance.get('swarm_bull_pct', 50) > 60 else 'bearish'} "
                       f"but elites were {'split' if dissonance_score > 70 else 'cautious'}.",
                       "nexus", topic_domain)

    conn.commit()
    conn.close()


def get_reasoning_bank(topic_domain: str = None, limit: int = 20) -> list:
    """Retrieve patterns from the ReasoningBank."""
    conn = _get_db()
    if topic_domain:
        rows = conn.execute(
            "SELECT * FROM sona_reasoning_bank WHERE topic_domain=? "
            "ORDER BY times_validated DESC, confidence DESC LIMIT ?",
            (topic_domain, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sona_reasoning_bank "
            "ORDER BY times_validated DESC, confidence DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_agents(topic_domain: str, limit: int = 10) -> list:
    """Get the top-performing agents for a domain (SONA-ranked)."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT agent_id, agent_type, total_weight, quality_score, edge_case_bonus, runs "
        "FROM sona_agent_scores WHERE topic_domain=? "
        "ORDER BY total_weight DESC LIMIT ?",
        (topic_domain, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def enhance_system_prompt(base_prompt: str, agent_id: str, topic_domain: str) -> str:
    """Enhance an agent's system prompt with SONA's learned patterns.

    This is how the system gets SMARTER over time.
    """
    patterns = get_reasoning_bank(topic_domain, limit=5)
    if not patterns:
        return base_prompt

    weight = get_agent_weight(agent_id, topic_domain)

    sona_block = f"""
SONA SYSTEM AUDITOR CONTEXT:
Your performance weight for '{topic_domain}' topics: {weight:.2f}x
{'You are BOOSTED — your past predictions in this domain were accurate.' if weight > 1.2 else ''}
{'You are DEMOTED — your past predictions in this domain missed key risks. Be more careful.' if weight < 0.8 else ''}

PATTERNS FROM REASONING BANK (learned from past runs):
"""
    for p in patterns[:3]:
        sona_block += f"- [{p['pattern_type']}] {p['pattern_description'][:150]}\n"

    sona_block += "\nUse these patterns to improve your analysis. Avoid repeating past mistakes."

    return base_prompt + "\n\n" + sona_block


# ============================================================
# Internal helpers
# ============================================================

def _update_agent_score(conn, agent_id, agent_type, topic_domain, quality, edge_case_bonus):
    """Update or insert an agent's SONA score. Uses exponential moving average."""
    existing = conn.execute(
        "SELECT * FROM sona_agent_scores WHERE agent_id=? AND topic_domain=?",
        (agent_id, topic_domain)
    ).fetchone()

    if existing:
        # Exponential moving average: 70% old + 30% new
        new_quality = existing["quality_score"] * 0.7 + quality * 0.3
        new_edge = existing["edge_case_bonus"] * 0.7 + edge_case_bonus * 0.3
        new_weight = 0.5 + new_quality * 0.5 + new_edge * 0.5  # Weight between 0.5 and 1.5
        new_weight = max(0.3, min(2.0, new_weight))  # Clamp

        conn.execute(
            "UPDATE sona_agent_scores SET quality_score=?, edge_case_bonus=?, "
            "total_weight=?, runs=runs+1, last_updated=CURRENT_TIMESTAMP "
            "WHERE agent_id=? AND topic_domain=?",
            (new_quality, new_edge, new_weight, agent_id, topic_domain)
        )
    else:
        weight = 0.5 + quality * 0.5 + edge_case_bonus * 0.5
        conn.execute(
            "INSERT INTO sona_agent_scores (agent_id, agent_type, topic_domain, "
            "quality_score, edge_case_bonus, total_weight, runs) VALUES (?,?,?,?,?,?,1)",
            (agent_id, agent_type, topic_domain, quality, edge_case_bonus, weight)
        )


def _log_audit(conn, pipeline_id, topic, agent_id, agent_type, score, reasoning):
    conn.execute(
        "INSERT INTO sona_audit_log (pipeline_id, topic, agent_id, agent_type, score, reasoning) "
        "VALUES (?,?,?,?,?,?)",
        (pipeline_id, topic, agent_id, agent_type, score, reasoning)
    )


def _store_pattern(conn, pattern_type, description, source_agent, topic_domain):
    conn.execute(
        "INSERT INTO sona_reasoning_bank (pattern_type, pattern_description, source_agent, topic_domain) "
        "VALUES (?,?,?,?)",
        (pattern_type, description, source_agent, topic_domain)
    )


# ============================================================
# NERVOUS SYSTEM EXTENSIONS — Agent Deduplication
# ============================================================

def should_agent_run(agent_id: str, entity_hash: str) -> bool:
    """Check if an agent has already processed this data.

    Prevents duplicate compute — if Fraud Detector already scanned a booking,
    Tax Optimizer can skip re-scanning and use the cached result.

    entity_hash: hash of the data being processed (e.g., hash of booking IDs).
    """
    init_sona_tables()
    conn = _get_db()
    try:
        # Check recent audit log for this agent + entity combo
        result = conn.execute(
            "SELECT COUNT(*) FROM sona_audit_log WHERE agent_id = ? AND reasoning LIKE ? "
            "AND created_at > datetime('now', '-1 hour')",
            (agent_id, f"%{entity_hash[:20]}%")
        ).fetchone()
        already_processed = result[0] > 0
        return not already_processed
    finally:
        conn.close()


def get_cached_agent_result(agent_id: str, topic_domain: str) -> dict | None:
    """Get the most recent result from an agent for a domain.

    Used by the nervous system to inject prior results into downstream agents.
    """
    init_sona_tables()
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT score, reasoning FROM sona_audit_log "
            "WHERE agent_id = ? AND topic LIKE ? "
            "ORDER BY created_at DESC LIMIT 1",
            (agent_id, f"%{topic_domain}%")
        ).fetchone()
        if row:
            return {"agent_id": agent_id, "score": row[0], "reasoning": row[1]}
        return None
    finally:
        conn.close()
