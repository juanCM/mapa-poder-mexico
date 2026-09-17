import json
from collections.abc import Iterable

import psycopg

from worker.models import CandidateAssertion, FetchResult


class PostgresReviewSink:
    def __init__(self, database_url: str):
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    def start_run(self, adapter_key: str) -> str:
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ingestion_runs (adapter_key, status, started_at) VALUES (%s, 'running', now()) RETURNING id",
                (adapter_key,),
            )
            return str(cursor.fetchone()[0])

    def emit(self, run_id: str, candidates: Iterable[CandidateAssertion]) -> int:
        count = 0
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            for candidate in candidates:
                cursor.execute(
                    """
                    INSERT INTO review_tasks (ingestion_run_id, candidate_key, title, summary, priority, status)
                    SELECT %s, %s, %s, %s, 'medium', 'needs_review'
                    WHERE NOT EXISTS (
                      SELECT 1 FROM review_tasks
                      WHERE candidate_key = %s AND status = 'needs_review'
                    )
                    """,
                    (
                        run_id,
                        candidate.candidate_id,
                        f"Revisar {candidate.predicate}: {candidate.subject_label}",
                        json.dumps(candidate.as_dict(), ensure_ascii=False),
                        candidate.candidate_id,
                    ),
                )
                count += cursor.rowcount
            cursor.execute(
                "UPDATE ingestion_runs SET candidate_count = %s, status = 'succeeded', finished_at = now() WHERE id = %s",
                (count, run_id),
            )
        return count

    def record_snapshot(
        self,
        run_id: str,
        result: FetchResult,
        content_hash: str,
        storage_path: str,
    ) -> bool:
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO source_documents (slug, publisher, title, canonical_url, source_type, adapter_key)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                  publisher = EXCLUDED.publisher,
                  title = EXCLUDED.title,
                  canonical_url = EXCLUDED.canonical_url,
                  source_type = EXCLUDED.source_type,
                  adapter_key = EXCLUDED.adapter_key
                RETURNING id
                """,
                (
                    result.document.source_key,
                    result.document.publisher,
                    result.document.title,
                    result.document.url,
                    result.document.source_type,
                    result.document.source_key,
                ),
            )
            source_id = cursor.fetchone()[0]
            cursor.execute(
                "SELECT id FROM source_snapshots WHERE source_document_id = %s ORDER BY retrieved_at DESC LIMIT 1",
                (source_id,),
            )
            previous = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO source_snapshots (
                  source_document_id, retrieved_at, final_url, content_hash, mime_type,
                  byte_size, storage_path, http_status, previous_snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_document_id, content_hash) DO NOTHING
                RETURNING id
                """,
                (
                    source_id,
                    result.retrieved_at,
                    result.final_url,
                    content_hash,
                    result.mime_type,
                    len(result.content),
                    storage_path,
                    result.status_code,
                    previous[0] if previous else None,
                ),
            )
            inserted = cursor.fetchone() is not None
            if inserted:
                cursor.execute(
                    "UPDATE ingestion_runs SET snapshot_count = snapshot_count + 1 WHERE id = %s",
                    (run_id,),
                )
            return inserted

    def fail(self, run_id: str, message: str) -> None:
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ingestion_runs SET status = 'failed', error_message = %s, finished_at = now() WHERE id = %s",
                (message[:4000], run_id),
            )
