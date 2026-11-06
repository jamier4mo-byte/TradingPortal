import { animate } from "motion/react";
import { useEffect, useRef } from "react";

import { motionLevel } from "../../lib/motion.ts";

/** A headline number that counts up on first view and rolls to the new value on a filter change.
 * Off under Reduced/Off motion. The text node is the formatted value at every frame, so it reads right. */
export function CountUp({ value, format, className = "" }: { value: number | null | undefined; format: (v: number | null) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef<number | null>(null);
  const formatRef = useRef(format);
  formatRef.current = format;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = formatRef.current;
    if (value === null || value === undefined || !Number.isFinite(value) || motionLevel() !== "full") {
      el.textContent = fmt(value ?? null);
      last.current = value ?? null;
      return;
    }
    const from = last.current ?? 0;
    last.current = value;
    if (from === value) {
      el.textContent = fmt(value);
      return;
    }
    const controls = animate(from, value, {
      duration: 0.6,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        el.textContent = fmt(v);
      },
    });
    return () => controls.stop();
  }, [value]);

  return (
    <span ref={ref} className={className}>
      {format(value ?? null)}
    </span>
  );
}
