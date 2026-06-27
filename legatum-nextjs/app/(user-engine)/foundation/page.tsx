'use client'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const GATES = [
  { id:1, label:'Giving Identity', desc:'Complete persona questionnaire', done:true },
  { id:2, label:'First NGO Match', desc:'Select a verified partner', done:true },
  { id:3, label:'Impact Contribution', desc:'Make your first contribution', done:false },
  { id:4, label:'Mission Statement', desc:'Define your foundation purpose', done:false },
  { id:5, label:'LBBW Consultation', desc:'Meet your advisor', done:false },
]

const SAMPLE_STATEMENT = `Your giving identity as an Architect is not a label — it is a constraint on where your resources go and how they work. What you are building with this foundation is not a vehicle for donations. It is a permanent institution: one that continues to allocate capital according to your values after your personal involvement ends.

The purpose of the Architekt Stiftung is to fund structural interventions in educational equity across Baden-Württemberg — specifically the design and long-term financing of peer mentorship infrastructure in secondary schools that serve first-generation university candidates. The method is not direct service. It is the architecture of service: funding the systems that allow others to deliver direct impact at scale, sustainably, without your name on every door.`

export default function FoundationPage() {
  const [readiness] = useState(24)
  const [persona, setPersona] = useState('Architect')
  const [generating, setGenerating] = useState(false)
  const [statement, setStatement] = useState('')
  const [typed, setTyped] = useState('')
  const [showAdvisor, setShowAdvisor] = useState(false)

  useEffect(() => {
    const p = localStorage.getItem('lg2_persona') || 'Architect'
    setPersona(p)
  }, [])

  function generateStatement() {
    setGenerating(true)
    setStatement('')
    setTyped('')
    setTimeout(() => {
      setGenerating(false)
      setStatement(SAMPLE_STATEMENT)
    }, 2200)
  }

  useEffect(() => {
    if (!statement) return
    let i = 0
    const words = statement.split(' ')
    const interval = setInterval(() => {
      setTyped(words.slice(0,i+1).join(' '))
      i++
      if (i >= words.length) clearInterval(interval)
    }, 55)
    return () => clearInterval(interval)
  }, [statement])

  return (
    <div className="min-h-screen bg-[#0A1628] pt-12 pb-24">
      <div className="max-w-lg mx-auto px-4">
        <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-1">Layer 7 · Foundation Arc</div>
        <h1 className="font-display text-2xl text-[#F8FAFC] mb-1">Your Foundation</h1>
        <p className="text-[#475569] text-sm mb-6">Five gates to becoming a Stifter with LBBW</p>

        {/* Readiness arc */}
        <div className="rounded-2xl border border-[#162952] bg-[#0F2040] p-5 mb-6">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs text-[#475569] font-mono uppercase tracking-widest">Foundation Readiness</span>
            <span className="font-mono text-[#00C896]">{readiness}%</span>
          </div>
          <div className="h-2 bg-[#162952] rounded-full overflow-hidden mb-4">
            <motion.div className="h-full rounded-full bg-gradient-to-r from-[#00C896] to-[#7C3AED]"
              initial={{width:0}} animate={{width:`${readiness}%`}} transition={{duration:1,delay:0.3}} />
          </div>

          {/* Gates */}
          <div className="space-y-2">
            {GATES.map((g,i) => (
              <motion.div key={g.id} className="flex items-center gap-3"
                initial={{opacity:0,x:-8}} animate={{opacity:1,x:0}} transition={{delay:i*0.1}}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                  g.done ? 'bg-[#00C896] text-[#0A1628]' : 'bg-[#162952] text-[#475569] border border-[#162952]'
                }`}>{g.done?'✓':g.id}</div>
                <div className="flex-1">
                  <div className={`text-sm ${g.done?'text-[#F8FAFC]':'text-[#475569]'}`}>{g.label}</div>
                  <div className="text-xs text-[#475569]">{g.desc}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Mission statement generator */}
        <div className="rounded-2xl border border-[#7C3AED]/20 bg-[#0F2040] p-5 mb-6">
          <div className="text-xs text-[#7C3AED] font-mono uppercase tracking-widest mb-3">Foundation Mission</div>

          {!statement && !generating && (
            <div className="text-center py-6">
              <div className="text-[#475569] text-sm mb-4">Generate a foundation statement from your giving identity</div>
              <button onClick={generateStatement}
                className="px-6 py-3 bg-[#7C3AED]/20 border border-[#7C3AED]/30 text-[#7C3AED] rounded-xl text-sm font-medium hover:bg-[#7C3AED]/30 transition-all">
                Generate mission statement
              </button>
            </div>
          )}

          {generating && (
            <div className="py-8 flex flex-col items-center gap-4">
              <div className="flex gap-2">
                {[0,1,2].map(i=>(
                  <motion.div key={i} className="w-2 h-2 rounded-full bg-[#7C3AED]"
                    animate={{y:[0,-8,0]}} transition={{duration:0.8,delay:i*0.15,repeat:Infinity}} />
                ))}
              </div>
              <div className="text-[#475569] text-xs font-mono">Crafting your foundation's story...</div>
            </div>
          )}

          {typed && (
            <div>
              <p className="text-[#F8FAFC] text-sm leading-loose whitespace-pre-line mb-2">{typed}</p>
              {typed === statement && (
                <motion.div initial={{opacity:0}} animate={{opacity:1}} transition={{delay:0.5}}>
                  <p className="text-[#475569] text-xs italic mb-4">Generated from your choices. Not a template.</p>
                  <div className="flex gap-2">
                    <button className="flex-1 py-3 border border-[#162952] text-[#94A3B8] rounded-xl text-xs font-medium hover:bg-[#162952]/50">Save to passport</button>
                    <button onClick={()=>setShowAdvisor(true)}
                      className="flex-1 py-3 bg-[#00C896] text-[#0A1628] rounded-xl text-xs font-semibold">
                      Begin with LBBW →
                    </button>
                  </div>
                </motion.div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Advisor panel */}
      <AnimatePresence>
        {showAdvisor && (
          <motion.div className="fixed inset-0 bg-[#0A1628]/90 backdrop-blur-md flex items-end z-50"
            initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            onClick={()=>setShowAdvisor(false)}>
            <motion.div className="w-full max-w-lg mx-auto bg-[#0F2040] rounded-t-3xl border-t-2 border-[#00C896] p-6"
              initial={{y:'100%'}} animate={{y:0}} exit={{y:'100%'}} transition={{type:'spring',damping:28}}
              onClick={e=>e.stopPropagation()}>
              <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-3">LBBW Foundation Advisor</div>
              <div className="flex items-center gap-3 mb-4 p-3 bg-[#162952] rounded-xl">
                <div className="w-10 h-10 rounded-full bg-[#00C896]/20 flex items-center justify-center text-[#00C896] font-bold">MS</div>
                <div>
                  <div className="text-sm font-medium text-[#F8FAFC]">Mirjam Schwink</div>
                  <div className="text-xs text-[#475569]">Head of Foundation Management · LBBW</div>
                </div>
              </div>
              <div className="bg-[#162952] rounded-xl p-4 mb-4">
                <div className="text-xs text-[#00C896] font-mono mb-2">Recommended path</div>
                <div className="text-sm font-medium text-[#F8FAFC] mb-1">Treuhandstiftung Classic</div>
                <div className="grid grid-cols-3 gap-2 text-xs text-[#475569] mt-2">
                  <div>Min. capital<br/><span className="text-[#F8FAFC] font-mono">€50,000</span></div>
                  <div>Annual fees<br/><span className="text-[#F8FAFC] font-mono">~€3,000</span></div>
                  <div>First grant<br/><span className="text-[#F8FAFC] font-mono">18 months</span></div>
                </div>
              </div>
              <button className="w-full py-4 bg-[#00C896] text-[#0A1628] rounded-xl font-bold mb-2">Book consultation</button>
              <button className="w-full py-3 border border-[#162952] text-[#475569] rounded-xl text-sm" onClick={()=>setShowAdvisor(false)}>Close</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
