/**
 * The HTTP boundary. Everything crossing it is validated.
 *
 * One `request` helper so timeout, error shape and schema parsing are decided once
 * rather than re-improvised per call site.
 */

import type { z } from "zod";

import {
  modelCatalogueSchema,
  readinessSchema,
  sourcesResponseSchema,
  type ModelCatalogue,
  type Readiness,
  type SourcesResponse,
} from "@/lib/api/schemas";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;

interface RequestOptions {
  signal?: AbortSignal;
  accessToken?: string | null;
  timeoutMs?: number;
}

/**
 * A hung request is worse than a failed one — it shows a spinner forever. Every call
 * gets a deadline, combined with any caller-supplied abort signal.
 */
async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  { signal, accessToken, timeoutMs = DEFAULT_TIMEOUT_MS }: RequestOptions = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  const headers: Record<string, string> = {};
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers,
      signal: combined,
      cache: "no-store",
    });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    throw new ApiError("Could not reach the server.", 0);
  }

  if (!response.ok) {
    throw new ApiError(
      await readErrorDetail(response),
      response.status,
      readRetryAfter(response),
    );
  }

  // Parsed, not cast. A shape change becomes one clear error here instead of `undefined`
  // surfacing somewhere unrelated later.
  return schema.parse(await response.json());
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
  } catch {
    // A non-JSON error body is not itself an error worth reporting.
  }
  return `Request failed (${response.status})`;
}

function readRetryAfter(response: Response): number | undefined {
  const header = response.headers.get("retry-after");
  if (!header) return undefined;
  const seconds = Number(header);
  return Number.isFinite(seconds) ? seconds : undefined;
}

export const fetchReadiness = (options?: RequestOptions): Promise<Readiness> =>
  request("/readyz", readinessSchema, options);

export const fetchModels = (options?: RequestOptions): Promise<ModelCatalogue> =>
  request("/api/models", modelCatalogueSchema, options);

export function fetchSources(
  { query, limit = 1000 }: { query?: string; limit?: number } = {},
  options?: RequestOptions,
): Promise<SourcesResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query) params.set("q", query);
  return request(`/api/sources?${params}`, sourcesResponseSchema, {
    timeoutMs: 30_000,
    ...options,
  });
}

export interface FeedbackPayload {
  vote: "up" | "down";
  question: string;
  answer: string;
  conversation_id?: string | null;
  model?: string | null;
  trace?: Record<string, unknown> | null;
}

/**
 * Records a thumbs up/down. Fire-and-forget by design: the user has already read their
 * answer, and a failed vote has no recovery worth interrupting them for.
 */
export async function submitFeedback(
  payload: FeedbackPayload,
  { accessToken }: { accessToken?: string | null } = {},
): Promise<void> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;

  try {
    await fetch(`${API_BASE_URL}/api/feedback`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(8000),
      keepalive: true,
    });
  } catch {
    // Intentionally swallowed — see the note above.
  }
}
