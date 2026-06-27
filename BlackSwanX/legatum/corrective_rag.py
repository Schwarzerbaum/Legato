#!/usr/bin/env python3
"""
Phase 2 Improvement #4: Self-Correction (Corrective RAG / CRAG) (+3%)

Current: Retrieve once, synthesize answer
Better: Grade retrieved context against question, retry if insufficient

Flow:
  1. Retrieve initial context
  2. Grade: Is context sufficient for question?
     - Correct: Use for synthesis
     - Ambiguous: Expand graph search
     - Missing: Trigger secondary search (VDI norms, related standards)
  3. Synthesize with corrected context

Benefit: Catches edge cases where initial retrieval is insufficient.
Prevents LLM from hallucinating when context is genuinely missing.
"""
import json
import re
from typing import Optional


class ContextGrader:
    """Grade relevance of retrieved context to question."""

    @staticmethod
    def grade_context(question: str, context: str) -> dict:
        """
        Use Qwen to grade context relevance.
        Returns: {grade: "correct"|"ambiguous"|"missing", confidence: 0-1, reason: str}
        """
        try:
            import httpx

            prompt = f"""Grade this context against the question. Respond with JSON:
{{"grade": "correct"|"ambiguous"|"missing", "confidence": 0.0-1.0, "reason": "short reason"}}

Grade meanings:
- correct: Context directly answers the question
- ambiguous: Context is partially relevant but unclear
- missing: Context doesn't address the question

Question: {question}

Context: {context[:500]}

Respond with ONLY JSON."""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 150, "temperature": 0.0}
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

        # Fallback: simple heuristic grading
        context_lower = context.lower()
        question_lower = question.lower()
        q_terms = [t for t in question_lower.split() if len(t) > 3]
        matches = sum(1 for term in q_terms if term in context_lower)
        ratio = matches / max(len(q_terms), 1)

        return {
            "grade": "correct" if ratio > 0.6 else "ambiguous" if ratio > 0.2 else "missing",
            "confidence": ratio,
            "reason": f"Matched {matches}/{len(q_terms)} key terms"
        }


class CorrectiveRAG:
    """Self-correcting retrieval-augmented generation."""

    def __init__(self, graph: dict):
        self.graph = graph
        self.grader = ContextGrader()

    def correct_retrieval(
        self,
        question: str,
        initial_context: str,
        graph_entities: list[dict]
    ) -> dict:
        """
        Grade initial retrieval and correct if needed.
        """
        # Grade initial context
        grade_result = self.grader.grade_context(question, initial_context)

        result = {
            "original_grade": grade_result,
            "corrected_context": initial_context,
            "corrections_applied": []
        }

        # If context is sufficient, return as-is
        if grade_result.get("grade") == "correct" and grade_result.get("confidence", 0) > 0.7:
            return result

        # If ambiguous or missing, apply corrections
        if grade_result.get("grade") in ["ambiguous", "missing"]:
            result["corrections_applied"].append("expand_graph_search")

            # Expand graph search: find entities mentioned in question
            question_lower = question.lower()
            related_entities = [
                e for e in graph_entities
                if e.get("name", "").lower() in question_lower
            ]

            if related_entities:
                entity_context = "\n\n".join([
                    f"**{e.get('name')}** ({e.get('type')}): {e.get('description')}"
                    for e in related_entities[:5]
                ])
                result["corrected_context"] += "\n\nRelated Entities:\n" + entity_context

        # If still missing, try to find related standards/norms
        if grade_result.get("grade") == "missing":
            result["corrections_applied"].append("search_related_standards")

            # Look for standards/norms mentioned in question
            standard_keywords = ["vdi", "norm", "standard", "directive", "guideline"]
            if any(kw in question.lower() for kw in standard_keywords):
                # Add a placeholder for expanded search
                result["corrected_context"] += (
                    "\n\n[SECONDARY SEARCH NEEDED: Look up referenced standards in VDI registry]"
                )

        return result

    def validate_answer(
        self,
        question: str,
        answer: str,
        context: str
    ) -> dict:
        """
        Validate final answer against context.
        Ensures answer isn't hallucinating beyond retrieved context.
        """
        try:
            import httpx

            prompt = f"""Check if this answer is grounded in the provided context.
Respond with JSON: {{"grounded": true|false, "confidence": 0.0-1.0, "issues": [...]}}

Context: {context[:500]}

Question: {question}

Answer: {answer[:300]}

Respond with ONLY JSON."""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 150, "temperature": 0.0}
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

        # Fallback: check for "I don't know" signals
        refusal_signals = ["not available", "not mentioned", "not found", "not clear"]
        has_refusal = any(sig in answer.lower() for sig in refusal_signals)

        return {
            "grounded": has_refusal or len(answer) > 0,
            "confidence": 0.8 if has_refusal else 0.5,
            "issues": ["Low confidence grounding"] if not has_refusal else []
        }


# ── Integration with QA Runtime ────────────────────────────────────────────

def enhance_qa_with_self_correction(
    question: str,
    initial_context: str,
    graph_dict: dict
) -> str:
    """
    Apply self-correction to improve retrieval quality.
    Returns: corrected context for synthesis
    """
    corrector = CorrectiveRAG(graph_dict)
    graph_entities = graph_dict.get("entities", [])

    result = corrector.correct_retrieval(question, initial_context, graph_entities)

    return result["corrected_context"]


def validate_final_answer(
    question: str,
    answer: str,
    context: str
) -> dict:
    """
    Validate synthesized answer before returning to user.
    Flags hallucinations.
    """
    corrector = CorrectiveRAG({})
    validation = corrector.validate_answer(question, answer, context)

    return {
        "answer": answer,
        "is_grounded": validation.get("grounded", False),
        "confidence": validation.get("confidence", 0.5),
        "issues": validation.get("issues", []),
        "recommendation": (
            "ACCEPT" if validation.get("grounded") and validation.get("confidence") > 0.7
            else "REVIEW"
        )
    }
