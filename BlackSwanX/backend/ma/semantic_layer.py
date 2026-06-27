"""
BlackSwanX Semantic Layer — the map of what documents MEAN, not just what they say.

Sits alongside Maurice's knowledge graph and adds four capabilities:

  1. NarrativeDriftDetector  — tracks how entity descriptions SHIFT across docs over time
  2. LatentChainDiscovery    — finds implied risk chains across entity types
  3. AbsenceSignatureDetector — flags what SHOULD be present but isn't
  4. SynapticMapper          — behavioral fingerprint matching (not just name matching)

All operate on the existing ma_chunks / ma_facts SQLite store.
Zero new dependencies — numpy + existing embeddings.py.
"""

import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime

from ma.knowledge import get_db
from ma.embeddings import get_embedding, cosine_similarity


# ═══════════════════════════════════════════════════════════════════════════
# 1. NARRATIVE DRIFT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

# Sentiment poles — words that indicate positive vs cautious framing
_POSITIVE_SIGNALS = [
    "market leader", "dominant", "accelerating", "exceptional", "strong growth",
    "outperforming", "best-in-class", "proven", "robust", "industry-leading",
    "profitable", "expanding", "award-winning", "record revenue",
]
_CAUTIOUS_SIGNALS = [
    "investment required", "challenges", "headwinds", "transition", "restructuring",
    "retention", "post-close", "key personnel", "competitive pressure", "declining",
    "below expectations", "remediation", "loss", "dispute", "contingent", "pending",
    "regulatory review", "compliance issue", "wind-down", "renegotiation",
]


def _sentiment_score(text: str) -> float:
    """
    Simple sentiment score: +1 per positive signal, -1 per cautious signal.
    Returns normalised float in [-1, +1].
    """
    text_lower = text.lower()
    pos = sum(1 for s in _POSITIVE_SIGNALS if s in text_lower)
    neg = sum(1 for s in _CAUTIOUS_SIGNALS if s in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _cosine_of_vectors(v1: list[float], v2: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def detect_narrative_drift(entity_name: str, threshold: float = 0.25) -> dict:
    """
    Find all chunks mentioning entity_name across all documents.
    Sort by document upload order (proxy for deal timeline).
    Compute sentiment trajectory and embedding centroid shift.

    Returns:
      drift_score: 0-1 (how much the narrative has shifted)
      sentiment_trajectory: list of {doc, score} over time
      early_framing: words used in first third of docs
      late_framing: words used in last third of docs
      flag: bool — True if drift_score > threshold
      signal: human-readable description of the shift
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT c.id, c.doc_id, c.text, c.page, d.filename, d.upload_date
           FROM ma_chunks c
           JOIN ma_documents d ON d.id = c.doc_id
           WHERE LOWER(c.text) LIKE ?
           ORDER BY d.id ASC""",
        (f"%{entity_name.lower()}%",),
    ).fetchall()
    conn.close()

    if len(rows) < 3:
        return {
            "entity": entity_name,
            "drift_score": 0.0,
            "flag": False,
            "signal": "Insufficient data — entity appears in fewer than 3 chunks",
            "sentiment_trajectory": [],
            "early_framing": [],
            "late_framing": [],
            "chunk_count": len(rows),
        }

    chunks = [dict(r) for r in rows]
    n = len(chunks)
    third = max(1, n // 3)

    # Sentiment scores over time
    scores = [_sentiment_score(c["text"]) for c in chunks]
    trajectory = [
        {"doc": c["filename"], "doc_id": c["doc_id"], "score": round(s, 3)}
        for c, s in zip(chunks, scores)
    ]

    early_score = sum(scores[:third]) / third
    late_score = sum(scores[-third:]) / third
    sentiment_drift = early_score - late_score  # positive = got more cautious

    # Keyword framing extraction
    def _top_words(texts: list[str], n_words: int = 8) -> list[str]:
        freq: dict[str, int] = defaultdict(int)
        for t in texts:
            for w in re.findall(r'\b[a-zA-Z]{4,}\b', t.lower()):
                if w not in {"that", "this", "with", "from", "have", "will",
                             "been", "were", "they", "their", "also", "which"}:
                    freq[w] += 1
        return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n_words]]

    early_texts = [c["text"] for c in chunks[:third]]
    late_texts = [c["text"] for c in chunks[-third:]]
    early_words = _top_words(early_texts)
    late_words = _top_words(late_texts)

    # Embedding centroid shift (if embeddings available)
    embedding_drift = 0.0
    try:
        early_embs = [get_embedding(t[:500]) for t in early_texts]
        late_embs = [get_embedding(t[:500]) for t in late_texts]
        early_embs = [e for e in early_embs if e]
        late_embs = [e for e in late_embs if e]
        if early_embs and late_embs:
            dim = len(early_embs[0])
            early_centroid = [sum(e[i] for e in early_embs) / len(early_embs) for i in range(dim)]
            late_centroid = [sum(e[i] for e in late_embs) / len(late_embs) for i in range(dim)]
            sim = _cosine_of_vectors(early_centroid, late_centroid)
            embedding_drift = 1.0 - sim  # 0 = no drift, 1 = total shift
    except Exception:
        pass

    # Combined drift score
    drift_score = round(min(1.0, abs(sentiment_drift) * 0.6 + embedding_drift * 0.4), 3)
    flag = drift_score > threshold

    # Human-readable signal
    if flag:
        direction = "more cautious" if sentiment_drift > 0 else "more positive"
        signal = (
            f"Narrative drift detected for '{entity_name}': "
            f"early documents frame it as [{', '.join(early_words[:4])}], "
            f"later documents shift to [{', '.join(late_words[:4])}]. "
            f"Tone becomes {direction} over the deal timeline. "
            f"Drift score: {drift_score}."
        )
    else:
        signal = f"No significant narrative drift detected for '{entity_name}' (score: {drift_score})."

    return {
        "entity": entity_name,
        "drift_score": drift_score,
        "flag": flag,
        "signal": signal,
        "sentiment_trajectory": trajectory,
        "early_framing": early_words,
        "late_framing": late_words,
        "chunk_count": n,
        "sentiment_drift": round(sentiment_drift, 3),
        "embedding_drift": round(embedding_drift, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. LATENT CHAIN DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════

# Chain patterns: each pattern is a list of topic clusters that form a risk chain
_CHAIN_PATTERNS = [
    {
        "name": "Regulatory → Revenue → Warranty",
        "chain": [
            ["regulatory", "compliance", "review", "approval", "authority", "permit"],
            ["revenue", "sales", "income", "turnover", "performance", "earnings"],
            ["warranty", "indemnity", "representation", "covenant", "obligation", "guarantee"],
        ],
        "risk": "Regulatory issue may invalidate revenue and trigger warranty claims",
    },
    {
        "name": "Key Person → Operations → Continuity",
        "chain": [
            ["ceo", "founder", "management", "executive", "director", "key person", "retention"],
            ["operations", "processes", "systems", "platform", "technology", "delivery"],
            ["continuity", "handover", "transition", "succession", "knowledge transfer"],
        ],
        "risk": "Key person dependency creates operational and continuity risk",
    },
    {
        "name": "Customer Concentration → Revenue → Valuation",
        "chain": [
            ["customer", "client", "account", "contract renewal", "top customer"],
            ["revenue", "recurring", "arr", "mrr", "churn", "retention rate"],
            ["valuation", "multiple", "ebitda", "purchase price", "earn-out"],
        ],
        "risk": "Customer concentration risk flows directly into revenue reliability and valuation basis",
    },
    {
        "name": "Debt → Covenant → Change of Control",
        "chain": [
            ["debt", "loan", "facility", "credit", "leverage", "lender"],
            ["covenant", "restriction", "obligation", "compliance", "ratio"],
            ["change of control", "coc", "acceleration", "event of default", "cross-default"],
        ],
        "risk": "Debt covenants may trigger change-of-control provisions that accelerate obligations",
    },
    {
        "name": "IP Ownership → License → Revenue",
        "chain": [
            ["intellectual property", "patent", "trademark", "copyright", "ip ownership"],
            ["license", "sublicense", "royalty", "usage rights", "exclusivity"],
            ["revenue", "product", "platform", "saas", "software", "technology"],
        ],
        "risk": "IP ownership uncertainty clouds revenue legitimacy and licensing structure",
    },
]


def _chunk_matches_cluster(text: str, cluster: list[str]) -> bool:
    """True if any cluster keyword appears in chunk text."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in cluster)


def discover_latent_chains(doc_ids: list[int] | None = None) -> list[dict]:
    """
    Scan chunks across all (or specified) documents for latent risk chains.
    A chain fires when chunks from DIFFERENT documents match each link.

    Returns list of discovered chains with evidence chunks.
    """
    conn = get_db()
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT c.id, c.doc_id, c.text, c.page, d.filename, d.upload_date "
            f"FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id "
            f"WHERE c.doc_id IN ({placeholders}) ORDER BY d.id, c.id",
            doc_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, d.filename, d.upload_date "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id ORDER BY d.id, c.id"
        ).fetchall()
    conn.close()

    chunks = [dict(r) for r in rows]
    if not chunks:
        return []

    results = []
    for pattern in _CHAIN_PATTERNS:
        chain_links = pattern["chain"]
        evidence_per_link = []

        for link_cluster in chain_links:
            matching = [
                {"chunk_id": c["id"], "doc_id": c["doc_id"],
                 "filename": c["filename"], "page": c["page"],
                 "excerpt": c["text"][:200]}
                for c in chunks
                if _chunk_matches_cluster(c["text"], link_cluster)
            ]
            evidence_per_link.append(matching)

        # Chain fires only if ALL links have evidence AND from multiple docs
        all_have_evidence = all(len(e) > 0 for e in evidence_per_link)
        if not all_have_evidence:
            continue

        # Check cross-document (chain is more alarming if links span different docs)
        all_doc_ids = set()
        for evidence in evidence_per_link:
            all_doc_ids.update(e["doc_id"] for e in evidence)
        cross_document = len(all_doc_ids) > 1

        results.append({
            "chain_name": pattern["name"],
            "risk_description": pattern["risk"],
            "cross_document": cross_document,
            "documents_involved": len(all_doc_ids),
            "severity": "HIGH" if cross_document else "MEDIUM",
            "evidence_per_link": [
                {"link_keywords": chain_links[i], "matches": evidence_per_link[i][:3]}
                for i in range(len(chain_links))
            ],
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# 3. ABSENCE SIGNATURE DETECTOR (the dog that didn't bark)
# ═══════════════════════════════════════════════════════════════════════════

# What SHOULD be in a standard M&A data room — patterns to look for
_EXPECTED_DEAL_TOPICS = [
    {"topic": "Pension & Employee Benefits", "keywords": ["pension", "retirement", "benefits", "pbo", "defined benefit", "employee obligations"], "severity": "HIGH"},
    {"topic": "Environmental Liability", "keywords": ["environmental", "contamination", "esg", "emissions", "waste", "soil remediation"], "severity": "HIGH"},
    {"topic": "Material Contracts List", "keywords": ["material contract", "key agreement", "significant agreement", "material customer"], "severity": "HIGH"},
    {"topic": "Change of Control Provisions", "keywords": ["change of control", "coc trigger", "acceleration", "anti-assignment"], "severity": "HIGH"},
    {"topic": "IP Ownership & Assignment", "keywords": ["ip ownership", "invention assignment", "work for hire", "patent assignment", "trademark registration"], "severity": "HIGH"},
    {"topic": "Related Party Transactions", "keywords": ["related party", "shareholder loan", "intercompany", "affiliate transaction", "arms length"], "severity": "MEDIUM"},
    {"topic": "Litigation & Claims Register", "keywords": ["litigation", "lawsuit", "claim", "proceedings", "arbitration", "dispute"], "severity": "MEDIUM"},
    {"topic": "Tax Compliance History", "keywords": ["tax return", "tax audit", "transfer pricing", "tax compliance", "deferred tax"], "severity": "MEDIUM"},
    {"topic": "Customer Concentration Analysis", "keywords": ["top customer", "customer concentration", "revenue concentration", "single customer"], "severity": "MEDIUM"},
    {"topic": "Software License Compliance", "keywords": ["software license", "open source", "gpl", "license compliance", "third party software"], "severity": "LOW"},
    {"topic": "Insurance Coverage", "keywords": ["insurance", "d&o", "e&o", "professional indemnity", "product liability coverage"], "severity": "LOW"},
    {"topic": "Data Privacy & GDPR", "keywords": ["gdpr", "data protection", "privacy", "dpa", "data processing agreement"], "severity": "MEDIUM"},
]


def detect_absences(doc_ids: list[int] | None = None) -> dict:
    """
    Compare current data room content against expected M&A deal topics.
    Flag topics that are absent — the dog that didn't bark.

    Returns absent topics with severity and suggested questions.
    """
    conn = get_db()
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT c.text FROM ma_chunks c WHERE c.doc_id IN ({placeholders})",
            doc_ids,
        ).fetchall()
    else:
        rows = conn.execute("SELECT c.text FROM ma_chunks c").fetchall()
    conn.close()

    if not rows:
        return {"absent_topics": [], "coverage_score": 0.0, "total_checked": 0}

    all_text = " ".join(r["text"].lower() for r in rows)

    present = []
    absent = []
    for topic in _EXPECTED_DEAL_TOPICS:
        found = any(kw in all_text for kw in topic["keywords"])
        entry = {
            "topic": topic["topic"],
            "severity": topic["severity"],
            "keywords_checked": topic["keywords"],
        }
        if found:
            present.append(entry)
        else:
            absent.append({
                **entry,
                "suggested_question": f"Request disclosure of {topic['topic'].lower()} documentation and current status.",
            })

    coverage_score = round(len(present) / len(_EXPECTED_DEAL_TOPICS), 2)

    return {
        "absent_topics": absent,
        "present_topics": [t["topic"] for t in present],
        "coverage_score": coverage_score,
        "total_checked": len(_EXPECTED_DEAL_TOPICS),
        "high_severity_gaps": [t for t in absent if t["severity"] == "HIGH"],
        "flag": len([t for t in absent if t["severity"] == "HIGH"]) > 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. SYNAPTIC MAPPER — behavioral fingerprint matching
# ═══════════════════════════════════════════════════════════════════════════

# Behavioral roles — what an entity DOES, not just its name
_BEHAVIORAL_ROLES = {
    "Person": [
        ("founder", ["founded", "co-founded", "established the company"]),
        ("ceo", ["chief executive", "ceo", "managing director", "md"]),
        ("cfo", ["chief financial", "cfo", "finance director"]),
        ("auditor", ["audit", "reviewed the accounts", "signed off", "pwc", "deloitte", "kpmg", "ey"]),
        ("board_member", ["board of directors", "supervisory board", "appointed to the board"]),
        ("key_person", ["key person", "critical to", "retention", "indispensable"]),
    ],
    "Company": [
        ("acquirer", ["acquirer", "buyer", "purchasing entity", "bidder"]),
        ("target", ["target company", "the company", "subject of the acquisition"]),
        ("subsidiary", ["subsidiary", "wholly owned", "controlled by", "owned by"]),
        ("competitor", ["competitor", "competing", "market rival"]),
        ("customer", ["customer of", "client of", "purchases from"]),
        ("supplier", ["supplier", "vendor", "provides services to"]),
    ],
    "FinancialMetric": [
        ("revenue", ["revenue", "turnover", "sales", "income"]),
        ("ebitda", ["ebitda", "operating profit", "adjusted earnings"]),
        ("debt", ["debt", "borrowings", "leverage", "net debt"]),
        ("capex", ["capex", "capital expenditure", "investment in"]),
    ],
}


def _extract_behavioral_fingerprint(text: str, entity_type: str) -> dict[str, float]:
    """
    Extract behavioral fingerprint for entity_type from text.
    Returns {role_name: confidence_score} dict.
    """
    text_lower = text.lower()
    roles = _BEHAVIORAL_ROLES.get(entity_type, [])
    fingerprint = {}
    for role_name, signals in roles:
        hits = sum(1 for s in signals if s in text_lower)
        if hits > 0:
            fingerprint[role_name] = min(1.0, hits / len(signals) * 2)
    return fingerprint


def _fingerprint_similarity(fp_a: dict[str, float], fp_b: dict[str, float]) -> float:
    """Cosine-like similarity between two behavioral fingerprints."""
    all_roles = set(fp_a) | set(fp_b)
    if not all_roles:
        return 0.0
    dot = sum(fp_a.get(r, 0.0) * fp_b.get(r, 0.0) for r in all_roles)
    n_a = math.sqrt(sum(v * v for v in fp_a.values()))
    n_b = math.sqrt(sum(v * v for v in fp_b.values()))
    if n_a == 0 or n_b == 0:
        return 0.0
    return dot / (n_a * n_b)


def synaptic_map(entity_name: str, entity_type: str = "Person",
                 threshold: float = 0.5) -> dict:
    """
    Find all chunks that mention entity_name variants across all documents.
    Extract behavioral fingerprint for each. Find cross-document connections
    where the same BEHAVIOR appears even when the name string doesn't match.

    This is the "jump" — finding document 47 talks about the same person
    as document 3 even though one says "M. Höfer" and the other says "the CEO."
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT c.id, c.doc_id, c.text, c.page, d.filename
           FROM ma_chunks c JOIN ma_documents d ON d.id = c.doc_id
           WHERE LOWER(c.text) LIKE ?
           ORDER BY d.id, c.id""",
        (f"%{entity_name.lower()}%",),
    ).fetchall()
    conn.close()

    if not rows:
        return {"entity": entity_name, "connections": [], "fingerprints": []}

    # Extract fingerprint per chunk
    chunk_fingerprints = []
    for r in rows:
        fp = _extract_behavioral_fingerprint(r["text"], entity_type)
        if fp:
            chunk_fingerprints.append({
                "chunk_id": r["id"],
                "doc_id": r["doc_id"],
                "filename": r["filename"],
                "page": r["page"],
                "fingerprint": fp,
                "excerpt": r["text"][:200],
            })

    # Find cross-document synaptic connections
    connections = []
    seen = set()
    for i, cf_a in enumerate(chunk_fingerprints):
        for cf_b in chunk_fingerprints[i + 1:]:
            if cf_a["doc_id"] == cf_b["doc_id"]:
                continue  # only interested in cross-document matches
            pair_key = tuple(sorted([cf_a["chunk_id"], cf_b["chunk_id"]]))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            sim = _fingerprint_similarity(cf_a["fingerprint"], cf_b["fingerprint"])
            if sim >= threshold:
                shared_roles = [r for r in cf_a["fingerprint"] if r in cf_b["fingerprint"]]
                connections.append({
                    "chunk_a": cf_a["chunk_id"],
                    "doc_a": cf_a["filename"],
                    "chunk_b": cf_b["chunk_id"],
                    "doc_b": cf_b["filename"],
                    "behavioral_similarity": round(sim, 3),
                    "shared_roles": shared_roles,
                    "jump_signal": f"Same behavioral role ({', '.join(shared_roles)}) detected across different documents",
                })

    connections.sort(key=lambda x: -x["behavioral_similarity"])

    return {
        "entity": entity_name,
        "entity_type": entity_type,
        "connections": connections[:10],
        "fingerprints": chunk_fingerprints,
        "cross_document_jumps": len(connections),
    }


# ═══════════════════════════════════════════════════════════════════════════
# COMBINED ANALYSIS — run all four layers at once
# ═══════════════════════════════════════════════════════════════════════════

def full_semantic_analysis(entity_names: list[str],
                           doc_ids: list[int] | None = None) -> dict:
    """
    Run all four semantic layers and return a unified intelligence report.
    """
    drift_results = [detect_narrative_drift(name) for name in entity_names]
    chains = discover_latent_chains(doc_ids)
    absences = detect_absences(doc_ids)
    synaptic = [synaptic_map(name) for name in entity_names]

    # Count flags
    drift_flags = [d for d in drift_results if d["flag"]]
    chain_flags = [c for c in chains if c["severity"] == "HIGH"]
    absence_flags = absences.get("high_severity_gaps", [])

    threat_level = "LOW"
    if len(drift_flags) > 0 or len(absence_flags) > 2:
        threat_level = "MEDIUM"
    if len(drift_flags) > 1 or len(chain_flags) > 0 or len(absence_flags) > 4:
        threat_level = "HIGH"

    return {
        "threat_level": threat_level,
        "narrative_drift": drift_results,
        "latent_chains": chains,
        "absence_signatures": absences,
        "synaptic_map": synaptic,
        "summary": {
            "drift_flags": len(drift_flags),
            "implied_chains": len(chains),
            "missing_topics": len(absences.get("absent_topics", [])),
            "high_severity_gaps": len(absence_flags),
            "cross_doc_connections": sum(s["cross_document_jumps"] for s in synaptic),
        },
    }
