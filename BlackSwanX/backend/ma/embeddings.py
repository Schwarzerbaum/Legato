"""
Semantic Vector Embeddings — Ollama nomic-embed-text backend.
Catches "wind-down event" when you search "termination upon acquisition."
Falls back gracefully to BM25 if Ollama embedding model isn't loaded.
"""
import json
import math


EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"


def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> list[float] | None:
    """Call Ollama embeddings API. Returns vector or None on failure."""
    try:
        import requests
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text[:2000]},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("embedding")
    except Exception:
        pass
    return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 4)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Add 'embedding' field to each chunk dict.
    Returns chunks with embeddings (skips failures silently).
    """
    results = []
    for c in chunks:
        emb = get_embedding(c.get("text", ""))
        results.append({**c, "embedding": emb})
    return results


def semantic_search(
    query: str,
    chunk_rows: list[dict],  # each must have 'embedding_json' or 'embedding' field
    top_k: int = 12,
    min_score: float = 0.3,
) -> list[dict]:
    """
    Rank chunks by cosine similarity to query embedding.
    chunk_rows: list of dicts with keys: id, doc_id, text, page, embedding_json (JSON string), filename
    """
    query_emb = get_embedding(query)
    if not query_emb:
        return []  # Caller should fall back to BM25

    results = []
    for row in chunk_rows:
        emb_raw = row.get("embedding_json") or row.get("embedding")
        if not emb_raw:
            continue
        try:
            chunk_emb = json.loads(emb_raw) if isinstance(emb_raw, str) else emb_raw
        except Exception:
            continue
        score = cosine_similarity(query_emb, chunk_emb)
        if score >= min_score:
            results.append({
                "chunk_id": row.get("id") or row.get("chunk_id"),
                "doc_id": row.get("doc_id"),
                "filename": row.get("filename", ""),
                "text": row.get("text", ""),
                "page": row.get("page", 1),
                "score": score,
                "method": "semantic",
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def check_embedding_model_available() -> dict:
    """Check if the embedding model is loaded in Ollama."""
    try:
        import requests
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            available = any(EMBEDDING_MODEL in m for m in models)
            return {
                "available": available,
                "model": EMBEDDING_MODEL,
                "all_models": models,
                "message": f"{'✓' if available else '✗'} {EMBEDDING_MODEL}",
            }
    except Exception as e:
        return {"available": False, "model": EMBEDDING_MODEL, "message": str(e)}
    return {"available": False, "model": EMBEDDING_MODEL, "message": "Ollama not reachable"}
