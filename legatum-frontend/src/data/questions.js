// 12 persona questions. Each answer scores: systemic, depth, identity, engagement (all 0–2).
// Final persona = highest composite score across 4 archetypes.

export const QUESTIONS = [
  {
    id: 1,
    text: 'When you give, what matters most to you?',
    a: { text: 'Seeing a direct, measurable difference in someone\'s life', scores: { systemic: 0, depth: 1, identity: 0, engagement: 1 } },
    b: { text: 'Changing the systems and structures that cause the problem', scores: { systemic: 2, depth: 1, identity: 1, engagement: 0 } },
  },
  {
    id: 2,
    text: 'How do you prefer to support a cause?',
    a: { text: 'Deep, long-term commitment to one cause', scores: { systemic: 1, depth: 2, identity: 1, engagement: 1 } },
    b: { text: 'Supporting many causes to diversify my impact', scores: { systemic: 0, depth: 0, identity: 0, engagement: 2 } },
  },
  {
    id: 3,
    text: 'Which statement resonates more with you?',
    a: { text: 'Giving is core to who I am — it defines my values', scores: { systemic: 0, depth: 1, identity: 2, engagement: 1 } },
    b: { text: 'Giving is a responsibility — I want results, not recognition', scores: { systemic: 1, depth: 1, identity: 0, engagement: 0 } },
  },
  {
    id: 4,
    text: 'Your ideal relationship with an NGO you support:',
    a: { text: 'Closely involved — visit projects, know the team personally', scores: { systemic: 0, depth: 2, identity: 1, engagement: 2 } },
    b: { text: 'Trust the experts — donate and let them lead', scores: { systemic: 1, depth: 0, identity: 0, engagement: 0 } },
  },
  {
    id: 5,
    text: 'If you had €10,000 to give today:',
    a: { text: 'Fund one critical project fully and track every euro', scores: { systemic: 0, depth: 2, identity: 0, engagement: 2 } },
    b: { text: 'Spread it across 6–8 promising initiatives', scores: { systemic: 1, depth: 0, identity: 0, engagement: 1 } },
  },
  {
    id: 6,
    text: 'What frustrates you most about traditional philanthropy?',
    a: { text: 'Money doesn\'t reach those who need it — too much overhead', scores: { systemic: 0, depth: 1, identity: 0, engagement: 2 } },
    b: { text: 'Band-aid solutions that never fix root causes', scores: { systemic: 2, depth: 1, identity: 1, engagement: 0 } },
  },
  {
    id: 7,
    text: 'The impact you care about most looks like:',
    a: { text: 'Measurable and immediate — X people helped this year', scores: { systemic: 0, depth: 1, identity: 0, engagement: 1 } },
    b: { text: 'Structural — society functions better 20 years from now', scores: { systemic: 2, depth: 1, identity: 1, engagement: 0 } },
  },
  {
    id: 8,
    text: 'How do you feel about public recognition for your giving?',
    a: { text: 'I want my giving identity to be visible — it inspires others', scores: { systemic: 1, depth: 0, identity: 2, engagement: 1 } },
    b: { text: 'Irrelevant — anonymity is fine if the impact is real', scores: { systemic: 1, depth: 1, identity: 0, engagement: 0 } },
  },
  {
    id: 9,
    text: 'In 10 years, what would make you feel your giving truly mattered?',
    a: { text: 'Real people whose lives changed because of my support', scores: { systemic: 0, depth: 2, identity: 0, engagement: 2 } },
    b: { text: 'A system, institution, or policy that outlasts me', scores: { systemic: 2, depth: 1, identity: 2, engagement: 0 } },
  },
  {
    id: 10,
    text: 'How do you feel about creating a foundation?',
    a: { text: 'Very interested — a foundation gives my giving permanence', scores: { systemic: 2, depth: 2, identity: 2, engagement: 1 } },
    b: { text: 'Uncertain — I\'d rather stay flexible and responsive', scores: { systemic: 0, depth: 0, identity: 0, engagement: 1 } },
  },
  {
    id: 11,
    text: 'When evaluating an NGO, you primarily look at:',
    a: { text: 'Their theory of change and policy influence', scores: { systemic: 2, depth: 1, identity: 0, engagement: 0 } },
    b: { text: 'On-the-ground impact reports and beneficiary stories', scores: { systemic: 0, depth: 1, identity: 0, engagement: 2 } },
  },
  {
    id: 12,
    text: 'The phrase that best describes your giving philosophy:',
    a: { text: '"Go deep, not wide — be the best funder of one great cause"', scores: { systemic: 1, depth: 2, identity: 1, engagement: 1 } },
    b: { text: '"Diversify — no single cause deserves all my resources"', scores: { systemic: 0, depth: 0, identity: 0, engagement: 2 } },
  },
]

// Persona calculation from score object { systemic, depth, identity, engagement }
export function calcPersona(scores) {
  const { systemic, depth, identity, engagement } = scores

  const archetypes = [
    { id: 'Architect', name: 'Architect', score: systemic * 1.5 + depth * 1.5 },
    { id: 'Catalyst',  name: 'Catalyst',  score: systemic * 1.5 + identity * 1.5 },
    { id: 'Guardian',  name: 'Guardian',  score: depth * 1.5 + engagement * 1.2 - systemic * 0.3 },
    { id: 'Explorer',  name: 'Explorer',  score: engagement * 1.5 + (20 - depth) * 0.3 },
  ]

  archetypes.sort((a, b) => b.score - a.score)
  return archetypes[0].id
}
