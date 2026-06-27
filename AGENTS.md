# Legato

AI-powered impact-giving platform for LBBW (HackXplore 2026 — *The Future of Giving*).
A credible, modern path that guides Next-Gen givers from their first flexible euro to
their own LBBW-delegated foundation. Built as a bank product, not a donation app.

## Agent Instructions

- Always use npm (not bun).
- Run `npm run dev` to develop, `npm run build` to verify a production build, `npx tsc -b` to typecheck.
- Keep the existing visual language: editorial-minimal, the Foundations/NGOs (blue) vs
  Corporate-partners (orange) duality, and the per-phase accent colors in `src/data/phases.ts`.
- Before adding a feature, read the relevant files and ask the user if scope is unclear.

## Architecture

- **Stack:** Vite 8 + React 19 + TypeScript SPA, deployed to Cloudflare Workers.
- **State:** single Zustand store at `src/store/useAppStore.ts`.
- **Styling:** Tailwind v4 (config lives in `src/App.css`), shadcn/ui (`new-york`, base color zinc).
- **AI:** Anthropic Claude via a same-origin proxy `/api/ai/*` (`src/index.ts` worker injects the key;
  `vite.config.ts` proxies it in dev from `.dev.vars`). Never expose `ANTHROPIC_API_KEY` to the browser.
- **Graphs:** discovery graph uses `@xyflow/react`; the research/topic graphs use `reactflow` v11 + `elkjs`.

## The journey (`src/data/phases.ts`)

Discover (onboarding) → **Explore** → **Commit** → **Plan** → **Impact** → **Found**.
Committing to one or more projects (the `committedTopicIds` portfolio) unlocks Plan/Impact/Found.

## Key paths

| Path | What |
|---|---|
| `src/data/index.ts` | Domain types, lookups, filters, impact helpers (`formatEuro`, `fundingPct`) |
| `mock-data/*.json` | Cause areas, foundations/NGOs, corporate partners, advisors, impact projects |
| `src/pages/OnboardingPage.tsx` | Giver-Identity onboarding |
| `src/components/graph/GraphView.tsx` | The hero discovery graph |
| `src/pages/ResearchPage.tsx` | AI giving-plan builder (Claude tool-calling) |
| `src/pages/CompanionPage.tsx` | Impact tracker + AI companion |
| `src/pages/FoundationPage.tsx` | The "Found" climax — donor-advised fund / foundation |
| `src/store/useAppStore.ts` | Navigation, selections, shortlist, giving portfolio |

See `mock-data/README.md` for the data model.
