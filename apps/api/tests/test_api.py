from fastapi.testclient import TestClient

from app.main import app
from app.repository import active_on

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


def test_power_map_initial_cut_is_grouped_and_evidence_only_is_visible():
    response = client.get("/v1/power-map", params={"as_of": "2026-09-17"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["root"] is None
    assert any(node["category"] == "branch" for node in payload["nodes"])
    assert all(edge["hasEvidence"] for edge in payload["relationships"])
    assert "nextCursor" in payload


def test_power_map_expands_a_root_and_rejects_unknown_roots():
    response = client.get(
        "/v1/power-map",
        params={"as_of": "2026-09-17", "root": "poder-legislativo-federal", "depth": 2},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]
    assert any(node["slug"] == "camara-de-diputados" for node in payload["nodes"])
    assert client.get(
        "/v1/power-map", params={"as_of": "2026-09-17", "root": "no-existe"}
    ).status_code == 404


def test_node_context_groups_relationship_evidence_and_labels():
    response = client.get(
        "/v1/nodes/presidencia-de-la-republica/context", params={"as_of": "2026-09-17"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["node"]["slug"] == "presidencia-de-la-republica"
    assert payload["relationships"]
    assert all(relation["evidence"] for relation in payload["relationships"])
    assert all(relation["sourceLabel"] and relation["targetLabel"] for relation in payload["relationships"])


def test_search_supports_branch_and_category_filters():
    response = client.get(
        "/v1/search",
        params={"q": "Suprema", "as_of": "2026-09-17", "branch": "judicial", "category": "court"},
    )
    assert response.status_code == 200
    assert response.json()["results"]
    excluded = client.get(
        "/v1/search",
        params={"q": "Suprema", "as_of": "2026-09-17", "branch": "executive"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["results"] == []


def test_temporal_ranges_use_an_exclusive_end_date():
    from datetime import date

    record = {"validFrom": "2024-10-01", "validTo": "2030-09-30"}
    assert active_on(record, date(2030, 9, 29))
    assert not active_on(record, date(2030, 9, 30))


def test_batch_decision_supports_task_exclusions(monkeypatch):
    batch_id = "00000000-0000-4000-8000-000000000001"
    excluded_id = "00000000-0000-4000-8000-000000000002"
    captured = {}
    monkeypatch.setattr(
        "app.main.review_batches",
        lambda: [{"id": batch_id, "adapter": "test", "status": "needs_review", "title": "Lote", "total": 3, "pending": 3, "approved": 0, "rejected": 0, "published": 0, "createdAt": "2026-09-18T00:00:00Z"}],
    )

    def decide(*args):
        captured["args"] = args
        return 2

    monkeypatch.setattr("app.main.decide_review_batch", decide)
    response = client.post(
        f"/v1/admin/review-batches/{batch_id}/decision",
        json={"decision": "approved", "note": "Dos tareas verificadas", "excludedTaskIds": [excluded_id]},
    )
    assert response.status_code == 200
    assert response.json()["changed"] == 2
    assert captured["args"][4] == [excluded_id]
