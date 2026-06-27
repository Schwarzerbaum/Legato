export interface NGORecord {
  id: string
  name: string
  country: string
  sdgs: number[]
  impactScore: number
  verificationStatus: 'pending' | 'verified' | 'flagged'
}

export interface NGOIntelligenceResult {
  ngo: NGORecord
  credibilityRank: number
  riskFlags: string[]
}

export function scoreNGO(ngo: NGORecord): NGOIntelligenceResult {
  const riskFlags: string[] = []
  if (ngo.verificationStatus === 'flagged') riskFlags.push('Verification flag')
  if (ngo.impactScore < 0.4) riskFlags.push('Low impact score')
  return {
    ngo,
    credibilityRank: ngo.impactScore,
    riskFlags,
  }
}
