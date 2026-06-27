"""
LEGATUM Demo — Construction AI Modules
==========================================
Quick demonstration of all four novel modules without requiring
a running database or LLM (uses mock data where needed).

Run: python -m legatum.demo
"""

from __future__ import annotations

import json
from datetime import date


def demo_nachtrag_engine():
    """Demo: Nachtragsprüfung with VOB/B procedural checks."""
    print("\n" + "="*60)
    print("DEMO 1: Nachtragsprüfung Engine")
    print("="*60)

    from legatum.nachtrag_engine import (
        NachtragInput, prüfe_nachtrag, verdict_to_dict,
        _run_procedural_checks
    )

    nachtrag = NachtragInput(
        nachtrag_id="N-007",
        claim_value_eur=48_500.0,
        contract_type="VOB/B",
        is_pauschalvertrag=False,
        nachtrag_text="""
        Nachtrag Nr. 7: Fassadenmaterial

        Aufgrund der schriftlichen Anordnung des Auftraggebers vom 15.03.2026
        wurde das Fassadenmaterial von Putz (Leistungsverzeichnis Position 05.02.001)
        auf Klinker geändert. Die Mehrkosten betragen EUR 48.500,00 netto.

        Grundlage: VOB/B §2 Abs. 5 (schriftliche Anordnung liegt vor).
        Aufmaß wurde gemeinsam mit dem Bauleiter am 20.03.2026 aufgenommen.
        """,
        original_lv_text="""
        Position 05.02.001: Außenwandputz, Kalkzementputz zweilagig
        Einheitspreis: EUR 28,50/m²
        Menge: 850 m²
        Gesamtbetrag: EUR 24.225,00
        """,
        correspondence_text="""
        Email AG vom 14.03.2026:
        'Bitte ändern Sie das Fassadenmaterial auf Klinker gemäß beiliegendem
        Muster. Beauftragung erfolgt hiermit schriftlich.'

        Protokoll Baubesprechung 15.03.2026: Änderung besprochen und bestätigt.
        """
    )

    # Run deterministic procedural checks (no LLM)
    procedural = _run_procedural_checks(nachtrag)
    print("\n📋 Verfahrensrechtliche Vorprüfung (ohne KI, regelbasiert):")
    for arg in procedural["an_procedural_points"][:3]:
        print(f"  ✅ AN: {arg[:80]}...")
    for arg in procedural["ag_procedural_points"][:2]:
        print(f"  ⚠️  AG: {arg[:80]}...")

    print("\n💡 Vollständige KI-Analyse würde jetzt starten (Ollama erforderlich)")
    print("   Ergebnis-Format:")

    # Show expected output structure
    expected_output = {
        "nachtrag_id": "N-007",
        "claim_value_eur": 48500.0,
        "risk_score": 35.0,
        "likely_outcome_pct": 72.0,
        "estimated_exposure": {
            "min_eur": 27405.0,
            "max_eur": 41900.0,
            "midpoint_eur": 34652.50,
        },
        "decisive_factor": "Schriftliche Anordnung vorhanden (VOB/B §2 Abs. 5 erfüllt)",
        "documentation_gaps": ["Ankündigung Mehrvergütung vor Ausführung nicht explizit dokumentiert"],
        "recommendation": "APPROVE_PARTIAL",
        "recommendation_reasoning": (
            "Teils berechtigter Nachtrag. Empfehlung: EUR 27.405 – EUR 41.900 anerkennen."
        ),
    }
    print(json.dumps(expected_output, indent=2, ensure_ascii=False))


def demo_vendor_risk():
    """Demo: Institutional Vendor Risk Index."""
    print("\n" + "="*60)
    print("DEMO 2: Institutional Vendor Risk Index")
    print("="*60)

    from legatum.vendor_risk import (
        VendorBehaviorEvent, record_vendor_event,
        get_vendor_risk_profile, procurement_check, _vendor_id
    )

    vendor_name = "Mustermann Tiefbau GmbH"
    vid = _vendor_id(vendor_name)

    # Simulate 3 historical events
    events = [
        VendorBehaviorEvent(
            vendor_id=vid, vendor_name=vendor_name,
            project_id="PRJ-2022-A", project_name="Neubau Wohnanlage Hamburg",
            pattern_id="baugrundrisiko_serial",
            claim_value_eur=32_000.0,
            evidence_text="Nachtrag für unvorhergesehene Baugrundverhältnisse — Felsdurchfahrung",
            quality=5,
        ),
        VendorBehaviorEvent(
            vendor_id=vid, vendor_name=vendor_name,
            project_id="PRJ-2023-B", project_name="Gewerbepark München",
            pattern_id="baugrundrisiko_serial",
            claim_value_eur=55_000.0,
            evidence_text="Nachtrag Baugrundrisiko — unerwartete Grundwasserstand",
            quality=4,
        ),
        VendorBehaviorEvent(
            vendor_id=vid, vendor_name=vendor_name,
            project_id="PRJ-2024-C", project_name="Logistikzentrum Berlin",
            pattern_id="baugrundrisiko_serial",
            claim_value_eur=41_000.0,
            evidence_text="Nachtrag für kontaminiertes Erdreich — Altlastenverdacht",
            quality=5,
        ),
    ]

    print(f"\n📝 Erfasse 3 historische Ereignisse für '{vendor_name}'...")
    for event in events:
        result = record_vendor_event(event)
        print(f"   Muster '{event.pattern_id}': Stärke {result['new_strength']:.2f} "
              f"({'PERMANENT ✅' if result['is_permanent'] else 'episodisch'})")

    # Procurement check
    print(f"\n🔍 Beschaffungsprüfung für neues Projekt (EUR 850.000 Auftragswert):")
    check = procurement_check(vendor_name, contract_value_eur=850_000.0)
    print(f"   Risikoklasse: {check['risk_classification']}")
    print(f"   Risikoscore: {check['risk_score']}/100")
    print(f"   Empfehlung: {check['recommendation']}")
    print(f"   Risikorücklage: {check['contingency_recommendation']['percentage']}% "
          f"= EUR {check['contingency_recommendation']['amount_eur']:,.2f}")
    if check['procurement_flags']:
        print("   Beschaffungshinweise:")
        for flag in check['procurement_flags']:
            print(f"     {flag}")


def demo_schedule_cascade():
    """Demo: Schedule-Aware Risk Cascade."""
    print("\n" + "="*60)
    print("DEMO 3: Schedule-Aware Risk Cascade (CPM-Integration)")
    print("="*60)

    from legatum.schedule_cascade import (
        register_schedule, propagate_delay_cascade,
        cascade_to_dict, analyze_delay_from_text
    )

    project_id = "PRJ-DEMO-2026"

    # Register a simple schedule
    tasks = [
        {
            "node_id": "T001", "name": "Betonage Kellerdecke", "trade": "betonage",
            "planned_start": "2026-06-15", "planned_end": "2026-06-22",
            "predecessors": [], "lag_days": 0, "contract_value_eur": 45_000,
            "subcontractor": "Beton AG", "is_critical_path": True,
        },
        {
            "node_id": "T002", "name": "Rohbau Erdgeschoss", "trade": "rohbau",
            "planned_start": "2026-06-23", "planned_end": "2026-07-10",
            "predecessors": ["T001"], "lag_days": 1, "contract_value_eur": 120_000,
            "subcontractor": "Rohbau GmbH", "is_critical_path": True,
        },
        {
            "node_id": "T003", "name": "Estrich verlegen", "trade": "estrich",
            "planned_start": "2026-07-14", "planned_end": "2026-07-25",
            "predecessors": ["T002"], "lag_days": 4, "contract_value_eur": 28_000,
            "subcontractor": "Estrich Partner", "is_critical_path": False,
        },
        {
            "node_id": "T004", "name": "Elektroinstallation", "trade": "elektroinstallation",
            "planned_start": "2026-07-28", "planned_end": "2026-08-15",
            "predecessors": ["T003"], "lag_days": 3, "contract_value_eur": 65_000,
            "subcontractor": "Elektro Müller", "is_critical_path": True,
        },
        {
            "node_id": "T005", "name": "Trockenbau", "trade": "trockenbau",
            "planned_start": "2026-08-18", "planned_end": "2026-09-05",
            "predecessors": ["T004"], "lag_days": 3, "contract_value_eur": 55_000,
            "subcontractor": "Trockenbau Schmidt", "is_critical_path": False,
        },
    ]

    reg = register_schedule(project_id, tasks)
    print(f"\n✅ Terminplan registriert: {reg['tasks_registered']} Gewerke")

    # Trigger a delay on T001
    print("\n⚠️  Ereignis: Betonage Kellerdecke verzögert sich um 14 Tage")
    result = propagate_delay_cascade(
        project_id=project_id,
        trigger_node_id="T001",
        delay_days=14,
    )

    output = cascade_to_dict(result)
    print(f"\n📊 Kaskadenanalyse:")
    print(f"   Betroffene Gewerke: {output['cascade_summary']['affected_nodes']}")
    print(f"   Kaskadentiefe: {output['cascade_summary']['cascade_depth']} Stufen")
    print(f"   Kritischer Pfad betroffen: {output['cascade_summary']['critical_path_impact']}")
    print(f"   Geschätzte Exposition: EUR {output['cascade_summary']['total_exposure_eur']:,.0f}")
    print(f"\n   VOB/B Rechte ausgelöst:")
    for right in output['vob_rights_triggered']:
        print(f"     • {right}")
    print(f"\n   ⏰ Behinderungsanzeige bis: {output['behinderungsanzeige_deadline']}")
    print(f"\n   {output['recommendation']}")

    if output['affected_nodes']:
        print("\n   Top betroffene Gewerke:")
        for node in output['affected_nodes'][:3]:
            print(f"     • {node['name']} ({node['subcontractor']}): "
                  f"+{node['downstream_delay_days']} Tage, "
                  f"EUR {node['financial_exposure_eur']:,.0f}")


def demo_contractual_mesh():
    """Demo: Cross-Document Contractual Mesh (GAEB + VOB/B)."""
    print("\n" + "="*60)
    print("DEMO 4: Cross-Document Contractual Mesh")
    print("="*60)

    from legatum.contractual_mesh import (
        register_document, build_contractual_mesh,
        _classify_doc_type, GAEB_POSITION_PATTERN, VOB_REF_PATTERN
    )

    sample_docs = [
        {
            "doc_id": 1,
            "filename": "Hauptvertrag_Musteranlage.pdf",
            "text": """
            Werkvertrag nach VOB/B für die Errichtung der Musteranlage.
            Die Vergütung richtet sich nach VOB/B §2. Abnahme gem. VOB/B §12.
            Gewährleistung: 4 Jahre gem. VOB/B §13 Abs. 4.
            """
        },
        {
            "doc_id": 2,
            "filename": "Leistungsverzeichnis_Los1.gaeb",
            "text": """
            Leistungsverzeichnis Los 1 — Rohbauarbeiten
            Position 01.01.001: Aushub Baugrube, 450 m³, EUR 45,00/m³
            Position 01.02.001: Betonage Fundament C25/30, 85 m³, EUR 185,00/m³
            Position 02.01.001: Mauerwerk KS-Stein 24cm, 320 m², EUR 62,00/m²
            Ausführung gem. DIN 18300 (Erdarbeiten), DIN 18331 (Betonarbeiten)
            """
        },
        {
            "doc_id": 3,
            "filename": "Nachtrag_007_Fassade.pdf",
            "text": """
            Nachtrag Nr. 7 zu Position 05.02.001 — Fassadenmaterial
            Schriftliche Anordnung AG vom 15.03.2026 gem. VOB/B §2 Abs. 5.
            Position 05.02.001: Änderung von Putz auf Klinker
            Mehrbetrag: EUR 48.500,00 netto
            Ausführung nach DIN 105 (Mauerziegel)
            """
        },
    ]

    print("\n📄 Dokumente registrieren und klassifizieren:")
    for doc in sample_docs:
        doc_type = _classify_doc_type(doc["filename"], doc["text"])
        positions = GAEB_POSITION_PATTERN.findall(doc["text"])
        vob_refs = [
            f"VOB/B {m.group(1).strip()}"
            for m in VOB_REF_PATTERN.finditer(doc["text"])
        ]
        print(f"   '{doc['filename']}'")
        print(f"     Typ: {doc_type}")
        print(f"     GAEB Positionen: {positions or 'keine'}")
        print(f"     VOB/B Referenzen: {vob_refs or 'keine'}")

    result = build_contractual_mesh(sample_docs)

    print(f"\n🕸️  Contractual Mesh aufgebaut:")
    print(f"   Dokumente verarbeitet: {result['documents_registered']}")
    print(f"   Dokumenttypen: {result['doc_types']}")
    print(f"   Knoten gesamt: {result['total_nodes']}")
    print(f"   Kanten gesamt: {result['total_edges']}")
    print(f"   GAEB Positionen: {result['unique_positions']} "
          f"({result['cross_doc_positions']} dokumentübergreifend)")
    print(f"\n   Pass 1 (Hierarchie): {result['pass_1_hierarchy']['edges_added']} Kanten")
    print(f"   Pass 2 (GAEB):       {result['pass_2_gaeb_positions']['edges_added']} Kanten")
    print(f"   Pass 3 (VOB/DIN):    {result['pass_3_legal_refs']['edges_added']} Kanten")
    print(f"\n   Abfrage-Beispiel: 'Zeige alle Dokumente zu Position 05.02.001'")
    print(f"   → Würde Hauptvertrag + LV + Nachtrag #7 verbinden")


if __name__ == "__main__":
    print("=" * 60)
    print("LEGATUM — Construction AI Modules Demo")
    print("Manjunath Bhaskar / LBBW GmbH")
    print("=" * 60)

    demo_contractual_mesh()
    demo_nachtrag_engine()
    demo_vendor_risk()
    demo_schedule_cascade()

    print("\n" + "="*60)
    print("Demo abgeschlossen.")
    print("Alle Module laufen. Für vollständige KI-Analyse: Ollama starten.")
    print("="*60)
