"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { fetchReadiness } from "@/lib/api/client";
import type { DependencyCheck } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

/**
 * Dependency status.
 *
 * A Client Component on purpose: fetching from the browser exercises the same cross-origin
 * path the chat stream uses, so a green board here means the browser really can reach the
 * API — not merely that the Next.js server can.
 */
export default function StatusPage() {
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["readiness"],
    queryFn: ({ signal }) => fetchReadiness({ signal }),
    staleTime: 0,
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10 sm:px-6">
      <nav className="text-sm">
        <Link
          href="/"
          className="text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          ← Back to WinChat
        </Link>
      </nav>

      <main id="main" className="flex flex-col gap-4">
        <header className="flex items-baseline justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">System status</h1>
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
            {error instanceof Error ? error.message : "Could not reach the API."}
          </p>
        )}

        {data && (
          <>
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Dot
                status={
                  data.status === "ok" ? "ok" : data.status === "error" ? "error" : "not_configured"
                }
              />
              api v{data.version} · {data.env} · {data.status}
            </p>

            <ul className="flex flex-col gap-2">
              {Object.entries(data.checks).map(([name, check]) => (
                <li
                  key={name}
                  className="flex items-start justify-between gap-4 rounded-xl border border-border px-4 py-3"
                >
                  <div className="flex items-start gap-3">
                    <Dot status={check.status} className="mt-1.5" />
                    <div>
                      <p className="font-medium">{name}</p>
                      <p className="text-sm text-muted-foreground">
                        {[check.provider, check.model].filter(Boolean).join(" · ") || "—"}
                      </p>
                      {check.detail && (
                        <p className="mt-0.5 text-sm text-muted-foreground">{check.detail}</p>
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
    </div>
  );
}

const DOT_COLOURS: Record<DependencyCheck["status"], string> = {
  ok: "bg-emerald-500",
  error: "bg-destructive",
  not_configured: "bg-amber-400",
};

function Dot({ status, className }: { status: DependencyCheck["status"]; className?: string }) {
  return (
    <span
      role="img"
      aria-label={status}
      className={cn("inline-block size-2.5 shrink-0 rounded-full", DOT_COLOURS[status], className)}
    />
  );
}
