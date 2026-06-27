"""
Document Topography Parser
===========================
Extracts text with spatial coordinates from PDFs and images.
Understands document structure: stamps, signatures, tables, amendments.

Uses PyMuPDF (fitz) for instant, offline PDF parsing.
No vision LLM required.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import hashlib

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TextBlock:
    """A text element with spatial coordinates and metadata."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_type: str  # "text", "image", "table", "stamp", "signature"
    page: int
    confidence: float = 1.0
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    is_bold: bool = False


@dataclass
class DocumentTopography:
    """Complete spatial structure of a document."""
    filename: str
    pages: int
    blocks: list[TextBlock]
    detected_stamps: list[dict]  # Revisions, approvals, signatures
    detected_tables: list[dict]  # Tables with bounding boxes
    document_hash: str  # SHA-256 of content

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "pages": self.pages,
            "blocks": [asdict(b) for b in self.blocks],
            "detected_stamps": self.detected_stamps,
            "detected_tables": self.detected_tables,
            "document_hash": self.document_hash,
        }


# ── Topography detection patterns ─────────────────────────────────────────────

STAMP_PATTERNS = [
    r"REVISION\s+([A-Z0-9]+)",
    r"REV\s+([A-Z0-9]+)",
    r"AMENDMENT\s+(\d+)",
    r"NACHTRAG\s+(\d+)",
    r"GENEHMIGT|APPROVED|FREIGEGEBEN",
    r"UNTERSCHRIFT|SIGNATURE|SIGNATUR",
    r"STEMPEL|STAMP|SIEGEL",
    r"\d{1,2}\.\d{1,2}\.\d{4}",  # Date pattern
]

TABLE_INDICATORS = [
    "Position", "Menge", "Einheitspreis", "Gesamtbetrag", "EUR",
    "Item", "Quantity", "Unit Price",
    "LOG 100", "LOI 100", "Tabelle", "Table",
    "LOG\t", "LOI\t", "LOD\t",
]


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_pdf_topography(pdf_path: str) -> Optional[DocumentTopography]:
    """
    Extract spatial structure from a PDF.
    Returns None if PyMuPDF not available or file not readable.
    """
    if fitz is None:
        return None

    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
    except Exception:
        return None

    blocks = []
    detected_stamps = []
    detected_tables = []
    all_text = ""

    for page_num, page in enumerate(doc):
        # Extract text blocks with coordinates
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    all_text += " " + text

                    bbox = span["bbox"]
                    tb = TextBlock(
                        text=text,
                        x0=bbox[0],
                        y0=bbox[1],
                        x1=bbox[2],
                        y1=bbox[3],
                        block_type="text",
                        page=page_num,
                        font_size=span.get("size"),
                        font_name=span.get("font"),
                        is_bold="bold" in span.get("font", "").lower(),
                    )
                    blocks.append(tb)

                    # Detect stamps and signatures
                    for pattern in STAMP_PATTERNS:
                        if re.search(pattern, text, re.IGNORECASE):
                            detected_stamps.append({
                                "text": text,
                                "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                                "page": page_num,
                                "pattern": pattern,
                            })
                            break

        # Detect table regions by layout density
        # (simplified: look for vertical alignment of numbers)
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue

            line_texts = []
            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"])
                line_texts.append(line_text)

            full_block_text = " ".join(line_texts)
            if any(ind in full_block_text for ind in TABLE_INDICATORS):
                # Build rows from lines for display
                rows = [lt.strip() for lt in line_texts if lt.strip()]
                detected_tables.append({
                    "content_sample": full_block_text[:300],
                    "rows": rows[:12],
                    "bbox": block.get("bbox", [0, 0, 0, 0]),
                    "page": page_num,
                    "title": rows[0][:80] if rows else "",
                })

    doc.close()

    # Document hash for version tracking
    doc_hash = hashlib.sha256(all_text.encode()).hexdigest()

    return DocumentTopography(
        filename=Path(pdf_path).name,
        pages=page_count,
        blocks=blocks,
        detected_stamps=detected_stamps,
        detected_tables=detected_tables,
        document_hash=doc_hash,
    )


def extract_amendments(topo: DocumentTopography) -> list[dict]:
    """
    Extract document amendments and revisions from detected stamps.
    Returns list of amendments with dates and revision levels.
    """
    amendments = []

    date_pattern = r"(\d{1,2})\.(\d{1,2})\.(\d{4})"

    for stamp in topo.detected_stamps:
        text = stamp["text"]

        # Extract revision level
        rev_match = re.search(r"REVISION\s+([A-Z0-9]+)|REV\s+([A-Z0-9]+)", text, re.IGNORECASE)
        rev = rev_match.group(1) or rev_match.group(2) if rev_match else None

        # Extract date
        date_match = re.search(date_pattern, text)
        date = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else None

        if rev or date:
            amendments.append({
                "revision": rev,
                "date": date,
                "page": stamp["page"],
                "bbox": stamp["bbox"],
            })

    return sorted(amendments, key=lambda x: x.get("date", ""), reverse=True)


def topography_to_text_summary(topo: DocumentTopography) -> str:
    """Convert topography to human-readable text for downstream processing."""
    lines = [
        f"Document: {topo.filename}",
        f"Pages: {topo.pages}",
        f"Hash: {topo.document_hash[:16]}...",
        "",
        "Text Content:",
    ]

    for block in sorted(topo.blocks, key=lambda b: (b.page, b.y0)):
        lines.append(f"  Page {block.page} [{block.x0:.0f},{block.y0:.0f}]: {block.text}")

    if topo.detected_stamps:
        lines.append("")
        lines.append("Detected Stamps/Revisions:")
        for stamp in topo.detected_stamps:
            lines.append(f"  {stamp['text']} @ Page {stamp['page']}")

    if topo.detected_tables:
        lines.append("")
        lines.append("Detected Tables:")
        for table in topo.detected_tables:
            lines.append(f"  Page {table['page']}: {table['content_sample']}")

    return "\n".join(lines)
