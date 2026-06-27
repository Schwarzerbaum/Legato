import { useState, useRef, useEffect, useMemo } from "react"
import { motion } from "framer-motion"
import ReactMarkdown from "react-markdown"
import OpenAI from "openai"
import {
  ListTree, Sparkles, Scale, ArrowRight, Heart, Layers, Globe, MapPin, TrendingUp, Send,
} from "lucide-react"
import { useAppStore } from "@/store/useAppStore"
import { companyById, foundationById, fieldById } from "@/data/index"
import type { Topic } from "@/data/index"
import { computeAllocations, type Allocation } from "@/lib/giving"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const ACCENT = "#d97706" // Plan accent
const PRESETS = [25_000, 50_000, 100_000, 250_000]

function euro(n: number): string {
  return "€" + Math.round(n).toLocaleString("de-DE")
}

function partnerName(t: Topic): string {
  if (t.companyId) return companyById[t.companyId]?.name ?? ""
  if (t.foundationId) return foundationById[t.foundationId]?.name ?? ""
  return ""
}

// ── AI companion (right pane) — forecast / planning focused ───────────────────

const client = new OpenAI({
  apiKey: "not-needed",
  baseURL: `${window.location.origin}/api/ai/v1`,
  dangerouslyAllowBrowser: true,
})

const MODEL = "gpt-4o-mini"

interface Message {
  role: "user" | "assistant"
  content: string
}

function PlanCompanion({ plan, total }: { plan: Allocation[]; total: number }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const systemPrompt = useMemo(() => {
    const portfolio = plan
      .map(a => {
        const impact = a.impact ? `≈ ${a.impact.units}× ${a.impact.phrase}` : a.topic.impactUnit
        return `- ${a.topic.title} (${partnerName(a.topic)}, ${a.topic.region}) — ${euro(a.amount)}/yr (${a.pct}%): would fund ${impact}`
      })
      .join("\n")

    return `You are the Legato Planning Companion — an AI advisor from LBBW that helps a donor plan their giving and understand the impact it will create.

## The donor's draft plan (a FORECAST — they have not given yet)
They intend to give ${euro(total)} per year, split across ${plan.length} committed project(s):
${portfolio}

## Your role
Help the donor decide how to allocate and understand the impact their giving WILL create. Suggest how to rebalance for more impact, compare projects, and explain trade-offs. Always speak in forward-looking terms ("your plan would fund…", "this allocation could create…") — never claim impact has already happened.
Be concise, direct, warm and credible. Use bullet points for action items and refer to concrete figures from their plan.`
  }, [plan, total])

  useEffect(() => {
    setMessages([
      {
        role: "assistant",
        content: `Your plan directs **${euro(total)}/year** across **${plan.length} project${plan.length !== 1 ? "s" : ""}**. Ask me how to allocate for more impact, or what your giving would create.`,
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
      const stream = await client.chat.completions.create({
        model: MODEL,
        max_tokens: 1500,
        stream: true,
        messages: [
          { role: "system", content: systemPrompt },
          ...newMessages.map(m => ({ role: m.role, content: m.content })),
        ],
      })
      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta?.content
        if (delta) {
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: "assistant",
              content: updated[updated.length - 1].content + delta,
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
        <span className="ds-label">Planning Companion</span>
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
          placeholder="How should I allocate for more impact?"
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

// ── Forecast stat ─────────────────────────────────────────────────────────────

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="mb-1" style={{ color: ACCENT }}>{icon}</div>
      <p className="ds-title-sm">{value}</p>
      <p className="ds-caption text-muted-foreground">{label}</p>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function PlanPage() {
  const {
    committedTopicIds,
    givingTotal,
    allocations,
    setGivingTotal,
    setAllocation,
    setCurrentPhase,
  } = useAppStore()

  const plan = useMemo(
    () => computeAllocations(committedTopicIds, allocations, givingTotal),
    [committedTopicIds, allocations, givingTotal],
  )

  if (plan.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm space-y-3 text-center">
          <ListTree className="mx-auto size-8 text-muted-foreground/40" />
          <p className="ds-label text-muted-foreground">No projects to plan yet</p>
          <p className="ds-caption text-muted-foreground/60">
            Commit to a few impact projects in Explore, then come back to set your
            donation amount and see the impact your giving will create.
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

  const causeAreas = new Set(plan.flatMap(a => a.topic.fieldIds)).size
  const regions = new Set(plan.map(a => a.topic.region)).size

  return (
    <div className="flex h-full min-h-0 bg-background">
      {/* Left — plan controls + forecast */}
      <div className="flex-1 overflow-y-auto border-r border-border">
        <div className="mx-auto max-w-2xl space-y-8 px-8 py-10 pb-28">
          {/* Header */}
          <div className="space-y-2">
            <div className="flex items-center gap-2" style={{ color: ACCENT }}>
              <ListTree className="size-5" />
              <span className="ds-caption font-medium uppercase tracking-wide">Phase 2 · Plan</span>
            </div>
            <h1 className="ds-title-xl">Plan your impact</h1>
            <p className="ds-body text-muted-foreground">
              Decide how much to give and how to split it — and see the impact your
              giving would create.
            </p>
          </div>

          {/* Total amount */}
          <div className="space-y-3 rounded-2xl border border-border bg-card p-6">
            <label className="ds-label">I want to give</label>
            <div className="flex items-baseline gap-1">
              <span className="ds-title-lg text-muted-foreground">€</span>
              <input
                type="number"
                min={25_000}
                step={5_000}
                value={givingTotal}
                onChange={e => setGivingTotal(Number(e.target.value))}
                className="w-44 bg-transparent ds-title-xl outline-none"
                style={{ color: ACCENT }}
              />
              <span className="ds-caption text-muted-foreground">per year</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map(p => (
                <button
                  key={p}
                  onClick={() => setGivingTotal(p)}
                  className={`rounded-full border px-3 py-1 ds-caption transition ${
                    givingTotal === p ? "border-transparent text-white" : "border-border text-muted-foreground hover:border-foreground/30"
                  }`}
                  style={givingTotal === p ? { backgroundColor: ACCENT } : undefined}
                >
                  {euro(p)}
                </button>
              ))}
            </div>
          </div>

          {/* Forecast */}
          <div className="space-y-4 rounded-2xl border p-6" style={{ borderColor: ACCENT, backgroundColor: "rgba(217,119,6,0.06)" }}>
            <div className="flex items-center gap-2" style={{ color: ACCENT }}>
              <TrendingUp className="size-4" />
              <span className="ds-caption font-medium uppercase tracking-wide">Your forecast impact</span>
            </div>
            <p className="ds-title-sm leading-snug">
              Your <span style={{ color: ACCENT }}>{euro(givingTotal)}/year</span> would fund{" "}
              <span style={{ color: ACCENT }}>{plan.length}</span> project{plan.length !== 1 ? "s" : ""} across{" "}
              <span style={{ color: ACCENT }}>{causeAreas}</span> cause areas in{" "}
              <span style={{ color: ACCENT }}>{regions}</span> region{regions !== 1 ? "s" : ""}.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat icon={<Heart className="size-4" />} value={String(plan.length)} label="projects" />
              <Stat icon={<Layers className="size-4" />} value={String(causeAreas)} label="cause areas" />
              <Stat icon={<Globe className="size-4" />} value={String(regions)} label="regions" />
              <Stat icon={<TrendingUp className="size-4" />} value={euro(givingTotal)} label="per year" />
            </div>
          </div>

          {/* Distribution */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-0.5">
              <div className="flex items-center gap-2">
                <Scale className="size-4 text-muted-foreground" />
                <span className="ds-label">Distribute across {plan.length} project{plan.length !== 1 ? "s" : ""}</span>
              </div>
              <button
                onClick={() => plan.forEach(a => setAllocation(a.topic.id, 50))}
                className="ds-caption text-muted-foreground hover:text-foreground transition-colors"
              >
                Even split
              </button>
            </div>

            {plan.map(({ topic: p, weight, amount, pct, impact }, i) => {
              const causes = p.fieldIds.map(id => fieldById[id]?.name).filter(Boolean).slice(0, 2)
              return (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: 0.03 * i }}
                  className="space-y-3 rounded-xl border border-border bg-card p-5"
                >
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

                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={weight}
                    onChange={e => setAllocation(p.id, Number(e.target.value))}
                    className="w-full cursor-pointer accent-[#d97706]"
                  />

                  {impact && (
                    <div className="rounded-lg px-3 py-2.5" style={{ backgroundColor: "rgba(217,119,6,0.08)" }}>
                      <p className="ds-caption" style={{ color: ACCENT }}>Would fund</p>
                      <p className="ds-label leading-snug">
                        <span className="ds-title-sm" style={{ color: ACCENT }}>≈ {impact.units.toLocaleString("de-DE")}×</span>{" "}
                        <span className="font-normal text-muted-foreground">{impact.phrase}</span>
                      </p>
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Right — planning companion */}
      <div className="hidden w-[380px] shrink-0 flex-col px-6 py-6 lg:flex">
        <PlanCompanion plan={plan} total={givingTotal} />
      </div>
    </div>
  )
}
