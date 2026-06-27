import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Sparkles } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'

interface FieldNodeData {
  fieldId: string
  label: string
  atMax?: boolean
  suggested?: boolean
  hasSuggestions?: boolean
}

export const FieldNode = memo(function FieldNode({ data }: { data: FieldNodeData }) {
  const { selectedFieldIds, toggleField } = useAppStore()
  const isSelected = selectedFieldIds.includes(data.fieldId)
  const isDisabled = !isSelected && (data.atMax ?? false)
  const isSuggested = data.suggested ?? false
  const hasSuggestions = data.hasSuggestions ?? false
  // Dim non-suggested when suggestions are loaded and this field isn't suggested and isn't selected
  const isDimmed = hasSuggestions && !isSuggested && !isSelected

  return (
    <div
      onClick={isDisabled ? undefined : () => toggleField(data.fieldId)}
      className={cn(
        'group relative flex items-center justify-center rounded-xl border px-4 py-2.5 shadow-sm select-none',
        'min-w-32.5 text-center transition-all duration-150',
        isSelected
          ? 'border-foreground bg-foreground text-background cursor-pointer'
          : isDisabled
          ? 'border-border bg-card text-muted-foreground opacity-35 cursor-not-allowed'
          : isSuggested
          ? 'border-amber-400 bg-amber-50 text-amber-900 ring-1 ring-amber-300/60 cursor-pointer hover:border-amber-500 hover:shadow-md hover:scale-[1.03]'
          : isDimmed
          ? 'border-border bg-card text-muted-foreground opacity-50 cursor-pointer hover:opacity-80 hover:border-foreground/40'
          : 'border-border bg-card text-foreground cursor-pointer hover:border-foreground/40 hover:shadow-md hover:scale-[1.03]'
      )}
    >
      {isSuggested && !isSelected && (
        <span className="absolute -top-1.5 -right-1.5 flex size-4 items-center justify-center rounded-full bg-amber-500 shadow-sm">
          <Sparkles className="size-2.5 text-white" />
        </span>
      )}
      <span className="ds-label leading-tight">{data.label}</span>
      <Handle type="source" position={Position.Top} className="opacity-0 w-0! h-0!" />
      <Handle type="target" position={Position.Top} className="opacity-0 w-0! h-0!" />
    </div>
  )
})
