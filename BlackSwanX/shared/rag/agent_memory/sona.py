"""
SONA — Self-Optimizing Neural Architecture (Python port)
=========================================================
Based on @ruvector/sona@0.1.1 concepts, adapted for the LEGATUM
RAG pipeline (Python + Ollama, no Node.js dependency).

THREE CORE MECHANISMS
─────────────────────
1. EWC++ (Elastic Weight Consolidation++)
   Tracks "importance" for every memory item so high-value facts are
   protected from being overwritten or decayed out.
   Importance proxy = Σ (quality × access_frequency) normalised to [0,1].
   Protected items require quality < ewc_floor before SM-2 resets.

2. Pattern Library (k-NN retrieval, k=3)
   Every successful query-run is stored as a pattern:
     (query_fingerprint, pipeline_config, quality_score)
   At query time, the k=3 most similar past patterns are retrieved
   and the best-scoring config is reused (skip steps that didn't help).

3. LLM Router
   Routes each query to the cheapest Ollama model that should handle it:
     FAST  = llama3.2:3b   — simple factual / yes-no
     MID   = qwen2.5-coder:7b — structured extraction / entity check
     MAIN  = phi4:14b      — complex reasoning / synthesis
   Router learns from past routing decisions (quality × cost).

USAGE
─────
    from agent_memory.sona import SonaOptimizer

    sona = SonaOptimizer()

    # Pre-task hook
    plan = sona.pre_task(query)
    # → {"model": "phi4:14b", "skip_visual": False, "top_k": 6, ...}

    # Post-task hook
    sona.post_task(query, answer, verdict, score, elapsed_s, plan)

    # EWC++ protect an entity
    sona.ewc_protect("aia", quality=5, access_count=12)

    # Query EWC importance (used by SemanticMemory to guard resets)
    imp = sona.ewc_importance("aia")   # 0.0 – 1.0

    # Pattern stats
    sona.stats()
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .ledgers import _conn, DEFAULT_EASE, sm2_update, forgetting_curve

# ─────────────────────────────────────────────────────────────────────────────
# Paths + constants
# ─────────────────────────────────────────────────────────────────────────────

BASE      = Path(__file__).parent.parent
SONA_DB   = BASE / "data" / "sona.db"

# EWC++
EWC_LAMBDA    = 0.4     # weight of importance penalty (0=off, 1=full protection)
EWC_FLOOR     = 0.6     # items with importance > this need quality >= 3 to reset
EWC_DECAY     = 0.98    # importance decays slightly each update (prevents lock-in)

# Pattern library
PATTERN_K     = 3       # k-nearest patterns to retrieve
PATTERN_SIM_THRESHOLD = 0.15   # min Jaccard to count as a match

# LLM router thresholds
FAST_MODEL  = "llama3.2:3b"
MID_MODEL   = "qwen2.5-coder:7b"
MAIN_MODEL  = "phi4:14b"

FAST_COST   = 1.0    # relative cost unit
MID_COST    = 4.0
MAIN_COST   = 12.0

# Quality improvement cap per SONA spec (+55% max)
QUALITY_CAP = 0.55

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity (German-aware, min 3-char tokens)."""
    sa = set(w for w in re.split(r'\W+', a.lower()) if len(w) >= 3)
    sb = set(w for w in re.split(r'\W+', b.lower()) if len(w) >= 3)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _query_complexity(query: str) -> float:
    """
    Heuristic complexity 0.0–1.0.
    Short factual queries → low; multi-part / 'warum' / 'erkläre' → high.
    """
    q = query.lower()
    words = len(q.split())
    high_markers = sum(q.count(w) for w in
                       ("warum", "erkläre", "vergleiche", "beschreibe",
                        "wie unterscheidet", "welche schritte", "erläutere",
                        "stufenplan", "zusammenfassung", "why", "explain",
                        "compare", "how does", "what are the steps"))
    low_markers  = sum(q.count(w) for w in
                       ("was ist", "wer", "wann", "welche", "wie viele",
                        "what is", "who", "when", "how many", "list"))
    score = min(1.0, words / 30 + high_markers * 0.25 - low_markers * 0.1)
    return max(0.0, score)


# ─────────────────────────────────────────────────────────────────────────────
# SONA DB schema
# ─────────────────────────────────────────────────────────────────────────────

def _init_sona_db(db: Path):
    c = _conn(db)
    c.executescript("""
        -- EWC++ importance table
        CREATE TABLE IF NOT EXISTS ewc_importance (
            name_key    TEXT PRIMARY KEY,
            importance  REAL DEFAULT 0.0,    -- 0.0 – 1.0
            access_count INTEGER DEFAULT 0,
            quality_sum  REAL DEFAULT 0.0,
            last_updated TEXT NOT NULL
        );

        -- Pattern library
        CREATE TABLE IF NOT EXISTS patterns (
            id            TEXT PRIMARY KEY,
            query_text    TEXT NOT NULL,
            pipeline_cfg  TEXT NOT NULL,    -- JSON pipeline configuration used
            quality_score REAL DEFAULT 0.0,
            elapsed_s     REAL DEFAULT 0.0,
            verdict       TEXT DEFAULT '',
            created_at    TEXT NOT NULL
        );

        -- LLM routing decisions
        CREATE TABLE IF NOT EXISTS routing_log (
            id            INTEGER PRIMARY KEY,
            query_text    TEXT NOT NULL,
            complexity    REAL NOT NULL,
            model_used    TEXT NOT NULL,
            quality_score REAL DEFAULT 0.0,
            cost_unit     REAL DEFAULT 0.0,
            created_at    TEXT NOT NULL
        );

        -- Quality trajectory (rolling window)
        CREATE TABLE IF NOT EXISTS quality_trajectory (
            id         INTEGER PRIMARY KEY,
            domain     TEXT DEFAULT 'general',
            score      REAL NOT NULL,
            baseline   REAL DEFAULT 0.45,   -- phase-1 baseline
            improvement REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS pat_quality ON patterns(quality_score DESC);
        CREATE INDEX IF NOT EXISTS ewc_imp     ON ewc_importance(importance DESC);
    """)
    c.commit()
    c.close()


# ─────────────────────────────────────────────────────────────────────────────
# SONA Optimizer
# ─────────────────────────────────────────────────────────────────────────────

class SonaOptimizer:
    """
    SONA self-optimizing layer.  Wraps the memory stack and gives
    pre_task / post_task hooks (matching the @ruvector/sona API).
    """

    def __init__(self, db_path: Path = SONA_DB):
        self._db = db_path
        _init_sona_db(db_path)

    # ── EWC++ ────────────────────────────────────────────────────────────────

    def ewc_protect(self, name_key: str, quality: int,
                    access_count: int = 1):
        """
        Update EWC++ importance for a memory item.
        importance = decay × old_importance + (quality/5) × log(1 + access_count)
        Normalised to [0, 1].
        """
        nk = name_key.strip().lower()
        c  = _conn(self._db)
        row = c.execute(
            "SELECT importance, access_count, quality_sum FROM ewc_importance WHERE name_key=?",
            (nk,),
        ).fetchone()
        now = datetime.utcnow().isoformat()

        q_norm     = quality / 5.0
        log_access = math.log1p(access_count)

        if row:
            old_imp  = row["importance"]
            new_acc  = row["access_count"] + access_count
            new_qsum = row["quality_sum"]  + q_norm
            new_imp  = min(1.0,
                           EWC_DECAY * old_imp + q_norm * math.log1p(new_acc) / 5.0)
            c.execute(
                "UPDATE ewc_importance SET importance=?,access_count=?,quality_sum=?,"
                "last_updated=? WHERE name_key=?",
                (new_imp, new_acc, new_qsum, now, nk),
            )
        else:
            new_imp = min(1.0, q_norm * log_access / 5.0)
            c.execute(
                "INSERT INTO ewc_importance(name_key,importance,access_count,quality_sum,last_updated)"
                " VALUES(?,?,?,?,?)",
                (nk, new_imp, access_count, q_norm, now),
            )
        c.commit()
        c.close()
        return new_imp

    def ewc_importance(self, name_key: str) -> float:
        """Return current EWC++ importance for a memory item (0.0 – 1.0)."""
        c   = _conn(self._db)
        row = c.execute(
            "SELECT importance FROM ewc_importance WHERE name_key=?",
            (name_key.strip().lower(),),
        ).fetchone()
        c.close()
        return float(row["importance"]) if row else 0.0

    def ewc_allows_reset(self, name_key: str, quality: int) -> bool:
        """
        Returns True if SM-2 reset is allowed for this item.
        High-importance items are protected: quality must be < EWC_FLOOR·5
        to override protection (i.e. a really bad failure still resets).
        """
        imp = self.ewc_importance(name_key)
        if imp < EWC_FLOOR:
            return True   # not important enough to protect
        # Protected: only reset if quality is truly catastrophic (0-1)
        return quality <= 1

    def ewc_top(self, n: int = 10) -> list[dict]:
        """Top-n most important entities (most protected)."""
        c   = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM ewc_importance ORDER BY importance DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    # ── Pattern Library ──────────────────────────────────────────────────────

    def save_pattern(self, query: str, pipeline_cfg: dict,
                     quality_score: float, elapsed_s: float,
                     verdict: str = ""):
        """Store a completed run as a learnable pattern."""
        c   = _conn(self._db)
        pid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        c.execute(
            "INSERT INTO patterns(id,query_text,pipeline_cfg,quality_score,"
            "elapsed_s,verdict,created_at) VALUES(?,?,?,?,?,?,?)",
            (pid, query, json.dumps(pipeline_cfg, ensure_ascii=False),
             quality_score, elapsed_s, verdict, now),
        )
        c.commit()
        c.close()
        return pid

    def retrieve_patterns(self, query: str,
                          k: int = PATTERN_K) -> list[dict]:
        """
        k-NN pattern retrieval by Jaccard similarity on query tokens.
        Returns k best patterns with their pipeline configs.
        """
        c    = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM patterns WHERE quality_score > 0.5 ORDER BY quality_score DESC LIMIT 100"
        ).fetchall()
        c.close()

        scored = []
        for r in rows:
            sim = _jaccard(query, r["query_text"])
            if sim >= PATTERN_SIM_THRESHOLD:
                scored.append({**dict(r), "_sim": sim})

        scored.sort(key=lambda x: x["_sim"] * x["quality_score"], reverse=True)
        return scored[:k]

    def best_pipeline_config(self, query: str) -> dict:
        """
        Retrieve the best known pipeline config for similar past queries.
        Returns empty dict if no good pattern found (use defaults).
        """
        patterns = self.retrieve_patterns(query, k=PATTERN_K)
        if not patterns:
            return {}

        # Weighted merge of top-k configs
        best = patterns[0]
        cfg  = json.loads(best.get("pipeline_cfg") or "{}")
        sim  = best["_sim"]
        q    = best["quality_score"]

        # Only trust it if similarity is reasonable
        if sim < 0.25 or q < 0.6:
            return {}

        return cfg

    # ── LLM Router ───────────────────────────────────────────────────────────

    def route_model(self, query: str, force: str | None = None) -> str:
        """
        Select the cheapest Ollama model likely to handle this query correctly.
        Learns from past routing decisions.

        Returns model name string.
        """
        if force:
            return force

        complexity = _query_complexity(query)

        # Check past routing decisions for similar queries
        c    = _conn(self._db)
        past = c.execute(
            "SELECT model_used, quality_score, complexity FROM routing_log"
            " WHERE quality_score > 0.6 ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        c.close()

        # Build per-model quality averages from learned history
        model_scores: dict[str, list[float]] = {}
        for row in past:
            complexity_diff = abs(row["complexity"] - complexity)
            if complexity_diff < 0.3:   # similar complexity queries
                m = row["model_used"]
                model_scores.setdefault(m, []).append(float(row["quality_score"]))

        model_avg = {m: sum(v)/len(v) for m, v in model_scores.items() if v}

        # Cost-quality tradeoff: pick cheapest model with avg quality >= 0.7
        if complexity < 0.3:
            # Simple query — prefer FAST
            if model_avg.get(FAST_MODEL, 0) >= 0.65:
                return FAST_MODEL
            if model_avg.get(MID_MODEL, 0) >= 0.70:
                return MID_MODEL

        if complexity < 0.65:
            # Medium — prefer MID
            if model_avg.get(MID_MODEL, 0) >= 0.70:
                return MID_MODEL

        # Complex or unknown — use MAIN
        return MAIN_MODEL

    def log_routing(self, query: str, model: str,
                    quality_score: float, elapsed_s: float = 0.0):
        complexity = _query_complexity(query)
        cost = {FAST_MODEL: FAST_COST, MID_MODEL: MID_COST,
                MAIN_MODEL: MAIN_COST}.get(model, MID_COST)
        c = _conn(self._db)
        c.execute(
            "INSERT INTO routing_log(query_text,complexity,model_used,"
            "quality_score,cost_unit,created_at) VALUES(?,?,?,?,?,?)",
            (query, complexity, model, quality_score, cost,
             datetime.utcnow().isoformat()),
        )
        c.commit()
        c.close()

    # ── Pre / Post Task hooks (matching @ruvector/sona API) ──────────────────

    def pre_task(self, query: str) -> dict:
        """
        Pre-task hook.  Returns an optimised pipeline plan:
          {
            "model": str,
            "skip_visual": bool,
            "skip_graph": bool,
            "top_k_chunks": int,
            "top_k_visual": int,
            "pattern_match": bool,
            "complexity": float,
            "pattern_cfg": dict,
          }
        """
        t0 = time.perf_counter()

        model   = self.route_model(query)
        cfg     = self.best_pipeline_config(query)
        compl   = _query_complexity(query)

        plan = {
            "model":          cfg.get("model", model),
            "skip_visual":    cfg.get("skip_visual", compl < 0.2),
            "skip_graph":     cfg.get("skip_graph", False),
            "top_k_chunks":   cfg.get("top_k_chunks", 6 if compl > 0.5 else 4),
            "top_k_visual":   cfg.get("top_k_visual", 5 if compl > 0.5 else 3),
            "pattern_match":  bool(cfg),
            "complexity":     round(compl, 3),
            "pattern_cfg":    cfg,
            "_overhead_ms":   round((time.perf_counter() - t0) * 1000, 3),
        }
        return plan

    def post_task(self, query: str, answer: str, verdict: str,
                  score: float, elapsed_s: float, plan: dict):
        """
        Post-task hook.  Records the run and updates all learning structures.
        Maps to SONA 'record trajectory + LoRA-equivalent update'.
        """
        # 1. Save pattern
        pipeline_cfg = {k: v for k, v in plan.items()
                        if not k.startswith("_") and k != "pattern_cfg"}
        pipeline_cfg["model"] = plan.get("model", MAIN_MODEL)
        pipeline_cfg["quality_score"] = score
        self.save_pattern(query, pipeline_cfg, score, elapsed_s, verdict)

        # 2. Log routing decision
        self.log_routing(query, plan.get("model", MAIN_MODEL),
                         score, elapsed_s)

        # 3. Quality trajectory
        baseline  = 0.45   # phase-1 baseline
        improvement = min(QUALITY_CAP, max(0.0, (score - baseline) / max(baseline, 0.01)))
        c = _conn(self._db)
        c.execute(
            "INSERT INTO quality_trajectory(domain,score,baseline,improvement,created_at)"
            " VALUES(?,?,?,?,?)",
            ("general", score, baseline, improvement,
             datetime.utcnow().isoformat()),
        )
        c.commit()
        c.close()

    # ── Quality Trajectory ────────────────────────────────────────────────────

    def quality_improvement(self, last_n: int = 20) -> dict:
        """
        Rolling improvement over last_n runs vs phase-1 baseline.
        Caps at +55% per SONA spec.
        """
        c    = _conn(self._db)
        rows = c.execute(
            "SELECT score, baseline, improvement, created_at FROM quality_trajectory"
            " ORDER BY created_at DESC LIMIT ?", (last_n,)
        ).fetchall()
        c.close()

        if not rows:
            return {"runs": 0, "avg_score": 0.0, "avg_improvement": 0.0,
                    "max_improvement": 0.0, "trend": "no data"}

        scores = [r["score"] for r in rows]
        imps   = [r["improvement"] for r in rows]
        avg_s  = sum(scores) / len(scores)
        avg_i  = sum(imps)   / len(imps)
        max_i  = max(imps)

        # Trend: compare first-half vs second-half
        mid = max(1, len(scores) // 2)
        trend_delta = sum(scores[:mid]) / mid - sum(scores[mid:]) / max(len(scores) - mid, 1)
        trend = "improving" if trend_delta > 0.02 else \
                "declining"  if trend_delta < -0.02 else "stable"

        return {
            "runs": len(rows),
            "avg_score": round(avg_s, 3),
            "avg_improvement": round(avg_i * 100, 1),   # as %
            "max_improvement": round(max_i * 100, 1),   # as %
            "trend": trend,
            "baseline": 0.45,
        }

    # ── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        c = _conn(self._db)
        patterns  = c.execute("SELECT count(*) FROM patterns").fetchone()[0]
        ewc_items = c.execute("SELECT count(*) FROM ewc_importance").fetchone()[0]
        routes    = c.execute("SELECT count(*) FROM routing_log").fetchone()[0]
        fast_pct  = 0.0
        if routes:
            fast = c.execute(
                f"SELECT count(*) FROM routing_log WHERE model_used=?",
                (FAST_MODEL,),
            ).fetchone()[0]
            fast_pct = round(fast / routes * 100, 1)
        c.close()
        qi = self.quality_improvement()
        return {
            "patterns_stored": patterns,
            "ewc_items": ewc_items,
            "routing_decisions": routes,
            "fast_model_pct": fast_pct,
            "quality": qi,
        }
