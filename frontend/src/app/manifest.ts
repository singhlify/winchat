import type { MetadataRoute } from "next";

/**
 * Web app manifest.
 *
 * `start_url` is `/app` rather than `/`: someone who installs this has already decided
 * what it is for, and landing them on a marketing page every launch is the most common
 * way an installed app feels like a bookmark.
 *
 * `display: "standalone"` rather than `fullscreen`. Standalone keeps the system status bar
 * and the platform back gesture, both of which people rely on; fullscreen buys a few pixels
 * and takes away their way out.
 *
 * `id` is set explicitly. Without it the identity is derived from `start_url`, so changing
 * that URL later would make browsers treat the result as a different app and orphan
 * everyone's existing install.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/?source=pwa",
    name: "WinChat · University of Windsor FAQ",
    short_name: "WinChat",
    description:
      "Ask about University of Windsor admissions, fees, courses and campus services. Every answer links back to the university's own published FAQ article.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#fdfdfe",
    theme_color: "#0b4f6c",
    categories: ["education", "productivity", "utilities"],
    lang: "en-CA",
    dir: "ltr",
    icons: [
      // SVG covers every size on browsers that accept it, which is most of them now.
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      // Maskable is a separate entry, not an extra purpose on the one above: a maskable
      // icon is designed with a safe zone and gets cropped to the platform's shape, so
      // reusing a plain icon as maskable is how installed apps end up with their edges
      // shaved off.
      {
        src: "/icon-maskable.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      {
        name: "New chat",
        short_name: "New chat",
        description: "Start a fresh conversation",
        url: "/app",
      },
      {
        name: "Browse sources",
        short_name: "Sources",
        description: "Every indexed University of Windsor FAQ article",
        url: "/sources",
      },
    ],
  };
}
