'use client'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRouter } from 'next/navigation'
import NGOS from '../../../data/ngos.json'

export default function DiscoverPage() {
  const router = useRouter()
  const [persona, setPersona] = useState('Architect')
  const [selected, setSelected] = useState<any>(null)
  const [added, setAdded] = useState<string[]>([])

  useEffect(() => {
    const p = localStorage.getItem('lg2_persona') || 'Architect'
    setPersona(p)
  }, [])

  const matches = NGOS.filter((n:any) => n.personas.includes(persona) && !n.anomaly_flag).slice(0,3)
  const flagged = NGOS.filter((n:any) => n.anomaly_flag).slice(0,1)
  const shown = [...matches, ...flagged]

  const scoreColor = (s:number) => s>=85?'#00C896':s>=65?'#F59E0B':'#EF4444'

  return (
    <div className="min-h-screen bg-[#0A1628] pt-12 pb-24">
      <div className="max-w-lg mx-auto px-4">
        <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-1">Layer 3 · NGO Match</div>
        <h1 className="font-display text-2xl text-[#F8FAFC] mb-1">Your NGO Matches</h1>
        <p className="text-[#475569] text-sm mb-6">Matched by BlackSwanX to your {persona} profile</p>

        <div className="space-y-3">
          {shown.map((ngo:any, i) => (
            <motion.div key={ngo.id}
              initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} transition={{delay:i*0.1}}
              className={`rounded-2xl border p-4 cursor-pointer transition-all ${
                ngo.anomaly_flag
                  ? 'border-[#EF4444]/30 bg-[#EF4444]/5'
                  : selected?.id===ngo.id
                  ? 'border-[#00C896]/40 bg-[#0F2040]'
                  : 'border-[#162952] bg-[#0F2040] hover:border-[#00C896]/20'
              }`}
              onClick={()=>setSelected(selected?.id===ngo.id?null:ngo)}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-[#F8FAFC] text-sm">{ngo.name}</span>
                    {ngo.phineo_certified && <span className="text-xs bg-[#00C896]/10 text-[#00C896] border border-[#00C896]/20 px-2 py-0.5 rounded-full">PHINEO ✓</span>}
                    {ngo.anomaly_flag && <span className="text-xs bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20 px-2 py-0.5 rounded-full">⚠ Under Review</span>}
                  </div>
                  <div className="text-[#475569] text-xs">{ngo.cause} · {ngo.location.split(',')[0]}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="font-mono text-lg font-bold" style={{color:scoreColor(ngo.credibility_score)}}>{ngo.credibility_score}</div>
                  <div className="text-[10px] text-[#475569]">score</div>
                </div>
              </div>

              <AnimatePresence>
                {selected?.id===ngo.id && (
                  <motion.div initial={{height:0,opacity:0}} animate={{height:'auto',opacity:1}} exit={{height:0,opacity:0}}
                    className="overflow-hidden">
                    <div className="mt-4 pt-4 border-t border-[#162952]">
                      <p className="text-[#94A3B8] text-sm leading-relaxed mb-3">{ngo.description}</p>

                      {/* Score bars */}
                      <div className="space-y-2 mb-4">
                        {[['Financial Transparency',ngo.financial_transparency,10],['Impact Consistency',ngo.impact_consistency,10],['Source Diversity',ngo.source_diversity,10]].map(([l,v,max])=>(
                          <div key={l as string}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-[#475569]">{l}</span>
                              <span className="font-mono" style={{color:scoreColor((v as number)/(max as number)*100)}}>{(v as number).toFixed(1)}/{max}</span>
                            </div>
                            <div className="h-1 bg-[#162952] rounded-full overflow-hidden">
                              <motion.div className="h-full rounded-full" style={{background:scoreColor((v as number)/(max as number)*100)}}
                                initial={{width:0}} animate={{width:`${(v as number)/(max as number)*100}%`}} transition={{duration:0.6}} />
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Anomaly panel */}
                      {ngo.anomaly_flag && ngo.anomaly_data && (
                        <div className="bg-[#EF4444]/8 border border-[#EF4444]/20 rounded-xl p-4 mb-4">
                          <div className="text-[#EF4444] text-xs font-bold uppercase tracking-widest mb-2">⚠ BlackSwanX Anomaly</div>
                          <div className="text-[#94A3B8] text-xs leading-relaxed mb-2">
                            Claimed {ngo.anomaly_data.claimed_metric}: <span className="text-[#EF4444] font-mono">{ngo.anomaly_data.claimed_value.toLocaleString()}</span>{' '}
                            vs verified: <span className="text-[#00C896] font-mono">{ngo.anomaly_data.verified_value.toLocaleString()}</span>
                          </div>
                          <div className="text-[#475569] text-xs">Confidence: {Math.round(ngo.anomaly_data.confidence*100)}% · {ngo.anomaly_data.sources.length} independent sources</div>
                        </div>
                      )}

                      <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
                        <div className="bg-[#162952] rounded-lg p-3">
                          <div className="text-[#475569] mb-0.5">Impact ratio</div>
                          <div className="font-mono text-[#00C896]">€1 = {ngo.impact_ratio} beneficiaries</div>
                        </div>
                        <div className="bg-[#162952] rounded-lg p-3">
                          <div className="text-[#475569] mb-0.5">Funding gap</div>
                          <div className="font-mono text-[#F59E0B]">€{ngo.funding_gap.toLocaleString()}</div>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        {!added.includes(ngo.id) ? (
                          <button className="flex-1 py-3 bg-[#00C896] text-[#0A1628] rounded-xl font-semibold text-sm"
                            onClick={e=>{e.stopPropagation();setAdded(a=>[...a,ngo.id])}}>
                            Add to my giving
                          </button>
                        ) : (
                          <div className="flex-1 py-3 bg-[#00C896]/10 border border-[#00C896]/30 text-[#00C896] rounded-xl text-sm text-center font-medium">
                            ✓ Added
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>

        {added.length > 0 && (
          <motion.button className="w-full mt-6 py-4 bg-[#00C896] text-[#0A1628] rounded-full font-bold text-base"
            initial={{opacity:0,y:12}} animate={{opacity:1,y:0}}
            onClick={()=>router.push('/impact')}>
            See my impact flow →
          </motion.button>
        )}
      </div>
    </div>
  )
}
