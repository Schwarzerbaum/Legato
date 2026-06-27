import { useState } from 'react'
import { useLegatum } from '../context/LegatumContext'
import { NGOS } from '../data/ngos'
import { PERSONAS } from '../data/personas'

const LAYERS = [
  { id: 1, name: 'Document Ingestion',    status: 'live',   tag: 'Layer 1' },
  { id: 2, name: 'Knowledge Graph Build', status: 'live',   tag: 'Layer 2' },
  { id: 3, name: 'Hybrid RAG Engine',     status: 'live',   tag: 'Layer 3' },
  { id: 4, name: 'BlackSwanX Scoring',    status: 'live',   tag: 'Layer 4' },
  { id: 5, name: 'Impact Simulation',     status: 'active', tag: 'Layer 5' },
  { id: 6, name: 'Living Impact Graph',   status: 'active', tag: 'Layer 6' },
  { id: 7, name: 'Foundation Arc',        status: 'active', tag: 'Layer 7' },
  { id: 8, name: 'Soulbound Passport',    status: 'primed', tag: 'Layer 8' },
  { id: 9, name: 'LBBW Advisor Trigger',  status: 'primed', tag: 'Layer 9' },
]

const STATUS_STYLE = {
  live:   { dot: 'bg-green-400', label: 'Live',   text: 'text-green-400' },
  active: { dot: 'bg-lbbw-cyan', label: 'Active', text: 'text-lbbw-cyan' },
  primed: { dot: 'bg-lbbw-amber', label: 'Primed', text: 'text-lbbw-amber' },
}

function calcScore(persona, ngos, monthly, badgesEarned) {
  let s = 0
  if (persona) s += 30
  if (ngos.length > 0) s += 20
  if (monthly > 200) s += 15
  if (monthly > 1000) s += 10
  if (badgesEarned.size >= 5) s += 15
  if (badgesEarned.has('FOUNDATION_READY')) s += 10
  return Math.min(100, s)
}

export default function AdvisorDashboard() {
  const { persona, selectedNGOs, monthly, badgesEarned, advisorNotified, setAdvisorNotified } = useLegatum()
  const [notifying, setNotifying] = useState(false)
  const [notified, setNotified] = useState(advisorNotified)

  const ngos = NGOS.filter(n => selectedNGOs.includes(n.id))
  const p = persona ? PERSONAS[persona.id] : null
  const score = calcScore(persona, ngos, monthly, badgesEarned)

  const totalBene = ngos.reduce((acc, ngo) => {
    const share = (monthly * 12 * 5) / Math.max(ngos.length, 1)
    return acc + Math.round((share / ngo.costPerBeneficiary) * ngo.impactRatio)
  }, 0)

  async function notify() {
    setNotifying(true)
    await new Promise(r => setTimeout(r, 1800))
    setNotified(true)
    setAdvisorNotified(true)
    setNotifying(false)
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <div className="text-xs text-lbbw-teal font-bold tracking-widest uppercase mb-2">Layer 9 · LBBW Command Center</div>
          <h1 className="text-3xl font-bold text-white mb-1">LBBW Advisor Dashboard</h1>
          <p className="text-white/40">Real-time intelligence for the philanthropic journey. Mirjam Schwink — Senior Stiftungsberaterin.</p>
        </div>

        {/* Hero stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Prospect Score', value: `${score}/100`, accent: score >= 70 ? 'text-lbbw-teal' : 'text-lbbw-amber' },
            { label: 'Monthly Giving', value: `€${monthly.toLocaleString('de-DE')}`, accent: 'text-lbbw-cyan' },
            { label: 'Projected Beneficiaries (5yr)', value: totalBene.toLocaleString('de-DE'), accent: 'text-white' },
            { label: 'Badges Earned', value: `${badgesEarned.size}/14`, accent: 'text-lbbw-amber' },
          ].map(s => (
            <div key={s.label} className="rounded-xl border border-white/10 bg-white/3 p-4 text-center">
              <div className={`text-2xl font-bold mb-1 ${s.accent}`}>{s.value}</div>
              <div className="text-xs text-white/40">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left — active journey + layers */}
          <div className="lg:col-span-2 space-y-5">
            {/* Active journey */}
            {p && (
              <div className={`rounded-2xl border ${p.border} bg-gradient-to-br ${p.color} p-5`}>
                <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Active Journey</div>
                <div className="flex items-center gap-4">
                  <span className="text-4xl">{p.icon}</span>
                  <div>
                    <div className={`text-xl font-bold ${p.accent}`}>{p.id} Persona</div>
                    <div className="text-white/50 text-sm">{p.tagline}</div>
                    <div className="text-white/30 text-xs mt-1">{p.lbbwPath}</div>
                  </div>
                </div>
              </div>
            )}
            {!p && (
              <div className="rounded-2xl border border-white/10 bg-white/3 p-5 text-white/30 text-center">
                No persona yet — <a href="/quiz" className="text-lbbw-teal underline">start the quiz</a>
              </div>
            )}

            {/* 9-layer pipeline */}
            <div className="rounded-2xl border border-white/10 bg-white/3 p-5">
              <div className="text-xs text-white/40 uppercase tracking-widest mb-4">9-Layer Intelligence Pipeline</div>
              <div className="space-y-2">
                {LAYERS.map(l => {
                  const s = STATUS_STYLE[l.status]
                  return (
                    <div key={l.id} className="flex items-center gap-3 py-1.5 border-b border-white/5 last:border-0">
                      <span className="text-xs text-white/20 w-14">{l.tag}</span>
                      <span className="flex-1 text-sm text-white/70">{l.name}</span>
                      <span className={`flex items-center gap-1.5 text-xs ${s.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${l.status === 'live' ? 'animate-pulse' : ''}`} />
                        {s.label}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* NGO credibility feed */}
            <div className="rounded-2xl border border-white/10 bg-white/3 p-5">
              <div className="text-xs text-white/40 uppercase tracking-widest mb-4">BlackSwanX NGO Feed</div>
              <div className="space-y-2">
                {NGOS.map(ngo => (
                  <div key={ngo.id} className="flex items-center gap-3 py-1.5 border-b border-white/5 last:border-0">
                    <span className={`font-bold text-sm w-8 text-center ${
                      ngo.score >= 80 ? 'text-green-400' :
                      ngo.score >= 60 ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>{ngo.score}</span>
                    <span className="flex-1 text-sm text-white/70">{ngo.name}</span>
                    <span className="text-xs">
                      {ngo.anomaly ? '✗' : ngo.verified ? <span className="text-green-400">✓</span> : '—'}
                    </span>
                    {ngo.anomaly && <span className="text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded">Flagged</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right — advisor panel */}
          <div className="space-y-5">
            {/* KG stats */}
            <div className="rounded-2xl border border-white/10 bg-white/3 p-5">
              <div className="text-xs text-white/40 uppercase tracking-widest mb-4">Knowledge Graph</div>
              {[
                { label: 'Nodes', value: '847' },
                { label: 'Edges', value: '2,341' },
                { label: 'Docs indexed', value: '18' },
                { label: 'NGO records', value: '12,500+' },
              ].map(s => (
                <div key={s.label} className="flex justify-between py-2 border-b border-white/5 last:border-0">
                  <span className="text-white/40 text-sm">{s.label}</span>
                  <span className="text-white font-semibold text-sm">{s.value}</span>
                </div>
              ))}
            </div>

            {/* SWYM */}
            {p && (
              <div className="rounded-2xl border border-white/10 bg-white/3 p-5">
                <div className="text-xs text-white/40 uppercase tracking-widest mb-4">SWYM Analysis — {p.id}</div>
                {Object.entries(p.swym).map(([k, v]) => (
                  <div key={k} className="mb-3 last:mb-0">
                    <div className={`text-xs font-bold ${p.accent} uppercase mb-1`}>{k}</div>
                    <div className="text-xs text-white/50 leading-snug">{v}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Advisor trigger */}
            <div className={`rounded-2xl border p-5 ${
              notified ? 'border-lbbw-teal/30 bg-lbbw-teal/5' : 'border-lbbw-amber/30 bg-lbbw-amber/5'
            }`}>
              <div className="text-xs text-lbbw-amber font-bold tracking-widest uppercase mb-2">LBBW Advisor Trigger</div>
              <div className="text-white font-semibold mb-1">Mirjam Schwink</div>
              <div className="text-white/40 text-xs mb-3">Senior Stiftungsberaterin · LBBW Private Banking</div>
              <div className="text-xs text-white/40 mb-4">
                Prospect score: <span className={`font-bold ${score >= 70 ? 'text-lbbw-teal' : 'text-lbbw-amber'}`}>{score}/100</span>
                {score >= 70 ? ' — HOT LEAD' : ' — Warming up'}
              </div>
              {!notified ? (
                <button
                  onClick={notify}
                  disabled={notifying || score < 30}
                  className={`w-full py-3 font-bold rounded-xl text-sm transition-colors ${
                    score >= 30
                      ? 'bg-lbbw-amber text-navy-900 hover:bg-yellow-400'
                      : 'bg-white/10 text-white/30 cursor-not-allowed'
                  }`}
                >
                  {notifying ? 'Sending…' : `Notify Mirjam Schwink${score >= 70 ? ' — HOT LEAD →' : ' →'}`}
                </button>
              ) : (
                <div className="w-full py-3 text-center rounded-xl bg-lbbw-teal/10 text-lbbw-teal text-sm font-semibold">
                  ✓ Mirjam notified · Calendar invite sent
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
