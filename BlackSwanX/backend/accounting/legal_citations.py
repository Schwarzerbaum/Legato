"""Legal Citation Layer -- Translates biological signals back to German law.

Auditors want law references (paragraphs from AO, UStG, HGB, EStG, GoBD),
not "pheromone intensity" or "apoptosis score."  This module maps every
accounting action to its governing legal citation so that AuditLog entries,
compliance reports, and Betriebspruefung exports speak the language of
German tax law.

Usage:
    from backend.accounting.legal_citations import cite, get_citation, enrich_audit_log

    # Quick inline citation
    user_action = cite("booking_create", f"Buchung #{booking_number}")

    # Enrich an existing audit dict
    enriched = enrich_audit_log({"action": "create", "entity_type": "booking", ...})
"""

from typing import Optional


# ---------------------------------------------------------------------------
# 1. Citation Registry
# ---------------------------------------------------------------------------

LEGAL_CITATIONS: dict[str, str] = {
    # ── GoBD (Grundsaetze ordnungsmaessiger DV-gestuetzter Buchfuehrungssysteme) ──
    "booking_create": (
        "§146 AO Abs. 1 — Buchungen sind einzeln, vollstaendig, "
        "richtig, zeitgerecht und geordnet vorzunehmen."
    ),
    "booking_lock": (
        "§146 AO Abs. 4 — Eine Buchung darf nicht in einer Weise "
        "veraendert werden, dass der urspruengliche Inhalt nicht mehr "
        "feststellbar ist."
    ),
    "booking_storno": (
        "§146 AO Abs. 4 i.V.m. GoBD Tz. 59 — Korrekturen nur "
        "durch Stornobuchung, nicht durch Loeschung."
    ),
    "fiscal_year_close": (
        "§146 AO Abs. 5 i.V.m. §147 AO — "
        "Aufbewahrungspflicht 10 Jahre."
    ),
    "audit_log_create": (
        "GoBD Tz. 52-55 — Verfahrensdokumentation und "
        "Protokollierung aller Aenderungen."
    ),

    # ── UStG (Umsatzsteuergesetz) ──
    "invoice_create": (
        "§14 UStG Abs. 4 — Pflichtangaben einer Rechnung."
    ),
    "invoice_sequential": (
        "§14 UStG Abs. 4 Nr. 4 — Fortlaufende Rechnungsnummer."
    ),
    "ust_va_calculate": (
        "§18 UStG Abs. 1 — Voranmeldungspflicht."
    ),
    "ust_va_submit": (
        "§18 UStG Abs. 1 Satz 1 — Abgabe bis zum 10. des "
        "Folgemonats."
    ),

    # ── Apoptosis-specific ──
    "apoptosis_ust_va": (
        "§146 AO Abs. 1 i.V.m. §168 AO — Steueranmeldung "
        "unter Vorbehalt. System-Selbstpruefung: Konsens der Pruefagenten "
        "unterschreitet Schwellenwert."
    ),
    "apoptosis_report": (
        "GoBD Tz. 100-105 — Ordnungsmaessigkeit der Verarbeitung "
        "nicht sichergestellt."
    ),
    "apoptosis_categorization": (
        "§146 AO Abs. 1 — Richtigkeit der Buchung nicht "
        "gewaehrleistet."
    ),

    # ── AO (Abgabenordnung) -- Audit risk ──
    "betriebspruefung_risk": (
        "§193 AO — Zulaessigkeit der Aussenpruefung."
    ),
    "aufbewahrung": (
        "§147 AO Abs. 1 — Aufbewahrungspflicht fuer "
        "Buchungsbelege."
    ),
    "mitwirkung": (
        "§200 AO — Mitwirkungspflicht des Steuerpflichtigen."
    ),

    # ── EStG (Einkommensteuergesetz) ──
    "euer_calculate": (
        "§4 Abs. 3 EStG — Einnahmen-Ueberschussrechnung."
    ),
    "investitionsabzug": (
        "§7g EStG — Investitionsabzugsbetraege."
    ),
    "gwg": (
        "§6 Abs. 2 EStG — Geringwertige Wirtschaftsgueter."
    ),
    "arbeitszimmer": (
        "§4 Abs. 5 Nr. 6b EStG — Haeusliches Arbeitszimmer."
    ),

    # ── HGB ──
    "gobd_compliance": (
        "§238 HGB i.V.m. §239 HGB — Buchfuehrungspflicht "
        "und Fuehrung der Handelsbuecher."
    ),
    "grundsatz_klarheit": (
        "§243 Abs. 2 HGB — Grundsatz der Klarheit und "
        "Uebersichtlichkeit."
    ),
}

# Mapping from AuditLog (entity_type, action) pairs to citation keys.
# Used by enrich_audit_log to auto-resolve citations.
_ACTION_MAP: dict[tuple[str, str], str] = {
    ("booking", "create"): "booking_create",
    ("booking", "lock"): "booking_lock",
    ("booking", "storno"): "booking_storno",
    ("fiscal_year", "lock"): "fiscal_year_close",
    ("invoice", "create"): "invoice_create",
    ("ust_va", "create"): "ust_va_calculate",
    ("ust_va", "apoptosis"): "apoptosis_ust_va",
}


# ---------------------------------------------------------------------------
# 2. Public API
# ---------------------------------------------------------------------------

def get_citation(action: str) -> str:
    """Look up a legal citation by action key.

    Returns the full citation text, or a fallback string if the action
    key is not found in the registry.
    """
    return LEGAL_CITATIONS.get(
        action,
        f"Keine gesetzliche Referenz fuer Aktion '{action}' hinterlegt.",
    )


def cite(action: str, context: str = "") -> str:
    """Format a full audit-ready citation string.

    Example output::

        [§146 AO Abs. 1] Buchungen sind einzeln... | Kontext: Buchung #42

    If *context* is empty the ``| Kontext:`` suffix is omitted.
    """
    raw = LEGAL_CITATIONS.get(action)
    if raw is None:
        base = f"[Keine Referenz] Aktion: {action}"
    else:
        # Extract the paragraph reference (everything before the em-dash)
        parts = raw.split("—", 1)
        ref = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else raw
        base = f"[{ref}] {description}"

    if context:
        return f"{base} | Kontext: {context}"
    return base


def enrich_audit_log(audit_dict: dict) -> dict:
    """Add a ``legal_citation`` field to an AuditLog-shaped dict.

    Resolution order:
      1. Direct match on ``audit_dict["action"]`` as a citation key.
      2. Compound match on ``(entity_type, action)`` via ``_ACTION_MAP``.
      3. Falls back to a "no citation" placeholder.

    The original dict is returned (mutated in place) with the new field.
    """
    action = audit_dict.get("action", "")
    entity_type = audit_dict.get("entity_type", "")

    # Try direct action key first
    if action in LEGAL_CITATIONS:
        audit_dict["legal_citation"] = cite(action)
        return audit_dict

    # Try compound (entity_type, action) mapping
    compound_key = _ACTION_MAP.get((entity_type, action))
    if compound_key is not None:
        audit_dict["legal_citation"] = cite(compound_key)
        return audit_dict

    # Fallback
    audit_dict["legal_citation"] = get_citation(action)
    return audit_dict
