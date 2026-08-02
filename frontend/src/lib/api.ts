/**
 * Typed client for the FastAPI backend.
 *
 * The browser talks to the API directly (not through a Next.js proxy) because Phase 3
 * streams answers over SSE, and an extra hop would buffer the stream. That is why the
 * backend ships CORS from day one.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type CheckStatus = "ok" | "error" | "not_configured";

export interface DependencyCheck {
  status: CheckStatus;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  detail: string | null;
}

export interface Readiness {
  status: "ok" | "degraded" | "error";
  version: string;
  env: string;
  checks: Record<string, DependencyCheck>;
}

/**
 * `/readyz` answers 503 with a full body when a dependency is down — that body is the
 * whole point, so a non-2xx status is parsed rather than thrown away.
 */
export async function fetchReadiness(): Promise<Readiness> {
  const response = await fetch(`${API_BASE_URL}/readyz`, { cache: "no-store" });
  const body: unknown = await response.json();

  if (!body || typeof body !== "object" || !("checks" in body)) {
    throw new Error(`Unexpected response from ${API_BASE_URL}/readyz`);
  }
  return body as Readiness;
}
