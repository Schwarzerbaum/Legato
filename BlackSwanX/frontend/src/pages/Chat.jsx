import { useState, useRef, useEffect } from 'react'

const agents = [
  { id: 'provocateur', name: 'Agent Provocateur', color: 'text-red-400', icon: '⚡' },
  { id: 'whale', name: 'Sentiment Whale', color: 'text-blue-400', icon: '◈' },
  { id: 'catalyst', name: 'Catalyst', color: 'text-amber-400', icon: '◉' },
]

export default function Chat() {
  const [selectedAgent, setSelectedAgent] = useState('provocateur')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || streaming) return

    const userMsg = { role: 'user', content: input.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    try {
      const res = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: selectedAgent, message: userMsg.content }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let agentText = ''

      setMessages(prev => [...prev, { role: 'agent', content: '', agent: selectedAgent }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        agentText += decoder.decode(value, { stream: true })
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'agent', content: agentText, agent: selectedAgent }
          return updated
        })
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'agent', content: 'Error: Could not reach Ollama. Is it running?', agent: selectedAgent }])
    } finally {
      setStreaming(false)
    }
  }

  const agent = agents.find(a => a.id === selectedAgent)

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-2">Agent Chat</h1>
      <p className="text-gray-400 mb-4 text-sm">
        Talk directly to the adversarial agents. Ask "what-if" questions.
      </p>

      {/* Agent Selector */}
      <div className="flex gap-2 mb-4">
        {agents.map(a => (
          <button
            key={a.id}
            onClick={() => setSelectedAgent(a.id)}
            className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors ${
              selectedAgent === a.id
                ? 'bg-white/10 border border-gray-600 text-white'
                : 'bg-[#111118] border border-gray-800 text-gray-500 hover:text-gray-300'
            }`}
          >
            <span>{a.icon}</span> {a.name}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto bg-[#111118] border border-gray-800 rounded-xl p-4 mb-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 py-12">
            <p className="text-3xl mb-2">{agent?.icon}</p>
            <p>Ask {agent?.name} anything about the simulation.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-cyan-900/30 text-cyan-100'
                : 'bg-[#0a0a0f] text-gray-300 border border-gray-800'
            }`}>
              {msg.role === 'agent' && (
                <div className={`text-xs font-medium mb-1 ${agents.find(a => a.id === msg.agent)?.color || 'text-gray-500'}`}>
                  {agents.find(a => a.id === msg.agent)?.name}
                </div>
              )}
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={sendMessage} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={`Ask ${agent?.name}...`}
          className="flex-1 bg-[#111118] border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white px-6 py-3 rounded-xl font-medium"
        >
          {streaming ? '...' : 'Send'}
        </button>
      </form>
    </div>
  )
}
