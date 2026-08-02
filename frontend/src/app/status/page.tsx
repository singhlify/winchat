"use client";

import { useEffect, useState } from "react";

import {
  API_BASE_URL,
  fetchReadiness,
  type CheckStatus,
  type Readiness,
} from "@/lib/api";

/**
 * Phase 1 status board. It exists to prove one thing end to end: the browser can reach
 * the Python AI core, and the core can reach its providers. The chat UI replaces it in
 * Phase 3.
 *
 * A Client Component on purpose — fetching from the browser exercises the same
 * cross-origin path the SSE chat stream will use later. A Server Component would prove
 * only that the Next.js server can reach the API.
 */
export default function Home() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);
  // Bumping this re-runs the effect; it is how the button asks for a fresh check.
  const [attempt, setAttempt] = useState(0);

  // The effect only *starts* the request. State is set in the async continuation, so
  // nothing renders and sets state in the same pass, and an unmount mid-flight is a no-op.
  useEffect(() => {
    let cancelled = false;

    fetchReadiness().then(
      (result) => {
        if (cancelled) return;
        setReadiness(result);
        setError(null);
        setPending(false);
      },
      () => {
        if (cancelled) return;
        setReadiness(null);
        setError(
          `Could not reach the API at ${API_BASE_URL}. Is the backend running?`,
        );
        setPending(false);
      },
    );

    return () => {
      cancelled = true;
    };
  }, [attempt]);

  function recheck() {
    setPending(true);
    setAttempt((n) => n + 1);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-16">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">WinChat</h1>
          <p className="text-sm text-neutral-500">
            UWindsor FAQ assistant — system status
          </p>
        </div>
        <button
          onClick={recheck}
          disabled={pending}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          {pending ? "Checking…" : "Re-check"}
        </button>
      </header>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      {readiness && (
        <section className="flex flex-col gap-3">
          <p className="flex items-center gap-2 text-sm text-neutral-500">
            <StatusDot status={overallDot(readiness.status)} />
            api v{readiness.version} · env {readiness.env} · {readiness.status}
          </p>

          <ul className="flex flex-col gap-2">
            {Object.entries(readiness.checks).map(([name, check]) => (
              <li
                key={name}
                className="flex items-start justify-between gap-4 rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
              >
                <div className="flex items-start gap-3">
                  <StatusDot status={check.status} className="mt-1.5" />
                  <div>
                    <p className="font-medium">{name}</p>
                    <p className="text-sm text-neutral-500">
                      {[check.provider, check.model].filter(Boolean).join(" · ") || "—"}
                    </p>
                    {check.detail && (
                      <p className="mt-0.5 text-sm text-neutral-500">{check.detail}</p>
                    )}
                  </div>
                </div>
                {check.latency_ms !== null && (
                  <span className="shrink-0 text-sm tabular-nums text-neutral-500">
                    {check.latency_ms} ms
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function overallDot(status: Readiness["status"]): CheckStatus {
  if (status === "ok") return "ok";
  if (status === "error") return "error";
  return "not_configured";
}

const DOT_COLOURS: Record<CheckStatus, string> = {
  ok: "bg-emerald-500",
  error: "bg-red-500",
  not_configured: "bg-amber-400",
};

function StatusDot({
  status,
  className = "",
}: {
  status: CheckStatus;
  className?: string;
}) {
  return (
    <span
      aria-label={status}
      className={`inline-block size-2.5 shrink-0 rounded-full ${DOT_COLOURS[status]} ${className}`}
    />
  );
}
