import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactFlow, {
  Background,
  Controls,
  Panel,
  useNodesState,
  useEdgesState,
  ConnectionLineType,
  type Node,
} from "reactflow";
import { AnimatePresence } from "framer-motion";
import legatoLogo from "@/assets/legato.svg";
import { Bookmark } from "lucide-react";
import { TopicViewDetailPanel } from "../TopicViewDetailPanel";
import "reactflow/dist/style.css";
import ELK from "elkjs/lib/elk.bundled.js";
import topicsData from "../../../mock-data/topics.json";
import advisorsData from "../../../mock-data/advisors.json";
import supervisorsData from "../../../mock-data/supervisors.json";
import foundationsData from "../../../mock-data/foundations.json";
import companiesData from "../../../mock-data/companies.json";
import fieldsData from "../../../mock-data/fields.json";
import projectsData from "../../../mock-data/projects.json";
import TopicNode from "../nodes/TopicNode";
import AdvisorNode from "../nodes/AdvisorNode";
import SupervisorNode from "../nodes/SupervisorNode";
import FoundationNode from "../nodes/FoundationNode";
import CompanyNode from "../nodes/CompanyNode";
import ProjectNode from "../nodes/ProjectNode";
import type { Topic } from "../../types/topic";
import type { Advisor, Company } from "../../types/booking";
import type { Supervisor, Foundation, Project } from "../../types/entities";

// ─── Context ──────────────────────────────────────────────────────────────────

export const ActiveNodeContext = createContext<string | null>(null);
export function useActiveNodeId() {
  return useContext(ActiveNodeContext);
}

// ─── Node types & dimensions ──────────────────────────────────────────────────

const nodeTypes = {
  topicNode: TopicNode,
  advisorNode: AdvisorNode,
  supervisorNode: SupervisorNode,
  foundationNode: FoundationNode,
  companyNode: CompanyNode,
  projectNode: ProjectNode,
};

const NODE_DIMENSIONS: Record<string, { width: number; height: number }> = {
  topicNode: { width: 420, height: 200 },
  projectNode: { width: 320, height: 160 },
  advisorNode: { width: 320, height: 160 },
  supervisorNode: { width: 320, height: 180 },
  companyNode: { width: 320, height: 140 },
  foundationNode: { width: 320, height: 130 },
};

// ─── ELK layout ───────────────────────────────────────────────────────────────

const elk = new ELK();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function applyElkLayout(nodes: any[], edges: any[]): Promise<any[]> {
  const visibleNodes = nodes.filter((n) => !n.hidden);
  const visibleEdges = edges.filter((e) => !e.hidden);

  const elkGraph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "80",
      "elk.layered.spacing.nodeNodeBetweenLayers": "160",
      "elk.spacing.edgeNode": "60",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    },
    children: visibleNodes.map((n) => ({
      id: n.id,
      width: NODE_DIMENSIONS[n.type]?.width ?? 320,
      height: NODE_DIMENSIONS[n.type]?.height ?? 180,
    })),
    edges: visibleEdges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const layout = await elk.layout(elkGraph);
  const positionMap = new Map(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (layout.children ?? []).map((n: any) => [
      n.id,
      { x: n.x ?? 0, y: n.y ?? 0 },
    ]),
  );

  return nodes.map((n) => ({
    ...n,
    position: positionMap.get(n.id) ?? n.position,
  }));
}

// ─── Graph builder ────────────────────────────────────────────────────────────

function resolveFields(ids: string[]) {
  return ids.map((id) => fieldsData.find((f) => f.id === id)?.name ?? id);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildGraph(topic: Topic): {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  nodes: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  edges: any[];
  projectNodeMap: Map<string, string>;
  projectEdgeSet: Set<string>;
  topicChildIds: Set<string>;
  topicEdgeSet: Set<string>;
} {
  const nodeIds = new Set<string>([topic.id]);
  const projectNodeMap = new Map<string, string>();
  const projectEdgeSet = new Set<string>();
  const topicChildIds = new Set<string>();
  const topicEdgeSet = new Set<string>();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodes: any[] = [
    {
      id: topic.id,
      type: "topicNode",
      position: { x: 0, y: 0 },
      data: { ...topic, fieldNames: resolveFields(topic.fieldIds) },
    },
  ];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const edges: any[] = [];

  if (topic.companyId) {
    const company = (companiesData as Company[]).find(
      (c) => c.id === topic.companyId,
    );
    if (company) {
      nodeIds.add(company.id);
      topicChildIds.add(company.id);
      nodes.push({ id: company.id, type: "companyNode", position: { x: 0, y: 0 }, data: company });
      const edgeId = `${topic.id}-${company.id}`;
      topicEdgeSet.add(edgeId);
      edges.push({ id: edgeId, source: topic.id, target: company.id });
    }
  }

  if (topic.foundationId) {
    const foundation = (foundationsData as Foundation[]).find(
      (u) => u.id === topic.foundationId,
    );
    if (foundation) {
      nodeIds.add(foundation.id);
      topicChildIds.add(foundation.id);
      nodes.push({ id: foundation.id, type: "foundationNode", position: { x: 0, y: 0 }, data: foundation });
      const edgeId = `${topic.id}-${foundation.id}`;
      topicEdgeSet.add(edgeId);
      edges.push({ id: edgeId, source: topic.id, target: foundation.id });
    }
  }

  topic.supervisorIds.forEach((supervisorId) => {
    const supervisor = (supervisorsData as Supervisor[]).find((s) => s.id === supervisorId);
    if (supervisor) {
      nodeIds.add(supervisor.id);
      topicChildIds.add(supervisor.id);
      nodes.push({
        id: supervisor.id,
        type: "supervisorNode",
        position: { x: 0, y: 0 },
        data: { ...supervisor, fieldNames: resolveFields(supervisor.fieldIds) },
      });
      const edgeId = `${topic.id}-${supervisor.id}`;
      topicEdgeSet.add(edgeId);
      edges.push({ id: edgeId, source: topic.id, target: supervisor.id });
    }
  });

  topic.advisorIds.forEach((advisorId) => {
    const advisor = (advisorsData as Advisor[]).find((e) => e.id === advisorId);
    if (advisor) {
      nodeIds.add(advisor.id);
      topicChildIds.add(advisor.id);
      nodes.push({
        id: advisor.id,
        type: "advisorNode",
        position: { x: 0, y: 0 },
        data: { ...advisor, fieldNames: resolveFields(advisor.fieldIds) },
      });
      const edgeId = `${topic.id}-${advisor.id}`;
      topicEdgeSet.add(edgeId);
      edges.push({ id: edgeId, source: topic.id, target: advisor.id });
    }
  });

  const projects = (projectsData as Project[]).filter((p) => p.topicId === topic.id);
  projects.forEach((project) => {
    nodeIds.add(project.id);
    topicChildIds.add(project.id);
    nodes.push({ id: project.id, type: "projectNode", position: { x: 0, y: 0 }, data: project });
    const topicProjectEdgeId = `${topic.id}-${project.id}`;
    topicEdgeSet.add(topicProjectEdgeId);
    edges.push({ id: topicProjectEdgeId, source: topic.id, target: project.id });

    const addProjectEdge = (edgeId: string, source: string, target: string) => {
      projectEdgeSet.add(edgeId);
      edges.push({ id: edgeId, source, target });
    };

    if (project.companyId) {
      if (!nodeIds.has(project.companyId)) {
        const company = (companiesData as Company[]).find((c) => c.id === project.companyId);
        if (company) {
          nodeIds.add(company.id);
          projectNodeMap.set(company.id, project.id);
          nodes.push({ id: company.id, type: "companyNode", position: { x: 0, y: 0 }, data: company });
        }
      }
      if (nodeIds.has(project.companyId)) {
        addProjectEdge(`${project.id}-${project.companyId}`, project.id, project.companyId);
      }
    }

    if (project.foundationId) {
      if (!nodeIds.has(project.foundationId)) {
        const foundation = (foundationsData as Foundation[]).find((u) => u.id === project.foundationId);
        if (foundation) {
          nodeIds.add(foundation.id);
          projectNodeMap.set(foundation.id, project.id);
          nodes.push({ id: foundation.id, type: "foundationNode", position: { x: 0, y: 0 }, data: foundation });
        }
      }
      if (nodeIds.has(project.foundationId)) {
        addProjectEdge(`${project.id}-${project.foundationId}`, project.id, project.foundationId);
      }
    }

    project.supervisorIds.forEach((supervisorId) => {
      if (!nodeIds.has(supervisorId)) {
        const supervisor = (supervisorsData as Supervisor[]).find((s) => s.id === supervisorId);
        if (supervisor) {
          nodeIds.add(supervisor.id);
          projectNodeMap.set(supervisor.id, project.id);
          nodes.push({
            id: supervisor.id,
            type: "supervisorNode",
            position: { x: 0, y: 0 },
            data: { ...supervisor, fieldNames: resolveFields(supervisor.fieldIds) },
          });
        }
      }
      if (nodeIds.has(supervisorId)) {
        addProjectEdge(`${project.id}-${supervisorId}`, project.id, supervisorId);
      }
    });

    project.advisorIds.forEach((advisorId) => {
      if (!nodeIds.has(advisorId)) {
        const advisor = (advisorsData as Advisor[]).find((e) => e.id === advisorId);
        if (advisor) {
          nodeIds.add(advisor.id);
          projectNodeMap.set(advisor.id, project.id);
          nodes.push({
            id: advisor.id,
            type: "advisorNode",
            position: { x: 0, y: 0 },
            data: { ...advisor, fieldNames: resolveFields(advisor.fieldIds) },
          });
        }
      }
      if (nodeIds.has(advisorId)) {
        addProjectEdge(`${project.id}-${advisorId}`, project.id, advisorId);
      }
    });
  });

  return { nodes, edges, projectNodeMap, projectEdgeSet, topicChildIds, topicEdgeSet };
}

// ─── Multi-graph builder ──────────────────────────────────────────────────────
// Child nodes use their original IDs so shared entities (same foundation,
// supervisor, etc.) across multiple topic trees are merged into one node.

function buildMultiGraph(topicIds: string[]) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const allNodesMap = new Map<string, any>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const allEdges: any[] = [];

  // nodeId -> Set<topicId>  (direct topic children; shared nodes belong to multiple topics)
  const nodeParentTopics = new Map<string, Set<string>>();
  // projectId -> topicId
  const projectToTopic = new Map<string, string>();
  // nodeId -> projectId  (project-specific nodes)
  const projectNodeMap = new Map<string, string>();
  // edge ids belonging to projects
  const projectEdgeSet = new Set<string>();
  // topicId -> set of edge ids (topic->direct-child edges)
  const topicEdgeSets = new Map<string, Set<string>>();

  for (const topicId of topicIds) {
    const topic = (topicsData as Topic[]).find((t) => t.id === topicId);
    if (!topic) continue;

    const result = buildGraph(topic);

    // Add nodes by original ID, deduplicating shared entities
    for (const node of result.nodes) {
      if (!allNodesMap.has(node.id)) {
        allNodesMap.set(node.id, node);
      }
    }

    // Prefix edge IDs only (to keep them unique), source/target use original IDs
    for (const edge of result.edges) {
      const prefixedEdgeId = `${topicId}__${edge.id}`;
      allEdges.push({ ...edge, id: prefixedEdgeId });
      if (result.projectEdgeSet.has(edge.id)) {
        projectEdgeSet.add(prefixedEdgeId);
      }
    }

    // Direct topic children (node may belong to multiple topics)
    for (const childId of result.topicChildIds) {
      if (!nodeParentTopics.has(childId)) {
        nodeParentTopics.set(childId, new Set());
      }
      nodeParentTopics.get(childId)!.add(topicId);
    }

    // Projects → topic mapping
    for (const [nodeId, projId] of result.projectNodeMap) {
      projectNodeMap.set(nodeId, projId);
    }

    const topicEdgeSet = new Set<string>();
    for (const edgeId of result.topicEdgeSet) {
      topicEdgeSet.add(`${topicId}__${edgeId}`);
    }
    topicEdgeSets.set(topicId, topicEdgeSet);

    // Build projectToTopic from projectsData
    for (const project of (projectsData as Project[]).filter((p) => p.topicId === topicId)) {
      projectToTopic.set(project.id, topicId);
    }
  }

  return {
    nodes: Array.from(allNodesMap.values()),
    edges: allEdges,
    nodeParentTopics,
    projectToTopic,
    projectNodeMap,
    projectEdgeSet,
    topicEdgeSets,
  };
}

// ─── MultiTopicFlow component ─────────────────────────────────────────────────

export function MultiTopicFlow({ topicIds }: { topicIds: string[] }) {
  const {
    nodes: allNodes,
    edges: allEdges,
    nodeParentTopics,
    projectToTopic,
    projectNodeMap,
    projectEdgeSet,
    topicEdgeSets,
  } = useMemo(() => buildMultiGraph(topicIds), [topicIds]);

  // React Flow warns if `nodeTypes` is a different object reference between renders.
  // Keep the mapping referentially stable.
  const memoNodeTypes = useMemo(() => ({ ...nodeTypes }), []);

  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfInstanceRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [activeNode, setActiveNode] = useState<{ type: string; data: any } | null>(null);
  const isFirstLayout = useRef(true);

  // Reset expand state when topicIds change
  useEffect(() => {
    setExpandedTopics(new Set());
    setExpandedProjects(new Set());
    isFirstLayout.current = true;
  }, [topicIds.join(",")]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setActiveNode((prev) =>
      prev && prev.data.id === node.data.id ? null : { type: node.type!, data: node.data },
    );
  }, []);

  const toggleTopic = useCallback((topicId: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicId)) next.delete(topicId);
      else next.add(topicId);
      return next;
    });
  }, []);

  const toggleProject = useCallback((projectId: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
  }, []);

  const { visibleNodes, visibleEdges } = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const visibleNodes = allNodes.map((node: any) => {
      if (node.type === "topicNode") {
        const isExpanded = expandedTopics.has(node.id);
        return {
          ...node,
          data: {
            ...node.data,
            expanded: isExpanded,
            onToggle: () => toggleTopic(node.id),
          },
        };
      }

      if (node.type === "projectNode") {
        const parentTopicId = projectToTopic.get(node.id);
        const isParentExpanded = parentTopicId ? expandedTopics.has(parentTopicId) : false;
        const isExpanded = expandedProjects.has(node.id);
        return {
          ...node,
          hidden: !isParentExpanded,
          data: {
            ...node.data,
            expanded: isExpanded,
            onToggle: () => toggleProject(node.id),
          },
        };
      }

      // Direct topic children (a shared node is visible if any of its parent topics is expanded)
      const parentTopicIds = nodeParentTopics.get(node.id);
      if (parentTopicIds !== undefined) {
        return { ...node, hidden: ![...parentTopicIds].some((id) => expandedTopics.has(id)) };
      }

      // Project children
      const owningProject = projectNodeMap.get(node.id);
      if (owningProject !== undefined) {
        const parentTopicId = projectToTopic.get(owningProject);
        const isTopicExpanded = parentTopicId ? expandedTopics.has(parentTopicId) : false;
        const isProjectExpanded = expandedProjects.has(owningProject);
        return { ...node, hidden: !(isTopicExpanded && isProjectExpanded) };
      }

      return node;
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const visibleEdges = allEdges.map((edge: any) => {
      // Check topic->child edges (one set per topic)
      for (const [topicId, edgeSet] of topicEdgeSets) {
        if (edgeSet.has(edge.id)) {
          return { ...edge, hidden: !expandedTopics.has(topicId) };
        }
      }

      // Project edges
      if (projectEdgeSet.has(edge.id)) {
        const owningProject =
          projectNodeMap.get(edge.target) ?? projectNodeMap.get(edge.source) ?? "";
        const hidden = !expandedProjects.has(owningProject);
        return { ...edge, hidden };
      }

      return edge;
    });

    return { visibleNodes, visibleEdges };
  }, [
    allNodes,
    allEdges,
    nodeParentTopics,
    projectToTopic,
    projectNodeMap,
    projectEdgeSet,
    topicEdgeSets,
    expandedTopics,
    expandedProjects,
    toggleTopic,
    toggleProject,
  ]);

  const runLayout = useCallback(
    (fitAfter = false) => {
      const first = isFirstLayout.current;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      applyElkLayout(visibleNodes, visibleEdges).then((layoutedNodes: any[]) => {
        // Always use ELK positions so nodes move apart when new ones appear.
        const finalNodes = layoutedNodes;

        setRfNodes(finalNodes as never[]);
        setRfEdges(visibleEdges as never[]);

        if (fitAfter || first) {
          isFirstLayout.current = false;
          setTimeout(
            () => rfInstanceRef.current?.fitView({ padding: 0.5, maxZoom: 0.7, duration: 300 }),
            50,
          );
        }
      });
    },
    [visibleNodes, visibleEdges, setRfNodes, setRfEdges],
  );

  useEffect(() => {
    runLayout(false);
  }, [runLayout]);

  return (
    <ActiveNodeContext.Provider value={activeNode?.data.id ?? null}>
      <>
        <div style={{ width: "100%", height: "100%" }}>
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={memoNodeTypes}
            proOptions={{ hideAttribution: true }}
            onInit={(instance) => {
              rfInstanceRef.current = instance;
            }}
            nodesConnectable={false}
            elementsSelectable={false}
            onNodeClick={onNodeClick}
            onPaneClick={() => setActiveNode(null)}
            defaultEdgeOptions={{ type: "step" }}
            connectionLineType={ConnectionLineType.SmoothStep}
          >
            <Background />
            <Controls />
            <Panel position="bottom-right">
              <img src={legatoLogo} alt="Legato" className="h-6 opacity-60 pointer-events-none" />
            </Panel>
          </ReactFlow>
        </div>
        <AnimatePresence>
          {activeNode && (
            <TopicViewDetailPanel node={activeNode} onClose={() => setActiveNode(null)} />
          )}
        </AnimatePresence>
      </>
    </ActiveNodeContext.Provider>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

export function MultiTopicFlowEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-20 text-center space-y-3">
      <Bookmark className="size-8 text-muted-foreground/40" />
      <p className="ds-label text-muted-foreground">No bookmarks yet</p>
      <p className="ds-caption text-muted-foreground/60">
        Go to Discover and shortlist impact projects to visualise them here
      </p>
    </div>
  );
}
