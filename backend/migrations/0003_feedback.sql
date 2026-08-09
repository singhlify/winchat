-- Human feedback on answers.
--
-- The eval harness scores answers with assertions and a model judge. This is the third
-- signal RESEARCH.md calls for: real users telling us when an answer was wrong. It is the
-- only one that can catch a failure both other tiers agree is fine.
--
-- Stored with the retrieval trace of the turn it refers to, so a thumbs-down is
-- actionable, "which sources did it have, and what did it do with them", rather than an
-- anonymous complaint.

create table if not exists answer_feedback (
    id              bigserial primary key,
    -- Nullable: anonymous users can rate too. Requiring an account to say "this was wrong"
    -- would filter out most of the signal we actually want.
    user_id         uuid,
    conversation_id uuid references conversations (id) on delete cascade,
    vote            text        not null check (vote in ('up', 'down')),
    question        text        not null,
    answer          text        not null,
    -- Citations, scores, timings and whether it refused, as of the rated turn.
    trace           jsonb,
    model           text,
    created_at      timestamptz not null default now()
);

create index if not exists answer_feedback_created_idx on answer_feedback (created_at desc);
create index if not exists answer_feedback_vote_idx on answer_feedback (vote, created_at desc);

-- No RLS: nothing here is readable through the API at all. Feedback is written by users
-- and read only by us, offline, when deciding what to fix next. A table with no read path
-- needs no row policy, and adding one would imply a read path exists.
