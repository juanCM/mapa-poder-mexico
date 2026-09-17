from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_seed_dataset():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["nodes"] > 0


def test_search_finds_institution():
    response = client.get("/v1/search", params={"q": "Suprema Corte", "as_of": "2026-09-17"})
    assert response.status_code == 200
    assert response.json()["results"][0]["slug"] == "suprema-corte-de-justicia-de-la-nacion"


def test_power_graph_only_returns_power_edges():
    response = client.get("/v1/graph", params={"mode": "power", "as_of": "2026-09-17"})
    assert response.status_code == 200
    assert all(edge["mode"] in ("power", "both") for edge in response.json()["edges"])


def test_unknown_relationship_is_404():
    assert client.get("/v1/relationships/missing").status_code == 404


def test_admin_decision_requires_a_note():
    response = client.post(
        "/v1/admin/review-tasks/review-001/decision",
        json={"decision": "approved", "note": "Fuente y vigencia confirmadas"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
