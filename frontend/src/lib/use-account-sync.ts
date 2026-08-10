"use client";

import { useEffect, useRef } from "react";

import { fetchConversations } from "@/lib/api/client";
import { mergeServerConversations } from "@/lib/conversations";

/**
 * Pull the account's saved conversations into this browser when a session appears.
 */
export function useAccountSync(accessToken: string | null): void {
  // Tracks which token has already been synced, so a re-render does not refetch. A ref rather
  // than state: nothing renders from this, and state would cause the extra render it is
  // trying to avoid.
  const syncedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!accessToken || syncedFor.current === accessToken) return;
    syncedFor.current = accessToken;

    const controller = new AbortController();

    void fetchConversations({ accessToken, signal: controller.signal })
      .then((conversations) => mergeServerConversations(conversations))
      .catch(() => {
        // Signed out mid-flight, offline, or the backend cold-starting. All of these are
        // fine, try again on the next sign-in rather than nagging.
      });

    return () => controller.abort();
  }, [accessToken]);
}
