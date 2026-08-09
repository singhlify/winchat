"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * The hero graphic: a diagram of what the app actually does.
 *
 * Drawn as SVG rather than illustrated, and specific rather than abstract — it shows a
 * question resolving to two of 556 indexed articles, which is the product's whole claim.
 * A generic gradient blob or a stock isometric laptop would fill the same space and say
 * nothing; worse, it would say "this space needed filling", which is the impression the
 * page is trying not to give.
 *
 * The motion is diegetic: the connector lines draw from the question toward the sources,
 * in the direction retrieval actually flows. It runs once on mount and then stops, because
 * a looping animation beside a paragraph competes with reading it.
 *
 * SVG rather than canvas or WebGL: it is a few hundred bytes, scales to any density, works
 * with no JavaScript at all, and inherits `currentColor` so it follows the theme for free.
 * A shader here would cost a library, a GPU context and battery on the phones most of this
 * app's visitors are using, to draw eleven lines.
 */
export function RetrievalMark({ className }: { className?: string }) {
  const reduced = useReducedMotion();

  // With reduced motion the finished state is rendered directly — the diagram is
  // informative, so it must be complete, not merely still.
  const draw = reduced
    ? undefined
    : {
        initial: { pathLength: 0, opacity: 0 },
        animate: { pathLength: 1, opacity: 1 },
      };

  return (
    <svg
      viewBox="0 0 220 140"
      className={className}
      role="img"
      aria-label="A question connecting to two of the indexed source articles"
    >
      {/* Question node */}
      <rect
        x="4"
        y="58"
        width="62"
        height="24"
        rx="12"
        className="fill-primary/10 stroke-primary/40"
        strokeWidth="1"
      />
      <text x="35" y="74" textAnchor="middle" className="fill-primary text-[9px]">
        question
      </text>

      {/* Connectors, drawn in the direction retrieval flows */}
      {[
        { d: "M66 70 C 110 70, 120 34, 152 34", delay: 0.15 },
        { d: "M66 70 C 110 70, 120 106, 152 106", delay: 0.3 },
      ].map((line) => (
        <motion.path
          key={line.d}
          d={line.d}
          fill="none"
          strokeWidth="1.25"
          className="stroke-gold"
          {...draw}
          transition={{ duration: 0.9, delay: line.delay, ease: [0.22, 1, 0.36, 1] }}
        />
      ))}

      {/* The two cited sources */}
      {[34, 106].map((y, index) => (
        <motion.g
          key={y}
          initial={reduced ? undefined : { opacity: 0, x: -6 }}
          animate={reduced ? undefined : { opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.75 + index * 0.12, ease: [0.22, 1, 0.36, 1] }}
        >
          <rect
            x="152"
            y={y - 12}
            width="64"
            height="24"
            rx="6"
            className="fill-gold/15 stroke-gold/50"
            strokeWidth="1"
          />
          <text
            x="184"
            y={y + 4}
            textAnchor="middle"
            className="fill-gold-foreground text-[9px]"
          >
            source {index + 1}
          </text>
        </motion.g>
      ))}

      {/* The corpus the two were chosen from — context for the two boxes above. */}
      <text x="184" y="132" textAnchor="middle" className="fill-muted-foreground text-[8px]">
        of 556 indexed articles
      </text>
    </svg>
  );
}
