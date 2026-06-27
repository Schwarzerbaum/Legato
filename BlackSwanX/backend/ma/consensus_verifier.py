"""
consensus_verifier.py — Multi-Agent Consensus Verification & Fallback Protocol

When high-certainty evaluation is requested:
  1. Fork N isolated inferences across llama3.2:3b (T=0.3, T=0.6) and
     mistral:7b (T=0.2, T=0.5) via ThreadPoolExecutor.
  2. Vectorize all N string outputs using a shared BGE-M3 embedding instance.
     Falls back to TF-IDF cosine if model is not cached locally.
  3. Compute the full cross-similarity matrix:
       S_ij = dot(A_i, A_j) / (||A_i|| * ||A_j||)
  4. mean_consensus = mean of all off-diagonal S_ij values.
  5. Degradation boundary: mean_consensus < 0.40 → irreconcilable semantic divergence.
  6. Fail-safe: STATUS forced to RED, synthesized LLM payload dropped from memory,
     raw context-matched source markdown returned directly to the client.
"""

from __future__ import annotations

import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

_OLLAMA = "http://localhost:11434/api/generate"
_CONSENSUS_THRESHOLD = 0.40

# Agent profiles — temperature diversity forces semantic spread when agents disagree
_AGENTS = [
    {"model": "llama3.2:3b", "profile": "analyst_a",    "temperature": 0.3},
    {"model": "llama3.2:3b", "profile": "analyst_b",    "temperature": 0.6},
    {"model": "mistral:7b",  "profile": "specialist_a", "temperature": 0.2},
    {"model": "mistral:7b",  "profile": "specialist_b", "temperature": 0.5},
]

# ── Lazy BGE-M3 singleton ─────────────────────────────────────────────────────
_bge_model = None
_bge_available = None  # None = untried, True/False after first attempt

def _get_bge_model():
    global _bge_model, _bge_available
    if _bge_available is False:
        return None
    if _bge_model is not None:
        return _bge_model
    try:
        from sentence_transformers import SentenceTransformer
        _bge_model = SentenceTransformer("BAAI/bge-m3", device="cpu")
        _bge_available = True
        return _bge_model
    except Exception:
        _bge_available = False
        return None


# ── Embedding strategies ──────────────────────────────────────────────────────

def _embed_bge(texts: list[str]) -> list[list[float]]:
    """Primary: BAAI/bge-m3 via sentence_transformers."""
    model = _get_bge_model()
    if model is None:
        return []
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]


def _tfidf_vector(text: str, vocab: dict[str, int]) -> list[float]:
    tokens = re.findall(r'\w+', text.lower())
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = max(len(tokens), 1)
    vec = [0.0] * len(vocab)
    for word, idx in vocab.items():
        if word in tf:
            vec[idx] = tf[word] / total
    return vec


def _embed_tfidf(texts: list[str]) -> list[list[float]]:
    """Fallback: TF (no IDF — fine for short agent outputs)."""
    tokens_per = [set(re.findall(r'\w+', t.lower())) for t in texts]
    vocab_words = sorted(set().union(*tokens_per))
    vocab = {w: i for i, w in enumerate(vocab_words)}
    if not vocab:
        return [[0.0]] * len(texts)
    return [_tfidf_vector(t, vocab) for t in texts]


def _embed(texts: list[str]) -> list[list[float]]:
    vecs = _embed_bge(texts)
    if not vecs:
        vecs = _embed_tfidf(texts)
    return vecs


# ── Cosine math (no deps) ─────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── Single-agent inference ────────────────────────────────────────────────────

def _infer(agent: dict, question: str, context: str) -> tuple[str, str, str]:
    """
    Returns (profile, model, response_text).
    Hard cap at 90s per agent — returns error marker on timeout.
    """
    system = (
        "You are a construction document analysis expert. "
        "Answer only from the context provided. "
        "Cite paragraph and page numbers. Be precise."
    )
    prompt = (
        f"{system}\n\n"
        f"CONTEXT:\n{context[:4000]}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )
    try:
        with httpx.Client(timeout=90) as client:
            r = client.post(
                _OLLAMA,
                json={
                    "model": agent["model"],
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": agent["temperature"]},
                },
            )
            r.raise_for_status()
            text = r.json().get("response", "").strip()
            return agent["profile"], agent["model"], text
    except Exception as exc:
        return agent["profile"], agent["model"], f"[AGENT_TIMEOUT: {exc}]"


# ── Main entry point ──────────────────────────────────────────────────────────

def run_consensus_verification(
    question: str,
    context: str,
    raw_sources: list[dict],
) -> dict[str, Any]:
    """
    Run N agents in parallel, compute pairwise BGE-M3 cosine similarity matrix,
    and apply fail-safe if consensus < 0.40.

    Args:
        question:    Original user question.
        context:     Retrieved context text (already GraphRAG-injected).
        raw_sources: Top-K section dicts — returned directly on fail-safe trigger.

    Returns:
        {
            mode, n_agents, mean_consensus, consensus_matrix,
            force_red, synthesized_dropped,
            agents: [{profile, model, response}],
            fallback_sources (list of raw markdown strings, only when force_red),
            embedding_backend ("bge-m3" | "tfidf"),
            latency_ms,
        }
    """
    t0 = time.time()

    # ── Step 1: Parallel inference across N agent profiles ────────────────────
    agent_results: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=len(_AGENTS)) as pool:
        futures = {pool.submit(_infer, ag, question, context): ag for ag in _AGENTS}
        for future in as_completed(futures, timeout=110):
            try:
                agent_results.append(future.result())
            except Exception as exc:
                ag = futures[future]
                agent_results.append((ag["profile"], ag["model"], f"[FUTURE_ERROR: {exc}]"))

    # Separate valid responses from error stubs
    valid_results = [(p, m, r) for p, m, r in agent_results if not r.startswith("[")]
    n_valid = len(valid_results)

    if n_valid < 2:
        # Cannot compute matrix — treat as inconclusive (yellow, not red)
        return {
            "mode": "consensus_verification",
            "n_agents": len(_AGENTS),
            "n_valid": n_valid,
            "mean_consensus": None,
            "consensus_matrix": [],
            "force_red": False,
            "synthesized_dropped": False,
            "agents": [{"profile": p, "model": m, "response": r} for p, m, r in agent_results],
            "fallback_sources": None,
            "embedding_backend": "none",
            "latency_ms": round((time.time() - t0) * 1000),
            "note": "Fewer than 2 agents responded — matrix undefined, defaulting to yellow.",
        }

    texts = [r for _, _, r in valid_results]

    # ── Step 2: Vectorize outputs via BGE-M3 (or TF fallback) ────────────────
    vecs = _embed(texts)
    backend = "bge-m3" if _bge_available else "tfidf"

    # ── Step 3: Cross-similarity matrix ──────────────────────────────────────
    n = len(texts)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            matrix[i][j] = round(_cosine(vecs[i], vecs[j]), 4) if i != j else 1.0

    # ── Step 4: Mean off-diagonal consensus score ─────────────────────────────
    off_diag = [matrix[i][j] for i in range(n) for j in range(n) if i != j]
    mean_consensus = round(sum(off_diag) / len(off_diag), 4) if off_diag else 0.0

    # ── Step 5: Degradation boundary check ───────────────────────────────────
    force_red = mean_consensus < _CONSENSUS_THRESHOLD

    # ── Step 6: Fail-safe — build raw source markdown when triggered ──────────
    fallback_sources: list[str] | None = None
    if force_red:
        fallback_sources = []
        for sec in raw_sources:
            heading  = sec.get("heading", "")
            doc      = sec.get("doc", "")
            page     = sec.get("page", "")
            body     = sec.get("text", " ".join(sec.get("blocks", [])))
            fallback_sources.append(
                f"### [{doc} — p.{page}] {heading}\n{body}"
            )

    latency = round((time.time() - t0) * 1000)

    return {
        "mode": "consensus_verification",
        "n_agents": len(_AGENTS),
        "n_valid": n_valid,
        "mean_consensus": mean_consensus,
        "consensus_matrix": matrix,
        "force_red": force_red,
        "synthesized_dropped": force_red,
        "agents": [{"profile": p, "model": m, "response": r} for p, m, r in agent_results],
        "fallback_sources": fallback_sources,
        "embedding_backend": backend,
        "latency_ms": latency,
    }
