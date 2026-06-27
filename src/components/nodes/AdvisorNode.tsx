import { Handle, Position } from "reactflow";
import type { Advisor } from "../../types/booking";
import { useActiveNodeId } from "../graph/MultiTopicFlow";

interface AdvisorNodeProps {
  data: Advisor & { fieldNames: string[] };
}

export default function AdvisorNode({ data }: AdvisorNodeProps) {
  const isActive = useActiveNodeId() === data.id;
  return (
    <div className={`bg-white rounded-xl shadow-lg p-5 w-[320px] border-2 transition-colors ${isActive ? "border-emerald-500" : "border-emerald-200"}`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">
            {data.firstName} {data.lastName}
          </h3>
          <p className="text-xs text-gray-500">{data.title}</p>
        </div>
        <span className="shrink-0 text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
          Advisor
        </span>
      </div>
      <p className="text-xs text-emerald-600 mb-2">{data.email}</p>
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
  );
}
