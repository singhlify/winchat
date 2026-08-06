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


# Module-level so it is not a function call in a default argument.
_RERANKER_OK = health.DependencyCheck(status="ok", provider="cohere")


def _stub_checks(
    monkeypatch,
    llm: health.DependencyCheck,
    embeddings: health.DependencyCheck,
    database: health.DependencyCheck | None = None,
    reranker: health.DependencyCheck | None = _RERANKER_OK,
):
    """Readiness must be testable without a network — stub the dependency probes.

    `reranker=None` leaves the real check in place, for the tests that are about the
    reranker itself.
    """
    database = database or health.DependencyCheck(status="not_configured")

    async def fake_llm() -> health.DependencyCheck:
        return llm

    async def fake_embeddings() -> health.DependencyCheck:
        return embeddings

    async def fake_database(pool) -> health.DependencyCheck:
        return database

    monkeypatch.setattr(health, "_check_llm", fake_llm)
    monkeypatch.setattr(health, "_check_embeddings", fake_embeddings)
    monkeypatch.setattr(health, "_check_database", fake_database)

    if reranker is not None:

        async def fake_reranker() -> health.DependencyCheck:
            return reranker

        monkeypatch.setattr(health, "_check_reranker", fake_reranker)


def test_readyz_is_ok_when_every_dependency_answers(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="ok", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
        database=health.DependencyCheck(status="ok", provider="postgres"),
    )

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
    # A valid deployment configuration, so this test fails for the reason it claims to.
    # Without these the config check also errors and readiness reports "error" instead of
    # "degraded" — a passing assertion about the wrong thing.
    monkeypatch.setenv("RATE_LIMIT_SALT", "a-real-random-value-not-the-default")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://winchat.vercel.app")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="not_configured", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
    )

    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_a_requested_but_inactive_reranker_is_an_error_not_a_shrug(monkeypatch):
    """The incident this guards: the API ran a whole session with reranking silently off
    because it was started before the key was added. 17 points of recall, no symptom."""
    monkeypatch.setenv("RERANK_PROVIDER", "cohere")
    # Set empty rather than deleted: pydantic-settings also reads backend/.env, so
    # removing the process variable alone leaves the real key in place.
    monkeypatch.setenv("COHERE_API_KEY", "")
    get_settings.cache_clear()

    from winchat_api.retrieval.rerank.registry import get_reranker

    get_reranker.cache_clear()

    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="ok", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
        reranker=None,
    )

    response = client.get("/readyz")
    body = response.json()

    assert body["checks"]["reranker"]["status"] == "error"
    assert "restart" in body["checks"]["reranker"]["detail"]
    assert response.status_code == 503
    get_reranker.cache_clear()


def test_reranking_switched_off_on_purpose_is_not_an_error(monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "none")
    get_settings.cache_clear()

    from winchat_api.retrieval.rerank.registry import get_reranker

    get_reranker.cache_clear()

    _stub_checks(
        monkeypatch,
        llm=health.DependencyCheck(status="ok", provider="groq"),
        embeddings=health.DependencyCheck(status="ok", provider="ollama"),
        reranker=None,
    )

    assert client.get("/readyz").json()["checks"]["reranker"]["status"] == "not_configured"
    get_reranker.cache_clear()


# --- production configuration guard -------------------------------------------------


def test_non_deployed_envs_skip_the_deployment_checks():
    """The dev defaults are correct off a server; flagging them there is just noise.

    The suite runs with APP_ENV=test, which must be exempt — an earlier version exempted
    only "local" and turned every readiness test red.
    """
    get_settings.cache_clear()

    assert health._check_config().status == "ok"


def test_the_default_rate_limit_salt_is_an_error_in_production(monkeypatch):
    """A public salt makes anonymous subject hashes computable, and nothing else notices.

    This is the failure mode the check exists for: the app works perfectly with the default
    salt. Nothing breaks, no request fails, no log line appears — the limiter is simply
    weaker than it looks, until someone works out that the salt is in the repository.
    """
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    check = health._check_config()

    assert check.status == "error"
    assert "RATE_LIMIT_SALT" in (check.detail or "")


def test_localhost_cors_in_production_is_an_error(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RATE_LIMIT_SALT", "a-real-random-value-not-the-default")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    check = health._check_config()

    assert check.status == "error"
    assert "CORS" in (check.detail or "")


def test_proxy_headers_off_in_production_is_an_error(monkeypatch):
    """Off behind a proxy, every visitor collapses into one rate-limit identity."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RATE_LIMIT_SALT", "a-real-random-value-not-the-default")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://winchat.vercel.app")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    get_settings.cache_clear()

    check = health._check_config()

    assert check.status == "error"
    assert "TRUST_PROXY_HEADERS" in (check.detail or "")


def test_a_correctly_configured_production_passes(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RATE_LIMIT_SALT", "a-real-random-value-not-the-default")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://winchat.vercel.app")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    assert health._check_config().status == "ok"
