"use client";

import { MessageSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AccountMenu } from "@/components/AccountMenu";
import { Logo } from "@/components/Logo";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/**
 * The site's one navigation bar. Everything outside the chat used to have its own header, or
 * none at all: the landing page had a bespoke one with no theme control, the sources page had
 * a bare "back" link, and the app had a wordmark-less toolbar with no way home.
 */
export function SiteNav({
  leading,
  cta = true,
  trailing,
  className,
}: {
  leading?: React.ReactNode;
  /** The "Open WinChat" button. Hidden inside the app, where it would point at itself. */
  cta?: boolean;
  /**
   * Page-specific controls, placed before the account menu. The chat puts its model picker
   * here rather than inside the account menu, because the model changes the answer you are
   * about to get: that is a property of the conversation, not a preference, and burying it
   * would hide the one setting worth seeing.
   */
  trailing?: React.ReactNode;
  className?: string;
}) {
  const pathname = usePathname();
  const { setAccessToken } = useSession();

  // Hidden inside the app, where the sidebar already carries this link. Two routes to the
  // same page a few hundred pixels apart reads as an oversight, not as convenience.
  const inApp = pathname.startsWith("/app");

  const links = inApp ? [] : [{ href: "/sources", label: "Sources" }];

  return (
    <header
      className={cn(
        "border-border/60 bg-background/85 sticky top-0 z-20 border-b backdrop-blur",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-5xl items-center gap-1 px-4 py-2.5 sm:gap-3 sm:px-6">
        {leading}

        {/* The wordmark is a link home on every page, including the app. Its absence there
            was the one navigational dead end left in the product. */}
        <Link
          href="/"
          className="focus-visible:outline-ring flex items-center gap-2 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          <Logo className="text-primary size-[22px]" />
          <span
            className={cn(
              "text-sm font-semibold tracking-tight",
              // Hidden on a narrow screen ONLY inside the app, where the model picker needs
              // the room. Everywhere else nothing is competing for it, so hiding the name
              // would just make the bar emptier for no gain.
              inApp && "hidden sm:inline",
            )}
          >
            WinChat
          </span>
        </Link>

        <nav
          aria-label="Primary"
          className="ml-3 hidden items-center gap-4 text-sm sm:flex"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className={cn(
                "hover:text-foreground transition-colors",
                pathname === link.href
                  ? "text-foreground"
                  : "text-muted-foreground",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          {trailing}
          {cta && (
            <Link
              href="/app"
              className="bg-primary text-primary-foreground hidden items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-opacity hover:opacity-90 sm:inline-flex"
            >
              <MessageSquare className="size-3.5" aria-hidden />
              Open WinChat
            </Link>
          )}
          {/* Carries theme, account and sign-out. Previously the landing page had no theme
              control at all, which is a strange thing to discover on a site that has one. */}
          <AccountMenu onSession={setAccessToken} />
        </div>
      </div>
    </header>
  );
}
