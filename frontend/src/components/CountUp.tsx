"use client";

import { animate, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

/**
 * Count a figure up when it scrolls into view.
 *
 * Used only on the measured results, because those numbers *are* the argument of that
 * section — animating them makes the eye land on them, which is what you want the reader
 * to take away. It would be decoration anywhere else on this page.
 *
 * Three details that keep it from feeling like a gimmick:
 *
 * **It eases out, hard.** A linear count reads like a loading spinner. `easeOut` lands the
 * last few digits slowly, which is what makes the final value feel arrived-at.
 *
 * **It is short.** 1.1s. Long counters hold the reader hostage to an animation while they
 * are trying to read a number, which is the opposite of the intent.
 *
 * **The final value is in the DOM from the first render.** The element renders its real
 * text and is only overwritten while animating, so a crawler, a reader with reduced motion,
 * and anyone whose JavaScript failed all see `100%` rather than `0`.
 */
export function CountUp({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(value);

  // Split "100%" into 100 and "%" so the suffix is preserved while the digits move.
  const numeric = Number.parseFloat(value);
  const suffix = value.replace(/^[\d.]+/, "");

  useEffect(() => {
    if (!inView || reduced || Number.isNaN(numeric)) return;

    const controls = animate(0, numeric, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (latest) => {
        // Match the source's precision: 96 must not become 96.0, and a decimal value must
        // not be rounded away.
        const decimals = value.includes(".") ? 1 : 0;
        setDisplay(latest.toFixed(decimals) + suffix);
      },
      // Snap to the exact source string at the end rather than trusting the tween to land
      // on it — floating point does not reliably arrive at a round number.
      onComplete: () => setDisplay(value),
    });

    return () => controls.stop();
  }, [inView, reduced, numeric, suffix, value]);

  return (
    <span ref={ref} className={className}>
      {/* Announced once, as the real value: a screen reader should not hear every
          intermediate number, and `aria-hidden` on the animated text keeps it quiet. */}
      <span aria-hidden>{display}</span>
      <span className="sr-only">{value}</span>
    </span>
  );
}
