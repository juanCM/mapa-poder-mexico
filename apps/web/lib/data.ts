import rawDataset from "@mapa/contracts/data/mvp.json";
import type {
  GraphEdge,
  GraphNode,
  MvpDataset,
  SourceRecord
} from "@mapa/contracts";

export const dataset = rawDataset as MvpDataset;

export function getNodeBySlug(slug: string): GraphNode | undefined {
  return dataset.nodes.find((node) => node.slug === slug);
}

export function getNodeById(id: string): GraphNode | undefined {
  return dataset.nodes.find((node) => node.id === id);
}

export function getRelationship(id: string): GraphEdge | undefined {
  return dataset.edges.find((edge) => edge.id === id);
}

export function getSource(id: string): SourceRecord | undefined {
  return dataset.sources.find((source) => source.id === id);
}

export function relationshipsForNode(id: string): GraphEdge[] {
  return dataset.edges.filter((edge) => edge.source === id || edge.target === id);
}

export function sourcesForNode(node: GraphNode): SourceRecord[] {
  return node.sourceIds
    .map(getSource)
    .filter((source): source is SourceRecord => Boolean(source));
}

export function formatDate(date: string | null): string {
  if (!date) return "Vigente";
  return new Intl.DateTimeFormat("es-MX", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC"
  }).format(new Date(`${date}T00:00:00Z`));
}

export function hrefForNode(node: GraphNode): string {
  if (node.kind === "person") return `/personas/${node.slug}`;
  return `/instituciones/${node.slug}`;
}
