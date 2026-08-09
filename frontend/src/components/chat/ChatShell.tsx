"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Chat } from "@/components/chat/Chat";
import { Sidebar } from "@/components/chat/Sidebar";
import type { Turn } from "@/components/chat/use-chat";
import {
  getConversation,
  newConversationId,
  saveConversation,
  titleFrom,
} from "@/lib/conversations";
import { useSession } from "@/lib/session";
import { useViewportHeight } from "@/lib/use-viewport-height";
import { useConversationHydration } from "@/lib/use-conversation-hydration";
import { useMediaQuery } from "@/lib/use-media-query";
import { usePersistentState } from "@/lib/use-persistent-state";

/**
 * The application shell: sidebar plus the active conversation. It owns three things the chat
 * view should not: which conversation is open, whether the sidebar is showing, and
 * persistence.
 */
export function ChatShell({ conversationId }: { conversationId?: string }) {
  const router = useRouter();

  // Keeps the shell as tall as the *visible* area when a keyboard is open. `dvh` alone does
  // not shrink for the keyboard on any current browser, and the viewport-meta opt-out that
  // would fix it has no WebKit support.
  useViewportHeight();

  // Open by default on desktop, closed on mobile — but only until the user decides,
  // after which their choice wins for the rest of the session.
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [override, setOverride] = useState<boolean | null>(null);
  const sidebarOpen = override ?? isDesktop;

  // Restored once, synchronously on first render, so the transcript is never briefly empty
  // before its own content appears.
  const [initialTurns] = useState<Turn[]>(() =>
    conversationId ? (getConversation(conversationId)?.turns ?? []) : [],
  );

  // State, not a ref: this id is read during render (as the remount key), and a ref read
  // in render is exactly the pattern that goes stale without re-rendering.
  const [id] = useState(() => conversationId ?? newConversationId());

  // A conversation synced from another device arrives as a stub with no turns; this fetches
  // the transcript the first time it is opened. Returns null until it has something, so a
  // locally-produced conversation is never blanked while a request is in flight.
  const { accessToken } = useSession();
  const hydrated = useConversationHydration(conversationId, accessToken);

  // Persisted so an explicit choice survives the /-to-/c/{id} navigation and reloads.
  const [model, setModel] = usePersistentState<string | null>(
    "winchat:model",
    null,
  );
  const navigatedRef = useRef(Boolean(conversationId));

  const persist = useCallback(
    (turns: Turn[], serverConversationId: string | null) => {
      const firstQuestion = turns.find((turn) => turn.role === "user");
      if (!firstQuestion) return;

      const existing = getConversation(id);
      saveConversation({
        id,
        // A manual rename must survive later messages, so an existing title wins.
        title: existing?.title ?? titleFrom(firstQuestion.content),
        createdAt: existing?.createdAt ?? Date.now(),
        updatedAt: Date.now(),
        turns,
        // Links this local conversation to the row the API created, so account sync
        // recognises it instead of adding a duplicate.
        serverId: serverConversationId ?? existing?.serverId,
      });

      // Move to the conversation's own URL after the first exchange. `replace`, not `push`:
      // Back should return to wherever the user came from, not to the same chat in its empty
      // state.
      if (!navigatedRef.current) {
        navigatedRef.current = true;
        router.replace(`/app/c/${id}`, { scroll: false });
      }
    },
    [id, router],
  );

  return (
    <div className="flex h-[var(--app-height,100dvh)] overflow-hidden bg-background">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setOverride(false)}
        isDesktop={isDesktop}
      />
      <div className="relative flex min-w-0 flex-1 flex-col">
        <Chat
          // Remounting on id change resets every piece of conversation state at once — far
          // safer than trying to reconcile a half-streamed answer with a new thread. Also
          // remounts once a hydrated transcript arrives: `initialTurns` is read at mount, so
          // without this the fetched turns would sit in storage unseen until the next
          // navigation.
          key={hydrated ? `${id}:hydrated` : id}
          initialTurns={hydrated ?? initialTurns}
          onTurnsChange={persist}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setOverride(!sidebarOpen)}
          model={model}
          onModelChange={setModel}
        />
      </div>
    </div>
  );
}
