"""Hybrid retrieval — the "lens" in the architecture sketch."""
from __future__ import annotations
from . import graph
from .db import connect
from .embedding import get_embedder
from .models import PageHit
from .store import get_store
def visual_search(query: str, k: int = 5) -> list[PageHit]:
    """Top-k page hits by multimodal MaxSim, enriched with title + image path."""
    q_emb = get_embedder().embed_queries([query])[0]
    hits = get_store().search(q_emb, k=k)
    if not hits:
        return []
    keys = {(d, p) for d, p, _ in hits}
    meta: dict[tuple[str, int], tuple[str, str]] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.doc_id, p.page, p.image_path, d.title "
                "FROM pages p JOIN documents d ON d.doc_id = p.doc_id "
                "WHERE (p.doc_id, p.page) IN (SELECT * FROM unnest(%s::text[], %s::int[]))",
                ([d for d, _ in keys], [p for _, p in keys]),
            )
            for doc_id, page, image_path, title in cur.fetchall():
                meta[(doc_id, page)] = (image_path or "", title or "")
    return [
        PageHit(
            doc_id=d,
            page=p,
            score=round(s, 4),
            image_path=meta.get((d, p), ("", ""))[0],
            title=meta.get((d, p), ("", ""))[1],
        )
        for d, p, s in hits
    ]
def graph_context(query: str, depth: int = 1) -> dict:
    """Entities matching the query + their neighbourhood edges."""
    ents = graph.search_entities(query)
    edges: list[dict] = []
    for e in ents[:5]:
        edges.extend(graph.neighbors(e["name"], depth=depth))
    return {"entities": ents, "relations": edges}
def retrieve(query: str, k: int = 5) -> dict:
    """Run all retrievers, swallowing per-signal failures (degrade-soft)."""
    def _safe(fn, default):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)[:200], "value": default}
    visual = _safe(lambda: [h.model_dump() for h in visual_search(query, k)], [])
    graph_c = _safe(lambda: graph_context(query), {})
    return {"query": query, "visual": visual, "graph": graph_c}
