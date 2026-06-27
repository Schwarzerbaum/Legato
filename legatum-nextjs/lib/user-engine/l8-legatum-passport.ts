export interface PassportBadge {
  id: string
  title: string
  description: string
  icon: string
  earnedAt?: string
}

export interface LegatumPassport {
  userId: string
  badges: PassportBadge[]
  credibilityScore: number
  tier: 'Bronze' | 'Silver' | 'Gold' | 'Platinum'
}

export function calcPassportTier(score: number): LegatumPassport['tier'] {
  if (score >= 90) return 'Platinum'
  if (score >= 70) return 'Gold'
  if (score >= 40) return 'Silver'
  return 'Bronze'
}
