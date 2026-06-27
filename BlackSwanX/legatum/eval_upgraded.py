#!/usr/bin/env python3
"""
Evaluation: Current RRF + new LLM harvester (Option A integration).
Tests legatum/graph_store.py with PR #2's windowed entity/relation extraction.
"""
import json
import sys
from pathlib import Path
import pypdfium2 as pdfium
import yaml
import re

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from legatum.graph_store import (
    harvest_from_pages, graph_ground, semantic_search, embed_sections, save_graph
)

def extract_text_from_pdf(pdf_path: str) -> list[tuple[int, str]]:
    """Extract text from each page."""
    pdf = pdfium.PdfDocument(pdf_path)
    pages = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                text = page.get_textpage().get_text_range()
            except Exception:
                text = ""
            pages.append((i, text or ""))
    finally:
        pdf.close()
    return pages


def synthesize_answer(question: str, context: str, graph_facts: dict) -> str:
    """Synthesize answer grounded in context + graph."""
    try:
        import httpx

        if not context.strip() and not graph_facts.get("entities"):
            return "Diese Information ist nicht in den bereitgestellten Dokumenten enthalten."

        # Build grounding context
        ent_str = ", ".join(e["name"] for e in graph_facts.get("entities", [])[:5])
        rel_str = "; ".join(
            f'{r["source"]}-[{r["type"]}]->{r["target"]}'
            for r in graph_facts.get("relations", [])[:3]
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
        print(f"  [Synthesis failed: {str(e)[:80]}]", file=sys.stderr)
        return context[:300] + "..." if context else "Fehler bei der Synthese."


def judge_answer(question: str, expected: str, answer: str) -> tuple[str, float]:
    """Judge answer correctness."""
    try:
        import httpx

        prompt = f"""Bewerte diese Q&A-Antwort gegen die Musterantwort.
Werte nur Korrektheit, nicht Wortlaut.
Antworte mit JSON: {{"verdict": "correct"|"partial"|"incorrect", "score": 0-1}}

Frage: {question}

Musterantwort:
{expected[:500]}

System-Antwort:
{answer[:500]}"""

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

        try:
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return (
                    data.get("verdict", "incorrect"),
                    float(data.get("score", 0))
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return ("incorrect", 0.0)

    except Exception:
        return ("incorrect", 0.0)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 eval_upgraded.py <pdf_path> <questions_yaml>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    yaml_path = sys.argv[2]

    print(f"\n{'='*72}")
    print(f"  LEGATUM RAG — Option A (RRF + LLM Harvester)")
    print(f"{'='*72}\n")

    # 1. Extract PDF
    print(f"[1/5] Extracting PDF: {Path(pdf_path).name}")
    pages = extract_text_from_pdf(pdf_path)
    print(f"      → {len(pages)} pages extracted\n")

    # 2. Build property graph with harvester
    print(f"[2/5] Harvesting entities/relations with LLM...")
    page_texts = [(p, t) for p, t in pages]
    harvest = harvest_from_pages(page_texts, window_size=3, overlap=1)
    print(f"      → {len(harvest['entities'])} entities, {len(harvest['relations'])} relations")
    print(f"      → {len(harvest['mentions'])} mention(s) across pages\n")

    # 3. Embed sections for retrieval
    print(f"[3/5] Embedding sections...")
    sections = [
        {
            "page": p,
            "heading": f"Page {p}",
            "text": t[:1000] if t else ""
        }
        for p, t in pages
    ]
    sections = embed_sections(sections)
    print(f"      → {sum(1 for s in sections if s.get('embedding'))} sections embedded\n")

    # 4. Load questions
    print(f"[4/5] Loading questions...")
    with open(yaml_path) as f:
        raw_yaml = f.read()

    questions = []
    for part in re.split(r"(?m)^document:", raw_yaml):
        if not part.strip():
            continue
        block = yaml.safe_load("document:" + part) or {}
        questions.extend(block.get("questions", []) or [])

    print(f"      → {len(questions)} questions loaded\n")

    # 5. Evaluate
    print(f"[5/5] Running evaluation...\n")
    results = []

    for i, q in enumerate(questions, 1):
        qid = q.get("id", "?")
        question_text = q.get("question", "")
        expected = q.get("expected_answer", "")
        if isinstance(expected, (list, dict)):
            expected = json.dumps(expected, ensure_ascii=False)

        print(f"  [{i:2d}] {qid}: ", end="", flush=True)

        # Retrieve with RRF
        hits = semantic_search(question_text, sections, top_k=5)
        context = "\n".join(s.get("text", "") for s in hits)[:2000]

        # Ground in extracted graph
        graph_facts = graph_ground(question_text, harvest)

        # Synthesize
        answer = synthesize_answer(question_text, context, graph_facts)

        # Judge
        verdict, score = judge_answer(question_text, expected, answer)

        color_map = {"correct": "\033[92m", "partial": "\033[93m", "incorrect": "\033[91m"}
        reset = "\033[0m"
        color = color_map.get(verdict, "")

        print(f"{color}{verdict:10s}{reset} {score:.2f}")

        results.append({
            "id": qid,
            "verdict": verdict,
            "score": score,
            "retrieved_pages": [s.get("page") for s in hits],
            "grounded_entities": [e["name"] for e in graph_facts.get("entities", [])[:3]]
        })

    # Summary
    print(f"\n{'='*72}")
    correct = sum(1 for r in results if r["verdict"] == "correct")
    partial = sum(1 for r in results if r["verdict"] == "partial")
    incorrect = sum(1 for r in results if r["verdict"] == "incorrect")
    avg_score = sum(r["score"] for r in results) / max(len(results), 1)

    print(f"  RESULTS — Option A Hybrid")
    print(f"  \033[92m{correct} correct\033[0m · \033[93m{partial} partial\033[0m · \033[91m{incorrect} incorrect\033[0m")
    print(f"  Average score: {avg_score:.1%}")
    print(f"{'='*72}\n")

    # Save
    out = Path(__file__).parent / "eval_upgraded_results.json"
    out.write_text(json.dumps({
        "summary": {
            "total": len(results),
            "correct": correct,
            "partial": partial,
            "incorrect": incorrect,
            "avg_score": round(avg_score, 3),
        },
        "harvest": {
            "entities": len(harvest["entities"]),
            "relations": len(harvest["relations"]),
            "mentions": len(harvest["mentions"]),
        },
        "results": results,
    }, indent=2, ensure_ascii=False))

    print(f"Results saved to: {out}\n")
    print("COMPARISON:")
    print("─" * 72)
    print(f"Phase 1 (text-only retrieval):     45.0%")
    print(f"Option A (RRF + LLM harvester):    {avg_score:.1%}")
    print(f"Target (PR #2 full multimodal):    65-75%")
    print("─" * 72 + "\n")


if __name__ == "__main__":
    main()
