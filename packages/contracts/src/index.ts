export type NodeKind = "jurisdiction" | "organization" | "unit" | "position" | "person";

export type GraphMode = "organization" | "power";

export type EvidenceSummary = {
  sourceId: string;
  publisher: string;
  title: string;
  url: string;
  locator: string;
  retrievedAt: string;
};

export type GraphNode = {
  id: string;
  slug: string;
  kind: NodeKind;
  label: string;
  shortLabel: string;
  description: string;
  category: string;
  branch: string;
  jurisdiction: string;
  validFrom: string;
  validTo: string | null;
  currentRole?: string;
  organizationSlug?: string;
  sourceIds: string[];
};

export type GraphEdge = {
  id: string;
  type: string;
  label: string;
  source: string;
  target: string;
  mode: GraphMode | "both";
  description: string;
  condition: string | null;
  legalBasis: string;
  validFrom: string;
  validTo: string | null;
  evidence: EvidenceSummary[];
};

export type SourceRecord = {
  id: string;
  publisher: string;
  title: string;
  url: string;
  type: string;
  publicationDate: string | null;
  retrievedAt: string;
  contentHash: string;
  description: string;
};

export type ChangeEvent = {
  id: string;
  type: string;
  date: string;
  title: string;
  description: string;
  nodeIds: string[];
  sourceId: string;
};

export type ReviewTask = {
  id: string;
  status: "needs_review" | "approved" | "rejected";
  priority: "high" | "medium" | "low";
  title: string;
  source: string;
  detectedAt: string;
  summary: string;
  batchId?: string | null;
};

export type MvpDataset = {
  generatedAt: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  sources: SourceRecord[];
  changes: ChangeEvent[];
  reviewTasks: ReviewTask[];
};

export type GraphResponse = {
  asOf: string;
  mode: GraphMode;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type OccupancyStatus = "confirmed" | "acting" | "vacant" | "unrecorded";

export type PortraitSummary = {
  url: string;
  sourceUrl: string;
  credit: string;
  alt: string;
};

export type OccupancySummary = {
  id: string;
  personId: string | null;
  personSlug: string | null;
  personLabel: string | null;
  positionId: string;
  positionSlug: string;
  positionLabel: string;
  organizationId: string;
  status: OccupancyStatus;
  validFrom: string | null;
  validTo: string | null;
  portrait: PortraitSummary | null;
};

export type PowerMapCounts = {
  children: number;
  positions: number;
  people: number;
  relationships: number;
};

export type PowerMapNode = GraphNode & {
  parentId: string | null;
  hierarchyDepth: number;
  expandable: boolean;
  counts: PowerMapCounts;
  occupancy: OccupancySummary | null;
  portrait: PortraitSummary | null;
  metadata: Record<string, string | number | boolean | null>;
};

export type PowerMapGroup = {
  id: string;
  label: string;
  branch: string;
  parentId: string | null;
  childCount: number;
  kinds: NodeKind[];
  expanded: boolean;
};

export type PowerMapRelationship = Omit<GraphEdge, "evidence"> & {
  relationshipClass: "structure" | "power" | "competence" | "accountability" | "tenure";
  hasEvidence: boolean;
  sourceLabel?: string;
  targetLabel?: string;
};

export type PowerMapStats = {
  organizations: number;
  positions: number;
  people: number;
  vacancies: number;
  relationships: number;
};

export type PowerMapResponse = {
  asOf: string;
  root: string | null;
  nodes: PowerMapNode[];
  groups: PowerMapGroup[];
  relationships: PowerMapRelationship[];
  ancestors: PowerMapNode[];
  stats: PowerMapStats;
  nextCursor: string | null;
};

export type NodeContextResponse = {
  asOf: string;
  node: PowerMapNode;
  occupancies: OccupancySummary[];
  relationships: Array<PowerMapRelationship & { evidence: EvidenceSummary[] }>;
  changes: ChangeEvent[];
};

export type ReviewBatch = {
  id: string;
  adapter: string;
  status: string;
  title: string;
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  published: number;
  createdAt: string;
};
