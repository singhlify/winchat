-- Take the public API roles off every table that does not need them.
--
-- THE BUG THIS FIXES. Supabase grants `anon` and `authenticated` full DML on every table in
-- the `public` schema by default — including tables created by raw SQL, which is easy to
-- assume are private because no dashboard step ever exposed them. Audited on the live
-- database, both roles held DELETE, INSERT, UPDATE and TRUNCATE on all seven tables, while
-- Row Level Security protected only `conversations` and `messages`.
--
-- That matters because Supabase publishes those tables over PostgREST, and the anon key is
-- shipped to every browser by design. So the reachable consequences were:
--
--   * `usage_events`  — DELETE wipes the rate-limit counters. That table IS the spend
--                       ceiling (OWASP LLM10); emptying it turns metered access into an
--                       open tab against the Groq and Cohere keys.
--   * `faq_chunks`    — INSERT/UPDATE poisons the retrieval corpus. An attacker-authored
--                       chunk comes back as a cited "University of Windsor answer",
--                       which is content injection wearing the app's credibility.
--   * `faq_answers`   — DELETE destroys the corpus.
--   * `answer_feedback` — readable and destroyable; it holds user-submitted text.
--
-- None of this needed the repository to be public. It is a deployment-configuration bug,
-- and it was found by querying the database rather than by reading the migrations — the
-- migrations look correct in isolation, which is exactly why the audit was necessary.
--
-- THE FIX IS TWO INDEPENDENT LAYERS, because either alone is one mistake from failing:
--
--   1. Revoke the grants. Without a grant, PostgREST cannot touch the table at all.
--   2. Enable RLS with no policy, which denies every non-owner role by default.
--
-- Note `enable` WITHOUT `force`, deliberately, and opposite to migration 0002. `force`
-- subjects the table OWNER to the policies too — correct for conversations/messages, which
-- are always reached through `user_scoped` under the `authenticated` role and a matching
-- policy. These five tables are read by the API as the owner with no policy at all, so
-- forcing RLS here would return zero rows and silently break retrieval, rate limiting and
-- feedback. Same keyword, opposite correct answer, depending on who does the reading.

revoke all privileges on faq_answers        from anon, authenticated;
revoke all privileges on faq_chunks         from anon, authenticated;
revoke all privileges on usage_events       from anon, authenticated;
revoke all privileges on answer_feedback    from anon, authenticated;
revoke all privileges on schema_migrations  from anon, authenticated;

alter table faq_answers       enable row level security;
alter table faq_chunks        enable row level security;
alter table usage_events      enable row level security;
alter table answer_feedback   enable row level security;
alter table schema_migrations enable row level security;

-- Stop the next table from inheriting the same exposure. Supabase's default privileges are
-- what granted these in the first place, so a table added later would repeat the bug
-- unless this is changed at the source.
alter default privileges in schema public revoke all on tables from anon, authenticated;
