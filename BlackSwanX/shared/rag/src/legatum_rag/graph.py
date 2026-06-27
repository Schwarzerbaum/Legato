"""Property graph — LLM-harvested entities + relations in plain Postgres tables."""
from __future__ import annotations
from .db import connect
from .models import Entity, Mention, Relation
def upsert_entities(doc_id: str, entities: list[Entity]) -> int:
    """Insert/refresh entities (keyed by normalized name). Returns count."""
    if not entities:
        return 0
    rows = [
        (e.name.strip(), e.name.strip().lower(), e.type, e.description, doc_id)
        for e in entities
        if e.name.strip()
    ]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO entities (name, name_key, type, description, doc_id) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (name_key) DO UPDATE SET "
                "  type = COALESCE(NULLIF(EXCLUDED.type, ''), entities.type), "
                "  description = COALESCE(NULLIF(EXCLUDED.description, ''), entities.description)",
                rows,
            )
    return len(rows)
def upsert_relations(doc_id: str, relations: list[Relation]) -> int:
    """Insert relations (source/target by name). Returns count."""
    if not relations:
        return 0
    rows = [
        (
            r.source.strip().lower(),
            r.target.strip().lower(),
            r.type,
            r.description,
            doc_id,
        )
        for r in relations
        if r.source.strip() and r.target.strip()
    ]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO relations (source_key, target_key, type, description, doc_id) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                rows,
            )
    return len(rows)
def upsert_mentions(doc_id: str, mentions: list[Mention]) -> int:
    """Record per-page provenance for harvested entities. Returns count."""
    if not mentions:
        return 0
    rows = [(m.name_key, doc_id, m.page) for m in mentions if m.name_key]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO entity_mentions (name_key, doc_id, page) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                rows,
            )
    return len(rows)
def search_entities(text: str, limit: int = 20) -> list[dict]:
    """Substring search over entity names/descriptions."""
    like = f"%{text.strip().lower()}%"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, type, description, doc_id FROM entities "
                "WHERE name_key LIKE %s OR lower(description) LIKE %s LIMIT %s",
                (like, like, limit),
            )
            return [
                {"name": n, "type": t, "description": d, "doc_id": doc}
                for n, t, d, doc in cur.fetchall()
            ]
def neighbors(name: str, depth: int = 1, limit: int = 50) -> list[dict]:
    """Return relations within ``depth`` hops of an entity (by name)."""
    key = name.strip().lower()
    frontier = {key}
    seen: set[str] = set()
    edges: list[dict] = []
    with connect() as conn:
        with conn.cursor() as cur:
            for _ in range(max(1, depth)):
                if not frontier:
                    break
                cur.execute(
                    "SELECT source_key, target_key, type, description FROM relations "
                    "WHERE source_key = ANY(%s) OR target_key = ANY(%s) LIMIT %s",
                    (list(frontier), list(frontier), limit),
                )
                seen |= frontier
                nxt: set[str] = set()
                for s, t, typ, desc in cur.fetchall():
                    edges.append(
                        {"source": s, "target": t, "type": typ, "description": desc}
                    )
                    nxt |= {s, t}
                frontier = nxt - seen
    uniq = {(e["source"], e["target"], e["type"]): e for e in edges}
    return list(uniq.values())
def graph_stats() -> dict:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM entities")
            ents = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM relations")
            rels = cur.fetchone()[0]
    return {"entities": ents, "relations": rels}
