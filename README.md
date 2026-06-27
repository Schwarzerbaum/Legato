# Legato — The Future of Giving

> HackXplore 2026 submission for the **LBBW** challenge: *Win the Next Generation of Philanthropists*

---

## The Case

LBBW manages 1,500+ foundations and €10B+ in assets, but philanthropy is still "old, male, and rigid" — 95% of German foundation founders are 45+. Meanwhile **88% of under-40s want a philanthropic identity but lack the right digital product to start**, and a traditional foundation needs €100k of capital and months of bureaucracy.

The core question: *how does a user journey look that guides both the broad base and high-profile founders from their first flexible euro to their own foundation?*

LBBW explicitly does **not** want another donation app or crowdfunding platform — they want a **bank product** with a credible, modern, seamless path to impact giving.

---

## Our Solution

**Legato** — a credible, modern path to impact giving, fully wrapped as an LBBW bank product. Next-Gen givers (20–45) self-serve: they discover their *Giver-Identity*, explore impact projects on an interactive graph, commit their first flexible euro, track real-world impact, and — when they're ready — graduate into their **own Impact Hub** (a donor-advised fund) — which opens immediately rather than over the six months a traditional foundation needs, with all governance, compliance and tax handling delegated to LBBW.

We lead with the Next-Gen discovery story and end on the *Impact Hub* climax, where the bank's business logic lands: recurring assets under management, deeper loyalty, and measurable impact.

---

## The Journey

| # | Phase | What happens |
|---|-------|-------------|
| — | **Discover** | Onboarding: pick what moves you + how you like to give. Claude suggests the cause areas that fit your *Giver-Identity*. |
| 1 | **Explore** | An interactive graph of the giving landscape — cause areas → foundations/NGOs & corporate partners → fundable impact projects. |
| 2 | **Commit** | Shortlist, compare projects side-by-side, and commit your first flexible euro. |
| 3 | **Plan** | An AI advisor builds your giving strategy as a visual portfolio of cause pillars and allocations. |
| 4 | **Impact** | A real-time impact tracker + AI companion: "what has my giving achieved?" |
| 5 | **Impact Hub** | Graduate into your own LBBW-delegated Impact Hub (a donor-advised fund) — opens immediately, no six-month foundation set-up, immediate tax benefits, a lasting legacy. |

---

## Key Features

- **Interactive giving graph** — concentric rings of cause areas, foundations & corporate co-funders, and impact projects (XYFlow + ELK), each showing live funding progress.
- **AI Giver-Identity onboarding** — Claude maps your values + giving style to relevant cause areas.
- **Impact projects** — every project carries a funding goal/raised bar, region, UN SDG, and a concrete impact unit (e.g. *"€50 funds one month of school meals"*).
- **AI giving-plan builder** — Claude structures your mission into cause pillars and allocations via tool calling.
- **Impact tracker** — streaming AI companion reporting on the real-world impact of your gifts.
- **Impact Hub climax** — the donor-advised fund product the user opens instantly, framed around LBBW's AUM and loyalty business case.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 8 |
| Routing | React Router 7 |
| Styling | TailwindCSS 4, shadcn/ui |
| Animation | Framer Motion |
| State | Zustand |
| Graph | XYFlow/React, ReactFlow, elkjs |
| AI | OpenAI (gpt-4o-mini) via a same-origin proxy |
| Deployment | Cloudflare Workers |

---

## Getting Started

```bash
npm install
npm run dev
```

For deployment:

```bash
npm run build
npx wrangler deploy
```

Set `OPENAI_API_KEY` for AI features — locally in a `.dev.vars` file in the project root, and in your Cloudflare Worker environment for production (`npx wrangler secret put OPENAI_API_KEY`). Without it the app still runs, but the AI features ("Help me decide" onboarding chat, planning companion) silently no-op.

---

## Data

The prototype runs on realistic mock data (German/European, Baden-Württemberg flavour):

- 60 impact projects with funding goals, regions, SDGs and impact units
- 10 foundations & NGOs (Caritas BW, Welthungerhilfe, NABU, WWF Deutschland, …)
- 15 corporate giving partners (Bosch, SAP, Mercedes-Benz, Porsche, …)
- Philanthropy advisors and program leads for 1:1 booking

---

## The bank side — `legatum-nextjs/` + `backend/`

Alongside the giver-facing app (this repo's root), the project ships the
**bank/advisor-facing** side so an LBBW banker can discover, vet and manage the
philanthropic portfolio:

- **`legatum-nextjs/`** — a Next.js 14 advisor app with five screens: Discover (verified
  German NGOs), Assess (BlackSwanX credibility / anomaly detection), Portfolio, Foundation
  intelligence (Treuhand-/Verbrauchsstiftung guidance), and a D3 Knowledge-Graph view.
  Run with `cd legatum-nextjs && npm install && npm run dev`.
- **`backend/`** — Python intelligence layers (`legatum_bank_engine`, `legatum_user_engine`,
  `legatum_intelligence` orchestrator/router/vector-store).
- **`contracts/LegatumPassport.sol`** — an ERC-721 on-chain "Legatum Passport" + giving badges.

See `legatum-nextjs/README.md` for the full bank-engine docs.

### Running & linking the two apps

```bash
npm run dev     # giver app  → http://localhost:5173  (Vite)
npm run bank    # bank app   → http://localhost:3000  (Next.js)
```

They deploy separately (giver → Cloudflare Workers via `npm run deploy`; bank → its
own host). To **link** them, each side reads the other's deployed URL from an env var,
and the cross-link only renders when its URL is set:

- **Giver app** (build-time): `VITE_BANK_URL=https://<bank-url>` → shows an
  "LBBW Advisor view ↗" link top-right of onboarding.
- **Bank app** (deploy env): `NEXT_PUBLIC_GIVER_URL=https://<giver-url>` → shows a
  "Giver app ↗" link in the bottom nav.

---

## Team

Built during **HackXplore 2026** at LBBW Stuttgart.
