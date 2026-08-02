"use client";

import { useCallback, useRef, useState } from "react";

import { AnswerText } from "@/components/AnswerText";
import { Sources } from "@/components/Sources";
import { streamChat, type Citation, type HistoryTurn } from "@/lib/chat";

interface Turn {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  reranker?: string;
  model?: string;
  error?: string;
  streaming?: boolean;
}

const SUGGESTIONS = [
  "How do I activate my UWin account?",
  "What is the last day to drop a course?",
  "How do I get my T2202 tax form?",
];

export function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;

      // History is captured before the new turns are appended, so the backend sees the
      // conversation as it stood when the question was asked.
      const history: HistoryTurn[] = turns
        .filter((turn) => !turn.error)
        .map((turn) => ({ role: turn.role, content: turn.content }));

      setDraft("");
      setBusy(true);
      setTurns((previous) => [
        ...previous,
        { role: "user", content: trimmed, citations: [] },
        { role: "assistant", content: "", citations: [], streaming: true },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      const updateAnswer = (patch: Partial<Turn>) =>
        setTurns((previous) => {
          const next = [...previous];
          next[next.length - 1] = { ...next[next.length - 1], ...patch };
          return next;
        });

      try {
        for await (const event of streamChat(trimmed, history, controller.signal)) {
          if (event.type === "sources") {
            updateAnswer({ citations: event.citations, reranker: event.reranker });
          } else if (event.type === "token") {
            setTurns((previous) => {
              const next = [...previous];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + event.text };
              return next;
            });
          } else if (event.type === "done") {
            updateAnswer({ model: event.model });
          } else if (event.type === "error") {
            updateAnswer({ error: event.detail ?? event.message });
          }
        }
      } catch (exception) {
        if (!controller.signal.aborted) {
          updateAnswer({
            error:
              exception instanceof Error ? exception.message : "Could not reach the API.",
          });
        }
      } finally {
        updateAnswer({ streaming: false });
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, turns],
  );

  return (
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-5 py-10">
        <header>
          <h1 className="text-xl font-semibold tracking-tight">WinChat</h1>
          <p className="text-sm text-neutral-500">
            Answers grounded in the University of Windsor FAQ, with sources.
          </p>
        </header>

        {turns.length === 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-neutral-500">Try asking:</p>
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => void send(suggestion)}
                className="w-fit rounded-full border border-neutral-200 px-3 py-1.5 text-sm text-neutral-700 transition hover:bg-neutral-100 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-900"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <ol className="flex flex-1 flex-col gap-6">
          {turns.map((turn, position) =>
            turn.role === "user" ? (
              <li key={position} className="self-end">
                <p className="max-w-xl rounded-2xl bg-neutral-100 px-4 py-2.5 dark:bg-neutral-900">
                  {turn.content}
                </p>
              </li>
            ) : (
              <li key={position}>
                {turn.error ? (
                  <p className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
                    {turn.error}
                  </p>
                ) : (
                  <>
                    {turn.content ? (
                      <AnswerText text={turn.content} citations={turn.citations} />
                    ) : (
                      <p className="text-sm text-neutral-500">
                        {turn.citations.length > 0
                          ? "Reading the sources…"
                          : "Searching the FAQ…"}
                      </p>
                    )}
                    {!turn.streaming && (
                      <Sources text={turn.content} citations={turn.citations} />
                    )}
                    {!turn.streaming && turn.model && (
                      <p className="mt-2 text-xs text-neutral-400">
                        {turn.model}
                        {turn.reranker && turn.reranker !== "none"
                          ? ` · reranked by ${turn.reranker}`
                          : " · no reranker"}
                      </p>
                    )}
                  </>
                )}
              </li>
            ),
          )}
        </ol>
      </div>

      <div className="sticky bottom-0 border-t border-neutral-200 bg-white/85 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/85">
        <form
          onSubmit={(submitEvent) => {
            submitEvent.preventDefault();
            void send(draft);
          }}
          className="mx-auto flex w-full max-w-3xl gap-2 px-5 py-4"
        >
          <input
            value={draft}
            onChange={(changeEvent) => setDraft(changeEvent.target.value)}
            placeholder="Ask about UWindsor…"
            maxLength={2000}
            className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-3 py-2 outline-none focus:border-neutral-500 dark:border-neutral-700 dark:focus:border-neutral-500"
          />
          <button
            type="submit"
            disabled={busy || draft.trim().length === 0}
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {busy ? "…" : "Ask"}
          </button>
        </form>
      </div>
    </div>
  );
}
