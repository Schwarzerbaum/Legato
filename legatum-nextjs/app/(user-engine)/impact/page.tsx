'use client'
import { useState } from 'react'
import dynamic from 'next/dynamic'
import SDGFootprint from '../../../components/SDGFootprint'

const Simulation = dynamic(() => import('../../../components/Simulation'), { ssr: false })

const TABS = [
  { id: 'sim',  label: 'Particle Flow' },
  { id: 'sdg',  label: 'SDG Footprint' },
] as const

export default function ImpactPage() {
  const [tab, setTab] = useState<'sim'|'sdg'>('sim')

  return (
    <div className="min-h-screen bg-[#0A1628] flex flex-col">
      <div className="px-4 pt-12 pb-0">
        <div className="text-xs text-[#00C896] font-mono uppercase tracking-widest mb-1">Layer 5 · Impact Universe</div>
        <h1 className="font-display text-2xl text-[#F8FAFC] mb-4">Living Impact Flow</h1>
        <div className="flex gap-1 p-1 bg-[#0F2040] rounded-xl border border-[#162952] w-fit">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-5 py-2 rounded-lg text-xs font-medium transition-all ${
                tab === t.id
                  ? 'bg-[#00C896]/20 text-[#00C896] border border-[#00C896]/30'
                  : 'text-[#475569] hover:text-[#94A3B8]'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        {tab === 'sim' ? (
          <Simulation />
        ) : (
          <SDGFootprint />
        )}
      </div>
    </div>
  )
}
