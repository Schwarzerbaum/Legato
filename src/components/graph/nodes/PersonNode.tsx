import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { User } from 'lucide-react'

interface PersonNodeData {
  name: string
  role: string   // 'Supervisor' | 'Advisor'
  color: string
  lightBg: string
}

export const PersonNode = memo(function PersonNode({ data }: { data: PersonNodeData }) {
  return (
    <div
      className="rounded-xl border px-3 py-2 shadow-sm select-none"
      style={{
        minWidth: 150,
        borderColor: data.color,
        backgroundColor: data.lightBg,
        borderLeft: `3px solid ${data.color}`,
      }}
    >
      <div className="flex items-center gap-1.5">
        <User className="size-3 shrink-0" style={{ color: data.color }} />
        <span className="ds-caption font-semibold leading-tight truncate" style={{ color: data.color }}>
          {data.role}
        </span>
      </div>
      <p className="ds-caption leading-snug mt-0.5 line-clamp-2 text-foreground">{data.name}</p>
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})
