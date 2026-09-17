from hashlib import sha256
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult


class LeyesBiblioAdapter(SourceAdapter):
    key = "leyesbiblio"

    def discover(self) -> list[DiscoveredDocument]:
        return [DiscoveredDocument(self.key, "https://www.diputados.gob.mx/LeyesBiblio/index.htm", "Leyes Federales de México", "Cámara de Diputados", "legal_index")]

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        soup = BeautifulSoup(result.content, "html.parser")
        candidates: list[CandidateAssertion] = []
        for anchor in soup.select("a[href]"):
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "")
            if not title or not (href.lower().endswith(".pdf") or "ref/" in href):
                continue
            if not any(word in title.casefold() for word in ("constitución", "orgánica", "fiscalización")):
                continue
            url = urljoin(result.final_url, href)
            candidate_id = sha256(f"{self.key}:instrument:{url}".encode()).hexdigest()[:24]
            candidates.append(CandidateAssertion(
                candidate_id=candidate_id,
                source_key=self.key,
                subject_label=title,
                predicate="HAS_CANONICAL_INDEX_ENTRY",
                object_label=None,
                literal_value=url,
                source_locator="Índice de leyes federales",
                source_excerpt=title,
                confidence=0.99,
                extraction_method="deterministic_html",
            ))
        return candidates
