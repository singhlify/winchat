"use client";

import { useEffect, useRef } from "react";

import { fetchConversations } from "@/lib/api/client";
import { mergeServerConversations } from "@/lib/conversations";

/**
 * Pull the account's saved conversations into this browser when a session appears.
 *
 * This is what makes signing in worth doing. Conversations were always written server-side
 * for signed-in users; nothing ever read them back, so an account stored your history and
 * could not show it to you — the history existed and was reachable only from the device
 * that happened to still hold its id.
 *
 * Runs once per token rather than on an interval. A chat app does not change behind your
 * back often enough to justify polling, and a background request every N seconds on a
 * free-tier backend is a self-inflicted load problem.
 *
 * Failure is deliberately silent. A visitor who cannot reach the sync endpoint still has a
 * fully working app with local history — surfacing "could not sync" would turn a
 * degradation into an error message about a feature they may not know exists.
 */
export function useAccountSync(accessToken: string | null): void {
  // Tracks which token has already been synced, so a re-render does not refetch. A ref
  // rather than state: nothing renders from this, and state would cause the extra render
  // it is trying to avoid.
  const syncedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!accessToken || syncedFor.current === accessToken) return;
    syncedFor.current = accessToken;

    const controller = new AbortController();

    void fetchConversations({ accessToken, signal: controller.signal })
      .then((conversations) => mergeServerConversations(conversations))
      .catch(() => {
        // Signed out mid-flight, offline, or the backend cold-starting. All of these are
        // fine — try again on the next sign-in rather than nagging.
      });

    return () => controller.abort();
  }, [accessToken]);
}
