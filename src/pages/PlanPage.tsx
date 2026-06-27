import { motion } from 'framer-motion'
import { ListTree, Sparkles, Scale, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { topicById, companyById, foundationById, fieldById } from '@/data/index'

const ACCENT = '#d97706' // phase-3 (Plan) accent

const PRESETS = [250, 1000, 5000, 25000]

function euro(n: number): string {
  return '€' + Math.round(n).toLocaleString('de-DE')
}

// impactUnit looks like "€200 equips one classroom …" → split cost + phrase.
function parseImpactUnit(unit: string): { cost: number; phrase: string } | null {
  const m = unit.match(/^€\s*([\d.,]+)\s+(.*)$/)
  if (!m) return null
  const cost = parseInt(m[1].replace(/[.,]/g, ''), 10)
  if (!cost) return null
  return { cost, phrase: m[2] }
}

function partnerName(topicId: string): string {
  const t = topicById[topicId]
  if (!t) return ''
  if (t.companyId) return companyById[t.companyId]?.name ?? ''
  if (t.foundationId) return foundationById[t.foundationId]?.name ?? ''
  return ''
}

export function PlanPage() {
  const {
    committedTopicIds,
    givingTotal,
    allocations,
    setGivingTotal,
    setAllocation,
    setCurrentPhase,
  } = useAppStore()

  const projects = committedTopicIds.map(id => topicById[id]).filter(Boolean)

  // weights → normalised shares (always sum to 100% of the total, no "must equal 100" guard)
  const weightOf = (id: string) => allocations[id] ?? 50
  const sumWeights = projects.reduce((s, p) => s + weightOf(p.id), 0)
  const denom = sumWeights || 1

  if (projects.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm space-y-3 text-center">
          <ListTree className="mx-auto size-8 text-muted-foreground/40" />
          <p className="ds-label text-muted-foreground">No projects to plan yet</p>
          <p className="ds-caption text-muted-foreground/60">
            Commit to a few impact projects in Explore, then come back to set your
            donation amount and split it across them.
          </p>
          <button
            onClick={() => setCurrentPhase(1)}
            className="mx-auto mt-1 flex items-center gap-1.5 rounded-lg px-3 py-1.5 ds-caption font-medium text-white"
            style={{ backgroundColor: ACCENT }}
          >
            Back to Explore <ArrowRight className="size-3.5" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-8 px-8 py-12 pb-28">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2" style={{ color: ACCENT }}>
            <ListTree className="size-5" />
            <span className="ds-caption font-medium uppercase tracking-wide">Phase 3 · Plan</span>
          </div>
          <h1 className="ds-title-xl">Your giving plan</h1>
          <p className="ds-body text-muted-foreground">
            Decide how much to give and how to split it across your committed projects —
            and see the real impact each share buys.
          </p>
        </div>

        {/* Total amount */}
        <div className="space-y-3 rounded-2xl border border-border bg-card p-6">
          <label className="ds-label">I want to give</label>
          <div className="flex items-baseline gap-1">
            <span className="ds-title-lg text-muted-foreground">€</span>
            <input
              type="number"
              min={0}
              value={givingTotal}
              onChange={e => setGivingTotal(Number(e.target.value))}
              className="w-44 bg-transparent ds-title-xl outline-none"
              style={{ color: ACCENT }}
            />
            <span className="ds-caption text-muted-foreground">per year</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map(p => (
              <button
                key={p}
                onClick={() => setGivingTotal(p)}
                className={`rounded-full border px-3 py-1 ds-caption transition ${
                  givingTotal === p
                    ? 'border-transparent text-white'
                    : 'border-border text-muted-foreground hover:border-foreground/30'
                }`}
                style={givingTotal === p ? { backgroundColor: ACCENT } : undefined}
              >
                {euro(p)}
              </button>
            ))}
          </div>
        </div>

        {/* Distribution */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-0.5">
            <div className="flex items-center gap-2">
              <Scale className="size-4 text-muted-foreground" />
              <span className="ds-label">Distribute across {projects.length} project{projects.length !== 1 ? 's' : ''}</span>
            </div>
            <button
              onClick={() => projects.forEach(p => setAllocation(p.id, 50))}
              className="ds-caption text-muted-foreground hover:text-foreground transition-colors"
            >
              Even split
            </button>
          </div>

          {projects.map((p, i) => {
            const weight = weightOf(p.id)
            const share = weight / denom
            const amount = Math.round(givingTotal * share)
            const pct = Math.round(share * 100)
            const parsed = parseImpactUnit(p.impactUnit)
            const units = parsed ? Math.floor(amount / parsed.cost) : 0
            const causes = p.fieldIds.map(id => fieldById[id]?.name).filter(Boolean).slice(0, 2)

            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: 0.03 * i }}
                className="space-y-3 rounded-xl border border-border bg-card p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-1">
                    <p className="ds-caption text-muted-foreground">{partnerName(p.id)}</p>
                    <h3 className="ds-label leading-tight">{p.title}</h3>
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {causes.map(c => (
                        <span key={c} className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground">{c}</span>
                      ))}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="ds-title-sm" style={{ color: ACCENT }}>{euro(amount)}</p>
                    <p className="ds-caption text-muted-foreground">{pct}%</p>
                  </div>
                </div>

                <input
                  type="range"
                  min={0}
                  max={100}
                  value={weight}
                  onChange={e => setAllocation(p.id, Number(e.target.value))}
                  className="w-full cursor-pointer accent-[#d97706]"
                />

                {parsed && (
                  <div className="flex items-baseline gap-1.5 rounded-lg bg-secondary/60 px-3 py-2">
                    <Sparkles className="size-3.5 shrink-0 translate-y-0.5" style={{ color: ACCENT }} />
                    <p className="ds-caption text-muted-foreground">
                      <span className="font-semibold text-foreground">≈ {units.toLocaleString('de-DE')}×</span>{' '}
                      {parsed.phrase}
                    </p>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
