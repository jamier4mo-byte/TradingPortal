import { motion } from "motion/react";

import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";
import type { Usage } from "../../lib/markets.ts";
import { ukTime } from "../../lib/news.ts";

/** Twelve Data credits used today against the daily allowance. Fills smoothly; never green/red. */
export function CreditsMeter({ usage, className = "" }: { usage: Usage; className?: string }) {
  const pct = usage.limit ? Math.min(1, usage.used / usage.limit) : 0;
  const level = motionLevel();
  const tight = pct >= 0.85;
  return (
    <div className={className}>
      <div className="flex items-baseline gap-2 text-label">
        <span className="text-muted">Credits today</span>
        <span className="num ml-auto text-text">
          {usage.used.toLocaleString("en-GB")} / {usage.limit.toLocaleString("en-GB")}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-pill bg-surface-2"
        role="meter"
        aria-label="Twelve Data credits used today"
        aria-valuemin={0}
        aria-valuemax={usage.limit}
        aria-valuenow={usage.used}
      >
        <motion.div
          className={`h-full origin-left rounded-pill ${tight ? "bg-impact-medium" : "bg-accent"}`}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: pct }}
          transition={{ duration: level === "off" ? 0 : dur.emphasis(), ease: easeEnter }}
        />
      </div>
      <p className="num mt-1.5 text-label text-muted">
        {usage.provider === "fake" ? "Sample prices (no key in development) · " : ""}
        {usage.background_used ? `${usage.background_used} on background jobs · ` : ""}
        Resets {ukTime(usage.resets_at)} UK
      </p>
    </div>
  );
}

/** "Live data paused – daily limit reached": slides in, shows the last known prices below it. */
export function PausedBanner({ reason }: { reason: string }) {
  return (
    <div
      role="status"
      className="flex min-h-11 items-center gap-2 rounded-panel border border-border-strong bg-surface-2 px-3 text-body animate-[page-enter_var(--dur-standard)_var(--ease-in-enter)]"
    >
      <span aria-hidden className="size-2 shrink-0 rounded-full bg-stale" />
      <span>
        {reason}. <span className="text-muted">Showing the last known prices.</span>
      </span>
    </div>
  );
}
