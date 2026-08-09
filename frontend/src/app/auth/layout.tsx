import type { Metadata } from "next";

/**
 * A server component wrapping the two client pages under /auth, for one reason: metadata.
 * `robots.txt` only *asks* crawlers not to fetch a path, and the pages themselves are client
 * components, which cannot export `metadata`.
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
