import type { Metadata } from "next";
import { RotateCcw } from "lucide-react";
import Link from "next/link";

/**
 * Shown by the service worker when a navigation fails.
 *
 * Says what is actually true rather than "you are offline", which is not always the
 * reason: the backend sleeps on a free instance and a cold start can take the better part
 * of a minute, which looks identical from here.
 */
export const metadata: Metadata = {
  title: "Offline · WinChat",
  robots: { index: false, follow: false },
};

export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center gap-4 px-6">
      <p className="text-gold-foreground flex items-center gap-2.5 text-xs font-medium tracking-[0.14em] uppercase">
        <span aria-hidden className="bg-gold h-px w-8" />
        No connection
      </p>
      <h1 className="font-display text-4xl">WinChat needs the network</h1>
      <p className="text-muted-foreground text-base leading-relaxed">
        Every answer is retrieved and cited at the moment you ask, so there is
        nothing useful to show while offline. Your saved conversations are still
        on this device and will be here when the connection returns.
      </p>
      <p className="text-muted-foreground text-sm leading-relaxed">
        If you are online, the server may be waking up. That can take up to a
        minute on the free tier.
      </p>
      <div>
        <Link
          href="/app"
          className="bg-primary text-primary-foreground inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium transition-opacity hover:opacity-90"
        >
          <RotateCcw className="size-4" aria-hidden />
          Try again
        </Link>
      </div>
    </main>
  );
}
