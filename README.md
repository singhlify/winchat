# WinChat — production RAG over the UWindsor FAQ

A retrieval-augmented generation (RAG) assistant that answers University of Windsor
questions grounded in the public `ask.uwindsor.ca` knowledge base — with clickable
citations, a calibrated "I don't know", and an evaluation suite that gates CI.

> RAG = retrieve relevant passages from a corpus, then have a language model answer using
> only those passages. The interesting engineering is in the retrieval and in proving the
> answers are actually grounded — not in the model call.

**556 FAQ answers · 665 indexed chunks · hybrid retrieval · 96 backend tests**

> **Not affiliated with the University of Windsor.** WinChat is an independent project
> built over the university's public FAQ service at ask.uwindsor.ca. It quotes and links
> to that content; it does not republish it, and it is not an official channel. For
> anything official, use [ask.uwindsor.ca](https://ask.uwindsor.ca).

---

## Why the pieces are the way they are

| Decision | Reason |
|---|---|
| **Python (FastAPI) is the AI core** | Retrieval, generation and evaluation are all Python. The frontend is a client, not the identity of the system. |
| **Provider-agnostic LLM layer** | Every call goes through a `ChatProvider` protocol. Swapping Groq for Anthropic is one registry entry and one env var — written by hand rather than delegated to a framework, because that abstraction is the point. |
| **Open-weight models via Groq** | Groq is a fast host for open weights, not an open-source vendor. The win is portability: the same model runs on Groq, Together, or self-hosted vLLM. |
| **Embeddings behind a provider interface** | Four implementations — open `nomic-embed-text` (Ollama or in-process ONNX) and hosted Cohere — selected by one env var. **The deployed configuration uses Cohere, which is not open-weight.** That is a deliberate trade and is called out rather than glossed: see below. |
| **pgvector inside Postgres** | Vectors and application data in one database. A second managed vector store is a system to operate, back up and pay for, at a scale that does not need it. |
| **Plain SQL, never `supabase-js`** | Supabase is ordinary Postgres. Keeping data access in SQL means the database can move to any host unchanged. `supabase-js` is used in one place only: browser login. |
| **The eval harness is the centrepiece** | Anyone can wire an LLM to a vector store. Being able to say *how good it is, measured how* is the part that separates a system from a demo. |

## Architecture

```
 Browser (Next.js, Vercel)
      │  POST /api/chat        ← SSE stream: sources first, then tokens
      ▼
 FastAPI  (Render)  ── the AI core
      │
      ├─ rate limit + circuit breaker      Postgres counters (OWASP LLM10)
      ├─ auth: verify Supabase JWT         local ES256 verification via JWKS
      ├─ query rewrite (multi-turn only)
      ├─ hybrid retrieval  ──┬─ dense: pgvector cosine, top 50
      │                      └─ lexical: Postgres FTS, top 50
      ├─ Reciprocal Rank Fusion (k=60, ranks not scores)
      ├─ Cohere Rerank → top 6            optional; degrades to fused order
      ├─ refusal gate                     calibrated similarity threshold
      └─ grounded generation (Groq)       cites [n]; URLs never enter the prompt
      ▼
 Postgres + pgvector (Supabase) · Row Level Security FORCEd on user data

 OFFLINE — never in the request path
   ingestion:  answers.jsonl → chunk → embed → upsert → reconcile deletions
   evaluation: golden set → deterministic checks → LLM judge → CI gate
```

Ingestion and evaluation never run inside a request. Embedding documents during a chat
request is the classic mistake this separation exists to avoid.

## Retrieval, and why it is hybrid

Dense vector search fails *structurally* on exact strings — course codes, form numbers,
`UWinsite` — because a fixed-length vector cannot encode exact string identity. No better
embedding model fixes it. Keyword search has the mirror failure: it cannot connect "how
much does it cost" to "tuition fees". Both arms run concurrently and are fused.

Fusion is over **ranks, not scores**. Cosine similarity and `ts_rank_cd` are not on
comparable scales, and a weighted sum of the two would invent a calibration that does not
exist.

One measured example: the first lexical implementation used `plainto_tsquery`, which ANDs
every term — so *"deadline to drop a course without penalty"* required all six words in one
chunk and matched **nothing**. Rewriting the operators to OR moved the correct answer to
rank 1.

## The "I don't know", and why there are two of them

A refusal threshold was **calibrated, not guessed** — the best dense similarity measured
over 8 on-topic and 8 off-topic questions against this corpus:

| | range |
|---|---|
| on-topic | 0.7329 – 0.8328 |
| off-topic | 0.5323 – 0.6952 *(one outlier at 0.7849)* |

A threshold of **0.70** sits in that gap. Below it the model is never called at all — no
tokens, no latency, no opportunity to hallucinate.

The outlier is the argument for a second defence. *"What are the admission requirements at
the University of Toronto?"* scores 0.7849 against UWindsor's own admissions FAQ, because
the questions genuinely are near-identical in meaning. No threshold can separate them; only
a reader notices it names a different university. The prompt's grounding rule catches it —
the model replies that the sources cover Windsor, not Toronto.

The threshold is specific to the embedding model and this corpus. Cosine scores are not
comparable across models, so changing either means recalibrating — three times so far
(0.70 → 0.66 → 0.38), which is why `python -m winchat_api.chat.calibrate` reproduces the
whole procedure in one command instead of living in a runbook.

## The open-weight claim, stated honestly

The pipeline was built to be free of vendor lock-in, and the LLM layer still is: Groq hosts
open weights and swaps to Anthropic or a self-hosted vLLM through one registry entry.

**Embeddings in the deployed configuration do not meet that bar.** They run on Cohere's
`embed-v4.0`, whose weights are closed. The reason is hosting economics, not quality: the
in-process open model made the container 920 MB and no free tier fits that. Hosted
embeddings took it to 51 MB.

What survives the trade is the part that was actually load-bearing — the interface. Going
back is `EMBEDDING_PROVIDER=fastembed`, `uv sync --extra local`, and a re-ingest; the
provider is still in the tree and still tested. The swap was gated on measured retrieval
quality rather than assumed to be harmless, and recall held at 100% while MRR improved
0.741 → 0.847.

An architecture that claims portability and has never exercised it is a claim. This one has
now been moved across three embedding runtimes and two dimensionalities, which is evidence.

## Evaluation

Three properties make it worth trusting:

1. **It runs the real pipeline.** The same `answer_question` the HTTP endpoint calls — an
   eval against a parallel implementation eventually measures something users never touch.
2. **Two tiers.** Deterministic checks first (citation validity, required facts, forbidden
   patterns, retrieval recall and MRR) — no model, no cost, no variance. Then an LLM judge
   for faithfulness and correctness, scored separately because they fail independently.
3. **The judge is a different model family from the generator.** Models prefer their own
   outputs; a same-family judge inflates every number it produces. The generator is Llama,
   the judge is GPT-OSS, and the report always names both — "92% faithful" is meaningless
   without saying who graded it.

The golden set is hand-written with expectations read out of the actual corpus, including
a case whose correct answer is *a pointer, not a date* (the FAQ deliberately does not state
the drop deadline) — with a regex asserting no date is invented.

```bash
uv run python -m winchat_api.evals.run            # both tiers, gated, exits non-zero on failure
uv run python -m winchat_api.evals.run --tier1    # deterministic only, zero model cost
```

### What the first run actually found

The suite failed on its first execution, which is the point of building it.

**It found a retrieval bug.** Recall was 72.2%. Diagnosis showed the correct answer was
ranked **#1 by dense search** in three of the five misses but pushed to rank 8–11 by
fusion — and the six final slots were being spent on three or four distinct answers,
because the same FAQ article occupied several of them. Deduplicating to one chunk per
answer before the cut moved recall to **83.3%** and MRR from 0.383 to 0.409.

**It quantified whether the reranker is worth adding.** After that fix:

| | |
|---|---|
| recall inside the 40-candidate pool | **100%** |
| recall at top-6, what reaches the model | **83.3%** |

The right answer is *always* retrieved and sometimes ranked too low — precisely the
condition under which a cross-encoder earns its latency, and the opposite of the case where
it cannot help. That gap, not the project plan, is the argument for the Cohere key.

**It found a bug in the judge itself.** The first judge marked every *correct* refusal as
unfaithful ("claims the FAQ lacks information, which no source states") and incorrect
("does not provide the capital of France") — and graded a successfully resisted prompt
injection as a failure for "not replying with BANANA". The judge was scoring the system
against a general-assistant contract. Both prompts now state what the system under test is
required to do, and the correctness judge receives the sources so it can tell a justified
refusal from a lazy one. A judge that does not know the contract measures the wrong system,
confidently.

Baseline numbers are from a run against `qwen/qwen3.6-27b` rather than the pinned reference
model, because Groq's free tier allows roughly one full suite run per model per day
(12k tokens/minute, 100k/day) and the reference model's budget was spent. Each model has its
own bucket, which is how the suite ran at all — and why CI will need a paid tier.

## Running it locally

Prerequisites: [`uv`](https://docs.astral.sh/uv/) and Node 20+ with pnpm. Embeddings are
hosted by default, so nothing needs to be downloaded to run this — set `COHERE_API_KEY` and
go. To run them locally on open weights instead, add `uv sync --extra local` and set
`EMBEDDING_PROVIDER=fastembed` (in-process, no daemon) or `ollama` (needs
`ollama pull nomic-embed-text`). Either choice re-embeds the corpus on the next ingest,
automatically, because the stored `model_id` changes.

```bash
# backend — the AI core
cd backend
cp .env.example .env          # set GROQ_API_KEY, COHERE_API_KEY and DATABASE_URL
uv sync
uv run python -m winchat_api.db.migrate          # schema + pgvector + RLS
uv run python -m winchat_api.ingestion.run       # chunk, embed, upsert
uv run uvicorn winchat_api.main:app --reload     # http://localhost:8000

# frontend — second terminal
cd frontend
cp .env.example .env.local
pnpm install && pnpm dev                          # http://localhost:3000
```

Checks:

```bash
curl localhost:8000/healthz      # liveness — no external calls
curl localhost:8000/readyz       # readiness — one real call per dependency
cd backend && uv run python -m winchat_api.ask "how do I drop a course?"
```

`/healthz` and `/readyz` are separate on purpose. Liveness makes no external calls, so a
slow third party never restarts the service. Readiness exercises every dependency and
reports each one's status, model and latency — and an unconfigured dependency reports
`not_configured`, never `ok`, which is fatal outside local development. A health check that
reports green while missing its API key is worse than no health check.

## Security posture

- **Row Level Security, FORCEd.** `ENABLE` alone is not enough: Postgres exempts a table's
  owner from its own policies, and the API owns these tables — so the policy would look
  right in the schema and enforce nothing. Verified by test: a second user reads zero rows
  even when targeting a conversation id directly, and cannot forge a row as someone else.
- **Rate limits as a feature** (OWASP LLM10). A per-subject rolling window plus a global
  daily circuit breaker, because per-user limits do not bound total spend — users are not
  bounded. Anonymous callers are identified by a *salted hash* of their address; rate
  limiting needs to tell clients apart, not to identify anyone.
- **Prompt injection** (OWASP LLM01). For RAG the dangerous form is indirect — instructions
  smuggled inside a retrieved document. The system prompt treats source text as content,
  never as instructions, and the golden set contains injection attempts as test cases.
- **Signed-in history comes from the database, not the request body.** A client that can
  invent its own history can invent assistant turns to steer the model.
- **JWTs are verified locally** against the project's published JWKS, so the API's
  availability does not depend on the auth service being reachable.

## Documentation

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — goal, hard constraints, how to work
- [`docs/STATE.md`](./docs/STATE.md) — current status, decisions, what was rejected
- [`docs/PLAN.md`](./docs/PLAN.md) — architecture, hosting, phased build
- [`docs/RESEARCH.md`](./docs/RESEARCH.md) — the research behind every choice
- [`docs/DATA.md`](./docs/DATA.md) — the corpus and its scraper

## Scaling story

Stateless backend behind a load balancer; Postgres read replicas; move vectors to a
dedicated store past roughly a million chunks; a queue for ingestion; swap Groq for
self-hosted vLLM if volume ever justifies it; add online drift monitoring alongside the
offline CI gate. Detail in `docs/RESEARCH.md` §2, §5, §8.
