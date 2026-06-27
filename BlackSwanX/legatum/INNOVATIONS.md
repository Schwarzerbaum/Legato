# LEGATUM — Novel Architecture Proposals
**Author:** Manjunath  
**Date:** June 2026  
**Status:** Proposal — for discussion with Patrick & Linus

These are domain-specific transformations of BlackSwanX's existing algorithms into 
genuinely novel systems for the German construction AI market. Each one takes a known 
algorithm and grounds it in construction law, process, and legal structure in a way 
no generic RAG system does.

---

## 1. Cross-Document Contractual Mesh
*(Replaces: generic Spider-Web Densifier using text Jaccard)*

### What the basic algo does
Standard graph densification using text-chunk Jaccard similarity — two nodes get an 
edge if they appear in the same chunks often enough. Domain-agnostic.

### What makes this novel
In construction, documents have an **implicit hierarchical and legal relationship** that 
generic similarity cannot see:

```
Hauptvertrag (Main Contract)
  └── Leistungsverzeichnis (BoQ)
        └── Position 03.01.002 (specific line item)
              └── Nachtrag #7 (modifies this position)
                    └── VOB/B §2 Abs. 5 (legal basis)
                          └── DIN 18550 (technical standard referenced)
```

A generic Jaccard edge between "Nachtrag" and "DIN 18550" has no legal weight.  
A **structural edge** `modifies_clause → governed_by → references_standard` is 
deterministic and legally meaningful.

### Implementation approach

**Pass 1 — Document Hierarchy Mapping:**
Parse the document type and establish parent-child relationships:
- Hauptvertrag → Anlage → Leistungsverzeichnis → Nachtrag
- Edge type: `parent_of`, `amends`, `supplements`
- Weight: structural position, not similarity

**Pass 2 — GAEB Positionsnummer Linking:**
GAEB (German standard for BoQ exchange) uses standardized item numbers like `03.01.002`.
When the same Positionsnummer appears across a Nachtrag, a Rechnung, and the original LV:
- Create deterministic edges between those nodes
- Edge type: `references_position`, weight: 1.0 (exact match, not probabilistic)
- No LLM needed — pure structured data extraction

**Pass 3 — VOB/B + DIN Standard Resolution:**
When a clause cites VOB/B §X or DIN XXXXX:
- Resolve to a shared canonical node (the standard itself)
- All contracts citing the same standard are now connected through it
- Enables: "Show me all clauses across all projects governed by VOB/B §13 Abs. 4"

### Result
The graph becomes a **deterministic legal twin** of the construction project's actual 
contractual skeleton — not a probabilistic similarity network. Every edge has a legal 
meaning. Every path through the graph corresponds to a real legal dependency chain.

---

## 2. Automated Claim/Defense Simulation (Nachtragsprüfung Engine)
*(Replaces: generic Adversarial Pollination with Predator/Prey)*

### What the basic algo does
Two LLM agents with opposing system prompts debate a document chunk. Dissonance 
detected when both flag the same clause. Domain-agnostic — works for any contract type.

### What makes this novel
This becomes a **pre-litigation risk engine** grounded strictly in VOB/B and HOAI law.

### Agent A — The Contractor (AN)
Maximizes claim value by finding:
- Ambiguities in original Bausoll (what was actually specified?)
- Changed conditions from what was tendered (Baugrundrisiko §4 Abs. 1)
- Additional services not covered by Pauschalpreis
- AG-ordered changes without formal Anordnung

Prompt is grounded in: **VOB/B §2, §4, §6, §13**

### Agent B — The Client/Architect (AG)
Weaponizes documentation gaps:
- "Bedenkenanzeige not submitted within the required window"
- "Nachtrag submitted after Abnahme — §640 BGB applies, not VOB"
- "No written Anordnung exists — §2 Abs. 5 claim fails"
- "Price was agreed as Pauschalvertrag — no Aufmaß basis"

Prompt is grounded in: **VOB/B §2 Abs. 3, §12, §13, §14, §16**

### The Novel Output: Financial Risk Exposure Score
Instead of just "both sides flagged this" → output a structured risk assessment:

```json
{
  "nachtrag_id": "N-007",
  "claim_value": 48500,
  "contractor_position_strength": 0.72,
  "client_position_strength": 0.41,
  "decisive_factor": "Written Anordnung exists (§2 Abs. 5 satisfied)",
  "documentation_gaps": ["Bedenkenanzeige missing", "Aufmaß not countersigned"],
  "likely_outcome": "Partial — approx. 60-70% of claim value",
  "estimated_exposure": { "min": 28000, "max": 38000 },
  "recommendation": "Settle before arbitration — documentation gap is recoverable"
}
```

No generic AI system outputs this. This is what a construction lawyer charges €400/hour 
to produce manually.

---

## 3. Institutional Vendor Risk Index
*(Replaces: SM-2 Spaced Repetition LTM)*

### What the basic algo does
SM-2 spaced repetition strengthens facts each time they are re-encountered across 
documents. Designed for human memorization, applied to data persistence.

### What makes this novel
Contractors and subcontractors **repeat behaviors** across different multi-million euro 
projects. A project manager on Project A needs to know what a subcontractor did on 
Project B three years ago — before signing the contract.

### The Institutional Vendor Risk Index

Instead of "memorizing facts," the system tracks **behavioral patterns** across projects:

**Pattern detection example:**
```
Project A (2022): Subcontractor X claims Nachtrag for "unexpected ground conditions"
Project B (2023): Subcontractor X claims Nachtrag for "unexpected ground conditions"  
Project C (2024): Subcontractor X claims Nachtrag for "unexpected ground conditions"

→ SM-2 strength for this pattern: 0.83 (permanent tier)
→ Behavioral classification: "Claim Maximizer — Baugrundrisiko"
→ Risk flag: surfaces automatically in Project D bidding phase
```

**Memory tiers remapped:**
- **Working** → current project claims (volatile)
- **Episodic** → subcontractor behavior within one project portfolio
- **Semantic (permanent)** → cross-project behavioral fingerprint, survives indefinitely

**Output during procurement:**
When Subcontractor X appears in a new tender:
```
⚠️  VENDOR RISK FLAG
Subcontractor: X GmbH
Pattern: Baugrundrisiko Nachträge (3 occurrences, 2022-2024)
Total historical claim value from this pattern: €340,000
Average % of contract value claimed: 8.3%
Recommendation: Include explicit Baugrundrisiko allocation in contract
                Price in 10% contingency buffer
```

No system in the market does cross-project contractor behavioral memory. This is the 
kind of institutional knowledge that currently lives only in the heads of experienced 
project managers — and walks out the door when they retire.

---

## 4. Schedule-Aware Risk Cascade (Temporal Pheromone System)
*(Replaces: cosine similarity signal propagation)*

### What the basic algo does
Signal propagation via cosine similarity with 0.85 decay per hop. Finds semantically 
related nodes. Completely time-agnostic.

### What makes this novel
Construction projects are entirely governed by **time dependencies**. A delay in concrete 
pouring does not just semantically relate to a drywall delay — it **causes** it, with a 
quantifiable lag and a cascade of downstream Nachtrag rights.

### Implementation: CPM-Integrated Signal Propagation

**Input:** Project schedule (Gantt / CPM) + document corpus

**Decay function — replace cosine-only with temporal proximity:**
```
Signal strength to node B = base_strength 
                          × text_similarity(A, B)     # existing
                          × schedule_proximity(A, B)  # NEW
                          × (1 / (lag_days + 1))      # NEW — closer in time = stronger signal
```

**Schedule-aware pheromone cascade:**
```
Event: "Betonage Kellerdecke" delayed by 14 days
  → Signal emitted: TERMIN_DELAY, strength=1.0
  → CPM lookup: who depends on this milestone?
      └── "Rohbau Erdgeschoss" (lag: 7 days)  → signal strength: 0.92
            └── "Estrich verlegen" (lag: 14 days) → signal strength: 0.78
                  └── "Elektroinstallation" (lag: 7 days) → signal strength: 0.71
                        └── "Trockenbau" (lag: 14 days) → signal strength: 0.63
                              └── → potential Nachtrag rights for 4 subcontractors
```

**Output:**
```
⚠️  CASCADE ALERT: Betonage delay propagates to 4 schedule dependencies
    Estimated downstream Nachtrag exposure: €18,000 - €47,000
    Earliest impact: 7 days from now (Rohbau team)
    VOB/B §6 Abs. 6 applies: Bauzeitverlängerung claims eligible
    Action required: Issue formal Behinderungsanzeige within 3 days
```

This is genuinely novel. No RAG system integrates CPM schedule data with document 
analysis and legal rights. This is what construction project controllers do manually 
using Excel — and it takes days, not seconds.

---

## Summary: Why These Are Novel

| System | Generic version | Novel version | What makes it different |
|--------|----------------|---------------|------------------------|
| KG densification | Jaccard text similarity | Legal structure + GAEB item numbers | Deterministic, legally meaningful edges |
| Adversarial agents | Two LLM prompts debate | VOB/B-grounded pre-litigation engine | Outputs financial risk exposure score |
| Long-term memory | SM-2 fact persistence | Vendor behavioral fingerprint | Cross-project institutional memory |
| Signal propagation | Cosine similarity decay | CPM schedule-integrated cascade | Time-aware, legally triggered |

The novelty is not in the base algorithms. It is in **grounding each one in the 
specific legal, structural, and temporal reality of German construction projects** — 
in a way that no domain-agnostic AI system does or can do without this specialization.

---

## Next Steps

1. Validate VOB/B legal groundings with Linus/Patrick (they may have pilot customer 
   input on which Nachtrag patterns are most common)
2. GAEB file parser — check if any pilot customers use GAEB format (most German 
   construction companies do for BoQ exchange)
3. CPM/Gantt integration — what format do pilot customers use? (MS Project, Asta, 
   custom Excel?)
4. Prioritize: Vendor Risk Index (#3) likely has the fastest path to customer value 
   as it requires no new data format — just cross-project memory
