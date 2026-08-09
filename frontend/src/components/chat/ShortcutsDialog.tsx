"use client";

import { useEffect, useRef } from "react";

const SHORTCUTS = [
  { keys: ["⌘", "K"], label: "New chat" },
  { keys: ["Enter"], label: "Send message" },
  { keys: ["Shift", "Enter"], label: "New line" },
  { keys: ["Esc"], label: "Stop generating" },
  { keys: ["⌘", "/"], label: "Show this list" },
];

/**
 * The shortcut list, shown on ⌘/ or ?.
 *
 * A real `<dialog>` rather than a hand-rolled overlay: the browser gives focus trapping,
 * Escape-to-close, inertness of the page behind, and the top-layer stacking that otherwise
 * needs a z-index nobody can reason about. Reimplementing those in React is how modals
 * end up subtly inaccessible.
 *
 * `⌘` is displayed for everyone. Detecting the platform to swap in `Ctrl` reads the user
 * agent, which is unreliable, and the handler accepts either key regardless — so the label
 * is a hint, not a contract.
 */
export function ShortcutsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    // showModal() is what puts it in the top layer and makes the rest of the page inert;
    // toggling the `open` attribute directly does neither.
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // Escape already closes a modal dialog; this catches the click-outside case, which
      // lands on the dialog element itself rather than its contents.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      aria-labelledby="shortcuts-title"
      className="m-auto rounded-xl border border-border bg-background p-0 text-foreground backdrop:bg-black/40"
    >
      <div className="w-80 p-5">
        <h2 id="shortcuts-title" className="text-sm font-medium">
          Keyboard shortcuts
        </h2>
        <dl className="mt-4 flex flex-col gap-2.5">
          {SHORTCUTS.map((shortcut) => (
            <div
              key={shortcut.label}
              className="flex items-center justify-between gap-4"
            >
              <dt className="text-sm text-muted-foreground">
                {shortcut.label}
              </dt>
              <dd className="flex gap-1">
                {shortcut.keys.map((key) => (
                  <kbd
                    key={key}
                    className="rounded border border-border bg-muted px-1.5 py-0.5 font-sans text-xs"
                  >
                    {key}
                  </kbd>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </dialog>
  );
}
