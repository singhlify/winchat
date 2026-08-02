"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const PINNED_THRESHOLD_PX = 80;

/**
 * Keeps a scroll container pinned to the bottom as content streams in — but only while the
 * user has not scrolled away.
 *
 * The naive version scrolls to the bottom on every token, which yanks the page out from
 * under anyone reading back through an earlier answer. Tracking whether they are near the
 * bottom, and surfacing a "jump to latest" affordance when they are not, is the difference
 * between a chat that follows along and one that fights you.
 */
export function useStickToBottom(dependencies: unknown[]) {
  const scrollRef = useRef<HTMLElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isPinned, setIsPinned] = useState(true);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;

    function onScroll() {
      if (!element) return;
      const distanceFromBottom =
        element.scrollHeight - element.scrollTop - element.clientHeight;
      setIsPinned(distanceFromBottom < PINNED_THRESHOLD_PX);
    }

    element.addEventListener("scroll", onScroll, { passive: true });
    return () => element.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!isPinned) return;
    bottomRef.current?.scrollIntoView({ block: "end" });
    // `dependencies` is the caller's content signal; re-running on it is the point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    setIsPinned(true);
  }, []);

  return { scrollRef, bottomRef, isPinned, scrollToBottom };
}
