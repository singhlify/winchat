/**
 * The maker's credit. One component so the wording and the link live in a single place.
 */
export function Credit({ className }: { className?: string }) {
  return (
    <span className={className}>
      Designed and built by{" "}
      <a
        href="https://singhlify.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-foreground underline underline-offset-2 transition-colors"
      >
        singhlify
      </a>
    </span>
  );
}
