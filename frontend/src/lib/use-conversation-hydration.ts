"use client";

import { useEffect, useState } from "react";

import type { Turn } from "@/components/chat/use-chat";
import { fetchConversation } from "@/lib/api/client";
import { getConversation, hydrateConversation } from "@/lib/conversations";

/**
 * Fetch a synced conversation's transcript the first time it is opened.
 *
 * The sidebar sync stores conversations as stubs with no turns, because pulling every
 * transcript up front would mean one request per conversation to render a list the user
 * may never click. The cost of that choice is paid here: an opened conversation with an
 * empty transcript is either genuinely empty or merely not fetched yet, and this resolves
 * the difference.
 *
 * Returns turns only when it actually fetched something, so the caller can keep rendering
 * whatever it already had. A hook that returned `[]` while loading would blank a
 * transcript the user was reading.
 */
export function useConversationHydration(
  conversationId: string | undefined,
  accessToken: string | null,
): Turn[] | null {
  const [turns, setTurns] = useState<Turn[] | null>(null);

  useEffect(() => {
    if (!conversationId || !accessToken) return;

    // Only a stub needs filling. A conversation this browser produced already holds the
    // real transcript, and refetching would replace it with the server's copy for no gain.
    const existing = getConversation(conversationId);
    if (!existing || existing.turns.length > 0) return;

    const controller = new AbortController();

    void fetchConversation(conversationId, {
      accessToken,
      signal: controller.signal,
    })
      .then((detail) => {
        const restored: Turn[] = detail.turns.map((turn) => ({
          role: turn.role,
          content: turn.content,
          // The stored trace carries citations and the refusal flag, so a restored
          // conversation shows its sources rather than degrading to plain text.
          ...(turn.trace ?? {}),
        })) as Turn[];

        hydrateConversation(conversationId, restored);
        setTurns(restored);
      })
      .catch(() => {
        // 404 (not yours, or gone), offline, or signed out mid-flight. The conversation
        // simply stays as it was; there is nothing useful to say about it here.
      });

    return () => controller.abort();
  }, [conversationId, accessToken]);

  return turns;
}
