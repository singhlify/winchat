/**
 * Client for the streaming chat endpoint.
 *
 * `EventSource` (the browser's built-in SSE client) only issues GET requests, and the
 * question does not belong in a URL, so the stream is read from a POST response body and
 * the SSE framing is parsed by hand. It is about twenty lines and removes the alternative
 * of stuffing conversation history into a query string.
 */

import { API_BASE_URL } from "@/lib/api";

export interface Citation {
  index: number;
  a_id: string;
  question: string;
  url: string;
  score: number;
}

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

export interface RefusalInfo {
  reason: string;
  score: number;
  threshold: number;
  stage: string;
}

export type ChatEvent =
  | {
      type: "sources";
      searchQuery: string;
      citations: Citation[];
      reranker: string;
      rerankSkippedReason: string | null;
      refused: boolean;
      refusal: RefusalInfo | null;
      nearMisses: Citation[];
    }
  | { type: "token"; text: string }
  | {
      type: "done";
      model: string;
      provider: string;
      conversationId: string | null;
      timingsMs: Record<string, number>;
      candidates: { dense: number; lexical: number; fused: number };
    }
  | { type: "error"; message: string; detail?: string };

function toChatEvent(event: string, data: string): ChatEvent | null {
  const payload = JSON.parse(data);
  switch (event) {
    case "sources":
      return {
        type: "sources",
        searchQuery: payload.search_query,
        citations: payload.citations,
        reranker: payload.reranker,
        rerankSkippedReason: payload.rerank_skipped_reason,
        refused: Boolean(payload.refused),
        refusal: payload.refusal ?? null,
        nearMisses: payload.near_misses ?? [],
      };
    case "token":
      return { type: "token", text: payload.text };
    case "done":
      return {
        type: "done",
        model: payload.model,
        provider: payload.provider,
        conversationId: payload.conversation_id ?? null,
        timingsMs: payload.timings_ms,
        candidates: payload.candidates,
      };
    case "error":
      return { type: "error", message: payload.message, detail: payload.detail };
    default:
      return null;
  }
}

export interface StreamOptions {
  signal?: AbortSignal;
  accessToken?: string | null;
  conversationId?: string | null;
  model?: string | null;
}

export interface ModelInfo {
  id: string;
  is_default: boolean;
  is_eval_reference: boolean;
}

export interface ModelCatalogue {
  provider: string;
  models: ModelInfo[];
  eval_reference: string;
}

export async function fetchModels(): Promise<ModelCatalogue> {
  const response = await fetch(`${API_BASE_URL}/api/models`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load models (${response.status})`);
  return (await response.json()) as ModelCatalogue;
}

export async function* streamChat(
  message: string,
  history: HistoryTurn[],
  options: StreamOptions = {},
): AsyncGenerator<ChatEvent> {
  const { signal, accessToken, conversationId, model } = options;

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers,
    // For a signed-in conversation the server loads history from the database and ignores
    // what we send — a client that can invent history can invent assistant turns.
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId ?? null,
      model: model ?? null,
    }),
    signal,
  });

  if (response.status === 429) {
    const retryAfter = response.headers.get("retry-after");
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body?.detail ??
        `Rate limit reached${retryAfter ? `. Try again in ${retryAfter}s.` : "."}`,
    );
  }

  if (!response.ok || !response.body) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail.slice(0, 200) || `Request failed (${response.status})`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;

    // SSE frames are separated by a blank line. A partial frame stays in the buffer.
    let split = buffer.indexOf("\n\n");
    while (split !== -1) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      split = buffer.indexOf("\n\n");

      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;

      const parsed = toChatEvent(eventName, dataLines.join("\n"));
      if (parsed) yield parsed;
    }
  }
}

/** The [n] markers the model actually wrote, in the order it first used them. */
export function citedIndexes(text: string): number[] {
  const seen = new Set<number>();
  for (const match of text.matchAll(/\[(\d+)\]/g)) {
    seen.add(Number(match[1]));
  }
  return [...seen].sort((a, b) => a - b);
}
