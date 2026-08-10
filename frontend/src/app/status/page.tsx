"use client";

import { useQuery } from "@tanstack/react-query";

import { Credit } from "@/components/Credit";
import { SiteNav } from "@/components/SiteNav";

import { Button } from "@/components/ui/button";
import { fetchReadiness } from "@/lib/api/client";
import type { DependencyCheck } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

/**
 * Dependency status. A Client Component so the fetch uses the same cross-origin path as the
 * chat stream, which is what the visitor's browser actually has to reach.
 */
/**
 * Plain-language description of each dependency, since the raw provider strings do not say
 * what a failure means for answers.
 */
const EXPLAINS: Record<string, { title: string; means: string }> = {
  config: {
    title: "Configuration",
    means: "Deployment settings are correct for a live site.",
  },
  llm: {
    title: "Answer generation",
    means:
      "The language model responds to a full-size request, not just a token.",
  },
  embeddings: {
    title: "Question understanding",
    means: "Questions can be turned into vectors and matched against articles.",
  },
  reranker: {
    title: "Answer ranking",
    means:
      "The best article is picked from the candidates. Off, answers get noticeably worse.",
  },
  database: {
    title: "Article index",
    means: "The indexed FAQ articles are reachable.",
  },
};

export default function StatusPage() {
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["readiness"],
    queryFn: ({ signal }) => fetchReadiness({ signal }),
    staleTime: 0,
    refetchInterval: 30_000,
  });

  return (
    <>
      <SiteNav />
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10 sm:px-6">
        <main id="main" className="flex flex-col gap-4">
          <header className="flex flex-col items-center gap-3 text-center sm:flex-row sm:items-baseline sm:justify-between sm:gap-4 sm:text-left">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                System status
              </h1>
              <p className="text-sm text-muted-foreground">
                Each dependency answers a real call, not a ping.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refetch()}
              disabled={isFetching}
            >
              {isFetching ? "Checking…" : "Re-check"}
            </Button>
          </header>

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"
            >
              {error instanceof Error
                ? error.message
                : "Could not reach the API."}
            </p>
          )}

          {data && (
            <>
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Dot
                  status={
                    data.status === "ok"
                      ? "ok"
                      : data.status === "error"
                        ? "error"
                        : "not_configured"
                  }
                />
                {data.status === "ok"
                  ? "Everything is working."
                  : data.status === "degraded"
                    ? "Working, with something not configured."
                    : "Something is wrong. Answers may fail."}
              </p>

              <ul className="flex flex-col gap-2">
                {Object.entries(data.checks).map(([name, check]) => (
                  <li
                    key={name}
                    className="border-border flex flex-col items-center gap-3 rounded-xl border px-4 py-3 text-center sm:flex-row sm:items-start sm:justify-between sm:gap-4 sm:text-left"
                  >
                    <div className="flex flex-col items-center gap-2 sm:flex-row sm:items-start sm:gap-3">
                      <Dot status={check.status} className="mt-1.5" />
                      <div>
                        <p className="font-medium">
                          {EXPLAINS[name]?.title ?? name}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {EXPLAINS[name]?.means}
                        </p>
                        {(check.detail || check.model) && (
                          <p className="text-muted-foreground/70 mt-1 text-xs">
                            {[check.detail, check.model]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        )}
                      </div>
                    </div>
                    {check.latency_ms !== null && (
                      <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                        {check.latency_ms} ms
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </main>

        <footer className="border-border mt-12 border-t pt-6 pb-10 text-center sm:text-left">
          <Credit className="text-muted-foreground text-sm" />
        </footer>
      </div>
    </>
  );
}

const DOT_COLOURS: Record<DependencyCheck["status"], string> = {
  ok: "bg-emerald-500",
  error: "bg-destructive",
  not_configured: "bg-amber-400",
};

function Dot({
  status,
  className,
}: {
  status: DependencyCheck["status"];
  className?: string;
}) {
  return (
    <span
      role="img"
      aria-label={status}
      className={cn(
        "inline-block size-2.5 shrink-0 rounded-full",
        DOT_COLOURS[status],
        className,
      )}
    />
  );
}
