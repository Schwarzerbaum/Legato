import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ReactFlow, {
  Background,
  Controls,
  Panel,
  useNodesState,
  useEdgesState,
  ConnectionLineType,
  type Node,
  type Edge,
  type NodeChange,
} from "reactflow"
import "reactflow/dist/style.css"
import ELK from "elkjs/lib/elk.bundled.js"
import Anthropic from "@anthropic-ai/sdk"
import { Send, X } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ResearchNode, type ResearchNodeData } from "../components/research/ResearchNode"
import { useAppStore } from "@/store/useAppStore"
import { topicById } from "@/data/index"
import legatoLogo from "@/assets/legato.svg"

// ── Anthropic client ──────────────────────────────────────────────────────────
const client = new Anthropic({
  apiKey: 'not-needed',
  baseURL: `${window.location.origin}/api/ai`,
  dangerouslyAllowBrowser: true,
})

// ── ELK layout ────────────────────────────────────────────────────────────────
const elk = new ELK()
const NODE_W = 220
const NODE_H = 160

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function applyElkLayout(nodes: any[], edges: any[], heightHints: Map<string, number>): Promise<any[]> {
  if (nodes.length === 0) return nodes
  const elkGraph = {
    id: "elk-container",
    layoutOptions: {
      "elk.algorithm": "mrtree",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "80",
      "elk.spacing.edgeNode": "60",
    },
    children: nodes.map((n) => ({ id: n.id, width: NODE_W, height: heightHints.get(n.id) ?? NODE_H })),
    edges: edges
      .filter((e) => nodes.some((n) => n.id === e.source) && nodes.some((n) => n.id === e.target))
      .map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  }
  const layout = await elk.layout(elkGraph)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const posMap = new Map((layout.children ?? []).map((n: any) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]))
  return nodes.map((n) => ({ ...n, position: posMap.get(n.id) ?? n.position }))
}

// ── AI tools ──────────────────────────────────────────────────────────────────
const AI_TOOLS: Anthropic.Tool[] = [
  {
    name: "add_project",
    description:
      "Create a top-level cause pillar directly under the giving-mission root. " +
      "The pillar MUST be a concrete, specific dimension of the donor's mission and chosen cause areas — " +
      "not a generic philanthropy category. " +
      "Read the root node's text and description before calling this tool and make sure every pillar reflects a meaningful part of that specific giving mission. " +
      "Never use add_node to attach something to the mission root.",
    input_schema: {
      type: "object" as const,
      properties: {
        id: { type: "string", description: "Unique kebab-case ID" },
        text: { type: "string", description: "Short label (≤5 words) — must reference the topic domain" },
        description: { type: "string", description: "One-line body (≤15 words) — explains how this project relates to the root topic" },
        color: { type: "string", description: "Hex accent color" },
      },
      required: ["id", "text", "description", "color"],
    },
  },
  {
    name: "add_node",
    description:
      "Add a child node under an existing project node or detail node. Never use this to connect to the topic root — use add_project for that.",
    input_schema: {
      type: "object" as const,
      properties: {
        id: { type: "string", description: "Unique kebab-case ID" },
        text: { type: "string", description: "Short label (≤5 words)" },
        description: { type: "string", description: "One-line body (≤15 words)" },
        color: { type: "string", description: "Hex accent color" },
        connections: {
          type: "array",
          items: { type: "string" },
          description: "Parent node IDs — must be project or detail nodes, never 'root'",
        },
      },
      required: ["id", "text", "description", "color", "connections"],
    },
  },
  {
    name: "edit_node",
    description: "Update the text, description, or color of any existing node.",
    input_schema: {
      type: "object" as const,
      properties: {
        id: { type: "string", description: "ID of the node to edit" },
        text: { type: "string", description: "New short label (≤5 words)" },
        description: { type: "string", description: "New one-line body (≤15 words)" },
        color: { type: "string", description: "New hex accent color" },
      },
      required: ["id"],
    },
  },
  {
    name: "remove_node",
    description: "Remove a node and all its descendants",
    input_schema: {
      type: "object" as const,
      properties: { id: { type: "string" } },
      required: ["id"],
    },
  },
]

const SYSTEM_PROMPT = `You are the Legato giving-plan advisor (from LBBW). You help a donor turn their philanthropic mission into a clear, visual giving strategy via tool calls.

## Tools
- add_project: level-1 cause pillar directly under root. Must be mission-specific (see below).
- add_node: child of a pillar or detail node. Never connects to root.
- edit_node: updates text, description, or color of any existing node.
- remove_node: deletes a node and all its descendants.

## Hierarchy
  Level 0 — root (id="root"): the donor's giving mission. Read its text + description carefully.
  Level 1 — PILLAR nodes (add_project): the donor's core cause areas / focus pillars.
  Level 2+ — DETAIL nodes (add_node): specific projects, funding allocations, recurring gifts, impact milestones under a pillar.

## add_project — strong mission correlation
Before calling add_project, read the root node's text and description.
Every pillar must be a named, concrete part of that exact giving mission — derived from the donor's values and cause areas.
BAD (generic): "Donations", "Charity", "Good Causes"
GOOD for "Climate & education in Baden-Württemberg": "Local Reforestation", "School Scholarships", "Clean-Energy Grants"
If the mission mentions a cause, region, or value — the pillar names must reflect it.

## Behavior — read carefully, these cases are mutually exclusive

Case 1 — User asks to add ONE specific pillar ("add a climate pillar", "create an education focus"):
  → Call add_project ONCE for that single pillar.
  → Then call add_node 3–5 times to add detail nodes (projects, allocations, milestones) under it.
  → Do NOT call add_project multiple times. One pillar = one add_project call.

Case 2 — User asks to map/plan the whole mission ("build my giving plan", "map out my strategy"):
  → Call add_project 3–5 times to create distinct cause pillars.
  → Do NOT call add_node unless explicitly asked to go deeper.

Case 3 — Focused node is set:
  → Use add_node only, with connections: [focused-node-id]. Never call add_project.

Case 4 — Edit request:
  → Call edit_node with only the fields that change.

## Formatting
- text ≤ 5 words. description ≤ 15 words.
- Vivid distinct hex colors; same hue family within a branch.

## Replies
1–2 sentences. State what you did. No preamble, no markdown lists.`

const nodeTypes = { researchNode: ResearchNode }

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

// ── Per-topic graph persistence (survives component unmount) ─────────────────
interface PersistedGraph {
  nodeDataMap: Map<string, ResearchNodeData>
  edges: Edge[]
  knownNodeIds: Set<string>
  positions: Map<string, { x: number; y: number }>
  chat: ChatMessage[]
  conversation: Anthropic.MessageParam[]
}
const persistedGraphs = new Map<string, PersistedGraph>()

function makeRootNodeData(topicId: string | null): ResearchNodeData {
  const topic = topicId ? topicById[topicId] : null
  return {
    id: "root",
    text: topic?.title ?? "Research Planning",
    description: topic?.description ?? "Start by asking the assistant to map out your research.",
    color: "#6366f1",
    isRoot: true,
  }
}

const INITIAL_CHAT: ChatMessage[] = [{
  role: "assistant",
  content: "I'm your research planning assistant. Tell me what to explore and I'll build out the graph.",
}]

// ── Page ──────────────────────────────────────────────────────────────────────
export function ResearchPage() {
  const plannedTopicId = useAppStore((s) => s.plannedTopicId)
  const setSelectedProjectId = useAppStore((s) => s.setSelectedProjectId)
  const setCurrentPhase = useAppStore((s) => s.setCurrentPhase)

  const activeTopicId = plannedTopicId

  const [nodeDataMap, setNodeDataMap] = useState<Map<string, ResearchNodeData>>(
    () => {
      const p = activeTopicId ? persistedGraphs.get(activeTopicId) : null
      return p?.nodeDataMap ?? new Map([["root", makeRootNodeData(activeTopicId)]])
    }
  )
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<ResearchNodeData>([])
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState<Edge>(
    (activeTopicId ? persistedGraphs.get(activeTopicId)?.edges : undefined) ?? []
  )
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>(
    () => {
      const p = activeTopicId ? persistedGraphs.get(activeTopicId) : null
      return p?.chat ?? INITIAL_CHAT
    }
  )
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const conversationRef = useRef<Anthropic.MessageParam[]>(
    activeTopicId ? (persistedGraphs.get(activeTopicId)?.conversation ?? []) : []
  )
  const knownNodeIds = useRef<Set<string>>(
    activeTopicId
      ? (persistedGraphs.get(activeTopicId)?.knownNodeIds ?? new Set(["root"]))
      : new Set(["root"])
  )

  const memoNodeTypes = useMemo(() => ({ ...nodeTypes }), [])

  // Actual DOM heights measured by ReactFlow — used by ELK to avoid overlap
  const measuredHeightsRef = useRef<Map<string, number>>(new Map())
  // Incremented whenever measured heights change, triggering a re-layout pass
  const [relayoutTick, setRelayoutTick] = useState(0)

  // Persists ELK-computed positions so re-renders don't reset them to {0,0}
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(
    activeTopicId ? (persistedGraphs.get(activeTopicId)?.positions ?? new Map()) : new Map()
  )

  // Keep a ref so the save effect always writes to the CURRENT topic's key,
  // even when the effect fires due to data changes after a topic switch.
  const activeTopicIdRef = useRef(activeTopicId)
  activeTopicIdRef.current = activeTopicId

  // Save graph state to module-level store on every meaningful change.
  // Intentionally omits activeTopicId from deps so switching topics doesn't
  // save the old topic's data under the new topic's key.
  useEffect(() => {
    const id = activeTopicIdRef.current
    if (!id) return
    persistedGraphs.set(id, {
      nodeDataMap,
      edges: rfEdges,
      knownNodeIds: knownNodeIds.current,
      positions: positionsRef.current,
      chat,
      conversation: conversationRef.current,
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeDataMap, rfEdges, chat])

  // Restore (or initialize) graph state when active topic switches
  useEffect(() => {
    if (!activeTopicId) return
    const p = persistedGraphs.get(activeTopicId)
    if (p) {
      setNodeDataMap(p.nodeDataMap)
      setRfEdges(p.edges)
      setChat(p.chat)
      knownNodeIds.current = p.knownNodeIds
      positionsRef.current = p.positions
      conversationRef.current = p.conversation
    } else {
      setNodeDataMap(new Map([["root", makeRootNodeData(activeTopicId)]]))
      setRfEdges([])
      setChat(INITIAL_CHAT)
      knownNodeIds.current = new Set(["root"])
      positionsRef.current = new Map()
      conversationRef.current = []
    }
    setSelectedNodeId(null)
  }, [activeTopicId]) // eslint-disable-line react-hooks/exhaustive-deps


  const selectNode = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id))
  }, [])

  // ── Cascade delete ────────────────────────────────────────────────────────
  const deleteNode = useCallback(
    (id: string) => {
      if (id === "root") return
      setRfEdges((edges) => {
        const toDelete = new Set<string>([id])
        const queue = [id]
        while (queue.length) {
          const cur = queue.shift()!
          for (const e of edges) {
            if (e.source === cur && !toDelete.has(e.target)) {
              toDelete.add(e.target)
              queue.push(e.target)
            }
          }
        }
        for (const nid of toDelete) {
          knownNodeIds.current.delete(nid)
          positionsRef.current.delete(nid)
        }
        setNodeDataMap((prev) => {
          const next = new Map(prev)
          for (const nid of toDelete) next.delete(nid)
          return next
        })
        setSelectedNodeId((prev) => (prev && toDelete.has(prev) ? null : prev))
        return edges.filter((e) => !toDelete.has(e.source) && !toDelete.has(e.target))
      })
    },
    [setRfEdges]
  )

  // ── Layout effect — single source of truth ────────────────────────────────
  // Builds rfNodes fresh from nodeDataMap (never reads stale rfNodes state),
  // preserves positions via positionsRef, then runs ELK.
  useEffect(() => {
    // Compute depth (BFS from root) to identify project-level nodes (depth=1)
    const depthMap = new Map<string, number>([["root", 0]])
    const q = ["root"]
    while (q.length) {
      const cur = q.shift()!
      const d = depthMap.get(cur)!
      for (const e of rfEdges) {
        if (e.source === cur && !depthMap.has(e.target)) {
          depthMap.set(e.target, d + 1)
          q.push(e.target)
        }
      }
    }

    const openCompanion = () => {
      // Unlock Phase 4 by ensuring selectedProjectId is set.
      // Don't override if the user already picked a specific project via Select.
      if (!useAppStore.getState().selectedProjectId) {
        setSelectedProjectId("project-06")
      }
      setCurrentPhase(4)
    }

    const nodes: Node<ResearchNodeData>[] = [...nodeDataMap.values()].map((data) => {
      const depth = depthMap.get(data.id) ?? 0
      const isProject = depth === 1
      return {
        id: data.id,
        type: "researchNode",
        position: positionsRef.current.get(data.id) ?? { x: 0, y: 0 },
        data: {
          ...data,
          isSelected: false,
          isProject,
          onDelete: deleteNode,
          onSelect: selectNode,
          onOpenCompanion: isProject ? openCompanion : undefined,
        },
      }
    })
    applyElkLayout(nodes, rfEdges, measuredHeightsRef.current).then((laid) => {
      for (const n of laid) positionsRef.current.set(n.id, n.position)
      // Re-apply selection state after layout
      setRfNodes(laid.map((n) => ({
        ...n,
        data: { ...n.data, isSelected: n.id === selectedNodeId },
      })))
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeDataMap, rfEdges, relayoutTick])

  // ── Capture measured node heights → re-run ELK with actual sizes ─────────
  // ReactFlow emits "dimensions" changes after it measures the DOM. We store
  // the actual heights and trigger one more ELK pass so spacing is correct.
  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    let updated = false
    for (const change of changes) {
      if (change.type === "dimensions" && change.dimensions && change.dimensions.height > 0) {
        const prev = measuredHeightsRef.current.get(change.id)
        if (prev !== change.dimensions.height) {
          measuredHeightsRef.current.set(change.id, change.dimensions.height)
          updated = true
        }
      }
    }
    onNodesChange(changes)
    if (updated) setRelayoutTick((t) => t + 1)
  }, [onNodesChange])

  // ── Selection effect — update highlight without re-running layout ─────────
  useEffect(() => {
    setRfNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, isSelected: n.id === selectedNodeId },
      }))
    )
  }, [selectedNodeId, setRfNodes])

  // ── Auto-scroll chat ──────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chat])

  // ── Graph context ─────────────────────────────────────────────────────────
  const graphContext = useCallback(() => {
    const depthMap = new Map<string, number>([["root", 0]])
    const q = ["root"]
    while (q.length) {
      const cur = q.shift()!
      const d = depthMap.get(cur)!
      for (const e of rfEdges) {
        if (e.source === cur && !depthMap.has(e.target)) {
          depthMap.set(e.target, d + 1)
          q.push(e.target)
        }
      }
    }
    const levelLabel = (d: number) => (d === 0 ? "root" : d === 1 ? "project" : "detail")
    const nodes = [...nodeDataMap.values()].map(({ id, text, description, color }) => ({
      id,
      text,
      description,
      color,
      level: levelLabel(depthMap.get(id) ?? 0),
    }))
    const edges = rfEdges.map((e) => ({ source: e.source, target: e.target }))

    let ctx = ""
    if (selectedNodeId) {
      const focused = nodeDataMap.get(selectedNodeId)
      const focusedDepth = depthMap.get(selectedNodeId) ?? 0
      const parentEdge = rfEdges.find((e) => e.target === selectedNodeId)
      const parent = parentEdge ? nodeDataMap.get(parentEdge.source) : null
      ctx += `FOCUSED NODE — attach ALL new nodes as children of this node:\n`
      ctx += `  id="${focused?.id}" | level=${levelLabel(focusedDepth)} | label="${focused?.text}" | description="${focused?.description}"`
      if (parent) ctx += ` | parent="${parent.text}"`
      ctx += "\n\n"
    }
    const rootNode = nodeDataMap.get("root")
    if (rootNode) {
      ctx += `TOPIC ROOT: "${rootNode.text}" — ${rootNode.description}\n\n`
    }
    ctx += `Graph (levels: root→project→detail):\nNodes: ${JSON.stringify(nodes)}\nEdges: ${JSON.stringify(edges)}`
    return ctx
  }, [nodeDataMap, rfEdges, selectedNodeId])

  // ── Tool execution ────────────────────────────────────────────────────────
  const executeToolCall = useCallback(
    (name: string, toolInput: unknown): { success: boolean; message: string } => {
      // ── add_project: always connects to root ─────────────────────────────
      if (name === "add_project") {
        const { id, text, description, color } = toolInput as {
          id: string; text: string; description: string; color: string
        }
        knownNodeIds.current.add(id)
        setNodeDataMap((prev) => new Map(prev).set(id, { id, text, description, color }))
        setRfEdges((prev) => {
          const edgeId = `root->${id}`
          if (prev.some((e) => e.id === edgeId)) return prev
          return [...prev, { id: edgeId, source: "root", target: id, type: "smoothstep" }]
        })
        return { success: true, message: `Added project '${id}'` }
      }

      // ── add_node: connects to any non-root node ──────────────────────────
      if (name === "add_node") {
        const { id, text, description, color, connections: raw } = toolInput as {
          id: string; text: string; description: string; color: string; connections: string[]
        }
        // If focused node is set, redirect any stray connection to it
        const connections =
          selectedNodeId && selectedNodeId !== "root"
            ? raw.map((src) => (knownNodeIds.current.has(src) && src !== "root" ? src : selectedNodeId))
            : raw.filter((src) => src !== "root") // never allow direct root connection

        if (connections.length === 0)
          return { success: false, message: "add_node cannot connect to root — use add_project" }

        knownNodeIds.current.add(id)
        setNodeDataMap((prev) => new Map(prev).set(id, { id, text, description, color }))
        setRfEdges((prev) => {
          const newEdges = connections
            .filter((src) => knownNodeIds.current.has(src))
            .map((src) => ({ id: `${src}->${id}`, source: src, target: id, type: "smoothstep" }))
          const existing = new Set(prev.map((e) => e.id))
          return [...prev, ...newEdges.filter((e) => !existing.has(e.id))]
        })
        return { success: true, message: `Added node '${id}'` }
      }

      // ── edit_node: update existing node fields ───────────────────────────
      if (name === "edit_node") {
        const { id, text, description, color } = toolInput as {
          id: string; text?: string; description?: string; color?: string
        }
        if (!knownNodeIds.current.has(id))
          return { success: false, message: `Node '${id}' not found` }
        setNodeDataMap((prev) => {
          const existing = prev.get(id)
          if (!existing) return prev
          return new Map(prev).set(id, {
            ...existing,
            ...(text !== undefined && { text }),
            ...(description !== undefined && { description }),
            ...(color !== undefined && { color }),
          })
        })
        return { success: true, message: `Updated node '${id}'` }
      }

      // ── remove_node ──────────────────────────────────────────────────────
      if (name === "remove_node") {
        const { id } = toolInput as { id: string }
        if (id === "root") return { success: false, message: "Cannot remove root node" }
        deleteNode(id)
        return { success: true, message: `Removed node '${id}' and descendants` }
      }

      return { success: false, message: `Unknown tool: ${name}` }
    },
    [setRfEdges, deleteNode, selectedNodeId]
  )

  // ── AI loop ───────────────────────────────────────────────────────────────
  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput("")
    setLoading(true)
    setChat((prev) => [...prev, { role: "user", content: text }])

    conversationRef.current = [
      ...conversationRef.current,
      { role: "user", content: graphContext() + "\n\nUser request: " + text },
    ]

    let assistantText = ""
    try {
      let continueLoop = true
      while (continueLoop) {
        const response = await client.messages.create({
          model: "claude-sonnet-4-6",
          max_tokens: 4096,
          system: SYSTEM_PROMPT,
          tools: AI_TOOLS,
          messages: conversationRef.current,
        })

        const toolResults: Anthropic.ToolResultBlockParam[] = []
        for (const block of response.content) {
          if (block.type === "text") assistantText += block.text
          else if (block.type === "tool_use") {
            const result = executeToolCall(block.name, block.input)
            toolResults.push({ type: "tool_result", tool_use_id: block.id, content: result.message })
          }
        }
        conversationRef.current = [
          ...conversationRef.current,
          { role: "assistant", content: response.content },
        ]
        if (toolResults.length > 0) {
          conversationRef.current = [
            ...conversationRef.current,
            { role: "user", content: toolResults },
          ]
        }
        continueLoop = response.stop_reason === "tool_use" && toolResults.length > 0
      }
      if (assistantText) {
        setChat((prev) => [...prev, { role: "assistant", content: assistantText }])
      }
    } catch (err) {
      console.error(err)
      setChat((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Please try again." },
      ])
    } finally {
      setLoading(false)
    }
  }, [input, loading, graphContext, executeToolCall])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full w-full bg-gray-50">
      <div className="flex-1 flex flex-col">
        <div className="flex-1">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={memoNodeTypes}
          connectionLineType={ConnectionLineType.SmoothStep}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Panel position="bottom-right">
            <img src={legatoLogo} alt="Legato" className="h-6 opacity-60 pointer-events-none" />
          </Panel>
          <Controls />
        </ReactFlow>
        </div>
      </div>

      <div className="w-[400px] flex flex-col border-l border-gray-200 bg-white">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Research Assistant</h2>
          <p className="text-xs text-gray-500 mt-0.5">AI-powered graph builder</p>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {chat.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-indigo-500 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
                }`}
              >
                {msg.role === "user" ? (
                  msg.content
                ) : (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>,
                      li: ({ children }) => <li>{children}</li>,
                      code: ({ children }) => <code className="bg-gray-200 rounded px-1 text-xs font-mono">{children}</code>,
                      h1: ({ children }) => <p className="font-bold mb-1">{children}</p>,
                      h2: ({ children }) => <p className="font-bold mb-1">{children}</p>,
                      h3: ({ children }) => <p className="font-semibold mb-0.5">{children}</p>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-3 py-2">
                <span className="inline-flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="px-4 py-3 border-t border-gray-100 space-y-2">
          {selectedNodeId && (() => {
            const node = nodeDataMap.get(selectedNodeId)
            return node ? (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Focused:</span>
                <span
                  className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{ background: node.color + "22", color: node.color }}
                >
                  {node.text}
                  <button
                    onClick={() => setSelectedNodeId(null)}
                    className="ml-0.5 opacity-60 hover:opacity-100"
                  >
                    <X size={10} />
                  </button>
                </span>
              </div>
            ) : null
          })()}
          <div className="flex gap-2 items-end">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedNodeId ? "Prompt for selected node…" : "Ask me to map out projects…"}
              className="flex-1 resize-none text-sm min-h-[44px] max-h-[120px]"
              rows={1}
            />
            <Button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              size="icon"
              className="bg-indigo-500 hover:bg-indigo-600 shrink-0"
            >
              <Send size={16} />
            </Button>
          </div>
          <p className="text-xs text-gray-400">Enter to send · Shift+Enter for newline · Click a node to focus it</p>
        </div>
      </div>
    </div>
  )
}
