/**
 * The maker's credit.
 *
 * One component so the wording and the link live in a single place. A credit line that has
 * drifted into three slightly different versions across a site is the kind of detail people
 * do notice.
 *
 * The link is deliberately not `nofollow`: it points at the author's own site, and a real
 * backlink from a working project is worth having.
 */
export function Credit({ className }: { className?: string }) {
  return (
    <span className={className}>
      Built in Windsor by{" "}
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
