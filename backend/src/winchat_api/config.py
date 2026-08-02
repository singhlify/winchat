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
    # A curated allowlist, not everything the provider serves. Exposing weak models makes
    # the product look bad for a failure that is not the pipeline's, and an unvalidated
    # model name from a client is an open proxy to whatever the provider will bill for.
    llm_allowed_models: str = (
        "llama-3.3-70b-versatile,openai/gpt-oss-120b,qwen/qwen3.6-27b,llama-3.1-8b-instant"
    )
    llm_timeout_s: float = 30.0
    # Providers meter by tokens per minute and Groq's free tier is low enough to hit. How
    # long to wait is a per-caller decision: a user watching a chat box gets seconds.
    llm_retry_budget_s: float = 20.0
    groq_api_key: str | None = None

    # --- embeddings (provider-agnostic; see embeddings/registry.py) ---
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_s: float = 30.0
    ollama_base_url: str = "http://localhost:11434"
    # For EMBEDDING_PROVIDER=openai_compatible (deployment). Must serve the SAME model the
    # corpus was ingested with — a query embedded by a different model retrieves confident
    # nonsense rather than raising.
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None

    # --- retrieval ---
    # Wide recall then narrow precision: cast a big net with cheap retrieval, then let the
    # expensive cross-encoder pick. A reranker cannot recover a passage retrieval never saw.
    retrieval_dense_k: int = 50
    retrieval_lexical_k: int = 50
    retrieval_rrf_k: int = 60
    rerank_pool: int = 40  # candidates handed to the reranker
    retrieval_top_n: int = 6  # passages that reach the model

    # Refuse to answer when nothing retrieved is close enough. Calibrated by measuring the
    # best dense similarity over 8 on-topic and 8 off-topic questions against this corpus:
    # on-topic 0.7329-0.8328, off-topic 0.5323-0.6952 with one outlier at 0.7849. 0.70 sits
    # in that gap. The number is specific to nomic-embed-text and this corpus — RECALIBRATE
    # when either changes, because cosine scores are not comparable across models.
    refusal_min_dense_score: float = 0.70
    # A second gate on reranker relevance. Left off until it can be calibrated with a real
    # Cohere key; shipping an uncalibrated threshold is worse than shipping none.
    refusal_min_rerank_score: float | None = None

    rerank_provider: str = "cohere"  # cohere | llm | none
    # Ordering candidates is far easier than answering from them, so the rerank stage
    # uses a small fast model; putting the slow one here doubles every question's latency.
    rerank_llm_model: str = "llama-3.1-8b-instant"
    rerank_model: str = "rerank-v3.5"
    rerank_timeout_s: float = 15.0
    cohere_api_key: str | None = None

    # --- evaluation ---
    # Pinned separately from the app model. Users may pick any model; a quality claim is
    # only coherent if it names one, so the eval always runs against this one.
    eval_model: str = "llama-3.3-70b-versatile"
    # A different model family from the generator on purpose — models prefer their own
    # outputs, and a same-family judge inflates every score it produces.
    eval_judge_model: str = "openai/gpt-oss-120b"
    # Low on purpose: the whole suite against one model exceeds Groq's free-tier
    # tokens-per-minute budget, so concurrency mostly buys retries, not speed.
    eval_concurrency: int = 2
    # Offline work can afford to wait out a per-minute budget; a chat request cannot.
    eval_retry_budget_s: float = 900.0

    # CI gates. Set from the first measured baseline, then ratcheted up — never guessed,
    # because a threshold nobody can meet gets disabled and one nobody can fail is decoration.
    eval_min_retrieval_recall: float = 0.85
    eval_min_deterministic_pass: float = 0.85
    eval_min_faithfulness: float = 0.90
    eval_min_correctness: float = 0.85

    # --- auth & abuse control ---
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # only for legacy HS256 projects
    # Signing in is optional: the FAQ is public, and gating a public question behind a
    # login is theatre. Auth buys history, isolation, and a higher rate limit.
    require_auth: bool = False

    rate_limit_per_hour: int = 20
    rate_limit_per_day: int = 60
    rate_limit_global_per_day: int = 2000  # the actual spend ceiling (OWASP LLM10)
    # Salts the hash of anonymous client addresses. Change it and every anonymous caller
    # becomes a new subject, which is the intended blast radius of rotating it.
    rate_limit_salt: str = "winchat-dev-salt"
    # Off by default. X-Forwarded-For is client-supplied; trusting it without a proxy in
    # front lets anyone mint a fresh rate-limit identity per request. Turn it on only where
    # a known proxy (Render, Vercel) actually sets it.
    trust_proxy_headers: bool = False

    @property
    def supabase_jwks_url(self) -> str | None:
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    # --- data / database ---
    # Phase 2 will fill this in (Supabase Postgres + pgvector).
    database_url: str | None = None
    corpus_path: Path = Field(default=REPO_ROOT / "data" / "ask_uwindsor" / "answers.jsonl")

    @property
    def allowed_models(self) -> list[str]:
        models = [m.strip() for m in self.llm_allowed_models.split(",") if m.strip()]
        # The configured default is always selectable, even if omitted from the list.
        return models if self.llm_model in models else [self.llm_model, *models]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the whole process shares one Settings instance."""
    return Settings()
