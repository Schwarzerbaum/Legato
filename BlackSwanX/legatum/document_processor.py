"""
Document Processor Pipeline
=============================
Orchestrates document topography, image deduplication, and defect detection.

Workflow:
1. Ingest PDFs → extract topography (structure, stamps, amendments)
2. Ingest photos → deduplicate (remove near-duplicates)
3. Analyze remaining photos → detect defects
4. Convert to pheromone signals and Legal-Twin KG inputs
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from legatum.document_topography import (
    parse_pdf_topography,
    topography_to_text_summary,
    extract_amendments,
)
from legatum.image_deduplicator import ImageDeduplicator, deduplicate_images
from legatum.edge_defect_detector import (
    create_detector,
    analyze_batch,
    results_to_pheromone_signals,
)
from legatum.diagram_analyzer import extract_diagrams_from_pdf, diagrams_to_kg_edges


@dataclass
class ProcessingResult:
    """Complete result of processing a document batch."""
    pdf_results: list[dict]  # Topography results
    image_stats: dict  # Deduplication summary
    defect_results: list[dict]  # Analysis results
    pheromone_signals: list[dict]  # Signals for pheromone system
    kg_amendments: list[dict]  # Amendments for Legal-Twin KG
    processing_summary: dict


class DocumentProcessor:
    """
    Main pipeline orchestrator.
    """

    def __init__(self, use_mock_detector: bool = True):
        self.detector = create_detector(use_mock=use_mock_detector)
        self.deduplicator = ImageDeduplicator(similarity_threshold=0.90)

    def process_pdfs(self, pdf_paths: list[str]) -> list[dict]:
        """Process PDFs to extract topography and diagram structure."""
        results = []
        for pdf_path in pdf_paths:
            topo = parse_pdf_topography(pdf_path)
            if topo:
                amendments = extract_amendments(topo)

                # Extract diagram structure (4-layer analysis)
                diagrams = extract_diagrams_from_pdf(pdf_path)
                diagram_edges = diagrams_to_kg_edges(diagrams)

                results.append({
                    "filename": topo.filename,
                    "pages": topo.pages,
                    "document_hash": topo.document_hash,
                    "block_count": len(topo.blocks),
                    "stamp_count": len(topo.detected_stamps),
                    "table_count": len(topo.detected_tables),
                    "amendments": amendments,
                    "diagrams_detected": len(diagrams),
                    "diagram_edges": diagram_edges,
                    "extraction_methods": list(set(
                        m for d in diagrams for m in d.extraction_methods_used
                    )),
                    "text_summary": topography_to_text_summary(topo),
                })
        return results

    def process_images(self, image_paths: list[str]) -> tuple[dict, list[dict]]:
        """
        Process images: deduplicate, then analyze for defects.
        Returns (dedup_stats, analysis_results).
        """
        # Step 1: Deduplication
        dedup_result = deduplicate_images(image_paths, threshold=0.90)
        unique_images = dedup_result["unique_images"]

        # Step 2: Defect detection on unique images only
        if self.detector and unique_images:
            full_paths = [
                next(p for p in image_paths if Path(p).name == img)
                for img in unique_images
            ]
            results, summary = analyze_batch(full_paths, self.detector)

            # Format analysis results
            analysis_results = []
            for result in results:
                analysis_results.append({
                    "filename": result.filename,
                    "image_hash": result.image_hash,
                    "has_defects": result.has_defects,
                    "defect_count": len(result.detections),
                    "detections": [
                        {
                            "type": d.defect_type,
                            "confidence": round(d.confidence, 3),
                            "severity": d.severity,
                            "signal": d.pheromone_signal,
                        }
                        for d in result.detections
                    ],
                    "primary_signals": result.primary_signals,
                })

            return dedup_result, analysis_results

        return dedup_result, []

    def process_batch(
        self,
        pdf_paths: Optional[list[str]] = None,
        image_paths: Optional[list[str]] = None,
    ) -> ProcessingResult:
        """
        Process a complete batch of PDFs and images.
        """
        pdf_paths = pdf_paths or []
        image_paths = image_paths or []

        # Process PDFs
        pdf_results = self.process_pdfs(pdf_paths)

        # Collect amendments for KG
        kg_amendments = []
        for result in pdf_results:
            kg_amendments.extend(result.get("amendments", []))

        # Process images
        image_stats, defect_results = self.process_images(image_paths)

        # Convert defect results to pheromone signals
        pheromone_signals = []
        for defect_result in defect_results:
            if defect_result["primary_signals"]:
                pheromone_signals.append({
                    "source": defect_result["filename"],
                    "signal_types": defect_result["primary_signals"],
                    "defect_count": defect_result["defect_count"],
                })

        # Summary
        processing_summary = {
            "pdfs_processed": len(pdf_paths),
            "pdfs_successful": len(pdf_results),
            "total_images": image_stats["total"],
            "unique_images": image_stats["unique"],
            "duplicates_skipped": image_stats["duplicates"],
            "savings_pct": round(image_stats["savings_pct"], 1),
            "images_analyzed": len(defect_results),
            "images_with_defects": len([r for r in defect_results if r["has_defects"]]),
            "total_defects_detected": sum(r["defect_count"] for r in defect_results),
            "pheromone_signals_generated": len(pheromone_signals),
            "amendments_detected": len(kg_amendments),
        }

        return ProcessingResult(
            pdf_results=pdf_results,
            image_stats=image_stats,
            defect_results=defect_results,
            pheromone_signals=pheromone_signals,
            kg_amendments=kg_amendments,
            processing_summary=processing_summary,
        )


# ── Convenience function ───────────────────────────────────────────────────────

def process_documents(
    pdf_paths: Optional[list[str]] = None,
    image_paths: Optional[list[str]] = None,
    use_mock_detector: bool = True,
) -> ProcessingResult:
    """
    One-shot processing of documents and images.
    """
    processor = DocumentProcessor(use_mock_detector=use_mock_detector)
    return processor.process_batch(pdf_paths=pdf_paths, image_paths=image_paths)
