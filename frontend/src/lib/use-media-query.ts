"use client";

import { useSyncExternalStore } from "react";

/**
 * Subscribe to a CSS media query.
 *
 * `useSyncExternalStore` rather than an effect that calls setState: the viewport is
 * external state that React does not own, and this is the API built for exactly that. It
 * also keeps the value correct when the viewport changes after mount — an effect with an
 * empty dependency list reads it once and then quietly goes stale on rotation or resize.
 *
 * The server snapshot is `false` because no viewport exists during server rendering.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
