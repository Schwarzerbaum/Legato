'use client'
import { useState, useEffect, useCallback } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant,
  useNodesState, useEdgesState, Handle, Position,
  useInternalNode, type Node, type Edge,
} from '@xyflow/react'
import { getBezierPath } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { motion, AnimatePresence } from 'framer-motion'

// ── Theme ─────────────────────────────────────────────────────────────────────
const INK    = '#0f172a'
const PARCH  = '#ffffff'
const LBBW   = '#003B6F'
const GREEN  = '#059669'
const AMBER  = '#d97706'
const NGO_C  = '#7c3aed'
const CORP_C = '#2563eb'
const RED    = '#dc2626'

// ── Domains ───────────────────────────────────────────────────────────────────
const DOMAINS = [
  'Climate & Energy', 'Education & Schools', 'Child Welfare',
  'Poverty & Social Inclusion', 'Health & Medical Research', 'Mental Health',
  'Clean Water & Sanitation', 'Biodiversity & Nature',
  'Disaster Relief', 'Refugees & Migration',
  'Human Rights & Justice', 'Digital Inclusion', 'Arts & Culture',
]

// ── Sources ───────────────────────────────────────────────────────────────────
const SOURCES = [
  { id:'phineo',   type:'ngo',  label:'PHINEO gAG',          sub:'Democracy · Stuttgart',         score:94, domains:['Human Rights & Justice','Education & Schools'] },
  { id:'bund',     type:'ngo',  label:'BUND e.V.',            sub:'Climate · BW',                  score:91, domains:['Climate & Energy','Biodiversity & Nature'] },
  { id:'wwh',      type:'ngo',  label:'Welthungerhilfe',      sub:'Poverty · global',              score:83, domains:['Poverty & Social Inclusion','Clean Water & Sanitation'] },
  { id:'sos',      type:'ngo',  label:'SOS-Kinderdorf',       sub:'Child Welfare · BW',            score:88, domains:['Child Welfare','Health & Medical Research'] },
  { id:'bws',      type:'ngo',  label:'BW Stiftung',          sub:'Education · BW',                score:74, domains:['Education & Schools','Arts & Culture'] },
  { id:'aktion',   type:'ngo',  label:'Aktion Mensch',        sub:'Disability · nationwide',       score:85, domains:['Digital Inclusion','Mental Health'] },
  { id:'bosch',    type:'corp', label:'Robert Bosch GmbH',    sub:'Tech · 1:1 Match',              score:0,  domains:['Education & Schools','Digital Inclusion'] },
  { id:'mercedes', type:'corp', label:'Mercedes-Benz AG',     sub:'Climate · 2:1 Match',           score:0,  domains:['Climate & Energy','Human Rights & Justice'] },
  { id:'porsche',  type:'corp', label:'Porsche AG',           sub:'Social · 1:1 Match',            score:0,  domains:['Human Rights & Justice','Poverty & Social Inclusion'] },
  { id:'wuerth',   type:'corp', label:'Würth Group',          sub:'Education Match · BW',          score:0,  domains:['Education & Schools','Refugees & Migration'] },
]

// ── Projects ──────────────────────────────────────────────────────────────────
const PROJECTS = [
  { id:'p1',  sid:'bund',     label:'Forest Conservation BW',      mission:'Protect 3,200 ha Schwarzwald by 2030',     impact:'SDG 13/15', alloc:'€120k', match:'Dr. Hoffmann' },
  { id:'p2',  sid:'bund',     label:'Solar Village Network',        mission:'100 rural solar grids in BW',              impact:'SDG 7/13',  alloc:'€80k',  match:'von Saalfeld' },
  { id:'p3',  sid:'phineo',   label:'Democracy Labs BW',           mission:'Civic participation in 40 BW communities', impact:'SDG 16',    alloc:'€60k',  match:'Breitner-Koch' },
  { id:'p4',  sid:'phineo',   label:'Wirkt-Siegel Certification',  mission:'Quality-audit 12 new BW NGOs 2026',        impact:'SDG 17',    alloc:'€30k',  match:'All mandates' },
  { id:'p5',  sid:'wwh',      label:'Food Corridor East Africa',   mission:'350k meals/yr Ethiopia & Kenya',           impact:'SDG 2',     alloc:'€200k', match:'von Saalfeld' },
  { id:'p6',  sid:'sos',      label:'Stuttgart Family Hub',        mission:'500 families supported annually',           impact:'SDG 1/3',   alloc:'€75k',  match:'Breitner-Koch' },
  { id:'p7',  sid:'bws',      label:'Digital Schools BW',          mission:'Broadband & devices, 85 rural schools',    impact:'SDG 4',     alloc:'€90k',  match:'Walczak' },
  { id:'p8',  sid:'aktion',   label:'Digital Bridges Seniors',     mission:'12k seniors connected in BW',              impact:'SDG 10',    alloc:'€45k',  match:'Walczak' },
  { id:'p9',  sid:'bosch',    label:'Bosch 1:1 STEM Match',        mission:'Double every STEM donation up to €50k',    impact:'SDG 4',     alloc:'1:1',   match:'von Saalfeld' },
  { id:'p10', sid:'mercedes', label:'Mercedes 2:1 Climate',        mission:'Triple climate donations up to €100k',     impact:'SDG 13',    alloc:'2:1',   match:'Dr. Hoffmann' },
]

// ── Live feed ─────────────────────────────────────────────────────────────────
const LIVE: Record<string,{t:string;text:string;s:'pos'|'neg'|'neu';ts:string}[]> = {
  phineo:   [
    { t:'◈', text:'PHINEO-Wirkt-Siegel Frühjahrsrunde 2026 startet', s:'pos', ts:'2h ago' },
    { t:'◎', text:'Handelsblatt: Impact-Messung in deutschen NGOs — PHINEO führend', s:'pos', ts:'6h ago' },
    { t:'⊞', text:'Jahresbericht 2025 — Transparenzranking A+', s:'pos', ts:'1d ago' },
    { t:'◈', text:'Kooperationsabkommen mit LBBW Stiftungsmanagement unterzeichnet', s:'pos', ts:'2d ago' },
  ],
  bund:     [
    { t:'◈', text:'BUND BW: Klage gegen Waldrodung Nordschwarzwald eingereicht', s:'neu', ts:'4h ago' },
    { t:'◎', text:'Bundesregierung kürzt Naturschutzmittel — BUND kritisiert scharf', s:'neg', ts:'8h ago' },
    { t:'⊞', text:'DZI Spendensiegel 2025/26 erneuert — höchste Kategorie', s:'pos', ts:'2d ago' },
    { t:'◈', text:'500 neue Mitglieder in BW allein im Mai', s:'pos', ts:'3d ago' },
  ],
  wwh:      [
    { t:'◎', text:'UN WFP bestätigt Partnerschaft Welthungerhilfe Äthiopien', s:'pos', ts:'1h ago' },
    { t:'◈', text:'Spendenaufruf: Dürrekatastrophe Horn of Africa — Ziel €2M', s:'neu', ts:'5h ago' },
    { t:'⊞', text:'Jahresabschluss 2025 — 89.4% Mittelverwendung für Projekte', s:'pos', ts:'1d ago' },
    { t:'◈', text:'Kritik: Verwaltungskosten leicht gestiegen gegenüber 2024', s:'neg', ts:'4d ago' },
  ],
  sos:      [
    { t:'◎', text:'SOS-Kinderdorf Stuttgart: Kapazitätserweiterung genehmigt', s:'pos', ts:'2h ago' },
    { t:'◈', text:'Welttag des Kindes: SOS sammelt €1.2M in 48 Stunden', s:'pos', ts:'7h ago' },
    { t:'⊞', text:'GPA BW Prüfung 2025 — keine Beanstandungen festgestellt', s:'pos', ts:'3d ago' },
    { t:'◈', text:'Kooperation DKMS erweitert: Familienbetreuung + Gesundheit', s:'pos', ts:'5d ago' },
  ],
  bws:      [
    { t:'◈', text:'BW Stiftung fördert 14 neue Bildungsprojekte Q2 2026', s:'pos', ts:'3h ago' },
    { t:'◎', text:'Landesrechnungshof: BW Stiftung mit vollem Freistellungsbescheid', s:'pos', ts:'1d ago' },
    { t:'⊞', text:'Stiftungsregister BW Eintragung bestätigt', s:'pos', ts:'2d ago' },
    { t:'◈', text:'Neuer Vorstand: Dr. Kerstin Müller-Weber ab Juli 2026', s:'neu', ts:'5d ago' },
  ],
  aktion:   [
    { t:'◎', text:'Aktion Mensch: Lotterie 2026 finanziert 2,340 Projekte', s:'pos', ts:'1h ago' },
    { t:'◈', text:'Digital Bridges — Phase 3: 15 neue BW-Standorte bestätigt', s:'pos', ts:'6h ago' },
    { t:'⊞', text:'Transparenzbericht 2025 — 100% Zweckbindung bestätigt', s:'pos', ts:'2d ago' },
    { t:'◈', text:'Kritik: Lotteriegebühren vs. direkte Projektausschüttung', s:'neg', ts:'6d ago' },
  ],
  bosch:    [
    { t:'◈', text:'Bosch Community Fund Q2: 1:1 Match verlängert bis Dez 2026', s:'pos', ts:'2h ago' },
    { t:'◎', text:'Bosch CSR Report 2025: €47M in Social Investments global', s:'pos', ts:'1d ago' },
    { t:'⊞', text:'CSRD Art. 8 Disclosure: Social Taxonomy aligned, Q1 2026', s:'pos', ts:'3d ago' },
    { t:'◈', text:'STEM-Stipendien BW 2026: Bewerbungsphase jetzt offen', s:'pos', ts:'4d ago' },
  ],
  mercedes: [
    { t:'◈', text:'Mercedes 2:1 Klimamatch: Kontingent 2026 noch 40% verfügbar', s:'pos', ts:'3h ago' },
    { t:'◎', text:'EU Carbon Neutrality Pledge 2039 — Mercedes zwei Jahre früher', s:'pos', ts:'12h ago' },
    { t:'⊞', text:'SFDR Art. 9 Fund Disclosure aktualisiert Q2 2026', s:'pos', ts:'2d ago' },
    { t:'◈', text:'Stuttgart Sozialprojekte: €8M Förderung 2026 angekündigt', s:'pos', ts:'5d ago' },
  ],
  porsche:  [
    { t:'◈', text:'Porsche Second Chance: 280 Auszubildende 2026 aufgenommen', s:'pos', ts:'5h ago' },
    { t:'◎', text:'Porsche Stiftung: €12M Sozialausgaben BW 2025', s:'pos', ts:'1d ago' },
    { t:'⊞', text:'1:1 Match verfügbar: Human Rights Education bis €5k/Donor', s:'pos', ts:'4d ago' },
    { t:'◈', text:'Interne Compliance-Überprüfung 2025 — keine Mängel', s:'pos', ts:'7d ago' },
  ],
  wuerth:   [
    { t:'◈', text:'Würth Stiftung: Bildungsmatching Q3 2026 jetzt offen', s:'pos', ts:'1h ago' },
    { t:'◎', text:'Würth Gruppe: €4.5B Umsatz Q1 — Stiftungsbudget erhöht', s:'pos', ts:'8h ago' },
    { t:'⊞', text:'Mittelstand-Förderung BW: Kooperation IHK Heilbronn', s:'pos', ts:'3d ago' },
    { t:'◈', text:'22 neue Schulpartnerschaften im Hohenlohekreis 2026', s:'pos', ts:'6d ago' },
  ],
}

// ── Credibility sub-scores (NGOs only) ────────────────────────────────────────
const CRED: Record<string,{dim:string;val:number}[]> = {
  phineo: [ {dim:'Financial Transparency',val:94}, {dim:'Impact Consistency',val:96}, {dim:'Governance Quality',val:92}, {dim:'Media Sentiment',val:89}, {dim:'LBBW Due Diligence',val:97} ],
  bund:   [ {dim:'Financial Transparency',val:88}, {dim:'Impact Consistency',val:93}, {dim:'Governance Quality',val:87}, {dim:'Media Sentiment',val:82}, {dim:'LBBW Due Diligence',val:94} ],
  wwh:    [ {dim:'Financial Transparency',val:84}, {dim:'Impact Consistency',val:86}, {dim:'Governance Quality',val:80}, {dim:'Media Sentiment',val:74}, {dim:'LBBW Due Diligence',val:87} ],
  sos:    [ {dim:'Financial Transparency',val:90}, {dim:'Impact Consistency',val:88}, {dim:'Governance Quality',val:86}, {dim:'Media Sentiment',val:84}, {dim:'LBBW Due Diligence',val:91} ],
  bws:    [ {dim:'Financial Transparency',val:72}, {dim:'Impact Consistency',val:77}, {dim:'Governance Quality',val:78}, {dim:'Media Sentiment',val:65}, {dim:'LBBW Due Diligence',val:79} ],
  aktion: [ {dim:'Financial Transparency',val:88}, {dim:'Impact Consistency',val:82}, {dim:'Governance Quality',val:85}, {dim:'Media Sentiment',val:79}, {dim:'LBBW Due Diligence',val:88} ],
}

// ── Radii ─────────────────────────────────────────────────────────────────────
const R1 = 240, R2 = 460, R3 = 680

function polar(r:number, deg:number) {
  const a = deg * Math.PI / 180
  return { x: Math.round(r * Math.cos(a)), y: Math.round(r * Math.sin(a)) }
}
function ring(i:number, total:number, offset=-90) {
  return offset + i * (360 / total)
}

// ── Floating bezier edge ──────────────────────────────────────────────────────
function getCenter(node: ReturnType<typeof useInternalNode>) {
  const w = node?.measured?.width  ?? 110
  const h = node?.measured?.height ?? 38
  return {
    x: (node?.internals?.positionAbsolute?.x ?? 0) + w/2,
    y: (node?.internals?.positionAbsolute?.y ?? 0) + h/2,
  }
}
function FloatingEdge({ id, source, target, data }: any) {
  const s = useInternalNode(source)
  const t = useInternalNode(target)
  if (!s?.measured || !t?.measured) return null
  const sp = getCenter(s), tp = getCenter(t)
  const [path] = getBezierPath({ sourceX:sp.x, sourceY:sp.y, targetX:tp.x, targetY:tp.y })
  return (
    <path id={id} d={path} fill="none"
      stroke={data?.active ? INK : `${INK}28`}
      strokeWidth={data?.active ? 1.2 : 0.6}
      strokeDasharray={data?.active ? '0' : '4 6'}
      style={{ pointerEvents:'none', transition:'stroke 0.2s, stroke-width 0.2s' }}
    />
  )
}

// ── Node components ───────────────────────────────────────────────────────────
function CenterNode() {
  return (
    <div style={{ background:'#f8fafc', border:`1px solid ${INK}1A`, borderRadius:8,
      padding:'14px 24px', textAlign:'center', minWidth:200, boxShadow:`0 2px 18px ${INK}07` }}>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'-0.01em',
        textTransform:'none', color:INK, opacity:0.22, marginBottom:6 }}>
        Legato · Bank Intelligence
      </div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:17, fontStyle:'italic',
        color:INK, opacity:0.68 }}>Philanthropy Due Diligence</div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:10, color:INK,
        opacity:0.25, marginTop:2 }}>{DOMAINS.length} domains · {SOURCES.length} organisations</div>
      <Handle type="source" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
    </div>
  )
}

function DomainNode({ data }: any) {
  return (
    <div onClick={data.onClick} style={{
      background: data.active ? INK : PARCH,
      border:`1px solid ${data.active ? INK : INK+'44'}`,
      borderRadius:999, padding:'5px 14px', cursor:'pointer', whiteSpace:'nowrap',
      opacity: data.dimmed ? 0.15 : 1,
      transition:'all 0.18s',
    }}>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12,
        color: data.active ? PARCH : INK, opacity: data.active ? 0.9 : 0.62 }}>
        {data.label}
      </div>
      <Handle type="target" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
      <Handle type="source" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
    </div>
  )
}

function SourceNode({ data }: any) {
  const { src, active, dimmed } = data
  const col = src.type === 'ngo' ? NGO_C : CORP_C
  return (
    <div onClick={data.onClick} style={{
      background: active ? col : col+'10',
      border:`1px solid ${col}`,
      borderRadius:8, padding:'9px 14px', cursor:'pointer', width:162,
      opacity: dimmed ? 0.1 : 1,
      boxShadow: active ? `0 2px 16px ${col}28` : 'none',
      transition:'all 0.2s',
    }}>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12,
        color: active ? '#fff' : col, opacity:0.6, marginBottom:2 }}>
        {src.type==='ngo' ? '◇ NGO' : '⬡ Corporate'}
      </div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13, fontWeight:500,
        color: active ? '#fff' : col, lineHeight:1.3 }}>{src.label}</div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:10.5,
        color: active ? '#fff' : col, opacity:0.45, marginTop:1,
        whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{src.sub}</div>
      {src.score > 0 && (
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color: active ? '#fff' : GREEN,
          opacity: active ? 0.6 : 0.85, marginTop:4 }}>{src.score}/100</div>
      )}
      {src.type==='corp' && (
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
          textTransform:'none', color: active ? '#fff' : CORP_C,
          opacity: active ? 0.6 : 0.8, marginTop:3 }}>Match Available</div>
      )}
      <Handle type="target" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
      <Handle type="source" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
    </div>
  )
}

function ProjectNode({ data }: any) {
  const { proj, active, dimmed } = data
  const isMatch = proj.alloc==='1:1' || proj.alloc==='2:1'
  return (
    <div onClick={data.onClick} style={{
      background: active ? INK : '#fff',
      borderTop:`0.5px solid ${INK}12`, borderRight:`0.5px solid ${INK}12`,
      borderBottom:`0.5px solid ${INK}12`,
      borderLeft:`2px solid ${active ? GREEN : INK+'20'}`,
      borderRadius:4, padding:'8px 11px', cursor:'pointer', width:170,
      opacity: dimmed ? 0.1 : 1,
      transition:'all 0.18s',
    }}>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12.5, fontWeight:500,
        color: active ? '#fff' : INK, lineHeight:1.3, marginBottom:2 }}>{proj.label}</div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:10,
        color: active ? '#fff' : INK, opacity: active ? 0.5 : 0.35 }}>{proj.impact}</div>
      {isMatch && (
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
          textTransform:'none', color: active ? '#fff' : CORP_C,
          opacity: active ? 0.65 : 0.8, marginTop:3 }}>{proj.alloc} Match</div>
      )}
      <Handle type="target" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
      <Handle type="source" position={Position.Top} style={{ opacity:0, width:0, height:0 }} />
    </div>
  )
}

const nodeTypes = { center:CenterNode, domain:DomainNode, source:SourceNode, project:ProjectNode }
const edgeTypes = { floating:FloatingEdge }

// ── Graph builder ─────────────────────────────────────────────────────────────
function buildGraph(
  selDomains: string[],
  selSrc: string|null,
  selProj: string|null,
  onDomain:(d:string)=>void,
  onSrc:(s:string)=>void,
  onProj:(p:string)=>void,
): { nodes:Node[]; edges:Edge[] } {
  const nodes:Node[] = [], edges:Edge[] = []
  const hasDomain = selDomains.length > 0
  const hasSrc = !!selSrc

  nodes.push({ id:'center', type:'center', position:{x:-100,y:-36}, data:{}, draggable:true })

  // R1 — domains
  DOMAINS.forEach((d, i) => {
    const p = polar(R1, ring(i, DOMAINS.length))
    const active = selDomains.includes(d)
    const dimmed = hasDomain && !active
    nodes.push({
      id:`d${i}`, type:'domain',
      position:{ x:p.x-50, y:p.y-18 },
      data:{ label:d, active, dimmed, onClick:()=>onDomain(d) },
      draggable:true,
    })
    edges.push({ id:`ec${i}`, source:'center', target:`d${i}`, type:'floating',
      data:{ active: active || !hasDomain } })
  })

  // R2 — sources only appear after a domain is selected
  if (hasDomain) {
    const visibleSources = SOURCES.filter(s => s.domains.some(sd => selDomains.includes(sd)))
    visibleSources.forEach((s) => {
      const anchor = s.domains.find(sd => selDomains.includes(sd)) ?? s.domains[0]
      const di = DOMAINS.indexOf(anchor)
      const sib = visibleSources.filter(x => {
        const a = x.domains.find(sd => selDomains.includes(sd)) ?? x.domains[0]
        return a === anchor
      })
      const si = sib.indexOf(s)
      const baseA = ring(di>=0?di:0, DOMAINS.length)
      const finalA = baseA + (si - (sib.length-1)/2) * 26
      const p = polar(R2, finalA)
      const active = selSrc===s.id
      const dimmed = hasSrc && !active

      nodes.push({
        id:`s-${s.id}`, type:'source',
        position:{ x:p.x-81, y:p.y-42 },
        data:{ src:s, active, dimmed, onClick:()=>onSrc(s.id) },
        draggable:true,
      })

      s.domains.filter(sd => selDomains.includes(sd)).forEach(sd => {
        const dIdx = DOMAINS.indexOf(sd)
        if (dIdx<0) return
        edges.push({ id:`eds-${s.id}-${sd}`, source:`d${dIdx}`, target:`s-${s.id}`,
          type:'floating', data:{ active: active || !hasSrc } })
      })
    })
  }

  // R3 — projects (only when source selected)
  if (selSrc) {
    const sp = PROJECTS.filter(p => p.sid===selSrc)
    const srcNode = SOURCES.find(s => s.id===selSrc)
    const anchor = srcNode?.domains[0] ?? ''
    const di = DOMAINS.indexOf(anchor)
    const baseA = ring(di>=0?di:0, DOMAINS.length)
    sp.forEach((proj, j) => {
      const a = baseA + (j - (sp.length-1)/2) * 22
      const p = polar(R3, a)
      const active = selProj===proj.id
      nodes.push({
        id:`p-${proj.id}`, type:'project',
        position:{ x:p.x-85, y:p.y-36 },
        data:{ proj, active, dimmed:false, onClick:()=>onProj(proj.id) },
        draggable:true,
      })
      edges.push({ id:`esp-${proj.id}`, source:`s-${selSrc}`, target:`p-${proj.id}`,
        type:'floating', data:{ active } })
    })
  }

  return { nodes, edges }
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
function sCol(s:'pos'|'neg'|'neu') { return s==='pos'?GREEN:s==='neg'?RED:AMBER }

function Sidebar({ srcId, selProj, onProj, onClose }: {
  srcId:string; selProj:string|null; onProj:(p:string)=>void; onClose:()=>void
}) {
  const src = SOURCES.find(s => s.id===srcId)!
  const col = src.type==='ngo' ? NGO_C : CORP_C
  const creds = CRED[srcId]
  const feed  = LIVE[srcId] ?? []
  const projs = PROJECTS.filter(p => p.sid===srcId)
  const accredited = src.score >= 85

  return (
    <motion.div key={srcId}
      initial={{ x:'100%' }} animate={{ x:0 }} exit={{ x:'100%' }}
      transition={{ type:'spring', damping:28, stiffness:260 }}
      style={{ width:360, flexShrink:0, background:'#fff', overflowY:'auto',
        borderLeft:`1px solid ${INK}0E`, position:'sticky', top:0,
        maxHeight:'calc(100vh - 52px)' }}>
      <div style={{ padding:'22px 20px 80px', position:'relative' }}>
        <button onClick={onClose} style={{ position:'absolute', top:16, right:16,
          background:'none', border:'none', cursor:'pointer',
          fontSize:17, color:INK, opacity:0.2 }}>✕</button>

        {/* Header */}
        <div style={{ display:'flex', gap:7, alignItems:'center', marginBottom:8 }}>
          <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:9.5, color:col, opacity:0.65 }}>
            {src.type==='ngo' ? '◇ NGO · Verified' : '⬡ Corporate Partner'}
          </span>
          {accredited && (
            <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:'#fff', background:LBBW,
              padding:'2px 8px', borderRadius:3 }}>LBBW Accredited</span>
          )}
        </div>
        <h2 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:21, fontWeight:500,
          color:INK, margin:'0 0 2px', lineHeight:1.2 }}>{src.label}</h2>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12, color:INK,
          opacity:0.32, fontStyle:'italic', marginBottom:16 }}>{src.sub}</div>

        {/* Credibility sub-scores (NGOs only) */}
        {creds && (
          <div style={{ marginBottom:18 }}>
            <div style={{ display:'flex', justifyContent:'space-between',
              alignItems:'center', marginBottom:10 }}>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                textTransform:'none', color:INK, opacity:0.25 }}>LBBW Credibility Score</div>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:18, color:GREEN }}>{src.score}</div>
            </div>
            {creds.map(c => (
              <div key={c.dim} style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:INK,
                  opacity:0.28, width:88, flexShrink:0, lineHeight:1.3 }}>{c.dim}</div>
                <div style={{ flex:1, height:2.5, background:`${INK}08`, borderRadius:2 }}>
                  <motion.div initial={{ width:0 }} animate={{ width:`${c.val}%` }}
                    transition={{ duration:0.65 }}
                    style={{ height:'100%', background:GREEN, opacity:0.65, borderRadius:2 }} />
                </div>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:GREEN, width:22, textAlign:'right' }}>
                  {c.val}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Corporate match info */}
        {src.type==='corp' && (
          <div style={{ padding:'12px 14px', background:`${CORP_C}06`,
            border:`1px solid ${CORP_C}22`, borderRadius:6, marginBottom:18 }}>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:CORP_C, opacity:0.7, marginBottom:4 }}>
              Matching Programme
            </div>
            <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13, color:INK,
              opacity:0.6, lineHeight:1.75, fontStyle:'italic', margin:0 }}>{src.sub}</p>
          </div>
        )}

        {/* Projects */}
        {projs.length > 0 && (
          <div style={{ marginBottom:18 }}>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:INK, opacity:0.25, marginBottom:8 }}>
              Fundable Projects · {projs.length}
            </div>
            {projs.map(proj => {
              const active = selProj===proj.id
              const isMatch = proj.alloc==='1:1'||proj.alloc==='2:1'
              return (
                <div key={proj.id} onClick={()=>onProj(proj.id)} style={{
                  padding:'9px 11px', marginBottom:5, cursor:'pointer',
                  background: active ? `${GREEN}08` : '#fff',
                  borderTop:`0.5px solid ${INK}0A`, borderRight:`0.5px solid ${INK}0A`,
                  borderBottom:`0.5px solid ${INK}0A`,
                  borderLeft:`2px solid ${active?GREEN:INK+'18'}`,
                  transition:'all 0.14s',
                }}>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13.5,
                    color:INK, fontWeight: active?500:400, marginBottom:1 }}>{proj.label}</div>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11.5,
                    color:INK, opacity:0.42, fontStyle:'italic', lineHeight:1.5 }}>{proj.mission}</div>
                  <div style={{ display:'flex', gap:10, marginTop:4 }}>
                    <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:LBBW, opacity:0.6 }}>{proj.impact}</span>
                    {isMatch
                      ? <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:CORP_C }}>{proj.alloc} Match</span>
                      : <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:INK, opacity:0.25 }}>{proj.alloc}</span>
                    }
                    <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:GREEN, opacity:0.65 }}>→ {proj.match}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Live Intelligence feed */}
        <div style={{ marginBottom:22 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:10 }}>
            <motion.div animate={{ opacity:[1,0.2,1] }} transition={{ repeat:Infinity, duration:2.4 }}
              style={{ width:5, height:5, borderRadius:'50%', background:RED }} />
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:RED, opacity:0.75 }}>Live Intelligence</div>
          </div>
          {feed.map((f, i) => (
            <div key={i} style={{ display:'flex', gap:8, marginBottom:9,
              paddingBottom:9, borderBottom:`0.5px solid ${INK}07` }}>
              <span style={{ fontSize:10, color:sCol(f.s), flexShrink:0, marginTop:1 }}>{f.t}</span>
              <div style={{ flex:1 }}>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12.5,
                  color:INK, opacity:0.62, lineHeight:1.55 }}>{f.text}</div>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:INK,
                  opacity:0.2, marginTop:2 }}>{f.ts}</div>
              </div>
              <div style={{ width:5, height:5, borderRadius:'50%', flexShrink:0,
                marginTop:5, background:sCol(f.s), opacity:0.38 }} />
            </div>
          ))}
        </div>

        {/* CTAs */}
        <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
          <button style={{ padding:'12px', background:LBBW, color:'#fff', border:'none',
            cursor:'pointer', borderRadius:3, fontFamily:"Inter, system-ui, -apple-system, sans-serif",
            fontSize:11, letterSpacing:'0em', textTransform:'uppercase' }}>
            ⊞ Add to LBBW Portfolio
          </button>
          <button style={{ padding:'11px', background:'transparent', color:LBBW,
            border:`1px solid ${LBBW}44`, cursor:'pointer', borderRadius:3,
            fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em', textTransform:'uppercase' }}>
            ◎ Request LBBW Accreditation Review
          </button>
          <button style={{ padding:'10px', background:'transparent', color:INK,
            border:`1px solid ${INK}18`, cursor:'pointer', borderRadius:3,
            fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13.5, fontStyle:'italic', opacity:0.38 }}>
            Send to Client
          </button>
        </div>
      </div>
    </motion.div>
  )
}

// ── Inner flow ────────────────────────────────────────────────────────────────
function DiscoverFlow({ selDomains, selSrc, selProj, onDomain, onSrc, onProj }: {
  selDomains:string[]; selSrc:string|null; selProj:string|null
  onDomain:(d:string)=>void; onSrc:(s:string)=>void; onProj:(p:string)=>void
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    const { nodes:n, edges:e } = buildGraph(selDomains, selSrc, selProj, onDomain, onSrc, onProj)
    setNodes(n); setEdges(e)
  }, [selDomains, selSrc, selProj])

  return (
    <ReactFlow nodes={nodes} edges={edges}
      onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      fitView fitViewOptions={{ padding:0.12 }}
      minZoom={0.15} maxZoom={2}
      style={{ background:'#f8fafc' }}>
      <Background variant={BackgroundVariant.Dots} color={`${INK}09`} gap={26} size={1} />
    </ReactFlow>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DiscoverPage() {
  const [selDomains, setSelDomains] = useState<string[]>([])
  const [selSrc,     setSelSrc]     = useState<string|null>(null)
  const [selProj,    setSelProj]    = useState<string|null>(null)

  const onDomain = useCallback((d:string) => {
    setSelDomains(p => p.includes(d) ? p.filter(x=>x!==d) : [...p,d])
    setSelSrc(null); setSelProj(null)
  }, [])
  const onSrc = useCallback((s:string) => {
    setSelSrc(p => p===s ? null : s)
    setSelProj(null)
  }, [])
  const onProj = useCallback((p:string) => {
    setSelProj(prev => prev===p ? null : p)
  }, [])

  return (
    <div style={{ display:'flex', height:'calc(100vh - 52px)',
      marginLeft:'-40px', marginRight:'-40px', overflow:'hidden' }}>
      <div style={{ flex:1 }}>
        <ReactFlowProvider>
          <DiscoverFlow
            selDomains={selDomains} selSrc={selSrc} selProj={selProj}
            onDomain={onDomain} onSrc={onSrc} onProj={onProj}
          />
        </ReactFlowProvider>
      </div>
      <AnimatePresence>
        {selSrc && (
          <Sidebar srcId={selSrc} selProj={selProj} onProj={onProj}
            onClose={()=>{ setSelSrc(null); setSelProj(null) }} />
        )}
      </AnimatePresence>
    </div>
  )
}
