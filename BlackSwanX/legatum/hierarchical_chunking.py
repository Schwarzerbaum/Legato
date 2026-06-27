#!/usr/bin/env python3
"""
Phase 2 Improvement #1: Hierarchical Graph Chunking (+5%)

Instead of flat 3-page windows, build parent-child structure:
  Document
    ├─ Chapter 1
    │   ├─ Section 1.1
    │   │   └─ Entities from pages 1-3
    │   └─ Section 1.2
    │       └─ Entities from pages 4-6
    └─ Chapter 2
        └─ ...

Benefit: Questions like "according to Chapter 3" instantly lock onto parent node,
avoiding noise from other chapters. Macro-relationships are explicit.
"""
import json
import re
from typing import Optional
from pathlib import Path


class HierarchicalGraphBuilder:
    """Build parent-child entity graph from document structure."""

    def __init__(self):
        self.chapters = {}
        self.sections = {}
        self.entities = {}
        self.relations = {}

    def detect_structure(self, pages: list[dict]) -> dict:
        """
        Detect document structure (chapters, sections) from page text.
        Uses heuristics: "# Chapter", "## Section", "### Subsection"
        """
        structure = {
            "chapters": [],
            "sections_by_chapter": {},
            "page_to_chapter": {},
            "page_to_section": {}
        }

        current_chapter = None
        current_section = None

        for page in pages:
            text = page.get("text", "")
            page_num = page.get("page", 0)

            # Detect chapter (heuristic: "Kapitel", "Chapter", "Teil")
            chapter_match = re.search(
                r"(?:Kapitel|Chapter|Teil)\s+(\d+)[:.\s]+(.+?)(?:\n|$)",
                text,
                re.IGNORECASE
            )
            if chapter_match:
                current_chapter = {
                    "number": chapter_match.group(1),
                    "title": chapter_match.group(2).strip(),
                    "start_page": page_num,
                    "end_page": page_num
                }
                structure["chapters"].append(current_chapter)
                structure["page_to_chapter"][page_num] = len(structure["chapters"]) - 1
                structure["sections_by_chapter"][len(structure["chapters"]) - 1] = []

            # Detect section (heuristic: "## ", "Abschnitt", "Section")
            section_match = re.search(
                r"(?:Abschnitt|Section|Abschnitt)\s+(\d+\.?\d*)[:.\s]+(.+?)(?:\n|$)",
                text,
                re.IGNORECASE
            )
            if section_match and current_chapter is not None:
                current_section = {
                    "number": section_match.group(1),
                    "title": section_match.group(2).strip(),
                    "start_page": page_num,
                    "end_page": page_num,
                    "chapter": current_chapter["number"]
                }
                ch_idx = len(structure["chapters"]) - 1
                structure["sections_by_chapter"][ch_idx].append(current_section)
                structure["page_to_section"][page_num] = len(structure["sections_by_chapter"][ch_idx]) - 1

        return structure

    def build_hierarchical_graph(
        self,
        entities: list[dict],
        relations: list[dict],
        mentions: list[dict],
        structure: dict
    ) -> dict:
        """
        Build hierarchical graph:
        - Root: Document
        - Level 1: Chapters
        - Level 2: Sections
        - Level 3: Entities (with parent links)
        """
        graph = {
            "document": {
                "name": "BIM-Leitfaden",
                "type": "document",
                "children": []  # Chapter IDs
            },
            "chapters": {},
            "sections": {},
            "entities": {},
            "relations": relations,
            "mentions": mentions,
            "hierarchy": structure
        }

        # Create chapter nodes
        for i, chapter in enumerate(structure["chapters"]):
            ch_id = f"chapter_{chapter['number']}"
            graph["chapters"][ch_id] = {
                "id": ch_id,
                "name": f"Chapter {chapter['number']}",
                "title": chapter["title"],
                "type": "chapter",
                "start_page": chapter["start_page"],
                "end_page": chapter["end_page"],
                "children": []  # Section IDs
            }
            graph["document"]["children"].append(ch_id)

        # Create section nodes
        for ch_idx, sections in structure["sections_by_chapter"].items():
            ch_id = f"chapter_{structure['chapters'][ch_idx]['number']}"
            for sec_idx, section in enumerate(sections):
                sec_id = f"section_{section['chapter']}_{section['number']}"
                graph["sections"][sec_id] = {
                    "id": sec_id,
                    "name": f"Section {section['number']}",
                    "title": section["title"],
                    "type": "section",
                    "chapter": section["chapter"],
                    "start_page": section["start_page"],
                    "end_page": section["end_page"],
                    "children": []  # Entity IDs
                }
                graph["chapters"][ch_id]["children"].append(sec_id)

        # Assign entities to sections/chapters
        for entity in entities:
            entity_id = f"entity_{entity['name'].lower()}"
            graph["entities"][entity_id] = {
                **entity,
                "id": entity_id,
                "parents": []  # Parent section/chapter IDs
            }

            # Find parent based on mentions
            entity_name = entity["name"].lower()
            for mention in mentions:
                if mention.get("entity_name", "").lower() == entity_name:
                    page = mention.get("page", 0)

                    # Link to section if available
                    if page in structure["page_to_section"]:
                        sec_idx = structure["page_to_section"][page]
                        ch_idx = structure["page_to_chapter"].get(page, 0)
                        chapter_num = structure["chapters"][ch_idx]["number"]
                        section_num = structure["sections_by_chapter"][ch_idx][sec_idx]["number"]
                        sec_id = f"section_{chapter_num}_{section_num}"

                        if sec_id not in graph["entities"][entity_id]["parents"]:
                            graph["entities"][entity_id]["parents"].append(sec_id)
                            if sec_id in graph["sections"]:
                                graph["sections"][sec_id]["children"].append(entity_id)

                    # Link to chapter if no section
                    elif page in structure["page_to_chapter"]:
                        ch_idx = structure["page_to_chapter"][page]
                        ch_num = structure["chapters"][ch_idx]["number"]
                        ch_id = f"chapter_{ch_num}"

                        if ch_id not in graph["entities"][entity_id]["parents"]:
                            graph["entities"][entity_id]["parents"].append(ch_id)
                            if ch_id in graph["chapters"]:
                                graph["chapters"][ch_id]["children"].append(entity_id)

        return graph

    def retrieve_by_chapter(self, graph: dict, chapter_num: str) -> dict:
        """
        Retrieve all entities in a chapter (query-time optimization).
        Example: "Chapter 3" question → fetch chapter_3 node + all its children.
        """
        ch_id = f"chapter_{chapter_num}"
        if ch_id not in graph["chapters"]:
            return {"entities": [], "relations": []}

        chapter = graph["chapters"][ch_id]
        entities_in_chapter = []

        # Collect all entities from sections in this chapter
        for sec_id in chapter["children"]:
            section = graph["sections"].get(sec_id, {})
            for entity_id in section.get("children", []):
                if entity_id in graph["entities"]:
                    entities_in_chapter.append(graph["entities"][entity_id])

        # Filter relations to those involving chapter entities
        entity_names = {e["name"].lower() for e in entities_in_chapter}
        relations_in_chapter = [
            r for r in graph.get("relations", [])
            if r.get("source", "").lower() in entity_names or r.get("target", "").lower() in entity_names
        ]

        return {
            "chapter": chapter,
            "entities": entities_in_chapter,
            "relations": relations_in_chapter
        }


# ── Integration with QA Runtime ────────────────────────────────────────────

def enhance_qa_with_hierarchical_chunking(question: str, index: dict) -> dict:
    """
    Detect if question mentions a chapter/section, then use hierarchical retrieval.
    """
    builder = HierarchicalGraphBuilder()
    pages = index.get("pages", [])
    structure = builder.detect_structure(pages)

    # Build hierarchical graph
    graph = builder.build_hierarchical_graph(
        index["graph"]["entities"],
        index["graph"]["relations"],
        index["graph"]["mentions"],
        structure
    )

    # Detect chapter/section mention in question
    chapter_match = re.search(r"(?:Chapter|Kapitel)\s+(\d+)", question, re.IGNORECASE)
    if chapter_match:
        chapter_num = chapter_match.group(1)
        return builder.retrieve_by_chapter(graph, chapter_num)

    # Return full graph for general queries
    return {
        "entities": graph["entities"].values(),
        "relations": graph["relations"],
        "structure": structure
    }
