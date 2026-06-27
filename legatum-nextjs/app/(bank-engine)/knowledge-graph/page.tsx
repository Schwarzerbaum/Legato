'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { addNode, addEdge, queryNeighbours } from '../../../lib/bank-engine/l6-knowledge-graph'
import type { KnowledgeGraph } from '../../../lib/bank-engine/l6-knowledge-graph'

const SEED_GRAPH: KnowledgeGraph = {
  nodes: [
    { id: 'donor-1', type: 'donor', label: 'Familie Müller Stiftung' },
    { id: 'ngo-1', type: 'ngo', label: 'BUND e.V.' },
    { id: 'ngo-2', type: 'ngo', label: 'Welthungerhilfe' },
    { id: 'sdg-13', type: 'sdg', label: 'SDG 13 Climate Action' },
    { id: 'sdg-2', type: 'sdg', label: 'SDG 2 Zero Hunger' },
  ],
  edges: [
    { from: 'donor-1', to: 'ngo-1', relation: 'funds', weight: 0.9 },
    { from: 'donor-1', to: 'ngo-2', relation: 'funds', weight: 0.7 },
    { from: 'ngo-1', to: 'sdg-13', relation: 'targets_sdg', weight: 1 },
    { from: 'ngo-2', to: 'sdg-2', relation: 'targets_sdg', weight: 1 },
  ],
}

const TYPE_COLOR: Record<string, string> = {
  donor: '#c8a96e',
  ngo: '#60a5fa',
  sdg: '#4ade80',
  foundation: '#a78bfa',
}

export default function KnowledgeGraphPage() {
  const [graph] = useState(SEED_GRAPH)
  const [selected, setSelected] = useState<string | null>(null)

  const neighbours = selected ? queryNeighbours(graph, selected) : []

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-xl mx-auto space-y-8"
      >
        <div>
          <p className="text-xs tracking-widest text-[#c8a96e] uppercase mb-2">L6 · AI Agent Knowledge Graph</p>
          <h1 className="text-3xl font-light">Relationship Mesh</h1>
          <p className="mt-2 text-white/40 text-sm">Select a node to explore its connections</p>
        </div>

        <div className="bg-white/5 rounded-2xl p-6 space-y-3">
          {graph.nodes.map(node => (
            <button
              key={node.id}
              onClick={() => setSelected(node.id === selected ? null : node.id)}
              className="w-full flex items-center gap-3 p-3 rounded-xl transition-colors"
              style={{ background: node.id === selected ? `${TYPE_COLOR[node.type]}18` : 'transparent' }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: TYPE_COLOR[node.type] }}
              />
              <span className="text-sm text-left">{node.label}</span>
              <span className="ml-auto text-xs text-white/30 capitalize">{node.type}</span>
            </button>
          ))}
        </div>

        {selected && neighbours.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white/5 rounded-2xl p-6"
          >
            <p className="text-xs text-white/40 uppercase tracking-wider mb-4">Connected nodes</p>
            <div className="space-y-2">
              {neighbours.map(n => (
                <div key={n.id} className="flex items-center gap-3 text-sm">
                  <span className="w-2 h-2 rounded-full" style={{ background: TYPE_COLOR[n.type] }} />
                  <span>{n.label}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </motion.div>
    </main>
  )
}
