"use client";

import { motion, useReducedMotion } from "motion/react";
import { useMemo } from "react";

/**
 * The hero's background: the corpus itself. 556 marks in a loose grid, one per indexed
 * article, with a handful lit in gold — the ones a question would reach.
 */

const TOTAL = 556;
const COLUMNS = 28;
const CELL = 11;
const MARK_W = 5;
const MARK_H = 1.5;

// Which marks are lit. Spread across the field so the eye reads "a few of many" rather
// than "a cluster", and stable so the composition does not change between renders.
const LIT = new Set([73, 149, 218, 305, 371, 448, 502]);

export function CorpusField({
  className,
  fill = false,
}: {
  className?: string;
  /**
   * Stretch to the element's box instead of preserving the field's aspect ratio. Needed
   * wherever the field is used as a wide banner: letterboxed into a short, full- width box it
   * collapses into a small dense block in the middle, which reads as a grey smudge rather
   * than as a collection of articles.
   */
  fill?: boolean;
}) {
  const reduced = useReducedMotion();

  const marks = useMemo(
    () =>
      Array.from({ length: TOTAL }, (_, i) => {
        const column = i % COLUMNS;
        const row = Math.floor(i / COLUMNS);
        // A small deterministic offset per mark keeps the field from looking like graph paper
        // — a perfect lattice reads as a texture swatch, a slightly irregular one reads as a
        // collection of things.
        const jitter = ((i * 2654435761) % 100) / 100;
        return {
          i,
          x: column * CELL + jitter * 2.5,
          y: row * CELL + (((i * 40503) % 100) / 100) * 2,
          lit: LIT.has(i),
        };
      }),
    [],
  );

  return (
    <svg
      viewBox={`0 0 ${COLUMNS * CELL} ${Math.ceil(TOTAL / COLUMNS) * CELL}`}
      className={className}
      preserveAspectRatio={fill ? "none" : "xMidYMid meet"}
      aria-hidden
      focusable="false"
    >
      {marks.map((mark) => (
        <motion.rect
          key={mark.i}
          x={mark.x}
          y={mark.y}
          width={MARK_W}
          height={MARK_H}
          rx={0.75}
          className={mark.lit ? "fill-gold" : "fill-current"}
          initial={reduced ? undefined : { opacity: 0 }}
          animate={reduced ? undefined : { opacity: mark.lit ? 0.95 : 0.22 }}
          // Staggered by position rather than index, so the field fills from the top-left
          // the way a page of text is read, and finishes inside a second.
          transition={{
            duration: 0.5,
            delay: reduced ? 0 : Math.min(0.9, (mark.y / 220) * 0.9),
            ease: "easeOut",
          }}
          // With reduced motion the field is simply present at its final opacity.
          opacity={reduced ? (mark.lit ? 0.95 : 0.22) : undefined}
        />
      ))}
    </svg>
  );
}
