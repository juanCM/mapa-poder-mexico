from hashlib import sha256
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult


class DofAdapter(SourceAdapter):
    key = "dof"

    def discover(self) -> list[DiscoveredDocument]:
        return [DiscoveredDocument(self.key, "https://www.dof.gob.mx/", "Diario Oficial de la Federación", "Secretaría de Gobernación", "official_gazette")]

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        soup = BeautifulSoup(result.content, "html.parser")
        candidates: list[CandidateAssertion] = []
        for anchor in soup.select("a[href*='nota_detalle']"):
            title = anchor.get_text(" ", strip=True)
            if len(title) < 20:
                continue
            url = urljoin(result.final_url, anchor.get("href", ""))
            candidate_id = sha256(f"{self.key}:publication:{url}".encode()).hexdigest()[:24]
            candidates.append(CandidateAssertion(
                candidate_id=candidate_id,
                source_key=self.key,
                subject_label=title,
                predicate="OFFICIAL_PUBLICATION",
                object_label=None,
                literal_value=url,
                source_locator="Edición del día",
                source_excerpt=title[:500],
                confidence=0.98,
                extraction_method="deterministic_html",
            ))
        return candidates
