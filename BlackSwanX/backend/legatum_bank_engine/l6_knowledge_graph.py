"""
L6 — AI Agent Knowledge Graph
Relationship mesh across donors, NGOs, foundations, and SDGs.
Backed by SQLite for persistence; exportable as JSON for D3 visualisation.
"""
from __future__ import annotations
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

NodeType  = Literal["donor", "ngo", "sdg", "foundation", "advisor"]
EdgeRel   = Literal["funds", "aligns_with", "founded_by", "targets_sdg", "advised_by", "co_funds"]

_DB_PATH  = Path(__file__).parent.parent.parent / "blackswanx.db"
_lock     = threading.Lock()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables() -> None:
    with _lock, _db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS lkg_nodes (
            id         TEXT PRIMARY KEY,
            node_type  TEXT NOT NULL,
            label      TEXT NOT NULL,
            metadata   TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS lkg_edges (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id    TEXT NOT NULL,
            to_id      TEXT NOT NULL,
            relation   TEXT NOT NULL,
            weight     REAL DEFAULT 1.0,
            UNIQUE(from_id, to_id, relation)
        );
        """)


_ensure_tables()


@dataclass
class KGNode:
    id: str
    node_type: NodeType
    label: str
    metadata: dict = field(default_factory=dict)


@dataclass
class KGEdge:
    from_id: str
    to_id: str
    relation: EdgeRel
    weight: float = 1.0


def add_node(node: KGNode) -> KGNode:
    with _lock, _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO lkg_nodes (id, node_type, label, metadata) VALUES (?,?,?,?)",
            (node.id, node.node_type, node.label, json.dumps(node.metadata)),
        )
    return node


def add_edge(edge: KGEdge) -> KGEdge:
    with _lock, _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO lkg_edges (from_id, to_id, relation, weight) VALUES (?,?,?,?)",
            (edge.from_id, edge.to_id, edge.relation, edge.weight),
        )
    return edge


def get_graph() -> dict:
    with _db() as conn:
        nodes = [dict(r) for r in conn.execute("SELECT * FROM lkg_nodes").fetchall()]
        edges = [dict(r) for r in conn.execute("SELECT * FROM lkg_edges").fetchall()]
    # Parse metadata JSON
    for n in nodes:
        try:
            n["metadata"] = json.loads(n.get("metadata") or "{}")
        except Exception:
            n["metadata"] = {}
    return {"nodes": nodes, "edges": edges}


def query_neighbours(node_id: str) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM lkg_edges WHERE from_id=? OR to_id=?", (node_id, node_id)
        ).fetchall()
        neighbour_ids = {
            r["to_id"] if r["from_id"] == node_id else r["from_id"]
            for r in rows
        }
        nodes = [
            dict(r) for r in conn.execute(
                f"SELECT * FROM lkg_nodes WHERE id IN ({','.join('?'*len(neighbour_ids))})",
                list(neighbour_ids),
            ).fetchall()
        ] if neighbour_ids else []
    return nodes


def get_stats() -> dict:
    with _db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM lkg_nodes").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM lkg_edges").fetchone()[0]
        by_type = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT node_type, COUNT(*) FROM lkg_nodes GROUP BY node_type"
            ).fetchall()
        }
    return {"total_nodes": n, "total_edges": e, "by_type": by_type}


def seed_demo_graph() -> dict:
    """Insert a minimal demo graph for the hackathon demo."""
    demo_nodes = [
        KGNode("donor-fam-mueller", "donor",     "Familie Müller Stiftung"),
        KGNode("donor-meyer",       "donor",     "Dr. Meyer Legacy Fund"),
        KGNode("ngo-bund",          "ngo",       "BUND e.V."),
        KGNode("ngo-welthunger",    "ngo",       "Welthungerhilfe"),
        KGNode("sdg-13",            "sdg",       "SDG 13 Climate Action"),
        KGNode("sdg-2",             "sdg",       "SDG 2 Zero Hunger"),
        KGNode("advisor-hoffmann",  "advisor",   "Dr. Anna Hoffmann"),
    ]
    demo_edges = [
        KGEdge("donor-fam-mueller", "ngo-bund",         "funds",       0.9),
        KGEdge("donor-fam-mueller", "ngo-welthunger",   "funds",       0.6),
        KGEdge("donor-meyer",       "ngo-welthunger",   "co_funds",    0.7),
        KGEdge("ngo-bund",          "sdg-13",           "targets_sdg", 1.0),
        KGEdge("ngo-welthunger",    "sdg-2",            "targets_sdg", 1.0),
        KGEdge("donor-fam-mueller", "advisor-hoffmann", "advised_by",  1.0),
    ]
    for n in demo_nodes:
        add_node(n)
    for e in demo_edges:
        add_edge(e)
    return get_stats()
