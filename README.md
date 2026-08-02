# WinChat v2 — Production RAG (UWindsor FAQ assistant)

A production-grade RAG (retrieval-augmented generation) web app that answers University of
Windsor FAQ questions, grounded in the public `ask.uwindsor.ca` knowledge base. Built as a
showcase of shipping **secure, evaluated, useful** RAG systems.

> Stage 2 of a two-stage project. Stage 1 (`../winchat`) was a from-scratch learning rebuild
> of the AI layer; this is the production build.

## Stack
- **Backend / AI core:** Python (FastAPI) — retrieval, reranking, grounded generation, eval
- **Frontend:** Next.js (React/TypeScript) — streaming chat with inline citations
- **Vector store + data:** Postgres + pgvector (Supabase), with Auth + Row-Level Security
- **LLM:** open-weight models via Groq, behind a provider-agnostic interface (swappable)
- **Retrieval:** hybrid (dense + BM25) + RRF + Cohere Rerank
- **Evaluation:** LLM-as-judge (faithfulness + correctness) over a golden set, gated in CI

## Running it locally

Prerequisites: [`uv`](https://docs.astral.sh/uv/), Node 20+ with pnpm, and
[Ollama](https://ollama.com) running with the embedding model pulled
(`ollama pull nomic-embed-text`).

```bash
# backend — the AI core
cd backend
cp .env.example .env          # then set GROQ_API_KEY
uv sync
uv run uvicorn winchat_api.main:app --reload    # http://localhost:8000

# frontend — in a second terminal
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev                                         # http://localhost:3000
```

Verify the whole chain:

```bash
curl localhost:8000/healthz              # liveness — no external calls
curl localhost:8000/readyz               # readiness — one real call per dependency
cd backend && uv run python -m winchat_api.smoke   # real generation + embeddings
```

`http://localhost:3000` shows the same readiness report in the browser, which also proves
the cross-origin path the streaming chat will use.

Checks: `cd backend && uv run pytest && uv run ruff check .` · `cd frontend && pnpm lint`

## Documentation
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — goal, hard constraints, how to work
- [`docs/STATE.md`](./docs/STATE.md) — current status, next steps, decisions made
- [`docs/PLAN.md`](./docs/PLAN.md) — architecture, hosting, phased build, feature→signal map
- [`docs/RESEARCH.md`](./docs/RESEARCH.md) — the verified research behind every choice
- [`docs/DATA.md`](./docs/DATA.md) — the corpus and its scraper

## Status
Phase 1 complete — scaffold runs end to end (browser → FastAPI → Groq + embeddings), with a
readiness endpoint that exercises every dependency. Ingestion into pgvector is next. See
`docs/STATE.md`.
