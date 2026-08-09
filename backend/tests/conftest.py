"""Shared test setup.

Every test runs against a known, empty configuration. Never the developer's `.env`.

This exists because the suite passed locally and failed the moment it ran anywhere else.
`pydantic-settings` reads `backend/.env`, so a machine with real keys and a machine
without them were running different code paths: with a Cohere key the reranker health
check reported `ok`, without one it reported `error`, and three readiness tests silently
depended on which machine you were sitting at.

A test that passes only on a machine with credentials is not a test, it is a coincidence.
"""

import pytest

from winchat_api.config import get_settings
from winchat_api.retrieval.rerank.registry import get_reranker

# Anything a developer's .env might supply. Set to empty rather than deleted, because
# deleting the process variable still leaves the value in the .env file.
AMBIENT_SETTINGS = (
    "GROQ_API_KEY",
    "COHERE_API_KEY",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_JWT_SECRET",
    "EMBEDDING_API_KEY",
)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch):
    """Neutralise ambient configuration, then clear the caches that hold it.

    `get_settings` and `get_reranker` are both `lru_cache`d, so clearing them on the way in
    AND out matters: a test that changes the environment would otherwise leak its settings
    into whichever test ran next.
    """
    for name in AMBIENT_SETTINGS:
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("APP_ENV", "test")
    # TestClient sends no `Origin`, so leaving the browser-origin guard on would turn every
    # chat and feedback test into a 403. They would still pass or fail, but for the wrong
    # reason. The guard has its own dedicated tests in test_security.py.
    monkeypatch.setenv("REQUIRE_BROWSER_ORIGIN", "false")

    get_settings.cache_clear()
    get_reranker.cache_clear()
    yield
    get_settings.cache_clear()
    get_reranker.cache_clear()
