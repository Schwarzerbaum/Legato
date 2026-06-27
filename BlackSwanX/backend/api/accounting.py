"""Accounting API Router — Bookkeeping, invoices, EUeR, USt-VA.

The organism's financial management endpoints.
"""
from datetime import date
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.accounting.bookkeeping import (
    BookingEntry, create_booking, lock_booking, create_storno,
    get_or_create_fiscal_year, close_fiscal_year,
)
from backend.accounting.invoice import (
    InvoiceLineItem, create_invoice, update_invoice_status,
    render_invoice_html, get_invoices,
)
from backend.accounting.euer import calculate_euer, generate_euer_report
from backend.accounting.ust_va import calculate_ust_va, save_ust_va, generate_elster_xml_stub

router = APIRouter()


# ── REQUEST MODELS ───────────────────────────────────────────

class BookingCreate(BaseModel):
    debit_code: str
    credit_code: str
    amount: float
    booking_date: str  # ISO format
    description: str = ""
    tax_rate: float = 0.0
    document_ref: str = ""

class InvoiceCreate(BaseModel):
    customer_name: str
    customer_address: str = ""
    customer_ust_id: str = ""
    seller_name: str = ""
    seller_address: str = ""
    seller_ust_id: str = ""
    seller_steuernummer: str = ""
    invoice_date: Optional[str] = None
    service_date: Optional[str] = None
    due_date: Optional[str] = None
    line_items: list[dict]  # [{description, quantity, unit_price, tax_rate}]

class StatusUpdate(BaseModel):
    status: str
    payment_date: Optional[str] = None

class FiscalYearCreate(BaseModel):
    year: int


# ── BOOKINGS ─────────────────────────────────────────────────

@router.post("/booking")
async def api_create_booking(data: BookingCreate, db: AsyncSession = Depends(get_db)):
    """Create a new double-entry booking (GoBD compliant)."""
    try:
        entry = BookingEntry(
            debit_code=data.debit_code,
            credit_code=data.credit_code,
            amount=data.amount,
            booking_date=date.fromisoformat(data.booking_date),
            description=data.description,
            tax_rate=data.tax_rate,
            document_ref=data.document_ref,
        )
        booking = await create_booking(db, entry)
        return {
            "id": booking.id,
            "booking_number": booking.booking_number,
            "status": "created",
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/booking/{booking_id}/lock")
async def api_lock_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    """Lock a booking — makes it immutable per GoBD."""
    try:
        booking = await lock_booking(db, booking_id)
        return {"id": booking.id, "is_locked": booking.is_locked}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/booking/{booking_id}/storno")
async def api_storno_booking(booking_id: int, reason: str = "", db: AsyncSession = Depends(get_db)):
    """Create a Stornobuchung (reverse booking) — GoBD correction method."""
    try:
        storno = await create_storno(db, booking_id, reason)
        return {
            "id": storno.id,
            "booking_number": storno.booking_number,
            "is_storno": True,
            "storno_of_id": storno.storno_of_id,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── INVOICES ─────────────────────────────────────────────────

@router.post("/invoice")
async def api_create_invoice(data: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    """Create a section 14 UStG compliant invoice."""
    try:
        items = [
            InvoiceLineItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0),
                tax_rate=item.get("tax_rate", 0.19),
            )
            for item in data.line_items
        ]
        invoice = await create_invoice(
            db,
            customer_name=data.customer_name,
            line_items=items,
            invoice_date=date.fromisoformat(data.invoice_date) if data.invoice_date else None,
            service_date=date.fromisoformat(data.service_date) if data.service_date else None,
            due_date=date.fromisoformat(data.due_date) if data.due_date else None,
            seller_name=data.seller_name,
            seller_address=data.seller_address,
            seller_ust_id=data.seller_ust_id,
            seller_steuernummer=data.seller_steuernummer,
            customer_address=data.customer_address,
            customer_ust_id=data.customer_ust_id,
        )
        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "total": invoice.total,
            "status": invoice.status,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/invoices")
async def api_list_invoices(
    status: str = None,
    year: int = None,
    db: AsyncSession = Depends(get_db),
):
    """List invoices with optional filters."""
    return await get_invoices(db, status=status, year=year)


@router.get("/invoice/{invoice_id}/html")
async def api_invoice_html(invoice_id: int, db: AsyncSession = Depends(get_db)):
    """Get rendered HTML for an invoice."""
    from sqlalchemy import select
    from backend.database.models import Invoice
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(render_invoice_html(invoice))


@router.put("/invoice/{invoice_id}/status")
async def api_update_invoice_status(
    invoice_id: int,
    data: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update invoice status."""
    try:
        invoice = await update_invoice_status(
            db, invoice_id, data.status,
            payment_date=date.fromisoformat(data.payment_date) if data.payment_date else None,
        )
        return {"id": invoice.id, "status": invoice.status}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── EUER ─────────────────────────────────────────────────────

@router.get("/euer/{fiscal_year_id}")
async def api_euer(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Calculate EUeR for a fiscal year."""
    try:
        return await calculate_euer(db, fiscal_year_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/euer/{fiscal_year_id}/report")
async def api_euer_report(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Generate markdown EUeR report."""
    try:
        report = await generate_euer_report(db, fiscal_year_id)
        return {"report_md": report}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── UST-VORANMELDUNG ────────────────────────────────────────

@router.get("/ust-va/{year}/{month}")
async def api_ust_va(year: int, month: int, db: AsyncSession = Depends(get_db)):
    """Calculate USt-Voranmeldung for a period."""
    if month < 1 or month > 12:
        raise HTTPException(400, "Month must be 1-12")
    return await calculate_ust_va(db, year, month)


@router.post("/ust-va/{year}/{month}/save")
async def api_save_ust_va(
    year: int,
    month: int,
    consensus_score: float = 1.0,
    db: AsyncSession = Depends(get_db),
):
    """Save USt-VA calculation. Triggers apoptosis check."""
    data = await calculate_ust_va(db, year, month)
    ust_va = await save_ust_va(db, data, consensus_score)
    return {
        "id": ust_va.id,
        "status": ust_va.status,
        "consensus_score": ust_va.consensus_score,
        "apoptosis_reason": ust_va.apoptosis_reason,
        "kennzahlen": data["kennzahlen"],
    }


@router.get("/elster-stub/{year}/{month}")
async def api_elster_stub(year: int, month: int, db: AsyncSession = Depends(get_db)):
    """Generate ELSTER XML stub (not for actual submission)."""
    data = await calculate_ust_va(db, year, month)
    xml = generate_elster_xml_stub(data)
    from fastapi.responses import Response
    return Response(content=xml, media_type="application/xml")


# ── RECEIPT SCANNING ─────────────────────────────────────────

@router.post("/receipt/scan")
async def api_scan_receipt(text: str = "", db: AsyncSession = Depends(get_db)):
    """Auto-categorize a transaction description via LLM."""
    try:
        from backend.accounting.receipt_scanner import auto_categorize_booking
        result = await auto_categorize_booking(text, 0.0)
        return result
    except Exception as e:
        return {"error": str(e), "confidence": 0.0}


# ── FISCAL YEAR MANAGEMENT ───────────────────────────────────

@router.post("/fiscal-year")
async def api_create_fiscal_year(data: FiscalYearCreate, db: AsyncSession = Depends(get_db)):
    """Create a new fiscal year."""
    fy = await get_or_create_fiscal_year(db, data.year)
    return {"id": fy.id, "year": fy.year}


@router.post("/fiscal-year/{fiscal_year_id}/close")
async def api_close_fiscal_year(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Close a fiscal year — locks all bookings."""
    try:
        return await close_fiscal_year(db, fiscal_year_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
