import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { useAppStore } from '@/store/useAppStore'

export const CenterNode = memo(function CenterNode() {
  // The two onboarding slots now hold the giver's motivation + giving style.
  const { giverMotivation: motivation, giverStyle: givingStyle } = useAppStore()

  return (
    <div className="relative flex flex-col items-center justify-center rounded-2xl border border-border bg-card px-6 py-4 shadow-md min-w-[160px] text-center transition-shadow hover:shadow-lg">
      <div className="ds-badge uppercase tracking-wider text-muted-foreground mb-1">
        Your Giving
      </div>
      <div className="ds-label">{motivation ?? 'You'}</div>
      {givingStyle && (
        <div className="ds-caption text-muted-foreground mt-0.5 max-w-[140px] leading-tight">
          {givingStyle}
        </div>
      )}
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})
