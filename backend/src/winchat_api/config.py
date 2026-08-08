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
    # For EMBEDDING_PROVIDER=fastembed: same nomic weights, run in-process through ONNX.
    # Its vectors are NOT interchangeable with Ollama's despite the identical model name —
    # switching requires a re-ingest, which the pipeline triggers automatically because
    # model_id changes.
    fastembed_model: str = "nomic-ai/nomic-embed-text-v1.5"
    # Baked into the image at build time so a cold start does not download the model.
    fastembed_cache_dir: str | None = None
    # For EMBEDDING_PROVIDER=cohere (the deployed configuration). Hosted, so the model is
    # not resident in the container — which is the entire reason it is the shipped choice.
    # The dimension is part of the vector space, not a formatting detail: embed-v4.0 is
    # Matryoshka-trained and serves 256/512/1024/1536 from the same weights, so it is
    # carried in model_id and must match `faq_chunks.embedding`'s declared width.
    cohere_embed_model: str = "embed-v4.0"
    cohere_embed_dimension: int = 1024
    # Two budgets because the two callers have opposite tolerances. A user waiting on a
    # chat response gets seconds; an offline ingest can afford to sit out a whole
    # rate-limit window rather than abort 400 answers in. Cohere trial keys allow 100
    # embed calls/minute and ingestion makes one per answer, so it WILL hit the limit.
    embedding_retry_budget_s: float = 20.0
    embedding_ingest_retry_budget_s: float = 300.0

    # --- retrieval ---
    # Wide recall then narrow precision: cast a big net with cheap retrieval, then let the
    # expensive cross-encoder pick. A reranker cannot recover a passage retrieval never saw.
    retrieval_dense_k: int = 50
    # HNSW inspects at most `ef_search` candidates, so a value below the dense limit caps
    # the arm silently — pgvector's default is 40 against a limit of 50. Higher costs
    # latency and buys recall; 100 gives headroom over the limit without being reckless.
    # Only applies once the corpus is large enough that the planner prefers the index over
    # a sequential scan, which is exactly when nobody is looking.
    retrieval_hnsw_ef_search: int = 100
    retrieval_lexical_k: int = 50
    retrieval_rrf_k: int = 60
    rerank_pool: int = 40  # candidates handed to the reranker
    retrieval_top_n: int = 6  # passages that reach the model

    # Refuse to answer when nothing retrieved is close enough. Recalibrated for Cohere
    # embed-v4.0 by `python -m winchat_api.chat.calibrate`:
    #   on-topic  0.4641-0.7117
    #   off-topic 0.1492-0.2891
    # 0.38 sits mid-gap with ~0.09 margin either side. Note the absolute numbers are much
    # lower than nomic's and mean nothing on their own — what matters is the separation,
    # and this model spreads the two classes across 38% of the on-topic floor where the
    # Ollama runtime managed 5%.
    #
    # "Admission requirements at the University of Toronto" still scores 0.4852, inside the
    # on-topic range, on this model as on every previous one. No threshold catches it; the
    # prompt's grounding rule does. That is why there are two defences.
    #
    # This number is specific to the model AND the runtime. RECALIBRATE if either changes —
    # the calibrate script exists so that costs one command.
    refusal_min_dense_score: float = 0.38
    # A second gate on reranker relevance. Left off until it can be calibrated with a real
    # Cohere key; shipping an uncalibrated threshold is worse than shipping none.
    refusal_min_rerank_score: float | None = None

    rerank_provider: str = "cohere"  # cohere | llm | none
    # Ordering candidates is far easier than answering from them, so the rerank stage
    # uses a small fast model; putting the slow one here doubles every question's latency.
    rerank_llm_model: str = "llama-3.1-8b-instant"
    rerank_model: str = "rerank-v3.5"
    rerank_timeout_s: float = 15.0
    # Small on purpose: this is in the request path. Cohere trial keys allow 10 calls
    # per minute, and without any retry a burst degrades to unranked order silently.
    rerank_retry_budget_s: float = 8.0
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
    # Ratcheted from 0.85: recall has measured 100% across three embedding models and two
    # rerankers, so 0.85 no longer fails anything. Retrieval is the least noisy metric here
    # — it does not depend on a judge — which makes it the one safe to tighten. The
    # judge-scored gates below stay where they are; a metric that moves a few points between
    # identical runs needs headroom or it gets switched off the first time it cries wolf.
    eval_min_retrieval_recall: float = 0.95
    eval_min_deterministic_pass: float = 0.85
    eval_min_faithfulness: float = 0.90
    eval_min_correctness: float = 0.85

    # --- auth & abuse control ---
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # only for legacy HS256 projects
    # Signing in is optional: the FAQ is public, and gating a public question behind a
    # login is theatre. Auth buys history, isolation, and a higher rate limit.
    require_auth: bool = False

    # Anonymous callers. Identified by a salted hash of their address, which is cheap to
    # change — a different network or a VPN mints a fresh identity — so the budget is small.
    rate_limit_per_hour: int = 20
    rate_limit_per_day: int = 60
    # Signed-in callers. Higher because the identity is stronger, not as a reward: a verified
    # account costs an email round-trip to create, so the budget is harder to farm than an IP
    # hash. This is what makes "sign in for more" a real statement rather than a marketing one
    # — the docstrings claimed it before the code did.
    rate_limit_user_per_hour: int = 100
    rate_limit_user_per_day: int = 400
    rate_limit_global_per_day: int = 2000  # the actual spend ceiling (OWASP LLM10)
    # Salts the hash of anonymous client addresses. Change it and every anonymous caller
    # becomes a new subject, which is the intended blast radius of rotating it.
    rate_limit_salt: str = "winchat-dev-salt"
    # Off by default. X-Forwarded-For is client-supplied; trusting it without a proxy in
    # front lets anyone mint a fresh rate-limit identity per request. Turn it on only where
    # a known proxy (Render, Vercel) actually sets it.
    trust_proxy_headers: bool = False
    # A maintenance credential for testing a DEPLOYED instance without tripping the
    # per-visitor rate limit. Blank disables the path entirely, which is the default.
    #
    # Scope is deliberately tiny, and the name says so: it waives the per-subject caps and
    # NOTHING else. It grants no data access, bypasses no Row Level Security, and cannot
    # exceed the global daily spend ceiling. A leaked value costs a noisy log line and some
    # of the day's request budget — not the database, and not an unbounded bill.
    #
    # This is not an admin account, and resisting the urge to make it one is the point:
    # "one credential that can do everything" is the shape of every breach post-mortem.
    maintenance_token: str | None = None
    # Reject expensive POSTs that carry no browser `Origin`. CORS is enforced by browsers
    # only, so without this a script can call /api/chat freely — measured returning 200
    # against the deployed service. Off for local curl work and in tests; see security/origin.py
    # for what it is and is not worth.
    require_browser_origin: bool = True

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
