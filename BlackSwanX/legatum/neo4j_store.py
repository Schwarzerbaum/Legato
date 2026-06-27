"""
Neo4j GraphRAG backend — optional, activates when NEO4J_URI env var is set.
Falls back to JSON graph_store transparently when Neo4j is unavailable.

Connection:
  NEO4J_URI=bolt://localhost:7687   (default)
  NEO4J_USER=neo4j                  (default)
  NEO4J_PASSWORD=legatum123       (default)

Node labels map 1:1 to our 12-type ontology:
  ACTOR, PROJECT, ASSET, INFORMATION_OBJECT, MODEL, DOCUMENT,
  PROCESS, DATA_ENVIRONMENT, INFORMATION_REQUIREMENT,
  LIFECYCLE_PHASE, STANDARD_OR_RULE, SOFTWARE_OR_TOOL,
  CONSTRAINT, CONCEPT, GAEB_POSITION

Hierarchical edge types (Studio alignment):
  PARENT_OF, SUB_ORGANIZATION_OF, GOVERNED_BY, CONTAINS,
  CREATES, AUTHORS, IS_EXECUTED_BY, PRODUCES, MUST_COMPLY_WITH,
  IS_CHECKED_AGAINST, SATISFIES, APPLIES_IN, IS_STORED_IN,
  IS_RESPONSIBLE_FOR, HAS_ACCESS_TO, IS_DEFINED_IN,
  REPORTS_TO, IS_DERIVED_FROM, FULFILS, DEFINES, BOUNDED_BY,
  CO_OCCURS, REFERENCES, HAS_CONSTRAINT
"""
from __future__ import annotations
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_NEO4J_URI  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
_NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "legatum123")

_driver = None
_available: Optional[bool] = None   # None = not yet tested


def _get_driver():
    global _driver, _available
    if _available is False:
        return None
    if _driver is not None:
        return _driver
    try:
        from neo4j import GraphDatabase
        _driver = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASS))
        _driver.verify_connectivity()
        _available = True
        logger.info(f"Neo4j connected at {_NEO4J_URI}")
        _ensure_schema(_driver)
        return _driver
    except Exception as exc:
        _available = False
        logger.debug(f"Neo4j not available ({exc}) — falling back to JSON store")
        return None


def is_available() -> bool:
    return _get_driver() is not None


def _ensure_schema(driver):
    """Create indexes and constraints once on first connect."""
    with driver.session() as s:
        s.run("CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:DOCUMENT) REQUIRE d.doc_id IS UNIQUE")
        s.run("CREATE INDEX node_id IF NOT EXISTS FOR (n:KGNode) ON (n.id)")
        s.run("CREATE INDEX node_type IF NOT EXISTS FOR (n:KGNode) ON (n.node_type)")
        s.run("CREATE INDEX node_doc IF NOT EXISTS FOR (n:KGNode) ON (n.doc_id)")
        s.run("CREATE INDEX edge_type IF NOT EXISTS FOR ()-[r:KG_EDGE]-() ON (r.edge_type)")


# ── Ingest ─────────────────────────────────────────────────────────────────────

def upsert_graph(pdf_path: str, filename: str, nodes: list, edges: list,
                 sections: list) -> bool:
    """
    Write nodes + edges into Neo4j. Returns True on success.
    Each node gets a :KGNode label plus its specific type label.
    """
    driver = _get_driver()
    if not driver:
        return False

    import hashlib
    doc_id = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]

    with driver.session() as s:
        # Delete stale data for this document
        s.run("MATCH (n:KGNode {doc_id:$doc_id}) DETACH DELETE n", doc_id=doc_id)

        # Upsert nodes — dual label: :KGNode + :TYPE
        for n in nodes:
            ntype = n.get("type", "CONCEPT")
            s.run(
                f"""
                MERGE (n:KGNode {{id:$id, doc_id:$doc_id}})
                SET n.node_type = $ntype,
                    n.page      = $page,
                    n.confidence= $conf,
                    n.method    = $method,
                    n.filename  = $filename
                WITH n
                CALL apoc.create.addLabels(n, [$ntype]) YIELD node RETURN node
                """,
                id=n.get("id"), doc_id=doc_id, ntype=ntype,
                page=n.get("page"), conf=n.get("confidence", 1.0),
                method=n.get("method", "regex"), filename=filename,
            )

        # Upsert edges
        for e in edges:
            etype = (e.get("type") or "CO_OCCURS").upper().replace(" ", "_").replace("-", "_")
            s.run(
                """
                MATCH (src:KGNode {id:$src, doc_id:$doc_id})
                MATCH (tgt:KGNode {id:$tgt, doc_id:$doc_id})
                MERGE (src)-[r:KG_EDGE {edge_type:$etype, doc_id:$doc_id}]->(tgt)
                SET r.confidence = $conf,
                    r.page       = $page,
                    r.method     = $method
                """,
                src=e.get("source"), tgt=e.get("target"), doc_id=doc_id,
                etype=etype, conf=e.get("confidence", 0.9),
                page=e.get("page"), method=e.get("method", "regex"),
            )

    logger.info(f"Neo4j: upserted {len(nodes)} nodes, {len(edges)} edges for {filename}")
    return True


# ── Retrieval ──────────────────────────────────────────────────────────────────

def get_graph(pdf_path: str) -> Optional[dict]:
    """Load nodes + edges from Neo4j for a given pdf_path. Returns graph dict or None."""
    driver = _get_driver()
    if not driver:
        return None

    import hashlib
    doc_id = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]

    with driver.session() as s:
        node_res = s.run(
            "MATCH (n:KGNode {doc_id:$doc_id}) RETURN n.id AS id, n.node_type AS type, "
            "n.page AS page, n.confidence AS confidence, n.method AS method",
            doc_id=doc_id,
        )
        nodes = [dict(r) for r in node_res]

        edge_res = s.run(
            "MATCH (src:KGNode {doc_id:$doc_id})-[r:KG_EDGE]->(tgt:KGNode {doc_id:$doc_id}) "
            "RETURN src.id AS source, src.node_type AS source_type, "
            "tgt.id AS target, tgt.node_type AS target_type, "
            "r.edge_type AS type, r.confidence AS confidence, "
            "r.page AS page, r.method AS method",
            doc_id=doc_id,
        )
        edges = [dict(r) for r in edge_res]

    if not nodes and not edges:
        return None
    return {"nodes": nodes, "edges": edges}


def multi_hop_neo4j(pdf_path: str, start_node: str, max_hops: int = 3,
                    max_results: int = 40) -> list[dict]:
    """
    Cypher-native variable-length path traversal — much faster than Python BFS.
    Returns edges reachable from start_node within max_hops.
    """
    driver = _get_driver()
    if not driver:
        return []

    import hashlib
    doc_id = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]

    with driver.session() as s:
        result = s.run(
            f"""
            MATCH path = (start:KGNode {{id:$start, doc_id:$doc_id}})
                         -[:KG_EDGE*1..{max_hops}]->
                         (end:KGNode {{doc_id:$doc_id}})
            UNWIND relationships(path) AS r
            WITH DISTINCT r, startNode(r) AS src, endNode(r) AS tgt
            RETURN src.id AS source, src.node_type AS source_type,
                   tgt.id AS target, tgt.node_type AS target_type,
                   r.edge_type AS type, r.confidence AS confidence, r.page AS page
            LIMIT {max_results}
            """,
            start=start_node, doc_id=doc_id,
        )
        return [dict(r) for r in result]


def hierarchy_up(pdf_path: str, node_id: str) -> list[dict]:
    """
    Walk PARENT_OF / SUB_ORGANIZATION_OF / GOVERNED_BY edges upward.
    Returns ancestor chain — used for the hierarchical context injection.
    """
    driver = _get_driver()
    if not driver:
        return []

    import hashlib
    doc_id = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]

    with driver.session() as s:
        result = s.run(
            """
            MATCH (start:KGNode {id:$node_id, doc_id:$doc_id})
            MATCH path = (start)<-[:KG_EDGE*1..5 {edge_type: 'PARENT_OF'}]-(ancestor:KGNode)
            RETURN ancestor.id AS id, ancestor.node_type AS type,
                   length(path) AS depth
            ORDER BY depth
            LIMIT 10
            """,
            node_id=node_id, doc_id=doc_id,
        )
        return [dict(r) for r in result]


def fulltext_search_neo4j(pdf_path: str, query_terms: list[str],
                           top_k: int = 20) -> list[dict]:
    """
    Neo4j node search by partial name match — complements vector search.
    Returns edges where source or target node name matches any query term.
    """
    driver = _get_driver()
    if not driver:
        return []

    import hashlib
    doc_id = hashlib.sha256(pdf_path.encode()).hexdigest()[:16]
    term_pattern = "|".join(query_terms[:5])   # regex alternation, max 5 terms

    with driver.session() as s:
        result = s.run(
            f"""
            MATCH (n:KGNode {{doc_id:$doc_id}})
            WHERE n.id =~ '(?i).*({term_pattern}).*'
            MATCH (n)-[r:KG_EDGE]->(m:KGNode {{doc_id:$doc_id}})
            RETURN n.id AS source, n.node_type AS source_type,
                   m.id AS target, m.node_type AS target_type,
                   r.edge_type AS type, r.confidence AS confidence, r.page AS page
            LIMIT {top_k}
            """,
            doc_id=doc_id,
        )
        return [dict(r) for r in result]
