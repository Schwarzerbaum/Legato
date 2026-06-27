import { useState } from 'react'

export default function Simulation() {
  const [rounds, setRounds] = useState([])
  const [running, setRunning] = useState(false)

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold text-white mb-2">Mirror Simulation</h1>
      <p className="text-gray-400 mb-6 text-sm">
        Three adversarial agents debate the future. Watch them argue in real-time.
      </p>

      {/* Agent Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <AgentCard
          name="Agent Provocateur"
          role="Finds how this trend could be destroyed"
          color="red"
          icon="⚡"
        />
        <AgentCard
          name="Sentiment Whale"
          role="Represents the mass majority opinion"
          color="blue"
          icon="◈"
        />
        <AgentCard
          name="Catalyst"
          role="Predicts the event that flips everything"
          color="amber"
          icon="◉"
        />
      </div>

      {/* Debate Feed */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-gray-300 mb-4">Debate Feed</h2>
        {rounds.length === 0 ? (
          <div className="text-center py-12 text-gray-600">
            <p className="text-4xl mb-3">◎</p>
            <p>Start an analysis from the Dashboard to see the agents debate here.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {rounds.map((round, i) => (
              <div key={i} className="border-l-2 border-gray-700 pl-4">
                <div className="text-sm text-gray-500">Round {i + 1}</div>
                <div className="mt-2 text-sm text-gray-300 whitespace-pre-wrap">
                  {round}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function AgentCard({ name, role, color, icon }) {
  const borderColors = {
    red: 'border-red-800',
    blue: 'border-blue-800',
    amber: 'border-amber-800',
  }
  const textColors = {
    red: 'text-red-400',
    blue: 'text-blue-400',
    amber: 'text-amber-400',
  }
  return (
    <div className={`bg-[#111118] border ${borderColors[color]} rounded-xl p-4`}>
      <div className="text-2xl mb-2">{icon}</div>
      <div className={`font-semibold ${textColors[color]}`}>{name}</div>
      <div className="text-xs text-gray-500 mt-1">{role}</div>
    </div>
  )
}
