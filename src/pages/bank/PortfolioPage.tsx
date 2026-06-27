import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Briefcase, TrendingUp, AlertTriangle, ArrowRight, X,
  Diamond, Hexagon, Calendar, ChevronRight,
} from "lucide-react"

// ── Brand / semantic accents ──────────────────────────────────────────────────
const LBBW = "#003B6F" // bank identity navy
const GREEN = "#059669"
const AMBER = "#d97706"
const BLUE = "#2563eb"
const PURPLE = "#7c3aed"

// ── Data (ported verbatim) ─────────────────────────────────────────────────────
interface Allocation {
  org: string
  type: "ngo" | "corp"
  amount: number
  sdg: number
  progress: number
}
interface Client {
  id: string
  name: string
  tier: string
  aum: number
  givingBudget: number
  deployed: number
  sdgs: number[]
  pillars: string[]
  status: "active" | "review" | "onboarding" | "foundation"
  lastContact: string
  allocations: Allocation[]
  notes: string
}

const CLIENTS: Client[] = [
  {
    id: "c1",
    name: "Dr. Miriam Hoffmann",
    tier: "Private Banking",
    aum: 4_800_000,
    givingBudget: 120_000,
    deployed: 87_000,
    sdgs: [4, 13, 15],
    pillars: ["Climate", "Education"],
    status: "active",
    lastContact: "2026-06-18",
    allocations: [
      { org: "BUND e.V.", type: "ngo", amount: 40_000, sdg: 15, progress: 82 },
      { org: "BW Stiftung", type: "ngo", amount: 30_000, sdg: 4, progress: 56 },
      { org: "Robert Bosch GmbH", type: "corp", amount: 17_000, sdg: 4, progress: 34 },
    ],
    notes: "Wants quarterly impact reports. Prefers BW-region NGOs. SDG 13 anchor.",
  },
  {
    id: "c2",
    name: "Familie Breitner-Koch",
    tier: "Wealth Management",
    aum: 12_200_000,
    givingBudget: 350_000,
    deployed: 210_000,
    sdgs: [2, 10, 16],
    pillars: ["Poverty", "Human Rights", "Food Security"],
    status: "review",
    lastContact: "2026-05-30",
    allocations: [
      { org: "Welthungerhilfe", type: "ngo", amount: 120_000, sdg: 2, progress: 90 },
      { org: "PHINEO gAG", type: "ngo", amount: 55_000, sdg: 17, progress: 68 },
      { org: "Porsche AG", type: "corp", amount: 35_000, sdg: 8, progress: 44 },
    ],
    notes: "Stiftung interest raised in last call — flag for /found. Annual SDG 2 priority.",
  },
  {
    id: "c3",
    name: "Stefan Walczak",
    tier: "Private Banking",
    aum: 2_100_000,
    givingBudget: 50_000,
    deployed: 12_000,
    sdgs: [10, 11],
    pillars: ["Digital Inclusion", "Cities"],
    status: "onboarding",
    lastContact: "2026-06-22",
    allocations: [
      { org: "Aktion Mensch", type: "ngo", amount: 12_000, sdg: 10, progress: 24 },
    ],
    notes: "New client — impact strategy not finalised. Schedule Discover session.",
  },
  {
    id: "c4",
    name: "Ingrid von Saalfeld",
    tier: "Ultra High Net Worth",
    aum: 38_500_000,
    givingBudget: 900_000,
    deployed: 900_000,
    sdgs: [3, 4, 5, 13, 15],
    pillars: ["Health", "Education", "Climate", "Gender"],
    status: "foundation",
    lastContact: "2026-06-10",
    allocations: [
      { org: "SOS-Kinderdorf", type: "ngo", amount: 300_000, sdg: 3, progress: 100 },
      { org: "Welthungerhilfe", type: "ngo", amount: 200_000, sdg: 2, progress: 100 },
      { org: "BUND e.V.", type: "ngo", amount: 250_000, sdg: 15, progress: 100 },
      { org: "Mercedes-Benz AG", type: "corp", amount: 150_000, sdg: 13, progress: 100 },
    ],
    notes: "Delegated foundation granted 2026-04. Quarterly stewardship call only.",
  },
]

const STATUS_META: Record<Client["status"], { label: string; color: string }> = {
  active: { label: "Active", color: GREEN },
  review: { label: "Needs Review", color: AMBER },
  onboarding: { label: "Onboarding", color: BLUE },
  foundation: { label: "Foundation", color: PURPLE },
}

function fmt(n: number): string {
  return "€" + (n >= 1_000_000 ? (n / 1_000_000).toFixed(1) + "M" : (n / 1_000).toFixed(0) + "k")
}

// ── Progress bar ───────────────────────────────────────────────────────────────
function Bar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="h-full rounded-full"
        style={{ backgroundColor: color }}
      />
    </div>
  )
}

// ── Detail panel ───────────────────────────────────────────────────────────────
function DetailPanel({ client, onClose }: { client: Client; onClose: () => void }) {
  const meta = STATUS_META[client.status]
  return (
    <motion.div
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 24 }}
      transition={{ type: "spring", damping: 28, stiffness: 260 }}
      className="w-[340px] shrink-0"
    >
      <div className="sticky top-6 space-y-5 rounded-2xl border border-border bg-card p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <span
              className="ds-caption font-medium uppercase tracking-wide"
              style={{ color: meta.color }}
            >
              {meta.label}
            </span>
            <h2 className="ds-title-sm">{client.name}</h2>
            <p className="ds-caption italic text-muted-foreground">{client.tier}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {[
            { l: "AUM", v: fmt(client.aum) },
            { l: "Budget", v: fmt(client.givingBudget) },
            { l: "Deployed", v: fmt(client.deployed) },
            { l: "Last contact", v: client.lastContact },
          ].map(row => (
            <div key={row.l}>
              <p className="ds-caption text-muted-foreground">{row.l}</p>
              <p className="ds-label">{row.v}</p>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <p className="ds-caption font-medium uppercase tracking-wide text-muted-foreground">
            Allocations
          </p>
          {client.allocations.map(a => {
            const c = a.type === "ngo" ? PURPLE : BLUE
            const Icon = a.type === "ngo" ? Diamond : Hexagon
            return (
              <div key={a.org} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 ds-caption">
                    <Icon className="size-3" style={{ color: c }} />
                    {a.org}
                  </span>
                  <span className="ds-caption text-muted-foreground">{fmt(a.amount)}</span>
                </div>
                <Bar value={a.progress} color={c} />
              </div>
            )
          })}
        </div>

        <div className="rounded-xl border border-border bg-secondary/40 p-3">
          <p className="mb-1 ds-caption font-medium uppercase tracking-wide text-muted-foreground">
            Advisor Notes
          </p>
          <p className="ds-caption italic leading-relaxed text-muted-foreground">{client.notes}</p>
        </div>

        <div className="space-y-2">
          <button
            className="flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 ds-caption font-medium text-white"
            style={{ backgroundColor: LBBW }}
          >
            Open Discover Session <ArrowRight className="size-3.5" />
          </button>
          {client.status === "review" && (
            <button
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-2 ds-caption font-medium"
              style={{ borderColor: AMBER, color: AMBER }}
            >
              Schedule Review Call
            </button>
          )}
          {(client.aum >= 5_000_000 || client.status === "foundation") && (
            <button
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-2 ds-caption font-medium"
              style={{ borderColor: PURPLE, color: PURPLE }}
            >
              <Diamond className="size-3.5" /> Explore Foundation Path
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export function PortfolioPage() {
  const [selected, setSelected] = useState<string | null>(null)
  const client = CLIENTS.find(c => c.id === selected) ?? null

  const deployedTotal = CLIENTS.reduce((a, c) => a + c.deployed, 0)
  const budgetTotal = CLIENTS.reduce((a, c) => a + c.givingBudget, 0)

  const SUMMARY = [
    { label: "Active", status: "active" as const },
    { label: "Review", status: "review" as const },
    { label: "Onboarding", status: "onboarding" as const },
    { label: "Foundation", status: "foundation" as const },
  ].map(s => ({
    ...s,
    val: CLIENTS.filter(c => c.status === s.status).length,
    color: STATUS_META[s.status].color,
  }))

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-10 pb-28">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2" style={{ color: LBBW }}>
            <Briefcase className="size-4" />
            <span className="ds-caption font-medium uppercase tracking-wide">
              Advisor Dashboard · LBBW Philanthropic Services
            </span>
          </div>
          <h1 className="ds-title-xl">Client Portfolio</h1>
          <p className="ds-body text-muted-foreground">
            {CLIENTS.length} active advisories · {fmt(deployedTotal)} deployed of{" "}
            {fmt(budgetTotal)} mandated.
          </p>
        </div>

        {/* Summary stat cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SUMMARY.map(s => (
            <div key={s.label} className="rounded-2xl border border-border bg-card p-5">
              <p className="ds-title-lg" style={{ color: s.color }}>
                {s.val}
              </p>
              <p className="ds-caption text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Client list + detail */}
        <div className="flex gap-6">
          <div className="flex-1 space-y-3">
            {CLIENTS.map((c, i) => {
              const meta = STATUS_META[c.status]
              const pct = Math.round((c.deployed / c.givingBudget) * 100)
              const isSel = selected === c.id
              return (
                <motion.button
                  key={c.id}
                  type="button"
                  onClick={() => setSelected(isSel ? null : c.id)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: 0.04 * i }}
                  className="block w-full rounded-2xl border bg-card p-6 text-left transition-colors hover:border-foreground/20"
                  style={{
                    borderColor: isSel ? meta.color : undefined,
                    borderLeftWidth: 3,
                    borderLeftColor: meta.color,
                  }}
                >
                  {/* Top row: name + status */}
                  <div className="mb-4 flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-0.5">
                      <h3 className="ds-title-sm leading-tight">{c.name}</h3>
                      <p className="ds-caption text-muted-foreground">{c.tier}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <span
                        className="ds-caption font-medium uppercase tracking-wide"
                        style={{ color: meta.color }}
                      >
                        {meta.label}
                      </span>
                      <p className="ds-caption text-muted-foreground">AUM {fmt(c.aum)}</p>
                    </div>
                  </div>

                  {/* Deployment bar */}
                  <Bar value={pct} color={pct === 100 ? GREEN : LBBW} />
                  <div className="mt-2 flex items-center justify-between ds-caption">
                    <span className="text-muted-foreground">{fmt(c.deployed)} deployed</span>
                    <span
                      className="font-medium"
                      style={{ color: pct === 100 ? GREEN : pct < 50 ? AMBER : LBBW }}
                    >
                      {pct}% of {fmt(c.givingBudget)}
                    </span>
                  </div>

                  {/* Cause tags */}
                  <div className="mt-4 flex flex-wrap items-center gap-1.5">
                    {c.pillars.map(p => (
                      <span
                        key={p}
                        className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground"
                      >
                        {p}
                      </span>
                    ))}
                    {c.status === "review" && (
                      <span
                        className="flex items-center gap-1 rounded-full border px-2 py-0.5 ds-caption font-medium"
                        style={{ borderColor: AMBER, color: AMBER }}
                      >
                        <AlertTriangle className="size-3" /> Action needed
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-1 ds-caption text-muted-foreground">
                      <TrendingUp className="size-3" /> {c.allocations.length} allocations
                      <ChevronRight className="size-3" />
                    </span>
                  </div>
                </motion.button>
              )
            })}

            <p className="flex items-center gap-1.5 px-1 ds-caption text-muted-foreground/70">
              <Calendar className="size-3" /> Select a client to view allocations and advisor
              notes.
            </p>
          </div>

          {/* Detail panel */}
          <AnimatePresence mode="wait">
            {client && (
              <DetailPanel key={client.id} client={client} onClose={() => setSelected(null)} />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
