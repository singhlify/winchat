# Known issues

Defects and limitations that are true today. Each has a reproduction. Eval cases listed here
stay in the suite and stay failing; the deterministic gate names them explicitly, so a third
failure breaks the build and a fix here also breaks it until this file and
`KNOWN_DETERMINISTIC_FAILURES` are updated together.

Some of them fail only some of the time, because temperature 0.0 makes decoding greedy
without making a hosted provider reproducible. Those cases declare a pass-rate band and are
run several times, and the gate checks the measured rate against the band. Scoring them once
would report the sample rather than the defect, which is exactly how issue 1 briefly appeared
to be fixed. Never close one of these on a single run.

## 1. The corpus contradicts itself on graduate document deadlines

Two published articles give different dates for the same rule.

- `a_id 594`: "If you are a graduate student you have up until one (1) month prior to the end
  of your first term (December 1 for Fall, **April 1 for Winter**, August 1 for Spring)"
- `a_id 604`: "Graduate Students: You have up until one (1) month prior to the end of your
  first term (November 1 for Fall, **March 1 for Winter**, July 1 for Spring)"

Retrieval returns both, 594 at rank 1 and 604 at rank 2. The model answers "March 1" and
cites 604, which is a faithful reading of a source it was given. Nothing in the pipeline
detects that two retrieved articles disagree, and nothing establishes which is current.

Reproduction:

```bash
cd backend
uv run python -m winchat_api.ask "I'm a graduate student starting in winter. What is my deadline for submitting official documents?"
```

Eval case `g004` asserts "April 1" and fails.

This is not a hallucination and not a date computed by the model. Earlier versions of the
README described it that way; that description was wrong.

Fixing it needs a policy for conflicting sources: prefer the most recently modified article,
surface the disagreement to the reader, or curate the corpus. None of these is implemented.

## 2. Procedural answers drop named UI elements

Asked how to look up classes, the model synthesises across several articles and gives a
correct but generic answer. Article 49 step 5 says "click on the **Manage Classes** tile",
and the answer omits that name, offering "Class Search and Enroll tab" instead.

Retrieval is not the problem: article 49 is returned at rank 4.

Reproduction:

```bash
cd backend
uv run python -m winchat_api.ask "How do I look up which classes are being offered?"
```

Eval case `g005` asserts "Manage Classes" and fails.

Someone following the answer step by step cannot find the element they are told to click.
A prompt rule requiring exact UI element names to be preserved would likely fix it, and would
change every generated answer, so it needs its own measurement pass.

## 3. Single corpus, single institution

The system indexes one source, `ask.uwindsor.ca`, 556 articles. Retrieval, prompts, the
refusal threshold and the eval set are all tuned to it. The threshold in particular is
specific to this corpus and this embedding model and does not transfer.

## 4. No multi-hop support

Every case in the golden set is answerable from a single article. A question needing two
articles combined is not handled, and the suite does not currently contain a case that
proves the failure.

## 5. Superseded articles are not detected

Related to issue 1 but broader. The corpus has no notion of an article replacing another.
Ingestion reconciles deletions against the sitemap, so an unpublished article is removed,
but two live articles covering the same ground are both indexed and both retrievable.

## 6. The weekly refresh has never caught a real change

`.github/workflows/refresh.yml` runs weekly and was verified end to end against a live
scrape, but the corpus has not changed since it was built. The path where an article's
content actually changes, gets re-embedded and replaces the old vectors has been exercised
only by the initial ingest, not by a scheduled run.

## 7. Judge-tier metrics have no interval below the aggregate

`evals/report.py` reports Wilson intervals per category, but the judge tier scores far fewer
cases than the deterministic tier, so several per-category judge intervals span most of the
range. They are shown rather than hidden, but they support very little.
