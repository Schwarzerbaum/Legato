"""
Reactive Knowledge Graph — Connected Papers + Graphiti architecture for M&A documents.

Architecture inspired by:
  connectedpapers.com  — document similarity network, sqrt-scaled node importance
  getzep/graphiti      — temporal edges (valid_at/invalid_at), 2-stage entity dedup,
                         label-propagation community detection, episode provenance
  Financial-KG repos   — ownership %, director relationships, announcement chains

Entity types:
  Company, Person, FinancialMetric, Risk, Contract, Finding, Claim, EvidenceGap

Graph layers:
  Layer 1 — Entity Graph:  entity nodes connected by typed edges + co-occurrence
  Layer 2 — Document Graph: document similarity network (Connected Papers view)
  Layer 3 — Community Graph: label-propagation clusters of related entities

Persistence:  SQLite tables ma_kg_nodes, ma_kg_edges, ma_kg_doc_similarity
Reactivity:   update_graph_for_doc(doc_id) on every upload — delta only
Temporal:     edges carry valid_from_year/valid_until_year parsed from context
Communities:  run_community_detection() labels every node with community_id
Dedup:        deduplicate_nodes() merges near-duplicate entities by name similarity
KGX export:   export_kgx() for interoperability with KG-Hub ecosystem
"""

import re
import json
import math
import random
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from ma.knowledge import get_db


# ─── Schema ─────────────────────────────────────────────────────────────────

def init_kg_tables():
    """Create knowledge-graph persistence tables (idempotent)."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ma_kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            canonical_name TEXT,
            mention_count INTEGER DEFAULT 0,
            doc_ids TEXT DEFAULT '[]',
            chunk_ids TEXT DEFAULT '[]',
            first_seen TEXT,
            last_seen TEXT,
            confidence REAL DEFAULT 0.8,
            pheromone_intensity REAL DEFAULT 0.0,
            community_id INTEGER DEFAULT -1,   -- graphiti-style label-propagation community
            merged_into TEXT DEFAULT NULL,     -- if deduped, points to surviving node id
            properties TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS ma_kg_edges (
            id TEXT PRIMARY KEY,
            src_node_id TEXT NOT NULL REFERENCES ma_kg_nodes(id),
            tgt_node_id TEXT NOT NULL REFERENCES ma_kg_nodes(id),
            edge_type TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            severity TEXT DEFAULT 'medium',
            doc_ids TEXT DEFAULT '[]',
            sentence_excerpt TEXT DEFAULT '',
            valid_from_year INTEGER DEFAULT NULL,   -- temporal: graphiti valid_at
            valid_until_year INTEGER DEFAULT NULL,  -- temporal: graphiti invalid_at
            ownership_pct REAL DEFAULT NULL,        -- financial-KG: ownership percentage
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ma_kg_doc_similarity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id_a INTEGER NOT NULL,
            doc_id_b INTEGER NOT NULL,
            shared_entities INTEGER DEFAULT 0,
            shared_facts INTEGER DEFAULT 0,
            semantic_overlap REAL DEFAULT 0.0,
            similarity_score REAL DEFAULT 0.0,
            computed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(doc_id_a, doc_id_b)
        );

        CREATE TABLE IF NOT EXISTS ma_kg_communities (
            id INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            summary TEXT DEFAULT '',
            node_count INTEGER DEFAULT 0,
            dominant_type TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Migrate existing tables: add new columns without breaking old data
    for col, defn in [
        ("community_id",       "INTEGER DEFAULT -1"),
        ("merged_into",        "TEXT DEFAULT NULL"),
        # Bi-temporal supersession columns (TGS-2026)
        ("superseded_by",      "TEXT DEFAULT NULL"),   # node_id of the superseding node
        ("superseded_at",      "TEXT DEFAULT NULL"),   # ISO timestamp of supersession
        ("supersession_reason","TEXT DEFAULT NULL"),   # why this was superseded
        ("doc_type",           "TEXT DEFAULT NULL"),   # SPA / CIM / etc. from source doc
        ("valid_from",         "TEXT DEFAULT NULL"),   # earliest date this claim was valid
        ("valid_to",           "TEXT DEFAULT NULL"),   # when it was retired
        # Liar's Drift versioning (Supermemory-style graph mutability)
        ("is_latest",          "INTEGER DEFAULT 1"),   # 1 = current truth; 0 = superseded
        ("drift_generation",   "INTEGER DEFAULT 0"),   # 0=original, 1=first revision, etc.
    ]:
        try:
            conn.execute(f"ALTER TABLE ma_kg_nodes ADD COLUMN {col} {defn}")
        except Exception:
            pass  # column already exists
    for col, defn in [
        ("valid_from_year",  "INTEGER DEFAULT NULL"),
        ("valid_until_year", "INTEGER DEFAULT NULL"),
        ("ownership_pct",    "REAL DEFAULT NULL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE ma_kg_edges ADD COLUMN {col} {defn}")
        except Exception:
            pass
    conn.commit()
    conn.close()


# ─── Entity type detection ───────────────────────────────────────────────────

# Ordered: more specific first.
# Each entry: (entity_type, patterns, use_ignorecase)
# Proper-noun types (Contract, Company, Person) use case-SENSITIVE matching so that
# lowercase contract boilerplate ("as of the date of this Agreement") is excluded.
_ENTITY_RULES: list[tuple[str, list[str], bool]] = [
    ("Contract", [
        # Mixed-case proper noun contracts (e.g. "Share Purchase Agreement")
        r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}\s+(?:Agreement|Contract|MSA|SLA|License|Licence|Lease|Facility|Deed|Indenture|Note|Bond|MOU|LOI|Plan|Arrangement|Amendment|Addendum|Schedule|Exhibit))\b',
        # ALL-CAPS contracts common in SEC filings (e.g. "MERGER AGREEMENT")
        r'\b([A-Z]{2,}(?:\s+[A-Z]{2,}){0,4}\s+(?:AGREEMENT|CONTRACT|PLAN|ARRANGEMENT|INDENTURE|DEED|LICENSE|FACILITY))\b',
        r'\b(Master\s+Service\s+Agreement(?:\s+(?:No\.|No|#)\s*[\w-]+)?)\b',
        r'\b((?:Agreement\s+and\s+Plan\s+of\s+Merger|Plan\s+of\s+Merger|Merger\s+Agreement))\b',
        r'\b(Share\s+Purchase\s+Agreement(?:\s+(?:No\.|No|#)\s*[\w-]+)?)\b',
        r'\b(Loan\s+(?:Agreement|Facility)(?:\s+(?:No\.|No|#)\s*[\w-]+)?)\b',
        r'\b((?:Non-?Disclosure|Confidentiality|Distribution|Supply|Services?|Employment|Severance|Voting|Support|Tender|Escrow|Transition)\s+Agreement)\b',
    ], False),   # case-SENSITIVE
    ("FinancialMetric", [
        # Standard metrics
        r'\b((?:total\s+|annual\s+|quarterly\s+)?(?:EBITDA|EBIT|ARR|MRR|CAGR)(?:\s+of\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
        r'\b(net\s+(?:income|loss|revenue|profit)\s*(?:of\s+[\$€£]?[\d,.]+[MBKmb]?|(?:was|is|were)\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
        r'\b(gross\s+(?:profit|margin|revenue)\s*(?:of\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
        r'\b([\$€£][\d,.]+\s*[MBKmb]?\s*(?:revenue|EBITDA|profit|loss|sales|ARR|MRR))\b',
        r'\b([\d,.]+\s*(?:million|billion)\s*(?:in\s+)?(?:revenue|EBITDA|profit|loss|sales|ARR))\b',
        r'\b(debt[\s-]to[\s-]equity\s*(?:ratio)?|leverage\s+ratio|current\s+ratio|quick\s+ratio|interest\s+coverage)\b',
        r'\b(working\s+capital\s*(?:of\s+[\$€£]?[\d,.]+[MBKmb]?)?|free\s+cash\s+flow\s*(?:of\s+[\$€£]?[\d,.]+[MBKmb]?)?|operating\s+(?:income|loss|margin))\b',
        # M&A deal-specific — per-share price, consideration, deal value
        r'\b([\$€£][\d,.]+\s*per\s+(?:share|unit|ADS))\b',
        r'\b([\$€£][\d,.]+\s*(?:billion|million|B|M)\s*(?:in\s+)?(?:consideration|transaction\s+value|deal\s+value|purchase\s+price|aggregate\s+consideration))\b',
        r'\b((?:aggregate|total|implied)\s+(?:consideration|transaction\s+value|deal\s+value|equity\s+value|enterprise\s+value)(?:\s+of\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
        r'\b((?:purchase|merger|closing)\s+(?:price|consideration)(?:\s+of\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
        r'\b((?:earn[\s-]out|earnout)(?:\s+(?:payment|consideration|target|amount))?(?:\s+of\s+[\$€£]?[\d,.]+[MBKmb]?)?)\b',
    ], True),
    ("Risk", [
        # Core M&A risks
        r'\b(regulatory\s+(?:risk|exposure|requirement|approval|clearance))\b',
        r'\b(litigation\s+(?:risk|exposure|pending))\b',
        r'\b((?:material\s+)?adverse\s+(?:effect|change|event|condition))\b',
        r'\b((?:environmental|tax|compliance|operational|reputational|antitrust|cybersecurity)\s+risk)\b',
        r'\b(change\s+of\s+control\s+(?:provision|clause|trigger|right))\b',
        r'\b(cross[\s-]default\s+(?:clause|provision))\b',
        r'\b(termination\s+(?:for\s+cause|right|clause|fee|payment))\b',
        r'\b(indemnification\s+(?:obligation|cap|basket|claim))\b',
        # M&A-specific deal risks
        r'\b(breach\s+of\s+(?:the\s+)?(?:representations?|warranties?|covenants?|obligations?))\b',
        r'\b(failure\s+to\s+(?:close|consummate|obtain|satisfy|complete)\s+(?:the\s+)?(?:merger|transaction|acquisition|closing))\b',
        r'\b((?:closing|condition\s+to\s+closing|condition\s+to\s+the\s+merger)\s+(?:not\s+satisfied|failed|waived))\b',
        r'\b((?:specific\s+performance|injunctive\s+relief)\s+(?:right|remedy|claim))\b',
        r'\b((?:antitrust|HSR|CFIUS|regulatory)\s+(?:approval|clearance|filing|review|risk))\b',
        r'\b((?:no[\s-]shop|non[\s-]solicit|exclusivity)\s+(?:provision|clause|obligation|period))\b',
        r'\b((?:fiduciary|board)\s+(?:out|exception|carve[\s-]out|withdrawal|determination))\b',
    ], True),
    ("Company", [
        # Mixed-case with legal suffix
        r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:Corp|Inc|LLC|Ltd|GmbH|AG|BV|SAS|NV|SE|PLC|LP|LLP|Co)\.?)\b',
        # ALL-CAPS legal entities common in SEC filings (e.g. SQUARESPACE, INC.)
        r'\b([A-Z]{3,}(?:\s+[A-Z]{2,}){0,3},?\s+(?:INC|LLC|CORP|LTD|LP|LLP|CO)\.?)\b',
        r'\b([A-Z][A-Za-z]+Co(?:rp)?\.)\b',
        # Defined deal-party terms (capitalised throughout the agreement)
        r'\b(the\s+(?:Company|Parent|Acquirer|Target|Seller|Buyer|Bidder|Purchaser|Holdco|Newco|Merger\s+Sub(?:sidiary)?|Surviving\s+(?:Company|Corporation)|Surviving\s+Entity))\b',
    ], False),   # case-sensitive
    ("Person", [
        # "First Last, Chief Executive Officer" or "First Last, CEO"
        r'\b([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?),?\s+(?:Chief\s+(?:Executive|Financial|Operating|Technology|Legal|Revenue)\s+Officer|CEO|CFO|CTO|COO|CLO|CRO|Chairman|Director|President|Executive\s+Vice\s+President|Senior\s+Vice\s+President|Vice\s+President|VP|Managing\s+Director|MD|General\s+Counsel|Founder|Partner|Trustee)\b',
        # "CEO/Title First Last"
        r'(?:CEO|CFO|CTO|COO|Chairman|Director|President|VP|MD|Founder|Counsel)\s+([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20})\b',
        # Signed by / executed by
        r'(?:signed?\s+by|executed\s+by|authorized\s+(?:representative|signatory|person)):?\s*([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20})\b',
        r'\b(Dr\.?\s+[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20})\b',
        r'\b(Mr\.?\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)\b',
        r'\b(Ms\.?\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)\b',
    ], False),   # case-sensitive
    ("EvidenceGap", [
        # Require explicit "not" — prevents "information provided" from matching
        r'\b((?:not\s+(?:provided|available|disclosed|included|produced))(?:\s+(?:in|by|to|for)\b)?)\b',
        # "information/data ... not available/provided" — "not" REQUIRED
        r'\b((?:information|data|document(?:ation)?|records?)\s+not\s+(?:available|provided|disclosed|produced|found))\b',
        # Redacted/withheld — anchor on the key word only, no trailing greedy capture
        r'\b((?:redacted|withheld)\s+(?:pursuant\s+to|per|from|due\s+to))\b',
        # Missing / absent — short capture, stop before preposition
        r'\b((?:missing|absent)\s+(?:from\s+)?(?:the\s+)?(?:[A-Z]\w+(?:\s+[A-Z]\w+){0,3}|(?:disclosure|schedule|exhibit|appendix|report|financials?|statements?)))\b',
        # Explicit evidence gap phrases
        r'\b(no\s+(?:evidence|record)\s+of\s+[A-Z]\w+(?:\s+[A-Z]\w+){0,3})\b',
        r'\b(not\s+disclosed)\b',
    ], True),
    ("Finding", [
        r'\b((?:we\s+(?:found|identified|noted|observed)|our\s+(?:analysis|review|investigation)\s+(?:found|revealed|identified))[^.!?]{0,80})\b',
        r'\b((?:key\s+finding|significant\s+(?:finding|observation|concern))[^.!?]{0,60})\b',
    ], True),
    ("Claim", [
        r'\b((?:management\s+(?:claims?|states?|asserts?|represents?)|the\s+(?:company|seller|target)\s+(?:claims?|states?|represents?))[^.!?]{0,80})\b',
        r'\b(as\s+(?:per|stated\s+in)\s+the\s+[A-Z][^.!?,]{0,40})\b',
    ], True),
]


_TRAILING_PREPS = frozenset({
    'to','of','the','a','an','in','at','by','for','from','with','on','as',
    'or','and','any','pursuant','per','its','this','that','these','those',
    'which','who','where','when','how','what','whether','if','but','not',
    'regarding','concerning','about','upon','between','among','under',
    'during','through','against','towards','toward','into','onto',
})


def _is_quality_name(name: str, etype: str) -> bool:
    """
    Filter out low-quality entity names:
    - Too short or too long
    - Contract/Company/Person must start with uppercase
    - Contract: reject if >40% stopwords (it's a phrase, not a name)
    - EvidenceGap/Risk: reject if last word is a preposition/determiner (incomplete capture)
    - All: reject names with more than 8 words (over-captured sentence fragments)
    """
    if len(name) < 4 or len(name) > 90:
        return False
    _STOPWORDS = {'the','a','an','in','of','at','by','for','from','to','with','on',
                  'as','is','are','was','were','be','been','has','have','had','do',
                  'does','did','not','this','that','these','those','any','all','or',
                  'and','but','its','it','per','prior','date','time','pursuant',
                  'without','written','notice'}
    words = name.lower().split()
    if not words:
        return False
    # Hard cap: >8 words is almost certainly a captured sentence fragment
    if len(words) > 8:
        return False
    # Proper-noun types: first word must be capitalized
    if etype in ('Contract', 'Company', 'Person'):
        if not name[0].isupper():
            return False
    # Contract: reject if more than 40% stopwords
    if etype == 'Contract':
        stop_ratio = sum(1 for w in words if w in _STOPWORDS) / len(words)
        if stop_ratio > 0.4:
            return False
        # Must have at least one "real" proper word
        if not any(w[0].isupper() for w in name.split() if len(w) > 2):
            return False
        # Reject names starting with legal boilerplate determiners
        # ("Each Contract", "Such Agreement", "Any License" — these are clause starters)
        _CLAUSE_STARTERS = frozenset({
            'each', 'such', 'any', 'all', 'no', 'other', 'certain', 'every',
            'existing', 'applicable', 'written', 'prior', 'additional',
            # Document structure words — these start sections, not contract names
            'preamble', 'schedule', 'exhibit', 'section', 'annex', 'appendix',
            'term', 'clause', 'article', 'recital',
        })
        if words[0] in _CLAUSE_STARTERS:
            return False
    # EvidenceGap + Risk: reject if ends with a preposition/determiner (incomplete phrase)
    if etype in ('EvidenceGap', 'Risk', 'Finding', 'Claim'):
        if words[-1] in _TRAILING_PREPS:
            return False
        # Reject if majority of words are stopwords (sentence fragment)
        stop_ratio = sum(1 for w in words if w in _STOPWORDS) / len(words)
        if stop_ratio > 0.5:
            return False

    # Person: filter out corporate role descriptions captured as names
    if etype == 'Person':
        # Reject if any token is an all-uppercase acronym > 3 chars (AWS, IBM, CTO...)
        orig_words = name.split()
        for w in orig_words:
            if w.upper() == w and len(w) >= 3 and w.isalpha():
                return False  # acronym-like token = corporate entity, not a person
        # Reject if first word is a corporate/role title
        _ROLE_PREFIXES = frozenset({
            'chief', 'vice', 'senior', 'deputy', 'general', 'executive', 'board',
            'head', 'managing', 'corporate', 'principal', 'associate', 'assistant',
        })
        if words[0] in _ROLE_PREFIXES:
            return False

    return True

_EDGE_RULES: list[tuple[str, str, str]] = [
    # (regex, edge_type, severity)
    # ── Critical triggers ──
    (r'cross[\s-]default',                           "cross_default",           "critical"),
    (r'change\s+of\s+control|change-of-control',     "change_of_control",       "critical"),
    (r'material\s+adverse\s+(?:effect|change|event)|MAE\b|MAC\b',
                                                      "mae_trigger",             "critical"),
    (r'accelerat(?:e|ion)\s+(?:of\s+)?(?:payment|repayment|maturity)',
                                                      "acceleration",            "critical"),
    (r'automatically\s+terminat|termination\s+(?:is\s+)?automatic',
                                                      "auto_termination",        "critical"),
    # ── High triggers ──
    (r'without\s+(?:prior\s+)?written\s+consent|assignment\s+without\s+consent',
                                                      "assignment_restriction",  "high"),
    (r'personal\s+service|key[\s-]man|key\s+person', "personal_service",        "high"),
    (r'sole\s+(?:source|supplier|vendor)|exclusive\s+(?:supplier|vendor)',
                                                      "sole_source",             "high"),
    (r'(?:IP\s+)?license\s+(?:shall\s+)?terminat',   "ip_termination",          "high"),
    (r'guarantees?\s+(?:the\s+)?(?:payment|obligation|debt)',
                                                      "guarantees",              "high"),
    # ── Medium triggers ──
    (r'personal\s+guarant(?:y|ee)',                   "personal_guaranty",       "medium"),
    (r'non[\s-]compet',                               "non_compete",             "medium"),
    (r'depends?\s+on|contingent\s+(?:on|upon)',       "depends_on",              "medium"),
    (r'subsidiary\s+of|wholly[\s-]owned\s+by',        "subsidiary_of",           "medium"),
    (r'acqui(?:res?|sition\s+of)',                    "acquires",                "medium"),
    # ── Financial-KG inspired: ownership & directorship ──
    (r'owns?\s+(?:approximately\s+)?[\d,.]+\s*(?:%|percent)|[\d,.]+\s*(?:%|percent)\s+(?:stake|interest|ownership)',
                                                      "owns_stake",              "high"),
    (r'(?:serves?|appointed|elected)\s+as\s+(?:Director|CEO|CFO|Chairman|President|Officer)',
                                                      "director_of",             "medium"),
    (r'(?:beneficial\s+)?owner\s+of\s+(?:record|shares?)',
                                                      "beneficial_owner",        "high"),
    (r'board\s+(?:of\s+directors?|seat|member)',      "board_membership",        "medium"),
    # ── Low triggers ──
    (r'notify|notification\s+required|written\s+notice\s+(?:of|to)',
                                                      "notification_required",   "low"),
    (r'pursuant\s+to|in\s+accordance\s+with',         "governed_by",             "low"),
]

# ── Temporal year extraction (graphiti-inspired valid_at/invalid_at) ──────────
_YEAR_RE = re.compile(r'\b(20[0-9]{2}|19[89][0-9])\b')
_EFFECTIVE_DATE_RE = re.compile(
    r'(?:effective|as\s+of|dated?|commenc(?:es?|ing)|from)\s+.*?(20[0-9]{2}|19[89][0-9])\b',
    re.IGNORECASE
)
_EXPIRY_DATE_RE = re.compile(
    r'(?:expir(?:es?|ing|ation)|terminat(?:es?|ing|ion)\s+on|until|through|no\s+later\s+than)\s+.*?(20[0-9]{2}|19[89][0-9])\b',
    re.IGNORECASE
)
_OWNERSHIP_PCT_RE = re.compile(r'([\d,.]+)\s*(?:%|percent)', re.IGNORECASE)


def _parse_temporal_and_ownership(sentence: str) -> dict:
    """
    Extract temporal validity and ownership % from a sentence.
    Returns dict with optional keys: valid_from_year, valid_until_year, ownership_pct.
    Inspired by graphiti's EntityEdge.valid_at / invalid_at fields.
    """
    result: dict = {}
    m = _EFFECTIVE_DATE_RE.search(sentence)
    if m:
        result['valid_from_year'] = int(m.group(1))
    m = _EXPIRY_DATE_RE.search(sentence)
    if m:
        result['valid_until_year'] = int(m.group(1))
    if 'valid_from_year' not in result:
        years = _YEAR_RE.findall(sentence)
        if years:
            result['valid_from_year'] = int(min(years))
    m = _OWNERSHIP_PCT_RE.search(sentence)
    if m:
        try:
            result['ownership_pct'] = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    return result


def _node_id(name: str, etype: str) -> str:
    """Stable hash ID for a node — deterministic so same entity always gets same ID."""
    key = f"{name.lower().strip()}::{etype}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _edge_id(src: str, tgt: str, etype: str) -> str:
    key = f"{src}::{tgt}::{etype}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


_CANONICALS: list[tuple[re.Pattern, str]] = [
    # Normalize MAE/MAC variants
    (re.compile(r'material\s+adverse\s+effect.*', re.I), 'Material Adverse Effect'),
    (re.compile(r'material\s+adverse\s+change.*', re.I), 'Material Adverse Change'),
    # Change of control variants
    (re.compile(r'change\s+of\s+control\s+provision.*', re.I), 'Change of Control Provision'),
    (re.compile(r'change\s+of\s+control\s+clause.*', re.I), 'Change of Control Clause'),
    # Cross-default variants
    (re.compile(r'cross[\s-]default\s+(?:clause|provision).*', re.I), 'Cross-Default Clause'),
    # EBITDA variants
    (re.compile(r'EBITDA.*', re.I), 'EBITDA'),
]


def _canonicalize(name: str) -> str:
    """Normalize common entity name variants to a canonical form."""
    for pattern, canonical in _CANONICALS:
        if pattern.match(name):
            return canonical
    return name


def _clean(name: str) -> str:
    raw = re.sub(r'\s+', ' ', name.strip().rstrip('.,;:'))
    return _canonicalize(raw)


# ─── Reactive update ─────────────────────────────────────────────────────────

def update_graph_for_doc(doc_id: int) -> dict:
    """
    Incrementally update the knowledge graph for one document.
    Called automatically after ingest. Returns delta stats.
    """
    init_kg_tables()
    conn = get_db()

    chunks = conn.execute(
        "SELECT c.id, c.text, c.page FROM ma_chunks c WHERE c.doc_id=? ORDER BY c.id",
        (doc_id,),
    ).fetchall()

    if not chunks:
        conn.close()
        return {"doc_id": doc_id, "nodes_added": 0, "edges_added": 0}

    nodes_added = 0
    edges_added = 0
    now = datetime.now(timezone.utc).isoformat()

    # Extract all entities and edges from this doc's chunks
    doc_nodes: dict[str, dict] = {}   # node_id → node data
    edge_candidates: list[dict] = []

    for chunk in chunks:
        text = chunk["text"]
        chunk_id = chunk["id"]
        page = chunk["page"]

        # Extract entities
        for etype, patterns, use_ignorecase in _ENTITY_RULES:
            flags = re.IGNORECASE if use_ignorecase else 0
            for pattern in patterns:
                for m in re.finditer(pattern, text, flags):
                    raw = m.group(1) if m.lastindex else m.group(0)
                    name = _clean(raw)
                    if not _is_quality_name(name, etype):
                        continue
                    nid = _node_id(name, etype)
                    if nid not in doc_nodes:
                        doc_nodes[nid] = {
                            "id": nid, "name": name, "entity_type": etype,
                            "mention_count": 0, "chunk_ids": [], "first_seen": now,
                        }
                    doc_nodes[nid]["mention_count"] += 1
                    if chunk_id not in doc_nodes[nid]["chunk_ids"]:
                        doc_nodes[nid]["chunk_ids"].append(chunk_id)

        # Extract edge-triggering sentences
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            for pattern, etype, severity in _EDGE_RULES:
                if re.search(pattern, sentence, re.IGNORECASE):
                    edge_candidates.append({
                        "sentence": sentence.strip()[:250],
                        "edge_type": etype,
                        "severity": severity,
                        "chunk_id": chunk_id,
                        "page": page,
                    })
                    break

    # Upsert nodes into DB
    all_node_ids_in_doc = list(doc_nodes.keys())
    for nid, nd in doc_nodes.items():
        existing = conn.execute("SELECT id, mention_count, doc_ids, chunk_ids FROM ma_kg_nodes WHERE id=?", (nid,)).fetchone()
        if existing:
            old_docs = json.loads(existing["doc_ids"] or "[]")
            old_chunks = json.loads(existing["chunk_ids"] or "[]")
            new_docs = sorted(set(old_docs + [doc_id]))
            new_chunks = sorted(set(old_chunks + nd["chunk_ids"]))
            conn.execute(
                "UPDATE ma_kg_nodes SET mention_count=mention_count+?, doc_ids=?, chunk_ids=?, last_seen=? WHERE id=?",
                (nd["mention_count"], json.dumps(new_docs), json.dumps(new_chunks), now, nid),
            )
        else:
            conn.execute(
                "INSERT INTO ma_kg_nodes (id, name, entity_type, mention_count, doc_ids, chunk_ids, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                (nid, nd["name"], nd["entity_type"], nd["mention_count"],
                 json.dumps([doc_id]), json.dumps(nd["chunk_ids"]), now, now),
            )
            nodes_added += 1

    # ── Pass 1: semantic edge detection from trigger sentences ──
    node_names_lower = {nd["name"].lower(): nid for nid, nd in doc_nodes.items()}

    def _upsert_edge(src_id, tgt_id, etype, severity, weight, excerpt, temporal=None):
        """Insert or update an edge, storing temporal/ownership metadata from context."""
        nonlocal edges_added
        if src_id == tgt_id:
            return
        t = temporal or {}
        eid = _edge_id(src_id, tgt_id, etype)
        existing_edge = conn.execute("SELECT id, weight, doc_ids FROM ma_kg_edges WHERE id=?", (eid,)).fetchone()
        if existing_edge:
            old_docs = json.loads(existing_edge["doc_ids"] or "[]")
            conn.execute(
                "UPDATE ma_kg_edges SET weight=weight+?, doc_ids=?, updated_at=? WHERE id=?",
                (weight, json.dumps(sorted(set(old_docs + [doc_id]))), now, eid),
            )
        else:
            conn.execute(
                """INSERT INTO ma_kg_edges
                   (id, src_node_id, tgt_node_id, edge_type, weight, severity,
                    doc_ids, sentence_excerpt, valid_from_year, valid_until_year, ownership_pct)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (eid, src_id, tgt_id, etype, weight, severity,
                 json.dumps([doc_id]), excerpt[:200],
                 t.get('valid_from_year'), t.get('valid_until_year'), t.get('ownership_pct')),
            )
            edges_added += 1

    for ctx in edge_candidates:
        sent_lower = ctx["sentence"].lower()
        found = [nid for name, nid in node_names_lower.items() if name in sent_lower and len(name) > 3]
        if len(found) >= 2:
            temporal = _parse_temporal_and_ownership(ctx["sentence"])
            _upsert_edge(found[0], found[1], ctx["edge_type"], ctx["severity"], 1.0,
                         ctx["sentence"], temporal=temporal)

    # ── Pass 2: chunk co-occurrence edges ─────────────────────────────────
    # Cross-type co-occurrence with TYPED edges where possible.
    # We use semantically meaningful edge types for known pairs
    # and only fall back to co_mentioned for truly unclassifiable pairs.
    # This replaces the generic co_mentioned dominance with typed edges.
    _COOCCUR_PAIRS = {
        ("Company",  "Risk"),         ("Company",  "Contract"),
        ("Company",  "Person"),       ("Company",  "FinancialMetric"),
        ("Person",   "Contract"),     ("Person",   "Risk"),
        ("Contract", "Risk"),         ("Contract", "FinancialMetric"),
        ("Risk",     "FinancialMetric"), ("Finding", "Risk"),
        ("Finding",  "Company"),      ("Claim",    "Risk"),
        ("Claim",    "Contract"),
    }

    # Build chunk → [(nid, etype)] map
    chunk_entities: dict[int, list[tuple[str, str]]] = {}
    for nid, nd in doc_nodes.items():
        etype = nd["entity_type"]
        for cid in nd["chunk_ids"]:
            chunk_entities.setdefault(cid, []).append((nid, etype))

    # Typed co-occurrence edge map: (etype_a, etype_b) → (edge_type, severity, weight)
    _TYPED_COOCCUR: dict[tuple[str, str], tuple[str, str, float]] = {
        ("Company",        "Risk"):           ("has_risk",         "high",   0.8),
        ("Company",        "Contract"):       ("party_to",         "medium", 0.75),
        ("Company",        "Person"):         ("employs",          "medium", 0.7),
        ("Company",        "FinancialMetric"):("has_revenue",       "medium", 0.75),
        ("Person",         "Contract"):       ("signatory_of",     "medium", 0.75),
        ("Person",         "Risk"):           ("exposed_to",       "high",   0.8),
        ("Contract",       "Risk"):           ("triggers_risk",    "high",   0.85),
        ("Contract",       "FinancialMetric"):("defines_value",    "medium", 0.7),
        ("Risk",           "FinancialMetric"):("quantifies_risk",  "high",   0.85),
        ("Finding",        "Risk"):           ("evidences_risk",   "high",   0.8),
        ("Finding",        "Company"):        ("concerns",         "medium", 0.7),
        ("Claim",          "Risk"):           ("raises_risk",      "high",   0.8),
        ("Claim",          "Contract"):       ("pertains_to",      "medium", 0.7),
        ("EvidenceGap",    "Risk"):           ("gap_in_risk",      "high",   0.85),
        ("EvidenceGap",    "Company"):        ("gap_about",        "medium", 0.7),
    }

    # For each chunk, emit TYPED co-occurrence edges
    for cid, ents in chunk_entities.items():
        if len(ents) < 2:
            continue
        chunk_row = conn.execute("SELECT text FROM ma_chunks WHERE id=?", (cid,)).fetchone()
        excerpt = chunk_row["text"][:150] if chunk_row else ""
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                nid_a, etype_a = ents[i]
                nid_b, etype_b = ents[j]
                # Try typed pair first, then reverse
                typed = _TYPED_COOCCUR.get((etype_a, etype_b)) or _TYPED_COOCCUR.get((etype_b, etype_a))
                if typed:
                    etype, sev, wt = typed
                    _upsert_edge(nid_a, nid_b, etype, sev, wt, excerpt)
                else:
                    # Fallback co_mentioned with low weight — keeps graph connected
                    _upsert_edge(nid_a, nid_b, "co_mentioned", "low", 0.2, excerpt)

    # ── Pass 3: Orphan rescue ─────────────────────────────────────────────
    # Any node extracted from this document that still has no edge gets a
    # "co_mentioned" edge to the highest-mention-count node in its same document.
    # This guarantees every entity is reachable in the graph, enabling PPR.
    if len(all_node_ids_in_doc) >= 2:
        # Find which nodes from this doc have at least one edge
        connected_ids: set[str] = set()
        for nid in all_node_ids_in_doc:
            row = conn.execute(
                "SELECT 1 FROM ma_kg_edges WHERE src_node_id=? OR tgt_node_id=? LIMIT 1",
                (nid, nid),
            ).fetchone()
            if row:
                connected_ids.add(nid)

        orphan_ids = [nid for nid in all_node_ids_in_doc if nid not in connected_ids]
        if orphan_ids:
            # Anchor selection: prefer Company → Risk → Contract → anything else.
            # Using the highest-mention node regardless of type creates a "hub" star
            # where a single Contract (e.g. Confidentiality Agreement) becomes the
            # anchor for every orphan, dominating the graph with co_mentioned edges.
            def _pick_anchor(candidate_set: set[str]) -> str | None:
                if not candidate_set:
                    return None
                clist = list(candidate_set)
                placeholders = ",".join("?" * len(clist))
                for preferred_type in ("Company", "Risk", "FinancialMetric", "Person"):
                    row = conn.execute(
                        f"SELECT id FROM ma_kg_nodes "
                        f"WHERE id IN ({placeholders}) AND entity_type=? "
                        f"ORDER BY mention_count DESC LIMIT 1",
                        clist + [preferred_type],
                    ).fetchone()
                    if row:
                        return row["id"]
                # Fallback: any type, highest mention — but skip Contract-only anchors
                # if there are other types available
                row = conn.execute(
                    f"SELECT id FROM ma_kg_nodes WHERE id IN ({placeholders}) "
                    f"AND entity_type != 'Contract' ORDER BY mention_count DESC LIMIT 1",
                    clist,
                ).fetchone()
                if row:
                    return row["id"]
                row = conn.execute(
                    f"SELECT id FROM ma_kg_nodes WHERE id IN ({placeholders}) "
                    f"ORDER BY mention_count DESC LIMIT 1",
                    clist,
                ).fetchone()
                return row["id"] if row else None

            if connected_ids:
                anchor_id = _pick_anchor(connected_ids)
            else:
                candidates_set = set(all_node_ids_in_doc) - {orphan_ids[0]}
                anchor_id = _pick_anchor(candidates_set)

            if anchor_id:
                for oid in orphan_ids:
                    if oid == anchor_id:
                        continue
                    # Get a short excerpt from the orphan's first chunk
                    orphan_chunk_ids = doc_nodes[oid]["chunk_ids"]
                    excerpt = ""
                    if orphan_chunk_ids:
                        cr = conn.execute("SELECT text FROM ma_chunks WHERE id=?", (orphan_chunk_ids[0],)).fetchone()
                        excerpt = (cr["text"][:120] if cr else "")
                    _upsert_edge(oid, anchor_id, "co_mentioned", "low", 0.3, excerpt)

    conn.commit()

    # Recompute document similarity for this doc vs all others
    _recompute_doc_similarity(conn, doc_id, all_node_ids_in_doc)

    conn.commit()
    conn.close()

    return {
        "doc_id": doc_id,
        "nodes_extracted": len(doc_nodes),
        "nodes_added": nodes_added,
        "nodes_updated": len(doc_nodes) - nodes_added,
        "edges_added": edges_added,
    }


def weave_spider_web() -> dict:
    """
    Three-pass spider-web densifier — turns a hub-and-spoke graph into a mesh.

    Pass 1 — Shared-chunk strands: any two nodes that appear together in 2+
             chunks get a direct edge weighted by Jaccard chunk overlap.
    Pass 2 — Cross-document bridges: nodes that appear in multiple docs act as
             bridges; connect them to highly-connected nodes of the other doc.
    Pass 3 — Second-degree shortcuts: if A–B and A–C exist, add B–C with
             decayed weight (0.4 × min(wAB, wAC)) — fills triangle gaps.
    """
    init_kg_tables()
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    edges_added = 0

    def _web_edge(src, tgt, etype, sev, wt, excerpt=""):
        nonlocal edges_added
        if src == tgt:
            return
        eid = _edge_id(src, tgt, etype)
        existing = conn.execute("SELECT id, weight FROM ma_kg_edges WHERE id=?", (eid,)).fetchone()
        if existing:
            conn.execute("UPDATE ma_kg_edges SET weight=MAX(weight,?) WHERE id=?", (wt, eid))
        else:
            conn.execute(
                """INSERT INTO ma_kg_edges
                   (id, src_node_id, tgt_node_id, edge_type, weight, severity, doc_ids, sentence_excerpt)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (eid, src, tgt, etype, wt, sev, "[]", excerpt[:150]),
            )
            edges_added += 1

    # ── Pass 1: shared-chunk strands ─────────────────────────────────────────
    nodes = conn.execute(
        "SELECT id, entity_type, chunk_ids FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchall()
    node_chunks: dict[str, set[int]] = {}
    for n in nodes:
        cids = json.loads(n["chunk_ids"] or "[]")
        node_chunks[n["id"]] = set(cids)

    node_list = [(n["id"], n["entity_type"]) for n in nodes]
    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            nid_a, etype_a = node_list[i]
            nid_b, etype_b = node_list[j]
            shared = node_chunks[nid_a] & node_chunks[nid_b]
            if len(shared) < 2:
                continue
            union = node_chunks[nid_a] | node_chunks[nid_b]
            jaccard = len(shared) / len(union) if union else 0
            if jaccard < 0.05:
                continue
            wt = round(0.3 + jaccard * 0.5, 3)
            _web_edge(nid_a, nid_b, "co_mentioned", "low", wt,
                      f"Shared in {len(shared)} chunks (Jaccard={jaccard:.2f})")

    # ── Pass 2: cross-document bridges ───────────────────────────────────────
    multi_doc_nodes = conn.execute(
        """SELECT id, entity_type, doc_ids FROM ma_kg_nodes
           WHERE merged_into IS NULL AND json_array_length(doc_ids) >= 2"""
    ).fetchall()
    for bridge in multi_doc_nodes:
        doc_ids_list = json.loads(bridge["doc_ids"] or "[]")
        bridge_id = bridge["id"]
        for other_doc in doc_ids_list:
            # Find top-3 highest-mention nodes from each other doc (excluding bridge itself)
            companions = conn.execute(
                """SELECT id FROM ma_kg_nodes
                   WHERE merged_into IS NULL AND id != ?
                   AND doc_ids LIKE ? ORDER BY mention_count DESC LIMIT 3""",
                (bridge_id, f"%{other_doc}%"),
            ).fetchall()
            for comp in companions:
                _web_edge(bridge_id, comp["id"], "co_mentioned", "low", 0.35,
                          f"Cross-document bridge via doc {other_doc}")

    # ── Pass 3: second-degree triangle shortcuts ──────────────────────────────
    # For each node A, find all its neighbours B, C and add B–C if not present
    # Cap at degree-10 nodes to avoid O(n³) blowup on hubs
    hub_threshold = 10
    all_nodes_ids = [n["id"] for n in nodes]
    for nid_a in all_nodes_ids:
        neighbours = conn.execute(
            """SELECT CASE WHEN src_node_id=? THEN tgt_node_id ELSE src_node_id END as nb,
                      weight FROM ma_kg_edges
               WHERE (src_node_id=? OR tgt_node_id=?) LIMIT ?""",
            (nid_a, nid_a, nid_a, hub_threshold),
        ).fetchall()
        if len(neighbours) < 2:
            continue
        nb_list = [(r["nb"], float(r["weight"] or 0.3)) for r in neighbours]
        for i in range(len(nb_list)):
            for j in range(i + 1, len(nb_list)):
                nb_b, wb = nb_list[i]
                nb_c, wc = nb_list[j]
                bridge_wt = round(0.4 * min(wb, wc), 3)
                if bridge_wt >= 0.1:
                    _web_edge(nb_b, nb_c, "co_mentioned", "low", bridge_wt,
                              f"Second-degree via {nid_a[:8]}")

    conn.commit()
    conn.close()

    # Recompute degree distribution for reporting
    conn2 = get_db()
    total_edges = conn2.execute("SELECT COUNT(*) FROM ma_kg_edges").fetchone()[0]
    leaf_nodes = conn2.execute(
        """SELECT COUNT(*) FROM ma_kg_nodes n WHERE merged_into IS NULL
           AND (SELECT COUNT(*) FROM ma_kg_edges e
                WHERE e.src_node_id=n.id OR e.tgt_node_id=n.id) = 1"""
    ).fetchone()[0]
    total_nodes = conn2.execute(
        "SELECT COUNT(*) FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchone()[0]
    conn2.close()

    return {
        "edges_added": edges_added,
        "total_edges": total_edges,
        "total_nodes": total_nodes,
        "leaf_nodes_remaining": leaf_nodes,
        "avg_degree": round(2 * total_edges / total_nodes, 1) if total_nodes else 0,
    }


def _recompute_doc_similarity(conn, new_doc_id: int, new_node_ids: list[str]):
    """Update doc-similarity rows for new_doc_id vs every other document."""
    # Get all other doc_ids
    other_docs = conn.execute(
        "SELECT DISTINCT d.id FROM ma_documents d WHERE d.id != ?", (new_doc_id,)
    ).fetchall()

    new_node_set = set(new_node_ids)

    for row in other_docs:
        other_id = row["id"]
        # Get nodes for other doc
        other_nodes_raw = conn.execute(
            "SELECT id, doc_ids FROM ma_kg_nodes WHERE doc_ids LIKE ?",
            (f"%{other_id}%",),
        ).fetchall()
        other_node_set = set(
            r["id"] for r in other_nodes_raw
            if other_id in json.loads(r["doc_ids"] or "[]")
        )

        shared = len(new_node_set & other_node_set)
        union = len(new_node_set | other_node_set)
        jaccard = shared / union if union else 0.0

        # Shared facts
        shared_facts = conn.execute(
            "SELECT COUNT(*) as cnt FROM ma_facts WHERE doc_id IN (?,?)",
            (new_doc_id, other_id),
        ).fetchone()["cnt"]

        score = round(jaccard * 0.7 + min(shared / max(len(new_node_set), 1), 1.0) * 0.3, 4)

        a, b = min(new_doc_id, other_id), max(new_doc_id, other_id)
        conn.execute(
            "INSERT OR REPLACE INTO ma_kg_doc_similarity (doc_id_a, doc_id_b, shared_entities, shared_facts, semantic_overlap, similarity_score) VALUES (?,?,?,?,?,?)",
            (a, b, shared, shared_facts, jaccard, score),
        )


# ─── Query API ───────────────────────────────────────────────────────────────

def get_entity_neighborhood(entity_name: str, depth: int = 2) -> dict:
    """
    Return a subgraph centered on an entity — all nodes within `depth` hops.
    Edge-case: entity not found → empty graph with message.
    """
    init_kg_tables()
    conn = get_db()

    # Find the node (case-insensitive partial match)
    row = conn.execute(
        "SELECT * FROM ma_kg_nodes WHERE LOWER(name) LIKE ? ORDER BY mention_count DESC LIMIT 1",
        (f"%{entity_name.lower()}%",),
    ).fetchone()

    if not row:
        conn.close()
        return {"found": False, "entity": entity_name, "nodes": [], "edges": []}

    root_id = row["id"]
    visited = {root_id}
    frontier = {root_id}
    all_nodes = {root_id: dict(row)}
    all_edges = []

    for _ in range(depth):
        if not frontier:
            break
        placeholders = ",".join("?" * len(frontier))
        edges = conn.execute(
            f"SELECT * FROM ma_kg_edges WHERE src_node_id IN ({placeholders}) OR tgt_node_id IN ({placeholders})",
            list(frontier) * 2,
        ).fetchall()

        next_frontier = set()
        for e in edges:
            all_edges.append(dict(e))
            for nid in (e["src_node_id"], e["tgt_node_id"]):
                if nid not in visited:
                    visited.add(nid)
                    next_frontier.add(nid)
                    node = conn.execute("SELECT * FROM ma_kg_nodes WHERE id=?", (nid,)).fetchone()
                    if node:
                        all_nodes[nid] = dict(node)
        frontier = next_frontier

    conn.close()

    return {
        "found": True,
        "root": dict(row),
        "nodes": list(all_nodes.values()),
        "edges": all_edges,
        "stats": {
            "node_count": len(all_nodes),
            "edge_count": len(all_edges),
            "depth_searched": depth,
        },
    }


def get_connected_papers_graph(min_similarity: float = 0.05) -> dict:
    """
    Connected Papers view — documents as nodes, similarity as edges.
    Nodes sized by page_count; edges thickness by shared_entities.
    Returns D3-compatible {nodes, links}.
    """
    init_kg_tables()
    conn = get_db()

    docs = conn.execute(
        "SELECT id, filename, page_count, chunk_count, upload_date FROM ma_documents ORDER BY id"
    ).fetchall()

    sim_rows = conn.execute(
        "SELECT * FROM ma_kg_doc_similarity WHERE similarity_score >= ?",
        (min_similarity,),
    ).fetchall()

    doc_entity_counts = {}
    for row in conn.execute(
        "SELECT doc_ids FROM ma_kg_nodes WHERE doc_ids != '[]'"
    ).fetchall():
        for did in json.loads(row["doc_ids"] or "[]"):
            doc_entity_counts[did] = doc_entity_counts.get(did, 0) + 1

    # Color by upload order (simulates "field" clustering)
    palette = ["#6366f1", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4"]

    d3_nodes = [
        {
            "id": f"doc_{d['id']}",
            "doc_id": d["id"],
            "label": d["filename"],
            "short_label": d["filename"][:20] + ("…" if len(d["filename"]) > 20 else ""),
            "page_count": d["page_count"] or 1,
            "chunk_count": d["chunk_count"] or 0,
            "entity_count": doc_entity_counts.get(d["id"], 0),
            "upload_date": d["upload_date"],
            "radius": max(12, min(40, 10 + (doc_entity_counts.get(d["id"], 0) * 0.8))),
            "color": palette[i % len(palette)],
        }
        for i, d in enumerate(docs)
    ]

    d3_links = [
        {
            "source": f"doc_{r['doc_id_a']}",
            "target": f"doc_{r['doc_id_b']}",
            "shared_entities": r["shared_entities"],
            "shared_facts": r["shared_facts"],
            "similarity": round(r["similarity_score"], 3),
            "width": max(1, min(8, r["shared_entities"] * 0.5)),
            "opacity": min(0.9, 0.2 + r["similarity_score"]),
        }
        for r in sim_rows
    ]

    conn.close()

    return {
        "nodes": d3_nodes,
        "links": d3_links,
        "stats": {
            "doc_count": len(d3_nodes),
            "similarity_links": len(d3_links),
            "connected_docs": len(set(
                [f"doc_{r['doc_id_a']}" for r in sim_rows] +
                [f"doc_{r['doc_id_b']}" for r in sim_rows]
            )),
        },
    }


def get_full_entity_graph(limit_nodes: int = 120) -> dict:
    """
    Full entity graph — top N entities by mention count + their edges.
    D3-compatible. Used for the main knowledge graph visualisation.
    """
    init_kg_tables()
    conn = get_db()

    nodes_raw = conn.execute(
        "SELECT * FROM ma_kg_nodes ORDER BY mention_count DESC LIMIT ?",
        (limit_nodes,),
    ).fetchall()

    if not nodes_raw:
        conn.close()
        return {"nodes": [], "links": [], "stats": {"node_count": 0, "edge_count": 0}}

    node_ids = {r["id"] for r in nodes_raw}
    placeholders = ",".join("?" * len(node_ids))

    edges_raw = conn.execute(
        f"SELECT * FROM ma_kg_edges WHERE src_node_id IN ({placeholders}) AND tgt_node_id IN ({placeholders})",
        list(node_ids) * 2,
    ).fetchall()

    conn.close()

    _TYPE_COLOR = {
        "Company":        "#3b82f6",
        "Person":         "#ec4899",
        "FinancialMetric":"#10b981",
        "Risk":           "#ef4444",
        "Contract":       "#6366f1",
        "Finding":        "#f59e0b",
        "Claim":          "#94a3b8",
        "EvidenceGap":    "#8b5cf6",
    }
    _SEV_COLOR = {"critical":"#ef4444","high":"#f59e0b","medium":"#eab308","low":"#94a3b8"}

    d3_nodes = []
    for r in nodes_raw:
        props = json.loads(r["properties"] or "{}") if r["properties"] else {}
        is_ghost = bool(props.get("is_ghost", False))
        d3_nodes.append({
            "id": r["id"],
            "name": r["name"],
            "canonical": r["canonical_name"] or r["name"],
            "type": r["entity_type"],
            "mentions": r["mention_count"],
            "docs": json.loads(r["doc_ids"] or "[]"),
            "color": "#6d28d9" if is_ghost else _TYPE_COLOR.get(r["entity_type"], "#9ca3af"),
            "radius": max(8, min(36, 6 + r["mention_count"] * 2.5)),
            "pheromone": round(r["pheromone_intensity"] or 0.0, 3),
            "community_id": r["community_id"] if r["community_id"] is not None else -1,
            "is_ghost": is_ghost,
        })

    d3_links = [
        {
            "id": e["id"],
            "source": e["src_node_id"],
            "target": e["tgt_node_id"],
            "type": e["edge_type"],
            "severity": e["severity"],
            "weight": round(e["weight"], 2),
            "color": _SEV_COLOR.get(e["severity"], "#94a3b8"),
            "width": max(1, min(5, e["weight"])),
            "docs": json.loads(e["doc_ids"] or "[]"),
            "excerpt": e["sentence_excerpt"],
            "valid_from_year": e["valid_from_year"],
            "valid_until_year": e["valid_until_year"],
            "ownership_pct": e["ownership_pct"],
        }
        for e in edges_raw
        if e["src_node_id"] != e["tgt_node_id"]
    ]

    return {
        "nodes": d3_nodes,
        "links": d3_links,
        "stats": {
            "node_count": len(d3_nodes),
            "edge_count": len(d3_links),
            "critical_edges": sum(1 for e in d3_links if e["severity"] == "critical"),
        },
    }


def get_entity_centrality(top_n: int = 20) -> list[dict]:
    """
    Degree centrality — which entities are most connected across the graph.
    Edge-case: empty graph returns [].
    """
    init_kg_tables()
    conn = get_db()

    edges = conn.execute("SELECT src_node_id, tgt_node_id FROM ma_kg_edges").fetchall()
    if not edges:
        conn.close()
        return []

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["src_node_id"]] += 1
        degree[e["tgt_node_id"]] += 1

    top_ids = sorted(degree, key=lambda k: -degree[k])[:top_n]
    placeholders = ",".join("?" * len(top_ids))
    nodes = conn.execute(
        f"SELECT id, name, entity_type, mention_count FROM ma_kg_nodes WHERE id IN ({placeholders})",
        top_ids,
    ).fetchall()
    conn.close()

    node_map = {r["id"]: dict(r) for r in nodes}
    return [
        {**node_map[nid], "degree": degree[nid]}
        for nid in top_ids
        if nid in node_map
    ]


def find_cross_doc_path(entity_a: str, entity_b: str) -> dict:
    """
    BFS shortest path between two entities in the knowledge graph.
    Edge-case: disconnected → returns path=[] with message.
    """
    init_kg_tables()
    conn = get_db()

    def _find_node(name: str):
        return conn.execute(
            "SELECT id, name FROM ma_kg_nodes WHERE LOWER(name) LIKE ? ORDER BY mention_count DESC LIMIT 1",
            (f"%{name.lower()}%",),
        ).fetchone()

    node_a = _find_node(entity_a)
    node_b = _find_node(entity_b)

    if not node_a or not node_b:
        conn.close()
        missing = []
        if not node_a: missing.append(entity_a)
        if not node_b: missing.append(entity_b)
        return {"found": False, "path": [], "message": f"Not in graph: {', '.join(missing)}"}

    if node_a["id"] == node_b["id"]:
        conn.close()
        return {"found": True, "path": [dict(node_a)], "message": "Same entity"}

    # BFS
    from collections import deque
    queue = deque([[node_a["id"]]])
    visited = {node_a["id"]}
    all_edges = conn.execute("SELECT src_node_id, tgt_node_id, edge_type FROM ma_kg_edges").fetchall()
    adj: dict[str, list[tuple]] = defaultdict(list)
    for e in all_edges:
        adj[e["src_node_id"]].append((e["tgt_node_id"], e["edge_type"]))
        adj[e["tgt_node_id"]].append((e["src_node_id"], e["edge_type"]))

    found_path = None
    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor, etype in adj.get(current, []):
            if neighbor == node_b["id"]:
                found_path = path + [neighbor]
                break
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
        if found_path:
            break

    if not found_path:
        conn.close()
        return {"found": False, "path": [], "message": f"No path connecting '{entity_a}' and '{entity_b}'"}

    # Resolve path node details
    placeholders = ",".join("?" * len(found_path))
    path_nodes = conn.execute(
        f"SELECT id, name, entity_type FROM ma_kg_nodes WHERE id IN ({placeholders})",
        found_path,
    ).fetchall()
    node_map = {r["id"]: dict(r) for r in path_nodes}
    conn.close()

    return {
        "found": True,
        "path": [node_map.get(nid, {"id": nid, "name": "?"}) for nid in found_path],
        "hops": len(found_path) - 1,
        "message": f"Path of {len(found_path)-1} hop(s) found",
    }


def get_kg_stats() -> dict:
    """Summary stats for the knowledge graph health dashboard."""
    init_kg_tables()
    conn = get_db()

    node_count = conn.execute("SELECT COUNT(*) FROM ma_kg_nodes WHERE merged_into IS NULL").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM ma_kg_edges").fetchone()[0]
    critical_edges = conn.execute("SELECT COUNT(*) FROM ma_kg_edges WHERE severity='critical'").fetchone()[0]
    doc_links = conn.execute("SELECT COUNT(*) FROM ma_kg_doc_similarity WHERE similarity_score > 0").fetchone()[0]
    communities = conn.execute("SELECT COUNT(DISTINCT community_id) FROM ma_kg_nodes WHERE community_id >= 0").fetchone()[0]
    temporal_edges = conn.execute("SELECT COUNT(*) FROM ma_kg_edges WHERE valid_from_year IS NOT NULL").fetchone()[0]

    type_dist = conn.execute(
        "SELECT entity_type, COUNT(*) as cnt FROM ma_kg_nodes WHERE merged_into IS NULL GROUP BY entity_type ORDER BY cnt DESC"
    ).fetchall()

    conn.close()
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "critical_edges": critical_edges,
        "document_similarity_links": doc_links,
        "communities": communities,
        "temporal_edges": temporal_edges,
        "entity_type_distribution": [dict(r) for r in type_dist],
    }


# ─── Community Detection — graphiti label propagation ────────────────────────

def run_community_detection() -> dict:
    """
    Label-propagation community detection (graphiti algorithm).
    Pure Python, no external deps.

    Each node starts in its own community (its ID as community label).
    Each iteration: every node adopts the plurality community of its neighbours.
    Repeat until convergence or 30 iterations.
    Community IDs are sequential integers 0..N-1.
    Returns summary dict.
    """
    init_kg_tables()
    conn = get_db()

    nodes = conn.execute("SELECT id FROM ma_kg_nodes WHERE merged_into IS NULL").fetchall()
    edges = conn.execute("SELECT src_node_id, tgt_node_id, weight FROM ma_kg_edges").fetchall()
    conn.close()

    if not nodes:
        return {"communities": 0, "nodes_updated": 0}

    # Build weighted adjacency list
    adj: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e in edges:
        adj[e["src_node_id"]][e["tgt_node_id"]] += float(e["weight"] or 1.0)
        adj[e["tgt_node_id"]][e["src_node_id"]] += float(e["weight"] or 1.0)

    # Initialise: each node is its own community
    community: dict[str, str] = {n["id"]: n["id"] for n in nodes}
    node_ids = [n["id"] for n in nodes]

    for _ in range(30):
        changed = False
        order = node_ids[:]
        random.shuffle(order)
        for nid in order:
            nbrs = adj.get(nid)
            if not nbrs:
                continue
            # Weighted vote for each community among neighbours
            vote: dict[str, float] = defaultdict(float)
            for nb, w in nbrs.items():
                vote[community.get(nb, nb)] += w
            best = max(vote, key=lambda k: (vote[k], k))
            if best != community[nid]:
                community[nid] = best
                changed = True
        if not changed:
            break

    # Map raw labels → sequential ints
    unique = sorted(set(community.values()))
    cmap = {c: i for i, c in enumerate(unique)}

    # Build community metadata
    type_by_node: dict[str, str] = {}
    conn2 = get_db()
    for n in conn2.execute("SELECT id, entity_type FROM ma_kg_nodes").fetchall():
        type_by_node[n["id"]] = n["entity_type"]

    # Compute dominant type per community
    comm_types: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for nid, craw in community.items():
        cid = cmap[craw]
        comm_types[cid][type_by_node.get(nid, "Unknown")] += 1

    # Persist community IDs to nodes
    for nid, craw in community.items():
        conn2.execute("UPDATE ma_kg_nodes SET community_id=? WHERE id=?", (cmap[craw], nid))

    # Rebuild community summary table
    conn2.execute("DELETE FROM ma_kg_communities")
    for cid, type_counts in comm_types.items():
        dominant = max(type_counts, key=lambda k: type_counts[k])
        node_count = sum(type_counts.values())
        label = f"Community {cid} — {dominant}"
        conn2.execute(
            "INSERT INTO ma_kg_communities (id, label, node_count, dominant_type) VALUES (?,?,?,?)",
            (cid, label, node_count, dominant),
        )

    conn2.commit()
    conn2.close()

    return {
        "communities": len(unique),
        "nodes_updated": len(community),
        "community_sizes": {cmap[c]: sum(1 for v in community.values() if v == c) for c in unique},
    }


# ─── Entity Deduplication — graphiti-inspired string similarity ───────────────

_SUFFIX_RE = re.compile(
    r'\b(?:Inc|Corp|LLC|Ltd|GmbH|AG|BV|NV|SE|PLC|Co|the|a|an)\b\.?', re.IGNORECASE
)


def _name_token_sim(a: str, b: str) -> float:
    """
    Token-overlap similarity for entity names.
    Strips legal suffixes before comparing so 'TechTarget Inc' ≈ 'TechTarget Corp'.

    Initial-expansion rule (Person dedup):
      "j.smith" == "john smith" when:
        – both have 2+ tokens after normalisation
        – last tokens match (same surname)
        – one first token is a single char that is a prefix of the other's first token
      Returns 0.92 (above any reasonable threshold).

    Abbreviated-suffix rule (Company dedup):
      "TechTarget" inside "TechTarget Inc" → same token set after suffix strip.
    """
    def _norm_tokens(s: str, min_len: int = 2) -> list[str]:
        """Lower, strip suffix words, return list of tokens ≥min_len chars."""
        cleaned = _SUFFIX_RE.sub('', s.lower())
        # Also strip punctuation around tokens (handles "j.smith" → ["j","smith"])
        cleaned = re.sub(r'[.\-_]', ' ', cleaned)
        return re.findall(rf'\w{{{min_len},}}', cleaned)

    # Use min_len=1 for initial-expansion check (preserves single-char initials)
    ta_raw = _norm_tokens(a, min_len=1)
    tb_raw = _norm_tokens(b, min_len=1)

    # ── Initial-expansion check (for Person names) ────────────────────────
    # "j.smith" ↔ "john smith": same last token + one first token is an initial of the other
    if len(ta_raw) >= 2 and len(tb_raw) >= 2:
        last_a = ta_raw[-1].rstrip('.')
        last_b = tb_raw[-1].rstrip('.')
        if last_a == last_b:                       # same surname
            first_a = ta_raw[0].rstrip('.')
            first_b = tb_raw[0].rstrip('.')
            is_initial_a = len(first_a) == 1
            is_initial_b = len(first_b) == 1
            if (is_initial_a and first_b.startswith(first_a)) or \
               (is_initial_b and first_a.startswith(first_b)):
                return 0.92   # Strong match — same person

    # Standard token-overlap for everything else (min_len=2 filters noise)
    ta = set(_norm_tokens(a, min_len=2))
    tb = set(_norm_tokens(b, min_len=2))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def deduplicate_nodes(sim_threshold: float = 0.75, dry_run: bool = False) -> dict:
    """
    Merge near-duplicate entity nodes using string similarity (graphiti stage-1 dedup).
    For each entity type group, pairs with name similarity >= sim_threshold are merged:
      - Lower mention-count node is redirected to higher-count node.
      - All edges pointing to/from the absorbed node are re-pointed to the survivor.
      - Absorbed node gets merged_into set (not deleted, for audit trail).

    dry_run=True returns what WOULD be merged without making changes.

    Graphiti uses cosine sim on name embeddings (threshold 0.6) + LLM escalation.
    We use token overlap (faster, no Ollama calls needed for small graphs).
    For larger graphs or higher accuracy, call /api/ma/kg/deduplicate?method=embedding.
    """
    init_kg_tables()
    conn = get_db()

    nodes = conn.execute(
        "SELECT id, name, entity_type, mention_count FROM ma_kg_nodes WHERE merged_into IS NULL ORDER BY mention_count DESC"
    ).fetchall()
    conn.close()

    # Group by entity type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for n in nodes:
        by_type[n["entity_type"]].append(dict(n))

    merge_plan: list[tuple[str, str, float]] = []  # (absorbed_id, survivor_id, sim)

    for etype, group in by_type.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                sim = _name_token_sim(a["name"], b["name"])
                if sim >= sim_threshold:
                    # Survivor = higher mention count (already sorted DESC)
                    merge_plan.append((b["id"], a["id"], round(sim, 3)))

    if dry_run:
        # Enrich with names for readable preview
        id_to_name = {n["id"]: n["name"] for n in nodes}
        return {
            "dry_run": True,
            "merges": [
                {"absorbed": ab, "absorbed_name": id_to_name.get(ab, ab),
                 "survivor": sv, "survivor_name": id_to_name.get(sv, sv), "sim": s}
                for ab, sv, s in merge_plan
            ],
            "count": len(merge_plan),
        }

    if not merge_plan:
        return {"merges_applied": 0, "message": "No duplicates found at threshold"}

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    merges_applied = 0
    for absorbed_id, survivor_id, sim in merge_plan:
        # Skip if already merged
        check = conn.execute("SELECT merged_into FROM ma_kg_nodes WHERE id=?", (absorbed_id,)).fetchone()
        if check and check["merged_into"]:
            continue
        # Re-point edges
        conn.execute("UPDATE ma_kg_edges SET src_node_id=? WHERE src_node_id=?", (survivor_id, absorbed_id))
        conn.execute("UPDATE ma_kg_edges SET tgt_node_id=? WHERE tgt_node_id=?", (survivor_id, absorbed_id))
        # Delete self-loops created by merge
        conn.execute("DELETE FROM ma_kg_edges WHERE src_node_id=tgt_node_id")
        # Mark absorbed as merged (graphiti audit trail)
        conn.execute(
            "UPDATE ma_kg_nodes SET merged_into=?, last_seen=? WHERE id=?",
            (survivor_id, now, absorbed_id)
        )
        # Add absorbed mentions to survivor
        absorbed_row = conn.execute("SELECT mention_count, doc_ids FROM ma_kg_nodes WHERE id=?", (absorbed_id,)).fetchone()
        if absorbed_row:
            surv_docs = json.loads(conn.execute("SELECT doc_ids FROM ma_kg_nodes WHERE id=?", (survivor_id,)).fetchone()["doc_ids"] or "[]")
            extra_docs = json.loads(absorbed_row["doc_ids"] or "[]")
            conn.execute(
                "UPDATE ma_kg_nodes SET mention_count=mention_count+?, doc_ids=? WHERE id=?",
                (absorbed_row["mention_count"], json.dumps(sorted(set(surv_docs + extra_docs))), survivor_id),
            )
        merges_applied += 1

    conn.commit()
    conn.close()
    return {"merges_applied": merges_applied, "threshold": sim_threshold}


# ─── KGX Export — KG-Hub interoperability ────────────────────────────────────

def export_kgx() -> dict:
    """
    Export the knowledge graph in KGX format (KG-Hub standard).
    Returns {nodes: [{id,name,category,...}], edges: [{subject,predicate,object,...}]}
    Compatible with kg-covid-19 / kg-microbe pipeline format.
    """
    init_kg_tables()
    conn = get_db()

    nodes_raw = conn.execute(
        "SELECT * FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchall()
    edges_raw = conn.execute(
        "SELECT * FROM ma_kg_edges WHERE src_node_id != tgt_node_id"
    ).fetchall()
    conn.close()

    # KGX biolink-style category mapping
    _BIOLINK = {
        "Company":        "biolink:Organization",
        "Person":         "biolink:Person",
        "FinancialMetric":"biolink:NamedThing",
        "Risk":           "biolink:NamedThing",
        "Contract":       "biolink:Agreement",
        "Finding":        "biolink:InformationContentEntity",
        "Claim":          "biolink:InformationContentEntity",
        "EvidenceGap":    "biolink:InformationContentEntity",
    }

    kgx_nodes = [
        {
            "id": f"blackswanx:{r['id']}",
            "name": r["name"],
            "category": _BIOLINK.get(r["entity_type"], "biolink:NamedThing"),
            "entity_type": r["entity_type"],
            "mention_count": r["mention_count"],
            "community_id": r["community_id"],
            "provided_by": "BlackSwanX M&A KG",
        }
        for r in nodes_raw
    ]

    kgx_edges = [
        {
            "subject": f"blackswanx:{e['src_node_id']}",
            "predicate": f"blackswanx:{e['edge_type']}",
            "object": f"blackswanx:{e['tgt_node_id']}",
            "weight": e["weight"],
            "severity": e["severity"],
            "valid_from_year": e["valid_from_year"],
            "valid_until_year": e["valid_until_year"],
            "ownership_pct": e["ownership_pct"],
            "provided_by": "BlackSwanX M&A KG",
        }
        for e in edges_raw
    ]

    return {"nodes": kgx_nodes, "edges": kgx_edges,
            "stats": {"node_count": len(kgx_nodes), "edge_count": len(kgx_edges)}}


# ─── Personalized PageRank — HippoRAG multi-hop retrieval ────────────────────

def personalized_pagerank(
    seed_entities: list[str],
    seed_weights: list[float] | None = None,
    damping: float = 0.5,          # HippoRAG default (vs standard 0.85)
    max_iter: int = 50,
    top_k: int = 15,
) -> dict:
    """
    HippoRAG-style Personalized PageRank over the entity knowledge graph.

    Instead of simple BFS path-finding, PPR propagates probability mass
    from seed entities through the graph. Entities multi-hop connected
    to the seeds rank higher — surfacing hidden relationships.

    Architecture:  seed → reset vector → power iteration → ranked entities
    HippoRAG ref:  graph_search_with_fact_entities → run_ppr → doc_scores

    Args:
        seed_entities: entity names (partial match OK — acts as query)
        seed_weights:  optional per-seed weights (default: uniform)
        damping:       teleportation probability (0.5 = balanced exploration)
        max_iter:      power iteration cap
        top_k:         return top-k nodes

    Returns dict with ranked_nodes, seed_hits, convergence info.
    """
    init_kg_tables()
    conn = get_db()
    nodes_raw = conn.execute(
        "SELECT id, name, entity_type, mention_count, community_id, pheromone_intensity "
        "FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchall()
    edges_raw = conn.execute(
        "SELECT src_node_id, tgt_node_id, weight FROM ma_kg_edges"
    ).fetchall()
    conn.close()

    if not nodes_raw:
        return {"ranked_nodes": [], "seed_hits": [], "converged": True, "iterations": 0}

    n = len(nodes_raw)
    nodes_list = [dict(r) for r in nodes_raw]
    node_idx   = {r["id"]: i for i, r in enumerate(nodes_list)}

    # ── Sparse adjacency (undirected, row-normalised) ──
    adj_sparse: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for e in edges_raw:
        i = node_idx.get(e["src_node_id"])
        j = node_idx.get(e["tgt_node_id"])
        if i is None or j is None or i == j:
            continue
        w = float(e["weight"] or 1.0)
        adj_sparse[i][j] += w
        adj_sparse[j][i] += w

    # Row-normalise
    for i in list(adj_sparse):
        total = sum(adj_sparse[i].values())
        if total > 0:
            adj_sparse[i] = {j: w / total for j, w in adj_sparse[i].items()}

    # ── Seed vector: find nodes matching each seed query ──
    seed_vec = [0.0] * n
    seed_hits: list[dict] = []
    for q_idx, query in enumerate(seed_entities):
        q_lower = query.lower()
        w = (seed_weights[q_idx] if seed_weights else 1.0)
        matched = False
        for ni, nd in enumerate(nodes_list):
            name_l = nd["name"].lower()
            if q_lower in name_l or name_l in q_lower:
                # Boost by mention count (like HippoRAG's phrase_weights averaging)
                boost = 1.0 + math.log1p(nd["mention_count"])
                seed_vec[ni] += w * boost
                if not matched:
                    seed_hits.append({"name": nd["name"], "type": nd["entity_type"],
                                      "query": query})
                    matched = True

    # Uniform seed if nothing matched
    s = sum(seed_vec)
    if s == 0:
        seed_vec = [1.0 / n] * n
    else:
        seed_vec = [v / s for v in seed_vec]

    # ── Power iteration: r = α·Aᵀ·r + (1−α)·seed ──
    r = seed_vec[:]
    iterations = 0
    for it in range(max_iter):
        iterations = it + 1
        r_new = [(1 - damping) * seed_vec[j] for j in range(n)]
        for i, nbrs in adj_sparse.items():
            ri = r[i]
            if ri == 0:
                continue
            for j, w in nbrs.items():
                r_new[j] += damping * w * ri
        diff = sum(abs(r_new[i] - r[i]) for i in range(n))
        r = r_new
        if diff < 1e-7:
            break

    # ── Rank and return ──
    ranked_idx = sorted(range(n), key=lambda i: -r[i])[:top_k]
    ranked_nodes = [
        {
            **nodes_list[i],
            "ppr_score": round(r[i], 7),
            "rank": rank + 1,
            "is_seed": seed_vec[i] > 0,
        }
        for rank, i in enumerate(ranked_idx)
        if r[i] > 1e-9
    ]

    return {
        "ranked_nodes": ranked_nodes,
        "seed_hits": seed_hits,
        "seeds_not_found": [q for q in seed_entities
                            if not any(h["query"] == q for h in seed_hits)],
        "converged": iterations < max_iter,
        "iterations": iterations,
        "graph_size": {"nodes": n, "edges": len(edges_raw)},
    }


# ─── Hybrid search — GitNexus BM25 + PPR fusion ──────────────────────────────

def hybrid_search(query: str, top_k: int = 15, bm25_weight: float = 0.4) -> dict:
    """
    Hybrid search combining BM25 keyword score + PPR graph score.
    Inspired by GitNexus reciprocal-rank fusion (BM25 + semantic + graph).

    BM25 provides recall for exact term matches.
    PPR provides precision for multi-hop connected entities.
    Final score = bm25_weight * bm25_score + (1 - bm25_weight) * ppr_score.

    Returns merged ranked list with source annotations.
    """
    init_kg_tables()
    conn = get_db()
    nodes_raw = conn.execute(
        "SELECT id, name, entity_type, mention_count, community_id "
        "FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchall()
    conn.close()

    if not nodes_raw:
        return {"results": [], "query": query}

    nodes_list = [dict(r) for r in nodes_raw]
    query_terms = set(re.findall(r'\w{3,}', query.lower()))

    # ── BM25 (simplified: TF × IDF approximation) ──
    # Corpus = name tokens + entity_type tokens (lowercased, split on camelCase)
    # e.g. "FinancialMetric" → ["financial", "metric"] so "metric" query hits it
    def _type_tokens(etype: str) -> list[str]:
        # Split CamelCase: FinancialMetric → ['financial', 'metric']
        parts = re.findall(r'[A-Z][a-z]+|[A-Z]+(?=[A-Z]|$)', etype)
        return [p.lower() for p in parts] if parts else [etype.lower()]

    def _node_tokens(nd: dict) -> list[str]:
        return re.findall(r'\w{3,}', nd["name"].lower()) + _type_tokens(nd["entity_type"])

    N = len(nodes_list)
    # DF for each term across corpus (name + type tokens)
    df: dict[str, int] = defaultdict(int)
    for nd in nodes_list:
        terms = set(_node_tokens(nd))
        for t in terms:
            df[t] += 1

    bm25_scores: list[float] = []
    for nd in nodes_list:
        all_terms = _node_tokens(nd)   # name tokens + type tokens
        if not all_terms:
            bm25_scores.append(0.0)
            continue
        score = 0.0
        tf_map: dict[str, float] = defaultdict(float)
        for t in all_terms:
            tf_map[t] += 1
        for t in query_terms:
            if t not in tf_map:
                continue
            tf = tf_map[t] / len(all_terms)
            idf = math.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1)
            # BM25 k1=1.5 b=0.75 avgdl≈5 (avg entity name length in tokens)
            k1, b, avgdl = 1.5, 0.75, 5.0
            dl = len(all_terms)
            bm25 = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
            score += bm25
        bm25_scores.append(score)

    # Normalise BM25 scores 0–1
    max_bm25 = max(bm25_scores) or 1.0
    bm25_norm = [s / max_bm25 for s in bm25_scores]

    # ── PPR scores from [query] as seed ──
    ppr_result = personalized_pagerank([query], damping=0.5, top_k=N)
    ppr_by_id = {r["id"]: r["ppr_score"] for r in ppr_result["ranked_nodes"]}
    max_ppr = max(ppr_by_id.values(), default=1.0) or 1.0
    ppr_norm_by_id = {k: v / max_ppr for k, v in ppr_by_id.items()}

    # ── Fuse ──
    fused: list[dict] = []
    for i, nd in enumerate(nodes_list):
        bm25_s = bm25_norm[i]
        ppr_s = ppr_norm_by_id.get(nd["id"], 0.0)
        combined = bm25_weight * bm25_s + (1 - bm25_weight) * ppr_s
        if combined > 0:
            fused.append({
                **nd,
                "score": round(combined, 5),
                "bm25_score": round(bm25_s, 4),
                "ppr_score":  round(ppr_s,  4),
                "match_type": "both" if bm25_s > 0 and ppr_s > 0
                              else ("bm25" if bm25_s > 0 else "graph"),
            })

    fused.sort(key=lambda x: -x["score"])
    return {
        "results": fused[:top_k],
        "query": query,
        "stats": {
            "bm25_hits":  sum(1 for x in fused if x["bm25_score"] > 0),
            "graph_hits": sum(1 for x in fused if x["ppr_score"] > 0),
            "both_hits":  sum(1 for x in fused if x["match_type"] == "both"),
        },
    }


# ─── Agent Decision Provenance — Semantica-inspired ──────────────────────────

def log_agent_decision(
    agent_name: str,
    decision_type: str,          # e.g. "jury_verdict", "drift_detected", "absence_found"
    subject_entity: str,         # entity this decision is about
    verdict: str,                # the decision text / result
    confidence: float = 0.0,
    linked_entities: list[str] | None = None,   # other entities involved
    source_doc_ids: list[int] | None = None,
) -> str:
    """
    Record an agent decision as a provenance node in the KG.
    Semantica-inspired: every agent verdict becomes a first-class graph object
    with causal links to the entities it reasoned about.

    Returns the new decision node ID.
    """
    init_kg_tables()
    conn = get_db()

    # Create a synthetic decision entity
    decision_name = f"[{agent_name}] {decision_type}: {subject_entity[:40]}"
    decision_etype = "Finding"
    nid = _node_id(decision_name, decision_etype)
    now = datetime.now(timezone.utc).isoformat()

    # Upsert decision node
    existing = conn.execute("SELECT id FROM ma_kg_nodes WHERE id=?", (nid,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO ma_kg_nodes (id, name, entity_type, mention_count, doc_ids, chunk_ids, "
            "first_seen, last_seen, confidence, properties) VALUES (?,?,?,1,?,?,?,?,?,?)",
            (nid, decision_name, decision_etype,
             json.dumps(source_doc_ids or []), json.dumps([]),
             now, now, round(confidence, 3),
             json.dumps({"agent": agent_name, "verdict": verdict[:500],
                         "decision_type": decision_type})),
        )
    else:
        conn.execute(
            "UPDATE ma_kg_nodes SET mention_count=mention_count+1, last_seen=?, confidence=? WHERE id=?",
            (now, round(confidence, 3), nid),
        )

    # Link decision to subject entity (causal edge)
    subject_node = conn.execute(
        "SELECT id FROM ma_kg_nodes WHERE LOWER(name) LIKE ? AND merged_into IS NULL "
        "ORDER BY mention_count DESC LIMIT 1",
        (f"%{subject_entity.lower()}%",),
    ).fetchone()
    if subject_node:
        _eid = _edge_id(nid, subject_node["id"], "agent_decision_about")
        if not conn.execute("SELECT id FROM ma_kg_edges WHERE id=?", (_eid,)).fetchone():
            conn.execute(
                "INSERT INTO ma_kg_edges (id, src_node_id, tgt_node_id, edge_type, weight, severity, doc_ids) "
                "VALUES (?,?,?,?,?,?,?)",
                (_eid, nid, subject_node["id"], "agent_decision_about",
                 confidence, "medium", json.dumps(source_doc_ids or [])),
            )

    # Link to other entities involved (context edges)
    for linked in (linked_entities or []):
        linked_node = conn.execute(
            "SELECT id FROM ma_kg_nodes WHERE LOWER(name) LIKE ? AND merged_into IS NULL "
            "ORDER BY mention_count DESC LIMIT 1",
            (f"%{linked.lower()}%",),
        ).fetchone()
        if linked_node:
            _eid2 = _edge_id(nid, linked_node["id"], "agent_context")
            if not conn.execute("SELECT id FROM ma_kg_edges WHERE id=?", (_eid2,)).fetchone():
                conn.execute(
                    "INSERT INTO ma_kg_edges (id, src_node_id, tgt_node_id, edge_type, weight, severity, doc_ids) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (_eid2, nid, linked_node["id"], "agent_context",
                     0.5, "low", json.dumps(source_doc_ids or [])),
                )

    conn.commit()
    conn.close()
    return nid


# ─── M&A Document Type Detection ─────────────────────────────────────────────

# Keyword fingerprints for each M&A document type
_MA_DOC_TYPE_SIGNALS: list[tuple[str, list[str], int]] = [
    # (doc_type, keywords, min_hits_to_classify)
    ("SPA",         ["share purchase agreement","agreement and plan of merger","definitive agreement","purchase price","closing conditions","representations and warranties","covenants","indemnification","escrow","merger sub","surviving corporation"], 3),
    ("CIM",         ["confidential information memorandum","investment highlights","market opportunity","management team","financial summary","growth strategy","cim"], 2),
    ("NDA",         ["non-disclosure","confidentiality agreement","proprietary information","shall not disclose","receiving party","disclosing party"], 2),
    ("LOI",         ["letter of intent","non-binding","exclusivity","indicative valuation","subject to due diligence","good faith negotiation"], 2),
    ("DD_REPORT",   ["due diligence","findings summary","red flag","diligence scope","management interview","site visit","pending litigation"], 3),
    ("BOARD_MINS",  ["board of directors","minutes","quorum","resolution","motion","seconded","unanimous","special committee"], 3),
    ("FINANCIALS",  ["balance sheet","income statement","cash flow","revenue","ebitda","operating expenses","fiscal year","audited","unaudited"], 3),
    ("FORECAST",    ["forecast","projection","budget","plan","assumptions","sensitivity","base case","downside","upside"], 3),
    ("EMPLOYMENT",  ["employment agreement","severance","non-compete","non-solicitation","base salary","bonus","equity grant"], 2),
    ("IP",          ["intellectual property","patent","trademark","copyright","software license","open source","assignment"], 2),
    ("REGULATORY",  ["regulatory approval","antitrust","competition authority","hsr","merger control","filing"], 2),
]

# M&A defined terms: how roles map to entity types
# Key = lowercased defined-term; Value = (entity_type, role_description)
_MA_DEFINED_TERMS: dict[str, tuple[str, str]] = {
    "the company":    ("Company", "Target Company"),
    "company":        ("Company", "Target Company"),
    "the target":     ("Company", "Target Company"),
    "target":         ("Company", "Target Company"),
    "the buyer":      ("Company", "Acquirer"),
    "buyer":          ("Company", "Acquirer"),
    "the acquirer":   ("Company", "Acquirer"),
    "acquirer":       ("Company", "Acquirer"),
    "the seller":     ("Company", "Seller"),
    "seller":         ("Company", "Seller"),
    "the parent":     ("Company", "Parent/Acquirer"),
    "parent":         ("Company", "Parent/Acquirer"),
    "the purchaser":  ("Company", "Acquirer"),
    "purchaser":      ("Company", "Acquirer"),
    "holdco":         ("Company", "HoldCo"),
    "newco":          ("Company", "NewCo/SPV"),
    "the bidder":     ("Company", "Bidder"),
    "bidder":         ("Company", "Bidder"),
    "the group":      ("Company", "Group Entity"),
    "the guarantor":  ("Company", "Guarantor"),
    "guarantor":      ("Company", "Guarantor"),
}


def detect_doc_type(text: str) -> str:
    """
    Classify an M&A document from its text content.
    Returns doc type string: SPA | CIM | NDA | LOI | DD_REPORT |
    BOARD_MINS | FINANCIALS | FORECAST | EMPLOYMENT | IP | REGULATORY | UNKNOWN
    """
    text_lower = text.lower()
    best_type, best_score = "UNKNOWN", 0

    for doc_type, keywords, min_hits in _MA_DOC_TYPE_SIGNALS:
        hits = sum(1 for kw in keywords if kw in text_lower)
        # Score = hits × (hits / min_hits) — quadratic boost for exceeding minimum
        score = hits * (hits / min_hits) if hits >= min_hits else hits * 0.3
        if score > best_score:
            best_score, best_type = score, doc_type

    return best_type


def resolve_defined_terms(doc_id: int) -> dict:
    """
    Resolve M&A defined terms across documents.

    In M&A documents, parties are referred to by defined terms:
      "the Company" = TechTarget Inc
      "the Buyer" = Permira Advisers LLC

    Strategy:
    1. Find the highest-mention Company nodes in the KG (these are the real entities)
    2. Look for defined-term role patterns in doc text ("hereinafter referred to as 'the Company'")
    3. When found, create "alias_of" edges linking the defined-term mention to the real entity
    4. Mark aliases in node properties so downstream dedup can collapse them

    Returns: {resolved_terms, aliases_created, ambiguous_terms}

    This dramatically improves graph quality for 50-60 doc corpora where "the Company"
    appears hundreds of times and PPR correctly propagates risk scores.
    """
    init_kg_tables()
    conn = get_db()

    # Get text for this document
    doc_row = conn.execute("SELECT filename FROM ma_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc_row:
        conn.close()
        return {"error": "Document not found"}

    chunks = conn.execute(
        "SELECT text FROM ma_chunks WHERE doc_id=? ORDER BY page, id",
        (doc_id,),
    ).fetchall()
    full_text = "\n".join(c["text"] for c in chunks)

    # ── Step 1: Find canonical entity bindings in this document ──
    #
    # Two-phase approach handles both formats:
    #   “Squarespace, Inc., a Delaware corporation (the “Company”)”
    #   “Spaceship Purchaser, Inc., a Delaware corporation (“Parent”)”
    #   “X Corp, referred to herein as 'the Company'”
    #
    # Phase 1: Find role-term anchors (the parenthetical or “referred to” phrase)
    # Phase 2: Look left (up to 160 chars) for the last company name

    # Matches (Parent), (the “Company”), (“Merger Sub”), (the 'Buyer') etc.
    _ROLE_ANCHOR_RE = re.compile(
        r'\(\s*(?:the\s+)?[“””\'”]?\s*'
        r'(the\s+(?:Company|Buyer|Seller|Parent|Acquirer|Purchaser|Target|Bidder|'
        r'Guarantor|Group)|Parent|Company|Buyer|Seller|Target|Purchaser|'
        r'Merger\s+Sub|NewCo|HoldCo|Buyer\s+Parties)'
        r'\s*[“””\'”]?\s*(?:,\s*and\s+together[^)]{0,60})?\)',
        re.IGNORECASE,
    )

    # Matches the LAST proper company name (ending in legal suffix) in a text block
    _COMPANY_NAME_FIND = re.compile(
        r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}'
        r',?\s*(?:Inc\.|Inc|Corp\.|Corp|LLC|Ltd\.|Ltd|GmbH|AG|BV|NV|SE|PLC)\.?)',
    )

    # “referred to as” pattern as fallback
    _REFERRED_AS_RE = re.compile(
        r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}[, ]+(?:Inc\.|Corp\.|LLC|Ltd|GmbH|AG|SE|PLC)\.?)'
        r'[^,]{0,80}?'
        r'(?:herein(?:after)?|collectively|individually)?\s*'
        r'(?:referred\s+to\s+(?:herein\s+)?as|known\s+as|defined\s+as)\s+'
        r'[“””\'”]?\s*(the\s+(?:Company|Buyer|Seller|Parent|Target|Acquirer))\s*[“””\'”]?',
        re.IGNORECASE,
    )

    bindings: dict[str, str] = {}  # defined_term_lower → real_entity_name
    search_window = full_text[:80000]

    # Phase 1+2: anchor search
    for m in _ROLE_ANCHOR_RE.finditer(search_window):
        defined_term = m.group(1).strip().lower()
        # Look up to 160 chars before the opening paren for the company name
        start = max(0, m.start() - 160)
        prefix = search_window[start:m.start()]
        name_matches = list(_COMPANY_NAME_FIND.finditer(prefix))
        if name_matches:
            real_name = name_matches[-1].group(1).strip().rstrip(',').rstrip('.')
            # Strip any leading non-uppercase chars (e.g. "by and among Spaceship..." → "Spaceship...")
            real_name = re.sub(r'^[^A-Z]+', '', real_name).strip()
            if real_name and len(real_name) >= 5 and defined_term not in bindings:
                bindings[defined_term] = real_name

    # “referred to as” fallback
    for m in _REFERRED_AS_RE.finditer(search_window):
        real_name = m.group(1).strip().rstrip(',').rstrip('.')
        defined_term = m.group(2).strip().lower()
        if real_name and defined_term and defined_term not in bindings:
            bindings[defined_term] = real_name

    # ── Step 2: Check existing KG nodes for the real entities ──
    aliases_created = 0
    resolved_terms: list[dict] = []
    ambiguous: list[str] = []

    for defined_term, real_name in bindings.items():
        # Find the real entity node in the KG
        real_node = conn.execute(
            "SELECT id, name, entity_type, mention_count FROM ma_kg_nodes "
            "WHERE LOWER(name) LIKE ? AND merged_into IS NULL "
            "ORDER BY mention_count DESC LIMIT 1",
            (f"%{real_name[:30].lower()}%",),
        ).fetchone()

        # If the KG node's name is a noisy version of our clean real_name, rename it
        # e.g. KG has "by and among Spaceship Purchaser, Inc." but real_name is "Spaceship Purchaser, Inc"
        if real_node and real_node["name"] != real_name:
            stored = real_node["name"]
            # Use our clean extraction if stored name is longer and contains our name,
            # or if stored name starts with lowercase (was a garbage extraction)
            if (real_name in stored and len(stored) > len(real_name) + 4) or not stored[0].isupper():
                conn.execute(
                    "UPDATE ma_kg_nodes SET name=? WHERE id=?",
                    (real_name, real_node["id"]),
                )
                real_node = dict(real_node)
                real_node["name"] = real_name

        if not real_node:
            # Not in KG yet — add it as a Company node with the defined-term role
            role = _MA_DEFINED_TERMS.get(defined_term.lower(), ("Company", "Unknown"))[1]
            nid = _node_id(real_name, "Company")
            now = datetime.now(timezone.utc).isoformat()
            existing = conn.execute("SELECT id FROM ma_kg_nodes WHERE id=?", (nid,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO ma_kg_nodes (id, name, entity_type, mention_count, doc_ids, chunk_ids, first_seen, last_seen, properties) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (nid, real_name, "Company", 1,
                     json.dumps([doc_id]), json.dumps([]),
                     now, now,
                     json.dumps({"role": role, "defined_as": defined_term})),
                )
                real_node = {"id": nid, "name": real_name, "entity_type": "Company"}
            else:
                real_node = {"id": nid, "name": real_name, "entity_type": "Company"}

        # Find any nodes that represent the defined-term role (e.g. "the Company" as a node)
        # These would have been extracted as Company with name "Surviving Corp" etc.
        role_node = conn.execute(
            "SELECT id, name FROM ma_kg_nodes "
            "WHERE LOWER(name)=? AND merged_into IS NULL LIMIT 1",
            (defined_term,),
        ).fetchone()

        # Create an "alias_of" edge connecting the defined term to the real entity
        eid = _edge_id(real_node["id"], real_node["id"] + "_alias", "alias_of")
        eid = _edge_id(real_node["id"], _node_id(defined_term, "Company"), "alias_of")
        if role_node and role_node["id"] != real_node["id"]:
            merge_eid = _edge_id(role_node["id"], real_node["id"], "alias_of")
            if not conn.execute("SELECT id FROM ma_kg_edges WHERE id=?", (merge_eid,)).fetchone():
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO ma_kg_edges (id, src_node_id, tgt_node_id, edge_type, weight, severity, doc_ids) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (merge_eid, role_node["id"], real_node["id"],
                     "alias_of", 1.0, "low", json.dumps([doc_id])),
                )
                aliases_created += 1

        resolved_terms.append({
            "defined_term": defined_term,
            "resolved_to": real_node["name"],
            "node_id": real_node["id"],
        })

    conn.commit()
    conn.close()

    return {
        "doc_id": doc_id,
        "bindings_found": len(bindings),
        "resolved_terms": resolved_terms,
        "aliases_created": aliases_created,
        "ambiguous_terms": ambiguous,
    }


def get_cross_doc_entity_summary(top_n: int = 20) -> dict:
    """
    Cross-document entity importance summary for large M&A data rooms (50-60 docs).

    Returns entities ranked by:
    1. doc_coverage — appears in how many documents (% of total)
    2. mention_count — total mentions across all docs
    3. edge_count — how many relationships it has (connectivity)
    4. pheromone_intensity — how much agent attention it attracted

    Entities that appear in many documents AND have many edges are the
    "pivot entities" of the deal — the most analytically important nodes.
    """
    init_kg_tables()
    conn = get_db()

    total_docs = conn.execute("SELECT COUNT(*) FROM ma_documents").fetchone()[0] or 1

    # Get nodes with their edge counts
    rows = conn.execute(
        """
        SELECT
            n.id, n.name, n.entity_type, n.mention_count,
            n.pheromone_intensity, n.community_id,
            json_array_length(n.doc_ids) AS doc_coverage_count,
            COUNT(e.id) AS edge_count
        FROM ma_kg_nodes n
        LEFT JOIN ma_kg_edges e
            ON (e.src_node_id = n.id OR e.tgt_node_id = n.id)
        WHERE n.merged_into IS NULL
        GROUP BY n.id
        ORDER BY doc_coverage_count DESC, mention_count DESC
        LIMIT ?
        """,
        (top_n * 3,),   # over-fetch then re-rank
    ).fetchall()

    conn.close()

    # Compute composite importance score
    # importance = 0.4*doc_coverage + 0.35*log(mentions) + 0.25*log(edges+1)
    import math as _math
    max_docs = total_docs
    max_mentions = max((r["mention_count"] for r in rows), default=1) or 1
    max_edges = max((r["edge_count"] for r in rows), default=1) or 1

    pivot_entities = []
    for r in rows:
        doc_cov = r["doc_coverage_count"] / max_docs
        mention_score = _math.log1p(r["mention_count"]) / _math.log1p(max_mentions)
        edge_score = _math.log1p(r["edge_count"]) / _math.log1p(max_edges)
        importance = round(0.4 * doc_cov + 0.35 * mention_score + 0.25 * edge_score, 4)
        pivot_entities.append({
            "id": r["id"],
            "name": r["name"],
            "entity_type": r["entity_type"],
            "mention_count": r["mention_count"],
            "doc_coverage": r["doc_coverage_count"],
            "doc_coverage_pct": round(r["doc_coverage_count"] / total_docs * 100, 1),
            "edge_count": r["edge_count"],
            "pheromone_intensity": r["pheromone_intensity"],
            "importance_score": importance,
        })

    # Re-rank by importance and take top_n
    pivot_entities.sort(key=lambda x: -x["importance_score"])
    return {
        "total_docs": total_docs,
        "total_entities": len(rows),
        "top_n": top_n,
        "pivot_entities": pivot_entities[:top_n],
    }


# ─── TGS-RAG: Bidirectional KG ↔ Chunk Mapping ──────────────────────────────

def tgs_rag_search(query: str, top_k: int = 12) -> dict:
    """
    TGS-RAG bidirectional retrieval (Zhong & Chen, 2026 pattern).

    Standard RAG: query → BM25/vector → chunks
    TGS-RAG:      query → KG entity match → edge traversal → cross-type neighbors → chunks

    The key upgrade: when you ask "Revenue Risk", BM25 finds chunks containing
    those exact words. TGS-RAG *also* traverses the KG edge from FinancialMetric
    nodes (Net Revenue) to Risk nodes (Material Adverse Effect) and pulls the
    chunks attached to those connected entities — chunks that never mentioned
    "revenue risk" explicitly but contain the evidential connection.

    Returns chunks ranked by: seed_score × edge_weight × cross_type_bonus,
    with full KG provenance chain (seed → edge → neighbor → chunk).
    """
    init_kg_tables()
    conn = get_db()

    # ── Step 1: Find seed entities via BM25 on name + type tokens ──
    nodes_raw = conn.execute(
        "SELECT id, name, entity_type, mention_count, chunk_ids "
        "FROM ma_kg_nodes WHERE merged_into IS NULL AND superseded_by IS NULL"
    ).fetchall()
    edges_raw = conn.execute(
        "SELECT src_node_id, tgt_node_id, edge_type, weight, sentence_excerpt "
        "FROM ma_kg_edges"
    ).fetchall()

    query_terms = set(re.findall(r'\w{3,}', query.lower()))

    def _type_tokens_local(etype: str) -> list[str]:
        parts = re.findall(r'[A-Z][a-z]+|[A-Z]+(?=[A-Z]|$)', etype)
        return [p.lower() for p in parts] if parts else [etype.lower()]

    # Score every node by BM25 against query
    seed_scores: dict[str, float] = {}
    for nd in nodes_raw:
        name_tokens = re.findall(r'\w{3,}', nd["name"].lower())
        type_tokens = _type_tokens_local(nd["entity_type"])
        all_tokens = name_tokens + type_tokens
        if not all_tokens:
            continue
        score = sum(1 for t in query_terms if t in all_tokens)
        if score > 0:
            seed_scores[nd["id"]] = score / len(all_tokens)

    if not seed_scores:
        conn.close()
        return {"results": [], "query": query, "method": "tgs_rag", "seed_hits": 0}

    # Normalise seed scores
    max_seed = max(seed_scores.values()) or 1.0
    seed_scores = {k: v / max_seed for k, v in seed_scores.items()}

    # ── Step 2: Build adjacency map and node lookup ──
    node_by_id: dict[str, dict] = {nd["id"]: dict(nd) for nd in nodes_raw}
    adj: dict[str, list[dict]] = defaultdict(list)
    for e in edges_raw:
        adj[e["src_node_id"]].append({
            "neighbor": e["tgt_node_id"],
            "edge_type": e["edge_type"],
            "weight": float(e["weight"] or 1.0),
            "excerpt": e["sentence_excerpt"] or "",
        })
        adj[e["tgt_node_id"]].append({
            "neighbor": e["src_node_id"],
            "edge_type": e["edge_type"],
            "weight": float(e["weight"] or 1.0),
            "excerpt": e["sentence_excerpt"] or "",
        })

    # Cross-type multiplier: bonus for traversing between different entity types
    # This implements the "M mapping" — Financial↔Risk, Company↔Contract get boosted
    _CROSS_TYPE_PAIRS = {
        frozenset({"FinancialMetric", "Risk"}): 1.8,
        frozenset({"Company", "Risk"}): 1.6,
        frozenset({"Company", "Contract"}): 1.5,
        frozenset({"Contract", "Risk"}): 1.7,
        frozenset({"FinancialMetric", "Finding"}): 1.5,
        frozenset({"Risk", "EvidenceGap"}): 1.9,
        frozenset({"Claim", "Risk"}): 1.6,
        frozenset({"Company", "Person"}): 1.3,
    }

    # ── Step 3: Traverse from seeds to neighbors, collect chunks ──
    # chunk_id → best pull score + provenance chain
    chunk_pulls: dict[int, dict] = {}

    top_seeds = sorted(seed_scores.items(), key=lambda x: -x[1])[:5]
    for seed_id, seed_score in top_seeds:
        seed_node = node_by_id.get(seed_id)
        if not seed_node:
            continue

        for edge in adj.get(seed_id, []):
            neighbor_id = edge["neighbor"]
            neighbor = node_by_id.get(neighbor_id)
            if not neighbor:
                continue

            # Cross-type bonus
            pair = frozenset({seed_node["entity_type"], neighbor["entity_type"]})
            multiplier = _CROSS_TYPE_PAIRS.get(pair, 1.0)

            pull_score = seed_score * edge["weight"] * multiplier

            # Pull chunks from the neighbor node
            raw_chunk_ids = neighbor.get("chunk_ids") or "[]"
            try:
                neighbor_chunk_ids = json.loads(raw_chunk_ids) if isinstance(raw_chunk_ids, str) else raw_chunk_ids
            except Exception:
                neighbor_chunk_ids = []

            for cid in neighbor_chunk_ids[:3]:  # max 3 chunks per neighbor
                if cid not in chunk_pulls or chunk_pulls[cid]["pull_score"] < pull_score:
                    chunk_pulls[cid] = {
                        "chunk_id": cid,
                        "pull_score": round(pull_score, 5),
                        "seed_entity": seed_node["name"],
                        "seed_type": seed_node["entity_type"],
                        "edge_type": edge["edge_type"],
                        "neighbor_entity": neighbor["name"],
                        "neighbor_type": neighbor["entity_type"],
                        "cross_type_bonus": round(multiplier, 2),
                        "kg_path": f"{seed_node['name']} --[{edge['edge_type']}]--> {neighbor['name']}",
                        "excerpt_hint": edge["excerpt"][:120],
                    }

        # Also pull chunks directly from seed node itself
        raw_seed_cids = seed_node.get("chunk_ids") or "[]"
        try:
            seed_chunk_ids = json.loads(raw_seed_cids) if isinstance(raw_seed_cids, str) else raw_seed_cids
        except Exception:
            seed_chunk_ids = []

        for cid in seed_chunk_ids[:2]:
            if cid not in chunk_pulls:
                chunk_pulls[cid] = {
                    "chunk_id": cid,
                    "pull_score": round(seed_score, 5),
                    "seed_entity": seed_node["name"],
                    "seed_type": seed_node["entity_type"],
                    "edge_type": "direct",
                    "neighbor_entity": seed_node["name"],
                    "neighbor_type": seed_node["entity_type"],
                    "cross_type_bonus": 1.0,
                    "kg_path": f"{seed_node['name']} [direct seed]",
                    "excerpt_hint": "",
                }

    if not chunk_pulls:
        conn.close()
        return {"results": [], "query": query, "method": "tgs_rag", "seed_hits": len(top_seeds)}

    # ── Step 4: Fetch actual chunk text ──
    cid_list = list(chunk_pulls.keys())
    placeholders = ",".join("?" * len(cid_list))
    rows = conn.execute(
        f"SELECT id, doc_id, text, page FROM ma_chunks WHERE id IN ({placeholders})",
        cid_list,
    ).fetchall()
    conn.close()

    chunk_text_map = {r["id"]: dict(r) for r in rows}

    # ── Step 5: Build result list ──
    results = []
    for cid, pull in chunk_pulls.items():
        chunk = chunk_text_map.get(cid)
        if not chunk:
            continue
        results.append({
            **pull,
            "doc_id": chunk["doc_id"],
            "page": chunk["page"],
            "text": chunk["text"][:400],
            "full_text_len": len(chunk["text"]),
        })

    results.sort(key=lambda x: -x["pull_score"])
    return {
        "results": results[:top_k],
        "query": query,
        "method": "tgs_rag",
        "seed_hits": len(top_seeds),
        "chunks_pulled": len(results),
        "cross_type_pulls": sum(1 for r in results if r["cross_type_bonus"] > 1.0),
    }


# ─── Bi-Temporal Supersession ────────────────────────────────────────────────

def apply_supersession(
    old_node_id: str,
    new_node_id: str,
    reason: str,
    confidence: float = 0.9,
) -> dict:
    """
    Mark old_node as superseded by new_node.

    This implements the bi-temporal model: old facts are NOT deleted.
    They are marked SUPERSEDED_BY with a timestamp and reason.
    The graph retains both nodes, connected by a 'supersession' edge,
    enabling reports like:
      "Target originally claimed X [2023], but evidence Y [2026] supersedes this."

    Used by: SupersessionJury verdict, temporal drift detector, upload impact analysis.
    """
    init_kg_tables()
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()

    old_node = conn.execute("SELECT id, name, entity_type FROM ma_kg_nodes WHERE id=?", (old_node_id,)).fetchone()
    new_node = conn.execute("SELECT id, name, entity_type FROM ma_kg_nodes WHERE id=?", (new_node_id,)).fetchone()

    if not old_node or not new_node:
        conn.close()
        return {"error": "One or both nodes not found", "old": old_node_id, "new": new_node_id}

    # Mark old node as superseded
    conn.execute(
        "UPDATE ma_kg_nodes SET superseded_by=?, superseded_at=?, supersession_reason=? WHERE id=?",
        (new_node_id, now, reason, old_node_id),
    )

    # Create supersession edge (keeps the temporal relationship queryable)
    edge_id = _edge_id(old_node_id, new_node_id, "supersession")
    existing = conn.execute("SELECT id FROM ma_kg_edges WHERE id=?", (edge_id,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO ma_kg_edges (id, src_node_id, tgt_node_id, edge_type, weight, severity, "
            "doc_ids, sentence_excerpt, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (edge_id, old_node_id, new_node_id, "supersession", confidence, "high",
             json.dumps([]), reason[:200], now, now),
        )

    conn.commit()
    conn.close()

    return {
        "superseded": old_node["name"],
        "superseded_by": new_node["name"],
        "reason": reason,
        "confidence": confidence,
        "timestamp": now,
    }


def get_supersession_chain(entity_name: str) -> list[dict]:
    """
    Return the full temporal chain for an entity: original → superseded_by → ...
    Useful for generating timeline reports: "Claim A was true in 2022, superseded by B in 2024."
    """
    init_kg_tables()
    conn = get_db()

    # Find the base node (the one not superseded yet, or root of chain)
    rows = conn.execute(
        "SELECT id, name, entity_type, superseded_by, superseded_at, supersession_reason, "
        "doc_ids, mention_count, first_seen, last_seen "
        "FROM ma_kg_nodes WHERE LOWER(name) LIKE ? ORDER BY first_seen",
        (f"%{entity_name[:30].lower()}%",),
    ).fetchall()
    conn.close()

    chain = []
    for r in rows:
        chain.append({
            "id": r["id"],
            "name": r["name"],
            "entity_type": r["entity_type"],
            "status": "superseded" if r["superseded_by"] else "current",
            "superseded_by": r["superseded_by"],
            "superseded_at": r["superseded_at"],
            "supersession_reason": r["supersession_reason"],
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
            "mention_count": r["mention_count"],
        })

    # Sort: superseded nodes first (oldest), then current
    chain.sort(key=lambda x: (x["status"] == "current", x["first_seen"] or ""))
    return chain


# ─── Proactive Upload Impact Analysis ────────────────────────────────────────

def analyze_upload_impact(doc_id: int) -> dict:
    """
    Proactive impact analysis: after uploading a new document, automatically
    audit the entire deal and report what changed.

    Three questions:
    1. RESOLVED GAPS:  Does this doc address any existing EvidenceGap nodes?
       (Topic keyword overlap between gap name and new chunks)

    2. NEW CONTRADICTIONS: Does this doc contradict any existing Claim/Finding/Risk?
       (Number conflicts, negation patterns, opposing keywords)

    3. SUPERSESSION CANDIDATES: Does this doc contain newer versions of existing claims?
       (Same entity, different value or date — flagged for Jury review)

    Returns a structured impact report ready for display in the UI.
    The pitch: "I don't wait for you to ask questions. Every time you upload a doc,
    the system audits the whole deal and tells you what changed."
    """
    init_kg_tables()
    conn = get_db()

    # Get new doc's text
    new_chunks = conn.execute(
        "SELECT id, text FROM ma_chunks WHERE doc_id=? ORDER BY id",
        (doc_id,),
    ).fetchall()
    if not new_chunks:
        conn.close()
        return {"doc_id": doc_id, "error": "No chunks found"}

    new_text_combined = " ".join(c["text"] for c in new_chunks).lower()
    new_tokens = set(re.findall(r'\w{4,}', new_text_combined))

    # ── Part 1: Resolved EvidenceGaps ──
    gap_nodes = conn.execute(
        "SELECT id, name, doc_ids FROM ma_kg_nodes "
        "WHERE entity_type='EvidenceGap' AND merged_into IS NULL AND superseded_by IS NULL"
    ).fetchall()

    resolved_gaps = []
    for gap in gap_nodes:
        # Skip gaps that came from this doc itself
        gap_doc_ids = json.loads(gap["doc_ids"] or "[]")
        if doc_id in gap_doc_ids:
            continue
        # Check keyword overlap between gap name and new doc
        gap_tokens = set(re.findall(r'\w{4,}', gap["name"].lower()))
        overlap = gap_tokens & new_tokens
        # Also check for topic words: if gap is "financial statements not available",
        # look for "financial statements" plus actual numbers/data in new doc
        if len(overlap) >= max(1, len(gap_tokens) // 2):
            # Score: what % of the gap's topic words appear in new doc
            coverage = len(overlap) / max(len(gap_tokens), 1)
            resolved_gaps.append({
                "gap_id": gap["id"],
                "gap_name": gap["name"],
                "coverage_score": round(coverage, 3),
                "matched_terms": list(overlap)[:5],
                "resolution": "partial" if coverage < 0.8 else "likely",
            })

    resolved_gaps.sort(key=lambda x: -x["coverage_score"])

    # ── Part 2: New Contradictions ──
    # Compare numeric claims: same metric name but different values
    # Also look for explicit negation patterns
    existing_claims = conn.execute(
        "SELECT n.id, n.name, n.entity_type, n.doc_ids, c.text as source_text "
        "FROM ma_kg_nodes n "
        "LEFT JOIN ma_chunks c ON c.id = (SELECT chunk_ids FROM ma_kg_nodes WHERE id=n.id LIMIT 1) "
        "WHERE n.entity_type IN ('Claim','Finding','FinancialMetric') "
        "AND n.merged_into IS NULL AND n.superseded_by IS NULL",
    ).fetchall()

    # Pull actual chunk texts for existing claims
    claim_chunk_ids = []
    for cl in existing_claims:
        raw_cids = conn.execute(
            "SELECT chunk_ids FROM ma_kg_nodes WHERE id=?", (cl["id"],)
        ).fetchone()
        if raw_cids:
            try:
                cids = json.loads(raw_cids["chunk_ids"] or "[]")
                claim_chunk_ids.extend(cids[:2])
            except Exception:
                pass

    claim_texts: dict[int, str] = {}
    if claim_chunk_ids:
        ph = ",".join("?" * len(claim_chunk_ids))
        rows = conn.execute(
            f"SELECT id, text FROM ma_chunks WHERE id IN ({ph})", claim_chunk_ids
        ).fetchall()
        claim_texts = {r["id"]: r["text"] for r in rows}

    _NEGATION_WORDS = {"not", "never", "no", "contrary", "incorrect", "false",
                       "disputed", "denied", "rejected", "retracted", "superseded"}
    _NUMBER_RE = re.compile(r'\b(\d[\d,\.]*(?:\s*(?:million|billion|%|percent))?\b)')

    contradictions = []
    for cl in existing_claims:
        # Skip if the claim comes from this doc
        cl_doc_ids = json.loads(cl["doc_ids"] or "[]")
        if doc_id in cl_doc_ids:
            continue

        cl_tokens = set(re.findall(r'\w{4,}', cl["name"].lower()))
        overlap = cl_tokens & new_tokens
        if len(overlap) < max(1, len(cl_tokens) // 2):
            continue  # New doc doesn't mention this claim's topic

        # Check for negation signals in new doc near this topic
        topic_words = list(cl_tokens)[:4]
        negation_score = 0
        for chunk in new_chunks:
            chunk_lower = chunk["text"].lower()
            if any(w in chunk_lower for w in topic_words[:2]):
                neg_count = sum(1 for w in _NEGATION_WORDS if w in chunk_lower)
                negation_score = max(negation_score, neg_count)

        # Number conflict detection: same metric, different value
        number_conflict = None
        if cl["entity_type"] == "FinancialMetric":
            # Find numbers in existing claim source chunks
            raw_cids = conn.execute("SELECT chunk_ids FROM ma_kg_nodes WHERE id=?", (cl["id"],)).fetchone()
            if raw_cids:
                try:
                    cids = json.loads(raw_cids["chunk_ids"] or "[]")
                    for cid in cids[:1]:
                        old_text = claim_texts.get(cid, "")
                        old_nums = set(_NUMBER_RE.findall(old_text.lower()))
                        new_nums = set(_NUMBER_RE.findall(new_text_combined))
                        if old_nums and new_nums and old_nums != new_nums:
                            # Same metric, different numbers → potential conflict
                            if cl_tokens & new_tokens:
                                number_conflict = {
                                    "old_values": list(old_nums)[:3],
                                    "new_values": list(new_nums)[:3],
                                }
                except Exception:
                    pass

        if negation_score >= 2 or number_conflict:
            contradictions.append({
                "claim_id": cl["id"],
                "claim_name": cl["name"],
                "claim_type": cl["entity_type"],
                "contradiction_type": "number_conflict" if number_conflict else "negation_pattern",
                "negation_signals": negation_score,
                "number_conflict": number_conflict,
                "matched_terms": list(overlap)[:4],
                "severity": "high" if (negation_score >= 3 or number_conflict) else "medium",
            })

    contradictions.sort(key=lambda x: (x["severity"] == "high", x["negation_signals"]), reverse=True)

    # ── Part 3: Supersession Candidates ──
    # Find existing nodes where the new doc mentions the same entity name but different values
    all_nodes = conn.execute(
        "SELECT id, name, entity_type, doc_ids, mention_count "
        "FROM ma_kg_nodes WHERE merged_into IS NULL AND superseded_by IS NULL "
        "AND doc_ids != '[]' AND doc_ids NOT LIKE ?",
        (f'%{doc_id}%',),
    ).fetchall()

    supersession_candidates = []
    for nd in all_nodes:
        # Check if new doc mentions this entity by name (at least 2 name tokens)
        name_tokens = set(re.findall(r'\w{4,}', nd["name"].lower()))
        if len(name_tokens) < 1:
            continue
        overlap = name_tokens & new_tokens
        if len(overlap) >= max(1, len(name_tokens)):
            # Entity appears in new doc — flag as supersession candidate
            supersession_candidates.append({
                "node_id": nd["id"],
                "entity_name": nd["name"],
                "entity_type": nd["entity_type"],
                "existing_doc_count": len(json.loads(nd["doc_ids"] or "[]")),
                "note": "Entity re-appears in new doc — Jury recommended to check for supersession",
            })

    supersession_candidates = supersession_candidates[:8]  # cap at 8

    # ── Emit signals for resolved gaps and contradictions ──
    signals_emitted = []
    if new_chunks:
        first_chunk_id = new_chunks[0]["id"]
        try:
            from ma.signal_pheromones import emit_signal, SignalType  # noqa: PLC0415
            for gap in resolved_gaps[:3]:
                s = emit_signal(
                    SignalType.EVIDENCE_GAP, gap["gap_name"],
                    source_chunk_id=first_chunk_id, source_doc_id=doc_id,
                    strength=gap["coverage_score"],
                    payload={"resolution": gap["resolution"], "gap_id": gap["gap_id"]},
                )
                signals_emitted.append(s.signal_id)
            for contradiction in contradictions[:2]:
                s = emit_signal(
                    SignalType.CONTRADICTION, contradiction["claim_name"],
                    source_chunk_id=first_chunk_id, source_doc_id=doc_id,
                    strength=0.8 if contradiction["severity"] == "high" else 0.5,
                    payload={"claim_id": contradiction["claim_id"],
                             "type": contradiction["contradiction_type"]},
                )
                signals_emitted.append(s.signal_id)
        except Exception:
            pass  # Signal emission is best-effort

    conn.close()

    # ── Impact score: how significant is this upload? ──
    impact_score = round(
        0.4 * min(1.0, len(resolved_gaps) / 3) +
        0.35 * min(1.0, len(contradictions) / 2) +
        0.25 * min(1.0, len(supersession_candidates) / 5),
        3,
    )

    return {
        "doc_id": doc_id,
        "impact_score": impact_score,
        "summary": _impact_summary(resolved_gaps, contradictions, supersession_candidates),
        "resolved_gaps": resolved_gaps,
        "contradictions": contradictions,
        "supersession_candidates": supersession_candidates,
        "signals_emitted": signals_emitted,
        "counts": {
            "resolved_gaps": len(resolved_gaps),
            "contradictions": len(contradictions),
            "supersession_candidates": len(supersession_candidates),
        },
    }


# ─── Ghost Nodes — Post-Acquisition Structural Simulation ───────────────────
# When an SPA is uploaded, spawn "ghost nodes" representing the simulated
# post-acquisition corporate structure. These are speculative future-state
# entities, visually distinct in the D3 graph (dashed, lower opacity).
# Pheromones run on BOTH current-state and ghost nodes simultaneously,
# surfacing structural mismatches before closing.

_SPA_GHOST_TRIGGERS = re.compile(
    r'merger\s+sub|newco|holdco|escrow\s+(?:account|agent)|'
    r'working\s+capital\s+(?:peg|escrow|holdback)|'
    r'purchase\s+price\s+(?:adjustment|escrow)|'
    r'earn[\s-]?out\s+(?:escrow|account|obligation)|'
    # Broader SPA/merger agreement indicators (narrative prose)
    r'merger\s+agreement|'
    r'purchase\s+and\s+sale\s+agreement|'
    r'definitive\s+agreement|'
    r'representations\s+and\s+warranties|'
    r'closing\s+condition|conditions\s+to\s+closing|'
    r'material\s+adverse\s+(?:effect|change)|'
    r'indemnif(?:y|ication)\s+(?:the\s+)?(?:purchaser|buyer|acquiror)',
    re.IGNORECASE,
)
_NEWCO_RE = re.compile(
    r'\b(New\s*Co(?:mpany)?|HoldCo|MergerSub|Merger\s+Sub|Purchaser\s+Sub)\b', re.IGNORECASE
)
_EARN_OUT_VALUE_RE = re.compile(
    r'earn[\s-]?out.*?\$([\d,.]+\s*(?:million|M|billion|B)?)',
    re.IGNORECASE,
)
_ESCROW_VALUE_RE = re.compile(
    r'escrow.*?\$([\d,.]+\s*(?:million|M|billion|B)?)',
    re.IGNORECASE,
)


def simulate_post_acquisition_structure(doc_id: int) -> dict:
    """
    Structural Neuroplasticity: spawn ghost nodes for the post-acquisition entity.

    Triggered when an SPA/merger agreement is uploaded. Creates:
    - NewCo / MergedEntity ghost node (the combined entity post-close)
    - Escrow Account node (holdback amounts)
    - Working Capital Peg node (NWC target/adjustment mechanism)
    - Earn-Out Obligation node (contingent consideration)

    Ghost nodes are tagged with properties.is_ghost=true and rendered
    as dashed circles in the D3 graph. Agents drop pheromones on both
    current-state and ghost-state nodes to surface structural mismatches.
    """
    conn = get_db()
    chunks = conn.execute(
        "SELECT id, text FROM ma_chunks WHERE doc_id=? ORDER BY page, id LIMIT 120",
        (doc_id,),
    ).fetchall()

    if not chunks:
        conn.close()
        return {"error": "No chunks found", "doc_id": doc_id}

    # Check if this looks like an SPA
    spa_signals = sum(1 for c in chunks if _SPA_GHOST_TRIGGERS.search(c["text"]))
    if spa_signals < 2:
        conn.close()
        return {"doc_id": doc_id, "ghost_nodes_created": 0, "reason": "Not an SPA/merger agreement"}

    full_text = " ".join(c["text"] for c in chunks)
    chunk_ids = [c["id"] for c in chunks[:10]]  # anchor to first chunks
    ghost_nodes_created = 0
    ghost_registry: list[dict] = []

    def _create_ghost(name: str, etype: str, props: dict) -> str:
        nid = _node_id(f"GHOST:{name}", etype)
        props_full = {"is_ghost": True, "simulation": "post_acquisition", "doc_id": doc_id, **props}
        existing = conn.execute("SELECT id FROM ma_kg_nodes WHERE id=?", (nid,)).fetchone()
        if not existing:
            conn.execute(
                """INSERT OR IGNORE INTO ma_kg_nodes
                   (id, name, entity_type, mention_count, doc_ids, chunk_ids,
                    first_seen, last_seen, confidence, pheromone_intensity, properties)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    nid, f"[GHOST] {name}", etype, 1,
                    json.dumps([doc_id]),
                    json.dumps(chunk_ids[:3]),
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    0.6, 0.15,  # ghost nodes start with mild heat
                    json.dumps(props_full),
                ),
            )
            return nid
        return nid

    # 1. NewCo / MergedEntity — the combined post-acquisition company
    newco_match = _NEWCO_RE.search(full_text)
    newco_name = newco_match.group(1) if newco_match else "MergedEntity"
    # Try to find the acquirer name — prefer Company KG nodes first,
    # then regex fallback with strict filtering.
    _COMMON_WORDS = frozenset({
        'no', 'the', 'it', 'a', 'an', 'in', 'on', 'at', 'by', 'to', 'is',
        'as', 'or', 'if', 'of', 'be', 'so', 'we', 'he', 'she', 'its', 'any',
        'new', 'not', 'all', 'and', 'for', 'are', 'was', 'has', 'had', 'our',
    })
    # Prefer: use the top Company node already in the KG for this doc
    top_company_row = conn.execute(
        """SELECT name FROM ma_kg_nodes
           WHERE entity_type='Company' AND doc_ids LIKE ? AND name NOT LIKE '%GHOST%'
           AND merged_into IS NULL ORDER BY mention_count DESC LIMIT 1""",
        (f"%{doc_id}%",),
    ).fetchone()
    if top_company_row:
        newco_name = f"{top_company_row['name']} + Target (Post-Close)"
    else:
        acquirer_match = re.search(
            r'([A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,}){0,3})'
            r'\s*[,\s]+(?:as\s+)?(?:Parent|Purchaser|Acquirer|Buyer)',
            full_text,
        )
        if acquirer_match:
            candidate = acquirer_match.group(1).strip()
            # Block common English words masquerading as company names
            if candidate.lower() not in _COMMON_WORDS and len(candidate) >= 4:
                newco_name = f"{candidate} + Target (Post-Close)"

    nid = _create_ghost(newco_name, "Company", {
        "ghost_type": "merged_entity",
        "description": "Simulated post-acquisition combined entity",
    })
    ghost_registry.append({"id": nid, "name": f"[GHOST] {newco_name}", "type": "merged_entity"})
    ghost_nodes_created += 1

    # 2. Escrow Account
    escrow_val = _ESCROW_VALUE_RE.search(full_text)
    escrow_amount = escrow_val.group(1) if escrow_val else "TBD"
    nid = _create_ghost(f"Escrow Account ({escrow_amount})", "FinancialMetric", {
        "ghost_type": "escrow_account",
        "amount": escrow_amount,
        "description": "Holdback escrow for indemnification / price adjustment",
    })
    ghost_registry.append({"id": nid, "name": f"[GHOST] Escrow Account ({escrow_amount})", "type": "escrow_account"})
    ghost_nodes_created += 1

    # 3. Working Capital Peg
    nwc_match = re.search(
        r'working\s+capital\s+(?:peg|target|amount)\s+of\s+\$?([\d,.]+)',
        full_text, re.IGNORECASE,
    )
    nwc_val = nwc_match.group(1) if nwc_match else "TBD"
    nid = _create_ghost(f"Working Capital Peg (${nwc_val})", "FinancialMetric", {
        "ghost_type": "nwc_peg",
        "peg_value": nwc_val,
        "description": "NWC target at closing — delta triggers price adjustment",
    })
    ghost_registry.append({"id": nid, "name": f"[GHOST] Working Capital Peg (${nwc_val})", "type": "nwc_peg"})
    ghost_nodes_created += 1

    # 4. Earn-Out (if present)
    earnout_val = _EARN_OUT_VALUE_RE.search(full_text)
    if earnout_val:
        earnout_amount = earnout_val.group(1)
        nid = _create_ghost(f"Earn-Out Obligation (${earnout_amount})", "FinancialMetric", {
            "ghost_type": "earn_out",
            "amount": earnout_amount,
            "description": "Contingent post-close consideration tied to performance",
        })
        ghost_registry.append({"id": nid, "name": f"[GHOST] Earn-Out (${earnout_amount})", "type": "earn_out"})
        ghost_nodes_created += 1

    # 5. EvidenceGap ghost: Post-Close Integration Plan (almost never in SPA)
    nid = _create_ghost("Post-Close Integration Plan", "EvidenceGap", {
        "ghost_type": "integration_gap",
        "description": "Integration roadmap not present in transaction documents",
    })
    ghost_registry.append({"id": nid, "name": "[GHOST] Post-Close Integration Plan", "type": "integration_gap"})
    ghost_nodes_created += 1

    # Link ghost nodes to the real Company node (highest-mention company in this doc)
    top_company = conn.execute(
        """SELECT id FROM ma_kg_nodes
           WHERE entity_type='Company' AND doc_ids LIKE ? AND merged_into IS NULL
           ORDER BY mention_count DESC LIMIT 1""",
        (f"%{doc_id}%",),
    ).fetchone()
    if top_company:
        now_ts = datetime.now(timezone.utc).isoformat()
        for ghost in ghost_registry:
            src_id = top_company["id"]
            tgt_id = ghost["id"]
            etype = "post_acquisition_structure"
            eid = _edge_id(src_id, tgt_id, etype)
            existing_edge = conn.execute(
                "SELECT id, doc_ids FROM ma_kg_edges WHERE id=?", (eid,)
            ).fetchone()
            if existing_edge:
                old_docs = json.loads(existing_edge["doc_ids"] or "[]")
                conn.execute(
                    "UPDATE ma_kg_edges SET weight=weight+0.7, doc_ids=?, updated_at=? WHERE id=?",
                    (json.dumps(sorted(set(old_docs + [doc_id]))), now_ts, eid),
                )
            else:
                conn.execute(
                    """INSERT INTO ma_kg_edges
                       (id, src_node_id, tgt_node_id, edge_type, weight, severity,
                        doc_ids, sentence_excerpt, valid_from_year, valid_until_year, ownership_pct)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (eid, src_id, tgt_id, etype, 0.7, "medium",
                     json.dumps([doc_id]),
                     "Simulated post-acquisition entity spawned from SPA analysis",
                     None, None, None),
                )

    conn.commit()
    conn.close()

    return {
        "doc_id": doc_id,
        "ghost_nodes_created": ghost_nodes_created,
        "ghost_registry": ghost_registry,
        "spa_signal_count": spa_signals,
        "summary": f"Spawned {ghost_nodes_created} ghost nodes representing post-acquisition structure",
    }


# ─── Role-Anchor Entity Extraction ──────────────────────────────────────────
# Solves the "1 Person" problem: instead of generic NER, find functional
# M&A roles first (the anchor), then extract the person/entity attached.
# If a role is present but empty → automatic EvidenceGap node.

_ROLE_ANCHORS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, role_label, entity_type)
    (re.compile(r'(?:the\s+)?(?:Target\s+)?CEO|Chief\s+Executive\s+Officer', re.I), "CEO", "Person"),
    (re.compile(r'(?:the\s+)?(?:Target\s+)?CFO|Chief\s+Financial\s+Officer', re.I), "CFO", "Person"),
    (re.compile(r'(?:the\s+)?(?:Target\s+)?CTO|Chief\s+Technology\s+Officer', re.I), "CTO", "Person"),
    (re.compile(r'(?:the\s+)?Founder(?:s)?', re.I), "Founder", "Person"),
    (re.compile(r'(?:the\s+)?(?:Lead\s+)?Investor', re.I), "Lead Investor", "Company"),
    (re.compile(r'(?:the\s+)?Guarantor', re.I), "Guarantor", "Person"),
    (re.compile(r'(?:the\s+)?Signator(?:y|ies)', re.I), "Signatory", "Person"),
    (re.compile(r'(?:the\s+)?Indemnifying\s+Party', re.I), "Indemnifying Party", "Person"),
    (re.compile(r'(?:the\s+)?Indemnified\s+Party', re.I), "Indemnified Party", "Person"),
    (re.compile(r'(?:the\s+)?Key\s+(?:Man|Person|Employee)', re.I), "Key Person", "Person"),
    (re.compile(r'(?:the\s+)?(?:Target\s+)?(?:Company\s+)?(?:General\s+)?Counsel', re.I), "General Counsel", "Person"),
    (re.compile(r'(?:the\s+)?Board\s+(?:of\s+Directors?|Chair(?:man)?)', re.I), "Board Chair", "Person"),
    (re.compile(r'(?:the\s+)?(?:Lead\s+)?Underwriter', re.I), "Lead Underwriter", "Company"),
    (re.compile(r'(?:the\s+)?(?:Financial\s+)?Advisor', re.I), "Financial Advisor", "Company"),
    (re.compile(r'(?:the\s+)?(?:Legal\s+)?Counsel\s+(?:for|to)', re.I), "Legal Counsel", "Company"),
    (re.compile(r'(?:the\s+)?Escrow\s+Agent', re.I), "Escrow Agent", "Company"),
    (re.compile(r'(?:the\s+)?(?:Independent\s+)?Auditor|(?:the\s+)?Accounting\s+Firm', re.I), "Auditor", "Company"),
]

# Pattern to find "Name, Role" — requires FULL role title so "Officer" alone doesn't
# split "Chief Executive" as the name. Ordered longest→shortest to prevent partial match.
_ROLE_BINDING_RE = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})'   # Capitalized name (1-4 words)
    r'\s*,\s*(?:the\s+)?'                        # comma separator
    r'(Chief\s+Executive\s+Officer|Chief\s+Financial\s+Officer|'
    r'Chief\s+Technology\s+Officer|Chief\s+Operating\s+Officer|'
    r'CEO|CFO|CTO|COO|Founder|Co-Founder|'
    r'Guarantor|Signatory|President|Director|Chairman)',
    re.IGNORECASE,
)
# Pattern: "Role, [Name]" or "Role: [Name]" in signature blocks / recitals
_SIGNATURE_RE = re.compile(
    r'(CEO|CFO|CTO|President|Chairman|Director|Founder|Guarantor)\s*[:\-,]\s*'
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    re.IGNORECASE,
)


def extract_role_anchors(doc_id: int) -> dict:
    """
    Role-Anchor extraction: find M&A functional roles and the people/entities attached.

    Strategy:
    1. Scan all chunks for role keywords (CEO, Founder, Guarantor…)
    2. For each role, extract the name attached via binding patterns
    3. Create/update Person/Company nodes with role properties
    4. Where role found but no name → create EvidenceGap node ("Missing CEO identity")

    Returns summary of roles found, persons extracted, gaps created.
    """
    conn = get_db()
    chunks = conn.execute(
        "SELECT id, text, page FROM ma_chunks WHERE doc_id=? ORDER BY page, id",
        (doc_id,),
    ).fetchall()

    if not chunks:
        conn.close()
        return {"error": "No chunks found", "doc_id": doc_id}

    found_roles: dict[str, str] = {}   # role_label → person/company name
    role_chunk_ids: dict[str, list[int]] = {}  # role_label → chunk_ids

    for chunk in chunks:
        text = chunk["text"]
        cid = chunk["id"]

        # Try signature patterns first (most reliable)
        for m in _SIGNATURE_RE.finditer(text):
            role = m.group(1).strip()
            name = m.group(2).strip()
            if len(name) >= 4 and role not in found_roles:
                found_roles[role] = name
                role_chunk_ids.setdefault(role, []).append(cid)

        # Try binding patterns ("Jane Smith, CEO")
        for m in _ROLE_BINDING_RE.finditer(text):
            name = m.group(1).strip()
            role = m.group(2).strip()
            if len(name) >= 4 and role not in found_roles:
                found_roles[role] = name
                role_chunk_ids.setdefault(role, []).append(cid)

        # Track which roles appear in this chunk (for gap detection)
        for pattern, role_label, _ in _ROLE_ANCHORS:
            if pattern.search(text):
                role_chunk_ids.setdefault(role_label, []).append(cid)

    persons_created = 0
    gaps_created = 0
    results = []

    # Determine which roles appear in doc but have no resolved name
    all_doc_text = " ".join(c["text"] for c in chunks)
    for pattern, role_label, etype in _ROLE_ANCHORS:
        if not pattern.search(all_doc_text):
            continue  # Role not mentioned in this doc at all

        if role_label in found_roles:
            real_name = found_roles[role_label]
            # Create/update Person node with role
            nid = _node_id(real_name, etype)
            existing = conn.execute(
                "SELECT id, mention_count, properties FROM ma_kg_nodes WHERE id=?", (nid,)
            ).fetchone()
            cids = json.dumps(list(set(role_chunk_ids.get(role_label, []))))
            if existing:
                # Enrich properties with role
                props = {}
                try:
                    props = json.loads(existing["properties"] or "{}")
                except Exception:
                    pass
                props["role"] = role_label
                props["role_in_doc"] = doc_id
                conn.execute(
                    "UPDATE ma_kg_nodes SET properties=?, mention_count=mention_count+1 WHERE id=?",
                    (json.dumps(props), nid),
                )
            else:
                props = {"role": role_label, "role_in_doc": doc_id}
                conn.execute(
                    """INSERT OR IGNORE INTO ma_kg_nodes
                       (id, name, entity_type, mention_count, doc_ids, chunk_ids,
                        first_seen, last_seen, confidence, pheromone_intensity, properties)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        nid, real_name, etype, 1,
                        json.dumps([doc_id]), cids,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                        0.85, 0.0, json.dumps(props),
                    ),
                )
                persons_created += 1
            results.append({"role": role_label, "resolved_to": real_name, "type": etype, "status": "found"})
        else:
            # Role mentioned but no name found → EvidenceGap
            gap_name = f"Missing {role_label} identity"
            gap_id = _node_id(gap_name, "EvidenceGap")
            existing_gap = conn.execute(
                "SELECT id FROM ma_kg_nodes WHERE id=?", (gap_id,)
            ).fetchone()
            if not existing_gap:
                conn.execute(
                    """INSERT OR IGNORE INTO ma_kg_nodes
                       (id, name, entity_type, mention_count, doc_ids, chunk_ids,
                        first_seen, last_seen, confidence, pheromone_intensity, properties)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        gap_id, gap_name, "EvidenceGap", 1,
                        json.dumps([doc_id]),
                        json.dumps(role_chunk_ids.get(role_label, [])),
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                        0.5, 0.3,  # EvidenceGaps start with mild pheromone heat
                        json.dumps({"gap_type": "missing_role", "role": role_label}),
                    ),
                )
                gaps_created += 1

                # Connect EvidenceGap to the top Company node in this doc
                # (gap_about edge) so it's reachable in the graph — prevents orphan
                top_co = conn.execute(
                    """SELECT id FROM ma_kg_nodes
                       WHERE entity_type='Company' AND doc_ids LIKE ? AND merged_into IS NULL
                       AND name NOT LIKE '%GHOST%' ORDER BY mention_count DESC LIMIT 1""",
                    (f"%{doc_id}%",),
                ).fetchone()
                if top_co and top_co["id"] != gap_id:
                    eid = _edge_id(gap_id, top_co["id"], "gap_about")
                    existing_eid = conn.execute("SELECT id FROM ma_kg_edges WHERE id=?", (eid,)).fetchone()
                    if not existing_eid:
                        conn.execute(
                            """INSERT INTO ma_kg_edges
                               (id, src_node_id, tgt_node_id, edge_type, weight, severity,
                                doc_ids, sentence_excerpt, valid_from_year, valid_until_year, ownership_pct)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            (eid, gap_id, top_co["id"], "gap_about", 0.6, "high",
                             json.dumps([doc_id]), f"Missing {role_label} identity",
                             None, None, None),
                        )

            results.append({"role": role_label, "resolved_to": None, "type": "EvidenceGap", "status": "gap"})

    conn.commit()
    conn.close()

    return {
        "doc_id": doc_id,
        "roles_found": len([r for r in results if r["status"] == "found"]),
        "gaps_created": gaps_created,
        "persons_created": persons_created,
        "role_anchors": results,
    }


# ─── Fractal Myelination — Simplified Signal Propagation ────────────────────
# When any node's pheromone_intensity changes (e.g. after adversarial pollination
# or jury run), shock all connected nodes with a fraction of that signal.
# Myelinated pathways (high-weight edges) propagate faster/stronger.

def propagate_myelinated_signals(doc_id: int | None = None, min_intensity: float = 0.1) -> dict:
    """
    Simplified fractal myelination: propagate signals through the KG graph.

    For each hot node (pheromone_intensity > min_intensity):
    - Follow all edges from that node
    - Deposit fraction of signal to neighbors (scaled by edge weight)
    - High-weight (myelinated) edges carry stronger signal
    - Caps at 1.0, decays with each hop

    This is "myelination" — frequently-traversed, high-weight paths carry
    signals faster. A definition change shocks every connected clause node.
    """
    conn = get_db()

    # Find hot nodes to propagate from
    if doc_id:
        hot_nodes = conn.execute(
            """SELECT id, name, entity_type, pheromone_intensity
               FROM ma_kg_nodes
               WHERE pheromone_intensity >= ? AND doc_ids LIKE ?
               ORDER BY pheromone_intensity DESC LIMIT 50""",
            (min_intensity, f"%{doc_id}%"),
        ).fetchall()
    else:
        hot_nodes = conn.execute(
            """SELECT id, name, entity_type, pheromone_intensity
               FROM ma_kg_nodes
               WHERE pheromone_intensity >= ?
               ORDER BY pheromone_intensity DESC LIMIT 50""",
            (min_intensity,),
        ).fetchall()

    if not hot_nodes:
        conn.close()
        return {"nodes_propagated": 0, "signals_deposited": 0}

    DECAY = 0.4       # Signal fraction passed to neighbors
    MYELINATION_BOOST = 1.6  # High-weight edges amplify signal
    WEIGHT_THRESHOLD = 0.8   # Edge weight above this = "myelinated"

    nodes_propagated = 0
    signals_deposited = 0
    updated: set[str] = set()

    for node in hot_nodes:
        nid = node["id"]
        source_intensity = node["pheromone_intensity"] or 0.0

        # Get all edges from this node
        edges = conn.execute(
            """SELECT tgt_node_id, src_node_id, edge_type, weight
               FROM ma_kg_edges
               WHERE src_node_id=? OR tgt_node_id=?""",
            (nid, nid),
        ).fetchall()

        for edge in edges:
            neighbor_id = edge["tgt_node_id"] if edge["src_node_id"] == nid else edge["src_node_id"]
            if neighbor_id in updated:
                continue  # Don't double-update in same tick

            weight = edge["weight"] or 0.5
            is_myelinated = weight >= WEIGHT_THRESHOLD
            propagated = source_intensity * DECAY * (MYELINATION_BOOST if is_myelinated else 1.0)

            if propagated < 0.02:
                continue  # Too weak to propagate

            # Update neighbor intensity
            neighbor = conn.execute(
                "SELECT pheromone_intensity FROM ma_kg_nodes WHERE id=?", (neighbor_id,)
            ).fetchone()
            if neighbor:
                current = neighbor["pheromone_intensity"] or 0.0
                new_val = min(1.0, current + propagated)
                conn.execute(
                    "UPDATE ma_kg_nodes SET pheromone_intensity=? WHERE id=?",
                    (new_val, neighbor_id),
                )
                updated.add(neighbor_id)
                signals_deposited += 1

        nodes_propagated += 1

    conn.commit()
    conn.close()

    return {
        "nodes_propagated": nodes_propagated,
        "signals_deposited": signals_deposited,
        "hot_nodes_count": len(hot_nodes),
    }

def _impact_summary(gaps: list, contradictions: list, candidates: list) -> str:
    """One-line human-readable summary of upload impact."""
    parts = []
    if gaps:
        parts.append(f"resolves {len(gaps)} evidence gap{'s' if len(gaps)>1 else ''}")
    if contradictions:
        sev = sum(1 for c in contradictions if c["severity"] == "high")
        parts.append(f"introduces {len(contradictions)} contradiction{'s' if len(contradictions)>1 else ''}"
                     + (f" ({sev} high severity)" if sev else ""))
    if candidates:
        parts.append(f"{len(candidates)} supersession candidate{'s' if len(candidates)>1 else ''} for Jury review")
    if not parts:
        return "No significant impact on existing deal analysis."
    return "This upload " + "; ".join(parts) + "."


# ─── Rebuild helpers ─────────────────────────────────────────────────────────

def _drop_kg_for_doc(doc_id: int) -> None:
    """
    Remove all KG nodes/edges that belong exclusively to doc_id,
    and strip doc_id from nodes shared with other documents.
    """
    conn = get_db()
    try:
        # Find all nodes that include doc_id in their doc_ids JSON array
        all_nodes = conn.execute(
            "SELECT id, doc_ids FROM ma_kg_nodes WHERE doc_ids LIKE ?",
            (f"%{doc_id}%",),
        ).fetchall()

        nodes_only_this_doc: list[str] = []
        for row in all_nodes:
            try:
                doc_list = json.loads(row["doc_ids"] or "[]")
            except Exception:
                doc_list = []
            if doc_id not in doc_list:
                continue
            if len(doc_list) == 1:
                nodes_only_this_doc.append(row["id"])
            else:
                # Remove this doc from the array, keep node
                new_list = [d for d in doc_list if d != doc_id]
                conn.execute(
                    "UPDATE ma_kg_nodes SET doc_ids=? WHERE id=?",
                    (json.dumps(new_list), row["id"]),
                )

        # Delete edges where BOTH endpoints are exclusive to this doc
        if nodes_only_this_doc:
            placeholders = ",".join("?" * len(nodes_only_this_doc))
            conn.execute(
                f"DELETE FROM ma_kg_edges WHERE src_node_id IN ({placeholders})"
                f" OR tgt_node_id IN ({placeholders})",
                nodes_only_this_doc * 2,
            )
            conn.execute(
                f"DELETE FROM ma_kg_nodes WHERE id IN ({placeholders})",
                nodes_only_this_doc,
            )
        else:
            # Still need to clean up edges that reference this doc exclusively
            # Get all node ids referencing this doc (shared nodes included)
            all_node_ids_for_doc = [row["id"] for row in all_nodes
                                    if doc_id in json.loads(row["doc_ids"] or "[]")]
            if all_node_ids_for_doc:
                placeholders = ",".join("?" * len(all_node_ids_for_doc))
                # Remove doc from edge doc_ids; delete edges that only had this doc
                edges = conn.execute(
                    f"SELECT id, doc_ids FROM ma_kg_edges WHERE src_node_id IN ({placeholders})"
                    f" OR tgt_node_id IN ({placeholders})",
                    all_node_ids_for_doc * 2,
                ).fetchall()
                for edge in edges:
                    try:
                        edoc_list = json.loads(edge["doc_ids"] or "[]")
                    except Exception:
                        edoc_list = []
                    if doc_id in edoc_list:
                        new_edocs = [d for d in edoc_list if d != doc_id]
                        if not new_edocs:
                            conn.execute("DELETE FROM ma_kg_edges WHERE id=?", (edge["id"],))
                        else:
                            conn.execute(
                                "UPDATE ma_kg_edges SET doc_ids=? WHERE id=?",
                                (json.dumps(new_edocs), edge["id"]),
                            )

        # Clean doc similarity rows for this doc
        conn.execute(
            "DELETE FROM ma_kg_doc_similarity WHERE doc_id_a=? OR doc_id_b=?",
            (doc_id, doc_id),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Upgrade 1: Liar's Drift — Relational Versioning ────────────────────────

# Document type hierarchy: later in this list = more authoritative / later in deal
_DOC_TYPE_ORDER = [
    "teaser", "cim", "information_memorandum", "loi", "term_sheet",
    "due_diligence", "disclosure_letter", "spa", "share_purchase_agreement",
    "closing_statement", "amendment",
]

def _doc_type_rank(doc_type: str | None) -> int:
    if not doc_type:
        return -1
    dt = doc_type.lower().replace(" ", "_").replace("-", "_")
    for i, t in enumerate(_DOC_TYPE_ORDER):
        if t in dt:
            return i
    return -1


def stamp_supersession_edges(doc_id: int, doc_type: str | None = None) -> dict:
    """Compare newly ingested document against all earlier docs.

    For every FinancialMetric or Claim node that shares a canonical_name with
    an existing node from an earlier document type:
      - Draw a red ``UPDATES`` edge (new → old) if the value changed
      - Draw a ``CONTRADICTS`` edge if the sentiment flipped (positive→negative)
      - Flip ``is_latest=0`` on the old node
      - Increment ``drift_generation`` on the new node

    Returns a summary of edges stamped.
    """
    conn = get_db()
    new_rank = _doc_type_rank(doc_type)

    # Load nodes from this doc
    new_nodes = conn.execute(
        """SELECT id, name, canonical_name, entity_type, properties
           FROM ma_kg_nodes
           WHERE json_extract(doc_ids, '$[0]') IS NOT NULL
             AND (doc_ids LIKE ? OR doc_ids LIKE ?)
             AND entity_type IN ('FinancialMetric','Claim','Risk','Contract')
             AND is_latest = 1""",
        (f'[{doc_id}%', f'%,{doc_id}%'),
    ).fetchall()

    updates_stamped = 0
    contradicts_stamped = 0
    nodes_flipped = 0

    for new_node in new_nodes:
        # Find older nodes with the same canonical name from different (earlier) docs
        canon = new_node["canonical_name"] or new_node["name"]
        older = conn.execute(
            """SELECT id, name, properties, doc_ids, doc_type
               FROM ma_kg_nodes
               WHERE canonical_name = ? AND id != ?
                 AND is_latest = 1
                 AND entity_type = ?
                 AND merged_into IS NULL""",
            (canon, new_node["id"], new_node["entity_type"]),
        ).fetchall()

        for old_node in older:
            old_rank = _doc_type_rank(old_node["doc_type"])
            # Only stamp if new doc is more authoritative
            if new_rank >= 0 and old_rank >= 0 and new_rank <= old_rank:
                continue

            try:
                new_props = json.loads(new_node["properties"] or "{}")
                old_props = json.loads(old_node["properties"] or "{}")
            except Exception:
                new_props, old_props = {}, {}

            # Detect value change for FinancialMetric nodes
            new_val = new_props.get("value") or new_props.get("amount")
            old_val = old_props.get("value") or old_props.get("amount")
            value_changed = new_val is not None and old_val is not None and str(new_val) != str(old_val)

            # Detect sentiment flip (positive claim → negative / contradicted)
            new_sent = new_props.get("sentiment", "")
            old_sent = old_props.get("sentiment", "")
            sentiment_flipped = (
                new_sent and old_sent and new_sent != old_sent and
                {new_sent, old_sent} <= {"positive", "negative"}
            )

            edge_type = "CONTRADICTS" if sentiment_flipped else "UPDATES"
            excerpt = (
                f"Drift: '{canon}' changed from doc_type={old_node['doc_type'] or 'unknown'} "
                f"to doc_type={doc_type or 'unknown'}"
                + (f" | value: {old_val} → {new_val}" if value_changed else "")
            )

            edge_id = hashlib.md5(
                f"drift:{new_node['id']}:{old_node['id']}:{edge_type}".encode()
            ).hexdigest()[:16]

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO ma_kg_edges
                       (id, src_node_id, tgt_node_id, edge_type, weight, severity,
                        doc_ids, sentence_excerpt, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (edge_id, new_node["id"], old_node["id"], edge_type,
                     0.95, "high", json.dumps([doc_id]), excerpt[:400]),
                )
                updates_stamped += (1 if edge_type == "UPDATES" else 0)
                contradicts_stamped += (1 if edge_type == "CONTRADICTS" else 0)
            except Exception:
                pass

            # Flip old node's is_latest flag and record supersession
            conn.execute(
                """UPDATE ma_kg_nodes
                   SET is_latest=0,
                       superseded_by=?,
                       superseded_at=datetime('now'),
                       supersession_reason=?
                   WHERE id=?""",
                (new_node["id"], f"Overridden by {doc_type or 'newer doc'}", old_node["id"]),
            )
            nodes_flipped += 1

            # Bump drift_generation on the new node
            conn.execute(
                "UPDATE ma_kg_nodes SET drift_generation = drift_generation + 1 WHERE id=?",
                (new_node["id"],),
            )

    conn.commit()
    conn.close()
    return {
        "updates_edges": updates_stamped,
        "contradicts_edges": contradicts_stamped,
        "nodes_flipped_to_superseded": nodes_flipped,
    }


def get_drift_timeline(entity_canonical_name: str) -> list[dict]:
    """Return the full mutation history of a claim/metric across all documents.

    Each entry is a node version ordered by drift_generation ascending,
    with UPDATES/CONTRADICTS edges linking them.
    Returns a list ready for frontend timeline rendering.
    """
    conn = get_db()
    nodes = conn.execute(
        """SELECT n.id, n.name, n.entity_type, n.doc_type, n.drift_generation,
                  n.is_latest, n.properties, n.first_seen, n.superseded_at,
                  n.supersession_reason
           FROM ma_kg_nodes n
           WHERE (n.canonical_name = ? OR n.name = ?)
             AND n.merged_into IS NULL
           ORDER BY n.drift_generation ASC""",
        (entity_canonical_name, entity_canonical_name),
    ).fetchall()

    timeline = []
    for n in nodes:
        edges_out = conn.execute(
            """SELECT edge_type, tgt_node_id, sentence_excerpt
               FROM ma_kg_edges
               WHERE src_node_id = ?
                 AND edge_type IN ('UPDATES','CONTRADICTS')""",
            (n["id"],),
        ).fetchall()
        timeline.append({
            "node_id": n["id"],
            "name": n["name"],
            "entity_type": n["entity_type"],
            "doc_type": n["doc_type"],
            "drift_generation": n["drift_generation"],
            "is_latest": bool(n["is_latest"]),
            "properties": json.loads(n["properties"] or "{}"),
            "first_seen": n["first_seen"],
            "superseded_at": n["superseded_at"],
            "supersession_reason": n["supersession_reason"],
            "drift_edges": [
                {"edge_type": e["edge_type"], "to": e["tgt_node_id"],
                 "excerpt": e["sentence_excerpt"]}
                for e in edges_out
            ],
        })
    conn.close()
    return timeline


# ─── Upgrade 3: Hybrid Recall — Subgraph Triple Injection ───────────────────

def build_subgraph_triples(entity_names: list[str], limit: int = 20) -> str:
    """Build a compact triple string for the named entities.

    Extracts the top ``limit`` edges touching any of the given entity names
    and formats them as human-readable (Subject, predicate, Object) triples.
    This structured context is prepended to LLM prompts so the 3B model
    gets a reasoning shortcut rather than raw messy chunk text.

    Example output::

        [KG Context]
        Acme Corp --[party_to]--> Share Purchase Agreement (weight: 0.95)
        Revenue €42M --[UPDATES]--> Revenue €38M [SUPERSEDED] (drift: CIM→SPA)
        John Smith --[signatory_of]--> Share Purchase Agreement (weight: 0.90)

    Returns an empty string if no relevant nodes are found (safe to prepend).
    """
    if not entity_names:
        return ""

    conn = get_db()
    placeholders = ",".join("?" * len(entity_names))

    # Resolve entity names to node IDs (fuzzy: LIKE match on name/canonical_name)
    like_clauses = " OR ".join(
        f"(LOWER(name) LIKE ? OR LOWER(canonical_name) LIKE ?)"
        for _ in entity_names
    )
    params = []
    for name in entity_names:
        slug = f"%{name.lower()}%"
        params += [slug, slug]

    nodes = conn.execute(
        f"SELECT id, name, entity_type, is_latest FROM ma_kg_nodes WHERE {like_clauses} AND merged_into IS NULL LIMIT 30",
        params,
    ).fetchall()

    if not nodes:
        conn.close()
        return ""

    node_ids = {n["id"]: n for n in nodes}
    id_list = list(node_ids.keys())
    id_placeholders = ",".join("?" * len(id_list))

    edges = conn.execute(
        f"""SELECT e.src_node_id, e.tgt_node_id, e.edge_type, e.weight,
                   e.sentence_excerpt, e.severity,
                   ns.name AS src_name, ns.is_latest AS src_latest,
                   nt.name AS tgt_name, nt.is_latest AS tgt_latest
            FROM ma_kg_edges e
            JOIN ma_kg_nodes ns ON ns.id = e.src_node_id
            JOIN ma_kg_nodes nt ON nt.id = e.tgt_node_id
            WHERE (e.src_node_id IN ({id_placeholders})
                OR e.tgt_node_id IN ({id_placeholders}))
            ORDER BY e.weight DESC
            LIMIT ?""",
        id_list + id_list + [limit],
    ).fetchall()

    conn.close()

    if not edges:
        return ""

    lines = ["[KG Context — structured reasoning shortcuts for this document]"]
    for e in edges:
        src_label = e["src_name"] + ("" if e["src_latest"] else " [SUPERSEDED]")
        tgt_label = e["tgt_name"] + ("" if e["tgt_latest"] else " [SUPERSEDED]")
        drift_note = " (Liar's Drift)" if e["edge_type"] in ("UPDATES", "CONTRADICTS") else ""
        lines.append(
            f"  {src_label} --[{e['edge_type']}]--> {tgt_label}"
            f" (weight: {e['weight']:.2f}, severity: {e['severity']})"
            f"{drift_note}"
        )
    return "\n".join(lines)


def rebuild_all_kg(drop_existing: bool = True) -> dict:
    """
    Rebuild the knowledge graph for every document in ma_documents.

    When drop_existing=True (default) each document's prior nodes/edges are
    removed before the graph is re-extracted, ensuring old co_mentioned edges
    are replaced by the current typed-edge map.

    Returns a summary dict with doc counts, node/edge totals and a breakdown
    of typed vs co_mentioned edges.
    """
    init_kg_tables()
    conn = get_db()
    doc_ids = [r["id"] for r in conn.execute("SELECT id FROM ma_documents").fetchall()]
    conn.close()

    results: dict = {"docs_rebuilt": 0, "errors": []}

    for doc_id in doc_ids:
        try:
            if drop_existing:
                _drop_kg_for_doc(doc_id)
            update_graph_for_doc(doc_id)
            results["docs_rebuilt"] += 1
        except Exception as exc:
            results["errors"].append({"doc_id": doc_id, "error": str(exc)})

    # Summarise final state
    conn = get_db()
    results["total_nodes"] = conn.execute(
        "SELECT COUNT(*) FROM ma_kg_nodes WHERE merged_into IS NULL"
    ).fetchone()[0]
    results["total_edges"] = conn.execute(
        "SELECT COUNT(*) FROM ma_kg_edges"
    ).fetchone()[0]
    results["co_mentioned"] = conn.execute(
        "SELECT COUNT(*) FROM ma_kg_edges WHERE edge_type='co_mentioned'"
    ).fetchone()[0]
    results["typed_edges"] = results["total_edges"] - results["co_mentioned"]
    conn.close()
    return results


# ---------------------------------------------------------------------------
# DFS Cascade Tracer
# ---------------------------------------------------------------------------

_CASCADE_EDGE_TYPES = frozenset({
    "triggers_risk", "CONTRADICTS", "UPDATES", "has_risk",
    "party_to", "governs", "governed_by", "mae_trigger",
    "quantifies_risk", "gap_about", "signatory_of",
    "change_of_control", "post_acquisition_structure",
    "defines_value", "has_revenue", "subsidiary_of", "personal_service",
})
_CASCADE_PHEROMONE = "CHAIN_TRIGGER"


def trace_cascade(start_node_id: str, max_depth: int = 6) -> dict:
    """
    DFS chain-of-consequence tracer.

    Starting from *start_node_id*, follows high-severity / high-weight edges
    (edge_type in _CASCADE_EDGE_TYPES, weight >= 0.4) depth-first up to
    *max_depth* hops.  Deposits CHAIN_TRIGGER pheromones on every node in the
    cascade path and returns the full chain as an ordered list.

    Returns
    -------
    {
        "start": {id, name, type},
        "chain": [{"depth": int, "node": {id, name, type, pheromone},
                   "via_edge": str, "weight": float}],
        "nodes_visited": int,
        "pheromones_deposited": int,
    }
    """
    init_kg_tables()
    conn = get_db()

    def _get_node(nid: int) -> dict | None:
        r = conn.execute(
            "SELECT id, name, entity_type, pheromone_intensity FROM ma_kg_nodes WHERE id=? AND merged_into IS NULL",
            (nid,),
        ).fetchone()
        return dict(r) if r else None

    start = _get_node(start_node_id)
    if not start:
        conn.close()
        return {"error": f"Node {start_node_id} not found"}

    # Build adjacency once — only cascade-eligible edges, weight >= 0.4
    all_edges = conn.execute(
        """SELECT src_node_id, tgt_node_id, edge_type, weight
           FROM ma_kg_edges
           WHERE weight >= 0.4""",
    ).fetchall()

    adj: dict[int, list[tuple[int, str, float]]] = {}
    for e in all_edges:
        if e["edge_type"] not in _CASCADE_EDGE_TYPES:
            continue
        adj.setdefault(e["src_node_id"], []).append(
            (e["tgt_node_id"], e["edge_type"], e["weight"])
        )
        # Treat as undirected for cascade (risk propagates both ways)
        adj.setdefault(e["tgt_node_id"], []).append(
            (e["src_node_id"], e["edge_type"], e["weight"])
        )

    # DFS — iterative to avoid Python recursion limits
    chain: list[dict] = []
    visited: set[int] = {start_node_id}
    # Stack entries: (node_id, depth, via_edge, via_weight)
    stack: list[tuple[int, int, str, float]] = []
    for tgt, etype, wt in sorted(adj.get(start_node_id, []), key=lambda x: -x[2]):
        if tgt not in visited:
            stack.append((tgt, 1, etype, wt))

    while stack:
        nid, depth, via_edge, via_weight = stack.pop()
        if nid in visited or depth > max_depth:
            continue
        visited.add(nid)
        node = _get_node(nid)
        if not node:
            continue
        chain.append({
            "depth": depth,
            "node": {
                "id": node["id"],
                "name": node["name"],
                "type": node["entity_type"],
                "pheromone": round(node["pheromone_intensity"] or 0.0, 3),
            },
            "via_edge": via_edge,
            "weight": round(via_weight, 3),
        })
        # Push neighbours sorted by weight descending (DFS prefers high-weight paths)
        for tgt, etype, wt in sorted(adj.get(nid, []), key=lambda x: -x[2]):
            if tgt not in visited:
                stack.append((tgt, depth + 1, etype, wt))

    # Deposit CHAIN_TRIGGER pheromones on every visited node (excluding start)
    now = datetime.now(timezone.utc).isoformat()
    pheromones_deposited = 0
    for step in chain:
        nid = step["node"]["id"]
        # Intensity decays with depth — deeper nodes get weaker signal
        intensity = max(0.3, 1.0 - (step["depth"] - 1) * 0.12)
        current = conn.execute(
            "SELECT pheromone_intensity FROM ma_kg_nodes WHERE id=?", (nid,)
        ).fetchone()
        if current:
            new_val = min(1.0, (current["pheromone_intensity"] or 0.0) + intensity * 0.5)
            conn.execute(
                "UPDATE ma_kg_nodes SET pheromone_intensity=? WHERE id=?",
                (round(new_val, 4), nid),
            )
            pheromones_deposited += 1

    conn.commit()
    conn.close()

    return {
        "start": {
            "id": start["id"],
            "name": start["name"],
            "type": start["entity_type"],
        },
        "chain": chain,
        "nodes_visited": len(chain),
        "pheromones_deposited": pheromones_deposited,
    }
