"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/**
 * Reveal a block as it enters the viewport.
 *
 * The values are chosen, not defaults, and the reasoning is the same one that separates
 * motion that feels designed from motion that feels *added*:
 *
 * **Distance is small.** 14px, not 60. Large travel reads as a slide show and makes the
 * page feel like it is assembling itself in front of you. The job is to draw the eye, not
 * to perform.
 *
 * **Duration is short and easing is asymmetric.** 0.5s on a custom cubic-bezier that
 * leaves quickly and arrives slowly (0.22, 1, 0.36, 1). Linear or symmetric easing is the
 * single most recognisable tell of motion added without thought — nothing in the physical
 * world starts and stops at the same rate.
 *
 * **It fires once.** `once: true`. Re-animating on every scroll-past turns a page into a
 * fidget and actively hurts anyone re-reading it.
 *
 * **`prefers-reduced-motion` removes the movement entirely** rather than shortening it.
 * For someone with a vestibular disorder a fast slide is still a slide; the honest response
 * is to render the content already in place.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -12% 0px" }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
