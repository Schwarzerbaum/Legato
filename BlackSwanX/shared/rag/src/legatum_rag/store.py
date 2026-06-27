"""Multi-vector page store — persist ColModernVBERT patch embeddings and
retrieve pages by **MaxSim** (late interaction)."""
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np
from .db import connect
@runtime_checkable
class VectorStore(Protocol):
    def add_page(
        self, doc_id: str, page: int, image_path: str, patches: np.ndarray
    ) -> None: ...
    def search(
        self, query: np.ndarray, k: int = 5, candidate_pages: int = 50
    ) -> list[tuple[str, int, float]]: ...
def _pooled(matrix: np.ndarray) -> np.ndarray:
    """Mean-pool a (n_tokens, dim) matrix to a single (dim,) vector for ANN."""
    v = np.asarray(matrix, dtype=np.float32).mean(axis=0)
    n = np.linalg.norm(v)
    return v / n if n else v
def maxsim(query: np.ndarray, doc: np.ndarray) -> float:
    """Late-interaction score: Σ_i max_j (q_i · d_j)."""
    q = np.asarray(query, dtype=np.float32)
    d = np.asarray(doc, dtype=np.float32)
    if q.size == 0 or d.size == 0:
        return 0.0
    return float((q @ d.T).max(axis=1).sum())
class PgVectorStore:
    """pgvector-backed multi-vector store (works on the VectorChord container)."""
    def _register(self, conn) -> None:
        from pgvector.psycopg import register_vector  # noqa: PLC0415
        register_vector(conn)
    def add_page(
        self,
        doc_id: str,
        page: int,
        image_path: str,
        patches: np.ndarray,
        content: str = "",
    ) -> None:
        patches = np.asarray(patches, dtype=np.float32)
        pooled = _pooled(patches)
        rows = [
            (doc_id, page, i, patches[i]) for i in range(patches.shape[0])
        ]
        with connect() as conn:
            self._register(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pages (doc_id, page, image_path, pooled, content) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (doc_id, page) DO UPDATE SET "
                    "image_path = EXCLUDED.image_path, pooled = EXCLUDED.pooled, "
                    "content = EXCLUDED.content",
                    (doc_id, page, image_path, pooled, content),
                )
                cur.execute(
                    "DELETE FROM page_patches WHERE doc_id = %s AND page = %s",
                    (doc_id, page),
                )
                cur.executemany(
                    "INSERT INTO page_patches (doc_id, page, patch_idx, embedding) "
                    "VALUES (%s, %s, %s, %s)",
                    rows,
                )
    def search(
        self, query: np.ndarray, k: int = 5, candidate_pages: int = 50
    ) -> list[tuple[str, int, float]]:
        query = np.asarray(query, dtype=np.float32)
        qbar = _pooled(query)
        with connect() as conn:
            self._register(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page FROM pages "
                    "ORDER BY pooled <=> %s LIMIT %s",
                    (qbar, candidate_pages),
                )
                candidates = cur.fetchall()
                scored: list[tuple[str, int, float]] = []
                for doc_id, page in candidates:
                    cur.execute(
                        "SELECT embedding FROM page_patches "
                        "WHERE doc_id = %s AND page = %s ORDER BY patch_idx",
                        (doc_id, page),
                    )
                    mat = np.asarray([r[0] for r in cur.fetchall()], dtype=np.float32)
                    scored.append((doc_id, page, maxsim(query, mat)))
        scored.sort(key=lambda t: t[2], reverse=True)
        return scored[:k]
def get_store() -> PgVectorStore:
    return PgVectorStore()
