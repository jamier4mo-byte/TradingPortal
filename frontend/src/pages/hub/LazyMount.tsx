import { useInView } from "motion/react";
import { type ReactNode, Suspense, useRef } from "react";

/** Mounts its children (usually a `React.lazy` component) only once the slot scrolls near the viewport,
 * showing the same skeleton before and while the chunk loads (F18: nothing below the fold is in the Hub's
 * initial JavaScript). */
export function LazyMount({ children, fallback, className = "" }: { children: ReactNode; fallback: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "240px 0px" });
  return (
    <div ref={ref} className={className}>
      {inView ? <Suspense fallback={fallback}>{children}</Suspense> : fallback}
    </div>
  );
}
