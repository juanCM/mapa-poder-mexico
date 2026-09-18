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
  { branch: "executive", label: "Poder Ejecutivo", start: -78, end: 42, color: "var(--map-executive)" },
  { branch: "legislative", label: "Poder Legislativo", start: 51, end: 127, color: "var(--map-legislative)" },
  { branch: "judicial", label: "Poder Judicial", start: 136, end: 212, color: "var(--map-judicial)" },
  { branch: "independent", label: "Órganos autónomos", start: 221, end: 273, color: "var(--map-independent)" }
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
  const children = nodes
    .filter((node) => node.id !== center?.id)
    .sort((a, b) => a.label.localeCompare(b.label, "es"));
  const ordered = center ? [center, ...children] : children;
  const capacity = 92;
  return ordered.map((node) => {
    if (node.id === center?.id) return { ...node, x: MAP_CENTER, y: MAP_CENTER, angle: 0, radius: 0, compact: false };
    const index = children.findIndex((item) => item.id === node.id);
    const ring = Math.floor(index / capacity);
    const ringItems = children.slice(ring * capacity, (ring + 1) * capacity);
    const ringIndex = index - ring * capacity;
    const radius = 188 + ring * 42;
    const angle = (ringIndex / Math.max(ringItems.length, 1)) * 360;
    return { ...node, ...polar(angle, radius), angle, radius, compact: children.length > 55 };
  });
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
    branchNodes.forEach((node, index) => {
      const angle = sector.start + 6 + ((sector.end - sector.start - 12) * (index + 0.5)) / Math.max(branchNodes.length, 1);
      const radius = index % 2 === 0 ? 282 : 348;
      result.push({ ...node, ...polar(angle, radius), angle, radius, compact: branchNodes.length > 18 });
    });
  }

  const centerNodes = uniqueNodes(nodes.filter((node) => node.branch === "state" || node.slug === "ciudadania"));
  centerNodes.forEach((node) => result.push({ ...node, x: MAP_CENTER, y: MAP_CENTER, angle: 0, radius: 0, compact: false }));
  return result;
}
