"""Application configuration.

Everything is environment-driven. Paths are derived from this file's location so the
app behaves identically no matter which directory it is launched from — no absolute
paths anywhere (a named anti-goal, see CONTRIBUTING.md).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> winchat_api -> src -> backend -> <repo root>
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_env: str = "local"
    log_level: str = "INFO"
    # Comma-separated in the environment; parsed by the validator below.
    cors_allow_origins: str = "http://localhost:3000"

    # --- LLM (provider-agnostic; see llm/registry.py) ---
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: float = 30.0
    groq_api_key: str | None = None

    # --- embeddings (provider-agnostic; see embeddings/registry.py) ---
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_s: float = 30.0
    ollama_base_url: str = "http://localhost:11434"

    # --- retrieval ---
    # Wide recall then narrow precision: cast a big net with cheap retrieval, then let the
    # expensive cross-encoder pick. A reranker cannot recover a passage retrieval never saw.
    retrieval_dense_k: int = 50
    retrieval_lexical_k: int = 50
    retrieval_rrf_k: int = 60
    rerank_pool: int = 40  # candidates handed to the reranker
    retrieval_top_n: int = 6  # passages that reach the model

    rerank_provider: str = "cohere"  # or "none"
    rerank_model: str = "rerank-v3.5"
    rerank_timeout_s: float = 15.0
    cohere_api_key: str | None = None

    # --- data / database ---
    # Phase 2 will fill this in (Supabase Postgres + pgvector).
    database_url: str | None = None
    corpus_path: Path = Field(default=REPO_ROOT / "data" / "ask_uwindsor" / "answers.jsonl")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the whole process shares one Settings instance."""
    return Settings()
