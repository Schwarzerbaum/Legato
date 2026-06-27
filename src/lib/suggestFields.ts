// Legato — for a giver who isn't sure where to start: turn a free-text
// description of what they care about into matching onboarding cause-cards.
// Returns theme keys (verbatim from the provided list). Falls back to [] when
// the AI proxy is unavailable (e.g. no API key locally).
export async function suggestThemes(
  description: string,
  themes: { key: string; label: string }[],
): Promise<string[]> {
  const prompt = `You are an advisor at LBBW helping someone who isn't sure which causes to support discover what matters to them.
They describe what they care about: "${description}".

Available cause themes (key — label):
${themes.map(t => `${t.key} — ${t.label}`).join('\n')}

Return a JSON array of 2 to 4 theme keys (verbatim from the keys above, e.g. "health") that best match this person, ordered by relevance. Respond with ONLY the JSON array, no other text.`

  try {
    const res = await fetch('/api/ai/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 100,
        messages: [{ role: 'user', content: prompt }],
      }),
    })
    if (!res.ok) return []
    const data = await res.json()
    const text: string = data.content?.[0]?.text ?? ''
    const match = text.match(/\[[\s\S]*?\]/)
    if (!match) return []
    const keys: unknown[] = JSON.parse(match[0])
    const valid = new Set(themes.map(t => t.key))
    return keys
      .filter((k): k is string => typeof k === 'string' && valid.has(k))
      .slice(0, 4)
  } catch {
    return []
  }
}

// Legato — suggest the most relevant cause areas for a new giver based on
// their motivation and giving style. Runs through the same-origin AI proxy.
export async function suggestCauseAreas(
  motivation: string,
  givingStyle: string,
  causeNames: string[],
  causeIds: string[],
): Promise<string[]> {
  const prompt = `You are an advisor at LBBW helping someone discover their philanthropic identity.
The person says what moves them most is: "${motivation}".
Their preferred way of giving is: "${givingStyle}".

Available cause areas:
${causeNames.map((n, i) => `${i + 1}. ${n}`).join('\n')}

Return a JSON array of exactly 3 cause area names (verbatim from the list above) that best match this person, ordered by relevance. Respond with ONLY the JSON array, no other text.`

  try {
    const res = await fetch('/api/ai/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 100,
        messages: [{ role: 'user', content: prompt }],
      }),
    })

    if (!res.ok) return []

    const data = await res.json()
    const text: string = data.content?.[0]?.text ?? ''

    const match = text.match(/\[[\s\S]*?\]/)
    if (!match) return []

    const names: unknown[] = JSON.parse(match[0])

    return names
      .filter((n): n is string => typeof n === 'string')
      .map(name => {
        const idx = causeNames.findIndex(fn => fn.toLowerCase() === name.toLowerCase())
        return idx >= 0 ? causeIds[idx] : null
      })
      .filter((id): id is string => id !== null)
      .slice(0, 3)
  } catch {
    return []
  }
}
