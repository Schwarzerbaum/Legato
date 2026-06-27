import { useState, useEffect, useCallback } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldCheck, Building2, X, Radio } from 'lucide-react'
import { FloatingEdge } from '@/components/graph/edges/FloatingEdge'
import { cn } from '@/lib/utils'

// ── Accents ─────────────────────────────────────────────────────────────────
const LBBW = '#003B6F'
const GREEN = '#059669'
const AMBER = '#d97706'
const RED = '#dc2626'
const NGO_C = '#7c3aed'
const CORP_C = '#2563eb'

// ── Domains ─────────────────────────────────────────────────────────────────
const DOMAINS = [
  'Climate & Energy', 'Education & Schools', 'Child Welfare',
  'Poverty & Social Inclusion', 'Health & Medical Research', 'Mental Health',
  'Clean Water & Sanitation', 'Biodiversity & Nature',
  'Disaster Relief', 'Refugees & Migration',
  'Human Rights & Justice', 'Digital Inclusion', 'Arts & Culture',
]

// ── Sources ─────────────────────────────────────────────────────────────────
type Source = { id: string; type: 'ngo' | 'corp'; label: string; sub: string; score: number; domains: string[] }
const SOURCES: Source[] = [
  { id: 'phineo', type: 'ngo', label: 'PHINEO gAG', sub: 'Democracy · Stuttgart', score: 94, domains: ['Human Rights & Justice', 'Education & Schools'] },
  { id: 'bund', type: 'ngo', label: 'BUND e.V.', sub: 'Climate · BW', score: 91, domains: ['Climate & Energy', 'Biodiversity & Nature'] },
  { id: 'wwh', type: 'ngo', label: 'Welthungerhilfe', sub: 'Poverty · global', score: 83, domains: ['Poverty & Social Inclusion', 'Clean Water & Sanitation'] },
  { id: 'sos', type: 'ngo', label: 'SOS-Kinderdorf', sub: 'Child Welfare · BW', score: 88, domains: ['Child Welfare', 'Health & Medical Research'] },
  { id: 'bws', type: 'ngo', label: 'BW Stiftung', sub: 'Education · BW', score: 74, domains: ['Education & Schools', 'Arts & Culture'] },
  { id: 'aktion', type: 'ngo', label: 'Aktion Mensch', sub: 'Disability · nationwide', score: 85, domains: ['Digital Inclusion', 'Mental Health'] },
  { id: 'bosch', type: 'corp', label: 'Robert Bosch GmbH', sub: 'Tech · 1:1 Match', score: 0, domains: ['Education & Schools', 'Digital Inclusion'] },
  { id: 'mercedes', type: 'corp', label: 'Mercedes-Benz AG', sub: 'Climate · 2:1 Match', score: 0, domains: ['Climate & Energy', 'Human Rights & Justice'] },
  { id: 'porsche', type: 'corp', label: 'Porsche AG', sub: 'Social · 1:1 Match', score: 0, domains: ['Human Rights & Justice', 'Poverty & Social Inclusion'] },
  { id: 'wuerth', type: 'corp', label: 'Würth Group', sub: 'Education Match · BW', score: 0, domains: ['Education & Schools', 'Refugees & Migration'] },
]

// ── Projects ────────────────────────────────────────────────────────────────
type Project = { id: string; sid: string; label: string; mission: string; impact: string; alloc: string; match: string }
const PROJECTS: Project[] = [
  { id: 'p1', sid: 'bund', label: 'Forest Conservation BW', mission: 'Protect 3,200 ha Schwarzwald by 2030', impact: 'SDG 13/15', alloc: '€120k', match: 'Dr. Hoffmann' },
  { id: 'p2', sid: 'bund', label: 'Solar Village Network', mission: '100 rural solar grids in BW', impact: 'SDG 7/13', alloc: '€80k', match: 'von Saalfeld' },
  { id: 'p3', sid: 'phineo', label: 'Democracy Labs BW', mission: 'Civic participation in 40 BW communities', impact: 'SDG 16', alloc: '€60k', match: 'Breitner-Koch' },
  { id: 'p4', sid: 'phineo', label: 'Wirkt-Siegel Certification', mission: 'Quality-audit 12 new BW NGOs 2026', impact: 'SDG 17', alloc: '€30k', match: 'All mandates' },
  { id: 'p5', sid: 'wwh', label: 'Food Corridor East Africa', mission: '350k meals/yr Ethiopia & Kenya', impact: 'SDG 2', alloc: '€200k', match: 'von Saalfeld' },
  { id: 'p6', sid: 'sos', label: 'Stuttgart Family Hub', mission: '500 families supported annually', impact: 'SDG 1/3', alloc: '€75k', match: 'Breitner-Koch' },
  { id: 'p7', sid: 'bws', label: 'Digital Schools BW', mission: 'Broadband & devices, 85 rural schools', impact: 'SDG 4', alloc: '€90k', match: 'Walczak' },
  { id: 'p8', sid: 'aktion', label: 'Digital Bridges Seniors', mission: '12k seniors connected in BW', impact: 'SDG 10', alloc: '€45k', match: 'Walczak' },
  { id: 'p9', sid: 'bosch', label: 'Bosch 1:1 STEM Match', mission: 'Double every STEM donation up to €50k', impact: 'SDG 4', alloc: '1:1', match: 'von Saalfeld' },
  { id: 'p10', sid: 'mercedes', label: 'Mercedes 2:1 Climate', mission: 'Triple climate donations up to €100k', impact: 'SDG 13', alloc: '2:1', match: 'Dr. Hoffmann' },
]

// ── Live feed ───────────────────────────────────────────────────────────────
const LIVE: Record<string, { text: string; s: 'pos' | 'neg' | 'neu'; ts: string }[]> = {
  phineo: [
    { text: 'PHINEO-Wirkt-Seal spring round 2026 launches', s: 'pos', ts: '2h ago' },
    { text: 'Handelsblatt: Impact measurement in German NGOs — PHINEO leads', s: 'pos', ts: '6h ago' },
    { text: 'Annual report 2025 — transparency ranking A+', s: 'pos', ts: '1d ago' },
    { text: 'Cooperation agreement with LBBW foundation management signed', s: 'pos', ts: '2d ago' },
  ],
  bund: [
    { text: 'BUND BW: Lawsuit filed against Black Forest deforestation', s: 'neu', ts: '4h ago' },
    { text: 'Federal government cuts conservation funding — BUND criticises sharply', s: 'neg', ts: '8h ago' },
    { text: 'DZI donation seal 2025/26 renewed — highest category', s: 'pos', ts: '2d ago' },
    { text: '500 new members in BW in May alone', s: 'pos', ts: '3d ago' },
  ],
  wwh: [
    { text: 'UN WFP confirms Welthungerhilfe partnership in Ethiopia', s: 'pos', ts: '1h ago' },
    { text: 'Donation appeal: Horn of Africa drought disaster — target €2M', s: 'neu', ts: '5h ago' },
    { text: 'Annual accounts 2025 — 89.4% of funds used for projects', s: 'pos', ts: '1d ago' },
    { text: 'Criticism: Administrative costs slightly up vs. 2024', s: 'neg', ts: '4d ago' },
  ],
  sos: [
    { text: "SOS Children's Village Stuttgart: capacity expansion approved", s: 'pos', ts: '2h ago' },
    { text: "World Children's Day: SOS raises €1.2M in 48 hours", s: 'pos', ts: '7h ago' },
    { text: 'GPA BW audit 2025 — no findings recorded', s: 'pos', ts: '3d ago' },
    { text: 'DKMS cooperation expanded: family support + health', s: 'pos', ts: '5d ago' },
  ],
  bws: [
    { text: 'BW Foundation funds 14 new education projects Q2 2026', s: 'pos', ts: '3h ago' },
    { text: 'State Audit Court: BW Foundation holds full tax exemption notice', s: 'pos', ts: '1d ago' },
    { text: 'Foundation Register BW entry confirmed', s: 'pos', ts: '2d ago' },
    { text: 'New board chair: Dr. Kerstin Müller-Weber from July 2026', s: 'neu', ts: '5d ago' },
  ],
  aktion: [
    { text: 'Aktion Mensch: 2026 lottery funds 2,340 projects', s: 'pos', ts: '1h ago' },
    { text: 'Digital Bridges — Phase 3: 15 new BW locations confirmed', s: 'pos', ts: '6h ago' },
    { text: 'Transparency report 2025 — 100% purpose restriction confirmed', s: 'pos', ts: '2d ago' },
    { text: 'Criticism: lottery fees vs. direct project disbursement', s: 'neg', ts: '6d ago' },
  ],
  bosch: [
    { text: 'Bosch Community Fund Q2: 1:1 match extended to Dec 2026', s: 'pos', ts: '2h ago' },
    { text: 'Bosch CSR Report 2025: €47M in global social investments', s: 'pos', ts: '1d ago' },
    { text: 'CSRD Art. 8 Disclosure: Social Taxonomy aligned, Q1 2026', s: 'pos', ts: '3d ago' },
    { text: 'STEM scholarships BW 2026: application phase now open', s: 'pos', ts: '4d ago' },
  ],
  mercedes: [
    { text: 'Mercedes 2:1 climate match: 2026 allocation still 40% available', s: 'pos', ts: '3h ago' },
    { text: 'EU Carbon Neutrality Pledge 2039 — Mercedes two years ahead of schedule', s: 'pos', ts: '12h ago' },
    { text: 'SFDR Art. 9 Fund Disclosure aktualisiert Q2 2026', s: 'pos', ts: '2d ago' },
    { text: 'Stuttgart social projects: €8M funding 2026 announced', s: 'pos', ts: '5d ago' },
  ],
  porsche: [
    { text: 'Porsche Second Chance: 280 Auszubildende 2026 aufgenommen', s: 'pos', ts: '5h ago' },
    { text: 'Porsche Stiftung: €12M Sozialausgaben BW 2025', s: 'pos', ts: '1d ago' },
    { text: '1:1 match available: Human Rights Education up to €5k/donor', s: 'pos', ts: '4d ago' },
    { text: 'Internal compliance review 2025 — no findings', s: 'pos', ts: '7d ago' },
  ],
  wuerth: [
    { text: 'Würth Foundation: education matching Q3 2026 now open', s: 'pos', ts: '1h ago' },
    { text: 'Würth Group: €4.5B revenue Q1 — foundation budget increased', s: 'pos', ts: '8h ago' },
    { text: 'SME funding BW: cooperation with IHK Heilbronn', s: 'pos', ts: '3d ago' },
    { text: '22 neue Schulpartnerschaften im Hohenlohekreis 2026', s: 'pos', ts: '6d ago' },
  ],
}

// ── Credibility sub-scores (NGOs only) ──────────────────────────────────────
const CRED: Record<string, { dim: string; val: number }[]> = {
  phineo: [{ dim: 'Financial Transparency', val: 94 }, { dim: 'Impact Consistency', val: 96 }, { dim: 'Governance Quality', val: 92 }, { dim: 'Media Sentiment', val: 89 }, { dim: 'LBBW Due Diligence', val: 97 }],
  bund: [{ dim: 'Financial Transparency', val: 88 }, { dim: 'Impact Consistency', val: 93 }, { dim: 'Governance Quality', val: 87 }, { dim: 'Media Sentiment', val: 82 }, { dim: 'LBBW Due Diligence', val: 94 }],
  wwh: [{ dim: 'Financial Transparency', val: 84 }, { dim: 'Impact Consistency', val: 86 }, { dim: 'Governance Quality', val: 80 }, { dim: 'Media Sentiment', val: 74 }, { dim: 'LBBW Due Diligence', val: 87 }],
  sos: [{ dim: 'Financial Transparency', val: 90 }, { dim: 'Impact Consistency', val: 88 }, { dim: 'Governance Quality', val: 86 }, { dim: 'Media Sentiment', val: 84 }, { dim: 'LBBW Due Diligence', val: 91 }],
  bws: [{ dim: 'Financial Transparency', val: 72 }, { dim: 'Impact Consistency', val: 77 }, { dim: 'Governance Quality', val: 78 }, { dim: 'Media Sentiment', val: 65 }, { dim: 'LBBW Due Diligence', val: 79 }],
  aktion: [{ dim: 'Financial Transparency', val: 88 }, { dim: 'Impact Consistency', val: 82 }, { dim: 'Governance Quality', val: 85 }, { dim: 'Media Sentiment', val: 79 }, { dim: 'LBBW Due Diligence', val: 88 }],
}

// ── Geometry ────────────────────────────────────────────────────────────────
const R1 = 300, R2 = 560, R3 = 780
function polar(r: number, deg: number) {
  const a = (deg * Math.PI) / 180
  return { x: Math.round(r * Math.cos(a)), y: Math.round(r * Math.sin(a)) }
}
function ring(i: number, total: number, offset = -90) {
  return offset + i * (360 / total)
}

// ── Node components ─────────────────────────────────────────────────────────
const HANDLES = (
  <>
    <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
  </>
)

function CenterNode() {
  return (
    <div className="relative min-w-[210px] rounded-2xl border border-border bg-card px-7 py-4 text-center shadow-md">
      <div className="ds-badge uppercase tracking-wider text-muted-foreground mb-1" style={{ color: LBBW }}>
        Bank Intelligence
      </div>
      <div className="ds-title-cards" style={{ color: LBBW }}>Philanthropy Due Diligence</div>
      <div className="ds-caption text-muted-foreground mt-0.5">
        {DOMAINS.length} domains · {SOURCES.length} organisations
      </div>
      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
}

function DomainNode({ data }: { data: { label: string; active: boolean; dimmed: boolean; onClick: () => void } }) {
  return (
    <div
      onClick={data.onClick}
      className={cn(
        'cursor-pointer select-none whitespace-nowrap rounded-full border px-4 py-1.5 ds-caption shadow-sm transition-all duration-150',
        data.active
          ? 'border-foreground bg-foreground text-background'
          : 'border-border bg-card text-muted-foreground hover:border-foreground/40 hover:shadow-md hover:scale-[1.03]',
      )}
      style={{ opacity: data.dimmed ? 0.18 : 1 }}
    >
      {data.label}
      {HANDLES}
    </div>
  )
}

function SourceNode({ data }: { data: { src: Source; active: boolean; dimmed: boolean; onClick: () => void } }) {
  const { src, active, dimmed } = data
  const col = src.type === 'ngo' ? NGO_C : CORP_C
  const Icon = src.type === 'ngo' ? ShieldCheck : Building2
  return (
    <div
      onClick={data.onClick}
      className="w-[176px] cursor-pointer select-none rounded-xl border px-4 py-3 shadow-sm transition-all duration-150 hover:shadow-md hover:scale-[1.03]"
      style={{
        borderColor: col,
        backgroundColor: active ? col : `${col}10`,
        opacity: dimmed ? 0.12 : 1,
        boxShadow: active ? `0 2px 18px ${col}33` : undefined,
      }}
    >
      <div className="mb-1 flex items-center gap-1.5">
        <Icon className="size-3 shrink-0" style={{ color: active ? 'rgba(255,255,255,0.8)' : col }} />
        <span className="ds-caption" style={{ color: active ? 'rgba(255,255,255,0.85)' : col }}>
          {src.type === 'ngo' ? 'NGO · Verified' : 'Corporate Partner'}
        </span>
      </div>
      <div className="ds-label leading-tight" style={{ color: active ? '#fff' : col }}>{src.label}</div>
      <div className="ds-caption mt-0.5 truncate" style={{ color: active ? 'rgba(255,255,255,0.65)' : 'var(--muted-foreground)' }}>
        {src.sub}
      </div>
      {src.score > 0 && (
        <div className="ds-caption mt-1 font-medium" style={{ color: active ? '#fff' : GREEN }}>{src.score}/100</div>
      )}
      {src.type === 'corp' && (
        <div className="ds-caption mt-1" style={{ color: active ? '#fff' : CORP_C }}>Match Available</div>
      )}
      {HANDLES}
    </div>
  )
}

function ProjectNode({ data }: { data: { proj: Project; active: boolean; onClick: () => void } }) {
  const { proj, active } = data
  const isMatch = proj.alloc === '1:1' || proj.alloc === '2:1'
  return (
    <div
      onClick={data.onClick}
      className="w-[184px] cursor-pointer select-none rounded-lg border px-3 py-2.5 shadow-sm transition-all duration-150 hover:shadow-md hover:scale-[1.02]"
      style={{
        borderLeftWidth: 3,
        borderLeftColor: active ? GREEN : 'var(--border)',
        backgroundColor: active ? '#0f172a' : 'var(--card)',
        color: active ? '#fff' : 'var(--foreground)',
      }}
    >
      <div className="ds-label leading-tight">{proj.label}</div>
      <div className="ds-caption mt-0.5" style={{ color: active ? 'rgba(255,255,255,0.55)' : 'var(--muted-foreground)' }}>
        {proj.impact}
      </div>
      {isMatch && (
        <div className="ds-caption mt-1" style={{ color: active ? '#fff' : CORP_C }}>{proj.alloc} Match</div>
      )}
      {HANDLES}
    </div>
  )
}

const nodeTypes = { center: CenterNode, domain: DomainNode, source: SourceNode, project: ProjectNode }
const edgeTypes = { floating: FloatingEdge }

// ── Graph builder ───────────────────────────────────────────────────────────
function buildGraph(
  selDomains: string[],
  selSrc: string | null,
  selProj: string | null,
  onDomain: (d: string) => void,
  onSrc: (s: string) => void,
  onProj: (p: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []
  const hasDomain = selDomains.length > 0
  const hasSrc = !!selSrc

  nodes.push({ id: 'center', type: 'center', position: { x: -105, y: -42 }, data: {}, draggable: true })

  // R1 — domains
  DOMAINS.forEach((d, i) => {
    const p = polar(R1, ring(i, DOMAINS.length))
    const active = selDomains.includes(d)
    const dimmed = hasDomain && !active
    nodes.push({
      id: `d${i}`,
      type: 'domain',
      position: { x: p.x - 55, y: p.y - 16 },
      data: { label: d, active, dimmed, onClick: () => onDomain(d) },
      draggable: true,
    })
    edges.push({
      id: `ec${i}`, source: 'center', target: `d${i}`, type: 'floating',
      data: { selected: active, dimmed },
    } as Edge)
  })

  // R2 — sources appear once a domain is selected
  if (hasDomain) {
    const visibleSources = SOURCES.filter(s => s.domains.some(sd => selDomains.includes(sd)))
    visibleSources.forEach(s => {
      const anchor = s.domains.find(sd => selDomains.includes(sd)) ?? s.domains[0]
      const di = DOMAINS.indexOf(anchor)
      const sib = visibleSources.filter(x => {
        const a = x.domains.find(sd => selDomains.includes(sd)) ?? x.domains[0]
        return a === anchor
      })
      const si = sib.indexOf(s)
      const baseA = ring(di >= 0 ? di : 0, DOMAINS.length)
      const finalA = baseA + (si - (sib.length - 1) / 2) * 26
      const p = polar(R2, finalA)
      const active = selSrc === s.id
      const dimmed = hasSrc && !active

      nodes.push({
        id: `s-${s.id}`,
        type: 'source',
        position: { x: p.x - 88, y: p.y - 42 },
        data: { src: s, active, dimmed, onClick: () => onSrc(s.id) },
        draggable: true,
      })

      s.domains.filter(sd => selDomains.includes(sd)).forEach(sd => {
        const dIdx = DOMAINS.indexOf(sd)
        if (dIdx < 0) return
        edges.push({
          id: `eds-${s.id}-${sd}`, source: `d${dIdx}`, target: `s-${s.id}`, type: 'floating',
          data: { selected: active, dimmed },
        } as Edge)
      })
    })
  }

  // R3 — projects (only when a source is selected)
  if (selSrc) {
    const sp = PROJECTS.filter(p => p.sid === selSrc)
    const srcNode = SOURCES.find(s => s.id === selSrc)
    const anchor = srcNode?.domains[0] ?? ''
    const di = DOMAINS.indexOf(anchor)
    const baseA = ring(di >= 0 ? di : 0, DOMAINS.length)
    sp.forEach((proj, j) => {
      const a = baseA + (j - (sp.length - 1) / 2) * 22
      const p = polar(R3, a)
      const active = selProj === proj.id
      nodes.push({
        id: `p-${proj.id}`,
        type: 'project',
        position: { x: p.x - 92, y: p.y - 34 },
        data: { proj, active, onClick: () => onProj(proj.id) },
        draggable: true,
      })
      edges.push({
        id: `esp-${proj.id}`, source: `s-${selSrc}`, target: `p-${proj.id}`, type: 'floating',
        data: { selected: active, dimmed: false },
      } as Edge)
    })
  }

  return { nodes, edges }
}

// ── Sidebar ─────────────────────────────────────────────────────────────────
function sCol(s: 'pos' | 'neg' | 'neu') {
  return s === 'pos' ? GREEN : s === 'neg' ? RED : AMBER
}

function Sidebar({ srcId, selProj, onProj, onClose }: {
  srcId: string; selProj: string | null; onProj: (p: string) => void; onClose: () => void
}) {
  const src = SOURCES.find(s => s.id === srcId)!
  const col = src.type === 'ngo' ? NGO_C : CORP_C
  const creds = CRED[srcId]
  const feed = LIVE[srcId] ?? []
  const projs = PROJECTS.filter(p => p.sid === srcId)
  const accredited = src.score >= 85

  return (
    <motion.div
      key={srcId}
      initial={{ x: 40, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 40, opacity: 0 }}
      transition={{ type: 'spring', damping: 28, stiffness: 280 }}
      className="absolute right-4 top-4 bottom-20 z-20 w-[360px] overflow-y-auto rounded-2xl border border-border bg-card p-6 shadow-xl"
    >
      <button
        onClick={onClose}
        className="absolute right-4 top-4 text-muted-foreground transition-colors hover:text-foreground"
      >
        <X className="size-4" />
      </button>

      {/* Header */}
      <div className="mb-2 flex items-center gap-2">
        <span className="ds-caption" style={{ color: col }}>
          {src.type === 'ngo' ? 'NGO · Verified' : 'Corporate Partner'}
        </span>
        {accredited && (
          <span className="rounded-full px-2 py-0.5 ds-caption text-white" style={{ backgroundColor: LBBW }}>
            LBBW Accredited
          </span>
        )}
      </div>
      <h2 className="ds-title-sm">{src.label}</h2>
      <div className="ds-caption text-muted-foreground italic mb-5">{src.sub}</div>

      {/* Credibility sub-scores (NGOs only) */}
      {creds && (
        <div className="mb-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="ds-caption text-muted-foreground">LBBW Credibility Score</div>
            <div className="ds-title-sm" style={{ color: GREEN }}>{src.score}</div>
          </div>
          {creds.map(c => (
            <div key={c.dim} className="mb-2 flex items-center gap-2">
              <div className="ds-caption text-muted-foreground w-[92px] shrink-0 leading-tight">{c.dim}</div>
              <div className="h-1.5 flex-1 rounded-full bg-secondary">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${c.val}%` }}
                  transition={{ duration: 0.6 }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: GREEN }}
                />
              </div>
              <div className="ds-caption w-6 text-right" style={{ color: GREEN }}>{c.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Corporate match info */}
      {src.type === 'corp' && (
        <div className="mb-5 rounded-xl border p-4" style={{ borderColor: `${CORP_C}33`, backgroundColor: `${CORP_C}08` }}>
          <div className="ds-caption mb-1" style={{ color: CORP_C }}>Matching Programme</div>
          <p className="ds-small text-muted-foreground italic">{src.sub}</p>
        </div>
      )}

      {/* Fundable projects */}
      {projs.length > 0 && (
        <div className="mb-5">
          <div className="ds-caption text-muted-foreground mb-2">Fundable Projects · {projs.length}</div>
          {projs.map(proj => {
            const active = selProj === proj.id
            const isMatch = proj.alloc === '1:1' || proj.alloc === '2:1'
            return (
              <div
                key={proj.id}
                onClick={() => onProj(proj.id)}
                className="mb-1.5 cursor-pointer rounded-lg border px-3 py-2 transition-all"
                style={{
                  borderLeftWidth: 3,
                  borderLeftColor: active ? GREEN : 'var(--border)',
                  backgroundColor: active ? `${GREEN}0d` : 'transparent',
                }}
              >
                <div className={cn('ds-small leading-tight', active && 'font-medium')}>{proj.label}</div>
                <div className="ds-caption text-muted-foreground italic leading-snug">{proj.mission}</div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="ds-caption" style={{ color: LBBW }}>{proj.impact}</span>
                  {isMatch
                    ? <span className="ds-caption" style={{ color: CORP_C }}>{proj.alloc} Match</span>
                    : <span className="ds-caption text-muted-foreground">{proj.alloc}</span>}
                  <span className="ds-caption" style={{ color: GREEN }}>→ {proj.match}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Live intelligence feed */}
      <div className="mb-5">
        <div className="mb-3 flex items-center gap-1.5">
          <motion.span
            animate={{ opacity: [1, 0.2, 1] }}
            transition={{ repeat: Infinity, duration: 2.4 }}
          >
            <Radio className="size-3.5" style={{ color: RED }} />
          </motion.span>
          <div className="ds-caption" style={{ color: RED }}>Live Intelligence</div>
        </div>
        {feed.map((f, i) => (
          <div key={i} className="mb-2 flex gap-2 border-b border-border/60 pb-2">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full" style={{ backgroundColor: sCol(f.s) }} />
            <div className="flex-1">
              <div className="ds-small text-muted-foreground leading-snug">{f.text}</div>
              <div className="ds-caption text-muted-foreground/60 mt-0.5">{f.ts}</div>
            </div>
          </div>
        ))}
      </div>

      {/* CTAs */}
      <div className="flex flex-col gap-2">
        <button
          className="rounded-lg px-4 py-2.5 ds-label text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: LBBW }}
        >
          Add to LBBW Portfolio
        </button>
        <button
          className="rounded-lg border px-4 py-2.5 ds-label transition-colors hover:bg-secondary"
          style={{ borderColor: `${LBBW}44`, color: LBBW }}
        >
          Request LBBW Accreditation Review
        </button>
        <button className="rounded-lg border border-border px-4 py-2.5 ds-small text-muted-foreground italic transition-colors hover:bg-secondary">
          Send to Client
        </button>
      </div>
    </motion.div>
  )
}

// ── Flow canvas ─────────────────────────────────────────────────────────────
function DiscoverFlow({ selDomains, selSrc, selProj, onDomain, onSrc, onProj }: {
  selDomains: string[]; selSrc: string | null; selProj: string | null
  onDomain: (d: string) => void; onSrc: (s: string) => void; onProj: (p: string) => void
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    const { nodes: n, edges: e } = buildGraph(selDomains, selSrc, selProj, onDomain, onSrc, onProj)
    setNodes(n)
    setEdges(e)
  }, [selDomains, selSrc, selProj, onDomain, onSrc, onProj, setNodes, setEdges])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.16 }}
      minZoom={0.15}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="var(--border)" />
    </ReactFlow>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────
export function DiscoverPage() {
  const [selDomains, setSelDomains] = useState<string[]>([])
  const [selSrc, setSelSrc] = useState<string | null>(null)
  const [selProj, setSelProj] = useState<string | null>(null)

  const onDomain = useCallback((d: string) => {
    setSelDomains(p => (p.includes(d) ? p.filter(x => x !== d) : [...p, d]))
    setSelSrc(null)
    setSelProj(null)
  }, [])
  const onSrc = useCallback((s: string) => {
    setSelSrc(p => (p === s ? null : s))
    setSelProj(null)
  }, [])
  const onProj = useCallback((p: string) => {
    setSelProj(prev => (prev === p ? null : p))
  }, [])

  return (
    <div className="relative h-full w-full">
      <ReactFlowProvider>
        <DiscoverFlow
          selDomains={selDomains}
          selSrc={selSrc}
          selProj={selProj}
          onDomain={onDomain}
          onSrc={onSrc}
          onProj={onProj}
        />
      </ReactFlowProvider>

      {/* Header overlay — top-left, on-brand */}
      <div className="pointer-events-none absolute left-6 top-6 z-10 max-w-xs">
        <div className="ds-badge uppercase tracking-wider" style={{ color: LBBW }}>
          Due Diligence · Germany
        </div>
        <h1 className="ds-title-lg mt-1">Discover</h1>
        <p className="ds-small text-muted-foreground mt-1">
          A radial map of vetted cause domains, NGOs with credibility scores, and corporate match partners.
          Select a domain to reveal organisations.
        </p>
      </div>

      {/* Legend — bottom-left, clear of the centre nav */}
      <div className="pointer-events-none absolute bottom-6 left-6 z-10 flex items-center gap-4 rounded-xl border border-border bg-card/85 px-4 py-2 shadow-sm backdrop-blur-sm">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="size-3.5" style={{ color: NGO_C }} />
          <span className="ds-caption text-muted-foreground">NGO · credibility score</span>
        </div>
        <div className="h-3 w-px bg-border" />
        <div className="flex items-center gap-1.5">
          <Building2 className="size-3.5" style={{ color: CORP_C }} />
          <span className="ds-caption text-muted-foreground">Corporate · match offer</span>
        </div>
      </div>

      {/* Detail panel */}
      <AnimatePresence>
        {selSrc && (
          <Sidebar
            srcId={selSrc}
            selProj={selProj}
            onProj={onProj}
            onClose={() => { setSelSrc(null); setSelProj(null) }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
