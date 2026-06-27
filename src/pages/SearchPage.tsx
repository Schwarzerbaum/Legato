import { useState, useMemo } from 'react'
import { Search, GraduationCap, Building2, MapPin, Target, Bookmark, BookmarkCheck, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useAppStore } from '@/store/useAppStore'
import {
  topics, fields, companyById, supervisorById, foundationById, fieldById,
  formatEuro, fundingPct,
} from '@/data/index'
import { ACADEMIC, INDUSTRY } from '@/components/graph/colors'

// ─── Filter chip ──────────────────────────────────────────────────────────────

function FilterChip({
  label, active, onClick, icon, color,
}: {
  label: string
  active: boolean
  onClick: () => void
  icon?: React.ReactNode
  color?: { border: string; bg: string; text: string; selectedBg: string }
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 ds-caption transition-all select-none"
      style={active && color
        ? { borderColor: color.border, backgroundColor: color.selectedBg, color: '#fff' }
        : active
        ? { borderColor: 'var(--foreground)', backgroundColor: 'var(--foreground)', color: 'var(--background)' }
        : { borderColor: 'var(--border)', backgroundColor: 'transparent', color: 'var(--muted-foreground)' }
      }
    >
      {icon}
      {label}
    </button>
  )
}

// ─── Result card ──────────────────────────────────────────────────────────────

function TopicCard({ topicId }: { topicId: string }) {
  const { bookmarkedTopicIds, toggleBookmark, setActiveTopic } = useAppStore()
  const topic = topics.find(t => t.id === topicId)!
  const isBookmarked = bookmarkedTopicIds.includes(topicId)

  const company = topic.companyId ? companyById[topic.companyId] : null
  const supervisor = topic.supervisorIds[0] ? supervisorById[topic.supervisorIds[0]] : null
  const foundation = topic.foundationId ? foundationById[topic.foundationId] : null
  const isAcademic = !topic.companyId
  const colors = isAcademic ? ACADEMIC : INDUSTRY
  const Icon = isAcademic ? GraduationCap : Building2

  const sourceName = company?.name
    ?? (supervisor ? `${supervisor.title} ${supervisor.lastName}` : '')
  const institutionName = isAcademic ? (foundation?.name ?? '') : (company?.domains.slice(0, 2).join(', ') ?? '')

  const topicFields = topic.fieldIds.map(id => fieldById[id]).filter(Boolean)

  return (
    <div
      className="group rounded-xl border bg-card p-5 space-y-3 cursor-pointer hover:shadow-md transition-all"
      style={{ borderColor: colors.border }}
      onClick={() => setActiveTopic(topicId)}
    >
      {/* Source row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="flex size-6 shrink-0 items-center justify-center rounded-md"
            style={{ backgroundColor: colors.bg, border: `1px solid ${colors.border}` }}
          >
            <Icon className="size-3.5" style={{ color: colors.text }} />
          </div>
          <div className="min-w-0">
            <p className="ds-caption font-medium leading-tight truncate" style={{ color: colors.text }}>
              {sourceName}
            </p>
            {institutionName && (
              <p className="ds-caption text-muted-foreground/70 leading-tight truncate">{institutionName}</p>
            )}
          </div>
        </div>
        <button
          onClick={e => { e.stopPropagation(); toggleBookmark(topicId) }}
          className="shrink-0 flex size-7 items-center justify-center rounded-lg transition-colors text-muted-foreground hover:text-foreground hover:bg-secondary"
          aria-label={isBookmarked ? 'Remove bookmark' : 'Bookmark'}
        >
          {isBookmarked
            ? <BookmarkCheck className="size-4 text-foreground" />
            : <Bookmark className="size-4" />
          }
        </button>
      </div>

      {/* Title */}
      <h3 className="ds-label leading-snug">{topic.title}</h3>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5">
        {topicFields.slice(0, 3).map(f => (
          <Badge key={f.id} variant="secondary" className="ds-caption">{f.name}</Badge>
        ))}
        <Badge variant="outline" className="ds-caption flex items-center gap-1">
          <MapPin className="size-2.5" />{topic.region}
        </Badge>
        <Badge variant="outline" className="ds-caption flex items-center gap-1">
          <Target className="size-2.5" />SDG {topic.sdg}
        </Badge>
      </div>

      {/* Description */}
      <p className="ds-small text-muted-foreground leading-relaxed line-clamp-2">
        {topic.description}
      </p>

      {/* Funding progress */}
      <div className="flex items-center gap-2 pt-1">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
          <div className="h-full rounded-full" style={{ width: `${fundingPct(topic)}%`, backgroundColor: '#059669' }} />
        </div>
        <span className="ds-caption text-muted-foreground shrink-0">
          {formatEuro(topic.fundingRaised)} / {formatEuro(topic.fundingGoal)}
        </span>
      </div>
    </div>
  )
}

// ─── Search page ──────────────────────────────────────────────────────────────

type FilterType = 'academic' | 'industry'

function toggle<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]
}

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [types, setTypes] = useState<FilterType[]>([])
  const [fieldIds, setFieldIds] = useState<string[]>([])
  const [showAllFields, setShowAllFields] = useState(false)

  const hasFilters = query || types.length || fieldIds.length

  const filtered = useMemo(() => {
    return topics.filter(t => {
      if (query) {
        const q = query.toLowerCase()
        if (!t.title.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q)) return false
      }
      if (types.length) {
        const isAcademic = !t.companyId
        if (!types.some(tp => (tp === 'academic' && isAcademic) || (tp === 'industry' && !isAcademic))) return false
      }
      if (fieldIds.length && !t.fieldIds.some(fid => fieldIds.includes(fid))) return false
      return true
    })
  }, [query, types, fieldIds])

  const visibleFields = showAllFields ? fields : fields.slice(0, 10)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-8 py-8 space-y-6">

        {/* Header */}
        <div className="space-y-1">
          <h1 className="header-sm">Search Projects</h1>
          <p className="ds-caption text-muted-foreground">
            Filter through all impact projects
          </p>
        </div>

        {/* Search bar */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search by title or keyword…"
            className="w-full rounded-xl border border-border bg-card pl-10 pr-10 py-2.5 ds-label placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-foreground/20 transition-shadow"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="space-y-3 rounded-xl border border-border bg-card p-4">

          {/* Type */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="ds-caption text-muted-foreground w-20 shrink-0">Run by</span>
            <div className="flex flex-wrap gap-1.5">
              <FilterChip
                label="Foundations & NGOs"
                active={types.includes('academic')}
                onClick={() => setTypes(prev => toggle(prev, 'academic'))}
                icon={<GraduationCap className="size-3" />}
                color={ACADEMIC}
              />
              <FilterChip
                label="Corporate Partners"
                active={types.includes('industry')}
                onClick={() => setTypes(prev => toggle(prev, 'industry'))}
                icon={<Building2 className="size-3" />}
                color={INDUSTRY}
              />
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Cause */}
          <div className="flex items-start gap-3">
            <span className="ds-caption text-muted-foreground w-20 shrink-0 pt-1">Cause</span>
            <div className="flex flex-wrap gap-1.5">
              {visibleFields.map(f => (
                <FilterChip
                  key={f.id}
                  label={f.name}
                  active={fieldIds.includes(f.id)}
                  onClick={() => setFieldIds(prev => toggle(prev, f.id))}
                />
              ))}
              <button
                onClick={() => setShowAllFields(v => !v)}
                className="ds-caption text-muted-foreground hover:text-foreground transition-colors px-1"
              >
                {showAllFields ? '↑ Show less' : `+${fields.length - 10} more`}
              </button>
            </div>
          </div>

          {/* Clear filters */}
          {hasFilters && (
            <>
              <div className="h-px bg-border" />
              <button
                onClick={() => { setQuery(''); setTypes([]); setFieldIds([]) }}
                className="ds-caption text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
              >
                <X className="size-3" /> Clear all filters
              </button>
            </>
          )}
        </div>

        {/* Results count */}
        <p className="ds-caption text-muted-foreground">
          {filtered.length} project{filtered.length !== 1 ? "s" : ""}
          {hasFilters ? ' matching your filters' : ' available'}
        </p>

        {/* Results */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center space-y-2">
            <Search className="size-8 text-muted-foreground/40" />
            <p className="ds-label text-muted-foreground">No projects found</p>
            <p className="ds-caption text-muted-foreground/60">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="space-y-3 pb-8">
            {filtered.map(t => (
              <TopicCard key={t.id} topicId={t.id} />
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
