"use client";

import { ArrowUpRight } from "lucide-react";

/**
 * The first screen: what can be asked, where the answers come from, and a link to the full
 * source list.
 */

export const SUGGESTIONS = [
  "How do I activate my UWin account?",
  "What is the last day to drop a course?",
  "How much does it cost to replace my UwinCARD?",
  "Where is the Odette School of Business?",
];

export function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="flex flex-col gap-8 py-6 sm:py-10">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          Ask anything about the University of Windsor.
        </h2>
        <p className="max-w-prose text-[15px] text-muted-foreground text-pretty">
          Answers come from the university&rsquo;s published FAQ articles, with
          a link to every source used.
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
    </div>
  );
}
