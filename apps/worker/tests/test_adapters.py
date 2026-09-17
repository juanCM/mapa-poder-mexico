from worker.adapters.gobierno import GobiernoMxAdapter
from worker.models import DiscoveredDocument, FetchResult


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
