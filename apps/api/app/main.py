from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_admin
from .repository import (
    admin_overview,
    changes_between,
    database_check,
    database_enabled,
    decide_review_batch,
    decide_review_task,
    get_edge,
    get_node,
    graph,
    load_dataset,
    node_context,
    node_timeline,
    parse_detected_at,
    power_map,
    review_batches,
    review_tasks,
    search_nodes,
)
from .schemas import (
    BatchReviewDecision,
    Edge,
    GraphResponse,
    HealthResponse,
    Node,
    NodeContextResponse,
    PowerMapResponse,
    ReviewBatch,
    ReviewDecision,
    ReviewTask,
    SearchResponse,
)
from .settings import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de consulta y revisión para información gubernamental temporal y verificable.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    dataset = load_dataset()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        dataset_generated_at=dataset["generatedAt"],
        persistence="postgresql" if database_enabled() else "seed",
        checks={
            "dataset": True,
            "database": database_check() if database_enabled() else None,
            "nodes": len(dataset["nodes"]),
            "edges": len(dataset["edges"]),
        },
    )


@app.get("/v1/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=2, max_length=120),
    types: str = "",
    branch: Optional[str] = None,
    category: Optional[str] = None,
    as_of: date = Query(default_factory=date.today),
) -> SearchResponse:
    results = search_nodes(q, {value for value in types.split(",") if value}, as_of, branch, category)
    return SearchResponse(query=q, total=len(results), results=[Node.model_validate(item) for item in results])


@app.get("/v1/nodes/{identifier}", response_model=Node)
def node_detail(identifier: str, as_of: date = Query(default_factory=date.today)) -> Node:
    node = get_node(identifier)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return Node.model_validate(node)


@app.get("/v1/graph", response_model=GraphResponse)
def graph_view(
    mode: Literal["organization", "power"] = "power",
    as_of: date = Query(default_factory=date.today),
    root: Optional[str] = None,
    depth: int = Query(default=2, ge=1, le=4),
    relation_types: str = "",
) -> GraphResponse:
    nodes, edges = graph(mode, as_of, root, depth, {value for value in relation_types.split(",") if value})
    if root and not nodes:
        raise HTTPException(status_code=404, detail="Root node not found or not connected")
    return GraphResponse(as_of=as_of, mode=mode, nodes=nodes, edges=edges)


@app.get("/v1/power-map", response_model=PowerMapResponse)
def power_map_view(
    as_of: date = Query(default_factory=date.today),
    root: Optional[str] = None,
    depth: int = Query(default=2, ge=1, le=4),
    cursor: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=1000),
) -> PowerMapResponse:
    result = power_map(as_of, root, depth, cursor, limit)
    if root and result["root"] is None:
        raise HTTPException(status_code=404, detail="Root node not found")
    return PowerMapResponse.model_validate(result)


@app.get("/v1/nodes/{identifier}/context", response_model=NodeContextResponse)
def node_context_view(identifier: str, as_of: date = Query(default_factory=date.today)) -> NodeContextResponse:
    result = node_context(identifier, as_of)
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return NodeContextResponse.model_validate(result)


@app.get("/v1/relationships/{identifier}", response_model=Edge)
def relationship_detail(identifier: str) -> Edge:
    edge = get_edge(identifier)
    if not edge:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return Edge.model_validate(edge)


@app.get("/v1/timeline")
def timeline(node_id: str):
    if not get_node(node_id):
        raise HTTPException(status_code=404, detail="Node not found")
    return {"nodeId": node_id, "events": node_timeline(node_id)}


@app.get("/v1/changes")
def changes(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
):
    return {"events": changes_between(from_date, to_date)}


@app.get("/v1/admin/review-tasks", response_model=list[ReviewTask], dependencies=[Depends(require_admin)])
def admin_review_tasks() -> list[ReviewTask]:
    return [ReviewTask(**{**task, "detected_at": parse_detected_at(task)}) for task in review_tasks()]


@app.get("/v1/admin/review-batches", response_model=list[ReviewBatch], dependencies=[Depends(require_admin)])
def admin_review_batches() -> list[ReviewBatch]:
    return [ReviewBatch.model_validate(item) for item in review_batches()]


@app.get("/v1/admin/overview", dependencies=[Depends(require_admin)])
def admin_overview_endpoint() -> dict:
    return admin_overview()


@app.post("/v1/admin/review-tasks/{task_id}/decision", dependencies=[Depends(require_admin)])
def decide_review_task_endpoint(
    task_id: str,
    decision: ReviewDecision,
    reviewer: str = Depends(require_admin),
):
    task = next((item for item in review_tasks() if item["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    persisted = decide_review_task(task_id, decision.decision, decision.note, reviewer)
    return {
        "id": task_id,
        "status": decision.decision,
        "note": decision.note,
        "persisted": persisted,
        "message": "Decision persisted." if persisted else "Seed preview: decision was not persisted.",
    }


@app.post("/v1/admin/review-batches/{batch_id}/decision", dependencies=[Depends(require_admin)])
def decide_review_batch_endpoint(
    batch_id: str,
    decision: BatchReviewDecision,
    reviewer: str = Depends(require_admin),
):
    batch = next((item for item in review_batches() if item["id"] == batch_id), None)
    if not batch:
        raise HTTPException(status_code=404, detail="Review batch not found")
    changed = decide_review_batch(
        batch_id, decision.decision, decision.note, reviewer, decision.excluded_task_ids
    )
    return {"id": batch_id, "status": decision.decision, "changed": changed, "note": decision.note}
