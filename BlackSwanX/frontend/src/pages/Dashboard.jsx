import { useState, useEffect } from 'react'

const API = '/api'

export default function Dashboard() {
  const [query, setQuery] = useState('')
  const [topics, setTopics] = useState([])
  const [hardware, setHardware] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API}/system/hardware`).then(r => r.json()).then(setHardware).catch(() => {})
    fetch(`${API}/analysis/topics`).then(r => r.json()).then(setTopics).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/analysis/topics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      })
      const topic = await res.json()
      setTopics(prev => [topic, ...prev])
      setQuery('')

      // Auto-start crawl
      await fetch(`${API}/analysis/topics/${topic.id}/crawl`, { method: 'POST' })
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold text-white mb-2">BlackSwanX</h1>
      <p className="text-gray-400 mb-8">
        Enter any topic. We'll crawl the web, compress opinions into Social Personas,
        run adversarial simulations, and generate a Decision-Ready Map.
      </p>

      {/* Hardware Status */}
      {hardware && (
        <div className="bg-[#111118] border border-gray-800 rounded-xl p-4 mb-6 flex gap-6 text-sm">
          <div>
            <span className="text-gray-500">Chip</span>
            <div className="text-cyan-400">{hardware.hardware?.chip || 'Detecting...'}</div>
          </div>
          <div>
            <span className="text-gray-500">RAM</span>
            <div className="text-cyan-400">{hardware.hardware?.total_ram_gb} GB</div>
          </div>
          <div>
            <span className="text-gray-500">Cluster Model</span>
            <div className="text-green-400">{hardware.models?.cluster_model || '...'}</div>
          </div>
          <div>
            <span className="text-gray-500">Reasoning Model</span>
            <div className="text-green-400">{hardware.models?.reasoning_model || '...'}</div>
          </div>
        </div>
      )}

      {/* Topic Input */}
      <form onSubmit={handleSubmit} className="mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="e.g., AI regulation trends, Bitcoin sentiment, climate policy..."
            className="flex-1 bg-[#111118] border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white px-6 py-3 rounded-xl font-medium transition-colors"
          >
            {loading ? 'Starting...' : 'Analyze'}
          </button>
        </div>
      </form>

      {/* Topic List */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-300">Recent Analyses</h2>
        {topics.length === 0 ? (
          <p className="text-gray-600 text-sm">No topics yet. Enter one above to get started.</p>
        ) : (
          topics.map(topic => (
            <div
              key={topic.id}
              className="bg-[#111118] border border-gray-800 rounded-xl p-4 flex items-center justify-between"
            >
              <div>
                <div className="text-white font-medium">{topic.query}</div>
                <div className="text-xs text-gray-500 mt-1">ID: {topic.id}</div>
              </div>
              <StatusBadge status={topic.status} />
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const colors = {
    pending: 'bg-gray-700 text-gray-300',
    crawling: 'bg-blue-900/50 text-blue-400',
    analyzing: 'bg-yellow-900/50 text-yellow-400',
    simulating: 'bg-purple-900/50 text-purple-400',
    complete: 'bg-green-900/50 text-green-400',
  }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium ${colors[status] || colors.pending}`}>
      {status}
    </span>
  )
}
