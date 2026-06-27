"""
Q&A Evaluation Runner — BIM-Leitfaden 2.0
Runs all questions from the YAML eval file against the live backend
and scores each answer against the expected answer.

Usage:
  python3.14 scripts/eval_qa.py
  python3.14 scripts/eval_qa.py --model llama3.2:3b
  python3.14 scripts/eval_qa.py --questions Q01,Q02,Q05

Scoring (per question):
  GREEN  = answer contains all key expected entities + key phrases  (score 2)
  YELLOW = answer partially matches — some entities found            (score 1)
  RED    = answer misses most/all expected content                   (score 0)
"""
import sys, re, json, time, textwrap, argparse
import httpx
import yaml

BACKEND   = "http://localhost:9200"
PDF_PATH  = "/Users/mango/Downloads/2025_Broschuere_BIM-Leitfaden_2.0_barrierefrei.pdf"
YAML_FILE = "/Users/mango/Downloads/bim_leitfaden_eval_15_questions_draft.yaml"
TIMEOUT   = 120  # seconds per question


def load_questions(yaml_path: str) -> list[dict]:
    """
    Load all questions from the YAML file.
    The file contains two concatenated YAML blocks (Q01-Q15 and Q16-Q18)
    without proper --- separators. We split on `- id:` boundaries.
    """
    with open(yaml_path) as f:
        raw = f.read()

    # Try splitting into separate document blocks at top-level "document:" keys
    # (each block starts with "document:" or "questions:")
    import re as _re
    # Insert --- before each top-level "document:" except the very first
    fixed = _re.sub(r'\n(?=document:\n)', '\n---\n', raw)
    try:
        docs = list(yaml.safe_load_all(fixed))
        questions = []
        for doc in docs:
            if doc and "questions" in doc:
                questions.extend(doc["questions"])
        if questions:
            return questions
    except Exception:
        pass

    # Fallback: extract question blocks by splitting on "- id: Q"
    blocks = _re.split(r'\n(?=- id: Q)', raw)
    questions = []
    for block in blocks:
        try:
            item = yaml.safe_load(block)
            if isinstance(item, dict) and "id" in item:
                questions.append(item)
            elif isinstance(item, list):
                for it in item:
                    if isinstance(it, dict) and "id" in it:
                        questions.append(it)
        except Exception:
            continue
    return questions


def flatten_expected(expected) -> str:
    """Flatten expected_answer to a single string regardless of format."""
    if isinstance(expected, str):
        return expected
    if isinstance(expected, list):
        return " ".join(str(x) for x in expected)
    if isinstance(expected, dict):
        parts = []
        for v in expected.values():
            parts.append(flatten_expected(v))
        return " ".join(parts)
    return str(expected)


def score_answer(answer: str, expected: str, entities: list[str]) -> tuple[str, float, list, list]:
    """
    Compare answer against expected. Returns (color, score, found, missing).
    Scoring:
      - Check expected entities (each worth 1 point)
      - Check key phrases from expected answer (>4 chars, top 8 by length)
    """
    a_lower = answer.lower()

    found = []
    missing = []
    for ent in entities:
        if ent.lower() in a_lower:
            found.append(ent)
        else:
            missing.append(ent)

    # Key phrase check from expected answer
    exp_words = re.findall(r'\b\w{5,}\b', expected.lower())
    # deduplicate, take top-8 most distinctive (longest)
    key_phrases = sorted(set(exp_words), key=len, reverse=True)[:8]
    phrase_hits = sum(1 for p in key_phrases if p in a_lower)
    phrase_ratio = phrase_hits / max(len(key_phrases), 1)

    # "No answer" / "Leider gibt es keine" = instant RED
    no_answer_signals = [
        "keine explizite antwort",
        "no answer",
        "no documents loaded",
        "leider gibt es keine",
        "nicht im dokument",
        "not found",
    ]
    if any(sig in a_lower for sig in no_answer_signals):
        return "RED", 0.0, found, missing

    entity_ratio = len(found) / max(len(entities), 1)
    combined = (entity_ratio * 0.6) + (phrase_ratio * 0.4)

    if combined >= 0.65:
        color = "GREEN"
        score = 2.0
    elif combined >= 0.3:
        color = "YELLOW"
        score = 1.0
    else:
        color = "RED"
        score = 0.0

    return color, score, found, missing


def ask(question: str, model: str = "llama3.2:3b") -> dict:
    payload = {
        "question": question,
        "pdf_paths": [PDF_PATH],
        "generator_model": model,
        "adversarial": False,
        "panel": False,
        "verify": False,
    }
    try:
        r = httpx.post(f"{BACKEND}/api/legatum/documents/qa",
                       json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"answer": f"ERROR: {exc}", "sources": [], "ampel": "red"}


def fmt_color(text: str, color: str) -> str:
    codes = {"GREEN": "\033[92m", "YELLOW": "\033[93m", "RED": "\033[91m", "RESET": "\033[0m"}
    return f"{codes.get(color,'')}{text}{codes['RESET']}"


def run_eval(questions: list[dict], filter_ids: list[str], model: str):
    total_score = 0.0
    max_score = 0.0
    results = []

    print(f"\n{'='*72}")
    print(f"  BIM-Leitfaden Q&A Evaluation   model={model}   questions={len(questions)}")
    print(f"{'='*72}\n")

    for q in questions:
        qid = q.get("id", "?")
        if filter_ids and qid not in filter_ids:
            continue

        question_text = q.get("question", "")
        expected_raw  = q.get("expected_answer", "")
        entities      = q.get("expected_entities", [])
        source_page   = q.get("source", {}).get("page", "?")

        print(f"[{qid}] {question_text}")
        print(f"      Expected source: p.{source_page}")

        t0 = time.time()
        resp = ask(question_text, model)
        elapsed = time.time() - t0

        answer  = resp.get("answer", "")
        ampel   = resp.get("ampel", "?")
        method  = resp.get("method", "?")
        sources = resp.get("sources", [])

        expected_str = flatten_expected(expected_raw)
        color, score, found, missing = score_answer(answer, expected_str, entities)

        total_score += score
        max_score   += 2.0

        # Print answer (truncated)
        answer_preview = textwrap.fill(answer[:280] + ("…" if len(answer) > 280 else ""),
                                       width=68, initial_indent="      ", subsequent_indent="      ")
        print(answer_preview)

        # Score line
        entity_line = (f"  entities found: {', '.join(found[:4])}" if found else "  entities found: none")
        miss_line   = (f"  missing: {', '.join(missing[:4])}" if missing else "")
        print(fmt_color(f"      [{color}] score={score:.0f}/2  {entity_line}  {miss_line}", color))
        print(f"      ampel={ampel}  method={method}  sources={len(sources)}  {elapsed:.1f}s\n")

        results.append({
            "id": qid, "color": color, "score": score,
            "elapsed": round(elapsed, 1),
            "found_entities": found,
            "missing_entities": missing,
            "answer_preview": answer[:200],
        })

    # Summary
    pct = (total_score / max_score * 100) if max_score else 0
    green  = sum(1 for r in results if r["color"] == "GREEN")
    yellow = sum(1 for r in results if r["color"] == "YELLOW")
    red    = sum(1 for r in results if r["color"] == "RED")

    print(f"{'='*72}")
    print(f"  RESULTS  {len(results)} questions")
    print(fmt_color(f"  GREEN  (full match):    {green}", "GREEN"))
    print(fmt_color(f"  YELLOW (partial match): {yellow}", "YELLOW"))
    print(fmt_color(f"  RED    (miss/no answer): {red}", "RED"))
    print(f"  TOTAL SCORE: {total_score:.0f} / {max_score:.0f}  ({pct:.0f}%)")
    print(f"{'='*72}\n")

    # Worst performers
    worst = sorted(results, key=lambda r: r["score"])[:5]
    print("  Needs improvement:")
    for r in worst:
        missing_str = ", ".join(r["missing_entities"][:3])
        print(fmt_color(f"  [{r['id']}] {r['color']} — missing: {missing_str}", r["color"]))

    # Save JSON
    out = {
        "model": model, "pdf": PDF_PATH,
        "score_pct": round(pct, 1),
        "green": green, "yellow": yellow, "red": red,
        "questions": results,
    }
    out_path = "/Users/mango/BlackSwanX/scripts/eval_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  Full results saved to: {out_path}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--questions", default="", help="Comma-separated IDs, e.g. Q01,Q02")
    args = parser.parse_args()

    filter_ids = [x.strip() for x in args.questions.split(",") if x.strip()]
    questions  = load_questions(YAML_FILE)

    if not questions:
        print("ERROR: No questions loaded from YAML.")
        sys.exit(1)

    print(f"Loaded {len(questions)} questions from YAML.")
    run_eval(questions, filter_ids, args.model)


if __name__ == "__main__":
    main()
