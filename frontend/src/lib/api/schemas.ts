/**
 * Runtime contracts for everything the API returns.
 *
 * TypeScript types vanish at build time — they describe what we *believe* the server
 * sends. These schemas check it. The failure they prevent is the quiet one: a backend
 * field gets renamed, the type still compiles, and the UI renders `undefined` somewhere
 * three components deep with no clue where it came from. Parsing at the boundary turns
 * that into one loud error naming the exact field.
 *
 * Every type below is inferred from its schema, so the parser and the type can never
 * disagree.
 */

import { z } from "zod";

/**
 * A URL that is safe to place in an `href`.
 *
 * `z.url()` alone is NOT enough: `javascript:alert(1)` is a syntactically valid URL and
 * passes it. Rendering that as a link is a cross-site scripting vector — the classic one.
 * These values originate from a corpus scraped off a site we do not control, so the scheme
 * has to be checked, not assumed.
 */
const httpUrl = z.url().refine(
  (value) => {
    try {
      const { protocol } = new URL(value);
      return protocol === "http:" || protocol === "https:";
    } catch {
      return false;
    }
  },
  { message: "must be an http(s) URL" },
);

// ---------------------------------------------------------------- health

export const dependencyCheckSchema = z.object({
  status: z.enum(["ok", "error", "not_configured"]),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  latency_ms: z.number().nullable(),
  detail: z.string().nullable(),
});

export const readinessSchema = z.object({
  status: z.enum(["ok", "degraded", "error"]),
  version: z.string(),
  env: z.string(),
  checks: z.record(z.string(), dependencyCheckSchema),
});

export type DependencyCheck = z.infer<typeof dependencyCheckSchema>;
export type Readiness = z.infer<typeof readinessSchema>;

// ---------------------------------------------------------------- models

export const modelInfoSchema = z.object({
  id: z.string(),
  is_default: z.boolean(),
  is_eval_reference: z.boolean(),
});

export const modelCatalogueSchema = z.object({
  provider: z.string(),
  models: z.array(modelInfoSchema),
  eval_reference: z.string(),
});

export type ModelInfo = z.infer<typeof modelInfoSchema>;
export type ModelCatalogue = z.infer<typeof modelCatalogueSchema>;

// ---------------------------------------------------------------- sources

export const sourceSchema = z.object({
  a_id: z.string(),
  question: z.string(),
  url: httpUrl,
  lastmod: z.string().nullable().default(null),
  chunks: z.number().int(),
});

export const sourcesResponseSchema = z.object({
  total: z.number().int(),
  returned: z.number().int(),
  sources: z.array(sourceSchema),
});

export type Source = z.infer<typeof sourceSchema>;
export type SourcesResponse = z.infer<typeof sourcesResponseSchema>;

// ---------------------------------------------------------------- chat stream

export const citationSchema = z.object({
  index: z.number().int(),
  a_id: z.string(),
  question: z.string(),
  // See `httpUrl`: this value becomes an href, so the scheme is checked, not assumed.
  url: httpUrl,
  score: z.number(),
});

export const refusalInfoSchema = z.object({
  reason: z.string(),
  score: z.number(),
  threshold: z.number(),
  stage: z.string(),
});

export const sourcesEventSchema = z.object({
  search_query: z.string(),
  citations: z.array(citationSchema),
  reranker: z.string(),
  rerank_skipped_reason: z.string().nullable(),
  refused: z.boolean(),
  refusal: refusalInfoSchema.nullable(),
  near_misses: z.array(citationSchema),
});

export const tokenEventSchema = z.object({ text: z.string() });

export const doneEventSchema = z.object({
  model: z.string(),
  provider: z.string(),
  conversation_id: z.string().nullable(),
  timings_ms: z.record(z.string(), z.number()),
  candidates: z.object({
    dense: z.number().int(),
    lexical: z.number().int(),
    fused: z.number().int(),
  }),
});

export const errorEventSchema = z.object({
  message: z.string(),
  detail: z.string().optional(),
});

export type Citation = z.infer<typeof citationSchema>;
export type RefusalInfo = z.infer<typeof refusalInfoSchema>;
export type SourcesEvent = z.infer<typeof sourcesEventSchema>;
export type DoneEvent = z.infer<typeof doneEventSchema>;

export type ChatEvent =
  | ({ type: "sources" } & SourcesEvent)
  | { type: "token"; text: string }
  | ({ type: "done" } & DoneEvent)
  | { type: "error"; message: string; detail?: string };

/** Parses one SSE frame. Unknown event names return null rather than throwing, so a new
 *  server-side event type cannot break an older client mid-stream. */
export function parseChatEvent(event: string, data: string): ChatEvent | null {
  const payload: unknown = JSON.parse(data);

  switch (event) {
    case "sources":
      return { type: "sources", ...sourcesEventSchema.parse(payload) };
    case "token":
      return { type: "token", ...tokenEventSchema.parse(payload) };
    case "done":
      return { type: "done", ...doneEventSchema.parse(payload) };
    case "error":
      return { type: "error", ...errorEventSchema.parse(payload) };
    default:
      return null;
  }
}

// ---------------------------------------------------------------- outbound

/** Mirrors the server's own validation. Catching an over-long message here saves a
 *  round trip; the server still enforces it, because a client check is a convenience,
 *  never a control. */
export const chatRequestSchema = z.object({
  message: z.string().min(1).max(2000),
  history: z
    .array(
      z.object({
        role: z.enum(["user", "assistant"]),
        content: z.string().min(1),
      }),
    )
    .max(20),
  conversation_id: z.string().nullable(),
  model: z.string().nullable(),
});

export type ChatRequest = z.infer<typeof chatRequestSchema>;

/**
 * A conversation saved to the signed-in user's account.
 *
 * Validated rather than trusted, like every other response: this data crosses a network
 * boundary and is rendered into the UI, so a shape change upstream should fail loudly here
 * instead of surfacing as an undefined halfway down a component tree.
 */
export const conversationSummarySchema = z.object({
  id: z.string(),
  title: z.string().nullable(),
  question_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const conversationListSchema = z.object({
  conversations: z.array(conversationSummarySchema),
});

export const storedTurnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  trace: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: z.string(),
});

export const conversationDetailSchema = z.object({
  id: z.string(),
  turns: z.array(storedTurnSchema),
});

export type ConversationSummary = z.infer<typeof conversationSummarySchema>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
