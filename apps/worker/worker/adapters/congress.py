"""Directorios oficiales de la LXVI Legislatura.

El adaptador modela el asiento antes que a su ocupante. Si una fila oficial
marca una vacante, emite únicamente el cargo estable; nunca inventa una
persona. Un cambio de titular produce otro candidato para el mismo ``seatKey``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from hashlib import sha256
from unicodedata import normalize
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult

CHAMBER_SOURCES = {
    "congreso_lxvi_diputaciones": {
        "url": "https://sitl.diputados.gob.mx/LXVI_leg/listado_diputados_gpnp.php?tipot=T",
        "title": "Listado de Diputadas y Diputados de la LXVI Legislatura",
        "publisher": "Cámara de Diputados",
        "organization": "Cámara de Diputados",
        "expected": 500,
        "chamber": "deputies",
    },
    "congreso_lxvi_senadurias": {
        "url": "https://www.senado.gob.mx/66/senadores",
        "title": "Senadoras y Senadores de la LXVI Legislatura",
        "publisher": "Senado de la República",
        "organization": "Senado de la República",
        "expected": 128,
        "chamber": "senate",
    },
}


def normalized(value: str) -> str:
    return normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower().strip()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \n\r\t|-")


def key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalized(value)).strip("-")


def _field(row: dict[str, str], *names: str) -> str:
    for name in names:
        for header, value in row.items():
            if name in normalized(header):
                return compact(value)
    return ""


def table_records(soup: BeautifulSoup) -> list[tuple[dict[str, str], object]]:
    records: list[tuple[dict[str, str], object]] = []
    for table in soup.select("table"):
        headers = [compact(cell.get_text(" ", strip=True)) for cell in table.select("tr th")]
        if not headers:
            first = table.select_one("tr")
            headers = [compact(cell.get_text(" ", strip=True)) for cell in first.select("td")] if first else []
        if not headers:
            continue
        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            values = [compact(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) > len(headers):
                values = values[-len(headers):]
            if len(values) != len(headers):
                continue
            records.append((dict(zip(headers, values)), row))
    return records


class CongressRosterAdapter(SourceAdapter):
    key = "congress_lxvi"

    def discover(self) -> list[DiscoveredDocument]:
        return [
            DiscoveredDocument(source_key, data["url"], data["title"], data["publisher"], "official_roster")
            for source_key, data in CHAMBER_SOURCES.items()
        ]

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        source = CHAMBER_SOURCES.get(result.document.source_key)
        if not source:
            raise ValueError(f"Unknown Congress source {result.document.source_key}")
        soup = BeautifulSoup(result.content, "html.parser")
        expected = int(soup.select_one("[data-expected-seats]").get("data-expected-seats")) if soup.select_one("[data-expected-seats]") else int(source["expected"])
        records = self._records(soup)
        candidates = self._deputies(records, result, source) if source["chamber"] == "deputies" else self._senate(records, result, source)
        seat_keys = {(candidate.metadata or {}).get("seatKey") for candidate in candidates}
        if len(seat_keys) != expected:
            raise ValueError(
                f"{result.document.source_key} produced {len(seat_keys)} constitutional seats; expected {expected}"
            )
        return candidates

    @staticmethod
    def _records(soup: BeautifulSoup) -> list[tuple[dict[str, str], object]]:
        records = table_records(soup)
        for card in soup.select("[data-legislative-seat]"):
            records.append(({
                "name": card.get("data-person", ""),
                "entity": card.get("data-entity", ""),
                "district": card.get("data-district", ""),
                "circumscription": card.get("data-circumscription", ""),
                "principle": card.get("data-principle", ""),
                "seat": card.get("data-seat", ""),
                "group": card.get("data-parliamentary-group", ""),
            }, card))
        return records

    def _deputies(self, records, result: FetchResult, source: dict) -> list[CandidateAssertion]:
        counters: defaultdict[str, int] = defaultdict(int)
        candidates: list[CandidateAssertion] = []
        for row, element in records:
            name = _field(row, "diputad", "name", "nombre")
            entity = _field(row, "entidad", "entity")
            district_text = _field(row, "distrito", "circunscripcion", "district", "circumscription")
            if not district_text:
                continue
            number_match = re.search(r"\d+", district_text)
            number = int(number_match.group()) if number_match else None
            proportional = "circ" in normalized(district_text)
            if proportional:
                circ = number or 0
                counters[f"rp-{circ}"] += 1
                seat_number = counters[f"rp-{circ}"]
                seat_key = f"diputacion-rp-c{circ}-a{seat_number:03d}"
                position = f"Diputación de representación proporcional · circunscripción {circ} · asiento {seat_number}"
                principle = "representacion_proporcional"
            else:
                if not entity or number is None:
                    continue
                seat_key = f"diputacion-mr-{key(entity)}-d{number:02d}"
                position = f"Diputación federal de {entity} · distrito {number}"
                principle = "mayoria_relativa"
                seat_number = number
            candidates.append(self._candidate(
                result, source, element, name, position, seat_key, seat_number,
                entity, number if not proportional else None, number if proportional else None,
                principle, _field(row, "grupo", "partido"),
            ))
        return candidates

    def _senate(self, records, result: FetchResult, source: dict) -> list[CandidateAssertion]:
        counters: defaultdict[str, int] = defaultdict(int)
        candidates: list[CandidateAssertion] = []
        for row, element in records:
            name = _field(row, "senador", "name", "nombre")
            entity = _field(row, "entidad", "entity")
            raw_principle = _field(row, "principio", "principle")
            raw_seat = _field(row, "escano", "seat", "asiento")
            principle_text = normalized(raw_principle or entity)
            if "lista" in principle_text or "representacion" in principle_text:
                principle = "representacion_proporcional"
                scope = "lista-nacional"
            elif "primera" in principle_text or "minoria" in principle_text:
                principle = "primera_minoria"
                scope = key(entity)
            else:
                principle = "mayoria_relativa"
                scope = key(entity)
            counter_key = f"{principle}-{scope}"
            counters[counter_key] += 1
            seat_number = int(raw_seat) if raw_seat.isdigit() else counters[counter_key]
            seat_key = f"senaduria-{counter_key}-a{seat_number:02d}"
            position = (
                f"Senaduría de lista nacional · asiento {seat_number}"
                if scope == "lista-nacional"
                else f"Senaduría de {entity} · {raw_principle or principle.replace('_', ' ')} · asiento {seat_number}"
            )
            candidates.append(self._candidate(
                result, source, element, name, position, seat_key, seat_number,
                entity, None, None, principle, _field(row, "grupo", "partido"),
            ))
        return candidates

    @staticmethod
    def _candidate(
        result: FetchResult, source: dict, element, name: str, position: str, seat_key: str,
        seat_number: int, entity: str, district: int | None, circumscription: int | None,
        principle: str, parliamentary_group: str,
    ) -> CandidateAssertion:
        profile = element.select_one("a[href]") if hasattr(element, "select_one") else None
        image = element.select_one("img[src]") if hasattr(element, "select_one") else None
        profile_url = urljoin(result.final_url, profile.get("href")) if profile else None
        portrait_url = urljoin(result.final_url, image.get("src")) if image and profile_url else None
        vacant = not name or "vacante" in normalized(name)
        identity = f"{result.document.source_key}:{seat_key}:{'vacant' if vacant else normalized(name)}"
        metadata = {
            "sourceDocumentSlug": result.document.source_key,
            "positionOrganizationLabel": source["organization"],
            "organizationLabel": source["organization"],
            "branch": "legislative",
            "category": "legislative_chamber",
            "organizationType": "legislative_chamber",
            "positionCategory": "legislative_seat",
            "positionType": "legislative_seat",
            "seatKey": seat_key,
            "seatNumber": seat_number,
            "legislature": "LXVI",
            "entity": entity or None,
            "district": district,
            "circumscription": circumscription,
            "electionPrinciple": principle,
            "selectionMethod": principle,
            "parliamentaryGroup": parliamentary_group or None,
            "isElected": True,
            "isCollegial": True,
            "occupancyStatus": "vacant" if vacant else "confirmed",
            "officialProfileUrl": profile_url,
            "officialPortraitUrl": portrait_url,
            "officialIdentifier": profile_url,
            "mode": "both",
            "relationshipClass": "tenure" if not vacant else "structure",
            "legalBasis": "CPEUM, artículos 52 a 56",
        }
        return CandidateAssertion(
            candidate_id=sha256(identity.encode()).hexdigest()[:24],
            source_key=result.document.source_key,
            subject_label=position if vacant else compact(name),
            predicate="PART_OF" if vacant else "HOLDS",
            object_label=source["organization"] if vacant else position,
            literal_value=None,
            source_locator=position,
            source_excerpt=compact(element.get_text(" ", strip=True)) if hasattr(element, "get_text") else position,
            confidence=0.99,
            extraction_method="deterministic_official_roster",
            subject_kind="position" if vacant else "person",
            object_kind="organization" if vacant else "position",
            metadata=metadata,
        )
