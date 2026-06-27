import { memo, useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Handle,
  Position,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  User,
  Landmark,
  Globe,
  HeartHandshake,
  Building2,
  Network,
  type LucideIcon,
} from 'lucide-react'
import { FloatingEdge } from '@/components/graph/edges/FloatingEdge'
import { cn } from '@/lib/utils'

// ─── Brand / accent palette ───────────────────────────────────────────────────
const LBBW = '#003B6F'

type Category = 'client' | 'foundation' | 'sdg' | 'ngo' | 'corporate'

const CATS: Record<Category, { label: string; color: string; icon: LucideIcon }> = {
  client:     { label: 'Clients',     color: '#7c3aed', icon: User },           // purple
  foundation: { label: 'Foundations', color: LBBW,      icon: Landmark },       // LBBW navy
  sdg:        { label: 'SDGs',        color: '#059669', icon: Globe },          // green
  ngo:        { label: 'NGOs',        color: '#2563eb', icon: HeartHandshake }, // blue
  corporate:  { label: 'Corporates',  color: '#ea580c', icon: Building2 },      // orange
}

// ─── Knowledge-graph data (LBBW advisor scope) ────────────────────────────────
// Ported from the advisor-intelligence "Organisations in LBBW Scope" reference:
// NGO credibility scores, client AUM/pillars, managed foundations and SDG mapping.

interface EntityDef {
  id: string
  category: Category
  label: string
  sublabel?: string
}

const ENTITIES: Record<Category, EntityDef[]> = {
  client: [
    { id: 'c-hoffmann', category: 'client', label: 'Dr. Miriam Hoffmann',   sublabel: '€4.8M AUM · Climate / Education' },
    { id: 'c-breitner', category: 'client', label: 'Familie Breitner-Koch', sublabel: '€12.2M AUM · Poverty / Rights' },
    { id: 'c-saalfeld', category: 'client', label: 'Ingrid von Saalfeld',   sublabel: '€38.5M AUM · Foundation granted' },
    { id: 'c-walczak',  category: 'client', label: 'Stefan Walczak',        sublabel: 'Onboarding · Digital' },
  ],
  foundation: [
    { id: 'f-hoffmann', category: 'foundation', label: 'Hoffmann Klimastiftung',       sublabel: '€1.2M endowment' },
    { id: 'f-breitner', category: 'foundation', label: 'Breitner-Koch Sozialstiftung', sublabel: '€4.8M endowment' },
    { id: 'f-saalfeld', category: 'foundation', label: 'von Saalfeld Stiftung',        sublabel: '€12.5M endowment' },
    { id: 'f-walczak',  category: 'foundation', label: 'Walczak Digitalstiftung',      sublabel: 'Recognition pending' },
  ],
  sdg: [
    { id: 'sdg-climate', category: 'sdg', label: 'SDG 13 · Climate Action' },
    { id: 'sdg-edu',     category: 'sdg', label: 'SDG 4 · Quality Education' },
    { id: 'sdg-rights',  category: 'sdg', label: 'SDG 16 · Peace & Justice' },
    { id: 'sdg-poverty', category: 'sdg', label: 'SDG 1 · No Poverty' },
    { id: 'sdg-digital', category: 'sdg', label: 'SDG 9 · Industry & Innovation' },
    { id: 'sdg-hunger',  category: 'sdg', label: 'SDG 2 · Zero Hunger' },
  ],
  ngo: [
    { id: 'n-bund',   category: 'ngo', label: 'BUND e.V.',       sublabel: '93/100 · DZI Spendensiegel' },
    { id: 'n-phineo', category: 'ngo', label: 'PHINEO gAG',      sublabel: '94/100 · Impact methodology' },
    { id: 'n-sos',    category: 'ngo', label: 'SOS-Kinderdorf',  sublabel: '88/100' },
    { id: 'n-mensch', category: 'ngo', label: 'Aktion Mensch',   sublabel: '85/100' },
    { id: 'n-welt',   category: 'ngo', label: 'Welthungerhilfe', sublabel: '83/100' },
    { id: 'n-bw',     category: 'ngo', label: 'BW Stiftung',     sublabel: '74/100' },
  ],
  corporate: [
    { id: 'co-bosch',    category: 'corporate', label: 'Robert Bosch GmbH', sublabel: 'Co-funding · 1:1 match' },
    { id: 'co-mercedes', category: 'corporate', label: 'Mercedes-Benz AG',  sublabel: 'Co-funding · 2:1 match' },
    { id: 'co-wuerth',   category: 'corporate', label: 'Würth Group',       sublabel: 'Co-funding' },
    { id: 'co-porsche',  category: 'corporate', label: 'Porsche AG',        sublabel: 'Co-funding' },
  ],
}

// Relationships (source → target)
const RELATIONS: Array<[string, string]> = [
  // Clients → managed foundations
  ['c-hoffmann', 'f-hoffmann'],
  ['c-breitner', 'f-breitner'],
  ['c-saalfeld', 'f-saalfeld'],
  ['c-walczak',  'f-walczak'],
  // Client cause pillar (beyond foundation channel)
  ['c-hoffmann', 'sdg-edu'],
  // Foundations → SDG disbursement focus
  ['f-hoffmann', 'sdg-climate'],
  ['f-breitner', 'sdg-poverty'],
  ['f-breitner', 'sdg-rights'],
  ['f-saalfeld', 'sdg-edu'],
  ['f-saalfeld', 'sdg-rights'],
  ['f-walczak',  'sdg-digital'],
  // NGOs → SDG alignment
  ['n-bund',   'sdg-climate'],
  ['n-phineo', 'sdg-edu'],
  ['n-phineo', 'sdg-rights'],
  ['n-sos',    'sdg-edu'],
  ['n-sos',    'sdg-rights'],
  ['n-mensch', 'sdg-rights'],
  ['n-welt',   'sdg-hunger'],
  ['n-welt',   'sdg-poverty'],
  ['n-bw',     'sdg-edu'],
  ['n-bw',     'sdg-digital'],
  // Corporate co-funding focus → SDG
  ['co-bosch',    'sdg-climate'],
  ['co-bosch',    'sdg-edu'],
  ['co-mercedes', 'sdg-climate'],
  ['co-mercedes', 'sdg-digital'],
  ['co-wuerth',   'sdg-edu'],
  ['co-porsche',  'sdg-climate'],
]

// ─── Layout: layered columns with SDGs as the central hub ─────────────────────
const COLUMN_ORDER: Category[] = ['client', 'foundation', 'sdg', 'ngo', 'corporate']
const COL_GAP = 340
const ROW_GAP = 118
const CENTER_Y = 360

const ENTITY_BY_ID: Record<string, EntityDef> = Object.values(ENTITIES)
  .flat()
  .reduce((acc, e) => ({ ...acc, [e.id]: e }), {} as Record<string, EntityDef>)

function buildPositions(): Record<string, { x: number; y: number }> {
  const pos: Record<string, { x: number; y: number }> = {}
  COLUMN_ORDER.forEach((cat, col) => {
    const list = ENTITIES[cat]
    const n = list.length
    list.forEach((e, i) => {
      pos[e.id] = {
        x: col * COL_GAP,
        y: CENTER_Y + (i - (n - 1) / 2) * ROW_GAP,
      }
    })
  })
  return pos
}
const POSITIONS = buildPositions()

// Adjacency for focus / highlight
const NEIGHBORS: Record<string, Set<string>> = (() => {
  const m: Record<string, Set<string>> = {}
  for (const e of Object.values(ENTITIES).flat()) m[e.id] = new Set([e.id])
  for (const [s, t] of RELATIONS) {
    m[s]?.add(t)
    m[t]?.add(s)
  }
  return m
})()

// ─── Custom node ──────────────────────────────────────────────────────────────
interface EntityNodeData {
  label: string
  sublabel?: string
  category: Category
  active: boolean
  dimmed: boolean
}

const EntityNode = memo(function EntityNode({ data }: { data: EntityNodeData }) {
  const meta = CATS[data.category]
  const Icon = meta.icon
  return (
    <div
      className={cn(
        'flex w-[200px] flex-col gap-1 rounded-xl border bg-card px-3.5 py-2.5 shadow-sm transition-all duration-200',
        data.active ? 'shadow-md' : '',
        data.dimmed ? 'opacity-30' : 'opacity-100',
      )}
      style={{ borderColor: data.active ? meta.color : 'var(--border)' }}
    >
      <div className="flex items-center gap-2">
        <span
          className="flex size-5 shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: `${meta.color}1a` }}
        >
          <Icon className="size-3" style={{ color: meta.color }} />
        </span>
        <p className="ds-label leading-tight line-clamp-2">{data.label}</p>
      </div>
      {data.sublabel && (
        <p className="ds-caption pl-7 leading-tight text-muted-foreground line-clamp-1">
          {data.sublabel}
        </p>
      )}
      <Handle type="source" position={Position.Right} className="!h-0 !w-0 !opacity-0" />
      <Handle type="target" position={Position.Left} className="!h-0 !w-0 !opacity-0" />
    </div>
  )
})

const nodeTypes = { entity: EntityNode }
const edgeTypes = { floating: FloatingEdge }

// ─── Canvas ───────────────────────────────────────────────────────────────────
function GraphCanvas() {
  const [selected, setSelected] = useState<string | null>(null)

  const nodes: Node[] = useMemo(() => {
    return Object.values(ENTITIES)
      .flat()
      .map(e => {
        const active = selected != null && NEIGHBORS[selected].has(e.id)
        const dimmed = selected != null && !NEIGHBORS[selected].has(e.id)
        return {
          id: e.id,
          type: 'entity',
          position: POSITIONS[e.id],
          data: {
            label: e.label,
            sublabel: e.sublabel,
            category: e.category,
            active,
            dimmed,
          } satisfies EntityNodeData,
          draggable: true,
        } as Node
      })
  }, [selected])

  const edges: Edge[] = useMemo(() => {
    return RELATIONS.map(([s, t]) => {
      const touches = selected != null && (s === selected || t === selected)
      const otherSelected = selected != null && !touches
      return {
        id: `e-${s}-${t}`,
        source: s,
        target: t,
        type: 'floating',
        data: { selected: touches, dimmed: otherSelected },
      } as Edge
    })
  }, [selected])

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelected(prev => (prev === node.id ? null : node.id))
  }, [])

  const onPaneClick = useCallback(() => setSelected(null), [])

  const sel = selected ? ENTITY_BY_ID[selected] : null
  const selLinks = selected
    ? [...NEIGHBORS[selected]].filter(id => id !== selected).map(id => ENTITY_BY_ID[id])
    : []

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      proOptions={{ hideAttribution: true }}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.25}
      maxZoom={1.6}
      nodesConnectable={false}
      className="bg-background"
    >
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />

      {/* Header — top-left, clear of the floating bottom nav */}
      <div className="pointer-events-none absolute left-6 top-6 z-10 max-w-sm">
        <div className="pointer-events-auto rounded-2xl border border-border bg-card/90 px-5 py-4 shadow-sm backdrop-blur-sm">
          <div className="mb-1 flex items-center gap-1.5" style={{ color: LBBW }}>
            <Network className="size-3.5" />
            <span className="ds-caption font-medium uppercase tracking-wide">
              Intelligence · Knowledge Graph
            </span>
          </div>
          <h1 className="ds-title-md">Advisor knowledge graph</h1>
          <p className="ds-caption mt-1 text-muted-foreground">
            Clients, managed foundations, credibility-scored NGOs, corporate co-funders and
            their SDG alignment. Click any node to trace its relationships.
          </p>
        </div>
      </div>

      {/* Legend — top-right */}
      <div className="pointer-events-none absolute right-6 top-6 z-10">
        <div className="pointer-events-auto rounded-2xl border border-border bg-card/90 px-4 py-3 shadow-sm backdrop-blur-sm">
          <p className="ds-caption mb-2 font-medium uppercase tracking-wide text-muted-foreground">
            Node types
          </p>
          <div className="space-y-1.5">
            {COLUMN_ORDER.map(cat => {
              const meta = CATS[cat]
              const Icon = meta.icon
              return (
                <div key={cat} className="flex items-center gap-2">
                  <span
                    className="flex size-4 items-center justify-center rounded"
                    style={{ backgroundColor: `${meta.color}1a` }}
                  >
                    <Icon className="size-2.5" style={{ color: meta.color }} />
                  </span>
                  <span className="ds-caption text-foreground">{meta.label}</span>
                  <span className="ds-caption text-muted-foreground">
                    {ENTITIES[cat].length}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Selection detail — bottom-left, lifted above the floating nav */}
      {sel && (
        <div className="pointer-events-none absolute bottom-20 left-6 z-10 max-w-xs">
          <div className="pointer-events-auto rounded-2xl border border-border bg-card/95 px-5 py-4 shadow-md backdrop-blur-sm">
            <div className="mb-2 flex items-center gap-2">
              <span
                className="rounded-full border px-2 py-0.5 ds-caption"
                style={{ borderColor: CATS[sel.category].color, color: CATS[sel.category].color }}
              >
                {CATS[sel.category].label.replace(/s$/, '')}
              </span>
            </div>
            <h2 className="ds-title-sm leading-snug">{sel.label}</h2>
            {sel.sublabel && (
              <p className="ds-caption mt-0.5 text-muted-foreground">{sel.sublabel}</p>
            )}
            <div className="mt-3 border-t border-border pt-3">
              <p className="ds-caption mb-1.5 font-medium text-muted-foreground">
                {selLinks.length} connection{selLinks.length !== 1 ? 's' : ''}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {selLinks.map(l => (
                  <span
                    key={l.id}
                    className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground"
                  >
                    <span
                      className="mr-1 inline-block size-1.5 rounded-full align-middle"
                      style={{ backgroundColor: CATS[l.category].color }}
                    />
                    {l.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </ReactFlow>
  )
}

export function KnowledgeGraphPage() {
  return (
    <div className="relative h-full w-full bg-background">
      <ReactFlowProvider>
        <GraphCanvas />
      </ReactFlowProvider>
    </div>
  )
}
