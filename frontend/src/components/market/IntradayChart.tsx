import { useMemo } from "react";

import { Chart, type OptionBuilder } from "../charts/Chart.tsx";
import { categoryAxis, tipRow, tipTitle, valueAxis } from "../charts/theme.ts";
import { formatPrice } from "../../lib/markets.ts";
import { ukTime } from "../../lib/news.ts";


/** The instrument view's intraday line: the shared ECharts wrapper (axes, crosshair, tap to pin, summary
 * and data table). Series 1, never green/red. */
export function IntradayChart({ points, decimals, label }: { points: { t: string; v: number }[]; decimals: number; label: string }) {
  const option = useMemo<OptionBuilder>(
    () => (t) => ({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", snap: true, lineStyle: { color: t.axis, width: 1 }, crossStyle: { color: t.axis, width: 1 }, label: { backgroundColor: t.surface2, color: t.text, borderColor: t.borderStrong, borderWidth: 1, fontFamily: t.font } },
        formatter: (ps: { dataIndex: number }[]) => {
          const p = points[ps[0]?.dataIndex ?? 0];
          return p ? tipTitle(`${ukTime(p.t)} UK`) + tipRow(t.series1, "close", formatPrice(p.v, decimals)) : "";
        },
      },
      xAxis: categoryAxis(t, points.map((p) => ukTime(p.t)), { boundaryGap: false }),
      yAxis: valueAxis(t, { scale: true, axisLabel: { color: t.muted, formatter: (v: number) => formatPrice(v, Math.min(decimals, 4)) } }),
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      series: [
        {
          id: "intraday",
          type: "line",
          data: points.map((p) => p.v),
          showSymbol: false,
          symbolSize: 8,
          lineStyle: { width: 2, color: t.series1, cap: "round", join: "round" },
          itemStyle: { color: t.series1 },
          areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: t.accentSoft }, { offset: 1, color: "transparent" }] } },
        },
      ],
    }),
    [points, decimals],
  );
  if (points.length < 2) return <p className="text-body text-muted">No intraday prices yet.</p>;
  const first = points[0].v;
  const last = points[points.length - 1].v;
  const hi = Math.max(...points.map((p) => p.v));
  const lo = Math.min(...points.map((p) => p.v));
  const summary = `${label}: ${points.length} 15-minute closes from ${ukTime(points[0].t)} to ${ukTime(points[points.length - 1].t)} UK, ${last >= first ? "up" : "down"} from ${formatPrice(first, decimals)} to ${formatPrice(last, decimals)}; high ${formatPrice(hi, decimals)}, low ${formatPrice(lo, decimals)}.`;
  return <Chart label={label} option={option} summary={summary} table={{ columns: ["Time (UK)", "Close"], rows: points.map((p) => [ukTime(p.t), formatPrice(p.v, decimals)]) }} height={220} />;
}
