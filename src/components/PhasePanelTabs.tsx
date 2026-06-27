import { useAppStore } from '@/store/useAppStore'
import { PHASES } from '@/data/phases'

// Secondary navigation: switches between the panels *within* the current phase
// (the bottom PhasesBar only switches between phases). Floats at top-centre,
// mirroring the PhasesBar styling.
export function PhasePanelTabs() {
  const { currentPhase, currentPanel, setCurrentPanel } = useAppStore()
  const phase = PHASES.find(p => p.id === currentPhase)
  if (!phase || phase.items.length < 2) return null

  return (
    <div className="flex shrink-0 items-center justify-center py-3">
      <div className="flex items-center gap-1 rounded-full border border-border/60 bg-background/75 px-1.5 py-1.5 shadow-lg backdrop-blur-md">
        {phase.items.map(item => {
          const isActive = currentPanel === item.panel
          const Icon = item.icon
          return (
            <button
              key={item.panel}
              onClick={() => setCurrentPanel(item.panel)}
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 ds-caption font-medium transition-all duration-150"
              style={
                isActive
                  ? { backgroundColor: phase.color, color: '#fff' }
                  : { color: 'var(--muted-foreground)' }
              }
            >
              <Icon className="size-3.5" />
              {item.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
