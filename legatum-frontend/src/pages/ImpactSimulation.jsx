import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { NGOS } from '../data/ngos'

function calcImpact(ngos, monthly, years = 5) {
  const total = monthly * 12 * years
  return ngos.reduce((acc, ngo) => {
    const share = total / ngos.length
    const beneficiaries = Math.round((share / ngo.costPerBeneficiary) * ngo.impactRatio)
    return {
      total: acc.total + beneficiaries,
      euros: acc.euros + share,
    }
  }, { total: 0, euros: 0 })
}

export default function ImpactSimulation() {
  const navigate = useNavigate()
  const { monthly, setMonthly, selectedNGOs, earnBadge } = useLegatum()
  const [years, setYears] = useState(5)

  const ngos = NGOS.filter(n => selectedNGOs.includes(n.id))
  const impact = calcImpact(ngos, monthly, years)
  const totalEuros = (monthly * 12 * years).toLocaleString('de-DE')
  const taxSaving = Math.round(monthly * 12 * years * 0.29).toLocaleString('de-DE')

  function proceed() {
    earnBadge('IMPACT_MULTIPLIER')
    navigate('/graph')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-10">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <div className="text-xs text-lbbw-cyan font-bold tracking-widest uppercase mb-2">Layer 5 · Impact Simulation</div>
          <h1 className="text-3xl font-bold text-white mb-2">Live Impact Simulation</h1>
          <p className="text-white/40">Adjust your giving to see projected real-world impact across your selected NGOs.</p>
        </div>

        {/* Sliders */}
        <div className="rounded-2xl border border-white/10 bg-white/3 p-6 mb-6">
          <div className="mb-6">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-white/60">Monthly contribution</span>
              <span className="text-white font-bold text-lg">€{monthly.toLocaleString('de-DE')}</span>
            </div>
            <input
              type="range"
              min={50}
              max={5000}
              step={50}
              value={monthly}
              onChange={e => setMonthly(+e.target.value)}
              className="w-full accent-[#0ea5e9] cursor-pointer"
            />
            <div className="flex justify-between text-xs text-white/20 mt-1">
              <span>€50</span><span>€5,000</span>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-white/60">Time horizon</span>
              <span className="text-white font-bold text-lg">{years} years</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              step={1}
              value={years}
              onChange={e => setYears(+e.target.value)}
              className="w-full accent-[#0ea5e9] cursor-pointer"
            />
            <div className="flex justify-between text-xs text-white/20 mt-1">
              <span>1yr</span><span>20yr</span>
            </div>
          </div>
        </div>

        {/* Impact cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Beneficiaries', value: impact.total.toLocaleString('de-DE'), accent: 'text-lbbw-teal' },
            { label: 'Total Donated', value: `€${totalEuros}`, accent: 'text-lbbw-cyan' },
            { label: 'Tax Saving (29%)', value: `€${taxSaving}`, accent: 'text-lbbw-amber' },
            { label: 'NGOs Supported', value: ngos.length || '—', accent: 'text-white' },
          ].map(c => (
            <div key={c.label} className="rounded-xl border border-white/10 bg-white/3 p-4 text-center">
              <div className={`text-2xl font-bold mb-1 ${c.accent}`}>{c.value}</div>
              <div className="text-xs text-white/40">{c.label}</div>
            </div>
          ))}
        </div>

        {/* Per-NGO breakdown */}
        {ngos.length > 0 && (
          <div className="rounded-2xl border border-white/10 bg-white/3 p-6 mb-8">
            <h2 className="text-sm font-bold text-white/40 uppercase tracking-widest mb-4">Breakdown by NGO</h2>
            <div className="space-y-3">
              {ngos.map(ngo => {
                const share = (monthly * 12 * years) / ngos.length
                const bene = Math.round((share / ngo.costPerBeneficiary) * ngo.impactRatio)
                return (
                  <div key={ngo.id} className="flex items-center gap-3">
                    <div className="flex-1">
                      <div className="text-sm text-white font-medium">{ngo.name}</div>
                      <div className="text-xs text-white/40">{ngo.cause}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-lbbw-teal font-bold">{bene.toLocaleString('de-DE')}</div>
                      <div className="text-xs text-white/30">beneficiaries</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {ngos.length === 0 && (
          <div className="text-center text-white/30 py-8 mb-8">
            No NGOs selected. <button className="text-lbbw-teal underline" onClick={() => navigate('/ngo-match')}>Go back to select NGOs</button>
          </div>
        )}

        <button
          onClick={proceed}
          className="w-full py-4 bg-lbbw-teal text-navy-900 font-bold rounded-xl hover:bg-lbbw-cyan transition-colors text-lg"
        >
          View Living Impact Graph →
        </button>
      </div>
    </div>
  )
}
