# Feature: Legato — Pivot from Studyond (thesis) to Impact Giving (LBBW)
Created: 2026-06-27
Last Updated: 2026-06-27

## Overview
Repurpose the Studyond thesis-discovery SPA into **Legato**, a bank product for LBBW's
"The Future of Giving" challenge. A credible, modern, seamless path to impact giving —
NOT a donation app / crowdfunding platform.

Hero narrative: **Next Gen (20–45) self-serve discovery → graduating into your own foundation**,
fully delegated to LBBW. Answers the case's core question: "from first flexible euro to own foundation."

## Key Decisions
1. **Name: Legato** (smooth, connected; bank-credible).
2. **Lead persona:** Next Gen graduating to Founder.
3. **Keep all data IDs + cross-references intact** — only rewrite content + add impact fields.
   Nothing referential breaks; graph/filters/store keep working.
4. **Keep internal type names** (Topic, Field, University, Company, Expert) — reinterpret meaning
   via data + UI labels. Minimizes churn.

## Domain mapping
- Field            → Cause Area (Climate, Education, Health, ...)
- University (blue/academic side) → Foundation / NGO (mission-driven)
- Company (orange/industry side)  → Corporate Giving / Co-Funding partner
- Supervisor       → NGO program lead / advisor
- Expert           → LBBW philanthropy advisor (bookable)
- Topic            → Impact Project (the fundable entity) + new impact fields
- Project (Companion) → donor giving commitment / impact dashboard

### New Topic fields (added to topics.json + Topic type)
- fundingGoal: number (€)
- fundingRaised: number (€, < goal)
- region: string
- sdg: number (1–17, UN SDG)
- impactUnit: string (e.g. "€50 funds one month of school meals")

## Journey reshape (phases.ts)
1. Discover (Giver-Identity onboarding)  — was Browse onboarding
2. Explore (cause/project discovery graph) — was Browse
3. Commit (fund + compare projects)       — was Select/Compare
4. Impact (real-time impact tracking)     — was Companion
5. Found (your own foundation / DAF, LBBW-delegated) — was disabled WrapUp; the bank-product climax

## Relevant Files
- `src/data/index.ts` — types + lookups + filters (extend Topic)
- `mock-data/*.json` — regenerate content, keep IDs
- `src/data/phases.ts` — journey config
- `src/store/useAppStore.ts` — panel names + gating
- `src/pages/OnboardingPage.tsx` — Giver-Identity
- `src/components/graph/GraphView.tsx` — hero discovery graph
- `src/lib/suggestFields.ts` — Haiku cause-area suggestions
- `src/pages/CompanionPage.tsx` — impact tracker chat (Opus)
- `src/pages/ResearchPage.tsx` — foundation blueprint builder (Sonnet, tool use)
- `index.html`, `src/App.css`, `package.json`, `README.md` — branding
- `src/components/ThesisAIChat.tsx` — ORPHAN, delete

## Current Status
- [x] Research phase (architecture inventory at .claude/doc/architecture-inventory.md)
- [x] Data layer reshape (mock-data + Topic impact fields + projects.json)
- [x] Branding rename (Legato logo, index.html, package.json, README)
- [x] Onboarding (Giver-Identity) / graph / phases / AI prompts
- [x] Found climax phase (FoundationPage)
- [x] Typecheck + production build both pass

## Verification
- `node node_modules/typescript/bin/tsc -b` → clean
- `vite build` → 816 modules, builds OK
- Deps installed via npm (bun not available on this machine)

## Known follow-ups (not yet done)
- stateLabel() in CompanionPage still uses thesis-application states (proposed/applied/agreed/...) — relabel to giving terms (pledged/active/funded/...) if time.
- Graph node files under src/components/nodes/* and src/components/graph/nodes/* still named TopicNode/SupervisorNode etc. (internal identifiers only, not user-visible).
- Commit phase (2) secondary panels (Advisors/Allocation) are still PlaceholderView stubs.
- TopicViewPage (/topic/:id) and MultiTopicFlow deep features not fully re-themed.

## Subagent Activity Log
| Agent | Task | Output File | Status |
| codebase-explorer (sonnet) | Architecture inventory | .claude/doc/architecture-inventory.md | done |

## Notes
- Stack: Vite 8 + React 19 SPA, Cloudflare Worker AI proxy (/api/ai/*), Zustand, shadcn, Tailwind v4 (config in src/App.css).
- Two graph engines: @xyflow/react v12 (discovery) + reactflow v11 + elkjs (research/topic).
- AI models in code are hackathon strings (haiku-4-5, sonnet-4-6, opus-4-6) — verify vs current IDs.
- Must hit the **Business Logic Sketch** (AUM, loyalty) in the Found phase for the pitch.
