import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { calcPersona } from '../data/questions'

const SCENES = [
  {
    id: 1,
    chapter: 'Chapter I',
    title: 'The Inheritance',
    duration: 24,
    bg: 'from-slate-900 via-zinc-900 to-stone-900',
    accent: '#a78bfa',
    narrator: 'November. A Tuesday afternoon. A call from your late uncle\'s lawyer changes everything.',
    visual: {
      icon: '🏛',
      label: 'Notary Office · Stuttgart',
      sublabel: 'November 2025',
    },
    scene: `Your uncle has left you €80,000 — completely unexpected. By evening, two more calls arrive. You sit with the weight of it. The money could become anything.`,
    prompt: 'What is your first instinct?',
    choices: [
      {
        label: 'You call a tax advisor the next morning.',
        sub: 'The money needs a structure. You spend the week reading about Stiftungsrecht, mapping what a lasting gift could look like.',
        scores: { systemic: 1, depth: 2, identity: 1, engagement: 0 },
      },
      {
        label: 'You transfer €20,000 to the refugee centre you\'ve been meaning to support for years.',
        sub: 'You\'ve waited long enough. The rest can be a plan — but something meaningful should happen today.',
        scores: { systemic: 0, depth: 1, identity: 1, engagement: 2 },
      },
    ],
  },
  {
    id: 2,
    chapter: 'Chapter II',
    title: 'The Dinner',
    duration: 18,
    bg: 'from-zinc-900 via-neutral-900 to-stone-900',
    accent: '#34d399',
    narrator: 'Saturday night. A dinner party in Schwabing. Across the table — an unexpected conversation.',
    visual: {
      icon: '🕯',
      label: 'Private residence · Munich',
      sublabel: 'Saturday evening',
    },
    scene: `An architect across the table runs a small NGO building schools in rural Saxony. Three projects. One staff member. She mentions it offhand — but you hear it clearly. She needs help.`,
    prompt: 'What do you do?',
    choices: [
      {
        label: '"I\'d love to visit one of the projects next month."',
        sub: 'You want to understand the work before funding it. Presence before cheques.',
        scores: { systemic: 0, depth: 2, identity: 0, engagement: 2 },
      },
      {
        label: 'You write a figure on a card. "Get the staff member. That\'s what you need."',
        sub: 'Expertise is fungible. Time isn\'t. You give what makes the most immediate difference.',
        scores: { systemic: 1, depth: 0, identity: 0, engagement: 1 },
      },
    ],
  },
  {
    id: 3,
    chapter: 'Chapter III',
    title: 'The Documentary',
    duration: 21,
    bg: 'from-gray-950 via-slate-900 to-gray-900',
    accent: '#60a5fa',
    narrator: 'Late Sunday. A documentary about child poverty in Germany airs. You don\'t change the channel.',
    visual: {
      icon: '📺',
      label: 'Living room · Frankfurt',
      sublabel: 'Sunday, 22:47',
    },
    scene: `Footage from Leipzig. Families. Statistics on food insecurity among children under 10 in Germany — a country that considers itself one of the world\'s wealthiest. You sit with it long after the credits.`,
    prompt: 'What runs through your mind?',
    choices: [
      {
        label: '"The real problem is policy — housing, wages, systemic failure. Not charity."',
        sub: 'You want to fund the organisations working on root causes. The ones nobody sees.',
        scores: { systemic: 2, depth: 1, identity: 1, engagement: 0 },
      },
      {
        label: '"I need to find who\'s doing the most verifiable work on this. Right now."',
        sub: 'You open your laptop and start reading PHINEO impact reports before midnight.',
        scores: { systemic: 0, depth: 1, identity: 0, engagement: 2 },
      },
    ],
  },
  {
    id: 4,
    chapter: 'Chapter IV',
    title: 'The Question',
    duration: 16,
    bg: 'from-stone-950 via-zinc-900 to-neutral-900',
    accent: '#fb923c',
    narrator: 'Your closest friend asks you something you weren\'t expecting. You pause before answering.',
    visual: {
      icon: '💬',
      label: 'Café Leidinger · Stuttgart',
      sublabel: 'Sunday morning',
    },
    scene: `"If you could only be remembered for one thing you did with your money — what would it be?" You take a long sip of coffee. Two answers come to you simultaneously.`,
    prompt: 'What do you say?',
    choices: [
      {
        label: '"That I built something that outlasts me — a foundation, a permanent endowment."',
        sub: 'Legacy over transaction. Something that compounds across decades without you.',
        scores: { systemic: 2, depth: 2, identity: 2, engagement: 0 },
      },
      {
        label: '"That I was present — real to the people I helped, not just a name on a cheque."',
        sub: 'Connection over scale. You want the people you helped to know you cared.',
        scores: { systemic: 0, depth: 1, identity: 1, engagement: 2 },
      },
    ],
  },
  {
    id: 5,
    chapter: 'Chapter V',
    title: 'The Seat',
    duration: 20,
    bg: 'from-slate-950 via-blue-950 to-slate-900',
    accent: '#a78bfa',
    narrator: 'A foundation board offers you a role. The cause is digital education. Two seats are open.',
    visual: {
      icon: '🤝',
      label: 'LBBW Foundation Board · Stuttgart',
      sublabel: 'Monday, 09:00',
    },
    scene: `You care deeply about the cause — access to digital tools in underserved schools. But two very different roles are available, and you can only choose one.`,
    prompt: 'Which seat do you take?',
    choices: [
      {
        label: 'Strategy & Partnerships — shape where the organisation goes over 10 years.',
        sub: 'You\'d rather design the map than walk any single path on it.',
        scores: { systemic: 2, depth: 1, identity: 1, engagement: 0 },
      },
      {
        label: 'Programme Officer — work directly with schools and teachers every quarter.',
        sub: 'Proximity to impact is what keeps you honest about whether the work is real.',
        scores: { systemic: 0, depth: 2, identity: 0, engagement: 2 },
      },
    ],
  },
]

const PERSONA_META = {
  Architect: { icon: '🏗', color: '#06b6d4', desc: 'You design for permanence. Your giving is a blueprint for systems that outlast you.' },
  Catalyst:  { icon: '🔥', color: '#f97316', desc: 'You ignite movements. Your giving creates momentum that multiplies far beyond the original gift.' },
  Guardian:  { icon: '🛡', color: '#60a5fa', desc: 'You protect what matters. Your giving goes deep — personal, verified, and lasting.' },
  Explorer:  { icon: '🧭', color: '#34d399', desc: 'You map what others miss. Your giving discovers impact before it becomes obvious.' },
}

function VideoPlayer({ scene, progress, onSeek, paused, onToggle }) {
  const barRef = useRef(null)

  function handleBarClick(e) {
    if (!barRef.current) return
    const rect = barRef.current.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    onSeek(Math.max(0, Math.min(1, pct)))
  }

  const mins = Math.floor((scene.duration * progress) / 60)
  const secs = Math.floor((scene.duration * progress) % 60)
  const totalMins = Math.floor(scene.duration / 60)
  const totalSecs = scene.duration % 60

  return (
    <div className="absolute inset-0 flex flex-col justify-end p-4 bg-gradient-to-t from-black/80 via-transparent to-transparent">
      {/* Chapter badge */}
      <div className="absolute top-4 left-4 flex items-center gap-2">
        <div className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur text-xs font-bold text-white/80 border border-white/10">
          {scene.chapter}
        </div>
      </div>
      {/* Location badge */}
      <div className="absolute top-4 right-4 text-right">
        <div className="text-xs text-white/50">{scene.visual.label}</div>
        <div className="text-xs text-white/30">{scene.visual.sublabel}</div>
      </div>

      {/* Progress bar */}
      <div
        ref={barRef}
        onClick={handleBarClick}
        className="w-full h-1 bg-white/20 rounded-full cursor-pointer mb-3 group"
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${progress * 100}%`, background: scene.accent }}
        />
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-3">
        <button onClick={onToggle} className="w-8 h-8 rounded-full bg-white/15 backdrop-blur flex items-center justify-center text-white hover:bg-white/25 transition-colors text-xs">
          {paused ? '▶' : '⏸'}
        </button>
        <span className="text-xs text-white/50 tabular-nums">
          {mins}:{String(secs).padStart(2, '0')} / {totalMins}:{String(totalSecs).padStart(2, '0')}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-white/30">CC</span>
          <span className="text-xs text-white/30">HD</span>
          <span className="text-xs text-white/30">⛶</span>
        </div>
      </div>
    </div>
  )
}

export default function StoryMode() {
  const navigate = useNavigate()
  const { setPersona, earnBadge, persona: ctxPersona } = useLegatum()

  const [scene, setScene]         = useState(0)
  const [progress, setProgress]   = useState(0)
  const [paused, setPaused]       = useState(false)
  const [revealed, setRevealed]   = useState(false)   // choice moment shown
  const [chosen, setChosen]       = useState(null)
  const [scores, setScores]       = useState({ systemic: 0, depth: 0, identity: 0, engagement: 0 })
  const [done, setDone]           = useState(false)
  const [result, setResult]       = useState(null)
  const [claiming, setClaiming]   = useState(false)
  const [typeIdx, setTypeIdx]     = useState(0)        // typewriter for narrator

  const current = SCENES[scene]
  const intervalRef = useRef(null)

  // Wait for context to commit persona before navigating
  useEffect(() => {
    if (claiming && ctxPersona) navigate('/persona')
  }, [claiming, ctxPersona])

  // Typewriter for narrator text
  useEffect(() => {
    setTypeIdx(0)
    const t = setInterval(() => {
      setTypeIdx(i => {
        if (i >= current.narrator.length) { clearInterval(t); return i }
        return i + 1
      })
    }, 28)
    return () => clearInterval(t)
  }, [scene])

  // Video progress ticker
  useEffect(() => {
    if (done || revealed || paused) { clearInterval(intervalRef.current); return }
    intervalRef.current = setInterval(() => {
      setProgress(p => {
        if (p >= 1) {
          clearInterval(intervalRef.current)
          setRevealed(true)
          return 1
        }
        return p + 1 / (current.duration * 20)
      })
    }, 50)
    return () => clearInterval(intervalRef.current)
  }, [scene, paused, revealed, done])

  function seek(pct) {
    setProgress(pct)
    if (pct >= 1) setRevealed(true)
  }

  function pick(i) {
    if (chosen !== null) return
    setChosen(i)
    const opt = current.choices[i]
    const next = {
      systemic:   scores.systemic   + opt.scores.systemic,
      depth:      scores.depth      + opt.scores.depth,
      identity:   scores.identity   + opt.scores.identity,
      engagement: scores.engagement + opt.scores.engagement,
    }

    setTimeout(() => {
      if (scene + 1 < SCENES.length) {
        setScores(next)
        setScene(s => s + 1)
        setProgress(0)
        setRevealed(false)
        setChosen(null)
        setPaused(false)
      } else {
        const personaId = calcPersona(next)
        setScores(next)
        setResult(personaId)
        setDone(true)
      }
    }, 900)
  }

  function claim() {
    setPersona({ id: result, scores })
    earnBadge('SEEKER')
    earnBadge('CATALYST')
    setClaiming(true)
  }

  // — RESULT SCREEN —
  if (done && result) {
    const meta = PERSONA_META[result]
    return (
      <div className="min-h-screen bg-gray-950 pt-14 flex items-center justify-center px-4">
        <div className="max-w-lg w-full animate-fade-up text-center">
          <div className="text-6xl mb-5">{meta.icon}</div>
          <div className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: meta.color }}>
            Your story reveals…
          </div>
          <h1 className="text-6xl font-bold text-white mb-4">{result}</h1>
          <p className="text-white/50 text-lg mb-10 leading-relaxed">{meta.desc}</p>

          <div className="grid grid-cols-2 gap-3 mb-10">
            {Object.entries(scores).map(([dim, val]) => {
              const maxPossible = SCENES.length * 2
              const pct = Math.min(100, Math.round((val / maxPossible) * 100))
              return (
                <div key={dim} className="p-4 rounded-xl bg-white/5 border border-white/8 text-left">
                  <div className="flex justify-between text-xs mb-2">
                    <span className="text-white/40 capitalize">{dim}</span>
                    <span className="text-white/30">{pct}%</span>
                  </div>
                  <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-1000"
                      style={{ width: `${pct}%`, background: meta.color }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          <button
            onClick={claim}
            className="w-full py-4 font-bold rounded-xl text-gray-950 text-lg transition-all hover:brightness-110"
            style={{ background: meta.color }}
          >
            Claim Your Persona →
          </button>
          <button
            onClick={() => { setScene(0); setProgress(0); setDone(false); setResult(null); setChosen(null); setScores({ systemic: 0, depth: 0, identity: 0, engagement: 0 }) }}
            className="mt-3 text-sm text-white/30 hover:text-white/50 transition-colors"
          >
            Watch again
          </button>
        </div>
      </div>
    )
  }

  // — VIDEO PLAYER SCREEN —
  return (
    <div className="min-h-screen bg-gray-950 pt-14 flex flex-col">
      {/* Progress dots */}
      <div className="flex justify-center gap-2 py-4">
        {SCENES.map((s, i) => (
          <div
            key={s.id}
            className={`h-1 rounded-full transition-all duration-500 ${
              i < scene ? 'w-6' : i === scene ? 'w-10' : 'w-3'
            }`}
            style={{
              background: i <= scene ? current.accent : 'rgba(255,255,255,0.12)',
            }}
          />
        ))}
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
        <div className="w-full max-w-3xl">

          {/* Video frame */}
          <div
            className={`relative rounded-2xl overflow-hidden bg-gradient-to-br ${current.bg} border border-white/8 mb-5`}
            style={{ aspectRatio: '16/9' }}
          >
            {/* Scene visual */}
            <div className="absolute inset-0 flex flex-col items-center justify-center select-none">
              <div className="text-8xl mb-4 opacity-20">{current.visual.icon}</div>
            </div>

            {/* Narrator text — typewriter */}
            <div className="absolute inset-0 flex items-center justify-center px-12">
              <div className="text-center">
                <p className="text-white/80 text-xl font-light leading-relaxed italic">
                  "{current.narrator.slice(0, typeIdx)}"
                  <span className="inline-block w-0.5 h-5 bg-white/60 ml-1 animate-pulse align-middle" />
                </p>
              </div>
            </div>

            {/* Video player chrome */}
            <VideoPlayer
              scene={current}
              progress={progress}
              onSeek={seek}
              paused={paused}
              onToggle={() => setPaused(p => !p)}
            />

            {/* CHOICE OVERLAY */}
            {revealed && (
              <div className="absolute inset-0 bg-black/85 backdrop-blur-sm flex flex-col items-center justify-center p-8 animate-fade-up">
                <div className="w-full max-w-xl">
                  <div className="text-center mb-6">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-xs text-white/60 mb-3">
                      ⏸ Scene paused — your choice determines the outcome
                    </div>
                    <p className="text-white font-semibold text-lg">{current.scene}</p>
                    <p className="text-white/50 text-sm mt-2">{current.prompt}</p>
                  </div>

                  <div className="space-y-3">
                    {current.choices.map((opt, i) => (
                      <button
                        key={i}
                        onClick={() => pick(i)}
                        className={`w-full text-left rounded-xl border p-4 transition-all duration-300 ${
                          chosen === i
                            ? 'bg-white/15 border-white/40'
                            : chosen !== null
                            ? 'opacity-30 border-white/8 bg-white/3 cursor-not-allowed'
                            : 'border-white/15 bg-white/6 hover:border-white/30 hover:bg-white/10 cursor-pointer'
                        }`}
                        style={chosen === i ? { borderColor: current.accent } : {}}
                      >
                        <div className={`font-medium text-sm mb-1 ${chosen === i ? 'text-white' : 'text-white/80'}`}>
                          {opt.label}
                        </div>
                        {chosen === i && (
                          <div className="text-xs text-white/40 mt-1 italic">{opt.sub}</div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Scene info bar */}
          <div className="flex items-center justify-between px-1">
            <div>
              <div className="text-white font-semibold">{current.title}</div>
              <div className="text-white/30 text-xs">Scene {scene + 1} of {SCENES.length}</div>
            </div>
            {!revealed && (
              <button
                onClick={() => { setProgress(1); setRevealed(true) }}
                className="text-xs text-white/30 hover:text-white/50 transition-colors border border-white/10 rounded-lg px-3 py-1.5"
              >
                Skip to choice →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
