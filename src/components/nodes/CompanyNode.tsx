import { Handle, Position } from "reactflow";
import type { Company } from "../../types/booking";
import { useActiveNodeId } from "../graph/MultiTopicFlow";

interface CompanyNodeProps {
  data: Company;
}

export default function CompanyNode({ data }: CompanyNodeProps) {
  const isActive = useActiveNodeId() === data.id;
  return (
    <div className={`bg-white rounded-xl shadow-lg p-5 w-[320px] border-2 transition-colors ${isActive ? "border-rose-500" : "border-rose-200"}`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />

      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-semibold text-gray-900">{data.name}</h3>
        <span className="shrink-0 text-xs font-medium px-2 py-0.5 rounded-full bg-rose-100 text-rose-700">
          Company
        </span>
      </div>


      <p className="text-xs text-gray-400 mb-3">{data.size} employees</p>

      <div className="flex flex-wrap gap-1.5">
        {data.domains.map((domain) => (
          <span
            key={domain}
            className="text-xs px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200"
          >
            {domain}
          </span>
        ))}
      </div>


      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}
