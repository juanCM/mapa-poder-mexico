import type {
  NodeContextResponse,
  GraphEdge,
  GraphNode,
  OccupancySummary,
  PowerMapNode,
  PowerMapRelationship,
  PowerMapResponse
} from "@mapa/contracts";
import { dataset } from "@/lib/data";

function isActive(record: { validFrom: string; validTo: string | null }, asOf: string) {
  // El contrato temporal usa rangos [inicio, fin), igual que PostgreSQL.
  return record.validFrom <= asOf && (!record.validTo || record.validTo > asOf);
}

function relationship(edge: GraphEdge, labels: Map<string, string>): PowerMapRelationship {
  return {
    id: edge.id,
    type: edge.type,
    label: edge.label,
    source: edge.source,
    target: edge.target,
    mode: edge.mode,
    relationshipClass: edge.type === "PART_OF" ? "structure" : edge.type === "HOLDS" ? "tenure" : "power",
    description: edge.description,
    condition: edge.condition,
    legalBasis: edge.legalBasis,
    validFrom: edge.validFrom,
    validTo: edge.validTo,
    hasEvidence: edge.evidence.length > 0,
    sourceLabel: labels.get(edge.source),
    targetLabel: labels.get(edge.target)
  };
}

export function createFallbackPowerMap(asOf: string, root?: string | null): PowerMapResponse {
  const nodes = dataset.nodes.filter((node) => isActive(node, asOf));
  const edges = dataset.edges.filter((edge) => isActive(edge, asOf));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const labels = new Map(nodes.map((node) => [node.id, node.label]));
  const bySlug = new Map(nodes.map((node) => [node.slug, node]));
  const parent = new Map<string, string>();
  const children = new Map<string, string[]>();

  for (const edge of edges) {
    if (["PART_OF", "HEADS", "HOLDS"].includes(edge.type)) parent.set(edge.source, edge.target);
  }
  for (const node of nodes) {
    if (node.kind === "position" && node.organizationSlug && bySlug.has(node.organizationSlug)) {
      parent.set(node.id, bySlug.get(node.organizationSlug)!.id);
    }
  }
  for (const [child, parentId] of parent) children.set(parentId, [...(children.get(parentId) ?? []), child]);

  const occupancies = new Map<string, OccupancySummary>();
  for (const edge of edges.filter((item) => item.type === "HOLDS")) {
    const person = byId.get(edge.source);
    const position = byId.get(edge.target);
    if (!person || !position) continue;
    const organizationId = parent.get(position.id) ?? position.id;
    occupancies.set(position.id, {
      id: edge.id,
      personId: person.id,
      personSlug: person.slug,
      personLabel: person.label,
      positionId: position.id,
      positionSlug: position.slug,
      positionLabel: position.label,
      organizationId,
      status: "confirmed",
      validFrom: edge.validFrom,
      validTo: edge.validTo,
      portrait: null
    });
  }

  function depth(id: string) {
    let value = 0;
    let current = id;
    const seen = new Set([id]);
    while (parent.has(current) && !seen.has(parent.get(current)!)) {
      current = parent.get(current)!;
      seen.add(current);
      value += 1;
    }
    return value;
  }

  function serialize(node: GraphNode): PowerMapNode {
    const positions = nodes.filter((item) => item.kind === "position" && parent.get(item.id) === node.id);
    const recordedOccupancy = occupancies.get(node.id) ?? (positions.length === 1 ? occupancies.get(positions[0].id) : undefined);
    const occupancy = recordedOccupancy ?? null;
    return {
      ...node,
      parentId: parent.get(node.id) ?? null,
      hierarchyDepth: depth(node.id),
      expandable: (children.get(node.id)?.length ?? 0) > 0,
      counts: {
        children: children.get(node.id)?.length ?? 0,
        positions: positions.length,
        people: positions.filter((position) => occupancies.has(position.id)).length,
        relationships: edges.filter((edge) => edge.source === node.id || edge.target === node.id).length
      },
      occupancy,
      portrait: null,
      metadata: {}
    };
  }

  const rootNode = nodes.find((node) => node.id === root || node.slug === root);
  const visible = new Set<string>();
  if (rootNode) {
    visible.add(rootNode.id);
    for (const child of children.get(rootNode.id) ?? []) {
      visible.add(child);
      if ((children.get(child)?.length ?? 0) <= 40) for (const grandchild of children.get(child) ?? []) visible.add(grandchild);
    }
    for (const edge of edges) {
      if (edge.source === rootNode.id) visible.add(edge.target);
      if (edge.target === rootNode.id) visible.add(edge.source);
    }
    let routeId = parent.get(rootNode.id);
    while (routeId && !visible.has(routeId)) {
      visible.add(routeId);
      routeId = parent.get(routeId);
    }
  } else {
    for (const node of nodes) {
      if (["estado-mexicano", "ciudadania", "organos-autonomos"].includes(node.slug) || node.category === "branch") visible.add(node.id);
    }
    for (const node of nodes.filter((item) => ["branch", "navigation_group"].includes(item.category))) {
      for (const child of children.get(node.id) ?? []) visible.add(child);
    }
  }

  const visibleNodes = nodes.filter((node) => visible.has(node.id)).map(serialize);
  const relationships = edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).map((edge) => relationship(edge, labels));
  const positions = nodes.filter((node) => node.kind === "position");
  const ancestors: PowerMapNode[] = [];
  let ancestorId = rootNode ? parent.get(rootNode.id) : undefined;
  while (ancestorId && byId.has(ancestorId)) {
    ancestors.unshift(serialize(byId.get(ancestorId)!));
    ancestorId = parent.get(ancestorId);
  }

  return {
    asOf,
    root: rootNode?.id ?? null,
    nodes: visibleNodes,
    groups: nodes.filter((node) => children.has(node.id)).map((node) => ({
      id: node.id,
      label: node.label,
      branch: node.branch,
      parentId: parent.get(node.id) ?? null,
      childCount: children.get(node.id)?.length ?? 0,
      kinds: [...new Set((children.get(node.id) ?? []).map((id) => byId.get(id)?.kind).filter(Boolean))] as GraphNode["kind"][],
      expanded: rootNode?.id === node.id
    })),
    relationships,
    ancestors,
    stats: {
      organizations: nodes.filter((node) => node.kind === "organization").length,
      positions: positions.length,
      people: nodes.filter((node) => node.kind === "person").length,
      vacancies: 0,
      relationships: edges.length
    },
    nextCursor: null
  };
}

export function createFallbackNodeContext(identifier: string, asOf: string): NodeContextResponse | null {
  const map = createFallbackPowerMap(asOf, identifier);
  const node = map.nodes.find((item) => item.id === map.root || item.slug === identifier || item.id === identifier);
  if (!node) return null;
  const labels = new Map(dataset.nodes.map((item) => [item.id, item.label]));
  const activeEdges = dataset.edges.filter((edge) => isActive(edge, asOf));
  const relationships = activeEdges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => ({
      ...relationship(edge, labels),
      evidence: edge.evidence
    }));
  const occupancies = map.nodes
    .map((item) => item.occupancy)
    .filter((item): item is OccupancySummary => Boolean(item))
    .filter((item) => [item.personId, item.positionId, item.organizationId].includes(node.id));
  return {
    asOf,
    node,
    occupancies,
    relationships,
    changes: dataset.changes.filter((change) => change.nodeIds.includes(node.id))
  };
}
