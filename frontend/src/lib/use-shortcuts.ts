"use client";

import { useEffect } from "react";

/**
 * Global keyboard shortcuts.
 *
 * Two rules make the difference between shortcuts that help and shortcuts that infuriate:
 *
 * **Never fire while the user is typing into something else.** A bare key handler that
 * hijacks `/` or `?` makes it impossible to type a question containing them — the exact
 * bug that makes people disable shortcuts entirely. Anything originating in an input,
 * textarea or contenteditable is ignored, with one deliberate exception noted below.
 *
 * **Never override the platform.** `Cmd/Ctrl+K` is claimed here because no browser uses
 * it, while `Cmd+L`, `Cmd+T` and `Cmd+W` are the browser's and taking them is hostile.
 */

export interface Shortcuts {
  onNewChat: () => void;
  onStop: () => void;
  onShowHelp: () => void;
  busy: boolean;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
}

export function useShortcuts({
  onNewChat,
  onStop,
  onShowHelp,
  busy,
}: Shortcuts): void {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;

      // Escape while streaming stops the answer — allowed even from the composer, because
      // that is exactly where your hands are when you want to stop, and Escape means
      // "cancel" everywhere else in an interface too.
      if (event.key === "Escape" && busy) {
        event.preventDefault();
        onStop();
        return;
      }

      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onNewChat();
        return;
      }

      // `?` and `/` are ordinary characters in a question, so these only fire outside a
      // text field. The modifier form works anywhere.
      if (meta && event.key === "/") {
        event.preventDefault();
        onShowHelp();
        return;
      }
      if (event.key === "?" && !isTypingTarget(event.target)) {
        event.preventDefault();
        onShowHelp();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onNewChat, onStop, onShowHelp, busy]);
}
