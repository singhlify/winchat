"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AssistantMessage, UserMessage } from "@/components/chat/Message";
import { Composer, type ComposerHandle } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { useChat, type Turn } from "@/components/chat/use-chat";
import { submitFeedback } from "@/lib/api/client";
import { useStickToBottom } from "@/components/chat/use-stick-to-bottom";
import { Header } from "@/components/Header";

export function Chat({ sourceCount }: { sourceCount?: number }) {
  const [draft, setDraft] = useState("");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const composerRef = useRef<ComposerHandle>(null);

  const onFeedback = useCallback(
    (turn: Turn, vote: "up" | "down", question: string) => {
      void submitFeedback(
        {
          vote,
          question,
          answer: turn.content,
          model: turn.model,
          trace: {
            citations: turn.citations,
            refused: turn.refused,
            refusal: turn.refusal,
            reranker: turn.reranker,
            search_query: turn.searchQuery,
            timings_ms: turn.timings,
          },
        },
        { accessToken },
      );
    },
    [accessToken],
  );

  const { turns, busy, send, stop, retry, undo, clear, rate } = useChat({
    accessToken,
    model,
    onFeedback,
  });

  const { scrollRef, bottomRef, isPinned, scrollToBottom } = useStickToBottom([turns]);

  const handleSession = useCallback((token: string | null) => setAccessToken(token), []);

  const submit = useCallback(() => {
    send(draft);
    setDraft("");
  }, [draft, send]);

  const handleUndo = useCallback(() => {
    const restored = undo();
    if (restored !== null) composerRef.current?.setValue(restored);
  }, [undo]);

  const ask = useCallback(
    (question: string) => {
      send(question);
      setDraft("");
    },
    [send],
  );

  // A global Escape stops generation from anywhere, including while the composer is
  // unfocused — the single most likely thing someone wants when an answer goes wrong.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && busy) stop();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, stop]);

  const lastTurn = turns.at(-1);
  const status = busy
    ? lastTurn?.citations.length
      ? "Reading the sources"
      : "Searching the FAQ"
    : lastTurn?.role === "assistant" && lastTurn.content
      ? "Answer ready"
      : "";

  return (
    // 100dvh, not 100vh: on mobile the browser chrome collapses and `vh` leaves the
    // composer stranded under the viewport edge.
    <div className="flex h-[100dvh] flex-col bg-background">
      <Header
        onSession={handleSession}
        model={model}
        onModelChange={setModel}
        onNewChat={turns.length > 0 ? clear : undefined}
      />

      {/* Two live regions, both mounted for the lifetime of the page and never hidden.
          A region that is conditionally rendered — or hidden when idle — is not reliably
          announced by screen readers, so these exist from first paint and only their text
          changes.

          They are deliberately split by politeness, because a progress update and a
          failure are not the same urgency:
            role="status"  — polite; stage changes ("Searching the FAQ")
            role="alert"   — assertive; failures the user must notice

          Neither carries the token stream. Announcing every token would make the page
          unusable with a screen reader; the finished answer is read by navigating to it. */}
      <p role="status" aria-atomic="true" className="sr-only">
        {status}
      </p>
      <p role="alert" aria-atomic="true" className="sr-only">
        {lastTurn?.error ?? ""}
      </p>

      <main
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain scroll-smooth motion-reduce:scroll-auto"
      >
        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
          {turns.length === 0 ? (
            <EmptyState onPick={ask} sourceCount={sourceCount} />
          ) : (
            // role="log" marks a sequential, append-only region — the right semantic
            // for a transcript, and distinct from the status and alert regions above.
            <ol role="log" className="flex flex-col gap-6 py-6">
              {turns.map((turn, index) =>
                turn.role === "user" ? (
                  <UserMessage key={turn.id} content={turn.content} />
                ) : (
                  <AssistantMessage
                    key={turn.id}
                    turn={turn}
                    isLast={index === turns.length - 1}
                    onRetry={retry}
                    onRate={(vote) => rate(turn.id, vote)}
                  />
                ),
              )}
            </ol>
          )}
          <div ref={bottomRef} className="h-2" />
        </div>
      </main>

      {!isPinned && turns.length > 0 && (
        <div className="pointer-events-none relative">
          <button
            type="button"
            onClick={scrollToBottom}
            className="pointer-events-auto absolute -top-12 left-1/2 z-10 -translate-x-1/2 rounded-full border border-border bg-background px-3 py-1.5 text-xs shadow-md transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            Jump to latest
          </button>
        </div>
      )}

      {/* pb-[env(safe-area-inset-bottom)] keeps the composer clear of the iOS home bar. */}
      <div className="border-t border-border/60 bg-background/85 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6">
          <Composer
            ref={composerRef}
            value={draft}
            onChange={setDraft}
            onSubmit={submit}
            onStop={stop}
            onUndo={handleUndo}
            busy={busy}
            canUndo={turns.length > 0}
          />
        </div>
      </div>
    </div>
  );
}
