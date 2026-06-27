# LEGATUM — Call Briefing Document
**Manjunath | LBBW Founding Team**
**Date: June 2026**

---

## Context: What I Said Last Time

I told Patrick I had built something with overlap to what LEGATUM needs:
- Working knowledge graph
- Hybrid BM25 + embedding search
- Adversarial agents (both sides of a clause)
- Absence detection

**What I've done since: I built it for construction specifically.**

Not just adapted the M&A codebase. Built 7 new domain-specific modules from scratch,
grounded in VOB/B, GAEB, DIN standards, and German construction law.
It runs at http://localhost:9200. I can demo it live.

---

## What We Built — 7 Modules

---

### 1. Nachtragsprüfung Engine
**File:** `legatum/nachtrag_engine.py`

**What it does:**
Feed it a Nachtrag claim (text + claim value + LV context + correspondence).
It outputs a Financial Risk Exposure Score, settlement range in EUR,
and a legal recommendation — without a lawyer.

**How it works:**
- 6 VOB/B procedural rules run deterministically first (zero LLM, instant)
  - Was there a schriftliche Anordnung? (VOB/B §2 Abs. 5)
  - Was the Bedenkenanzeige filed on time? (VOB/B §4 Abs. 3)
  - Is this a Pauschalvertrag? (VOB/B §2 Abs. 7)
  - Was Ankündigung der Mehrvergütung given before execution?
  - Was a joint Aufmaß created? (VOB/B §14 Abs. 2)
  - Was Nachtrag claimed after Abnahme? (§640 BGB)
- If Ollama is running: AN agent and AG agent then argue the claim in parallel
- Verdict: APPROVE_FULL / APPROVE_PARTIAL / NEGOTIATE / REJECT / ESCALATE_LAWYER

**Models used:** llama3.2:3b via Ollama (local, optional). Procedural analysis needs no model.

**Why novel:** Standard RAG returns documents about Nachträge.
This actually tells you whether a specific Nachtrag is legally valid and for how much.

---

### 2. Adversarial Clause Analysis
**File:** `backend/api/legatum.py` (adversarial endpoint)

**What it does:**
Any contract clause gets argued by two opposing AI agents simultaneously.
AN counsel (Auftragnehmer) maximizes the claim.
AG counsel (Auftraggeber) weaponizes documentation gaps.
Where both flag the same clause = DISSONANCE = contested zone.

**Modes:**
- Nachtrag Claim (VOB/B §2)
- Mängelrüge (VOB/B §13)
- Vertragsstrafe (VOB/B §5)

**How it works:**
- Deterministic pattern matching first (no LLM): checks for key VOB/B phrases
- Optional LLM layer if Ollama running: full argumentation
- Dissonance score shows which clauses will cause negotiation breakdown

**Models used:** llama3.2:3b via Ollama (optional). Deterministic layer needs no model.

---

### 3. Institutional Vendor Risk Index
**File:** `legatum/vendor_risk.py`

**What it does:**
Cross-project behavioral memory for contractors and subcontractors.
If Mustermann Tiefbau claimed Baugrundrisiko on 3 different projects,
that pattern becomes permanent institutional memory and surfaces the next time
you're about to sign a contract with them.

**How it works — SM-2 Spaced Repetition:**
Same algorithm behind Anki flashcards, adapted for contractor behavior.

Memory tiers:
- Working → current project (volatile)
- Episodic → within one client portfolio
- Semantic → cross-project, PERMANENT (strength ≥ 0.75, 3+ projects)

6 behavioral pattern types tracked:
- baugrundrisiko_serial — repeatedly claims unexpected ground conditions
- claim_maximizer — Nachtrag on every ambiguity
- delay_claimer — systematic Behinderungsanzeigen
- documentation_avoider — habitually incomplete Aufmaß/Protokolle
- quality_risk — repeated Mängel at Abnahme
- reliable_contractor — positive pattern (reduces contingency recommendation)

**Output:** Procurement check before signing = risk score 0-100 +
contingency EUR recommendation + procurement flags.

**Models used:** None. Fully deterministic.

**Why novel:** No construction AI has cross-project contractor behavioral memory.
This knowledge currently lives only in the heads of experienced project managers
and walks out the door when they retire.

---

### 4. Schedule-Aware Risk Cascade
**File:** `legatum/schedule_cascade.py`

**What it does:**
Input a delay (e.g. concrete pouring delayed 14 days).
Get the full downstream cascade along the CPM schedule:
which trades are affected, by how many days, estimated EUR exposure per trade,
and the Behinderungsanzeige deadline.

**How it works:**
Signal strength formula:
  strength_B = strength_A × schedule_proximity(A,B) × DECAY^hops

Key insight: for direct schedule predecessors (A → B in CPM),
text similarity is irrelevant — the schedule dependency IS the connection.
"Betonage" and "Trockenbau" share zero vocabulary but are causally linked.

Schedule proximity:
- Direct predecessor in CPM → 1.0 (full strength)
- Same trade family → 0.7-0.9
- Adjacent trade in construction sequence → 0.3-0.5

VOB/B §6 rights triggered automatically:
- Any delay → Bauzeitverlängerung right
- >7 days → §6 Abs. 6 Schadensersatz right
- Behinderungsanzeige deadline = 3 days from recognition

**Models used:** None. Fully deterministic.

**Demo result:** 14-day concrete delay → 4 trades affected → EUR 18,760 exposure
→ critical path impact → Behinderungsanzeige deadline calculated.

---

### 5. Cross-Document Contractual Mesh
**File:** `legatum/contractual_mesh.py`

**What it does:**
Builds a deterministic legal graph from construction documents.
Not based on text similarity — based on structural legal relationships.

**3 passes:**

Pass 1 — Document Hierarchy:
Hauptvertrag → Anlage → LV → Nachtrag → Rechnung
Edges: parent_of, amends, supplements

Pass 2 — GAEB Positionsnummer Linking:
Same position number (e.g. 05.02.001) in LV + Nachtrag + Rechnung
= deterministic edge, weight 1.0, no probability.
Enables: "Show me everything related to Position 05.02.001 across all documents"

Pass 3 — VOB/B + DIN Standard Resolution:
Any doc citing VOB/B §13 connects to a canonical VOB/B §13 node.
Any doc citing DIN 18300 connects to a canonical DIN 18300 node.
Enables: "Show me all contracts governed by VOB/B §13 Abs. 4 across all projects"

**Models used:** None. Fully deterministic regex-based.

**Why novel:** Standard KGs connect text chunks by similarity.
This connects legal documents by their actual contractual relationships.
Every edge has a legal meaning.

---

### 6. Legal-Twin Knowledge Graph
**File:** `legatum/legal_kg.py`

**What it does:**
The full 3-dimensional KG that embeds hierarchy, time, and regulation
natively into its mathematical structure.

**3 dimensions:**

Hierarchy (GAEB deterministic tree):
Documents anchor to GAEB position codes, not just to text chunks.

Time (asymmetric temporal edges):
Every node and edge carries valid_from / valid_until.
Enables retroactive queries: "What was the contractual relationship between
concrete supplier and general contractor on March 12, before Amendment 2?"

Regulation (DIN/VOB/B auto-binding):
11 construction activity → DIN/VOB/B mappings.
"Erdarbeiten" in any document → automatically connected to DIN 18300
+ VOB/C ATV DIN 18300 + liability note. Zero LLM, instant.

**3 structural passes:**

Pass 1 — Parent-Child Inheritance:
Nachtrag automatically inherits Vertragsstrafe, Gewährleistung,
Sicherheitseinbehalt, Abtretungsverbot, Versicherung from parent contract
UNLESS explicitly overridden.

Pass 2 — Regulatory Auto-Binding:
Any mention of "Betonarbeiten" → instant edge to DIN 18331, DIN EN 206,
DIN 1045, VOB/C ATV DIN 18331. No LLM. 100% deterministic.

Pass 3 — Triangle Transitivity (Shared Risk Interface):
If Party A and Party B are both bound to VOB/B §13 (Gewährleistung),
a "shared_risk_interface" edge is inferred between them.
Means: they share a legal obligation they may not know about.

**Tribunal Entity Deduplication:**
3-agent judicial loop for entity resolution.
- Prosecutor: argues "Müller GmbH" and "Müller Beton" are DIFFERENT
- Defense: argues they are the SAME entity
- Judge: weighs evidence, writes verdict
- SHA-256 audit hash of entire decision — legally traceable, immutable
- Verdict options: merge / separate / needs_human

**Visualization:**
D3.js force-directed graph. Node sizes scale with connection count.
Stats bar: entities / connections / inherited edges / regulatory bindings / risk interfaces.
Two views: Entity Graph (interactive) / Top Nodes (ranked list).
Hover tooltip with entity details.

**Models used:** None for graph construction. Optional Ollama for Tribunal
LLM enhancement (deterministic structural evidence used as fallback).

---

### 7. Construction Signal Pheromone System
**File:** `legatum/pheromones.py`

**What it does:**
Stigmergic signal propagation across construction documents.
Agents deposit typed signals on document entities.
When 3+ signals hit the same node, intensities compound ×1.3 —
that document glows hot on the heat map.
Tells you where to look first without reading everything.

**7 signal types:**
- NACHTRAG_RISK — Nachtrag claim detected
- BEHINDERUNG — Behinderungsanzeige trigger (VOB/B §6)
- MANGEL_FLAG — Defect documented (VOB/B §13)
- TERMIN_DRIFT — Schedule date shifted
- FEHLENDE_UNTERLAGE — Required document missing
- VERTRAGSSTRAFE_RISK — Penalty clause may trigger
- AUDIT_BEACON — Legal dispute, mandatory human review

**How propagation works:**
1. Scan document for signal keywords (deterministic, no LLM)
2. Source document gets full signal strength deposited on itself
3. Signal propagates to semantically similar documents (keyword Jaccard similarity)
4. Decay rate: 0.85 per hop, threshold: 0.15 similarity
5. When node accumulates 3+ signals: intensity ×1.3 compound boost

**Output:** Heat map with intensity bars, color-coded by dominant signal.
Compound nodes (🔥) = highest priority.

**Models used:** None. Fully deterministic.

**Demo result (5 docs):**
Behinderungsanzeige_Elektro.pdf 🔥 intensity 3.36 (compound, 3 signals)
Email_Vertragsstrafe.pdf intensity 1.94 (AUDIT_BEACON)
Nachtrag_003.pdf intensity 1.00 (NACHTRAG_RISK)

---

## Models Used — Summary

| Feature | Model | Provider | Required? |
|---------|-------|----------|-----------|
| Nachtragsprüfung (full) | llama3.2:3b | Ollama (local) | Optional |
| Nachtragsprüfung (procedural) | None | — | Always works |
| Adversarial agents (full) | llama3.2:3b | Ollama (local) | Optional |
| Adversarial agents (pattern) | None | — | Always works |
| Tribunal (enhanced) | llama3.2:3b | Ollama (local) | Optional |
| Tribunal (structural) | None | — | Always works |
| All other modules | None | — | Always works |

**The entire system works without Ollama/any LLM.**
LLM layers add richer argumentation but are optional enhancements.

---

## How This Maps to LEGATUM's Backlog

Looking at legatum-backend GitHub issues (#23–#26 in Backlog, no MVP label):

| legatum-backend issue | BlackSwanX/legatum equivalent | Status |
|------------------------|--------------------------------|--------|
| #23 Embeddings + RAG index | `ma/embeddings.py` (working) | Ready to port |
| #24 Load RAG context into chat | `ma/semantic_layer.py` | Ready to adapt |
| #25 Chat session + history | Partially in `ma/knowledge.py` | Needs FastAPI wiring |
| #26 RAG-Query endpoint | `ma/semantic_layer.py` search | Ready to port |
| #22 Hybrid search | `knowledge_graph.py` BM25+PPR | Working |
| #33 Agent runtime | All 7 modules above | Working |
| Not in any issue | Nachtragsprüfung Engine | Novel — not planned yet |
| Not in any issue | Vendor Risk Index | Novel — not planned yet |
| Not in any issue | Schedule Cascade | Novel — not planned yet |
| Not in any issue | Legal-Twin KG | Novel — not planned yet |
| Not in any issue | Pheromone Heat Map | Novel — not planned yet |

**The 5 novel modules I built don't exist anywhere in the current backlog.**
They are the differentiation layer — what makes LEGATUM defensible against
generic RAG competitors.

---

## What to Say on the Call

1. "I said I had something relevant. Here it is — running at localhost:9200."

2. "7 modules, all grounded in VOB/B, GAEB, DIN. Not generic AI — construction-specific."

3. "The 5 novel ones aren't in your backlog at all. Nachtragsprüfung Engine,
   Vendor Risk Index, Schedule Cascade, Legal-Twin KG, Pheromone Heat Map.
   These are the differentiators. No competitor can copy this quickly."

4. "4 of your backlog issues (#23–#26 — the RAG chain with no MVP label)
   have working implementations I can port. That's weeks of build time collapsed."

5. "The whole system runs without any LLM or API key. Everything deterministic
   falls back gracefully. No OpenAI cost, no GDPR risk in the pipeline itself."

6. "Where is Phase 0 right now? I want to know where I can plug in immediately."

---

## Files Built

```
legatum/
├── nachtrag_engine.py      # VOB/B Nachtragsprüfung (deterministic + LLM)
├── vendor_risk.py          # SM-2 contractor behavioral memory
├── schedule_cascade.py     # CPM delay propagation
├── contractual_mesh.py     # GAEB + VOB/B deterministic graph
├── legal_kg.py             # 3D Legal-Twin KG + Tribunal
├── pheromones.py           # Signal pheromone heat map
├── dashboard.html          # Full UI (7 tabs, D3 graph)
├── server.py               # FastAPI standalone server
├── INNOVATIONS.md          # Architecture proposal document
└── BLACKSWANX_TO_LEGATUM.md  # Transfer analysis

docs/
└── BLACKSWANX_TO_LEGATUM.md  # Full algorithm documentation
```

**Total: ~3,500 lines of original Python + ~1,200 lines of dashboard HTML/JS**
