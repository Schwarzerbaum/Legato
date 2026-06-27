import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLegatum } from '../context/LegatumContext'
import { QUESTIONS, calcPersona } from '../data/questions'

export default function PersonaQuiz() {
  const navigate = useNavigate()
  const { setPersona, earnBadge, persona: ctxPersona } = useLegatum()
  const [idx, setIdx] = useState(0)
  const [scores, setScores] = useState({ systemic: 0, depth: 0, identity: 0, engagement: 0 })
  const [chosen, setChosen] = useState(null)
  const [navigating, setNavigating] = useState(false)

  // Navigate only after context commits the persona update
  useEffect(() => {
    if (navigating && ctxPersona) navigate('/persona')
  }, [navigating, ctxPersona])

  const q = QUESTIONS[idx]
  const progress = ((idx) / QUESTIONS.length) * 100

  function choose(option) {
    setChosen(option)
    const s = q[option].scores
    const next = {
      systemic: scores.systemic + s.systemic,
      depth: scores.depth + s.depth,
      identity: scores.identity + s.identity,
      engagement: scores.engagement + s.engagement,
    }

    setTimeout(() => {
      if (idx + 1 < QUESTIONS.length) {
        setScores(next)
        setIdx(idx + 1)
        setChosen(null)
      } else {
        const personaId = calcPersona(next)
        setPersona({ id: personaId, scores: next })
        earnBadge('SEEKER')
        setNavigating(true)
      }
    }, 400)
  }

  return (
    <div className="min-h-screen bg-navy-900 pt-14 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between text-xs text-white/40 mb-2">
            <span>Question {idx + 1} of {QUESTIONS.length}</span>
            <span>Giving DNA Analysis</span>
          </div>
          <div className="h-1 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-lbbw-teal to-lbbw-cyan transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Question card */}
        <div className="rounded-2xl border border-white/10 bg-white/3 p-8 animate-fade-up">
          <p className="text-2xl font-semibold text-white mb-8 leading-snug">{q.text}</p>
          <div className="space-y-3">
            {['a', 'b'].map(opt => (
              <button
                key={opt}
                onClick={() => !chosen && choose(opt)}
                className={`w-full text-left px-6 py-4 rounded-xl border transition-all ${
                  chosen === opt
                    ? 'border-lbbw-teal bg-lbbw-teal/10 text-white'
                    : chosen
                    ? 'border-white/5 bg-white/2 text-white/30 cursor-not-allowed'
                    : 'border-white/10 bg-white/4 text-white/80 hover:border-lbbw-teal/40 hover:bg-white/8'
                }`}
              >
                <span className="font-medium text-lbbw-teal/60 mr-3">{opt.toUpperCase()}</span>
                {q[opt].text}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
