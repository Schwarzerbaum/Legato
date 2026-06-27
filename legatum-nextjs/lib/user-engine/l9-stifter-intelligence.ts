export interface GivingStrategy {
  title: string
  rationale: string
  suggestedNGOs: string[]
  sdgFocus: number[]
  annualCommitment: number
}

export interface StifterIntelligenceInput {
  archetype: string
  totalWealth: number
  sdgAffinity: number[]
  riskTolerance: 'low' | 'medium' | 'high'
}

export function generateGivingStrategy(
  input: StifterIntelligenceInput
): GivingStrategy {
  const topSDGs = [...input.sdgAffinity]
    .map((w, i) => ({ sdg: i + 1, w }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3)
    .map(x => x.sdg)

  return {
    title: `${input.archetype} Impact Strategy`,
    rationale: `Optimised for ${input.archetype} profile with ${input.riskTolerance} risk tolerance`,
    suggestedNGOs: [],
    sdgFocus: topSDGs,
    annualCommitment: Math.round(input.totalWealth * 0.05),
  }
}
