"""Sentence embedding via Ollama's small model.

Uses the cluster model (e.g., qwen2.5:3b) for embeddings.
Falls back to TF-IDF if Ollama embedding fails.
"""
import numpy as np
from backend.llm.client import embed


async def embed_posts(posts: list[dict]) -> np.ndarray:
    """Embed a list of posts using Ollama. Returns (n_posts, dim) array."""
    texts = [p.get("content", "")[:500] for p in posts]  # Truncate for speed

    try:
        vectors = await embed(texts)
        return np.array(vectors)
    except Exception:
        # Fallback: simple TF-IDF-like embedding using hash trick
        return _hash_embed(texts)


def _hash_embed(texts: list[str], dim: int = 128) -> np.ndarray:
    """Ultra-fast hash-based embedding fallback. No ML model needed."""
    vectors = np.zeros((len(texts), dim))
    for i, text in enumerate(texts):
        words = text.lower().split()
        for word in words:
            idx = hash(word) % dim
            vectors[i, idx] += 1.0
        # L2 normalize
        norm = np.linalg.norm(vectors[i])
        if norm > 0:
            vectors[i] /= norm
    return vectors
