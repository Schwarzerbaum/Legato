"""
Automated Nachtragsprüfung Engine
===================================
Pre-litigation risk assessment for German construction change order disputes.

Replaces generic two-agent debate (Predator/Prey) with a VOB/B-grounded
claim/defense simulation that outputs a structured Financial Risk Exposure Score.

Agents:
    Agent A (Auftragnehmer / AN): Maximizes claim value
        - Finds ambiguities in original Bausoll
        - Cites VOB/B §2 Abs. 5, §2 Abs. 6, §4 for change order rights
        - Identifies changed conditions (Baugrundrisiko, Zusätzliche Leistungen)

    Agent B (Auftraggeber / AG): Weaponizes documentation gaps
        - Checks Bedenkenanzeige submission timeline
        - Validates written Anordnung requirement
        - Challenges Pauschalvertrag scope inclusion
        - Verifies VOB/B procedural compliance

Output: NachtragVerdict with Financial Risk Exposure Score (0-100)
        and estimated settlement range in EUR.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

try:
    import httpx
    _OLLAMA_BASE = "http://localhost:11434"
    _MODEL = "llama3.2:3b"

    def _llm(system: str, user: str, model: str = _MODEL) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 500},
        }
        try:
            r = httpx.post(f"{_OLLAMA_BASE}/api/chat", json=payload, timeout=60)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception as e:
            return f"[LLM_ERROR: {e}]"
except ImportError:
    def _llm(system: str, user: str, model: str = "") -> str:  # type: ignore
        return "[LLM_UNAVAILABLE]"


# ── VOB/B procedural rules (deterministic, no LLM) ───────────────────────────

VOB_PROCEDURAL_RULES = [
    {
        "rule_id": "bedenkenanzeige_timing",
        "name": "Bedenkenanzeige — 14-day notice requirement",
        "check": lambda text: bool(re.search(
            r'bedenkenanzeige|bedenken.{0,20}angezeigt|concerns?.{0,20}notif',
            text, re.IGNORECASE
        )),
        "ag_argument": "Auftragnehmer hat keine rechtzeitige Bedenkenanzeige "
                       "gem. VOB/B §4 Abs. 3 eingereicht. Anspruch verwirkt.",
        "vob_ref": "VOB/B §4 Abs. 3",
    },
    {
        "rule_id": "schriftliche_anordnung",
        "name": "Written order requirement (§2 Abs. 5)",
        "check": lambda text: bool(re.search(
            r'schriftlich.{0,20}angeordnet|written.{0,20}order|anordnung',
            text, re.IGNORECASE
        )),
        "an_argument": "Leistungsänderung wurde schriftlich angeordnet gem. "
                       "VOB/B §2 Abs. 5. Nachtragsvergütung ist geschuldet.",
        "ag_argument": "Keine schriftliche Anordnung nachweisbar. "
                       "§2 Abs. 5 VOB/B Voraussetzungen nicht erfüllt.",
        "vob_ref": "VOB/B §2 Abs. 5",
    },
    {
        "rule_id": "ankuendigung_mehrvergütung",
        "name": "Prior notice of additional cost required",
        "check": lambda text: bool(re.search(
            r'ankündigung|preisankündigung|vor.{0,10}ausführung.{0,20}preis',
            text, re.IGNORECASE
        )),
        "ag_argument": "Ankündigung der Mehrvergütung vor Ausführung fehlt. "
                       "Gem. VOB/B §2 Abs. 5 S. 2 ist der Anspruch ausgeschlossen.",
        "vob_ref": "VOB/B §2 Abs. 5 S. 2",
    },
    {
        "rule_id": "pauschalvertrag_scope",
        "name": "Pauschalvertrag scope inclusion check",
        "check": lambda text: bool(re.search(
            r'pauschal|lump.?sum|festpreis',
            text, re.IGNORECASE
        )),
        "ag_argument": "Pauschalvertrag gem. §2 Abs. 7 VOB/B. Leistung ist "
                       "im Pauschalpreis enthalten. Kein Nachtrag begründet.",
        "an_argument": "Leistung geht über den Pauschalumfang hinaus — "
                       "außervertragliche Zusatzleistung gem. §2 Abs. 6 VOB/B.",
        "vob_ref": "VOB/B §2 Abs. 7",
    },
    {
        "rule_id": "baugrundrisiko",
        "name": "Unforeseeable ground conditions (§4 Abs. 1)",
        "check": lambda text: bool(re.search(
            r'baugrund|ground.?condition|boden.{0,15}verhältnis|unvorhergesehen',
            text, re.IGNORECASE
        )),
        "an_argument": "Unvorhersehbare Baugrundverhältnisse gem. VOB/B §4 Abs. 1. "
                       "Risiko trägt der Auftraggeber. Nachtrag berechtigt.",
        "vob_ref": "VOB/B §4 Abs. 1",
    },
    {
        "rule_id": "aufmass_erforderlich",
        "name": "Aufmaß (measurement record) required for billing",
        "check": lambda text: bool(re.search(
            r'aufmaß|aufmass|mengenermittlung|measurement.{0,15}record',
            text, re.IGNORECASE
        )),
        "ag_argument": "Kein gemeinsames Aufmaß gem. VOB/B §14 Abs. 2 erstellt. "
                       "Abrechnung nicht prüfbar.",
        "vob_ref": "VOB/B §14 Abs. 2",
    },
]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class NachtragInput:
    """Input for a Nachtragsprüfung."""
    nachtrag_id: str
    claim_value_eur: float
    nachtrag_text: str              # Text of the change order
    original_lv_text: str = ""     # Relevant LV sections
    correspondence_text: str = ""  # Emails, letters, meeting minutes
    contract_type: Literal["VOB/B", "BGB", "UNKNOWN"] = "VOB/B"
    is_pauschalvertrag: bool = False


@dataclass
class AgentPosition:
    """Position of one agent (AN or AG)."""
    agent: Literal["AN", "AG"]
    arguments: list[str] = field(default_factory=list)
    vob_citations: list[str] = field(default_factory=list)
    documentation_strength: float = 0.0   # 0-1: how well-documented is this side
    position_strength: float = 0.0        # 0-1: legal strength of position


@dataclass
class NachtragVerdict:
    """Full verdict from Nachtragsprüfung simulation."""
    nachtrag_id: str
    claim_value_eur: float

    # Agent positions
    an_position: AgentPosition = field(default_factory=lambda: AgentPosition("AN"))
    ag_position: AgentPosition = field(default_factory=lambda: AgentPosition("AG"))

    # Financial risk exposure
    risk_score: float = 0.0              # 0-100
    estimated_min_eur: float = 0.0
    estimated_max_eur: float = 0.0
    likely_outcome_pct: float = 0.0      # % of claim value likely to be awarded

    # Decision factors
    decisive_factor: str = ""
    documentation_gaps: list[str] = field(default_factory=list)
    procedural_violations: list[str] = field(default_factory=list)

    # Recommendation
    recommendation: Literal[
        "APPROVE_FULL",
        "APPROVE_PARTIAL",
        "NEGOTIATE",
        "REJECT",
        "ESCALATE_LAWYER"
    ] = "NEGOTIATE"
    recommendation_reasoning: str = ""

    # Meta
    contract_type: str = "VOB/B"
    duration_ms: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Agent system prompts ──────────────────────────────────────────────────────

_AN_SYSTEM = """Du bist der Anwalt des Auftragnehmers (AN) in einer deutschen Nachtragsprüfung.
Du kennst VOB/B, HOAI und BGB auswendig. Dein Ziel: den maximalen berechtigten Nachtragswert durchsetzen.

Suche nach:
1. Leistungsänderungen gem. VOB/B §2 Abs. 5 (schriftliche Anordnung des AG)
2. Zusätzliche Leistungen gem. VOB/B §2 Abs. 6 (nicht im LV enthalten)
3. Geänderte Baugrundverhältnisse gem. VOB/B §4 Abs. 1
4. Behinderungen gem. VOB/B §6 (Bauzeitverlängerung + Mehrkosten)
5. Unklarheiten im Leistungsverzeichnis zugunsten des AN (§305c BGB)
6. Preisanpassungsrecht bei Mengenabweichungen >10% (VOB/B §2 Abs. 3)

Antworte NUR im folgenden JSON-Format:
{
  "flagged": true/false,
  "legal_basis": ["VOB/B §2 Abs. 5", ...],
  "arguments": ["Argument 1", "Argument 2"],
  "documentation_strength": 0.0-1.0,
  "position_strength": 0.0-1.0,
  "key_evidence": "wichtigste Beweisstelle (max 150 Zeichen)"
}"""

_AG_SYSTEM = """Du bist der Anwalt des Auftraggebers (AG) / Architekten in einer deutschen Nachtragsprüfung.
Du kennst VOB/B, HOAI und BGB auswendig. Dein Ziel: unberechtigte Nachträge abzuwehren und Dokumentationslücken auszunutzen.

Prüfe folgende Abwehrmöglichkeiten:
1. Fehlende schriftliche Anordnung (VOB/B §2 Abs. 5 — keine mündliche Anordnung ausreichend)
2. Keine Ankündigung der Mehrvergütung vor Ausführung (VOB/B §2 Abs. 5 S. 2)
3. Leistung im Pauschalpreis enthalten (VOB/B §2 Abs. 7)
4. Verspätete Bedenkenanzeige (VOB/B §4 Abs. 3 — muss unverzüglich erfolgen)
5. Kein gemeinsames Aufmaß (VOB/B §14 Abs. 2)
6. Nachtrag nach Abnahme geltend gemacht (§640 BGB Ausschlusswirkung)
7. Fehlende Urkalkulation als Preisgrundlage

Antworte NUR im folgenden JSON-Format:
{
  "flagged": true/false,
  "legal_basis": ["VOB/B §2 Abs. 5 S. 2", ...],
  "arguments": ["Abwehrargument 1", "Abwehrargument 2"],
  "documentation_gaps": ["Lücke 1", "Lücke 2"],
  "documentation_strength": 0.0-1.0,
  "position_strength": 0.0-1.0,
  "key_weakness": "schwächste Stelle des Nachtrags (max 150 Zeichen)"
}"""


# ── Deterministic pre-screening (no LLM) ─────────────────────────────────────

def _run_procedural_checks(nachtrag: NachtragInput) -> dict:
    """
    Run all VOB/B procedural rules deterministically before LLM.
    Fast, zero token cost, catches obvious patterns.
    """
    full_text = (
        nachtrag.nachtrag_text + " " +
        nachtrag.original_lv_text + " " +
        nachtrag.correspondence_text
    )

    an_points: list[str] = []
    ag_points: list[str] = []
    vob_refs: list[str] = []

    for rule in VOB_PROCEDURAL_RULES:
        triggered = rule["check"](full_text)
        vob_refs.append(rule["vob_ref"])

        if triggered:
            if "an_argument" in rule:
                an_points.append(rule["an_argument"])
            if "ag_argument" in rule:
                ag_points.append(rule["ag_argument"])
        else:
            # Rule NOT triggered = absence = potential issue for AN
            if "ag_argument" in rule and rule["rule_id"] in (
                "schriftliche_anordnung", "bedenkenanzeige_timing", "aufmass_erforderlich"
            ):
                ag_points.append(rule["ag_argument"])

    return {
        "an_procedural_points": an_points,
        "ag_procedural_points": ag_points,
        "vob_refs_triggered": list(set(vob_refs)),
    }


def _parse_agent_response(raw: str, agent: Literal["AN", "AG"]) -> dict:
    """Parse JSON from agent LLM response. Fallback to empty on failure."""
    try:
        # Extract JSON block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "flagged": False,
        "legal_basis": [],
        "arguments": [],
        "documentation_strength": 0.5,
        "position_strength": 0.5,
    }


# ── Main Nachtragsprüfung engine ──────────────────────────────────────────────

def prüfe_nachtrag(nachtrag: NachtragInput) -> NachtragVerdict:
    """
    Run full Nachtragsprüfung simulation for a change order.

    1. Deterministic procedural pre-screen (VOB/B rules, no LLM)
    2. AN agent: finds legal basis for claim
    3. AG agent: finds procedural gaps and defenses
    4. Verdict: calculates Financial Risk Exposure Score + settlement range

    Returns NachtragVerdict with full analysis.
    """
    start = time.time()
    verdict = NachtragVerdict(
        nachtrag_id=nachtrag.nachtrag_id,
        claim_value_eur=nachtrag.claim_value_eur,
        contract_type=nachtrag.contract_type,
    )

    # Step 1: Deterministic procedural checks
    procedural = _run_procedural_checks(nachtrag)
    verdict.procedural_violations = procedural["ag_procedural_points"]

    # Build context for LLM agents
    context = f"""
NACHTRAG ID: {nachtrag.nachtrag_id}
FORDERUNGSBETRAG: EUR {nachtrag.claim_value_eur:,.2f}
VERTRAGSART: {nachtrag.contract_type} {'(Pauschalvertrag)' if nachtrag.is_pauschalvertrag else ''}

NACHTRAG TEXT:
{nachtrag.nachtrag_text[:2000]}

RELEVANTE LV-POSITIONEN:
{nachtrag.original_lv_text[:1000] if nachtrag.original_lv_text else '(nicht vorhanden)'}

SCHRIFTVERKEHR / PROTOKOLLE:
{nachtrag.correspondence_text[:1000] if nachtrag.correspondence_text else '(nicht vorhanden)'}

VORLÄUFIGE VERFAHRENSRECHTLICHE FESTSTELLUNGEN:
AN-Argumente: {'; '.join(procedural['an_procedural_points'][:3]) or 'keine'}
AG-Argumente: {'; '.join(procedural['ag_procedural_points'][:3]) or 'keine'}
""".strip()

    # Step 2: AN Agent
    an_raw = _llm(_AN_SYSTEM, f"Analysiere diesen Nachtrag:\n\n{context}")
    an_data = _parse_agent_response(an_raw, "AN")

    verdict.an_position = AgentPosition(
        agent="AN",
        arguments=procedural["an_procedural_points"] + an_data.get("arguments", []),
        vob_citations=procedural["vob_refs_triggered"] + an_data.get("legal_basis", []),
        documentation_strength=an_data.get("documentation_strength", 0.5),
        position_strength=an_data.get("position_strength", 0.5),
    )

    # Step 3: AG Agent
    ag_raw = _llm(_AG_SYSTEM, f"Prüfe diesen Nachtrag auf Abwehrmöglichkeiten:\n\n{context}")
    ag_data = _parse_agent_response(ag_raw, "AG")

    verdict.ag_position = AgentPosition(
        agent="AG",
        arguments=procedural["ag_procedural_points"] + ag_data.get("arguments", []),
        vob_citations=ag_data.get("legal_basis", []),
        documentation_strength=ag_data.get("documentation_strength", 0.5),
        position_strength=ag_data.get("position_strength", 0.5),
    )

    verdict.documentation_gaps = ag_data.get("documentation_gaps", [])

    # Step 4: Financial Risk Exposure Score
    an_strength = verdict.an_position.position_strength
    ag_strength = verdict.ag_position.position_strength

    # Normalize to relative strength
    total = an_strength + ag_strength
    if total > 0:
        an_relative = an_strength / total
    else:
        an_relative = 0.5

    # Penalize for procedural violations (each = -0.1 to AN's position)
    penalty = min(0.4, len(verdict.procedural_violations) * 0.1)
    an_adjusted = max(0.0, an_relative - penalty)

    verdict.likely_outcome_pct = round(an_adjusted * 100, 1)
    verdict.estimated_min_eur = round(nachtrag.claim_value_eur * max(0, an_adjusted - 0.15), 2)
    verdict.estimated_max_eur = round(nachtrag.claim_value_eur * min(1, an_adjusted + 0.15), 2)

    # Risk score: how contested is this (both sides strong = high risk/uncertainty)
    contention = 1 - abs(an_strength - ag_strength)
    verdict.risk_score = round(contention * 100, 1)

    # Decisive factor
    if verdict.procedural_violations:
        verdict.decisive_factor = verdict.procedural_violations[0]
    elif an_data.get("key_evidence"):
        verdict.decisive_factor = an_data["key_evidence"]
    elif ag_data.get("key_weakness"):
        verdict.decisive_factor = ag_data["key_weakness"]

    # Recommendation
    if an_adjusted >= 0.75:
        verdict.recommendation = "APPROVE_FULL"
        verdict.recommendation_reasoning = (
            f"AN-Position rechtlich stark ({an_adjusted:.0%}). "
            f"Nachtrag in voller Höhe berechtigt."
        )
    elif an_adjusted >= 0.55:
        verdict.recommendation = "APPROVE_PARTIAL"
        verdict.recommendation_reasoning = (
            f"Teils berechtigter Nachtrag. "
            f"Empfehlung: EUR {verdict.estimated_min_eur:,.0f} – "
            f"EUR {verdict.estimated_max_eur:,.0f} anerkennen."
        )
    elif an_adjusted >= 0.35:
        verdict.recommendation = "NEGOTIATE"
        verdict.recommendation_reasoning = (
            f"Ausgewogene Risikolage. Verhandlungslösung empfohlen. "
            f"Erwartungswert: ca. EUR {(verdict.estimated_min_eur + verdict.estimated_max_eur)/2:,.0f}."
        )
    elif len(verdict.documentation_gaps) >= 3:
        verdict.recommendation = "REJECT"
        verdict.recommendation_reasoning = (
            f"Zu viele Dokumentationslücken ({len(verdict.documentation_gaps)}). "
            f"Nachtrag formal nicht prüfbar. Zurückweisen."
        )
    else:
        verdict.recommendation = "ESCALATE_LAWYER"
        verdict.recommendation_reasoning = (
            "Rechtlich komplexe Situation. Fachanwalt für Baurecht hinzuziehen."
        )

    verdict.duration_ms = int((time.time() - start) * 1000)
    return verdict


def verdict_to_dict(v: NachtragVerdict) -> dict:
    """Serialize NachtragVerdict to JSON-compatible dict."""
    return {
        "nachtrag_id": v.nachtrag_id,
        "claim_value_eur": v.claim_value_eur,
        "risk_score": v.risk_score,
        "likely_outcome_pct": v.likely_outcome_pct,
        "estimated_exposure": {
            "min_eur": v.estimated_min_eur,
            "max_eur": v.estimated_max_eur,
            "midpoint_eur": round((v.estimated_min_eur + v.estimated_max_eur) / 2, 2),
        },
        "decisive_factor": v.decisive_factor,
        "documentation_gaps": v.documentation_gaps,
        "procedural_violations": v.procedural_violations,
        "recommendation": v.recommendation,
        "recommendation_reasoning": v.recommendation_reasoning,
        "an_position": {
            "strength": v.an_position.position_strength,
            "arguments": v.an_position.arguments[:5],
            "vob_citations": list(set(v.an_position.vob_citations)),
        },
        "ag_position": {
            "strength": v.ag_position.position_strength,
            "arguments": v.ag_position.arguments[:5],
            "documentation_gaps": v.documentation_gaps,
        },
        "contract_type": v.contract_type,
        "duration_ms": v.duration_ms,
        "timestamp": v.timestamp,
    }
