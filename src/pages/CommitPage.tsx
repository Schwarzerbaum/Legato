import { motion, AnimatePresence } from 'framer-motion'
import { Target, Check, Bookmark, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { topicById, companyById, foundationById, fieldById, fundingPct, formatEuro } from '@/data/index'
import type { Topic } from '@/data/index'

const ACCENT = '#0d9488' // phase-2 (Commit) accent

function partnerName(t: Topic): string {
  if (t.companyId) return companyById[t.companyId]?.name ?? ''
  if (t.foundationId) return foundationById[t.foundationId]?.name ?? ''
  return ''
}

function ProjectRow({
  topic,
  committed,
  onToggle,
  onView,
}: {
  topic: Topic
  committed: boolean
  onToggle: () => void
  onView: () => void
}) {
  const causes = topic.fieldIds.map(id => fieldById[id]?.name).filter(Boolean).slice(0, 2) as string[]
  const pct = fundingPct(topic)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.15 } }}
      className="space-y-3 rounded-xl border border-border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <button onClick={onView} className="min-w-0 flex-1 space-y-1 text-left">
          <p className="ds-caption text-muted-foreground">{partnerName(topic)}</p>
          <h3 className="ds-label leading-tight">{topic.title}</h3>
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {causes.map(c => (
              <span key={c} className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground">{c}</span>
            ))}
          </div>
        </button>

        <button
          onClick={onToggle}
          className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 ds-caption font-medium transition"
          style={
            committed
              ? { backgroundColor: ACCENT, color: '#fff' }
              : { border: `1px solid ${ACCENT}`, color: ACCENT }
          }
        >
          {committed ? <><Check className="size-3.5" /> Committed</> : <><Target className="size-3.5" /> Commit</>}
        </button>
      </div>

      {/* funding progress */}
      <div className="space-y-1">
        <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: ACCENT }} />
        </div>
        <div className="flex justify-between ds-caption text-muted-foreground">
          <span>{formatEuro(topic.fundingRaised)} of {formatEuro(topic.fundingGoal)}</span>
          <span>{pct}% funded</span>
        </div>
      </div>
    </motion.div>
  )
}

export function CommitPage() {
  const {
    bookmarkedTopicIds,
    committedTopicIds,
    toggleCommitment,
    setActiveTopic,
    setCurrentPhase,
  } = useAppStore()

  const committed = committedTopicIds.map(id => topicById[id]).filter(Boolean)
  const shortlist = bookmarkedTopicIds
    .filter(id => !committedTopicIds.includes(id))
    .map(id => topicById[id])
    .filter(Boolean)

  const empty = committed.length === 0 && shortlist.length === 0

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-8 px-8 py-12 pb-28">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2" style={{ color: ACCENT }}>
            <Target className="size-5" />
            <span className="ds-caption font-medium uppercase tracking-wide">Phase 2 · Commit</span>
          </div>
          <h1 className="ds-title-xl">Your giving portfolio</h1>
          <p className="ds-body text-muted-foreground">
            Turn the projects you shortlisted into commitments. Commit to as many as
            you like — your portfolio unlocks the Plan, Impact and Impact Hub phases.
          </p>
        </div>

        {empty && (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-12 text-center">
            <Bookmark className="size-8 text-muted-foreground/40" />
            <p className="ds-label text-muted-foreground">Nothing here yet</p>
            <p className="ds-caption max-w-xs text-muted-foreground/60">
              Explore the graph, shortlist the impact projects you care about, then
              commit to them here.
            </p>
            <button
              onClick={() => setCurrentPhase(1)}
              className="mt-1 flex items-center gap-1.5 rounded-lg px-3 py-1.5 ds-caption font-medium text-white"
              style={{ backgroundColor: ACCENT }}
            >
              Back to Explore <ArrowRight className="size-3.5" />
            </button>
          </div>
        )}

        {/* Committed portfolio */}
        {committed.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between px-0.5">
              <span className="ds-label">Committed · {committed.length}</span>
              <button
                onClick={() => setCurrentPhase(3)}
                className="flex items-center gap-1.5 ds-caption font-medium transition-colors"
                style={{ color: ACCENT }}
              >
                Continue to Plan <ArrowRight className="size-3.5" />
              </button>
            </div>
            <AnimatePresence>
              {committed.map(t => (
                <ProjectRow
                  key={t.id}
                  topic={t}
                  committed
                  onToggle={() => toggleCommitment(t.id)}
                  onView={() => setActiveTopic(t.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* Shortlist — ready to commit */}
        {shortlist.length > 0 && (
          <div className="space-y-3">
            <span className="ds-label px-0.5">Shortlisted · ready to commit · {shortlist.length}</span>
            <AnimatePresence>
              {shortlist.map(t => (
                <ProjectRow
                  key={t.id}
                  topic={t}
                  committed={false}
                  onToggle={() => toggleCommitment(t.id)}
                  onView={() => setActiveTopic(t.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}
