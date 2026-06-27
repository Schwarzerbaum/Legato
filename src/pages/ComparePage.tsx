import { motion, AnimatePresence } from 'framer-motion'
import {
  Bookmark, ChevronUp, ChevronDown, X, GraduationCap, Building2,
  MapPin, Briefcase, Plus,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useAppStore } from '@/store/useAppStore'
import {
  topicById, companyById, supervisorById, foundationById, fieldById,
  degreeLabel, workplaceLabel, employmentTypeLabel,
} from '@/data/index'
import { ACADEMIC, INDUSTRY } from '@/components/graph/colors'

// ─── Compare slot card ────────────────────────────────────────────────────────

function CompareCard({ topicId, slot }: { topicId: string | null; slot: 'A' | 'B' }) {
  const { setActiveTopic, toggleCompare } = useAppStore()
  const colors = slot === 'A' ? ACADEMIC : INDUSTRY

  if (!topicId) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border min-h-[280px] p-8 text-center"
        style={{ borderColor: colors.muted }}
      >
        <div
          className="flex size-10 items-center justify-center rounded-full mb-3"
          style={{ backgroundColor: colors.bg }}
        >
          <Plus className="size-5" style={{ color: colors.text }} />
        </div>
        <p
          className="ds-label"
          style={{ color: colors.text }}
        >
          Project {slot}
        </p>
        <p className="ds-caption text-muted-foreground mt-1">
          Select from your bookmarks below
        </p>
      </div>
    )
  }

  const topic = topicById[topicId]
  if (!topic) return null

  const company = topic.companyId ? companyById[topic.companyId] : null
  const supervisor = topic.supervisorIds[0] ? supervisorById[topic.supervisorIds[0]] : null
  const foundation = topic.foundationId ? foundationById[topic.foundationId] : null
  const isAcademic = !topic.companyId
  const nodeColors = isAcademic ? ACADEMIC : INDUSTRY
  const Icon = isAcademic ? GraduationCap : Building2
  const topicFields = topic.fieldIds.map(id => fieldById[id]).filter(Boolean)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative flex flex-col rounded-2xl border p-5 space-y-4"
      style={{ borderColor: nodeColors.border, backgroundColor: nodeColors.bg }}
    >
      {/* Slot label + remove */}
      <div className="flex items-center justify-between">
        <span
          className="ds-caption font-semibold px-2 py-0.5 rounded-md"
          style={{ backgroundColor: nodeColors.selectedBg, color: '#fff' }}
        >
          Project {slot}
        </span>
        <button
          onClick={() => toggleCompare(topicId)}
          className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          <X className="size-3.5" />
        </button>
      </div>

      {/* Source */}
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 shrink-0" style={{ color: nodeColors.text }} />
        <p className="ds-caption leading-tight" style={{ color: nodeColors.text }}>
          {company?.name ?? (supervisor ? `${supervisor.title} ${supervisor.lastName}` : foundation?.name ?? '')}
        </p>
      </div>

      {/* Title */}
      <h3 className="ds-label leading-snug">{topic.title}</h3>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5">
        {topic.degrees.map(d => (
          <Badge key={d} variant="outline" className="ds-caption">{degreeLabel(d)}</Badge>
        ))}
        {topicFields.map(f => (
          <Badge key={f.id} variant="secondary" className="ds-caption">{f.name}</Badge>
        ))}
        {topic.workplaceType && (
          <Badge variant="outline" className="ds-caption flex items-center gap-1">
            <MapPin className="size-2.5" />{workplaceLabel(topic.workplaceType)}
          </Badge>
        )}
        {topic.employmentType && (
          <Badge variant="outline" className="ds-caption flex items-center gap-1">
            <Briefcase className="size-2.5" />{employmentTypeLabel(topic.employmentType)}
          </Badge>
        )}
      </div>

      {/* Description */}
      <p className="ds-small text-muted-foreground leading-relaxed line-clamp-4">
        {topic.description}
      </p>

      {/* View full details */}
      <button
        onClick={() => setActiveTopic(topicId)}
        className="mt-auto ds-caption text-left hover:underline transition-colors"
        style={{ color: nodeColors.text }}
      >
        View full details →
      </button>
    </motion.div>
  )
}

// ─── Ranked bookmark row ──────────────────────────────────────────────────────

function BookmarkRow({ topicId, rank }: { topicId: string; rank: number }) {
  const {
    bookmarkedTopicIds, compareTopicIds,
    moveBookmark, toggleBookmark, toggleCompare, setActiveTopic,
  } = useAppStore()

  const topic = topicById[topicId]
  if (!topic) return null

  const company = topic.companyId ? companyById[topic.companyId] : null
  const supervisor = topic.supervisorIds[0] ? supervisorById[topic.supervisorIds[0]] : null
  const sourceName = company?.name ?? (supervisor ? `${supervisor.title} ${supervisor.lastName}` : '')
  const isAcademic = !topic.companyId
  const colors = isAcademic ? ACADEMIC : INDUSTRY
  const isFirst = rank === 1
  const isLast = rank === bookmarkedTopicIds.length

  const [slotA, slotB] = compareTopicIds
  const inSlotA = slotA === topicId
  const inSlotB = slotB === topicId
  const inCompare = inSlotA || inSlotB

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.12 } }}
      className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3"
    >
      {/* Rank + reorder */}
      <div className="flex flex-col items-center gap-0.5 w-6 shrink-0">
        <button
          onClick={() => moveBookmark(topicId, 'up')}
          disabled={isFirst}
          className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
        >
          <ChevronUp className="size-3.5" />
        </button>
        <span className="ds-caption text-muted-foreground font-medium leading-none">{rank}</span>
        <button
          onClick={() => moveBookmark(topicId, 'down')}
          disabled={isLast}
          className="flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
        >
          <ChevronDown className="size-3.5" />
        </button>
      </div>

      {/* Color accent bar */}
      <div className="w-1 self-stretch rounded-full shrink-0" style={{ backgroundColor: colors.border }} />

      {/* Topic info */}
      <div className="flex-1 min-w-0">
        <p className="ds-caption text-muted-foreground truncate">{sourceName}</p>
        <p className="ds-label leading-snug mt-0.5 line-clamp-1">{topic.title}</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Compare toggle */}
        <button
          onClick={() => toggleCompare(topicId)}
          className="ds-caption px-2.5 py-1 rounded-lg border transition-colors"
          style={inCompare
            ? { borderColor: colors.border, backgroundColor: colors.selectedBg, color: '#fff' }
            : { borderColor: 'var(--border)', color: 'var(--muted-foreground)' }
          }
        >
          {inSlotA ? 'A' : inSlotB ? 'B' : 'Compare'}
        </button>

        <button
          onClick={() => setActiveTopic(topicId)}
          className="ds-caption text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-secondary"
        >
          View
        </button>

        <button
          onClick={() => toggleBookmark(topicId)}
          className="flex size-7 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          aria-label="Remove bookmark"
        >
          <X className="size-3.5" />
        </button>
      </div>
    </motion.div>
  )
}

// ─── Compare page ─────────────────────────────────────────────────────────────

export function ComparePage() {
  const { bookmarkedTopicIds, compareTopicIds } = useAppStore()
  const [slotA, slotB] = compareTopicIds

  if (bookmarkedTopicIds.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-2">
          <Bookmark className="size-8 mx-auto text-muted-foreground/40" />
          <p className="ds-label text-muted-foreground">No bookmarks yet</p>
          <p className="ds-caption text-muted-foreground/60">
            Explore the graph and shortlist impact projects to compare them here
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-8 py-8 space-y-8">

        {/* Header */}
        <div className="space-y-1">
          <h1 className="header-sm">Compare Projects</h1>
          <p className="ds-caption text-muted-foreground">
            Pick two projects from your shortlist to compare side by side
          </p>
        </div>

        {/* Comparison slots */}
        <div className="grid grid-cols-2 gap-5">
          <CompareCard topicId={slotA} slot="A" />
          <CompareCard topicId={slotB} slot="B" />
        </div>

        {/* Ranked bookmarks */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="ds-label">
              Your bookmarks
              <span className="ml-2 ds-caption text-muted-foreground font-normal">
                ranked by priority
              </span>
            </h2>
            <p className="ds-caption text-muted-foreground">
              {bookmarkedTopicIds.length} saved
            </p>
          </div>

          <AnimatePresence>
            {bookmarkedTopicIds.map((id, i) => (
              <BookmarkRow key={id} topicId={id} rank={i + 1} />
            ))}
          </AnimatePresence>
        </div>

      </div>
    </div>
  )
}
