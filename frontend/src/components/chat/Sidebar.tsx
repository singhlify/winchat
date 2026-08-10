"use client";

import {
  Check,
  Library,
  MessageSquare,
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
 * Conversation history. Two presentations of one list.
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
  // Exactly one presentation is mounted at a time. Rendering both and hiding the drawer with
  // `md:hidden` looked right but was not: Sheet portals its overlay as a separate node that
  // the class never reaches, so on desktop an invisible full-screen overlay sat above the
  // page and ate every click.
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
      {/* No wordmark and no spacer. The global nav carries the wordmark, and reserving
          its height here just moved the redundancy from a duplicate label to an empty
          band. "New chat" is the first thing you want in a sidebar, so it goes first. */}
      {/* pt-12 on mobile only. Inside the Sheet the close button sits at the top-right,
          and removing the old header spacer left "New chat" sliding underneath it. On
          desktop there is no Sheet and no close button, so the padding would just be a
          gap. */}
      <div className="px-3 pt-12 pb-2 md:pt-3">
        <Button
          asChild
          variant="outline"
          className="w-full justify-start gap-2"
        >
          <Link href="/app" onClick={onNavigate}>
            <MessageSquarePlus className="size-4" aria-hidden />
            New chat
          </Link>
        </Button>
      </div>

      <nav
        className="min-h-0 flex-1 overflow-y-auto px-2 pb-2"
        aria-label="Previous chats"
      >
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
      // `aria-expanded` carries the state and the label says what the control does. No
      // `aria-controls`: the element it would reference differs between the desktop column
      // and the mobile drawer, and would sometimes resolve to a hidden node.
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
        href={`/app/c/${conversation.id}`}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex min-h-11 items-center rounded-md py-2 pr-10 pl-2 text-sm transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          active && "bg-accent font-medium",
        )}
      >
        {/* A leading glyph gives the eye a fixed left edge to scan down, so titles of
            different lengths still read as one column rather than ragged text. */}
        <MessageSquare
          className="mr-2 size-4 shrink-0 text-muted-foreground"
          aria-hidden
        />
        <span className="truncate">{conversation.title}</span>
      </Link>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Options for ${conversation.title}`}
            // 36px and always visible on touch. WCAG 2.5.8 asks for at least 24x24, and
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
          <DropdownMenuItem
            onSelect={remove}
            variant="destructive"
            className="gap-2"
          >
            <Trash2 className="size-3.5" aria-hidden />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}
