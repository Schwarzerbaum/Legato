'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

const PERSONA_DATA: Record<string,any> = {
  Architect: { color:'#7C3AED', tagline:'You build for centuries, not quarters.', description:'You think in systems and structures. Your giving is designed to outlast you — a foundation, not a donation.', swym:{ see:'Only 12% of German foundations have multi-generational governance structures. Most dissolve within 30 years.', want:'I want to create something that functions without me.', you:'You have the strategic patience to build institutions. Your instinct is to fix systems, not symptoms.', make:'In 12 months you could establish a Treuhandstiftung with €50k seed capital funding 3 education projects in BW.'} },
  Catalyst: { color:'#F59E0B', tagline:'You move fast and aim at roots.', description:'You identify injustice, calculate leverage, and act. Where others give to symptoms, you fund the intervention that makes symptoms unnecessary.', swym:{ see:'Baden-Württemberg has 34,000 long-term unemployed under 25. Existing programs reach 8% of them.', want:'I want to fund the thing that makes all the other problems smaller.', you:'You bring urgency and analytical precision. You will research before you give, then commit fully.', make:'In 12 months your €200/month could fund 47 young people through a vocational program with 91% placement rate.'} },
  Guardian: { color:'#059669', tagline:'You go deep, not wide.', description:'Relationships are your impact. You give your time, your name, and your presence — not just your money. The few people you support will remember you forever.', swym:{ see:'63% of Stuttgart integration program participants say a personal relationship with a donor changed their trajectory.', want:'I want to know the people my giving reaches.', you:'You have rare depth of commitment. You will show up, not just write cheques. That makes you ten times more valuable.', make:'In 12 months your monthly giving plus volunteer hours equals the support of 2 full-time social workers in your community.'} },
  Explorer: { color:'#0EA5E9', tagline:'You follow curiosity into impact.', description:'Giving is how you understand the world. You spread across causes, follow what moves you, and discover what matters through the act of trying. Breadth is your superpower.', swym:{ see:'Philanthropic explorers discover 3x more high-impact organisations than structured givers — and share them.', want:'I want to keep discovering. Giving is how I learn.', you:'You are a signal amplifier. The causes you find and share will be found by others. Your curiosity creates network effects.', make:'In 12 months a diversified portfolio across 4 causes reaches 340 more lives than concentration in one.'} },
}

export default function PersonaPage() {
  const router = useRouter()
  const [persona, setPersona] = useState<string|null>(null)
  const [phase, setPhase] = useState(0)
  const [typedName, setTypedName] = useState('')
  const [showSwym, setShowSwym] = useState(false)

  useEffect(() => {
    const p = localStorage.getItem('lg2_persona') || 'Architect'
    setPersona(p)
    // Phase sequence
    const phases = [0,1,2,3,4,5]
    const delays = [200, 800, 2200, 3500, 4800, 5800]
    const timers = phases.map((ph, i) => setTimeout(() => setPhase(ph+1), delays[i]))
    return () => timers.forEach(clearTimeout)
  }, [])

  useEffect(() => {
    if (phase < 4 || !persona) return
    let i = 0
    const interval = setInterval(() => {
      setTypedName(persona.slice(0, i+1))
      i++
      if (i >= persona.length) clearInterval(interval)
    }, 90)
    return () => clearInterval(interval)
  }, [phase, persona])

  useEffect(() => {
    if (phase >= 6) setShowSwym(true)
  }, [phase])

  if (!persona) return null
  const p = PERSONA_DATA[persona]
  if (!p) return null

  return (
    <div className="min-h-screen bg-[#0A1628] flex flex-col items-center justify-start overflow-y-auto"
      style={{ background: phase >= 2 ? `radial-gradient(ellipse at center, ${p.color}18 0%, #0A1628 60%)` : '#0A1628' }}>

      {/* Phase 1-3: Particle implosion forming symbol */}
      <AnimatePresence>
        {phase >= 2 && phase < 4 && (
          <motion.div className="fixed inset-0 flex items-center justify-center pointer-events-none"
            initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}>
            {[...Array(12)].map((_,i) => (
              <motion.div key={i} className="absolute rounded-full"
                style={{ width:4, height:4, background: p.color,
                  left: `${50 + Math.cos(i/12*Math.PI*2)*30}%`,
                  top: `${50 + Math.sin(i/12*Math.PI*2)*30}%` }}
                animate={{ left:'50%', top:'50%', scale:[1,0.3,1.5,1], opacity:[0,1,0.5,0] }}
                transition={{ duration:1.2, delay:i*0.05, ease:'easeInOut' }} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="w-full max-w-md mx-auto px-6 pt-20 pb-12 flex flex-col items-center">

        {/* Symbol */}
        <AnimatePresence>
          {phase >= 3 && (
            <motion.div className="mb-8 text-8xl"
              initial={{scale:0, opacity:0}} animate={{scale:1, opacity:1}}
              transition={{type:'spring', stiffness:200, damping:15}}>
              {persona==='Architect'?'🏛':persona==='Catalyst'?'⚡':persona==='Guardian'?'🛡':'🧭'}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Persona name */}
        <AnimatePresence>
          {phase >= 4 && (
            <motion.div className="text-center mb-2"
              initial={{opacity:0}} animate={{opacity:1}} transition={{duration:0.4}}>
              <div className="text-xs text-[#475569] font-mono uppercase tracking-widest mb-1">Your Giving Persona</div>
              <h1 className="font-display text-6xl font-bold" style={{color: p.color}}>
                {typedName}<span className="animate-pulse">|</span>
              </h1>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tagline */}
        <AnimatePresence>
          {phase >= 5 && (
            <motion.p className="text-[#94A3B8] text-lg text-center mb-4"
              initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:0.6}}>
              {p.tagline}
            </motion.p>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {phase >= 5 && (
            <motion.p className="text-[#F8FAFC]/80 text-sm text-center leading-relaxed mb-8 max-w-xs"
              initial={{opacity:0}} animate={{opacity:1}} transition={{duration:0.6, delay:0.2}}>
              {p.description}
            </motion.p>
          )}
        </AnimatePresence>

        {/* SWYM card */}
        <AnimatePresence>
          {showSwym && (
            <motion.div className="w-full rounded-2xl border p-6 mb-8"
              style={{ background:'#0F2040', borderColor:`${p.color}40`, boxShadow:`0 0 40px ${p.color}18` }}
              initial={{opacity:0,y:24}} animate={{opacity:1,y:0}} transition={{duration:0.6}}>
              <div className="text-xs font-mono text-[#475569] uppercase tracking-widest mb-4">SWYM Analysis</div>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(p.swym).map(([key, val], i) => (
                  <motion.div key={key} className="p-3 rounded-xl bg-[#162952]"
                    initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:i*0.1}}>
                    <div className="text-xs font-bold uppercase tracking-widest mb-1" style={{color:p.color}}>{key}</div>
                    <div className="text-[#94A3B8] text-xs leading-relaxed">{val as string}</div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {showSwym && (
            <motion.button
              className="w-full py-4 rounded-full font-semibold text-[#0A1628] text-base"
              style={{background:'#00C896'}}
              initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{delay:0.5}}
              whileTap={{scale:0.97}}
              onClick={() => router.push('/discover')}>
              Discover my NGOs →
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
