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


class HealthResponse(ApiModel):
    status: Literal["ok"]
    environment: str
    dataset_generated_at: str
    persistence: Literal["seed", "postgresql"]
    checks: dict[str, Any]
