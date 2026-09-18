"""Integrantes de órganos superiores extraídos de perfiles oficiales."""

from __future__ import annotations

import re
from hashlib import sha256
from io import BytesIO
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from worker.adapters.base import SourceAdapter
from worker.adapters.congress import _field, compact, key, normalized, table_records
from worker.models import CandidateAssertion, DiscoveredDocument, FetchResult

LEADERSHIP_SOURCES = {
    "directorio_gabinete_legal": ("https://www.gob.mx/gobierno", "Presidencia de la República", "executive", "central_administration", 24),
    "directorio_scjn_pleno": ("https://www.scjn.gob.mx/conoce-la-corte", "Suprema Corte de Justicia de la Nación", "judicial", "court", 9),
    "directorio_tepjf_sala_superior": ("https://www.te.gob.mx/front3/ContenidoSalas/salaSuperior", "Sala Superior del Tribunal Electoral del Poder Judicial de la Federación", "judicial", "court", 5),
    "directorio_oaj_pleno": ("https://www.oaj.gob.mx/pleno.htm", "Órgano de Administración Judicial", "judicial", "judicial_administration", 5),
    "directorio_tdj_pleno": ("https://www.tdj.gob.mx/assets/resources/pdf/com_01.pdf", "Tribunal de Disciplina Judicial", "judicial", "court", 5),
    "directorio_ine_consejo": ("https://www.ine.mx/estructura-ine/consejo-general/", "Consejo General del Instituto Nacional Electoral", "independent", "constitutional_body", 11),
    "directorio_banxico_junta": ("https://www.banxico.org.mx/organigrama/informacion.jsp?BMXC_id=4d76334e33776a4d344d673d&BMXC_idioma=E", "Junta de Gobierno del Banco de México", "independent", "constitutional_body", 5),
    "directorio_inegi_junta": ("https://www.inegi.org.mx/inegi/cca/consejo.html", "Junta de Gobierno del INEGI", "independent", "constitutional_body", 5),
    "directorio_cndh_superior": ("https://directorio.cndh.org.mx/", "Comisión Nacional de los Derechos Humanos", "independent", "constitutional_body", 8),
    "directorio_fgr_titular": ("https://fgr.org.mx/swb/FGR/directorio", "Fiscalía General de la República", "independent", "constitutional_body", 1),
    "directorio_asf_titular": ("https://www.asf.gob.mx/Section/51_Quienes_somos", "Auditoría Superior de la Federación", "legislative", "audit_body", 1),
}


ROLE_WORDS = (
    "ministra", "ministro", "magistrada", "magistrado", "consejera", "consejero",
    "gobernadora", "gobernador", "subgobernadora", "subgobernador", "presidenta", "presidente",
    "secretaria", "secretario", "fiscal general", "auditor superior",
    "integrante del pleno", "integrante",
)


def canonical_role(value: str) -> str:
    patterns = (
        r"magistrad[oa](?:\s+presidente|\s+presidenta)?",
        r"ministr[oa](?:\s+presidente|\s+presidenta)?",
        r"consejer[oa](?:\s+presidente|\s+presidenta)?",
        r"(?:sub)?gobernador[ae]?",
        r"president[ae]",
        r"integrante del pleno",
        r"fiscal general",
        r"auditor superior",
        r"secretari[oa](?:\s+de estado)?",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return compact(match.group(0)).title()
    return compact(value)


HONORIFICS = (
    r"Lic\.?", r"Lcda\.?", r"Licenciad[oa]", r"Mtr[oa]\.?", r"Maestr[oa]",
    r"Dr\.?", r"Dra\.?", r"Doctor(?:a)?", r"Ministr[oa]", r"Magistrad[oa]",
    r"Consejer[oa]", r"C\.",
)


def strip_honorific(value: str) -> str:
    """Quita tratamientos y puntuación de arrastre del nombre de una persona.

    Los directorios oficiales anteponen el tratamiento o el cargo al nombre.
    Conservarlos produciría personas distintas para la misma persona según la
    fuente que la publique.
    """
    text = compact(value)
    pattern = r"^(?:{})\s+".format("|".join(HONORIFICS))
    previous = None
    while previous != text:
        previous = text
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip(" .,;:")


class FederalLeadershipAdapter(SourceAdapter):
    key = "federal_leadership"
    source_keys: tuple[str, ...] | None = None

    def discover(self) -> list[DiscoveredDocument]:
        documents = []
        for source_key, (url, organization, _, _, _) in LEADERSHIP_SOURCES.items():
            if self.source_keys is not None and source_key not in self.source_keys:
                continue
            documents.append(DiscoveredDocument(source_key, url, f"Integración de {organization}", organization, "official_roster"))
        return documents

    def parse(self, result: FetchResult) -> list[CandidateAssertion]:
        config = LEADERSHIP_SOURCES.get(result.document.source_key)
        if not config:
            raise ValueError(f"Unknown leadership source {result.document.source_key}")
        _, organization, branch, organization_type, expected = config
        if result.document.source_key == "directorio_tdj_pleno" and result.mime_type == "application/pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:  # pragma: no cover - verified by deployment dependency
                raise RuntimeError("pypdf is required to parse the official TDJ roster") from exc
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(result.content)).pages)
            expected_count = expected
            rows = self._tdj_rows_from_text(text)
        else:
            soup = BeautifulSoup(result.content, "html.parser")
            expected_node = soup.select_one("[data-expected-members]")
            expected_count = int(expected_node.get("data-expected-members")) if expected_node else expected
            source_key = result.document.source_key
            rows = self._explicit_rows(soup)
            if rows:
                pass
            elif source_key == "directorio_scjn_pleno":
                rows = self._scjn_rows(soup)
            elif source_key == "directorio_ine_consejo":
                rows = self._ine_rows(soup)
            elif source_key == "directorio_banxico_junta":
                rows = self._banxico_rows(soup)
            elif source_key == "directorio_inegi_junta":
                rows = self._inegi_rows(soup)
            elif source_key == "directorio_cndh_superior":
                rows = self._cndh_rows(soup)
            elif source_key == "directorio_fgr_titular":
                rows = self._fgr_rows(soup)
            elif source_key == "directorio_asf_titular":
                rows = self._asf_rows(soup)
            else:
                rows = []
            if not rows:
                rows = self._heading_rows(soup)
            if not rows:
                rows = self._table_rows(soup)
        candidates = [
            self._candidate(result, organization, branch, organization_type, index + 1, row)
            for index, row in enumerate(rows)
        ]
        if len(candidates) != expected_count:
            raise ValueError(
                f"{result.document.source_key} produced {len(candidates)} voting members; expected {expected_count}"
            )
        return candidates

    @staticmethod
    def _explicit_rows(soup: BeautifulSoup) -> list[dict]:
        rows = []
        for card in soup.select("[data-power-map-person]"):
            rows.append({
                "name": compact(card.get("data-power-map-person", "")),
                "role": compact(card.get("data-position", "")),
                "profile": card.get("data-profile"),
                "portrait": card.get("data-portrait"),
                "status": card.get("data-status", "confirmed"),
                "valid_from": card.get("data-valid-from"),
                "organization": card.get("data-organization"),
                "excerpt": compact(card.get_text(" ", strip=True)),
            })
        return rows

    @staticmethod
    def _table_rows(soup: BeautifulSoup) -> list[dict]:
        rows = []
        for record, element in table_records(soup):
            name = _field(record, "nombre", "integrante", "name")
            role = _field(record, "cargo", "puesto", "role")
            if not name or not role or not any(word in normalized(role) for word in ROLE_WORDS):
                continue
            link = element.select_one("a[href]")
            image = element.select_one("img[src]")
            rows.append({
                "name": name,
                "role": role,
                "profile": link.get("href") if link else None,
                "portrait": image.get("src") if image else None,
                "status": "confirmed",
                "valid_from": None,
                "organization": _field(record, "institucion", "dependencia", "organization"),
                "excerpt": compact(element.get_text(" ", strip=True)),
            })
        return rows

    @staticmethod
    def _ine_rows(soup: BeautifulSoup) -> list[dict]:
        """Extrae sólo Presidencia y consejerías electorales con voto."""
        rows: list[dict] = []
        section = ""
        for heading in soup.select("h2, h3"):
            text = compact(heading.get_text(" ", strip=True))
            normalized_text = normalized(text)
            if heading.name == "h2":
                if "integrantes del consejo general" in normalized_text:
                    section = "presidency"
                elif "consejeros y consejeras electorales" in normalized_text:
                    section = "electoral"
                else:
                    section = ""
                continue
            link = heading.find("a", href=True)
            if not link:
                continue
            href = link.get("href", "")
            if section == "presidency" and "consejer" not in href:
                continue
            if section not in ("presidency", "electoral"):
                continue
            image = heading.find_previous("img")
            rows.append({
                "name": strip_honorific(text),
                "role": "Consejera Presidenta" if section == "presidency" else "Consejería Electoral",
                "profile": href,
                "portrait": image.get("src") if image else None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": f"{text} · {'Presidencia del Consejo' if section == 'presidency' else 'Consejería Electoral'}",
            })
        return rows

    @staticmethod
    def _cndh_rows(soup: BeautifulSoup) -> list[dict]:
        rows: list[dict] = []
        for card in soup.select("div.card"):
            name_node = card.select_one(".full-name")
            role_node = card.select_one(".badge-Area.fw-bold")
            if not name_node:
                continue
            area_nodes = card.select(".badge-Area.text-dark")
            area = compact(area_nodes[0].get_text(" ", strip=True)) if area_nodes else ""
            if not role_node:
                if normalized(area) == "tercera visitaduria general" and not any(
                    row.get("position_only") and row["role"] == area for row in rows
                ):
                    rows.append({
                        "name": area,
                        "role": area,
                        "profile": None,
                        "portrait": None,
                        "status": "unrecorded",
                        "position_only": True,
                        "valid_from": None,
                        "organization": None,
                        "excerpt": compact(card.get_text(" ", strip=True)),
                    })
                continue
            role = compact(role_node.get_text(" ", strip=True))
            role_key = normalized(role)
            if not (
                "presidenta de la cndh" in role_key
                or role_key == "secretario ejecutivo"
                or ("encargad" in role_key and "visitaduria general" in role_key)
            ):
                if normalized(area) == "tercera visitaduria general" and not any(
                    row.get("position_only") and row["role"] == area for row in rows
                ):
                    rows.append({
                        "name": area,
                        "role": area,
                        "profile": None,
                        "portrait": None,
                        "status": "unrecorded",
                        "position_only": True,
                        "valid_from": None,
                        "organization": None,
                        "excerpt": compact(card.get_text(" ", strip=True)),
                    })
                continue
            image = card.select_one("img[src]")
            portrait = image.get("src") if image and "avatar" not in image.get("src", "").lower() else None
            rows.append({
                "name": strip_honorific(name_node.get_text(" ", strip=True)),
                "role": role,
                "profile": None,
                "portrait": portrait,
                "status": "acting" if "encargad" in role_key else "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": compact(card.get_text(" ", strip=True)),
            })
        return rows

    @staticmethod
    def _banxico_rows(soup: BeautifulSoup) -> list[dict]:
        rows: list[dict] = []
        cells = soup.select("table td")
        for index in range(0, len(cells), 3):
            group = cells[index:index + 3]
            if len(group) != 3:
                continue
            name = compact(group[0].get_text(" ", strip=True))
            role = compact(group[1].get_text(" ", strip=True))
            role_key = normalized(role)
            if not name or not ("gobernador" in role_key or "subgobernador" in role_key):
                continue
            if "," in name:
                family, given = [compact(part) for part in name.split(",", 1)]
                name = f"{given} {family}"
            rows.append({
                "name": name,
                "role": "Gobernadora" if "gobernador" in role_key and "sub" not in role_key else "Subgobernatura",
                "profile": None,
                "portrait": None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": f"{name} · {role}",
            })
        return rows

    @staticmethod
    def _inegi_rows(soup: BeautifulSoup) -> list[dict]:
        rows: list[dict] = []
        for record, element in table_records(soup):
            name = _field(record, "nombre")
            role = _field(record, "puesto")
            role_key = normalized(role)
            if not name or not (
                role_key == "presidenta del inegi"
                or role_key.startswith("vicepresident")
            ):
                continue
            rows.append({
                "name": name,
                "role": "Presidenta de la Junta de Gobierno" if role_key == "presidenta del inegi" else "Vicepresidencia de la Junta de Gobierno",
                "profile": None,
                "portrait": None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": compact(element.get_text(" ", strip=True)),
            })
        return rows

    @staticmethod
    def _fgr_rows(soup: BeautifulSoup) -> list[dict]:
        for card in soup.select("div.card"):
            role_node = next(
                (node for node in card.select("p") if normalized(node.get_text(" ", strip=True)) == "fiscal general de la republica"),
                None,
            )
            if not role_node:
                continue
            name_node = card.select_one("h5.titulo")
            if not name_node:
                continue
            image = card.select_one("img[src]")
            return [{
                "name": strip_honorific(name_node.get_text(" ", strip=True)),
                "role": "Fiscal General de la República",
                "profile": None,
                "portrait": image.get("src") if image else None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": compact(card.get_text(" ", strip=True)),
            }]
        return []

    @staticmethod
    def _asf_rows(soup: BeautifulSoup) -> list[dict]:
        for heading in soup.select("h2, h3, h4, h5"):
            if normalized(heading.get_text(" ", strip=True)) != "auditor superior de la federacion":
                continue
            name_heading = heading.find_previous(["h2", "h3", "h4", "h5"])
            if not name_heading:
                continue
            image = heading.find_previous("img")
            return [{
                "name": strip_honorific(name_heading.get_text(" ", strip=True)),
                "role": "Auditor Superior de la Federación",
                "profile": None,
                "portrait": image.get("src") if image else None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": f"{compact(name_heading.get_text(' ', strip=True))} · Auditor Superior de la Federación",
            }]
        return []

    @staticmethod
    def _heading_rows(soup: BeautifulSoup) -> list[dict]:
        rows: list[dict] = []
        seen: set[str] = set()
        for heading in soup.select("h2, h3, h4"):
            name = compact(heading.get_text(" ", strip=True))
            normalized_name = normalized(name)
            if (
                len(name.split()) < 2
                or any(word in normalized_name for word in ROLE_WORDS)
                or normalized_name.startswith(("el pleno", "integracion", "contenido"))
                or any(section in normalized_name for section in ("actividad profesional", "trayectoria", "semblanza", "formacion academica", "experiencia"))
            ):
                continue
            container = heading.parent
            nearby = []
            for sibling in heading.find_all_next(limit=5):
                if sibling is not heading and sibling.name in ("h2", "h3", "h4"):
                    break
                value = compact(sibling.get_text(" ", strip=True))
                if value and value != name:
                    nearby.append(value)
            role = next((value for value in nearby if any(word in normalized(value) for word in ROLE_WORDS)), "")
            if not role or normalized_name in seen:
                continue
            seen.add(normalized_name)
            link = heading.find("a", href=True) or (container.find("a", href=True) if container else None)
            image = container.find("img", src=True) if container else None
            rows.append({
                "name": name,
                "role": canonical_role(role),
                "profile": link.get("href") if link else None,
                "portrait": image.get("src") if image else None,
                "status": "confirmed",
                "valid_from": None,
                "organization": None,
                "excerpt": f"{name} · {role}",
            })
        return rows

    @staticmethod
    def _tdj_rows_from_text(text: str) -> list[dict]:
        normalized_text = compact(text)
        president_match = re.search(
            r"magistrada presidenta\s+([A-ZÁÉÍÓÚÑ][^,.;]+)", normalized_text, flags=re.IGNORECASE
        )
        members_match = re.search(
            r"magistradas\s+(.+?)\s+e\s+(.+?),\s+así como los magistrados\s+(.+?)\s+y\s+(.+?)[.]",
            normalized_text,
            flags=re.IGNORECASE,
        )
        if not president_match or not members_match:
            return []
        names = [compact(president_match.group(1)), *[compact(value) for value in members_match.groups()]]
        return [
            {
                "name": name,
                "role": "Magistrada Presidenta" if index == 0 else "Magistratura del Pleno",
                "profile": None,
                "portrait": None,
                "status": "confirmed",
                "valid_from": "2025-09-02",
                "organization": None,
                "excerpt": name,
            }
            for index, name in enumerate(names)
        ]

    @staticmethod
    def _scjn_rows(soup: BeautifulSoup) -> list[dict]:
        """Lee el directorio del Pleno, no un comunicado.

        Cada ministratura se publica como una ficha propia bajo ``/ministro-``
        o ``/ministra-``. La presidencia se reconoce por el texto de su ficha,
        no por el orden de aparición, que el sitio puede reordenar.
        """
        rows: list[dict] = []
        seen: set[str] = set()
        for link in soup.select('a[href^="/ministro-"], a[href^="/ministra-"]'):
            href = link.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            # La ficha antepone el cargo y el tratamiento dentro del propio
            # enlace; el último `span` aísla el nombre. Si el sitio cambia esa
            # estructura, el texto completo sigue sirviendo tras limpiarlo.
            spans = link.select("span")
            raw = spans[-1].get_text(" ", strip=True) if spans else link.get_text(" ", strip=True)
            name = strip_honorific(raw)
            if not name:
                continue
            container = link.find_parent(["div", "li", "article", "section"])
            context = normalized(link.get_text(" ", strip=True))
            presides = "presidente de la suprema corte" in context or "presidenta de la suprema corte" in context
            rows.append({
                "name": name,
                "role": "Ministro Presidente" if presides else "Ministratura del Pleno",
                "profile": href,
                "portrait": None,
                "status": "confirmed",
                "valid_from": "2025-09-01",
                "organization": None,
                "excerpt": compact(container.get_text(" ", strip=True)) if container else name,
            })
        rows.sort(key=lambda row: row["role"] != "Ministro Presidente")
        return rows

    @staticmethod
    def _candidate(
        result: FetchResult, organization: str, branch: str, organization_type: str,
        seat_number: int, row: dict,
    ) -> CandidateAssertion:
        profile = urljoin(result.final_url, row.get("profile")) if row.get("profile") else result.final_url
        portrait = urljoin(result.final_url, row.get("portrait")) if row.get("portrait") else None
        if portrait and not FederalLeadershipAdapter._official_url(portrait, result.final_url):
            portrait = None
        # Punto único por el que pasan todas las fuentes: normalizar aquí evita
        # que cada directorio imponga su propia convención de tratamientos.
        name = strip_honorific(row["name"])
        role = row["role"]
        member_organization = row.get("organization") or organization
        seat_key = f"{key(member_organization)}-{key(role)}-{seat_number:02d}"
        identity = profile if profile != result.final_url else f"{result.document.source_key}:{normalized(name)}"
        position_only = bool(row.get("position_only"))
        metadata = {
            "sourceDocumentSlug": result.document.source_key,
            "positionOrganizationLabel": member_organization,
            "organizationLabel": member_organization,
            "branch": branch,
            "category": "constitutional_body" if branch == "independent" else organization_type,
            "organizationType": organization_type,
            "positionCategory": "collegiate_seat",
            "positionType": "collegiate_seat",
            "seatKey": seat_key,
            "seatNumber": seat_number,
            "selectionMethod": "constitutional_appointment",
            "isCollegial": True,
            "occupancyStatus": row.get("status", "confirmed"),
            "officialProfileUrl": profile,
            "officialPortraitUrl": portrait,
            "officialIdentifier": identity,
            "validFrom": row.get("valid_from"),
            "mode": "both",
            "relationshipClass": "structure" if position_only else "tenure",
            "legalBasis": "Directorio oficial del órgano",
        }
        candidate_key = f"{result.document.source_key}:{seat_key}:{identity}"
        return CandidateAssertion(
            candidate_id=sha256(candidate_key.encode()).hexdigest()[:24],
            source_key=result.document.source_key,
            subject_label=role if position_only else name,
            predicate="PART_OF" if position_only else "HOLDS",
            object_label=member_organization if position_only else role,
            literal_value=None,
            source_locator=f"Integrante {seat_number}",
            source_excerpt=row.get("excerpt") or f"{name} · {role}",
            confidence=0.98,
            extraction_method="deterministic_official_roster",
            subject_kind="position" if position_only else "person",
            object_kind="organization" if position_only else "position",
            metadata=metadata,
        )

    @staticmethod
    def _official_url(candidate: str, source: str) -> bool:
        candidate_host = urlparse(candidate).hostname or ""
        source_host = urlparse(source).hostname or ""
        return urlparse(candidate).scheme == "https" and (
            candidate_host == source_host
            or candidate_host.endswith((".gob.mx", ".org.mx"))
        )


class CabinetLeadershipAdapter(FederalLeadershipAdapter):
    """Titular de Presidencia y titulares de la administración central."""

    key = "federal_cabinet"
    source_keys = ("directorio_gabinete_legal",)


class JudicialLeadershipAdapter(FederalLeadershipAdapter):
    """Integraciones superiores del Poder Judicial de la Federación."""

    key = "federal_judicial_leadership"
    source_keys = (
        "directorio_scjn_pleno",
        "directorio_tepjf_sala_superior",
        "directorio_oaj_pleno",
        "directorio_tdj_pleno",
    )


class AutonomousLeadershipAdapter(FederalLeadershipAdapter):
    """Órganos colegiados autónomos y fiscalización superior."""

    key = "federal_autonomous_leadership"
    source_keys = (
        "directorio_ine_consejo",
        "directorio_banxico_junta",
        "directorio_inegi_junta",
        "directorio_cndh_superior",
        "directorio_fgr_titular",
        "directorio_asf_titular",
    )
