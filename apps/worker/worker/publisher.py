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


def effective_date(candidate: dict, fallback: date) -> date:
    value = (candidate.get("metadata") or {}).get("validFrom")
    if not value:
        return fallback
    return date.fromisoformat(str(value)[:10])


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
    tenures: int
    change_events: int

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

    def publish(
        self,
        adapter_key: str | None = None,
        limit: int | None = None,
        batch_id: str | None = None,
    ) -> PublicationResult:
        counts = {
            "tasks": 0, "nodes": 0, "organizations": 0, "positions": 0,
            "persons": 0, "relationships": 0, "assertions": 0, "evidence_links": 0,
            "tenures": 0, "change_events": 0,
        }
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            tasks = self._approved_tasks(cursor, adapter_key, batch_id, limit)
            if not tasks:
                return PublicationResult(**counts)

            executive_id = self._node_id(cursor, EXECUTIVE_SLUG)
            if not executive_id:
                raise RuntimeError("Missing canonical Poder Ejecutivo Federal node")

            needs_paraestatal_root = any(
                task["candidate"].get("object_label") == PARAESTATAL_LABEL
                or (task["candidate"].get("metadata") or {}).get("apfSector") == "paraestatal"
                for task in tasks
            )
            paraestatal_id = (
                self._ensure_paraestatal_root(cursor, executive_id, counts)
                if needs_paraestatal_root
                else (self._node_id(cursor, slugify(PARAESTATAL_LABEL)) or "")
            )
            for task in tasks:
                candidate = task["candidate"]
                source_slug = self._source_slug(candidate)
                snapshot_id, source_document_id, observed_on = self._latest_snapshot(cursor, source_slug)
                target_id = self._target_id(cursor, candidate, executive_id, paraestatal_id, observed_on, counts)
                subject_id = self._ensure_subject(
                    cursor, candidate, source_document_id, observed_on, executive_id, paraestatal_id, counts
                )
                self._publish_relationship(
                    cursor, task, candidate, subject_id, target_id, snapshot_id, observed_on, counts
                )
                if candidate.get("predicate") == "HOLDS":
                    self._publish_position_structure(
                        cursor, task, candidate, target_id, snapshot_id, observed_on, counts
                    )
                    self._materialize_tenure(
                        cursor, task, candidate, subject_id, target_id, observed_on, counts
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
            cursor.execute(
                """
                UPDATE review_batches rb
                SET status = CASE
                    WHEN EXISTS (SELECT 1 FROM review_tasks rt WHERE rt.batch_id = rb.id AND rt.status IN ('needs_review', 'approved'))
                      THEN 'partially_reviewed'
                    ELSE 'published'
                  END
                WHERE rb.id IN (SELECT DISTINCT batch_id FROM review_tasks WHERE id = ANY(%s::uuid[]))
                """,
                ([task["id"] for task in tasks],),
            )
        return PublicationResult(**counts)

    @staticmethod
    def _approved_tasks(
        cursor: psycopg.Cursor,
        adapter_key: str | None,
        batch_id: str | None,
        limit: int | None,
    ) -> list[dict]:
        cursor.execute(
            """
            SELECT rt.id::text, rt.summary
            FROM review_tasks rt
            JOIN ingestion_runs ir ON ir.id = rt.ingestion_run_id
            WHERE rt.status = 'approved'
              AND (%s::text IS NULL OR ir.adapter_key = %s)
              AND (%s::text IS NULL OR rt.batch_id::text = %s)
            ORDER BY rt.created_at, rt.id LIMIT %s
            """,
            (adapter_key, adapter_key, batch_id, batch_id, limit),
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
        snapshot_id, _, observed_on = self._latest_snapshot(cursor, "apf_loapf")
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
        self, cursor: psycopg.Cursor, candidate: dict, executive_id: str, paraestatal_id: str,
        observed_on: date, counts: dict,
    ) -> str:
        metadata = candidate.get("metadata") or {}
        label = candidate.get("object_label")
        if candidate.get("object_kind") == "position":
            organization_label = metadata.get("positionOrganizationLabel")
            if not organization_label:
                raise ValueError(f"Position target for {candidate['candidate_id']} lacks positionOrganizationLabel")
            organization_id = self._target_id(
                cursor,
                {"object_label": organization_label, "metadata": metadata},
                executive_id,
                paraestatal_id,
                observed_on,
                counts,
            )
            return self._ensure_position(cursor, label, organization_id, metadata, observed_on, counts)
        if label == "Poder Ejecutivo Federal":
            return executive_id
        if label == PARAESTATAL_LABEL:
            if not paraestatal_id:
                raise RuntimeError("Missing canonical paraestatal root")
            return paraestatal_id
        if not label:
            raise ValueError(f"Candidate {candidate['candidate_id']} has no relationship target")
        existing = self._node_id(cursor, slugify(label))
        if existing:
            return existing
        return self._ensure_organization(
            cursor, label, metadata.get("category", "federal_entity"),
            metadata.get("organizationType", "federal_entity"), observed_on, [], counts,
            branch=metadata.get("branch", "executive"),
        )

    @staticmethod
    def _source_slug(candidate: dict) -> str:
        metadata = candidate.get("metadata") or {}
        if metadata.get("sourceDocumentSlug"):
            return metadata["sourceDocumentSlug"]
        return "apf_loapf" if metadata.get("apfSector") == "centralizada" else "apf_paraestatales"

    def _ensure_subject(
        self, cursor: psycopg.Cursor, candidate: dict, source_document_id: str, observed_on: date,
        executive_id: str, paraestatal_id: str, counts: dict,
    ) -> str:
        kind = candidate.get("subject_kind") or "organization"
        metadata = candidate.get("metadata") or {}
        if kind == "person":
            return self._ensure_person(
                cursor, candidate["subject_label"], candidate["candidate_id"], metadata,
                source_document_id, observed_on, counts,
            )
        if kind == "position":
            organization_label = metadata.get("organizationLabel")
            if not organization_label:
                raise ValueError(f"Position candidate {candidate['candidate_id']} lacks organizationLabel")
            organization_id = self._target_id(
                cursor, {"object_label": organization_label, "metadata": metadata},
                executive_id, paraestatal_id, observed_on, counts,
            )
            return self._ensure_position(
                cursor, candidate["subject_label"], organization_id, metadata, observed_on, counts
            )
        return self._ensure_organization(
            cursor,
            candidate["subject_label"],
            metadata.get("organizationType", "federal_entity"),
            metadata.get("organizationType", "federal_entity"),
            observed_on,
            ["apf_loapf" if metadata.get("apfSector") == "centralizada" else "apf_paraestatales"],
            counts,
            branch=metadata.get("branch", "executive"),
        )

    def _ensure_organization(
        self, cursor: psycopg.Cursor, label: str, category: str, organization_type: str,
        observed_on: date, source_ids: list[str], counts: dict, branch: str = "executive",
    ) -> str:
        canonical_slug = slugify(label)
        if label == "Oficina de la Presidencia de la República":
            canonical_slug = "presidencia-de-la-republica"
        existing = self._node_id(cursor, canonical_slug)
        node_id = existing or stable_id(f"node/{canonical_slug}")
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'organization', %s, %s, %s, %s, %s, daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (slug) DO UPDATE SET
              canonical_name = EXCLUDED.canonical_name,
              short_name = EXCLUDED.short_name,
              category = EXCLUDED.category,
              branch = EXCLUDED.branch,
              metadata = nodes.metadata || EXCLUDED.metadata
            RETURNING id::text, (xmax = 0) AS inserted
            """,
            (node_id, canonical_slug, label, label, f"Institución federal: {label}.",
             category, branch, observed_on, json.dumps({"jurisdiction": "Federal", "sourceIds": source_ids})),
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

    def _ensure_person(
        self, cursor: psycopg.Cursor, label: str, candidate_id: str, metadata: dict,
        source_document_id: str, observed_on: date, counts: dict,
    ) -> str:
        identity = metadata.get("officialIdentifier") or metadata.get("officialProfileUrl") or candidate_id
        node_id = stable_id(f"node/person/{identity}")
        base_slug = slugify(label)
        cursor.execute(
            "SELECT id::text, metadata FROM nodes WHERE slug = %s AND kind = 'person'",
            (base_slug,),
        )
        existing = cursor.fetchone()
        if existing and (existing[1] or {}).get("identityKey") == identity:
            person_slug = base_slug
            node_id = existing[0]
        elif existing:
            person_slug = f"{base_slug}-{sha256(str(identity).encode()).hexdigest()[:8]}"
        else:
            person_slug = base_slug
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'person', %s, %s, '', 'public_official', %s, daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
              canonical_name = EXCLUDED.canonical_name,
              short_name = EXCLUDED.short_name,
              metadata = nodes.metadata || EXCLUDED.metadata
            RETURNING id::text, (xmax = 0) AS inserted
            """,
            (
                node_id, person_slug, label, label, metadata.get("branch", "executive"), observed_on,
                json.dumps({"jurisdiction": "Federal", "identityKey": identity}),
            ),
        )
        row = cursor.fetchone()
        stored_id = row[0]
        counts["nodes"] += int(row[1])
        given, family = person_name_parts(label, metadata)
        cursor.execute(
            """
            INSERT INTO persons (
              node_id, given_names, family_names, official_profile_url,
              official_portrait_url, portrait_source_document_id
            )
            VALUES (%s, %s, %s, %s, %s, CASE WHEN %s IS NULL THEN NULL ELSE %s::uuid END)
            ON CONFLICT (node_id) DO UPDATE SET
              given_names = EXCLUDED.given_names,
              family_names = EXCLUDED.family_names,
              official_profile_url = COALESCE(EXCLUDED.official_profile_url, persons.official_profile_url),
              official_portrait_url = COALESCE(EXCLUDED.official_portrait_url, persons.official_portrait_url),
              portrait_source_document_id = CASE
                WHEN EXCLUDED.official_portrait_url IS NOT NULL THEN EXCLUDED.portrait_source_document_id
                ELSE persons.portrait_source_document_id
              END
            RETURNING (xmax = 0) AS inserted
            """,
            (
                stored_id, given, family, metadata.get("officialProfileUrl"),
                metadata.get("officialPortraitUrl"),
                metadata.get("officialPortraitUrl"), source_document_id,
            ),
        )
        counts["persons"] += int(cursor.fetchone()[0])
        return stored_id

    def _ensure_position(
        self, cursor: psycopg.Cursor, label: str, organization_id: str,
        metadata: dict, observed_on: date, counts: dict,
    ) -> str:
        seat_key = metadata.get("seatKey") or slugify(label)
        node_id = stable_id(f"node/position/{organization_id}/{seat_key}")
        slug = f"{slugify(label)}-{sha256(str(seat_key).encode()).hexdigest()[:8]}"
        cursor.execute(
            """
            INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
            VALUES (%s, %s, 'position', %s, %s, '', %s, %s, daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
              canonical_name = EXCLUDED.canonical_name,
              short_name = EXCLUDED.short_name,
              metadata = nodes.metadata || EXCLUDED.metadata
            RETURNING id::text, (xmax = 0) AS inserted
            """,
            (
                node_id, slug, label, label, metadata.get("positionCategory", "public_office"),
                metadata.get("branch", "executive"), observed_on,
                json.dumps({"jurisdiction": "Federal", "occupancyStatus": metadata.get("occupancyStatus", "unrecorded")}),
            ),
        )
        row = cursor.fetchone()
        stored_id = row[0]
        counts["nodes"] += int(row[1])
        cursor.execute(
            """
            INSERT INTO positions (
              node_id, organization_id, position_type, seat_number, selection_method,
              is_elected, is_collegial, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (node_id) DO UPDATE SET
              organization_id = EXCLUDED.organization_id,
              position_type = EXCLUDED.position_type,
              seat_number = EXCLUDED.seat_number,
              selection_method = EXCLUDED.selection_method,
              is_elected = EXCLUDED.is_elected,
              is_collegial = EXCLUDED.is_collegial,
              metadata = positions.metadata || EXCLUDED.metadata
            RETURNING (xmax = 0) AS inserted
            """,
            (
                stored_id, organization_id, metadata.get("positionType", "public_office"),
                metadata.get("seatNumber"), metadata.get("selectionMethod"),
                bool(metadata.get("isElected", False)), bool(metadata.get("isCollegial", False)),
                json.dumps({key: value for key, value in metadata.items() if value is not None}),
            ),
        )
        counts["positions"] += int(cursor.fetchone()[0])
        return stored_id

    @staticmethod
    def _latest_snapshot(cursor: psycopg.Cursor, source_slug: str) -> tuple[str, str, date]:
        cursor.execute(
            """
            SELECT ss.id::text, sd.id::text, ss.retrieved_at::date
            FROM source_snapshots ss JOIN source_documents sd ON sd.id = ss.source_document_id
            WHERE sd.slug = %s ORDER BY ss.retrieved_at DESC LIMIT 1
            """,
            (source_slug,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"Missing snapshot for {source_slug}")
        return row[0], row[1], row[2]

    def _publish_position_structure(
        self, cursor: psycopg.Cursor, task: dict, candidate: dict, position_id: str,
        snapshot_id: str, observed_on: date, counts: dict,
    ) -> None:
        cursor.execute("SELECT organization_id::text FROM positions WHERE node_id = %s", (position_id,))
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"Position {position_id} has no organization")
        organization_id = row[0]
        structure_candidate = {
            "candidate_id": f"position-structure-{position_id}",
            "predicate": "PART_OF",
            "subject_label": candidate.get("object_label"),
            "object_label": (candidate.get("metadata") or {}).get("positionOrganizationLabel"),
            "source_locator": candidate.get("source_locator", "Directorio oficial"),
            "source_excerpt": candidate.get("source_excerpt", ""),
            "metadata": {
                "mode": "organization",
                "legalBasis": (candidate.get("metadata") or {}).get("legalBasis", candidate.get("source_locator")),
                "relationshipClass": "structure",
                "validFrom": (candidate.get("metadata") or {}).get("validFrom"),
            },
        }
        structure_task = {"id": stable_id(f"task-position-structure/{task['id']}")}
        self._publish_relationship(
            cursor, structure_task, structure_candidate, position_id, organization_id,
            snapshot_id, observed_on, counts,
        )

    def _materialize_tenure(
        self, cursor: psycopg.Cursor, task: dict, candidate: dict, person_id: str,
        position_id: str, observed_on: date, counts: dict,
    ) -> None:
        metadata = candidate.get("metadata") or {}
        starts_on = effective_date(candidate, observed_on)
        status = metadata.get("occupancyStatus", "confirmed")
        if status not in ("confirmed", "acting"):
            status = "confirmed"
        self._close_previous_occupancies(cursor, person_id, position_id, starts_on, counts)
        tenure_id = stable_id(f"tenure/{task['id']}")
        cursor.execute(
            """
            INSERT INTO tenures (
              id, person_id, position_id, status, selection_method, valid_during
            )
            VALUES (%s, %s, %s, %s, %s, daterange(%s, NULL, '[)'))
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            (tenure_id, person_id, position_id, status, metadata.get("selectionMethod"), starts_on),
        )
        counts["tenures"] += int(cursor.fetchone() is not None)
        event_id = stable_id(f"change/{task['id']}")
        assertion_id = stable_id(f"assertion/{task['id']}")
        cursor.execute(
            """
            INSERT INTO government_change_events (
              id, event_type, title, description, occurred_on, primary_node_id, assertion_id
            )
            VALUES (%s, 'officeholder_changed', %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            (
                event_id,
                f"Titularidad de {candidate.get('object_label')}",
                f"{candidate.get('subject_label')} ocupa {candidate.get('object_label')}.",
                starts_on, position_id, assertion_id,
            ),
        )
        counts["change_events"] += int(cursor.fetchone() is not None)

    @staticmethod
    def _close_previous_occupancies(
        cursor: psycopg.Cursor, person_id: str, position_id: str, starts_on: date, counts: dict,
    ) -> None:
        cursor.execute(
            """
            SELECT id::text, person_id::text, lower(valid_during)
            FROM tenures
            WHERE position_id = %s AND retired_at IS NULL
              AND valid_during @> %s::date AND person_id <> %s
            FOR UPDATE
            """,
            (position_id, starts_on, person_id),
        )
        previous = cursor.fetchall()
        for tenure_id, previous_person_id, previous_start in previous:
            if previous_start >= starts_on:
                raise ValueError(f"Cannot close tenure {tenure_id}: replacement date is not later")
            cursor.execute(
                "UPDATE tenures SET valid_during = daterange(%s, %s, '[)') WHERE id = %s",
                (previous_start, starts_on, tenure_id),
            )
            cursor.execute(
                """
                SELECT r.id::text, a.id::text
                FROM relationships r
                JOIN assertions a ON a.relationship_id = r.id AND a.status = 'published'
                WHERE r.relationship_type = 'HOLDS' AND r.source_node_id = %s
                  AND r.target_node_id = %s AND r.valid_during @> %s::date
                ORDER BY a.published_at DESC LIMIT 1
                """,
                (previous_person_id, position_id, starts_on),
            )
            relationship = cursor.fetchone()
            if not relationship:
                continue
            relationship_id, old_assertion_id = relationship
            corrected_assertion_id = stable_id(f"assertion/closed/{old_assertion_id}/{starts_on.isoformat()}")
            cursor.execute(
                """
                INSERT INTO assertions (
                  id, assertion_type, subject_node_id, predicate, object_node_id,
                  relationship_id, valid_during, observed_at, extraction_method,
                  confidence, status, supersedes_assertion_id, reviewed_by, reviewed_at, published_at
                )
                SELECT %s, assertion_type, subject_node_id, predicate, object_node_id,
                       relationship_id, daterange(lower(valid_during), %s, '[)'), now(),
                       'approved_replacement', confidence, 'published', id,
                       'editorial-batch', now(), now()
                FROM assertions WHERE id = %s
                ON CONFLICT (id) DO NOTHING RETURNING id
                """,
                (corrected_assertion_id, starts_on, old_assertion_id),
            )
            inserted = cursor.fetchone() is not None
            counts["assertions"] += int(inserted)
            if inserted:
                cursor.execute(
                    """
                    INSERT INTO evidence_links (assertion_id, source_fragment_id, legal_provision_id, supports, note)
                    SELECT %s, source_fragment_id, legal_provision_id, supports, note
                    FROM evidence_links WHERE assertion_id = %s
                    ON CONFLICT DO NOTHING
                    """,
                    (corrected_assertion_id, old_assertion_id),
                )
                counts["evidence_links"] += cursor.rowcount
            cursor.execute("UPDATE assertions SET status = 'superseded' WHERE id = %s", (old_assertion_id,))
            cursor.execute(
                "UPDATE relationships SET valid_during = daterange(lower(valid_during), %s, '[)') WHERE id = %s",
                (starts_on, relationship_id),
            )

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
        starts_on = effective_date(candidate, observed_on)
        relationship_class = metadata.get("relationshipClass") or (
            "tenure" if candidate.get("predicate") == "HOLDS" else "structure"
        )
        cursor.execute(
            """
            INSERT INTO relationships (id, slug, relationship_type, relationship_class, source_node_id, target_node_id, label, description, valid_during, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, daterange(%s, NULL, '[)'), %s::jsonb)
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            (relationship_id, relationship_slug, candidate.get("predicate", "PART_OF"),
             relationship_class, subject_id, target_id,
             candidate.get("predicate", "PART_OF"),
             f"{candidate.get('subject_label')} {candidate.get('predicate', 'PART_OF')} {candidate.get('object_label')}.",
             starts_on, json.dumps({
                 "mode": metadata.get("mode", "organization"),
                 "legalBasis": metadata.get("legalBasis", candidate.get("source_locator")),
                 "occupancyStatus": metadata.get("occupancyStatus"),
             })),
        )
        counts["relationships"] += int(cursor.fetchone() is not None)
        cursor.execute(
            """
            INSERT INTO assertions (id, assertion_type, subject_node_id, predicate, object_node_id, relationship_id, valid_during, observed_at, extraction_method, confidence, status, reviewed_by, reviewed_at, published_at)
            VALUES (%s, 'relationship', %s, %s, %s, %s, daterange(%s, NULL, '[)'), now(), 'approved_candidate', 1, 'published', 'editorial-batch', now(), now())
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            (assertion_id, subject_id, candidate.get("predicate", "PART_OF"), target_id, relationship_id, starts_on),
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
