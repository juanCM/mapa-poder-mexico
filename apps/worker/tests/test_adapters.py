from worker.adapters.apf import CENTRAL_APF, ApfCatalogAdapter
from worker.adapters.gobierno import GobiernoMxAdapter
from worker.adapters.nomina import NominaTransparenteAdapter
from worker.models import DiscoveredDocument, FetchResult
from worker.publisher import person_name_parts, slugify


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
