"""USt-Voranmeldung — Umsatzsteuer-Voranmeldung (VAT pre-registration).

Calculates Kennzahlen for the ELSTER submission form.
Integrates with the Apoptosis Kill Switch — if agent consensus
on tax calculations drops below 99.5%, filing is self-terminated.
"""
from datetime import date, datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    Booking, FiscalYear, UStVoranmeldung, AuditLog, ApoptosisLog,
)
from backend.config import settings
from backend.accounting.legal_citations import cite


# Tax rate to Kennzahl mapping
TAX_RATE_KZ = {
    0.19: {"revenue_kz": "81", "tax_kz": "36"},  # 19% USt
    0.07: {"revenue_kz": "86", "tax_kz": "35"},  # 7% USt
}

# Account code ranges for VSt (input tax / Vorsteuer)
VST_ACCOUNTS = {"1571", "1576", "1577", "1578"}  # SKR03 Vorsteuer accounts
UST_REVENUE_19 = {"8300", "8400"}  # SKR03 Revenue 19%
UST_REVENUE_07 = {"8000"}  # SKR03 Revenue 7%
UST_REVENUE_FREE = {"8100"}  # Steuerfreie Umsaetze
UST_INTRACOMMUNITY = {"8125", "8130"}  # Innergemeinschaftliche Lieferungen


async def calculate_ust_va(
    db: AsyncSession,
    year: int,
    month: int,
) -> dict:
    """Calculate USt-Voranmeldung for a given period.

    Returns dict with all Kennzahlen ready for ELSTER form.
    """
    # Get bookings for the period
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.date >= period_start,
                Booking.date < period_end,
            )
        )
    )
    bookings = result.scalars().all()

    # Calculate revenue by tax rate
    revenue_19 = 0.0  # Netto revenue at 19%
    revenue_07 = 0.0  # Netto revenue at 7%
    revenue_free = 0.0  # Steuerfreie Umsaetze
    revenue_intracommunity = 0.0  # Innergemeinschaftliche Lieferungen
    vorsteuer = 0.0  # Input tax (Vorsteuer)
    ust_19 = 0.0  # Output tax 19%
    ust_07 = 0.0  # Output tax 7%

    for b in bookings:
        if b.is_storno:
            multiplier = -1.0
        else:
            multiplier = 1.0

        # Revenue accounts (credit side = income)
        if b.credit_account_code in UST_REVENUE_19:
            revenue_19 += b.amount * multiplier
            ust_19 += b.tax_amount * multiplier
        elif b.credit_account_code in UST_REVENUE_07:
            revenue_07 += b.amount * multiplier
            ust_07 += b.tax_amount * multiplier
        elif b.credit_account_code in UST_REVENUE_FREE:
            revenue_free += b.amount * multiplier
        elif b.credit_account_code in UST_INTRACOMMUNITY:
            revenue_intracommunity += b.amount * multiplier

        # Also check debit side for revenue (storno bookings reverse debit/credit)
        if b.debit_account_code in UST_REVENUE_19:
            revenue_19 -= b.amount * multiplier
            ust_19 -= b.tax_amount * multiplier
        elif b.debit_account_code in UST_REVENUE_07:
            revenue_07 -= b.amount * multiplier
            ust_07 -= b.tax_amount * multiplier

        # Vorsteuer (input tax) — debit to VSt account
        if b.debit_account_code in VST_ACCOUNTS:
            vorsteuer += b.tax_amount * multiplier
        if b.credit_account_code in VST_ACCOUNTS:
            vorsteuer -= b.tax_amount * multiplier

    # KZ 83: Zahllast = USt - VSt
    zahllast = round(ust_19 + ust_07 - vorsteuer, 2)

    return {
        "period_year": year,
        "period_month": month,
        "period_label": f"{month:02d}/{year}",
        "kennzahlen": {
            "81": round(revenue_19, 2),   # Steuerpflichtige Umsaetze 19% (Bemessungsgrundlage)
            "86": round(revenue_07, 2),    # Steuerpflichtige Umsaetze 7%
            "36": round(ust_19, 2),        # USt auf KZ81
            "35": round(ust_07, 2),        # USt auf KZ86
            "66": round(vorsteuer, 2),     # Abziehbare Vorsteuer
            "83": zahllast,                # Verbleibende USt-Vorauszahlung
            "61": round(revenue_free, 2),  # Steuerfreie Umsaetze mit Vorsteuerabzug
            "45": round(revenue_intracommunity, 2),  # Innergemeinschaftliche Lieferungen
        },
        "summary": {
            "total_revenue_netto": round(revenue_19 + revenue_07 + revenue_free, 2),
            "total_ust": round(ust_19 + ust_07, 2),
            "total_vorsteuer": round(vorsteuer, 2),
            "zahllast": zahllast,
            "direction": "Zahllast" if zahllast > 0 else "Erstattung",
        },
        "booking_count": len(bookings),
    }


async def save_ust_va(
    db: AsyncSession,
    data: dict,
    consensus_score: float = 1.0,
) -> UStVoranmeldung:
    """Persist USt-VA calculation to database.

    Includes apoptosis check — if consensus < threshold, filing is killed.
    """
    kz = data["kennzahlen"]

    # Check for existing
    result = await db.execute(
        select(UStVoranmeldung).where(
            and_(
                UStVoranmeldung.period_year == data["period_year"],
                UStVoranmeldung.period_month == data["period_month"],
            )
        )
    )
    existing = result.scalar_one_or_none()

    # Apoptosis check
    threshold = settings.apoptosis_threshold_ust_va
    if consensus_score < threshold:
        # KILL SWITCH — self-terminate this filing
        apoptosis = ApoptosisLog(
            entity_type="ust_va",
            entity_id=existing.id if existing else 0,
            trigger_reason=(
                f"{cite('apoptosis_ust_va')} | "
                f"Agent consensus {consensus_score:.3f} below threshold {threshold:.3f}. "
                f"USt-VA for {data['period_month']:02d}/{data['period_year']} terminated."
            ),
            consensus_score=consensus_score,
            threshold_required=threshold,
            agents_involved=["tax_optimizer", "fraud_detector", "bookkeeping_engine"],
        )
        db.add(apoptosis)

        if existing:
            existing.status = "apoptosed"
            existing.apoptosis_reason = apoptosis.trigger_reason
            existing.consensus_score = consensus_score
        else:
            existing = UStVoranmeldung(
                period_year=data["period_year"],
                period_month=data["period_month"],
                kennzahl_81=kz.get("81", 0),
                kennzahl_86=kz.get("86", 0),
                kennzahl_36=kz.get("36", 0),
                kennzahl_35=kz.get("35", 0),
                kennzahl_66=kz.get("66", 0),
                kennzahl_83=kz.get("83", 0),
                kennzahl_61=kz.get("61", 0),
                kennzahl_45=kz.get("45", 0),
                consensus_score=consensus_score,
                status="apoptosed",
                apoptosis_reason=apoptosis.trigger_reason,
            )
            db.add(existing)

        await db.commit()
        return existing

    # Normal save
    if existing:
        existing.kennzahl_81 = kz.get("81", 0)
        existing.kennzahl_86 = kz.get("86", 0)
        existing.kennzahl_36 = kz.get("36", 0)
        existing.kennzahl_35 = kz.get("35", 0)
        existing.kennzahl_66 = kz.get("66", 0)
        existing.kennzahl_83 = kz.get("83", 0)
        existing.kennzahl_61 = kz.get("61", 0)
        existing.kennzahl_45 = kz.get("45", 0)
        existing.consensus_score = consensus_score
        existing.status = "draft"
    else:
        existing = UStVoranmeldung(
            period_year=data["period_year"],
            period_month=data["period_month"],
            kennzahl_81=kz.get("81", 0),
            kennzahl_86=kz.get("86", 0),
            kennzahl_36=kz.get("36", 0),
            kennzahl_35=kz.get("35", 0),
            kennzahl_66=kz.get("66", 0),
            kennzahl_83=kz.get("83", 0),
            kennzahl_61=kz.get("61", 0),
            kennzahl_45=kz.get("45", 0),
            consensus_score=consensus_score,
        )
        db.add(existing)

    audit = AuditLog(
        entity_type="ust_va",
        entity_id=existing.id if existing.id else 0,
        action="create",
        new_value=kz,
        user_action=f"USt-VA {data['period_month']:02d}/{data['period_year']} calculated",
    )
    db.add(audit)
    await db.commit()
    return existing


def generate_elster_xml_stub(data: dict) -> str:
    """Generate ELSTER XML structure (stub — not actual submission).

    Real ELSTER submission requires ERiC (ELSTER Rich Client) library
    and certified interface. This generates the XML structure for reference.
    """
    kz = data["kennzahlen"]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- ELSTER XML Stub — NOT for actual submission -->
<!-- Real submission requires ERiC (ELSTER Rich Client) -->
<Elster xmlns="http://www.elster.de/elsterxml/schema/v11">
  <TransferHeader>
    <Verfahren>ElsterAnmeldung</Verfahren>
    <DatenArt>UStVA</DatenArt>
    <Vorgang>send</Vorgang>
  </TransferHeader>
  <DatenTeil>
    <Nutzdatenblock>
      <Nutzdaten>
        <Anmeldungssteuern art="UStVA" version="202601">
          <Zeitraum>
            <Jahr>{data['period_year']}</Jahr>
            <Zeitraum>{data['period_month']:02d}</Zeitraum>
          </Zeitraum>
          <Kz81>{kz.get('81', 0):.2f}</Kz81>
          <Kz86>{kz.get('86', 0):.2f}</Kz86>
          <Kz36>{kz.get('36', 0):.2f}</Kz36>
          <Kz35>{kz.get('35', 0):.2f}</Kz35>
          <Kz66>{kz.get('66', 0):.2f}</Kz66>
          <Kz83>{kz.get('83', 0):.2f}</Kz83>
          <Kz61>{kz.get('61', 0):.2f}</Kz61>
          <Kz45>{kz.get('45', 0):.2f}</Kz45>
        </Anmeldungssteuern>
      </Nutzdaten>
    </Nutzdatenblock>
  </DatenTeil>
</Elster>"""
