import { Lock, LockOpen } from "lucide-react";
import { motion } from "motion/react";

import { dur, easeEnter, motionLevel } from "../../../lib/motion.ts";
import { type Coverage, fmtMonth } from "../../../lib/journal.ts";

/** Six blocks, one per month of the unlock rule, filled by the best run. Lives on strategy cards. */
export function CoverageBar({ coverage, compact = false }: { coverage: Coverage; compact?: boolean }) {
  const filled = Math.min(coverage.target_months, coverage.best_run);
  return (
    <div className="flex items-center gap-2" aria-label={`${filled} of ${coverage.target_months} consecutive months covered`} role="img">
      <div className="flex flex-1 gap-1">
        {Array.from({ length: coverage.target_months }, (_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-pill ${i < filled ? "bg-accent" : "bg-surface-2 border border-border"}`} />
        ))}
      </div>
      {compact ? null : (
        <span className="num text-label text-muted">
          {filled}/{coverage.target_months}
        </span>
      )}
    </div>
  );
}

/** The months grid: every month from the first trade to the last, gaps included. */
export function CoverageTracker({ coverage }: { coverage: Coverage }) {
  const level = motionLevel();
  const months = coverage.months;
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="num text-heading font-semibold leading-none">
            {Math.min(coverage.best_run, coverage.target_months)}
            <span className="text-body font-normal text-muted"> of {coverage.target_months} consecutive months</span>
          </p>
          <p className="mt-1 text-body text-muted">
            <span className="num">{coverage.trade_count}</span> ideal {coverage.trade_count === 1 ? "trade" : "trades"}
            {coverage.covered_count ? (
              <>
                {" "}
                across <span className="num">{coverage.covered_count}</span> {coverage.covered_count === 1 ? "month" : "months"}
              </>
            ) : null}
          </p>
        </div>
        <span className={`inline-flex min-h-11 items-center gap-2 rounded-panel border px-3 text-body ${coverage.unlocked ? "border-win/40 text-win" : "border-border text-muted"}`}>
          {coverage.unlocked ? <LockOpen aria-hidden className="size-4" /> : <Lock aria-hidden className="size-4" />}
          {coverage.unlocked ? "Backtest unlocked" : coverage.next_uncovered ? `Next: replay ${fmtMonth(coverage.next_uncovered)}` : "Log the first winner"}
        </span>
      </div>
      {months.length ? (
        <ol className="mt-4 grid grid-cols-3 gap-2 tablet:grid-cols-6 desktop:grid-cols-8" aria-label="Months">
          {months.map((m, i) => (
            <motion.li
              key={m.month}
              initial={level === "full" ? { opacity: 0, y: 6 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter, delay: level === "full" ? Math.min(i, 12) * 0.03 : 0 }}
              className={`flex min-h-16 flex-col justify-between rounded-panel border p-2 ${
                m.covered ? "border-accent/60 bg-accent-soft" : "border-dashed border-border-strong"
              }`}
            >
              <span className="text-label text-muted">{fmtMonth(m.month)}</span>
              <span className={`num text-body font-medium ${m.covered ? "" : "text-muted"}`}>
                {m.covered ? `${m.trades} ${m.trades === 1 ? "trade" : "trades"}` : "gap"}
              </span>
            </motion.li>
          ))}
        </ol>
      ) : (
        <p className="mt-4 rounded-panel border border-dashed border-border-strong px-4 py-6 text-center text-body text-muted">
          The months grid fills as you log winners. One trade a month for six months in a row unlocks the Backtest tab.
        </p>
      )}
    </div>
  );
}
