"""M&A Knowledge Base — SQLite store for documents, chunks, facts, annotations."""
import json
import sqlite3
import os
from datetime import datetime

MA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "blackswanx.db")


def get_db():
    conn = sqlite3.connect(MA_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_ma_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ma_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            upload_date TEXT DEFAULT (datetime('now')),
            char_count INTEGER DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'indexed',
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS ma_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            text TEXT NOT NULL,
            page INTEGER DEFAULT 1,
            source TEXT DEFAULT 'text',
            char_start INTEGER DEFAULT 0,
            keyword_freq TEXT DEFAULT '{}',
            relevance_score REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS ma_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            chunk_id INTEGER REFERENCES ma_chunks(id),
            fact_type TEXT NOT NULL,
            subject TEXT,
            value TEXT,
            confidence REAL DEFAULT 0.8,
            extracted_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ma_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id INTEGER NOT NULL REFERENCES ma_chunks(id),
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            note TEXT NOT NULL,
            tag TEXT DEFAULT 'general',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def store_document(filename: str, file_type: str, pages: list[dict], chunks: list[dict]) -> int:
    """Persist a document with its pages and chunks. Returns new doc_id."""
    conn = get_db()
    char_count = sum(len(p["text"]) for p in pages)
    page_count = max((p.get("page", 1) for p in pages), default=1)

    cur = conn.execute(
        "INSERT INTO ma_documents (filename, file_type, char_count, page_count, chunk_count) VALUES (?,?,?,?,?)",
        (filename, file_type, char_count, page_count, len(chunks)),
    )
    doc_id = cur.lastrowid

    for c in chunks:
        conn.execute(
            "INSERT INTO ma_chunks (doc_id, text, page, source, char_start, keyword_freq) VALUES (?,?,?,?,?,?)",
            (
                doc_id,
                c["text"],
                c.get("page", 1),
                c.get("source", "text"),
                c.get("char_start", 0),
                json.dumps(c.get("keyword_freq", {})),
            ),
        )
    conn.commit()
    conn.close()
    return doc_id


def list_documents() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, file_type, upload_date, char_count, page_count, chunk_count, status, summary FROM ma_documents ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id: int) -> dict | None:
    conn = get_db()
    doc = conn.execute(
        "SELECT * FROM ma_documents WHERE id=?", (doc_id,)
    ).fetchone()
    if not doc:
        conn.close()
        return None
    chunks = conn.execute(
        "SELECT id, text, page, source, char_start, relevance_score FROM ma_chunks WHERE doc_id=? ORDER BY id",
        (doc_id,),
    ).fetchall()
    conn.close()
    return {**dict(doc), "chunks": [dict(c) for c in chunks]}


def bm25_search(query: str, doc_id: int | None = None, limit: int = 15) -> list[dict]:
    """BM25-style search across all chunks (or one document)."""
    from ma.ingestion import keyword_vector, bm25_score

    terms = list(keyword_vector(query).keys())
    if not terms:
        return []

    conn = get_db()
    if doc_id is not None:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.source, c.keyword_freq, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id WHERE c.doc_id=?",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.source, c.keyword_freq, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id"
        ).fetchall()

    # Compute avg doc length
    total_len = sum(len(r["text"]) for r in rows)
    avg_len = total_len / max(len(rows), 1)

    results = []
    for r in rows:
        try:
            freq = json.loads(r["keyword_freq"] or "{}")
        except Exception:
            freq = {}
        score = bm25_score(terms, freq, len(r["text"]), avg_len)
        if score > 0:
            results.append({
                "chunk_id": r["id"],
                "doc_id": r["doc_id"],
                "filename": r["filename"],
                "text": r["text"],
                "page": r["page"],
                "score": round(score, 3),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    conn.close()
    return results[:limit]


def save_annotation(chunk_id: int, doc_id: int, note: str, tag: str = "general") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO ma_annotations (chunk_id, doc_id, note, tag) VALUES (?,?,?,?)",
        (chunk_id, doc_id, note, tag),
    )
    ann_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ann_id


def list_annotations(doc_id: int | None = None) -> list[dict]:
    conn = get_db()
    if doc_id is not None:
        rows = conn.execute(
            "SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            "JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            "WHERE a.doc_id=? ORDER BY a.id DESC",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            "JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            "ORDER BY a.id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_facts(doc_id: int, facts: list[dict]) -> int:
    """Persist extracted facts. Returns count saved."""
    conn = get_db()
    for f in facts:
        conn.execute(
            "INSERT INTO ma_facts (doc_id, chunk_id, fact_type, subject, value, confidence) VALUES (?,?,?,?,?,?)",
            (doc_id, f.get("chunk_id"), f["fact_type"], f.get("subject", ""), f.get("value", ""), f.get("confidence", 0.8)),
        )
    conn.commit()
    conn.close()
    return len(facts)


def list_facts(doc_id: int | None = None) -> list[dict]:
    conn = get_db()
    if doc_id is not None:
        rows = conn.execute(
            "SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id WHERE f.doc_id=? ORDER BY f.id DESC",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id ORDER BY f.id DESC LIMIT 200"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
