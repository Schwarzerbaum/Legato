"""
Institutional Vendor Risk Index
=================================
Cross-project behavioral memory for contractors and subcontractors.

Replaces SM-2 spaced repetition (designed for human memorization) with
a behavioral pattern tracking system that persists contractor fingerprints
across multiple projects over years.

Core insight: Contractors repeat behaviors. A subcontractor who claimed
Baugrundrisiko Nachträge on 3 different projects will do it on Project 4.
This system surfaces that history before the contract is signed.

Memory tiers (remapped from BlackSwanX SM-2):
    Working     → current project claims (volatile, project-scoped)
    Episodic    → subcontractor behavior within one client's portfolio
    Semantic    → cross-project behavioral fingerprint (PERMANENT after threshold)

Behavioral classifications:
    claim_maximizer         → systematically claims maximum on ambiguous items
    baugrundrisiko_serial   → repeatedly claims unexpected ground conditions
    delay_claimer           → consistently files Behinderungsanzeigen
    documentation_avoider   → habitually submits incomplete documentation
    quality_risk            → repeated Mängel across projects
    reliable_contractor     → low claim rate, clean documentation history
"""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


# ── Behavioral pattern definitions ───────────────────────────────────────────

BEHAVIORAL_PATTERNS = [
    {
        "pattern_id": "baugrundrisiko_serial",
        "label": "Serieller Baugrundrisiko-Kläger",
        "description": "Fordert wiederholt Nachträge für unvorhersehbare Baugrundverhältnisse",
        "keywords": ["baugrund", "ground condition", "unvorhergesehen", "bodenverhältnis",
                     "bodengutachten", "baugrundrisiko"],
        "vob_ref": "VOB/B §4 Abs. 1",
        "risk_multiplier": 1.35,
        "procurement_flag": "⚠️ Explizite Baugrundrisiko-Zuweisung im Vertrag empfohlen",
    },
    {
        "pattern_id": "claim_maximizer",
        "label": "Claim Maximierer",
        "description": "Stellt systematisch Nachträge für jede Leistungsabweichung",
        "keywords": ["nachtrag", "mehrvergütung", "zusatzleistung", "change order",
                     "zusätzliche leistung", "mehr als vereinbart"],
        "vob_ref": "VOB/B §2 Abs. 5/6",
        "risk_multiplier": 1.25,
        "procurement_flag": "⚠️ Detailliertere Leistungsbeschreibung erforderlich. "
                            "10% Nachtragsreserve einplanen.",
    },
    {
        "pattern_id": "delay_claimer",
        "label": "Verzögerungs-Kläger",
        "description": "Reicht systematisch Behinderungsanzeigen und Bauzeitverlängerungen ein",
        "keywords": ["behinderung", "verzögerung", "bauzeitverlängerung", "delay",
                     "behinderungsanzeige", "unterbrechung"],
        "vob_ref": "VOB/B §6",
        "risk_multiplier": 1.20,
        "procurement_flag": "⚠️ Detaillierter Bauzeitenplan mit Meilensteinen. "
                            "Vertragsstrafe bei kritischem Pfad einbauen.",
    },
    {
        "pattern_id": "documentation_avoider",
        "label": "Dokumentationsmuffel",
        "description": "Reicht regelmäßig unvollständige Unterlagen ein (Aufmaß, Protokolle)",
        "keywords": ["dokumentation fehlt", "kein aufmaß", "protokoll fehlt",
                     "unterlagen unvollständig", "nachreichung"],
        "vob_ref": "VOB/B §14",
        "risk_multiplier": 1.15,
        "procurement_flag": "⚠️ Dokumentationspflichten explizit vertraglich verankern. "
                            "Zahlungsvorbehalt bei fehlenden Unterlagen.",
    },
    {
        "pattern_id": "quality_risk",
        "label": "Qualitätsrisiko",
        "description": "Wiederholt auftretende Mängel bei Abnahme oder in Gewährleistungsphase",
        "keywords": ["mangel", "mängel", "gewährleistung", "nachbesserung", "defect",
                     "abnahmemangel", "werksmangel"],
        "vob_ref": "VOB/B §13",
        "risk_multiplier": 1.30,
        "procurement_flag": "⚠️ Erhöhte Sicherheitsleistung (10% statt 5%) empfohlen. "
                            "Vorabnahme kritischer Leistungen.",
    },
    {
        "pattern_id": "reliable_contractor",
        "label": "Zuverlässiger Auftragnehmer",
        "description": "Geringe Nachtragsquote, vollständige Dokumentation, saubere Abwicklung",
        "keywords": [],  # Identified by LOW occurrence of other patterns
        "vob_ref": None,
        "risk_multiplier": 0.85,
        "procurement_flag": "✅ Bevorzugter Bieter. Vereinfachte Vergabeprüfung möglich.",
    },
]


# ── SM-2 adapted for vendor behavior ─────────────────────────────────────────

def _sm2_update(
    repetitions: int,
    ease_factor: float,
    interval_days: float,
    quality: int,  # 0-5: how clearly this pattern was confirmed
) -> tuple[int, float, float, float]:
    """
    SM-2 algorithm adapted for behavioral pattern tracking.
    quality: 5=exact repeat, 4=clear pattern, 3=partial match, <3=weak signal
    Returns: (new_repetitions, new_ease_factor, new_interval_days, new_strength)
    """
    if quality < 3:
        repetitions = 0
        interval_days = 1.0
    else:
        if repetitions == 0:
            interval_days = 1.0
        elif repetitions == 1:
            interval_days = 6.0
        else:
            interval_days = interval_days * ease_factor

        ease_factor += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        ease_factor = max(1.3, ease_factor)
        repetitions += 1

    strength = min(1.0, repetitions / (repetitions + 2))
    return repetitions, ease_factor, interval_days, strength


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class VendorBehaviorEvent:
    """A single observed behavioral event for a vendor."""
    vendor_id: str
    vendor_name: str
    project_id: str
    project_name: str
    pattern_id: str
    claim_value_eur: float
    evidence_text: str
    quality: int = 3            # SM-2 quality score (0-5)
    observed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class VendorRiskProfile:
    """Full risk profile for a vendor across all projects."""
    vendor_id: str
    vendor_name: str
    total_projects: int = 0
    total_claim_value_eur: float = 0.0
    avg_claim_pct_of_contract: float = 0.0
    behavioral_patterns: list[dict] = field(default_factory=list)
    risk_classification: str = "UNKNOWN"
    risk_score: float = 0.0         # 0-100
    procurement_flags: list[str] = field(default_factory=list)
    contingency_recommendation_pct: float = 5.0
    project_history: list[dict] = field(default_factory=list)
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Database ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db_path = Path(__file__).parent.parent / "backend" / "blackswanx.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_vendor_tables() -> None:
    """Create vendor risk index tables (idempotent)."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ms_vendors (
            vendor_id       TEXT PRIMARY KEY,
            vendor_name     TEXT NOT NULL,
            total_projects  INTEGER DEFAULT 0,
            total_claim_eur REAL DEFAULT 0.0,
            risk_score      REAL DEFAULT 0.0,
            risk_class      TEXT DEFAULT 'UNKNOWN',
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_vendor_patterns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id       TEXT NOT NULL,
            pattern_id      TEXT NOT NULL,
            repetitions     INTEGER DEFAULT 0,
            ease_factor     REAL DEFAULT 2.5,
            interval_days   REAL DEFAULT 1.0,
            strength        REAL DEFAULT 0.0,
            is_permanent    INTEGER DEFAULT 0,
            total_claim_eur REAL DEFAULT 0.0,
            project_count   INTEGER DEFAULT 0,
            first_seen      TEXT DEFAULT (datetime('now')),
            last_seen       TEXT DEFAULT (datetime('now')),
            UNIQUE(vendor_id, pattern_id)
        );

        CREATE TABLE IF NOT EXISTS ms_vendor_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id       TEXT NOT NULL,
            vendor_name     TEXT NOT NULL,
            project_id      TEXT NOT NULL,
            project_name    TEXT NOT NULL,
            pattern_id      TEXT NOT NULL,
            claim_value_eur REAL DEFAULT 0.0,
            evidence_text   TEXT DEFAULT '',
            quality         INTEGER DEFAULT 3,
            observed_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ms_vendor_projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id       TEXT NOT NULL,
            project_id      TEXT NOT NULL,
            project_name    TEXT NOT NULL,
            contract_value  REAL DEFAULT 0.0,
            total_nachträge REAL DEFAULT 0.0,
            nachtrag_count  INTEGER DEFAULT 0,
            outcome         TEXT DEFAULT 'ongoing',
            started_at      TEXT,
            completed_at    TEXT
        );
    """)
    conn.commit()
    conn.close()


# ── Core operations ───────────────────────────────────────────────────────────

def _vendor_id(vendor_name: str) -> str:
    return hashlib.md5(vendor_name.lower().strip().encode()).hexdigest()[:16]


def record_vendor_event(event: VendorBehaviorEvent) -> dict:
    """
    Record a behavioral event for a vendor.
    Updates SM-2 pattern strength. Triggers permanence if threshold met.

    Permanence gate (adapted from BlackSwanX SM-2):
        strength >= 0.75 AND repetitions >= 3 AND project_count >= 2
    """
    init_vendor_tables()
    conn = _get_db()

    # Ensure vendor exists
    conn.execute(
        "INSERT OR IGNORE INTO ms_vendors (vendor_id, vendor_name) VALUES (?,?)",
        (event.vendor_id, event.vendor_name)
    )

    # Get or create pattern record
    existing = conn.execute(
        "SELECT * FROM ms_vendor_patterns WHERE vendor_id=? AND pattern_id=?",
        (event.vendor_id, event.pattern_id)
    ).fetchone()

    if existing:
        reps, ef, interval, strength = _sm2_update(
            existing["repetitions"],
            existing["ease_factor"],
            existing["interval_days"],
            event.quality,
        )
        project_count = existing["project_count"] + 1
        is_permanent = int(
            strength >= 0.75 and reps >= 3 and project_count >= 2
        )
        conn.execute(
            """UPDATE ms_vendor_patterns SET
               repetitions=?, ease_factor=?, interval_days=?, strength=?,
               is_permanent=?, total_claim_eur=total_claim_eur+?,
               project_count=?, last_seen=datetime('now')
               WHERE vendor_id=? AND pattern_id=?""",
            (reps, ef, interval, strength, is_permanent,
             event.claim_value_eur, project_count,
             event.vendor_id, event.pattern_id)
        )
    else:
        reps, ef, interval, strength = _sm2_update(0, 2.5, 1.0, event.quality)
        conn.execute(
            """INSERT INTO ms_vendor_patterns
               (vendor_id, pattern_id, repetitions, ease_factor, interval_days,
                strength, total_claim_eur, project_count)
               VALUES (?,?,?,?,?,?,?,1)""",
            (event.vendor_id, event.pattern_id, reps, ef, interval, strength,
             event.claim_value_eur)
        )

    # Record the event
    conn.execute(
        """INSERT INTO ms_vendor_events
           (vendor_id, vendor_name, project_id, project_name, pattern_id,
            claim_value_eur, evidence_text, quality, observed_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (event.vendor_id, event.vendor_name, event.project_id, event.project_name,
         event.pattern_id, event.claim_value_eur, event.evidence_text[:500],
         event.quality, event.observed_at)
    )

    # Update vendor totals
    conn.execute(
        """UPDATE ms_vendors SET
           total_claim_eur = total_claim_eur + ?,
           updated_at = datetime('now')
           WHERE vendor_id=?""",
        (event.claim_value_eur, event.vendor_id)
    )

    conn.commit()
    conn.close()

    return {
        "vendor_id": event.vendor_id,
        "pattern_id": event.pattern_id,
        "new_strength": round(strength, 3),
        "repetitions": reps,
        "is_permanent": bool(strength >= 0.75 and reps >= 3),
    }


def get_vendor_risk_profile(vendor_name: str) -> VendorRiskProfile:
    """
    Retrieve full risk profile for a vendor.
    Surfaces permanent behavioral patterns first.
    """
    init_vendor_tables()
    vid = _vendor_id(vendor_name)
    conn = _get_db()

    vendor = conn.execute(
        "SELECT * FROM ms_vendors WHERE vendor_id=?", (vid,)
    ).fetchone()

    if not vendor:
        conn.close()
        return VendorRiskProfile(vendor_id=vid, vendor_name=vendor_name)

    patterns_raw = conn.execute(
        """SELECT * FROM ms_vendor_patterns
           WHERE vendor_id=? ORDER BY is_permanent DESC, strength DESC""",
        (vid,)
    ).fetchall()

    projects_raw = conn.execute(
        "SELECT * FROM ms_vendor_projects WHERE vendor_id=? ORDER BY started_at DESC",
        (vid,)
    ).fetchall()

    conn.close()

    # Build pattern profiles
    active_patterns = []
    procurement_flags = []
    risk_multipliers = []

    for p in patterns_raw:
        p = dict(p)
        if p["strength"] < 0.2:
            continue  # weak signal, skip

        pattern_def = next(
            (pd for pd in BEHAVIORAL_PATTERNS if pd["pattern_id"] == p["pattern_id"]),
            None
        )
        if not pattern_def:
            continue

        pattern_entry = {
            "pattern_id": p["pattern_id"],
            "label": pattern_def["label"],
            "description": pattern_def["description"],
            "strength": round(p["strength"], 3),
            "repetitions": p["repetitions"],
            "is_permanent": bool(p["is_permanent"]),
            "total_claim_eur": p["total_claim_eur"],
            "project_count": p["project_count"],
            "vob_ref": pattern_def["vob_ref"],
            "last_seen": p["last_seen"],
        }
        active_patterns.append(pattern_entry)

        if p["strength"] >= 0.5:
            procurement_flags.append(pattern_def["procurement_flag"])
            risk_multipliers.append(pattern_def["risk_multiplier"])

    # Risk score: weighted by pattern strength and permanence
    if active_patterns:
        base_score = sum(
            p["strength"] * (1.5 if p["is_permanent"] else 1.0)
            for p in active_patterns
            if p["pattern_id"] != "reliable_contractor"
        )
        risk_score = min(100, base_score * 25)
    else:
        risk_score = 0.0

    # Classification
    permanent_count = sum(1 for p in active_patterns if p["is_permanent"])
    if permanent_count >= 3 or risk_score >= 75:
        classification = "HIGH_RISK"
    elif permanent_count >= 2 or risk_score >= 50:
        classification = "MEDIUM_RISK"
    elif risk_score >= 25:
        classification = "LOW_RISK"
    elif any(p["pattern_id"] == "reliable_contractor" for p in active_patterns):
        classification = "PREFERRED"
    else:
        classification = "UNKNOWN"

    # Contingency recommendation
    avg_multiplier = (
        sum(risk_multipliers) / len(risk_multipliers)
        if risk_multipliers else 1.0
    )
    contingency_pct = round((avg_multiplier - 1.0) * 100 + 5.0, 1)

    return VendorRiskProfile(
        vendor_id=vid,
        vendor_name=vendor_name,
        total_projects=dict(vendor).get("total_projects", 0),
        total_claim_value_eur=dict(vendor).get("total_claim_eur", 0.0),
        behavioral_patterns=active_patterns,
        risk_classification=classification,
        risk_score=round(risk_score, 1),
        procurement_flags=list(set(procurement_flags)),
        contingency_recommendation_pct=contingency_pct,
        project_history=[dict(p) for p in projects_raw],
        last_updated=dict(vendor).get("updated_at", ""),
    )


def procurement_check(vendor_name: str, contract_value_eur: float) -> dict:
    """
    Run a procurement risk check for a vendor before signing a contract.
    Returns a structured warning with historical data and recommendations.
    """
    profile = get_vendor_risk_profile(vendor_name)
    permanent_patterns = [
        p for p in profile.behavioral_patterns if p["is_permanent"]
    ]

    contingency_eur = round(
        contract_value_eur * profile.contingency_recommendation_pct / 100, 2
    )

    output = {
        "vendor": vendor_name,
        "contract_value_eur": contract_value_eur,
        "risk_classification": profile.risk_classification,
        "risk_score": profile.risk_score,
        "permanent_behavioral_patterns": permanent_patterns,
        "procurement_flags": profile.procurement_flags,
        "contingency_recommendation": {
            "percentage": profile.contingency_recommendation_pct,
            "amount_eur": contingency_eur,
            "reasoning": (
                f"Basierend auf historischer Nachtragsquote "
                f"({len(profile.behavioral_patterns)} aktive Verhaltensmuster)"
            ),
        },
        "historical_summary": {
            "projects_in_database": profile.total_projects,
            "total_claims_eur": profile.total_claim_value_eur,
            "permanent_patterns": len(permanent_patterns),
        },
        "action_required": profile.risk_classification in ("HIGH_RISK", "MEDIUM_RISK"),
    }

    if profile.risk_classification == "HIGH_RISK":
        output["recommendation"] = (
            "🔴 HOHES RISIKO: Vertragsschluss nur mit erhöhten Sicherheiten, "
            "detaillierter Leistungsbeschreibung und expliziter Risikoallokation empfohlen."
        )
    elif profile.risk_classification == "MEDIUM_RISK":
        output["recommendation"] = (
            "🟡 MITTLERES RISIKO: Spezifische Vertragsklauseln für bekannte "
            "Verhaltensmuster einbauen. Erhöhte Dokumentationsanforderungen."
        )
    elif profile.risk_classification == "PREFERRED":
        output["recommendation"] = (
            "🟢 BEVORZUGTER BIETER: Vereinfachte Vergabeprüfung möglich. "
            "Standardkonditionen ausreichend."
        )
    else:
        output["recommendation"] = (
            "⚪ KEINE HISTORISCHEN DATEN: Standardprüfung durchführen."
        )

    return output
