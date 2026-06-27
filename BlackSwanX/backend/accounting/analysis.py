"""Financial AI analysis pipeline — fraud detection, tax optimisation, cashflow, audit risk.

Combines pure-math statistical tests (Benford, duplicates, round-number clustering)
with LLM-powered agent analysis via the Ollama swarm.  All inference is local.
"""
import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select, func, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Booking, FiscalYear, ChartOfAccounts
from backend.accounting.bookkeeping import get_trial_balance, get_account_balance
from backend.llm.router import smart_chat

logger = logging.getLogger(__name__)


# ===================================================================
# Agent system prompts (inline until migrated to backend/llm/prompts.py)
# ===================================================================

FRAUD_DETECTOR_SYSTEM = (
    "You are a forensic accounting specialist trained in German commercial law "
    "(HGB) and tax law (AO/EStG). Your task is to analyse bookkeeping data for "
    "signs of fraud, manipulation, or error.\n\n"
    "You receive:\n"
    "  - Benford's law analysis of first-digit distribution\n"
    "  - Duplicate booking report\n"
    "  - Round-number anomaly statistics\n"
    "  - A summary of the trial balance\n\n"
    "Evaluate the evidence and return JSON with:\n"
    "  risk_level: 'low' | 'medium' | 'high'\n"
    "  findings: list of finding strings\n"
    "  recommendations: list of recommended actions\n"
    "  confidence: float 0-1\n\n"
    "Be precise and cite the specific statistical results that support each finding. "
    "Do not invent issues that the data does not support."
)

TAX_OPTIMIZER_SYSTEM = (
    "You are a German Steuerberater specialising in small-business tax optimisation "
    "(Einzelunternehmer, Freiberufler, kleine GmbH). You analyse a company's "
    "bookkeeping data and trial balance to find missed deductions and optimisation "
    "opportunities.\n\n"
    "Focus areas:\n"
    "  - Section 7g EStG (Investitionsabzugsbetrag)\n"
    "  - Home office deduction (Arbeitszimmer)\n"
    "  - Vehicle expenses (1% rule vs. Fahrtenbuch)\n"
    "  - Geringwertige Wirtschaftsgueter (GWG, section 6 Abs. 2 EStG)\n"
    "  - Vorsteuerabzug correctness\n"
    "  - Depreciation optimisation (AfA)\n"
    "  - Charitable donations (Spenden, section 10b EStG)\n\n"
    "Return JSON with:\n"
    "  potential_savings_eur: float estimate\n"
    "  optimisations: list of {area, description, estimated_impact_eur, action}\n"
    "  warnings: list of compliance risk strings\n"
    "  confidence: float 0-1"
)

CASHFLOW_PREDICTOR_SYSTEM = (
    "You are a financial analyst specialising in small-business cashflow forecasting. "
    "Given monthly income and expense history, predict the next 3 months and flag "
    "potential liquidity risks.\n\n"
    "Return JSON with:\n"
    "  forecast: list of {month: 'YYYY-MM', predicted_income, predicted_expenses, "
    "predicted_net}\n"
    "  trend: 'improving' | 'stable' | 'declining'\n"
    "  liquidity_risk: 'low' | 'medium' | 'high'\n"
    "  insights: list of insight strings\n"
    "  confidence: float 0-1"
)

AUDIT_RISK_SYSTEM = (
    "You are a German Betriebspruefung (tax audit) risk analyst. Given key financial "
    "metrics for a small business, estimate the probability of being selected for a "
    "tax audit and recommend preparation steps.\n\n"
    "Risk factors you evaluate:\n"
    "  - Revenue relative to industry average\n"
    "  - Expense-to-revenue ratio\n"
    "  - Cash transactions percentage\n"
    "  - Year-over-year variance\n"
    "  - Unusual account patterns\n\n"
    "Return JSON with:\n"
    "  audit_probability: float 0-1\n"
    "  risk_level: 'low' | 'medium' | 'high'\n"
    "  risk_factors: list of {factor, severity, detail}\n"
    "  preparation_steps: list of action strings\n"
    "  confidence: float 0-1"
)


# ===================================================================
# JSON parsing helper
# ===================================================================

def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from LLM output."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "")
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ===================================================================
# 1. Benford's Law Analysis (pure math, no LLM)
# ===================================================================

def benford_analysis(amounts: list[float]) -> dict:
    """Test first-digit distribution against Benford's law.

    Benford expected probability: P(d) = log10(1 + 1/d) for d in 1..9.

    Returns observed/expected distributions, chi-squared statistic, p-value
    approximation, and a suspicious flag (True if p < 0.05).
    """
    expected = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

    # Extract first significant digit from each amount, skip zeros
    first_digits: list[int] = []
    for a in amounts:
        a = abs(a)
        if a < 0.01:
            continue
        # Strip to first significant digit
        s = f"{a:.10f}".lstrip("0").lstrip(".")
        if s:
            digit = int(s[0])
            if 1 <= digit <= 9:
                first_digits.append(digit)

    n = len(first_digits)
    if n < 10:
        return {
            "observed": {},
            "expected": {str(d): round(v, 4) for d, v in expected.items()},
            "chi_squared": 0.0,
            "p_value": 1.0,
            "suspicious": False,
            "sample_size": n,
            "note": "Too few data points for meaningful Benford analysis.",
        }

    counts = Counter(first_digits)
    observed = {d: counts.get(d, 0) / n for d in range(1, 10)}

    # Chi-squared goodness-of-fit
    chi_sq = sum(
        ((observed[d] - expected[d]) ** 2) / expected[d]
        for d in range(1, 10)
    )

    # Approximate p-value using chi-squared CDF (df=8)
    # Lightweight approximation — avoids scipy dependency
    p_value = _chi2_survival(chi_sq, df=8)

    return {
        "observed": {str(d): round(v, 4) for d, v in observed.items()},
        "expected": {str(d): round(v, 4) for d, v in expected.items()},
        "chi_squared": round(chi_sq, 4),
        "p_value": round(p_value, 6),
        "suspicious": p_value < 0.05,
        "sample_size": n,
    }


def _chi2_survival(x: float, df: int) -> float:
    """Approximate upper-tail probability for chi-squared distribution.

    Uses the Wilson-Hilferty normal approximation:
        Z = ( (x/df)^(1/3) - (1 - 2/(9*df)) ) / sqrt(2/(9*df))
    Then Phi(-Z) gives the survival probability.
    """
    if x <= 0:
        return 1.0
    z = ((x / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    # Standard normal survival via error function approximation
    return 0.5 * math.erfc(z / math.sqrt(2))


# ===================================================================
# 2. Duplicate Detection (pure logic, no LLM)
# ===================================================================

def find_duplicates(bookings: list[dict]) -> list[dict]:
    """Find duplicate bookings (same amount + same date + same accounts).

    Returns a list of duplicate groups, each containing the matching bookings.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)

    for b in bookings:
        key = (
            b.get("date"),
            round(float(b.get("amount", 0)), 2),
            b.get("debit_account_code"),
            b.get("credit_account_code"),
        )
        groups[key].append(b)

    duplicates = []
    for key, group in groups.items():
        if len(group) >= 2:
            duplicates.append({
                "date": key[0],
                "amount": key[1],
                "debit_account": key[2],
                "credit_account": key[3],
                "count": len(group),
                "booking_ids": [b.get("id") for b in group],
                "descriptions": [b.get("description", "") for b in group],
            })

    return duplicates


# ===================================================================
# 3. Round-Number Anomaly Detection (pure math, no LLM)
# ===================================================================

def find_round_number_anomalies(amounts: list[float]) -> dict:
    """Detect suspicious clustering at round numbers.

    Round numbers: amounts ending in .00 that are multiples of 10,
    or classic psychological pricing (X9.99, X99, etc.).
    """
    if not amounts:
        return {
            "round_count": 0,
            "total_count": 0,
            "ratio": 0.0,
            "suspicious": False,
        }

    round_count = 0
    for a in amounts:
        a = abs(a)
        if a < 0.01:
            continue
        # Check if amount is a round multiple of 50 or 100
        if a >= 10 and (a % 50 == 0 or a % 100 == 0):
            round_count += 1
        # Check psychological pricing thresholds (99.99, 499, 999, etc.)
        elif _is_just_below_round(a):
            round_count += 1

    total = len([a for a in amounts if abs(a) >= 0.01])
    ratio = round_count / total if total > 0 else 0.0

    return {
        "round_count": round_count,
        "total_count": total,
        "ratio": round(ratio, 4),
        "suspicious": ratio > 0.3,
    }


def _is_just_below_round(amount: float) -> bool:
    """Check if amount is just below a round number (e.g. 99.99, 499, 999.99)."""
    for threshold in [100, 500, 1000, 5000, 10000]:
        diff = threshold - amount
        if 0 < diff <= 1.01:
            return True
    return False


# ===================================================================
# Database helpers
# ===================================================================

async def _get_all_bookings(db: AsyncSession, fiscal_year_id: int) -> list[dict]:
    """Fetch all bookings for a fiscal year as dicts."""
    result = await db.execute(
        select(Booking)
        .where(Booking.fiscal_year_id == fiscal_year_id)
        .order_by(Booking.date, Booking.booking_number)
    )
    bookings = result.scalars().all()
    return [
        {
            "id": b.id,
            "booking_number": b.booking_number,
            "date": b.date.isoformat() if b.date else None,
            "debit_account_code": b.debit_account_code,
            "credit_account_code": b.credit_account_code,
            "amount": b.amount,
            "tax_rate": b.tax_rate,
            "description": b.description or "",
            "is_storno": b.is_storno,
        }
        for b in bookings
    ]


async def _get_monthly_totals(
    db: AsyncSession, fiscal_year_id: int
) -> list[dict]:
    """Aggregate monthly income (credit to 8xxx) and expenses (debit to 4xxx/6xxx)."""
    result = await db.execute(
        select(Booking)
        .where(Booking.fiscal_year_id == fiscal_year_id)
        .order_by(Booking.date)
    )
    bookings = result.scalars().all()

    monthly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"income": 0.0, "expenses": 0.0}
    )

    for b in bookings:
        if not b.date:
            continue
        month_key = b.date.strftime("%Y-%m")
        # Revenue accounts: 8000-8999 (Erloese)
        if b.credit_account_code and b.credit_account_code.startswith("8"):
            monthly[month_key]["income"] += b.amount
        # Expense accounts: 4000-4999 or 6000-6999
        if b.debit_account_code and (
            b.debit_account_code.startswith("4")
            or b.debit_account_code.startswith("6")
        ):
            monthly[month_key]["expenses"] += b.amount

    return [
        {
            "month": m,
            "income": round(monthly[m]["income"], 2),
            "expenses": round(monthly[m]["expenses"], 2),
            "net": round(monthly[m]["income"] - monthly[m]["expenses"], 2),
        }
        for m in sorted(monthly.keys())
    ]


# ===================================================================
# 4. Fraud Scan (statistical + LLM)
# ===================================================================

async def run_fraud_scan(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Combined fraud analysis: Benford + duplicates + round numbers + LLM.

    Fetches all bookings, runs three statistical tests, then sends a
    summary to the fraud_detector agent for holistic evaluation.
    """
    bookings = await _get_all_bookings(db, fiscal_year_id)
    amounts = [b["amount"] for b in bookings]

    benford = benford_analysis(amounts)
    duplicates = find_duplicates(bookings)
    round_numbers = find_round_number_anomalies(amounts)

    # Build summary for the LLM agent
    trial_balance = await get_trial_balance(db, fiscal_year_id)
    tb_summary = [
        f"  {r['code']} {r['name']}: {r['balance']:.2f}"
        for r in trial_balance[:20]
    ]

    prompt = (
        f"Fiscal year bookings: {len(bookings)}\n\n"
        f"BENFORD ANALYSIS:\n"
        f"  Chi-squared: {benford['chi_squared']}, p-value: {benford['p_value']}\n"
        f"  Suspicious: {benford['suspicious']}\n\n"
        f"DUPLICATE BOOKINGS: {len(duplicates)} groups found\n"
    )
    for dup in duplicates[:5]:
        prompt += (
            f"  {dup['date']} | {dup['amount']:.2f} EUR | "
            f"{dup['debit_account']}->{dup['credit_account']} | "
            f"count={dup['count']}\n"
        )
    prompt += (
        f"\nROUND-NUMBER ANOMALIES:\n"
        f"  Ratio: {round_numbers['ratio']:.2%} "
        f"({round_numbers['round_count']}/{round_numbers['total_count']})\n"
        f"  Suspicious: {round_numbers['suspicious']}\n\n"
        f"TRIAL BALANCE (top 20):\n" + "\n".join(tb_summary) + "\n\n"
        "Analyse and return JSON."
    )

    llm_result = {}
    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=FRAUD_DETECTOR_SYSTEM,
            temperature=0.3,
            max_tokens=2048,
            json_mode=True,
            force_model="reasoning",
        )
        llm_result = _extract_json(response) or {}
    except Exception as exc:
        logger.warning("Fraud scan LLM analysis failed: %s", exc)
        llm_result = {"error": str(exc)}

    return {
        "benford": benford,
        "duplicates": duplicates,
        "round_numbers": round_numbers,
        "agent_analysis": llm_result,
        "booking_count": len(bookings),
    }


# ===================================================================
# 5. Tax Optimisation (LLM)
# ===================================================================

async def run_tax_optimization(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Analyse bookings for missed deductions and tax optimisation opportunities."""
    trial_balance = await get_trial_balance(db, fiscal_year_id)
    bookings = await _get_all_bookings(db, fiscal_year_id)

    # Summarise by account type
    expense_total = sum(r["balance"] for r in trial_balance if r.get("type") == "expense")
    revenue_total = sum(abs(r["balance"]) for r in trial_balance if r.get("type") == "revenue")

    tb_lines = [
        f"  {r['code']} {r['name']}: {r['balance']:.2f} ({r['type']})"
        for r in trial_balance
    ]

    prompt = (
        f"Company financial summary (fiscal year):\n"
        f"  Total revenue: {revenue_total:.2f} EUR\n"
        f"  Total expenses: {expense_total:.2f} EUR\n"
        f"  Net: {revenue_total - abs(expense_total):.2f} EUR\n"
        f"  Total bookings: {len(bookings)}\n\n"
        f"TRIAL BALANCE:\n" + "\n".join(tb_lines) + "\n\n"
        "Identify missed deductions and optimisation opportunities. Return JSON."
    )

    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=TAX_OPTIMIZER_SYSTEM,
            temperature=0.3,
            max_tokens=2048,
            json_mode=True,
            force_model="reasoning",
        )
        result = _extract_json(response) or {}
    except Exception as exc:
        logger.warning("Tax optimisation analysis failed: %s", exc)
        result = {"error": str(exc)}

    result["revenue"] = revenue_total
    result["expenses"] = expense_total
    return result


# ===================================================================
# 6. Cashflow Forecast (LLM)
# ===================================================================

async def run_cashflow_forecast(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Forecast cashflow for the next 3 months based on historical patterns."""
    monthly = await _get_monthly_totals(db, fiscal_year_id)

    if not monthly:
        return {
            "forecast": [],
            "trend": "unknown",
            "liquidity_risk": "unknown",
            "insights": ["No booking data available for forecasting."],
            "confidence": 0.0,
        }

    history_lines = [
        f"  {m['month']}: income={m['income']:.2f}, expenses={m['expenses']:.2f}, net={m['net']:.2f}"
        for m in monthly
    ]

    prompt = (
        f"Monthly income/expense history ({len(monthly)} months):\n"
        + "\n".join(history_lines) + "\n\n"
        "Predict the next 3 months and assess liquidity risk. Return JSON."
    )

    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=CASHFLOW_PREDICTOR_SYSTEM,
            temperature=0.4,
            max_tokens=1500,
            json_mode=True,
            force_model="reasoning",
        )
        result = _extract_json(response) or {}
    except Exception as exc:
        logger.warning("Cashflow forecast failed: %s", exc)
        result = {"error": str(exc)}

    result["history"] = monthly
    return result


# ===================================================================
# 7. Audit Risk Assessment (LLM)
# ===================================================================

async def run_audit_risk(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Estimate tax audit probability and recommend preparation steps."""
    trial_balance = await get_trial_balance(db, fiscal_year_id)
    bookings = await _get_all_bookings(db, fiscal_year_id)

    revenue = sum(abs(r["balance"]) for r in trial_balance if r.get("type") == "revenue")
    expenses = sum(r["balance"] for r in trial_balance if r.get("type") == "expense")
    expense_ratio = expenses / revenue if revenue > 0 else 0.0

    # Count cash transactions (Kasse = account 1000)
    cash_bookings = [
        b for b in bookings
        if b.get("debit_account_code") == "1000" or b.get("credit_account_code") == "1000"
    ]
    cash_ratio = len(cash_bookings) / len(bookings) if bookings else 0.0

    prompt = (
        f"Company financial metrics:\n"
        f"  Revenue: {revenue:.2f} EUR\n"
        f"  Expenses: {expenses:.2f} EUR\n"
        f"  Expense-to-revenue ratio: {expense_ratio:.2%}\n"
        f"  Total bookings: {len(bookings)}\n"
        f"  Cash transaction ratio: {cash_ratio:.2%} ({len(cash_bookings)} of {len(bookings)})\n"
        f"  Industry: general / unknown\n\n"
        "Estimate audit probability and recommend preparation. Return JSON."
    )

    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=AUDIT_RISK_SYSTEM,
            temperature=0.3,
            max_tokens=1500,
            json_mode=True,
            force_model="reasoning",
        )
        result = _extract_json(response) or {}
    except Exception as exc:
        logger.warning("Audit risk assessment failed: %s", exc)
        result = {"error": str(exc)}

    result["metrics"] = {
        "revenue": revenue,
        "expenses": expenses,
        "expense_ratio": round(expense_ratio, 4),
        "cash_ratio": round(cash_ratio, 4),
        "booking_count": len(bookings),
    }
    return result


# ===================================================================
# 8. Full Financial Analysis (orchestrator)
# ===================================================================

async def run_full_financial_analysis(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Run all financial analyses and aggregate into a unified health report.

    Executes fraud scan, tax optimisation, cashflow forecast, and audit risk
    assessment, then combines results into a single dict.
    """
    # Verify fiscal year exists
    result = await db.execute(
        select(FiscalYear).where(FiscalYear.id == fiscal_year_id)
    )
    fy = result.scalar_one_or_none()
    if not fy:
        return {"error": f"Fiscal year with id={fiscal_year_id} not found."}

    fraud = await run_fraud_scan(db, fiscal_year_id)
    tax = await run_tax_optimization(db, fiscal_year_id)
    cashflow = await run_cashflow_forecast(db, fiscal_year_id)
    audit = await run_audit_risk(db, fiscal_year_id)

    # Derive overall health score (0-100)
    health_score = 100.0
    if fraud.get("agent_analysis", {}).get("risk_level") == "high":
        health_score -= 30
    elif fraud.get("agent_analysis", {}).get("risk_level") == "medium":
        health_score -= 15
    if fraud.get("benford", {}).get("suspicious"):
        health_score -= 10
    if fraud.get("round_numbers", {}).get("suspicious"):
        health_score -= 5
    if len(fraud.get("duplicates", [])) > 3:
        health_score -= 10
    if audit.get("risk_level") == "high":
        health_score -= 15
    elif audit.get("risk_level") == "medium":
        health_score -= 5
    if cashflow.get("liquidity_risk") == "high":
        health_score -= 10

    health_score = max(0.0, min(100.0, health_score))

    return {
        "fiscal_year": fy.year,
        "health_score": round(health_score, 1),
        "fraud_scan": fraud,
        "tax_optimization": tax,
        "cashflow_forecast": cashflow,
        "audit_risk": audit,
    }
