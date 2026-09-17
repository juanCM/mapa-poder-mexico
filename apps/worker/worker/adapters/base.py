from abc import ABC, abstractmethod
from hashlib import sha256

import httpx
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult


class SourceAdapter(ABC):
    key: str

    @abstractmethod
    def discover(self) -> list[DiscoveredDocument]:
        raise NotImplementedError

    def fetch(self, document: DiscoveredDocument) -> FetchResult:
        headers = {"User-Agent": "MapaPoderMexico/0.1 (+public-interest research)"}
        with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as client:
            response = client.get(document.url)
            response.raise_for_status()
        return FetchResult(
            document=document,
            final_url=str(response.url),
            status_code=response.status_code,
            mime_type=response.headers.get("content-type", "application/octet-stream").split(";")[0],
            content=response.content,
        )

    @staticmethod
    def fingerprint(content: bytes) -> str:
        return sha256(content).hexdigest()

    @abstractmethod
    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        raise NotImplementedError

    def normalize(self, candidates: list[CandidateAssertion]) -> list[CandidateAssertion]:
        unique: dict[str, CandidateAssertion] = {}
        for candidate in candidates:
            unique[candidate.candidate_id] = candidate
        return list(unique.values())

    def emit_candidates(self, result: FetchResult) -> list[CandidateAssertion]:
        return self.normalize(self.parse(result))
