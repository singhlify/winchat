import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";

import "./globals.css";
import { Providers } from "@/app/providers";
import { SiteJsonLd } from "@/components/SiteJsonLd";
import { cn } from "@/lib/utils";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const TITLE = "WinChat — University of Windsor FAQ, answered with sources";
const DESCRIPTION =
  "Ask about University of Windsor admissions, tuition, courses, UWinsite and campus services. Every answer is drawn from the university's own published FAQ articles and links back to them.";

/**
 * `metadataBase` is what turns the relative OG and canonical URLs below into absolute
 * ones. Without it Next emits relative image URLs, which crawlers and social scrapers
 * silently drop — the most common reason link previews come out blank.
 */
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: TITLE, template: "%s — WinChat" },
  description: DESCRIPTION,
  applicationName: "WinChat",
  keywords: [
    "University of Windsor",
    "UWindsor FAQ",
    "UWinsite Student",
    "UWin account",
    "UWindsor admissions",
    "UWindsor tuition",
    "ask.uwindsor.ca",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "WinChat",
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
    locale: "en_CA",
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-snippet": -1, "max-image-preview": "large" },
  },
  category: "education",
};

export const viewport: Viewport = {
  // No maximum-scale and no user-scalable=no: blocking pinch-zoom fails WCAG 1.4.4 (which
  // requires at least 2x scaling), and is the accessibility mistake most often shipped in
  // the name of an "app-like" feel.
  width: "device-width",
  initialScale: 1,
  // The default is `resizes-visual`, where the on-screen keyboard resizes only the visual
  // viewport and leaves layout untouched — which is exactly how a bottom-pinned composer
  // ends up hidden behind the keyboard on a phone. `resizes-content` resizes the layout
  // viewport instead, so the composer is pushed above it.
  //
  // Chromium-originated progressive enhancement, not a universal fix: browsers that ignore
  // it fall back to today's behaviour, so nothing depends on it being honoured.
  interactiveWidget: "resizes-content",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-CA" className={cn("font-sans", geist.variable)} suppressHydrationWarning>
      {/* suppressHydrationWarning on <body> too, not just <html>.
          Browser extensions inject attributes onto the body before React hydrates —
          ColorZilla adds `cz-shortcut-listen`, Grammarly adds its own — and React reports
          that as a hydration mismatch even though the app's own markup matches perfectly.
          It suppresses attribute noise on this element only, not mismatches in children. */}
      <body className="bg-background text-foreground antialiased" suppressHydrationWarning>
        {/* First tab stop on every page. Without it a keyboard user traverses the whole
            header on every navigation before reaching content (WCAG 2.4.1). */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <SiteJsonLd siteUrl={SITE_URL} description={DESCRIPTION} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
