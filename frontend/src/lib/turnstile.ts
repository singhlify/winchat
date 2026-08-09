/**
 * Cloudflare Turnstile, invisible mode.
 *
 * Produces a short-lived token proving this browser solved a challenge, which the API
 * exchanges with Cloudflare. Nothing here proves anything on its own — a token the server
 * does not verify is decoration — so this module's only job is to obtain one and hand it
 * over.
 *
 * Invisible rather than a checkbox, and only for guests: a signed-in visitor already proved
 * themselves to an identity provider. The median real visitor sees nothing at all.
 *
 * Everything degrades to `null` when unconfigured or unavailable. The backend treats a
 * missing token as "feature off" when it has no secret, so an app without Turnstile keys
 * behaves exactly as it did before — and a Cloudflare outage does not take the app down.
 */

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export const turnstileConfigured = Boolean(SITE_KEY);

interface TurnstileApi {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  execute: (widgetId: string, options?: Record<string, unknown>) => void;
  reset: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<void> | null = null;
let widgetId: string | null = null;

function loadScript(): Promise<void> {
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${SCRIPT_SRC}"]`,
    );
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () =>
        reject(new Error("turnstile failed to load")),
      );
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("turnstile failed to load"));
    document.head.appendChild(script);
  });

  return scriptPromise;
}

/**
 * A fresh token for one request.
 *
 * Turnstile tokens are single-use — Cloudflare rejects a replay with
 * `timeout-or-duplicate` — so this executes the widget per message rather than caching.
 * In invisible mode that is typically imperceptible after the first load.
 *
 * Returns null rather than throwing on any failure. A guest who cannot reach Cloudflare
 * should still be able to ask a question; the server decides what to do about a missing
 * token, and the rate limiter is still there either way.
 */
export async function getTurnstileToken(): Promise<string | null> {
  if (!SITE_KEY || typeof window === "undefined") return null;

  try {
    await loadScript();
    const api = window.turnstile;
    if (!api) return null;

    if (widgetId === null) {
      // An offscreen container: invisible mode still needs somewhere to mount, and a
      // `display: none` element is not reliably executed by the widget.
      const container = document.createElement("div");
      container.style.position = "absolute";
      container.style.width = "0";
      container.style.height = "0";
      container.style.overflow = "hidden";
      container.setAttribute("aria-hidden", "true");
      document.body.appendChild(container);
      widgetId = api.render(container, {
        sitekey: SITE_KEY,
        // `appearance: "execute"` is what makes the widget render nothing until
        // `execute()` is called — there is no `size: "invisible"`, which an earlier
        // version passed and Turnstile would simply have ignored.
        //
        // This pairs with the dashboard widget mode set to **Invisible**. It must not be
        // used with "Managed": that mode escalates suspicious traffic to an interactive
        // challenge, and a challenge rendered into the 0x0 offscreen container below is
        // one nobody can solve — the request would hang until the timeout and fail.
        appearance: "execute",
      });
    }

    const id = widgetId;
    return await new Promise<string | null>((resolve) => {
      // A hung challenge must not hang the message. Five seconds is far longer than an
      // invisible solve takes and short enough that a visitor does not notice a stall.
      const timer = window.setTimeout(() => resolve(null), 5000);

      api.execute(id, {
        callback: (token: string) => {
          window.clearTimeout(timer);
          api.reset(id);
          resolve(token);
        },
        "error-callback": () => {
          window.clearTimeout(timer);
          api.reset(id);
          resolve(null);
        },
      });
    });
  } catch {
    return null;
  }
}
