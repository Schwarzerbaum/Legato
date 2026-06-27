import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Receipt, HeartHandshake } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { topicById, topics, type Topic } from '@/data/index'
import { givingProjection, type TaxInputs } from '@/lib/germanTax'

// Phase-5 "Tax Benefits" panel. One job: in three seconds, show that giving
// through Legato costs far less than the headline figure, because the German
// tax system refunds a meaningful share of every charitable euro.

const YOU = '#7c3aed'   // what you actually pay (Found-phase violet)
const TAX = '#059669'   // what the tax system gives back
const GOOD = '#e11d48'  // impact

const START_YEAR = new Date().getFullYear()
const calendarYear = (year: number) => START_YEAR + year - 1

const euro = (n: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(
    Math.round(n),
  )

const euroShort = (n: number) => {
  if (Math.abs(n) >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `€${Math.round(n / 1_000)}k`
  return `€${Math.round(n)}`
}

function parseImpactUnit(unit: string): { cost: number; text: string } | null {
  const m = unit.match(/€\s*([\d.,]+)\s+(.*)/)
  if (!m) return null
  const cost = Number(m[1].replace(/[.,](?=\d{3}\b)/g, '').replace(',', '.'))
  if (!Number.isFinite(cost) || cost <= 0) return null
  return { cost, text: m[2] }
}

export function TaxBenefitsPage() {
  const { committedTopicIds } = useAppStore()

  const [income, setIncome] = useState(60_000)
  const [monthly, setMonthly] = useState(150)
  const [years, setYears] = useState(30)

  const inputs: TaxInputs = useMemo(
    () => ({ income, donation: monthly * 12, married: false, churchRate: 0 }),
    [income, monthly],
  )
  const projection = useMemo(() => givingProjection(inputs, years), [inputs, years])
  const final = projection[projection.length - 1]

  const donated = final?.cumulativeDonated ?? 0
  const saved = final?.cumulativeSaved ?? 0
  const netCost = final?.cumulativeNetCost ?? 0
  const refundPct = donated > 0 ? Math.round((saved / donated) * 100) : 0

  const impact = useMemo(() => {
    const committed = committedTopicIds.map(id => topicById[id]).filter(Boolean) as Topic[]
    const pick = (committed[0] ?? topics[1]) as Topic | undefined
    if (!pick) return null
    const parsed = parseImpactUnit(pick.impactUnit)
    if (!parsed) return null
    return { count: Math.floor(donated / parsed.cost), text: parsed.text }
  }, [committedTopicIds, donated])

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-10 pt-24 pb-28 space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="space-y-3 max-w-2xl"
        >
          <div className="flex items-center gap-2" style={{ color: YOU }}>
            <Receipt className="size-5" />
            <span className="ds-caption font-medium uppercase tracking-wide">Tax Benefits · Germany</span>
          </div>
          <h1 className="ds-title-xl">Giving costs less than you think</h1>
          <p className="ds-body text-muted-foreground">
            Over {years} years of steady giving, {euro(donated)} reaches your causes at an effective cost of{' '}
            {euro(netCost)} — the balance is recovered through German charitable tax relief.
          </p>
        </motion.div>

        {/* Chart + summary, side by side */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.08 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
        >
          {/* Chart — the hero */}
          <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="ds-title-cards">Your giving over time</h2>
              <div className="flex items-center gap-4">
                <Legend color={YOU} label="You pay" />
                <Legend color={TAX} label="Tax refunds" />
              </div>
            </div>
            <ProjectionChart data={projection} />
          </div>

          {/* Summary figures */}
          <div className="rounded-2xl border border-border bg-card p-6 flex flex-col justify-center divide-y divide-border">
            <Figure label="Total contributed" value={euro(donated)} color={GOOD} className="pb-5" />
            <Figure label="Recovered via tax relief" value={euro(saved)} sub={`${refundPct}% of your giving`} color={TAX} className="py-5" />
            <Figure label="Effective cost to you" value={euro(netCost)} color={YOU} className="pt-5" />
          </div>
        </motion.div>

        {/* Controls */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.16 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-8"
        >
          <Slider label="Monthly gift" value={monthly} min={10} max={1_000} step={10}
            display={`${euro(monthly)}/mo`} onChange={setMonthly} accent={YOU} />
          <Slider label="Your income" value={income} min={20_000} max={200_000} step={1_000}
            display={euro(income)} onChange={setIncome} accent={YOU} />
          <Slider label="Years of giving" value={years} min={5} max={50} step={1}
            display={`${years} yrs`} onChange={setYears} accent={YOU} />
        </motion.div>

        {/* One impact line */}
        {impact && impact.count > 0 && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.22 }}
            className="flex items-center gap-3 rounded-2xl border border-border bg-card p-5"
          >
            <HeartHandshake className="size-6 shrink-0" style={{ color: GOOD }} />
            <p className="ds-small">
              That funds{' '}
              <span className="ds-title-sm font-medium tabular-nums" style={{ color: GOOD }}>
                {impact.count.toLocaleString('de-DE')}×
              </span>{' '}
              — {impact.text}.
            </p>
          </motion.div>
        )}

        <p className="ds-caption text-center text-muted-foreground/60">
          Illustrative, not tax advice · 2025 income-tax schedule (§ 32a EStG), deductible up to 20 % of income (§ 10b EStG).
        </p>
      </div>
    </div>
  )
}

function Figure({
  label, value, sub, color, className,
}: {
  label: string; value: string; sub?: string; color: string; className?: string
}) {
  return (
    <div className={className}>
      <p className="ds-caption text-muted-foreground">{label}</p>
      <p className="ds-title-md tabular-nums" style={{ color }}>{value}</p>
      {sub && <p className="ds-caption text-muted-foreground/70 mt-0.5">{sub}</p>}
    </div>
  )
}

// --------------------------------------------------------------------------
// Projection chart — stacked areas (you pay + tax refunds) with a hover scrubber
// --------------------------------------------------------------------------

function ProjectionChart({ data }: { data: ReturnType<typeof givingProjection> }) {
  const [hover, setHover] = useState<number | null>(null)

  const W = 640
  const H = 280
  const P = { top: 16, right: 16, bottom: 28, left: 52 }
  const innerW = W - P.left - P.right
  const innerH = H - P.top - P.bottom

  const maxY = Math.max(1, data[data.length - 1]?.cumulativeDonated ?? 1)
  const n = data.length

  const x = (i: number) => P.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
  const y = (v: number) => P.top + innerH - (v / maxY) * innerH

  const line = (sel: (p: (typeof data)[number]) => number) =>
    data.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(sel(p)).toFixed(1)}`).join(' ')

  const netArea =
    `M ${x(0)} ${y(0)} ` +
    data.map((p, i) => `L ${x(i).toFixed(1)} ${y(p.cumulativeNetCost).toFixed(1)}`).join(' ') +
    ` L ${x(n - 1)} ${y(0)} Z`

  const savedBand =
    data.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.cumulativeNetCost).toFixed(1)}`).join(' ') +
    ' ' +
    data.map((_, i) => `L ${x(n - 1 - i).toFixed(1)} ${y(data[n - 1 - i].cumulativeDonated).toFixed(1)}`).join(' ') +
    ' Z'

  const gridVals = [0, 0.5, 1].map(f => f * maxY)
  const xTicks = n <= 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1]
  const hp = hover != null ? data[hover] : null

  return (
    <div className="relative w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 'auto' }}
        onMouseLeave={() => setHover(null)}
        onMouseMove={e => {
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          const px = ((e.clientX - rect.left) / rect.width) * W
          const i = Math.round(((px - P.left) / innerW) * (n - 1))
          setHover(Math.max(0, Math.min(n - 1, i)))
        }}
      >
        <defs>
          <linearGradient id="grad-saved" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={TAX} stopOpacity={0.45} />
            <stop offset="100%" stopColor={TAX} stopOpacity={0.12} />
          </linearGradient>
          <linearGradient id="grad-net" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={YOU} stopOpacity={0.35} />
            <stop offset="100%" stopColor={YOU} stopOpacity={0.06} />
          </linearGradient>
        </defs>

        {gridVals.map((v, i) => (
          <g key={i}>
            <line x1={P.left} x2={W - P.right} y1={y(v)} y2={y(v)} stroke="currentColor" className="text-border" strokeWidth={1} />
            <text x={P.left - 8} y={y(v) + 4} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 11 }}>
              {euroShort(v)}
            </text>
          </g>
        ))}

        <motion.path d={savedBand} fill="url(#grad-saved)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} />
        <motion.path d={netArea} fill="url(#grad-net)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} />

        <motion.path
          d={line(p => p.cumulativeDonated)} fill="none" stroke={TAX} strokeWidth={2.5}
          strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.7 }}
        />
        <motion.path
          d={line(p => p.cumulativeNetCost)} fill="none" stroke={YOU} strokeWidth={2.5}
          strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.7, delay: 0.1 }}
        />

        {xTicks.map(i => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className="fill-muted-foreground" style={{ fontSize: 11 }}>
            {calendarYear(data[i]?.year ?? 1)}
          </text>
        ))}

        {hp && (
          <g>
            <line x1={x(hover!)} x2={x(hover!)} y1={P.top} y2={P.top + innerH} stroke={YOU} strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
            <circle cx={x(hover!)} cy={y(hp.cumulativeDonated)} r={4} fill={TAX} stroke="white" strokeWidth={1.5} />
            <circle cx={x(hover!)} cy={y(hp.cumulativeNetCost)} r={4} fill={YOU} stroke="white" strokeWidth={1.5} />
          </g>
        )}
      </svg>

      {hp && (
        <div
          className="pointer-events-none absolute top-2 rounded-lg border border-border bg-popover px-3 py-2 shadow-md"
          style={{ left: `${(x(hover!) / W) * 100}%`, transform: `translateX(${hover! > n / 2 ? 'calc(-100% - 10px)' : '10px'})` }}
        >
          <p className="ds-caption font-medium">{calendarYear(hp.year)}</p>
          <Row color={TAX} label="Given" value={euro(hp.cumulativeDonated)} />
          <Row color={YOU} label="Net cost" value={euro(hp.cumulativeNetCost)} />
        </div>
      )}
    </div>
  )
}

function Row({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 mt-1">
      <span className="ds-caption text-muted-foreground flex items-center gap-1.5">
        <span className="inline-block size-2 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </span>
      <span className="ds-caption font-medium tabular-nums">{value}</span>
    </div>
  )
}

function Slider({
  label, value, min, max, step, display, onChange, accent,
}: {
  label: string; value: number; min: number; max: number; step: number
  display: string; onChange: (v: number) => void; accent: string
}) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="ds-label">{label}</span>
        <span className="ds-label tabular-nums" style={{ color: accent }}>{display}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{ background: `linear-gradient(to right, ${accent} ${pct}%, var(--secondary) ${pct}%)`, color: accent }}
      />
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="ds-caption text-muted-foreground flex items-center gap-1.5">
      <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  )
}
