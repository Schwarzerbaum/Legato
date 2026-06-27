"""
Adversarial Pollination — Predator/Prey Swarm System

Deploys two opposing agent swarms over every document chunk:
  Predator Swarm (Buyer counsel) — hunts for MAC triggers, indemnity leaks,
      unlimited liability, deal-breaking conditions, change-of-control traps.
  Prey Swarm (Seller counsel) — hunts for liability caps, knowledge qualifiers,
      materiality scrapes, basket protections, seller-friendly carve-outs.

Where both swarms flag the SAME chunk → DISSONANCE pheromone explodes.
These are the exact paragraphs where the deal will blow up in negotiation.

Result: a "Heat Map of Negotiation Conflict" — visually unique, zero equivalent
in La Marca's system.

Pheromone types deposited:
  PREDATOR_SCENT  — buyer risk (chunk flagged by predator only)
  PREY_SCENT      — seller protection (chunk flagged by prey only)
  DISSONANCE      — both swarms clashed here (hottest signal, deal-break risk)
"""

import json
import re
import hashlib
from datetime import datetime, timezone
from typing import TypedDict

from ma.knowledge import get_db

# ── LLM client (mirrors jury.py pattern) ─────────────────────────────────────
try:
    import httpx
    _OLLAMA_BASE = "http://localhost:11434"
    _FAST_MODEL  = "llama3.2:3b"

    def _llm(system: str, user: str, model: str = _FAST_MODEL) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system",  "content": system},
                {"role": "user",    "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 300},
        }
        try:
            r = httpx.post(
                f"{_OLLAMA_BASE}/api/chat",
                json=payload,
                timeout=45,
            )
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception as e:
            return f"[LLM_ERROR: {e}]"

except ImportError:
    def _llm(system: str, user: str, model: str = "") -> str:  # type: ignore[misc]
        return "[LLM_UNAVAILABLE]"


# ── Swarm system prompts ──────────────────────────────────────────────────────

_PREDATOR_SYSTEM = """You are aggressive M&A buyer's counsel. Your job is to find every clause
that creates risk, unlimited liability, or deal-breaking conditions for the buyer.

Hunt for:
- MAC/MAE triggers (any event that could trigger Material Adverse Effect)
- Indemnity leaks (unlimited or uncapped seller indemnification obligations)
- Change-of-control provisions that require third-party consent
- Representations that are unconditional or impossible to satisfy
- Earn-out risks or post-closing payment obligations
- IP ownership gaps or license termination triggers
- Key-man dependencies that could collapse value post-close
- Assignment restrictions that would block integration

OUTPUT FORMAT (JSON only, no other text):
{
  "flagged": true/false,
  "risk_type": "one of: mac_trigger|indemnity_leak|coc_trap|rep_breach|earnout_risk|ip_gap|keyman|assignment_block|other",
  "severity": "critical|high|medium",
  "excerpt": "the exact dangerous phrase (max 120 chars)",
  "score": 0.0-1.0
}

If nothing dangerous found: {"flagged": false, "score": 0.0}"""


_PREY_SYSTEM = """You are seller's counsel protecting the seller's position. Your job is to find
every protective mechanism, limitation, and seller-favorable clause.

Hunt for:
- Liability caps (limits on seller's total exposure)
- Knowledge qualifiers ("to the seller's knowledge", "to the best of seller's knowledge")
- Materiality scrapes being ABSENT (seller wants them present)
- Basket/deductible protections (minimum threshold before indemnity kicks in)
- Survival limitations (short survival periods limit seller exposure)
- Seller-friendly MAC definitions (many carve-outs that protect seller)
- Specific indemnity carve-outs or exclusions
- Representations qualified by "material" or "in all material respects"

OUTPUT FORMAT (JSON only, no other text):
{
  "flagged": true/false,
  "protection_type": "one of: liability_cap|knowledge_qualifier|basket|survival_limit|mac_carveout|rep_qualifier|indemnity_exclusion|other",
  "strength": "strong|moderate|weak",
  "excerpt": "the exact protective phrase (max 120 chars)",
  "score": 0.0-1.0
}

If no seller protection found: {"flagged": false, "score": 0.0}"""


# ── Score extraction ──────────────────────────────────────────────────────────

def _parse_score(raw: str) -> tuple[bool, float, dict]:
    """Parse LLM JSON response → (flagged, score, full_data)."""
    try:
        # Extract JSON block
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return False, 0.0, {}
        data = json.loads(m.group())
        flagged = bool(data.get("flagged", False))
        score = float(data.get("score", 0.0))
        return flagged, score, data
    except Exception:
        return False, 0.0, {}


# ── Regex-based fast pre-screen (saves LLM calls on boring chunks) ────────────

_PREDATOR_PATTERNS = re.compile(
    r'material\s+adverse|MAC\b|MAE\b|change\s+of\s+control|unlimited\s+liability|'
    r'indemnif|no\s+cap|uncapped|earn[\s-]out|assignment\s+(?:requires?|needs?|without)',
    re.IGNORECASE
)
_PREY_PATTERNS = re.compile(
    r'knowledge\s+of\s+(?:the\s+)?seller|seller.s\s+knowledge|'
    r'liability\s+(?:shall\s+)?(?:not\s+exceed|cap|limit)|'
    r'basket|deductible|survival\s+(?:period|limit|shall)|'
    r'material\s+(?:adverse\s+effect\s+)?(?:shall\s+not\s+include|carve[\s-]?out)',
    re.IGNORECASE
)


def _chunk_is_interesting(text: str) -> tuple[bool, bool]:
    """Quick regex pre-screen. Returns (predator_candidate, prey_candidate)."""
    return bool(_PREDATOR_PATTERNS.search(text)), bool(_PREY_PATTERNS.search(text))


# ── Pheromone deposit ─────────────────────────────────────────────────────────

class ChunkResult(TypedDict):
    chunk_id: int
    chunk_text: str
    predator_flagged: bool
    predator_score: float
    predator_data: dict
    prey_flagged: bool
    prey_score: float
    prey_data: dict
    dissonance_score: float
    pheromone_type: str   # PREDATOR_SCENT | PREY_SCENT | DISSONANCE | NONE


def _deposit_pheromone(conn, chunk_id: int, doc_id: int, pheromone_type: str,
                        intensity: float, payload: dict) -> None:
    """Write a signal/pheromone to ma_signals and update relevant node intensities."""
    sig_id = hashlib.sha1(
        f"{pheromone_type}:{chunk_id}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:16]
    conn.execute(
        """INSERT OR REPLACE INTO ma_signals
           (id, signal_type, source_entity, source_chunk_id, source_doc_id,
            strength, payload, created_at, hops, propagated_to, is_active)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sig_id, pheromone_type,
            payload.get("excerpt", "")[:120],
            chunk_id, doc_id,
            intensity,
            json.dumps(payload),
            datetime.now(timezone.utc).isoformat(),
            0, "[]", 1,
        ),
    )
    # Update pheromone_intensity on all nodes that appear in this chunk
    nodes = conn.execute(
        "SELECT id, pheromone_intensity FROM ma_kg_nodes WHERE chunk_ids LIKE ?",
        (f"%{chunk_id}%",),
    ).fetchall()
    for node in nodes:
        current = node["pheromone_intensity"] or 0.0
        # Super-linear amplification: dissonance compounds harder
        amplifier = 1.5 if pheromone_type == "DISSONANCE" else 1.0
        new_intensity = min(1.0, current + intensity * amplifier)
        conn.execute(
            "UPDATE ma_kg_nodes SET pheromone_intensity=? WHERE id=?",
            (new_intensity, node["id"]),
        )


# ── Main runner ───────────────────────────────────────────────────────────────

def run_adversarial_pollination(
    doc_id: int,
    max_chunks: int = 80,
    use_llm: bool = True,
) -> dict:
    """
    Run the Predator/Prey swarm over all chunks of a document.
    Deposits PREDATOR_SCENT, PREY_SCENT, or DISSONANCE pheromones.
    Returns a heatmap report.
    """
    conn = get_db()
    started_at = datetime.now(timezone.utc)

    # Load chunks
    chunks = conn.execute(
        "SELECT id, text, page FROM ma_chunks WHERE doc_id=? ORDER BY page, id LIMIT ?",
        (doc_id, max_chunks),
    ).fetchall()

    if not chunks:
        conn.close()
        return {"error": f"No chunks found for doc_id={doc_id}"}

    results: list[ChunkResult] = []
    counts = {"predator_only": 0, "prey_only": 0, "dissonance": 0, "cold": 0}

    for chunk in chunks:
        cid = chunk["id"]
        text = chunk["text"]

        pred_candidate, prey_candidate = _chunk_is_interesting(text)

        # If neither regex matches and LLM enabled, skip (save tokens)
        if not pred_candidate and not prey_candidate:
            counts["cold"] += 1
            continue

        # Truncate for LLM
        chunk_prompt = text[:600]

        pred_flagged, pred_score, pred_data = False, 0.0, {}
        prey_flagged, prey_score, prey_data = False, 0.0, {}

        if use_llm:
            if pred_candidate:
                raw = _llm(_PREDATOR_SYSTEM, f"Analyse this M&A clause:\n\n{chunk_prompt}")
                pred_flagged, pred_score, pred_data = _parse_score(raw)

            if prey_candidate:
                raw = _llm(_PREY_SYSTEM, f"Analyse this M&A clause:\n\n{chunk_prompt}")
                prey_flagged, prey_score, prey_data = _parse_score(raw)
        else:
            # Regex-only scoring for fast mode
            pred_flagged = pred_candidate
            pred_score = 0.6 if pred_candidate else 0.0
            prey_flagged = prey_candidate
            prey_score = 0.6 if prey_candidate else 0.0

        # Determine pheromone type
        if pred_flagged and prey_flagged:
            # DISSONANCE: both swarms clash here
            dissonance = min(1.0, (pred_score + prey_score) * 0.7)
            ptype = "DISSONANCE"
            intensity = dissonance
            counts["dissonance"] += 1
        elif pred_flagged:
            ptype = "PREDATOR_SCENT"
            intensity = pred_score
            dissonance = 0.0
            counts["predator_only"] += 1
        elif prey_flagged:
            ptype = "PREY_SCENT"
            intensity = prey_score
            dissonance = 0.0
            counts["prey_only"] += 1
        else:
            counts["cold"] += 1
            continue

        payload = {
            "predator": pred_data,
            "prey": prey_data,
            "excerpt": (pred_data.get("excerpt") or prey_data.get("excerpt") or text[:120]),
            "page": chunk["page"],
        }
        _deposit_pheromone(conn, cid, doc_id, ptype, intensity, payload)

        results.append(ChunkResult(
            chunk_id=cid,
            chunk_text=text[:200],
            predator_flagged=pred_flagged,
            predator_score=pred_score,
            predator_data=pred_data,
            prey_flagged=prey_flagged,
            prey_score=prey_score,
            prey_data=prey_data,
            dissonance_score=dissonance if ptype == "DISSONANCE" else 0.0,
            pheromone_type=ptype,
        ))

    conn.commit()

    # Sort by dissonance first, then by score
    results.sort(key=lambda r: (r["dissonance_score"], r["predator_score"] + r["prey_score"]), reverse=True)

    duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

    conn.close()
    return {
        "doc_id": doc_id,
        "chunks_scanned": len(chunks),
        "counts": counts,
        "top_conflicts": [
            {
                "chunk_id": r["chunk_id"],
                "pheromone_type": r["pheromone_type"],
                "dissonance_score": round(r["dissonance_score"], 3),
                "predator_score": round(r["predator_score"], 3),
                "prey_score": round(r["prey_score"], 3),
                "predator_risk": r["predator_data"].get("risk_type", ""),
                "prey_protection": r["prey_data"].get("protection_type", ""),
                "excerpt": r["predator_data"].get("excerpt") or r["prey_data"].get("excerpt") or r["chunk_text"][:120],
                "page": r["predator_data"].get("page"),
            }
            for r in results[:15]
        ],
        "summary": (
            f"{counts['dissonance']} conflict zones, "
            f"{counts['predator_only']} buyer risks, "
            f"{counts['prey_only']} seller protections"
        ),
        "duration_ms": duration_ms,
    }


def get_pollination_heatmap(doc_id: int) -> dict:
    """
    Returns current pheromone state for a doc — for UI heatmap rendering.
    Groups chunks by pheromone type with intensity scores.
    """
    conn = get_db()
    signals = conn.execute(
        """SELECT signal_type, source_chunk_id, strength, payload, created_at
           FROM ma_signals
           WHERE source_doc_id=? AND signal_type IN ('PREDATOR_SCENT','PREY_SCENT','DISSONANCE')
           ORDER BY strength DESC""",
        (doc_id,),
    ).fetchall()

    heatmap = []
    for s in signals:
        try:
            payload = json.loads(s["payload"] or "{}")
        except Exception:
            payload = {}
        heatmap.append({
            "chunk_id": s["source_chunk_id"],
            "type": s["signal_type"],
            "intensity": round(s["strength"], 3),
            "excerpt": payload.get("excerpt", "")[:120],
            "page": payload.get("page"),
            "predator_risk": payload.get("predator", {}).get("risk_type", ""),
            "prey_protection": payload.get("prey", {}).get("protection_type", ""),
        })

    # Hot nodes — nodes with pheromone_intensity > 0 in this doc
    hot_nodes = conn.execute(
        """SELECT name, entity_type, pheromone_intensity
           FROM ma_kg_nodes
           WHERE doc_ids LIKE ? AND pheromone_intensity > 0.05
           ORDER BY pheromone_intensity DESC
           LIMIT 20""",
        (f"%{doc_id}%",),
    ).fetchall()

    conn.close()
    return {
        "doc_id": doc_id,
        "heatmap": heatmap,
        "hot_nodes": [
            {"name": n["name"], "type": n["entity_type"], "intensity": round(n["pheromone_intensity"], 3)}
            for n in hot_nodes
        ],
        "dissonance_count": sum(1 for h in heatmap if h["type"] == "DISSONANCE"),
        "predator_count": sum(1 for h in heatmap if h["type"] == "PREDATOR_SCENT"),
        "prey_count": sum(1 for h in heatmap if h["type"] == "PREY_SCENT"),
    }
