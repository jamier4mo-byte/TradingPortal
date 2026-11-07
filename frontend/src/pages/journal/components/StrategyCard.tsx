import { Link } from "react-router-dom";

import { Chip, OwnerChip } from "../../../components/ui/index.ts";
import { CountUp } from "../../../components/ui/CountUp.tsx";
import { relativeTime } from "../../../lib/format.ts";
import { fmtPct, fmtR, fmtRange, STAGE_LABEL, type Strategy } from "../../../lib/journal.ts";
import { vtName } from "../../../lib/vt.ts";
import { CoverageBar } from "./Coverage.tsx";
import { Sparkline } from "./Sparkline.tsx";

/** `countUp`: the headline number counts up (first load of the grid this session); otherwise it just shows.
 * The title carries the shared-element name that the strategy page's heading picks up (one card per id). */
export function StrategyCard({ strategy, countUp = false }: { strategy: Strategy; countUp?: boolean }) {
  const s = strategy;
  const stats = s.backtest_stats;
  return (
    <Link
      to={`/journal/strategies/${s.id}`}
      className="card group flex min-h-56 flex-col p-4 transition-[transform,border-color] duration-(--dur-quick) ease-(--ease-in-enter) hover:-translate-y-0.5 hover:border-border-strong focus-visible:border-accent tablet:p-5"
      aria-label={`${s.name}, ${STAGE_LABEL[s.stage]}`}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="line-clamp-2 text-title font-semibold" style={{ viewTransitionName: vtName("strategy", s.id) }}>
            {s.name}
          </h2>
          <p className="mt-0.5 truncate text-label text-muted">
            {[...s.instruments, ...s.timeframes].join(" · ") || "No instruments yet"}
          </p>
        </div>
        <Chip dot dotClass={s.stage === "ideal" ? "bg-muted" : "bg-accent"}>
          {STAGE_LABEL[s.stage]}
        </Chip>
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <p className="num text-heading font-semibold leading-none">
            <CountUp value={s.ideal_count} format={(v) => String(Math.round(v ?? 0))} initial={countUp} />
          </p>
          <p className="num mt-1 text-label text-muted">ideal {s.ideal_count === 1 ? "trade" : "trades"} · {fmtRange(s.range_start, s.range_end)}</p>
        </div>
        <Sparkline values={s.sparkline} width={120} height={36} />
      </div>

      <div className="mt-3">
        <CoverageBar coverage={s.coverage} />
      </div>

      {stats && stats.trades > 0 ? (
        <dl className="mt-4 grid grid-cols-3 gap-x-2 gap-y-2.5 rounded-panel border border-border bg-surface-2 p-2 text-center" aria-label="Backtest headline stats">
          <Stat label="Win rate" value={fmtPct(stats.win_rate)} />
          <Stat label="Avg R" value={fmtR(stats.avg_r)} tone={stats.avg_r} />
          <Stat label="Total R" value={fmtR(stats.total_r)} tone={stats.total_r} />
          <Stat label="Profit factor" value={stats.profit_factor === null || stats.profit_factor === undefined ? "—" : stats.profit_factor.toFixed(2)} />
          <Stat label="Max DD" value={fmtR(stats.max_dd_r ?? null)} tone={stats.max_dd_r} />
          <Stat label="Trades" value={String(stats.trades)} />
        </dl>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <OwnerChip name={s.owner.display_name} colourIndex={s.owner.colour_index} deactivated={s.owner.status === "deactivated"} />
        <span className="num text-label text-muted">Updated {relativeTime(s.updated_at)}</span>
      </div>
    </Link>
  );
}

/** Signed values carry the reserved colour and their +/− sign; colour is never the only signal. */
function Stat({ label, value, tone }: { label: string; value: string; tone?: number | null }) {
  const cls = tone === null || tone === undefined || tone === 0 ? "" : tone > 0 ? "text-win" : "text-loss";
  return (
    <div className="min-w-0">
      <dt className="truncate text-label text-muted">{label}</dt>
      <dd className={`num text-body font-medium ${cls}`}>{value}</dd>
    </div>
  );
}
