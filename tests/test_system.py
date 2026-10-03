from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_status_reports_components(client, settings):
    response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["components"]["storage"]["status"] == "ok"
    assert body["components"]["llm"]["status"] == "not_configured"
    assert body["llm"]["api_key_configured"] is False
    assert body["components"]["evaluator"] == {"status": "not_configured", "detail": "same model as llm"}
    assert body["retrieval"]["arxiv_categories"] == settings.arxiv_categories
    assert settings.chroma_dir.is_dir()
    assert settings.pdf_dir.is_dir()


def test_status_never_leaks_api_key(tmp_path):
    secret = "sk-test-should-not-appear"
    settings = Settings(_env_file=None, data_dir=tmp_path, llm_api_key=secret)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/system/status")
    assert response.json()["llm"]["api_key_configured"] is True
    assert secret not in response.text
