"use client";

import { Check, LogOut, Monitor, Moon, Sun, User } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { AuthPanel } from "@/components/AuthPanel";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { signOut } from "@/lib/auth";
import { authConfigured, getSupabase } from "@/lib/supabase";

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

/**
 * One control on the right of the header, holding everything that is a preference rather than
 * part of the conversation: theme, account, sign-out, and the links off to sources. This is
 * the pattern every major chat UI uses, and the reason it works is subtraction.
 */
export function AccountMenu({
  onSession,
}: {
  onSession: (token: string | null) => void;
}) {
  const { theme, setTheme } = useTheme();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    void supabase.auth.getSession().then(({ data }) => {
      setEmail(data.session?.user.email ?? null);
      onSession(data.session?.access_token ?? null);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user.email ?? null);
      onSession(session?.access_token ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, [onSession]);

  // Signed out with auth available: show the sign-in panel, which carries its own guest path.
  // Auth unconfigured: this still renders, because theme and the source links are useful with
  // or without accounts.
  if (authConfigured && !email) {
    return <AuthPanel onSession={onSession} />;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-9"
          aria-label={email ? `Account: ${email}` : "Settings"}
        >
          <User className="size-4" aria-hidden />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        {email && (
          <>
            <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
              {email}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
          </>
        )}

        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            {/* Icon swapped by CSS rather than JS: the resolved theme is unknowable during
                server rendering, so a JS-driven icon needs a mounted guard and flickers. */}
            <Sun className="mr-2 size-4 dark:hidden" aria-hidden />
            <Moon className="mr-2 hidden size-4 dark:block" aria-hidden />
            Theme
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {THEMES.map((option) => (
              <DropdownMenuItem
                key={option.value}
                onClick={() => setTheme(option.value)}
              >
                <option.icon className="mr-2 size-4" aria-hidden />
                {option.label}
                {theme === option.value && (
                  <Check className="ml-auto size-4" aria-hidden />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        {email && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => void signOut()}>
              <LogOut className="mr-2 size-4" aria-hidden />
              Sign out
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
