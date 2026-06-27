"""
construction_panel.py — Expert Panel for German Construction Document Q&A.

6 domain experts debate an LLM answer about VOB/B / HOAI / BIM documents.
Each expert now produces structured output with visible reasoning chain,
confidence score, memory references, and evidence quotes.

Memory-aware: institutional knowledge from resonance.db is injected into
every expert's context so they reason against cross-project patterns,
not just the current document snippet.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

import httpx

OLLAMA_URL   = "http://localhost:11434/api/generate"
# Default models — overridden at call time via convene_panel(model=...)
PANEL_MODEL  = "llama3.2:3b"      # 5 expert workers — fast parallel reasoning
JUDGE_MODEL  = "mistral-small:24b"  # moderator synthesis — 32k context

_TIMEOUT = 180   # larger models need more time


def _call(model: str, prompt: str, temperature: float = 0.3,
          num_predict: int = 500) -> str:
    try:
        r = httpx.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": temperature, "num_predict": num_predict}},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[nicht verfügbar: {e}]"


def _judge_call(prompt: str, model: str) -> str:
    result = _call(model, prompt, temperature=0.1, num_predict=600)
    if result.startswith("[nicht verfügbar"):
        result = _call("llama3.2:3b", prompt, temperature=0.1, num_predict=400)
    return result


# ── Expert definitions ────────────────────────────────────────────────────────

_EXPERTS = [
    {
        "id": "bauleiter",
        "name": "Bauleiter",
        "icon": "🏗",
        "temp": 0.4,
        "focus": "Fristen, Abnahme, Mängelrüge, Ausführungsrisiken, Baustellenalltag",
        "system": (
            "Du bist ein erfahrener Bauleiter mit 25 Jahren Erfahrung auf deutschen Großbaustellen. "
            "Du kennst jeden §-Trick in VOB/B und weißt, was in der Praxis wirklich passiert vs. was Juristen schreiben. "
            "Du bist direkt, skeptisch und praxisnah."
        ),
    },
    {
        "id": "jurist",
        "name": "Baurechts-Jurist",
        "icon": "⚖️",
        "temp": 0.1,
        "focus": "§-Korrektheit, Verjährungsfristen, Haftungsgrenzen, Formvorschriften",
        "system": (
            "Du bist ein Fachanwalt für Baurecht mit Schwerpunkt VOB/B, BGB Werkvertragsrecht und HOAI. "
            "Du prüfst jeden Rechtsbezug auf §-Korrektheit und formelle Anforderungen. "
            "Du zitierst konkrete Paragraphen und Urteile."
        ),
    },
    {
        "id": "bim_koordinator",
        "name": "BIM-Koordinator",
        "icon": "📐",
        "temp": 0.2,
        "focus": "AIA, BAP, IFC, ISO 19650, Koordinationsmodelle, CDE-Prozesse",
        "system": (
            "Du bist ein zertifizierter BIM-Manager nach VDI 2552. "
            "Du kennst BIM-Abwicklungsplan (BAP), Auftraggeber-Informations-Anforderungen (AIA), "
            "IFC-Standards und digitale Lieferformate nach ISO 19650."
        ),
    },
    {
        "id": "auftraggeber",
        "name": "Auftraggeber-Vertreter",
        "icon": "🏢",
        "temp": 0.3,
        "focus": "Kosten, Termine, Abnahmerisiken, Vertragsstrafen, Gewährleistungsansprüche",
        "system": (
            "Du vertrittst die Interessen des Auftraggebers (Bauherr/öffentlicher Auftraggeber). "
            "Du fragst: Was kostet uns das? Was können wir durchsetzen? Wo sind wir exponiert? "
            "Du bist kritisch gegenüber Auftragnehmerpositionen."
        ),
    },
    {
        "id": "kalkulator",
        "name": "Kalkulator / Nachtragsmanager",
        "icon": "🔢",
        "temp": 0.2,
        "focus": "Einheitspreise, Nachtragskalkulation §2 VOB/B, Skonti, Kostenfallen",
        "system": (
            "Du bist Kalkulator und Nachtragsmanager für einen deutschen Baukonzern. "
            "Du kennst Einheitspreise, Nachtragskalkulationen nach §2 Abs.5/6 VOB/B und "
            "die versteckten Kostenfallen in Pauschalverträgen."
        ),
    },
]

_MODERATOR_SYSTEM = """Du bist ein neutraler Moderator und Schiedsrichter für Baurecht-Compliance.
Du hast die strukturierten Analysen von 5 Bauexperten gelesen.
Deine Aufgabe: Synthese, Widersprüche aufdecken, Abschlussurteil.

Antworte GENAU in diesem JSON-Format (kein anderer Text außerhalb):
{
  "verdict": "BESTAETIGT" | "FEHLERHAFT" | "ERGAENZT" | "UNSICHER",
  "confidence": 0.0-1.0,
  "key_finding": "Der wichtigste Befund in einem Satz",
  "reasoning": "Wie du zum Urteil kamst — welche Expertenargumente ausschlaggebend waren",
  "corrections": ["Korrektur 1", "Korrektur 2"],
  "confirmed_points": ["Bestätigter Punkt 1"],
  "conflicts": ["Widerspruch zwischen Experten X und Y über Thema Z"],
  "memory_impact": "Wie das institutionelle Gedächtnis das Urteil beeinflusst hat (oder nicht)",
  "ampel": "green" | "yellow" | "red"
}"""


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class ExpertOpinion:
    expert_id: str
    expert_name: str
    icon: str
    opinion: str
    reasoning_chain: list[str]   # step-by-step reasoning the expert showed
    confidence: float
    evidence_quotes: list[str]   # direct quotes from context/memory
    memory_refs: list[str]       # which memory entries influenced this opinion
    flags: list[str]             # issues flagged (missing §, wrong date, etc.)

@dataclass
class PanelVerdict:
    ampel: Literal["green", "yellow", "red"]
    confidence: float
    verdict: str
    key_finding: str
    reasoning: str
    corrections: list[str]
    confirmed_points: list[str]
    conflicts: list[str]
    memory_impact: str
    expert_opinions: dict[str, ExpertOpinion]


# ── Expert runner ─────────────────────────────────────────────────────────────

def _run_expert(expert: dict, question: str, draft_answer: str,
                context_snippet: str, memory_block: str,
                model: str) -> tuple[str, ExpertOpinion]:

    prompt = f"""{expert['system']}

INSTITUTIONELLES GEDÄCHTNIS (aus früheren Projekten — höchste Verlässlichkeit):
{memory_block or '(keine relevanten Einträge)'}

KONTEXT AUS DEN BAUDOKUMENTEN:
{context_snippet}

FRAGE: {question}

KI-ENTWURF DER ANTWORT:
{draft_answer}

Deine Aufgabe als {expert['name']} (Fokus: {expert['focus']}):
Antworte GENAU in diesem JSON-Format (kein anderer Text):
{{
  "opinion": "Deine Gesamteinschätzung in 2-3 Sätzen auf Deutsch",
  "reasoning_chain": [
    "Schritt 1: Was ich zuerst geprüft habe und warum",
    "Schritt 2: Was der Kontext/das Gedächtnis dazu sagt",
    "Schritt 3: Meine Schlussfolgerung"
  ],
  "confidence": 0.0-1.0,
  "evidence_quotes": ["Direktes Zitat aus Kontext oder Gedächtnis das meine Meinung stützt"],
  "memory_refs": ["Welche Gedächtnis-Einträge relevant waren (oder 'keine')"],
  "flags": ["Problem 1 das ich gefunden habe", "Problem 2"]
}}"""

    raw = _call(model, prompt, temperature=expert["temp"], num_predict=700)

    # Parse structured output
    try:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return expert["id"], ExpertOpinion(
                expert_id=expert["id"],
                expert_name=expert["name"],
                icon=expert["icon"],
                opinion=data.get("opinion", raw[:300]),
                reasoning_chain=data.get("reasoning_chain", []),
                confidence=float(data.get("confidence", 0.5)),
                evidence_quotes=data.get("evidence_quotes", []),
                memory_refs=data.get("memory_refs", []),
                flags=data.get("flags", []),
            )
    except Exception:
        pass

    # Fallback: wrap plain text
    return expert["id"], ExpertOpinion(
        expert_id=expert["id"],
        expert_name=expert["name"],
        icon=expert["icon"],
        opinion=raw[:400],
        reasoning_chain=["(Strukturiertes Format nicht verfügbar — Rohtext oben)"],
        confidence=0.5,
        evidence_quotes=[],
        memory_refs=[],
        flags=[],
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def convene_panel(question: str, draft_answer: str, context: str,
                  model: str = PANEL_MODEL,
                  institutional_memories: list[dict] | None = None,
                  agentic_instructions: dict[str, list[str]] | None = None) -> PanelVerdict:
    """
    Run 5 experts in parallel (ThreadPoolExecutor), then Moderator synthesizes.
    Each expert receives:
      - Institutional memory block (cross-project knowledge)
      - Full context (up to 4000 chars instead of 2000)
      - Structured reasoning format — shows HOW they reached their opinion
    """
    context_snippet = context[:4000]

    # Build memory block for experts
    memory_block = ""
    if institutional_memories:
        lines = []
        for m in institutional_memories:
            truth = m.get("display_truth") or m.get("fact", "")
            lines.append(
                f"• {m['entity']} [{m['entity_type']}] "
                f"(Stärke: {m.get('memory_strength',0):.0%}, "
                f"{m.get('repetition_count',1)}× gesehen): {truth}"
            )
        memory_block = "\n".join(lines)

    # Build per-role agentic block for experts
    _ai = agentic_instructions or {}
    _expert_agentic = ""
    if _ai.get("expert"):
        _expert_agentic = (
            "\n\nAGENTISCHE ANWEISUNGEN (aus permanentem institutionellem Gedächtnis):\n"
            + "\n".join(f"→ {i}" for i in _ai["expert"])
        )
    _augmented_context = context_snippet + _expert_agentic

    # Run all 5 experts in parallel
    expert_opinions: dict[str, ExpertOpinion] = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(
                _run_expert, expert, question, draft_answer,
                _augmented_context, memory_block, model
            ): expert["id"]
            for expert in _EXPERTS
        }
        for future in as_completed(futures):
            try:
                eid, opinion = future.result(timeout=_TIMEOUT)
                expert_opinions[eid] = opinion
            except Exception as e:
                eid = futures[future]
                expert_opinions[eid] = ExpertOpinion(
                    expert_id=eid, expert_name=eid, icon="❓",
                    opinion=f"[Fehler: {e}]",
                    reasoning_chain=[], confidence=0.0,
                    evidence_quotes=[], memory_refs=[], flags=[]
                )

    # Preserve display order
    ordered = {e["id"]: expert_opinions.get(e["id"]) for e in _EXPERTS}

    # Build moderator input — include reasoning chains for richer synthesis
    expert_summaries = []
    for e in _EXPERTS:
        op = ordered.get(e["id"])
        if not op:
            continue
        chain_text = " → ".join(op.reasoning_chain) if op.reasoning_chain else ""
        flags_text = "; ".join(op.flags) if op.flags else "keine Probleme"
        expert_summaries.append(
            f"{op.icon} {op.expert_name} (Konfidenz: {op.confidence:.0%}):\n"
            f"  Meinung: {op.opinion}\n"
            f"  Reasoning: {chain_text}\n"
            f"  Probleme: {flags_text}"
        )
    summaries_text = "\n\n".join(expert_summaries)

    _mod_agentic = ""
    if _ai.get("moderator"):
        _mod_agentic = "\n\nAGENTISCHE ANWEISUNGEN FÜR MODERATOR:\n" + \
                       "\n".join(f"→ {i}" for i in _ai["moderator"])

    mod_prompt = f"""{_MODERATOR_SYSTEM}

FRAGE: {question}

KI-ENTWURF:
{draft_answer}

INSTITUTIONELLES GEDÄCHTNIS:
{memory_block or '(keine)'}{_mod_agentic}

STRUKTURIERTE EXPERTENANALYSEN:
{summaries_text}"""

    raw = _judge_call(mod_prompt, JUDGE_MODEL)

    try:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            ampel = data.get("ampel", "yellow")
            if ampel not in ("green", "yellow", "red"):
                ampel = "yellow"
            return PanelVerdict(
                ampel=ampel,
                confidence=float(data.get("confidence", 0.5)),
                verdict=data.get("verdict", "UNSICHER").upper(),
                key_finding=data.get("key_finding", ""),
                reasoning=data.get("reasoning", ""),
                corrections=data.get("corrections", []),
                confirmed_points=data.get("confirmed_points", []),
                conflicts=data.get("conflicts", []),
                memory_impact=data.get("memory_impact", ""),
                expert_opinions=ordered,
            )
    except Exception:
        pass

    return PanelVerdict(
        ampel="yellow", confidence=0.5, verdict="UNSICHER",
        key_finding=raw[:200], reasoning="", corrections=[],
        confirmed_points=[], conflicts=[], memory_impact="",
        expert_opinions=ordered,
    )
