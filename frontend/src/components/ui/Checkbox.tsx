import { motion } from "motion/react";

import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";

/** A checkbox whose tick draws itself in (Micro-interactions → Toggles and checkboxes). The native input
 * stays underneath for labels, forms and screen readers; the box and the SVG tick are decoration. The tick
 * is an SVG path whose length animates over --dur-quick in Full, fades in Reduced and just appears in Off. */
export function Checkbox({
  checked,
  onChange,
  disabled = false,
  className = "",
  "aria-label": ariaLabel,
  "aria-describedby": describedBy,
  name,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
  name?: string;
}) {
  const level = motionLevel();
  const transition =
    level === "full"
      ? { pathLength: { duration: dur.quick(), ease: [...easeEnter] }, opacity: { duration: 0 } }
      : level === "reduced"
        ? { pathLength: { duration: 0 }, opacity: { duration: dur.quick() } }
        : { duration: 0 };
  return (
    <span className={`relative inline-grid size-5 shrink-0 place-items-center ${className}`}>
      <input
        type="checkbox"
        name={name}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.checked)}
        className="peer absolute inset-0 z-10 size-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
      />
      <span
        aria-hidden
        className="size-5 rounded-sm border border-border-input bg-surface-2 transition-colors duration-(--dur-quick) peer-checked:border-accent peer-checked:bg-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-disabled:opacity-50"
      />
      <svg aria-hidden viewBox="0 0 20 20" fill="none" className="pointer-events-none absolute inset-0 size-5 text-on-accent">
        <motion.path
          d="M5 10.5l3.2 3.2L15 7"
          stroke="currentColor"
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={false}
          animate={{ pathLength: checked ? 1 : 0, opacity: checked ? 1 : 0 }}
          transition={transition}
        />
      </svg>
    </span>
  );
}
