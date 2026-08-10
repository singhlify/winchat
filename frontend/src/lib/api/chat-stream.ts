/**
 * The streaming chat client. `EventSource`, the browser's built-in SSE client, only issues
 * GET requests, and a question with conversation history does not belong in a URL.
 */

import { API_BASE_URL, ApiError } from "@/lib/api/client";
import { getTurnstileToken, turnstileConfigured } from "@/lib/turnstile";
import {
  chatRequestSchema,
  parseChatEvent,
  type ChatEvent,
  type ChatRequest,
} from "@/lib/api/schemas";

export interface StreamOptions {
  signal?: AbortSignal;
  accessToken?: string | null;
  conversationId?: string | null;
  model?: string | null;
}

export async function* streamChat(
  message: string,
  history: ChatRequest["history"],
  { signal, accessToken, conversationId, model }: StreamOptions = {},
): AsyncGenerator<ChatEvent> {
  const body = chatRequestSchema.parse({
    message,
    history,
    conversation_id: conversationId ?? null,
    model: model ?? null,
  });

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;

  // Guests prove they are a browser; signed-in visitors already proved it to an identity
  // provider, so asking them again is pure latency. A null token is sent as nothing at all,
  // the API treats that as "feature off" when it holds no Turnstile secret, which is what
  // keeps an unconfigured deployment working exactly as before.
  if (!accessToken && turnstileConfigured) {
    const token = await getTurnstileToken();
    if (token) headers["cf-turnstile-response"] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    throw new ApiError("Could not reach the server.", 0);
  }

  if (!response.ok || !response.body) {
    const retryAfter = Number(response.headers.get("retry-after"));
    let detail = `Request failed (${response.status})`;
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        detail = String((payload as { detail: unknown }).detail);
      }
    } catch {}
    throw new ApiError(
      detail,
      response.status,
      Number.isFinite(retryAfter) ? retryAfter : undefined,
    );
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;

      // Frames are separated by a blank line. TCP does not respect that boundary, so a
      // partial frame stays in the buffer until the rest arrives.
      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        split = buffer.indexOf("\n\n");

        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  } finally {
    // Releasing the lock lets an aborted stream tear down its connection promptly instead
    // of holding it until garbage collection.
    reader.releaseLock();
  }
}

function parseFrame(frame: string): ChatEvent | null {
  let name = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;

  return parseChatEvent(name, dataLines.join("\n"));
}

/** The [n] markers the model actually wrote, in ascending order. */
export function citedIndexes(text: string): number[] {
  const seen = new Set<number>();
  for (const match of text.matchAll(/\[(\d+)\]/g)) seen.add(Number(match[1]));
  return [...seen].sort((a, b) => a - b);
}
