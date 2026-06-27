"""
Structural Graph Dependency Mapping — The Chain Reaction Engine.

Extracts entities and their dependencies from M&A documents, then runs
a Dependency Stress-Test: kill one node, watch the domino cascade.

Entity types:  Company, Contract, Director, FinancialInstrument, IP, Vendor, Customer
Edge types:    depends_on, triggers_default, assignment_restriction,
               change_of_control, cross_default, personal_service, termination_trigger
"""
import re
from collections import defaultdict, deque


# ─────────────────────────────────────────────────────────────
# 1. ENTITY EXTRACTION
# ─────────────────────────────────────────────────────────────

ENTITY_PATTERNS = {
    "Contract": [
        r'\b([A-Z][A-Za-z\s]{2,30}(?:Agreement|Contract|MSA|SLA|License|Lease|Facility|Terms|Deed|Indenture|Note|Bond))\b',
        r'\b((?:Master\s+)?Service\s+Agreement[^,.\n]{0,30})\b',
        r'\b(Enterprise\s+Agreement[^,.\n]{0,30})\b',
        r'\b(Credit\s+Facility[^,.\n]{0,20})\b',
    ],
    "Company": [
        r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:Corp|Inc|LLC|Ltd|GmbH|AG|BV|SAS|NV)\.?)\b',
        r'\b([A-Z][A-Za-z]+Co(?:rp)?\.)\b',
    ],
    "Director": [
        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,?\s*(?:CEO|CFO|CTO|COO|Chairman|Director|President|VP)\b',
        r'(?:CEO|CFO|CTO|COO|Chairman|Director)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
    ],
    "FinancialInstrument": [
        r'\b((?:Revolving\s+)?Credit\s+(?:Facility|Line|Agreement)[^,.\n]{0,20})\b',
        r'\b(Term\s+Loan[^,.\n]{0,20})\b',
        r'\b([\$€][\d,.]+[MBK]?\s+(?:facility|note|bond|loan))\b',
        r'\b(Series\s+[A-Z]\s+(?:Note|Preferred|Bond)[^,.\n]{0,15})\b',
    ],
    "IP": [
        r'\b(Patent\s+No\.?\s*[\d,]+[^,.\n]{0,20})\b',
        r'\b((?:core\s+)?IP\s+portfolio[^,.\n]{0,20})\b',
        r'\b([A-Z][A-Za-z\s]{2,20}(?:trademark|patent|copyright)[^,.\n]{0,15})\b',
    ],
    "Vendor": [
        r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:vendor|supplier|provider|partner)\b',
        r'(?:vendor|supplier|provider|partner)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b',
    ],
}

EDGE_PATTERNS = [
    # Cross-default
    (r'cross[\s-]default', "cross_default", "critical",
     "Breach triggers cross-default in connected credit facilities"),
    # Change of Control
    (r'change\s+of\s+control|change-of-control', "change_of_control", "critical",
     "Acquisition triggers termination or renegotiation"),
    # Material Adverse Effect
    (r'material\s+adverse\s+(?:effect|change|event)|MAE\b|MAC\b', "mae_trigger", "critical",
     "Material Adverse Effect clause activated"),
    # Assignment restriction
    (r'without\s+(?:prior\s+)?written\s+consent|assignment\s+without\s+consent', "assignment_restriction", "high",
     "Cannot be assigned without consent — deal blocker"),
    # Acceleration
    (r'accelerat(?:e|ion)\s+(?:of\s+)?(?:payment|repayment|maturity)', "acceleration", "critical",
     "Payment acceleration triggered on event"),
    # Automatic termination
    (r'automatically\s+terminat|termination\s+(?:is\s+)?automatic', "auto_termination", "critical",
     "Agreement auto-terminates on trigger event"),
    # Personal service / key man
    (r'personal\s+service|key[\s-]man|key\s+person', "personal_service", "high",
     "Non-transferable personal service or key-man dependency"),
    # Vendor dependency
    (r'sole\s+(?:source|supplier|vendor|provider)|exclusive\s+(?:supplier|vendor)', "sole_source", "high",
     "Single-source dependency — no fallback vendor"),
    # IP license dependency
    (r'license\s+(?:shall\s+)?terminat|IP\s+license\s+(?:ends|ceases)', "ip_termination", "high",
     "IP license terminates on trigger"),
    # Guaranty / surety
    (r'personal\s+guaranty|personal\s+guarantee', "personal_guaranty", "medium",
     "Personal guaranty by individual — non-transferable"),
    # Non-compete
    (r'non[\s-]compet', "non_compete", "medium",
     "Non-compete obligation survives acquisition"),
    # Notification obligation
    (r'notify|notification\s+required|written\s+notice\s+(?:of|to)', "notification_required", "low",
     "Party must be notified of change"),
]


def _clean_entity_name(name: str) -> str:
    return re.sub(r'\s+', ' ', name.strip().rstrip('.,'))


def extract_entities_from_chunks(chunks: list[dict]) -> dict:
    """
    Extract all entities and dependency edges from chunks.
    Returns {nodes: [...], edges: [...], entity_map: {...}}
    """
    entity_map = {}   # name → {id, type, mentions, chunk_ids, pages}
    entity_id = [0]

    def add_entity(name: str, etype: str, chunk_id, page: int):
        name = _clean_entity_name(name)
        if len(name) < 4 or len(name) > 80:
            return None
        # Normalize — case-insensitive dedup
        key = name.lower()
        if key not in entity_map:
            entity_id[0] += 1
            entity_map[key] = {
                "id": f"e{entity_id[0]}",
                "name": name,
                "type": etype,
                "mentions": 0,
                "chunk_ids": [],
                "pages": [],
            }
        entity_map[key]["mentions"] += 1
        if chunk_id and chunk_id not in entity_map[key]["chunk_ids"]:
            entity_map[key]["chunk_ids"].append(chunk_id)
        if page and page not in entity_map[key]["pages"]:
            entity_map[key]["pages"].append(page)
        return entity_map[key]["id"]

    # Collect raw edges as (sentence, edge_type, severity, description, chunk_id, page)
    raw_edge_contexts = []

    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("id")
        page = chunk.get("page", 1)

        # Extract entities
        for etype, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    name = m.group(1) if m.lastindex else m.group(0)
                    add_entity(name, etype, chunk_id, page)

        # Extract edge contexts
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            for pattern, edge_type, severity, description in EDGE_PATTERNS:
                if re.search(pattern, sentence, re.IGNORECASE):
                    raw_edge_contexts.append({
                        "sentence": sentence.strip()[:200],
                        "edge_type": edge_type,
                        "severity": severity,
                        "description": description,
                        "chunk_id": chunk_id,
                        "page": page,
                    })
                    break  # One edge type per sentence

    # Build edges by co-occurrence: entities in the same sentence as an edge pattern
    edges = []
    edge_id = [0]

    all_entity_names = list(entity_map.keys())

    for ctx in raw_edge_contexts:
        sentence_lower = ctx["sentence"].lower()
        found_entities = [k for k in all_entity_names if k in sentence_lower and len(k) > 4]

        if len(found_entities) >= 2:
            # Create edge between first two entities found
            src_key = found_entities[0]
            tgt_key = found_entities[1]
            edge_id[0] += 1
            edges.append({
                "id": f"edge{edge_id[0]}",
                "source": entity_map[src_key]["id"],
                "target": entity_map[tgt_key]["id"],
                "source_name": entity_map[src_key]["name"],
                "target_name": entity_map[tgt_key]["name"],
                "edge_type": ctx["edge_type"],
                "severity": ctx["severity"],
                "description": ctx["description"],
                "sentence": ctx["sentence"],
                "chunk_id": ctx["chunk_id"],
                "page": ctx["page"],
            })
        elif len(found_entities) == 1:
            # Self-reference edge — entity has this risk
            src_key = found_entities[0]
            edge_id[0] += 1
            edges.append({
                "id": f"edge{edge_id[0]}",
                "source": entity_map[src_key]["id"],
                "target": entity_map[src_key]["id"],
                "source_name": entity_map[src_key]["name"],
                "target_name": entity_map[src_key]["name"],
                "edge_type": ctx["edge_type"],
                "severity": ctx["severity"],
                "description": ctx["description"],
                "sentence": ctx["sentence"],
                "chunk_id": ctx["chunk_id"],
                "page": ctx["page"],
            })

    # Convert entity_map to node list, filter to entities with 1+ mentions
    nodes = [v for v in entity_map.values() if v["mentions"] >= 1]

    # Deduplicate edges
    seen_edges = set()
    deduped_edges = []
    for e in edges:
        key = f"{e['source']}:{e['target']}:{e['edge_type']}"
        if key not in seen_edges:
            seen_edges.add(key)
            deduped_edges.append(e)

    return {
        "nodes": nodes,
        "edges": deduped_edges,
        "entity_map": {v["id"]: v for v in nodes},
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(deduped_edges),
            "critical_edges": sum(1 for e in deduped_edges if e["severity"] == "critical"),
            "high_edges": sum(1 for e in deduped_edges if e["severity"] == "high"),
        },
    }


# ─────────────────────────────────────────────────────────────
# 2. DEPENDENCY STRESS-TEST — THE DOMINO ENGINE
# ─────────────────────────────────────────────────────────────

CASCADE_RULES = {
    # If this edge type fires, what does it propagate as?
    "cross_default":         ("cross_default",  "critical", "Cross-default clause fires — debt acceleration"),
    "change_of_control":     ("auto_termination","critical", "CoC triggers — contract self-terminates"),
    "mae_trigger":           ("acceleration",   "critical", "MAE → lender can call the loan"),
    "auto_termination":      ("mae_trigger",    "critical", "Termination may constitute MAE in lenders' eyes"),
    "acceleration":          ("cross_default",  "critical", "Acceleration event triggers cross-default"),
    "assignment_restriction":("change_of_control","high",   "Assignment blocked — deal requires consent"),
    "personal_service":      ("auto_termination","high",    "Key person clause — loss terminates agreement"),
    "sole_source":           ("mae_trigger",    "high",     "Sole-source vendor loss = MAE to operations"),
    "ip_termination":        ("mae_trigger",    "critical", "IP license loss = MAE to product / revenue"),
    "non_compete":           ("assignment_restriction","medium","Non-compete restricts acquirer operations"),
    "personal_guaranty":     ("assignment_restriction","medium","Personal guaranty cannot transfer to acquirer"),
    "notification_required": ("assignment_restriction","low","Notification delay may block deal timeline"),
}

SEVERITY_SCORE = {"critical": 40, "high": 25, "medium": 12, "low": 5}


def stress_test(graph: dict, killed_node_id: str) -> dict:
    """
    Simulate killing a node (contract/vendor/entity goes away).
    BFS cascade through dependency edges.
    Returns ordered domino chain with cumulative damage score.
    """
    nodes_by_id = graph.get("entity_map", {})
    edges = graph.get("edges", [])

    if killed_node_id not in nodes_by_id:
        return {"error": f"Node {killed_node_id} not found in graph"}

    killed_node = nodes_by_id[killed_node_id]

    # Build adjacency: source_id → [edge]
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for e in edges:
        outgoing[e["source"]].append(e)
        incoming[e["target"]].append(e)

    # BFS cascade
    cascade_chain = []
    visited = {killed_node_id}
    queue = deque()

    # Seed: all edges FROM the killed node (it's dead → its obligations cascade)
    for edge in outgoing.get(killed_node_id, []):
        queue.append((edge, 1, killed_node["name"]))

    # Also: all edges TO the killed node (dependents lose their source)
    for edge in incoming.get(killed_node_id, []):
        if edge["source"] != killed_node_id:
            queue.append((edge, 1, killed_node["name"]))

    cumulative_score = 0
    step = 0

    while queue and step < 20:  # cap cascade depth
        edge, depth, trigger_name = queue.popleft()
        step += 1

        target_id = edge["target"] if edge["source"] == killed_node_id else edge["source"]
        if target_id == killed_node_id:
            target_id = edge["target"]

        target_node = nodes_by_id.get(target_id, {"name": "Unknown", "type": "Unknown"})
        sev_score = SEVERITY_SCORE.get(edge["severity"], 5)
        cumulative_score += sev_score * max(1, 3 - depth)  # depth decay

        cascade_step = {
            "step": step,
            "depth": depth,
            "node_id": target_id,
            "node_name": target_node.get("name", "Unknown"),
            "node_type": target_node.get("type", "Unknown"),
            "triggered_by": trigger_name,
            "edge_type": edge["edge_type"],
            "severity": edge["severity"],
            "description": edge["description"],
            "sentence": edge.get("sentence", ""),
            "page": edge.get("page", 1),
            "cascade_rule": None,
        }

        # Apply cascade rule — does this node's event propagate further?
        if edge["edge_type"] in CASCADE_RULES and target_id not in visited:
            visited.add(target_id)
            next_edge_type, next_severity, next_desc = CASCADE_RULES[edge["edge_type"]]
            cascade_step["cascade_rule"] = f"→ Propagates as '{next_edge_type}'"

            # Find edges from this target that match the cascade type
            for next_edge in outgoing.get(target_id, []):
                if next_edge["target"] not in visited:
                    # Synthesize a cascade edge
                    synthetic = {
                        **next_edge,
                        "edge_type": next_edge_type,
                        "severity": next_severity,
                        "description": next_desc,
                    }
                    queue.append((synthetic, depth + 1, target_node.get("name", "?")))

        cascade_chain.append(cascade_step)

    cumulative_score = min(100, cumulative_score)

    if cumulative_score >= 70:
        verdict = "CATASTROPHIC — Deal-breaker cascade"
        color = "#ef4444"
    elif cumulative_score >= 40:
        verdict = "SEVERE — Material deal risk"
        color = "#f59e0b"
    elif cumulative_score >= 15:
        verdict = "MODERATE — Requires renegotiation"
        color = "#eab308"
    else:
        verdict = "CONTAINED — Limited blast radius"
        color = "#10b981"

    return {
        "killed_node": killed_node,
        "cascade_chain": cascade_chain,
        "nodes_affected": len(set(s["node_id"] for s in cascade_chain)),
        "max_depth": max((s["depth"] for s in cascade_chain), default=0),
        "cumulative_damage_score": cumulative_score,
        "verdict": verdict,
        "color": color,
        "critical_steps": [s for s in cascade_chain if s["severity"] == "critical"],
    }


def graph_to_d3(graph: dict) -> dict:
    """Convert internal graph to D3-compatible {nodes, links} format."""
    type_colors = {
        "Contract": "#6366f1",
        "Company": "#3b82f6",
        "Director": "#ec4899",
        "FinancialInstrument": "#f59e0b",
        "IP": "#10b981",
        "Vendor": "#8b5cf6",
        "Customer": "#06b6d4",
    }
    severity_colors = {
        "critical": "#ef4444",
        "high": "#f59e0b",
        "medium": "#eab308",
        "low": "#94a3b8",
    }

    d3_nodes = [
        {
            "id": n["id"],
            "name": n["name"],
            "type": n["type"],
            "mentions": n["mentions"],
            "color": type_colors.get(n["type"], "#9ca3af"),
            "radius": min(30, 10 + n["mentions"] * 3),
            "pages": n.get("pages", []),
        }
        for n in graph.get("nodes", [])
    ]

    d3_links = [
        {
            "id": e["id"],
            "source": e["source"],
            "target": e["target"],
            "edge_type": e["edge_type"],
            "severity": e["severity"],
            "description": e["description"],
            "color": severity_colors.get(e["severity"], "#94a3b8"),
            "width": {"critical": 3, "high": 2, "medium": 1.5, "low": 1}.get(e["severity"], 1),
            "sentence": e.get("sentence", ""),
            "page": e.get("page", 1),
        }
        for e in graph.get("edges", [])
        if e["source"] != e["target"]  # exclude self-loops from D3 links
    ]

    return {"nodes": d3_nodes, "links": d3_links, "stats": graph.get("stats", {})}
