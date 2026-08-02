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

## Documentation
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — goal, hard constraints, how to work
- [`docs/STATE.md`](./docs/STATE.md) — current status, next steps, decisions made
- [`docs/PLAN.md`](./docs/PLAN.md) — architecture, hosting, phased build, feature→signal map
- [`docs/RESEARCH.md`](./docs/RESEARCH.md) — the verified research behind every choice
- [`docs/DATA.md`](./docs/DATA.md) — the corpus and its scraper

## Status
Bootstrapping — planning complete, corpus scraped, app scaffold next. See `docs/STATE.md`.
