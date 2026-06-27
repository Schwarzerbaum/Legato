import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Landmark, AlertTriangle, CheckCircle2, Clock, FileDown, Send, ChevronRight,
} from "lucide-react"

// ── Accents ───────────────────────────────────────────────────────────────────
const LBBW = "#003B6F"
const GREEN = "#059669"
const AMBER = "#d97706"
const RED = "#dc2626"

// ── Data (ported verbatim from the original) ──────────────────────────────────
interface Foundation {
  id: string
  name: string
  client: string
  purpose: string
  assets: number
  disbursed2025: number
  disbursedTarget: number
  status: "active" | "mature" | "pending"
  recognition: string
  recognitionDate: string
  taxStatus: string
  nextDisbursement: string
  complianceScore: number
  sdgs: number[]
  ngos: string[]
  alerts: string[]
  stiftungsregister: string
  annualReport: string
  gpa: string
}

const FOUNDATIONS: Foundation[] = [
  {
    id: "f1",
    name: "Hoffmann Klimastiftung",
    client: "Dr. Miriam Hoffmann",
    purpose: "Forest protection and renewable energy in Baden-Württemberg",
    assets: 1_200_000,
    disbursed2025: 84_000,
    disbursedTarget: 120_000,
    status: "active",
    recognition: "Anerkannt",
    recognitionDate: "2024-03-15",
    taxStatus: "§55–68 AO · Freigestellt",
    nextDisbursement: "2026-09-01",
    complianceScore: 96,
    sdgs: [13, 15],
    ngos: ["BUND e.V.", "BW Stiftung"],
    alerts: [],
    stiftungsregister: "StR-BW-2024-0311",
    annualReport: "submitted",
    gpa: "clear",
  },
  {
    id: "f2",
    name: "Breitner-Koch Sozialstiftung",
    client: "Familie Breitner-Koch",
    purpose: "Poverty alleviation, food security and human rights",
    assets: 4_800_000,
    disbursed2025: 210_000,
    disbursedTarget: 350_000,
    status: "active",
    recognition: "Anerkannt",
    recognitionDate: "2023-07-01",
    taxStatus: "§55–68 AO · Freigestellt",
    nextDisbursement: "2026-07-15",
    complianceScore: 88,
    sdgs: [2, 10, 16],
    ngos: ["Welthungerhilfe", "PHINEO gAG"],
    alerts: ["Annual Report 2025 — Submission deadline 30.06.2026"],
    stiftungsregister: "StR-BW-2023-0174",
    annualReport: "due",
    gpa: "clear",
  },
  {
    id: "f3",
    name: "von Saalfeld Stiftung",
    client: "Ingrid von Saalfeld",
    purpose: "Gesundheit, Bildung, Klimaschutz und Gleichstellung",
    assets: 12_500_000,
    disbursed2025: 900_000,
    disbursedTarget: 900_000,
    status: "mature",
    recognition: "Anerkannt",
    recognitionDate: "2022-01-20",
    taxStatus: "§55–68 AO · Freigestellt · §13 Nr. 16b ErbStG",
    nextDisbursement: "2026-10-01",
    complianceScore: 99,
    sdgs: [3, 4, 5, 13, 15],
    ngos: ["SOS-Kinderdorf", "Welthungerhilfe", "BUND e.V.", "Mercedes-Benz AG"],
    alerts: [],
    stiftungsregister: "StR-BW-2022-0041",
    annualReport: "submitted",
    gpa: "clear",
  },
  {
    id: "f4",
    name: "Walczak Digitalstiftung",
    client: "Stefan Walczak",
    purpose: "Digitale Inklusion und nachhaltige Stadtentwicklung BW",
    assets: 0,
    disbursed2025: 0,
    disbursedTarget: 50_000,
    status: "pending",
    recognition: "In Bearbeitung",
    recognitionDate: "—",
    taxStatus: "Tax Exemption Notice ausstehend",
    nextDisbursement: "—",
    complianceScore: 0,
    sdgs: [10, 11],
    ngos: ["Aktion Mensch"],
    alerts: [
      "Notarial deed complete — awaiting RP BW recognition",
      "Tax Exemption Notice from tax authority pending",
    ],
    stiftungsregister: "Eintragung beantragt",
    annualReport: "not_due",
    gpa: "pending",
  },
]

const STATUS_META: Record<string, { label: string; color: string }> = {
  active: { label: "Active", color: GREEN },
  mature: { label: "Established", color: LBBW },
  pending: { label: "Pending Registration", color: AMBER },
}

interface CalendarItem {
  date: string
  item: string
  priority: "high" | "normal" | "done"
  done: boolean
}

const COMPLIANCE_CALENDAR: CalendarItem[] = [
  { date: "30.06.2026", item: "Breitner-Koch Sozialstiftung — Annual Report 2025 einreichen", priority: "high", done: false },
  { date: "15.07.2026", item: "von Saalfeld Stiftung — Interim disbursement Q3 freigeben", priority: "normal", done: false },
  { date: "01.09.2026", item: "Hoffmann Klimastiftung — Q3 Disbursement an BUND e.V.", priority: "normal", done: false },
  { date: "15.09.2026", item: "Walczak Digitalstiftung — Stiftungsregister BW Eintragung", priority: "high", done: false },
  { date: "31.12.2026", item: "Alle Stiftungen — §55 AO Fund Utilisation Report", priority: "normal", done: false },
  { date: "31.01.2026", item: "von Saalfeld Foundation — GPA BW annual audit", priority: "done", done: true },
  { date: "15.03.2026", item: "Hoffmann Climate Foundation — Tax Exemption Notice renewed", priority: "done", done: true },
]

function fmt(n: number): string {
  return n >= 1_000_000 ? `€${(n / 1_000_000).toFixed(1)}M` : `€${(n / 1_000).toFixed(0)}k`
}

// ── Page ──────────────────────────────────────────────────────────────────────
export function BankFoundationPage() {
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<"portfolio" | "calendar">("portfolio")
  const found = FOUNDATIONS.find(f => f.id === selected)

  const totalAssets = FOUNDATIONS.filter(f => f.status !== "pending").reduce((a, f) => a + f.assets, 0)
  const totalDisbursed = FOUNDATIONS.filter(f => f.status !== "pending").reduce((a, f) => a + f.disbursed2025, 0)
  const alertCount = FOUNDATIONS.reduce((a, f) => a + f.alerts.length, 0)

  const kpis = [
    { l: "Foundations total", v: String(FOUNDATIONS.length), sub: "incl. 1 pending registration", alert: false },
    { l: "Foundation assets", v: fmt(totalAssets), sub: "assets under management", alert: false },
    { l: "Disbursements 2025", v: fmt(totalDisbursed), sub: "§55 AO compliant", alert: false },
    { l: "Open compliance", v: String(alertCount), sub: "deadlines & conditions", alert: alertCount > 0 },
  ]

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-10 pb-28">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2" style={{ color: LBBW }}>
            <Landmark className="size-5" />
            <span className="ds-caption font-medium uppercase tracking-wide">
              Foundation Intelligence · Internal Management
            </span>
          </div>
          <h1 className="ds-title-xl">Foundation Intelligence</h1>
          <p className="ds-body text-muted-foreground">
            Complete overview of all LBBW-managed foundations — compliance, disbursements,
            Foundation Register BW and real-time tax monitoring.
          </p>
        </div>

        {/* KPI strip */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {kpis.map(k => (
            <div
              key={k.l}
              className="rounded-2xl border bg-card p-5"
              style={k.alert ? { borderColor: RED, backgroundColor: "rgba(220,38,38,0.05)" } : undefined}
            >
              <p className="ds-title-md" style={{ color: k.alert ? RED : undefined }}>{k.v}</p>
              <p className="ds-caption mt-1 font-medium">{k.l}</p>
              <p className="ds-caption text-muted-foreground">{k.sub}</p>
            </div>
          ))}
        </div>

        {/* View toggle */}
        <div className="flex gap-2">
          {(["portfolio", "calendar"] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-full border px-4 py-1.5 ds-caption font-medium transition ${
                view === v ? "border-transparent text-white" : "border-border text-muted-foreground hover:border-foreground/30"
              }`}
              style={view === v ? { backgroundColor: LBBW } : undefined}
            >
              {v === "portfolio" ? "Foundation Portfolio" : "Compliance Calendar"}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {view === "portfolio" && (
            <motion.div
              key="portfolio"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex gap-6"
            >
              {/* List */}
              <div className="min-w-0 flex-1 space-y-3">
                {FOUNDATIONS.map(f => {
                  const sm = STATUS_META[f.status]
                  const pct = f.disbursedTarget > 0 ? Math.round((f.disbursed2025 / f.disbursedTarget) * 100) : 0
                  const isSel = selected === f.id
                  return (
                    <motion.div
                      key={f.id}
                      onClick={() => setSelected(isSel ? null : f.id)}
                      whileHover={{ x: 2 }}
                      className="cursor-pointer space-y-3 rounded-xl border bg-card p-5"
                      style={{
                        borderColor: isSel ? sm.color : undefined,
                        borderLeftWidth: 3,
                        borderLeftColor: sm.color,
                      }}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h3 className="ds-label leading-tight">{f.name}</h3>
                          <p className="ds-caption text-muted-foreground">{f.client}</p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="ds-caption font-medium uppercase tracking-wide" style={{ color: sm.color }}>
                            {sm.label}
                          </p>
                          {f.assets > 0 && (
                            <p className="ds-caption text-muted-foreground">{fmt(f.assets)}</p>
                          )}
                        </div>
                      </div>

                      {f.status !== "pending" && (
                        <div className="space-y-1.5">
                          <div className="h-1.5 rounded-full bg-secondary">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ duration: 0.7 }}
                              className="h-full rounded-full"
                              style={{ backgroundColor: pct === 100 ? LBBW : GREEN }}
                            />
                          </div>
                          <div className="flex justify-between ds-caption text-muted-foreground">
                            <span>{fmt(f.disbursed2025)} disbursed</span>
                            <span>{pct}% of {fmt(f.disbursedTarget)}</span>
                          </div>
                        </div>
                      )}

                      {f.alerts.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {f.alerts.map(a => (
                            <span
                              key={a}
                              className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ds-caption"
                              style={{ borderColor: AMBER, color: AMBER }}
                            >
                              <AlertTriangle className="size-3" />
                              {a.length > 45 ? a.substring(0, 45) + "…" : a}
                            </span>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </div>

              {/* Detail panel */}
              <AnimatePresence>
                {found && (
                  <motion.div
                    key={found.id}
                    initial={{ opacity: 0, x: 16 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 16 }}
                    transition={{ type: "spring", damping: 28, stiffness: 260 }}
                    className="hidden w-[320px] shrink-0 lg:block"
                  >
                    <div className="sticky top-4 space-y-4 rounded-2xl border border-border bg-card p-6">
                      <div>
                        <p className="ds-caption font-medium uppercase tracking-wide" style={{ color: STATUS_META[found.status].color }}>
                          {STATUS_META[found.status].label}
                        </p>
                        <h2 className="ds-title-sm leading-tight">{found.name}</h2>
                        <p className="ds-caption text-muted-foreground">{found.client}</p>
                      </div>

                      <p className="ds-body text-muted-foreground">{found.purpose}</p>

                      <div className="space-y-3">
                        {[
                          { l: "Stiftungsregister", v: found.stiftungsregister },
                          { l: "Anerkennung", v: `${found.recognition}${found.recognitionDate !== "—" ? " · " + found.recognitionDate : ""}` },
                          { l: "Steuerlicher Status", v: found.taxStatus },
                          { l: "Next Disbursement", v: found.nextDisbursement },
                        ].map(row => (
                          <div key={row.l}>
                            <p className="ds-caption text-muted-foreground">{row.l}</p>
                            <p className="ds-label leading-snug">{row.v}</p>
                          </div>
                        ))}
                      </div>

                      {found.complianceScore > 0 && (
                        <div className="space-y-2 rounded-xl border p-4" style={{ borderColor: LBBW, backgroundColor: "rgba(0,59,111,0.04)" }}>
                          <div className="flex items-center justify-between">
                            <span className="ds-caption font-medium" style={{ color: LBBW }}>Compliance Score</span>
                            <span className="ds-label" style={{ color: found.complianceScore >= 90 ? GREEN : AMBER }}>
                              {found.complianceScore}/100
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-secondary">
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${found.complianceScore}%`, backgroundColor: found.complianceScore >= 90 ? GREEN : AMBER }}
                            />
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap gap-1.5">
                        {found.sdgs.map(s => (
                          <span key={s} className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground">
                            SDG {s}
                          </span>
                        ))}
                      </div>

                      <div className="space-y-2 pt-1">
                        <button
                          className="flex w-full items-center justify-center gap-2 rounded-lg py-2.5 ds-caption font-medium uppercase tracking-wide text-white"
                          style={{ backgroundColor: LBBW }}
                        >
                          <Send className="size-3.5" /> Disbursement freigeben
                        </button>
                        <button className="flex w-full items-center justify-center gap-2 rounded-lg border border-border py-2.5 ds-caption text-muted-foreground transition hover:text-foreground">
                          <FileDown className="size-3.5" /> Stiftungsbericht exportieren
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {view === "calendar" && (
            <motion.div
              key="calendar"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              {COMPLIANCE_CALENDAR.map((item, i) => {
                const accent = item.done ? "#94a3b8" : item.priority === "high" ? RED : LBBW
                return (
                  <div
                    key={i}
                    className="flex items-center gap-4 rounded-xl border bg-card p-5"
                    style={{ borderLeftWidth: 3, borderLeftColor: accent, opacity: item.done ? 0.6 : 1 }}
                  >
                    <span className="w-20 shrink-0 ds-caption text-muted-foreground">{item.date}</span>
                    <span className="ds-label flex-1 font-normal leading-snug">{item.item}</span>
                    <span className="flex shrink-0 items-center gap-1 ds-caption font-medium" style={{ color: accent }}>
                      {item.done ? (
                        <><CheckCircle2 className="size-3.5" /> Erledigt</>
                      ) : item.priority === "high" ? (
                        <><AlertTriangle className="size-3.5" /> Dringend</>
                      ) : (
                        <><Clock className="size-3.5" /> Offen</>
                      )}
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-muted-foreground/40" />
                  </div>
                )
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
