import { Handle, Position } from "reactflow"
import { X } from "lucide-react"

export interface ResearchNodeData {
  id: string
  text: string
  description: string
  color: string
  isRoot?: boolean
  isProject?: boolean
  isSelected?: boolean
  onDelete?: (id: string) => void
  onSelect?: (id: string) => void
  onOpenCompanion?: () => void
}

export function ResearchNode({ data }: { data: ResearchNodeData }) {
  return (
    <div
      onClick={() => data.onSelect?.(data.id)}
      className="bg-white rounded-xl shadow-md w-[220px] relative overflow-hidden cursor-pointer transition-shadow hover:shadow-lg"
      style={{
        borderLeft: `4px solid ${data.color}`,
        boxShadow: data.isSelected
          ? `0 0 0 2px ${data.color}, 0 4px 16px 0 ${data.color}33`
          : undefined,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-300" />

      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="font-semibold text-sm text-gray-900 leading-snug">{data.text}</p>
          {!data.isRoot && (
            <button
              onClick={(e) => { e.stopPropagation(); data.onDelete?.(data.id) }}
              className="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors mt-0.5"
              title="Delete node"
            >
              <X size={14} />
            </button>
          )}
        </div>
        {data.description && (
          <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">{data.description}</p>
        )}
        {data.isProject && data.onOpenCompanion && (
          <button
            onClick={(e) => { e.stopPropagation(); data.onOpenCompanion!() }}
            className="mt-2 w-full text-xs font-medium px-2 py-1 rounded-lg bg-slate-900 text-white hover:bg-slate-700 transition-colors"
          >
            Companion →
          </button>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-gray-300" />
    </div>
  )
}
