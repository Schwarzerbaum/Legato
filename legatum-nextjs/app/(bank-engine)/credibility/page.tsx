'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { calcCredibilityScore } from '../../../lib/bank-engine/l3-blackswanx-credibility'

const GRADE_COLOR: Record<string, string> = {
  A: '#4ade80',
  B: '#86efac',
  C: '#fbbf24',
  D: '#f97316',
  F: '#ef4444',
}

export default function CredibilityPage() {
  const [score] = useState(() =>
    calcCredibilityScore({
      donorId: 'demo-donor',
      ngoId: 'demo-ngo',
      commitmentEuro: 75_000,
      sdgAlignment: 0.82,
      historicalCompliance: 0.91,
    })
  )

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-xl mx-auto space-y-8"
      >
        <div>
          <p className="text-xs tracking-widest text-[#c8a96e] uppercase mb-2">L3 · BlackSwanX Credibility AI</p>
          <h1 className="text-3xl font-light">Credibility Score</h1>
          <p className="mt-2 text-white/40 text-sm">Risk-adjusted philanthropic credibility analysis</p>
        </div>

        <div className="bg-white/5 rounded-2xl p-8 flex items-center gap-8">
          <div
            className="w-24 h-24 rounded-full flex items-center justify-center text-4xl font-bold shrink-0"
            style={{ background: `${GRADE_COLOR[score.grade]}22`, color: GRADE_COLOR[score.grade] }}
          >
            {score.grade}
          </div>
          <div>
            <p className="text-5xl font-light">{score.score}</p>
            <p className="text-white/50 text-sm mt-1">BlackSwan Risk: <span className="capitalize">{score.blackSwanRisk}</span></p>
          </div>
        </div>

        <div className="bg-white/5 rounded-2xl p-6 space-y-3">
          <p className="text-xs text-white/40 uppercase tracking-wider mb-4">Score Breakdown</p>
          {Object.entries(score.breakdown).map(([key, val]) => (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-white/60 capitalize">{key.replace(/([A-Z])/g, ' $1')}</span>
              <span>{Math.round(val as number)} pts</span>
            </div>
          ))}
        </div>
      </motion.div>
    </main>
  )
}
