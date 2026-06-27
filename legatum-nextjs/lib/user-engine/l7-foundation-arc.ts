export type GateStatus = 'locked' | 'active' | 'completed'

export interface FoundationGate {
  id: string
  title: string
  description: string
  status: GateStatus
}

export function evaluateGates(
  gates: FoundationGate[],
  completedIds: string[]
): FoundationGate[] {
  let prevCompleted = true
  return gates.map(gate => {
    if (completedIds.includes(gate.id)) {
      prevCompleted = true
      return { ...gate, status: 'completed' }
    }
    if (prevCompleted) {
      prevCompleted = false
      return { ...gate, status: 'active' }
    }
    return { ...gate, status: 'locked' }
  })
}
