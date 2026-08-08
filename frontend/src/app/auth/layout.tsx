import type { Metadata } from "next";

/**
 * A server component wrapping the two client pages under /auth, for one reason: metadata.
 *
 * `robots.txt` only *asks* crawlers not to fetch a path, and the pages themselves are
 * client components, which cannot export `metadata`. This layout emits a real `noindex`
 * tag, so a crawler that ignores robots.txt — or that reached the page from a link rather
 * than a crawl — still gets an unambiguous instruction.
 *
 * Both pages are landing targets for a link in an email or from an OAuth provider. They
 * render nothing useful without one, so an indexed copy is a dead end for a searcher, and
 * a password form in search results is worse than useless for everyone else.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
