"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

/**
 * Light / dark / system.
 *
 * Three options rather than a two-state switch: "system" is what most people actually
 * want, and a binary toggle silently opts them out of their OS preference the first time
 * they touch it.
 *
 * The trigger icon is swapped in CSS by the `dark:` variant rather than from JavaScript
 * state. The resolved theme is genuinely unknowable during server rendering — it depends
 * on localStorage and a media query — so any JS-driven icon needs a `mounted` guard, which
 * means an effect that immediately sets state. Letting CSS do it sidesteps the hydration
 * problem rather than papering over it, and the correct icon is right on first paint.
 *
 * The menu items may read `theme` freely: the content only mounts once opened, which is
 * necessarily after hydration.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-9" aria-label="Change theme">
          <Sun className="size-4 dark:hidden" aria-hidden />
          <Moon className="hidden size-4 dark:block" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onSelect={() => setTheme(option.value)}
            className="gap-2"
          >
            <option.icon className="size-4" aria-hidden />
            {option.label}
            {theme === option.value && <Check className="ml-auto size-3.5" aria-hidden />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
