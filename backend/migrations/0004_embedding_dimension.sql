-- Widen `faq_chunks.embedding` from 768 to 1024 dimensions.
--
-- Why: embeddings moved out of the container to Cohere's hosted endpoint, so the app fits
-- a 512 MB free instance instead of needing 920 MB for a resident model. Cohere's
-- embed-v4.0 serves 1024 dimensions where nomic-embed-text served 768.
--
-- Why this is a migration and not a config value: a pgvector column declares its width in
-- the type, and vectors of different widths cannot be compared at all. Postgres refuses
-- the operator rather than returning bad results. Changing embedding model *families* is
-- therefore a schema change, which is the correct amount of friction for an operation that
-- invalidates every stored vector.
--
-- The delete is not data loss. Chunks are derived data, regenerated in about five minutes
-- by `python -m winchat_api.ingestion.run`. `faq_answers` (the source records) is
-- untouched, and because `_existing_state` reads `embedding_model` through a LEFT JOIN,
-- every answer comes back as needing work automatically, no --force flag required.
--
-- Run the ingestion immediately after this migration. Between the two, retrieval returns
-- nothing: the table is empty, which is a visible failure rather than a silent one.

drop index if exists faq_chunks_embedding_idx;

delete from faq_chunks;

alter table faq_chunks
    alter column embedding type vector(1024);

create index faq_chunks_embedding_idx
    on faq_chunks using hnsw (embedding vector_cosine_ops);
