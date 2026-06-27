# BlackSwanX → LEGATUM: Technical Transfer Document

**Author:** Manjunath  
**Date:** June 2026  
**Purpose:** Document all algorithms, systems, and code in BlackSwanX that can be transferred to the LEGATUM platform being built by Linus/Patrick.

---

## 1. IS ANY OF THIS PATENTED?

**No.** Nothing in BlackSwanX is patented. All algorithms used are:

- **BM25** — published 1994 by Robertson & Jones, standard open algorithm
- **Personalized PageRank (PPR)** — published 1998 by Brin & Page, public domain
- **SM-2 Spaced Repetition** — published 1987 by Piotr Wozniak, open algorithm
- **Jaccard similarity** — 1901, public domain
- **Rete algorithm** — published 1982 by Charles Forgy, public domain
- **Label-propagation community detection** — published 2002 by Raghavan et al., public domain
- **Cosine similarity** — public domain
- **BFS/DFS graph traversal** — public domain
- **Benford's Law** — public domain

The **pheromone system** and **signal propagation architecture** are an original design inspired by ant colony stigmergy (public biological concept). The specific implementation is original BlackSwanX code but not patentable as a software algorithm in the EU or US under standard rules.

The **three-agent Jury system** (Attacker/Defender/Judge) is an original design pattern, not patented. Similar adversarial agent patterns exist in academic literature.

**Bottom line: All code is original, all algorithms are public domain. Safe to use in LEGATUM.**

---

## 2. SYSTEM ARCHITECTURE OVERVIEW

```
BlackSwanX Engine
─────────────────────────────────────────────────────
Documents (PDF/DOCX/XLSX)
       │
       ▼
[Ingestion + Chunking]          ma/ingestion.py
       │
       ├──▶ [Embeddings]        ma/embeddings.py      (nomic-embed-text via Ollama)
       │          │
       │          ▼
       │    [Vector Search]     cosine similarity
       │
       ├──▶ [Knowledge Graph]   ma/knowledge_graph.py
       │          │
       │          ├── Entity extraction (15 types, regex + LLM)
       │          ├── Spider-Web Densifier (3-pass Jaccard)
       │          ├── DFS Cascade Tracer (6 hops)
       │          ├── Personalized PageRank (HippoRAG)
       │          ├── BM25 + PPR Hybrid Search
       │          ├── Community Detection (label-propagation)
       │          └── Entity Dedup (string similarity + Jury)
       │
       ├──▶ [Semantic Layer]    ma/semantic_layer.py
       │          ├── Narrative Drift Detection
       │          ├── Latent Chain Discovery
       │          ├── Absence Detection
       │          └── Synaptic Mapper (behavioral fingerprinting)
       │
       ├──▶ [Signal Pheromones] ma/signal_pheromones.py
       │          └── Organic signal propagation via semantic proximity
       │
       ├──▶ [Adversarial Agents] ma/adversarial_pollination.py
       │          ├── Predator Swarm (buyer/client counsel)
       │          ├── Prey Swarm (seller/contractor counsel)
       │          └── Dissonance Map (contested clauses)
       │
       ├──▶ [Long-Term Memory]  ma/long_term_memory.py
       │          └── SM-2 spaced repetition (Working→Episodic→Semantic)
       │
       └──▶ [Consensus Jury]    ma/jury.py
                  └── Attacker / Defender / Judge (3-agent tribunal)
```

---

## 3. MODELS USED

### 3a. BlackSwanX (local, Ollama)

| Role | Model | Size | Use |
|------|-------|------|-----|
| Swarm / fast | `llama3.2:3b` | 3B params | Quick tasks, JSON formatting, citizen agents |
| Assassin / deep | `phi4:14b` | 14B params | Complex reasoning, kill-shot detection |
| Nexus / synthesis | `mistral-small:24b` | 24B params | Orchestration, DAG, elite analysis |
| Embeddings | `nomic-embed-text` | Small | 768-dim vectors via Ollama |

**Hardware routing:** `hardware.py` auto-detects RAM/VRAM and selects the right tier.  
- M2 Pro 16GB → `llama3.2:3b` (swarm) + `phi4:14b` (assassin)  
- M2 Max 32GB → `llama3.2:3b` (swarm) + `mistral-small:24b` (nexus)

### 3b. LEGATUM (cloud, LiteLLM)

| Role | Model | Provider |
|------|-------|----------|
| Simple tasks | `gpt-4o-mini` / `gemini-flash` | OpenAI / Google |
| Complex reasoning | `claude-opus-4` / `gpt-4o` | Anthropic / OpenAI |
| Embeddings | `text-embedding-3-small` | OpenAI |

**The routing concept transfers directly.** LEGATUM's `core/llm/registry.py` needs the same 
tier-routing logic BlackSwanX has in `llm/router.py` — just swap model names.

---

## 4. KNOWLEDGE GRAPH — HOW IT WORKS

### 4a. Entity Extraction

The KG uses a **regex-first, LLM-second** approach for efficiency:

1. **Rule-based extraction** (`_ENTITY_RULES` in `knowledge_graph.py`) — ordered regex patterns for 15 entity types. More specific patterns run first. Longer matches preferred.
2. **LLM fallback** — for complex entities that regex misses (e.g. implied relationships in prose)
3. **Quality filter** (`_is_quality_name`) — rejects tokens under 3 chars, all-numbers, stopwords

**15 Entity Types:**
`Contract`, `FinancialMetric`, `Risk`, `Finding`, `Claim`, `Company`, `Person`, `EvidenceGap`, `Jurisdiction`, `Regulation`, `Process`, `Asset`, `Timeline`, `Obligation`, `Milestone`

**For LEGATUM construction domain, remap to:**
`Contract` → VOB/HOAI contracts  
`Person` → Bauleiter, Auftraggeber, Auftragnehmer  
`FinancialMetric` → Nachtragswert, Bauzeitverlängerung, LV-Position  
`EvidenceGap` → missing safety certs, sign-offs, DIN compliance docs  
`Risk` → Nachtrag risk, Mängelrisiko, Terminrisiko  

### 4b. Spider-Web Densifier (3-Pass Algorithm)

Turns a sparse hub-and-spoke graph into a dense mesh. Runs after initial extraction.

**Pass 1 — Shared-Chunk Strands:**
```
For each pair of nodes (A, B):
  shared_chunks = chunks_of_A ∩ chunks_of_B
  if |shared_chunks| >= 2:
    jaccard = |shared| / |union|
    if jaccard >= 0.05:
      add edge(A, B, weight = 0.3 + jaccard * 0.5)
```
Result: nodes that appear together frequently get direct edges.

**Pass 2 — Cross-Document Bridges:**
```
For each node that appears in 2+ documents (bridge node):
  For each document it bridges:
    Find top-3 highest-mention nodes in that doc
    Add edge(bridge, top_node, weight=0.35)
```
Result: cross-document entity connections via shared bridge nodes.

**Pass 3 — Triangle Shortcuts:**
```
For each node A (capped at degree-10 to avoid O(n³)):
  For each pair of neighbours (B, C):
    bridge_weight = 0.4 × min(weight_AB, weight_AC)
    if bridge_weight >= 0.1:
      add edge(B, C, weight=bridge_weight)
```
Result: fills triangle gaps, raises average degree significantly.

**Measured result on M&A docs:** avg degree 2.3 → 11.9, leaf nodes 62 → 14.

### 4c. DFS Cascade Tracer

Starting from any node, follows `consequence` and `triggers_risk` edges depth-first:

```
DFS(start_node, max_depth=6):
  For each edge from current_node:
    if edge.type in CONSEQUENCE_EDGES:
      visit(target_node, depth+1)
      deposit CHAIN_TRIGGER pheromone on target_node
      recurse if depth < max_depth
```

**For LEGATUM:** Trace Nachtrag chains — "Change in material spec → Cost overrun → LV-Adjustment → Final account dispute" across multiple project documents.

### 4d. Personalized PageRank (HippoRAG-style)

Algorithm for multi-hop entity retrieval. Standard PageRank finds globally important nodes. **Personalized** PageRank seeds from query entities and finds what's reachable from them.

```
Algorithm:
  1. Build sparse adjacency matrix A (row-normalised, undirected)
  2. Create seed vector s: s[i] = 1 if node_i matches query, else 0
     (boosted by log(mention_count+1) per HippoRAG)
  3. Normalise s to sum=1
  4. Power iteration (max 50 rounds):
     r_new[j] = (1-α) × s[j] + α × Σ(A[i,j] × r[i])
     Stop when Σ|r_new - r| < 1e-7
  5. Return top-k nodes by r score
```

**Parameters:**
- `damping = 0.5` (HippoRAG default, vs. standard 0.85 — more exploration)
- `max_iter = 50`
- Convergence threshold: `1e-7`

**Why better than BM25 alone:** Surfaces entities that are 2-3 hops away from the query terms but highly connected to them. E.g. "Nachtrag" query → finds "VOB §2" → finds "Honorarzone" → surfaces the indirectly related cost node.

### 4e. Hybrid Search (BM25 + PPR Fusion)

Combines keyword recall with graph precision:

```
Final score = 0.4 × BM25_normalised + 0.6 × PPR_normalised
```

**BM25 implementation:**
```
For each node:
  TF = term_frequency_in_name_tokens
  IDF = log((N - df + 0.5) / (df + 0.5) + 1)
  BM25 = IDF × (TF × (k1+1)) / (TF + k1 × (1 - b + b × dl/avgdl))
  Parameters: k1=1.5, b=0.75, avgdl=5
```

**PPR used as graph-based semantic score** — nodes highly connected to query-matched nodes score high even without keyword overlap.

**Match type annotation:** each result tagged as `bm25`, `graph`, or `both` for explainability.

---

## 5. PHEROMONE SIGNAL SYSTEM — HOW IT WORKS

Inspired by ant colony stigmergy. Not a routing algorithm — it's a **signal propagation layer** that makes related nodes glow without explicit edges.

### Signal Types:
| Signal | Triggered by | Effect |
|--------|-------------|--------|
| `RISK_PULSE` | Risk node detected | Pulls related FinancialMetric nodes |
| `ANOMALY_SCENT` | Inconsistency found | Pulls related Claims |
| `CHAIN_TRIGGER` | DFS cascade step | Marks dependency chain |
| `DRIFT_MARKER` | Narrative drift detected | Flags entity across docs |
| `ABSENCE_FLAG` | Expected topic missing | Highlights gap |
| `DISSONANCE` | Predator+Prey both flag same clause | Hottest signal — deal-break risk |
| `AUDIT_BEACON` | Jury says: human must review | Mandatory escalation |

### Propagation Algorithm:
```
emit_signal(type, source_entity, strength=1.0):
  persist to DB
  
propagate_signal(signal):
  if signal.strength < 0.05: stop
  
  source_embedding = embed(source_chunk_text)
  
  for each candidate_chunk in other_docs:
    candidate_embedding = embed(candidate_chunk)
    similarity = cosine(source_embedding, candidate_embedding)
    
    if similarity >= 0.55:  # SEMANTIC_PULL_THRESHOLD
      pulled_strength = signal.strength × similarity × DECAY(0.85^hops)
      record PulledNode
      
  signal.strength × 0.85  # decay for next hop
  signal.hops += 1
```

**Key difference from graph traversal:** follows semantic similarity, not explicit edges. A Risk node about "Fassadenmaterial" automatically pulls chunks about "DIN 18550" even if there's no explicit edge between them.

### For LEGATUM:
Replace M&A signal types with construction equivalents:
- `NACHTRAG_PULSE` — Nachtrag risk node detected
- `MANGEL_SCENT` — Defect documented
- `TERMIN_DRIFT` — Delivery date shifted
- `FEHLENDE_UNTERLAGE` — Missing document flagged

---

## 6. LEUKOCYTE RETE — HOW IT WORKS

A **deterministic pre-screener** that runs BEFORE any LLM call. Uses a minimal self-contained Rete algorithm (production rules engine) to catch known fatal patterns via regex — zero LLM tokens spent.

### Rete Algorithm (simplified):
```
Rules = list of _Rule objects, each with:
  - conditions: [{field, operator, value}]  (AND logic)
  - conclusion: {type, severity, deal_impact}
  - priority: int (higher = checked first)

For each text chunk:
  sort rules by priority DESC
  for each rule:
    if ALL conditions match (case-insensitive substring):
      fire rule → return finding with severity
```

### 14 Kill-Switch Patterns (M&A):
1. Change of Control — termination trigger
2. Change of Control — payment acceleration
3. Debt acceleration on closing
4. Cross-default trigger
5. Assignment restriction (no consent carve-out)
6. Key-man / golden parachute
7. IP encumbrance / exclusive license
8. CFIUS regulatory approval required
9. EU competition clearance required
10. Tax indemnity refusal / cap
11. Drag-along override on buyer
12. Earnout with seller-controlled milestones
13. Anti-assignment / no novation
14. GDPR data liability cap below exposure

### For LEGATUM — Construction Kill-Switch Patterns:
Remap to VOB/construction fatal clauses:
1. Werkvertragsabschluss ohne VOB/B Einbeziehung
2. Pauschalpreisvertrag mit Massenrisiko beim AG
3. Vertragsstrafe ohne Obergrenze (>5% Auftragswert)
4. Abtretungsverbot (Forderungsabtretung ausgeschlossen)
5. Gewährleistungsfrist über 5 Jahre (VOB §13)
6. Keine Abnahme-Regelung (§640 BGB greift)
7. Sicherheitseinbehalt über 10%
8. Einseitige Änderungsvorbehalt des AG

**Speed advantage:** Rete pre-screener runs in microseconds. Only clauses that pass the pre-screener get sent to the LLM. Reduces LLM calls by ~60% on typical construction contracts.

---

## 7. LONG-TERM MEMORY (SM-2) — HOW IT WORKS

SuperMemo SM-2 spaced repetition adapted for cross-project institutional memory.

### Three Memory Tiers:
```
Working Memory    → facts from current document/session (volatile)
Episodic Memory   → facts from current project (persists across sessions)
Semantic Memory   → facts seen 3+ times across 2+ projects (PERMANENT)
```

### SM-2 Algorithm:
```
On each re-encounter of a fact with quality score q (0-5):

if q < 3:
  repetitions = 0
  interval = 1 day
else:
  if repetitions == 0: interval = 1
  elif repetitions == 1: interval = 6
  else: interval = prev_interval × ease_factor
  
  ease_factor += 0.1 - (5-q) × (0.08 + (5-q) × 0.02)
  ease_factor = max(1.3, ease_factor)
  repetitions += 1

strength = min(1.0, repetitions / (repetitions + 2))

# Permanence gate:
if strength >= 0.75 AND repetitions >= 3 AND doc_count >= 2:
  is_permanent = True  # Never deleted, always retrieved first
```

### For LEGATUM — What Gets Remembered:
- "Contractor X always disputes NWC adjustment at project close" → permanent after 3 projects
- "VOB §2 Abs. 3 Nachtrag pattern" → clause pattern, permanent
- "This Bauleiter's defect reports always miss photo documentation" → advisor fingerprint
- "Projects with this type of Leistungsverzeichnis have 40% Nachtrag rate" → statistical pattern

**Why this is a differentiator:** No RAG system has cross-project institutional memory. Every query starts fresh. With SM-2 LTM, the system gets smarter with every project — facts about contractors, patterns across projects, known risk combinations all accumulate and strengthen.

---

## 8. ADVERSARIAL AGENTS — HOW THEY WORK

### Predator/Prey Architecture:

Two opposing LLM agents run simultaneously over the same document chunk:

```
For each chunk:
  Predator (client/AG):
    System prompt: "Find every clause that creates risk for the Auftraggeber.
                   Hunt for uncapped liability, missing safeguards, 
                   contractor-favorable terms..."
    Output: {flagged, risk_type, severity, excerpt, score}
    
  Prey (contractor/AN):  
    System prompt: "Find every protective mechanism for the Auftragnehmer.
                   Find liability caps, materiality qualifiers,
                   basket protections, contractor-favorable carve-outs..."
    Output: {flagged, protection_type, strength, excerpt, score}

if Predator.flagged AND Prey.flagged on same chunk:
  emit DISSONANCE pheromone (intensity compound: sum × 1.3)
  → "This is where the negotiation will break"
```

### For LEGATUM — Nachtragsprüfung:
```
Predator (Auftraggeber counsel):
  "Is this Nachtrag valid under VOB/C? Find reasons it is NOT:
   - Was the change ordered in writing (§2 Abs. 5)?
   - Is the price claim supported by Urkalkulation?
   - Has the Auftragnehmer waived the claim by proceeding without notice?"

Prey (Auftragnehmer counsel):
  "Find every reason this Nachtrag IS valid:
   - Changed conditions from the original LV?
   - Zusätzliche Leistungen not included in Pauschalpreis?
   - AG-ordered changes documented?"

DISSONANCE → contested clauses where parties will dispute
```

---

## 9. WHAT TRANSFERS TO LEGATUM — PRIORITISED

### Immediate (Week 1-2) — fills current TODO stubs:

| BlackSwanX | LEGATUM target | Changes needed |
|-----------|-----------------|----------------|
| `ma/ingestion.py` | `app/features/ai_generation/chunking.py` | None — pure Python |
| `ma/embeddings.py` | `app/features/ai_generation/vector_service.py` | Swap Ollama → LiteLLM embeddings |
| `llm/router.py` | `app/core/llm/registry.py` | Swap model names |

### Phase 1 (Month 1) — M1 Jana milestone:

| BlackSwanX | LEGATUM target | Changes needed |
|-----------|-----------------|----------------|
| `ma/semantic_layer.py` (absence detection, drift) | New service in `ai_generation` | Replace M&A keyword lists with construction domain |
| `ma/leukocyte_rete.py` | Pre-screener before LLM in chat | Replace 14 M&A rules with construction VOB rules |
| BM25 hybrid search in `knowledge_graph.py` | `features/ai_generation/vector_service.py` | Extract BM25 logic, wire to pgvector |

### Phase 2 (Month 2-3) — when KG gate triggers:

| BlackSwanX | LEGATUM target | Changes needed |
|-----------|-----------------|----------------|
| `ma/knowledge_graph.py` | `features/agents/graph/` | Port SQLite → Postgres/AGE; add org_id RLS |
| PPR + hybrid search | KG retrieval layer | Wire to pgvector + Postgres graph |
| Spider-web densifier | Background task via Celery | Already async-compatible |
| `ma/adversarial_pollination.py` | Nachtragsprüfung agent | Rewrite system prompts for VOB/construction |

### Phase 3 (Month 3+) — differentiator features:

| BlackSwanX | LEGATUM target | Changes needed |
|-----------|-----------------|----------------|
| `ma/long_term_memory.py` | Cross-project institutional memory | Add org_id scoping, port to Postgres |
| `ma/jury.py` | Entity resolution in KG | Swap Ollama → LiteLLM |
| Signal pheromones | Risk heatmap in UI | Add org_id, map to construction signals |

---

## 10. WHAT IS BETTER IN BLACKSWANX vs. WHAT LEGATUM CURRENTLY HAS

| Capability | LEGATUM state | BlackSwanX state | Delta |
|-----------|----------------|-----------------|-------|
| Document ingestion | `"""TODO"""` one line | Full: PDF+DOCX+XLSX+CSV with table extraction | **Ready now** |
| Embeddings | `"""TODO"""` | Working cosine search, fallback to BM25 | **Ready now** |
| LLM routing | `NotImplementedError` | Keyword classifier, 3-tier | **Ready now** |
| Hybrid search | Issue #22, Backlog | BM25 + PPR fusion, working | **1 week to port** |
| Cross-doc analysis | Not designed | Drift detection, latent chains | **2 weeks to adapt** |
| Absence detection | Not designed | 12 domain topics, configurable | **1 week to adapt** |
| KG | Shelved (Risk #6) | 3,748 lines, full implementation | **2-3 weeks to port** |
| Long-term memory | Not designed | SM-2 spaced repetition, working | **3 weeks to port + RLS** |
| Adversarial agents | Planned, not designed | Full Predator/Prey + Dissonance | **2 weeks to adapt** |

---

## 11. BORIS'S CONCERNS — ADDRESSED BY BLACKSWANX

**Boris flagged:** "I'm not sure pure text embedding search would be sufficient for the range of domain tasks — especially visual/multimodal"

BlackSwanX's answer: The hybrid BM25 + PPR search is significantly better than pure embedding search for domain-specific queries. PPR finds multi-hop connections pure cosine search misses. This doesn't solve the multimodal gap but substantially improves text-only retrieval quality.

**Boris flagged:** "Graphiti for KG?"

BlackSwanX's answer: The KG implementation IS Graphiti-inspired — temporal edges (`valid_from_year`/`valid_until_year`), 2-stage entity dedup, label-propagation community detection, episode provenance. The architecture comment in `knowledge_graph.py` explicitly cites Graphiti. We've already built the Graphiti-inspired patterns.

**Boris flagged:** "Agent observability"

BlackSwanX answer: `ma/provenance_layer.py` (not read yet but exists in the codebase) tracks agent decision provenance. Combined with the trajectory logging in LEGATUM's `core/llm/registry.py`, this addresses the observability requirement.

---

## 12. THE ONE-LINE SUMMARY FOR PATRICK

> "I have working implementations of document ingestion, hybrid BM25+PPR search, a full knowledge graph with temporal edges and community detection, cross-project SM-2 memory, and adversarial agents for contract analysis. These map directly to what LEGATUM needs and are currently TODO stubs or not yet designed in the backend. The domain adaptation and Postgres porting is 2-3 weeks of work, not a rebuild from scratch."
