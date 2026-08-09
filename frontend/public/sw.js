/**
 * Service worker.
 *
 * Deliberately small. A chat assistant is useless offline: every answer needs the model,
 * the embeddings and the database, so there is nothing meaningful to cache and pretending
 * otherwise would produce an installed app that opens and then fails at the first question.
 *
 * What it does buy is worth having:
 *
 *   1. An installed app that opens instantly instead of waiting on the network for its
 *      shell, which on a cold Render instance can be fifty seconds.
 *   2. An honest offline page instead of the browser's dinosaur, so someone on the subway
 *      is told what happened rather than left guessing.
 *
 * Strategies are chosen per resource rather than applied globally:
 *
 *   - Navigations are NETWORK-FIRST. A stale HTML shell is how a PWA ends up serving a
 *     build from three deploys ago with no way to escape it.
 *   - Static build assets are CACHE-FIRST, because Next fingerprints their filenames, so a
 *     hit is always the exact file that was asked for.
 *   - API calls are never cached. A cached answer is worse than no answer when the whole
 *     product promise is that answers are current and cited.
 */

const VERSION = "winchat-v1";
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;
const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((cache) => cache.addAll([OFFLINE_URL]))
      // `skipWaiting` so a fix reaches people on their next launch rather than whenever
      // they happen to close every tab.
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only GET. A cached POST would mean a replayed question, and the Range requests a
  // media element makes cannot be satisfied from a full cached response.
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache the API. An answer is only worth showing if it is current.
  if (url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL);
        return (await cache.match(OFFLINE_URL)) ?? Response.error();
      }),
    );
    return;
  }

  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ??
          fetch(request).then((response) => {
            // Only store a real success. Caching an opaque or error response pins a
            // broken asset until the next version bump.
            if (response.ok) {
              const copy = response.clone();
              void caches.open(ASSETS).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});
