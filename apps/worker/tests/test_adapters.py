from pathlib import Path

from worker.adapters.apf import CENTRAL_APF, ApfCatalogAdapter
from worker.adapters.congress import CongressRosterAdapter
from worker.adapters.gobierno import GobiernoMxAdapter
from worker.adapters.leadership import (
    AutonomousLeadershipAdapter,
    CabinetLeadershipAdapter,
    FederalLeadershipAdapter,
    JudicialLeadershipAdapter,
)
from worker.adapters.nomina import NominaTransparenteAdapter
from worker.models import DiscoveredDocument, FetchResult
from worker.publisher import person_name_parts, slugify

FIXTURES = Path(__file__).resolve().parents[3] / "sources" / "fixtures"


def test_gobierno_adapter_emits_review_candidates_only():
    content = b"<html><body><h2>Dependencias</h2><ul><li>Hacienda</li><li>Salud</li></ul></body></html>"
    document = DiscoveredDocument("gobierno_mx", "https://example.test", "Test", "Test", "directory")
    result = FetchResult(document, document.url, 200, "text/html", content)
    candidates = GobiernoMxAdapter().emit_candidates(result)
    assert {candidate.subject_label for candidate in candidates} == {"Hacienda", "Salud"}
    assert all(candidate.status == "needs_review" for candidate in candidates)


def test_fingerprint_is_deterministic():
    adapter = GobiernoMxAdapter()
    assert adapter.fingerprint(b"same") == adapter.fingerprint(b"same")
    assert adapter.fingerprint(b"same") != adapter.fingerprint(b"different")


def test_apf_catalog_emits_complete_central_administration_candidates():
    adapter = ApfCatalogAdapter()
    document = adapter.discover()[0]
    result = FetchResult(document, document.url, 200, "application/pdf", b"%PDF-test")
    candidates = adapter.emit_candidates(result)

    assert {candidate.subject_label for candidate in candidates} == set(CENTRAL_APF)
    assert all(candidate.object_label == "Poder Ejecutivo Federal" for candidate in candidates)
    assert all(candidate.metadata["apfSector"] == "centralizada" for candidate in candidates)


def test_apf_catalog_extracts_only_current_entities_from_dof_content():
    content = b"""
    <div class="Texto">A. ENTIDADES PARAESTATALES DE LA ADMINISTRACION PUBLICA FEDERAL</div>
    <div class="ROMANOS">1. Instituto Mexicano del Seguro Social</div>
    <div class="ROMANOS">2. Instituto Politecnico Nacional</div>
    <div class="Texto">B. ENTIDADES PARAESTATALES EN PROCESO DE DESINCORPORACION</div>
    <div class="ROMANOS">1. Entidad en liquidacion</div>
    """
    adapter = ApfCatalogAdapter()
    document = adapter.discover()[1]
    result = FetchResult(document, document.url, 200, "text/html", content)
    candidates = adapter.emit_candidates(result)

    labels = {candidate.subject_label for candidate in candidates}
    assert "Instituto Mexicano del Seguro Social" in labels
    assert "Instituto Politecnico Nacional" in labels
    assert "Entidad en liquidacion" not in labels


def test_apf_catalog_attributes_sector_coordinator_without_leaking_it():
    content = """
    <div class="Texto">A. ENTIDADES PARAESTATALES DE LA ADMINISTRACIÓN PÚBLICA FEDERAL</div>
    <div class="Texto">ORGANISMOS DESCENTRALIZADOS SECTORIZADOS</div>
    <div class="Texto">SECRETARÍA DE GOBERNACIÓN</div>
    <div class="ROMANOS">1. Talleres Gráficos de México</div>
    <div class="Texto">SUBTOTAL: 1</div>
    <div class="Texto">ORGANISMOS DESCENTRALIZADOS NO SECTORIZADOS</div>
    <div class="ROMANOS">2. Instituto Mexicano del Seguro Social</div>
    """.encode()
    adapter = ApfCatalogAdapter()
    document = adapter.discover()[1]
    candidates = adapter.emit_candidates(FetchResult(document, document.url, 200, "text/html", content))

    oversight = [candidate for candidate in candidates if candidate.predicate == "OVERSEES"]
    # El encabezado del DOF viene en mayúsculas; publicarlo tal cual
    # sobrescribiría el nombre canónico de la dependencia en el grafo.
    assert [(c.subject_label, c.object_label) for c in oversight] == [
        ("Secretaría de Gobernación", "Talleres Gráficos de México")
    ]
    # Un organismo no sectorizado no puede heredar la coordinadora del bloque
    # anterior: el encabezado intermedio tiene que limpiar el sector.
    imss = next(c for c in candidates if c.subject_label == "Instituto Mexicano del Seguro Social")
    assert "sectorLabel" not in imss.metadata


def test_publication_helpers_are_stable_and_preserve_hispanic_names():
    assert slugify("Secretaría de las Mujeres") == "secretaria-de-las-mujeres"
    assert person_name_parts("Ana María López García", {}) == ("Ana María", "López García")
    assert person_name_parts("Ana María López García", {"givenNames": "Ana María", "familyNames": "López García"}) == (
        "Ana María", "López García"
    )


def test_nomina_adapter_creates_person_position_candidates():
    content = b'''{"data":{"consultaNominaPorRamoPaginado":{"listDtoServidorPublicoDto":[{"nombre":"Ana Maria Lopez Garcia","puesto":"Directora General","institution":"Secretaria de Ejemplo","ramo":6,"idUr":"100"}]}}}'''
    document = DiscoveredDocument("nomina_apf_6_100_0", "https://example.test", "Test", "Test", "official_public_payroll")
    candidates = NominaTransparenteAdapter().emit_candidates(FetchResult(document, document.url, 200, "application/json", content))
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.subject_kind == "person"
    assert candidate.object_kind == "position"
    assert candidate.predicate == "HOLDS"
    assert candidate.metadata["positionOrganizationLabel"] == "Secretaria de Ejemplo"
    assert candidate.metadata["sourceDocumentSlug"] == "nomina_apf_6_100_0"


def test_congress_adapter_models_stable_seats_and_real_vacancies():
    content = (FIXTURES / "congreso_lxvi_diputaciones.html").read_bytes()
    document = CongressRosterAdapter().discover()[0]
    result = FetchResult(document, document.url, 200, "text/html", content)
    candidates = CongressRosterAdapter().emit_candidates(result)

    assert len(candidates) == 3
    assert len({candidate.metadata["seatKey"] for candidate in candidates}) == 3
    vacancy = next(candidate for candidate in candidates if candidate.metadata["occupancyStatus"] == "vacant")
    assert vacancy.subject_kind == "position"
    assert vacancy.object_kind == "organization"
    assert vacancy.predicate == "PART_OF"
    occupied = next(candidate for candidate in candidates if candidate.subject_label == "Ana López García")
    assert occupied.object_kind == "position"
    assert occupied.metadata["district"] == 3
    assert occupied.metadata["officialPortraitUrl"].endswith("/retratos/1.jpg")


def test_leadership_adapter_requires_official_profiles_and_numbered_seats():
    content = (FIXTURES / "liderazgo_colegiado.html").read_bytes()
    document = next(item for item in FederalLeadershipAdapter().discover() if item.source_key == "directorio_ine_consejo")
    result = FetchResult(document, document.url, 200, "text/html", content)
    candidates = FederalLeadershipAdapter().emit_candidates(result)

    assert len(candidates) == 2
    assert all(candidate.predicate == "HOLDS" for candidate in candidates)
    assert all(candidate.metadata["isCollegial"] for candidate in candidates)
    assert candidates[0].metadata["officialProfileUrl"].startswith("https://www.ine.mx/")
    assert candidates[0].metadata["officialPortraitUrl"].startswith("https://www.ine.mx/")


def test_cabinet_adapter_supports_official_profile_rosters_and_acting_holders():
    content = (FIXTURES / "gabinete_legal.html").read_bytes()
    adapter = CabinetLeadershipAdapter()
    document = adapter.discover()[0]
    candidates = adapter.emit_candidates(FetchResult(document, document.url, 200, "text/html", content))

    assert len(candidates) == 2
    assert {candidate.metadata["positionOrganizationLabel"] for candidate in candidates} == {
        "Dependencia Uno",
        "Dependencia Dos",
    }
    acting = next(candidate for candidate in candidates if candidate.metadata["occupancyStatus"] == "acting")
    assert acting.metadata["officialProfileUrl"].startswith("https://www.gob.mx/")


def test_congress_adapter_rejects_partial_constitutional_roster():
    content = b"<html><body><table><tr><th>Diputado</th><th>Entidad</th><th>Distrito</th></tr><tr><td>Persona Uno</td><td>Jalisco</td><td>Dtto. 1</td></tr></table></body></html>"
    document = CongressRosterAdapter().discover()[0]
    result = FetchResult(document, document.url, 200, "text/html", content)
    try:
        CongressRosterAdapter().emit_candidates(result)
    except ValueError as error:
        assert "expected 500" in str(error)
    else:
        raise AssertionError("A partial constitutional roster must be rejected")


def test_tdj_official_release_parser_extracts_all_five_magistratures():
    text = (
        "La magistrada presidenta Celia Maya García, asumió la presidencia. "
        "También forman parte del Pleno las magistradas Eva Verónica de Gyvés Zárate "
        "e Indira Isabel García Pérez, así como los magistrados Bernardo Bátiz Vázquez "
        "y Rufino H León Tovar."
    )
    rows = FederalLeadershipAdapter._tdj_rows_from_text(text)
    assert len(rows) == 5
    assert rows[0]["name"] == "Celia Maya García"
    assert rows[0]["role"] == "Magistrada Presidenta"


def test_scjn_directory_parser_reads_the_plenary_roster():
    from bs4 import BeautifulSoup

    html = """
    <div><a href="/ministra-lenia-batres-guadarrama">
         <span>Ministra</span><span>Lenia Batres Guadarrama</span></a></div>
    <div><a href="/ministro-hugo-aguilar-ortiz">
         <span>Presidente de la Suprema Corte de Justicia de la Nación</span>
         <span>Ministro</span><span>Hugo Aguilar Ortiz</span></a>
         <a href="/ministro-hugo-aguilar-ortiz"><span>Ministro</span><span>Hugo Aguilar Ortiz</span></a></div>
    """
    rows = FederalLeadershipAdapter._scjn_rows(BeautifulSoup(html, "html.parser"))

    # El cargo y el tratamiento viven dentro del propio enlace: el nombre no
    # debe arrastrarlos. La ficha repetida no cuenta dos veces y la presidencia
    # se reconoce por su texto, aunque el sitio la liste en segundo lugar.
    assert [row["name"] for row in rows] == ["Hugo Aguilar Ortiz", "Lenia Batres Guadarrama"]
    assert rows[0]["role"] == "Ministro Presidente"
    assert rows[1]["role"] == "Ministratura del Pleno"


def test_leadership_domains_can_run_as_independent_review_batches():
    assert {document.source_key for document in CabinetLeadershipAdapter().discover()} == {
        "directorio_gabinete_legal"
    }
    assert {document.source_key for document in JudicialLeadershipAdapter().discover()} == {
        "directorio_scjn_pleno",
        "directorio_tepjf_sala_superior",
        "directorio_oaj_pleno",
        "directorio_tdj_pleno",
    }
    assert {document.source_key for document in AutonomousLeadershipAdapter().discover()} == {
        "directorio_ine_consejo",
        "directorio_banxico_junta",
        "directorio_inegi_junta",
        "directorio_cndh_superior",
        "directorio_fgr_titular",
        "directorio_asf_titular",
    }


def test_ine_parser_excludes_legislative_representatives_without_vote():
    content = b"""
    <main data-expected-members="2">
      <h2>INTEGRANTES DEL CONSEJO GENERAL</h2>
      <h3><a href="/consejera-presidenta/">Lic. Persona Presidenta</a></h3>
      <h2>CONSEJEROS Y CONSEJERAS ELECTORALES</h2>
      <h3><a href="/consejero-electoral/">Mtro. Persona Consejera</a></h3>
      <h2>CONSEJEROS Y CONSEJERAS DEL PODER LEGISLATIVO</h2>
      <h3><a href="/representante/">Persona Representante</a></h3>
    </main>
    """
    adapter = FederalLeadershipAdapter()
    document = next(item for item in adapter.discover() if item.source_key == "directorio_ine_consejo")
    candidates = adapter.emit_candidates(FetchResult(document, document.url, 200, "text/html", content))
    assert [candidate.subject_label for candidate in candidates] == ["Persona Presidenta", "Persona Consejera"]


def test_cndh_parser_preserves_an_unrecorded_superior_position_without_inventing_a_person():
    content = b"""
    <main data-expected-members="2">
      <div class="card"><span class="full-name">Mtra. Persona Presidenta</span><span class="badge-Area fw-bold">Presidenta de la CNDH</span><span class="badge-Area text-dark">Presidencia</span></div>
      <div class="card"><span class="full-name">Persona Directora</span><span class="badge-Area fw-bold">Directora General de Quejas</span><span class="badge-Area text-dark">Tercera Visitaduria General</span></div>
    </main>
    """
    adapter = FederalLeadershipAdapter()
    document = next(item for item in adapter.discover() if item.source_key == "directorio_cndh_superior")
    candidates = adapter.emit_candidates(FetchResult(document, document.url, 200, "text/html", content))
    unrecorded = next(item for item in candidates if item.metadata["occupancyStatus"] == "unrecorded")
    assert unrecorded.subject_kind == "position"
    assert unrecorded.predicate == "PART_OF"


def test_banxico_parser_handles_the_official_malformed_table_rows():
    content = b"""
    <main data-expected-members="2"><table><tr><th>Nombre</th><th>Puesto</th><th>Direccion</th></tr>
      <tr><td>Rodriguez Ceja, Victoria</td><td>Gobernador/a</td><td></td></tr>
      <td>Heath Constable, Jonathan Ernest</td><td>Subgobernador/a</td><td>Mexico</td>
    </table></main>
    """
    adapter = FederalLeadershipAdapter()
    document = next(item for item in adapter.discover() if item.source_key == "directorio_banxico_junta")
    candidates = adapter.emit_candidates(FetchResult(document, document.url, 200, "text/html", content))
    assert [item.subject_label for item in candidates] == ["Victoria Rodriguez Ceja", "Jonathan Ernest Heath Constable"]
