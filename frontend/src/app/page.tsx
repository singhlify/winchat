import type { Metadata } from "next";
import Link from "next/link";

import { fetchSources } from "@/lib/api/client";

/**
 * The landing page.
 *
 * The app moved to /app so that / can be a real page: server-rendered prose that a crawler
 * and a language model can actually read. The chat interface is a client shell behind a
 * stream — excellent for using, invisible to indexing — so leaving it at the root meant the
 * most linkable URL on the site said nothing about what this is.
 *
 * It has two audiences and does not pretend otherwise. A student wants to know whether the
 * answers can be trusted; someone evaluating the engineering wants to know whether the
 * quality claims are measured. Both get the same evidence, which is the honest way to serve
 * them at once — every number below is from the eval suite in this repository, and the
 * limitations are stated rather than rounded away.
 */

export const revalidate = 3600;

const TITLE = "WinChat — University of Windsor FAQ, answered with sources";
const DESCRIPTION =
  "Ask about admissions, fees, courses and campus services. Every answer is drawn from the " +
  "university's own published FAQ articles and links back to the source, so you can check " +
  "it yourself. When the answer isn't there, WinChat says so instead of guessing.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
    type: "website",
  },
};

/** Measured on the golden set by the eval suite in this repo. Update both together. */
const MEASURED = [
  {
    value: "100%",
    label: "retrieval recall",
    detail: "the right article was found in every graded case",
  },
  {
    value: "96%",
    label: "answer correctness",
    detail: "judged by a different model family than the one answering",
  },
  {
    value: "556",
    label: "source articles",
    detail: "indexed from ask.uwindsor.ca",
  },
];

const TRUST = [
  {
    title: "Every claim is cited",
    body: "Answers link to the exact University of Windsor article they came from, so you can read the original rather than take a chatbot's word for it.",
  },
  {
    title: "It says “I don’t know”",
    body: "When nothing in the FAQ is close enough to your question, WinChat declines instead of inventing an answer. That threshold was calibrated, not guessed.",
  },
  {
    title: "Nothing is required of you",
    body: "No account, no sign-up wall. Ask a question and get an answer; your chats stay in your browser unless you choose to sign in.",
  },
];

export default async function LandingPage() {
  let sourceCount: number | undefined;
  try {
    sourceCount = (await fetchSources({ limit: 1 })).total;
  } catch {
    // A live count is nice; the page is not about to fail over a number.
  }

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      {/* A skip link is the cheapest accessibility win there is: a keyboard or screen-reader
          user should not have to walk the whole header to reach the page. Visually hidden
          until focused, then unmissable. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <span className="text-sm font-semibold tracking-tight">WinChat</span>
        <nav aria-label="Primary" className="flex items-center gap-5 text-sm">
          <Link
            href="/sources"
            className="text-muted-foreground hover:text-foreground"
          >
            Sources
          </Link>
          <Link
            href="/app"
            className="rounded-full bg-primary px-4 py-1.5 font-medium text-primary-foreground hover:opacity-90"
          >
            Open WinChat
          </Link>
        </nav>
      </header>

      <main id="main">
        <section className="mx-auto max-w-3xl px-6 pb-16 pt-12 text-center sm:pt-20">
          <p className="text-sm font-medium text-muted-foreground">
            Unofficial · built on the university’s public FAQ
          </p>
          <h1 className="mt-4 font-display text-4xl leading-[1.08] text-balance sm:text-5xl">
            University of Windsor questions,{" "}
            <span className="text-gold-foreground italic">
              answered with the source attached
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
            Admissions, fees, courses, UwinCARD, deadlines. WinChat answers from
            {sourceCount ? ` ${sourceCount} ` : " "}
            published FAQ articles and links to every one it used — and tells
            you when the answer isn’t there.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/app"
              className="w-full rounded-full bg-primary px-7 py-3 text-base font-medium text-primary-foreground hover:opacity-90 sm:w-auto"
            >
              Ask a question
            </Link>
            <Link
              href="/sources"
              className="w-full rounded-full border border-border px-7 py-3 text-base font-medium hover:bg-muted sm:w-auto"
            >
              Browse the sources
            </Link>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            No account needed. Free to use.
          </p>
        </section>

        <section
          aria-labelledby="trust-heading"
          className="border-t border-border bg-muted/30"
        >
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2
              id="trust-heading"
              className="text-center font-display text-3xl"
            >
              Why you can check the answers
            </h2>
            <ul className="mt-10 grid gap-6 sm:grid-cols-3">
              {TRUST.map((item) => (
                <li
                  key={item.title}
                  className="rounded-xl border border-border bg-background p-6"
                >
                  <h3 className="text-base font-medium">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {item.body}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section
          aria-labelledby="measured-heading"
          className="mx-auto max-w-5xl px-6 py-16"
        >
          <h2
            id="measured-heading"
            className="text-center font-display text-3xl"
          >
            Measured, not asserted
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-relaxed text-muted-foreground">
            An assistant that sounds confident is easy to build. These numbers
            come from an evaluation suite that runs against the real pipeline on
            every change, and the build fails when they drop.
          </p>

          <dl className="mt-10 grid gap-6 sm:grid-cols-3">
            {MEASURED.map((stat) => (
              <div
                key={stat.label}
                className="rounded-xl border border-border p-6 text-center"
              >
                <dt className="sr-only">{stat.label}</dt>
                <dd>
                  <span className="block text-3xl font-semibold tracking-tight">
                    {stat.value}
                  </span>
                  <span className="mt-1 block text-sm font-medium">
                    {stat.label}
                  </span>
                  <span className="mt-2 block text-xs leading-relaxed text-muted-foreground">
                    {stat.detail}
                  </span>
                </dd>
              </div>
            ))}
          </dl>

          {/* Stated on the page rather than buried in a repo, because a quality claim
              without its caveat is a marketing claim. */}
          <p className="mx-auto mt-8 max-w-2xl text-center text-xs leading-relaxed text-muted-foreground">
            Honest limits: the graded set is 26 hand-written questions, so these
            are indicative rather than definitive, and one known failure remains
            — the model occasionally computes a date instead of copying it.
            Always confirm anything that affects a deadline or a payment against
            the official page.
          </p>
        </section>

        <section className="border-t border-border">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="font-display text-3xl">Ask it something</h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              “How much does it cost to replace a lost UwinCARD?” · “What is the
              last day to drop a course?” · “How do I activate my UWin account?”
            </p>
            <Link
              href="/app"
              className="mt-8 inline-block rounded-full bg-primary px-7 py-3 text-base font-medium text-primary-foreground hover:opacity-90"
            >
              Open WinChat
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-5xl px-6 py-10">
          {/* The disclaimer stays prominent, not demoted to fine print: "Win" reads as
              Windsor, and the university has not endorsed this. */}
          <p className="text-sm leading-relaxed text-muted-foreground">
            <strong className="font-medium text-foreground">
              WinChat is an independent project.
            </strong>{" "}
            It is not affiliated with, endorsed by, or operated by the
            University of Windsor. It reads the university’s public FAQ at{" "}
            <a
              href="https://ask.uwindsor.ca"
              className="underline underline-offset-4 hover:text-foreground"
            >
              ask.uwindsor.ca
            </a>{" "}
            and links back to it. For anything official — deadlines, fees,
            admission decisions — use the university’s own pages.
          </p>

          <nav
            aria-label="Footer"
            className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm"
          >
            <Link
              href="/app"
              className="text-muted-foreground hover:text-foreground"
            >
              Open WinChat
            </Link>
            <Link
              href="/sources"
              className="text-muted-foreground hover:text-foreground"
            >
              All {sourceCount ?? ""} sources
            </Link>
            <Link
              href="/status"
              className="text-muted-foreground hover:text-foreground"
            >
              Status
            </Link>
            <a
              href="https://ask.uwindsor.ca"
              className="text-muted-foreground hover:text-foreground"
            >
              Official UWindsor FAQ
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
