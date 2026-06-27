export interface AdvisorProfile {
  advisorId: string
  name: string
  specialisation: string[]
  matchScore: number
}

export interface AdvisorRecommendation {
  advisor: AdvisorProfile
  rationale: string
  nextStep: string
}

export function matchAdvisor(
  archetype: string,
  advisors: AdvisorProfile[]
): AdvisorRecommendation | null {
  const match = advisors.find(a => a.matchScore > 0.7) ?? advisors[0] ?? null
  if (!match) return null
  return {
    advisor: match,
    rationale: `Best fit for ${archetype} profile`,
    nextStep: 'Schedule intro call',
  }
}
