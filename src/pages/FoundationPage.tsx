import { motion } from 'framer-motion'
import { Landmark, Receipt, ShieldCheck, TrendingUp, Sparkles, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import {
  topicById,
  fieldById,
  companyById,
  foundationById,
  formatEuro,
} from '@/data/index'

// The "Found" phase — the climax of the Legato journey. The donor graduates
// from one-off giving into their own LBBW-delegated foundation (a donor-advised
// fund). This is where the bank's business logic lands: assets under management,
// recurring commitment, and long-term loyalty.

const ENDOWMENT = 250_000          // illustrative starting endowment
const ANNUAL_GRANT_RATE = 0.05     // 5% of endowment granted per year
const TAX_DEDUCTION_RATE = 0.30    // ~30% effective tax benefit (illustrative)

export function FoundationPage() {
  const { committedTopicIds } = useAppStore()

  const projects = committedTopicIds.map(id => topicById[id]).filter(Boolean)

  const causeIds = new Set(projects.flatMap(p => p.fieldIds))
  const causes = Array.from(causeIds).map(id => fieldById[id]?.name).filter(Boolean) as string[]

  const partnerIds = new Set(
    projects.flatMap(p => [p.companyId, p.foundationId].filter(Boolean) as string[]),
  )
  const partners = Array.from(partnerIds)
    .map(id => companyById[id]?.name ?? foundationById[id]?.name)
    .filter(Boolean) as string[]

  const annualGrants = Math.round(ENDOWMENT * ANNUAL_GRANT_RATE)
  const taxBenefit = Math.round(ENDOWMENT * TAX_DEDUCTION_RATE)

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-12 pb-28 space-y-8">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-3"
        >
          <div className="flex items-center gap-2" style={{ color: '#7c3aed' }}>
            <Landmark className="size-5" />
            <span className="ds-caption font-medium uppercase tracking-wide">The Future of Giving · LBBW</span>
          </div>
          <h1 className="ds-title-xl">
            You're ready for your{' '}
            <span className="text-ai">own foundation</span>
          </h1>
          <p className="ds-body text-muted-foreground">
            From your first flexible euro to a lasting institution. Legato turns the
            causes you've explored into a <span className="text-foreground font-medium">donor-advised fund</span> —
            your personal foundation, with the paperwork, governance and compliance fully delegated to LBBW.
          </p>
        </motion.div>

        {/* Journey recap */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.08 }}
          className="grid grid-cols-3 gap-4"
        >
          <RecapStat value={String(projects.length || '—')} label="Projects committed" />
          <RecapStat value={String(causes.length || '—')} label="Cause areas" />
          <RecapStat value={String(partners.length || '—')} label="Partner organisations" />
        </motion.div>

        {/* Foundation at a glance */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.16 }}
          className="rounded-2xl border border-border bg-card p-6 space-y-5"
        >
          <div className="flex items-center justify-between">
            <h2 className="ds-title-sm">Your Legato Foundation</h2>
            <span
              className="rounded-full px-3 py-1 ds-caption font-medium"
              style={{ backgroundColor: 'rgba(124,58,237,0.12)', color: '#7c3aed' }}
            >
              Managed by LBBW
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <GlanceFigure label="Starting endowment" value={formatEuro(ENDOWMENT)} accent="#14304A" />
            <GlanceFigure label="Annual grants" value={formatEuro(annualGrants)} accent="#059669" />
            <GlanceFigure label="Est. tax benefit" value={formatEuro(taxBenefit)} accent="#d97706" />
          </div>

          {causes.length > 0 && (
            <div className="space-y-2">
              <p className="ds-caption text-muted-foreground">Your foundation's focus</p>
              <div className="flex flex-wrap gap-2">
                {causes.map(c => (
                  <span key={c} className="rounded-full border border-border px-3 py-1 ds-caption">{c}</span>
                ))}
              </div>
            </div>
          )}

          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl py-3.5 ds-label text-white transition-transform active:scale-[0.98]"
            style={{ backgroundColor: '#7c3aed' }}
          >
            <Sparkles className="size-4" />
            Open my foundation with LBBW
            <ArrowRight className="size-4" />
          </button>
        </motion.div>

        {/* Why LBBW — the business logic */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.24 }}
          className="grid grid-cols-2 gap-4"
        >
          <ValueProp
            icon={ShieldCheck}
            title="Zero bureaucracy"
            body="LBBW handles legal setup, governance, reporting and compliance. You decide where the impact goes."
          />
          <ValueProp
            icon={TrendingUp}
            title="Your endowment, invested"
            body="Capital is managed under LBBW's sustainable mandate — assets under management that keep funding your causes."
          />
          <ValueProp
            icon={Receipt}
            title="Immediate tax benefits"
            body="Contributions are deductible from day one — give now, optimise later, with documentation handled for you."
          />
          <ValueProp
            icon={Landmark}
            title="A lasting legacy"
            body="A foundation in your name, your values, your impact — for this generation and the next."
          />
        </motion.div>

        {/* Pitch footnote */}
        <p className="ds-caption text-center text-muted-foreground/60">
          Prototype — figures are illustrative. The Legato journey converts flexible givers into
          long-term LBBW foundation clients: recurring AUM, deeper loyalty, measurable impact.
        </p>
      </div>
    </div>
  )
}

function RecapStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 text-center">
      <p className="ds-title-md" style={{ color: '#7c3aed' }}>{value}</p>
      <p className="ds-caption text-muted-foreground mt-1">{label}</p>
    </div>
  )
}

function GlanceFigure({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="space-y-1">
      <p className="ds-title-sm" style={{ color: accent }}>{value}</p>
      <p className="ds-caption text-muted-foreground">{label}</p>
    </div>
  )
}

function ValueProp({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Landmark
  title: string
  body: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-2">
      <Icon className="size-5" style={{ color: '#7c3aed' }} />
      <p className="ds-label">{title}</p>
      <p className="ds-small text-muted-foreground leading-relaxed">{body}</p>
    </div>
  )
}
