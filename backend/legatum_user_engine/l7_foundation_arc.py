"""
L7 — Foundation Arc
Milestones and legal gates for structuring a German Stiftung.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

GateStatus = Literal["locked", "active", "completed"]

_DEFAULT_GATES = [
    {
        "id": "G1", "title": "Stiftungszweck definieren",
        "description": "Gemeinnützigen Zweck gem. §52 AO festlegen",
        "legal_ref": "§52 AO",
    },
    {
        "id": "G2", "title": "Stiftungskapital prüfen",
        "description": "Mindestkapital €50.000 für anerkannte Stiftung",
        "legal_ref": "StiftG BW §4",
    },
    {
        "id": "G3", "title": "Satzungsentwurf",
        "description": "Notarielle Satzung mit Zweck, Organen, Vermögen",
        "legal_ref": "BGB §81",
    },
    {
        "id": "G4", "title": "Anerkennungsverfahren",
        "description": "Einreichung beim Regierungspräsidium Stuttgart",
        "legal_ref": "StiftG BW §3",
    },
    {
        "id": "G5", "title": "Gemeinnützigkeitsbescheid",
        "description": "Finanzamt bestätigt Steuerbefreiung nach §5 KStG",
        "legal_ref": "§5 Abs. 1 Nr. 9 KStG",
    },
    {
        "id": "G6", "title": "LBBW Stiftungskonto eröffnen",
        "description": "Dediziertes Konto + Kapitalanlage-Strategie",
        "legal_ref": "internal",
    },
]


@dataclass
class FoundationGate:
    id: str
    title: str
    description: str
    legal_ref: str
    status: GateStatus = "locked"


@dataclass
class FoundationArc:
    project_id: str
    gates: list[FoundationGate] = field(default_factory=list)
    completion_pct: float = 0.0


def build_foundation_arc(project_id: str, completed_ids: list[str]) -> FoundationArc:
    gates: list[FoundationGate] = []
    prev_completed = True

    for g in _DEFAULT_GATES:
        if g["id"] in completed_ids:
            status: GateStatus = "completed"
            prev_completed = True
        elif prev_completed:
            status = "active"
            prev_completed = False
        else:
            status = "locked"

        gates.append(FoundationGate(
            id=g["id"], title=g["title"],
            description=g["description"], legal_ref=g["legal_ref"],
            status=status,
        ))

    completed = sum(1 for g in gates if g.status == "completed")
    pct = round(completed / len(gates) * 100, 1) if gates else 0.0
    return FoundationArc(project_id=project_id, gates=gates, completion_pct=pct)


def arc_to_dict(arc: FoundationArc) -> dict:
    return {
        "project_id": arc.project_id,
        "completion_pct": arc.completion_pct,
        "gates": [
            {
                "id": g.id, "title": g.title, "description": g.description,
                "legal_ref": g.legal_ref, "status": g.status,
            }
            for g in arc.gates
        ],
    }
