"""Long-Term Memory — SuperMemo-style "never forget" system for BlackSwanX.

Architecture
------------
Inspired by how the human brain consolidates memories:

  Working memory   → this document, this session.
  Episodic memory  → this company / this deal (survives across sessions).
  Semantic memory  → permanent firm-wide patterns (never forgotten).

Every fact the system learns from any document is stored here and
strengthened via the SM-2 spaced repetition algorithm each time it is
re-encountered in future documents.  Once a fact's strength crosses the
consolidation threshold (0.75) and has been seen in 3+ documents it becomes
*permanent* — flagged ``is_permanent=True`` and always injected into agent
context when that entity or pattern appears in a new deal.

Why this matters for M&A
------------------------
  • "We analysed Acme Corp 18 months ago — their churn was 12% not the 5%
    they claimed.  We remember that."
  • "This law firm (Skadden) always inserts uncapped IP warranties.  We have
    seen it 4 times.  Flag immediately."
  • "Revenue growth > 30% + customer concentration > 50% correlated with
    post-close NWC dispute in 3 prior deals.  Pattern strength: 0.92."

Memory Types
------------
  entity    — remembered facts about a specific company, person, contract.
  clause    — learned clause patterns (e.g. 'uncapped IP warranty in SaaS').
  pattern   — statistical/correlation patterns across deals.
  advisor   — law firm / bank / auditor behavioural fingerprints.
  red_flag  — proven risk signals from closed deals.

SM-2 Algorithm (SuperMemo)
--------------------------
  quality:  0–5 (how well the fact was confirmed by the new document)
    5 = perfect match / direct confirmation
    4 = correct with minor discrepancy
    3 = correct but hard to find
    2 = wrong answer but close
    1 = wrong answer
    0 = complete blackout / contradiction

  interval update:
    q < 3  → reset repetitions to 0, interval = 1 day
    q >= 3 →
      rep == 0 → interval = 1
      rep == 1 → interval = 6
      rep >= 2 → interval = prev_interval * ease_factor
    ease_factor += 0.1 - (5-q) * (0.08 + (5-q) * 0.02)
    ease_factor = max(1.3, ease_factor)

  strength = min(1.0, repetitions / (repetitions + 2))
  -- approaches 1 asymptotically, never actually reaches it.

Consolidation
-------------
  is_permanent = True when:
    strength >= 0.75
    AND repetitions >= 3
    AND seen in >= 2 distinct documents (doc_count >= 2)

  Permanent memories are NEVER deleted and always retrieved first.
"""

from __future__ import annotations

import json
import math
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from ma.knowledge import get_db


# ─── Schema ──────────────────────────────────────────────────────────────────

def init_ltm_tables() -> None:
    """Create long-term memory tables (idempotent)."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ma_ltm_memories (
            id          TEXT PRIMARY KEY,
            fact_key    TEXT NOT NULL,       -- canonical key for this fact
            fact_type   TEXT NOT NULL,       -- entity|clause|pattern|advisor|red_flag
            memory_tier TEXT DEFAULT 'episodic',  -- working|episodic|semantic
            subject     TEXT NOT NULL,       -- primary entity name
            predicate   TEXT NOT NULL,       -- what we know (e.g. 'churn_pct', 'clause_pattern')
            value       TEXT NOT NULL,       -- JSON value / description
            confidence  REAL DEFAULT 0.8,    -- initial confidence 0-1
            -- SM-2 spaced repetition fields
            strength        REAL    DEFAULT 0.0,
            ease_factor     REAL    DEFAULT 2.5,
            interval_days   REAL    DEFAULT 1.0,
            repetitions     INTEGER DEFAULT 0,
            -- temporal
            first_seen      TEXT DEFAULT (datetime('now')),
            last_seen       TEXT DEFAULT (datetime('now')),
            next_review     TEXT DEFAULT (datetime('now', '+1 day')),
            -- provenance
            source_doc_ids  TEXT DEFAULT '[]',   -- JSON array of ma_documents.id
            source_deals    TEXT DEFAULT '[]',   -- JSON array of deal labels
            doc_count       INTEGER DEFAULT 1,
            -- consolidation
            is_permanent    INTEGER DEFAULT 0,   -- 1 once strength + repetitions threshold met
            -- cross-deal counter
            deal_count      INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_ltm_subject ON ma_ltm_memories(subject);
        CREATE INDEX IF NOT EXISTS idx_ltm_fact_type ON ma_ltm_memories(fact_type);
        CREATE INDEX IF NOT EXISTS idx_ltm_permanent ON ma_ltm_memories(is_permanent);
        CREATE INDEX IF NOT EXISTS idx_ltm_next_review ON ma_ltm_memories(next_review);
        CREATE INDEX IF NOT EXISTS idx_ltm_tier ON ma_ltm_memories(memory_tier);

        CREATE TABLE IF NOT EXISTS ma_ltm_review_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id   TEXT NOT NULL REFERENCES ma_ltm_memories(id),
            reviewed_at TEXT DEFAULT (datetime('now')),
            quality     INTEGER NOT NULL,    -- 0-5 SM-2 quality
            old_strength REAL,
            new_strength REAL,
            old_interval REAL,
            new_interval REAL,
            doc_id      INTEGER,             -- which doc triggered this review
            notes       TEXT
        );
    """)

    # Migrate: add columns if upgrading from older schema
    for col, defn in [
        ("deal_count",   "INTEGER DEFAULT 1"),
        ("memory_tier",  "TEXT DEFAULT 'episodic'"),
        ("doc_count",    "INTEGER DEFAULT 1"),
    ]:
        try:
            conn.execute(f"ALTER TABLE ma_ltm_memories ADD COLUMN {col} {defn}")
        except Exception:
            pass

    conn.commit()
    conn.close()


# ─── SM-2 Core ────────────────────────────────────────────────────────────────

def _sm2_update(
    repetitions: int,
    ease_factor: float,
    interval_days: float,
    quality: int,           # 0-5
) -> tuple[int, float, float, float]:
    """Apply one SM-2 cycle.  Returns (new_reps, new_ef, new_interval, new_strength)."""
    if quality < 3:
        repetitions = 0
        interval_days = 1.0
    else:
        if repetitions == 0:
            interval_days = 1.0
        elif repetitions == 1:
            interval_days = 6.0
        else:
            interval_days = interval_days * ease_factor
        repetitions += 1

    ease_factor = max(1.3, ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

    # Strength: asymptotically approaches 1.0 with repetitions
    # Formula: reps / (reps + 2) gives 0.33, 0.50, 0.60, 0.67, 0.71, 0.75 ... for reps 1-6
    strength = repetitions / (repetitions + 2)

    return repetitions, ease_factor, interval_days, strength


def _make_id(subject: str, predicate: str, fact_type: str) -> str:
    return hashlib.md5(f"{fact_type}:{subject.lower()}:{predicate.lower()}".encode()).hexdigest()[:16]


# ─── Consolidation ────────────────────────────────────────────────────────────

_CONSOLIDATION_STRENGTH    = 0.75   # strength threshold for permanent
_CONSOLIDATION_REPETITIONS = 3      # minimum repetitions
_CONSOLIDATION_DOCS        = 2      # seen in at least N distinct documents


def _maybe_consolidate(conn, memory_id: str) -> bool:
    """Promote a memory to permanent if thresholds are met.  Returns True if promoted."""
    row = conn.execute(
        "SELECT strength, repetitions, doc_count, is_permanent FROM ma_ltm_memories WHERE id=?",
        (memory_id,),
    ).fetchone()
    if not row or row["is_permanent"]:
        return False

    if (row["strength"] >= _CONSOLIDATION_STRENGTH
            and row["repetitions"] >= _CONSOLIDATION_REPETITIONS
            and (row["doc_count"] >= _CONSOLIDATION_DOCS
                 or row["deal_count"] >= _CONSOLIDATION_DOCS)):
        conn.execute(
            "UPDATE ma_ltm_memories SET is_permanent=1, memory_tier='semantic' WHERE id=?",
            (memory_id,),
        )
        return True
    return False


# ─── Write path ──────────────────────────────────────────────────────────────

def consolidate_memory(
    subject: str,
    predicate: str,
    value: object,
    fact_type: str = "entity",
    confidence: float = 0.8,
    doc_id: Optional[int] = None,
    deal_label: Optional[str] = None,
    quality: int = 4,
) -> dict:
    """Record or reinforce a fact.

    Call this every time the system learns (or re-confirms) a fact from a
    document.  If the fact already exists its SM-2 counter is updated,
    strength grows, and it may be promoted to permanent memory.

    Parameters
    ----------
    subject     Entity name (company / person / clause label).
    predicate   What is known ('revenue_claimed', 'churn_pct', 'has_uncapped_ip_warranty').
    value       The actual value — will be JSON-serialised.
    fact_type   One of entity|clause|pattern|advisor|red_flag.
    confidence  Initial confidence in this fact (0-1).
    doc_id      Source document ID (for provenance).
    deal_label  Human-readable deal name (e.g. 'Acme-Acquisition-2024').
    quality     SM-2 quality score 0-5.  Use 5 for direct re-confirmation,
                3 for indirect corroboration, 2 for mild contradiction.

    Returns a dict with the memory state after update.
    """
    init_ltm_tables()
    conn = get_db()

    mem_id = _make_id(subject, predicate, fact_type)
    value_str = json.dumps(value) if not isinstance(value, str) else value
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        "SELECT * FROM ma_ltm_memories WHERE id=?", (mem_id,)
    ).fetchone()

    if existing is None:
        # First encounter — insert at working/episodic tier
        reps, ef, interval, strength = _sm2_update(0, 2.5, 1.0, quality)
        next_review = (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat()
        tier = "working"

        conn.execute(
            """INSERT INTO ma_ltm_memories
               (id, fact_key, fact_type, memory_tier, subject, predicate, value,
                confidence, strength, ease_factor, interval_days, repetitions,
                first_seen, last_seen, next_review,
                source_doc_ids, source_deals, doc_count, is_permanent, deal_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,1)""",
            (mem_id, f"{fact_type}:{subject}:{predicate}", fact_type, tier,
             subject, predicate, value_str, confidence,
             strength, ef, interval, reps,
             now, now, next_review,
             json.dumps([doc_id] if doc_id else []),
             json.dumps([deal_label] if deal_label else [])),
        )
        promoted = False
    else:
        # Re-encounter — apply SM-2
        reps, ef, interval, strength = _sm2_update(
            existing["repetitions"], existing["ease_factor"],
            existing["interval_days"], quality,
        )
        next_review = (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat()

        # Update source provenance
        old_docs = json.loads(existing["source_doc_ids"] or "[]")
        old_deals = json.loads(existing["source_deals"] or "[]")
        if doc_id and doc_id not in old_docs:
            old_docs.append(doc_id)
        if deal_label and deal_label not in old_deals:
            old_deals.append(deal_label)

        # Escalate tier
        tier = existing["memory_tier"]
        if tier == "working" and reps >= 2:
            tier = "episodic"

        conn.execute(
            """UPDATE ma_ltm_memories
               SET strength=?, ease_factor=?, interval_days=?, repetitions=?,
                   last_seen=?, next_review=?,
                   source_doc_ids=?, source_deals=?,
                   doc_count=?, memory_tier=?,
                   value=?
               WHERE id=?""",
            (strength, ef, interval, reps,
             now, next_review,
             json.dumps(old_docs), json.dumps(old_deals),
             len(old_docs), tier,
             value_str,
             mem_id),
        )
        promoted = _maybe_consolidate(conn, mem_id)

        # Log the review
        conn.execute(
            """INSERT INTO ma_ltm_review_log
               (memory_id, quality, old_strength, new_strength,
                old_interval, new_interval, doc_id)
               VALUES (?,?,?,?,?,?,?)""",
            (mem_id, quality,
             existing["strength"], strength,
             existing["interval_days"], interval,
             doc_id),
        )

    conn.commit()

    final = conn.execute("SELECT * FROM ma_ltm_memories WHERE id=?", (mem_id,)).fetchone()
    conn.close()

    return {
        "id": mem_id,
        "subject": subject,
        "predicate": predicate,
        "strength": round(strength, 3),
        "repetitions": reps,
        "is_permanent": bool(final["is_permanent"]),
        "memory_tier": final["memory_tier"],
        "promoted_to_permanent": promoted,
    }


# ─── Read path ────────────────────────────────────────────────────────────────

def recall(
    entity_names: list[str],
    fact_types: Optional[list[str]] = None,
    min_strength: float = 0.3,
    limit: int = 20,
    permanent_only: bool = False,
) -> list[dict]:
    """Retrieve relevant memories for the given entity names.

    Permanent memories (is_permanent=1) are always returned first.
    Results are ordered by strength DESC so the most-reinforced facts
    surface at the top.

    Parameters
    ----------
    entity_names    Entity names to search (fuzzy LIKE match).
    fact_types      Filter by type(s) — None means all types.
    min_strength    Only return memories at or above this strength (0-1).
    limit           Maximum results.
    permanent_only  If True, only return consolidated permanent memories.
    """
    init_ltm_tables()
    if not entity_names:
        return []

    conn = get_db()

    like_clauses = " OR ".join("LOWER(subject) LIKE ?" for _ in entity_names)
    params: list = [f"%{n.lower()}%" for n in entity_names]

    type_clause = ""
    if fact_types:
        type_clause = f"AND fact_type IN ({','.join('?' * len(fact_types))})"
        params += fact_types

    perm_clause = "AND is_permanent=1" if permanent_only else ""
    params += [min_strength, limit]

    rows = conn.execute(
        f"""SELECT id, fact_type, memory_tier, subject, predicate, value,
                   strength, repetitions, confidence, is_permanent,
                   first_seen, last_seen, source_deals, doc_count
            FROM ma_ltm_memories
            WHERE ({like_clauses})
              {type_clause}
              {perm_clause}
              AND strength >= ?
            ORDER BY is_permanent DESC, strength DESC
            LIMIT ?""",
        params,
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def recall_as_context_block(
    entity_names: list[str],
    min_strength: float = 0.3,
    limit: int = 15,
) -> str:
    """Format recalled memories as a text block for LLM injection.

    Returns a formatted string ready to prepend to agent prompts.
    Empty string if nothing relevant is remembered.

    Example output::

        [LONG-TERM MEMORY — facts learned from prior deals, never forgotten]
        ★ PERMANENT  Acme Corp | churn_pct: "12.3% actual vs 5% claimed in CIM"
                     (strength: 0.91, seen 5 docs, 3 deals — entity)
        ◆ STRONG     Skadden | uncapped_ip_warranty: "Always inserts uncapped IP warranty in SaaS deals"
                     (strength: 0.78, seen 4 docs — advisor)
        ○ KNOWN      Revenue Growth >30% | nwc_dispute_risk: "Correlated with post-close NWC dispute"
                     (strength: 0.50, seen 2 docs — pattern)
    """
    memories = recall(entity_names, min_strength=min_strength, limit=limit)
    if not memories:
        return ""

    lines = ["[LONG-TERM MEMORY — facts learned from prior deals, never forgotten]"]
    for m in memories:
        if m["is_permanent"]:
            marker = "★ PERMANENT "
        elif m["strength"] >= 0.6:
            marker = "◆ STRONG    "
        else:
            marker = "○ KNOWN     "

        try:
            val = json.loads(m["value"])
            if isinstance(val, dict):
                val_str = "; ".join(f"{k}: {v}" for k, v in list(val.items())[:3])
            else:
                val_str = str(val)
        except Exception:
            val_str = str(m["value"])

        deals = json.loads(m["source_deals"] or "[]")
        deal_note = f", {len(deals)} deal(s)" if deals else ""

        lines.append(
            f"  {marker}{m['subject']} | {m['predicate']}: \"{val_str[:120]}\"\n"
            f"           (strength: {m['strength']:.2f}, seen {m['doc_count']} doc(s)"
            f"{deal_note} — {m['fact_type']})"
        )

    return "\n".join(lines)


# ─── Auto-extract from KG ─────────────────────────────────────────────────────

def extract_and_consolidate_from_doc(
    doc_id: int,
    deal_label: Optional[str] = None,
    quality: int = 4,
) -> dict:
    """Auto-extract high-confidence facts from an ingested document and consolidate.

    Pulls high-confidence KG nodes + facts from ``ma_facts`` and feeds them
    into the LTM.  Call this after ``update_graph_for_doc(doc_id)``.

    Returns a summary dict.
    """
    init_ltm_tables()
    conn = get_db()

    # Pull high-confidence KG nodes for this document
    kg_nodes = conn.execute(
        """SELECT name, entity_type, canonical_name, confidence, properties
           FROM ma_kg_nodes
           WHERE (doc_ids LIKE ? OR doc_ids LIKE ?)
             AND confidence >= 0.7
             AND merged_into IS NULL
             AND is_latest = 1
           LIMIT 200""",
        (f'[{doc_id}%', f'%,{doc_id}%'),
    ).fetchall()

    # Pull structured facts from ma_facts
    try:
        ma_facts = conn.execute(
            "SELECT fact_type, subject, predicate, value, confidence FROM ma_facts WHERE doc_id=? LIMIT 200",
            (doc_id,),
        ).fetchall()
    except Exception:
        ma_facts = []

    conn.close()

    consolidated = 0
    promoted = 0

    # Consolidate KG nodes as entity memories
    for node in kg_nodes:
        try:
            props = json.loads(node["properties"] or "{}")
        except Exception:
            props = {}

        name = node["canonical_name"] or node["name"]
        etype = node["entity_type"]

        # Store the entity existence as a memory
        result = consolidate_memory(
            subject=name,
            predicate=f"is_{etype.lower()}",
            value={"entity_type": etype, "confidence": node["confidence"]},
            fact_type="entity",
            confidence=node["confidence"],
            doc_id=doc_id,
            deal_label=deal_label,
            quality=quality,
        )
        consolidated += 1
        if result["promoted_to_permanent"]:
            promoted += 1

        # Store each property as a separate memory
        for k, v in props.items():
            if v is None or str(v).strip() == "":
                continue
            consolidate_memory(
                subject=name,
                predicate=k,
                value=v,
                fact_type="entity",
                confidence=node["confidence"],
                doc_id=doc_id,
                deal_label=deal_label,
                quality=quality,
            )
            consolidated += 1

    # Consolidate structured facts from ma_facts
    for fact in ma_facts:
        try:
            result = consolidate_memory(
                subject=fact["subject"] or "",
                predicate=fact["predicate"] or fact["fact_type"] or "fact",
                value=fact["value"] or "",
                fact_type="entity",
                confidence=fact["confidence"] or 0.7,
                doc_id=doc_id,
                deal_label=deal_label,
                quality=quality,
            )
            consolidated += 1
            if result["promoted_to_permanent"]:
                promoted += 1
        except Exception:
            pass

    return {
        "doc_id": doc_id,
        "memories_consolidated": consolidated,
        "promoted_to_permanent": promoted,
        "deal_label": deal_label,
    }


# ─── Pattern learning ─────────────────────────────────────────────────────────

def learn_pattern(
    pattern_name: str,
    description: str,
    trigger_entities: list[str],
    outcome: str,
    doc_id: Optional[int] = None,
    deal_label: Optional[str] = None,
    quality: int = 4,
) -> dict:
    """Record a cross-deal pattern as a semantic memory.

    Used when an agent detects a recurring correlation across deals.

    Example::

        learn_pattern(
            "high_growth_nwc_risk",
            "Revenue growth > 30% + customer concentration > 50%",
            trigger_entities=["HighGrowthSaaS", "CustomerConcentration"],
            outcome="Correlated with post-close NWC dispute in 3 prior deals",
        )
    """
    return consolidate_memory(
        subject=pattern_name,
        predicate="pattern",
        value={"description": description, "triggers": trigger_entities, "outcome": outcome},
        fact_type="pattern",
        confidence=0.85,
        doc_id=doc_id,
        deal_label=deal_label,
        quality=quality,
    )


def learn_advisor_fingerprint(
    firm_name: str,
    behaviour: str,
    clause_type: str,
    doc_id: Optional[int] = None,
    deal_label: Optional[str] = None,
) -> dict:
    """Record a law firm / advisor behavioural fingerprint.

    Example::

        learn_advisor_fingerprint(
            "Skadden",
            "Always inserts uncapped IP warranty in SaaS acquisition SPAs",
            clause_type="ip_warranty",
        )
    """
    return consolidate_memory(
        subject=firm_name,
        predicate=clause_type,
        value=behaviour,
        fact_type="advisor",
        confidence=0.9,
        doc_id=doc_id,
        deal_label=deal_label,
        quality=4,
    )


# ─── Stats & introspection ────────────────────────────────────────────────────

def memory_stats() -> dict:
    """Return a summary of the long-term memory state."""
    init_ltm_tables()
    conn = get_db()

    stats = {}
    stats["total"] = conn.execute("SELECT COUNT(*) FROM ma_ltm_memories").fetchone()[0]
    stats["permanent"] = conn.execute(
        "SELECT COUNT(*) FROM ma_ltm_memories WHERE is_permanent=1"
    ).fetchone()[0]
    stats["by_tier"] = {
        row["memory_tier"]: row["cnt"]
        for row in conn.execute(
            "SELECT memory_tier, COUNT(*) as cnt FROM ma_ltm_memories GROUP BY memory_tier"
        ).fetchall()
    }
    stats["by_type"] = {
        row["fact_type"]: row["cnt"]
        for row in conn.execute(
            "SELECT fact_type, COUNT(*) as cnt FROM ma_ltm_memories GROUP BY fact_type"
        ).fetchall()
    }
    stats["avg_strength"] = conn.execute(
        "SELECT ROUND(AVG(strength),3) FROM ma_ltm_memories"
    ).fetchone()[0] or 0.0
    stats["strongest"] = [
        dict(r) for r in conn.execute(
            """SELECT subject, predicate, strength, repetitions, is_permanent, fact_type
               FROM ma_ltm_memories ORDER BY strength DESC LIMIT 10"""
        ).fetchall()
    ]
    stats["due_for_review"] = conn.execute(
        "SELECT COUNT(*) FROM ma_ltm_memories WHERE next_review <= datetime('now') AND is_permanent=0"
    ).fetchone()[0]

    conn.close()
    return stats


def get_permanent_memories() -> list[dict]:
    """Return all permanent (fully consolidated) memories, ordered by strength."""
    init_ltm_tables()
    conn = get_db()
    rows = conn.execute(
        """SELECT subject, predicate, value, strength, repetitions,
                  fact_type, memory_tier, first_seen, last_seen, source_deals
           FROM ma_ltm_memories
           WHERE is_permanent=1
           ORDER BY strength DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_memories_due_for_review(limit: int = 50) -> list[dict]:
    """Return memories whose next_review date has passed — ready for SM-2 re-scoring."""
    init_ltm_tables()
    conn = get_db()
    rows = conn.execute(
        """SELECT id, subject, predicate, value, fact_type,
                  strength, repetitions, ease_factor, interval_days, next_review
           FROM ma_ltm_memories
           WHERE next_review <= datetime('now')
             AND is_permanent = 0
           ORDER BY next_review ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
