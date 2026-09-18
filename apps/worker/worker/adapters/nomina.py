"""Consulta paginada de personas servidoras públicas en Nómina Transparente."""

from __future__ import annotations

import json
import os
from hashlib import sha256

import httpx
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult

DEFAULT_ENDPOINT = "https://services.buengobierno.gob.mx/nomina/consultas/"
QUERY = """
query consultaNominaPorRamoPaginado($ramo: Int!, $ur: String!, $seccion: Seccion!, $sn: Boolean!) {
  consultaNominaPorRamoPaginado(ramo: $ramo, ur: $ur, sn: $sn, seccion: $seccion) {
    listDtoServidorPublicoDto { institution: dependencia puesto: nombrePuesto nombre ramo idUr }
  }
}
"""


class NominaTransparenteAdapter(SourceAdapter):
    """Ingiere una página acotada, nunca el padrón completo en una ejecución.

    Variables requeridas: ``NOMINA_TRANSPARENTE_API_KEY`` y
    ``NOMINA_APF_RAMO``. Las variables ``NOMINA_APF_UR``,
    ``NOMINA_APF_OFFSET`` y ``NOMINA_APF_LIMIT`` permiten retomar la carga en
    lotes idempotentes. La clave pública del portal no se almacena en el repo.
    """

    key = "nomina_transparente_apf"

    def discover(self) -> list[DiscoveredDocument]:
        ramo = os.environ["NOMINA_APF_RAMO"]
        ur = os.getenv("NOMINA_APF_UR", "0")
        offset = os.getenv("NOMINA_APF_OFFSET", "0")
        return [DiscoveredDocument(
            f"nomina_apf_{ramo}_{ur}_{offset}",
            os.getenv("NOMINA_TRANSPARENTE_ENDPOINT", DEFAULT_ENDPOINT),
            f"Nómina Transparente APF — ramo {ramo}, UR {ur}, página {offset}",
            "Secretaría Anticorrupción y Buen Gobierno",
            "official_public_payroll",
        )]

    def fetch(self, document: DiscoveredDocument) -> FetchResult:
        api_key = os.environ["NOMINA_TRANSPARENTE_API_KEY"]
        ramo = int(os.environ["NOMINA_APF_RAMO"])
        ur = os.getenv("NOMINA_APF_UR", "0")
        offset = int(os.getenv("NOMINA_APF_OFFSET", "0"))
        limit = int(os.getenv("NOMINA_APF_LIMIT", "100"))
        payload = {
            "operationName": "consultaNominaPorRamoPaginado",
            "query": QUERY,
            "variables": {"ramo": ramo, "ur": ur, "seccion": {"inicio": offset, "limite": limit}, "sn": False},
        }
        with httpx.Client(timeout=60, headers={"Content-Type": "application/json", "Accept": "application/json", "apikey": api_key}) as client:
            response = client.post(document.url, json=payload)
            response.raise_for_status()
        return FetchResult(document, str(response.url), response.status_code, "application/json", response.content)

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        payload = json.loads(result.content)
        records = payload.get("data", {}).get("consultaNominaPorRamoPaginado", {}).get("listDtoServidorPublicoDto", [])
        candidates: list[CandidateAssertion] = []
        for record in records:
            person = str(record.get("nombre") or "").strip()
            position = str(record.get("puesto") or "").strip()
            organization = str(record.get("institution") or "").strip()
            if not person or not position or not organization:
                continue
            identifier = sha256(f"{person}|{position}|{organization}|{record.get('ramo')}|{record.get('idUr')}".encode()).hexdigest()[:24]
            candidates.append(CandidateAssertion(
                candidate_id=identifier,
                source_key=self.key,
                subject_label=person,
                predicate="HOLDS",
                object_label=position,
                literal_value=None,
                source_locator=f"Ramo {record.get('ramo', '')}; UR {record.get('idUr', '')}",
                source_excerpt=f"{person} — {position} — {organization}",
                confidence=0.98,
                extraction_method="official_graphql_page",
                subject_kind="person",
                object_kind="position",
                metadata={
                    "positionOrganizationLabel": organization,
                    "employmentSource": "nomina_transparente",
                    "sourceDocumentSlug": result.document.source_key,
                },
            ))
        return candidates
