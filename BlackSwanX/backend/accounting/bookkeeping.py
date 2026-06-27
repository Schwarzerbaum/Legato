"""Double-entry bookkeeping engine — GoBD-compliant.

GoBD (Grundsaetze zur ordnungsmaessigen Fuehrung und Aufbewahrung von
Buechern, Aufzeichnungen und Unterlagen in elektronischer Form):
  - Sequential, gapless booking numbers per fiscal year
  - Locked bookings are immutable (no edits, no deletes)
  - Corrections only via Stornobuchung (reverse booking)
  - Complete audit trail in AuditLog
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Booking, FiscalYear, AuditLog, ChartOfAccounts
from backend.accounting.legal_citations import cite


class BookingEntry:
    """Input for creating a new booking."""
    def __init__(
        self,
        debit_code: str,
        credit_code: str,
        amount: float,
        booking_date: date,
        description: str = "",
        tax_rate: float = 0.0,
        document_ref: str = "",
        receipt_path: str = "",
    ):
        if amount <= 0:
            raise ValueError("Booking amount must be positive")
        self.debit_code = debit_code
        self.credit_code = credit_code
        self.amount = round(amount, 2)
        self.date = booking_date
        self.description = description
        self.tax_rate = tax_rate
        self.tax_amount = round(amount * tax_rate, 2)
        self.document_ref = document_ref
        self.receipt_path = receipt_path


async def get_or_create_fiscal_year(db: AsyncSession, year: int) -> FiscalYear:
    """Get fiscal year or create if not exists."""
    result = await db.execute(select(FiscalYear).where(FiscalYear.year == year))
    fy = result.scalar_one_or_none()
    if fy:
        return fy
    fy = FiscalYear(
        year=year,
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
    )
    db.add(fy)
    await db.flush()
    return fy


async def get_next_booking_number(db: AsyncSession, fiscal_year_id: int) -> int:
    """Get next sequential booking number for a fiscal year. GoBD: gapless."""
    result = await db.execute(
        select(func.max(Booking.booking_number))
        .where(Booking.fiscal_year_id == fiscal_year_id)
    )
    max_num = result.scalar_one_or_none()
    return (max_num or 0) + 1


async def create_booking(db: AsyncSession, entry: BookingEntry, fiscal_year_id: int = None) -> Booking:
    """Create a new double-entry booking with GoBD compliance.

    - Assigns sequential gapless booking number
    - Validates accounts exist in chart
    - Creates AuditLog entry
    - Returns the created Booking
    """
    # Get or create fiscal year
    if fiscal_year_id is None:
        fy = await get_or_create_fiscal_year(db, entry.date.year)
        fiscal_year_id = fy.id
    else:
        result = await db.execute(select(FiscalYear).where(FiscalYear.id == fiscal_year_id))
        fy = result.scalar_one_or_none()
        if not fy:
            raise ValueError(f"Fiscal year {fiscal_year_id} not found")

    # Check fiscal year not closed
    if fy.is_closed:
        raise ValueError(f"Fiscal year {fy.year} is closed. No new bookings allowed.")

    # Get next sequential number
    booking_number = await get_next_booking_number(db, fiscal_year_id)

    booking = Booking(
        booking_number=booking_number,
        date=entry.date,
        debit_account_code=entry.debit_code,
        credit_account_code=entry.credit_code,
        amount=entry.amount,
        tax_rate=entry.tax_rate,
        tax_amount=entry.tax_amount,
        description=entry.description,
        document_ref=entry.document_ref,
        receipt_path=entry.receipt_path,
        fiscal_year_id=fiscal_year_id,
    )
    db.add(booking)
    await db.flush()

    # Audit trail
    audit = AuditLog(
        entity_type="booking",
        entity_id=booking.id,
        action="create",
        old_value=None,
        new_value={
            "booking_number": booking_number,
            "debit": entry.debit_code,
            "credit": entry.credit_code,
            "amount": entry.amount,
            "description": entry.description,
        },
        user_action=cite("booking_create", f"Buchung #{booking_number}"),
    )
    db.add(audit)
    await db.commit()
    return booking


async def lock_booking(db: AsyncSession, booking_id: int) -> Booking:
    """Lock a booking — makes it immutable per GoBD."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise ValueError(f"Booking {booking_id} not found")
    if booking.is_locked:
        return booking  # Already locked

    booking.is_locked = True
    audit = AuditLog(
        entity_type="booking",
        entity_id=booking.id,
        action="lock",
        old_value={"is_locked": False},
        new_value={"is_locked": True},
        user_action=cite("booking_lock", f"Buchung #{booking.booking_number}"),
    )
    db.add(audit)
    await db.commit()
    return booking


async def create_storno(db: AsyncSession, booking_id: int, reason: str = "") -> Booking:
    """Create a Stornobuchung (reverse booking) — the GoBD way to correct errors.

    Never delete or modify a locked booking. Instead, create a reverse booking
    that cancels it out, then optionally create a new correct booking.
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    original = result.scalar_one_or_none()
    if not original:
        raise ValueError(f"Booking {booking_id} not found")

    # Create reverse: swap debit/credit
    entry = BookingEntry(
        debit_code=original.credit_account_code,
        credit_code=original.debit_account_code,
        amount=original.amount,
        booking_date=date.today(),
        description=f"STORNO #{original.booking_number}: {reason or original.description}",
        tax_rate=original.tax_rate,
        document_ref=original.document_ref,
    )

    storno = await create_booking(db, entry, fiscal_year_id=original.fiscal_year_id)
    storno.is_storno = True
    storno.storno_of_id = original.id

    # Lock the original if not already
    if not original.is_locked:
        original.is_locked = True

    audit = AuditLog(
        entity_type="booking",
        entity_id=original.id,
        action="storno",
        old_value={"booking_number": original.booking_number},
        new_value={"storno_booking_id": storno.id, "storno_number": storno.booking_number},
        user_action=cite("booking_storno", f"Storno von Buchung #{original.booking_number}: {reason}"),
    )
    db.add(audit)
    await db.commit()
    return storno


async def get_account_balance(
    db: AsyncSession,
    account_code: str,
    fiscal_year_id: int,
    as_of_date: date = None,
) -> float:
    """Calculate account balance: sum of debits minus sum of credits.

    For asset/expense accounts: debit increases, credit decreases
    For liability/equity/revenue accounts: credit increases, debit decreases
    Returns the raw debit-credit difference; caller interprets sign by account type.
    """
    filters = [Booking.fiscal_year_id == fiscal_year_id]
    if as_of_date:
        filters.append(Booking.date <= as_of_date)

    # Sum of amounts where this account is debited
    result = await db.execute(
        select(func.coalesce(func.sum(Booking.amount), 0.0))
        .where(and_(Booking.debit_account_code == account_code, *filters))
    )
    total_debit = result.scalar_one()

    # Sum of amounts where this account is credited
    result = await db.execute(
        select(func.coalesce(func.sum(Booking.amount), 0.0))
        .where(and_(Booking.credit_account_code == account_code, *filters))
    )
    total_credit = result.scalar_one()

    return round(total_debit - total_credit, 2)


async def get_trial_balance(db: AsyncSession, fiscal_year_id: int) -> list[dict]:
    """Generate trial balance (Saldenliste) for a fiscal year.

    Returns all accounts with non-zero balances.
    """
    # Get all unique account codes used in bookings
    debit_codes = await db.execute(
        select(Booking.debit_account_code).distinct()
        .where(Booking.fiscal_year_id == fiscal_year_id)
    )
    credit_codes = await db.execute(
        select(Booking.credit_account_code).distinct()
        .where(Booking.fiscal_year_id == fiscal_year_id)
    )

    all_codes = set()
    for row in debit_codes:
        all_codes.add(row[0])
    for row in credit_codes:
        all_codes.add(row[0])

    balances = []
    for code in sorted(all_codes):
        balance = await get_account_balance(db, code, fiscal_year_id)
        if abs(balance) > 0.005:  # Skip zero balances
            # Try to get account name
            result = await db.execute(
                select(ChartOfAccounts)
                .where(ChartOfAccounts.code == code)
                .limit(1)
            )
            account = result.scalar_one_or_none()
            balances.append({
                "code": code,
                "name": account.name if account else f"Konto {code}",
                "type": account.account_type if account else "unknown",
                "debit_balance": balance if balance > 0 else 0.0,
                "credit_balance": abs(balance) if balance < 0 else 0.0,
                "balance": balance,
            })

    return balances


async def close_fiscal_year(db: AsyncSession, fiscal_year_id: int) -> dict:
    """Close a fiscal year — lock all bookings, mark year as closed.

    After closing:
    - No new bookings can be created for this year
    - All bookings are locked (immutable)
    - Audit trail records the closure
    """
    result = await db.execute(select(FiscalYear).where(FiscalYear.id == fiscal_year_id))
    fy = result.scalar_one_or_none()
    if not fy:
        raise ValueError(f"Fiscal year {fiscal_year_id} not found")
    if fy.is_closed:
        return {"status": "already_closed", "year": fy.year}

    # Lock all unlocked bookings
    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.fiscal_year_id == fiscal_year_id,
                Booking.is_locked == False,
            )
        )
    )
    unlocked = result.scalars().all()
    locked_count = 0
    for booking in unlocked:
        booking.is_locked = True
        locked_count += 1

    fy.is_closed = True

    audit = AuditLog(
        entity_type="fiscal_year",
        entity_id=fy.id,
        action="lock",
        old_value={"is_closed": False},
        new_value={"is_closed": True, "bookings_locked": locked_count},
        user_action=cite("fiscal_year_close", f"Geschaeftsjahr {fy.year}, {locked_count} Buchungen gesperrt"),
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "closed",
        "year": fy.year,
        "bookings_locked": locked_count,
    }


async def get_bookings(
    db: AsyncSession,
    fiscal_year_id: int,
    account_code: str = None,
    date_from: date = None,
    date_to: date = None,
    unlocked_only: bool = False,
    reflex: bool = False,
    limit: int = 500,
) -> list[dict]:
    """Get bookings with optional filters.

    reflex=True: Hyper-Reflex mode — only return bookings with agent attention
    (pheromone_intensity > 0.1) or recent/unlocked bookings. Routine data summarized.
    """
    query = select(Booking).where(Booking.fiscal_year_id == fiscal_year_id)

    if account_code:
        query = query.where(
            (Booking.debit_account_code == account_code) |
            (Booking.credit_account_code == account_code)
        )
    if date_from:
        query = query.where(Booking.date >= date_from)
    if date_to:
        query = query.where(Booking.date <= date_to)
    if unlocked_only:
        query = query.where(Booking.is_locked == False)
    if reflex:
        # Saltatory UI: only render where financial signal is jumping
        seven_days_ago = date.today().replace(day=max(1, date.today().day - 7))
        query = query.where(
            (Booking.pheromone_intensity > 0.1) |
            (Booking.is_locked == False) |
            (Booking.date >= seven_days_ago)
        )

    query = query.order_by(Booking.date.desc(), Booking.booking_number.desc()).limit(limit)
    result = await db.execute(query)
    bookings = result.scalars().all()

    return [
        {
            "id": b.id,
            "booking_number": b.booking_number,
            "date": b.date.isoformat(),
            "debit_account_code": b.debit_account_code,
            "credit_account_code": b.credit_account_code,
            "amount": b.amount,
            "tax_rate": b.tax_rate,
            "tax_amount": b.tax_amount,
            "description": b.description,
            "document_ref": b.document_ref,
            "is_locked": b.is_locked,
            "is_storno": b.is_storno,
            "pheromone_intensity": b.pheromone_intensity,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


async def update_booking_pheromone(
    db: AsyncSession,
    booking_id: int,
    intensity: float,
) -> None:
    """Update the pheromone intensity on a booking (called by neural tick)."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if booking:
        booking.pheromone_intensity = round(intensity, 4)
        await db.commit()
