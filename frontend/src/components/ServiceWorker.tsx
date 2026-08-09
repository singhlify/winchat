"use client";

import { useEffect } from "react";

/**
 * Register the service worker, in production only. Skipped in development on purpose: a
 * worker that caches build assets while those assets are being rebuilt every few seconds
 * serves stale chunks and produces hydration errors that look like application bugs.
 */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;

    const register = () => {
      void navigator.serviceWorker.register("/sw.js").catch(() => {
        // A failed registration is not worth surfacing: the app works without it, and
        // there is nothing the visitor could do about it.
      });
    };

    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
  }, []);

  return null;
}
