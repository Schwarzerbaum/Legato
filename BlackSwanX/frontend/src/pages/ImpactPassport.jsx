import { useState } from 'react'
import ShareCard from '../components/ShareCard'

// ─── Badge catalogue ──────────────────────────────────────────────────────────

const BADGE_META = {
  // Tier 1 — Identity
  SEEKER:            { icon: '🌱', label: 'Seeker',            tier: 1, msg: 'Your giving identity is established. This is permanent.' },
  CATALYST:          { icon: '🔥', label: 'Catalyst',          tier: 1, msg: 'You see systems. You build momentum.' },
  GUARDIAN:          { icon: '🛡', label: 'Guardian',          tier: 1, msg: 'You protect what matters most.' },
  EXPLORER:          { icon: '🧭', label: 'Explorer',          tier: 1, msg: 'You discover what others overlook.' },
  ARCHITECT:         { icon: '🏗', label: 'Architect',         tier: 1, msg: 'You design the infrastructure of change.' },
  // Tier 2 — Impact
  FIRST_RIPPLE:      { icon: '💧', label: 'First Ripple',      tier: 2, msg: 'Every movement begins with one drop.' },
  WAVE_MAKER:        { icon: '🌊', label: 'Wave Maker',        tier: 2, msg: 'Your giving is building momentum.' },
  IMPACT_MULTIPLIER: { icon: '⚡', label: 'Impact Multiplier', tier: 2, msg: 'Your impact now spans multiple streams.' },
  // Tier 3 — Verification
  TRUTH_SEEKER:      { icon: '🔍', label: 'Truth Seeker',      tier: 3, msg: 'You chose intelligence over convenience.' },
  VERIFIED_GIVER:    { icon: '🛡', label: 'Verified Giver',    tier: 3, msg: 'Every euro you give is independently verified.' },
  WATCHDOG:          { icon: '👁', label: 'Watchdog',          tier: 3, msg: 'You caught what others missed.' },
  // Tier 4 — Journey
  STORY_BUILDER:     { icon: '📖', label: 'Story Builder',     tier: 4, msg: 'Your impact narrative is taking shape.' },
  FOUNDATION_READY:  { icon: '🏛', label: 'Foundation Ready',  tier: 4, msg: 'You are ready to build something that outlasts you.' },
  STIFTER:           { icon: '👑', label: 'Stifter',           tier: 4, msg: 'You are now a Stifter. Your legacy begins.' },
}

// Display order for the passport grid
const BADGE_ORDER = [
  ['SEEKER', 'CATALYST', 'GUARDIAN', 'EXPLORER', 'ARCHITECT'],
  ['FIRST_RIPPLE', 'WAVE_MAKER', 'IMPACT_MULTIPLIER'],
  ['TRUTH_SEEKER', 'VERIFIED_GIVER', 'WATCHDOG'],
  ['STORY_BUILDER', 'FOUNDATION_READY', 'STIFTER'],
]

const TIER_LABELS = ['', 'Identity', 'Impact', 'Verification', 'Journey']

// ─── Demo state (replace with ethers.js + contract read in real deploy) ──────

const DEMO_PASSPORT = {
  address: '0x7f3a...d91b',
  persona: 'ARCHITECT',
  mbtiType: 'INTJ',
  createdAt: 'June 27, 2026',
  earnedBadges: new Set([
    'SEEKER', 'ARCHITECT', 'FIRST_RIPPLE', 'TRUTH_SEEKER', 'VERIFIED_GIVER',
  ]),
  contributed: 347,
  targetWaveMaker: 500,
  ngoCount: 3,
  beneficiaries: 169,
  txHash: '0x4a2f8e1b3c9d7f0a5e2b8c1d4f7a3e9b2c5d8f1a',
}

// ─── Components ──────────────────────────────────────────────────────────────

function BadgeTile({ type, earned, onClick }) {
  const meta = BADGE_META[type]
  if (!meta) return null

  return (
    <button
      onClick={() => earned && onClick(type)}
      className={`
        relative flex flex-col items-center gap-1 p-3 rounded-xl border transition-all
        ${earned
          ? 'border-cyan-500/40 bg-cyan-500/5 hover:bg-cyan-500/10 cursor-pointer'
          : 'border-gray-800 bg-gray-900/30 opacity-35 cursor-default'
        }
      `}
    >
      <span className={`text-2xl ${earned ? '' : 'grayscale'}`}>{meta.icon}</span>
      <span className={`text-[10px] font-medium text-center leading-tight ${earned ? 'text-cyan-300' : 'text-gray-600'}`}>
        {meta.label}
      </span>
      {earned && (
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-cyan-400 rounded-full" />
      )}
    </button>
  )
}

function BadgeRow({ types, earnedBadges, onBadgeClick }) {
  return (
    <div className="flex gap-3 flex-wrap">
      {types.map(t => (
        <BadgeTile key={t} type={t} earned={earnedBadges.has(t)} onClick={onBadgeClick} />
      ))}
    </div>
  )
}

function BadgeTooltip({ type, onClose }) {
  const meta = BADGE_META[type]
  if (!meta) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-[#111118] border border-cyan-500/30 rounded-2xl p-6 max-w-sm mx-4 text-center"
        onClick={e => e.stopPropagation()}
      >
        <div className="text-5xl mb-3">{meta.icon}</div>
        <div className="text-lg font-bold text-cyan-400 mb-1">{meta.label}</div>
        <div className="text-xs text-gray-400 mb-1">Tier {meta.tier} — {TIER_LABELS[meta.tier]}</div>
        <p className="text-sm text-gray-300 mt-3 italic">"{meta.msg}"</p>
        <button onClick={onClose} className="mt-5 text-xs text-gray-500 hover:text-gray-300">
          Close
        </button>
      </div>
    </div>
  )
}

// ─── Foundation Progress Arc ──────────────────────────────────────────────────

const GATES = [
  { label: 'Persona complete', done: true },
  { label: 'NGOs verified', done: true },
  { label: 'Impact simulated', done: true },
  { label: '6-month story', done: false },
  { label: 'Foundation ready', done: false },
]

function FoundationArc({ gates }) {
  const pct = Math.round((gates.filter(g => g.done).length / gates.length) * 100)
  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-gray-400">Foundation Readiness</span>
        <span className="text-xs font-bold text-cyan-400">{pct}%</span>
      </div>
      <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 to-teal-400 rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex gap-2">
        {gates.map((g, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div className={`w-4 h-4 rounded-full border flex items-center justify-center text-[8px] ${
              g.done ? 'bg-cyan-500 border-cyan-400 text-black' : 'border-gray-700 text-gray-700'
            }`}>
              {g.done ? '✓' : i + 1}
            </div>
            <span className="text-[9px] text-gray-600 text-center leading-tight">{g.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function ImpactPassport() {
  const [activeBadge, setActiveBadge] = useState(null)
  const [showShare, setShowShare] = useState(false)
  const p = DEMO_PASSPORT
  const earnedCount = p.earnedBadges.size
  const totalBadges = Object.keys(BADGE_META).length
  const progressPct = Math.round((p.contributed / p.targetWaveMaker) * 100)

  return (
    <div className="max-w-xl mx-auto space-y-5">

      {/* Header */}
      <div className="bg-[#111118] border border-gray-800 rounded-2xl p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">
              Legatum Impact Passport
            </p>
            <h1 className="text-xl font-bold text-white">
              {BADGE_META[p.persona]?.icon} {p.persona.charAt(0) + p.persona.slice(1).toLowerCase()} Giver
            </h1>
            <p className="text-sm text-gray-400 mt-0.5">{p.mbtiType} · Est. {p.createdAt}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-cyan-400">{earnedCount}</div>
            <div className="text-[10px] text-gray-500">of {totalBadges} badges</div>
          </div>
        </div>
        <FoundationArc gates={GATES} />
      </div>

      {/* Badges by tier */}
      {BADGE_ORDER.map((row, idx) => (
        <div key={idx} className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
            Tier {idx + 1} — {TIER_LABELS[idx + 1]}
          </p>
          <BadgeRow types={row} earnedBadges={p.earnedBadges} onBadgeClick={setActiveBadge} />
        </div>
      ))}

      {/* Next milestone */}
      <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
        <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">Next Milestone</p>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-300">
            🌊 Wave Maker — €{p.targetWaveMaker} contributed
          </span>
          <span className="text-xs text-cyan-400 font-bold">{progressPct}%</span>
        </div>
        <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-500 to-blue-400 rounded-full"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-2">
          €{p.contributed} contributed · €{p.targetWaveMaker - p.contributed} to go
        </p>
      </div>

      {/* Impact summary */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { value: p.beneficiaries, label: 'beneficiaries' },
          { value: p.ngoCount, label: 'NGOs supported' },
          { value: earnedCount, label: 'badges earned' },
        ].map(({ value, label }) => (
          <div key={label} className="bg-[#111118] border border-gray-800 rounded-xl p-3 text-center">
            <div className="text-2xl font-bold text-cyan-400">{value}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Footer actions */}
      <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4 flex items-center justify-between">
        <div>
          <p className="text-[10px] text-gray-500 mb-0.5">On-chain — Polygon Mumbai</p>
          <p className="text-xs text-gray-400 font-mono">{p.address}</p>
        </div>
        <div className="flex gap-2">
          <a
            href={`https://mumbai.polygonscan.com/tx/${p.txHash}`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-gray-500 hover:text-cyan-400 border border-gray-800 hover:border-cyan-500/30 px-3 py-1.5 rounded-lg transition-colors"
          >
            🔗 Polygon
          </a>
          <button
            onClick={() => setShowShare(true)}
            className="text-xs font-semibold text-black bg-cyan-400 hover:bg-cyan-300 px-3 py-1.5 rounded-lg transition-colors"
          >
            Share Journey
          </button>
        </div>
      </div>

      {/* Modals */}
      {activeBadge && <BadgeTooltip type={activeBadge} onClose={() => setActiveBadge(null)} />}
      {showShare && (
        <ShareCard
          persona={p.persona}
          mbtiType={p.mbtiType}
          earnedBadges={p.earnedBadges}
          beneficiaries={p.beneficiaries}
          ngoCount={p.ngoCount}
          contributed={p.contributed}
          onClose={() => setShowShare(false)}
        />
      )}
    </div>
  )
}
