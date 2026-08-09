"use client";

import { ArrowUp, Square } from "lucide-react";

import { Credit } from "@/components/Credit";
import { useEffect, useImperativeHandle, useRef, type Ref } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const MAX_LENGTH = 2000;
const MAX_ROWS_HEIGHT = 200;

export interface ComposerHandle {
  focus: () => void;
  setValue: (value: string) => void;
}

/**
 * The input.
 *
 * A textarea, not an input: real questions wrap, and a single-line field that scrolls
 * sideways hides what you typed. Enter sends and Shift+Enter adds a newline — the
 * convention every chat app shares, so breaking it would be its own bug.
 *
 * Height grows with content up to a cap, then scrolls. Without the cap a pasted essay
 * pushes the send button off-screen on a phone.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  busy,
  ref,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  busy: boolean;
  ref?: Ref<ComposerHandle>;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    setValue: (next: string) => {
      onChange(next);
      textareaRef.current?.focus();
    },
  }));

  // Autosize. Reset to auto first or the box can only ever grow.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_ROWS_HEIGHT)}px`;
  }, [value]);

  const remaining = MAX_LENGTH - value.length;
  const nearLimit = remaining <= 200;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      className="relative"
    >
      <div className="flex items-end gap-2 rounded-2xl border border-input bg-background p-2 shadow-sm transition-colors focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/25">
        <label htmlFor="composer" className="sr-only">
          Ask a question about the University of Windsor
        </label>
        <textarea
          id="composer"
          ref={textareaRef}
          rows={1}
          value={value}
          maxLength={MAX_LENGTH}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              onSubmit();
            }
            // Backspace deliberately does NOTHING special here. An earlier version used
            // empty-box Backspace to pull the last exchange back for editing, borrowing a
            // terminal reflex. In a chat it is destructive and unprompted: the most-pressed
            // key on the keyboard silently deleted a question and its answer. Undo stays
            // available as an explicit control.
          }}
          placeholder="Ask a question…"
          aria-describedby="composer-hint"
          // text-base (16px) on mobile, NOT the 15px this used to be. iOS Safari zooms the
          // whole page when a focused input is under 16px — so tapping the composer, the
          // single most-used control in the app, threw the layout out on every iPhone. The
          // shadcn Input and Textarea already do this; the chat composer did not.
          className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-1.5 text-base leading-relaxed outline-none placeholder:text-muted-foreground/70 sm:text-[15px]"
        />

        {busy ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="secondary"
                onClick={onStop}
                aria-label="Stop generating"
                className="size-11 shrink-0 rounded-xl sm:size-9"
              >
                <Square className="size-3.5 fill-current" aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Stop generating</TooltipContent>
          </Tooltip>
        ) : (
          <Button
            type="submit"
            size="icon"
            disabled={value.trim().length === 0}
            aria-label="Send question"
            className="size-11 shrink-0 rounded-xl sm:size-9"
          >
            <ArrowUp className="size-4" aria-hidden />
          </Button>
        )}
      </div>

      {/* The model picker lives here, not in the top bar.
       *
       * It was in the nav, where it had no room at 390px and was hidden outright — so on a
       * phone there was no way to choose a model at all. Beside the composer it is visible
       * at every width and sits next to the thing it actually governs: the message you are
       * about to send. That is where every major chat UI puts it, and the reason is the same.
       *
       * Not the sidebar, which would hide it behind a drawer on exactly the devices that
       * had the problem. */}
      <div
        id="composer-hint"
        className="mt-1.5 flex items-center justify-between gap-2 px-1 text-[11px] text-muted-foreground"
      >
        {/* The name contains "Win", which reads as Windsor, so independence has to be
            stated where people actually look — not in a footer nobody scrolls to. This
            sits under the composer, the one element present on every screen. */}

        <span className="hidden shrink-0 sm:inline">
          <kbd className="rounded border border-border px-1 py-px font-sans">
            Enter
          </kbd>{" "}
          to send
        </span>
        {/* Only shown when it starts to matter — a permanent counter is noise. */}
        {nearLimit && (
          <span
            aria-live="polite"
            className={remaining < 0 ? "text-destructive" : undefined}
          >
            {remaining} characters left
          </span>
        )}
      </div>

      {/* Its own quiet line, so a credit never competes with a control for the same row. */}
      <p className="text-muted-foreground mt-1 px-1 text-center text-[11px]">
        <Credit />
      </p>
    </form>
  );
}
