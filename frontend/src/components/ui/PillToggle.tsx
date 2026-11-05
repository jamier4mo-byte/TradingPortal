import { motion } from "motion/react";
import { useId } from "react";

import { motionLevel, spring } from "../../lib/motion.ts";

export interface PillOption<T extends string> {
  value: T;
  label: string;
}

/** Segmented control with a sliding indicator (a gentle spring). */
export function PillToggle<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
}: {
  value: T;
  onChange: (value: T) => void;
  options: PillOption<T>[];
  label: string;
  size?: "sm" | "md";
}) {
  const layoutId = useId();
  const level = motionLevel();
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-pill border border-border bg-surface-2 p-0.5">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={`relative min-h-11 rounded-pill text-body transition-colors duration-(--dur-quick) ${
              size === "sm" ? "px-2.5 text-label" : "px-3"
            } ${active ? "text-on-accent" : "text-muted hover:text-text"}`}
          >
            {active ? (
              <motion.span
                layoutId={layoutId}
                aria-hidden
                className="absolute inset-0 rounded-pill bg-accent"
                transition={level === "full" ? spring : { duration: 0 }}
              />
            ) : null}
            <span className="relative">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
