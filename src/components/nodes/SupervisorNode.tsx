import { Handle, Position } from "reactflow"
import type { Supervisor } from "../../types/entities"
import { useActiveNodeId } from "../graph/MultiTopicFlow"

interface SupervisorNodeProps {
  data: Supervisor & { fieldNames: string[] }
}

export default function SupervisorNode({ data }: SupervisorNodeProps) {
  const isActive = useActiveNodeId() === data.id
  return (
    <div className={`bg-white rounded-xl shadow-lg p-5 w-[320px] border-2 transition-colors ${isActive ? "border-violet-500" : "border-violet-200"}`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />

      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-semibold text-gray-900">{data.title} {data.firstName} {data.lastName}</h3>
        <span className="shrink-0 text-xs font-medium px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">
          Supervisor
        </span>
      </div>
      {data.researchInterests.length > 0 && (
        <p className="text-xs text-gray-400 mb-2">
          {data.researchInterests.slice(0, 2).map((r) => r.replace(/\b\w/g, (c) => c.toUpperCase())).join(" · ")}
        </p>
      )}
      <p className="text-xs text-violet-600 mb-2">{data.email}</p>

      <div className="flex flex-wrap gap-1.5 mb-2">
        {data.researchInterests.map((interest) => (
          <span
            key={interest}
            className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200"
          >
            {interest.replace(/\b\w/g, (c) => c.toUpperCase())}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {data.fieldNames.map((name) => (
          <span
            key={name}
            className="text-xs px-2 py-0.5 rounded-full bg-gray-50 text-gray-500 border border-gray-200"
          >
            {name}
          </span>
        ))}
      </div>

      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  )
}
