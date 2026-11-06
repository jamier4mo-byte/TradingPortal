import { animate } from "motion/react";
import { useLayoutEffect, useRef } from "react";

import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";

/** A headline number that counts up on first view and rolls to the new value on a filter change.
 * Off under Reduced/Off motion. The span has no React children: this component owns its text, so the
 * text is always the formatted value; screen readers read the final number from a hidden twin. */
export function CountUp({ value, format, className = "" }: { value: number | null | undefined; format: (v: number | null) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef<number | null>(null);
  const formatRef = useRef(format);
  formatRef.current = format;
  const label = format(value ?? null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = formatRef.current;
    const from = last.current;
    last.current = value ?? null;
    if (value === null || value === undefined || !Number.isFinite(value) || motionLevel() !== "full" || from === value) {
      el.textContent = fmt(value ?? null);
      return;
    }
    const controls = animate(from ?? 0, value, {
      duration: dur.emphasis(),
      ease: [...easeEnter],
      onUpdate: (v) => {
        el.textContent = fmt(v);
      },
      onComplete: () => {
        el.textContent = fmt(value);
      },
    });
    return () => controls.stop();
  }, [value]);

  // Same value, new format (e.g. a unit switch): just rewrite the text.
  useLayoutEffect(() => {
    if (ref.current && last.current === (value ?? null)) ref.current.textContent = label;
  }, [label, value]);

  return (
    <span className={className}>
      <span ref={ref} aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}
