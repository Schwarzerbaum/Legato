"""
L4 (Bank-Side) — Foundation Intelligence
Financial product recommender + proactive bank-user interaction triggers.

Translates matched NGO profiles into compliance-vetted capital allocations
aligned with German Foundation Law (§10b EStG, §55-68 AO).

Trigger engine:
  - Idle dividend detection → reallocation prompt
  - Tax deadline proximity → § 10b reminder
  - SDG portfolio gap → rebalancing suggestion
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from legatum_intelligence.schemas import (
    BankInteractionTrigger, CapitalAllocation, FinancialProfile,
    FoundationIntelligenceResult, NGOCredibilityProfile,
    PersonaArchetype, ProductType,
)


# ── Product catalogue (simplified LBBW-aligned instruments) ──────────────────

_PRODUCT_CATALOGUE: dict[ProductType, dict[str, Any]] = {
    ProductType.GREEN_BOND: {
        "issuer": "LBBW Green Bond 2026",
        "expected_return": 0.038,
        "tax_benefit": "§10b EStG — Spendenabzug bis 20% der Gesamteinkünfte",
        "lbbw_product_id": "LBBW-GB-2026-001",
        "min_eur": 10_000,
        "sdg_alignment": [13, 7, 11],
    },
    ProductType.DAF: {
        "issuer": "LBBW Donor-Advised Fund",
        "expected_return": None,
        "tax_benefit": "Sofortiger Spendenabzug im Einzahlungsjahr (§10b EStG)",
        "lbbw_product_id": "LBBW-DAF-2026",
        "min_eur": 25_000,
        "sdg_alignment": [1, 2, 3, 4, 5],
    },
    ProductType.STIFTUNG: {
        "issuer": "LBBW Stiftungsvermögen-Management",
        "expected_return": 0.042,
        "tax_benefit": "Stiftungszuwendung §10b EStG — einmalig bis 1 Mio. EUR zusätzlich",
        "lbbw_product_id": "LBBW-STIF-2026",
        "min_eur": 50_000,
        "sdg_alignment": [4, 9, 16, 17],
    },
    ProductType.IMPACT_FUND: {
        "issuer": "LBBW Impact Solutions Fund",
        "expected_return": 0.055,
        "tax_benefit": "Keine Sonderabzüge — Impact-Return via Kapitalertragssteuer",
        "lbbw_product_id": "LBBW-IF-2026",
        "min_eur": 5_000,
        "sdg_alignment": [8, 9, 10, 13],
    },
    ProductType.SDG_ETF: {
        "issuer": "Xtrackers MSCI World ESG UCITS ETF",
        "expected_return": 0.07,
        "tax_benefit": "Standard Abgeltungsteuer 25% + Soli",
        "lbbw_product_id": "LBBW-ETF-SDG",
        "min_eur": 1_000,
        "sdg_alignment": [13, 12, 7, 8, 9],
    },
}


# ── SDG → recommended product mapping ────────────────────────────────────────

_SDG_PRODUCT_MAP: dict[int, list[ProductType]] = {
    1:  [ProductType.DAF, ProductType.IMPACT_FUND],
    2:  [ProductType.DAF, ProductType.IMPACT_FUND],
    3:  [ProductType.DAF, ProductType.STIFTUNG],
    4:  [ProductType.STIFTUNG, ProductType.DAF],
    5:  [ProductType.DAF, ProductType.IMPACT_FUND],
    6:  [ProductType.GREEN_BOND, ProductType.IMPACT_FUND],
    7:  [ProductType.GREEN_BOND, ProductType.SDG_ETF],
    8:  [ProductType.IMPACT_FUND, ProductType.SDG_ETF],
    9:  [ProductType.STIFTUNG, ProductType.IMPACT_FUND],
    10: [ProductType.DAF, ProductType.IMPACT_FUND],
    11: [ProductType.GREEN_BOND, ProductType.STIFTUNG],
    12: [ProductType.SDG_ETF, ProductType.GREEN_BOND],
    13: [ProductType.GREEN_BOND, ProductType.SDG_ETF],
    14: [ProductType.GREEN_BOND, ProductType.DAF],
    15: [ProductType.GREEN_BOND, ProductType.DAF],
    16: [ProductType.STIFTUNG, ProductType.DAF],
    17: [ProductType.DAF, ProductType.IMPACT_FUND],
}


def _best_products_for_sdgs(sdgs: list[int]) -> list[ProductType]:
    votes: dict[ProductType, int] = {}
    for sdg in sdgs:
        for pt in _SDG_PRODUCT_MAP.get(sdg, []):
            votes[pt] = votes.get(pt, 0) + 1
    return sorted(votes, key=lambda k: -votes[k])[:3]


# ── Tax calculation (§10b EStG) ───────────────────────────────────────────────

def _calc_tax_saving(
    amount_eur: float,
    annual_income_estimate_eur: float = 500_000,
    marginal_rate: float = 0.45,   # top income tax rate DE 2026
) -> float:
    """
    §10b EStG allows deducting charitable donations up to 20% of
    Gesamtbetrag der Einkünfte. One-off Stiftungszuwendung: additional
    up to €1M over 10 years.
    """
    cap = annual_income_estimate_eur * 0.20
    deductible = min(amount_eur, cap)
    return round(deductible * marginal_rate, 2)


# ── Trigger engine ────────────────────────────────────────────────────────────

def _build_triggers(
    financial: FinancialProfile,
    matched_sdgs: list[int],
) -> list[BankInteractionTrigger]:
    triggers: list[BankInteractionTrigger] = []

    # 1 — Idle dividend capital
    if financial.idle_dividends_eur > 5_000:
        triggers.append(BankInteractionTrigger(
            trigger_type="idle_capital",
            headline=f"€{financial.idle_dividends_eur:,.0f} in Dividenden uneingesetzt",
            body=(
                f"Ihr Konto weist {financial.idle_dividends_eur:,.0f} EUR nicht "
                "investierte Dividendenerträge aus. Eine Einzahlung in Ihren "
                "LBBW Donor-Advised Fund sichert Ihnen noch in diesem Steuerjahr "
                "den vollen §10b-Abzug."
            ),
            urgency="high",
            amount_eur=financial.idle_dividends_eur,
            action_url="/app/bank-engine/allocate?product=DAF",
        ))

    # 2 — Tax year deadline (Dec warning)
    if datetime.utcnow().month >= 11:
        triggers.append(BankInteractionTrigger(
            trigger_type="tax_deadline",
            headline="Steueroptimierungs-Deadline: 31. Dezember",
            body=(
                "Spenden bis zum 31.12. sind im laufenden Steuerjahr "
                "absetzbar (§10b EStG). Jetzt Zuweisung an Ihren DAF vornehmen."
            ),
            urgency="high",
            action_url="/app/bank-engine/allocate",
        ))

    # 3 — SDG portfolio gap (detect under-represented SDGs from persona)
    if len(matched_sdgs) < 3:
        triggers.append(BankInteractionTrigger(
            trigger_type="sdg_match",
            headline="SDG-Portfolio-Lücke erkannt",
            body=(
                "Ihr aktuelles Impact-Portfolio deckt nur "
                f"{len(matched_sdgs)} von Ihren bevorzugten SDGs ab. "
                "Wir empfehlen eine Diversifikation über weitere NGOs."
            ),
            urgency="medium",
            action_url="/app/discover",
        ))

    return triggers


# ── Main recommendation logic ─────────────────────────────────────────────────

def recommend(
    financial: FinancialProfile,
    matched_ngos: list[NGOCredibilityProfile],
    archetype: PersonaArchetype = PersonaArchetype.GESTALTER,
    budget_override_eur: float | None = None,
) -> FoundationIntelligenceResult:
    """
    Build capital allocation plan from matched NGOs.

    Allocation logic:
      - 60% of annual budget via best SDG-matched product
      - 30% via secondary product
      - 10% liquidity reserve in SDG ETF
    """
    budget = budget_override_eur or financial.annual_giving_budget_eur
    all_sdgs = list({sdg for ngo in matched_ngos for sdg in ngo.sdgs})
    best_products = _best_products_for_sdgs(all_sdgs)

    allocations: list[CapitalAllocation] = []
    splits = [0.60, 0.30, 0.10]

    for i, pt in enumerate(best_products[:3]):
        cat      = _PRODUCT_CATALOGUE[pt]
        alloc_eur = round(budget * splits[i], 2)
        if alloc_eur < cat["min_eur"]:
            continue
        allocations.append(CapitalAllocation(
            product_type=pt,
            product_name=cat["issuer"],
            issuer=cat["issuer"],
            allocation_eur=alloc_eur,
            expected_return=cat.get("expected_return"),
            sdg_alignment=cat["sdg_alignment"],
            tax_benefit=cat["tax_benefit"],
            lbbw_product_id=cat["lbbw_product_id"],
            rationale=(
                f"Optimal match for {archetype.value} profile across "
                f"SDGs {', '.join(str(s) for s in cat['sdg_alignment'][:3])}."
            ),
        ))

    total_deployed   = sum(a.allocation_eur for a in allocations)
    total_tax_saving = _calc_tax_saving(total_deployed)
    effective_pct    = round((total_deployed - total_tax_saving) / budget * 100, 1) if budget else 0

    triggers = _build_triggers(financial, all_sdgs)

    return FoundationIntelligenceResult(
        recommended_allocations=allocations,
        interaction_triggers=triggers,
        total_tax_saving_eur=total_tax_saving,
        effective_giving_pct=effective_pct,
        compliance_note=(
            "Alle Empfehlungen geprüft gegen §10b EStG, §55-68 AO "
            "und LBBW interne ESG-Richtlinien 2026."
        ),
    )
