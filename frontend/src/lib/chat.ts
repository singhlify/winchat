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

export type ChatEvent =
  | {
      type: "sources";
      searchQuery: string;
      citations: Citation[];
      reranker: string;
      rerankSkippedReason: string | null;
    }
  | { type: "token"; text: string }
  | {
      type: "done";
      model: string;
      provider: string;
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
      };
    case "token":
      return { type: "token", text: payload.text };
    case "done":
      return {
        type: "done",
        model: payload.model,
        provider: payload.provider,
        timingsMs: payload.timings_ms,
        candidates: payload.candidates,
      };
    case "error":
      return { type: "error", message: payload.message, detail: payload.detail };
    default:
      return null;
  }
}

export async function* streamChat(
  message: string,
  history: HistoryTurn[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

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
