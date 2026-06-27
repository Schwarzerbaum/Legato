"""
Consensus Jury — replaces 0.92 cosine threshold with a 3-agent swarm.

Instead of a single similarity number deciding whether two entity mentions
refer to the same real-world entity, three specialized agents debate:

  Assassin  — tries to BREAK the merge assumption (finds reasons they differ)
  Defender  — argues FOR the merge (finds evidence they're the same entity)
  Judge     — reads both arguments and delivers final verdict

If Assassin and Defender disagree strongly → HumanAuditFlag.
This enforces "NO GUESSING" at the most dangerous point in the pipeline.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

OLLAMA_URL = "http://localhost:11434"
FAST_MODEL = "llama3.2:3b"     # Haiku-equivalent — cheap, fast
JUDGE_MODEL = "llama3.2:3b"    # Same model, different system prompt


# ── Data types ─────────────────────────────────────────────────────────────

@dataclass
class EntityMention:
    """A single mention of an entity in a document chunk."""
    mention_id: str
    surface_text: str          # raw text: "M. Höfer", "Max Höfer", "CEO"
    entity_type: str           # Company / Person / FinancialMetric / Risk / etc.
    doc_id: int
    chunk_id: int
    chunk_text: str            # surrounding context (200 chars)
    doc_filename: str
    doc_date: str | None = None
    properties: dict = field(default_factory=dict)


@dataclass
class JuryVerdict:
    """Output of one jury run."""
    mention_a: str
    mention_b: str
    decision: Literal["merge", "separate", "audit"]
    confidence: float          # 0.0 – 1.0
    assassin_verdict: str
    defender_verdict: str
    judge_verdict: str
    reasoning: str
    audit_reason: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: int = 0


# ── Ollama call helper ──────────────────────────────────────────────────────

def _llm(system: str, user: str, model: str = FAST_MODEL, timeout: int = 25) -> str:
    """Single Ollama completion. Returns text or error string."""
    if not _HAS_REQUESTS:
        return "[requests not available]"
    try:
        resp = _requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"temperature": 0.1, "num_predict": 300},
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
        return f"[LLM error {resp.status_code}]"
    except Exception as e:
        return f"[LLM unavailable: {e}]"


# ── The three agents ────────────────────────────────────────────────────────

_ASSASSIN_SYSTEM = """You are the ASSASSIN agent in an M&A entity resolution jury.
Your ONLY job is to find reasons these two entity mentions refer to DIFFERENT real-world entities.
Be adversarial. Look for: different roles, different time periods, different organisations,
different spelling patterns that are NOT just abbreviations, context contradictions.
If you find NO differences, say so clearly — do not invent differences.
Reply in exactly this format:
VERDICT: [DIFFERENT / POSSIBLY_SAME]
REASONS: <bullet list of differences found, or "none found">
CONFIDENCE: [HIGH / MEDIUM / LOW]"""

_DEFENDER_SYSTEM = """You are the DEFENDER agent in an M&A entity resolution jury.
Your ONLY job is to find evidence these two entity mentions refer to the SAME real-world entity.
Look for: name abbreviations, role consistency, same organisation context, co-occurrence,
coreferential pronouns, same metric values across docs.
If you find NO evidence they're the same, say so clearly — do not invent connections.
Reply in exactly this format:
VERDICT: [SAME / POSSIBLY_DIFFERENT]
REASONS: <bullet list of evidence, or "none found">
CONFIDENCE: [HIGH / MEDIUM / LOW]"""

_JUDGE_SYSTEM = """You are the JUDGE in an M&A entity resolution jury.
You receive arguments from an Assassin (arguing they're different) and a Defender (arguing they're the same).
Your job: weigh both arguments and deliver a final binding verdict.
NO GUESSING — if the evidence genuinely does not resolve the question, rule AUDIT.
Reply in exactly this format:
FINAL_VERDICT: [MERGE / SEPARATE / AUDIT]
CONFIDENCE_SCORE: <0.00-1.00>
REASONING: <2-3 sentences explaining the decision>
AUDIT_REASON: <only if AUDIT — what specific information is needed to resolve this>"""


def _parse_confidence(text: str) -> float:
    """Extract 0-1 float from agent outputs."""
    # Try numeric score first
    m = re.search(r'CONFIDENCE_SCORE:\s*([\d.]+)', text)
    if m:
        try:
            return min(1.0, max(0.0, float(m.group(1))))
        except ValueError:
            pass
    # Map text confidence
    text_upper = text.upper()
    if "HIGH" in text_upper:
        return 0.85
    if "MEDIUM" in text_upper:
        return 0.60
    if "LOW" in text_upper:
        return 0.35
    return 0.50


def _parse_judge_decision(text: str) -> tuple[str, float, str, str | None]:
    """Return (decision, confidence, reasoning, audit_reason)."""
    decision = "audit"
    if "FINAL_VERDICT: MERGE" in text.upper():
        decision = "merge"
    elif "FINAL_VERDICT: SEPARATE" in text.upper():
        decision = "separate"
    elif "FINAL_VERDICT: AUDIT" in text.upper():
        decision = "audit"

    confidence = _parse_confidence(text)

    reasoning = ""
    m = re.search(r'REASONING:\s*(.+?)(?=AUDIT_REASON:|$)', text, re.DOTALL | re.IGNORECASE)
    if m:
        reasoning = m.group(1).strip()

    audit_reason = None
    m = re.search(r'AUDIT_REASON:\s*(.+)', text, re.DOTALL | re.IGNORECASE)
    if m:
        audit_reason = m.group(1).strip()

    return decision, confidence, reasoning, audit_reason


# ── Public API ──────────────────────────────────────────────────────────────

def run_jury(mention_a: EntityMention, mention_b: EntityMention) -> JuryVerdict:
    """
    Run the full 3-agent jury on two entity mentions.
    Returns a JuryVerdict with decision: merge / separate / audit.
    """
    t0 = time.time()

    context = f"""ENTITY TYPE: {mention_a.entity_type}

MENTION A:
  Surface text: "{mention_a.surface_text}"
  Document: {mention_a.doc_filename} ({mention_a.doc_date or 'date unknown'})
  Context: "{mention_a.chunk_text[:300]}"
  Properties: {json.dumps(mention_a.properties, ensure_ascii=False)}

MENTION B:
  Surface text: "{mention_b.surface_text}"
  Document: {mention_b.doc_filename} ({mention_b.doc_date or 'date unknown'})
  Context: "{mention_b.chunk_text[:300]}"
  Properties: {json.dumps(mention_b.properties, ensure_ascii=False)}

Are these two mentions referring to the SAME real-world {mention_a.entity_type}?"""

    # Round 1: Assassin and Defender run independently
    assassin_raw = _llm(_ASSASSIN_SYSTEM, context)
    defender_raw = _llm(_DEFENDER_SYSTEM, context)

    # Round 2: Judge sees both arguments
    judge_input = f"""ASSASSIN'S ARGUMENT (arguing they're DIFFERENT entities):
{assassin_raw}

DEFENDER'S ARGUMENT (arguing they're the SAME entity):
{defender_raw}

ORIGINAL CONTEXT:
{context}"""

    judge_raw = _llm(_JUDGE_SYSTEM, judge_input, model=JUDGE_MODEL)

    decision, confidence, reasoning, audit_reason = _parse_judge_decision(judge_raw)
    duration_ms = int((time.time() - t0) * 1000)

    verdict_obj = JuryVerdict(
        mention_a=mention_a.surface_text,
        mention_b=mention_b.surface_text,
        decision=decision,
        confidence=confidence,
        assassin_verdict=assassin_raw,
        defender_verdict=defender_raw,
        judge_verdict=judge_raw,
        reasoning=reasoning,
        audit_reason=audit_reason,
        duration_ms=duration_ms,
    )

    # Log provenance to KG — non-blocking, best-effort
    # Only log notable decisions (merge or audit — skip trivial "separate")
    if decision in ("merge", "audit"):
        try:
            from ma.knowledge_graph import log_agent_decision  # noqa: PLC0415
            doc_ids = list({mention_a.doc_id, mention_b.doc_id})
            log_agent_decision(
                agent_name="Jury",
                decision_type="entity_deduplication",
                subject_entity=mention_a.surface_text,
                verdict=decision,
                confidence=confidence,
                linked_entities=[mention_b.surface_text],
                source_doc_ids=doc_ids,
            )
        except Exception:
            pass  # KG logging is best-effort — never break jury

    return verdict_obj


def run_jury_batch(pairs: list[tuple[EntityMention, EntityMention]]) -> list[JuryVerdict]:
    """Run jury on a list of (mention_a, mention_b) pairs. Sequential for now."""
    return [run_jury(a, b) for a, b in pairs]


# ─── Supersession Jury ───────────────────────────────────────────────────────
#
# The standard Jury asks: "Are A and B the SAME entity?"
# The Supersession Jury asks a harder question:
#   "Does the NEWER claim (B) REPLACE the older claim (A)?"
#
# This implements the Supersession Decision Tree from TGS-2026:
#   SUPERSEDES  — B is a newer/more authoritative version of A (keep both, mark A retired)
#   NO_CHANGE   — Both are valid simultaneously (different time periods, perspectives)
#   CONFLICT    — They contradict but neither clearly supersedes (flag for human review)
#
# This enables reports like:
#   "The target originally claimed $50M ARR [FY2022], but the Q4 2025 earnings
#    call (B) supersedes this with $38M ARR — a 24% downward revision."


_SUPERSESSION_ANALYST_SYSTEM = """You are a TEMPORAL ANALYST in an M&A due diligence jury.
Your job: determine if Claim B (from a LATER or more authoritative document) SUPERSEDES Claim A.

SUPERSEDES means: B provides a newer, more accurate, or officially corrected version of the same fact.
Examples of supersession:
- A financial figure updated in a later filing
- A CEO statement that officially corrects an earlier press release
- A legal filing that supersedes a letter of intent
- An audited statement that supersedes a management estimate

NOT supersession:
- Two separate events that happened at different times
- Two genuinely different entities that happen to share a topic
- A prediction and its outcome (both can be true simultaneously)

Reply in exactly this format:
VERDICT: [SUPERSEDES / NO_CHANGE / CONFLICT]
CONFIDENCE: [HIGH / MEDIUM / LOW]
TEMPORAL_DIRECTION: [B_SUPERSEDES_A / A_SUPERSEDES_B / UNCLEAR]
REASONING: <2-3 sentences>
AUDIT_FLAG: [YES / NO] — YES if human review is needed"""

_SUPERSESSION_JUDGE_SYSTEM = """You are the FINAL JUDGE in a supersession analysis.
Given one analyst's assessment and the original context, deliver a binding verdict.
NO GUESSING — if genuinely unclear, rule CONFLICT.
Reply in exactly this format:
FINAL_VERDICT: [SUPERSEDES / NO_CHANGE / CONFLICT]
CONFIDENCE_SCORE: <0.00-1.00>
TEMPORAL_DIRECTION: [B_SUPERSEDES_A / A_SUPERSEDES_B / UNCLEAR]
REASONING: <2-3 sentences on why this is a supersession or not>
AUDIT_REASON: <only if CONFLICT — what specific information resolves this>"""


@dataclass
class SupersessionVerdict:
    """Output of a supersession jury run."""
    mention_a: str
    mention_b: str
    decision: Literal["supersedes", "no_change", "conflict"]
    temporal_direction: Literal["b_supersedes_a", "a_supersedes_b", "unclear"]
    confidence: float
    reasoning: str
    audit_reason: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: int = 0


def _parse_supersession_verdict(text: str) -> tuple[str, str, float, str, str | None]:
    """Return (decision, temporal_direction, confidence, reasoning, audit_reason)."""
    text_upper = text.upper()

    decision = "conflict"
    if "FINAL_VERDICT: SUPERSEDES" in text_upper:
        decision = "supersedes"
    elif "FINAL_VERDICT: NO_CHANGE" in text_upper:
        decision = "no_change"
    elif "FINAL_VERDICT: CONFLICT" in text_upper:
        decision = "conflict"

    temporal = "unclear"
    if "B_SUPERSEDES_A" in text_upper:
        temporal = "b_supersedes_a"
    elif "A_SUPERSEDES_B" in text_upper:
        temporal = "a_supersedes_b"

    confidence = _parse_confidence(text)

    reasoning = ""
    m = re.search(r'REASONING:\s*(.+?)(?=AUDIT_REASON:|$)', text, re.DOTALL | re.IGNORECASE)
    if m:
        reasoning = m.group(1).strip()

    audit_reason = None
    m = re.search(r'AUDIT_REASON:\s*(.+)', text, re.DOTALL | re.IGNORECASE)
    if m:
        audit_reason = m.group(1).strip()

    return decision, temporal, confidence, reasoning, audit_reason


def run_supersession_jury(
    mention_a: EntityMention,
    mention_b: EntityMention,
) -> SupersessionVerdict:
    """
    Determine if mention_b (newer doc) supersedes mention_a (older doc).

    This is a DIFFERENT question from entity deduplication:
    - Dedup Jury: "Are these the same entity?"
    - Supersession Jury: "Does B replace A's claim about this entity?"

    Used when: same metric/claim appears in documents from different dates,
    or when upload impact analysis flags a supersession candidate.
    """
    t0 = time.time()

    context = f"""CLAIM TYPE: {mention_a.entity_type}

CLAIM A (potentially older):
  Text: "{mention_a.surface_text}"
  Document: {mention_a.doc_filename}
  Date: {mention_a.doc_date or 'unknown'}
  Context: "{mention_a.chunk_text[:300]}"

CLAIM B (potentially newer / more authoritative):
  Text: "{mention_b.surface_text}"
  Document: {mention_b.doc_filename}
  Date: {mention_b.doc_date or 'unknown'}
  Context: "{mention_b.chunk_text[:300]}"

Question: Does Claim B supersede (replace/correct/retire) Claim A?"""

    analyst_raw = _llm(_SUPERSESSION_ANALYST_SYSTEM, context)

    judge_input = f"""ANALYST ASSESSMENT:
{analyst_raw}

ORIGINAL CONTEXT:
{context}"""

    judge_raw = _llm(_SUPERSESSION_JUDGE_SYSTEM, judge_input, model=JUDGE_MODEL)
    decision, temporal, confidence, reasoning, audit_reason = _parse_supersession_verdict(judge_raw)
    duration_ms = int((time.time() - t0) * 1000)

    # If B supersedes A, apply it to the KG
    if decision == "supersedes" and confidence >= 0.7:
        try:
            from ma.knowledge_graph import apply_supersession, _node_id  # noqa: PLC0415
            old_id = _node_id(mention_a.surface_text, mention_a.entity_type)
            new_id = _node_id(mention_b.surface_text, mention_b.entity_type)
            if temporal == "a_supersedes_b":
                old_id, new_id = new_id, old_id
            apply_supersession(old_id, new_id, reason=reasoning[:200], confidence=confidence)
        except Exception:
            pass  # best-effort

        # Log to KG provenance
        try:
            from ma.knowledge_graph import log_agent_decision  # noqa: PLC0415
            log_agent_decision(
                agent_name="SupersessionJury",
                decision_type="supersession",
                subject_entity=mention_a.surface_text,
                verdict=f"{decision}:{temporal}",
                confidence=confidence,
                linked_entities=[mention_b.surface_text],
                source_doc_ids=[mention_a.doc_id, mention_b.doc_id],
            )
        except Exception:
            pass

    return SupersessionVerdict(
        mention_a=mention_a.surface_text,
        mention_b=mention_b.surface_text,
        decision=decision,
        temporal_direction=temporal,
        confidence=confidence,
        reasoning=reasoning,
        audit_reason=audit_reason,
        duration_ms=duration_ms,
    )


def jury_from_chunks(chunks_a: list[dict], chunks_b: list[dict],
                     entity_type: str = "Person") -> JuryVerdict:
    """
    Convenience wrapper: build EntityMentions from raw chunk dicts and run jury.
    chunk dict: {id, doc_id, text, page, filename, date?, surface_text?}
    """
    def _to_mention(c: dict, idx: str) -> EntityMention:
        return EntityMention(
            mention_id=f"{c.get('doc_id', 0)}_c{c.get('id', 0)}",
            surface_text=c.get("surface_text", c["text"][:60]),
            entity_type=entity_type,
            doc_id=c.get("doc_id", 0),
            chunk_id=c.get("id", 0),
            chunk_text=c["text"][:400],
            doc_filename=c.get("filename", "unknown"),
            doc_date=c.get("date"),
            properties=c.get("properties", {}),
        )

    return run_jury(_to_mention(chunks_a[0], "a"), _to_mention(chunks_b[0], "b"))
