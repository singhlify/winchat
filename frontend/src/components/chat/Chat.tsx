"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AssistantMessage, UserMessage } from "@/components/chat/Message";
import { Composer, type ComposerHandle } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { useChat, type Turn } from "@/components/chat/use-chat";
import { submitFeedback } from "@/lib/api/client";
import { useSession } from "@/lib/session";
import { useAccountSync } from "@/lib/use-account-sync";
import { useStickToBottom } from "@/components/chat/use-stick-to-bottom";
import { Header } from "@/components/Header";

export function Chat({
  sourceCount,
  initialTurns,
  onTurnsChange,
  sidebarOpen,
  onToggleSidebar,
  model,
  onModelChange,
}: {
  sourceCount?: number;
  initialTurns?: Turn[];
  onTurnsChange?: (turns: Turn[], serverConversationId: string | null) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  model: string | null;
  onModelChange: (model: string | null) => void;
}) {
  const [draft, setDraft] = useState("");
  // The session lives in context: ChatShell sits above this component and needs the same
  // token to hydrate a conversation opened from another device.
  const { accessToken, setAccessToken } = useSession();

  // Signing in makes the account's saved conversations appear in the sidebar. Without
  // this the server kept a history it could never show anyone.
  useAccountSync(accessToken);
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

  const {
    turns,
    busy,
    send,
    stop,
    retry,
    editFrom,
    clear,
    rate,
    serverConversationId,
  } = useChat({
    accessToken,
    model,
    initialTurns,
    onFeedback,
  });

  // Persist whenever the transcript settles. Gated on `busy` so a streaming answer is not
  // written to storage on every token.
  useEffect(() => {
    if (busy || turns.length === 0) return;
    onTurnsChange?.(turns, serverConversationId);
  }, [busy, turns, serverConversationId, onTurnsChange]);

  const { scrollRef, bottomRef, isPinned, scrollToBottom } = useStickToBottom([
    turns,
  ]);

  // `setAccessToken` is a useState setter behind the context, so it is referentially
  // stable and listing it costs nothing — but the linter cannot prove that through a
  // context boundary, and silencing the rule is worse than satisfying it.
  const handleSession = useCallback(
    (token: string | null) => setAccessToken(token),
    [setAccessToken],
  );

  const submit = useCallback(() => {
    send(draft);
    setDraft("");
  }, [draft, send]);

  /**
   * Rewind to a question and put it back in the composer for rewriting.
   *
   * Focus moves to the composer deliberately: the message the user was pointing at has
   * just disappeared from the transcript, and leaving focus on a removed element strands
   * a keyboard or screen-reader user with nothing selected.
   */
  const handleEdit = useCallback(
    (index: number) => {
      const restored = editFrom(index);
      if (restored === null) return;
      composerRef.current?.setValue(restored);
      composerRef.current?.focus();
    },
    [editFrom],
  );

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
    // The shell owns the viewport height; this fills whatever column it is given.
    <div className="flex h-full min-h-0 flex-col">
      <Header
        onSession={handleSession}
        model={model}
        onModelChange={onModelChange}
        onNewChat={turns.length > 0 ? clear : undefined}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={onToggleSidebar}
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
                  <UserMessage
                    key={turn.id}
                    content={turn.content}
                    onEdit={busy ? undefined : () => handleEdit(index)}
                  />
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
            busy={busy}
          />
        </div>
      </div>
    </div>
  );
}
