"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { authConfigured, getSupabase } from "@/lib/supabase";

/**
 * Where OAuth providers and email confirmation links return to.
 *
 * The work is done by `supabase-js` itself: the browser client is created with
 * `detectSessionInUrl`, so it exchanges the PKCE code for a session as soon as it
 * initialises. This page's only job is to wait for that to finish and then get out of the
 * way — which is why it holds no tokens and does nothing clever.
 *
 * It is a client component because the code exchange needs the PKCE verifier, which lives
 * in this browser's storage and is deliberately never sent to a server. That is the point
 * of PKCE: a code intercepted in transit is useless without it.
 *
 * `router.replace` is not used: a hard assignment guarantees the URL — which still carries
 * the authorization code — is gone from the address bar and not left in history.
 */
export default function AuthCallbackPage() {
  // Derived at first render, not set inside the effect: whether Supabase is configured is
  // known before mount, and setting state synchronously in an effect triggers a second
  // render pass for a value that never changes.
  const [error, setError] = useState<string | null>(
    authConfigured ? null : "Sign-in is not configured for this deployment.",
  );

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      window.location.replace("/app");
    };

    // Either the session is already established, or it lands a moment later via the
    // auth-state event. Listening to both avoids a race that would otherwise show a
    // "could not sign in" message to someone who signed in perfectly well.
    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (session) finish();
      },
    );

    void supabase.auth.getSession().then(({ data }) => {
      if (data.session) finish();
    });

    // If neither fires, the link was already used or has expired. Say so rather than
    // spinning forever.
    const timeout = window.setTimeout(() => {
      if (!done) setError("That sign-in link has expired or was already used.");
    }, 8000);

    return () => {
      subscription.subscription.unsubscribe();
      window.clearTimeout(timeout);
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
      {error ? (
        <>
          <h1 className="text-lg font-medium">Could not complete sign-in</h1>
          <p role="alert" className="text-sm text-muted-foreground">
            {error}
          </p>
          <Link href="/app" className="text-sm underline underline-offset-4">
            Back to WinChat
          </Link>
        </>
      ) : (
        <p role="status" className="text-sm text-muted-foreground">
          Signing you in…
        </p>
      )}
    </main>
  );
}
