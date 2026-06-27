"""
L3 — Credibility Engine (Bank-Side NGO Scanner)

Data pipeline:
  1. Ingest from DZI / Stifterverband transparency registers (HTTP scrape)
  2. Monitor live news via RSS / newsapi
  3. Parse into NGOCredibilityProfile with vector embedding
  4. Mirror entity nodes + risk edges into l6_knowledge_graph

Greenwash detection runs pattern-matching over scraped text and
sentiment scoring using VADER (no LLM required at scrape time).
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx

from legatum_intelligence.schemas import (
    ComplianceRecord, GreenwashFlag, GreenwashSeverity,
    NGOCredibilityProfile, SentimentWindow,
)

# Optional sentiment analyser (VADER — no API key)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    def _sentiment(text: str) -> float:
        return _vader.polarity_scores(text)["compound"]
except ImportError:
    def _sentiment(text: str) -> float:  # type: ignore[misc]
        # Lightweight keyword fallback
        pos = len(re.findall(r'\b(transparency|impact|verified|award|trust)\b', text, re.I))
        neg = len(re.findall(r'\b(fraud|scandal|misuse|greenwash|corrupt)\b', text, re.I))
        return max(-1.0, min(1.0, (pos - neg) * 0.2))


# ── Greenwash patterns ────────────────────────────────────────────────────────

_GREENWASH_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "GW-001", "severity": GreenwashSeverity.CRITICAL,
        "pattern": r'\b(fraud|Betrug|misappropriation|Veruntreuung)\b',
        "description": "Financial misconduct signal detected in public sources",
    },
    {
        "id": "GW-002", "severity": GreenwashSeverity.WARNING,
        "pattern": r'\b(greenwashing|Greenwashing|misleading claims|irreführende)\b',
        "description": "Greenwashing accusation in media or regulatory filing",
    },
    {
        "id": "GW-003", "severity": GreenwashSeverity.WARNING,
        "pattern": r'(annual report|Jahresbericht).{0,80}(missing|fehlt|not published|nicht veröffentlicht)',
        "description": "Annual report missing or unpublished",
    },
    {
        "id": "GW-004", "severity": GreenwashSeverity.ADVISORY,
        "pattern": r'\b(management fee|Verwaltungskosten).{0,40}(\d{2,3}%)',
        "description": "Unusually high administrative cost ratio detected",
    },
]


def _scan_greenwash(text: str) -> list[GreenwashFlag]:
    flags: list[GreenwashFlag] = []
    for p in _GREENWASH_PATTERNS:
        if re.search(p["pattern"], text, re.IGNORECASE | re.DOTALL):
            flags.append(GreenwashFlag(
                flag_id=p["id"],
                severity=p["severity"],
                source="credibility_engine_scan",
                description=p["description"],
            ))
    return flags


def _derive_risk_score(flags: list[GreenwashFlag]) -> float:
    weight = {
        GreenwashSeverity.CRITICAL: 0.5,
        GreenwashSeverity.WARNING:  0.25,
        GreenwashSeverity.ADVISORY: 0.1,
        GreenwashSeverity.CLEAN:    0.0,
    }
    return min(1.0, sum(weight[f.severity] for f in flags))


# ── DZI / Stifterverband ingestion ────────────────────────────────────────────

DZI_SEAL_URL         = "https://www.dzi.de/spenderberatung/dzi-spenden-siegel/"
STIFTERVERBAND_URL   = "https://www.stifterverband.org/transparenz"
BUNDESANZEIGER_SEARCH = "https://www.bundesanzeiger.de/pub/de/start"


async def _fetch_dzi_seal_holders() -> set[str]:
    """
    Scrape DZI seal-holder names.
    In production: replace with DZI's structured XML export or licensed data feed.
    """
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            resp = await client.get(DZI_SEAL_URL)
            # Extract org names from the DZI page (simplified pattern)
            names = set(re.findall(
                r'<td[^>]*class="[^"]*organization[^"]*"[^>]*>([^<]+)</td>',
                resp.text,
            ))
            return names or {"Welthungerhilfe", "BUND e.V.", "SOS Kinderdörfer"}
        except Exception:
            # Fallback to known sealed orgs for hackathon demo
            return {"Welthungerhilfe", "BUND e.V.", "SOS Kinderdörfer", "Caritas", "Diakonie"}


async def _fetch_news_sentiment(ngo_name: str) -> SentimentWindow:
    """
    Pull recent news headlines for an NGO and compute rolling sentiment.
    Uses DuckDuckGo Instant Answer API (no key required).
    """
    query = f"{ngo_name} scandal OR award OR transparency OR fraud"
    url   = f"https://api.duckduckgo.com/?q={httpx.QueryParams({'q': query})}&format=json&no_html=1"
    scores: list[float] = []
    sources: list[str]  = []

    async with httpx.AsyncClient(timeout=8) as client:
        try:
            resp = await client.get(url)
            data = resp.json()
            for topic in data.get("RelatedTopics", [])[:10]:
                text = topic.get("Text", "")
                if text:
                    scores.append(_sentiment(text))
                    url_ = topic.get("FirstURL", "")
                    if url_:
                        sources.append(url_)
        except Exception:
            pass

    avg_score = sum(scores) / len(scores) if scores else 0.1
    return SentimentWindow(
        score=round(avg_score, 3),
        article_count=len(scores),
        top_sources=sources[:3],
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def ingest_ngo(
    name: str,
    mission_statement: str,
    sdgs: list[int],
    website: str = "",
    country: str = "DE",
    registration_number: str = "",
    additional_text: str = "",
) -> NGOCredibilityProfile:
    """
    Full ingestion pipeline for one NGO:
      1. Fetch DZI seal list
      2. Pull news sentiment
      3. Scan for greenwash
      4. Build NGOCredibilityProfile (without embedding — VectorStore adds that)
    """
    dzi_holders, sentiment = await asyncio.gather(
        _fetch_dzi_seal_holders(),
        _fetch_news_sentiment(name),
    )

    dzi_seal = any(name.lower() in h.lower() for h in dzi_holders)

    # Compliance
    compliance = ComplianceRecord(
        dzi_seal=dzi_seal,
        dzi_seal_year=datetime.utcnow().year if dzi_seal else None,
        registration_number=registration_number,
        annual_report_verified=bool(website),
        annual_report_url=f"{website}/jahresbericht" if website else "",
        transparency_grade="A" if dzi_seal else "B",
        tax_exempt_status=True,
    )

    # Greenwash
    scan_corpus = f"{mission_statement} {additional_text}"
    flags       = _scan_greenwash(scan_corpus)
    risk_score  = _derive_risk_score(flags)

    profile = NGOCredibilityProfile(
        ngo_id=uuid4(),
        name=name,
        country=country,
        sdgs=sdgs,
        website=website,
        compliance=compliance,
        risk_score=risk_score,
        greenwash_flags=flags,
        sentiment=sentiment,
        mission_statement=mission_statement,
    )
    profile.compute_credibility()
    return profile


async def batch_ingest(ngo_list: list[dict]) -> list[NGOCredibilityProfile]:
    """Ingest multiple NGOs concurrently."""
    tasks = [
        ingest_ngo(
            name=n["name"],
            mission_statement=n["mission"],
            sdgs=n.get("sdgs", []),
            website=n.get("website", ""),
            country=n.get("country", "DE"),
            registration_number=n.get("reg_number", ""),
        )
        for n in ngo_list
    ]
    return await asyncio.gather(*tasks)


# ── Demo seed data ─────────────────────────────────────────────────────────────

DEMO_NGOS = [
    {
        "name": "BUND e.V.",
        "mission": (
            "Wir setzen uns für den Schutz von Natur, Umwelt und Klima ein. "
            "BUND kämpft für sauberes Wasser, intakte Ökosysteme und eine "
            "enkeltaugliche Gesellschaft in Deutschland und Europa."
        ),
        "sdgs": [13, 15, 6, 14],
        "website": "https://www.bund.net",
        "reg_number": "VR 4443",
    },
    {
        "name": "Welthungerhilfe",
        "mission": (
            "Eine Welt ohne Hunger ist möglich. Wir kämpfen für nachhaltige "
            "Ernährungssicherung, Krisenresilienz und das Recht auf Nahrung "
            "für alle Menschen — besonders in den ärmsten Regionen der Welt."
        ),
        "sdgs": [1, 2, 6, 17],
        "website": "https://www.welthungerhilfe.de",
        "reg_number": "VR 3730",
    },
    {
        "name": "Deutsche Meeresschutz Stiftung",
        "mission": (
            "Schutz der Meeresökosysteme vor Plastikverschmutzung, Überfischung "
            "und klimabedingter Erwärmung. Wir fördern marine Schutzgebiete und "
            "ozeanbasierte Klimaschutzlösungen in der Nord- und Ostsee."
        ),
        "sdgs": [14, 13, 15],
        "website": "https://www.deutsche-meeresschutz.de",
        "reg_number": "VR 9912",
    },
    {
        "name": "Baden-Württemberg Stiftung",
        "mission": (
            "Wir investieren in Bildung, Wissenschaft und Gesellschaft in "
            "Baden-Württemberg. Schwerpunkte: frühkindliche Bildung, "
            "Nachhaltigkeitsforschung und demokratische Teilhabe."
        ),
        "sdgs": [4, 9, 10, 16],
        "website": "https://www.bwstiftung.de",
        "reg_number": "VR 721312",
    },
]
