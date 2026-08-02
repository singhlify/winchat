-- Conversation history, per-user isolation, and usage accounting.
--
-- Row Level Security is the point of this migration. Postgres enforces "you can only see
-- your own conversations" in the database itself, so no application query can leak another
-- user's data by forgetting a WHERE clause. Application-layer permission checks fail open
-- when someone writes a new query; RLS fails closed.

-- ---------------------------------------------------------------- conversations

create table if not exists conversations (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid        not null,        -- Supabase auth.users.id
    title      text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists conversations_user_idx on conversations (user_id, updated_at desc);

create table if not exists messages (
    id              bigserial primary key,
    conversation_id uuid        not null references conversations (id) on delete cascade,
    user_id         uuid        not null,   -- denormalized so RLS needs no join
    role            text        not null check (role in ('user', 'assistant')),
    content         text        not null,
    -- The retrieval trace for this turn: citations, scores, timings, whether it refused.
    -- Stored because the eval harness scores logged traces, and a trace you cannot
    -- reconstruct is an answer you cannot debug after the fact.
    trace           jsonb,
    created_at      timestamptz not null default now()
);

create index if not exists messages_conversation_idx on messages (conversation_id, created_at);

-- ENABLE alone is not enough here. Postgres exempts a table's OWNER from its own row
-- policies, and our connection owns these tables — so `enable row level security` would
-- look correct in the schema and enforce nothing at runtime. FORCE removes the exemption.
-- This is the difference between a security control and a security-shaped comment.
alter table conversations enable row level security;
alter table conversations force row level security;
alter table messages enable row level security;
alter table messages force row level security;

-- `auth.uid()` reads the user id out of the request's JWT. With these policies a query for
-- someone else's rows returns zero rows rather than an error — unauthorized data is never
-- in the result set to begin with.
drop policy if exists conversations_owner on conversations;
create policy conversations_owner on conversations
    for all using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists messages_owner on messages;
create policy messages_owner on messages
    for all using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- The API runs user queries as `authenticated` with the request's JWT claims set, which is
-- what makes auth.uid() resolve and the policies above apply.
grant usage on schema public to authenticated;
grant select, insert, update, delete on conversations, messages to authenticated;
grant usage, select on all sequences in schema public to authenticated;

-- ---------------------------------------------------------------- usage accounting

-- Rate limiting is a feature, not a safeguard: OWASP LLM10 (Unbounded Consumption). One
-- table serves both the per-user rolling window and the global daily circuit breaker.
create table if not exists usage_events (
    id           bigserial primary key,
    -- A user id when signed in, otherwise a salted hash of the client address. Raw IPs are
    -- never stored: rate limiting does not require identifying anyone.
    subject      text        not null,
    subject_kind text        not null check (subject_kind in ('user', 'anonymous')),
    occurred_at  timestamptz not null default now(),
    tokens       int         not null default 0
);

create index if not exists usage_events_subject_idx on usage_events (subject, occurred_at desc);
create index if not exists usage_events_recent_idx on usage_events (occurred_at desc);

-- The FAQ corpus is public and identical for everyone, so faq_answers/faq_chunks stay
-- readable without RLS. Access control belongs on user data, not on a published FAQ, and
-- RLS over an HNSW index costs recall (post-scan filtering can return fewer than top-k).
