"""
Cross-Document Contractual Mesh
================================
Replaces generic Jaccard-similarity graph densification with a legally-grounded
construction document graph.

In construction, documents have deterministic hierarchical and legal relationships:
    Hauptvertrag → LV (Leistungsverzeichnis) → Position → Nachtrag → VOB/B §X → DIN XXXXX

This module builds those edges deterministically — not probabilistically.

Three passes:
    Pass 1: Document hierarchy mapping (parent_of, amends, supplements)
    Pass 2: GAEB Positionsnummer linking (exact item number matches across docs)
    Pass 3: VOB/B + DIN standard resolution (canonical legal nodes)

No LLM needed for Passes 1 and 2. Pass 3 uses regex + a VOB/B reference table.
"""

from __future__ import annotations

import re
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ── Document type classification ─────────────────────────────────────────────

DOC_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"leistungsverzeichnis|lv\b|bill of quantities|boq", "LV"),
    (r"nachtrag|nachtragsangebot|change.?order|zusatzauftrag", "NACHTRAG"),
    (r"hauptvertrag|werkvertrag|bauvertrag|main.?contract", "HAUPTVERTRAG"),
    (r"anlage|anhang|appendix|exhibit", "ANLAGE"),
    (r"rechnung|invoice|abschlagsrechnung|schlussrechnung", "RECHNUNG"),
    (r"abnahmeprotokoll|abnahme|acceptance.?report", "ABNAHME"),
    (r"behinderungsanzeige|behinderung|delay.?notice", "BEHINDERUNGSANZEIGE"),
    (r"maengelprotokoll|maengel|defect.?report|mängelprotokoll", "MAENGELPROTOKOLL"),
    (r"bautagebuch|site.?diary|bautagesberichte", "BAUTAGEBUCH"),
    (r"leistungsbeschreibung|specification|bausoll", "LEISTUNGSBESCHREIBUNG"),
]

# Legal hierarchy: higher index = more specific / subordinate
DOC_HIERARCHY = {
    "HAUPTVERTRAG": 0,
    "ANLAGE": 1,
    "LV": 2,
    "LEISTUNGSBESCHREIBUNG": 2,
    "NACHTRAG": 3,
    "RECHNUNG": 4,
    "ABNAHME": 5,
    "MAENGELPROTOKOLL": 6,
    "BEHINDERUNGSANZEIGE": 6,
    "BAUTAGEBUCH": 6,
}

# VOB/B paragraph reference table
VOB_B_PARAGRAPHS: dict[str, str] = {
    "§2": "Vergütung",
    "§2 abs. 3": "Pauschalvertrag — Leistungsänderungen",
    "§2 abs. 5": "Anordnung des AG — Nachtragsvergütung",
    "§2 abs. 6": "Zusätzliche Leistungen",
    "§4": "Ausführung der Leistung",
    "§4 abs. 1": "Baugrundrisiko",
    "§6": "Behinderung und Unterbrechung",
    "§6 abs. 6": "Schadensersatz bei Behinderung",
    "§12": "Abnahme",
    "§13": "Mängelansprüche / Gewährleistung",
    "§13 abs. 4": "Gewährleistungsfrist",
    "§14": "Abrechnung",
    "§16": "Zahlung",
    "§16 abs. 3": "Schlusszahlung / Vorbehalt",
}

# GAEB position number pattern (e.g. 01.01.001, 03.02.0010)
GAEB_POSITION_PATTERN = re.compile(
    r'\b(\d{2}[._]\d{2}[._]\d{3,4})\b'
)

# VOB/B reference pattern
VOB_REF_PATTERN = re.compile(
    r'VOB[/\s]?B\s*(§\s*\d+(?:\s*Abs?\.\s*\d+)?)',
    re.IGNORECASE
)

# DIN standard pattern
DIN_PATTERN = re.compile(
    r'\b(DIN(?:\s+EN)?\s+\d{3,6}(?:[:-]\d+)?)\b',
    re.IGNORECASE
)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ContractNode:
    node_id: str
    name: str
    node_type: str          # DOC, VOB_PARAGRAPH, DIN_STANDARD, GAEB_POSITION
    doc_type: str | None = None
    doc_id: int | None = None
    legal_ref: str | None = None
    properties: dict = field(default_factory=dict)


@dataclass
class ContractEdge:
    edge_id: str
    src: str
    tgt: str
    edge_type: str          # parent_of, amends, supplements, references_position,
                            # governed_by, references_standard
    weight: float = 1.0
    legal_basis: str | None = None
    excerpt: str = ""


# ── Database setup ────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db_path = Path(__file__).parent.parent / "backend" / "blackswanx.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_mesh_tables() -> None:
    """Create contractual mesh persistence tables (idempotent)."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ms_contract_nodes (
            node_id     TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            node_type   TEXT NOT NULL,
            doc_type    TEXT,
            doc_id      INTEGER,
            legal_ref   TEXT,
            properties  TEXT DEFAULT '{}',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_contract_edges (
            edge_id     TEXT PRIMARY KEY,
            src         TEXT NOT NULL,
            tgt         TEXT NOT NULL,
            edge_type   TEXT NOT NULL,
            weight      REAL DEFAULT 1.0,
            legal_basis TEXT,
            excerpt     TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_doc_registry (
            doc_id      INTEGER PRIMARY KEY,
            filename    TEXT NOT NULL,
            doc_type    TEXT NOT NULL,
            hierarchy   INTEGER DEFAULT 99,
            positions   TEXT DEFAULT '[]',  -- GAEB positions found
            vob_refs    TEXT DEFAULT '[]',  -- VOB/B paragraphs cited
            din_refs    TEXT DEFAULT '[]',  -- DIN standards cited
            registered_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Utility ───────────────────────────────────────────────────────────────────

def _classify_doc_type(filename: str, text_sample: str) -> str:
    """Classify document type from filename + first 2000 chars of text."""
    combined = (filename + " " + text_sample[:2000]).lower()
    for pattern, doc_type in DOC_TYPE_PATTERNS:
        if re.search(pattern, combined):
            return doc_type
    return "UNKNOWN"


def _node_id(name: str, node_type: str) -> str:
    import hashlib
    return hashlib.md5(f"{node_type}:{name}".encode()).hexdigest()[:16]


def _edge_id(src: str, tgt: str, etype: str) -> str:
    import hashlib
    return hashlib.md5(f"{src}:{tgt}:{etype}".encode()).hexdigest()[:16]


def _upsert_node(conn: sqlite3.Connection, node: ContractNode) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO ms_contract_nodes
           (node_id, name, node_type, doc_type, doc_id, legal_ref, properties)
           VALUES (?,?,?,?,?,?,?)""",
        (node.node_id, node.name, node.node_type, node.doc_type,
         node.doc_id, node.legal_ref, json.dumps(node.properties))
    )


def _upsert_edge(conn: sqlite3.Connection, edge: ContractEdge) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO ms_contract_edges
           (edge_id, src, tgt, edge_type, weight, legal_basis, excerpt)
           VALUES (?,?,?,?,?,?,?)""",
        (edge.edge_id, edge.src, edge.tgt, edge.edge_type,
         edge.weight, edge.legal_basis, edge.excerpt[:200])
    )


# ── Pass 1: Document Hierarchy Mapping ───────────────────────────────────────

def register_document(doc_id: int, filename: str, text: str) -> dict:
    """
    Register a document in the mesh. Classifies type, extracts references.
    Returns registration summary.
    """
    init_mesh_tables()
    doc_type = _classify_doc_type(filename, text)
    hierarchy_level = DOC_HIERARCHY.get(doc_type, 99)

    # Extract structured references
    positions = list(set(GAEB_POSITION_PATTERN.findall(text)))
    vob_refs = list(set(
        f"VOB/B {m.group(1).strip()}"
        for m in VOB_REF_PATTERN.finditer(text)
    ))
    din_refs = list(set(m.group(1).strip() for m in DIN_PATTERN.finditer(text)))

    conn = _get_db()
    conn.execute(
        """INSERT OR REPLACE INTO ms_doc_registry
           (doc_id, filename, doc_type, hierarchy, positions, vob_refs, din_refs)
           VALUES (?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_type, hierarchy_level,
         json.dumps(positions), json.dumps(vob_refs), json.dumps(din_refs))
    )

    # Create doc node
    doc_node = ContractNode(
        node_id=_node_id(filename, "DOC"),
        name=filename,
        node_type="DOC",
        doc_type=doc_type,
        doc_id=doc_id,
    )
    _upsert_node(conn, doc_node)
    conn.commit()
    conn.close()

    return {
        "doc_id": doc_id,
        "filename": filename,
        "doc_type": doc_type,
        "hierarchy_level": hierarchy_level,
        "gaeb_positions": positions,
        "vob_refs": vob_refs,
        "din_refs": din_refs,
    }


def build_hierarchy_edges(project_doc_ids: list[int] | None = None) -> dict:
    """
    Pass 1: Connect documents by their legal hierarchy.
    Hauptvertrag → Anlage → LV → Nachtrag (parent_of / amends edges).
    """
    init_mesh_tables()
    conn = _get_db()

    if project_doc_ids:
        placeholders = ",".join("?" * len(project_doc_ids))
        docs = conn.execute(
            f"SELECT * FROM ms_doc_registry WHERE doc_id IN ({placeholders}) "
            f"ORDER BY hierarchy ASC",
            project_doc_ids
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT * FROM ms_doc_registry ORDER BY hierarchy ASC"
        ).fetchall()

    docs = [dict(d) for d in docs]
    edges_added = 0

    # Group by hierarchy level
    by_level: dict[int, list[dict]] = {}
    for doc in docs:
        lvl = doc["hierarchy"]
        by_level.setdefault(lvl, []).append(doc)

    # Connect each doc to the most recent parent-level doc
    levels = sorted(by_level.keys())
    for i, lvl in enumerate(levels[1:], 1):
        parent_level = levels[i - 1]
        parents = by_level[parent_level]
        children = by_level[lvl]

        for child in children:
            for parent in parents:
                # Determine edge type
                if child["doc_type"] == "NACHTRAG":
                    etype = "amends"
                    legal = "VOB/B §2 Abs. 5 — Nachtrag modifies original contract"
                elif child["doc_type"] in ("ANLAGE", "LEISTUNGSBESCHREIBUNG"):
                    etype = "supplements"
                    legal = "Vertragsbestandteil gemäß §1 VOB/B"
                else:
                    etype = "parent_of"
                    legal = None

                edge = ContractEdge(
                    edge_id=_edge_id(
                        _node_id(parent["filename"], "DOC"),
                        _node_id(child["filename"], "DOC"),
                        etype
                    ),
                    src=_node_id(parent["filename"], "DOC"),
                    tgt=_node_id(child["filename"], "DOC"),
                    edge_type=etype,
                    weight=1.0,
                    legal_basis=legal,
                    excerpt=f"{parent['doc_type']} → {child['doc_type']}"
                )
                _upsert_edge(conn, edge)
                edges_added += 1

    conn.commit()
    conn.close()
    return {"pass": 1, "edges_added": edges_added, "docs_processed": len(docs)}


# ── Pass 2: GAEB Positionsnummer Linking ─────────────────────────────────────

def build_position_edges(project_doc_ids: list[int] | None = None) -> dict:
    """
    Pass 2: Link nodes across documents via shared GAEB Positionsnummern.
    Same position number in LV + Nachtrag + Rechnung = deterministic edge.
    Weight: 1.0 (exact match, not probabilistic).
    """
    init_mesh_tables()
    conn = _get_db()

    if project_doc_ids:
        placeholders = ",".join("?" * len(project_doc_ids))
        docs = conn.execute(
            f"SELECT * FROM ms_doc_registry WHERE doc_id IN ({placeholders})",
            project_doc_ids
        ).fetchall()
    else:
        docs = conn.execute("SELECT * FROM ms_doc_registry").fetchall()

    docs = [dict(d) for d in docs]
    edges_added = 0
    position_map: dict[str, list[dict]] = {}

    # Index which docs contain which positions
    for doc in docs:
        positions = json.loads(doc["positions"] or "[]")
        for pos in positions:
            position_map.setdefault(pos, []).append(doc)

            # Create position node
            pos_node = ContractNode(
                node_id=_node_id(pos, "GAEB_POSITION"),
                name=pos,
                node_type="GAEB_POSITION",
                legal_ref=f"GAEB Position {pos}",
            )
            _upsert_node(conn, pos_node)

    # Connect docs to their positions and positions to each other (cross-doc)
    for pos, pos_docs in position_map.items():
        pos_node_id = _node_id(pos, "GAEB_POSITION")

        for doc in pos_docs:
            doc_node_id = _node_id(doc["filename"], "DOC")
            edge = ContractEdge(
                edge_id=_edge_id(doc_node_id, pos_node_id, "references_position"),
                src=doc_node_id,
                tgt=pos_node_id,
                edge_type="references_position",
                weight=1.0,
                legal_basis=f"GAEB Position {pos} in {doc['doc_type']}",
                excerpt=f"{doc['filename']} references position {pos}"
            )
            _upsert_edge(conn, edge)
            edges_added += 1

        # Cross-document: if same position appears in LV and NACHTRAG, direct edge
        if len(pos_docs) >= 2:
            for i in range(len(pos_docs)):
                for j in range(i + 1, len(pos_docs)):
                    a, b = pos_docs[i], pos_docs[j]
                    # Nachtrag modifying LV position is the key relationship
                    if {a["doc_type"], b["doc_type"]} == {"NACHTRAG", "LV"}:
                        legal = f"VOB/B §2 Abs. 5 — Nachtrag modifies LV Position {pos}"
                    elif {a["doc_type"], b["doc_type"]} == {"RECHNUNG", "LV"}:
                        legal = f"VOB/B §14 — Rechnung references LV Position {pos}"
                    else:
                        legal = f"Shared GAEB Position {pos}"

                    edge = ContractEdge(
                        edge_id=_edge_id(
                            _node_id(a["filename"], "DOC"),
                            _node_id(b["filename"], "DOC"),
                            f"shares_position_{pos}"
                        ),
                        src=_node_id(a["filename"], "DOC"),
                        tgt=_node_id(b["filename"], "DOC"),
                        edge_type="shares_position",
                        weight=1.0,
                        legal_basis=legal,
                        excerpt=f"Both reference GAEB Position {pos}"
                    )
                    _upsert_edge(conn, edge)
                    edges_added += 1

    conn.commit()
    conn.close()
    return {
        "pass": 2,
        "edges_added": edges_added,
        "unique_positions": len(position_map),
        "cross_doc_positions": sum(1 for v in position_map.values() if len(v) >= 2)
    }


# ── Pass 3: VOB/B + DIN Standard Resolution ──────────────────────────────────

def build_legal_reference_edges(project_doc_ids: list[int] | None = None) -> dict:
    """
    Pass 3: Create canonical VOB/B paragraph nodes and DIN standard nodes.
    All documents citing the same legal reference connect through it.
    Enables: 'Show me all clauses across all projects governed by VOB/B §13 Abs. 4'
    """
    init_mesh_tables()
    conn = _get_db()

    if project_doc_ids:
        placeholders = ",".join("?" * len(project_doc_ids))
        docs = conn.execute(
            f"SELECT * FROM ms_doc_registry WHERE doc_id IN ({placeholders})",
            project_doc_ids
        ).fetchall()
    else:
        docs = conn.execute("SELECT * FROM ms_doc_registry").fetchall()

    docs = [dict(d) for d in docs]
    edges_added = 0

    for doc in docs:
        doc_node_id = _node_id(doc["filename"], "DOC")

        # VOB/B paragraph nodes
        vob_refs = json.loads(doc["vob_refs"] or "[]")
        for ref in vob_refs:
            # Normalise: "VOB/B § 2 Abs. 5" → "VOB/B §2 abs. 5"
            ref_key = re.sub(r'\s+', ' ', ref.lower().replace("abs.", "abs."))
            description = VOB_B_PARAGRAPHS.get(
                ref_key.replace("vob/b ", ""),
                "VOB/B Regelung"
            )
            vob_node = ContractNode(
                node_id=_node_id(ref, "VOB_PARAGRAPH"),
                name=ref,
                node_type="VOB_PARAGRAPH",
                legal_ref=ref,
                properties={"description": description}
            )
            _upsert_node(conn, vob_node)

            edge = ContractEdge(
                edge_id=_edge_id(doc_node_id, vob_node.node_id, "governed_by"),
                src=doc_node_id,
                tgt=vob_node.node_id,
                edge_type="governed_by",
                weight=1.0,
                legal_basis=f"{ref} — {description}",
                excerpt=f"{doc['filename']} governed by {ref}"
            )
            _upsert_edge(conn, edge)
            edges_added += 1

        # DIN standard nodes
        din_refs = json.loads(doc["din_refs"] or "[]")
        for din in din_refs:
            din_node = ContractNode(
                node_id=_node_id(din, "DIN_STANDARD"),
                name=din,
                node_type="DIN_STANDARD",
                legal_ref=din,
            )
            _upsert_node(conn, din_node)

            edge = ContractEdge(
                edge_id=_edge_id(doc_node_id, din_node.node_id, "references_standard"),
                src=doc_node_id,
                tgt=din_node.node_id,
                edge_type="references_standard",
                weight=1.0,
                legal_basis=f"Technical standard {din}",
                excerpt=f"{doc['filename']} references {din}"
            )
            _upsert_edge(conn, edge)
            edges_added += 1

    conn.commit()
    conn.close()
    return {"pass": 3, "edges_added": edges_added, "docs_processed": len(docs)}


# ── Full mesh build ───────────────────────────────────────────────────────────

def build_contractual_mesh(
    documents: list[dict],  # [{"doc_id": int, "filename": str, "text": str}]
) -> dict:
    """
    Full pipeline: register all documents, then run all 3 passes.

    Args:
        documents: list of dicts with doc_id, filename, text

    Returns:
        Summary of nodes and edges built.
    """
    init_mesh_tables()

    # Register all documents
    registrations = [
        register_document(d["doc_id"], d["filename"], d["text"])
        for d in documents
    ]
    doc_ids = [d["doc_id"] for d in documents]

    # Run all 3 passes
    p1 = build_hierarchy_edges(doc_ids)
    p2 = build_position_edges(doc_ids)
    p3 = build_legal_reference_edges(doc_ids)

    conn = _get_db()
    total_nodes = conn.execute("SELECT COUNT(*) FROM ms_contract_nodes").fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM ms_contract_edges").fetchone()[0]
    conn.close()

    return {
        "documents_registered": len(registrations),
        "doc_types": {r["doc_type"] for r in registrations},
        "pass_1_hierarchy": p1,
        "pass_2_gaeb_positions": p2,
        "pass_3_legal_refs": p3,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "unique_positions": p2["unique_positions"],
        "cross_doc_positions": p2["cross_doc_positions"],
    }


# ── Query API ─────────────────────────────────────────────────────────────────

def get_position_history(position: str) -> dict:
    """
    Get full history of a GAEB position across all documents.
    Shows how a line item evolved from LV → Nachtrag → Rechnung.
    """
    conn = _get_db()
    pos_node_id = _node_id(position, "GAEB_POSITION")

    connected = conn.execute(
        """SELECT r.*, e.edge_type, e.legal_basis
           FROM ms_contract_edges e
           JOIN ms_doc_registry r ON (
               ms_contract_nodes.node_id = e.src AND r.doc_id = ms_contract_nodes.doc_id
           )
           JOIN ms_contract_nodes ON ms_contract_nodes.node_id = e.src
           WHERE e.tgt = ? OR e.src = ?
           ORDER BY r.hierarchy ASC""",
        (pos_node_id, pos_node_id)
    ).fetchall()
    conn.close()

    return {
        "position": position,
        "appearances": [dict(r) for r in connected],
        "count": len(connected)
    }


def get_vob_governed_docs(paragraph: str) -> list[dict]:
    """
    Find all documents governed by a specific VOB/B paragraph.
    E.g. get_vob_governed_docs('§13 Abs. 4') → all contracts with this Gewährleistungsfrist clause.
    """
    conn = _get_db()
    vob_node_id = _node_id(f"VOB/B {paragraph}", "VOB_PARAGRAPH")

    docs = conn.execute(
        """SELECT r.*, e.edge_type, e.legal_basis
           FROM ms_contract_edges e
           JOIN ms_doc_registry r ON r.doc_id = (
               SELECT doc_id FROM ms_contract_nodes WHERE node_id = e.src
           )
           WHERE e.tgt = ? AND e.edge_type = 'governed_by'""",
        (vob_node_id,)
    ).fetchall()
    conn.close()
    return [dict(d) for d in docs]
