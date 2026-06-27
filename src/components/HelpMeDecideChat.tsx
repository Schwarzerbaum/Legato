import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import Anthropic from "@anthropic-ai/sdk"
import { X, Sparkles, Send } from "lucide-react"
import { useAppStore } from "@/store/useAppStore"
import { CAUSE_THEMES, themeByKey } from "@/data/themes"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const client = new Anthropic({
  apiKey: "not-needed",
  baseURL: `${window.location.origin}/api/ai`,
  dangerouslyAllowBrowser: true,
})

const SELECT_TOOL = {
  name: "select_causes",
  description:
    "Select the cause cards that best match what the giver cares about. Call this once you understand them; you may call it again to refine.",
  input_schema: {
    type: "object" as const,
    properties: {
      keys: {
        type: "array",
        items: { type: "string", enum: CAUSE_THEMES.map(t => t.key) },
        description: "2 to 4 theme keys, ordered by relevance.",
      },
    },
    required: ["keys"],
  },
}

const SYSTEM = `You are a warm, concise giving advisor at LBBW helping a new philanthropist who isn't sure where to start discover which causes matter to them.

Available cause themes (key — label):
${CAUSE_THEMES.map(t => `${t.key} — ${t.label}`).join("\n")}

Have a short, friendly conversation. Ask at most one or two brief questions if you need to, then call the select_causes tool with the 2–4 best-matching theme keys. After selecting, briefly tell them what you picked and why, and invite them to adjust the cards. Keep every reply to 1–3 sentences.`

interface DisplayMsg {
  role: "user" | "assistant"
  text: string
}

export function HelpMeDecideChat({ open, onClose }: { open: boolean; onClose: () => void }) {
  const setSelectedThemes = useAppStore(s => s.setSelectedThemes)
  const [display, setDisplay] = useState<DisplayMsg[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const convo = useRef<Anthropic.MessageParam[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  // Seed the greeting when the panel opens fresh.
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
        const res = await client.messages.create({
          model: "claude-opus-4-6",
          max_tokens: 600,
          system: SYSTEM,
          tools: [SELECT_TOOL],
          messages: convo.current,
        })

        const textOut = res.content
          .filter((b): b is Anthropic.TextBlock => b.type === "text")
          .map(b => b.text)
          .join("")
          .trim()
        if (textOut) setDisplay(d => [...d, { role: "assistant", text: textOut }])

        convo.current.push({ role: "assistant", content: res.content })

        const toolUses = res.content.filter(
          (b): b is Anthropic.ToolUseBlock => b.type === "tool_use",
        )
        if (toolUses.length === 0) break

        for (const tu of toolUses) {
          if (tu.name === "select_causes") {
            const keys = ((tu.input as { keys?: unknown }).keys ?? []) as unknown[]
            const valid = keys.filter((k): k is string => typeof k === "string" && !!themeByKey[k])
            if (valid.length) setSelectedThemes(valid)
          }
        }
        convo.current.push({
          role: "user",
          content: toolUses.map(tu => ({
            type: "tool_result" as const,
            tool_use_id: tu.id,
            content: "Cards updated on screen.",
          })),
        })
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
