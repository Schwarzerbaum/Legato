#!/usr/bin/env python3
"""
Phase 2 Improvement #3: Layout-Aware PDF Parsing (+5%)

Current: OCR extracts raw text/images from PDFs
Better: Extract structured data (tables, matrices) as clean Markdown/HTML

Example:
  Raw table in PDF:
    Responsibility | Owner | Phase
    ─────────────────────────────
    Design         | A     | 1
    Review         | B     | 2

  Parsed as Markdown table + entity links:
    | Responsibility | Owner | Phase |
    |---|---|---|
    | Design (LOI entity) | Architect (person entity) | Phase 1 (phase entity) |
    | ...

Benefit: LLM understands matrix structure, no hallucination on responsibilities/phases.
"""
import re
from typing import Optional
from pathlib import Path


class LayoutAwarePDFParser:
    """Extract structured tables and matrices from PDF text."""

    def __init__(self):
        self.tables = []
        self.matrices = []

    def detect_table_from_text(self, text: str) -> Optional[dict]:
        """
        Detect and parse ASCII table from text.
        Looks for: pipe-delimited rows, or uniform spacing.
        """
        lines = text.split("\n")

        # Look for pipe-delimited tables (Markdown style)
        pipe_lines = [l for l in lines if "|" in l]
        if len(pipe_lines) >= 3:
            return self.parse_pipe_table(pipe_lines)

        # Look for uniformly-spaced columns (fixed-width table)
        if len(lines) >= 3:
            result = self.parse_fixed_width_table(lines)
            if result and len(result["rows"]) >= 2:
                return result

        return None

    def parse_pipe_table(self, lines: list[str]) -> dict:
        """Parse Markdown-style pipe-delimited table."""
        table = {
            "format": "markdown",
            "headers": [],
            "rows": [],
            "raw_lines": lines
        }

        # First line: headers
        header_line = lines[0].strip("|").split("|")
        table["headers"] = [h.strip() for h in header_line]

        # Skip separator line (---)
        # Parse data rows
        for line in lines[2:]:
            cells = line.strip("|").split("|")
            if len(cells) == len(table["headers"]):
                table["rows"].append([c.strip() for c in cells])

        return table if table["rows"] else None

    def parse_fixed_width_table(self, lines: list[str]) -> Optional[dict]:
        """Parse fixed-width columns (spaces as delimiters)."""
        # Heuristic: find column boundaries based on spacing
        if not lines or len(lines) < 3:
            return None

        # Simple approach: split on 2+ spaces
        table = {
            "format": "fixed_width",
            "headers": [],
            "rows": [],
            "raw_lines": lines
        }

        # First line: headers
        headers = re.split(r'\s{2,}', lines[0].strip())
        table["headers"] = [h.strip() for h in headers if h.strip()]

        # Parse rows
        for line in lines[2:]:
            if line.strip():
                cells = re.split(r'\s{2,}', line.strip())
                if len(cells) >= len(table["headers"]):
                    table["rows"].append([c.strip() for c in cells[:len(table["headers"])]])

        return table if table["rows"] else None

    def link_table_to_entities(
        self,
        table: dict,
        entities: list[dict]
    ) -> dict:
        """Link table cell values to entities in the graph."""
        entity_names = {e["name"].lower(): e for e in entities}

        enhanced_table = {
            **table,
            "entity_links": {}  # cell_value → entity
        }

        # Scan all cells for entity matches
        all_cells = table["headers"] + [cell for row in table["rows"] for cell in row]
        for cell_value in all_cells:
            cell_lower = cell_value.lower()
            for ent_name, ent in entity_names.items():
                if ent_name in cell_lower:
                    enhanced_table["entity_links"][cell_value] = {
                        "entity_name": ent["name"],
                        "entity_type": ent.get("type", ""),
                        "entity_description": ent.get("description", "")
                    }

        return enhanced_table

    def table_to_markdown(self, table: dict) -> str:
        """Convert table to Markdown format (for LLM context)."""
        if not table or not table.get("headers"):
            return ""

        # Header row
        md = "| " + " | ".join(table["headers"]) + " |\n"

        # Separator
        md += "|" + "|".join(["---"] * len(table["headers"])) + "|\n"

        # Data rows
        for row in table.get("rows", []):
            md += "| " + " | ".join(row) + " |\n"

        return md

    def extract_all_tables(self, pages: list[dict], entities: list[dict]) -> list[dict]:
        """Extract and link all tables from document pages."""
        all_tables = []

        for page in pages:
            text = page.get("text", "")
            table = self.detect_table_from_text(text)

            if table:
                # Link to entities
                table = self.link_table_to_entities(table, entities)
                table["page"] = page.get("page", 0)
                all_tables.append(table)

        return all_tables

    def extract_responsibilities_matrix(
        self,
        tables: list[dict]
    ) -> Optional[dict]:
        """
        Find and extract RACI/responsibility matrix (common in guidelines).
        Pattern: rows=tasks, cols=roles, cells=responsibility level (R/A/C/I)
        """
        for table in tables:
            headers = [h.lower() for h in table.get("headers", [])]

            # Look for responsibility/phase columns
            if any(
                word in headers for word in ["responsibility", "phase", "owner", "phase", "actor"]
            ):
                return {
                    "type": "responsibility_matrix",
                    "table": table,
                    "page": table.get("page", 0),
                    "markdown": self.table_to_markdown(table)
                }

        return None


# ── Integration with Offline Preprocessor ──────────────────────────────────

def enhance_preprocessing_with_layout_parsing(
    pages: list[dict],
    entities: list[dict]
) -> dict:
    """
    Extract structured tables during preprocessing.
    Adds table metadata to each page's section object.
    """
    parser = LayoutAwarePDFParser()

    # Extract all tables
    tables = parser.extract_all_tables(pages, entities)

    # Find special matrices (responsibility, phase gates, etc.)
    special_matrices = {
        "responsibility": parser.extract_responsibilities_matrix(tables)
    }

    return {
        "tables": tables,
        "special_matrices": special_matrices,
        "table_markdowns": [parser.table_to_markdown(t) for t in tables]
    }


def format_tables_for_synthesis(layout_analysis: dict) -> str:
    """Format extracted tables as context for LLM synthesis."""
    context = ""

    if layout_analysis.get("special_matrices", {}).get("responsibility"):
        context += "**Responsibility Matrix:**\n"
        context += layout_analysis["special_matrices"]["responsibility"]["markdown"] + "\n\n"

    # Add regular tables
    for table in layout_analysis.get("tables", [])[:3]:  # Top 3 tables
        context += f"**Table (page {table.get('page', '?')}):**\n"
        context += parser_instance.table_to_markdown(table) + "\n\n"

    return context


# Global parser instance for formatting
parser_instance = LayoutAwarePDFParser()
