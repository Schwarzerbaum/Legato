import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { NGOS } from '../data/ngos'

function ScoreRing({ score }) {
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444'
  const r = 36, c = 40, circ = 2 * Math.PI * r
  const dash = (score / 100) * circ
  return (
    <svg width="80" height="80" viewBox="0 0 80 80">
      <circle cx={c} cy={c} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
      <circle
        cx={c} cy={c} r={r}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 40 40)"
      />
      <text x={c} y={c + 5} textAnchor="middle" fill="white" fontSize="14" fontWeight="bold">{score}</text>
    </svg>
  )
}

const LAYERS = [
  { name: 'Financial Transparency', key: 'fin' },
  { name: 'Impact Measurement', key: 'imp' },
  { name: 'Governance', key: 'gov' },
  { name: 'Beneficiary Claim Accuracy', key: 'ben' },
  { name: 'External Validation', key: 'ext' },
]

function subScore(ngo, key) {
  const base = ngo.score
  const offsets = { fin: 2, imp: -3, gov: 4, ben: -6, ext: 1 }
  return Math.max(0, Math.min(100, base + (offsets[key] || 0) + (ngo.anomaly ? -30 : 0)))
}

export default function CredibilityReport() {
  const navigate = useNavigate()
  const { selectedNGOs, earnBadge } = useLegatum()
  const [expanded, setExpanded] = useState(null)

  const ngos = NGOS.filter(n => selectedNGOs.includes(n.id))
    .concat(NGOS.find(n => n.anomaly) ? [] : [NGOS.find(n => n.anomaly)])
    .filter(Boolean)

  function proceed() {
    earnBadge('TRUTH_SEEKER')
    earnBadge('VERIFIED_GIVER')
    navigate('/impact')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <div className="text-xs text-lbbw-amber font-bold tracking-widest uppercase mb-2">BlackSwanX · Layer 4</div>
          <h1 className="text-3xl font-bold text-white mb-2">NGO Credibility Report</h1>
          <p className="text-white/40">AI-powered credibility scoring across 5 dimensions. Anomalies auto-flagged.</p>
        </div>

        <div className="space-y-4 mb-8">
          {NGOS.sort((a, b) => b.score - a.score).map(ngo => (
            <div
              key={ngo.id}
              className={`rounded-2xl border transition-all ${
                ngo.anomaly
                  ? 'border-red-500/30 bg-red-500/5'
                  : selectedNGOs.includes(ngo.id)
                  ? 'border-lbbw-teal/20 bg-lbbw-teal/3'
                  : 'border-white/8 bg-white/2'
              }`}
            >
              <button
                className="w-full text-left p-5 flex items-center gap-5"
                onClick={() => setExpanded(expanded === ngo.id ? null : ngo.id)}
              >
                <ScoreRing score={ngo.score} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-white">{ngo.name}</span>
                    {ngo.verified && <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">✓ Verified</span>}
                    {ngo.anomaly && <span className="text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">⚠ Anomaly</span>}
                  </div>
                  <div className="text-xs text-white/40">{ngo.cause} · Founded {ngo.founded} · {ngo.annual_budget}</div>
                  {ngo.anomaly && ngo.flag && (
                    <div className="text-xs text-red-300/70 mt-1">{ngo.flag}</div>
                  )}
                </div>
                <span className="text-white/30 text-sm">{expanded === ngo.id ? '▲' : '▼'}</span>
              </button>

              {expanded === ngo.id && (
                <div className="px-5 pb-5 pt-0 border-t border-white/5">
                  <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 mt-4">
                    {LAYERS.map(l => {
                      const s = subScore(ngo, l.key)
                      return (
                        <div key={l.key} className="text-center p-3 rounded-xl bg-white/5">
                          <div className={`text-xl font-bold ${s >= 80 ? 'text-green-400' : s >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>{s}</div>
                          <div className="text-xs text-white/30 mt-1 leading-tight">{l.name}</div>
                        </div>
                      )
                    })}
                  </div>
                  <div className="mt-4 text-sm text-white/60 leading-relaxed">{ngo.description}</div>
                  <div className="mt-3 text-xs text-white/30">
                    Cost per beneficiary: <span className="text-white/50">€{ngo.costPerBeneficiary}</span> ·
                    Impact ratio: <span className="text-white/50">{(ngo.impactRatio * 100).toFixed(0)}%</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <button
          onClick={proceed}
          className="w-full py-4 bg-lbbw-teal text-navy-900 font-bold rounded-xl hover:bg-lbbw-cyan transition-colors text-lg"
        >
          Run Impact Simulation →
        </button>
      </div>
    </div>
  )
}
