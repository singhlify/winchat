"use client";

import { Check, Library, MessageSquarePlus, MoreHorizontal, PanelLeft, Pencil, Trash2, X } from "lucide-react";
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
import {
  removeConversation,
  renameConversation,
  useConversations,
  type Conversation,
} from "@/lib/conversations";
import { cn } from "@/lib/utils";

/**
 * Conversation list.
 *
 * One component serves both layouts: a permanent column from `md` up, and an overlay
 * drawer below it. Two separate implementations would drift, and the drawer is the same
 * list with different chrome.
 */
export function Sidebar({
  open,
  onClose,
  onOpen,
}: {
  open: boolean;
  onClose: () => void;
  onOpen: () => void;
}) {
  const conversations = useConversations();

  return (
    <>
      {/* Mobile: dim the page behind the drawer and make the backdrop a dismiss target. */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        // `hidden`/`md:flex` rather than unmounting: the desktop column is always present,
        // and only the mobile drawer slides.
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-border/60 bg-card transition-transform duration-200 motion-reduce:transition-none md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Chat history"
      >
        <div className="flex items-center gap-2 px-3 py-2.5">
          <Button
            variant="ghost"
            size="icon"
            className="size-9 md:hidden"
            onClick={onClose}
            aria-label="Close chat history"
          >
            <X className="size-4" aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="hidden size-9 md:inline-flex"
            onClick={onClose}
            aria-label="Hide chat history"
          >
            <PanelLeft className="size-4" aria-hidden />
          </Button>
          <span className="text-sm font-semibold tracking-tight">WinChat</span>
        </div>

        <div className="px-3 pb-2">
          <Button asChild variant="outline" className="w-full justify-start gap-2">
            <Link href="/" onClick={onClose}>
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
                  onNavigate={onClose}
                />
              ))}
            </ul>
          )}
        </nav>

        <div className="border-t border-border/60 p-2">
          <Button asChild variant="ghost" className="w-full justify-start gap-2 text-muted-foreground">
            <Link href="/sources" onClick={onClose}>
              <Library className="size-4" aria-hidden />
              All sources
            </Link>
          </Button>
        </div>
      </aside>

      {/* Re-open control, shown only when the sidebar is hidden. */}
      {!open && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpen}
          aria-label="Show chat history"
          className="fixed top-2.5 left-3 z-20 size-9 md:absolute"
        >
          <PanelLeft className="size-4" aria-hidden />
        </Button>
      )}
    </>
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
          <Button type="submit" variant="ghost" size="icon" className="size-8" aria-label="Save title">
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
          "flex min-h-9 items-center rounded-md py-2 pr-9 pl-2 text-sm transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
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
            className="absolute top-1/2 right-1 size-7 -translate-y-1/2 opacity-100 md:opacity-0 md:group-focus-within/row:opacity-100 md:group-hover/row:opacity-100"
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
