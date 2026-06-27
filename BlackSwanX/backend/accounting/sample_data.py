"""Generate realistic sample DATEV data for testing.

Produces synthetic DATEV bookkeeping, payroll, and bank statement CSVs
that let users try the BlackSwanX analysis pipeline without uploading
real financial data.  Each generator embeds intentional anomalies for
the fraud detector and compliance agents to catch.
"""


def generate_sample_datev_csv() -> str:
    """Generate a realistic DATEV CSV with ~50 bookings for a small German company.

    Includes intentional anomalies:
    - 3 duplicate bookings (same amount, date, accounts)
    - 2 round-number expenses (exactly 499.00, 999.00 EUR)
    - 1 weekend booking (Saturday)

    Format: DATEV CSV with semicolon separator.
    Headers: Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen;
             Konto;Gegenkonto (ohne BU-Schluessel);BU-Schluessel;
             Belegdatum;Belegfeld 1;Buchungstext
    """
    header = (
        "Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen;"
        "Konto;Gegenkonto (ohne BU-Schluessel);BU-Schluessel;"
        "Belegdatum;Belegfeld 1;Buchungstext"
    )

    # Each entry: (amount, s_h, konto, gegenkonto, bu, date, beleg, text)
    bookings = [
        # ── Revenue entries (8300/8400 → 1200 Bank) ─────────────
        ("2380,00", "H", "8400", "1200", "3", "0301", "RE-2026-001",
         "Webdesign Projekt Mueller GmbH"),
        ("4760,00", "H", "8400", "1200", "3", "0501", "RE-2026-002",
         "IT-Beratung Q1 Schmidt AG"),
        ("1190,00", "H", "8400", "1200", "3", "0801", "RE-2026-003",
         "Logo-Design Becker OHG"),
        ("5950,00", "H", "8400", "1200", "3", "1201", "RE-2026-004",
         "Software-Entwicklung Meier KG"),
        ("3570,00", "H", "8400", "1200", "3", "1501", "RE-2026-005",
         "SEO-Optimierung Weber GmbH"),
        ("7140,00", "H", "8400", "1200", "3", "2001", "RE-2026-006",
         "App-Entwicklung Fischer AG"),
        ("1785,00", "H", "8300", "1200", "3", "2501", "RE-2026-007",
         "Schulung Social Media Marketing"),
        ("2975,00", "H", "8400", "1200", "3", "0102", "RE-2026-008",
         "Datenbank-Migration Braun GmbH"),
        ("4165,00", "H", "8400", "1200", "3", "0502", "RE-2026-009",
         "Cloud-Setup Hoffmann AG"),
        ("8330,00", "H", "8400", "1200", "3", "1002", "RE-2026-010",
         "Jahresvertrag IT-Support Schulz KG"),
        ("595,00", "H", "8400", "1200", "3", "1502", "RE-2026-011",
         "WordPress-Plugin Entwicklung"),
        ("3332,50", "H", "8400", "1200", "3", "2002", "RE-2026-012",
         "API-Integration Wagner GmbH"),
        ("1428,00", "H", "8300", "1200", "3", "2502", "RE-2026-013",
         "Workshop Datenschutz DSGVO"),
        ("2618,00", "H", "8400", "1200", "3", "0103", "RE-2026-014",
         "Netzwerk-Audit Klein AG"),
        ("6545,00", "H", "8400", "1200", "3", "0803", "RE-2026-015",
         "ERP-Anpassung Zimmermann GmbH"),

        # ── Expense entries (4xxx → 1200 Bank) ──────────────────
        ("1200,00", "S", "4210", "1200", "", "0201", "M-2026-001",
         "Bueromiete Januar Gewerbepark Sued"),
        ("1200,00", "S", "4210", "1200", "", "0102", "M-2026-002",
         "Bueromiete Februar Gewerbepark Sued"),
        ("1200,00", "S", "4210", "1200", "", "0103", "M-2026-003",
         "Bueromiete Maerz Gewerbepark Sued"),
        ("49,99", "S", "4930", "1200", "", "0501", "TEL-001",
         "Telekom Internet Business L"),
        ("49,99", "S", "4930", "1200", "", "0502", "TEL-002",
         "Telekom Internet Business L"),
        ("49,99", "S", "4930", "1200", "", "0503", "TEL-003",
         "Telekom Internet Business L"),
        ("255,00", "S", "4940", "1200", "", "0301", "DB-001",
         "DB Bahncard 50 Business"),
        ("39,90", "S", "4806", "1200", "", "0401", "VER-001",
         "Berufshaftpflichtversicherung"),
        ("119,00", "S", "4955", "1200", "", "0501", "SW-001",
         "JetBrains IntelliJ IDEA Ultimate"),
        ("23,80", "S", "4950", "1200", "", "0601", "BK-001",
         "Fachbuch Softwarearchitektur"),
        ("47,60", "S", "4950", "1200", "", "0701", "BK-002",
         "Fachbuch Cloud Computing"),
        ("178,50", "S", "4530", "1200", "", "0801", "KFZ-001",
         "Tankfuellung Geschaeftsreise Berlin"),
        ("95,20", "S", "4670", "1200", "", "0901", "RK-001",
         "Reisekosten Messe CeBIT"),
        ("285,60", "S", "4670", "1200", "", "1001", "RK-002",
         "Hotel Uebernachtung Kundenbesuch"),
        ("71,40", "S", "4654", "1200", "", "1101", "BW-001",
         "Geschaeftsessen Kunde Mueller"),
        ("35,70", "S", "4946", "1200", "", "1201", "Porto-001",
         "DHL Paketversand Hardware"),
        ("142,80", "S", "4806", "1200", "", "0102", "VER-002",
         "Bueroinhaltsversicherung"),
        ("59,50", "S", "4960", "1200", "", "0202", "WB-001",
         "Fortbildung Online-Kurs AWS"),
        ("832,00", "S", "4855", "1200", "", "0302", "HW-001",
         "Dell Monitor U2723QE"),
        ("1547,00", "S", "4855", "1200", "", "0402", "HW-002",
         "Apple MacBook Pro Zubehoer"),

        # ── ANOMALY: 3 duplicate bookings ───────────────────────
        ("285,60", "S", "4670", "1200", "", "1001", "RK-002",
         "Hotel Uebernachtung Kundenbesuch"),
        ("49,99", "S", "4930", "1200", "", "0501", "TEL-001",
         "Telekom Internet Business L"),
        ("1200,00", "S", "4210", "1200", "", "0201", "M-2026-001",
         "Bueromiete Januar Gewerbepark Sued"),

        # ── ANOMALY: 2 round-number expenses ────────────────────
        ("499,00", "S", "4900", "1200", "", "0602", "SO-001",
         "Sonstige betriebliche Aufwendungen"),
        ("999,00", "S", "4900", "1200", "", "0702", "SO-002",
         "Beratungsleistung extern"),

        # ── ANOMALY: 1 weekend booking (Saturday) ───────────────
        # 04.01.2026 is a Saturday
        ("357,00", "S", "4855", "1200", "", "0401", "HW-003",
         "Amazon Business Zubehoer Samstag"),

        # ── Additional normal bookings ──────────────────────────
        ("11,90", "S", "4930", "1200", "", "0802", "CL-001",
         "Hetzner Cloud Server"),
        ("29,90", "S", "4955", "1200", "", "0902", "SW-002",
         "GitHub Team Abo"),
        ("16,90", "S", "4955", "1200", "", "1002", "SW-003",
         "Slack Pro Workspace"),
        ("59,50", "S", "4806", "1200", "", "1102", "VER-003",
         "Cyber-Versicherung"),
    ]

    lines = [header]
    for b in bookings:
        lines.append(";".join(b))

    return "\n".join(lines)


def generate_sample_payroll_csv() -> str:
    """Generate a sample payroll CSV with ~10 employees.

    Includes intentional anomalies:
    - One employee near overtime limit (47.5 hrs/week ~ 205.5 monthly)
    - One Minijob at exactly 520 EUR
    - One with Firmenwagen but Geldwerter_Vorteil = 0
    - One below Mindestlohn (11.50 EUR/h effective)
    - Sick days with high count for one employee

    Format: CSV with semicolons.
    """
    header = (
        "Personalnummer;Name;Vorname;Eintritt;Bruttolohn;Nettolohn;"
        "Steuerklasse;SV_Beitrag_AG;SV_Beitrag_AN;"
        "Arbeitsstunden;Ueberstunden;Krankheitstage;Urlaubstage;"
        "Minijob;Firmenwagen;Geldwerter_Vorteil"
    )

    # Format: all fields as strings, German decimals with comma
    employees = [
        # 1. Senior developer — normal, has company car properly declared
        ("1001", "Mueller", "Thomas", "01.03.2020",
         "5800,00", "3654,00", "1",
         "1160,00", "870,00",
         "168,00", "8,00", "3", "2",
         "N", "J", "350,00"),

        # 2. Junior developer — normal
        ("1002", "Schmidt", "Anna", "15.06.2022",
         "3200,00", "2176,00", "1",
         "640,00", "480,00",
         "168,00", "4,00", "5", "2",
         "N", "N", "0,00"),

        # 3. Project manager — ANOMALY: near overtime limit (205h ~ 47.3h/week)
        ("1003", "Weber", "Markus", "01.01.2019",
         "5200,00", "3328,00", "3",
         "1040,00", "780,00",
         "180,00", "25,50", "1", "1",
         "N", "N", "0,00"),

        # 4. Office manager — normal
        ("1004", "Fischer", "Sabine", "01.09.2021",
         "3000,00", "2070,00", "4",
         "600,00", "450,00",
         "160,00", "0,00", "2", "3",
         "N", "N", "0,00"),

        # 5. Sales manager — ANOMALY: Firmenwagen but Geldwerter_Vorteil = 0
        ("1005", "Braun", "Michael", "15.04.2018",
         "4800,00", "3072,00", "1",
         "960,00", "720,00",
         "168,00", "12,00", "4", "2",
         "N", "J", "0,00"),

        # 6. Part-time accountant — normal
        ("1006", "Hoffmann", "Claudia", "01.02.2023",
         "2500,00", "1800,00", "5",
         "500,00", "375,00",
         "100,00", "0,00", "1", "1",
         "N", "N", "0,00"),

        # 7. Werkstudent — ANOMALY: below Mindestlohn (1150/100 = 11.50 EUR/h)
        ("1007", "Klein", "Lukas", "01.10.2025",
         "1150,00", "1035,00", "1",
         "115,00", "86,25",
         "100,00", "0,00", "0", "0",
         "N", "N", "0,00"),

        # 8. Minijob receptionist — ANOMALY: exactly 520 EUR threshold
        ("1008", "Zimmermann", "Petra", "01.04.2024",
         "520,00", "520,00", "6",
         "156,00", "0,00",
         "43,00", "0,00", "0", "0",
         "J", "N", "0,00"),

        # 9. Senior consultant — ANOMALY: high sick days (18 days)
        ("1009", "Wagner", "Stefan", "01.07.2017",
         "6000,00", "3780,00", "3",
         "1200,00", "900,00",
         "168,00", "6,00", "18", "0",
         "N", "N", "0,00"),

        # 10. Marketing intern — normal
        ("1010", "Becker", "Lisa", "01.01.2026",
         "2800,00", "1960,00", "1",
         "560,00", "420,00",
         "160,00", "0,00", "2", "2",
         "N", "N", "0,00"),
    ]

    lines = [header]
    for emp in employees:
        lines.append(";".join(emp))

    return "\n".join(lines)


def generate_sample_bank_csv() -> str:
    """Generate a sample bank statement CSV with ~30 transactions.

    Mix of incoming (client payments) and outgoing (expenses) with
    realistic German Verwendungszweck entries.

    Format: Datum;Betrag;Waehrung;Auftraggeber;Verwendungszweck
    """
    header = "Datum;Betrag;Waehrung;Auftraggeber;Verwendungszweck"

    # (date, amount, currency, sender/receiver, purpose)
    transactions = [
        # ── Incoming payments ───────────────────────────────────
        ("03.01.2026", "2380,00", "EUR",
         "Mueller GmbH",
         "RE-2026-001 Webdesign Projekt"),
        ("05.01.2026", "4760,00", "EUR",
         "Schmidt AG",
         "RE-2026-002 IT-Beratung Q1 Zahlung"),
        ("08.01.2026", "1190,00", "EUR",
         "Becker OHG",
         "RE-2026-003 Logo-Design Abschlussrechnung"),
        ("15.01.2026", "5950,00", "EUR",
         "Meier KG",
         "RE-2026-004 Software-Entwicklung Teilzahlung"),
        ("22.01.2026", "3570,00", "EUR",
         "Weber GmbH",
         "RE-2026-005 SEO-Optimierung Februar"),
        ("02.02.2026", "7140,00", "EUR",
         "Fischer AG",
         "RE-2026-006 App-Entwicklung Sprint 3"),
        ("10.02.2026", "1785,00", "EUR",
         "Volkshochschule Berlin",
         "RE-2026-007 Schulung Social Media"),
        ("15.02.2026", "2975,00", "EUR",
         "Braun GmbH",
         "RE-2026-008 Datenbank-Migration"),
        ("20.02.2026", "4165,00", "EUR",
         "Hoffmann AG",
         "RE-2026-009 Cloud-Setup Projekt"),
        ("05.03.2026", "8330,00", "EUR",
         "Schulz KG",
         "RE-2026-010 IT-Support Jahresvertrag Q1"),
        ("12.03.2026", "595,00", "EUR",
         "Privatperson Neumann",
         "RE-2026-011 WordPress-Plugin"),
        ("20.03.2026", "3332,50", "EUR",
         "Wagner GmbH",
         "RE-2026-012 API-Integration Restzahlung"),

        # ── Outgoing payments ───────────────────────────────────
        ("01.01.2026", "-1200,00", "EUR",
         "Gewerbepark Sued GmbH",
         "Miete Buero Januar 2026 Mietvertrag 4711"),
        ("01.02.2026", "-1200,00", "EUR",
         "Gewerbepark Sued GmbH",
         "Miete Buero Februar 2026 Mietvertrag 4711"),
        ("01.03.2026", "-1200,00", "EUR",
         "Gewerbepark Sued GmbH",
         "Miete Buero Maerz 2026 Mietvertrag 4711"),
        ("05.01.2026", "-49,99", "EUR",
         "Telekom Deutschland GmbH",
         "Internet Business L Kundennr 12345678"),
        ("05.02.2026", "-49,99", "EUR",
         "Telekom Deutschland GmbH",
         "Internet Business L Kundennr 12345678"),
        ("05.03.2026", "-49,99", "EUR",
         "Telekom Deutschland GmbH",
         "Internet Business L Kundennr 12345678"),
        ("15.01.2026", "-255,00", "EUR",
         "Deutsche Bahn AG",
         "Bahncard 50 Business Kundennr 7890"),
        ("10.01.2026", "-39,90", "EUR",
         "Hiscox SA",
         "Berufshaftpflicht Vers.-Nr. BHP-2026-001"),
        ("20.01.2026", "-119,00", "EUR",
         "JetBrains s.r.o.",
         "IntelliJ IDEA Ultimate Annual License"),
        ("25.01.2026", "-23,80", "EUR",
         "Amazon EU S.a.r.l.",
         "Fachbuch Softwarearchitektur ISBN 978-3-xxx"),
        ("03.02.2026", "-178,50", "EUR",
         "Shell Deutschland GmbH",
         "Tankstelle Berlin-Mitte Geschaeftsreise"),
        ("08.02.2026", "-95,20", "EUR",
         "Deutsche Bahn AG",
         "Fahrkarte ICE Berlin-Hannover CeBIT"),
        ("12.02.2026", "-285,60", "EUR",
         "Motel One GmbH",
         "Hotel Berlin 2 Naechte Kundenbesuch"),
        ("18.02.2026", "-71,40", "EUR",
         "Restaurant Lindenhof",
         "Geschaeftsessen 2 Personen Bewirtungsbeleg"),
        ("22.02.2026", "-832,00", "EUR",
         "Dell Technologies GmbH",
         "Monitor U2723QE Bestellung B-2026-041"),
        ("01.03.2026", "-29,90", "EUR",
         "GitHub Inc.",
         "GitHub Team Monthly Subscription"),
        ("05.03.2026", "-16,90", "EUR",
         "Slack Technologies LLC",
         "Slack Pro Workspace Monthly"),
        ("10.03.2026", "-59,50", "EUR",
         "Allianz Versicherung AG",
         "Cyber-Versicherung Police CV-2026"),
    ]

    lines = [header]
    for txn in transactions:
        lines.append(";".join(txn))

    return "\n".join(lines)
