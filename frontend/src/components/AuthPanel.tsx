"use client";

import { LogIn } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  OAUTH_PROVIDERS,
  type OAuthProvider,
  sendPasswordReset,
  signInWithPassword,
  signInWithProvider,
  signOut,
  signUpWithPassword,
} from "@/lib/auth";
import { authConfigured, getSupabase } from "@/lib/supabase";

/**
 * Sign-in control: email/password, social providers, and password recovery.
 *
 * Optional by design — the FAQ is public, so requiring an account to ask a public question
 * would be friction with no security benefit. An account buys saved history and a higher
 * rate limit (100/hour against 20), and the panel says exactly that.
 *
 * Renders nothing when Supabase is unconfigured, so the app is fully usable without it.
 *
 * One panel with three views rather than three routes: signing in is an interruption to
 * whatever the visitor came here to do, and sending them to a separate page loses their
 * place. The two views that MUST be routes — the OAuth return and the recovery link — are
 * pages under /auth, because an email link has nowhere else to land.
 */

type View = "in" | "up" | "forgot";

const VIEW_TITLE: Record<View, string> = {
  in: "Sign in",
  up: "Create an account",
  forgot: "Reset your password",
};

export function AuthPanel({
  onSession,
}: {
  onSession: (accessToken: string | null) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("in");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    void supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user.email ?? null);
      onSession(data.session?.access_token ?? null);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUserEmail(session?.user.email ?? null);
        onSession(session?.access_token ?? null);
      },
    );

    return () => subscription.subscription.unsubscribe();
  }, [onSession]);

  // Dismiss on outside click and on Escape — a panel that can only be closed by the button
  // that opened it is a trap on touch devices.
  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      if (!panelRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Move focus into the panel when it opens. Without this a keyboard user tabs from the
  // trigger straight past the form they just asked for.
  useEffect(() => {
    if (open) emailRef.current?.focus();
  }, [open, view]);

  const switchTo = useCallback((next: View) => {
    setView(next);
    setError(null);
    setNotice(null);
  }, []);

  if (!authConfigured) return null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setNotice(null);

    const result =
      view === "in"
        ? await signInWithPassword(email, password)
        : view === "up"
          ? await signUpWithPassword(email, password)
          : await sendPasswordReset(email);

    setPending(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    if (result.notice) {
      setNotice(result.notice);
      return;
    }
    // Signed in with a live session — close up and clear the password from memory.
    setOpen(false);
    setPassword("");
  }

  async function oauth(provider: OAuthProvider) {
    setPending(true);
    setError(null);
    const result = await signInWithProvider(provider);
    // Only reached if the redirect never happened.
    setPending(false);
    if (result.error) setError(result.error);
  }

  if (userEmail) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="hidden max-w-32 truncate sm:inline" title={userEmail}>
          {userEmail}
        </span>
        <Button variant="ghost" size="sm" onClick={() => void signOut()}>
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className="relative" ref={panelRef}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <LogIn className="size-4 sm:hidden" aria-hidden />
        <span className="hidden sm:inline">Sign in</span>
      </Button>

      {open && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label={VIEW_TITLE[view]}
          className="absolute right-0 z-30 mt-2 w-80 rounded-xl border border-border bg-popover p-4 shadow-lg"
        >
          <h2 className="text-sm font-medium">{VIEW_TITLE[view]}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {view === "forgot"
              ? "We will email you a link to choose a new password."
              : "Optional — an account saves your history and raises your hourly limit from 20 to 100."}
          </p>

          {view !== "forgot" && (
            <>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {OAUTH_PROVIDERS.map((provider) => (
                  <Button
                    key={provider.id}
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={pending}
                    onClick={() => void oauth(provider.id)}
                  >
                    {provider.label}
                  </Button>
                ))}
              </div>
              <div className="my-3 flex items-center gap-2">
                <span className="h-px flex-1 bg-border" />
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  or
                </span>
                <span className="h-px flex-1 bg-border" />
              </div>
            </>
          )}

          <form onSubmit={submit} className="flex flex-col gap-2">
            <Label htmlFor="auth-email" className="sr-only">
              Email
            </Label>
            <Input
              id="auth-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@uwindsor.ca"
            />

            {view !== "forgot" && (
              <>
                <Label htmlFor="auth-password" className="sr-only">
                  Password
                </Label>
                <Input
                  id="auth-password"
                  type="password"
                  // Tells a password manager whether to offer a saved password or a new one.
                  autoComplete={
                    view === "in" ? "current-password" : "new-password"
                  }
                  required
                  minLength={8}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Password (8+ characters)"
                />
              </>
            )}

            <Button type="submit" size="sm" disabled={pending}>
              {pending
                ? "Working…"
                : view === "in"
                  ? "Sign in"
                  : view === "up"
                    ? "Create account"
                    : "Send reset link"}
            </Button>
          </form>

          <div className="mt-3 flex items-center justify-between text-xs">
            {view === "in" ? (
              <>
                <button
                  type="button"
                  className="text-muted-foreground underline-offset-2 hover:underline"
                  onClick={() => switchTo("up")}
                >
                  Create an account
                </button>
                <button
                  type="button"
                  className="text-muted-foreground underline-offset-2 hover:underline"
                  onClick={() => switchTo("forgot")}
                >
                  Forgot password?
                </button>
              </>
            ) : (
              <button
                type="button"
                className="text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => switchTo("in")}
              >
                Back to sign in
              </button>
            )}
          </div>

          {/* Live regions, so a screen reader announces the outcome instead of leaving the
              user to discover it. Errors are assertive; confirmations are polite. */}
          {error && (
            <p role="alert" className="mt-2 text-xs text-destructive">
              {error}
            </p>
          )}
          {notice && (
            <p
              role="status"
              className="mt-2 text-xs text-emerald-600 dark:text-emerald-400"
            >
              {notice}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
