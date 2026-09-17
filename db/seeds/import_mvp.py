"""Importa el conjunto MVP compartido y publica sus relaciones con evidencia.

Uso:
    DATABASE_URL=postgresql://... python db/seeds/import_mvp.py
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg

ROOT = Path(__file__).resolve().parents[2]
DATASET = json.loads((ROOT / "packages/contracts/data/mvp.json").read_text(encoding="utf-8"))


def stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://mapapoder.mx/{value}"))


def date_range(start: str, end: str | None) -> str:
    exclusive_end = (date.fromisoformat(end) + timedelta(days=1)).isoformat() if end else ""
    return f"[{start},{exclusive_end})"


def main() -> None:
    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    nodes_by_slug = {node["slug"]: node for node in DATASET["nodes"]}
    source_ids: dict[str, str] = {}

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        for node in DATASET["nodes"]:
            cursor.execute(
                """
                INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::daterange, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                  canonical_name = EXCLUDED.canonical_name,
                  short_name = EXCLUDED.short_name,
                  description = EXCLUDED.description,
                  category = EXCLUDED.category,
                  branch = EXCLUDED.branch,
                  valid_during = EXCLUDED.valid_during,
                  metadata = EXCLUDED.metadata
                """,
                (
                    node["id"], node["slug"], node["kind"], node["label"], node["shortLabel"],
                    node["description"], node["category"], node["branch"],
                    date_range(node["validFrom"], node.get("validTo")),
                    json.dumps({
                        "jurisdiction": node["jurisdiction"],
                        "sourceIds": node["sourceIds"],
                        "currentRole": node.get("currentRole"),
                        "organizationSlug": node.get("organizationSlug"),
                    }),
                ),
            )

        for node in DATASET["nodes"]:
            if node["kind"] == "organization":
                cursor.execute(
                    "INSERT INTO organizations (node_id, organization_type) VALUES (%s, %s) ON CONFLICT (node_id) DO UPDATE SET organization_type = EXCLUDED.organization_type",
                    (node["id"], node["category"]),
                )
            elif node["kind"] == "position":
                organization = nodes_by_slug[node["organizationSlug"]]
                cursor.execute(
                    """
                    INSERT INTO positions (node_id, organization_id, position_type, is_elected)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (node_id) DO UPDATE SET organization_id = EXCLUDED.organization_id, position_type = EXCLUDED.position_type, is_elected = EXCLUDED.is_elected
                    """,
                    (node["id"], organization["id"], node["category"], node["category"] == "elected_office"),
                )
            elif node["kind"] == "person":
                parts = node["label"].split()
                cursor.execute(
                    """
                    INSERT INTO persons (node_id, given_names, family_names)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (node_id) DO UPDATE SET given_names = EXCLUDED.given_names, family_names = EXCLUDED.family_names
                    """,
                    (node["id"], " ".join(parts[:-2]) or parts[0], " ".join(parts[-2:])),
                )

        for source in DATASET["sources"]:
            source_uuid = stable_id(f"source/{source['id']}")
            source_ids[source["id"]] = source_uuid
            cursor.execute(
                """
                INSERT INTO source_documents (id, slug, publisher, title, canonical_url, source_type, publication_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET publisher = EXCLUDED.publisher, title = EXCLUDED.title, canonical_url = EXCLUDED.canonical_url
                """,
                (source_uuid, source["id"], source["publisher"], source["title"], source["url"], source["type"], source["publicationDate"]),
            )

        for edge in DATASET["edges"]:
            relationship_uuid = stable_id(f"relationship/{edge['id']}")
            relationship_class = "structure" if edge["type"] == "PART_OF" else "tenure" if edge["type"] == "HOLDS" else "power"
            cursor.execute(
                """
                INSERT INTO relationships (id, slug, relationship_type, relationship_class, source_node_id, target_node_id, label, description, condition, valid_during, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::daterange, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET description = EXCLUDED.description, condition = EXCLUDED.condition, valid_during = EXCLUDED.valid_during, metadata = EXCLUDED.metadata
                """,
                (
                    relationship_uuid, edge["id"], edge["type"], relationship_class, edge["source"], edge["target"],
                    edge["label"], edge["description"], edge.get("condition"),
                    date_range(edge["validFrom"], edge.get("validTo")),
                    json.dumps({"mode": edge["mode"], "legalBasis": edge["legalBasis"]}),
                ),
            )
            assertion_uuid = stable_id(f"assertion/{edge['id']}")
            cursor.execute(
                """
                INSERT INTO assertions (id, assertion_type, subject_node_id, predicate, object_node_id, relationship_id, valid_during, observed_at, extraction_method, confidence, status, reviewed_by, reviewed_at, published_at)
                VALUES (%s, 'relationship', %s, %s, %s, %s, %s::daterange, %s, 'curated_seed', 1, 'published', 'bootstrap', now(), now())
                ON CONFLICT (id) DO NOTHING
                """,
                (assertion_uuid, edge["source"], edge["type"], edge["target"], relationship_uuid, date_range(edge["validFrom"], edge.get("validTo")), DATASET["generatedAt"]),
            )
            for evidence in edge["evidence"]:
                snapshot_uuid = stable_id(f"snapshot/{edge['id']}/{evidence['sourceId']}")
                fragment_uuid = stable_id(f"fragment/{edge['id']}/{evidence['sourceId']}")
                content_hash = stable_id(f"hash/{edge['id']}/{evidence['sourceId']}").replace("-", "")
                cursor.execute(
                    """
                    INSERT INTO source_snapshots (id, source_document_id, retrieved_at, final_url, content_hash, mime_type, byte_size, storage_path, http_status)
                    VALUES (%s, %s, %s, %s, %s, 'text/html', 0, %s, 200)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (snapshot_uuid, source_ids[evidence["sourceId"]], evidence["retrievedAt"], evidence["url"], content_hash, f"seed://{evidence['sourceId']}"),
                )
                cursor.execute(
                    """
                    INSERT INTO source_fragments (id, snapshot_id, locator, fragment_text, fragment_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (fragment_uuid, snapshot_uuid, evidence["locator"], edge["legalBasis"], content_hash),
                )
                cursor.execute(
                    "INSERT INTO evidence_links (assertion_id, source_fragment_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (assertion_uuid, fragment_uuid),
                )

    print(f"Imported {len(DATASET['nodes'])} nodes, {len(DATASET['edges'])} relationships and {len(DATASET['sources'])} sources")


if __name__ == "__main__":
    main()
