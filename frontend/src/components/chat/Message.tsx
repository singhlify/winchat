"use client";

import {
  AlertTriangle,
  Check,
  Copy,
  Pencil,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/chat/Markdown";
import { SourceLink, SourcePanel } from "@/components/chat/SourcePanel";
import type { Turn } from "@/components/chat/use-chat";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function UserMessage({
  content,
  onEdit,
}: {
  content: string;
  onEdit?: () => void;
}) {
  const reveal =
    "opacity-100 transition-opacity sm:opacity-0 sm:group-focus-within/message:opacity-100 sm:group-hover/message:opacity-100";

  return (
    // `group/message` + the button's opacity rules mean the controls appear on hover for
    // pointer users and are always present on touch, where there is no hover to reveal it.
    <li className="group/message flex items-center justify-end gap-1">
      {onEdit && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onEdit}
              aria-label="Edit this question"
              className={cn("size-8 text-muted-foreground", reveal)}
            >
              <Pencil className="size-3.5" aria-hidden />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Edit</TooltipContent>
        </Tooltip>
      )}
      <CopyButton text={content} label="Copy your message" className={reveal} />
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-foreground sm:max-w-[75%]">
        <p className="text-[15px] leading-relaxed whitespace-pre-wrap">
          {content}
        </p>
      </div>
    </li>
  );
}

/**
 * Copy-to-clipboard, shared by both message kinds.
 *
 * The confirmation is the icon swapping to a tick for a moment — no toast. A toast for
 * something the user just did, whose result is obvious, is noise.
 */
function CopyButton({
  text,
  label,
  className,
}: {
  text: string;
  label: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1600);
    // Cleared on unmount so the timer cannot fire into an unmounted component.
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // The Clipboard API needs a secure context and can be denied. Silently doing
      // nothing beats an error dialog for a convenience action.
    }
  }

  return (
    <IconAction
      label={copied ? "Copied" : label}
      onClick={() => void copy()}
      className={className}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </IconAction>
  );
}

export function AssistantMessage({
  turn,
  isLast,
  onRetry,
  onRate,
}: {
  turn: Turn;
  isLast: boolean;
  onRetry: () => void;
  onRate: (vote: "up" | "down") => void;
}) {
  return (
    <li className="group/message">
      {turn.error ? (
        <ErrorState turn={turn} onRetry={onRetry} />
      ) : turn.refused ? (
        <RefusalState turn={turn} />
      ) : turn.content ? (
        <Markdown citations={turn.citations}>{turn.content}</Markdown>
      ) : (
        <PendingState hasSources={turn.citations.length > 0} />
      )}

      {!turn.refused && !turn.error && turn.content && (
        <SourcePanel answer={turn.content} citations={turn.citations} />
      )}

      {!turn.streaming && !turn.error && turn.content && (
        <MessageActions
          turn={turn}
          isLast={isLast}
          onRetry={onRetry}
          onRate={onRate}
        />
      )}
    </li>
  );
}

/**
 * A refusal is a calm, informative state — not an error.
 *
 * Styling correct behaviour in red teaches people to distrust the system precisely when it
 * is being most trustworthy. The closest articles are shown because a bare "no results" is
 * indistinguishable from a broken search, and the actual score is shown because this is a
 * portfolio piece where the mechanism is part of the point.
 */
function RefusalState({ turn }: { turn: Turn }) {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-50/60 p-4 dark:bg-amber-950/20">
      <p className="text-[15px] leading-relaxed text-amber-950 dark:text-amber-100">
        {turn.content}
      </p>

      {turn.nearMisses.length > 0 && (
        <div className="mt-3">
          <h3 className="mb-1 text-xs font-medium tracking-wide text-amber-900/70 uppercase dark:text-amber-200/60">
            Closest articles found
          </h3>
          <ul className="flex flex-col gap-0.5">
            {turn.nearMisses.map((citation) => (
              <SourceLink key={citation.a_id} citation={citation} muted />
            ))}
          </ul>
        </div>
      )}

      {turn.refusal && (
        <p className="mt-3 font-mono text-[11px] text-amber-800/60 dark:text-amber-200/40">
          best match {turn.refusal.score} · answers below{" "}
          {turn.refusal.threshold} are not used
        </p>
      )}
    </div>
  );
}

function ErrorState({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  return (
    // No role="alert" here on purpose. This node mounts only when an error occurs, and a
    // live region that appears at the same moment as its content is not reliably announced.
    // The persistent alert region in Chat.tsx does the announcing; this is the visual half.
    <div className="flex flex-col gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <p className="flex items-start gap-2 text-sm text-foreground">
        <AlertTriangle
          className="mt-0.5 size-4 shrink-0 text-destructive"
          aria-hidden
        />
        <span>{turn.error}</span>
      </p>
      {turn.retryAfterSeconds != null && (
        <p className="pl-6 text-xs text-muted-foreground">
          You can try again in about {Math.ceil(turn.retryAfterSeconds / 60)}{" "}
          minute
          {turn.retryAfterSeconds >= 120 ? "s" : ""}.
        </p>
      )}
      <div className="pl-6">
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCcw className="size-3.5" aria-hidden />
          Try again
        </Button>
      </div>
    </div>
  );
}

/**
 * The wait has two distinct stages and says which one it is in. "Searching" then "Writing"
 * tells the user the system is progressing rather than hung — and the two stages are real,
 * because sources arrive as their own event before the first token.
 */
function PendingState({ hasSources }: { hasSources: boolean }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="size-1.5 animate-pulse rounded-full bg-current motion-reduce:animate-none"
            style={{ animationDelay: `${dot * 150}ms` }}
          />
        ))}
      </span>
      {hasSources ? "Reading the sources…" : "Searching the FAQ…"}
    </p>
  );
}

function MessageActions({
  turn,
  isLast,
  onRetry,
  onRate,
}: {
  turn: Turn;
  isLast: boolean;
  onRetry: () => void;
  onRate: (vote: "up" | "down") => void;
}) {
  return (
    // Visible on hover for pointer users, but always reachable by keyboard and always
    // visible on touch, where there is no hover to reveal them.
    <div className="mt-2 flex items-center gap-0.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/message:opacity-100 sm:focus-within:opacity-100">
      <CopyButton text={turn.content} label="Copy answer" />

      {isLast && (
        <IconAction label="Regenerate answer" onClick={onRetry}>
          <RotateCcw className="size-3.5" />
        </IconAction>
      )}

      <span className="mx-1 h-4 w-px bg-border" aria-hidden />

      <IconAction
        label="Good answer"
        pressed={turn.feedback === "up"}
        onClick={() => onRate("up")}
      >
        <ThumbsUp className="size-3.5" />
      </IconAction>
      <IconAction
        label="Bad answer"
        pressed={turn.feedback === "down"}
        onClick={() => onRate("down")}
      >
        <ThumbsDown className="size-3.5" />
      </IconAction>

      {turn.model && (
        <span className="ml-1 truncate font-mono text-[11px] text-muted-foreground/60">
          {turn.model}
        </span>
      )}
    </div>
  );
}

function IconAction({
  label,
  onClick,
  pressed,
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  pressed?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        onClick={onClick}
        aria-label={label}
        aria-pressed={pressed}
        className={cn(
          "inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          pressed && "bg-muted text-foreground",
          className,
        )}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
