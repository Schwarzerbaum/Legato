"""
Edge-Based Construction Defect Detector
=========================================
Lightweight ONNX-based detection of construction defects in photos.
Runs locally on CPU, no vision LLM required.

Detects:
- Concrete cracks and spalling
- Rebar exposure
- Missing PPE / safety violations
- Misalignment and geometric defects
- Surface damage (scuff, chip, stain)

Output: Text tags + confidence scores → feed into Pheromone system.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None


# ── Defect definitions ─────────────────────────────────────────────────────────

DEFECT_CLASSES = {
    0: {"name": "no_defect", "severity": 0, "pheromone_signal": None},
    1: {"name": "concrete_crack", "severity": 2, "pheromone_signal": "MANGEL_FLAG"},
    2: {"name": "rebar_exposed", "severity": 3, "pheromone_signal": "MANGEL_FLAG"},
    3: {"name": "spalling", "severity": 2, "pheromone_signal": "MANGEL_FLAG"},
    4: {"name": "ppe_missing", "severity": 2, "pheromone_signal": "AUDIT_BEACON"},
    5: {"name": "misalignment", "severity": 1, "pheromone_signal": "MANGEL_FLAG"},
    6: {"name": "water_damage", "severity": 2, "pheromone_signal": "MANGEL_FLAG"},
}


@dataclass
class DefectDetection:
    """A single detected defect in an image."""
    defect_type: str
    confidence: float
    severity: int  # 0-3, higher = worse
    bbox: list[float]  # [x0, y0, x1, y1] normalized 0-1
    pheromone_signal: Optional[str]

    def to_text_tag(self) -> str:
        """Convert to a text tag for pheromone system."""
        confidence_pct = round(self.confidence * 100)
        return f"[{self.defect_type.upper()}, {confidence_pct}%]"


@dataclass
class ImageAnalysisResult:
    """Complete analysis result for one image."""
    filename: str
    image_hash: str
    detections: list[DefectDetection]
    has_defects: bool
    primary_signals: list[str]  # Dominant pheromone signals
    analysis_time_ms: float

    def to_pheromone_input(self) -> dict:
        """Format for ingestion into pheromone system."""
        return {
            "source_image": self.filename,
            "signals": self.primary_signals,
            "defect_count": len([d for d in self.detections if d.pheromone_signal]),
            "max_severity": max((d.severity for d in self.detections), default=0),
        }


# ── Mock detector (for testing without real ONNX models) ──────────────────────

class EdgeDefectDetectorMock:
    """
    Mock detector for demonstration. In production, replace with real ONNX model.
    """

    def __init__(self):
        self.model_name = "YOLOv8-Construction-Mock"

    def analyze_image(self, image_path: str) -> Optional[ImageAnalysisResult]:
        """Analyze a single image for construction defects."""
        try:
            img = Image.open(image_path)
            img_array = np.array(img)
        except Exception:
            return None

        # Mock: simulate detections based on filename hints
        filename = Path(image_path).name.lower()
        detections = []

        # Heuristic: if filename contains keywords, simulate findings
        if "crack" in filename or "damaged" in filename:
            detections.append(DefectDetection(
                defect_type="concrete_crack",
                confidence=0.87,
                severity=2,
                bbox=[0.2, 0.3, 0.5, 0.6],
                pheromone_signal="MANGEL_FLAG",
            ))

        if "rebar" in filename or "exposed" in filename:
            detections.append(DefectDetection(
                defect_type="rebar_exposed",
                confidence=0.92,
                severity=3,
                bbox=[0.1, 0.2, 0.4, 0.8],
                pheromone_signal="MANGEL_FLAG",
            ))

        if "ppe" in filename or "safety" in filename:
            detections.append(DefectDetection(
                defect_type="ppe_missing",
                confidence=0.75,
                severity=2,
                bbox=[0.0, 0.0, 1.0, 0.3],
                pheromone_signal="AUDIT_BEACON",
            ))

        # Always find something for demo purposes (unless "clean" or "ok")
        if not detections and "clean" not in filename and "ok" not in filename:
            detections.append(DefectDetection(
                defect_type="misalignment",
                confidence=0.65,
                severity=1,
                bbox=[0.3, 0.4, 0.7, 0.7],
                pheromone_signal="MANGEL_FLAG",
            ))

        # Compute image hash
        img_hash = hashlib.md5(np.array(img).tobytes()).hexdigest()[:16]

        # Primary signals
        primary_signals = [
            d.pheromone_signal
            for d in detections
            if d.pheromone_signal and d.confidence > 0.6
        ]
        primary_signals = list(dict.fromkeys(primary_signals))  # Deduplicate

        return ImageAnalysisResult(
            filename=Path(image_path).name,
            image_hash=img_hash,
            detections=detections,
            has_defects=len(detections) > 0,
            primary_signals=primary_signals,
            analysis_time_ms=15.0,  # Mock: instant
        )


# ── Real ONNX detector (production) ────────────────────────────────────────────

class EdgeDefectDetectorONNX:
    """
    Real ONNX-based detector. Requires model file and onnxruntime.
    """

    def __init__(self, model_path: str):
        if ort is None:
            raise ImportError("onnxruntime not installed")

        self.model_path = model_path
        try:
            self.session = ort.InferenceSession(model_path)
            self.model_name = Path(model_path).stem
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model: {e}")

    def analyze_image(self, image_path: str) -> Optional[ImageAnalysisResult]:
        """Analyze image using ONNX model."""
        # This is a placeholder for the actual ONNX inference
        # Real implementation would:
        # 1. Load image, resize to model input size
        # 2. Preprocess (normalize, etc.)
        # 3. Run session.run(input_name, {input_data})
        # 4. Post-process outputs (NMS, confidence thresholding)
        # 5. Map to DefectDetection objects
        # For now, return None (requires real model)
        return None


# ── Factory and utilities ──────────────────────────────────────────────────────

def create_detector(use_mock: bool = True, model_path: Optional[str] = None) -> Optional[EdgeDefectDetectorMock | EdgeDefectDetectorONNX]:
    """
    Create a detector instance.
    use_mock=True → mock detector (instant, for testing)
    use_mock=False + model_path → real ONNX detector
    """
    if use_mock:
        return EdgeDefectDetectorMock()

    if model_path and Path(model_path).exists():
        try:
            return EdgeDefectDetectorONNX(model_path)
        except Exception:
            pass

    return None


def analyze_batch(image_paths: list[str], detector: Optional[object] = None) -> tuple[list[ImageAnalysisResult], dict]:
    """
    Analyze a batch of images.
    Returns (results, summary).
    """
    if detector is None:
        detector = create_detector(use_mock=True)

    results = []
    summary = {
        "total": len(image_paths),
        "with_defects": 0,
        "defect_count": 0,
        "primary_signals": [],
        "analysis_time_total_ms": 0.0,
    }

    for path in image_paths:
        result = detector.analyze_image(path)
        if result:
            results.append(result)
            summary["analysis_time_total_ms"] += result.analysis_time_ms

            if result.has_defects:
                summary["with_defects"] += 1
                summary["defect_count"] += len(result.detections)
                summary["primary_signals"].extend(result.primary_signals)

    summary["primary_signals"] = list(dict.fromkeys(summary["primary_signals"]))

    return results, summary


def results_to_pheromone_signals(results: list[ImageAnalysisResult]) -> list[dict]:
    """Convert analysis results to pheromone system input."""
    signals = []
    for result in results:
        if result.has_defects:
            signals.append(result.to_pheromone_input())
    return signals
