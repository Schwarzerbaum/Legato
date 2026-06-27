import { useState, useRef, useEffect, useMemo } from "react"
import ReactMarkdown from "react-markdown"
import Anthropic from "@anthropic-ai/sdk"
import { useAppStore } from "@/store/useAppStore"
import { companyById, foundationById, fieldById } from "@/data/index"
import type { Topic } from "@/data/index"
import { computeAllocations, type Allocation } from "@/lib/giving"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Sparkles, Send, Heart, Layers, Globe, MapPin, ArrowRight, TrendingUp } from "lucide-react"

const ACCENT = "#e11d48" // phase-4 (Impact) accent

function euro(n: number): string {
  return "€" + Math.round(n).toLocaleString("de-DE")
}

function partnerName(t: Topic): string {
  if (t.companyId) return companyById[t.companyId]?.name ?? ""
  if (t.foundationId) return foundationById[t.foundationId]?.name ?? ""
  return ""
}

// ── Impact overview (left pane) ──────────────────────────────────────────────

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-1.5" style={{ color: ACCENT }}>{icon}</div>
      <p className="ds-title-sm">{value}</p>
      <p className="ds-caption text-muted-foreground">{label}</p>
    </div>
  )
}

function ImpactOverview({ plan, total }: { plan: Allocation[]; total: number }) {
  const causeAreas = new Set(plan.flatMap(a => a.topic.fieldIds)).size
  const regions = new Set(plan.map(a => a.topic.region)).size

  return (
    <div className="mx-auto max-w-2xl space-y-8 px-8 py-10 pb-16">
      <div className="space-y-2">
        <div className="flex items-center gap-2" style={{ color: ACCENT }}>
          <Heart className="size-5" />
          <span className="ds-caption font-medium uppercase tracking-wide">Phase 4 · Impact</span>
        </div>
        <h1 className="ds-title-xl">Your impact so far</h1>
        <p className="ds-body text-muted-foreground">
          Here's what your giving is achieving across your committed portfolio.
        </p>
      </div>

      {/* Hero stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat icon={<TrendingUp className="size-5" />} value={euro(total)} label="deployed / year" />
        <Stat icon={<Heart className="size-5" />} value={String(plan.length)} label="projects funded" />
        <Stat icon={<Layers className="size-5" />} value={String(causeAreas)} label="cause areas" />
        <Stat icon={<Globe className="size-5" />} value={String(regions)} label="regions reached" />
      </div>

      {/* Per-project achievements */}
      <div className="space-y-3">
        <span className="ds-label px-0.5">What your giving achieves</span>
        {plan.map(({ topic: p, amount, pct, impact }) => {
          const causes = p.fieldIds.map(id => fieldById[id]?.name).filter(Boolean).slice(0, 2)
          return (
            <div key={p.id} className="space-y-2.5 rounded-xl border border-border bg-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-1">
                  <p className="ds-caption text-muted-foreground">{partnerName(p)}</p>
                  <h3 className="ds-label leading-tight">{p.title}</h3>
                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    <span className="flex items-center gap-1 ds-caption text-muted-foreground">
                      <MapPin className="size-3" /> {p.region}
                    </span>
                    {causes.map(c => (
                      <span key={c} className="rounded-full border border-border px-2 py-0.5 ds-caption text-muted-foreground">{c}</span>
                    ))}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <p className="ds-title-sm" style={{ color: ACCENT }}>{euro(amount)}</p>
                  <p className="ds-caption text-muted-foreground">{pct}% / yr</p>
                </div>
              </div>

              {impact && (
                <div className="flex items-baseline gap-1.5 rounded-lg bg-secondary/60 px-3 py-2">
                  <Sparkles className="size-3.5 shrink-0 translate-y-0.5" style={{ color: ACCENT }} />
                  <p className="ds-caption text-muted-foreground">
                    <span className="font-semibold text-foreground">≈ {impact.units.toLocaleString("de-DE")}×</span>{" "}
                    {impact.phrase}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── AI companion (right pane) ────────────────────────────────────────────────

const client = new Anthropic({
  apiKey: "not-needed",
  baseURL: `${window.location.origin}/api/ai`,
  dangerouslyAllowBrowser: true,
})

interface Message {
  role: "user" | "assistant"
  content: string
}

function CompanionChat({ plan, total }: { plan: Allocation[]; total: number }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const systemPrompt = useMemo(() => {
    const portfolio = plan
      .map(a => {
        const impact = a.impact ? `≈ ${a.impact.units}× ${a.impact.phrase}` : a.topic.impactUnit
        return `- ${a.topic.title} (${partnerName(a.topic)}, ${a.topic.region}) — ${euro(a.amount)}/yr (${a.pct}%): ${impact}`
      })
      .join("\n")

    return `You are the Legato Impact Companion — a dedicated AI assistant from LBBW that tracks the real-world impact of a donor's giving.

## The donor's plan
They give ${euro(total)} per year, split across ${plan.length} committed project(s):
${portfolio}

## Your role
Help the donor understand and grow their impact: answer "what has my giving achieved?", suggest how to rebalance or increase their giving, surface milestones, and — when it makes sense — explain growing into their own Impact Hub (a donor-advised fund) with LBBW.
Be concise, direct, warm and credible. Use bullet points for action items. Refer to concrete figures from their plan.`
  }, [plan, total])

  useEffect(() => {
    setMessages([
      {
        role: "assistant",
        content: `Your **${euro(total)}/year** is working across **${plan.length} project${plan.length !== 1 ? "s" : ""}**. Ask me what it's achieving, or how to grow your impact.`,
      },
    ])
  }, [plan.length, total])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return
    const newMessages = [...messages, { role: "user", content: text } as Message]
    setMessages([...newMessages, { role: "assistant", content: "" }])
    setInput("")
    setLoading(true)
    try {
      const stream = client.messages.stream({
        model: "claude-opus-4-6",
        max_tokens: 1500,
        system: systemPrompt,
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
      })
      for await (const event of stream) {
        if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: "assistant",
              content: updated[updated.length - 1].content + (event.delta as { type: string; text: string }).text,
            }
            return updated
          })
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: "assistant", content: "Sorry, something went wrong. Please try again." }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-shrink-0 items-center gap-2 border-b border-border pb-4">
        <Sparkles className="size-4" style={{ color: ACCENT }} />
        <span className="ds-label">Impact Companion</span>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto py-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="mr-2 mt-0.5 flex size-6 flex-shrink-0 items-center justify-center rounded-md bg-secondary">
                <Sparkles className="size-3.5" style={{ color: ACCENT }} />
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                msg.role === "user" ? "bg-primary text-primary-foreground whitespace-pre-wrap" : "bg-secondary text-foreground"
              }`}
            >
              {msg.role === "user" ? (
                msg.content
              ) : (
                <ReactMarkdown
                  components={{
                    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    ul: ({ children }) => <ul className="mb-1 list-disc space-y-0.5 pl-4">{children}</ul>,
                    ol: ({ children }) => <ol className="mb-1 list-decimal space-y-0.5 pl-4">{children}</ol>,
                    li: ({ children }) => <li>{children}</li>,
                  }}
                >
                  {msg.content || (loading && i === messages.length - 1 ? "…" : "")}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex flex-shrink-0 items-end gap-2 border-t border-border pt-4">
        <Textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What has my giving achieved?"
          className="min-h-10 resize-none"
          rows={1}
          disabled={loading}
        />
        <Button size="icon" className="flex-shrink-0 rounded-full" onClick={sendMessage} disabled={loading || !input.trim()}>
          <Send className="size-4" />
        </Button>
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function CompanionPage() {
  const { committedTopicIds, allocations, givingTotal, setCurrentPhase } = useAppStore()
  const plan = useMemo(
    () => computeAllocations(committedTopicIds, allocations, givingTotal),
    [committedTopicIds, allocations, givingTotal],
  )

  if (plan.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm space-y-3 text-center">
          <Heart className="mx-auto size-8 text-muted-foreground/40" />
          <p className="ds-label text-muted-foreground">No impact to show yet</p>
          <p className="ds-caption text-muted-foreground/60">
            Commit to projects and set your giving plan — then track the real-world
            impact of your donations here.
          </p>
          <button
            onClick={() => setCurrentPhase(1)}
            className="mx-auto mt-1 flex items-center gap-1.5 rounded-lg px-3 py-1.5 ds-caption font-medium text-white"
            style={{ backgroundColor: ACCENT }}
          >
            Back to Explore <ArrowRight className="size-3.5" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 bg-background">
      <div className="flex-1 overflow-y-auto border-r border-border">
        <ImpactOverview plan={plan} total={givingTotal} />
      </div>
      <div className="hidden w-[380px] shrink-0 flex-col px-6 py-6 lg:flex">
        <CompanionChat plan={plan} total={givingTotal} />
      </div>
    </div>
  )
}
