-- Corpus tables for the UWindsor FAQ assistant.
--
-- Two tables, not one: `faq_answers` mirrors the source record (one row per published
-- FAQ answer) and `faq_chunks` holds the retrievable pieces. Keeping the source row
-- separate is what makes deletion handling and incremental refresh honest. We can diff
-- the live corpus against `faq_answers` by primary key, and `content_hash` tells us
-- whether an answer actually changed or just got a new lastmod stamp.

create extension if not exists vector;

create table if not exists faq_answers (
    a_id          text primary key,          -- the source system's stable answer id
    question      text        not null,
    answer_text   text        not null,
    url           text        not null,
    lastmod       timestamptz,               -- from the site's sitemap
    content_hash  text        not null,      -- sha256(question + answer_text); skips re-embedding
    fetched_at    timestamptz,
    ingested_at   timestamptz not null default now()
);

create table if not exists faq_chunks (
    id              bigserial primary key,
    a_id            text        not null references faq_answers (a_id) on delete cascade,
    chunk_index     int         not null,
    -- `content` is the raw chunk, shown to the user and fed to the model as context.
    content         text        not null,
    -- `context_text` is `content` with its parent question prepended. It is what we embed
    -- AND what full-text search indexes, so a chunk from the middle of a long answer still
    -- carries what question it answers. (Contextual retrieval, see RESEARCH.md §1.)
    context_text    text        not null,
    token_estimate  int         not null,
    embedding       vector(768) not null,
    embedding_model text        not null,    -- vectors from different models are not comparable
    created_at      timestamptz not null default now(),
    unique (a_id, chunk_index)
);

-- Dense retrieval (meaning-based). Cosine distance matches how nomic-embed is trained.
create index if not exists faq_chunks_embedding_idx
    on faq_chunks using hnsw (embedding vector_cosine_ops);

-- Lexical retrieval (exact keyword). Hybrid search needs both: dense vectors structurally
-- cannot do exact term matching on rare strings, and no better embedding model fixes that.
create index if not exists faq_chunks_tsv_idx
    on faq_chunks using gin (to_tsvector('english', context_text));

create index if not exists faq_chunks_a_id_idx on faq_chunks (a_id);
