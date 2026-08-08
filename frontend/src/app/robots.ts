import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * Crawler policy.
 *
 * AI crawlers are allowed. That is a deliberate choice, not an oversight: this site's
 * purpose is to help people find University of Windsor answers, and being readable by the
 * assistants people increasingly ask serves that. There is nothing here worth withholding
 * — the underlying content is the university's own public FAQ.
 *
 * Honesty about the limits of this file: whether allowing a given AI crawler affects
 * whether a model cites you is NOT something this project has evidence for. The research
 * pass commissioned for exactly this question produced no claims that survived
 * verification. So this file does the one thing that is unambiguously true — it does not
 * block anyone — and makes no claim beyond that.
 *
 * `/status` is excluded because it is an operational page, not content, and indexing it
 * would put dependency health in search results. `/auth/*` is excluded because those pages
 * exist only as landing targets for a link in an email or from an OAuth provider — they
 * render nothing without one, so an indexed copy is a dead end for a searcher and a
 * password form sitting in search results for everyone else.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/status", "/auth/"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
