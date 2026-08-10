"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * The hero graphic: a question resolving to two of the 556 indexed articles. SVG so it
 * inherits the theme colours.
 */
export function RetrievalMark({ className }: { className?: string }) {
  const reduced = useReducedMotion();

  // The finished state is always the `animate` target, including under reduced motion, where
  // only the starting point changes. Dropping the props instead would strand the element at
  // opacity 0: `useReducedMotion` resolves after first paint, so `initial` has already been
  // applied by the time it flips, and nothing is left to animate it back.
  const draw = {
    initial: reduced
      ? { pathLength: 1, opacity: 1 }
      : { pathLength: 0, opacity: 0 },
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
      <text
        x="35"
        y="74"
        textAnchor="middle"
        className="fill-primary text-[9px]"
      >
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
          transition={{
            duration: 0.9,
            delay: line.delay,
            ease: [0.22, 1, 0.36, 1],
          }}
        />
      ))}

      {/* The two cited sources */}
      {[34, 106].map((y, index) => (
        <motion.g
          key={y}
          initial={reduced ? { opacity: 1, x: 0 } : { opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            duration: reduced ? 0 : 0.45,
            delay: reduced ? 0 : 0.75 + index * 0.12,
            ease: [0.22, 1, 0.36, 1],
          }}
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

      {/* The corpus the two were chosen from, context for the two boxes above. */}
      <text
        x="184"
        y="132"
        textAnchor="middle"
        className="fill-muted-foreground text-[8px]"
      >
        of 556 indexed articles
      </text>
    </svg>
  );
}
