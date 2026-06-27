export interface SDGAllocation {
  sdg: number
  label: string
  percentage: number
  euroAmount: number
}

export interface ImpactSnapshot {
  totalCommitted: number
  allocations: SDGAllocation[]
  lastUpdated: string
}

export function buildImpactSnapshot(
  totalCommitted: number,
  weights: number[]
): ImpactSnapshot {
  const sum = weights.reduce((a, b) => a + b, 0) || 1
  const allocations: SDGAllocation[] = weights.map((w, i) => ({
    sdg: i + 1,
    label: `SDG ${i + 1}`,
    percentage: (w / sum) * 100,
    euroAmount: (w / sum) * totalCommitted,
  }))
  return { totalCommitted, allocations, lastUpdated: new Date().toISOString() }
}
