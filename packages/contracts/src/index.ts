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
