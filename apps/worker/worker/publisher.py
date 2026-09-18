"""Materializa candidatos aprobados como datos públicos y trazables."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from unicodedata import normalize
from uuid import NAMESPACE_URL, uuid5

import psycopg

NAMESPACE = "https://mapapoder.mx/"
PARAESTATAL_LABEL = "Administración Pública Federal Paraestatal"
EXECUTIVE_SLUG = "poder-ejecutivo-federal"


def stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{NAMESPACE}{value}"))


def slugify(value: str) -> str:
    folded = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", folded))


def observed_today() -> date:
    return datetime.now(timezone.utc).date()


def person_name_parts(label: str, metadata: dict) -> tuple[str, str]:
    """Obtiene nombres sin depender de una convención de fuente particular."""
    given = metadata.get("givenNames")
    family = metadata.get("familyNames")
    if given and family:
        return str(given), str(family)
    parts = label.split()
    if len(parts) < 3:
        return label, ""
    return " ".join(parts[:-2]), " ".join(parts[-2:])


@dataclass(frozen=True)
class PublicationResult:
    tasks: int
    nodes: int
    organizations: int
    positions: int
    persons: int
    relationships: int
    assertions: int
    evidence_links: int

    def as_dict(self) -> dict:
        return asdict(self)


class ApprovedCandidatePublisher:
    """Publica tareas aprobadas en una única transacción atómica.

    Una tarea no se considera publicada hasta que existen su relación, una
    afirmación `published` y una liga a un fragmento del snapshot que la
    respalda. El publicador es idempotente: reintentar no duplica registros.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    def publish(self, adapter_key: str | None = None, limit: int | None = None) -> PublicationResult:
        counts = {
            "tasks": 0, "nodes": 0, "organizations": 0, "positions": 0,
            "persons": 0, "relationships": 0, "assertions": 0, "evidence_links": 0,
        }
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            tasks = self._approved_tasks(cursor, adapter_key, limit)
            if not tasks:
                return PublicationResult(**counts)

            executive_id = self._node_id(cursor, EXECUTIVE_SLUG)
            if not executive_id:
                raise RuntimeError("Missing canonical Poder Ejecutivo Federal node")

            paraestatal_id = self._ensure_paraestatal_root(cursor, executive_id, counts)
            for task in tasks:
                candidate = task["candidate"]
                target_id = self._target_id(cursor, candidate, executive_id, paraestatal_id, counts)
                subject_id = self._ensure_subject(cursor, candidate, counts)
                source_slug = self._source_slug(candidate)
                snapshot_id, observed_on = self._latest_snapshot(cursor, source_slug)
                self._publish_relationship(
                    cursor, task, candidate, subject_id, target_id, snapshot_id, observed_on, counts
                )
                cursor.execute(
                    """
                    UPDATE review_tasks
                    SET status = 'published', assertion_id = %s, decided_at = COALESCE(decided_at, now())
                    WHERE id = %s AND status = 'approved'
                    """,
                    (stable_id(f"assertion/{task['id']}"), task["id"]),
                )
                counts["tasks"] += cursor.rowcount
        return PublicationResult(**counts)

    @staticmethod
    def _approved_tasks(cursor: psycopg.Cursor, adapter_key: str | None, limit: int | None) -> list[dict]:
        cursor.execute(
            """
            SELECT rt.id::text, rt.summary
            FROM review_tasks rt
            JOIN ingestion_runs ir ON ir.id = rt.ingestion_run_id
            WHERE rt.status = 'approved' AND (%s::text IS NULL OR ir.adapter_key = %s)
            ORDER BY rt.created_at, rt.id LIMIT %s
            """,
            (adapter_key, adapter_key, limit),
        )
        return [{"id": row[0], "candidate": json.loads(row[1])} for row in cursor.fetchall()]

    @staticmethod
    def _node_id(cursor: psycopg.Cursor, slug: str) -> str | None:
        cursor.execute("SELECT id::text FROM nodes WHERE slug = %s", (slug,))
        row = cursor.fetchone()
        return row[0] if row else None

    def _ensure_paraestatal_root(self, cursor: psycopg.Cursor, executive_id: str, counts: dict) -> str:
        node_id = self._ensure_organization(
            cursor,
            label=PARAESTATAL_LABEL,
            category="administrative_group",
            organization_type="administrative_group",
            observed_on=observed_today(),
            source_ids=["apf_loapf"],
            counts=counts,
        )
        snapshot_id, observed_on = self._latest_snapshot(cursor, "apf_loapf")
        task = {"id": "apf-paraestatal-root"}
        candidate = {
            "candidate_id": "apf-paraestatal-root",
            "predicate": "PART_OF",
            "subject_label": PARAESTATAL_LABEL,
            "object_label": "Poder Ejecutivo Federal",
            "source_locator": "LOAPF, artículos 1 y 3",
            "source_excerpt": "La Administración Pública Federal se integra por la administración centralizada y paraestatal.",
            "metadata": {"mode": "organization", "legalBasis": "LOAPF, artículos 1 y 3"},
        }
        self._publish_relationship(cursor, task, candidate, node_id, executive_id, snapshot_id, observed_on, counts)
        return node_id

    def _target_id(
        self, cursor: psycopg.Cursor, candidate: dict, executive_id: str, paraestatal_id: str, counts: dict
    ) -> str:
        label = candidate.get("object_label")
        if candidate.get("object_kind") == "position":
            organization_label = (candidate.get("metadata") or {}).get("positionOrganizationLabel")
            if not organization_label:
                raise ValueError(f"Position target for {candidate['candidate_id']} lacks positionOrganizationLabel")
            organization_id = self._target_id(cursor, {"object_label": organization_label}, executive_id, paraestatal_id, counts)
            return self._ensure_position(cursor, label, organization_id, observed_today(), counts)
        if label == "Poder Ejecutivo Federal":
            return executive_id
        if label == PARAESTATAL_LABEL:
            return paraestatal_id
        if not label:
            raise ValueError(f"Candidate {candidate['candidate_id']} has no relationship target")
        existing = self._node_id(cursor, slugify(label))
        if existing:
            return existing
        return self._ensure_organization(
            cursor, label, "federal_entity", "federal_entity", observed_today(), [], counts
        )

    @staticmethod
    def _source_slug(candidate: dict) -> str:
        metadata = candidate.get("metadata") or {}
        if metadata.get("sourceDocumentSlug"):
            return metadata["sourceDocumentSlug"]
        return "apf_loapf" if metadata.get("apfSector") == "centralizada" else "apf_paraestatales"

    def _ensure_subject(self, cursor: psycopg.Cursor, candidate: dict, counts: dict) -> str:
        kind = candidate.get("subject_kind") or "organization"
        metadata = candidate.get("metadata") or {}
        if kind == "person":
            return self._ensure_person(cursor, candidate["subject_label"], metadata, observed_today(), counts)
        if kind == "position":
            organization_label = metadata.get("organizationLabel")
            if not organization_label:
                raise ValueError(f"Position candidate {candidate['candidate_id']} lacks organizationLabel")
            organization_id = self._target_id(cursor, {"object_label": organization_label}, "", "", counts)
            return self._ensure_position(cursor, candidate["subject_label"], organization_id, observed_today(), counts)
        return self._ensure_organization(
            cursor,
            candidate["subject_label"],
            metadata.get("organizationType", "federal_entity"),
            metadata.get("organizationType", "federal_entity"),
            observed_today(),
            ["apf_loapf" if metadata.get("apfSector") == "centralizada" else "apf_paraestatales"],
            counts,
        )

    def _ensure_organization(
        self, cursor: psycopg.Cursor, label: str, category: str, organization_type: str,
        observed_on: date, source_ids: list[str], counts: dict,
    ) -> str:
        canonical_slug = slugify(label)
        if label == "Oficina de la Presidencia de la República":
            canonical_slug = "presidencia-de-la-republica"
        existing = self._node_id(cursor, canonical_slug)
        node_id = existing or stable_id(f"node/{canonical_slug}")
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'organization', %s, %s, %s, %s, 'executive', daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (slug) DO UPDATE SET
              canonical_name = EXCLUDED.canonical_name,
              short_name = EXCLUDED.short_name,
              category = EXCLUDED.category,
              metadata = nodes.metadata || EXCLUDED.metadata
            RETURNING id::text, (xmax = 0) AS inserted
            """,
            (node_id, canonical_slug, label, label, f"Entidad de la Administración Pública Federal: {label}.",
             category, observed_on, json.dumps({"jurisdiction": "Federal", "sourceIds": source_ids})),
        )
        stored_id, inserted = cursor.fetchone()
        counts["nodes"] += int(inserted)
        cursor.execute(
            """
            INSERT INTO organizations (node_id, organization_type)
            VALUES (%s, %s)
            ON CONFLICT (node_id) DO UPDATE SET organization_type = EXCLUDED.organization_type
            RETURNING (xmax = 0) AS inserted
            """,
            (stored_id, organization_type),
        )
        counts["organizations"] += int(cursor.fetchone()[0])
        return stored_id

    def _ensure_person(self, cursor: psycopg.Cursor, label: str, metadata: dict, observed_on: date, counts: dict) -> str:
        node_id = stable_id(f"node/person/{slugify(label)}")
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'person', %s, %s, '', 'public_official', 'executive', daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (slug) DO NOTHING RETURNING id::text
            """,
            (node_id, slugify(label), label, label, observed_on, json.dumps({"jurisdiction": "Federal"})),
        )
        row = cursor.fetchone()
        stored_id = row[0] if row else self._node_id(cursor, slugify(label))
        counts["nodes"] += int(row is not None)
        given, family = person_name_parts(label, metadata)
        cursor.execute(
            "INSERT INTO persons (node_id, given_names, family_names) VALUES (%s, %s, %s) ON CONFLICT (node_id) DO NOTHING RETURNING node_id",
            (stored_id, given, family),
        )
        counts["persons"] += int(cursor.fetchone() is not None)
        return stored_id

    def _ensure_position(self, cursor: psycopg.Cursor, label: str, organization_id: str, observed_on: date, counts: dict) -> str:
        node_id = stable_id(f"node/position/{organization_id}/{slugify(label)}")
        slug = f"{slugify(label)}-{str(organization_id)[:8]}"
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'position', %s, %s, '', 'public_office', 'executive', daterange(%s, NULL, '[)'), '{"jurisdiction":"Federal"}'::jsonb)
            ON CONFLICT (slug) DO NOTHING RETURNING id::text
            """,
            (node_id, slug, label, label, observed_on),
        )
        row = cursor.fetchone()
        stored_id = row[0] if row else self._node_id(cursor, slug)
        counts["nodes"] += int(row is not None)
        cursor.execute(
            "INSERT INTO positions (node_id, organization_id, position_type) VALUES (%s, %s, 'public_office') ON CONFLICT (node_id) DO NOTHING RETURNING node_id",
            (stored_id, organization_id),
        )
        counts["positions"] += int(cursor.fetchone() is not None)
        return stored_id

    @staticmethod
    def _latest_snapshot(cursor: psycopg.Cursor, source_slug: str) -> tuple[str, date]:
        cursor.execute(
            """
            SELECT ss.id::text, ss.retrieved_at::date
            FROM source_snapshots ss JOIN source_documents sd ON sd.id = ss.source_document_id
            WHERE sd.slug = %s ORDER BY ss.retrieved_at DESC LIMIT 1
            """,
            (source_slug,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"Missing snapshot for {source_slug}")
        return row[0], row[1]

    def _publish_relationship(
        self, cursor: psycopg.Cursor, task: dict, candidate: dict, subject_id: str, target_id: str,
        snapshot_id: str, observed_on: date, counts: dict,
    ) -> str:
        candidate_id = candidate["candidate_id"]
        relationship_id = stable_id(f"relationship/{candidate_id}")
        assertion_id = stable_id(f"assertion/{task['id']}")
        fragment_id = stable_id(f"fragment/{candidate_id}")
        relationship_slug = f"{candidate.get('predicate', 'relationship').lower()}-{candidate_id}"
        metadata = candidate.get("metadata") or {}
        cursor.execute(
            """
            INSERT INTO relationships (id, slug, relationship_type, relationship_class, source_node_id, target_node_id, label, description, valid_during, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            (relationship_id, relationship_slug, candidate.get("predicate", "PART_OF"),
             "tenure" if candidate.get("predicate") == "HOLDS" else "structure", subject_id, target_id,
             candidate.get("predicate", "PART_OF"),
             f"{candidate.get('subject_label')} {candidate.get('predicate', 'PART_OF')} {candidate.get('object_label')}.",
             observed_on, json.dumps({"mode": metadata.get("mode", "organization"), "legalBasis": metadata.get("legalBasis", candidate.get("source_locator"))})),
        )
        counts["relationships"] += int(cursor.fetchone() is not None)
        cursor.execute(
            """
            INSERT INTO assertions (id, assertion_type, subject_node_id, predicate, object_node_id, relationship_id, valid_during, observed_at, extraction_method, confidence, status, reviewed_by, reviewed_at, published_at)
            VALUES (%s, 'relationship', %s, %s, %s, %s, daterange(%s, NULL, '[)'), now(), 'approved_candidate', 1, 'published', 'editorial-batch-apf', now(), now())
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            (assertion_id, subject_id, candidate.get("predicate", "PART_OF"), target_id, relationship_id, observed_on),
        )
        counts["assertions"] += int(cursor.fetchone() is not None)
        excerpt = candidate.get("source_excerpt") or candidate.get("subject_label", "")
        cursor.execute(
            """
            INSERT INTO source_fragments (id, snapshot_id, locator, fragment_text, fragment_hash)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
            """,
            (fragment_id, snapshot_id, candidate.get("source_locator", ""), excerpt, sha256(excerpt.encode()).hexdigest()),
        )
        cursor.execute(
            "INSERT INTO evidence_links (assertion_id, source_fragment_id) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING assertion_id",
            (assertion_id, fragment_id),
        )
        counts["evidence_links"] += int(cursor.fetchone() is not None)
        return relationship_id
