from fastapi.testclient import TestClient

from app.main import create_app
from tests.factories import make_paper, make_query, uniform_scores


def test_status_reports_database_counts(client, db):
    make_paper(db)
    body = client.get("/api/system/status").json()
    assert body["components"]["database"]["status"] == "ok"
    assert body["counts"]["papers"] == 1
    assert body["counts"]["chunks"] == 2
    assert body["counts"]["weight_snapshots"] == 1


def test_initial_weights_are_seeded_once(settings):
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            history = client.get("/api/improvement/history").json()
    assert len(history["snapshots"]) == 1
    assert history["snapshots"][0]["trigger"] == "init"
    assert history["current"] == {
        "alpha": settings.alpha_init,
        "beta": settings.beta_init,
        "gamma": settings.gamma_init,
    }


def test_get_paper(client, db):
    make_paper(db)
    body = client.get("/api/papers/2401.00001").json()
    assert body["chunk_count"] == 2
    assert body["chunks"] is None
    with_chunks = client.get("/api/papers/2401.00001", params={"include_chunks": True}).json()
    assert [c["section"] for c in with_chunks["chunks"]] == ["Introduction", "Method"]


def test_get_paper_with_old_style_id(client, db):
    make_paper(db, paper_id="cs/0112017")
    assert client.get("/api/papers/cs/0112017").json()["id"] == "cs/0112017"


def test_unknown_paper_and_query_return_404(client):
    assert client.get("/api/papers/9999.99999").status_code == 404
    assert client.get("/api/query/42").status_code == 404


def test_get_query_detail(client, db):
    record = make_query(db, make_paper(db), scores=uniform_scores(0.8))
    body = client.get(f"/api/query/{record.id}").json()
    assert [r["rank"] for r in body["retrieved"]] == [1, 2]
    assert [r["cited"] for r in body["retrieved"]] == [True, False]
    assert body["citations"][0]["paper_id"] == "2401.00001"
    assert body["evaluation"]["groundedness"] == 0.8
    assert body["weights"] == {"alpha": 0.7, "beta": 0.15, "gamma": 0.15}


def test_feedback_is_stored(client, db):
    record = make_query(db, make_paper(db))
    response = client.post(
        "/api/feedback",
        json={"query_id": record.id, "rating": 1, "chunk_id": "2401.00001#1", "comment": "useful"},
    )
    assert response.status_code == 201
    detail = client.get(f"/api/query/{record.id}").json()
    assert detail["feedback"][0]["rating"] == 1
    assert detail["feedback"][0]["chunk_id"] == "2401.00001#1"


def test_feedback_validation(client, db):
    paper = make_paper(db)
    record = make_query(db, paper)
    pending = make_query(db, paper, status="pending")
    assert client.post("/api/feedback", json={"query_id": record.id, "rating": 0}).status_code == 422
    assert client.post("/api/feedback", json={"query_id": 999, "rating": 1}).status_code == 404
    assert client.post("/api/feedback", json={"query_id": pending.id, "rating": 1}).status_code == 409
    unrelated = {"query_id": record.id, "rating": 1, "chunk_id": "other#0"}
    assert client.post("/api/feedback", json=unrelated).status_code == 422


def test_metrics_aggregate_by_mode(client, db):
    paper = make_paper(db)
    make_query(db, paper, mode="baseline", scores=uniform_scores(0.4), total_ms=1000)
    make_query(db, paper, mode="baseline", scores=uniform_scores(0.6), total_ms=3000)
    proposed = make_query(db, paper, mode="proposed", scores=uniform_scores(0.9), total_ms=2000)
    make_query(db, paper, mode="proposed")
    client.post("/api/feedback", json={"query_id": proposed.id, "rating": 1})
    client.post("/api/feedback", json={"query_id": proposed.id, "rating": -1})

    modes = {m["mode"]: m for m in client.get("/api/metrics").json()["modes"]}
    assert modes["baseline"]["queries"] == 2
    assert modes["baseline"]["means"]["groundedness"] == 0.5
    assert modes["baseline"]["mean_latency_ms"] == 2000
    assert modes["proposed"]["queries"] == 2
    assert modes["proposed"]["evaluated"] == 1
    assert modes["proposed"]["means"]["overall"] == 0.9
    assert (modes["proposed"]["positive_feedback"], modes["proposed"]["negative_feedback"]) == (1, 1)


def test_metrics_empty_database(client):
    modes = client.get("/api/metrics").json()["modes"]
    assert [m["mode"] for m in modes] == ["baseline", "proposed"]
    assert all(m["queries"] == 0 and m["means"]["overall"] is None for m in modes)
