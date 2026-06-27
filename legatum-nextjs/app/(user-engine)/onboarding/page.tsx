'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { QUESTIONS, calcPersona } from '../../../data/questions'

export default function OnboardingPage() {
  const router = useRouter()
  const [idx, setIdx] = useState(0)
  const [scores, setScores] = useState({ systemic:0, depth:0, identity:0, engagement:0 })
  const [chosen, setChosen] = useState<string|null>(null)
  const [typing, setTyping] = useState(true)
  const [messages, setMessages] = useState<{type:'q'|'a',text:string}[]>([])
  const [bgTint, setBgTint] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const q = QUESTIONS[idx]

  useEffect(() => {
    setTyping(true)
    const t = setTimeout(() => setTyping(false), 900)
    return () => clearTimeout(t)
  }, [idx])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  function choose(opt: { key: string; text: string; scores: Record<string, number> }) {
    if (chosen || typing) return
    setChosen(opt.key)
    const next = {
      systemic: scores.systemic + (opt.scores.systemic||0),
      depth: scores.depth + (opt.scores.depth||0),
      identity: scores.identity + (opt.scores.identity||0),
      engagement: scores.engagement + (opt.scores.engagement||0),
    }
    setMessages(m => [...m, {type:'q', text:q.text}, {type:'a', text:opt.text}])

    const dominant = Object.entries(next).sort((a,b)=>b[1]-a[1])[0][0]
    const tintMap: Record<string,string> = { systemic:'#7C3AED', depth:'#059669', identity:'#F59E0B', engagement:'#0EA5E9' }
    setBgTint(tintMap[dominant])

    setTimeout(() => {
      if (idx + 1 < QUESTIONS.length) {
        setScores(next); setIdx(idx+1); setChosen(null)
      } else {
        const persona = calcPersona(next)
        if (typeof window !== 'undefined') {
          localStorage.setItem('lg2_scores', JSON.stringify(next))
          localStorage.setItem('lg2_persona', persona)
        }
        router.push('/persona')
      }
    }, 500)
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden"
      style={{ background: bgTint ? `radial-gradient(ellipse at top, ${bgTint}10 0%, #0A1628 55%)` : '#0A1628' }}>

      {/* Progress — top bar */}
      <div className="flex-shrink-0 px-4 pt-4 pb-3 border-b border-[#162952] bg-[#0A1628]/95 backdrop-blur-md">
        <div className="max-w-md mx-auto">
          <div className="flex items-center justify-between text-xs text-[#475569] mb-2">
            <span>Question {idx+1} of {QUESTIONS.length}</span>
            <span className="font-mono text-[#00C896]/70">Giving DNA Analysis</span>
          </div>
          <div className="flex gap-1">
            {QUESTIONS.map((_,i) => (
              <div key={i} className="flex-1 h-0.5 rounded-full bg-[#162952] overflow-hidden">
                <motion.div className="h-full rounded-full"
                  style={{ background: bgTint || '#00C896' }}
                  animate={{ width: i < idx ? '100%' : i === idx ? '50%' : '0%' }}
                  transition={{ duration: 0.4 }} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Scrollable chat history */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-md mx-auto px-4 pt-4 pb-4 flex flex-col gap-3">
          {messages.map((m,i) => (
            <div key={i} className={`flex ${m.type==='a' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[78%] px-4 py-3 text-sm leading-relaxed ${
                m.type==='q'
                  ? 'bg-[#162952] text-[#94A3B8] rounded-[18px_18px_18px_4px]'
                  : 'bg-[#00C896]/15 border border-[#00C896]/30 text-[#F8FAFC] rounded-[18px_18px_4px_18px]'
              }`}>{m.text}</div>
            </div>
          ))}

          {/* Typing / current question */}
          <div className="flex justify-start">
            <AnimatePresence mode="wait">
              {typing ? (
                <motion.div key="typing" className="bg-[#162952] px-5 py-4 rounded-[18px_18px_18px_4px]"
                  initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0}}>
                  <div className="flex gap-1.5">
                    {[0,1,2].map(i => (
                      <motion.div key={i} className="w-2 h-2 rounded-full bg-[#475569]"
                        animate={{y:[0,-5,0]}} transition={{duration:0.8,delay:i*0.15,repeat:Infinity}} />
                    ))}
                  </div>
                </motion.div>
              ) : (
                <motion.div key={`q${idx}`}
                  className="bg-[#162952] px-5 py-4 rounded-[18px_18px_18px_4px] max-w-[78%]"
                  initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:0.4}}>
                  <p className="text-[#F8FAFC] text-[15px] leading-relaxed">{q.text}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Options — sticks to bottom naturally */}
      <AnimatePresence>
        {!typing && (
          <motion.div
            className="flex-shrink-0 border-t border-[#162952] bg-[#0A1628]/95 backdrop-blur-md"
            initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} exit={{opacity:0,y:16}} transition={{duration:0.3}}>
            <div className="max-w-md mx-auto px-4 py-3 flex flex-col gap-2">
              {q.options.map((opt, i) => (
                <motion.button key={opt.key}
                  initial={{opacity:0,x:-8}} animate={{opacity:1,x:0}} transition={{delay:i*0.06}}
                  onClick={() => choose(opt as { key: string; text: string; scores: Record<string, number> })}
                  disabled={!!chosen}
                  whileTap={{scale:0.98}}
                  className={`w-full text-left px-5 py-3 rounded-xl border text-sm transition-all ${
                    chosen===opt.key
                      ? 'border-[#00C896] bg-[#00C896]/10 text-[#F8FAFC]'
                      : chosen
                      ? 'border-[#162952] bg-[#0F2040]/50 text-[#475569] cursor-not-allowed'
                      : 'border-[#162952] bg-[#0F2040] text-[#94A3B8] hover:border-[#00C896]/40 hover:bg-[#162952] hover:text-[#F8FAFC]'
                  }`}>
                  <span className="text-[#00C896]/50 font-mono mr-3 text-xs">{opt.key}</span>
                  {opt.text}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
