export interface KGNode {
  id: string
  type: 'donor' | 'ngo' | 'sdg' | 'foundation'
  label: string
  metadata?: Record<string, unknown>
}

export interface KGEdge {
  from: string
  to: string
  relation: 'funds' | 'aligns_with' | 'founded_by' | 'targets_sdg'
  weight: number
}

export interface KnowledgeGraph {
  nodes: KGNode[]
  edges: KGEdge[]
}

export function addNode(graph: KnowledgeGraph, node: KGNode): KnowledgeGraph {
  if (graph.nodes.find(n => n.id === node.id)) return graph
  return { ...graph, nodes: [...graph.nodes, node] }
}

export function addEdge(graph: KnowledgeGraph, edge: KGEdge): KnowledgeGraph {
  return { ...graph, edges: [...graph.edges, edge] }
}

export function queryNeighbours(graph: KnowledgeGraph, nodeId: string): KGNode[] {
  const ids = graph.edges
    .filter(e => e.from === nodeId || e.to === nodeId)
    .map(e => (e.from === nodeId ? e.to : e.from))
  return graph.nodes.filter(n => ids.includes(n.id))
}
