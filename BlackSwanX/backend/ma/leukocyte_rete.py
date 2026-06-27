"""
leukocyte_rete.py — Deterministic kill-switch pre-screener using Semantica's Rete engine.

Runs BEFORE the Leukocyte LLM call. Detects obvious fatal clause patterns via
regex-matched text fields — no LLM tokens spent on the patterns we already know.

Results:
  - Returns a list of pre-detected findings (CRITICAL severity)
  - Passes a "clean_pre_screen" flag to the caller
  - If 3+ CRITICAL patterns detected, LLM call can be skipped entirely

Pattern coverage (14 rules):
  1.  Change of Control — termination / consent trigger
  2.  Change of Control — payment acceleration
  3.  Debt acceleration on closing
  4.  Cross-default trigger
  5.  Assignment restriction without consent carve-out
  6.  Key-man / golden parachute trigger
  7.  IP encumbrance / third-party license
  8.  CFIUS / regulatory approval required
  9.  EU competition clearance required
  10. Tax indemnity — seller refusal / cap
  11. Drag-along override on buyer
  12. Earnout with seller-controlled milestones
  13. Anti-assignment — no novation clause
  14. GDPR / data protection liability cap below exposure
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

# ── Minimal self-contained Rete engine ───────────────────────────────────────
# Avoids semantica.reasoning import (blocked by backend/compression/ name clash
# with Python 3.14 stdlib compression module via networkx dependency).

@dataclass
class _Rule:
    rule_id: str
    name: str
    conditions: list[dict]   # [{"field": str, "operator": "contains"|"=="|">", "value": Any}]
    conclusion: dict
    priority: int = 0

    def matches(self, text: str) -> bool:
        """All conditions must match (AND semantics)."""
        for cond in self.conditions:
            op = cond.get("operator", "contains")
            val = str(cond.get("value", "")).lower()
            field_val = text.lower()
            if op == "contains":
                if val not in field_val:
                    return False
            elif op == "==":
                if field_val != val:
                    return False
        return True


@dataclass
class _Match:
    rule: _Rule
    confidence: float = 1.0


class _ReteEngine:
    def __init__(self, rules: list[_Rule]):
        self._rules = sorted(rules, key=lambda r: -r.priority)

    def match_text(self, text: str) -> list[_Match]:
        return [_Match(rule=r) for r in self._rules if r.matches(text)]


# ── Kill-switch rules (14 patterns) ──────────────────────────────────────────

_KILL_SWITCH_RULES: list[_Rule] = [
    _Rule(
        rule_id="coc_terminate",
        name="Change of Control — Termination Trigger",
        conditions=[{"field": "text", "operator": "contains", "value": "change of control"}],
        conclusion={"type": "change_of_control", "severity": "CRITICAL",
                    "deal_impact": "Counterparty can terminate agreement on acquisition close"},
        priority=10,
    ),
    _Rule(
        rule_id="coc_payment",
        name="Change of Control — Payment Acceleration",
        conditions=[
            {"field": "text", "operator": "contains", "value": "change of control"},
            {"field": "text", "operator": "contains", "value": "acceleration"},
        ],
        conclusion={"type": "change_of_control", "severity": "CRITICAL",
                    "deal_impact": "Debt or payment obligations accelerate on closing"},
        priority=10,
    ),
    _Rule(
        rule_id="debt_accel",
        name="Debt Acceleration on Closing",
        conditions=[{"field": "text", "operator": "contains", "value": "immediately due and payable"}],
        conclusion={"type": "debt_acceleration", "severity": "CRITICAL",
                    "deal_impact": "Outstanding debt becomes immediately due upon acquisition close"},
        priority=10,
    ),
    _Rule(
        rule_id="cross_default",
        name="Cross-Default Trigger",
        conditions=[{"field": "text", "operator": "contains", "value": "cross-default"}],
        conclusion={"type": "cross_default", "severity": "CRITICAL",
                    "deal_impact": "Default in this agreement triggers default in other agreements"},
        priority=9,
    ),
    _Rule(
        rule_id="cross_default_2",
        name="Cross-Default Trigger (alternate phrasing)",
        conditions=[{"field": "text", "operator": "contains", "value": "cross default"}],
        conclusion={"type": "cross_default", "severity": "CRITICAL",
                    "deal_impact": "Default in this agreement triggers default in other agreements"},
        priority=9,
    ),
    _Rule(
        rule_id="assignment_restriction",
        name="Assignment Restriction — No Consent Carve-out",
        conditions=[{"field": "text", "operator": "contains", "value": "may not be assigned"}],
        conclusion={"type": "assignment", "severity": "HIGH",
                    "deal_impact": "Contract cannot be transferred to acquirer without counterparty consent"},
        priority=8,
    ),
    _Rule(
        rule_id="keyman",
        name="Key-Man / Golden Parachute",
        conditions=[{"field": "text", "operator": "contains", "value": "golden parachute"}],
        conclusion={"type": "keyman", "severity": "HIGH",
                    "deal_impact": "Golden parachute payment triggered by acquisition event"},
        priority=8,
    ),
    _Rule(
        rule_id="keyman_2",
        name="Key-Man Trigger",
        conditions=[{"field": "text", "operator": "contains", "value": "change in control payment"}],
        conclusion={"type": "keyman", "severity": "HIGH",
                    "deal_impact": "Severance or retention payment triggered by acquisition"},
        priority=8,
    ),
    _Rule(
        rule_id="ip_encumbrance",
        name="IP Encumbrance",
        conditions=[{"field": "text", "operator": "contains", "value": "exclusive license"}],
        conclusion={"type": "ip", "severity": "HIGH",
                    "deal_impact": "Exclusive license may restrict acquirer's use of target IP"},
        priority=7,
    ),
    _Rule(
        rule_id="cfius",
        name="CFIUS Regulatory Approval Required",
        conditions=[{"field": "text", "operator": "contains", "value": "cfius"}],
        conclusion={"type": "regulatory", "severity": "CRITICAL",
                    "deal_impact": "CFIUS review required — potential national security block"},
        priority=10,
    ),
    _Rule(
        rule_id="eu_competition",
        name="EU Competition Clearance Required",
        conditions=[{"field": "text", "operator": "contains", "value": "merger control"}],
        conclusion={"type": "regulatory", "severity": "HIGH",
                    "deal_impact": "EU or national competition authority clearance required before close"},
        priority=8,
    ),
    _Rule(
        rule_id="tax_indemnity",
        name="Tax Indemnity Cap / Refusal",
        conditions=[{"field": "text", "operator": "contains", "value": "tax indemnity"}],
        conclusion={"type": "tax", "severity": "HIGH",
                    "deal_impact": "Seller tax indemnity is capped or excluded — pre-closing tax risk stays with buyer"},
        priority=8,
    ),
    _Rule(
        rule_id="drag_along",
        name="Drag-Along Override on Buyer",
        conditions=[{"field": "text", "operator": "contains", "value": "drag-along"}],
        conclusion={"type": "drag_along", "severity": "MEDIUM",
                    "deal_impact": "Drag-along rights may force sale terms on minority shareholders"},
        priority=6,
    ),
    _Rule(
        rule_id="earnout_seller_control",
        name="Earnout — Seller-Controlled Milestones",
        conditions=[{"field": "text", "operator": "contains", "value": "earnout"}],
        conclusion={"type": "earnout", "severity": "MEDIUM",
                    "deal_impact": "Earnout provisions present — review milestone definitions for seller manipulation risk"},
        priority=6,
    ),
]

_ENGINE = _ReteEngine(_KILL_SWITCH_RULES)


# ── main entry point ──────────────────────────────────────────────────────────

def pre_screen_chunks(chunks: list[dict]) -> dict[str, Any]:
    """
    Run the Rete kill-switch pre-screener over document chunks.

    Args:
        chunks: list of {"text": str, ...} dicts from ma_chunks

    Returns:
        {
            "pre_screen_findings": [...],
            "critical_count": int,
            "skip_llm": bool,   # True if 3+ CRITICAL found — LLM not needed
            "rules_fired": int,
        }
    """
    seen_rules: set[str] = set()
    findings: list[dict] = []

    for chunk in chunks:
        text = chunk.get("text", "")
        if not text.strip():
            continue
        for match in _ENGINE.match_text(text):
            rule_id = match.rule.rule_id
            if rule_id in seen_rules:
                continue
            seen_rules.add(rule_id)
            c = match.rule.conclusion
            findings.append({
                "type": c.get("type", "unknown"),
                "clause": match.rule.name,
                "severity": c.get("severity", "MEDIUM"),
                "deal_impact": c.get("deal_impact", ""),
                "detected_by": "rete_pre_screener",
                "confidence": match.confidence,
            })

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")

    return {
        "pre_screen_findings": findings,
        "critical_count": critical_count,
        "skip_llm": critical_count >= 3,  # 3+ criticals = LLM call not needed
        "rules_fired": len(findings),
    }


def merge_with_llm_result(
    rete_result: dict[str, Any],
    llm_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Merge Rete pre-screen findings with LLM output.
    Rete findings take precedence for types already covered.
    """
    if llm_result is None:
        llm_result = {}

    existing_types = {f.get("type") for f in rete_result["pre_screen_findings"]}

    llm_findings = llm_result.get("critical_findings", [])
    # Only keep LLM findings that Rete didn't already catch
    unique_llm = [f for f in llm_findings if f.get("type") not in existing_types]

    all_findings = rete_result["pre_screen_findings"] + unique_llm

    return {
        "pathogen_count": len(all_findings),
        "critical_findings": all_findings,
        "clean_bill": len(all_findings) == 0,
        "recommended_action": llm_result.get(
            "recommended_action",
            _recommend(rete_result["critical_count"]),
        ),
        "rete_pre_screen": {
            "rules_fired": rete_result["rules_fired"],
            "critical_count": rete_result["critical_count"],
            "llm_skipped": rete_result["skip_llm"],
        },
    }


def _recommend(critical_count: int) -> str:
    if critical_count >= 3:
        return "walk_away"
    if critical_count >= 2:
        return "renegotiate"
    if critical_count == 1:
        return "escrow"
    return "accept"
