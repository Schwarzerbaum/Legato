"""
construction_screener.py — Deterministic clause pre-screener for German construction docs.

Adapts leukocyte_rete.py's Rete engine for VOB/B, HOAI, BGB construction patterns.
Zero LLM cost — pure regex. Runs at extraction time.

Patterns:
  1.  Mängelrüge deadline (§13 VOB/B — 4 years structural, 2 years general)
  2.  Vertragsstrafe (penalty clause)
  3.  Sicherheitseinbehalt (retention money)
  4.  Abnahme trigger (formal acceptance)
  5.  Kündigungsrecht (termination right)
  6.  Haftungsbeschränkung (liability cap)
  7.  Nachtragsregelung (variation order clause)
  8.  Zahlungsfrist (payment deadline — §16 VOB/B)
  9.  Skonto / Preisnachlass (discount trap)
  10. Baugrundrisiko (ground risk allocation)
  11. Pauschalpreis (lump sum — risk of scope creep)
  12. HOAI-Honorar (fee schedule compliance)
  13. Bedenkenanmeldung (contractor objection duty)
  14. Gefahrtragung (risk of accidental loss)
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class _Rule:
    rule_id: str
    name: str
    pattern: re.Pattern
    severity: str   # CRITICAL | HIGH | MEDIUM
    clause_ref: str
    impact: str

    def matches(self, text: str) -> bool:
        return bool(self.pattern.search(text))


_CONSTRUCTION_RULES: list[_Rule] = [
    _Rule(
        rule_id="maengelruege_deadline",
        name="Mängelrüge-Frist (§13 VOB/B)",
        pattern=re.compile(
            r'Mängel(?:rüge|anzeige|haftung|bürgschaft)|Gewährleistung(?:sfrist|spflicht)|'
            r'Verjährungsfrist.*Mängel|4[\s-]*Jahre|zwei[\s-]*Jahre.*Mängel|'
            r'§\s*13\s+VOB', re.I),
        severity="CRITICAL",
        clause_ref="§13 VOB/B",
        impact="Mängelrüge-Frist läuft — Versäumnis führt zu Rechtsverlust des Auftraggebers",
    ),
    _Rule(
        rule_id="vertragsstrafe",
        name="Vertragsstrafe / Pönale",
        pattern=re.compile(
            r'Vertragsstrafe|Pönale|Verzugsstrafe|Strafklausel|'
            r'pro\s+(?:Werktag|Arbeitstag|Tag)\s+(?:\d|eine[rn]?)', re.I),
        severity="CRITICAL",
        clause_ref="§11 VOB/B",
        impact="Vertragsstrafe vereinbart — Höhe und Obergrenze (5% der Auftragssumme) prüfen",
    ),
    _Rule(
        rule_id="sicherheitseinbehalt",
        name="Sicherheitseinbehalt / Gewährleistungsbürgschaft",
        pattern=re.compile(
            r'Sicherheitseinbehalt|Einbehalt.*Gewährleistung|'
            r'Gewährleistungsbürgschaft|Erfüllungsbürgschaft|'
            r'\d+\s*%\s*(?:der\s+)?(?:Abrechnungs|Schluss|Abschlags)summe', re.I),
        severity="HIGH",
        clause_ref="§17 VOB/B",
        impact="Sicherheitseinbehalt — Liquiditätsrisiko für Auftragnehmer, Bürgschaftskosten beachten",
    ),
    _Rule(
        rule_id="abnahme_trigger",
        name="Abnahme-Regelung",
        pattern=re.compile(
            r'förmliche\s+Abnahme|Abnahmeprotokoll|Abnahmedatum|'
            r'Abnahme\s+(?:nach|gem\.?|gemäß)\s+§|fiktive\s+Abnahme|'
            r'§\s*12\s+VOB', re.I),
        severity="HIGH",
        clause_ref="§12 VOB/B",
        impact="Abnahme-Trigger definiert — Gewährleistungsfrist und Gefahrübergang ab Abnahmedatum",
    ),
    _Rule(
        rule_id="kuendigungsrecht",
        name="Kündigungsrecht (§8/§9 VOB/B)",
        pattern=re.compile(
            r'Kündigung(?:srecht|sgrund|sfrist|smöglichkeit)|freie\s+Kündigung|'
            r'außerordentliche\s+Kündigung|§\s*[89]\s+VOB|'
            r'Vertrag.*kündigen|Auftrag.*entziehen', re.I),
        severity="CRITICAL",
        clause_ref="§8/§9 VOB/B",
        impact="Kündigungsklausel — Vergütungsansprüche nach §8 Abs.1 VOB/B (erbrachte Leistungen + entg. Gewinn) prüfen",
    ),
    _Rule(
        rule_id="haftungsgrenze",
        name="Haftungsbeschränkung / -ausschluss",
        pattern=re.compile(
            r'Haftung(?:sbeschränkung|sausschluss|sobergrenze|slimit)|'
            r'beschränkt\s+(?:auf|bis)\s+(?:die\s+)?(?:Höhe|den\s+Betrag|\d)|'
            r'keine\s+Haftung|Haftungsausschluss', re.I),
        severity="HIGH",
        clause_ref="§13 Abs.7 VOB/B",
        impact="Haftungsobergrenze vereinbart — Deckungslücke bei Großschäden möglich",
    ),
    _Rule(
        rule_id="nachtrag",
        name="Nachtragsregelung / Änderungsanordnung",
        pattern=re.compile(
            r'Nachtrag(?:sbeauftragung|sleistung|sprüfung)|Änderungsanordnung|'
            r'Zusatzleistung|§\s*1\s+Abs\.?\s*[34]\s+VOB|'
            r'Mehr(?:kosten|aufwand).*Ankündigung|Ankündigungspflicht', re.I),
        severity="HIGH",
        clause_ref="§2 Abs.5/6 VOB/B",
        impact="Nachtragsprozess definiert — Ankündigungsfristen und Preisgrenzen für §2 Abs.6 beachten",
    ),
    _Rule(
        rule_id="zahlungsfrist",
        name="Zahlungsfrist / Fälligkeit (§16 VOB/B)",
        pattern=re.compile(
            r'Zahlungsfrist|Fälligkeit\s+(?:der\s+)?(?:Abschlags|Schluss)rechnung|'
            r'binnen\s+\d+\s+(?:Tage[n]?|Werktage[n]?)|§\s*16\s+VOB|'
            r'Prüffrist|Rechnungsprüfung\s+(?:innerhalb|binnen)', re.I),
        severity="HIGH",
        clause_ref="§16 VOB/B",
        impact="Zahlungsfrist abweichend von §16 VOB/B (18 Werktage) — Verzugsrisiko prüfen",
    ),
    _Rule(
        rule_id="skonto",
        name="Skonto / Preisnachlass",
        pattern=re.compile(
            r'Skonto|Preisnachlass|Rabatt.*Zahlung|Zahlung.*(?:innerhalb|binnen).*%', re.I),
        severity="MEDIUM",
        clause_ref="§16 Abs.5 VOB/B",
        impact="Skontoklausel — nur bei ausdrücklicher Vereinbarung in Auftragsunterlagen zulässig",
    ),
    _Rule(
        rule_id="baugrundrisiko",
        name="Baugrundrisiko",
        pattern=re.compile(
            r'Baugrund(?:risiko|verhältnis|gutachten)|unvorhergesehene\s+(?:Boden|Grund)|'
            r'geotechnisch|Bodenverhältnisse|§\s*4\s+Abs\.?\s*1\s+VOB', re.I),
        severity="MEDIUM",
        clause_ref="§4 Abs.1 VOB/B",
        impact="Baugrundrisiko erwähnt — Zuordnung zum AG (§4 Abs.1) oder abweichende Vereinbarung prüfen",
    ),
    _Rule(
        rule_id="pauschalpreis",
        name="Pauschalpreis / Globalpauschalvertrag",
        pattern=re.compile(
            r'Pauschal(?:preis|vertrag|honorar|betrag|vereinbarung)|Global(?:pauschal|preis)|'
            r'Festpreis|unveränderliche[rn]?\s+Preis', re.I),
        severity="HIGH",
        clause_ref="§2 Abs.7 VOB/B",
        impact="Pauschalpreisvertrag — Mengenänderungen und Nachtragsrecht (§2 Abs.7 VOB/B) gesondert prüfen",
    ),
    _Rule(
        rule_id="hoai_honorar",
        name="HOAI-Honorar / Leistungsphasen",
        pattern=re.compile(
            r'HOAI|Honorar(?:ordnung|tabelle|zone|vereinbarung)|Leistungsphase[n]?\s+\d|'
            r'Grundleistung(?:en)?|Besondere\s+Leistung', re.I),
        severity="MEDIUM",
        clause_ref="HOAI 2021",
        impact="HOAI-Honorar vereinbart — Mindesthonorar und Leistungsbilder nach HOAI 2021 prüfen",
    ),
    _Rule(
        rule_id="bedenken",
        name="Bedenkenanmeldung (§4 Abs.3 VOB/B)",
        pattern=re.compile(
            r'Bedenken(?:anmeldung|anzeige|pflicht)|Hinweispflicht.*Auftragnehmer|'
            r'§\s*4\s+Abs\.?\s*3\s+VOB|unverzüglich.*Bedenken', re.I),
        severity="MEDIUM",
        clause_ref="§4 Abs.3 VOB/B",
        impact="Bedenkenanmeldepflicht — Auftragnehmer muss Bedenken schriftlich unverzüglich anzeigen",
    ),
    _Rule(
        rule_id="gefahrtragung",
        name="Gefahrtragung / Versicherungspflicht",
        pattern=re.compile(
            r'Gefahrtragung|Gefahrübergang|Bauleistungsversicherung|'
            r'Versicherungspflicht|Betriebshaftpflicht|§\s*7\s+VOB', re.I),
        severity="MEDIUM",
        clause_ref="§7 VOB/B",
        impact="Gefahrtragungsregelung — Versicherungspflichten und Risikoübergang vor Abnahme prüfen",
    ),
]


def screen_sections(sections: list[dict]) -> dict[str, Any]:
    """
    Run construction Rete screener over extracted sections.
    Returns findings grouped by severity.

    Args:
        sections: list of {"text": str, "heading": str, "page": int, ...}
    """
    seen_rules: set[str] = set()
    findings: list[dict] = []

    for sec in sections:
        text = sec.get("text", "") or " ".join(sec.get("blocks", []))
        heading = sec.get("heading", "")
        full_text = f"{heading} {text}"
        if not full_text.strip():
            continue

        for rule in _CONSTRUCTION_RULES:
            if rule.rule_id in seen_rules:
                continue
            if rule.matches(full_text):
                seen_rules.add(rule.rule_id)
                findings.append({
                    "rule_id": rule.rule_id,
                    "clause": rule.name,
                    "severity": rule.severity,
                    "clause_ref": rule.clause_ref,
                    "impact": rule.impact,
                    "page": sec.get("page", 1),
                    "heading": heading[:80] if heading else "",
                    "detected_by": "construction_rete",
                })

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    high     = [f for f in findings if f["severity"] == "HIGH"]
    medium   = [f for f in findings if f["severity"] == "MEDIUM"]

    return {
        "findings": findings,
        "critical_count": len(critical),
        "high_count": len(high),
        "medium_count": len(medium),
        "total": len(findings),
        "risk_level": (
            "CRITICAL" if critical else
            "HIGH"     if high     else
            "MEDIUM"   if medium   else
            "LOW"
        ),
        "summary": _summarise(critical, high, medium),
    }


def _summarise(critical, high, medium) -> str:
    parts = []
    if critical:
        parts.append(f"{len(critical)} kritische Klauseln ({', '.join(f['rule_id'] for f in critical)})")
    if high:
        parts.append(f"{len(high)} hohe Risiken")
    if medium:
        parts.append(f"{len(medium)} mittlere Risiken")
    return "; ".join(parts) if parts else "Keine Risikoklauseln erkannt"


# ── Cross-doc Truth Gap (adapted from warroom.py) ─────────────────────────────

import re as _re

_NUM_PAT = _re.compile(
    r'(\d+(?:[,\.]\d+)?)\s*'
    r'(Tage?|Wochen?|Monate?|Jahre?|Werktage?|€|EUR|mm|cm|m²|m³|%)',
    _re.I
)


def _extract_numeric_claims(text: str) -> list[tuple[str, float, str]]:
    """Returns list of (raw_match, numeric_value, unit)."""
    results = []
    for m in _NUM_PAT.finditer(text):
        try:
            val = float(m.group(1).replace(",", "."))
            results.append((m.group(0), val, m.group(2).lower()))
        except ValueError:
            pass
    return results


def truth_gap_scan(all_sections_by_doc: dict[str, list[dict]]) -> dict[str, Any]:
    """
    Cross-document contradiction detector for construction sections.

    Args:
        all_sections_by_doc: {"filename": [sections...], ...}

    Returns findings where same unit-type claims differ >25% across docs.
    """
    if len(all_sections_by_doc) < 2:
        return {"verdict": "single_document", "gaps": [], "total_gaps": 0,
                "message": "Mindestens 2 Dokumente erforderlich."}

    # Collect (value, unit, page, doc) per unit type
    by_unit: dict[str, list[dict]] = {}
    for doc_name, sections in all_sections_by_doc.items():
        for sec in sections:
            text = sec.get("text", "") or " ".join(sec.get("blocks", []))
            for raw, val, unit in _extract_numeric_claims(text):
                by_unit.setdefault(unit, []).append({
                    "doc": doc_name, "value": val, "raw": raw,
                    "page": sec.get("page", 1),
                    "heading": sec.get("heading", "")[:60],
                })

    gaps = []
    for unit, claims in by_unit.items():
        # Group by doc
        docs_seen: dict[str, list[dict]] = {}
        for c in claims:
            docs_seen.setdefault(c["doc"], []).append(c)

        if len(docs_seen) < 2:
            continue

        doc_list = list(docs_seen.items())
        for i in range(len(doc_list)):
            for j in range(i + 1, len(doc_list)):
                doc_a, claims_a = doc_list[i]
                doc_b, claims_b = doc_list[j]
                for ca in claims_a:
                    for cb in claims_b:
                        if ca["value"] == 0 or cb["value"] == 0:
                            continue
                        rel_diff = abs(ca["value"] - cb["value"]) / max(ca["value"], cb["value"])
                        if rel_diff > 0.25:
                            gaps.append({
                                "unit": unit,
                                "doc_a": doc_a,
                                "doc_b": doc_b,
                                "value_a": ca["raw"],
                                "value_b": cb["raw"],
                                "page_a": ca["page"],
                                "page_b": cb["page"],
                                "heading_a": ca["heading"],
                                "heading_b": cb["heading"],
                                "spread_pct": round(rel_diff * 100),
                                "severity": "critical" if rel_diff > 0.5 else "high",
                                "label": f"Widerspruch: {ca['raw']} ({doc_a}) vs {cb['raw']} ({doc_b})",
                            })

    # Deduplicate + top 15
    seen_keys: set[str] = set()
    deduped = []
    for g in sorted(gaps, key=lambda x: -x["spread_pct"]):
        k = f"{g['unit']}:{g['value_a']}:{g['value_b']}"
        if k not in seen_keys:
            seen_keys.add(k)
            deduped.append(g)
        if len(deduped) >= 15:
            break

    return {
        "verdict": "gaps_found" if deduped else "consistent",
        "total_gaps": len(deduped),
        "critical_gaps": sum(1 for g in deduped if g["severity"] == "critical"),
        "gaps": deduped,
        "docs_analyzed": len(all_sections_by_doc),
        "message": f"{len(all_sections_by_doc)} Dokumente analysiert. {len(deduped)} Widersprüche gefunden.",
    }


# ── Adversarial Pollination (regex-only, no SQLite) ──────────────────────────

_RISK_BUYER = _re.compile(
    r'Haftung|Vertragsstrafe|Pönale|Kündigung|Verzug|Mängelrüge|'
    r'Schadensersatz|unbegrenzt|uneingeschränkt|Gewährleistung.*\d+\s*Jahr',
    _re.I
)
_PROTECTION_SELLER = _re.compile(
    r'Haftungsbeschränkung|Haftungsausschluss|Pauschal(?:vergütung|preis)|'
    r'höchstens|maximal|begrenzt\s+auf|Sicherheitseinbehalt.*ablösen|'
    r'Bürgschaft\s+statt\s+Einbehalt',
    _re.I
)


def adversarial_scan(sections: list[dict]) -> dict[str, Any]:
    """
    Predator/Prey regex scan over construction sections.
    No LLM — pure regex, instant.

    Returns heat map: which sections have clause conflict (both sides flagged).
    """
    results = []
    counts = {"risk_only": 0, "protection_only": 0, "dissonance": 0, "cold": 0}

    for sec in sections:
        text = sec.get("text", "") or " ".join(sec.get("blocks", []))
        heading = sec.get("heading", "")
        full = f"{heading} {text}"

        risk_hit = bool(_RISK_BUYER.search(full))
        prot_hit = bool(_PROTECTION_SELLER.search(full))

        if risk_hit and prot_hit:
            ptype = "DISSONANCE"
            intensity = 0.9
            counts["dissonance"] += 1
        elif risk_hit:
            ptype = "RISK"
            intensity = 0.6
            counts["risk_only"] += 1
        elif prot_hit:
            ptype = "PROTECTION"
            intensity = 0.5
            counts["protection_only"] += 1
        else:
            counts["cold"] += 1
            continue

        results.append({
            "heading": heading[:80],
            "page": sec.get("page", 1),
            "pheromone": ptype,
            "intensity": intensity,
            "label": (
                "⚡ Konfliktklausel — beide Parteien betroffen" if ptype == "DISSONANCE" else
                "⚠ Risikoklausel (Auftraggeber)" if ptype == "RISK" else
                "🛡 Schutzklausel (Auftragnehmer)"
            ),
        })

    # Sort dissonance first
    results.sort(key=lambda x: -x["intensity"])

    return {
        "heat_map": results[:30],
        "counts": counts,
        "dissonance_zones": [r for r in results if r["pheromone"] == "DISSONANCE"],
        "total_flagged": len(results),
        "summary": (
            f"{counts['dissonance']} Konfliktklauseln, "
            f"{counts['risk_only']} Risikoklauseln, "
            f"{counts['protection_only']} Schutzklauseln"
        ),
    }
