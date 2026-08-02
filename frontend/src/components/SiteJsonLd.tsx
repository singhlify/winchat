/**
 * Structured data (JSON-LD).
 *
 * Machine-readable statements of what this site is, who publishes it and what it covers.
 * Search engines use it for entity understanding, and answer engines increasingly read it
 * when deciding what a page is authoritative about.
 *
 * A Server Component, so the markup is in the initial HTML rather than injected by script
 * — a crawler that does not execute JavaScript would otherwise never see it.
 *
 * `JSON.stringify` output is escaped before it reaches `dangerouslySetInnerHTML`: a `<`
 * inside a string would otherwise let content close the script tag early. Every value here
 * is currently a literal, but the escape stays because the next person to add a dynamic
 * field should not have to rediscover why it matters.
 */

function serialize(payload: unknown): string {
  return JSON.stringify(payload).replace(/</g, "\\u003c");
}

export function SiteJsonLd({ siteUrl, description }: { siteUrl: string; description: string }) {
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${siteUrl}/#website`,
        url: siteUrl,
        name: "WinChat",
        description,
        inLanguage: "en-CA",
        isAccessibleForFree: true,
      },
      {
        "@type": "WebApplication",
        "@id": `${siteUrl}/#app`,
        name: "WinChat",
        url: siteUrl,
        applicationCategory: "EducationalApplication",
        operatingSystem: "Any (web browser)",
        browserRequirements: "Requires JavaScript",
        description,
        inLanguage: "en-CA",
        isAccessibleForFree: true,
        offers: { "@type": "Offer", price: "0", priceCurrency: "CAD" },
        // The corpus this assistant answers from, stated explicitly. It is the honest
        // description of scope, and it attributes the underlying content to the
        // university rather than implying we authored it.
        isBasedOn: {
          "@type": "WebSite",
          name: "ask.uwindsor.ca — University of Windsor answer service",
          url: "https://ask.uwindsor.ca",
        },
        about: {
          "@type": "CollegeOrUniversity",
          name: "University of Windsor",
          url: "https://www.uwindsor.ca",
          address: {
            "@type": "PostalAddress",
            addressLocality: "Windsor",
            addressRegion: "ON",
            addressCountry: "CA",
          },
        },
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: serialize(graph) }}
    />
  );
}
