#!/usr/bin/env python3
"""
Fast Q&A Runtime — Uses preprocessed index + Phase 2 improvements.

All heavy lifting (embedding, OCR, extraction) already done offline.
Runtime: Load index → Retrieve (hybrid) → Enhance (graph/layout/hierarchical)
         → Grade (corrective) → Synthesize (30s per question).
"""
import json
import sys
import math
import re
from pathlib import Path
from typing import Optional
from collections import deque, defaultdict


# ── Phase 2 Imports ────────────────────────────────────────────────────────

class GraphRAGEnhancer:
    """Graph RAG: multi-hop traversal for entity connections."""
    def __init__(self, graph: dict):
        self.entities = {e["name"].lower(): e for e in graph.get("entities", [])}
        self.relations = graph.get("relations", [])
        self.build_adjacency()

    def build_adjacency(self):
        self.adjacency = defaultdict(list)
        self.reverse_adjacency = defaultdict(list)
        for rel in self.relations:
            src = rel.get("source", "").lower()
            tgt = rel.get("target", "").lower()
            rel_type = rel.get("type", "")
            desc = rel.get("description", "")
            self.adjacency[src].append((tgt, rel_type, desc))
            self.reverse_adjacency[tgt].append((src, rel_type, desc))

    def find_connections(self, entity1: str, entity2: str, max_depth: int = 2) -> Optional[dict]:
        """Find shortest path between two entities."""
        e1_lower = entity1.lower()
        e2_lower = entity2.lower()
        if e1_lower not in self.entities or e2_lower not in self.entities:
            return None

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

            for target, rel_type, desc in self.adjacency.get(current, []):
                if target not in path:
                    queue.append((target, path + [target], relations_path + [{"type": rel_type, "description": desc}], depth + 1))

        return None

    def format_paths(self, entity_names: list[str]) -> str:
        """Format multi-hop connections for synthesis."""
        if not entity_names or len(entity_names) < 2:
            return ""

        paths = []
        for i in range(len(entity_names) - 1):
            conn = self.find_connections(entity_names[i], entity_names[i + 1])
            if conn:
                path_str = conn["path"][0]
                for j, entity in enumerate(conn["path"][1:]):
                    rel = conn["relations"][j] if j < len(conn["relations"]) else {}
                    rel_type = rel.get("type", "related_to")
                    path_str += f" -[{rel_type}]-> {entity}"
                paths.append(path_str)

        return "\n".join(f"  Path {i}: {p}" for i, p in enumerate(paths, 1)) if paths else ""


class HierarchicalChunkingEnhancer:
    """Detect chapters/sections and lock retrieval to relevant hierarchy."""
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.structure = self.detect_structure()

    def detect_structure(self) -> dict:
        structure = {"chapters": [], "page_to_chapter": {}}
        current_chapter = None

        for page in self.pages:
            text = page.get("text", "")
            page_num = page.get("page", 0)

            chapter_match = re.search(r"(?:Kapitel|Chapter|Teil)\s+(\d+)", text, re.IGNORECASE)
            if chapter_match:
                current_chapter = {
                    "number": chapter_match.group(1),
                    "start_page": page_num,
                    "end_page": page_num
                }
                structure["chapters"].append(current_chapter)
                structure["page_to_chapter"][page_num] = len(structure["chapters"]) - 1

        return structure

    def retrieve_by_chapter(self, pages: list[dict], chapter_num: str) -> list[dict]:
        """Filter pages to specific chapter."""
        chapter_pages = [p for p in pages if self.structure["page_to_chapter"].get(p.get("page"), -1) >= 0]
        return [p for p in chapter_pages if p.get("page", 0) >= int(chapter_num) * 5]  # rough heuristic


class LayoutAwareParsing:
    """Extract and preserve table structure."""
    @staticmethod
    def detect_tables(text: str) -> list[str]:
        """Simple table detection (pipe-delimited rows)."""
        lines = text.split("\n")
        pipe_lines = [l for l in lines if "|" in l]
        return pipe_lines if len(pipe_lines) >= 3 else []

    @staticmethod
    def format_for_synthesis(pages: list[dict]) -> str:
        """Extract table context for LLM."""
        context = ""
        for page in pages[:3]:  # top 3 pages
            text = page.get("text", "")
            if "|" in text:
                lines = [l for l in text.split("\n") if "|" in l]
                if lines:
                    context += f"\n**Table from page {page.get('page', '?')}:**\n"
                    context += "\n".join(lines[:10]) + "\n"
        return context


class CorrectiveRAG:
    """Grade context quality and retry if insufficient."""
    @staticmethod
    def grade_context_simple(question: str, context: str) -> str:
        """Simple heuristic grading."""
        q_terms = [t.lower() for t in question.split() if len(t) > 3]
        context_lower = context.lower()
        matches = sum(1 for term in q_terms if term in context_lower)
        ratio = matches / max(len(q_terms), 1)

        if ratio > 0.6:
            return "correct"
        elif ratio > 0.2:
            return "ambiguous"
        else:
            return "missing"


class QARuntimeOptimized:
    """Fast Q&A pipeline using preprocessed index."""

    def __init__(self, index_file: str):
        """Load preprocessed index from disk."""
        self.index_file = Path(index_file)
        self.index = json.loads(self.index_file.read_text())
        self.pages = self.index.get("pages", [])
        self.graph = self.index.get("graph", {})

        print(f"[INFO] Loaded index: {self.index_file.name}", file=sys.stderr)
        print(f"       {self.index['stats']['total_pages']} pages, "
              f"{self.index['stats']['total_entities']} entities", file=sys.stderr)

    def retrieve_hybrid(self, question: str, k: int = 5) -> list[dict]:
        """
        Hybrid retrieval: dense (embedding similarity) + sparse (BM25).
        Fast because vectors are pre-computed.
        """
        # Embed question (lightweight, already cached)
        q_embedding = self._embed_question(question)

        # Dense retrieval (cosine similarity)
        scored = []
        for i, page in enumerate(self.pages):
            page_emb = page.get("embedding", [])
            if q_embedding and page_emb:
                cosine = self._cosine_similarity(q_embedding, page_emb)
                scored.append((i, "dense", cosine))

        # Sparse retrieval (BM25 approx)
        q_terms = [t for t in question.lower().split() if len(t) > 3]
        for i, page in enumerate(self.pages):
            text_lower = page.get("text", "").lower()
            matches = sum(text_lower.count(term) for term in q_terms)
            if matches > 0:
                score = matches / max(len(q_terms), 1)
                scored.append((i, "sparse", score))

        # RRF fusion
        from collections import defaultdict
        rank_scores = defaultdict(float)
        for i, method, score in scored:
            rank_scores[i] += score

        top_pages = sorted(rank_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return [self.pages[i] for i, _ in top_pages]

    def ground_in_graph(self, question: str) -> dict:
        """Find matching entities/relations in the property graph."""
        entities = self.graph.get("entities", [])
        relations = self.graph.get("relations", [])

        question_lower = question.lower()

        # Match entities
        matching_ents = []
        matched_keys = set()
        for ent in entities:
            name = ent.get("name", "").lower()
            if name in question_lower or any(word in question_lower for word in name.split()):
                matching_ents.append({
                    "name": ent.get("name", ""),
                    "type": ent.get("type", ""),
                    "description": ent.get("description", "")
                })
                matched_keys.add(name)

        # Match relations
        matching_rels = []
        for rel in relations:
            source = rel.get("source", "").lower()
            target = rel.get("target", "").lower()
            if source in matched_keys or target in matched_keys:
                matching_rels.append({
                    "source": rel.get("source", ""),
                    "target": rel.get("target", ""),
                    "type": rel.get("type", ""),
                    "description": rel.get("description", "")
                })

        return {
            "entities": matching_ents[:10],
            "relations": matching_rels[:10]
        }

    def synthesize(self, question: str, retrieved: list[dict], grounding: dict) -> str:
        """Synthesize answer with Phase 2 enhancements: Graph RAG + Layout + Corrective."""
        try:
            import httpx

            # === Phase 2: Layout-Aware Parsing ===
            layout_context = LayoutAwareParsing.format_for_synthesis(retrieved)

            # === Phase 2: Graph RAG (multi-hop connections) ===
            graph_rag = GraphRAGEnhancer(self.graph)
            entity_names = [e["name"] for e in grounding.get("entities", [])[:3]]
            graph_paths = graph_rag.format_paths(entity_names)

            # === Phase 2: Corrective RAG (grade context) ===
            base_context = "\n\n".join(p.get("text", "")[:1500] for p in retrieved)
            grade = CorrectiveRAG.grade_context_simple(question, base_context)

            ent_str = ", ".join(e["name"] for e in grounding.get("entities", [])[:5])
            rel_str = "; ".join(
                f'{r["source"]}-[{r["type"]}]->{r["target"]}'
                for r in grounding.get("relations", [])[:3]
            )

            context_parts = [
                "Verfügbarer Kontext:",
                "",
                "Seitentexte:",
                base_context[:7500],
            ]

            if graph_paths:
                context_parts.extend(["", "Graph-Strukturen (Beziehungen):", graph_paths])

            if layout_context:
                context_parts.extend(["", "Tabellen und Struktur:", layout_context])

            context_parts.extend([
                "",
                f"Bekannte Entitäten: {ent_str or '(keine)'}",
                f"Beziehungen: {rel_str or '(keine)'}",
                f"[Kontextqualität: {grade}]"
            ])

            context_str = "\n".join(context_parts)

            prompt = f"""Beantworte diese Frage NUR basierend auf dem bereitgestellten Kontext.
Antworte auf Deutsch, kurz und faktisch.
Wenn die Antwort im Kontext nicht enthalten ist, antworte: "Diese Information ist nicht verfügbar."
Nutze die Graphstrukturen und Tabellen zur Orientierung.

Frage: {question}

{context_str}"""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 500, "temperature": 0.1}
                },
                timeout=120
            )
            response.raise_for_status()

            return response.json().get("response", "").strip()

        except Exception as e:
            print(f"[WARNING] Synthesis failed: {str(e)[:80]}", file=sys.stderr)
            return "Antwort konnte nicht generiert werden."

    def answer_question(self, question: str) -> tuple[str, dict]:
        """Answer a single question, return answer + metadata."""
        # Retrieve
        retrieved = self.retrieve_hybrid(question, k=5)

        # Ground
        grounding = self.ground_in_graph(question)

        # Synthesize (with Phase 2 enhancements)
        answer = self.synthesize(question, retrieved, grounding)

        return answer, {
            "retrieved_pages": [p.get("page", 0) for p in retrieved],
            "entities_used": len(grounding.get("entities", [])),
            "relations_used": len(grounding.get("relations", []))
        }

    def evaluate(self, questions_yaml_path: str) -> dict:
        """Evaluate against question set."""
        import yaml

        with open(questions_yaml_path) as f:
            raw_yaml = f.read()

        questions = []
        for part in re.split(r"(?m)^document:", raw_yaml):
            if not part.strip():
                continue
            block = yaml.safe_load("document:" + part) or {}
            doc = block.get("document", block) or {}
            questions.extend(doc.get("questions", []) or [])

        results = []
        for i, q in enumerate(questions, 1):
            qid = q.get("id", "?")
            question_text = q.get("question", "")
            expected = q.get("expected_answer", "")

            print(f"  [{i:2d}] {qid}: ", end="", flush=True)

            answer, metadata = self.answer_question(question_text)

            # Judge
            verdict, score = self._judge(question_text, expected, answer)

            color_map = {
                "correct": "\033[92m",
                "partial": "\033[93m",
                "incorrect": "\033[91m"
            }
            reset = "\033[0m"

            print(f"{color_map.get(verdict, '')}{verdict:10s}{reset} {score:.2f}")

            results.append({
                "id": qid,
                "verdict": verdict,
                "score": score,
                "answer": answer[:200],
                "metadata": metadata
            })

        avg_score = sum(r["score"] for r in results) / max(len(results), 1)
        correct = sum(1 for r in results if r["verdict"] == "correct")
        partial = sum(1 for r in results if r["verdict"] == "partial")

        return {
            "total": len(results),
            "correct": correct,
            "partial": partial,
            "incorrect": len(results) - correct - partial,
            "avg_score": round(avg_score, 3),
            "results": results
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _embed_question(self, question: str) -> list[float]:
        """Embed question with multilingual sentence-transformer (German-capable, CPU-safe)."""
        try:
            from sentence_transformers import SentenceTransformer
            if not hasattr(self, "_st_model"):
                # paraphrase-multilingual-MiniLM-L12-v2: 118MB, German/multilingual, CPU fast
                self._st_model = SentenceTransformer(
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    device="cpu"
                )
            return self._st_model.encode(question, normalize_embeddings=True).tolist()
        except Exception:
            return []

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b + 1e-9) if norm_a > 0 and norm_b > 0 else 0.0

    def _judge(self, question: str, expected: str, answer: str) -> tuple[str, float]:
        """Judge using LLM with robust JSON extraction — strips <think> blocks, clamps score."""
        if not answer or not expected:
            return ("incorrect", 0.0)

        # Fast-fail on refusal answers
        refusals = ["nicht verfügbar", "nicht enthalten", "nicht vorhanden",
                    "not available", "keine information"]
        if any(r in answer.lower() for r in refusals):
            return ("incorrect", 0.0)

        try:
            import httpx

            prompt = (
                f"Beantworte: Ist diese Antwort korrekt, teilweise korrekt oder falsch?\n"
                f"Antworte NUR mit einem JSON-Objekt: {{\"verdict\": \"correct\"|\"partial\"|\"incorrect\", \"score\": 0.0-1.0}}\n\n"
                f"Frage: {question}\n"
                f"Erwartete Antwort: {expected[:250]}\n"
                f"Gegebene Antwort: {answer[:250]}\n\n"
                f"JSON:"
            )

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 80, "temperature": 0.0}
                },
                timeout=90
            )
            response.raise_for_status()

            text = response.json().get("response", "").strip()
            # Strip <think> blocks
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            # Extract first balanced JSON object
            match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                verdict = data.get("verdict", "incorrect")
                raw = float(data.get("score", 0))
                # Normalize if model used 0-10 scale
                score = raw / 10.0 if raw > 1.0 else raw
                score = max(0.0, min(1.0, score))
                # Reconcile verdict with score
                if score >= 0.75:
                    return ("correct", score)
                elif score >= 0.35:
                    return ("partial", score)
                else:
                    return ("incorrect", score)
        except Exception:
            pass

        return ("incorrect", 0.0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 qa_runtime.py <index_file> [questions_yaml]")
        sys.exit(1)

    index_file = sys.argv[1]
    questions_yaml = sys.argv[2] if len(sys.argv) > 2 else None

    runtime = QARuntimeOptimized(index_file)

    if questions_yaml:
        # Evaluate mode
        print(f"\n{'='*72}")
        print(f"  Q&A Runtime Evaluation")
        print(f"{'='*72}\n")

        results = runtime.evaluate(questions_yaml)

        print(f"\n{'='*72}")
        print(f"  Results")
        print(f"  \033[92m{results['correct']} correct\033[0m · "
              f"\033[93m{results['partial']} partial\033[0m · "
              f"\033[91m{results['incorrect']} incorrect\033[0m")
        print(f"  Average: {results['avg_score']:.1%}")
        print(f"{'='*72}\n")
    else:
        # Interactive mode
        print(f"\nQ&A Runtime ready. Type questions (Ctrl+C to exit):\n")
        while True:
            try:
                question = input("Q: ").strip()
                if not question:
                    continue
                answer = runtime.answer_question(question)
                print(f"A: {answer}\n")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")
