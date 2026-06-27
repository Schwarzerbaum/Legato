import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { useAppStore } from '@/store/useAppStore'
import { themeByKey } from '@/data/themes'

export const CenterNode = memo(function CenterNode() {
  const { selectedThemeKeys, activeThemeKey, giverStyle: givingStyle } = useAppStore()

  // The center reflects the theme whose map is currently on screen.
  const activeKey = selectedThemeKeys.includes(activeThemeKey ?? '')
    ? activeThemeKey
    : (selectedThemeKeys[0] ?? null)
  const motivation = activeKey ? (themeByKey[activeKey]?.label ?? 'You') : 'You'

  return (
    <div className="relative flex flex-col items-center justify-center rounded-2xl border border-border bg-card px-6 py-4 shadow-md min-w-[160px] text-center transition-shadow hover:shadow-lg">
      <div className="ds-badge uppercase tracking-wider text-muted-foreground mb-1">
        Your Giving
      </div>
      <div className="ds-label">{motivation}</div>
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
