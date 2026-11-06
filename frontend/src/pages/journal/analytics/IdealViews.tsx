import { useState } from "react";

import Card from "../../../components/Card.tsx";
import { PillToggle } from "../../../components/ui/index.ts";
import type { IdealBlock, MetricMeta } from "../../../lib/analytics.ts";
import { binsToItems, CountBars, EntryHeatmap } from "./charts.tsx";
import { KpiStrip } from "./parts.tsx";

export const IDEAL_KPIS = ["trades", "avg_r", "avg_tp_r", "avg_sl_distance", "median_duration"];

const SIZE_OPTIONS = [
  { value: "tp_r" as const, label: "TP in R" },
  { value: "tp_distance" as const, label: "TP size" },
  { value: "sl_distance" as const, label: "SL size" },
];

const num = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

/** What a typical winner looks like: sizes, durations, entry times, models, days, and the profile. */
export function IdealViews({ block, meta, unit, dim }: { block: IdealBlock; meta: Record<string, MetricMeta>; unit: string; dim: boolean }) {
  const [size, setSize] = useState<(typeof SIZE_OPTIONS)[number]["value"]>("tp_r");
  const d = block.distributions;
  const sizeItems = size === "tp_r" ? binsToItems(d.tp_r, (v) => `${num(v)}R`) : binsToItems(d[size], num);
  const p = block.profile;
  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <KpiStrip ids={IDEAL_KPIS} kpis={block.kpis} meta={meta} phoneHidden={["median_duration"]} />

      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <Card title="TP and SL sizes" subtitle={size === "tp_r" ? "Distance to the take-profit, in R" : `In ${unit}`} controls={<PillToggle size="sm" value={size} onChange={setSize} options={SIZE_OPTIONS} label="Size shown" />}>
          <CountBars items={sizeItems} label={SIZE_OPTIONS.find((o) => o.value === size)?.label ?? "Sizes"} dim={dim} />
        </Card>
        <Card title="Duration" subtitle="How long winners were held">
          <CountBars items={d.duration} label="Trade duration" dim={dim} />
        </Card>
      </div>

      <Card title="Entry times" subtitle="Hour × weekday, UK time">
        <EntryHeatmap cells={block.heatmap} dim={dim} />
      </Card>

      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <Card title="Entry models" subtitle="How often each model produced a winner">
          <CountBars items={block.breakdowns.entry_model.map((g) => ({ label: g.label, n: g.n }))} label="Entry models" dim={dim} />
        </Card>
        <Card title="Day of week" subtitle="Spread of winners across the week">
          <CountBars items={block.breakdowns.weekday.map((g) => ({ label: g.label, n: g.n }))} label="Day of week" dim={dim} />
        </Card>
      </div>

      <Card title="Strategy profile" subtitle="The most common features of these winners">
        <dl className="grid gap-x-6 gap-y-3 tablet:grid-cols-2 laptop:grid-cols-3">
          {(
            [
              ["Entry hours (UK)", p.entry_hours],
              ["Sessions", p.sessions],
              ["Entry models", p.entry_models],
              ["Weekdays", p.weekdays],
              ["Direction", p.sides],
              ["Tags", p.tags],
            ] as const
          ).map(([label, items]) => (
            <div key={label} className="flex flex-col gap-1.5">
              <dt className="text-label text-muted">{label}</dt>
              <dd className="flex flex-wrap gap-1.5">
                {items.length ? (
                  items.map((x) => (
                    <span key={x.label} className="num inline-flex min-h-7 items-center gap-1.5 rounded-pill border border-border bg-surface-2 px-2.5 text-label">
                      {x.label} <span className="text-muted">{x.count}</span>
                    </span>
                  ))
                ) : (
                  <span className="text-label text-muted">None yet</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
