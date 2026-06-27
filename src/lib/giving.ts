import { topicById } from '@/data/index'
import type { Topic } from '@/data/index'

// A committed project's resolved share of the giving plan + the impact it buys.
export interface Allocation {
  topic: Topic
  weight: number   // raw slider weight (0–100)
  share: number    // normalised 0–1
  pct: number      // rounded share %
  amount: number   // € allocated
  impact: { units: number; cost: number; phrase: string } | null
}

// impactUnit looks like "€200 equips one classroom …" → unit cost + phrase.
export function parseImpactUnit(unit: string): { cost: number; phrase: string } | null {
  const m = unit.match(/^€\s*([\d.,]+)\s+(.*)$/)
  if (!m) return null
  const cost = parseInt(m[1].replace(/[.,]/g, ''), 10)
  if (!cost) return null
  return { cost, phrase: m[2] }
}

// Resolve the giving plan: weights → shares → € → impact units. Weights default
// to 50 (an even split) so a fresh portfolio is balanced without any input.
export function computeAllocations(
  committedTopicIds: string[],
  allocations: Record<string, number>,
  total: number,
): Allocation[] {
  const topics = committedTopicIds.map(id => topicById[id]).filter(Boolean) as Topic[]
  const weightOf = (id: string) => allocations[id] ?? 50
  const sum = topics.reduce((s, t) => s + weightOf(t.id), 0) || 1

  return topics.map(topic => {
    const weight = weightOf(topic.id)
    const share = weight / sum
    const amount = Math.round(total * share)
    const parsed = parseImpactUnit(topic.impactUnit)
    const impact = parsed ? { ...parsed, units: Math.floor(amount / parsed.cost) } : null
    return { topic, weight, share, pct: Math.round(share * 100), amount, impact }
  })
}
