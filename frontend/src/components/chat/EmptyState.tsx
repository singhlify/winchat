"use client";

import { ArrowUpRight, BookOpen, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

/**
 * The first screen.
 *
 * It answers three questions a first-time visitor actually has — what can I ask, where do
 * the answers come from, and can I trust it — instead of showing a bare input and a logo.
 * The suggestions are real questions from the corpus, so the first thing anyone tries
 * succeeds.
 */

export const SUGGESTIONS = [
  "How do I activate my UWin account?",
  "What is the last day to drop a course?",
  "How much does it cost to replace my UwinCARD?",
  "Where is the Odette School of Business?",
];

export function EmptyState({
  onPick,
  sourceCount,
}: {
  onPick: (question: string) => void;
  sourceCount?: number;
}) {
  return (
    <div className="flex flex-col gap-8 py-6 sm:py-10">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          Ask anything about the University of Windsor.
        </h2>
        <p className="max-w-prose text-[15px] text-muted-foreground text-pretty">
          Every answer is drawn from the university&rsquo;s own published FAQ articles and
          links back to them, so you can check it yourself. If the answer isn&rsquo;t in
          there, it says so instead of guessing.
        </p>
        <p className="max-w-prose text-sm text-muted-foreground text-pretty">
          An independent project, not affiliated with or operated by the University of
          Windsor. For anything official, use{" "}
          <a
            href="https://ask.uwindsor.ca"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            ask.uwindsor.ca
          </a>
          .
        </p>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Try one of these
        </h3>
        <ul className="flex flex-col gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <li key={suggestion}>
              <button
                type="button"
                onClick={() => onPick(suggestion)}
                className="group flex min-h-11 w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-2.5 text-left text-[15px] transition-colors hover:border-primary/40 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                <span>{suggestion}</span>
                <ArrowUpRight
                  className="size-4 shrink-0 text-muted-foreground/50 transition-colors group-hover:text-primary"
                  aria-hidden
                />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <dl className="grid gap-3 sm:grid-cols-3">
        <Fact
          icon={<BookOpen className="size-4" aria-hidden />}
          term={sourceCount ? `${sourceCount} articles` : "Official articles"}
          detail={
            <>
              indexed from{" "}
              <Link href="/sources" className="underline underline-offset-2 hover:text-foreground">
                ask.uwindsor.ca
              </Link>
            </>
          }
        />
        <Fact
          icon={<Sparkles className="size-4" aria-hidden />}
          term="Cited answers"
          detail="every claim links to its source"
        />
        <Fact
          icon={<ShieldCheck className="size-4" aria-hidden />}
          term="Says “I don’t know”"
          detail="rather than inventing an answer"
        />
      </dl>
    </div>
  );
}

function Fact({
  icon,
  term,
  detail,
}: {
  icon: React.ReactNode;
  term: string;
  detail: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border/60 bg-muted/30 p-3">
      <dt className="flex items-center gap-1.5 text-sm font-medium">
        <span className="text-primary">{icon}</span>
        {term}
      </dt>
      <dd className="text-xs text-muted-foreground">{detail}</dd>
    </div>
  );
}
