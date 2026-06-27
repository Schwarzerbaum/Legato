'use client'
import { useEffect, useState, useRef } from 'react'
import NGOS from '../data/ngos.json'

const SDG_META = [
  { n:1,  label:'No Poverty',             color:'#E5243B', icon:'🏚' },
  { n:2,  label:'Zero Hunger',            color:'#DDA63A', icon:'🌾' },
  { n:3,  label:'Good Health',            color:'#4C9F38', icon:'❤️' },
  { n:4,  label:'Quality Education',      color:'#C5192D', icon:'📚' },
  { n:5,  label:'Gender Equality',        color:'#FF3A21', icon:'⚖️' },
  { n:6,  label:'Clean Water',            color:'#26BDE2', icon:'💧' },
  { n:7,  label:'Clean Energy',           color:'#FCC30B', icon:'⚡' },
  { n:8,  label:'Decent Work',            color:'#A21942', icon:'💼' },
  { n:9,  label:'Innovation',             color:'#FD6925', icon:'🏗' },
  { n:10, label:'Reduced Inequalities',   color:'#DD1367', icon:'🤝' },
  { n:11, label:'Sustainable Cities',     color:'#FD9D24', icon:'🏙' },
  { n:12, label:'Responsible Production', color:'#BF8B2E', icon:'♻️' },
  { n:13, label:'Climate Action',         color:'#3F7E44', icon:'🌍' },
  { n:14, label:'Life Below Water',       color:'#0A97D9', icon:'🌊' },
  { n:15, label:'Life on Land',           color:'#56C02B', icon:'🌿' },
  { n:16, label:'Peace & Justice',        color:'#00689D', icon:'🕊' },
  { n:17, label:'Partnerships',           color:'#19486A', icon:'🔗' },
]

export default function SDGFootprint() {
  const [selectedNGOs, setSelectedNGOs] = useState<string[]>([])
  const [hovered, setHovered] = useState<number|null>(null)
  const [pulse, setPulse] = useState<number[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval>|null>(null)

  useEffect(() => {
    // Hydrate from zustand persist store
    try {
      const raw = localStorage.getItem('legatum-v2')
      if (raw) {
        const parsed = JSON.parse(raw)
        setSelectedNGOs(parsed.state?.selectedNGOs || [])
      }
    } catch {}
  }, [])

  // Build SDG → NGO coverage map
  const activeNgos = selectedNGOs.length > 0
    ? (NGOS as any[]).filter(n => selectedNGOs.includes(n.id))
    : (NGOS as any[]) // show all if none selected

  const coverage: Record<number, string[]> = {}
  activeNgos.forEach((ngo: any) => {
    (ngo.sdg_alignment || []).forEach((s: string) => {
      const num = parseInt(s.replace('SDG ', ''))
      if (!coverage[num]) coverage[num] = []
      coverage[num].push(ngo.name)
    })
  })

  const maxCount = Math.max(...Object.values(coverage).map(v => v.length), 1)

  // Random pulse effect
  useEffect(() => {
    const activeSDGs = Object.keys(coverage).map(Number)
    if (activeSDGs.length === 0) return
    timerRef.current = setInterval(() => {
      const pick = activeSDGs[Math.floor(Math.random() * activeSDGs.length)]
      setPulse(p => [...p, pick])
      setTimeout(() => setPulse(p => p.filter(x => x !== pick)), 800)
    }, 600)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [selectedNGOs])

  const totalSDGs = Object.keys(coverage).length
  const totalNGOs = activeNgos.length

  return (
    <div className="flex flex-col h-full px-4 py-4 gap-4 overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-0.5">UN SDG Coverage</div>
          <div className="text-[#F8FAFC] text-lg font-semibold">Your Global Footprint</div>
          <div className="text-[#475569] text-xs mt-0.5">
            {selectedNGOs.length > 0
              ? `${totalNGOs} selected NGOs covering ${totalSDGs} of 17 SDGs`
              : `All ${totalNGOs} NGOs · ${totalSDGs} of 17 SDGs reachable`}
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-mono text-[#00C896]">{totalSDGs}<span className="text-[#475569] text-base">/17</span></div>
          <div className="text-[9px] text-[#475569] uppercase tracking-widest">goals reached</div>
        </div>
      </div>

      {/* Hex-style SDG grid */}
      <div className="grid grid-cols-5 gap-2">
        {SDG_META.map(sdg => {
          const ngos = coverage[sdg.n] || []
          const intensity = ngos.length / maxCount
          const isActive = intensity > 0
          const isPulsing = pulse.includes(sdg.n)
          const isHov = hovered === sdg.n

          return (
            <div
              key={sdg.n}
              onMouseEnter={() => setHovered(sdg.n)}
              onMouseLeave={() => setHovered(null)}
              className="relative flex flex-col items-center justify-center rounded-2xl p-2 cursor-pointer select-none transition-all duration-300"
              style={{
                aspectRatio: '1',
                background: isActive
                  ? `${sdg.color}${Math.round(intensity * 28).toString(16).padStart(2,'0')}`
                  : '#0F2040',
                border: `1.5px solid ${isActive ? sdg.color + (isHov ? 'ee' : '55') : '#162952'}`,
                boxShadow: isPulsing || isHov
                  ? `0 0 ${isHov?24:16}px ${sdg.color}${isHov?'88':'44'}`
                  : 'none',
                transform: isPulsing ? 'scale(1.06)' : isHov ? 'scale(1.04)' : 'scale(1)',
              }}>
              <div className="text-base leading-none">{sdg.icon}</div>
              <div className="font-mono text-xs font-bold mt-0.5"
                style={{ color: isActive ? sdg.color : '#334155' }}>
                {sdg.n}
              </div>
              {isActive && (
                <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold"
                  style={{ background: sdg.color, color: '#0A1628' }}>
                  {ngos.length}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Hover detail */}
      <div className="min-h-[72px] rounded-xl border border-[#162952] bg-[#0F2040] px-4 py-3 transition-all duration-200">
        {hovered ? (
          (() => {
            const sdg = SDG_META.find(s => s.n === hovered)!
            const ngos = coverage[hovered] || []
            return (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-lg">{sdg.icon}</span>
                  <span className="font-semibold text-sm" style={{ color: sdg.color }}>
                    SDG {sdg.n} — {sdg.label}
                  </span>
                </div>
                {ngos.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {ngos.map(name => (
                      <span key={name} className="text-[10px] px-2 py-0.5 rounded-full bg-[#162952] text-[#94A3B8]">
                        {name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-[#334155]">No NGOs in your portfolio cover this goal</div>
                )}
              </div>
            )
          })()
        ) : (
          <div className="text-xs text-[#334155] flex items-center gap-2 h-full">
            <span className="text-base">👆</span>
            Hover any goal to see which NGOs in your portfolio contribute to it
          </div>
        )}
      </div>

      {/* Coverage bar */}
      <div>
        <div className="text-xs text-[#475569] mb-2 flex justify-between">
          <span>SDG Coverage</span>
          <span className="font-mono text-[#00C896]">{Math.round((totalSDGs/17)*100)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-[#162952] overflow-hidden">
          <div className="h-full rounded-full bg-gradient-to-r from-[#00C896] to-[#0EA5E9] transition-all duration-700"
            style={{ width: `${(totalSDGs/17)*100}%` }} />
        </div>
        <div className="flex gap-3 mt-3 flex-wrap">
          {Object.entries(coverage).sort((a,b) => b[1].length - a[1].length).slice(0,4).map(([sdgN, ngos]) => {
            const sdg = SDG_META.find(s => s.n === parseInt(sdgN))!
            return (
              <div key={sdgN} className="flex items-center gap-1.5 text-xs">
                <div className="w-2 h-2 rounded-full" style={{ background: sdg.color }} />
                <span className="text-[#94A3B8]">SDG {sdgN}</span>
                <span className="font-mono text-[#475569]">×{ngos.length}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
