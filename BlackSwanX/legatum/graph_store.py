"""
Persistent graph store with LLM-based entity/relation extraction (PR #2 style).
Combines windowed LLM harvest with RRF + cross-encoder retrieval.

Storage layout:
  legatum/graphs/{sha256_of_pdf_path}.json
  {
    "pdf_path": str,
    "filename": str,
    "extracted_at": ISO timestamp,
    "entities": [{"name": str, "type": str, "description": str}],
    "relations": [{"source": str, "target": str, "type": str, "description": str}],
    "mentions": [{"entity_name": str, "page": int}],
    "nodes": [{id, type, page}],
    "edges": [{source, source_type, target, target_type, type, page, confidence}],
    "sections": [{heading, doc, page, text, embedding: [float] | null}]
  }
"""
import json
import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

GRAPH_DIR = Path(__file__).parent / "graphs"
GRAPH_DIR.mkdir(exist_ok=True)

# ── Embedding config ───────────────────────────────────────────────────────────
# Default: BGE-M3 local (1024-dim, multilingual, free, matches founders' stack).
# Embedding stack: nomic-embed-text via Ollama (768-dim, available locally)
# BGE-M3 (1024-dim) requires Python ≤3.12; skip on 3.14 to avoid model download hang.
# Override: EMBEDDING_PROVIDER=local EMBEDDING_MODEL_LOCAL=BAAI/bge-m3
import os as _os
import sys as _sys
_EMBEDDING_PROVIDER = _os.getenv("EMBEDDING_PROVIDER",
    "local" if _sys.version_info < (3, 14) else "none")
_EMBEDDING_MODEL    = _os.getenv("EMBEDDING_MODEL_LOCAL", "BAAI/bge-m3")
_OLLAMA_EMBED_URL   = "http://localhost:11434/api/embeddings"
# BGE-M3 via Ollama: 1024-dim, multilingual, matches founders' pgvector stack.
# Falls back to nomic-embed-text (768-dim) if bge-m3 not pulled yet.
_OLLAMA_EMBED_MODEL = _os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
_OLLAMA_EMBED_FALLBACK = "nomic-embed-text"   # 768-dim fallback


# ── Storage helpers ────────────────────────────────────────────────────────────

def _graph_path(pdf_path: str) -> Path:
    key = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]
    return GRAPH_DIR / f"{key}.json"


def _build_constraint_index(edges: list[dict]) -> dict:
    """
    Pre-index all CONSTRAINT edges at extraction time.
    Structure: {process_or_standard_name: [{edge}]}
    Query time just does a dict lookup — no scanning.
    """
    index: dict[str, list[dict]] = {}
    for e in edges:
        if e.get("target_type") == "CONSTRAINT" or e.get("source_type") == "CONSTRAINT":
            # index by the non-CONSTRAINT node so lookup is fast
            key = e["source"] if e.get("target_type") == "CONSTRAINT" else e["target"]
            index.setdefault(key.lower(), []).append(e)
    return index


# ── LLM-based entity/relation extraction (PR #2 Harvester) ──────────────────────

def _harvest_text_with_llm(text: str) -> dict:
    """
    Extract entities and relations from a text window using Qwen via Ollama.
    Uses httpx directly to avoid SDK dependencies.
    """
    try:
        import httpx

        text = (text or "").strip()
        if not text:
            return {"entities": [], "relations": []}

        prompt = f"""Extract key entities and relations from this document text.
Return JSON with:
- entities: array of {{name, type (one of: concept, standard, organization, person, process), description}}
- relations: array of {{source, target, type (e.g. part_of, requires, defines), description}}

Only extract what the text explicitly supports. Prefer high-confidence items.

Text:
{text[:8000]}

Return ONLY valid JSON, no preamble."""

        response = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5-coder:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2000, "temperature": 0.1}
            },
            timeout=60
        )
        response.raise_for_status()

        response_text = response.json().get("response", "").strip()

        # Parse JSON from response
        try:
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                entities = [
                    {
                        "name": e.get("name", "").strip(),
                        "type": e.get("type", "concept").strip(),
                        "description": e.get("description", "").strip()
                    }
                    for e in data.get("entities", [])
                    if e.get("name", "").strip()
                ]
                relations = [
                    {
                        "source": r.get("source", "").strip(),
                        "target": r.get("target", "").strip(),
                        "type": r.get("type", "").strip(),
                        "description": r.get("description", "").strip()
                    }
                    for r in data.get("relations", [])
                    if r.get("source", "").strip() and r.get("target", "").strip()
                ]
                return {"entities": entities, "relations": relations}
        except json.JSONDecodeError:
            pass

        return {"entities": [], "relations": []}

    except Exception as e:
        import sys
        print(f"[LLM harvest failed: {str(e)[:100]}]", file=sys.stderr)
        return {"entities": [], "relations": []}


def harvest_from_pages(pages: list[tuple[int, str]], window_size: int = 3, overlap: int = 1) -> dict:
    """
    Windowed harvest of entity/relation extraction from pages.
    Slides a window of `window_size` pages with `overlap` pages between windows.
    Merges results across windows, deduplicating and tracking page mentions.
    """
    if not pages:
        return {"entities": [], "relations": [], "mentions": []}

    # Build windows
    windows = []
    step = max(1, window_size - max(0, overlap))
    i = 0
    while i < len(pages):
        chunk = pages[i:i + window_size]
        page_nums = [p for p, _ in chunk]
        window_text = "\n\n".join(
            f"[page {p}]\n{t}" for p, t in chunk if t.strip()
        )
        if window_text.strip():
            windows.append((page_nums, window_text))
        if i + window_size >= len(pages):
            break
        i += step

    # Harvest each window
    all_entities = {}  # name_key → {name, type, description}
    all_relations = {}  # (source_key, target_key, type) → {source, target, type, description}
    all_mentions = set()  # (name_key, page)

    for page_nums, window_text in windows:
        harvest = _harvest_text_with_llm(window_text)

        for ent in harvest.get("entities", []):
            name = ent.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in all_entities:
                all_entities[key] = ent
            else:
                # Merge: prefer longer description
                cur = all_entities[key]
                if ent.get("type") and not cur.get("type"):
                    cur["type"] = ent.get("type")
                if len(ent.get("description", "")) > len(cur.get("description", "")):
                    cur["description"] = ent.get("description", "")

            for page in page_nums:
                all_mentions.add((key, page))

        for rel in harvest.get("relations", []):
            source = rel.get("source", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            rel_type = rel.get("type", "").strip()
            if not source or not target:
                continue
            key = (source, target, rel_type)
            if key not in all_relations:
                all_relations[key] = {
                    "source": rel.get("source", "").strip(),
                    "target": rel.get("target", "").strip(),
                    "type": rel_type,
                    "description": rel.get("description", "").strip()
                }

    return {
        "entities": list(all_entities.values()),
        "relations": list(all_relations.values()),
        "mentions": [{"entity_name": k, "page": p} for k, p in sorted(all_mentions)]
    }


def save_graph(pdf_path: str, filename: str, nodes: list, edges: list, sections: list,
               entities: list = None, relations: list = None, mentions: list = None):
    # Auto-harvest if not provided (harvest from page text)
    if entities is None or relations is None or mentions is None:
        pages = [(s.get("page"), s.get("text", "")) for s in sections]
        harvest = harvest_from_pages(pages, window_size=3, overlap=1)
        entities = entities or harvest.get("entities", [])
        relations = relations or harvest.get("relations", [])
        mentions = mentions or harvest.get("mentions", [])

    data = {
        "pdf_path": pdf_path,
        "filename": filename,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "sections": sections,
        "entities": entities,
        "relations": relations,
        "mentions": mentions,
        # Pre-built at extraction time — never recomputed at query time
        "constraint_index": _build_constraint_index(edges),
    }
    # JSON — always write (cache + fallback)
    _graph_path(pdf_path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    # Neo4j — dual-write when available (non-fatal if unavailable)
    try:
        from legatum.neo4j_store import upsert_graph, is_available
        if is_available():
            upsert_graph(pdf_path, filename, nodes, edges, sections)
    except Exception:
        pass


def load_graph(pdf_path: str) -> Optional[dict]:
    p = _graph_path(pdf_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def graph_exists(pdf_path: str) -> bool:
    return _graph_path(pdf_path).exists()


# ── Embeddings (BGE-M3 via xpertly layer → Ollama nomic fallback) ─────────────

_embed_provider = None   # lazy singleton

def _get_embed_provider():
    """Lazy-load the embedding provider singleton (BGE-M3 local by default)."""
    global _embed_provider
    if _embed_provider is not None:
        return _embed_provider
    try:
        from legatum.embeddings.factory import create_embedding_provider
        _embed_provider = create_embedding_provider(
            provider=_EMBEDDING_PROVIDER,
            model=_EMBEDDING_MODEL,
        )
        return _embed_provider
    except Exception:
        return None


def _embed_text(text: str) -> Optional[list[float]]:
    """Embed a single text. Uses BGE-M3 via xpertly layer, falls back to Ollama."""
    # Primary: BGE-M3 local via sentence-transformers
    provider = _get_embed_provider()
    if provider is not None:
        try:
            return provider.embed(text[:8192]).embedding
        except Exception:
            pass
    # Ollama: try bge-m3 (1024-dim) first, then nomic-embed-text (768-dim)
    try:
        import httpx
        r = httpx.post(
            _OLLAMA_EMBED_URL,
            json={"model": _OLLAMA_EMBED_MODEL, "prompt": text[:2000]},
            timeout=30,
        )
        r.raise_for_status()
        emb = r.json().get("embedding")
        if emb:
            return emb
    except Exception:
        pass
    try:
        import httpx
        r = httpx.post(
            _OLLAMA_EMBED_URL,
            json={"model": _OLLAMA_EMBED_FALLBACK, "prompt": text[:2000]},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception:
        return None


def embed_sections(sections: list[dict]) -> list[dict]:
    """
    Add embedding vectors to all sections in one batch (BGE-M3) or one-by-one fallback.
    Falls back gracefully — RRF still works if embeddings are unavailable.
    """
    # Build text strings — prefer the breadcrumb-enriched `text` field set by
    # hierarchical chunking; fall back to heading + blocks for legacy sections.
    texts = [
        (
            s.get("text") or
            (s.get("heading", "") + " " + " ".join(s.get("blocks", []))).strip()
        )
        for s in sections
    ]

    # Attempt batch embed via BGE-M3 (much faster than one-by-one)
    vectors: list[Optional[list[float]]] = [None] * len(sections)
    provider = _get_embed_provider()
    if provider is not None:
        try:
            non_empty_idx = [i for i, t in enumerate(texts) if t]
            non_empty_texts = [texts[i] for i in non_empty_idx]
            if non_empty_texts:
                batch_result = provider.embed_batch(non_empty_texts)
                for pos, idx in enumerate(non_empty_idx):
                    vectors[idx] = batch_result.embeddings[pos]
        except Exception:
            pass  # fall through to per-section Ollama fallback

    enriched = []
    for i, s in enumerate(sections):
        vec = vectors[i]
        if vec is None and texts[i]:
            vec = _embed_text(texts[i])   # Ollama fallback per section
        enriched.append({**s, "text": texts[i], "embedding": vec})
    return enriched


# ── Retrieval: RRF + Cross-encoder Reranker ───────────────────────────────────
# Pipeline:
#   1. Dense retrieval  — cosine similarity against nomic-embed-text vectors (top 50)
#   2. Sparse retrieval — BM25 token overlap (top 50)
#   3. RRF fusion       — merge rank positions, not raw scores
#   4. Reranker         — cross-encoder evaluates full question↔chunk attention (top_k)

RRF_K = 60          # standard constant for RRF; higher = less aggressive rank weighting
CANDIDATE_POOL = 50  # how many candidates each retriever sends to RRF before reranking

# Lazy-loaded reranker — downloads once (~600MB), then cached locally
_reranker = None
_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"   # multilingual, strong on German legal text

def _get_reranker():
    global _reranker
    if _reranker is None:
        # Skip on Python 3.14+ — CrossEncoder would download bge-reranker-v2-m3 (~1GB)
        # and torch has incompatibilities. BM25+RRF is sufficient fallback.
        if _sys.version_info >= (3, 14):
            _reranker = False
        else:
            try:
                from sentence_transformers import CrossEncoder
                _reranker = CrossEncoder(_RERANKER_MODEL, max_length=512)
            except Exception:
                _reranker = False
    return _reranker if _reranker is not False else None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb + 1e-9)


def _bm25_ranks(question: str, sections: list[dict]) -> list[tuple[int, float]]:
    """Return (original_index, bm25_score) sorted best-first."""
    import re as _re
    def _tok(t): return _re.findall(r'\w+', t.lower())

    def _match(q_token: str, s_tokens_set: set) -> bool:
        """Match with German morphology tolerance.
        Handles: genitive/plural suffixes, compound word decomposition.
        """
        if q_token in s_tokens_set:
            return True
        if len(q_token) < 4:
            return False
        # Strip common German suffixes for base-form matching
        q_stem = q_token[:-2] if len(q_token) > 6 else q_token  # -en, -es, -er, -em, -s
        for t in s_tokens_set:
            if not t or len(t) < 4:
                continue
            t_stem = t[:-2] if len(t) > 6 else t
            # Direct stem overlap (length-similar words)
            if abs(len(t) - len(q_token)) <= 4:
                if q_stem.startswith(t_stem) or t_stem.startswith(q_stem):
                    return True
            # German compound decomposition: section token is a component of query token
            # e.g. "verwaltung" in "straßenbauverwaltung"
            if len(t) >= 6 and len(q_token) > len(t) and q_token.endswith(t):
                return True
            if len(q_token) >= 6 and len(t) > len(q_token) and t.endswith(q_token):
                return True
            # Also check stems of compounds
            if len(t_stem) >= 6 and q_token.endswith(t_stem):
                return True
        return False

    q_tok = _tok(question)
    if not q_tok:
        return []

    # Pre-compute section lengths for BM25 length normalization
    s_toks_list = [_tok(s.get("text", "")) for s in sections]
    avg_dl = sum(len(t) for t in s_toks_list) / max(len(s_toks_list), 1)
    K1, B = 1.5, 0.75  # standard BM25 parameters

    scored = []
    for i, (s, s_tok) in enumerate(zip(sections, s_toks_list)):
        s_set = set(s_tok)
        dl = len(s_tok)
        bm25_score = 0.0
        for qt in q_tok:
            if not _match(qt, s_set):
                continue
            # Count occurrences of matching tokens (approximate with 1 for set match)
            tf_raw = sum(1 for t in s_tok if _match(qt, {t}))
            # BM25 TF normalization with length penalty
            tf_norm = (tf_raw * (K1 + 1)) / (tf_raw + K1 * (1 - B + B * dl / max(avg_dl, 1)))
            bm25_score += tf_norm
        scored.append((i, bm25_score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _rrf_merge(dense_ranks: list[int], sparse_ranks: list[int],
               n: int) -> list[int]:
    """
    Reciprocal Rank Fusion.
    dense_ranks / sparse_ranks: lists of section indices ordered best-first.
    Returns merged list of indices ordered by RRF score, length n.
    """
    scores: dict[int, float] = {}
    for rank, idx in enumerate(dense_ranks):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
    for rank, idx in enumerate(sparse_ranks):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
    merged = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    return merged[:n]


# ── Graph grounding: Look up entities/relations matching query ──────────────────

def graph_ground(question: str, graph: dict) -> dict:
    """
    Find entities and relations in the graph matching the query.
    This ensures answers are grounded in extracted facts (prevents hallucination).
    Returns {entities: [...], relations: [...], pages: set(...)}
    """
    entities = graph.get("entities", [])
    relations = graph.get("relations", [])
    mentions = graph.get("mentions", [])

    question_lower = question.lower()

    # Find entities matching query terms
    matching_entities = []
    matched_entity_names = set()
    for ent in entities:
        name = ent.get("name", "").lower()
        desc = ent.get("description", "").lower()
        if name in question_lower or any(word in question_lower for word in name.split()):
            matching_entities.append({
                "name": ent.get("name", ""),
                "type": ent.get("type", ""),
                "description": ent.get("description", "")
            })
            matched_entity_names.add(name)

    # Find relations involving matched entities
    matching_relations = []
    for rel in relations:
        source = rel.get("source", "").lower()
        target = rel.get("target", "").lower()
        if source in matched_entity_names or target in matched_entity_names:
            matching_relations.append({
                "source": rel.get("source", ""),
                "target": rel.get("target", ""),
                "type": rel.get("type", ""),
                "description": rel.get("description", "")
            })

    # Find pages where matched entities appear
    matching_pages = set()
    for ment in mentions:
        entity_name = ment.get("entity_name", "").lower()
        if entity_name in matched_entity_names:
            page = ment.get("page")
            if page is not None:
                matching_pages.add(page)

    return {
        "entities": matching_entities[:10],
        "relations": matching_relations[:10],
        "pages": matching_pages
    }


def semantic_search(question: str, sections: list[dict], top_k: int = 12) -> list[dict]:
    """
    Full retrieval pipeline: dense + sparse → RRF → cross-encoder reranker.

    Returns top_k sections, ordered by reranker score when available.
    Falls back gracefully at each stage if models are unavailable.
    """
    if not sections:
        return []

    q_vec = _embed_text(question)
    with_emb = [s for s in sections if s.get("embedding")]

    # ── Stage 1: Dense retrieval ────────────────────────────────────────────
    if q_vec and with_emb:
        dense_scored = sorted(
            range(len(sections)),
            key=lambda i: _cosine(q_vec, sections[i]["embedding"]) if sections[i].get("embedding") else -1,
            reverse=True,
        )
        dense_top = dense_scored[:CANDIDATE_POOL]
    else:
        dense_top = []  # no embeddings — BM25 is sole ranker, no false positional bias

    # ── Stage 2: Sparse retrieval (BM25) ───────────────────────────────────
    bm25_scored = _bm25_ranks(question, sections)
    sparse_top = [i for i, _ in bm25_scored[:CANDIDATE_POOL]]

    # ── Stage 3: RRF fusion (or BM25-only when no dense) ───────────────────
    if dense_top:
        candidates_idx = _rrf_merge(dense_top, sparse_top, n=20)
    else:
        candidates_idx = sparse_top[:20]
    candidates = [sections[i] for i in candidates_idx]

    # ── Stage 4: Cross-encoder reranker ────────────────────────────────────
    reranker = _get_reranker()
    if reranker and len(candidates) > top_k:
        try:
            pairs = [(question, s.get("text", "")[:512]) for s in candidates]
            scores = reranker.predict(pairs)
            reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
            return [s for s, _ in reranked[:top_k]]
        except Exception:
            pass  # reranker failed — fall through to RRF order

    return candidates[:top_k]


# ── Structured graph traversal ─────────────────────────────────────────────────

MAX_HOP_DEPTH = 3   # never traverse more than 3 hops from any start node
MAX_EDGES_PER_NODE = 8   # cap fan-out per node to prevent combinatorial explosion


def query_graph(edges: list[dict], node_type: str = None,
                relation: str = None, node_name: str = None,
                max_results: int = 50) -> list[dict]:
    """
    Single-hop filtered lookup. All filters optional, combined with AND.
    Capped at max_results to prevent runaway responses.
    """
    results = []
    for e in edges:
        if node_type and e.get("source_type") != node_type and e.get("target_type") != node_type:
            continue
        if relation and e.get("type") != relation:
            continue
        if node_name:
            name_l = node_name.lower()
            if name_l not in e.get("source", "").lower() and name_l not in e.get("target", "").lower():
                continue
        results.append(e)
        if len(results) >= max_results:
            break
    return results


def multi_hop(edges: list[dict], start_node: str,
              max_hops: int = MAX_HOP_DEPTH, max_results: int = 40,
              pdf_path: str = None) -> list[dict]:
    """
    BFS traversal — uses Cypher-native traversal if Neo4j available (much faster).
    Falls back to Python BFS over JSON edges.
    """
    if pdf_path:
        try:
            from legatum.neo4j_store import multi_hop_neo4j, is_available
            if is_available():
                return multi_hop_neo4j(pdf_path, start_node, max_hops, max_results)
        except Exception:
            pass
    """
    BFS traversal from start_node up to max_hops (capped at MAX_HOP_DEPTH).
    Returns all edges reachable within that depth. Fan-out capped at MAX_EDGES_PER_NODE.
    """
    max_hops = min(max_hops, MAX_HOP_DEPTH)
    # Build adjacency: node → [edges]
    adj: dict[str, list[dict]] = {}
    for e in edges:
        adj.setdefault(e.get("source", ""), []).append(e)

    visited_nodes: set[str] = {start_node}
    frontier: list[str] = [start_node]
    collected: list[dict] = []

    for _ in range(max_hops):
        next_frontier: list[str] = []
        for node in frontier:
            neighbours = adj.get(node, [])[:MAX_EDGES_PER_NODE]
            for e in neighbours:
                if len(collected) >= max_results:
                    return collected
                collected.append(e)
                tgt = e.get("target", "")
                if tgt not in visited_nodes:
                    visited_nodes.add(tgt)
                    next_frontier.append(tgt)
        frontier = next_frontier
        if not frontier:
            break

    return collected


def lookup_constraints(constraint_index: dict, node_text: str) -> list[dict]:
    """
    O(1) lookup into pre-built constraint index.
    Use this at query time instead of scanning all edges.
    """
    return constraint_index.get(node_text.lower(), [])


def validate_claims_against_index(answer: str, constraint_index: dict) -> tuple[str, str, list, list]:
    """
    Deterministic claim validator — uses pre-built index, zero scanning.
    Returns (ampel, reason, contradictions, unverified).
    Called at query time but does no graph traversal — pure dict lookups.
    """
    import re as _re

    _claim_pat = _re.compile(
        r"(\d+[\s ]*(Tage?|Wochen?|Monate?|Stunden?|Werktage?)|"
        r"\d+[,.]?\d*\s*(mm|cm|m²|m³|kg|kN|MPa|%|€|EUR)|"
        r"[A-Z]\d+/\d+|"
        r"§\s*\d+(?:\s*Abs\.\s*\d+)?)",
        _re.I | _re.UNICODE,
    )
    answer_claims = set(m.group(0).strip() for m in _claim_pat.finditer(answer))

    # All constraint edges as flat list for conflict detection
    all_constraint_edges = [e for edges in constraint_index.values() for e in edges]

    contradictions: list[dict] = []
    unverified: list[str] = []

    for claim in answer_claims:
        cl = claim.lower()
        # O(1): check if this claim value is a key in the index
        matched = next(
            (e for e in all_constraint_edges
             if cl in e.get("source", "").lower() or cl in e.get("target", "").lower()),
            None,
        )
        if matched:
            # Check for conflicting constraint on the same source node
            source_key = matched.get("source", "").lower()
            siblings = constraint_index.get(source_key, [])
            conflicts = [
                e for e in siblings
                if e.get("type") == matched.get("type")
                and e["target"].lower() != cl
            ]
            for c in conflicts:
                contradictions.append({
                    "claim": claim,
                    "kg_value": c["target"],
                    "edge": f"({c['source']})-[{c['type']}]->({c['target']})",
                    "page": c.get("page"),
                })
        else:
            unverified.append(claim)

    if contradictions:
        ampel = "red"
        reason = "; ".join(
            f"Answer says '{c['claim']}' but KG shows {c['kg_value']} — {c['edge']}"
            for c in contradictions
        )
    elif unverified:
        ampel = "yellow"
        reason = f"Unverified claim(s) not in document graph: {', '.join(unverified)}"
    else:
        ampel = "green"
        reason = "All numeric/temporal claims verified against document graph."

    return ampel, reason, contradictions, unverified


def find_constraints_for_process(edges: list[dict], process_text: str) -> list[dict]:
    """Find all CONSTRAINT nodes linked to a PROCESS node (by partial name match)."""
    proc_l = process_text.lower()
    return [
        e for e in edges
        if e.get("source_type") == "PROCESS"
        and proc_l in e.get("source", "").lower()
        and e.get("target_type") == "CONSTRAINT"
    ]


def find_responsible_roles(edges: list[dict], deliverable_text: str) -> list[dict]:
    """Find ROLE nodes RESPONSIBLE_FOR a DELIVERABLE."""
    deliv_l = deliverable_text.lower()
    return [
        e for e in edges
        if e.get("type") == "RESPONSIBLE_FOR"
        and deliv_l in e.get("target", "").lower()
    ]


# ── LLM Extraction Enhancer ───────────────────────────────────────────────────
# Runs after regex KG is built. Finds entities regex missed in unmatched sections.
# Regex takes priority on conflicts — LLM results tagged confidence=0.6.

_EXTRACT_PROMPT = """Du analysierst einen Abschnitt aus einem deutschen Baudokument.
Extrahiere alle Entitäten aus diesen 5 Typen:
- ROLE: Personen/Organisationen mit Verantwortung (z.B. Auftraggeber, Bauleiter, BIM-Koordinator)
- STANDARD: Normen/Gesetze (z.B. VOB/B §4, DIN EN 206, HOAI LP8)
- DELIVERABLE: Dokumente/Ergebnisse (z.B. BAP, Mängelrüge, Bautagebuch)
- PROCESS: Abläufe/Tätigkeiten (z.B. Abnahme, Qualitätsprüfung, Freigabe)
- CONSTRAINT: Fristen/Werte/Toleranzen (z.B. 14 Tage, C30/37, €5000)

TEXT:
{text}

Antworte NUR mit JSON-Array. Kein anderer Text:
[{{"entity": "Name", "type": "ROLE|STANDARD|DELIVERABLE|PROCESS|CONSTRAINT"}}]
Maximal 8 Einträge. Nur eindeutige, klar erkennbare Entitäten."""


def llm_extract_entities(sections: list[dict], existing_nodes: set[str],
                          max_sections: int = 20) -> list[dict]:
    """
    LLM pass over sections that regex missed (not in existing_nodes).
    Returns new edges with confidence=0.6 (lower than regex 0.9).
    Runs synchronously — call via run_in_executor from async context.
    """
    import httpx as _httpx
    import json as _json
    import re as _re

    new_edges: list[dict] = []
    processed = 0

    for s in sections:
        if processed >= max_sections:
            break
        text = s.get("text", "").strip()
        if not text or len(text) < 40:
            continue

        # Skip sections already well-covered by regex
        words = set(text.lower().split())
        known_hit = sum(1 for n in existing_nodes if n.lower() in words)
        if known_hit >= 2:
            continue

        try:
            r = _httpx.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": _EXTRACT_PROMPT.format(text=text[:800]),
                      "stream": False, "options": {"temperature": 0.05, "num_predict": 300}},
                timeout=30,
            )
            raw = r.json().get("response", "")
            match = _re.search(r'\[.*?\]', raw, _re.DOTALL)
            if not match:
                continue
            entities = _json.loads(match.group())
            valid_types = {"ROLE","STANDARD","DELIVERABLE","PROCESS","CONSTRAINT"}
            entities = [e for e in entities
                        if isinstance(e, dict) and e.get("type") in valid_types
                        and e.get("entity") and e["entity"] not in existing_nodes][:8]

            for i, ent in enumerate(entities):
                if i + 1 < len(entities):
                    nxt = entities[i + 1]
                    new_edges.append({
                        "source": ent["entity"],
                        "source_type": ent["type"],
                        "target": nxt["entity"],
                        "target_type": nxt["type"],
                        "type": "CO_OCCURS",
                        "method": "llm_extraction",
                        "confidence": 0.6,
                        "page": s.get("page"),
                    })
                existing_nodes.add(ent["entity"])
            processed += 1
        except Exception:
            continue

    return new_edges


# ── KG Reviewer Agent ─────────────────────────────────────────────────────────
# After full KG is built, audit a sample of nodes for type correctness.
# Returns list of suggested corrections — does NOT auto-apply (human-in-loop).

_REVIEW_PROMPT = """Du prüfst die Klassifizierung von Entitäten aus deutschen Baudokumenten.
Prüfe ob der zugewiesene Typ korrekt ist.

Typen:
- ROLE: Personen/Organisationen
- STANDARD: Normen/Gesetze/Paragraphen
- DELIVERABLE: Dokumente/Ergebnisse die erstellt werden
- PROCESS: Tätigkeiten/Abläufe
- CONSTRAINT: Fristen/Zahlen/Toleranzen/Werte
- CONCEPT: Alles andere

Entitäten zur Prüfung:
{entities}

Antworte NUR mit JSON. Kein anderer Text:
[{{"entity": "Name", "assigned_type": "TYPE", "correct_type": "TYPE", "issue": "Begründung oder null"}}]
Nur Einträge mit tatsächlichen Fehlern (correct_type != assigned_type)."""


def review_kg_types(nodes: list[dict], sample_size: int = 30) -> list[dict]:
    """
    LLM audits a sample of node type assignments.
    Returns list of corrections: [{entity, assigned_type, correct_type, issue}]
    Synchronous — call via run_in_executor.
    """
    import httpx as _httpx
    import json as _json
    import re as _re

    if not nodes:
        return []

    sample = nodes[:sample_size]
    entity_lines = "\n".join(f"- {n['id']} → {n.get('type','CONCEPT')}" for n in sample)

    try:
        r = _httpx.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2:3b",
                  "prompt": _REVIEW_PROMPT.format(entities=entity_lines),
                  "stream": False,
                  "options": {"temperature": 0.05, "num_predict": 400}},
            timeout=45,
        )
        raw = r.json().get("response", "")
        match = _re.search(r'\[.*?\]', raw, _re.DOTALL)
        if not match:
            return []
        corrections = _json.loads(match.group())
        return [c for c in corrections
                if isinstance(c, dict)
                and c.get("correct_type") != c.get("assigned_type")
                and c.get("issue")]
    except Exception:
        return []
