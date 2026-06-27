"""LLM-based receipt scanning and auto-categorization for SKR03.

Uses Ollama (local LLM) to:
  1. Extract structured data from receipt text / bank statement lines
  2. Auto-categorize bookings into SKR03 account codes
  3. Batch-categorize multiple transactions efficiently

All inference runs locally — zero API cost, full privacy.
"""
import json
import logging
import re
from datetime import date

from backend.llm.router import smart_chat

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

RECEIPT_CATEGORIZE_SYSTEM = (
    "You are a German tax accountant (Steuerberater). "
    "Given a transaction description, suggest the best SKR03 account code. "
    "Consider: the nature of the expense, tax deductibility, and proper "
    "categorization per German tax law. "
    "Return JSON with: account_code, account_name, tax_rate (0.19 or 0.07 or 0.0), "
    "confidence (0-1), reasoning."
)

RECEIPT_EXTRACT_SYSTEM = (
    "You are a German tax accountant. Extract structured data from the "
    "following receipt or bank statement text. "
    "Return JSON with: date (YYYY-MM-DD), vendor (company name), "
    "amount (float, positive), tax_rate (0.19 or 0.07 or 0.0), "
    "description (short summary of what was purchased/paid)."
)

# ---------------------------------------------------------------------------
# Default fallback when LLM response is unparseable
# ---------------------------------------------------------------------------

_DEFAULT_CATEGORIZATION = {
    "account_code": "4900",
    "account_name": "Sonstige betriebliche Aufwendungen",
    "tax_rate": 0.19,
    "confidence": 0.1,
    "reasoning": "Could not determine category — defaulted to miscellaneous expenses.",
}

_DEFAULT_EXTRACTION = {
    "date": None,
    "vendor": "Unknown",
    "amount": 0.0,
    "tax_rate": 0.19,
    "description": "",
}


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from LLM output, tolerating markdown fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "")

    # Try parsing the whole cleaned text first
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # Fall back to finding the first { ... } block
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _safe_float(val, default: float = 0.0) -> float:
    """Coerce a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _normalise_categorization(raw: dict) -> dict:
    """Ensure categorization dict has all expected keys with correct types."""
    return {
        "account_code": str(raw.get("account_code", "4900")),
        "account_name": str(raw.get("account_name", "Unbekannt")),
        "tax_rate": _safe_float(raw.get("tax_rate"), 0.19),
        "confidence": max(0.0, min(1.0, _safe_float(raw.get("confidence"), 0.5))),
        "reasoning": str(raw.get("reasoning", "")),
    }


def _normalise_extraction(raw: dict) -> dict:
    """Ensure extraction dict has all expected keys with correct types."""
    # Validate / coerce date
    raw_date = raw.get("date")
    parsed_date = None
    if isinstance(raw_date, str):
        try:
            parsed_date = date.fromisoformat(raw_date).isoformat()
        except ValueError:
            parsed_date = None

    return {
        "date": parsed_date,
        "vendor": str(raw.get("vendor", "Unknown")),
        "amount": abs(_safe_float(raw.get("amount"))),
        "tax_rate": _safe_float(raw.get("tax_rate"), 0.19),
        "description": str(raw.get("description", "")),
    }


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

async def auto_categorize_booking(
    description: str,
    amount: float,
    vendor: str = "",
) -> dict:
    """Categorize a single booking into an SKR03 account via LLM.

    Uses the swarm model (fast, cheap) for quick categorization.

    Returns dict with: account_code, account_name, tax_rate, confidence, reasoning.
    """
    prompt = (
        f"Transaction to categorize:\n"
        f"  Description: {description}\n"
        f"  Amount: {amount:.2f} EUR\n"
    )
    if vendor:
        prompt += f"  Vendor: {vendor}\n"
    prompt += "\nReturn ONLY valid JSON."

    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=RECEIPT_CATEGORIZE_SYSTEM,
            temperature=0.2,
            max_tokens=512,
            json_mode=True,
            force_model="swarm",
        )
        parsed = _extract_json(response)
        if parsed:
            return _normalise_categorization(parsed)
    except Exception as exc:
        logger.warning("auto_categorize_booking failed: %s", exc)

    return dict(_DEFAULT_CATEGORIZATION)


async def scan_receipt_text(text: str) -> dict:
    """Extract structured data from raw receipt or bank statement text.

    Returns dict with: date, vendor, amount, tax_rate, description,
    plus a nested category_suggestion from auto-categorization.
    """
    prompt = (
        f"Receipt / bank statement text:\n"
        f"---\n{text}\n---\n\n"
        "Extract the structured data. Return ONLY valid JSON."
    )

    extracted = dict(_DEFAULT_EXTRACTION)

    try:
        response, _model = await smart_chat(
            prompt=prompt,
            system=RECEIPT_EXTRACT_SYSTEM,
            temperature=0.1,
            max_tokens=512,
            json_mode=True,
            force_model="swarm",
        )
        parsed = _extract_json(response)
        if parsed:
            extracted = _normalise_extraction(parsed)
    except Exception as exc:
        logger.warning("scan_receipt_text extraction failed: %s", exc)

    # Run auto-categorization on the extracted info
    cat_desc = extracted["description"] or text[:200]
    cat_amount = extracted["amount"] or 0.0
    cat_vendor = extracted["vendor"] or ""

    category_suggestion = await auto_categorize_booking(
        description=cat_desc,
        amount=cat_amount,
        vendor=cat_vendor,
    )

    extracted["category_suggestion"] = category_suggestion
    return extracted


async def batch_categorize(descriptions: list[dict]) -> list[dict]:
    """Categorize multiple bookings in sequence.

    Each item in *descriptions* must have:
      - description: str
      - amount: float
      - vendor: str (optional)

    Returns a list of categorization results in the same order.
    """
    results: list[dict] = []

    for item in descriptions:
        desc = item.get("description", "")
        amount = _safe_float(item.get("amount"))
        vendor = item.get("vendor", "")

        result = await auto_categorize_booking(
            description=desc,
            amount=amount,
            vendor=vendor,
        )
        results.append(result)

    return results
