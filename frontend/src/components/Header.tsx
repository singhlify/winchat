"use client";

import { Library, PenSquare } from "lucide-react";
import Link from "next/link";

import { AuthPanel } from "@/components/AuthPanel";
import { ModelPicker } from "@/components/ModelPicker";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function Header({
  onSession,
  model,
  onModelChange,
  onNewChat,
}: {
  onSession: (token: string | null) => void;
  model: string | null;
  onModelChange: (model: string | null) => void;
  onNewChat?: () => void;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-2 px-4 py-2.5 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-lg bg-primary text-[13px] font-bold text-primary-foreground"
          >
            W
          </span>
          <span className="font-semibold tracking-tight">WinChat</span>
        </Link>

        <span className="hidden text-xs text-muted-foreground sm:inline">
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

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" asChild className="size-9">
                <Link href="/sources" aria-label="Browse all sources">
                  <Library className="size-4" aria-hidden />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Browse all sources</TooltipContent>
          </Tooltip>

          <ModelPicker value={model} onChange={onModelChange} />
          <AuthPanel onSession={onSession} />
        </div>
      </div>
    </header>
  );
}
