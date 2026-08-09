import type { Metadata } from "next";
import Link from "next/link";

import { CorpusField } from "@/components/CorpusField";
import { SiteNav } from "@/components/SiteNav";
import { CountUp } from "@/components/CountUp";
import { HeroScroll } from "@/components/HeroScroll";
import { Reveal } from "@/components/Reveal";
import { RetrievalMark } from "@/components/RetrievalMark";
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

const TITLE = "WinChat · University of Windsor FAQ, answered with sources";
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

      <SiteNav />

      <main id="main">
        {/* Left-aligned, not centred. A centred hero over a centred sub-head over a
            centred button row is the layout every template ships, and it also reads worse:
            centred prose gives the eye no fixed left edge to return to on each line.
            Editorial pages left-align their body text for exactly that reason. */}
        <div className="relative isolate overflow-hidden">
          {/* The corpus, behind the words. Masked to fade out before it reaches the text,
              so it reads as ground rather than competing with the headline. */}
          <CorpusField className="text-foreground pointer-events-none absolute -top-8 right-0 hidden w-[46%] [mask-image:linear-gradient(to_bottom_left,black,transparent_72%)] lg:block" />

          <HeroScroll>
            <section className="mx-auto grid max-w-5xl gap-10 px-6 pt-14 pb-20 sm:pt-20 lg:grid-cols-[1.35fr_1fr] lg:items-end lg:gap-16">
              <div>
                <p className="text-gold-foreground flex items-center gap-2.5 text-xs font-medium tracking-[0.14em] uppercase">
                  <span aria-hidden className="bg-gold h-px w-8" />
                  Unofficial · built on the university’s public FAQ
                </p>
                <h1 className="font-display mt-6 text-[2.75rem] leading-[1.04] text-balance sm:text-6xl">
                  University of Windsor questions,{" "}
                  <span className="text-gold-foreground italic">
                    answered with the source attached
                  </span>
                </h1>
                <p className="text-muted-foreground mt-6 max-w-xl text-lg leading-relaxed text-pretty">
                  Admissions, fees, courses, UwinCARD, deadlines. WinChat
                  answers from
                  {sourceCount ? ` ${sourceCount} ` : " "}
                  published FAQ articles and links to every one it used, and
                  tells you when the answer isn’t there.
                </p>

                <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                  <Link
                    href="/app"
                    className="bg-primary text-primary-foreground rounded-full px-7 py-3 text-center text-base font-medium transition-opacity hover:opacity-90"
                  >
                    Ask a question
                  </Link>
                  <Link
                    href="/sources"
                    className="border-input hover:bg-muted rounded-full border px-7 py-3 text-center text-base font-medium transition-colors"
                  >
                    Browse the sources
                  </Link>
                </div>
                <p className="text-muted-foreground mt-4 text-sm">
                  No account needed. Free to use.
                </p>
              </div>

              {/* A worked example rather than an illustration. It shows the behaviour the whole
              page is claiming — a cited answer — so the second column carries evidence
              instead of decoration. */}
              <div className="lg:mb-2">
                <RetrievalMark className="mb-5 w-full max-w-[280px] text-foreground lg:ml-auto" />
                <figure className="border-border bg-muted/40 rounded-2xl border p-5">
                  <figcaption className="text-muted-foreground text-2xs tracking-[0.12em] uppercase">
                    A real answer
                  </figcaption>
                  <p className="mt-3 text-sm font-medium">
                    “How much does it cost to replace a lost UwinCARD?”
                  </p>
                  <p className="mt-3 text-sm leading-relaxed">
                    There is a $25 charge for the production of replacement
                    cards{" "}
                    <span className="bg-gold/25 text-gold-ink text-2xs rounded px-1 py-0.5 font-medium">
                      1
                    </span>
                  </p>
                  <p className="text-muted-foreground border-border text-2xs mt-3 border-t pt-3">
                    <span className="bg-gold/25 text-gold-ink mr-1.5 rounded px-1 py-0.5 font-medium">
                      1
                    </span>
                    Is there a fee for the UwinCARD? · ask.uwindsor.ca
                  </p>
                </figure>
              </div>
            </section>
          </HeroScroll>
        </div>

        <section
          aria-labelledby="trust-heading"
          className="border-t border-border bg-muted/30"
        >
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2
              id="trust-heading"
              className="font-display text-3xl sm:text-4xl"
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
            className="font-display text-3xl sm:text-4xl"
          >
            Measured, not asserted
          </h2>
          <p className="text-muted-foreground mt-3 max-w-2xl text-base leading-relaxed">
            An assistant that sounds confident is easy to build. These numbers
            come from an evaluation suite that runs against the real pipeline on
            every change, and the build fails when they drop.
          </p>

          <dl className="border-border mt-10 grid divide-y divide-border border-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {MEASURED.map((stat, index) => (
              <Reveal
                key={stat.label}
                delay={index * 0.08}
                className="px-2 py-7 sm:px-6"
              >
                <dt className="sr-only">{stat.label}</dt>
                <dd>
                  <CountUp
                    value={stat.value}
                    className="text-gold-foreground font-display block text-5xl leading-none"
                  />
                  <span className="mt-3 block text-sm font-medium">
                    {stat.label}
                  </span>
                  <span className="text-muted-foreground mt-1.5 block text-xs leading-relaxed">
                    {stat.detail}
                  </span>
                </dd>
              </Reveal>
            ))}
          </dl>

          {/* Stated on the page rather than buried in a repo, because a quality claim
              without its caveat is a marketing claim. */}
          <p className="text-muted-foreground border-gold/50 mt-8 max-w-2xl border-l-2 pl-4 text-sm leading-relaxed">
            Honest limits: the graded set is 26 hand-written questions, so these
            are indicative rather than definitive, and one known failure remains
            : the model occasionally computes a date instead of copying it.
            Always confirm anything that affects a deadline or a payment against
            the official page.
          </p>
        </section>

        {/* The one deliberately loud block on the page. Every section above sits on the
            same near-white ground, so a full-bleed band in the brand blue gives the page a
            terminal beat and stops the closing CTA reading as one more row of text. */}
        <section className="bg-band text-band-foreground">
          <div className="mx-auto grid max-w-5xl gap-8 px-6 py-16 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <h2 className="font-display text-3xl sm:text-4xl">
                Ask it something
              </h2>
              <p className="mt-3 max-w-xl text-base leading-relaxed opacity-85">
                “How much does it cost to replace a lost UwinCARD?” · “What is
                the last day to drop a course?” · “How do I activate my UWin
                account?”
              </p>
            </div>
            <Link
              href="/app"
              className="bg-background text-foreground justify-self-start rounded-full px-8 py-3.5 text-base font-medium transition-opacity hover:opacity-90 lg:justify-self-end"
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
            and links back to it. For anything official, such as deadlines, fees
            or admission decisions, use the university’s own pages.
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
