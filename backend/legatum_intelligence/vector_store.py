"""
Legatum Intelligence — Vector Store abstraction.

Wraps Qdrant (primary) with an in-memory fallback so the system
runs in hackathon environments without a running Qdrant instance.

Collections:
    giver_identities   — GiverIdentityProfile   (384-dim cosine)
    ngo_profiles       — NGOCredibilityProfile   (384-dim cosine)
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any
from uuid import UUID

# Optional Qdrant client — falls back gracefully
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, FieldCondition, Filter, MatchAny, MatchValue,
        PointStruct, Range, VectorParams,
    )
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False

from .schemas import GiverIdentityProfile, NGOCredibilityProfile

# ── Embedding model (sentence-transformers, no API key needed) ────────────────
try:
    from sentence_transformers import SentenceTransformer
    _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    _EMBED_AVAILABLE = True
except Exception:
    _EMBED_AVAILABLE = False


def embed(text: str) -> list[float]:
    """Return 384-dim normalised embedding. Falls back to deterministic pseudo-vector."""
    if _EMBED_AVAILABLE:
        return _EMBED_MODEL.encode(text, normalize_embeddings=True).tolist()
    # Deterministic fallback: hash-seeded pseudo-vector (for CI / demo without GPU)
    digest = hashlib.sha256(text.encode()).digest()
    raw = [(b / 127.5) - 1.0 for b in digest]
    # Pad to 384 dims by repeating
    repeated = (raw * (384 // len(raw) + 1))[:384]
    norm = math.sqrt(sum(x * x for x in repeated)) or 1.0
    return [x / norm for x in repeated]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb  = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


# ── In-memory fallback store ──────────────────────────────────────────────────

class _InMemoryStore:
    def __init__(self) -> None:
        self._giver: dict[str, dict[str, Any]] = {}
        self._ngo:   dict[str, dict[str, Any]] = {}

    def upsert_giver(self, profile: GiverIdentityProfile) -> None:
        uid = str(profile.user_id)
        self._giver[uid] = {
            "vector": profile.giver_embedding or embed(profile.giver_narrative),
            "payload": json.loads(profile.model_dump_json()),
        }

    def upsert_ngo(self, profile: NGOCredibilityProfile) -> None:
        nid = str(profile.ngo_id)
        self._ngo[nid] = {
            "vector": profile.mission_embedding or embed(profile.mission_statement),
            "payload": json.loads(profile.model_dump_json()),
        }

    def search_ngos(
        self,
        query_text: str,
        sdg_filter: list[int],
        top_k: int,
    ) -> list[dict[str, Any]]:
        qvec = embed(query_text)
        results = []
        for nid, point in self._ngo.items():
            payload = point["payload"]
            if sdg_filter:
                if not any(s in payload.get("sdgs", []) for s in sdg_filter):
                    continue
            score = _cosine(qvec, point["vector"])
            results.append({"score": score, "payload": payload})
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def get_giver(self, user_id: UUID) -> dict[str, Any] | None:
        return self._giver.get(str(user_id))


_mem_store = _InMemoryStore()


# ── Public interface ──────────────────────────────────────────────────────────

class VectorStore:
    """
    Thin facade — routes to Qdrant when available, in-memory otherwise.
    Replace qdrant_url in production with your Qdrant Cloud / self-hosted URL.
    """

    GIVER_COLLECTION = "giver_identities"
    NGO_COLLECTION   = "ngo_profiles"
    DIMS             = 384

    def __init__(self, qdrant_url: str = "http://localhost:6333") -> None:
        self._qdrant: QdrantClient | None = None
        if _QDRANT_AVAILABLE:
            try:
                self._qdrant = QdrantClient(url=qdrant_url, timeout=2)
                self._ensure_collections()
            except Exception:
                self._qdrant = None

    def _ensure_collections(self) -> None:
        assert self._qdrant
        existing = {c.name for c in self._qdrant.get_collections().collections}
        for name in (self.GIVER_COLLECTION, self.NGO_COLLECTION):
            if name not in existing:
                self._qdrant.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self.DIMS, distance=Distance.COSINE),
                )

    # ── Giver Identity ────────────────────────────────────────────────────────

    def upsert_giver(self, profile: GiverIdentityProfile) -> GiverIdentityProfile:
        vector = embed(profile.giver_narrative)
        profile.giver_embedding = vector

        if self._qdrant:
            self._qdrant.upsert(
                collection_name=self.GIVER_COLLECTION,
                points=[PointStruct(
                    id=str(profile.user_id),
                    vector=vector,
                    payload=json.loads(profile.model_dump_json(exclude={"giver_embedding"})),
                )],
            )
        else:
            _mem_store.upsert_giver(profile)
        return profile

    def get_giver(self, user_id: UUID) -> GiverIdentityProfile | None:
        if self._qdrant:
            results = self._qdrant.retrieve(
                collection_name=self.GIVER_COLLECTION,
                ids=[str(user_id)],
                with_payload=True,
                with_vectors=True,
            )
            if not results:
                return None
            p = results[0]
            data = p.payload or {}
            data["giver_embedding"] = p.vector or []
            return GiverIdentityProfile(**data)
        raw = _mem_store.get_giver(user_id)
        if not raw:
            return None
        return GiverIdentityProfile(**raw["payload"])

    # ── NGO Profiles ──────────────────────────────────────────────────────────

    def upsert_ngo(self, profile: NGOCredibilityProfile) -> NGOCredibilityProfile:
        vector = embed(profile.mission_statement)
        profile.mission_embedding = vector
        profile.compute_credibility()

        if self._qdrant:
            payload = json.loads(profile.model_dump_json(exclude={"mission_embedding"}))
            self._qdrant.upsert(
                collection_name=self.NGO_COLLECTION,
                points=[PointStruct(
                    id=str(profile.ngo_id),
                    vector=vector,
                    payload=payload,
                )],
            )
        else:
            _mem_store.upsert_ngo(profile)
        return profile

    def search_ngos(
        self,
        query_text: str,
        sdg_filter: list[int] | None = None,
        geography: list[str] | None = None,
        min_credibility: float = 50.0,
        top_k: int = 5,
    ) -> list[tuple[float, NGOCredibilityProfile]]:
        """
        Semantic search over NGO mission embeddings with hard-metadata filters.

        Qdrant filter: sdgs ∈ sdg_filter AND credibility_score ≥ min_credibility
        """
        qvec = embed(query_text)

        if self._qdrant:
            conditions = []
            if sdg_filter:
                conditions.append(
                    FieldCondition(key="sdgs", match=MatchAny(any=sdg_filter))
                )
            conditions.append(
                FieldCondition(key="credibility_score", range=Range(gte=min_credibility))
            )
            hits = self._qdrant.search(
                collection_name=self.NGO_COLLECTION,
                query_vector=qvec,
                query_filter=Filter(must=conditions),
                limit=top_k,
                with_payload=True,
                with_vectors=True,
            )
            results = []
            for h in hits:
                data = h.payload or {}
                data["mission_embedding"] = h.vector or []
                results.append((h.score, NGOCredibilityProfile(**data)))
            return results

        # In-memory fallback
        raw = _mem_store.search_ngos(
            query_text, sdg_filter or [], top_k * 3
        )
        out = []
        for r in raw:
            profile = NGOCredibilityProfile(**r["payload"])
            if profile.credibility_score >= min_credibility:
                out.append((r["score"], profile))
        return out[:top_k]


# Singleton — import this everywhere
vector_store = VectorStore()
