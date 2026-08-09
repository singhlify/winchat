/**
 * The WinChat mark: a speech bubble with a W knocked out of it.
 *
 * Inlined as JSX rather than referenced as an `<img src>` because `currentColor` cannot
 * cross an image boundary. An `<img>` is its own document, so a `text-primary` class on
 * the element styles nothing inside it, and the mark rendered flat black regardless of
 * theme. Inline, it inherits colour like any other glyph and follows dark mode for free.
 *
 * No background plate: the shape IS the logo. A coloured square behind it would be the
 * app-icon treatment, which belongs on a home screen and nowhere in the interface.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="112 136 288 288"
      className={className}
      role="img"
      aria-label="WinChat"
    >
      <path
        d="M 160 152 h 192 c 26.5 0 48 21.5 48 48 v 96 c 0 26.5 -21.5 48 -48 48 h -112 l -48 48 v -48 h -32 c -26.5 0 -48 -21.5 -48 -48 v -96 c 0 -26.5 21.5 -48 48 -48 z"
        fill="currentColor"
      />
      {/* The W is cut out of the bubble, so it takes the page background rather than a
          hardcoded white, which would show as a light smear in dark mode. */}
      <path
        d="M 188 212 l 28 72 l 40 -48 l 40 48 l 28 -72"
        fill="none"
        stroke="var(--background)"
        strokeWidth="26"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
