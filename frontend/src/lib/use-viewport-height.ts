"use client";

import { useEffect } from "react";

/**
 * Keep the app exactly as tall as the *visible* area, including when a keyboard is open.
 * Why `dvh` is not enough. Since Chrome 108 the on-screen keyboard resizes only the
 * VISUAL viewport, not the layout viewport — on Android and on iOS alike.
 */
export function useViewportHeight(): void {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const apply = () => {
      // Rounded down: a fractional height leaves a hairline gap that shows as a flickering
      // 1px seam under the composer while the keyboard animates.
      document.documentElement.style.setProperty(
        "--app-height",
        `${Math.floor(viewport.height)}px`,
      );
    };

    apply();
    viewport.addEventListener("resize", apply);
    // `scroll` matters on iOS: focusing an input scrolls the visual viewport within the
    // layout viewport, which changes what is actually visible without firing `resize`.
    viewport.addEventListener("scroll", apply);

    return () => {
      viewport.removeEventListener("resize", apply);
      viewport.removeEventListener("scroll", apply);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
}
