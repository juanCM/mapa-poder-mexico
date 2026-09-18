from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .settings import get_settings


@lru_cache
def load_dataset() -> dict[str, Any]:
    with get_settings().seed_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def database_enabled() -> bool:
    return bool(get_settings().database_url)


def database_url() -> str:
    configured = get_settings().database_url
    if not configured:
        raise RuntimeError("DATABASE_URL is not configured")
    return configured.replace("postgresql+psycopg://", "postgresql://", 1)


def database_check() -> bool:
    if not database_enabled():
        return False
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1


def range_dates(value: Any) -> tuple[str, str | None]:
    start = value.lower.isoformat()
    end = None
    if value.upper:
        end = (value.upper - timedelta(days=1)).isoformat()
    return start, end


def node_from_row(row: dict[str, Any]) -> dict[str, Any]:
    valid_from, valid_to = range_dates(row["valid_during"])
    metadata = row.get("metadata") or {}
    return {
        "id": str(row["id"]),
        "slug": row["slug"],
        "kind": row["kind"],
        "label": row["canonical_name"],
        "shortLabel": row["short_name"] or row["canonical_name"],
        "description": row["description"],
        "category": row["category"],
        "branch": row["branch"],
        "jurisdiction": metadata.get("jurisdiction", "Federal"),
        "validFrom": valid_from,
        "validTo": valid_to,
        "currentRole": metadata.get("currentRole"),
        "organizationSlug": metadata.get("organizationSlug"),
        "sourceIds": metadata.get("sourceIds", []),
    }


def evidence_for_relationship(connection: psycopg.Connection, relationship_id: str) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT sd.slug AS source_id, sd.publisher, sd.title, sd.canonical_url AS url,
                   sf.locator, ss.retrieved_at
            FROM assertions a
            JOIN evidence_links el ON el.assertion_id = a.id AND el.supports
            JOIN source_fragments sf ON sf.id = el.source_fragment_id
            JOIN source_snapshots ss ON ss.id = sf.snapshot_id
            JOIN source_documents sd ON sd.id = ss.source_document_id
            WHERE a.relationship_id = %s AND a.status = 'published'
            ORDER BY sd.publisher, sf.locator
            """,
            (relationship_id,),
        )
        return [
            {
                "sourceId": row["source_id"],
                "publisher": row["publisher"],
                "title": row["title"],
                "url": row["url"],
                "locator": row["locator"],
                "retrievedAt": row["retrieved_at"].date().isoformat(),
            }
            for row in cursor.fetchall()
        ]


def edge_from_row(connection: psycopg.Connection, row: dict[str, Any]) -> dict[str, Any]:
    valid_from, valid_to = range_dates(row["valid_during"])
    metadata = row.get("metadata") or {}
    return {
        "id": row["slug"],
        "type": row["relationship_type"],
        "label": row["label"],
        "source": str(row["source_node_id"]),
        "target": str(row["target_node_id"]),
        "mode": metadata.get("mode", "power"),
        "description": row["description"],
        "condition": row["condition"],
        "legalBasis": metadata.get("legalBasis", "Fundamento pendiente"),
        "validFrom": valid_from,
        "validTo": valid_to,
        "evidence": evidence_for_relationship(connection, str(row["id"])),
    }


def active_on(record: dict[str, Any], as_of: date) -> bool:
    start = date.fromisoformat(record["validFrom"])
    end_value = record.get("validTo")
    end = date.fromisoformat(end_value) if end_value else None
    return start <= as_of and (end is None or as_of <= end)


def search_nodes(query: str, types: set[str], as_of: date) -> list[dict[str, Any]]:
    if database_enabled():
        pattern = f"%{query.strip()}%"
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT n.*
                FROM nodes n
                LEFT JOIN entity_aliases ea ON ea.node_id = n.id AND ea.valid_during @> %s::date
                WHERE n.valid_during @> %s::date
                  AND (n.canonical_name ILIKE %s OR n.short_name ILIKE %s OR ea.alias ILIKE %s)
                ORDER BY n.canonical_name
                LIMIT 50
                """,
                (as_of, as_of, pattern, pattern, pattern),
            )
            results = [node_from_row(row) for row in cursor.fetchall()]
        return [node for node in results if not types or node["kind"] in types]

    normalized = query.casefold().strip()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for node in load_dataset()["nodes"]:
        if types and node["kind"] not in types:
            continue
        if not active_on(node, as_of):
            continue
        haystack = f'{node["label"]} {node["shortLabel"]} {node["description"]}'.casefold()
        if normalized in haystack:
            score = 0 if node["label"].casefold().startswith(normalized) else 1
            ranked.append((score, node))
    ranked.sort(key=lambda item: (item[0], item[1]["label"]))
    return [node for _, node in ranked]


def get_node(identifier: str) -> dict[str, Any] | None:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nodes WHERE id::text = %s OR slug = %s", (identifier, identifier))
            row = cursor.fetchone()
            return node_from_row(row) if row else None
    return next((item for item in load_dataset()["nodes"] if item["id"] == identifier or item["slug"] == identifier), None)


def get_edge(identifier: str) -> dict[str, Any] | None:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM published_relationships WHERE id::text = %s OR slug = %s", (identifier, identifier))
            row = cursor.fetchone()
            return edge_from_row(connection, row) if row else None
    return next((item for item in load_dataset()["edges"] if item["id"] == identifier), None)


def graph(mode: str, as_of: date, root: str | None, depth: int, relation_types: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM published_relationships
                WHERE valid_during @> %s::date
                  AND (metadata->>'mode' = %s OR metadata->>'mode' = 'both')
                ORDER BY relationship_type, slug
                """,
                (as_of, mode),
            )
            edges = [edge_from_row(connection, row) for row in cursor.fetchall()]
        dataset = None
    else:
        dataset = load_dataset()
        edges = [edge for edge in dataset["edges"] if edge["mode"] in (mode, "both") and active_on(edge, as_of)]
    if relation_types:
        edges = [edge for edge in edges if edge["type"] in relation_types]

    if root:
        root_node = get_node(root)
        if not root_node:
            return [], []
        frontier = {root_node["id"]}
        visited = set(frontier)
        selected: list[dict[str, Any]] = []
        for _ in range(depth):
            step_edges = [edge for edge in edges if edge["source"] in frontier or edge["target"] in frontier]
            selected.extend(edge for edge in step_edges if edge not in selected)
            frontier = {node_id for edge in step_edges for node_id in (edge["source"], edge["target"])} - visited
            visited.update(frontier)
        edges = selected

    node_ids = {node_id for edge in edges for node_id in (edge["source"], edge["target"])}
    if database_enabled():
        if not node_ids:
            return [], edges
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nodes WHERE id = ANY(%s::uuid[]) AND valid_during @> %s::date", (list(node_ids), as_of))
            nodes = [node_from_row(row) for row in cursor.fetchall()]
    else:
        nodes = [node for node in dataset["nodes"] if node["id"] in node_ids and active_on(node, as_of)]
    return nodes, edges


def node_timeline(node_id: str) -> list[dict[str, Any]]:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT gce.*, sd.slug AS source_id
                FROM government_change_events gce
                JOIN assertions a ON a.id = gce.assertion_id
                LEFT JOIN evidence_links el ON el.assertion_id = a.id
                LEFT JOIN source_fragments sf ON sf.id = el.source_fragment_id
                LEFT JOIN source_snapshots ss ON ss.id = sf.snapshot_id
                LEFT JOIN source_documents sd ON sd.id = ss.source_document_id
                WHERE gce.primary_node_id = %s
                ORDER BY gce.occurred_on DESC
                """,
                (node_id,),
            )
            return [event_from_row(row) for row in cursor.fetchall()]
    return [event for event in load_dataset()["changes"] if node_id in event["nodeIds"]]


def changes_between(from_date: date | None, to_date: date | None) -> list[dict[str, Any]]:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT gce.*, sd.slug AS source_id
                FROM government_change_events gce
                JOIN assertions a ON a.id = gce.assertion_id
                LEFT JOIN evidence_links el ON el.assertion_id = a.id
                LEFT JOIN source_fragments sf ON sf.id = el.source_fragment_id
                LEFT JOIN source_snapshots ss ON ss.id = sf.snapshot_id
                LEFT JOIN source_documents sd ON sd.id = ss.source_document_id
                WHERE (%s::date IS NULL OR occurred_on >= %s::date)
                  AND (%s::date IS NULL OR occurred_on <= %s::date)
                ORDER BY occurred_on DESC
                """,
                (from_date, from_date, to_date, to_date),
            )
            return [event_from_row(row) for row in cursor.fetchall()]
    events = load_dataset()["changes"]
    return [
        event for event in events
        if (from_date is None or date.fromisoformat(event["date"]) >= from_date)
        and (to_date is None or date.fromisoformat(event["date"]) <= to_date)
    ]


def review_tasks() -> list[dict[str, Any]]:
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rt.id, rt.status, rt.priority, rt.title, rt.summary, rt.created_at,
                       COALESCE(ir.adapter_key, 'manual') AS source
                FROM review_tasks rt
                LEFT JOIN ingestion_runs ir ON ir.id = rt.ingestion_run_id
                ORDER BY CASE rt.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                         rt.created_at
                """
            )
            return [
                {
                    "id": str(row["id"]),
                    "status": row["status"],
                    "priority": row["priority"],
                    "title": row["title"],
                    "source": row["source"],
                    "detectedAt": row["created_at"].isoformat(),
                    "summary": row["summary"],
                }
                for row in cursor.fetchall()
            ]
    return load_dataset()["reviewTasks"]


def admin_overview() -> dict[str, list[dict[str, Any]]]:
    """Return operational records for the editorial console.

    The seed response intentionally only contains records that exist in the
    curated dataset: it must not pretend that an ingestion run or duplicate
    candidate was created when PostgreSQL is not configured.
    """
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, adapter_key, status, started_at, finished_at, discovered_count,
                       candidate_count, snapshot_count, error_message, created_at
                FROM ingestion_runs
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
            runs = [
                {
                    "id": str(row["id"]), "adapter": row["adapter_key"], "status": row["status"],
                    "startedAt": row["started_at"].isoformat() if row["started_at"] else None,
                    "finishedAt": row["finished_at"].isoformat() if row["finished_at"] else None,
                    "discoveredCount": row["discovered_count"], "candidateCount": row["candidate_count"],
                    "snapshotCount": row["snapshot_count"], "errorMessage": row["error_message"],
                    "createdAt": row["created_at"].isoformat(),
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT ss.content_hash AS candidate_key, COUNT(DISTINCT sd.id) AS count,
                       MAX(ss.retrieved_at) AS detected_at,
                       array_agg(DISTINCT sd.title) AS titles
                FROM source_snapshots ss
                JOIN source_documents sd ON sd.id = ss.source_document_id
                GROUP BY ss.content_hash
                HAVING COUNT(DISTINCT sd.id) > 1
                ORDER BY MAX(ss.retrieved_at) DESC
                LIMIT 100
                """
            )
            duplicates = [
                {
                    "candidateKey": row["candidate_key"], "count": row["count"],
                    "detectedAt": row["detected_at"].isoformat(), "titles": row["titles"],
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT sd.slug, sd.publisher, sd.title, sd.canonical_url, sd.source_type,
                       sd.enabled, sd.trust_tier, sd.adapter_key, sd.created_at,
                       MAX(ss.retrieved_at) AS last_retrieved_at, COUNT(ss.id) AS snapshot_count
                FROM source_documents sd
                LEFT JOIN source_snapshots ss ON ss.source_document_id = sd.id
                GROUP BY sd.id
                ORDER BY MAX(ss.retrieved_at) DESC NULLS LAST, sd.title
                LIMIT 200
                """
            )
            sources = [
                {
                    "id": row["slug"], "publisher": row["publisher"], "title": row["title"],
                    "url": row["canonical_url"], "type": row["source_type"], "enabled": row["enabled"],
                    "trustTier": row["trust_tier"], "adapter": row["adapter_key"],
                    "createdAt": row["created_at"].isoformat(),
                    "lastRetrievedAt": row["last_retrieved_at"].isoformat() if row["last_retrieved_at"] else None,
                    "snapshotCount": row["snapshot_count"],
                }
                for row in cursor.fetchall()
            ]
            return {"runs": runs, "duplicates": duplicates, "sources": sources}

    dataset = load_dataset()
    return {
        "runs": [],
        "duplicates": [],
        "sources": [
            {
                "id": source["id"], "publisher": source["publisher"], "title": source["title"],
                "url": source["url"], "type": source["type"], "enabled": True, "trustTier": "A",
                "adapter": None, "createdAt": source["retrievedAt"], "lastRetrievedAt": source["retrievedAt"],
                "snapshotCount": 1,
            }
            for source in dataset["sources"]
        ],
    }


def parse_detected_at(task: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(task["detectedAt"])


def decide_review_task(task_id: str, decision: str, note: str, reviewer: str) -> bool:
    if not database_enabled():
        return False
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE review_tasks
            SET status = %s, decision_note = %s, decided_by = %s, decided_at = now()
            WHERE id::text = %s AND status = 'needs_review'
            RETURNING assertion_id
            """,
            (decision, note, reviewer, task_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        if row[0]:
            cursor.execute(
                "UPDATE assertions SET status = %s, reviewed_by = %s, reviewed_at = now() WHERE id = %s AND status = 'needs_review'",
                (decision, reviewer, row[0]),
            )
        return True


def event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "type": row["event_type"],
        "date": row["occurred_on"].isoformat(),
        "title": row["title"],
        "description": row["description"],
        "nodeIds": [str(row["primary_node_id"])] if row["primary_node_id"] else [],
        "sourceId": row.get("source_id"),
    }
