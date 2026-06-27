import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import OpenAI from "openai"
import { X, Sparkles, Send } from "lucide-react"
import { useAppStore } from "@/store/useAppStore"
import { CAUSE_THEMES, themeByKey } from "@/data/themes"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const client = new OpenAI({
  apiKey: "not-needed",
  baseURL: `${window.location.origin}/api/ai/v1`,
  dangerouslyAllowBrowser: true,
})

const MODEL = "gpt-4o-mini"

const SELECT_TOOL: OpenAI.Chat.Completions.ChatCompletionTool = {
  type: "function",
  function: {
    name: "select_causes",
    description:
      "Select the cause cards that best match what the giver cares about. Call this once you understand them; you may call it again to refine.",
    parameters: {
      type: "object",
      properties: {
        keys: {
          type: "array",
          items: { type: "string", enum: CAUSE_THEMES.map(t => t.key) },
          description: "2 to 4 theme keys, ordered by relevance.",
        },
      },
      required: ["keys"],
    },
  },
}

const SYSTEM = `You are a warm, concise giving advisor at LBBW helping a new philanthropist who isn't sure where to start discover which causes matter to them.

Available cause themes (key — label):
${CAUSE_THEMES.map(t => `${t.key} — ${t.label}`).join("\n")}

How you work:
- The ONLY way to actually select cards is by calling the select_causes function. Text you write does NOT select anything, so never just name causes in prose.
- As soon as the user tells you what they care about (usually their very first message), immediately call select_causes with the 2–4 best-matching theme keys. Do not describe your recommendation in words instead of calling the tool.
- Only ask a brief clarifying question if their message is genuinely too vague to map to any theme.
- After calling the tool, write 1–2 warm sentences naming what you picked and inviting them to adjust the cards.`

interface DisplayMsg {
  role: "user" | "assistant"
  text: string
}

export function HelpMeDecideChat({ open, onClose }: { open: boolean; onClose: () => void }) {
  const setSelectedThemes = useAppStore(s => s.setSelectedThemes)
  const [display, setDisplay] = useState<DisplayMsg[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const convo = useRef<OpenAI.Chat.Completions.ChatCompletionMessageParam[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && display.length === 0) {
      setDisplay([
        {
          role: "assistant",
          text: "Hi! Not sure where to start? Tell me what matters to you — your family, the planet, your community, a cause close to your heart — and I'll suggest the causes that fit.",
        },
      ])
    }
  }, [open, display.length])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [display, loading])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput("")
    setDisplay(d => [...d, { role: "user", text }])
    convo.current.push({ role: "user", content: text })
    setLoading(true)

    try {
      let guard = 0
      while (guard++ < 4) {
        const res = await client.chat.completions.create({
          model: MODEL,
          max_tokens: 600,
          messages: [{ role: "system", content: SYSTEM }, ...convo.current],
          tools: [SELECT_TOOL],
        })

        const m = res.choices[0].message
        if (m.content) setDisplay(d => [...d, { role: "assistant", text: m.content! }])
        convo.current.push({ role: "assistant", content: m.content ?? "", tool_calls: m.tool_calls })

        if (!m.tool_calls?.length) break

        for (const tc of m.tool_calls) {
          if (tc.type === "function" && tc.function.name === "select_causes") {
            try {
              const args = JSON.parse(tc.function.arguments) as { keys?: unknown[] }
              const keys = (args.keys ?? []).filter(
                (k): k is string => typeof k === "string" && !!themeByKey[k],
              )
              if (keys.length) setSelectedThemes(keys)
            } catch {
              // ignore malformed tool args
            }
          }
          convo.current.push({ role: "tool", tool_call_id: tc.id, content: "Cards updated on screen." })
        }
      }
    } catch {
      setDisplay(d => [
        ...d,
        { role: "assistant", text: "I couldn't connect just now — you can pick the cards yourself, or try again." },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "tween", duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="fixed right-0 top-0 z-40 flex h-screen w-full max-w-sm flex-col border-l border-border bg-background shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-amber-500" />
              <span className="ds-label">Help me decide</span>
            </div>
            <button onClick={onClose} className="text-muted-foreground transition-colors hover:text-foreground" aria-label="Close">
              <X className="size-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
            {display.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="mr-2 mt-0.5 flex size-6 flex-shrink-0 items-center justify-center rounded-md bg-secondary">
                    <Sparkles className="size-3.5 text-amber-500" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                    msg.role === "user" ? "bg-primary text-primary-foreground whitespace-pre-wrap" : "bg-secondary text-foreground"
                  }`}
                >
                  {msg.role === "user" ? (
                    msg.text
                  ) : (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      }}
                    >
                      {msg.text}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="mr-2 mt-0.5 flex size-6 flex-shrink-0 items-center justify-center rounded-md bg-secondary">
                  <Sparkles className="size-3.5 animate-pulse text-amber-500" />
                </div>
                <div className="rounded-2xl bg-secondary px-3.5 py-2.5 text-sm text-muted-foreground">…</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="flex items-end gap-2 border-t border-border px-5 py-4">
            <Textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. I want to help kids and the planet…"
              className="min-h-10 resize-none"
              rows={1}
              disabled={loading}
            />
            <Button size="icon" className="flex-shrink-0 rounded-full" onClick={send} disabled={loading || !input.trim()}>
              <Send className="size-4" />
            </Button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
