import { useState, useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'

const API = '/api'

const PHEROMONE_COLORS = {
  ANOMALY_SCENT: '#ef4444',
  OPPORTUNITY_BLOOM: '#22c55e',
  URGENCY_ALARM: '#eab308',
  DANGER_MARKER: '#d946ef',
  LIQUIDITY_TRACE: '#3b82f6',
}

const NODE_COLORS = {
  fraud: '#ef4444',
  tax: '#22c55e',
  cashflow: '#3b82f6',
  audit: '#f97316',
  regulatory: '#a855f7',
  invoice: '#06b6d4',
  datev: '#eab308',
  default: '#6b7280',
}

export default function NeuralMap() {
  const svgRef = useRef(null)
  const tooltipRef = useRef(null)
  const simulationRef = useRef(null)

  const [network, setNetwork] = useState(null)
  const [pheromones, setPheromones] = useState([])
  const [aweb, setAweb] = useState([])
  const [stats, setStats] = useState(null)
  const [apoptosis, setApoptosis] = useState([])
  const [showUnmyelinated, setShowUnmyelinated] = useState(true)
  const [showPheromones, setShowPheromones] = useState(true)
  const [apoptosisOpen, setApoptosisOpen] = useState(false)
  const [tickLoading, setTickLoading] = useState(false)

  const fetchAll = useCallback(() => {
    fetch(`${API}/neural/network`).then(r => r.json()).then(setNetwork).catch(() => {})
    fetch(`${API}/neural/pheromones`).then(r => r.json()).then(data => setPheromones(Array.isArray(data) ? data : data.pheromones || [])).catch(() => {})
    fetch(`${API}/neural/aweb`).then(r => r.json()).then(data => setAweb(Array.isArray(data) ? data : data.veins || [])).catch(() => {})
    fetch(`${API}/neural/stats`).then(r => r.json()).then(setStats).catch(() => {})
    fetch(`${API}/neural/apoptosis`).then(r => r.json()).then(data => setApoptosis(Array.isArray(data) ? data : data.events || [])).catch(() => {})
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // D3 Force Graph
  useEffect(() => {
    if (!network || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight
    const nodes = (network.nodes || []).map(d => ({ ...d }))
    const links = (network.edges || network.links || network.pathways || []).map(d => ({ ...d }))

    // Defs for animated dash
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#374151')

    const g = svg.append('g')

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => g.attr('transform', event.transform))
    svg.call(zoom)

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', d => d.myelinated ? '#06b6d4' : '#374151')
      .attr('stroke-width', d => d.myelinated ? (d.strength || 3) : 1)
      .attr('stroke-dasharray', d => d.myelinated ? '8 4' : 'none')
      .attr('opacity', d => {
        if (!d.myelinated && !showUnmyelinated) return 0
        return d.myelinated ? 0.8 : 0.3
      })

    // Animate myelinated dashes
    function animateDashes() {
      link.filter(d => d.myelinated)
        .attr('stroke-dashoffset', function () {
          const current = parseFloat(d3.select(this).attr('stroke-dashoffset')) || 0
          return current - 1
        })
      requestAnimationFrame(animateDashes)
    }
    animateDashes()

    // Nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => Math.max(6, Math.min(20, (d.signal_count || 1) * 2)))
      .attr('fill', d => NODE_COLORS[d.type] || NODE_COLORS.default)
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 1.5)
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulationRef.current?.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulationRef.current?.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )

    // Node labels
    const label = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text(d => d.name || d.id)
      .attr('font-size', 10)
      .attr('fill', '#9ca3af')
      .attr('dx', 12)
      .attr('dy', 4)
      .attr('pointer-events', 'none')

    // Pheromone overlay
    if (showPheromones && pheromones.length > 0) {
      g.append('g')
        .attr('class', 'pheromone-layer')
        .selectAll('circle')
        .data(pheromones)
        .join('circle')
        .attr('r', d => 25 * (d.intensity || 0.5))
        .attr('fill', d => PHEROMONE_COLORS[d.type] || '#06b6d4')
        .attr('opacity', d => (d.intensity || 0.5) * 0.4)
        .attr('pointer-events', 'none')
        .each(function (d) {
          // Position pheromones at matching node positions
          const matchNode = nodes.find(n => n.id === d.node_id || n.name === d.node_name)
          if (matchNode) {
            d._node = matchNode
          }
        })
    }

    // Tooltip
    const tooltip = d3.select(tooltipRef.current)

    node.on('mouseover', (event, d) => {
      tooltip
        .style('display', 'block')
        .style('left', `${event.offsetX + 15}px`)
        .style('top', `${event.offsetY - 10}px`)
        .html(`
          <div class="font-semibold text-white">${d.name || d.id}</div>
          <div class="text-gray-400 text-xs mt-1">Type: ${d.type || 'unknown'}</div>
          <div class="text-gray-400 text-xs">Threshold: ${d.threshold ?? '—'}</div>
          <div class="text-gray-400 text-xs">Signals: ${d.signal_count ?? 0}</div>
          <div class="text-gray-400 text-xs">Connections: ${links.filter(l => l.source?.id === d.id || l.target?.id === d.id || l.source === d.id || l.target === d.id).length}</div>
        `)
    })
    .on('mouseout', () => tooltip.style('display', 'none'))

    // Simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => Math.max(8, (d.signal_count || 1) * 2 + 5)))
      .on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y)

        node.attr('cx', d => d.x).attr('cy', d => d.y)
        label.attr('x', d => d.x).attr('y', d => d.y)

        // Update pheromone positions
        g.selectAll('.pheromone-layer circle')
          .attr('cx', d => d._node?.x || 0)
          .attr('cy', d => d._node?.y || 0)
      })

    simulationRef.current = simulation

    return () => simulation.stop()
  }, [network, pheromones, showUnmyelinated, showPheromones])

  const triggerTick = async () => {
    setTickLoading(true)
    try {
      await fetch(`${API}/neural/tick`, { method: 'POST' })
      fetchAll()
    } catch (err) {
      console.error(err)
    } finally {
      setTickLoading(false)
    }
  }

  // Group AWEB veins by source_type
  const awebGrouped = aweb.reduce((acc, vein) => {
    const group = vein.source_type || 'other'
    if (!acc[group]) acc[group] = []
    acc[group].push(vein)
    return acc
  }, {})

  const statusDot = (status) => {
    if (status === 'healthy') return 'bg-green-400'
    if (status === 'degraded') return 'bg-yellow-400'
    return 'bg-red-400'
  }

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Neural Map</h1>
          <p className="text-gray-400 text-sm mt-1">Organism Visualizer — Force-Directed Neural Network</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showUnmyelinated}
              onChange={e => setShowUnmyelinated(e.target.checked)}
              className="accent-cyan-500"
            />
            Unmyelinated
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showPheromones}
              onChange={e => setShowPheromones(e.target.checked)}
              className="accent-cyan-500"
            />
            Pheromones
          </label>
          <button
            onClick={triggerTick}
            disabled={tickLoading}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {tickLoading ? 'Ticking...' : 'Trigger Tick'}
          </button>
          <button
            onClick={fetchAll}
            className="bg-[#111118] border border-gray-700 hover:border-gray-600 text-gray-300 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Main Area: Graph + Sidebar */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* D3 Graph */}
        <div className="flex-[7] bg-[#111118] border border-gray-800 rounded-xl relative overflow-hidden">
          <svg ref={svgRef} className="w-full h-full" />
          <div
            ref={tooltipRef}
            className="absolute hidden bg-[#1a1a24] border border-gray-700 rounded-lg px-3 py-2 text-xs pointer-events-none z-10 shadow-lg"
            style={{ maxWidth: 220 }}
          />
          {/* Legend */}
          <div className="absolute bottom-3 left-3 bg-[#0a0a0f]/80 border border-gray-800 rounded-lg px-3 py-2 text-xs space-y-1">
            <div className="text-gray-500 font-medium mb-1">Node Types</div>
            {Object.entries(NODE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color }} />
                <span className="text-gray-400 capitalize">{type}</span>
              </div>
            ))}
          </div>
        </div>

        {/* AWEB Health Sidebar */}
        <div className="flex-[3] bg-[#111118] border border-gray-800 rounded-xl p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold text-white mb-3">AWEB Health</h3>
          {Object.keys(awebGrouped).length === 0 ? (
            <p className="text-gray-600 text-xs">No veins data.</p>
          ) : (
            Object.entries(awebGrouped).map(([group, veins]) => (
              <div key={group} className="mb-4">
                <div className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-2">{group}</div>
                <div className="space-y-1.5">
                  {veins.map((vein, i) => (
                    <div key={vein.id || i} className="flex items-center gap-2 text-xs">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot(vein.status)}`} />
                      <span className="text-gray-300 truncate flex-1">{vein.name || vein.id}</span>
                      {vein.status === 'degraded' && (
                        <span className="text-yellow-500 text-[10px]">{vein.latency_ms}ms</span>
                      )}
                      {vein.status === 'blocked' && (
                        <span className="text-red-400 text-[10px]">{vein.failure_count} fails</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}

          {/* Pheromone Legend */}
          {showPheromones && (
            <div className="mt-4 pt-3 border-t border-gray-800">
              <div className="text-xs text-gray-500 font-medium mb-2">Pheromone Types</div>
              {Object.entries(PHEROMONE_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2 text-xs mb-1">
                  <span className="w-2.5 h-2.5 rounded-full inline-block opacity-60" style={{ backgroundColor: color }} />
                  <span className="text-gray-400">{type.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl px-5 py-3 flex items-center gap-8">
        <StatItem label="Pheromone Deposits" value={stats?.pheromone_deposits} />
        <StatItem label="Pathways" value={stats?.pathways_count} />
        <StatItem label="Myelinated" value={stats?.myelinated_count} />
        <StatItem label="Signals" value={stats?.signals_count} />
        <StatItem label="Apoptosis Events" value={stats?.apoptosis_events} accent="text-red-400" />
      </div>

      {/* Apoptosis Event Log */}
      <div className="bg-[#111118] border border-red-900/30 rounded-xl">
        <button
          onClick={() => setApoptosisOpen(prev => !prev)}
          className="w-full flex items-center justify-between p-4 text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-red-400">⚠</span>
            <h3 className="text-sm font-semibold text-red-400">Apoptosis Event Log</h3>
            {apoptosis.length > 0 && (
              <span className="bg-red-900/50 text-red-400 text-xs px-2 py-0.5 rounded-full">{apoptosis.length}</span>
            )}
          </div>
          <span className="text-gray-500 text-lg">{apoptosisOpen ? '▾' : '▸'}</span>
        </button>
        {apoptosisOpen && (
          <div className="px-4 pb-4 space-y-2 max-h-60 overflow-y-auto">
            {apoptosis.length === 0 ? (
              <p className="text-gray-600 text-xs">No apoptosis events recorded.</p>
            ) : (
              apoptosis.map((evt, i) => (
                <div key={evt.id || i} className="bg-red-500/5 border border-red-900/30 rounded-lg px-3 py-2 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-red-400 font-medium">{evt.entity_type || 'Entity'}</span>
                    <span className="text-gray-600">{evt.timestamp}</span>
                  </div>
                  <div className="text-gray-400">{evt.reason}</div>
                  <div className="flex gap-4 mt-1 text-gray-500">
                    <span>Consensus: {evt.consensus_score ?? '—'}</span>
                    <span>Threshold: {evt.threshold ?? '—'}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------- Sub-components ---------- */

function StatItem({ label, value, accent }) {
  return (
    <div className="text-center">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-bold font-mono ${accent || 'text-cyan-400'}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}
