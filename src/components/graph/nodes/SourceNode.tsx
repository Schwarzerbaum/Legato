import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { GraduationCap, Building2 } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'
import { ACADEMIC, INDUSTRY } from '@/components/graph/colors'

interface SourceNodeData {
  sourceId: string
  label: string
  sublabel?: string
  isAcademic: boolean
  atMax?: boolean
}

export const SourceNode = memo(function SourceNode({ data }: { data: SourceNodeData }) {
  const { selectedSourceIds, toggleSource } = useAppStore()
  const isSelected = selectedSourceIds.includes(data.sourceId)
  const isDisabled = !isSelected && (data.atMax ?? false)
  const Icon = data.isAcademic ? GraduationCap : Building2

  const colors = data.isAcademic ? ACADEMIC : INDUSTRY

  return (
    <div
      onClick={isDisabled ? undefined : () => toggleSource(data.sourceId)}
      className={cn(
        'group relative flex w-[160px] cursor-pointer flex-col justify-center rounded-xl border px-4 py-3 shadow-sm select-none',
        'transition-all duration-150',
        isDisabled
          ? 'border-border bg-card text-muted-foreground opacity-35 cursor-not-allowed'
          : 'hover:shadow-md hover:scale-[1.03]'
      )}
      style={isSelected
        ? { borderColor: colors.border, backgroundColor: colors.selectedBg, color: '#fff' }
        : { borderColor: colors.border, backgroundColor: colors.bg, color: 'var(--foreground)' }
      }
    >
      <div className="flex items-center gap-1.5 mb-1">
        <Icon
          className="size-3 shrink-0"
          style={{ color: isSelected ? 'rgba(255,255,255,0.7)' : colors.text }}
        />
        <p className="ds-label leading-tight line-clamp-2">
          {data.label}
        </p>
      </div>
      {data.sublabel && (
        <p
          className="ds-caption leading-tight line-clamp-1"
          style={{ color: isSelected ? 'rgba(255,255,255,0.6)' : 'var(--muted-foreground)' }}
        >
          {data.sublabel}
        </p>
      )}
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})
