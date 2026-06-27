"""
Construction Jury — 3-agent adversarial debate for Q&A answer verification.

Assassin (skeptical Bauleiter) and Defender (Baurechts-Jurist) run in parallel,
both memory-aware. Judge synthesizes with explicit reasoning chain.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal

import httpx

OLLAMA_URL      = "http://localhost:11434/api/generate"
ASSASSIN_MODEL  = "llama3.2:3b"
DEFENDER_MODEL  = "llama3.2:3b"
JUDGE_MODEL     = "mistral-small:24b"

_TIMEOUT = 180


def _call(model: str, prompt: str, temperature: float,
          num_predict: int = 500, timeout: int = _TIMEOUT) -> str:
    try:
        r = httpx.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": temperature, "num_predict": num_predict}},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[unavailable: {e}]"


def _judge_call(model: str, prompt: str) -> str:
    result = _call(model, prompt, temperature=0.1, num_predict=600)
    if result.startswith("[unavailable"):
        result = _call("llama3.2:3b", prompt, temperature=0.1, num_predict=400)
    return result


@dataclass
class JuryVerdict:
    ampel: Literal["green", "yellow", "red"]
    confidence: float
    assassin: str
    assassin_reasoning: list[str]
    assassin_flags: list[str]
    defender: str
    defender_reasoning: list[str]
    defender_evidence: list[str]
    judge: str
    judge_reasoning: str
    memory_impact: str
    confirmed: bool


def run_assassin(question: str, answer: str, context: str,
                 memory_block: str, model: str) -> dict:
    prompt = f"""Du bist ein extrem skeptischer, erfahrener Bauleiter mit 30 Jahren Erfahrung.
Ein KI-System hat die folgende Antwort auf eine Frage gegeben. Deine Aufgabe: finde JEDEN Fehler.

INSTITUTIONELLES GEDÄCHTNIS (höchste Verlässlichkeit — nutze es zur Überprüfung):
{memory_block or '(keine)'}

KONTEXT AUS DEN DOKUMENTEN:
{context[:4000]}

FRAGE: {question}

KI-ANTWORT:
{answer}

Antworte GENAU in diesem JSON-Format:
{{
  "critique": "Deine Hauptkritik in 2-3 Sätzen auf Deutsch",
  "reasoning_chain": [
    "Schritt 1: Was ich zuerst geprüft habe",
    "Schritt 2: Wo ich Abweichungen vom Kontext/Gedächtnis gefunden habe",
    "Schritt 3: Mein Urteil"
  ],
  "flags": ["Konkreter Fehler 1 (mit Seitenangabe wenn möglich)", "Fehler 2"],
  "memory_conflicts": ["Widerspruch zur Gedächtnis-Einheit X (oder 'keine')"],
  "severity": "LOW" | "MEDIUM" | "HIGH"
}}"""

    raw = _call(model, prompt, temperature=0.6, num_predict=600)
    try:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"critique": raw[:300], "reasoning_chain": [], "flags": [], "memory_conflicts": [], "severity": "MEDIUM"}


def run_defender(question: str, answer: str, context: str,
                 assassin_data: dict, memory_block: str, model: str) -> dict:
    flags_text = "\n".join(f"- {f}" for f in assassin_data.get("flags", []))
    prompt = f"""Du bist ein erfahrener Baurechts-Jurist. Ein skeptischer Bauleiter hat diese Kritik geäußert.
Deine Aufgabe: Verteidige die Antwort mit Textstellen aus Kontext und Gedächtnis. Räume echte Fehler ein.

INSTITUTIONELLES GEDÄCHTNIS (höchste Verlässlichkeit):
{memory_block or '(keine)'}

KONTEXT AUS DEN DOKUMENTEN:
{context[:4000]}

FRAGE: {question}

KI-ANTWORT:
{answer}

KRITIK DES BAULEITERS (Schweregrad: {assassin_data.get('severity','?')}):
{assassin_data.get('critique','')}
Konkrete Mängel:
{flags_text or '(keine spezifischen Mängel genannt)'}

Antworte GENAU in diesem JSON-Format:
{{
  "defense": "Deine Verteidigung in 2-3 Sätzen auf Deutsch",
  "reasoning_chain": [
    "Schritt 1: Welche Kritikpunkte ich geprüft habe",
    "Schritt 2: Was der Kontext/das Gedächtnis dazu belegt",
    "Schritt 3: Was ich einräume vs. zurückweise"
  ],
  "evidence_quotes": ["Direktes Zitat aus Kontext das die Antwort stützt"],
  "conceded_errors": ["Eingeräumter Fehler 1 (oder 'keine')"],
  "rebutted_points": ["Zurückgewiesene Kritik 1"]
}}"""

    raw = _call(model, prompt, temperature=0.15, num_predict=700)
    try:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"defense": raw[:300], "reasoning_chain": [], "evidence_quotes": [], "conceded_errors": [], "rebutted_points": []}


def run_judge(question: str, answer: str,
              assassin_data: dict, defender_data: dict,
              memory_block: str, model: str) -> tuple[str, str, float, str, str]:
    """Returns (verdict_text, ampel, confidence, reasoning, memory_impact)."""
    prompt = f"""Du bist ein neutraler Schiedsrichter für Baurecht-Compliance.
Ein Bauleiter hat eine KI-Antwort angegriffen, ein Jurist hat sie verteidigt.
Nutze auch das institutionelle Gedächtnis für dein Urteil.

GEDÄCHTNIS:
{memory_block or '(keine)'}

FRAGE: {question}

ANGRIFF (Bauleiter — Schweregrad {assassin_data.get('severity','?')}):
{assassin_data.get('critique','')}
Flags: {'; '.join(assassin_data.get('flags',[]))}

VERTEIDIGUNG (Jurist):
{defender_data.get('defense','')}
Eingeräumte Fehler: {'; '.join(defender_data.get('conceded_errors',[]))}
Zurückgewiesen: {'; '.join(defender_data.get('rebutted_points',[]))}

Antworte GENAU in diesem JSON-Format:
{{
  "verdict": "BESTAETIGT" | "FEHLERHAFT" | "UNSICHER",
  "confidence": 0.0-1.0,
  "reason": "Abschlussurteil in einem Satz auf Deutsch",
  "reasoning": "Wie du zu diesem Urteil gekommen bist — welche Argumente ausschlaggebend waren",
  "memory_impact": "Wie das Gedächtnis dein Urteil beeinflusst hat (oder nicht)",
  "ampel": "green" | "yellow" | "red"
}}"""

    raw = _judge_call(model, prompt)
    try:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            v = data.get("verdict", "UNSICHER").upper()
            ampel = data.get("ampel", "yellow")
            if ampel not in ("green", "yellow", "red"):
                ampel = "yellow"
            return (
                data.get("reason", raw[:200]),
                ampel,
                float(data.get("confidence", 0.5)),
                data.get("reasoning", ""),
                data.get("memory_impact", ""),
            )
    except Exception:
        pass
    return raw[:200], "yellow", 0.5, "", ""


def deliberate(question: str, answer: str, context: str,
               model: str = JUDGE_MODEL,
               institutional_memories: list[dict] | None = None,
               agentic_instructions: dict[str, list[str]] | None = None) -> JuryVerdict:
    """
    Assassin and Defender run in parallel — both memory-aware, both produce
    structured output with visible reasoning chain.
    """
    memory_block = ""
    if institutional_memories:
        lines = []
        for mem in institutional_memories:
            truth = mem.get("display_truth") or mem.get("fact", "")
            lines.append(
                f"• {mem['entity']} [{mem['entity_type']}] "
                f"(Stärke: {mem.get('memory_strength',0):.0%}): {truth}"
            )
        memory_block = "\n".join(lines)

    # Build per-role agentic instruction blocks
    _ai = agentic_instructions or {}

    def _agentic_block(role: str) -> str:
        instrs = _ai.get(role, [])
        if not instrs:
            return ""
        return "\n\nAGENTISCHE ANWEISUNGEN (gelernt aus früheren Dokumenten — befolge diese):\n" + \
               "\n".join(f"→ {i}" for i in instrs)

    # Patch the model assignments per role
    _assassin_model = ASSASSIN_MODEL
    _defender_model = DEFENDER_MODEL

    # Inject agentic instructions by monkey-patching prompts at call time
    def _run_assassin_agentic():
        prompt_suffix = _agentic_block("assassin")
        # Temporarily augment context with agentic instructions
        augmented_context = context + prompt_suffix
        return run_assassin(question, answer, augmented_context, memory_block, _assassin_model)

    def _run_defender_standalone_agentic():
        augmented_context = context + _agentic_block("defender")
        return run_defender(question, answer, augmented_context, {}, memory_block, _defender_model)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_assassin = pool.submit(_run_assassin_agentic)
        f_defender_standalone = pool.submit(_run_defender_standalone_agentic)
        assassin_data = f_assassin.result()
        # Run full defender with assassin output after parallel warmup
        defender_context = context + _agentic_block("defender")
        defender_data = run_defender(question, answer, defender_context, assassin_data, memory_block, _defender_model)
        _ = f_defender_standalone.result()  # discard warmup result

    judge_memory = memory_block
    if _ai.get("judge"):
        judge_memory += "\n\nAGENTISCHE ANWEISUNGEN FÜR SCHIEDSRICHTER:\n" + \
                        "\n".join(f"→ {i}" for i in _ai["judge"])
    verdict_text, ampel, confidence, reasoning, memory_impact = run_judge(
        question, answer, assassin_data, defender_data, judge_memory, JUDGE_MODEL
    )

    return JuryVerdict(
        ampel=ampel,
        confidence=confidence,
        assassin=assassin_data.get("critique", ""),
        assassin_reasoning=assassin_data.get("reasoning_chain", []),
        assassin_flags=assassin_data.get("flags", []),
        defender=defender_data.get("defense", ""),
        defender_reasoning=defender_data.get("reasoning_chain", []),
        defender_evidence=defender_data.get("evidence_quotes", []),
        judge=verdict_text,
        judge_reasoning=reasoning,
        memory_impact=memory_impact,
        confirmed=ampel == "green",
    )
