"use client";

import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import { useRef, type ReactNode } from "react";

/**
 * Scroll-linked treatment for the hero. The hero fades and drifts up slightly as it leaves,
 * which does one useful thing rather than one showy one: it hands attention over to the next
 * section instead of letting two blocks compete while both are half on screen.
 */
export function HeroScroll({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const opacity = useTransform(scrollYProgress, [0, 0.85], [1, 0.15]);
  const y = useTransform(scrollYProgress, [0, 1], [0, -40]);

  if (reduced) return <div ref={ref}>{children}</div>;

  return (
    <motion.div ref={ref} style={{ opacity, y }}>
      {children}
    </motion.div>
  );
}
