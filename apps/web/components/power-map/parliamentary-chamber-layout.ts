import type { PowerMapNode } from "@mapa/contracts";

export type ParliamentarySeat = {
  node: PowerMapNode;
  x: number;
  y: number;
  radius: number;
  group: string;
  color: string;
};

export type ParliamentaryGroup = {
  label: string;
  count: number;
  color: string;
};

const knownColors: Array<[RegExp, string]> = [
  [/\bPAN\b|ACCION NACIONAL/, "#4169e1"],
  [/\bPRI\b|REVOLUCIONARIO INSTITUCIONAL/, "#df3945"],
  [/MORENA/, "#a52b43"],
  [/\bPVEM\b|VERDE ECOLOGISTA/, "#63c783"],
  [/MOVIMIENTO CIUDADANO|\bMC\b/, "#f08a2c"],
  [/\bPT\b|PARTIDO DEL TRABAJO/, "#e04a3f"],
  [/\bPRD\b|REVOLUCION DEMOCRATICA/, "#e7bd26"]
];

export function parliamentaryGroup(node: PowerMapNode) {
  const value = node.metadata.parliamentaryGroup;
  return typeof value === "string" && value.trim() ? value.trim() : "Sin grupo registrado";
}

export function parliamentaryColor(group: string) {
  const normalized = group.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleUpperCase("es");
  const known = knownColors.find(([pattern]) => pattern.test(normalized));
  if (known) return known[1];
  if (normalized === "SIN GRUPO REGISTRADO") return "#777f79";
  let hash = 0;
  for (const character of normalized) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360} 48% 52%)`;
}

export function legislativeSeats(nodes: PowerMapNode[]) {
  return nodes.filter((node) => node.kind === "position" && (
    node.category === "legislative_seat" || node.metadata.positionType === "legislative_seat"
  ));
}

export function layoutParliamentarySeats(nodes: PowerMapNode[]): { seats: ParliamentarySeat[]; groups: ParliamentaryGroup[] } {
  const sorted = legislativeSeats(nodes).sort((a, b) => {
    const groupOrder = parliamentaryGroup(a).localeCompare(parliamentaryGroup(b), "es");
    if (groupOrder) return groupOrder;
    const seatA = typeof a.metadata.seatNumber === "number" ? a.metadata.seatNumber : Number.MAX_SAFE_INTEGER;
    const seatB = typeof b.metadata.seatNumber === "number" ? b.metadata.seatNumber : Number.MAX_SAFE_INTEGER;
    return seatA - seatB || a.label.localeCompare(b.label, "es");
  });
  if (!sorted.length) return { seats: [], groups: [] };

  const rowCount = sorted.length <= 150 ? 6 : 10;
  const innerRadius = sorted.length <= 150 ? 150 : 135;
  const outerRadius = sorted.length <= 150 ? 380 : 402;
  const radii = Array.from({ length: rowCount }, (_, index) => (
    innerRadius + ((outerRadius - innerRadius) * index) / Math.max(rowCount - 1, 1)
  ));
  const weightTotal = radii.reduce((sum, radius) => sum + radius, 0);
  const rawCounts = radii.map((radius) => (sorted.length * radius) / weightTotal);
  const rowCounts = rawCounts.map(Math.floor);
  let remainder = sorted.length - rowCounts.reduce((sum, count) => sum + count, 0);
  rawCounts
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction)
    .forEach(({ index }) => {
      if (remainder > 0) {
        rowCounts[index] += 1;
        remainder -= 1;
      }
    });

  const slots = radii.flatMap((radius, row) => {
    const count = rowCounts[row];
    const inset = Math.min(.14, 1.8 / Math.max(count, 1));
    return Array.from({ length: count }, (_, index) => {
      const angle = Math.PI + inset + ((Math.PI - inset * 2) * (index + .5)) / count;
      return {
        x: 460 + Math.cos(angle) * radius,
        y: 665 + Math.sin(angle) * radius,
        angle,
        radius
      };
    });
  }).sort((a, b) => a.angle - b.angle || b.radius - a.radius);

  const seatRadius = sorted.length <= 150 ? 10.5 : 6.2;
  const seats = sorted.map((node, index) => {
    const group = parliamentaryGroup(node);
    return { node, x: slots[index].x, y: slots[index].y, radius: seatRadius, group, color: parliamentaryColor(group) };
  });
  const grouped = new Map<string, ParliamentaryGroup>();
  for (const seat of seats) {
    const current = grouped.get(seat.group);
    grouped.set(seat.group, { label: seat.group, count: (current?.count ?? 0) + 1, color: seat.color });
  }
  return { seats, groups: [...grouped.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "es")) };
}
