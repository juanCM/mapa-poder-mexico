from hashlib import sha256

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult

DEPENDENCY_NAMES = {
    "Agricultura", "Bienestar", "Buen Gobierno", "Ciencia y Tecnología",
    "Comunicaciones", "Consejería Jurídica", "Cultura", "Defensa",
    "Desarrollo Territorial", "Economía", "Educación", "Energía",
    "Gobernación", "Hacienda", "Marina", "Medio Ambiente", "Mujeres",
    "Relaciones Exteriores", "Salud", "Seguridad", "Trabajo",
    "Transformación Digital", "Turismo",
}


class GobiernoMxAdapter(SourceAdapter):
    key = "gobierno_mx"

    def discover(self) -> list[DiscoveredDocument]:
        return [DiscoveredDocument(self.key, "https://www.gob.mx/gobierno", "Gobierno de México", "Gobierno de México", "official_directory")]

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        soup = BeautifulSoup(result.content, "html.parser")
        values = {element.get_text(" ", strip=True) for element in soup.select("li, h2, h3, h4, a")}
        candidates: list[CandidateAssertion] = []
        for name in sorted(DEPENDENCY_NAMES.intersection(values)):
            candidate_id = sha256(f"{self.key}:dependency:{name}".encode()).hexdigest()[:24]
            candidates.append(CandidateAssertion(
                candidate_id=candidate_id,
                source_key=self.key,
                subject_label=name,
                predicate="PART_OF",
                object_label="Poder Ejecutivo Federal",
                literal_value=None,
                source_locator="Sección Dependencias",
                source_excerpt=name,
                confidence=0.97,
                extraction_method="deterministic_html",
            ))
        return candidates
