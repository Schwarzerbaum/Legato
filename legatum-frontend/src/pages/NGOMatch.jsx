import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { NGOS } from '../data/ngos'
import { PERSONAS } from '../data/personas'

export default function NGOMatch() {
  const navigate = useNavigate()
  const { persona, selectedNGOs, setSelectedNGOs, earnBadge } = useLegatum()
  const [filter, setFilter] = useState('all')

  const p = persona ? PERSONAS[persona.id] : null
  const causes = ['all', ...new Set(NGOS.map(n => n.cause))]

  const visible = NGOS.filter(n => {
    if (filter !== 'all' && n.cause !== filter) return false
    return true
  }).sort((a, b) => {
    const aMatch = p ? (a.personas.includes(p.id) ? 1 : 0) : 0
    const bMatch = p ? (b.personas.includes(p.id) ? 1 : 0) : 0
    if (bMatch !== aMatch) return bMatch - aMatch
    return b.score - a.score
  })

  function toggle(id) {
    if (selectedNGOs.includes(id)) {
      setSelectedNGOs(selectedNGOs.filter(x => x !== id))
    } else {
      setSelectedNGOs([...selectedNGOs, id])
      earnBadge('FIRST_RIPPLE')
    }
  }

  function proceed() {
    earnBadge('GUARDIAN')
    navigate('/credibility')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">NGO Match</h1>
          {p && (
            <p className="text-white/50">
              Showing NGOs matched to your <span className={p.accent}>{p.id}</span> persona. Select 1–3 to add to your impact portfolio.
            </p>
          )}
        </div>

        {/* Cause filter */}
        <div className="flex gap-2 flex-wrap mb-6">
          {causes.map(c => (
            <button
              key={c}
              onClick={() => setFilter(c)}
              className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                filter === c
                  ? 'border-lbbw-teal bg-lbbw-teal/10 text-lbbw-teal'
                  : 'border-white/10 text-white/40 hover:text-white/60'
              }`}
            >
              {c === 'all' ? 'All Causes' : c}
            </button>
          ))}
        </div>

        {/* NGO grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {NGOS.filter(n => filter === 'all' || n.cause === filter).sort((a, b) => b.score - a.score).map(ngo => {
            const selected = selectedNGOs.includes(ngo.id)
            const personaMatch = p && ngo.personas.includes(p.id)
            return (
              <button
                key={ngo.id}
                onClick={() => !ngo.anomaly && toggle(ngo.id)}
                className={`text-left p-5 rounded-2xl border transition-all ${
                  ngo.anomaly
                    ? 'border-red-500/30 bg-red-500/5 cursor-not-allowed'
                    : selected
                    ? 'border-lbbw-teal bg-lbbw-teal/10'
                    : 'border-white/10 bg-white/3 hover:border-white/20'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="font-semibold text-white text-sm">{ngo.name}</div>
                    <div className="text-xs text-white/40">{ngo.cause} · {ngo.location}</div>
                  </div>
                  <div className={`ml-2 px-2 py-0.5 rounded text-xs font-bold ${
                    ngo.score >= 80 ? 'bg-green-500/20 text-green-400' :
                    ngo.score >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-red-500/20 text-red-400'
                  }`}>
                    {ngo.score}
                  </div>
                </div>

                {ngo.anomaly && (
                  <div className="text-xs text-red-400 mb-2 flex items-center gap-1">
                    <span>⚠</span> BlackSwanX Anomaly Flagged
                  </div>
                )}
                {personaMatch && !ngo.anomaly && (
                  <div className="text-xs text-lbbw-teal mb-2">✓ {p.id} persona match</div>
                )}
                {ngo.verified && (
                  <div className="text-xs text-green-400 mb-2">✓ PHINEO-Wirkt-Siegel</div>
                )}

                <p className="text-xs text-white/40 leading-relaxed">{ngo.impact}</p>

                <div className="mt-3 flex flex-wrap gap-1">
                  {ngo.sdgs.map(s => (
                    <span key={s} className="px-1.5 py-0.5 rounded text-xs bg-white/5 text-white/30">SDG {s}</span>
                  ))}
                </div>

                {selected && (
                  <div className="mt-3 text-xs text-lbbw-teal font-medium">✓ Added to portfolio</div>
                )}
              </button>
            )
          })}
        </div>

        {selectedNGOs.length > 0 && (
          <div className="flex items-center justify-between p-4 rounded-xl border border-lbbw-teal/20 bg-lbbw-teal/5 mb-6">
            <span className="text-white/60 text-sm">{selectedNGOs.length} NGO{selectedNGOs.length > 1 ? 's' : ''} selected</span>
            <button
              onClick={proceed}
              className="px-6 py-2 bg-lbbw-teal text-navy-900 font-bold rounded-lg hover:bg-lbbw-cyan transition-colors"
            >
              Run Credibility Check →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
