import { useState } from "react";

import Card from "../../../components/Card.tsx";
import { PillToggle } from "../../../components/ui/index.ts";
import { type BacktestBlock, fmtMetric, type MetricMeta, type OwnerSplit, toneOf } from "../../../lib/analytics.ts";
import { fmtR } from "../../../lib/journal.ts";
import { BreakdownChart, type BreakdownMetric, DrawdownChart, EquityChart, ExcursionScatter, OwnerLines, OwnerSparkChart, RDistributionChart, RuleCostChart, RunsChart } from "./charts.tsx";
import { MonteCarloCard } from "./MonteCarloCard.tsx";
import { AllMetrics, KpiStrip, KpiTile } from "./parts.tsx";
import { PnlCalendar } from "./PnlCalendar.tsx";

const UNIT_OPTIONS = [
  { value: "r" as const, label: "R" },
  { value: "usd" as const, label: "$" },
];
const DIMENSIONS = [
  { value: "session" as const, label: "Session" },
  { value: "entry_model" as const, label: "Model" },
  { value: "weekday" as const, label: "Day" },
  { value: "hour" as const, label: "Hour" },
  { value: "direction" as const, label: "Side" },
];
const METRICS = [
  { value: "total_r" as const, label: "Total R" },
  { value: "win_rate" as const, label: "Win %" },
  { value: "avg_r" as const, label: "Avg R" },
];
const DIM_LABEL = { session: "session", entry_model: "entry model", weekday: "weekday", hour: "entry hour", direction: "direction", instrument: "instrument" } as const;

export const BACKTEST_KPIS = ["total_r", "win_rate", "profit_factor", "max_dd_r", "expectancy_r"];

export function BacktestViews({ block, meta, registry, owners, dim }: { block: BacktestBlock; meta: Record<string, MetricMeta>; registry: MetricMeta[]; owners: OwnerSplit[] | null; dim: boolean }) {
  const [unit, setUnit] = useState<"r" | "usd">("r");
  const [dimension, setDimension] = useState<(typeof DIMENSIONS)[number]["value"]>("session");
  const [metric, setMetric] = useState<BreakdownMetric>("total_r");
  const [calUnit, setCalUnit] = useState<"usd" | "r">("usd");
  const k = block.kpis;
  const rb = block.rulebook;

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <KpiStrip ids={BACKTEST_KPIS} kpis={k} meta={meta} signed={["total_r", "max_dd_r", "expectancy_r"]} phoneHidden={["expectancy_r"]} />

      <Card title="Equity curve" subtitle="Cumulative result, trades booked at close" controls={<PillToggle size="sm" value={unit} onChange={setUnit} options={UNIT_OPTIONS} label="Equity unit" />}>
        <EquityChart equity={block.equity} unit={unit} dim={dim} />
      </Card>

      {owners && owners.length > 1 ? <OwnersCard owners={owners} /> : null}

      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <Card title="Drawdown and streaks" subtitle="Distance below the running peak; runs of wins and losses">
          <div className="flex flex-col gap-4">
            <DrawdownChart equity={block.equity} unit={unit} dim={dim} />
            <div className="grid grid-cols-2 gap-2">
              <KpiTile meta={meta.longest_win_streak} value={k.longest_win_streak} />
              <KpiTile meta={meta.longest_loss_streak} value={k.longest_loss_streak} />
            </div>
            <RunsChart streaks={block.streaks} dim={dim} />
          </div>
        </Card>

        <Card title="R distribution" subtitle="How often each result came up, in 0.5R bins">
          <div className="flex flex-col gap-4">
            <RDistributionChart bins={block.r_distribution} dim={dim} />
            <div className="grid grid-cols-2 gap-2">
              <KpiTile meta={meta.avg_win_r} value={k.avg_win_r} signed />
              <KpiTile meta={meta.avg_loss_r} value={k.avg_loss_r} signed />
            </div>
          </div>
        </Card>
      </div>

      <Card
        title="Breakdowns"
        subtitle="Where the results come from"
        controls={
          <div className="flex flex-wrap justify-end gap-2">
            <PillToggle size="sm" value={metric} onChange={setMetric} options={METRICS} label="Breakdown measure" />
          </div>
        }
      >
        <div className="-mx-1 mb-3 overflow-x-auto px-1">
          <PillToggle size="sm" value={dimension} onChange={setDimension} options={DIMENSIONS} label="Break down by" />
        </div>
        <BreakdownChart groups={block.breakdowns[dimension]} metric={metric} label={DIM_LABEL[dimension]} dim={dim} />
      </Card>

      <Card title="P&L calendar" subtitle="By the UK date each trade opened" controls={<PillToggle size="sm" value={calUnit} onChange={setCalUnit} options={[{ value: "usd" as const, label: "$" }, { value: "r" as const, label: "R" }]} label="Calendar unit" />}>
        <PnlCalendar days={block.calendar} unit={calUnit} />
      </Card>

      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <Card title="Rulebook" subtitle="R with every rule kept vs any rule broken, and what each broken rule cost">
          {rb.marked ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-2">
                <RuleGroup title="All rules kept" n={rb.all_kept.n} avg={rb.all_kept.avg_r} total={rb.all_kept.total_r} winRate={rb.all_kept.win_rate} />
                <RuleGroup title="Any rule broken" n={rb.any_broken.n} avg={rb.any_broken.avg_r} total={rb.any_broken.total_r} winRate={rb.any_broken.win_rate} />
              </div>
              <RuleCostChart rules={rb.rules} dim={dim} />
            </div>
          ) : (
            <p className="text-body text-muted">Tick the rulebook on each trade in Annotate mode and this shows what breaking each rule costs.</p>
          )}
        </Card>
        <Card title="Exit efficiency" subtitle="Realised R against the best R available (MAE/MFE, or FX Replay's ideal price)">
          {block.excursions.n ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-2">
                <KpiTile meta={meta.exit_efficiency} value={k.exit_efficiency} />
                <KpiTile meta={meta.r_left_on_table} value={k.r_left_on_table} />
              </div>
              <ExcursionScatter points={block.excursions.points} dim={dim} />
            </div>
          ) : (
            <p className="text-body text-muted">Add MAE and MFE in Annotate mode (or import from FX Replay, which records the best price) to see how much of each move you kept.</p>
          )}
        </Card>
      </div>

      <MonteCarloCard rs={block.r_sequence} />

      <Card title="Every metric" subtitle="Values for the current filters, with how each is worked out">
        <AllMetrics kpis={k} registry={registry} />
      </Card>
    </div>
  );
}

function RuleGroup({ title, n, avg, total, winRate }: { title: string; n: number; avg: number | null; total: number | null; winRate: number | null }) {
  const tone = toneOf(avg);
  return (
    <div className="rounded-panel border border-border bg-surface-2 p-3">
      <p className="text-label text-muted">{title}</p>
      <p className={`num mt-1 text-heading leading-none font-semibold ${tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : ""}`}>{fmtR(avg)}</p>
      <p className="num mt-1 text-label text-muted">
        avg · {n} trades · {fmtR(total)} · {fmtMetric("pct", winRate)} win
      </p>
    </div>
  );
}

/** F12: split by owner. Up to three overlay in owner colours; more become small multiples. */
export function OwnersCard({ owners }: { owners: OwnerSplit[] }) {
  return (
    <Card title="By owner" subtitle={owners.length > 3 ? "One small chart each: more than three overlapping lines would mislead" : "Each person's cumulative R, in their owner colour"}>
      {owners.length > 3 ? (
        <div className="grid gap-3 tablet:grid-cols-2 desktop:grid-cols-3" data-testid="owner-multiples">
          {owners.map((o) => (
            <div key={o.owner.id} className="rounded-panel border border-border p-3">
              <OwnerHeader owner={o} />
              <OwnerSparkChart owner={o} />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3" data-testid="owner-overlay">
          <ul className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Legend">
            {owners.map((o) => (
              <li key={o.owner.id}>
                <OwnerHeader owner={o} />
              </li>
            ))}
          </ul>
          <OwnerLines owners={owners} />
        </div>
      )}
    </Card>
  );
}

const OWNER_LINE = ["bg-owner-0", "bg-owner-1", "bg-owner-2", "bg-owner-3", "bg-owner-4", "bg-owner-5", "bg-owner-6", "bg-owner-7"];

function OwnerHeader({ owner: o }: { owner: OwnerSplit }) {
  return (
    <span className="num flex items-center gap-2 text-label">
      <span aria-hidden className={`h-0.5 w-4 rounded-pill ${OWNER_LINE[o.owner.colour_index % 8]}`} />
      <span className="text-body text-text">{o.owner.display_name}</span>
      <span className="text-muted">
        {o.kpis.trades} trades · {fmtR(o.kpis.total_r)} · {fmtMetric("pct", o.kpis.win_rate)} win
      </span>
    </span>
  );
}
