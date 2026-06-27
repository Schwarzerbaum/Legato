"""Invoice generator — Section 14 UStG compliant.

Required fields per section 14 UStG:
  1. Vollstaendiger Name und Anschrift des leistenden Unternehmers
  2. Vollstaendiger Name und Anschrift des Leistungsempfaengers
  3. Steuernummer oder USt-IdNr des leistenden Unternehmers
  4. Ausstellungsdatum (Rechnungsdatum)
  5. Fortlaufende Rechnungsnummer (sequential, no gaps)
  6. Menge und Art der Lieferung/Leistung
  7. Zeitpunkt der Lieferung/Leistung (Leistungsdatum)
  8. Entgelt (Nettobetrag)
  9. Steuersatz und Steuerbetrag (or Hinweis auf Steuerbefreiung)
  10. Im Voraus vereinbarte Minderungen (Skonti, Rabatte)
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Invoice, AuditLog
from backend.accounting.legal_citations import cite


class InvoiceLineItem:
    """A single line item on an invoice."""
    def __init__(
        self,
        description: str,
        quantity: float,
        unit_price: float,
        tax_rate: float = 0.19,
        unit: str = "Stk.",
    ):
        self.description = description
        self.quantity = quantity
        self.unit_price = round(unit_price, 2)
        self.unit = unit
        self.tax_rate = tax_rate
        self.net_amount = round(quantity * unit_price, 2)
        self.tax_amount = round(self.net_amount * tax_rate, 2)
        self.gross_amount = round(self.net_amount + self.tax_amount, 2)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "tax_rate": self.tax_rate,
            "net_amount": self.net_amount,
            "tax_amount": self.tax_amount,
            "gross_amount": self.gross_amount,
        }


async def get_next_invoice_number(db: AsyncSession, year: int) -> str:
    """Generate next sequential invoice number. Format: RE-{year}-{NNNN}.

    GoBD: Numbers must be sequential with no gaps within a year.
    """
    prefix = f"RE-{year}-"
    result = await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.invoice_number.like(f"{prefix}%"))
    )
    count = result.scalar_one()
    return f"{prefix}{count + 1:04d}"


async def create_invoice(
    db: AsyncSession,
    customer_name: str,
    line_items: list[InvoiceLineItem],
    invoice_date: date = None,
    service_date: date = None,
    due_date: date = None,
    seller_name: str = "",
    seller_address: str = "",
    seller_ust_id: str = "",
    seller_steuernummer: str = "",
    seller_tax_id: str = "",
    customer_address: str = "",
    customer_ust_id: str = "",
) -> Invoice:
    """Create a section 14 UStG compliant invoice."""
    if not line_items:
        raise ValueError("Invoice must have at least one line item")
    if not customer_name:
        raise ValueError("Customer name is required (section 14 UStG)")
    if not seller_steuernummer and not seller_ust_id:
        raise ValueError("Seller Steuernummer or USt-IdNr required (section 14 UStG)")

    inv_date = invoice_date or date.today()
    inv_number = await get_next_invoice_number(db, inv_date.year)

    subtotal = round(sum(item.net_amount for item in line_items), 2)
    tax_total = round(sum(item.tax_amount for item in line_items), 2)
    total = round(subtotal + tax_total, 2)

    invoice = Invoice(
        invoice_number=inv_number,
        date=inv_date,
        service_date=service_date or inv_date,
        due_date=due_date,
        seller_name=seller_name,
        seller_address=seller_address,
        seller_ust_id=seller_ust_id,
        seller_steuernummer=seller_steuernummer,
        seller_tax_id=seller_tax_id,
        customer_name=customer_name,
        customer_address=customer_address,
        customer_ust_id=customer_ust_id,
        line_items=[item.to_dict() for item in line_items],
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
    )
    db.add(invoice)
    await db.flush()

    audit = AuditLog(
        entity_type="invoice",
        entity_id=invoice.id,
        action="create",
        old_value=None,
        new_value={
            "invoice_number": inv_number,
            "customer": customer_name,
            "total": total,
        },
        user_action=f"{cite('invoice_create', inv_number)} | {cite('invoice_sequential', inv_number)}",
    )
    db.add(audit)
    await db.commit()
    return invoice


async def update_invoice_status(
    db: AsyncSession,
    invoice_id: int,
    status: str,
    payment_date: date = None,
) -> Invoice:
    """Update invoice status (draft -> sent -> paid / overdue)."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    old_status = invoice.status
    invoice.status = status
    if payment_date:
        invoice.payment_date = payment_date

    audit = AuditLog(
        entity_type="invoice",
        entity_id=invoice.id,
        action="modify",
        old_value={"status": old_status},
        new_value={"status": status},
        user_action=f"Invoice {invoice.invoice_number} status: {old_status} -> {status}",
    )
    db.add(audit)
    await db.commit()
    return invoice


def render_invoice_html(invoice: Invoice) -> str:
    """Render invoice as section 14 UStG compliant HTML."""
    items_html = ""
    for item in (invoice.line_items or []):
        items_html += f"""
        <tr>
            <td>{item.get('description', '')}</td>
            <td class="right">{item.get('quantity', 0):.2f} {item.get('unit', 'Stk.')}</td>
            <td class="right">{item.get('unit_price', 0):.2f} EUR</td>
            <td class="right">{item.get('tax_rate', 0)*100:.0f}%</td>
            <td class="right">{item.get('net_amount', 0):.2f} EUR</td>
        </tr>"""

    # Group tax rates for summary
    tax_groups: dict[float, float] = {}
    for item in (invoice.line_items or []):
        rate = item.get("tax_rate", 0)
        tax_groups[rate] = tax_groups.get(rate, 0) + item.get("tax_amount", 0)

    tax_summary = ""
    for rate, amount in sorted(tax_groups.items()):
        if rate > 0:
            tax_summary += f"<p>USt {rate*100:.0f}%: {amount:.2f} EUR</p>\n"
        else:
            tax_summary += "<p>Umsatzsteuerbefreit gem. § 19 UStG (Kleinunternehmerregelung)</p>\n"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Rechnung {invoice.invoice_number}</title>
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; color: #222; margin: 40px; }}
  .header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
  .seller {{ font-size: 9pt; }}
  .customer {{ margin: 30px 0; }}
  .meta {{ margin: 20px 0; }}
  .meta table {{ border-collapse: collapse; }}
  .meta td {{ padding: 3px 15px 3px 0; }}
  .meta .label {{ font-weight: bold; }}
  table.items {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
  table.items th {{ text-align: left; border-bottom: 2px solid #333; padding: 8px 5px; font-size: 9pt; }}
  table.items td {{ padding: 6px 5px; border-bottom: 1px solid #ddd; }}
  .right {{ text-align: right; }}
  .totals {{ margin-top: 10px; text-align: right; }}
  .totals .total {{ font-size: 14pt; font-weight: bold; margin-top: 10px; }}
  .footer {{ margin-top: 60px; font-size: 8pt; color: #666; border-top: 1px solid #ccc; padding-top: 10px; }}
</style>
</head>
<body>

<div class="header">
  <div class="seller">
    <strong>{invoice.seller_name or 'Rechnungssteller'}</strong><br>
    {(invoice.seller_address or '').replace(chr(10), '<br>')}
  </div>
</div>

<div class="customer">
  <strong>{invoice.customer_name}</strong><br>
  {(invoice.customer_address or '').replace(chr(10), '<br>')}
</div>

<div class="meta">
  <table>
    <tr><td class="label">Rechnungsnummer:</td><td>{invoice.invoice_number}</td></tr>
    <tr><td class="label">Rechnungsdatum:</td><td>{invoice.date.strftime('%d.%m.%Y') if invoice.date else ''}</td></tr>
    <tr><td class="label">Leistungsdatum:</td><td>{invoice.service_date.strftime('%d.%m.%Y') if invoice.service_date else ''}</td></tr>
    {'<tr><td class="label">Faellig bis:</td><td>' + invoice.due_date.strftime('%d.%m.%Y') + '</td></tr>' if invoice.due_date else ''}
    {'<tr><td class="label">USt-IdNr.:</td><td>' + invoice.seller_ust_id + '</td></tr>' if invoice.seller_ust_id else ''}
    {'<tr><td class="label">Steuernummer:</td><td>' + invoice.seller_steuernummer + '</td></tr>' if invoice.seller_steuernummer else ''}
  </table>
</div>

<h2>Rechnung</h2>

<table class="items">
  <thead>
    <tr>
      <th>Beschreibung</th>
      <th class="right">Menge</th>
      <th class="right">Einzelpreis</th>
      <th class="right">USt</th>
      <th class="right">Netto</th>
    </tr>
  </thead>
  <tbody>
    {items_html}
  </tbody>
</table>

<div class="totals">
  <p>Nettobetrag: {invoice.subtotal:.2f} EUR</p>
  {tax_summary}
  <p class="total">Gesamtbetrag: {invoice.total:.2f} EUR</p>
</div>

{'<p>Bitte ueberweisen Sie den Betrag bis zum ' + invoice.due_date.strftime("%d.%m.%Y") + '.</p>' if invoice.due_date else ''}

<div class="footer">
  <p>{invoice.seller_name or ''} | {invoice.seller_steuernummer or invoice.seller_ust_id or ''}</p>
</div>

</body>
</html>"""


async def get_invoices(
    db: AsyncSession,
    status: str = None,
    year: int = None,
    limit: int = 100,
) -> list[dict]:
    """List invoices with optional filters."""
    query = select(Invoice)
    if status:
        query = query.where(Invoice.status == status)
    if year:
        query = query.where(Invoice.date >= date(year, 1, 1))
        query = query.where(Invoice.date <= date(year, 12, 31))
    query = query.order_by(Invoice.date.desc()).limit(limit)

    result = await db.execute(query)
    invoices = result.scalars().all()

    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "date": inv.date.isoformat() if inv.date else None,
            "customer_name": inv.customer_name,
            "subtotal": inv.subtotal,
            "tax_total": inv.tax_total,
            "total": inv.total,
            "status": inv.status,
            "line_item_count": len(inv.line_items) if inv.line_items else 0,
        }
        for inv in invoices
    ]
