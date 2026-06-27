# Local PR #2 Implementation — Complete Guide

**Goal:** Deploy full multimodal RAG locally (no cloud) with 60-75% accuracy on BIM-Leitfaden Q&A.

**Components:**
- ✅ **ColModernVBERT** (250M) — Multimodal embeddings via transformers + MPS
- ✅ **DeepSeek-OCR-2** (3B, FP16) — Extract tables/figures, optimized for Mac
- ✅ **Qwen 2.5 Coder** (7B) — Via Ollama, entity extraction + synthesis
- ✅ **Offline preprocessing** — One-time indexing, unload models after
- ✅ **Fast Q&A runtime** — Instant retrieval, no preprocessing overhead

---

## Quick Start (5 minutes)

### 1. Install Dependencies
```bash
pip install transformers torch accelerate httpx pyyaml pypdfium2
ollama pull qwen2.5-coder:7b
```

### 2. Initialize Models (First Time Only)
```bash
python3 legatum/init_models.py
```

This downloads:
- ColModernVBERT (500MB, cached in ~/.cache/huggingface/)
- DeepSeek-OCR-2 (3.5-6GB, cached, FP16 quantized for Mac RAM)
- Llama 3.1 via Ollama (4.8GB)

**Takes ~10-15 minutes, one-time only.**

### 3. Preprocess Your PDF
```bash
python3 legatum/eval_optimized.py /path/to/document.pdf /path/to/questions.yaml
```

This:
1. **Preprocesses** (10-15 min)
   - Extracts text + tables via DeepSeek-OCR-2
   - Embeds with ColModernVBERT (MPS accelerated)
   - Harvests entities/relations (async windowed)
   - Saves index to `legatum/indexes/{document}.json`

2. **Evaluates** (5 min)
   - Loads index
   - Runs 18 questions through fast Q&A runtime
   - Reports score vs Phase 1 baseline (45%)

### 4. Use Q&A Runtime Directly
```bash
# Interactive mode
python3 legatum/qa_runtime.py legatum/indexes/document.json

# Q: What is BIM?
# A: [grounded answer]
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ OFFLINE (One-time)                                          │
├─────────────────────────────────────────────────────────────┤
│ PDF → DeepSeek-OCR-2 → ColModernVBERT → Entity Extraction  │
│                           ↓                                  │
│                     Multimodal embeddings                   │
│                           ↓                                  │
│                   Save index to disk                        │
│                   (Unload models)                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ RUNTIME (Fast, per question)                                │
├─────────────────────────────────────────────────────────────┤
│ Load index → Hybrid retrieval → Graph grounding → Synthesis │
│  (instant)    (dense+sparse)    (entity matching)  (Qwen)   │
└─────────────────────────────────────────────────────────────┘
```

---

## Expected Performance

| Baseline | Score | Method |
|----------|-------|--------|
| Phase 1 (text-only) | 45% | Simple text search |
| **Local PR #2 (current)** | **60-75%** | Multimodal + OCR |
| Target with 4 improvements | 80%+ | + Hierarchical chunking, Graph RAG, Layout parsing, Self-correction |

---

## Troubleshooting

### ColModernVBERT fails to load
```
❌ ModuleNotFoundError: No module named 'transformers'
```
**Fix:** `pip install transformers torch accelerate`

### DeepSeek-OCR-2 runs out of RAM
```
❌ RuntimeError: CUDA out of memory
```
**Fix:** Already using FP16 quantization. If still failing, reduce batch size in preprocessor.

### Ollama not found
```
❌ FileNotFoundError: ollama command not found
```
**Fix:** Install from https://ollama.ai

### Models already downloaded but want to re-download
```bash
rm -rf ~/.cache/huggingface/models/*colmodernvbert*
rm -rf ~/.cache/huggingface/models/*deepseek-ocr*
python3 init_models.py
```

---

## Files

| File | Purpose |
|------|---------|
| `init_models.py` | Download ColModernVBERT + DeepSeek-OCR-2 |
| `offline_preprocessor.py` | One-time indexing (extract → embed → harvest) |
| `qa_runtime.py` | Fast Q&A (load index → answer) |
| `eval_optimized.py` | Complete pipeline (preprocess + evaluate) |
| `legatum/indexes/{doc}.json` | Preprocessed index (vectors + graph) |

---

## Performance

- **Preprocessing**: 10-15 minutes (one-time per PDF)
- **Q&A latency**: ~30 seconds per question
- **Accuracy target**: 60-75% (vs Phase 1: 45%)

---

## Next: Phase 2 Improvements

Once you hit 60%+, add:

1. **Hierarchical Graph Chunking** (+5%)
   - Parent-child entity structure
   - Macro-relationship linking

2. **Semantic Graph Traversal** (+8%)
   - Convert questions to mini-graphs
   - 1-2 hop neighborhood expansion

3. **Layout-Aware PDF Parsing** (+5%)
   - Markdown tables instead of raw text
   - Explicit entity-to-table linking

4. **Self-Correction (Corrective RAG)** (+3%)
   - Grade retrieved context
   - Trigger secondary search if ambiguous

**Expected:** 60-75% → 80%+ with all improvements

---

## Support

- **ColModernVBERT**: https://huggingface.co/ModernVBERT/colmodernvbert
- **DeepSeek-OCR-2**: https://huggingface.co/deepseek-ai/DeepSeek-OCR-2
- **Ollama**: https://ollama.ai

