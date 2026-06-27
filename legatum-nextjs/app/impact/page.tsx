'use client'
import { useState, lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import dynamic from 'next/dynamic'

const Simulation = dynamic(() => import('../../components/Simulation'), { ssr: false })

export default function ImpactPage() {
  const [tab, setTab] = useState<'sim'|'graph'>('sim')

  return (
    <div className="min-h-screen bg-[#0A1628] flex flex-col">
      {/* Header */}
      <div className="px-4 pt-12 pb-0">
        <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-1">Layer 5 · Impact Universe</div>
        <h1 className="font-display text-2xl text-[#F8FAFC] mb-4">Living Impact Flow</h1>
        <div className="flex gap-1 p-1 bg-[#0F2040] rounded-xl border border-[#162952] w-fit">
          {(['sim','graph'] as const).map(t=>(
            <button key={t} onClick={()=>setTab(t)}
              className={`px-5 py-2 rounded-lg text-xs font-medium transition-all ${
                tab===t?'bg-[#00C896]/20 text-[#00C896] border border-[#00C896]/30':'text-[#475569] hover:text-[#94A3B8]'
              }`}>
              {t==='sim'?'Particle Flow':'Impact Graph'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col">
        {tab==='sim' ? (
          <Simulation />
        ) : (
          <div className="flex-1 flex items-center justify-center text-[#475569] text-sm">
            Impact graph coming soon
          </div>
        )}
      </div>
    </div>
  )
}
