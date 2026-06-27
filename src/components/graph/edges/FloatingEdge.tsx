import { getBezierPath, useInternalNode } from '@xyflow/react'
import type { EdgeProps, InternalNode, Node } from '@xyflow/react'
import type { Position } from '@xyflow/react'

interface NodeWithMeasured extends InternalNode<Node> {
  measured: { width: number; height: number }
  internals: {
    positionAbsolute: { x: number; y: number }
    z: number
    userNode: Node
  }
}

function getNodeIntersection(
  intersectionNode: NodeWithMeasured,
  targetNode: NodeWithMeasured
) {
  const { width: w2, height: h2 } = intersectionNode.measured
  const pos2 = intersectionNode.internals.positionAbsolute
  const pos1 = targetNode.internals.positionAbsolute

  const w = w2 / 2
  const h = h2 / 2
  const x2 = pos2.x + w
  const y2 = pos2.y + h
  const x1 = pos1.x + targetNode.measured.width / 2
  const y1 = pos1.y + targetNode.measured.height / 2

  const xx1 = (x1 - x2) / (2 * w) - (y1 - y2) / (2 * h)
  const yy1 = (x1 - x2) / (2 * w) + (y1 - y2) / (2 * h)
  const a = 1 / (Math.abs(xx1) + Math.abs(yy1))
  const xx3 = a * xx1
  const yy3 = a * yy1
  const x = w * (xx3 + yy3) + x2
  const y = h * (-xx3 + yy3) + y2

  return { x, y }
}

function getEdgePosition(node: NodeWithMeasured, pt: { x: number; y: number }): Position {
  const nx = Math.round(node.internals.positionAbsolute.x)
  const ny = Math.round(node.internals.positionAbsolute.y)
  const px = Math.round(pt.x)
  const py = Math.round(pt.y)

  if (px <= nx + 1) return 'left' as Position
  if (px >= nx + node.measured.width - 1) return 'right' as Position
  if (py <= ny + 1) return 'top' as Position
  if (py >= ny + node.measured.height - 1) return 'bottom' as Position
  return 'top' as Position
}

interface FloatingEdgeData {
  selected?: boolean
  dimmed?: boolean
}

export function FloatingEdge({
  id,
  source,
  target,
  data,
}: EdgeProps & { data?: FloatingEdgeData }) {
  const sourceNode = useInternalNode(source) as NodeWithMeasured | undefined
  const targetNode = useInternalNode(target) as NodeWithMeasured | undefined

  if (!sourceNode || !targetNode) return null
  if (!sourceNode.measured || !targetNode.measured) return null

  const srcPt = getNodeIntersection(sourceNode, targetNode)
  const tgtPt = getNodeIntersection(targetNode, sourceNode)
  const srcPos = getEdgePosition(sourceNode, srcPt)
  const tgtPos = getEdgePosition(targetNode, tgtPt)

  const [edgePath] = getBezierPath({
    sourceX: srcPt.x,
    sourceY: srcPt.y,
    sourcePosition: srcPos,
    targetPosition: tgtPos,
    targetX: tgtPt.x,
    targetY: tgtPt.y,
  })

  const isSelected = data?.selected ?? false
  const isDimmed = data?.dimmed ?? false

  return (
    <path
      id={id}
      d={edgePath}
      fill="none"
      stroke="var(--foreground)"
      strokeWidth={isSelected ? 1.5 : 1}
      strokeOpacity={isDimmed ? 0.08 : isSelected ? 0.5 : 0.2}
      style={{ transition: 'stroke-opacity 0.3s, stroke-width 0.3s' }}
      className="react-flow__edge-path"
    />
  )
}
