import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { PERSONAS } from '../data/personas'

const GATES = [
  {
    id: 1,
    name: 'Persona Complete',
    desc: 'Your giving DNA has been mapped and your archetype identified.',
    check: (ctx) => !!ctx.persona,
    badge: 'SEEKER',
  },
  {
    id: 2,
    name: 'NGOs Verified',
    desc: 'At least one PHINEO-verified NGO added to your portfolio.',
    check: (ctx) => ctx.selectedNGOs.length > 0,
    badge: 'VERIFIED_GIVER',
  },
  {
    id: 3,
    name: 'Impact Simulated',
    desc: 'Projected beneficiaries and tax savings calculated.',
    check: (ctx) => ctx.monthly > 0 && ctx.selectedNGOs.length > 0,
    badge: 'IMPACT_MULTIPLIER',
  },
  {
    id: 4,
    name: '6-Month Story Built',
    desc: 'Your living impact graph and knowledge network is active.',
    check: (ctx) => ctx.badgesEarned.has('STORY_BUILDER'),
    badge: 'STORY_BUILDER',
  },
  {
    id: 5,
    name: 'Foundation Ready',
    desc: 'All gates passed. LBBW advisor trigger is primed.',
    check: (ctx) => [1, 2, 3, 4].every((_, i) => GATES[i].check(ctx)),
    badge: 'FOUNDATION_READY',
  },
]

export default function FoundationArc() {
  const navigate = useNavigate()
  const ctx = useLegatum()
  const { persona, earnBadge } = ctx

  const passed = GATES.filter(g => g.check(ctx)).length
  const pct = Math.round((passed / GATES.length) * 100)
  const p = persona ? PERSONAS[persona.id] : null

  function proceed() {
    earnBadge('FOUNDATION_READY')
    earnBadge('STIFTER')
    navigate('/passport')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <div className="text-xs text-lbbw-amber font-bold tracking-widest uppercase mb-2">Layer 7 · Foundation Readiness Arc</div>
          <h1 className="text-3xl font-bold text-white mb-2">Your Foundation Journey</h1>
          <p className="text-white/40">5 gates to foundation readiness. Complete each step to unlock your LBBW advisor session.</p>
        </div>

        {/* Readiness meter */}
        <div className="rounded-2xl border border-white/10 bg-white/3 p-6 mb-8">
          <div className="flex items-center justify-between mb-3">
            <span className="text-white font-semibold">Readiness</span>
            <span className={`text-2xl font-bold ${pct >= 80 ? 'text-lbbw-teal' : pct >= 60 ? 'text-lbbw-amber' : 'text-white/40'}`}>
              {pct}%
            </span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-lbbw-teal to-lbbw-cyan transition-all duration-700"
              style={{ width: `${pct}%` }}
            />
          </div>
          {p && (
            <div className="mt-3 text-xs text-white/40">
              {p.id} → <span className="text-white/60">{p.lbbwPath}</span>
            </div>
          )}
        </div>

        {/* Gates */}
        <div className="space-y-3 mb-8">
          {GATES.map((gate, i) => {
            const done = gate.check(ctx)
            const prev = i === 0 || GATES[i - 1].check(ctx)
            const active = prev && !done
            return (
              <div
                key={gate.id}
                className={`rounded-xl border p-5 flex items-start gap-4 transition-all ${
                  done
                    ? 'border-lbbw-teal/30 bg-lbbw-teal/5'
                    : active
                    ? 'border-lbbw-amber/30 bg-lbbw-amber/5'
                    : 'border-white/8 bg-white/2 opacity-50'
                }`}
              >
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  done ? 'bg-lbbw-teal text-navy-900' :
                  active ? 'bg-lbbw-amber text-navy-900' :
                  'bg-white/10 text-white/30'
                }`}>
                  {done ? '✓' : gate.id}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className={`font-semibold ${done ? 'text-white' : 'text-white/60'}`}>{gate.name}</span>
                    {done && <span className="text-xs text-lbbw-teal">Gate cleared</span>}
                    {active && <span className="text-xs text-lbbw-amber">Up next</span>}
                  </div>
                  <p className="text-xs text-white/40 mt-1">{gate.desc}</p>
                  {active && (
                    <button
                      onClick={() => navigate(gate.id === 1 ? '/quiz' : gate.id === 2 ? '/ngo-match' : gate.id === 3 ? '/impact' : '/graph')}
                      className="mt-2 text-xs text-lbbw-amber underline"
                    >
                      Complete this step →
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <button
          onClick={proceed}
          disabled={passed < 3}
          className={`w-full py-4 font-bold rounded-xl transition-colors text-lg ${
            passed >= 3
              ? 'bg-lbbw-teal text-navy-900 hover:bg-lbbw-cyan'
              : 'bg-white/10 text-white/30 cursor-not-allowed'
          }`}
        >
          {passed >= 3 ? 'Mint My Impact Passport →' : `Complete ${3 - passed} more gate${3 - passed > 1 ? 's' : ''} to continue`}
        </button>
      </div>
    </div>
  )
}
