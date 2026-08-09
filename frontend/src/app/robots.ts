import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * Crawler policy. AI crawlers are allowed.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/", // /api is listed for tidiness rather than defence. Crawlers issue GET and would get
        // nothing useful; the actual guard is the Origin check plus the rate limiter.
        disallow: ["/status", "/auth/", "/api/", "/offline"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
