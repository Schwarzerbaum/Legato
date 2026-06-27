# LEGATUM Credibility Engine

> NGO fact-checking and anomaly detection for the LEGATUM philanthropic banking platform.

This is the AI verification layer that powers **Layer 3 (BlackSwanX)** of the LEGATUM 9-layer architecture. It cross-references NGO self-reported metrics against public sources (Bundesanzeiger, city social departments, independent field audits) to surface credibility gaps.

## What it does for LEGATUM

- **Graph RAG** — queries a knowledge graph of German nonprofits, SDG alignment, and funding data
- **Corrective RAG** — fact-checks NGO claims by routing low-confidence answers back through verification
- **Anomaly detection** — flags NGOs where self-reported metrics diverge from verified data (e.g. 5,000 vs 800 children served)
- **Pheromone tracking** — stigmergic signal layer marks which NGOs have received multi-source scrutiny
- **Vendor risk** — scores nonprofits on financial transparency, impact consistency, source diversity

## Live anomalies surfaced (in the demo)

| NGO | Claimed | Verified | Discrepancy |
|-----|---------|----------|-------------|
| Initiative Herz e.V. | 5,000 children | 800 children | **6.25×** |
| Digital Refugees BW | 78% employment | 44% employment | **1.77×** |

Sources: Bundesanzeiger Annual Report 2023, Stuttgart City Social Dept, Federal Employment Agency BW.

## Files

| File | Purpose |
|------|---------|
| `graph_rag.py` | Graph-based retrieval over NGO knowledge graph |
| `corrective_rag.py` | Corrective RAG loop — re-queries when confidence < threshold |
| `graph_store.py` | NGO graph persistence and traversal |
| `qa_runtime.py` | Q&A runtime for fact-check queries |
| `pheromones.py` | Stigmergic agent coordination signals |
| `schedule_cascade.py` | Scheduled verification cascade |
| `vendor_risk.py` | NGO credibility scoring (financial transparency, impact consistency) |
| `server.py` | FastAPI server exposing credibility endpoints |
| `legatum_api.py` | LEGATUM-specific API layer (connects to Next.js frontend) |

## Integration with legatum-nextjs

The `/discover` page in the Next.js frontend reads `data/ngos.json` which contains the pre-computed credibility scores and anomaly flags produced by this engine. In production, this would call `legatum_api.py` in real-time.

## Requirements

```bash
pip install fastapi uvicorn httpx transformers torch
# Ollama for local LLM inference (no API keys needed)
brew install ollama && ollama pull qwen2.5-coder:7b
```
