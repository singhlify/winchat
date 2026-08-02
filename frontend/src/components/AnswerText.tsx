import type { Citation } from "@/lib/chat";

/**
 * Renders an answer with its [n] markers turned into clickable citations.
 *
 * The whole point of a grounded assistant is that a claim can be checked in one click.
 * A citation the user cannot follow is decoration; this is the feature.
 */
export function AnswerText({
  text,
  citations,
}: {
  text: string;
  citations: Citation[];
}) {
  const byIndex = new Map(citations.map((citation) => [citation.index, citation]));
  // Capturing split: odd positions are the captured numbers, even ones the prose.
  const parts = text.split(/\[(\d+)\]/g);

  return (
    <div className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, position) => {
        if (position % 2 === 0) return <span key={position}>{part}</span>;

        const citation = byIndex.get(Number(part));
        if (!citation) return <span key={position}>[{part}]</span>;

        return (
          <a
            key={position}
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            title={citation.question}
            className="mx-0.5 inline-flex min-w-5 items-center justify-center rounded border border-sky-300 bg-sky-50 px-1 align-baseline text-xs font-medium text-sky-800 no-underline transition hover:bg-sky-100 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200 dark:hover:bg-sky-900"
          >
            {part}
          </a>
        );
      })}
    </div>
  );
}
