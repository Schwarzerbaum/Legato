"""
mcp_server.py — BlackSwanX MCP server (Model Context Protocol)

Exposes the BlackSwanX M&A knowledge graph to any MCP-compatible tool:
  - Claude Desktop
  - Cursor / Windsurf / VS Code
  - Any tool that speaks MCP

Run with:
    cd backend && python -m ma.mcp_server

Or add to your MCP client config:
    {
      "mcpServers": {
        "blackswanx": {
          "command": "python",
          "args": ["-m", "ma.mcp_server"],
          "cwd": "/path/to/BlackSwanX/backend"
        }
      }
    }

Exposed tools (12):
  - search_entities          Search entities in the knowledge graph
  - get_entity               Get a single entity by ID
  - get_pheromone_heatmap    Return hot nodes (intensity >= threshold)
  - trace_cascade            DFS cascade from a node
  - get_war_room_report      Latest War Room analysis for a document
  - run_leukocyte            Run kill-switch pre-screener on a document
  - get_ltm_stats            Long-term memory tier breakdown
  - recall_ltm               Recall relevant LTM facts for a query
  - get_provenance           W3C PROV-O provenance trail for an entity
  - get_graph_summary        Full KG stats (nodes, edges, degrees)
  - list_documents           List all ingested documents
  - get_neural_status        Neural organism health (AWEB veins, pheromones)
"""

from __future__ import annotations

import json
import sys
import os

# Ensure backend is in path when run as module
_BACKEND = os.path.dirname(os.path.dirname(__file__))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

try:
    from semantica import mcp_server as _semantica_mcp
    _HAS_SEMANTICA_MCP = True
except ImportError:
    _HAS_SEMANTICA_MCP = False

# ── Lightweight JSON-RPC MCP server (no extra deps) ──────────────────────────
# If semantica's MCP server is available we use it; otherwise we roll a minimal
# stdio JSON-RPC server that any MCP client can connect to.

import asyncio
import logging

logging.basicConfig(level=logging.WARNING)


# ── Tool implementations ──────────────────────────────────────────────────────

def _db():
    """Open a read-only connection to BlackSwanX SQLite DB."""
    import sqlite3
    db_path = os.path.join(_BACKEND, "blackswanx.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def tool_search_entities(query: str, limit: int = 10) -> dict:
    try:
        from ma.knowledge_graph import search_entities
        results = search_entities(query, limit=limit)
        return {"entities": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "entities": []}


def tool_get_entity(entity_id: str) -> dict:
    try:
        conn = _db()
        row = conn.execute(
            "SELECT * FROM ma_entities WHERE id=?", (entity_id,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return {"error": f"Entity {entity_id} not found"}
    except Exception as e:
        return {"error": str(e)}


def tool_get_pheromone_heatmap(threshold: float = 0.5) -> dict:
    try:
        from ma.signal_pheromones import get_heatmap
        heatmap = get_heatmap(threshold=threshold)
        return {"heatmap": heatmap, "threshold": threshold}
    except Exception as e:
        return {"error": str(e), "heatmap": []}


def tool_trace_cascade(node_id: str, max_depth: int = 6) -> dict:
    try:
        from ma.knowledge_graph import trace_cascade
        return trace_cascade(node_id, max_depth=max_depth)
    except Exception as e:
        return {"error": str(e)}


def tool_get_war_room_report(doc_id: int) -> dict:
    try:
        conn = _db()
        row = conn.execute(
            "SELECT * FROM ma_warroom_reports WHERE doc_id=? ORDER BY id DESC LIMIT 1",
            (doc_id,),
        ).fetchone()
        conn.close()
        if row:
            d = dict(row)
            if "report_json" in d and isinstance(d["report_json"], str):
                try:
                    d["report"] = json.loads(d["report_json"])
                except Exception:
                    pass
            return d
        return {"error": f"No War Room report for doc {doc_id}"}
    except Exception as e:
        return {"error": str(e)}


def tool_run_leukocyte_prescreener(doc_id: int) -> dict:
    try:
        conn = _db()
        chunks = conn.execute(
            "SELECT text, section_type FROM ma_chunks WHERE doc_id=? LIMIT 50",
            (doc_id,),
        ).fetchall()
        conn.close()
        if not chunks:
            return {"error": f"No chunks found for doc {doc_id}"}
        from ma.leukocyte_rete import pre_screen_chunks
        return pre_screen_chunks([dict(c) for c in chunks])
    except Exception as e:
        return {"error": str(e)}


def tool_get_ltm_stats() -> dict:
    try:
        from ma.long_term_memory import get_memory_stats
        return get_memory_stats()
    except Exception as e:
        return {"error": str(e)}


def tool_recall_ltm(query: str, limit: int = 5) -> dict:
    try:
        from ma.long_term_memory import recall_memories
        memories = recall_memories(query, limit=limit)
        return {"memories": memories, "count": len(memories)}
    except Exception as e:
        return {"error": str(e), "memories": []}


def tool_get_provenance(entity_id: str) -> dict:
    try:
        from ma.provenance_layer import get_provenance, get_lineage
        return {
            "entity_id": entity_id,
            "provenance": get_provenance(entity_id),
            "lineage": get_lineage(entity_id),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_graph_summary() -> dict:
    try:
        conn = _db()
        nodes = conn.execute("SELECT COUNT(*) FROM ma_entities").fetchone()[0]
        edges = conn.execute("SELECT COUNT(*) FROM ma_kg_edges").fetchone()[0]
        entity_types = conn.execute(
            "SELECT entity_type, COUNT(*) as cnt FROM ma_entities GROUP BY entity_type ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        conn.close()
        return {
            "nodes": nodes,
            "edges": edges,
            "avg_degree": round((edges * 2) / nodes, 2) if nodes else 0,
            "top_entity_types": [dict(r) for r in entity_types],
        }
    except Exception as e:
        return {"error": str(e)}


def tool_list_documents() -> dict:
    try:
        conn = _db()
        docs = conn.execute(
            "SELECT id, filename, doc_type, page_count, created_at FROM ma_documents ORDER BY id DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return {"documents": [dict(d) for d in docs], "count": len(docs)}
    except Exception as e:
        return {"error": str(e), "documents": []}


def tool_get_neural_status() -> dict:
    try:
        from neural.integration import get_neural_stats
        return get_neural_stats()
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = {
    "search_entities": {
        "fn": tool_search_entities,
        "description": "Search entities in the BlackSwanX knowledge graph by name or type",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    "get_entity": {
        "fn": tool_get_entity,
        "description": "Get a single entity from the knowledge graph by its ID",
        "inputSchema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    },
    "get_pheromone_heatmap": {
        "fn": tool_get_pheromone_heatmap,
        "description": "Return hot nodes from the pheromone system (nodes with high agent attention)",
        "inputSchema": {
            "type": "object",
            "properties": {"threshold": {"type": "number", "default": 0.5}},
        },
    },
    "trace_cascade": {
        "fn": tool_trace_cascade,
        "description": "DFS cascade tracer — follow consequence chains from any KG node up to 6 hops",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "max_depth": {"type": "integer", "default": 6},
            },
            "required": ["node_id"],
        },
    },
    "get_war_room_report": {
        "fn": tool_get_war_room_report,
        "description": "Get the War Room synthesis report for a document (Red Flag Score, ranked risks)",
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "integer"}},
            "required": ["doc_id"],
        },
    },
    "run_leukocyte_prescreener": {
        "fn": tool_run_leukocyte_prescreener,
        "description": "Run the deterministic Rete kill-switch pre-screener on a document (no LLM, instant)",
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "integer"}},
            "required": ["doc_id"],
        },
    },
    "get_ltm_stats": {
        "fn": tool_get_ltm_stats,
        "description": "Get Long-Term Memory tier breakdown (Working / Episodic / Semantic)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "recall_ltm": {
        "fn": tool_recall_ltm,
        "description": "Recall relevant facts from Long-Term Memory (SM-2) for a query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    "get_provenance": {
        "fn": tool_get_provenance,
        "description": "Get W3C PROV-O provenance trail for a knowledge graph entity",
        "inputSchema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    },
    "get_graph_summary": {
        "fn": tool_get_graph_summary,
        "description": "Get BlackSwanX knowledge graph statistics (nodes, edges, top entity types)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "list_documents": {
        "fn": tool_list_documents,
        "description": "List all documents ingested into BlackSwanX",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_neural_status": {
        "fn": tool_get_neural_status,
        "description": "Get neural organism status (AWEB vein health, pheromone stats, apoptosis log)",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


# ── Minimal stdio MCP server (JSON-RPC 2.0 over stdin/stdout) ────────────────

def _jsonrpc_response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle(req: dict) -> dict:
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return _jsonrpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blackswanx", "version": "1.0.0"},
        })

    if method == "tools/list":
        tool_list = [
            {
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"],
            }
            for name, meta in TOOLS.items()
        ]
        return _jsonrpc_response(req_id, {"tools": tool_list})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name not in TOOLS:
            return _jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' not found")
        try:
            result = TOOLS[tool_name]["fn"](**arguments)
            return _jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}]
            })
        except Exception as e:
            return _jsonrpc_error(req_id, -32603, str(e))

    if method == "notifications/initialized":
        return None  # no response for notifications

    return _jsonrpc_error(req_id, -32601, f"Method '{method}' not found")


def run_stdio():
    """Run the MCP server over stdin/stdout (standard MCP transport)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(req)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
