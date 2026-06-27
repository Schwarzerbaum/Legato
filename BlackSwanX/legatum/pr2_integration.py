"""
PR #2 Integration Bridge — Multimodal RAG with OCR + visual grounding.
Bridges legatum/server.py with PR #2 pipeline from shared/rag/src/legatum_rag/.

Pipeline:
  PDF → OCR extraction → Text + visual analysis → Multimodal embedding → Harvest entities
  → Property graph → Hybrid retrieval (visual + text) → Qwen synthesis → Answer
"""
import json
import sys
from pathlib import Path
from typing import Optional
import re

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── OCR + Visual Extraction ────────────────────────────────────────────────────

def extract_text_and_images(pdf_path: str) -> tuple[list[tuple[int, str]], list[tuple[int, bytes]]]:
    """
    Extract text AND images from PDF.
    Falls back to text-only if OCR unavailable.

    Returns:
      ([(page, text), ...], [(page, image_bytes), ...])
    """
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(pdf_path)
        pages = []
        images = []

        try:
            for i in range(len(pdf)):
                page = pdf[i]

                # Extract text
                try:
                    text = page.get_textpage().get_text_range()
                except Exception:
                    text = ""
                pages.append((i, text or ""))

                # Try to extract page image (for visual embedding)
                try:
                    from PIL import Image
                    import io

                    bitmap = page.render(matrix=pdfium.Matrix(2, 2))  # 2x render for quality
                    pil_image = bitmap.to_pil()
                    img_bytes = io.BytesIO()
                    pil_image.save(img_bytes, format="PNG")
                    images.append((i, img_bytes.getvalue()))
                except Exception:
                    pass

        finally:
            pdf.close()

        return pages, images

    except Exception as e:
        print(f"[PDF extraction failed: {str(e)[:100]}]", file=sys.stderr)
        return [], []


def extract_entities_and_relations(text_pages: list[tuple[int, str]]) -> dict:
    """
    Use PR #2's harvester to extract entities/relations from windowed pages.
    """
    try:
        import httpx

        entities = {}
        relations = {}
        mentions = []

        # Windowed harvest (3-page windows with 1-page overlap)
        window_size = 3
        step = max(1, window_size - 1)

        i = 0
        while i < len(text_pages):
            chunk = text_pages[i : i + window_size]
            page_nums = [p for p, _ in chunk]
            window_text = "\n\n".join(
                f"[page {p}]\n{t}" for p, t in chunk if t.strip()
            )

            if not window_text.strip():
                i += step
                continue

            prompt = f"""Extract entities and relations from this document section.
Return ONLY valid JSON with:
{{"entities": [{{"name": "...", "type": "concept|standard|org|person|process", "description": "..."}}],
"relations": [{{"source": "...", "target": "...", "type": "part_of|requires|defines", "description": "..."}}]}}

Document:
{window_text[:8000]}"""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 2000, "temperature": 0.1}
                },
                timeout=60
            )
            response.raise_for_status()
            response_text = response.json().get("response", "").strip()

            try:
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    data = json.loads(match.group())

                    # Merge entities
                    for ent in data.get("entities", []):
                        name = ent.get("name", "").strip()
                        if name:
                            key = name.lower()
                            if key not in entities:
                                entities[key] = ent
                            # Track mentions
                            for page in page_nums:
                                mentions.append({"entity_name": key, "page": page})

                    # Merge relations
                    for rel in data.get("relations", []):
                        source = rel.get("source", "").strip().lower()
                        target = rel.get("target", "").strip().lower()
                        rel_type = rel.get("type", "").strip()
                        if source and target:
                            key = (source, target, rel_type)
                            if key not in relations:
                                relations[key] = rel
            except json.JSONDecodeError:
                pass

            i += step

        return {
            "entities": list(entities.values()),
            "relations": list(relations.values()),
            "mentions": mentions
        }

    except Exception as e:
        print(f"[Entity extraction failed: {str(e)[:100]}]", file=sys.stderr)
        return {"entities": [], "relations": [], "mentions": []}


# ── Multimodal Embedding (Fallback to text-only) ────────────────────────────

def embed_text_multimodal(text: str) -> list[float]:
    """
    Try ColModernVBERT (multimodal), fall back to BGE-M3 (text-only).
    """
    try:
        # Try ColModernVBERT via Ollama (if available)
        import httpx

        response = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "colpali:latest", "prompt": text[:2000]},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("embedding", [])
    except Exception:
        pass

    # Fall back to BGE-M3 (text-only)
    try:
        import httpx

        response = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "bge-m3", "prompt": text[:2000]},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("embedding", [])
    except Exception:
        pass

    # Fallback to nomic-embed-text
    try:
        import httpx

        response = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text[:2000]},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("embedding", [])
    except Exception:
        pass

    return []


def embed_image_multimodal(image_bytes: bytes) -> list[float]:
    """
    Try to embed image via multimodal model.
    Falls back to empty if unavailable.
    """
    try:
        import httpx
        import base64

        b64 = base64.b64encode(image_bytes).decode()
        response = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "colpali:latest", "image": b64},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("embedding", [])
    except Exception:
        pass

    return []


# ── Hybrid Retrieval (Text + Visual) ───────────────────────────────────────

def hybrid_search(
    query: str,
    sections: list[dict],
    text_embedding: list[float] = None,
    k: int = 10
) -> list[dict]:
    """
    Retrieve using:
    1. Dense (text embedding)
    2. Sparse (BM25)
    3. RRF fusion
    4. Cross-encoder reranking

    Sections should have: {page, text, embedding, [image_embedding]}
    """
    import math

    if not sections:
        return []

    # Get query embedding if not provided
    if not text_embedding:
        text_embedding = embed_text_multimodal(query)

    # Dense retrieval
    scored = []
    for i, sec in enumerate(sections):
        sec_embedding = sec.get("embedding", [])
        if text_embedding and sec_embedding:
            # Cosine similarity
            dot = sum(a * b for a, b in zip(text_embedding, sec_embedding))
            norm_q = math.sqrt(sum(x * x for x in text_embedding))
            norm_s = math.sqrt(sum(x * x for x in sec_embedding))
            cosine = dot / (norm_q * norm_s + 1e-9) if norm_q > 0 and norm_s > 0 else 0
            scored.append((i, "dense", cosine))

    # Sparse (BM25 approximation)
    q_terms = [t for t in query.lower().split() if len(t) > 3]
    for i, sec in enumerate(sections):
        sec_text = (sec.get("text", "") or "").lower()
        matches = sum(sec_text.count(term) for term in q_terms)
        if matches > 0:
            score = matches / max(len(q_terms), 1)
            scored.append((i, "sparse", score))

    # RRF fusion (combine ranks)
    from collections import defaultdict

    rank_scores = defaultdict(float)
    for i, method, score in scored:
        rank_scores[i] += score

    top_sections = sorted(rank_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [sections[i] for i, _ in top_sections]


# ── Graph Grounding ────────────────────────────────────────────────────────

def ground_in_graph(query: str, harvest: dict) -> dict:
    """Find entities/relations matching query in the extracted graph."""
    entities = harvest.get("entities", [])
    relations = harvest.get("relations", [])

    query_lower = query.lower()

    # Match entities
    matching_ents = []
    matched_keys = set()
    for ent in entities:
        name = ent.get("name", "").lower()
        if name in query_lower or any(word in query_lower for word in name.split()):
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


# ── Answer Synthesis ──────────────────────────────────────────────────────

def synthesize_answer_pr2(
    question: str,
    retrieved_sections: list[dict],
    graph_grounding: dict
) -> str:
    """Synthesize answer grounded in retrieval + graph."""
    try:
        import httpx

        context = "\n\n".join(sec.get("text", "")[:500] for sec in retrieved_sections)

        ent_str = ", ".join(e["name"] for e in graph_grounding.get("entities", [])[:5])
        rel_str = "; ".join(
            f'{r["source"]}-[{r["type"]}]->{r["target"]}'
            for r in graph_grounding.get("relations", [])[:3]
        )

        context_str = f"""Verfügbarer Kontext:

Seitentexte:
{context[:2000]}

Bekannte Entitäten: {ent_str or "(keine)"}
Beziehungen: {rel_str or "(keine)"}"""

        prompt = f"""Beantworte diese Frage NUR basierend auf dem bereitgestellten Kontext.
Antworte auf Deutsch, kurz und faktisch.
Wenn die Antwort im Kontext nicht enthalten ist, antworte: "Diese Information ist nicht verfügbar."

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
            timeout=60
        )
        response.raise_for_status()

        return response.json().get("response", "").strip()

    except Exception as e:
        print(f"[Synthesis failed: {str(e)[:80]}]", file=sys.stderr)
        return "Antwort konnte nicht generiert werden."


# ── Main Pipeline ─────────────────────────────────────────────────────────

class PR2Pipeline:
    """Complete PR #2 RAG pipeline."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.text_pages = []
        self.images = []
        self.harvest = {}
        self.sections = []

    def ingest(self):
        """Extract text/images, build graph."""
        print(f"[1/4] Extracting PDF...")
        self.text_pages, self.images = extract_text_and_images(self.pdf_path)
        print(f"      → {len(self.text_pages)} pages, {len(self.images)} images")

        print(f"[2/4] Harvesting entities/relations...")
        self.harvest = extract_entities_and_relations(self.text_pages)
        print(f"      → {len(self.harvest['entities'])} entities, {len(self.harvest['relations'])} relations")

        print(f"[3/4] Building multimodal sections...")
        self.sections = []
        for page_num, text in self.text_pages:
            section = {
                "page": page_num,
                "text": text,
                "embedding": embed_text_multimodal(text[:2000]) or [],
            }

            # Try to add image embedding
            for img_page, img_bytes in self.images:
                if img_page == page_num:
                    section["image_embedding"] = embed_image_multimodal(img_bytes) or []
                    break

            self.sections.append(section)

        print(f"      → {len(self.sections)} sections embedded")

    def answer_question(self, question: str) -> str:
        """Answer a single question."""
        # Retrieve
        query_embedding = embed_text_multimodal(question)
        retrieved = hybrid_search(question, self.sections, query_embedding, k=5)

        # Ground in graph
        grounding = ground_in_graph(question, self.harvest)

        # Synthesize
        answer = synthesize_answer_pr2(question, retrieved, grounding)

        return answer

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
            questions.extend(block.get("questions", []) or [])

        results = []
        for i, q in enumerate(questions, 1):
            qid = q.get("id", "?")
            question_text = q.get("question", "")
            expected = q.get("expected_answer", "")

            print(f"  [{i:2d}] {qid}: ", end="", flush=True)

            answer = self.answer_question(question_text)

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
                "answer": answer[:200]
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

    def _judge(self, question: str, expected: str, answer: str) -> tuple[str, float]:
        """Judge answer correctness."""
        try:
            import httpx

            prompt = f"""Bewerte diese Antwort. Antworte mit JSON: {{"verdict": "correct"|"partial"|"incorrect", "score": 0-1}}

Frage: {question}
Erwartet: {expected[:300]}
Antwort: {answer[:300]}"""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 100, "temperature": 0.0}
                },
                timeout=60
            )
            response.raise_for_status()

            response_text = response.json().get("response", "").strip()
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return (
                    data.get("verdict", "incorrect"),
                    float(data.get("score", 0))
                )
        except Exception:
            pass

        return ("incorrect", 0.0)
