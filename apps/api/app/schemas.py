from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Evidence(ApiModel):
    source_id: str
    publisher: str
    title: str
    url: str
    locator: str
    retrieved_at: str


class Node(ApiModel):
    id: str
    slug: str
    kind: Literal["jurisdiction", "organization", "unit", "position", "person"]
    label: str
    short_label: str
    description: str
    category: str
    branch: str
    jurisdiction: str
    valid_from: str
    valid_to: Optional[str] = None
    current_role: Optional[str] = None
    organization_slug: Optional[str] = None
    source_ids: list[str] = Field(default_factory=list)


class Edge(ApiModel):
    id: str
    type: str
    label: str
    source: str
    target: str
    mode: Literal["organization", "power", "both"]
    description: str
    condition: Optional[str] = None
    legal_basis: str
    valid_from: str
    valid_to: Optional[str] = None
    evidence: list[Evidence]


class GraphResponse(ApiModel):
    as_of: date
    mode: Literal["organization", "power"]
    nodes: list[Node]
    edges: list[Edge]


class PortraitSummary(ApiModel):
    url: str
    source_url: str
    credit: str
    alt: str


class OccupancySummary(ApiModel):
    id: str
    person_id: Optional[str] = None
    person_slug: Optional[str] = None
    person_label: Optional[str] = None
    position_id: str
    position_slug: str
    position_label: str
    organization_id: str
    status: Literal["confirmed", "acting", "vacant", "unrecorded"]
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    portrait: Optional[PortraitSummary] = None


class PowerMapCounts(ApiModel):
    children: int = 0
    positions: int = 0
    people: int = 0
    relationships: int = 0


class PowerMapNode(Node):
    parent_id: Optional[str] = None
    hierarchy_depth: int = 0
    expandable: bool = False
    counts: PowerMapCounts = Field(default_factory=PowerMapCounts)
    occupancy: Optional[OccupancySummary] = None
    portrait: Optional[PortraitSummary] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PowerMapGroup(ApiModel):
    id: str
    label: str
    branch: str
    parent_id: Optional[str] = None
    child_count: int
    kinds: list[Literal["jurisdiction", "organization", "unit", "position", "person"]]
    expanded: bool = False


class PowerMapRelationship(ApiModel):
    id: str
    type: str
    label: str
    source: str
    target: str
    mode: Literal["organization", "power", "both"]
    relationship_class: Literal["structure", "power", "competence", "accountability", "tenure"]
    description: str
    condition: Optional[str] = None
    legal_basis: str
    valid_from: str
    valid_to: Optional[str] = None
    has_evidence: bool
    source_label: Optional[str] = None
    target_label: Optional[str] = None


class PowerMapStats(ApiModel):
    organizations: int
    positions: int
    people: int
    vacancies: int
    relationships: int


class PowerMapResponse(ApiModel):
    as_of: date
    root: Optional[str] = None
    nodes: list[PowerMapNode]
    groups: list[PowerMapGroup]
    relationships: list[PowerMapRelationship]
    ancestors: list[PowerMapNode]
    stats: PowerMapStats
    next_cursor: Optional[str] = None


class ContextRelationship(PowerMapRelationship):
    evidence: list[Evidence] = Field(default_factory=list)


class NodeContextResponse(ApiModel):
    as_of: date
    node: PowerMapNode
    occupancies: list[OccupancySummary]
    relationships: list[ContextRelationship]
    changes: list[dict[str, Any]]


class SearchResponse(ApiModel):
    query: str
    total: int
    results: list[Node]


class ReviewDecision(ApiModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)


class ReviewTask(ApiModel):
    id: str
    status: str
    priority: str
    title: str
    source: str
    detected_at: datetime
    summary: str
    batch_id: Optional[str] = None


class ReviewBatch(ApiModel):
    id: str
    adapter: str
    status: str
    title: str
    total: int
    pending: int
    approved: int
    rejected: int
    published: int
    created_at: datetime


class BatchReviewDecision(ReviewDecision):
    excluded_task_ids: list[str] = Field(default_factory=list)


class HealthResponse(ApiModel):
    status: Literal["ok"]
    environment: str
    dataset_generated_at: str
    persistence: Literal["seed", "postgresql"]
    checks: dict[str, Any]
