import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // The chat used to live at the root, with conversations at /c/{id}. Those URLs are in
      // browser history and possibly in someone's bookmarks, and a conversation id is the
      // only handle a visitor has on their own transcript — letting it 404 would look like
      // their history had been deleted.
      //
      // Permanent (308), because the move is not coming back and a permanent redirect is
      // what tells a search engine to transfer the old URL's standing rather than treat
      // /app as an unrelated page.
      { source: "/c/:id", destination: "/app/c/:id", permanent: true },
    ];
  },
};

export default nextConfig;
