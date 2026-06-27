"""Evaluate retrieval + answer against a YAML question set with gold answers."""
from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from .config import get_settings
from .db import connect
from .retrieve import graph_context, visual_search
def load_questions(path: str | Path) -> list[dict]:
    import yaml  # noqa: PLC0415
    text = Path(path).read_text(encoding="utf-8")
    questions: list[dict] = []
    for part in re.split(r"(?m)^document:", text):
        if not part.strip():
            continue
        block = yaml.safe_load("document:" + part) or {}
        questions.extend(block.get("questions", []) or [])
    return questions
def _expected_str(q: dict) -> str:
    ea = q.get("expected_answer")
    return ea if isinstance(ea, str) else json.dumps(ea, ensure_ascii=False)
def _pages_text(hits, per_page: int = 1500, cap: int = 6000) -> str:
    if not hits:
        return "(keine Seiten abgerufen)"
    out: list[str] = []
    with connect() as conn:
        with conn.cursor() as cur:
            for h in hits:
                cur.execute(
                    "SELECT content FROM pages WHERE doc_id=%s AND page=%s",
                    (h.doc_id, h.page),
                )
                row = cur.fetchone()
                if row and row[0]:
                    out.append(f"[render-page {h.page}]\n{row[0][:per_page]}")
    return "\n\n".join(out)[:cap]
def _graph_text(query: str) -> str:
    gc = graph_context(query)
    ents = ", ".join(e["name"] for e in gc.get("entities", [])[:10])
    rels = "; ".join(
        f'{r["source"]} -[{r["type"]}]-> {r["target"]}' for r in gc.get("relations", [])[:10]
    )
    return f"Entitäten: {ents or '—'}\nBeziehungen: {rels or '—'}"
@lru_cache
def _llm():
    from .llm import chat_model  # noqa: PLC0415
    return chat_model()
def answer_question(question: str, k: int = 5):
    hits = visual_search(question, k=k)
    pages = _pages_text(hits)
    prompt = (
        "Beantworte die Frage NUR anhand des folgenden Kontexts (abgerufene "
        "Seitentexte, Graph-Fakten). Antworte auf Deutsch, faktisch und knapp. "
        "Wenn der Kontext die Antwort nicht hergibt, sage das ausdrücklich.\n\n"
        f"Frage: {question}\n\n"
        f"=== Abgerufene Seitentexte ===\n{pages}\n\n"
        f"=== Graph-Fakten ===\n{_graph_text(question)}\n"
    )
    msg = _llm().invoke(prompt)
    text = msg.content if isinstance(msg.content, str) else str(msg.content)
    return text.strip(), [h.page for h in hits]
class Verdict(BaseModel):
    verdict: Literal["correct", "partial", "incorrect"] = Field(
        description="correct=all core facts right; partial=partial; incorrect=wrong"
    )
    score: float = Field(ge=0, le=1, description="0..1 score")
    reason: str = Field(description="brief explanation")
@lru_cache
def _judge_llm():
    from .llm import chat_model  # noqa: PLC0415
    return chat_model().with_structured_output(Verdict)
def judge(question: str, expected: str, answer: str) -> Verdict:
    prompt = (
        "Du bewertest eine Q&A-Systemantwort gegen eine Musterantwort. "
        "Bewerte nur fachliche Übereinstimmung.\n\n"
        f"Frage: {question}\n\nMusterantwort:\n{expected}\n\nSystem-Antwort:\n{answer}\n"
    )
    return _judge_llm().invoke(prompt)
def run_eval(path: str | Path, k: int = 5) -> dict:
    questions = load_questions(path)
    rows: list[dict] = []
    for q in questions:
        qid = q.get("id", "?")
        qtext = q.get("question", "")
        try:
            ans, pages = answer_question(qtext, k=k)
            v = judge(qtext, _expected_str(q), ans)
            rows.append(
                {
                    "id": qid,
                    "verdict": v.verdict,
                    "score": round(v.score, 2),
                    "reason": v.reason,
                    "retrieved_pages": pages,
                    "gold_page": q.get("source", {}).get("page"),
                    "answer": ans[:500],
                }
            )
            print(
                f"{qid}: {v.verdict:9s} score={v.score:.2f} "
                f"pages={pages} gold={q.get('source',{}).get('page')}"
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": qid, "verdict": "error", "score": 0.0, "reason": str(exc)[:200]})
            print(f"{qid}: ERROR {str(exc)[:160]}")
    graded = [r for r in rows if r["verdict"] in ("correct", "partial", "incorrect")]
    n = len(graded) or 1
    summary = {
        "questions": len(rows),
        "correct": sum(r["verdict"] == "correct" for r in graded),
        "partial": sum(r["verdict"] == "partial" for r in graded),
        "incorrect": sum(r["verdict"] == "incorrect" for r in graded),
        "errors": sum(r["verdict"] == "error" for r in rows),
        "avg_score": round(sum(r["score"] for r in graded) / n, 3),
    }
    return {"summary": summary, "rows": rows}
def run_eval_cli() -> None:
    """`uv run legatum-rag-eval <questions.yaml>` — score retrieval+answer."""
    import sys
    if len(sys.argv) < 2:
        print("usage: legatum-rag-eval <questions.yaml> [k]")
        raise SystemExit(2)
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    result = run_eval(sys.argv[1], k=k)
    out = get_settings().data_dir / "eval-results.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    s = result["summary"]
    print(
        f"\n=== SUMMARY ===\n{s['correct']} correct · {s['partial']} partial · "
        f"{s['incorrect']} incorrect · {s['errors']} errors  |  avg score {s['avg_score']}  "
        f"(of {s['questions']} questions)\nwrote {out}"
    )
