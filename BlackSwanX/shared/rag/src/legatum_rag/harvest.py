"""LLM harvest — extract entities, relations, and a summary from a document."""
from __future__ import annotations
import logging
from functools import lru_cache
from .config import get_settings
from .models import DocHarvest, Entity, Harvest, Mention, Relation
_log = logging.getLogger("legatum_rag.harvest")
_PROMPT = (
    "You are a knowledge-graph harvester. Read the document text and populate the "
    "Harvest structure:\n"
    "- entities: an ARRAY of objects, each with fields name, type, and description.\n"
    "- relations: an ARRAY of objects, each with fields source, target, type, and description.\n"
    "- summary: a 2-3 sentence string about this section.\n"
    "Only extract what the text supports; prefer fewer, high-confidence items.\n\n"
    "--- document text ---\n{text}"
)
@lru_cache
def _structured_llm():
    from .llm import chat_model  # noqa: PLC0415
    return chat_model().with_structured_output(Harvest)
def harvest_text(text: str) -> Harvest:
    """Extract a :class:`Harvest` from one window of text."""
    text = (text or "").strip()
    if not text:
        return Harvest()
    return _structured_llm().invoke(_PROMPT.format(text=text[:12000]))
def _page_texts(doc_id: str) -> list[tuple[int, str]]:
    from .db import connect  # noqa: PLC0415
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page, content FROM pages WHERE doc_id = %s ORDER BY page",
                (doc_id,),
            )
            return [(p, c or "") for p, c in cur.fetchall()]
def _windows(
    pages: list[tuple[int, str]], size: int, overlap: int
) -> list[tuple[list[int], str]]:
    """Slide a window of `size` pages with `overlap`."""
    size = max(1, size)
    step = max(1, size - max(0, overlap))
    out: list[tuple[list[int], str]] = []
    i, n = 0, len(pages)
    while i < n:
        chunk = pages[i : i + size]
        nums = [p for p, _ in chunk]
        text = "\n\n".join(f"[page {p}]\n{t}" for p, t in chunk if t.strip())
        if text.strip():
            out.append((nums, text))
        if i + size >= n:
            break
        i += step
    return out
def _merge_windows(per_window: list[tuple[list[int], Harvest]]) -> DocHarvest:
    ents: dict[str, Entity] = {}
    rels: dict[tuple[str, str, str], Relation] = {}
    mentions: set[tuple[str, int]] = set()
    summaries: list[str] = []
    for nums, h in per_window:
        for e in h.entities:
            name = e.name.strip()
            key = name.lower()
            if not key:
                continue
            if key not in ents:
                ents[key] = Entity(
                    name=name, type=e.type.strip(), description=e.description.strip()
                )
            else:
                cur = ents[key]
                if not cur.type and e.type.strip():
                    cur.type = e.type.strip()
                if len(e.description.strip()) > len(cur.description):
                    cur.description = e.description.strip()
            for p in nums:
                mentions.add((key, p))
        for r in h.relations:
            sk, tk, typ = (
                r.source.strip().lower(),
                r.target.strip().lower(),
                r.type.strip(),
            )
            if not sk or not tk:
                continue
            k = (sk, tk, typ)
            if k not in rels:
                rels[k] = Relation(
                    source=r.source.strip(),
                    target=r.target.strip(),
                    type=typ,
                    description=r.description.strip(),
                )
        if h.summary.strip():
            summaries.append(h.summary.strip())
    summary = " ".join(summaries)[:1500]
    return DocHarvest(
        entities=list(ents.values()),
        relations=list(rels.values()),
        mentions=[Mention(name_key=k, page=p) for k, p in sorted(mentions)],
        summary=summary,
        windows=len(per_window),
    )
def harvest_document(
    doc_id: str, window: int | None = None, overlap: int | None = None
) -> DocHarvest:
    """Windowed harvest of a stored document → merged entities/relations/mentions."""
    s = get_settings()
    size = window if window is not None else s.harvest_window
    ov = overlap if overlap is not None else s.harvest_overlap
    pages = _page_texts(doc_id)
    wins = _windows(pages, size, ov)
    _log.info("harvest %s: %d windows (size=%d overlap=%d)", doc_id, len(wins), size, ov)
    per_window: list[tuple[list[int], Harvest]] = []
    for k, (nums, text) in enumerate(wins, 1):
        try:
            h = harvest_text(text)
        except Exception as exc:  # noqa: BLE001
            _log.warning("  window %d/%d (pages %s) FAILED: %s", k, len(wins), nums, str(exc)[:140])
            continue
        _log.info(
            "  window %d/%d (pages %s) → %d entities, %d relations",
            k, len(wins), nums, len(h.entities), len(h.relations),
        )
        per_window.append((nums, h))
    doc = _merge_windows(per_window)
    doc.pages = len(pages)
    return doc
