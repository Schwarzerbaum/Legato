"""Ingestion — PDF → page images (+ extracted text) → embeddings → store."""
from __future__ import annotations
import hashlib
import logging
import re
from pathlib import Path
from .config import get_settings
from .db import connect
from .embedding import get_embedder
from .models import IngestResult
from .store import get_store
_log = logging.getLogger("legatum_rag.ingest")
def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "doc"
def doc_id_for(pdf_path: str | Path) -> str:
    p = Path(pdf_path)
    digest = hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:8]
    return f"{_slug(p.stem)}-{digest}"
def render_pdf(pdf_path: str | Path, doc_id: str, dpi: int = 150) -> list[dict]:
    """Render each page to a PNG and pull its text layer."""
    import pypdfium2 as pdfium  # noqa: PLC0415
    out_dir = get_settings().pages_dir / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages: list[dict] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            image = page.render(scale=dpi / 72).to_pil()
            image_path = out_dir / f"{i:04d}.png"
            image.save(image_path)
            try:
                text = page.get_textpage().get_text_range()
            except Exception:
                text = ""
            pages.append(
                {"page": i, "image_path": str(image_path), "text": text or ""}
            )
    finally:
        pdf.close()
    return pages
def _record_document(doc_id: str, title: str, path: str, n_pages: int) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (doc_id, title, path, pages) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (doc_id) DO UPDATE SET "
                "title = EXCLUDED.title, path = EXCLUDED.path, pages = EXCLUDED.pages",
                (doc_id, title, path, n_pages),
            )
def ingest_pdf(
    pdf_path: str | Path,
    title: str | None = None,
    dpi: int = 150,
    harvest: bool | None = None,
) -> IngestResult:
    """Full ingest: render → OCR → embed → store, then (by default) harvest into the graph."""
    pdf_path = Path(pdf_path)
    doc_id = doc_id_for(pdf_path)
    title = title or pdf_path.stem
    _log.info("ingest '%s' → %s — rendering…", pdf_path.name, doc_id)
    pages = render_pdf(pdf_path, doc_id, dpi=dpi)
    n = len(pages)
    _log.info("rendered %d pages", n)
    _record_document(doc_id, title, str(pdf_path.resolve()), n)
    _log.info(
        "loading embedding model %s (first run downloads ~250MB)…",
        get_settings().embed_model,
    )
    embedder = get_embedder()
    _log.info("embedding on device: %s", embedder.device)
    store = get_store()
    for pg in pages:
        emb = embedder.embed_images([pg["image_path"]])[0]
        text = pg["text"]
        store.add_page(doc_id, pg["page"], pg["image_path"], emb, content=text)
        _log.info(
            "page %d/%d stored — %d patch vectors, %d chars text",
            pg["page"] + 1, n, emb.shape[0], len(text),
        )
    result = IngestResult(doc_id=doc_id, title=title, pages=n)
    _log.info("DONE %s", doc_id)
    return result
