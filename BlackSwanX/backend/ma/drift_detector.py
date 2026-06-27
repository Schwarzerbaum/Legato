"""
drift_detector.py — Opinion Drifter for LEGATUM Construction AI.

Plugs into SONA's ReasoningBank (SQLite) to track baselines and flag anomalies.
Zero LLM cost — pure math on existing graph/embedding/jury outputs.

Three detection mechanisms:

  1. Topological Drift (Stage 6.5 — post-ingestion)
     Monitors KG node type distribution and orphan ratio.
     Alarm: single relation type >60% of all edges, or orphans >10%.

  2. Embedding Cosine Drift (Stage 6.5 — post-ingestion)
     Tracks rolling mean embedding vector per domain.
     Alarm: cosine distance from baseline mean >0.35 (semantic foreign territory).

  3. Jury Variance Drift (post-query, optional)
     Measures consensus between Jury/Panel agent outputs using token overlap.
     Alarm: consensus <0.40 → agents diverging wildly → auto-escalate Ampel to RED.

Results are stored in SONA's sona_reasoning_bank table and returned as structured dict.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any

# SONA DB path — same SQLite used by BlackSwanX SONA
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resonance.db"
)
_DOMAIN = "construction_legatum"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    conn = _db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS legatum_drift_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_key TEXT NOT NULL UNIQUE,
            baseline_value TEXT NOT NULL,   -- JSON-encoded float or list
            sample_count  INTEGER DEFAULT 0,
            last_updated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS legatum_drift_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name      TEXT,
            metric_key    TEXT NOT NULL,
            current_value REAL,
            baseline_value REAL,
            deviation     REAL,
            alarm         INTEGER DEFAULT 0,   -- 1 = flagged
            detail        TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS agentic_ledger (
            id          TEXT PRIMARY KEY,
            entity      TEXT NOT NULL,
            agent_role  TEXT NOT NULL,   -- assassin | defender | judge | expert | moderator
            instruction TEXT NOT NULL,   -- behavioral directive injected into agent's system prompt
            priority    INTEGER DEFAULT 5,
            source_kid  TEXT,            -- FK → company_knowledge.id that triggered this
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS company_knowledge (
            id                  TEXT PRIMARY KEY,
            entity              TEXT NOT NULL,
            entity_type         TEXT NOT NULL DEFAULT 'CONCEPT',
            fact                TEXT NOT NULL,
            generalized_truth   TEXT,           -- Pass 3: refined, project-stripped version
            episodic_refs       TEXT,           -- JSON [{doc, page, snippet, variance_type}] — synapse bridge
            concept_embedding   TEXT,           -- JSON float array (BGE-M3 1024-dim)
            source_doc          TEXT,
            project_id          TEXT,
            org_id              TEXT DEFAULT 'default',
            confidence          REAL DEFAULT 1.0,
            repetition_count    INTEGER DEFAULT 1,
            ease_factor         REAL DEFAULT 2.5,
            memory_strength     REAL DEFAULT 0.1,
            is_permanent        INTEGER DEFAULT 0,  -- 1 when strength >= 0.75
            last_reinforced_at  TEXT DEFAULT (datetime('now')),
            created_at          TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def _get_baseline(key: str) -> dict | None:
    conn = _db()
    row = conn.execute(
        "SELECT baseline_value, sample_count FROM legatum_drift_baselines WHERE metric_key=?",
        (key,)
    ).fetchone()
    conn.close()
    if row:
        return {"value": json.loads(row["baseline_value"]), "count": row["sample_count"]}
    return None


def _update_baseline(key: str, new_value: float | list, alpha: float = 0.1):
    """EWA (exponential weighted average) update — new samples shift baseline slowly."""
    conn = _db()
    existing = conn.execute(
        "SELECT baseline_value, sample_count FROM legatum_drift_baselines WHERE metric_key=?",
        (key,)
    ).fetchone()

    if existing:
        old_val = json.loads(existing["baseline_value"])
        count   = existing["sample_count"] + 1
        if isinstance(new_value, list) and isinstance(old_val, list):
            # EWA per dimension
            updated = [alpha * n + (1 - alpha) * o for n, o in zip(new_value, old_val)]
        else:
            updated = alpha * float(new_value) + (1 - alpha) * float(old_val)
        conn.execute(
            "UPDATE legatum_drift_baselines SET baseline_value=?, sample_count=?, last_updated=? WHERE metric_key=?",
            (json.dumps(updated), count, datetime.utcnow().isoformat(), key)
        )
    else:
        conn.execute(
            "INSERT INTO legatum_drift_baselines (metric_key, baseline_value, sample_count) VALUES (?,?,?)",
            (key, json.dumps(new_value), 1)
        )
    conn.commit()
    conn.close()


def _log_drift(doc_name: str, key: str, current: float, baseline: float,
               deviation: float, alarm: bool, detail: str):
    conn = _db()
    conn.execute(
        "INSERT INTO legatum_drift_log (doc_name, metric_key, current_value, baseline_value, deviation, alarm, detail) "
        "VALUES (?,?,?,?,?,?,?)",
        (doc_name, key, current, baseline, deviation, int(alarm), detail)
    )
    # Also push to SONA reasoning bank if alarm fires
    if alarm:
        conn.execute(
            "INSERT INTO sona_reasoning_bank (pattern_type, pattern_description, source_agent, topic_domain, confidence) "
            "VALUES (?,?,?,?,?)",
            ("drift_alarm", f"{key}: {detail}", "drift_detector", _DOMAIN, 0.9)
        )
    conn.commit()
    conn.close()


# ── Cosine similarity (no deps) ───────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _mean_vector(vecs: list[list[float]]) -> list[float]:
    if not vecs:
        return []
    n = len(vecs[0])
    return [sum(v[i] for v in vecs) / len(vecs) for i in range(n)]


# ── Token overlap (for jury variance) ────────────────────────────────────────

def _token_overlap(a: str, b: str) -> float:
    tok_a = set(re.findall(r'\w+', a.lower()))
    tok_b = set(re.findall(r'\w+', b.lower()))
    if not tok_a or not tok_b:
        return 0.0
    return len(tok_a & tok_b) / len(tok_a | tok_b)


# ── 1. Topological Drift ──────────────────────────────────────────────────────

def check_topological_drift(
    nodes: list[dict],
    edges: list[dict],
    doc_name: str = "unknown",
) -> dict[str, Any]:
    """
    Check KG structure for anomalies vs learned baseline.

    Metrics tracked:
      - relation_entropy: Shannon entropy over edge type distribution (low = one type dominates)
      - orphan_ratio: nodes with no edges / total nodes
    """
    _ensure_tables()
    alarms = []
    metrics = {}

    if not edges:
        return {"alarms": [], "metrics": {}, "status": "no_edges"}

    # Relation type distribution
    rel_counts = Counter(e.get("type", "UNKNOWN") for e in edges)
    total_edges = len(edges)
    dominant_type  = rel_counts.most_common(1)[0]
    dominant_ratio = dominant_type[1] / total_edges

    # Shannon entropy over relation types
    entropy = 0.0
    for count in rel_counts.values():
        p = count / total_edges
        entropy -= p * math.log2(p)

    # Orphan ratio
    connected = set()
    for e in edges:
        connected.add(e.get("source", ""))
        connected.add(e.get("target", ""))
    orphan_ratio = 1 - (len(connected) / max(len(nodes), 1))

    metrics["dominant_ratio"] = round(dominant_ratio, 3)
    metrics["entropy"]        = round(entropy, 3)
    metrics["orphan_ratio"]   = round(orphan_ratio, 3)
    metrics["edge_count"]     = total_edges
    metrics["node_count"]     = len(nodes)

    # Compare against baselines
    for key, val, threshold, direction in [
        ("topo_dominant_ratio", dominant_ratio, 0.60, "above"),
        ("topo_orphan_ratio",   orphan_ratio,   0.10, "above"),
    ]:
        baseline_rec = _get_baseline(key)
        baseline_val = baseline_rec["value"] if baseline_rec else val

        deviation = abs(val - float(baseline_val))
        alarm = (val > threshold) if direction == "above" else (val < threshold)

        if alarm:
            alarms.append({
                "type": "topological",
                "metric": key,
                "current": round(val, 3),
                "baseline": round(float(baseline_val), 3),
                "threshold": threshold,
                "detail": (
                    f"Dominant relation '{dominant_type[0]}' = {dominant_ratio:.0%} of all edges"
                    if "dominant" in key
                    else f"Orphan nodes = {orphan_ratio:.0%} of KG"
                ),
            })
            _log_drift(doc_name, key, val, float(baseline_val), deviation, True,
                       alarms[-1]["detail"])

        # Update baseline with this observation (EWA, alpha=0.15)
        _update_baseline(key, val, alpha=0.15)

    return {"alarms": alarms, "metrics": metrics, "status": "ok"}


# ── 2. Embedding Cosine Drift ─────────────────────────────────────────────────

def check_embedding_drift(
    sections: list[dict],
    doc_name: str = "unknown",
    threshold: float = 0.35,
) -> dict[str, Any]:
    """
    Compare mean embedding of this document against the rolling baseline mean.
    Flags if cosine distance > threshold (0.35 = semantically far from normal docs).
    """
    _ensure_tables()

    vecs = [s["embedding"] for s in sections if s.get("embedding")]
    if not vecs:
        return {"alarms": [], "metrics": {}, "status": "no_embeddings"}

    doc_mean = _mean_vector(vecs)
    baseline_rec = _get_baseline("embed_mean_vector")

    if not baseline_rec:
        # First document — set as baseline, no alarm
        _update_baseline("embed_mean_vector", doc_mean, alpha=1.0)
        return {"alarms": [], "metrics": {"cosine_distance": 0.0, "status": "baseline_set"}, "status": "ok"}

    baseline_vec = baseline_rec["value"]
    cosine_sim   = _cosine(doc_mean, baseline_vec)
    distance     = 1.0 - cosine_sim

    alarm = distance > threshold
    alarms = []

    if alarm:
        detail = (
            f"Embedding cosine distance {distance:.3f} > threshold {threshold}. "
            f"Document may be in foreign domain or severely mis-parsed."
        )
        alarms.append({
            "type": "embedding",
            "metric": "embed_cosine_distance",
            "current": round(distance, 3),
            "threshold": threshold,
            "detail": detail,
        })
        _log_drift(doc_name, "embed_cosine_distance", distance, 0.0, distance, True, detail)

    # Update rolling baseline (alpha=0.1 — slow drift to accommodate new docs)
    _update_baseline("embed_mean_vector", doc_mean, alpha=0.1)

    return {
        "alarms": alarms,
        "metrics": {"cosine_distance": round(distance, 3), "cosine_sim": round(cosine_sim, 3)},
        "status": "ok",
    }


# ── 3. Jury Variance Drift ────────────────────────────────────────────────────

def check_jury_variance(
    critic_output: dict,
    doc_name: str = "unknown",
    consensus_threshold: float = 0.40,
) -> dict[str, Any]:
    """
    Measures token overlap between jury/panel agent outputs.
    Low consensus = agents diverging wildly = untrustworthy answer.

    Returns: drift result + whether to force Ampel RED.
    """
    _ensure_tables()

    if not critic_output:
        return {"alarms": [], "force_red": False, "consensus": None}

    mode = critic_output.get("mode", "jury")
    texts: list[str] = []

    if mode == "panel" and critic_output.get("experts"):
        texts = [v for v in critic_output["experts"].values() if v and not v.startswith("[")]
    else:
        for key in ("assassin", "defender", "critique"):
            if critic_output.get(key):
                texts.append(critic_output[key])

    if len(texts) < 2:
        return {"alarms": [], "force_red": False, "consensus": None}

    # Pairwise token overlap → mean consensus
    pairs = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            pairs.append(_token_overlap(texts[i], texts[j]))

    consensus = sum(pairs) / len(pairs)
    alarm = consensus < consensus_threshold

    alarms = []
    if alarm:
        detail = (
            f"Agent consensus {consensus:.2f} < threshold {consensus_threshold}. "
            f"Agents diverging — answer reliability low."
        )
        alarms.append({
            "type": "jury_variance",
            "metric": "agent_consensus",
            "current": round(consensus, 3),
            "threshold": consensus_threshold,
            "detail": detail,
        })
        _log_drift(doc_name, "jury_consensus", consensus, consensus_threshold,
                   consensus_threshold - consensus, True, detail)

        # Store pattern in SONA for future agent weighting
        conn = _db()
        conn.execute(
            "INSERT INTO sona_reasoning_bank (pattern_type, pattern_description, source_agent, topic_domain, confidence) "
            "VALUES (?,?,?,?,?)",
            ("jury_divergence", detail, "drift_detector", _DOMAIN, round(1 - consensus, 2))
        )
        conn.commit()
        conn.close()

    return {
        "alarms": alarms,
        "force_red": alarm,
        "consensus": round(consensus, 3),
        "agent_count": len(texts),
    }


# ── Combined ingestion check (Stage 6.5) ─────────────────────────────────────

def ingestion_drift_check(
    nodes: list[dict],
    edges: list[dict],
    sections: list[dict],
    doc_name: str = "unknown",
) -> dict[str, Any]:
    """
    Run topological + embedding drift checks after KG review, before saving.
    Returns combined result with all alarms.
    """
    topo   = check_topological_drift(nodes, edges, doc_name)
    embeds = check_embedding_drift(sections, doc_name)

    all_alarms = topo["alarms"] + embeds["alarms"]
    risk_level = "CRITICAL" if len(all_alarms) >= 2 else ("HIGH" if all_alarms else "OK")

    return {
        "risk_level": risk_level,
        "alarms": all_alarms,
        "topological": topo["metrics"],
        "embedding": embeds["metrics"],
        "recommendation": (
            "Flag for manual review — KG structure or document domain anomaly detected."
            if all_alarms else
            "Document within normal parameters."
        ),
    }


# ── Schema migration for existing DBs (safe: ALTER TABLE IF NOT EXISTS col) ───

def _migrate_company_knowledge():
    """Add new columns to company_knowledge if they don't exist yet (safe migration)."""
    new_cols = [
        ("generalized_truth",  "TEXT"),
        ("episodic_refs",      "TEXT DEFAULT '[]'"),
        ("concept_embedding",  "TEXT"),
        ("org_id",             "TEXT DEFAULT 'default'"),
        ("repetition_count",   "INTEGER DEFAULT 1"),
        ("ease_factor",        "REAL DEFAULT 2.5"),
        ("memory_strength",    "REAL DEFAULT 0.1"),
        ("is_permanent",       "INTEGER DEFAULT 0"),
        ("last_reinforced_at", "TEXT DEFAULT (datetime('now'))"),
    ]
    conn = _db()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(company_knowledge)").fetchall()}
    for col, typedef in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE company_knowledge ADD COLUMN {col} {typedef}")
    conn.commit()
    conn.close()


# ── Company Knowledge CRUD ────────────────────────────────────────────────────

def add_company_knowledge(entity: str, entity_type: str, fact: str,
                          source_doc: str = "", project_id: str = "",
                          confidence: float = 1.0) -> str:
    """Store a company knowledge entry. Returns the new id."""
    import uuid as _uuid
    _ensure_tables()
    eid = str(_uuid.uuid4())
    conn = _db()
    conn.execute(
        "INSERT INTO company_knowledge (id, entity, entity_type, fact, source_doc, project_id, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, entity, entity_type, fact, source_doc, project_id, confidence)
    )
    conn.commit()
    conn.close()
    return eid


def list_company_knowledge(project_id: str = "", limit: int = 200) -> list[dict]:
    """Return stored company knowledge entries."""
    _ensure_tables()
    conn = _db()
    if project_id:
        rows = conn.execute(
            "SELECT * FROM company_knowledge WHERE project_id=? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM company_knowledge ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_company_knowledge(kid: str) -> bool:
    """Delete a single entry by id. Returns True if deleted."""
    _ensure_tables()
    conn = _db()
    cur = conn.execute("DELETE FROM company_knowledge WHERE id=?", (kid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def inject_memory_into_graph(sections: list[dict], node_set: dict, rels: list[dict]) -> tuple[dict, list[dict]]:
    """
    Pre-Stage-3 injection: scan document text for known company entities,
    add them as confidence=1.0 nodes and SUBORDINATE_TO edges if not already present.
    Mutates node_set and rels in place and returns them.
    """
    _ensure_tables()
    conn = _db()
    entries = conn.execute("SELECT entity, entity_type, fact FROM company_knowledge").fetchall()
    conn.close()
    if not entries:
        return node_set, rels

    # Build a combined text blob from the first ~50 sections for matching
    doc_text = " ".join(
        (s.get("text") or " ".join(s.get("blocks", [])))
        for s in sections[:50]
    ).lower()

    import re as _re2
    for row in entries:
        entity, etype, fact = row["entity"], row["entity_type"], row["fact"]
        if _re2.search(_re2.escape(entity.lower()), doc_text):
            if entity not in node_set:
                node_set[entity] = {
                    "id": entity, "type": etype, "page": 0,
                    "confidence": 1.0, "method": "memory"
                }
            # Add a memory-sourced self-annotation edge (fact as target node)
            fact_node = f"{entity}: {fact}"
            if fact_node not in node_set:
                node_set[fact_node] = {
                    "id": fact_node, "type": "CONCEPT", "page": 0,
                    "confidence": 1.0, "method": "memory"
                }
            rels.append({
                "source": entity, "target": fact_node,
                "relation": "known_as", "confidence": 1.0,
                "method": "memory",
                "source_type": etype, "target_type": "CONCEPT"
            })
    return node_set, rels


# ── Episodic → Semantic Consolidation Engine ─────────────────────────────────
# Implements the 3-pass memory consolidation described in the IP architecture:
#   Pass 1: Novelty Extractor — derive structured tuples from KG nodes post-ingestion
#   Pass 2: Vector + entity dedup — reinforce existing memories or insert new ones
#   Pass 3: Generalization trigger — when strength >= 0.75, LLM refines the truth

_SM2_MIN_EASE = 1.3
_STRENGTH_THRESHOLD = 0.75   # permanent memory
_COSINE_DEDUP_THRESHOLD = 0.88   # treat as same concept if similarity > this


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


def _embed_text_for_memory(text: str) -> list[float] | None:
    """Embed a string using BGE-M3 via the legatum embedding provider."""
    try:
        from legatum.embeddings import embed
        result = embed(text)
        if result and result.embedding:
            return result.embedding
    except Exception:
        pass
    try:
        import urllib.request, json as _json
        body = _json.dumps({"model": "nomic-embed-text", "prompt": text}).encode()
        req  = urllib.request.Request("http://localhost:11434/api/embeddings",
                                      data=body, method="POST",
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return _json.loads(r.read()).get("embedding")
    except Exception:
        return None


def _sm2_update(repetition_count: int, ease_factor: float,
                memory_strength: float) -> tuple[int, float, float]:
    """
    SM-2 variant update.
    Returns (new_repetition_count, new_ease_factor, new_memory_strength).
    Each reinforcement bumps strength toward 1.0 with diminishing returns.
    """
    new_count = repetition_count + 1
    # Ease factor adjusts based on repetition frequency (simplified)
    new_ease  = max(_SM2_MIN_EASE, ease_factor - 0.1 + 0.08 * (1 / new_count))
    # Memory strength: SM-2 interval proxy, capped at 1.0
    new_strength = min(1.0, memory_strength + (1.0 - memory_strength) * (0.3 / new_ease))
    return new_count, round(new_ease, 4), round(new_strength, 4)


def _find_similar_memory(embedding: list[float], entity_type: str,
                         org_id: str = "default") -> dict | None:
    """Return the most similar existing memory entry if cosine > threshold."""
    conn = _db()
    rows = conn.execute(
        "SELECT id, entity, fact, concept_embedding, repetition_count, ease_factor, memory_strength "
        "FROM company_knowledge WHERE org_id=? AND concept_embedding IS NOT NULL AND entity_type=?",
        (org_id, entity_type)
    ).fetchall()
    conn.close()
    best_sim, best_row = 0.0, None
    for row in rows:
        try:
            stored_emb = json.loads(row["concept_embedding"])
            sim = _cosine(embedding, stored_emb)
            if sim > best_sim:
                best_sim, best_row = sim, dict(row)
        except Exception:
            continue
    if best_sim >= _COSINE_DEDUP_THRESHOLD:
        return best_row
    return None


def _reinforce_memory(kid: str, source_doc: str, project_id: str,
                      episodic_snippet: str = "", episodic_page: int = 0):
    """Pass 2 update: increment repetition_count, recompute SM-2, append episodic ref."""
    conn = _db()
    row = conn.execute(
        "SELECT repetition_count, ease_factor, memory_strength, episodic_refs "
        "FROM company_knowledge WHERE id=?",
        (kid,)
    ).fetchone()
    if not row:
        conn.close()
        return
    new_count, new_ease, new_strength = _sm2_update(
        row["repetition_count"], row["ease_factor"], row["memory_strength"]
    )
    is_permanent = 1 if new_strength >= _STRENGTH_THRESHOLD else 0

    # Append episodic ref to the synapse bridge array
    try:
        refs = json.loads(row["episodic_refs"] or "[]")
    except Exception:
        refs = []
    if episodic_snippet or source_doc:
        refs.append({
            "doc": source_doc, "page": episodic_page,
            "snippet": episodic_snippet[:300],
            "project_id": project_id,
            "variance_type": "LOCAL_VARIANCE"
        })
    # Keep last 10 episodic refs to stay compact
    refs = refs[-10:]

    conn.execute(
        "UPDATE company_knowledge SET repetition_count=?, ease_factor=?, memory_strength=?, "
        "is_permanent=?, last_reinforced_at=?, episodic_refs=?, "
        "source_doc=COALESCE(source_doc||', '||?, source_doc) "
        "WHERE id=?",
        (new_count, new_ease, new_strength, is_permanent,
         datetime.utcnow().isoformat(), json.dumps(refs), source_doc, kid)
    )
    conn.commit()
    conn.close()
    if is_permanent:
        _trigger_generalization(kid)


def _trigger_generalization(kid: str):
    """
    Pass 3: when memory_strength >= 0.75, produce a generalized_truth via LLM
    AND compile_compact_context — a pre-digested narrative that flattens the
    core principle + known episodic variances into one cohesive string.

    This means the LLM at Q&A time reads ONE integrated statement, not 4 tiers,
    which is critical for 3B models that suffer from "lost in the middle."
    """
    try:
        conn = _db()
        row = conn.execute(
            "SELECT entity, entity_type, fact, source_doc, episodic_refs "
            "FROM company_knowledge WHERE id=?", (kid,)
        ).fetchone()
        conn.close()
        if not row or not row["fact"]:
            return

        # Parse episodic refs for the compact context
        try:
            refs = json.loads(row["episodic_refs"] or "[]")
        except Exception:
            refs = []

        import urllib.request, json as _json

        # Build a pre-digested episodic summary for the LLM prompt
        variance_lines = ""
        if refs:
            variance_lines = "Known specific applications observed across documents:\n"
            for r in refs[-5:]:  # last 5 references
                snippet = r.get("snippet", "")[:150]
                variance_lines += (
                    f"- In '{r.get('doc','')}' (p.{r.get('page','')}): {snippet}\n"
                )

        prompt = (
            f"You are a construction contract knowledge engineer for a German construction AI platform. "
            f"A concept has been observed across multiple documents and is now being consolidated.\n\n"
            f"Concept: '{row['entity']}' ({row['entity_type']})\n"
            f"Repeated fact: {row['fact']}\n"
            f"{variance_lines}\n"
            f"Write a single, generalized institutional truth (1-2 sentences). "
            f"Strip all project-specific IDs and page numbers — keep only the universal rule. "
            f"Write in German if the content is German, English otherwise. "
            f"Output ONLY the truth text, nothing else."
        )
        body = _json.dumps({"model": "llama3.2:3b", "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=body, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            truth = _json.loads(r.read()).get("response", "").strip()

        conn2 = _db()
        if truth:
            conn2.execute(
                "UPDATE company_knowledge SET generalized_truth=? WHERE id=?", (truth, kid)
            )
        conn2.commit()
        conn2.close()
        # Spawn role-specific behavioral instructions in the Agentic Ledger
        _auto_promote_to_agentic(kid)
    except Exception:
        pass  # generalization is best-effort, never blocks ingestion


def consolidate_memory_from_kg(nodes: list[dict], edges: list[dict],
                               doc_name: str, project_id: str = "",
                               org_id: str = "default"):
    """
    Pass 1 + 2: After KG extraction, derive structured memory tuples from
    high-confidence nodes and reinforce or insert them.

    Called post-Stage 7 so the full LLM-enhanced KG is available.
    Only nodes with confidence >= 0.8 are candidates.
    """
    _ensure_tables()
    _migrate_company_knowledge()
    import uuid as _uuid

    # Build entity→edges lookup for richer fact construction
    edge_map: dict[str, list[dict]] = {}
    for e in edges:
        edge_map.setdefault(e.get("source", ""), []).append(e)

    candidates = [
        n for n in nodes
        if n.get("confidence", 0.6) >= 0.8
        and n.get("entity_type", n.get("type", "")) not in ("CONCEPT",)
        and len(n.get("id", "")) >= 4
    ]

    for node in candidates:
        entity      = node.get("id", "")
        entity_type = node.get("entity_type") or node.get("type", "CONCEPT")
        # Build a fact string from outgoing edges
        outgoing = edge_map.get(entity, [])
        if outgoing:
            fact_parts = [f"{e['relation']} {e['target']}" for e in outgoing[:3]]
            fact = f"{entity} — " + "; ".join(fact_parts)
        else:
            fact = f"{entity} — found in {doc_name}"

        # Embed the entity+fact for dedup
        embedding = _embed_text_for_memory(f"{entity_type}: {entity}. {fact}")

        if embedding:
            existing = _find_similar_memory(embedding, entity_type, org_id)
            if existing:
                # Pass 2: reinforce existing memory + append episodic ref
                _reinforce_memory(
                    existing["id"], doc_name, project_id,
                    episodic_snippet=fact,
                    episodic_page=node.get("page", 0)
                )
                continue

        # Insert new episodic memory with low initial strength
        kid = str(_uuid.uuid4())
        conn = _db()
        conn.execute(
            "INSERT INTO company_knowledge "
            "(id, entity, entity_type, fact, concept_embedding, source_doc, project_id, "
            "org_id, confidence, repetition_count, ease_factor, memory_strength, is_permanent) "
            "VALUES (?,?,?,?,?,?,?,?,?,1,2.5,0.1,0)",
            (kid, entity, entity_type, fact,
             json.dumps(embedding) if embedding else None,
             doc_name, project_id, org_id, node.get("confidence", 0.8))
        )
        conn.commit()
        conn.close()


def search_semantic_memory(query_embedding: list[float], min_strength: float = 0.4,
                           top_k: int = 3, org_id: str = "default") -> list[dict]:
    """
    Retrieve high-strength memories semantically similar to the query embedding.
    Used at Q&A time to inject INSTITUTIONAL GLOBAL KNOWLEDGE into the context window.
    """
    _ensure_tables()
    _migrate_company_knowledge()
    conn = _db()
    rows = conn.execute(
        "SELECT id, entity, entity_type, fact, generalized_truth, concept_embedding, "
        "memory_strength, repetition_count, is_permanent "
        "FROM company_knowledge "
        "WHERE org_id=? AND memory_strength>=? AND concept_embedding IS NOT NULL "
        "ORDER BY memory_strength DESC LIMIT 100",
        (org_id, min_strength)
    ).fetchall()
    conn.close()

    scored: list[tuple[float, dict]] = []
    for row in rows:
        try:
            emb = json.loads(row["concept_embedding"])
            sim = _cosine(query_embedding, emb)
            scored.append((sim, dict(row)))
        except Exception:
            continue

    scored.sort(key=lambda x: -x[0])
    results = []
    for sim, row in scored[:top_k]:
        if sim < 0.3:
            continue
        results.append({
            **row,
            "similarity": round(sim, 3),
            "display_truth": row.get("generalized_truth") or row.get("fact", ""),
        })
    return results


# ── Agentic Ledger — behavioral instructions generated from permanent memories ──
# When a memory becomes permanent (strength ≥ 0.75), an LLM generates role-specific
# procedural instructions so each agent knows WHAT TO WATCH FOR when that entity appears.

_AGENTIC_ROLES = ["assassin", "defender", "judge", "expert", "moderator"]

_AGENTIC_ROLE_PROMPTS = {
    "assassin": (
        "You are configuring a skeptical construction lawyer (Assassin) who attacks AI answers. "
        "Based on this permanent institutional knowledge, write ONE short behavioral instruction "
        "(max 2 sentences, German preferred) telling the Assassin what to specifically scrutinize "
        "when this entity appears in a document. Focus on deadlines, liabilities, and common errors."
    ),
    "defender": (
        "You are configuring a defensive construction jurist (Defender) who protects AI answers. "
        "Based on this permanent institutional knowledge, write ONE short behavioral instruction "
        "(max 2 sentences, German preferred) telling the Defender which evidence or §-references "
        "to cite when this entity appears. Focus on legal basis and standard contract protections."
    ),
    "judge": (
        "You are configuring a neutral arbitration judge for construction compliance. "
        "Based on this permanent institutional knowledge, write ONE short behavioral instruction "
        "(max 2 sentences, German preferred) telling the Judge what weight to give this entity "
        "and which consistency checks to run. Focus on cross-document verification."
    ),
    "expert": (
        "You are configuring a domain expert panel member for construction document analysis. "
        "Based on this permanent institutional knowledge, write ONE short behavioral instruction "
        "(max 2 sentences, German preferred) telling the expert what domain-specific risk or "
        "opportunity this entity represents. Be concrete — e.g. '§12 VOB/B 14-day deadline'."
    ),
    "moderator": (
        "You are configuring a panel moderator for construction expert debates. "
        "Based on this permanent institutional knowledge, write ONE short behavioral instruction "
        "(max 2 sentences, German preferred) telling the moderator how to weigh this entity "
        "when synthesizing expert opinions. Focus on consensus-breaking edge cases."
    ),
}


def _auto_promote_to_agentic(kid: str):
    """
    Called when a memory becomes permanent. Uses llama3.2:3b to generate
    role-specific behavioral instructions for all agent roles and writes
    them to the agentic_ledger.
    """
    try:
        import uuid as _uuid
        import urllib.request, json as _json

        conn = _db()
        row = conn.execute(
            "SELECT entity, entity_type, fact, generalized_truth "
            "FROM company_knowledge WHERE id=?", (kid,)
        ).fetchone()
        # Skip if already promoted for this entity
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM agentic_ledger WHERE source_kid=?", (kid,)
        ).fetchone()
        conn.close()

        if not row or (existing and existing["cnt"] >= len(_AGENTIC_ROLES)):
            return

        truth = row["generalized_truth"] or row["fact"]
        entity = row["entity"]
        etype = row["entity_type"]

        for role in _AGENTIC_ROLES:
            system_ctx = _AGENTIC_ROLE_PROMPTS[role]
            prompt = (
                f"{system_ctx}\n\n"
                f"Entity: '{entity}' (type: {etype})\n"
                f"Established institutional truth: {truth}\n\n"
                f"Output ONLY the instruction text, no labels or preamble."
            )
            body = _json.dumps({
                "model": "llama3.2:3b", "prompt": prompt,
                "stream": False, "options": {"num_predict": 120}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate", data=body, method="POST",
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    instruction = _json.loads(r.read()).get("response", "").strip()
                if not instruction:
                    continue
                iid = str(_uuid.uuid4())
                conn2 = _db()
                conn2.execute(
                    "INSERT OR IGNORE INTO agentic_ledger (id, entity, agent_role, instruction, source_kid) "
                    "VALUES (?,?,?,?,?)",
                    (iid, entity, role, instruction, kid)
                )
                conn2.commit()
                conn2.close()
            except Exception:
                continue
    except Exception:
        pass  # agentic promotion is best-effort


def get_agentic_instructions(entities_in_doc: list[str],
                             agent_role: str) -> list[str]:
    """
    Return behavioral instructions for agents when specific entities appear
    in the current document. Matched by entity name (case-insensitive substring).

    Returns list of instruction strings, sorted by priority DESC.
    """
    _ensure_tables()
    if not entities_in_doc or not agent_role:
        return []
    conn = _db()
    rows = conn.execute(
        "SELECT entity, instruction, priority FROM agentic_ledger "
        "WHERE agent_role=? ORDER BY priority DESC LIMIT 50",
        (agent_role,)
    ).fetchall()
    conn.close()

    doc_entities_lower = {e.lower() for e in entities_in_doc}
    results = []
    seen = set()
    for row in rows:
        ent_lower = row["entity"].lower()
        # Match if the ledger entity appears in any of the doc entities or vice versa
        matched = any(
            ent_lower in doc_ent or doc_ent in ent_lower
            for doc_ent in doc_entities_lower
        )
        if matched and row["instruction"] not in seen:
            seen.add(row["instruction"])
            results.append(row["instruction"])
    return results


# ── SONA ReasoningBank query (expose patterns learned over time) ──────────────

def get_drift_history(limit: int = 20) -> list[dict]:
    """Return recent drift alarms from the log."""
    _ensure_tables()
    conn = _db()
    rows = conn.execute(
        "SELECT doc_name, metric_key, current_value, baseline_value, deviation, alarm, detail, created_at "
        "FROM legatum_drift_log WHERE alarm=1 ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
