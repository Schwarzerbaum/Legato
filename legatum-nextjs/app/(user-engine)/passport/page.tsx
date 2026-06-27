'use client'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRouter } from 'next/navigation'
import BADGES from '../../../data/badges.json'

const TREE_STAGES = [
  { stage:0, name:'Seed',        emoji:'🌱', desc:'Something dormant. Full of potential.', threshold:0 },
  { stage:1, name:'Sprout',      emoji:'🌿', desc:'Something is growing.',                 threshold:50 },
  { stage:2, name:'Sapling',     emoji:'🪴', desc:'Your roots are forming.',               threshold:500 },
  { stage:3, name:'Young Tree',  emoji:'🌳', desc:'Your impact is branching.',             threshold:5000 },
  { stage:4, name:'Full Tree',   emoji:'🌲', desc:'You are creating shelter for others.',  threshold:50000 },
  { stage:5, name:'Ancient Tree',emoji:'🎋', desc:'Your legacy is taking shape.',          threshold:100000 },
  { stage:6, name:'Forest',      emoji:'🌳🌲🌴', desc:'You created an ecosystem.',        threshold:500000 },
]

export default function PassportPage() {
  const router = useRouter()
  const [persona, setPersona] = useState('Architect')
  const [total, setTotal] = useState(0)
  const [earned, setEarned] = useState<string[]>(['SEEKER','ARCHITECT'])
  const [selectedBadge, setSelectedBadge] = useState<any>(null)
  const [stage, setStage] = useState(0)
  const [tilt, setTilt] = useState({x:0,y:0})

  useEffect(() => {
    const p = localStorage.getItem('lg2_persona') || 'Architect'
    setPersona(p)
    if (p) setEarned(['SEEKER', p.toUpperCase()])

    const onMotion = (e: DeviceOrientationEvent) => {
      setTilt({ x: (e.beta||0)*0.08, y: (e.gamma||0)*0.08 })
    }
    window.addEventListener('deviceorientation', onMotion)
    return () => window.removeEventListener('deviceorientation', onMotion)
  }, [])

  const currentStage = TREE_STAGES[stage]
  const nextStage = TREE_STAGES[stage+1]
  const progress = nextStage ? Math.min(1, total/nextStage.threshold) : 1

  const PERSONA_COLOR: Record<string,string> = { Catalyst:'#F59E0B', Guardian:'#059669', Explorer:'#0EA5E9', Architect:'#7C3AED' }
  const pColor = PERSONA_COLOR[persona] || '#00C896'

  return (
    <div className="min-h-screen bg-[#0A1628] pt-12 pb-24">
      <div className="max-w-lg mx-auto px-4">
        <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-1">Layer 8 · Impact Passport</div>
        <h1 className="font-display text-2xl text-[#F8FAFC] mb-6">My Giving Journey</h1>

        {/* Tree card with gyroscope */}
        <motion.div
          className="rounded-2xl border border-[#162952] bg-[#0F2040] p-8 mb-6 flex flex-col items-center"
          style={{
            transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
            transition: 'transform 0.1s linear',
            boxShadow: `0 0 60px ${pColor}15`,
          }}>

          {/* Tree emoji + glow */}
          <motion.div className="text-7xl mb-4"
            animate={{ scale:[1,1.04,1] }} transition={{ duration:4, repeat:Infinity, ease:'easeInOut' }}>
            {currentStage.emoji}
          </motion.div>

          <div className="text-xs text-[#475569] font-mono uppercase tracking-widest mb-1">Stage {stage} of 6</div>
          <h2 className="font-display text-2xl mb-1" style={{color:pColor}}>{currentStage.name}</h2>
          <p className="text-[#94A3B8] text-sm text-center mb-6">{currentStage.desc}</p>

          {/* Progress to next */}
          {nextStage && (
            <div className="w-full">
              <div className="flex justify-between text-xs text-[#475569] mb-2">
                <span>€{total.toLocaleString()}</span>
                <span>€{nextStage.threshold.toLocaleString()} → {nextStage.name}</span>
              </div>
              <div className="h-1.5 bg-[#162952] rounded-full overflow-hidden">
                <motion.div className="h-full rounded-full" style={{background:pColor}}
                  animate={{width:`${progress*100}%`}} transition={{duration:0.8}} />
              </div>
            </div>
          )}

          {/* Demo stage controls */}
          <div className="flex gap-2 mt-4">
            <button onClick={()=>setStage(s=>Math.max(0,s-1))} className="text-xs text-[#475569] px-3 py-1 border border-[#162952] rounded-lg">←</button>
            <span className="text-xs text-[#475569] px-2 py-1">demo stage</span>
            <button onClick={()=>setStage(s=>Math.min(6,s+1))} className="text-xs text-[#475569] px-3 py-1 border border-[#162952] rounded-lg">→</button>
          </div>
        </motion.div>

        {/* Badges */}
        <div className="mb-6">
          <div className="text-xs text-[#475569] font-mono uppercase tracking-widest mb-3">Badges · {earned.length}/{BADGES.length}</div>
          <div className="grid grid-cols-4 gap-3">
            {(BADGES as any[]).map((b:any) => {
              const isEarned = earned.includes(b.id)
              return (
                <button key={b.id} onClick={()=>isEarned&&setSelectedBadge(b)}
                  className={`aspect-square rounded-2xl flex flex-col items-center justify-center gap-1 border transition-all ${
                    isEarned ? 'bg-[#0F2040] border-[#162952] cursor-pointer hover:border-[#00C896]/30' : 'bg-[#0A1628] border-[#0F2040] opacity-30 cursor-default'
                  }`}>
                  <span className={`text-xl ${isEarned?'':'grayscale'}`}>{b.icon}</span>
                  <span className="text-[9px] text-[#475569] leading-none text-center px-1">{b.name}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Foundation readiness */}
        <div className="rounded-2xl border border-[#162952] bg-[#0F2040] p-5 mb-6">
          <div className="text-xs text-[#475569] font-mono uppercase tracking-widest mb-3">Foundation Readiness</div>
          <div className="flex items-center gap-4">
            <div className="flex-1 h-2 bg-[#162952] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[#00C896] to-[#7C3AED] rounded-full" style={{width:'24%'}} />
            </div>
            <span className="text-[#F8FAFC] font-mono text-sm">24%</span>
          </div>
          <div className="mt-3 text-xs text-[#475569]">5 gates to unlock Foundation Arc</div>
          <button onClick={()=>router.push('/foundation')} className="mt-3 w-full py-3 border border-[#00C896]/30 text-[#00C896] rounded-xl text-sm font-medium hover:bg-[#00C896]/5 transition-all">
            View Foundation Arc →
          </button>
        </div>

        <button className="w-full py-4 border border-[#162952] text-[#94A3B8] rounded-full text-sm font-medium hover:bg-[#0F2040] transition-all">
          Share my journey ↗
        </button>
      </div>

      {/* Badge detail overlay */}
      <AnimatePresence>
        {selectedBadge && (
          <motion.div className="fixed inset-0 bg-[#0A1628]/90 backdrop-blur-md flex items-end z-50"
            initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            onClick={()=>setSelectedBadge(null)}>
            <motion.div className="w-full max-w-lg mx-auto bg-[#0F2040] rounded-t-3xl border-t border-[#162952] p-8"
              initial={{y:100}} animate={{y:0}} exit={{y:100}}
              onClick={e=>e.stopPropagation()}>
              <div className="text-5xl mb-4">{selectedBadge.icon}</div>
              <div className="text-xs font-mono text-[#475569] uppercase tracking-widest mb-1">Tier {selectedBadge.tier} Badge</div>
              <h3 className="font-display text-2xl mb-2" style={{color:selectedBadge.color}}>{selectedBadge.name}</h3>
              <p className="text-[#94A3B8] text-sm leading-relaxed mb-4">{selectedBadge.description}</p>
              <div className="bg-[#162952] rounded-xl p-3 mb-4">
                <div className="text-xs text-[#475569] font-mono mb-1">On-chain message</div>
                <div className="text-[#8B5CF6] text-sm font-mono">{selectedBadge.on_chain_message}</div>
              </div>
              <button className="w-full py-3 border border-[#162952] text-[#475569] rounded-xl text-sm" onClick={()=>setSelectedBadge(null)}>Close</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
