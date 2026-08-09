import type { Metadata } from "next";

import { Credit } from "@/components/Credit";
import { SiteNav } from "@/components/SiteNav";

import { CorpusField } from "@/components/CorpusField";

import { SourcesBrowser } from "@/app/sources/SourcesBrowser";
import { fetchSources } from "@/lib/api/client";
import type { Source } from "@/lib/api/schemas";

/**
 * Every source, listed.
 *
 * This page exists for people first: it is the assistant's complete, checkable boundary.
 * Anyone can see exactly which university articles it can draw on and click through to the
 * original.
 *
 * It happens to be the strongest page on the site for search and AI-answer engines too,
 * because it is a large body of real, structured, link-rich text about a specific domain —
 * rendered on the server, so it is present in the HTML rather than assembled by script.
 */

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "All sources",
  description:
    "Every University of Windsor FAQ article WinChat can answer from, with a direct link to each one on ask.uwindsor.ca.",
  alternates: { canonical: "/sources" },
  openGraph: {
    title: "All sources · WinChat",
    description:
      "The complete list of University of Windsor FAQ articles behind every WinChat answer.",
    url: "/sources",
  },
};

export default async function SourcesPage() {
  let sources: Source[] = [];
  let total = 0;
  let unavailable = false;

  try {
    const response = await fetchSources({ limit: 1000 });
    sources = response.sources;
    total = response.total;
  } catch {
    // A page that renders without the API is better than a build that fails with it. The
    // list is regenerated on the next revalidation.
    unavailable = true;
  }

  return (
    <>
      <SiteNav />
      <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
        <main id="main">
          <header className="mb-8 flex flex-col gap-3">
            <p className="text-gold-foreground flex items-center gap-2.5 text-xs font-medium tracking-[0.14em] uppercase">
              <span aria-hidden className="bg-gold h-px w-8" />
              The complete corpus
            </p>
            {/* The field is the list, drawn. It gives the page an opening image that is
              literally its own content rather than a stock header graphic. */}
            <CorpusField
              fill
              className="text-foreground -mt-1 mb-1 h-14 w-full [mask-image:linear-gradient(to_right,black,transparent_85%)]"
            />
            <h1 className="font-display text-4xl text-balance sm:text-5xl">
              Every source behind WinChat
            </h1>
            <p className="max-w-prose text-[15px] text-muted-foreground text-pretty">
              WinChat answers only from the {total > 0 ? `${total} ` : ""}
              University of Windsor FAQ articles below, and nothing else. Each
              one links to the university&rsquo;s own published page, so you can
              verify any answer at its origin. If a topic isn&rsquo;t on this
              list, WinChat will tell you it doesn&rsquo;t know rather than
              guess.
            </p>
            <p className="text-sm text-muted-foreground">
              Source:{" "}
              <a
                href="https://ask.uwindsor.ca"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 hover:text-foreground"
              >
                ask.uwindsor.ca
              </a>{" "}
              , the University of Windsor&rsquo;s official answer service.
              WinChat is an independent project and is not affiliated with or
              operated by the university.
            </p>
          </header>

          {unavailable ? (
            <p className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
              The source list is temporarily unavailable. Please try again
              shortly.
            </p>
          ) : (
            <SourcesBrowser sources={sources} />
          )}
        </main>

        <footer className="border-border mt-12 border-t pt-6 pb-10 text-center sm:text-left">
          <Credit className="text-muted-foreground text-sm" />
        </footer>
      </div>
    </>
  );
}
