"use client";

import { ArrowUpRight } from "lucide-react";

import type { Turn } from "@/components/chat/use-chat";

/**
 * Follow-up questions, taken from the corpus rather than invented.
 *
 * Every suggestion here is the *title of a real University of Windsor FAQ article* that
 * retrieval surfaced for this question but the answer did not end up citing. So a
 * suggestion is never a guess about what might exist — it is a question the assistant can
 * definitely answer, because the article is already indexed.
 *
 * That is the whole reason this is worth building. A generated "you might also ask" costs
 * a model call and can propose questions the corpus cannot answer, which teaches people
 * the assistant is unreliable. This costs nothing, cannot hallucinate, and surfaces the
 * genuinely useful thing retrieval already knew and was throwing away: the near misses.
 *
 * Shown only under the newest answer. Suggestions under an older turn would compete with
 * the conversation that has since moved on.
 */

const MAX_SUGGESTIONS = 3;

export function FollowUps({
  turn,
  onAsk,
  disabled,
}: {
  turn: Turn;
  onAsk: (question: string) => void;
  disabled?: boolean;
}) {
  // A refusal means nothing relevant was found, so the near misses are not near anything.
  // Offering them would be inviting the user into a second dead end.
  if (turn.refused || turn.streaming || turn.error) return null;

  const cited = new Set(turn.citations.map((citation) => citation.a_id));
  const suggestions = turn.nearMisses
    .filter((candidate) => !cited.has(candidate.a_id))
    // The same article can surface as more than one chunk; the question is what is shown,
    // so dedupe on that rather than on id.
    .filter(
      (candidate, index, all) =>
        all.findIndex((other) => other.question === candidate.question) ===
        index,
    )
    .slice(0, MAX_SUGGESTIONS);

  if (suggestions.length === 0) return null;

  return (
    <div className="mt-3">
      <h3 className="text-xs font-medium text-muted-foreground">
        Related questions
      </h3>
      <ul className="mt-2 flex flex-col gap-1.5">
        {suggestions.map((suggestion) => (
          <li key={suggestion.a_id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onAsk(suggestion.question)}
              className="group flex w-full items-start gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
            >
              <span className="flex-1">{suggestion.question}</span>
              <ArrowUpRight
                className="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                aria-hidden
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
