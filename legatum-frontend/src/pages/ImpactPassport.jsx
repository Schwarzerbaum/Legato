import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { PERSONAS } from '../data/personas'

const BADGE_DEFS = [
  // Tier 1 — Identity
  { id: 'SEEKER',    tier: 1, label: 'Seeker',     desc: 'Began the giving journey',      icon: '🔍' },
  { id: 'CATALYST',  tier: 1, label: 'Catalyst',   desc: 'Persona discovered',            icon: '⚡' },
  { id: 'GUARDIAN',  tier: 1, label: 'Guardian',   desc: 'First NGO bond formed',         icon: '🛡' },
  { id: 'EXPLORER',  tier: 1, label: 'Explorer',   desc: 'Cause landscape mapped',        icon: '🧭' },
  { id: 'ARCHITECT', tier: 1, label: 'Architect',  desc: 'Impact blueprint drafted',      icon: '🏗' },
  // Tier 2 — Impact
  { id: 'FIRST_RIPPLE',      tier: 2, label: 'First Ripple',     desc: 'First NGO selected',         icon: '💧' },
  { id: 'WAVE_MAKER',        tier: 2, label: 'Wave Maker',       desc: '3+ months of giving',        icon: '🌊' },
  { id: 'IMPACT_MULTIPLIER', tier: 2, label: 'Impact Multiplier',desc: 'Impact simulated',           icon: '✖️' },
  // Tier 3 — Credibility
  { id: 'TRUTH_SEEKER',  tier: 3, label: 'Truth Seeker',    desc: 'Credibility report reviewed', icon: '🔬' },
  { id: 'VERIFIED_GIVER',tier: 3, label: 'Verified Giver',  desc: 'PHINEO-verified NGO funded',  icon: '✅' },
  { id: 'WATCHDOG',      tier: 3, label: 'Watchdog',        desc: 'Anomaly detected and avoided',icon: '👁' },
  // Tier 4 — Legacy
  { id: 'STORY_BUILDER',    tier: 4, label: 'Story Builder',   desc: 'Living impact graph active',  icon: '📖' },
  { id: 'FOUNDATION_READY', tier: 4, label: 'Foundation Ready',desc: 'All 5 readiness gates passed',icon: '🏛' },
  { id: 'STIFTER',          tier: 4, label: 'Stifter',         desc: 'Foundation journey complete', icon: '⭐' },
]

const TIER_LABELS = { 1: 'Identity', 2: 'Impact', 3: 'Credibility', 4: 'Legacy' }
const TIER_COLORS = {
  1: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400' },
  2: { bg: 'bg-teal-500/10', border: 'border-teal-500/20', text: 'text-teal-400' },
  3: { bg: 'bg-purple-500/10', border: 'border-purple-500/20', text: 'text-purple-400' },
  4: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
}

function ShareCard({ persona, badgeCount }) {
  const [copied, setCopied] = useState(false)
  const p = PERSONAS[persona.id]
  const text = `I just mapped my philanthropic DNA on LEGATUM by LBBW.\n\nPersona: ${persona.id} ${p.icon}\nBadges: ${badgeCount}/14\n\nDiscover your giving identity → legatum.bwbank.de\n\n#LEGATUM #FutureOfGiving #LBBW #HackXplore2026`

  function share() {
    window.open(`https://www.linkedin.com/sharing/share-offsite/?url=https://legatum.bwbank.de&summary=${encodeURIComponent(text)}`)
  }

  function copy() {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }

  return (
    <div className="rounded-2xl border border-lbbw-amber/20 bg-gradient-to-br from-navy-800 to-navy-900 p-6">
      <div className="text-xs text-lbbw-amber font-bold tracking-widest uppercase mb-4">Share Your Impact</div>
      <div className="bg-gradient-to-br from-navy-700 to-navy-900 border border-white/10 rounded-xl p-5 mb-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-3xl">{p.icon}</span>
          <div>
            <div className="text-white font-bold">{persona.id} Giver</div>
            <div className="text-lbbw-teal text-sm">{badgeCount}/14 badges earned</div>
          </div>
        </div>
        <p className="text-xs text-white/50 leading-relaxed">{p.tagline}</p>
        <div className="mt-3 text-xs text-white/20">legatum.bwbank.de · LBBW HackXplore 2026</div>
      </div>
      <div className="flex gap-3">
        <button onClick={share} className="flex-1 py-2.5 bg-[#0a66c2] text-white text-sm font-semibold rounded-lg hover:bg-[#0a55a0] transition-colors">
          Share on LinkedIn
        </button>
        <button onClick={copy} className="flex-1 py-2.5 border border-white/20 text-white/70 text-sm rounded-lg hover:bg-white/5 transition-colors">
          {copied ? '✓ Copied!' : 'Copy Text'}
        </button>
      </div>
    </div>
  )
}

export default function ImpactPassport() {
  const navigate = useNavigate()
  const { persona, badgesEarned, passportMinted, setPassportMinted } = useLegatum()
  const [minting, setMinting] = useState(false)

  if (!persona) {
    navigate('/quiz')
    return null
  }

  const p = PERSONAS[persona.id]
  const earnedCount = badgesEarned.size

  async function mint() {
    setMinting(true)
    await new Promise(r => setTimeout(r, 2000))
    setPassportMinted(true)
    setMinting(false)
  }

  const tiers = [1, 2, 3, 4]

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="text-xs text-lbbw-teal font-bold tracking-widest uppercase mb-2">Layer 8 · Soulbound NFT</div>
            <h1 className="text-3xl font-bold text-white mb-1">LEGATUM Impact Passport</h1>
            <p className="text-white/40">Non-transferable on-chain record of your philanthropic journey.</p>
          </div>
          <div className={`px-3 py-1.5 rounded-full text-xs font-bold border ${
            passportMinted ? 'border-lbbw-teal/30 bg-lbbw-teal/10 text-lbbw-teal' : 'border-white/10 text-white/30'
          }`}>
            {passportMinted ? '⛓ On-chain' : 'Not minted'}
          </div>
        </div>

        {/* Passport header */}
        <div className={`rounded-2xl border ${p.border} bg-gradient-to-br ${p.color} p-6 mb-6 flex items-center gap-5`}>
          <div className="text-5xl">{p.icon}</div>
          <div>
            <div className="text-xs text-white/40 uppercase tracking-widest mb-1">Persona</div>
            <div className={`text-3xl font-bold ${p.accent}`}>{p.id}</div>
            <div className="text-white/50 text-sm">{p.lbbwPath}</div>
          </div>
          <div className="ml-auto text-right">
            <div className="text-4xl font-bold text-white">{earnedCount}</div>
            <div className="text-xs text-white/40">/ 14 badges</div>
          </div>
        </div>

        {/* Badge grid by tier */}
        {tiers.map(tier => {
          const tc = TIER_COLORS[tier]
          const tierBadges = BADGE_DEFS.filter(b => b.tier === tier)
          return (
            <div key={tier} className="mb-5">
              <div className={`text-xs font-bold tracking-widest uppercase mb-3 ${tc.text}`}>
                Tier {tier} — {TIER_LABELS[tier]}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {tierBadges.map(b => {
                  const earned = badgesEarned.has(b.id)
                  return (
                    <div
                      key={b.id}
                      className={`rounded-xl border p-3 text-center transition-all ${
                        earned ? `${tc.bg} ${tc.border}` : 'border-white/8 bg-white/2 opacity-40'
                      }`}
                    >
                      <div className="text-2xl mb-1">{earned ? b.icon : '🔒'}</div>
                      <div className={`text-xs font-semibold ${earned ? 'text-white' : 'text-white/30'}`}>{b.label}</div>
                      <div className="text-xs text-white/30 mt-0.5 leading-tight">{b.desc}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Mint */}
        {!passportMinted ? (
          <button
            onClick={mint}
            disabled={minting}
            className="w-full mt-4 py-4 bg-lbbw-teal text-navy-900 font-bold rounded-xl hover:bg-lbbw-cyan transition-colors text-lg disabled:opacity-60 mb-6"
          >
            {minting ? 'Minting on Polygon Mumbai…' : '⛓ Mint My Passport (Free · Polygon Mumbai)'}
          </button>
        ) : (
          <div className="w-full mt-4 py-4 text-center rounded-xl border border-lbbw-teal/20 bg-lbbw-teal/5 text-lbbw-teal font-semibold mb-6">
            ✓ Passport minted · Tx: 0xlegatum…{Date.now().toString(16).slice(-8)} · Polygon Mumbai
          </div>
        )}

        {/* Share card */}
        <ShareCard persona={persona} badgeCount={earnedCount} />

        <button
          onClick={() => navigate('/advisor')}
          className="w-full mt-6 py-4 border border-white/20 text-white rounded-xl hover:bg-white/5 transition-colors"
        >
          View LBBW Advisor Dashboard →
        </button>
      </div>
    </div>
  )
}
