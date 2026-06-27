"""German Standard Chart of Accounts (Standardkontenrahmen) — SKR03 and SKR04.

Provides the complete account definitions, tax mappings, and EUeR line mappings
for the two most widely used German charts of accounts. SKR03 is organized by
process (Prozessgliederungsprinzip), SKR04 by financial statement structure
(Abschlussgliederungsprinzip).

Usage:
    from backend.accounting.skr import seed_chart_of_accounts, classify_account

    await seed_chart_of_accounts(db, variant="SKR03")
    account_type = classify_account("4200")  # -> "expense"
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ChartOfAccounts


# ---------------------------------------------------------------------------
# SKR03 — Prozessgliederungsprinzip (~100 most-used accounts)
# ---------------------------------------------------------------------------

SKR03_ACCOUNTS: list[dict] = [
    # ── Class 0: Anlagevermoegen (Fixed Assets) ────────────────────────
    {"code": "0027", "name": "EDV-Software", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0200", "name": "Maschinen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0210", "name": "Maschinen (beweglich)", "type": "asset", "parent_code": "0200", "tax_relevant": False},
    {"code": "0300", "name": "Fahrzeuge", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0320", "name": "PKW", "type": "asset", "parent_code": "0300", "tax_relevant": False},
    {"code": "0350", "name": "LKW", "type": "asset", "parent_code": "0300", "tax_relevant": False},
    {"code": "0400", "name": "Betriebs- und Geschaeftsausstattung", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0410", "name": "Geschaeftsausstattung", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0420", "name": "Bueroeinrichtung", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0440", "name": "Ladeneinrichtung", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0480", "name": "Geringwertige Wirtschaftsgueter (GWG)", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0500", "name": "Darlehen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0520", "name": "Kautionen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0620", "name": "Grundstuecke und Bauten", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0650", "name": "Buerogebaeude", "type": "asset", "parent_code": "0620", "tax_relevant": False},

    # ── Class 1: Umlaufvermoegen / Finanzkonten (Current Assets / Finance) ─
    {"code": "1000", "name": "Kasse", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1200", "name": "Bank", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1210", "name": "Bank 2", "type": "asset", "parent_code": "1200", "tax_relevant": False},
    {"code": "1300", "name": "Wechsel", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1360", "name": "Geldtransit", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1400", "name": "Forderungen aus Lieferungen und Leistungen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1410", "name": "Forderungen aus Lieferungen und Leistungen ohne Kontokorrent", "type": "asset", "parent_code": "1400", "tax_relevant": False},
    {"code": "1450", "name": "Forderungen nach 14 Abs. 2 Satz 2 UStG", "type": "asset", "parent_code": "1400", "tax_relevant": True},
    {"code": "1500", "name": "Sonstige Vermoegensgegenstande", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1518", "name": "Vorsteuer im Folgejahr abziehbar", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1545", "name": "Umsatzsteuerforderungen", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1548", "name": "Vorsteuer in Folgeperiode abziehbar", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1571", "name": "Abziehbare Vorsteuer 7%", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1576", "name": "Abziehbare Vorsteuer 19%", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1580", "name": "Abziehbare Vorsteuer nach 13b UStG", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "1590", "name": "Durchlaufende Posten", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1600", "name": "Verbindlichkeiten aus Lieferungen und Leistungen", "type": "liability", "parent_code": None, "tax_relevant": False},
    {"code": "1700", "name": "Sonstige Verbindlichkeiten", "type": "liability", "parent_code": None, "tax_relevant": False},
    {"code": "1710", "name": "Erhaltene Anzahlungen", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1740", "name": "Verbindlichkeiten aus Steuern und Abgaben", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1755", "name": "Lohnsteuerverbindlichkeiten", "type": "liability", "parent_code": "1740", "tax_relevant": True},
    {"code": "1771", "name": "Umsatzsteuer 7%", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1773", "name": "Umsatzsteuer aus innergemeinschaftlichem Erwerb", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1776", "name": "Umsatzsteuer 19%", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1780", "name": "Umsatzsteuer-Vorauszahlung", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1789", "name": "Umsatzsteuer laufendes Jahr", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1790", "name": "Umsatzsteuer Vorjahr", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1791", "name": "Umsatzsteuer frueherer Jahre", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "1800", "name": "Privatentnahmen allgemein", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "1810", "name": "Privatsteuern", "type": "equity", "parent_code": "1800", "tax_relevant": False},
    {"code": "1890", "name": "Privateinlagen", "type": "equity", "parent_code": None, "tax_relevant": False},

    # ── Class 2: Abgrenzungskonten (Accruals / Extraordinary) ──────────
    {"code": "2000", "name": "Ausserordentliche Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "2010", "name": "Ausserordentliche Ertraege", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "2100", "name": "Zinsertraege", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "2110", "name": "Zinsaufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "2120", "name": "Zinsaufwendungen fuer kurzfristige Verbindlichkeiten", "type": "expense", "parent_code": "2110", "tax_relevant": True},
    {"code": "2150", "name": "Zinsaufwendungen fuer langfristige Verbindlichkeiten", "type": "expense", "parent_code": "2110", "tax_relevant": True},
    {"code": "2300", "name": "Sonstige Aufwendungen, unregelmaessig", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "2400", "name": "Forderungsverluste", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "2500", "name": "Anlagenabgaenge Sachanlagen (Restbuchwert)", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "2742", "name": "Investitionsabzugsbetraege 7g", "type": "expense", "parent_code": None, "tax_relevant": True},

    # ── Class 3: Wareneingang / Material (Purchases) ──────────────────
    {"code": "3000", "name": "Roh-, Hilfs- und Betriebsstoffe", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3100", "name": "Fremdleistungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3300", "name": "Wareneingang 19%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3400", "name": "Wareneingang 7%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3500", "name": "Wareneingang steuerfrei", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3550", "name": "Leistungen eines im Ausland ansaessigen Unternehmers 19%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3700", "name": "Nachlaesse", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3730", "name": "Erhaltene Skonti 19%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3740", "name": "Erhaltene Skonti 7%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "3800", "name": "Anschaffungsnebenkosten", "type": "expense", "parent_code": None, "tax_relevant": True},

    # ── Class 4: Betriebliche Aufwendungen (Operating Expenses) ───────
    {"code": "4100", "name": "Loehne", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4110", "name": "Loehne (Hilfskraefte)", "type": "expense", "parent_code": "4100", "tax_relevant": True},
    {"code": "4120", "name": "Gehaelter", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4125", "name": "Ehegattengehalt", "type": "expense", "parent_code": "4120", "tax_relevant": True},
    {"code": "4130", "name": "Gesetzliche soziale Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4138", "name": "Beitraege zur Berufsgenossenschaft", "type": "expense", "parent_code": "4130", "tax_relevant": True},
    {"code": "4140", "name": "Freiwillige soziale Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4150", "name": "Vermoegenswirksame Leistungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4170", "name": "Fahrtkostenzuschuesse", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4190", "name": "Aushilfslohne", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4200", "name": "Raumkosten / Miete", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4210", "name": "Strom, Gas, Wasser", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4220", "name": "Heizung", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4230", "name": "Nebenkosten", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4240", "name": "Grundsteuer", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4250", "name": "Reinigung", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4260", "name": "Instandhaltung Raeume", "type": "expense", "parent_code": "4200", "tax_relevant": True},
    {"code": "4300", "name": "Versicherungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4320", "name": "Gewerbeversicherung", "type": "expense", "parent_code": "4300", "tax_relevant": True},
    {"code": "4360", "name": "Kfz-Steuer", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4380", "name": "Kfz-Kosten (allgemein)", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4400", "name": "Reparaturen und Instandhaltung", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4500", "name": "Kfz-Kosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4510", "name": "Kfz-Steuer (Fahrzeuge)", "type": "expense", "parent_code": "4500", "tax_relevant": True},
    {"code": "4520", "name": "Kfz-Versicherung", "type": "expense", "parent_code": "4500", "tax_relevant": True},
    {"code": "4530", "name": "Laufende Kfz-Betriebskosten", "type": "expense", "parent_code": "4500", "tax_relevant": True},
    {"code": "4540", "name": "Kfz-Reparaturen", "type": "expense", "parent_code": "4500", "tax_relevant": True},
    {"code": "4580", "name": "Sonstige Kfz-Kosten", "type": "expense", "parent_code": "4500", "tax_relevant": True},
    {"code": "4600", "name": "Werbekosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4610", "name": "Repraesentationskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4630", "name": "Geschenke abziehbar", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4635", "name": "Geschenke nicht abziehbar", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4640", "name": "Bewirtungskosten (70% abziehbar)", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4650", "name": "Reisekosten Arbeitnehmer", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4654", "name": "Reisekosten Fahrtkosten", "type": "expense", "parent_code": "4650", "tax_relevant": True},
    {"code": "4660", "name": "Reisekosten Uebernachtung", "type": "expense", "parent_code": "4650", "tax_relevant": True},
    {"code": "4663", "name": "Reisekosten Verpflegungsmehraufwand", "type": "expense", "parent_code": "4650", "tax_relevant": True},
    {"code": "4670", "name": "Reisekosten Unternehmer", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4700", "name": "Porto", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4800", "name": "Telefon und Internet", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4806", "name": "Mobilfunkkosten", "type": "expense", "parent_code": "4800", "tax_relevant": True},
    {"code": "4830", "name": "Buechergeld, Zeitschriften", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4855", "name": "Nebenkosten des Geldverkehrs", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4900", "name": "Sonstige betriebliche Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4910", "name": "Burobedarf", "type": "expense", "parent_code": "4900", "tax_relevant": True},
    {"code": "4920", "name": "Fachzeitschriften und Buecher", "type": "expense", "parent_code": "4900", "tax_relevant": True},
    {"code": "4930", "name": "Rechts- und Beratungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4940", "name": "Buchfuehrungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4945", "name": "Abschluss- und Pruefungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4955", "name": "Nebenkosten des Geldverkehrs", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4957", "name": "Saeuamniszuschlaege und Zwangsgelder", "type": "expense", "parent_code": None, "tax_relevant": False},
    {"code": "4970", "name": "Abschreibungen auf Sachanlagen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "4980", "name": "Gewerbesteuer", "type": "expense", "parent_code": None, "tax_relevant": False},

    # ── Class 8: Erloese (Revenue) ────────────────────────────────────
    {"code": "8000", "name": "Erloese 7%", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8100", "name": "Steuerfreie Erloese (Inland)", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8120", "name": "Steuerfreie innergemeinschaftliche Lieferungen", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8125", "name": "Steuerfreie Ausfuhrlieferungen Drittland", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8300", "name": "Erloese 19%", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8400", "name": "Erloese 19% (allgemein)", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8500", "name": "Provisionserloese", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8600", "name": "Erloese Vermietung/Verpachtung", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8700", "name": "Erloese Nebenbetrieb", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8730", "name": "Erhaltene Skonti", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "8900", "name": "Erloese Anlageverkaeufe", "type": "revenue", "parent_code": None, "tax_relevant": True},

    # ── Class 9: Eigenkapital / Vortragskonten (Equity) ───────────────
    {"code": "9000", "name": "Eigenkapital / Vortragskonto", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "9008", "name": "Offene Ruecklagen", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "9050", "name": "Gewinnvortrag vor Verwendung", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "9060", "name": "Verlustvortrag vor Verwendung", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "9090", "name": "Jahresueberschuss / Jahresfehlbetrag", "type": "equity", "parent_code": None, "tax_relevant": False},
]


# ---------------------------------------------------------------------------
# SKR04 — Abschlussgliederungsprinzip (~80 most-used accounts)
# ---------------------------------------------------------------------------

SKR04_ACCOUNTS: list[dict] = [
    # ── Class 0: Anlagevermoegen (Fixed Assets) ────────────────────────
    {"code": "0027", "name": "EDV-Software", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0200", "name": "Maschinen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0320", "name": "PKW", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0400", "name": "Betriebs- und Geschaeftsausstattung", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "0420", "name": "Bueroeinrichtung", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0480", "name": "Geringwertige Wirtschaftsgueter (GWG)", "type": "asset", "parent_code": "0400", "tax_relevant": False},
    {"code": "0620", "name": "Grundstuecke und Bauten", "type": "asset", "parent_code": None, "tax_relevant": False},

    # ── Class 1: Finanzanlagen / Eigenkapital (Financial Assets / Equity)
    {"code": "1000", "name": "Anleihen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "1200", "name": "Beteiligungen", "type": "asset", "parent_code": None, "tax_relevant": False},

    # ── Class 2: Umlaufvermoegen (Current Assets) ─────────────────────
    {"code": "2000", "name": "Roh-, Hilfs- und Betriebsstoffe (Bestand)", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "2200", "name": "Forderungen aus Lieferungen und Leistungen", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "2300", "name": "Sonstige Vermoegensgegenstande", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "2400", "name": "Vorsteuer im Folgejahr abziehbar", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "2600", "name": "Vorsteuer 19%", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "2601", "name": "Vorsteuer 7%", "type": "asset", "parent_code": None, "tax_relevant": True},
    {"code": "2800", "name": "Bank", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "2810", "name": "Bank 2", "type": "asset", "parent_code": "2800", "tax_relevant": False},
    {"code": "2880", "name": "Kasse", "type": "asset", "parent_code": None, "tax_relevant": False},
    {"code": "2900", "name": "Aktive Rechnungsabgrenzung", "type": "asset", "parent_code": None, "tax_relevant": False},

    # ── Class 3: Eigenkapital / Verbindlichkeiten (Equity / Liabilities)
    {"code": "3000", "name": "Eigenkapital / Vortragskonto", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "3001", "name": "Gewinnvortrag", "type": "equity", "parent_code": "3000", "tax_relevant": False},
    {"code": "3030", "name": "Verlustvortrag", "type": "equity", "parent_code": "3000", "tax_relevant": False},
    {"code": "3100", "name": "Privatentnahmen", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "3180", "name": "Privateinlagen", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "3300", "name": "Verbindlichkeiten aus Lieferungen und Leistungen", "type": "liability", "parent_code": None, "tax_relevant": False},
    {"code": "3500", "name": "Sonstige Verbindlichkeiten", "type": "liability", "parent_code": None, "tax_relevant": False},
    {"code": "3700", "name": "Erhaltene Anzahlungen", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3800", "name": "Umsatzsteuer 19%", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3801", "name": "Umsatzsteuer 7%", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3806", "name": "Umsatzsteuer-Vorauszahlung", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3811", "name": "Umsatzsteuer Vorjahr", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3820", "name": "Lohnsteuerverbindlichkeiten", "type": "liability", "parent_code": None, "tax_relevant": True},
    {"code": "3900", "name": "Passive Rechnungsabgrenzung", "type": "liability", "parent_code": None, "tax_relevant": False},

    # ── Class 4: Erloese (Revenue) ────────────────────────────────────
    {"code": "4000", "name": "Erloese 7%", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4100", "name": "Steuerfreie Erloese (Inland)", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4120", "name": "Steuerfreie innergemeinschaftliche Lieferungen", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4125", "name": "Steuerfreie Ausfuhrlieferungen Drittland", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4300", "name": "Erloese 19%", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4400", "name": "Erloese 19% (allgemein)", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4500", "name": "Provisionserloese", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4700", "name": "Erloese Nebenbetrieb", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4730", "name": "Erhaltene Skonti", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "4900", "name": "Erloese Anlageverkaeufe", "type": "revenue", "parent_code": None, "tax_relevant": True},

    # ── Class 5: Materialaufwand (Material Costs) ─────────────────────
    {"code": "5000", "name": "Roh-, Hilfs- und Betriebsstoffe", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5100", "name": "Fremdleistungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5200", "name": "Wareneingang 19%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5300", "name": "Wareneingang 7%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5400", "name": "Wareneingang steuerfrei", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5730", "name": "Erhaltene Skonti 19%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5740", "name": "Erhaltene Skonti 7%", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "5800", "name": "Anschaffungsnebenkosten", "type": "expense", "parent_code": None, "tax_relevant": True},

    # ── Class 6: Personalaufwand und sonstige Aufwendungen (Personnel / Other)
    {"code": "6000", "name": "Loehne", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6020", "name": "Gehaelter", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6030", "name": "Gesetzliche soziale Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6040", "name": "Freiwillige soziale Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6100", "name": "Abschreibungen auf Sachanlagen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6200", "name": "Sonstige betriebliche Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6300", "name": "Raumkosten / Miete", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6310", "name": "Strom, Gas, Wasser", "type": "expense", "parent_code": "6300", "tax_relevant": True},
    {"code": "6330", "name": "Reinigung", "type": "expense", "parent_code": "6300", "tax_relevant": True},
    {"code": "6400", "name": "Versicherungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6500", "name": "Kfz-Kosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6510", "name": "Kfz-Steuer", "type": "expense", "parent_code": "6500", "tax_relevant": True},
    {"code": "6520", "name": "Kfz-Versicherung", "type": "expense", "parent_code": "6500", "tax_relevant": True},
    {"code": "6530", "name": "Laufende Kfz-Betriebskosten", "type": "expense", "parent_code": "6500", "tax_relevant": True},
    {"code": "6540", "name": "Kfz-Reparaturen", "type": "expense", "parent_code": "6500", "tax_relevant": True},
    {"code": "6600", "name": "Werbekosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6610", "name": "Repraesentationskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6630", "name": "Geschenke abziehbar", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6640", "name": "Bewirtungskosten (70% abziehbar)", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6650", "name": "Reisekosten Arbeitnehmer", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6660", "name": "Reisekosten Uebernachtung", "type": "expense", "parent_code": "6650", "tax_relevant": True},
    {"code": "6663", "name": "Reisekosten Verpflegungsmehraufwand", "type": "expense", "parent_code": "6650", "tax_relevant": True},
    {"code": "6700", "name": "Porto", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6800", "name": "Telefon und Internet", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6805", "name": "Mobilfunkkosten", "type": "expense", "parent_code": "6800", "tax_relevant": True},
    {"code": "6815", "name": "Burobedarf", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6820", "name": "Fachzeitschriften und Buecher", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6825", "name": "Rechts- und Beratungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6830", "name": "Buchfuehrungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6835", "name": "Abschluss- und Pruefungskosten", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6855", "name": "Nebenkosten des Geldverkehrs", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "6900", "name": "Reparaturen und Instandhaltung", "type": "expense", "parent_code": None, "tax_relevant": True},

    # ── Class 7: Weitere Aufwendungen / Ertraege (Further Expenses / Income)
    {"code": "7000", "name": "Gewerbesteuer", "type": "expense", "parent_code": None, "tax_relevant": False},
    {"code": "7100", "name": "Zinsertraege", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "7200", "name": "Zinsaufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "7300", "name": "Ausserordentliche Aufwendungen", "type": "expense", "parent_code": None, "tax_relevant": True},
    {"code": "7310", "name": "Ausserordentliche Ertraege", "type": "revenue", "parent_code": None, "tax_relevant": True},
    {"code": "7400", "name": "Forderungsverluste", "type": "expense", "parent_code": None, "tax_relevant": True},

    # ── Class 9: Statistische Konten ──────────────────────────────────
    {"code": "9000", "name": "Saldenvortraege Sachkonten", "type": "equity", "parent_code": None, "tax_relevant": False},
    {"code": "9008", "name": "Offene Ruecklagen", "type": "equity", "parent_code": None, "tax_relevant": False},
]


# ---------------------------------------------------------------------------
# Tax mapping: SKR03 account code -> USt-VA Kennzahl
# ---------------------------------------------------------------------------

SKR03_TAX_MAPPING: dict[str, dict] = {
    # Revenue accounts -> Kennzahlen
    "8300": {"kennzahl": "81", "tax_rate": 0.19, "description": "Erloese 19% -> KZ81"},
    "8400": {"kennzahl": "81", "tax_rate": 0.19, "description": "Erloese 19% -> KZ81"},
    "8500": {"kennzahl": "81", "tax_rate": 0.19, "description": "Provisionserloese -> KZ81"},
    "8600": {"kennzahl": "81", "tax_rate": 0.19, "description": "Erloese Vermietung -> KZ81"},
    "8700": {"kennzahl": "81", "tax_rate": 0.19, "description": "Erloese Nebenbetrieb -> KZ81"},
    "8000": {"kennzahl": "86", "tax_rate": 0.07, "description": "Erloese 7% -> KZ86"},
    "8100": {"kennzahl": "61", "tax_rate": 0.0, "description": "Steuerfreie Erloese -> KZ61"},
    "8120": {"kennzahl": "41", "tax_rate": 0.0, "description": "Innergem. Lieferungen -> KZ41"},
    "8125": {"kennzahl": "43", "tax_rate": 0.0, "description": "Ausfuhrlieferungen Drittland -> KZ43"},
    # Input tax accounts -> Kennzahlen
    "1576": {"kennzahl": "66", "tax_rate": 0.19, "description": "Vorsteuer 19% -> KZ66"},
    "1571": {"kennzahl": "66", "tax_rate": 0.07, "description": "Vorsteuer 7% -> KZ66"},
    "1580": {"kennzahl": "67", "tax_rate": 0.19, "description": "Vorsteuer 13b -> KZ67"},
    # Output tax accounts
    "1776": {"kennzahl": "36", "tax_rate": 0.19, "description": "USt 19% -> Steuer auf KZ81"},
    "1771": {"kennzahl": "35", "tax_rate": 0.07, "description": "USt 7% -> Steuer auf KZ86"},
    # Innergemeinschaftlicher Erwerb
    "1773": {"kennzahl": "89", "tax_rate": 0.19, "description": "USt aus igE -> KZ89"},
}


# ---------------------------------------------------------------------------
# EUeR line mapping: SKR03 account code -> Anlage EUeR line number
# ---------------------------------------------------------------------------

_EUER_LINE_MAP: dict[str, str] = {
    # Betriebseinnahmen
    "8300": "14",   # Betriebseinnahmen als umsatzsteuerlicher Regelbesteuerer
    "8400": "14",
    "8000": "14",
    "8100": "12",   # Steuerfreie Betriebseinnahmen
    "8120": "12",
    "8125": "12",
    "8730": "14",   # Erhaltene Skonti — in Erloese eingerechnet
    "8900": "18",   # Veraeusserung von Anlagevermoegen
    # Wareneinkauf
    "3000": "26",   # Wareneinkauf / Rohstoffe
    "3100": "27",   # Bezogene Leistungen (Fremdleistungen)
    "3300": "26",
    "3400": "26",
    "3500": "26",
    # Personal
    "4100": "30",   # Loehne und Gehaelter
    "4110": "30",
    "4120": "30",
    "4125": "30",
    "4130": "32",   # Sozialversicherungsbeitraege
    "4138": "32",
    "4140": "32",
    "4150": "32",
    "4170": "30",
    "4190": "30",
    # Abschreibungen
    "4970": "34",   # AfA auf Sachanlagen
    "0480": "36",   # GWG
    # Raumkosten
    "4200": "50",   # Raumkosten / Miete
    "4210": "50",
    "4220": "50",
    "4230": "50",
    "4240": "50",
    "4250": "50",
    "4260": "50",
    # Versicherungen
    "4300": "52",   # Versicherungen
    "4320": "52",
    # Kfz-Kosten
    "4360": "56",   # Kfz-Steuer
    "4380": "54",   # Kfz-Kosten allgemein
    "4500": "54",
    "4510": "56",
    "4520": "54",
    "4530": "54",
    "4540": "54",
    "4580": "54",
    # Werbung / Repraesentation
    "4600": "58",   # Werbekosten
    "4610": "58",
    "4630": "60",   # Geschenke
    "4635": "60",
    "4640": "62",   # Bewirtungskosten
    # Reisekosten
    "4650": "64",   # Reisekosten
    "4654": "64",
    "4660": "64",
    "4663": "64",
    "4670": "64",
    # Kommunikation
    "4700": "68",   # Porto
    "4800": "68",   # Telefon/Internet
    "4806": "68",
    # Buero und Verwaltung
    "4830": "70",   # Zeitschriften
    "4855": "70",   # Nebenkosten Geldverkehr
    "4900": "70",   # Sonstige Aufwendungen
    "4910": "70",
    "4920": "70",
    "4930": "66",   # Rechts-/Beratungskosten
    "4940": "66",   # Buchfuehrungskosten
    "4945": "66",   # Abschluss-/Pruefungskosten
    "4955": "70",
    "4957": "70",
    "4980": "70",   # Gewerbesteuer (nicht abziehbar, Zeile 70 informatorisch)
    # Reparaturen
    "4400": "52",   # Reparaturen -> Sonstige Aufwendungen
    # Zinsen
    "2100": "19",   # Zinsertraege -> Sonstige Einnahmen
    "2110": "44",   # Zinsaufwendungen
    "2120": "44",
    "2150": "44",
    # Ausserordentlich
    "2000": "72",   # Ausserordentliche Aufwendungen
    "2010": "19",   # Ausserordentliche Ertraege
    "2300": "72",
    "2400": "72",   # Forderungsverluste
    "2500": "72",   # Restbuchwert Abgaenge
}


# ---------------------------------------------------------------------------
# Build index for fast in-memory lookup by (code, variant)
# ---------------------------------------------------------------------------

_SKR03_INDEX: dict[str, dict] = {a["code"]: a for a in SKR03_ACCOUNTS}
_SKR04_INDEX: dict[str, dict] = {a["code"]: a for a in SKR04_ACCOUNTS}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def seed_chart_of_accounts(
    db: AsyncSession,
    variant: str = "SKR03",
) -> int:
    """Insert all standard accounts for the given SKR variant into the database.

    Accounts that already exist (matched on code + variant) are skipped.
    Returns the number of newly inserted accounts.

    Args:
        db: Async SQLAlchemy session.
        variant: Either ``"SKR03"`` or ``"SKR04"``.

    Returns:
        Count of newly inserted rows.
    """
    accounts = SKR03_ACCOUNTS if variant == "SKR03" else SKR04_ACCOUNTS

    # Fetch all codes that already exist for this variant in one query.
    stmt = select(ChartOfAccounts.code).where(
        ChartOfAccounts.skr_variant == variant,
    )
    result = await db.execute(stmt)
    existing_codes: set[str] = {row[0] for row in result.fetchall()}

    inserted = 0
    for acct in accounts:
        if acct["code"] in existing_codes:
            continue
        row = ChartOfAccounts(
            code=acct["code"],
            name=acct["name"],
            account_type=acct["type"],
            skr_variant=variant,
            parent_code=acct["parent_code"],
            is_custom=False,
            tax_relevant=acct["tax_relevant"],
        )
        db.add(row)
        inserted += 1

    if inserted > 0:
        await db.commit()

    return inserted


def get_account_by_code(code: str, variant: str = "SKR03") -> Optional[dict]:
    """Look up an account from the in-memory static list.

    Args:
        code: The 4-digit account code, e.g. ``"1200"``.
        variant: ``"SKR03"`` or ``"SKR04"``.

    Returns:
        The account dict if found, otherwise ``None``.
    """
    index = _SKR03_INDEX if variant == "SKR03" else _SKR04_INDEX
    return index.get(code)


def classify_account(code: str) -> str:
    """Classify an account code into one of the five standard types based on
    SKR03 code-range conventions.

    SKR03 ranges:
        * 0000-0999: asset (Anlagevermoegen)
        * 1000-1399: asset (Umlaufvermoegen / Finanzkonten)
        * 1400-1499: asset (Forderungen)
        * 1500-1599: asset (Sonstige Vermoegensgegenstande / Vorsteuer)
        * 1600-1699: liability (Verbindlichkeiten LuL)
        * 1700-1799: liability (Sonstige Verbindlichkeiten / USt)
        * 1800-1899: equity (Privatkonten)
        * 1900-1999: liability (Rechnungsabgrenzung)
        * 2000-2999: expense/revenue (Abgrenzung — resolved per sub-range)
        * 3000-3999: expense (Wareneinkauf)
        * 4000-4999: expense (Betriebliche Aufwendungen)
        * 5000-7999: expense (rarely used in SKR03)
        * 8000-8999: revenue (Erloese)
        * 9000-9999: equity (Eigenkapital / Vortragskonten)

    Args:
        code: The 4-digit account code string.

    Returns:
        One of ``"asset"``, ``"liability"``, ``"equity"``, ``"revenue"``,
        ``"expense"``.
    """
    numeric = int(code)

    if numeric < 1000:
        return "asset"
    if numeric < 1600:
        return "asset"
    if numeric < 1800:
        return "liability"
    if numeric < 1900:
        return "equity"
    if numeric < 2000:
        return "liability"

    # Class 2: mixed — check known sub-ranges
    if 2000 <= numeric < 3000:
        if numeric in (2010, 2100):
            return "revenue"
        return "expense"

    if 3000 <= numeric < 8000:
        return "expense"
    if 8000 <= numeric < 9000:
        return "revenue"
    if numeric >= 9000:
        return "equity"

    return "expense"


def get_euer_line(code: str) -> Optional[str]:
    """Map a SKR03 account code to its Anlage EUeR line number.

    The Anlage EUeR (Einnahmen-Ueberschuss-Rechnung) is the simplified
    income statement required for small businesses and freelancers in Germany.

    Key line numbers:
        * 12: Steuerfreie Betriebseinnahmen
        * 14: Steuerpflichtige Betriebseinnahmen
        * 18: Veraeusserung Anlagevermoegen
        * 19: Sonstige Einnahmen (Zinsen etc.)
        * 26: Wareneinkauf
        * 27: Fremdleistungen
        * 30: Loehne und Gehaelter
        * 32: Sozialversicherungsbeitraege
        * 34: AfA auf Sachanlagen
        * 36: GWG
        * 44: Zinsaufwendungen
        * 50: Raumkosten
        * 52: Versicherungen / Reparaturen
        * 54: Kfz-Kosten (ohne Steuer)
        * 56: Kfz-Steuer
        * 58: Werbekosten
        * 60: Geschenke
        * 62: Bewirtungskosten
        * 64: Reisekosten
        * 66: Rechts-/Beratungskosten
        * 68: Kommunikationskosten
        * 70: Sonstige Aufwendungen
        * 72: Ausserordentliche Aufwendungen

    Args:
        code: The SKR03 account code.

    Returns:
        The EUeR line number as a string, or ``None`` if unmapped.
    """
    return _EUER_LINE_MAP.get(code)
