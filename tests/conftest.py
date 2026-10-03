import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import build_services
from tests.fakes import HashEmbedder


@pytest.fixture
def settings(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        arxiv_request_delay_seconds=0,
        arxiv_backoff_seconds=0,
        pdf_download_delay_seconds=0,
    )
    settings.ensure_dirs()
    return settings


@pytest.fixture
def services(settings):
    return build_services(settings, embedder=HashEmbedder())


@pytest.fixture
def client(settings, services):
    with TestClient(create_app(settings, services)) as test_client:
        yield test_client


@pytest.fixture
def db(client):
    with client.app.state.session_factory() as session:
        yield session
