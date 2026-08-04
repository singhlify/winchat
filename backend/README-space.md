---
title: WinChat API
emoji: 🎓
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: RAG API answering University of Windsor FAQ questions with citations
---

# WinChat API

The Python AI core for [WinChat](https://github.com/singhlify/winchat) — hybrid retrieval
over the University of Windsor's public FAQ, with Cohere reranking, a calibrated refusal
threshold and grounded generation.

Not affiliated with the University of Windsor. Source: https://ask.uwindsor.ca

- `GET /healthz` — liveness
- `GET /readyz` — every dependency, with latency
- `POST /api/chat` — streaming answers (SSE)
- `GET /api/sources` — all 556 indexed articles
