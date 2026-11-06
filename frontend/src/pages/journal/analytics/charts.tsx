/** Every analytics chart, built on the one Chart wrapper. Option builders are memoised on their data so a
 * filter change merges new data into the same series (a morph) instead of re-creating the chart. */
import { useMemo } from "react";

import { Chart, type OptionBuilder } from "../../../components/charts/Chart.tsx";
import { categoryAxis, type ChartTokens, tipRow, tipTitle, valueAxis } from "../../../components/charts/theme.ts";
import type { Bin, EquityPoint, Group, HeatCell, OwnerSplit, RuleCost, Streak } from "../../../lib/analytics.ts";
import { WEEKDAYS } from "../../../lib/analytics.ts";
import { fmtPnl, fmtR, fmtUkDate } from "../../../lib/journal.ts";
import type { MonteCarloResult } from "../../../lib/montecarlo.ts";

/** "#2f7bff" → "rgba(47,123,255,a)". Tokens arrive as authored in index.css. */
export function alpha(colour: string, a: number): string {
  const hex = colour.trim().replace("#", "");
  if (/^[0-9a-f]{6}$/i.test(hex)) {
    const n = parseInt(hex, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  const m = colour.match(/rgba?\(([^)]+)\)/);
  if (m) {
    const [r, g, b] = m[1].split(",").map((x) => x.trim());
    return `rgba(${r},${g},${b},${a})`;
  }
  return colour;
}

const signTone = (t: ChartTokens, v: number) => (v > 0 ? t.win : v < 0 ? t.loss : t.breakeven);
const fmtSigned = (unit: "r" | "usd", v: number | null) => (unit === "r" ? fmtR(v) : fmtPnl(v));
const barRadius = (v: number) => (v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4]);

function crosshair(t: ChartTokens) {
  return { type: "cross", snap: true, lineStyle: { color: t.axis, width: 1 }, crossStyle: { color: t.axis, width: 1 }, label: { backgroundColor: t.surface2, color: t.text, borderColor: t.borderStrong, borderWidth: 1, fontFamily: t.font } };
}

// ---- equity and drawdown -------------------------------------------------------------------------

export function EquityChart({ equity, unit, dim }: { equity: EquityPoint[]; unit: "r" | "usd"; dim?: boolean }) {
  const key = unit === "r" ? "cum_r" : "cum_pnl";
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: {
        trigger: "axis",
        axisPointer: crosshair(t),
        formatter: (params: { dataIndex: number }[]) => {
          const p = equity[params[0]?.dataIndex ?? 0];
          if (!p) return "";
          return tipTitle(`Trade ${p.i} · ${fmtUkDate(p.at)}`) + tipRow(t.series1, "cumulative", fmtSigned(unit, p[key])) + tipRow(t.muted, "this trade", fmtSigned(unit, unit === "r" ? p.r : p.pnl));
        },
      },
      xAxis: categoryAxis(t, equity.map((p) => String(p.i)), { name: "Trade", nameLocation: "middle", nameGap: 24, nameTextStyle: { color: t.muted }, boundaryGap: false }),
      yAxis: valueAxis(t, { axisLabel: { color: t.muted, formatter: (v: number) => (unit === "r" ? `${v}R` : `$${v.toLocaleString("en-GB")}`) } }),
      grid: { left: 8, right: 56, top: 16, bottom: 28, containLabel: true },
      series: [
        {
          id: "equity",
          type: "line",
          data: equity.map((p) => p[key]),
          showSymbol: false,
          symbolSize: 8,
          lineStyle: { width: 2, color: t.series1, cap: "round", join: "round" },
          itemStyle: { color: t.series1, borderColor: t.surface1, borderWidth: 2 },
          areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: alpha(t.series1, 0.24) }, { offset: 1, color: alpha(t.series1, 0) }] } },
          endLabel: { show: true, color: t.text, fontFamily: t.font, fontSize: 12, formatter: (p: { value: number }) => fmtSigned(unit, p.value) },
          markLine: { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: t.axis, width: 1, type: "solid" }, data: [{ yAxis: 0 }] },
        },
      ],
    }),
    [equity, key, unit],
  );
  const last = equity[equity.length - 1];
  const peak = equity.reduce((m, p) => Math.max(m, p[key]), 0);
  const summary = last ? `${equity.length} trades, finishing at ${fmtSigned(unit, last[key])}; peak ${fmtSigned(unit, peak)}.` : "No trades yet.";
  const table = { columns: ["Trade", "Date", unit === "r" ? "R" : "P&L", "Cumulative"], rows: equity.map((p) => [p.i, fmtUkDate(p.at), fmtSigned(unit, unit === "r" ? p.r : p.pnl), fmtSigned(unit, p[key])]) };
  return <Chart label={`Equity curve in ${unit === "r" ? "R" : "$"}`} option={option} summary={summary} table={table} height={280} dim={dim} />;
}

export function DrawdownChart({ equity, unit, dim }: { equity: EquityPoint[]; unit: "r" | "usd"; dim?: boolean }) {
  const key = unit === "r" ? "dd_r" : "dd_pnl";
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "axis", axisPointer: crosshair(t), formatter: (ps: { dataIndex: number }[]) => { const p = equity[ps[0]?.dataIndex ?? 0]; return p ? tipTitle(`Trade ${p.i} · ${fmtUkDate(p.at)}`) + tipRow(t.loss, "below the peak", fmtSigned(unit, p[key])) : ""; } },
      xAxis: categoryAxis(t, equity.map((p) => String(p.i)), { boundaryGap: false }),
      yAxis: valueAxis(t, { max: 0, axisLabel: { color: t.muted, formatter: (v: number) => (unit === "r" ? `${v}R` : `$${v}`) } }),
      series: [{ id: "dd", type: "line", data: equity.map((p) => p[key]), showSymbol: false, lineStyle: { width: 2, color: t.loss }, areaStyle: { color: alpha(t.loss, 0.1) } }],
    }),
    [equity, key, unit],
  );
  const worst = equity.reduce((m, p) => Math.min(m, p[key]), 0);
  const at = equity.find((p) => p[key] === worst);
  const summary = worst < 0 && at ? `Deepest drawdown ${fmtSigned(unit, worst)} after trade ${at.i} (${fmtUkDate(at.at)}).` : "No drawdown: the curve never fell below a previous high.";
  return <Chart label="Drawdown from the running peak" option={option} summary={summary} table={{ columns: ["Trade", "Drawdown"], rows: equity.map((p) => [p.i, fmtSigned(unit, p[key])]) }} height={160} dim={dim} />;
}

/** Each run of wins (up) and losses (down) in order: direction carries the outcome as well as colour. */
export function RunsChart({ streaks, dim }: { streaks: Streak[]; dim?: boolean }) {
  const runs = streaks.filter((s) => s.outcome === "win" || s.outcome === "loss");
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const s = runs[p.dataIndex]; return s ? tipTitle(`From ${fmtUkDate(s.start)}`) + tipRow(s.outcome === "win" ? t.win : t.loss, s.outcome === "win" ? "wins in a row" : "losses in a row", String(s.length)) + tipRow(t.muted, "R over the run", fmtR(s.r)) : ""; } },
      xAxis: categoryAxis(t, runs.map((_, i) => String(i + 1)), { axisLabel: { show: false }, axisLine: { lineStyle: { color: t.axis } } }),
      yAxis: valueAxis(t, { minInterval: 1, axisLabel: { color: t.muted, formatter: (v: number) => `${Math.abs(v)}` } }),
      series: [{ id: "runs", type: "bar", barMaxWidth: 12, barCategoryGap: "30%", data: runs.map((s) => ({ value: s.outcome === "win" ? s.length : -s.length, itemStyle: { color: s.outcome === "win" ? t.win : t.loss, borderRadius: s.outcome === "win" ? [3, 3, 0, 0] : [0, 0, 3, 3] } })) }],
    }),
    [runs],
  );
  const longestWin = Math.max(0, ...runs.filter((s) => s.outcome === "win").map((s) => s.length));
  const longestLoss = Math.max(0, ...runs.filter((s) => s.outcome === "loss").map((s) => s.length));
  return (
    <Chart
      label="Win and loss streaks"
      option={option}
      summary={`${runs.length} runs. Longest: ${longestWin} wins, ${longestLoss} losses (up = wins, down = losses; a breakeven ends a run).`}
      table={{ columns: ["Run", "Outcome", "Length", "R"], rows: runs.map((s, i) => [i + 1, s.outcome === "win" ? "Wins" : "Losses", s.length, fmtR(s.r)]) }}
      height={140}
      dim={dim}
    />
  );
}

// ---- breakdowns and distributions -----------------------------------------------------------------

export type BreakdownMetric = "total_r" | "win_rate" | "avg_r" | "n";

export function BreakdownChart({ groups, metric, label, dim }: { groups: Group[]; metric: BreakdownMetric; label: string; dim?: boolean }) {
  const shown = groups.filter((g) => g.n > 0 || label === "weekday");
  const fmt = (v: number | null) => (v === null ? "—" : metric === "win_rate" ? `${Math.round(v * 100)}%` : metric === "n" ? String(v) : fmtR(v));
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: {
        trigger: "item",
        formatter: (p: { dataIndex: number }) => {
          const g = shown[p.dataIndex];
          if (!g) return "";
          return tipTitle(g.label) + tipRow(t.series1, `n=${g.n}`, fmt(g[metric] as number | null)) + (metric !== "win_rate" ? tipRow(t.muted, "win rate", g.win_rate === null ? "—" : `${Math.round(g.win_rate * 100)}%`) : tipRow(t.muted, "total", fmtR(g.total_r)));
        },
      },
      xAxis: categoryAxis(t, shown.map((g) => g.label), { axisLabel: { color: t.muted, interval: 0, hideOverlap: true, rotate: shown.length > 8 ? 45 : 0 } }),
      yAxis: valueAxis(t, metric === "win_rate" ? { min: 0, max: 1, axisLabel: { color: t.muted, formatter: (v: number) => `${Math.round(v * 100)}%` } } : { axisLabel: { color: t.muted, formatter: (v: number) => (metric === "n" ? `${v}` : `${v}R`) } }),
      series: [
        {
          id: "breakdown",
          type: "bar",
          barMaxWidth: 24,
          data: shown.map((g) => {
            const v = (g[metric] as number | null) ?? 0;
            const signed = metric === "total_r" || metric === "avg_r";
            return { value: g[metric], itemStyle: { color: signed ? signTone(t, v) : t.series1, borderRadius: barRadius(v) } };
          }),
          label: { show: shown.length <= 8, position: "top", color: t.muted, fontFamily: t.font, fontSize: t.labelSize, formatter: (p: { value: number | null }) => fmt(p.value) },
        },
      ],
    }),
    [shown, metric],
  );
  const best = [...shown].filter((g) => g.n >= 3 && g[metric] !== null).sort((a, b) => (b[metric] as number) - (a[metric] as number))[0];
  const summary = shown.length ? (best ? `Best ${label} by ${metricName(metric)}: ${best.label} (${fmt(best[metric] as number)}, n=${best.n}).` : `${shown.length} ${label} groups, none with 3+ trades yet.`) : "No trades.";
  return (
    <Chart
      label={`Breakdown by ${label}`}
      option={option}
      summary={summary}
      table={{ columns: [capital(label), "Trades", "Win rate", "Total R", "Avg R"], rows: shown.map((g) => [g.label, g.n, g.win_rate === null ? "—" : `${Math.round(g.win_rate * 100)}%`, fmtR(g.total_r), fmtR(g.avg_r)]) }}
      height={220}
      dim={dim}
    />
  );
}

const metricName = (m: BreakdownMetric) => ({ total_r: "total R", win_rate: "win rate", avg_r: "average R", n: "trade count" })[m];
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function RDistributionChart({ bins, dim }: { bins: Bin[]; dim?: boolean }) {
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const b = bins[p.dataIndex]; return b ? tipTitle(`${fmtR(b.from)} to ${fmtR(b.to)}`) + tipRow(t.series1, "trades", String(b.n)) : ""; } },
      xAxis: categoryAxis(t, bins.map((b) => (b.from > 0 ? `+${b.from}` : b.from < 0 ? `−${Math.abs(b.from)}` : "0")), { name: "R (bin start)", nameLocation: "middle", nameGap: 26, nameTextStyle: { color: t.muted } }),
      yAxis: valueAxis(t, { minInterval: 1 }),
      grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
      series: [{ id: "rdist", type: "bar", barMaxWidth: 24, barCategoryGap: "8%", data: bins.map((b) => ({ value: b.n, itemStyle: { color: b.to <= 0 ? t.loss : b.from > 0 ? t.win : t.breakeven, borderRadius: [4, 4, 0, 0] } })) }],
    }),
    [bins],
  );
  const total = bins.reduce((a, b) => a + b.n, 0);
  const mode = [...bins].sort((a, b) => b.n - a.n)[0];
  return (
    <Chart
      label="R distribution"
      option={option}
      summary={mode ? `${total} trades in 0.5R bins; the most common result is ${fmtR(mode.from)} to ${fmtR(mode.to)} (${mode.n}). Losses red, wins green, around zero grey.` : "No trades."}
      table={{ columns: ["From", "To", "Trades"], rows: bins.map((b) => [fmtR(b.from), fmtR(b.to), b.n]) }}
      height={220}
      dim={dim}
    />
  );
}

/** Plain count bars for one series: durations, sizes, entry models, weekdays. */
export function CountBars({ items, label, unitLabel = "trades", dim, height = 200 }: { items: { label: string; n: number }[]; label: string; unitLabel?: string; dim?: boolean; height?: number }) {
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const it = items[p.dataIndex]; return it ? tipTitle(it.label) + tipRow(t.series1, unitLabel, String(it.n)) : ""; } },
      xAxis: categoryAxis(t, items.map((i) => i.label), { axisLabel: { color: t.muted, interval: 0, hideOverlap: true, rotate: items.length > 8 ? 45 : 0 } }),
      yAxis: valueAxis(t, { minInterval: 1 }),
      series: [{ id: "counts", type: "bar", barMaxWidth: 24, itemStyle: { color: t.series1, borderRadius: [4, 4, 0, 0] }, data: items.map((i) => i.n), label: { show: items.length <= 10, position: "top", color: t.muted, fontFamily: t.font, fontSize: t.labelSize } }],
    }),
    [items, unitLabel],
  );
  const total = items.reduce((a, i) => a + i.n, 0);
  const top = [...items].sort((a, b) => b.n - a.n)[0];
  return (
    <Chart
      label={label}
      option={option}
      summary={top && total ? `${total} ${unitLabel}; most common: ${top.label} (${top.n}, ${Math.round((top.n / total) * 100)}%).` : "Nothing to show yet."}
      table={{ columns: ["", capital(unitLabel)], rows: items.map((i) => [i.label, i.n]) }}
      height={height}
      dim={dim}
    />
  );
}

export function binsToItems(bins: Bin[], fmt: (v: number) => string): { label: string; n: number }[] {
  return bins.map((b) => ({ label: `${fmt(b.from)}–${fmt(b.to)}`, n: b.n }));
}

/** Entry time heatmap, hour × weekday (UK). One sequential hue; cells fade in busiest first. */
export function EntryHeatmap({ cells, dim }: { cells: HeatCell[]; dim?: boolean }) {
  const days = WEEKDAYS.filter((_, i) => i < 5 || cells.some((c) => c.weekday === i));
  const hours = Array.from(new Set(cells.map((c) => c.hour))).sort((a, b) => a - b);
  const span = hours.length ? Array.from({ length: hours[hours.length - 1] - hours[0] + 1 }, (_, i) => hours[0] + i) : [];
  const max = Math.max(1, ...cells.map((c) => c.n));
  const shownCells = cells.filter((c) => span.includes(c.hour));
  const ranked = [...shownCells].sort((a, b) => b.n - a.n);
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { data: [number, number, number] }) => { const [h, d, n] = p.data; const c = cells.find((x) => x.hour === span[h] && x.weekday === WEEKDAYS.indexOf(days[d])); return tipTitle(`${days[d]} ${String(span[h]).padStart(2, "0")}:00 UK`) + tipRow(t.series1, "trades", String(n)) + (c?.avg_r !== undefined && c?.avg_r !== null ? tipRow(t.muted, "average", fmtR(c.avg_r)) : ""); } },
      grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
      xAxis: categoryAxis(t, span.map((h) => `${String(h).padStart(2, "0")}:00`), { splitArea: { show: false } }),
      yAxis: categoryAxis(t, days as unknown as string[], { inverse: true, axisLine: { show: false } }),
      visualMap: { min: 0, max, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 10, itemHeight: 120, text: ["More", "Fewer"], textStyle: { color: t.muted, fontFamily: t.font, fontSize: t.labelSize }, inRange: { color: [alpha(t.series1, 0.08), t.series1] } },
      series: [
        {
          id: "heat",
          type: "heatmap",
          data: shownCells.map((c) => [span.indexOf(c.hour), days.indexOf(WEEKDAYS[c.weekday]), c.n]),
          itemStyle: { borderColor: t.surface1, borderWidth: 2, borderRadius: 3 },
          emphasis: { itemStyle: { borderColor: t.text, borderWidth: 1 } },
          // Cells fade in by intensity, busiest first, 30ms apart (capped so big grids don't drag).
          animationDelay: (idx: number) => Math.min(ranked.indexOf(shownCells[idx]), 16) * 30,
        },
      ],
    }),
    [cells, shownCells, days, span, max, ranked],
  );
  const top = ranked[0];
  return (
    <Chart
      label="Entry-time heatmap"
      option={option}
      summary={top ? `Busiest: ${WEEKDAYS[top.weekday]} ${String(top.hour).padStart(2, "0")}:00 UK with ${top.n} trades. Brighter blue = more trades.` : "No entries yet."}
      table={{ columns: ["Day", "Hour (UK)", "Trades", "Avg R"], rows: cells.map((c) => [WEEKDAYS[c.weekday], `${String(c.hour).padStart(2, "0")}:00`, c.n, fmtR(c.avg_r)]) }}
      height={Math.max(180, days.length * 34 + 60)}
      dim={dim}
    />
  );
}

// ---- rulebook, excursions, Monte Carlo, owners --------------------------------------------------

export function RuleCostChart({ rules, dim }: { rules: RuleCost[]; dim?: boolean }) {
  const shown = rules.filter((r) => r.cost_r !== null);
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const r = shown[p.dataIndex]; return r ? tipTitle(r.text) + tipRow(t.loss, "cost", fmtR(-(r.cost_r ?? 0))) + tipRow(t.muted, "broken", `${r.broken}×`) + tipRow(t.muted, "avg kept / broken", `${fmtR(r.avg_r_kept)} / ${fmtR(r.avg_r_broken)}`) : ""; } },
      grid: { left: 8, right: 64, top: 8, bottom: 8, containLabel: true },
      xAxis: valueAxis(t, { axisLabel: { show: false } }),
      yAxis: categoryAxis(t, shown.map((r, i) => `${i + 1}. ${r.text.length > 28 ? `${r.text.slice(0, 27)}…` : r.text}`), { inverse: true, axisLine: { show: false } }),
      series: [{ id: "cost", type: "bar", barMaxWidth: 16, data: shown.map((r) => ({ value: r.cost_r, itemStyle: { color: (r.cost_r ?? 0) > 0 ? t.loss : t.breakeven, borderRadius: [0, 4, 4, 0] } })), label: { show: true, position: "right", color: t.muted, fontFamily: t.font, fontSize: t.labelSize, formatter: (p: { value: number }) => (p.value > 0 ? `−${p.value.toFixed(2)}R` : fmtR(-p.value)) } }],
    }),
    [shown],
  );
  const worst = [...shown].sort((a, b) => (b.cost_r ?? 0) - (a.cost_r ?? 0))[0];
  return (
    <Chart
      label="What each broken rule cost"
      option={option}
      summary={worst && (worst.cost_r ?? 0) > 0 ? `Most costly: “${worst.text}”, broken ${worst.broken}×, costing about ${worst.cost_r?.toFixed(2)}R.` : "No rule has cost R so far."}
      table={{ columns: ["Rule", "Kept", "Broken", "Avg R kept", "Avg R broken", "Cost"], rows: rules.map((r) => [r.text, r.kept, r.broken, fmtR(r.avg_r_kept), fmtR(r.avg_r_broken), r.cost_r === null ? "—" : fmtR(-r.cost_r)]) }}
      height={Math.max(140, shown.length * 36 + 24)}
      dim={dim}
    />
  );
}

export function ExcursionScatter({ points, dim }: { points: { id: number; r: number; mfe: number; outcome: string | null }[]; dim?: boolean }) {
  const max = Math.ceil(Math.max(1, ...points.map((p) => Math.max(p.mfe, p.r))));
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const pt = points[p.dataIndex]; return pt ? tipTitle(`Trade #${pt.id}`) + tipRow(t.series1, "realised", fmtR(pt.r)) + tipRow(t.muted, "max favourable", fmtR(pt.mfe)) : ""; } },
      grid: { left: 28, right: 16, top: 12, bottom: 28, containLabel: true },
      xAxis: valueAxis(t, { min: 0, max, name: "Max favourable R", nameLocation: "middle", nameGap: 24, nameTextStyle: { color: t.muted } }),
      yAxis: valueAxis(t, { min: Math.min(-1, Math.floor(Math.min(...points.map((p) => p.r), 0))), max, name: "Realised R", nameLocation: "middle", nameRotate: 90, nameGap: 28, nameTextStyle: { color: t.muted } }),
      series: [
        {
          id: "exc",
          type: "scatter",
          symbolSize: 9,
          data: points.map((p) => ({ value: [p.mfe, p.r], itemStyle: { color: p.r > 0 ? t.win : p.r < 0 ? t.loss : t.breakeven, borderColor: t.surface1, borderWidth: 2 } })),
          markLine: { silent: true, symbol: "none", lineStyle: { color: t.axis, type: "solid", width: 1 }, label: { show: false }, data: [[{ coord: [0, 0] }, { coord: [max, max] }]] },
        },
      ],
    }),
    [points, max],
  );
  return (
    <Chart
      label="Exit efficiency scatter"
      option={option}
      summary={`${points.length} trades with a favourable excursion. On the diagonal = took all of it; below = R left on the table.`}
      table={{ columns: ["Trade", "Realised R", "Max favourable R"], rows: points.map((p) => [`#${p.id}`, fmtR(p.r), fmtR(p.mfe)]) }}
      height={240}
      dim={dim}
    />
  );
}

export function MonteCarloChart({ result }: { result: MonteCarloResult }) {
  const x = Array.from({ length: result.length }, (_, i) => String(i + 1));
  const option = useMemo<OptionBuilder>(
    () => (t) => {
      const { p5, p25, p50, p75, p95 } = result.bands;
      return {
        tooltip: { trigger: "axis", axisPointer: crosshair(t), formatter: (ps: { dataIndex: number }[]) => { const i = ps[0]?.dataIndex ?? 0; return tipTitle(`After ${i + 1} trades`) + tipRow(t.series1, "median", fmtR(p50[i])) + tipRow(alpha(t.series1, 0.45), "middle half", `${fmtR(p25[i])} to ${fmtR(p75[i])}`) + tipRow(alpha(t.series1, 0.2), "90% of paths", `${fmtR(p5[i])} to ${fmtR(p95[i])}`); } },
        xAxis: categoryAxis(t, x, { boundaryGap: false, name: "Trades", nameLocation: "middle", nameGap: 24, nameTextStyle: { color: t.muted } }),
        yAxis: valueAxis(t, { axisLabel: { color: t.muted, formatter: (v: number) => `${v}R` } }),
        grid: { left: 8, right: 56, top: 16, bottom: 28, containLabel: true },
        series: [
          { id: "lo", type: "line", data: p5, stack: "outer", lineStyle: { opacity: 0 }, showSymbol: false, silent: true },
          { id: "outer", type: "line", data: p95.map((v, i) => v - p5[i]), stack: "outer", lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: alpha(t.series1, 0.1) }, silent: true },
          { id: "lo2", type: "line", data: p25, stack: "inner", lineStyle: { opacity: 0 }, showSymbol: false, silent: true },
          { id: "inner", type: "line", data: p75.map((v, i) => v - p25[i]), stack: "inner", lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: alpha(t.series1, 0.2) }, silent: true },
          { id: "median", type: "line", data: p50, showSymbol: false, lineStyle: { width: 2, color: t.series1 }, endLabel: { show: true, color: t.text, fontFamily: t.font, formatter: (p: { value: number }) => fmtR(p.value) } },
        ],
      };
    },
    [result, x],
  );
  return (
    <Chart
      label="Monte Carlo of the R sequence"
      option={option}
      summary={`${result.paths.toLocaleString("en-GB")} reshuffled paths of ${result.length} trades. Median finish ${fmtR(result.final.p50)}; 90% of paths finish between ${fmtR(result.final.p5)} and ${fmtR(result.final.p95)}.`}
      table={{ columns: ["After trade", "5th", "25th", "Median", "75th", "95th"], rows: result.bands.p50.map((_, i) => [i + 1, fmtR(result.bands.p5[i]), fmtR(result.bands.p25[i]), fmtR(result.bands.p50[i]), fmtR(result.bands.p75[i]), fmtR(result.bands.p95[i])]).filter((_, i, all) => i % Math.max(1, Math.ceil(all.length / 40)) === 0 || i === all.length - 1) }}
      height={260}
    />
  );
}

/** Up to three owners overlay in their owner colours; F12 says merged curves mislead past that. */
export function OwnerLines({ owners, dim }: { owners: OwnerSplit[]; dim?: boolean }) {
  const longest = Math.max(0, ...owners.map((o) => o.equity.length));
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "axis", axisPointer: crosshair(t), formatter: (ps: { dataIndex: number }[]) => { const i = ps[0]?.dataIndex ?? 0; return tipTitle(`Trade ${i + 1}`) + owners.map((o) => tipRow(t.owners[o.owner.colour_index % 8], o.owner.display_name, o.equity[i] === undefined ? "—" : fmtR(o.equity[i]))).join(""); } },
      legend: { show: false },
      xAxis: categoryAxis(t, Array.from({ length: longest }, (_, i) => String(i + 1)), { boundaryGap: false }),
      yAxis: valueAxis(t, { axisLabel: { color: t.muted, formatter: (v: number) => `${v}R` } }),
      // No end labels: shorter histories end mid-chart and would sit on the other lines. The legend names them.
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      series: owners.map((o) => ({
        id: `owner-${o.owner.id}`,
        name: o.owner.display_name,
        type: "line",
        data: o.equity,
        showSymbol: false,
        lineStyle: { width: 2, color: t.owners[o.owner.colour_index % 8] },
        itemStyle: { color: t.owners[o.owner.colour_index % 8] },
      })),
    }),
    [owners, longest],
  );
  return (
    <Chart
      label="Cumulative R by owner"
      option={option}
      summary={owners.map((o) => `${o.owner.display_name} ${fmtR(o.equity[o.equity.length - 1] ?? 0)} over ${o.equity.length} trades`).join("; ") + "."}
      table={{ columns: ["Owner", "Trades", "Total R", "Win rate"], rows: owners.map((o) => [o.owner.display_name, o.equity.length, fmtR(o.kpis.total_r), o.kpis.win_rate === null ? "—" : `${Math.round((o.kpis.win_rate ?? 0) * 100)}%`]) }}
      height={260}
      dim={dim}
    />
  );
}

export function OwnerSparkChart({ owner }: { owner: OwnerSplit }) {
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: { trigger: "axis", formatter: (ps: { dataIndex: number }[]) => { const i = ps[0]?.dataIndex ?? 0; return tipTitle(`Trade ${i + 1}`) + tipRow(t.owners[owner.owner.colour_index % 8], owner.owner.display_name, fmtR(owner.equity[i])); } },
      xAxis: categoryAxis(t, owner.equity.map((_, i) => String(i + 1)), { boundaryGap: false, axisLabel: { show: false } }),
      yAxis: valueAxis(t, { splitNumber: 2, axisLabel: { color: t.muted, formatter: (v: number) => `${v}R` } }),
      grid: { left: 4, right: 8, top: 8, bottom: 4, containLabel: true },
      series: [{ id: "eq", type: "line", data: owner.equity, showSymbol: false, lineStyle: { width: 2, color: t.owners[owner.owner.colour_index % 8] } }],
    }),
    [owner],
  );
  return (
    <Chart
      label={`${owner.owner.display_name}: cumulative R`}
      option={option}
      summary={`${owner.equity.length} trades, ${fmtR(owner.equity[owner.equity.length - 1] ?? 0)}.`}
      table={{ columns: ["Trade", "Cumulative R"], rows: owner.equity.map((v, i) => [i + 1, fmtR(v)]) }}
      height={120}
    />
  );
}
