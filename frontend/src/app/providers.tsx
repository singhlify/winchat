"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionProvider } from "@/lib/session";

/**
 * Client-side providers.
 *
 * The QueryClient is created inside `useState` rather than at module scope: a module-level
 * client would be shared across every request on the server and leak one visitor's cached
 * data into another's render.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // The model catalogue and source list change only on redeploy or re-ingest,
            // so refetching them on every window focus is pure noise.
            staleTime: 5 * 60_000,
            refetchOnWindowFocus: false,
            retry: (failureCount, error) => {
              // Retrying a 4xx just repeats the same rejection. A rate limit especially:
              // hammering it is what caused it.
              if (
                error instanceof ApiError &&
                error.status >= 400 &&
                error.status < 500
              ) {
                return false;
              }
              return failureCount < 2;
            },
          },
        },
      }),
  );

  return (
    // `defaultTheme="system"` respects the OS setting until the user overrides it, and
    // next-themes writes the class in a blocking inline script before paint — which is
    // what prevents the white flash a dark-mode user gets from a client-side toggle.
    // `disableTransitionOnChange` stops every coloured surface animating at once when the
    // theme flips, which reads as a glitch rather than a transition.
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        </SessionProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
