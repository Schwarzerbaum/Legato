export type PersonaArchetype =
  | 'Visionär'
  | 'Bewahrer'
  | 'Gestalter'
  | 'Brückenbauer'
  | 'Pionier'

export interface PersonaResult {
  archetype: PersonaArchetype
  scores: Record<string, number>
  sdgAffinity: number[]
}

export function calcPersonaFromScores(scores: Record<string, number>): PersonaArchetype {
  const top = Object.entries(scores).sort((a, b) => b[1] - a[1])[0]
  return (top?.[0] as PersonaArchetype) ?? 'Gestalter'
}
