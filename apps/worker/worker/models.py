from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DiscoveredDocument:
    source_key: str
    url: str
    title: str
    publisher: str
    source_type: str


@dataclass(frozen=True)
class FetchResult:
    document: DiscoveredDocument
    final_url: str
    status_code: int
    mime_type: str
    content: bytes
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CandidateAssertion:
    candidate_id: str
    source_key: str
    subject_label: str
    predicate: str
    object_label: str | None
    literal_value: str | None
    source_locator: str
    source_excerpt: str
    confidence: float
    extraction_method: str
    # Estos campos permiten que la cola editorial distinga un hallazgo de
    # catálogo (institución/persona/cargo) de una relación. Son opcionales
    # para mantener la compatibilidad con los adaptadores legales existentes.
    subject_kind: str | None = None
    object_kind: str | None = None
    jurisdiction: str = "Federal"
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "needs_review"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
