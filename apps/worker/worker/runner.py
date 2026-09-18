import json
import os
from datetime import datetime
from pathlib import Path

from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion
from worker.sink import PostgresReviewSink
from worker.storage import LocalSnapshotStorage, SupabaseSnapshotStorage


class IngestionRunner:
    def __init__(self, adapter: SourceAdapter):
        self.adapter = adapter
        self.database_url = os.getenv("DATABASE_URL")
        if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
            self.storage = SupabaseSnapshotStorage(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                os.getenv("SUPABASE_STORAGE_BUCKET", "source-documents"),
            )
        else:
            self.storage = LocalSnapshotStorage(Path(os.getenv("INGESTION_STORAGE_DIR", "./storage")))

    def run(self) -> dict:
        sink = PostgresReviewSink(self.database_url) if self.database_url else None
        run_id = sink.start_run(self.adapter.key) if sink else None
        all_candidates: list[CandidateAssertion] = []
        snapshots = 0
        try:
            documents = self.adapter.discover()
            if sink and run_id:
                sink.record_discovered_count(run_id, len(documents))
            for document in documents:
                fetched = self.adapter.fetch(document)
                digest = self.adapter.fingerprint(fetched.content)
                extension = extension_for(fetched.mime_type)
                key = f"{self.adapter.key}/{fetched.retrieved_at:%Y/%m/%d}/{digest}.{extension}"
                storage_path = self.storage.put(key, fetched.content, fetched.mime_type)
                inserted = sink.record_snapshot(run_id, fetched, digest, storage_path) if sink and run_id else True
                snapshots += int(inserted)
                all_candidates.extend(self.adapter.emit_candidates(fetched))
            persisted = sink.emit(run_id, all_candidates) if sink and run_id else 0
            return {
                "adapter": self.adapter.key,
                "finishedAt": datetime.now().astimezone().isoformat(),
                "snapshots": snapshots,
                "candidates": len(all_candidates),
                "persistedReviewTasks": persisted,
                "status": "succeeded",
                "items": [candidate.as_dict() for candidate in all_candidates],
            }
        except Exception as exc:
            if sink and run_id:
                sink.fail(run_id, str(exc))
            raise


def extension_for(mime_type: str) -> str:
    return {"text/html": "html", "application/pdf": "pdf", "application/json": "json", "text/csv": "csv"}.get(mime_type, "bin")


def dump_result(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
