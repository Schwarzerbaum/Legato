import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as d3 from 'd3'
import { useLegatum } from '../context/LegatumContext'
import { NGOS } from '../data/ngos'
import { PERSONAS } from '../data/personas'

// ─── AGENT SWARM NODES ───────────────────────────────────────────────────────
const AGENTS = [
  { id: 'ag1', label: 'Doc Ingestion',     layer: 1, status: 'live',   group: 'engine' },
  { id: 'ag2', label: 'KG Builder',        layer: 2, status: 'live',   group: 'engine' },
  { id: 'ag3', label: 'Hybrid RAG',        layer: 3, status: 'live',   group: 'engine' },
  { id: 'ag4', label: 'BlackSwanX',        layer: 4, status: 'live',   group: 'analysis' },
  { id: 'ag5', label: 'Impact Sim',        layer: 5, status: 'active', group: 'analysis' },
  { id: 'ag6', label: 'Living Graph',      layer: 6, status: 'active', group: 'analysis' },
  { id: 'ag7', label: 'Foundation Arc',    layer: 7, status: 'active', group: 'advisory' },
  { id: 'ag8', label: 'NFT Passport',      layer: 8, status: 'primed', group: 'advisory' },
  { id: 'ag9', label: 'Advisor Trigger',   layer: 9, status: 'primed', group: 'advisory' },
]

const CAUSES = [
  { id: 'c_democracy',    label: 'Democracy',     color: '#a78bfa' },
  { id: 'c_education',    label: 'Education',     color: '#34d399' },
  { id: 'c_climate',      label: 'Climate',       color: '#60a5fa' },
  { id: 'c_integration',  label: 'Integration',   color: '#f97316' },
  { id: 'c_digital',      label: 'Digital Equity',color: '#38bdf8' },
  { id: 'c_health',       label: 'Health',        color: '#fb7185' },
]

const STATUS_COLOR = { live: '#10b981', active: '#06b6d4', primed: '#f59e0b' }
const GROUP_COLOR  = { engine: '#818cf8', analysis: '#f59e0b', advisory: '#34d399' }

function buildGraph(persona, selectedIds) {
  const nodes = [], links = []

  // Centre: You
  const personaLabel = persona ? `${persona.id} Giver` : 'You'
  nodes.push({ id: 'me', label: personaLabel, type: 'persona', r: 26 })

  // All NGOs (not just selected)
  NGOS.forEach(ngo => {
    nodes.push({ id: ngo.id, label: ngo.name, type: 'ngo', r: 10 + ngo.score * 0.07,
      score: ngo.score, anomaly: ngo.anomaly, selected: selectedIds.includes(ngo.id) })
    links.push({ source: 'me', target: ngo.id, type: 'gives', strength: selectedIds.includes(ngo.id) ? 0.9 : 0.25 })

    ngo.sdgs.forEach(sdg => {
      const sid = `sdg${sdg}`
      if (!nodes.find(n => n.id === sid))
        nodes.push({ id: sid, label: `SDG ${sdg}`, type: 'sdg', r: 7 })
      links.push({ source: ngo.id, target: sid, type: 'aligns', strength: 0.4 })
    })

    // NGO ↔ cause
    const cause = CAUSES.find(c =>
      ngo.cause.toLowerCase().includes(c.id.replace('c_', '').split('_')[0]) ||
      ngo.nodes?.some(n => c.id.includes(n))
    ) || CAUSES[Math.abs(ngo.id.charCodeAt(0) - 97) % CAUSES.length]
    if (!nodes.find(n => n.id === cause.id))
      nodes.push({ id: cause.id, label: cause.label, type: 'cause', r: 11, color: cause.color })
    if (!links.find(l => (l.source === ngo.id && l.target === cause.id)))
      links.push({ source: ngo.id, target: cause.id, type: 'supports', strength: 0.5 })
  })

  // Agent swarm
  AGENTS.forEach(ag => {
    nodes.push({ ...ag, type: 'agent', r: 13 })
    // Agents form a pipeline chain
    if (ag.layer > 1) links.push({ source: `ag${ag.layer - 1}`, target: ag.id, type: 'pipeline', strength: 0.7 })
    // Each engine agent connects to a random NGO
    if (ag.group === 'engine') {
      const ngo = NGOS[ag.layer % NGOS.length]
      links.push({ source: ag.id, target: ngo.id, type: 'scans', strength: 0.3 })
    }
    // Analysis agents connect to me
    if (ag.group === 'analysis') links.push({ source: 'me', target: ag.id, type: 'queries', strength: 0.4 })
    // Advisory agents connect to me strongly
    if (ag.group === 'advisory') links.push({ source: ag.id, target: 'me', type: 'advises', strength: 0.6 })
  })

  return { nodes, links }
}

// Flowing particle along an SVG path
function animateParticles(svg, links, nodeMap) {
  const particleG = svg.append('g').attr('class', 'particles')
  const flowLinks = links.filter(l => ['gives','pipeline','advises','queries'].includes(l.type))

  flowLinks.forEach((l, i) => {
    const src = nodeMap.get(typeof l.source === 'object' ? l.source.id : l.source)
    const tgt = nodeMap.get(typeof l.target === 'object' ? l.target.id : l.target)
    if (!src || !tgt) return

    const circle = particleG.append('circle')
      .attr('r', 2.5)
      .attr('fill', l.type === 'pipeline' ? '#f59e0b' : l.type === 'advises' ? '#34d399' : '#0ea5e9')
      .attr('opacity', 0.7)

    function animate() {
      const dur = 1200 + Math.random() * 1800
      circle
        .attr('cx', src.x || 0).attr('cy', src.y || 0)
        .transition().duration(dur).ease(d3.easeLinear)
        .attr('cx', tgt.x || 0).attr('cy', tgt.y || 0)
        .on('end', () => setTimeout(animate, Math.random() * 600))
    }
    setTimeout(animate, i * 200)
  })

  return particleG
}

const TYPE_LABEL = {
  persona: 'You', ngo: 'NGO', agent: 'AI Agent',
  sdg: 'UN SDG', cause: 'Cause Area',
}

export default function ImpactGraph() {
  const svgRef    = useRef(null)
  const navigate  = useNavigate()
  const { persona, selectedNGOs, earnBadge } = useLegatum()
  const [selected, setSelected] = useState(null)
  const [stats, setStats]       = useState({ nodes: 0, links: 0, agents: 9 })

  const p = persona ? PERSONAS[persona.id] : null

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const W = rect.width || 900, H = rect.height || 600

    d3.select(el).selectAll('*').remove()

    const graph = buildGraph(persona, selectedNGOs)
    setStats({ nodes: graph.nodes.length, links: graph.links.length, agents: 9 })

    const svg = d3.select(el).append('g')

    // Defs: glow filter + gradient
    const defs = d3.select(el).append('defs')
    const glow = defs.append('filter').attr('id', 'glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%')
    glow.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'blur')
    const merge = glow.append('feMerge')
    merge.append('feMergeNode').attr('in', 'blur')
    merge.append('feMergeNode').attr('in', 'SourceGraphic')

    const sim = d3.forceSimulation(graph.nodes)
      .force('link',      d3.forceLink(graph.links).id(d => d.id)
        .distance(d =>
          d.type === 'pipeline' ? 90 :
          d.type === 'gives' && d.strength > 0.5 ? 180 :
          d.type === 'gives' ? 220 :
          d.type === 'aligns' ? 130 :
          d.type === 'advises' || d.type === 'queries' ? 170 :
          140)
        .strength(d => d.strength || 0.4))
      .force('charge',    d3.forceManyBody().strength(d =>
        d.type === 'persona' ? -600 :
        d.type === 'agent'   ? -280 :
        d.type === 'ngo'     ? -220 :
        d.type === 'cause'   ? -160 : -100))
      .force('center',    d3.forceCenter(0, 0).strength(0.04))
      .force('collision', d3.forceCollide(d => d.r + 18))
      .force('x',         d3.forceX(d => {
        if (d.group === 'engine')   return -W * 0.38
        if (d.group === 'analysis') return  W * 0.38
        if (d.group === 'advisory') return  0
        if (d.type === 'sdg')       return  W * 0.22 * (d.id.charCodeAt(3) % 2 === 0 ? 1 : -1)
        if (d.type === 'cause')     return  W * 0.18 * (d.id.charCodeAt(2) % 2 === 0 ? 1 : -1)
        return 0
      }).strength(0.18))
      .force('y',         d3.forceY(d => {
        if (d.group === 'engine')   return -H * 0.28
        if (d.group === 'analysis') return -H * 0.28
        if (d.group === 'advisory') return  H * 0.28
        if (d.type === 'sdg')       return  H * 0.32
        if (d.type === 'cause')     return -H * 0.35
        return 0
      }).strength(0.12))
      .alphaDecay(0.012)

    // Arrow markers
    defs.append('marker').attr('id', 'arrow-teal')
      .attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('refX', 5).attr('refY', 3).attr('orient', 'auto')
      .append('path').attr('d', 'M0,0 L0,6 L6,3 z').attr('fill', 'rgba(14,165,233,0.5)')

    // Links
    const link = svg.append('g').selectAll('line').data(graph.links).join('line')
      .attr('stroke', d =>
        d.type === 'pipeline' ? 'rgba(245,158,11,0.35)' :
        d.type === 'advises'  ? 'rgba(52,211,153,0.35)' :
        d.type === 'queries'  ? 'rgba(129,140,248,0.30)' :
        d.type === 'gives' && d.strength > 0.5 ? 'rgba(14,165,233,0.50)' :
        'rgba(255,255,255,0.08)')
      .attr('stroke-width', d => d.type === 'pipeline' ? 1.5 : d.strength > 0.7 ? 1.5 : 0.8)
      .attr('stroke-dasharray', d => d.type === 'scans' ? '3,4' : null)

    // Nodes
    const nodeG = svg.append('g').selectAll('g').data(graph.nodes).join('g')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null }))
      .on('click', (_, d) => setSelected(d))

    // Outer pulse ring for agents + persona
    nodeG.filter(d => d.type === 'agent' || d.type === 'persona')
      .append('circle')
      .attr('r', d => d.r + 8)
      .attr('fill', 'none')
      .attr('stroke', d => d.type === 'persona' ? '#0ea5e9' : STATUS_COLOR[d.status] || '#f59e0b')
      .attr('stroke-width', 1)
      .attr('opacity', 0.3)
      .each(function(d) {
        const el = d3.select(this)
        function pulse() {
          el.attr('r', d.r + 4).transition().duration(1200 + Math.random() * 600)
            .attr('r', d.r + 14).attr('opacity', 0)
            .transition().duration(0).attr('opacity', 0.3)
            .on('end', pulse)
        }
        setTimeout(pulse, Math.random() * 1000)
      })

    // Main circle
    nodeG.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d =>
        d.type === 'persona' ? '#0ea5e9' :
        d.type === 'agent'   ? (GROUP_COLOR[d.group] || '#818cf8') :
        d.type === 'cause'   ? (d.color || '#0ea5e9') :
        d.type === 'sdg'     ? 'rgba(255,255,255,0.08)' :
        d.anomaly            ? '#ef4444' :
        d.selected           ? '#10b981' :
        '#1e7a5c')
      .attr('stroke', d =>
        d.type === 'persona' ? '#67e8f9' :
        d.type === 'agent'   ? 'rgba(255,255,255,0.2)' :
        d.selected           ? 'rgba(16,185,129,0.5)' :
        'rgba(255,255,255,0.1)')
      .attr('stroke-width', d => d.type === 'persona' ? 2.5 : 1)
      .attr('filter', d => d.type === 'persona' || d.selected ? 'url(#glow)' : null)

    // Layer badge on agents
    nodeG.filter(d => d.type === 'agent')
      .append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('fill', 'rgba(0,0,0,0.8)').attr('font-size', 7).attr('font-weight', 'bold')
      .text(d => `L${d.layer}`)

    // Labels
    nodeG.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.r + 13)
      .attr('fill', d =>
        d.type === 'persona' ? 'rgba(255,255,255,0.9)' :
        d.type === 'agent'   ? 'rgba(255,255,255,0.65)' :
        d.type === 'cause'   ? (d.color || 'rgba(255,255,255,0.5)') :
        'rgba(255,255,255,0.45)')
      .attr('font-size', d => d.type === 'persona' ? 11 : d.type === 'agent' ? 8 : 8)
      .attr('font-weight', d => d.type === 'persona' ? 'bold' : 'normal')
      .text(d => d.label && d.label.length > 18 ? d.label.slice(0, 16) + '…' : d.label)

    // Pan + zoom
    const zoom = d3.zoom().scaleExtent([0.3, 3])
      .on('zoom', e => svg.attr('transform', e.transform))
    d3.select(el).call(zoom)
      .call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(0.62))

    // Particle flow (after first tick settles)
    let particleG = null
    let ticked = 0

    sim.on('tick', () => {
      ticked++
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      nodeG.attr('transform', d => `translate(${d.x},${d.y})`)

      // Start particles after graph settles
      if (ticked === 80 && !particleG) {
        const nodeMap = new Map(graph.nodes.map(n => [n.id, n]))
        particleG = animateParticles(svg, graph.links, nodeMap)
      }
    })

    return () => sim.stop()
  }, [persona, selectedNGOs])

  function proceed() {
    earnBadge('STORY_BUILDER')
    navigate('/arc')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-white/8 flex-shrink-0">
        <div>
          <div className="text-xs text-lbbw-cyan font-bold tracking-widest uppercase">Layer 6 · Living Impact Graph</div>
          <h1 className="text-xl font-bold text-white mt-0.5">LEGATUM Knowledge Network</h1>
        </div>
        <div className="flex items-center gap-4 text-xs text-white/30">
          <span><span className="text-white/60 font-semibold">{stats.nodes}</span> nodes</span>
          <span><span className="text-white/60 font-semibold">{stats.links}</span> edges</span>
          <span><span className="text-lbbw-amber font-semibold">{stats.agents}</span> agents</span>
          <button
            onClick={proceed}
            className="ml-4 px-4 py-2 bg-lbbw-teal text-navy-900 font-bold rounded-lg hover:bg-lbbw-cyan transition-colors text-xs"
          >
            Foundation Arc →
          </button>
        </div>
      </div>

      {/* Graph + sidebar */}
      <div className="flex-1 flex overflow-hidden" style={{ minHeight: 0 }}>
        {/* Graph canvas — takes all space */}
        <div className="flex-1 relative">
          <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block', minHeight: '520px' }} />

          {/* Legend */}
          <div className="absolute bottom-4 left-4 flex flex-wrap gap-3 text-xs text-white/40 pointer-events-none">
            {[
              { color: '#0ea5e9', label: `${p ? p.id : 'You'}` },
              { color: '#10b981', label: 'Selected NGO' },
              { color: '#1e7a5c', label: 'NGO' },
              { color: '#ef4444', label: 'Anomaly' },
              { color: '#818cf8', label: 'Engine Agent' },
              { color: '#f59e0b', label: 'Analysis Agent' },
              { color: '#34d399', label: 'Advisory Agent' },
              { color: 'rgba(255,255,255,0.15)', label: 'SDG' },
            ].map(l => (
              <span key={l.label} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: l.color }} />
                {l.label}
              </span>
            ))}
          </div>

          {/* Zoom hint */}
          <div className="absolute top-4 left-4 text-xs text-white/20 pointer-events-none">
            Scroll to zoom · Drag to pan · Click node for details
          </div>
        </div>

        {/* Side panel — selected node or agent swarm status */}
        <div className="w-64 flex-shrink-0 border-l border-white/8 flex flex-col overflow-y-auto">
          {selected ? (
            <div className="p-4">
              <button onClick={() => setSelected(null)} className="text-xs text-white/30 hover:text-white/50 mb-4">← back</button>
              <div className="text-xs text-white/30 uppercase tracking-widest mb-1">{TYPE_LABEL[selected.type]}</div>
              <div className="font-bold text-white text-sm mb-3">{selected.label}</div>
              {selected.type === 'ngo' && (
                <>
                  <div className={`text-2xl font-bold mb-1 ${selected.score >= 80 ? 'text-green-400' : selected.score >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {selected.score}
                  </div>
                  <div className="text-xs text-white/30 mb-3">Credibility score</div>
                  {selected.anomaly && <div className="text-xs text-red-400 bg-red-400/10 rounded p-2 mb-2">⚠ BlackSwanX anomaly flagged</div>}
                  {selected.selected && <div className="text-xs text-green-400">✓ In your portfolio</div>}
                </>
              )}
              {selected.type === 'agent' && (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: STATUS_COLOR[selected.status] }} />
                    <span className="text-xs capitalize" style={{ color: STATUS_COLOR[selected.status] }}>{selected.status}</span>
                  </div>
                  <div className="text-xs text-white/30">Layer {selected.layer} · {selected.group} pipeline</div>
                </>
              )}
              {selected.type === 'sdg' && (
                <div className="text-xs text-white/40">United Nations Sustainable Development Goal</div>
              )}
            </div>
          ) : (
            <div className="p-4">
              <div className="text-xs text-white/30 uppercase tracking-widest mb-3">Agent Swarm</div>
              <div className="space-y-2">
                {AGENTS.map(ag => (
                  <div key={ag.id} className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-0">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0 animate-pulse"
                      style={{ background: STATUS_COLOR[ag.status], animationDelay: `${ag.layer * 0.1}s` }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-white/60 truncate">{ag.label}</div>
                    </div>
                    <span className="text-xs text-white/20 flex-shrink-0">L{ag.layer}</span>
                  </div>
                ))}
              </div>

              <div className="mt-4 pt-4 border-t border-white/8">
                <div className="text-xs text-white/30 uppercase tracking-widest mb-3">Particle Legend</div>
                <div className="space-y-1.5 text-xs text-white/40">
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#0ea5e9]" /> Giving flow</div>
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#f59e0b]" /> Pipeline data</div>
                  <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#34d399]" /> Advisory signal</div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-white/8">
                <div className="text-xs text-white/30 uppercase tracking-widest mb-2">KG Stats</div>
                {[['Nodes', stats.nodes], ['Edges', stats.links], ['AI Agents', 9], ['NGOs indexed', '12,500+'], ['Docs', 18]].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs py-1 border-b border-white/5 last:border-0">
                    <span className="text-white/30">{k}</span>
                    <span className="text-white/60 font-medium">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
