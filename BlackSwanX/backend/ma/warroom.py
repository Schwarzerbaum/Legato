"""
M&A War Room — Adversarial Due Diligence Agents.

Agents:
  1. Benford's Law Auditor — detects fabricated financial figures
  2. Change-of-Control Scanner — finds Kill Switch clauses
  3. Truth Gap Detector — cross-doc contradiction finder
  4. Red Flag Aggregator — unified risk score
"""
import re
import math
import json
from collections import defaultdict


# ─────────────────────────────────────────────
# 1. BENFORD'S LAW AUDITOR
# ─────────────────────────────────────────────

BENFORD_EXPECTED = {
    1: 30.1, 2: 17.6, 3: 12.5, 4: 9.7,
    5: 7.9,  6: 6.7,  7: 5.8,  8: 5.1, 9: 4.6,
}


def extract_numbers_from_text(text: str) -> list[float]:
    """Pull all standalone numbers from text."""
    nums = []
    for m in re.finditer(r'\b(\d{2,}(?:\.\d+)?)\b', text):
        try:
            n = float(m.group())
            if n > 0:
                nums.append(n)
        except ValueError:
            pass
    return nums


def benford_audit(chunks: list[dict]) -> dict:
    """
    Run Benford's Law analysis on all numeric figures in chunks.
    Returns deviation score, first-digit distribution, verdict.
    """
    all_numbers = []
    for c in chunks:
        all_numbers.extend(extract_numbers_from_text(c.get("text", "")))

    if len(all_numbers) < 10:
        return {
            "verdict": "insufficient_data",
            "sample_size": len(all_numbers),
            "deviation_score": 0.0,
            "first_digit_dist": {},
            "expected_dist": BENFORD_EXPECTED,
            "red_flags": [],
            "message": f"Only {len(all_numbers)} numbers found — need 10+ for meaningful analysis.",
        }

    # Count first digits
    first_digit_counts = defaultdict(int)
    for n in all_numbers:
        first_digit = int(str(n).lstrip("0")[0])
        if 1 <= first_digit <= 9:
            first_digit_counts[first_digit] += 1

    total = sum(first_digit_counts.values())
    observed = {d: round(first_digit_counts[d] / total * 100, 1) for d in range(1, 10)}

    # Chi-square-like deviation
    deviation = 0.0
    for d in range(1, 10):
        exp = BENFORD_EXPECTED[d] / 100
        obs = observed.get(d, 0) / 100
        if exp > 0:
            deviation += ((obs - exp) ** 2) / exp
    deviation = round(deviation * 100, 2)  # scale to 0–100

    red_flags = []
    if deviation > 15:
        red_flags.append(f"High Benford deviation ({deviation:.1f}) — possible fabrication or rounding")
    if observed.get(5, 0) > 20:
        red_flags.append("Excess 5s detected — common in manually rounded figures")
    if observed.get(1, 0) < 15:
        red_flags.append("Insufficient leading 1s — data may be artificially compressed")

    verdict = "clean" if deviation < 10 else ("suspicious" if deviation < 20 else "high_risk")

    return {
        "verdict": verdict,
        "sample_size": len(all_numbers),
        "deviation_score": deviation,
        "first_digit_dist": observed,
        "expected_dist": BENFORD_EXPECTED,
        "red_flags": red_flags,
        "message": f"Analyzed {len(all_numbers)} figures. Deviation: {deviation:.1f}.",
    }


# ─────────────────────────────────────────────
# 2. CHANGE-OF-CONTROL (CoC) SCANNER
# ─────────────────────────────────────────────

COC_PATTERNS = [
    (r'\bchange\s+of\s+control\b', "Change of Control clause", "critical"),
    (r'\bchange-of-control\b', "Change of Control clause", "critical"),
    (r'\btermination\s+upon\s+(acquisition|merger|sale|change)\b', "Termination on acquisition", "critical"),
    (r'\bassignment\s+without\s+consent\b', "Assignment restriction", "high"),
    (r'\bprior\s+written\s+consent\b.*\bassign', "Consent-to-assign clause", "high"),
    (r'\bacceleration\b.*\bacquisition|acquisition\b.*\bacceleration\b', "Payment acceleration on acquisition", "high"),
    (r'\bkey\s+man\b|\bkey-man\b', "Key-man clause", "high"),
    (r'\bmost\s+favored\s+nation\b|\bMFN\b', "MFN clause — may require renegotiation", "medium"),
    (r'\bright\s+of\s+first\s+refusal\b|\bROFR\b', "Right of First Refusal", "medium"),
    (r'\bexclusive\b.{0,40}\bagreement\b', "Exclusivity provision", "medium"),
    (r'\bnon-compete\b|\bnon\s+compete\b', "Non-compete clause", "medium"),
    (r'\bautomatically\s+terminates?\b', "Auto-termination trigger", "critical"),
    (r'\bchurn.{0,20}at.{0,5}will\b|\bat.{0,5}will\b', "At-will termination — recurring revenue risk", "high"),
    (r'\b30.day\b.{0,40}\bterminat|termination.{0,40}\b30.day\b', "30-day termination window", "high"),
    (r'\bpersonal\s+service\s+agreement\b', "Personal service — non-transferable", "critical"),
]


def coc_scan(chunks: list[dict]) -> dict:
    """Scan all chunks for Change-of-Control / Kill Switch clauses."""
    findings = []
    seen_types = set()

    for chunk in chunks:
        text = chunk.get("text", "")
        for pattern, label, severity in COC_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                # Context window around match
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 120)
                context = text[start:end].strip()

                key = f"{label}:{chunk.get('id')}"
                if key not in seen_types:
                    seen_types.add(key)
                    findings.append({
                        "label": label,
                        "severity": severity,
                        "chunk_id": chunk.get("id"),
                        "page": chunk.get("page", 1),
                        "context": context,
                        "matched_text": m.group(),
                    })

    # Sort by severity
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda x: order.get(x["severity"], 9))

    critical_count = sum(1 for f in findings if f["severity"] == "critical")
    high_count = sum(1 for f in findings if f["severity"] == "high")

    verdict = "clean"
    if critical_count > 0:
        verdict = "kill_switch_detected"
    elif high_count > 2:
        verdict = "high_risk"
    elif findings:
        verdict = "review_required"

    return {
        "verdict": verdict,
        "total_clauses": len(findings),
        "critical": critical_count,
        "high": high_count,
        "medium": sum(1 for f in findings if f["severity"] == "medium"),
        "findings": findings[:30],
        "kill_switches": [f for f in findings if f["severity"] == "critical"],
    }


# ─────────────────────────────────────────────
# 3. TRUTH GAP DETECTOR
# ─────────────────────────────────────────────

def _extract_claims(text: str) -> list[tuple[str, float]]:
    """Extract percentage and figure claims from text."""
    claims = []
    # Percentages
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*%', text):
        claims.append(("pct", float(m.group(1))))
    # Dollar/Euro figures with M/B
    for m in re.finditer(r'[\$€]?\s*(\d+(?:\.\d+)?)\s*([MBK])\b', text, re.IGNORECASE):
        val = float(m.group(1))
        mult = {"M": 1_000_000, "B": 1_000_000_000, "K": 1_000}.get(m.group(2).upper(), 1)
        claims.append(("amount", val * mult))
    return claims


def truth_gap_scan(all_docs_chunks: list[dict]) -> dict:
    """
    Cross-document contradiction detection.
    Groups numeric claims by type across documents and flags spreads > 20%.
    """
    if len(all_docs_chunks) < 2:
        return {
            "verdict": "single_document",
            "gaps": [],
            "message": "Need 2+ documents to detect Truth Gaps.",
        }

    # Group by doc_id
    by_doc = defaultdict(list)
    for c in all_docs_chunks:
        by_doc[c.get("doc_id")].append(c)

    doc_ids = list(by_doc.keys())
    gaps = []

    # Compare percentage claims across docs
    doc_pcts = {}
    for doc_id, chunks in by_doc.items():
        pcts = []
        for c in chunks:
            for _, val in _extract_claims(c["text"]):
                pcts.append(val)
        if pcts:
            doc_pcts[doc_id] = sorted(pcts)

    # Look for docs where same claim range differs substantially
    if len(doc_pcts) >= 2:
        doc_list = list(doc_pcts.items())
        for i in range(len(doc_list)):
            for j in range(i + 1, len(doc_list)):
                doc_a_id, pcts_a = doc_list[i]
                doc_b_id, pcts_b = doc_list[j]
                # Find overlapping ranges with big differences
                for p_a in pcts_a:
                    for p_b in pcts_b:
                        if p_a == 0 or p_b == 0:
                            continue
                        diff = abs(p_a - p_b)
                        rel_diff = diff / max(p_a, p_b)
                        if 30 < p_a < 100 and 30 < p_b < 100 and rel_diff > 0.25:
                            # Find the actual chunks containing these values
                            chunk_a = next(
                                (c for c in by_doc[doc_a_id]
                                 if f"{p_a:.0f}%" in c["text"] or f"{p_a:.1f}%" in c["text"]),
                                by_doc[doc_a_id][0] if by_doc[doc_a_id] else {}
                            )
                            chunk_b = next(
                                (c for c in by_doc[doc_b_id]
                                 if f"{p_b:.0f}%" in c["text"] or f"{p_b:.1f}%" in c["text"]),
                                by_doc[doc_b_id][0] if by_doc[doc_b_id] else {}
                            )
                            gaps.append({
                                "type": "percentage_conflict",
                                "doc_a": doc_a_id,
                                "doc_b": doc_b_id,
                                "claim_a": f"{p_a:.1f}%",
                                "claim_b": f"{p_b:.1f}%",
                                "spread": f"{rel_diff*100:.0f}%",
                                "chunk_id_a": chunk_a.get("id"),
                                "chunk_id_b": chunk_b.get("id"),
                                "page_a": chunk_a.get("page", 1),
                                "page_b": chunk_b.get("page", 1),
                                "severity": "critical" if rel_diff > 0.5 else "high",
                                "label": f"Truth Gap: {p_a:.1f}% vs {p_b:.1f}% ({rel_diff*100:.0f}% spread)",
                            })

    # Deduplicate
    seen = set()
    deduped = []
    for g in gaps:
        k = f"{g['claim_a']}:{g['claim_b']}"
        if k not in seen:
            seen.add(k)
            deduped.append(g)

    deduped.sort(key=lambda x: float(x["spread"].rstrip("%")), reverse=True)
    deduped = deduped[:15]

    return {
        "verdict": "gaps_found" if deduped else "consistent",
        "total_gaps": len(deduped),
        "critical_gaps": sum(1 for g in deduped if g["severity"] == "critical"),
        "gaps": deduped,
        "docs_analyzed": len(doc_ids),
        "message": f"Analyzed {len(doc_ids)} documents. Found {len(deduped)} Truth Gaps.",
    }


# ─────────────────────────────────────────────
# 4. RED FLAG AGGREGATOR
# ─────────────────────────────────────────────

def red_flag_score(benford: dict, coc: dict, truth_gaps: dict, fact_count: int) -> dict:
    """Combine all agent outputs into a unified risk score (0–100) and traffic light."""
    score = 0
    flags = []

    # Benford contribution (max 35)
    dev = benford.get("deviation_score", 0)
    if dev > 20:
        score += 35
        flags.append({"source": "Benford Auditor", "severity": "critical",
                       "message": f"Financial figures show high fabrication risk (deviation {dev:.1f})"})
    elif dev > 10:
        score += 20
        flags.append({"source": "Benford Auditor", "severity": "high",
                       "message": f"Benford deviation {dev:.1f} — verify financial statements"})
    elif dev > 5:
        score += 8
    flags.extend([{"source": "Benford Auditor", "severity": "medium", "message": f} for f in benford.get("red_flags", [])])

    # CoC contribution (max 40)
    crit = coc.get("critical", 0)
    high = coc.get("high", 0)
    score += min(40, crit * 15 + high * 5)
    if crit > 0:
        flags.append({"source": "CoC Scanner", "severity": "critical",
                       "message": f"{crit} Kill Switch clause(s) detected — deal may collapse post-close"})
    if high > 0:
        flags.append({"source": "CoC Scanner", "severity": "high",
                       "message": f"{high} high-risk contract clause(s) require renegotiation"})

    # Truth Gap contribution (max 25)
    gaps = truth_gaps.get("total_gaps", 0)
    crit_gaps = truth_gaps.get("critical_gaps", 0)
    score += min(25, crit_gaps * 12 + (gaps - crit_gaps) * 4)
    if gaps > 0:
        flags.append({"source": "Truth Gap Detector", "severity": "critical" if crit_gaps else "high",
                       "message": f"{gaps} Truth Gap(s) found across documents — verify claims"})

    score = min(100, score)
    if score >= 70:
        traffic_light = "red"
        verdict = "HIGH RISK — Do not proceed without resolution"
    elif score >= 35:
        traffic_light = "amber"
        verdict = "REVIEW REQUIRED — Material issues need resolution"
    else:
        traffic_light = "green"
        verdict = "LOW RISK — Proceed with standard diligence"

    return {
        "score": score,
        "traffic_light": traffic_light,
        "verdict": verdict,
        "total_red_flags": len(flags),
        "flags": flags,
        "breakdown": {
            "benford_contribution": min(35, round(dev * 1.5)),
            "coc_contribution": min(40, crit * 15 + high * 5),
            "truth_gap_contribution": min(25, crit_gaps * 12 + (gaps - crit_gaps) * 4),
        },
    }
