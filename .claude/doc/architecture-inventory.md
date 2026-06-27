# Architecture Inventory — "Studyond" Thesis Discovery App

> Initial full-codebase inventory. Goal: map everything before repurposing this thesis-discovery
> app into a philanthropy / impact-giving platform for LBBW (a bank).

**IMPORTANT framing correction:** Despite the repo folder name `ThesisCoPilot`, this is **NOT a Next.js app**.
It is a **Vite + React 19 SPA** deployed to **Cloudflare Workers**. There is no `app/` or `pages/` Next.js
router, no server components, no API routes in the Next.js sense. Routing is client-side via `react-router-dom`.
All "AI backend" is a thin proxy to the Anthropic API (a Cloudflare Worker in prod, a Vite middleware in dev).
The product brand everywhere is **"Studyond"**, not "ThesisCoPilot".

---

## 1. Top-Level Structure

### Stack (from `package.json`, name = `start-hack-2026`)
- **Framework:** Vite 8 + React 19 (`@vitejs/plugin-react`), TypeScript ~5.9
- **Routing:** `react-router-dom` ^7.13
- **State:** `zustand` ^5
- **Styling:** Tailwind CSS v4 (`@tailwindcss/vite`), `shadcn` ^3.8 (new-york style), `tw-animate-css`
- **UI primitives:** `radix-ui`, `lucide-react` icons, `class-variance-authority`, `tailwind-merge`
- **Animation:** `framer-motion` ^12
- **Graph/network viz:** TWO libraries coexist — `@xyflow/react` ^12 (newer) AND `reactflow` ^11 (legacy). Plus `elkjs` ^0.11 for layered/tree auto-layout.
- **AI:** `@anthropic-ai/sdk` ^0.80 (used directly in browser) + `@ai-sdk/anthropic` + `ai` ^6 (Vercel AI SDK, present as dep but the actual code uses the raw Anthropic SDK)
- **Forms:** `react-hook-form` + `@hookform/resolvers` + `zod` ^4 (deps present; forms barely used)
- **Markdown:** `react-markdown`
- **Deploy:** `wrangler` ^4 → Cloudflare Workers. Package manager: **bun** (`bun.lock`).

### Scripts
- `dev` → vite; `build` → `tsc -b && vite build`; `deploy` → `bun run build && wrangler deploy`; `cf-typegen` for CF env types.

### Entry points
- `index.html` → loads `/src/main.tsx`. Title = **"Studyond"**, favicon from `https://studyond.com/favicon.svg`.
- `src/main.tsx` — React root, wraps app in `<BrowserRouter>` with the route table (see §2).
- `src/App.tsx` — the `/` route. Renders **either** `OnboardingPage` **or** `GraphPage` based on a single Zustand flag `currentView` (`'onboarding' | 'graph'`), with framer-motion crossfade. This is the heart of the app.
- `src/index.ts` — **Cloudflare Worker** entry (configured by `wrangler.jsonc` `main`). Proxies `/api/ai/*` → `https://api.anthropic.com/*`, injecting `x-api-key` from `env.ANTHROPIC_API_KEY` and `anthropic-version`. Everything else → static asset serving with SPA fallback to `/`.
- `vite.config.ts` — plugins: a custom `anthropicDevProxy` (reads `.dev.vars` for `ANTHROPIC_API_KEY`, proxies `/api/ai` to Anthropic in dev, streaming-capable), then `react()`, `tailwindcss()`, `cloudflare()`. Alias `@` → `./src`.

### Notable non-source dirs
- `context/` — ~88 markdown strategy/spec docs (Studyond business model, personas, data model, etc.). Pure documentation, not code.
- `brand/` — brand guideline docs + example components (Chat.tsx, CardExample.tsx).
- `mock-data/` — all the seed JSON (see §5).
- `skills/`, `AGENTS.md` (symlinked from `CLAUDE.md`), `Starthack_Studyond_26.pdf` — pitch material.

---

## 2. Routes / Pages

Routing is in `src/main.tsx`. Only the `/` route uses the phase-based SPA shell; the others are standalone full-screen pages (deep-linkable).

| URL | Component file | Renders |
|-----|----------------|---------|
| `/` | `App.tsx` → `OnboardingPage` or `GraphPage` | Main app shell. Onboarding gate, then the phased workspace. |
| `/schedule/:expertId` | `src/pages/ExpertBookingPage.tsx` | Expert 1:1 booking: profile card + month calendar + time-slot picker + confirm dialog. |
| `/booking-success` | `src/pages/BookingSuccessPage.tsx` | Booking confirmation screen (reads nav state). |
| `/topic/:topicId` | `src/pages/TopicViewPage.tsx` | Full-screen ReactFlow graph of one topic and all its related entities (company, university, supervisors, experts, projects, students). Expandable nodes + ELK layout. |
| `/research` | `src/pages/ResearchPage.tsx` | AI research-planning graph builder (also embedded inside the shell — see below). |

### The phase flow (core of the product) — driven by Zustand, NOT routes
`App.tsx` shows `OnboardingPage` until `enterGraph()` flips `currentView='graph'`, then `GraphPage` renders.
`GraphPage` (`src/pages/GraphPage.tsx`) is a **panel switcher**: it reads `currentPanel` from the store and conditionally mounts a sub-view, with a floating **`PhasesBar`** at the bottom for phase navigation.

Phases are defined in `src/data/phases.ts` (5 phases, each with sidebar items/panels):
1. **Browse** (`#2563eb` blue) — panels: graph, bookmarks, thesis-graph, compare, search
2. **Select** (`#0d9488` teal) — thesis-graph, literature, experts, resources, notes (mostly placeholders)
3. **Research** (`#d97706` amber) — outline, editor, citations, ai-assist → all route to `ResearchPage`
4. **Companion** (`#e11d48` rose) — companion, checklist, formatting, submission, feedback
5. **Wrap Up** (`#7c3aed` violet) — **disabled** (reviews, revisions, publish, archive — not built)

> Note: README markets a "6-phase journey" (Browse, Select, Research, Thesis Companion, Submit, Publish) but the code implements **5 phases** with phase 5 disabled. README/marketing and code diverge.

**Phase gating** (`PhasesBar.tsx`): phase 2 unlocked once ≥1 bookmark; phase 3 once `plannedTopicId` set; phase 4 once `selectedProjectId` set; phase 5 always disabled.

Panels that are NOT graph/bookmarks/compare/search/thesis-graph/research/companion render a generic `PlaceholderView` ("Coming soon"). So Select-phase literature/experts/resources/notes and most of Companion/Wrap-Up are stubs.

Mapped panel → real view in `GraphPage.tsx`:
- `graph` → `GraphView` (the radial discovery graph)
- `bookmarks` → inline `BookmarksView`
- `thesis-graph` → `ThesisGraphPage` → `MultiTopicFlow`
- `compare` → `ComparePage`
- `search` → `SearchPage`
- phase-3 panels → `ResearchPage`
- `companion` → `CompanionPage`

---

## 3. Components

Location: `src/components/`. shadcn primitives in `src/components/ui/` (avatar, badge, button, card, dialog, dropdown-menu, form, input, label, select, separator, sheet, skeleton, tabs, textarea, tooltip).

### Interactive graph / network visualizations (the signature feature) — THREE distinct graph systems
1. **`src/components/graph/GraphView.tsx`** — the **radial discovery graph** (uses `@xyflow/react`). Hand-rolled polar layout: concentric rings — Ring 1 = research **fields** (R=330), Ring 2 = **sources** (universities fanned LEFT at 180°, companies RIGHT at 0°, R=550), Ring 3 = **topics** clustered near their source (R=750). Click topic → opens detail panel; double-click source → source panel. Custom node types in `src/components/graph/nodes/`: `CenterNode`, `FieldNode`, `SourceNode`, `TopicNode`, `PersonNode`, `SourceNode`. Custom edge `edges/FloatingEdge.tsx`. Color tokens in `graph/colors.ts`.
2. **`src/components/graph/MultiTopicFlow.tsx`** (~600 lines) — multi-topic "thesis graph" shown in `ThesisGraphPage`; visualizes all bookmarked topics together. Uses `@xyflow/react`. Has `MultiTopicFlowEmptyState`.
3. **`src/components/graph/ThesisGraph.tsx`** — single-topic graph builder (`buildThesisGraph(topicId)`), `ThesisCenterNode`. Standalone.
4. **`src/pages/TopicViewPage.tsx`** (route `/topic/:topicId`) — uses **legacy `reactflow` v11** (different import!) + ELK `layered` layout. Builds an expandable entity graph: topic → company/university/supervisors/experts/projects → (project sub-entities: company, supervisors, experts, student). Node components in `src/components/nodes/` (`TopicNode`, `ExpertNode`, `SupervisorNode`, `UniversityNode`, `CompanyNode`, `ProjectNode`, `StudentNode`). Detail panel `TopicViewDetailPanel.tsx`.

> **Repurposing note:** `src/components/graph/*` (xyflow) and `src/components/nodes/*` (reactflow v11) are two parallel node families for two different graph engines. Don't confuse them.

### AI onboarding flow
- `src/pages/OnboardingPage.tsx` — university + study-programme `Select` dropdowns. On programme selection calls `suggestFields()` (Claude Haiku) to highlight 3 relevant fields, then `enterGraph()`.

### Research outline editor (AI graph builder)
- `src/pages/ResearchPage.tsx` (~730 lines) — the most complex AI feature. ReactFlow (v11) canvas + ELK `mrtree` layout + chat sidebar. Claude (sonnet) drives it via **tool calling** (add_project / add_node / edit_node / remove_node) to build a hierarchical research-plan graph. Per-topic graph state persisted in a module-level `Map`. Node component: `src/components/research/ResearchNode.tsx`. A project node has an "open companion" affordance that unlocks Phase 4.

### Expert / supervisor booking
- `src/pages/ExpertBookingPage.tsx` + `src/components/booking/`: `ExpertProfileCard.tsx`, `CalendarView.tsx`, `TimeSlotPicker.tsx`, `BookingConfirmDialog.tsx`. Availability is **deterministically generated** (`src/lib/availability.ts`, seeded djb2 hash) — no backend.
- `src/pages/BookingSuccessPage.tsx` — post-booking screen.

### AI chat sidebars
- `src/pages/CompanionPage.tsx` — project timeline (left, 62%) + `CompanionChat` (right, 38%). Streaming Claude (opus) chat with project-context system prompt. Manual milestone CRUD (local state only).
- `src/components/ThesisAIChat.tsx` — a standalone AI thesis-assistant chat card with a **hardcoded student persona ("Nils", ETH Zürich)**. **ORPHAN: not imported anywhere** (only self-reference). Dead/demo code, but contains a full system prompt.

### Detail panels / wizards
- `src/components/TopicDetailPanel.tsx` — right slide-in for a selected topic (badges, company/supervisor info, bookmark toggle).
- `src/components/SourceDetailPanel.tsx` — right slide-in for a university/company/supervisor + its topics.
- `src/components/TopicViewDetailPanel.tsx` — detail panel for the `/topic/:id` graph.
- `src/components/PhasesBar.tsx` — the floating phase navigation pill bar with gating logic.

---

## 4. State Management (Zustand)

**Single store:** `src/store/useAppStore.ts` (the ONLY Zustand store).

State shape:
- Navigation: `currentView` (`onboarding|graph`), `currentPhase` (1–5), `currentPanel` (SidebarPanel union of ~22 panel names).
- Onboarding: `selectedUniversityId`, `selectedProgramId`.
- Graph selections: `selectedFieldIds` (max 1 enforced), `selectedSourceIds` (multi).
- Topic/bookmarks: `activeTopicId`, `activeSourceId`, `bookmarkedTopicIds` (ordered = priority ranking), `plannedTopicId`.
- Compare: `compareTopicIds: [A, B]`.
- AI field suggestions: `suggestedFieldIds`, `suggestionsLoading`.
- Companion: `selectedProjectId`.

Actions: `setUniversityId`, `setProgramId`, `enterGraph`, `goToOnboarding`, `toggleField`, `toggleSource`, `setActiveTopic`, `setActiveSource`, `toggleBookmark`, `moveBookmark` (reorder priority), `toggleCompare` (A/B slot logic), `setCurrentPanel`, `setCurrentPhase` (also sets default panel per phase + clears active selections), `setPlannedTopic`, `setSuggestedFieldIds`, `setSuggestionsLoading`, `setSelectedProjectId`.

Derived helper: `deriveGraphLevel(state)` → 1/2/3 (fields → sources → topics) controls how many rings render.

> Local component state (NOT in Zustand): research graph (module-level `Map` in ResearchPage), companion milestones, booking selections, search filters. No persistence to localStorage/backend anywhere — all state is in-memory and resets on reload.

---

## 5. Data Layer (all mock JSON, no database)

Raw JSON in `mock-data/` (imported directly at build time):

| File | ~Items | Entity |
|------|--------|--------|
| `universities.json` | ~10 | University |
| `study-programs.json` | ~30 | StudyProgram |
| `fields.json` | ~20 | Field (research field taxonomy) |
| `supervisors.json` | ~25 | Supervisor (academic) |
| `companies.json` | ~15 | Company (industry) |
| `experts.json` | ~30 | Expert (industry mentors) |
| `topics.json` | ~60 | Topic (the central entity — thesis topics/jobs) |
| `students.json` | ~40 | Student |
| `projects.json` | ~15 | Project (a student working a topic) |

> (README claims "400+ topics / 185+ supervisors" but the actual seed data is the smaller counts above.)

### Type definitions (two parallel sets — slight drift)
- **`src/data/index.ts`** — the **primary data access layer**. Re-declares interfaces (University, StudyProgram, Field, Supervisor, Company, Expert, Topic), casts the JSON, builds O(1) lookup maps (`topicById`, `companyById`, `supervisorById`, `fieldById`, `expertById`, `universityById`), and exposes filter/derivation functions: `programsForUniversity`, `universitiesForFields`, `companiesForFields`, `topicsForSourcesAndFields`, plus label helpers (`degreeLabel`, `workplaceLabel`, `employmentTypeLabel`). **This file is the data backbone — everything imports from `@/data/index`.**
- **`src/types/entities.ts`** — Student, Supervisor, University, **Project** (Project type only lives here, not in data/index).
- **`src/types/topic.ts`** — Topic, Degree, TopicType, TopicEmployment(Type), TopicWorkplaceType.
- **`src/types/booking.ts`** — Expert, Company, Field, TimeSlot, DayAvailability, BookingSelection.

Key entity highlights for repurposing:
- **Topic** = central unit: `{ id, title, description, type('topic'|'job'), employment, employmentType, workplaceType, degrees[], fieldIds[], companyId?, universityId?, supervisorIds[], expertIds[] }`. Every screen revolves around Topic + its field/company/university/supervisor/expert relations. **This is what would map to "impact projects / causes / charities" in a philanthropy pivot.**
- **Field** = `{ id, name }` flat taxonomy (maps to "cause areas").
- **Company / University** = the two "source" sides (academic vs industry). The whole UI has a baked-in **academic-vs-industry duality** (blue vs orange — see §8).

`src/lib/`: `availability.ts` (seeded mock calendar), `suggestFields.ts` (Claude field suggestions), `utils.ts` (shadcn `cn`). `src/hooks/use-mobile.ts`.

---

## 6. AI Integration

**Architecture:** No traditional backend. The browser talks to Anthropic through a same-origin proxy at **`/api/ai/...`**:
- **Prod:** `src/index.ts` Cloudflare Worker forwards `/api/ai/*` → `api.anthropic.com/*`, injecting `x-api-key` (`env.ANTHROPIC_API_KEY`) + `anthropic-version: 2023-06-01`, adds permissive CORS.
- **Dev:** `vite.config.ts` `anthropicDevProxy` does the same using `.dev.vars`.

Clients use the raw `@anthropic-ai/sdk` with `baseURL: ${origin}/api/ai`, `apiKey: 'not-needed'` (real key injected by proxy), `dangerouslyAllowBrowser: true`. (The `ai` / `@ai-sdk/anthropic` Vercel deps are installed but the shipped code uses the raw SDK + `fetch`.)

### Four AI call sites + their prompts/models

1. **`src/lib/suggestFields.ts`** — onboarding field suggestion.
   - Model: **`claude-haiku-4-5-20251001`**, `max_tokens:100`, plain `fetch` to `/api/ai/v1/messages`.
   - Prompt: "You are helping a university student find a thesis topic. Student: {degree} in {program} at {university}. Available fields: …. Return a JSON array of exactly 3 field names …". Parses JSON array back to field IDs.

2. **`src/pages/ResearchPage.tsx`** — AI research-graph builder (the big one).
   - Model: **`claude-sonnet-4-6`**, `max_tokens:4096`, **tool use** with 4 tools (`add_project`, `add_node`, `edit_node`, `remove_node`) defined as `Anthropic.Tool[]`. Agentic loop: keeps calling while `stop_reason === 'tool_use'`.
   - System prompt: "You are a research planning assistant that builds visual graphs via tool calls…" with detailed hierarchy rules (root→project→detail), topic-correlation rules, and 4 mutually-exclusive behavior cases. Full prompt at `ResearchPage.tsx:125-167`. Tool schemas at lines 60-123.
   - Sends a `graphContext()` string (current nodes/edges/focused node) prepended to each user message.

3. **`src/pages/CompanionPage.tsx`** (`CompanionChat`) — project companion chat.
   - Model: **`claude-opus-4-6`**, `max_tokens:2000`, **streaming** (`client.messages.stream`), markdown rendering.
   - System prompt built dynamically per project: "You are the Studyond Companion — a dedicated AI assistant for thesis project tracking." + injected Project Context (title/state/description/university/company/supervisors/experts) + Timeline. At `CompanionPage.tsx:367-383`.

4. **`src/components/ThesisAIChat.tsx`** — **ORPHAN/unused** standalone assistant.
   - Model: **`claude-opus-4-6`**, `max_tokens:1024`, streaming.
   - System prompt: "You are the Studyond AI Thesis Assistant…" with a **hardcoded persona "Nils" at ETH Zürich**, the 5 thesis stages, and hardcoded matches (Roche/UBS/McKinsey, Prof. Glimm/Zhang). At `ThesisAIChat.tsx:14-43`. Good prompt to reference but currently dead code.

> Model IDs (`claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-6`) are hackathon-era placeholders — verify against current Anthropic model IDs before reuse.

---

## 7. Branding / Naming

The product name is **"Studyond"** everywhere (not "ThesisCoPilot" — that's only the git folder name; `CLAUDE.md` → `AGENTS.md` symlink). Package name is `start-hack-2026`.

Every place "Studyond" / "thesis" appears (key hits — full list available via grep):

**Brand name "Studyond":**
- `index.html:7` — `<title>Studyond</title>`; `index.html:5` — favicon `https://studyond.com/favicon.svg`
- `src/assets/studyond.svg` — the logo asset, imported in: `OnboardingPage.tsx:9,70`, `GraphView.tsx:2,340`, `ResearchPage.tsx:23,625`, `ThesisGraph.tsx:2,288`, `MultiTopicFlow.tsx:20,585` (rendered bottom-right of every graph)
- `src/App.css:2` — "Studyond Design System — Main CSS"
- `ThesisAIChat.tsx:14,23` — "Studyond AI Thesis Assistant", "Studyond is a three-sided marketplace…"
- `CompanionPage.tsx:367` — "You are the Studyond Companion…"
- `README.md:1,3,11` — title + challenge link `https://studyond.com`

**"Thesis"/"thesis" (copy + identifiers):**
- `OnboardingPage.tsx`: "Switzerland · Thesis Discovery" (84), "perfect thesis" (88), "personalised graph of thesis opportunities" (91), "Explore thesis graph" (174), footer (183)
- `SearchPage.tsx:172,293` — "Filter through all available thesis topics", "{n} theses"
- `ComparePage.tsx:36,70,234` — "Thesis A/B", "bookmark thesis topics"
- `SourceDetailPanel.tsx:143,153` — "Thesis collaboration", "{n} thesis topics"
- `ExpertProfileCard.tsx:46` — "...thesis topics, career paths…"
- Identifiers (would need careful rename): panel id `'thesis-graph'` and store union (`useAppStore.ts:5,167`), `ThesisGraph`/`ThesisGraphPage`/`ThesisCenterNode`/`buildThesisGraph` (`graph/ThesisGraph.tsx`), `ThesisGraphPage.tsx`, `ThesisAIChat.tsx`, phase labels in `data/phases.ts`.
- README marketing copy throughout.

**Constants/copy hotspots to rebrand:** `index.html` (title/favicon), `src/App.css:2` header, `src/assets/studyond.svg` (+ `hero.png`), `data/phases.ts` (phase names/colors), all page heading strings, the 4 AI system prompts (§6).

There is **no central constants/config file** for branding — copy is hardcoded inline across pages. A rebrand touches many files.

---

## 8. Styling / Theme

- **No `tailwind.config.ts`** — Tailwind v4 is config-via-CSS. The single source is **`src/App.css`** (also `src/index.ts`? no — CSS is `App.css`, imported by `App.tsx`). `components.json` points shadcn at `src/App.css`, `baseColor: zinc`, style `new-york`, css-variables on.
- `App.css` imports: `tailwindcss`, `tw-animate-css`, `shadcn/tailwind.css`, `@xyflow/react/dist/style.css`.
- **Theme tokens** (`@theme inline` + `:root` / `.dark`): a **neutral grayscale** palette in OKLCH (background/foreground/card/primary/secondary/muted/accent/border + chart-1..5 + sidebar-*). Light and dark both defined; the app effectively runs light (no theme toggle wired). `--radius: 0.625rem`.
- **AI accent utilities** (`App.css:133-155`): `.text-ai` (purple→blue gradient text), `.bg-ai` (gradient bg), `.text-ai-solid` (blue-600), `.border-ai` (blue-200). Used to mark AI surfaces.
- **Typography:** font = "Avenir Next" stack. Custom type scale classes `.ds-caption / .ds-label / .ds-small / .ds-body / .ds-title-* / .header-*`. Used pervasively instead of raw Tailwind text classes.
- **Academic vs Industry visual distinction (important, baked-in everywhere):** `src/components/graph/colors.ts` defines `ACADEMIC` = **blue** (`#3b82f6`/`#2563eb`) and `INDUSTRY` = **orange** (`#f97316`/`#ea580c`), each with border/text/bg/selectedBg/muted. This blue=universities / orange=companies duality is reused in `GraphView`, `SearchPage`, `ComparePage`, detail panels, and legends. README §"Design Philosophy" calls this out explicitly.
- **Phase colors** (separate from the above) live in `data/phases.ts`: Browse blue `#2563eb`, Select teal `#0d9488`, Research amber `#d97706`, Companion rose `#e11d48`, WrapUp violet `#7c3aed`.
- No dedicated ThemeProvider component; dark mode via `.dark` class variant only (`@custom-variant dark`).

---

## Repurposing Implications (for the LBBW philanthropy pivot)

- **Reusable as-is:** the radial discovery graph (`GraphView`), the phase shell + `PhasesBar`, Zustand store pattern, shadcn UI kit, the AI proxy architecture (`src/index.ts` + dev proxy), the AI research-graph builder (tool-use pattern), booking flow, the academic/industry color-duality system.
- **Domain remap:** Topic → impact project/cause; Field → cause area; Company/University (the two "sources") → e.g. NGOs/initiatives vs corporate-giving programs; Supervisor/Expert → advisors/beneficiaries; Project → a donor's giving commitment. The `src/data/index.ts` layer + `mock-data/*.json` are the single point to swap the dataset.
- **Heavy rebrand surface:** name "Studyond" + "thesis" copy is hardcoded inline in ~15 files and all 4 AI system prompts; logo `studyond.svg` + `index.html` title/favicon; phase names. No central config to flip.
- **Two graph engines** (`@xyflow/react` v12 AND `reactflow` v11) and **two parallel node-component families** (`components/graph/*` vs `components/nodes/*`) — consolidate to reduce confusion.
- **Stubs/dead code:** Select-phase panels (literature/experts/resources/notes), most of Companion/Wrap-Up are `PlaceholderView`s; `ThesisAIChat.tsx` is unused; phase 5 disabled. README oversells (6 phases, 400+ topics) vs reality (5 phases w/ #5 off, ~60 topics).
- **No backend/persistence** — everything in-memory + mock JSON; a real bank platform would need data + auth layers added.
