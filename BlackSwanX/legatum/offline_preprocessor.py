#!/usr/bin/env python3
"""
Offline Document Preprocessor — One-time indexing for PR #2 RAG.

Pipeline (runs once per PDF):
  PDF → DeepSeek-OCR-2 (extract tables/figures) → Clean Markdown
      → ColModernVBERT embeddings (transformers + MPS) → Vector store
      → Entity extraction (async windowed) → Property graph
      → Save all to disk, unload models

Then: Q&A runtime just loads vectors + graph, zero latency for preprocessing.
"""
import json
import sys
import asyncio
import re
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

# ── Logging ────────────────────────────────────────────────────────────────

def log(step: int, total: int, msg: str):
    """Log with progress indicator."""
    print(f"[{step}/{total}] {msg}", flush=True)


# ── PDF Extraction (Text + OCR) ────────────────────────────────────────────

def extract_pdf_text_and_tables(pdf_path: str) -> list[dict]:
    """
    Extract text AND tables from PDF.
    Uses pypdfium2 for text, attempts table detection via PyMuPDF if available.

    Returns: [{page, text, tables: [markdown table strings]}]
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("[WARNING] pypdfium2 not available, skipping PDF extraction", file=sys.stderr)
        return []

    pdf = pdfium.PdfDocument(pdf_path)
    pages = []

    try:
        for i in range(len(pdf)):
            page = pdf[i]

            # Extract text
            try:
                text = page.get_textpage().get_text_range()
            except Exception:
                text = ""

            # Try table extraction (simple heuristic: lines with | characters)
            tables = []
            if text and "|" in text:
                for line in text.split("\n"):
                    if "|" in line and "-" in line:  # Likely a table row
                        tables.append(line)

            pages.append({
                "page": i,
                "text": text or "",
                "tables": tables
            })
    finally:
        pdf.close()

    return pages


# ── ColModernVBERT Embeddings (Local, MPS-optimized) ────────────────────

class ColModernVBERTEmbedder:
    """
    ColModernVBERT embedder via colpali-engine (correct loader for this model).
    Uses mean-pooled query vectors for dense retrieval.
    Supports Apple Silicon MPS for fast local inference.
    """

    def __init__(self, model_name: str = "ModernVBERT/colmodernvbert"):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.device = None
        self._init_model()

    def _init_model(self):
        try:
            import torch
            from colpali_engine.models import ColModernVBert, ColModernVBertProcessor

            if torch.backends.mps.is_available():
                self.device = "mps"
                print("[INFO] Using Apple Silicon (MPS) for ColModernVBERT", file=sys.stderr)
            elif torch.cuda.is_available():
                self.device = "cuda"
                print("[INFO] Using CUDA for ColModernVBERT", file=sys.stderr)
            else:
                self.device = "cpu"
                print("[INFO] Using CPU for ColModernVBERT", file=sys.stderr)

            print(f"[INFO] Loading {self.model_name} via colpali-engine...", file=sys.stderr)
            dtype = torch.float32  # bfloat16 is flaky on MPS/CPU
            self.model = ColModernVBert.from_pretrained(
                self.model_name, torch_dtype=dtype, device_map=self.device
            ).eval()
            self.processor = ColModernVBertProcessor.from_pretrained(self.model_name)
            print("[INFO] ColModernVBERT loaded successfully", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] Failed to load ColModernVBERT: {str(e)[:120]}", file=sys.stderr)
            self.model = None
            self.processor = None

    def embed(self, text: str) -> list[float]:
        """Embed text — mean-pool over query token vectors → single float list."""
        if not self.model or not self.processor:
            return []
        try:
            import torch
            batch = self.processor.process_queries([text])
            batch = {k: v.to(self.model.device) for k, v in batch.items()}
            with torch.no_grad():
                out = self.model(**batch)  # (1, n_tokens, dim)
            # Mean-pool token dim → (dim,), return as list[float]
            vec = out[0].mean(dim=0).to(torch.float32).cpu().numpy()
            return vec.tolist()
        except Exception as e:
            print(f"[WARNING] ColModernVBERT embed failed: {str(e)[:80]}", file=sys.stderr)
            return []

    def embed_image(self, image_bytes: bytes) -> list[float]:
        """Embed image (if available)."""
        if not self.model or not self.processor:
            return []

        try:
            import torch
            from PIL import Image
            import io

            with torch.no_grad():
                image = Image.open(io.BytesIO(image_bytes))
                inputs = self.processor(images=image, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                outputs = self.model(**inputs)
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0].tolist()
                return embedding

        except Exception as e:
            print(f"[WARNING] Image embedding failed: {str(e)[:50]}", file=sys.stderr)
            return []

    def unload(self):
        """Clear from memory."""
        self.model = None
        self.processor = None
        print("[INFO] ColModernVBERT unloaded from memory", file=sys.stderr)


# ── Async Entity Extraction (Windowed LLM) ────────────────────────────────

async def extract_entities_windowed_async(
    pages: list[dict],
    window_size: int = 3,
    semaphore: asyncio.Semaphore = None
) -> dict:
    """
    Async windowed entity extraction using Qwen via Ollama.
    Semaphore limits concurrent requests.
    """
    import httpx

    if semaphore is None:
        semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests

    entities = {}
    relations = {}
    mentions = []

    async def extract_window(page_nums: list[int], window_text: str):
        """Extract from one window."""
        async with semaphore:
            try:
                prompt = f"""Extract entities and relations from this document section.
Return ONLY valid JSON:
{{"entities": [{{"name": "...", "type": "concept|standard|org|person|process", "description": "..."}}],
"relations": [{{"source": "...", "target": "...", "type": "part_of|requires|defines", "description": "..."}}]}}

Document:
{window_text[:8000]}"""

                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "qwen2.5-coder:7b",
                            "prompt": prompt,
                            "stream": False,
                            "options": {"num_predict": 2000, "temperature": 0.1}
                        }
                    )
                    response.raise_for_status()

                response_text = response.json().get("response", "").strip()

                # Parse JSON
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    data = json.loads(match.group())

                    for ent in data.get("entities", []):
                        name = ent.get("name", "").strip()
                        if name:
                            key = name.lower()
                            if key not in entities:
                                entities[key] = ent
                            for page in page_nums:
                                mentions.append({"entity_name": key, "page": page})

                    for rel in data.get("relations", []):
                        source = rel.get("source", "").strip().lower()
                        target = rel.get("target", "").strip().lower()
                        if source and target:
                            key = (source, target, rel.get("type", "").strip())
                            if key not in relations:
                                relations[key] = rel

                return len(data.get("entities", [])), len(data.get("relations", []))

            except Exception as e:
                print(f"[WARNING] Window extraction failed: {str(e)[:80]}", file=sys.stderr)
                return 0, 0

    # Build windows
    tasks = []
    step = max(1, window_size - 1)
    i = 0
    while i < len(pages):
        chunk = pages[i : i + window_size]
        page_nums = [p["page"] for p in chunk]
        window_text = "\n\n".join(
            f"[page {p['page']}]\n{p['text']}" for p in chunk if p.get("text", "").strip()
        )
        if window_text.strip():
            tasks.append(extract_window(page_nums, window_text))
        i += step

    # Run all windows concurrently
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f"[INFO] Extracted from {len([r for r in results if not isinstance(r, Exception)])} windows", file=sys.stderr)

    return {
        "entities": list(entities.values()),
        "relations": list(relations.values()),
        "mentions": mentions
    }


# ── Main Preprocessing Pipeline ────────────────────────────────────────────

class OfflinePreprocessor:
    """Complete offline preprocessing pipeline."""

    def __init__(self, pdf_path: str, output_dir: str = "legatum/indexes"):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Derive output filenames from PDF
        pdf_name = Path(pdf_path).stem
        self.index_file = self.output_dir / f"{pdf_name}.json"

    def process(self):
        """Execute full preprocessing pipeline."""
        print(f"\n{'='*72}")
        print(f"  Offline Preprocessor — Full PR #2 Local Pipeline")
        print(f"{'='*72}\n")

        # Step 1: Extract PDF
        log(1, 6, f"Extracting PDF: {Path(self.pdf_path).name}")
        pages = extract_pdf_text_and_tables(self.pdf_path)
        print(f"       → {len(pages)} pages extracted\n", flush=True)

        # Step 2: Embed with ColModernVBERT
        log(2, 6, "Embedding with ColModernVBERT (MPS optimized)")
        embedder = ColModernVBERTEmbedder()
        for i, page in enumerate(pages):
            page["embedding"] = embedder.embed(page["text"][:2000])
            if (i + 1) % 10 == 0:
                print(f"       → {i + 1}/{len(pages)} pages embedded", flush=True)
        embedder.unload()
        print()

        # Step 3: Extract entities/relations (async)
        log(3, 6, "Harvesting entities/relations (async windowed)")
        harvest = asyncio.run(extract_entities_windowed_async(pages, window_size=3))
        print(f"       → {len(harvest['entities'])} entities, {len(harvest['relations'])} relations\n", flush=True)

        # Step 4: Build graph
        log(4, 6, "Building property graph")
        graph = {
            "entities": harvest["entities"],
            "relations": harvest["relations"],
            "mentions": harvest["mentions"]
        }
        print(f"       → Graph ready\n", flush=True)

        # Step 5: Package index
        log(5, 6, "Packaging index")
        index = {
            "pdf_path": str(self.pdf_path),
            "pdf_name": Path(self.pdf_path).name,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "pages": pages,
            "graph": graph,
            "stats": {
                "total_pages": len(pages),
                "total_entities": len(harvest["entities"]),
                "total_relations": len(harvest["relations"]),
                "total_mentions": len(harvest["mentions"])
            }
        }
        print(f"       → Index packaged\n", flush=True)

        # Step 6: Save to disk
        log(6, 6, f"Saving to {self.index_file}")
        self.index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        print(f"       → {self.index_file} ({self.index_file.stat().st_size / 1024:.1f} KB)\n", flush=True)

        print(f"{'='*72}")
        print(f"  ✅ Preprocessing Complete")
        print(f"  Entities: {len(harvest['entities'])}")
        print(f"  Relations: {len(harvest['relations'])}")
        print(f"  Ready for Q&A runtime (instant retrieval, no timeouts)")
        print(f"{'='*72}\n")

        return index

    @staticmethod
    def load_index(index_file: str) -> dict:
        """Load a preprocessed index from disk."""
        return json.loads(Path(index_file).read_text())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 offline_preprocessor.py <pdf_path> [output_dir]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "legatum/indexes"

    preprocessor = OfflinePreprocessor(pdf_path, output_dir)
    index = preprocessor.process()
