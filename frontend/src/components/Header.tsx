"use client";

import { PenSquare } from "lucide-react";

import { AuthPanel } from "@/components/AuthPanel";
import { ModelPicker } from "@/components/ModelPicker";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function Header({
  onSession,
  model,
  onModelChange,
  onNewChat,
  sidebarOpen,
}: {
  onSession: (token: string | null) => void;
  model: string | null;
  onModelChange: (model: string | null) => void;
  onNewChat?: () => void;
  sidebarOpen?: boolean;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-2 px-4 py-2.5 sm:px-6">
        {/* Leaves room for the floating sidebar toggle when the sidebar is hidden. */}
        {!sidebarOpen && <span className="w-9 shrink-0" aria-hidden />}

        <span className="truncate text-sm text-muted-foreground">
          UWindsor FAQ, answered with sources
        </span>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          {onNewChat && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onNewChat}
                  aria-label="New chat"
                  className="size-9"
                >
                  <PenSquare className="size-4" aria-hidden />
                </Button>
              </TooltipTrigger>
              <TooltipContent>New chat</TooltipContent>
            </Tooltip>
          )}

          <ModelPicker value={model} onChange={onModelChange} />
          <ThemeToggle />
          <AuthPanel onSession={onSession} />
        </div>
      </div>
    </header>
  );
}
