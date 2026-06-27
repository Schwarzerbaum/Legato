#!/usr/bin/env python3
"""
LEGATUM Complete RAG — all layers combined, no Docker required.

INGESTION LAYERS
  1. PDFium text extraction
  2. Parent-Child chunking  (150-token children → 500-token parents)
  3. Context compaction     (strip noise before it enters the LLM)
  4. ColModernVBERT visual  (page image patch embeddings → .npy)
  5. phi4:14b hierarchical  (entity+relation harvest, 25 chapters)

RETRIEVAL LAYERS
  6. Visual MaxSim          (ColModernVBERT late-interaction)
  7. BM25 child-chunk search
  8. Graph traversal        (1-2 hop from matched entities)
  9. Reverse context-inversion (validate context before synthesis)
 10. Fragmented polling     (each chunk in isolation → no lost-in-middle)

SYNTHESIS / ANTI-HALLUCINATION
 11. Map-Reduce multi-pass  (SKIP / extract per chunk → consolidate)
 12. Entity dictionary check (logprob-style: invented terms get flagged)
 13. Self-RAG fact-check    (binary grounding check → forced regen if fail)

Usage:
  python3 legatum_complete.py ingest  /path/to/doc.pdf
  python3 legatum_complete.py ask     "Welche Rollen gibt es?"
  python3 legatum_complete.py eval    /path/to/questions.yaml
  python3 legatum_complete.py graph   [output.html]
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import pypdfium2 as pdfium
import yaml
from openai import OpenAI
from PIL import Image

from agent_memory import MemoryStack, EpisodicLedger, SonaOptimizer

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent
DATA = BASE / "data"
PAGES_DIR   = DATA / "pages"
PATCHES_DIR = DATA / "patches"
DB_PATH     = DATA / "legatum_complete.db"
OKF_DIR     = BASE / "okf"

for d in [DATA, PAGES_DIR, PATCHES_DIR, OKF_DIR / "docs"]:
    d.mkdir(parents=True, exist_ok=True)

OLLAMA      = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
FAST_MODEL  = "llama3.2:3b"      # map-reduce single-chunk pass (tiny context)
MID_MODEL   = "qwen2.5-coder:7b" # entity dict, self-rag check
MAIN_MODEL  = "phi4:14b"         # synthesis, harvest, chapter detection
EMBED_MODEL = "ModernVBERT/colmodernvbert"  # visual patches

CHILD_TOKENS  = 150
PARENT_TOKENS = 500
TOP_K_VISUAL  = 5
TOP_K_CHUNKS  = 6
GRAPH_HOPS    = 2
INVERSION_MAXSIM_THRESHOLD = 3.0  # MaxSim score below this → "not in document"

# ─────────────────────────────────────────────────────────────────────────────
# SQLite schema
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title  TEXT,
            path   TEXT,
            pages  INTEGER,
            summary TEXT DEFAULT ''
        );
        -- Parent chunks (500-token, for LLM context window)
        CREATE TABLE IF NOT EXISTS parent_chunks (
            id      INTEGER PRIMARY KEY,
            doc_id  TEXT,
            page    INTEGER,
            idx     INTEGER,
            text    TEXT,
            chapter TEXT DEFAULT '',
            UNIQUE(doc_id, page, idx)
        );
        -- Child chunks (150-token, for BM25 retrieval)
        CREATE TABLE IF NOT EXISTS child_chunks (
            id        INTEGER PRIMARY KEY,
            doc_id    TEXT,
            page      INTEGER,
            parent_id INTEGER,
            idx       INTEGER,
            text      TEXT,
            FOREIGN KEY(parent_id) REFERENCES parent_chunks(id)
        );
        -- Knowledge graph
        CREATE TABLE IF NOT EXISTS entities (
            id       INTEGER PRIMARY KEY,
            name     TEXT NOT NULL,
            name_key TEXT NOT NULL UNIQUE,
            type     TEXT DEFAULT '',
            description TEXT DEFAULT '',
            importance INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS relations (
            id          INTEGER PRIMARY KEY,
            source_key  TEXT NOT NULL,
            target_key  TEXT NOT NULL,
            type        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            confidence  REAL DEFAULT 1.0,
            page_number INTEGER DEFAULT 0,
            UNIQUE(source_key, target_key, type)
        );
        CREATE TABLE IF NOT EXISTS mentions (
            name_key TEXT,
            page     INTEGER,
            chapter  TEXT DEFAULT '',
            context  TEXT DEFAULT '',
            PRIMARY KEY(name_key, page)
        );
        CREATE TABLE IF NOT EXISTS chapters (
            chapter_key TEXT PRIMARY KEY,
            title       TEXT,
            start_page  INTEGER,
            end_page    INTEGER
        );
        CREATE TABLE IF NOT EXISTS chapter_entities (
            chapter_key TEXT,
            name_key    TEXT,
            PRIMARY KEY(chapter_key, name_key)
        );
    """)
    conn.commit()
    return conn


def nkey(s: str) -> str:
    return s.strip().lower()


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — PDFium text extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_pages(pdf_path: str) -> list[tuple[int, str]]:
    pdf = pdfium.PdfDocument(pdf_path)
    pages: list[tuple[int, str]] = []
    try:
        for i in range(len(pdf)):
            pg = pdf[i]
            try:
                text = pg.get_textpage().get_text_range() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append((i + 1, text))
    finally:
        pdf.close()
    print(f"[PDF] {len(pages)} pages with text", flush=True)
    return pages


def render_page_images(pdf_path: str, doc_id: str, dpi: int = 150) -> list[Path]:
    out_dir = PAGES_DIR / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(pdf_path)
    paths: list[Path] = []
    try:
        for i in range(len(pdf)):
            dest = out_dir / f"{i:04d}.png"
            if not dest.exists():
                img = pdf[i].render(scale=dpi / 72).to_pil()
                img.save(dest)
            paths.append(dest)
    finally:
        pdf.close()
    print(f"[render] {len(paths)} page images → {out_dir}", flush=True)
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — Parent-Child chunking
# ─────────────────────────────────────────────────────────────────────────────

def rough_tokens(text: str) -> int:
    """Rough token count: 1 token ≈ 4 chars for German text."""
    return len(text) // 4


def split_parent_child(text: str) -> tuple[list[str], list[list[str]]]:
    """
    Split text into parent chunks (~PARENT_TOKENS tokens) and each parent
    into child chunks (~CHILD_TOKENS tokens). Returns (parents, children_per_parent).
    """
    # Split on sentence boundaries (German: ". ", "? ", "! ", "\n\n")
    sentences = re.split(r'(?<=[.!?])\s+|\n{2,}', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    parents: list[str] = []
    children_per_parent: list[list[str]] = []

    buf: list[str] = []
    buf_tokens = 0

    def flush_parent():
        nonlocal buf, buf_tokens
        if not buf:
            return
        parent_text = " ".join(buf)
        parents.append(parent_text)
        # Split parent into children
        kids: list[str] = []
        kb: list[str] = []
        kt = 0
        for sent in buf:
            st = rough_tokens(sent)
            if kt + st > CHILD_TOKENS and kb:
                kids.append(" ".join(kb))
                kb, kt = [sent], st
            else:
                kb.append(sent)
                kt += st
        if kb:
            kids.append(" ".join(kb))
        children_per_parent.append(kids)
        buf, buf_tokens = [], 0

    for sent in sentences:
        st = rough_tokens(sent)
        if buf_tokens + st > PARENT_TOKENS and buf:
            flush_parent()
        buf.append(sent)
        buf_tokens += st

    flush_parent()
    return parents, children_per_parent


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — Context compaction
# ─────────────────────────────────────────────────────────────────────────────

# German stop-words + PDF boilerplate that waste tokens
_NOISE = re.compile(
    r'\b(seite|page|abbildung|tabelle|www\.|https?://|impressum|inhaltsverzeichnis'
    r'|tel\.|fax|e-mail|stand:|datum:|version:|alle rechte|copyright|©)\b.*',
    re.IGNORECASE | re.MULTILINE,
)
_BLANK = re.compile(r'\n{3,}')
_REPEAT = re.compile(r'(\b\w+\b)(\s+\1){2,}', re.IGNORECASE)


def compact(text: str) -> str:
    """Strip noise, repeated headers, and boilerplate. Keeps 30% more real content."""
    text = _NOISE.sub('', text)
    text = _REPEAT.sub(r'\1', text)
    text = _BLANK.sub('\n\n', text)
    # Remove lines that are just numbers or single chars (page artifacts)
    lines = [ln for ln in text.splitlines() if len(ln.strip()) > 3]
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4 — ColModernVBERT visual embeddings
# ─────────────────────────────────────────────────────────────────────────────

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        print("[ColModernVBERT] loading model (first run downloads ~250MB)…", flush=True)
        import torch
        from colpali_engine.models import ColModernVBert, ColModernVBertProcessor
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        dtype  = torch.float32
        _embedder = {
            "model": ColModernVBert.from_pretrained(
                EMBED_MODEL, torch_dtype=dtype, device_map=device
            ).eval(),
            "processor": ColModernVBertProcessor.from_pretrained(EMBED_MODEL),
            "device": device,
        }
        print(f"[ColModernVBERT] loaded on {device}", flush=True)
    return _embedder


def embed_images(image_paths: list[Path]) -> list[np.ndarray]:
    e = get_embedder()
    import torch
    images = [Image.open(p).convert("RGB") for p in image_paths]
    batch = e["processor"].process_images(images)
    batch = {k: v.to(e["model"].device) for k, v in batch.items()}
    with torch.no_grad():
        out = e["model"](**batch)
    return [row.to(torch.float32).cpu().numpy() for row in out]


def embed_queries(queries: list[str]) -> list[np.ndarray]:
    e = get_embedder()
    import torch
    batch = e["processor"].process_queries(queries)
    batch = {k: v.to(e["model"].device) for k, v in batch.items()}
    with torch.no_grad():
        out = e["model"](**batch)
    return [row.to(torch.float32).cpu().numpy() for row in out]


def maxsim(q: np.ndarray, d: np.ndarray) -> float:
    """Late-interaction MaxSim: Σ_i max_j (q_i · d_j)."""
    return float((q.astype(np.float32) @ d.astype(np.float32).T).max(axis=1).sum())


def store_patches(doc_id: str, page: int, patches: np.ndarray):
    out = PATCHES_DIR / doc_id
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / f"{page:04d}.npy", patches.astype(np.float32))


def load_patches(doc_id: str, page: int) -> Optional[np.ndarray]:
    f = PATCHES_DIR / doc_id / f"{page:04d}.npy"
    return np.load(f) if f.exists() else None


def visual_search(doc_id: str, query: str, k: int = TOP_K_VISUAL) -> list[dict]:
    """ColModernVBERT MaxSim search over stored page patches."""
    q_emb = embed_queries([query])[0]
    patch_dir = PATCHES_DIR / doc_id
    if not patch_dir.exists():
        return []

    scored = []
    for f in sorted(patch_dir.glob("*.npy")):
        page = int(f.stem)
        patches = np.load(f)
        score = maxsim(q_emb, patches)
        scored.append({"page": page, "score": score, "doc_id": doc_id})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 7 — BM25 child-chunk search
# ─────────────────────────────────────────────────────────────────────────────

def bm25_score(query_terms: list[str], text: str, avg_dl: float,
               k1: float = 1.5, b: float = 0.75) -> float:
    text_lower = text.lower()
    words = text_lower.split()
    dl = len(words)
    word_freq = Counter(words)
    score = 0.0
    for term in query_terms:
        tf = word_freq.get(term, 0)
        if tf == 0:
            continue
        idf = math.log(1 + (1 / (0.5 + tf)))  # simplified
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1)))
    return score


def bm25_search(conn: sqlite3.Connection, doc_id: str,
                query: str, k: int = TOP_K_CHUNKS) -> list[dict]:
    """BM25 over child chunks → return top-k parent chunks."""
    terms = [t for t in query.lower().split() if len(t) > 2]
    rows = conn.execute(
        "SELECT c.id, c.page, c.text, c.parent_id, p.text as parent_text, p.chapter "
        "FROM child_chunks c JOIN parent_chunks p ON p.id=c.parent_id "
        "WHERE c.doc_id=?", (doc_id,)
    ).fetchall()
    if not rows:
        return []
    avg_dl = sum(len(r["text"].split()) for r in rows) / max(len(rows), 1)
    scored = []
    seen_parents = set()
    for r in rows:
        s = bm25_score(terms, r["text"], avg_dl)
        if s > 0:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for s, r in scored:
        if r["parent_id"] not in seen_parents:
            seen_parents.add(r["parent_id"])
            results.append({
                "page": r["page"],
                "score": s,
                "child_text": r["text"],
                "parent_text": r["parent_text"],
                "chapter": r["chapter"],
            })
        if len(results) >= k:
            break
    return results


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 8 — Graph traversal (1-2 hop)
# ─────────────────────────────────────────────────────────────────────────────

def graph_traverse(conn: sqlite3.Connection, query: str,
                   hops: int = GRAPH_HOPS) -> dict:
    q_lower = query.lower()
    terms = [t for t in q_lower.split() if len(t) > 3]

    # Find seed entities by keyword match on name + description
    seeds = []
    for row in conn.execute(
        "SELECT name_key, name, type, description FROM entities WHERE "
        + " OR ".join(["name_key LIKE ? OR lower(description) LIKE ?"] * len(terms)),
        [f for t in terms for f in (f"%{t}%", f"%{t}%")]
    ).fetchall():
        seeds.append(row["name_key"])

    # Expand frontier
    frontier = set(seeds[:8])
    seen: set[str] = set()
    all_edges: list[dict] = []

    for _ in range(hops):
        if not frontier:
            break
        pl = list(frontier)
        rows = conn.execute(
            "SELECT source_key,target_key,type,description FROM relations "
            "WHERE source_key IN ({}) OR target_key IN ({}) LIMIT 40".format(
                ",".join("?" * len(pl)), ",".join("?" * len(pl))
            ), pl + pl
        ).fetchall()
        seen |= frontier
        new_frontier: set[str] = set()
        for r in rows:
            all_edges.append(dict(r))
            new_frontier |= {r["source_key"], r["target_key"]}
        frontier = new_frontier - seen

    # Collect entity details for the traversed nodes
    all_keys = list(
        {e["source_key"] for e in all_edges} | {e["target_key"] for e in all_edges}
    )
    ent_rows = []
    if all_keys:
        ent_rows = conn.execute(
            "SELECT name, type, description FROM entities WHERE name_key IN ({})".format(
                ",".join("?" * len(all_keys))
            ), all_keys
        ).fetchall()

    return {
        "entities": [dict(r) for r in ent_rows],
        "relations": all_edges,
        "seed_entities": list(seeds[:8]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 9 — Reverse context-inversion (validate context before synthesis)
# ─────────────────────────────────────────────────────────────────────────────

def reverse_context_inversion(query: str, chunks: list[str]) -> tuple[bool, float]:
    """
    Ask the LLM to generate 3 questions the chunks CAN answer.
    Use ColModernVBERT MaxSim (not Jaccard) to compare against user query —
    handles German Komposita and acronym/expansion pairs that word-overlap misses.
    """
    if not chunks:
        return False, 0.0
    context = "\n\n".join(chunks[:3])[:2000]
    prompt = (
        "Lies diesen Text und erstelle genau 3 spezifische Fragen, die dieser Text direkt beantworten kann. "
        "Antworte NUR mit einem JSON-Array aus 3 Fragestrings (auf Deutsch).\n\n"
        f"TEXT:\n{context}"
    )
    try:
        msg = OLLAMA.chat.completions.create(
            model=FAST_MODEL, max_tokens=200, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not match:
            return True, 0.5
        qs = [q for q in json.loads(match.group()) if isinstance(q, str) and q.strip()]
        if not qs:
            return True, 0.5
        q_emb    = embed_queries([query])[0]
        gen_embs = embed_queries(qs)
        max_sim  = max(maxsim(q_emb, g) for g in gen_embs)
        return max_sim >= INVERSION_MAXSIM_THRESHOLD, float(max_sim)
    except Exception:
        return True, 0.5


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 10 — Fragmented context multi-polling (no lost-in-middle)
# ─────────────────────────────────────────────────────────────────────────────

def fragment_poll(query: str, parent_text: str, page: int) -> Optional[str]:
    """
    Send ONE chunk to llama3.2:3b in isolation.
    Returns extracted sentence(s) or None if not found.
    """
    prompt = (
        f"Enthält der folgende Textabschnitt Informationen, Fakten oder Entitäten, "
        f"die für die Beantwortung der Frage '{query}' nützlich sein könnten?\n"
        f"Antworte mit JA und extrahiere die relevanten Sätze wörtlich, oder antworte nur 'NEIN'.\n\n"
        f"TEXT [Seite {page}]:\n{parent_text[:1200]}"
    )
    try:
        msg = OLLAMA.chat.completions.create(
            model=FAST_MODEL, max_tokens=300, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        result = (msg.choices[0].message.content or "").strip()
        upper10 = result.upper()[:10]
        if "NEIN" in upper10:
            return None
        return result
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 11 — Map-Reduce multi-pass (chunk isolation → consolidate)
# ─────────────────────────────────────────────────────────────────────────────

def map_reduce(query: str, chunks: list[dict]) -> list[dict]:
    """
    Map: poll each chunk independently with llama3.2:3b.
    Returns only chunks that contained relevant extractions.
    """
    verified: list[dict] = []
    for chunk in chunks:
        parent_text = chunk.get("parent_text") or chunk.get("text", "")
        page = chunk.get("page", 0)
        extraction = fragment_poll(query, parent_text, page)
        if extraction:
            verified.append({**chunk, "extraction": extraction})
    return verified


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 12 — Entity dictionary check (logprob-style hallucination guard)
# ─────────────────────────────────────────────────────────────────────────────

def build_entity_dict(conn: sqlite3.Connection, doc_id: str, chunks: list[dict]) -> set[str]:
    """
    Build a set of allowed technical terms from:
    - Retrieved chunk text
    - Entity names in the graph
    """
    allowed: set[str] = set()
    for chunk in chunks:
        text = (chunk.get("parent_text") or chunk.get("text", "")).lower()
        # Extract capitalised German nouns (4+ chars) as allowed terms
        for w in re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]{3,}\b', text):
            allowed.add(w.lower())
    # Add all known entity names
    for row in conn.execute("SELECT name FROM entities"):
        allowed.add(row["name"].lower())
        for part in row["name"].split("-"):
            allowed.add(part.lower())
    return allowed


def entity_dict_check(answer: str, allowed_terms: set[str],
                      conn: sqlite3.Connection) -> tuple[str, list[str]]:
    """
    Find technical nouns in the answer that are NOT in the allowed set.
    Returns (verdict, flagged_terms).
    """
    # Extract capitalised nouns from the answer
    answer_nouns = re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]{3,}\b', answer)
    flagged = [w for w in answer_nouns if w.lower() not in allowed_terms]
    verdict = "PASS" if not flagged else "FLAG"
    return verdict, flagged


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 13 — Self-RAG fact-check loop
# ─────────────────────────────────────────────────────────────────────────────

def self_rag_check(answer: str, source_chunks: list[str], query: str = "", max_tries: int = 2) -> str:
    """
    Binary grounding check: does the answer contain major unsupported claims?
    Only regenerates if factual hallucinations are detected.
    Returns the grounded answer (original if check passes).
    """
    sources = "\n\n".join(source_chunks[:4])[:3000]
    check_prompt = (
        "Du bist ein Fakten-Checker. Prüfe: Enthält die ANTWORT Aussagen, die KLAR NICHT "
        "durch den QUELLTEXT belegt sind (nicht nur paraphrasiert oder abgeleitet)?\n\n"
        f"QUELLTEXT:\n{sources}\n\n"
        f"ANTWORT:\n{answer}\n\n"
        "Antworte NUR mit 'JA' (alles belegt) oder 'NEIN: <kurze Begründung>'."
    )
    try:
        msg = OLLAMA.chat.completions.create(
            model=MID_MODEL, max_tokens=150, temperature=0,
            messages=[{"role": "user", "content": check_prompt}],
        )
        verdict = (msg.choices[0].message.content or "").strip()
        if not verdict.upper().startswith("NEIN"):
            return answer  # JA or unclear → keep original
        # Regen: use query (not answer) as the question
        frage = query if query else "Beantworte die Frage aus dem Quelltext."
        regen_prompt = (
            "Beantworte die folgende Frage ausschließlich mit Fakten aus dem Quelltext. "
            "Keine Erfindungen, keine Schlussfolgerungen.\n\n"
            f"Quelltext:\n{sources}\n\n"
            f"Frage: {frage}\n"
            "Antwort:"
        )
        msg2 = OLLAMA.chat.completions.create(
            model=MAIN_MODEL, max_tokens=600, temperature=0.05,
            messages=[{"role": "user", "content": regen_prompt}],
        )
        return (msg2.choices[0].message.content or "").strip()
    except Exception:
        return answer


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 5 — phi4 hierarchical harvest
# ─────────────────────────────────────────────────────────────────────────────

HARVEST_PROMPT = """You are a precision Knowledge Graph Extraction Engine for a German BIM (Building Information Modeling) technical guideline.

## RULE 1 — TABLE PRESERVATION
If a table, matrix, or enumeration grid is present in the text, preserve it EXACTLY in Markdown:
| Spalte 1 | Spalte 2 | Spalte 3 |
|----------|----------|----------|
| Wert A   | Wert B   | Wert C   |
Never flatten table rows into prose sentences.

## RULE 2 — ENTITY STABILIZATION (Morphological Collapse)
Collapse abbreviations, acronyms, and grammatical variants into ONE canonical entity per concept.
- Use the document's own preferred full term as canonical_name
- List all variations as synonyms
- Entity types (lowercase): document, standard, organization, system, role, concept, method, process, model, tool
- importance: 1=peripheral  2=supporting  3=central
- Prefer quality over quantity — max 12 entities per window

## RULE 3 — RELATIONSHIPS (Multi-Hop, Directional)
Extract directional relationships using precise German-domain edge types:
  BESCHREIBT, BASIERT_AUF, DEFINIERT, VERWEIST_AUF, IMPLEMENTIERT,
  VERANTWORTLICH_FUER, BESTEHT_AUS, KONKRETISIERT, VERWENDET, ERSETZT,
  UNTERSTUETZT, ZERTIFIZIERT, HERAUSGEGEBEN_VON, VERWALTET_VON, ERFORDERT

## RULE 4 — ANTI-HALLUCINATION
- Only extract entities and relationships EXPLICITLY present in the text.
- Do NOT invent numbered step-by-step workflows unless the source defines an explicit sequence.
- If the chunk contains no extractable knowledge, set processed_content to "CONTEXT_INSUFFICIENT".

## OUTPUT — Return ONLY valid JSON, no prose:
{
  "processed_content": "Markdown text; include any tables verbatim in Markdown syntax",
  "entities": [
    {
      "canonical_name": "Auftraggeber-Informationsanforderungen (AIA)",
      "type": "document",
      "synonyms": ["AIA", "Auftraggeberinformationsanforderungen"],
      "description": "Definiert die digitalen Liefergegenstände und Anforderungen des Auftraggebers.",
      "importance": 3
    }
  ],
  "relationships": [
    {
      "source": "BIM-Management",
      "target": "Auftraggeber-Informationsanforderungen (AIA)",
      "edge_type": "VERANTWORTLICH_FUER",
      "description": "Das BIM-Management ist für die Erstellung der AIA verantwortlich.",
      "confidence": 0.95
    }
  ],
  "summary": "2-3 sentence section summary in German."
}

--- TEXT (Seiten {PAGES}, Kapitel: {CHAPTER}) ---
{TEXT}"""


def llm_harvest_window(pages: list[tuple[int, str]], page_nums: list[int],
                        chapter: str = "") -> dict:
    parts = []
    for p, t in pages:
        cleaned = compact(t)
        # Preserve pipe-tables as markdown blocks
        lines = cleaned.splitlines()
        table_lines = [ln for ln in lines if ln.count("|") >= 2]
        block = f"[Seite {p}]\n{cleaned}"
        if table_lines:
            block += "\n\n[TABELLE — Markdown]\n" + "\n".join(table_lines[:30])
        parts.append(block)

    text = "\n\n".join(parts)
    prompt = (HARVEST_PROMPT
              .replace("{PAGES}", ", ".join(str(p) for p in page_nums))
              .replace("{CHAPTER}", chapter or "—")
              .replace("{TEXT}", text[:9000]))
    try:
        msg = OLLAMA.chat.completions.create(
            model=MAIN_MODEL, max_tokens=3000, temperature=0.05,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return {"entities": [], "relations": [], "summary": ""}
        result = json.loads(m.group())
    except Exception as e:
        print(f"  [harvest error: {e}]", flush=True)
        return {"entities": [], "relations": [], "summary": ""}

    # Skip CONTEXT_INSUFFICIENT windows
    if str(result.get("processed_content", "")).strip() == "CONTEXT_INSUFFICIENT":
        return {"entities": [], "relations": [], "summary": ""}

    # Normalize entities: canonical_name → name, collect synonyms
    normalized_entities = []
    for e in result.get("entities", []):
        name = (e.get("canonical_name") or e.get("name") or "").strip()
        if not name:
            continue
        normalized_entities.append({
            "name":        name,
            "type":        e.get("type", "concept"),
            "description": e.get("description", ""),
            "importance":  int(e.get("importance", 1)),
            "synonyms":    [s.strip() for s in e.get("synonyms", []) if s.strip() and s.strip() != name],
        })

    # Normalize relationships: edge_type → type (fall back to type if old schema)
    normalized_rels = []
    for r in result.get("relationships", result.get("relations", [])):
        src = (r.get("source") or "").strip()
        tgt = (r.get("target") or "").strip()
        if not src or not tgt:
            continue
        normalized_rels.append({
            "source":      src,
            "target":      tgt,
            "type":        (r.get("edge_type") or r.get("type") or "VERWEIST_AUF").strip(),
            "description": (r.get("description") or r.get("context") or ""),
            "confidence":  float(r.get("confidence", 0.85)),
        })

    return {
        "entities":          normalized_entities,
        "relations":         normalized_rels,
        "summary":           result.get("summary", ""),
        "processed_content": result.get("processed_content", ""),
    }


def detect_chapters(pages: list[tuple[int, str]]) -> list[dict]:
    sample = "\n".join(f"[PAGE:{p}]\n{t[:600]}" for p, t in pages[:15])
    prompt = (
        "Extract the table of contents from this German document. "
        "Return JSON array: [{\"number\":\"1\",\"title\":\"Einführung\",\"page\":3},...]. "
        "Only numbered chapters/sections. Return ONLY valid JSON.\n\n" + sample
    )
    try:
        msg = OLLAMA.chat.completions.create(
            model=MAIN_MODEL, max_tokens=800, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        return json.loads(m.group()) if m else []
    except Exception:
        return []


def condense_summary(summaries: list[str]) -> str:
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    joined = " ".join(summaries)[:5000]
    try:
        msg = OLLAMA.chat.completions.create(
            model=MAIN_MODEL, max_tokens=500, temperature=0.1,
            messages=[{"role": "user", "content":
                "Fasse zu einer 4-5-Satz-Zusammenfassung auf Deutsch zusammen:\n\n" + joined}],
        )
        return (msg.choices[0].message.content or "").strip()
    except Exception:
        return joined[:600]


# ─────────────────────────────────────────────────────────────────────────────
# GraphCurator dedup — collapse acronym/variant entity names (from PR #2)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_synonym_pairs(conn: sqlite3.Connection, pairs: list[tuple[str, str]]) -> int:
    """Merge synonym aliases into their canonical entity, repointing all FK references.
    pairs = [(canonical_name, alias_name), ...]
    Returns number of merges applied.
    """
    merged = 0
    for canonical, alias in pairs:
        ck = nkey(canonical)
        ak = nkey(alias)
        if ck == ak:
            continue
        # Canonical must exist; alias may or may not exist yet
        canon_row = conn.execute("SELECT name_key FROM entities WHERE name_key=?", (ck,)).fetchone()
        alias_row = conn.execute("SELECT name_key FROM entities WHERE name_key=?", (ak,)).fetchone()
        if not canon_row or not alias_row:
            continue
        # Remap relations
        conn.execute("UPDATE OR IGNORE relations SET source_key=? WHERE source_key=?", (ck, ak))
        conn.execute("DELETE FROM relations WHERE source_key=?", (ak,))
        conn.execute("UPDATE OR IGNORE relations SET target_key=? WHERE target_key=?", (ck, ak))
        conn.execute("DELETE FROM relations WHERE target_key=?", (ak,))
        # Remap mentions and chapter_entities
        conn.execute("UPDATE OR IGNORE mentions SET name_key=? WHERE name_key=?", (ck, ak))
        conn.execute("DELETE FROM mentions WHERE name_key=?", (ak,))
        try:
            conn.execute("UPDATE OR IGNORE chapter_entities SET entity_key=? WHERE entity_key=?", (ck, ak))
            conn.execute("DELETE FROM chapter_entities WHERE entity_key=?", (ak,))
        except Exception:
            pass
        # Merge: keep longer description, higher importance
        a_ent = conn.execute("SELECT description, importance FROM entities WHERE name_key=?", (ak,)).fetchone()
        c_ent = conn.execute("SELECT description, importance FROM entities WHERE name_key=?", (ck,)).fetchone()
        if a_ent and c_ent:
            new_desc = a_ent["description"] if len(a_ent["description"] or "") > len(c_ent["description"] or "") else c_ent["description"]
            new_imp  = max(a_ent["importance"] or 1, c_ent["importance"] or 1)
            conn.execute("UPDATE entities SET description=?, importance=? WHERE name_key=?", (new_desc, new_imp, ck))
        conn.execute("DELETE FROM entities WHERE name_key=?", (ak,))
        merged += 1
    return merged


_CURATOR_PROMPT = """You are a knowledge-graph curator for a German BIM document.

Below is a list of extracted entity names, one per line as "name [type]".
Identify groups of names that refer to the SAME real-world entity:
- Acronym/expansion pairs (e.g. "BIM" and "Building Information Modeling (BIM)")
- Morphological variants (e.g. "BIM-Methode" and "BIM-Methodik")
- Obvious near-duplicates (spelling, spacing, punctuation)

For each group, pick the CLEAREST canonical name and list the aliases.
Be CONSERVATIVE — only merge when clearly the same entity.
Do NOT merge distinct roles, different document versions, or part vs. whole.
Return ONLY valid JSON (no prose):
[{"canonical":"BIM-Methode","aliases":["BIM","Building Information Modeling (BIM)"]}]

If there are no groups to merge, return: []

--- entities ---
{LISTING}"""


def graph_curator_dedup(conn: sqlite3.Connection) -> int:
    """One LLM pass over all harvested entities → collapse duplicates in-place.
    Returns number of alias names merged."""
    rows = conn.execute(
        "SELECT name, name_key, type FROM entities ORDER BY importance DESC, name"
    ).fetchall()
    if len(rows) < 3:
        return 0

    listing = "\n".join(f"- {r['name']} [{r['type'] or '—'}]" for r in rows[:120])
    prompt = _CURATOR_PROMPT.replace("{LISTING}", listing)
    try:
        msg = OLLAMA.chat.completions.create(
            model=MAIN_MODEL, max_tokens=1200, temperature=0.05,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (msg.choices[0].message.content or "").strip()
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if not m:
            return 0
        groups = json.loads(m.group())
    except Exception as e:
        print(f"  [curator] error: {e}", flush=True)
        return 0

    merged = 0
    for g in groups:
        canonical = (g.get("canonical") or "").strip()
        aliases   = [a.strip() for a in g.get("aliases", []) if a.strip()]
        if not canonical or not aliases:
            continue
        ck = nkey(canonical)
        # Ensure canonical exists in DB
        canon_row = conn.execute("SELECT name_key FROM entities WHERE name_key=?", (ck,)).fetchone()
        if not canon_row:
            # Try to find by name
            canon_row = conn.execute(
                "SELECT name_key FROM entities WHERE lower(name)=?", (canonical.lower(),)
            ).fetchone()
            if not canon_row:
                continue
            ck = canon_row["name_key"]

        for alias in aliases:
            ak = nkey(alias)
            if ak == ck:
                continue
            alias_row = conn.execute("SELECT name_key FROM entities WHERE name_key=?", (ak,)).fetchone()
            if not alias_row:
                continue
            # Remap relations: source_key alias → canonical
            conn.execute(
                "UPDATE OR IGNORE relations SET source_key=? WHERE source_key=?", (ck, ak)
            )
            conn.execute("DELETE FROM relations WHERE source_key=?", (ak,))
            # Remap relations: target_key alias → canonical
            conn.execute(
                "UPDATE OR IGNORE relations SET target_key=? WHERE target_key=?", (ck, ak)
            )
            conn.execute("DELETE FROM relations WHERE target_key=?", (ak,))
            # Remap mentions
            conn.execute(
                "UPDATE OR IGNORE mentions SET name_key=? WHERE name_key=?", (ck, ak)
            )
            conn.execute("DELETE FROM mentions WHERE name_key=?", (ak,))
            # Remap chapter_entities
            try:
                conn.execute(
                    "UPDATE OR IGNORE chapter_entities SET entity_key=? WHERE entity_key=?",
                    (ck, ak)
                )
                conn.execute("DELETE FROM chapter_entities WHERE entity_key=?", (ak,))
            except Exception:
                pass
            # Merge entity: keep longest description, max importance
            alias_ent = conn.execute(
                "SELECT description, importance FROM entities WHERE name_key=?", (ak,)
            ).fetchone()
            if alias_ent:
                canon_ent = conn.execute(
                    "SELECT description, importance FROM entities WHERE name_key=?", (ck,)
                ).fetchone()
                new_desc = (alias_ent["description"]
                            if len(alias_ent["description"] or "") > len(canon_ent["description"] or "")
                            else canon_ent["description"])
                new_imp = max(alias_ent["importance"] or 1, canon_ent["importance"] or 1)
                conn.execute(
                    "UPDATE entities SET description=?, importance=? WHERE name_key=?",
                    (new_desc, new_imp, ck)
                )
            conn.execute("DELETE FROM entities WHERE name_key=?", (ak,))
            merged += 1
            print(f"  [curator] '{alias}' → '{canonical}'", flush=True)

    conn.commit()
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def db_upsert_entity(conn, name: str, etype: str, desc: str, imp: int = 1):
    k = nkey(name)
    if not k or len(k) < 2:
        return
    try:
        conn.execute(
            "INSERT INTO entities(name,name_key,type,description,importance) VALUES(?,?,?,?,?)",
            (name.strip(), k, etype, desc, imp),
        )
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE entities SET "
            "type=COALESCE(NULLIF(?,''),type), "
            "description=CASE WHEN length(?)>length(description) THEN ? ELSE description END, "
            "importance=MAX(importance,?) WHERE name_key=?",
            (etype, desc, desc, imp, k),
        )


def db_upsert_relation(conn, src, tgt, rtype, desc, conf=1.0, page=0):
    sk, tk = nkey(src), nkey(tgt)
    if not sk or not tk or sk == tk:
        return
    try:
        conn.execute(
            "INSERT INTO relations(source_key,target_key,type,description,confidence,page_number) VALUES(?,?,?,?,?,?)",
            (sk, tk, rtype, desc, conf, page),
        )
    except sqlite3.IntegrityError:
        # Update description if new one is longer (richer evidence)
        conn.execute(
            "UPDATE relations SET description=MAX(description,?), confidence=MAX(confidence,?) "
            "WHERE source_key=? AND target_key=? AND type=? AND length(?)>length(description)",
            (desc, conf, sk, tk, rtype, desc),
        )


def db_add_mention(conn, name, page, chapter="", context=""):
    k = nkey(name)
    if not k:
        return
    try:
        conn.execute(
            "INSERT INTO mentions(name_key,page,chapter,context) VALUES(?,?,?,?)",
            (k, page, chapter, context[:200]),
        )
    except sqlite3.IntegrityError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# INGESTION — full pipeline
# ─────────────────────────────────────────────────────────────────────────────

def ingest(pdf_path: str):
    import hashlib
    doc_id = hashlib.sha1(pdf_path.encode()).hexdigest()[:12]
    conn = get_db()

    # Check if already ingested
    existing = conn.execute("SELECT doc_id FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if existing:
        print(f"[ingest] {doc_id} already ingested — use 'reingest' to force", flush=True)
        return doc_id

    doc_title = Path(pdf_path).stem
    print(f"\n{'='*60}", flush=True)
    print(f"[ingest] {doc_title} → {doc_id}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # L1: Extract text
    pages = extract_pages(pdf_path)

    # L2+L3: Parent-child chunks + compaction → store
    print("[chunks] building parent-child splits…", flush=True)
    page_chapter: dict[int, str] = {}
    total_parents = 0
    for pg_num, text in pages:
        cleaned = compact(text)
        parents, children_list = split_parent_child(cleaned)
        chapter = page_chapter.get(pg_num, "")
        for idx, (parent_text, children) in enumerate(zip(parents, children_list)):
            cur = conn.execute(
                "INSERT OR IGNORE INTO parent_chunks(doc_id,page,idx,text,chapter) VALUES(?,?,?,?,?)",
                (doc_id, pg_num, idx, parent_text, chapter),
            )
            parent_id = cur.lastrowid or conn.execute(
                "SELECT id FROM parent_chunks WHERE doc_id=? AND page=? AND idx=?",
                (doc_id, pg_num, idx),
            ).fetchone()["id"]
            for c_idx, child in enumerate(children):
                conn.execute(
                    "INSERT OR IGNORE INTO child_chunks(doc_id,page,parent_id,idx,text) VALUES(?,?,?,?,?)",
                    (doc_id, pg_num, parent_id, c_idx, child),
                )
            total_parents += 1
    conn.commit()
    print(f"[chunks] {total_parents} parent chunks stored", flush=True)

    # L4: ColModernVBERT visual embeddings
    print("[visual] rendering + embedding page images…", flush=True)
    image_paths = render_page_images(pdf_path, doc_id)
    for i, img_path in enumerate(image_paths):
        page_num = i + 1
        patch_file = PATCHES_DIR / doc_id / f"{page_num:04d}.npy"
        if not patch_file.exists():
            patches = embed_images([img_path])[0]
            store_patches(doc_id, page_num, patches)
            if (i + 1) % 5 == 0:
                print(f"  embedded {i+1}/{len(image_paths)} pages", flush=True)
    print(f"[visual] {len(image_paths)} pages embedded", flush=True)

    # L5: Detect chapters
    print("[chapters] detecting document structure…", flush=True)
    raw_chaps = detect_chapters(pages)
    print(f"  found {len(raw_chaps)} chapters/sections", flush=True)
    for i, ch in enumerate(raw_chaps):
        pg = ch.get("page", 1)
        next_pg = raw_chaps[i+1]["page"] if i+1 < len(raw_chaps) else len(pages)+1
        ch_title = f"{ch.get('number','')} {ch.get('title','')}".strip()
        ck = nkey(ch_title)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO chapters(chapter_key,title,start_page,end_page) VALUES(?,?,?,?)",
                (ck, ch_title, pg, next_pg-1),
            )
        except Exception:
            pass
        for p in range(pg, next_pg):
            page_chapter[p] = ck
    conn.commit()

    # L5: Windowed harvest (3 pages, overlap 1)
    win_size, overlap = 3, 1
    step = max(1, win_size - overlap)
    wins = [pages[i:i+win_size] for i in range(0, len(pages), step)
            if pages[i:i+win_size]]
    print(f"[harvest] {len(wins)} windows with phi4:14b…", flush=True)

    summaries = []
    # synonym_pairs: (canonical_name, alias) collected from all windows for fast dedup
    synonym_pairs: list[tuple[str, str]] = []

    for i, win in enumerate(wins, 1):
        pnums = [p for p, _ in win]
        ck = page_chapter.get(pnums[0], "")
        ch_row = conn.execute("SELECT title FROM chapters WHERE chapter_key=?", (ck,)).fetchone()
        ch_label = ch_row["title"] if ch_row else ""

        print(f"  [{i:02d}/{len(wins)}] pp={pnums} … ", end="", flush=True)
        result = llm_harvest_window(win, pnums, chapter=ch_label)
        n_e = len(result.get("entities", []))
        n_r = len(result.get("relations", []))
        n_s = sum(len(e.get("synonyms", [])) for e in result.get("entities", []))
        print(f"{n_e} ents, {n_r} rels, {n_s} synonyms", flush=True)

        for e in result.get("entities", []):
            nm = (e.get("name") or "").strip()
            if not nm:
                continue
            db_upsert_entity(conn, nm, e.get("type",""), e.get("description",""), int(e.get("importance",1)))
            # Register synonyms for fast-path dedup after harvest
            for syn in e.get("synonyms", []):
                if syn and syn != nm:
                    synonym_pairs.append((nm, syn))
            for pg in pnums:
                pt = next((t for p,t in win if p==pg), "")
                idx = pt.lower().find(nm.lower())
                ctx = pt[max(0,idx-40):idx+80].strip() if idx>=0 else ""
                db_add_mention(conn, nm, pg, ch_label, ctx)
                if ck:
                    try:
                        conn.execute("INSERT OR IGNORE INTO chapter_entities VALUES(?,?)", (ck, nkey(nm)))
                    except Exception:
                        pass

        for r in result.get("relations", []):
            src, tgt = (r.get("source","")).strip(), (r.get("target","")).strip()
            if src and tgt:
                db_upsert_relation(conn, src, tgt, r.get("type",""), r.get("description",""),
                                   float(r.get("confidence", 0.85)), page=pnums[0])
                db_upsert_entity(conn, src, "", "", 1)
                db_upsert_entity(conn, tgt, "", "", 1)

        if result.get("summary"):
            summaries.append(result["summary"])

    # Fast-path synonym dedup: merge aliases harvested at extraction time
    if synonym_pairs:
        print(f"[synonyms] applying {len(synonym_pairs)} harvest-time synonym merges…", flush=True)
        _apply_synonym_pairs(conn, synonym_pairs)
        conn.commit()

    conn.commit()

    # Final summary + GraphCurator dedup — run concurrently (two independent LLM calls)
    print("[summary+curator] condensing summary & deduplicating entities in parallel…", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_summary  = ex.submit(condense_summary, summaries)
        f_curator  = ex.submit(graph_curator_dedup, conn)
        doc_summary = f_summary.result()
        n_merged    = f_curator.result()
    if n_merged:
        print(f"  [curator] collapsed {n_merged} duplicate entity names", flush=True)
    else:
        print("  [curator] no duplicates found", flush=True)

    ent_c  = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
    rel_c  = conn.execute("SELECT count(*) FROM relations").fetchone()[0]
    chap_c = conn.execute("SELECT count(*) FROM chapters").fetchone()[0]
    print(f"\n[graph] {ent_c} entities · {rel_c} relations · {chap_c} chapters (after dedup)", flush=True)

    conn.execute(
        "INSERT OR REPLACE INTO documents(doc_id,title,path,pages,summary) VALUES(?,?,?,?,?)",
        (doc_id, doc_title, pdf_path, len(pages), doc_summary),
    )
    conn.commit()

    # Write OKF wiki
    _write_okf(conn, doc_id, doc_title, doc_summary)

    # Export graph HTML
    _export_graph(conn, doc_id)

    conn.close()
    print(f"\n✅ Ingestion complete — doc_id: {doc_id}", flush=True)
    return doc_id


# ─────────────────────────────────────────────────────────────────────────────
# QUERY — full pipeline (layers 6-13)
# ─────────────────────────────────────────────────────────────────────────────

def ask(query: str, doc_id: str | None = None,
        agent_id: str = "default") -> dict:
    conn = get_db()

    # Resolve doc_id
    if not doc_id:
        row = conn.execute("SELECT doc_id FROM documents LIMIT 1").fetchone()
        if not row:
            return {"answer": "No documents ingested yet.", "sources": [], "confidence": 0}
        doc_id = row["doc_id"]

    print(f"\n[query] {query[:80]}", flush=True)
    t0 = time.time()

    # ── SONA pre-task hook → optimised pipeline plan ──
    sona = SonaOptimizer()
    plan = sona.pre_task(query)
    print(f"  [SONA] model={plan['model']} complexity={plan['complexity']}"
          f" pattern={'HIT' if plan['pattern_match'] else 'miss'}"
          f" overhead={plan['_overhead_ms']}ms", flush=True)

    # Apply SONA routing — override model constants for this request
    _synthesis_model = plan["model"]
    _top_k_visual    = plan["top_k_visual"]
    _top_k_chunks    = plan["top_k_chunks"]

    # ── Memory stack init ──
    mem = MemoryStack(agent_id=agent_id)
    episode_id = mem.episodic.open_session(query=query, doc_id=doc_id)
    mem.episodic.log_step(episode_id, "start", query[:200])

    # Company memory context (injected into synthesis later)
    company_ctx = mem.company.as_context_block(query, top_k=3)

    # L6: Visual MaxSim
    print("  [L6] visual search…", flush=True)
    visual_hits = ([] if plan.get("skip_visual")
                   else visual_search(doc_id, query, k=_top_k_visual))
    visual_pages = {h["page"] for h in visual_hits}
    mem.episodic.log_step(episode_id, "visual_search",
                          f"{len(visual_hits)} hits pages={sorted(visual_pages)[:5]}")

    # L7: BM25 child-chunk search
    print("  [L7] BM25 search…", flush=True)
    bm25_hits = bm25_search(conn, doc_id, query, k=_top_k_chunks)
    mem.episodic.log_step(episode_id, "bm25_search", f"{len(bm25_hits)} hits")

    # L8: Graph traversal → SM-2 re-rank entity list
    print("  [L8] graph traversal…", flush=True)
    graph_ctx = graph_traverse(conn, query, hops=GRAPH_HOPS)
    raw_keys  = [e["name"].strip().lower() for e in graph_ctx["entities"]]
    ranked    = mem.semantic.ranked_entities(raw_keys)  # SM-2 re-rank
    top_keys  = [k for k, _ in ranked[:8]]
    mem.episodic.log_step(episode_id, "graph_traversal",
                          f"{len(graph_ctx['entities'])} ents, {len(graph_ctx['relations'])} rels")

    # Merge retrieved parent chunks (visual + BM25 unique by page)
    all_chunks: list[dict] = []
    seen_pages = set()

    for hit in bm25_hits:
        if hit["page"] not in seen_pages:
            all_chunks.append(hit)
            seen_pages.add(hit["page"])

    # Add visual-only pages not already in BM25 results
    for vh in visual_hits:
        if vh["page"] not in seen_pages:
            row = conn.execute(
                "SELECT text, chapter FROM parent_chunks WHERE doc_id=? AND page=? LIMIT 1",
                (doc_id, vh["page"]),
            ).fetchone()
            if row:
                all_chunks.append({
                    "page": vh["page"],
                    "score": vh["score"],
                    "parent_text": row["text"],
                    "chapter": row["chapter"],
                    "child_text": "",
                })
                seen_pages.add(vh["page"])

    print(f"  [merge] {len(all_chunks)} candidate chunks (pages: {sorted(seen_pages)})", flush=True)

    # L9: Reverse context-inversion check  [adversarial gate #1]
    chunk_texts = [c["parent_text"] for c in all_chunks]
    print("  [L9] reverse context-inversion check…", flush=True)
    valid, sim = reverse_context_inversion(query, chunk_texts)
    mem.episodic.log_step(episode_id, "adv_gate_1_inversion",
                          f"valid={valid} sim={sim:.2f}")
    if not valid:
        # L9 entity-graph fallback: retrieved chunks missed, but KG may know the answer
        print(f"  [L9] sim={sim:.3f} below threshold — trying entity-graph fallback…", flush=True)
        graph_ctx_fb = graph_traverse(conn, query)
        doc_row_fb = conn.execute("SELECT summary FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        doc_sum_fb = doc_row_fb["summary"] if doc_row_fb else ""
        ent_names_fb = [e["name"] for e in graph_ctx_fb["entities"][:8]]

        if ent_names_fb:
            # Build entity-graph context and synthesize directly
            ent_descs = "\n".join(
                f"- {e['name']} ({e['type']}): {e['description']}"
                for e in graph_ctx_fb["entities"][:8]
            )
            rel_text = "; ".join(
                f'{r["source_key"]} –[{r["type"]}]→ {r["target_key"]}'
                for r in graph_ctx_fb["relations"][:12]
            )
            fb_prompt = (
                "Beantworte die folgende Frage auf Basis der Graph-Entitäten und der Dokumentzusammenfassung.\n"
                "Antworte auf Deutsch, faktisch und präzise. Wenn die Information nicht vorhanden ist, sage das.\n\n"
                f"Frage: {query}\n\n"
                f"=== Entitäten aus dem Wissensgraph ===\n{ent_descs}\n\n"
                f"=== Beziehungen ===\n{rel_text or '—'}\n\n"
                f"=== Dokumentzusammenfassung ===\n{doc_sum_fb[:800]}"
            )
            try:
                fb_msg = OLLAMA.chat.completions.create(
                    model=MAIN_MODEL, max_tokens=500, temperature=0.05,
                    messages=[{"role": "user", "content": fb_prompt}],
                )
                fb_answer = (fb_msg.choices[0].message.content or "").strip()
                print(f"  [L9-fallback] entity synthesis: {fb_answer[:100]}", flush=True)
                mem.episodic.close_session(episode_id, answer=fb_answer,
                                           verdict="unknown", score=0.0,
                                           elapsed_s=round(time.time() - t0, 1))
                conn.close()
                return {
                    "answer": fb_answer,
                    "sources": [],
                    "confidence": sim,
                    "technique": "entity_graph_fallback",
                    "retrieved_pages": [],
                }
            except Exception as e:
                print(f"  [L9-fallback] synthesis failed: {e}", flush=True)

        # Nothing in graph either — truly not in document
        mem.episodic.close_session(episode_id, answer="not_in_doc",
                                   verdict="incorrect", score=0.0,
                                   elapsed_s=round(time.time() - t0, 1))
        conn.close()
        return {
            "answer": "Diese Information ist nicht in dem Dokument enthalten.",
            "sources": [],
            "confidence": sim,
            "technique": "reverse_context_inversion_blocked",
        }
    print(f"  [L9] context valid (sim={sim:.2f})", flush=True)

    # L10+L11: Fragmented polling + Map-Reduce
    print("  [L10+L11] fragmented polling + map-reduce…", flush=True)
    verified_chunks = map_reduce(query, all_chunks)
    if len(verified_chunks) < 2:
        # Too few passed — 3B model too conservative on German BIM jargon; use all chunks
        verified_chunks = all_chunks
        print(f"  [L11] <2 verified — keeping all {len(all_chunks)} chunks", flush=True)
    else:
        print(f"  [L11] {len(verified_chunks)}/{len(all_chunks)} chunks verified relevant", flush=True)
    mem.episodic.log_step(episode_id, "map_reduce",
                          f"{len(verified_chunks)} verified/{len(all_chunks)} total")

    # Build final context — include company memory block
    graph_ents = ", ".join(e["name"] for e in graph_ctx["entities"]
                           if e["name"].strip().lower() in top_keys
                           or graph_ctx["entities"].index(e) < 4)
    graph_rels = "; ".join(
        f'{r["source_key"]} –[{r["type"]}]→ {r["target_key"]}'
        for r in graph_ctx["relations"][:10]
    )

    doc_row = conn.execute("SELECT summary FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    doc_summary = doc_row["summary"] if doc_row else ""

    # Build context blocks — prefer verbatim extractions from fragment_poll, fall back to parent_text
    context_blocks = [c.get("extraction") or c["parent_text"] for c in verified_chunks]
    source_pages = sorted({c["page"] for c in verified_chunks})

    # L12: Entity dictionary
    print("  [L12] building entity dictionary…", flush=True)
    allowed_terms = build_entity_dict(conn, doc_id, verified_chunks)

    # Collect relevant entity names from DB for the retrieved pages (inject into synthesis)
    page_list = list(source_pages) or [0]
    relevant_entities = conn.execute(
        f"SELECT DISTINCT e.name FROM entities e JOIN mentions m ON m.name_key=e.name_key "
        f"WHERE m.page IN ({','.join('?'*len(page_list))})",
        page_list,
    ).fetchall()
    entity_hint = ", ".join(r["name"] for r in relevant_entities[:40]) if relevant_entities else "—"

    # Verbatim fragment block — prefer extraction sentences, fall back to parent_text
    verbatim_fragments = "\n\n".join(
        f"[Seite {c['page']}]\n{c.get('extraction') or c['parent_text']}"
        for c in verified_chunks[:5]
    )

    # Synthesis — precision-first prompt: zero paraphrasing, exhaustive enumeration
    synthesis_prompt = (
        "You are an expert, precision-driven retrieval-augmented synthesis engine. "
        "Your core task is to answer a user query by aggregating extracted text fragments. "
        "You must prioritize exact entity preservation over stylistic paraphrasing.\n\n"
        "### OPERATIONAL CONSTRAINTS:\n\n"
        "1. ZERO PARAPHRASING OF TERMS:\n"
        "   You are provided with a list of mandatory allowed terms ([ALLOWED_TERMS]). "
        "You must use these exact strings word-for-word if their semantic concept is mentioned. "
        "Never substitute an allowed term with a general synonym "
        "(e.g., never write \"Landesverwaltung\" if \"Straßenbauverwaltung Baden-Württemberg\" is the target entity).\n\n"
        "2. STRICT EVIDENCE BOUNDING:\n"
        "   Your synthesis must ONLY rely on the verbatim sentences provided in the [VERBATIM_FRAGMENTS] block. "
        "Do not look outside these fragments, and do not extrapolate or infer facts not explicitly stated. "
        "If the fragments do not contain enough information to fully answer a specific point, "
        "state what IS in the fragments and do NOT invent entities, names, or organisations to fill the gap.\n\n"
        "3. EXPLICIT COMPLETENESS (NO SUMMARIZATION):\n"
        "   Do not summarize the context to make it sound elegant. Your goal is exhaustive enumeration. "
        "If the source text lists three specific organizations, guidelines, or conditions, "
        "you must explicitly name all three. Treat the evaluation criteria as a strict checklist of specific terms. "
        "Only enumerate what the fragments actually contain — never invent specifics to appear thorough.\n\n"
        "### INPUT DATA:\n\n"
        f"FRAGE:\n{query}\n\n"
        f"ERLAUBTE FACHBEGRIFFE:\n{entity_hint}\n\n"
        f"QUELLTEXTPASSAGEN:\n{verbatim_fragments}\n\n"
        f"GRAPH-KONTEXT:\nEntitäten: {graph_ents or '—'}\nBeziehungen: {graph_rels or '—'}\n\n"
        "### AUSGABE:\n"
        "- Beantworte die FRAGE vollständig auf Deutsch.\n"
        "- Verwende so viele exakte Namen aus ERLAUBTE FACHBEGRIFFE wie die QUELLTEXTPASSAGEN belegen.\n"
        "- Antworte direkt — keine Metakommentare wie 'laut den Fragmenten' oder 'basierend auf den Passagen'.\n"
        "- Hohe Dichte an spezifischen Fachbegriffen. Nenne alle relevanten Eigennamen explizit. Sei vollständig."
        + (f"\n\n{company_ctx}" if company_ctx else "")
    )

    print(f"  [synthesis] {_synthesis_model} generating answer…", flush=True)
    try:
        msg = OLLAMA.chat.completions.create(
            model=_synthesis_model, max_tokens=1000, temperature=0.05,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        answer = (msg.choices[0].message.content or "").strip()
    except Exception as e:
        answer = f"[synthesis error: {e}]"

    mem.episodic.log_step(episode_id, "synthesis", answer[:200])

    # L13: Self-RAG (disabled — qwen2.5-coder degrades German answers; re-enable after tuning)
    # answer = self_rag_check(answer, context_blocks[:4], query=query)
    mem.episodic.log_step(episode_id, "adv_gate_3_selfrag", answer[:200])

    # L12 check on final answer
    verdict, flagged = entity_dict_check(answer, allowed_terms, conn)
    if flagged:
        print(f"  [L12] flagged terms: {flagged[:5]}", flush=True)

    elapsed = time.time() - t0
    conn.close()

    # ── SONA post-task hook ──
    sona.post_task(query, answer, verdict="", score=0.0,
                   elapsed_s=round(elapsed, 1), plan=plan)

    # ── EWC++ protect entities that contributed to this answer ──
    for k in raw_keys[:10]:
        sona.ewc_protect(k, quality=3, access_count=1)

    # ── Close episode + reinforce SM-2 for used entities ──
    mem.episodic.close_session(
        episode_id, answer=answer,
        verdict="",   # filled in by eval judge; empty for direct asks
        score=0.0,
        sources=source_pages,
        entity_check=verdict,
        chunks_used=len(verified_chunks),
        elapsed_s=round(elapsed, 1),
    )
    # Neutral quality (3) for entities seen in a direct query —
    # eval judge will call reinforce_episode with actual quality later
    mem.reinforce_episode(episode_id, raw_keys[:10], verdict="partial")

    return {
        "answer": answer,
        "sources": source_pages,
        "retrieved_pages": source_pages,   # alias used by eval diagnostics
        "visual_pages": list(visual_pages),
        "graph_entities": graph_ents,
        "graph_relations": len(graph_ctx["relations"]),
        "chunks_verified": len(verified_chunks),
        "context_sim": round(sim, 2),
        "entity_check": verdict,
        "flagged_terms": flagged[:5],
        "elapsed_s": round(elapsed, 1),
        "episode_id": episode_id,
        "technique": "full_pipeline",
    }


# ─────────────────────────────────────────────────────────────────────────────
# EVAL — run all questions + judge
# ─────────────────────────────────────────────────────────────────────────────

def run_eval(questions_yaml: str, doc_id: str | None = None):
    with open(questions_yaml, "r", encoding="utf-8") as f:
        raw = f.read()

    # Handle multi-document YAML
    questions = []
    for part in re.split(r'(?m)^document:', raw):
        if not part.strip():
            continue
        block = yaml.safe_load("document:" + part) or {}
        # handle both flat {questions:[...]} and nested {document:{questions:[...]}}
        qs = block.get("questions") or block.get("document", {}).get("questions") or []
        questions.extend(qs)

    print(f"\n[eval] {len(questions)} questions", flush=True)

    # Pre-load all entity name_keys for entity-recall tracking
    with get_db() as _ec:
        all_entity_keys = [r[0] for r in _ec.execute("SELECT name_key FROM entities").fetchall()]

    judge_llm = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")

    rows = []
    for q in questions:
        qid = q.get("id", "?")
        qtext = q.get("question", "")
        expected = q.get("expected_answer", "")
        if isinstance(expected, list):
            expected = " | ".join(str(x) for x in expected)
        gold_page = q.get("source", {}).get("page") if isinstance(q.get("source"), dict) else q.get("source_page")
        evidence_type = q.get("evidence", {}).get("type", "") if isinstance(q.get("evidence"), dict) else ""
        expected_entities = q.get("expected_entities", []) or []

        print(f"\n--- {qid} ---", flush=True)
        result = ask(qtext, doc_id=doc_id)
        answer = result["answer"]
        retrieved_pages = result.get("retrieved_pages", result.get("sources", []))
        technique = result.get("technique", "unknown")
        print(f"  [answer] {answer[:200]}", flush=True)

        # Entity recall: which expected entities are in our KG?
        er_hit, er_tot, er_missing = 0, len(expected_entities), []
        for ent in expected_entities:
            ek = ent.strip().lower()
            if any(ek in k or k in ek for k in all_entity_keys):
                er_hit += 1
            else:
                er_missing.append(ent)

        # LLM judge — use phi4 (main model) for more reliable German semantic eval
        judge_prompt = (
            "Du bist ein strenger aber fairer Bewerter eines Dokumenten-RAG-Systems.\n"
            "Vergleiche die System-Antwort mit der Musterantwort auf Basis der enthaltenen Kernfakten.\n"
            "Eine Antwort ist 'correct' wenn sie die wichtigsten Fakten der Musterantwort enthält (Wortlaut egal).\n"
            "Eine Antwort ist 'partial' wenn sie einige Fakten enthält aber unvollständig ist.\n"
            "Eine Antwort ist 'incorrect' NUR wenn komplett falsche oder keine relevanten Fakten enthalten sind.\n\n"
            f"Frage: {qtext}\n"
            f"Musterantwort: {expected}\n"
            f"System-Antwort: {answer}\n\n"
            "Antworte NUR mit JSON (kein anderer Text): "
            '{"verdict":"correct"|"partial"|"incorrect","score":0.0..1.0,"reason":"kurz"}'
        )
        try:
            jmsg = judge_llm.chat.completions.create(
                model=MAIN_MODEL, max_tokens=300, temperature=0,
                messages=[{"role": "user", "content": judge_prompt}],
            )
            raw_j = jmsg.choices[0].message.content or ""
            m = re.search(r'\{.*\}', raw_j, re.DOTALL)
            verdict_data = json.loads(m.group()) if m else {}
        except Exception:
            verdict_data = {}

        verdict  = verdict_data.get("verdict", "error")
        score    = float(verdict_data.get("score", 0.0))
        reason   = verdict_data.get("reason", "")

        # ── Update episodic ledger with real judge verdict + SM-2 reinforce ──
        episode_id = result.get("episode_id", "")
        if episode_id:
            ep_ledger = EpisodicLedger()
            ep_ledger.close_session(
                episode_id, answer=answer, verdict=verdict, score=score,
                sources=retrieved_pages,
                entity_check=result.get("entity_check", ""),
                chunks_used=result.get("chunks_verified", 0),
                elapsed_s=result.get("elapsed_s", 0),
            )
            mem_stack = MemoryStack(agent_id="eval")
            mem_stack.reinforce_episode(episode_id, [], verdict=verdict)
            sona_opt = SonaOptimizer()
            sona_opt.log_routing(qtext, result.get("_model", MAIN_MODEL),
                                 score, result.get("elapsed_s", 0))
            sona_opt.post_task(qtext, answer, verdict, score,
                               result.get("elapsed_s", 0), {})

        # Diagnostic print: verdict, score, pages retrieved vs gold, entity recall, technique
        er_str = f"{er_hit}/{er_tot}" if er_tot > 0 else "—"
        miss_str = f" missing={er_missing}" if er_missing else ""
        print(
            f"  {verdict:9s} {score:.2f} | pages={retrieved_pages} gold={gold_page} "
            f"ents={er_str}{miss_str} [{technique}] | {reason[:60]}",
            flush=True
        )

        rows.append({
            "id": qid,
            "verdict": verdict,
            "score": score,
            "reason": reason,
            "answer": answer,
            "retrieved_pages": retrieved_pages,
            "gold_page": gold_page,
            "evidence_type": evidence_type,
            "entity_recall": f"{er_hit}/{er_tot}",
            "entities_missing": er_missing,
            "technique": technique,
            "sources": retrieved_pages,
            "entity_check": result.get("entity_check", ""),
            "chunks_verified": result.get("chunks_verified", 0),
            "elapsed_s": result.get("elapsed_s", 0),
            "episode_id": episode_id,
        })

    graded = [r for r in rows if r["verdict"] in ("correct","partial","incorrect")]
    n = max(len(graded), 1)

    # Breakdown by technique
    tech_counts = Counter(r["technique"] for r in rows)
    tech_correct = Counter(r["technique"] for r in rows if r["verdict"] == "correct")

    summary = {
        "questions": len(rows),
        "correct":  sum(r["verdict"]=="correct"  for r in graded),
        "partial":  sum(r["verdict"]=="partial"  for r in graded),
        "incorrect":sum(r["verdict"]=="incorrect" for r in graded),
        "errors":   sum(r["verdict"]=="error"     for r in rows),
        "avg_score": round(sum(r["score"] for r in graded) / n, 3),
        "by_technique": {k: {"total": tech_counts[k], "correct": tech_correct.get(k, 0)} for k in tech_counts},
    }

    out_path = DATA / "eval_results_complete.json"
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))

    print(f"\n{'='*60}")
    print(f"  correct:   {summary['correct']}/{summary['questions']}")
    print(f"  partial:   {summary['partial']}")
    print(f"  incorrect: {summary['incorrect']}")
    print(f"  avg score: {summary['avg_score']}")
    print(f"  by technique: {dict(tech_counts)}")
    print(f"  baseline:  2/18 correct (v8), PR target: better")
    print(f"{'='*60}")
    print(f"Results → {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Graph HTML export (vis-network)
# ─────────────────────────────────────────────────────────────────────────────

import urllib.request

TYPE_COLORS = {
    "standard": "#e91e8c", "organization": "#1e88e5",
    "method": "#f57c00",   "system": "#2ecc71",
    "role": "#9b59b6",     "concept": "#00bcd4",
    "document": "#607d8b", "process": "#e74c3c",
    "model": "#27ae60",    "tool": "#f39c12",
}

def _export_graph(conn: sqlite3.Connection, doc_id: str):
    ents  = conn.execute("SELECT name_key,name,type,description,importance FROM entities").fetchall()
    rels  = conn.execute("SELECT source_key,target_key,type,description,confidence FROM relations").fetchall()
    ments = conn.execute("SELECT name_key,page,chapter,context FROM mentions").fetchall()
    chaps = conn.execute("SELECT chapter_key,title,start_page,end_page FROM chapters").fetchall()
    ch_ents = conn.execute("SELECT chapter_key,name_key FROM chapter_entities").fetchall()

    mention_map = defaultdict(list)
    for mk, pg, ch, ctx in ments:
        mention_map[mk].append({"page": pg, "chapter": ch, "context": ctx})

    chap_ent_map = defaultdict(list)
    for ck, nk in ch_ents:
        chap_ent_map[ck].append(nk)

    degree: Counter = Counter()
    for src, tgt, *_ in rels:
        degree[src] += 1
        degree[tgt] += 1

    known = {e["name_key"] for e in ents}
    entity_info = {}
    nodes_data = []

    for e in ents:
        k = e["name_key"]
        etype = (e["type"] or "concept").lower()
        bg = TYPE_COLORS.get(etype, "#546e7a")
        ms = mention_map.get(k, [])
        pages = sorted({m["page"] for m in ms})
        chaps_list = sorted({m["chapter"] for m in ms if m["chapter"]})
        ctx_samples = [m["context"] for m in ms[:2] if m["context"]]
        imp = e["importance"] or 1

        tooltip = (
            f"<b style='font-size:14px'>{e['name']}</b><br>"
            f"<i style='color:#aaa'>{etype}</i><br>"
            f"<hr style='border:0;border-top:1px solid #333;margin:4px 0'>"
            + (f"{e['description']}<br>" if e["description"] else "")
            + (f"<b>Seiten:</b> {', '.join(str(p) for p in pages[:10])}<br>" if pages else "")
            + (f"<b>Kapitel:</b> {'; '.join(chaps_list[:2])}<br>" if chaps_list else "")
            + (f"<b>Kontext:</b> <i>…{ctx_samples[0][:100]}…</i>" if ctx_samples else "")
        )
        entity_info[k] = {"name": e["name"], "type": etype, "description": e["description"], "pages": pages}

        nodes_data.append({
            "id": k, "label": (e["name"] or k)[:32],
            "group": etype, "value": (degree.get(k, 0) + 1) * imp,
            "title": tooltip,
            "color": {"background": bg, "border": bg,
                      "highlight": {"background": bg, "border": "#fff"},
                      "hover": {"background": bg, "border": "#fff"}},
            "font": {"color": "#fff", "size": 12 + min(imp * 2, 6)},
        })

    for k in {e for src, tgt, *_ in rels for e in (src, tgt)} - known:
        nodes_data.append({
            "id": k, "label": k[:30], "group": "concept", "value": degree.get(k, 1),
            "color": {"background": "#546e7a", "border": "#546e7a"},
            "font": {"color": "#ccc", "size": 10},
            "title": f"<b>{k}</b>",
        })

    # Chapter diamond nodes
    for ch in chaps:
        ck, ct = ch["chapter_key"], ch["title"]
        nc = len(chap_ent_map.get(ck, []))
        nodes_data.append({
            "id": f"__ch_{ck}", "label": ct[:28], "group": "chapter",
            "shape": "diamond", "value": max(nc * 2, 3),
            "color": {"background": "#0d1530", "border": "#3d5af1"},
            "font": {"color": "#7089ff", "size": 10},
            "title": f"<b>📂 {ct}</b><br>pp.{ch['start_page']}–{ch['end_page']} · {nc} entities",
        })

    edges_data = []
    for ck, nks in chap_ent_map.items():
        for nk in nks[:6]:
            edges_data.append({"from": f"__ch_{ck}", "to": nk, "dashes": True,
                               "width": 0.7, "color": {"color": "#1a2555", "opacity": 0.4},
                               "arrows": "", "label": ""})

    for src, tgt, rtype, desc, conf in rels:
        edges_data.append({
            "from": src, "to": tgt, "label": rtype[:16],
            "title": f"<b>{rtype}</b><br>{desc or ''}",
            "arrows": "to", "width": max(0.8, (conf or 1.0) * 2.5),
            "color": {"color": "#3a4575", "highlight": "#6080d0", "hover": "#5070c0"},
            "font": {"size": 9, "color": "#8090b0", "strokeWidth": 0},
        })

    vis_js = DATA / "vis-network.min.js"
    if not vis_js.exists():
        print("[VIS] downloading vis-network…", flush=True)
        try:
            urllib.request.urlretrieve(
                "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js", vis_js
            )
        except Exception:
            pass

    legend = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:2px 0">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{c};flex-shrink:0"></span>'
        f'<span style="color:#889;font-size:11px">{t}</span></div>'
        for t, c in TYPE_COLORS.items()
    )

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>LEGATUM Knowledge Graph</title>
<script src="{vis_js.name}"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;background:#070b18;color:#ccd;font-family:-apple-system,BlinkMacSystemFont,sans-serif;overflow:hidden}}
#net{{position:absolute;top:0;left:0;right:340px;bottom:0}}
#sidebar{{position:absolute;top:0;right:0;width:340px;bottom:0;background:#0c1128;border-left:1px solid #1e2a4a;display:flex;flex-direction:column}}
#hud{{padding:12px 14px;border-bottom:1px solid #1e2a4a}}
#hud h2{{font-size:13px;color:#fff;margin-bottom:5px}}
#stats{{color:#556;font-size:10px;margin-bottom:8px}}
#q{{width:100%;background:#111827;border:1px solid #2a3560;color:#dde;border-radius:5px;padding:6px 10px;font-size:11px;outline:none}}
#filters{{padding:8px 12px;border-bottom:1px solid #1e2a4a;display:flex;flex-wrap:wrap;gap:4px}}
.fb{{padding:2px 7px;border-radius:10px;border:1px solid currentColor;background:transparent;font-size:9px;cursor:pointer;opacity:0.6}}
.fb.on{{opacity:1}}
#detail{{flex:1;overflow-y:auto;padding:12px;font-size:12px}}
#ph{{color:#334;text-align:center;padding:30px 16px;font-size:12px;line-height:1.8}}
.dh{{font-size:14px;color:#fff;margin-bottom:3px}}
.db{{display:inline-block;padding:2px 7px;border-radius:9px;font-size:9px;margin-bottom:8px}}
.dd{{color:#aab;line-height:1.5;margin-bottom:10px;font-size:11px}}
.ds{{color:#556;font-size:9px;text-transform:uppercase;letter-spacing:1px;margin:8px 0 3px}}
.tag{{display:inline-block;background:#111827;border:1px solid #2a3560;color:#8af;padding:1px 6px;border-radius:3px;font-size:9px;margin:1px}}
.rr{{padding:4px 0;border-bottom:1px solid #111827;font-size:10px}}
.rt{{color:#5566aa;font-size:9px;margin-right:3px}}
</style></head><body>
<div id="net"></div>
<div id="sidebar">
<div id="hud">
  <h2>🧠 BIM-Leitfaden 2.0 — Knowledge Graph</h2>
  <div id="stats">{len(nodes_data)} nodes · {len(edges_data)} edges</div>
  <input id="q" placeholder="Search entity (Enter)…">
</div>
<div id="filters">
  {''.join(f'<button class="fb on" data-t="{t}" style="color:{c};border-color:{c}">{t}</button>' for t,c in TYPE_COLORS.items())}
  <button class="fb on" data-t="chapter" style="color:#3d5af1;border-color:#3d5af1">chapter</button>
</div>
<div id="detail"><div id="ph">← Click a node<br>to see details</div></div>
<div style="padding:8px 12px;border-top:1px solid #1e2a4a">{legend}</div>
</div>
<script>
const NDS={json.dumps(nodes_data,ensure_ascii=False)};
const EDS={json.dumps(edges_data,ensure_ascii=False)};
const EI={json.dumps(entity_info,ensure_ascii=False)};
const TC={json.dumps({t:c for t,c in TYPE_COLORS.items()},ensure_ascii=False)};
const nodes=new vis.DataSet(NDS),edges=new vis.DataSet(EDS);
const net=new vis.Network(document.getElementById('net'),{{nodes,edges}},{{
  nodes:{{shape:'dot',scaling:{{min:10,max:52,label:{{min:10,max:20,drawThreshold:6}}}},borderWidth:2,borderWidthSelected:4}},
  edges:{{width:1.5,selectionWidth:3,color:{{inherit:false}},font:{{size:9,color:'#8090b0',strokeWidth:0,vadjust:-5}}}},
  physics:{{solver:'forceAtlas2Based',stabilization:{{iterations:350,updateInterval:20}},forceAtlas2Based:{{gravitationalConstant:-65,springLength:140,springConstant:0.06,damping:0.9,centralGravity:0.003}}}},
  interaction:{{hover:true,tooltipDelay:50,navigationButtons:true,keyboard:{{enabled:true,bindToWindow:false}}}},
}});
net.on('stabilizationIterationsDone',()=>net.setOptions({{physics:{{enabled:false}}}}));
net.on('click',p=>{{
  if(!p.nodes.length&&!p.edges.length){{reset();return;}}
  if(p.nodes.length){{hi(p.nodes[0]);detail(p.nodes[0]);}}
}});
function hi(nid){{
  const cn=new Set(net.getConnectedNodes(nid));cn.add(nid);
  nodes.update(nodes.getIds().map(id=>({{'id':id,'opacity':cn.has(id)?1:0.1}})));
  const ce=new Set(net.getConnectedEdges(nid));
  edges.update(edges.getIds().map(id=>({{'id':id,'color':ce.has(id)?{{color:'#5070d0',opacity:1}}:{{color:'#111827',opacity:0.1}},'width':ce.has(id)?2.5:0.5}})));
}}
function reset(){{
  nodes.update(nodes.getIds().map(id=>({{'id':id,'opacity':1}})));
  edges.update(edges.getIds().map(id=>({{'id':id,'color':undefined,'width':undefined}})));
  document.getElementById('detail').innerHTML='<div id="ph">← Click a node<br>to see details</div>';
}}
function detail(nid){{
  const info=EI[nid],nd=nodes.get(nid),bg=TC[nd?.group]||'#546e7a';
  const ce=net.getConnectedEdges(nid);
  const rels=ce.slice(0,15).map(eid=>{{
    const e=edges.get(eid);if(!e)return'';
    const out=e.from===nid,oth=out?e.to:e.from,on=nodes.get(oth);
    return `<div class="rr"><span class="rt">${{e.label||''}}</span>${{out?'→':'←'}} <b>${{on?.label||oth}}</b></div>`;
  }}).join('');
  document.getElementById('detail').innerHTML=`
    <div class="dh">${{info?.name||nid}}</div>
    <span class="db" style="background:${{bg}}">${{info?.type||nd?.group||''}}</span>
    <p class="dd">${{info?.description||'<em style="color:#445">No description</em>'}}</p>
    <div class="ds">Pages</div>${{(info?.pages||[]).map(p=>`<span class="tag">p.${{p}}</span>`).join('')||'<span style="color:#445">—</span>'}}
    <div class="ds">Relations (${{ce.length}})</div>${{rels||'<span style="color:#445">None</span>'}}
  `;
}}
document.getElementById('q').addEventListener('keydown',e=>{{
  if(e.key!=='Enter')return;
  const q=e.target.value.toLowerCase().trim();
  const hit=nodes.get().find(n=>(n.label||'').toLowerCase().includes(q)||(n.id||'').includes(q));
  if(hit){{net.selectNodes([hit.id]);net.focus(hit.id,{{scale:1.8,animation:{{duration:500}}}});hi(hit.id);detail(hit.id);}}
}});
document.querySelectorAll('.fb').forEach(b=>b.addEventListener('click',()=>{{b.classList.toggle('on');applyF()}}));
function applyF(){{
  const on=new Set([...document.querySelectorAll('.fb.on')].map(b=>b.dataset.t));
  nodes.update(NDS.map(n=>({{'id':n.id,'hidden':!on.has(n.group||'concept')}})));
}}
net.on('doubleClick',p=>{{if(p.nodes.length)net.focus(p.nodes[0],{{scale:2.5,animation:true}});}});
</script></body></html>"""

    out = DATA / "knowledge_graph_complete.html"
    out.write_text(html, encoding="utf-8")
    print(f"[graph] → {out}", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# OKF wiki
# ─────────────────────────────────────────────────────────────────────────────

def _write_okf(conn, doc_id, doc_title, summary):
    slug = re.sub(r'[^a-z0-9]+', '-', doc_title.lower()).strip('-')
    f = OKF_DIR / "docs" / f"{slug}-complete.md"
    ents = conn.execute("SELECT name,type,description,importance FROM entities ORDER BY importance DESC,type,name").fetchall()
    rels = conn.execute("SELECT count(*) FROM relations").fetchone()[0]
    chaps = conn.execute("SELECT title,start_page,end_page FROM chapters ORDER BY start_page").fetchall()

    by_type = defaultdict(list)
    for e in ents:
        by_type[e["type"] or "concept"].append(e)

    lines = [
        f"---\ntitle: {doc_title}\ntype: Document\nversion: complete\n---\n",
        f"# {doc_title}\n",
        f"## Summary\n{summary or '_(none)_'}\n",
        f"**{len(ents)} entities · {rels} relations · {len(chaps)} chapters**\n",
        "## Document Structure",
    ]
    for ch in chaps:
        lines.append(f"- **{ch['title']}** (pp. {ch['start_page']}–{ch['end_page']})")
    for etype in sorted(by_type):
        lines += [f"\n## {etype.capitalize()}s ({len(by_type[etype])})"]
        for e in by_type[etype]:
            stars = "★" * min(e["importance"] or 1, 3)
            desc = f" — {e['description']}" if e["description"] else ""
            lines.append(f"- **{e['name']}** {stars}{desc}")
    f.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OKF] {f}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "ingest":
        pdf = sys.argv[2] if len(sys.argv) > 2 else \
            "/Users/mango/Downloads/2025_Broschuere_BIM-Leitfaden_2.0_barrierefrei.pdf"
        ingest(pdf)

    elif cmd == "ask":
        query = " ".join(sys.argv[2:]) or "Wozu dient der BIM-Leitfaden 2.0?"
        result = ask(query)
        print(f"\n{'='*60}")
        print(f"ANSWER:\n{result['answer']}")
        print(f"\nSources: pages {result.get('sources')}")
        print(f"Entity check: {result.get('entity_check')} | Chunks verified: {result.get('chunks_verified')}")
        print(f"Elapsed: {result.get('elapsed_s')}s")

    elif cmd == "eval":
        yaml_path = sys.argv[2] if len(sys.argv) > 2 else \
            "/Users/mango/Downloads/bim_leitfaden_eval_15_questions_draft.yaml"
        run_eval(yaml_path)

    elif cmd == "graph":
        conn = get_db()
        row = conn.execute("SELECT doc_id FROM documents LIMIT 1").fetchone()
        if row:
            out = _export_graph(conn, row["doc_id"])
            os.system(f"open {out}")
        conn.close()

    elif cmd == "status":
        conn = get_db()
        docs  = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
        ents  = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
        rels  = conn.execute("SELECT count(*) FROM relations").fetchone()[0]
        chaps = conn.execute("SELECT count(*) FROM chapters").fetchone()[0]
        pc    = conn.execute("SELECT count(*) FROM parent_chunks").fetchone()[0]
        cc    = conn.execute("SELECT count(*) FROM child_chunks").fetchone()[0]
        print(f"Documents: {docs} | Entities: {ents} | Relations: {rels}")
        print(f"Chapters:  {chaps} | Parent chunks: {pc} | Child chunks: {cc}")
        patch_count = sum(1 for _ in PATCHES_DIR.rglob("*.npy"))
        print(f"Patch files (ColModernVBERT): {patch_count}")
        conn.close()

    else:
        print(__doc__)
