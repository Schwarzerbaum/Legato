#!/usr/bin/env python3
"""
Phase 2 Improvement #2: Semantic Graph Traversal (Graph RAG) (+8%)

Current approach: Text retrieval + keyword entity matching
Graph RAG approach: Convert question → mini-graph → traverse graph → synthesize

Example:
  Q: "How does CDE relate to BAP?"
  → Mini-graph: {entities: [CDE, BAP], relations: [relates_to]}
  → Traverse: CDE → (enables) → Review Process → (requires) → Approval
  → Feed explicit structural path to LLM
  → Synthesis: "CDE enables the Review Process, which requires Approval per BAP"

Benefit: Multi-hop reasoning, explicit structural understanding, no hallucination.
"""
import json
import re
from typing import Optional
from collections import defaultdict, deque


class SemanticGraphTraversal:
    """Convert questions to graphs, traverse entity relationships."""

    def __init__(self, graph: dict):
        """Initialize with entity/relation graph."""
        self.entities = {e["name"].lower(): e for e in graph.get("entities", [])}
        self.relations = graph.get("relations", [])
        self.build_adjacency()

    def build_adjacency(self):
        """Build adjacency lists for fast traversal."""
        self.adjacency = defaultdict(list)  # source → [(target, relation_type, description)]
        self.reverse_adjacency = defaultdict(list)  # target → [(source, relation_type, description)]

        for rel in self.relations:
            source = rel.get("source", "").lower()
            target = rel.get("target", "").lower()
            rel_type = rel.get("type", "")
            desc = rel.get("description", "")

            self.adjacency[source].append((target, rel_type, desc))
            self.reverse_adjacency[target].append((source, rel_type, desc))

    def extract_mini_graph_from_question(self, question: str) -> dict:
        """
        Convert question text into entities + expected relationships.
        Uses Qwen to understand intent.
        """
        try:
            import httpx

            prompt = f"""Extract the core entities and relationship from this question.
Return JSON: {{"entities": ["Entity1", "Entity2", ...], "relationship": "related_type"}}

Question: {question}

Return ONLY JSON, no preamble."""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 200, "temperature": 0.1}
                },
                timeout=60
            )
            response.raise_for_status()

            response_text = response.json().get("response", "").strip()
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                return json.loads(match.group())

        except Exception:
            pass

        # Fallback: extract named entities via regex
        entity_names = list(self.entities.keys())
        found_entities = [
            ent for ent in entity_names
            if ent in question.lower()
        ]

        return {
            "entities": found_entities,
            "relationship": "related_to"
        }

    def traverse(
        self,
        start_entity: str,
        max_depth: int = 2,
        max_results: int = 10
    ) -> list[dict]:
        """
        BFS traversal from start entity up to max_depth hops.
        Returns: [{path, relations, entities}]
        """
        start_lower = start_entity.lower()
        if start_lower not in self.entities:
            return []

        paths = []
        visited = set()
        queue = deque([(start_lower, [start_lower], [], 0)])

        while queue and len(paths) < max_results:
            current, path, relations_path, depth = queue.popleft()

            if (current, depth) in visited:
                continue
            visited.add((current, depth))

            # Current path is valid
            if depth > 0:
                paths.append({
                    "path": path,
                    "relations": relations_path,
                    "depth": depth
                })

            # Continue traversal if depth < max
            if depth < max_depth:
                # Forward edges
                for target, rel_type, desc in self.adjacency.get(current, []):
                    if target not in path:
                        queue.append((
                            target,
                            path + [target],
                            relations_path + [{"type": rel_type, "description": desc}],
                            depth + 1
                        ))

                # Reverse edges
                for source, rel_type, desc in self.reverse_adjacency.get(current, []):
                    if source not in path:
                        queue.append((
                            source,
                            [source] + path,
                            [{"type": rel_type, "description": desc}] + relations_path,
                            depth + 1
                        ))

        return paths

    def find_connections(
        self,
        entity1: str,
        entity2: str,
        max_depth: int = 2
    ) -> Optional[dict]:
        """
        Find shortest path between two entities.
        Example: CDE → BAP
        """
        e1_lower = entity1.lower()
        e2_lower = entity2.lower()

        if e1_lower not in self.entities or e2_lower not in self.entities:
            return None

        # BFS to find shortest path
        queue = deque([(e1_lower, [e1_lower], [], 0)])
        visited = set()

        while queue:
            current, path, relations_path, depth = queue.popleft()

            if current == e2_lower:
                return {
                    "source": entity1,
                    "target": entity2,
                    "path": [self.entities[e]["name"] for e in path],
                    "relations": relations_path,
                    "distance": depth
                }

            if (current, depth) in visited or depth >= max_depth:
                continue
            visited.add((current, depth))

            # Explore neighbors
            for target, rel_type, desc in self.adjacency.get(current, []):
                if target not in path:
                    queue.append((
                        target,
                        path + [target],
                        relations_path + [{"type": rel_type, "description": desc}],
                        depth + 1
                    ))

        return None

    def format_traversal_for_synthesis(self, paths: list[dict]) -> str:
        """Format graph traversal results as context for LLM synthesis."""
        if not paths:
            return ""

        formatted = "Graph Structure:\n"
        for i, path_info in enumerate(paths[:5], 1):  # Top 5 paths
            path = path_info["path"]
            relations = path_info["relations"]

            # Build path string: Entity1 -[relation]-> Entity2 -[relation]-> Entity3
            path_str = path[0]
            for j, entity in enumerate(path[1:]):
                rel = relations[j] if j < len(relations) else {}
                rel_type = rel.get("type", "related_to")
                path_str += f" -[{rel_type}]-> {entity}"

            formatted += f"  Path {i}: {path_str}\n"

        return formatted


# ── Integration with QA Runtime ────────────────────────────────────────────

def enhance_qa_with_graph_rag(
    question: str,
    graph_dict: dict,
    retrieved_text: str = ""
) -> str:
    """
    Use Graph RAG to enhance answer synthesis.
    Returns enriched context string for LLM synthesis.
    """
    traversal = SemanticGraphTraversal(graph_dict)

    # Extract mini-graph from question
    mini_graph = traversal.extract_mini_graph_from_question(question)

    # Traverse graph starting from each entity
    all_paths = []
    for entity in mini_graph.get("entities", [])[:3]:  # Top 3 entities
        paths = traversal.traverse(entity, max_depth=2, max_results=5)
        all_paths.extend(paths)

    # Find direct connections between entity pairs
    entities = mini_graph.get("entities", [])
    if len(entities) >= 2:
        connection = traversal.find_connections(entities[0], entities[1], max_depth=3)
        if connection:
            all_paths.insert(0, {
                "path": connection["path"],
                "relations": connection["relations"],
                "depth": connection["distance"],
                "is_direct": True
            })

    # Format for synthesis
    graph_context = traversal.format_traversal_for_synthesis(all_paths)

    # Combine with retrieved text
    enhanced_context = retrieved_text
    if graph_context:
        enhanced_context += "\n\n" + graph_context

    return enhanced_context
