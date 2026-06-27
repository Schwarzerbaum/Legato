import { AnimatePresence, motion } from 'framer-motion'
import { Bookmark, X } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { PhasesBar } from '@/components/PhasesBar'
import { PhasePanelTabs } from '@/components/PhasePanelTabs'
import { GraphView } from '@/components/graph/GraphView'
import { TopicDetailPanel } from '@/components/TopicDetailPanel'
import { SourceDetailPanel } from '@/components/SourceDetailPanel'
import { ComparePage } from '@/pages/ComparePage'
import { SearchPage } from '@/pages/SearchPage'
import { ConnectionsGraphPage } from '@/pages/ConnectionsGraphPage'
import { PlanPage } from '@/pages/PlanPage'
import { ImpactHubPage } from '@/pages/ImpactHubPage'
import { TaxBenefitsPage } from '@/pages/TaxBenefitsPage'
import { topicById, companyById, supervisorById, fieldById } from '@/data/index'
import { PHASES } from '@/data/phases'
import { Badge } from '@/components/ui/badge'

const PHASE1_PANELS = new Set(['graph', 'bookmarks', 'connections-graph', 'compare', 'search'])

function BookmarksView() {
  const { bookmarkedTopicIds, setActiveTopic, toggleBookmark } = useAppStore()

  if (bookmarkedTopicIds.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-2">
          <Bookmark className="size-8 mx-auto text-muted-foreground/40" />
          <p className="ds-label text-muted-foreground">Your shortlist is empty</p>
          <p className="ds-caption text-muted-foreground/60">
            Explore the graph and shortlist impact projects you care about
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="max-w-2xl space-y-4">
        <div className="space-y-1">
          <h1 className="header-sm">Shortlisted projects</h1>
          <p className="ds-caption text-muted-foreground">
            {bookmarkedTopicIds.length} project{bookmarkedTopicIds.length !== 1 ? 's' : ''} saved
          </p>
        </div>

        <AnimatePresence>
          {bookmarkedTopicIds.map(topicId => {
            const topic = topicById[topicId]
            if (!topic) return null
            const company = topic.companyId ? companyById[topic.companyId] : null
            const supervisor = topic.supervisorIds[0] ? supervisorById[topic.supervisorIds[0]] : null
            const sourceName = company?.name ?? (supervisor ? `${supervisor.title} ${supervisor.lastName}` : '')
            const topicFields = topic.fieldIds.map(id => fieldById[id]).filter(Boolean)

            return (
              <motion.div
                key={topicId}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.15 } }}
                className="group flex items-start gap-4 rounded-xl border border-border p-4 bg-card"
              >
                <div className="flex-1 min-w-0 space-y-2">
                  <div>
                    <p className="ds-caption text-muted-foreground">{sourceName}</p>
                    <h3 className="ds-label mt-0.5">{topic.title}</h3>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {topicFields.slice(0, 3).map(f => (
                      <Badge key={f!.id} variant="secondary" className="ds-caption">{f!.name}</Badge>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => setActiveTopic(topicId)}
                    className="ds-caption text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-secondary"
                  >
                    View
                  </button>
                  <motion.button
                    whileTap={{ scale: 0.85 }}
                    onClick={() => toggleBookmark(topicId)}
                    className="flex size-7 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                    aria-label="Remove bookmark"
                  >
                    <X className="size-3.5" />
                  </motion.button>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}

function PlaceholderView({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center space-y-2">
        <p className="ds-label text-muted-foreground">{label}</p>
        <p className="ds-caption text-muted-foreground/60">Coming soon</p>
      </div>
    </div>
  )
}

export function GraphPage() {
  const { currentPanel, currentPhase, activeTopicId, activeSourceId } = useAppStore()

  const phase = PHASES.find(p => p.id === currentPhase) ?? PHASES[0]
  const isPhase1Panel = PHASE1_PANELS.has(currentPanel)

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Main content area */}
      <div className="relative flex-1 overflow-hidden">
        {/* Pages */}
        <div className="absolute inset-0">
        <AnimatePresence mode="wait">
          {/* Phase 1 — Find */}
          {currentPanel === 'graph' && (
            <motion.div
              key="graph"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <GraphView />
            </motion.div>
          )}
          {currentPanel === 'bookmarks' && (
            <motion.div
              key="bookmarks"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <BookmarksView />
            </motion.div>
          )}
          {currentPanel === 'connections-graph' && (
            <motion.div
              key="connections-graph"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <ConnectionsGraphPage />
            </motion.div>
          )}
          {currentPanel === 'compare' && (
            <motion.div
              key="compare"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <ComparePage />
            </motion.div>
          )}
          {currentPanel === 'search' && (
            <motion.div
              key="search"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <SearchPage />
            </motion.div>
          )}

          {/* Phase 2 — Plan (distribution + forecast impact + companion) */}
          {currentPanel === 'plan' && (
            <motion.div
              key="plan"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <PlanPage />
            </motion.div>
          )}

          {/* Phase 3 — Impact Hub */}
          {currentPanel === 'impact-hub' && (
            <motion.div
              key="impact-hub"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <ImpactHubPage />
            </motion.div>
          )}

          {/* Phase 3 — Tax Benefits (Impact Hub sub-panel) */}
          {currentPanel === 'reviews' && (
            <motion.div
              key="reviews"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <TaxBenefitsPage />
            </motion.div>
          )}

          {/* Impact Hub sub-panel placeholder (Legacy) */}
          {!isPhase1Panel && currentPanel !== 'plan' && currentPanel !== 'impact-hub' && currentPanel !== 'reviews' && (
            <motion.div
              key={currentPanel}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full w-full"
            >
              <PlaceholderView label={phase.items.find(i => i.panel === currentPanel)?.label ?? currentPanel} />
            </motion.div>
          )}
        </AnimatePresence>
        </div>

        {/* Phase sub-panel tabs — overlaid at top (Impact Hub phase) */}
        {currentPhase === 3 && (
          <div className="absolute top-0 left-0 right-0 pointer-events-none">
            <div className="pointer-events-auto w-fit mx-auto">
              <PhasePanelTabs />
            </div>
          </div>
        )}

        {/* Phases bar — overlaid at bottom */}
        <div className="absolute bottom-0 left-0 right-0 pointer-events-none">
          <div className="pointer-events-auto w-fit mx-auto">
            <PhasesBar />
          </div>
        </div>
      </div>

      {/* Detail panels — only one visible at a time */}
      <AnimatePresence>
        {activeTopicId && <TopicDetailPanel key={`topic-${activeTopicId}`} />}
        {activeSourceId && <SourceDetailPanel key={`source-${activeSourceId}`} />}
      </AnimatePresence>
    </div>
  )
}
