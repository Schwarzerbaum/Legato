"""EUeR — Einnahmen-Ueberschuss-Rechnung (Income-Expenditure Accounting).

Simplified profit calculation for Freiberufler and Kleingewerbetreibende.
Maps SKR03 account codes to Anlage EUeR form line numbers.
"""
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Booking, FiscalYear, ChartOfAccounts


# Anlage EUeR line mapping for SKR03 accounts
# Line numbers reference the official Anlage EUeR form
EUER_LINE_MAP = {
    # Betriebseinnahmen (Operating Income)
    "8000": {"line": "14", "category": "Erloese 7%"},
    "8100": {"line": "14", "category": "Steuerfreie Erloese"},
    "8300": {"line": "14", "category": "Erloese 19%"},
    "8400": {"line": "14", "category": "Erloese 19%"},
    "8900": {"line": "18", "category": "Veraeusserung Anlagevermoegen"},
    "8730": {"line": "14", "category": "Erhaltene Skonti"},
    "2100": {"line": "20", "category": "Zinsertraege"},
    # Betriebsausgaben (Operating Expenses)
    "3000": {"line": "26", "category": "Wareneinkauf"},
    "3300": {"line": "26", "category": "Wareneinkauf"},
    "3400": {"line": "26", "category": "Wareneinkauf 7%"},
    "4100": {"line": "31", "category": "Loehne und Gehaelter"},
    "4120": {"line": "31", "category": "Gehaelter"},
    "4130": {"line": "34", "category": "Sozialversicherung"},
    "4200": {"line": "50", "category": "Raumkosten/Miete"},
    "4210": {"line": "51", "category": "Energie"},
    "4250": {"line": "50", "category": "Reinigung"},
    "4300": {"line": "52", "category": "Versicherungen"},
    "4360": {"line": "57", "category": "Kfz-Steuer"},
    "4380": {"line": "57", "category": "Kfz-Kosten sonstige"},
    "4500": {"line": "57", "category": "Kfz-Kosten"},
    "4510": {"line": "57", "category": "Kfz-Steuer"},
    "4520": {"line": "57", "category": "Kfz-Versicherung"},
    "4530": {"line": "57", "category": "Kfz-Betriebskosten"},
    "4600": {"line": "58", "category": "Werbekosten"},
    "4610": {"line": "58", "category": "Repraesentation"},
    "4630": {"line": "59", "category": "Geschenke (abziehbar bis 50 EUR)"},
    "4640": {"line": "60", "category": "Bewirtungskosten (70%)"},
    "4650": {"line": "61", "category": "Reisekosten"},
    "4654": {"line": "61", "category": "Reisekosten Fahrt"},
    "4660": {"line": "61", "category": "Reisekosten Uebernachtung"},
    "4663": {"line": "61", "category": "Reisekosten Verpflegung"},
    "4700": {"line": "62", "category": "Porto"},
    "4800": {"line": "62", "category": "Telefon/Internet"},
    "4806": {"line": "62", "category": "Mobilfunk"},
    "4900": {"line": "68", "category": "Sonstige Aufwendungen"},
    "4910": {"line": "62", "category": "Burobedarf"},
    "4920": {"line": "62", "category": "Fachliteratur"},
    "4930": {"line": "63", "category": "Rechts-/Beratungskosten"},
    "4940": {"line": "63", "category": "Buchfuehrungskosten"},
    "4945": {"line": "63", "category": "Abschlusserstellung"},
    "4955": {"line": "64", "category": "Nebenkosten Geldverkehr"},
    "4970": {"line": "43", "category": "Abschreibungen"},
    "4980": {"line": "65", "category": "Gewerbesteuer"},
    "2110": {"line": "64", "category": "Zinsaufwendungen"},
    "2000": {"line": "68", "category": "Ausserordentliche Aufwendungen"},
}

# Expense categories for grouping
EXPENSE_CATEGORIES = {
    "26": "Waren, Rohstoffe und Hilfsstoffe",
    "31": "Personalkosten (Loehne und Gehaelter)",
    "34": "Sozialversicherungsbeitraege",
    "43": "Abschreibungen (AfA)",
    "50": "Raumkosten",
    "51": "Energie (Strom, Gas, Wasser)",
    "52": "Versicherungen",
    "57": "Fahrzeugkosten",
    "58": "Werbung und Repraesentation",
    "59": "Geschenke",
    "60": "Bewirtungskosten",
    "61": "Reisekosten",
    "62": "Uebrige unbeschraenkt abziehbare Betriebsausgaben",
    "63": "Beratungskosten",
    "64": "Finanzkosten",
    "65": "Gewerbesteuer",
    "68": "Sonstige Betriebsausgaben",
}


def get_euer_line(account_code: str) -> dict | None:
    """Map account code to EUeR line. Returns {line, category} or None."""
    return EUER_LINE_MAP.get(account_code)


def _classify_as_income_or_expense(account_code: str) -> str:
    """Classify SKR03 account as income or expense by code range."""
    code_int = int(account_code) if account_code.isdigit() else 0
    if 8000 <= code_int <= 8999:
        return "income"
    if 2100 <= code_int <= 2199:
        return "income"  # Zinsertraege
    if 2000 <= code_int <= 2999:
        return "expense"
    if 3000 <= code_int <= 3999:
        return "expense"  # Wareneinkauf
    if 4000 <= code_int <= 4999:
        return "expense"  # Betriebsausgaben
    return "other"


async def calculate_euer(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Calculate EUeR for a fiscal year.

    Returns structured report with:
    - betriebseinnahmen (income by category)
    - betriebsausgaben (expenses by category)
    - gewinn_oder_verlust (profit or loss)
    - line_totals (per Anlage EUeR line)
    """
    result = await db.execute(select(FiscalYear).where(FiscalYear.id == fiscal_year_id))
    fy = result.scalar_one_or_none()
    if not fy:
        raise ValueError(f"Fiscal year {fiscal_year_id} not found")

    # Get all bookings for fiscal year
    result = await db.execute(
        select(Booking).where(Booking.fiscal_year_id == fiscal_year_id)
    )
    bookings = result.scalars().all()

    # Aggregate by account
    account_sums: dict[str, float] = {}
    for b in bookings:
        # For income accounts: credit increases
        debit_type = _classify_as_income_or_expense(b.debit_account_code)
        credit_type = _classify_as_income_or_expense(b.credit_account_code)

        # Income accounts accumulate via credit
        if credit_type == "income":
            account_sums[b.credit_account_code] = account_sums.get(b.credit_account_code, 0) + b.amount
        # Expense accounts accumulate via debit
        if debit_type == "expense":
            account_sums[b.debit_account_code] = account_sums.get(b.debit_account_code, 0) + b.amount

        # Handle reverse entries (storno)
        if b.is_storno:
            if debit_type == "income":
                account_sums[b.debit_account_code] = account_sums.get(b.debit_account_code, 0) - b.amount
            if credit_type == "expense":
                account_sums[b.credit_account_code] = account_sums.get(b.credit_account_code, 0) - b.amount

    # Build income section
    income_items = []
    total_income = 0.0
    for code, amount in sorted(account_sums.items()):
        if _classify_as_income_or_expense(code) == "income":
            euer = get_euer_line(code)
            income_items.append({
                "code": code,
                "category": euer["category"] if euer else f"Konto {code}",
                "line": euer["line"] if euer else "?",
                "amount": round(amount, 2),
            })
            total_income += amount

    # Build expense section
    expense_items = []
    total_expenses = 0.0
    line_totals: dict[str, float] = {}
    for code, amount in sorted(account_sums.items()):
        if _classify_as_income_or_expense(code) == "expense":
            euer = get_euer_line(code)
            line = euer["line"] if euer else "68"
            expense_items.append({
                "code": code,
                "category": euer["category"] if euer else f"Konto {code}",
                "line": line,
                "amount": round(amount, 2),
            })
            total_expenses += amount
            line_totals[line] = line_totals.get(line, 0) + amount

    profit = round(total_income - total_expenses, 2)

    return {
        "fiscal_year": fy.year,
        "betriebseinnahmen": {
            "items": income_items,
            "total": round(total_income, 2),
        },
        "betriebsausgaben": {
            "items": expense_items,
            "total": round(total_expenses, 2),
            "by_line": {
                line: {
                    "name": EXPENSE_CATEGORIES.get(line, f"Zeile {line}"),
                    "amount": round(amt, 2),
                }
                for line, amt in sorted(line_totals.items())
            },
        },
        "gewinn_oder_verlust": profit,
        "ergebnis": "Gewinn" if profit >= 0 else "Verlust",
    }


async def generate_euer_report(db: AsyncSession, fiscal_year_id: int) -> str:
    """Generate a markdown-formatted EUeR report."""
    euer = await calculate_euer(db, fiscal_year_id)

    lines = [
        f"# Einnahmen-Ueberschuss-Rechnung {euer['fiscal_year']}",
        "",
        "## Betriebseinnahmen",
        "",
        "| Konto | Bezeichnung | Zeile | Betrag |",
        "|-------|-------------|-------|--------|",
    ]
    for item in euer["betriebseinnahmen"]["items"]:
        lines.append(f"| {item['code']} | {item['category']} | {item['line']} | {item['amount']:,.2f} EUR |")
    lines.append(f"| | **Summe Einnahmen** | | **{euer['betriebseinnahmen']['total']:,.2f} EUR** |")
    lines.append("")

    lines.append("## Betriebsausgaben")
    lines.append("")
    lines.append("| Konto | Bezeichnung | Zeile | Betrag |")
    lines.append("|-------|-------------|-------|--------|")
    for item in euer["betriebsausgaben"]["items"]:
        lines.append(f"| {item['code']} | {item['category']} | {item['line']} | {item['amount']:,.2f} EUR |")
    lines.append(f"| | **Summe Ausgaben** | | **{euer['betriebsausgaben']['total']:,.2f} EUR** |")
    lines.append("")

    lines.append("## Ergebnis")
    lines.append("")
    lines.append(f"**{euer['ergebnis']}: {euer['gewinn_oder_verlust']:,.2f} EUR**")

    return "\n".join(lines)
