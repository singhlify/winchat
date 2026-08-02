"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import { useState } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { citedIndexes } from "@/lib/api/chat-stream";
import type { Citation } from "@/lib/api/schemas";

/**
 * The sources behind an answer — every one of them, each a link to the university's own
 * published article.
 *
 * Two groups, and the split is the honest part. **Cited** are the articles the answer
 * actually drew on. **Also searched** are the rest of what retrieval surfaced and the
 * model did not use. Listing all of them as if they backed the answer would manufacture
 * corroboration; hiding the unused ones would hide the assistant's reasoning. So: both,
 * labelled, with the used ones first.
 *
 * The domain is shown on every link. A citation the reader cannot trace to a real,
 * checkable page is decoration.
 */
export function SourcePanel({
  answer,
  citations,
  compact = false,
}: {
  answer: string;
  citations: Citation[];
  compact?: boolean;
}) {
  const [showOthers, setShowOthers] = useState(false);

  if (citations.length === 0) return null;

  const cited = new Set(citedIndexes(answer));
  const used = citations.filter((citation) => cited.has(citation.index));
  const unused = citations.filter((citation) => !cited.has(citation.index));

  return (
    <section
      aria-label="Sources for this answer"
      className={cn("mt-4 border-t border-border/60 pt-3", compact && "mt-3")}
    >
      {used.length > 0 && (
        <>
          <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {used.length === 1 ? "Source" : "Sources"}
          </h3>
          <ul className="flex flex-col gap-1">
            {used.map((citation) => (
              <SourceLink key={citation.a_id} citation={citation} showIndex />
            ))}
          </ul>
        </>
      )}

      {unused.length > 0 && (
        <Collapsible open={showOthers} onOpenChange={setShowOthers} className="mt-2">
          <CollapsibleTrigger className="group flex min-h-9 items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
            <ChevronDown
              className={cn(
                "size-3.5 transition-transform motion-reduce:transition-none",
                showOthers && "rotate-180",
              )}
              aria-hidden
            />
            Also searched {unused.length} more {unused.length === 1 ? "article" : "articles"}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-1 flex flex-col gap-1">
              {unused.map((citation) => (
                <SourceLink key={citation.a_id} citation={citation} muted />
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      )}
    </section>
  );
}

export function SourceLink({
  citation,
  showIndex = false,
  muted = false,
}: {
  citation: Citation;
  showIndex?: boolean;
  muted?: boolean;
}) {
  return (
    <li>
      <a
        href={citation.url}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "group flex min-h-9 items-start gap-2 rounded-md px-1.5 py-1 text-sm transition-colors hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          muted && "text-muted-foreground",
        )}
      >
        {showIndex && (
          <span
            aria-hidden
            className="mt-0.5 inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded-[4px] border border-primary/25 bg-primary/10 px-1 text-[10px] font-semibold text-primary tabular-nums"
          >
            {citation.index}
          </span>
        )}
        <span className="flex-1 leading-snug group-hover:underline">{citation.question}</span>
        <ExternalLink
          className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/60"
          aria-label="opens on ask.uwindsor.ca"
        />
      </a>
    </li>
  );
}
