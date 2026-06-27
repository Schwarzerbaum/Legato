"""DATEV CSV/ASCII parser — Import bookkeeping data from Germany's standard format.

DATEV exports come in two formats:
1. CSV (semicolon-separated, cp1252 encoding) — Modern export from DATEV Unternehmen Online
2. ASCII fixed-width — Legacy DATEV-Format with defined column positions

Both are parsed into normalized booking dicts, validated against the chart of accounts,
and imported into the BlackSwanX accounting database.
"""
import csv
import io
import re
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Booking, FiscalYear, AuditLog, ChartOfAccounts
from backend.accounting.bookkeeping import BookingEntry, create_booking, get_or_create_fiscal_year


def detect_datev_format(file_content: bytes) -> str:
    """Auto-detect whether file is DATEV CSV or ASCII format."""
    try:
        text = file_content.decode("cp1252")
    except UnicodeDecodeError:
        text = file_content.decode("utf-8", errors="replace")

    # DATEV CSV starts with header "EXTF" or has semicolons
    if text.startswith('"EXTF"') or text.startswith("EXTF"):
        return "csv"
    # Check for semicolons (CSV) vs fixed-width
    first_lines = text.split("\n")[:5]
    semicolon_count = sum(line.count(";") for line in first_lines)
    if semicolon_count > 10:
        return "csv"
    return "ascii"


def _parse_datev_date(date_str: str, default_year: int = None) -> date | None:
    """Parse DATEV date formats: DDMM, DDMMYY, DDMMYYYY, DD.MM.YYYY."""
    if not date_str or not date_str.strip():
        return None
    s = date_str.strip().replace(".", "")

    try:
        if len(s) == 4:  # DDMM
            day, month = int(s[:2]), int(s[2:4])
            year = default_year or date.today().year
            return date(year, month, day)
        elif len(s) == 6:  # DDMMYY
            day, month, yr = int(s[:2]), int(s[2:4]), int(s[4:6])
            year = 2000 + yr if yr < 50 else 1900 + yr
            return date(year, month, day)
        elif len(s) == 8:  # DDMMYYYY
            day, month, year = int(s[:2]), int(s[2:4]), int(s[4:8])
            return date(year, month, day)
    except (ValueError, IndexError):
        return None
    return None


def _parse_amount(amount_str: str) -> float:
    """Parse German number format: 1.234,56 -> 1234.56."""
    if not amount_str:
        return 0.0
    s = amount_str.strip()
    # Remove thousand separators (dots), replace decimal comma with dot
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def parse_datev_csv(file_content: bytes, encoding: str = "cp1252") -> list[dict]:
    """Parse DATEV CSV export format.

    DATEV CSV has a header row (EXTF metadata) followed by column headers,
    then data rows. Key columns:
      - Umsatz (Soll/Haben): Amount
      - Soll/Haben-Kennzeichen: 'S' or 'H'
      - Konto: Debit/Credit account
      - Gegenkonto: Counter account
      - BU-Schluessel: Tax key
      - Belegdatum: Document date (DDMM)
      - Belegfeld 1: Document reference
      - Buchungstext: Description
    """
    try:
        text = file_content.decode(encoding)
    except UnicodeDecodeError:
        text = file_content.decode("utf-8", errors="replace")

    lines = text.strip().split("\n")
    bookings = []

    # Find header row — skip EXTF metadata lines
    header_idx = 0
    for i, line in enumerate(lines):
        if "Umsatz" in line and "Konto" in line:
            header_idx = i
            break
        # Also detect by common DATEV column names
        if "Soll/Haben" in line or "Gegenkonto" in line:
            header_idx = i
            break

    if header_idx == 0 and not ("Umsatz" in lines[0] or "Konto" in lines[0]):
        # First line is likely EXTF header, skip 1-2 lines
        header_idx = 1
        if len(lines) > 2 and "Umsatz" not in lines[1]:
            header_idx = 2

    # Parse CSV from header row
    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")

    for row in reader:
        try:
            # Find amount column (various DATEV versions use different names)
            amount_str = (
                row.get("Umsatz (ohne Soll/Haben-Kz)", "") or
                row.get("Umsatz", "") or
                row.get("WKZ Umsatz", "")
            )
            amount = _parse_amount(amount_str)
            if amount == 0:
                continue

            # Soll/Haben determines direction
            sh_kz = (
                row.get("Soll/Haben-Kennzeichen", "") or
                row.get("S/H", "") or
                row.get("Soll/Haben", "")
            ).strip().upper()

            konto = (row.get("Konto", "") or row.get("Kontonummer", "")).strip()
            gegenkonto = (row.get("Gegenkonto (ohne BU-Schluessel)", "") or
                         row.get("Gegenkonto", "")).strip()

            if not konto or not gegenkonto:
                continue

            # S = Soll (debit to Konto), H = Haben (credit to Konto)
            if sh_kz == "S":
                debit_code = konto
                credit_code = gegenkonto
            else:
                debit_code = gegenkonto
                credit_code = konto

            # BU-Schluessel (tax key)
            bu = (row.get("BU-Schluessel", "") or row.get("BU-Schl.", "")).strip()
            tax_rate = _bu_to_tax_rate(bu)

            # Date
            belegdatum = (row.get("Belegdatum", "") or row.get("Datum", "")).strip()
            booking_date = _parse_datev_date(belegdatum)

            # Description
            buchungstext = (
                row.get("Buchungstext", "") or
                row.get("Text", "")
            ).strip()

            # Document reference
            belegfeld = (row.get("Belegfeld 1", "") or row.get("Beleg", "")).strip()

            bookings.append({
                "debit_code": debit_code,
                "credit_code": credit_code,
                "amount": amount,
                "tax_rate": tax_rate,
                "date": booking_date,
                "description": buchungstext,
                "document_ref": belegfeld,
                "bu_key": bu,
                "raw": dict(row),
            })
        except Exception:
            continue  # Skip unparseable rows

    return bookings


def _bu_to_tax_rate(bu_key: str) -> float:
    """Convert DATEV BU-Schluessel to tax rate."""
    BU_TAX_MAP = {
        "2": 0.07,   # 7% USt
        "3": 0.19,   # 19% USt
        "8": 0.07,   # 7% VSt
        "9": 0.19,   # 19% VSt
        "40": 0.19,  # Innergemeinschaftlicher Erwerb 19%
        "46": 0.07,  # Innergemeinschaftlicher Erwerb 7%
        "10": 0.0,   # Steuerfrei
        "11": 0.0,   # Reverse Charge
    }
    return BU_TAX_MAP.get(bu_key, 0.0)


def parse_datev_ascii(file_content: bytes) -> list[dict]:
    """Parse DATEV ASCII fixed-width format.

    Legacy format with fixed column positions.
    Common layout (positions may vary by DATEV version):
      Col 1-12:  Umsatz (right-aligned, 2 decimal places without separator)
      Col 13:    Soll/Haben (S/H)
      Col 14-21: Konto
      Col 22-29: Gegenkonto
      Col 30-33: BU-Schluessel
      Col 34-37: Belegdatum (DDMM)
      Col 38-49: Belegfeld
      Col 50+:   Buchungstext
    """
    try:
        text = file_content.decode("cp1252")
    except UnicodeDecodeError:
        text = file_content.decode("utf-8", errors="replace")

    bookings = []
    for line in text.strip().split("\n"):
        if len(line) < 50:
            continue
        try:
            amount_str = line[0:12].strip()
            amount = round(int(amount_str) / 100, 2) if amount_str.isdigit() else _parse_amount(amount_str)
            if amount == 0:
                continue

            sh_kz = line[12:13].strip().upper()
            konto = line[13:21].strip()
            gegenkonto = line[21:29].strip()
            bu = line[29:33].strip()
            belegdatum = line[33:37].strip()
            belegfeld = line[37:49].strip()
            buchungstext = line[49:].strip()

            if not konto or not gegenkonto:
                continue

            if sh_kz == "S":
                debit_code = konto
                credit_code = gegenkonto
            else:
                debit_code = gegenkonto
                credit_code = konto

            bookings.append({
                "debit_code": debit_code,
                "credit_code": credit_code,
                "amount": amount,
                "tax_rate": _bu_to_tax_rate(bu),
                "date": _parse_datev_date(belegdatum),
                "description": buchungstext,
                "document_ref": belegfeld,
                "bu_key": bu,
            })
        except Exception:
            continue

    return bookings


def validate_bookings(
    bookings: list[dict],
    valid_codes: set[str] = None,
) -> list[dict]:
    """Validate parsed bookings. Returns list of validation errors."""
    errors = []
    for i, b in enumerate(bookings):
        if b.get("amount", 0) <= 0:
            errors.append({"row": i, "field": "amount", "error": "Amount must be positive"})
        if not b.get("debit_code"):
            errors.append({"row": i, "field": "debit_code", "error": "Missing debit account"})
        if not b.get("credit_code"):
            errors.append({"row": i, "field": "credit_code", "error": "Missing credit account"})
        if b.get("debit_code") == b.get("credit_code"):
            errors.append({"row": i, "field": "accounts", "error": "Debit and credit accounts are the same"})
        if not b.get("date"):
            errors.append({"row": i, "field": "date", "error": "Invalid or missing date"})
        if valid_codes:
            if b.get("debit_code") and b["debit_code"] not in valid_codes:
                errors.append({"row": i, "field": "debit_code", "error": f"Unknown account {b['debit_code']}"})
            if b.get("credit_code") and b["credit_code"] not in valid_codes:
                errors.append({"row": i, "field": "credit_code", "error": f"Unknown account {b['credit_code']}"})
    return errors


async def import_datev_to_db(
    db: AsyncSession,
    file_content: bytes,
    fiscal_year: int = None,
) -> dict:
    """Parse and import DATEV file into BlackSwanX database.

    Auto-detects format (CSV vs ASCII), validates, and creates bookings.
    Returns import summary with counts and errors.
    """
    # Detect format and parse
    fmt = detect_datev_format(file_content)
    if fmt == "csv":
        bookings = parse_datev_csv(file_content)
    else:
        bookings = parse_datev_ascii(file_content)

    if not bookings:
        return {"imported": 0, "errors": [{"error": "No bookings found in file"}], "format": fmt}

    # Determine fiscal year from data
    if fiscal_year is None:
        dates = [b["date"] for b in bookings if b.get("date")]
        if dates:
            fiscal_year = dates[0].year
        else:
            fiscal_year = date.today().year

    fy = await get_or_create_fiscal_year(db, fiscal_year)

    # Get valid account codes for validation
    result = await db.execute(select(ChartOfAccounts.code))
    valid_codes = {row[0] for row in result}

    # Validate
    errors = validate_bookings(bookings, valid_codes if valid_codes else None)

    # Import valid bookings
    imported = 0
    import_errors = []
    for i, b in enumerate(bookings):
        # Skip rows with validation errors
        row_errors = [e for e in errors if e["row"] == i]
        if row_errors:
            import_errors.extend(row_errors)
            continue

        try:
            entry = BookingEntry(
                debit_code=b["debit_code"],
                credit_code=b["credit_code"],
                amount=b["amount"],
                booking_date=b["date"] or date.today(),
                description=b.get("description", ""),
                tax_rate=b.get("tax_rate", 0.0),
                document_ref=b.get("document_ref", ""),
            )
            await create_booking(db, entry, fiscal_year_id=fy.id)
            imported += 1
        except Exception as e:
            import_errors.append({"row": i, "error": str(e)})

    # Audit trail for the import
    audit = AuditLog(
        entity_type="datev_import",
        entity_id=fy.id,
        action="create",
        old_value=None,
        new_value={
            "format": fmt,
            "total_rows": len(bookings),
            "imported": imported,
            "errors": len(import_errors),
        },
        user_action=f"DATEV {fmt.upper()} import: {imported}/{len(bookings)} bookings",
    )
    db.add(audit)
    await db.commit()

    return {
        "format": fmt,
        "total_rows": len(bookings),
        "imported": imported,
        "errors": import_errors[:50],  # Cap at 50 errors to avoid huge responses
        "fiscal_year": fiscal_year,
    }
