/**
 * Supabase client — for AUTHENTICATION ONLY.
 *
 * This is the one place `supabase-js` is allowed. It never reads or writes application
 * data: every query goes through our own API as plain SQL, which is what keeps the
 * database portable. Using the vendor SDK for login is a different trade — auth is a
 * protocol, not a schema, and hand-rolling session management, refresh and email flows
 * would spend the project's scarce time on the least differentiating part of it.
 *
 * Returns null when unconfigured, so the app runs anonymously without a Supabase project.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!url || !anonKey) return null;
  // The anon key is designed to be public: it grants nothing on its own, because Row Level
  // Security decides what a request may see. That is exactly why RLS is FORCEd server-side.
  client ??= createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      // PKCE rather than the implicit flow. A browser app is a *public* client — it cannot
      // keep a secret — so the implicit flow returns tokens directly in the URL fragment,
      // where they land in history and in anything that logs URLs. PKCE returns a
      // single-use code that is worthless without the verifier held in this tab.
      flowType: "pkce",
      // Lets the client finish an OAuth or recovery redirect on load, which is what makes
      // /auth/callback and /auth/reset work without hand-rolling a code exchange.
      detectSessionInUrl: true,
    },
  });
  return client;
}

/**
 * Where a provider or an email link should send the user back to.
 *
 * Read from the live origin rather than NEXT_PUBLIC_SITE_URL on purpose: preview
 * deployments have their own origin, and a hardcoded production URL would bounce a
 * preview login into production. Every value returned here must also be listed in
 * Supabase's redirect allowlist, which is what stops an open redirect.
 */
export function authRedirectTo(path: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  return new URL(path, window.location.origin).toString();
}

export const authConfigured = Boolean(url && anonKey);
