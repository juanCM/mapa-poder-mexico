import type { PowerMapNode } from "@mapa/contracts";

export const MAP_SIZE = 920;
export const MAP_CENTER = MAP_SIZE / 2;

export type BranchKey = "executive" | "legislative" | "judicial" | "independent" | "state";

export type Sector = {
  branch: BranchKey;
  label: string;
  start: number;
  end: number;
  color: string;
};

export type PositionedNode = PowerMapNode & { x: number; y: number; angle: number; radius: number; compact: boolean };

/**
 * The API normally returns unique nodes, but a relational query can temporarily
 * repeat an entity when a node has more than one related record. Keep the SVG
 * layout a set as well, so React never receives duplicate keys.
 */
export function uniqueNodes<T extends PowerMapNode>(nodes: T[]): T[] {
  return [...new Map(nodes.map((node) => [node.id, node])).values()];
}

export const sectors: Sector[] = [
  { branch: "executive", label: "Poder Ejecutivo", start: -84, end: 18, color: "var(--map-executive)" },
  { branch: "legislative", label: "Poder Legislativo", start: 24, end: 114, color: "var(--map-legislative)" },
  { branch: "judicial", label: "Poder Judicial", start: 120, end: 210, color: "var(--map-judicial)" },
  { branch: "independent", label: "Órganos autónomos", start: 216, end: 276, color: "var(--map-independent)" }
];

export function polar(angleDegrees: number, radius: number) {
  const angle = ((angleDegrees - 90) * Math.PI) / 180;
  return { x: MAP_CENTER + Math.cos(angle) * radius, y: MAP_CENTER + Math.sin(angle) * radius };
}

export function annularSector(start: number, end: number, innerRadius: number, outerRadius: number) {
  const p1 = polar(start, outerRadius);
  const p2 = polar(end, outerRadius);
  const p3 = polar(end, innerRadius);
  const p4 = polar(start, innerRadius);
  const large = end - start > 180 ? 1 : 0;
  return [
    `M ${p1.x} ${p1.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${large} 1 ${p2.x} ${p2.y}`,
    `L ${p3.x} ${p3.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${large} 0 ${p4.x} ${p4.y}`,
    "Z"
  ].join(" ");
}

export function labelArc(start: number, end: number, radius: number) {
  const p1 = polar(start, radius);
  const p2 = polar(end, radius);
  return `M ${p1.x} ${p1.y} A ${radius} ${radius} 0 0 1 ${p2.x} ${p2.y}`;
}

function positionExpanded(nodes: PowerMapNode[], root: string): PositionedNode[] {
  const center = nodes.find((node) => node.id === root) ?? nodes[0];
  if (!center) return [];

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const childrenByParent = new Map<string, PowerMapNode[]>();
  for (const node of nodes) {
    if (node.parentId && byId.has(node.parentId)) {
      childrenByParent.set(node.parentId, [...(childrenByParent.get(node.parentId) ?? []), node]);
    }
  }
  for (const children of childrenByParent.values()) children.sort(compareHierarchyNodes);

  const ancestors: PowerMapNode[] = [];
  const ancestorIds = new Set<string>();
  let ancestorId = center.parentId;
  while (ancestorId && byId.has(ancestorId) && !ancestorIds.has(ancestorId)) {
    const ancestor = byId.get(ancestorId)!;
    ancestors.push(ancestor);
    ancestorIds.add(ancestor.id);
    ancestorId = ancestor.parentId;
  }

  const result: PositionedNode[] = [{ ...center, x: MAP_CENTER, y: MAP_CENTER, angle: 0, radius: 0, compact: false }];
  const placed = new Set<string>([center.id]);
  const dense = nodes.length > 44;
  const families = (childrenByParent.get(center.id) ?? []).filter((node) => !ancestorIds.has(node.id));
  const reserveAncestorLane = ancestors.length > 0;
  const familyStart = reserveAncestorLane ? 46 : 0;
  const familySpan = reserveAncestorLane ? 268 : 360;
  const familyArc = familySpan / Math.max(families.length, 1);

  families.forEach((node, index) => {
    const angle = families.length === 1
      ? 180
      : familyStart + familyArc * (index + .5);
    result.push({ ...node, ...polar(angle, 205), angle, radius: 205, compact: dense });
    placed.add(node.id);
    placeDescendants(node.id, angle, familyArc * .72, 2);
  });

  ancestors.forEach((node, index) => {
    const radius = 205 + index * 145;
    result.push({ ...node, ...polar(0, radius), angle: 0, radius, compact: false });
    placed.add(node.id);
  });

  const context = nodes.filter((node) => !placed.has(node.id)).sort(compareHierarchyNodes);
  if (!families.length && !ancestors.length) {
    context.forEach((node, index) => {
      const angle = (360 * (index + .5)) / Math.max(context.length, 1);
      result.push({ ...node, ...polar(angle, 275), angle, radius: 275, compact: context.length > 18 });
    });
  } else {
    context.forEach((node, index) => {
      const angle = -38 + (76 * (index + 1)) / (context.length + 1);
      result.push({ ...node, ...polar(angle, 405), angle, radius: 405, compact: context.length > 6 });
    });
  }
  return result;

  function placeDescendants(parentId: string, parentAngle: number, availableArc: number, level: number) {
    if (level > 4) return;
    const children = (childrenByParent.get(parentId) ?? []).filter((node) => !placed.has(node.id) && !ancestorIds.has(node.id));
    const spread = Math.min(availableArc, 34);
    children.forEach((node, index) => {
      const angle = children.length === 1
        ? parentAngle
        : parentAngle - spread / 2 + (spread * (index + .5)) / children.length;
      const radius = level === 2 ? 340 : Math.min(420, 340 + (level - 1) * 65);
      result.push({ ...node, ...polar(angle, radius), angle, radius, compact: dense });
      placed.add(node.id);
      placeDescendants(node.id, angle, Math.max(availableArc / Math.max(children.length, 1), 8), level + 1);
    });
  }
}

function compareHierarchyNodes(a: PowerMapNode, b: PowerMapNode) {
  const seatA = typeof a.metadata.seatNumber === "number" ? a.metadata.seatNumber : Number.MAX_SAFE_INTEGER;
  const seatB = typeof b.metadata.seatNumber === "number" ? b.metadata.seatNumber : Number.MAX_SAFE_INTEGER;
  return seatA - seatB || a.label.localeCompare(b.label, "es") || a.id.localeCompare(b.id);
}

export function positionNodes(nodes: PowerMapNode[], root: string | null): PositionedNode[] {
  nodes = uniqueNodes(nodes);
  if (root) {
    return positionExpanded(nodes, root);
  }

  const result: PositionedNode[] = [];
  for (const sector of sectors) {
    const branchNodes = nodes
      // Ciudadanía is the semantic centre even when an imported legacy row has
      // an incorrect branch. Do not render it once in a sector and once again
      // in the centre.
      .filter((node) => node.branch === sector.branch && node.category !== "branch" && node.slug !== "ciudadania")
      .sort((a, b) => a.hierarchyDepth - b.hierarchyDepth || a.label.localeCompare(b.label, "es"));
    const branchNode = nodes.find((node) => node.branch === sector.branch && node.category === "branch");
    if (branchNode) {
      const angle = (sector.start + sector.end) / 2;
      result.push({ ...branchNode, ...polar(angle, 174), angle, radius: 174, compact: false });
    }
    const availableAngle = sector.end - sector.start - 14;
    const ringRadii = [248, 318, 386];
    const ringCapacities = ringRadii.map((radius) => Math.max(1, Math.floor((availableAngle * Math.PI / 180 * radius) / 52)));
    branchNodes.forEach((node, nodeIndex) => {
      let ring = 0;
      let ringStart = 0;
      while (ring < ringCapacities.length - 1 && nodeIndex >= ringStart + ringCapacities[ring]) {
        ringStart += ringCapacities[ring];
        ring += 1;
      }
      const ringNodes = branchNodes.slice(ringStart, ringStart + ringCapacities[ring]);
      const ringIndex = nodeIndex - ringStart;
      const angle = sector.start + 7 + (availableAngle * (ringIndex + .5)) / Math.max(ringNodes.length, 1);
      const radius = ringRadii[ring];
      result.push({ ...node, ...polar(angle, radius), angle, radius, compact: branchNodes.length > 14 });
    });
  }

  const centerNodes = uniqueNodes(nodes.filter((node) => node.branch === "state" || node.slug === "ciudadania"));
  centerNodes.forEach((node) => result.push({ ...node, x: MAP_CENTER, y: MAP_CENTER, angle: 0, radius: 0, compact: false }));
  return result;
}
