import { Handle, Position } from "reactflow";
import type { Foundation } from "../../types/entities";
import { useActiveNodeId } from "../graph/MultiTopicFlow";

interface FoundationNodeProps {
  data: Foundation;
}

export default function FoundationNode({ data }: FoundationNodeProps) {
  const isActive = useActiveNodeId() === data.id;
  return (
    <div className={`bg-white rounded-xl shadow-lg p-5 w-[320px] border-2 transition-colors ${isActive ? "border-amber-500" : "border-amber-200"}`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />

      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-semibold text-gray-900">{data.name}</h3>
        <span className="shrink-0 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
          Foundation
        </span>
      </div>

      <a
        href={`https://${data.domains[0]}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-amber-600 hover:text-amber-700 hover:underline"
      >
        {data.domains[0]} ↗
      </a>

      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}
