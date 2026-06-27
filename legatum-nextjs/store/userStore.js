'use client'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const PERSONA_COLORS = {
  Catalyst: '#F59E0B',
  Guardian: '#059669',
  Explorer: '#0EA5E9',
  Architect: '#7C3AED',
}

export const useStore = create(
  persist(
    (set, get) => ({
      currentQuestion: 0,
      answers: [],

      persona: null,
      mbtiType: null,
      personaColor: null,
      personaSymbol: null,
      swym: null,
      personaTagline: null,
      personaDescription: null,

      matchedNGOs: [],
      selectedNGOs: [],
      activeAnomaly: null,

      contributions: [],
      totalContributed: 0,
      livesTouched: 0,
      monthlyAmount: 100,

      treeStage: 0,
      treeStageName: 'Seed',
      nextMilestone: 50,

      earnedBadges: [],

      walletConnected: false,
      walletAddress: null,
      passportMinted: false,
      lastTxHash: null,

      foundationReadiness: 0,
      foundationStatement: null,

      submitAnswer: (answer) => {
        const { answers, currentQuestion } = get()
        const newAnswers = [...answers, { q: currentQuestion + 1, a: answer }]
        set({ answers: newAnswers, currentQuestion: currentQuestion + 1 })
      },

      setPersona: (data) => {
        set({
          persona: data.persona,
          mbtiType: data.mbti_type,
          personaColor: PERSONA_COLORS[data.persona] || '#00C896',
          personaSymbol: data.persona_symbol,
          swym: data.swym,
          personaTagline: data.persona_tagline,
          personaDescription: data.persona_description,
        })
      },

      setMatchedNGOs: (ngos) => set({ matchedNGOs: ngos }),

      addSelectedNGO: (ngoId) => {
        const { selectedNGOs } = get()
        if (!selectedNGOs.includes(ngoId)) {
          set({ selectedNGOs: [...selectedNGOs, ngoId] })
        }
      },

      addContribution: (amount, ngoId) => {
        const { contributions, totalContributed, livesTouched } = get()
        const newTotal = totalContributed + amount
        const newLives = Math.floor(newTotal * 0.047)
        const stage = calcTreeStage(newTotal)
        set({
          contributions: [...contributions, { amount, ngoId, date: new Date().toISOString() }],
          totalContributed: newTotal,
          livesTouched: newLives,
          treeStage: stage.stage,
          treeStageName: stage.name,
          nextMilestone: stage.next,
          foundationReadiness: Math.min(100, Math.floor((newTotal / 100000) * 100)),
        })
      },

      setMonthlyAmount: (amount) => set({ monthlyAmount: amount }),

      earnBadge: (badgeId) => {
        const { earnedBadges } = get()
        if (!earnedBadges.includes(badgeId)) {
          set({ earnedBadges: [...earnedBadges, badgeId] })
        }
      },

      setFoundationStatement: (statement) => set({ foundationStatement: statement }),

      connectWallet: (address) => set({ walletConnected: true, walletAddress: address }),

      setLastTxHash: (hash) => set({ lastTxHash: hash }),

      resetJourney: () => set({
        currentQuestion: 0, answers: [], persona: null, mbtiType: null,
        personaColor: null, personaSymbol: null, swym: null,
      }),
    }),
    { name: 'legatum-v2', skipHydration: true }
  )
)

function calcTreeStage(total) {
  if (total >= 500000) return { stage: 6, name: 'Forest', next: Infinity }
  if (total >= 100000) return { stage: 5, name: 'Ancient Tree', next: 500000 }
  if (total >= 50000)  return { stage: 4, name: 'Full Tree', next: 100000 }
  if (total >= 5000)   return { stage: 3, name: 'Young Tree', next: 50000 }
  if (total >= 500)    return { stage: 2, name: 'Sapling', next: 5000 }
  if (total >= 50)     return { stage: 1, name: 'Sprout', next: 500 }
  return { stage: 0, name: 'Seed', next: 50 }
}
