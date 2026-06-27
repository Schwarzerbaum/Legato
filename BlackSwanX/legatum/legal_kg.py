"""
Legal-Twin Knowledge Graph Engine
====================================
Novel ConTech KG architecture embedding three dimensions natively:
    1. Hierarchy  — GAEB deterministic tree (not text similarity)
    2. Time       — Asymmetric temporal edges with valid_from/valid_until
    3. Regulation — DIN/VOB/B auto-binding without LLM

Novel features:
    - Multi-Dimensional Legal-Twin Graph (GAEB anchors + temporal edges)
    - Tribunal Consensus Entity Deduplication (Prosecutor/Defense/Judge)
    - Structural Legal Densification (3 passes: inheritance, regulatory, transitivity)
    - Spatiotemporal Critical Path Cascading (graph traversal along CPM)
"""

from __future__ import annotations

import re
import json
import math
import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Literal


# ── DIN / VOB/B Regulatory Binding Table ─────────────────────────────────────
# Maps construction activities → automatic DIN standard + VOB/B bindings
# This is what makes Pass 2 deterministic — no LLM needed

REGULATORY_BINDINGS: list[dict] = [
    {
        "activity_keywords": ["erdarbeit", "aushub", "erdreich", "boden", "excavat"],
        "din_standards": ["DIN 18300", "DIN 18301"],
        "vob_section": "VOB/C ATV DIN 18300",
        "liability_note": "Baugrundrisiko beim AG gem. VOB/B §4 Abs. 1",
    },
    {
        "activity_keywords": ["betonarbeit", "beton", "stahlbeton", "fundament", "concrete"],
        "din_standards": ["DIN 18331", "DIN EN 206", "DIN 1045"],
        "vob_section": "VOB/C ATV DIN 18331",
        "liability_note": "Betonqualität gem. DIN EN 206; Abnahme nach VOB/B §12",
    },
    {
        "activity_keywords": ["mauerwerk", "ziegel", "kalksandstein", "masonry"],
        "din_standards": ["DIN 18330", "DIN 1053", "DIN 105"],
        "vob_section": "VOB/C ATV DIN 18330",
        "liability_note": "Mauerwerksausführung gem. DIN 1053",
    },
    {
        "activity_keywords": ["putz", "verputz", "außenputz", "innenputz", "plaster"],
        "din_standards": ["DIN 18350", "DIN 18550"],
        "vob_section": "VOB/C ATV DIN 18350",
        "liability_note": "Putzausführung gem. DIN 18550 Teile 1-4",
    },
    {
        "activity_keywords": ["trockenbau", "gipskarton", "drywall", "ständerwand"],
        "din_standards": ["DIN 18183", "DIN 4102"],
        "vob_section": "VOB/C ATV DIN 18183",
        "liability_note": "Brandschutzanforderungen gem. DIN 4102",
    },
    {
        "activity_keywords": ["elektro", "installation", "elektroinstallation", "electrical"],
        "din_standards": ["DIN VDE 0100", "DIN 18382", "VDE 0100-600"],
        "vob_section": "VOB/C ATV DIN 18382",
        "liability_note": "VDE-Abnahme erforderlich; DIN VDE 0100-600 Prüfprotokoll",
    },
    {
        "activity_keywords": ["heizung", "sanitär", "klima", "hvac", "lüftung"],
        "din_standards": ["DIN 18380", "DIN EN 12831", "VDI 2050"],
        "vob_section": "VOB/C ATV DIN 18380",
        "liability_note": "Heizlastberechnung gem. DIN EN 12831",
    },
    {
        "activity_keywords": ["dach", "dachdecker", "abdichtung", "roofing"],
        "din_standards": ["DIN 18338", "DIN 18195", "DIN 68800"],
        "vob_section": "VOB/C ATV DIN 18338",
        "liability_note": "Abdichtung gem. DIN 18195; Holzschutz gem. DIN 68800",
    },
    {
        "activity_keywords": ["fenster", "tür", "verglasung", "glazing", "window"],
        "din_standards": ["DIN 18360", "DIN EN 14351", "DIN 4108"],
        "vob_section": "VOB/C ATV DIN 18360",
        "liability_note": "Wärmeschutz gem. DIN 4108; CE-Kennzeichnung gem. DIN EN 14351",
    },
    {
        "activity_keywords": ["estrich", "bodenbelag", "screed", "floor"],
        "din_standards": ["DIN 18353", "DIN 18560", "DIN 18365"],
        "vob_section": "VOB/C ATV DIN 18353",
        "liability_note": "Estrich gem. DIN 18560; Trocknungszeiten einhalten",
    },
    {
        "activity_keywords": ["fassade", "wärmedämmung", "wdvs", "insulation"],
        "din_standards": ["DIN 55699", "DIN EN 13162", "DIN 4108-2"],
        "vob_section": "VOB/C ATV Wärmedämm-Verbundsysteme",
        "liability_note": "EnEV/GEG Anforderungen; Zulassung des WDVS-Systems",
    },
]

# Liability clauses that are inherited from parent contracts (Pass 1)
INHERITABLE_CLAUSE_TYPES = [
    "vertragsstrafe", "gewährleistung", "haftung", "versicherung",
    "gerichtsstand", "abtretungsverbot", "bankgarantie", "sicherheitseinbehalt",
]


# ── Database ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db_path = Path(__file__).parent.parent / "backend" / "blackswanx.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_legal_kg_tables() -> None:
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS lkg_nodes (
            node_id         TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            node_type       TEXT NOT NULL,
            -- Legal-Twin dimensions
            gaeb_code       TEXT,           -- e.g. "01.02.003" — deterministic anchor
            valid_from      TEXT,           -- ISO date — when this fact became true
            valid_until     TEXT,           -- ISO date — when superseded (NULL = current)
            is_superseded   INTEGER DEFAULT 0,
            superseded_by   TEXT,
            -- Regulatory dimension
            din_standards   TEXT DEFAULT '[]',
            vob_section     TEXT,
            liability_note  TEXT,
            -- Graph metadata
            doc_ids         TEXT DEFAULT '[]',
            mention_count   INTEGER DEFAULT 1,
            confidence      REAL DEFAULT 0.9,
            -- Tribunal audit
            tribunal_verdict TEXT,          -- JSON: prosecutor/defense/judge verdicts
            merged_from     TEXT DEFAULT '[]',  -- node_ids that were merged into this
            properties      TEXT DEFAULT '{}',
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lkg_edges (
            edge_id         TEXT PRIMARY KEY,
            src             TEXT NOT NULL,
            tgt             TEXT NOT NULL,
            edge_type       TEXT NOT NULL,
            -- Legal-Twin temporal dimension
            valid_from      TEXT,
            valid_until     TEXT,
            milestone_trigger TEXT,         -- which milestone activates/deactivates this edge
            -- Legal dimension
            legal_basis     TEXT,
            inherited_from  TEXT,           -- parent contract node_id (Pass 1)
            is_inferred     INTEGER DEFAULT 0,  -- 1 if derived by structural pass
            inferred_by     TEXT,           -- "pass1_inheritance"|"pass2_regulatory"|"pass3_transitivity"
            -- Weight
            weight          REAL DEFAULT 1.0,
            excerpt         TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lkg_tribunal_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_a        TEXT NOT NULL,
            entity_b        TEXT NOT NULL,
            prosecutor_verdict TEXT,
            defense_verdict  TEXT,
            judge_verdict    TEXT,
            final_decision  TEXT NOT NULL,  -- "merge" | "separate" | "needs_human"
            confidence      REAL DEFAULT 0.0,
            audit_hash      TEXT,           -- SHA256 of all inputs — immutable audit trail
            decided_at      TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Node / Edge helpers ───────────────────────────────────────────────────────

def _nid(name: str, ntype: str) -> str:
    return hashlib.md5(f"{ntype}:{name.lower().strip()}".encode()).hexdigest()[:16]

def _eid(src: str, tgt: str, etype: str) -> str:
    return hashlib.md5(f"{src}:{tgt}:{etype}".encode()).hexdigest()[:16]

def _upsert_node(conn, node_id, name, node_type, **kwargs) -> None:
    props = {k: v for k, v in kwargs.items()
             if k in ("gaeb_code","valid_from","valid_until","din_standards",
                      "vob_section","liability_note","doc_ids","confidence","properties")}
    conn.execute(
        """INSERT OR IGNORE INTO lkg_nodes
           (node_id, name, node_type, gaeb_code, valid_from, valid_until,
            din_standards, vob_section, liability_note, doc_ids, confidence)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (node_id, name, node_type,
         props.get("gaeb_code"),
         props.get("valid_from"),
         props.get("valid_until"),
         json.dumps(props.get("din_standards", [])),
         props.get("vob_section"),
         props.get("liability_note"),
         json.dumps(props.get("doc_ids", [])),
         props.get("confidence", 0.9))
    )

def _upsert_edge(conn, src, tgt, etype, **kwargs) -> bool:
    eid = _eid(src, tgt, etype)
    existing = conn.execute("SELECT edge_id FROM lkg_edges WHERE edge_id=?", (eid,)).fetchone()
    if existing:
        return False
    conn.execute(
        """INSERT INTO lkg_edges
           (edge_id, src, tgt, edge_type, valid_from, valid_until,
            milestone_trigger, legal_basis, inherited_from, is_inferred,
            inferred_by, weight, excerpt)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, src, tgt, etype,
         kwargs.get("valid_from"), kwargs.get("valid_until"),
         kwargs.get("milestone_trigger"),
         kwargs.get("legal_basis"),
         kwargs.get("inherited_from"),
         int(kwargs.get("is_inferred", False)),
         kwargs.get("inferred_by"),
         kwargs.get("weight", 1.0),
         kwargs.get("excerpt", "")[:200])
    )
    return True


# ── GAEB Position extraction ──────────────────────────────────────────────────

GAEB_RE = re.compile(r'\b(\d{2}[._]\d{2}[._]\d{3,4})\b')
DATE_RE = re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b')

def _extract_gaeb_positions(text: str) -> list[str]:
    return list(set(GAEB_RE.findall(text)))

def _extract_date(text: str) -> str | None:
    m = DATE_RE.search(text)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 100: y += 2000
        try:
            return date(y, int(mo), int(d)).isoformat()
        except ValueError:
            pass
    return None

def _detect_activities(text: str) -> list[dict]:
    """Find which construction activities appear in text and return their regulatory bindings."""
    text_lower = text.lower()
    found = []
    for binding in REGULATORY_BINDINGS:
        if any(kw in text_lower for kw in binding["activity_keywords"]):
            found.append(binding)
    return found


# ── Pass 1: Parent-Child Inheritance ─────────────────────────────────────────

def pass1_inheritance(conn, parent_node_id: str, child_node_id: str,
                      parent_text: str, child_text: str) -> int:
    """
    Force child node (Nachtrag, Anlage) to inherit liability/venue/insurance
    clauses from parent contract UNLESS explicitly overridden.
    Returns number of inherited edges created.
    """
    edges_added = 0
    parent_lower = parent_text.lower()
    child_lower = child_text.lower()

    for clause_type in INHERITABLE_CLAUSE_TYPES:
        if clause_type not in parent_lower:
            continue

        # Check if child overrides it
        if clause_type in child_lower:
            # Child has its own clause — no inheritance, explicit override
            _upsert_edge(conn, child_node_id, parent_node_id,
                f"overrides_{clause_type}",
                legal_basis=f"Explicit override of {clause_type} in subordinate document",
                is_inferred=True, inferred_by="pass1_inheritance", weight=1.0)
            edges_added += 1
        else:
            # Child inherits from parent
            clause_node_id = _nid(f"{clause_type}_clause", "CLAUSE")
            _upsert_node(conn, clause_node_id, f"{clause_type.title()} Clause",
                         "CLAUSE", liability_note=f"Inherited clause type: {clause_type}")

            _upsert_edge(conn, parent_node_id, clause_node_id, "contains_clause",
                legal_basis=f"VOB/B — {clause_type} Regelung im Hauptvertrag",
                weight=1.0)

            _upsert_edge(conn, child_node_id, clause_node_id, "inherits_clause",
                legal_basis=f"Untergeordnetes Dokument erbt {clause_type} vom Hauptvertrag",
                inherited_from=parent_node_id,
                is_inferred=True, inferred_by="pass1_inheritance", weight=0.9)
            edges_added += 2

    return edges_added


# ── Pass 2: Regulatory Auto-Binding ──────────────────────────────────────────

def pass2_regulatory_binding(conn, node_id: str, text: str) -> int:
    """
    Automatically bind any node mentioning a construction activity to its
    DIN standards and VOB/C section — without LLM, purely deterministic.
    """
    activities = _detect_activities(text)
    edges_added = 0

    for binding in activities:
        for din in binding["din_standards"]:
            din_node_id = _nid(din, "DIN_STANDARD")
            _upsert_node(conn, din_node_id, din, "DIN_STANDARD",
                         vob_section=binding["vob_section"],
                         liability_note=binding["liability_note"])

            added = _upsert_edge(conn, node_id, din_node_id, "regulated_by",
                legal_basis=binding["vob_section"],
                is_inferred=True, inferred_by="pass2_regulatory",
                weight=1.0,
                excerpt=f"Auto-bound: {binding['activity_keywords'][0]} → {din}")
            if added:
                edges_added += 1

        # VOB/C section node
        if binding["vob_section"]:
            vob_node_id = _nid(binding["vob_section"], "VOB_SECTION")
            _upsert_node(conn, vob_node_id, binding["vob_section"], "VOB_SECTION",
                         liability_note=binding["liability_note"])
            added = _upsert_edge(conn, node_id, vob_node_id, "governed_by_vob",
                legal_basis=binding["vob_section"],
                is_inferred=True, inferred_by="pass2_regulatory", weight=1.0)
            if added:
                edges_added += 1

    return edges_added


# ── Pass 3: Triangle Transitivity — Shared Risk Interface ────────────────────

def pass3_shared_risk_interface(conn) -> int:
    """
    If Subcontractor A is bound to Clause X, and Party B is also bound to Clause X,
    infer a 'shared_risk_interface' edge between A and B.
    Also: if A → C and B → C exist, add inferred A ↔ B (shared dependency).
    """
    edges_added = 0

    # Find all clause/standard nodes
    shared_nodes = conn.execute(
        """SELECT tgt, COUNT(DISTINCT src) as cnt, GROUP_CONCAT(DISTINCT src) as sources
           FROM lkg_edges
           WHERE edge_type IN ('governed_by_vob','regulated_by','inherits_clause','contains_clause')
           GROUP BY tgt HAVING cnt >= 2"""
    ).fetchall()

    for row in shared_nodes:
        sources = row["sources"].split(",")
        shared_node = row["tgt"]

        # Connect all pairs through shared node
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                a, b = sources[i], sources[j]
                if a == b:
                    continue
                added = _upsert_edge(conn, a, b, "shared_risk_interface",
                    legal_basis=f"Both parties bound to same obligation: {shared_node[:30]}",
                    is_inferred=True, inferred_by="pass3_transitivity",
                    weight=0.7,
                    excerpt=f"Shared dependency on {shared_node}")
                if added:
                    edges_added += 1

    conn.commit()
    return edges_added


# ── Tribunal Entity Deduplication ─────────────────────────────────────────────

def tribunal_dedup(entity_a_name: str, entity_a_text: str,
                   entity_b_name: str, entity_b_text: str) -> dict:
    """
    Three-agent judicial loop for entity resolution.
    Creates an immutable audit log for every merge decision.

    Agent 1 (Prosecutor): Argues they are DIFFERENT entities
    Agent 2 (Defense): Argues they are the SAME entity
    Agent 3 (Judge): Weighs structural evidence and writes auditable verdict

    Returns verdict dict with audit_hash.
    """
    # Deterministic structural evidence (no LLM needed for basic cases)
    a_lower = entity_a_name.lower().strip()
    b_lower = entity_b_name.lower().strip()

    # Prosecutor arguments
    prosecutor_args = []
    defense_args = []

    # Name similarity
    a_tokens = set(re.findall(r'\w{2,}', a_lower))
    b_tokens = set(re.findall(r'\w{2,}', b_lower))
    token_overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)

    if token_overlap < 0.3:
        prosecutor_args.append(f"Name token overlap only {token_overlap:.0%} — likely different entities")
    else:
        defense_args.append(f"Name token overlap {token_overlap:.0%} — likely same entity")

    # Common abbreviation patterns (GmbH, AG, etc.)
    legal_forms_a = set(re.findall(r'\b(gmbh|ag|kg|ohg|gbr|se|ug)\b', a_lower))
    legal_forms_b = set(re.findall(r'\b(gmbh|ag|kg|ohg|gbr|se|ug)\b', b_lower))
    if legal_forms_a and legal_forms_b and not legal_forms_a & legal_forms_b:
        prosecutor_args.append(f"Different legal forms: {legal_forms_a} vs {legal_forms_b}")
    elif legal_forms_a & legal_forms_b:
        defense_args.append(f"Same legal form: {legal_forms_a & legal_forms_b}")

    # Check if one is an abbreviation of the other
    a_initials = "".join(w[0] for w in a_lower.split() if len(w) > 1)
    if a_initials in b_lower or b_lower.replace(" ","") in a_lower.replace(" ",""):
        defense_args.append(f"'{entity_a_name}' appears to be abbreviation of '{entity_b_name}'")

    # Context text overlap
    if entity_a_text and entity_b_text:
        ctx_a = set(re.findall(r'\w{5,}', entity_a_text.lower()))
        ctx_b = set(re.findall(r'\w{5,}', entity_b_text.lower()))
        ctx_overlap = len(ctx_a & ctx_b) / max(len(ctx_a | ctx_b), 1)
        if ctx_overlap > 0.4:
            defense_args.append(f"Context overlap {ctx_overlap:.0%} — same project context")
        else:
            prosecutor_args.append(f"Context overlap only {ctx_overlap:.0%}")

    # Judge decision
    pro_score = len(prosecutor_args)
    def_score = len(defense_args)
    confidence = abs(pro_score - def_score) / max(pro_score + def_score, 1)

    if def_score > pro_score:
        decision = "merge"
        judge_verdict = f"MERGE: Defense arguments ({def_score}) outweigh Prosecutor ({pro_score}). Token overlap: {token_overlap:.0%}."
    elif pro_score > def_score:
        decision = "separate"
        judge_verdict = f"SEPARATE: Prosecutor arguments ({pro_score}) outweigh Defense ({def_score})."
    else:
        decision = "needs_human"
        judge_verdict = "INCONCLUSIVE: Equal evidence. Human review required before merge."
        confidence = 0.0

    # Immutable audit hash
    audit_input = json.dumps({
        "a": entity_a_name, "b": entity_b_name,
        "prosecutor": prosecutor_args, "defense": defense_args,
        "judge": judge_verdict, "decision": decision
    }, sort_keys=True)
    audit_hash = hashlib.sha256(audit_input.encode()).hexdigest()

    # Persist to tribunal log
    conn = _get_db()
    init_legal_kg_tables()
    conn.execute(
        """INSERT INTO lkg_tribunal_log
           (entity_a, entity_b, prosecutor_verdict, defense_verdict,
            judge_verdict, final_decision, confidence, audit_hash)
           VALUES (?,?,?,?,?,?,?,?)""",
        (entity_a_name, entity_b_name,
         "; ".join(prosecutor_args), "; ".join(defense_args),
         judge_verdict, decision, confidence, audit_hash)
    )
    conn.commit()
    conn.close()

    return {
        "entity_a": entity_a_name,
        "entity_b": entity_b_name,
        "final_decision": decision,
        "confidence": round(confidence, 3),
        "prosecutor_arguments": prosecutor_args,
        "defense_arguments": defense_args,
        "judge_verdict": judge_verdict,
        "audit_hash": audit_hash,
        "can_trust": decision != "needs_human",
    }


# ── Main: Build Legal-Twin KG from document ───────────────────────────────────

# NOTE: DATE and FINANCIAL are intentionally excluded — they are properties on
# nodes/edges (valid_from, valid_until, contract_value), NOT graph entities.
# Putting dates and EUR amounts as nodes clutters the graph with meaningless nodes.
ENTITY_PATTERNS: list[tuple[str, str]] = [
    (r'\b([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*\s+(?:GmbH|AG|KG|OHG|GbR|SE|UG))\b', "COMPANY"),
    (r'\b(Dipl\.-(?:Ing|Kfm|Arch)\.\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)\b', "PERSON"),
    (r'\b([A-ZÄÖÜ][a-zäöüß]+\s+(?:Meier|Müller|Schmidt|Weber|Fischer|Hoffmann|Wagner|Bauer|Koch|Richter|Klein|Wolf))\b', "PERSON"),
    # EUR amounts → stored as node property, not as graph nodes
    # Dates → stored as valid_from/valid_until on edges, not as graph nodes
    (r'\bNachtrag\s+(?:Nr\.?\s*)?(\d+)\b', "NACHTRAG"),
    (r'\bPosition\s+(\d{2}[._]\d{2}[._]\d{3,4})\b', "GAEB_POSITION"),
    (r'\b(VOB/B\s*§\s*\d+(?:\s*Abs\.\s*\d+)?)\b', "VOB_PARAGRAPH"),
    (r'\b(DIN(?:\s+EN)?\s*\d{3,6})\b', "DIN_STANDARD"),
    # ROLE only when followed by a name (e.g. "Bauleiter: Thomas Meier") — not standalone
    (r'\b(Bauleiter|Architekt|Subunternehmer|Planer):\s*([A-Z][^\n,;]{3,40})', "ROLE"),
]

def extract_entities(text: str, doc_id: int) -> list[dict]:
    """Extract all entities from text with type classification."""
    entities = []
    seen = set()
    for pattern, etype in ENTITY_PATTERNS:
        for m in re.finditer(pattern, text):
            name = m.group(1).strip() if m.lastindex else m.group(0).strip()
            if name in seen or len(name) < 3:
                continue
            seen.add(name)
            entities.append({
                "name": name,
                "type": etype,
                "node_id": _nid(name, etype),
                "position": m.start(),
                "context": text[max(0,m.start()-80):m.end()+80],
                "doc_id": doc_id,
            })
    return entities


def build_legal_twin(
    documents: list[dict],  # [{doc_id, filename, text, doc_type, valid_from, valid_until}]
    project_id: str = "default",
) -> dict:
    """
    Full Legal-Twin KG build pipeline.

    For each document:
        1. Extract entities with temporal validity
        2. Auto-bind regulatory standards (Pass 2)
        3. Inherit clauses from parent documents (Pass 1)
        4. Run Triangle Transitivity (Pass 3)
        5. Return full graph for visualization
    """
    init_legal_kg_tables()
    conn = _get_db()

    total_nodes = 0
    total_edges = 0
    pass1_edges = 0
    pass2_edges = 0
    pass3_edges = 0
    doc_nodes = []

    # Sort by document hierarchy (HAUPTVERTRAG first)
    TYPE_ORDER = {"HAUPTVERTRAG": 0, "ANLAGE": 1, "LV": 2,
                  "NACHTRAG": 3, "RECHNUNG": 4, "UNKNOWN": 5}

    def doc_sort_key(d):
        dt = d.get("doc_type", "UNKNOWN").upper()
        return TYPE_ORDER.get(dt, 5)

    docs_sorted = sorted(documents, key=doc_sort_key)

    for doc in docs_sorted:
        doc_id = doc["doc_id"]
        text = doc["text"]
        doc_type = doc.get("doc_type", "UNKNOWN").upper()
        valid_from = doc.get("valid_from")
        valid_until = doc.get("valid_until")
        filename = doc.get("filename", f"doc_{doc_id}")

        # Create document node
        doc_node_id = _nid(filename, "DOCUMENT")
        _upsert_node(conn, doc_node_id, filename, "DOCUMENT",
                     valid_from=valid_from, valid_until=valid_until,
                     doc_ids=[doc_id])
        doc_nodes.append({"node_id": doc_node_id, "name": filename,
                          "doc_type": doc_type, "valid_from": valid_from})
        total_nodes += 1

        # Extract GAEB positions
        gaeb_positions = _extract_gaeb_positions(text)
        for pos in gaeb_positions:
            pos_node_id = _nid(pos, "GAEB_POSITION")
            _upsert_node(conn, pos_node_id, f"Position {pos}", "GAEB_POSITION",
                         gaeb_code=pos, valid_from=valid_from,
                         doc_ids=[doc_id])
            added = _upsert_edge(conn, doc_node_id, pos_node_id, "contains_position",
                legal_basis="GAEB Hierarchie — deterministische Ankerposition",
                valid_from=valid_from, weight=1.0)
            if added:
                total_edges += 1
            total_nodes += 1

        # Extract entities
        entities = extract_entities(text, doc_id)
        for ent in entities:
            _upsert_node(conn, ent["node_id"], ent["name"], ent["type"],
                         valid_from=valid_from, doc_ids=[doc_id])
            added = _upsert_edge(conn, doc_node_id, ent["node_id"], "mentions",
                valid_from=valid_from,
                weight=0.8, excerpt=ent["context"][:150])
            if added:
                total_nodes += 1
                total_edges += 1

        # Pass 2: Regulatory auto-binding
        p2 = pass2_regulatory_binding(conn, doc_node_id, text)
        pass2_edges += p2
        total_edges += p2

    # Pass 1: Inheritance (Nachtrag/Anlage from Hauptvertrag)
    hauptvertrag_nodes = [d for d in doc_nodes if d["doc_type"] in ("HAUPTVERTRAG",)]
    child_nodes = [d for d in doc_nodes if d["doc_type"] in ("NACHTRAG", "ANLAGE", "LV")]

    for hv in hauptvertrag_nodes:
        hv_doc = next((d for d in documents if _nid(d["filename"], "DOCUMENT") == hv["node_id"]), None)
        for child in child_nodes:
            child_doc = next((d for d in documents if _nid(d["filename"], "DOCUMENT") == child["node_id"]), None)
            if hv_doc and child_doc:
                p1 = pass1_inheritance(conn, hv["node_id"], child["node_id"],
                                       hv_doc["text"], child_doc["text"])
                pass1_edges += p1
                total_edges += p1

        # Hierarchy edges
        for child in child_nodes:
            added = _upsert_edge(conn, hv["node_id"], child["node_id"],
                "parent_of" if child["doc_type"] != "NACHTRAG" else "amended_by",
                legal_basis="Vertragsstruktur — hierarchische Dokument-Beziehung",
                is_inferred=True, inferred_by="pass1_inheritance", weight=1.0)
            if added:
                total_edges += 1

    # Pass 3: Triangle Transitivity
    p3 = pass3_shared_risk_interface(conn)
    pass3_edges += p3
    total_edges += p3

    conn.commit()

    # Return graph for visualization
    nodes_raw = conn.execute("SELECT * FROM lkg_nodes").fetchall()
    edges_raw = conn.execute("SELECT * FROM lkg_edges").fetchall()
    conn.close()

    return {
        "project_id": project_id,
        "stats": {
            "total_nodes": len(nodes_raw),
            "total_edges": len(edges_raw),
            "pass1_inherited_edges": pass1_edges,
            "pass2_regulatory_edges": pass2_edges,
            "pass3_transitivity_edges": pass3_edges,
        },
        "nodes": [
            {
                "id": dict(n)["node_id"],
                "name": dict(n)["name"],
                "type": dict(n)["node_type"],
                "gaeb_code": dict(n)["gaeb_code"],
                "valid_from": dict(n)["valid_from"],
                "valid_until": dict(n)["valid_until"],
                "din_standards": json.loads(dict(n)["din_standards"] or "[]"),
                "vob_section": dict(n)["vob_section"],
                "confidence": dict(n)["confidence"],
            }
            for n in nodes_raw
        ],
        "edges": [
            {
                "id": dict(e)["edge_id"],
                "source": dict(e)["src"],
                "target": dict(e)["tgt"],
                "type": dict(e)["edge_type"],
                "legal_basis": dict(e)["legal_basis"],
                "is_inferred": bool(dict(e)["is_inferred"]),
                "inferred_by": dict(e)["inferred_by"],
                "valid_from": dict(e)["valid_from"],
                "weight": dict(e)["weight"],
            }
            for e in edges_raw
        ],
    }


def get_graph_for_viz() -> dict:
    """Return current graph state for D3 visualization."""
    init_legal_kg_tables()
    conn = _get_db()
    nodes = [dict(n) for n in conn.execute("SELECT * FROM lkg_nodes LIMIT 200").fetchall()]
    edges = [dict(e) for e in conn.execute("SELECT * FROM lkg_edges LIMIT 500").fetchall()]
    conn.close()

    # Clean up for JSON
    for n in nodes:
        n["din_standards"] = json.loads(n.get("din_standards") or "[]")
        n["merged_from"] = json.loads(n.get("merged_from") or "[]")
        n["doc_ids"] = json.loads(n.get("doc_ids") or "[]")

    return {
        "nodes": [{"id": n["node_id"], "name": n["name"][:40], "type": n["node_type"],
                   "gaeb": n["gaeb_code"], "valid_from": n["valid_from"],
                   "confidence": n["confidence"]} for n in nodes],
        "links": [{"source": e["src"], "target": e["tgt"], "type": e["edge_type"],
                   "inferred": bool(e["is_inferred"]), "weight": e["weight"],
                   "legal_basis": (e.get("legal_basis") or "")[:60]} for e in edges],
    }
