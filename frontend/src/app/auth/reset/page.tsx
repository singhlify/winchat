"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { updatePassword } from "@/lib/auth";
import { KeyRound } from "lucide-react";
import Link from "next/link";

import { authConfigured, getSupabase } from "@/lib/supabase";

/**
 * Choose a new password, after following the link from a reset email.
 *
 * How this works, because it is not obvious: the recovery link signs the visitor in to a
 * short-lived session and `supabase-js` raises a `PASSWORD_RECOVERY` event on load. From
 * there `updateUser({ password })` applies to the session the link established — so there
 * is no token to handle here, and no "old password" field, because possession of a
 * mailbox is what authorised the change.
 *
 * The consequence worth stating: this page must confirm a real session exists before
 * showing the form. Without that check it would render a password field to anyone who
 * typed the URL, and they would get a confusing failure instead of an honest one.
 */
export default function ResetPasswordPage() {
  const [ready, setReady] = useState(false);
  // Known at first render; see the note in the callback page about setState-in-effect.
  const [invalid, setInvalid] = useState(!authConfigured);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    const { data: subscription } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (event === "PASSWORD_RECOVERY" || session) setReady(true);
      },
    );

    void supabase.auth.getSession().then(({ data }) => {
      if (data.session) setReady(true);
    });

    const timeout = window.setTimeout(() => setInvalid(true), 8000);
    return () => {
      subscription.subscription.unsubscribe();
      window.clearTimeout(timeout);
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    // Checked here rather than only with `pattern`, because a mismatch is worth an explicit
    // message and browser validation messages are easy to miss.
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }

    setPending(true);
    setError(null);
    const result = await updatePassword(password);
    setPending(false);

    if (result.error) setError(result.error);
    else setDone(true);
  }

  if (done) {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
        <h1 className="text-lg font-medium">Password updated</h1>
        <p role="status" className="text-sm text-muted-foreground">
          You are signed in with your new password.
        </p>
        <Link href="/app" className="text-sm underline underline-offset-4">
          Back to WinChat
        </Link>
      </main>
    );
  }

  if (invalid && !ready) {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
        <h1 className="text-lg font-medium">
          This reset link is no longer valid
        </h1>
        <p role="alert" className="text-sm text-muted-foreground">
          Reset links expire and can only be used once. Request a new one from
          the sign-in panel.
        </p>
        <Link href="/app" className="text-sm underline underline-offset-4">
          Back to WinChat
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center gap-4 px-6">
      <div>
        <h1 className="text-lg font-medium">Choose a new password</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          At least 8 characters. Longer beats complicated.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="new-password">New password</Label>
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            disabled={!ready}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="confirm-password">Confirm new password</Label>
          <Input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            disabled={!ready}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </div>

        <Button type="submit" disabled={pending || !ready}>
          <KeyRound className="size-4" aria-hidden />
          {pending
            ? "Updating…"
            : ready
              ? "Update password"
              : "Checking your link…"}
        </Button>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </form>
    </main>
  );
}
