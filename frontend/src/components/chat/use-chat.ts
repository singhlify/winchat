"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { streamChat } from "@/lib/api/chat-stream";
import type { Citation, RefusalInfo } from "@/lib/api/schemas";

export interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  nearMisses: Citation[];
  refused: boolean;
  refusal: RefusalInfo | null;
  reranker: string | null;
  model: string | null;
  searchQuery: string | null;
  timings: Record<string, number> | null;
  error: string | null;
  retryAfterSeconds: number | null;
  streaming: boolean;
  feedback: "up" | "down" | null;
}

function emptyAssistantTurn(id: string): Turn {
  return {
    id,
    role: "assistant",
    content: "",
    citations: [],
    nearMisses: [],
    refused: false,
    refusal: null,
    reranker: null,
    model: null,
    searchQuery: null,
    timings: null,
    error: null,
    retryAfterSeconds: null,
    streaming: true,
    feedback: null,
  };
}

let counter = 0;
const nextId = () => `t${Date.now().toString(36)}-${counter++}`;

export interface UseChatOptions {
  accessToken: string | null;
  model: string | null;
  /** Turns restored from storage when opening an existing conversation. */
  initialTurns?: Turn[];
  /** `question` is resolved here rather than by the caller: this hook already owns the
   *  turn list, and having the view re-derive it would mean reading state during render. */
  onFeedback?: (turn: Turn, vote: "up" | "down", question: string) => void;
}

/**
 * All conversation state and control in one hook, so the view components stay declarative.
 *
 * Deliberately not TanStack Query: a mutation returns one value, and this returns a stream
 * of partial values. Forcing it into a mutation would mean re-implementing streaming
 * inside a cache that has nothing to cache. Query handles the request/response endpoints
 * (models, sources); the stream is its own thing.
 */
export function useChat({ accessToken, model, initialTurns, onFeedback }: UseChatOptions) {
  const [turns, setTurns] = useState<Turn[]>(initialTurns ?? []);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const conversationRef = useRef<string | null>(null);

  const patchLast = useCallback((patch: Partial<Turn>) => {
    setTurns((previous) => {
      if (previous.length === 0) return previous;
      const next = [...previous];
      next[next.length - 1] = { ...next[next.length - 1], ...patch };
      return next;
    });
  }, []);

  const run = useCallback(
    async (question: string, priorTurns: Turn[]) => {
      const history = priorTurns
        .filter((turn) => !turn.error && turn.content.trim().length > 0)
        .slice(-12)
        .map((turn) => ({ role: turn.role, content: turn.content }));

      setBusy(true);
      setTurns([
        ...priorTurns,
        {
          ...emptyAssistantTurn(nextId()),
          role: "user",
          content: question,
          streaming: false,
        },
        emptyAssistantTurn(nextId()),
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of streamChat(question, history, {
          signal: controller.signal,
          accessToken,
          conversationId: conversationRef.current,
          model,
        })) {
          if (event.type === "sources") {
            patchLast({
              citations: event.citations,
              nearMisses: event.near_misses,
              refused: event.refused,
              refusal: event.refusal,
              reranker: event.reranker,
              searchQuery: event.search_query,
            });
          } else if (event.type === "token") {
            setTurns((previous) => {
              const next = [...previous];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + event.text };
              return next;
            });
          } else if (event.type === "done") {
            if (event.conversation_id) conversationRef.current = event.conversation_id;
            patchLast({ model: event.model, timings: event.timings_ms });
          } else if (event.type === "error") {
            patchLast({ error: event.detail ?? event.message });
          }
        }
      } catch (exception) {
        // An abort is the user pressing Stop — whatever streamed so far is kept, because
        // a partial answer they chose to interrupt is not an error.
        if (!controller.signal.aborted) {
          patchLast({
            error:
              exception instanceof ApiError
                ? exception.message
                : "Something went wrong. Please try again.",
            retryAfterSeconds:
              exception instanceof ApiError ? (exception.retryAfterSeconds ?? null) : null,
          });
        }
      } finally {
        patchLast({ streaming: false });
        setBusy(false);
        abortRef.current = null;
      }
    },
    [accessToken, model, patchLast],
  );

  const send = useCallback(
    (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      void run(trimmed, turns);
    },
    [busy, run, turns],
  );

  /** Stop generating. The partial answer stays on screen. */
  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  /** Regenerate the last answer from the same question. */
  const retry = useCallback(() => {
    if (busy) return;
    const lastUser = [...turns].reverse().find((turn) => turn.role === "user");
    if (!lastUser) return;
    const index = turns.lastIndexOf(lastUser);
    void run(lastUser.content, turns.slice(0, index));
  }, [busy, run, turns]);

  /** Remove the last question and its answer, putting the text back for editing. */
  const undo = useCallback((): string | null => {
    if (busy) return null;
    const lastUser = [...turns].reverse().find((turn) => turn.role === "user");
    if (!lastUser) return null;
    setTurns(turns.slice(0, turns.lastIndexOf(lastUser)));
    return lastUser.content;
  }, [busy, turns]);

  /** Start over. A new conversation id is minted on the next answer. */
  const clear = useCallback(() => {
    abortRef.current?.abort();
    conversationRef.current = null;
    setTurns([]);
  }, []);

  const rate = useCallback(
    (id: string, vote: "up" | "down") => {
      setTurns((previous) =>
        previous.map((turn) =>
          turn.id === id
            ? { ...turn, feedback: turn.feedback === vote ? null : vote }
            : turn,
        ),
      );
      const index = turns.findIndex((candidate) => candidate.id === id);
      const turn = index === -1 ? undefined : turns[index];
      // Only report a vote being set, never one being cleared by pressing it again.
      if (turn && turn.feedback !== vote) {
        onFeedback?.(turn, vote, index > 0 ? turns[index - 1].content : "");
      }
    },
    [onFeedback, turns],
  );

  return { turns, busy, send, stop, retry, undo, clear, rate };
}
