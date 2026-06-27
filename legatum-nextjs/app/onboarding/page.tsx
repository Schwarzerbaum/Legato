'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { QUESTIONS, calcPersona } from '../../data/questions'

const PERSONA_COLORS: Record<string,string> = { Catalyst:'#F59E0B', Guardian:'#059669', Explorer:'#0EA5E9', Architect:'#7C3AED' }

export default function OnboardingPage() {
  const router = useRouter()
  const [idx, setIdx] = useState(0)
  const [scores, setScores] = useState({ systemic:0, depth:0, identity:0, engagement:0 })
  const [chosen, setChosen] = useState<string|null>(null)
  const [typing, setTyping] = useState(true)
  const [messages, setMessages] = useState<{type:'q'|'a',text:string}[]>([])
  const [bgTint, setBgTint] = useState('')

  const q = QUESTIONS[idx]
  const progress = idx / QUESTIONS.length

  useEffect(() => {
    setTyping(true)
    const t = setTimeout(() => { setTyping(false) }, 900)
    return () => clearTimeout(t)
  }, [idx])

  function choose(opt: typeof q.options[0]) {
    if (chosen || typing) return
    setChosen(opt.key)
    const next = {
      systemic: scores.systemic + (opt.scores.systemic||0),
      depth: scores.depth + (opt.scores.depth||0),
      identity: scores.identity + (opt.scores.identity||0),
      engagement: scores.engagement + (opt.scores.engagement||0),
    }
    setMessages(m => [...m, {type:'q',text:q.text}, {type:'a',text:opt.text}])

    // Accumulate background tint hint
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
    <div className="min-h-screen bg-[#0A1628] flex flex-col pt-14 pb-32 overflow-hidden"
      style={{ background: bgTint ? `radial-gradient(ellipse at top, ${bgTint}08 0%, #0A1628 60%)` : '#0A1628' }}>

      {/* Progress */}
      <div className="fixed top-0 left-0 right-0 z-20 px-4 pt-4 pb-3 bg-[#0A1628]/80 backdrop-blur-md">
        <div className="max-w-lg mx-auto">
          <div className="flex items-center justify-between text-xs text-[#475569] mb-2">
            <span>Question {idx+1} of {QUESTIONS.length}</span>
            <span className="font-mono">Giving DNA Analysis</span>
          </div>
          <div className="flex gap-1">
            {QUESTIONS.map((_,i) => (
              <div key={i} className="flex-1 h-0.5 rounded-full overflow-hidden bg-[#162952]">
                <motion.div className="h-full rounded-full"
                  style={{ background: bgTint || '#00C896' }}
                  animate={{ width: i < idx ? '100%' : i === idx ? '50%' : '0%' }}
                  transition={{ duration: 0.4 }} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Chat feed */}
      <div className="max-w-lg mx-auto w-full px-4 flex flex-col gap-3 mt-4">
        {messages.slice(-6).map((m,i) => (
          <div key={i} className={`flex ${m.type==='a'?'justify-end':'justify-start'}`}>
            <div className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${
              m.type==='q'
                ? 'bg-[#162952] text-[#94A3B8] rounded-[18px_18px_18px_4px]'
                : 'bg-[#00C896]/15 border border-[#00C896]/30 text-[#F8FAFC] rounded-[18px_18px_4px_18px]'
            }`}>{m.text}</div>
          </div>
        ))}

        {/* Current question */}
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
              <motion.div key={`q${idx}`} className="bg-[#162952] px-5 py-4 rounded-[18px_18px_18px_4px] max-w-[85%]"
                initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:0.4}}>
                <p className="text-[#F8FAFC] text-[15px] leading-relaxed">{q.text}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Options fixed at bottom */}
      <AnimatePresence>
        {!typing && (
          <motion.div className="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-4 bg-gradient-to-t from-[#0A1628] via-[#0A1628] to-transparent"
            initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} exit={{opacity:0,y:20}} transition={{duration:0.4}}>
            <div className="max-w-lg mx-auto flex flex-col gap-2">
              {q.options.map((opt, i) => (
                <motion.button key={opt.key}
                  initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} transition={{delay:i*0.08}}
                  onClick={() => choose(opt)}
                  disabled={!!chosen}
                  whileTap={{scale:0.98}}
                  className={`w-full text-left px-5 py-3.5 rounded-xl border text-sm transition-all ${
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
