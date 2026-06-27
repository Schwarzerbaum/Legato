import { useEffect, memo, useMemo } from 'react'
import legatoLogo from '@/assets/legato.svg'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  type Node,
  type Edge,
} from '@xyflow/react'
import {
  topicById, foundationById, companyById,
  supervisorById, advisorById, fieldById,
  degreeLabel,
} from '@/data/index'
import { ACADEMIC, INDUSTRY } from './colors'
import { FloatingEdge } from './edges/FloatingEdge'
import { PersonNode } from './nodes/PersonNode'
import { Badge } from '@/components/ui/badge'
import { GraduationCap, Building2, Layers } from 'lucide-react'

// ─── Colors per entity type ──────────────────────────────────────────────────

const SUPERVISOR_COLOR  = { color: '#0d9488', lightBg: 'rgba(13,148,136,0.10)' }
const ADVISOR_COLOR      = { color: '#7c3aed', lightBg: 'rgba(124,58,237,0.10)' }
const FIELD_COLOR       = { color: '#d97706', lightBg: 'rgba(217,119,6,0.08)' }

// ─── ConnectionsCenterNode ─────────────────────────────────────────────────────────

interface ConnectionsCenterData { topicId: string }

const ConnectionsCenterNode = memo(function ConnectionsCenterNode({ data }: { data: ConnectionsCenterData }) {
  const topic = topicById[data.topicId]
  if (!topic) return null
  const isAcademic = !topic.companyId
  const colors = isAcademic ? ACADEMIC : INDUSTRY

  return (
    <div
      className="rounded-2xl border-2 px-5 py-4 shadow-lg select-none"
      style={{ maxWidth: 260, borderColor: colors.border, backgroundColor: colors.bg }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="flex size-6 items-center justify-center rounded-md"
          style={{ backgroundColor: colors.selectedBg }}>
          {isAcademic
            ? <GraduationCap className="size-3.5 text-white" />
            : <Building2 className="size-3.5 text-white" />
          }
        </div>
        <span className="ds-caption font-semibold" style={{ color: colors.text }}>
          {isAcademic ? 'Academic' : 'Industry'}
        </span>
      </div>
      <h3 className="ds-label leading-snug line-clamp-3 mb-2">{topic.title}</h3>
      <div className="flex flex-wrap gap-1">
        {topic.degrees.map(d => (
          <Badge key={d} variant="outline" className="ds-caption">{degreeLabel(d)}</Badge>
        ))}
      </div>
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})

// ─── TagNode (fields) ─────────────────────────────────────────────────────────

interface TagNodeData { label: string }

const TagNode = memo(function TagNode({ data }: { data: TagNodeData }) {
  return (
    <div
      className="rounded-lg border px-3 py-1.5 select-none"
      style={{
        borderColor: FIELD_COLOR.color,
        backgroundColor: FIELD_COLOR.lightBg,
        color: FIELD_COLOR.color,
      }}
    >
      <div className="flex items-center gap-1.5">
        <Layers className="size-3 shrink-0" style={{ color: FIELD_COLOR.color }} />
        <span className="ds-caption font-medium">{data.label}</span>
      </div>
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})

// ─── Node types ───────────────────────────────────────────────────────────────

const nodeTypes = {
  'connections-center': ConnectionsCenterNode,
  'person': PersonNode,
  'tag': TagNode,
}

const edgeTypes = { floating: FloatingEdge }

// ─── Layout helpers ───────────────────────────────────────────────────────────

function toRad(deg: number) { return deg * Math.PI / 180 }

function pos(radius: number, angleDeg: number) {
  return {
    x: Math.round(radius * Math.cos(toRad(angleDeg))),
    y: Math.round(radius * Math.sin(toRad(angleDeg))),
  }
}

function spreadAngles(count: number, centerDeg: number, maxSpread: number): number[] {
  if (count === 0) return []
  if (count === 1) return [centerDeg]
  const spread = Math.min(count * 30, maxSpread)
  return Array.from({ length: count }, (_, i) =>
    centerDeg - spread / 2 + (i / (count - 1)) * spread
  )
}

// ─── Build graph ──────────────────────────────────────────────────────────────

function buildConnectionsGraph(topicId: string): { nodes: Node[]; edges: Edge[] } {
  const topic = topicById[topicId]
  if (!topic) return { nodes: [], edges: [] }

  const nodes: Node[] = []
  const edges: Edge[] = []

  const centerW = 260
  const centerH = 120

  // Center: connections
  nodes.push({
    id: 'tc',
    type: 'connections-center',
    position: { x: -centerW / 2, y: -centerH / 2 },
    data: { topicId },
    draggable: true,
  })

  // Foundation or Company — top (-90°)
  const sourceId = topic.foundationId ?? topic.companyId
  if (sourceId) {
    const isAcademic = !!topic.foundationId
    const source = isAcademic ? foundationById[sourceId] : companyById[sourceId]
    const colors = isAcademic ? ACADEMIC : INDUSTRY
    const { x, y } = pos(250, -90)
    nodes.push({
      id: `source-${sourceId}`,
      type: 'person',   // reuse PersonNode with source color
      position: { x: x - 75, y: y - 30 },
      data: {
        name: source?.name ?? sourceId,
        role: isAcademic ? 'Foundation' : 'Company',
        color: colors.text,
        lightBg: colors.bg,
        icon: isAcademic ? 'grad' : 'building',
      },
      draggable: true,
    })
    edges.push({
      id: `e-tc-source`,
      source: 'tc',
      target: `source-${sourceId}`,
      type: 'floating',
      data: { selected: true, dimmed: false },
    } as Edge)
  }

  // Supervisors — left arc (180° ± spread)
  const supervisors = topic.supervisorIds.map(id => supervisorById[id]).filter(Boolean)
  spreadAngles(supervisors.length, 180, 120).forEach((angle, i) => {
    const sup = supervisors[i]
    const { x, y } = pos(300, angle)
    nodes.push({
      id: `sup-${sup.id}`,
      type: 'person',
      position: { x: x - 75, y: y - 30 },
      data: {
        name: `${sup.title} ${sup.firstName} ${sup.lastName}`.trim(),
        role: 'Supervisor',
        ...SUPERVISOR_COLOR,
      },
      draggable: true,
    })
    edges.push({
      id: `e-tc-sup-${sup.id}`,
      source: 'tc',
      target: `sup-${sup.id}`,
      type: 'floating',
      data: { selected: true, dimmed: false },
    } as Edge)
  })

  // Advisors — right arc (0° ± spread)
  const advisors = topic.advisorIds.map(id => advisorById[id]).filter(Boolean)
  spreadAngles(advisors.length, 0, 120).forEach((angle, i) => {
    const exp = advisors[i]
    const { x, y } = pos(300, angle)
    nodes.push({
      id: `exp-${exp.id}`,
      type: 'person',
      position: { x: x - 75, y: y - 30 },
      data: {
        name: `${exp.title} ${exp.firstName} ${exp.lastName}`.trim(),
        role: 'Advisor',
        ...ADVISOR_COLOR,
      },
      draggable: true,
    })
    edges.push({
      id: `e-tc-exp-${exp.id}`,
      source: 'tc',
      target: `exp-${exp.id}`,
      type: 'floating',
      data: { selected: true, dimmed: false },
    } as Edge)
  })

  // Fields — bottom arc (90° ± spread)
  const fields = topic.fieldIds.map(id => fieldById[id]).filter(Boolean)
  spreadAngles(fields.length, 90, 150).forEach((angle, i) => {
    const field = fields[i]
    const { x, y } = pos(280, angle)
    nodes.push({
      id: `field-${field.id}`,
      type: 'tag',
      position: { x: x - 55, y: y - 18 },
      data: { label: field.name },
      draggable: true,
    })
    edges.push({
      id: `e-tc-field-${field.id}`,
      source: 'tc',
      target: `field-${field.id}`,
      type: 'floating',
      data: { selected: false, dimmed: true },
    } as Edge)
  })

  return { nodes, edges }
}

// ─── Inner canvas ─────────────────────────────────────────────────────────────

function ConnectionsGraphCanvas({ topicId }: { topicId: string }) {
  const { fitView } = useReactFlow()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const memoNodeTypes = useMemo(() => ({ ...nodeTypes }), [])
  const memoEdgeTypes = useMemo(() => ({ ...edgeTypes }), [])

  useEffect(() => {
    const { nodes: n, edges: e } = buildConnectionsGraph(topicId)
    setNodes(n)
    setEdges(e)
    setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 80)
  }, [topicId, setNodes, setEdges, fitView])

  const topic = topicById[topicId]
  const isAcademic = topic ? !topic.companyId : true

  return (
    <div className="h-full w-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={memoNodeTypes}
        edgeTypes={memoEdgeTypes}
        proOptions={{ hideAttribution: true }}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Panel position="bottom-right">
          <img src={legatoLogo} alt="Legato" className="h-6 opacity-60 pointer-events-none" />
        </Panel>
      </ReactFlow>

      {/* Legend */}
      <div className="pointer-events-none absolute bottom-4 left-4 z-10">
        <div className="flex flex-col gap-1.5 rounded-xl border border-border bg-background/80 px-3 py-2.5 backdrop-blur-sm">
          {[
            { label: isAcademic ? 'Foundation' : 'Company', color: isAcademic ? ACADEMIC.text : INDUSTRY.text },
            { label: 'Supervisor', color: SUPERVISOR_COLOR.color },
            { label: 'Advisor', color: ADVISOR_COLOR.color },
            { label: 'Field', color: FIELD_COLOR.color },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-2">
              <div className="size-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="ds-caption text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Public export ────────────────────────────────────────────────────────────

export function ConnectionsGraph({ topicId }: { topicId: string }) {
  return (
    <ReactFlowProvider>
      <ConnectionsGraphCanvas topicId={topicId} />
    </ReactFlowProvider>
  )
}
