'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { useRouter } from 'next/navigation'
import { generateGivingStrategy } from '../../../lib/user-engine/l9-stifter-intelligence'
import type { StifterIntelligenceInput } from '../../../lib/user-engine/l9-stifter-intelligence'

const DEFAULT_INPUT: StifterIntelligenceInput = {
  archetype: 'Visionär',
  totalWealth: 1_000_000,
  sdgAffinity: [0.1, 0.3, 0.05, 0.2, 0.05, 0.1, 0.05, 0.05, 0.05, 0, 0, 0, 0, 0, 0, 0, 0],
  riskTolerance: 'medium',
}

export default function StifterIntelligencePage() {
  const router = useRouter()
  const [strategy] = useState(() => generateGivingStrategy(DEFAULT_INPUT))

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-xl mx-auto space-y-8"
      >
        <div>
          <p className="text-xs tracking-widest text-[#c8a96e] uppercase mb-2">L9 · Stifter Intelligence</p>
          <h1 className="text-3xl font-light">{strategy.title}</h1>
          <p className="mt-3 text-white/60 text-sm">{strategy.rationale}</p>
        </div>

        <div className="bg-white/5 rounded-2xl p-6 space-y-4">
          <div>
            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">SDG Focus</p>
            <div className="flex gap-2 flex-wrap">
              {strategy.sdgFocus.map(sdg => (
                <span key={sdg} className="bg-[#c8a96e]/20 text-[#c8a96e] text-sm px-3 py-1 rounded-full">
                  SDG {sdg}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Annual Commitment</p>
            <p className="text-2xl font-light">
              €{strategy.annualCommitment.toLocaleString('de-DE')}
            </p>
          </div>
        </div>

        <button
          onClick={() => router.push('/passport')}
          className="w-full py-4 bg-[#c8a96e] text-black font-medium rounded-2xl"
        >
          View LegatumPassport →
        </button>
      </motion.div>
    </main>
  )
}
