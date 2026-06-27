'use client'
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'

const INK    = '#0f172a'
const PARCH  = '#ffffff'
const LBBW   = '#003B6F'
const GREEN  = '#059669'

// ── Types ─────────────────────────────────────────────────────────────────────
interface Message { role: 'user' | 'assistant'; content: string }

// ── Bank system prompt ────────────────────────────────────────────────────────
const SYSTEM = `You are the Legato Advisor Intelligence — a private AI assistant embedded in LBBW's philanthropic banking platform. You assist LBBW relationship managers and philanthropic advisors with:

**Portfolio & Client Intelligence**
- Client giving mandates, cause pillars, SDG alignment, allocation strategy
- Portfolio rebalancing and sector concentration analysis
- Corporate matching and co-funding structures (1:1, 2:1 match mechanisms)

**Credibility & Due Diligence**
- NGO credibility scoring: financial transparency, governance, impact measurement, ESG conformity, media sentiment
- Legal entity analysis: Verein, gAG, gGmbH, Stiftung (foundation), AöR, KdöR, Kapitalgesellschaft
- Tax law: §10b EStG, §55–68 AO Non-profit law, §9 KStG, §5 KStG, §13 ErbStG
- SFDR Art. 8/9 alignment, DZI Spendensiegel, PHINEO-Wirkt-Siegel criteria

**Foundation Intelligence**
- Foundation law BW: Regierungspräsidium recognition, §55–68 Tax Code compliance
- Stiftungsregister, tax exemption notice renewal cycles, GPA BW audit preparation
- Disbursement planning, §55 AO fund utilisation report

**Impact & SDG Intelligence**
- SDG mapping and portfolio-level impact reporting
- CSRD Social Taxonomy alignment, SFDR disclosure requirements
- impact measurement frameworks: PHINEO, EVPA, GIIN IRIS+

**Organisations in LBBW Scope** (for reference)
NGOs: BUND e.V. (score 93/100, DZI), PHINEO gAG (94/100), SOS-Kinderdorf (88/100), Welthungerhilfe (83/100), BW Stiftung (74/100), Aktion Mensch (85/100)
Corporates: Robert Bosch GmbH, Mercedes-Benz AG, Würth Group, Porsche AG
Clients: Dr. Miriam Hoffmann (€4.8M AUM, Climate/Education), Familie Breitner-Koch (€12.2M, Poverty/Rights), Stefan Walczak (onboarding, Digital), Ingrid von Saalfeld (€38.5M, Foundation granted)
Foundations managed: Hoffmann Klimastiftung (€1.2M), Breitner-Koch Sozialstiftung (€4.8M), von Saalfeld Stiftung (€12.5M), Walczak Digitalstiftung (pending recognition)

Respond in the same language the advisor uses (German or English). Be concise, precise, and credible. Use bullet points for action items. Cite legal paragraphs and standards when relevant.`

// ── Suggested prompts ─────────────────────────────────────────────────────────
const SUGGESTIONS = [
  'Which NGOs are suitable for a climate-focused portfolio with §10b EStG deduction?',
  'What is the LBBW accreditation status of BUND e.V. and how is it scored?',
  'Breitner-Koch Sozialstiftung — what compliance deadlines are approaching?',
  'Explain the tax benefit difference between donating to a Verein vs. a gGmbH.',
  'How should we structure a 1:1 corporate match with Robert Bosch GmbH?',
  'Which of our managed foundations needs a Jahresbericht filed before Q3 2026?',
]

// ── Chat component ────────────────────────────────────────────────────────────
export default function AdvisorIntelligencePage() {
  const [messages, setMessages]   = useState<Message[]>([])
  const [input,    setInput]      = useState('')
  const [loading,  setLoading]    = useState(false)
  const [started,  setStarted]    = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(text?: string) {
    const content = (text ?? input).trim()
    if (!content || loading) return
    setStarted(true)
    setInput('')
    const userMsg: Message = { role: 'user', content }
    const next = [...messages, userMsg]
    setMessages(next)
    setLoading(true)

    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages([...next, assistantMsg])

    try {
      const res = await fetch('/api/ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system: SYSTEM,
          messages: next.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      if (!res.body) throw new Error('No body')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: updated[updated.length - 1].content + chunk,
          }
          return updated
        })
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: 'Something went wrong. Please try again.' }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: 'calc(100vh - 110px)',
      marginLeft: '-40px', marginRight: '-40px',
    }}>
      {/* Header */}
      <div style={{
        padding: '22px 40px 16px',
        borderBottom: `0.5px solid ${INK}10`,
        background: '#f8fafc', flexShrink: 0,
      }}>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'-0.01em',
          textTransform:'none', color:INK, opacity:0.28, marginBottom:6 }}>
          Legato · Advisor Intelligence
        </div>
        <div style={{ display:'flex', alignItems:'baseline', gap:12 }}>
          <h1 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:24, fontWeight:500,
            color:INK, margin:0 }}>AI Advisor</h1>
          <div style={{ display:'flex', alignItems:'center', gap:5 }}>
            <motion.div animate={{ opacity:[1,0.3,1] }} transition={{ repeat:Infinity, duration:2.5 }}
              style={{ width:6, height:6, borderRadius:'50%', background:GREEN }} />
            <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:GREEN }}>Online</span>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div style={{ flex:1, overflowY:'auto', padding:'28px 40px', display:'flex',
        flexDirection:'column', gap:0 }}>

        {/* Empty state */}
        {!started && (
          <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }}
            style={{ flex:1, display:'flex', flexDirection:'column',
              alignItems:'center', justifyContent:'center', textAlign:'center' }}>
            <div style={{ fontSize:28, opacity:0.15, marginBottom:20 }}>◈</div>
            <h2 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:22, fontWeight:500,
              color:INK, margin:'0 0 6px', opacity:0.7 }}>
              Ask anything about your portfolio
            </h2>
            <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14, color:INK,
              opacity:0.38, fontStyle:'italic', margin:'0 0 32px', maxWidth:400, lineHeight:1.7 }}>
              NGO credibility, foundation compliance, tax structures, client allocation strategy — all in one place.
            </p>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6, maxWidth:640, width:'100%' }}>
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s)} style={{
                  padding:'11px 14px', background:'#fff',
                  border:`1px solid ${INK}14`, borderRadius:4,
                  cursor:'pointer', textAlign:'left',
                  fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13,
                  color:INK, opacity:0.6, lineHeight:1.5,
                  transition:'all 0.15s',
                }}>
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* Message thread */}
        {messages.map((msg, i) => (
          <div key={i} style={{
            display:'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: 14,
          }}>
            {msg.role === 'assistant' && (
              <div style={{
                width:26, height:26, borderRadius:'50%',
                background: LBBW, display:'flex', alignItems:'center',
                justifyContent:'center', flexShrink:0,
                marginRight:10, marginTop:2,
                fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12, color:'#fff', letterSpacing:'0.05em',
              }}>L</div>
            )}
            <div style={{
              maxWidth:'72%',
              padding: msg.role === 'user' ? '10px 16px' : '12px 16px',
              background: msg.role === 'user' ? INK : '#fff',
              color: msg.role === 'user' ? PARCH : INK,
              borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '2px 12px 12px 12px',
              border: msg.role === 'assistant' ? `0.5px solid ${INK}0E` : 'none',
              fontFamily:"Inter, system-ui, -apple-system, sans-serif",
              fontSize:14.5,
              lineHeight:1.75,
            }}>
              {msg.role === 'user' ? (
                <span style={{ opacity:0.9 }}>{msg.content || (loading && i === messages.length - 1 ? '…' : '')}</span>
              ) : (
                <ReactMarkdown
                  components={{
                    p:      ({ children }) => <p style={{ margin:'0 0 8px' }}>{children}</p>,
                    strong: ({ children }) => <strong style={{ fontWeight:600 }}>{children}</strong>,
                    ul:     ({ children }) => <ul style={{ paddingLeft:18, margin:'6px 0' }}>{children}</ul>,
                    ol:     ({ children }) => <ol style={{ paddingLeft:18, margin:'6px 0' }}>{children}</ol>,
                    li:     ({ children }) => <li style={{ marginBottom:3 }}>{children}</li>,
                    code:   ({ children }) => <code style={{ background:`${INK}0C`, padding:'1px 5px',
                      borderRadius:2, fontSize:12, fontFamily:'monospace' }}>{children}</code>,
                    h2:     ({ children }) => <p style={{ fontWeight:600, marginBottom:5 }}>{children}</p>,
                    h3:     ({ children }) => <p style={{ fontWeight:600, marginBottom:4 }}>{children}</p>,
                  }}
                >
                  {msg.content || (loading && i === messages.length - 1 ? '…' : '')}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding:'14px 40px 20px',
        borderTop:`0.5px solid ${INK}10`,
        background: '#f8fafc', flexShrink:0,
      }}>
        <div style={{
          display:'flex', gap:10, alignItems:'flex-end',
          background:'#fff', border:`1px solid ${INK}18`,
          borderRadius:8, padding:'10px 12px',
        }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => { setInput(e.target.value); e.target.style.height='auto'; e.target.style.height=e.target.scrollHeight+'px' }}
            onKeyDown={handleKey}
            placeholder="Ask about clients, credibility, foundations, tax…"
            disabled={loading}
            rows={1}
            style={{
              flex:1, resize:'none', border:'none', outline:'none',
              background:'transparent',
              fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14.5,
              color:INK, lineHeight:1.6,
              maxHeight:160, overflow:'auto',
            }}
          />
          <button onClick={() => send()} disabled={loading || !input.trim()} style={{
            width:32, height:32, borderRadius:'50%', flexShrink:0,
            background: input.trim() && !loading ? INK : `${INK}18`,
            border:'none', cursor: input.trim() && !loading ? 'pointer' : 'default',
            display:'flex', alignItems:'center', justifyContent:'center',
            transition:'background 0.15s',
          }}>
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M1 12L12 6.5L1 1V5.5L8.5 6.5L1 7.5V12Z"
                fill={input.trim() && !loading ? '#F4F1EA' : `${INK}55`} />
            </svg>
          </button>
        </div>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
          textTransform:'none', color:INK, opacity:0.2, marginTop:7, textAlign:'center' }}>
          LBBW Advisor Intelligence · Claude Sonnet · Internal System
        </div>
      </div>
    </div>
  )
}
