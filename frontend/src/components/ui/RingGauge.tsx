import { motion } from "motion/react";

import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";

/** Ring that sweeps to its value, used sparingly: win rate, coverage, credits, countdowns. */
export function RingGauge({
  value,
  max = 100,
  size = 96,
  label,
  display,
  tone = "accent",
}: {
  value: number;
  max?: number;
  size?: number;
  label: string;
  display?: string;
  tone?: "accent" | "win" | "loss" | "impact-medium" | "impact-high";
}) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, max === 0 ? 0 : value / max));
  const level = motionLevel();
  const toneClass = {
    accent: "text-accent",
    win: "text-win",
    loss: "text-loss",
    "impact-medium": "text-impact-medium",
    "impact-high": "text-impact-high",
  }[tone];
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={`${label}: ${display ?? `${Math.round(pct * 100)}%`}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-surface-2" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          className={toneClass}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={{ duration: level === "off" ? 0 : dur.emphasis(), ease: easeEnter }}
        />
      </svg>
      <span className="num absolute text-title font-semibold">{display ?? `${Math.round(pct * 100)}%`}</span>
    </div>
  );
}
