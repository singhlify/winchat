import { citedIndexes, type Citation } from "@/lib/chat";

/**
 * The sources list.
 *
 * Only what the model actually cited is listed. Retrieval hands over six passages and a
 * good answer often uses one; listing all six would imply six sources backed the answer,
 * which is the same false-corroboration problem the citation numbering avoids. The rest
 * stay available behind a disclosure, because "what else did it look at" is a fair
 * question to ask of a retrieval system.
 */
export function Sources({ text, citations }: { text: string; citations: Citation[] }) {
  if (citations.length === 0) return null;

  const cited = new Set(citedIndexes(text));
  const used = citations.filter((citation) => cited.has(citation.index));
  const unused = citations.filter((citation) => !cited.has(citation.index));

  return (
    <div className="mt-3 flex flex-col gap-1.5 border-t border-neutral-200 pt-3 dark:border-neutral-800">
      {used.length > 0 && (
        <ul className="flex flex-col gap-1">
          {used.map((citation) => (
            <li key={citation.index} className="text-sm">
              <a
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-neutral-600 underline decoration-neutral-300 underline-offset-2 hover:text-neutral-900 dark:text-neutral-400 dark:decoration-neutral-700 dark:hover:text-neutral-100"
              >
                <span className="tabular-nums">[{citation.index}]</span> {citation.question}
              </a>
            </li>
          ))}
        </ul>
      )}

      {unused.length > 0 && (
        <details className="text-sm text-neutral-500">
          <summary className="cursor-pointer select-none hover:text-neutral-700 dark:hover:text-neutral-300">
            {unused.length} other passage{unused.length === 1 ? "" : "s"} retrieved but not
            cited
          </summary>
          <ul className="mt-1 flex flex-col gap-1 pl-4">
            {unused.map((citation) => (
              <li key={citation.index}>
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-neutral-300 underline-offset-2 dark:decoration-neutral-700"
                >
                  {citation.question}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
