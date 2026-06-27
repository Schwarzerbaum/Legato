# Mock Data — Legato

Mock dataset for **Legato**, the impact-giving platform (HackXplore 2026, LBBW challenge).

All files are plain JSON, imported at build time through `src/data/index.ts`, which
also holds the TypeScript interfaces and lookup/filter helpers.

## Entities

| File | Records | Represents |
|---|--:|---|
| `fields.json` | 20 | **Cause areas** (Climate, Education, Health, …) — the inner ring of the discovery graph |
| `foundations.json` | 10 | **Foundations & NGOs** (the mission-driven side) |
| `companies.json` | 15 | **Corporate giving / co-funding partners** |
| `supervisors.json` | 25 | **Program leads / advisors** at foundations |
| `experts.json` | 30 | **Philanthropy advisors** (LBBW + corporate CSR), bookable 1:1 |
| `topics.json` | 60 | **Impact projects** — the fundable entity |
| `projects.json` | 15 | **Giving commitments** at various stages (used by the Impact tracker) |
| `students.json` | 40 | Donor/people records referenced by the `/topic/:id` deep view |

## Impact project shape (`topics.json`)

Each project is owned by **either** a foundation (`foundationId`) **or** a corporate
partner (`companyId`), references one or more cause areas (`fieldIds`), and carries
the giving-specific fields:

- `fundingGoal` / `fundingRaised` — euros (raised is always < goal)
- `region` — where the impact happens
- `sdg` — relevant UN Sustainable Development Goal (1–17)
- `impactUnit` — concrete outcome per euro (e.g. *"€50 funds one month of school meals"*)

## ID format

Human-readable `entity-NN` (e.g. `topic-45`, `field-08`). IDs are stable — the data
was transformed from the original thesis dataset while preserving every ID and
cross-reference, so relationships stay consistent.
