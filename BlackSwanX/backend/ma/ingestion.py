"""Document ingestion pipeline — PDF, DOCX, XLSX, TXT → text chunks."""
import re
import io


CHUNK_SIZE = 600      # characters per chunk
CHUNK_OVERLAP = 80    # overlap between chunks


def extract_text(filename: str, file_bytes: bytes) -> list[dict]:
    """Extract text from uploaded file. Returns list of {text, page, source}."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    try:
        if ext == "pdf":
            return _extract_pdf(file_bytes)
        elif ext in ("docx", "doc"):
            return _extract_docx(file_bytes)
        elif ext in ("xlsx", "xls", "csv"):
            return _extract_excel(filename, file_bytes)
        else:
            # Plain text / unknown
            text = file_bytes.decode("utf-8", errors="replace")
            return [{"text": text, "page": 1, "source": "text"}]
    except Exception as e:
        return [{"text": f"[Extraction error: {e}]", "page": 1, "source": "error"}]


def _extract_pdf(file_bytes: bytes) -> list[dict]:
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            # Also grab tables as pipe-formatted text
            for table in (page.extract_tables() or []):
                rows = [" | ".join(str(c or "") for c in row) for row in table if row]
                text += "\n" + "\n".join(rows)
            if text.strip():
                pages.append({"text": text.strip(), "page": i, "source": "pdf"})
    return pages or [{"text": "(No text extracted from PDF)", "page": 1, "source": "pdf"}]


def _extract_docx(file_bytes: bytes) -> list[dict]:
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
            if row_text:
                paragraphs.append(row_text)
    full_text = "\n".join(paragraphs)
    return [{"text": full_text, "page": 1, "source": "docx"}]


def _extract_excel(filename: str, file_bytes: bytes) -> list[dict]:
    if filename.lower().endswith(".csv"):
        text = file_bytes.decode("utf-8", errors="replace")
        return [{"text": text, "page": 1, "source": "csv"}]
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    pages = []
    for sheet in wb.worksheets:
        rows = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            pages.append({"text": f"[Sheet: {sheet.title}]\n" + "\n".join(rows), "page": 1, "source": "xlsx"})
    return pages or [{"text": "(Empty spreadsheet)", "page": 1, "source": "xlsx"}]


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Split page texts into overlapping chunks for RAG."""
    chunks = []
    for page in pages:
        text = page["text"]
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": page["page"],
                    "source": page["source"],
                    "char_start": start,
                })
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Synaptic Pruning ─────────────────────────────────────────────────────────
# M&A documents are 500+ pages of boilerplate + ~30 pages of actual deal terms.
# Synaptic Pruning scores every chunk by M&A signal density, tags section types,
# and pushes high-priority chunks to the front so agents see what matters first.
#
# Biological analogy: the brain prunes weak synapses during development.
# We prune legal boilerplate so only high-weight "myelinated" fibers reach agents.

# Section type detection patterns (ordered by priority)
_SECTION_PATTERNS: list[tuple[str, str, int, re.Pattern]] = [
    # (section_type, label, base_priority, pattern)
    ("representations_warranties", "R&W",        95, re.compile(
        r'represent(?:ation)?s?\s+and\s+warrant(?:ies|y)|'
        r'reps?\s+(?:and\s+)?warr?ant|'
        r'section\s+\d+\s*[–—-]\s*represent',
        re.IGNORECASE)),
    ("mae_trigger",               "MAE",         93, re.compile(
        r'material\s+adverse\s+(?:effect|change|event)|'
        r'\bMAE\b|\bMAC\b|'
        r'material\s+adverse\s+condition',
        re.IGNORECASE)),
    ("indemnification",           "Indemnity",   90, re.compile(
        r'indemnif(?:y|ication|ied|ying)|'
        r'hold\s+harmless|'
        r'indemnity\s+(?:cap|basket|deductible|obligation)',
        re.IGNORECASE)),
    ("nwc_adjustment",            "NWC",         90, re.compile(
        r'net\s+working\s+capital|'
        r'working\s+capital\s+(?:peg|adjustment|target|mechanism)|'
        r'current\s+assets\s*[-–]\s*current\s+liabilities|'
        r'locked[\s-]box|completion\s+accounts',
        re.IGNORECASE)),
    ("conditions_closing",        "Closing Cond", 88, re.compile(
        r'condition(?:s)?\s+(?:to|of)\s+(?:the\s+)?closing|'
        r'conditions\s+precedent|'
        r'closing\s+condition|'
        r'shall\s+not\s+be\s+obligated\s+to\s+close',
        re.IGNORECASE)),
    ("termination",               "Termination", 87, re.compile(
        r'terminat(?:e|ion|ing)\s+(?:this\s+)?agreement|'
        r'right\s+to\s+terminat|'
        r'break[\s-]?up\s+fee|termination\s+fee|'
        r'reverse\s+(?:termination|break)',
        re.IGNORECASE)),
    ("purchase_price",            "Price",       85, re.compile(
        r'purchase\s+price|'
        r'merger\s+consideration|'
        r'aggregate\s+consideration|'
        r'per\s+share\s+(?:price|consideration|amount)',
        re.IGNORECASE)),
    ("earn_out",                  "Earn-Out",    85, re.compile(
        r'earn[\s-]?out|'
        r'contingent\s+consideration|'
        r'milestone\s+payment|'
        r'deferred\s+consideration',
        re.IGNORECASE)),
    ("change_of_control",         "CoC",         85, re.compile(
        r'change\s+of\s+control|'
        r'change-of-control|'
        r'consent\s+(?:to\s+)?(?:the\s+)?(?:merger|acquisition|transaction)',
        re.IGNORECASE)),
    ("non_compete",               "Non-Compete", 80, re.compile(
        r'non[\s-]compet(?:e|ition)|'
        r'restrictive\s+covenant|'
        r'non[\s-]solicit(?:ation)?|'
        r'garden\s+leave',
        re.IGNORECASE)),
    ("ip_ownership",              "IP",          80, re.compile(
        r'intellectual\s+property|'
        r'patent|trademark|copyright|'
        r'trade\s+secret|'
        r'ip\s+(?:ownership|license|assignment)',
        re.IGNORECASE)),
    ("definitions",               "Definitions", 70, re.compile(
        r'(?:^|\n)\s*"[A-Z][^"]{3,40}"\s+(?:means|shall\s+mean|has\s+the\s+meaning)|'
        r'definitions?\s+(?:section|article)|'
        r'as\s+used\s+(?:herein|in\s+this\s+agreement)',
        re.IGNORECASE)),
    ("financial_statements",      "Financials",  75, re.compile(
        r'financial\s+statement|'
        r'balance\s+sheet|'
        r'income\s+statement|profit\s+and\s+loss|'
        r'EBITDA|revenue|cash\s+flow',
        re.IGNORECASE)),
    ("dispute_resolution",        "Disputes",    60, re.compile(
        r'arbitration|'
        r'dispute\s+resolution|'
        r'governing\s+law|jurisdiction',
        re.IGNORECASE)),
    # Boilerplate — deprioritise
    ("boilerplate",               "Boilerplate", 15, re.compile(
        r'(?:^|\n)\s*(?:ARTICLE|SECTION)\s+\d+\s*\n\s*(?:MISCELLANEOUS|GENERAL\s+PROVISIONS|NOTICES|ENTIRE\s+AGREEMENT|COUNTERPARTS|HEADINGS|SEVERABILITY|WAIVER)|'
        r'this\s+agreement\s+may\s+be\s+executed\s+in\s+counterparts|'
        r'headings\s+(?:in\s+this\s+agreement\s+)?(?:are|shall\s+be)\s+(?:for\s+)?(?:convenience|reference)|'
        r'entire\s+agreement\s+(?:and|of)\s+the\s+parties|'
        r'further\s+assurances|'
        r'successors\s+and\s+assigns',
        re.IGNORECASE)),
]

# Boilerplate filler phrases — chunks dominated by these get heavily deprioritised
_BOILERPLATE_PHRASES = re.compile(
    r'\b(?:hereinafter|herein|hereof|hereunder|hereto|hereby|'
    r'whereas|witnesseth|now therefore|in witness whereof|'
    r'mutually agreed|good and valuable consideration|'
    r'force and effect|null and void|time of the essence|'
    r'without limitation|including but not limited to)\b',
    re.IGNORECASE,
)


_DEFINITIONS_DENSITY_RE = re.compile(
    r'"[A-Z][^"]{3,40}"\s+(?:means|shall\s+mean|has\s+the\s+meaning)',
    re.IGNORECASE,
)


def synaptic_priority_score(text: str) -> tuple[int, str, str]:
    """
    Score a chunk by M&A signal density.
    Returns (priority_score 0-100, section_type, section_label).
    Higher = more important = agent sees it first.

    Design note: _SECTION_PATTERNS is ordered highest-priority-first and returns
    the FIRST match. This means a definitions section that defines e.g. "Purchase
    Price" gets classified as purchase_price (85) rather than definitions (70) —
    intentional, because the signal density of the defined term matters more than
    the structural role of the section.

    Exception: if the chunk is PRIMARILY a definitions block (≥3 "X" means Y
    patterns) and only incidentally contains a high-signal keyword, we re-score
    it as definitions to preserve semantic accuracy.
    """
    # Detect definitions-dominated chunks first — avoids masking
    def_count = len(_DEFINITIONS_DENSITY_RE.findall(text))
    if def_count >= 3:
        # Still score by signal density but override section_type to definitions
        signal_count = sum(1 for _, _, _, p in _SECTION_PATTERNS if p.search(text))
        boost = min(5, signal_count - 1) * 2
        return min(80, 70 + boost), "definitions", "Definitions"

    # Check each section pattern (ordered by priority)
    for section_type, label, base_priority, pattern in _SECTION_PATTERNS:
        if pattern.search(text):
            # Boost if multiple M&A signals in same chunk
            signal_count = sum(1 for _, _, _, p in _SECTION_PATTERNS if p.search(text))
            boost = min(5, signal_count - 1) * 2
            return min(100, base_priority + boost), section_type, label

    # Count boilerplate phrases — penalise chunks full of legal throat-clearing
    bp_matches = len(_BOILERPLATE_PHRASES.findall(text))
    if bp_matches >= 4:
        return max(5, 30 - bp_matches * 3), "boilerplate", "Boilerplate"

    # Default: unclassified clause
    return 40, "general", "General"


def synaptic_prune(chunks: list[dict], drop_boilerplate: bool = False) -> list[dict]:
    """
    Apply Synaptic Pruning to a chunk list:
    1. Score each chunk by M&A signal priority
    2. Tag with section_type, section_label, priority
    3. Sort high-priority chunks first (agents process them first)
    4. Optionally drop boilerplate chunks entirely (for context-constrained runs)

    The original page order is preserved in chunk['page'] and chunk['char_start'].
    The returned order is priority-first so agents see what matters most.
    """
    scored = []
    for chunk in chunks:
        priority, section_type, label = synaptic_priority_score(chunk["text"])
        enriched = dict(chunk)
        enriched["priority"] = priority
        enriched["section_type"] = section_type
        enriched["section_label"] = label
        scored.append(enriched)

    if drop_boilerplate:
        scored = [c for c in scored if c["section_type"] != "boilerplate"]

    # Sort: high priority first, preserve page order within same priority band
    scored.sort(key=lambda c: (-c["priority"], c.get("page", 0)))
    return scored


def get_high_signal_chunks(chunks: list[dict], min_priority: int = 70) -> list[dict]:
    """Return only chunks above the priority threshold — for context-limited LLM runs."""
    return [c for c in chunks if c.get("priority", 0) >= min_priority]


def keyword_vector(text: str) -> dict:
    """Build simple term-frequency vector for BM25-style search."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = text.split()
    freq = {}
    for w in words:
        if len(w) > 2:
            freq[w] = freq.get(w, 0) + 1
    return freq


def bm25_score(query_terms: list[str], chunk_freq: dict, doc_len: int, avg_len: float = 400) -> float:
    """Simplified BM25 scoring."""
    k1, b = 1.5, 0.75
    score = 0.0
    for term in query_terms:
        tf = chunk_freq.get(term, 0)
        if tf > 0:
            norm_tf = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / avg_len))
            score += norm_tf
    return score
