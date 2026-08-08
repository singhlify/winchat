"use client";

import { createContext, useContext, useMemo, useState } from "react";

/**
 * The signed-in access token, held once for the whole app.
 *
 * It used to live in `Chat`, because that is where the header — and therefore the sign-in
 * panel — happened to be rendered. That was fine while only the chat request needed a
 * token, and stopped being fine the moment `ChatShell` needed one too: the shell decides
 * which conversation to open, and it sat *above* the component holding the token.
 *
 * The fix is not to drill the prop upward through a callback, which would leave two
 * components owning the same fact. A session is an application-wide concern, so it lives in
 * one context that any component can read.
 *
 * Deliberately holds the token in memory only. `supabase-js` owns persistence and refresh;
 * a second copy in localStorage would be one more place for a stale token to survive a
 * sign-out.
 */

interface SessionValue {
  accessToken: string | null;
  setAccessToken: (token: string | null) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const value = useMemo(() => ({ accessToken, setAccessToken }), [accessToken]);
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) {
    // A hard failure rather than a silent null: a component reading the session outside the
    // provider would otherwise render as permanently signed out, which looks like a bug in
    // authentication rather than a mistake in the tree.
    throw new Error("useSession must be used inside <SessionProvider>");
  }
  return value;
}
