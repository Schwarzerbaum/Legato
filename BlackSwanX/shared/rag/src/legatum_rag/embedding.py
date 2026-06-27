"""Multimodal embedder — ColModernVBERT via ``colpali-engine``."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable
import numpy as np
from .config import get_settings
@runtime_checkable
class Embedder(Protocol):
    """The contract the store + retriever depend on (swappable model backend)."""
    def embed_images(self, image_paths: list[str | Path]) -> list[np.ndarray]: ...
    def embed_queries(self, queries: list[str]) -> list[np.ndarray]: ...
    def score(self, query: np.ndarray, docs: list[np.ndarray]) -> list[float]: ...
def _select_device(pref: str):
    import torch  # noqa: PLC0415
    pref = (pref or "auto").lower()
    if pref != "auto":
        return pref
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"
class ColModernVBertEmbedder:
    """`colpali-engine` ColModernVBERT wrapper (lazy model load, batched)."""
    def __init__(self, model_name: str | None = None, device: str | None = None):
        s = get_settings()
        self.model_name = model_name or s.embed_model
        self.device_pref = device or s.embed_device
        self._model = None
        self._processor = None
        self._device: str | None = None
    def _load(self):
        if self._model is not None:
            return
        import torch  # noqa: PLC0415
        from colpali_engine.models import (  # noqa: PLC0415
            ColModernVBert,
            ColModernVBertProcessor,
        )
        self._device = _select_device(self.device_pref)
        dtype = torch.bfloat16 if self._device == "cuda" else torch.float32
        self._model = (
            ColModernVBert.from_pretrained(
                self.model_name, torch_dtype=dtype, device_map=self._device
            )
            .eval()
        )
        self._processor = ColModernVBertProcessor.from_pretrained(self.model_name)
    @property
    def device(self) -> str:
        self._load()
        return self._device or "cpu"
    def _run(self, batch) -> list[np.ndarray]:
        import torch  # noqa: PLC0415
        batch = {k: v.to(self._model.device) for k, v in batch.items()}
        with torch.no_grad():
            out = self._model(**batch)
        return [row.to(torch.float32).cpu().numpy() for row in out]
    def embed_images(self, image_paths: list[str | Path]) -> list[np.ndarray]:
        self._load()
        from PIL import Image  # noqa: PLC0415
        images = [Image.open(p).convert("RGB") for p in image_paths]
        batch = self._processor.process_images(images)
        return self._run(batch)
    def embed_queries(self, queries: list[str]) -> list[np.ndarray]:
        self._load()
        batch = self._processor.process_queries(list(queries))
        return self._run(batch)
    def score(self, query: np.ndarray, docs: list[np.ndarray]) -> list[float]:
        """MaxSim score of one query against each doc embedding (rerank helper)."""
        if not docs:
            return []
        self._load()
        import torch  # noqa: PLC0415
        q = [torch.from_numpy(query)]
        d = [torch.from_numpy(x) for x in docs]
        scores = self._processor.score_multi_vector(q, d)
        return scores[0].tolist()
@lru_cache
def get_embedder() -> ColModernVBertEmbedder:
    return ColModernVBertEmbedder()
