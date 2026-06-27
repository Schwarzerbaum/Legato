"""DATEV API Router — Import, analysis, and financial intelligence.

Endpoints for:
- DATEV file import (CSV/ASCII)
- Booking management
- Chart of accounts
- Trial balance
- Financial AI analysis (fraud, tax optimization, cashflow, audit risk)
"""
from datetime import date
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.db import get_db
from backend.database.models import ChartOfAccounts, FiscalYear
from backend.accounting.datev_parser import import_datev_to_db
from backend.accounting.bookkeeping import (
    get_bookings, get_trial_balance, get_or_create_fiscal_year,
)
from backend.accounting.skr import seed_chart_of_accounts
from backend.config import settings

router = APIRouter()


# ── CHART OF ACCOUNTS ────────────────────────────────────────

@router.get("/accounts")
async def list_accounts(variant: str = "SKR03", db: AsyncSession = Depends(get_db)):
    """List all accounts in the chart of accounts."""
    result = await db.execute(
        select(ChartOfAccounts)
        .where(ChartOfAccounts.skr_variant == variant)
        .order_by(ChartOfAccounts.code)
    )
    accounts = result.scalars().all()

    # Auto-seed if empty
    if not accounts:
        await seed_chart_of_accounts(db, variant)
        result = await db.execute(
            select(ChartOfAccounts)
            .where(ChartOfAccounts.skr_variant == variant)
            .order_by(ChartOfAccounts.code)
        )
        accounts = result.scalars().all()

    return [
        {
            "code": a.code,
            "name": a.name,
            "type": a.account_type,
            "variant": a.skr_variant,
            "tax_relevant": a.tax_relevant,
        }
        for a in accounts
    ]


# ── DATEV IMPORT ─────────────────────────────────────────────

@router.post("/import")
async def import_datev(
    file: UploadFile = File(...),
    fiscal_year: int = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload and import a DATEV CSV or ASCII file."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    # Ensure chart of accounts is seeded
    result = await db.execute(select(ChartOfAccounts).limit(1))
    if not result.scalar_one_or_none():
        await seed_chart_of_accounts(db, settings.default_skr_variant)

    try:
        result = await import_datev_to_db(db, content, fiscal_year)
        return result
    except Exception as e:
        raise HTTPException(400, str(e))


# ── BOOKINGS ─────────────────────────────────────────────────

@router.get("/bookings")
async def list_bookings(
    fiscal_year_id: int = None,
    account_code: str = None,
    date_from: str = None,
    date_to: str = None,
    reflex: bool = False,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
):
    """List bookings with optional filters.

    reflex=True: Hyper-Reflex mode — only returns bookings with agent attention.
    """
    if fiscal_year_id is None:
        # Default to current year
        fy = await get_or_create_fiscal_year(db, date.today().year)
        fiscal_year_id = fy.id

    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None

    return await get_bookings(
        db, fiscal_year_id,
        account_code=account_code,
        date_from=d_from,
        date_to=d_to,
        reflex=reflex,
        limit=limit,
    )


# ── TRIAL BALANCE ────────────────────────────────────────────

@router.get("/trial-balance/{fiscal_year_id}")
async def trial_balance(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Get trial balance (Saldenliste) for a fiscal year."""
    try:
        return await get_trial_balance(db, fiscal_year_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── FINANCIAL AI ANALYSIS ────────────────────────────────────

@router.post("/analyze/{fiscal_year_id}")
async def run_analysis(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Run all 5 financial AI agents against bookkeeping data."""
    try:
        from backend.accounting.analysis import run_full_financial_analysis
        return await run_full_financial_analysis(db, fiscal_year_id)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/fraud-scan/{fiscal_year_id}")
async def fraud_scan(fiscal_year_id: int, db: AsyncSession = Depends(get_db)):
    """Run standalone fraud detection (Benford + duplicates + LLM)."""
    try:
        from backend.accounting.analysis import run_fraud_scan
        return await run_fraud_scan(db, fiscal_year_id)
    except Exception as e:
        raise HTTPException(500, f"Fraud scan failed: {str(e)}")


# ── FISCAL YEARS ─────────────────────────────────────────────

@router.get("/fiscal-years")
async def list_fiscal_years(db: AsyncSession = Depends(get_db)):
    """List all fiscal years."""
    result = await db.execute(select(FiscalYear).order_by(FiscalYear.year.desc()))
    years = result.scalars().all()
    return [
        {
            "id": fy.id,
            "year": fy.year,
            "start_date": fy.start_date.isoformat(),
            "end_date": fy.end_date.isoformat(),
            "is_closed": fy.is_closed,
        }
        for fy in years
    ]


# ── PAYROLL ANALYSIS ────────────────────────────────────────────

@router.post("/payroll-analysis")
async def payroll_analysis(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload payroll CSV and run compliance analysis.

    Accepts DATEV Lohn & Gehalt CSV exports.  Runs statistical checks
    (overtime, Mindestlohn, Minijob, sick-leave patterns, Geldwerter
    Vorteil) plus LLM-powered expert review.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    from backend.accounting.payroll import parse_payroll_csv, run_payroll_analysis

    employees = parse_payroll_csv(content)
    if not employees:
        raise HTTPException(400, "No employee data found in CSV")

    result = await run_payroll_analysis(employees)
    return result


# ── SAMPLE DATA ─────────────────────────────────────────────────

@router.get("/sample-data/{data_type}")
async def get_sample_data(data_type: str):
    """Get sample DATEV/payroll/bank data for testing.

    Supported types: datev, payroll, bank
    """
    from backend.accounting.sample_data import (
        generate_sample_datev_csv,
        generate_sample_payroll_csv,
        generate_sample_bank_csv,
    )
    from fastapi.responses import Response

    generators = {
        "datev": (generate_sample_datev_csv, "sample_datev.csv"),
        "payroll": (generate_sample_payroll_csv, "sample_payroll.csv"),
        "bank": (generate_sample_bank_csv, "sample_bank.csv"),
    }

    if data_type not in generators:
        raise HTTPException(
            400,
            f"Unknown data type: {data_type}. Use: datev, payroll, bank",
        )

    gen_func, filename = generators[data_type]
    csv_content = gen_func()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
