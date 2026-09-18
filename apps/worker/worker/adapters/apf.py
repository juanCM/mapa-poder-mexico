"""Fuentes canónicas para la Administración Pública Federal (APF).

La Ley Orgánica de la Administración Pública Federal (LOAPF) define la
Administración Pública Centralizada. La relación de entidades paraestatales se
publica periódicamente en el Diario Oficial de la Federación (DOF). Ninguna de
las dos fuentes, por sí sola, contiene todas las personas servidoras públicas;
por esa razón este adaptador sólo emite candidatos verificables y no publica
ocupaciones automáticamente.
"""

from __future__ import annotations

import re
from hashlib import sha256
from unicodedata import normalize

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult

LOAPF_URL = "https://www.diputados.gob.mx/LeyesBiblio/pdf/LOAPF.pdf"
PARAESTATAL_URL = "https://sidof.segob.gob.mx/notas/docFuente/5735614"

# Artículos 1, 2 y 26 de la LOAPF.  Esta lista deliberadamente usa las
# denominaciones legales completas: el parser nunca debe convertir un apodo de
# navegación (por ejemplo, "Hacienda") en el nombre canónico de una entidad.
CENTRAL_APF = (
    "Oficina de la Presidencia de la República",
    "Secretaría de Gobernación",
    "Secretaría de Relaciones Exteriores",
    "Secretaría de la Defensa Nacional",
    "Secretaría de Marina",
    "Secretaría de Seguridad y Protección Ciudadana",
    "Secretaría de Hacienda y Crédito Público",
    "Secretaría de Bienestar",
    "Secretaría de Medio Ambiente y Recursos Naturales",
    "Secretaría de Energía",
    "Secretaría de Economía",
    "Secretaría de Agricultura y Desarrollo Rural",
    "Secretaría de Infraestructura, Comunicaciones y Transportes",
    "Secretaría Anticorrupción y Buen Gobierno",
    "Secretaría de Educación Pública",
    "Secretaría de Ciencia, Humanidades, Tecnología e Innovación",
    "Secretaría de Salud",
    "Secretaría del Trabajo y Previsión Social",
    "Secretaría de Desarrollo Agrario, Territorial y Urbano",
    "Secretaría de Cultura",
    "Secretaría de Turismo",
    "Secretaría de las Mujeres",
    "Agencia de Transformación Digital y Telecomunicaciones",
    "Consejería Jurídica del Ejecutivo Federal",
)


def folded(value: str) -> str:
    """Compara texto de HTML sin depender de acentos, mayúsculas o espacios."""
    value = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", value.casefold()).strip()


def candidate_id(kind: str, name: str) -> str:
    return sha256(f"apf:{kind}:{folded(name)}".encode()).hexdigest()[:24]


class ApfCatalogAdapter(SourceAdapter):
    """Genera el catálogo base central y detecta entidades paraestatales del DOF.

    El catálogo central se conserva como lista legal versionada porque la LOAPF
    oficial se distribuye como PDF. El snapshot del PDF queda enlazado a cada
    tarea. La relación paraestatal se interpreta de manera conservadora: sólo
    se aceptan filas/tablas que se identifiquen como entidad y se excluyen
    encabezados, números de página y sectores.
    """

    key = "apf_catalog"

    def discover(self) -> list[DiscoveredDocument]:
        return [
            DiscoveredDocument(
                "apf_loapf",
                LOAPF_URL,
                "Ley Orgánica de la Administración Pública Federal",
                "Cámara de Diputados",
                "constitutionally_defined_catalog",
            ),
            DiscoveredDocument(
                "apf_paraestatales",
                PARAESTATAL_URL,
                "Relación de las Entidades Paraestatales de la Administración Pública Federal",
                "Secretaría de Hacienda y Crédito Público / DOF",
                "official_register",
            ),
        ]

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        if result.document.source_key == "apf_loapf":
            return [self._central_candidate(name) for name in CENTRAL_APF]
        return self._paraestatal_candidates(result)

    def _central_candidate(self, name: str) -> CandidateAssertion:
        return CandidateAssertion(
            candidate_id=candidate_id("central", name),
            source_key=self.key,
            subject_label=name,
            predicate="PART_OF",
            object_label="Poder Ejecutivo Federal",
            literal_value=None,
            source_locator="LOAPF, artículos 1, 2 y 26",
            source_excerpt=name,
            confidence=1.0,
            extraction_method="curated_legal_catalog",
            subject_kind="organization",
            object_kind="organization",
            metadata={"apfSector": "centralizada", "organizationType": "federal_dependency"},
        )

    def _paraestatal_candidates(self, result: FetchResult) -> list[CandidateAssertion]:
        if result.mime_type == "application/pdf":
            # La extracción de PDF se incorpora después de guardar el
            # documento. No se adivinan nombres a partir de bytes binarios.
            return []
        soup = BeautifulSoup(result.content, "html.parser")
        values = self._dof_entity_values(soup)
        candidates: list[CandidateAssertion] = []
        for value in values:
            name = re.sub(r"^\s*(?:\d+|[IVXLCDM]+)[.)-]\s*", "", value).strip(" -:;")
            if not self._looks_like_entity(name):
                continue
            candidates.append(CandidateAssertion(
                candidate_id=candidate_id("paraestatal", name),
                source_key=self.key,
                subject_label=name,
                predicate="PART_OF",
                object_label="Administración Pública Federal Paraestatal",
                literal_value=None,
                source_locator="Relación de Entidades Paraestatales de la APF",
                source_excerpt=name,
                confidence=0.94,
                extraction_method="deterministic_table_html",
                subject_kind="organization",
                object_kind="organization",
                metadata={"apfSector": "paraestatal", "organizationType": "paraestatal_entity"},
            ))
        return candidates

    @staticmethod
    def _dof_entity_values(soup: BeautifulSoup) -> list[str]:
        """Obtiene únicamente el apartado A del documento fuente del DOF.

        El lector principal del DOF incorpora el contenido real dentro de un
        iframe ``docFuente`` y usa ``div.ROMANOS`` para cada entidad. Acotar la
        búsqueda a dicho apartado evita confundir enlaces de navegación, notas
        explicativas o entidades en proceso de desincorporación con el padrón
        vigente.
        """
        values: list[str] = []
        in_current_catalog = False
        for element in soup.select("div"):
            text = element.get_text(" ", strip=True)
            text_folded = folded(text)
            if text_folded.startswith("a. entidades paraestatales de la administracion publica federal"):
                in_current_catalog = True
                continue
            if text_folded.startswith("b. entidades paraestatales en proceso de desincorporacion"):
                break
            if in_current_catalog and "ROMANOS" in (element.get("class") or []):
                values.append(text)
        return values

    @staticmethod
    def _looks_like_entity(value: str) -> bool:
        compact = re.sub(r"\s+", " ", value).strip()
        if not 4 <= len(compact) <= 240 or compact.isdigit():
            return False
        rejected = ("entidad", "sector", "dependencia", "relacion de", "secretaria", "subtotal", "total")
        return not any(folded(compact).startswith(prefix) for prefix in rejected)
