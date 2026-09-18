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


def range_dates(value: Any) -> tuple[str | None, str | None]:
    """Traduce un rango temporal, admitiendo un inicio no afirmado.

    Un límite inferior abierto significa que la fuente no declara desde cuándo
    existe la entidad, no que exista desde siempre ni desde que se observó.
    """
    start = value.lower.isoformat() if value.lower else None
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
    # Los rangos del modelo son [inicio, fin): la fecha final ya no está activa.
    return start <= as_of and (end is None or as_of < end)


def search_nodes(
    query: str,
    types: set[str],
    as_of: date,
    branch: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    if database_enabled():
        pattern = f"%{query.strip()}%"
        with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT n.*
                FROM nodes n
                LEFT JOIN entity_aliases ea ON ea.node_id = n.id AND ea.valid_during @> %s::date
                WHERE n.valid_during @> %s::date
                  AND (%s::text IS NULL OR n.branch = %s)
                  AND (%s::text IS NULL OR n.category = %s)
                  AND (n.canonical_name ILIKE %s OR n.short_name ILIKE %s OR ea.alias ILIKE %s)
                ORDER BY n.canonical_name
                LIMIT 50
                """,
                (as_of, as_of, branch, branch, category, category, pattern, pattern, pattern),
            )
            results = [node_from_row(row) for row in cursor.fetchall()]
        return [node for node in results if not types or node["kind"] in types]

    normalized = query.casefold().strip()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for node in load_dataset()["nodes"]:
        if types and node["kind"] not in types:
            continue
        if branch and node["branch"] != branch:
            continue
        if category and node["category"] != category:
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


def _primitive_metadata(value: dict[str, Any] | None) -> dict[str, str | int | bool | None]:
    return {
        key: item for key, item in (value or {}).items()
        if item is None or isinstance(item, (str, int, bool))
    }


def _portrait_from_record(record: dict[str, Any]) -> dict[str, str] | None:
    metadata = record.get("metadata") or {}
    url = record.get("official_portrait_url") or metadata.get("officialPortraitUrl")
    source_url = record.get("portrait_source_url") or metadata.get("portraitSourceUrl")
    if not url or not source_url:
        return None
    return {
        "url": url,
        "sourceUrl": source_url,
        "credit": record.get("portrait_credit") or metadata.get("portraitCredit") or "Fuente oficial",
        "alt": f'Retrato oficial de {record.get("canonical_name") or record.get("label", "la persona")}',
    }


def _power_relationship_from_row(row: dict[str, Any]) -> dict[str, Any]:
    valid_from, valid_to = range_dates(row["valid_during"])
    metadata = row.get("metadata") or {}
    return {
        "id": row["slug"],
        "type": row["relationship_type"],
        "label": row["label"],
        "source": str(row["source_node_id"]),
        "target": str(row["target_node_id"]),
        "mode": metadata.get("mode", "power"),
        "relationshipClass": row["relationship_class"],
        "description": row["description"],
        "condition": row.get("condition"),
        "legalBasis": metadata.get("legalBasis", "Fundamento pendiente"),
        "validFrom": valid_from,
        "validTo": valid_to,
        "hasEvidence": bool(row.get("has_evidence", True)),
        "sourceLabel": row.get("source_label"),
        "targetLabel": row.get("target_label"),
        "_relationshipId": str(row["id"]),
    }


def _seed_power_relationship(edge: dict[str, Any]) -> dict[str, Any]:
    relationship_class = "structure" if edge["type"] == "PART_OF" else "tenure" if edge["type"] == "HOLDS" else "power"
    return {
        **{key: value for key, value in edge.items() if key != "evidence"},
        "relationshipClass": relationship_class,
        "hasEvidence": bool(edge.get("evidence")),
        "_evidence": edge.get("evidence", []),
    }


def _load_power_records(as_of: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load map records in bulk. The returned occupancies are normalized for seed and PostgreSQL."""
    if not database_enabled():
        dataset = load_dataset()
        nodes = [{**node, "metadata": {}, "portrait": None} for node in dataset["nodes"] if active_on(node, as_of)]
        edges = [_seed_power_relationship(edge) for edge in dataset["edges"] if active_on(edge, as_of)]
        seed_labels = {node["id"]: node["label"] for node in nodes}
        for edge in edges:
            edge["sourceLabel"] = seed_labels.get(edge["source"])
            edge["targetLabel"] = seed_labels.get(edge["target"])
        node_by_slug = {node["slug"]: node for node in nodes}
        organization_by_position = {
            node["id"]: node_by_slug[node["organizationSlug"]]["id"]
            for node in nodes
            if node["kind"] == "position" and node.get("organizationSlug") in node_by_slug
        }
        occupancies: list[dict[str, Any]] = []
        for edge in edges:
            if edge["type"] != "HOLDS":
                continue
            person = next((node for node in nodes if node["id"] == edge["source"]), None)
            position = next((node for node in nodes if node["id"] == edge["target"]), None)
            if not person or not position:
                continue
            occupancies.append({
                "id": edge["id"], "personId": person["id"], "personSlug": person["slug"],
                "personLabel": person["label"], "positionId": position["id"],
                "positionSlug": position["slug"], "positionLabel": position["label"],
                "organizationId": organization_by_position.get(position["id"], position["id"]),
                "status": "confirmed", "validFrom": edge["validFrom"], "validTo": edge["validTo"],
                "portrait": None,
            })
        for node in nodes:
            if node["kind"] == "position":
                node["_organizationId"] = organization_by_position.get(node["id"])
        return nodes, edges, occupancies

    with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT n.*, p.organization_id AS position_organization_id, p.position_type,
                   p.seat_number, p.selection_method, p.is_elected, p.is_collegial,
                   p.metadata AS position_metadata, pe.official_profile_url,
                   pe.official_portrait_url, psd.canonical_url AS portrait_source_url,
                   psd.publisher AS portrait_credit
            FROM nodes n
            LEFT JOIN positions p ON p.node_id = n.id
            LEFT JOIN persons pe ON pe.node_id = n.id
            LEFT JOIN source_documents psd ON psd.id = pe.portrait_source_document_id
            WHERE n.valid_during @> %s::date AND n.retired_at IS NULL
            ORDER BY n.branch, n.category, n.canonical_name
            """,
            (as_of,),
        )
        # A node should have one specialized record, but keeping this boundary
        # unique makes the API resilient to legacy/imported rows that may cause
        # a join to repeat the same polymorphic node.
        node_rows = {str(row["id"]): row for row in cursor.fetchall()}
        nodes = []
        for row in node_rows.values():
            node = node_from_row(row)
            node["metadata"] = _primitive_metadata({**(row.get("metadata") or {}), **(row.get("position_metadata") or {})})
            node["portrait"] = _portrait_from_record(row)
            node["_organizationId"] = str(row["position_organization_id"]) if row.get("position_organization_id") else None
            nodes.append(node)

        cursor.execute(
            """
            SELECT r.*, source.canonical_name AS source_label, target.canonical_name AS target_label,
                   EXISTS (
              SELECT 1 FROM assertions a
              JOIN evidence_links el ON el.assertion_id = a.id AND el.supports
              WHERE a.relationship_id = r.id AND a.status = 'published'
            ) AS has_evidence
            FROM published_relationships r
            JOIN nodes source ON source.id = r.source_node_id
            JOIN nodes target ON target.id = r.target_node_id
            WHERE r.valid_during @> %s::date AND r.retired_at IS NULL
            ORDER BY r.relationship_class, r.relationship_type, r.slug
            """,
            (as_of,),
        )
        edges = [_power_relationship_from_row(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT t.id, t.status, t.valid_during, pos.id AS position_id, pos.slug AS position_slug,
                   pos.canonical_name AS position_label, p.organization_id,
                   person.id AS person_id, person.slug AS person_slug, person.canonical_name AS person_label,
                   pe.official_portrait_url, psd.canonical_url AS portrait_source_url,
                   psd.publisher AS portrait_credit, person.metadata
            FROM tenures t
            JOIN nodes pos ON pos.id = t.position_id
            JOIN positions p ON p.node_id = pos.id
            JOIN nodes person ON person.id = t.person_id
            JOIN persons pe ON pe.node_id = person.id
            LEFT JOIN source_documents psd ON psd.id = pe.portrait_source_document_id
            WHERE t.valid_during @> %s::date AND t.retired_at IS NULL
            ORDER BY pos.canonical_name, person.canonical_name
            """,
            (as_of,),
        )
        occupancies = []
        for row in cursor.fetchall():
            valid_from, valid_to = range_dates(row["valid_during"])
            occupancies.append({
                "id": str(row["id"]), "personId": str(row["person_id"]),
                "personSlug": row["person_slug"], "personLabel": row["person_label"],
                "positionId": str(row["position_id"]), "positionSlug": row["position_slug"],
                "positionLabel": row["position_label"], "organizationId": str(row["organization_id"]),
                "status": row["status"] if row["status"] in ("confirmed", "acting") else "confirmed",
                "validFrom": valid_from, "validTo": valid_to, "portrait": _portrait_from_record(row),
            })
        return nodes, edges, occupancies


def _assemble_power_map(
    as_of: date,
    root: str | None,
    depth: int,
    cursor_value: str | None,
    limit: int,
) -> dict[str, Any]:
    nodes, edges, occupancies = _load_power_records(as_of)
    nodes_by_id = {node["id"]: node for node in nodes}
    nodes_by_slug = {node["slug"]: node for node in nodes}
    parent: dict[str, str] = {}
    for edge in edges:
        if edge["type"] in ("PART_OF", "HEADS", "HOLDS"):
            parent.setdefault(edge["source"], edge["target"])
    for node in nodes:
        if node.get("_organizationId"):
            parent.setdefault(node["id"], node["_organizationId"])

    occupancy_by_position = {item["positionId"]: item for item in occupancies}
    occupancy_by_person = {item["personId"]: item for item in occupancies if item.get("personId")}
    positions_by_organization: dict[str, list[dict[str, Any]]] = {}
    children: dict[str, list[str]] = {}
    for child_id, parent_id in parent.items():
        children.setdefault(parent_id, []).append(child_id)
    for node in nodes:
        organization_id = node.get("_organizationId")
        if organization_id:
            positions_by_organization.setdefault(organization_id, []).append(node)

    def hierarchy_depth(node_id: str) -> int:
        seen = {node_id}
        current = node_id
        result = 0
        while current in parent and parent[current] not in seen and result < 12:
            current = parent[current]
            seen.add(current)
            result += 1
        return result

    relationship_count: dict[str, int] = {}
    for edge in edges:
        relationship_count[edge["source"]] = relationship_count.get(edge["source"], 0) + 1
        relationship_count[edge["target"]] = relationship_count.get(edge["target"], 0) + 1

    def serialize_node(node: dict[str, Any]) -> dict[str, Any]:
        direct_children = children.get(node["id"], [])
        positions = positions_by_organization.get(node["id"], [])
        occupancy = occupancy_by_position.get(node["id"]) or occupancy_by_person.get(node["id"])
        if not occupancy and len(positions) == 1:
            occupancy = occupancy_by_position.get(positions[0]["id"])
        if not occupancy and node["kind"] == "position" and (node.get("metadata") or {}).get("occupancyStatus") == "vacant":
            occupancy = {
                "id": f"vacant-{node['id']}", "personId": None, "personSlug": None,
                "personLabel": None, "positionId": node["id"], "positionSlug": node["slug"],
                "positionLabel": node["label"], "organizationId": node.get("_organizationId") or node["id"],
                "status": "vacant", "validFrom": node["validFrom"], "validTo": node.get("validTo"),
                "portrait": None,
            }
        return {
            **{key: value for key, value in node.items() if not key.startswith("_") and key != "portrait"},
            "parentId": parent.get(node["id"]),
            "hierarchyDepth": hierarchy_depth(node["id"]),
            "expandable": bool(direct_children),
            "counts": {
                "children": len(direct_children),
                "positions": len(positions),
                "people": sum(1 for position in positions if position["id"] in occupancy_by_position),
                "relationships": relationship_count.get(node["id"], 0),
            },
            "occupancy": occupancy,
            "portrait": node.get("portrait"),
            "metadata": node.get("metadata") or {},
        }

    root_node = nodes_by_id.get(root or "") or nodes_by_slug.get(root or "")
    offset = int(cursor_value) if cursor_value and cursor_value.isdigit() else 0
    visible_ids: set[str] = set()
    next_cursor: str | None = None

    if root_node:
        visible_ids.add(root_node["id"])
        direct = sorted(children.get(root_node["id"], []), key=lambda item: nodes_by_id.get(item, {}).get("label", ""))
        page = direct[offset:offset + limit]
        if offset + limit < len(direct):
            next_cursor = str(offset + limit)
        frontier = set(page)
        visible_ids.update(frontier)
        for _ in range(max(depth - 1, 0)):
            next_frontier: set[str] = set()
            for node_id in frontier:
                descendants = children.get(node_id, [])
                if len(descendants) <= 40:
                    next_frontier.update(descendants)
            visible_ids.update(next_frontier)
            frontier = next_frontier
        # A selection must remain understandable even when it has no children:
        # include its direct graph neighbours and complete ancestor route so the
        # client can draw every direct relation without loading the full graph.
        for edge in edges:
            if edge["source"] == root_node["id"]:
                visible_ids.add(edge["target"])
            elif edge["target"] == root_node["id"]:
                visible_ids.add(edge["source"])
        ancestor_id = parent.get(root_node["id"])
        ancestor_seen: set[str] = set()
        while ancestor_id and ancestor_id not in ancestor_seen:
            ancestor_seen.add(ancestor_id)
            visible_ids.add(ancestor_id)
            ancestor_id = parent.get(ancestor_id)
    else:
        anchor_ids = {
            node["id"] for node in nodes
            if node["slug"] in ("estado-mexicano", "ciudadania", "organos-autonomos")
            or node["category"] == "branch"
        }
        visible_ids.update(anchor_ids)
        branch_ids = {node["id"] for node in nodes if node["category"] in ("branch", "navigation_group")}
        for branch_id in branch_ids:
            visible_ids.update(children.get(branch_id, []))

    visible_nodes = [serialize_node(nodes_by_id[node_id]) for node_id in visible_ids if node_id in nodes_by_id]
    visible_nodes.sort(key=lambda item: (item["branch"], item["hierarchyDepth"], item["label"]))
    visible_edges = [
        {key: value for key, value in edge.items() if not key.startswith("_") and key != "_evidence"}
        for edge in edges if edge["source"] in visible_ids and edge["target"] in visible_ids
    ]
    groups = [
        {
            "id": node["id"], "label": node["label"], "branch": node["branch"],
            "parentId": parent.get(node["id"]), "childCount": len(children.get(node["id"], [])),
            "kinds": sorted({nodes_by_id[child]["kind"] for child in children.get(node["id"], []) if child in nodes_by_id}),
            "expanded": bool(root_node and root_node["id"] == node["id"]),
        }
        for node in nodes if children.get(node["id"])
    ]

    ancestors: list[dict[str, Any]] = []
    current = parent.get(root_node["id"]) if root_node else None
    seen: set[str] = set()
    while current and current not in seen and current in nodes_by_id:
        seen.add(current)
        ancestors.append(serialize_node(nodes_by_id[current]))
        current = parent.get(current)
    ancestors.reverse()

    positions = [node for node in nodes if node["kind"] == "position"]
    return {
        "asOf": as_of, "root": root_node["id"] if root_node else None,
        "nodes": visible_nodes, "groups": groups, "relationships": visible_edges,
        "ancestors": ancestors,
        "stats": {
            "organizations": sum(1 for node in nodes if node["kind"] == "organization"),
            "positions": len(positions), "people": sum(1 for node in nodes if node["kind"] == "person"),
            "vacancies": sum(
                1 for node in positions
                if node["id"] not in occupancy_by_position
                and (node.get("metadata") or {}).get("occupancyStatus") == "vacant"
            ),
            "relationships": len(edges),
        },
        "nextCursor": next_cursor,
    }


def power_map(as_of: date, root: str | None, depth: int, cursor_value: str | None, limit: int) -> dict[str, Any]:
    return _assemble_power_map(as_of, root, depth, cursor_value, limit)


def _bulk_evidence(connection: psycopg.Connection, relationship_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not relationship_ids:
        return {}
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT a.relationship_id::text, sd.slug AS source_id, sd.publisher, sd.title,
                   sd.canonical_url AS url, sf.locator, ss.retrieved_at
            FROM assertions a
            JOIN evidence_links el ON el.assertion_id = a.id AND el.supports
            JOIN source_fragments sf ON sf.id = el.source_fragment_id
            JOIN source_snapshots ss ON ss.id = sf.snapshot_id
            JOIN source_documents sd ON sd.id = ss.source_document_id
            WHERE a.relationship_id = ANY(%s::uuid[]) AND a.status = 'published'
            ORDER BY a.relationship_id, sd.publisher, sf.locator
            """,
            (relationship_ids,),
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            result.setdefault(row["relationship_id"], []).append({
                "sourceId": row["source_id"], "publisher": row["publisher"], "title": row["title"],
                "url": row["url"], "locator": row["locator"],
                "retrievedAt": row["retrieved_at"].date().isoformat(),
            })
        return result


def node_context(identifier: str, as_of: date) -> dict[str, Any] | None:
    nodes, edges, occupancies = _load_power_records(as_of)
    selected = next((node for node in nodes if node["id"] == identifier or node["slug"] == identifier), None)
    if not selected:
        return None
    assembled = _assemble_power_map(as_of, selected["id"], 1, None, 1)
    serialized = next((node for node in assembled["nodes"] if node["id"] == selected["id"]), None)
    if not serialized:
        return None
    related = [edge for edge in edges if selected["id"] in (edge["source"], edge["target"])]
    selected_occupancies = [
        item for item in occupancies
        if selected["id"] in (item.get("personId"), item["positionId"], item["organizationId"])
    ]
    if database_enabled():
        with psycopg.connect(database_url(), row_factory=dict_row) as connection:
            evidence = _bulk_evidence(connection, [edge["_relationshipId"] for edge in related])
        context_relationships = [
            {
                **{key: value for key, value in edge.items() if not key.startswith("_")},
                "evidence": evidence.get(edge["_relationshipId"], []),
            }
            for edge in related
        ]
    else:
        context_relationships = [
            {**{key: value for key, value in edge.items() if not key.startswith("_")}, "evidence": edge.get("_evidence", [])}
            for edge in related
        ]
    return {
        "asOf": as_of, "node": serialized, "occupancies": selected_occupancies,
        "relationships": context_relationships, "changes": node_timeline(selected["id"]),
    }


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
                SELECT rt.id, rt.status, rt.priority, rt.title, rt.summary, rt.created_at, rt.batch_id,
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
                    "batchId": str(row["batch_id"]) if row["batch_id"] else None,
                }
                for row in cursor.fetchall()
            ]
    return load_dataset()["reviewTasks"]


def review_batches() -> list[dict[str, Any]]:
    if not database_enabled():
        return []
    with psycopg.connect(database_url(), row_factory=dict_row) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT rb.id, ir.adapter_key, rb.status, rb.title, rb.created_at,
                   COUNT(rt.id) AS total,
                   COUNT(rt.id) FILTER (WHERE rt.status = 'needs_review') AS pending,
                   COUNT(rt.id) FILTER (WHERE rt.status = 'approved') AS approved,
                   COUNT(rt.id) FILTER (WHERE rt.status = 'rejected') AS rejected,
                   COUNT(rt.id) FILTER (WHERE rt.status = 'published') AS published
            FROM review_batches rb
            JOIN ingestion_runs ir ON ir.id = rb.ingestion_run_id
            LEFT JOIN review_tasks rt ON rt.batch_id = rb.id
            GROUP BY rb.id, ir.adapter_key
            ORDER BY rb.created_at DESC
            LIMIT 100
            """
        )
        return [
            {
                "id": str(row["id"]), "adapter": row["adapter_key"], "status": row["status"],
                "title": row["title"], "total": row["total"], "pending": row["pending"],
                "approved": row["approved"], "rejected": row["rejected"],
                "published": row["published"], "createdAt": row["created_at"],
            }
            for row in cursor.fetchall()
        ]


def decide_review_batch(
    batch_id: str,
    decision: str,
    note: str,
    reviewer: str,
    excluded_task_ids: list[str],
) -> int:
    if not database_enabled():
        return 0
    target_status = "approved" if decision == "approved" else "rejected"
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE review_tasks rt
            SET status = %s, decision_note = %s, decided_by = %s, decided_at = now()
            WHERE rt.batch_id::text = %s AND rt.status = 'needs_review'
              AND NOT (rt.id::text = ANY(%s::text[]))
            """,
            (target_status, note, reviewer, batch_id, excluded_task_ids),
        )
        changed = cursor.rowcount
        cursor.execute(
            """
            UPDATE review_batches rb
            SET status = CASE
                  WHEN EXISTS (SELECT 1 FROM review_tasks rt WHERE rt.batch_id = rb.id AND rt.status = 'needs_review')
                    THEN 'partially_reviewed'
                  ELSE %s
                END,
                decision_note = %s, decided_by = %s, decided_at = now()
            WHERE rb.id::text = %s
            """,
            (target_status, note, reviewer, batch_id),
        )
        return changed


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
