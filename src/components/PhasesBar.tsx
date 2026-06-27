import { ChevronRight } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { PHASES } from '@/data/phases'

export function PhasesBar() {
  const { currentPhase, setCurrentPhase, committedTopicIds } = useAppStore()
  const hasCommitments = committedTopicIds.length > 0

  return (
    <div className="flex shrink-0 items-center justify-center py-3">
      <div className="flex items-center gap-1 rounded-full border border-border/60 bg-background/75 px-3 py-2 shadow-lg backdrop-blur-md">
        {PHASES.map((phase, idx) => {
          const isActive = currentPhase === phase.id
          const notClickable =
            phase.disabled ||
            ((phase.id === 2 || phase.id === 3) && !hasCommitments)
          return (
            <div key={phase.id} className="flex items-center gap-1">
              {idx > 0 && (
                <ChevronRight className="size-3 shrink-0 text-muted-foreground/30" />
              )}
              <button
                onClick={notClickable ? undefined : () => setCurrentPhase(phase.id)}
                disabled={notClickable}
                className="rounded-full px-3 py-1 ds-caption font-medium transition-all duration-150"
                style={
                  isActive
                    ? { backgroundColor: phase.color, color: '#fff' }
                    : notClickable
                    ? { color: 'var(--muted-foreground)', opacity: 0.4, cursor: 'not-allowed' }
                    : { color: 'var(--muted-foreground)' }
                }
              >
                {idx + 1}. {phase.name}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
