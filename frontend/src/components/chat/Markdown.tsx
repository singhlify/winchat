"use client";

import ReactMarkdown, {
  defaultUrlTransform,
  type Components,
} from "react-markdown";
import remarkGfm from "remark-gfm";
import { visit } from "unist-util-visit";
import type { Root, Text } from "mdast";

import { cn } from "@/lib/utils";
import type { Citation } from "@/lib/api/schemas";

/**
 * Renders an answer as markdown, with [n] markers turned into clickable citations. The model
 * replies with numbered steps, bold labels and links.
 */

const CITATION_PROTOCOL = "citation:";

/**
 * A remark plugin, rather than a string replace on the raw markdown. It walks the parsed tree
 * and skips `code` and `inlineCode` nodes, so a literal `[1]` inside a code sample stays
 * literal.
 */
function remarkCitations(validIndexes: Set<number>) {
  return () => (tree: Root) => {
    visit(tree, "text", (node: Text, index, parent) => {
      if (!parent || index === null || index === undefined) return;
      if (parent.type === "link") return; // never nest a link inside a link

      const pattern = /\[(\d+)\]/g;
      const children: (
        Text | { type: "link"; url: string; children: Text[] }
      )[] = [];
      let lastIndex = 0;
      let match: RegExpExecArray | null;

      while ((match = pattern.exec(node.value)) !== null) {
        const citationIndex = Number(match[1]);
        if (!validIndexes.has(citationIndex)) continue;

        if (match.index > lastIndex) {
          children.push({
            type: "text",
            value: node.value.slice(lastIndex, match.index),
          });
        }
        children.push({
          type: "link",
          url: `${CITATION_PROTOCOL}${citationIndex}`,
          children: [{ type: "text", value: String(citationIndex) }],
        });
        lastIndex = match.index + match[0].length;
      }

      if (children.length === 0) return;
      if (lastIndex < node.value.length) {
        children.push({ type: "text", value: node.value.slice(lastIndex) });
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      parent.children.splice(index, 1, ...(children as any));
    });
  };
}

export function Markdown({
  children,
  citations = [],
  className,
}: {
  children: string;
  citations?: Citation[];
  className?: string;
}) {
  const byIndex = new Map(
    citations.map((citation) => [citation.index, citation]),
  );
  const validIndexes = new Set(byIndex.keys());

  const components: Components = {
    a({ href, children: linkChildren, ...props }) {
      if (href?.startsWith(CITATION_PROTOCOL)) {
        const citation = byIndex.get(
          Number(href.slice(CITATION_PROTOCOL.length)),
        );
        if (!citation) return <span>[{linkChildren}]</span>;

        return (
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            // The full question is the accessible name: "2" alone tells a screen-reader
            // user nothing about what they are about to open.
            aria-label={`Source ${citation.index}: ${citation.question} (opens on ask.uwindsor.ca)`}
            title={citation.question}
            // Gold, not blue. A citation is the one thing on this page the reader is meant to
            // notice and follow, and gold is the brand's emphasis colour, the same mark used
            // on the landing page's worked example, so the gesture is already familiar before
            // anyone reaches the app.
            className="border-gold/50 bg-gold/25 text-gold-foreground focus-visible:outline-ring mx-0.5 inline-flex h-4 min-w-4 translate-y-[-1px] items-center justify-center rounded-[4px] border px-1 align-middle text-[10px] font-semibold tabular-nums no-underline transition-all duration-120 hover:-translate-y-[2px] hover:border-gold/80 hover:bg-gold/40 focus-visible:outline-2 focus-visible:outline-offset-2 motion-reduce:transition-none motion-reduce:hover:translate-y-[-1px]"
          >
            {linkChildren}
          </a>
        );
      }

      // Every other link leaves the site: noopener/noreferrer, and never target=_blank
      // without them (the opened page can otherwise reach back via window.opener).
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="underline decoration-muted-foreground/40 underline-offset-2 hover:decoration-current"
          {...props}
        >
          {linkChildren}
        </a>
      );
    },
    ol: ({ children: c }) => (
      <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted-foreground">
        {c}
      </ol>
    ),
    ul: ({ children: c }) => (
      <ul className="my-2 list-disc space-y-1 pl-5 marker:text-muted-foreground">
        {c}
      </ul>
    ),
    li: ({ children: c }) => <li className="pl-0.5">{c}</li>,
    p: ({ children: c }) => <p className="my-2 first:mt-0 last:mb-0">{c}</p>,
    strong: ({ children: c }) => <strong className="font-semibold">{c}</strong>,
    code: ({ children: c }) => (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
        {c}
      </code>
    ),
    pre: ({ children: c }) => (
      <pre className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm">
        {c}
      </pre>
    ),
    table: ({ children: c }) => (
      <div className="my-3 overflow-x-auto">
        <table className="w-full border-collapse text-sm">{c}</table>
      </div>
    ),
    th: ({ children: c }) => (
      <th className="border-b border-border px-2 py-1 text-left font-medium">
        {c}
      </th>
    ),
    td: ({ children: c }) => (
      <td className="border-b border-border/50 px-2 py-1">{c}</td>
    ),
    h1: ({ children: c }) => <h3 className="mt-3 mb-1 font-semibold">{c}</h3>,
    h2: ({ children: c }) => <h3 className="mt-3 mb-1 font-semibold">{c}</h3>,
    h3: ({ children: c }) => <h3 className="mt-3 mb-1 font-semibold">{c}</h3>,
    blockquote: ({ children: c }) => (
      <blockquote className="my-2 border-l-2 border-border pl-3 text-muted-foreground">
        {c}
      </blockquote>
    ),
  };

  return (
    <div className={cn("text-[15px] leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations(validIndexes)]}
        components={components}
        /**
         * react-markdown strips URLs whose scheme is not on its safe list, which is the
         * behaviour we want for untrusted model output, and which silently ate the internal
         * `citation:` scheme, rendering every citation as plain text. So: pass our own scheme
         * through, and hand everything else to the library's default sanitizer untouched.
         */
        urlTransform={(url) =>
          url.startsWith(CITATION_PROTOCOL) ? url : defaultUrlTransform(url)
        }
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
