"use client";

import { useEffect, useState } from "react";

import { authConfigured, getSupabase } from "@/lib/supabase";

/**
 * Sign-in control.
 *
 * Signing in is optional by design — the FAQ is public, so requiring an account to ask a
 * public question would be friction with no security benefit. What an account buys is
 * saved history and a higher rate limit, and the button says so.
 *
 * Renders nothing at all when Supabase is not configured, so the app is fully usable
 * without it.
 */
export function AuthPanel({
  onSession,
}: {
  onSession: (accessToken: string | null) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user.email ?? null);
      onSession(data.session?.access_token ?? null);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user.email ?? null);
      onSession(session?.access_token ?? null);
    });

    return () => subscription.subscription.unsubscribe();
  }, [onSession]);

  if (!authConfigured) return null;

  async function submit(mode: "in" | "up") {
    const supabase = getSupabase();
    if (!supabase) return;

    setPending(true);
    setNotice(null);
    const { error } =
      mode === "in"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setPending(false);

    if (error) setNotice(error.message);
    else if (mode === "up") setNotice("Check your email to confirm the account.");
    else {
      setOpen(false);
      setPassword("");
    }
  }

  async function signOut() {
    await getSupabase()?.auth.signOut();
  }

  if (userEmail) {
    return (
      <div className="flex items-center gap-2 text-sm text-neutral-500">
        <span className="max-w-40 truncate">{userEmail}</span>
        <button onClick={() => void signOut()} className="underline underline-offset-2">
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        Sign in
      </button>

      {open && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit("in");
          }}
          className="absolute right-0 z-10 mt-2 flex w-72 flex-col gap-2 rounded-lg border border-neutral-200 bg-white p-3 shadow-lg dark:border-neutral-800 dark:bg-neutral-900"
        >
          <p className="text-xs text-neutral-500">
            Optional — an account saves your history and raises your daily limit.
          </p>
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@uwindsor.ca"
            className="rounded border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700"
          />
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            className="rounded border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={pending}
              className="flex-1 rounded bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
            >
              Sign in
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => void submit("up")}
              className="flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-neutral-700"
            >
              Create
            </button>
          </div>
          {notice && <p className="text-xs text-amber-600 dark:text-amber-400">{notice}</p>}
        </form>
      )}
    </div>
  );
}
