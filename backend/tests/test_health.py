import pytest
from fastapi.testclient import TestClient

from winchat_api.api.routes import health
from winchat_api.config import get_settings
from winchat_api.main import create_app

client = TestClient(create_app())


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_healthz_is_ok_without_touching_dependencies():
    response = client.get("/healthz")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "winchat-api"


def _stub_checks(monkeypatch, llm: health.DependencyCheck, embeddings: health.DependencyCheck):
    """Readiness must be testable without a network — stub the dependency probes."""

    async def fake_llm() -> health.DependencyCheck:
        return llm

    async def fake_embeddings() -> health.DependencyCheck:
        return embeddings

    monkeypatch.setattr(health, "_check_llm", fake_llm)
    monkeypatch.setattr(health, "_check_embeddings", fake_embeddings)


def test_readyz_is_ok_when_every_dependency_answers(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="ok", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
    )

    async def fake_database() -> health.DependencyCheck:
        return health.DependencyCheck(status="ok")

    monkeypatch.setattr(health, "_check_database", fake_database)

    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_reports_a_failing_dependency_as_503(monkeypatch):
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="error", provider="groq", detail="401 unauthorized"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
    )

    response = client.get("/readyz")
    assert response.status_code == 503

    body = response.json()
    assert body["status"] == "error"
    assert body["checks"]["llm"]["detail"] == "401 unauthorized"


def test_unconfigured_dependency_is_tolerated_locally(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="not_configured", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
    )

    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_unconfigured_dependency_fails_readiness_outside_local(monkeypatch):
    """A deployed app missing its API key is not ready, however cheerful it feels."""
    monkeypatch.setenv("APP_ENV", "production")
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="not_configured", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
    )

    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
