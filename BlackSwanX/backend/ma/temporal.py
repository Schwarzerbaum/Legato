"""
Temporal Adversarial Reconstruction — The Time Machine.

Agents:
  1. Document Period Classifier   — detects which year a document belongs to
  2. Forward Claim Extractor      — finds every promise / forecast / intention
  3. Liar's Drift Engine          — matches old promises against current reality
  4. Ghost Asset Scanner          — tracks asset mentions across time, flags disappearances
  5. Accuracy Timeline Builder    — per-year accuracy score (Value Bridge data)
"""
import re
from collections import defaultdict
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# 1. DOCUMENT PERIOD CLASSIFIER
# ─────────────────────────────────────────────────────────────

CURRENT_YEAR = datetime.now().year


def classify_document_period(filename: str, chunks: list[dict]) -> dict:
    """
    Detect which year/period a document belongs to.
    Returns {year, era, confidence, method}
    """
    full_text = " ".join(c.get("text", "") for c in chunks[:10])
    year_counts = defaultdict(int)

    # Year mentions in text
    for m in re.finditer(r'\b(20\d{2})\b', full_text):
        yr = int(m.group(1))
        if 2010 <= yr <= CURRENT_YEAR + 1:
            year_counts[yr] += 1

    # Year in filename
    fn_match = re.search(r'(20\d{2})', filename)
    if fn_match:
        yr = int(fn_match.group(1))
        year_counts[yr] += 5  # Weight filename heavily

    # Doc type hints
    doc_era_hints = {
        r'\bboard\s+minutes\b': "governance",
        r'\bannual\s+report\b': "financial",
        r'\bforecast\b|\bbudget\b|\bplan\b': "planning",
        r'\bconfidential\s+information\s+memorandum\b|\bCIM\b': "current",
        r'\bdue\s+diligence\b': "current",
        r'\bQ[1-4]\s+20\d{2}\b': "quarterly",
    }
    doc_type = "unknown"
    for pattern, dtype in doc_era_hints.items():
        if re.search(pattern, full_text, re.IGNORECASE):
            doc_type = dtype
            break

    if year_counts:
        detected_year = max(year_counts, key=year_counts.get)
        confidence = min(0.95, year_counts[detected_year] / max(sum(year_counts.values()), 1))
    else:
        detected_year = CURRENT_YEAR
        confidence = 0.2

    age = CURRENT_YEAR - detected_year
    era = "current" if age <= 1 else ("recent" if age <= 2 else ("historical" if age <= 4 else "archive"))

    return {
        "year": detected_year,
        "era": era,
        "age_years": age,
        "confidence": round(confidence, 2),
        "doc_type": doc_type,
        "year_distribution": dict(sorted(year_counts.items())),
    }


# ─────────────────────────────────────────────────────────────
# 2. FORWARD CLAIM EXTRACTOR
# ─────────────────────────────────────────────────────────────

FORWARD_PATTERNS = [
    # Hard commitments with target years
    (r'(by\s+(?:20\d{2}|end\s+of\s+\d{4})[^.]{0,100})', "commitment", 0.9),
    (r'((?:will|shall)\s+[a-z\s]{3,60}(?:by|in|before)\s+20\d{2}[^.]{0,80})', "commitment", 0.85),
    # Strategic pivots
    (r'((?:pivot|transition|migrate|move\s+away|phase\s+out)[^.]{0,120})', "strategic_pivot", 0.8),
    (r'((?:plan(?:ning)?\s+to|intend(?:ing)?\s+to|expect(?:ing)?\s+to)[^.]{0,120})', "intention", 0.75),
    # Growth targets
    (r'((?:target|goal|objective)\s+(?:of|is|:)[^.]{0,100})', "target", 0.8),
    (r'((?:grow|reach|achieve|hit)[^.]{0,40}(?:\$[\d,.]+[MBK]?|[\d,.]+\s*(?:million|billion))[^.]{0,60})', "growth_target", 0.85),
    (r'([\d,.]+%\s+(?:growth|increase|improvement)[^.]{0,60})', "growth_target", 0.75),
    # Hiring / headcount
    (r'((?:hire|expand\s+team|grow\s+(?:team|headcount)|add[^.]{0,20}(?:employee|engineer|staff))[^.]{0,100})', "hiring_plan", 0.7),
    # Product / tech promises
    (r'((?:launch|release|deploy|build|develop)[^.]{0,40}(?:product|feature|platform|system)[^.]{0,80})', "product_promise", 0.75),
    (r'((?:legacy|old|outdated)[^.]{0,40}(?:replace|retire|migrate|sunset|phase\s+out)[^.]{0,80})', "tech_debt_promise", 0.8),
    # Revenue / financial promises
    (r'((?:ARR|revenue|EBITDA|margin)[^.]{0,20}(?:will|shall|expect|target|forecast)[^.]{0,100})', "financial_forecast", 0.85),
    # Compliance / certification
    (r'((?:SOC\s*2|ISO\s*27001|GDPR|compliance)[^.]{0,40}(?:by|achieve|complete|certif)[^.]{0,80})', "compliance_promise", 0.8),
]

# Keywords that indicate current reality (not promises)
CURRENT_REALITY_INDICATORS = [
    r'\b(?:currently|as\s+of|today|now|at\s+present|this\s+year)\b',
    r'\b(?:achieved|completed|launched|deployed|delivered|migrated)\b',
    r'\b(?:Q[1-4]\s+20\d{2}\s+results)\b',
]


def _is_current_reality(sentence: str) -> bool:
    for p in CURRENT_REALITY_INDICATORS:
        if re.search(p, sentence, re.IGNORECASE):
            return True
    return False


def _extract_target_year(text: str, source_year: int) -> int | None:
    m = re.search(r'\b(20\d{2})\b', text)
    if m:
        yr = int(m.group(1))
        if yr > source_year:
            return yr
    return None


def extract_forward_claims(doc_id: int, chunks: list[dict], source_year: int) -> list[dict]:
    """Extract all forward-looking claims/promises from a document."""
    claims = []
    seen = set()

    for chunk in chunks:
        text = chunk.get("text", "")
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            if _is_current_reality(sentence):
                continue
            if len(sentence) < 20:
                continue

            for pattern, claim_type, confidence in FORWARD_PATTERNS:
                for m in re.finditer(pattern, sentence, re.IGNORECASE):
                    claim_text = m.group(1).strip()
                    if len(claim_text) < 15:
                        continue

                    # Dedup by first 60 chars
                    key = claim_text[:60].lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    target_year = _extract_target_year(claim_text, source_year)
                    claims.append({
                        "doc_id": doc_id,
                        "chunk_id": chunk.get("id"),
                        "page": chunk.get("page", 1),
                        "claim_text": claim_text[:200],
                        "claim_type": claim_type,
                        "source_year": source_year,
                        "target_year": target_year,
                        "confidence": confidence,
                        "verifiable": target_year is not None and target_year <= CURRENT_YEAR,
                    })

    return claims[:40]  # Cap per doc


# ─────────────────────────────────────────────────────────────
# 3. LIAR'S DRIFT ENGINE
# ─────────────────────────────────────────────────────────────

def _keyword_overlap(claim: str, reality_text: str) -> float:
    """Simple keyword overlap score between a claim and current reality text."""
    claim_words = set(re.findall(r'\b[a-z]{4,}\b', claim.lower()))
    reality_words = set(re.findall(r'\b[a-z]{4,}\b', reality_text.lower()))

    # Remove stop words
    stop = {'that', 'this', 'with', 'will', 'have', 'from', 'they', 'their',
            'been', 'were', 'also', 'more', 'than', 'into', 'over', 'some',
            'when', 'each', 'both', 'very', 'would', 'could', 'should'}
    claim_words -= stop
    reality_words -= stop

    if not claim_words:
        return 0.0
    overlap = len(claim_words & reality_words) / len(claim_words)
    return round(overlap, 3)


def _extract_numbers(text: str) -> list[float]:
    nums = []
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:M|B|K|%|million|billion)?', text, re.IGNORECASE):
        try:
            nums.append(float(m.group(1)))
        except Exception:
            pass
    return nums


def liars_drift_scan(
    historical_claims: list[dict],
    current_chunks: list[dict],
) -> dict:
    """
    Match each historical forward claim against current reality.
    Returns drift analysis with per-claim verdicts.
    """
    if not historical_claims:
        return {
            "verdict": "no_historical_data",
            "message": "No historical forward claims found — upload older documents.",
            "drift_score": 0,
            "claims_analyzed": 0,
            "verified": 0,
            "drifted": 0,
            "unverifiable": 0,
            "claim_verdicts": [],
        }

    current_text = " ".join(c.get("text", "") for c in current_chunks)
    verifiable = [c for c in historical_claims if c.get("verifiable")]

    claim_verdicts = []
    verified_count = 0
    drifted_count = 0
    unverifiable_count = 0

    for claim in historical_claims:
        claim_text = claim["claim_text"]
        overlap = _keyword_overlap(claim_text, current_text)

        # Number comparison for financial claims
        claim_nums = _extract_numbers(claim_text)
        current_nums = _extract_numbers(current_text[:2000])
        number_match = None
        if claim_nums and current_nums:
            closest = min(current_nums, key=lambda x: abs(x - claim_nums[0]))
            ratio = closest / claim_nums[0] if claim_nums[0] != 0 else 1
            number_match = 1.0 if 0.85 <= ratio <= 1.15 else (0.5 if 0.6 <= ratio <= 1.4 else 0.0)

        # Verdict logic
        if not claim.get("verifiable"):
            verdict = "unverifiable"
            drift_flag = False
            unverifiable_count += 1
        elif overlap >= 0.4 and (number_match is None or number_match >= 0.5):
            verdict = "verified"
            drift_flag = False
            verified_count += 1
        elif overlap >= 0.25:
            verdict = "partial"
            drift_flag = True
            drifted_count += 1
        else:
            verdict = "drifted"
            drift_flag = True
            drifted_count += 1

        # Strategic Integrity Gap — specific check for pivot/migration claims
        integrity_gap = None
        if claim["claim_type"] in ("strategic_pivot", "tech_debt_promise"):
            # Look for contradicting evidence
            tech_keywords = re.findall(r'\b(?:legacy|old|deprecated|technical\s+debt|monolith)\b',
                                        current_text, re.IGNORECASE)
            if tech_keywords and verdict != "verified":
                integrity_gap = f"Strategic pivot promised in {claim['source_year']} — {len(tech_keywords)} legacy references still found in current docs"

        claim_verdicts.append({
            "claim_text": claim_text,
            "claim_type": claim["claim_type"],
            "source_year": claim["source_year"],
            "target_year": claim.get("target_year"),
            "doc_id": claim["doc_id"],
            "chunk_id": claim.get("chunk_id"),
            "page": claim.get("page", 1),
            "verdict": verdict,
            "drift_flag": drift_flag,
            "overlap_score": overlap,
            "number_match": number_match,
            "integrity_gap": integrity_gap,
        })

    total_verifiable = len(verifiable)
    accuracy = round(verified_count / max(total_verifiable, 1) * 100, 1)
    drift_rate = round(drifted_count / max(total_verifiable, 1) * 100, 1)

    overall_verdict = "trustworthy" if accuracy >= 80 else ("drifting" if accuracy >= 50 else "liar")

    return {
        "verdict": overall_verdict,
        "accuracy_score": accuracy,
        "drift_rate": drift_rate,
        "claims_analyzed": len(historical_claims),
        "verifiable": total_verifiable,
        "verified": verified_count,
        "drifted": drifted_count,
        "unverifiable": unverifiable_count,
        "integrity_gaps": [v["integrity_gap"] for v in claim_verdicts if v.get("integrity_gap")],
        "claim_verdicts": sorted(claim_verdicts, key=lambda x: (x["drift_flag"], -x["overlap_score"]), reverse=True)[:25],
        "message": f"Analyzed {len(historical_claims)} historical claims. Accuracy: {accuracy}%. Drift rate: {drift_rate}%.",
    }


# ─────────────────────────────────────────────────────────────
# 4. GHOST ASSET SCANNER
# ─────────────────────────────────────────────────────────────

ASSET_CATEGORIES = {
    "real_estate": [r'\b(?:office|warehouse|facility|facilities|premises|lease|sq\s*ft|square\s+feet|headquarters)\b'],
    "equipment": [r'\b(?:server|hardware|equipment|machinery|fleet|vehicle|device)\b'],
    "ip_portfolio": [r'\b(?:patent|trademark|copyright|IP|intellectual\s+property|trade\s+secret)\b'],
    "people": [r'\b(?:employee|headcount|FTE|staff|engineer|team)\s+(?:of\s+)?(\d+)', r'\b(\d+)\s+(?:employee|FTE|staff|engineer)'],
    "customers": [r'\b(?:customer|client|account)\s+(?:base|count|of\s+)?(\d+[K]?)', r'\b(\d+[K]?)\s+(?:customer|client|account)'],
    "technology": [r'\b(?:platform|product|system|application|codebase|stack)\b'],
    "financial": [r'\b(?:cash|revenue|ARR|MRR|EBITDA)\s+(?:of\s+)?(?:\$[\d,.]+[MBK]?)'],
    "partnerships": [r'\b(?:partnership|integration|alliance|contract)\s+with\b'],
}


def ghost_asset_scan(docs_by_year: dict[int, list[dict]]) -> dict:
    """
    Track asset mentions across document years.
    Flag assets that appear in old docs but vanish from recent docs.
    """
    if len(docs_by_year) < 2:
        return {
            "verdict": "insufficient_timeline",
            "message": "Need documents from 2+ different years for ghost asset detection.",
            "ghost_assets": [],
            "asset_timeline": {},
        }

    years = sorted(docs_by_year.keys())
    asset_timeline = {}  # category → {year: count}

    for year, chunks in docs_by_year.items():
        combined = " ".join(c.get("text", "") for c in chunks)
        for category, patterns in ASSET_CATEGORIES.items():
            count = 0
            for pattern in patterns:
                count += len(re.findall(pattern, combined, re.IGNORECASE))
            if category not in asset_timeline:
                asset_timeline[category] = {}
            asset_timeline[category][year] = count

    ghost_assets = []
    latest_year = max(years)
    historical_years = [y for y in years if y < latest_year]

    for category, year_counts in asset_timeline.items():
        hist_avg = sum(year_counts.get(y, 0) for y in historical_years) / max(len(historical_years), 1)
        current_count = year_counts.get(latest_year, 0)

        if hist_avg > 3 and current_count < hist_avg * 0.3:
            decay_pct = round((1 - current_count / max(hist_avg, 1)) * 100, 1)
            ghost_assets.append({
                "category": category,
                "historical_avg_mentions": round(hist_avg, 1),
                "current_mentions": current_count,
                "decay_pct": decay_pct,
                "severity": "critical" if decay_pct > 80 else "high",
                "message": f"{category.replace('_',' ').title()} mentioned {hist_avg:.0f}x historically but only {current_count}x in current docs — {decay_pct:.0f}% drop",
                "year_counts": year_counts,
            })

    ghost_assets.sort(key=lambda x: x["decay_pct"], reverse=True)
    return {
        "verdict": "ghosts_detected" if ghost_assets else "assets_consistent",
        "ghost_count": len(ghost_assets),
        "ghost_assets": ghost_assets,
        "asset_timeline": asset_timeline,
        "years_analyzed": years,
        "message": f"Tracked {len(asset_timeline)} asset categories across {len(years)} document periods.",
    }


# ─────────────────────────────────────────────────────────────
# 5. ACCURACY TIMELINE BUILDER  (Value Bridge data)
# ─────────────────────────────────────────────────────────────

def build_accuracy_timeline(
    claims_by_year: dict[int, list[dict]],
    drift_results_by_year: dict[int, dict],
) -> list[dict]:
    """
    Build a per-year accuracy timeline for the Value Bridge D3 chart.
    Returns list of {year, accuracy_score, total_claims, verified, drifted, verdict}
    """
    all_years = sorted(set(list(claims_by_year.keys()) + list(drift_results_by_year.keys())))
    timeline = []

    for year in all_years:
        claims = claims_by_year.get(year, [])
        drift = drift_results_by_year.get(year, {})

        accuracy = drift.get("accuracy_score", None)
        if accuracy is None and claims:
            # No drift result yet — treat as unknown
            accuracy = None

        verified = drift.get("verified", 0)
        drifted = drift.get("drifted", 0)
        total = drift.get("verifiable", len(claims))

        if accuracy is not None:
            if accuracy >= 80:
                verdict = "trustworthy"
                color = "#10b981"
            elif accuracy >= 55:
                verdict = "drifting"
                color = "#f59e0b"
            else:
                verdict = "liar"
                color = "#ef4444"
        else:
            verdict = "unknown"
            color = "#6b7280"

        timeline.append({
            "year": year,
            "accuracy_score": accuracy,
            "total_claims": total,
            "verified": verified,
            "drifted": drifted,
            "verdict": verdict,
            "color": color,
        })

    return timeline


# ─────────────────────────────────────────────────────────────
# 6. MASTER TEMPORAL ANALYSIS RUNNER
# ─────────────────────────────────────────────────────────────

def run_temporal_analysis(all_docs: list[dict], all_chunks: list[dict]) -> dict:
    """
    Orchestrate all temporal agents across a set of documents.
    Returns full temporal forensic report.
    """
    if not all_docs:
        return {"error": "No documents found"}

    # Classify each doc into a year
    chunks_by_doc = defaultdict(list)
    for c in all_chunks:
        chunks_by_doc[c["doc_id"]].append(c)

    doc_periods = {}
    for doc in all_docs:
        doc_id = doc["id"]
        chunks = chunks_by_doc.get(doc_id, [])
        period = classify_document_period(doc.get("filename", ""), chunks)
        doc_periods[doc_id] = {**doc, **period}

    # Split into historical vs current
    current_year = CURRENT_YEAR
    historical_docs = {d: p for d, p in doc_periods.items() if p["age_years"] >= 2}
    current_docs = {d: p for d, p in doc_periods.items() if p["age_years"] < 2}

    # Group chunks by year
    docs_by_year = defaultdict(list)
    for doc_id, period in doc_periods.items():
        docs_by_year[period["year"]].extend(chunks_by_doc.get(doc_id, []))

    # Extract forward claims from historical docs
    all_historical_claims = []
    claims_by_year = defaultdict(list)
    for doc_id, period in historical_docs.items():
        claims = extract_forward_claims(doc_id, chunks_by_doc.get(doc_id, []), period["year"])
        all_historical_claims.extend(claims)
        claims_by_year[period["year"]].extend(claims)

    # Current reality chunks
    current_chunk_list = []
    for doc_id in current_docs:
        current_chunk_list.extend(chunks_by_doc.get(doc_id, []))
    # Fallback: use all chunks if no "current" docs
    if not current_chunk_list:
        current_chunk_list = all_chunks

    # Run Liar's Drift
    drift_result = liars_drift_scan(all_historical_claims, current_chunk_list)

    # Per-year drift for timeline
    drift_by_year = {}
    for year, year_claims in claims_by_year.items():
        if year_claims:
            drift_by_year[year] = liars_drift_scan(year_claims, current_chunk_list)

    # Ghost asset detection
    ghost_result = ghost_asset_scan(dict(docs_by_year))

    # Accuracy timeline
    timeline = build_accuracy_timeline(dict(claims_by_year), drift_by_year)

    # Overall temporal risk score
    temporal_risk = 0
    risk_flags = []

    drift_score_penalty = max(0, 100 - drift_result.get("accuracy_score", 100))
    temporal_risk += drift_score_penalty * 0.5

    if ghost_result.get("ghost_count", 0) > 0:
        temporal_risk += min(30, ghost_result["ghost_count"] * 8)
        risk_flags.append(f"{ghost_result['ghost_count']} Ghost Asset(s) detected")

    if drift_result.get("integrity_gaps"):
        temporal_risk += 20
        risk_flags.extend(drift_result["integrity_gaps"])

    temporal_risk = min(100, round(temporal_risk))

    return {
        "temporal_risk_score": temporal_risk,
        "traffic_light": "red" if temporal_risk >= 60 else ("amber" if temporal_risk >= 30 else "green"),
        "doc_periods": list(doc_periods.values()),
        "historical_docs": len(historical_docs),
        "current_docs": len(current_docs),
        "drift": drift_result,
        "ghost_assets": ghost_result,
        "accuracy_timeline": timeline,
        "total_claims_extracted": len(all_historical_claims),
        "risk_flags": risk_flags,
        "message": (
            f"Reconstructed {len(all_docs)} documents across "
            f"{len(set(p['year'] for p in doc_periods.values()))} time periods. "
            f"Temporal risk: {temporal_risk}/100."
        ),
    }
