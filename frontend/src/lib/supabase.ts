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
    auth: { persistSession: true, autoRefreshToken: true },
  });
  return client;
}

export const authConfigured = Boolean(url && anonKey);
