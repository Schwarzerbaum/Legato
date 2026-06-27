import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { PERSONAS } from '../data/personas'
import { NGOS } from '../data/ngos'

function downloadMD(persona, p) {
  const date = new Date().toISOString().split('T')[0]
  const md = `# LEGATUM Giving Persona Profile
*Generated: ${date} · LBBW HackXplore 2026*

## Persona: ${p.id} ${p.icon}

> ${p.tagline}

${p.description}

## Giving DNA Scores

| Dimension | Score |
|---|---|
| Systemic | ${persona.scores?.systemic ?? '—'} |
| Depth | ${persona.scores?.depth ?? '—'} |
| Identity | ${persona.scores?.identity ?? '—'} |
| Engagement | ${persona.scores?.engagement ?? '—'} |

## SWYM Analysis

**See:** ${p.swym.see}

**Want:** ${p.swym.want}

**You:** ${p.swym.you}

**Make:** ${p.swym.make}

## Recommended LBBW Path

**${p.lbbwPath}** · Segment: ${p.segment}

## Cause Areas

${p.causes.map(c => `- ${c}`).join('\n')}

---
*Powered by LEGATUM · legatum.bwbank.de*
`
  const blob = new Blob([md], { type: 'text/markdown' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `legatum-persona-${p.id.toLowerCase()}-${date}.md`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function PersonaResult() {
  const navigate = useNavigate()
  const { persona, earnBadge } = useLegatum()

  useEffect(() => {
    if (!persona) {
      const t = setTimeout(() => navigate('/quiz'), 300)
      return () => clearTimeout(t)
    }
  }, [persona])

  if (!persona) return (
    <div className="min-h-screen bg-navy-900 pt-14 flex items-center justify-center">
      <div className="text-white/30 text-sm">Calculating your persona…</div>
    </div>
  )

  const p = PERSONAS[persona.id]
  if (!p) return (
    <div className="min-h-screen bg-navy-900 pt-14 flex items-center justify-center">
      <div className="text-white/30 text-sm">Unknown persona — <button className="text-lbbw-teal underline" onClick={() => navigate('/story')}>start over</button></div>
    </div>
  )
  const { scores } = persona

  function proceed() {
    earnBadge('CATALYST')
    navigate('/ngo-match')
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 px-4 py-12">
      <div className="max-w-3xl mx-auto animate-fade-up">
        <div className={`rounded-2xl border ${p.border} bg-gradient-to-br ${p.color} p-8 mb-6`}>
          <div className="text-6xl mb-4">{p.icon}</div>
          <div className="text-xs text-white/40 font-medium tracking-widest uppercase mb-2">Your Giving Persona</div>
          <h1 className={`text-5xl font-bold mb-2 ${p.accent}`}>{p.id}</h1>
          <p className="text-white/70 text-lg mb-6">{p.tagline}</p>
          <p className="text-white/50 leading-relaxed">{p.description}</p>
        </div>

        {/* SWYM */}
        <div className="rounded-2xl border border-white/10 bg-white/3 p-6 mb-6">
          <h2 className="text-sm font-bold text-white/40 tracking-widest uppercase mb-4">SWYM Analysis</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Object.entries(p.swym).map(([key, val]) => (
              <div key={key} className="p-4 rounded-xl bg-white/5">
                <div className={`text-xs font-bold ${p.accent} uppercase tracking-widest mb-1`}>{key}</div>
                <div className="text-white/70 text-sm">{val}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Scores radar-ish */}
        <div className="rounded-2xl border border-white/10 bg-white/3 p-6 mb-6">
          <h2 className="text-sm font-bold text-white/40 tracking-widest uppercase mb-4">Your Giving DNA</h2>
          <div className="space-y-3">
            {Object.entries(scores).map(([dim, val]) => {
              const max = Math.max(24, Math.max(...Object.values(scores)) * 1.2)
              const pct = Math.min(100, Math.round((val / max) * 100))
              return (
                <div key={dim}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-white/50 capitalize">{dim}</span>
                    <span className="text-white/30">{pct}%</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 bg-gradient-to-r from-lbbw-teal to-lbbw-cyan`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* LBBW path */}
        <div className="rounded-2xl border border-lbbw-teal/20 bg-lbbw-teal/5 p-6 mb-8">
          <div className="text-xs text-lbbw-teal font-bold tracking-widest uppercase mb-2">Recommended LBBW Path</div>
          <div className="text-white font-semibold text-lg">{p.lbbwPath}</div>
          <div className="text-white/40 text-sm mt-1">LBBW-Stiftungsfamilie · Segment: {p.segment}</div>
        </div>

        {/* Causes */}
        <div className="flex flex-wrap gap-2 mb-8">
          {p.causes.map(c => (
            <span key={c} className={`px-3 py-1 rounded-full text-xs border ${p.border} ${p.accent} bg-white/3`}>
              {c}
            </span>
          ))}
        </div>

        <div className="flex gap-3 mb-3">
          <button
            onClick={proceed}
            className="flex-1 py-4 bg-lbbw-teal text-navy-900 font-bold rounded-xl hover:bg-lbbw-cyan transition-colors text-lg"
          >
            Find My NGOs →
          </button>
          <button
            onClick={() => downloadMD(persona, p)}
            className="px-5 py-4 border border-white/20 text-white/60 rounded-xl hover:bg-white/5 transition-colors text-sm font-medium"
            title="Download profile as Markdown"
          >
            ↓ .md
          </button>
        </div>
      </div>
    </div>
  )
}
