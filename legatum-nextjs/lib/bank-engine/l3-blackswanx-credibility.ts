export interface CredibilityInput {
  donorId: string
  ngoId: string
  commitmentEuro: number
  sdgAlignment: number  // 0–1
  historicalCompliance: number  // 0–1
}

export interface CredibilityScore {
  score: number          // 0–100
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  blackSwanRisk: 'low' | 'medium' | 'high'
  breakdown: Record<string, number>
}

export function calcCredibilityScore(input: CredibilityInput): CredibilityScore {
  const raw =
    input.sdgAlignment * 40 +
    input.historicalCompliance * 40 +
    Math.min(input.commitmentEuro / 100_000, 1) * 20

  const score = Math.round(raw)
  const grade =
    score >= 85 ? 'A' : score >= 70 ? 'B' : score >= 55 ? 'C' : score >= 40 ? 'D' : 'F'
  const blackSwanRisk =
    score >= 70 ? 'low' : score >= 45 ? 'medium' : 'high'

  return {
    score,
    grade,
    blackSwanRisk,
    breakdown: {
      sdgAlignment: input.sdgAlignment * 40,
      compliance: input.historicalCompliance * 40,
      commitment: Math.min(input.commitmentEuro / 100_000, 1) * 20,
    },
  }
}
