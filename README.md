# LEGATUM — Intelligence-First Philanthropic Banking

> Built for **HackXplore 2026** by LBBW · Team: Mango

Legatum is a 9-layer AI-powered philanthropic banking product that transforms LBBW's wealth management offering. It turns philanthropic intent into structured, verifiable, long-term impact — guided by an agentic AI swarm at every step.

---

## Architecture: 9 Layers

| Layer | Name | What it does |
|-------|------|--------------|
| L1 | **Persona Discovery** | 12-question chat quiz → 4 giving personas |
| L2 | **NGO Intelligence** | 15 verified German NGOs, PHINEO-certified filter |
| L3 | **BlackSwanX Credibility AI** | Anomaly detection on NGO metrics (6.25× discrepancy flag) |
| L4 | **LBBW Advisor Interface** | Treuhandstiftung / Verbrauchsstiftung guidance |
| L5 | **Living Impact Universe** | Real-time particle flow simulation + D3 Knowledge Graph |
| L6 | **AI Agent Knowledge Graph** | 28-node living graph (personas, NGOs, SDGs, agent swarm) |
| L7 | **Foundation Arc** | 5-gate readiness path → mission statement generator |
| L8 | **LegatumPassport** | On-chain identity (ERC-721) + badge minting |
| L9 | **Stifter Intelligence** | CEO/advisor dashboard for portfolio strategy |

---

## Agent Swarm (L1–L9)

The 9-layer pipeline runs as an **AI agent swarm** — each layer is an autonomous node in the Knowledge Graph:

```
PersonaAgent  →  NGOMatchAgent  →  BlackSwanXAgent
     ↓                ↓                  ↓
FoundationAgent  →  ImpactAgent  →  PassportAgent
     ↓                ↓                  ↓
AdvisorAgent  →  KnowledgeAgent  →  StifterAgent
```

### 3 Expert Agents

| Agent | Role | Model |
|-------|------|-------|
| **PersonaExpert** | Classifies giving DNA → Architect / Catalyst / Guardian / Explorer | Claude claude-sonnet-4-6 |
| **BlackSwanXAnalyst** | Cross-references NGO claims vs Bundesanzeiger, independent audits | Claude Haiku (high-speed) |
| **FoundationAdvisor** | Structures Zustiftung / Treuhandstiftung based on persona + amount | Claude Opus |

---

## Repo Structure

```
Legatum/
├── legatum-nextjs/          ← Main hackathon demo (Next.js 14 + Framer Motion)
│   ├── app/                 ← 7 pages: entry, onboarding, persona, discover, impact, passport, foundation
│   ├── components/          ← Simulation.tsx (particle physics), BottomNav.tsx
│   ├── data/                ← ngos.json (15 NGOs, 2 anomaly-flagged), badges.json, questions.js
│   └── store/               ← Zustand persist store (full journey state)
│
├── BlackSwanX/              ← AI credibility verification engine
│   ├── legatum/             ← Graph RAG, corrective RAG, anomaly detection
│   ├── backend/             ← FastAPI endpoints
│   └── legatum_api.py       ← Legatum-specific API layer
│
├── contracts/
│   └── LegatumPassport.sol  ← ERC-721 on-chain giving identity + badge NFTs
│
└── legatum-frontend/        ← Original Vite prototype (archived reference)
```

---

## Quick Start — Main Demo

```bash
cd legatum-nextjs
npm install
npm run dev
# → http://localhost:3001
```

**Journey**: `/` → `/onboarding` → `/persona` → `/discover` → `/impact` → `/passport` → `/foundation`

---

## Giving Personas

| Persona | Color | Profile |
|---------|-------|---------|
| 🏛 **Architect** | `#7C3AED` | Systemic builder, long-term, legacy-driven |
| ⚡ **Catalyst** | `#F59E0B` | Root-cause activator, high leverage, bold |
| 🛡 **Guardian** | `#059669` | Deep relationships, few causes, personal |
| 🧭 **Explorer** | `#0EA5E9` | Curiosity-led, diverse, discovery-first |

---

## Key Technical Choices

- **Next.js 14 App Router** + `'use client'` for canvas-heavy pages
- **Framer Motion** — AnimatePresence, staggered reveals, spring physics
- **Zustand + persist** — Full journey state survives page refreshes
- **Canvas particle physics** — RAF loop, lerp steering, trail rendering, node absorption
- **D3 force simulation** — 28-node Knowledge Graph with zoom/drag
- **Direct DOM counter updates** — Bypass React batching for live €/lives counters
- **BlackSwanX Graph RAG** — ColModernVBERT + corrective RAG for NGO fact-checking
- **Solidity ERC-721** — LegatumPassport with 14 badge types, on-chain provenance

---

## LBBW Integration Points

- **Treuhandstiftung via BW-Bank** — Foundation arc gates (Gate 4)
- **PHINEO-Wirkt-Siegel** — 7 of 15 NGOs carry Germany's highest certification
- **BW-Bank Stiftungsmanagement** — Advisor slide-up in Foundation page
- **LBBW Innovation Deep Dive** — betterplace.org and Sinngeber featured

---

## Team

Built during **HackXplore 2026** at LBBW Stuttgart.
