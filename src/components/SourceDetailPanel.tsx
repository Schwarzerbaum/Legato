import { motion } from 'framer-motion'
import { X, Bookmark, BookmarkCheck, Building2, GraduationCap, Globe, Mail, Briefcase, MapPin } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useAppStore } from '@/store/useAppStore'
import {
  supervisorById,
  companyById,
  foundationById,
  topics,
  fieldById,
  degreeLabel,
  workplaceLabel,
  employmentTypeLabel,
} from '@/data/index'

export function SourceDetailPanel() {
  const { activeSourceId, bookmarkedTopicIds, setActiveSource, setActiveTopic, toggleBookmark } = useAppStore()

  if (!activeSourceId) return null

  const foundation = foundationById[activeSourceId]
  const company = companyById[activeSourceId]
  // Fallback: supervisor (for any lingering double-clicks on supervisor nodes)
  const supervisor = !foundation && !company ? supervisorById[activeSourceId] : null

  if (!foundation && !company && !supervisor) return null

  // All topics from this source
  const sourceTopics = foundation
    ? topics.filter(t => t.foundationId === activeSourceId)
    : company
    ? topics.filter(t => t.companyId === activeSourceId)
    : topics.filter(t => t.supervisorIds.includes(activeSourceId))

  const isAcademic = !!foundation || !!supervisor

  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="fixed right-0 top-0 z-40 flex h-full w-96 flex-col border-l border-border bg-background shadow-2xl"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-border p-5">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {isAcademic
              ? <GraduationCap className="size-4 text-muted-foreground shrink-0" />
              : <Building2 className="size-4 text-muted-foreground shrink-0" />
            }
            <p className="ds-caption text-muted-foreground">
              {foundation ? 'Foundation' : supervisor ? 'Academic Supervisor' : 'Industry Partner'}
            </p>
          </div>
          <h2 className="ds-title-sm leading-snug">
            {foundation?.name ?? (supervisor
              ? `${supervisor.title} ${supervisor.firstName} ${supervisor.lastName}`
              : company?.name)}
          </h2>
          {supervisor && (
            <p className="ds-caption text-muted-foreground mt-0.5">
              {foundationById[supervisor.foundationId]?.name ?? ''}
            </p>
          )}
          {foundation && (
            <p className="ds-caption text-muted-foreground mt-0.5">{foundation.country}</p>
          )}
        </div>
        <button
          onClick={() => setActiveSource(null)}
          className="mt-0.5 shrink-0 flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* Foundation profile */}
        {foundation && (
          <>
            {foundation.domains.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {foundation.domains.map(d => (
                  <Badge key={d} variant="secondary" className="ds-caption">{d}</Badge>
                ))}
              </div>
            )}
            {foundation.about && (
              <p className="ds-small text-muted-foreground leading-relaxed">{foundation.about}</p>
            )}
            <div className="flex items-center gap-2 text-muted-foreground">
              <Globe className="size-3.5 shrink-0" />
              <p className="ds-caption">{foundation.country}</p>
            </div>
          </>
        )}

        {/* Supervisor profile */}
        {supervisor && (
          <>
            {supervisor.researchInterests.length > 0 && (
              <div className="space-y-2">
                <p className="ds-label">Research interests</p>
                <div className="flex flex-wrap gap-1.5">
                  {supervisor.researchInterests.map(r => (
                    <Badge key={r} variant="secondary" className="ds-caption">{r}</Badge>
                  ))}
                </div>
              </div>
            )}
            {supervisor.about && (
              <div className="space-y-1">
                <p className="ds-label">About</p>
                <p className="ds-small text-muted-foreground leading-relaxed">{supervisor.about}</p>
              </div>
            )}
            <div className="flex items-center gap-2 text-muted-foreground">
              <Mail className="size-3.5 shrink-0" />
              <p className="ds-caption truncate">{supervisor.email}</p>
            </div>
          </>
        )}

        {/* Company profile */}
        {company && (
          <>
            {company.domains.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {company.domains.map(d => (
                  <Badge key={d} variant="secondary" className="ds-caption">{d}</Badge>
                ))}
              </div>
            )}
            {company.description && (
              <p className="ds-small text-muted-foreground leading-relaxed">{company.description}</p>
            )}
            {company.about && (
              <div className="space-y-1">
                <p className="ds-label">Impact collaboration</p>
                <p className="ds-small text-muted-foreground leading-relaxed">{company.about}</p>
              </div>
            )}
          </>
        )}

        {/* All topics from this source */}
        <div className="space-y-3">
          <p className="ds-label">
            {sourceTopics.length} impact project{sourceTopics.length !== 1 ? "s" : ""}
          </p>
          {sourceTopics.map(topic => {
            const isBookmarked = bookmarkedTopicIds.includes(topic.id)
            const topicFields = topic.fieldIds.map(id => fieldById[id]).filter(Boolean)
            const supervisorName = topic.supervisorIds[0]
              ? `${supervisorById[topic.supervisorIds[0]]?.title ?? ''} ${supervisorById[topic.supervisorIds[0]]?.lastName ?? ''}`.trim()
              : null

            return (
              <div
                key={topic.id}
                className="rounded-xl border border-border p-3 space-y-2 hover:bg-secondary/40 transition-colors cursor-pointer"
                onClick={() => {
                  setActiveSource(null)
                  setActiveTopic(topic.id)
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    {foundation && supervisorName && (
                      <p className="ds-caption text-muted-foreground mb-0.5">{supervisorName}</p>
                    )}
                    <p className="ds-label leading-snug">{topic.title}</p>
                  </div>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      toggleBookmark(topic.id)
                    }}
                    className="shrink-0 flex size-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {isBookmarked
                      ? <BookmarkCheck className="size-3.5 text-foreground" />
                      : <Bookmark className="size-3.5" />
                    }
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {topic.degrees.map(d => (
                    <Badge key={d} variant="outline" className="ds-caption">{degreeLabel(d)}</Badge>
                  ))}
                  {topicFields.slice(0, 2).map(f => (
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
              </div>
            )
          })}
        </div>
      </div>
    </motion.aside>
  )
}
