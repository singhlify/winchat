"use client";

import { ExternalLink, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import type { Source } from "@/lib/api/schemas";

/**
 * Client-side filtering over a server-rendered list.
 *
 * The full list ships in the HTML — that is what makes it crawlable and what makes it work
 * with JavaScript disabled. Filtering then happens in the browser with no round trip,
 * because 556 rows is nothing to search locally and a server call per keystroke would be
 * slower and more fragile.
 *
 * `useDeferredValue` keeps typing responsive: the input updates immediately while the
 * filtered list re-renders at a lower priority.
 */
export function SourcesBrowser({ sources }: { sources: Source[] }) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const filtered = useMemo(() => {
    const needle = deferredQuery.trim().toLowerCase();
    if (!needle) return sources;
    return sources.filter((source) => source.question.toLowerCase().includes(needle));
  }, [deferredQuery, sources]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <label htmlFor="source-filter" className="sr-only">
          Filter sources
        </label>
        <input
          id="source-filter"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter these articles…"
          className="h-11 w-full rounded-xl border border-input bg-background pr-3 pl-9 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/25"
        />
      </div>

      <p aria-live="polite" className="text-sm text-muted-foreground">
        {filtered.length === sources.length
          ? `${sources.length} articles`
          : `${filtered.length} of ${sources.length} articles`}
      </p>

      {filtered.length === 0 ? (
        <p className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
          No article titles match &ldquo;{query}&rdquo;. WinChat searches the full text of
          every article, not just titles, so it may still find an answer — try asking it
          directly.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border/60">
          {filtered.map((source) => (
            <li key={source.a_id}>
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex min-h-11 items-start gap-3 py-2.5 transition-colors hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                <span className="flex-1 text-[15px] leading-snug group-hover:underline">
                  {source.question}
                </span>
                <ExternalLink
                  className="mt-1 size-3.5 shrink-0 text-muted-foreground/50"
                  aria-hidden
                />
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
