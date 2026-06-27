"""
Diagram Structure Analyzer
===========================
Four-layer approach to extract structured information from PDFs with diagrams.

Layers (in order of preference):
1. Vector extraction — Lines, arrows, boxes as mathematical paths
2. Color extraction — Pixel sampling for metadata
3. Spatial hierarchy — Bounding box containment for relationships
4. Local vision model fallback — MiniCPM-V for complex diagrams

No cloud APIs. No expensive vision LLMs. All local.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re

try:
    import fitz
except ImportError:
    fitz = None

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DiagramElement:
    """A detected element in a diagram (box, text, shape)."""
    name: str
    bbox: list[float]  # [x0, y0, x1, y1]
    element_type: str  # "box", "text", "arrow", "line"
    color: Optional[str] = None  # Hex color or semantic name
    status: Optional[str] = None  # "prepared", "next_step", "category"
    page: int = 0


@dataclass
class DiagramRelationship:
    """A detected relationship between diagram elements."""
    source: str
    target: str
    relationship_type: str  # "subordinate_to", "points_to", "flows_to", "depends_on"
    confidence: float  # 0-1
    extraction_method: str  # "vector", "spatial", "color", "vision"


@dataclass
class DiagramAnalysisResult:
    """Complete analysis of a diagram."""
    page: int
    elements: list[DiagramElement]
    relationships: list[DiagramRelationship]
    extraction_methods_used: list[str]


# ── Color extraction utilities ────────────────────────────────────────────────

COLOR_MAPPINGS = {
    "blue": {"rgb_range": ((50, 100, 200), (150, 180, 255)), "semantic": "prepared"},
    "yellow": {"rgb_range": ((200, 200, 0), (255, 255, 100)), "semantic": "category"},
    "gray": {"rgb_range": ((150, 150, 150), (200, 200, 200)), "semantic": "next_step"},
    "white": {"rgb_range": ((240, 240, 240), (255, 255, 255)), "semantic": "neutral"},
}


def color_from_rgb(r: int, g: int, b: int) -> Optional[str]:
    """Identify color name from RGB values."""
    for color_name, config in COLOR_MAPPINGS.items():
        (r_min, g_min, b_min), (r_max, g_max, b_max) = config["rgb_range"]
        if r_min <= r <= r_max and g_min <= g <= g_max and b_min <= b <= b_max:
            return color_name
    return None


def sample_color_at_bbox(image, bbox: list[float]) -> Optional[tuple[int, int, int]]:
    """Sample the dominant color in a bounding box region."""
    if cv2 is None or image is None:
        return None

    x0, y0, x1, y1 = [int(v) for v in bbox]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(image.shape[1], x1), min(image.shape[0], y1)

    if x0 >= x1 or y0 >= y1:
        return None

    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None

    # Calculate mean color
    mean_color = cv2.mean(crop)[:3]
    return tuple(int(c) for c in mean_color)


# ── Layer 1: Vector extraction ─────────────────────────────────────────────────

def extract_vectors_from_pdf(pdf_path: str, page_num: int = 0) -> Optional[tuple[list[DiagramElement], list[DiagramRelationship]]]:
    """
    Extract vector graphics (lines, arrows, boxes) from PDF using PyMuPDF.
    Returns (elements, relationships).
    """
    if fitz is None:
        return None

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
    except Exception:
        return None

    elements = []
    relationships = []

    # Extract drawings (vectors)
    drawings = page.get_drawings()

    for drawing in drawings:
        # Each drawing is a dict with 'rect' and 'type' keys
        try:
            rect = drawing.get("rect") or drawing.get("bbox")
            if not rect:
                continue

            # rect can be a fitz.Rect or a tuple/list
            if hasattr(rect, 'x0'):
                bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
            else:
                bbox = list(rect)

            draw_type = drawing.get("type", "")
            # PyMuPDF uses string codes: "f"=fill/rect, "s"=stroke/line, "fs"=fill+stroke
            fill = drawing.get("fill")
            has_fill = fill is not None

            # Skip degenerate 0-height lines (horizontal rules)
            if bbox[3] - bbox[1] < 2 and draw_type == "s":
                elements.append(DiagramElement(
                    name=f"line_{len(elements)}",
                    bbox=bbox,
                    element_type="line",
                    page=page_num,
                ))
            elif has_fill or draw_type in ("f", "fs"):
                # Filled rectangle = a box/shape
                elements.append(DiagramElement(
                    name=f"box_{len(elements)}",
                    bbox=bbox,
                    element_type="box",
                    page=page_num,
                ))
            elif draw_type == "s":
                elements.append(DiagramElement(
                    name=f"line_{len(elements)}",
                    bbox=bbox,
                    element_type="line",
                    page=page_num,
                ))
        except (TypeError, KeyError, AttributeError):
            continue

    doc.close()
    return elements, relationships


# ── Layer 2: Color extraction ──────────────────────────────────────────────────

def extract_colors_from_page(pdf_path: str, page_num: int = 0, elements: list[DiagramElement] = None) -> list[DiagramElement]:
    """
    Sample colors from rendered page at element bounding boxes.
    Annotates elements with color and semantic status.
    """
    if cv2 is None or fitz is None or elements is None:
        return elements

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        # Render page at 150 DPI
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        doc.close()
    except Exception:
        return elements

    # Sample color at each element
    for elem in elements:
        rgb = sample_color_at_bbox(image, elem.bbox)
        if rgb:
            color_name = color_from_rgb(*rgb)
            elem.color = color_name
            # Map color to semantic status
            if color_name in COLOR_MAPPINGS:
                elem.status = COLOR_MAPPINGS[color_name].get("semantic")

    return elements


# ── Text-to-box label matching ────────────────────────────────────────────────

def label_elements_with_text(pdf_path: str, page_num: int, elements: list[DiagramElement]) -> list[DiagramElement]:
    """
    Match text blocks to their nearest enclosing box and set box name = text label.
    This makes KG relationships show real names instead of box_N.
    """
    if fitz is None or not elements:
        return elements

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        text_dict = page.get_text("dict")
        doc.close()
    except Exception:
        return elements

    boxes = [e for e in elements if e.element_type == "box"]

    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue
        block_text = " ".join(
            span["text"].strip()
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        )
        if not block_text:
            continue

        bx0, by0, bx1, by1 = block.get("bbox", [0, 0, 0, 0])
        bx_cx = (bx0 + bx1) / 2
        bx_cy = (by0 + by1) / 2

        # Find the tightest box that contains this text centroid
        best_box = None
        best_area = float("inf")
        for box in boxes:
            x0, y0, x1, y1 = box.bbox
            if x0 <= bx_cx <= x1 and y0 <= bx_cy <= y1:
                area = (x1 - x0) * (y1 - y0)
                if area < best_area:
                    best_area = area
                    best_box = box

        if best_box:
            label = block_text[:60].strip()
            if best_box.name.startswith("box_"):
                best_box.name = label
            else:
                best_box.name = best_box.name + " / " + label

    return elements


# ── Layer 3: Spatial hierarchy ─────────────────────────────────────────────────

def infer_spatial_hierarchy(elements: list[DiagramElement]) -> list[DiagramRelationship]:
    """
    Detect parent-child relationships by bounding box containment.
    If box A contains box B, generate relationship: B --subordinate_to--> A.
    """
    relationships = []

    for elem_a in elements:
        if elem_a.element_type != "box":
            continue

        x0_a, y0_a, x1_a, y1_a = elem_a.bbox

        for elem_b in elements:
            if elem_b.element_type != "box" or elem_a == elem_b:
                continue

            x0_b, y0_b, x1_b, y1_b = elem_b.bbox

            # Check if B is inside A (with margin)
            margin = 5
            if (x0_a + margin < x0_b and x1_b < x1_a - margin and
                y0_a + margin < y0_b and y1_b < y1_a - margin):

                relationships.append(DiagramRelationship(
                    source=elem_b.name,
                    target=elem_a.name,
                    relationship_type="subordinate_to",
                    confidence=0.95,
                    extraction_method="spatial",
                ))

    return relationships


def infer_text_hierarchy(pdf_path: str, page_num: int = 0) -> list[DiagramRelationship]:
    """
    Extract text-based hierarchy by analyzing the PDF text dict.
    Look for patterns like "Parent\n  Child" or "Parent\n    Child".
    """
    if fitz is None:
        return []

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        text_dict = page.get_text("dict")
    except Exception:
        return []

    relationships = []
    y_positions = {}

    # Extract text with y-coordinates
    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue

        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                y = span["bbox"][1]

                if text:
                    y_positions[text] = y

    # Heuristic: if two texts have similar y but one is indented, infer hierarchy
    # This is simplistic; real implementation would analyze x-coordinates and grouping
    prev_text = None
    prev_x = 0
    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue

        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                x = span["bbox"][0]

                # If this text is indented more than previous, it's a child
                if prev_text and x > prev_x + 20:
                    relationships.append(DiagramRelationship(
                        source=text,
                        target=prev_text,
                        relationship_type="subordinate_to",
                        confidence=0.70,
                        extraction_method="text_indent",
                    ))

                prev_text = text
                prev_x = x

    doc.close()
    return relationships


# ── Layer 4: Local vision model fallback ───────────────────────────────────────

def analyze_diagram_with_vision(pdf_path: str, page_num: int = 0) -> Optional[list[DiagramRelationship]]:
    """
    Fallback: Use local vision model (MiniCPM-V or Moondream2) to analyze diagram.

    In production, this would call Ollama with a vision model:
    curl http://localhost:11434/api/generate \
      -d '{"model":"minicpm-v","prompt":"Analyze this diagram structure",...}'

    For now, returns None (requires Ollama setup).
    """
    # This requires Ollama + vision model running locally
    # Implementation would:
    # 1. Render page to image
    # 2. Call Ollama vision endpoint
    # 3. Parse response for relationships
    # For demo purposes, return None
    return None


# ── Main analyzer ──────────────────────────────────────────────────────────────

class DiagramAnalyzer:
    """Multi-layer diagram analyzer using deterministic local methods."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def analyze(self, page_num: int = 0) -> Optional[DiagramAnalysisResult]:
        """
        Analyze a page for diagram structure using all available layers.
        """
        elements = []
        relationships = []
        methods = []

        # Layer 1: Vector extraction
        vectors = extract_vectors_from_pdf(self.pdf_path, page_num)
        if vectors:
            v_elements, v_rels = vectors
            elements.extend(v_elements)
            relationships.extend(v_rels)
            methods.append("vector_extraction")

        # Layer 2: Color extraction
        if cv2:
            elements = extract_colors_from_page(self.pdf_path, page_num, elements)
            methods.append("color_extraction")

        # Label boxes with their text content (CEO-ready named nodes)
        elements = label_elements_with_text(self.pdf_path, page_num, elements)

        # Layer 3: Spatial hierarchy
        spatial_rels = infer_spatial_hierarchy(elements)
        relationships.extend(spatial_rels)
        if spatial_rels:
            methods.append("spatial_hierarchy")

        # Layer 3b: Text hierarchy
        text_rels = infer_text_hierarchy(self.pdf_path, page_num)
        relationships.extend(text_rels)
        if text_rels:
            methods.append("text_hierarchy")

        # Layer 4: Local vision model fallback
        # (requires Ollama + vision model)
        # vision_rels = analyze_diagram_with_vision(self.pdf_path, page_num)
        # if vision_rels:
        #     relationships.extend(vision_rels)
        #     methods.append("local_vision_model")

        return DiagramAnalysisResult(
            page=page_num,
            elements=elements,
            relationships=relationships,
            extraction_methods_used=methods,
        )


# ── Integration with document processor ────────────────────────────────────────

def extract_diagrams_from_pdf(pdf_path: str) -> list[DiagramAnalysisResult]:
    """Analyze all pages in a PDF for diagram structure."""
    if fitz is None:
        return []

    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
    except Exception:
        return []

    results = []
    analyzer = DiagramAnalyzer(pdf_path)

    for page_num in range(min(page_count, 20)):  # Analyze first 20 pages
        result = analyzer.analyze(page_num)
        if result and (result.elements or result.relationships):
            results.append(result)

    return results


def diagrams_to_kg_edges(diagrams: list[DiagramAnalysisResult]) -> list[dict]:
    """Convert diagram analysis to Knowledge Graph edges."""
    edges = []

    for diagram in diagrams:
        for rel in diagram.relationships:
            edges.append({
                "source": rel.source,
                "target": rel.target,
                "edge_type": rel.relationship_type,
                "confidence": rel.confidence,
                "method": rel.extraction_method,
                "page": diagram.page,
            })

        for elem in diagram.elements:
            if elem.status or elem.color:
                edges.append({
                    "node": elem.name,
                    "properties": {
                        "color": elem.color,
                        "status": elem.status,
                    },
                    "page": diagram.page,
                })

    return edges
