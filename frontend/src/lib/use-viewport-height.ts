"use client";

import { useEffect } from "react";

/**
 * Keep the app exactly as tall as the *visible* area, including when a keyboard is open.
 *
 * **Why `dvh` is not enough.** Since Chrome 108 the on-screen keyboard resizes only the
 * VISUAL viewport, not the layout viewport — on Android and on iOS alike. Viewport units
 * are computed from the layout viewport, so `100dvh` does not shrink when the keyboard
 * appears and a bottom-pinned composer ends up underneath it.
 *
 * `interactive-widget=resizes-content` in the viewport meta fixes this by shrinking the
 * layout viewport instead — but it has **no WebKit support at any version**, so it does
 * nothing on iPhone, which is most of this app's traffic. This hook is the cross-browser
 * half: `window.visualViewport` is supported everywhere that matters and reports the real
 * visible height.
 *
 * The two combine safely rather than fighting. Where `resizes-content` is honoured the
 * layout viewport has already shrunk, so `visualViewport.height` matches it and this writes
 * the same number it would have used anyway.
 *
 * Sets a custom property rather than inline styles so any component can opt in with
 * `h-[var(--app-height,100dvh)]`, and the fallback is a plain CSS value for browsers
 * without `visualViewport` — no JavaScript required for the app to be usable.
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
