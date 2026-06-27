import { useState, useEffect, useRef } from 'react'

// ─── Demo data ────────────────────────────────────────────────────────────────

const USER = {
  name: 'Felix M.',
  persona: 'Architect',
  mbtiType: 'INTJ',
  address: '0x7f3a...d91b',
  contributed: 347,
  targetWaveMaker: 500,
  beneficiaries: 169,
  ngoCount: 3,
  monthsActive: 6,
  foundationGate: 3, // gates 1-5
  score: 8.7,        // LBBW advisor prospect score
}

const LAYERS = [
  { id: 1, name: 'React Frontend',          role: 'Persona UX · Impact Graph · Passport',   status: 'live' },
  { id: 2, name: 'Persona Engine',          role: '12 questions → Giving Persona via Claude', status: 'live' },
  { id: 3, name: 'KG Intelligence',         role: 'NGO matching · hybrid RAG · 847 nodes',   status: 'live' },
  { id: 4, name: 'BlackSwanX',              role: 'Credibility scoring · anomaly detection',  status: 'live' },
  { id: 5, name: 'Polygon Chain',           role: 'LegatumPassport.sol · impact milestones',  status: 'live' },
  { id: 6, name: 'Impact Simulation',       role: '€/mo × months × NGO ratio = beneficiaries', status: 'live' },
  { id: 7, name: 'Living Impact Graph',     role: 'D3.js giving universe visualisation',      status: 'live' },
  { id: 8, name: 'Foundation Arc',          role: '5-gate readiness path → Treuhandstiftung', status: 'active' },
  { id: 9, name: 'LBBW Advisor Trigger',   role: 'Prospect scoring → advisor notification',  status: 'primed' },
]

const NGOS = [
  { name: 'PHINEO gAG',             cause: 'Democracy · Social',  score: 94, verified: true,  anomaly: false, flag: null,                        sdg: [16, 10] },
  { name: 'Betterplace.org',        cause: 'Digital platform',    score: 87, verified: true,  anomaly: false, flag: null,                        sdg: [17, 1] },
  { name: 'Über den Tellerrand e.V',cause: 'Integration · Food',  score: 79, verified: true,  anomaly: false, flag: null,                        sdg: [10, 2] },
  { name: 'Initiative Herz e.V.',   cause: 'Children · Health',   score: 41, verified: false, anomaly: true,  flag: 'Claim gap detected — financials unverified', sdg: [3] },
]

const KG_STATS = { nodes: 847, edges: 2341, docs: 18, lastUpdated: '2 min ago' }

const GATES = [
  { label: 'Persona complete',  done: true },
  { label: 'NGOs verified',     done: true },
  { label: 'Impact simulated',  done: true },
  { label: '6-month story',     done: false },
  { label: 'Foundation ready',  done: false },
]

const BADGES_EARNED = ['SEEKER', 'ARCHITECT', 'FIRST_RIPPLE', 'TRUTH_SEEKER', 'VERIFIED_GIVER']

const BADGE_META = {
  SEEKER:         { icon: '🌱' }, ARCHITECT:      { icon: '🏗' },
  FIRST_RIPPLE:   { icon: '💧' }, TRUTH_SEEKER:   { icon: '🔍' },
  VERIFIED_GIVER: { icon: '🛡' }, WAVE_MAKER:     { icon: '🌊' },
  FOUNDATION_READY: { icon: '🏛' }, STIFTER:      { icon: '👑' },
}

// ─── Tiny D3-free impact graph (CSS + SVG) ────────────────────────────────────

const GRAPH_NODES = [
  { id: 'felix',   label: 'Felix', x: 50,  y: 50,  color: '#06b6d4', r: 18 },
  { id: 'phineo',  label: 'PHINEO', x: 20, y: 20,  color: '#22d3ee', r: 13 },
  { id: 'bp',      label: 'Betterplace', x: 80, y: 25, color: '#22d3ee', r: 13 },
  { id: 'udt',     label: 'Ü.d.T.', x: 15, y: 72,  color: '#22d3ee', r: 13 },
  { id: 'demo',    label: 'Democracy', x: 82, y: 68, color: '#a78bfa', r: 10 },
  { id: 'int',     label: 'Integration', x: 48, y: 84, color: '#a78bfa', r: 10 },
  { id: 'dig',     label: 'Digital', x: 85, y: 45,  color: '#a78bfa', r: 10 },
  { id: 'sdg16',   label: 'SDG 16', x: 55,  y: 15,  color: '#f59e0b', r: 7 },
  { id: 'sdg10',   label: 'SDG 10', x: 33,  y: 10,  color: '#f59e0b', r: 7 },
]

const GRAPH_EDGES = [
  ['felix','phineo'], ['felix','bp'], ['felix','udt'],
  ['phineo','demo'], ['phineo','sdg16'], ['bp','dig'],
  ['udt','int'], ['udt','sdg10'], ['demo','sdg16'],
]

function ImpactGraphMini() {
  return (
    <svg viewBox="0 0 100 100" className="w-full h-full" style={{ overflow: 'visible' }}>
      {/* edges */}
      {GRAPH_EDGES.map(([a, b], i) => {
        const na = GRAPH_NODES.find(n => n.id === a)
        const nb = GRAPH_NODES.find(n => n.id === b)
        return (
          <line key={i}
            x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
            stroke="#1e3a4a" strokeWidth="0.8"
          />
        )
      })}
      {/* nodes */}
      {GRAPH_NODES.map(n => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity={0.15} stroke={n.color} strokeWidth="0.8" />
          <text x={n.x} y={n.y + 0.4} textAnchor="middle" dominantBaseline="middle"
            fontSize={n.r > 14 ? '3.5' : '2.8'} fill={n.color} fontWeight="600">
            {n.label.split(' ')[0]}
          </text>
        </g>
      ))}
      {/* pulse on felix */}
      <circle cx={50} cy={50} r={18} fill="none" stroke="#06b6d4" strokeWidth="0.6" opacity="0.4">
        <animate attributeName="r" values="18;24;18" dur="3s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" />
      </circle>
    </svg>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Stat({ value, label, sub }) {
  return (
    <div className="bg-[#111118] border border-gray-800 rounded-xl p-4">
      <div className="text-2xl font-bold text-cyan-400">{value}</div>
      <div className="text-xs text-gray-300 mt-0.5 font-medium">{label}</div>
      {sub && <div className="text-[10px] text-gray-600 mt-0.5">{sub}</div>}
    </div>
  )
}

function LayerRow({ layer }) {
  const dot = {
    live:   'bg-emerald-400 shadow-[0_0_6px_#34d399]',
    active: 'bg-cyan-400 shadow-[0_0_6px_#22d3ee]',
    primed: 'bg-amber-400 shadow-[0_0_6px_#fbbf24]',
    idle:   'bg-gray-600',
  }[layer.status] || 'bg-gray-600'

  const tag = {
    live:   { text: 'LIVE',   cls: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' },
    active: { text: 'ACTIVE', cls: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/20' },
    primed: { text: 'PRIMED', cls: 'text-amber-400 bg-amber-400/10 border-amber-400/20' },
    idle:   { text: 'IDLE',   cls: 'text-gray-500 bg-gray-500/10 border-gray-600/20' },
  }[layer.status] || {}

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-5 text-[10px] text-gray-600 font-mono text-right">{layer.id}</div>
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
      <div className="flex-1 min-w-0">
        <span className="text-xs font-semibold text-gray-200">{layer.name}</span>
        <span className="text-[10px] text-gray-500 ml-2 hidden sm:inline">{layer.role}</span>
      </div>
      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${tag.cls}`}>
        {tag.text}
      </span>
    </div>
  )
}

function NGORow({ ngo }) {
  const scoreColor = ngo.score >= 75 ? 'text-emerald-400' : ngo.score >= 50 ? 'text-amber-400' : 'text-red-400'
  const barColor = ngo.score >= 75 ? 'bg-emerald-400' : ngo.score >= 50 ? 'bg-amber-400' : 'bg-red-400'

  return (
    <div className={`rounded-xl p-3 border ${ngo.anomaly ? 'border-red-500/30 bg-red-500/5' : 'border-gray-800'}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div>
          <span className="text-xs font-semibold text-gray-200">{ngo.name}</span>
          <span className="text-[10px] text-gray-500 ml-2">{ngo.cause}</span>
        </div>
        <div className="flex items-center gap-2">
          {ngo.anomaly && (
            <span className="text-[9px] text-red-400 bg-red-400/10 border border-red-400/20 px-1.5 py-0.5 rounded font-bold">
              ⚠ ANOMALY
            </span>
          )}
          <span className={`text-sm font-bold ${scoreColor}`}>{ngo.score}</span>
          <span className={`text-xs ${ngo.verified ? 'text-emerald-400' : 'text-gray-600'}`}>
            {ngo.verified ? '✓' : '✗'}
          </span>
        </div>
      </div>
      <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${barColor} rounded-full`} style={{ width: `${ngo.score}%` }} />
      </div>
      {ngo.flag && (
        <p className="text-[10px] text-red-300/70 mt-1.5 italic">{ngo.flag}</p>
      )}
      <div className="flex gap-1 mt-1.5">
        {ngo.sdg.map(s => (
          <span key={s} className="text-[9px] text-purple-400 bg-purple-400/10 border border-purple-400/15 px-1 py-0.5 rounded">
            SDG {s}
          </span>
        ))}
      </div>
    </div>
  )
}

function FoundationArc({ gates, active }) {
  const pct = Math.round((gates.filter(g => g.done).length / gates.length) * 100)
  return (
    <div>
      <div className="flex justify-between mb-1.5">
        <span className="text-[10px] text-gray-500 uppercase tracking-widest">Foundation Readiness Arc</span>
        <span className="text-xs font-bold text-cyan-400">{pct}%</span>
      </div>
      <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden mb-3">
        <div className="h-full bg-gradient-to-r from-cyan-500 to-teal-400 transition-all duration-700"
          style={{ width: `${pct}%` }} />
      </div>
      <div className="flex gap-1.5">
        {gates.map((g, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div className={`w-5 h-5 rounded-full border flex items-center justify-center text-[8px] font-bold ${
              g.done ? 'bg-cyan-500 border-cyan-400 text-black' : 'border-gray-700 text-gray-700'
            }`}>
              {g.done ? '✓' : i + 1}
            </div>
            <span className="text-[9px] text-gray-600 text-center leading-tight hidden sm:block">{g.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── LBBW Advisor Trigger ─────────────────────────────────────────────────────

function AdvisorTrigger({ user }) {
  const [notified, setNotified] = useState(false)
  const [pulsing, setPulsing] = useState(true)

  useEffect(() => {
    const t = setInterval(() => setPulsing(p => !p), 1200)
    return () => clearInterval(t)
  }, [])

  const signals = [
    { label: 'Foundation Readiness', value: '60%',  hit: true },
    { label: 'NGOs Verified (3+)',   value: '3 NGOs', hit: true },
    { label: 'Giving History',       value: '6 mo', hit: true },
    { label: 'Contribution Level',   value: '€347', hit: false },
    { label: 'Passport On-Chain',    value: 'Yes',  hit: true },
  ]

  return (
    <div className={`rounded-xl border p-4 transition-all duration-700 ${
      notified
        ? 'border-emerald-500/30 bg-emerald-500/5'
        : 'border-amber-500/30 bg-amber-500/5'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] text-amber-400 uppercase tracking-widest mb-0.5">Layer 9 — LBBW Trigger</p>
          <h3 className="text-sm font-bold text-white">Advisor Notification Panel</h3>
        </div>
        <div className={`text-center transition-opacity duration-500 ${pulsing && !notified ? 'opacity-100' : 'opacity-70'}`}>
          <div className="text-2xl font-bold text-amber-400">{user.score}</div>
          <div className="text-[9px] text-gray-500">/ 10 score</div>
        </div>
      </div>

      <div className="space-y-1.5 mb-4">
        {signals.map(s => (
          <div key={s.label} className="flex items-center justify-between text-xs">
            <span className={s.hit ? 'text-gray-300' : 'text-gray-600'}>{s.label}</span>
            <span className={`font-medium ${s.hit ? 'text-emerald-400' : 'text-gray-600'}`}>
              {s.hit ? '✓ ' : '○ '}{s.value}
            </span>
          </div>
        ))}
      </div>

      {!notified ? (
        <button
          onClick={() => setNotified(true)}
          className="w-full py-2.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-black text-xs font-bold transition-colors"
        >
          Notify Mirjam Schwink — HOT LEAD →
        </button>
      ) : (
        <div className="text-center py-2">
          <p className="text-xs text-emerald-400 font-semibold">✓ Advisor notified</p>
          <p className="text-[10px] text-gray-500 mt-0.5">
            Mirjam Schwink · Stiftungsmanagement · BW-Bank
          </p>
          <p className="text-[10px] text-gray-600 mt-0.5">
            Prospect: {user.name} · {user.persona} · Est. Stiftungsfonds €100k+
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Impact simulation widget ─────────────────────────────────────────────────

function ImpactSim({ user }) {
  const [monthly, setMonthly] = useState(user.contributed)
  const ngoRatio = 0.81
  const beneficiaries = Math.round((monthly * 12 * ngoRatio) / 21.7)

  return (
    <div>
      <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">Impact Simulation — Layer 6</p>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-gray-400 w-20 flex-shrink-0">€/month</span>
        <input
          type="range" min="50" max="1000" step="10" value={monthly}
          onChange={e => setMonthly(Number(e.target.value))}
          className="flex-1 accent-cyan-400"
        />
        <span className="text-sm font-bold text-cyan-400 w-14 text-right">€{monthly}</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[
          { value: `€${monthly * 12}`, label: 'annual' },
          { value: `${Math.round(ngoRatio * 100)}%`, label: 'NGO ratio' },
          { value: beneficiaries, label: 'beneficiaries' },
        ].map(({ value, label }) => (
          <div key={label} className="bg-[#0a0a0f] rounded-lg p-2.5 text-center border border-gray-800">
            <div className="text-lg font-bold text-cyan-400">{value}</div>
            <div className="text-[10px] text-gray-500">{label}</div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-600 mt-2 text-center">
        €{monthly}/mo × 12 × {ngoRatio} NGO ratio ÷ €21.70 per person
      </p>
    </div>
  )
}

// ─── Main dashboard ───────────────────────────────────────────────────────────

export default function LegatumDashboard() {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 5000)
    return () => clearInterval(t)
  }, [])

  const donatedPct = Math.round((USER.contributed / USER.targetWaveMaker) * 100)

  return (
    <div className="space-y-4 max-w-6xl">

      {/* ── Top bar ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            LEGATUM
            <span className="text-xs font-normal text-gray-500 ml-3 tracking-normal">
              Intelligence-First Philanthropic Banking
            </span>
          </h1>
          <p className="text-[10px] text-gray-600 mt-0.5">
            HackXplore 2026 · LBBW Challenge: The Future of Giving
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-emerald-400 rounded-full shadow-[0_0_6px_#34d399]" />
          <span className="text-[10px] text-emerald-400 font-medium">All systems operational</span>
        </div>
      </div>

      {/* ── Hero stats ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat value="1,500+" label="Foundations managed" sub="by LBBW / BW-Bank" />
        <Stat value="€10B+" label="Assets under mgmt" sub="LBBW-Stiftungsfamilie" />
        <Stat value="88%" label="Under-40s want giving ID" sub="but lack digital products" />
        <Stat value="€100k" label="Stiftungsfonds entry" sub="Treuhandstiftung classic €500k" />
      </div>

      {/* ── Active journey + passport strip ── */}
      <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Active Journey</p>
            <div className="flex items-center gap-2">
              <span className="text-lg">🏗</span>
              <div>
                <span className="text-sm font-bold text-white">{USER.name}</span>
                <span className="text-xs text-gray-400 ml-2">{USER.persona} · {USER.mbtiType}</span>
              </div>
            </div>
            <p className="text-[10px] text-gray-500 mt-1 font-mono">{USER.address}</p>
          </div>
          <div className="flex gap-1">
            {BADGES_EARNED.map(b => (
              <span key={b} title={b} className="text-lg">{BADGE_META[b]?.icon}</span>
            ))}
            <span className="text-lg opacity-25">{BADGE_META.WAVE_MAKER?.icon}</span>
            <span className="text-lg opacity-25">{BADGE_META.FOUNDATION_READY?.icon}</span>
            <span className="text-lg opacity-25">{BADGE_META.STIFTER?.icon}</span>
          </div>
        </div>

        {/* Progress toward Wave Maker */}
        <div className="mb-4">
          <div className="flex justify-between mb-1">
            <span className="text-[10px] text-gray-500">Wave Maker progress — €{USER.contributed} of €{USER.targetWaveMaker}</span>
            <span className="text-[10px] text-cyan-400 font-bold">{donatedPct}%</span>
          </div>
          <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-500 to-teal-400 rounded-full transition-all"
              style={{ width: `${donatedPct}%` }} />
          </div>
        </div>

        <FoundationArc gates={GATES} active={USER.foundationGate} />
      </div>

      {/* ── Main grid: 3 columns ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Col 1: 9-layer status */}
        <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
            9-Layer Pipeline
          </p>
          <div className="space-y-0.5 divide-y divide-gray-800/50">
            {LAYERS.map(l => <LayerRow key={l.id} layer={l} />)}
          </div>
        </div>

        {/* Col 2: NGO feed + impact sim */}
        <div className="space-y-4">
          {/* NGO credibility */}
          <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
              BlackSwanX — NGO Credibility Feed
            </p>
            <div className="space-y-2">
              {NGOS.map(n => <NGORow key={n.name} ngo={n} />)}
            </div>
          </div>

          {/* Impact simulation */}
          <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
            <ImpactSim user={USER} />
          </div>
        </div>

        {/* Col 3: Living graph + KG stats + advisor */}
        <div className="space-y-4">
          {/* Living Impact Graph mini */}
          <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Living Impact Graph</p>
              <span className="text-[9px] text-purple-400 border border-purple-400/20 bg-purple-400/5 px-1.5 py-0.5 rounded">
                D3 · Layer 7
              </span>
            </div>
            <div className="h-44 w-full">
              <ImpactGraphMini />
            </div>
          </div>

          {/* KG stats */}
          <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
              Knowledge Graph — Layer 3
            </p>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: KG_STATS.nodes, label: 'nodes', color: 'text-cyan-400' },
                { value: KG_STATS.edges, label: 'edges', color: 'text-purple-400' },
                { value: KG_STATS.docs,  label: 'docs indexed', color: 'text-teal-400' },
                { value: KG_STATS.lastUpdated, label: 'last updated', color: 'text-gray-400' },
              ].map(({ value, label, color }) => (
                <div key={label} className="bg-[#0a0a0f] rounded-lg p-2.5 border border-gray-800">
                  <div className={`text-base font-bold ${color}`}>{value}</div>
                  <div className="text-[10px] text-gray-600">{label}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {['NGO', 'Cause', 'Impact', 'Source', 'Persona', 'Milestone'].map(t => (
                <span key={t} className="text-[9px] text-cyan-300/60 border border-cyan-500/15 bg-cyan-500/5 px-1.5 py-0.5 rounded">
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* LBBW advisor trigger */}
          <AdvisorTrigger user={USER} />
        </div>
      </div>

      {/* ── SWYM bar ── */}
      <div className="bg-[#111118] border border-gray-800 rounded-2xl p-4">
        <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
          SWYM Analysis — Architect persona
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { key: 'See',  label: 'SEE',  text: 'Systemic gaps in philanthropic infrastructure',   color: 'border-cyan-500/30 text-cyan-300' },
            { key: 'Want', label: 'WANT', text: 'Verifiable, data-backed giving with lasting structures', color: 'border-purple-500/30 text-purple-300' },
            { key: 'You',  label: 'YOU',  text: 'An Architect giver — INTJ · High systemic depth', color: 'border-teal-500/30 text-teal-300' },
            { key: 'Make', label: 'MAKE', text: 'Found a Treuhandstiftung via LBBW-Stiftungsfamilie', color: 'border-amber-500/30 text-amber-300' },
          ].map(({ key, label, text, color }) => (
            <div key={key} className={`rounded-xl border p-3 ${color}`}>
              <div className="text-[9px] font-bold mb-1 opacity-70">{label}</div>
              <p className="text-[11px] leading-relaxed">{text}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
