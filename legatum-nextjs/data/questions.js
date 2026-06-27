export const QUESTIONS = [
  {
    id: 1,
    text: "Imagine you have one free Saturday. A friend is organising a community clean-up with 40 strangers. You...",
    options: [
      { key: 'A', text: "Jump in immediately — sounds energising", scores: { engagement: 3 } },
      { key: 'B', text: "Go if a close friend is also coming", scores: { depth: 2 } },
      { key: 'C', text: "Contribute quietly behind the scenes", scores: { depth: 1, identity: 1 } },
      { key: 'D', text: "Donate instead and skip the crowd", scores: { systemic: 1 } },
    ]
  },
  {
    id: 2,
    text: "You want to help a struggling neighbourhood. What matters most to you first?",
    options: [
      { key: 'A', text: "The specific families affected right now", scores: { depth: 2 } },
      { key: 'B', text: "The systemic reasons the neighbourhood declined", scores: { systemic: 3 } },
      { key: 'C', text: "Data on which interventions actually work", scores: { systemic: 2 } },
      { key: 'D', text: "Stories from people who live there", scores: { engagement: 2 } },
    ]
  },
  {
    id: 3,
    text: "You have €500 to give. How do you choose where it goes?",
    options: [
      { key: 'A', text: "I research impact per euro and pick the highest scorer", scores: { engagement: 3 } },
      { key: 'B', text: "I give to causes connected to people I know personally", scores: { depth: 2 } },
      { key: 'C', text: "I follow my gut about who needs it most", scores: { identity: 2 } },
      { key: 'D', text: "I spread it across several causes to cover more ground", scores: { engagement: 2 } },
    ]
  },
  {
    id: 4,
    text: "Which achievement would make you proudest in 20 years?",
    options: [
      { key: 'A', text: "I built something that outlasted me", scores: { identity: 3 } },
      { key: 'B', text: "I helped specific people I can name", scores: { depth: 3 } },
      { key: 'C', text: "I changed how a system works", scores: { systemic: 3 } },
      { key: 'D', text: "I inspired others to give", scores: { engagement: 2 } },
    ]
  },
  {
    id: 5,
    text: "Your giving philosophy is closer to...",
    options: [
      { key: 'A', text: "One river running deep — one cause, maximum impact", scores: { depth: 3 } },
      { key: 'B', text: "Many streams — diverse causes, broad reach", scores: { engagement: 2 } },
      { key: 'C', text: "Wherever the drought is worst — most urgent needs", scores: { systemic: 2 } },
      { key: 'D', text: "Where I have personal expertise or connection", scores: { depth: 2, identity: 1 } },
    ]
  },
  {
    id: 6,
    text: "A new NGO has a radical approach — unproven but potentially transformative. You...",
    options: [
      { key: 'A', text: "Back them early — high risk, high reward", scores: { systemic: 2 } },
      { key: 'B', text: "Wait for evidence before committing", scores: { depth: 3 } },
      { key: 'C', text: "Fund a small pilot to test before scaling", scores: { systemic: 2, depth: 1 } },
      { key: 'D', text: "Stick with established organisations", scores: { depth: 2 } },
    ]
  },
  {
    id: 7,
    text: "Real change happens through...",
    options: [
      { key: 'A', text: "Fixing root causes even if results take decades", scores: { systemic: 3 } },
      { key: 'B', text: "Helping individuals directly today", scores: { depth: 2 } },
      { key: 'C', text: "Building movements and shifting culture", scores: { engagement: 2 } },
      { key: 'D', text: "Policy and institutional reform", scores: { systemic: 2 } },
    ]
  },
  {
    id: 8,
    text: "Your ideal giving is...",
    options: [
      { key: 'A', text: "Completely anonymous — impact is what matters", scores: { depth: 2 } },
      { key: 'B', text: "Known to the organisation but not the public", scores: { depth: 1 } },
      { key: 'C', text: "Part of my public identity — I am proud of it", scores: { identity: 3 } },
      { key: 'D', text: "Shared selectively with people I trust", scores: { engagement: 1 } },
    ]
  },
  {
    id: 9,
    text: "Beyond money, what would you most want to contribute?",
    options: [
      { key: 'A', text: "My professional skills and network", scores: { engagement: 2 } },
      { key: 'B', text: "My time on the ground", scores: { depth: 2 } },
      { key: 'C', text: "My voice and platform", scores: { identity: 2 } },
      { key: 'D', text: "Just the money — I trust the experts", scores: { systemic: 1 } },
    ]
  },
  {
    id: 10,
    text: "What feeling drives you most when you give?",
    options: [
      { key: 'A', text: "Injustice — something is wrong and I can fix it", scores: { systemic: 2, engagement: 1 } },
      { key: 'B', text: "Gratitude — I have been fortunate and want to share", scores: { depth: 1 } },
      { key: 'C', text: "Curiosity — I want to understand complex problems", scores: { systemic: 2 } },
      { key: 'D', text: "Connection — I want to be part of something larger", scores: { engagement: 2 } },
    ]
  },
  {
    id: 11,
    text: "Your giving feels most meaningful when...",
    options: [
      { key: 'A', text: "I see results within months", scores: { engagement: 2 } },
      { key: 'B', text: "I know the impact compounds over years", scores: { systemic: 2 } },
      { key: 'C', text: "The results are uncertain but the cause is right", scores: { identity: 2 } },
      { key: 'D', text: "Someone tells me directly that it helped", scores: { depth: 2 } },
    ]
  },
  {
    id: 12,
    text: "Which statement resonates most?",
    options: [
      { key: 'A', text: "I want to give flexibly with no long-term commitment", scores: { engagement: 2 } },
      { key: 'B', text: "I want a structured approach but still stay in control", scores: { systemic: 2 } },
      { key: 'C', text: "I want my name attached to something lasting", scores: { identity: 3 } },
      { key: 'D', text: "I want to delegate everything and trust the experts", scores: { depth: 1 } },
    ]
  },
]

export function calcPersona(scores) {
  const { systemic, depth, identity, engagement } = scores
  const s = systemic || 0, d = depth || 0, i = identity || 0, e = engagement || 0

  const candidates = [
    { id: 'Architect', score: s * 1.5 + d * 1.5 + i * 0.5 },
    { id: 'Catalyst',  score: s * 1.5 + i * 1.2 + e * 0.5 },
    { id: 'Guardian',  score: d * 1.5 + e * 1.0 - s * 0.2 },
    { id: 'Explorer',  score: e * 1.5 + i * 0.8 + (12 - d) * 0.3 },
  ]
  candidates.sort((a, b) => b.score - a.score)
  return candidates[0].id
}
