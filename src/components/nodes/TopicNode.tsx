import { Handle, Position } from "reactflow"
import type { Topic } from "../../types/topic"
import { useActiveNodeId } from "../graph/MultiTopicFlow"

const employmentTypeLabel: Record<string, string> = {
  internship: "Internship",
  working_student: "Working Student",
  graduate_program: "Graduate Program",
  direct_entry: "Direct Entry",
}

const workplaceLabel: Record<string, string> = {
  on_site: "On-site",
  hybrid: "Hybrid",
  remote: "Remote",
}

const degreeLabel: Record<string, string> = {
  bsc: "BSc",
  msc: "MSc",
  phd: "PhD",
}

interface TopicNodeProps {
  data: Topic & { fieldNames: string[]; expanded: boolean; onToggle: () => void }
}

export default function TopicNode({ data }: TopicNodeProps) {
  const activeId = useActiveNodeId()
  const isActive = activeId === data.id
  const isJob = data.type === "job"

  return (
    <div className={`bg-white rounded-xl shadow-lg p-5 w-[420px] border-2 transition-colors ${isActive ? "border-gray-500" : "border-gray-200"}`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />

      <div className="flex items-start justify-between gap-3 mb-3">
        <h2 className="text-base font-semibold text-gray-900 leading-snug">{data.title}</h2>
        <span
          className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
            isJob
              ? "bg-purple-100 text-purple-700"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {isJob ? "Job" : "Topic"}
        </span>
      </div>

      {(data.employmentType || data.workplaceType) && (
        <p className="text-xs text-gray-400 mb-3">
          {[data.employmentType && employmentTypeLabel[data.employmentType], data.workplaceType && workplaceLabel[data.workplaceType]].filter(Boolean).join(" · ")}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5 mb-3">
        {data.degrees.map((d) => (
          <span
            key={d}
            className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium"
          >
            {degreeLabel[d]}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        {data.fieldNames.map((name) => (
          <span
            key={name}
            className="text-xs px-2 py-0.5 rounded-full bg-gray-50 text-gray-500 border border-gray-200"
          >
            {name}
          </span>
        ))}
      </div>

      <button
        onClick={(e) => { e.stopPropagation(); data.onToggle(); }}
        className="w-full text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors flex items-center justify-center gap-1"
      >
        {data.expanded ? "▲ Hide Details" : "▼ Show Details"}
      </button>

      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  )
}
