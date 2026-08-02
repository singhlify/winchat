"use client";

import {
  Check,
  Library,
  MessageSquarePlus,
  MoreHorizontal,
  PanelLeft,
  Pencil,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  removeConversation,
  renameConversation,
  useConversations,
  type Conversation,
} from "@/lib/conversations";
import { cn } from "@/lib/utils";

/**
 * Conversation history.
 *
 * Two presentations of one list. On desktop it is a static column; on mobile it is a modal
 * drawer built on Sheet (Radix Dialog), which brings focus trapping, Escape-to-close,
 * background scroll lock and `aria-modal` — everything a hand-rolled overlay has to
 * reimplement and usually gets wrong.
 *
 * An earlier version used one translating `<aside>` for both and put the re-open control
 * in a floating button. That button shared a stacking context with the sticky header and
 * lost, so on mobile there was no way to open the sidebar at all. The control now lives in
 * the header at every breakpoint, where it cannot be occluded and is in a predictable
 * place — see `Header`.
 */
export function Sidebar({
  open,
  onClose,
  isDesktop,
}: {
  open: boolean;
  onClose: () => void;
  isDesktop: boolean;
}) {
  // Exactly one presentation is mounted at a time. Rendering both and hiding the drawer
  // with `md:hidden` looked right but was not: Sheet portals its overlay as a separate
  // node that the class never reaches, so on desktop an invisible full-screen overlay sat
  // above the page and ate every click.
  if (isDesktop) {
    return (
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-border/60 bg-card transition-[width] duration-200 motion-reduce:transition-none",
          open ? "w-72" : "w-0 overflow-hidden border-r-0",
        )}
        aria-label="Chat history"
      >
        {open && <SidebarContent onNavigate={() => undefined} />}
      </aside>
    );
  }

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="left" className="w-[85vw] max-w-80 p-0">
        {/* Radix requires an accessible name for the dialog. Visually hidden because the
            list below is self-evident on screen. */}
        <SheetTitle className="sr-only">Chat history</SheetTitle>
        <SidebarContent onNavigate={onClose} />
      </SheetContent>
    </Sheet>
  );
}

function SidebarContent({ onNavigate }: { onNavigate: () => void }) {
  const conversations = useConversations();

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="flex items-center gap-2 px-3 py-3">
        <span className="text-sm font-semibold tracking-tight">WinChat</span>
      </div>

      <div className="px-3 pb-2">
        <Button asChild variant="outline" className="w-full justify-start gap-2">
          <Link href="/" onClick={onNavigate}>
            <MessageSquarePlus className="size-4" aria-hidden />
            New chat
          </Link>
        </Button>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2" aria-label="Previous chats">
        {conversations.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">
            Your chats are saved in this browser and appear here.
          </p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {conversations.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                onNavigate={onNavigate}
              />
            ))}
          </ul>
        )}
      </nav>

      <div className="border-t border-border/60 p-2">
        <Button
          asChild
          variant="ghost"
          className="w-full justify-start gap-2 text-muted-foreground"
        >
          <Link href="/sources" onClick={onNavigate}>
            <Library className="size-4" aria-hidden />
            All sources
          </Link>
        </Button>
      </div>
    </div>
  );
}

/** The header's toggle. Exported so the control lives with the header, not floating. */
export function SidebarToggle({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onToggle}
      // `aria-expanded` conveys the state; the label says what it does. No `aria-controls`
      // on purpose — the element it would reference differs between the desktop column and
      // the mobile drawer, and a reference that resolves to a hidden node is worse than none.
      aria-expanded={open}
      aria-label={open ? "Hide chat history" : "Show chat history"}
      className="size-9 shrink-0"
    >
      <PanelLeft className="size-4" aria-hidden />
    </Button>
  );
}

function ConversationRow({
  conversation,
  onNavigate,
}: {
  conversation: Conversation;
  onNavigate: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(conversation.title);
  const inputRef = useRef<HTMLInputElement>(null);

  const active = pathname === `/c/${conversation.id}`;

  useEffect(() => {
    if (renaming) inputRef.current?.select();
  }, [renaming]);

  function commit() {
    renameConversation(conversation.id, draft);
    setRenaming(false);
  }

  function remove() {
    removeConversation(conversation.id);
    // Deleting the chat you are reading must not leave you on a dead route.
    if (active) router.push("/");
  }

  if (renaming) {
    return (
      <li>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            commit();
          }}
          className="flex items-center gap-1 px-1"
        >
          <input
            ref={inputRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setDraft(conversation.title);
                setRenaming(false);
              }
            }}
            aria-label="Chat title"
            className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring"
          />
          <Button
            type="submit"
            variant="ghost"
            size="icon"
            className="size-9"
            aria-label="Save title"
          >
            <Check className="size-3.5" aria-hidden />
          </Button>
        </form>
      </li>
    );
  }

  return (
    <li className="group/row relative">
      <Link
        href={`/c/${conversation.id}`}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex min-h-11 items-center rounded-md py-2 pr-10 pl-2 text-sm transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          active && "bg-accent font-medium",
        )}
      >
        <span className="truncate">{conversation.title}</span>
      </Link>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Options for ${conversation.title}`}
            // 36px and always visible on touch — WCAG 2.5.8 asks for at least 24x24, and
            // a control revealed only on hover is unreachable on a phone.
            className="absolute top-1/2 right-1 size-9 -translate-y-1/2 md:opacity-0 md:group-focus-within/row:opacity-100 md:group-hover/row:opacity-100"
          >
            <MoreHorizontal className="size-3.5" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              setDraft(conversation.title);
              setRenaming(true);
            }}
            className="gap-2"
          >
            <Pencil className="size-3.5" aria-hidden />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={remove} variant="destructive" className="gap-2">
            <Trash2 className="size-3.5" aria-hidden />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}
