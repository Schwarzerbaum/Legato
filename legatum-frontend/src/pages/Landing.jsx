import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { PERSONAS } from '../data/personas'

export default function Landing() {
  const navigate = useNavigate()
  const { persona } = useLegatum()

  return (
    <div className="min-h-screen bg-navy-900 pt-14">
      {/* Hero */}
      <section className="relative overflow-hidden px-4 py-24 text-center">
        <div className="absolute inset-0 bg-gradient-to-b from-lbbw-teal/5 to-transparent pointer-events-none" />
        <div className="relative max-w-4xl mx-auto animate-fade-up">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-lbbw-teal/10 border border-lbbw-teal/20 text-lbbw-teal text-xs font-medium mb-6">
            HackXplore 2026 · LBBW Challenge — The Future of Giving
          </div>
          <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 leading-tight">
            Your giving.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-lbbw-teal to-lbbw-cyan">Intelligently matched.</span>
          </h1>
          <p className="text-xl text-white/60 max-w-2xl mx-auto mb-10 leading-relaxed">
            LEGATUM combines AI-powered persona discovery, verified NGO credibility scores,
            and live impact simulation to turn your philanthropic intent into lasting change.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate('/story')}
              className="px-8 py-4 bg-lbbw-teal text-navy-900 font-bold rounded-xl hover:bg-lbbw-cyan transition-colors text-lg"
            >
              ▶ Start Your Story →
            </button>
            <button
              onClick={() => navigate('/quiz')}
              className="px-8 py-4 border border-white/20 text-white rounded-xl hover:bg-white/5 transition-colors text-lg"
            >
              Take the Quiz instead
            </button>
          </div>
          {persona && (
            <div className="mt-4">
              <button
                onClick={() => navigate('/advisor')}
                className="text-sm text-lbbw-teal underline"
              >
                Continue as {persona.id} →
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Stats row */}
      <section className="border-y border-white/10 bg-white/2">
        <div className="max-w-5xl mx-auto px-4 py-8 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: '1,500+', label: 'German Foundations' },
            { value: '€10B+', label: 'Stiftungskapital' },
            { value: '88%', label: 'NGO Credibility Rate' },
            { value: '9 Layers', label: 'Intelligence Stack' },
          ].map(s => (
            <div key={s.label}>
              <div className="text-3xl font-bold text-lbbw-teal">{s.value}</div>
              <div className="text-sm text-white/40 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 4 Personas */}
      <section className="max-w-6xl mx-auto px-4 py-20">
        <h2 className="text-2xl font-bold text-white mb-2 text-center">4 Giving Personas</h2>
        <p className="text-white/40 text-center mb-10">Which one are you?</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.values(PERSONAS).map(p => (
            <button
              key={p.id}
              onClick={() => navigate('/quiz')}
              className={`text-left p-6 rounded-2xl bg-gradient-to-br ${p.color} border ${p.border} hover:brightness-110 transition-all`}
            >
              <div className="text-4xl mb-3">{p.icon}</div>
              <div className={`font-bold text-lg mb-1 ${p.accent}`}>{p.id}</div>
              <div className="text-xs text-white/50 leading-relaxed">{p.tagline}</div>
              <div className="mt-4 text-xs text-white/30">{p.lbbwPath}</div>
            </button>
          ))}
        </div>
      </section>

      {/* 9-layer pipeline teaser */}
      <section className="max-w-4xl mx-auto px-4 pb-20">
        <div className="rounded-2xl border border-white/10 bg-white/3 p-8">
          <h2 className="text-xl font-bold text-white mb-6">9-Layer Intelligence Pipeline</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { layers: '1–3', name: 'Knowledge Engine', desc: 'LBBW doc corpus · NGO ingestion · Hybrid RAG', color: 'text-lbbw-teal' },
              { layers: '4–6', name: 'BlackSwanX', desc: 'Credibility scoring · Anomaly detection · Impact sim', color: 'text-lbbw-amber' },
              { layers: '7–9', name: 'LBBW Advisor', desc: 'Persona match · Foundation Arc · Advisor trigger', color: 'text-lbbw-cyan' },
            ].map(b => (
              <div key={b.layers} className="p-4 rounded-xl bg-white/5">
                <div className={`text-xs font-bold ${b.color} mb-1`}>Layers {b.layers}</div>
                <div className="text-white font-medium mb-1">{b.name}</div>
                <div className="text-xs text-white/40">{b.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
