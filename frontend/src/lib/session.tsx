"use client";

import { createContext, useContext, useMemo, useState } from "react";

/**
 * The signed-in access token, held once for the whole app. It used to live in `Chat`, because
 * that is where the header, and therefore the sign-in panel, happened to be rendered.
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
