"use client";

import { useCallback, useState } from "react";

/**
 * State that survives reloads and route changes, stored in localStorage. Written for the
 * model picker, which reset to the default every time the first answer moved the user from
 * `/` to `/c/{id}`, the route change remounts the tree, so anything held in component state
 * is lost.
 */
export function usePersistentState<T extends string | null>(
  key: string,
  initial: T,
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === "undefined") return initial;
    try {
      return (window.localStorage.getItem(key) as T) ?? initial;
    } catch {
      return initial;
    }
  });

  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        if (next === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, next);
      } catch {
        // Storage unavailable, the value still applies for this session.
      }
    },
    [key],
  );

  return [value, update];
}
