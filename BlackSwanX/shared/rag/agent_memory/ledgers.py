"""
LEGATUM Memory Layers
=======================
Four stores, all SQLite-backed (no Docker required).

SCHEDULING MODEL
  • SM-2 algorithm    — governs review interval per memory item
  • Ebbinghaus curve  — R(t) = e^(−t / S)   decay score at query time
                        t = days since last access   S = SM-2 stability (interval)

  Combined retrieval score  =  R(t) × ease_factor_norm × importance
  Items with score < DECAY_FLOOR are archived, not deleted.

STORES
  1. EpisodicLedger   — append-only log of every query session
  2. AgenticMemory    — per-agent session scratchpad + SM-2 scheduled items
  3. CompanyMemory    — org-level knowledge injected into every query
  4. SemanticMemory   — overlay on top of the graph (entity reinforcement scores)

USAGE
  from agent_memory.ledgers import EpisodicLedger, AgenticMemory, CompanyMemory, SemanticMemory

  ep  = EpisodicLedger()
  am  = AgenticMemory(agent_id="bim_expert")
  cm  = CompanyMemory()
  sm  = SemanticMemory()

  # Log a session
  sid = ep.open_session(query="Was ist AIA?")
  ep.close_session(sid, answer="...", verdict="correct", score=0.9)

  # SM-2 update (quality 0-5: 5=perfect recall, 0=blackout)
  sm.update_entity("aia", quality=5)

  # Retrieve company context for a query
  ctx = cm.retrieve("Welche Rollen gibt es?", top_k=3)
"""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

BASE       = Path(__file__).parent.parent
LEDGER_DB  = BASE / "data" / "ledgers.db"
COMPANY_DB = BASE / "data" / "company_memory.db"
GRAPH_DB   = BASE / "data" / "legatum_complete.db"   # SemanticMemory overlay

DECAY_FLOOR = 0.10   # items below this R(t) score are "cold" — still retrievable but ranked last

# ─────────────────────────────────────────────────────────────────────────────
# SM-2  +  Ebbinghaus forgetting curve
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_EASE    = 2.5    # starting ease factor (SM-2 default)
DEFAULT_INTERVAL = 1     # days
MIN_EASE        = 1.3


def sm2_update(ease: float, interval: int, reps: int,
               quality: int) -> tuple[float, int, int, datetime]:
    """
    SM-2 algorithm update.
    quality  0-2 → failed (reset)   3 → pass   4 → good   5 → perfect
    Returns  (new_ease, new_interval, new_reps, next_review_datetime)
    """
    if quality < 3:
        reps     = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, min(round(interval * ease), 36500))  # cap at 100 years
        reps += 1
    ease = max(MIN_EASE,
               ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    next_review = datetime.utcnow() + timedelta(days=interval)
    return ease, interval, reps, next_review


def forgetting_curve(last_accessed: datetime, stability: float) -> float:
    """
    Ebbinghaus R(t) = e^(−t / S)
    t = days since last_accessed   S = stability (SM-2 interval in days, min 1)
    Returns 0.0 – 1.0  (1.0 = perfectly fresh)
    """
    if stability <= 0:
        stability = 1.0
    elapsed_days = max(0.0, (datetime.utcnow() - last_accessed).total_seconds() / 86400)
    return math.exp(-elapsed_days / stability)


def retrieval_score(row: dict) -> float:
    """Combined score used to rank memories at query time."""
    last = _parse_dt(row.get("last_accessed") or row.get("created_at", ""))
    stab = float(row.get("sm2_interval") or 1)
    ease = float(row.get("sm2_ease") or DEFAULT_EASE)
    imp  = float(row.get("importance") or 1)
    R    = forgetting_curve(last, stab)
    return R * (ease / DEFAULT_EASE) * imp


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow() - timedelta(days=365)  # very old if unset


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _conn(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


# ─────────────────────────────────────────────────────────────────────────────
# 1. EPISODIC LEDGER
# ─────────────────────────────────────────────────────────────────────────────

class EpisodicLedger:
    """
    Append-only log of every answered query.

    Schema
    ------
    episodes  — one row per query session
    episode_steps  — one row per pipeline step inside a session
    """

    def __init__(self, db_path: Path = LEDGER_DB):
        self._db = db_path
        self._init()

    def _init(self):
        c = _conn(self._db)
        c.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id           TEXT PRIMARY KEY,
                query        TEXT NOT NULL,
                answer       TEXT DEFAULT '',
                verdict      TEXT DEFAULT '',   -- correct/partial/incorrect/error
                score        REAL DEFAULT 0,
                doc_id       TEXT DEFAULT '',
                sources      TEXT DEFAULT '[]', -- JSON list of pages
                entity_check TEXT DEFAULT '',
                chunks_used  INTEGER DEFAULT 0,
                elapsed_s    REAL DEFAULT 0,
                created_at   TEXT NOT NULL,
                closed_at    TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS episode_steps (
                id          INTEGER PRIMARY KEY,
                episode_id  TEXT NOT NULL,
                step        TEXT NOT NULL,   -- e.g. 'visual_search', 'adv_gate_1'
                result      TEXT DEFAULT '',
                duration_ms REAL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY(episode_id) REFERENCES episodes(id)
            );
            CREATE INDEX IF NOT EXISTS ep_created ON episodes(created_at);
            CREATE INDEX IF NOT EXISTS ep_verdict  ON episodes(verdict);
        """)
        c.commit()
        c.close()

    def open_session(self, query: str, doc_id: str = "") -> str:
        sid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        c = _conn(self._db)
        c.execute(
            "INSERT INTO episodes(id,query,doc_id,created_at) VALUES(?,?,?,?)",
            (sid, query, doc_id, now),
        )
        c.commit()
        c.close()
        return sid

    def log_step(self, episode_id: str, step: str,
                 result: str = "", duration_ms: float = 0.0):
        now = datetime.utcnow().isoformat()
        c = _conn(self._db)
        c.execute(
            "INSERT INTO episode_steps(episode_id,step,result,duration_ms,created_at)"
            " VALUES(?,?,?,?,?)",
            (episode_id, step, result[:500], duration_ms, now),
        )
        c.commit()
        c.close()

    def close_session(self, episode_id: str, answer: str = "",
                      verdict: str = "", score: float = 0.0,
                      sources: list[int] | None = None,
                      entity_check: str = "", chunks_used: int = 0,
                      elapsed_s: float = 0.0):
        now = datetime.utcnow().isoformat()
        c = _conn(self._db)
        c.execute(
            "UPDATE episodes SET answer=?,verdict=?,score=?,sources=?,"
            "entity_check=?,chunks_used=?,elapsed_s=?,closed_at=? WHERE id=?",
            (answer, verdict, score,
             json.dumps(sources or []),
             entity_check, chunks_used, elapsed_s, now, episode_id),
        )
        c.commit()
        c.close()

    def recent(self, n: int = 20) -> list[dict]:
        c = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def failure_patterns(self, min_failures: int = 2) -> list[dict]:
        """Queries that failed 2+ times — useful for targeted re-harvest."""
        c = _conn(self._db)
        rows = c.execute("""
            SELECT query, count(*) as fail_count,
                   round(avg(score),3) as avg_score,
                   max(created_at) as last_seen
            FROM episodes
            WHERE verdict IN ('incorrect','error')
            GROUP BY query HAVING fail_count >= ?
            ORDER BY fail_count DESC
        """, (min_failures,)).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def accuracy_by_day(self) -> list[dict]:
        c = _conn(self._db)
        rows = c.execute("""
            SELECT substr(created_at,1,10) as day,
                   count(*) as total,
                   round(avg(score),3) as avg_score,
                   sum(verdict='correct') as correct
            FROM episodes WHERE verdict != ''
            GROUP BY day ORDER BY day DESC LIMIT 30
        """).fetchall()
        c.close()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 2. AGENTIC MEMORY
# ─────────────────────────────────────────────────────────────────────────────

class AgenticMemory:
    """
    Per-agent short-term + scheduled memory.

    Two tables:
      agent_sessions  — one row per session (scratchpad)
      agent_items     — SM-2 scheduled memory items per agent
                        (facts the agent learned that should resurface)
    """

    def __init__(self, agent_id: str, db_path: Path = LEDGER_DB):
        self.agent_id = agent_id
        self._db = db_path
        self._init()

    def _init(self):
        c = _conn(self._db)
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                query       TEXT DEFAULT '',
                state       TEXT DEFAULT '{}',  -- JSON scratchpad
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_items (
                id           INTEGER PRIMARY KEY,
                agent_id     TEXT NOT NULL,
                key          TEXT NOT NULL,
                value        TEXT NOT NULL,
                importance   REAL DEFAULT 1.0,
                sm2_ease     REAL DEFAULT 2.5,
                sm2_interval INTEGER DEFAULT 1,
                sm2_reps     INTEGER DEFAULT 0,
                next_review  TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                archived     INTEGER DEFAULT 0,
                UNIQUE(agent_id, key)
            );
            CREATE INDEX IF NOT EXISTS ai_agent    ON agent_items(agent_id);
            CREATE INDEX IF NOT EXISTS ai_review   ON agent_items(next_review);
            CREATE INDEX IF NOT EXISTS as_agent    ON agent_sessions(agent_id);
        """)
        c.commit()
        c.close()

    # ── Session scratchpad ──

    def new_session(self, query: str = "") -> str:
        sid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        c = _conn(self._db)
        c.execute(
            "INSERT INTO agent_sessions(id,agent_id,query,state,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)",
            (sid, self.agent_id, query, "{}", now, now),
        )
        c.commit()
        c.close()
        return sid

    def write_state(self, session_id: str, key: str, value):
        c = _conn(self._db)
        row = c.execute("SELECT state FROM agent_sessions WHERE id=?",
                        (session_id,)).fetchone()
        state = json.loads(row["state"]) if row else {}
        state[key] = value
        now = datetime.utcnow().isoformat()
        c.execute("UPDATE agent_sessions SET state=?,updated_at=? WHERE id=?",
                  (json.dumps(state, ensure_ascii=False), now, session_id))
        c.commit()
        c.close()

    def read_state(self, session_id: str) -> dict:
        c = _conn(self._db)
        row = c.execute("SELECT state FROM agent_sessions WHERE id=?",
                        (session_id,)).fetchone()
        c.close()
        return json.loads(row["state"]) if row else {}

    # ── SM-2 scheduled items ──

    def remember(self, key: str, value: str, importance: float = 1.0):
        """Store a new fact for this agent (or update if key exists)."""
        now = datetime.utcnow().isoformat()
        nr  = (datetime.utcnow() + timedelta(days=1)).isoformat()
        c   = _conn(self._db)
        try:
            c.execute(
                "INSERT INTO agent_items"
                "(agent_id,key,value,importance,next_review,last_accessed,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (self.agent_id, key, value, importance, nr, now, now),
            )
        except sqlite3.IntegrityError:
            c.execute(
                "UPDATE agent_items SET value=?,importance=MAX(importance,?),updated_at=?"
                " WHERE agent_id=? AND key=?",
                (value, importance, now, self.agent_id, key),
            )
        c.commit()
        c.close()

    def reinforce(self, key: str, quality: int):
        """
        Call after the item was used.
        quality 0-5 (5=perfect, 0=blackout).
        Updates SM-2 schedule + last_accessed.
        """
        c = _conn(self._db)
        row = c.execute(
            "SELECT sm2_ease,sm2_interval,sm2_reps FROM agent_items"
            " WHERE agent_id=? AND key=?",
            (self.agent_id, key),
        ).fetchone()
        if not row:
            c.close()
            return
        ease, interval, reps = row
        new_ease, new_int, new_reps, next_rev = sm2_update(
            ease, interval, reps, quality
        )
        now = datetime.utcnow().isoformat()
        c.execute(
            "UPDATE agent_items SET sm2_ease=?,sm2_interval=?,sm2_reps=?,"
            "next_review=?,last_accessed=? WHERE agent_id=? AND key=?",
            (new_ease, new_int, new_reps, next_rev.isoformat(), now,
             self.agent_id, key),
        )
        c.commit()
        c.close()

    def recall(self, query: str = "", top_k: int = 5,
               include_cold: bool = False) -> list[dict]:
        """
        Retrieve top-k items ranked by R(t) × ease × importance.
        cold items (R < DECAY_FLOOR) excluded unless include_cold=True.
        """
        c = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM agent_items WHERE agent_id=? AND archived=0",
            (self.agent_id,),
        ).fetchall()
        c.close()

        scored = []
        for r in rows:
            d = dict(r)
            score = retrieval_score(d)
            if score < DECAY_FLOOR and not include_cold:
                continue
            q_lower = query.lower()
            # Boost if key matches query terms
            key_match = sum(1 for t in q_lower.split() if t in d["key"].lower())
            scored.append({**d, "_score": score + key_match * 0.1})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored[:top_k]

    def due_for_review(self) -> list[dict]:
        """Items whose next_review is now or past."""
        now = datetime.utcnow().isoformat()
        c   = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM agent_items WHERE agent_id=? AND archived=0"
            " AND next_review <= ? ORDER BY next_review ASC",
            (self.agent_id, now),
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 3. COMPANY MEMORY
# ─────────────────────────────────────────────────────────────────────────────

class CompanyMemory:
    """
    Organisation-level persistent knowledge.
    Injected into every query context and synthesis prompt.

    Items have tags (e.g. 'bim_standard', 'project_template', 'house_style')
    and are retrieved by semantic keyword overlap + SM-2 score.
    """

    def __init__(self, db_path: Path = COMPANY_DB):
        self._db = db_path
        self._init()

    def _init(self):
        c = _conn(self._db)
        c.executescript("""
            CREATE TABLE IF NOT EXISTS company_items (
                id           INTEGER PRIMARY KEY,
                title        TEXT NOT NULL,
                content      TEXT NOT NULL,
                tags         TEXT DEFAULT '[]',  -- JSON list
                source       TEXT DEFAULT '',    -- file path or URL
                importance   REAL DEFAULT 1.0,
                sm2_ease     REAL DEFAULT 2.5,
                sm2_interval INTEGER DEFAULT 1,
                sm2_reps     INTEGER DEFAULT 0,
                next_review  TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                archived     INTEGER DEFAULT 0
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS company_fts USING fts5(
                title, content, tags,
                content='company_items', content_rowid='id'
            );
            CREATE TRIGGER IF NOT EXISTS ci_insert AFTER INSERT ON company_items BEGIN
                INSERT INTO company_fts(rowid,title,content,tags)
                VALUES(new.id, new.title, new.content, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS ci_update AFTER UPDATE ON company_items BEGIN
                INSERT INTO company_fts(company_fts, rowid, title, content, tags)
                VALUES('delete', old.id, old.title, old.content, old.tags);
                INSERT INTO company_fts(rowid, title, content, tags)
                VALUES(new.id, new.title, new.content, new.tags);
            END;
        """)
        c.commit()
        c.close()

    def add(self, title: str, content: str,
            tags: list[str] | None = None,
            source: str = "", importance: float = 1.0):
        now = datetime.utcnow().isoformat()
        nr  = (datetime.utcnow() + timedelta(days=7)).isoformat()  # review in a week
        c   = _conn(self._db)
        c.execute(
            "INSERT INTO company_items"
            "(title,content,tags,source,importance,next_review,last_accessed,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (title, content, json.dumps(tags or []), source, importance, nr, now, now),
        )
        c.commit()
        c.close()

    def retrieve(self, query: str, top_k: int = 4,
                 tags: list[str] | None = None) -> list[dict]:
        """
        FTS search → SM-2 + forgetting curve re-rank → top_k.
        """
        c = _conn(self._db)
        # FTS match first
        try:
            fts_rows = c.execute(
                "SELECT ci.*, bm25(company_fts) as fts_score"
                " FROM company_fts JOIN company_items ci ON ci.id=company_fts.rowid"
                " WHERE company_fts MATCH ? AND ci.archived=0"
                " ORDER BY fts_score LIMIT 20",
                (query,),
            ).fetchall()
        except Exception:
            fts_rows = []

        if not fts_rows:
            fts_rows = c.execute(
                "SELECT *, 0.0 as fts_score FROM company_items WHERE archived=0 LIMIT 20"
            ).fetchall()

        c.close()

        scored = []
        for r in fts_rows:
            d = dict(r)
            if tags and not any(t in json.loads(d.get("tags") or "[]") for t in tags):
                continue
            mem_score = retrieval_score(d)
            fts_s     = abs(float(d.get("fts_score") or 0))
            scored.append({**d, "_score": mem_score * 0.5 + fts_s * 0.5})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored[:top_k]

    def reinforce(self, item_id: int, quality: int):
        c = _conn(self._db)
        row = c.execute(
            "SELECT sm2_ease,sm2_interval,sm2_reps FROM company_items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not row:
            c.close()
            return
        new_ease, new_int, new_reps, next_rev = sm2_update(*row, quality)
        now = datetime.utcnow().isoformat()
        c.execute(
            "UPDATE company_items SET sm2_ease=?,sm2_interval=?,sm2_reps=?,"
            "next_review=?,last_accessed=? WHERE id=?",
            (new_ease, new_int, new_reps, next_rev.isoformat(), now, item_id),
        )
        c.commit()
        c.close()

    def seed_from_okf(self, okf_dir: Path | None = None):
        """
        Seed company memory from existing OKF wiki markdown files.
        Safe to call multiple times (checks for duplicates by title).
        """
        okf_dir = okf_dir or (Path(__file__).parent.parent / "okf" / "docs")
        if not okf_dir.exists():
            return
        c = _conn(self._db)
        existing = {r[0] for r in c.execute("SELECT title FROM company_items")}
        c.close()
        for md in okf_dir.glob("*.md"):
            title = md.stem.replace("-", " ").title()
            if title in existing:
                continue
            content = md.read_text(encoding="utf-8")[:3000]
            self.add(title, content, tags=["okf_wiki", "bim"], source=str(md))
        print(f"[CompanyMemory] seeded from {okf_dir}", flush=True)

    def as_context_block(self, query: str, top_k: int = 3) -> str:
        """Ready-to-inject string for synthesis prompt."""
        items = self.retrieve(query, top_k=top_k)
        if not items:
            return ""
        lines = ["=== Company Memory ==="]
        for it in items:
            lines.append(f"[{it['title']}]\n{it['content'][:400]}")
        return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 4. SEMANTIC MEMORY (SM-2 overlay on knowledge graph entities)
# ─────────────────────────────────────────────────────────────────────────────

class SemanticMemory:
    """
    Reinforcement layer on top of the existing graph.

    Does NOT duplicate entity data — stores only SM-2 metadata
    keyed on entity name_key.  Combined with Ebbinghaus score to
    surface the most *recently useful* entities first during graph traversal.
    """

    def __init__(self, ledger_db: Path = LEDGER_DB,
                 graph_db: Path = GRAPH_DB):
        self._db       = ledger_db
        self._graph_db = graph_db
        self._init()

    def _init(self):
        c = _conn(self._db)
        c.executescript("""
            CREATE TABLE IF NOT EXISTS semantic_scores (
                name_key     TEXT PRIMARY KEY,
                sm2_ease     REAL DEFAULT 2.5,
                sm2_interval INTEGER DEFAULT 1,
                sm2_reps     INTEGER DEFAULT 0,
                next_review  TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                hit_count    INTEGER DEFAULT 0,
                importance   REAL DEFAULT 1.0
            );
        """)
        c.commit()
        c.close()

    def update_entity(self, name_key: str, quality: int,
                      importance: float = 1.0):
        """
        Call when an entity was retrieved and judged useful (quality 3-5)
        or not useful (quality 0-2).
        """
        name_key = name_key.strip().lower()
        c  = _conn(self._db)
        row = c.execute(
            "SELECT sm2_ease,sm2_interval,sm2_reps,hit_count"
            " FROM semantic_scores WHERE name_key=?",
            (name_key,),
        ).fetchone()

        now = datetime.utcnow().isoformat()
        if row:
            new_ease, new_int, new_reps, next_rev = sm2_update(
                row["sm2_ease"], row["sm2_interval"], row["sm2_reps"], quality
            )
            c.execute(
                "UPDATE semantic_scores SET sm2_ease=?,sm2_interval=?,sm2_reps=?,"
                "next_review=?,last_accessed=?,hit_count=hit_count+1,"
                "importance=MAX(importance,?) WHERE name_key=?",
                (new_ease, new_int, new_reps, next_rev.isoformat(), now,
                 importance, name_key),
            )
        else:
            new_ease, new_int, new_reps, next_rev = sm2_update(
                DEFAULT_EASE, DEFAULT_INTERVAL, 0, quality
            )
            c.execute(
                "INSERT INTO semantic_scores"
                "(name_key,sm2_ease,sm2_interval,sm2_reps,next_review,"
                "last_accessed,hit_count,importance) VALUES(?,?,?,?,?,?,1,?)",
                (name_key, new_ease, new_int, new_reps,
                 next_rev.isoformat(), now, importance),
            )
        c.commit()
        c.close()

    def ranked_entities(self, name_keys: list[str]) -> list[tuple[str, float]]:
        """
        Given a list of entity keys (e.g. from graph traversal),
        return them sorted by  R(t) × ease × importance  descending.
        Entities with no SM-2 history get score=0.5 (neutral).
        """
        if not name_keys:
            return []
        c = _conn(self._db)
        placeholders = ",".join("?" * len(name_keys))
        rows = c.execute(
            f"SELECT * FROM semantic_scores WHERE name_key IN ({placeholders})",
            name_keys,
        ).fetchall()
        c.close()

        scores: dict[str, float] = {r["name_key"]: retrieval_score(dict(r))
                                    for r in rows}
        result = [(k, scores.get(k, 0.5)) for k in name_keys]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def cold_entities(self, top_n: int = 10) -> list[dict]:
        """Entities that are decaying — candidate for re-harvest or review."""
        c = _conn(self._db)
        rows = c.execute(
            "SELECT * FROM semantic_scores WHERE hit_count > 0 ORDER BY last_accessed ASC LIMIT ?",
            (top_n,),
        ).fetchall()
        c.close()
        result = []
        for r in rows:
            d   = dict(r)
            r_t = forgetting_curve(_parse_dt(d["last_accessed"]),
                                   float(d["sm2_interval"]))
            if r_t < DECAY_FLOOR:
                result.append({**d, "decay_score": round(r_t, 3)})
        return result

    def stats(self) -> dict:
        c = _conn(self._db)
        total = c.execute("SELECT count(*) FROM semantic_scores").fetchone()[0]
        active = c.execute(
            "SELECT count(*) FROM semantic_scores WHERE hit_count>0"
        ).fetchone()[0]
        due = c.execute(
            "SELECT count(*) FROM semantic_scores WHERE next_review<=?",
            (datetime.utcnow().isoformat(),),
        ).fetchone()[0]
        c.close()
        return {"total": total, "active": active, "due_for_review": due}


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: open all four stores at once
# ─────────────────────────────────────────────────────────────────────────────

class MemoryStack:
    """
    Single entry point for the full memory stack.

    Usage:
        mem = MemoryStack(agent_id="bim_expert")
        sid = mem.episodic.open_session(query)
        ctx = mem.company.as_context_block(query)
        top = mem.semantic.ranked_entities(entity_keys)
        ...
        mem.episodic.close_session(sid, answer=..., verdict=..., score=...)
    """

    def __init__(self, agent_id: str = "default"):
        self.episodic = EpisodicLedger()
        self.agentic  = AgenticMemory(agent_id=agent_id)
        self.company  = CompanyMemory()
        self.semantic = SemanticMemory()

    def company_context(self, query: str, top_k: int = 3) -> str:
        return self.company.as_context_block(query, top_k=top_k)

    def rank_graph_entities(self, keys: list[str]) -> list[tuple[str, float]]:
        return self.semantic.ranked_entities(keys)

    def reinforce_episode(self, episode_id: str, entity_keys: list[str],
                          verdict: str):
        """After a query closes, bulk-reinforce the entities that were used."""
        quality = {"correct": 5, "partial": 3, "incorrect": 1, "error": 0}.get(
            verdict, 3
        )
        for k in entity_keys:
            self.semantic.update_entity(k, quality=quality)
