"use client";

import { PenSquare } from "lucide-react";

import { SidebarToggle } from "@/components/chat/Sidebar";

import { ModelPicker } from "@/components/ModelPicker";
import { SiteNav } from "@/components/SiteNav";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * The top bar.
 *
 * Deliberately close to every major chat UI's, because that layout is now what people
 * expect and expectation is most of what makes an interface feel effortless. Both put
 * almost nothing up here: navigation on the far left, the one thing you might change about
 * the current conversation next to it, and everything else — theme, account, sign-out —
 * folded behind a single control on the right.
 *
 * The previous version had five siblings competing on the right (new chat, model picker,
 * theme toggle, sign-in, email). Each was individually reasonable; together they read as a
 * toolbar, which makes the page feel like software to be configured rather than a box to
 * type in. What moved is only the rarely-used: the model picker stayed visible because it
 * changes the answer you are about to get, which is a property of this conversation rather
 * than a preference.
 */
export function Header({
  model,
  onModelChange,
  onNewChat,
  sidebarOpen,
  onToggleSidebar,
}: {
  model: string | null;
  onModelChange: (model: string | null) => void;
  onNewChat?: () => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}) {
  return (
    <SiteNav
      // No "Open WinChat" here: it would point at the page you are already on.
      cta={false}
      trailing={<ModelPicker value={model} onChange={onModelChange} />}
      leading={
        <>
          <SidebarToggle open={sidebarOpen} onToggle={onToggleSidebar} />
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
        </>
      }
    />
  );
}
