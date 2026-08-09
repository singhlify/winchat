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
 * The top bar. Deliberately close to every major chat UI's, because that layout is now what
 * people expect and expectation is most of what makes an interface feel effortless.
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
          {/* Desktop docks the sidebar permanently, so its "New chat" is always visible and
              a second one here is pure duplication. On mobile the sidebar is a drawer, so
              removing this would put the most frequent action in the app behind an extra
              tap. Hidden from md: up rather than deleted. */}
          {onNewChat && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onNewChat}
                  aria-label="New chat"
                  className="size-9 md:hidden"
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
