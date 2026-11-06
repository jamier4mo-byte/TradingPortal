/** Cumulative R as a thin line with a baseline at 0. Inline SVG: no chart library on a card. */
export function Sparkline({ values, width = 160, height = 40, label = "Cumulative R" }: { values: number[]; width?: number; height?: number; label?: string }) {
  if (values.length < 2) {
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: not enough trades yet`} className="text-subtle">
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="currentColor" strokeDasharray="2 4" strokeWidth="1" />
      </svg>
    );
  }
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const x = (i: number) => (i / (values.length - 1)) * (width - 2) + 1;
  const y = (v: number) => height - 2 - ((v - min) / span) * (height - 4);
  const d = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = values[values.length - 1];
  const tone = last > 0 ? "text-win" : last < 0 ? "text-loss" : "text-breakeven";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: ${last > 0 ? "+" : ""}${last.toFixed(2)}R after ${values.length} trades`} className={tone}>
      <line x1="0" y1={y(0)} x2={width} y2={y(0)} stroke="currentColor" strokeOpacity="0.25" strokeWidth="1" />
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r="2" fill="currentColor" />
    </svg>
  );
}
