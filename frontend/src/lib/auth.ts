/**
 * Every authentication action the app can take, in one place. The panel owns presentation;
 * this owns what actually happens.
 */

import { authRedirectTo, getSupabase } from "@/lib/supabase";

export type AuthResult = { error: string | null; notice?: string };

/** Providers offered in the UI. Each must also be enabled in the Supabase dashboard. */
export const OAUTH_PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "github", label: "GitHub" },
] as const;

export type OAuthProvider = (typeof OAUTH_PROVIDERS)[number]["id"];

const UNCONFIGURED = "Sign-in is not configured for this deployment.";

/**
 * Supabase messages are written for developers. A few of them reach end users often enough
 * to be worth translating; everything else passes through, because inventing a friendly
 * message for an error you did not anticipate usually means hiding the useful one.
 */
function humanize(message: string): string {
  const lowered = message.toLowerCase();
  if (lowered.includes("invalid login credentials")) {
    return "That email and password do not match an account.";
  }
  if (lowered.includes("email not confirmed")) {
    return "Confirm your email address first. Check your inbox for the link.";
  }
  if (lowered.includes("user already registered")) {
    return "An account with that email already exists. Try signing in.";
  }
  if (lowered.includes("password should be at least")) {
    return "Password is too short. Use at least 8 characters.";
  }
  if (lowered.includes("rate limit") || lowered.includes("too many")) {
    return "Too many attempts. Wait a minute and try again.";
  }
  return message;
}

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { error } = await supabase.auth.signInWithPassword({ email, password });
  return { error: error ? humanize(error.message) : null };
}

export async function signUpWithPassword(
  email: string,
  password: string,
): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { emailRedirectTo: authRedirectTo("/auth/callback") },
  });
  if (error) return { error: humanize(error.message) };

  // A confirmed-on-signup project returns a session immediately; one that requires email
  // confirmation does not. Reporting "check your inbox" in the first case would leave the
  // user waiting for an email that is never coming.
  if (data.session) return { error: null };
  return { error: null, notice: "Check your email for a confirmation link." };
}

export async function signInWithProvider(
  provider: OAuthProvider,
): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: authRedirectTo("/auth/callback") },
  });
  // On success the browser navigates away, so nothing after this runs.
  return { error: error ? humanize(error.message) : null };
}

export async function sendPasswordReset(email: string): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: authRedirectTo("/auth/reset"),
  });
  if (error) return { error: humanize(error.message) };

  // Deliberately identical whether or not the address has an account. Saying "no account with
  // that email" turns the reset form into a membership oracle. An attacker can farm which
  // addresses are registered without ever signing in.
  return {
    error: null,
    notice: "If that email has an account, a reset link is on its way.",
  };
}

export async function updatePassword(password: string): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { error } = await supabase.auth.updateUser({ password });
  return { error: error ? humanize(error.message) : null };
}

export async function signOut(): Promise<AuthResult> {
  const supabase = getSupabase();
  if (!supabase) return { error: UNCONFIGURED };

  const { error } = await supabase.auth.signOut();
  return { error: error ? humanize(error.message) : null };
}
