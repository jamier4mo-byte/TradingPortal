import { Link } from "react-router-dom";

import { Chip, OwnerChip } from "../../../components/ui/index.ts";
import { relativeTime } from "../../../lib/format.ts";
import { fmtPct, fmtR, fmtRange, STAGE_LABEL, type Strategy } from "../../../lib/journal.ts";
import { CoverageBar } from "./Coverage.tsx";
import { Sparkline } from "./Sparkline.tsx";

export function StrategyCard({ strategy }: { strategy: Strategy }) {
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
          <h2 className="line-clamp-2 text-title font-semibold">{s.name}</h2>
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
          <p className="num text-heading font-semibold leading-none">{s.ideal_count}</p>
          <p className="num mt-1 text-label text-muted">ideal {s.ideal_count === 1 ? "trade" : "trades"} · {fmtRange(s.range_start, s.range_end)}</p>
        </div>
        <Sparkline values={s.sparkline} width={120} height={36} />
      </div>

      <div className="mt-3">
        <CoverageBar coverage={s.coverage} />
      </div>

      {stats && stats.trades > 0 ? (
        <dl className="mt-4 grid grid-cols-3 gap-2 rounded-panel border border-border bg-surface-2 p-2 text-center">
          <div>
            <dt className="text-label text-muted">Win rate</dt>
            <dd className="num text-body font-medium">{fmtPct(stats.win_rate)}</dd>
          </div>
          <div>
            <dt className="text-label text-muted">Total R</dt>
            <dd className={`num text-body font-medium ${(stats.total_r ?? 0) > 0 ? "text-win" : (stats.total_r ?? 0) < 0 ? "text-loss" : ""}`}>{fmtR(stats.total_r)}</dd>
          </div>
          <div>
            <dt className="text-label text-muted">Avg R</dt>
            <dd className="num text-body font-medium">{fmtR(stats.avg_r)}</dd>
          </div>
        </dl>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <OwnerChip name={s.owner.display_name} colourIndex={s.owner.colour_index} deactivated={s.owner.status === "deactivated"} />
        <span className="num text-label text-muted">Updated {relativeTime(s.updated_at)}</span>
      </div>
    </Link>
  );
}
