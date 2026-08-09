import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * The sitemap lists only pages that exist on this site. It deliberately does NOT enumerate
 * the 556 ask.uwindsor.ca articles.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    { url: SITE_URL, lastModified, changeFrequency: "weekly", priority: 1 },
    // /app is deliberately absent: it is an interactive client shell with nothing for a
    // crawler to read, and the landing page is what should rank for the same intent.
    {
      url: `${SITE_URL}/sources`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.8,
    },
  ];
}
