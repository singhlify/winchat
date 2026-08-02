import type { Citation, RefusalInfo } from "@/lib/chat";

/**
 * The "I don't know" state.
 *
 * Shown as a distinct, calm state rather than an error. A refusal is the system working
 * correctly, and presenting it in red would train users to read correct behaviour as
 * breakage. The near-misses are included because a bare "no results" is indistinguishable
 * from a broken search — showing what it nearly matched proves it looked.
 */
export function Refusal({
  text,
  refusal,
  nearMisses,
}: {
  text: string;
  refusal: RefusalInfo | null;
  nearMisses: Citation[];
}) {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-900/70 dark:bg-amber-950/40">
      <p className="text-sm text-amber-900 dark:text-amber-100">{text}</p>

      {nearMisses.length > 0 && (
        <details className="mt-2 text-sm text-amber-800/80 dark:text-amber-200/70">
          <summary className="cursor-pointer select-none">Closest articles found</summary>
          <ul className="mt-1 flex flex-col gap-1 pl-4">
            {nearMisses.map((citation) => (
              <li key={citation.a_id}>
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-2"
                >
                  {citation.question}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}

      {refusal && (
        <p className="mt-2 font-mono text-xs text-amber-700/70 dark:text-amber-300/50">
          {refusal.stage} similarity {refusal.score} &lt; {refusal.threshold}
        </p>
      )}
    </div>
  );
}
