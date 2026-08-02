"use client";

import { LogIn } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authConfigured, getSupabase } from "@/lib/supabase";

/**
 * Sign-in control.
 *
 * Optional by design — the FAQ is public, so requiring an account to ask a public question
 * would be friction with no security benefit. An account buys saved history and a higher
 * rate limit, and the panel says exactly that.
 *
 * Renders nothing when Supabase is unconfigured, so the app is fully usable without it.
 */
export function AuthPanel({ onSession }: { onSession: (accessToken: string | null) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    void supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user.email ?? null);
      onSession(data.session?.access_token ?? null);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user.email ?? null);
      onSession(session?.access_token ?? null);
    });

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

  if (userEmail) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="hidden max-w-32 truncate sm:inline">{userEmail}</span>
        <Button variant="ghost" size="sm" onClick={() => void getSupabase()?.auth.signOut()}>
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
          aria-label="Sign in"
          className="absolute right-0 z-30 mt-2 w-72 rounded-xl border border-border bg-popover p-3 shadow-lg"
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit("in");
            }}
            className="flex flex-col gap-2"
          >
            <p className="text-xs text-muted-foreground">
              Optional — an account saves your history and raises your daily limit.
            </p>
            <Label htmlFor="auth-email" className="sr-only">
              Email
            </Label>
            <Input
              id="auth-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@uwindsor.ca"
            />
            <Label htmlFor="auth-password" className="sr-only">
              Password
            </Label>
            <Input
              id="auth-password"
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Password (8+ characters)"
            />
            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={pending} className="flex-1">
                Sign in
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={pending}
                onClick={() => void submit("up")}
                className="flex-1"
              >
                Create
              </Button>
            </div>
            {notice && (
              <p role="status" className="text-xs text-amber-600 dark:text-amber-400">
                {notice}
              </p>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
